"""Read-only US OHLCV local-cache coverage and readiness projection."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from src.services.starter_market_data import STARTER_MARKET_DATA_SYMBOLS
from src.services.us_history_helper import (
    LOCAL_US_PARQUET_SOURCE,
    get_configured_us_stock_parquet_dir,
    load_local_us_daily_history,
)
from src.utils.symbol_classification import is_us_stock_code


US_OHLCV_COVERAGE_READINESS_CONTRACT_VERSION = "us_ohlcv_coverage_readiness_v1"
US_OHLCV_TIER1_SYMBOLS_ENV = "WOLFYSTOCK_US_OHLCV_TIER1_SYMBOLS"
CURATED_US_LIQUID_TIER1_SYMBOLS: tuple[str, ...] = (
    "SPY",
    "QQQ",
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA",
    "AMZN",
    "META",
    "GOOGL",
    "AMD",
    "AVGO",
    "NFLX",
    "PLTR",
    "SOFI",
    "MU",
    "QCOM",
    "TSM",
    "ARM",
    "ORCL",
    "CRM",
    "PANW",
    "UBER",
    "SHOP",
    "SNOW",
    "COIN",
    "SMCI",
    "INTC",
    "JPM",
    "BAC",
    "WFC",
    "GS",
    "MS",
    "C",
    "XOM",
    "CVX",
    "UNH",
    "ADBE",
    "NOW",
    "CRWD",
    "ABNB",
    "PYPL",
    "SQ",
    "HOOD",
    "RBLX",
    "PFE",
    "DIS",
    "NKE",
    "KO",
    "WMT",
    "COST",
    "GE",
    "CAT",
    "BA",
    "PLUG",
    "MSTR",
    "APP",
    "TEM",
    "RDDT",
    "IWM",
    "DIA",
    "SMH",
    "XLF",
)


def resolve_us_ohlcv_coverage_universe(
    *,
    tier: str = "starter",
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return the configured US OHLCV coverage universe without touching data."""

    normalized_tier = str(tier or "starter").strip().lower()
    if normalized_tier in {"0", "tier0", "starter"}:
        return {
            "tier": "starter",
            "source": "starter_market_data_symbols",
            "configured": False,
            "symbols": list(STARTER_MARKET_DATA_SYMBOLS),
            "consumerSafe": True,
        }

    source = os.environ if env is None else env
    configured_symbols = _parse_symbol_list(source.get(US_OHLCV_TIER1_SYMBOLS_ENV))
    if configured_symbols:
        return {
            "tier": "tier1",
            "source": US_OHLCV_TIER1_SYMBOLS_ENV,
            "configured": True,
            "symbols": configured_symbols,
            "consumerSafe": True,
        }
    return {
        "tier": "tier1",
        "source": "curated_us_liquid_tier1_symbols",
        "configured": False,
        "symbols": list(CURATED_US_LIQUID_TIER1_SYMBOLS),
        "consumerSafe": True,
    }


