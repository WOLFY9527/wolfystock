"""Explicit operator-controlled US OHLCV cache refresh service."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from data_provider.yfinance_fetcher import YfinanceFetcher
from src.services.us_ohlcv_coverage_readiness import resolve_us_ohlcv_coverage_universe
from src.services.yfinance_us_ohlcv_cache_provider import (
    DailyHistoryFetcher,
    LocalUsOhlcvParquetCache,
    UsOhlcvCache,
)
from src.utils.symbol_classification import is_us_stock_code


US_OHLCV_CACHE_REFRESH_CONTRACT_VERSION = "us_ohlcv_cache_refresh_v1"
DEFAULT_US_OHLCV_REFRESH_MAX_SYMBOLS = 5
US_OHLCV_REFRESH_WRITE_TARGET = "local_us_parquet_cache"


class UsOhlcvCacheRefreshService:
    """Plan or execute bounded US daily OHLCV cache refreshes.

    Dry-run is intentionally read-only: it reads local cache state only and does
    not call the provider fetcher or write the cache.
    """

    def __init__(
        self,
        *,
        cache: UsOhlcvCache | None = None,
        fetcher: DailyHistoryFetcher | None = None,
        env: Mapping[str, str] | None = None,
        today: date | None = None,
    ) -> None:
        self.cache = cache or LocalUsOhlcvParquetCache.from_env(env)
        self.fetcher = fetcher
        self.env = env
        self.today = today or date.today()

    def refresh(
        self,
        *,
        symbols: Sequence[str] | str | None = None,
        tier: str = "starter",
        execute: bool = False,
        max_symbols: int = DEFAULT_US_OHLCV_REFRESH_MAX_SYMBOLS,
        required_bars: int = 60,
        require_adjusted: bool = True,
    ) -> dict[str, Any]:
        requested_symbols, normalized_symbols, skipped_symbols, universe = self._resolve_target(
            symbols=symbols,
            tier=tier,
        )
        required = max(1, int(required_bars or 0))
        budget = max(1, int(max_symbols or DEFAULT_US_OHLCV_REFRESH_MAX_SYMBOLS))
        dry_run = not bool(execute)
        write_target = self._write_target()
        cache_writes_allowed = bool(execute and write_target == US_OHLCV_REFRESH_WRITE_TARGET)
        plan_items = [
            self._plan_symbol(symbol, required_bars=required, require_adjusted=require_adjusted)
            for symbol in normalized_symbols
        ]
        already_available = [
            item["symbol"]
            for item in plan_items
            if item["planState"] == "already_available"
        ]
        refresh_candidates = [
            item
            for item in plan_items
            if item["planState"] in {"missing_cache", "insufficient_history", "stale"}
        ]
        planned_provider_calls = min(budget, len(refresh_candidates))
        planned_symbols_to_write = [
            str(item.get("symbol") or "")
            for item in refresh_candidates[:planned_provider_calls]
            if item.get("writePlanned")
        ]
        planned_cache_writes = len(planned_symbols_to_write)
        results = []
        if execute:
            results.extend(
                _result(
                    str(item.get("symbol") or ""),
                    "already_available",
                    usable_bars=int(item.get("usableBars") or 0),
                )
                for item in plan_items
                if item["planState"] == "already_available"
            )
            results.extend(
                self._execute_candidates(
                    refresh_candidates,
                    cache_writes_allowed=cache_writes_allowed,
                    budget=budget,
                    required_bars=required,
                    require_adjusted=require_adjusted,
                )
            )
        symbols_written = [
            str(item.get("symbol") or "")
            for item in results
            if int(item.get("rowsWritten") or 0) > 0
        ]
        rows_written = sum(int(item.get("rowsWritten") or 0) for item in results)
        provider_calls_made = len([item for item in results if item.get("providerCalled")])
        return {
            "contractVersion": US_OHLCV_CACHE_REFRESH_CONTRACT_VERSION,
            "dryRun": dry_run,
            "execute": bool(execute),
            "target": {
                "market": "us",
                "tier": universe["tier"],
                "source": universe["source"],
                "configured": bool(universe.get("configured")),
            },
            "requestedSymbols": requested_symbols,
            "normalizedSymbols": normalized_symbols,
            "alreadyAvailableSymbols": already_available,
            "missingOrStaleSymbols": [item["symbol"] for item in refresh_candidates],
            "skippedSymbols": skipped_symbols,
            "estimatedMaxProviderCalls": planned_provider_calls,
            "plannedProviderCalls": planned_provider_calls,
            "actualProviderCallsMade": provider_calls_made,
            "plannedCacheWrites": planned_cache_writes,
            "plannedSymbolsToWrite": planned_symbols_to_write,
            "plannedRowsUnknown": planned_cache_writes > 0,
            "actualSymbolsWritten": len(symbols_written),
            "actualRowsWritten": rows_written,
            "maxSymbols": budget,
            "requiredBars": required,
            "requireAdjusted": bool(require_adjusted),
            "writeTarget": write_target,
            "refreshPolicy": {
                "explicitExecutionRequired": True,
                "dryRunDefault": True,
                "boundedByMaxSymbols": True,
                "consumerSafe": True,
            },
            "providerPolicy": {
                "liveProviderCallsAllowed": bool(execute),
                "plannedProviderCalls": planned_provider_calls,
                "actualProviderCallsMade": provider_calls_made,
                "providerCallsMade": provider_calls_made,
                "providerCallBoundary": "missing_or_stale_symbols_only",
                "consumerSafe": True,
            },
            "writePolicy": {
                "cacheWritesAllowed": cache_writes_allowed,
                "databaseWritesAllowed": False,
                "writeTarget": write_target,
                "plannedCacheWrites": planned_cache_writes,
                "plannedSymbolsToWrite": planned_symbols_to_write,
                "plannedRowsUnknown": planned_cache_writes > 0,
                "symbolsWritten": symbols_written,
                "rowsWritten": rows_written,
                "actualSymbolsWritten": len(symbols_written),
                "actualRowsWritten": rows_written,
                "consumerSafe": True,
            },
            "plan": {
                "symbols": plan_items,
                "alreadyAvailableCount": len(already_available),
                "refreshCandidateCount": len(refresh_candidates),
                "plannedProviderCalls": planned_provider_calls,
                "plannedCacheWrites": planned_cache_writes,
                "plannedSymbolsToWrite": planned_symbols_to_write,
                "writePlanSemantics": "would_write_if_execute_true",
                "skippedCount": len(skipped_symbols),
            },
            "results": results,
            "summary": self._summary(
                plan_items=plan_items,
                results=results,
                planned_provider_calls=planned_provider_calls,
                planned_cache_writes=planned_cache_writes,
                symbols_written=symbols_written,
                rows_written=rows_written,
            ),
            "consumerSafe": True,
        }

    def _resolve_target(
        self,
        *,
        symbols: Sequence[str] | str | None,
        tier: str,
    ) -> tuple[list[str], list[str], list[dict[str, str]], dict[str, Any]]:
        universe = resolve_us_ohlcv_coverage_universe(tier=tier, env=self.env)
        requested = _raw_symbol_list(symbols)
        source_symbols = requested or list(universe["symbols"])
        normalized: list[str] = []
        skipped: list[dict[str, str]] = []
        for raw in source_symbols:
            symbol = str(raw or "").strip().upper()
            if not symbol:
                continue
            if not is_us_stock_code(symbol):
                skipped.append({"symbol": symbol, "reason": "not_us_stock_symbol"})
                continue
            if symbol in normalized:
                skipped.append({"symbol": symbol, "reason": "duplicate_symbol"})
                continue
            normalized.append(symbol)
        return requested or list(source_symbols), normalized, skipped, universe

    def _plan_symbol(
        self,
        symbol: str,
        *,
        required_bars: int,
        require_adjusted: bool,
    ) -> dict[str, Any]:
        cache = self._read_cache(symbol, required_bars=required_bars)
        state = _plan_state(cache, required_bars=required_bars, require_adjusted=require_adjusted)
        return {
            "symbol": symbol,
            "planState": state,
            "cacheState": cache["cacheState"],
            "usableBars": cache["usableBars"],
            "missingBars": max(0, required_bars - int(cache["usableBars"])),
            "dateRange": cache["dateRange"],
            "freshnessState": cache["freshnessState"],
            "adjustmentState": cache["adjustmentState"],
            "providerCallPlanned": state != "already_available",
            "writePlanned": state != "already_available",
            "consumerSafe": True,
        }

    def _read_cache(self, symbol: str, *, required_bars: int) -> dict[str, Any]:
        load_result = getattr(self.cache, "load_result", None)
        try:
            if callable(load_result):
                result = load_result(symbol, days=required_bars)
                status = str(getattr(result, "status", "") or "")
                frame = _coerce_frame(getattr(result, "dataframe", None))
            else:
                loaded = self.cache.load(symbol, days=required_bars)
                frame = _coerce_frame(loaded)
                status = "hit" if frame is not None and not frame.empty else "missing"
        except Exception:
            return _cache_summary(status="failed", frame=None, today=self.today)
        return _cache_summary(status=status, frame=frame, today=self.today)

    def _execute_candidates(
        self,
        candidates: Sequence[Mapping[str, Any]],
        *,
        cache_writes_allowed: bool,
        budget: int,
        required_bars: int,
        require_adjusted: bool,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for index, item in enumerate(candidates):
            symbol = str(item.get("symbol") or "").strip().upper()
            if index >= budget:
                results.append(_result(symbol, "skipped_budget"))
                continue
            if not cache_writes_allowed:
                results.append(_result(symbol, "failed", reason="cache_write_target_not_configured"))
                continue
            results.append(
                self._refresh_symbol(
                    symbol,
                    required_bars=required_bars,
                    require_adjusted=require_adjusted,
                )
            )
        return results

    def _refresh_symbol(
        self,
        symbol: str,
        *,
        required_bars: int,
        require_adjusted: bool,
    ) -> dict[str, Any]:
        try:
            fetched = (self.fetcher or YfinanceFetcher()).get_daily_data(
                stock_code=symbol,
                start_date=None,
                end_date=None,
                days=required_bars,
            )
        except Exception:
            return _result(symbol, "provider_unavailable", provider_called=True)
        if isinstance(fetched, tuple) and fetched:
            fetched = fetched[0]
        frame = _normalize_frame(_coerce_frame(fetched))
        if frame is None or frame.empty:
            return _result(symbol, "provider_unavailable", provider_called=True)
        usable_bars = int(len(frame))
        adjustment_state = _adjustment_state(frame, require_adjusted=require_adjusted)
        if usable_bars < required_bars:
            return _result(
                symbol,
                "insufficient_history",
                provider_called=True,
                usable_bars=usable_bars,
                reason="insufficient_provider_history",
            )
        if adjustment_state == "missing":
            return _result(
                symbol,
                "insufficient_history",
                provider_called=True,
                usable_bars=usable_bars,
                reason="missing_adjusted_prices",
            )
        try:
            rows_written = int(self.cache.save(symbol, frame) or 0)
        except Exception:
            return _result(symbol, "failed", provider_called=True, usable_bars=usable_bars)
        if rows_written <= 0:
            return _result(
                symbol,
                "failed",
                provider_called=True,
                usable_bars=usable_bars,
                reason="cache_write_failed",
            )
        return _result(
            symbol,
            "refreshed",
            provider_called=True,
            usable_bars=usable_bars,
            rows_written=rows_written,
        )

    def _write_target(self) -> str:
        if not isinstance(self.cache, LocalUsOhlcvParquetCache):
            return US_OHLCV_REFRESH_WRITE_TARGET
        root_dir = getattr(self.cache, "root_dir", None)
        if isinstance(root_dir, Path):
            return US_OHLCV_REFRESH_WRITE_TARGET
        return "not_configured"

    @staticmethod
    def _summary(
        *,
        plan_items: Sequence[Mapping[str, Any]],
        results: Sequence[Mapping[str, Any]],
        planned_provider_calls: int,
        planned_cache_writes: int,
        symbols_written: Sequence[str],
        rows_written: int,
    ) -> dict[str, Any]:
        statuses = [str(item.get("status") or "") for item in results]
        provider_calls_made = len([item for item in results if item.get("providerCalled")])
        return {
            "totalSymbols": len(plan_items),
            "alreadyAvailable": len([item for item in plan_items if item.get("planState") == "already_available"]),
            "refreshCandidates": len([item for item in plan_items if item.get("planState") != "already_available"]),
            "plannedProviderCalls": int(planned_provider_calls),
            "actualProviderCallsMade": provider_calls_made,
            "plannedCacheWrites": int(planned_cache_writes),
            "refreshed": statuses.count("refreshed"),
            "providerUnavailable": statuses.count("provider_unavailable"),
            "insufficientHistory": statuses.count("insufficient_history"),
            "failed": statuses.count("failed"),
            "skippedBudget": statuses.count("skipped_budget"),
            "symbolsWritten": len(symbols_written),
            "rowsWritten": int(rows_written),
            "actualSymbolsWritten": len(symbols_written),
            "actualRowsWritten": int(rows_written),
        }


def _raw_symbol_list(value: Sequence[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = value.split(",")
    else:
        raw_values = value
    return [str(item or "").strip().upper() for item in raw_values if str(item or "").strip()]


def _cache_summary(*, status: str, frame: pd.DataFrame | None, today: date) -> dict[str, Any]:
    normalized = _normalize_frame(frame)
    if status == "hit" and normalized is not None and not normalized.empty:
        date_range = _date_range(normalized)
        return {
            "cacheState": "available",
            "usableBars": int(len(normalized)),
            "dateRange": date_range,
            "freshnessState": _freshness_state(date_range.get("end"), today),
            "adjustmentState": _adjustment_state(normalized, require_adjusted=True),
        }
    if status == "not_configured":
        state = "not_configured"
    elif status in {"failed", "invalid"}:
        state = "unavailable"
    else:
        state = "missing"
    return {
        "cacheState": state,
        "usableBars": 0,
        "dateRange": {},
        "freshnessState": "unknown",
        "adjustmentState": "missing",
    }


def _plan_state(cache: Mapping[str, Any], *, required_bars: int, require_adjusted: bool) -> str:
    cache_state = str(cache.get("cacheState") or "missing")
    usable_bars = int(cache.get("usableBars") or 0)
    if cache_state != "available":
        return "missing_cache"
    if usable_bars < required_bars:
        return "insufficient_history"
    if require_adjusted and str(cache.get("adjustmentState") or "") == "missing":
        return "insufficient_history"
    if str(cache.get("freshnessState") or "") == "stale":
        return "stale"
    return "already_available"


def _coerce_frame(value: Any) -> pd.DataFrame | None:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, Mapping) and isinstance(value.get("data"), list):
        return pd.DataFrame(value["data"])
    if isinstance(value, list):
        return pd.DataFrame(value)
    return None


def _normalize_frame(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    if frame is None or frame.empty:
        return None
    df = frame.copy()
    if "trade_date" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"trade_date": "date"})
    for candidate in ("adjusted_close", "adjustedClose", "adj_close", "Adj Close", "Adjusted Close"):
        if candidate in df.columns:
            if candidate != "adjusted_close":
                df = df.rename(columns={candidate: "adjusted_close"})
            break
    if "date" not in df.columns:
        return None
    required = {"open", "high", "low", "close"}
    if not required.issubset(set(df.columns)):
        return None
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "open", "high", "low", "close"])
    if df.empty:
        return None
    return df.sort_values("date").reset_index(drop=True)


def _date_range(frame: pd.DataFrame) -> dict[str, str]:
    dates = frame["date"].dropna()
    if dates.empty:
        return {}
    start = dates.min()
    end = dates.max()
    return {
        "start": start.date().isoformat() if hasattr(start, "date") else str(start)[:10],
        "end": end.date().isoformat() if hasattr(end, "date") else str(end)[:10],
    }


def _freshness_state(end_date: str | None, today: date) -> str:
    if not end_date:
        return "unknown"
    try:
        parsed = date.fromisoformat(str(end_date)[:10])
    except ValueError:
        return "unknown"
    return "stale" if parsed < today else "current"


def _adjustment_state(frame: pd.DataFrame | None, *, require_adjusted: bool) -> str:
    if not require_adjusted:
        return "not_required"
    if frame is None or frame.empty or "adjusted_close" not in frame.columns:
        return "missing"
    return "available" if bool(frame["adjusted_close"].notna().all()) else "missing"


def _result(
    symbol: str,
    status: str,
    *,
    provider_called: bool = False,
    usable_bars: int = 0,
    rows_written: int = 0,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "status": status,
        "providerCalled": bool(provider_called),
        "usableBars": int(usable_bars),
        "rowsWritten": int(rows_written),
        "reason": reason,
        "consumerSafe": True,
    }


__all__ = [
    "DEFAULT_US_OHLCV_REFRESH_MAX_SYMBOLS",
    "US_OHLCV_CACHE_REFRESH_CONTRACT_VERSION",
    "US_OHLCV_REFRESH_WRITE_TARGET",
    "UsOhlcvCacheRefreshService",
]
