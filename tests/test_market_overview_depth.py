# -*- coding: utf-8 -*-
"""Relevant market-depth contracts for Market Overview."""

from __future__ import annotations

import threading
from datetime import timedelta
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


class _FrameColumn:
    def __init__(self, values: list[float]) -> None:
        self._values = values

    def tolist(self) -> list[float]:
        return list(self._values)


class _HistoryFrame:
    def __init__(self, closes: list[float], volumes: list[float]) -> None:
        self.empty = False
        self._columns = {
            "Close": _FrameColumn(closes),
            "Volume": _FrameColumn(volumes),
        }

    def __getitem__(self, key: str) -> _FrameColumn:
        return self._columns[key]

    def __contains__(self, key: str) -> bool:
        return key in self._columns


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
    assert payload["providerHealth"]["provider"] == "yfinance_proxy"
    assert payload["providerHealth"]["status"] in {"live", "cache"}
    assert isinstance(payload["providerHealth"]["latencyMs"], int)
    assert payload["items"][0]["sourceLabel"] == "Yahoo Finance"


def test_us_breadth_unavailable_returns_compact_fallback_shape() -> None:
    service = MarketOverviewService()

    with patch.object(service, "_latest_quote", side_effect=RuntimeError("yfinance unavailable")):
        payload = service.get_us_breadth()

    assert payload["source"] == "unavailable"
    assert payload["freshness"] == "fallback"
    assert payload["isFallback"] is True
    assert payload["providerHealth"]["status"] == "unavailable"
    assert any(item["symbol"] == "SECTOR_PROXY_UNAVAILABLE" for item in payload["items"])
    assert "未接入" in payload["items"][0]["label"] or "暂不可用" in payload["items"][0]["label"]


def test_market_refresh_failure_serves_stale_snapshot_with_provider_health() -> None:
    service = MarketOverviewService()
    quotes = {
        "XLK": {"value": 220.0, "change_pct": 1.8, "trend": [216.0, 220.0], "volume": 10_000_000},
        "XLF": {"value": 44.0, "change_pct": -0.4, "trend": [44.2, 44.0], "volume": 8_000_000},
        "SPY": {"value": 520.0, "change_pct": 0.6, "trend": [516.0, 520.0], "volume": 60_000_000},
        "RSP": {"value": 168.0, "change_pct": 0.2, "trend": [167.0, 168.0], "volume": 4_000_000},
        "QQQ": {"value": 460.0, "change_pct": 1.1, "trend": [454.0, 460.0], "volume": 45_000_000},
        "IWM": {"value": 210.0, "change_pct": -0.3, "trend": [211.0, 210.0], "volume": 22_000_000},
    }

    with patch.object(service, "_latest_quote", side_effect=lambda ticker: quotes[ticker]):
        warm_payload = service.get_us_breadth()

    entry = market_cache.get("us_breadth")
    assert entry is not None
    entry.expires_at = entry.fetched_at - timedelta(seconds=1)

    with patch.object(service, "_latest_quote", side_effect=RuntimeError("provider_down raw stack trace")):
        stale_payload = service.get_us_breadth()
        market_cache.wait_for_refreshes(timeout=2)
        served_payload = service.get_us_breadth()

    assert stale_payload["items"][0]["symbol"] == warm_payload["items"][0]["symbol"]
    assert served_payload["items"][0]["symbol"] == warm_payload["items"][0]["symbol"]
    assert served_payload["isStale"] is True
    assert served_payload["providerHealth"]["status"] == "stale"
    assert served_payload["providerHealth"]["isStale"] is True
    assert served_payload["providerHealth"]["status"] != "live"
    assert served_payload["providerHealth"]["errorSummary"] == "数据源暂不可用"
    assert "provider_down" not in str(served_payload)
    assert "raw stack trace" not in str(served_payload)


def test_error_only_payload_does_not_overwrite_last_known_good_snapshot() -> None:
    service = MarketOverviewService()
    good_payload = {
        "source": "sina",
        "updatedAt": "2026-04-29T10:00:00+08:00",
        "asOf": "2026-04-29T10:00:00+08:00",
        "items": [{"symbol": "000001.SH", "label": "上证指数", "value": 3120.55, "source": "sina"}],
    }

    first = service._cached_payload("cn_indices", lambda: good_payload, service._fallback_cn_indices_snapshot)
    entry = market_cache.get("cn_indices")
    assert entry is not None
    entry.expires_at = entry.fetched_at - timedelta(seconds=1)

    stale = service._cached_payload(
        "cn_indices",
        lambda: {"source": "error", "error": "provider_error leaked raw exception", "items": []},
        service._fallback_cn_indices_snapshot,
    )
    market_cache.wait_for_refreshes(timeout=2)
    second = service._cached_payload(
        "cn_indices",
        lambda: {"source": "error", "error": "provider_error leaked raw exception", "items": []},
        service._fallback_cn_indices_snapshot,
    )

    assert first["items"][0]["value"] == 3120.55
    assert stale["items"][0]["value"] == 3120.55
    assert second["items"][0]["value"] == 3120.55
    assert MarketOverviewService._market_data_cache["cn_indices"]["items"][0]["value"] == 3120.55
    assert "provider_error leaked raw exception" not in str(second)


