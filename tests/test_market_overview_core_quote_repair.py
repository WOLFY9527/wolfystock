# -*- coding: utf-8 -*-
"""Core quote source coverage regressions for Market Overview."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from src.services.market_cache import market_cache
from src.services.market_overview_service import MarketOverviewService
from src.storage import DatabaseManager


CN_TZ = timezone(timedelta(hours=8))


class _FrameColumn:
    def __init__(self, values: list[float]) -> None:
        self._values = values

    def tolist(self) -> list[float]:
        return list(self._values)


class _HistoryFrame:
    def __init__(self, closes: list[float], *, as_of: datetime, volumes: list[float] | None = None) -> None:
        self.empty = False
        self.index = [as_of - timedelta(days=len(closes) - 1 - index) for index in range(len(closes))]
        self._columns = {"Close": _FrameColumn(closes)}
        if volumes is not None:
            self._columns["Volume"] = _FrameColumn(volumes)

    def __getitem__(self, key: str) -> _FrameColumn:
        return self._columns[key]

    def __contains__(self, key: str) -> bool:
        return key in self._columns


@pytest.fixture(autouse=True)
def isolated_market_overview_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MARKET_OVERVIEW_SNAPSHOT_TEST_DB", "1")
    DatabaseManager.reset_instance()
    DatabaseManager(db_url=f"sqlite:///{tmp_path / 'market-overview-core-quotes.sqlite'}")
    market_cache.clear()
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    yield
    market_cache.clear()
    MarketOverviewService._market_cache.wait_for_refreshes(timeout=2)
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    DatabaseManager.reset_instance()


def _log_patch():
    patcher = patch("src.services.market_overview_service.ExecutionLogService")
    mocked = patcher.start()
    mocked.return_value.record_market_overview_fetch.return_value = "log-core-quotes"
    return patcher


def _item(payload: dict, symbol: str) -> dict:
    return next(item for item in payload["items"] if item["symbol"] == symbol)


def test_spx_configured_quote_carries_delayed_source_and_trust_metadata() -> None:
    service = MarketOverviewService()
    as_of = datetime.now(CN_TZ)

    def history(ticker: str) -> _HistoryFrame:
        if ticker == "^GSPC":
            return _HistoryFrame([5200.0, 5231.25], as_of=as_of, volumes=[1_000_000, 1_200_000])
        raise RuntimeError(f"{ticker} fixture unavailable")

    log_patcher = _log_patch()
    try:
        with patch("src.services.market_overview_service.fetch_yfinance_quote_history_frame", side_effect=history):
            payload = service.get_indices()
    finally:
        log_patcher.stop()

    spx = _item(payload, "SPX")
    assert spx["value"] == 5231.25
    assert spx["source"] == "yfinance"
    assert spx["sourceLabel"] == "Yahoo Finance"
    assert spx["sourceTier"] == "unofficial_public_api"
    assert spx["freshness"] == "delayed"
    assert spx["trustLevel"] == "usable_with_caution"
    assert spx["degradationReason"] == "delayed_source"
    assert spx["asOf"] == as_of.isoformat(timespec="seconds")
    assert spx["freshness"] not in {"live", "fresh"}

    unavailable = _item(payload, "NASDAQ")
    assert unavailable["value"] is None
    assert unavailable["source"] == "yfinance"
    assert unavailable["freshness"] == "unavailable"
    assert unavailable["isUnavailable"] is True
    assert unavailable["degradationReason"] == "provider_unavailable"
    assert unavailable["trustLevel"] == "unavailable"


def test_vix_official_quote_keeps_delayed_macro_semantics() -> None:
    service = MarketOverviewService()
    as_of = (datetime.now(CN_TZ) - timedelta(days=1)).date().isoformat()
    previous = (datetime.now(CN_TZ) - timedelta(days=2)).date().isoformat()

    points = {
        "VIXCLS": [
            ("VIXCLS", 18.4, as_of, as_of, "fred:VIXCLS", "official_public", "daily_close"),
            ("VIXCLS", 19.2, previous, previous, "fred:VIXCLS", "official_public", "daily_close"),
        ]
    }

    def official_points(*args: object, **kwargs: object) -> dict:
        from src.services.official_macro_transport import MacroObservation

        return {
            key: [MacroObservation(*row) for row in rows]
            for key, rows in points.items()
        }

    log_patcher = _log_patch()
    try:
        with (
            patch.object(service, "_quote_items", return_value=[]),
            patch.object(service, "_atr_item", return_value=None),
            patch.object(service, "_official_macro_points", side_effect=official_points),
        ):
            payload = service.get_volatility()
    finally:
        log_patcher.stop()

    vix = _item(payload, "VIX")
    assert vix["value"] == 18.4
    assert vix["source"] == "fred"
    assert vix["sourceLabel"].startswith("FRED")
    assert vix["sourceTier"] == "official_public"
    assert vix["freshness"] in {"delayed", "stale"}
    assert vix["freshness"] not in {"live", "fresh"}
    assert vix["trustLevel"] in {"usable_with_caution", "weak"}
    assert vix["degradationReason"] in {"delayed_source", "stale_source"}


def test_hsi_sina_proxy_quote_uses_dashboard_symbol_and_truthful_metadata() -> None:
    service = MarketOverviewService()
    row = [
        "HSI",
        "恒生指数",
        "25838.960",
        "25962.730",
        "25838.960",
        "25505.710",
        "25675.182",
        "-287.550",
        "-1.110",
        "0.000",
        "0.000",
        "292712398.554",
        "21878681948",
        "0.000",
        "0.000",
        "28056.100",
        "22668.350",
        "2026/05/18",
        "16:09:22",
    ]

    log_patcher = _log_patch()
    try:
        with patch("src.services.market_overview_service.fetch_sina_cn_index_rows", return_value={"rt_hkHSI": row}):
            payload = service.get_cn_indices()
    finally:
        log_patcher.stop()

    hsi = _item(payload, "HSI")
    assert hsi["value"] == 25675.182
    assert hsi["changePercent"] == -1.11
    assert hsi["source"] == "sina"
    assert hsi["sourceLabel"] == "新浪财经"
    assert hsi["sourceTier"] == "unofficial_public_api"
    assert hsi["freshness"] in {"cached", "stale"}
    assert hsi["freshness"] not in {"live", "fresh"}
    assert hsi["degradationReason"] in {"delayed_source", "stale_source"}
    assert hsi["asOf"] == "2026-05-18T16:09:22+08:00"
    assert all(item["symbol"] != "HSI.HK" for item in payload["items"])


def test_us10y_dxy_and_btc_keep_truthful_source_freshness_metadata() -> None:
    service = MarketOverviewService()
    as_of = datetime.now(CN_TZ)

    def history(ticker: str, *, timeout: float | None = None) -> _HistoryFrame:
        return _HistoryFrame([105.0, 105.4], as_of=as_of)

    def ticker_snapshot(symbols: list[str]) -> list[dict]:
        return [
            {
                "symbol": "BTCUSDT",
                "lastPrice": "67000",
                "priceChangePercent": "1.5",
                "quoteVolume": "1000000000",
                "highPrice": "67500",
                "lowPrice": "66000",
            }
        ] + [
            {
                "symbol": symbol,
                "lastPrice": "1",
                "priceChangePercent": "0",
                "quoteVolume": "1",
                "highPrice": "1",
                "lowPrice": "1",
            }
            for symbol in symbols
            if symbol != "BTCUSDT"
        ]

    def kline_rows(symbol: str) -> list[list[str]]:
        return [[0, "0", "0", "0", str(value)] for value in (66000, 66500, 67000)]

    log_patcher = _log_patch()
    try:
        with (
            patch.object(service, "_official_macro_points", return_value={}),
            patch("src.services.market_overview_service.fetch_yfinance_quote_history_frame", side_effect=history),
            patch("src.services.market_overview_service.fetch_binance_ticker_snapshot", side_effect=ticker_snapshot),
            patch("src.services.market_overview_service.fetch_binance_kline_history_rows", side_effect=kline_rows),
            patch("src.services.market_overview_service.fetch_binance_funding_row", side_effect=RuntimeError("funding unavailable")),
        ):
            macro_payload = service.get_macro()
            crypto_payload = service.get_crypto()
    finally:
        log_patcher.stop()

    us10y = _item(macro_payload, "US10Y")
    dxy = _item(macro_payload, "DXY")
    btc = _item(crypto_payload, "BTC")

    assert us10y["source"] == "yfinance"
    assert us10y["freshness"] == "delayed"
    assert us10y["sourceTier"] == "unofficial_public_api"
    assert us10y["degradationReason"] == "delayed_source"
    assert dxy["source"] == "yfinance"
    assert dxy["freshness"] == "delayed"
    assert dxy["sourceTier"] == "unofficial_public_api"
    assert dxy["degradationReason"] == "delayed_source"
    assert btc["source"] == "binance"
    assert btc["sourceTier"] == "exchange_public"
    assert btc["freshness"] == "live"
    assert btc.get("degradationReason") is None
