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


def _authoritative_base_decision() -> dict[str, Any]:
    base = copy.deepcopy(_base_decision())
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
        if isinstance(value, (list, tuple)):
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


def _assert_fixture_payload(payload: dict[str, Any], scenario_name: str) -> None:
    assert payload["selectedScenario"]["presetId"] == scenario_name
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert payload["sourceClass"] == "fixture"
    assert payload["dataSourceClass"] == "fixture"
    assert payload["baseMarketContext"]["source"] == "scenarioFixture"
    assert payload["baseMarketContext"]["evidenceState"] == "degraded"
    assert payload["contractStatus"]["state"] == "degraded"
    assert payload["scenarioRegime"].get("status") != "unavailable"
    assert payload["driverDeltas"]
    assert payload["changedDrivers"]
    assert payload["noAdviceDisclosure"] == "Research planning only; not a personalized decision basis."
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
    assert payload["baselineReadiness"]["evidenceCompleteness"]["state"] == "blocked"
    assert payload["baselineReadiness"]["scoreAuthority"] == "observation_only"
    assert payload["baselineReadiness"]["observationOnly"] is True
    assert payload["scenarioBaselineSnapshot"]["status"] == "not_available"
    assert payload["scenarioBaselineSnapshot"]["reasonCode"] == "baseline_missing"
    assert "baselineSnapshot" in payload["baselineReadiness"]["evidenceGaps"]
    assert "dealerGamma" in payload["baselineReadiness"]["affectedDriverKeys"]
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
    assert payload["confirmInvalidateContext"]["status"] == "available"
    assert payload["confirmInvalidateContext"]["confirm"] == payload["whatWouldConfirm"]
    assert payload["confirmInvalidateContext"]["invalidate"] == payload["whatWouldInvalidate"]

    _assert_safe_consumer_text(payload)
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
    assert payload["confirmInvalidateContext"] == {
        "status": "available",
        "message": "Scenario comparison includes confirm and invalidate context for research review.",
        "confirm": payload["whatWouldConfirm"],
        "invalidate": payload["whatWouldInvalidate"],
    }


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
    assert payload["baselineReadiness"]["status"] == "blocked"
    assert payload["baselineReadiness"]["baselineSnapshot"]["state"] == "missing"
    assert payload["baselineReadiness"]["marketFrame"]["state"] == "missing"
    assert payload["baselineReadiness"]["driverInputs"]["state"] == "missing"
    assert payload["baselineReadiness"]["evidenceCompleteness"]["state"] == "blocked"
    assert payload["baselineReadiness"]["dataState"] == "unavailable"
    assert payload["baselineReadiness"]["scoreAuthority"] == "observation_only"
    assert payload["scenarioBaselineSnapshot"]["status"] == "not_available"
    assert payload["scenarioBaselineSnapshot"]["reasonCode"] == "baseline_missing"
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert payload["selectedScenario"]["name"] == "riskOnConfirmation"
    assert payload["confidenceDelta"] == 0.0
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
    assert payload["selectedScenario"]["presetId"] == "riskOnConfirmation"
    _assert_preset_contract(payload["selectedScenario"])
    for label in _consumer_label_values(payload):
        assert not INTERNAL_LOOKING_TOKEN.search(label)


def test_fixture_path_runs_volatility_spike_without_weakening_real_gating() -> None:
    payload = build_market_scenario_lab(
        base_decision={},
        scenario={"name": "volatilitySpike", "dataSourceClass": "fixture"},
    )

    _assert_fixture_payload(payload, "volatilitySpike")
    assert payload["baselineReadiness"]["status"] == "blocked"
    assert payload["baselineReadiness"]["dataState"] == "demo_static_sample"
    assert payload["baselineReadiness"]["sampleState"] == "fixture"
    assert payload["baselineReadiness"]["scoreAuthority"] == "observation_only"
    assert payload["baselineReadiness"]["observationOnly"] is True
    assert payload["baseRegime"]["regime"] == "riskOn"
    assert payload["confidenceDelta"] < 0
    assert payload["driverDeltas"]["volatilityStructure"] < 0
    assert "volatilityStructure" in payload["changedDrivers"]


def test_fixture_path_runs_risk_on_confirmation_without_weakening_real_gating() -> None:
    payload = build_market_scenario_lab(
        base_decision={},
        scenario={"name": "riskOnConfirmation", "sourceClass": "sample"},
    )

    _assert_fixture_payload(payload, "riskOnConfirmation")
    assert payload["baselineReadiness"]["dataState"] == "demo_static_sample"
    assert payload["baselineReadiness"]["sampleState"] == "sample"
    assert payload["driverDeltas"]["breadthParticipation"] > 0
    assert payload["driverDeltas"]["liquidityCredit"] > 0
    assert "breadthParticipation" in payload["changedDrivers"]


def test_static_fallback_baseline_is_observation_only() -> None:
    base = _authoritative_base_decision()
    base["dataSourceClass"] = "static_fallback"

    payload = build_market_scenario_lab(
        base_decision=base,
        scenario={"name": "riskOnConfirmation"},
    )

    readiness = payload["baselineReadiness"]
    assert readiness["status"] == "partial"
    assert readiness["dataState"] == "demo_static_sample"
    assert readiness["sampleState"] == "fallback"
    assert readiness["baselineSnapshot"]["state"] == "partial"
    assert readiness["scoreAuthority"] == "observation_only"
    assert readiness["observationOnly"] is True


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
    assert payload["baselineReadiness"]["status"] == "blocked"
    assert payload["baselineReadiness"]["baselineSnapshot"]["state"] == "missing"
    assert payload["baselineReadiness"]["dataState"] == "request_supplied"


