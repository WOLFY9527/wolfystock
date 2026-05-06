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

from api.deps import CurrentUser, get_current_user
from api.v1 import api_v1_router
from api.v1.endpoints import admin_logs, admin_notifications
from src.services.notification_service import NotificationDeliveryClient, NotificationService
from src.storage import DatabaseManager


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
        self.assertEqual(payload["type"], "in_app")
        self.assertEqual(len(fake_service.create_calls), 1)
        self.assertEqual(fake_service.create_calls[0]["name"], "Ops inbox")

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
                "webhook_url": "https://hooks.example.test/services/SECRET/PATH",
                "token": "super-secret-token",
            },
        )

        payload = self.service.list_channels()

        self.assertEqual(payload[0]["id"], channel["id"])
        self.assertNotIn("super-secret-token", str(payload))
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

    def test_existing_system_channel_sends_through_configured_notifier(self) -> None:
        sent_messages: list[str] = []

        class FakeSystemNotifier:
            def __init__(self, *, channel_allowlist=None, **_kwargs):
                self.channel_allowlist = list(channel_allowlist or [])

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

    def test_delete_system_channel_rule_only_unbinds_log_notification_association(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = DatabaseManager(db_url=f"sqlite:///{tmpdir}/notification_channels.sqlite?check_same_thread=False")
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

        class FakeSystemNotifier:
            def __init__(self, *, channel_allowlist=None, **_kwargs):
                self.channel_allowlist = list(channel_allowlist or [])

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
        self.assertIn("mock webhook failure", channels[0]["last_error"])
        self.assertEqual(channels[0]["last_error_code"], "webhook_delivery_failed")

    def test_ssl_delivery_failure_is_classified_and_localized_by_request_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = DatabaseManager(db_url=f"sqlite:///{tmpdir}/notification_channels.sqlite?check_same_thread=False")
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
            self.assertIn("troubleshooting", zh_payload["diagnostics"])
            self.assertIn("troubleshooting", en_payload["diagnostics"])

            channels = failing.list_channels()
            self.assertEqual(channels[0]["last_error_code"], "ssl_certificate_verify_failed")
            self.assertIn("CERTIFICATE_VERIFY_FAILED", channels[0]["last_error"])

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