def test_partial_provider_health_is_preserved_for_mixed_cn_indices() -> None:
    service = MarketOverviewService()
    live_quote = {
        "000001.SH": {
            "symbol": "000001.SH",
            "name": "上证指数",
            "value": 3120.55,
            "change": 12.3,
            "changePercent": 0.39,
            "asOf": "2026-04-29T10:00:00+08:00",
        }
    }

    with patch.object(service, "_fetch_sina_cn_index_quotes", return_value=live_quote):
        payload = service.get_cn_indices()

    assert payload["source"] == "mixed"
    assert payload["fallbackUsed"] is True
    assert payload["providerHealth"]["status"] == "partial"
    assert payload["providerHealth"]["status"] != "live"
    assert payload["providerHealth"]["isFallback"] is False
    assert any(item["source"] == "sina" and item["isFallback"] is False for item in payload["items"])
    assert any(item["isFallback"] is True for item in payload["items"])


def test_market_us_breadth_endpoint_uses_market_service() -> None:
    service = Mock()
    service.get_us_breadth.return_value = {"source": "yfinance_proxy", "items": [{"symbol": "SECTORS_UP"}]}

    with patch("api.v1.endpoints.market.MarketOverviewService", return_value=service):
        payload = market.get_us_breadth()

    assert payload["items"][0]["symbol"] == "SECTORS_UP"
    service.get_us_breadth.assert_called_once()


def test_latest_quote_service_shapes_yfinance_transport_history_frame() -> None:
    service = MarketOverviewService()
    frame = _HistoryFrame(
        closes=[510.0, 515.5, 520.25],
        volumes=[1000000.0, 1200000.0, 1400000.0],
    )

    with patch("src.services.market_overview_service.fetch_yfinance_quote_history_frame", return_value=frame) as mock_fetch:
        quote = service._latest_quote("SPY")

    mock_fetch.assert_called_once_with("SPY")
    assert quote == {
        "value": 520.25,
        "change_pct": 0.921,
        "trend": [510.0, 515.5, 520.25],
        "volume": 1400000.0,
    }


def test_crypto_snapshot_includes_sol_and_funding_when_binance_public_data_available() -> None:
    service = MarketOverviewService()

    ticker_rows = [
        {"symbol": "BTCUSDT", "lastPrice": "70000", "priceChangePercent": "1.2", "quoteVolume": "2200000000", "highPrice": "71000", "lowPrice": "69000"},
        {"symbol": "ETHUSDT", "lastPrice": "3500", "priceChangePercent": "0.4", "quoteVolume": "1200000000", "highPrice": "3550", "lowPrice": "3400"},
        {"symbol": "SOLUSDT", "lastPrice": "155", "priceChangePercent": "2.4", "quoteVolume": "700000000", "highPrice": "160", "lowPrice": "150"},
        {"symbol": "BNBUSDT", "lastPrice": "610", "priceChangePercent": "-0.2", "quoteVolume": "320000000", "highPrice": "618", "lowPrice": "604"},
    ]
    funding_rows = {
        "BTCUSDT": {"lastFundingRate": "0.00012", "nextFundingTime": 1770000000000},
        "ETHUSDT": {"lastFundingRate": "0.00008", "nextFundingTime": 1770000000000},
        "SOLUSDT": {"lastFundingRate": "-0.00005", "nextFundingTime": 1770000000000},
        "BNBUSDT": {"lastFundingRate": "0.00003", "nextFundingTime": 1770000000000},
    }

    with (
        patch("src.services.market_overview_service.fetch_binance_ticker_snapshot", return_value=ticker_rows),
        patch("src.services.market_overview_service.fetch_binance_funding_row", side_effect=lambda symbol: funding_rows[symbol]),
        patch.object(service, "_fetch_binance_kline_history", return_value=[69000, 70000]),
    ):
        payload = service._fetch_crypto_market_snapshot()

    symbols = {item["symbol"] for item in payload["items"]}
    assert {"BTC", "ETH", "SOL", "BNB", "BTC_FUNDING", "ETH_FUNDING", "SOL_FUNDING", "BNB_FUNDING"} <= symbols
    assert payload["source"] == "binance"
    assert payload["items"][0]["source"] == "binance"
    assert any("Quote volume" in detail for item in payload["items"] for detail in item.get("hover_details", []))


