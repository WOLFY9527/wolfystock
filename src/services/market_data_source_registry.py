# -*- coding: utf-8 -*-
"""Pure provenance helpers for market data source classification."""

from __future__ import annotations

from typing import Any, Dict


CANONICAL_SOURCE_TYPES = {
    "exchange_public",
    "official_public",
    "public_proxy",
    "unofficial_proxy",
    "cache_snapshot",
    "fallback_static",
    "synthetic_fixture",
    "delayed_fixture",
    "malformed_fixture",
    "disabled_live_stub",
    "missing",
}

SOURCE_TYPE_BY_SOURCE = {
    "akshare": "public_proxy",
    "akshare_existing_baseline": "public_proxy",
    "aksharefetcher": "public_proxy",
    "alpha_vantage": "public_proxy",
    "authorized.us_etf_flow": "missing",
    "alternative": "official_public",
    "alternative_me": "official_public",
    "alpaca": "official_public",
    "ashare": "public_proxy",
    "baostock": "public_proxy",
    "binance": "exchange_public",
    "binance_public": "exchange_public",
    "binance_ws": "exchange_public",
    "builtin_stock_mapping": "fallback_static",
    "board_lookup_missing": "missing",
    "board_lookup_provider": "public_proxy",
    "cache": "cache_snapshot",
    "cached": "cache_snapshot",
    "cnn": "official_public",
    "curated_hk_liquid_seed": "fallback_static",
    "curated_us_liquid_seed": "fallback_static",
    "datafetchermanager": "public_proxy",
    "delayed_fixture": "delayed_fixture",
    "disabled_live_stub": "disabled_live_stub",
    "eastmoney": "official_public",
    "efinance": "public_proxy",
    "efinancefetcher": "public_proxy",
    "fallback": "fallback_static",
    "fixture": "synthetic_fixture",
    "finnhub": "public_proxy",
    "fred_existing_baseline": "official_public",
    "local_db": "cache_snapshot",
    "local_db_hk_history": "cache_snapshot",
    "local_db_us_history": "cache_snapshot",
    "local_history_degraded": "fallback_static",
    "local_universe_cache": "cache_snapshot",
    "local_us_parquet_dir": "cache_snapshot",
    "malformed_fixture": "malformed_fixture",
    "marketstack": "public_proxy",
    "fx_fallback": "fallback_static",
    "fx_frankfurter_public": "official_public",
    "ledger_snapshot": "cache_snapshot",
    "nasdaq_data_link": "public_proxy",
    "openbb_reference_only": "public_proxy",
    "official_or_authorized.us_market_breadth": "missing",
    "pandas_datareader_fred": "official_public",
    "pandas_datareader_oecd": "official_public",
    "pandas_datareader_stooq": "public_proxy",
    "pandas_datareader_world_bank": "official_public",
    "projection_cache": "cache_snapshot",
    "risk_diagnostics_sanitized": "cache_snapshot",
    "mock": "synthetic_fixture",
    "pytdx": "public_proxy",
    "pytdx_existing_baseline": "public_proxy",
    "pytdxfetcher": "public_proxy",
    "qstock": "public_proxy",
    "real_shaped_delayed_fixture": "delayed_fixture",
    "sec_edgar": "official_public",
    "snapshot": "cache_snapshot",
    "sina": "public_proxy",
    "tickflow": "public_proxy",
    "synthetic": "synthetic_fixture",
    "synthetic_fixture": "synthetic_fixture",
    "tickflow": "public_proxy",
    "treasury_existing_baseline": "official_public",
    "tushare_pro": "public_proxy",
    "tusharefetcher": "official_public",
    "twelve_data": "public_proxy",
    "unit_fixture": "synthetic_fixture",
    "unavailable": "missing",
    "yahoo": "unofficial_proxy",
    "yahooquery": "unofficial_proxy",
    "yfinance": "unofficial_proxy",
    "yfinance_current_baseline": "unofficial_proxy",
    "yfinance_proxy": "unofficial_proxy",
    "coinbase_public": "exchange_public",
}

SOURCE_TYPE_ALIASES = {
    "": "missing",
    "cache": "cache_snapshot",
    "cache_snapshot": "cache_snapshot",
    "cached": "cache_snapshot",
    "delayed_fixture": "delayed_fixture",
    "disabled_live_stub": "disabled_live_stub",
    "exchange_public": "exchange_public",
    "fallback": "fallback_static",
    "fallback_static": "fallback_static",
    "malformed_fixture": "malformed_fixture",
    "missing": "missing",
    "mock": "synthetic_fixture",
    "official_api": "official_public",
    "official_public": "official_public",
    "proxy_public": "public_proxy",
    "public": "public_proxy",
    "public_api": "public_proxy",
    "public_or_live": "public_proxy",
    "public_proxy": "public_proxy",
    "snapshot": "cache_snapshot",
    "synthetic": "synthetic_fixture",
    "synthetic_fixture": "synthetic_fixture",
    "unavailable": "missing",
    "unofficial_proxy": "unofficial_proxy",
    "unofficial_public_api": "unofficial_proxy",
}

