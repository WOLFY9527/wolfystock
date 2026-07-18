# -*- coding: utf-8 -*-
"""Admin operational notification channel API and service tests."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from api.deps import CurrentUser, get_current_user
from api.v1 import api_v1_router
from api.v1.endpoints import admin_logs, admin_notifications
from src.services.notification_service import NotificationDeliveryClient, NotificationService
from src.services.quota_policy_service import QuotaPolicyService
from src.storage import (
    DatabaseManager,
    NotificationChannel as NotificationChannelRow,
    PortfolioAccount,
    PortfolioCashLedger,
    PortfolioTrade,
)


def _admin_user() -> CurrentUser:
    return CurrentUser(
        user_id="bootstrap-admin",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("ops:notifications:read", "ops:notifications:write"),
    )


def _regular_user() -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="alice",
        display_name="Alice",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


class FakeDeliveryClient(NotificationDeliveryClient):
    def __init__(self, *, fail: bool = False, failure_message: str = "mock webhook failure") -> None:
        self.fail = fail
        self.failure_message = failure_message
        self.webhook_calls: list[dict] = []

    def send_webhook(self, *, url: str, payload: dict, headers: dict | None = None, timeout: float = 5.0) -> None:
        self.webhook_calls.append({"url": url, "payload": payload, "headers": headers or {}, "timeout": timeout})
        if self.fail:
            raise RuntimeError(self.failure_message)


class FakeAdminNotificationService:
    def __init__(self) -> None:
        self.create_calls: list[dict] = []

    def create_channel(self, **kwargs):
        self.create_calls.append(kwargs)
        return {
            "id": 101,
            "name": kwargs["name"],
            "type": kwargs["type"],
            "enabled": kwargs["enabled"],
            "severity_min": kwargs["severity_min"],
            "event_types": list(kwargs["event_types"]),
            "config": dict(kwargs["config"]),
            "created_at": None,
            "updated_at": None,
            "last_tested_at": None,
            "last_sent_at": None,
            "last_error": None,
        }


class NotificationChannelsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.db = DatabaseManager(db_url="sqlite:///:memory:")
        self.delivery = FakeDeliveryClient()
        self.service = NotificationService(db=self.db, delivery_client=self.delivery)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def _replace_database(self, db_url: str) -> DatabaseManager:
        DatabaseManager.reset_instance()
        self.db = DatabaseManager(db_url=db_url)
        return self.db

    def _app(self, user: CurrentUser | None = None) -> TestClient:
        app = FastAPI()
        app.include_router(api_v1_router)
        app.dependency_overrides[get_current_user] = lambda: user or _admin_user()
        return TestClient(app)

    def test_channel_crud_requires_admin_auth(self) -> None:
        client = self._app(_regular_user())

        response = client.get("/api/v1/admin/notification-channels")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["error"], "admin_required")

    def test_create_channel_post_route_is_registered_on_v1_router(self) -> None:
        client = self._app()
        fake_service = FakeAdminNotificationService()

        with patch("api.v1.endpoints.admin_notifications.NotificationService", return_value=fake_service):
            response = client.post(
                "/api/v1/admin/notification-channels",
                json={
                    "name": "Ops inbox",
                    "type": "in_app",
                    "enabled": True,
                    "severity_min": "warning",
                    "event_types": ["admin_logs.storage"],
                    "config": {},
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["name"], "Ops inbox")
        self.assertEqual(payload["channel_type"], "in_app")
        self.assertEqual(len(fake_service.create_calls), 1)
        self.assertEqual(fake_service.create_calls[0]["name"], "Ops inbox")

    def test_channel_api_projects_safe_operator_status_from_leaky_service_payload(self) -> None:
        client = self._app()

        class LeakyNotificationService:
            def list_system_channels(self):
                return ["email"]

            def list_channels(self):
                return [
                    {
                        "id": 7,
                        "name": "Ops webhook",
                        "type": "webhook",
                        "enabled": True,
                        "severity_min": "warning",
                        "event_types": ["admin_logs.storage"],
                        "config": {
                            "webhook_url": "https://user:pass@hooks.example.test/services/raw/path",
                            "token": "route-token",
                            "email_destination": "alice@example.com",
                            "provider_credentials": {"password": "provider-password"},
                        },
                        "target_summary": "webhook:https://hooks.example.test/services/raw/path",
                        "last_tested_at": "2026-06-14T01:02:03",
                        "last_status": "failed",
                        "last_error": "Traceback token=raw-token /tmp/provider.py",
                        "last_error_diagnostics": {
                            "provider_error": "raw provider response token=raw-token",
                            "filesystem_path": "/tmp/provider.py",
                        },
                    },
                    {
                        "id": 8,
                        "name": "Disabled webhook",
                        "type": "webhook",
                        "enabled": False,
                        "config": {"webhook_url": "https://hooks.example.test/disabled"},
                        "target_summary": "webhook:configured",
                        "last_status": "disabled",
                    },
                    {
                        "id": 9,
                        "name": "Unconfigured webhook",
                        "type": "webhook",
                        "enabled": True,
                        "config": {},
                        "target_summary": "webhook:unconfigured",
                        "last_status": "unknown",
                    },
                ]

            def test_channel(self, channel_id: int, *, dry_run: bool = False):
                return {
                    "success": False,
                    "dry_run": bool(dry_run),
                    "target_summary": "webhook:https://hooks.example.test/services/raw/path",
                    "error": "Traceback token=raw-token /tmp/provider.py",
                    "error_code": "webhook_delivery_failed",
                    "diagnostics": {
                        "provider_error": "raw provider response token=raw-token",
                        "filesystem_path": "/tmp/provider.py",
                    },
                    "channel": self.list_channels()[0],
                }

        with patch("api.v1.endpoints.admin_notifications.NotificationService", return_value=LeakyNotificationService()):
            list_response = client.get("/api/v1/admin/notification-channels")
            test_response = client.post("/api/v1/admin/notification-channels/7/test?dry_run=true")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(test_response.status_code, 200)
        combined = f"{list_response.json()} {test_response.json()}"
        for leaked in (
            "user:pass",
            "/services/raw/path",
            "route-token",
            "alice@example.com",
            "provider-password",
            "raw-token",
            "raw provider response",
            "/tmp/provider.py",
            "Traceback",
            "diagnostics",
            "target_summary",
            "last_error",
        ):
            self.assertNotIn(leaked, combined)
        self.assertNotIn("'config':", combined)
        item = list_response.json()["items"][0]
        self.assertEqual(item["channel_type"], "webhook")
        self.assertTrue(item["configured"])
        self.assertEqual(item["delivery_mode"], "webhook")
        self.assertEqual(item["status"], "failed")
        self.assertEqual(item["last_checked_at"], "2026-06-14T01:02:03")
        disabled = list_response.json()["items"][1]
        self.assertTrue(disabled["configured"])
        self.assertEqual(disabled["delivery_mode"], "no_send")
        self.assertEqual(disabled["status"], "disabled")
        unconfigured = list_response.json()["items"][2]
        self.assertFalse(unconfigured["configured"])
        self.assertEqual(unconfigured["delivery_mode"], "no_send")
        self.assertEqual(unconfigured["status"], "unavailable")
        test_payload = test_response.json()
        self.assertEqual(test_payload["status"], "failed")
        self.assertEqual(test_payload["error_code"], "webhook_delivery_failed")
        self.assertEqual(test_payload["channel"]["status"], "failed")

    def test_webhook_url_validation_rejects_non_http_targets(self) -> None:
        with self.assertRaises(ValueError):
            self.service.create_channel(
                name="bad webhook",
                type="webhook",
                enabled=True,
                severity_min="warning",
                event_types=[],
                config={"webhook_url": "file:///tmp/notify"},
            )

    def test_secrets_and_webhook_url_are_masked_in_api_output(self) -> None:
        channel = self.service.create_channel(
            name="ops webhook",
            type="webhook",
            enabled=True,
            severity_min="warning",
            event_types=["admin_logs.storage"],
            config={
                "webhook_url": "https://user:pass@hooks.example.test/services/SECRET/PATH",
                "token": "super-secret-token",
            },
        )

        payload = self.service.list_channels()

        self.assertEqual(payload[0]["id"], channel["id"])
        self.assertNotIn("super-secret-token", str(payload))
        self.assertNotIn("user:pass", str(payload))
        self.assertNotIn("/services/SECRET/PATH", str(payload))
        self.assertEqual(payload[0]["config"]["token"], "********")
        self.assertEqual(payload[0]["config"]["webhook_url"], "https://hooks.example.test/***")

    def test_disabled_channels_do_not_send(self) -> None:
        self.service.create_channel(
            name="disabled webhook",
            type="webhook",
            enabled=False,
            severity_min="info",
            event_types=[],
            config={"webhook_url": "https://hooks.example.test/disabled"},
        )

        event = self.service.emit_event(
            event_type="scanner.failure",
            severity="critical",
            title="Scanner failed",
            message="Scanner run failed",
            payload={"run_id": 123},
            fingerprint="scanner:123",
        )

        self.assertEqual(self.delivery.webhook_calls, [])
        self.assertEqual(event["delivery_status"], "no_channels")

    def test_channel_opt_out_update_suppresses_matching_delivery(self) -> None:
        channel = self.service.create_channel(
            name="ops webhook",
            type="webhook",
            enabled=True,
            severity_min="warning",
            event_types=["admin_logs.storage"],
            config={"webhook_url": "https://hooks.example.test/opt-out"},
        )
        updated = self.service.update_channel(channel["id"], enabled=False)

        class ExplodingSystemNotifier:
            def __init__(self, *_args, **_kwargs):
                raise AssertionError("system notification sender should not be constructed")

        with (
            patch("urllib.request.urlopen", side_effect=AssertionError("network call attempted")) as mock_urlopen,
            patch("src.services.notification_service.SystemNotificationService", ExplodingSystemNotifier),
        ):
            event = self.service.emit_event(
                event_type="admin_logs.storage",
                severity="critical",
                title="Storage critical",
                message="Disabled route should stay local",
                payload={"owner_user_id": "user-1"},
                fingerprint="storage:opt-out-disabled",
            )

        self.assertFalse(updated["enabled"])
        self.assertEqual(event["delivery_status"], "no_channels")
        self.assertEqual(self.delivery.webhook_calls, [])
        mock_urlopen.assert_not_called()
        listed = self.service.list_channels()[0]
        self.assertEqual(listed["last_status"], "disabled")
        self.assertIsNone(listed["last_sent_at"])

    def test_default_delivery_requires_explicit_opt_in_route_and_target(self) -> None:
        event = self.service.emit_event(
            event_type="admin_logs.storage",
            severity="critical",
            title="Storage critical",
            message="Storage threshold exceeded",
            payload={"session_id": "run-1"},
            fingerprint="storage:explicit-opt-in",
        )

        self.assertEqual(event["delivery_status"], "no_channels")
        self.assertEqual(self.delivery.webhook_calls, [])
        with self.assertRaises(ValueError):
            self.service.create_channel(
                name="missing webhook target",
                type="webhook",
                enabled=True,
                severity_min="warning",
                event_types=["admin_logs.storage"],
                config={},
            )
        with self.assertRaises(ValueError):
            self.service.create_channel(
                name="missing system channel",
                type="system_channel",
                enabled=True,
                severity_min="warning",
                event_types=["admin_logs.storage"],
                config={},
            )

    def test_default_rehearsal_path_makes_no_external_network_call(self) -> None:
        class ExplodingSystemNotifier:
            def __init__(self, *_args, **_kwargs):
                raise AssertionError("system notification sender should not be constructed")

        with (
            patch("urllib.request.urlopen", side_effect=AssertionError("network call attempted")) as mock_urlopen,
            patch("src.services.notification_service.SystemNotificationService", ExplodingSystemNotifier),
        ):
            event = self.service.emit_event(
                event_type="notifications.staging_rehearsal",
                severity="warning",
                title="Notification rehearsal",
                message="Default staging rehearsal should stay local",
                payload={"dry_run": True},
                fingerprint="notifications:default-no-network",
            )

        self.assertEqual(event["delivery_status"], "no_channels")
        self.assertEqual(self.delivery.webhook_calls, [])
        mock_urlopen.assert_not_called()

    def test_available_system_channels_are_not_default_user_delivery_without_opt_in(self) -> None:
        send_calls: list[str] = []

        class FakeSystemNotifier:
            def get_available_channels(self):
                return [SimpleNamespace(value="email"), SimpleNamespace(value="discord")]

            def send(self, content: str, **_kwargs) -> bool:
                send_calls.append(content)
                raise AssertionError("system notification sender should not be called")

        with (
            patch("urllib.request.urlopen", side_effect=AssertionError("network call attempted")) as mock_urlopen,
            patch("src.services.notification_service.SystemNotificationService", FakeSystemNotifier),
        ):
            self.assertEqual(self.service.list_system_channels(), ["email", "discord"])
            event = self.service.emit_event(
                event_type="user.notification.contract",
                severity="warning",
                title="User notification contract",
                message="System channels are available but not user opt-in targets",
                payload={"owner_user_id": "user-1", "dry_run": True},
                fingerprint="user-notification:no-default-system-channel",
            )

        self.assertEqual(event["delivery_status"], "no_channels")
        self.assertEqual(send_calls, [])
        self.assertEqual(self.delivery.webhook_calls, [])
        mock_urlopen.assert_not_called()

    def test_missing_channel_config_fails_closed_with_sanitized_reason_code(self) -> None:
        now = datetime.utcnow()
        with self.db.session_scope() as session:
            row = NotificationChannelRow(
                name="broken webhook",
                type="webhook",
                enabled=True,
                severity_min="warning",
                event_types_json="[]",
                config_json="{}",
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            channel_id = row.id

        result = self.service.test_channel(channel_id, dry_run=True)
        combined = f"{result} {self.service.list_channels()}"

        self.assertFalse(result["success"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["error_code"], "webhook_delivery_failed")
        self.assertEqual(result["error"], "Webhook delivery failed")
        self.assertEqual(result["target_summary"], "webhook:unconfigured")
        self.assertNotIn("webhook_url must be", combined)
        self.assertNotIn("Traceback", combined)

    def test_quota_budget_alert_dry_run_intent_has_no_default_outbound_delivery(self) -> None:
        self.db.upsert_quota_policy(
            policy_key="user-budget-alerts",
            scope_type="user",
            daily_budget_units=120,
            metadata={"daily_soft_limit_units": 100},
        )
        quota_service = QuotaPolicyService(db=self.db)
        preflight = quota_service.classify_pilot_readiness_preflight(
            owner_user_id="pilot-user",
            route_family="analysis",
            estimated_units=121,
            pilot_enforcement_enabled=True,
            pilot_owner_user_ids=("pilot-user",),
            pilot_route_families=("analysis",),
        )
        intent = quota_service.build_budget_alert_notification_intent(preflight)

        event = self.service.emit_event(
            event_type=intent["eventType"],
            severity=intent["severity"],
            title="Quota budget alert dry-run",
            message="Quota pilot alert rehearsal",
            payload=intent,
            fingerprint="quota-budget-alert:dry-run",
        )

        self.assertEqual(intent["state"], "dry_run_intent")
        self.assertTrue(intent["dryRun"])
        self.assertFalse(intent["outboundAttempted"])
        self.assertFalse(intent["liveOutbound"])
        self.assertFalse(intent["safety"]["realOutboundNotification"])
        self.assertEqual(intent["operatorReview"]["deliveryStatusLabel"], "dry_run_disabled")
        self.assertEqual(event["delivery_status"], "no_channels")
        self.assertEqual(self.delivery.webhook_calls, [])

    def test_log_info_debug_events_are_not_exposed_to_admin_notifications(self) -> None:
        self.service.create_channel(
            name="Ops inbox",
            type="in_app",
            enabled=True,
            severity_min="info",
            event_types=["admin_logs.event"],
            config={},
        )

        info_event = self.service.emit_log_event(
            log_level="INFO",
            category="notification",
            event_name="NotificationRouteDebug",
            message="configured webhook internals",
            session_id="debug-session",
        )
        debug_event = self.service.emit_log_event(
            log_level="DEBUG",
            category="notification",
            event_name="NotificationRouteDebug",
            message="configured webhook internals",
            session_id="debug-session",
        )

        self.assertIsNone(info_event)
        self.assertIsNone(debug_event)
        self.assertEqual(self.service.list_events()["items"], [])

    def test_alert_payload_redacts_sensitive_credentials_before_storage_and_delivery(self) -> None:
        self.service.create_channel(
            name="ops webhook",
            type="webhook",
            enabled=True,
            severity_min="warning",
            event_types=["admin_logs.storage"],
            config={"webhook_url": "https://hooks.example.test/alert", "token": "route-token"},
        )

        event = self.service.emit_event(
            event_type="admin_logs.storage",
            severity="critical",
            title="Storage critical",
            message="Storage threshold exceeded",
            payload={
                "token": "raw-token",
                "password": "raw-password",
                "api_key": "raw-api-key",
                "session_cookie": "raw-cookie",
                "sessionToken": "raw-session-token",
                "cookie_header": "raw-cookie-header",
                "broker_credentials": {"account": "acct-1", "password": "broker-password"},
                "provider_credentials": {"apiKey": "provider-api-key", "provider_password": "provider-password"},
                "webhook_url": "https://hooks.example.test/services/raw/path",
                "trade_order": {"symbol": "AAPL", "side": "BUY"},
                "portfolio_mutation": {"action": "rebalance"},
            },
            fingerprint="storage:sensitive-payload",
        )

        self.assertEqual(event["delivery_status"], "delivered")
        delivered_payload = self.delivery.webhook_calls[0]["payload"]
        stored_payload = self.service.list_events()["items"][0]["payload"]
        for payload in (event["payload"], delivered_payload["payload"], stored_payload):
            payload_text = str(payload)
            self.assertNotIn("raw-token", payload_text)
            self.assertNotIn("raw-password", payload_text)
            self.assertNotIn("raw-api-key", payload_text)
            self.assertNotIn("raw-cookie", payload_text)
            self.assertNotIn("raw-session-token", payload_text)
            self.assertNotIn("raw-cookie-header", payload_text)
            self.assertNotIn("broker-password", payload_text)
            self.assertNotIn("provider-api-key", payload_text)
            self.assertNotIn("provider-password", payload_text)
            self.assertNotIn("/services/raw/path", payload_text)
            self.assertEqual(payload["token"], "********")
            self.assertEqual(payload["password"], "********")
            self.assertEqual(payload["api_key"], "********")
            self.assertEqual(payload["session_cookie"], "********")
            self.assertEqual(payload["sessionToken"], "********")
            self.assertEqual(payload["cookie_header"], "********")
            self.assertEqual(payload["webhook_url"], "https://hooks.example.test/***")
            self.assertEqual(payload["trade_order"]["symbol"], "AAPL")
            self.assertEqual(payload["portfolio_mutation"]["action"], "rebalance")

    def test_api_channel_and_event_surfaces_do_not_expose_raw_notification_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = self._replace_database(
                f"sqlite:///{tmpdir}/notification_channels.sqlite?check_same_thread=False"
            )
            service = NotificationService(db=db, delivery_client=FakeDeliveryClient())
            service.create_channel(
                name="ops webhook",
                type="webhook",
                enabled=True,
                severity_min="warning",
                event_types=["admin_logs.storage"],
                config={
                    "webhook_url": "https://user:pass@hooks.example.test/services/raw/path",
                    "token": "route-token",
                    "provider_credentials": {"password": "provider-password"},
                },
            )
            service.emit_event(
                event_type="admin_logs.storage",
                severity="critical",
                title="Storage critical",
                message="Storage threshold exceeded",
                payload={
                    "token": "raw-token",
                    "authorization": "Bearer raw-bearer",
                    "webhook_url": "https://hooks.example.test/services/event/path",
                    "session_cookie": "raw-cookie",
                    "provider_credentials": {"password": "payload-provider-password"},
                },
                fingerprint="storage:api-redaction",
            )
            class FakeSystemNotifier:
                def get_available_channels(self):
                    return []

            with (
                patch("api.v1.endpoints.admin_notifications.NotificationService", return_value=service),
                patch("src.services.notification_service.SystemNotificationService", FakeSystemNotifier),
            ):
                channels = admin_notifications.list_notification_channels(_=_admin_user())
                events = admin_notifications.list_notifications(
                    event_type=None,
                    severity=None,
                    include_acknowledged=True,
                    limit=100,
                    offset=0,
                    _=_admin_user(),
                )

        combined = f"{channels.model_dump_json()} {events.model_dump_json()}"
        for leaked in (
            "route-token",
            "user:pass",
            "/services/raw/path",
            "provider-password",
            "raw-token",
            "raw-bearer",
            "/services/event/path",
            "raw-cookie",
            "payload-provider-password",
        ):
            self.assertNotIn(leaked, combined)

    def test_existing_system_channel_sends_through_configured_notifier(self) -> None:
        sent_messages: list[str] = []
        allowlists: list[list[str]] = []

        class FakeSystemNotifier:
            def __init__(self, *, channel_allowlist=None, **_kwargs):
                self.channel_allowlist = list(channel_allowlist or [])
                allowlists.append(list(self.channel_allowlist))

            def send(self, content: str, **_kwargs) -> bool:
                sent_messages.append(content)
                return True

        self.service.create_channel(
            name="System Discord",
            type="system_channel",
            enabled=True,
            severity_min="warning",
            event_types=["admin_logs.event"],
            config={"channel": "discord"},
        )

        with patch("src.services.notification_service.SystemNotificationService", FakeSystemNotifier):
            event = self.service.emit_log_event(
                log_level="ERROR",
                category="analysis",
                event_name="AnalysisFailed",
                message="analysis failed",
                session_id="analysis-error",
            )

        self.assertIsNotNone(event)
        self.assertEqual(event["delivery_status"], "delivered")
        self.assertEqual(len(sent_messages), 1)
        self.assertIn("AnalysisFailed", sent_messages[0])
        self.assertIn("analysis failed", sent_messages[0])
        self.assertEqual(allowlists, [["discord"]])

    def test_delete_system_channel_rule_only_unbinds_log_notification_association(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = self._replace_database(
                f"sqlite:///{tmpdir}/notification_channels.sqlite?check_same_thread=False"
            )
            service = NotificationService(db=db, delivery_client=self.delivery)
            channel = service.create_channel(
                name="System Discord",
                type="system_channel",
                enabled=True,
                severity_min="warning",
                event_types=["admin_logs.event"],
                config={"channel": "discord"},
            )

            class FakeSystemNotifier:
                def get_available_channels(self):
                    return [SimpleNamespace(value="discord")]

            with patch("api.v1.endpoints.admin_notifications.NotificationService", return_value=service):
                response = admin_notifications.delete_notification_channel(channel["id"], _=_admin_user())

            self.assertTrue(response["success"])
            self.assertEqual(response["deleted_scope"], "log_notification_association")
            self.assertEqual(service.list_channels(), [])
            with patch("src.services.notification_service.SystemNotificationService", FakeSystemNotifier):
                self.assertEqual(service.list_system_channels(), ["discord"])

    def test_execution_log_warning_triggers_matching_system_channel_once(self) -> None:
        sent_messages: list[str] = []
        allowlists: list[list[str]] = []

        class FakeSystemNotifier:
            def __init__(self, *, channel_allowlist=None, **_kwargs):
                self.channel_allowlist = list(channel_allowlist or [])
                allowlists.append(list(self.channel_allowlist))

            def send(self, content: str, **_kwargs) -> bool:
                sent_messages.append(content)
                return True

        self.service.create_channel(
            name="System Email",
            type="system_channel",
            enabled=True,
            severity_min="warning",
            event_types=["admin_logs.event"],
            config={"channel": "email"},
        )

        self.db.create_execution_log_session(
            session_id="warning-log",
            task_id="DataSourceTimeout",
            overall_status="partial",
            truth_level="actual",
            started_at=datetime.now(),
        )
        with (
            patch("src.storage.AdminNotificationService", return_value=self.service),
            patch("src.services.notification_service.SystemNotificationService", FakeSystemNotifier),
        ):
            self.db.append_execution_log_event(
                session_id="warning-log",
                phase="data_source",
                step="ExternalSourceTimeout",
                status="timed_out",
                truth_level="actual",
                message="provider timed out",
                detail={"log": {"level": "WARNING", "category": "data_source"}},
            )
            self.db.append_execution_log_event(
                session_id="warning-log",
                phase="data_source",
                step="ExternalSourceTimeout",
                status="timed_out",
                truth_level="actual",
                message="provider timed out",
                detail={"log": {"level": "WARNING", "category": "data_source"}},
            )

        events = self.service.list_events(event_type="admin_logs.event")["items"]
        self.assertEqual(len(events), 1)
        self.assertEqual(len(sent_messages), 1)
        self.assertEqual(allowlists, [["email"]])
        self.assertEqual(events[0]["severity"], "warning")

    def test_test_channel_uses_mock_delivery(self) -> None:
        channel = self.service.create_channel(
            name="ops webhook",
            type="webhook",
            enabled=True,
            severity_min="warning",
            event_types=[],
            config={"webhook_url": "https://hooks.example.test/test"},
        )

        result = self.service.test_channel(channel["id"])

        self.assertTrue(result["success"])
        self.assertEqual(len(self.delivery.webhook_calls), 1)
        self.assertEqual(self.delivery.webhook_calls[0]["url"], "https://hooks.example.test/test")

    def test_channel_listing_includes_additive_route_status_metadata(self) -> None:
        self.service.create_channel(
            name="ops webhook",
            type="webhook",
            enabled=True,
            severity_min="warning",
            event_types=["admin_logs.event"],
            config={"webhook_url": "https://hooks.example.test/test", "token": "secret-token"},
        )

        payload = self.service.list_channels()[0]

        self.assertEqual(payload["route_scope"], "log_notification_association")
        self.assertEqual(payload["coverage_summary"], "admin_logs.event; min_severity=warning")
        self.assertEqual(payload["target_summary"], "webhook:configured")
        self.assertEqual(payload["last_status"], "unknown")
        self.assertNotIn("secret-token", str(payload))
        self.assertNotIn("https://hooks.example.test/test", str(payload))

    def test_dry_run_validates_channel_without_sending(self) -> None:
        channel = self.service.create_channel(
            name="ops webhook",
            type="webhook",
            enabled=True,
            severity_min="warning",
            event_types=[],
            config={"webhook_url": "https://hooks.example.test/test"},
        )

        result = self.service.test_channel(channel["id"], dry_run=True)

        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["target_summary"], "webhook:configured")
        self.assertEqual(self.delivery.webhook_calls, [])
        listed = self.service.list_channels()[0]
        self.assertIsNotNone(listed["last_tested_at"])
        self.assertIsNone(listed["last_sent_at"])

    def test_dry_run_channel_intent_redacts_delivery_credentials(self) -> None:
        channel = self.service.create_channel(
            name="ops webhook",
            type="webhook",
            enabled=True,
            severity_min="warning",
            event_types=[],
            config={
                "webhook_url": "https://user:pass@hooks.example.test/services/raw/path",
                "token": "route-token",
                "api_key": "provider-api-key",
                "session_cookie": "raw-cookie",
                "provider_credentials": {"password": "provider-password"},
            },
        )

        result = self.service.test_channel(channel["id"], dry_run=True)
        combined = f"{result} {self.service.list_channels()}"

        self.assertTrue(result["success"])
        self.assertEqual(result["target_summary"], "webhook:configured")
        self.assertEqual(self.delivery.webhook_calls, [])
        self.assertNotIn("user:pass", combined)
        self.assertNotIn("/services/raw/path", combined)
        self.assertNotIn("route-token", combined)
        self.assertNotIn("provider-api-key", combined)
        self.assertNotIn("raw-cookie", combined)
        self.assertNotIn("provider-password", combined)

    def test_delivery_failure_is_recorded_not_raised(self) -> None:
        failing = NotificationService(db=self.db, delivery_client=FakeDeliveryClient(fail=True))
        failing.create_channel(
            name="failing webhook",
            type="webhook",
            enabled=True,
            severity_min="warning",
            event_types=[],
            config={"webhook_url": "https://hooks.example.test/fail"},
        )

        event = failing.emit_event(
            event_type="admin_logs.storage",
            severity="critical",
            title="Storage critical",
            message="Admin Logs storage is critical",
            fingerprint="storage:critical",
        )
        channels = failing.list_channels()

        self.assertEqual(event["delivery_status"], "failed")
        self.assertEqual(channels[0]["last_error"], "Webhook delivery failed")
        self.assertEqual(channels[0]["last_error_summary"], "Webhook delivery failed")
        self.assertEqual(channels[0]["last_error_code"], "webhook_delivery_failed")

    def test_delivery_failure_status_is_sanitized_for_admin_surfaces(self) -> None:
        failing = NotificationService(
            db=self.db,
            delivery_client=FakeDeliveryClient(
                fail=True,
                failure_message=(
                    "Traceback (most recent call last): provider raw response failed "
                    "token=raw-token password=raw-password api_key=raw-api-key "
                    "session=raw-session cookie=raw-cookie "
                    "https://hooks.example.test/services/raw/path"
                ),
            ),
        )
        channel = failing.create_channel(
            name="failing webhook",
            type="webhook",
            enabled=True,
            severity_min="warning",
            event_types=[],
            config={"webhook_url": "https://hooks.example.test/fail", "token": "route-token"},
        )

        with patch("api.v1.endpoints.admin_notifications.NotificationService", return_value=failing):
            payload = admin_notifications.test_notification_channel(
                channel_id=channel["id"],
                request=SimpleNamespace(headers={"accept-language": "en-US"}),
                _=_admin_user(),
            ).model_dump()

        channels = failing.list_channels()
        combined = f"{payload} {channels}"
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error_code"], "webhook_delivery_failed")
        self.assertIn("Webhook delivery failed", payload["error"])
        self.assertNotIn("Traceback", combined)
        self.assertNotIn("raw-token", combined)
        self.assertNotIn("raw-password", combined)
        self.assertNotIn("raw-api-key", combined)
        self.assertNotIn("raw-session", combined)
        self.assertNotIn("raw-cookie", combined)
        self.assertNotIn("provider raw response", combined)
        self.assertNotIn("/services/raw/path", combined)

    def test_notification_routing_does_not_mutate_broker_order_or_portfolio_state(self) -> None:
        self.service.create_channel(
            name="Ops inbox",
            type="in_app",
            enabled=True,
            severity_min="info",
            event_types=["notifications.staging_rehearsal"],
            config={},
        )

        def _portfolio_counts() -> dict[str, int]:
            with self.db.get_session() as session:
                return {
                    "accounts": session.execute(select(func.count(PortfolioAccount.id))).scalar_one(),
                    "trades": session.execute(select(func.count(PortfolioTrade.id))).scalar_one(),
                    "cash": session.execute(select(func.count(PortfolioCashLedger.id))).scalar_one(),
                }

        before = _portfolio_counts()
        event = self.service.emit_event(
            event_type="notifications.staging_rehearsal",
            severity="warning",
            title="Notification delivery rehearsal",
            message="Payload contains order-shaped metadata only",
            payload={
                "broker_order": {"symbol": "AAPL", "side": "BUY", "quantity": 10},
                "portfolio_mutation": {"action": "rebalance", "account_id": 99},
                "dry_run": True,
            },
            fingerprint="notifications:no-broker-portfolio-mutation",
        )
        after = _portfolio_counts()

        self.assertEqual(event["delivery_status"], "delivered")
        self.assertEqual(before, after)
        self.assertEqual(self.delivery.webhook_calls, [])

    def test_ssl_delivery_failure_is_classified_and_localized_by_request_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = self._replace_database(
                f"sqlite:///{tmpdir}/notification_channels.sqlite?check_same_thread=False"
            )
            failing = NotificationService(
                db=db,
                delivery_client=FakeDeliveryClient(
                    fail=True,
                    failure_message="SSL certificate verification failed: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self signed certificate",
                ),
            )
            channel = failing.create_channel(
                name="ssl webhook",
                type="webhook",
                enabled=True,
                severity_min="warning",
                event_types=[],
                config={"webhook_url": "https://hooks.example.test/ssl"},
            )

            with patch("api.v1.endpoints.admin_notifications.NotificationService", return_value=failing):
                zh_payload = admin_notifications.test_notification_channel(
                    channel_id=channel["id"],
                    request=SimpleNamespace(headers={"accept-language": "zh-CN"}),
                    _=_admin_user(),
                ).model_dump()
                en_payload = admin_notifications.test_notification_channel(
                    channel_id=channel["id"],
                    request=SimpleNamespace(headers={"accept-language": "en-US"}),
                    _=_admin_user(),
                ).model_dump()

            self.assertFalse(zh_payload["success"])
            self.assertFalse(en_payload["success"])
            self.assertEqual(zh_payload["error_code"], "ssl_certificate_verify_failed")
            self.assertEqual(en_payload["error_code"], "ssl_certificate_verify_failed")
            self.assertIn("证书", zh_payload["error"])
            self.assertIn("certificate", en_payload["error"].lower())
            self.assertNotIn("diagnostics", zh_payload)
            self.assertNotIn("diagnostics", en_payload)
            self.assertEqual(zh_payload["status"], "failed")
            self.assertEqual(en_payload["status"], "failed")

            channels = failing.list_channels()
            self.assertEqual(channels[0]["last_error_code"], "ssl_certificate_verify_failed")
            self.assertEqual(channels[0]["last_error"], "SSL certificate verification failed")

    def test_test_channel_missing_route_returns_clean_error(self) -> None:
        with patch("api.v1.endpoints.admin_notifications.NotificationService", return_value=self.service), self.assertRaises(HTTPException) as raised:
            admin_notifications.test_notification_channel(
                channel_id=404,
                request=SimpleNamespace(headers={"accept-language": "zh-CN"}),
                dry_run=True,
                _=_admin_user(),
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail["error"], "not_found")

    def test_notification_event_dedupe_window_returns_existing_event(self) -> None:
        first = self.service.emit_event(
            event_type="admin_logs.storage",
            severity="warning",
            title="Storage warning",
            message="Admin Logs storage is above the soft limit",
            fingerprint="storage:warning",
            dedupe_window=timedelta(minutes=30),
        )
        second = self.service.emit_event(
            event_type="admin_logs.storage",
            severity="warning",
            title="Storage warning again",
            message="Repeated page refresh",
            fingerprint="storage:warning",
            dedupe_window=timedelta(minutes=30),
        )

        self.assertEqual(second["id"], first["id"])
        self.assertTrue(second["deduped"])
        self.assertEqual(self.service.list_events()["total"], 1)

    def test_admin_logs_warning_creates_notification_without_duplicates(self) -> None:
        self.db.create_execution_log_session(
            session_id="recent-warning",
            task_id="AnalysisWarning",
            overall_status="completed",
            truth_level="actual",
            started_at=datetime.now(),
        )
        with (
            patch("src.services.admin_logs_service.get_db", return_value=self.db),
            patch(
                "src.services.admin_logs_service.get_config",
                return_value=SimpleNamespace(
                    admin_logs_retention_days=90,
                    admin_logs_min_retention_days=7,
                    admin_logs_storage_soft_limit_mb=1,
                    admin_logs_storage_hard_limit_mb=2,
                    admin_logs_cleanup_batch_size=1000,
                    admin_logs_auto_cleanup_enabled=False,
                    admin_logs_warning_threshold_count=1,
                    admin_logs_critical_threshold_count=100000,
                    admin_logs_warning_threshold_storage_bytes=None,
                ),
            ),
            patch("src.services.admin_logs_service.NotificationService", return_value=self.service),
        ):
            admin_logs.get_log_storage_summary(_=_admin_user())
            admin_logs.get_log_storage_summary(_=_admin_user())

        events = self.service.list_events()["items"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "admin_logs.storage")
        self.assertEqual(events[0]["severity"], "warning")

    def test_acknowledge_notification_records_admin_actor(self) -> None:
        event = self.service.emit_event(
            event_type="data_provider.degraded",
            severity="warning",
            title="Provider degraded",
            message="Provider fallback was used",
            fingerprint="provider:fallback",
        )

        acknowledged = self.service.acknowledge_event(event["id"], acknowledged_by="bootstrap-admin")

        self.assertIsNotNone(acknowledged["acknowledged_at"])
        self.assertEqual(acknowledged["acknowledged_by"], "bootstrap-admin")

    def test_capacity_cleanup_event_is_created_when_cleanup_runs(self) -> None:
        old_at = datetime.now() - timedelta(days=120)
        self.db.create_execution_log_session(
            session_id="old-error",
            task_id="AnalysisFailed",
            overall_status="failed",
            truth_level="actual",
            started_at=old_at,
        )
        self.db.append_execution_log_event(
            session_id="old-error",
            phase="analysis",
            step="AnalysisFailed",
            status="failed",
            truth_level="actual",
            message="old failure",
            event_at=old_at,
        )

        with (
            patch("src.services.admin_logs_service.get_db", return_value=self.db),
            patch(
                "src.services.admin_logs_service.get_config",
                return_value=SimpleNamespace(
                    admin_logs_retention_days=90,
                    admin_logs_min_retention_days=7,
                    admin_logs_storage_soft_limit_mb=1,
                    admin_logs_storage_hard_limit_mb=2,
                    admin_logs_cleanup_batch_size=1000,
                    admin_logs_auto_cleanup_enabled=False,
                    admin_logs_warning_threshold_count=50000,
                    admin_logs_critical_threshold_count=100000,
                    admin_logs_warning_threshold_storage_bytes=None,
                ),
            ),
            patch("src.services.admin_logs_service.AdminLogsRetentionService._storage_bytes", return_value=3 * 1024 * 1024),
            patch("src.services.admin_logs_service.NotificationService", return_value=self.service),
        ):
            admin_logs.cleanup_admin_logs(admin_logs.AdminLogCleanupRequest(mode="capacity", dry_run=False), _=_admin_user())

        events = self.service.list_events(event_type="admin_logs.cleanup")["items"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["severity"], "warning")
        self.assertIn("capacity cleanup", events[0]["title"].lower())


if __name__ == "__main__":
    unittest.main()
