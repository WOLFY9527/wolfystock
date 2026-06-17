# -*- coding: utf-8 -*-
"""Bounded research queue aggregation from already-projected research signals."""

from __future__ import annotations

import copy
import re
from collections import Counter
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import quote


RESEARCH_QUEUE_SCHEMA_VERSION = "research_queue_v1"
RESEARCH_QUEUE_LIMIT = 10
RESEARCH_QUEUE_NO_ADVICE_DISCLOSURE = (
    "Research-only queue; verify evidence gaps before further review."
)

_SOURCE_SURFACES = ("scanner", "watchlist", "market", "manual_gap")
_PRIORITY_TIERS = ("urgent_review", "follow_up", "monitor")
_FORBIDDEN_TEXT_RE = re.compile(
    r"\b("
    r"buy|sell|hold|recommendation|trade recommendation|trading advice|investment advice|"
    r"target price|stop loss|take profit|position sizing|place order|submit order"
    r")\b|买入|卖出|持有|交易建议|投资建议|目标价|止损|止盈|仓位",
    re.IGNORECASE,
)
_RAW_DIAGNOSTIC_RE = re.compile(
    r"\b("
    r"request\s*id|trace\s*id|provider|cache|runtime|debug|diagnostic|"
    r"raw\s*(?:payload|diagnostics|result|response)|schema\s*version|marketcache"
    r")\b|[a-z][a-z0-9]*_[a-z0-9_]+",
    re.IGNORECASE,
)


