# -*- coding: utf-8 -*-
"""API contract tests for the Market Scenario Lab endpoint."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import api.deps as api_deps
import api.middlewares.auth as auth_middleware
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app import create_app
from api.deps import CurrentUser, get_current_user, get_optional_current_user
from api.middlewares.auth import add_auth_middleware
from api.v1.endpoints import market
from src.repositories.scenario_baseline_snapshot_repository import ScenarioBaselineSnapshotStorageError
from src.storage import DatabaseManager, ScenarioBaselineSnapshotRow
from tests.api.route_table_helpers import iter_effective_api_routes


FORBIDDEN_PUBLIC_TERMS = (
    "buy",
    "sell",
    "hold",
    "recommendation",
    "recommended",
    "position",
    "target",
    "stop",
    "prediction",
    "predict",
    "forecast",
    "broker",
    "order",
    "trade",
    "backtest",
    "guaranteed",
    "交易建议",
    "投资建议",
    "买入",
    "卖出",
    "持有",
    "仓位",
    "目标价",
    "止损",
)
INTERNAL_LOOKING_TOKEN = re.compile(r"\b[a-z]+(?:_[a-z0-9]+){1,}\b")
EXPECTED_PRESET_IDS = [
    "volatilitySpike",
    "breadthBreakdown",
    "ratesUpDollarUp",
    "liquidityStress",
    "riskOnConfirmation",
    "gammaUnavailable",
]
EXPECTED_PRESET_KEYS = {
    "presetId",
    "name",
    "label",
    "category",
    "description",
    "inputAssumptions",
    "expectedDriverImpacts",
    "evidenceLimits",
    "confirmInvalidateContext",
    "linkedSurfaces",
    "consumerIssues",
    "noAdviceDisclosure",
    "observationOnly",
    "decisionGrade",
}
SAFE_DRILLDOWN_ROUTES = {
    "/market/decision-cockpit",
    "/market-overview",
    "/scenario-lab",
}
DURABLE_SCENARIO_BASELINE_ROUTE_SIGNATURES = {
    ("POST", "/api/v1/market/scenario-lab/baseline-snapshots"),
    ("GET", "/api/v1/market/scenario-lab/baseline-snapshots/latest"),
    ("GET", "/api/v1/market/scenario-lab/baseline-snapshots/{snapshot_id}"),
}
SCENARIO_EVALUATION_ROUTE_SIGNATURE = ("POST", "/api/v1/market/scenario-lab")


def _make_user(user_id: str, username: str = "scenario-user") -> CurrentUser:
    return CurrentUser(
        user_id=user_id,
        username=username,
        display_name=username,
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


def _client(
    *,
    snapshot_db_manager: DatabaseManager | None = None,
    current_user: CurrentUser | None = _make_user("scenario-member"),
) -> TestClient:
    app = FastAPI()
    if snapshot_db_manager is not None:
        app.state.scenario_baseline_snapshot_db_manager = snapshot_db_manager
    if current_user is not None:
        app.dependency_overrides[get_optional_current_user] = lambda: current_user
        app.dependency_overrides[get_current_user] = lambda: current_user
    app.include_router(market.router, prefix="/api/v1/market")
    return TestClient(app)


def _registered_route_signatures(route: Any) -> set[tuple[str, str]]:
    return {
        (method, route.path)
        for method in route.methods or set()
        if method not in {"HEAD", "OPTIONS"}
    }


def _route_dependency_calls(route: Any) -> list[object]:
    calls: list[object] = []
    pending = list(route.dependant.dependencies)
    while pending:
        dependency = pending.pop(0)
        call = getattr(dependency, "call", None)
        if call is not None:
            calls.append(call)
        pending.extend(getattr(dependency, "dependencies", []) or [])
    return calls


def _snapshot_db(tmp_path: Path, *, name: str = "scenario-api.sqlite") -> DatabaseManager:
    DatabaseManager.reset_instance()
    return DatabaseManager(db_url=f"sqlite:///{tmp_path / name}")


def _base_regime() -> dict[str, Any]:
    return {
        "schemaVersion": "market_regime_decision_engine.v1",
        "regime": "riskOn",
        "confidence": "medium",
        "confidenceScore": 0.68,
        "driverScores": {
            "dealerGamma": {"score": 0, "evidenceState": "unavailable"},
            "breadthParticipation": {"score": 58, "evidenceState": "score_grade"},
            "volatilityStructure": {"score": 72, "evidenceState": "score_grade"},
            "ratesDollar": {"score": 34, "evidenceState": "score_grade"},
            "liquidityCredit": {"score": 65, "evidenceState": "score_grade"},
            "crossAssetRisk": {"score": 28, "evidenceState": "score_grade"},
            "sectorThemeRotation": {"score": 52, "evidenceState": "score_grade"},
            "eventCatalyst": {"score": 0, "evidenceState": "unavailable"},
        },
        "dataQuality": {
            "availableDriverCount": 6,
            "scoringDriverCount": 6,
            "missingDriverCount": 2,
            "confidenceCapReasons": ["dealer_gamma_unavailable_caps_volatility_compression"],
        },
        "missingEvidence": ["dealerGamma:unavailable", "eventCatalyst:unavailable"],
    }


def _ready_base_regime() -> dict[str, Any]:
    base = copy.deepcopy(_base_regime())
    base.update(
        {
            "dataSourceClass": "cached",
            "sourceAuthorityAllowed": True,
            "generatedAt": "2026-06-15T09:30:00Z",
            "baselineSnapshot": {
                "state": "available",
                "asOf": "2026-06-15T09:30:00Z",
                "available": True,
            },
            "marketFrame": {
                "state": "available",
                "asOf": "2026-06-15T09:30:00Z",
                "available": True,
            },
            "dataQuality": {
                "availableDriverCount": 8,
                "scoringDriverCount": 8,
                "missingDriverCount": 0,
                "sourceAuthorityAllowed": True,
                "scoreAuthorityAllowed": True,
                "confidenceCapReasons": [],
            },
            "missingEvidence": [],
        }
    )
    for driver in base["driverScores"].values():
        driver["evidenceState"] = "score_grade"
        driver["score"] = driver["score"] or 15
    return base


def _baseline_snapshot_create_payload(snapshot_id: str = "baseline-api-durable") -> dict[str, Any]:
    return {
        "snapshotId": snapshot_id,
        "scope": {"type": "market", "value": "US"},
        "createdAt": "2026-07-07T09:31:00Z",
        "asOf": "2026-07-07T09:30:00Z",
        "source": {
            "dataState": "real_cached",
            "freshness": "fresh",
            "asOf": "2026-07-07T09:30:00Z",
            "sourceAuthorityAllowed": True,
        },
        "categories": {
            "price": {"state": "available"},
            "marketRegime": {"state": "available"},
            "volatility": {"state": "available"},
            "flowPositioning": {"state": "available"},
            "optionsGreeks": {"state": "available"},
        },
        "inputSnapshotRefs": ["market-overview:2026-07-07T09:30:00Z"],
        "sourceAuthoritySummary": {
            "state": "authoritative",
            "allowed": True,
            "reasonCodes": ["target_environment_evidence_present"],
        },
        "freshnessSummary": {
            "state": "fresh",
            "asOf": "2026-07-07T09:30:00Z",
        },
        "targetEnvironmentEvidence": {
            "state": "present",
            "evidenceRefs": ["uat-runtime:scenario-baseline"],
        },
    }


def _not_available_baseline_snapshot_create_payload(
    snapshot_id: str = "baseline-api-not-available",
) -> dict[str, Any]:
    payload = _baseline_snapshot_create_payload(snapshot_id)
    payload.pop("snapshotId")
    payload.pop("createdAt")
    payload.pop("asOf")
    payload["source"] = {
        "dataState": "unavailable",
        "freshness": "unavailable",
        "asOf": "2026-07-07T09:30:00Z",
        "sourceAuthorityAllowed": False,
    }
    payload["categories"] = {
        "price": {"state": "missing"},
        "marketRegime": {"state": "missing"},
        "volatility": {"state": "missing"},
        "flowPositioning": {"state": "missing"},
        "optionsGreeks": {"state": "missing"},
    }
    payload["inputSnapshotRefs"] = ["market-overview:missing:2026-07-07T09:30:00Z"]
    payload["sourceAuthoritySummary"] = {
        "state": "unavailable",
        "allowed": False,
        "reasonCodes": ["source_authority_unavailable"],
    }
    payload["freshnessSummary"] = {
        "state": "unavailable",
        "asOf": "2026-07-07T09:30:00Z",
    }
    payload["missingInputList"] = ["market_price", "market_regime", "volatility", "market_flow", "options_greeks"]
    payload["targetEnvironmentEvidence"] = {"state": "missing", "evidenceRefs": []}
    return payload


def test_market_scenario_lab_durable_baseline_route_metadata_requires_current_user(
    tmp_path: Path,
) -> None:
    app = create_app(static_dir=tmp_path / "static")
    scenario_routes = {
        signature: route
        for route in iter_effective_api_routes(app.routes)
        for signature in _registered_route_signatures(route)
        if signature[1].startswith("/api/v1/market/scenario-lab")
    }
    baseline_route_signatures = {
        signature
        for signature in scenario_routes
        if signature[1].startswith("/api/v1/market/scenario-lab/baseline-snapshots")
    }

    durable_routes = {
        signature: scenario_routes[signature]
        for signature in DURABLE_SCENARIO_BASELINE_ROUTE_SIGNATURES
        if signature in scenario_routes
    }

    assert baseline_route_signatures == DURABLE_SCENARIO_BASELINE_ROUTE_SIGNATURES
    assert set(durable_routes) == DURABLE_SCENARIO_BASELINE_ROUTE_SIGNATURES
    assert SCENARIO_EVALUATION_ROUTE_SIGNATURE in scenario_routes
    assert SCENARIO_EVALUATION_ROUTE_SIGNATURE not in durable_routes

    for signature, route in durable_routes.items():
        dependency_calls = _route_dependency_calls(route)
        assert get_current_user in dependency_calls, signature
        assert get_optional_current_user not in dependency_calls, signature

    evaluation_dependency_calls = _route_dependency_calls(scenario_routes[SCENARIO_EVALUATION_ROUTE_SIGNATURE])
    assert get_current_user in evaluation_dependency_calls
    assert get_optional_current_user not in evaluation_dependency_calls


def _serialized_values(payload: object) -> str:
    values: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, str):
            values.append(value)
            return
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload)
    return json.dumps(values, ensure_ascii=False, sort_keys=True).lower()


def _consumer_label_values(payload: object) -> list[str]:
    values: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized_key = str(key).lower()
                if isinstance(item, str) and ("label" in normalized_key or "message" in normalized_key):
                    values.append(item)
                visit(item)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload)
    return values


def _consumer_text_values(payload: object) -> list[str]:
    text_keys = {
        "label",
        "category",
        "description",
        "message",
        "reason",
        "driver",
        "direction",
        "magnitude",
        "noAdviceDisclosure",
    }
    list_text_keys = {
        "inputAssumptions",
        "evidenceLimits",
        "confirm",
        "invalidate",
        "scenarioSummary",
        "whatWouldConfirm",
        "whatWouldInvalidate",
    }
    values: list[str] = []

    def visit(value: object, key: str = "") -> None:
        if isinstance(value, dict):
            for item_key, item in value.items():
                visit(item, str(item_key))
            return
        if isinstance(value, list):
            for item in value:
                visit(item, key)
            return
        if isinstance(value, str) and (key in text_keys or key in list_text_keys):
            values.append(value)

    visit(payload)
    return values


def _assert_safe_consumer_text(payload: object) -> None:
    serialized = _serialized_values(payload)
    for forbidden in FORBIDDEN_PUBLIC_TERMS:
        assert forbidden not in serialized
    for value in _consumer_text_values(payload):
        assert not INTERNAL_LOOKING_TOKEN.search(value)


def _assert_confirm_invalidate_context(context: dict[str, Any]) -> None:
    assert set(context) == {"status", "message", "confirm", "invalidate"}
    assert context["status"] in {"available", "unavailable"}
    assert isinstance(context["message"], str)
    if context["status"] == "available":
        assert context["confirm"]
        assert context["invalidate"]
    else:
        assert context["confirm"] == []
        assert context["invalidate"] == []


def _assert_fixture_response(payload: dict[str, Any], scenario_name: str) -> None:
    assert payload["selectedScenario"]["presetId"] == scenario_name
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert payload["sourceClass"] == "fixture"
    assert payload["dataSourceClass"] == "fixture"
    assert payload["baseMarketContext"]["source"] == "scenarioFixture"
    assert payload["scenarioRegime"].get("status") != "unavailable"
    assert payload["driverDeltas"]
    assert payload["changedDrivers"]
    assert any("sample fixture" in item.lower() for item in payload["evidenceLimits"])
    serialized_issues = json.dumps(payload["consumerIssues"], ensure_ascii=False).lower()
    assert "proxy_or_sample_evidence_present" not in serialized_issues
    assert "sample" in serialized_issues
    _assert_safe_consumer_text(payload)


def _assert_preset_contract(preset: dict[str, Any]) -> None:
    assert set(preset) == EXPECTED_PRESET_KEYS
    assert preset["presetId"] == preset["name"]
    assert preset["presetId"] in EXPECTED_PRESET_IDS
    assert preset["label"]
    assert preset["category"]
    assert preset["description"]
    assert preset["inputAssumptions"]
    assert preset["evidenceLimits"]
    assert preset["noAdviceDisclosure"] == "Research planning only; not a personalized decision basis."
    assert preset["observationOnly"] is True
    assert preset["decisionGrade"] is False
    _assert_confirm_invalidate_context(preset["confirmInvalidateContext"])

    for impact in preset["expectedDriverImpacts"]:
        assert set(impact) == {"driver", "direction", "magnitude"}
        assert impact["driver"]
        assert impact["direction"] in {"pressure", "supportive", "unchanged"}
        assert impact["magnitude"] in {"low", "medium", "high"}

    assert preset["linkedSurfaces"]
    for link in preset["linkedSurfaces"]:
        assert set(link) == {"label", "route", "section", "reason"}
        assert link["route"] in SAFE_DRILLDOWN_ROUTES
        assert not link["route"].startswith("/api/")

    for issue in preset["consumerIssues"]:
        assert set(issue) == {"label", "message", "severity", "category"}

    _assert_safe_consumer_text(preset)


def test_market_scenario_lab_route_is_exposed() -> None:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    routes = {
        (method, route.path)
        for route in market.router.routes
        if hasattr(route, "methods")
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }

    assert [route for route in routes if route == ("POST", "/scenario-lab")] == [
        ("POST", "/scenario-lab")
    ]


def test_market_scenario_lab_accepts_base_regime_and_named_scenario_without_mutating_request() -> None:
    request_payload = {
        "baseRegime": _base_regime(),
        "scenarioName": "volatilitySpike",
    }
    original_payload = copy.deepcopy(request_payload)

    response = _client().post("/api/v1/market/scenario-lab", json=request_payload)

    assert response.status_code == 200
    assert request_payload == original_payload
    payload = response.json()
    assert list(payload.keys()) == [
        "schemaVersion",
        "contractStatus",
        "observationOnly",
        "decisionGrade",
        "selectedScenario",
        "scenarioPresets",
        "baseMarketContext",
        "baselineReadiness",
        "scenarioBaselineSnapshot",
        "baseRegime",
        "scenarioRegime",
        "scenarioOutput",
        "confidenceDelta",
        "driverDeltas",
        "changedDrivers",
        "scenarioSummary",
        "confirmInvalidateContext",
        "whatWouldConfirm",
        "whatWouldInvalidate",
        "evidenceLimits",
        "consumerIssues",
        "noAdviceDisclosure",
    ]
    assert payload["schemaVersion"] == "market_scenario_lab_engine.v1"
    assert payload["contractStatus"] == {
        "state": "degraded",
        "label": "Scenario constrained by evidence gaps",
        "message": "Scenario comparison is available, but incomplete evidence keeps the result observation-only.",
        "observationOnly": True,
        "decisionGrade": False,
    }
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert payload["selectedScenario"]["presetId"] == "volatilitySpike"
    assert payload["selectedScenario"]["label"] == "Volatility stress observation"
    _assert_preset_contract(payload["selectedScenario"])
    assert [item["presetId"] for item in payload["scenarioPresets"]] == EXPECTED_PRESET_IDS
    for preset in payload["scenarioPresets"]:
        _assert_preset_contract(preset)
    assert payload["baseMarketContext"] == {
        "source": "decisionCockpitInput",
        "label": "Decision Cockpit market context",
        "message": "Base regime context was supplied by the request and is treated as observation-only evidence.",
        "evidenceState": "degraded",
        "scoringDriverCount": 6,
    }
    assert payload["baselineReadiness"]["status"] == "blocked"
    assert payload["baselineReadiness"]["baselineSnapshot"]["state"] == "missing"
    assert payload["baselineReadiness"]["marketFrame"]["state"] == "available"
    assert payload["baselineReadiness"]["driverInputs"]["state"] == "partial"
    assert payload["baselineReadiness"]["dataState"] == "request_supplied"
    assert payload["baselineReadiness"]["scoreAuthority"] == "observation_only"
    assert payload["baselineReadiness"]["observationOnly"] is True
    assert payload["scenarioBaselineSnapshot"]["status"] == "not_available"
    assert payload["scenarioBaselineSnapshot"]["reasonCode"] == "baseline_missing"
    assert payload["baseRegime"]["regime"] == "riskOn"
    assert payload["scenarioRegime"]["regime"] in {"mixed", "riskOff", "downsideAccelerationRisk"}
    assert payload["scenarioOutput"]["scenarioRegime"] == payload["scenarioRegime"]
    assert payload["scenarioOutput"]["confidenceDelta"] == payload["confidenceDelta"]
    assert payload["scenarioOutput"]["driverDeltas"] == payload["driverDeltas"]
    assert payload["confirmInvalidateContext"]["status"] == "available"
    assert payload["confirmInvalidateContext"]["confirm"] == payload["whatWouldConfirm"]
    assert payload["confirmInvalidateContext"]["invalidate"] == payload["whatWouldInvalidate"]
    assert payload["confidenceDelta"] < 0
    assert payload["driverDeltas"]["volatilityStructure"] < 0
    assert payload["changedDrivers"] == [
        "breadthParticipation",
        "volatilityStructure",
        "crossAssetRisk",
    ]
    assert payload["noAdviceDisclosure"] == "Research planning only; not a personalized decision basis."
    assert payload["consumerIssues"]

    _assert_safe_consumer_text(payload)
    for label in _consumer_label_values(payload):
        assert not INTERNAL_LOOKING_TOKEN.search(label)


def test_market_scenario_lab_accepts_normalized_driver_scores_and_overrides() -> None:
    response = _client().post(
        "/api/v1/market/scenario-lab",
        json={
            "driverScores": {
                "breadthParticipation": 62,
                "volatilityStructure": 48,
                "ratesDollar": 34,
                "liquidityCredit": 57,
                "crossAssetRisk": 36,
                "sectorThemeRotation": 42,
            },
            "scenarioName": "riskOnConfirmation",
            "scenarioOverrides": {
                "breadthShock": -55,
                "ratesDollarShock": -45,
                "liquidityShock": -30,
                "gammaEvidenceStatus": "unavailable",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["baseRegime"]["regime"] == "riskOn"
    assert payload["driverDeltas"]["breadthParticipation"] == -55
    assert payload["driverDeltas"]["ratesDollar"] == -45
    assert payload["driverDeltas"]["liquidityCredit"] == -30
    assert payload["driverDeltas"]["crossAssetRisk"] == 25
    assert "Gamma evidence status is unavailable, so gamma-sensitive conclusions remain capped." in payload[
        "evidenceLimits"
    ]
    assert "dealer_gamma_unavailable_caps_volatility_compression" not in payload["evidenceLimits"]
    assert all(not INTERNAL_LOOKING_TOKEN.search(item) for item in payload["evidenceLimits"])


def test_market_scenario_lab_fails_closed_when_required_base_evidence_is_missing() -> None:
    response = _client().post(
        "/api/v1/market/scenario-lab",
        json={"scenarioName": "liquidityStress"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["baseRegime"] == {"regime": "lowConfidence", "confidence": "low", "confidenceScore": 0.0}
    assert payload["scenarioRegime"] == {
        "regime": "lowConfidence",
        "confidence": "low",
        "confidenceScore": 0.0,
        "status": "unavailable",
    }
    assert payload["contractStatus"] == {
        "state": "unavailable",
        "label": "Scenario unavailable",
        "message": "Scenario lab needs at least three score-grade market drivers before comparing scenarios.",
        "observationOnly": True,
        "decisionGrade": False,
    }
    assert payload["baselineReadiness"]["status"] == "blocked"
    assert payload["baselineReadiness"]["baselineSnapshot"]["state"] == "missing"
    assert payload["baselineReadiness"]["marketFrame"]["state"] == "missing"
    assert payload["baselineReadiness"]["driverInputs"]["state"] == "missing"
    assert payload["baselineReadiness"]["dataState"] == "unavailable"
    assert payload["baselineReadiness"]["scoreAuthority"] == "observation_only"
    assert payload["scenarioBaselineSnapshot"]["status"] == "not_available"
    assert payload["scenarioBaselineSnapshot"]["reasonCode"] == "baseline_missing"
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert payload["selectedScenario"]["name"] == "liquidityStress"
    assert payload["driverDeltas"] == {}
    assert payload["changedDrivers"] == []
    assert "sourceClass" not in payload
    assert "dataSourceClass" not in payload
    assert payload["scenarioSummary"] == [
        "Scenario lab is unavailable because base score-grade regime evidence is missing."
    ]
    assert payload["evidenceLimits"] == [
        "Base regime evidence is missing or below the minimum driver coverage for scenario analysis."
    ]
    assert payload["confirmInvalidateContext"] == {
        "status": "unavailable",
        "message": (
            "Confirm and invalidate context is unavailable until base score-grade evidence reaches minimum coverage."
        ),
        "confirm": [],
        "invalidate": [],
    }
    assert payload["selectedScenario"]["presetId"] == "liquidityStress"
    _assert_preset_contract(payload["selectedScenario"])
    for label in _consumer_label_values(payload):
        assert not INTERNAL_LOOKING_TOKEN.search(label)


def test_market_scenario_lab_fixture_path_runs_volatility_spike_observation() -> None:
    response = _client().post(
        "/api/v1/market/scenario-lab",
        json={
            "scenarioName": "volatilitySpike",
            "scenarioOverrides": {"dataSourceClass": "fixture"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    _assert_fixture_response(payload, "volatilitySpike")
    assert payload["baselineReadiness"]["status"] == "blocked"
    assert payload["baselineReadiness"]["dataState"] == "demo_static_sample"
    assert payload["baselineReadiness"]["sampleState"] == "fixture"
    assert payload["baselineReadiness"]["scoreAuthority"] == "observation_only"
    assert payload["confidenceDelta"] < 0
    assert payload["driverDeltas"]["volatilityStructure"] < 0


def test_market_scenario_lab_fixture_path_runs_risk_on_confirmation_observation() -> None:
    response = _client().post(
        "/api/v1/market/scenario-lab",
        json={
            "scenarioName": "riskOnConfirmation",
            "scenarioOverrides": {"sourceClass": "sample"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    _assert_fixture_response(payload, "riskOnConfirmation")
    assert payload["baselineReadiness"]["dataState"] == "demo_static_sample"
    assert payload["baselineReadiness"]["sampleState"] == "sample"
    assert payload["driverDeltas"]["breadthParticipation"] > 0
    assert payload["driverDeltas"]["liquidityCredit"] > 0


def test_market_scenario_lab_exposes_authoritative_readiness_for_complete_cached_baseline() -> None:
    response = _client().post(
        "/api/v1/market/scenario-lab",
        json={
            "baseRegime": _ready_base_regime(),
            "scenarioName": "riskOnConfirmation",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    readiness = payload["baselineReadiness"]
    assert readiness["status"] == "ready"
    assert readiness["baselineSnapshot"]["state"] == "available"
    assert readiness["marketFrame"]["state"] == "available"
    assert readiness["driverInputs"]["state"] == "available"
    assert readiness["evidenceCompleteness"] == {"state": "ready", "gaps": []}
    assert readiness["dataState"] == "real_cached"
    assert readiness["scoreAuthority"] == "authoritative"
    assert readiness["authoritative"] is True
    assert readiness["observationOnly"] is False
    assert readiness["lastUpdated"] == "2026-06-15T09:30:00Z"


def test_market_scenario_lab_marks_stale_baseline_readiness_as_partial() -> None:
    base = _ready_base_regime()
    base["baselineSnapshot"]["state"] = "stale"
    base["baselineSnapshot"]["isStale"] = True

    response = _client().post(
        "/api/v1/market/scenario-lab",
        json={
            "baseRegime": base,
            "scenarioName": "liquidityStress",
        },
    )

    assert response.status_code == 200
    readiness = response.json()["baselineReadiness"]
    assert readiness["status"] == "partial"
    assert readiness["baselineSnapshot"]["state"] == "stale"
    assert readiness["evidenceCompleteness"]["state"] == "partial"
    assert readiness["scoreAuthority"] == "observation_only"
    assert "baselineSnapshot" in readiness["affectedBaselineComponents"]


def test_market_scenario_lab_exposes_consumer_safe_baseline_snapshot_without_internal_markers() -> None:
    base = _ready_base_regime()
    base["scenarioBaselineSnapshot"] = {
        "snapshotId": "baseline-api-redaction",
        "scope": {"type": "symbol", "value": "MSFT"},
        "createdAt": "2026-06-15T09:30:00Z",
        "source": {
            "providerClass": "InternalProvider",
            "providerName": "secret-provider",
            "apiKey": "secret",
            "env": "LOCAL_ENV",
            "token": "secret-token",
            "credential": "secret-credential",
            "requestId": "req-1",
            "traceId": "trace-1",
            "cacheKey": "cache-key",
            "rawPayload": {"price": 123.45},
            "exceptionClass": "ProviderError",
            "exceptionChain": ["boom"],
            "freshness": "fresh",
        },
        "categories": {
            "price": {"state": "available"},
            "volatility": {"state": "degraded"},
        },
        "labels": ["providerName must not leak", "Safe baseline"],
        "notes": "traceId providerClass rawPayload token must not leak.",
    }

    response = _client().post(
        "/api/v1/market/scenario-lab",
        json={
            "baseRegime": base,
            "scenarioName": "riskOnConfirmation",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    snapshot = payload["scenarioBaselineSnapshot"]
    assert snapshot["snapshotId"] == "baseline-api-redaction"
    assert snapshot["scope"] == {"type": "symbol", "value": "MSFT"}
    assert snapshot["availableDataCategories"] == ["market_price"]
    assert snapshot["degradedDataCategories"] == ["volatility"]
    assert snapshot["labels"] == ["Safe baseline"]
    assert snapshot["notes"] == "Baseline snapshot note omitted."
    serialized = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
    for marker in (
        "providerClass",
        "providerName",
        "apiKey",
        "env",
        "token",
        "credential",
        "requestId",
        "traceId",
        "cacheKey",
        "rawPayload",
        "exceptionClass",
        "exceptionChain",
    ):
        assert marker not in serialized
        assert marker.lower() not in serialized.lower()


def test_market_scenario_lab_baseline_snapshot_create_and_readback_are_explicit_and_owner_scoped(
    tmp_path: Path,
) -> None:
    db = _snapshot_db(tmp_path)
    client = _client(snapshot_db_manager=db, current_user=_make_user("user-a", "alice"))

    create_response = client.post(
        "/api/v1/market/scenario-lab/baseline-snapshots",
        json=_baseline_snapshot_create_payload(),
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["snapshotId"] == "baseline-api-durable"
    assert created["ownerScope"] == {"type": "user", "value": "user-a"}
    assert created["status"] == "available"
    assert created["readinessState"] == "ready"
    assert created["observationOnly"] is False
    assert created["contentHash"].startswith("sha256:")

    latest_response = client.get(
        "/api/v1/market/scenario-lab/baseline-snapshots/latest",
        params={"scopeType": "market", "scopeValue": "US"},
    )
    by_id_response = client.get("/api/v1/market/scenario-lab/baseline-snapshots/baseline-api-durable")

    assert latest_response.status_code == 200
    assert by_id_response.status_code == 200
    assert latest_response.json() == created
    assert by_id_response.json() == created

    other_user = _client(snapshot_db_manager=db, current_user=_make_user("user-b", "bob"))
    other_user_read = other_user.get("/api/v1/market/scenario-lab/baseline-snapshots/baseline-api-durable")
    assert other_user_read.status_code == 404
    other_user_latest = other_user.get(
        "/api/v1/market/scenario-lab/baseline-snapshots/latest",
        params={"scopeType": "market", "scopeValue": "US"},
    )
    assert other_user_latest.status_code == 200
    assert other_user_latest.json()["status"] == "not_available"
    assert other_user_latest.json()["ownerScope"] == {"type": "user", "value": "user-b"}


def test_market_scenario_lab_baseline_snapshot_requires_current_user_without_middleware(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db = _snapshot_db(tmp_path)
    monkeypatch.setattr(api_deps, "is_auth_enabled", lambda: True)
    client = _client(snapshot_db_manager=db, current_user=None)

    create_response = client.post(
        "/api/v1/market/scenario-lab/baseline-snapshots",
        json=_baseline_snapshot_create_payload("baseline-api-auth-required"),
    )
    latest_response = client.get(
        "/api/v1/market/scenario-lab/baseline-snapshots/latest",
        params={"scopeType": "market", "scopeValue": "US"},
    )
    by_id_response = client.get(
        "/api/v1/market/scenario-lab/baseline-snapshots/baseline-api-auth-required",
    )

    assert create_response.status_code == 401
    assert latest_response.status_code == 401
    assert by_id_response.status_code == 401
    assert create_response.json()["detail"]["error"] == "unauthorized"
    assert latest_response.json()["detail"]["error"] == "unauthorized"
    assert by_id_response.json()["detail"]["error"] == "unauthorized"
    with db.get_session() as session:
        assert session.query(ScenarioBaselineSnapshotRow).count() == 0


def test_market_scenario_lab_baseline_snapshot_auth_enabled_anonymous_rejected_by_app_middleware(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db = _snapshot_db(tmp_path)
    monkeypatch.setattr(api_deps, "is_auth_enabled", lambda: True)
    monkeypatch.setattr(auth_middleware, "is_auth_enabled", lambda: True)
    app = FastAPI()
    app.state.scenario_baseline_snapshot_db_manager = db
    app.include_router(market.router, prefix="/api/v1/market")
    add_auth_middleware(app)
    client = TestClient(app)

    create_response = client.post(
        "/api/v1/market/scenario-lab/baseline-snapshots",
        json=_baseline_snapshot_create_payload("baseline-api-middleware-auth-required"),
    )
    latest_response = client.get(
        "/api/v1/market/scenario-lab/baseline-snapshots/latest",
        params={"scopeType": "market", "scopeValue": "US"},
    )

    assert create_response.status_code == 401
    assert latest_response.status_code == 401
    assert create_response.json()["error"] == "unauthorized"
    assert latest_response.json()["error"] == "unauthorized"
    with db.get_session() as session:
        assert session.query(ScenarioBaselineSnapshotRow).count() == 0


def test_market_scenario_lab_baseline_snapshot_auth_disabled_uses_bootstrap_owner(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db = _snapshot_db(tmp_path)
    monkeypatch.setattr(api_deps, "is_auth_enabled", lambda: False)
    client = _client(snapshot_db_manager=db, current_user=None)

    create_response = client.post(
        "/api/v1/market/scenario-lab/baseline-snapshots",
        json=_baseline_snapshot_create_payload("baseline-api-local-compat"),
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["ownerScope"] == {"type": "user", "value": db.get_default_owner_id()}
    assert created["ownerScope"]["value"] != "anonymous"

    latest_response = client.get(
        "/api/v1/market/scenario-lab/baseline-snapshots/latest",
        params={"scopeType": "market", "scopeValue": "US"},
    )
    by_id_response = client.get("/api/v1/market/scenario-lab/baseline-snapshots/baseline-api-local-compat")

    assert latest_response.status_code == 200
    assert by_id_response.status_code == 200
    assert latest_response.json() == created
    assert by_id_response.json() == created


def test_market_scenario_lab_durable_create_idempotent_retry_conflict_is_409_and_non_destructive(
    tmp_path: Path,
) -> None:
    db = _snapshot_db(tmp_path)
    client = _client(snapshot_db_manager=db, current_user=_make_user("user-a", "alice"))
    original_payload = _baseline_snapshot_create_payload("baseline-api-idempotency")

    create_response = client.post(
        "/api/v1/market/scenario-lab/baseline-snapshots",
        json=original_payload,
    )
    retry_response = client.post(
        "/api/v1/market/scenario-lab/baseline-snapshots",
        json=original_payload,
    )

    assert create_response.status_code == 200
    assert retry_response.status_code == 200
    created = create_response.json()
    assert retry_response.json() == created

    conflicting_payload = copy.deepcopy(original_payload)
    conflicting_payload["asOf"] = "2026-07-07T09:45:00Z"
    conflicting_payload["source"]["asOf"] = "2026-07-07T09:45:00Z"
    conflicting_response = client.post(
        "/api/v1/market/scenario-lab/baseline-snapshots",
        json=conflicting_payload,
    )

    assert conflicting_response.status_code == 409
    assert conflicting_response.json()["detail"]["error"] == "scenario_baseline_snapshot_conflict"

    by_id_response = client.get("/api/v1/market/scenario-lab/baseline-snapshots/baseline-api-idempotency")
    latest_response = client.get(
        "/api/v1/market/scenario-lab/baseline-snapshots/latest",
        params={"scopeType": "market", "scopeValue": "US"},
    )
    assert by_id_response.status_code == 200
    assert latest_response.status_code == 200
    assert by_id_response.json() == created
    assert latest_response.json() == created

    with db.get_session() as session:
        rows = session.query(ScenarioBaselineSnapshotRow).all()
    assert len(rows) == 1
    assert rows[0].snapshot_id == "baseline-api-idempotency"
    assert rows[0].content_hash == created["contentHash"]


def test_market_scenario_lab_durable_create_preserves_domain_not_available_without_storage_500(
    tmp_path: Path,
) -> None:
    db = _snapshot_db(tmp_path)
    client = _client(snapshot_db_manager=db, current_user=_make_user("user-a", "alice"))

    create_response = client.post(
        "/api/v1/market/scenario-lab/baseline-snapshots",
        json=_not_available_baseline_snapshot_create_payload(),
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["snapshotId"].startswith("scenario-baseline-")
    assert created["status"] == "not_available"
    assert created["reasonCode"] == "baseline_missing"
    assert created["readinessState"] == "not_available"
    assert created["ownerScope"] == {"type": "user", "value": "user-a"}
    assert created["contentHash"].startswith("sha256:")

    latest_response = client.get(
        "/api/v1/market/scenario-lab/baseline-snapshots/latest",
        params={"scopeType": "market", "scopeValue": "US"},
    )
    by_id_response = client.get(f"/api/v1/market/scenario-lab/baseline-snapshots/{created['snapshotId']}")

    assert latest_response.status_code == 200
    assert by_id_response.status_code == 200
    assert latest_response.json() == created
    assert by_id_response.json() == created


def test_market_scenario_lab_durable_create_maps_domain_validation_distinct_from_storage_failure(
    tmp_path: Path,
) -> None:
    db = _snapshot_db(tmp_path)
    client = _client(snapshot_db_manager=db, current_user=_make_user("user-a", "alice"))
    invalid_domain_payload = _baseline_snapshot_create_payload("baseline-api-domain-invalid")
    invalid_domain_payload["inputSnapshotRefs"] = []

    domain_response = client.post(
        "/api/v1/market/scenario-lab/baseline-snapshots",
        json=invalid_domain_payload,
    )

    assert domain_response.status_code == 422
    assert domain_response.json()["detail"]["error"] == "scenario_baseline_snapshot_invalid"

    class FailingRepository:
        def upsert_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
            raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_database_write_failed")

    app = FastAPI()
    app.state.scenario_baseline_snapshot_repository = FailingRepository()
    app.dependency_overrides[get_optional_current_user] = lambda: _make_user("user-a", "alice")
    app.dependency_overrides[get_current_user] = lambda: _make_user("user-a", "alice")
    app.include_router(market.router, prefix="/api/v1/market")
    storage_response = TestClient(app).post(
        "/api/v1/market/scenario-lab/baseline-snapshots",
        json=_baseline_snapshot_create_payload("baseline-api-storage-failure"),
    )

    assert storage_response.status_code == 500
    assert storage_response.status_code not in {409, 422}
    storage_payload = storage_response.json()
    assert storage_payload["detail"]["error"] == "scenario_baseline_snapshot_storage_unavailable"
    assert "snapshotId" not in storage_payload
    assert "contentHash" not in storage_payload
    assert "contentVersionRef" not in storage_payload


def test_market_scenario_lab_evaluation_does_not_persist_request_supplied_baseline(tmp_path: Path) -> None:
    db = _snapshot_db(tmp_path)
    client = _client(snapshot_db_manager=db, current_user=_make_user("user-a", "alice"))
    base = _ready_base_regime()
    base["scenarioBaselineSnapshot"] = _baseline_snapshot_create_payload("request-supplied-only")

    response = client.post(
        "/api/v1/market/scenario-lab",
        json={"baseRegime": base, "scenarioName": "riskOnConfirmation"},
    )

    assert response.status_code == 200
    assert response.json()["scenarioBaselineSnapshot"]["snapshotId"] == "request-supplied-only"

    latest_response = client.get(
        "/api/v1/market/scenario-lab/baseline-snapshots/latest",
        params={"scopeType": "market", "scopeValue": "US"},
    )
    assert latest_response.status_code == 200
    assert latest_response.json()["status"] == "not_available"


def test_market_scenario_lab_rejects_unsupported_named_scenario() -> None:
    response = _client().post(
        "/api/v1/market/scenario-lab",
        json={
            "driverScores": {
                "breadthParticipation": 62,
                "volatilityStructure": 48,
                "ratesDollar": 34,
            },
            "scenarioName": "tomorrowPrediction",
        },
    )

    assert response.status_code == 422
