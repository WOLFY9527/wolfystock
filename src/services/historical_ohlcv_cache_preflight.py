from __future__ import annotations

import importlib.util
import os
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from typing import Any

import pandas as pd

from data_provider.base import DataFetcherManager
from src.repositories.stock_repo import StockRepository
from src.services.akshare_cn_ohlcv_cache import (
    AkshareCnOhlcvRuntime,
    RUNTIME_ENABLED_ENV as CN_RUNTIME_ENABLED_ENV,
    historical_ohlcv_runtime_enabled,
)
from src.services.yfinance_us_ohlcv_cache_provider import (
    LocalUsOhlcvParquetCache,
    YFINANCE_US_OHLCV_ENABLE_ENV,
)
from src.utils.symbol_classification import is_us_stock_code


HISTORICAL_OHLCV_CACHE_PREFLIGHT_CONTRACT_VERSION = "historical_ohlcv_cache_preflight_v1"
HISTORICAL_OHLCV_CACHE_PRELIGHT_CONTRACT_VERSION = HISTORICAL_OHLCV_CACHE_PREFLIGHT_CONTRACT_VERSION
HISTORICAL_OHLCV_CACHE_SEED_ENABLED_ENV = "WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED"
DEFAULT_CN_REPRESENTATIVE_SYMBOLS = ("600519",)
DEFAULT_US_REPRESENTATIVE_SYMBOLS = ("ORCL", "AAPL", "NVDA")
_TRUTHY = {"1", "true", "yes", "on"}
_UNSAFE_KEY_RE = re.compile(
    r"(api[_-]?key|authorization|bearer|cachekey|cookie|debug|exceptionclass|password|"
    r"private[_-]?key|providerclass|raw[_-]?(payload|request|response)|requestid|"
    r"stack[_-]?trace|token|traceback|traceid)",
    re.IGNORECASE,
)
_UNSAFE_VALUE_RE = re.compile(
    r"\b(api[-_\s]?key|authorization|bearer|cachekey|cookie|exceptionclass|"
    r"providerclass|aksharefetcher|yfinancefetcher|raw[_\s-]?(payload|request|response)|"
    r"secret|stack trace|token|traceback|traceid|requestid)\b",
    re.IGNORECASE,
)

SpecFinder = Callable[[str], object | None]


