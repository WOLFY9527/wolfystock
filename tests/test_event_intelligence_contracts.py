# -*- coding: utf-8 -*-
"""Focused contract tests for event intelligence DTOs and provider boundary."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from api.v1.schemas.event_intelligence import (
    EventIntelligenceDirection,
    EventIntelligenceFreshnessStatus,
    EventIntelligenceItem,
    EventIntelligenceProvenance,
    EventIntelligenceSourceType,
    EventIntelligenceType,
)
from src.services.event_intelligence_provider_contract import EventIntelligenceProvider


def _item_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "evt-earnings-001",
        "symbol": "AAPL",
        "market": "us",
        "event_type": EventIntelligenceType.EARNINGS,
        "subtype": "earnings_date",
        "title": "Q2 earnings scheduled",
        "summary": "Apple scheduled its quarterly earnings release.",
        "source_type": EventIntelligenceSourceType.COMPANY_FILING,
        "source_name": "SEC 8-K",
        "source_url": "https://example.test/aapl-earnings",
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
    return payload


def test_event_at_can_be_future_if_published_at_was_visible_by_as_of() -> None:
    item = EventIntelligenceItem.model_validate(_item_payload())

    assert item.event_at > item.as_of
    assert item.published_at <= item.as_of
    assert item.freshness_status is EventIntelligenceFreshnessStatus.FRESH


def test_missing_as_of_is_rejected() -> None:
    payload = _item_payload()
    payload.pop("as_of")

    with pytest.raises(ValidationError, match="as_of"):
        EventIntelligenceItem.model_validate(payload)


def test_published_at_after_as_of_is_rejected_for_lookahead_bias() -> None:
    with pytest.raises(ValidationError, match="published_at cannot be after as_of"):
        EventIntelligenceItem.model_validate(
            _item_payload(
                published_at=datetime(2026, 5, 13, 14, 0, tzinfo=timezone.utc),
                as_of=datetime(2026, 5, 12, 14, 0, tzinfo=timezone.utc),
            )
        )


@pytest.mark.parametrize("field_name", ["confidence", "importance_score"])
@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_confidence_and_importance_bounds_are_enforced(field_name: str, value: float) -> None:
    with pytest.raises(ValidationError):
        EventIntelligenceItem.model_validate(_item_payload(**{field_name: value}))


@pytest.mark.parametrize(
    ("provenance", "freshness_status"),
    [
        (EventIntelligenceProvenance.FALLBACK_STATIC, EventIntelligenceFreshnessStatus.LIVE),
        (EventIntelligenceProvenance.FALLBACK_STATIC, EventIntelligenceFreshnessStatus.FRESH),
        (EventIntelligenceProvenance.UNKNOWN, EventIntelligenceFreshnessStatus.LIVE),
        (EventIntelligenceProvenance.SYNTHETIC_FIXTURE, EventIntelligenceFreshnessStatus.FRESH),
    ],
)
def test_unknown_or_fallback_states_cannot_claim_live_or_fresh(
    provenance: EventIntelligenceProvenance,
    freshness_status: EventIntelligenceFreshnessStatus,
) -> None:
    with pytest.raises(ValidationError, match="cannot claim live or fresh"):
        EventIntelligenceItem.model_validate(
            _item_payload(
                provenance=provenance,
                freshness_status=freshness_status,
            )
        )


def test_source_type_is_required() -> None:
    payload = _item_payload()
    payload.pop("source_type")

    with pytest.raises(ValidationError, match="source_type"):
        EventIntelligenceItem.model_validate(payload)


def test_provider_contract_signature_is_stable() -> None:
    params = list(inspect.signature(EventIntelligenceProvider.fetch_events).parameters)

    assert params == ["self", "symbol", "market", "start", "end", "as_of"]