def build_us_ohlcv_coverage_readiness(
    *,
    symbols: Sequence[str] | None = None,
    tier: str = "starter",
    parquet_dir: Path | None = None,
    required_bars: int = 60,
    today: date | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Assess local US OHLCV parquet coverage for a symbol universe.

    The function is intentionally read-only. It never executes provider calls,
    never writes cache files, and never invents missing bars.
    """

    universe = resolve_us_ohlcv_coverage_universe(tier=tier, env=env)
    normalized_symbols = _parse_symbol_list(symbols) or list(universe["symbols"])
    root_dir = parquet_dir if parquet_dir is not None else get_configured_us_stock_parquet_dir(env)
    configured = root_dir is not None
    symbol_items = [
        _build_symbol_readiness(
            symbol=symbol,
            parquet_dir=root_dir,
            required_bars=required_bars,
            configured=configured,
            today=today,
        )
        for symbol in normalized_symbols
    ]
    ready_count = sum(1 for item in symbol_items if item["overallState"] == "ready")
    partial_count = sum(1 for item in symbol_items if item["overallState"] == "insufficient_history")
    missing_count = sum(1 for item in symbol_items if item["overallState"] == "missing_cache")
    return {
        "contractVersion": US_OHLCV_COVERAGE_READINESS_CONTRACT_VERSION,
        "tier": universe["tier"],
        "universe": universe,
        "coverageState": _coverage_state(
            configured=configured,
            total=len(symbol_items),
            ready=ready_count,
            partial=partial_count,
            missing=missing_count,
        ),
        "summary": {
            "totalSymbols": len(symbol_items),
            "readySymbols": ready_count,
            "partialSymbols": partial_count,
            "missingSymbols": missing_count,
            "requiredBars": max(0, int(required_bars or 0)),
        },
        "source": {
            "sourceClass": "local_us_parquet_cache",
            "sourcePath": "configured_parquet_dir" if configured else "not_configured",
            "provider": LOCAL_US_PARQUET_SOURCE,
            "readOnly": True,
            "noExternalCalls": True,
            "providerCallsEnabled": False,
        },
        "symbols": symbol_items,
        "consumerSafe": True,
    }


def starter_us_ohlcv_coverage_symbols() -> tuple[str, ...]:
    return STARTER_MARKET_DATA_SYMBOLS


def tier1_us_ohlcv_coverage_symbols(env: Mapping[str, str] | None = None) -> tuple[str, ...]:
    return tuple(resolve_us_ohlcv_coverage_universe(tier="tier1", env=env)["symbols"])


def _build_symbol_readiness(
    *,
    symbol: str,
    parquet_dir: Path | None,
    required_bars: int,
    configured: bool,
    today: date | None,
) -> dict[str, Any]:
    normalized_symbol = str(symbol or "").strip().upper()
    required = max(0, int(required_bars or 0))
    if not configured:
        return _missing_symbol_readiness(
            symbol=normalized_symbol,
            required_bars=required,
            provider_state="not_configured",
        )

    result = load_local_us_daily_history(
        normalized_symbol,
        parquet_dir=parquet_dir,
        require_configured_dir=True,
    )
    if result.status != "hit" or result.dataframe is None:
        return _missing_symbol_readiness(
            symbol=normalized_symbol,
            required_bars=required,
            provider_state="missing",
        )

    frame = result.dataframe
    usable_bars = int(len(frame))
    missing_bars = max(0, required - usable_bars)
    date_range = _date_range(frame)
    freshness_state = _freshness_state(date_range.get("end"), today)
    if missing_bars > 0:
        overall_state = "insufficient_history"
        missing_requirements = ["insufficient_history"]
    else:
        overall_state = "ready"
        missing_requirements = []
    return {
        "symbol": normalized_symbol,
        "overallState": overall_state,
        "providerState": "available",
        "runtimeStatus": "available",
        "usableBars": usable_bars,
        "requiredBars": required,
        "missingBars": missing_bars,
        "dateRange": date_range,
        "freshnessState": freshness_state,
        "missingRequirements": missing_requirements,
        "source": "local_us_parquet_cache",
        "sufficientFor": {
            "chart": usable_bars > 0,
            "backtest": missing_bars <= 0,
            "scanner": missing_bars <= 0,
        },
        "consumerSafe": True,
    }


def _missing_symbol_readiness(
    *,
    symbol: str,
    required_bars: int,
    provider_state: str,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "overallState": "missing_cache",
        "providerState": provider_state,
        "runtimeStatus": "not_configured" if provider_state == "not_configured" else "missing",
        "usableBars": 0,
        "requiredBars": required_bars,
        "missingBars": required_bars,
        "dateRange": {},
        "freshnessState": "unknown",
        "missingRequirements": ["missing_cache", "insufficient_history"],
        "source": "local_us_parquet_cache",
        "sufficientFor": {
            "chart": False,
            "backtest": False,
            "scanner": False,
        },
        "consumerSafe": True,
    }


def _parse_symbol_list(value: Any) -> list[str]:
    if value is None:
        return []
    raw_values = value.split(",") if isinstance(value, str) else value
    if not isinstance(raw_values, Sequence) or isinstance(raw_values, (bytes, bytearray)):
        return []
    symbols: list[str] = []
    for raw in raw_values:
        symbol = str(raw or "").strip().upper()
        if not symbol or symbol in symbols or not is_us_stock_code(symbol):
            continue
        symbols.append(symbol)
    return symbols


def _date_range(frame: Any) -> dict[str, str]:
    if frame is None or frame.empty or "date" not in frame.columns:
        return {}
    dates = frame["date"].dropna()
    if dates.empty:
        return {}
    start = dates.min()
    end = dates.max()
    return {
        "start": start.date().isoformat() if hasattr(start, "date") else str(start)[:10],
        "end": end.date().isoformat() if hasattr(end, "date") else str(end)[:10],
    }


def _freshness_state(end_date: str | None, today: date | None) -> str:
    if not end_date or today is None:
        return "unknown"
    try:
        parsed = date.fromisoformat(str(end_date)[:10])
    except ValueError:
        return "unknown"
    return "stale" if parsed < today else "current"


def _coverage_state(*, configured: bool, total: int, ready: int, partial: int, missing: int) -> str:
    if not configured:
        return "not_configured"
    if total <= 0 or missing >= total:
        return "missing"
    if ready >= total:
        return "ready"
    if ready > 0 or partial > 0 or missing > 0:
        return "partial"
    return "unknown"


__all__ = [
    "CURATED_US_LIQUID_TIER1_SYMBOLS",
    "US_OHLCV_COVERAGE_READINESS_CONTRACT_VERSION",
    "US_OHLCV_TIER1_SYMBOLS_ENV",
    "build_us_ohlcv_coverage_readiness",
    "resolve_us_ohlcv_coverage_universe",
    "starter_us_ohlcv_coverage_symbols",
    "tier1_us_ohlcv_coverage_symbols",
]
