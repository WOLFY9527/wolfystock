# -*- coding: utf-8 -*-
"""Focused contracts for cross-asset driver readiness."""

from __future__ import annotations

import json

from src.services.cross_asset_driver_readiness import (
    CROSS_ASSET_DRIVER_READINESS_CONTRACT_VERSION,
    build_cross_asset_driver_readiness,
)


EXPECTED_DRIVER_CATEGORIES = {
    "equities_index",
    "rates",
    "usd",
    "oil_energy",
    "gold",
    "volatility",
    "credit",
    "crypto",
    "sectors",
}
EXPECTED_STATES = {
    "available",
    "missing",
    "stale",
    "insufficient_history",
    "not_configured",
}
FORBIDDEN_FRAGMENTS = {
    "risk-on",
    "risk off",
    "risk-off",
    "liquidity",
    "inflation",
    "recession",
    "buy",
    "sell",
    "hold",
    "recommend",
    "target price",
    "stop loss",
    "position sizing",
    "providerclass",
    "providername",
    "providerattempted",
    "requestid",
    "traceid",
    "cachekey",
    "rawpayload",
    "token",
    "secret",
    "credential",
    "env",
}


def _symbol(
    symbol: str,
    *,
    data_state: str,
    cached_bars: int,
    required_bars: int = 60,
    latest_bar_date: str | None = "2026-06-25",
    freshness_state: str = "fresh",
) -> dict:
    return {
        "symbol": symbol,
        "dataState": data_state,
        "cacheState": "cache_hit" if cached_bars else "cache_missing",
        "cachedBars": cached_bars,
        "latestBarDate": latest_bar_date,
        "freshnessState": freshness_state,
        "requiredBars": required_bars,
    }


def test_cross_asset_driver_readiness_separates_all_driver_categories() -> None:
    payload = build_cross_asset_driver_readiness().to_dict()

    assert payload["contractVersion"] == CROSS_ASSET_DRIVER_READINESS_CONTRACT_VERSION
    assert payload["consumerSafe"] is True
    assert payload["diagnosticOnly"] is True
    assert payload["networkCallsEnabled"] is False
    assert payload["externalProviderCalls"] is False
    assert payload["mutationEnabled"] is False
    assert EXPECTED_DRIVER_CATEGORIES == {item["category"] for item in payload["drivers"]}
    assert EXPECTED_STATES <= set(payload["supportedStates"])

    drivers = {item["category"]: item for item in payload["drivers"]}
    assert drivers["equities_index"]["configuredIdentifiers"] == [
        {"kind": "symbol", "value": "SPY", "market": "us"},
        {"kind": "symbol", "value": "QQQ", "market": "us"},
        {"kind": "symbol", "value": "IWM", "market": "us"},
    ]
    assert drivers["rates"]["configuredIdentifiers"] == [
        {"kind": "series", "value": "DGS2", "market": "us"},
        {"kind": "series", "value": "DGS10", "market": "us"},
        {"kind": "series", "value": "DGS30", "market": "us"},
        {"kind": "series", "value": "T10Y2Y", "market": "us"},
        {"kind": "series", "value": "T10Y3M", "market": "us"},
    ]
    assert drivers["credit"]["state"] == "not_configured"
    assert drivers["credit"]["configuredIdentifiers"] == []


def test_cross_asset_driver_readiness_projects_cached_ohlcv_states() -> None:
    payload = build_cross_asset_driver_readiness(
        historical_ohlcv_cache_preflight={
            "markets": {
                "us": {
                    "symbols": [
                        _symbol("SPY", data_state="fresh", cached_bars=90),
                        _symbol("QQQ", data_state="fresh", cached_bars=72),
                        _symbol("IWM", data_state="stale", cached_bars=82, freshness_state="stale"),
                        _symbol("USO", data_state="insufficient", cached_bars=12),
                        _symbol("GLD", data_state="cache_missing", cached_bars=0, latest_bar_date=None),
                        _symbol("BTC-USD", data_state="cache_missing", cached_bars=0, latest_bar_date=None),
                        _symbol("XLK", data_state="fresh", cached_bars=60),
                        _symbol("XLF", data_state="fresh", cached_bars=61),
                    ]
                }
            }
        }
    ).to_dict()
    drivers = {item["category"]: item for item in payload["drivers"]}

    assert drivers["equities_index"]["state"] == "stale"
    assert drivers["equities_index"]["cachedOhlcv"] == {
        "requiredBars": 60,
        "usableBars": 72,
        "missingBars": 0,
        "cacheState": "cache_hit",
        "freshnessState": "stale",
        "latestBarDate": "2026-06-25",
    }
    assert drivers["oil_energy"]["state"] == "insufficient_history"
    assert drivers["oil_energy"]["cachedOhlcv"]["usableBars"] == 12
    assert drivers["oil_energy"]["cachedOhlcv"]["missingBars"] == 48
    assert drivers["gold"]["state"] == "missing"
    assert drivers["crypto"]["state"] == "missing"
    assert drivers["sectors"]["state"] == "available"


def test_cross_asset_driver_readiness_redacts_internals_and_makes_no_fake_conclusions() -> None:
    payload = build_cross_asset_driver_readiness(
        historical_ohlcv_cache_preflight={
            "providerName": "unsafe-provider",
            "cacheKey": "unsafe-cache-key",
            "markets": {
                "us": {
                    "symbols": [
                        {
                            **_symbol("SPY", data_state="fresh", cached_bars=90),
                            "rawPayload": {"secret": "hidden"},
                        }
                    ]
                }
            },
        }
    ).to_dict()
    serialized = json.dumps(payload, ensure_ascii=False).lower()

    for fragment in FORBIDDEN_FRAGMENTS:
        assert fragment not in serialized
    assert payload["consumerSummary"] == (
        "Cross-asset drivers are reported as data-readiness inputs only; no market conclusion is inferred."
    )
