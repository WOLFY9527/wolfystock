# -*- coding: utf-8 -*-
"""Focused RBAC R3b route migration tests for ops-sensitive admin routes."""

from __future__ import annotations

from typing import Iterable

from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.auth as auth
from api.deps import CurrentUser, get_current_user, get_system_config_service
from api.v1 import api_v1_router


FORBIDDEN_DENIAL_MARKERS = (
    "password_hash",
    "raw-session",
    "session-id",
    "cookie",
    "token-value",
    "api-key",
    "secret-value",
    "broker-credential",
    "provider-credential",
    "webhook.example.test",
    ".env",
    "traceback",
    "super-admin",
    "ops:logs:read",
)


def _user(
    *,
    is_admin: bool = True,
    capabilities: Iterable[str] = (),
    legacy_admin: bool = False,
) -> CurrentUser:
    return CurrentUser(
        user_id="admin-r3b",
        username="admin-r3b",
        display_name="Admin R3b",
        role="admin" if is_admin else "user",
        is_admin=is_admin,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="raw-session-id",
        legacy_admin=legacy_admin,
        admin_capabilities=tuple(capabilities),
    )


def _client(user: CurrentUser) -> TestClient:
    app = FastAPI()
    app.include_router(api_v1_router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_system_config_service] = lambda: FakeSystemConfigService()
    return TestClient(app)


def _admin_unlock_headers(monkeypatch, user: CurrentUser) -> dict[str, str]:
    monkeypatch.setattr(auth, "_auth_enabled", True)
    monkeypatch.setattr(auth, "_session_secret", b"r" * 32)
    token = auth.create_admin_unlock_token(
        user_id=user.user_id,
        username=user.username,
        role=user.role,
    )
    assert token
    return {"X-Admin-Unlock-Token": token}


def _assert_sanitized_denial(response) -> None:
    text = response.text.lower()
    for marker in FORBIDDEN_DENIAL_MARKERS:
        assert marker.lower() not in text


class FakeAdminLogsRetentionService:
    def storage_summary(self):
        return {"total_log_count": 0, "total_event_count": 0, "status": "ok"}

    def cleanup(self, **_kwargs):
        return {"mode": "retention", "dry_run": True, "matched_log_count": 0, "deleted_log_count": 0}


class FakeSystemConfigService:
    def get_config(self, *, include_schema: bool = True):
        return {
            "config_version": "v1",
            "mask_token": "******",
            "items": [],
            "updated_at": None,
        }

    def update(self, **_kwargs):
        return {
            "success": True,
            "config_version": "v2",
            "applied_count": 1,
            "skipped_masked_count": 0,
            "reload_triggered": False,
            "updated_keys": ["STOCK_LIST"],
            "warnings": [],
        }

    def validate(self, **_kwargs):
        return {"valid": True, "issues": []}

    def test_llm_channel(self, **_kwargs):
        return {"success": True, "message": "LLM channel test succeeded"}

    def test_custom_data_source(self, **_kwargs):
        return {"success": True, "message": "Data source test succeeded"}

    def test_builtin_data_source(self, **_kwargs):
        return {
            "provider": "yahoo",
            "ok": True,
            "status": "success",
            "checked_at": "2026-05-06T00:00:00Z",
            "duration_ms": 1,
            "checks": [],
            "summary": "ok",
            "suggestion": "none",
        }

    def reset_runtime_caches(self):
        return {"success": True, "action": "reset_runtime_caches", "message": "ok", "cleared": []}

    def factory_reset_system(self, **_kwargs):
        return {
            "success": True,
            "action": "factory_reset_system",
            "message": "ok",
            "cleared": [],
            "preserved": ["bootstrap_admin_access"],
            "counts": {},
        }


class FakeNotificationService:
    def list_channels(self):
        return []

    def list_system_channels(self):
        return []

    def create_channel(self, **kwargs):
        return {
            "id": 1,
            "name": kwargs["name"],
            "type": kwargs["type"],
            "enabled": kwargs["enabled"],
            "severity_min": kwargs["severity_min"],
            "event_types": kwargs["event_types"],
            "config": {},
        }

    def acknowledge_event(self, event_id: int, *, acknowledged_by: str):
        return {
            "id": event_id,
            "event_type": "admin_logs.storage",
            "severity": "warning",
            "title": "Storage warning",
            "message": "",
            "payload": {},
            "fingerprint": "storage",
            "created_at": None,
            "acknowledged_at": "2026-05-06T00:00:00Z",
            "acknowledged_by": acknowledged_by,
            "delivery_status": "pending",
            "deduped": False,
        }


