# -*- coding: utf-8 -*-
"""Inert provider capability metadata for quota-aware planning reviews.

This module is metadata only. It must not import provider clients, read
credentials, call networks, mutate runtime config, or affect provider order.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Optional

from src.services.source_confidence_contract import (
    ProviderCapabilitySupportContract,
    ProviderDryRunProbeContract,
    ProviderFitMetadataContract,
)


class ProviderDomain(str, Enum):
    QUOTE = "quote"
    OHLCV = "ohlcv"
    FUNDAMENTALS = "fundamentals"
    STATEMENTS = "statements"
    EARNINGS = "earnings"
    NEWS = "news"
    SENTIMENT = "sentiment"
    TECHNICALS = "technicals"
    MACRO = "macro"
    CRYPTO = "crypto"
    FOREX = "forex"
    OPTIONS = "options"


class ProviderMarket(str, Enum):
    US = "US"
    CN = "CN"
    HK = "HK"
    CRYPTO = "crypto"
    FOREX = "forex"
    GLOBAL = "global"
    UNKNOWN = "unknown"


class ProviderQuotaClass(str, Enum):
    CHEAP = "cheap"
    MODERATE = "moderate"
    SCARCE = "scarce"
    UNKNOWN = "unknown"
    LOCAL = "local"


class FreshnessClass(str, Enum):
    REALTIME = "realtime"
    DELAYED = "delayed"
    DAILY = "daily"
    CACHED = "cached"
    INFERRED = "inferred"
    MANUAL_REVIEW = "manual_review"


class ScannerUsage(str, Enum):
    LOCAL_ONLY = "local_only"
    TOP_N_ONLY = "top_n_only"
    NEVER = "never"
    DIAGNOSTICS_ONLY = "diagnostics_only"


class BacktestUsage(str, Enum):
    LOCAL_ONLY = "local_only"
    NEVER = "never"


@dataclass(frozen=True)
class ProviderCapability:
    provider_id: str
    display_name: str
    domains: tuple[ProviderDomain, ...]
    markets: tuple[ProviderMarket, ...]
    quota_class: ProviderQuotaClass
    freshness_class: FreshnessClass
    recommended_ttl_seconds_by_domain: Mapping[str, int]
    scanner_allowed: bool
    scanner_usage: ScannerUsage
    backtest_allowed: bool
    backtest_usage: BacktestUsage
    quick_analysis_allowed: bool
    standard_analysis_allowed: bool
    deep_research_allowed: bool
    default_priority_by_domain: Mapping[str, int]
    risk_notes: tuple[str, ...] = ()
    operator_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderScoringContract:
    provider_id: str
    capability: str
    coverage_universe: str
    cadence: str
    freshness_floor: str
    coverage_ratio_floor: float
    required_source_tier: str
    score_eligibility_gate: str

    def to_dict(self) -> dict[str, object]:
        return {
            "providerId": self.provider_id,
            "capability": self.capability,
            "coverageUniverse": self.coverage_universe,
            "cadence": self.cadence,
            "freshnessFloor": self.freshness_floor,
            "coverageRatioFloor": self.coverage_ratio_floor,
            "requiredSourceTier": self.required_source_tier,
            "scoreEligibilityGate": self.score_eligibility_gate,
        }


def _ttl(**values: int) -> Mapping[str, int]:
    return MappingProxyType(dict(values))


def _priority(**values: int) -> Mapping[str, int]:
    return MappingProxyType(dict(values))


_CAPABILITIES = (
    ProviderCapability(
        provider_id="local_cache",
        display_name="Local Cache",
        domains=(
            ProviderDomain.QUOTE,
            ProviderDomain.OHLCV,
            ProviderDomain.FUNDAMENTALS,
            ProviderDomain.STATEMENTS,
            ProviderDomain.EARNINGS,
            ProviderDomain.NEWS,
            ProviderDomain.SENTIMENT,
            ProviderDomain.TECHNICALS,
            ProviderDomain.MACRO,
            ProviderDomain.CRYPTO,
            ProviderDomain.FOREX,
            ProviderDomain.OPTIONS,
        ),
        markets=(ProviderMarket.US, ProviderMarket.CN, ProviderMarket.HK, ProviderMarket.CRYPTO, ProviderMarket.FOREX, ProviderMarket.GLOBAL),
        quota_class=ProviderQuotaClass.LOCAL,
        freshness_class=FreshnessClass.CACHED,
        recommended_ttl_seconds_by_domain=_ttl(
            quote=60,
            ohlcv=15 * 60,
            fundamentals=12 * 60 * 60,
            statements=24 * 60 * 60,
            earnings=12 * 60 * 60,
            news=30 * 60,
            sentiment=2 * 60 * 60,
            technicals=15 * 60,
            macro=10 * 60,
            crypto=15,
            forex=60,
            options=15 * 60,
        ),
        scanner_allowed=True,
        scanner_usage=ScannerUsage.LOCAL_ONLY,
        backtest_allowed=True,
        backtest_usage=BacktestUsage.LOCAL_ONLY,
        quick_analysis_allowed=True,
        standard_analysis_allowed=True,
        deep_research_allowed=True,
        default_priority_by_domain=_priority(
            quote=1,
            ohlcv=1,
            fundamentals=1,
            statements=1,
            earnings=1,
            news=1,
            sentiment=1,
            technicals=3,
            macro=1,
            crypto=1,
            forex=1,
            options=1,
        ),
        operator_notes=("Backtest and scanner should use persisted/cache data first; stale/fallback labels must remain visible.",),
    ),
    ProviderCapability(
        provider_id="local_ohlcv",
        display_name="Local OHLCV",
        domains=(ProviderDomain.OHLCV, ProviderDomain.TECHNICALS),
        markets=(ProviderMarket.US, ProviderMarket.CN, ProviderMarket.HK),
        quota_class=ProviderQuotaClass.LOCAL,
        freshness_class=FreshnessClass.CACHED,
        recommended_ttl_seconds_by_domain=_ttl(ohlcv=15 * 60, technicals=15 * 60),
        scanner_allowed=True,
        scanner_usage=ScannerUsage.LOCAL_ONLY,
        backtest_allowed=True,
        backtest_usage=BacktestUsage.LOCAL_ONLY,
        quick_analysis_allowed=True,
        standard_analysis_allowed=True,
        deep_research_allowed=True,
        default_priority_by_domain=_priority(ohlcv=2, technicals=2),
        operator_notes=("Compute technical indicators locally from OHLCV where possible.",),
    ),
    ProviderCapability(
        provider_id="local_news_cache",
        display_name="Local News Cache",
        domains=(ProviderDomain.NEWS, ProviderDomain.SENTIMENT),
        markets=(ProviderMarket.US, ProviderMarket.CN, ProviderMarket.HK, ProviderMarket.GLOBAL),
        quota_class=ProviderQuotaClass.LOCAL,
        freshness_class=FreshnessClass.CACHED,
        recommended_ttl_seconds_by_domain=_ttl(news=30 * 60, sentiment=2 * 60 * 60),
        scanner_allowed=True,
        scanner_usage=ScannerUsage.LOCAL_ONLY,
        backtest_allowed=True,
        backtest_usage=BacktestUsage.LOCAL_ONLY,
        quick_analysis_allowed=True,
        standard_analysis_allowed=True,
        deep_research_allowed=True,
        default_priority_by_domain=_priority(news=2, sentiment=4),
        risk_notes=("Cached news may be stale; never label cached or inferred sentiment as live.",),
        operator_notes=("Use cached news before external news/search providers.",),
    ),
    ProviderCapability(
        provider_id="yahoo_yfinance",
        display_name="Yahoo Finance / yfinance",
        domains=(ProviderDomain.QUOTE, ProviderDomain.OHLCV, ProviderDomain.FUNDAMENTALS, ProviderDomain.STATEMENTS),
        markets=(ProviderMarket.US, ProviderMarket.CN, ProviderMarket.HK, ProviderMarket.CRYPTO, ProviderMarket.FOREX, ProviderMarket.GLOBAL),
        quota_class=ProviderQuotaClass.CHEAP,
        freshness_class=FreshnessClass.DELAYED,
        recommended_ttl_seconds_by_domain=_ttl(quote=60, ohlcv=15 * 60, fundamentals=12 * 60 * 60, statements=24 * 60 * 60),
        scanner_allowed=True,
        scanner_usage=ScannerUsage.TOP_N_ONLY,
        backtest_allowed=False,
        backtest_usage=BacktestUsage.NEVER,
        quick_analysis_allowed=True,
        standard_analysis_allowed=True,
        deep_research_allowed=True,
        default_priority_by_domain=_priority(quote=40, ohlcv=30, fundamentals=40, statements=35),
        risk_notes=("Unofficial and often delayed; do not treat as decision-grade live data.",),
        operator_notes=("Useful cheap fallback or research data after local/cache checks.",),
    ),
    ProviderCapability(
        provider_id="akshare",
        display_name="AkShare",
        domains=(ProviderDomain.QUOTE, ProviderDomain.OHLCV, ProviderDomain.TECHNICALS),
        markets=(ProviderMarket.CN, ProviderMarket.HK),
        quota_class=ProviderQuotaClass.CHEAP,
        freshness_class=FreshnessClass.DELAYED,
        recommended_ttl_seconds_by_domain=_ttl(quote=60, ohlcv=15 * 60, technicals=15 * 60),
        scanner_allowed=True,
        scanner_usage=ScannerUsage.TOP_N_ONLY,
        backtest_allowed=False,
        backtest_usage=BacktestUsage.NEVER,
        quick_analysis_allowed=True,
        standard_analysis_allowed=True,
        deep_research_allowed=False,
        default_priority_by_domain=_priority(quote=30, ohlcv=35, technicals=45),
        risk_notes=(
            "Public web interfaces can change or fail without notice; do not treat AkShare as official or decision-grade live data.",
        ),
        operator_notes=(
            "Observation-first CN/HK enrichment only; scoring or trust promotion requires separate source-specific review.",
        ),
    ),
    ProviderCapability(
        provider_id="alpaca",
        display_name="Alpaca Market Data",
        domains=(ProviderDomain.QUOTE, ProviderDomain.OHLCV),
        markets=(ProviderMarket.US,),
        quota_class=ProviderQuotaClass.MODERATE,
        freshness_class=FreshnessClass.REALTIME,
        recommended_ttl_seconds_by_domain=_ttl(quote=60, ohlcv=15 * 60),
        scanner_allowed=True,
        scanner_usage=ScannerUsage.TOP_N_ONLY,
        backtest_allowed=False,
        backtest_usage=BacktestUsage.NEVER,
        quick_analysis_allowed=True,
        standard_analysis_allowed=True,
        deep_research_allowed=False,
        default_priority_by_domain=_priority(quote=20, ohlcv=25),
        risk_notes=("Entitlement and feed may affect realtime/delayed posture.",),
        operator_notes=("Reserve for configured US quote/OHLCV enrichment, not broad research.",),
    ),
    ProviderCapability(
        provider_id="twelve_data",
        display_name="Twelve Data",
        domains=(ProviderDomain.QUOTE, ProviderDomain.OHLCV, ProviderDomain.FOREX, ProviderDomain.CRYPTO),
        markets=(ProviderMarket.HK, ProviderMarket.US, ProviderMarket.FOREX, ProviderMarket.CRYPTO),
        quota_class=ProviderQuotaClass.SCARCE,
        freshness_class=FreshnessClass.DELAYED,
        recommended_ttl_seconds_by_domain=_ttl(quote=60, ohlcv=15 * 60, forex=60, crypto=60),
        scanner_allowed=True,
        scanner_usage=ScannerUsage.TOP_N_ONLY,
        backtest_allowed=False,
        backtest_usage=BacktestUsage.NEVER,
        quick_analysis_allowed=True,
        standard_analysis_allowed=True,
        deep_research_allowed=False,
        default_priority_by_domain=_priority(quote=25, ohlcv=25, forex=50, crypto=50),
        risk_notes=("Quota is limited; coverage depends on configured product entitlement.",),
        operator_notes=("Best suited for HK/US quote and OHLCV enrichment after deterministic preselection.",),
    ),
    ProviderCapability(
        provider_id="fmp",
        display_name="Financial Modeling Prep",
        domains=(
            ProviderDomain.QUOTE,
            ProviderDomain.OHLCV,
            ProviderDomain.FUNDAMENTALS,
            ProviderDomain.STATEMENTS,
            ProviderDomain.EARNINGS,
            ProviderDomain.TECHNICALS,
        ),
        markets=(ProviderMarket.US, ProviderMarket.GLOBAL),
        quota_class=ProviderQuotaClass.MODERATE,
        freshness_class=FreshnessClass.DAILY,
        recommended_ttl_seconds_by_domain=_ttl(
            quote=60,
            ohlcv=15 * 60,
            fundamentals=12 * 60 * 60,
            statements=24 * 60 * 60,
            earnings=12 * 60 * 60,
            technicals=24 * 60 * 60,
        ),
        scanner_allowed=False,
        scanner_usage=ScannerUsage.TOP_N_ONLY,
        backtest_allowed=False,
        backtest_usage=BacktestUsage.NEVER,
        quick_analysis_allowed=True,
        standard_analysis_allowed=True,
        deep_research_allowed=True,
        default_priority_by_domain=_priority(
            quote=50,
            ohlcv=70,
            fundamentals=10,
            statements=10,
            earnings=15,
            technicals=80,
        ),
        risk_notes=("Avoid burning quota on OHLCV or external technical indicators when local data can satisfy the need.",),
        operator_notes=("Use first for fundamentals/statements; do not run scanner-wide.",),
    ),
    ProviderCapability(
        provider_id="finnhub",
        display_name="Finnhub",
        domains=(ProviderDomain.QUOTE, ProviderDomain.FUNDAMENTALS, ProviderDomain.NEWS),
        markets=(ProviderMarket.US,),
        quota_class=ProviderQuotaClass.MODERATE,
        freshness_class=FreshnessClass.DAILY,
        recommended_ttl_seconds_by_domain=_ttl(quote=60, fundamentals=12 * 60 * 60, news=30 * 60),
        scanner_allowed=True,
        scanner_usage=ScannerUsage.TOP_N_ONLY,
        backtest_allowed=False,
        backtest_usage=BacktestUsage.NEVER,
        quick_analysis_allowed=True,
        standard_analysis_allowed=True,
        deep_research_allowed=True,
        default_priority_by_domain=_priority(quote=35, fundamentals=25, news=35),
        risk_notes=("Per-symbol company-news or quote fanout can burn free quota.",),
        operator_notes=("Use bounded US quote/company-news/metrics fallback only.",),
    ),
    ProviderCapability(
        provider_id="alpha_vantage",
        display_name="Alpha Vantage",
        domains=(ProviderDomain.FUNDAMENTALS, ProviderDomain.STATEMENTS, ProviderDomain.TECHNICALS),
        markets=(ProviderMarket.US, ProviderMarket.GLOBAL),
        quota_class=ProviderQuotaClass.SCARCE,
        freshness_class=FreshnessClass.MANUAL_REVIEW,
        recommended_ttl_seconds_by_domain=_ttl(fundamentals=24 * 60 * 60, statements=24 * 60 * 60, technicals=24 * 60 * 60),
        scanner_allowed=False,
        scanner_usage=ScannerUsage.NEVER,
        backtest_allowed=False,
        backtest_usage=BacktestUsage.NEVER,
        quick_analysis_allowed=False,
        standard_analysis_allowed=False,
        deep_research_allowed=True,
        default_priority_by_domain=_priority(fundamentals=95, statements=95, technicals=99),
        risk_notes=("Very scarce free quota; external technical indicators are usually avoidable.",),
        operator_notes=("Manual/deep last-resort fallback only.",),
    ),
    ProviderCapability(
        provider_id="gnews",
        display_name="GNews",
        domains=(ProviderDomain.NEWS,),
        markets=(ProviderMarket.GLOBAL,),
        quota_class=ProviderQuotaClass.SCARCE,
        freshness_class=FreshnessClass.DAILY,
        recommended_ttl_seconds_by_domain=_ttl(news=30 * 60),
        scanner_allowed=False,
        scanner_usage=ScannerUsage.NEVER,
        backtest_allowed=False,
        backtest_usage=BacktestUsage.NEVER,
        quick_analysis_allowed=False,
        standard_analysis_allowed=True,
        deep_research_allowed=True,
        default_priority_by_domain=_priority(news=65),
        risk_notes=("Generic news quota should not be spent across scanner-wide symbol batches.",),
        operator_notes=("Use only for standard/deep or explicit top-N research enrichment.",),
    ),
    ProviderCapability(
        provider_id="tavily",
        display_name="Tavily",
        domains=(ProviderDomain.NEWS, ProviderDomain.SENTIMENT, ProviderDomain.MACRO),
        markets=(ProviderMarket.GLOBAL,),
        quota_class=ProviderQuotaClass.MODERATE,
        freshness_class=FreshnessClass.MANUAL_REVIEW,
        recommended_ttl_seconds_by_domain=_ttl(news=30 * 60, sentiment=2 * 60 * 60, macro=30 * 60),
        scanner_allowed=False,
        scanner_usage=ScannerUsage.TOP_N_ONLY,
        backtest_allowed=False,
        backtest_usage=BacktestUsage.NEVER,
        quick_analysis_allowed=False,
        standard_analysis_allowed=True,
        deep_research_allowed=True,
        default_priority_by_domain=_priority(news=45, sentiment=65, macro=70),
        risk_notes=("Multi-dimension searches can multiply provider calls per symbol.",),
        operator_notes=("Deep research after cache/local evidence; never scanner-wide by default.",),
    ),
    ProviderCapability(
        provider_id="social_sentiment",
        display_name="Social Sentiment",
        domains=(ProviderDomain.SENTIMENT,),
        markets=(ProviderMarket.US,),
        quota_class=ProviderQuotaClass.UNKNOWN,
        freshness_class=FreshnessClass.CACHED,
        recommended_ttl_seconds_by_domain=_ttl(sentiment=30 * 60),
        scanner_allowed=False,
        scanner_usage=ScannerUsage.TOP_N_ONLY,
        backtest_allowed=False,
        backtest_usage=BacktestUsage.NEVER,
        quick_analysis_allowed=False,
        standard_analysis_allowed=True,
        deep_research_allowed=True,
        default_priority_by_domain=_priority(sentiment=50),
        risk_notes=("Per-ticker social reports may be expensive or slow.",),
        operator_notes=("Use only for configured US standard/deep or explicit top-N enrichment.",),
    ),
    ProviderCapability(
        provider_id="local_inference",
        display_name="Local Inference",
        domains=(ProviderDomain.SENTIMENT,),
        markets=(ProviderMarket.US, ProviderMarket.CN, ProviderMarket.HK, ProviderMarket.GLOBAL),
        quota_class=ProviderQuotaClass.LOCAL,
        freshness_class=FreshnessClass.INFERRED,
        recommended_ttl_seconds_by_domain=_ttl(sentiment=2 * 60 * 60),
        scanner_allowed=True,
        scanner_usage=ScannerUsage.LOCAL_ONLY,
        backtest_allowed=True,
        backtest_usage=BacktestUsage.LOCAL_ONLY,
        quick_analysis_allowed=True,
        standard_analysis_allowed=True,
        deep_research_allowed=True,
        default_priority_by_domain=_priority(sentiment=5),
        risk_notes=("Derived from existing text only; never live external sentiment.",),
        operator_notes=("Keep labels inferred/local and tie freshness to source text.",),
    ),
)

_CAPABILITIES_BY_ID = {capability.provider_id: capability for capability in _CAPABILITIES}


def _capability_support_entry(
    provider_id: str,
    capability: str,
    *,
    provider_name: str | None = None,
    source_type: str = "public_proxy",
    source_tier: str = "unofficial_public_api",
    trust_level: str,
    freshness_expectation: str,
    degradation_reason: str,
    missing_provider_reason: str,
    paid_data_likely_required: bool = False,
    key_required: bool = False,
    cache_required: bool = True,
    background_refresh_recommended: bool = True,
) -> ProviderCapabilitySupportContract:
    return ProviderCapabilitySupportContract(
        provider_name=provider_name or provider_id,
        provider_id=provider_id,
        capability=capability,
        source_type=source_type,
        source_tier=source_tier,
        trust_level=trust_level,
        freshness_expectation=freshness_expectation,
        observation_only=True,
        score_contribution_allowed=False,
        paid_data_likely_required=paid_data_likely_required,
        key_required=key_required,
        cache_required=cache_required,
        background_refresh_recommended=background_refresh_recommended,
        degradation_reason=degradation_reason,
        missing_provider_reason=missing_provider_reason,
    )


_PROVIDER_CAPABILITY_SUPPORT_CONTRACTS = (
    _capability_support_entry(
        "authorized.us_etf_flow",
        "us_etf_flow_daily",
        provider_name="Authorized US ETF Flow",
        source_type="missing",
        source_tier="authorized_licensed_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="licensed_daily_or_delayed_fund_flow",
        degradation_reason="authorized_feed_not_configured",
        missing_provider_reason="authorized_us_etf_flow_feed_not_configured",
        paid_data_likely_required=True,
        key_required=True,
    ),
    _capability_support_entry(
        "authorized.us_etf_flow",
        "us_etf_creation_redemption",
        provider_name="Authorized US ETF Flow",
        source_type="missing",
        source_tier="authorized_licensed_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="licensed_daily_or_delayed_fund_flow",
        degradation_reason="authorized_feed_not_configured",
        missing_provider_reason="authorized_us_etf_flow_feed_not_configured",
        paid_data_likely_required=True,
        key_required=True,
    ),
    _capability_support_entry(
        "authorized.us_etf_flow",
        "us_sector_etf_flow",
        provider_name="Authorized US ETF Flow",
        source_type="missing",
        source_tier="authorized_licensed_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="licensed_daily_or_delayed_fund_flow",
        degradation_reason="authorized_feed_not_configured",
        missing_provider_reason="authorized_us_etf_flow_feed_not_configured",
        paid_data_likely_required=True,
        key_required=True,
    ),
    _capability_support_entry(
        "official_public.fed_liquidity",
        "fed_liquidity",
        provider_name="Official Fed Liquidity",
        source_type="official_public",
        source_tier="official_public",
        trust_level="score_grade_when_configured",
        freshness_expectation="daily_or_weekly_public_release_lag",
        degradation_reason="official_liquidity_contract_not_configured",
        missing_provider_reason="official_fed_liquidity_contract_not_configured",
        cache_required=True,
        background_refresh_recommended=True,
    ),
    _capability_support_entry(
        "official_public.cn_money_market_rates",
        "cn_money_market_rates",
        provider_name="Official CN Money Market Rates",
        source_type="missing",
        source_tier="official_public",
        trust_level="score_grade_when_configured",
        freshness_expectation="session_delayed_or_daily_official_fixing",
        degradation_reason="official_liquidity_contract_not_configured",
        missing_provider_reason="official_cn_money_market_rates_contract_not_configured",
        cache_required=True,
        background_refresh_recommended=True,
    ),
    _capability_support_entry(
        "official_or_authorized.fx_dxy",
        "fx_dxy",
        provider_name="Official or Authorized DXY",
        source_type="missing",
        source_tier="official_or_authorized_fx_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="continuous_session_or_delayed_fix_snapshot",
        degradation_reason="authorized_fx_contract_not_configured",
        missing_provider_reason="authorized_dxy_feed_not_configured",
        paid_data_likely_required=True,
        key_required=True,
    ),
    _capability_support_entry(
        "authorized.cn_hk_connect_flow",
        "cn_hk_connect_flow",
        provider_name="Authorized CN/HK Connect Flow",
        source_type="missing",
        source_tier="authorized_licensed_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="session_delayed_cross_border_flow_snapshot",
        degradation_reason="authorized_feed_not_configured",
        missing_provider_reason="authorized_cn_hk_connect_flow_feed_not_configured",
        paid_data_likely_required=True,
        key_required=True,
    ),
    _capability_support_entry(
        "exchange_or_broker_authorized.index_futures",
        "index_futures",
        provider_name="Exchange or Broker Authorized Index Futures",
        source_type="missing",
        source_tier="exchange_or_broker_authorized_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="extended_hours_delayed_or_realtime_index_futures",
        degradation_reason="authorized_feed_not_configured",
        missing_provider_reason="authorized_index_futures_feed_not_configured",
        paid_data_likely_required=True,
        key_required=True,
    ),
    _capability_support_entry(
        "authorized.real_sector_theme_flow",
        "real_sector_theme_flow_evidence",
        provider_name="Authorized Real Sector/Theme Flow",
        source_type="missing",
        source_tier="authorized_licensed_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="daily_or_intraday_sector_theme_flow_snapshot",
        degradation_reason="authorized_feed_not_configured",
        missing_provider_reason="authorized_real_sector_theme_flow_not_configured",
        paid_data_likely_required=True,
        key_required=True,
    ),
    _capability_support_entry(
        "baostock",
        "cn_adjust_factor",
        provider_name="baostock",
        source_type="public_proxy",
        source_tier="third_party_free_api",
        trust_level="usable_with_caution",
        freshness_expectation="t_plus_1_or_delayed",
        degradation_reason="baostock_provider_unavailable",
        missing_provider_reason="baostock_not_installed",
    ),
    _capability_support_entry(
        "baostock",
        "cn_basic_financials",
        provider_name="baostock",
        source_type="public_proxy",
        source_tier="third_party_free_api",
        trust_level="usable_with_caution",
        freshness_expectation="t_plus_1_or_delayed",
        degradation_reason="baostock_provider_unavailable",
        missing_provider_reason="baostock_not_installed",
    ),
    _capability_support_entry(
        "baostock",
        "cn_history_daily",
        provider_name="baostock",
        source_type="public_proxy",
        source_tier="third_party_free_api",
        trust_level="usable_with_caution",
        freshness_expectation="t_plus_1_or_delayed",
        degradation_reason="baostock_provider_unavailable",
        missing_provider_reason="baostock_not_installed",
    ),
    _capability_support_entry(
        "baostock",
        "cn_index_history_daily",
        provider_name="baostock",
        source_type="public_proxy",
        source_tier="third_party_free_api",
        trust_level="usable_with_caution",
        freshness_expectation="t_plus_1_or_delayed",
        degradation_reason="baostock_provider_unavailable",
        missing_provider_reason="baostock_not_installed",
    ),
    _capability_support_entry(
        "pytdx",
        "cn_history_daily",
        trust_level="usable_with_caution",
        freshness_expectation="best_effort_realtime_quote_and_daily_history",
        degradation_reason="pytdx_provider_unavailable",
        missing_provider_reason="pytdx_not_installed",
    ),
    _capability_support_entry(
        "pytdx",
        "cn_name_lookup",
        trust_level="usable_with_caution",
        freshness_expectation="best_effort_realtime_quote_and_daily_history",
        degradation_reason="pytdx_provider_unavailable",
        missing_provider_reason="pytdx_not_installed",
    ),
    _capability_support_entry(
        "pytdx",
        "cn_quote",
        trust_level="usable_with_caution",
        freshness_expectation="best_effort_realtime_quote_and_daily_history",
        degradation_reason="pytdx_provider_unavailable",
        missing_provider_reason="pytdx_not_installed",
    ),
    _capability_support_entry(
        "pytdx",
        "cn_realtime_quote",
        trust_level="usable_with_caution",
        freshness_expectation="best_effort_realtime_quote_and_daily_history",
        degradation_reason="pytdx_provider_unavailable",
        missing_provider_reason="pytdx_not_installed",
    ),
    _capability_support_entry(
        "akshare",
        "chip_distribution",
        trust_level="weak",
        freshness_expectation="best_effort_public_web_quote_snapshot_and_daily_history",
        degradation_reason="akshare_provider_unavailable",
        missing_provider_reason="akshare_not_installed",
    ),
    _capability_support_entry(
        "akshare",
        "cn_etf_history_daily",
        trust_level="weak",
        freshness_expectation="best_effort_public_web_quote_snapshot_and_daily_history",
        degradation_reason="akshare_provider_unavailable",
        missing_provider_reason="akshare_not_installed",
    ),
    _capability_support_entry(
        "akshare",
        "cn_etf_realtime_quote",
        trust_level="weak",
        freshness_expectation="best_effort_public_web_quote_snapshot_and_daily_history",
        degradation_reason="akshare_provider_unavailable",
        missing_provider_reason="akshare_not_installed",
    ),
    _capability_support_entry(
        "akshare",
        "cn_history_daily",
        trust_level="weak",
        freshness_expectation="best_effort_public_web_quote_snapshot_and_daily_history",
        degradation_reason="akshare_provider_unavailable",
        missing_provider_reason="akshare_not_installed",
    ),
    _capability_support_entry(
        "akshare",
        "cn_index_quote",
        trust_level="weak",
        freshness_expectation="best_effort_public_web_quote_snapshot_and_daily_history",
        degradation_reason="akshare_provider_unavailable",
        missing_provider_reason="akshare_not_installed",
    ),
    _capability_support_entry(
        "akshare",
        "cn_market_stats",
        trust_level="weak",
        freshness_expectation="best_effort_public_web_quote_snapshot_and_daily_history",
        degradation_reason="akshare_provider_unavailable",
        missing_provider_reason="akshare_not_installed",
    ),
    _capability_support_entry(
        "akshare",
        "cn_realtime_quote",
        trust_level="weak",
        freshness_expectation="best_effort_public_web_quote_snapshot_and_daily_history",
        degradation_reason="akshare_provider_unavailable",
        missing_provider_reason="akshare_not_installed",
    ),
    _capability_support_entry(
        "akshare",
        "cn_realtime_snapshot",
        trust_level="weak",
        freshness_expectation="best_effort_public_web_quote_snapshot_and_daily_history",
        degradation_reason="akshare_provider_unavailable",
        missing_provider_reason="akshare_not_installed",
    ),
    _capability_support_entry(
        "akshare",
        "cn_sector_rankings",
        trust_level="weak",
        freshness_expectation="best_effort_public_web_quote_snapshot_and_daily_history",
        degradation_reason="akshare_provider_unavailable",
        missing_provider_reason="akshare_not_installed",
    ),
    _capability_support_entry(
        "akshare",
        "cn_stock_list",
        trust_level="weak",
        freshness_expectation="best_effort_public_web_quote_snapshot_and_daily_history",
        degradation_reason="akshare_provider_unavailable",
        missing_provider_reason="akshare_not_installed",
    ),
    _capability_support_entry(
        "akshare",
        "hk_history_daily",
        trust_level="weak",
        freshness_expectation="best_effort_public_web_quote_snapshot_and_daily_history",
        degradation_reason="akshare_provider_unavailable",
        missing_provider_reason="akshare_not_installed",
    ),
    _capability_support_entry(
        "akshare",
        "hk_realtime_quote",
        trust_level="weak",
        freshness_expectation="best_effort_public_web_quote_snapshot_and_daily_history",
        degradation_reason="akshare_provider_unavailable",
        missing_provider_reason="akshare_not_installed",
    ),
    _capability_support_entry(
        "official_or_authorized.us_market_breadth",
        "us_market_breadth_constituents",
        provider_name="Official or Authorized US Market Breadth",
        source_type="missing",
        source_tier="official_or_authorized_licensed_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="licensed_daily_or_delayed_breadth_snapshot",
        degradation_reason="authorized_feed_not_configured",
        missing_provider_reason="authorized_us_market_breadth_feed_not_configured",
        paid_data_likely_required=True,
        key_required=True,
    ),
    _capability_support_entry(
        "official_or_authorized.us_market_breadth",
        "us_advancers_decliners",
        provider_name="Official or Authorized US Market Breadth",
        source_type="missing",
        source_tier="official_or_authorized_licensed_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="licensed_daily_or_delayed_breadth_snapshot",
        degradation_reason="authorized_feed_not_configured",
        missing_provider_reason="authorized_us_market_breadth_feed_not_configured",
        paid_data_likely_required=True,
        key_required=True,
    ),
    _capability_support_entry(
        "official_or_authorized.us_market_breadth",
        "us_new_highs_lows",
        provider_name="Official or Authorized US Market Breadth",
        source_type="missing",
        source_tier="official_or_authorized_licensed_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="licensed_daily_or_delayed_breadth_snapshot",
        degradation_reason="authorized_feed_not_configured",
        missing_provider_reason="authorized_us_market_breadth_feed_not_configured",
        paid_data_likely_required=True,
        key_required=True,
    ),
    _capability_support_entry(
        "official_or_authorized.us_market_breadth",
        "us_above_ma_breadth",
        provider_name="Official or Authorized US Market Breadth",
        source_type="missing",
        source_tier="official_or_authorized_licensed_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="licensed_daily_or_delayed_breadth_snapshot",
        degradation_reason="authorized_feed_not_configured",
        missing_provider_reason="authorized_us_market_breadth_feed_not_configured",
        paid_data_likely_required=True,
        key_required=True,
    ),
    _capability_support_entry(
        "official_or_authorized.us_market_breadth",
        "us_sector_breadth",
        provider_name="Official or Authorized US Market Breadth",
        source_type="missing",
        source_tier="official_or_authorized_licensed_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="licensed_daily_or_delayed_breadth_snapshot",
        degradation_reason="authorized_feed_not_configured",
        missing_provider_reason="authorized_us_market_breadth_feed_not_configured",
        paid_data_likely_required=True,
        key_required=True,
    ),
)
_PROVIDER_CAPABILITY_SUPPORT_BY_KEY = {
    (item.provider_id, item.capability): item for item in _PROVIDER_CAPABILITY_SUPPORT_CONTRACTS
}

_PROVIDER_SCORING_CONTRACTS = (
    ProviderScoringContract(
        provider_id="authorized.us_etf_flow",
        capability="us_etf_flow_daily",
        coverage_universe="licensed_us_listed_etf_universe",
        cadence="daily",
        freshness_floor="daily",
        coverage_ratio_floor=0.8,
        required_source_tier="authorized_licensed_feed",
        score_eligibility_gate="configured_authorized_feed_and_daily_freshness_and_min_coverage",
    ),
    ProviderScoringContract(
        provider_id="authorized.us_etf_flow",
        capability="us_etf_creation_redemption",
        coverage_universe="licensed_us_primary_etf_basket",
        cadence="daily",
        freshness_floor="daily",
        coverage_ratio_floor=0.8,
        required_source_tier="authorized_licensed_feed",
        score_eligibility_gate="configured_authorized_feed_and_daily_freshness_and_min_coverage",
    ),
    ProviderScoringContract(
        provider_id="authorized.us_etf_flow",
        capability="us_sector_etf_flow",
        coverage_universe="licensed_us_sector_etf_universe",
        cadence="daily",
        freshness_floor="daily",
        coverage_ratio_floor=0.8,
        required_source_tier="authorized_licensed_feed",
        score_eligibility_gate="configured_authorized_feed_and_daily_freshness_and_min_coverage",
    ),
    ProviderScoringContract(
        provider_id="official_public.cn_money_market_rates",
        capability="cn_money_market_rates",
        coverage_universe="dr007_shibor_repo_liquidity_rate_bundle",
        cadence="session_daily",
        freshness_floor="delayed",
        coverage_ratio_floor=1.0,
        required_source_tier="official_public",
        score_eligibility_gate="configured_official_rates_and_session_freshness_and_full_component_coverage",
    ),
    ProviderScoringContract(
        provider_id="official_public.fed_liquidity",
        capability="fed_liquidity",
        coverage_universe="rrp_tga_reserve_balances_release_bundle",
        cadence="daily_weekly",
        freshness_floor="delayed",
        coverage_ratio_floor=1.0,
        required_source_tier="official_public",
        score_eligibility_gate="configured_official_release_ids_and_cache_freshness_and_full_component_coverage",
    ),
    ProviderScoringContract(
        provider_id="official_or_authorized.fx_dxy",
        capability="fx_dxy",
        coverage_universe="dxy_reference_pair_bundle",
        cadence="continuous_session",
        freshness_floor="delayed",
        coverage_ratio_floor=1.0,
        required_source_tier="official_or_authorized_fx_feed",
        score_eligibility_gate="configured_official_or_authorized_dxy_authority_and_pair_context",
    ),
    ProviderScoringContract(
        provider_id="authorized.cn_hk_connect_flow",
        capability="cn_hk_connect_flow",
        coverage_universe="northbound_southbound_mainland_flow_bundle",
        cadence="session_daily",
        freshness_floor="delayed",
        coverage_ratio_floor=0.8,
        required_source_tier="authorized_licensed_feed",
        score_eligibility_gate="configured_cn_hk_connect_bundle_and_session_freshness_and_min_coverage",
    ),
    ProviderScoringContract(
        provider_id="exchange_or_broker_authorized.index_futures",
        capability="index_futures",
        coverage_universe="nq_es_ym_rty_extended_hours_bundle",
        cadence="extended_hours",
        freshness_floor="delayed",
        coverage_ratio_floor=1.0,
        required_source_tier="exchange_or_broker_authorized_feed",
        score_eligibility_gate="configured_authorized_index_futures_bundle_and_extended_hours_freshness",
    ),
    ProviderScoringContract(
        provider_id="authorized.real_sector_theme_flow",
        capability="real_sector_theme_flow_evidence",
        coverage_universe="licensed_sector_theme_flow_universe",
        cadence="daily_intraday",
        freshness_floor="delayed",
        coverage_ratio_floor=0.7,
        required_source_tier="authorized_licensed_feed",
        score_eligibility_gate="configured_sector_theme_flow_and_taxonomy_mapping_and_min_coverage",
    ),
    ProviderScoringContract(
        provider_id="official_or_authorized.us_market_breadth",
        capability="us_market_breadth_constituents",
        coverage_universe="nyse_nasdaq_listed_equity_universe",
        cadence="daily",
        freshness_floor="daily",
        coverage_ratio_floor=0.8,
        required_source_tier="official_or_authorized_licensed_feed",
        score_eligibility_gate="configured_official_or_authorized_feed_and_daily_freshness_and_min_coverage",
    ),
    ProviderScoringContract(
        provider_id="official_or_authorized.us_market_breadth",
        capability="us_advancers_decliners",
        coverage_universe="nyse_nasdaq_listed_equity_universe",
        cadence="daily",
        freshness_floor="daily",
        coverage_ratio_floor=0.8,
        required_source_tier="official_or_authorized_licensed_feed",
        score_eligibility_gate="configured_official_or_authorized_feed_and_daily_freshness_and_min_coverage",
    ),
    ProviderScoringContract(
        provider_id="official_or_authorized.us_market_breadth",
        capability="us_new_highs_lows",
        coverage_universe="nyse_nasdaq_listed_equity_universe",
        cadence="daily",
        freshness_floor="daily",
        coverage_ratio_floor=0.8,
        required_source_tier="official_or_authorized_licensed_feed",
        score_eligibility_gate="configured_official_or_authorized_feed_and_daily_freshness_and_min_coverage",
    ),
    ProviderScoringContract(
        provider_id="official_or_authorized.us_market_breadth",
        capability="us_above_ma_breadth",
        coverage_universe="configured_index_or_exchange_breadth_universe",
        cadence="daily",
        freshness_floor="daily",
        coverage_ratio_floor=0.8,
        required_source_tier="official_or_authorized_licensed_feed",
        score_eligibility_gate="configured_official_or_authorized_feed_and_daily_freshness_and_min_coverage",
    ),
    ProviderScoringContract(
        provider_id="official_or_authorized.us_market_breadth",
        capability="us_sector_breadth",
        coverage_universe="licensed_us_sector_breadth_basket",
        cadence="daily",
        freshness_floor="daily",
        coverage_ratio_floor=0.8,
        required_source_tier="official_or_authorized_licensed_feed",
        score_eligibility_gate="configured_official_or_authorized_feed_and_daily_freshness_and_min_coverage",
    ),
)
_PROVIDER_SCORING_CONTRACTS_BY_KEY = {
    (item.provider_id, item.capability): item for item in _PROVIDER_SCORING_CONTRACTS
}


def _provider_fit_entry(
    provider_id: str,
    provider_name: str,
    *,
    provider_category: str,
    source_tier: str,
    trust_level: str,
    freshness_expectation: str,
    paid_data_likely_required: bool,
    key_required: bool,
    cache_required: bool,
    background_refresh_recommended: bool,
    best_use_cases: tuple[str, ...],
    rejected_for: tuple[str, ...],
    not_recommended_for: tuple[str, ...],
    missing_provider_reason: str | None = None,
    plan_dependent: bool = False,
) -> ProviderFitMetadataContract:
    return ProviderFitMetadataContract(
        provider_name=provider_name,
        provider_id=provider_id,
        provider_category=provider_category,
        source_tier=source_tier,
        trust_level=trust_level,
        freshness_expectation=freshness_expectation,
        observation_only=True,
        score_contribution_allowed=False,
        paid_data_likely_required=paid_data_likely_required,
        key_required=key_required,
        live_tests_avoided=True,
        cache_required=cache_required,
        background_refresh_recommended=background_refresh_recommended,
        enabled_by_default=False,
        missing_provider_reason=missing_provider_reason,
        degradation_reason="provider_fit_metadata_only",
        plan_dependent=plan_dependent,
        best_use_cases=best_use_cases,
        rejected_for=rejected_for,
        not_recommended_for=not_recommended_for,
    )


_PROVIDER_FIT_METADATA = (
    _provider_fit_entry(
        "akshare_existing_baseline",
        "AkShare Existing Baseline",
        provider_category="cn_hk_existing_baseline",
        source_tier="unofficial_public_api",
        trust_level="weak",
        freshness_expectation="best_effort_public_web_quote_snapshot_and_daily_history",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=("cn_hk_observation_backfill", "delayed_market_observation"),
        rejected_for=("official_provenance", "score_inputs"),
        not_recommended_for=("live_quotes", "headline_indices"),
    ),
    _provider_fit_entry(
        "authorized.us_etf_flow",
        "Authorized US ETF Flow",
        provider_category="authorized_flow_dataset",
        source_tier="authorized_licensed_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="licensed_daily_or_delayed_fund_flow",
        paid_data_likely_required=True,
        key_required=True,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=(
            "us_etf_flow_authority",
            "daily_net_flow_authority",
            "creation_redemption_evidence",
            "sector_flow_authority",
            "licensed_us_etf_universe_coverage",
        ),
        rejected_for=(
            "runtime_unconfigured",
            "score_inputs_until_licensed",
            "freshness_unqualified",
            "coverage_unqualified",
        ),
        not_recommended_for=("proxy_replacements", "frontend_claims", "partial_coverage_scoring"),
        missing_provider_reason="authorized_us_etf_flow_feed_not_configured",
        plan_dependent=True,
    ),
    _provider_fit_entry(
        "authorized.cn_hk_connect_flow",
        "Authorized CN/HK Connect Flow",
        provider_category="authorized_cross_border_flow_dataset",
        source_tier="authorized_licensed_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="session_delayed_cross_border_flow_snapshot",
        paid_data_likely_required=True,
        key_required=True,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=(
            "cn_hk_connect_flow_authority",
            "northbound_flow_authority",
            "southbound_flow_authority",
            "mainland_flow_context",
        ),
        rejected_for=(
            "runtime_unconfigured",
            "score_inputs_until_licensed",
            "session_unqualified",
            "coverage_unqualified",
        ),
        not_recommended_for=("proxy_replacements", "frontend_claims", "partial_coverage_scoring"),
        missing_provider_reason="authorized_cn_hk_connect_flow_feed_not_configured",
        plan_dependent=True,
    ),
    _provider_fit_entry(
        "authorized.real_sector_theme_flow",
        "Authorized Real Sector/Theme Flow",
        provider_category="authorized_rotation_flow_dataset",
        source_tier="authorized_licensed_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="daily_or_intraday_sector_theme_flow_snapshot",
        paid_data_likely_required=True,
        key_required=True,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=(
            "rotation_real_flow_authority",
            "sector_theme_flow_evidence",
            "theme_headline_confirmation",
            "sector_theme_taxonomy_mapping",
        ),
        rejected_for=(
            "runtime_unconfigured",
            "score_inputs_until_licensed",
            "freshness_unqualified",
            "coverage_unqualified",
        ),
        not_recommended_for=("proxy_replacements", "frontend_claims", "taxonomy_only_rotation"),
        missing_provider_reason="authorized_real_sector_theme_flow_not_configured",
        plan_dependent=True,
    ),
    _provider_fit_entry(
        "official_public.cn_money_market_rates",
        "Official CN Money Market Rates",
        provider_category="official_macro_liquidity_contract",
        source_tier="official_public",
        trust_level="score_grade_when_configured",
        freshness_expectation="session_delayed_or_daily_official_fixing",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=(
            "china_liquidity_context",
            "dr007_authority",
            "shibor_authority",
            "repo_liquidity_rate_authority",
            "cn_money_market_session_calendar",
        ),
        rejected_for=(
            "runtime_unconfigured",
            "score_inputs_until_official_cache",
            "session_unqualified",
            "freshness_unqualified",
            "coverage_unqualified",
        ),
        not_recommended_for=(
            "proxy_replacements",
            "frontend_live_claims",
            "score_inputs_without_full_official_cache",
        ),
        missing_provider_reason="official_cn_money_market_rates_contract_not_configured",
        plan_dependent=True,
    ),
    _provider_fit_entry(
        "official_or_authorized.fx_dxy",
        "Official or Authorized DXY",
        provider_category="authorized_fx_macro_dataset",
        source_tier="official_or_authorized_fx_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="continuous_session_or_delayed_fix_snapshot",
        paid_data_likely_required=True,
        key_required=True,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=(
            "dxy_reference_authority",
            "usd_macro_context_authority",
            "major_fx_pair_crosscheck",
        ),
        rejected_for=(
            "runtime_unconfigured",
            "score_inputs_until_authorized",
            "session_unqualified",
            "freshness_unqualified",
            "coverage_unqualified",
        ),
        not_recommended_for=("proxy_replacements", "frontend_live_claims", "partial_coverage_scoring"),
        missing_provider_reason="authorized_dxy_feed_not_configured",
        plan_dependent=True,
    ),
    _provider_fit_entry(
        "alpha_vantage",
        "Alpha Vantage",
        provider_category="market_data_api",
        source_tier="gated_public_api",
        trust_level="usable_with_caution",
        freshness_expectation="plan_dependent_delayed_or_daily",
        paid_data_likely_required=True,
        key_required=True,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=("bounded_fundamentals_lookup", "manual_technical_reference"),
        rejected_for=("scanner_scoring", "live_quotes"),
        not_recommended_for=("high_fanout_requests", "intraday_decisions"),
        missing_provider_reason="alpha_vantage_key_not_configured",
        plan_dependent=True,
    ),
    _provider_fit_entry(
        "ashare",
        "Ashare",
        provider_category="cn_hk_observation",
        source_tier="unofficial_public_api",
        trust_level="weak",
        freshness_expectation="delayed_public_proxy",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=False,
        best_use_cases=("cn_market_observation", "research_backfill"),
        rejected_for=("official_quotes", "score_inputs"),
        not_recommended_for=("live_panels", "hkex_grade_quotes"),
    ),
    _provider_fit_entry(
        "baostock",
        "BaoStock",
        provider_category="cn_delayed_observation",
        source_tier="third_party_free_api",
        trust_level="usable_with_caution",
        freshness_expectation="t_plus_1_or_delayed",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=("a_share_delayed_history", "cn_observation_cache_fill"),
        rejected_for=("live_quotes", "score_inputs"),
        not_recommended_for=("premarket", "cn_hk_flows"),
    ),
    _provider_fit_entry(
        "binance_public",
        "Binance",
        provider_category="exchange_reference",
        source_tier="exchange_public",
        trust_level="usable_with_caution",
        freshness_expectation="near_real_time_venue_scoped",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=("crypto_venue_redundancy", "venue_scoped_observation"),
        rejected_for=("cross_venue_price_truth", "score_inputs"),
        not_recommended_for=("macro_conclusions", "fx_reference"),
    ),
    _provider_fit_entry(
        "coinbase_public",
        "Coinbase",
        provider_category="exchange_reference",
        source_tier="exchange_public",
        trust_level="usable_with_caution",
        freshness_expectation="near_real_time_venue_scoped",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=("crypto_venue_redundancy", "venue_scoped_observation"),
        rejected_for=("cross_venue_price_truth", "score_inputs"),
        not_recommended_for=("macro_conclusions", "fx_reference"),
    ),
    _provider_fit_entry(
        "efinance",
        "Efinance",
        provider_category="cn_hk_observation",
        source_tier="public_proxy",
        trust_level="weak",
        freshness_expectation="delayed_public_proxy",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=False,
        best_use_cases=("cn_snapshot_observation", "public_web_backfill"),
        rejected_for=("official_quotes", "score_inputs"),
        not_recommended_for=("live_headlines", "hkex_grade_quotes"),
    ),
    _provider_fit_entry(
        "finnhub",
        "Finnhub",
        provider_category="market_data_api",
        source_tier="gated_public_api",
        trust_level="usable_with_caution",
        freshness_expectation="plan_dependent_delayed_or_daily",
        paid_data_likely_required=True,
        key_required=True,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=("bounded_quote_enrichment", "company_news_reference"),
        rejected_for=("score_inputs", "provider_order_changes"),
        not_recommended_for=("scanner_fanout", "live_market_overview"),
        missing_provider_reason="finnhub_key_not_configured",
        plan_dependent=True,
    ),
    _provider_fit_entry(
        "fred_existing_baseline",
        "FRED Existing Baseline",
        provider_category="macro_baseline",
        source_tier="official_public",
        trust_level="usable_with_caution",
        freshness_expectation="daily_or_public_release",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=("macro_reference_expansion", "official_public_baseline"),
        rejected_for=("intraday_scoring", "live_quotes"),
        not_recommended_for=("premarket", "tick_level_refresh"),
    ),
    _provider_fit_entry(
        "official_public.fed_liquidity",
        "Official Fed Liquidity",
        provider_category="official_macro_liquidity_contract",
        source_tier="official_public",
        trust_level="score_grade_when_configured",
        freshness_expectation="daily_or_weekly_public_release_lag",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=(
            "federal_liquidity_context",
            "fed_rrp_balance_authority",
            "treasury_general_account_authority",
            "reserve_balances_authority",
            "federal_liquidity_release_calendar",
        ),
        rejected_for=(
            "runtime_unconfigured",
            "score_inputs_until_official_cache",
            "release_lag_unqualified",
            "freshness_unqualified",
            "coverage_unqualified",
        ),
        not_recommended_for=(
            "proxy_replacements",
            "frontend_live_claims",
            "score_inputs_without_full_official_cache",
        ),
        missing_provider_reason="official_fed_liquidity_contract_not_configured",
        plan_dependent=True,
    ),
    _provider_fit_entry(
        "exchange_or_broker_authorized.index_futures",
        "Exchange or Broker Authorized Index Futures",
        provider_category="authorized_index_futures_dataset",
        source_tier="exchange_or_broker_authorized_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="extended_hours_delayed_or_realtime_index_futures",
        paid_data_likely_required=True,
        key_required=True,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=(
            "index_futures_authority",
            "premarket_risk_context",
            "extended_hours_index_confirmation",
            "us_futures_bundle_coverage",
        ),
        rejected_for=(
            "runtime_unconfigured",
            "score_inputs_until_authorized",
            "session_unqualified",
            "freshness_unqualified",
            "coverage_unqualified",
        ),
        not_recommended_for=("proxy_replacements", "frontend_claims", "partial_coverage_scoring"),
        missing_provider_reason="authorized_index_futures_feed_not_configured",
        plan_dependent=True,
    ),
    _provider_fit_entry(
        "marketstack",
        "Marketstack",
        provider_category="market_data_api",
        source_tier="gated_public_api",
        trust_level="usable_with_caution",
        freshness_expectation="plan_dependent_delayed_or_daily",
        paid_data_likely_required=True,
        key_required=True,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=("bounded_quote_reference", "historical_observation_cache"),
        rejected_for=("score_inputs", "live_quotes"),
        not_recommended_for=("scanner_fanout", "broad_market_panels"),
        missing_provider_reason="marketstack_key_not_configured",
        plan_dependent=True,
    ),
    _provider_fit_entry(
        "nasdaq_data_link",
        "Nasdaq Data Link",
        provider_category="reference_dataset_api",
        source_tier="gated_public_api",
        trust_level="usable_with_caution",
        freshness_expectation="plan_dependent_dataset_release",
        paid_data_likely_required=True,
        key_required=True,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=("dataset_reference", "scheduled_cache_refresh"),
        rejected_for=("live_quotes", "score_inputs"),
        not_recommended_for=("premarket", "intraday_panels"),
        missing_provider_reason="nasdaq_data_link_key_not_configured",
        plan_dependent=True,
    ),
    _provider_fit_entry(
        "openbb_reference_only",
        "OpenBB",
        provider_category="integration_reference",
        source_tier="reference_wrapper",
        trust_level="reference_only",
        freshness_expectation="plan_dependent_reference_only",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=False,
        background_refresh_recommended=False,
        best_use_cases=("integration_planning", "provider_discovery_reference"),
        rejected_for=("source_of_truth", "score_inputs"),
        not_recommended_for=("official_provenance", "quote_freshness"),
        plan_dependent=True,
    ),
    _provider_fit_entry(
        "official_or_authorized.us_market_breadth",
        "Official or Authorized US Market Breadth",
        provider_category="authorized_breadth_dataset",
        source_tier="official_or_authorized_licensed_feed",
        trust_level="score_grade_when_configured",
        freshness_expectation="licensed_daily_or_delayed_breadth_snapshot",
        paid_data_likely_required=True,
        key_required=True,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=(
            "us_market_breadth_authority",
            "breadth_constituent_coverage",
            "advancers_decliners_authority",
            "new_highs_lows_authority",
            "above_ma_breadth_authority",
            "sector_breadth_confirmation",
            "nyse_nasdaq_exchange_coverage",
        ),
        rejected_for=(
            "runtime_unconfigured",
            "score_inputs_until_licensed",
            "freshness_unqualified",
            "coverage_unqualified",
        ),
        not_recommended_for=("proxy_replacements", "frontend_claims", "partial_coverage_scoring"),
        missing_provider_reason="authorized_us_market_breadth_feed_not_configured",
        plan_dependent=True,
    ),
    _provider_fit_entry(
        "pandas_datareader_fred",
        "pandas-datareader FRED",
        provider_category="macro_reference",
        source_tier="official_public",
        trust_level="usable_with_caution",
        freshness_expectation="daily_or_public_release",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=("macro_reference_expansion", "scheduled_release_backfill"),
        rejected_for=("live_quotes", "score_inputs"),
        not_recommended_for=("intraday_macro", "premarket"),
    ),
    _provider_fit_entry(
        "pandas_datareader_oecd",
        "pandas-datareader OECD",
        provider_category="macro_reference",
        source_tier="official_public",
        trust_level="usable_with_caution",
        freshness_expectation="daily_or_public_release",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=("macro_reference_expansion", "cross_country_research"),
        rejected_for=("live_quotes", "score_inputs"),
        not_recommended_for=("intraday_macro", "headline_panels"),
    ),
    _provider_fit_entry(
        "pandas_datareader_stooq",
        "pandas-datareader Stooq",
        provider_category="public_market_proxy",
        source_tier="public_proxy",
        trust_level="weak",
        freshness_expectation="delayed_public_proxy",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=False,
        best_use_cases=("delayed_history_reference", "research_cross_check"),
        rejected_for=("official_quotes", "score_inputs"),
        not_recommended_for=("live_panels", "fx_reference"),
    ),
    _provider_fit_entry(
        "pandas_datareader_world_bank",
        "pandas-datareader World Bank",
        provider_category="macro_reference",
        source_tier="official_public",
        trust_level="usable_with_caution",
        freshness_expectation="daily_or_public_release",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=("macro_reference_expansion", "structural_country_context"),
        rejected_for=("live_quotes", "score_inputs"),
        not_recommended_for=("intraday_macro", "headline_panels"),
    ),
    _provider_fit_entry(
        "pytdx_existing_baseline",
        "pytdx Existing Baseline",
        provider_category="cn_hk_existing_baseline",
        source_tier="unofficial_public_api",
        trust_level="usable_with_caution",
        freshness_expectation="best_effort_realtime_quote_and_daily_history",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=("cn_quote_observation", "baseline_health_reference"),
        rejected_for=("official_quotes", "score_inputs"),
        not_recommended_for=("headline_panels", "hkex_grade_quotes"),
    ),
    _provider_fit_entry(
        "qstock",
        "QStock",
        provider_category="cn_hk_observation",
        source_tier="public_proxy",
        trust_level="weak",
        freshness_expectation="delayed_public_proxy",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=False,
        best_use_cases=("cn_market_observation", "research_backfill"),
        rejected_for=("official_quotes", "score_inputs"),
        not_recommended_for=("live_panels", "cn_hk_flows"),
    ),
    _provider_fit_entry(
        "sec_edgar",
        "SEC EDGAR",
        provider_category="filings_reference",
        source_tier="official_public",
        trust_level="reliable_for_filings_metadata",
        freshness_expectation="filing_or_daily",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=("filings_metadata", "company_facts_reference"),
        rejected_for=("live_quotes", "score_inputs"),
        not_recommended_for=("premarket_quotes", "intraday_panels"),
    ),
    _provider_fit_entry(
        "treasury_existing_baseline",
        "US Treasury Existing Baseline",
        provider_category="macro_baseline",
        source_tier="official_public",
        trust_level="usable_with_caution",
        freshness_expectation="daily_or_public_release",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=("official_rate_reference", "macro_baseline_cross_check"),
        rejected_for=("live_quotes", "score_inputs"),
        not_recommended_for=("intraday_rates", "premarket"),
    ),
    _provider_fit_entry(
        "tushare_pro",
        "Tushare Pro",
        provider_category="market_data_api",
        source_tier="gated_public_api",
        trust_level="usable_with_caution",
        freshness_expectation="plan_dependent_delayed_or_daily",
        paid_data_likely_required=True,
        key_required=True,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=("a_share_delayed_observation", "cn_reference_enrichment"),
        rejected_for=("score_inputs", "provider_order_changes"),
        not_recommended_for=("live_panels", "cn_hk_flows"),
        missing_provider_reason="tushare_pro_key_not_configured",
        plan_dependent=True,
    ),
    _provider_fit_entry(
        "twelve_data",
        "Twelve Data",
        provider_category="market_data_api",
        source_tier="gated_public_api",
        trust_level="usable_with_caution",
        freshness_expectation="plan_dependent_delayed_or_daily",
        paid_data_likely_required=True,
        key_required=True,
        cache_required=True,
        background_refresh_recommended=True,
        best_use_cases=("bounded_quote_reference", "fx_crypto_cross_check"),
        rejected_for=("score_inputs", "live_quotes"),
        not_recommended_for=("scanner_fanout", "market_overview_runtime"),
        missing_provider_reason="twelve_data_key_not_configured",
        plan_dependent=True,
    ),
    _provider_fit_entry(
        "yahooquery",
        "Yahooquery",
        provider_category="baseline_proxy_observation",
        source_tier="unofficial_public_api",
        trust_level="weak",
        freshness_expectation="delayed_public_proxy",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=False,
        best_use_cases=("research_backfill", "delayed_observation_cross_check"),
        rejected_for=("official_quotes", "score_inputs"),
        not_recommended_for=("live_panels", "headline_indices"),
    ),
    _provider_fit_entry(
        "yfinance_current_baseline",
        "yfinance Current Baseline",
        provider_category="baseline_proxy_observation",
        source_tier="unofficial_public_api",
        trust_level="weak",
        freshness_expectation="delayed_public_proxy",
        paid_data_likely_required=False,
        key_required=False,
        cache_required=True,
        background_refresh_recommended=False,
        best_use_cases=("baseline_cross_check", "delayed_market_observation"),
        rejected_for=("official_quotes", "score_inputs"),
        not_recommended_for=("live_panels", "headline_indices"),
    ),
)
_PROVIDER_FIT_METADATA_BY_ID = {item.provider_id: item for item in _PROVIDER_FIT_METADATA}


def _build_provider_dry_run_probe_contract(
    entry: ProviderFitMetadataContract,
) -> ProviderDryRunProbeContract:
    missing_provider_reason = entry.missing_provider_reason if entry.key_required else None
    return ProviderDryRunProbeContract(
        provider_name=entry.provider_name,
        provider_id=entry.provider_id,
        enabled_by_default=False,
        reason_code="provider_fit_metadata_only",
        network_call_executed=False,
        no_default_live_http_calls=True,
        http_method="NONE",
        key_required=entry.key_required,
        required_credential_count=1 if entry.key_required else 0,
        configured_credential_count=0,
        requires_credential_presence_only=entry.key_required,
        live_tests_avoided=entry.live_tests_avoided,
        cache_required=entry.cache_required,
        background_refresh_recommended=entry.background_refresh_recommended,
        observation_only=entry.observation_only,
        score_contribution_allowed=entry.score_contribution_allowed,
        raw_credential_values_included=False,
        provider_payload_values_included=False,
        response_bodies_included=False,
        missing_provider_reason=missing_provider_reason,
        degradation_reason=entry.degradation_reason,
    )


_PROVIDER_DRY_RUN_PROBE_CONTRACTS = tuple(
    _build_provider_dry_run_probe_contract(item)
    for item in sorted(_PROVIDER_FIT_METADATA, key=lambda item: item.provider_id)
)
_PROVIDER_DRY_RUN_PROBE_BY_ID = {
    item.provider_id: item for item in _PROVIDER_DRY_RUN_PROBE_CONTRACTS
}


def _normalize_provider_id(provider_id: str) -> str:
    return str(provider_id or "").strip().lower().replace("-", "_")


def _normalize_domain(domain: ProviderDomain | str) -> str:
    return domain.value if isinstance(domain, ProviderDomain) else str(domain or "").strip().lower()


def _normalize_capability(capability: str) -> str:
    return str(capability or "").strip().lower()


def list_provider_capabilities() -> tuple[ProviderCapability, ...]:
    """Return provider capability metadata sorted by provider id."""

    return tuple(_CAPABILITIES_BY_ID[key] for key in sorted(_CAPABILITIES_BY_ID))


def get_provider_capability(provider_id: str) -> Optional[ProviderCapability]:
    """Return metadata for a provider id, or ``None`` when unknown."""

    return _CAPABILITIES_BY_ID.get(_normalize_provider_id(provider_id))


def list_provider_capability_support_contracts(
    provider_id: str | None = None,
) -> tuple[ProviderCapabilitySupportContract, ...]:
    """Return deterministic provider/capability support metadata for CN observation providers."""

    if provider_id is None:
        return tuple(_PROVIDER_CAPABILITY_SUPPORT_CONTRACTS)

    normalized_provider = _normalize_provider_id(provider_id)
    return tuple(
        item
        for item in _PROVIDER_CAPABILITY_SUPPORT_CONTRACTS
        if item.provider_id == normalized_provider
    )


def get_provider_capability_support_contract(
    provider_id: str,
    capability: str,
) -> Optional[ProviderCapabilitySupportContract]:
    """Return provider/capability support metadata, or ``None`` when unsupported."""

    return _PROVIDER_CAPABILITY_SUPPORT_BY_KEY.get(
        (_normalize_provider_id(provider_id), _normalize_capability(capability))
    )


def list_provider_scoring_contracts(
    provider_id: str | None = None,
) -> tuple[ProviderScoringContract, ...]:
    """Return deterministic score-gate metadata for authorized flow/breadth contracts."""

    if provider_id is None:
        return tuple(
            sorted(
                _PROVIDER_SCORING_CONTRACTS,
                key=lambda item: (item.provider_id, item.capability),
            )
        )

    normalized_provider = _normalize_provider_id(provider_id)
    return tuple(
        item for item in _PROVIDER_SCORING_CONTRACTS if item.provider_id == normalized_provider
    )


def get_provider_scoring_contract(
    provider_id: str,
    capability: str,
) -> Optional[ProviderScoringContract]:
    """Return score-gate metadata for a provider/capability pair."""

    return _PROVIDER_SCORING_CONTRACTS_BY_KEY.get(
        (_normalize_provider_id(provider_id), _normalize_capability(capability))
    )


def list_provider_fit_metadata(
    provider_id: str | None = None,
) -> tuple[ProviderFitMetadataContract, ...]:
    """Return inert provider-fit metadata for audited but unwired provider candidates."""

    if provider_id is None:
        return tuple(_PROVIDER_FIT_METADATA_BY_ID[key] for key in sorted(_PROVIDER_FIT_METADATA_BY_ID))

    item = get_provider_fit_metadata(provider_id)
    return (item,) if item is not None else ()


def get_provider_fit_metadata(provider_id: str) -> Optional[ProviderFitMetadataContract]:
    """Return inert provider-fit metadata, or ``None`` when unknown."""

    return _PROVIDER_FIT_METADATA_BY_ID.get(_normalize_provider_id(provider_id))


def list_provider_dry_run_probe_contracts(
    provider_id: str | None = None,
) -> tuple[ProviderDryRunProbeContract, ...]:
    """Return metadata-only dry-run probe contracts for audited provider candidates."""

    if provider_id is None:
        return tuple(_PROVIDER_DRY_RUN_PROBE_CONTRACTS)

    item = get_provider_dry_run_probe_contract(provider_id)
    return (item,) if item is not None else ()


def get_provider_dry_run_probe_contract(
    provider_id: str,
) -> Optional[ProviderDryRunProbeContract]:
    """Return a metadata-only dry-run probe contract, or ``None`` when unknown."""

    return _PROVIDER_DRY_RUN_PROBE_BY_ID.get(_normalize_provider_id(provider_id))


def providers_for_domain(domain: ProviderDomain | str) -> tuple[ProviderCapability, ...]:
    """Return providers declaring a domain, sorted by domain priority hint."""

    normalized_domain = _normalize_domain(domain)
    providers = [
        capability
        for capability in _CAPABILITIES
        if normalized_domain in {item.value for item in capability.domains}
    ]
    return tuple(
        sorted(
            providers,
            key=lambda capability: (
                capability.default_priority_by_domain.get(normalized_domain, 999),
                capability.provider_id,
            ),
        )
    )


def is_provider_allowed_for_scanner(provider_id: str) -> bool:
    """Return whether provider metadata allows scanner use in Phase 1 policy."""

    capability = get_provider_capability(provider_id)
    return bool(capability and capability.scanner_allowed)


def is_provider_allowed_for_backtest(provider_id: str) -> bool:
    """Return whether provider metadata allows backtest use without live calls."""

    capability = get_provider_capability(provider_id)
    return bool(capability and capability.backtest_allowed)


def recommended_ttl(provider_id: str, domain: ProviderDomain | str) -> Optional[int]:
    """Return recommended TTL seconds for a provider/domain pair."""

    capability = get_provider_capability(provider_id)
    if capability is None:
        return None
    return capability.recommended_ttl_seconds_by_domain.get(_normalize_domain(domain))


__all__ = [
    "BacktestUsage",
    "FreshnessClass",
    "ProviderCapability",
    "ProviderCapabilitySupportContract",
    "ProviderDryRunProbeContract",
    "ProviderDomain",
    "ProviderFitMetadataContract",
    "ProviderMarket",
    "ProviderQuotaClass",
    "ProviderScoringContract",
    "ScannerUsage",
    "get_provider_capability",
    "get_provider_capability_support_contract",
    "get_provider_dry_run_probe_contract",
    "get_provider_fit_metadata",
    "get_provider_scoring_contract",
    "is_provider_allowed_for_backtest",
    "is_provider_allowed_for_scanner",
    "list_provider_capability_support_contracts",
    "list_provider_dry_run_probe_contracts",
    "list_provider_capabilities",
    "list_provider_fit_metadata",
    "list_provider_scoring_contracts",
    "providers_for_domain",
    "recommended_ttl",
]
