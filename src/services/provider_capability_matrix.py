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


def _normalize_provider_id(provider_id: str) -> str:
    return str(provider_id or "").strip().lower().replace("-", "_")


def _normalize_domain(domain: ProviderDomain | str) -> str:
    return domain.value if isinstance(domain, ProviderDomain) else str(domain or "").strip().lower()


def list_provider_capabilities() -> tuple[ProviderCapability, ...]:
    """Return provider capability metadata sorted by provider id."""

    return tuple(_CAPABILITIES_BY_ID[key] for key in sorted(_CAPABILITIES_BY_ID))


def get_provider_capability(provider_id: str) -> Optional[ProviderCapability]:
    """Return metadata for a provider id, or ``None`` when unknown."""

    return _CAPABILITIES_BY_ID.get(_normalize_provider_id(provider_id))


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
