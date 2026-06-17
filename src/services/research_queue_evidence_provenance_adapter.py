# -*- coding: utf-8 -*-
"""Adapter from bounded research queue packets to evidence provenance ledgers.

This helper is intentionally inert: it only projects caller-provided research
queue metadata into the existing evidence provenance ledger helper.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from src.services.evidence_provenance_ledger import build_evidence_provenance_ledger


_SURFACE_INPUTS = {
    "scanner": "scannerResearchOverlay",
    "scanneroverlay": "scannerResearchOverlay",
    "watchlist": "watchlistResearchOverlay",
    "watchlistoverlay": "watchlistResearchOverlay",
    "market": "marketRadar",
    "marketresearch": "marketRadar",
    "manualgap": "researchRadar",
    "research": "researchRadar",
    "researchqueue": "researchRadar",
}
_FAMILY_KEYWORDS = (
    ("news", ("news", "catalyst", "event")),
    ("fundamentals", ("fundamental", "financial", "earnings", "filing")),
    ("macro", ("macro",)),
    ("valuation", ("valuation",)),
    ("sentiment", ("sentiment",)),
    ("sector_theme", ("sector", "theme")),
    ("market_data", ("technical", "trend", "momentum", "liquidity", "price", "quote", "volume")),
)
_HELPER_FAMILY_INPUTS = {
    "market_data": "technicals",
    "fundamentals": "fundamentals",
    "news": "news",
    "macro": "macro",
    "valuation": "valuation",
    "sentiment": "sentiment",
    "sector_theme": "sectorTheme",
    "research_context": "research",
}
_LABELS = {
    "market_data": "Primary market data summary",
    "fundamentals": "Fundamentals summary",
    "news": "News context",
    "macro": "Macro context summary",
    "valuation": "Valuation context",
    "sentiment": "Sentiment context",
    "sector_theme": "Sector theme context",
    "research_context": "Research context",
}
_USED_FOR_INPUTS = {
    "market_data": "technical",
    "fundamentals": "fundamentals",
    "news": "news",
    "macro": "macro",
    "valuation": "valuation",
    "sentiment": "sentiment",
    "sector_theme": "research",
    "research_context": "research",
}
_ADVICE_RE = re.compile(
    r"\b("
    r"buy|sell|hold|recommendation|trade recommendation|trading advice|investment advice|"
    r"target price|stop loss|take profit|position sizing|place order|submit order"
    r")\b|买入|卖出|持有|交易建议|投资建议|目标价|止损|止盈|仓位",
    re.IGNORECASE,
)
_RAW_DIAGNOSTIC_RE = re.compile(
    r"\b("
    r"request\s*id|trace\s*id|source\s*ref|reason\s*code|provider|cache|runtime|"
    r"debug|diagnostic|raw\s*(?:payload|diagnostics|result|response)|marketcache|"
    r"token|secret|authorization|bearer"
    r")\b|https?://|/users/",
    re.IGNORECASE,
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _compact_key(value: Any) -> str:
    return "".join(char for char in _text(value).lower() if char.isalnum())


def _sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    if isinstance(value, Iterable):
        return list(value)
    return [value]


def _is_unsafe_text(value: Any) -> bool:
    text = _text(value)
    return bool(text and (_ADVICE_RE.search(text) or _RAW_DIAGNOSTIC_RE.search(text)))


def _queue_items(value: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    payload = _mapping(value)
    raw_items = payload.get("researchQueue")
    if isinstance(raw_items, list):
        return [_mapping(item) for item in raw_items if isinstance(item, Mapping)]
    if payload.get("queueItemId") or payload.get("sourceSurface"):
        return [payload]
    return []


def _surface_input(item: Mapping[str, Any]) -> str:
    raw_surface = item.get("sourceSurface")
    if _is_unsafe_text(raw_surface):
        return "general"
    return _SURFACE_INPUTS.get(_compact_key(raw_surface), "general")


def _freshness_input(item: Mapping[str, Any]) -> str:
    freshness = _mapping(item.get("freshness"))
    raw_state = _text(freshness.get("state") or item.get("freshnessState") or item.get("freshness")).lower()
    if not raw_state or _is_unsafe_text(raw_state):
        return "unknown"
    normalized = raw_state.replace("-", "_").replace(" ", "_")
    if normalized in {"current", "fresh", "live"}:
        return "current"
    if normalized in {"recent", "cached"}:
        return "recent"
    if normalized in {"needs_review", "partial", "limited"}:
        return "partial"
    if normalized in {"delayed", "stale"}:
        return "stale"
    if normalized in {"no_evidence", "missing", "unavailable", "failed"}:
        return "unavailable"
    if normalized in {"synthetic", "fixture", "demo"}:
        return "synthetic"
    return "unknown"


def _family_from_text(value: Any) -> str | None:
    text = _text(value).lower()
    if not text or _is_unsafe_text(text):
        return None
    for family, keywords in _FAMILY_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return family
    return None


def _families_for_item(item: Mapping[str, Any]) -> list[str]:
    families: list[str] = []
    for value in [*_sequence(item.get("evidenceUsed")), *_sequence(item.get("evidenceGaps"))]:
        family = _family_from_text(value)
        if family and family not in families:
            families.append(family)
        if len(families) >= 4:
            break
    return families or ["research_context"]


def _has_evidence_gaps(item: Mapping[str, Any]) -> bool:
    return bool(_sequence(item.get("evidenceGaps")))


def _limitation_input(item: Mapping[str, Any]) -> str:
    if _has_evidence_gaps(item):
        return "missingEvidence"
    freshness = _freshness_input(item)
    if freshness == "partial":
        return "partial"
    if freshness == "stale":
        return "stale"
    if freshness == "synthetic":
        return "synthetic"
    if freshness == "unavailable":
        return "missingEvidence"
    return "observationOnly"


def _entries_for_item(item: Mapping[str, Any]) -> list[dict[str, Any]]:
    source_surface = _surface_input(item)
    freshness = _freshness_input(item)
    limitation = _limitation_input(item)
    entries: list[dict[str, Any]] = []
    for family in _families_for_item(item):
        entries.append(
            {
                "sourceSurface": source_surface,
                "evidenceFamily": _HELPER_FAMILY_INPUTS[family],
                "freshnessBucket": freshness,
                "authorityBucket": "observationOnly",
                "consumerSafeSourceLabel": _LABELS[family],
                "usedFor": [_USED_FOR_INPUTS[family]],
                "limitation": limitation,
                "observationOnly": True,
            }
        )
    return entries


def build_research_queue_evidence_provenance_ledger(
    research_queue_packet: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build a T-1708 evidence provenance ledger from a research queue packet."""

    entries = [
        entry
        for item in _queue_items(research_queue_packet)
        for entry in _entries_for_item(item)
    ]
    return build_evidence_provenance_ledger(entries)


__all__ = ["build_research_queue_evidence_provenance_ledger"]
