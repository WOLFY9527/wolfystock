from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import pandas as pd

from scripts.historical_ohlcv_operator_verifier import build_operator_verifier_payload, main
from src.services.historical_ohlcv_cache_preflight import (
    HISTORICAL_OHLCV_CACHE_SEED_ENABLED_ENV,
    HistoricalOhlcvCachePreflightService,
)
from src.services.historical_ohlcv_readiness import HistoricalOhlcvReadinessService
from src.services.yfinance_us_ohlcv_cache_provider import (
    YFINANCE_US_OHLCV_ENABLE_ENV,
    YfinanceUsOhlcvCacheProvider,
)


class _FakeUsCache:
    def __init__(self, frames: dict[str, pd.DataFrame] | None = None) -> None:
        self.frames = dict(frames or {})
        self.load_calls: list[dict[str, Any]] = []
        self.save_calls: list[dict[str, Any]] = []

    def load(self, symbol: str, *, start_date=None, end_date=None, days=None):
        self.load_calls.append({"symbol": symbol, "start_date": start_date, "end_date": end_date, "days": days})
        frame = self.frames.get(str(symbol).upper())
        if frame is None:
            return None
        return frame.tail(days).reset_index(drop=True) if days else frame.copy()

    def save(self, symbol: str, frame: pd.DataFrame) -> int:
        self.save_calls.append({"symbol": symbol, "rows": int(len(frame))})
        self.frames[str(symbol).upper()] = frame.copy()
        return int(len(frame))


class _FailingFetcher:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get_daily_data(self, stock_code: str, start_date=None, end_date=None, days: int = 30):
        self.calls.append({"stock_code": stock_code, "start_date": start_date, "end_date": end_date, "days": days})
        raise AssertionError("provider should not be called")


class _UnsafeService:
    def seed(self, **kwargs):
        return {
            "dryRun": True,
            "networkCallsEnabled": False,
            "mutationEnabled": False,
            "markets": {"us": {"symbols": []}},
            "rawPayload": {"token": "secret-token"},
            "providerClass": "LeakyProvider",
            "message": "Traceback requestId=abc token=secret raw response",
        }

    def preflight(self, **kwargs):
        return self.seed(**kwargs)


def _spec_finder(available: set[str]):
    return lambda module_name: object() if module_name in available else None


def _frame(count: int, *, start: date = date(2026, 5, 1), adjusted: bool = True) -> pd.DataFrame:
    rows = []
    for index in range(count):
        row = {
            "date": (start + timedelta(days=index)).isoformat(),
            "open": 100.0 + index,
            "high": 101.0 + index,
            "low": 99.0 + index,
            "close": 100.5 + index,
            "volume": 1000.0 + index,
        }
        if adjusted:
            row["adjusted_close"] = 100.5 + index
        rows.append(row)
    return pd.DataFrame(rows)


def _service(*, env: dict[str, str] | None = None, cache: _FakeUsCache | None = None, fetcher=None):
    return HistoricalOhlcvCachePreflightService(
        env=env or {},
        spec_finder=_spec_finder({"yfinance"}),
        us_cache=cache or _FakeUsCache(),
        us_fetcher=fetcher or _FailingFetcher(),
        today=date(2026, 6, 24),
    )


def test_inspect_mode_lists_gates_without_requiring_live_provider() -> None:
    payload = build_operator_verifier_payload(
        mode="inspect",
        env={},
        symbols=["SPY", "QQQ", "AAPL", "MSFT"],
        service=_service(),
    )

    assert payload["status"] == "ok"
    assert payload["mode"] == "inspect"
    assert {gate["name"] for gate in payload["envGates"]} == {
        "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED",
        "WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED",
        "WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED",
    }
    assert all(gate["valueRedacted"] is True for gate in payload["envGates"])
    assert payload["cacheLocation"]["primaryEnv"] == "LOCAL_US_PARQUET_DIR"
    assert payload["cacheLocation"]["resolvedPathExposed"] is False


