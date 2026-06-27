from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.services.historical_ohlcv_readiness import (
    build_backtest_historical_ohlcv_readiness,
    HistoricalOhlcvBar,
    HistoricalOhlcvProviderResult,
    HistoricalOhlcvReadinessRequest,
    HistoricalOhlcvReadinessService,
)
from src.services.historical_ohlcv_runtime_adapter import HistoricalOhlcvRuntimeAdapter
from src.services.stock_structure_decision_service import StockStructureDecisionService
from src.services.yfinance_us_ohlcv_cache_provider import (
    YFINANCE_US_OHLCV_CACHE_SOURCE,
    YfinanceUsOhlcvCacheProvider,
)


class _FakeOhlcvProvider:
    def __init__(
        self,
        responses: dict[str, HistoricalOhlcvProviderResult],
    ) -> None:
        self.responses = responses
        self.calls: list[HistoricalOhlcvReadinessRequest] = []

    def fetch_ohlcv_history(
        self,
        request: HistoricalOhlcvReadinessRequest,
    ) -> HistoricalOhlcvProviderResult:
        self.calls.append(request)
        return self.responses.get(
            request.symbol,
            HistoricalOhlcvProviderResult.unavailable("provider_unavailable"),
        )


class _FakeHistoryService:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def get_history_data(self, stock_code: str, period: str = "daily", days: int = 30) -> dict[str, Any]:
        self.calls.append({"stock_code": stock_code, "period": period, "days": days})
        return self.payload


class _RaisingHistoryService:
    def get_history_data(self, stock_code: str, period: str = "daily", days: int = 30) -> dict[str, Any]:
        raise RuntimeError("providerName=LeakyProvider token=secret Traceback")


class _FakeUsOhlcvCache:
    def __init__(self, frames: dict[str, Any] | None = None) -> None:
        self.frames = dict(frames or {})
        self.load_calls: list[dict[str, Any]] = []
        self.save_calls: list[dict[str, Any]] = []

    def load(self, symbol: str, *, start_date: str | None = None, end_date: str | None = None, days: int | None = None):
        self.load_calls.append(
            {"symbol": symbol, "start_date": start_date, "end_date": end_date, "days": days}
        )
        return self.frames.get(symbol)

    def save(self, symbol: str, frame: Any) -> int:
        self.save_calls.append({"symbol": symbol, "rows": len(frame)})
        self.frames[symbol] = frame
        return len(frame)


class _FakeDailyFetcher:
    def __init__(self, frame: Any | None = None, error: Exception | None = None) -> None:
        self.frame = frame
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def get_daily_data(self, stock_code: str, start_date=None, end_date=None, days: int = 30):
        self.calls.append(
            {
                "stock_code": stock_code,
                "start_date": start_date,
                "end_date": end_date,
                "days": days,
            }
        )
        if self.error is not None:
            raise self.error
        return self.frame, YFINANCE_US_OHLCV_CACHE_SOURCE


def _bars(count: int, *, start: date = date(2026, 1, 1), adjusted: bool = True) -> list[HistoricalOhlcvBar]:
    return [
        HistoricalOhlcvBar(
            date=start + timedelta(days=index),
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.5 + index,
            volume=1000.0 + index,
            adjusted_close=100.5 + index if adjusted else None,
        )
        for index in range(count)
    ]


