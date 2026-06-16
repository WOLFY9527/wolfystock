# -*- coding: utf-8 -*-
"""Focused tests for the admin backend surface contract parity gate."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1 import api_v1_router
from src.storage import DatabaseManager


FORBIDDEN_RESPONSE_MARKERS = (
    "authorization",
    "bearer",
    "cookie",
    "api_key",
    "apikey",
    "secret",
    "traceback",
    "stack trace",
    "raw_payload",
    "provider_payload",
    "request_body",
    "response_body",
    "session_id",
    "/users/",
    ".py",
    ".md",
)


def _ops_admin() -> CurrentUser:
    return CurrentUser(
        user_id="admin-surface-readiness",
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
        user_id="admin-no-surface-readiness",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="raw-session-id",
        admin_capabilities=("ops:providers:read",),
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
        session_id="raw-session-id",
    )


def _json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def _assert_no_sensitive_markers(payload: object) -> None:
    text = _json_text(payload)
    for marker in FORBIDDEN_RESPONSE_MARKERS:
        assert marker.lower() not in text


def _client(app: FastAPI, user_factory) -> TestClient:
    app.dependency_overrides[get_current_user] = user_factory
    return TestClient(app)


def _surface_by_key(payload: dict, surface_key: str) -> dict:
    return next(item for item in payload["surfaces"] if item["surfaceKey"] == surface_key)


def test_surface_readiness_requires_admin_with_ops_logs_read(tmp_path: Path) -> None:
    DatabaseManager.reset_instance()
    DatabaseManager(db_url=f"sqlite:///{tmp_path / 'admin-surface-readiness.sqlite'}")
    app = FastAPI()
    app.include_router(api_v1_router)

    with _client(app, _regular_user) as client:
        response = client.get("/api/v1/admin/ops/surface-readiness")
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "admin_required"
    _assert_no_sensitive_markers(response.json())

    with _client(app, _admin_without_ops_logs_read) as client:
        response = client.get("/api/v1/admin/ops/surface-readiness")
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "admin_capability_required"
    assert "ops:logs:read" not in response.text
    _assert_no_sensitive_markers(response.json())

    with _client(app, _ops_admin) as client:
        response = client.get("/api/v1/admin/ops/surface-readiness")
    assert response.status_code == 200

    DatabaseManager.reset_instance()


def test_surface_readiness_returns_read_only_contract_truth_table(tmp_path: Path) -> None:
    DatabaseManager.reset_instance()
    DatabaseManager(db_url=f"sqlite:///{tmp_path / 'admin-surface-readiness.sqlite'}")
    app = FastAPI()
    app.include_router(api_v1_router)

    with _client(app, _ops_admin) as client:
        response = client.get("/api/v1/admin/ops/surface-readiness")

    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["readOnly"] is True
    assert payload["noExternalCalls"] is True
    assert payload["liveEnforcement"] is False
    assert payload["runtimeBehaviorChanged"] is False
    assert payload["consumerVisible"] is False
    assert payload["metadata"] == {
        "contract": "backend_surface_contract_parity_v1",
        "projection": "route_registry_contract_signals_only",
        "providerCallsAttempted": False,
        "cacheMutation": False,
        "authBehaviorChanged": False,
    }
    assert payload["summary"]["surfaceCount"] == 10
    assert set(payload["summary"]["statusCounts"]) == {
        "ready",
        "ready_fixture_only",
        "mixed_contract",
        "degraded_contract",
    }

    surface_keys = {item["surfaceKey"] for item in payload["surfaces"]}
    assert surface_keys == {
        "market_decision_cockpit",
        "daily_intelligence",
        "market_overview",
        "research_radar",
        "scanner",
        "watchlist",
        "portfolio_structure_review",
        "scenario_lab",
        "stock_structure_decision",
        "options_gamma_observation",
    }

    cockpit = _surface_by_key(payload, "market_decision_cockpit")
    assert cockpit["status"] == "degraded_contract"
    assert cockpit["primaryRoute"]["method"] == "GET"
    assert cockpit["primaryRoute"]["path"] == "/api/v1/market/decision-cockpit"
    assert cockpit["authRequirement"] == {"status": "known", "label": "optional_user"}
    assert cockpit["schemaVersionStatus"] == "present"
    assert cockpit["observationBoundaryStatus"] == "present"
    assert cockpit["degradedStateShapeStatus"] == "present"
    assert cockpit["consumerSafeIssueLabelsStatus"] == "raw_internal_codes_detected"
    assert "response_model_untyped" in cockpit["gaps"]

    radar = _surface_by_key(payload, "research_radar")
    assert radar["status"] == "degraded_contract"
    assert radar["primaryRoute"]["method"] == "GET"
    assert radar["primaryRoute"]["path"] == "/api/v1/research/radar"
    assert radar["authRequirement"] == {"status": "known", "label": "authenticated_user"}
    assert radar["schemaVersionStatus"] == "present"
    assert radar["observationBoundaryStatus"] == "present"
    assert radar["degradedStateShapeStatus"] == "present"
    assert radar["consumerSafeIssueLabelsStatus"] == "raw_internal_codes_detected"
    assert "response_model_untyped" in radar["gaps"]

    market_overview = _surface_by_key(payload, "market_overview")
    assert market_overview["status"] == "mixed_contract"
    assert market_overview["routeStatus"] == "all_present"
    assert len(market_overview["relatedRoutes"]) >= 3

    options = _surface_by_key(payload, "options_gamma_observation")
    assert options["status"] == "ready_fixture_only"
    assert options["implementationStatus"] == "fixture_only"
    assert options["consumerSafeIssueLabelsStatus"] in {"present", "unknown"}

    scenario_lab = _surface_by_key(payload, "scenario_lab")
    assert scenario_lab["status"] == "ready"
    assert scenario_lab["primaryRoute"]["method"] == "POST"
    assert scenario_lab["primaryRoute"]["path"] == "/api/v1/market/scenario-lab"

    _assert_no_sensitive_markers(payload)
    DatabaseManager.reset_instance()
