# -*- coding: utf-8 -*-
"""Pure Market Intelligence actionability projection contract."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.services.research_readiness_contract import build_research_readiness_v1


MARKET_INTELLIGENCE_ACTIONABILITY_VERSION = "market_intelligence_actionability_v1"
_REQUIRED_EVIDENCE = ("macro", "liquidity", "technical")
_DEGRADED_FRESHNESS = {"stale", "fallback", "unavailable", "unknown", "synthetic", "mock", "error"}
_ROTATION_SUPPORTIVE_STATES = {"leading", "broadening", "confirming"}


def build_market_actionability_frame(
    payload: Mapping[str, Any] | None,
    *,
    inputs: Mapping[str, Any] | None = None,
    liquidity_impulse_synthesis: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    market_payload = _mapping(payload)
    input_payload = _mapping(inputs)
    regime = _mapping(market_payload.get("marketRegimeSynthesis"))
    decision = _mapping(market_payload.get("marketDecisionSemantics"))
    direction = _mapping(decision.get("directionReadiness"))
    summary = _mapping(market_payload.get("regimeSummary"))
    liquidity_signal = _mapping(input_payload.get("capitalFlowSignal"))
    liquidity = _mapping(liquidity_impulse_synthesis)
    rotation_rows = _sequence(input_payload.get("rotationFamilyRollup"))
    market_freshness = _market_context_freshness(market_payload, liquidity_signal, rotation_rows)

    evidence: list[dict[str, Any]] = []
    missing: list[str] = []

    macro_present = bool(regime) and _text(regime.get("primaryRegime")).lower() != "data_insufficient"
    macro_score_allowed = (
        bool(market_payload.get("conclusionAllowed"))
        and int(_mapping(direction.get("scoreGradePillars")).get("count") or 0) > 0
        and not _is_degraded_freshness(market_payload.get("freshness"))
    )
    if macro_present:
        evidence.append(
            _evidence_item(
                domain="macro",
                freshness=market_freshness,
                source_type="score_grade" if macro_score_allowed else market_payload.get("sourceType") or market_payload.get("sourceTier"),
                source_tier="score_grade" if macro_score_allowed else market_payload.get("sourceTier"),
                trust_level="score_grade" if macro_score_allowed else market_payload.get("trustLevel"),
                source_allowed=macro_score_allowed,
                score_allowed=macro_score_allowed,
                observation_only=not macro_score_allowed,
                source=market_payload.get("source") or "market_temperature",
            )
        )
    else:
        missing.append("macro")

    technical_status = _text(direction.get("status")).lower()
    technical_present = technical_status in {"direction_ready", "observe_only"} or int(
        _mapping(direction.get("scoreGradePillars")).get("count") or 0
    ) > 0 or int(_mapping(direction.get("observationOnlyPillars")).get("count") or 0) > 0
    technical_score_allowed = technical_status == "direction_ready" and bool(market_payload.get("conclusionAllowed"))
    if technical_present:
        evidence.append(
            _evidence_item(
                domain="technical",
                freshness=market_freshness,
                source_type="score_grade" if technical_score_allowed else market_payload.get("sourceType") or market_payload.get("sourceTier"),
                source_tier="score_grade" if technical_score_allowed else market_payload.get("sourceTier"),
                trust_level="score_grade" if technical_score_allowed else market_payload.get("trustLevel"),
                source_allowed=technical_score_allowed,
                score_allowed=technical_score_allowed,
                observation_only=not technical_score_allowed,
                source=market_payload.get("source") or "market_temperature",
            )
        )
    else:
        missing.append("technical")

    liquidity_present = bool(liquidity_signal) or _text(liquidity.get("liquidityImpulse")).lower() not in {
        "",
        "data_insufficient",
    }
    liquidity_freshness = (
        liquidity_signal.get("freshness")
        or liquidity.get("freshness")
        or market_payload.get("freshness")
        or "unknown"
    )
    liquidity_source_allowed = bool(liquidity_signal.get("sourceAuthorityAllowed"))
    liquidity_score_allowed = bool(liquidity_signal.get("scoreContributionAllowed")) and liquidity_source_allowed
    liquidity_observation_only = (
        bool(liquidity_signal.get("observationOnly"))
        or not liquidity_source_allowed
        or not liquidity_score_allowed
        or _is_degraded_freshness(liquidity_freshness)
    )
    if liquidity_present:
        evidence.append(
            _evidence_item(
                domain="liquidity",
                freshness=liquidity_freshness,
                source_type=liquidity_signal.get("sourceType") or liquidity_signal.get("sourceTier") or "snapshot",
                source_tier=liquidity_signal.get("sourceTier") or liquidity_signal.get("sourceType") or "snapshot",
                trust_level="score_grade" if liquidity_score_allowed else liquidity_signal.get("trustLevel") or market_payload.get("trustLevel"),
                source_allowed=liquidity_source_allowed and not _is_degraded_freshness(liquidity_freshness),
                score_allowed=liquidity_score_allowed and not _is_degraded_freshness(liquidity_freshness),
                observation_only=liquidity_observation_only,
                source=liquidity_signal.get("source") or "liquidity_monitor_projection",
            )
        )
    else:
        missing.append("liquidity")

    worst_freshness = _worst_freshness([market_freshness, liquidity_freshness, *[_mapping(row.get("themeFlowSignal")).get("freshness") for row in rotation_rows]])
    if (
        not bool(market_payload.get("conclusionAllowed"))
        and worst_freshness in {"fallback", "unavailable", "unknown"}
        and _text(regime.get("primaryRegime")).lower() == "data_insufficient"
    ):
        evidence = []
        missing = list(_REQUIRED_EVIDENCE)
    if worst_freshness in _DEGRADED_FRESHNESS:
        _append_unique(missing, "freshness")

    readiness = build_research_readiness_v1(
        {
            "requiredEvidence": list(_REQUIRED_EVIDENCE),
            "missingEvidence": missing,
            "evidence": evidence,
            "sourceAuthorityAllowed": bool(market_payload.get("conclusionAllowed")),
            "scoreContributionAllowed": bool(market_payload.get("conclusionAllowed")),
            "freshness": worst_freshness,
            "noAdviceBoundary": True,
            "consumerActionBoundary": "no_advice",
            "debugRef": "market:temperature:actionability",
        }
    )

    return {
        "contractVersion": MARKET_INTELLIGENCE_ACTIONABILITY_VERSION,
        "verdict": readiness["readinessState"],
        "confidence": _build_confidence(readiness, summary, regime),
        "evidenceCoverage": dict(readiness["evidenceCoverage"]),
        "missingEvidence": list(readiness["missingEvidence"]),
        "regimeContext": {
            "primaryRegime": _text(regime.get("primaryRegime")) or "data_insufficient",
            "liquidityImpulse": _text(liquidity.get("liquidityImpulse")) or "data_insufficient",
            "rotationPosture": _rotation_posture(rotation_rows),
            "contradictionCount": _contradiction_count(summary, liquidity_signal),
            "freshnessFloor": readiness["freshnessFloor"],
        },
        "sourceAuthority": readiness["sourceAuthority"],
        "freshness": readiness["freshnessFloor"],
        "noAdviceBoundary": True,
        "nextResearchStep": _next_research_step(readiness, summary, liquidity_observation_only),
        "debugRef": readiness["debugRef"],
    }


def _build_confidence(
    readiness: Mapping[str, Any],
    summary: Mapping[str, Any],
    regime: Mapping[str, Any],
) -> dict[str, Any]:
    verdict = _text(readiness.get("readinessState")).lower()
    cap_reasons = list(_sequence(readiness.get("blockingReasons")))
    base_value = _float(_mapping(summary.get("confidence")).get("value"))
    if base_value is None:
        base_value = _float(regime.get("confidence"))
    value = max(0.0, min(base_value if base_value is not None else 0.0, 1.0))
    if verdict == "ready":
        label = _text(_mapping(summary.get("confidence")).get("label")) or "medium"
    elif verdict == "observe_only":
        label = "low"
        value = min(value or 0.32, 0.49)
    else:
        label = "insufficient"
        value = min(value, 0.18)
    return {
        "value": round(value, 2),
        "label": label,
        "capReasons": cap_reasons,
    }


def _evidence_item(
    *,
    domain: str,
    freshness: Any,
    source_type: Any,
    source_tier: Any,
    trust_level: Any,
    source_allowed: bool,
    score_allowed: bool,
    observation_only: bool,
    source: Any,
) -> dict[str, Any]:
    return {
        "domain": domain,
        "freshness": _normalize_contract_freshness(freshness) or "unknown",
        "sourceType": _text(source_type) or "unavailable",
        "sourceTier": _text(source_tier) or "unavailable",
        "trustLevel": _text(trust_level) or "unknown",
        "sourceAuthorityAllowed": source_allowed,
        "scoreContributionAllowed": score_allowed,
        "observationOnly": observation_only,
        "source": _text(source) or "unavailable",
    }


def _rotation_posture(rows: Sequence[Mapping[str, Any]]) -> str:
    for row in rows:
        state = _text(_mapping(row.get("themeFlowSignal")).get("themeFlowState")).lower()
        if state in _ROTATION_SUPPORTIVE_STATES:
            return state
    return "unavailable"


def _contradiction_count(summary: Mapping[str, Any], liquidity_signal: Mapping[str, Any]) -> int:
    return len(_sequence(summary.get("contradictions"))) + len(_sequence(liquidity_signal.get("contradictionCodes")))


def _next_research_step(
    readiness: Mapping[str, Any],
    summary: Mapping[str, Any],
    liquidity_observation_only: bool,
) -> str:
    next_needed = _sequence(readiness.get("nextEvidenceNeeded"))
    if next_needed:
        return _text(next_needed[0])
    if liquidity_observation_only:
        return "等待更高授权流动性证据"
    watch_items = _sequence(summary.get("nextWatchItems"))
    if watch_items:
        return _text(_mapping(watch_items[0]).get("label")) or _text(_mapping(watch_items[0]).get("detail"))
    return "继续观察市场证据更新"


def _market_context_freshness(
    market_payload: Mapping[str, Any],
    liquidity_signal: Mapping[str, Any],
    rotation_rows: Sequence[Mapping[str, Any]],
) -> str:
    explicit = _normalize_contract_freshness(
        market_payload.get("freshness")
        or _mapping(market_payload.get("sourceFreshnessEvidence")).get("freshness")
    )
    if explicit:
        return explicit
    derived = _worst_freshness(
        [
            liquidity_signal.get("freshness"),
            *[_mapping(row.get("themeFlowSignal")).get("freshness") for row in rotation_rows],
        ]
    )
    if derived != "unknown":
        return derived
    if bool(market_payload.get("conclusionAllowed")):
        return "fresh"
    return "unknown"


def _worst_freshness(values: Sequence[Any]) -> str:
    order = {
        "fresh": 0,
        "live": 0,
        "delayed": 1,
        "cached": 1,
        "partial": 2,
        "stale": 3,
        "fallback": 4,
        "synthetic": 5,
        "mock": 5,
        "error": 6,
        "unavailable": 6,
        "unknown": 7,
    }
    normalized = []
    for value in values:
        freshness = _normalize_contract_freshness(value)
        if freshness:
            normalized.append(freshness)
    if not normalized:
        return "unknown"
    return max(normalized, key=lambda item: order.get(item, 7))


def _is_degraded_freshness(value: Any) -> bool:
    return _normalize_contract_freshness(value) in _DEGRADED_FRESHNESS


def _normalize_contract_freshness(value: Any) -> str:
    normalized = _text(value).lower()
    if normalized in {"fresh", "live"}:
        return "fresh"
    if normalized in {"cached", "cache", "delayed", "partial"}:
        return "delayed"
    if normalized in {"stale", "fallback", "synthetic", "mock", "error", "unavailable", "unknown"}:
        return normalized
    return ""


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)
