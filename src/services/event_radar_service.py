# -*- coding: utf-8 -*-
"""Safe scaffold service for market-moving event radar snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Mapping

from api.v1.schemas.event_radar import (
    EventRadarFreshness,
    EventRadarItem,
    EventRadarSnapshot,
    EventRadarSourceStatus,
)


EVENT_RADAR_NO_ADVICE_DISCLOSURE = "Observation and review context only; verify independently."
_NO_EVIDENCE_SUMMARY = "No verified event source is wired for this snapshot."
_UNAVAILABLE_SUMMARY = "Event radar source is unavailable, so no safe event snapshot is emitted."


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_as_of(as_of: datetime | None) -> datetime:
    return as_of if isinstance(as_of, datetime) else _utc_now()


def _coerce_items(items: Iterable[EventRadarItem | Mapping[str, object]]) -> list[EventRadarItem]:
    normalized: list[EventRadarItem] = []
    for item in items:
        if isinstance(item, EventRadarItem):
            normalized.append(item)
            continue
        normalized.append(EventRadarItem.model_validate(item))
    return normalized


def _derive_freshness(
    items: list[EventRadarItem],
    source_status: EventRadarSourceStatus,
) -> EventRadarFreshness:
    if source_status in {EventRadarSourceStatus.NO_EVIDENCE, EventRadarSourceStatus.UNAVAILABLE}:
        return EventRadarFreshness.UNAVAILABLE
    if not items:
        return EventRadarFreshness.UNKNOWN

    if any(item.freshness is EventRadarFreshness.STALE for item in items):
        return EventRadarFreshness.STALE
    if any(item.freshness is EventRadarFreshness.DELAYED for item in items):
        return EventRadarFreshness.DELAYED
    if all(item.freshness is EventRadarFreshness.FRESH for item in items):
        return EventRadarFreshness.FRESH
    return EventRadarFreshness.UNKNOWN


def _derive_summary(
    *,
    items: list[EventRadarItem],
    source_status: EventRadarSourceStatus,
) -> str:
    if source_status is EventRadarSourceStatus.NO_EVIDENCE:
        return _NO_EVIDENCE_SUMMARY
    if source_status is EventRadarSourceStatus.UNAVAILABLE:
        return _UNAVAILABLE_SUMMARY
    high_attention_count = sum(1 for item in items if item.impactStatus.value == "high_attention")
    if high_attention_count:
        return (
            f"{len(items)} impact-oriented event items are available; "
            f"{high_attention_count} require high-attention review."
        )
    return f"{len(items)} impact-oriented event items are available for observation or review."


def build_no_evidence_event_radar_snapshot(*, as_of: datetime | None = None) -> EventRadarSnapshot:
    return EventRadarSnapshot(
        asOf=_coerce_as_of(as_of),
        sourceStatus=EventRadarSourceStatus.NO_EVIDENCE,
        freshness=EventRadarFreshness.UNAVAILABLE,
        summary=_NO_EVIDENCE_SUMMARY,
        itemCount=0,
        items=[],
        noAdviceDisclosure=EVENT_RADAR_NO_ADVICE_DISCLOSURE,
    )


def build_event_radar_snapshot(
    *,
    items: Iterable[EventRadarItem | Mapping[str, object]],
    as_of: datetime | None = None,
    source_status: EventRadarSourceStatus = EventRadarSourceStatus.READY,
) -> EventRadarSnapshot:
    normalized_items = _coerce_items(items)
    resolved_status = EventRadarSourceStatus(source_status)
    if resolved_status is not EventRadarSourceStatus.READY and normalized_items:
        raise ValueError("only ready snapshots may carry event items")
    if resolved_status is not EventRadarSourceStatus.READY and not normalized_items:
        return EventRadarSnapshot(
            asOf=_coerce_as_of(as_of),
            sourceStatus=resolved_status,
            freshness=EventRadarFreshness.UNAVAILABLE,
            summary=_derive_summary(items=normalized_items, source_status=resolved_status),
            itemCount=0,
            items=[],
            noAdviceDisclosure=EVENT_RADAR_NO_ADVICE_DISCLOSURE,
        )
    return EventRadarSnapshot(
        asOf=_coerce_as_of(as_of),
        sourceStatus=resolved_status,
        freshness=_derive_freshness(normalized_items, resolved_status),
        summary=_derive_summary(items=normalized_items, source_status=resolved_status),
        itemCount=len(normalized_items),
        items=normalized_items,
        noAdviceDisclosure=EVENT_RADAR_NO_ADVICE_DISCLOSURE,
    )


class EventRadarService:
    """Pure scaffold service until a real curated event source is approved."""

    def build_snapshot(
        self,
        *,
        as_of: datetime | None = None,
        items: Iterable[EventRadarItem | Mapping[str, object]] | None = None,
    ) -> EventRadarSnapshot:
        if items is None:
            return build_no_evidence_event_radar_snapshot(as_of=as_of)
        return build_event_radar_snapshot(
            items=items,
            as_of=as_of,
            source_status=EventRadarSourceStatus.READY,
        )


__all__ = [
    "EVENT_RADAR_NO_ADVICE_DISCLOSURE",
    "EventRadarService",
    "build_event_radar_snapshot",
    "build_no_evidence_event_radar_snapshot",
]
