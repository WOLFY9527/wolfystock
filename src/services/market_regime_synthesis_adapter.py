# -*- coding: utf-8 -*-
"""Market Overview -> regime synthesis adapter.

This module only transforms already-normalized Market Overview / Market
Temperature snapshots into deterministic regime synthesis evidence. It does not
fetch providers, call networks, mutate cache state, or change scoring logic in
other Market Intelligence surfaces.
"""

from __future__ import annotations

from datetime import datetime, timezone
import statistics
from typing import Any, Mapping, Sequence

from src.services.liquidity_impulse_synthesis_service import (
    LiquidityImpulseEvidenceItem,
    synthesize_liquidity_impulse,
)
from src.services.market_regime_synthesis_service import (
    MarketRegimeEvidenceItem,
    synthesize_market_regime,
)


MARKET_REGIME_RESEARCH_SYNTHESIS_VERSION = "market_regime_synthesis_research_v1"

_PANEL_SYMBOL_PILLARS: dict[str, dict[str, str]] = {
    "futures": {
        "ES": "risk_appetite",
        "NQ": "risk_appetite",
        "YM": "risk_appetite",
        "RTY": "risk_appetite",
        "RUT": "risk_appetite",
        "SPX": "risk_appetite",
        "NDX": "risk_appetite",
        "DJI": "risk_appetite",
        "CN00Y": "china_risk_appetite",
        "HSI_F": "china_risk_appetite",
    },
    "indices": {
        "HSI": "china_risk_appetite",
        "HSTECH": "china_risk_appetite",
        "HSI.HK": "china_risk_appetite",
        "HSTECH.HK": "china_risk_appetite",
        "CSI300": "china_risk_appetite",
        "000300.SH": "china_risk_appetite",
        "000300.SS": "china_risk_appetite",
        "000001.SH": "china_risk_appetite",
        "399001.SZ": "china_risk_appetite",
        "399006.SZ": "china_risk_appetite",
        "CN00Y": "china_risk_appetite",
    },
    "rates": {
        "VIX": "volatility_stress",
        "US10Y": "rates_pressure",
        "US30Y": "rates_pressure",
    },
    "fx": {
        "DXY": "dollar_pressure",
        "USDCNH": "dollar_pressure",
    },
    "crypto": {
        "BTC": "crypto_risk_beta",
        "ETH": "crypto_risk_beta",
    },
}

_RESEARCH_FAMILIES: tuple[dict[str, Any], ...] = (
    {
        "key": "marketOverview",
        "label": "Market overview",
        "pillars": (
            "risk_appetite",
            "rates_pressure",
            "dollar_pressure",
            "volatility_stress",
            "crypto_risk_beta",
            "china_risk_appetite",
        ),
    },
    {
        "key": "liquidity",
        "label": "Liquidity",
        "pillars": ("liquidity_impulse",),
    },
    {
        "key": "rotation",
        "label": "Rotation",
        "pillars": ("rotation_leadership",),
    },
    {
        "key": "breadth",
        "label": "Breadth",
        "pillars": ("breadth_health",),
    },
    {
        "key": "riskRegime",
        "label": "Risk regime",
        "pillars": (),
    },
)

_PILLAR_FAMILY: dict[str, str] = {
    pillar: str(family["key"])
    for family in _RESEARCH_FAMILIES
    for pillar in family["pillars"]
}

_REGIME_LABELS = {
    "risk_on_liquidity_expansion": "Risk-supportive liquidity expansion",
    "risk_off_deleveraging": "Risk defensive deleveraging",
    "rates_shock_duration_pressure": "Rates and duration pressure",
    "dollar_squeeze": "Dollar squeeze pressure",
    "credit_or_funding_stress": "Credit or funding stress",
    "term_premium_or_inflation_scare": "Term premium or inflation pressure",
    "goldilocks_soft_landing": "Soft-landing risk support",
    "nacho_mega_cap_defensive_rotation": "Narrow leadership rotation",
    "china_policy_divergence": "China policy divergence",
    "data_insufficient": "Evidence insufficient",
}

_RISK_SUPPORTIVE_REGIMES = {
    "risk_on_liquidity_expansion",
    "goldilocks_soft_landing",
}

_RISK_DEFENSIVE_REGIMES = {
    "risk_off_deleveraging",
    "rates_shock_duration_pressure",
    "dollar_squeeze",
    "credit_or_funding_stress",
    "term_premium_or_inflation_scare",
}

_SAFE_GAP_REASONS = {
    "missing_scoring_evidence": "Evidence family has no score-contributing observation.",
    "score_contribution_not_allowed": "Evidence remains observation-only.",
    "freshness_unavailable": "Fresh evidence is unavailable.",
    "degradation_unavailable_or_rejected": "Evidence quality is not sufficient for scoring.",
    "missing_direction_or_magnitude": "Direction or magnitude is missing.",
    "unknown_pillar": "Evidence family is not recognized.",
    "unscorable": "Evidence is not score-contributing.",
}