SOURCE_LABEL_BY_SOURCE = {
    "akshare": "AkShare",
    "akshare_existing_baseline": "AkShare",
    "aksharefetcher": "AkShare",
    "alpha_vantage": "Alpha Vantage",
    "authorized.us_etf_flow": "未接入",
    "alternative": "Alternative.me",
    "alternative_me": "Alternative.me",
    "alpaca": "Alpaca",
    "ashare": "Ashare",
    "baostock": "BaoStock",
    "binance": "Binance",
    "binance_public": "Binance",
    "binance_ws": "Binance",
    "builtin_stock_mapping": "内置股票映射",
    "board_lookup_provider": "Board Lookup Provider",
    "cache": "缓存快照",
    "cached": "缓存快照",
    "coinbase_public": "Coinbase",
    "cnn": "CNN",
    "curated_hk_liquid_seed": "精选港股种子池",
    "curated_us_liquid_seed": "精选美股种子池",
    "datafetchermanager": "DataFetcherManager",
    "delayed_fixture": "Delayed Fixture",
    "disabled_live_stub": "Disabled Live Stub",
    "eastmoney": "东方财富",
    "efinance": "Efinance",
    "efinancefetcher": "Efinance",
    "fallback": "备用数据",
    "fixture": "Synthetic Fixture",
    "finnhub": "Finnhub",
    "fred_existing_baseline": "FRED",
    "local_db": "本地数据库历史",
    "local_db_hk_history": "本地数据库历史",
    "local_db_us_history": "本地数据库历史",
    "local_history_degraded": "本地历史降级快照",
    "local_universe_cache": "本地候选缓存",
    "local_us_parquet_dir": "本地 Parquet 历史",
    "malformed_fixture": "Malformed Fixture",
    "marketstack": "Marketstack",
    "fx_frankfurter_public": "Frankfurter",
    "mock": "模拟数据",
    "nasdaq_data_link": "Nasdaq Data Link",
    "openbb_reference_only": "OpenBB",
    "official_or_authorized.us_market_breadth": "未接入",
    "pandas_datareader_fred": "FRED",
    "pandas_datareader_oecd": "OECD",
    "pandas_datareader_stooq": "Stooq",
    "pandas_datareader_world_bank": "World Bank",
    "pytdx": "pytdx / 通达信",
    "pytdx_existing_baseline": "pytdx / 通达信",
    "pytdxfetcher": "pytdx / 通达信",
    "qstock": "QStock",
    "real_shaped_delayed_fixture": "Delayed Fixture",
    "sec_edgar": "SEC EDGAR",
    "snapshot": "缓存快照",
    "sina": "新浪财经",
    "tickflow": "TickFlow",
    "synthetic": "Synthetic Fixture",
    "synthetic_fixture": "Synthetic Fixture",
    "tickflow": "TickFlow",
    "treasury_existing_baseline": "US Treasury",
    "tushare_pro": "Tushare Pro",
    "tusharefetcher": "Tushare",
    "twelve_data": "Twelve Data",
    "unit_fixture": "Unit Fixture",
    "unavailable": "未接入",
    "yahoo": "Yahoo Finance",
    "yahooquery": "Yahoo Finance",
    "yfinance": "Yahoo Finance",
    "yfinance_current_baseline": "Yahoo Finance",
    "yfinance_proxy": "Yahoo Finance",
}

SOURCE_LABEL_BY_TYPE = {
    "cache_snapshot": "缓存快照",
    "delayed_fixture": "Delayed Fixture",
    "disabled_live_stub": "Disabled Live Stub",
    "exchange_public": "公开交易所",
    "fallback_static": "备用数据",
    "malformed_fixture": "Malformed Fixture",
    "missing": "未接入",
    "official_public": "公开数据",
    "public_proxy": "公开代理",
    "synthetic_fixture": "Synthetic Fixture",
    "unofficial_proxy": "Yahoo Finance",
}

