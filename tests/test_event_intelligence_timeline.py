# -*- coding: utf-8 -*-
"""Focused regression coverage for event intelligence timeline aggregation."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from api.v1.schemas.event_intelligence import (
    EventIntelligenceDirection,
    EventIntelligenceFreshnessStatus,
    EventIntelligenceItem,
    EventIntelligenceProvenance,
    EventIntelligenceSourceType,
    EventIntelligenceType,
)
from src.services.event_intelligence_timeline import (
    EventIntelligenceTimelineStatus,
    aggregate_event_timeline,
    build_insufficient_event_timeline,
)


def _item(**overrides: object) -> EventIntelligenceItem:
    payload: dict[str, object] = {
        "id": "evt-aapl-filing-001",
        "symbol": "AAPL",
        "market": "us",
        "event_type": EventIntelligenceType.EARNINGS,
        "subtype": "earnings_date",
        "title": "Q2 earnings scheduled",
        "summary": "Apple scheduled its quarterly earnings release.",
        "source_type": EventIntelligenceSourceType.COMPANY_FILING,
        "source_name": "SEC 8-K",
        "source_url": "https://example.test/aapl-earnings-filings",
        "published_at": datetime(2026, 5, 10, 14, 0, tzinfo=timezone.utc),
        "event_at": datetime(2026, 5, 20, 20, 0, tzinfo=timezone.utc),
        "confirmed_at": None,
        "as_of": datetime(2026, 5, 12, 14, 0, tzinfo=timezone.utc),
        "confidence": 0.82,
        "importance_score": 0.91,
        "direction": EventIntelligenceDirection.NEUTRAL,
        "freshness_status": EventIntelligenceFreshnessStatus.FRESH,
        "provenance": EventIntelligenceProvenance.OFFICIAL_PUBLIC,
        "related_period": "2026Q2",
        "payload_refs": ["sec:8k:2026-05-10"],
    }
    payload.update(overrides)
    return EventIntelligenceItem.model_validate(payload)


def test_aggregate_event_timeline_returns_empty_status_for_no_items() -> None:
    timeline = aggregate_event_timeline([])

    assert timeline.status is EventIntelligenceTimelineStatus.EMPTY
    assert timeline.groups == []
    assert timeline.raw_item_count == 0
    assert timeline.deduped_event_count == 0
    assert timeline.source_evidence_count == 0
    assert timeline.reason == "no_events"


def test_build_insufficient_event_timeline_returns_requested_reason() -> None:
    as_of = datetime(2026, 5, 12, 14, 0, tzinfo=timezone.utc)

    timeline = build_insufficient_event_timeline(as_of=as_of, reason="provider_unavailable")

    assert timeline.status is EventIntelligenceTimelineStatus.INSUFFICIENT
    assert timeline.as_of == as_of
    assert timeline.reason == "provider_unavailable"
    assert timeline.groups == []


def test_aggregate_event_timeline_groups_and_deduplicates_while_preserving_sources() -> None:
    sec_item = _item()
    reuters_item = _item(
        id="evt-aapl-news-001",
        source_type=EventIntelligenceSourceType.NEWSWIRE,
        source_name="Reuters",
        source_url="https://example.test/reuters/aapl-earnings",
        published_at=datetime(2026, 5, 10, 14, 5, tzinfo=timezone.utc),
        as_of=datetime(2026, 5, 12, 14, 30, tzinfo=timezone.utc),
        importance_score=0.89,
        payload_refs=["news:reuters:evt-1"],
    )
    reuters_duplicate = _item(
        id="evt-aapl-news-002",
        source_type=EventIntelligenceSourceType.NEWSWIRE,
        source_name="Reuters",
        source_url="https://example.test/reuters/aapl-earnings",
        published_at=datetime(2026, 5, 10, 14, 5, tzinfo=timezone.utc),
        as_of=datetime(2026, 5, 12, 14, 30, tzinfo=timezone.utc),
        importance_score=0.89,
        payload_refs=["news:reuters:evt-2"],
    )

    timeline = aggregate_event_timeline([sec_item, reuters_duplicate, reuters_item])

    assert timeline.status is EventIntelligenceTimelineStatus.READY
    assert timeline.raw_item_count == 3
    assert timeline.deduped_event_count == 1
    assert timeline.source_evidence_count == 2
    assert len(timeline.groups) == 1
    assert timeline.groups[0].event_date == date(2026, 5, 20)

    entry = timeline.groups[0].entries[0]
    assert entry.source_count == 2
    assert entry.latest_as_of == datetime(2026, 5, 12, 14, 30, tzinfo=timezone.utc)
    assert entry.latest_published_at == datetime(2026, 5, 10, 14, 5, tzinfo=timezone.utc)
    assert entry.max_importance_score == pytest.approx(0.91)
    assert [item.id for item in entry.source_evidence] == ["evt-aapl-news-001", "evt-aapl-filing-001"]
    assert entry.source_evidence[0].payload_refs == ["news:reuters:evt-1", "news:reuters:evt-2"]


def test_aggregate_event_timeline_sorts_groups_and_entries_deterministically() -> None:
    items = [
        _item(
            id="evt-aapl-guidance-001",
            event_type=EventIntelligenceType.GUIDANCE,
            subtype="guidance_update",
            title="Q2 guidance updated",
            summary="Apple updated quarterly guidance.",
            event_at=datetime(2026, 5, 20, 18, 0, tzinfo=timezone.utc),
            published_at=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
            as_of=datetime(2026, 5, 12, 12, 0, tzinfo=timezone.utc),
            importance_score=0.80,
        ),
        _item(
            id="evt-aapl-management-001",
            event_type=EventIntelligenceType.MANAGEMENT,
            subtype="management_change",
            title="Board appoints CFO",
            summary="Apple appointed a new CFO.",
            source_name="Company IR",
            source_type=EventIntelligenceSourceType.COMPANY_IR,
            source_url="https://example.test/aapl-ir-cfo",
            event_at=datetime(2026, 5, 22, 14, 0, tzinfo=timezone.utc),
            published_at=datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc),
            as_of=datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc),
            importance_score=0.75,
        ),
        _item(
            id="evt-aapl-earnings-002",
            title="Q2 earnings scheduled",
            summary="Apple scheduled its quarterly earnings release.",
            event_at=datetime(2026, 5, 20, 20, 0, tzinfo=timezone.utc),
            published_at=datetime(2026, 5, 11, 13, 0, tzinfo=timezone.utc),
            as_of=datetime(2026, 5, 12, 13, 0, tzinfo=timezone.utc),
            importance_score=0.93,
        ),
    ]

    timeline = aggregate_event_timeline(items)
    reversed_timeline = aggregate_event_timeline(list(reversed(items)))

    assert [group.event_date for group in timeline.groups] == [date(2026, 5, 22), date(2026, 5, 20)]
    assert [entry.title for entry in timeline.groups[1].entries] == [
        "Q2 earnings scheduled",
        "Q2 guidance updated",
    ]
    assert timeline.model_dump(mode="json") == reversed_timeline.model_dump(mode="json")


def test_aggregate_event_timeline_rejects_future_publication_even_from_unvalidated_input() -> None:
    payload = _item().model_dump()
    payload.update(
        published_at=datetime(2026, 5, 13, 14, 0, tzinfo=timezone.utc),
        as_of=datetime(2026, 5, 12, 14, 0, tzinfo=timezone.utc),
    )
    invalid_item = EventIntelligenceItem.model_construct(**payload)

    with pytest.raises(ValueError, match="published_at cannot be after as_of"):
        aggregate_event_timeline([invalid_item])
