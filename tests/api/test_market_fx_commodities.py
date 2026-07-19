# -*- coding: utf-8 -*-
"""Focused contract tests for FX / commodities proxy runtime behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.services.market_overview_service import MarketOverviewService


CN_TZ = timezone(timedelta(hours=8))


def setup_function() -> None:
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.clear()


def teardown_function() -> None:
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.clear()


class _FrameColumn:
    def __init__(self, values: list[float]) -> None:
        self._values = values

    def tolist(self) -> list[float]:
        return list(self._values)


class _HistoryFrame:
    def __init__(self, closes: list[float], *, as_of: datetime) -> None:
        self.empty = False
        self.index = [as_of - timedelta(days=1), as_of]
        self._columns = {
            "Close": _FrameColumn(closes),
        }

    def __getitem__(self, key: str) -> _FrameColumn:
        return self._columns[key]

    def __contains__(self, key: str) -> bool:
        return key in self._columns


def test_fx_commodities_proxy_snapshot_uses_delayed_yfinance_adapter_without_live_label() -> None:
    service = MarketOverviewService()
    as_of = datetime.now(CN_TZ) - timedelta(minutes=30)
    frames = {
        "DX-Y.NYB": _HistoryFrame([104.0, 104.3], as_of=as_of),
        "CNH=X": _HistoryFrame([7.20, 7.24], as_of=as_of),
        "JPY=X": _HistoryFrame([155.3, 156.4], as_of=as_of),
        "EURUSD=X": _HistoryFrame([1.071, 1.066], as_of=as_of),
        "GC=F": _HistoryFrame([2350.0, 2368.7], as_of=as_of),
        "CL=F": _HistoryFrame([79.1, 78.4], as_of=as_of),
        "BZ=F": _HistoryFrame([82.7, 82.1], as_of=as_of),
        "HG=F": _HistoryFrame([4.58, 4.63], as_of=as_of),
    }

    with patch(
        "src.services.market_overview_service.fetch_yfinance_quote_history_frame",
        side_effect=lambda ticker, *, timeout=None: frames[ticker],
    ), patch("src.services.market_overview_service.ExecutionLogService") as mock_log_service:
        mock_log_service.return_value.record_market_overview_fetch.return_value = "log-1"
        payload = service.get_fx_commodities()

    items = {item["symbol"]: item for item in payload["items"]}

    assert payload["source"] == "yfinance_proxy"
    assert payload["sourceType"] == "unofficial_proxy"
    assert payload["freshness"] == "delayed"
    assert payload["providerHealth"]["provider"] == "yfinance_proxy"
    assert payload["providerHealth"]["status"] == "cache"
    assert payload["providerHealth"]["status"] != "live"
    assert items["DXY"]["symbol"] == "DXY"
    assert items["DXY"]["label"] == "DXY"
    assert items["DXY"]["source"] == "yfinance_proxy"
    assert items["DXY"]["sourceType"] == "unofficial_proxy"
    assert items["DXY"]["freshness"] == "delayed"
    assert items["DXY"]["isFallback"] is False
    assert items["GOLD"]["value"] == 2368.7
    assert items["WTI"]["value"] == 78.4
    assert items["COPPER"]["value"] == 4.63


def test_fx_commodities_proxy_snapshot_keeps_item_level_fallback_on_symbol_failure() -> None:
    service = MarketOverviewService()
    as_of = datetime.now(CN_TZ) - timedelta(minutes=30)
    frames = {
        "DX-Y.NYB": _HistoryFrame([104.0, 104.3], as_of=as_of),
        "JPY=X": _HistoryFrame([155.3, 156.4], as_of=as_of),
        "EURUSD=X": _HistoryFrame([1.071, 1.066], as_of=as_of),
        "GC=F": _HistoryFrame([2350.0, 2368.7], as_of=as_of),
        "CL=F": _HistoryFrame([79.1, 78.4], as_of=as_of),
        "BZ=F": _HistoryFrame([82.7, 82.1], as_of=as_of),
        "HG=F": _HistoryFrame([4.58, 4.63], as_of=as_of),
    }

    def _fake_history(ticker: str, *, timeout: float | None = None) -> _HistoryFrame:
        if ticker == "CNH=X":
            raise RuntimeError("proxy down")
        return frames[ticker]

    with patch(
        "src.services.market_overview_service.fetch_yfinance_quote_history_frame",
        side_effect=_fake_history,
    ), patch("src.services.market_overview_service.ExecutionLogService") as mock_log_service:
        mock_log_service.return_value.record_market_overview_fetch.return_value = "log-2"
        payload = service.get_fx_commodities()

    items = {item["symbol"]: item for item in payload["items"]}

    assert payload["source"] == "mixed"
    assert payload["sourceLabel"] == "多来源"
    assert payload["sourceType"] == "unofficial_proxy"
    assert payload["fallbackUsed"] is True
    assert payload["isFallback"] is False
    assert payload["providerHealth"]["status"] == "partial"
    assert payload["providerHealth"]["status"] != "live"
    assert items["DXY"]["source"] == "yfinance_proxy"
    assert items["DXY"]["isFallback"] is False
    assert items["USDCNH"]["source"] == "fallback"
    assert items["USDCNH"]["freshness"] == "fallback"
    assert items["USDCNH"]["isFallback"] is True
