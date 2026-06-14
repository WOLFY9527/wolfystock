# -*- coding: utf-8 -*-
"""Focused tests for the market-moving event radar contract scaffold."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from api.v1.schemas.event_radar import (
    EventRadarCategory,
    EventRadarImpactDirection,
    EventRadarImpactStatus,
    EventRadarItem,
    EventRadarSnapshot,
    EventRadarSourceStatus,
)
from src.services.event_radar_service import (
    EVENT_RADAR_NO_ADVICE_DISCLOSURE,
    EventRadarService,
    build_event_radar_snapshot,
    build_no_evidence_event_radar_snapshot,
)


AS_OF = datetime(2026, 6, 14, 9, 30, tzinfo=timezone.utc)

FORBIDDEN_RUNTIME_TERMS = (
    "buy",
    "sell",
    "add position",
    "reduce position",
    "stop-loss",
    "take-profit",
    "target price",
    "predicted return",
    "ai recommends",
    "place order",
    "submit order",
)

FORBIDDEN_LEAK_MARKERS = (
    "traceback",
    "exception",
    "rawpayload",
    "providerpayload",
    "/users/",
    "api_key",
    "sessionid",
    "session_id",
    "bearer ",
    "sk-",
)

FORBIDDEN_FEED_KEYS = (
    "headline",
    "url",
    "sourceUrl",
    "rawPayload",
    "providerPayload",
    "author",
    "html",
    "page",
    "cursor",
    "limit",
    "offset",
    "nextCursor",
    "hasMore",
)


def _event_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "evt-radar-macro-001",
        "title": "US CPI surprise raises valuation review pressure across rate-sensitive groups",
        "category": EventRadarCategory.MACRO,
        "impactStatus": EventRadarImpactStatus.HIGH_ATTENTION,
        "impactDirection": EventRadarImpactDirection.NEGATIVE,
        "affectedSectors": ["software", "semiconductors"],
        "affectedThemes": ["rate_sensitivity", "duration_risk"],
        "relatedSymbols": ["QQQ", "SMH", "AAPL"],
        "relatedMarketSignals": ["rates", "sector_rotation", "watchlist"],
        "reviewModules": ["macro_context", "home_overview", "watchlist_context"],
        "sourceStatus": EventRadarSourceStatus.READY,
        "freshness": "delayed",
        "summary": (
            "Macro release pressure may affect discount-rate assumptions and sector leadership, "
            "so impacted holdings and watchlist names should be reviewed."
        ),
        "noAdviceDisclosure": EVENT_RADAR_NO_ADVICE_DISCLOSURE,
    }
    payload.update(overrides)
    return payload


def _assert_no_forbidden_terms(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for term in FORBIDDEN_RUNTIME_TERMS:
        assert term not in serialized


def _assert_no_leak_markers(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for marker in FORBIDDEN_LEAK_MARKERS:
        assert marker not in serialized


def test_event_radar_snapshot_serializes_contract_shape() -> None:
    snapshot = build_event_radar_snapshot(
        items=[_event_payload()],
        as_of=AS_OF,
        source_status=EventRadarSourceStatus.READY,
    )

    dumped = snapshot.model_dump(mode="json")

    assert dumped["schemaVersion"] == "event_radar_snapshot_v1"
    assert dumped["sourceStatus"] == "ready"
    assert dumped["itemCount"] == 1
    assert dumped["items"][0]["category"] == "macro"
    assert dumped["items"][0]["impactStatus"] == "high_attention"
    assert dumped["items"][0]["impactDirection"] == "negative"
    assert dumped["items"][0]["affectedSectors"] == ["software", "semiconductors"]
    assert dumped["items"][0]["relatedMarketSignals"] == ["rates", "sector_rotation", "watchlist"]
    assert dumped["items"][0]["reviewModules"] == ["macro_context", "home_overview", "watchlist_context"]


def test_no_evidence_default_snapshot_is_valid_and_safe() -> None:
    snapshot = build_no_evidence_event_radar_snapshot(as_of=AS_OF)

    assert isinstance(snapshot, EventRadarSnapshot)
    assert snapshot.sourceStatus is EventRadarSourceStatus.NO_EVIDENCE
    assert snapshot.freshness == "unavailable"
    assert snapshot.itemCount == 0
    assert snapshot.items == []
    assert "no verified event source" in snapshot.summary.lower()
    assert snapshot.noAdviceDisclosure == EVENT_RADAR_NO_ADVICE_DISCLOSURE

    dumped = snapshot.model_dump(mode="json")
    _assert_no_forbidden_terms(dumped)
    _assert_no_leak_markers(dumped)


def test_example_items_are_impact_oriented_and_not_headline_feed_entries() -> None:
    snapshot = build_event_radar_snapshot(
        items=[
            _event_payload(),
            _event_payload(
                id="evt-radar-portfolio-001",
                title="Portfolio earnings cluster creates concentrated review workload this week",
                category=EventRadarCategory.PORTFOLIO,
                impactStatus=EventRadarImpactStatus.REVIEW,
                impactDirection=EventRadarImpactDirection.MIXED,
                affectedSectors=["internet"],
                affectedThemes=["earnings_cluster", "position_overlap"],
                relatedSymbols=["AMZN", "GOOGL"],
                relatedMarketSignals=["earnings", "portfolio"],
                reviewModules=["portfolio_context", "earnings_calendar", "risk_review"],
                summary=(
                    "Several held or closely tracked names report in the same window, which can "
                    "change portfolio review priority and scenario preparation."
                ),
            ),
        ],
        as_of=AS_OF,
        source_status=EventRadarSourceStatus.READY,
    )

    assert all(item.affectedSectors for item in snapshot.items)
    assert all(item.affectedThemes for item in snapshot.items)
    assert all(item.relatedMarketSignals for item in snapshot.items)
    assert all(item.reviewModules for item in snapshot.items)
    assert "headline" not in snapshot.model_dump_json()


def test_contract_rejects_forbidden_trading_advice_language() -> None:
    with pytest.raises(ValidationError):
        EventRadarItem.model_validate(
            _event_payload(
                title="Buy semiconductors now",
                impactDirection="positive",
                summary="Immediate buy signal after the CPI release.",
            )
        )


def test_contract_rejects_internal_diagnostics_and_secret_like_markers() -> None:
    with pytest.raises(ValidationError):
        EventRadarItem.model_validate(
            _event_payload(
                impactDirection="negative",
                summary=(
                    "Traceback: provider failed at /Users/test with api_key=sk-secret, "
                    "reasonCode=provider_timeout, debugRef=abc, see https://internal.example.com"
                ),
            )
        )


def test_dirty_caller_input_is_normalized_to_bounded_homepage_card_fields() -> None:
    snapshot = build_event_radar_snapshot(
        items=[
            _event_payload(
                impactStatus="HIGH ATTENTION",
                impactDirection="downside pressure",
                affectedSectors=[" Software ", "semiconductors", "software", "internet", "banks"],
                affectedThemes=[" Rate Sensitivity ", "duration-risk", "earnings cluster", "fx headwind"],
                relatedSymbols=[" qqq ", "smh", "AAPL", "AAPL", "msft", "googl"],
                relatedMarketSignals=[
                    "front_end_yields_up",
                    "vix spike",
                    "sector leadership",
                    "watch list",
                    "portfolio overlap",
                    "earnings density",
                    "custom alpha pulse",
                ],
                reviewModules=[" Macro Context ", "home overview", "watchlist_context", "risk review"],
                sourceStatus="available",
                freshness="stale snapshot",
                headline="Fed headline should not ship",
                url="https://news.example.com/story",
                rawPayload={"token": "secret"},
                author="Reporter",
                html="<p>raw</p>",
                page=3,
                cursor="next-page",
            )
        ],
        as_of=AS_OF,
        source_status=EventRadarSourceStatus.READY,
    )

    dumped = snapshot.model_dump(mode="json")
    item = dumped["items"][0]

    assert item["impactStatus"] == "high_attention"
    assert item["impactDirection"] == "negative"
    assert item["sourceStatus"] == "ready"
    assert item["freshness"] == "stale"
    assert item["affectedSectors"] == ["software", "semiconductors", "internet"]
    assert item["affectedThemes"] == ["rate_sensitivity", "duration_risk", "earnings_cluster"]
    assert item["relatedSymbols"] == ["QQQ", "SMH", "AAPL", "MSFT"]
    assert item["relatedMarketSignals"] == ["rates", "volatility", "sector_rotation", "watchlist"]
    assert item["reviewModules"] == ["macro_context", "home_overview", "watchlist_context"]
    for key in FORBIDDEN_FEED_KEYS:
        assert key not in item


def test_direct_item_validation_ignores_known_news_feed_fields_without_exposing_them() -> None:
    item = EventRadarItem.model_validate(
        _event_payload(
            impactDirection="mixed",
            headline="Wire headline",
            url="https://news.example.com/story",
            rawPayload={"headline": "wire"},
            author="Wire desk",
            html="<p>raw</p>",
            page=1,
            cursor="abc",
        )
    )

    dumped = item.model_dump(mode="json")
    for key in FORBIDDEN_FEED_KEYS:
        assert key not in dumped


def test_snapshot_payload_does_not_introduce_generic_news_feed_shape() -> None:
    snapshot = build_event_radar_snapshot(
        items=[_event_payload()],
        as_of=AS_OF,
        source_status=EventRadarSourceStatus.READY,
    )

    dumped = snapshot.model_dump(mode="json")
    serialized = json.dumps(dumped, ensure_ascii=False)
    for key in FORBIDDEN_FEED_KEYS:
        assert f'"{key}"' not in serialized


def test_list_fields_are_bounded_for_homepage_card_density() -> None:
    item = EventRadarItem.model_validate(
        _event_payload(
            impactDirection="mixed",
            affectedSectors=["software", "semiconductors", "internet", "banks"],
            affectedThemes=["rates", "duration", "earnings", "fx"],
            relatedSymbols=["QQQ", "SMH", "AAPL", "MSFT", "GOOGL"],
            relatedMarketSignals=["rates", "volatility", "breadth", "watchlist", "portfolio"],
            reviewModules=["macro_context", "home_overview", "watchlist_context", "risk_review"],
        )
    )

    assert len(item.affectedSectors) == 3
    assert len(item.affectedThemes) == 3
    assert len(item.relatedSymbols) == 4
    assert len(item.relatedMarketSignals) == 4
    assert len(item.reviewModules) == 3


def test_service_returns_same_safe_no_evidence_snapshot_without_wired_sources() -> None:
    service = EventRadarService()

    snapshot = service.build_snapshot(as_of=AS_OF)

    assert snapshot.sourceStatus is EventRadarSourceStatus.NO_EVIDENCE
    assert snapshot.items == []
    assert snapshot.itemCount == 0
    _assert_no_forbidden_terms(snapshot.model_dump(mode="json"))
    _assert_no_leak_markers(snapshot.model_dump(mode="json"))