def test_admin_logs_reads_require_logs_read_not_write_only(monkeypatch) -> None:
    monkeypatch.setattr("api.v1.endpoints.admin_logs.AdminLogsRetentionService", FakeAdminLogsRetentionService)

    read_client = _client(_user(capabilities=("ops:logs:read",)))
    response = read_client.get("/api/v1/admin/logs/storage/summary")
    assert response.status_code == 200

    write_only_client = _client(_user(capabilities=("ops:logs:write",)))
    denied = write_only_client.get("/api/v1/admin/logs/storage/summary")
    assert denied.status_code == 403
    assert denied.json()["detail"]["error"] == "admin_capability_required"
    _assert_sanitized_denial(denied)


def test_admin_logs_cleanup_requires_logs_write(monkeypatch) -> None:
    monkeypatch.setattr("api.v1.endpoints.admin_logs.AdminLogsRetentionService", FakeAdminLogsRetentionService)

    read_client = _client(_user(capabilities=("ops:logs:read",)))
    denied = read_client.post("/api/v1/admin/logs/cleanup", json={"use_retention": True, "dry_run": True})
    assert denied.status_code == 403
    assert denied.json()["detail"]["error"] == "admin_capability_required"
    _assert_sanitized_denial(denied)

    write_client = _client(_user(capabilities=("ops:logs:write",)))
    allowed = write_client.post("/api/v1/admin/logs/cleanup", json={"use_retention": True, "dry_run": True})
    assert allowed.status_code == 200


def test_system_config_read_write_and_provider_probe_capabilities(monkeypatch) -> None:
    read_client = _client(_user(capabilities=("ops:system_config:read",)))
    assert read_client.get("/api/v1/system/config").status_code == 200
    assert read_client.post("/api/v1/system/config/validate", json={"items": [{"key": "STOCK_LIST", "value": "AAPL"}]}).status_code == 200

    denied_write = read_client.put(
        "/api/v1/system/config",
        json={"config_version": "v1", "items": [{"key": "STOCK_LIST", "value": "AAPL"}]},
    )
    assert denied_write.status_code == 403
    assert denied_write.json()["detail"]["error"] == "admin_capability_required"
    _assert_sanitized_denial(denied_write)

    write_user = _user(capabilities=("ops:system_config:write",))
    write_client = _client(write_user)
    missing_unlock_write = write_client.put(
        "/api/v1/system/config",
        json={"config_version": "v1", "items": [{"key": "STOCK_LIST", "value": "AAPL"}]},
    )
    assert missing_unlock_write.status_code == 403
    assert missing_unlock_write.json()["detail"]["error"] == "admin_unlock_required"
    _assert_sanitized_denial(missing_unlock_write)

    invalid_unlock_write = write_client.put(
        "/api/v1/system/config",
        json={"config_version": "v1", "items": [{"key": "STOCK_LIST", "value": "AAPL"}]},
        headers={"X-Admin-Unlock-Token": "token-value"},
    )
    assert invalid_unlock_write.status_code == 403
    assert invalid_unlock_write.json()["detail"]["error"] == "admin_unlock_required"
    _assert_sanitized_denial(invalid_unlock_write)

    unlock_headers = _admin_unlock_headers(monkeypatch, write_user)
    allowed_write = write_client.put(
        "/api/v1/system/config",
        json={"config_version": "v1", "items": [{"key": "STOCK_LIST", "value": "AAPL"}]},
        headers=unlock_headers,
    )
    assert allowed_write.status_code == 200
    assert write_client.post("/api/v1/system/actions/runtime-cache/reset", headers=unlock_headers).status_code == 200
    assert write_client.post(
        "/api/v1/system/actions/factory-reset",
        json={"confirmation_phrase": "FACTORY RESET"},
        headers=unlock_headers,
    ).status_code == 200

    denied_probe = write_client.post("/api/v1/system/config/llm/test-channel", json={"name": "primary"})
    assert denied_probe.status_code == 403
    assert denied_probe.json()["detail"]["error"] == "admin_capability_required"
    _assert_sanitized_denial(denied_probe)

    provider_user = _user(capabilities=("ops:providers:write",))
    provider_client = _client(provider_user)
    provider_unlock_headers = _admin_unlock_headers(monkeypatch, provider_user)
    missing_unlock_probe = provider_client.post("/api/v1/system/config/llm/test-channel", json={"name": "primary"})
    assert missing_unlock_probe.status_code == 403
    assert missing_unlock_probe.json()["detail"]["error"] == "admin_unlock_required"
    _assert_sanitized_denial(missing_unlock_probe)

    assert provider_client.post(
        "/api/v1/system/config/llm/test-channel",
        json={"name": "primary"},
        headers=provider_unlock_headers,
    ).status_code == 200
    assert provider_client.post(
        "/api/v1/system/config/data-source/test",
        json={"name": "custom", "base_url": "https://data.example.test"},
        headers=provider_unlock_headers,
    ).status_code == 200
    assert provider_client.post(
        "/api/v1/system/config/data-source/test-builtin",
        json={"provider": "yahoo"},
        headers=provider_unlock_headers,
    ).status_code == 200