def test_crypto_snapshot_fetches_kline_histories_with_bounded_parallelism() -> None:
    service = MarketOverviewService()
    ticker_rows = [
        {"symbol": "BTCUSDT", "lastPrice": "70000", "priceChangePercent": "1.2", "quoteVolume": "2200000000", "highPrice": "71000", "lowPrice": "69000"},
        {"symbol": "ETHUSDT", "lastPrice": "3500", "priceChangePercent": "0.4", "quoteVolume": "1200000000", "highPrice": "3550", "lowPrice": "3400"},
        {"symbol": "SOLUSDT", "lastPrice": "155", "priceChangePercent": "2.4", "quoteVolume": "700000000", "highPrice": "160", "lowPrice": "150"},
        {"symbol": "BNBUSDT", "lastPrice": "610", "priceChangePercent": "-0.2", "quoteVolume": "320000000", "highPrice": "618", "lowPrice": "604"},
    ]
    barrier = threading.Barrier(4)
    seen: list[str] = []

    def fetch_history(symbol: str) -> list[float]:
        seen.append(symbol)
        barrier.wait(timeout=0.5)
        return [100.0, 101.0]

    with (
        patch("src.services.market_overview_service.fetch_binance_ticker_snapshot", return_value=ticker_rows),
        patch.object(service, "_fetch_binance_kline_history", side_effect=fetch_history),
        patch.object(service, "_fetch_binance_funding_items", return_value=[]),
    ):
        payload = service._fetch_crypto_market_snapshot()

    assert set(seen) == {"BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"}
    assert {"BTC", "ETH", "SOL", "BNB"} <= {item["symbol"] for item in payload["items"]}
    assert payload["source"] == "binance"


def test_crypto_funding_fetches_with_bounded_parallelism_and_keeps_item_shape() -> None:
    service = MarketOverviewService()
    labels = {
        "BTCUSDT": ("BTC", "Bitcoin"),
        "ETHUSDT": ("ETH", "Ethereum"),
        "SOLUSDT": ("SOL", "Solana"),
        "BNBUSDT": ("BNB", "BNB"),
    }
    rates = {"BTCUSDT": "0.00012", "ETHUSDT": "0.00008", "SOLUSDT": "-0.00005", "BNBUSDT": "0.00003"}
    barrier = threading.Barrier(4)
    seen: list[str] = []

    def get_funding(symbol: str) -> dict[str, str]:
        seen.append(symbol)
        barrier.wait(timeout=0.5)
        return {"lastFundingRate": rates[symbol]}

    with patch("src.services.market_overview_service.fetch_binance_funding_row", side_effect=get_funding):
        items = service._fetch_binance_funding_items(labels, "2026-04-29T10:00:00+08:00")

    assert set(seen) == set(labels)
    assert {item["symbol"] for item in items} == {"BTC_FUNDING", "ETH_FUNDING", "SOL_FUNDING", "BNB_FUNDING"}
    assert all(item["source"] == "binance" for item in items)
    assert all(item["unit"] == "%" for item in items)


def test_crypto_funding_partial_failure_keeps_successes_item_level() -> None:
    service = MarketOverviewService()
    labels = {
        "BTCUSDT": ("BTC", "Bitcoin"),
        "ETHUSDT": ("ETH", "Ethereum"),
        "SOLUSDT": ("SOL", "Solana"),
        "BNBUSDT": ("BNB", "BNB"),
    }

    def get_funding(symbol: str) -> dict[str, str]:
        if symbol == "SOLUSDT":
            raise RuntimeError("funding unavailable")
        return {"lastFundingRate": "0.0001"}

    with patch("src.services.market_overview_service.fetch_binance_funding_row", side_effect=get_funding):
        items = service._fetch_binance_funding_items(labels, "2026-04-29T10:00:00+08:00")

    assert {item["symbol"] for item in items} == {"BTC_FUNDING", "ETH_FUNDING", "BNB_FUNDING"}
    assert "SOL_FUNDING" not in {item["symbol"] for item in items}
    assert all(item["source"] == "binance" for item in items)


def test_crypto_snapshot_marks_missing_funding_as_temporarily_unavailable() -> None:
    service = MarketOverviewService()

    ticker_rows = [
        {"symbol": "BTCUSDT", "lastPrice": "70000", "priceChangePercent": "1.2", "quoteVolume": "2200000000", "highPrice": "71000", "lowPrice": "69000"},
        {"symbol": "ETHUSDT", "lastPrice": "3500", "priceChangePercent": "0.4", "quoteVolume": "1200000000", "highPrice": "3550", "lowPrice": "3400"},
        {"symbol": "SOLUSDT", "lastPrice": "155", "priceChangePercent": "2.4", "quoteVolume": "700000000", "highPrice": "160", "lowPrice": "150"},
        {"symbol": "BNBUSDT", "lastPrice": "610", "priceChangePercent": "-0.2", "quoteVolume": "320000000", "highPrice": "618", "lowPrice": "604"},
    ]

    with (
        patch("src.services.market_overview_service.fetch_binance_ticker_snapshot", return_value=ticker_rows),
        patch("src.services.market_overview_service.fetch_binance_funding_row", side_effect=RuntimeError("funding unavailable")),
        patch.object(service, "_fetch_binance_kline_history", return_value=[69000, 70000]),
    ):
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
