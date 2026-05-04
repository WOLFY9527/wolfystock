# -*- coding: utf-8 -*-
"""Relevant market-depth contracts for Market Overview."""

from __future__ import annotations

from unittest.mock import Mock, patch

from api.v1.endpoints import market
from src.services.market_cache import market_cache
from src.services.market_overview_service import MarketOverviewService


def setup_function() -> None:
    market_cache.clear()
    MarketOverviewService._market_data_cache.clear()


def teardown_function() -> None:
    market_cache.clear()
    MarketOverviewService._market_data_cache.clear()


def test_us_breadth_sector_proxy_returns_stable_shape_with_metadata() -> None:
    service = MarketOverviewService()
    quotes = {
        "XLK": {"value": 220.0, "change_pct": 1.8, "trend": [216.0, 220.0], "volume": 10_000_000},
        "XLF": {"value": 44.0, "change_pct": -0.4, "trend": [44.2, 44.0], "volume": 8_000_000},
        "XLV": {"value": 146.0, "change_pct": 0.7, "trend": [144.8, 146.0], "volume": 7_000_000},
        "SPY": {"value": 520.0, "change_pct": 0.6, "trend": [516.0, 520.0], "volume": 60_000_000},
        "RSP": {"value": 168.0, "change_pct": 0.2, "trend": [167.0, 168.0], "volume": 4_000_000},
        "QQQ": {"value": 460.0, "change_pct": 1.1, "trend": [454.0, 460.0], "volume": 45_000_000},
        "IWM": {"value": 210.0, "change_pct": -0.3, "trend": [211.0, 210.0], "volume": 22_000_000},
    }

    with patch.object(service, "_latest_quote", side_effect=lambda ticker: quotes[ticker]):
        payload = service.get_us_breadth()

    symbols = {item["symbol"] for item in payload["items"]}
    assert {"SECTORS_UP", "SECTORS_DOWN", "STRONGEST_SECTOR", "WEAKEST_SECTOR", "RSP_SPY", "IWM_SPY", "QQQ_SPY"} <= symbols
    assert payload["source"] == "yfinance_proxy"
    assert payload["sourceLabel"] == "Yahoo Finance"
    assert payload["freshness"] in {"live", "delayed", "cached", "stale"}
    assert payload["isFallback"] is False
    assert payload["items"][0]["sourceLabel"] == "Yahoo Finance"


def test_us_breadth_unavailable_returns_compact_fallback_shape() -> None:
    service = MarketOverviewService()

    with patch.object(service, "_latest_quote", side_effect=RuntimeError("yfinance unavailable")):
        payload = service.get_us_breadth()

    assert payload["source"] == "unavailable"
    assert payload["freshness"] == "fallback"
    assert payload["isFallback"] is True
    assert any(item["symbol"] == "SECTOR_PROXY_UNAVAILABLE" for item in payload["items"])
    assert "未接入" in payload["items"][0]["label"] or "暂不可用" in payload["items"][0]["label"]


def test_market_us_breadth_endpoint_uses_market_service() -> None:
    service = Mock()
    service.get_us_breadth.return_value = {"source": "yfinance_proxy", "items": [{"symbol": "SECTORS_UP"}]}

    with patch("api.v1.endpoints.market.MarketOverviewService", return_value=service):
        payload = market.get_us_breadth()

    assert payload["items"][0]["symbol"] == "SECTORS_UP"
    service.get_us_breadth.assert_called_once()