def test_dry_run_does_not_mutate_cache_or_call_provider() -> None:
    cache = _FakeUsCache()
    fetcher = _FailingFetcher()
    service = _service(
        env={
            "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED": "true",
            YFINANCE_US_OHLCV_ENABLE_ENV: "true",
            HISTORICAL_OHLCV_CACHE_SEED_ENABLED_ENV: "true",
        },
        cache=cache,
        fetcher=fetcher,
    )

    payload = build_operator_verifier_payload(
        mode="dry-run",
        env=service.env,
        symbols=["SPY"],
        required_bars=5,
        service=service,
    )

    assert payload["status"] == "ok"
    assert payload["dryRun"] is True
    assert payload["networkCallsEnabled"] is False
    assert payload["mutationEnabled"] is False
    assert cache.save_calls == []
    assert fetcher.calls == []
    assert payload["preflight"]["markets"]["us"]["symbols"][0]["seedResult"] == "dry_run"


def test_execute_mode_refuses_without_explicit_flag_and_required_gates() -> None:
    service = _service()

    no_flag = build_operator_verifier_payload(
        mode="execute",
        env={},
        symbols=["AAPL"],
        service=service,
        execute=False,
    )
    no_gates = build_operator_verifier_payload(
        mode="execute",
        env={},
        symbols=["AAPL"],
        service=service,
        execute=True,
    )

    assert no_flag["status"] == "failed_closed"
    assert no_flag["reason"] == "missing_explicit_execute_flag"
    assert no_flag["networkCallsEnabled"] is False
    assert no_gates["status"] == "failed_closed"
    assert no_gates["reason"] == "required_env_gates_disabled"
    assert no_gates["missingRequiredGates"] == [
        "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED",
        "WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED",
        "WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED",
    ]


def test_verify_cache_reports_zero_bars_safely_when_cache_is_empty() -> None:
    payload = build_operator_verifier_payload(
        mode="verify-cache",
        env={},
        symbols=["SPY", "QQQ", "AAPL", "MSFT"],
        required_bars=5,
        service=_service(cache=_FakeUsCache()),
    )

    assert payload["status"] == "partial"
    assert payload["summary"] == {"symbolsChecked": 4, "cacheHitCount": 0, "zeroBarCount": 4}
    assert [row["cachedBars"] for row in payload["cacheRows"]] == [0, 0, 0, 0]
    assert payload["networkCallsEnabled"] is False
    assert payload["mutationEnabled"] is False


def test_verify_cache_reports_cache_hit_for_seeded_unadjusted_rows() -> None:
    cache = _FakeUsCache(
        {
            "SPY": _frame(60, adjusted=False),
            "QQQ": _frame(60, adjusted=False),
            "AAPL": _frame(60, adjusted=False),
            "MSFT": _frame(60, adjusted=False),
        }
    )

    payload = build_operator_verifier_payload(
        mode="verify-cache",
        env={},
        symbols=["SPY", "QQQ", "AAPL", "MSFT"],
        required_bars=60,
        service=_service(cache=cache),
    )

    assert payload["summary"]["cacheHitCount"] == 4
    assert [row["cacheState"] for row in payload["cacheRows"]] == ["cache_hit", "cache_hit", "cache_hit", "cache_hit"]
    assert [row["cachedBars"] for row in payload["cacheRows"]] == [60, 60, 60, 60]
    assert payload["networkCallsEnabled"] is False
    assert payload["mutationEnabled"] is False


def test_verify_chain_reads_cache_backed_rows_for_scanner_and_backtest_readiness() -> None:
    cache = _FakeUsCache(
        {
            "SPY": _frame(8),
            "QQQ": _frame(8),
            "AAPL": _frame(8),
            "MSFT": _frame(8),
        }
    )
    readiness_service = HistoricalOhlcvReadinessService(
        provider=YfinanceUsOhlcvCacheProvider(cache=cache, provider_fetch_enabled=False)
    )

    payload = build_operator_verifier_payload(
        mode="verify-chain",
        env={},
        symbols=["SPY", "QQQ", "AAPL", "MSFT"],
        required_bars=5,
        service=_service(cache=cache),
        readiness_service=readiness_service,
    )

    scanner = payload["scannerReadiness"]["scannerUniverseReadiness"]
    backtest = payload["backtestReadiness"]["data110"]
    assert payload["status"] == "ok"
    assert scanner["seededSymbols"] == ["SPY", "QQQ", "AAPL", "MSFT"]
    assert scanner["availableDataClasses"] == ["universe", "historical_ohlcv"]
    assert scanner["status"] == "insufficient_coverage"
    assert "quote_snapshot" in scanner["missingDataFamilies"]
    assert backtest["status"] == "available"
    assert backtest["executable"] is True
    assert backtest["adjustedDataRequirement"] == {"required": True, "state": "available"}
    assert backtest["symbolBarsAvailable"] == 5
    assert backtest["benchmarkReadiness"]["availableBarCount"] == 5
    assert backtest["benchmarkReadiness"]["adjustmentState"] == "available"
    assert cache.save_calls == []


