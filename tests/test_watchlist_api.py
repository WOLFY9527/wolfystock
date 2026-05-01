# -*- coding: utf-8 -*-
"""Integration tests for user-owned scanner watchlist endpoints."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from api.deps import CurrentUser, get_current_user
import src.auth as auth
from src.config import Config
from src.storage import DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


def _make_user(user_id: str, username: str, *, is_admin: bool = False, auth_enabled: bool = True) -> CurrentUser:
    return CurrentUser(
        user_id=user_id,
        username=username,
        display_name=username.title(),
        role="admin" if is_admin else "user",
        is_admin=is_admin,
        is_authenticated=True,
        transitional=False,
        auth_enabled=auth_enabled,
    )


class WatchlistApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "watchlist_api_test.db"
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=false",
                    f"DATABASE_PATH={self.db_path}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.db_path)
        Config.reset_instance()
        _reset_auth_globals()
        DatabaseManager.reset_instance()
        app = create_app(static_dir=self.data_dir / "empty-static")
        self.app = app
        self.client = TestClient(app)
        self.db = DatabaseManager.get_instance()
        self.db.create_or_update_app_user(
            user_id="user-1",
            username="alice",
            role="user",
            display_name="Alice",
        )
        self.db.create_or_update_app_user(
            user_id="user-2",
            username="bob",
            role="user",
            display_name="Bob",
        )

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        _reset_auth_globals()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def _make_auth_enabled_client(self) -> TestClient:
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=true",
                    f"DATABASE_PATH={self.db_path}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.db_path)
        Config.reset_instance()
        _reset_auth_globals()
        app = create_app(static_dir=self.data_dir / "empty-static")
        return TestClient(app)

    def test_watchlist_add_list_is_owner_scoped_and_preserves_scanner_metadata(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        add_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={
                "symbol": "NVDA",
                "market": "us",
                "name": "NVIDIA",
                "source": "scanner",
                "scanner_run_id": 11,
                "scanner_rank": 1,
                "scanner_score": 94,
                "theme_id": "crypto_miners",
                "universe_type": "default",
                "notes": "Backend reason: momentum and liquidity improved.",
            },
        )
        self.assertEqual(add_resp.status_code, 200)
        payload = add_resp.json()
        self.assertEqual(payload["symbol"], "NVDA")
        self.assertEqual(payload["market"], "us")
        self.assertEqual(payload["scanner_run_id"], 11)
        self.assertEqual(payload["scanner_rank"], 1)
        self.assertEqual(payload["scanner_score"], 94.0)
        self.assertEqual(payload["theme_id"], "crypto_miners")
        self.assertEqual(payload["universe_type"], "default")

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.json()["items"]), 1)

        logs, total = self.db.list_execution_log_sessions(task_id="portfolio:watchlist_add", limit=10)
        self.assertEqual(total, 1)
        self.assertEqual(logs[0]["code"], "NVDA")
        self.assertEqual(logs[0]["summary"]["portfolio_event"]["category"], "watchlist")
        self.assertEqual(logs[0]["summary"]["portfolio_event"]["scanner_run_id"], 11)

    def test_watchlist_duplicate_add_is_idempotent_and_delete_is_owner_scoped(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        first_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "MARA", "market": "us", "source": "scanner"},
        )
        self.assertEqual(first_resp.status_code, 200)
        first_item = first_resp.json()

        second_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "MARA", "market": "us", "source": "scanner", "notes": "updated note"},
        )
        self.assertEqual(second_resp.status_code, 200)
        second_item = second_resp.json()
        self.assertEqual(second_item["id"], first_item["id"])
        self.assertEqual(second_item["notes"], "updated note")

        delete_resp = self.client.delete(f"/api/v1/watchlist/items/{first_item['id']}")
        self.assertEqual(delete_resp.status_code, 200)
        self.assertEqual(delete_resp.json()["deleted"], 1)

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list_resp.json()["items"], [])

    def test_watchlist_items_do_not_leak_between_users(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")
        create_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "AVGO", "market": "us", "source": "scanner"},
        )
        self.assertEqual(create_resp.status_code, 200)
        item_id = create_resp.json()["id"]

        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-2", "bob")
        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list_resp.json()["items"], [])

        delete_resp = self.client.delete(f"/api/v1/watchlist/items/{item_id}")
        self.assertEqual(delete_resp.status_code, 404)

    def test_watchlist_unauthorized_add_is_rejected_when_auth_is_enabled(self) -> None:
        client = self._make_auth_enabled_client()
        resp = client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "NVDA", "market": "us", "source": "scanner"},
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["error"], "unauthorized")

    def test_watchlist_validation_rejects_invalid_symbol_and_market(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        bad_symbol = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "???", "market": "us", "source": "scanner"},
        )
        self.assertEqual(bad_symbol.status_code, 422)

        bad_market = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "NVDA", "market": "EU", "source": "scanner"},
        )
        self.assertEqual(bad_market.status_code, 422)
