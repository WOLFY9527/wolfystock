# -*- coding: utf-8 -*-
"""API tests for owner-scoped in-app user alerts."""

from __future__ import annotations

from datetime import datetime, timezone
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
from src.services.user_alert_dry_run_pipeline import build_user_alert_dry_run_pipeline_result
from src.services.user_alert_service import UserAlertService
from src.storage import DatabaseManager


_API_DRY_RUN_FIELDS = {
    "conditionObserved",
    "condition_observed",
    "dedupeFingerprint",
    "dedupe_fingerprint",
    "dedupeKey",
    "dedupe_key",
    "dryRun",
    "dry_run",
    "eventPacket",
    "event_packet",
    "fingerprint",
    "freshness",
    "freshnessStatus",
    "freshness_status",
    "liveOutbound",
    "live_outbound",
    "localOnly",
    "local_only",
    "marketCacheMutation",
    "market_cache_mutation",
    "networkCallsEnabled",
    "network_calls_enabled",
    "noSend",
    "no_send",
    "observedAsOf",
    "observed_as_of",
    "observedAt",
    "observed_at",
    "observedPrice",
    "observed_price",
    "outboundAttempted",
    "outbound_attempted",
    "providerRuntimeCalled",
    "provider_runtime_called",
    "safeMetadata",
    "safe_metadata",
    "suppression",
    "suppressionState",
    "suppression_state",
    "suppressed",
    "suppressedLocalRecord",
    "suppressed_local_record",
}
_RULE_RESPONSE_KEYS = {
    "id",
    "contractVersion",
    "ruleType",
    "symbol",
    "direction",
    "thresholdPrice",
    "enabled",
    "note",
    "deliveryMode",
    "inAppOnly",
    "ownerScoped",
    "createdAt",
    "updatedAt",
}
_RULE_LIST_RESPONSE_KEYS = {
    "contractVersion",
    "deliveryMode",
    "inAppOnly",
    "ownerScoped",
    "items",
}
_EVENT_RESPONSE_KEYS = {
    "id",
    "contractVersion",
    "eventType",
    "ruleId",
    "symbol",
    "direction",
    "thresholdPrice",
    "title",
    "message",
    "deliveryMode",
    "inAppOnly",
    "ownerScoped",
    "readAt",
    "createdAt",
}
_EVENT_LIST_RESPONSE_KEYS = {
    "contractVersion",
    "deliveryMode",
    "inAppOnly",
    "ownerScoped",
    "total",
    "limit",
    "offset",
    "items",
}
_DRY_RUN_RESPONSE_KEYS = {
    "dryRun",
    "noSend",
    "outboundAttempted",
    "liveOutbound",
    "localOnly",
    "suppressedLocalRecord",
    "evaluation",
    "suppression",
    "eventPacket",
}


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}
    try:
        from api.middlewares.public_abuse_limiter import reset_public_api_abuse_limiter_state
    except ModuleNotFoundError:
        return
    reset_public_api_abuse_limiter_state()


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


def _assert_no_api_dry_run_fields(test_case: unittest.TestCase, payload: object) -> None:
    if isinstance(payload, dict):
        unexpected = sorted(_API_DRY_RUN_FIELDS.intersection(payload))
        test_case.assertEqual(unexpected, [])
        for value in payload.values():
            _assert_no_api_dry_run_fields(test_case, value)
        return
    if isinstance(payload, list):
        for item in payload:
            _assert_no_api_dry_run_fields(test_case, item)


def _assert_response_keys(
    test_case: unittest.TestCase,
    payload: dict[str, object],
    expected_keys: set[str],
) -> None:
    test_case.assertEqual(set(payload), expected_keys)


class UserAlertsApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_admin_auth_enabled = os.environ.get("ADMIN_AUTH_ENABLED")
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
        os.environ["ADMIN_AUTH_ENABLED"] = "false"
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
        os.environ["ADMIN_AUTH_ENABLED"] = "true"
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
        if self.previous_admin_auth_enabled is None:
            os.environ.pop("ADMIN_AUTH_ENABLED", None)
        else:
            os.environ["ADMIN_AUTH_ENABLED"] = self.previous_admin_auth_enabled
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
        _assert_response_keys(self, created, _RULE_RESPONSE_KEYS)
        _assert_no_api_dry_run_fields(self, created)
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
        listed = list_resp.json()
        _assert_response_keys(self, listed, _RULE_LIST_RESPONSE_KEYS)
        _assert_no_api_dry_run_fields(self, listed)
        self.assertEqual(listed["items"][0]["id"], created["id"])
        _assert_response_keys(self, listed["items"][0], _RULE_RESPONSE_KEYS)

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
        _assert_response_keys(self, updated, _RULE_RESPONSE_KEYS)
        _assert_no_api_dry_run_fields(self, updated)
        self.assertEqual(updated["direction"], "below")
        self.assertEqual(updated["thresholdPrice"], 118.25)
        self.assertFalse(updated["enabled"])
        self.assertIsNone(updated["note"])

        delete_resp = self.client.delete(f"/api/v1/user-alerts/rules/{created['id']}")
        self.assertEqual(delete_resp.status_code, 200)
        self.assertEqual(delete_resp.json(), {"deleted": 1})
        after_delete = self.client.get("/api/v1/user-alerts/rules").json()
        _assert_response_keys(self, after_delete, _RULE_LIST_RESPONSE_KEYS)
        _assert_no_api_dry_run_fields(self, after_delete)
        self.assertEqual(after_delete["items"], [])

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

    def test_api_created_rule_feeds_pure_dry_run_helper_without_send_or_persisting_events(
        self,
    ) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")
        observed_at = datetime(2026, 6, 8, 10, 30, tzinfo=timezone.utc)
        recorded_at = datetime(2026, 6, 8, 10, 31, tzinfo=timezone.utc)

        with (
            patch("data_provider.base.DataFetcherManager.get_realtime_quote") as get_quote,
            patch("src.services.notification_service.NotificationService.emit_event") as emit_event,
            patch("src.services.notification_service.NotificationDeliveryClient.send_webhook") as send_webhook,
        ):
            create_resp = self.client.post(
                "/api/v1/user-alerts/rules",
                json={
                    "symbol": "nvda",
                    "direction": "above",
                    "thresholdPrice": 125.5,
                    "enabled": True,
                    "note": "Use helper input without API dry-run fields.",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            created = create_resp.json()
            _assert_no_api_dry_run_fields(self, created)

            rules_resp = self.client.get("/api/v1/user-alerts/rules")
            self.assertEqual(rules_resp.status_code, 200)
            _assert_no_api_dry_run_fields(self, rules_resp.json())

            before_events_resp = self.client.get("/api/v1/user-alerts/events")
            self.assertEqual(before_events_resp.status_code, 200)
            before_events = before_events_resp.json()
            _assert_no_api_dry_run_fields(self, before_events)
            self.assertEqual(before_events["total"], 0)
            self.assertEqual(before_events["items"], [])

            result = build_user_alert_dry_run_pipeline_result(
                rule=created,
                observed_price=130.0,
                observed_at=observed_at,
                freshness={"status": "fresh", "maxAgeMinutes": 120},
                suppression={
                    "muted": False,
                    "snoozedUntil": None,
                    "cooldownStartedAt": None,
                    "cooldownSeconds": None,
                    "previousFingerprint": "older-local-fingerprint",
                    "previousTimeBucket": "202606080900",
                },
                now=observed_at,
                recorded_at=recorded_at,
            )

            after_events_resp = self.client.get("/api/v1/user-alerts/events")
            self.assertEqual(after_events_resp.status_code, 200)
            after_events = after_events_resp.json()
            _assert_no_api_dry_run_fields(self, after_events)

        get_quote.assert_not_called()
        emit_event.assert_not_called()
        send_webhook.assert_not_called()

        self.assertEqual(after_events, before_events)
        self.assertEqual(after_events["total"], 0)
        self.assertEqual(after_events["items"], [])

        self.assertTrue(result["dryRun"])
        self.assertTrue(result["noSend"])
        self.assertTrue(result["localOnly"])
        self.assertFalse(result["outboundAttempted"])
        self.assertFalse(result["liveOutbound"])

        evaluation = result["evaluation"]
        self.assertEqual(evaluation["ruleType"], "watchlist_price_threshold")
        self.assertEqual(evaluation["subject"], "NVDA")
        self.assertEqual(evaluation["direction"], "above")
        self.assertEqual(evaluation["thresholdPrice"], 125.5)
        self.assertEqual(evaluation["state"], "condition_observed")
        self.assertTrue(evaluation["conditionObserved"])
        self.assertFalse(evaluation["suppressed"])
        self.assertFalse(evaluation["providerRuntimeCalled"])
        self.assertFalse(evaluation["networkCallsEnabled"])
        self.assertFalse(evaluation["marketCacheMutation"])

        packet = result["eventPacket"]
        self.assertIsNotNone(packet)
        assert packet is not None
        self.assertTrue(packet["dryRun"])
        self.assertTrue(packet["localOnly"])
        self.assertFalse(packet["outboundAttempted"])
        self.assertFalse(packet["liveOutbound"])
        self.assertEqual(packet["eventType"], "user.alert_dry_run_evaluation")
        self.assertEqual(packet["safeMetadata"]["subject"], "NVDA")

    def test_owner_can_dry_run_rule_with_caller_supplied_context_without_send_or_persisting_events(
        self,
    ) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")
        observed_at = datetime.now(timezone.utc)
        created = self.client.post(
            "/api/v1/user-alerts/rules",
            json={
                "symbol": "nvda",
                "direction": "above",
                "thresholdPrice": 125.5,
                "enabled": True,
            },
        ).json()
        before_events = self.client.get("/api/v1/user-alerts/events").json()
        self.assertEqual(before_events["total"], 0)

        with (
            patch("data_provider.base.DataFetcherManager.get_realtime_quote") as get_quote,
            patch("src.services.notification_service.NotificationService.emit_event") as emit_event,
            patch("src.services.notification_service.NotificationDeliveryClient.send_webhook") as send_webhook,
        ):
            response = self.client.post(
                f"/api/v1/user-alerts/rules/{created['id']}/dry-run",
                json={
                    "observedPrice": 130.0,
                    "observedAt": observed_at.isoformat(),
                    "freshness": {"status": "fresh", "maxAgeMinutes": 120},
                    "suppression": {
                        "muted": False,
                        "snoozedUntil": None,
                        "cooldownStartedAt": None,
                        "cooldownSeconds": None,
                        "previousFingerprint": "older-local-fingerprint",
                        "previousTimeBucket": "202606080900",
                    },
                },
            )
            after_events = self.client.get("/api/v1/user-alerts/events").json()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        _assert_response_keys(self, payload, _DRY_RUN_RESPONSE_KEYS)
        self.assertTrue(payload["dryRun"])
        self.assertTrue(payload["noSend"])
        self.assertFalse(payload["outboundAttempted"])
        self.assertFalse(payload["liveOutbound"])
        self.assertTrue(payload["localOnly"])
        self.assertFalse(payload["suppressedLocalRecord"])

        evaluation = payload["evaluation"]
        self.assertEqual(evaluation["state"], "condition_observed")
        self.assertTrue(evaluation["conditionObserved"])
        self.assertFalse(evaluation["providerRuntimeCalled"])
        self.assertFalse(evaluation["networkCallsEnabled"])
        self.assertFalse(evaluation["marketCacheMutation"])
        self.assertEqual(evaluation["subject"], "NVDA")
        self.assertEqual(evaluation["observedPrice"], 130.0)
        self.assertEqual(evaluation["freshnessStatus"], "fresh")
        self.assertEqual(payload["suppression"]["state"], "allowed")
        self.assertIsNotNone(payload["eventPacket"])

        self.assertEqual(after_events, before_events)
        get_quote.assert_not_called()
        emit_event.assert_not_called()
        send_webhook.assert_not_called()

    def test_dry_run_rule_is_owner_scoped(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")
        created = self.client.post(
            "/api/v1/user-alerts/rules",
            json={"symbol": "AAPL", "direction": "below", "thresholdPrice": 150},
        ).json()

        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-2", "bob")
        response = self.client.post(
            f"/api/v1/user-alerts/rules/{created['id']}/dry-run",
            json={
                "observedPrice": 149.0,
                "observedAt": datetime.now(timezone.utc).isoformat(),
                "freshness": {"status": "fresh"},
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get("/api/v1/user-alerts/events").json()["total"], 0)
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")
        self.assertEqual(self.client.get("/api/v1/user-alerts/events").json()["total"], 0)

    def test_dry_run_requires_current_user(self) -> None:
        client = self._make_auth_enabled_client()
        response = client.post(
            "/api/v1/user-alerts/rules/1/dry-run",
            json={
                "observedPrice": 130.0,
                "observedAt": datetime.now(timezone.utc).isoformat(),
                "freshness": {"status": "fresh"},
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "unauthorized")
        client.close()

    def test_dry_run_rejects_transitional_current_user(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            user_id="bootstrap",
            username="bootstrap",
            display_name="Bootstrap",
            role="user",
            is_admin=False,
            is_authenticated=False,
            transitional=True,
            auth_enabled=False,
        )

        response = self.client.post(
            "/api/v1/user-alerts/rules/1/dry-run",
            json={
                "observedPrice": 130.0,
                "observedAt": datetime.now(timezone.utc).isoformat(),
                "freshness": {"status": "fresh"},
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "unauthorized")

    def test_dry_run_stale_freshness_remains_blocked(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")
        created = self.client.post(
            "/api/v1/user-alerts/rules",
            json={"symbol": "MSFT", "direction": "above", "thresholdPrice": 425.0},
        ).json()

        response = self.client.post(
            f"/api/v1/user-alerts/rules/{created['id']}/dry-run",
            json={
                "observedPrice": 430.0,
                "observedAt": datetime.now(timezone.utc).isoformat(),
                "freshness": {"status": "stale"},
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["dryRun"])
        self.assertTrue(payload["noSend"])
        self.assertFalse(payload["outboundAttempted"])
        self.assertFalse(payload["liveOutbound"])
        self.assertTrue(payload["localOnly"])
        self.assertEqual(payload["evaluation"]["state"], "blocked_insufficient_data")
        self.assertFalse(payload["evaluation"]["conditionObserved"])

    def test_dry_run_requires_freshness_context(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")
        created = self.client.post(
            "/api/v1/user-alerts/rules",
            json={"symbol": "MSFT", "direction": "above", "thresholdPrice": 425.0},
        ).json()

        response = self.client.post(
            f"/api/v1/user-alerts/rules/{created['id']}/dry-run",
            json={
                "observedPrice": 430.0,
                "observedAt": datetime.now(timezone.utc).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_dry_run_rejects_raw_or_incomplete_suppression_context(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")
        created = self.client.post(
            "/api/v1/user-alerts/rules",
            json={"symbol": "MSFT", "direction": "above", "thresholdPrice": 425.0},
        ).json()

        raw_freshness = self.client.post(
            f"/api/v1/user-alerts/rules/{created['id']}/dry-run",
            json={
                "observedPrice": 430.0,
                "observedAt": datetime.now(timezone.utc).isoformat(),
                "freshness": {"status": "fresh", "providerTrace": {"raw": "must-not-leak"}},
            },
        )
        self.assertEqual(raw_freshness.status_code, 422)

        incomplete_cooldown = self.client.post(
            f"/api/v1/user-alerts/rules/{created['id']}/dry-run",
            json={
                "observedPrice": 430.0,
                "observedAt": datetime.now(timezone.utc).isoformat(),
                "freshness": {"status": "fresh"},
                "suppression": {"cooldownSeconds": 60},
            },
        )
        self.assertEqual(incomplete_cooldown.status_code, 422)

    def test_event_payload_is_sanitized_in_app_only_and_owner_scoped(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")
        create_resp = self.client.post(
            "/api/v1/user-alerts/rules",
            json={"symbol": "TSLA", "direction": "above", "thresholdPrice": 200},
        )
        self.assertEqual(create_resp.status_code, 200)
        created = create_resp.json()
        UserAlertService(db_manager=self.db).record_in_app_event(
            owner_id="user-1",
            rule_id=created["id"],
            title="Price threshold condition recorded",
            message="Condition recorded for in-app review.",
        )

        events_resp = self.client.get("/api/v1/user-alerts/events")
        self.assertEqual(events_resp.status_code, 200)
        payload = events_resp.json()
        _assert_response_keys(self, payload, _EVENT_LIST_RESPONSE_KEYS)
        _assert_no_api_dry_run_fields(self, payload)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(len(payload["items"]), 1)
        _assert_response_keys(self, payload["items"][0], _EVENT_RESPONSE_KEYS)
        self.assertEqual(payload["contractVersion"], "user_alert_contract_v1")
        self.assertTrue(payload["inAppOnly"])
        self.assertEqual(payload["deliveryMode"], "in_app")
        self.assertEqual(payload["items"][0]["eventType"], "watchlist_price_threshold")
        self.assertEqual(payload["items"][0]["symbol"], "TSLA")
        self.assertEqual(payload["items"][0]["direction"], "above")
        self.assertEqual(payload["items"][0]["deliveryMode"], "in_app")
        self.assertTrue(payload["items"][0]["inAppOnly"])
        self.assertTrue(payload["items"][0]["ownerScoped"])
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
