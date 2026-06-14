# -*- coding: utf-8 -*-
"""Focused tests for the standalone source freshness summary contract."""

from __future__ import annotations

import json

from api.v1.schemas.source_freshness_summary import SourceFreshnessSummary
from src.services.source_freshness_summary_service import build_source_freshness_summary


def _serialized_summary(payload: dict[str, object]) -> str:
    summary = build_source_freshness_summary(payload)
    validated = SourceFreshnessSummary.model_validate(summary.model_dump(by_alias=True))
    return json.dumps(validated.model_dump(by_alias=True), ensure_ascii=False, sort_keys=True).lower()


def test_source_freshness_summary_defaults_to_no_evidence_when_sources_empty() -> None:
    summary = build_source_freshness_summary({})

    assert summary.model_dump(by_alias=True) == {
        "status": "no_evidence",
        "asOf": None,
        "sources": [],
        "overallFreshness": "no_evidence",
        "staleCount": 0,
        "unavailableCount": 0,
        "message": "暂无足够来源新鲜度证据，当前仅保留观察位。",
        "noAdviceDisclosure": "仅供研究观察，不构成投资建议。",
    }


def test_source_freshness_summary_marks_all_fresh_sources_as_ready() -> None:
    summary = build_source_freshness_summary(
        {
            "sources": [
                {
                    "key": "market",
                    "label": "Market data",
                    "category": "market",
                    "freshness": "fresh",
                    "asOf": "2026-06-14T09:30:00Z",
                },
                {
                    "key": "research",
                    "label": "Research context",
                    "category": "research",
                    "freshness": "fresh",
                    "asOf": "2026-06-14T09:30:00Z",
                },
            ]
        }
    )

    assert summary.status == "ready"
    assert summary.as_of == "2026-06-14T09:30:00Z"
    assert summary.overall_freshness == "fresh"
    assert summary.stale_count == 0
    assert summary.unavailable_count == 0
    assert [source.public_message for source in summary.sources] == [
        "来源更新及时，适合观察。",
        "来源更新及时，适合观察。",
    ]


def test_source_freshness_summary_aggregates_stale_and_unavailable_sources() -> None:
    summary = build_source_freshness_summary(
        {
            "sources": [
                {
                    "key": "market",
                    "label": "Market data",
                    "category": "market",
                    "freshness": "recent",
                    "asOf": "2026-06-14T09:30:00Z",
                },
                {
                    "key": "event",
                    "label": "Event radar",
                    "category": "event",
                    "freshness": "stale",
                    "asOf": "2026-06-12T09:30:00Z",
                },
                {
                    "key": "watchlist",
                    "label": "Watchlist",
                    "category": "watchlist",
                    "freshness": "unavailable",
                    "publicMessage": "Provider timeout",
                },
            ]
        }
    )

    assert summary.status == "limited"
    assert summary.overall_freshness == "unavailable"
    assert summary.stale_count == 1
    assert summary.unavailable_count == 1
    assert summary.message == "部分来源已过时或暂不可用，当前仅适合谨慎观察。"


def test_source_freshness_summary_sanitizes_source_labels_and_keys() -> None:
    summary = build_source_freshness_summary(
        {
            "sources": [
                {
                    "key": "provider.market_feed",
                    "label": "https://internal.example/feed?token=abc",
                    "category": "market",
                    "freshness": "fresh",
                },
                {
                    "key": "research-note",
                    "label": "Research digest",
                    "category": "research",
                    "freshness": "recent",
                },
            ]
        }
    )

    assert [(source.key, source.label) for source in summary.sources] == [
        ("market", "市场数据"),
        ("research_note", "Research digest"),
    ]


def test_source_freshness_summary_does_not_leak_internal_diagnostics_or_secrets() -> None:
    dumped = _serialized_summary(
        {
            "asOf": "2026-06-14T09:30:00Z",
            "message": "Traceback: provider timeout token=abc secret-key",
            "sources": [
                {
                    "key": "provider://market",
                    "label": "provider error",
                    "category": "market",
                    "freshness": "stale",
                    "asOf": "https://internal.example/timestamp",
                    "publicMessage": "Provider timeout at https://internal.example token=abc",
                    "provider": "secret-provider",
                    "reasonCode": "raw_internal_reason",
                    "sessionId": "session-123",
                    "apiKey": "secret-key",
                    "traceback": "Traceback",
                }
            ],
        }
    )

    for forbidden in (
        "provider timeout",
        "internal.example",
        "secret-provider",
        "raw_internal_reason",
        "session-123",
        "secret-key",
        "token=abc",
        "traceback",
        "provider://market",
    ):
        assert forbidden not in dumped


def test_source_freshness_summary_avoids_trading_advice_terms() -> None:
    summary = build_source_freshness_summary(
        {
            "message": "Buy now",
            "sources": [
                {
                    "key": "market",
                    "label": "Market data",
                    "category": "market",
                    "freshness": "fresh",
                    "publicMessage": "立即交易",
                }
            ],
        }
    )

    dumped = json.dumps(summary.model_dump(by_alias=True), ensure_ascii=False, sort_keys=True).lower()

    for forbidden in ("buy now", "sell now", "立即交易", "交易指令", "target price", "stop loss"):
        assert forbidden not in dumped
    assert summary.no_advice_disclosure == "仅供研究观察，不构成投资建议。"
