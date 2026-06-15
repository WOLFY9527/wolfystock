# -*- coding: utf-8 -*-
"""Deterministic market scenario lab engine.

The engine consumes caller-supplied market regime evidence or normalized driver
scores. It does not read providers, mutate cache state, or produce personalized
financial advice.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "market_scenario_lab_engine.v1"
NO_ADVICE_DISCLOSURE = "Research planning only; not a personalized decision basis."

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
        base = _base_from_inputs(base_decision=base_decision, driver_scores=driver_scores)
        if base["scoringDriverCount"] < _MIN_BASE_SCORING_DRIVERS:
            return _unavailable_payload(base)

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

        return {
            "schemaVersion": SCHEMA_VERSION,
            "baseRegime": {
                "regime": base["regime"],
                "confidence": base["confidence"],
                "confidenceScore": base_confidence_score,
            },
            "scenarioRegime": {
                "regime": scenario_regime,
                "confidence": _confidence_label(scenario_confidence_score),
                "confidenceScore": scenario_confidence_score,
            },
            "confidenceDelta": confidence_delta,
            "driverDeltas": {key: deltas.get(key, 0) for key in DRIVER_KEYS},
            "changedDrivers": changed_drivers,
            "scenarioSummary": _scenario_summary(deltas),
            "whatWouldConfirm": [
                "Score-grade evidence would need to show the stressed drivers moving together in the scenario direction.",
                "The scenario frame would need current breadth, volatility, rates-dollar, liquidity, and cross-asset inputs.",
            ],
            "whatWouldInvalidate": [
                "The scenario frame weakens if score-grade evidence does not move with the selected shocks.",
                "The scenario frame weakens if key drivers are proxy-only, stale, blocked, or observation-only.",
            ],
            "evidenceLimits": _evidence_limits(base, scenario_input),
            "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
        }


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
    }


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


def _scenario_deltas(scenario: Mapping[str, Any]) -> dict[str, int]:
    name = str(scenario.get("name") or scenario.get("scenarioName") or "").strip()
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
        text = str(reason)
        if text and text not in limits:
            limits.append(text)
    return _dedupe(limits) or ["No additional evidence limits were supplied with the base read."]


def _gamma_status(scenario: Mapping[str, Any], base: Mapping[str, Any]) -> str:
    explicit = str(scenario.get("gammaEvidenceStatus") or "").strip().lower()
    if explicit:
        return explicit
    if "gammaUnavailable" == str(scenario.get("name") or scenario.get("scenarioName") or "").strip():
        return "unavailable"
    if base["evidenceStates"].get("dealerGamma") == "unavailable":
        return "unavailable"
    return "available"


def _unavailable_payload(base: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "baseRegime": {
            "regime": base["regime"],
            "confidence": base["confidence"],
            "confidenceScore": base["confidenceScore"],
        },
        "scenarioRegime": {
            "regime": "lowConfidence",
            "confidence": "low",
            "confidenceScore": 0.0,
            "status": "unavailable",
        },
        "confidenceDelta": 0.0,
        "driverDeltas": {},
        "changedDrivers": [],
        "scenarioSummary": ["Scenario lab is unavailable because base score-grade regime evidence is missing."],
        "whatWouldConfirm": [],
        "whatWouldInvalidate": [],
        "evidenceLimits": [
            "Base regime evidence is missing or below the minimum driver coverage for scenario analysis."
        ],
        "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
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