def build_market_regime_evidence_items(inputs: Mapping[str, Any]) -> tuple[MarketRegimeEvidenceItem, ...]:
    """Project normalized temperature inputs into regime synthesis evidence."""

    evidence: list[MarketRegimeEvidenceItem] = []

    for panel_key, symbol_map in _PANEL_SYMBOL_PILLARS.items():
        panel = inputs.get(panel_key)
        if not isinstance(panel, Mapping):
            continue
        items = panel.get("items")
        if not isinstance(items, Sequence):
            continue
        for raw_item in items:
            if not isinstance(raw_item, Mapping):
                continue
            symbol = _text(raw_item.get("symbol")).upper()
            if not symbol:
                continue
            pillar = symbol_map.get(symbol)
            if pillar is None:
                continue
            evidence.append(_change_driven_evidence(panel_key, panel, raw_item, pillar))

    breadth_panel = inputs.get("breadth")
    if isinstance(breadth_panel, Mapping):
        items = breadth_panel.get("items")
        if isinstance(items, Sequence):
            for raw_item in items:
                if not isinstance(raw_item, Mapping):
                    continue
                symbol = _text(raw_item.get("symbol")).upper()
                if symbol == "ADV_RATIO":
                    evidence.append(_breadth_percentile_evidence("breadth", breadth_panel, raw_item))

    rotation_evidence = _rotation_leadership_evidence(inputs)
    if rotation_evidence is not None:
        evidence.append(rotation_evidence)

    liquidity_evidence = _liquidity_impulse_evidence(inputs)
    if liquidity_evidence is not None:
        evidence.append(liquidity_evidence)

    return tuple(evidence)


def synthesize_market_regime_from_temperature_inputs(inputs: Mapping[str, Any]):
    """Run deterministic regime synthesis against normalized temperature inputs."""

    return synthesize_market_regime(build_market_regime_evidence_items(inputs))


