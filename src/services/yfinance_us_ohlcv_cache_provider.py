"""US daily OHLCV cache provider backed by explicit yfinance runtime fetches."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

import pandas as pd

from data_provider.yfinance_fetcher import YfinanceFetcher
from src.services.historical_ohlcv_readiness import (
    HistoricalOhlcvProviderResult,
    HistoricalOhlcvReadinessRequest,
)
from src.services.us_history_helper import (
    load_local_us_daily_history,
    persist_local_us_daily_history,
)
from src.utils.symbol_classification import is_us_stock_code


YFINANCE_US_OHLCV_CACHE_SOURCE = "yfinance_us_ohlcv_cache"
YFINANCE_US_OHLCV_ENABLE_ENV = "WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED"


class UsOhlcvCache(Protocol):
    def load(
        self,
        symbol: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        days: int | None = None,
    ) -> Any:
        ...

    def save(self, symbol: str, frame: pd.DataFrame) -> int:
        ...


class DailyHistoryFetcher(Protocol):
    def get_daily_data(
        self,
        stock_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        days: int = 30,
    ) -> Any:
        ...


@dataclass
class LocalUsOhlcvParquetCache:
    """Adapter around the repository's existing LOCAL_US_PARQUET_DIR cache."""

    def load(
        self,
        symbol: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        days: int | None = None,
    ) -> pd.DataFrame | None:
        result = load_local_us_daily_history(
            symbol,
            start_date=start_date,
            end_date=end_date,
            days=days,
        )
        if result.status == "hit" and result.dataframe is not None:
            return result.dataframe
        return None

    def save(self, symbol: str, frame: pd.DataFrame) -> int:
        result = persist_local_us_daily_history(symbol, frame)
        if result.status != "saved":
            return 0
        return int(result.rows)


class YfinanceUsOhlcvCacheProvider:
    """HistoricalOhlcvProvider for local-first US yfinance daily bars.

    Provider calls are disabled by default. Cache reads remain available because
    they do not touch the network and are the expected DATA-100 evidence path.
    """

    def __init__(
        self,
        *,
        cache: UsOhlcvCache | None = None,
        fetcher: DailyHistoryFetcher | None = None,
        provider_fetch_enabled: bool | None = None,
    ) -> None:
        self.cache = cache or LocalUsOhlcvParquetCache()
        self.fetcher = fetcher
        self.provider_fetch_enabled = (
            _env_enabled(YFINANCE_US_OHLCV_ENABLE_ENV)
            if provider_fetch_enabled is None
            else bool(provider_fetch_enabled)
        )

    @classmethod
    def from_env(cls) -> "YfinanceUsOhlcvCacheProvider":
        return cls(provider_fetch_enabled=_env_enabled(YFINANCE_US_OHLCV_ENABLE_ENV))

    def fetch_ohlcv_history(
        self,
        request: HistoricalOhlcvReadinessRequest,
    ) -> HistoricalOhlcvProviderResult:
        symbol = str(request.symbol or "").strip().upper()
        if not symbol or not is_us_stock_code(symbol):
            return HistoricalOhlcvProviderResult.unavailable("provider_missing")

        start_date = _date_arg(request.start)
        end_date = _date_arg(request.end)
        days = _requested_days(request)
        cached = self._load_cache(symbol, start_date=start_date, end_date=end_date, days=days)
        if cached is not None and not cached.empty:
            return HistoricalOhlcvProviderResult.available(
                _frame_records(cached),
                adjustments_available=_adjustments_available(cached),
                freshness_state=None,
            )

        if not self.provider_fetch_enabled:
            return HistoricalOhlcvProviderResult.unavailable("provider_missing")

        try:
            fetched = self._fetch_from_provider(
                symbol,
                start_date=start_date,
                end_date=end_date,
                days=days,
            )
        except Exception:
            return HistoricalOhlcvProviderResult.unavailable("provider_unavailable")

        if fetched is None or fetched.empty:
            return HistoricalOhlcvProviderResult.unavailable("provider_unavailable")

        self._save_cache(symbol, fetched)
        return HistoricalOhlcvProviderResult.available(
            _frame_records(fetched),
            adjustments_available=_adjustments_available(fetched),
            freshness_state=None,
        )

    def _load_cache(
        self,
        symbol: str,
        *,
        start_date: str | None,
        end_date: str | None,
        days: int,
    ) -> pd.DataFrame | None:
        try:
            loaded = self.cache.load(symbol, start_date=start_date, end_date=end_date, days=days)
        except Exception:
            return None
        return _coerce_frame(loaded)

    def _fetch_from_provider(
        self,
        symbol: str,
        *,
        start_date: str | None,
        end_date: str | None,
        days: int,
    ) -> pd.DataFrame | None:
        fetcher = self.fetcher or YfinanceFetcher()
        payload = fetcher.get_daily_data(
            stock_code=symbol,
            start_date=start_date,
            end_date=end_date,
            days=days,
        )
        if isinstance(payload, tuple) and payload:
            payload = payload[0]
        return _coerce_frame(payload)

    def _save_cache(self, symbol: str, frame: pd.DataFrame) -> None:
        try:
            self.cache.save(symbol, frame)
        except Exception:
            return


def _coerce_frame(value: Any) -> pd.DataFrame | None:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, Mapping):
        data = value.get("data")
        if isinstance(data, list):
            return pd.DataFrame(data)
    if isinstance(value, list):
        return pd.DataFrame(value)
    return None


def _frame_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    df = frame.copy()
    if "trade_date" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"trade_date": "date"})
    df = _normalize_adjusted_close_column(df)
    records: list[dict[str, Any]] = []
    for row in df.to_dict("records"):
        record: dict[str, Any] = {}
        for key in (
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "adjusted_close",
        ):
            if key in row:
                value = row[key]
                if key == "date" and hasattr(value, "strftime"):
                    value = value.strftime("%Y-%m-%d")
                record[key] = value
        records.append(record)
    return records


def _adjustments_available(frame: pd.DataFrame) -> bool | None:
    normalized = _normalize_adjusted_close_column(frame)
    if "adjusted_close" in normalized.columns:
        return bool(normalized["adjusted_close"].notna().all())
    return None


def _normalize_adjusted_close_column(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    for candidate in ("adjusted_close", "adjustedClose", "adj_close", "Adj Close", "Adjusted Close"):
        if candidate in df.columns:
            if candidate != "adjusted_close":
                df = df.rename(columns={candidate: "adjusted_close"})
            break
    return df


def _requested_days(request: HistoricalOhlcvReadinessRequest) -> int:
    for value in (request.lookback_bars, request.required_bars):
        try:
            parsed = int(value or 0)
        except (TypeError, ValueError):
            parsed = 0
        if parsed > 0:
            return parsed
    return 90


def _date_arg(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _env_enabled(key: str) -> bool:
    return str(os.getenv(key) or "").strip().lower() in {"1", "true", "yes", "on"}
