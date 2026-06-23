from __future__ import annotations

import importlib.util
import logging
import os
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime
from typing import Any

import pandas as pd

from src.repositories.stock_repo import StockRepository


logger = logging.getLogger(__name__)

AKSHARE_CN_DAILY_SOURCE = "akshare_cn_daily"
LOCAL_CN_DB_SOURCE = "local_cn_db"
RUNTIME_STATUS_CONTRACT_VERSION = "cn_daily_ohlcv_runtime_status_v1"
RUNTIME_ENABLED_ENV = "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED"

_TRUTHY = {"1", "true", "yes", "on"}
_UNAVAILABLE_SOURCE = "unavailable"


def historical_ohlcv_runtime_enabled(env: Mapping[str, str] | None = None) -> bool:
    resolved_env = env if env is not None else os.environ
    return str(resolved_env.get(RUNTIME_ENABLED_ENV) or "").strip().lower() in _TRUTHY


def is_cn_a_share_symbol(value: Any) -> bool:
    normalized = normalize_cn_a_share_symbol(value)
    return bool(normalized and normalized.isdigit() and len(normalized) == 6)


def normalize_cn_a_share_symbol(value: Any) -> str:
    candidate = str(value or "").strip().upper()
    if candidate.startswith(("SH", "SZ", "BJ")) and len(candidate) >= 8:
        candidate = candidate[2:]
    if candidate.endswith((".SH", ".SZ", ".BJ")):
        candidate = candidate.split(".", 1)[0]
    return candidate


class AkshareCnOhlcvRuntime:
    """Narrow disabled-by-default CN A-share daily OHLCV runtime."""

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        repository: StockRepository | None = None,
        dependency_checker: Callable[[], bool] | None = None,
        fetcher_factory: Callable[[], Any] | None = None,
        persist_cache: bool = True,
    ) -> None:
        self.enabled = historical_ohlcv_runtime_enabled() if enabled is None else bool(enabled)
        self.repository = repository if repository is not None else (StockRepository() if persist_cache else None)
        self.dependency_checker = dependency_checker or akshare_dependency_available
        self.fetcher_factory = fetcher_factory or _build_default_fetcher
        self.persist_cache = bool(persist_cache)

    def get_history_data(
        self,
        stock_code: str,
        period: str = "daily",
        days: int = 30,
        start_date: str | date | datetime | None = None,
        end_date: str | date | datetime | None = None,
    ) -> dict[str, Any]:
        symbol = normalize_cn_a_share_symbol(stock_code)
        requested_days = _positive_int(days, default=30)

        if period != "daily":
            return _unavailable_payload(
                symbol=symbol,
                period=period,
                requested_days=requested_days,
                status="runtime_unavailable",
                reason="unsupported_period",
            )
        if not is_cn_a_share_symbol(symbol):
            return _unavailable_payload(
                symbol=symbol,
                period=period,
                requested_days=requested_days,
                status="runtime_unavailable",
                reason="not_applicable",
            )
        if not self.enabled:
            return _unavailable_payload(
                symbol=symbol,
                period=period,
                requested_days=requested_days,
                status="disabled",
                reason="disabled_by_config",
            )

        cached = self._load_cache(symbol, requested_days)
        if cached is not None and not cached.empty:
            return _payload_from_frame(
                symbol=symbol,
                period=period,
                frame=cached,
                source=LOCAL_CN_DB_SOURCE,
                requested_days=requested_days,
                cache_hit=True,
            )

        try:
            dependency_available = bool(self.dependency_checker())
        except Exception:
            dependency_available = False
        if not dependency_available:
            return _unavailable_payload(
                symbol=symbol,
                period=period,
                requested_days=requested_days,
                status="dependency_missing",
                reason="dependency_missing",
            )

        try:
            fetcher = self.fetcher_factory()
            frame = fetcher.get_daily_data(
                stock_code=symbol,
                start_date=_date_arg(start_date),
                end_date=_date_arg(end_date),
                days=requested_days,
            )
        except Exception as exc:
            logger.warning("CN daily OHLCV runtime failed for %s: %s", symbol, type(exc).__name__)
            return _unavailable_payload(
                symbol=symbol,
                period=period,
                requested_days=requested_days,
                status="runtime_unavailable",
                reason="runtime_unavailable",
                error_type=type(exc).__name__,
            )

        normalized = _normalize_ohlcv_frame(frame, symbol)
        if normalized.empty:
            return _unavailable_payload(
                symbol=symbol,
                period=period,
                requested_days=requested_days,
                status="runtime_unavailable",
                reason="runtime_unavailable",
            )

        if self.persist_cache and self.repository is not None:
            try:
                self.repository.save_dataframe(
                    normalized.drop(columns=["adjustedClose"], errors="ignore"),
                    code=symbol,
                    data_source=AKSHARE_CN_DAILY_SOURCE,
                )
            except Exception:
                logger.warning("CN daily OHLCV cache persist skipped for %s", symbol)

        return _payload_from_frame(
            symbol=symbol,
            period=period,
            frame=normalized,
            source=AKSHARE_CN_DAILY_SOURCE,
            requested_days=requested_days,
            cache_hit=False,
        )

    def _load_cache(self, symbol: str, requested_days: int) -> pd.DataFrame | None:
        if self.repository is None:
            return None
        try:
            rows = self.repository.get_recent_daily_rows(code=symbol, limit=requested_days)
        except Exception:
            return None
        if not rows:
            return None
        records: list[dict[str, Any]] = []
        for row in reversed(list(rows)):
            record = {
                "date": getattr(row, "date", None),
                "code": symbol,
                "open": getattr(row, "open", None),
                "high": getattr(row, "high", None),
                "low": getattr(row, "low", None),
                "close": getattr(row, "close", None),
                "volume": getattr(row, "volume", None),
                "amount": getattr(row, "amount", None),
                "pct_chg": getattr(row, "pct_chg", None),
            }
            records.append(record)
        return _normalize_ohlcv_frame(pd.DataFrame(records), symbol)


