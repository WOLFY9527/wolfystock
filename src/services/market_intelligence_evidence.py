# -*- coding: utf-8 -*-
"""Pure Market Intelligence evidence projection contract."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


MARKET_INTELLIGENCE_EVIDENCE_VERSION = "market_intelligence_evidence_v1"
_DOMAIN_ORDER = ("macro", "liquidity", "rotation", "breadth", "scanner_context")
_DEGRADED_FRESHNESS = {"stale", "fallback", "unavailable", "unknown", "synthetic", "mock", "error"}
_NEXT_EVIDENCE_COPY = {
    "macro": "补充宏观证据",
    "liquidity": "补充流动性证据",
    "rotation": "补充轮动证据",
    "breadth": "补充广度证据",
    "scanner_context": "补充扫描器上下文证据",
    "freshness": "补充新鲜度证据",
}


def build_market_intelligence_evidence_frame(
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
    liquidity_signal = _mapping(input_payload.get("capitalFlowSignal"))
    liquidity = _mapping(liquidity_impulse_synthesis)
    breadth_panel = _mapping(input_payload.get("breadth"))
    rotation_rows = _sequence(input_payload.get("rotationFamilyRollup"))
    scanner_context = _mapping(input_payload.get("scannerContextFrame") or market_payload.get("scannerContextFrame"))
    market_freshness = _market_context_freshness(market_payload, liquidity_signal, rotation_rows)
    market_degraded = not bool(market_payload.get("conclusionAllowed")) and _is_degraded_freshness(
        market_payload.get("freshness") or market_freshness
    )

    regime_evidence = _build_regime_evidence(
        regime=regime,
        direction=direction,
        market_payload=market_payload,
        market_freshness=market_freshness,
        market_degraded=market_degraded,
    )
    liquidity_evidence = _build_liquidity_evidence(
        liquidity_signal=liquidity_signal,
        liquidity=liquidity,
        market_payload=market_payload,
        market_freshness=market_freshness,
        market_degraded=market_degraded,
    )
    rotation_evidence = _build_rotation_evidence(
        rotation_rows=rotation_rows,
        market_freshness=market_freshness,
        market_degraded=market_degraded,
    )
    breadth_evidence = _build_breadth_evidence(
        breadth_panel=breadth_panel,
        market_payload=market_payload,
        market_freshness=market_freshness,
        market_degraded=market_degraded,
    )
    scanner_evidence = _build_scanner_context_evidence(
        scanner_context=scanner_context,
        market_degraded=market_degraded,
    )

    domain_frames = {
        "macro": regime_evidence,
        "liquidity": liquidity_evidence,
        "rotation": rotation_evidence,
        "breadth": breadth_evidence,
        "scanner_context": scanner_evidence,
    }

    missing_evidence: list[str] = []
    blocking_reasons: list[str] = []
    domain_freshness: list[str] = []
    score_grade_count = 0
    observation_only_count = 0
    missing_count = 0

    for domain in _DOMAIN_ORDER:
        frame = domain_frames[domain]
        state = _text(frame.get("state")).lower()
        freshness = _normalize_contract_freshness(frame.get("freshness")) or "unknown"
        domain_freshness.append(freshness)
        if state == "missing":
            missing_count += 1
            missing_evidence.append(domain)
            _append_unique(blocking_reasons, "missing_required_evidence")
        elif state == "score_grade":
            score_grade_count += 1
        else:
            observation_only_count += 1
            _append_unique(blocking_reasons, "observation_only")

        for reason in _sequence(frame.get("blockingReasons")):
            _append_unique(blocking_reasons, _text(reason))

    freshness = _worst_freshness(domain_freshness + [market_payload.get("freshness"), market_freshness])
    if freshness in _DEGRADED_FRESHNESS:
        missing_evidence.append("freshness")
        if freshness == "stale":
            _append_unique(blocking_reasons, "stale_evidence")
        elif freshness == "fallback":
            _append_unique(blocking_reasons, "fallback_evidence")
        else:
            _append_unique(blocking_reasons, "freshness_missing")

    source_authority = "scoreGradeAllowed"
    if score_grade_count == 0 and missing_count == len(_DOMAIN_ORDER):
        source_authority = "unavailable"
    elif score_grade_count != len(_DOMAIN_ORDER):
        source_authority = "observationOnly"
        _append_unique(blocking_reasons, "source_authority_not_score_grade")

    no_advice_boundary = (
        market_payload.get("consumerActionBoundary") != "no_trade"
        and market_payload.get("consumerActionBoundary") != "no_execution"
        and scanner_evidence.get("noAdviceBoundary", True) is not False
    )
    if not no_advice_boundary:
        _append_unique(blocking_reasons, "consumer_action_blocked")

    next_evidence_needed = [_NEXT_EVIDENCE_COPY[item] for item in missing_evidence if item in _NEXT_EVIDENCE_COPY]

    frame_state = "ready"
    if any(_text(frame.get("state")).lower() == "waiting" for frame in domain_frames.values()):
        frame_state = "waiting"
    elif not no_advice_boundary:
        frame_state = "blocked"
    elif missing_count > 0 or freshness in _DEGRADED_FRESHNESS:
        frame_state = "insufficient"
    elif observation_only_count > 0:
        frame_state = "observe_only"

    return {
        "contractVersion": MARKET_INTELLIGENCE_EVIDENCE_VERSION,
        "frameState": frame_state,
        "evidenceCoverage": {
            "scoreGradeCount": score_grade_count,
            "observationOnlyCount": observation_only_count,
            "missingCount": missing_count,
            "totalCount": len(_DOMAIN_ORDER),
        },
        "regimeEvidence": regime_evidence,
        "liquidityEvidence": liquidity_evidence,
        "rotationEvidence": rotation_evidence,
        "breadthEvidence": breadth_evidence,
        "scannerContextEvidence": scanner_evidence,
        "missingEvidence": missing_evidence,
        "blockingReasons": blocking_reasons,
        "sourceAuthority": source_authority,
        "freshness": freshness,
        "nextEvidenceNeeded": next_evidence_needed,
        "noAdviceBoundary": no_advice_boundary,
        "debugRef": "market:temperature:evidence",
    }


def _build_regime_evidence(
    *,
    regime: Mapping[str, Any],
    direction: Mapping[str, Any],
    market_payload: Mapping[str, Any],
    market_freshness: str,
    market_degraded: bool,
) -> dict[str, Any]:
    primary_regime = _text(regime.get("primaryRegime")).lower()
    present = bool(regime) and primary_regime not in {"", "data_insufficient"}
    technical_ready = _text(direction.get("status")).lower() == "direction_ready"
    score_allowed = bool(market_payload.get("conclusionAllowed")) and technical_ready and not _is_degraded_freshness(
        market_payload.get("freshness") or market_freshness
    )
    if not present or market_degraded:
        return _missing_domain("macro", market_freshness)
    return _domain_frame(
        domain="macro",
        state="score_grade" if score_allowed else "observation_only",
        freshness=market_freshness,
        score_allowed=score_allowed,
        source_allowed=score_allowed,
        observation_only=not score_allowed,
        primary_regime=primary_regime or "data_insufficient",
    )


def _build_liquidity_evidence(
    *,
    liquidity_signal: Mapping[str, Any],
    liquidity: Mapping[str, Any],
    market_payload: Mapping[str, Any],
    market_freshness: str,
    market_degraded: bool,
) -> dict[str, Any]:
    present = bool(liquidity_signal) or _text(liquidity.get("liquidityImpulse")).lower() not in {"", "data_insufficient"}
    freshness = (
        _normalize_contract_freshness(liquidity_signal.get("freshness"))
        or _normalize_contract_freshness(liquidity.get("freshness"))
        or market_freshness
    )
    if not present or market_degraded:
        return _missing_domain("liquidity", freshness)
    source_allowed = bool(liquidity_signal.get("sourceAuthorityAllowed"))
    score_allowed = bool(liquidity_signal.get("scoreContributionAllowed")) and source_allowed and not _is_degraded_freshness(
        freshness
    )
    if _is_degraded_freshness(freshness):
        return _domain_frame(
            domain="liquidity",
            state="degraded",
            freshness=freshness,
            score_allowed=False,
            source_allowed=source_allowed,
            observation_only=True,
            likely_destination=_text(liquidity_signal.get("likelyDestination") or liquidity.get("liquidityImpulse")) or "data_insufficient",
            blocking_reasons=[f"{freshness}_evidence"],
        )
    return _domain_frame(
        domain="liquidity",
        state="score_grade" if score_allowed else "observation_only",
        freshness=freshness,
        score_allowed=score_allowed,
        source_allowed=source_allowed,
        observation_only=not score_allowed,
        likely_destination=_text(liquidity_signal.get("likelyDestination") or liquidity.get("liquidityImpulse")) or "data_insufficient",
    )


def _build_rotation_evidence(
    *,
    rotation_rows: Sequence[Mapping[str, Any]],
    market_freshness: str,
    market_degraded: bool,
) -> dict[str, Any]:
    present = any(_mapping(row.get("themeFlowSignal")) for row in rotation_rows)
    freshness = _worst_freshness([_mapping(row.get("themeFlowSignal")).get("freshness") for row in rotation_rows] + [market_freshness])
    if not present or market_degraded:
        return _missing_domain("rotation", freshness)
    score_allowed = any(
        bool(_mapping(row.get("themeFlowSignal")).get("scoreContributionAllowed"))
        and bool(_mapping(row.get("themeFlowSignal")).get("sourceAuthorityAllowed"))
        for row in rotation_rows
    ) and not _is_degraded_freshness(freshness)
    leading_theme_count = sum(
        1
        for row in rotation_rows
        if _text(_mapping(row.get("themeFlowSignal")).get("themeFlowState")).lower() in {"leading", "broadening", "confirming"}
    )
    if _is_degraded_freshness(freshness):
        return _domain_frame(
            domain="rotation",
            state="degraded",
            freshness=freshness,
            score_allowed=False,
            source_allowed=score_allowed,
            observation_only=True,
            leading_theme_count=leading_theme_count,
            blocking_reasons=[f"{freshness}_evidence"],
        )
    return _domain_frame(
        domain="rotation",
        state="score_grade" if score_allowed else "observation_only",
        freshness=freshness,
        score_allowed=score_allowed,
        source_allowed=score_allowed,
        observation_only=not score_allowed,
        leading_theme_count=leading_theme_count,
    )


def _build_breadth_evidence(
    *,
    breadth_panel: Mapping[str, Any],
    market_payload: Mapping[str, Any],
    market_freshness: str,
    market_degraded: bool,
) -> dict[str, Any]:
    items = [item for item in _sequence(breadth_panel.get("items")) if isinstance(item, Mapping)]
    present = bool(items)
    if not present or market_degraded:
        return _missing_domain("breadth", market_freshness)
    freshness = _worst_freshness([item.get("freshness") for item in items] + [market_freshness])
    score_allowed = bool(market_payload.get("conclusionAllowed")) and any(
        item.get("sourceAuthorityAllowed") is True and item.get("scoreContributionAllowed") is True for item in items
    ) and not _is_degraded_freshness(freshness)
    breadth_value = None
    for item in items:
        if _text(item.get("symbol")).upper() == "ADV_RATIO":
            breadth_value = item.get("value")
            break
    if _is_degraded_freshness(freshness):
        return _domain_frame(
            domain="breadth",
            state="degraded",
            freshness=freshness,
            score_allowed=False,
            source_allowed=False,
            observation_only=True,
            breadth_value=breadth_value,
            blocking_reasons=[f"{freshness}_evidence"],
        )
    return _domain_frame(
        domain="breadth",
        state="score_grade" if score_allowed else "observation_only",
        freshness=freshness,
        score_allowed=score_allowed,
        source_allowed=score_allowed,
        observation_only=not score_allowed,
        breadth_value=breadth_value,
    )


def _build_scanner_context_evidence(
    *,
    scanner_context: Mapping[str, Any],
    market_degraded: bool,
) -> dict[str, Any]:
    readiness = _mapping(scanner_context.get("marketReadiness"))
    macro_regime = _mapping(scanner_context.get("macroRegime"))
    present = bool(readiness)
    freshness = _normalize_contract_freshness(readiness.get("freshnessFloor") or macro_regime.get("freshness")) or "unknown"
    if not present or market_degraded:
        return _missing_domain("scanner_context", freshness)
    readiness_state = _text(readiness.get("readinessState")).lower()
    readiness_label = readiness_state or "insufficient"
    score_allowed = (
        readiness_state == "ready"
        and _text(readiness.get("sourceAuthority")) == "scoreGradeAllowed"
        and not _is_degraded_freshness(freshness)
    )
    if readiness_state == "waiting":
        return _domain_frame(
            domain="scanner_context",
            state="waiting",
            freshness=freshness,
            score_allowed=False,
            source_allowed=False,
            observation_only=True,
            readinessState=readiness_label,
            no_advice_boundary=readiness.get("consumerActionBoundary") == "no_advice" and bool(scanner_context.get("noAdviceBoundary")),
        )
    if _is_degraded_freshness(freshness) or readiness_state in {"blocked", "insufficient", "observe_only"}:
        reasons = list(_sequence(readiness.get("blockingReasons")))
        if _is_degraded_freshness(freshness):
            reasons.append(f"{freshness}_evidence")
        return _domain_frame(
            domain="scanner_context",
            state="degraded",
            freshness=freshness,
            score_allowed=False,
            source_allowed=_text(readiness.get("sourceAuthority")) == "scoreGradeAllowed",
            observation_only=True,
            readinessState=readiness_label,
            no_advice_boundary=readiness.get("consumerActionBoundary") == "no_advice" and bool(scanner_context.get("noAdviceBoundary")),
            blocking_reasons=reasons,
        )
    return _domain_frame(
        domain="scanner_context",
        state="score_grade" if score_allowed else "observation_only",
        freshness=freshness,
        score_allowed=score_allowed,
        source_allowed=_text(readiness.get("sourceAuthority")) == "scoreGradeAllowed",
        observation_only=not score_allowed,
        readinessState=readiness_label,
        no_advice_boundary=readiness.get("consumerActionBoundary") == "no_advice" and bool(scanner_context.get("noAdviceBoundary")),
    )


def _domain_frame(
    *,
    domain: str,
    state: str,
    freshness: str,
    score_allowed: bool,
    source_allowed: bool,
    observation_only: bool,
    blocking_reasons: Sequence[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        "domain": domain,
        "state": state,
        "freshness": _normalize_contract_freshness(freshness) or "unknown",
        "sourceAuthorityAllowed": bool(source_allowed),
        "scoreContributionAllowed": bool(score_allowed),
        "observationOnly": bool(observation_only),
        "blockingReasons": [reason for reason in (_text(item) for item in _sequence(blocking_reasons)) if reason],
    }
    for key, value in extra.items():
        if value is not None:
            payload[key] = value
    if "noAdviceBoundary" not in payload:
        payload["noAdviceBoundary"] = True
    return payload


def _missing_domain(domain: str, freshness: str) -> dict[str, Any]:
    return _domain_frame(
        domain=domain,
        state="missing",
        freshness=freshness,
        score_allowed=False,
        source_allowed=False,
        observation_only=True,
        blocking_reasons=["missing_required_evidence"],
    )


def _market_context_freshness(
    market_payload: Mapping[str, Any],
    liquidity_signal: Mapping[str, Any],
    rotation_rows: Sequence[Mapping[str, Any]],
) -> str:
    explicit = _normalize_contract_freshness(market_payload.get("freshness"))
    if explicit:
        return explicit
    derived = _worst_freshness(
        [liquidity_signal.get("freshness"), *[_mapping(row.get("themeFlowSignal")).get("freshness") for row in rotation_rows]]
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
    non_unknown = [item for item in normalized if item != "unknown"]
    if non_unknown:
        normalized = non_unknown
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


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)
