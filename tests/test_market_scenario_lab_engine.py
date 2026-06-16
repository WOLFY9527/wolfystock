# -*- coding: utf-8 -*-
"""Contract tests for the deterministic market scenario lab engine."""

from __future__ import annotations

import ast
import copy
import json
import re
from pathlib import Path
from typing import Any

from src.services.market_scenario_lab_engine import build_market_scenario_lab


REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PUBLIC_TERMS = (
    "buy",
    "sell",
    "hold",
    "position",
    "target",
    "stop",
    "prediction",
    "predict",
    "forecast",
    "will happen",
    "will change",
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
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "src.providers",
    "src.services.market_cache",
    "src.services.market_scanner_service",
    "src.services.watchlist_service",
    "src.services.portfolio",
    "api.deps",
    "src.auth",
)


def _base_decision() -> dict[str, Any]:
    return {
        "schemaVersion": "market_regime_decision_engine.v1",
        "regime": "riskOn",
        "confidence": "medium",
        "confidenceScore": 0.68,
        "driverScores": {
            "dealerGamma": {
                "score": 0,
                "evidenceState": "unavailable",
                "reasons": ["live_gex_not_implemented_v1"],
                "evidenceCount": 0,
                "observations": [],
            },
            "breadthParticipation": {
                "score": 58,
                "evidenceState": "score_grade",
                "reasons": [],
                "evidenceCount": 1,
                "observations": ["ADV_RATIO value=66 change=3"],
            },
            "volatilityStructure": {
                "score": 72,
                "evidenceState": "score_grade",
                "reasons": [],
                "evidenceCount": 1,
                "observations": ["VIX value=14 change=-6"],
            },
            "ratesDollar": {
                "score": 34,
                "evidenceState": "score_grade",
                "reasons": [],
                "evidenceCount": 2,
                "observations": ["US10Y value=4.16 change=-1", "DXY value=101.8 change=-0.4"],
            },
            "liquidityCredit": {
                "score": 65,
                "evidenceState": "score_grade",
                "reasons": [],
                "evidenceCount": 1,
                "observations": ["capitalFlowSignal=growth_ai_software_semis"],
            },
            "crossAssetRisk": {
                "score": 28,
                "evidenceState": "score_grade",
                "reasons": [],
                "evidenceCount": 1,
                "observations": ["ES value=5400 change=0.7"],
            },
            "sectorThemeRotation": {
                "score": 52,
                "evidenceState": "score_grade",
                "reasons": [],
                "evidenceCount": 1,
                "observations": ["AI_SOFTWARE value=72 change=2"],
            },
            "eventCatalyst": {
                "score": 0,
                "evidenceState": "unavailable",
                "reasons": ["event_evidence_missing"],
                "evidenceCount": 0,
                "observations": [],
            },
        },
        "dataQuality": {
            "availableDriverCount": 6,
            "scoringDriverCount": 6,
            "missingDriverCount": 2,
            "confidenceCapReasons": ["dealer_gamma_unavailable_caps_volatility_compression"],
        },
        "missingEvidence": ["dealerGamma:unavailable", "eventCatalyst:unavailable"],
        "noAdviceDisclosure": "Research support only; not personalized financial advice.",
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
        if isinstance(value, (list, tuple)):
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
        if isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    visit(payload)
    return values


def test_volatility_spike_scenario_reclassifies_base_decision_without_mutating_input() -> None:
    base = _base_decision()
    original = copy.deepcopy(base)

    payload = build_market_scenario_lab(
        base_decision=base,
        scenario={"name": "volatilitySpike"},
    )

    assert base == original
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
    assert payload["baseRegime"] == {"regime": "riskOn", "confidence": "medium", "confidenceScore": 0.68}
    assert payload["scenarioRegime"]["regime"] in {"mixed", "riskOff", "downsideAccelerationRisk"}
    assert payload["scenarioRegime"]["confidence"] in {"low", "medium"}
    assert payload["scenarioOutput"]["scenarioRegime"] == payload["scenarioRegime"]
    assert payload["scenarioOutput"]["confidenceDelta"] == payload["confidenceDelta"]
    assert payload["scenarioOutput"]["changedDrivers"] == payload["changedDrivers"]
    assert payload["confidenceDelta"] < 0
    assert payload["driverDeltas"]["volatilityStructure"] < 0
    assert payload["driverDeltas"]["breadthParticipation"] <= 0
    assert "volatilityStructure" in payload["changedDrivers"]
    assert "breadthParticipation" in payload["changedDrivers"]
    assert payload["scenarioSummary"] == [
        "Scenario lab compares the base regime with a deterministic stress case for research planning.",
        "The scenario read weakens when volatility pressure and breadth deterioration are applied.",
    ]
    assert "Dealer gamma evidence is unavailable in the base read." in payload["evidenceLimits"]
    assert "dealer_gamma_unavailable_caps_volatility_compression" not in payload["evidenceLimits"]
    assert all(not INTERNAL_LOOKING_TOKEN.search(item) for item in payload["evidenceLimits"])
    assert payload["consumerIssues"]
    serialized_issues = json.dumps(payload["consumerIssues"], ensure_ascii=False).lower()
    assert "dealer_gamma_unavailable_caps_volatility_compression" not in serialized_issues
    assert payload["noAdviceDisclosure"] == "Research planning only; not a personalized decision basis."
    assert payload["confirmInvalidateContext"] == {
        "confirm": payload["whatWouldConfirm"],
        "invalidate": payload["whatWouldInvalidate"],
    }

    serialized = _serialized_values(payload)
    for forbidden in FORBIDDEN_PUBLIC_TERMS:
        assert forbidden not in serialized
    for label in _consumer_label_values(payload):
        assert not INTERNAL_LOOKING_TOKEN.search(label)


def test_explicit_overrides_and_gamma_unavailable_surface_changed_drivers_and_limits() -> None:
    payload = build_market_scenario_lab(
        base_decision=_base_decision(),
        scenario={
            "breadthShock": -55,
            "ratesDollarShock": -45,
            "liquidityShock": -30,
            "gammaEvidenceStatus": "unavailable",
            "eventRiskShock": -20,
        },
    )

    assert payload["baseRegime"]["regime"] == "riskOn"
    assert payload["scenarioRegime"]["regime"] in {"mixed", "riskOff", "downsideAccelerationRisk"}
    assert payload["driverDeltas"]["breadthParticipation"] == -55
    assert payload["driverDeltas"]["ratesDollar"] == -45
    assert payload["driverDeltas"]["liquidityCredit"] == -30
    assert payload["driverDeltas"]["eventCatalyst"] == -20
    assert payload["driverDeltas"]["dealerGamma"] == 0
    assert payload["changedDrivers"] == [
        "breadthParticipation",
        "ratesDollar",
        "liquidityCredit",
        "eventCatalyst",
    ]
    assert "Gamma evidence status is unavailable, so gamma-sensitive conclusions remain capped." in payload[
        "evidenceLimits"
    ]
    assert payload["contractStatus"]["state"] == "degraded"
    assert payload["whatWouldConfirm"] == [
        "Score-grade evidence would need to show the stressed drivers moving together in the scenario direction.",
        "The scenario frame would need current breadth, volatility, rates-dollar, liquidity, and cross-asset inputs.",
    ]
    assert payload["whatWouldInvalidate"] == [
        "The scenario frame weakens if score-grade evidence does not move with the selected shocks.",
        "The scenario frame weakens if key drivers are proxy-only, stale, blocked, or observation-only.",
    ]


def test_missing_base_evidence_returns_degraded_unavailable_payload() -> None:
    payload = build_market_scenario_lab(
        base_decision={},
        scenario={"name": "riskOnConfirmation"},
    )

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
    assert payload["selectedScenario"]["name"] == "riskOnConfirmation"
    assert payload["confidenceDelta"] == 0.0
    assert payload["driverDeltas"] == {}
    assert payload["changedDrivers"] == []
    assert payload["scenarioSummary"] == [
        "Scenario lab is unavailable because base score-grade regime evidence is missing."
    ]
    assert payload["evidenceLimits"] == [
        "Base regime evidence is missing or below the minimum driver coverage for scenario analysis."
    ]
    assert payload["confirmInvalidateContext"] == {"confirm": [], "invalidate": []}
    for label in _consumer_label_values(payload):
        assert not INTERNAL_LOOKING_TOKEN.search(label)


def test_normalized_driver_scores_can_be_used_without_base_decision_payload() -> None:
    payload = build_market_scenario_lab(
        driver_scores={
            "breadthParticipation": 62,
            "volatilityStructure": 48,
            "ratesDollar": 34,
            "liquidityCredit": 57,
            "crossAssetRisk": 36,
            "sectorThemeRotation": 42,
        },
        scenario="breadthBreakdown",
    )

    assert payload["baseRegime"] == {"regime": "riskOn", "confidence": "medium", "confidenceScore": 0.68}
    assert payload["scenarioRegime"]["regime"] in {"mixed", "riskOff"}
    assert payload["driverDeltas"]["breadthParticipation"] == -110
    assert payload["changedDrivers"] == [
        "breadthParticipation",
        "liquidityCredit",
        "crossAssetRisk",
    ]


def test_all_public_named_scenarios_return_research_planning_payloads() -> None:
    expected_names = {
        "volatilitySpike",
        "breadthBreakdown",
        "ratesUpDollarUp",
        "liquidityStress",
        "riskOnConfirmation",
        "gammaUnavailable",
    }

    for scenario_name in expected_names:
        payload = build_market_scenario_lab(
            base_decision=_base_decision(),
            scenario={"name": scenario_name},
        )

        assert payload["schemaVersion"] == "market_scenario_lab_engine.v1"
        assert payload["observationOnly"] is True
        assert payload["decisionGrade"] is False
        assert payload["selectedScenario"]["name"] == scenario_name
        assert payload["baseRegime"]["regime"] == "riskOn"
        assert payload["scenarioRegime"]["regime"]
        assert payload["noAdviceDisclosure"] == "Research planning only; not a personalized decision basis."

        serialized = _serialized_values(payload)
        for forbidden in FORBIDDEN_PUBLIC_TERMS:
            assert forbidden not in serialized


def test_service_does_not_import_protected_runtime_domains() -> None:
    tree = ast.parse((REPO_ROOT / "src/services/market_scenario_lab_engine.py").read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    for module in imports:
        assert not any(module == prefix or module.startswith(f"{prefix}.") for prefix in FORBIDDEN_IMPORT_PREFIXES)
