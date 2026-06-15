# -*- coding: utf-8 -*-
"""API contract tests for the Market Scenario Lab endpoint."""

from __future__ import annotations

import copy
import json
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
        "baseRegime",
        "scenarioRegime",
        "confidenceDelta",
        "driverDeltas",
        "changedDrivers",
        "scenarioSummary",
        "whatWouldConfirm",
        "whatWouldInvalidate",
        "evidenceLimits",
        "noAdviceDisclosure",
    ]
    assert payload["schemaVersion"] == "market_scenario_lab_engine.v1"
    assert payload["baseRegime"]["regime"] == "riskOn"
    assert payload["scenarioRegime"]["regime"] in {"mixed", "riskOff", "downsideAccelerationRisk"}
    assert payload["confidenceDelta"] < 0
    assert payload["driverDeltas"]["volatilityStructure"] < 0
    assert payload["changedDrivers"] == [
        "breadthParticipation",
        "volatilityStructure",
        "crossAssetRisk",
    ]
    assert payload["noAdviceDisclosure"] == "Research planning only; not a personalized decision basis."

    serialized = _serialized_values(payload)
    for forbidden in FORBIDDEN_PUBLIC_TERMS:
        assert forbidden not in serialized


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
    assert payload["driverDeltas"] == {}
    assert payload["changedDrivers"] == []
    assert payload["scenarioSummary"] == [
        "Scenario lab is unavailable because base score-grade regime evidence is missing."
    ]
    assert payload["evidenceLimits"] == [
        "Base regime evidence is missing or below the minimum driver coverage for scenario analysis."
    ]


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
