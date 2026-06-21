# -*- coding: utf-8 -*-
"""Deterministic market scenario lab engine.

The engine consumes caller-supplied market regime evidence or normalized driver
scores. It does not read providers, mutate cache state, or produce personalized
financial advice.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from src.services.consumer_issue_labels import build_consumer_issues


SCHEMA_VERSION = "market_scenario_lab_engine.v1"
NO_ADVICE_DISCLOSURE = "Research planning only; not a personalized decision basis."
OBSERVATION_ONLY = True
DECISION_GRADE = False

DRIVER_KEYS: tuple[str, ...] = (
    "dealerGamma",
    "breadthParticipation",
    "volatilityStructure",
    "ratesDollar",
    "liquidityCredit",
    "crossAssetRisk",
    "sectorThemeRotation",
    "eventCatalyst",
)

_SCORING_DRIVER_KEYS = tuple(key for key in DRIVER_KEYS if key != "dealerGamma")
_MIN_BASE_SCORING_DRIVERS = 3
_FIXTURE_SOURCE_CLASSES = {"fixture", "demo", "sample"}
_STATIC_SOURCE_CLASSES = {"static", "fallback", "static_fallback", "public_web_fallback"}
_REAL_SOURCE_CLASSES = {
    "cached",
    "provider_backed",
    "provider-backed",
    "real_cached",
    "real",
    "live",
    "official",
    "authorized",
    "authorized_cached",
}
_STALE_STATES = {"stale", "expired", "stale_or_cached"}
_MISSING_STATES = {"missing", "unavailable", "blocked", "no_data", "none"}
_PARTIAL_STATES = {"partial", "degraded", "limited", "incomplete"}
_AVAILABLE_STATES = {"available", "ready", "fresh", "live", "cached", "delayed"}

_SHOCK_TO_DRIVER: dict[str, str] = {
    "volatilityShock": "volatilityStructure",
    "breadthShock": "breadthParticipation",
    "ratesDollarShock": "ratesDollar",
    "liquidityShock": "liquidityCredit",
    "crossAssetRiskShock": "crossAssetRisk",
    "eventRiskShock": "eventCatalyst",
}

_NAMED_SCENARIOS: dict[str, dict[str, int]] = {
    "volatilitySpike": {
        "volatilityStructure": -145,
        "breadthParticipation": -75,
        "crossAssetRisk": -40,
    },
    "breadthBreakdown": {
        "breadthParticipation": -110,
        "liquidityCredit": -20,
        "crossAssetRisk": -25,
    },
    "ratesUpDollarUp": {
        "ratesDollar": -105,
        "liquidityCredit": -25,
        "crossAssetRisk": -20,
    },
    "liquidityStress": {
        "liquidityCredit": -120,
        "crossAssetRisk": -45,
        "volatilityStructure": -35,
    },
    "riskOnConfirmation": {
        "breadthParticipation": 30,
        "volatilityStructure": 25,
        "ratesDollar": 20,
        "liquidityCredit": 30,
        "crossAssetRisk": 25,
        "sectorThemeRotation": 15,
    },
    "gammaUnavailable": {},
}
_COMMON_INPUT_ASSUMPTIONS: tuple[str, ...] = (
    "Uses market context supplied with the request.",
    "Compares deterministic driver changes without fetching fresh market data.",
    "Keeps the result as an observation-only research view.",
)
_DEFAULT_LINKED_SURFACES: tuple[dict[str, str], ...] = (
    {
        "label": "Market Decision Cockpit",
        "route": "/market/decision-cockpit",
        "section": "marketContext",
        "reason": "Review the base market context.",
    },
    {
        "label": "Market Overview",
        "route": "/market-overview",
        "section": "marketContext",
        "reason": "Review broader market observations.",
    },
    {
        "label": "Scenario Lab",
        "route": "/scenario-lab",
        "section": "scenarioPreset",
        "reason": "Review bounded scenario assumptions.",
    },
)
_AVAILABLE_CONFIRM_INVALIDATE_CONTEXT: dict[str, Any] = {
    "status": "available",
    "message": "Scenario comparison includes confirm and invalidate context for research review.",
    "confirm": [
        "Fresh score-grade observations move together with the selected scenario drivers.",
        "Broader market context remains consistent with the scenario assumptions.",
    ],
    "invalidate": [
        "Key observations remain unavailable, stale, or proxy-only.",
        "Broader market context moves against the selected scenario assumptions.",
    ],
}
_UNAVAILABLE_CONFIRM_INVALIDATE_CONTEXT: dict[str, Any] = {
    "status": "unavailable",
    "message": (
        "Confirm and invalidate context is unavailable until base score-grade evidence reaches minimum coverage."
    ),
    "confirm": [],
    "invalidate": [],
}
_SCENARIO_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "presetId": "volatilitySpike",
        "name": "volatilitySpike",
        "label": "Volatility stress observation",
        "category": "Volatility stress",
        "description": "Stress volatility and breadth inputs to compare research-context sensitivity.",
        "inputAssumptions": [
            *_COMMON_INPUT_ASSUMPTIONS,
            "Applies pressure to volatility, breadth, and cross-asset drivers.",
        ],
        "expectedDriverImpacts": [
            {"driver": "Volatility structure", "direction": "pressure", "magnitude": "high"},
            {"driver": "Breadth participation", "direction": "pressure", "magnitude": "medium"},
            {"driver": "Cross-asset risk", "direction": "pressure", "magnitude": "low"},
        ],
        "evidenceLimits": [
            "Gamma evidence may cap confidence when it is unavailable.",
            "Breadth and volatility observations need fresh confirmation before the frame can strengthen.",
        ],
        "confirmInvalidateContext": _AVAILABLE_CONFIRM_INVALIDATE_CONTEXT,
        "linkedSurfaces": _DEFAULT_LINKED_SURFACES,
        "consumerIssues": [],
        "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
        "observationOnly": OBSERVATION_ONLY,
        "decisionGrade": DECISION_GRADE,
    },
    {
        "presetId": "breadthBreakdown",
        "name": "breadthBreakdown",
        "label": "Breadth deterioration observation",
        "category": "Breadth stress",
        "description": "Stress market breadth inputs to compare research-context resilience.",
        "inputAssumptions": [
            *_COMMON_INPUT_ASSUMPTIONS,
            "Applies pressure to participation, liquidity, and cross-asset drivers.",
        ],
        "expectedDriverImpacts": [
            {"driver": "Breadth participation", "direction": "pressure", "magnitude": "high"},
            {"driver": "Liquidity and credit", "direction": "pressure", "magnitude": "low"},
            {"driver": "Cross-asset risk", "direction": "pressure", "magnitude": "low"},
        ],
        "evidenceLimits": [
            "Breadth observations can be sample-limited.",
            "Liquidity context may remain incomplete when only request evidence is supplied.",
        ],
        "confirmInvalidateContext": _AVAILABLE_CONFIRM_INVALIDATE_CONTEXT,
        "linkedSurfaces": _DEFAULT_LINKED_SURFACES,
        "consumerIssues": [],
        "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
        "observationOnly": OBSERVATION_ONLY,
        "decisionGrade": DECISION_GRADE,
    },
    {
        "presetId": "ratesUpDollarUp",
        "name": "ratesUpDollarUp",
        "label": "Rates and dollar stress observation",
        "category": "Macro stress",
        "description": "Stress rates-dollar inputs to compare macro-pressure sensitivity.",
        "inputAssumptions": [
            *_COMMON_INPUT_ASSUMPTIONS,
            "Applies pressure to rates, dollar, liquidity, and cross-asset drivers.",
        ],
        "expectedDriverImpacts": [
            {"driver": "Rates and dollar", "direction": "pressure", "magnitude": "high"},
            {"driver": "Liquidity and credit", "direction": "pressure", "magnitude": "low"},
            {"driver": "Cross-asset risk", "direction": "pressure", "magnitude": "low"},
        ],
        "evidenceLimits": [
            "Macro observations may lag intraday market context.",
            "Liquidity context may remain incomplete when only request evidence is supplied.",
        ],
        "confirmInvalidateContext": _AVAILABLE_CONFIRM_INVALIDATE_CONTEXT,
        "linkedSurfaces": _DEFAULT_LINKED_SURFACES,
        "consumerIssues": [],
        "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
        "observationOnly": OBSERVATION_ONLY,
        "decisionGrade": DECISION_GRADE,
    },
    {
        "presetId": "liquidityStress",
        "name": "liquidityStress",
        "label": "Liquidity stress observation",
        "category": "Liquidity stress",
        "description": "Stress liquidity and cross-asset inputs to compare evidence limits.",
        "inputAssumptions": [
            *_COMMON_INPUT_ASSUMPTIONS,
            "Applies pressure to liquidity, cross-asset, and volatility drivers.",
        ],
        "expectedDriverImpacts": [
            {"driver": "Liquidity and credit", "direction": "pressure", "magnitude": "high"},
            {"driver": "Cross-asset risk", "direction": "pressure", "magnitude": "medium"},
            {"driver": "Volatility structure", "direction": "pressure", "magnitude": "low"},
        ],
        "evidenceLimits": [
            "Liquidity observations may be partial when request evidence is limited.",
            "Cross-asset context needs confirmation from the broader market view.",
        ],
        "confirmInvalidateContext": _AVAILABLE_CONFIRM_INVALIDATE_CONTEXT,
        "linkedSurfaces": _DEFAULT_LINKED_SURFACES,
        "consumerIssues": [],
        "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
        "observationOnly": OBSERVATION_ONLY,
        "decisionGrade": DECISION_GRADE,
    },
    {
        "presetId": "riskOnConfirmation",
        "name": "riskOnConfirmation",
        "label": "Risk-on confirmation observation",
        "category": "Confirmation",
        "description": "Lift multiple score-grade drivers to compare what would support a stronger frame.",
        "inputAssumptions": [
            *_COMMON_INPUT_ASSUMPTIONS,
            "Applies supportive changes across breadth, volatility, macro, liquidity, and rotation drivers.",
        ],
        "expectedDriverImpacts": [
            {"driver": "Breadth participation", "direction": "supportive", "magnitude": "medium"},
            {"driver": "Volatility structure", "direction": "supportive", "magnitude": "low"},
            {"driver": "Liquidity and credit", "direction": "supportive", "magnitude": "medium"},
            {"driver": "Sector theme rotation", "direction": "supportive", "magnitude": "low"},
        ],
        "evidenceLimits": [
            "Supportive context still needs multiple score-grade observations.",
            "Unavailable gamma evidence keeps confidence capped.",
        ],
        "confirmInvalidateContext": _AVAILABLE_CONFIRM_INVALIDATE_CONTEXT,
        "linkedSurfaces": _DEFAULT_LINKED_SURFACES,
        "consumerIssues": [],
        "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
        "observationOnly": OBSERVATION_ONLY,
        "decisionGrade": DECISION_GRADE,
    },
    {
        "presetId": "gammaUnavailable",
        "name": "gammaUnavailable",
        "label": "Gamma evidence gap observation",
        "category": "Evidence gap",
        "description": "Keep gamma evidence unavailable to compare capped scenario output.",
        "inputAssumptions": [
            *_COMMON_INPUT_ASSUMPTIONS,
            "Treats gamma context as unavailable and does not infer missing option-chain evidence.",
        ],
        "expectedDriverImpacts": [
            {"driver": "Dealer gamma", "direction": "unchanged", "magnitude": "low"},
        ],
        "evidenceLimits": [
            "Gamma evidence is unavailable, so gamma-sensitive conclusions remain capped.",
            "The preset does not infer option-chain context from other market inputs.",
        ],
        "confirmInvalidateContext": _UNAVAILABLE_CONFIRM_INVALIDATE_CONTEXT,
        "linkedSurfaces": _DEFAULT_LINKED_SURFACES,
        "consumerIssues": build_consumer_issues(["live_gex_not_implemented_v1"]),
        "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
        "observationOnly": OBSERVATION_ONLY,
        "decisionGrade": DECISION_GRADE,
    },
)
_SCENARIO_PRESETS_BY_NAME = {preset["name"]: preset for preset in _SCENARIO_PRESETS}
_GENERIC_EVIDENCE_LIMIT = "No additional evidence limits were supplied with the base read."


class MarketScenarioLabEngine:
    """Compare a base market regime read with deterministic scenario shocks."""

    def build(
        self,
        *,
        base_decision: Mapping[str, Any] | None = None,
        driver_scores: Mapping[str, Any] | None = None,
        scenario: Mapping[str, Any] | str | None = None,
    ) -> dict[str, Any]:
        scenario_input = _scenario_mapping(scenario)
        fixture_source_class = _fixture_source_class(scenario_input)
        if fixture_source_class and not base_decision and not driver_scores:
            base_decision = _fixture_base_decision()
        base = _base_from_inputs(base_decision=base_decision, driver_scores=driver_scores)
        if base["scoringDriverCount"] < _MIN_BASE_SCORING_DRIVERS:
            return _unavailable_payload(base, scenario_input, fixture_source_class=fixture_source_class)

        deltas = _scenario_deltas(scenario_input)
        scenario_scores = {
            key: _clamp_score(base["scores"].get(key, 0) + deltas.get(key, 0))
            for key in DRIVER_KEYS
        }
        base_confidence_score = base["confidenceScore"]
        scenario_regime = _classify_regime(scenario_scores, base["evidenceStates"])
        scenario_confidence_score = _scenario_confidence_score(
            scenario_regime=scenario_regime,
            base_confidence_score=base_confidence_score,
            scoring_driver_count=base["scoringDriverCount"],
            deltas=deltas,
            scenario_input=scenario_input,
            base=base,
        )
        changed_drivers = [key for key in DRIVER_KEYS if deltas.get(key, 0) != 0]
        confidence_delta = round(scenario_confidence_score - base_confidence_score, 2)
        driver_deltas = {key: deltas.get(key, 0) for key in DRIVER_KEYS}
        scenario_regime_payload = {
            "regime": scenario_regime,
            "confidence": _confidence_label(scenario_confidence_score),
            "confidenceScore": scenario_confidence_score,
        }
        scenario_summary = _scenario_summary(deltas)
        confirm_context = [
            "Score-grade evidence would need to show the stressed drivers moving together in the scenario direction.",
            (
                "The scenario frame would need current breadth, volatility, rates-dollar, "
                "liquidity, and cross-asset inputs."
            ),
        ]
        invalidate_context = [
            "The scenario frame weakens if score-grade evidence does not move with the selected shocks.",
            "The scenario frame weakens if key drivers are proxy-only, stale, blocked, or observation-only.",
        ]
        confirm_invalidate_context = _confirm_invalidate_context(
            status="available",
            message="Scenario comparison includes confirm and invalidate context for research review.",
            confirm=confirm_context,
            invalidate=invalidate_context,
        )
        evidence_limits = _evidence_limits(base, scenario_input)
        if fixture_source_class:
            evidence_limits = _dedupe(
                [
                    *evidence_limits,
                    "Scenario uses a sample fixture for UAT observation; it is not live market evidence.",
                ]
            )
        consumer_issues = build_consumer_issues(
            base.get("missingEvidence"),
            base.get("dataQuality"),
            evidence_limits,
            scenario_input.get("gammaEvidenceStatus"),
            "proxy_or_sample_evidence_present" if fixture_source_class else None,
        )
        baseline_readiness = _baseline_readiness(
            base=base,
            evidence_limits=evidence_limits,
            fixture_source_class=fixture_source_class,
        )
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "contractStatus": _contract_status(base=base, evidence_limits=evidence_limits),
            "observationOnly": OBSERVATION_ONLY,
            "decisionGrade": DECISION_GRADE,
            "selectedScenario": _selected_scenario(scenario_input),
            "scenarioPresets": _scenario_presets(),
            "baseMarketContext": _base_market_context(base),
            "baselineReadiness": baseline_readiness,
            "baseRegime": {
                "regime": base["regime"],
                "confidence": base["confidence"],
                "confidenceScore": base_confidence_score,
            },
            "scenarioRegime": scenario_regime_payload,
            "scenarioOutput": {
                "scenarioRegime": scenario_regime_payload,
                "confidenceDelta": confidence_delta,
                "driverDeltas": driver_deltas,
                "changedDrivers": changed_drivers,
                "summary": scenario_summary,
            },
            "confidenceDelta": confidence_delta,
            "driverDeltas": driver_deltas,
            "changedDrivers": changed_drivers,
            "scenarioSummary": scenario_summary,
            "confirmInvalidateContext": confirm_invalidate_context,
            "whatWouldConfirm": confirm_context,
            "whatWouldInvalidate": invalidate_context,
            "evidenceLimits": evidence_limits,
            "consumerIssues": consumer_issues,
            "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
        }
        if fixture_source_class:
            payload["sourceClass"] = "fixture"
            payload["dataSourceClass"] = "fixture"
        return payload


def build_market_scenario_lab(
    *,
    base_decision: Mapping[str, Any] | None = None,
    driver_scores: Mapping[str, Any] | None = None,
    scenario: Mapping[str, Any] | str | None = None,
) -> dict[str, Any]:
    """Build the v1 market scenario lab payload."""

    return MarketScenarioLabEngine().build(
        base_decision=base_decision,
        driver_scores=driver_scores,
        scenario=scenario,
    )


def _base_from_inputs(
    *,
    base_decision: Mapping[str, Any] | None,
    driver_scores: Mapping[str, Any] | None,
) -> dict[str, Any]:
    decision = base_decision if isinstance(base_decision, Mapping) else {}
    raw_scores = driver_scores if isinstance(driver_scores, Mapping) else decision.get("driverScores")
    scores, evidence_states = _normalize_driver_scores(raw_scores if isinstance(raw_scores, Mapping) else {})
    scoring_driver_count = sum(
        1
        for key in _SCORING_DRIVER_KEYS
        if evidence_states.get(key) in {"score_grade", "limited"} or scores.get(key) != 0
    )
    regime = str(decision.get("regime") or "")
    if not regime:
        regime = _classify_regime(scores, evidence_states)

    confidence_score = _number(decision.get("confidenceScore"))
    if confidence_score is None:
        confidence_score = _confidence_score_for_regime(
            regime,
            scoring_driver_count,
        )

    return {
        "regime": regime or "lowConfidence",
        "confidence": str(decision.get("confidence") or _confidence_label(confidence_score)),
        "confidenceScore": round(max(0.0, min(0.92, confidence_score)), 2),
        "scores": scores,
        "evidenceStates": evidence_states,
        "missingEvidence": list(decision.get("missingEvidence") or []),
        "dataQuality": decision.get("dataQuality") if isinstance(decision.get("dataQuality"), Mapping) else {},
        "scoringDriverCount": scoring_driver_count,
        "contextSource": _base_context_source(decision=decision, driver_scores=driver_scores),
        "baselineSnapshot": _mapping_or_empty(
            decision.get("baselineSnapshot") or decision.get("baselineMarketSnapshot") or decision.get("snapshot")
        ),
        "marketFrame": _mapping_or_empty(decision.get("marketFrame") or decision.get("currentMarketFrame")),
        "lastUpdated": _first_text(
            decision.get("lastUpdated"),
            decision.get("updatedAt"),
            decision.get("generatedAt"),
            decision.get("asOf"),
            decision.get("timestamp"),
        ),
        "sourceClass": _first_text(
            decision.get("dataSourceClass"),
            decision.get("sourceClass"),
            decision.get("sourceType"),
            decision.get("dataState"),
        ),
        "sourceAuthorityAllowed": _truthy(
            decision.get("sourceAuthorityAllowed"),
            decision.get("scoreAuthorityAllowed"),
            _mapping_or_empty(decision.get("dataQuality")).get("sourceAuthorityAllowed"),
            _mapping_or_empty(decision.get("dataQuality")).get("scoreAuthorityAllowed"),
            _mapping_or_empty(decision.get("dataQuality")).get("scoreContributionAllowed"),
        ),
    }


def _base_context_source(*, decision: Mapping[str, Any], driver_scores: Mapping[str, Any] | None) -> str:
    schema_version = str(decision.get("schemaVersion") or "")
    if schema_version == "market_scenario_lab_fixture.v1":
        return "scenarioFixture"
    if schema_version or decision.get("regime") or decision.get("driverScores"):
        return "decisionCockpitInput"
    if isinstance(driver_scores, Mapping) and driver_scores:
        return "driverScoreInput"
    return "requestInput"


def _normalize_driver_scores(raw_scores: Mapping[str, Any]) -> tuple[dict[str, int], dict[str, str]]:
    scores: dict[str, int] = {}
    evidence_states: dict[str, str] = {}
    for key in DRIVER_KEYS:
        value = raw_scores.get(key)
        if isinstance(value, Mapping):
            scores[key] = _clamp_score(_number(value.get("score")) or 0)
            evidence_states[key] = str(value.get("evidenceState") or value.get("state") or "score_grade")
        else:
            scores[key] = _clamp_score(_number(value) or 0)
            evidence_states[key] = "score_grade" if key in raw_scores else "unavailable"
    return scores, evidence_states


def _scenario_mapping(scenario: Mapping[str, Any] | str | None) -> Mapping[str, Any]:
    if isinstance(scenario, Mapping):
        return scenario
    if isinstance(scenario, str):
        return {"name": scenario}
    return {}


def _fixture_source_class(scenario: Mapping[str, Any]) -> str | None:
    for key in ("dataSourceClass", "sourceClass", "data_source_class", "source_class"):
        value = str(scenario.get(key) or "").strip().lower()
        if value in _FIXTURE_SOURCE_CLASSES:
            return value
    if scenario.get("fixtureMode") is True or scenario.get("demoMode") is True or scenario.get("sampleData") is True:
        return "fixture"
    return None


def _fixture_base_decision() -> dict[str, Any]:
    return {
        "schemaVersion": "market_scenario_lab_fixture.v1",
        "regime": "riskOn",
        "confidence": "medium",
        "confidenceScore": 0.62,
        "driverScores": {
            "dealerGamma": {"score": 0, "evidenceState": "unavailable"},
            "breadthParticipation": {"score": 58, "evidenceState": "score_grade"},
            "volatilityStructure": {"score": 54, "evidenceState": "score_grade"},
            "ratesDollar": {"score": 28, "evidenceState": "score_grade"},
            "liquidityCredit": {"score": 56, "evidenceState": "score_grade"},
            "crossAssetRisk": {"score": 32, "evidenceState": "score_grade"},
            "sectorThemeRotation": {"score": 42, "evidenceState": "score_grade"},
            "eventCatalyst": {"score": 0, "evidenceState": "unavailable"},
        },
        "dataQuality": {
            "availableDriverCount": 6,
            "scoringDriverCount": 6,
            "missingDriverCount": 2,
            "confidenceCapReasons": ["scenario_fixture_sample_only"],
        },
        "missingEvidence": [
            "dealerGamma:unavailable",
            "eventCatalyst:unavailable",
            "proxy_or_sample_evidence_present",
        ],
    }


def _scenario_name(scenario: Mapping[str, Any]) -> str:
    return str(scenario.get("presetId") or scenario.get("name") or scenario.get("scenarioName") or "").strip()


def _scenario_deltas(scenario: Mapping[str, Any]) -> dict[str, int]:
    name = _scenario_name(scenario)
    deltas = {key: 0 for key in DRIVER_KEYS}
    for key, value in _NAMED_SCENARIOS.get(name, {}).items():
        deltas[key] = value
    for shock_key, driver_key in _SHOCK_TO_DRIVER.items():
        value = _number(scenario.get(shock_key))
        if value is not None:
            deltas[driver_key] = _clamp_delta(value)
    return deltas


def _classify_regime(scores: Mapping[str, int], evidence_states: Mapping[str, str]) -> str:
    scoring_count = sum(
        1
        for key in _SCORING_DRIVER_KEYS
        if evidence_states.get(key) in {"score_grade", "limited"} or scores.get(key, 0) != 0
    )
    if scoring_count < _MIN_BASE_SCORING_DRIVERS:
        return "lowConfidence"

    breadth = scores["breadthParticipation"]
    volatility = scores["volatilityStructure"]
    rates_dollar = scores["ratesDollar"]
    liquidity = scores["liquidityCredit"]
    cross_asset = scores["crossAssetRisk"]
    rotation = scores["sectorThemeRotation"]
    event = scores["eventCatalyst"]

    if event <= -60:
        return "eventRisk"

    negative_cluster = sum(score <= -35 for score in (breadth, volatility, rates_dollar, liquidity, cross_asset))
    if volatility <= -50 and breadth <= -35 and negative_cluster >= 3:
        return "downsideAccelerationRisk"

    positive_count = sum(score >= 30 for score in (breadth, liquidity, cross_asset, rotation))
    negative_count = sum(score <= -30 for score in (breadth, volatility, rates_dollar, liquidity, cross_asset, rotation))
    if positive_count >= 2 and negative_count >= 2:
        return "mixed"
    if negative_count >= 3:
        return "riskOff"
    if positive_count >= 3 and volatility > -30 and rates_dollar > -30:
        return "riskOn"
    if max(abs(score) for score in (breadth, volatility, rates_dollar, liquidity, cross_asset, rotation)) <= 30:
        return "rangeBound"
    return "mixed"


def _scenario_confidence_score(
    *,
    scenario_regime: str,
    base_confidence_score: float,
    scoring_driver_count: int,
    deltas: Mapping[str, int],
    scenario_input: Mapping[str, Any],
    base: Mapping[str, Any],
) -> float:
    magnitude = sum(abs(value) for value in deltas.values()) / max(1, len(DRIVER_KEYS))
    if scoring_driver_count >= 6:
        score = min(base_confidence_score, 0.64)
    elif scoring_driver_count >= 4:
        score = min(base_confidence_score, 0.54)
    else:
        score = min(base_confidence_score, 0.38)
    if scenario_regime in {"mixed", "lowConfidence"}:
        score = min(score, 0.42)
    if magnitude >= 35:
        score -= 0.08
    if _gamma_status(scenario_input, base) == "unavailable":
        score = min(score, 0.52)
    return round(max(0.0, min(0.72, score)), 2)


def _confidence_score_for_regime(regime: str, scoring_driver_count: int) -> float:
    if regime == "lowConfidence" or scoring_driver_count < _MIN_BASE_SCORING_DRIVERS:
        return 0.0
    if scoring_driver_count >= 6:
        return 0.68
    if scoring_driver_count >= 4:
        return 0.56
    return 0.42


def _confidence_label(score: float) -> str:
    if score >= 0.72:
        return "high"
    if score >= 0.48:
        return "medium"
    return "low"


def _scenario_summary(deltas: Mapping[str, int]) -> list[str]:
    pressure_drivers = {
        key
        for key, value in deltas.items()
        if value < 0 and key in {"volatilityStructure", "breadthParticipation", "ratesDollar", "liquidityCredit"}
    }
    if {"volatilityStructure", "breadthParticipation"}.issubset(pressure_drivers):
        second_line = "The scenario read weakens when volatility pressure and breadth deterioration are applied."
    elif pressure_drivers:
        second_line = "The scenario read weakens when macro, liquidity, breadth, or cross-asset pressure is applied."
    else:
        second_line = "The scenario read improves only when multiple score-grade drivers are adjusted together."
    return [
        "Scenario lab compares the base regime with a deterministic stress case for research planning.",
        second_line,
    ]


def _evidence_limits(base: Mapping[str, Any], scenario: Mapping[str, Any]) -> list[str]:
    limits: list[str] = []
    missing = {str(item) for item in base.get("missingEvidence", [])}
    if "dealerGamma:unavailable" in missing or base["evidenceStates"].get("dealerGamma") == "unavailable":
        limits.append("Dealer gamma evidence is unavailable in the base read.")
    if _gamma_status(scenario, base) == "unavailable":
        limits.append("Gamma evidence status is unavailable, so gamma-sensitive conclusions remain capped.")
    data_quality = base.get("dataQuality") if isinstance(base.get("dataQuality"), Mapping) else {}
    for reason in data_quality.get("confidenceCapReasons") or []:
        text = _consumer_safe_confidence_limit(reason)
        if text and text not in limits:
            limits.append(text)
    return _dedupe(limits) or [_GENERIC_EVIDENCE_LIMIT]


def _consumer_safe_confidence_limit(reason: Any) -> str:
    normalized = str(reason or "").strip().lower()
    if normalized == "dealer_gamma_unavailable_caps_volatility_compression":
        return "Dealer gamma evidence is unavailable, so volatility-compression confidence remains capped."
    if normalized == "scenario_fixture_sample_only":
        return "Scenario base context is a sample fixture for UAT observation."
    if not normalized:
        return ""
    return "The base read includes a data-quality confidence cap."


def _gamma_status(scenario: Mapping[str, Any], base: Mapping[str, Any]) -> str:
    explicit = str(scenario.get("gammaEvidenceStatus") or "").strip().lower()
    if explicit:
        return explicit
    if "gammaUnavailable" == str(scenario.get("name") or scenario.get("scenarioName") or "").strip():
        return "unavailable"
    if base["evidenceStates"].get("dealerGamma") == "unavailable":
        return "unavailable"
    return "available"


def _scenario_presets() -> list[dict[str, Any]]:
    return [deepcopy(preset) for preset in _SCENARIO_PRESETS]


def _selected_scenario(scenario: Mapping[str, Any]) -> dict[str, Any]:
    name = _scenario_name(scenario) or "customScenario"
    preset = _SCENARIO_PRESETS_BY_NAME.get(name)
    if preset is not None:
        return deepcopy(preset)
    return _custom_scenario_preset()


def _custom_scenario_preset() -> dict[str, Any]:
    return {
        "presetId": "customScenario",
        "name": "customScenario",
        "label": "Custom scenario observation",
        "category": "Custom",
        "description": "Compare caller-supplied driver adjustments against the base research context.",
        "inputAssumptions": [
            *_COMMON_INPUT_ASSUMPTIONS,
            "Uses caller-supplied driver adjustments for the comparison.",
        ],
        "expectedDriverImpacts": [],
        "evidenceLimits": [
            "Custom scenarios depend on the supplied driver adjustments and base market context.",
        ],
        "confirmInvalidateContext": deepcopy(_AVAILABLE_CONFIRM_INVALIDATE_CONTEXT),
        "linkedSurfaces": deepcopy(_DEFAULT_LINKED_SURFACES),
        "consumerIssues": [],
        "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
        "observationOnly": OBSERVATION_ONLY,
        "decisionGrade": DECISION_GRADE,
    }


def _base_market_context(base: Mapping[str, Any]) -> dict[str, Any]:
    source = str(base.get("contextSource") or "requestInput")
    labels = {
        "decisionCockpitInput": "Decision Cockpit market context",
        "driverScoreInput": "Driver score context",
        "scenarioFixture": "Scenario sample fixture",
        "requestInput": "Request market context",
    }
    messages = {
        "decisionCockpitInput": (
            "Base regime context was supplied by the request and is treated as observation-only evidence."
        ),
        "driverScoreInput": (
            "Base driver scores were supplied by the request and are treated as observation-only evidence."
        ),
        "scenarioFixture": (
            "Base regime context uses a bounded sample fixture for UAT observation and is not live market evidence."
        ),
        "requestInput": "Base market context was supplied by the request and is treated as observation-only evidence.",
    }
    return {
        "source": source,
        "label": labels.get(source, labels["requestInput"]),
        "message": messages.get(source, messages["requestInput"]),
        "evidenceState": _base_evidence_state(base),
        "scoringDriverCount": int(base.get("scoringDriverCount") or 0),
    }


def _base_evidence_state(base: Mapping[str, Any]) -> str:
    if int(base.get("scoringDriverCount") or 0) < _MIN_BASE_SCORING_DRIVERS:
        return "unavailable"
    evidence_states = base.get("evidenceStates") if isinstance(base.get("evidenceStates"), Mapping) else {}
    if any(str(evidence_states.get(key) or "") != "score_grade" for key in DRIVER_KEYS):
        return "degraded"
    data_quality = base.get("dataQuality") if isinstance(base.get("dataQuality"), Mapping) else {}
    if data_quality.get("confidenceCapReasons"):
        return "degraded"
    return "ready"


def _contract_status(*, base: Mapping[str, Any], evidence_limits: Sequence[str]) -> dict[str, Any]:
    if int(base.get("scoringDriverCount") or 0) < _MIN_BASE_SCORING_DRIVERS:
        return _contract_status_payload(
            state="unavailable",
            label="Scenario unavailable",
            message="Scenario lab needs at least three score-grade market drivers before comparing scenarios.",
        )
    if _base_evidence_state(base) == "degraded" or list(evidence_limits) != [_GENERIC_EVIDENCE_LIMIT]:
        return _contract_status_payload(
            state="degraded",
            label="Scenario constrained by evidence gaps",
            message="Scenario comparison is available, but incomplete evidence keeps the result observation-only.",
        )
    return _contract_status_payload(
        state="available",
        label="Scenario ready",
        message="Scenario comparison is available as an observation-only research output.",
    )


def _contract_status_payload(*, state: str, label: str, message: str) -> dict[str, Any]:
    return {
        "state": state,
        "label": label,
        "message": message,
        "observationOnly": OBSERVATION_ONLY,
        "decisionGrade": DECISION_GRADE,
    }


def _unavailable_payload(
    base: Mapping[str, Any],
    scenario: Mapping[str, Any],
    *,
    fixture_source_class: str | None = None,
) -> dict[str, Any]:
    scenario_regime = {
        "regime": "lowConfidence",
        "confidence": "low",
        "confidenceScore": 0.0,
        "status": "unavailable",
    }
    scenario_summary = ["Scenario lab is unavailable because base score-grade regime evidence is missing."]
    evidence_limits = ["Base regime evidence is missing or below the minimum driver coverage for scenario analysis."]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "contractStatus": _contract_status(base=base, evidence_limits=evidence_limits),
        "observationOnly": OBSERVATION_ONLY,
        "decisionGrade": DECISION_GRADE,
        "selectedScenario": _selected_scenario(scenario),
        "scenarioPresets": _scenario_presets(),
        "baseMarketContext": _base_market_context(base),
        "baselineReadiness": _baseline_readiness(
            base=base,
            evidence_limits=evidence_limits,
            fixture_source_class=fixture_source_class,
        ),
        "baseRegime": {
            "regime": base["regime"],
            "confidence": base["confidence"],
            "confidenceScore": base["confidenceScore"],
        },
        "scenarioRegime": scenario_regime,
        "scenarioOutput": {
            "scenarioRegime": scenario_regime,
            "confidenceDelta": 0.0,
            "driverDeltas": {},
            "changedDrivers": [],
            "summary": scenario_summary,
        },
        "confidenceDelta": 0.0,
        "driverDeltas": {},
        "changedDrivers": [],
        "scenarioSummary": scenario_summary,
        "confirmInvalidateContext": _confirm_invalidate_context(
            status="unavailable",
            message=(
                "Confirm and invalidate context is unavailable until base score-grade evidence reaches minimum "
                "coverage."
            ),
            confirm=[],
            invalidate=[],
        ),
        "whatWouldConfirm": [],
        "whatWouldInvalidate": [],
        "evidenceLimits": evidence_limits,
        "consumerIssues": build_consumer_issues(base.get("missingEvidence"), base.get("dataQuality")),
        "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
    }


def _baseline_readiness(
    *,
    base: Mapping[str, Any],
    evidence_limits: Sequence[str],
    fixture_source_class: str | None,
) -> dict[str, Any]:
    source_class = fixture_source_class or _normalized_token(base.get("sourceClass"))
    sample_state = _sample_state(source_class)
    data_state = _data_state(base=base, sample_state=sample_state)
    source_authority_allowed = bool(base.get("sourceAuthorityAllowed"))
    baseline_snapshot = _baseline_snapshot_component(
        base=base,
        source_authority_allowed=source_authority_allowed,
        data_state=data_state,
    )
    market_frame = _market_frame_component(base=base)
    driver_inputs = _driver_inputs_component(base)
    evidence = _evidence_completeness_component(
        baseline_snapshot=baseline_snapshot,
        market_frame=market_frame,
        driver_inputs=driver_inputs,
        evidence_limits=evidence_limits,
        data_state=data_state,
        source_authority_allowed=source_authority_allowed,
    )
    ready = evidence["state"] == "ready"
    blocked = evidence["state"] == "blocked"
    partial = not ready and not blocked
    last_updated = _first_text(
        baseline_snapshot.get("lastUpdated"),
        market_frame.get("lastUpdated"),
        base.get("lastUpdated"),
    )
    score_authority = "authoritative" if ready and source_authority_allowed else "observation_only"
    affected_baseline_components = _dedupe(
        [
            *baseline_snapshot["affectedComponents"],
            *market_frame["affectedComponents"],
        ]
    )
    evidence_gaps = _dedupe([*evidence["gaps"], *affected_baseline_components])
    return {
        "status": "ready" if ready else "blocked" if blocked else "partial",
        "baselineSnapshot": baseline_snapshot,
        "marketFrame": market_frame,
        "driverInputs": driver_inputs,
        "evidenceCompleteness": evidence,
        "dataState": data_state,
        "sampleState": sample_state,
        "scoreAuthority": score_authority,
        "sourceAuthorityAllowed": source_authority_allowed,
        "authoritative": score_authority == "authoritative",
        "observationOnly": score_authority != "authoritative",
        "ready": ready,
        "partial": partial,
        "blocked": blocked,
        "affectedBaselineComponents": affected_baseline_components,
        "affectedDriverKeys": driver_inputs["affectedDriverKeys"],
        "evidenceGaps": evidence_gaps,
        "lastUpdated": last_updated,
    }


def _baseline_snapshot_component(
    *,
    base: Mapping[str, Any],
    source_authority_allowed: bool,
    data_state: str,
) -> dict[str, Any]:
    snapshot = base.get("baselineSnapshot") if isinstance(base.get("baselineSnapshot"), Mapping) else {}
    state = _component_state(snapshot, default="missing")
    if data_state == "unavailable":
        state = "missing"
    elif state == "available" and (not source_authority_allowed or data_state != "real_cached"):
        state = "partial"
    affected = _component_gaps(
        snapshot,
        fallback=["baselineSnapshot"] if state != "available" else [],
    )
    return {
        "state": state,
        "available": state == "available",
        "lastUpdated": _component_last_updated(snapshot) or base.get("lastUpdated"),
        "affectedComponents": affected,
    }


def _market_frame_component(*, base: Mapping[str, Any]) -> dict[str, Any]:
    frame = base.get("marketFrame") if isinstance(base.get("marketFrame"), Mapping) else {}
    if frame:
        state = _component_state(frame, default="available")
    elif base.get("regime") and int(base.get("scoringDriverCount") or 0) >= _MIN_BASE_SCORING_DRIVERS:
        state = "available"
    else:
        state = "missing"
    if _has_stale_marker(frame, base.get("dataQuality")):
        state = "stale"
    return {
        "state": state,
        "available": state == "available",
        "lastUpdated": _component_last_updated(frame) or base.get("lastUpdated"),
        "affectedComponents": _component_gaps(
            frame,
            fallback=["marketFrame"] if state != "available" else [],
        ),
    }


def _driver_inputs_component(base: Mapping[str, Any]) -> dict[str, Any]:
    evidence_states = base.get("evidenceStates") if isinstance(base.get("evidenceStates"), Mapping) else {}
    available_driver_keys: list[str] = []
    partial_driver_keys: list[str] = []
    missing_driver_keys: list[str] = []
    for key in DRIVER_KEYS:
        state = _normalized_token(evidence_states.get(key))
        score = _number(_mapping_or_empty(base.get("scores")).get(key))
        if state in {"score_grade", "ready", "available"} or (score is not None and score != 0):
            available_driver_keys.append(key)
        elif state in {"limited", "partial", "degraded", "stale"}:
            partial_driver_keys.append(key)
        else:
            missing_driver_keys.append(key)
    if int(base.get("scoringDriverCount") or 0) < _MIN_BASE_SCORING_DRIVERS:
        state = "missing"
    elif missing_driver_keys or partial_driver_keys:
        state = "partial"
    else:
        state = "available"
    return {
        "state": state,
        "availableDriverKeys": available_driver_keys,
        "partialDriverKeys": partial_driver_keys,
        "missingDriverKeys": missing_driver_keys,
        "affectedDriverKeys": _dedupe([*partial_driver_keys, *missing_driver_keys]),
    }


def _evidence_completeness_component(
    *,
    baseline_snapshot: Mapping[str, Any],
    market_frame: Mapping[str, Any],
    driver_inputs: Mapping[str, Any],
    evidence_limits: Sequence[str],
    data_state: str,
    source_authority_allowed: bool,
) -> dict[str, Any]:
    gaps: list[str] = []
    if baseline_snapshot.get("state") != "available":
        gaps.append("baselineSnapshot")
    if market_frame.get("state") != "available":
        gaps.append("marketFrame")
    gaps.extend(str(key) for key in driver_inputs.get("affectedDriverKeys") or [])
    if data_state in {"demo_static_sample", "request_supplied"}:
        gaps.append("scenarioDataBoundary")
    if not source_authority_allowed:
        gaps.append("scoreAuthority")
    if list(evidence_limits) != [_GENERIC_EVIDENCE_LIMIT]:
        gaps.append("evidenceLimits")
    gaps = _dedupe(gaps)
    if baseline_snapshot.get("state") == "missing" or market_frame.get("state") == "missing" or driver_inputs.get("state") == "missing":
        state = "blocked"
    elif gaps:
        state = "partial"
    else:
        state = "ready"
    return {
        "state": state,
        "gaps": gaps,
    }


def _data_state(*, base: Mapping[str, Any], sample_state: str) -> str:
    if int(base.get("scoringDriverCount") or 0) < _MIN_BASE_SCORING_DRIVERS:
        return "unavailable"
    if sample_state != "none":
        return "demo_static_sample"
    source_class = _normalized_token(base.get("sourceClass"))
    if source_class in {_normalized_token(item) for item in _REAL_SOURCE_CLASSES} and base.get("sourceAuthorityAllowed"):
        return "real_cached"
    return "request_supplied"


def _sample_state(source_class: str | None) -> str:
    normalized = _normalized_token(source_class)
    if normalized in _FIXTURE_SOURCE_CLASSES:
        return "fixture" if normalized == "fixture" else normalized
    if normalized in _STATIC_SOURCE_CLASSES:
        return "fallback" if "fallback" in normalized else "static"
    return "none"


def _component_state(component: Mapping[str, Any], *, default: str) -> str:
    raw = _normalized_token(
        component.get("state")
        or component.get("status")
        or component.get("readiness")
        or component.get("freshness")
        or component.get("dataStatus")
    )
    if _has_stale_marker(component):
        return "stale"
    if raw in _MISSING_STATES:
        return "missing"
    if raw in _STALE_STATES:
        return "stale"
    if raw in _PARTIAL_STATES:
        return "partial"
    if raw in _AVAILABLE_STATES:
        return "available"
    if component.get("available") is True:
        return "available"
    if component.get("available") is False:
        return "missing"
    return default


def _component_gaps(component: Mapping[str, Any], *, fallback: Sequence[str]) -> list[str]:
    gaps = [
        str(item)
        for item in (
            component.get("affectedComponents")
            or component.get("missingComponents")
            or component.get("gaps")
            or []
        )
        if str(item)
    ]
    return _dedupe(gaps or list(fallback))


def _component_last_updated(component: Mapping[str, Any]) -> str | None:
    return _first_text(
        component.get("lastUpdated"),
        component.get("updatedAt"),
        component.get("asOf"),
        component.get("timestamp"),
    )


def _has_stale_marker(*components: Any) -> bool:
    for component in components:
        if not isinstance(component, Mapping):
            continue
        if component.get("isStale") is True or component.get("stale") is True:
            return True
        freshness = _normalized_token(component.get("freshness") or component.get("status") or component.get("state"))
        if freshness in _STALE_STATES:
            return True
    return False


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _truthy(*values: Any) -> bool:
    return any(value is True or str(value).strip().lower() in {"true", "1", "yes"} for value in values)


def _normalized_token(value: Any) -> str:
    return str(value or "").strip().replace("-", "_").lower()


def _confirm_invalidate_context(
    *,
    status: str,
    message: str,
    confirm: Sequence[str],
    invalidate: Sequence[str],
) -> dict[str, Any]:
    return {
        "status": status,
        "message": message,
        "confirm": list(confirm),
        "invalidate": list(invalidate),
    }


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return number


def _clamp_score(value: float) -> int:
    return int(round(max(-100, min(100, value))))


def _clamp_delta(value: float) -> int:
    return int(round(max(-200, min(200, value))))


def _dedupe(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


__all__ = [
    "DRIVER_KEYS",
    "MarketScenarioLabEngine",
    "NO_ADVICE_DISCLOSURE",
    "SCHEMA_VERSION",
    "build_market_scenario_lab",
]
