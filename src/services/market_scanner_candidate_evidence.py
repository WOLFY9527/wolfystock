# -*- coding: utf-8 -*-
"""Consumer-safe candidate evidence/readiness projections for scanner rows."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from src.services.research_readiness_contract import build_research_readiness_v1


SCANNER_CANDIDATE_EVIDENCE_VERSION = "scanner_candidate_evidence_v1"
_DOMAIN_ORDER = (
    "technicals",
    "priceHistory",
    "liquidity",
    "volume",
    "gapMomentum",
    "trend",
    "theme",
    "fundamentals",
    "newsCatalyst",
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _has_signal(*values: Any) -> bool:
    return any(_safe_float(value) is not None for value in values)


def _coerce_freshness(*values: Any) -> str:
    for value in values:
        normalized = _text(value).lower()
        if normalized in {"live", "fresh"}:
            return "fresh"
        if normalized in {"delayed", "cached", "cache", "partial"}:
            return "delayed"
        if normalized == "stale":
            return "stale"
        if normalized == "fallback":
            return "fallback"
        if normalized in {"unavailable", "missing"}:
            return "unknown"
    return "unknown"


def _domain_payload(
    *,
    base_state: str,
    observation_only: bool,
    score_grade_allowed: bool,
    freshness: str,
) -> dict[str, Any]:
    return {
        "state": base_state,
        "observationOnly": observation_only,
        "scoreGradeAllowed": score_grade_allowed and base_state != "missing",
        "freshness": freshness,
    }


def _summary_counts(domains: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    counts = {
        "availableCount": 0,
        "partialCount": 0,
        "observeOnlyCount": 0,
        "missingCount": 0,
        "totalCount": 0,
    }
    for name in _DOMAIN_ORDER:
        domain_payload = _mapping(domains.get(name))
        state = _text(domain_payload.get("state")).lower()
        if state in {"available", "partial", "missing"}:
            counts["totalCount"] += 1
            if state == "available":
                counts["availableCount"] += 1
            elif state == "partial":
                counts["partialCount"] += 1
            else:
                counts["missingCount"] += 1
            if state != "missing" and _bool(domain_payload.get("observationOnly")):
                counts["observeOnlyCount"] += 1
    return counts


def _coverage_state(domains: Mapping[str, Mapping[str, Any]]) -> str:
    price_history_state = _text(_mapping(domains.get("priceHistory")).get("state")).lower()
    liquidity_state = _text(_mapping(domains.get("liquidity")).get("state")).lower()
    technicals_state = _text(_mapping(domains.get("technicals")).get("state")).lower()
    all_states = {_text(_mapping(domains.get(name)).get("state")).lower() for name in _DOMAIN_ORDER}
    has_observation_only = any(
        _text(_mapping(domains.get(name)).get("state")).lower() != "missing"
        and _bool(_mapping(domains.get(name)).get("observationOnly"))
        for name in _DOMAIN_ORDER
    )
    if "missing" in {price_history_state, liquidity_state, technicals_state}:
        return "blocked"
    if has_observation_only:
        return "observe_only"
    if "missing" in all_states or "partial" in all_states:
        return "partial"
    return "available"


def _theme_present(candidate: Mapping[str, Any], diagnostics: Mapping[str, Any]) -> bool:
    boards = candidate.get("boards")
    if isinstance(boards, list) and any(_text(item) for item in boards):
        return True
    matched = candidate.get("_matched_sectors")
    if isinstance(matched, list) and any(_text(item) for item in matched):
        return True
    diagnostics_theme = _mapping(diagnostics.get("theme_context"))
    return any(
        _text(item)
        for item in diagnostics_theme.get("top_names") or []
    )


def _basic_evidence_state(*values: Any) -> str:
    if any(
        (isinstance(value, Mapping) and value)
        or (isinstance(value, list) and value)
        or (not isinstance(value, (Mapping, list)) and value not in (None, "", False))
        for value in values
    ):
        return "available"
    return "missing"


def build_scanner_candidate_evidence_frame(candidate: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(candidate or {})
    diagnostics = _mapping(payload.get("diagnostics") or payload.get("_diagnostics"))
    history = _mapping(diagnostics.get("history"))
    quote = _mapping(diagnostics.get("quote_context"))
    explainability = _mapping(diagnostics.get("score_explainability"))
    source_confidence = _mapping(explainability.get("source_confidence"))
    provider_observation = _mapping(diagnostics.get("cn_provider_observation"))
    evidence_packet = _mapping(diagnostics.get("evidence_packet"))
    freshness_detail = _mapping(evidence_packet.get("freshnessDetail"))
    component_scores = _mapping(payload.get("_component_scores") or diagnostics.get("component_scores"))

    history_rows = int(history.get("rows") or 0)
    history_available = bool(_text(history.get("latest_trade_date")))
    history_partial = history_available and 0 < history_rows < 60
    quote_available = quote.get("available") is True
    quote_present = bool(quote) or "quote_available" in payload or "quote_available" in diagnostics
    quote_missing = quote_present and not quote_available

    observation_only = (
        _bool(provider_observation.get("observationOnly"))
        or _bool(source_confidence.get("observationOnly"))
        or (
            source_confidence
            and not _bool(source_confidence.get("sourceAuthorityAllowed"))
            and not _bool(source_confidence.get("scoreContributionAllowed"))
        )
    )
    score_grade_allowed = (
        _bool(source_confidence.get("sourceAuthorityAllowed"))
        and _bool(source_confidence.get("scoreContributionAllowed"))
        and not observation_only
    )
    freshness = _coerce_freshness(
        source_confidence.get("freshness"),
        evidence_packet.get("freshnessState"),
        "fallback" if _bool(source_confidence.get("isFallback")) else None,
        "stale" if _bool(source_confidence.get("isStale")) or _bool(history.get("stale")) else None,
        "delayed" if quote_available else None,
        history.get("latest_trade_date"),
    )

    price_history_state = (
        "missing"
        if not history_available
        else "partial"
        if history_partial
        else "available"
    )
    if price_history_state == "missing":
        packet_history_state = _text(freshness_detail.get("historyState")).lower()
        if packet_history_state == "complete":
            price_history_state = "available"
        elif packet_history_state == "stale":
            price_history_state = "partial"
    liquidity_state = (
        "available"
        if _has_signal(payload.get("avg_amount_20"), payload.get("amount"))
        else "missing"
    )
    if liquidity_state == "missing":
        packet_liquidity_state = _text(_mapping(evidence_packet.get("liquidityEvidence")).get("state")).lower()
        if packet_liquidity_state == "complete":
            liquidity_state = "available"
        elif packet_liquidity_state == "partial":
            liquidity_state = "partial"
    volume_state = (
        "available"
        if _has_signal(payload.get("avg_volume_20"), payload.get("volume_expansion_20"))
        else "partial"
        if _has_signal(payload.get("avg_volume_20"), payload.get("volume"))
        else "missing"
    )
    if volume_state == "missing":
        packet_volume_state = _text(_mapping(evidence_packet.get("volumeEvidence")).get("state")).lower()
        if packet_volume_state == "complete":
            volume_state = "available"
        elif packet_volume_state == "partial":
            volume_state = "partial"
    trend_state = (
        "available"
        if _has_signal(component_scores.get("trend"))
        or (
            _has_signal(payload.get("price"), payload.get("close"))
            and _has_signal(payload.get("ma20"))
            and _has_signal(payload.get("ma60"))
        )
        else "missing"
    )
    if trend_state == "missing":
        packet_trend_state = _text(_mapping(evidence_packet.get("trendEvidence")).get("state")).lower()
        if packet_trend_state == "complete":
            trend_state = "available"
        elif packet_trend_state == "partial":
            trend_state = "partial"
    gap_momentum_state = (
        "available"
        if _has_signal(payload.get("ret_5d"))
        and _has_signal(payload.get("ret_20d"))
        and _has_signal(payload.get("gap_pct"))
        else "partial"
        if _has_signal(payload.get("ret_5d"))
        and _has_signal(payload.get("ret_20d"))
        else "missing"
    )
    if gap_momentum_state == "missing":
        packet_momentum_state = _text(_mapping(evidence_packet.get("momentumEvidence")).get("state")).lower()
        if packet_momentum_state == "complete":
            gap_momentum_state = "available"
        elif packet_momentum_state == "partial":
            gap_momentum_state = "partial"
    theme_state = "available" if _theme_present(payload, diagnostics) else "missing"
    if theme_state == "missing":
        packet_theme_state = _text(_mapping(evidence_packet.get("sectorThemeContext")).get("state")).lower()
        if packet_theme_state == "complete":
            theme_state = "available"
        elif packet_theme_state == "partial":
            theme_state = "partial"
    technicals_state = (
        "missing"
        if "missing" in {price_history_state, trend_state}
        else "partial"
        if "partial" in {price_history_state, gap_momentum_state, trend_state}
        else "available"
    )

    fundamentals_state = _basic_evidence_state(
        payload.get("fundamentals"),
        diagnostics.get("fundamentals"),
        diagnostics.get("fundamentals_context"),
    )
    news_catalyst_state = _basic_evidence_state(
        payload.get("news"),
        payload.get("catalyst"),
        diagnostics.get("news"),
        diagnostics.get("news_context"),
        diagnostics.get("news_catalyst"),
        diagnostics.get("catalyst"),
        diagnostics.get("events"),
    )

    domains = {
        "technicals": _domain_payload(
            base_state=technicals_state,
            observation_only=observation_only and technicals_state != "missing",
            score_grade_allowed=score_grade_allowed,
            freshness=freshness,
        ),
        "priceHistory": _domain_payload(
            base_state=price_history_state,
            observation_only=observation_only and price_history_state != "missing",
            score_grade_allowed=score_grade_allowed,
            freshness=freshness,
        ),
        "liquidity": _domain_payload(
            base_state=liquidity_state,
            observation_only=observation_only and liquidity_state != "missing",
            score_grade_allowed=score_grade_allowed,
            freshness=freshness,
        ),
        "volume": _domain_payload(
            base_state=volume_state,
            observation_only=observation_only and volume_state != "missing",
            score_grade_allowed=score_grade_allowed,
            freshness=freshness,
        ),
        "gapMomentum": _domain_payload(
            base_state=gap_momentum_state if not quote_missing else "partial",
            observation_only=(observation_only or quote_missing) and gap_momentum_state != "missing",
            score_grade_allowed=score_grade_allowed and not quote_missing,
            freshness=freshness,
        ),
        "trend": _domain_payload(
            base_state=trend_state,
            observation_only=observation_only and trend_state != "missing",
            score_grade_allowed=score_grade_allowed,
            freshness=freshness,
        ),
        "theme": _domain_payload(
            base_state=theme_state,
            observation_only=observation_only and theme_state != "missing",
            score_grade_allowed=score_grade_allowed,
            freshness=freshness,
        ),
        "fundamentals": _domain_payload(
            base_state=fundamentals_state,
            observation_only=False,
            score_grade_allowed=False,
            freshness="unknown",
        ),
        "newsCatalyst": _domain_payload(
            base_state=news_catalyst_state,
            observation_only=False,
            score_grade_allowed=False,
            freshness="unknown",
        ),
    }
    coverage = _summary_counts(domains)
    return {
        "contractVersion": SCANNER_CANDIDATE_EVIDENCE_VERSION,
        "coverageState": _coverage_state(domains),
        "domains": domains,
        "coverage": coverage,
        "noAdviceBoundary": True,
    }


def build_scanner_candidate_research_readiness(
    candidate: Mapping[str, Any] | None,
    *,
    candidate_evidence_frame: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(candidate or {})
    diagnostics = _mapping(payload.get("diagnostics") or payload.get("_diagnostics"))
    frame = dict(candidate_evidence_frame or build_scanner_candidate_evidence_frame(payload))
    domains = {
        name: _mapping(_mapping(frame.get("domains")).get(name))
        for name in _DOMAIN_ORDER
    }

    required_evidence = ["technical", "liquidity", "fundamentals", "news", "catalyst"]
    missing_evidence: list[str] = []
    if _text(domains["technicals"].get("state")).lower() == "missing":
        missing_evidence.append("technical")
    if _text(domains["liquidity"].get("state")).lower() == "missing":
        missing_evidence.append("liquidity")
    if _text(domains["fundamentals"].get("state")).lower() != "available":
        missing_evidence.append("fundamentals")
    if _text(domains["newsCatalyst"].get("state")).lower() != "available":
        missing_evidence.extend(["news", "catalyst"])

    evidence = [
        {
            "domain": "technical",
            "freshness": domains["technicals"].get("freshness"),
            "sourceAuthorityAllowed": domains["technicals"].get("scoreGradeAllowed"),
            "scoreContributionAllowed": domains["technicals"].get("scoreGradeAllowed"),
            "observationOnly": domains["technicals"].get("observationOnly"),
        },
        {
            "domain": "technical",
            "freshness": domains["priceHistory"].get("freshness"),
            "sourceAuthorityAllowed": domains["priceHistory"].get("scoreGradeAllowed"),
            "scoreContributionAllowed": domains["priceHistory"].get("scoreGradeAllowed"),
            "observationOnly": domains["priceHistory"].get("observationOnly"),
        },
        {
            "domain": "liquidity",
            "freshness": domains["liquidity"].get("freshness"),
            "sourceAuthorityAllowed": domains["liquidity"].get("scoreGradeAllowed"),
            "scoreContributionAllowed": domains["liquidity"].get("scoreGradeAllowed"),
            "observationOnly": domains["liquidity"].get("observationOnly"),
        },
        {
            "domain": "liquidity",
            "freshness": domains["volume"].get("freshness"),
            "sourceAuthorityAllowed": domains["volume"].get("scoreGradeAllowed"),
            "scoreContributionAllowed": domains["volume"].get("scoreGradeAllowed"),
            "observationOnly": domains["volume"].get("observationOnly"),
        },
        {
            "domain": "technical",
            "freshness": domains["gapMomentum"].get("freshness"),
            "sourceAuthorityAllowed": domains["gapMomentum"].get("scoreGradeAllowed"),
            "scoreContributionAllowed": domains["gapMomentum"].get("scoreGradeAllowed"),
            "observationOnly": domains["gapMomentum"].get("observationOnly"),
        },
    ]

    readiness = build_research_readiness_v1(
        {
            "requiredEvidence": required_evidence,
            "missingEvidence": missing_evidence,
            "evidence": evidence,
            "sourceAuthorityAllowed": all(bool(item.get("sourceAuthorityAllowed")) for item in evidence) and not missing_evidence,
            "scoreContributionAllowed": all(bool(item.get("scoreContributionAllowed")) for item in evidence) and not missing_evidence,
            "freshness": domains["technicals"].get("freshness"),
            "noAdviceBoundary": True,
            "consumerActionBoundary": "no_advice",
            "debugRef": f"scanner:candidate:{_text(payload.get('symbol') or 'unknown')}",
        }
    )

    blocking_reasons = list(readiness.get("blockingReasons") or [])
    next_evidence_needed = list(readiness.get("nextEvidenceNeeded") or [])
    if _text(domains["theme"].get("state")).lower() != "available":
        if "theme_context_missing" not in blocking_reasons:
            blocking_reasons.append("theme_context_missing")
        if "补充主题脉络证据" not in next_evidence_needed:
            next_evidence_needed.append("补充主题脉络证据")
    if _text(frame.get("coverageState")).lower() == "blocked":
        readiness.update(
            {
                "researchReady": False,
                "readinessState": "blocked",
                "verdictLabel": "研究结论受限",
            }
        )
    readiness["blockingReasons"] = blocking_reasons
    readiness["blockedReasons"] = list(blocking_reasons)
    readiness["nextEvidenceNeeded"] = next_evidence_needed
    readiness["market"] = _text(payload.get("market") or diagnostics.get("market")).lower() or None
    readiness["symbol"] = _text(payload.get("symbol")).upper() or None
    readiness["providerAuthority"] = readiness.get("sourceAuthority")
    readiness["freshness"] = readiness.get("freshnessFloor")
    readiness["noAdviceBoundary"] = True
    return readiness


__all__ = [
    "SCANNER_CANDIDATE_EVIDENCE_VERSION",
    "build_scanner_candidate_evidence_frame",
    "build_scanner_candidate_research_readiness",
]