class ResearchQueueAggregatorService:
    """Build a read-only queue without changing upstream rankings or memberships."""

    def build_queue(
        self,
        *,
        scanner_payload: Mapping[str, Any] | None = None,
        watchlist_overlay: Mapping[str, Any] | None = None,
        market_payload: Mapping[str, Any] | None = None,
        manual_gaps: Sequence[Mapping[str, Any] | Any] | None = None,
        limit: int = RESEARCH_QUEUE_LIMIT,
    ) -> dict[str, Any]:
        bounded_limit = _bounded_limit(limit)
        scanner_source = copy.deepcopy(_mapping(scanner_payload))
        watchlist_source = copy.deepcopy(_mapping(watchlist_overlay))
        market_source = copy.deepcopy(_mapping(market_payload))
        manual_sources = [copy.deepcopy(_mapping(item)) for item in manual_gaps or []]

        items = [
            *self._watchlist_items(watchlist_source),
            *self._scanner_items(scanner_source),
            *self._market_items(market_source),
            *self._manual_gap_items(manual_sources),
        ][:bounded_limit]
        evidence_gaps = _dedupe(
            gap
            for item in items
            for gap in list(item.get("evidenceGaps") or [])
        )
        source_surfaces = _dedupe(item.get("sourceSurface") for item in items)
        return {
            "schemaVersion": RESEARCH_QUEUE_SCHEMA_VERSION,
            "researchQueue": items,
            "aggregateSummary": {
                "itemCount": len(items),
                "limit": bounded_limit,
                "bounded": len(items) >= bounded_limit,
                "bySourceSurface": dict(Counter(item.get("sourceSurface") for item in items)),
                "byPriorityTier": {
                    tier: sum(1 for item in items if item.get("priorityTier") == tier)
                    for tier in _PRIORITY_TIERS
                },
            },
            "sourceSurfacesAggregated": source_surfaces,
            "evidenceGaps": evidence_gaps,
            "dataQuality": {
                "state": "ready" if items else "no_evidence",
                "itemCount": len(items),
                "sourceSurfacesAvailable": source_surfaces,
                "sourceSurfacesExpected": list(_SOURCE_SURFACES),
                "failClosed": not bool(items),
            },
            "noAdviceDisclosure": RESEARCH_QUEUE_NO_ADVICE_DISCLOSURE,
            "observationOnly": True,
            "decisionGrade": False,
        }

    @classmethod
    def _watchlist_items(cls, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for index, entry in enumerate(list(payload.get("researchPriorityQueue") or [])):
            source = _mapping(entry)
            symbol = _symbol(source.get("symbol"))
            if not symbol:
                continue
            reason = _first_safe_text(source.get("priorityReasonSafeLabel")) or (
                "Watchlist research priority needs review."
            )
            evidence_age = _mapping(source.get("evidenceAge"))
            result.append(
                {
                    "queueItemId": _queue_item_id("watchlist", symbol, index=index),
                    "sourceSurface": "watchlist",
                    "symbol": symbol,
                    "title": f"{symbol} watchlist research priority",
                    "priorityTier": _watchlist_priority_tier(source.get("priorityTier")),
                    "whyQueued": [reason],
                    "evidenceUsed": [reason],
                    "evidenceGaps": _safe_text_list(source.get("missingEvidence")),
                    "freshness": {
                        "state": _freshness_state(evidence_age.get("state")),
                        "lastReviewedAt": _optional_safe_public_text(evidence_age.get("lastReviewedAt")),
                    },
                    "suggestedResearchPath": _safe_research_path(source.get("suggestedResearchPath")),
                    "observationOnly": True,
                }
            )
        return result

    @classmethod
    def _scanner_items(cls, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        run_id = _safe_public_token(payload.get("id") or payload.get("runId") or "latest")
        candidates = payload.get("shortlist") if isinstance(payload.get("shortlist"), list) else None
        if not candidates:
            candidates = payload.get("selected") if isinstance(payload.get("selected"), list) else []

        for index, candidate_value in enumerate(candidates):
            candidate = _mapping(candidate_value)
            symbol = _symbol(candidate.get("symbol") or candidate.get("ticker"))
            if not symbol:
                continue
            packet = _mapping(candidate.get("candidateResearchPacket"))
            evidence_gaps = _safe_text_list(
                packet.get("limitingEvidence")
                or _mapping(candidate.get("candidateResearchReadiness")).get("missingEvidence")
                or _mapping(candidate.get("consumerDiagnostics")).get("missingEvidence")
            )
            why_queued = _safe_text_list(
                [
                    packet.get("whySurfaced"),
                    candidate.get("reason_summary"),
                ],
                limit=3,
            )
            if not why_queued:
                why_queued = ["Scanner candidate is available for follow-up research review."]
            next_step = _first_safe_text(packet.get("researchNextStep")) or (
                "Open structure detail for evidence review."
            )
            rank = _safe_int(candidate.get("rank")) or index + 1
            result.append(
                {
                    "queueItemId": _queue_item_id("scanner", symbol, run_id=run_id, rank=rank, index=index),
                    "sourceSurface": "scanner",
                    "symbol": symbol,
                    "title": f"{symbol} scanner candidate",
                    "priorityTier": _scanner_priority_tier(evidence_gaps, index),
                    "whyQueued": why_queued,
                    "evidenceUsed": _safe_text_list(packet.get("primaryEvidence"), limit=4),
                    "evidenceGaps": evidence_gaps,
                    "freshness": {
                        "state": _freshness_state(
                            _mapping(candidate.get("consumerDiagnostics")).get("freshnessState")
                            or _freshness_from_notes(packet.get("dataQualityNotes"))
                        ),
                        "lastReviewedAt": _safe_public_text(
                            candidate.get("scan_timestamp")
                            or payload.get("completed_at")
                            or payload.get("completedAt")
                            or payload.get("run_at")
                            or payload.get("runAt")
                        )
                        or None,
                    },
                    "suggestedResearchPath": [
                        {
                            "label": "Stock Structure",
                            "route": f"/stocks/{quote(symbol, safe='')}/structure-decision",
                            "section": "researchQueue",
                            "reason": next_step,
                        }
                    ],
                    "observationOnly": True,
                }
            )
        return result

    @classmethod
    def _market_items(cls, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        preview = _mapping(payload.get("researchQueuePreview"))
        candidates = preview.get("topCandidates")
        if not isinstance(candidates, list):
            candidates = payload.get("researchQueue") if isinstance(payload.get("researchQueue"), list) else []
        result: list[dict[str, Any]] = []
        for index, candidate_value in enumerate(candidates):
            candidate = _mapping(candidate_value)
            symbol = _symbol(candidate.get("symbol") or candidate.get("ticker"))
            if not symbol:
                continue
            gaps = _safe_text_list(candidate.get("evidenceGaps"))
            why = _safe_text_list(
                [
                    candidate.get("whyQueued"),
                    candidate.get("whyOnRadar"),
                    candidate.get("researchBias"),
                ],
                limit=3,
            ) or ["Market context surfaced this item for research review."]
            result.append(
                {
                    "queueItemId": _queue_item_id("market", symbol, index=index),
                    "sourceSurface": "market",
                    "symbol": symbol,
                    "title": f"{symbol} market research context",
                    "priorityTier": "urgent_review" if gaps else "follow_up",
                    "whyQueued": why,
                    "evidenceUsed": _safe_text_list(candidate.get("evidenceUsed"), limit=4),
                    "evidenceGaps": gaps,
                    "freshness": {"state": "unknown", "lastReviewedAt": None},
                    "suggestedResearchPath": _safe_research_path(candidate.get("suggestedResearchPath")),
                    "observationOnly": True,
                }
            )
        return result

    @classmethod
    def _manual_gap_items(cls, values: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for index, value in enumerate(values):
            symbol = _symbol(value.get("symbol")) or "RESEARCH"
            gaps = _safe_text_list(value.get("evidenceGaps") or value.get("missingEvidence"))
            why = _safe_text_list(value.get("whyQueued"), limit=3) or [
                "Manual research gap needs evidence review."
            ]
            result.append(
                {
                    "queueItemId": _queue_item_id("manual-gap", symbol, index=index),
                    "sourceSurface": "manual_gap",
                    "symbol": symbol,
                    "title": _first_safe_text(value.get("title")) or "Manual research gap",
                    "priorityTier": "urgent_review" if gaps else "follow_up",
                    "whyQueued": why,
                    "evidenceUsed": _safe_text_list(value.get("evidenceUsed"), limit=4),
                    "evidenceGaps": gaps,
                    "freshness": {"state": "unknown", "lastReviewedAt": None},
                    "suggestedResearchPath": _safe_research_path(value.get("suggestedResearchPath")),
                    "observationOnly": True,
                }
            )
        return result


def _watchlist_priority_tier(value: Any) -> str:
    normalized = _text(value)
    if normalized == "attention":
        return "urgent_review"
    if normalized == "follow_up":
        return "follow_up"
    return "monitor"


def _scanner_priority_tier(evidence_gaps: Sequence[str], index: int) -> str:
    if evidence_gaps:
        return "urgent_review"
    if index < 5:
        return "follow_up"
    return "monitor"


def _freshness_state(value: Any) -> str:
    normalized = _text(value).lower()
    if normalized in {"fresh", "current", "ready", "available", "complete"}:
        return "current"
    if normalized in {"stale", "delayed", "fallback", "stale_or_cached", "partial", "limited"}:
        return "needs_review"
    if normalized in {"unavailable", "unsupported", "unsupported_market"}:
        return "unavailable"
    if normalized in {"no_evidence", "symbol_unknown", "missing"}:
        return "needs_review"
    return "unknown"


def _freshness_from_notes(value: Any) -> str:
    for note in _text_list(value):
        label, separator, state = note.partition(":")
        if separator and label.strip().lower() == "freshness":
            return state.strip()
    return ""


def _safe_research_path(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for entry_value in value:
        entry = _mapping(entry_value)
        label = _safe_public_text(entry.get("label"))
        route = _safe_route(entry.get("route"))
        section = _safe_public_text(entry.get("section"))
        reason = _safe_public_text(entry.get("reason"))
        if not label or not route or not section:
            continue
        key = (label, route, section, reason or "")
        if key in seen:
            continue
        seen.add(key)
        result.append({"label": label, "route": route, "section": section, "reason": reason or ""})
    return result[:3]


def _safe_route(value: Any) -> str:
    route = _text(value)
    if not route.startswith("/") or _FORBIDDEN_TEXT_RE.search(route) or _RAW_DIAGNOSTIC_RE.search(route):
        return ""
    return route


def _queue_item_id(
    source: str,
    symbol: str,
    *,
    run_id: str | None = None,
    rank: int | None = None,
    index: int = 0,
) -> str:
    parts = [source, _safe_public_token(symbol)]
    if run_id:
        parts.extend(["run", _safe_public_token(run_id)])
    if rank is not None:
        parts.extend(["rank", str(max(rank, 0))])
    parts.extend(["item", str(max(index + 1, 1))])
    return "-".join(part for part in parts if part)


def _bounded_limit(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = RESEARCH_QUEUE_LIMIT
    return max(1, min(parsed, RESEARCH_QUEUE_LIMIT))


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _symbol(value: Any) -> str:
    return _safe_public_token(value).upper()


def _safe_public_token(value: Any) -> str:
    text = _text(value).upper()
    return re.sub(r"[^A-Z0-9.-]+", "-", text).strip("-")


def _safe_text_list(value: Any, *, limit: int = 6) -> list[str]:
    return _dedupe(_safe_public_text(item) for item in _text_list(value) if _safe_public_text(item))[:limit]


def _text_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, Mapping):
        values: Iterable[Any] = value.values()
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = [value]
    return [_text(item) for item in values if _text(item)]


def _first_safe_text(*values: Any) -> str:
    for value in values:
        safe = _safe_public_text(value)
        if safe:
            return safe
    return ""


def _safe_public_text(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    if _FORBIDDEN_TEXT_RE.search(text) or _RAW_DIAGNOSTIC_RE.search(text):
        return ""
    return text


def _optional_safe_public_text(value: Any) -> str | None:
    return _safe_public_text(value) or None


def _dedupe(items: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _safe_int(value: Any) -> int | None:
    try:
        if value in (None, "") or isinstance(value, bool):
            return None
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return str(value or "").strip()


__all__ = [
    "RESEARCH_QUEUE_LIMIT",
    "RESEARCH_QUEUE_NO_ADVICE_DISCLOSURE",
    "RESEARCH_QUEUE_SCHEMA_VERSION",
    "ResearchQueueAggregatorService",
]
