# -*- coding: utf-8 -*-
"""API tests for the read-only watchlist research overlay endpoint."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from api.deps import CurrentUser, get_current_user
import src.auth as auth
from src.config import Config
from src.storage import (
    DatabaseManager,
    MarketScannerCandidate,
    MarketScannerRun,
    UserAlertEvent,
    UserAlertRule,
)


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


def _make_user(user_id: str, username: str) -> CurrentUser:
    return CurrentUser(
        user_id=user_id,
        username=username,
        display_name=username.title(),
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


class WatchlistResearchOverlayEndpointTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "watchlist_overlay_endpoint_test.db"
        self.previous_admin_auth_enabled = os.environ.get("ADMIN_AUTH_ENABLED")
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
        os.environ["ADMIN_AUTH_ENABLED"] = "false"
        Config.reset_instance()
        _reset_auth_globals()
        DatabaseManager.reset_instance()
        self.app = create_app(static_dir=self.data_dir / "empty-static")
        self.client = TestClient(self.app)
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
        if self.previous_admin_auth_enabled is None:
            os.environ.pop("ADMIN_AUTH_ENABLED", None)
        else:
            os.environ["ADMIN_AUTH_ENABLED"] = self.previous_admin_auth_enabled
        self.temp_dir.cleanup()

    def _save_scanner_candidate(self) -> int:
        now = datetime(2026, 5, 4, 9, 30, 0)
        run = MarketScannerRun(
            market="us",
            profile="us_preopen_v1",
            universe_name="us_preopen_watchlist_v1",
            status="completed",
            run_at=now,
            completed_at=now,
            shortlist_size=1,
        )
        candidate = MarketScannerCandidate(
            symbol="NVDA",
            name="NVDA",
            rank=1,
            score=82.0,
            reason_summary="Research evidence changed.",
            diagnostics_json=json.dumps(
                {
                    "history": {
                        "source": "local_us_parquet",
                        "latest_trade_date": "2026-05-03",
                    },
                    "candidateResearchSummaryFrame": {
                        "primaryResearchReason": "Structure shifted after fresh volume evidence.",
                        "researchNextStep": "Verify local OHLCV and catalyst evidence.",
                    },
                },
                ensure_ascii=False,
            ),
            created_at=now,
        )
        with self.db.get_session() as session:
            session.add(run)
            session.flush()
            candidate.run_id = run.id
            session.add(candidate)
            session.commit()
            return int(run.id)

    def _alert_counts(self) -> tuple[int, int]:
        with self.db.get_session() as session:
            return int(session.query(UserAlertRule).count()), int(session.query(UserAlertEvent).count())

    def test_research_overlay_endpoint_is_owner_scoped_and_read_only(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")
        run_id = self._save_scanner_candidate()
        add_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={
                "symbol": "NVDA",
                "market": "us",
                "source": "scanner",
                "scanner_run_id": run_id,
                "scanner_rank": 1,
                "scanner_score": 82.0,
                "theme_id": "ai_infra",
            },
        )
        self.assertEqual(add_resp.status_code, 200)
        before_alerts = self._alert_counts()
        items_before = self.client.get("/api/v1/watchlist/items").json()

        response = self.client.get("/api/v1/watchlist/research-overlay")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["schemaVersion"], "watchlist_research_overlay_v1")
        self.assertEqual(payload["overlayState"], "degraded")
        self.assertTrue(payload["observationOnly"])
        self.assertFalse(payload["decisionGrade"])
        self.assertTrue(payload["researchSummary"])
        self.assertEqual([item["ticker"] for item in payload["items"]], ["NVDA"])
        self.assertEqual(len(payload["researchPriorityQueue"]), 1)
        queue_item = payload["researchPriorityQueue"][0]
        self.assertEqual(queue_item["symbol"], "NVDA")
        self.assertEqual(queue_item["priorityTier"], "follow_up")
        self.assertTrue(queue_item["priorityReasonSafeLabel"])
        self.assertEqual(queue_item["evidenceAge"]["state"], "stale_or_cached")
        self.assertTrue(queue_item["suggestedResearchPath"])
        self.assertTrue(queue_item["observationOnly"])
        self.assertEqual(payload["aggregateSummary"]["byThemeOrSector"], {"ai_infra": 1})
        self.assertEqual(
            payload["items"][0]["drilldownTargets"][0]["route"],
            "/stocks/NVDA/structure-decision",
        )
        self.assertEqual(self._alert_counts(), before_alerts)
        self.assertEqual(self.client.get("/api/v1/watchlist/items").json(), items_before)

        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-2", "bob")
        other_response = self.client.get("/api/v1/watchlist/research-overlay")
        self.assertEqual(other_response.status_code, 200)
        self.assertEqual(other_response.json()["items"], [])


if __name__ == "__main__":
    unittest.main()
