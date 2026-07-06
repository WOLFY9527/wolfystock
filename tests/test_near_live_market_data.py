from __future__ import annotations

import json
from datetime import datetime, timezone

from src.services.product_read_model import (
    build_stock_evidence_product_read_model,
    build_structure_decision_product_read_model,
)


def test_fresh_quote_while_market_open_is_available_and_usable() -> None:
    from src.services.near_live_market_data import build_canonical_market_observation

    observation = build_canonical_market_observation(
        {
            "market": "US",
            "symbol": "AAPL",
            "observationType": "quote",
            "value": 214.55,
            "currency": "USD",
            "asOf": "2026-07-06T14:31:00Z",
            "receivedAt": "2026-07-06T14:31:20Z",
            "sourceClass": "near_live_market_data",
            "sourceQuality": "reported",
        },
        surface="stock_evidence_quote",
        now=datetime(2026, 7, 6, 14, 32, tzinfo=timezone.utc),
    )

    assert observation["contractVersion"] == "near_live_market_observation_v1"
    assert observation["marketSessionState"] == "open"
    assert observation["freshnessState"] == "fresh"
    assert observation["ageSeconds"] == 60
    assert observation["usable"] is True
    assert observation["blockingReasons"] == []
    assert "providerName" not in json.dumps(observation)


def test_stale_quote_while_market_open_blocks_readiness() -> None:
    from src.services.near_live_market_data import build_canonical_market_observation

    observation = build_canonical_market_observation(
        {
            "market": "US",
            "symbol": "AAPL",
            "observationType": "quote",
            "value": 214.55,
            "currency": "USD",
            "asOf": "2026-07-06T14:00:00Z",
            "receivedAt": "2026-07-06T14:00:05Z",
            "sourceClass": "near_live_market_data",
            "sourceQuality": "reported",
        },
        surface="stock_evidence_quote",
        now=datetime(2026, 7, 6, 14, 32, tzinfo=timezone.utc),
    )

    assert observation["marketSessionState"] == "open"
    assert observation["freshnessState"] == "stale"
    assert observation["usable"] is False
    assert "outside_freshness_tolerance" in observation["blockingReasons"]


def test_friday_daily_close_remains_fresh_during_weekend_but_old_intraday_does_not() -> None:
    from src.services.near_live_market_data import build_canonical_market_observation

    sunday = datetime(2026, 7, 12, 16, 0, tzinfo=timezone.utc)
    daily_close = build_canonical_market_observation(
        {
            "market": "US",
            "symbol": "SPY",
            "observationType": "daily_ohlcv",
            "boundedPayloadRef": "historical:SPY:2026-07-10",
            "asOf": "2026-07-10T20:00:00Z",
            "receivedAt": "2026-07-10T20:05:00Z",
            "sourceClass": "local_historical_data",
            "sourceQuality": "usable",
        },
        surface="stock_evidence_technical_data",
        now=sunday,
    )
    old_intraday = build_canonical_market_observation(
        {
            "market": "US",
            "symbol": "SPY",
            "observationType": "intraday_price",
            "value": 550.12,
            "currency": "USD",
            "asOf": "2026-07-10T15:45:00Z",
            "receivedAt": "2026-07-10T15:45:05Z",
            "sourceClass": "near_live_market_data",
            "sourceQuality": "reported",
        },
        surface="stock_evidence_quote",
        now=sunday,
    )

    assert daily_close["marketSessionState"] == "non_trading_day"
    assert daily_close["freshnessState"] == "fresh"
    assert daily_close["usable"] is True
    assert old_intraday["marketSessionState"] == "non_trading_day"
    assert old_intraday["freshnessState"] == "stale"
    assert old_intraday["usable"] is False


def test_unknown_market_session_blocks_material_quote_surface() -> None:
    from src.services.near_live_market_data import build_canonical_market_observation

    observation = build_canonical_market_observation(
        {
            "market": "UNKNOWN",
            "symbol": "XYZ",
            "observationType": "quote",
            "value": 10.0,
            "asOf": "2026-07-06T14:31:00Z",
            "receivedAt": "2026-07-06T14:31:20Z",
            "sourceClass": "near_live_market_data",
        },
        surface="stock_evidence_quote",
        now=datetime(2026, 7, 6, 14, 32, tzinfo=timezone.utc),
    )

    assert observation["marketSessionState"] == "unknown"
    assert observation["freshnessState"] == "unknown"
    assert observation["usable"] is False
    assert "market_session_unknown" in observation["blockingReasons"]


def test_missing_and_malformed_quote_qualify_fail_closed() -> None:
    from src.services.near_live_market_data import qualify_near_live_coverage

    qualification = qualify_near_live_coverage(
        surface="stock_evidence_quote",
        market="US",
        symbol="AAPL",
        observations=[
            {
                "market": "US",
                "symbol": "AAPL",
                "observationType": "quote",
                "value": 214.55,
                "asOf": "not-a-timestamp",
                "sourceClass": "near_live_market_data",
            }
        ],
        now=datetime(2026, 7, 6, 14, 32, tzinfo=timezone.utc),
    )

    assert qualification["coverageState"] == "rejected"
    assert qualification["usableState"] == "blocked"
    assert qualification["ready"] is False
    assert "quote_malformed_timestamp" in qualification["blockingReasons"]
    assert qualification["requiredEvidenceFamilies"] == ["quote"]
    assert qualification["availableEvidenceFamilies"] == []


