# -*- coding: utf-8 -*-
"""Pure data source routing policy foundation.

This module is metadata and policy only. It must not import provider SDKs,
touch DataFetcherManager, read env or secrets, call networks, or mutate any
runtime routing order. The router produces eligibility plans only.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from src.services.market_data_source_registry import resolve_source_type
from src.services.provider_capability_matrix import (
    ProviderDomain,
    ProviderMarket,
    get_provider_capability,
    get_provider_capability_support_contract,
    get_provider_dry_run_probe_contract,
    get_provider_fit_metadata,
    get_provider_scoring_contract,
    is_provider_allowed_for_backtest,
    providers_for_domain,
)


_LIVE_FRESHNESS_VALUES = frozenset({"fresh", "live", "realtime"})
_PROXY_SOURCE_TYPES = frozenset({"public_proxy", "unofficial_proxy"})
_LOCAL_SOURCE_TYPE_BY_PROVIDER = MappingProxyType(
    {
        "local_cache": "cache_snapshot",
        "local_ohlcv": "cache_snapshot",
        "local_news_cache": "cache_snapshot",
        "local_inference": "cache_snapshot",
    }
)
_LOCAL_TRUST_LEVEL_BY_PROVIDER = MappingProxyType(
    {
        "local_cache": "reproducible_local_or_stored",
        "local_ohlcv": "reproducible_local_or_stored",
        "local_news_cache": "reproducible_local_or_stored",
        "local_inference": "reproducible_local_or_stored",
    }
)
_LOCAL_SOURCE_TIER_BY_PROVIDER = MappingProxyType(
    {
        "local_cache": "local_cache",
        "local_ohlcv": "local_store",
        "local_news_cache": "local_cache",
        "local_inference": "local_derived",
    }
)
_LOCAL_FRESHNESS_EXPECTATION_BY_PROVIDER = MappingProxyType(
    {
        "local_cache": "cache_or_snapshot",
        "local_ohlcv": "stored_ohlcv_snapshot",
        "local_news_cache": "cache_or_snapshot",
        "local_inference": "local_derived_from_stored_text",
    }
)
_MARKET_ALIASES = MappingProxyType(
    {
        "us": ProviderMarket.US,
        "cn": ProviderMarket.CN,
        "hk": ProviderMarket.HK,
        "crypto": ProviderMarket.CRYPTO,
        "forex": ProviderMarket.FOREX,
        "global": ProviderMarket.GLOBAL,
    }
)
_BACKTEST_DOMAIN_BY_CAPABILITY = MappingProxyType(
    {
        "ohlcv": ProviderDomain.OHLCV,
        "cn_history_daily": ProviderDomain.OHLCV,
        "cn_index_history_daily": ProviderDomain.OHLCV,
        "news": ProviderDomain.NEWS,
        "sentiment": ProviderDomain.SENTIMENT,
    }
)
_MARKET_INTELLIGENCE_AUTHORITY_FORBIDDEN_PROVIDER_IDS = (
    "coinbase_public",
    "akshare",
    "baostock",
    "pytdx_existing_baseline",
    "sec_edgar",
    "yfinance_current_baseline",
    "yahooquery",
)
_MARKET_INTELLIGENCE_AUTHORITY_REQUIRED_SOURCE_TYPES = (
    "official_public",
    "exchange_public",
    "cache_snapshot",
)
_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS = (
    "binance_public",
    "coinbase_public",
    "yfinance_current_baseline",
    "yahooquery",
    "akshare",
    "baostock",
    "pytdx_existing_baseline",
)
_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES = (
    "cache_required",
    "missing_provider_configuration",
    "authorization_required",
    "freshness_floor_required",
    "coverage_floor_required",
)
_OFFICIAL_LIQUIDITY_FORBIDDEN_PROVIDER_IDS = (
    "coinbase_public",
    "yfinance_current_baseline",
    "yahooquery",
    "akshare",
    "baostock",
    "pytdx_existing_baseline",
    "sec_edgar",
)
_FED_LIQUIDITY_PLAN_REASON_CODES = (
    "cache_required",
    "missing_provider_configuration",
    "release_schedule_required",
    "release_lag_expected",
    "freshness_floor_required",
    "coverage_floor_required",
)
_DXY_AUTHORITY_PLAN_REASON_CODES = (
    "cache_required",
    "missing_provider_configuration",
    "authorization_required",
    "session_market_hours_required",
    "freshness_floor_required",
    "coverage_floor_required",
)
_CN_MONEY_MARKET_PLAN_REASON_CODES = (
    "cache_required",
    "missing_provider_configuration",
    "session_calendar_required",
    "holiday_calendar_required",
    "freshness_floor_required",
    "coverage_floor_required",
)
_CN_HK_CONNECT_FLOW_PLAN_REASON_CODES = (
    "cache_required",
    "missing_provider_configuration",
    "authorization_required",
    "session_calendar_required",
    "coverage_floor_required",
)
_INDEX_FUTURES_PLAN_REASON_CODES = (
    "cache_required",
    "missing_provider_configuration",
    "authorization_required",
    "extended_hours_session_required",
    "freshness_floor_required",
    "coverage_floor_required",
)
_ROTATION_REAL_FLOW_PLAN_REASON_CODES = (
    "cache_required",
    "missing_provider_configuration",
    "authorization_required",
    "taxonomy_to_real_flow_mapping_required",
    "freshness_floor_required",
    "coverage_floor_required",
)
_LEGACY_CAPABILITY_ALIAS_PLAN_REASON_CODES = (
    "legacy_capability_alias_rejected",
    "canonical_capability_required",
)


def _text(value: str | None) -> str:
    return str(value or "").strip()


def _optional_text(value: str | None) -> str | None:
    text = _text(value)
    return text or None


def _normalize(value: str | None) -> str:
    return _text(value).lower()


def _unique_preserving_order(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)


@dataclass(frozen=True, slots=True)
class DataSourceRouteRequest:
    market: str
    asset_type: str
    use_case: str
    capability: str
    freshness_need: str
    scoring_allowed: bool
    symbol: str | None = None
    product_id: str | None = None
    cik: str | None = None
    as_of: str | None = None
    allow_network: bool = True
    reproducibility_required: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "market", _text(self.market))
        object.__setattr__(self, "asset_type", _text(self.asset_type))
        object.__setattr__(self, "use_case", _text(self.use_case))
        object.__setattr__(self, "capability", _text(self.capability))
        object.__setattr__(self, "freshness_need", _text(self.freshness_need))
        object.__setattr__(self, "symbol", _optional_text(self.symbol))
        object.__setattr__(self, "product_id", _optional_text(self.product_id))
        object.__setattr__(self, "cik", _optional_text(self.cik))
        object.__setattr__(self, "as_of", _optional_text(self.as_of))
        for field_name in ("market", "asset_type", "use_case", "capability", "freshness_need"):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} is required")


@dataclass(frozen=True, slots=True)
class ProviderRouteCandidate:
    provider_id: str
    provider_name: str
    capability: str
    source_type: str
    source_tier: str
    trust_level: str
    freshness_expectation: str
    observation_only: bool
    score_contribution_allowed: bool
    paid_data_likely_required: bool = False
    key_required: bool = False
    enabled_by_default: bool = False
    no_default_live_http_calls: bool = True
    missing_provider_reason: str | None = None


@dataclass(frozen=True, slots=True)
class DataSourceRoutePlan:
    primary_candidates: tuple[ProviderRouteCandidate, ...]
    observation_candidates: tuple[ProviderRouteCandidate, ...]
    forbidden_providers: tuple[ProviderRouteCandidate, ...]
    cache_required: bool
    background_refresh_required: bool
    score_contribution_allowed: bool
    degradation_policy: str
    required_source_types: tuple[str, ...]
    freshness_floor: str
    trust_floor: str
    reason_codes: Mapping[str, tuple[str, ...]]
    required_symbols: tuple[str, ...] = ()
    session: str | None = None


@dataclass(frozen=True, slots=True)
class _RoutePolicy:
    primary_provider_ids: tuple[str, ...] = ()
    observation_provider_ids: tuple[str, ...] = ()
    forbidden_provider_ids: tuple[str, ...] = ()
    cache_required: bool = True
    background_refresh_required: bool = True
    score_contribution_allowed: bool = False
    degradation_policy: str = "cache_then_explicit_unavailable"
    required_source_types: tuple[str, ...] = ("cache_snapshot",)
    freshness_floor: str = "delayed"
    trust_floor: str = "observation_only"
    required_symbols: tuple[str, ...] = ()
    session: str | None = None
    plan_reason_codes: tuple[str, ...] = ()


_ROUTE_POLICIES = MappingProxyType(
    {
        ("stock_evidence", "companyfacts"): _RoutePolicy(
            primary_provider_ids=("sec_edgar",),
            forbidden_provider_ids=("baostock", "coinbase_public", "yfinance_current_baseline"),
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="use_cached_evidence_or_explicit_unavailable",
            required_source_types=("official_public", "cache_snapshot"),
            freshness_floor="daily",
            trust_floor="filings_evidence",
            plan_reason_codes=("cache_required",),
        ),
        ("stock_evidence", "filing"): _RoutePolicy(
            primary_provider_ids=("sec_edgar",),
            forbidden_provider_ids=("baostock", "coinbase_public", "yfinance_current_baseline"),
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="use_cached_evidence_or_explicit_unavailable",
            required_source_types=("official_public", "cache_snapshot"),
            freshness_floor="daily",
            trust_floor="filings_evidence",
            plan_reason_codes=("cache_required",),
        ),
        ("filings_evidence", "companyfacts"): _RoutePolicy(
            primary_provider_ids=("sec_edgar",),
            forbidden_provider_ids=("baostock", "coinbase_public", "yfinance_current_baseline"),
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="use_cached_evidence_or_explicit_unavailable",
            required_source_types=("official_public", "cache_snapshot"),
            freshness_floor="daily",
            trust_floor="filings_evidence",
            plan_reason_codes=("cache_required",),
        ),
        ("filings_evidence", "filing"): _RoutePolicy(
            primary_provider_ids=("sec_edgar",),
            forbidden_provider_ids=("baostock", "coinbase_public", "yfinance_current_baseline"),
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="use_cached_evidence_or_explicit_unavailable",
            required_source_types=("official_public", "cache_snapshot"),
            freshness_floor="daily",
            trust_floor="filings_evidence",
            plan_reason_codes=("cache_required",),
        ),
        ("scanner_diagnostics", "cn_stock_list"): _RoutePolicy(
            observation_provider_ids=("akshare",),
            forbidden_provider_ids=("sec_edgar", "baostock", "coinbase_public", "yfinance_current_baseline"),
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="cache_then_observation_unavailable",
            required_source_types=("public_proxy", "cache_snapshot"),
            freshness_floor="delayed",
            trust_floor="observation_only",
            plan_reason_codes=("cache_required",),
        ),
        ("scanner_diagnostics", "cn_realtime_snapshot"): _RoutePolicy(
            observation_provider_ids=("akshare",),
            forbidden_provider_ids=("sec_edgar", "baostock", "coinbase_public", "yfinance_current_baseline"),
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="cache_then_observation_unavailable",
            required_source_types=("public_proxy", "cache_snapshot"),
            freshness_floor="delayed",
            trust_floor="observation_only",
            plan_reason_codes=("cache_required",),
        ),
        ("scanner_diagnostics", "cn_history_daily"): _RoutePolicy(
            observation_provider_ids=("pytdx", "baostock"),
            forbidden_provider_ids=("sec_edgar", "coinbase_public", "yfinance_current_baseline"),
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="cache_then_observation_unavailable",
            required_source_types=("public_proxy", "cache_snapshot"),
            freshness_floor="delayed",
            trust_floor="observation_only",
            plan_reason_codes=("cache_required",),
        ),
        ("market_observation", "cn_history_daily"): _RoutePolicy(
            observation_provider_ids=("baostock",),
            forbidden_provider_ids=("sec_edgar", "coinbase_public", "yfinance_current_baseline"),
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="cache_then_observation_unavailable",
            required_source_types=("cache_snapshot", "public_proxy"),
            freshness_floor="delayed",
            trust_floor="observation_only",
            plan_reason_codes=("cache_required",),
        ),
        ("market_observation", "cn_realtime_quote"): _RoutePolicy(
            observation_provider_ids=("pytdx",),
            forbidden_provider_ids=("sec_edgar", "baostock", "coinbase_public", "yfinance_current_baseline"),
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="cache_then_observation_unavailable",
            required_source_types=("public_proxy", "cache_snapshot"),
            freshness_floor="delayed",
            trust_floor="observation_only",
            plan_reason_codes=("cache_required",),
        ),
        ("market_observation", "cn_market_stats"): _RoutePolicy(
            observation_provider_ids=("akshare",),
            forbidden_provider_ids=("sec_edgar", "baostock", "coinbase_public", "yfinance_current_baseline"),
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="cache_then_observation_unavailable",
            required_source_types=("public_proxy", "cache_snapshot"),
            freshness_floor="delayed",
            trust_floor="observation_only",
            plan_reason_codes=("cache_required",),
        ),
        ("venue_observation", "venue_ticker"): _RoutePolicy(
            observation_provider_ids=("coinbase_public",),
            forbidden_provider_ids=("sec_edgar", "baostock", "yfinance_current_baseline"),
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="cache_then_observation_unavailable",
            required_source_types=("exchange_public", "cache_snapshot"),
            freshness_floor="delayed",
            trust_floor="observation_only",
            plan_reason_codes=("cache_required",),
        ),
        ("crypto_venue_observation", "venue_observation"): _RoutePolicy(
            observation_provider_ids=("coinbase_public",),
            forbidden_provider_ids=("sec_edgar", "baostock", "yfinance_current_baseline"),
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="cache_then_observation_unavailable",
            required_source_types=("exchange_public", "cache_snapshot"),
            freshness_floor="delayed",
            trust_floor="observation_only",
            plan_reason_codes=("cache_required",),
        ),
        ("market_overview", "quote"): _RoutePolicy(
            forbidden_provider_ids=("sec_edgar", "baostock", "coinbase_public", "yfinance_current_baseline", "yahooquery"),
            cache_required=False,
            background_refresh_required=True,
            score_contribution_allowed=True,
            degradation_policy="require_live_score_grade_authority",
            required_source_types=("official_public", "exchange_public", "cache_snapshot"),
            freshness_floor="live",
            trust_floor="score_grade",
        ),
        ("market_overview", "us_etf_flow_daily"): _RoutePolicy(
            primary_provider_ids=("authorized.us_etf_flow",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_flow_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("market_overview", "us_market_breadth_constituents"): _RoutePolicy(
            primary_provider_ids=("official_or_authorized.us_market_breadth",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_breadth_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("market_overview", "cn_money_market_rates"): _RoutePolicy(
            primary_provider_ids=("official_public.cn_money_market_rates",),
            forbidden_provider_ids=_OFFICIAL_LIQUIDITY_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_official_release_cache_or_explicit_missing",
            required_source_types=("official_public", "cache_snapshot"),
            freshness_floor="delayed",
            trust_floor="official_liquidity_context_or_missing",
            plan_reason_codes=_CN_MONEY_MARKET_PLAN_REASON_CODES,
        ),
        ("market_overview", "fed_liquidity"): _RoutePolicy(
            primary_provider_ids=("official_public.fed_liquidity",),
            forbidden_provider_ids=_OFFICIAL_LIQUIDITY_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_official_release_cache_or_explicit_missing",
            required_source_types=("official_public", "cache_snapshot"),
            freshness_floor="delayed",
            trust_floor="official_liquidity_context_or_missing",
            plan_reason_codes=_FED_LIQUIDITY_PLAN_REASON_CODES,
        ),
        ("market_overview", "fx_dxy"): _RoutePolicy(
            primary_provider_ids=("official_or_authorized.fx_dxy",),
            forbidden_provider_ids=_OFFICIAL_LIQUIDITY_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authoritative_dxy_cache_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="delayed",
            trust_floor="official_or_authorized_fx_context_or_missing",
            plan_reason_codes=_DXY_AUTHORITY_PLAN_REASON_CODES,
        ),
        ("market_overview", "us_advancers_decliners"): _RoutePolicy(
            primary_provider_ids=("official_or_authorized.us_market_breadth",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_breadth_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("market_overview", "us_new_highs_lows"): _RoutePolicy(
            primary_provider_ids=("official_or_authorized.us_market_breadth",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_breadth_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("market_overview", "us_above_ma_breadth"): _RoutePolicy(
            primary_provider_ids=("official_or_authorized.us_market_breadth",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_breadth_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("market_overview", "cn_hk_connect_flow"): _RoutePolicy(
            primary_provider_ids=("authorized.cn_hk_connect_flow",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_flow_bundle_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="delayed",
            trust_floor="authorized_connect_flow_or_missing",
            plan_reason_codes=_CN_HK_CONNECT_FLOW_PLAN_REASON_CODES,
        ),
        ("market_overview", "index_futures"): _RoutePolicy(
            primary_provider_ids=("exchange_or_broker_authorized.index_futures",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_futures_bundle_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="delayed",
            trust_floor="authorized_index_futures_or_missing",
            required_symbols=("NQ", "ES", "YM", "RTY"),
            session="extended_hours",
            plan_reason_codes=_INDEX_FUTURES_PLAN_REASON_CODES,
        ),
        ("market_regime", "us_etf_flow_daily"): _RoutePolicy(
            primary_provider_ids=("authorized.us_etf_flow",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_flow_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("market_regime", "us_market_breadth_constituents"): _RoutePolicy(
            primary_provider_ids=("official_or_authorized.us_market_breadth",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_breadth_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("market_regime", "us_new_highs_lows"): _RoutePolicy(
            primary_provider_ids=("official_or_authorized.us_market_breadth",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_breadth_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("market_regime", "us_above_ma_breadth"): _RoutePolicy(
            primary_provider_ids=("official_or_authorized.us_market_breadth",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_breadth_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("liquidity_impulse", "us_etf_flow_daily"): _RoutePolicy(
            primary_provider_ids=("authorized.us_etf_flow",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_flow_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("liquidity_impulse", "us_etf_creation_redemption"): _RoutePolicy(
            primary_provider_ids=("authorized.us_etf_flow",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_flow_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("liquidity_impulse", "cn_money_market_rates"): _RoutePolicy(
            primary_provider_ids=("official_public.cn_money_market_rates",),
            forbidden_provider_ids=_OFFICIAL_LIQUIDITY_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_official_release_cache_or_explicit_missing",
            required_source_types=("official_public", "cache_snapshot"),
            freshness_floor="delayed",
            trust_floor="official_liquidity_context_or_missing",
            plan_reason_codes=_CN_MONEY_MARKET_PLAN_REASON_CODES,
        ),
        ("liquidity_impulse", "fed_liquidity"): _RoutePolicy(
            primary_provider_ids=("official_public.fed_liquidity",),
            forbidden_provider_ids=_OFFICIAL_LIQUIDITY_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_official_release_cache_or_explicit_missing",
            required_source_types=("official_public", "cache_snapshot"),
            freshness_floor="delayed",
            trust_floor="official_liquidity_context_or_missing",
            plan_reason_codes=_FED_LIQUIDITY_PLAN_REASON_CODES,
        ),
        ("liquidity_impulse", "fx_dxy"): _RoutePolicy(
            primary_provider_ids=("official_or_authorized.fx_dxy",),
            forbidden_provider_ids=_OFFICIAL_LIQUIDITY_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authoritative_dxy_cache_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="delayed",
            trust_floor="official_or_authorized_fx_context_or_missing",
            plan_reason_codes=_DXY_AUTHORITY_PLAN_REASON_CODES,
        ),
        ("liquidity_impulse", "us_market_breadth_constituents"): _RoutePolicy(
            primary_provider_ids=("official_or_authorized.us_market_breadth",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_breadth_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("liquidity_impulse", "us_advancers_decliners"): _RoutePolicy(
            primary_provider_ids=("official_or_authorized.us_market_breadth",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_breadth_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("liquidity_impulse", "us_new_highs_lows"): _RoutePolicy(
            primary_provider_ids=("official_or_authorized.us_market_breadth",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_breadth_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("liquidity_impulse", "us_above_ma_breadth"): _RoutePolicy(
            primary_provider_ids=("official_or_authorized.us_market_breadth",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_breadth_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("liquidity_impulse", "cn_hk_connect_flow"): _RoutePolicy(
            primary_provider_ids=("authorized.cn_hk_connect_flow",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_flow_bundle_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="delayed",
            trust_floor="authorized_connect_flow_or_missing",
            plan_reason_codes=_CN_HK_CONNECT_FLOW_PLAN_REASON_CODES,
        ),
        ("liquidity_impulse", "index_futures"): _RoutePolicy(
            primary_provider_ids=("exchange_or_broker_authorized.index_futures",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_futures_bundle_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="delayed",
            trust_floor="authorized_index_futures_or_missing",
            required_symbols=("NQ", "ES", "YM", "RTY"),
            session="extended_hours",
            plan_reason_codes=_INDEX_FUTURES_PLAN_REASON_CODES,
        ),
        ("rotation_radar", "quote"): _RoutePolicy(
            forbidden_provider_ids=("sec_edgar", "baostock", "coinbase_public", "yfinance_current_baseline", "yahooquery"),
            cache_required=False,
            background_refresh_required=True,
            score_contribution_allowed=True,
            degradation_policy="require_live_score_grade_authority",
            required_source_types=("official_public", "exchange_public", "cache_snapshot"),
            freshness_floor="live",
            trust_floor="score_grade",
        ),
        ("rotation_radar", "us_sector_etf_flow"): _RoutePolicy(
            primary_provider_ids=("authorized.us_etf_flow",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_flow_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("rotation_radar", "us_market_breadth_constituents"): _RoutePolicy(
            primary_provider_ids=("official_or_authorized.us_market_breadth",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_breadth_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("rotation_radar", "real_sector_theme_flow_evidence"): _RoutePolicy(
            primary_provider_ids=("authorized.real_sector_theme_flow",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_real_sector_theme_flow_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="delayed",
            trust_floor="authorized_rotation_flow_or_missing",
            plan_reason_codes=_ROTATION_REAL_FLOW_PLAN_REASON_CODES,
        ),
        ("scanner_price_scoring", "cn_realtime_quote"): _RoutePolicy(
            forbidden_provider_ids=("baostock", "sec_edgar", "coinbase_public", "yfinance_current_baseline"),
            cache_required=False,
            background_refresh_required=True,
            score_contribution_allowed=True,
            degradation_policy="require_live_score_grade_authority",
            required_source_types=("official_public", "exchange_public", "cache_snapshot"),
            freshness_floor="live",
            trust_floor="score_grade",
        ),
        ("market_temperature", "quote"): _RoutePolicy(
            forbidden_provider_ids=(
                "coinbase_public",
                "akshare",
                "baostock",
                "pytdx_existing_baseline",
                "sec_edgar",
                "yfinance_current_baseline",
                "yahooquery",
            ),
            cache_required=False,
            background_refresh_required=True,
            score_contribution_allowed=True,
            degradation_policy="require_live_score_grade_authority",
            required_source_types=("official_public", "exchange_public", "cache_snapshot"),
            freshness_floor="live",
            trust_floor="score_grade",
        ),
        ("liquidity_score", "us_etf_flow_daily"): _RoutePolicy(
            primary_provider_ids=("authorized.us_etf_flow",),
            forbidden_provider_ids=_AUTHORIZED_US_FLOW_AND_BREADTH_FORBIDDEN_PROVIDER_IDS,
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=True,
            degradation_policy="require_authorized_feed_or_explicit_missing",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="authorized_flow_or_missing",
            plan_reason_codes=_AUTHORIZED_US_FLOW_AND_BREADTH_PLAN_REASON_CODES,
        ),
        ("liquidity_score", "quote"): _RoutePolicy(
            forbidden_provider_ids=(
                "coinbase_public",
                "akshare",
                "baostock",
                "pytdx_existing_baseline",
                "sec_edgar",
                "yfinance_current_baseline",
                "yahooquery",
            ),
            cache_required=False,
            background_refresh_required=True,
            score_contribution_allowed=True,
            degradation_policy="require_live_score_grade_authority",
            required_source_types=("official_public", "exchange_public", "cache_snapshot"),
            freshness_floor="live",
            trust_floor="score_grade",
        ),
        ("backtest", "ohlcv"): _RoutePolicy(
            forbidden_provider_ids=("sec_edgar", "baostock", "coinbase_public", "yfinance_current_baseline", "yahooquery"),
            cache_required=True,
            background_refresh_required=False,
            score_contribution_allowed=True,
            degradation_policy="fail_closed_without_reproducible_store",
            required_source_types=("cache_snapshot",),
            freshness_floor="cached",
            trust_floor="reproducible_local_or_stored",
            plan_reason_codes=("reproducible_data_required", "cache_required"),
        ),
        ("backtest", "cn_history_daily"): _RoutePolicy(
            forbidden_provider_ids=("sec_edgar", "baostock", "coinbase_public", "yfinance_current_baseline", "yahooquery"),
            cache_required=True,
            background_refresh_required=False,
            score_contribution_allowed=True,
            degradation_policy="fail_closed_without_reproducible_store",
            required_source_types=("cache_snapshot",),
            freshness_floor="cached",
            trust_floor="reproducible_local_or_stored",
            plan_reason_codes=("reproducible_data_required", "cache_required"),
        ),
    }
)


class CapabilityResolver:
    """Resolve inert provider metadata without touching runtime provider code."""

    @staticmethod
    def route_candidate(provider_id: str, capability: str) -> ProviderRouteCandidate | None:
        normalized_provider = _normalize(provider_id)
        support = get_provider_capability_support_contract(normalized_provider, capability)
        fit = get_provider_fit_metadata(normalized_provider)

        if support is not None:
            probe = get_provider_dry_run_probe_contract(normalized_provider)
            return ProviderRouteCandidate(
                provider_id=support.provider_id,
                provider_name=support.provider_name,
                capability=capability,
                source_type=support.source_type,
                source_tier=support.source_tier,
                trust_level=support.trust_level,
                freshness_expectation=support.freshness_expectation,
                observation_only=support.observation_only,
                score_contribution_allowed=support.score_contribution_allowed,
                paid_data_likely_required=support.paid_data_likely_required,
                key_required=support.key_required,
                enabled_by_default=False,
                no_default_live_http_calls=probe.no_default_live_http_calls if probe is not None else True,
                missing_provider_reason=(
                    support.missing_provider_reason
                    or (probe.missing_provider_reason if probe is not None else None)
                ),
            )

        if fit is not None:
            probe = get_provider_dry_run_probe_contract(normalized_provider)
            return ProviderRouteCandidate(
                provider_id=fit.provider_id,
                provider_name=fit.provider_name,
                capability=capability,
                source_type=resolve_source_type(source=fit.provider_id),
                source_tier=fit.source_tier,
                trust_level=fit.trust_level,
                freshness_expectation=fit.freshness_expectation,
                observation_only=fit.observation_only,
                score_contribution_allowed=fit.score_contribution_allowed,
                paid_data_likely_required=fit.paid_data_likely_required,
                key_required=fit.key_required,
                enabled_by_default=fit.enabled_by_default,
                no_default_live_http_calls=probe.no_default_live_http_calls if probe is not None else True,
                missing_provider_reason=fit.missing_provider_reason,
            )

        capability_metadata = get_provider_capability(normalized_provider)
        if capability_metadata is None:
            return None

        return ProviderRouteCandidate(
            provider_id=capability_metadata.provider_id,
            provider_name=capability_metadata.display_name,
            capability=capability,
            source_type=_LOCAL_SOURCE_TYPE_BY_PROVIDER.get(capability_metadata.provider_id, resolve_source_type(source=capability_metadata.provider_id)),
            source_tier=_LOCAL_SOURCE_TIER_BY_PROVIDER.get(capability_metadata.provider_id, "runtime_metadata"),
            trust_level=_LOCAL_TRUST_LEVEL_BY_PROVIDER.get(capability_metadata.provider_id, "runtime_metadata"),
            freshness_expectation=_LOCAL_FRESHNESS_EXPECTATION_BY_PROVIDER.get(
                capability_metadata.provider_id,
                capability_metadata.freshness_class.value,
            ),
            observation_only=False,
            score_contribution_allowed=True,
            paid_data_likely_required=False,
            key_required=False,
            enabled_by_default=True,
            no_default_live_http_calls=True,
            missing_provider_reason=None,
        )

    @staticmethod
    def backtest_primary_candidates(request: DataSourceRouteRequest) -> tuple[ProviderRouteCandidate, ...]:
        domain = _BACKTEST_DOMAIN_BY_CAPABILITY.get(_normalize(request.capability))
        if domain is None:
            return ()

        market = _MARKET_ALIASES.get(_normalize(request.market))
        candidates: list[ProviderRouteCandidate] = []
        for capability_metadata in providers_for_domain(domain):
            if not is_provider_allowed_for_backtest(capability_metadata.provider_id):
                continue
            if market is not None and ProviderMarket.GLOBAL not in capability_metadata.markets and market not in capability_metadata.markets:
                continue
            candidate = CapabilityResolver.route_candidate(capability_metadata.provider_id, request.capability)
            if candidate is not None:
                candidates.append(candidate)
        return tuple(candidates)


class DataSourceRouter:
    """Pure eligibility router for provider policy decisions."""

    @staticmethod
    def resolve(request: DataSourceRouteRequest) -> DataSourceRoutePlan:
        policy = _select_policy(request)
        primary_candidates = _build_primary_candidates(policy, request)
        observation_candidates = _build_observation_candidates(policy, request)
        forbidden_providers = _build_forbidden_providers(policy, request)

        reason_codes = _build_reason_codes(
            request=request,
            policy=policy,
            forbidden_providers=forbidden_providers,
        )
        return DataSourceRoutePlan(
            primary_candidates=primary_candidates,
            observation_candidates=observation_candidates,
            forbidden_providers=forbidden_providers,
            cache_required=policy.cache_required or (not request.allow_network and _normalize(request.freshness_need) in _LIVE_FRESHNESS_VALUES),
            background_refresh_required=policy.background_refresh_required,
            score_contribution_allowed=policy.score_contribution_allowed and not observation_candidates,
            degradation_policy=policy.degradation_policy,
            required_source_types=policy.required_source_types,
            freshness_floor=policy.freshness_floor,
            trust_floor=policy.trust_floor,
            required_symbols=policy.required_symbols,
            session=policy.session,
            reason_codes=reason_codes,
        )


def _select_policy(request: DataSourceRouteRequest) -> _RoutePolicy:
    if _normalize(request.capability) == "etf_flow":
        return _RoutePolicy(
            cache_required=True,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="reject_legacy_capability_alias",
            required_source_types=("cache_snapshot",),
            freshness_floor="daily",
            trust_floor="canonical_capability_required",
            plan_reason_codes=_LEGACY_CAPABILITY_ALIAS_PLAN_REASON_CODES,
        )

    key = (_normalize(request.use_case), _normalize(request.capability))
    policy = _ROUTE_POLICIES.get(key)
    if policy is not None:
        return policy

    if _normalize(request.use_case) == "backtest":
        return _ROUTE_POLICIES[("backtest", "ohlcv")]
    if _normalize(request.use_case) == "market_briefing":
        return _RoutePolicy(
            forbidden_provider_ids=_MARKET_INTELLIGENCE_AUTHORITY_FORBIDDEN_PROVIDER_IDS,
            cache_required=False,
            background_refresh_required=True,
            score_contribution_allowed=False,
            degradation_policy="require_live_score_grade_authority",
            required_source_types=_MARKET_INTELLIGENCE_AUTHORITY_REQUIRED_SOURCE_TYPES,
            freshness_floor="live",
            trust_floor="score_grade",
        )
    if request.scoring_allowed:
        return _ROUTE_POLICIES.get(
            (_normalize(request.use_case), "quote"),
            _RoutePolicy(
                cache_required=False,
                background_refresh_required=True,
                score_contribution_allowed=True,
                degradation_policy="require_live_score_grade_authority",
                required_source_types=_MARKET_INTELLIGENCE_AUTHORITY_REQUIRED_SOURCE_TYPES,
                freshness_floor="live",
                trust_floor="score_grade",
            ),
        )
    return _RoutePolicy()


def _build_primary_candidates(
    policy: _RoutePolicy,
    request: DataSourceRouteRequest,
) -> tuple[ProviderRouteCandidate, ...]:
    if _normalize(request.use_case) == "backtest":
        return CapabilityResolver.backtest_primary_candidates(request)

    candidates = [
        CapabilityResolver.route_candidate(provider_id, request.capability)
        for provider_id in policy.primary_provider_ids
    ]
    return tuple(candidate for candidate in candidates if candidate is not None)


def _build_observation_candidates(
    policy: _RoutePolicy,
    request: DataSourceRouteRequest,
) -> tuple[ProviderRouteCandidate, ...]:
    candidates = [
        CapabilityResolver.route_candidate(provider_id, request.capability)
        for provider_id in policy.observation_provider_ids
    ]
    filtered = [candidate for candidate in candidates if candidate is not None]
    return tuple(
        ProviderRouteCandidate(
            provider_id=candidate.provider_id,
            provider_name=candidate.provider_name,
            capability=candidate.capability,
            source_type=candidate.source_type,
            source_tier=candidate.source_tier,
            trust_level=candidate.trust_level,
            freshness_expectation=candidate.freshness_expectation,
            observation_only=True,
            score_contribution_allowed=False,
            paid_data_likely_required=candidate.paid_data_likely_required,
            key_required=candidate.key_required,
            enabled_by_default=candidate.enabled_by_default,
            no_default_live_http_calls=candidate.no_default_live_http_calls,
            missing_provider_reason=candidate.missing_provider_reason,
        )
        for candidate in filtered
    )


def _build_forbidden_providers(
    policy: _RoutePolicy,
    request: DataSourceRouteRequest,
) -> tuple[ProviderRouteCandidate, ...]:
    candidates = [
        CapabilityResolver.route_candidate(provider_id, request.capability)
        or CapabilityResolver.route_candidate(provider_id, "quote")
        or CapabilityResolver.route_candidate(provider_id, "companyfacts")
        for provider_id in policy.forbidden_provider_ids
    ]
    return tuple(candidate for candidate in candidates if candidate is not None)


def _build_reason_codes(
    *,
    request: DataSourceRouteRequest,
    policy: _RoutePolicy,
    forbidden_providers: tuple[ProviderRouteCandidate, ...],
) -> Mapping[str, tuple[str, ...]]:
    codes: dict[str, tuple[str, ...]] = {}
    plan_codes = list(policy.plan_reason_codes)
    if not request.allow_network and _normalize(request.freshness_need) in _LIVE_FRESHNESS_VALUES:
        plan_codes.extend(("live_network_forbidden", "cache_required"))
    if _normalize(request.use_case) == "backtest" and "reproducible_data_required" not in plan_codes:
        plan_codes.extend(("reproducible_data_required", "cache_required"))
    if plan_codes:
        codes["plan"] = _unique_preserving_order(tuple(plan_codes))

    for candidate in forbidden_providers:
        provider_codes = ["provider_forbidden_for_use_case"]
        if candidate.observation_only:
            provider_codes.append("provider_observation_only")
        if request.scoring_allowed and not candidate.score_contribution_allowed:
            provider_codes.append("scoring_not_allowed")
        if _provider_is_not_capable(candidate, request):
            provider_codes.append("provider_not_capable")
        fit = get_provider_fit_metadata(candidate.provider_id)
        if fit is not None:
            provider_codes.extend(fit.rejected_for)
            if _normalize(request.freshness_need) in _LIVE_FRESHNESS_VALUES and "delayed" in fit.freshness_expectation:
                provider_codes.append("provider_not_capable")
        support = get_provider_capability_support_contract(candidate.provider_id, request.capability)
        if support is not None and _normalize(request.freshness_need) in _LIVE_FRESHNESS_VALUES:
            if "delayed" in support.freshness_expectation or "t_plus_1" in support.freshness_expectation:
                provider_codes.append("provider_not_capable")
        scoring_contract = get_provider_scoring_contract(candidate.provider_id, request.capability)
        if scoring_contract is not None:
            provider_codes.extend(
                (
                    "authorization_required",
                    "freshness_floor_required",
                    "coverage_floor_required",
                )
            )
        if _normalize(request.use_case) == "backtest":
            provider_codes.append("reproducible_data_required")
        if not request.allow_network and _normalize(request.freshness_need) in _LIVE_FRESHNESS_VALUES:
            provider_codes.append("live_network_forbidden")
        codes[candidate.provider_id] = _unique_preserving_order(tuple(provider_codes))
    return MappingProxyType(codes)


def _provider_is_not_capable(candidate: ProviderRouteCandidate, request: DataSourceRouteRequest) -> bool:
    support = get_provider_capability_support_contract(candidate.provider_id, request.capability)
    normalized_capability = _normalize(request.capability)
    if support is None and candidate.provider_id == "baostock" and _normalize(request.capability) not in {
        "cn_adjust_factor",
        "cn_basic_financials",
        "cn_history_daily",
        "cn_index_history_daily",
    }:
        return True
    if (
        normalized_capability
        in {
            "us_etf_flow_daily",
            "us_etf_creation_redemption",
            "us_sector_etf_flow",
            "us_market_breadth_constituents",
            "us_advancers_decliners",
            "us_new_highs_lows",
            "us_above_ma_breadth",
            "us_sector_breadth",
            "fed_liquidity",
            "cn_money_market_rates",
            "fx_dxy",
            "cn_hk_connect_flow",
            "index_futures",
            "real_sector_theme_flow_evidence",
        }
        and candidate.source_type in _PROXY_SOURCE_TYPES
    ):
        return True
    if _normalize(request.freshness_need) in _LIVE_FRESHNESS_VALUES and candidate.source_type in _PROXY_SOURCE_TYPES:
        return True
    return False


__all__ = [
    "CapabilityResolver",
    "DataSourceRoutePlan",
    "DataSourceRouteRequest",
    "DataSourceRouter",
    "ProviderRouteCandidate",
]
