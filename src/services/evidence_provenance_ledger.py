# -*- coding: utf-8 -*-
"""Consumer-safe evidence provenance ledger helper.

This module is intentionally inert. It only normalizes caller-supplied metadata
into a bounded, human-safe summary and never imports provider/runtime/storage
code or exposes raw diagnostic identifiers.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


EVIDENCE_PROVENANCE_LEDGER_VERSION = "evidence_provenance_ledger_v1"

_SOURCE_SURFACE_ALIASES = {
    "analysis": "research_packet",
    "evidencecitationframe": "research_packet",
    "researchpacket": "research_packet",
    "researchpacketv1": "research_packet",
    "researchreadiness": "research_packet",
    "singlestockevidencepacket": "research_packet",
    "sourceprovenanceframe": "research_packet",
    "scannerresearchoverlay": "scanner_overlay",
    "watchlistresearchoverlay": "watchlist_overlay",
    "marketradar": "market_research",
    "researchradar": "market_research",
    "general": "general",
}
_EVIDENCE_FAMILY_ALIASES = {
    "catalyst": "news",
    "catalysts": "news",
    "earnings": "fundamentals",
    "filings": "filings",
    "fundamental": "fundamentals",
    "fundamentals": "fundamentals",
    "macro": "macro",
    "macroliquidity": "macro",
    "marketdata": "market_data",
    "news": "news",
    "newscatalysts": "news",
    "price": "market_data",
    "pricehistory": "market_data",
    "quote": "market_data",
    "quotes": "market_data",
    "research": "research_context",
    "sentiment": "sentiment",
    "sectortheme": "sector_theme",
    "technicals": "market_data",
    "valuation": "valuation",
    "general": "general",
}
_FRESHNESS_ALIASES = {
    "cached": "recent",
    "current": "current",
    "delayed": "stale",
    "fresh": "current",
    "live": "current",
    "partial": "partial",
    "recent": "recent",
    "stale": "stale",
    "fallback": "stale",
    "synthetic": "synthetic",
    "fixture": "synthetic",
    "unavailable": "unavailable",
    "missing": "unavailable",
    "unknown": "unknown",
}
_AUTHORITY_ALIASES = {
    "authorized": "primary",
    "authorizedfeed": "primary",
    "authorizedlicensedfeed": "primary",
    "official": "primary",
    "officialpublic": "primary",
    "primary": "primary",
    "scoregrade": "primary",
    "scoregradeallowed": "primary",
    "trustedpublic": "primary",
    "cache": "observation_only",
    "cachesnapshot": "observation_only",
    "fallback": "observation_only",
    "manualreview": "observation_only",
    "observationonly": "observation_only",
    "publicproxy": "observation_only",
    "proxy": "observation_only",
    "storedsnapshot": "observation_only",
    "unofficialproxy": "observation_only",
    "demo": "synthetic",
    "fixture": "synthetic",
    "synthetic": "synthetic",
    "unavailable": "unknown",
    "unknown": "unknown",
}
_USED_FOR_ALIASES = {
    "analysis": "research_context",
    "context": "research_context",
    "fundamental": "fundamentals_review",
    "fundamentals": "fundamentals_review",
    "macro": "macro_context",
    "macro liquidity": "macro_context",
    "news": "news_context",
    "news catalysts": "news_context",
    "price": "price_history",
    "price history": "price_history",
    "quote": "price_history",
    "research": "research_context",
    "sentiment": "sentiment_context",
    "technical": "technical_context",
    "technicals": "technical_context",
    "valuation": "valuation_context",
}
_SAFE_SOURCE_LABELS = {
    "market_data": "Primary market data summary",
    "fundamentals": "Fundamentals summary",
    "filings": "Public filings summary",
    "macro": "Macro context summary",
    "news": "News context",
    "research_context": "Research context",
    "sector_theme": "Sector theme context",
    "sentiment": "Sentiment context",
    "valuation": "Valuation context",
    "general": "Evidence source summary",
}
_SAFE_LIMITATIONS = {
    "fallbackorproxysource": "fallback_or_proxy",
    "fallbackproxy": "fallback_or_proxy",
    "fallbacksource": "fallback_or_proxy",
    "missing": "limited_coverage",
    "missingevidence": "limited_coverage",
    "observationonly": "observation_only",
    "partial": "limited_coverage",
    "stale": "stale_or_delayed",
    "stalesource": "stale_or_delayed",
    "delayed": "stale_or_delayed",
    "synthetic": "synthetic_or_demo",
    "syntheticsource": "synthetic_or_demo",
    "unknown": "limited_coverage",
    "unknownsource": "limited_coverage",
    "unavailable": "limited_coverage",
}
_UNSAFE_MARKERS = (
    "/users/",
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cache",
    "cookie",
    "debug",
    "diagnostic",
    "duckdb",
    "internal",
    "payload",
    "provider",
    "raw",
    "request_id",
    "requestid",
    "runtime",
    "scorecontributionallowed",
    "secret",
    "session",
    "sourceauthorityallowed",
    "sourcerefid",
    "stack",
    "token",
    "trace",
    "trace_id",
    "traceid",
    "http://",
    "https://",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _compact_key(value: Any) -> str:
    text = _text(value).lower()
    return "".join(char for char in text if char.isalnum())


def _snake_token(value: Any) -> str:
    text = _text(value).lower().replace("-", " ").replace("_", " ").replace("/", " ")
    return "_".join(part for part in text.split() if part)


def _is_unsafe(value: Any) -> bool:
    lowered = _text(value).lower()
    return any(marker in lowered for marker in _UNSAFE_MARKERS)


def _first_present(entry: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in entry and entry[key] not in (None, ""):
            return entry[key]
    return None


def _sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    if isinstance(value, Iterable):
        return list(value)
    return [value]


def _has_unsafe_core_metadata(entry: Mapping[str, Any]) -> bool:
    return any(
        _is_unsafe(_first_present(entry, *keys))
        for keys in (
            ("sourceSurface", "surface"),
            ("evidenceFamily", "evidenceDomain", "domain", "family"),
            ("freshnessBucket", "freshnessState", "freshness"),
            ("authorityBucket", "authorityTier", "providerAuthority", "sourceAuthority"),
        )
    )


def _surface(value: Any) -> str:
    if _is_unsafe(value):
        return "general"
    return _SOURCE_SURFACE_ALIASES.get(_compact_key(value), "general")


def _family(entry: Mapping[str, Any]) -> str:
    value = _first_present(entry, "evidenceFamily", "evidenceDomain", "domain", "family")
    if _is_unsafe(value):
        return "general"
    return _EVIDENCE_FAMILY_ALIASES.get(_compact_key(value), "general")


def _freshness(value: Any) -> str:
    if _is_unsafe(value):
        return "unknown"
    return _FRESHNESS_ALIASES.get(_compact_key(value), "unknown")


def _authority(value: Any) -> str:
    if _is_unsafe(value):
        return "unknown"
    return _AUTHORITY_ALIASES.get(_compact_key(value), "unknown")


def _source_label(value: Any, family: str) -> str:
    text = " ".join(_text(value).split())
    safe_labels = {_compact_key(label): label for label in _SAFE_SOURCE_LABELS.values()}
    if text and not _is_unsafe(text) and _compact_key(text) in safe_labels:
        return text[:80]
    return _SAFE_SOURCE_LABELS.get(family, "Evidence source summary")


def _used_for(value: Any) -> list[str]:
    labels: list[str] = []
    for item in _sequence(value):
        if _is_unsafe(item):
            continue
        alias = _USED_FOR_ALIASES.get(_text(item).lower()) or _USED_FOR_ALIASES.get(
            _snake_token(item).replace("_", " ")
        )
        if alias:
            labels.append(alias)
    return list(dict.fromkeys(labels)) or ["research_context"]


def _limitation(value: Any, *, freshness: str, authority: str, unsafe_input: bool) -> str:
    if unsafe_input:
        return "redacted_input"
    raw_values = _sequence(value)
    for item in raw_values:
        if _is_unsafe(item):
            continue
        alias = _SAFE_LIMITATIONS.get(_compact_key(item))
        if alias:
            return alias
        if _compact_key(item) == "none":
            return "none"
    if freshness == "stale":
        return "stale_or_delayed"
    if freshness in {"partial", "unavailable"}:
        return "limited_coverage"
    if freshness == "synthetic" or authority == "synthetic":
        return "synthetic_or_demo"
    if authority in {"observation_only", "unknown"}:
        return "observation_only" if authority == "observation_only" else "limited_coverage"
    return "none"


def _observation_only(value: Any, *, freshness: str, authority: str, limitation: str, unsafe_input: bool) -> bool:
    if unsafe_input:
        return True
    if bool(value):
        return True
    if authority != "primary":
        return True
    if freshness not in {"current", "recent"}:
        return True
    return limitation not in {"none"}


def _entry_id(index: int) -> str:
    return f"evidence-{index}"


def build_evidence_provenance_ledger(entries: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
    """Build a bounded evidence provenance ledger from caller-supplied metadata."""

    ledger: list[dict[str, Any]] = []
    for index, raw_entry in enumerate(entries or (), start=1):
        if not isinstance(raw_entry, Mapping):
            continue
        unsafe_input = _has_unsafe_core_metadata(raw_entry)
        family = _family(raw_entry)
        freshness = _freshness(_first_present(raw_entry, "freshnessBucket", "freshnessState", "freshness"))
        authority = _authority(
            _first_present(raw_entry, "authorityBucket", "authorityTier", "providerAuthority", "sourceAuthority")
        )
        limitation = _limitation(
            _first_present(raw_entry, "limitation", "limitations", "missingReasons", "blockingReasons"),
            freshness=freshness,
            authority=authority,
            unsafe_input=unsafe_input,
        )
        observation_only = _observation_only(
            _first_present(raw_entry, "observationOnly", "observation_only"),
            freshness=freshness,
            authority=authority,
            limitation=limitation,
            unsafe_input=unsafe_input,
        )
        if observation_only and authority == "primary":
            authority = "observation_only"
        ledger.append(
            {
                "evidenceId": _entry_id(len(ledger) + 1),
                "sourceSurface": _surface(_first_present(raw_entry, "sourceSurface", "surface")),
                "evidenceFamily": family,
                "freshnessBucket": freshness,
                "authorityBucket": authority,
                "consumerSafeSourceLabel": _source_label(
                    _first_present(raw_entry, "consumerSafeSourceLabel", "sourceLabel", "label"),
                    family,
                ),
                "usedFor": _used_for(_first_present(raw_entry, "usedFor", "purpose")),
                "limitation": limitation,
                "observationOnly": observation_only,
            }
        )
    return {
        "contractVersion": EVIDENCE_PROVENANCE_LEDGER_VERSION,
        "evidenceProvenanceLedger": ledger,
    }


__all__ = [
    "EVIDENCE_PROVENANCE_LEDGER_VERSION",
    "build_evidence_provenance_ledger",
]
