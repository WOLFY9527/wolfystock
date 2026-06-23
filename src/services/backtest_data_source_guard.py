# -*- coding: utf-8 -*-
"""Pure backtest data-source eligibility guard helpers."""

from __future__ import annotations

from dataclasses import dataclass

from src.services.data_source_router import DataSourceRoutePlan, DataSourceRouteRequest, DataSourceRouter
from src.services.market_data_source_registry import resolve_source_type
from src.utils.symbol_classification import is_us_index_code, is_us_stock_code
from src.utils.symbol_normalization import normalize_stock_code


_LOCAL_AUTHORITY_SOURCES = frozenset(
    {
        "database_cache",
        "local_db",
        "local_db_hk_history",
        "local_db_us_history",
        "local_ohlcv",
        "akshare_cn_daily",
        "local_us_parquet",
        "local_us_parquet_dir",
        "snapshot",
        "cache",
        "cached",
    }
)
_LOCAL_AUTHORITY_SOURCE_ALIASES = {
    "databasecache": "database_cache",
    "database-cache": "database_cache",
    "database cache": "database_cache",
}
_UNKNOWN_AUTHORITY_SOURCES = frozenset({"unknown", "missing"})
_UNKNOWN_AUTHORITY_REASON_CODE = "source_authority_unknown"
_PROXY_FILL_ONLY_PROVIDERS = frozenset(
    {
        "yahoo_yfinance",
        "yahooquery",
        "yfinance",
        "yfinance_current_baseline",
        "yfinance_proxy",
    }
)
_SOURCE_PROVIDER_ALIASES = {
    "cache": "local_cache",
    "cached": "local_cache",
    "database_cache": "local_cache",
    "local_db": "local_cache",
    "local_db_hk_history": "local_cache",
    "local_db_us_history": "local_cache",
    "local_ohlcv": "local_ohlcv",
    "akshare_cn_daily": "local_ohlcv",
    "local_us_parquet": "local_ohlcv",
    "local_us_parquet_dir": "local_ohlcv",
    "snapshot": "local_cache",
    "yahoo": "yfinance_current_baseline",
    "yfinance": "yfinance_current_baseline",
    "yfinance_proxy": "yfinance_current_baseline",
}


@dataclass(frozen=True, slots=True)
class BacktestDataSourceEligibility:
    request: DataSourceRouteRequest
    plan: DataSourceRoutePlan
    source: str | None
    provider_id: str | None
    source_type: str
    authority_status: str
    authority_allowed: bool
    degraded_fill_only: bool
    rejected: bool
    reason_codes: tuple[str, ...]


