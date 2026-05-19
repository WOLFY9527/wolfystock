# -*- coding: utf-8 -*-
"""Deadline and fallback contracts for Market Overview provider transports."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from src.services.market_cache import market_cache
from src.services.official_macro_transport import MacroObservation
from src.services.market_overview_service import MarketOverviewService
from src.services.market_overview_yfinance_transport import fetch_yfinance_quote_history_frame


def setup_function() -> None:
    market_cache.clear()
    MarketOverviewService._market_data_cache.clear()


def teardown_function() -> None:
    market_cache.clear()
    MarketOverviewService._market_data_cache.clear()


class _SlowTicker:
    def history(self, **_: object) -> object:
        time.sleep(0.05)
        return object()


def test_yfinance_history_transport_enforces_explicit_deadline() -> None:
    with patch("src.services.market_overview_yfinance_transport.yf.Ticker", return_value=_SlowTicker()):
        with pytest.raises(TimeoutError, match="yfinance history timeout"):
            fetch_yfinance_quote_history_frame("SPY", timeout=0.001)


def test_official_macro_points_stop_when_aggregate_deadline_is_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketOverviewService()
    calls: list[tuple[str, float | None]] = []
    stale_date = (datetime.now(timezone.utc).date() - timedelta(days=10)).isoformat()

    def slow_treasury_points(*, limit: int = 2, timeout: float | None = None) -> dict:
        calls.append(("treasury", timeout))
        raise AssertionError("VIXCLS should consume the official macro budget before Treasury")

    def fred_points(series_id: str, *, limit: int = 2, timeout: float | None = None) -> list:
        calls.append((series_id, timeout))
        time.sleep(0.03)
        return [
            MacroObservation(series_id, 18.0, stale_date, stale_date, f"fred:{series_id}", "official_public", "daily_close")
        ]

    monkeypatch.setattr(service, "OFFICIAL_MACRO_AGGREGATE_BUDGET_SECONDS", 0.01, raising=False)
    with (
        patch("src.services.market_overview_service.fetch_treasury_daily_rate_observation_points", side_effect=slow_treasury_points),
        patch("src.services.market_overview_service.fetch_fred_observation_points", side_effect=fred_points),
    ):
        points = service._official_macro_points()

    assert points == {}
    assert calls == [("VIXCLS", pytest.approx(0.01, abs=0.01))]


def test_official_macro_points_prioritize_vixcls_then_fred_dgs10_dgs30_after_treasury_miss() -> None:
    service = MarketOverviewService()
    latest = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    previous = (datetime.now(timezone.utc).date() - timedelta(days=2)).isoformat()
    calls: list[str] = []

    def empty_treasury_points(*, limit: int = 2, timeout: float | None = None) -> dict:
        calls.append("treasury")
        return {}

    def fred_points(series_id: str, *, limit: int = 2, timeout: float | None = None) -> list[MacroObservation]:
        calls.append(series_id)
        if series_id == "DGS2" and not {"DGS10", "DGS30"}.issubset(set(calls)):
            raise AssertionError("DGS10/DGS30 should not wait behind lower-priority DGS2")
        if series_id in {"VIXCLS", "DGS10", "DGS30"}:
            return [
                MacroObservation(series_id, 4.5, latest, latest, f"fred:{series_id}", "official_public", "daily_rate"),
                MacroObservation(series_id, 4.4, previous, previous, f"fred:{series_id}", "official_public", "daily_rate"),
            ]
        return []

    with (
        patch("src.services.market_overview_service.fetch_treasury_daily_rate_observation_points", side_effect=empty_treasury_points),
        patch("src.services.market_overview_service.fetch_fred_observation_points", side_effect=fred_points),
    ):
        points = service._official_macro_points()

    assert calls[:4] == ["VIXCLS", "treasury", "DGS10", "DGS30"]
    assert points["VIXCLS"]
    assert points["DGS10"]
    assert points["DGS30"]


def test_official_macro_points_attempt_fred_dgs10_dgs30_after_treasury_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketOverviewService()
    latest = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    previous = (datetime.now(timezone.utc).date() - timedelta(days=2)).isoformat()
    calls: list[str] = []
    treasury_timeouts: list[float | None] = []

    def timeout_treasury_points(*, limit: int = 2, timeout: float | None = None) -> dict:
        calls.append("treasury")
        treasury_timeouts.append(timeout)
        time.sleep(float(timeout or 0.0) + 0.005)
        raise TimeoutError("treasury timeout")

    def fred_points(series_id: str, *, limit: int = 2, timeout: float | None = None) -> list[MacroObservation]:
        calls.append(series_id)
        if series_id == "DGS10":
            time.sleep(float(timeout or 0.0) + 0.005)
        if series_id in {"DGS10", "DGS30"}:
            return [
                MacroObservation(series_id, 4.5, latest, latest, f"fred:{series_id}", "official_public", "daily_rate"),
                MacroObservation(series_id, 4.4, previous, previous, f"fred:{series_id}", "official_public", "daily_rate"),
            ]
        return []

    monkeypatch.setattr(service, "OFFICIAL_MACRO_AGGREGATE_BUDGET_SECONDS", 0.18, raising=False)
    monkeypatch.setattr(service, "OFFICIAL_MACRO_CALL_TIMEOUT_SECONDS", 0.18, raising=False)
    with (
        patch("src.services.market_overview_service.fetch_treasury_daily_rate_observation_points", side_effect=timeout_treasury_points),
        patch("src.services.market_overview_service.fetch_fred_observation_points", side_effect=fred_points),
    ):
        points = service._official_macro_points()

    assert calls[:4] == ["VIXCLS", "treasury", "DGS10", "DGS30"]
    assert treasury_timeouts and treasury_timeouts[0] is not None
    assert treasury_timeouts[0] < 0.18
    assert points["DGS10"][0].source_id == "fred:DGS10"
    assert points["DGS30"][0].source_id == "fred:DGS30"


def test_rates_macro_and_volatility_reuse_official_macro_observations_within_micro_cache_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketOverviewService()
    monkeypatch.setattr(service, "OFFICIAL_MACRO_MICRO_CACHE_TTL_SECONDS", 60.0, raising=False)
    latest_date = datetime.now(timezone.utc).date() - timedelta(days=1)
    latest = latest_date.isoformat()
    previous = (latest_date - timedelta(days=1)).isoformat()
    calls: list[str] = []
    treasury_points = {
        "DGS2": [
            MacroObservation("DGS2", 3.87, latest, latest, "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
            MacroObservation("DGS2", 3.91, previous, previous, "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
        ],
        "DGS10": [
            MacroObservation("DGS10", 4.41, latest, latest, "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
            MacroObservation("DGS10", 4.45, previous, previous, "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
        ],
        "DGS30": [
            MacroObservation("DGS30", 4.89, latest, latest, "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
            MacroObservation("DGS30", 4.92, previous, previous, "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
        ],
    }
    fred_points = {
        "DFF": [
            MacroObservation("DFF", 4.33, latest, latest, "fred:DFF", "official_public", "daily_policy_rate"),
            MacroObservation("DFF", 4.31, previous, previous, "fred:DFF", "official_public", "daily_policy_rate"),
        ],
        "VIXCLS": [
            MacroObservation("VIXCLS", 18.22, latest, latest, "fred:VIXCLS", "official_public", "daily_close"),
            MacroObservation("VIXCLS", 19.11, previous, previous, "fred:VIXCLS", "official_public", "daily_close"),
        ],
        "CPIAUCSL": [
            MacroObservation("CPIAUCSL", 321.0, latest, latest, "fred:CPIAUCSL", "official_public", "monthly_inflation_index"),
            MacroObservation("CPIAUCSL", 309.9, previous, previous, "fred:CPIAUCSL", "official_public", "monthly_inflation_index"),
        ],
        "PPIACO": [
            MacroObservation("PPIACO", 282.0, latest, latest, "fred:PPIACO", "official_public", "monthly_inflation_index"),
            MacroObservation("PPIACO", 248.0, previous, previous, "fred:PPIACO", "official_public", "monthly_inflation_index"),
        ],
        "SOFR": [
            MacroObservation("SOFR", 5.31, latest, latest, "fred:SOFR", "official_public", "daily_fixing"),
            MacroObservation("SOFR", 5.32, previous, previous, "fred:SOFR", "official_public", "daily_fixing"),
        ],
        "BAMLH0A0HYM2": [
            MacroObservation("BAMLH0A0HYM2", 3.31, latest, latest, "fred:BAMLH0A0HYM2", "official_public", "daily_credit_stress"),
            MacroObservation("BAMLH0A0HYM2", 3.45, previous, previous, "fred:BAMLH0A0HYM2", "official_public", "daily_credit_stress"),
        ],
    }

    def treasury_observations(*, limit: int = 2, timeout: float | None = None) -> dict:
        calls.append("treasury")
        return treasury_points

    def fred_observations(series_id: str, *, limit: int = 2, timeout: float | None = None) -> list:
        calls.append(series_id)
        return fred_points.get(series_id, [])

    def direct_cached_payload(_cache_key: str, fetcher: object, _fallback_factory: object) -> dict:
        return fetcher()  # type: ignore[operator]

    with (
        patch.object(service, "_cached_payload", side_effect=direct_cached_payload),
        patch.object(service, "_quote_items", return_value=[{"symbol": "VIX", "value": 20.0, "change_pct": 0.0, "trend": [20.0], "source": "yfinance"}]),
        patch.object(service, "_atr_item", return_value=None),
        patch("src.services.market_overview_service.fetch_treasury_daily_rate_observation_points", side_effect=treasury_observations),
        patch("src.services.market_overview_service.fetch_fred_observation_points", side_effect=fred_observations),
        patch("src.services.market_overview_service.ExecutionLogService") as log_service,
    ):
        log_service.return_value.record_market_overview_fetch.return_value = "log-market"
        rates_payload = service.get_rates()
        macro_payload = service.get_macro()
        volatility_payload = service.get_volatility()

    assert rates_payload["items"]
    assert macro_payload["items"]
    assert volatility_payload["items"]
    assert calls == ["VIXCLS", "treasury", "SOFR", "DFF", "CPIAUCSL", "PPIACO", "BAMLH0A0HYM2"]


def test_sentiment_deadline_skips_secondary_provider_and_fallback_is_not_live(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketOverviewService()
    alternative_calls = 0
    monkeypatch.setattr(service, "SENTIMENT_AGGREGATE_BUDGET_SECONDS", 0.01, raising=False)

    def slow_cnn() -> dict:
        time.sleep(0.03)
        raise TimeoutError("cnn timeout")

    def unexpected_alternative() -> dict:
        nonlocal alternative_calls
        alternative_calls += 1
        raise AssertionError("alternative provider should be skipped after sentiment budget is exhausted")

    with (
        patch.object(service, "_fetch_cnn_fear_greed_snapshot", side_effect=slow_cnn),
        patch.object(service, "_fetch_alternative_fear_greed_snapshot", side_effect=unexpected_alternative),
        patch("src.services.market_overview_service.ExecutionLogService") as log_service,
    ):
        log_service.return_value.record_market_overview_fetch.return_value = "log-sentiment"
        payload = service.get_market_sentiment()

    assert alternative_calls == 0
    assert payload["source"] == "unavailable"
    assert payload["freshness"] not in {"live", "fresh"}
    assert payload["isFallback"] is True
    assert payload["providerHealth"]["status"] == "unavailable"


def test_sentiment_snapshot_passes_remaining_deadline_to_transports(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketOverviewService()
    monkeypatch.setattr(service, "SENTIMENT_AGGREGATE_BUDGET_SECONDS", 0.4, raising=False)
    cnn_timeouts: list[float] = []
    alternative_timeouts: list[float] = []

    def cnn_payload(*, timeout: float) -> dict:
        cnn_timeouts.append(timeout)
        raise RuntimeError("cnn unavailable")

    def alternative_payload(*, timeout: float) -> dict:
        alternative_timeouts.append(timeout)
        return {"data": [{"value": "22"}, {"value": "24"}, {"value": "35"}]}

    with (
        patch("src.services.market_overview_service.fetch_cnn_fear_greed_payload", side_effect=cnn_payload),
        patch("src.services.market_overview_service.fetch_alternative_fear_greed_payload", side_effect=alternative_payload),
    ):
        payload = service._fetch_market_sentiment_snapshot()

    assert payload["source"] == "alternative_me"
    assert cnn_timeouts and 0 < cnn_timeouts[0] <= 0.45
    assert alternative_timeouts and 0 < alternative_timeouts[0] <= 0.45


def test_fx_proxy_snapshot_passes_deadline_to_yfinance_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketOverviewService()
    monkeypatch.setattr(service, "YFINANCE_PROXY_AGGREGATE_BUDGET_SECONDS", 0.4, raising=False)
    timeouts: list[float] = []

    class _FrameColumn:
        def __init__(self, values: list[float]) -> None:
            self._values = values

        def tolist(self) -> list[float]:
            return list(self._values)

    class _HistoryFrame:
        def __init__(self, closes: list[float]) -> None:
            self.empty = False
            self.index = [0, 1]
            self._columns = {"Close": _FrameColumn(closes)}

        def __getitem__(self, key: str) -> _FrameColumn:
            return self._columns[key]

        def __contains__(self, key: str) -> bool:
            return key in self._columns

    def fake_history(ticker: str, *, timeout: float) -> _HistoryFrame:
        timeouts.append(timeout)
        return _HistoryFrame([1.0, 1.1])

    with patch("src.services.market_overview_service.fetch_yfinance_quote_history_frame", side_effect=fake_history):
        payload = service._fetch_fx_commodities_snapshot()

    assert payload["source"] == "yfinance_proxy"
    assert timeouts
    assert all(0 < timeout <= 0.45 for timeout in timeouts)


def test_futures_snapshot_passes_deadline_to_yfinance_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketOverviewService()
    monkeypatch.setattr(service, "YFINANCE_PROXY_AGGREGATE_BUDGET_SECONDS", 0.4, raising=False)
    timeouts: list[float] = []

    class _FrameColumn:
        def __init__(self, values: list[float]) -> None:
            self._values = values

        def tolist(self) -> list[float]:
            return list(self._values)

    class _HistoryFrame:
        def __init__(self, closes: list[float]) -> None:
            self.empty = False
            self.index = [0, 1]
            self._columns = {"Close": _FrameColumn(closes)}

        def __getitem__(self, key: str) -> _FrameColumn:
            return self._columns[key]

        def __contains__(self, key: str) -> bool:
            return key in self._columns

    def fake_history(ticker: str, *, timeout: float) -> _HistoryFrame:
        timeouts.append(timeout)
        return _HistoryFrame([1.0, 1.1])

    with patch("src.services.market_overview_service.fetch_yfinance_quote_history_frame", side_effect=fake_history):
        payload = service._fetch_futures_snapshot()

    assert payload["source"] == "mixed"
    assert timeouts
    assert all(0 < timeout <= 0.45 for timeout in timeouts)


def test_fx_yfinance_stage_deadline_preserves_honest_fallback_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketOverviewService()
    monkeypatch.setattr(service, "YFINANCE_PROXY_AGGREGATE_BUDGET_SECONDS", 0.03, raising=False)

    def slow_proxy_history(_: str, *, timeout: float) -> object:
        time.sleep(0.02)
        raise TimeoutError("yfinance proxy timeout")

    with (
        patch("src.services.market_overview_service.fetch_yfinance_quote_history_frame", side_effect=slow_proxy_history) as fetch_history,
        patch("src.services.market_overview_service.ExecutionLogService") as log_service,
    ):
        log_service.return_value.record_market_overview_fetch.return_value = "log-fx"
        payload = service.get_fx_commodities()

    assert fetch_history.call_count < len(service.FX_COMMODITY_PROXY_TICKERS)
    assert payload["source"] == "fallback"
    assert payload["freshness"] == "fallback"
    assert payload["isFallback"] is True
    assert payload["providerHealth"]["status"] == "fallback"
    assert all(item["freshness"] == "fallback" for item in payload["items"])
