# -*- coding: utf-8 -*-
"""Relevant market-depth contracts for Market Overview."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from api.v1.endpoints import market
from src.services.market_cache import market_cache
from src.services.market_data_source_registry import project_source_provenance
from src.services.market_overview_service import MarketOverviewService
from src.services.official_macro_transport import MacroObservation

EXPECTED_PROVIDER_HEALTH_FIELDS = {
    "provider",
    "status",
    "asOf",
    "updatedAt",
    "latencyMs",
    "errorSummary",
    "isFallback",
    "isStale",
    "isRefreshing",
    "sourceLabel",
    "card",
}


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


def _missing_us_breadth_activation() -> dict[str, object]:
    return {
        "credentialsPresent": False,
        "providerConstructed": False,
        "probePassed": False,
        "freshnessValid": False,
        "sourceMetadataValid": True,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "broadMarketClaimAllowed": False,
        "fulfilledMetrics": [],
        "missingMetrics": [
            "ADVANCERS",
            "DECLINERS",
            "UNCHANGED",
            "ADVANCE_DECLINE_RATIO",
            "NEW_HIGHS",
            "NEW_LOWS",
            "HIGH_LOW_RATIO",
        ],
        "staleMetrics": [],
        "reasonCodes": ["authorized_us_market_breadth_feed_not_configured"],
    }


def _configured_unavailable_us_breadth_activation(reason: str) -> dict[str, object]:
    payload = _missing_us_breadth_activation()
    payload.update(
        {
            "credentialsPresent": True,
            "providerConstructed": True,
            "reasonCodes": [reason],
        }
    )
    return payload


def _fresh_official_macro_dates() -> tuple[str, str]:
    latest = datetime.now(ZoneInfo("America/New_York")).date()
    while latest.weekday() >= 5:
        latest -= timedelta(days=1)
    previous = latest - timedelta(days=1)
    while previous.weekday() >= 5:
        previous -= timedelta(days=1)
    return latest.isoformat(), previous.isoformat()


def test_us_breadth_sector_proxy_returns_stable_shape_with_metadata() -> None:
    service = MarketOverviewService()
    observed_at = datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds")
    quotes = {
        "XLK": {"value": 220.0, "change_pct": 1.8, "trend": [216.0, 220.0], "volume": 10_000_000},
        "XLF": {"value": 44.0, "change_pct": -0.4, "trend": [44.2, 44.0], "volume": 8_000_000},
        "XLV": {"value": 146.0, "change_pct": 0.7, "trend": [144.8, 146.0], "volume": 7_000_000},
        "SPY": {"value": 520.0, "change_pct": 0.6, "trend": [516.0, 520.0], "volume": 60_000_000},
        "RSP": {"value": 168.0, "change_pct": 0.2, "trend": [167.0, 168.0], "volume": 4_000_000},
        "QQQ": {"value": 460.0, "change_pct": 1.1, "trend": [454.0, 460.0], "volume": 45_000_000},
        "IWM": {"value": 210.0, "change_pct": -0.3, "trend": [211.0, 210.0], "volume": 22_000_000},
    }
    quotes = {symbol: {**quote, "asOf": observed_at} for symbol, quote in quotes.items()}

    with (
        patch("src.services.market_overview_service.run_polygon_us_breadth_activation", return_value=_missing_us_breadth_activation()),
        patch.object(service, "_latest_quote", side_effect=lambda ticker: quotes[ticker]),
    ):
        payload = service.get_us_breadth()

    symbols = {item["symbol"] for item in payload["items"]}
    assert {"SECTORS_UP", "SECTORS_DOWN", "STRONGEST_SECTOR", "WEAKEST_SECTOR", "RSP_SPY", "IWM_SPY", "QQQ_SPY"} <= symbols
    assert payload["source"] == "yfinance_proxy"
    assert payload["sourceLabel"] == "Yahoo Finance"
    assert payload["freshness"] in {"live", "delayed", "cached", "stale"}
    assert payload["isFallback"] is False
    assert set(payload["providerHealth"]) == EXPECTED_PROVIDER_HEALTH_FIELDS
    assert payload["providerHealth"]["provider"] == "yfinance_proxy"
    assert payload["providerHealth"]["status"] in {"live", "cache"}
    assert isinstance(payload["providerHealth"]["latencyMs"], int)
    assert payload["providerHealth"]["sourceLabel"] == "Yahoo Finance"
    assert payload["providerHealth"]["card"] == "us_breadth"
    assert payload["items"][0]["sourceLabel"] == "Yahoo Finance"
    assert payload["items"][0]["sourceType"] == "unofficial_proxy"


def test_rates_panel_keeps_static_cn_fallback_rows_non_authoritative_when_us_official_rows_are_mixed() -> None:
    service = MarketOverviewService()
    latest, previous = _fresh_official_macro_dates()
    official_points = {
        "DGS2": [
            MacroObservation("DGS2", 4.82, latest, latest, "treasury:daily_treasury_yield_curve", "official_public", "daily_rate"),
            MacroObservation("DGS2", 4.79, previous, previous, "treasury:daily_treasury_yield_curve", "official_public", "daily_rate"),
        ],
        "DGS10": [
            MacroObservation("DGS10", 4.41, latest, latest, "treasury:daily_treasury_yield_curve", "official_public", "daily_rate"),
            MacroObservation("DGS10", 4.36, previous, previous, "treasury:daily_treasury_yield_curve", "official_public", "daily_rate"),
        ],
    }

    with (
        patch.object(service, "_cached_payload", side_effect=lambda _key, fetcher, _fallback: fetcher()),
        patch.object(service, "_official_macro_points", return_value=official_points),
        patch("src.services.market_overview_service.ExecutionLogService") as log_service,
    ):
        log_service.return_value.record_market_overview_fetch.return_value = "log-rates"
        payload = service.get_rates()

    assert payload["source"] == "mixed"
    assert payload["fallbackUsed"] is True
    items = {item["symbol"]: item for item in payload["items"]}
    assert items["US10Y"]["sourceType"] == "official_public"
    for symbol in ("CN10Y", "DR007", "SHIBOR", "LPR"):
        item = items[symbol]
        assert item["source"] == "fallback"
        assert item["isFallback"] is True
        assert item.get("sourceAuthorityAllowed") is not True
        assert item.get("scoreContributionAllowed") is not True
        provenance = project_source_provenance(
            source=item.get("source"),
            source_type=item.get("sourceType"),
            freshness=item.get("freshness"),
            is_fallback=bool(item.get("isFallback") or item.get("fallbackUsed")),
        )
        assert provenance["sourceType"] == "fallback_static"


def test_us_breadth_unavailable_returns_compact_unavailable_shape() -> None:
    service = MarketOverviewService()

    with (
        patch("src.services.market_overview_service.run_polygon_us_breadth_activation", return_value=_missing_us_breadth_activation()),
        patch.object(service, "_latest_quote", side_effect=RuntimeError("yfinance unavailable")),
    ):
        payload = service.get_us_breadth()

    assert payload["source"] == "unavailable"
    assert payload["sourceType"] == "missing"
    assert payload["freshness"] == "unavailable"
    assert payload["breadthClaimType"] == "missing_unavailable_breadth"
    assert payload["isFallback"] is True
    assert payload["fallbackUsed"] is True
    assert payload["sourceAuthorityAllowed"] is False
    assert payload["scoreContributionAllowed"] is False
    assert payload["broadMarketClaimAllowed"] is False
    assert payload["sourceAuthorityReason"] == "authorized_us_market_breadth_feed_not_configured"
    assert payload["routeRejectedReasonCodes"] == ["authorized_us_market_breadth_feed_not_configured"]
    assert payload["providerHealth"]["status"] == "unavailable"
    assert payload["authorityDiagnostics"]["reason"] == "authorized_us_market_breadth_feed_not_configured"
    assert payload["authorityDiagnostics"]["missingMetrics"] == [
        "ADVANCERS",
        "DECLINERS",
        "UNCHANGED",
        "ADVANCE_DECLINE_RATIO",
        "NEW_HIGHS",
        "NEW_LOWS",
        "HIGH_LOW_RATIO",
    ]
    assert [item["symbol"] for item in payload["items"]] == [
        "US_BREADTH_UNAVAILABLE",
        "ADVANCE_DECLINE_UNAVAILABLE",
        "HIGH_LOW_UNAVAILABLE",
    ]
    assert all(item["scoreContributionAllowed"] is False for item in payload["items"])
    assert all(item["broadMarketClaimAllowed"] is False for item in payload["items"])
    assert payload["items"][0]["label"] == "US breadth missing/unavailable"
    assert payload["items"][0]["sourceLabel"] == "未接入"


def test_us_breadth_configured_polygon_unavailable_preserves_provider_reason() -> None:
    service = MarketOverviewService()

    with (
        patch(
            "src.services.market_overview_service.run_polygon_us_breadth_activation",
            return_value=_configured_unavailable_us_breadth_activation("polygon_unauthorized"),
        ),
        patch.object(service, "_latest_quote", side_effect=RuntimeError("yfinance unavailable")),
        patch.object(service, "_load_persistent_snapshot", return_value=None),
    ):
        payload = service.get_us_breadth()

    assert payload["source"] == "unavailable"
    assert payload["freshness"] == "unavailable"
    assert payload["sourceAuthorityAllowed"] is False
    assert payload["scoreContributionAllowed"] is False
    assert payload["authorityDiagnostics"]["reason"] == "polygon_unauthorized"
    assert payload["sourceAuthorityReason"] == "polygon_unauthorized"
    assert payload["degradationReason"] == "polygon_unauthorized"
    assert payload["routeRejectedReasonCodes"] == ["polygon_unauthorized"]
    assert payload["asOf"] is None


def test_us_funds_flow_quote_proxy_is_labeled_as_proxy_and_non_authoritative() -> None:
    service = MarketOverviewService()
    quotes = {
        "SPY": {"value": 520.0, "change_pct": 0.6, "trend": [516.0, 520.0], "volume": 60_000_000},
        "QQQ": {"value": 460.0, "change_pct": 1.1, "trend": [454.0, 460.0], "volume": 45_000_000},
        "IWM": {"value": 210.0, "change_pct": -0.3, "trend": [211.0, 210.0], "volume": 22_000_000},
    }

    with patch.object(service, "_latest_quote", side_effect=lambda ticker: quotes[ticker]):
        payload = service.get_funds_flow()

    items = {item["symbol"]: item for item in payload["items"]}

    assert payload["source"] == "yfinance_proxy"
    assert payload["sourceType"] == "unofficial_public_api"
    assert payload["observationOnly"] is True
    assert payload["sourceAuthorityAllowed"] is False
    assert payload["scoreContributionAllowed"] is False
    assert items["ETF"]["label"] == "ETF flow proxy"
    assert items["INSTITUTIONAL"]["label"] == "Institutional pressure proxy"
    assert items["INDUSTRY"]["label"] == "Industry breadth proxy"
    assert items["ETF"]["source"] == "yfinance_proxy"
    assert items["ETF"]["observationOnly"] is True
    assert items["ETF"]["sourceAuthorityAllowed"] is False
    assert items["ETF"]["scoreContributionAllowed"] is False


def test_market_refresh_failure_serves_stale_snapshot_with_provider_health() -> None:
    service = MarketOverviewService()
    observed_at = datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds")
    quotes = {
        "XLK": {"value": 220.0, "change_pct": 1.8, "trend": [216.0, 220.0], "volume": 10_000_000},
        "XLF": {"value": 44.0, "change_pct": -0.4, "trend": [44.2, 44.0], "volume": 8_000_000},
        "SPY": {"value": 520.0, "change_pct": 0.6, "trend": [516.0, 520.0], "volume": 60_000_000},
        "RSP": {"value": 168.0, "change_pct": 0.2, "trend": [167.0, 168.0], "volume": 4_000_000},
        "QQQ": {"value": 460.0, "change_pct": 1.1, "trend": [454.0, 460.0], "volume": 45_000_000},
        "IWM": {"value": 210.0, "change_pct": -0.3, "trend": [211.0, 210.0], "volume": 22_000_000},
    }
    quotes = {symbol: {**quote, "asOf": observed_at} for symbol, quote in quotes.items()}

    with (
        patch("src.services.market_overview_service.run_polygon_us_breadth_activation", return_value=_missing_us_breadth_activation()),
        patch.object(service, "_latest_quote", side_effect=lambda ticker: quotes[ticker]),
    ):
        warm_payload = service.get_us_breadth()

    entry = market_cache.get("us_breadth")
    assert entry is not None
    entry.expires_at = entry.fetched_at - timedelta(seconds=1)

    with (
        patch("src.services.market_overview_service.run_polygon_us_breadth_activation", return_value=_missing_us_breadth_activation()),
        patch.object(service, "_latest_quote", side_effect=RuntimeError("provider_down raw stack trace")),
    ):
        stale_payload = service.get_us_breadth()
        assert market_cache.wait_for_refreshes(timeout=2) is True
        served_payload = service.get_us_breadth()

    assert stale_payload["items"][0]["symbol"] == warm_payload["items"][0]["symbol"]
    assert served_payload["items"][0]["symbol"] == warm_payload["items"][0]["symbol"]
    assert served_payload["isStale"] is True
    assert set(served_payload["providerHealth"]) == EXPECTED_PROVIDER_HEALTH_FIELDS
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
    assert payload["sourceLabel"] == "多来源"
    assert payload["fallbackUsed"] is True
    assert payload["isFallback"] is False
    assert payload["providerHealth"]["status"] == "partial"
    assert payload["providerHealth"]["status"] != "live"
    assert payload["providerHealth"]["isFallback"] is False
    assert payload["providerHealth"]["sourceLabel"] == "多来源"
    live_item = next(item for item in payload["items"] if item["source"] == "sina")
    fallback_item = next(item for item in payload["items"] if item["isFallback"] is True)
    assert live_item["isFallback"] is False
    assert live_item["sourceLabel"] == "新浪财经"
    assert live_item["sourceType"] == "public_api"
    assert fallback_item["source"] == "fallback"
    assert fallback_item["sourceLabel"] == "备用数据"
    assert fallback_item["sourceType"] == "public_api"


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


def test_us_breadth_reuses_shared_yfinance_quotes_within_public_request() -> None:
    service = MarketOverviewService()
    calls: dict[str, int] = {}

    def fake_history_frame(ticker: str) -> _HistoryFrame:
        calls[ticker] = calls.get(ticker, 0) + 1
        base = float(100 + len(calls) * 10)
        return _HistoryFrame(
            closes=[base, base + 1.0, base + 2.0],
            volumes=[1_000_000.0, 1_100_000.0, 1_200_000.0],
        )

    with (
        patch("src.services.market_overview_service.run_polygon_us_breadth_activation", return_value=_missing_us_breadth_activation()),
        patch("src.services.market_overview_service.fetch_yfinance_quote_history_frame", side_effect=fake_history_frame),
        patch("src.services.market_overview_service.ExecutionLogService") as log_service,
    ):
        log_service.return_value.record_market_overview_fetch.return_value = "log-us-breadth"
        payload = service.get_us_breadth()

    assert payload["source"] == "yfinance_proxy"
    assert calls["SPY"] == 1
    assert calls["RSP"] == 1
    assert calls["QQQ"] == 1
    assert calls["IWM"] == 1


def test_crypto_snapshot_includes_sol_and_funding_when_binance_public_data_available() -> None:
    service = MarketOverviewService()
    ticker_time = 1768435200000
    funding_time = 1768435260000

    ticker_rows = [
        {"symbol": "BTCUSDT", "lastPrice": "70000", "priceChangePercent": "1.2", "quoteVolume": "2200000000", "highPrice": "71000", "lowPrice": "69000", "closeTime": ticker_time},
        {"symbol": "ETHUSDT", "lastPrice": "3500", "priceChangePercent": "0.4", "quoteVolume": "1200000000", "highPrice": "3550", "lowPrice": "3400", "closeTime": ticker_time},
        {"symbol": "SOLUSDT", "lastPrice": "155", "priceChangePercent": "2.4", "quoteVolume": "700000000", "highPrice": "160", "lowPrice": "150", "closeTime": ticker_time},
        {"symbol": "BNBUSDT", "lastPrice": "610", "priceChangePercent": "-0.2", "quoteVolume": "320000000", "highPrice": "618", "lowPrice": "604", "closeTime": ticker_time},
    ]
    funding_rows = {
        "BTCUSDT": {"lastFundingRate": "0.00012", "time": funding_time},
        "ETHUSDT": {"lastFundingRate": "0.00008", "time": funding_time},
        "SOLUSDT": {"lastFundingRate": "-0.00005", "time": funding_time},
        "BNBUSDT": {"lastFundingRate": "0.00003", "time": funding_time},
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
    expected_ticker_time = datetime.fromtimestamp(ticker_time / 1000, ZoneInfo("UTC")).isoformat()
    expected_funding_time = datetime.fromtimestamp(funding_time / 1000, ZoneInfo("UTC")).isoformat()
    assert payload["asOf"] == expected_ticker_time
    assert next(item for item in payload["items"] if item["symbol"] == "BTC")["asOf"] == expected_ticker_time
    assert next(item for item in payload["items"] if item["symbol"] == "BTC_FUNDING")["asOf"] == expected_funding_time


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
    normalized_panel = service._with_market_meta(payload, "crypto")
    btc = service._with_item_meta(payload["items"][0], "crypto", normalized_panel)
    assert normalized_panel["asOf"] is None
    assert btc["asOf"] is None
    assert btc["freshness"] == "unavailable"
    assert btc["scoreContributionAllowed"] is False


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