class HistoricalOhlcvCachePreflightService:
    def __init__(
        self,
        *,
        env: Mapping[str, str] | None = None,
        spec_finder: SpecFinder = importlib.util.find_spec,
        cn_repository: StockRepository | None = None,
        us_cache: Any | None = None,
        cn_fetcher_factory: Callable[[], Any] | None = None,
        us_fetcher: Any | None = None,
        today: date | None = None,
    ) -> None:
        self.env = dict(env or os.environ)
        self.spec_finder = spec_finder
        self.cn_repository = cn_repository or StockRepository()
        self.us_cache = us_cache or LocalUsOhlcvParquetCache()
        self.cn_fetcher_factory = cn_fetcher_factory or _default_cn_fetcher_factory
        self.us_fetcher = us_fetcher
        self.today = today or date.today()

    def preflight(
        self,
        *,
        symbols_by_market: Mapping[str, Sequence[str]] | None = None,
        required_bars: int = 60,
        require_adjusted: bool = True,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        return self._build_payload(
            mode="preflight",
            symbols_by_market=symbols_by_market,
            required_bars=required_bars,
            require_adjusted=require_adjusted,
            dry_run=dry_run,
        )

    def seed(
        self,
        *,
        symbols_by_market: Mapping[str, Sequence[str]] | None = None,
        required_bars: int = 60,
        require_adjusted: bool = True,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        return self._build_payload(
            mode="seed",
            symbols_by_market=symbols_by_market,
            required_bars=required_bars,
            require_adjusted=require_adjusted,
            dry_run=dry_run,
        )

    def _build_payload(
        self,
        *,
        mode: str,
        symbols_by_market: Mapping[str, Sequence[str]] | None,
        required_bars: int,
        require_adjusted: bool,
        dry_run: bool,
    ) -> dict[str, Any]:
        symbols = _normalize_symbols_by_market(symbols_by_market)
        global_runtime_enabled = historical_ohlcv_runtime_enabled(self.env)
        us_provider_enabled = _env_enabled(self.env.get(YFINANCE_US_OHLCV_ENABLE_ENV))
        runtime = {
            "cn": global_runtime_enabled,
            "us": global_runtime_enabled and us_provider_enabled,
        }
        dependencies = {
            "cn": _module_available("akshare", self.spec_finder),
            "us": _module_available("yfinance", self.spec_finder),
        }
        seed_enabled = _env_enabled(self.env.get(HISTORICAL_OHLCV_CACHE_SEED_ENABLED_ENV))
        mutation_allowed = bool(mode == "seed" and seed_enabled and not dry_run and any(runtime.values()))
        markets = {
            market: {
                "market": market,
                "runtimeEnabled": runtime[market],
                "dependencyAvailable": dependencies[market],
                "symbols": [
                    self._symbol_item(
                        mode=mode,
                        market=market,
                        symbol=symbol,
                        runtime_enabled=runtime[market],
                        dependency_available=dependencies[market],
                        seed_enabled=seed_enabled,
                        dry_run=dry_run,
                        required_bars=required_bars,
                        require_adjusted=require_adjusted,
                    )
                    for symbol in symbols[market]
                ],
            }
            for market in ("cn", "us")
        }
        return sanitize_historical_ohlcv_preflight_payload(
            {
                "contractVersion": HISTORICAL_OHLCV_CACHE_PREFLIGHT_CONTRACT_VERSION,
                "mode": mode,
                "dryRun": bool(dry_run),
                "seedEnabled": bool(seed_enabled),
                "networkCallsEnabled": mutation_allowed,
                "mutationEnabled": mutation_allowed,
                "consumerSafe": True,
                "requiredConfig": {
                    "historicalRuntimeFlag": f"{CN_RUNTIME_ENABLED_ENV}=true",
                    "cnRuntimeFlag": f"{CN_RUNTIME_ENABLED_ENV}=true",
                    "usRuntimeFlag": f"{CN_RUNTIME_ENABLED_ENV}=true; {YFINANCE_US_OHLCV_ENABLE_ENV}=true",
                    "seedFlag": f"{HISTORICAL_OHLCV_CACHE_SEED_ENABLED_ENV}=true",
                },
                "representativeSymbols": {"cn": list(symbols["cn"]), "us": list(symbols["us"])},
                "markets": markets,
            }
        )

    def _symbol_item(
        self,
        *,
        mode: str,
        market: str,
        symbol: str,
        runtime_enabled: bool,
        dependency_available: bool,
        seed_enabled: bool,
        dry_run: bool,
        required_bars: int,
        require_adjusted: bool,
    ) -> dict[str, Any]:
        runtime_state = _runtime_state(runtime_enabled, dependency_available)
        seed_state = "seed_skipped"
        cache = self._read_cache(market, symbol, required_bars, dependency_available)
        seed_report = _seed_report("not_requested", cache=cache)
        if mode == "seed":
            runtime_state, seed_state, seed_report, refresh_cache = self._seed_state(
                market=market,
                symbol=symbol,
                runtime_enabled=runtime_enabled,
                dependency_available=dependency_available,
                seed_enabled=seed_enabled,
                dry_run=dry_run,
                required_bars=required_bars,
                require_adjusted=require_adjusted,
                cache=cache,
            )
            if refresh_cache:
                cache = self._read_cache(market, symbol, required_bars, dependency_available)
        return _build_symbol_payload(
            market=market,
            symbol=symbol,
            runtime_state=runtime_state,
            seed_state=seed_state,
            cache=cache,
            seed_report=seed_report,
            required_bars=required_bars,
            require_adjusted=require_adjusted,
        )

    def _seed_state(
        self,
        *,
        market: str,
        symbol: str,
        runtime_enabled: bool,
        dependency_available: bool,
        seed_enabled: bool,
        dry_run: bool,
        required_bars: int,
        require_adjusted: bool,
        cache: Mapping[str, Any],
    ) -> tuple[str, str, dict[str, Any], bool]:
        if not _seed_allowlisted(market, symbol):
            return "symbol_not_allowlisted", "symbol_not_allowlisted", _seed_report(
                "failed_safely",
                cache=cache,
                intended_action="use_representative_symbol",
            ), False
        if not seed_enabled:
            return "seed_disabled_by_config", "seed_disabled_by_config", _seed_report(
                "disabled_by_config",
                cache=cache,
                intended_action="enable_seed_config",
            ), False
        if not runtime_enabled:
            return "disabled_by_config", "seed_skipped", _seed_report(
                "disabled_by_config",
                cache=cache,
                intended_action="enable_runtime_config",
            ), False
        if not dependency_available:
            return "dependency_missing", "seed_skipped", _seed_report(
                "dependency_missing",
                cache=cache,
                intended_action=f"install_{market}_ohlcv_dependency",
            ), False
        if _cache_satisfies_seed(cache=cache, required_bars=required_bars, require_adjusted=require_adjusted):
            return "available", "cache_hit", _seed_report("cache_hit", cache=cache), False
        if dry_run:
            return "available", "seed_skipped", _seed_report(
                "dry_run",
                cache=cache,
                intended_action=f"seed_{market}_ohlcv_cache",
            ), False
        return self._execute_seed(market, symbol, required_bars, require_adjusted)

    def _execute_seed(
        self,
        market: str,
        symbol: str,
        required_bars: int,
        require_adjusted: bool,
    ) -> tuple[str, str, dict[str, Any], bool]:
        try:
            if market == "cn":
                runtime = AkshareCnOhlcvRuntime(
                    enabled=True,
                    repository=self.cn_repository,
                    dependency_checker=lambda: True,
                    fetcher_factory=self.cn_fetcher_factory,
                    persist_cache=True,
                )
                payload = runtime.get_history_data(symbol, days=required_bars)
                if payload.get("source") == "unavailable":
                    return "runtime_unavailable", "failed_safely", _seed_report("failed_safely"), False
                rows = payload.get("data") if isinstance(payload.get("data"), list) else []
                cache_summary = _summarize_frame(
                    pd.DataFrame(rows) if rows else None,
                    dependency_available=True,
                    today=self.today,
                )
                return "available", "cache_updated", _seed_report(
                    "seeded",
                    cache=cache_summary,
                    bars_written=len(rows),
                ), True

            fetcher = self.us_fetcher or DataFetcherManager()
            payload = fetcher.get_daily_data(
                stock_code=symbol,
                start_date=None,
                end_date=None,
                days=max(1, int(required_bars)),
            )
            if isinstance(payload, tuple) and payload:
                payload = payload[0]
            frame = _coerce_frame(payload)
            if frame is None or frame.empty:
                return "runtime_unavailable", "failed_safely", _seed_report("failed_safely"), False
            rows_written = int(self.us_cache.save(symbol, frame) or 0)
            if rows_written <= 0:
                return "runtime_unavailable", "failed_safely", _seed_report("failed_safely"), False
            cache_summary = _summarize_frame(frame, dependency_available=True, today=self.today)
            return "available", "cache_updated", _seed_report(
                "seeded",
                cache=cache_summary,
                bars_written=rows_written,
            ), True
        except Exception:
            return "runtime_unavailable", "failed_safely", _seed_report("failed_safely"), False

    def _read_cache(self, market: str, symbol: str, required_bars: int, dependency_available: bool) -> dict[str, Any]:
        try:
            if market == "cn":
                rows = self.cn_repository.get_recent_daily_rows(code=symbol, limit=max(1, int(required_bars)))
                summary = _summarize_frame(_rows_to_frame(rows), dependency_available=dependency_available, today=self.today)
                if summary["cacheState"] == "cache_hit" and summary["adjustmentState"] == "missing":
                    summary["adjustmentState"] = "available"
                return summary
            return _summarize_frame(
                _coerce_frame(self.us_cache.load(symbol, days=max(1, int(required_bars)))),
                dependency_available=dependency_available,
                today=self.today,
            )
        except Exception:
            return _empty_cache_summary("cache_error", dependency_available=None)


def build_historical_ohlcv_cache_preflight(
    *,
    env: Mapping[str, str] | None = None,
    spec_finder: SpecFinder = importlib.util.find_spec,
    cn_repository: StockRepository | None = None,
    us_cache: Any | None = None,
    cn_fetcher_factory: Callable[[], Any] | None = None,
    us_fetcher: Any | None = None,
    symbols_by_market: Mapping[str, Sequence[str]] | None = None,
    required_bars: int = 60,
    require_adjusted: bool = True,
    dry_run: bool = True,
    today: date | None = None,
) -> dict[str, Any]:
    return HistoricalOhlcvCachePreflightService(
        env=env,
        spec_finder=spec_finder,
        cn_repository=cn_repository,
        us_cache=us_cache,
        cn_fetcher_factory=cn_fetcher_factory,
        us_fetcher=us_fetcher,
        today=today,
    ).preflight(
        symbols_by_market=symbols_by_market,
        required_bars=required_bars,
        require_adjusted=require_adjusted,
        dry_run=dry_run,
    )


def sanitize_historical_ohlcv_preflight_payload(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        return {
            str(key): sanitize_historical_ohlcv_preflight_payload(value)
            for key, value in payload.items()
            if not _UNSAFE_KEY_RE.search(str(key))
        }
    if isinstance(payload, list):
        return [sanitize_historical_ohlcv_preflight_payload(item) for item in payload]
    if isinstance(payload, str):
        return "<redacted>" if _UNSAFE_VALUE_RE.search(payload) else payload
    return payload


def _build_symbol_payload(
    *,
    market: str,
    symbol: str,
    runtime_state: str,
    seed_state: str,
    cache: Mapping[str, Any],
    seed_report: Mapping[str, Any],
    required_bars: int,
    require_adjusted: bool,
) -> dict[str, Any]:
    cache_state = str(cache.get("cacheState") or "cache_missing")
    cached_bars = int(cache.get("cachedBars") or 0)
    freshness_state = str(cache.get("freshnessState") or "unknown")
    adjustment_state = str(cache.get("adjustmentState") or "unknown")
    bars_written = int(seed_report.get("barsWritten") or 0)
    return {
        "market": market,
        "symbol": symbol,
        "runtimeState": runtime_state,
        "cacheState": cache_state,
        "dependencyState": cache.get("dependencyState"),
        "dependencyAvailable": cache.get("dependencyAvailable"),
        "cachedBars": cached_bars,
        "latestBarDate": cache.get("latestBarDate"),
        "freshnessState": freshness_state,
        "adjustmentState": adjustment_state,
        "dataState": _data_state(
            runtime_state=runtime_state,
            cache_state=cache_state,
            cached_bars=cached_bars,
            required_bars=required_bars,
            freshness_state=freshness_state,
            adjustment_state=adjustment_state,
            require_adjusted=require_adjusted,
        ),
        "seedState": seed_state,
        "seedResult": seed_report.get("seedResult") or "not_requested",
        "barsWritten": bars_written,
        "latestDate": seed_report.get("latestDate"),
        "freshness": seed_report.get("freshness") or "unknown",
        "adjustmentStatus": seed_report.get("adjustmentStatus") or "unknown",
        "intendedAction": seed_report.get("intendedAction"),
        "nextAction": _next_action(market, runtime_state, seed_state),
    }


def _seed_report(
    result: str,
    *,
    cache: Mapping[str, Any] | None = None,
    bars_written: int = 0,
    intended_action: str | None = None,
) -> dict[str, Any]:
    summary = dict(cache or {})
    return {
        "seedResult": _safe_seed_result(result),
        "barsWritten": max(0, int(bars_written or 0)),
        "latestDate": summary.get("latestBarDate"),
        "freshness": summary.get("freshnessState") or "unknown",
        "adjustmentStatus": summary.get("adjustmentState") or "unknown",
        "intendedAction": intended_action,
    }


def _safe_seed_result(value: str) -> str:
    normalized = str(value or "").strip().lower()
    allowed = {
        "cache_hit",
        "dependency_missing",
        "disabled_by_config",
        "dry_run",
        "failed_safely",
        "not_requested",
        "seeded",
    }
    return normalized if normalized in allowed else "failed_safely"


def _cache_satisfies_seed(
    *,
    cache: Mapping[str, Any],
    required_bars: int,
    require_adjusted: bool,
) -> bool:
    if str(cache.get("cacheState") or "") != "cache_hit":
        return False
    cached_bars = int(cache.get("cachedBars") or 0)
    if cached_bars < max(1, int(required_bars or 0)):
        return False
    return not (require_adjusted and str(cache.get("adjustmentState") or "") == "missing")


def _summarize_frame(frame: pd.DataFrame | None, *, dependency_available: bool | None, today: date) -> dict[str, Any]:
    if frame is None or frame.empty:
        return _empty_cache_summary("cache_missing", dependency_available=dependency_available)
    df = frame.copy()
    if "date" not in df.columns and "trade_date" in df.columns:
        df = df.rename(columns={"trade_date": "date"})
    if "date" not in df.columns:
        return _empty_cache_summary("cache_missing", dependency_available=dependency_available)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")
    if df.empty:
        return _empty_cache_summary("cache_missing", dependency_available=dependency_available)
    latest = df["date"].max().date()
    return {
        "cacheState": "cache_hit",
        "dependencyState": "installed" if dependency_available else "missing",
        "dependencyAvailable": bool(dependency_available),
        "cachedBars": int(len(df)),
        "latestBarDate": latest.isoformat(),
        "freshnessState": "fresh" if latest >= today else "stale",
        "adjustmentState": _adjustment_state(df),
    }


def _empty_cache_summary(cache_state: str, *, dependency_available: bool | None) -> dict[str, Any]:
    return {
        "cacheState": cache_state,
        "dependencyState": "unknown" if dependency_available is None else ("installed" if dependency_available else "missing"),
        "dependencyAvailable": None if dependency_available is None else bool(dependency_available),
        "cachedBars": 0,
        "latestBarDate": None,
        "freshnessState": "unknown",
        "adjustmentState": "unknown",
    }


def _adjustment_state(frame: pd.DataFrame) -> str:
    for column in ("adjustedClose", "adjusted_close", "adj_close"):
        if column in frame.columns:
            return "available" if bool(frame[column].notna().all()) else "missing"
    return "missing"


def _data_state(
    *,
    runtime_state: str,
    cache_state: str,
    cached_bars: int,
    required_bars: int,
    freshness_state: str,
    adjustment_state: str,
    require_adjusted: bool,
) -> str:
    if cache_state == "cache_error":
        return "runtime_unavailable"
    if runtime_state in {"dependency_missing", "runtime_unavailable", "symbol_not_allowlisted", "seed_disabled_by_config"}:
        return runtime_state if cache_state != "cache_hit" else _cache_data_state(cached_bars, required_bars, freshness_state, adjustment_state, require_adjusted)
    if cache_state != "cache_hit":
        return "cache_missing"
    return _cache_data_state(cached_bars, required_bars, freshness_state, adjustment_state, require_adjusted)


def _cache_data_state(
    cached_bars: int,
    required_bars: int,
    freshness_state: str,
    adjustment_state: str,
    require_adjusted: bool,
) -> str:
    if cached_bars < max(1, int(required_bars)):
        return "insufficient"
    if freshness_state == "stale":
        return "stale"
    if require_adjusted and adjustment_state == "missing":
        return "missing_adjustments"
    return "fresh"


def _next_action(market: str, runtime_state: str, seed_state: str) -> dict[str, Any]:
    if seed_state == "cache_updated":
        state = "cache_updated"
        summary = "Cache seed completed successfully through the existing storage abstraction."
    elif seed_state == "symbol_not_allowlisted":
        state = "symbol_not_allowlisted"
        summary = "Use the documented small representative symbol set for cache seed."
    elif seed_state == "seed_disabled_by_config":
        state = "seed_disabled_by_config"
        summary = "Enable the seed flag and the runtime flag before mutation is allowed."
    elif runtime_state == "disabled_by_config":
        state = "disabled_by_config"
        summary = "Enable the documented runtime flag before provider fetch is allowed."
    elif runtime_state == "dependency_missing":
        state = "dependency_missing"
        summary = "Install the documented optional dependency before provider fetch is allowed."
    elif runtime_state == "runtime_unavailable":
        state = "runtime_unavailable"
        summary = "Retry only after the provider runtime issue is resolved."
    else:
        state = "ready"
        summary = "Cache preflight is ready; enable seed only when operator approval allows mutation."
    return {"state": state, "summary": summary, "requiredConfig": _required_flag_text(market, include_seed=seed_state != "seed_skipped")}


def _required_flag_text(market: str, *, include_seed: bool = False) -> str:
    base = (
        f"{CN_RUNTIME_ENABLED_ENV}=true"
        if market == "cn"
        else f"{CN_RUNTIME_ENABLED_ENV}=true; {YFINANCE_US_OHLCV_ENABLE_ENV}=true"
    )
    return f"{base}; {HISTORICAL_OHLCV_CACHE_SEED_ENABLED_ENV}=true" if include_seed else base


def _runtime_state(runtime_enabled: bool, dependency_available: bool) -> str:
    if not runtime_enabled:
        return "disabled_by_config"
    if not dependency_available:
        return "dependency_missing"
    return "available"


def _normalize_symbols_by_market(symbols_by_market: Mapping[str, Sequence[str]] | None) -> dict[str, tuple[str, ...]]:
    symbols = {"cn": DEFAULT_CN_REPRESENTATIVE_SYMBOLS, "us": DEFAULT_US_REPRESENTATIVE_SYMBOLS}
    if not symbols_by_market:
        return symbols
    for market, defaults in list(symbols.items()):
        raw_values = symbols_by_market.get(market) or defaults
        normalized = tuple(dict.fromkeys(str(item or "").strip().upper() for item in raw_values if str(item or "").strip()))
        symbols[market] = tuple(item for item in normalized if market == "cn" or is_us_stock_code(item)) or defaults
    return symbols


def _rows_to_frame(rows: Sequence[Any]) -> pd.DataFrame | None:
    records = [
        {
            "date": getattr(row, "date", None),
            "open": getattr(row, "open", None),
            "high": getattr(row, "high", None),
            "low": getattr(row, "low", None),
            "close": getattr(row, "close", None),
            "volume": getattr(row, "volume", None),
            "amount": getattr(row, "amount", None),
            "pct_chg": getattr(row, "pct_chg", None),
        }
        for row in rows or ()
    ]
    return pd.DataFrame(records) if records else None


def _coerce_frame(value: Any) -> pd.DataFrame | None:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, Mapping) and isinstance(value.get("data"), list):
        return pd.DataFrame(value["data"])
    if isinstance(value, list):
        return pd.DataFrame(value)
    return None


def _seed_allowlisted(market: str, symbol: str) -> bool:
    return symbol in (DEFAULT_CN_REPRESENTATIVE_SYMBOLS if market == "cn" else DEFAULT_US_REPRESENTATIVE_SYMBOLS)


def _module_available(module_name: str, spec_finder: SpecFinder) -> bool:
    try:
        return spec_finder(module_name) is not None
    except Exception:
        return False


def _env_enabled(value: Any) -> bool:
    return str(value or "").strip().lower() in _TRUTHY


def _default_cn_fetcher_factory() -> Any:
    from data_provider.akshare_fetcher import AkshareFetcher

    return AkshareFetcher()


__all__ = [
    "DEFAULT_CN_REPRESENTATIVE_SYMBOLS",
    "DEFAULT_US_REPRESENTATIVE_SYMBOLS",
    "HISTORICAL_OHLCV_CACHE_PREFLIGHT_CONTRACT_VERSION",
    "HISTORICAL_OHLCV_CACHE_PRELIGHT_CONTRACT_VERSION",
    "HISTORICAL_OHLCV_CACHE_SEED_ENABLED_ENV",
    "HistoricalOhlcvCachePreflightService",
    "build_historical_ohlcv_cache_preflight",
    "sanitize_historical_ohlcv_preflight_payload",
]