def assess_backtest_data_source_eligibility(
    *,
    code: str,
    source: str | None = None,
    allow_network: bool = False,
    scoring_allowed: bool = True,
) -> BacktestDataSourceEligibility:
    request = _build_backtest_route_request(
        code=code,
        allow_network=allow_network,
        scoring_allowed=scoring_allowed,
    )
    plan = DataSourceRouter.resolve(request)
    normalized_source = str(source or "").strip()
    authority_source = _normalize_backtest_source_authority(normalized_source)
    provider_id = _resolve_provider_id(authority_source)
    source_type = _resolve_backtest_source_type(authority_source)

    if not normalized_source or authority_source in _UNKNOWN_AUTHORITY_SOURCES:
        return BacktestDataSourceEligibility(
            request=request,
            plan=plan,
            source=normalized_source or None,
            provider_id=provider_id,
            source_type=source_type,
            authority_status="degraded_fill_only",
            authority_allowed=False,
            degraded_fill_only=True,
            rejected=False,
            reason_codes=(_UNKNOWN_AUTHORITY_REASON_CODE,),
        )

    if authority_source in _LOCAL_AUTHORITY_SOURCES or source_type == "cache_snapshot":
        return BacktestDataSourceEligibility(
            request=request,
            plan=plan,
            source=normalized_source,
            provider_id=provider_id,
            source_type="cache_snapshot",
            authority_status="allowed",
            authority_allowed=True,
            degraded_fill_only=False,
            rejected=False,
            reason_codes=(),
        )

    forbidden_codes = tuple(plan.reason_codes.get(provider_id or "", ()))
    if provider_id in {"sec_edgar", "coinbase_public", "baostock"}:
        return BacktestDataSourceEligibility(
            request=request,
            plan=plan,
            source=normalized_source,
            provider_id=provider_id,
            source_type=source_type,
            authority_status="rejected",
            authority_allowed=False,
            degraded_fill_only=False,
            rejected=True,
            reason_codes=forbidden_codes or ("provider_forbidden_for_use_case",),
        )

    if provider_id in _PROXY_FILL_ONLY_PROVIDERS or source_type in {"public_proxy", "unofficial_proxy", "fallback_static"}:
        return BacktestDataSourceEligibility(
            request=request,
            plan=plan,
            source=normalized_source,
            provider_id=provider_id,
            source_type=source_type,
            authority_status="degraded_fill_only",
            authority_allowed=False,
            degraded_fill_only=True,
            rejected=False,
            reason_codes=("proxy_source_not_reproducible",),
        )

    if forbidden_codes:
        return BacktestDataSourceEligibility(
            request=request,
            plan=plan,
            source=normalized_source,
            provider_id=provider_id,
            source_type=source_type,
            authority_status="rejected",
            authority_allowed=False,
            degraded_fill_only=False,
            rejected=True,
            reason_codes=forbidden_codes,
        )

    return BacktestDataSourceEligibility(
        request=request,
        plan=plan,
        source=normalized_source,
        provider_id=provider_id,
        source_type=source_type,
        authority_status="degraded_fill_only",
        authority_allowed=False,
        degraded_fill_only=True,
        rejected=False,
        reason_codes=("source_not_reproducible_for_backtest",),
    )


def _build_backtest_route_request(
    *,
    code: str,
    allow_network: bool,
    scoring_allowed: bool,
) -> DataSourceRouteRequest:
    normalized_code = normalize_stock_code(str(code or "").strip()).upper()
    market = "global"
    asset_type = "equity"
    capability = "ohlcv"
    product_id = None

    if is_us_index_code(normalized_code):
        market = "US"
        asset_type = "equity_index"
    elif is_us_stock_code(normalized_code):
        market = "US"
        asset_type = "equity"
    elif normalized_code.isdigit() and len(normalized_code) == 6:
        market = "CN"
        asset_type = "equity"
        capability = "cn_history_daily"
    elif normalized_code.startswith("HK") and normalized_code[2:].isdigit():
        market = "HK"
        asset_type = "equity"
    elif "-" in normalized_code:
        market = "crypto"
        asset_type = "crypto"
        product_id = normalized_code

    return DataSourceRouteRequest(
        market=market,
        asset_type=asset_type,
        use_case="backtest",
        capability=capability,
        freshness_need="cached",
        scoring_allowed=scoring_allowed,
        symbol=None if product_id else normalized_code,
        product_id=product_id,
        allow_network=allow_network,
        reproducibility_required=True,
    )


def _resolve_provider_id(source: str) -> str | None:
    normalized = str(source or "").strip().lower()
    if not normalized:
        return None
    return _SOURCE_PROVIDER_ALIASES.get(normalized, normalized)


def _normalize_backtest_source_authority(source: str) -> str:
    normalized = str(source or "").strip().lower()
    if not normalized:
        return normalized
    return _LOCAL_AUTHORITY_SOURCE_ALIASES.get(normalized, normalized)


def _resolve_backtest_source_type(source: str) -> str:
    normalized = _normalize_backtest_source_authority(source)
    if not normalized or normalized in _UNKNOWN_AUTHORITY_SOURCES:
        return "missing"
    if normalized in _LOCAL_AUTHORITY_SOURCES:
        return "cache_snapshot"
    return resolve_source_type(source=normalized)


__all__ = [
    "BacktestDataSourceEligibility",
    "assess_backtest_data_source_eligibility",
]
