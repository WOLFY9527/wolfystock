from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

import pandas as pd

from src.services.us_ohlcv_cache_refresh import (
    US_OHLCV_CACHE_REFRESH_CONTRACT_VERSION,
    UsOhlcvCacheRefreshService,
)


def _frame(rows: int, *, start: date = date(2026, 1, 1), adjusted: bool = True) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": start + timedelta(days=index),
                "open": 100.0 + index,
                "high": 101.0 + index,
                "low": 99.0 + index,
                "close": 100.5 + index,
                "volume": 1_000_000 + index,
                "adjusted_close": 100.5 + index if adjusted else None,
            }
            for index in range(rows)
        ]
    )


class _FakeCache:
    def __init__(self, frames: dict[str, pd.DataFrame | None] | None = None) -> None:
        self.frames = {key.upper(): value for key, value in (frames or {}).items()}
        self.load_calls: list[str] = []
        self.save_calls: list[tuple[str, int]] = []

    def load_result(self, symbol: str, **_: Any) -> SimpleNamespace:
        normalized = symbol.upper()
        self.load_calls.append(normalized)
        frame = self.frames.get(normalized)
        if frame is None:
            return SimpleNamespace(status="missing", dataframe=None)
        return SimpleNamespace(status="hit", dataframe=frame.copy())

    def save(self, symbol: str, frame: pd.DataFrame) -> int:
        normalized = symbol.upper()
        rows = int(len(frame))
        self.save_calls.append((normalized, rows))
        self.frames[normalized] = frame.copy()
        return rows


class _FakeFetcher:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = {key.upper(): value for key, value in responses.items()}
        self.calls: list[str] = []

    def get_daily_data(self, *, stock_code: str, **_: Any) -> Any:
        normalized = stock_code.upper()
        self.calls.append(normalized)
        response = self.responses.get(normalized)
        if isinstance(response, Exception):
            raise response
        return response


def _by_symbol(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["symbol"]): item for item in items}


def test_dry_run_builds_refresh_plan_without_provider_calls_or_writes() -> None:
    cache = _FakeCache({"AAPL": _frame(4, start=date(2026, 1, 7))})
    fetcher = _FakeFetcher({"TSLA": _frame(4)})
    service = UsOhlcvCacheRefreshService(cache=cache, fetcher=fetcher, today=date(2026, 1, 10))

    payload = service.refresh(symbols=["aapl", "tsla", "bad!"], execute=False, required_bars=3)

    assert payload["contractVersion"] == US_OHLCV_CACHE_REFRESH_CONTRACT_VERSION
    assert payload["dryRun"] is True
    assert payload["providerPolicy"]["liveProviderCallsAllowed"] is False
    assert payload["providerPolicy"]["providerCallsMade"] == 0
    assert payload["writePolicy"]["cacheWritesAllowed"] is False
    assert payload["writePolicy"]["databaseWritesAllowed"] is False
    assert payload["writePolicy"]["rowsWritten"] == 0
    assert payload["alreadyAvailableSymbols"] == ["AAPL"]
    assert payload["missingOrStaleSymbols"] == ["TSLA"]
    assert payload["skippedSymbols"] == [{"symbol": "BAD!", "reason": "not_us_stock_symbol"}]
    assert fetcher.calls == []
    assert cache.save_calls == []


def test_execution_refreshes_only_missing_or_stale_symbols_within_budget() -> None:
    cache = _FakeCache(
        {
            "AAPL": _frame(5, start=date(2026, 1, 10)),
            "NVDA": _frame(5, start=date(2026, 1, 1)),
        }
    )
    fetcher = _FakeFetcher(
        {
            "TSLA": _frame(5, start=date(2026, 1, 10)),
            "NVDA": _frame(5, start=date(2026, 1, 10)),
            "MSFT": _frame(5, start=date(2026, 1, 10)),
        }
    )
    service = UsOhlcvCacheRefreshService(cache=cache, fetcher=fetcher, today=date(2026, 1, 14))

    payload = service.refresh(
        symbols=["AAPL", "TSLA", "NVDA", "MSFT"],
        execute=True,
        max_symbols=2,
        required_bars=5,
    )

    results = _by_symbol(payload["results"])
    assert results["AAPL"]["status"] == "already_available"
    assert results["TSLA"]["status"] == "refreshed"
    assert results["NVDA"]["status"] == "refreshed"
    assert results["MSFT"]["status"] == "skipped_budget"
    assert fetcher.calls == ["TSLA", "NVDA"]
    assert cache.save_calls == [("TSLA", 5), ("NVDA", 5)]
    assert payload["providerPolicy"]["providerCallsMade"] == 2
    assert payload["writePolicy"]["symbolsWritten"] == ["TSLA", "NVDA"]
    assert payload["writePolicy"]["rowsWritten"] == 10


def test_execution_reports_provider_failure_per_symbol_without_marking_available() -> None:
    cache = _FakeCache()
    fetcher = _FakeFetcher(
        {
            "TSLA": RuntimeError("raw provider traceback should not leak"),
            "NVDA": _frame(2, start=date(2026, 1, 10)),
        }
    )
    service = UsOhlcvCacheRefreshService(cache=cache, fetcher=fetcher, today=date(2026, 1, 14))

    payload = service.refresh(symbols=["TSLA", "NVDA"], execute=True, max_symbols=2, required_bars=5)

    results = _by_symbol(payload["results"])
    assert results["TSLA"]["status"] == "provider_unavailable"
    assert results["NVDA"]["status"] == "insufficient_history"
    assert payload["writePolicy"]["symbolsWritten"] == []
    assert payload["writePolicy"]["rowsWritten"] == 0
    assert cache.save_calls == []
    assert "traceback" not in str(payload).lower()


def test_tier1_plan_uses_configured_universe_without_provider_calls() -> None:
    cache = _FakeCache({"NVDA": _frame(5, start=date(2026, 1, 14))})
    fetcher = _FakeFetcher({"AAPL": _frame(5)})
    service = UsOhlcvCacheRefreshService(
        cache=cache,
        fetcher=fetcher,
        env={"WOLFYSTOCK_US_OHLCV_TIER1_SYMBOLS": "nvda,aapl,not-us!"},
        today=date(2026, 1, 14),
    )

    payload = service.refresh(tier="tier1", execute=False, required_bars=5)

    assert payload["target"]["tier"] == "tier1"
    assert payload["target"]["source"] == "WOLFYSTOCK_US_OHLCV_TIER1_SYMBOLS"
    assert payload["normalizedSymbols"] == ["NVDA", "AAPL"]
    assert payload["alreadyAvailableSymbols"] == ["NVDA"]
    assert payload["missingOrStaleSymbols"] == ["AAPL"]
    assert fetcher.calls == []
    assert cache.save_calls == []
