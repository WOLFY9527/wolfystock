# -*- coding: utf-8 -*-
"""Pure aggregation helpers for deterministic event intelligence timelines."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field

from api.v1.schemas.event_intelligence import EventIntelligenceItem
from src.services.event_intelligence_contracts import (
    EventIntelligenceDirection,
    EventIntelligenceType,
    validate_event_intelligence_visibility,
)


class EventIntelligenceTimelineStatus(str, Enum):
    READY = "ready"
    EMPTY = "empty"
    INSUFFICIENT = "insufficient"


class EventIntelligenceTimelineEntry(BaseModel):
    model_config = ConfigDict()

    event_key: str = Field(..., min_length=1)
    symbol: str = Field(..., min_length=1)
    market: str = Field(..., min_length=1)
    event_type: EventIntelligenceType
    subtype: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    event_at: datetime
    confirmed_at: datetime | None = None
    latest_published_at: datetime
    latest_as_of: datetime
    direction: EventIntelligenceDirection
    related_period: str | None = None
    max_confidence: float = Field(..., ge=0.0, le=1.0)
    max_importance_score: float = Field(..., ge=0.0, le=1.0)
    source_count: int = Field(..., ge=1)
    source_evidence: list[EventIntelligenceItem] = Field(default_factory=list, min_length=1)


class EventIntelligenceTimelineGroup(BaseModel):
    model_config = ConfigDict()

    event_date: date
    entries: list[EventIntelligenceTimelineEntry] = Field(default_factory=list)


class EventIntelligenceTimeline(BaseModel):
    model_config = ConfigDict()

    status: EventIntelligenceTimelineStatus
    as_of: datetime | None = None
    reason: str | None = None
    raw_item_count: int = Field(default=0, ge=0)
    deduped_event_count: int = Field(default=0, ge=0)
    source_evidence_count: int = Field(default=0, ge=0)
    groups: list[EventIntelligenceTimelineGroup] = Field(default_factory=list)


def build_empty_event_timeline(
    *,
    as_of: datetime | None = None,
    reason: str = "no_events",
) -> EventIntelligenceTimeline:
    return EventIntelligenceTimeline(
        status=EventIntelligenceTimelineStatus.EMPTY,
        as_of=as_of,
        reason=reason,
    )


def build_insufficient_event_timeline(
    *,
    as_of: datetime | None = None,
    reason: str = "insufficient_event_data",
) -> EventIntelligenceTimeline:
    return EventIntelligenceTimeline(
        status=EventIntelligenceTimelineStatus.INSUFFICIENT,
        as_of=as_of,
        reason=reason,
    )


def aggregate_event_timeline(items: Sequence[EventIntelligenceItem]) -> EventIntelligenceTimeline:
    if not items:
        return build_empty_event_timeline()

    validated_items = [_validated_item(item) for item in items]
    sorted_items = sorted(validated_items, key=_timeline_item_sort_key)

    grouped_items: dict[tuple[str, ...], list[EventIntelligenceItem]] = {}
    for item in sorted_items:
        grouped_items.setdefault(_event_identity(item), []).append(item)

    entries_by_date: dict[date, list[EventIntelligenceTimelineEntry]] = {}
    total_source_evidence = 0
    for identity, group_items in grouped_items.items():
        source_evidence = _deduplicate_source_evidence(group_items)
        total_source_evidence += len(source_evidence)
        entry = _build_entry(identity=identity, source_evidence=source_evidence)
        event_date = _utc_datetime(entry.event_at).date()
        entries_by_date.setdefault(event_date, []).append(entry)

    groups = [
        EventIntelligenceTimelineGroup(
            event_date=event_date,
            entries=sorted(entries, key=_timeline_entry_sort_key),
        )
        for event_date, entries in sorted(entries_by_date.items(), key=lambda item: item[0], reverse=True)
    ]
    latest_as_of = max(item.as_of for item in validated_items)

    return EventIntelligenceTimeline(
        status=EventIntelligenceTimelineStatus.READY,
        as_of=latest_as_of,
        reason=None,
        raw_item_count=len(validated_items),
        deduped_event_count=len(grouped_items),
        source_evidence_count=total_source_evidence,
        groups=groups,
    )


def _validated_item(item: EventIntelligenceItem) -> EventIntelligenceItem:
    candidate = EventIntelligenceItem.model_validate(item.model_dump())
    validate_event_intelligence_visibility(
        published_at=candidate.published_at,
        as_of=candidate.as_of,
    )
    return candidate


def _build_entry(
    *,
    identity: tuple[str, ...],
    source_evidence: list[EventIntelligenceItem],
) -> EventIntelligenceTimelineEntry:
    lead_item = source_evidence[0]

    return EventIntelligenceTimelineEntry(
        event_key="|".join(identity),
        symbol=lead_item.symbol,
        market=lead_item.market,
        event_type=lead_item.event_type,
        subtype=lead_item.subtype,
        title=lead_item.title,
        summary=lead_item.summary,
        event_at=lead_item.event_at,
        confirmed_at=_latest_optional_datetime(item.confirmed_at for item in source_evidence),
        latest_published_at=max(item.published_at for item in source_evidence),
        latest_as_of=max(item.as_of for item in source_evidence),
        direction=lead_item.direction,
        related_period=lead_item.related_period,
        max_confidence=max(item.confidence for item in source_evidence),
        max_importance_score=max(item.importance_score for item in source_evidence),
        source_count=len(source_evidence),
        source_evidence=source_evidence,
    )


def _deduplicate_source_evidence(items: Sequence[EventIntelligenceItem]) -> list[EventIntelligenceItem]:
    deduped: dict[tuple[str, ...], EventIntelligenceItem] = {}
    payload_refs_by_key: dict[tuple[str, ...], set[str]] = {}

    for item in items:
        dedupe_key = _source_identity(item)
        if dedupe_key not in deduped:
            deduped[dedupe_key] = item
            payload_refs_by_key[dedupe_key] = set(item.payload_refs or [])
            continue
        payload_refs_by_key[dedupe_key].update(item.payload_refs or [])

    merged_items: list[EventIntelligenceItem] = []
    for dedupe_key, item in deduped.items():
        payload_refs = sorted(payload_refs_by_key[dedupe_key]) or None
        merged_items.append(item.model_copy(update={"payload_refs": payload_refs}))
    return sorted(merged_items, key=_timeline_item_sort_key)


def _timeline_entry_sort_key(entry: EventIntelligenceTimelineEntry) -> tuple[object, ...]:
    lead_source = entry.source_evidence[0]
    return (
        -_timestamp(entry.latest_as_of),
        -_timestamp(entry.latest_published_at),
        -entry.max_importance_score,
        _normalized_text(lead_source.source_name),
        lead_source.source_type.value,
        lead_source.source_url or "",
        _normalized_text(entry.title),
        entry.event_key,
    )


def _timeline_item_sort_key(item: EventIntelligenceItem) -> tuple[object, ...]:
    return (
        -_timestamp(item.as_of),
        -_timestamp(item.published_at),
        -item.importance_score,
        _normalized_text(item.source_name),
        item.source_type.value,
        item.source_url or "",
        item.id,
    )


def _event_identity(item: EventIntelligenceItem) -> tuple[str, ...]:
    return (
        _normalized_text(item.symbol),
        _normalized_text(item.market),
        item.event_type.value,
        _normalized_text(item.subtype),
        _utc_datetime(item.event_at).isoformat(),
        item.direction.value,
        _normalized_text(item.related_period or ""),
        _normalized_text(item.title),
    )


def _source_identity(item: EventIntelligenceItem) -> tuple[str, ...]:
    return (
        *_event_identity(item),
        item.source_type.value,
        _normalized_text(item.source_name),
        item.source_url or "",
        _utc_datetime(item.published_at).isoformat(),
    )


def _latest_optional_datetime(values: Sequence[datetime | None] | list[datetime | None] | tuple[datetime | None, ...]) -> datetime | None:
    non_null = [value for value in values if value is not None]
    if not non_null:
        return None
    return max(non_null)


def _normalized_text(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def _timestamp(value: datetime) -> float:
    return _utc_datetime(value).timestamp()


def _utc_datetime(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


__all__ = [
    "EventIntelligenceTimeline",
    "EventIntelligenceTimelineEntry",
    "EventIntelligenceTimelineGroup",
    "EventIntelligenceTimelineStatus",
    "aggregate_event_timeline",
    "build_empty_event_timeline",
    "build_insufficient_event_timeline",
]