def _history_payload(count: int) -> dict[str, Any]:
    return {
        "stock_code": "AAPL",
        "period": "daily",
        "data": [
            {
                "date": bar.date.isoformat(),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in _bars(count, adjusted=False)
        ],
        "source": "local_db",
        "diagnostics": {"status": "ok", "reason": "history_available"},
    }


def _frame(count: int, *, start: date = date(2026, 1, 1), adjusted: bool = True):
    import pandas as pd

    rows: list[dict[str, Any]] = []
    for bar in _bars(count, start=start, adjusted=adjusted):
        row = {
            "date": bar.date.isoformat(),
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
        if adjusted:
            row["adjusted_close"] = bar.adjusted_close
        rows.append(row)
    return pd.DataFrame(rows)


def test_no_provider_configured_returns_provider_missing_readiness_without_bars() -> None:
    request = HistoricalOhlcvReadinessRequest(
        symbol="AAPL",
        market="us",
        timeframe="1d",
        lookback_bars=90,
        required_bars=60,
    )

    result = HistoricalOhlcvReadinessService().fetch(request)

    assert result.bars == []
    assert result.unavailable_reason == "provider_missing"
    assert result.readiness["symbol"] == "AAPL"
    assert result.readiness["market"] == "us"
    assert result.readiness["timeframe"] == "1d"
    assert result.readiness["lookbackBars"] == 90
    assert result.readiness["requiredBars"] == 60
    assert result.readiness["usableBars"] == 0
    assert result.readiness["missingBars"] == 60
    assert result.readiness["overallState"] == "blocked"
    assert result.readiness["providerState"] == "provider_missing"
    assert result.readiness["missingRequirements"] == ["provider_missing", "insufficient_history"]


def test_backtest_projection_maps_provider_missing_to_not_configured_actionable_contract() -> None:
    request = HistoricalOhlcvReadinessRequest(
        symbol="AAPL",
        market="us",
        timeframe="1d",
        start=date(2026, 1, 1),
        end=date(2026, 3, 31),
        lookback_bars=90,
        required_bars=60,
        require_adjusted=True,
        benchmark_symbol="SPY",
        benchmark_required=True,
    )

    result = HistoricalOhlcvReadinessService().fetch(request)
    projection = build_backtest_historical_ohlcv_readiness(
        result.readiness,
        runtime_status="not_configured",
    )

    assert projection["contractVersion"] == "backtest_historical_ohlcv_readiness_v1"
    assert projection["status"] == "not_configured"
    assert projection["executable"] is False
    assert projection["requestedSymbol"] == "AAPL"
    assert projection["requestedMarket"] == "us"
    assert projection["requestedDateRange"] == {"start": "2026-01-01", "end": "2026-03-31"}
    assert projection["requiredBarCount"] == 60
    assert projection["availableBarCount"] == 0
    assert projection["adjustedDataRequirement"] == {"required": True, "state": "missing"}
    assert projection["benchmarkReadiness"] == {"required": True, "symbol": "SPY", "status": "missing"}
    assert projection["historicalOhlcvRuntimeStatus"] == "not_configured"
    assert projection["blockedExecutionReason"] == "historical_ohlcv_not_configured"
    assert "historical_ohlcv" in projection["missingDataClasses"]
    assert "adjusted_prices" in projection["missingDataClasses"]
    assert "benchmark_ohlcv" in projection["missingDataClasses"]
    assert projection["consumerSafe"] is True
    serialized = json.dumps(projection, ensure_ascii=False).lower()
    for forbidden in ("apikey", "token", "credential", "traceid", "requestid", "cachekey", "traceback"):
        assert forbidden not in serialized


def test_backtest_projection_distinguishes_insufficient_coverage_stale_adjustment_and_available() -> None:
    base_readiness = {
        "contractVersion": "historical_ohlcv_readiness_v1",
        "symbol": "AAPL",
        "market": "us",
        "timeframe": "1d",
        "requestedRange": {"start": "2026-01-01", "end": "2026-02-15"},
        "lookbackBars": 30,
        "requiredBars": 30,
        "usableBars": 30,
        "missingBars": 0,
        "freshnessState": "current",
        "adjustmentState": "available",
        "benchmarkState": "not_requested",
        "providerState": "available",
        "overallState": "ready",
        "missingRequirements": [],
        "consumerSafe": True,
    }
    insufficient = {**base_readiness, "usableBars": 12, "missingBars": 18, "overallState": "blocked", "missingRequirements": ["insufficient_history"]}
    stale = {**base_readiness, "freshnessState": "stale", "overallState": "degraded", "missingRequirements": ["stale_data"]}
    missing_adjusted = {**base_readiness, "adjustmentState": "missing", "overallState": "degraded", "missingRequirements": ["missing_adjustments"]}

    assert build_backtest_historical_ohlcv_readiness(insufficient)["status"] == "insufficient_coverage"
    assert build_backtest_historical_ohlcv_readiness(stale)["status"] == "stale"
    assert build_backtest_historical_ohlcv_readiness(missing_adjusted)["status"] == "missing"
    available_projection = build_backtest_historical_ohlcv_readiness(base_readiness)
    assert available_projection["status"] == "available"
    assert available_projection["executable"] is True
    assert available_projection["blockedExecutionReason"] is None


def test_fake_provider_with_sufficient_bars_returns_normalized_available_payload() -> None:
    request = HistoricalOhlcvReadinessRequest(
        symbol="AAPL",
        market="us",
        timeframe="1d",
        start=date(2026, 1, 1),
        end=date(2026, 2, 14),
        required_bars=30,
        require_adjusted=True,
    )
    provider = _FakeOhlcvProvider(
        {"AAPL": HistoricalOhlcvProviderResult.available(_bars(45), adjustments_available=True)}
    )

    result = HistoricalOhlcvReadinessService(provider=provider).fetch(request)

    assert [call.symbol for call in provider.calls] == ["AAPL"]
    assert len(result.bars) == 45
    assert result.bars[0].as_dict() == {
        "date": "2026-01-01",
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 1000.0,
        "adjustedClose": 100.5,
    }
    assert result.unavailable_reason is None
    assert result.readiness["overallState"] == "ready"
    assert result.readiness["requiredBars"] == 30
    assert result.readiness["usableBars"] == 45
    assert result.readiness["missingBars"] == 0
    assert result.readiness["adjustmentState"] == "available"
    assert result.readiness["benchmarkState"] == "not_requested"
    assert result.readiness["missingRequirements"] == []


def test_fake_provider_with_insufficient_bars_quantifies_missing_bars() -> None:
    request = HistoricalOhlcvReadinessRequest(symbol="AAPL", market="us", timeframe="1d", required_bars=30)
    provider = _FakeOhlcvProvider(
        {"AAPL": HistoricalOhlcvProviderResult.available(_bars(12), adjustments_available=True)}
    )

    result = HistoricalOhlcvReadinessService(provider=provider).fetch(request)

    assert result.readiness["overallState"] == "blocked"
    assert result.readiness["usableBars"] == 12
    assert result.readiness["missingBars"] == 18
    assert "insufficient_history" in result.readiness["missingRequirements"]


def test_stale_data_is_reported_without_fabricating_missing_prices() -> None:
    request = HistoricalOhlcvReadinessRequest(
        symbol="AAPL",
        market="us",
        timeframe="1d",
        end=date(2026, 2, 15),
        required_bars=5,
    )
    provider = _FakeOhlcvProvider(
        {"AAPL": HistoricalOhlcvProviderResult.available(_bars(10, start=date(2026, 1, 1)))}
    )

    result = HistoricalOhlcvReadinessService(provider=provider).fetch(request)

    assert result.readiness["freshnessState"] == "stale"
    assert "stale_data" in result.readiness["missingRequirements"]
    assert all("return" not in bar.as_dict() for bar in result.bars)


def test_missing_adjustments_are_reported_when_adjusted_history_is_required() -> None:
    request = HistoricalOhlcvReadinessRequest(
        symbol="AAPL",
        market="us",
        timeframe="1d",
        required_bars=5,
        require_adjusted=True,
    )
    provider = _FakeOhlcvProvider(
        {"AAPL": HistoricalOhlcvProviderResult.available(_bars(8, adjusted=False), adjustments_available=False)}
    )

    result = HistoricalOhlcvReadinessService(provider=provider).fetch(request)

    assert result.readiness["adjustmentState"] == "missing"
    assert "missing_adjustments" in result.readiness["missingRequirements"]


def test_missing_benchmark_is_reported_when_benchmark_history_is_required() -> None:
    request = HistoricalOhlcvReadinessRequest(
        symbol="AAPL",
        market="us",
        timeframe="1d",
        required_bars=5,
        benchmark_symbol="SPY",
        benchmark_required=True,
    )
    provider = _FakeOhlcvProvider(
        {"AAPL": HistoricalOhlcvProviderResult.available(_bars(8), adjustments_available=True)}
    )

    result = HistoricalOhlcvReadinessService(provider=provider).fetch(request)

    assert [call.symbol for call in provider.calls] == ["AAPL", "SPY"]
    assert result.readiness["benchmarkState"] == "missing"
    assert "missing_benchmark" in result.readiness["missingRequirements"]


def test_provider_unavailable_and_entitlement_required_are_consumer_safe_states() -> None:
    request = HistoricalOhlcvReadinessRequest(symbol="AAPL", market="us", timeframe="1d", required_bars=5)
    cases = {
        "provider_unavailable": ("provider_unavailable", "provider_unavailable"),
        "entitlement_required": ("entitlement_required", "entitlement_required"),
    }

    for label, (reason, provider_state) in cases.items():
        provider = _FakeOhlcvProvider({"AAPL": HistoricalOhlcvProviderResult.unavailable(reason)})
        result = HistoricalOhlcvReadinessService(provider=provider).fetch(request)

        assert result.unavailable_reason == reason, label
        assert result.readiness["providerState"] == provider_state
        assert reason in result.readiness["missingRequirements"]


def test_consumer_payload_redacts_provider_internal_metadata() -> None:
    request = HistoricalOhlcvReadinessRequest(symbol="AAPL", market="us", timeframe="1d", required_bars=5)
    provider = _FakeOhlcvProvider(
        {
            "AAPL": HistoricalOhlcvProviderResult.available(
                _bars(8),
                adjustments_available=True,
                metadata={
                    "requestId": "rq-secret",
                    "traceId": "trace-secret",
                    "cacheKey": "cache-secret",
                    "apiKey": "key-secret",
                    "providerClass": "LeakyProvider",
                    "rawPayload": {"token": "token-secret"},
                },
            )
        }
    )

    result = HistoricalOhlcvReadinessService(provider=provider).fetch(request)
    serialized = json.dumps(result.as_dict(), ensure_ascii=False).lower()

    for forbidden in (
        "requestid",
        "traceid",
        "cachekey",
        "apikey",
        "providerclass",
        "rawpayload",
        "token-secret",
        "rq-secret",
        "trace-secret",
        "cache-secret",
        "key-secret",
        "leakyprovider",
    ):
        assert forbidden not in serialized


def test_historical_ohlcv_readiness_module_does_not_import_network_clients() -> None:
    source = Path("src/services/historical_ohlcv_readiness.py").read_text(encoding="utf-8")

    for forbidden in ("requests", "httpx", "urllib", "socket"):
        assert forbidden not in source


def test_runtime_adapter_without_configured_runtime_returns_provider_missing() -> None:
    request = HistoricalOhlcvReadinessRequest(symbol="AAPL", market="us", timeframe="1d", required_bars=5)

    result = HistoricalOhlcvRuntimeAdapter().fetch_ohlcv_history(request)

    assert result.unavailable_reason == "provider_missing"
    assert result.bars == ()


def test_runtime_adapter_normalizes_existing_history_service_payload() -> None:
    history = _FakeHistoryService(_history_payload(6))
    request = HistoricalOhlcvReadinessRequest(
        symbol="AAPL",
        market="us",
        timeframe="1d",
        start=date(2026, 1, 1),
        end=date(2026, 1, 6),
        lookback_bars=90,
        required_bars=5,
    )

    result = HistoricalOhlcvRuntimeAdapter(history_runtime=history).fetch_ohlcv_history(request)

    assert history.calls == [{"stock_code": "AAPL", "period": "daily", "days": 90}]
    assert result.unavailable_reason is None
    assert result.adjustments_available is None
    assert result.freshness_state is None
    assert len(result.bars) == 6
    assert result.bars[0].as_dict() == {
        "date": "2026-01-01",
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 1000.0,
    }


def test_runtime_adapter_maps_existing_unavailable_reasons_to_safe_states() -> None:
    cases = {
        "history_unavailable": "provider_missing",
        "provider_missing": "provider_missing",
        "entitlement_required": "entitlement_required",
    }
    for reason, expected in cases.items():
        payload = {
            "stock_code": "AAPL",
            "period": "daily",
            "data": [],
            "source": "unavailable",
            "diagnostics": {"status": "unavailable", "reason": reason},
        }

        result = HistoricalOhlcvRuntimeAdapter(
            history_runtime=_FakeHistoryService(payload)
        ).fetch_ohlcv_history(
            HistoricalOhlcvReadinessRequest(symbol="AAPL", market="us", timeframe="1d")
        )

        assert result.unavailable_reason == expected
        assert result.bars == ()


def test_runtime_adapter_provider_exception_is_redacted_to_provider_unavailable() -> None:
    result = HistoricalOhlcvRuntimeAdapter(
        history_runtime=_RaisingHistoryService()
    ).fetch_ohlcv_history(
        HistoricalOhlcvReadinessRequest(symbol="AAPL", market="us", timeframe="1d")
    )

    serialized = json.dumps(result.__dict__, ensure_ascii=False).lower()
    assert result.unavailable_reason == "provider_unavailable"
    for forbidden in (
        "providername",
        "leakyprovider",
        "secret",
        "traceback",
        "exceptionclass",
        "token",
    ):
        assert forbidden not in serialized


def test_yfinance_us_cache_provider_default_disabled_does_not_call_provider() -> None:
    cache = _FakeUsOhlcvCache()
    fetcher = _FakeDailyFetcher(_frame(60))
    provider = YfinanceUsOhlcvCacheProvider(
        cache=cache,
        fetcher=fetcher,
        provider_fetch_enabled=False,
    )

    result = provider.fetch_ohlcv_history(
        HistoricalOhlcvReadinessRequest(symbol="AAPL", market="us", timeframe="1d", required_bars=30)
    )

    assert result.unavailable_reason == "provider_missing"
    assert result.bars == ()
    assert fetcher.calls == []
    assert cache.save_calls == []


def test_yfinance_us_cache_provider_cache_hit_bypasses_provider_call() -> None:
    cache = _FakeUsOhlcvCache({"AAPL": _frame(45)})
    fetcher = _FakeDailyFetcher(_frame(60))
    provider = YfinanceUsOhlcvCacheProvider(
        cache=cache,
        fetcher=fetcher,
        provider_fetch_enabled=False,
    )

    readiness = HistoricalOhlcvReadinessService(provider=provider).fetch(
        HistoricalOhlcvReadinessRequest(
            symbol="AAPL",
            market="us",
            timeframe="1d",
            start=date(2026, 1, 1),
            end=date(2026, 2, 14),
            lookback_bars=90,
            required_bars=30,
        )
    ).readiness

    assert readiness["providerState"] == "available"
    assert readiness["overallState"] == "ready"
    assert readiness["requiredBars"] == 30
    assert readiness["usableBars"] == 45
    assert readiness["missingBars"] == 0
    assert fetcher.calls == []
    assert cache.save_calls == []


def test_yfinance_us_cache_provider_enabled_fetches_and_persists_sufficient_bars() -> None:
    cache = _FakeUsOhlcvCache()
    fetcher = _FakeDailyFetcher(_frame(60))
    provider = YfinanceUsOhlcvCacheProvider(
        cache=cache,
        fetcher=fetcher,
        provider_fetch_enabled=True,
    )

    result = HistoricalOhlcvReadinessService(provider=provider).fetch(
        HistoricalOhlcvReadinessRequest(
            symbol="NVDA",
            market="us",
            timeframe="1d",
            start=date(2026, 1, 1),
            end=date(2026, 3, 1),
            lookback_bars=90,
            required_bars=50,
            require_adjusted=True,
        )
    )

    assert fetcher.calls == [
        {"stock_code": "NVDA", "start_date": "2026-01-01", "end_date": "2026-03-01", "days": 90}
    ]
    assert cache.save_calls == [{"symbol": "NVDA", "rows": 60}]
    assert len(result.bars) == 60
    assert result.readiness["providerState"] == "available"
    assert result.readiness["overallState"] == "ready"
    assert result.readiness["missingRequirements"] == []


def test_yfinance_us_cache_provider_reports_insufficient_stale_and_missing_adjustments() -> None:
    cases = [
        (
            HistoricalOhlcvReadinessRequest(symbol="ORCL", market="us", timeframe="1d", required_bars=30),
            _frame(10),
            "insufficient_history",
        ),
        (
            HistoricalOhlcvReadinessRequest(
                symbol="ORCL",
                market="us",
                timeframe="1d",
                end=date(2026, 3, 1),
                required_bars=5,
            ),
            _frame(10, start=date(2026, 1, 1)),
            "stale_data",
        ),
        (
            HistoricalOhlcvReadinessRequest(
                symbol="ORCL",
                market="us",
                timeframe="1d",
                required_bars=5,
                require_adjusted=True,
            ),
            _frame(10, adjusted=False),
            "missing_adjustments",
        ),
    ]

    for request, frame, expected in cases:
        provider = YfinanceUsOhlcvCacheProvider(
            cache=_FakeUsOhlcvCache({"ORCL": frame}),
            fetcher=_FakeDailyFetcher(_frame(60)),
            provider_fetch_enabled=False,
        )

        readiness = HistoricalOhlcvReadinessService(provider=provider).fetch(request).readiness

        assert expected in readiness["missingRequirements"]


def test_yfinance_us_cache_provider_redacts_provider_exceptions() -> None:
    provider = YfinanceUsOhlcvCacheProvider(
        cache=_FakeUsOhlcvCache(),
        fetcher=_FakeDailyFetcher(error=RuntimeError("token=secret provider=LeakyProvider Traceback")),
        provider_fetch_enabled=True,
    )

    result = provider.fetch_ohlcv_history(
        HistoricalOhlcvReadinessRequest(symbol="AAPL", market="us", timeframe="1d", required_bars=30)
    )
    serialized = json.dumps(result.__dict__, ensure_ascii=False).lower()

    assert result.unavailable_reason == "provider_unavailable"
    for forbidden in ("secret", "leakyprovider", "traceback", "token"):
        assert forbidden not in serialized


def test_stock_structure_can_route_orcl_and_aapl_through_yfinance_cache_provider() -> None:
    cache = _FakeUsOhlcvCache({"ORCL": _frame(120), "AAPL": _frame(120)})
    provider = YfinanceUsOhlcvCacheProvider(
        cache=cache,
        fetcher=_FakeDailyFetcher(_frame(120)),
        provider_fetch_enabled=False,
    )

    for symbol in ("ORCL", "AAPL"):
        payload = StockStructureDecisionService(
            historical_ohlcv_provider=provider,
            require_adjusted_ohlcv=True,
        ).get_structure_decision(symbol)

        readiness = payload["historicalOhlcvReadiness"]
        assert readiness["symbol"] == symbol
        assert readiness["providerState"] == "available"
        assert readiness["requiredBars"] > 0
        assert readiness["usableBars"] >= readiness["requiredBars"]
        assert readiness["missingBars"] == 0
        assert "missing_adjustments" not in readiness["missingRequirements"]


def test_stock_structure_yfinance_cache_env_wiring_uses_provider_without_history_call(monkeypatch) -> None:
    provider = _FakeOhlcvProvider(
        {"AAPL": HistoricalOhlcvProviderResult.available(_bars(120), adjustments_available=True)}
    )
    history = _FakeHistoryService(_history_payload(0))
    monkeypatch.setenv("WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED", "true")
    monkeypatch.setattr(
        "src.services.stock_structure_decision_service.YfinanceUsOhlcvCacheProvider.from_env",
        lambda: provider,
    )

    payload = StockStructureDecisionService(history_service=history).get_structure_decision("AAPL")

    assert history.calls == []
    assert [call.symbol for call in provider.calls] == ["AAPL"]
    assert payload["historicalOhlcvReadiness"]["overallState"] == "ready"


def test_stock_structure_payload_includes_historical_ohlcv_readiness() -> None:
    payload = StockStructureDecisionService(
        history_service=_FakeHistoryService(_history_payload(8)),
    ).get_structure_decision("AAPL")

    readiness = payload["historicalOhlcvReadiness"]
    assert readiness["symbol"] == "AAPL"
    assert readiness["timeframe"] == "1d"
    assert readiness["requiredBars"] > 8
    assert readiness["usableBars"] == 8
    assert readiness["missingBars"] == readiness["requiredBars"] - 8
    assert readiness["overallState"] == "blocked"
    assert "insufficient_history" in readiness["missingRequirements"]
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in ("requestid", "traceid", "cachekey", "apikey", "rawpayload", "exception"):
        assert forbidden not in serialized


def test_stock_structure_runtime_adapter_can_make_readiness_actionable_with_sufficient_bars() -> None:
    history = _FakeHistoryService(_history_payload(120))

    payload = StockStructureDecisionService(
        historical_ohlcv_provider=HistoricalOhlcvRuntimeAdapter(history_runtime=history),
    ).get_structure_decision("AAPL")

    readiness = payload["historicalOhlcvReadiness"]
    assert history.calls == [{"stock_code": "AAPL", "period": "daily", "days": 90}]
    assert readiness["providerState"] == "available"
    assert readiness["overallState"] == "ready"
    assert readiness["requiredBars"] > 0
    assert readiness["usableBars"] >= readiness["requiredBars"]
    assert readiness["missingBars"] == 0
    assert readiness["missingRequirements"] == []


def test_stock_structure_default_runtime_adapter_is_disabled_without_env(monkeypatch) -> None:
    monkeypatch.delenv("WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED", raising=False)
    history = _FakeHistoryService(_history_payload(120))

    payload = StockStructureDecisionService(history_service=history).get_structure_decision("AAPL")

    assert history.calls == [{"stock_code": "AAPL", "period": "daily", "days": 90}]
    readiness = payload["historicalOhlcvReadiness"]
    assert readiness["overallState"] == "ready"
    assert readiness["providerState"] == "available"


def test_stock_structure_env_enabled_runtime_adapter_uses_existing_history_service(monkeypatch) -> None:
    monkeypatch.setenv("WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED", "true")
    history = _FakeHistoryService(_history_payload(120))

    payload = StockStructureDecisionService(history_service=history).get_structure_decision("AAPL")

    assert history.calls == [{"stock_code": "AAPL", "period": "daily", "days": 90}]
    readiness = payload["historicalOhlcvReadiness"]
    assert readiness["overallState"] == "ready"
    assert readiness["providerState"] == "available"
    assert readiness["missingBars"] == 0


def test_stock_structure_runtime_adapter_classifies_insufficient_stale_adjustments_and_entitlement() -> None:
    insufficient_payload = StockStructureDecisionService(
        historical_ohlcv_provider=HistoricalOhlcvRuntimeAdapter(
            history_runtime=_FakeHistoryService(_history_payload(4))
        ),
    ).get_structure_decision("AAPL")
    assert "insufficient_history" in insufficient_payload["historicalOhlcvReadiness"]["missingRequirements"]

    stale_provider = _FakeOhlcvProvider(
        {
            "AAPL": HistoricalOhlcvProviderResult.available(
                _bars(60, start=date(2026, 1, 1)),
                freshness_state="stale",
                adjustments_available=True,
            )
        }
    )
    stale_payload = StockStructureDecisionService(historical_ohlcv_provider=stale_provider).get_structure_decision("AAPL")
    assert "stale_data" in stale_payload["historicalOhlcvReadiness"]["missingRequirements"]

    missing_adjustments_payload = StockStructureDecisionService(
        historical_ohlcv_provider=_FakeOhlcvProvider(
            {
                "AAPL": HistoricalOhlcvProviderResult.available(
                    _bars(60, adjusted=False),
                    adjustments_available=False,
                )
            }
        ),
        require_adjusted_ohlcv=True,
    ).get_structure_decision("AAPL")
    assert "missing_adjustments" in missing_adjustments_payload["historicalOhlcvReadiness"]["missingRequirements"]

    entitlement_payload = StockStructureDecisionService(
        historical_ohlcv_provider=_FakeOhlcvProvider(
            {"AAPL": HistoricalOhlcvProviderResult.unavailable("entitlement_required")}
        ),
    ).get_structure_decision("AAPL")
    assert entitlement_payload["historicalOhlcvReadiness"]["providerState"] == "entitlement_required"
    assert "entitlement_required" in entitlement_payload["historicalOhlcvReadiness"]["missingRequirements"]


def test_stock_structure_runtime_adapter_consumer_json_redacts_provider_diagnostics() -> None:
    payload = StockStructureDecisionService(
        historical_ohlcv_provider=_FakeOhlcvProvider(
            {
                "AAPL": HistoricalOhlcvProviderResult.available(
                    _bars(60),
                    metadata={
                        "providerName": "UnsafeProvider",
                        "providerClass": "UnsafeClass",
                        "requestId": "rq-secret",
                        "traceId": "trace-secret",
                        "cacheKey": "cache-secret",
                        "raw_provider_payload": {"token": "secret"},
                        "exceptionClass": "RuntimeError",
                    },
                )
            }
        )
    ).get_structure_decision("AAPL")

    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in (
        "providername",
        "providerclass",
        "providerattempted",
        "requiredproviderclass",
        "endpointhost",
        "apikeypresent",
        "exceptionclass",
        "exceptionchain",
        "requestid",
        "traceid",
        "cachekey",
        "rawpayload",
        "raw_provider_payload",
        "credential",
        "token",
        "env",
        "api_key",
        "password",
        "secret",
        "private_key",
        "traceback",
        "unsafeprovider",
        "unsafeclass",
    ):
        assert forbidden not in serialized
