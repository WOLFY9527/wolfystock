# -*- coding: utf-8 -*-
"""Focused tests for the admin backend surface contract parity gate."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1 import api_v1_router
from src.services.admin_surface_contract_readiness_service import (
    AdminSurfaceContractReadinessService,
)
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
COCKPIT_REQUIRED_CONTRACT_FIELDS = (
    "schemaVersion",
    "noAdviceDisclosure",
    "observationOnly",
    "decisionGrade",
    "consumerIssues",
    "degradedSurfaceSummary",
    "researchWorkflow",
    "crossSurfaceEvidence",
    "topResearchQuestions",
    "priorityDrilldowns",
    "evidenceConflicts",
    "nextObservationSteps",
)
COCKPIT_SYNTHESIS_FIELDS = (
    "researchWorkflow",
    "crossSurfaceEvidence",
    "topResearchQuestions",
    "priorityDrilldowns",
    "evidenceConflicts",
    "nextObservationSteps",
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


def _readiness_payload_for_cockpit_fields(fields: tuple[str, ...]) -> dict:
    app = FastAPI()
    app.include_router(api_v1_router)
    cockpit_spec = next(
        spec
        for spec in AdminSurfaceContractReadinessService._SURFACES
        if spec.key == "market_decision_cockpit"
    )
    route_spec = replace(cockpit_spec.primary_route, manual_fields=fields)
    service_cls = type(
        "_SingleCockpitReadinessService",
        (AdminSurfaceContractReadinessService,),
        {"_SURFACES": (replace(cockpit_spec, primary_route=route_spec),)},
    )
    return service_cls().build_snapshot(routes=app.routes)


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
    }
    assert payload["summary"]["statusCounts"] == {
        "ready": 9,
        "ready_fixture_only": 1,
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
    assert cockpit["status"] == "ready"
    assert cockpit["contract"] == "market_decision_cockpit.v1"
    assert cockpit["primaryRoute"]["method"] == "GET"
    assert cockpit["primaryRoute"]["path"] == "/api/v1/market/decision-cockpit"
    assert cockpit["authRequirement"] == {"status": "known", "label": "optional_user"}
    assert cockpit["schemaVersionStatus"] == "present"
    assert cockpit["observationBoundaryStatus"] == "present"
    assert cockpit["degradedStateShapeStatus"] == "present"
    assert cockpit["consumerSafeIssueLabelsStatus"] == "present"
    assert cockpit["synthesisContractStatus"] == "present"
    assert cockpit["gaps"] == []

    radar = _surface_by_key(payload, "research_radar")
    assert radar["status"] == "ready"
    assert radar["primaryRoute"]["method"] == "GET"
    assert radar["primaryRoute"]["path"] == "/api/v1/research/radar"
    assert radar["authRequirement"] == {"status": "known", "label": "authenticated_user"}
    assert radar["schemaVersionStatus"] == "present"
    assert radar["observationBoundaryStatus"] == "present"
    assert radar["degradedStateShapeStatus"] == "present"
    assert radar["consumerSafeIssueLabelsStatus"] == "present"
    assert radar["gaps"] == []

    market_overview = _surface_by_key(payload, "market_overview")
    assert market_overview["status"] == "ready"
    assert market_overview["routeStatus"] == "all_present"
    assert [item["path"] for item in market_overview["relatedRoutes"]] == [
        "/api/v1/market/market-briefing"
    ]

    scanner = _surface_by_key(payload, "scanner")
    assert scanner["status"] == "ready"
    assert scanner["consumerSafeIssueLabelsStatus"] == "present"
    assert scanner["observationBoundaryStatus"] == "present"
    assert scanner["degradedStateShapeStatus"] == "present"

    watchlist = _surface_by_key(payload, "watchlist")
    assert watchlist["status"] == "ready"
    assert watchlist["consumerSafeIssueLabelsStatus"] == "present"
    assert watchlist["observationBoundaryStatus"] == "present"
    assert watchlist["degradedStateShapeStatus"] == "present"

    stock_structure = _surface_by_key(payload, "stock_structure_decision")
    assert stock_structure["status"] == "ready"
    assert stock_structure["consumerSafeIssueLabelsStatus"] == "present"
    assert stock_structure["observationBoundaryStatus"] == "present"
    assert stock_structure["degradedStateShapeStatus"] == "present"

    options = _surface_by_key(payload, "options_gamma_observation")
    assert options["status"] == "ready_fixture_only"
    assert options["contract"] == "options_gamma_observation_contract_v1"
    assert options["implementationStatus"] == "fixture_only"
    assert options["consumerSafeIssueLabelsStatus"] in {"present", "unknown"}

    scenario_lab = _surface_by_key(payload, "scenario_lab")
    assert scenario_lab["status"] == "ready"
    assert scenario_lab["primaryRoute"]["method"] == "POST"
    assert scenario_lab["primaryRoute"]["path"] == "/api/v1/market/scenario-lab"

    _assert_no_sensitive_markers(payload)
    DatabaseManager.reset_instance()


def test_surface_readiness_keeps_missing_required_routes_blocked() -> None:
    payload = AdminSurfaceContractReadinessService().build_snapshot(routes=[])

    assert payload["summary"]["statusCounts"] == {"missing_contract": 10}
    assert all(surface["status"] == "missing_contract" for surface in payload["surfaces"])
    assert all(surface["primaryRoute"]["exists"] is False for surface in payload["surfaces"])
    assert all(surface["gaps"] == ["primary_route_missing"] for surface in payload["surfaces"])


def test_market_decision_cockpit_readiness_fails_closed_when_synthesis_contract_is_missing() -> None:
    for missing_field in COCKPIT_SYNTHESIS_FIELDS:
        fields = tuple(field for field in COCKPIT_REQUIRED_CONTRACT_FIELDS if field != missing_field)

        payload = _readiness_payload_for_cockpit_fields(fields)
        cockpit = _surface_by_key(payload, "market_decision_cockpit")

        assert cockpit["status"] == "degraded_contract"
        assert cockpit["contract"] == "market_decision_cockpit.v1"
        assert cockpit["schemaVersionStatus"] == "present"
        assert cockpit["observationBoundaryStatus"] == "present"
        assert cockpit["consumerSafeIssueLabelsStatus"] == "present"
        assert cockpit["synthesisContractStatus"] == "missing"
        assert "cockpit_synthesis_fields_missing" in cockpit["gaps"]
        assert payload["summary"]["statusCounts"] == {"degraded_contract": 1}


def test_market_decision_cockpit_readiness_accepts_either_degraded_inputs_or_surface_summary() -> None:
    fields_with_degraded_inputs = tuple(
        "degradedInputs" if field == "degradedSurfaceSummary" else field
        for field in COCKPIT_REQUIRED_CONTRACT_FIELDS
    )

    payload = _readiness_payload_for_cockpit_fields(fields_with_degraded_inputs)
    cockpit = _surface_by_key(payload, "market_decision_cockpit")

    assert cockpit["status"] == "ready"
    assert cockpit["degradedStateShapeStatus"] == "present"
    assert cockpit["contractStatus"] == "present"
    assert cockpit["gaps"] == []


def test_market_decision_cockpit_readiness_fails_closed_when_degraded_state_shape_is_missing() -> None:
    fields_without_degraded_shape = tuple(
        field
        for field in COCKPIT_REQUIRED_CONTRACT_FIELDS
        if field not in {"degradedInputs", "degradedSurfaceSummary"}
    )

    payload = _readiness_payload_for_cockpit_fields(fields_without_degraded_shape)
    cockpit = _surface_by_key(payload, "market_decision_cockpit")

    assert cockpit["status"] == "degraded_contract"
    assert cockpit["degradedStateShapeStatus"] == "missing"
    assert cockpit["contractStatus"] == "missing"
    assert "degraded_state_shape_missing" in cockpit["gaps"]
    assert "contract_fields_missing" in cockpit["gaps"]


def test_market_decision_cockpit_readiness_fails_closed_when_no_advice_boundary_is_missing() -> None:
    fields_without_no_advice = (
        "schemaVersion",
        "observationOnly",
        "decisionGrade",
        "consumerIssues",
        "degradedSurfaceSummary",
        "researchWorkflow",
        "crossSurfaceEvidence",
        "topResearchQuestions",
        "priorityDrilldowns",
        "evidenceConflicts",
        "nextObservationSteps",
    )

    payload = _readiness_payload_for_cockpit_fields(fields_without_no_advice)
    cockpit = _surface_by_key(payload, "market_decision_cockpit")

    assert cockpit["status"] == "degraded_contract"
    assert cockpit["contract"] == "market_decision_cockpit.v1"
    assert cockpit["schemaVersionStatus"] == "present"
    assert cockpit["observationBoundaryStatus"] == "missing"
    assert cockpit["synthesisContractStatus"] == "present"
    assert "observation_boundary_missing" in cockpit["gaps"]


def test_market_decision_cockpit_readiness_fails_closed_when_observation_decision_boundary_is_missing() -> None:
    for missing_field in ("observationOnly", "decisionGrade"):
        fields = tuple(field for field in COCKPIT_REQUIRED_CONTRACT_FIELDS if field != missing_field)

        payload = _readiness_payload_for_cockpit_fields(fields)
        cockpit = _surface_by_key(payload, "market_decision_cockpit")

        assert cockpit["status"] == "degraded_contract"
        assert cockpit["contract"] == "market_decision_cockpit.v1"
        assert cockpit["schemaVersionStatus"] == "present"
        assert cockpit["observationBoundaryStatus"] == "missing"
        assert cockpit["synthesisContractStatus"] == "present"
        assert "observation_boundary_missing" in cockpit["gaps"]


def test_market_decision_cockpit_readiness_fails_closed_when_schema_version_is_missing() -> None:
    fields_without_schema_version = (
        "noAdviceDisclosure",
        "observationOnly",
        "decisionGrade",
        "consumerIssues",
        "degradedSurfaceSummary",
        "researchWorkflow",
        "crossSurfaceEvidence",
        "topResearchQuestions",
        "priorityDrilldowns",
        "evidenceConflicts",
        "nextObservationSteps",
    )

    payload = _readiness_payload_for_cockpit_fields(fields_without_schema_version)
    cockpit = _surface_by_key(payload, "market_decision_cockpit")

    assert cockpit["status"] == "degraded_contract"
    assert cockpit["contract"] == "market_decision_cockpit.v1"
    assert cockpit["schemaVersionStatus"] == "missing"
    assert cockpit["observationBoundaryStatus"] == "present"
    assert cockpit["synthesisContractStatus"] == "present"
    assert "schema_version_missing" in cockpit["gaps"]