def test_crypto_snapshot_includes_sol_and_funding_when_binance_public_data_available() -> None:
    service = MarketOverviewService()

    ticker_rows = [
        {"symbol": "BTCUSDT", "lastPrice": "70000", "priceChangePercent": "1.2", "quoteVolume": "2200000000", "highPrice": "71000", "lowPrice": "69000"},
        {"symbol": "ETHUSDT", "lastPrice": "3500", "priceChangePercent": "0.4", "quoteVolume": "1200000000", "highPrice": "3550", "lowPrice": "3400"},
        {"symbol": "SOLUSDT", "lastPrice": "155", "priceChangePercent": "2.4", "quoteVolume": "700000000", "highPrice": "160", "lowPrice": "150"},
        {"symbol": "BNBUSDT", "lastPrice": "610", "priceChangePercent": "-0.2", "quoteVolume": "320000000", "highPrice": "618", "lowPrice": "604"},
    ]

    with (
        patch("src.services.market_overview_service.requests.get") as get,
        patch.object(service, "_fetch_binance_kline_history", return_value=[69000, 70000]),
    ):
        get.return_value.raise_for_status.return_value = None
        get.return_value.json.side_effect = [
            ticker_rows,
            {"lastFundingRate": "0.00012", "nextFundingTime": 1770000000000},
            {"lastFundingRate": "0.00008", "nextFundingTime": 1770000000000},
            {"lastFundingRate": "-0.00005", "nextFundingTime": 1770000000000},
            {"lastFundingRate": "0.00003", "nextFundingTime": 1770000000000},
        ]

        payload = service._fetch_crypto_market_snapshot()

    symbols = {item["symbol"] for item in payload["items"]}
    assert {"BTC", "ETH", "SOL", "BNB", "BTC_FUNDING", "ETH_FUNDING", "SOL_FUNDING", "BNB_FUNDING"} <= symbols
    assert payload["source"] == "binance"
    assert payload["items"][0]["source"] == "binance"
    assert any("Quote volume" in detail for item in payload["items"] for detail in item.get("hover_details", []))


def test_crypto_snapshot_marks_missing_funding_as_temporarily_unavailable() -> None:
    service = MarketOverviewService()

    ticker_rows = [
        {"symbol": "BTCUSDT", "lastPrice": "70000", "priceChangePercent": "1.2", "quoteVolume": "2200000000", "highPrice": "71000", "lowPrice": "69000"},
        {"symbol": "ETHUSDT", "lastPrice": "3500", "priceChangePercent": "0.4", "quoteVolume": "1200000000", "highPrice": "3550", "lowPrice": "3400"},
        {"symbol": "SOLUSDT", "lastPrice": "155", "priceChangePercent": "2.4", "quoteVolume": "700000000", "highPrice": "160", "lowPrice": "150"},
        {"symbol": "BNBUSDT", "lastPrice": "610", "priceChangePercent": "-0.2", "quoteVolume": "320000000", "highPrice": "618", "lowPrice": "604"},
    ]

    with (
        patch("src.services.market_overview_service.requests.get") as get,
        patch.object(service, "_fetch_binance_kline_history", return_value=[69000, 70000]),
    ):
        get.return_value.raise_for_status.side_effect = [None, RuntimeError("funding unavailable")]
        get.return_value.json.return_value = ticker_rows

        payload = service._fetch_crypto_market_snapshot()

    funding_items = [item for item in payload["items"] if str(item["symbol"]).endswith("_FUNDING")]
    assert {item["symbol"] for item in funding_items} == {"BTC_FUNDING", "ETH_FUNDING", "SOL_FUNDING", "BNB_FUNDING"}
    assert all(item["source"] == "unavailable" for item in funding_items)
    assert all(item["freshness"] == "fallback" for item in funding_items)


def test_crypto_depth_fallback_marks_liquidity_and_dominance_unavailable() -> None:
    payload = MarketOverviewService()._fallback_crypto_market_snapshot()

    symbols = {item["symbol"] for item in payload["items"]}
    assert {
        "BTC",
        "ETH",
        "SOL",
        "BNB",
        "BTC_FUNDING",
        "ETH_FUNDING",
        "SOL_FUNDING",
        "BNB_FUNDING",
        "STABLECOIN_LIQUIDITY",
        "BTC_DOMINANCE",
    } <= symbols
    unavailable = [
        item
        for item in payload["items"]
        if item["symbol"] in {
            "BTC_FUNDING",
            "ETH_FUNDING",
            "SOL_FUNDING",
            "BNB_FUNDING",
            "STABLECOIN_LIQUIDITY",
            "BTC_DOMINANCE",
        }
    ]
    assert all(item["source"] == "unavailable" for item in unavailable)
    assert all(item["freshness"] == "fallback" for item in unavailable)