def build_akshare_cn_ohlcv_runtime_status(
    *,
    enabled: bool | None = None,
    dependency_checker: Callable[[], bool] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    runtime_enabled = historical_ohlcv_runtime_enabled(env) if enabled is None else bool(enabled)
    dependency_available = False
    if runtime_enabled:
        checker = dependency_checker or akshare_dependency_available
        try:
            dependency_available = bool(checker())
        except Exception:
            return _runtime_status("runtime_unavailable", enabled=True, dependency_installed=False)
    if not runtime_enabled:
        return _runtime_status("disabled", enabled=False, dependency_installed=None)
    if not dependency_available:
        return _runtime_status("dependency_missing", enabled=True, dependency_installed=False)
    return _runtime_status("available", enabled=True, dependency_installed=True)


def akshare_dependency_available() -> bool:
    return importlib.util.find_spec("akshare") is not None


def _runtime_status(status: str, *, enabled: bool, dependency_installed: bool | None) -> dict[str, Any]:
    return {
        "contractVersion": RUNTIME_STATUS_CONTRACT_VERSION,
        "runtimeStatus": status,
        "enabled": bool(enabled),
        "dependencyInstalled": dependency_installed,
        "dailyOhlcvAvailable": status == "available",
        "externalProviderCalls": False,
        "networkCallsEnabled": bool(enabled and status == "available"),
        "consumerSafe": True,
    }


def _build_default_fetcher() -> Any:
    from data_provider.akshare_fetcher import AkshareFetcher

    return AkshareFetcher()


def _normalize_ohlcv_frame(frame: Any, symbol: str) -> pd.DataFrame:
    if frame is None:
        return pd.DataFrame()
    df = frame.copy() if isinstance(frame, pd.DataFrame) else pd.DataFrame(frame)
    if df.empty:
        return pd.DataFrame()
    rename_map = {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "成交额": "amount",
        "涨跌幅": "pct_chg",
        "adjusted_close": "adjustedClose",
        "adj_close": "adjustedClose",
    }
    df = df.rename(columns=rename_map)
    if "date" not in df.columns:
        return pd.DataFrame()
    required = {"open", "high", "low", "close", "volume"}
    if not required.issubset(set(df.columns)):
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["code"] = symbol
    for column in ("open", "high", "low", "close", "volume", "amount", "pct_chg", "adjustedClose"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=["date", "open", "high", "low", "close", "volume"]).copy()
    if df.empty:
        return pd.DataFrame()
    if "amount" not in df.columns:
        df["amount"] = None
    if "pct_chg" not in df.columns:
        df["pct_chg"] = None
    if "adjustedClose" not in df.columns:
        # AkShareFetcher currently requests qfq history; expose the adjusted
        # close only for that explicitly adjusted source path.
        df["adjustedClose"] = df["close"]
    columns = ["date", "code", "open", "high", "low", "close", "volume", "amount", "pct_chg", "adjustedClose"]
    return df[columns].sort_values("date").reset_index(drop=True)


def _payload_from_frame(
    *,
    symbol: str,
    period: str,
    frame: pd.DataFrame,
    source: str,
    requested_days: int,
    cache_hit: bool,
) -> dict[str, Any]:
    normalized = _normalize_ohlcv_frame(frame, symbol).tail(requested_days).reset_index(drop=True)
    data = [_row_payload(row) for _, row in normalized.iterrows()]
    diagnostics = {
        "status": "available",
        "reason": "cache_hit" if cache_hit else "provider_fetch_success",
        "runtimeStatus": "available",
        "source": source,
        "rows": len(data),
        "requestedDays": requested_days,
        "cacheHit": bool(cache_hit),
        "consumerSafe": True,
    }
    return {
        "stock_code": symbol,
        "period": period,
        "data": data,
        "source": source,
        "diagnostics": diagnostics,
        "sourceConfidence": _source_confidence(source, rows=len(data), requested_days=requested_days, cache_hit=cache_hit),
    }


def _unavailable_payload(
    *,
    symbol: str,
    period: str,
    requested_days: int,
    status: str,
    reason: str,
    error_type: str | None = None,
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {
        "status": status,
        "reason": reason,
        "runtimeStatus": status,
        "source": _UNAVAILABLE_SOURCE,
        "rows": 0,
        "requestedDays": requested_days,
        "cacheHit": False,
        "consumerSafe": True,
    }
    if error_type:
        diagnostics["errorType"] = _safe_error_type(error_type)
    return {
        "stock_code": symbol,
        "period": period,
        "data": [],
        "source": _UNAVAILABLE_SOURCE,
        "diagnostics": diagnostics,
        "sourceConfidence": _source_confidence(_UNAVAILABLE_SOURCE, rows=0, requested_days=requested_days, cache_hit=False),
    }


def _source_confidence(source: str, *, rows: int, requested_days: int, cache_hit: bool) -> dict[str, Any]:
    requested = max(1, int(requested_days or 1))
    if source == _UNAVAILABLE_SOURCE:
        freshness = "unavailable"
        weight = 0.0
    elif cache_hit:
        freshness = "cached"
        weight = 0.75
    else:
        freshness = "delayed"
        weight = 0.65
    return {
        "source": source,
        "sourceLabel": "Local CN daily OHLCV cache" if cache_hit else ("Unavailable daily history" if source == _UNAVAILABLE_SOURCE else "CN daily OHLCV"),
        "freshness": freshness,
        "isFallback": False,
        "isUnavailable": source == _UNAVAILABLE_SOURCE,
        "confidenceWeight": weight,
        "coverage": round(min(1.0, max(0.0, float(rows or 0) / float(requested))), 4),
        "adjustmentsAvailable": source != _UNAVAILABLE_SOURCE,
    }


def _row_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "date": _date_string(row.get("date")),
        "open": float(row.get("open")),
        "high": float(row.get("high")),
        "low": float(row.get("low")),
        "close": float(row.get("close")),
        "volume": float(row.get("volume")),
        "amount": _optional_float(row.get("amount")),
        "change_percent": _optional_float(row.get("pct_chg")),
        "adjustedClose": float(row.get("adjustedClose")),
    }


def _date_arg(value: str | date | datetime | None) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()


def _date_string(value: Any) -> str:
    if hasattr(value, "date") and callable(getattr(value, "date")):
        try:
            return value.date().isoformat()
        except Exception:
            pass
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        parsed = 0
    return parsed if parsed > 0 else int(default)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _safe_error_type(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isalnum() or ch == "_")[:80] or "RuntimeError"


__all__ = [
    "AKSHARE_CN_DAILY_SOURCE",
    "LOCAL_CN_DB_SOURCE",
    "RUNTIME_ENABLED_ENV",
    "AkshareCnOhlcvRuntime",
    "akshare_dependency_available",
    "build_akshare_cn_ohlcv_runtime_status",
    "historical_ohlcv_runtime_enabled",
    "is_cn_a_share_symbol",
    "normalize_cn_a_share_symbol",
]
