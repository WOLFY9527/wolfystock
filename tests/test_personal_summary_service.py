# -*- coding: utf-8 -*-
"""Focused safety tests for the bounded personal summary contract."""

from __future__ import annotations

import json

from api.v1.schemas.portfolio import PortfolioSnapshotResponse
from api.v1.schemas.watchlist import WatchlistItemResponse
from src.services.personal_summary_service import PersonalSummaryService


FORBIDDEN_MARKERS = (
    "traceback",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "raw confidence",
    "rawconfidence",
    "token",
    "session",
    "api_key",
    "secret",
    "provider error",
    "/users/",
    "buy now",
    "sell now",
    "place order",
    "broker execution",
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "清仓",
    "止损",
    "止盈",
    "目标价",
    "收益预测",
    "ai推荐",
    "智能选股",
    "交易执行",
)


def _assert_no_forbidden_markers(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for marker in FORBIDDEN_MARKERS:
        assert marker.lower() not in serialized


def test_contract_serializes_portfolio_and_watchlist_summary() -> None:
    service = PersonalSummaryService()

    response = service.build_summary(
        portfolio_snapshot={
            "total_equity": 250000.0,
            "daily_change": 1800.5,
            "cash_percent": 12.5,
            "largest_exposure": 28.1,
            "risk_score": 41.0,
            "risk_status": "observe",
            "concentration_status": "observe",
            "account_count": 1,
            "data_status": "ready",
        },
        watchlist_items=[
            {
                "symbol": "NVDA",
                "displayName": "NVIDIA",
                "symbolStatus": "review",
                "movementStatus": "stronger",
                "relativeStrengthStatus": "stronger",
                "volumeStatus": "volume_expanded",
                "evidenceStatus": "review",
                "researchStatus": "review",
                "lastReviewedAt": "2026-06-14T08:00:00Z",
                "reviewReason": "Momentum evidence changed and requires review.",
            },
            {
                "symbol": "TSLA",
                "displayName": "Tesla",
                "evidenceStatus": "no_evidence",
                "researchStatus": "no_evidence",
            },
        ],
        portfolio_connected=True,
    )

    payload = response.model_dump(mode="json")

    assert payload["status"] == "partial"
    assert payload["portfolioSnapshot"]["totalValue"] == 250000.0
    assert payload["portfolioSnapshot"]["dailyChange"] == 1800.5
    assert payload["portfolioSnapshot"]["cashPercent"] == 12.5
    assert payload["portfolioSnapshot"]["largestExposure"] == 28.1
    assert payload["portfolioSnapshot"]["riskStatus"] == "observe"
    assert payload["watchlistExceptions"]["items"][0]["symbol"] == "NVDA"
    assert payload["watchlistExceptions"]["items"][0]["movementStatus"] == "stronger"
    assert payload["researchCoverage"]["missingSymbols"] == ["TSLA"]
    assert payload["reviewQueue"]["items"][0]["symbol"] == "NVDA"
    assert "not personalized financial advice" in payload["noAdviceDisclosure"].lower()


def test_no_connected_portfolio_state_is_safe_and_can_mark_sample_data() -> None:
    service = PersonalSummaryService()

    response = service.build_summary(
        portfolio_snapshot=None,
        watchlist_items=[],
        portfolio_connected=False,
        sample_data=True,
    )

    payload = response.model_dump(mode="json")

    assert payload["status"] == "no_evidence"
    assert payload["portfolioSnapshot"]["connected"] is False
    assert payload["portfolioSnapshot"]["sampleData"] is True
    assert payload["portfolioSnapshot"]["concentrationStatus"] == "sample_data"
    assert payload["dataQuality"]["portfolioStatus"] == "no_evidence"
    assert payload["dataQuality"]["sampleData"] is True


def test_watchlist_exceptions_do_not_use_trading_advice_terms() -> None:
    service = PersonalSummaryService()

    response = service.build_summary(
        watchlist_items=[
            {
                "symbol": "AAPL",
                "displayName": "AAPL 买入计划",
                "symbolStatus": "review",
                "researchStatus": "review",
                "evidenceStatus": "review",
                "reviewReason": "立即买入并触发 broker execution。",
            }
        ]
    )

    payload = response.model_dump(mode="json")

    assert payload["watchlistExceptions"]["items"][0]["displayName"] == "AAPL"
    assert payload["watchlistExceptions"]["items"][0]["reviewReason"] == "Review evidence changed."
    _assert_no_forbidden_markers(payload)


def test_missing_evidence_is_represented_as_no_evidence() -> None:
    service = PersonalSummaryService()

    response = service.build_summary(
        watchlist_items=[
            {
                "symbol": "MSFT",
                "displayName": "Microsoft",
                "researchStatus": "missing_data",
                "evidenceStatus": "missing",
            }
        ]
    )

    payload = response.model_dump(mode="json")

    assert payload["status"] == "no_evidence"
    assert payload["watchlistExceptions"]["status"] == "no_evidence"
    assert payload["watchlistExceptions"]["items"][0]["researchStatus"] == "no_evidence"
    assert payload["watchlistExceptions"]["items"][0]["evidenceStatus"] == "no_evidence"
    assert payload["researchCoverage"]["status"] == "no_evidence"
    assert payload["researchCoverage"]["missingSymbols"] == ["MSFT"]


def test_response_does_not_leak_internal_diagnostics_or_secrets() -> None:
    service = PersonalSummaryService()

    response = service.build_summary(
        portfolio_snapshot={
            "total_equity": 1000.0,
            "risk_status": "review",
            "concentration_status": "review",
            "reasonCode": "internal_reason",
            "trustLevel": "high",
            "sourceType": "private_feed",
            "rawConfidence": 0.91,
            "traceback": "Traceback secret token",
            "debugPath": "/Users/secret/workdir",
        },
        watchlist_items=[
            {
                "symbol": "META",
                "displayName": "Meta",
                "reviewReason": "Traceback secret token /Users/root api_key=123",
                "evidenceStatus": "review",
                "researchStatus": "review",
            }
        ],
    )

    payload = response.model_dump(mode="json")

    _assert_no_forbidden_markers(payload)
    assert "reasonCode" not in payload["portfolioSnapshot"]
    assert "trustLevel" not in payload["portfolioSnapshot"]
    assert "sourceType" not in payload["portfolioSnapshot"]


def test_existing_watchlist_and_portfolio_safe_shapes_can_be_imported() -> None:
    service = PersonalSummaryService()

    portfolio_snapshot = PortfolioSnapshotResponse(
        as_of="2026-06-14",
        cost_method="fifo",
        currency="USD",
        account_count=1,
        total_cash=12000.0,
        total_market_value=88000.0,
        total_equity=100000.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        fee_total=0.0,
        tax_total=0.0,
        fx_stale=False,
        data_status="ready",
        availability={"connected": True},
        analytics={
            "pnl": {
                "display_currency": "USD",
                "realized": {"amount": 0.0, "currency": "USD"},
                "unrealized": {"amount": 0.0, "currency": "USD"},
                "total": {"amount": 0.0, "currency": "USD"},
            },
            "exposure": {"by_account": [], "by_currency": [], "by_market": [], "by_symbol": [], "by_sector": []},
            "risk": {
                "largest_position": {"symbol": "NVDA", "percent": 26.4},
                "holding_count": 4,
                "account_count": 1,
                "cash_percent": 12.0,
            },
        },
    )
    watchlist_item = WatchlistItemResponse(
        id=1,
        symbol="AMD",
        market="us",
        name="AMD",
        source="scanner",
        symbol_status="ready",
        research_status="stale_or_cached",
        data_quality="stale_or_cached",
        evidence_status="stale_or_cached",
        last_reviewed_at="2026-06-13T12:00:00Z",
        no_advice_disclosure="This watchlist item provides bounded research context only.",
    )

    response = service.build_summary(
        portfolio_snapshot=portfolio_snapshot.model_dump(mode="json"),
        watchlist_items=[watchlist_item.model_dump(mode="json")],
        portfolio_connected=True,
    )
    payload = response.model_dump(mode="json")

    assert payload["portfolioSnapshot"]["totalValue"] == 100000.0
    assert payload["portfolioSnapshot"]["cashPercent"] == 12.0
    assert payload["watchlistExceptions"]["items"][0]["researchStatus"] == "stale"
    assert payload["watchlistExceptions"]["items"][0]["evidenceStatus"] == "stale"
    assert payload["researchCoverage"]["staleSymbols"] == ["AMD"]
    _assert_no_forbidden_markers(payload)