FRESHNESS_LABELS = {
    "cached": "缓存",
    "delayed": "延迟",
    "error": "不可用",
    "fallback": "备用/缺失",
    "live": "实时",
    "mock": "模拟",
    "stale": "过期",
    "unavailable": "不可用",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def resolve_source_type(
    source: Any = None,
    *,
    source_type: Any = None,
    freshness: Any = None,
    is_fallback: bool = False,
    is_from_snapshot: bool = False,
    no_external_calls: bool = False,
) -> str:
    """Return the canonical provenance class for a market data source."""
    normalized_source = _text(source).lower()
    normalized_type = _text(source_type).lower()
    normalized_freshness = _text(freshness).lower()

    if is_from_snapshot:
        return "cache_snapshot"
    if is_fallback or normalized_freshness in {"fallback", "mock"} or normalized_source == "fallback":
        return "fallback_static"
    if normalized_source in SOURCE_TYPE_BY_SOURCE:
        return SOURCE_TYPE_BY_SOURCE[normalized_source]
    if normalized_type in SOURCE_TYPE_ALIASES:
        if normalized_source and normalized_type in {
            "official_api",
            "official_public",
            "public",
            "public_api",
            "proxy_public",
            "public_or_live",
        }:
            return "missing"
        return SOURCE_TYPE_ALIASES[normalized_type]
    if no_external_calls and normalized_freshness == "cached":
        return "cache_snapshot"
    if normalized_source or normalized_type:
        return "public_proxy"
    return "missing"


def resolve_source_label(
    source: Any = None,
    *,
    source_type: Any = None,
    source_label: Any = None,
    freshness: Any = None,
    is_fallback: bool = False,
    is_from_snapshot: bool = False,
    no_external_calls: bool = False,
) -> str:
    """Return a human-readable provenance label while preserving explicit labels."""
    explicit_label = _text(source_label)
    if explicit_label:
        return explicit_label

    normalized_source = _text(source).lower()
    resolved_type = resolve_source_type(
        source,
        source_type=source_type,
        freshness=freshness,
        is_fallback=is_fallback,
        is_from_snapshot=is_from_snapshot,
        no_external_calls=no_external_calls,
    )
    if (
        normalized_source in SOURCE_LABEL_BY_SOURCE
        and SOURCE_TYPE_BY_SOURCE.get(normalized_source) == resolved_type
    ):
        return SOURCE_LABEL_BY_SOURCE[normalized_source]
    if resolved_type in {"cache_snapshot", "fallback_static", "missing"}:
        return SOURCE_LABEL_BY_TYPE.get(resolved_type, "公开数据")
    return SOURCE_LABEL_BY_TYPE.get(resolved_type, "公开数据")


def resolve_freshness_label(
    freshness: Any,
    *,
    is_fallback: bool = False,
    is_stale: bool = False,
    source_type: Any = None,
    is_from_snapshot: bool = False,
) -> str:
    """Return a standardized freshness label for display-only provenance."""
    normalized_freshness = _text(freshness).lower()
    resolved_type = _text(source_type).lower()
    if is_fallback or normalized_freshness == "fallback" or resolved_type == "fallback_static":
        return "备用/缺失"
    if is_stale or normalized_freshness == "stale":
        return "过期"
    if resolved_type == "missing":
        return "不可用"
    if is_from_snapshot or resolved_type == "cache_snapshot":
        return "缓存快照" if normalized_freshness in {"cached", "live", ""} else FRESHNESS_LABELS.get(normalized_freshness, "缓存快照")
    return FRESHNESS_LABELS.get(normalized_freshness or "unavailable", "不可用")


def project_source_provenance(
    *,
    source: Any = None,
    source_type: Any = None,
    source_label: Any = None,
    freshness: Any = None,
    is_fallback: bool = False,
    is_stale: bool = False,
    is_from_snapshot: bool = False,
    no_external_calls: bool = False,
) -> Dict[str, str]:
    """Project canonical sourceType/sourceLabel/freshnessLabel without side effects."""
    resolved_type = resolve_source_type(
        source,
        source_type=source_type,
        freshness=freshness,
        is_fallback=is_fallback,
        is_from_snapshot=is_from_snapshot,
        no_external_calls=no_external_calls,
    )
    return {
        "sourceType": resolved_type,
        "sourceLabel": resolve_source_label(
            source,
            source_type=resolved_type,
            source_label=source_label,
            freshness=freshness,
            is_fallback=is_fallback,
            is_from_snapshot=is_from_snapshot,
            no_external_calls=no_external_calls,
        ),
        "freshnessLabel": resolve_freshness_label(
            freshness,
            is_fallback=is_fallback,
            is_stale=is_stale,
            source_type=resolved_type,
            is_from_snapshot=is_from_snapshot,
        ),
    }
