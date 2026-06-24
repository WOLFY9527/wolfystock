from __future__ import annotations

import json
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

import pandas as pd

from src.services.historical_ohlcv_cache_preflight import (
    HISTORICAL_OHLCV_CACHE_SEED_ENABLED_ENV,
    HistoricalOhlcvCachePreflightService,
    sanitize_historical_ohlcv_preflight_payload,
)


class _FakeCnRepository:
    def __init__(self, rows: dict[str, list[Any]] | None = None) -> None:
        self.rows = dict(rows or {})
        self.saved: list[dict[str, Any]] = []

    def get_recent_daily_rows(self, *, code: str, limit: int) -> list[Any]:
        return list(reversed(self.rows.get(code, [])))[0:limit]

    def save_dataframe(self, df: pd.DataFrame, code: str, data_source: str = "Unknown") -> int:
        self.saved.append({"code": code, "rows": int(len(df)), "data_source": data_source})
        self.rows[code] = [
            SimpleNamespace(
                date=row["date"].date() if hasattr(row["date"], "date") else row["date"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
                amount=row.get("amount"),
                pct_chg=row.get("pct_chg"),
            )
            for row in df.to_dict("records")
        ]
        return int(len(df))


class _FakeUsCache:
    def __init__(self, frames: dict[str, pd.DataFrame] | None = None, *, error: Exception | None = None) -> None:
        self.frames = dict(frames or {})
        self.error = error
        self.load_calls: list[dict[str, Any]] = []
        self.save_calls: list[dict[str, Any]] = []

    def load(self, symbol: str, *, start_date: str | None = None, end_date: str | None = None, days: int | None = None):
        self.load_calls.append({"symbol": symbol, "start_date": start_date, "end_date": end_date, "days": days})
        if self.error is not None:
            raise self.error
        frame = self.frames.get(symbol)
        return None if frame is None else frame.tail(days).reset_index(drop=True)

    def save(self, symbol: str, frame: pd.DataFrame) -> int:
        self.save_calls.append({"symbol": symbol, "rows": int(len(frame))})
        self.frames[symbol] = frame.copy()
        return int(len(frame))


class _FakeDailyFetcher:
    def __init__(self, frame: pd.DataFrame | None = None, error: Exception | None = None) -> None:
        self.frame = frame if frame is not None else _frame(8)
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def get_daily_data(self, stock_code: str, start_date=None, end_date=None, days: int = 30):
        self.calls.append({"stock_code": stock_code, "start_date": start_date, "end_date": end_date, "days": days})
        if self.error is not None:
            raise self.error
        return self.frame.copy()


def _rows(count: int, *, start: date = date(2026, 6, 18)) -> list[Any]:
    return [
        SimpleNamespace(
            date=start + timedelta(days=index),
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.5 + index,
            volume=1000.0 + index,
            amount=100_000.0 + index,
            pct_chg=0.0,
        )
        for index in range(count)
    ]


def _frame(count: int, *, start: date = date(2026, 6, 18), adjusted: bool = True) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
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


def _spec_finder(available: set[str]):
    return lambda module_name: object() if module_name in available else None


def test_disabled_default_preflight_is_dry_run_without_provider_or_mutation() -> None:
    cn_fetcher = _FakeDailyFetcher(error=AssertionError("CN provider called"))
    us_fetcher = _FakeDailyFetcher(error=AssertionError("US provider called"))
    cn_repo = _FakeCnRepository()
    us_cache = _FakeUsCache()
    service = HistoricalOhlcvCachePreflightService(
        env={},
        spec_finder=_spec_finder({"akshare", "yfinance"}),
        cn_repository=cn_repo,
        us_cache=us_cache,
        cn_fetcher_factory=lambda: cn_fetcher,
        us_fetcher=us_fetcher,
        today=date(2026, 6, 24),
    )

    payload = service.preflight(symbols_by_market={"cn": ["600519"], "us": ["AAPL"]}, required_bars=5)

    assert payload["dryRun"] is True
    assert payload["networkCallsEnabled"] is False
    assert payload["mutationEnabled"] is False
    assert cn_fetcher.calls == []
    assert us_fetcher.calls == []
    assert cn_repo.saved == []
    assert us_cache.save_calls == []
    cn_item = payload["markets"]["cn"]["symbols"][0]
    us_item = payload["markets"]["us"]["symbols"][0]
    assert cn_item["runtimeState"] == "disabled_by_config"
    assert us_item["runtimeState"] == "disabled_by_config"
    assert cn_item["cacheState"] == "cache_missing"
    assert us_item["cacheState"] == "cache_missing"
    assert "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED=true" in cn_item["nextAction"]["requiredConfig"]
    assert "WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED=true" in us_item["nextAction"]["requiredConfig"]


def test_cache_hit_reports_bar_count_freshness_and_adjustments_without_provider_call() -> None:
    us_fetcher = _FakeDailyFetcher(error=AssertionError("provider called"))
    service = HistoricalOhlcvCachePreflightService(
        env={},
        spec_finder=_spec_finder({"akshare", "yfinance"}),
        cn_repository=_FakeCnRepository({"600519": _rows(6)}),
        us_cache=_FakeUsCache({"ORCL": _frame(6)}),
        us_fetcher=us_fetcher,
        today=date(2026, 6, 24),
    )

    payload = service.preflight(symbols_by_market={"cn": ["600519"], "us": ["ORCL"]}, required_bars=5)

    cn_item = payload["markets"]["cn"]["symbols"][0]
    us_item = payload["markets"]["us"]["symbols"][0]
    assert cn_item["cacheState"] == "cache_hit"
    assert cn_item["cachedBars"] == 5
    assert cn_item["latestBarDate"] == "2026-06-23"
    assert cn_item["freshnessState"] == "stale"
    assert cn_item["adjustmentState"] == "available"
    assert cn_item["dataState"] == "stale"
    assert us_item["cacheState"] == "cache_hit"
    assert us_item["cachedBars"] == 5
    assert us_item["latestBarDate"] == "2026-06-23"
    assert us_item["adjustmentState"] == "available"
    assert us_fetcher.calls == []


def test_dependency_missing_and_provider_exception_are_safe_states() -> None:
    missing = HistoricalOhlcvCachePreflightService(
        env={
            "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED": "true",
            HISTORICAL_OHLCV_CACHE_SEED_ENABLED_ENV: "true",
        },
        spec_finder=_spec_finder(set()),
        cn_repository=_FakeCnRepository(),
        cn_fetcher_factory=lambda: _FakeDailyFetcher(error=AssertionError("provider called")),
    ).seed(symbols_by_market={"cn": ["600519"]}, required_bars=5, dry_run=False)
    assert missing["markets"]["cn"]["symbols"][0]["runtimeState"] == "dependency_missing"

    fetcher = _FakeDailyFetcher(error=RuntimeError("AkshareFetcher token=secret rawPayload Traceback"))
    failed = HistoricalOhlcvCachePreflightService(
        env={
            "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED": "true",
            HISTORICAL_OHLCV_CACHE_SEED_ENABLED_ENV: "true",
        },
        spec_finder=_spec_finder({"akshare"}),
        cn_repository=_FakeCnRepository(),
        cn_fetcher_factory=lambda: fetcher,
    ).seed(symbols_by_market={"cn": ["600519"]}, required_bars=5, dry_run=False)
    serialized = json.dumps(failed, ensure_ascii=False).lower()

    assert fetcher.calls == [{"stock_code": "600519", "start_date": None, "end_date": None, "days": 5}]
    assert failed["markets"]["cn"]["symbols"][0]["runtimeState"] == "runtime_unavailable"
    for forbidden in ("aksharefetcher", "token", "secret", "rawpayload", "traceback", "runtimeerror"):
        assert forbidden not in serialized


def test_explicit_seed_with_fake_us_provider_writes_cache_only_when_flags_allow() -> None:
    us_cache = _FakeUsCache()
    fetcher = _FakeDailyFetcher(_frame(7))
    service = HistoricalOhlcvCachePreflightService(
        env={
            "WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED": "true",
            HISTORICAL_OHLCV_CACHE_SEED_ENABLED_ENV: "true",
        },
        spec_finder=_spec_finder({"yfinance"}),
        us_cache=us_cache,
        us_fetcher=fetcher,
        today=date(2026, 6, 24),
    )

    dry = service.seed(symbols_by_market={"us": ["NVDA"]}, required_bars=5, dry_run=True)
    live = service.seed(symbols_by_market={"us": ["NVDA"]}, required_bars=5, dry_run=False)

    assert dry["dryRun"] is True
    assert dry["networkCallsEnabled"] is False
    assert fetcher.calls == [{"stock_code": "NVDA", "start_date": None, "end_date": None, "days": 5}]
    assert us_cache.save_calls == [{"symbol": "NVDA", "rows": 7}]
    item = live["markets"]["us"]["symbols"][0]
    assert item["seedState"] == "cache_updated"
    assert item["runtimeState"] == "available"
    assert item["cachedBars"] == 5


def test_seed_requires_allowlisted_symbols_runtime_flag_and_seed_flag() -> None:
    fetcher = _FakeDailyFetcher(_frame(7))
    no_seed = HistoricalOhlcvCachePreflightService(
        env={"WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED": "true"},
        spec_finder=_spec_finder({"yfinance"}),
        us_cache=_FakeUsCache(),
        us_fetcher=fetcher,
    ).seed(symbols_by_market={"us": ["MSFT", "AAPL"]}, required_bars=5, dry_run=False)

    assert fetcher.calls == []
    assert [item["seedState"] for item in no_seed["markets"]["us"]["symbols"]] == [
        "symbol_not_allowlisted",
        "seed_disabled_by_config",
    ]


def test_recursive_redaction_removes_unsafe_admin_and_consumer_payload_fragments() -> None:
    payload = sanitize_historical_ohlcv_preflight_payload(
        {
            "safe": {
                "providerClass": "AkshareFetcher",
                "rawPayload": {"token": "secret-token", "nested": [{"traceId": "trace-secret"}]},
                "message": "RuntimeError: token=secret Traceback raw response",
                "nextAction": "Set WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED=true",
            }
        }
    )
    serialized = json.dumps(payload, ensure_ascii=False).lower()

    assert payload["safe"]["nextAction"] == "Set WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED=true"
    for forbidden in ("providerclass", "aksharefetcher", "rawpayload", "token", "secret", "traceid", "traceback"):
        assert forbidden not in serialized
