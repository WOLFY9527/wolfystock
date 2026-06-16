# -*- coding: utf-8 -*-
"""API contract tests for the Market Scenario Lab endpoint."""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import market


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


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    return TestClient(app)


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


def test_market_scenario_lab_route_is_exposed() -> None:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    routes = {
        (method, route.path)
        for route in app.routes
        if hasattr(route, "methods")
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }

    assert ("POST", "/api/v1/market/scenario-lab") in routes


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
    assert payload["selectedScenario"] == {
        "name": "volatilitySpike",
        "label": "Volatility stress observation",
        "description": "Stress volatility and breadth inputs to compare research-context sensitivity.",
    }
    assert {item["name"] for item in payload["scenarioPresets"]} == {
        "volatilitySpike",
        "breadthBreakdown",
        "ratesUpDollarUp",
        "liquidityStress",
        "riskOnConfirmation",
        "gammaUnavailable",
    }
    assert payload["baseMarketContext"] == {
        "source": "decisionCockpitInput",
        "label": "Decision Cockpit market context",
        "message": "Base regime context was supplied by the request and is treated as observation-only evidence.",
        "evidenceState": "degraded",
        "scoringDriverCount": 6,
    }
    assert payload["baseRegime"]["regime"] == "riskOn"
    assert payload["scenarioRegime"]["regime"] in {"mixed", "riskOff", "downsideAccelerationRisk"}
    assert payload["scenarioOutput"]["scenarioRegime"] == payload["scenarioRegime"]
    assert payload["scenarioOutput"]["confidenceDelta"] == payload["confidenceDelta"]
    assert payload["scenarioOutput"]["driverDeltas"] == payload["driverDeltas"]
    assert payload["confirmInvalidateContext"] == {
        "confirm": payload["whatWouldConfirm"],
        "invalidate": payload["whatWouldInvalidate"],
    }
    assert payload["confidenceDelta"] < 0
    assert payload["driverDeltas"]["volatilityStructure"] < 0
    assert payload["changedDrivers"] == [
        "breadthParticipation",
        "volatilityStructure",
        "crossAssetRisk",
    ]
    assert payload["noAdviceDisclosure"] == "Research planning only; not a personalized decision basis."
    assert payload["consumerIssues"]

    serialized = _serialized_values(payload)
    for forbidden in FORBIDDEN_PUBLIC_TERMS:
        assert forbidden not in serialized
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
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert payload["selectedScenario"]["name"] == "liquidityStress"
    assert payload["driverDeltas"] == {}
    assert payload["changedDrivers"] == []
    assert payload["scenarioSummary"] == [
        "Scenario lab is unavailable because base score-grade regime evidence is missing."
    ]
    assert payload["evidenceLimits"] == [
        "Base regime evidence is missing or below the minimum driver coverage for scenario analysis."
    ]
    for label in _consumer_label_values(payload):
        assert not INTERNAL_LOOKING_TOKEN.search(label)


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
