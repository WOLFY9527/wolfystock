# -*- coding: utf-8 -*-
"""Consumer-safe candidate research summary projection for scanner rows."""

from __future__ import annotations

from typing import Any, Mapping


SCANNER_CANDIDATE_RESEARCH_SUMMARY_VERSION = "scanner_candidate_research_summary_v1"

_DOMAIN_LABELS = {
    "technicals": "Technicals available",
    "priceHistory": "Price history available",
    "liquidity": "Liquidity available",
    "volume": "Volume evidence available",
    "gapMomentum": "Momentum evidence available",
    "trend": "Trend structure available",
    "theme": "Theme context available",
    "fundamentals": "Fundamentals available",
    "newsCatalyst": "News and catalyst context available",
}
_TOPDOWN_LABELS = {
    "marketReadiness": "Top-down market context available",
    "macroRegime": "Macro regime context available",
    "liquidityFrame": "Liquidity context available",
    "assetClassBias": "Asset-class bias available",
    "themeFrame": "Theme leadership context available",
}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _dedupe_text(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = _text(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _score_band(*, score: float | None, source_authority: str, freshness: str, frame_state: str) -> str:
    normalized_authority = _text(source_authority)
    normalized_freshness = _text(freshness).lower()
    normalized_state = _text(frame_state).lower()
    if normalized_state == "blocked":
        return "blocked"
    if normalized_authority != "scoreGradeAllowed":
        return "limited"
    if normalized_freshness in {"fallback", "stale", "unknown", "unavailable"}:
        return "limited"
    numeric_score = score if score is not None else 0.0
    if numeric_score >= 75.0:
        return "high"
    if numeric_score >= 55.0:
        return "medium"
    return "limited"


def _primary_reason(
    *,
    frame_state: str,
    source_authority: str,
    missing_evidence: list[str],
    blocking_reasons: list[str],
    evidence_highlights: list[str],
    rank: int | None,
) -> str:
    normalized_state = _text(frame_state).lower()
    if normalized_state == "blocked":
        return "Core evidence is missing, so this candidate stays in research-only review."
    if _text(source_authority) != "scoreGradeAllowed":
        return "Available signals are observation-only, so this candidate stays in research-only review."
    if missing_evidence:
        return f"Current signals support shortlist review, but {missing_evidence[0]} is still missing."
    if blocking_reasons:
        return "The candidate remains on the shortlist with bounded evidence and explicit research-only limits."
    if evidence_highlights:
        prefix = "Higher-ranked evidence is available" if rank == 1 else "Supporting evidence is available"
        return f"{prefix}: {evidence_highlights[0]}."
    return "The candidate appears for further research with no-advice boundaries."


def _evidence_highlights(candidate_evidence_frame: Mapping[str, Any]) -> list[str]:
    domains = _mapping(candidate_evidence_frame.get("domains"))
    highlights: list[str] = []
    for key in ("technicals", "priceHistory", "liquidity", "volume", "gapMomentum", "trend", "theme"):
        payload = _mapping(domains.get(key))
        if _text(payload.get("state")).lower() == "available":
            highlights.append(_DOMAIN_LABELS[key])
        elif _text(payload.get("state")).lower() == "partial" and key in {"gapMomentum", "theme"}:
            highlights.append(_DOMAIN_LABELS[key].replace(" available", " partial"))
    return _dedupe_text(highlights[:3])


def _top_down_context_refs(scanner_context_frame: Mapping[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for key in ("marketReadiness", "macroRegime", "liquidityFrame", "assetClassBias", "themeFrame"):
        payload = _mapping(scanner_context_frame.get(key))
        state = _text(payload.get("readinessState") or payload.get("state")).lower()
        if not state:
            continue
        refs.append(
            {
                "key": key,
                "state": state,
                "label": _TOPDOWN_LABELS[key],
            }
        )
    return refs


def build_scanner_candidate_research_summary_frame(
    candidate: Mapping[str, Any] | None,
    *,
    candidate_evidence_frame: Mapping[str, Any] | None = None,
    candidate_research_readiness: Mapping[str, Any] | None = None,
    scanner_context_frame: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(candidate or {})
    evidence_frame = _mapping(candidate_evidence_frame or payload.get("candidateEvidenceFrame"))
    readiness = _mapping(candidate_research_readiness or payload.get("candidateResearchReadiness"))
    context_frame = _mapping(scanner_context_frame or payload.get("scannerContextFrame"))

    symbol = _text(payload.get("symbol")).upper()
    rank = _int(payload.get("rank"))
    score = _float(payload.get("final_score"))
    if score is None:
        score = _float(payload.get("score"))

    frame_state = _text(readiness.get("readinessState")).lower() or "insufficient"
    missing_evidence = _dedupe_text(list(readiness.get("missingEvidence") or []))
    blocking_reasons = _dedupe_text(
        [item for item in list(readiness.get("blockingReasons") or []) or list(readiness.get("blockedReasons") or [])]
    )
    source_authority = _text(readiness.get("sourceAuthority") or readiness.get("providerAuthority") or "unavailable")
    freshness = _text(readiness.get("freshness") or readiness.get("freshnessFloor") or "unknown").lower() or "unknown"
    evidence_highlights = _evidence_highlights(evidence_frame)
    top_down_context_refs = _top_down_context_refs(context_frame)
    next_research_step = _text((readiness.get("nextEvidenceNeeded") or [None])[0]) or "Wait for more complete evidence."

    return {
        "contractVersion": SCANNER_CANDIDATE_RESEARCH_SUMMARY_VERSION,
        "frameState": frame_state,
        "symbol": symbol,
        "rank": rank or 0,
        "scoreBand": _score_band(
            score=score,
            source_authority=source_authority,
            freshness=freshness,
            frame_state=frame_state,
        ),
        "primaryResearchReason": _primary_reason(
            frame_state=frame_state,
            source_authority=source_authority,
            missing_evidence=missing_evidence,
            blocking_reasons=blocking_reasons,
            evidence_highlights=evidence_highlights,
            rank=rank,
        ),
        "evidenceHighlights": evidence_highlights,
        "missingEvidence": missing_evidence,
        "blockingReasons": blocking_reasons,
        "topDownContextRefs": top_down_context_refs,
        "sourceAuthority": source_authority or "unavailable",
        "freshness": freshness,
        "nextResearchStep": next_research_step,
        "noAdviceBoundary": True,
        "debugRef": f"scanner:candidate_summary:{symbol or 'UNKNOWN'}",
    }


__all__ = [
    "SCANNER_CANDIDATE_RESEARCH_SUMMARY_VERSION",
    "build_scanner_candidate_research_summary_frame",
]