def build_market_regime_synthesis_payload(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Return the camelCase payload that backend callers can surface later."""

    evidence_items = build_market_regime_evidence_items(inputs)
    payload = synthesize_market_regime(evidence_items).to_dict()
    payload.update(_build_research_synthesis_contract(payload, evidence_items))
    return payload


def build_liquidity_impulse_synthesis_payload(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Project normalized temperature inputs into liquidity synthesis payload."""

    return synthesize_liquidity_impulse(_projected_liquidity_evidence_items(inputs)).to_dict()


def _build_research_synthesis_contract(
    payload: Mapping[str, Any],
    evidence_items: Sequence[MarketRegimeEvidenceItem],
) -> dict[str, Any]:
    primary_regime = _text(payload.get("primaryRegime")) or "data_insufficient"
    confidence = _bounded_unit(payload.get("confidence"))
    evidence_quality = _mapping(payload.get("evidenceQuality"))
    confidence_cap = _confidence_cap(payload, evidence_quality, confidence)
    missing_evidence = _missing_evidence(payload)
    supportive_evidence = _supportive_evidence(payload)
    contradictory_evidence = _contradictory_evidence(payload)
    return {
        "contractVersion": MARKET_REGIME_RESEARCH_SYNTHESIS_VERSION,
        "regimeLabel": _REGIME_LABELS.get(primary_regime, primary_regime),
        "regimePosture": _regime_posture(primary_regime),
        "evidenceFamilies": _evidence_families(
            payload=payload,
            evidence_items=evidence_items,
            supportive_evidence=supportive_evidence,
            contradictory_evidence=contradictory_evidence,
            missing_evidence=missing_evidence,
        ),
        "supportiveEvidence": supportive_evidence,
        "contradictoryEvidence": contradictory_evidence,
        "missingEvidence": missing_evidence,
        "confidenceCap": confidence_cap,
        "observationBoundary": {
            "observationOnly": True,
            "decisionGrade": False,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "consumerActionBoundary": "no_advice",
            "notInvestmentAdvice": True,
            "detail": "Research synthesis only; evidence is not promoted into execution or personalized direction.",
        },
        "researchNextSteps": _research_next_steps(
            missing_evidence=missing_evidence,
            contradictory_evidence=contradictory_evidence,
            confidence_cap=confidence_cap,
        ),
        "generatedAt": _utc_now_iso(),
        "freshness": _research_freshness(payload, evidence_items),
    }


def _evidence_families(
    *,
    payload: Mapping[str, Any],
    evidence_items: Sequence[MarketRegimeEvidenceItem],
    supportive_evidence: Sequence[Mapping[str, Any]],
    contradictory_evidence: Sequence[Mapping[str, Any]],
    missing_evidence: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    evidence_count_by_family: dict[str, int] = {str(family["key"]): 0 for family in _RESEARCH_FAMILIES}
    freshness_by_family: dict[str, list[str]] = {str(family["key"]): [] for family in _RESEARCH_FAMILIES}
    for item in evidence_items:
        family_key = _family_for_pillar(item.pillar or item.category)
        evidence_count_by_family[family_key] = evidence_count_by_family.get(family_key, 0) + 1
        if item.freshness:
            freshness_by_family.setdefault(family_key, []).append(item.freshness)

    supportive_count_by_family = _count_by_family(supportive_evidence)
    contradictory_count_by_family = _count_by_family(contradictory_evidence)
    missing_count_by_family = _count_by_family(missing_evidence)
    covered = set(_sequence(_mapping(payload.get("evidenceQuality")).get("coveredPillars")))
    missing = set(_sequence(_mapping(payload.get("evidenceQuality")).get("missingPillars")))

    families: list[dict[str, Any]] = []
    for family in _RESEARCH_FAMILIES:
        key = str(family["key"])
        pillars = tuple(str(pillar) for pillar in family["pillars"])
        if key == "riskRegime":
            state = "supported" if _text(payload.get("primaryRegime")) != "data_insufficient" else "missing"
        elif any(pillar in covered for pillar in pillars):
            state = "supported"
        elif any(pillar in missing for pillar in pillars) or missing_count_by_family.get(key, 0):
            state = "missing"
        elif evidence_count_by_family.get(key, 0):
            state = "discounted"
        else:
            state = "missing"
        families.append(
            {
                "key": key,
                "label": str(family["label"]),
                "state": state,
                "pillars": list(pillars),
                "evidenceCount": evidence_count_by_family.get(key, 0),
                "supportiveCount": supportive_count_by_family.get(key, 0),
                "contradictoryCount": contradictory_count_by_family.get(key, 0),
                "missingCount": missing_count_by_family.get(key, 0),
                "freshness": _worst_freshness(freshness_by_family.get(key, [])),
                "observationOnly": True,
            }
        )
    return families


def _supportive_evidence(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in _sequence(payload.get("topDrivers"))[:6]:
        if not isinstance(raw, Mapping):
            continue
        pillar = _text(raw.get("pillar"))
        result.append(
            {
                "key": _text(raw.get("key")) or f"driver:{len(result) + 1}",
                "label": _text(raw.get("label")) or "Evidence driver",
                "family": _family_for_pillar(pillar),
                "pillar": pillar or "unknown",
                "direction": _safe_direction(raw.get("direction")),
                "freshness": _safe_freshness(raw.get("freshness")),
                "observationOnly": True,
            }
        )
    return result


def _contradictory_evidence(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in _sequence(payload.get("counterEvidence"))[:6]:
        if not isinstance(raw, Mapping):
            continue
        pillar = _text(raw.get("pillar"))
        result.append(
            {
                "key": _text(raw.get("key")) or f"counter:{len(result) + 1}",
                "label": _text(raw.get("label")) or "Contradictory evidence",
                "family": _family_for_pillar(pillar),
                "pillar": pillar or "unknown",
                "reason": _safe_gap_reason(raw.get("reason")),
                "observationOnly": True,
            }
        )
    return result


def _missing_evidence(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in _sequence(payload.get("dataGaps")):
        if not isinstance(raw, Mapping):
            continue
        pillar = _text(raw.get("pillar"))
        key = _text(raw.get("key")) or f"missing:{pillar or len(result) + 1}"
        if key in {item["key"] for item in result}:
            continue
        result.append(
            {
                "key": key,
                "label": _text(raw.get("label")) or _missing_label(pillar),
                "family": _family_for_pillar(pillar),
                "pillar": pillar or "unknown",
                "reason": _safe_gap_reason(raw.get("reason")),
                "observationOnly": True,
            }
        )
        if len(result) >= 12:
            break
    return result


def _confidence_cap(
    payload: Mapping[str, Any],
    evidence_quality: Mapping[str, Any],
    confidence: float,
) -> dict[str, Any]:
    cap = confidence
    reasons: list[str] = []
    if _int(evidence_quality.get("observationOnlyEvidenceCount")) > 0:
        cap = min(cap, 0.55)
        reasons.append("observation_only_evidence")
    if _int(evidence_quality.get("scoreBlockedEvidenceCount")) > 0:
        cap = min(cap, 0.45)
        reasons.append("score_blocked_evidence")
    if _int(evidence_quality.get("dataGapCount")) > 0:
        cap = min(cap, 0.62)
        reasons.append("missing_evidence")
    if _int(evidence_quality.get("discountedEvidenceCount")) > 0:
        cap = min(cap, 0.68)
        reasons.append("discounted_evidence")
    if payload.get("counterEvidence"):
        cap = min(cap, 0.58)
        reasons.append("contradictory_evidence")
    if _text(payload.get("primaryRegime")) == "data_insufficient":
        cap = min(cap, 0.35)
        reasons.append("data_insufficient")
    cap = round(max(0.0, min(confidence, cap)), 3)
    return {
        "value": cap,
        "label": _confidence_label(cap),
        "reasons": reasons or ["bounded_research_synthesis"],
    }


def _research_next_steps(
    *,
    missing_evidence: Sequence[Mapping[str, Any]],
    contradictory_evidence: Sequence[Mapping[str, Any]],
    confidence_cap: Mapping[str, Any],
) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    if missing_evidence:
        families = _unique_text(item.get("family") for item in missing_evidence)[:3]
        steps.append(
            {
                "key": "fill_missing_evidence",
                "label": "Fill missing evidence families",
                "detail": "Re-check " + ", ".join(families) + " before raising confidence.",
            }
        )
    if contradictory_evidence:
        steps.append(
            {
                "key": "review_contradictions",
                "label": "Review contradictory evidence",
                "detail": "Compare the conflicting families before treating one regime as dominant.",
            }
        )
    if confidence_cap.get("reasons"):
        steps.append(
            {
                "key": "respect_confidence_cap",
                "label": "Respect confidence cap",
                "detail": "Keep the synthesis observational while cap reasons remain active.",
            }
        )
    if not steps:
        steps.append(
            {
                "key": "monitor_persistence",
                "label": "Monitor persistence",
                "detail": "Look for repeated confirmation across the same evidence families.",
            }
        )
    return steps


def _research_freshness(
    payload: Mapping[str, Any],
    evidence_items: Sequence[MarketRegimeEvidenceItem],
) -> str:
    return _worst_freshness(
        [
            payload.get("freshness"),
            *[item.freshness for item in evidence_items],
            *[
                raw.get("freshness")
                for raw in _sequence(payload.get("topDrivers"))
                if isinstance(raw, Mapping)
            ],
        ]
    )


def _regime_posture(primary_regime: str) -> str:
    if primary_regime in _RISK_SUPPORTIVE_REGIMES:
        return "risk_supportive"
    if primary_regime in _RISK_DEFENSIVE_REGIMES:
        return "risk_defensive"
    if primary_regime == "data_insufficient":
        return "data_insufficient"
    return "mixed_or_transition"


def _change_driven_evidence(
    panel_key: str,
    panel: Mapping[str, Any],
    item: Mapping[str, Any],
    pillar: str,
) -> MarketRegimeEvidenceItem:
    change = _first_float(item.get("changePercent"), item.get("change_pct"), item.get("change"))
    return MarketRegimeEvidenceItem(
        key=_evidence_key(panel_key, item),
        label=_label(item),
        category=panel_key,
        pillar=pillar,
        change=change,
        direction=_direction_text(item, change=change),
        source=_text(item.get("source") or panel.get("source")),
        source_tier=_source_tier(item, panel),
        trust_level=_text(item.get("trustLevel") or panel.get("trustLevel")) or "unknown",
        freshness=_text(item.get("freshness") or panel.get("freshness")) or "unknown",
        observation_only=_bool(item.get("observationOnly"), item.get("observation_only"), panel.get("observationOnly")),
        score_contribution_allowed=_bool(
            item.get("scoreContributionAllowed"),
            item.get("score_contribution_allowed"),
            panel.get("scoreContributionAllowed"),
            default=True,
        ),
        as_of=_text(item.get("asOf") or panel.get("asOf")) or None,
        updated_at=_text(item.get("updatedAt") or panel.get("updatedAt")) or None,
        degradation_reason=_degradation_reason(item, panel),
    )


def _breadth_percentile_evidence(
    panel_key: str,
    panel: Mapping[str, Any],
    item: Mapping[str, Any],
) -> MarketRegimeEvidenceItem:
    percentile = _bounded_percentile(item.get("value"))
    return MarketRegimeEvidenceItem(
        key=_evidence_key(panel_key, item),
        label=_label(item),
        category=panel_key,
        pillar="breadth_health",
        percentile=percentile,
        direction=_breadth_direction(item, percentile),
        source=_text(item.get("source") or panel.get("source")),
        source_tier=_source_tier(item, panel),
        trust_level=_text(item.get("trustLevel") or panel.get("trustLevel")) or "unknown",
        freshness=_text(item.get("freshness") or panel.get("freshness")) or "unknown",
        observation_only=_bool(item.get("observationOnly"), item.get("observation_only"), panel.get("observationOnly")),
        score_contribution_allowed=_bool(
            item.get("scoreContributionAllowed"),
            item.get("score_contribution_allowed"),
            panel.get("scoreContributionAllowed"),
            default=True,
        ),
        as_of=_text(item.get("asOf") or panel.get("asOf")) or None,
        updated_at=_text(item.get("updatedAt") or panel.get("updatedAt")) or None,
        degradation_reason=_degradation_reason(item, panel),
    )


def _rotation_leadership_evidence(inputs: Mapping[str, Any]) -> MarketRegimeEvidenceItem | None:
    panel = inputs.get("sectors")
    if not isinstance(panel, Mapping):
        return None
    items = panel.get("items")
    if not isinstance(items, Sequence):
        return None

    candidates = [item for item in items if isinstance(item, Mapping) and _rotation_item_allowed(item)]
    if candidates:
        return _rotation_leadership_from_items("sectors", panel, candidates, score_allowed=True)

    blocked = [item for item in items if isinstance(item, Mapping) and _rotation_item_relevant(item)]
    if not blocked:
        return None
    return _rotation_leadership_from_items("sectors", panel, blocked, score_allowed=False)


def _rotation_leadership_from_items(
    panel_key: str,
    panel: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
    *,
    score_allowed: bool,
) -> MarketRegimeEvidenceItem:
    avg_rotation_score = _average_float(
        _optional_float(item.get("rotationScore")) for item in items
    )
    avg_change = _average_float(
        _optional_float(item.get("changePercent") or item.get("change")) for item in items
    )
    primary = items[0]
    source_reason = _rotation_degradation_reason(primary, panel)
    if score_allowed:
        source_tier = _text(primary.get("sourceTier") or primary.get("sourceType") or primary.get("source"))
        trust_level = _text(primary.get("trustLevel")) or "usable"
        freshness = _text(primary.get("freshness") or panel.get("freshness")) or "unknown"
        direction = _direction_text(primary, change=avg_change, value=avg_rotation_score)
        source = _text(primary.get("source") or panel.get("source") or "rotation_radar_projection")
        degradation_reason = source_reason
        observation_only = _bool(primary.get("observationOnly"), panel.get("observationOnly"))
        score_contribution_allowed = True
    else:
        source_tier = _text(primary.get("sourceTier") or primary.get("sourceType") or primary.get("source"))
        trust_level = _text(primary.get("trustLevel")) or "unavailable"
        freshness = _text(primary.get("freshness") or panel.get("freshness")) or "unavailable"
        direction = _direction_text(primary, change=avg_change, value=avg_rotation_score)
        source = _text(primary.get("source") or panel.get("source") or "rotation_radar_projection")
        degradation_reason = (
            source_reason
            or _text(primary.get("sourceAuthorityReason"))
            or _first_text(primary.get("degradationReason"), primary.get("rankExclusionReason"))
            or "score_contribution_not_allowed"
        )
        observation_only = True
        score_contribution_allowed = False

    return MarketRegimeEvidenceItem(
        key="sectors:rotation_leadership",
        label="Rotation Leadership",
        category=panel_key,
        pillar="rotation_leadership",
        value=avg_rotation_score,
        percentile=avg_rotation_score,
        direction=direction,
        source=source,
        source_tier=source_tier,
        trust_level=trust_level,
        freshness=freshness,
        observation_only=observation_only,
        score_contribution_allowed=score_contribution_allowed,
        as_of=_text(primary.get("asOf") or panel.get("asOf")) or None,
        updated_at=_text(primary.get("updatedAt") or panel.get("updatedAt")) or None,
        degradation_reason=degradation_reason,
    )


def _rotation_item_allowed(item: Mapping[str, Any]) -> bool:
    if not _rotation_item_relevant(item):
        return False
    if not _bool(item.get("sourceAuthorityAllowed"), default=True):
        return False
    if not _bool(item.get("scoreContributionAllowed"), default=True):
        return False
    if "rankEligible" in item and not _bool(item.get("rankEligible")):
        return False
    if "headlineEligible" in item and not _bool(item.get("headlineEligible")):
        return False
    return True


def _rotation_item_relevant(item: Mapping[str, Any]) -> bool:
    return _text(item.get("symbol") or item.get("name") or item.get("id")) != ""


def _rotation_degradation_reason(item: Mapping[str, Any], panel: Mapping[str, Any]) -> str | None:
    return _first_text(
        item.get("sourceAuthorityReason"),
        item.get("degradationReason"),
        item.get("rankExclusionReason"),
        panel.get("degradationReason"),
    )


def _liquidity_impulse_evidence(inputs: Mapping[str, Any]) -> MarketRegimeEvidenceItem | None:
    projected = tuple(_projected_liquidity_evidence_items(inputs))
    if not projected:
        return None

    result = synthesize_liquidity_impulse(projected)
    freshness = _worst_freshness(item.freshness for item in projected)
    trust_level = _liquidity_trust_level(result.confidence_label)
    source_tier = "computed_from_real" if int(result.evidence_quality.get("realScoringEvidenceCount") or 0) > 0 and result.liquidity_impulse != "data_insufficient" else "computed_from_data_gap"
    source = "liquidity_monitor_projection"
    as_of = _first_text(*(item.as_of for item in projected)) or None
    updated_at = _first_text(*(item.updated_at for item in projected)) or None
    direction = "up" if result.direction_score > 0 else "down" if result.direction_score < 0 else None
    score_allowed = result.liquidity_impulse != "data_insufficient" and int(result.evidence_quality.get("realScoringEvidenceCount") or 0) > 0
    degradation_reason = None
    if not score_allowed:
        degradation_reason = _first_text(
            *(gap.get("reason") for gap in result.data_gaps if isinstance(gap, Mapping)),
            result.subtype,
        )

    return MarketRegimeEvidenceItem(
        key="liquidity_monitor:liquidity_impulse",
        label="Liquidity Impulse",
        category="liquidity_monitor",
        pillar="liquidity_impulse",
        value=result.direction_score,
        direction=direction,
        source=source,
        source_tier=source_tier,
        trust_level=trust_level,
        freshness=freshness,
        observation_only=any(item.observation_only for item in projected),
        score_contribution_allowed=score_allowed,
        as_of=as_of,
        updated_at=updated_at,
        degradation_reason=degradation_reason,
    )


def _projected_liquidity_evidence_items(inputs: Mapping[str, Any]) -> tuple[LiquidityImpulseEvidenceItem, ...]:
    evidence: list[LiquidityImpulseEvidenceItem] = []
    panels = {
        "rates": inputs.get("rates"),
        "fx": inputs.get("fx"),
        "futures": inputs.get("futures"),
        "crypto": inputs.get("crypto"),
        "breadth": inputs.get("breadth"),
        "flows": inputs.get("flows"),
    }
    if isinstance(panels["rates"], Mapping):
        items = panels["rates"].get("items")
        if isinstance(items, Sequence):
            for symbol, pillar in (("US10Y", "rates_pressure"), ("VIX", "volatility_stress")):
                raw_item = _first_mapping_item(items, symbol)
                if raw_item is not None:
                    evidence.append(_liquidity_evidence_from_item("rates", raw_item, pillar))
    if isinstance(panels["fx"], Mapping):
        items = panels["fx"].get("items")
        if isinstance(items, Sequence):
            for symbol in ("DXY", "USDCNH"):
                raw_item = _first_mapping_item(items, symbol)
                if raw_item is not None:
                    evidence.append(_liquidity_evidence_from_item("fx", raw_item, "dollar_pressure"))
    if isinstance(panels["futures"], Mapping):
        items = panels["futures"].get("items")
        if isinstance(items, Sequence):
            for symbol in ("ES", "NQ", "YM", "RTY"):
                raw_item = _first_mapping_item(items, symbol)
                if raw_item is not None:
                    evidence.append(_liquidity_evidence_from_item("futures", raw_item, "risk_asset_demand"))
    if isinstance(panels["crypto"], Mapping):
        items = panels["crypto"].get("items")
        if isinstance(items, Sequence):
            for symbol in ("BTC", "ETH", "BNB"):
                raw_item = _first_mapping_item(items, symbol)
                if raw_item is not None:
                    evidence.append(_liquidity_evidence_from_item("crypto", raw_item, "crypto_liquidity_beta"))
    if isinstance(panels["breadth"], Mapping):
        items = panels["breadth"].get("items")
        if isinstance(items, Sequence):
            raw_item = _first_mapping_item(items, "ADV_RATIO")
            if raw_item is not None:
                evidence.append(_liquidity_breadth_evidence(raw_item))
    if isinstance(panels["flows"], Mapping):
        items = panels["flows"].get("items")
        if isinstance(items, Sequence):
            for symbol, pillar in (("CN_ETF", "equity_flow_proxy"), ("NORTHBOUND", "china_liquidity_context")):
                raw_item = _first_mapping_item(items, symbol)
                if raw_item is not None:
                    evidence.append(_liquidity_evidence_from_item("flows", raw_item, pillar))
    return tuple(evidence)


def _liquidity_evidence_from_item(
    panel_key: str,
    item: Mapping[str, Any],
    pillar: str,
) -> LiquidityImpulseEvidenceItem:
    score_allowed = _liquidity_item_allowed(item)
    source = _text(item.get("source") or "liquidity_monitor_projection")
    source_tier = _text(item.get("sourceTier") or item.get("sourceType") or source)
    trust_level = _text(item.get("trustLevel")) or "unknown"
    freshness = _text(item.get("freshness")) or "unknown"
    observation_only = _bool(item.get("observationOnly"))
    proxy_only = not _bool(item.get("sourceAuthorityAllowed"), default=True) or source_tier in {"unofficial_proxy", "unofficial_public_api", "public_proxy"}
    included_in_score = score_allowed if score_allowed else False
    direction, magnitude = _liquidity_direction_and_magnitude(panel_key, item, pillar)
    degradation_reason = None if score_allowed else _first_text(
        item.get("sourceAuthorityReason"),
        item.get("degradationReason"),
        "score_contribution_not_allowed",
    )
    return LiquidityImpulseEvidenceItem(
        key=f"liquidity_bridge:{panel_key}:{_text(item.get('symbol') or item.get('key'))}",
        label=_label(item),
        category=panel_key,
        pillar=pillar,
        value=magnitude,
        change=magnitude,
        direction=direction,
        source=source,
        source_tier=source_tier,
        trust_level=trust_level,
        freshness=freshness,
        observation_only=observation_only,
        score_contribution_allowed=score_allowed,
        included_in_score=included_in_score,
        proxy_only=proxy_only,
        as_of=_text(item.get("asOf") or item.get("updatedAt")) or None,
        updated_at=_text(item.get("updatedAt") or item.get("asOf")) or None,
        degradation_reason=degradation_reason,
    )


def _liquidity_breadth_evidence(item: Mapping[str, Any]) -> LiquidityImpulseEvidenceItem:
    score_allowed = _liquidity_item_allowed(item)
    source = _text(item.get("source") or "liquidity_monitor_projection")
    source_tier = _text(item.get("sourceTier") or item.get("sourceType") or source)
    trust_level = _text(item.get("trustLevel")) or "unknown"
    freshness = _text(item.get("freshness")) or "unknown"
    observation_only = _bool(item.get("observationOnly"))
    proxy_only = not _bool(item.get("sourceAuthorityAllowed"), default=True) or source_tier in {"unofficial_proxy", "unofficial_public_api", "public_proxy"}
    percentile = _bounded_percentile(item.get("value"))
    direction = _breadth_direction(item, percentile)
    degradation_reason = None if score_allowed else _first_text(
        item.get("sourceAuthorityReason"),
        item.get("degradationReason"),
        "score_contribution_not_allowed",
    )
    return LiquidityImpulseEvidenceItem(
        key=f"liquidity_bridge:breadth:{_text(item.get('symbol') or item.get('key'))}",
        label=_label(item),
        category="breadth",
        pillar="breadth_confirmation",
        value=percentile,
        percentile=percentile,
        direction=direction,
        source=source,
        source_tier=source_tier,
        trust_level=trust_level,
        freshness=freshness,
        observation_only=observation_only,
        score_contribution_allowed=score_allowed,
        included_in_score=score_allowed if score_allowed else False,
        proxy_only=proxy_only,
        as_of=_text(item.get("asOf") or item.get("updatedAt")) or None,
        updated_at=_text(item.get("updatedAt") or item.get("asOf")) or None,
        degradation_reason=degradation_reason,
    )


def _liquidity_item_allowed(item: Mapping[str, Any]) -> bool:
    if not _bool(item.get("scoreContributionAllowed"), default=True):
        return False
    if "sourceAuthorityAllowed" in item and not _bool(item.get("sourceAuthorityAllowed")):
        return False
    if _text(item.get("sourceAuthorityReason")) in {"proxy_context_only", "source_authority_router_rejected", "provider_absent"}:
        return False
    if _text(item.get("sourceTier") or item.get("sourceType")) in {"unofficial_proxy", "public_proxy", "unofficial_public_api"}:
        return False
    if _bool(item.get("observationOnly")):
        return False
    return True


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> tuple[Any, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(value)
    return ()


def _family_for_pillar(pillar: Any) -> str:
    normalized = _text(pillar)
    if normalized in _PILLAR_FAMILY:
        return _PILLAR_FAMILY[normalized]
    if normalized.startswith("liquidity"):
        return "liquidity"
    if "rotation" in normalized:
        return "rotation"
    if "breadth" in normalized:
        return "breadth"
    if normalized:
        return "marketOverview"
    return "riskRegime"


def _count_by_family(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        family = _text(row.get("family")) or "riskRegime"
        result[family] = result.get(family, 0) + 1
    return result


def _bounded_unit(value: Any) -> float:
    numeric = _optional_float(value)
    if numeric is None:
        return 0.0
    return max(0.0, min(1.0, float(numeric)))


def _int(value: Any) -> int:
    numeric = _optional_float(value)
    if numeric is None:
        return 0
    return int(numeric)


def _confidence_label(value: float) -> str:
    if value < 0.35:
        return "insufficient"
    if value < 0.55:
        return "low"
    if value < 0.74:
        return "medium"
    return "high"


def _safe_freshness(value: Any) -> str:
    freshness = _text(value).lower()
    allowed = {
        "live",
        "fresh",
        "cached",
        "delayed",
        "stale",
        "partial",
        "fallback",
        "mock",
        "synthetic",
        "unavailable",
        "error",
        "unknown",
    }
    return freshness if freshness in allowed else "unknown"


def _safe_direction(value: Any) -> str:
    direction = _text(value).lower()
    if direction in {"positive", "negative", "up", "down", "neutral"}:
        return direction
    return "neutral"


def _safe_gap_reason(value: Any) -> str:
    reason = _text(value)
    return _SAFE_GAP_REASONS.get(reason, "Evidence needs more confirmation.")


def _missing_label(pillar: str) -> str:
    if not pillar:
        return "Missing evidence"
    return "Missing evidence for " + pillar.replace("_", " ")


def _unique_text(values: Sequence[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in result:
            result.append(text)
    return result


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _liquidity_direction_and_magnitude(
    panel_key: str,
    item: Mapping[str, Any],
    pillar: str,
) -> tuple[str | None, float | None]:
    change = _first_float(item.get("changePercent"), item.get("change"))
    value = _first_float(item.get("value"), item.get("price"))
    if pillar == "breadth_confirmation":
        percentile = _bounded_percentile(item.get("value"))
        return _breadth_direction(item, percentile), percentile
    if change is not None:
        return _direction_text(item, change=change, value=value), change
    if value is not None:
        return _direction_text(item, change=None, value=value), value
    return None, None


def _first_mapping_item(items: Sequence[Any], symbol: str) -> Mapping[str, Any] | None:
    for raw_item in items:
        if isinstance(raw_item, Mapping) and _text(raw_item.get("symbol")).upper() == symbol.upper():
            return raw_item
    return None


def _average_float(values: Sequence[float | None]) -> float | None:
    finite = [float(value) for value in values if value is not None]
    return round(statistics.fmean(finite), 3) if finite else None


def _worst_freshness(values: Sequence[str]) -> str:
    order = {
        "live": 0,
        "fresh": 0,
        "cached": 1,
        "delayed": 2,
        "stale": 3,
        "partial": 4,
        "fallback": 5,
        "mock": 6,
        "unavailable": 7,
        "error": 8,
    }
    normalized = [(_text(value).lower() or "unknown") for value in values if _text(value)]
    if not normalized:
        return "unknown"
    return max(normalized, key=lambda value: order.get(value, 9))


def _liquidity_trust_level(confidence_label: str) -> str:
    if confidence_label in {"high", "medium"}:
        return "usable"
    if confidence_label == "low":
        return "usable_with_caution"
    return "unavailable"


def _direction_text(
    item: Mapping[str, Any],
    *,
    change: float | None = None,
    value: float | None = None,
) -> str | None:
    raw_direction = _text(
        item.get("direction")
        or item.get("risk_direction")
        or item.get("trendDirection")
    ).lower()
    if raw_direction in {"up", "rising", "higher", "positive", "strong", "improving", "risk_on", "risk-on", "increasing"}:
        return "up"
    if raw_direction in {"down", "falling", "lower", "negative", "weak", "deteriorating", "risk_off", "risk-off", "decreasing"}:
        return "down"
    numeric = change
    if numeric is None:
        numeric = value
    if numeric is None:
        return None
    if numeric > 0:
        return "up"
    if numeric < 0:
        return "down"
    return None


def _breadth_direction(item: Mapping[str, Any], percentile: float | None) -> str | None:
    explicit = _direction_text(item)
    if explicit is not None:
        return explicit
    if percentile is None:
        return None
    if percentile > 50.0:
        return "up"
    if percentile < 50.0:
        return "down"
    return None


def _degradation_reason(item: Mapping[str, Any], panel: Mapping[str, Any]) -> str | None:
    return _text(
        item.get("degradationReason")
        or item.get("sourceAuthorityReason")
        or item.get("excludeReason")
        or item.get("proxyObservationOnlyReason")
        or panel.get("degradationReason")
    ) or None


def _source_tier(item: Mapping[str, Any], panel: Mapping[str, Any]) -> str:
    return (
        _text(item.get("sourceTier"))
        or _text(panel.get("sourceTier"))
        or _text(item.get("sourceType"))
        or _text(panel.get("sourceType"))
        or _text(item.get("source"))
        or _text(panel.get("source"))
    )


def _bounded_percentile(value: Any) -> float | None:
    numeric = _optional_float(value)
    if numeric is None:
        return None
    return max(0.0, min(100.0, float(numeric)))


def _first_float(*values: Any) -> float | None:
    for value in values:
        numeric = _optional_float(value)
        if numeric is not None:
            return numeric
    return None


def _optional_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _evidence_key(panel_key: str, item: Mapping[str, Any]) -> str:
    symbol = _text(item.get("symbol")) or _text(item.get("key")) or "unknown"
    return f"{panel_key}:{symbol}"


def _label(item: Mapping[str, Any]) -> str:
    return _text(item.get("label") or item.get("name") or item.get("symbol")) or "Unknown"


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _bool(*values: Any, default: bool = False) -> bool:
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            return value
        text = _text(value).lower()
        if text in {"true", "1", "yes"}:
            return True
        if text in {"false", "0", "no"}:
            return False
    return default