def test_complete_cached_baseline_snapshot_can_be_ready_and_authoritative() -> None:
    payload = build_market_scenario_lab(
        base_decision=_authoritative_base_decision(),
        scenario={"name": "riskOnConfirmation"},
    )

    readiness = payload["baselineReadiness"]
    assert readiness["status"] == "ready"
    assert readiness["baselineSnapshot"] == {
        "state": "available",
        "available": True,
        "lastUpdated": "2026-06-15T09:30:00Z",
        "affectedComponents": [],
    }
    assert readiness["marketFrame"] == {
        "state": "available",
        "available": True,
        "lastUpdated": "2026-06-15T09:30:00Z",
        "affectedComponents": [],
    }
    assert readiness["driverInputs"]["state"] == "available"
    assert readiness["driverInputs"]["affectedDriverKeys"] == []
    assert readiness["evidenceCompleteness"] == {"state": "ready", "gaps": []}
    assert readiness["dataState"] == "real_cached"
    assert readiness["scoreAuthority"] == "authoritative"
    assert readiness["authoritative"] is True
    assert readiness["observationOnly"] is False
    assert readiness["lastUpdated"] == "2026-06-15T09:30:00Z"


def test_complete_cached_baseline_without_authority_remains_observation_only() -> None:
    base = _authoritative_base_decision()
    base["sourceAuthorityAllowed"] = False
    base["dataQuality"]["sourceAuthorityAllowed"] = False
    base["dataQuality"]["scoreAuthorityAllowed"] = False

    payload = build_market_scenario_lab(
        base_decision=base,
        scenario={"name": "riskOnConfirmation"},
    )

    readiness = payload["baselineReadiness"]
    assert readiness["status"] == "partial"
    assert readiness["baselineSnapshot"]["state"] == "partial"
    assert readiness["dataState"] == "request_supplied"
    assert readiness["scoreAuthority"] == "observation_only"
    assert readiness["authoritative"] is False
    assert "scoreAuthority" in readiness["evidenceGaps"]


def test_stale_baseline_snapshot_limits_readiness_without_changing_output() -> None:
    base = _authoritative_base_decision()
    base["baselineSnapshot"]["state"] = "stale"
    base["baselineSnapshot"]["isStale"] = True
    base["marketFrame"]["freshness"] = "stale"

    payload = build_market_scenario_lab(
        base_decision=base,
        scenario={"name": "volatilitySpike"},
    )

    readiness = payload["baselineReadiness"]
    assert payload["driverDeltas"]["volatilityStructure"] < 0
    assert readiness["status"] == "partial"
    assert readiness["baselineSnapshot"]["state"] == "stale"
    assert readiness["marketFrame"]["state"] == "stale"
    assert readiness["evidenceCompleteness"]["state"] == "partial"
    assert readiness["scoreAuthority"] == "observation_only"
    assert readiness["affectedBaselineComponents"] == ["baselineSnapshot", "marketFrame"]


def test_missing_driver_inputs_report_affected_keys() -> None:
    base = _authoritative_base_decision()
    base["driverScores"]["eventCatalyst"] = {"score": 0, "evidenceState": "unavailable"}
    base["dataQuality"]["confidenceCapReasons"] = ["event_evidence_missing"]
    base["missingEvidence"] = ["eventCatalyst:unavailable"]

    payload = build_market_scenario_lab(
        base_decision=base,
        scenario={"name": "riskOnConfirmation"},
    )

    readiness = payload["baselineReadiness"]
    assert readiness["status"] == "partial"
    assert readiness["driverInputs"]["state"] == "partial"
    assert "eventCatalyst" in readiness["driverInputs"]["missingDriverKeys"]
    assert "eventCatalyst" in readiness["affectedDriverKeys"]
    assert "evidenceLimits" in readiness["evidenceGaps"]
    assert readiness["evidenceCompleteness"]["state"] == "partial"


def test_all_public_named_scenarios_return_research_planning_payloads() -> None:
    first_payload = build_market_scenario_lab(
        base_decision=_base_decision(),
        scenario={"name": EXPECTED_PRESET_IDS[0]},
    )
    second_payload = build_market_scenario_lab(
        base_decision=_base_decision(),
        scenario={"name": EXPECTED_PRESET_IDS[0]},
    )
    assert first_payload["scenarioPresets"] == second_payload["scenarioPresets"]
    first_payload["scenarioPresets"][0]["inputAssumptions"].append("mutated assumption")
    third_payload = build_market_scenario_lab(
        base_decision=_base_decision(),
        scenario={"name": EXPECTED_PRESET_IDS[0]},
    )
    assert "mutated assumption" not in third_payload["scenarioPresets"][0]["inputAssumptions"]

    for scenario_name in EXPECTED_PRESET_IDS:
        payload = build_market_scenario_lab(
            base_decision=_base_decision(),
            scenario={"name": scenario_name},
        )

        assert payload["schemaVersion"] == "market_scenario_lab_engine.v1"
        assert payload["observationOnly"] is True
        assert payload["decisionGrade"] is False
        assert payload["selectedScenario"]["presetId"] == scenario_name
        assert payload["selectedScenario"]["name"] == scenario_name
        assert payload["selectedScenario"]["observationOnly"] is True
        assert payload["selectedScenario"]["decisionGrade"] is False
        _assert_preset_contract(payload["selectedScenario"])
        assert [item["presetId"] for item in payload["scenarioPresets"]] == EXPECTED_PRESET_IDS
        assert payload["baseRegime"]["regime"] == "riskOn"
        assert payload["scenarioRegime"]["regime"]
        assert payload["noAdviceDisclosure"] == "Research planning only; not a personalized decision basis."
        _assert_safe_consumer_text(payload)


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