def test_migrated_admin_write_surfaces_fail_closed_without_capability_payload(monkeypatch) -> None:
    monkeypatch.setattr("api.v1.endpoints.admin_logs.AdminLogsRetentionService", FakeAdminLogsRetentionService)
    client = _client(_user())

    denied_config = client.put(
        "/api/v1/system/config",
        json={"config_version": "v1", "items": [{"key": "STOCK_LIST", "value": "AAPL"}]},
    )
    assert denied_config.status_code == 403
    assert denied_config.json()["detail"]["error"] == "admin_capability_required"
    _assert_sanitized_denial(denied_config)

    denied_probe = client.post("/api/v1/system/config/llm/test-channel", json={"name": "primary"})
    assert denied_probe.status_code == 403
    assert denied_probe.json()["detail"]["error"] == "admin_capability_required"
    _assert_sanitized_denial(denied_probe)

    denied_logs_cleanup = client.post("/api/v1/admin/logs/cleanup", json={"use_retention": True, "dry_run": True})
    assert denied_logs_cleanup.status_code == 403
    assert denied_logs_cleanup.json()["detail"]["error"] == "admin_capability_required"
    _assert_sanitized_denial(denied_logs_cleanup)


def test_provider_circuit_diagnostics_require_provider_read_capability() -> None:
    read_client = _client(_user(capabilities=("ops:providers:read",)))
    assert read_client.get("/api/v1/admin/providers/circuits").status_code == 200
    assert read_client.get("/api/v1/admin/providers/circuits/events").status_code == 200
    assert read_client.get("/api/v1/admin/providers/quota-windows").status_code == 200
    assert read_client.get("/api/v1/admin/providers/probe-events").status_code == 200
    assert read_client.get("/api/v1/admin/providers/sla-readiness").status_code == 200

    write_only_client = _client(_user(capabilities=("ops:providers:write",)))
    denied = write_only_client.get("/api/v1/admin/providers/circuits")
    assert denied.status_code == 403
    assert denied.json()["detail"]["error"] == "admin_capability_required"
    _assert_sanitized_denial(denied)


def test_notification_reads_and_state_changes_use_notification_capabilities(monkeypatch) -> None:
    monkeypatch.setattr("api.v1.endpoints.admin_notifications.NotificationService", FakeNotificationService)

    read_client = _client(_user(capabilities=("ops:notifications:read",)))
    assert read_client.get("/api/v1/admin/notification-channels").status_code == 200
    denied_write = read_client.post(
        "/api/v1/admin/notification-channels",
        json={
            "name": "Ops inbox",
            "type": "in_app",
            "enabled": True,
            "severity_min": "warning",
            "event_types": [],
            "config": {},
        },
    )
    assert denied_write.status_code == 403
    assert denied_write.json()["detail"]["error"] == "admin_capability_required"
    _assert_sanitized_denial(denied_write)

    security_like_client = _client(_user(capabilities=("users:security:read", "ops:notifications:read")))
    denied_ack = security_like_client.post("/api/v1/admin/notifications/1/ack")
    assert denied_ack.status_code == 403
    assert denied_ack.json()["detail"]["error"] == "admin_capability_required"
    _assert_sanitized_denial(denied_ack)

    write_client = _client(_user(capabilities=("ops:notifications:write",)))
    allowed = write_client.post(
        "/api/v1/admin/notification-channels",
        json={
            "name": "Ops inbox",
            "type": "in_app",
            "enabled": True,
            "severity_min": "warning",
            "event_types": [],
            "config": {},
        },
    )
    assert allowed.status_code == 200
    assert write_client.post("/api/v1/admin/notifications/1/ack").status_code == 200


def test_legacy_admin_still_passes_r3b_compatibility(monkeypatch) -> None:
    monkeypatch.setattr("api.v1.endpoints.admin_logs.AdminLogsRetentionService", FakeAdminLogsRetentionService)
    client = _client(_user(legacy_admin=True))

    response = client.get("/api/v1/admin/logs/storage/summary")

    assert response.status_code == 200


def test_r3b_routes_fail_closed_when_coarse_fallback_disable_preflight_is_enabled(monkeypatch) -> None:
    monkeypatch.setattr("api.v1.endpoints.admin_logs.AdminLogsRetentionService", FakeAdminLogsRetentionService)
    monkeypatch.setenv("WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED", "false")
    client = _client(_user(legacy_admin=True))

    response = client.get("/api/v1/admin/logs/storage/summary")

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "admin_capability_required"
    _assert_sanitized_denial(response)


def test_non_admin_is_denied_before_capability_detail_leaks(monkeypatch) -> None:
    monkeypatch.setattr("api.v1.endpoints.admin_logs.AdminLogsRetentionService", FakeAdminLogsRetentionService)
    client = _client(_user(is_admin=False, capabilities=("ops:logs:read",)))

    response = client.get("/api/v1/admin/logs/storage/summary")

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "admin_required"
    _assert_sanitized_denial(response)
