# -*- coding: utf-8 -*-
"""Admin ops status snapshot API tests."""

from __future__ import annotations

import json
import src.auth as auth
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
    "credential-secret",
    "traceback",
    "stack_trace",
    "raw exception",
    "provider.example",
    "https://",
    "?token=",
    "postgres://",
    "db.example.test",
    "/users/example/",
    "runtimeerror",
    "operationalerror",
    "providercircuitstate",
    "providerprobecount",
    "configuredworkercount",
    "scripts/",
    "docs/",
    "tests/",
    "api/v1/endpoints/",
    ".py",
    ".md",
)


def _ops_admin() -> CurrentUser:
    return CurrentUser(
        user_id="admin-ops-status",
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
        user_id="admin-no-ops-status",
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
    DatabaseManager(db_url=f"sqlite:///{tmp_path / 'admin-ops-status.sqlite'}")
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


def _assert_bounded_section(payload: dict, key: str, *, expected_service: str) -> None:
    section = payload[key]
    assert section["service"] == expected_service
    assert isinstance(section["configured"], bool)
    assert isinstance(section["message"], str)
    assert section["summary"] == {}
    assert section["dataSources"] == []


def test_admin_ops_status_requires_admin_with_ops_logs_read(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_AUTH_ENABLED", "true")
    auth._auth_enabled = None
    with TestClient(app) as client:
        anonymous = client.get("/api/v1/admin/ops/status")
    assert anonymous.status_code == 401
    assert anonymous.json()["detail"]["error"] == "unauthorized"
    _assert_no_sensitive_markers(anonymous.json())
    auth._auth_enabled = None

    with _client(app, _regular_user) as client:
        regular = client.get("/api/v1/admin/ops/status")
    assert regular.status_code == 403
    assert regular.json()["detail"]["error"] == "admin_required"
    _assert_no_sensitive_markers(regular.json())

    with _client(app, _admin_without_ops_logs_read) as client:
        missing_capability = client.get("/api/v1/admin/ops/status")
    assert missing_capability.status_code == 403
    assert missing_capability.json()["detail"]["error"] == "admin_capability_required"
    assert "ops:logs:read" not in missing_capability.text
    _assert_no_sensitive_markers(missing_capability.json())

    app.state.task_queue = _TaskQueueFixture()
    with _client(app, _ops_admin) as client:
        allowed = client.get("/api/v1/admin/ops/status")
    assert allowed.status_code == 200


def test_admin_ops_status_returns_read_only_advisory_markers(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    app.state.task_queue = _TaskQueueFixture()

    monkeypatch.setattr(
        "src.services.quota_policy_service.QuotaPolicyService.reserve_quota",
        lambda *_, **__: pytest.fail("reserve_quota must not run for ops status"),
    )
    monkeypatch.setattr(
        "src.services.quota_policy_service.QuotaPolicyService.consume_reservation",
        lambda *_, **__: pytest.fail("consume_reservation must not run for ops status"),
    )
    monkeypatch.setattr(
        "src.services.quota_policy_service.QuotaPolicyService.release_reservation",
        lambda *_, **__: pytest.fail("release_reservation must not run for ops status"),
    )
    monkeypatch.setattr(
        "src.services.admin_logs_service.AdminLogsRetentionService.storage_summary",
        lambda *_args, **_kwargs: pytest.fail("storage_summary can emit notifications and must not run"),
    )

    with _client(app, _ops_admin) as client:
        response = client.get("/api/v1/admin/ops/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["readOnly"] is True
    assert payload["noExternalCalls"] is True
    assert payload["liveEnforcement"] is False
    assert payload["runtimeBehaviorChanged"] is False
    assert payload["consumerVisible"] is False
    assert payload["advisoryVsEnforcement"]["label"] == "advisory_snapshot"
    assert payload["advisoryVsEnforcement"]["liveEnforcement"] is False
    assert payload["providerStatusSummary"]["advisoryOnly"] is True
    assert payload["quotaCostAdvisoryStatusSummary"]["liveEnforcement"] is False
    assert payload["storageReadinessSummary"]["readOnly"] is True
    assert payload["taskQueueStatusSummary"]["noExternalCalls"] is True
    assert payload["adminLogEvidenceSummary"]["deleteAllowed"] is False
    assert payload["metadata"]["contract"] == "admin_ops_status_snapshot_v2"
    assert payload["metadata"]["projection"] == "bounded_admin_diagnostics"
    assert payload["metadata"]["publicLaunchNoGo"] is True
    _assert_no_sensitive_markers(payload)


def test_admin_ops_status_projects_bounded_admin_diagnostics(app: FastAPI) -> None:
    app.state.task_queue = _TaskQueueFixture()

    with _client(app, _ops_admin) as client:
        response = client.get("/api/v1/admin/ops/status")

    assert response.status_code == 200
    payload = response.json()

    _assert_bounded_section(payload, "providerStatusSummary", expected_service="provider_reliability")
    _assert_bounded_section(payload, "quotaCostAdvisoryStatusSummary", expected_service="quota_cost")
    _assert_bounded_section(payload, "storageReadinessSummary", expected_service="storage")
    _assert_bounded_section(payload, "taskQueueStatusSummary", expected_service="task_queue")
    _assert_bounded_section(payload, "adminLogEvidenceSummary", expected_service="admin_logs")

    cockpit = payload["launchCockpit"]
    assert cockpit["domains"]
    assert cockpit["blockers"]
    assert all(not item for item in (domain["evidenceRefs"] for domain in cockpit["domains"]))
    assert all(not item for item in (domain["blockerRefs"] for domain in cockpit["domains"]))
    assert all(not item for item in (domain["followUpProposals"] for domain in cockpit["domains"]))
    assert all(not item for item in (blocker["evidenceRefs"] for blocker in cockpit["blockers"]))
    _assert_no_sensitive_markers(payload)


def test_admin_ops_status_includes_private_beta_launch_cockpit_no_go_view(app: FastAPI) -> None:
    app.state.task_queue = _TaskQueueFixture()

    with _client(app, _ops_admin) as client:
        response = client.get("/api/v1/admin/ops/status")

    assert response.status_code == 200
    payload = response.json()
    cockpit = payload["launchCockpit"]
    assert cockpit["contract"] == "admin_ops_launch_cockpit_v1"
    assert cockpit["readOnly"] is True
    assert cockpit["advisoryOnly"] is True
    assert cockpit["noExternalCalls"] is True
    assert cockpit["publicLaunchApproved"] is False
    assert cockpit["publicLaunchNoGo"] is True
    assert cockpit["liveEnforcement"] is False
    assert cockpit["runtimeBehaviorChanged"] is False
    assert cockpit["approvalRequired"] is True
    assert cockpit["unsafeActionStates"] == {
        "quotaLiveBlockingEnabled": False,
        "providerCircuitBlockingEnabled": False,
        "mfaEnforcementEnabled": False,
        "rbacFallbackRemoved": False,
        "dbMigrationOrRestoreRun": False,
        "cleanupOrDeleteRun": False,
        "notificationSendEnabled": False,
        "providerLiveCallsEnabled": False,
        "productionConfigChanged": False,
    }

    domain_keys = {item["domainKey"] for item in cockpit["domains"]}
    assert domain_keys == {
        "security_rbac_mfa",
        "quota_cost",
        "provider_reliability",
        "storage_restore",
        "ws2_async",
        "notifications",
        "portfolio_backtest",
        "route_classification",
        "frontend_private_beta_safety",
    }
    assert cockpit["summaryCounts"]["domainCount"] == len(domain_keys)
    assert cockpit["summaryCounts"]["publicLaunchNoGoCount"] == len(domain_keys)
    assert cockpit["summaryCounts"]["realEvidenceMissingCount"] >= 8
    assert cockpit["summaryCounts"]["approvalRequiredCount"] == len(domain_keys)

    by_domain = {item["domainKey"]: item for item in cockpit["domains"]}
    security = by_domain["security_rbac_mfa"]
    assert security["foundationLanded"] is True
    assert security["evidenceToolingPresent"] is True
    assert security["realOperatorEvidenceMissing"] is True
    assert security["approvalRequired"] is True
    assert security["publicLaunchNoGo"] is True
    assert security["readOnly"] is True
    assert security["liveEnforcement"] is False
    assert security["evidenceRefs"] == []
    assert security["blockerRefs"] == []
    assert security["detailRoute"] == "/admin/users"

    quota = by_domain["quota_cost"]
    assert quota["safeNextActions"]
    assert quota["detailRoute"] == "/admin/cost-observability"
    assert quota["followUpProposals"] == []

    provider = by_domain["provider_reliability"]
    assert provider["providerRuntimeChanged"] is False
    assert provider["externalActionsEnabled"] is False
    assert provider["detailRoute"] == "/admin/provider-circuits"

    route = by_domain["route_classification"]
    assert route["realOperatorEvidenceMissing"] is False
    assert route["blockerRefs"] == []
    assert route["evidenceRefs"] == []

    blockers = cockpit["blockers"]
    assert any(blocker["blockerKey"] == "public_launch_no_go" for blocker in blockers)
    assert all(blocker["publicLaunchNoGo"] is True for blocker in blockers)
    assert all(blocker["evidenceRefs"] == [] for blocker in blockers)
    _assert_no_sensitive_markers(payload)


def test_admin_ops_status_does_not_call_provider_status_surfaces(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    app.state.task_queue = _TaskQueueFixture()
    monkeypatch.setattr(
        "requests.sessions.Session.request",
        lambda *_, **__: pytest.fail("external HTTP calls must not run for ops status"),
    )
    monkeypatch.setattr(
        "src.services.market_provider_operations_service.MarketProviderOperationsService.get_operations",
        lambda *_, **__: pytest.fail("provider operations aggregation must not run provider/cache surfaces"),
    )
    monkeypatch.setattr(
        "api.v1.endpoints.admin_provider_circuits.build_options_provider_live_readiness_preflight",
        lambda *_, **__: pytest.fail("live provider readiness preflight must not run"),
    )

    with _client(app, _ops_admin) as client:
        response = client.get("/api/v1/admin/ops/status")

    assert response.status_code == 200
    assert response.json()["providerStatusSummary"]["noExternalCalls"] is True


def test_admin_ops_status_unavailable_source_degrades_without_raw_exception(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_raw_provider_failure(self):
        raise RuntimeError("raw exception raw-owner-user-id raw-session-id access-token traceback provider-payload-secret")

    monkeypatch.setattr(
        "src.services.admin_ops_status_service.AdminOpsStatusService._build_provider_status_summary",
        _raise_raw_provider_failure,
    )

    with _client(app, _ops_admin) as client:
        response = client.get("/api/v1/admin/ops/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["providerStatusSummary"]["available"] is False
    assert payload["providerStatusSummary"]["status"] == "unavailable"
    assert payload["providerStatusSummary"]["reasonCode"] == "source_unavailable"
    assert payload["taskQueueStatusSummary"]["available"] is False
    assert payload["taskQueueStatusSummary"]["status"] == "unavailable"
    _assert_no_sensitive_markers(payload)


def test_admin_ops_status_launch_cockpit_failure_degrades_without_raw_exception(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_launch_cockpit_failure(self):
        raise RuntimeError(
            "RuntimeError postgres://raw-user:raw-password@db.example.test/wolfystock "
            "/Users/example/app.py raw-secret-token traceback"
        )

    monkeypatch.setattr(
        "src.services.admin_ops_status_service.AdminOpsStatusService._build_launch_cockpit",
        _raise_launch_cockpit_failure,
    )

    with _client(app, _ops_admin) as client:
        response = client.get("/api/v1/admin/ops/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["launchCockpit"]["status"] == "unavailable"
    assert payload["launchCockpit"]["message"] == "Admin launch readiness snapshot unavailable."
    _assert_no_sensitive_markers(payload)