def test_historical_technical_value_with_explicit_as_of_is_qualified() -> None:
    from src.services.near_live_market_data import qualify_near_live_coverage

    qualification = qualify_near_live_coverage(
        surface="stock_evidence_technical_data",
        market="US",
        symbol="AAPL",
        observations=[
            {
                "market": "US",
                "symbol": "AAPL",
                "observationType": "technical_indicator",
                "boundedPayloadRef": "stock_daily:AAPL:2026-07-10",
                "asOf": "2026-07-10T20:00:00Z",
                "receivedAt": "2026-07-10T20:05:00Z",
                "sourceClass": "local_historical_data",
                "sourceQuality": "usable",
            }
        ],
        now=datetime(2026, 7, 12, 16, 0, tzinfo=timezone.utc),
    )

    assert qualification["coverageState"] == "available"
    assert qualification["freshness"]["state"] == "fresh"
    assert qualification["usableState"] == "usable"
    assert qualification["ready"] is True


def test_structure_decision_prm_blocks_on_critical_near_live_gap() -> None:
    read_model = build_structure_decision_product_read_model(
        {
            "structureState": "rangeBound",
            "confidence": "high",
            "confidenceState": {"label": "high", "status": "ready", "reasons": []},
            "missingEvidence": [],
            "historicalOhlcvReadiness": {"overallState": "ready", "usableBars": 120},
            "dataQuality": {"status": "available", "usableBars": 120},
            "nearLiveCoverage": {
                "coverageState": "missing",
                "usableState": "blocked",
                "ready": False,
                "blockingReasons": ["quote_missing"],
            },
            "observationOnly": True,
            "decisionGrade": False,
        }
    )

    assert read_model["state"] == "no_evidence"
    assert read_model["ready"] is False
    assert read_model["classification"]["strongConclusionAllowed"] is False
    assert "near_live_market_data" in read_model["blockingChildren"]


def test_stock_evidence_prm_keeps_stale_value_readable_with_as_of_visible() -> None:
    read_model = build_stock_evidence_product_read_model(
        {
            "quote": {
                "status": "available",
                "freshness": "stale",
                "isStale": True,
                "asOf": "2026-07-06T14:00:00Z",
                "price": 214.55,
            },
            "technical": {"status": "missing"},
            "fundamental": {"status": "missing"},
            "news": {"status": "unknown", "isUnavailable": True},
            "nearLiveCoverage": {
                "coverageState": "stale",
                "usableState": "readable_stale",
                "ready": False,
                "freshness": {"state": "stale", "asOf": "2026-07-06T14:00:00Z"},
                "blockingReasons": ["quote_stale"],
            },
        }
    )

    assert read_model["state"] == "stale"
    assert read_model["ready"] is False
    assert read_model["freshness"]["asOf"] == "2026-07-06T14:00:00Z"
    assert read_model["evidence"]["preciseValuesMayBeReadableWhenStale"] is True
    assert read_model["nearLiveCoverage"]["usableState"] == "readable_stale"


def test_market_overview_partial_coverage_uses_bounded_provenance() -> None:
    from src.services.near_live_market_data import qualify_near_live_coverage

    qualification = qualify_near_live_coverage(
        surface="market_overview",
        market="US",
        symbol="MARKET",
        observations=[
            {
                "market": "US",
                "symbol": "SPY",
                "observationType": "index_data",
                "value": 550.12,
                "asOf": "2026-07-06T14:31:00Z",
                "sourceClass": "delayed_market_data",
                "sourceQuality": "delayed",
            }
        ],
        now=datetime(2026, 7, 6, 14, 32, tzinfo=timezone.utc),
    )

    assert qualification["coverageState"] == "partial"
    assert qualification["usableState"] == "usable"
    assert qualification["requiredEvidenceFamilies"] == ["index_data", "benchmark_data"]
    assert qualification["availableEvidenceFamilies"] == ["index_data"]
    assert qualification["provenance"]["sourceClass"] == "partial"
    assert "providerName" not in json.dumps(qualification)
    assert "rawPayload" not in json.dumps(qualification)


def test_uat_no_live_provider_mode_remains_blocked_for_external_dispatch() -> None:
    from src.services.uat_provider_isolation import check_uat_provider_dispatch

    dispatch = check_uat_provider_dispatch(
        provider="yfinance",
        capability="realtime_quote",
        route="DataFetcherManager.get_realtime_quote.us_direct_route",
        env={"WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS": "true"},
    )

    assert dispatch.allowed is False
    assert dispatch.reason_code == "uat_no_live_providers"


def test_default_dispatch_semantics_remain_allowed_with_fake_provider_adapter() -> None:
    from src.services.near_live_market_data import build_canonical_market_observation
    from src.services.uat_provider_isolation import check_uat_provider_dispatch

    dispatch = check_uat_provider_dispatch(
        provider="fake_adapter",
        capability="realtime_quote",
        route="unit_test",
        env={},
    )
    observation = build_canonical_market_observation(
        {
            "market": "US",
            "symbol": "AAPL",
            "observationType": "quote",
            "value": 214.55,
            "asOf": "2026-07-06T14:31:00Z",
            "sourceClass": "near_live_market_data",
            "sourceQuality": "reported",
        },
        surface="stock_evidence_quote",
        now=datetime(2026, 7, 6, 14, 32, tzinfo=timezone.utc),
    )

    assert dispatch.allowed is True
    assert dispatch.reason_code == "uat_no_live_providers_disabled"
    assert observation["usable"] is True
