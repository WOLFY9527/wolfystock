# -*- coding: utf-8 -*-
"""Core quote source coverage regressions for Market Overview."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import Config
from src.services.market_cache import market_cache
from src.services.market_overview_service import MarketOverviewService, get_freshness_status
from src.services.official_macro_transport import MacroObservation, OfficialMacroTransportError
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


def test_official_daily_rows_use_series_lag_policy_not_intraday_threshold() -> None:
    now = datetime(2026, 5, 19, 10, 0, tzinfo=CN_TZ)

    vix_freshness = get_freshness_status(
        "2026-05-15",
        "macro_rate",
        "fred",
        False,
        source_type="official_public",
        series_id="VIXCLS",
        now=now,
    )
    assert vix_freshness["freshness"] == "delayed"
    assert vix_freshness["freshnessPolicy"] == "official_daily_us_weekday_t_plus_1"
    assert vix_freshness["officialObservationDate"] == "2026-05-15"
    assert vix_freshness["maxAcceptedLagDays"] == 4
    assert vix_freshness["calendarAssumption"] == "US/Eastern weekdays; holidays not modeled"

    vix_volatility_freshness = get_freshness_status(
        "2026-05-15",
        "futures",
        "fred",
        False,
        source_type="official_public",
        series_id="VIXCLS",
        now=now,
    )
    assert vix_volatility_freshness["freshness"] == "delayed"
    assert vix_volatility_freshness["isStale"] is False
    assert vix_volatility_freshness["freshnessDecision"] == "accepted"

    stale_dgs30 = get_freshness_status(
        "2026-05-08",
        "macro_rate",
        "fred",
        False,
        source_type="official_public",
        series_id="DGS30",
        now=now,
    )
    assert stale_dgs30["freshness"] == "stale"
    assert stale_dgs30["freshnessDecision"] == "stale_official_row"
    assert stale_dgs30["staleReason"]

    proxy_freshness = get_freshness_status(
        "2026-05-15",
        "macro_rate",
        "yfinance",
        False,
        source_type="unofficial_proxy",
        series_id="DGS30",
        now=now,
    )
    assert proxy_freshness["freshness"] == "stale"
    assert "freshnessPolicy" not in proxy_freshness


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
    assert spx["providerAttempted"] is True
    assert spx["providerClass"] == "proxy"
    assert spx["officialOverlayAttempted"] is False
    assert spx["officialOverlayAvailable"] is False
    assert spx["officialOverlayFailureReason"] == "not_configured"
    assert spx["activationHint"] == "proxy_only_no_official_overlay"
    assert spx["sourceType"] != "exchange_public"
    assert spx["sourceTier"] != "exchange_public"

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
    assert vix["providerAttempted"] is True
    assert vix["providerClass"] == "official_daily"
    assert vix["officialOverlayAttempted"] is True
    assert vix["officialOverlayAvailable"] is True
    assert vix["officialOverlayFailureReason"] is None
    assert vix["activationHint"] == "official_daily_overlay_active"


def test_vix_fred_transport_overlay_is_consumed_when_fresh_enough() -> None:
    service = MarketOverviewService()
    proxy_as_of = datetime.now(CN_TZ)
    latest_date = (datetime.now(CN_TZ) - timedelta(days=1)).date().isoformat()
    previous_date = (datetime.now(CN_TZ) - timedelta(days=2)).date().isoformat()

    def history(ticker: str) -> _HistoryFrame:
        if ticker == "^VIX":
            return _HistoryFrame([19.0, 17.5], as_of=proxy_as_of, volumes=[1_000_000, 1_100_000])
        raise RuntimeError(f"{ticker} fixture unavailable")

    def fred_points(series_id: str, **_: object) -> list[MacroObservation]:
        if series_id == "VIXCLS":
            return [
                MacroObservation("VIXCLS", 16.8, latest_date, latest_date, "fred:VIXCLS", "official_public", "daily_close"),
                MacroObservation("VIXCLS", 17.2, previous_date, previous_date, "fred:VIXCLS", "official_public", "daily_close"),
            ]
        return []

    log_patcher = _log_patch()
    try:
        with (
            patch("src.services.market_overview_service.fetch_yfinance_quote_history_frame", side_effect=history),
            patch("src.services.market_overview_service.fetch_treasury_daily_rate_observation_points", return_value={}),
            patch("src.services.market_overview_service.fetch_fred_observation_points", side_effect=fred_points) as fred_fetch,
            patch.object(service, "_atr_item", return_value=None),
        ):
            payload = service.get_volatility()
    finally:
        log_patcher.stop()

    vix = _item(payload, "VIX")
    assert "VIXCLS" in [call.args[0] for call in fred_fetch.call_args_list]
    assert vix["value"] == 16.8
    assert vix["source"] == "fred"
    assert vix["sourceId"] == "fred:VIXCLS"
    assert vix["sourceType"] == "official_public"
    assert vix["providerClass"] == "official_daily"
    assert vix["officialOverlayAttempted"] is True
    assert vix["officialOverlayAvailable"] is True
    assert vix["officialOverlayFailureReason"] is None
    assert vix["freshness"] == "delayed"
    assert vix["isStale"] is False
    assert vix["sourceFreshnessEvidence"]["freshness"] == "delayed"


def test_vix_yfinance_proxy_panel_and_item_cannot_claim_live_realtime() -> None:
    service = MarketOverviewService()
    as_of = datetime.now(CN_TZ)

    def history(ticker: str) -> _HistoryFrame:
        if ticker == "^VIX":
            return _HistoryFrame([18.0, 15.0], as_of=as_of, volumes=[1_000_000, 1_100_000])
        raise RuntimeError(f"{ticker} fixture unavailable")

    log_patcher = _log_patch()
    try:
        with (
            patch("src.services.market_overview_service.fetch_yfinance_quote_history_frame", side_effect=history),
            patch("src.services.market_overview_service.fetch_treasury_daily_rate_observation_points", return_value={}),
            patch("src.services.market_overview_service.fetch_fred_observation_points", return_value=[]),
            patch.object(service, "_atr_item", return_value=None),
        ):
            payload = service.get_volatility()
    finally:
        log_patcher.stop()

    vix = _item(payload, "VIX")
    assert vix["value"] == 15.0
    assert vix["source"] == "yfinance"
    assert vix["sourceType"] == "unofficial_proxy"
    assert vix["sourceTier"] == "unofficial_public_api"
    assert vix["freshness"] == "delayed"
    assert vix["freshness"] not in {"live", "fresh"}
    assert vix["trustLevel"] == "usable_with_caution"
    assert vix["degradationReason"] == "delayed_source"
    assert vix["providerAttempted"] is True
    assert vix["providerClass"] == "proxy"
    assert vix["officialOverlayAttempted"] is True
    assert vix["officialOverlayAvailable"] is False
    assert vix["officialOverlayFailureReason"] == "empty_response"
    assert vix["activationHint"] == "official_overlay_unavailable_using_proxy"

    assert payload["source"] == "yfinance"
    assert payload["sourceType"] == "unofficial_proxy"
    assert payload["freshness"] == "delayed"
    assert payload["freshness"] not in {"live", "fresh"}
    assert payload["evidenceSnapshot"]["freshness"] == "partial"


def test_vix_stale_official_overlay_does_not_replace_delayed_proxy() -> None:
    service = MarketOverviewService()
    as_of = datetime.now(CN_TZ)
    stale_date = (datetime.now(CN_TZ) - timedelta(days=10)).date().isoformat()
    previous = (datetime.now(CN_TZ) - timedelta(days=11)).date().isoformat()

    def history(ticker: str) -> _HistoryFrame:
        if ticker == "^VIX":
            return _HistoryFrame([18.0, 15.0], as_of=as_of, volumes=[1_000_000, 1_100_000])
        raise RuntimeError(f"{ticker} fixture unavailable")

    def official_points(*args: object, **kwargs: object) -> dict:
        return {
            "VIXCLS": [
                MacroObservation("VIXCLS", 21.5, stale_date, stale_date, "fred:VIXCLS", "official_public", "daily_close"),
                MacroObservation("VIXCLS", 20.4, previous, previous, "fred:VIXCLS", "official_public", "daily_close"),
            ]
        }

    log_patcher = _log_patch()
    try:
        with (
            patch("src.services.market_overview_service.fetch_yfinance_quote_history_frame", side_effect=history),
            patch.object(service, "_official_macro_points", side_effect=official_points),
            patch.object(service, "_atr_item", return_value=None),
        ):
            payload = service.get_volatility()
    finally:
        log_patcher.stop()

    vix = _item(payload, "VIX")
    assert vix["value"] == 15.0
    assert vix["source"] == "yfinance"
    assert vix["sourceType"] == "unofficial_proxy"
    assert vix["providerClass"] == "proxy"
    assert vix["freshness"] == "delayed"
    assert vix["officialOverlayAttempted"] is True
    assert vix["officialOverlayAvailable"] is False
    assert vix["officialOverlayFailureReason"] == "stale_official_row"
    assert vix["activationHint"] == "official_overlay_stale_using_proxy"


def test_vix_fred_cache_miss_reason_is_propagated_to_proxy_item() -> None:
    service = MarketOverviewService()
    as_of = datetime.now(CN_TZ)
    service._official_macro_overlay_diagnostics["VIXCLS"] = "cache_miss"

    def history(ticker: str) -> _HistoryFrame:
        if ticker == "^VIX":
            return _HistoryFrame([18.0, 15.0], as_of=as_of, volumes=[1_000_000, 1_100_000])
        raise RuntimeError(f"{ticker} fixture unavailable")

    log_patcher = _log_patch()
    try:
        with (
            patch("src.services.market_overview_service.fetch_yfinance_quote_history_frame", side_effect=history),
            patch.object(service, "_official_macro_points", return_value={}),
            patch.object(service, "_atr_item", return_value=None),
        ):
            payload = service.get_volatility()
    finally:
        log_patcher.stop()

    vix = _item(payload, "VIX")
    assert vix["value"] == 15.0
    assert vix["sourceType"] == "unofficial_proxy"
    assert vix["providerClass"] == "proxy"
    assert vix["officialOverlayAttempted"] is True
    assert vix["officialOverlayAvailable"] is False
    assert vix["officialOverlayFailureReason"] == "cache_miss"
    assert vix["activationHint"] == "official_overlay_unavailable_using_proxy"


def test_vix_official_budget_exhausted_reason_is_reported_when_refresh_cannot_start() -> None:
    service = MarketOverviewService()
    as_of = datetime.now(CN_TZ)

    def history(ticker: str) -> _HistoryFrame:
        if ticker == "^VIX":
            return _HistoryFrame([18.0, 15.0], as_of=as_of, volumes=[1_000_000, 1_100_000])
        raise RuntimeError(f"{ticker} fixture unavailable")

    def fail_if_called(*args: object, **kwargs: object) -> object:
        raise AssertionError(f"official macro transport should not be called: {args} {kwargs}")

    log_patcher = _log_patch()
    try:
        with (
            patch("src.services.market_overview_service.fetch_yfinance_quote_history_frame", side_effect=history),
            patch("src.services.market_overview_service.fetch_treasury_daily_rate_observation_points", side_effect=fail_if_called),
            patch("src.services.market_overview_service.fetch_fred_observation_points", side_effect=fail_if_called),
            patch.object(service, "OFFICIAL_MACRO_AGGREGATE_BUDGET_SECONDS", 0.0),
            patch.object(service, "_atr_item", return_value=None),
        ):
            payload = service.get_volatility()
    finally:
        log_patcher.stop()

    vix = _item(payload, "VIX")
    assert vix["value"] == 15.0
    assert vix["sourceType"] == "unofficial_proxy"
    assert vix["providerClass"] == "proxy"
    assert vix["officialOverlayAttempted"] is True
    assert vix["officialOverlayAvailable"] is False
    assert vix["officialOverlayFailureReason"] == "budget_exhausted"
    assert vix["activationHint"] == "official_overlay_unavailable_using_proxy"


def test_vix_fred_missing_api_key_reason_is_propagated_to_proxy_item() -> None:
    service = MarketOverviewService()
    as_of = datetime.now(CN_TZ)

    def history(ticker: str) -> _HistoryFrame:
        if ticker == "^VIX":
            return _HistoryFrame([18.0, 15.0], as_of=as_of, volumes=[1_000_000, 1_100_000])
        raise RuntimeError(f"{ticker} fixture unavailable")

    log_patcher = _log_patch()
    try:
        with (
            patch("src.services.market_overview_service.fetch_yfinance_quote_history_frame", side_effect=history),
            patch("src.services.market_overview_service.fetch_treasury_daily_rate_observation_points", return_value={}),
            patch(
                "src.services.market_overview_service.fetch_fred_observation_points",
                side_effect=OfficialMacroTransportError("missing_api_key", "FRED API key not configured"),
            ),
            patch.object(service, "_atr_item", return_value=None),
        ):
            payload = service.get_volatility()
    finally:
        log_patcher.stop()

    vix = _item(payload, "VIX")
    assert vix["value"] == 15.0
    assert vix["sourceType"] == "unofficial_proxy"
    assert vix["providerClass"] == "proxy"
    assert vix["officialOverlayAttempted"] is True
    assert vix["officialOverlayAvailable"] is False
    assert vix["officialOverlayFailureReason"] == "missing_api_key"
    assert vix["activationHint"] == "official_overlay_unavailable_using_proxy"


def test_vix_fred_missing_runtime_config_uses_config_probe_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketOverviewService()
    as_of = datetime.now(CN_TZ)
    monkeypatch.setenv("FRED_API_KEY", "")
    Config.reset_instance()

    def history(ticker: str) -> _HistoryFrame:
        if ticker == "^VIX":
            return _HistoryFrame([18.0, 15.0], as_of=as_of, volumes=[1_000_000, 1_100_000])
        raise RuntimeError(f"{ticker} fixture unavailable")

    log_patcher = _log_patch()
    try:
        with (
            patch("src.services.market_overview_service.fetch_yfinance_quote_history_frame", side_effect=history),
            patch("src.services.market_overview_service.fetch_treasury_daily_rate_observation_points", return_value={}),
            patch("src.services.official_macro_transport.urlopen", side_effect=AssertionError("network should not be called")),
            patch.object(service, "_atr_item", return_value=None),
        ):
            payload = service.get_volatility()
    finally:
        log_patcher.stop()
        Config.reset_instance()

    vix = _item(payload, "VIX")
    assert vix["officialOverlayFailureReason"] == "missing_api_key"
    diagnostics = vix["officialOverlayFailureDetails"]
    assert diagnostics["providerName"] == "fred"
    assert diagnostics["endpointHost"] == "api.stlouisfed.org"
    assert diagnostics["requestedSeries"] == "VIXCLS"
    assert diagnostics["configPresent"] is True
    assert diagnostics["apiKeyPresent"] is False
    assert "api_key" not in str(diagnostics)


def test_vix_runtime_timeout_exception_is_not_collapsed_to_transport_error() -> None:
    service = MarketOverviewService()
    as_of = datetime.now(CN_TZ)

    def history(ticker: str) -> _HistoryFrame:
        if ticker == "^VIX":
            return _HistoryFrame([18.0, 15.0], as_of=as_of, volumes=[1_000_000, 1_100_000])
        raise RuntimeError(f"{ticker} fixture unavailable")

    log_patcher = _log_patch()
    try:
        with (
            patch("src.services.market_overview_service.fetch_yfinance_quote_history_frame", side_effect=history),
            patch("src.services.market_overview_service.fetch_treasury_daily_rate_observation_points", return_value={}),
            patch(
                "src.services.market_overview_service.fetch_fred_observation_points",
                side_effect=RuntimeError("read timed out token=SECRET"),
            ),
            patch.object(service, "_atr_item", return_value=None),
        ):
            payload = service.get_volatility()
    finally:
        log_patcher.stop()

    vix = _item(payload, "VIX")
    assert vix["officialOverlayFailureReason"] == "timeout"
    diagnostics = vix["officialOverlayFailureDetails"]
    assert diagnostics["providerName"] == "fred"
    assert diagnostics["requestedSeries"] == "VIXCLS"
    assert diagnostics["exceptionClass"] == "RuntimeError"
    assert "SECRET" not in str(diagnostics)


def test_fred_vix_priority_preserves_overlay_when_lower_priority_sources_exhaust_budget() -> None:
    service = MarketOverviewService()
    latest_date = (datetime.now(CN_TZ) - timedelta(days=1)).date().isoformat()
    previous_date = (datetime.now(CN_TZ) - timedelta(days=2)).date().isoformat()
    calls: list[str] = []

    def slow_vix_points(series_id: str, **_: object) -> list[MacroObservation]:
        calls.append(series_id)
        time.sleep(0.02)
        if series_id == "VIXCLS":
            return [
                MacroObservation("VIXCLS", 16.8, latest_date, latest_date, "fred:VIXCLS", "official_public", "daily_close"),
                MacroObservation("VIXCLS", 17.2, previous_date, previous_date, "fred:VIXCLS", "official_public", "daily_close"),
            ]
        return []

    def fail_if_called(*args: object, **kwargs: object) -> object:
        raise AssertionError(f"lower-priority official transport should not run before VIXCLS: {args} {kwargs}")

    with (
        patch("src.services.market_overview_service.fetch_fred_observation_points", side_effect=slow_vix_points),
        patch("src.services.market_overview_service.fetch_treasury_daily_rate_observation_points", side_effect=fail_if_called),
    ):
        points = service._official_macro_points(budget_seconds=0.01)

    assert calls == ["VIXCLS"]
    assert [point.value for point in points["VIXCLS"]] == [16.8, 17.2]


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


def test_hsi_sina_provider_quote_overrides_hk_alias_fallback_row() -> None:
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
    fallback = service._card_snapshot([
        service._metric_item("恒生指数", "HSI.HK", 17680.30, 146.20, 0.83, "pts", [17410, 17520, 17610, 17680.30], market="HK")
    ])

    log_patcher = _log_patch()
    try:
        with (
            patch.object(service, "_fallback_cn_indices_snapshot", return_value=fallback),
            patch("src.services.market_overview_service.fetch_sina_cn_index_rows", return_value={"rt_hkHSI": row}),
        ):
            payload = service.get_cn_indices()
    finally:
        log_patcher.stop()

    hsi = _item(payload, "HSI")
    assert hsi["value"] == 25675.182
    assert hsi["source"] == "sina"
    assert hsi["isFallback"] is False
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
            patch("src.services.market_overview_service.fetch_yfinance_quote_history_frame", side_effect=history),
            patch("src.services.market_overview_service.fetch_treasury_daily_rate_observation_points", return_value={}),
            patch("src.services.market_overview_service.fetch_fred_observation_points", return_value=[]),
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
    assert us10y["providerClass"] == "proxy"
    assert us10y["officialOverlayAttempted"] is True
    assert us10y["officialOverlayAvailable"] is False
    assert us10y["officialOverlayFailureReason"] == "empty_response"
    assert us10y["activationHint"] == "official_overlay_unavailable_using_proxy"
    assert dxy["source"] == "yfinance"
    assert dxy["freshness"] == "delayed"
    assert dxy["sourceTier"] == "unofficial_public_api"
    assert dxy["degradationReason"] == "delayed_source"
    assert dxy["providerClass"] == "proxy"
    assert dxy["officialOverlayAttempted"] is False
    assert dxy["officialOverlayAvailable"] is False
    assert dxy["officialOverlayFailureReason"] == "not_configured"
    assert dxy["activationHint"] == "proxy_only_no_official_overlay"
    assert dxy["freshness"] not in {"live", "fresh"}
    assert btc["source"] == "binance"
    assert btc["sourceTier"] == "exchange_public"
    assert btc["freshness"] == "live"
    assert btc.get("degradationReason") is None


def test_fred_dgs10_and_dgs30_overlays_replace_proxy_when_fresh_enough_without_configuring_fx_commodity_overlays() -> None:
    service = MarketOverviewService()
    latest_date = (datetime.now(CN_TZ) - timedelta(days=1)).date().isoformat()
    previous_date = (datetime.now(CN_TZ) - timedelta(days=2)).date().isoformat()
    proxy_as_of = datetime.now(CN_TZ).isoformat(timespec="seconds")
    proxy_items = [
        {
            "symbol": "US10Y",
            "label": "10Y yield",
            "value": 4.5,
            "price": 4.5,
            "unit": "%",
            "change_pct": 0.0,
            "changePercent": 0.0,
            "risk_direction": "neutral",
            "trend": [4.48, 4.5],
            "source": "yfinance",
            "sourceLabel": "Yahoo Finance",
            "sourceType": "unofficial_proxy",
            "asOf": proxy_as_of,
        },
        {
            "symbol": "US30Y",
            "label": "30Y yield",
            "value": 4.9,
            "price": 4.9,
            "unit": "%",
            "change_pct": 0.0,
            "changePercent": 0.0,
            "risk_direction": "neutral",
            "trend": [4.88, 4.9],
            "source": "yfinance",
            "sourceLabel": "Yahoo Finance",
            "sourceType": "unofficial_proxy",
            "asOf": proxy_as_of,
        },
        {
            "symbol": "DXY",
            "label": "US Dollar Index",
            "value": 105.2,
            "price": 105.2,
            "unit": "idx",
            "change_pct": 0.1,
            "changePercent": 0.1,
            "risk_direction": "decreasing",
            "trend": [105.0, 105.2],
            "source": "yfinance",
            "sourceLabel": "Yahoo Finance",
            "sourceType": "unofficial_proxy",
            "asOf": proxy_as_of,
        },
        {
            "symbol": "GOLD",
            "label": "Gold futures",
            "value": 2400.0,
            "price": 2400.0,
            "unit": "USD",
            "change_pct": -0.2,
            "changePercent": -0.2,
            "risk_direction": "increasing",
            "trend": [2405.0, 2400.0],
            "source": "yfinance",
            "sourceLabel": "Yahoo Finance",
            "sourceType": "unofficial_proxy",
            "asOf": proxy_as_of,
        },
        {
            "symbol": "OIL",
            "label": "WTI crude",
            "value": 78.0,
            "price": 78.0,
            "unit": "USD",
            "change_pct": 0.4,
            "changePercent": 0.4,
            "risk_direction": "decreasing",
            "trend": [77.7, 78.0],
            "source": "yfinance",
            "sourceLabel": "Yahoo Finance",
            "sourceType": "unofficial_proxy",
            "asOf": proxy_as_of,
        },
    ]

    def fred_points(series_id: str, **_: object) -> list[MacroObservation]:
        return {
            "DGS10": [
                MacroObservation("DGS10", 4.42, latest_date, latest_date, "fred:DGS10", "official_public", "daily_rate"),
                MacroObservation("DGS10", 4.47, previous_date, previous_date, "fred:DGS10", "official_public", "daily_rate"),
            ],
            "DGS30": [
                MacroObservation("DGS30", 4.88, latest_date, latest_date, "fred:DGS30", "official_public", "daily_rate"),
                MacroObservation("DGS30", 4.93, previous_date, previous_date, "fred:DGS30", "official_public", "daily_rate"),
            ],
        }.get(series_id, [])

    log_patcher = _log_patch()
    try:
        with (
            patch.object(service, "_quote_items", return_value=proxy_items),
            patch("src.services.market_overview_service.fetch_treasury_daily_rate_observation_points", return_value={}),
            patch("src.services.market_overview_service.fetch_fred_observation_points", side_effect=fred_points),
        ):
            macro_payload = service.get_macro()
    finally:
        log_patcher.stop()

    us10y = _item(macro_payload, "US10Y")
    us30y = _item(macro_payload, "US30Y")
    for item, source_id in ((us10y, "fred:DGS10"), (us30y, "fred:DGS30")):
        assert item["source"] == "fred"
        assert item["sourceId"] == source_id
        assert item["sourceType"] == "official_public"
        assert item["providerClass"] == "official_daily"
        assert item["officialOverlayAttempted"] is True
        assert item["officialOverlayAvailable"] is True
        assert item["officialOverlayFailureReason"] is None
        assert item["freshness"] not in {"live", "fresh"}

    for symbol in ("DXY", "GOLD", "OIL"):
        item = _item(macro_payload, symbol)
        assert item["sourceType"] == "unofficial_proxy"
        assert item["officialOverlayAttempted"] is False
        assert item["officialOverlayAvailable"] is False
        assert item["officialOverlayFailureReason"] == "not_configured"


def test_treasury_timeout_then_stale_fred_rate_overlay_keeps_proxy_with_provider_attempt_details() -> None:
    service = MarketOverviewService()
    stale_date = (datetime.now(CN_TZ) - timedelta(days=10)).date().isoformat()
    previous_date = (datetime.now(CN_TZ) - timedelta(days=11)).date().isoformat()
    proxy_as_of = datetime.now(CN_TZ).isoformat(timespec="seconds")
    calls: list[str] = []
    proxy_items = [
        {
            "symbol": "US10Y",
            "label": "10Y yield",
            "value": 4.5,
            "price": 4.5,
            "unit": "%",
            "change_pct": 0.0,
            "changePercent": 0.0,
            "risk_direction": "neutral",
            "trend": [4.48, 4.5],
            "source": "yfinance",
            "sourceLabel": "Yahoo Finance",
            "sourceType": "unofficial_proxy",
            "asOf": proxy_as_of,
        },
        {
            "symbol": "US30Y",
            "label": "30Y yield",
            "value": 4.9,
            "price": 4.9,
            "unit": "%",
            "change_pct": 0.0,
            "changePercent": 0.0,
            "risk_direction": "neutral",
            "trend": [4.88, 4.9],
            "source": "yfinance",
            "sourceLabel": "Yahoo Finance",
            "sourceType": "unofficial_proxy",
            "asOf": proxy_as_of,
        },
    ]

    def timeout_treasury_points(*, limit: int = 2, timeout: float | None = None) -> dict:
        calls.append("treasury")
        time.sleep(float(timeout or 0.0) + 0.005)
        raise OfficialMacroTransportError(
            "timeout",
            "treasury timed out token=SECRET",
            diagnostics={
                "providerName": "treasury",
                "endpointHost": "home.treasury.gov",
                "timeoutSeconds": timeout,
                "exceptionClass": "TimeoutError",
                "attemptedAt": "2026-05-19T00:00:00Z",
                "caBundleSource": "certifi",
            },
        )

    def stale_fred_points(series_id: str, **_: object) -> list[MacroObservation]:
        calls.append(series_id)
        if series_id in {"DGS10", "DGS30"}:
            return [
                MacroObservation(series_id, 4.42, stale_date, stale_date, f"fred:{series_id}", "official_public", "daily_rate"),
                MacroObservation(series_id, 4.47, previous_date, previous_date, f"fred:{series_id}", "official_public", "daily_rate"),
            ]
        return []

    log_patcher = _log_patch()
    try:
        with (
            patch.object(service, "OFFICIAL_MACRO_AGGREGATE_BUDGET_SECONDS", 0.18),
            patch.object(service, "OFFICIAL_MACRO_CALL_TIMEOUT_SECONDS", 0.18),
            patch.object(service, "_quote_items", return_value=proxy_items),
            patch("src.services.market_overview_service.fetch_treasury_daily_rate_observation_points", side_effect=timeout_treasury_points),
            patch("src.services.market_overview_service.fetch_fred_observation_points", side_effect=stale_fred_points),
        ):
            macro_payload = service.get_macro()
    finally:
        log_patcher.stop()

    assert calls[:4] == ["VIXCLS", "treasury", "DGS10", "DGS30"]
    for symbol, series_id in (("US10Y", "DGS10"), ("US30Y", "DGS30")):
        item = _item(macro_payload, symbol)
        assert item["source"] == "yfinance"
        assert item["sourceType"] == "unofficial_proxy"
        assert item["providerClass"] == "proxy"
        assert item["officialOverlayAttempted"] is True
        assert item["officialOverlayAvailable"] is False
        assert item["officialOverlayFailureReason"] == "stale_official_row"
        details = item["officialOverlayFailureDetails"]
        assert details["officialObservationDate"] == stale_date
        assert details["freshnessPolicy"] == "official_daily_us_weekday_t_plus_1"
        assert details["freshnessDecision"] == "stale_official_row"
        assert details["staleReason"]
        attempts = details["providerAttemptDetails"]
        assert [(attempt["providerName"], attempt["reason"]) for attempt in attempts] == [
            ("treasury", "timeout"),
            ("fred", "stale_official_row"),
        ]
        assert attempts[1]["officialObservationDate"] == stale_date
        assert attempts[1]["freshnessPolicy"] == "official_daily_us_weekday_t_plus_1"
        assert all(attempt["requestedSeries"] == series_id for attempt in attempts)
        assert "SECRET" not in str(details)
        assert "api_key" not in str(details).lower()


def test_cn00y_static_fallback_is_explicit_and_capped() -> None:
    service = MarketOverviewService()

    log_patcher = _log_patch()
    try:
        with patch.object(service, "_fetch_sina_cn_index_quotes", side_effect=RuntimeError("sina unavailable")):
            payload = service.get_cn_indices()
    finally:
        log_patcher.stop()

    cn00y = _item(payload, "CN00Y")
    assert cn00y["source"] == "fallback"
    assert cn00y["freshness"] == "fallback"
    assert cn00y["isFallback"] is True
    assert cn00y["providerAttempted"] is False
    assert cn00y["providerClass"] == "static"
    assert cn00y["officialOverlayAttempted"] is False
    assert cn00y["officialOverlayAvailable"] is False
    assert cn00y["officialOverlayFailureReason"] == "not_configured"
    assert cn00y["sourceTier"] == "static_fallback"
    assert cn00y["trustLevel"] == "weak"
    assert cn00y["degradationReason"] == "fallback_source"
    assert cn00y["activationHint"] == "static_fallback_no_provider"
