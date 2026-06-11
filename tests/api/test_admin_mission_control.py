# -*- coding: utf-8 -*-
"""Admin Mission Control read-only projection API tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1 import api_v1_router
from src.storage import DatabaseManager


FORBIDDEN_RESPONSE_MARKERS = (
    "raw-owner-user-id",
    "owner_user_id",
    "raw-session-id",
    "session_id",
    "provider-payload-secret",
    "provider_payload",
    "raw_payload",
    "request_body",
    "response_body",
    "raw_response",
    "access-token",
    "authorization",
    "bearer",
    "cookie",
    "api_key",
    "apikey",
    "secret",
    "traceback",
    "stack_trace",
    "raw exception",
    "provider.example",
    "https://",
    "?token=",
)


def _ops_admin() -> CurrentUser:
    return CurrentUser(
        user_id="admin-mission-control",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="raw-session-id",
        admin_capabilities=("ops:logs:read",),
    )


def _admin_without_ops_logs_read() -> CurrentUser:
    return CurrentUser(
        user_id="admin-no-mission-control",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="raw-session-id",
        admin_capabilities=("ops:providers:read", "cost:observability:read"),
    )


def _regular_user() -> CurrentUser:
    return CurrentUser(
        user_id="raw-owner-user-id",
        username="alice",
        display_name="Alice",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="raw-session-id",
    )


class _TaskQueueFixture:
    def get_runtime_status(self):
        return {
            "mode": "process_local",
            "single_process_required": True,
            "launch_status": "limited_single_process",
            "configured_worker_count": 1,
            "topology_ok": True,
            "shutdown": False,
            "accepting_new_tasks": True,
            "warning": "raw-session-id access-token traceback must not leak",
        }


@pytest.fixture()
def app(tmp_path: Path):
    DatabaseManager.reset_instance()
    DatabaseManager(db_url=f"sqlite:///{tmp_path / 'admin-mission-control.sqlite'}")
    app = FastAPI()
    app.include_router(api_v1_router)
    yield app
    app.dependency_overrides.clear()
    DatabaseManager.reset_instance()


def _client(app: FastAPI, user_factory) -> TestClient:
    app.dependency_overrides[get_current_user] = user_factory
    return TestClient(app)


def _json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def _assert_no_sensitive_markers(payload: object) -> None:
    text = _json_text(payload)
    for marker in FORBIDDEN_RESPONSE_MARKERS:
        assert marker.lower() not in text


def test_admin_mission_control_requires_admin_with_ops_logs_read(app: FastAPI) -> None:
    with _client(app, _regular_user) as client:
        regular = client.get("/api/v1/admin/mission-control")
    assert regular.status_code == 403
    assert regular.json()["detail"]["error"] == "admin_required"
    _assert_no_sensitive_markers(regular.json())

    with _client(app, _admin_without_ops_logs_read) as client:
        missing_capability = client.get("/api/v1/admin/mission-control")
    assert missing_capability.status_code == 403
    assert missing_capability.json()["detail"]["error"] == "admin_capability_required"
    assert "ops:logs:read" not in missing_capability.text
    _assert_no_sensitive_markers(missing_capability.json())

    app.state.task_queue = _TaskQueueFixture()
    with _client(app, _ops_admin) as client:
        allowed = client.get("/api/v1/admin/mission-control")
    assert allowed.status_code == 200


def test_admin_mission_control_returns_all_readiness_domains(app: FastAPI) -> None:
    app.state.task_queue = _TaskQueueFixture()

    with _client(app, _ops_admin) as client:
        response = client.get("/api/v1/admin/mission-control")

    assert response.status_code == 200
    payload = response.json()
    assert payload["readOnly"] is True
    assert payload["noExternalCalls"] is True
    assert payload["liveEnforcement"] is False
    assert payload["runtimeBehaviorChanged"] is False
    assert payload["publicLaunchApproved"] is False
    assert payload["releaseApproved"] is False
    assert payload["launchVerdict"] == "NO_GO"
    assert payload["metadata"]["mutationPaths"] == []
    assert payload["metadata"]["externalCallsMade"] is False
    assert payload["summary"]["domainCount"] == 9
    assert payload["summary"]["publicLaunchNoGoCount"] >= 1
    assert payload["summary"]["approvalRequiredCount"] >= 1
    assert payload["summary"]["realOperatorEvidenceMissingCount"] >= 1

    domains = {item["id"]: item for item in payload["domains"]}
    assert set(domains) == {
        "security_rbac_mfa",
        "quota_cost",
        "provider_reliability",
        "storage_restore",
        "ws2_async",
        "notifications",
        "portfolio_backtest",
        "route_classification",
        "private_beta_readiness",
    }
    for item in domains.values():
        assert item["readOnly"] is True
        assert item["noExternalCalls"] is True
        assert item["liveEnforcement"] is False
        assert item["runtimeBehaviorChanged"] is False
        assert "landedFoundation" in item["posture"]
        assert "evidenceToolingExists" in item["posture"]
        assert "realOperatorEvidenceMissing" in item["posture"]
        assert "approvalRequired" in item["posture"]
        assert "publicLaunchNoGo" in item["posture"]

    assert domains["quota_cost"]["opsStatus"]["summary"]["reserveConsumeReleaseCalled"] is False
    assert domains["storage_restore"]["opsStatus"]["summary"]["cleanupMutation"] is False
    assert domains["ws2_async"]["opsStatus"]["summary"]["mode"] == "process_local"
    _assert_no_sensitive_markers(payload)


def test_admin_mission_control_does_not_execute_live_or_mutating_paths(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.state.task_queue = _TaskQueueFixture()
    monkeypatch.setattr(
        "requests.sessions.Session.request",
        lambda *_, **__: pytest.fail("external HTTP calls must not run for mission control"),
    )
    monkeypatch.setattr(
        "src.services.quota_policy_service.QuotaPolicyService.reserve_quota",
        lambda *_, **__: pytest.fail("reserve_quota must not run for mission control"),
    )
    monkeypatch.setattr(
        "src.services.quota_policy_service.QuotaPolicyService.consume_reservation",
        lambda *_, **__: pytest.fail("consume_reservation must not run for mission control"),
    )
    monkeypatch.setattr(
        "src.services.quota_policy_service.QuotaPolicyService.release_reservation",
        lambda *_, **__: pytest.fail("release_reservation must not run for mission control"),
    )
    monkeypatch.setattr(
        "src.services.notification_service.NotificationService.test_channel",
        lambda *_, **__: pytest.fail("notification tests/sends must not run for mission control"),
    )
    monkeypatch.setattr(
        "src.services.admin_governance_audit_service.AdminGovernanceAuditService.record_view",
        lambda *_, **__: pytest.fail("mission control must not record target-user portfolio views"),
    )
    monkeypatch.setattr(
        "src.services.admin_portfolio_service.AdminPortfolioService.get_summary",
        lambda *_, **__: pytest.fail("mission control must not read target-user portfolio details"),
    )

    with _client(app, _ops_admin) as client:
        response = client.get("/api/v1/admin/mission-control")

    assert response.status_code == 200
    payload = response.json()
    assert payload["noExternalCalls"] is True
    assert payload["liveEnforcement"] is False
    assert payload["metadata"]["notificationSendAttempted"] is False
    assert payload["metadata"]["providerCallsAttempted"] is False
    assert payload["metadata"]["portfolioTargetReadsAttempted"] is False


def test_admin_mission_control_degrades_ops_snapshot_without_raw_exception(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_raw_failure(self, *, app_state=None):
        raise RuntimeError("raw exception raw-owner-user-id raw-session-id access-token traceback provider-payload-secret")

    monkeypatch.setattr(
        "src.services.admin_ops_status_service.AdminOpsStatusService.build_status",
        _raise_raw_failure,
    )

    with _client(app, _ops_admin) as client:
        response = client.get("/api/v1/admin/mission-control")

    assert response.status_code == 200
    payload = response.json()
    assert payload["opsSnapshotAvailable"] is False
    assert payload["metadata"]["opsSnapshotReasonCode"] == "source_unavailable"
    assert payload["summary"]["domainCount"] == 9
    _assert_no_sensitive_markers(payload)
