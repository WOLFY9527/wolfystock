# -*- coding: utf-8 -*-
"""Build a consumer-safe source freshness summary from caller-supplied states only."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from api.v1.schemas.source_freshness_summary import (
    SOURCE_FRESHNESS_NO_ADVICE_DISCLOSURE,
    SourceFreshnessItem,
    SourceFreshnessLevel,
    SourceFreshnessStatus,
    SourceFreshnessSummary,
    default_source_message,
    default_summary_message,
    normalize_source_category,
    normalize_source_freshness,
    sanitize_public_label,
    sanitize_public_text,
    sanitize_source_key,
    sanitize_timestamp_text,
)

_OVERALL_FRESHNESS_ORDER: tuple[SourceFreshnessLevel, ...] = (
    "unavailable",
    "stale",
    "no_evidence",
    "unknown",
    "recent",
    "fresh",
)


def build_source_freshness_summary(value: Mapping[str, Any] | None) -> SourceFreshnessSummary:
    payload = dict(value or {})
    sources = _normalize_sources(payload.get("sources"))
    if not sources:
        return SourceFreshnessSummary(
            status="no_evidence",
            asOf=None,
            sources=[],
            overallFreshness="no_evidence",
            staleCount=0,
            unavailableCount=0,
            message=default_summary_message("no_evidence"),
            noAdviceDisclosure=SOURCE_FRESHNESS_NO_ADVICE_DISCLOSURE,
        )

    stale_count = sum(1 for source in sources if source.freshness == "stale")
    unavailable_count = sum(1 for source in sources if source.freshness == "unavailable")
    overall_freshness = _aggregate_overall_freshness(sources)
    status = _derive_status(sources, stale_count=stale_count, unavailable_count=unavailable_count)
    message = sanitize_public_text(
        payload.get("message"),
        fallback=default_summary_message(status),
        max_length=80,
    )
    as_of = sanitize_timestamp_text(payload.get("asOf")) or _resolve_summary_as_of(sources)
    return SourceFreshnessSummary(
        status=status,
        asOf=as_of,
        sources=sources,
        overallFreshness=overall_freshness,
        staleCount=stale_count,
        unavailableCount=unavailable_count,
        message=message,
        noAdviceDisclosure=SOURCE_FRESHNESS_NO_ADVICE_DISCLOSURE,
    )


def _normalize_sources(value: object) -> list[SourceFreshnessItem]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []

    sources: list[SourceFreshnessItem] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        category = normalize_source_category(item.get("category"))
        freshness = normalize_source_freshness(item.get("freshness"))
        key = sanitize_source_key(item.get("key"), category=category)
        label = sanitize_public_label(item.get("label"), category=category)
        public_message = sanitize_public_text(
            item.get("publicMessage"),
            fallback=default_source_message(freshness),
            max_length=64,
        )
        sources.append(
            SourceFreshnessItem(
                key=key,
                label=label,
                category=category,
                freshness=freshness,
                asOf=sanitize_timestamp_text(item.get("asOf")),
                publicMessage=public_message,
            )
        )
    return sources


def _aggregate_overall_freshness(sources: Sequence[SourceFreshnessItem]) -> SourceFreshnessLevel:
    observed = {source.freshness for source in sources}
    for candidate in _OVERALL_FRESHNESS_ORDER:
        if candidate in observed:
            return candidate
    return "unknown"


def _derive_status(
    sources: Sequence[SourceFreshnessItem],
    *,
    stale_count: int,
    unavailable_count: int,
) -> SourceFreshnessStatus:
    if not sources:
        return "no_evidence"

    freshnesses = {source.freshness for source in sources}
    if freshnesses.issubset({"no_evidence", "unknown"}):
        return "no_evidence"
    if freshnesses == {"unavailable"}:
        return "unavailable"
    if stale_count or unavailable_count or freshnesses.intersection({"no_evidence", "unknown"}):
        return "limited"
    return "ready"


def _resolve_summary_as_of(sources: Sequence[SourceFreshnessItem]) -> str | None:
    for source in sources:
        if source.as_of:
            return source.as_of
    return None