def test_verify_chain_reports_seeded_but_degraded_when_adjustments_are_missing() -> None:
    cache = _FakeUsCache(
        {
            "SPY": _frame(60, adjusted=False),
            "QQQ": _frame(60, adjusted=False),
            "AAPL": _frame(60, adjusted=False),
            "MSFT": _frame(60, adjusted=False),
        }
    )
    readiness_service = HistoricalOhlcvReadinessService(
        provider=YfinanceUsOhlcvCacheProvider(cache=cache, provider_fetch_enabled=False)
    )

    payload = build_operator_verifier_payload(
        mode="verify-chain",
        env={},
        symbols=["SPY", "QQQ", "AAPL", "MSFT"],
        required_bars=60,
        service=_service(cache=cache),
        readiness_service=readiness_service,
    )

    scanner_summary = payload["scannerReadiness"]["historicalOhlcvSummary"]
    scanner = payload["scannerReadiness"]["scannerUniverseReadiness"]
    backtest = payload["backtestReadiness"]["data110"]
    serialized = json.dumps(payload, ensure_ascii=False).lower()

    assert payload["status"] == "partial"
    assert payload["scannerReadiness"]["cacheBackedSymbolCount"] == 4
    assert scanner_summary["usableBars"] == 60
    assert scanner_summary["missingBars"] == 0
    assert scanner_summary["overallState"] == "degraded"
    assert "missing_adjustments" in scanner_summary["missingRequirements"]
    assert scanner["seededSymbols"] == ["SPY", "QQQ", "AAPL", "MSFT"]
    assert scanner["eligibleSymbols"] == []
    assert scanner["blockedSymbols"] == ["SPY", "QQQ", "AAPL", "MSFT"]
    assert scanner["availableDataClasses"] == ["universe", "historical_ohlcv"]
    assert "historical_ohlcv" not in scanner["missingDataFamilies"]
    assert "quote_snapshot" in scanner["missingDataFamilies"]
    assert "adjusted_prices" in scanner["missingDataFamilies"]
    assert "cache-backed historical ohlcv rows exist" in scanner["nextOperatorAction"].lower()
    assert "quote snapshot" in scanner["nextOperatorAction"].lower()
    assert "adjusted" in scanner["nextOperatorAction"].lower()

    assert backtest["symbolBarsAvailable"] == 60
    assert backtest["benchmarkBarsAvailable"] == 60
    assert backtest["executable"] is False
    assert backtest["adjustedDataRequirement"] == {"required": True, "state": "missing"}
    assert backtest["blockedExecutionReason"] == "adjusted_prices_missing"
    assert "adjusted_prices" in backtest["missingDataFamilies"]
    assert "historical_ohlcv" not in backtest["missingDataFamilies"]
    assert "adjusted" in backtest["nextOperatorAction"].lower()
    assert "seed or refresh local cache rows" not in serialized
    assert "requestid" not in serialized
    assert "traceid" not in serialized
    assert "cachekey" not in serialized


def test_redaction_removes_raw_provider_secret_debug_and_trace_fragments() -> None:
    payload = build_operator_verifier_payload(
        mode="dry-run",
        env={},
        symbols=["SPY"],
        service=_UnsafeService(),  # type: ignore[arg-type]
    )
    serialized = json.dumps(payload, ensure_ascii=False).lower()

    for forbidden in (
        "rawpayload",
        "leakyprovider",
        "secret-token",
        "traceback",
        "requestid",
        "token=secret",
        "raw response",
    ):
        assert forbidden not in serialized


def test_cli_execute_without_execute_flag_exits_failed_closed(capsys) -> None:
    exit_code = main(["--mode", "execute", "--us-symbols", "AAPL", "--required-bars", "5"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 2
    assert payload["status"] == "failed_closed"
    assert payload["reason"] == "missing_explicit_execute_flag"
