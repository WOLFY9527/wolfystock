# -*- coding: utf-8 -*-
"""Release-facing auth/RBAC security contracts for private API surfaces."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import src.auth as auth
from api.middlewares.auth import add_auth_middleware
from api.v1 import api_v1_router
from src.admin_rbac import OPS_ADMIN_ROLE, SECURITY_ADMIN_ROLE
from src.auth import create_session
from src.multi_user import ROLE_ADMIN, ROLE_USER
from src.storage import AdminUserRole, DatabaseManager


AUDIT_SCRIPT = REPO_ROOT / "scripts" / "auth_rbac_release_audit.py"
BACKEND_ROUTE_CLASSIFICATION_FIXTURE = (
    REPO_ROOT / "tests" / "fixtures" / "auth" / "backend_route_capability_inventory.json"
)
AUDIT_EXPECTED_CAPABILITY_MARKERS = {
    "admin_users": (
        'require_admin_capability("users:read")',
        'require_admin_capability("users:activity:read")',
        "/users/onboard",
    ),
    "market_provider_operations": (
        'require_admin_capability("ops:providers:read")',
    ),
}

RAW_BODY_MARKER = "raw-auth-rbac-body-token"
RAW_COOKIE_MARKER = "raw-auth-rbac-cookie-token"
RAW_AUTH_MARKER = "raw-auth-rbac-bearer-token"
RAW_SESSION_MARKER = "raw-auth-rbac-session-id"
RAW_CLIENT_IP = "203.0.113.222"
RAW_PROVIDER_PAYLOAD = "provider_payload raw provider response"

FORBIDDEN_ERROR_MARKERS = (
    RAW_BODY_MARKER,
    RAW_COOKIE_MARKER,
    RAW_AUTH_MARKER,
    RAW_SESSION_MARKER,
    RAW_CLIENT_IP,
    RAW_PROVIDER_PAYLOAD,
    "authorization",
    "traceback",
    "stack trace",
    "raw request body",
    "raw_request_body",
    "provider_payload",
)


def _safe_error(error: str, message: str, status: int) -> dict[str, object]:
    return {
        "error": error,
        "code": error,
        "message": message,
        "status": status,
        "reason": error,
        "consumerSafeMessage": message,
    }

PRIVATE_SURFACES = (
    ("GET", "/api/v1/system/config"),
    ("GET", "/api/v1/portfolio/accounts"),
    ("GET", "/api/v1/watchlist/items"),
    ("GET", "/api/v1/backtest/runs"),
    ("GET", "/api/v1/admin/users"),
    ("GET", "/api/v1/admin/logs/storage/summary"),
    ("GET", "/api/v1/admin/mission-control"),
    ("GET", "/api/v1/admin/cost/llm-ledger-summary"),
    ("GET", "/api/v1/admin/providers/circuits"),
    ("GET", "/api/v1/admin/market-providers/operations"),
)

ORDINARY_USER_FORBIDDEN_SURFACES = (
    ("admin_users", "GET", "/api/v1/admin/users"),
    ("admin_logs", "GET", "/api/v1/admin/logs/storage/summary"),
    ("cost_observability", "GET", "/api/v1/admin/cost/llm-ledger-summary"),
    ("evidence_workflow_audit_drillthrough", "GET", "/api/v1/admin/logs?query=evidence%20workflow"),
    ("mission_control", "GET", "/api/v1/admin/mission-control"),
    ("provider_circuits", "GET", "/api/v1/admin/providers/circuits"),
    ("market_provider_operations", "GET", "/api/v1/admin/market-providers/operations"),
)
CAPABILITY_GATED_DIAGNOSTIC_SURFACES = (
    ("agent_status", "GET", "/api/v1/agent/status"),
    ("agent_models", "GET", "/api/v1/agent/models"),
    ("agent_provider_health", "GET", "/api/v1/agent/provider-health"),
    ("agent_chat_send", "POST", "/api/v1/agent/chat/send"),
    ("scanner_watchlist_today", "GET", "/api/v1/scanner/watchlists/today"),
    ("scanner_watchlist_recent", "GET", "/api/v1/scanner/watchlists/recent"),
    ("scanner_status", "GET", "/api/v1/scanner/status"),
    ("usage_summary", "GET", "/api/v1/usage/summary"),
    ("storage_summary", "GET", "/api/v1/admin/logs/storage/summary"),
    ("cost_ledger", "GET", "/api/v1/admin/cost/llm-ledger-summary"),
    ("mission_control", "GET", "/api/v1/admin/mission-control"),
    ("quota_dry_run", "POST", "/api/v1/admin/cost/quota-dry-run"),
    ("provider_quota_windows", "GET", "/api/v1/admin/providers/quota-windows"),
    ("provider_sla_readiness", "GET", "/api/v1/admin/providers/sla-readiness"),
    ("provider_operations_matrix", "GET", "/api/v1/admin/providers/operations-matrix"),
    ("provider_usage_ledger", "GET", "/api/v1/admin/provider-usage-ledger"),
    ("market_provider_operations", "GET", "/api/v1/admin/market-providers/operations"),
    ("market_provider_fit_advisor", "GET", "/api/v1/market/provider-fit-advisor"),
)
OPTIONS_AUTH_REQUIRED_RESEARCH_SURFACES = (
    ("options_summary", "GET", "/api/v1/options/underlyings/{symbol}/summary", "/api/v1/options/underlyings/TEM/summary", None),
    (
        "options_expirations",
        "GET",
        "/api/v1/options/underlyings/{symbol}/expirations",
        "/api/v1/options/underlyings/TEM/expirations",
        None,
    ),
    ("options_chain", "GET", "/api/v1/options/underlyings/{symbol}/chain", "/api/v1/options/underlyings/TEM/chain", None),
    (
        "options_analyze",
        "POST",
        "/api/v1/options/analyze",
        "/api/v1/options/analyze",
        {
            "symbol": "TEM",
            "direction": "bullish",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
        },
    ),
    (
        "options_decision",
        "POST",
        "/api/v1/options/decision/evaluate",
        "/api/v1/options/decision/evaluate",
        {
            "symbol": "TEM",
            "strategy": "bull_call_spread",
            "expiration": "2026-06-19",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "riskBudget": 600,
        },
    ),
    (
        "options_scenario",
        "POST",
        "/api/v1/options/scenario",
        "/api/v1/options/scenario",
        {
            "symbol": "TEM",
            "strategy": "long_put",
            "contractSymbol": "TEM260619P00050000",
            "expiration": "2026-06-19",
            "targetPrice": 45,
        },
    ),
    (
        "options_strategy_compare",
        "POST",
        "/api/v1/options/strategies/compare",
        "/api/v1/options/strategies/compare",
        {
            "symbol": "TEM",
            "direction": "bullish",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
        },
    ),
)
QUOTA_DRY_RUN_REQUEST = {
    "ownerUserId": "ordinary-user",
    "routeFamily": "analysis",
    "provider": "openai",
    "modelTier": "standard",
    "tokenEstimate": 100,
    "estimatedUnits": 1,
    "enforcementMode": "dry_run",
    "operation": "estimate",
    "pricingStatus": "ok",
}
AGENT_SEND_REQUEST = {
    "content": "T-1463 capability-gated notification dispatch check",
    "title": "T-1463",
}
LEGACY_ROLE_ONLY_ADMIN_ROUTE_COUNTS: dict[str, int] = {}
ANONYMOUS_DENIAL_MATRIX_SURFACES = (
    (
        "agent_skills_member",
        "GET",
        "/api/v1/agent/skills",
        "/api/v1/agent/skills",
        "authenticated_member",
        "authenticated_user",
        None,
        None,
    ),
    (
        "agent_chat_sessions_member",
        "GET",
        "/api/v1/agent/chat/sessions",
        "/api/v1/agent/chat/sessions",
        "authenticated_member",
        "authenticated_user",
        None,
        None,
    ),
    (
        "agent_status_operator_diagnostic",
        "GET",
        "/api/v1/agent/status",
        "/api/v1/agent/status",
        "operator_diagnostic",
        "admin_capability",
        "ops:providers:read",
        None,
    ),
    (
        "agent_models_operator_diagnostic",
        "GET",
        "/api/v1/agent/models",
        "/api/v1/agent/models",
        "operator_diagnostic",
        "admin_capability",
        "ops:providers:read",
        None,
    ),
    (
        "agent_provider_health_operator_diagnostic",
        "GET",
        "/api/v1/agent/provider-health",
        "/api/v1/agent/provider-health",
        "operator_diagnostic",
        "admin_capability",
        "ops:providers:read",
        None,
    ),
    (
        "agent_chat_send_capability_admin",
        "POST",
        "/api/v1/agent/chat/send",
        "/api/v1/agent/chat/send",
        "admin_capability_required",
        "admin_capability",
        "ops:notifications:write",
        AGENT_SEND_REQUEST,
    ),
    (
        "scanner_runs_member",
        "GET",
        "/api/v1/scanner/runs",
        "/api/v1/scanner/runs",
        "authenticated_member",
        "authenticated_user",
        None,
        None,
    ),
    (
        "scanner_strategy_simulation_member",
        "GET",
        "/api/v1/scanner/strategy-simulation",
        "/api/v1/scanner/strategy-simulation",
        "authenticated_member",
        "authenticated_user",
        None,
        None,
    ),
    (
        "scanner_status_capability_admin",
        "GET",
        "/api/v1/scanner/status",
        "/api/v1/scanner/status",
        "admin_capability_required",
        "admin_capability",
        "scanner:admin:read",
        None,
    ),
    (
        "scanner_watchlist_today_capability_admin",
        "GET",
        "/api/v1/scanner/watchlists/today",
        "/api/v1/scanner/watchlists/today",
        "admin_capability_required",
        "admin_capability",
        "scanner:admin:read",
        None,
    ),
    (
        "scanner_watchlist_recent_capability_admin",
        "GET",
        "/api/v1/scanner/watchlists/recent",
        "/api/v1/scanner/watchlists/recent",
        "admin_capability_required",
        "admin_capability",
        "scanner:admin:read",
        None,
    ),
    (
        "usage_summary_capability_admin",
        "GET",
        "/api/v1/usage/summary",
        "/api/v1/usage/summary",
        "admin_capability_required",
        "admin_capability",
        "cost:observability:read",
        None,
    ),
    (
        "system_config_capability_admin",
        "GET",
        "/api/v1/system/config",
        "/api/v1/system/config",
        "admin_capability_required",
        "admin_capability",
        "ops:system_config:read",
        None,
    ),
    (
        "admin_ops_status_capability_admin",
        "GET",
        "/api/v1/admin/ops/status",
        "/api/v1/admin/ops/status",
        "admin_capability_required",
        "admin_capability",
        "ops:logs:read",
        None,
    ),
    (
        "provider_quota_windows_capability_admin",
        "GET",
        "/api/v1/admin/providers/quota-windows",
        "/api/v1/admin/providers/quota-windows",
        "admin_capability_required",
        "admin_capability",
        "ops:providers:read",
        None,
    ),
    (
        "market_provider_fit_advisor_capability_admin",
        "GET",
        "/api/v1/market/provider-fit-advisor",
        "/api/v1/market/provider-fit-advisor",
        "admin_capability_required",
        "admin_capability",
        "ops:providers:read",
        None,
    ),
    (
        "quota_dry_run_capability_admin",
        "POST",
        "/api/v1/admin/cost/quota-dry-run",
        "/api/v1/admin/cost/quota-dry-run",
        "admin_capability_required",
        "admin_capability",
        "cost:observability:read",
        QUOTA_DRY_RUN_REQUEST,
    ),
)


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._password_hash_value = None
    auth._rate_limit = {}
    auth._admin_reauth_markers = {}
    try:
        from api.middlewares.public_abuse_limiter import reset_public_api_abuse_limiter_state
    except ModuleNotFoundError:
        return
    reset_public_api_abuse_limiter_state()


@pytest.fixture
def auth_release_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _reset_auth_globals()
    DatabaseManager.reset_instance()
    db_path = tmp_path / "auth-rbac-release.db"
    env_path = tmp_path / ".env"
    env_path.write_text(
        f"ADMIN_AUTH_ENABLED=true\nDATABASE_PATH={db_path}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("ENV_FILE", str(env_path))
    monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
    monkeypatch.setattr(auth, "_get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(auth, "_is_auth_enabled_from_env", lambda: True)
    auth._auth_enabled = True

    db = DatabaseManager(db_url=f"sqlite:///{db_path}")
    app = FastAPI()
    add_auth_middleware(app)
    app.include_router(api_v1_router)
    client = TestClient(app)
    try:
        yield client, db
    finally:
        client.close()
        DatabaseManager.reset_instance()
        _reset_auth_globals()


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _backend_surface_classifications_by_signature() -> dict[tuple[str, str], dict[str, object]]:
    fixture = json.loads(BACKEND_ROUTE_CLASSIFICATION_FIXTURE.read_text(encoding="utf-8"))
    entries = fixture["route_surface_classifications"]
    by_signature = {(entry["method"], entry["path"]): entry for entry in entries}
    assert len(by_signature) == len(entries)
    return by_signature


def _assert_public_error_safe(*parts: object) -> None:
    text = "\n".join(_json_text(part) if not isinstance(part, str) else part for part in parts).lower()
    for marker in FORBIDDEN_ERROR_MARKERS:
        assert marker.lower() not in text


def _set_cookie_for_user(client: TestClient, db: DatabaseManager, *, user_id: str, role: str) -> None:
    username = user_id.replace("_", "-")
    db.create_or_update_app_user(
        user_id=user_id,
        username=username,
        display_name=username.title(),
        role=role,
        is_active=True,
    )
    client.cookies.set(
        auth.COOKIE_NAME,
        create_session(user_id=user_id, username=username, role=role),
    )


def _request_capability_diagnostic_surface(client: TestClient, method: str, path: str):
    kwargs = {}
    if path == "/api/v1/admin/cost/quota-dry-run":
        kwargs["json"] = QUOTA_DRY_RUN_REQUEST
    if path == "/api/v1/agent/chat/send":
        kwargs["json"] = AGENT_SEND_REQUEST
    return client.request(method, path, **kwargs)


def test_unauthenticated_users_cannot_access_private_api_surfaces(auth_release_client) -> None:
    client, _ = auth_release_client

    responses = [
        client.request(method, path, headers={"X-Forwarded-For": RAW_CLIENT_IP})
        for method, path in PRIVATE_SURFACES
    ]

    assert [response.status_code for response in responses] == [401] * len(PRIVATE_SURFACES)
    for response in responses:
        assert response.json() == _safe_error("unauthorized", "Login required", 401)
        _assert_public_error_safe(response.json(), dict(response.headers))


def test_anonymous_denial_matrix_matches_sensitive_route_inventory(auth_release_client) -> None:
    client, _ = auth_release_client
    inventory = _backend_surface_classifications_by_signature()

    responses = {}
    for index, (
        label,
        method,
        inventory_path,
        request_path,
        expected_classification,
        expected_auth_dependency,
        expected_capability,
        request_json,
    ) in enumerate(ANONYMOUS_DENIAL_MATRIX_SURFACES, start=10):
        entry = inventory[(method, inventory_path)]
        assert entry["surface_classification"] == expected_classification, label
        assert entry["auth_dependency_label"] == expected_auth_dependency, label
        assert entry["capability_label"] == expected_capability, label
        if expected_auth_dependency == "admin_capability":
            assert entry["no_go_marker"] is None, label

        kwargs = {"headers": {"X-Forwarded-For": f"203.0.113.{index}"}}
        if request_json is not None:
            kwargs["json"] = request_json
        responses[label] = client.request(method, request_path, **kwargs)

    assert {label: response.status_code for label, response in responses.items()} == {
        surface[0]: 401 for surface in ANONYMOUS_DENIAL_MATRIX_SURFACES
    }
    for response in responses.values():
        assert response.json() == _safe_error("unauthorized", "Login required", 401)
        _assert_public_error_safe(response.json(), dict(response.headers))


def test_options_release_contract_is_auth_required_fixture_research_not_launch_approval(
    auth_release_client,
) -> None:
    client, db = auth_release_client
    inventory = _backend_surface_classifications_by_signature()

    anonymous_responses = {}
    member_responses = {}
    for index, (label, method, path, request_path, request_json) in enumerate(
        OPTIONS_AUTH_REQUIRED_RESEARCH_SURFACES,
        start=60,
    ):
        entry = inventory[(method, path)]
        marker = str(entry["no_go_marker"])
        assert entry["surface_classification"] == "authenticated_member", label
        assert entry["auth_dependency_label"] == "authenticated_user", label
        assert entry["capability_label"] is None, label
        assert "TODO/NO-GO" in marker, label
        assert "fixture/demo" in marker, label
        assert "production Options decisioning" in marker, label
        assert "provider evidence" in marker, label
        _assert_public_error_safe(entry)

        kwargs = {"headers": {"X-Forwarded-For": f"203.0.113.{index}"}}
        if request_json is not None:
            kwargs["json"] = request_json
        anonymous_responses[label] = client.request(method, request_path, **kwargs)

    assert {label: response.status_code for label, response in anonymous_responses.items()} == {
        surface[0]: 401 for surface in OPTIONS_AUTH_REQUIRED_RESEARCH_SURFACES
    }
    for response in anonymous_responses.values():
        assert response.json() == _safe_error("unauthorized", "Login required", 401)
        _assert_public_error_safe(response.json(), dict(response.headers))

    client.cookies.clear()
    _set_cookie_for_user(client, db, user_id="ordinary-user", role=ROLE_USER)
    for label, method, _path, request_path, request_json in OPTIONS_AUTH_REQUIRED_RESEARCH_SURFACES:
        kwargs = {}
        if request_json is not None:
            kwargs["json"] = request_json
        member_responses[label] = client.request(method, request_path, **kwargs)

    assert {label: response.status_code for label, response in member_responses.items()} == {
        surface[0]: 200 for surface in OPTIONS_AUTH_REQUIRED_RESEARCH_SURFACES
    }
    for response in member_responses.values():
        _assert_public_error_safe(response.json())


def test_agent_skills_member_metadata_is_session_gated_and_payload_safe(
    auth_release_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, db = auth_release_client
    inventory = _backend_surface_classifications_by_signature()
    entry = inventory[("GET", "/api/v1/agent/skills")]
    assert entry["surface_classification"] == "authenticated_member"
    assert entry["auth_dependency_label"] == "authenticated_user"
    assert entry["capability_label"] is None
    assert entry["no_go_marker"] is None

    skill_manager = type(
        "SkillManagerStub",
        (),
        {
            "list_skills": lambda self: [
                type(
                    "SkillStub",
                    (),
                    {
                        "name": "bull_trend",
                        "display_name": "Bull Trend",
                        "description": "Member-facing trend observation lens.",
                        "user_invocable": True,
                        "default_priority": 10,
                        "default_active": True,
                        "instructions": "raw prompt must not appear",
                        "required_tools": ["internal_tool"],
                        "allowed_tools": ["internal_tool"],
                        "entrypoint": "/private/SKILL.md",
                        "bundle_dir": "/private",
                        "source": "builtin",
                    },
                )(),
                type(
                    "HiddenSkillStub",
                    (),
                    {
                        "name": "operator_probe",
                        "display_name": "Operator Probe",
                        "description": "Operator-only topology",
                        "user_invocable": False,
                        "default_priority": 1,
                        "default_active": False,
                    },
                )(),
            ]
        },
    )()
    monkeypatch.setattr("src.agent.factory.get_skill_manager", lambda _config: skill_manager)

    anonymous = client.get("/api/v1/agent/skills", headers={"X-Forwarded-For": RAW_CLIENT_IP})
    assert anonymous.status_code == 401
    assert anonymous.json() == _safe_error("unauthorized", "Login required", 401)

    client.cookies.clear()
    _set_cookie_for_user(client, db, user_id="ordinary-user", role=ROLE_USER)
    member = client.get("/api/v1/agent/skills")
    assert member.status_code == 200
    assert member.json() == {
        "skills": [
            {
                "id": "bull_trend",
                "name": "Bull Trend",
                "description": "Member-facing trend observation lens.",
            }
        ],
        "default_skill_id": "bull_trend",
    }

    client.cookies.clear()
    _set_cookie_for_user(client, db, user_id="admin-without-capabilities", role=ROLE_ADMIN)
    admin = client.get("/api/v1/agent/skills")
    assert admin.status_code == 200
    assert admin.json() == member.json()

    payload_text = _json_text(member.json()).lower()
    for marker in (
        "raw prompt",
        "instructions",
        "required_tools",
        "allowed_tools",
        "internal_tool",
        "entrypoint",
        "bundle_dir",
        "source",
        "/private",
        "operator_probe",
        "operator-only",
        "api_key",
        "secret",
        "provider",
        "routing",
        "command",
        "environment",
    ):
        assert marker not in payload_text
    _assert_public_error_safe(anonymous.json(), member.json(), admin.json())


def test_ordinary_users_cannot_access_admin_release_surfaces(auth_release_client) -> None:
    client, db = auth_release_client
    _set_cookie_for_user(client, db, user_id="ordinary-user", role=ROLE_USER)

    results = {
        label: client.request(method, path, headers={"X-Forwarded-For": RAW_CLIENT_IP})
        for label, method, path in ORDINARY_USER_FORBIDDEN_SURFACES
    }

    assert {label: response.status_code for label, response in results.items()} == {
        label: 403 for label, *_ in ORDINARY_USER_FORBIDDEN_SURFACES
    }
    for response in results.values():
        _assert_public_error_safe(response.json(), dict(response.headers))


def test_ordinary_users_are_denied_before_capability_details_on_diagnostics(auth_release_client) -> None:
    client, db = auth_release_client
    _set_cookie_for_user(client, db, user_id="ordinary-user", role=ROLE_USER)

    results = {
        label: _request_capability_diagnostic_surface(client, method, path)
        for label, method, path in CAPABILITY_GATED_DIAGNOSTIC_SURFACES
    }

    assert {label: response.status_code for label, response in results.items()} == {
        label: 403 for label, *_ in CAPABILITY_GATED_DIAGNOSTIC_SURFACES
    }
    for label, response in results.items():
        assert response.json()["detail"]["error"] == "admin_required", label
        assert "admin_capability_required" not in response.text
        _assert_public_error_safe(response.json(), dict(response.headers))


def test_admin_without_matching_capabilities_cannot_access_diagnostic_surfaces(
    auth_release_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, db = auth_release_client
    monkeypatch.setenv("WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED", "false")
    _set_cookie_for_user(client, db, user_id="admin-without-capabilities", role=ROLE_ADMIN)

    results = {
        label: _request_capability_diagnostic_surface(client, method, path)
        for label, method, path in CAPABILITY_GATED_DIAGNOSTIC_SURFACES
    }

    assert {label: response.status_code for label, response in results.items()} == {
        label: 403 for label, *_ in CAPABILITY_GATED_DIAGNOSTIC_SURFACES
    }
    for label, response in results.items():
        assert response.json()["detail"]["error"] == "admin_capability_required", label
        _assert_public_error_safe(response.json(), dict(response.headers))


def test_auth_disabled_mode_exposes_transitional_admin_and_is_not_public_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_auth_globals()
    DatabaseManager.reset_instance()
    db_path = tmp_path / "auth-disabled-surface.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setattr(auth, "_get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(auth, "_is_auth_enabled_from_env", lambda: False)
    auth._auth_enabled = False

    DatabaseManager(db_url=f"sqlite:///{db_path}")
    app = FastAPI()
    add_auth_middleware(app)
    app.include_router(api_v1_router)
    client = TestClient(app)
    try:
        storage = client.get("/api/v1/admin/logs/storage/summary")
        provider = client.get("/api/v1/admin/providers/circuits")
        usage = client.get("/api/v1/usage/summary")

        evidence = {
            "authDisabledPublicIngressSafe": False,
            "surfaceClassification": "launch_blocker",
            "storageStatus": storage.status_code,
            "providerStatus": provider.status_code,
            "usageStatus": usage.status_code,
            "transitionalAdminObserved": all(response.status_code == 200 for response in (storage, provider, usage)),
        }
        assert evidence == {
            "authDisabledPublicIngressSafe": False,
            "surfaceClassification": "launch_blocker",
            "storageStatus": 200,
            "providerStatus": 200,
            "usageStatus": 200,
            "transitionalAdminObserved": True,
        }
        _assert_public_error_safe(evidence)
    finally:
        client.close()
        DatabaseManager.reset_instance()
        _reset_auth_globals()


def test_adjacent_admin_capabilities_do_not_unlock_cost_or_provider_routes(
    auth_release_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, db = auth_release_client
    monkeypatch.setenv("WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED", "false")
    _set_cookie_for_user(client, db, user_id="security-admin", role=ROLE_ADMIN)
    with db.get_session() as session:
        session.add(AdminUserRole(user_id="security-admin", role_key=SECURITY_ADMIN_ROLE))
        session.commit()

    allowed_adjacent = client.get("/api/v1/admin/logs/storage/summary")
    denied_cost = client.get("/api/v1/admin/cost/llm-ledger-summary")
    denied_provider = client.get("/api/v1/admin/providers/circuits")
    denied_market_provider_operations = client.get("/api/v1/admin/market-providers/operations")

    assert allowed_adjacent.status_code == 200
    assert denied_cost.status_code == 403
    assert denied_provider.status_code == 403
    assert denied_market_provider_operations.status_code == 403
    assert denied_cost.json()["detail"]["error"] == "admin_capability_required"
    assert denied_provider.json()["detail"]["error"] == "admin_capability_required"
    assert denied_market_provider_operations.json()["detail"]["error"] == "admin_capability_required"
    _assert_public_error_safe(
        denied_cost.json(),
        denied_provider.json(),
        denied_market_provider_operations.json(),
    )


def test_provider_read_admin_can_access_agent_operator_diagnostics_without_secrets(
    auth_release_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, db = auth_release_client
    monkeypatch.setenv("WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED", "false")
    _set_cookie_for_user(client, db, user_id="provider-admin", role=ROLE_ADMIN)
    with db.get_session() as session:
        session.add(AdminUserRole(user_id="provider-admin", role_key=OPS_ADMIN_ROLE))
        session.commit()

    responses = {
        "status": client.get("/api/v1/agent/status"),
        "models": client.get("/api/v1/agent/models"),
        "provider_health": client.get("/api/v1/agent/provider-health"),
    }

    assert {label: response.status_code for label, response in responses.items()} == {
        "status": 200,
        "models": 200,
        "provider_health": 200,
    }
    assert set(responses["status"].json()) == {"enabled"}
    assert set(responses["models"].json()) == {"models"}
    provider_health = responses["provider_health"].json()
    assert {"routingMode", "currentProvider", "currentModel", "providers"} <= set(provider_health)
    _assert_public_error_safe(*(response.json() for response in responses.values()))


def test_role_only_legacy_admin_route_dependencies_are_cleared() -> None:
    endpoint_dir = REPO_ROOT / "api" / "v1" / "endpoints"
    actual_counts = {
        path.name: count
        for path in endpoint_dir.glob("*.py")
        if (count := path.read_text(encoding="utf-8").count("Depends(require_admin_user)"))
    }

    assert actual_counts == LEGACY_ROLE_ONLY_ADMIN_ROUTE_COUNTS


def test_auth_401_403_and_429_errors_and_logs_are_sanitized(
    auth_release_client,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, db = auth_release_client
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    sensitive_headers = {
        "content-type": "application/json",
        "Authorization": f"Bearer {RAW_AUTH_MARKER}",
        "Cookie": f"{auth.COOKIE_NAME}={RAW_COOKIE_MARKER}",
        "X-Forwarded-For": RAW_CLIENT_IP,
        "X-Session-Id": RAW_SESSION_MARKER,
    }
    sensitive_body = {
        "token": RAW_BODY_MARKER,
        "sessionId": RAW_SESSION_MARKER,
        "providerPayload": RAW_PROVIDER_PAYLOAD,
    }

    with caplog.at_level(logging.INFO):
        unauthenticated = client.post(
            "/api/v1/admin/users/ordinary-user/disable",
            json=sensitive_body,
            headers=sensitive_headers,
        )
        repeated_unauthenticated = client.post(
            "/api/v1/admin/users/ordinary-user/disable",
            json=sensitive_body,
            headers=sensitive_headers,
        )
        auth._auth_enabled = None
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=False):
            public_failure = client.post(
                "/api/v1/options/decision/evaluate",
                content='{"symbol":"TEM"',
                headers=sensitive_headers,
            )
            limited = client.post(
                "/api/v1/options/decision/evaluate",
                content='{"symbol":"TEM"',
                headers=sensitive_headers,
            )
        auth._auth_enabled = None
        client.cookies.clear()
        _set_cookie_for_user(client, db, user_id="ordinary-user", role=ROLE_USER)
        forbidden = client.get(
            "/api/v1/admin/providers/circuits",
            headers={
                "Authorization": f"Bearer {RAW_AUTH_MARKER}",
                "X-Forwarded-For": RAW_CLIENT_IP,
                "X-Session-Id": RAW_SESSION_MARKER,
            },
        )

    assert [
        unauthenticated.status_code,
        repeated_unauthenticated.status_code,
        public_failure.status_code,
        limited.status_code,
        forbidden.status_code,
    ] == [401, 401, 422, 429, 403]
    assert limited.json() == {
        "error": "rate_limited",
        "message": "Too many public API errors; retry later.",
    }
    _assert_public_error_safe(
        caplog.text,
        unauthenticated.json(),
        repeated_unauthenticated.json(),
        public_failure.json(),
        limited.json(),
        forbidden.json(),
        dict(unauthenticated.headers),
        dict(repeated_unauthenticated.headers),
        dict(public_failure.headers),
        dict(limited.headers),
        dict(forbidden.headers),
    )


def test_offline_auth_rbac_release_audit_cli_outputs_bounded_json() -> None:
    result = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT), "--offline"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert set(payload) == {
        "auditStatus",
        "surfacesChecked",
        "riskyFindings",
        "manualReviewRequired",
        "networkCallsExecuted",
    }
    assert payload["networkCallsExecuted"] is False
    assert payload["manualReviewRequired"] is True
    assert payload["auditStatus"] == "manual_review_required"
    assert isinstance(payload["surfacesChecked"], list)
    assert 6 <= len(payload["surfacesChecked"]) <= 12
    surfaces = {surface["label"]: surface for surface in payload["surfacesChecked"]}
    labels = set(surfaces)
    assert {
        "private_api_auth_middleware",
        "admin_users",
        "admin_logs",
        "cost_observability",
        "provider_circuits",
        "market_provider_operations",
        "public_error_limiter",
        "operator_evidence_workflow",
    } <= labels
    findings_by_surface: dict[str, set[str]] = {}
    for finding in payload["riskyFindings"]:
        findings_by_surface.setdefault(str(finding["surface"]), set()).add(str(finding["reasonCode"]))

    for label in ("admin_users", "market_provider_operations"):
        assert surfaces[label]["status"] == "pass"
        assert "expected_release_guard_marker_missing" not in findings_by_surface.get(label, set())

    audit_script_source = AUDIT_SCRIPT.read_text(encoding="utf-8")
    for markers in AUDIT_EXPECTED_CAPABILITY_MARKERS.values():
        for marker in markers:
            assert marker in audit_script_source

    _assert_public_error_safe(payload, result.stderr)


def test_release_audit_contract_requires_manual_review_before_launch() -> None:
    result = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT), "--offline"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    audit_script_source = AUDIT_SCRIPT.read_text(encoding="utf-8")
    payload = json.loads(result.stdout)

    assert result.returncode == 0, result.stderr
    assert payload["manualReviewRequired"] is True
    assert payload["auditStatus"] == "manual_review_required"
    assert payload["networkCallsExecuted"] is False
    assert any(
        surface["label"] == "manual_release_review_contract"
        and surface["status"] == "pass"
        and "does not approve launch" in surface["reviewNote"]
        for surface in payload["surfacesChecked"]
    )
    for required in (
        "manualReviewRequired",
        "manual_review_required",
        "networkCallsExecuted",
        "approve launch",
    ):
        assert required in audit_script_source
