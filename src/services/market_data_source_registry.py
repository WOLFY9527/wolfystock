# -*- coding: utf-8 -*-
"""Pure provenance helpers for market data source classification."""

from __future__ import annotations

from typing import Any, Dict


CANONICAL_SOURCE_TYPES = {
    "authorized_licensed_feed",
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
    "authorized.cn_hk_connect_flow": "missing",
    "authorized.real_sector_theme_flow": "missing",
    "alternative": "official_public",
    "alternative_me": "official_public",
    "alpaca": "public_proxy",
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
    "eastmoney": "public_proxy",
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
    "local_us_parquet": "cache_snapshot",
    "local_us_parquet_dir": "cache_snapshot",
    "malformed_fixture": "malformed_fixture",
    "marketstack": "public_proxy",
    "fx_fallback": "fallback_static",
    "fx_frankfurter_public": "official_public",
    "ledger_snapshot": "cache_snapshot",
    "nasdaq_data_link": "public_proxy",
    "openbb_reference_only": "public_proxy",
    "exchange_or_broker_authorized.index_futures": "missing",
    "official_public.cn_money_market_rates": "missing",
    "official_public.fed_liquidity": "missing",
    "official_or_authorized.fx_dxy": "missing",
    "official_or_authorized.us_market_breadth": "missing",
    "polygon_us_grouped_daily": "authorized_licensed_feed",
    "pandas_datareader_fred": "official_public",
    "pandas_datareader_oecd": "official_public",
    "pandas_datareader_stooq": "public_proxy",
    "pandas_datareader_world_bank": "official_public",
    "portfolio.benchmark_return_history": "cache_snapshot",
    "portfolio.factor_risk_metrics": "cache_snapshot",
    "portfolio.fx_provenance": "cache_snapshot",
    "portfolio.price_provenance": "cache_snapshot",
    "portfolio.sector_industry_exposure": "cache_snapshot",
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
    "tusharefetcher": "public_proxy",
    "twelve_data": "public_proxy",
    "unit_fixture": "synthetic_fixture",
    "unavailable": "missing",
    "watchlist.no_score_stale_state": "missing",
    "watchlist.scanner_score_snapshot": "cache_snapshot",
    "watchlist.score_refresh_freshness": "cache_snapshot",
    "watchlist.source_confidence_preservation": "cache_snapshot",
    "options_lab.bid_ask_liquidity_gate": "missing",
    "options_lab.disabled_live_provider_stubs": "disabled_live_stub",
    "options_lab.event_calendar_candidate_evidence": "missing",
    "options_lab.expiration_calendar_candidate_evidence": "missing",
    "options_lab.iv_greeks_gate": "missing",
    "options_lab.iv_rank_candidate_evidence": "missing",
    "options_lab.iv_rank_history": "missing",
    "options_lab.oi_volume_gate": "missing",
    "options_lab.synthetic_fixture_chain": "synthetic_fixture",
    "yahoo": "unofficial_proxy",
    "yahooquery": "unofficial_proxy",
    "yfinance": "unofficial_proxy",
    "yfinance_current_baseline": "unofficial_proxy",
    "yfinance_proxy": "unofficial_proxy",
    "coinbase_public": "exchange_public",
}

