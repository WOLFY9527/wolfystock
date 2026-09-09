"""Shared helpers for loading locally normalized US stock history."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Mapping, Optional, Tuple, Union

import pandas as pd

from data_provider.base import DataFetcherManager
from src.portfolio_exact_numeric import (
    PortfolioExactNumericError,
    STOCK_DAILY_CLOSE_PROVENANCE_ATTR,
    attach_stock_daily_close_tokens,
    parse_portfolio_decimal,
)
from src.utils.symbol_classification import is_us_stock_code


DEFAULT_US_STOCK_PARQUET_DIR = "/root/us_test/data/normalized/us"
US_STOCK_PARQUET_ENV_KEYS = ("LOCAL_US_PARQUET_DIR", "US_STOCK_PARQUET_DIR")
LOCAL_US_PARQUET_SOURCE = "local_us_parquet"
_STOCK_DAILY_CLOSE_PROVENANCE_COLUMN = "__wolfystock_local_us_close_token"
DateLike = Union[str, date, datetime]

logger = logging.getLogger(__name__)


def has_complete_local_us_close_provenance(frame: object) -> bool:
    """Return whether every local-US close token is bound to its visible row."""

    close_tokens = getattr(frame, "attrs", {}).get(STOCK_DAILY_CLOSE_PROVENANCE_ATTR)
    if not isinstance(close_tokens, dict):
        return False
    if not {"date", "close"}.issubset(getattr(frame, "columns", ())):
        return False

    seen_dates: set[str] = set()
    for _, row in frame.iterrows():
        close = row.get("close")
        if close is None or pd.isna(close):
            return False

        row_date = pd.to_datetime(row.get("date"), errors="coerce")
        if pd.isna(row_date):
            return False
        date_key = row_date.date().isoformat()
        if date_key in seen_dates:
            return False
        seen_dates.add(date_key)

        token = close_tokens.get(date_key)
        if not isinstance(token, (Decimal, str)):
            return False
        try:
            token_value = parse_portfolio_decimal(token, kind="price", market="us")
            # Float rows are compared only; they never create or replace provenance tokens.
            visible_close = close if isinstance(close, (Decimal, int, str)) else str(close)
            visible_close_value = parse_portfolio_decimal(visible_close, kind="price", market="us")
        except PortfolioExactNumericError:
            return False
        if token_value != visible_close_value:
            return False

    return True


@dataclass(frozen=True)
class LocalUsHistoryLoadResult:
    """Normalized result for local US parquet reads."""

    stock_code: str
    path: Path
    status: str
    dataframe: Optional[pd.DataFrame] = None
    error: Optional[str] = None

    @property
    def source_name(self) -> str:
        return LOCAL_US_PARQUET_SOURCE


@dataclass(frozen=True)
class LocalUsHistoryPersistResult:
    """Result for normalized local US parquet writes."""

    stock_code: str
    path: Path
    status: str
    rows: int = 0
    error: Optional[str] = None


def get_us_stock_parquet_dir() -> Path:
    """Return the configured US parquet root.

    `LOCAL_US_PARQUET_DIR` is the primary knob for local-first backtests.
    `US_STOCK_PARQUET_DIR` remains as a compatibility fallback.
    """

    for env_key in US_STOCK_PARQUET_ENV_KEYS:
        configured = os.getenv(env_key, "").strip()
        if configured:
            return Path(configured)
    return Path(DEFAULT_US_STOCK_PARQUET_DIR)


def get_configured_us_stock_parquet_dir(env: Optional[Mapping[str, str]] = None) -> Optional[Path]:
    """Return the explicitly configured US parquet root, if any."""

    source = os.environ if env is None else env
    for env_key in US_STOCK_PARQUET_ENV_KEYS:
        configured = str(source.get(env_key, "") or "").strip()
        if configured:
            return Path(configured)
    return None


def get_local_us_history_path(stock_code: str) -> Path:
    """Return the parquet path for a US ticker."""

    return get_us_stock_parquet_dir() / f"{str(stock_code or '').upper()}.parquet"


def load_local_us_daily_history(
    stock_code: str,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: Optional[int] = None,
    parquet_dir: Optional[Path] = None,
    require_configured_dir: bool = False,
) -> LocalUsHistoryLoadResult:
    """Load normalized local US daily history for a ticker when available."""

    normalized_code = str(stock_code or "").strip().upper()
    configured_dir = parquet_dir or get_configured_us_stock_parquet_dir()
    if require_configured_dir and configured_dir is None:
        return LocalUsHistoryLoadResult(
            stock_code=normalized_code,
            path=get_local_us_history_path(normalized_code),
            status="not_configured",
        )
    root_dir = configured_dir or get_us_stock_parquet_dir()
    path = root_dir / f"{normalized_code}.parquet"
    if not normalized_code or not is_us_stock_code(normalized_code):
        return LocalUsHistoryLoadResult(
            stock_code=normalized_code,
            path=path,
            status="not_applicable",
        )

    try:
        exists = path.exists()
    except OSError as exc:
        return LocalUsHistoryLoadResult(
            stock_code=normalized_code,
            path=path,
            status="failed",
            error=str(exc),
        )

    if not exists:
        return LocalUsHistoryLoadResult(
            stock_code=normalized_code,
            path=path,
            status="missing",
        )

    try:
        raw_df = pd.read_parquet(path)
    except Exception as exc:
        return LocalUsHistoryLoadResult(
            stock_code=normalized_code,
            path=path,
            status="failed",
            error=str(exc),
        )

    normalized = _normalize_local_us_history_frame(raw_df)
    if normalized is None or normalized.empty:
        return LocalUsHistoryLoadResult(
            stock_code=normalized_code,
            path=path,
            status="invalid",
            error="missing required columns or no rows after normalization",
        )

    filtered = normalized.copy()
    if start_date:
        filtered = filtered[filtered["date"] >= pd.to_datetime(start_date)]
    if end_date:
        filtered = filtered[filtered["date"] <= pd.to_datetime(end_date)]
    if days:
        filtered = filtered.tail(max(1, int(days)))

    if filtered.empty:
        return LocalUsHistoryLoadResult(
            stock_code=normalized_code,
            path=path,
            status="invalid",
            error="no rows matched the requested date window",
        )

    result_frame = filtered.reset_index(drop=True)
    close_tokens = normalized.attrs.get(STOCK_DAILY_CLOSE_PROVENANCE_ATTR)
    if isinstance(close_tokens, dict):
        result_frame.attrs[STOCK_DAILY_CLOSE_PROVENANCE_ATTR] = close_tokens

    return LocalUsHistoryLoadResult(
        stock_code=normalized_code,
        path=path,
        status="hit",
        dataframe=result_frame,
    )


def persist_local_us_daily_history(
    stock_code: str,
    dataframe: Optional[pd.DataFrame],
    *,
    parquet_dir: Optional[Path] = None,
) -> LocalUsHistoryPersistResult:
    """Persist normalized US daily history to the existing local parquet cache."""

    normalized_code = str(stock_code or "").strip().upper()
    root_dir = parquet_dir or get_us_stock_parquet_dir()
    path = root_dir / f"{normalized_code}.parquet"
    if not normalized_code or not is_us_stock_code(normalized_code):
        return LocalUsHistoryPersistResult(
            stock_code=normalized_code,
            path=path,
            status="not_applicable",
        )
    normalized = _normalize_local_us_history_frame(dataframe)
    if normalized is None or normalized.empty:
        return LocalUsHistoryPersistResult(
            stock_code=normalized_code,
            path=path,
            status="invalid",
            error="missing required columns or no rows after normalization",
        )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        parquet_frame = normalized.copy()
        close_tokens = parquet_frame.attrs.get(STOCK_DAILY_CLOSE_PROVENANCE_ATTR)
        if isinstance(close_tokens, dict):
            parquet_frame.attrs[STOCK_DAILY_CLOSE_PROVENANCE_ATTR] = {
                date_key: format(token, "f") if isinstance(token, Decimal) else token
                for date_key, token in close_tokens.items()
            }
        parquet_frame.to_parquet(path, index=False)
    except Exception as exc:
        return LocalUsHistoryPersistResult(
            stock_code=normalized_code,
            path=path,
            status="failed",
            error=type(exc).__name__,
        )
    return LocalUsHistoryPersistResult(
        stock_code=normalized_code,
        path=path,
        status="saved",
        rows=int(len(normalized)),
    )


def fetch_daily_history_with_local_us_fallback(
    stock_code: str,
    *,
    start_date: Optional[DateLike] = None,
    end_date: Optional[DateLike] = None,
    days: Optional[int] = None,
    manager: Optional[DataFetcherManager] = None,
    log_context: str = "[daily history]",
    allow_provider_fallback: bool = True,
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Fetch daily bars with stored-first US parquet fallback semantics.

    Parameters:
        stock_code: Symbol requested by the caller.
        start_date: Optional inclusive lower date bound.
        end_date: Optional inclusive upper date bound.
        days: Optional max number of rows to keep from the tail of the window.
        manager: Optional fetch manager override for remote fallback reads.
        log_context: Short label appended to local-hit and fallback log lines.
        allow_provider_fallback: Whether to call the remote provider fallback
            when no local US parquet history is available.

    Returns:
        A tuple of ``(dataframe, source_name)``. ``dataframe`` is ``None`` when
        neither the local parquet fast path nor the fallback fetcher returns
        data. ``source_name`` is the concrete source label used for persistence.

    Example:
        >>> df, source = fetch_daily_history_with_local_us_fallback(
        ...     "AAPL",
        ...     start_date="2024-01-01",
        ...     end_date="2024-01-31",
        ...     days=20,
        ...     log_context="[rule-backtest history]",
        ... )
        >>> source in {"local_us_parquet", "yfinance", None}
        True
    """

    normalized_code = str(stock_code or "").strip().upper()
    start_date_str = _normalize_date_arg(start_date)
    end_date_str = _normalize_date_arg(end_date)

    local_history = load_local_us_daily_history(
        normalized_code,
        start_date=start_date_str,
        end_date=end_date_str,
        days=days,
    )
    if local_history.status == "hit" and local_history.dataframe is not None:
        logger.info("%s local parquet hit for %s: %s", log_context, normalized_code, local_history.path)
        return local_history.dataframe, _local_history_source_name(
            stock_code=normalized_code,
            local_history=local_history,
        )

    if local_history.status == "missing":
        logger.info("%s local parquet missing for %s: %s", log_context, normalized_code, local_history.path)
    elif local_history.status in {"invalid", "failed"}:
        logger.warning(
            "%s local parquet load failed for %s: %s (%s)",
            log_context,
            normalized_code,
            local_history.path,
            local_history.error or local_history.status,
        )

    if not allow_provider_fallback:
        logger.info("%s provider fallback disabled for %s", log_context, normalized_code)
        return None, None

    if normalized_code and is_us_stock_code(normalized_code):
        logger.info("%s API fallback for %s", log_context, normalized_code)

    fetcher = manager or DataFetcherManager()
    return fetcher.get_daily_data(
        stock_code=normalized_code,
        start_date=start_date_str,
        end_date=end_date_str,
        days=days,
    )


