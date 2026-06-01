# -*- coding: utf-8 -*-
"""API tests for owner-scoped in-app user alerts."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.auth as auth
from api.app import create_app
from api.deps import CurrentUser, get_current_user
from src.config import Config
from src.storage import DatabaseManager


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


class UserAlertsApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "user_alerts_api_test.db"
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
        self.app = create_app(static_dir=self.data_dir / "empty-static")
        self.client = TestClient(self.app)
        self.db = DatabaseManager.get_instance()
        self.db.create_or_update_app_user(user_id="user-1", username="alice", role="user")
        self.db.create_or_update_app_user(user_id="user-2", username="bob", role="user")

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

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()
        self.client.close()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        _reset_auth_globals()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def test_owner_can_create_list_update_and_delete_own_alert_rules(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        create_resp = self.client.post(
            "/api/v1/user-alerts/rules",
            json={
                "symbol": "nvda",
                "direction": "above",
                "thresholdPrice": 125.5,
                "enabled": True,
                "note": "Watch only in app.",
            },
        )
        self.assertEqual(create_resp.status_code, 200)
        created = create_resp.json()
        self.assertEqual(created["contractVersion"], "user_alert_contract_v1")
        self.assertEqual(created["ruleType"], "watchlist_price_threshold")
        self.assertEqual(created["symbol"], "NVDA")
        self.assertEqual(created["direction"], "above")
        self.assertEqual(created["thresholdPrice"], 125.5)
        self.assertTrue(created["inAppOnly"])
        self.assertEqual(created["deliveryMode"], "in_app")
        self.assertTrue(created["ownerScoped"])
        self.assertNotIn("buy", str(created).lower())
        self.assertNotIn("order", str(created).lower())

        list_resp = self.client.get("/api/v1/user-alerts/rules")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list_resp.json()["items"][0]["id"], created["id"])

        update_resp = self.client.patch(
            f"/api/v1/user-alerts/rules/{created['id']}",
            json={
                "direction": "below",
                "thresholdPrice": 118.25,
                "enabled": False,
                "note": None,
            },
        )
        self.assertEqual(update_resp.status_code, 200)
        updated = update_resp.json()
        self.assertEqual(updated["direction"], "below")
        self.assertEqual(updated["thresholdPrice"], 118.25)
        self.assertFalse(updated["enabled"])
        self.assertIsNone(updated["note"])

        delete_resp = self.client.delete(f"/api/v1/user-alerts/rules/{created['id']}")
        self.assertEqual(delete_resp.status_code, 200)
        self.assertEqual(delete_resp.json(), {"deleted": 1})
        self.assertEqual(self.client.get("/api/v1/user-alerts/rules").json()["items"], [])

    def test_guest_or_unauthorized_access_is_rejected(self) -> None:
        client = self._make_auth_enabled_client()
        response = client.get("/api/v1/user-alerts/rules")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "unauthorized")
        client.close()

    def test_another_owner_cannot_access_or_mutate_rule(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")
        created = self.client.post(
            "/api/v1/user-alerts/rules",
            json={"symbol": "AAPL", "direction": "below", "thresholdPrice": 150},
        ).json()

        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-2", "bob")
        self.assertEqual(self.client.get("/api/v1/user-alerts/rules").json()["items"], [])
        mutate_resp = self.client.patch(
            f"/api/v1/user-alerts/rules/{created['id']}",
            json={"enabled": False},
        )
        self.assertEqual(mutate_resp.status_code, 404)
        delete_resp = self.client.delete(f"/api/v1/user-alerts/rules/{created['id']}")
        self.assertEqual(delete_resp.status_code, 404)

    def test_invalid_threshold_or_direction_is_rejected(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        bad_direction = self.client.post(
            "/api/v1/user-alerts/rules",
            json={"symbol": "AAPL", "direction": "near", "thresholdPrice": 150},
        )
        self.assertEqual(bad_direction.status_code, 422)

        bad_threshold = self.client.post(
            "/api/v1/user-alerts/rules",
            json={"symbol": "AAPL", "direction": "above", "thresholdPrice": 0},
        )
        self.assertEqual(bad_threshold.status_code, 422)

    def test_no_provider_quote_or_notification_delivery_is_invoked(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        with (
            patch("data_provider.base.DataFetcherManager.get_realtime_quote") as get_quote,
            patch("src.services.notification_service.NotificationService.emit_event") as emit_event,
            patch("src.services.notification_service.NotificationDeliveryClient.send_webhook") as send_webhook,
        ):
            response = self.client.post(
                "/api/v1/user-alerts/rules",
                json={"symbol": "MSFT", "direction": "above", "thresholdPrice": 425.0},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.client.get("/api/v1/user-alerts/events").status_code, 200)

        get_quote.assert_not_called()
        emit_event.assert_not_called()
        send_webhook.assert_not_called()

    def test_event_payload_is_sanitized_in_app_only_and_owner_scoped(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")
        create_resp = self.client.post(
            "/api/v1/user-alerts/rules",
            json={"symbol": "TSLA", "direction": "above", "thresholdPrice": 200},
        )
        self.assertEqual(create_resp.status_code, 200)
        events_resp = self.client.get("/api/v1/user-alerts/events")
        self.assertEqual(events_resp.status_code, 200)
        payload = events_resp.json()
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["contractVersion"], "user_alert_contract_v1")
        self.assertTrue(payload["inAppOnly"])
        self.assertEqual(payload["deliveryMode"], "in_app")
        self.assertNotIn("provider", str(payload).lower())
        self.assertNotIn("admin", str(payload).lower())
        self.assertNotIn("webhook", str(payload).lower())

    def test_admin_notification_api_remains_registered(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        response = self.client.get("/api/v1/admin/notification-channels")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "admin_required")


if __name__ == "__main__":
    unittest.main()