SOURCE_TYPE_ALIASES = {
    "": "missing",
    "authorized_licensed_feed": "authorized_licensed_feed",
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
    "authorized.cn_hk_connect_flow": "未接入",
    "authorized.real_sector_theme_flow": "未接入",
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
    "local_us_parquet": "本地 Parquet 历史",
    "local_us_parquet_dir": "本地 Parquet 历史",
    "malformed_fixture": "Malformed Fixture",
    "marketstack": "Marketstack",
    "fx_frankfurter_public": "Frankfurter",
    "mock": "模拟数据",
    "nasdaq_data_link": "Nasdaq Data Link",
    "openbb_reference_only": "OpenBB",
    "exchange_or_broker_authorized.index_futures": "未接入",
    "official_public.cn_money_market_rates": "未接入",
    "official_public.fed_liquidity": "未接入",
    "official_or_authorized.fx_dxy": "未接入",
    "official_or_authorized.us_market_breadth": "未接入",
    "polygon_us_grouped_daily": "Polygon grouped daily US equities",
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
    "options_lab.bid_ask_liquidity_gate": "Offline Bid/Ask Liquidity Gate (no authorized live decision-grade evidence)",
    "options_lab.event_calendar_candidate_evidence": "Event Calendar Candidate Evidence (diagnostic only)",
    "options_lab.expiration_calendar_candidate_evidence": "Expiration Calendar Candidate Evidence (diagnostic only)",
    "options_lab.iv_greeks_gate": "Offline IV/Greeks Gate (no authorized live decision-grade evidence)",
    "options_lab.iv_rank_candidate_evidence": "IV Rank Candidate Evidence (diagnostic only)",
    "options_lab.oi_volume_gate": "Offline OI/Volume Gate (no authorized live decision-grade evidence)",
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
    "authorized_licensed_feed": "授权数据",
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

_OFFICIAL_CN_MONEY_MARKET_RATES_SOURCE = "official_public.cn_money_market_rates"
_OFFICIAL_CN_MONEY_MARKET_RATES_LABEL = "Official CN Money Market Rates"
_OFFICIAL_FED_LIQUIDITY_SOURCE = "official_public.fed_liquidity"
_OFFICIAL_FED_LIQUIDITY_LABEL = "Official Fed Liquidity"

SOURCE_REGISTRY_METADATA_BY_SOURCE = {
    "options_lab.event_calendar_candidate_evidence": {
        "diagnosticOnly": True,
        "candidateOnly": True,
        "surface": "event_calendar",
        "sourceType": "missing",
        "candidateSourceClass": "licensed_event_calendar_provider",
        "provenanceFamily": (
            "licensed_provider",
            "exchange",
            "issuer",
            "official_calendar",
            "approved_internal_source",
        ),
        "entitlementFamily": (
            "event_calendar_entitlement",
            "live_delayed_status",
            "environment",
            "sandbox_or_production",
            "decision_use_rights_evidence",
            "redistribution_rights",
            "audit_timestamp",
        ),
        "slaFreshnessFamily": (
            "as_of",
            "freshness",
            "max_age_policy",
            "provider_sla_status",
            "freshness_state",
            "latency_or_error_state",
        ),
        "eventTaxonomyFamily": (
            "earnings",
            "dividends",
            "ex_dividend",
            "dividends_ex_dividend",
            "splits",
            "corporate_actions",
            "macro_context_relevance",
            "fomc_macro_context_policy_scope",
        ),
        "confirmationFamily": (
            "confirmed_or_estimated",
            "announcement_status",
        ),
        "eventIdentityFamily": (
            "provider_event_id",
            "event_identity",
        ),
        "timezoneSessionFamily": (
            "event_date",
            "event_time",
            "session",
            "timezone",
        ),
        "coverageScopeFamily": (
            "symbol_or_underlying_coverage",
            "lookahead_window_or_date_range",
            "coverage_metadata",
        ),
        "forbiddenAuthorityInputs": (
            "event_presence",
            "event_count",
            "event_type",
            "timeline_evidence",
            "generic_macro_context",
            "provider_capabilities",
            "provider_capability_metadata",
            "candidate_gap_metadata",
            "source_labels",
            "provider_self_claims",
            "current_provider_id",
            "fixture",
            "synthetic",
            "fallback",
            "dry_run",
            "stub",
            "adapter_contract",
            "request_shaped_evidence",
            "proxy",
        ),
        "nextSafeStep": "document_candidate_evidence_only_without_approval",
    },
    "options_lab.expiration_calendar_candidate_evidence": {
        "diagnosticOnly": True,
        "candidateOnly": True,
        "surface": "expiration_calendar",
        "sourceType": "missing",
        "candidateSourceClass": "occ_opra_exchange_or_licensed_expiration_calendar",
        "provenanceFamily": (
            "occ",
            "opra",
            "exchange",
            "licensed_provider",
        ),
        "entitlementFamily": (
            "options_entitlement",
            "live_delayed_status",
            "environment",
            "decision_use_rights_evidence",
            "redistribution_rights",
            "audit_timestamp",
        ),
        "slaFreshnessFamily": (
            "as_of",
            "freshness",
            "max_age_policy",
            "provider_sla_status",
            "freshness_state",
            "latency_or_error_state",
        ),
        "expirationTaxonomyFamily": (
            "weekly",
            "monthly",
            "quarterly",
            "standard",
            "leaps",
            "special_expirations",
            "classification_source",
        ),
        "adjustedDeliverableCorporateActionFamily": (
            "occ_memo_or_equivalent",
            "effective_date",
            "adjusted_root_or_class",
            "deliverable_components",
            "multiplier",
            "cash_in_lieu",
            "standard_or_non_standard",
            "contract_symbol_mapping",
            "corporate_action_evidence",
        ),
        "forbiddenAuthorityInputs": (
            "coverage_completeness",
            "provider_capabilities",
            "provider_self_claims",
            "current_provider_id",
            "fixture",
            "synthetic",
            "fallback",
            "dry_run",
            "adapter_contract",
            "request_shaped_evidence",
            "proxy",
        ),
        "nextSafeStep": "document_candidate_evidence_only_without_approval",
    },
    "options_lab.iv_rank_candidate_evidence": {
        "diagnosticOnly": True,
        "candidateOnly": True,
        "surface": "iv_rank",
        "sourceType": "missing",
        "candidateSourceClass": "provider_reported_iv_rank",
        "candidateSourceClasses": (
            "provider_reported_iv_rank",
            "approved_historical_option_iv_series",
        ),
        "provenanceFamily": (
            "approved_provider",
            "licensed_source",
            "approved_internal_derived_source",
        ),
        "entitlementFamily": (
            "options_iv_history_entitlement",
            "live_delayed_status",
            "environment",
            "sandbox_or_production",
            "decision_use_rights_evidence",
            "redistribution_rights",
            "audit_timestamp",
        ),
        "slaFreshnessFamily": (
            "as_of",
            "freshness",
            "max_age_policy",
            "provider_sla_status",
            "freshness_state",
            "latency_or_error_state",
        ),
        "methodologyFamily": (
            "provider_reported_iv_rank_or_percentile",
            "deterministic_derived_iv_rank",
            "methodology_version",
            "percentile_or_rank_definition",
            "calculation_basis",
        ),
        "lookbackDateRangeFamily": (
            "lookback_window",
            "date_range_start",
            "date_range_end",
        ),
        "optionIvEvidenceFamily": (
            "approved_historical_option_iv_series_availability",
            "provider_reported_iv_rank",
            "provider_reported_iv_percentile",
        ),
        "coverageScopeFamily": (
            "symbol_or_underlying_coverage",
            "contract_universe_coverage",
            "moneyness_selection_rules",
            "expiry_selection_rules",
            "missing_data_policy",
            "coverage_metadata",
        ),
        "forbiddenAuthorityInputs": (
            "current_iv",
            "selected_contract_iv",
            "selected_contract_greeks",
            "greeks",
            "historicalIvProxy",
            "historical_iv_proxy",
            "underlying_realized_volatility",
            "realized_volatility_proxy",
            "coverage_completeness",
            "source_labels",
            "provider_capability_metadata",
            "provider_capabilities",
            "provider_self_claims",
            "current_provider_id",
            "docs_only_evidence",
            "fixture",
            "synthetic",
            "fallback",
            "dry_run",
            "stub",
            "adapter_contract",
            "request_shaped",
            "request_supplied",
            "request_shaped_evidence",
            "adapter_contract_evidence",
            "synthetic_fallback_dry_run_stub_evidence",
            "proxy",
            "candidate_gap_metadata",
        ),
        "nextSafeStep": "document_candidate_evidence_only_without_approval",
    },
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _project_registry_metadata_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _project_registry_metadata_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_project_registry_metadata_value(item) for item in value]
    if isinstance(value, list):
        return [_project_registry_metadata_value(item) for item in value]
    return value


def project_source_registry_metadata(source: Any) -> Dict[str, Any]:
    """Return inert candidate/source metadata for registry-only source ids."""
    metadata = SOURCE_REGISTRY_METADATA_BY_SOURCE.get(_text(source).lower())
    if not metadata:
        return {}
    return _project_registry_metadata_value(metadata)


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
    if _is_official_cn_money_market_cache_diagnostic(
        normalized_source,
        normalized_type,
        normalized_freshness,
        no_external_calls=no_external_calls,
    ):
        return "official_public"
    if _is_official_fed_liquidity_bundle_diagnostic(
        normalized_source,
        normalized_type,
        normalized_freshness,
        no_external_calls=no_external_calls,
    ):
        return "official_public"
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
    if normalized_source == _OFFICIAL_CN_MONEY_MARKET_RATES_SOURCE and resolved_type == "official_public":
        return _OFFICIAL_CN_MONEY_MARKET_RATES_LABEL
    if normalized_source == _OFFICIAL_FED_LIQUIDITY_SOURCE and resolved_type == "official_public":
        return _OFFICIAL_FED_LIQUIDITY_LABEL
    if resolved_type in {"cache_snapshot", "fallback_static", "missing"}:
        return SOURCE_LABEL_BY_TYPE.get(resolved_type, "公开数据")
    return SOURCE_LABEL_BY_TYPE.get(resolved_type, "公开数据")


def _is_official_cn_money_market_cache_diagnostic(
    normalized_source: str,
    normalized_type: str,
    normalized_freshness: str,
    *,
    no_external_calls: bool,
) -> bool:
    return bool(
        normalized_source == _OFFICIAL_CN_MONEY_MARKET_RATES_SOURCE
        and normalized_type == "official_public"
        and no_external_calls
        and normalized_freshness in {"cached", "delayed", "fresh"}
    )


def _is_official_fed_liquidity_bundle_diagnostic(
    normalized_source: str,
    normalized_type: str,
    normalized_freshness: str,
    *,
    no_external_calls: bool,
) -> bool:
    return bool(
        normalized_source == _OFFICIAL_FED_LIQUIDITY_SOURCE
        and normalized_type == "official_public"
        and no_external_calls
        and normalized_freshness in {"cached", "delayed", "partial", "stale", "unavailable", "fresh"}
    )


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