def _local_history_source_name(
    *,
    stock_code: str,
    local_history: LocalUsHistoryLoadResult,
) -> str:
    """Preserve a validated R06 cache as non-live qualification evidence.

    The import is intentionally local: the strict R06 context validates the
    configured local-history root and imports this module to do so.  Normal
    local cache reads remain independent of R06 and retain their source label.
    """

    from src.services.r06_nonlive_scanner_fixture import (
        R06_NONLIVE_QUALIFICATION_SOURCE,
        resolve_optional_r06_nonlive_scanner_fixture_context,
    )

    context = resolve_optional_r06_nonlive_scanner_fixture_context()
    if context is None:
        return local_history.source_name
    if (
        context.matches_symbol(stock_code)
        and local_history.path.parent.resolve() == context.cache_root
    ):
        return R06_NONLIVE_QUALIFICATION_SOURCE
    return local_history.source_name


def _normalize_local_us_history_frame(raw_df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    if raw_df is None or raw_df.empty:
        return None

    df = raw_df.copy()
    has_existing_close_tokens = STOCK_DAILY_CLOSE_PROVENANCE_ATTR in df.attrs
    existing_close_tokens = df.attrs.get(STOCK_DAILY_CLOSE_PROVENANCE_ATTR)
    df.attrs.pop(STOCK_DAILY_CLOSE_PROVENANCE_ATTR, None)
    if has_existing_close_tokens and not isinstance(existing_close_tokens, dict):
        return None
    date_column = None
    for candidate in ("trade_date", "date"):
        if candidate in df.columns:
            date_column = candidate
            break
    if date_column is None:
        return None

    required_columns = {"open", "high", "low", "close"}
    if not required_columns.issubset(set(df.columns)):
        return None

    df = df.rename(columns={date_column: "date"})
    if not has_existing_close_tokens:
        # Retain only original textual/Decimal source tokens. The shared helper
        # refuses binary-float tokens when attaching storage provenance.
        df[_STOCK_DAILY_CLOSE_PROVENANCE_COLUMN] = df["close"]
    for candidate in ("adjusted_close", "adjustedClose", "adj_close", "Adj Close", "Adjusted Close"):
        if candidate in df.columns:
            df = df.rename(columns={candidate: "adjusted_close"})
            break
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "open", "high", "low", "close"]).copy()
    if df.empty:
        return None

    df = df.sort_values("date").reset_index(drop=True)
    if "amount" not in df.columns:
        df["amount"] = None
    if "pct_chg" not in df.columns:
        df["pct_chg"] = None
    if "volume" not in df.columns:
        df["volume"] = None

    for column in ("open", "high", "low", "close", "volume", "amount", "pct_chg", "adjusted_close"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    if has_existing_close_tokens:
        raw_close_tokens = [
            existing_close_tokens.get(row_date.date().isoformat())
            for row_date in df["date"].tolist()
        ]
    else:
        raw_close_tokens = df.pop(_STOCK_DAILY_CLOSE_PROVENANCE_COLUMN).tolist()
    normalized = attach_stock_daily_close_tokens(df, raw_close_tokens)
    if (
        has_existing_close_tokens or STOCK_DAILY_CLOSE_PROVENANCE_ATTR in normalized.attrs
    ) and not has_complete_local_us_close_provenance(normalized):
        return None
    return normalized


def _normalize_date_arg(value: Optional[DateLike]) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()
