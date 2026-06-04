# -*- coding: utf-8 -*-
"""Pure helper-only Home/single-stock source capability authority matrix."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


SINGLE_STOCK_SOURCE_CAPABILITY_MATRIX_VERSION = "single_stock_source_capability_matrix_v1"

EVIDENCE_DOMAINS = (
    "priceHistory",
    "technicals",
    "fundamentals",
    "earnings",
    "filings",
    "news",
    "catalysts",
    "sentiment",
    "valuation",
    "sectorTheme",
    "macroLiquidity",
)
AUTHORITY_TIERS = (
    "score_grade",
    "observation_only",
    "fallback",
    "fixture_demo",
    "unavailable",
    "unknown",
)
FRESHNESS_CLASSES = (
    "realtime",
    "local",
    "daily",
    "delayed",
    "manual_review",
    "fixture",
    "unknown",
)
_SOURCE_ID_ALIASES = {
    "alpaca": "alpaca",
    "alpha_vantage": "alpha_vantage",
    "cache/local_fixture": "cache_local_fixture",
    "cache_local_fixture": "cache_local_fixture",
    "finnhub": "finnhub",
    "fmp": "fmp",
    "fred": "fred",
    "gnews": "gnews",
    "local_fixture": "cache_local_fixture",
    "local_us_parquet": "local_us_parquet",
    "manual": "manual_unknown",
    "manual_unknown": "manual_unknown",
    "news": "gnews",
    "polygon": "polygon",
    "treasury": "treasury",
    "twelve_data": "twelvedata",
    "twelvedata": "twelvedata",
    "unknown": "manual_unknown",
    "yahoo": "yfinance",
    "yahoo_finance": "yfinance",
    "yahoo_yfinance": "yfinance",
    "yfinance": "yfinance",
}
_DOMAIN_ALIASES = {
    "catalyst": "catalysts",
    "catalysts": "catalysts",
    "earnings": "earnings",
    "filing": "filings",
    "filings": "filings",
    "fundamental": "fundamentals",
    "fundamentals": "fundamentals",
    "macro": "macroLiquidity",
    "macro_liquidity": "macroLiquidity",
    "macroliquidity": "macroLiquidity",
    "news": "news",
    "price_history": "priceHistory",
    "pricehistory": "priceHistory",
    "sector_theme": "sectorTheme",
    "sectortheme": "sectorTheme",
    "sentiment": "sentiment",
    "technical": "technicals",
    "technicals": "technicals",
    "valuation": "valuation",
}
_AUTHORITY_RANK = {
    "unknown": 0,
    "unavailable": 1,
    "fixture_demo": 2,
    "fallback": 3,
    "observation_only": 4,
    "score_grade": 5,
}
_FRESHNESS_RANK = {
    "unknown": 0,
    "fixture": 1,
    "manual_review": 2,
    "delayed": 3,
    "daily": 4,
    "local": 5,
    "realtime": 6,
}
_MARKET_ORDER = {
    "us": 0,
    "hk": 1,
    "cn": 2,
    "global": 3,
    "macro": 4,
}


@dataclass(frozen=True, slots=True)
class _DomainCapabilitySpec:
    authority_tier: str
    freshness_class: str
    use_case: tuple[str, ...]
    limitations: tuple[str, ...]
    score_contribution_allowed: bool
    fallback_or_proxy: bool
    next_evidence_needed: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _SourceSpec:
    source_id: str
    display_label: str
    market_coverage: tuple[str, ...]
    known_domains: tuple[str, ...]
    domain_specs: Mapping[str, _DomainCapabilitySpec]
    default_freshness_class: str = "unknown"


def _capability(
    *,
    authority_tier: str,
    freshness_class: str,
    use_case: Sequence[str],
    limitations: Sequence[str],
    score_contribution_allowed: bool,
    fallback_or_proxy: bool,
    next_evidence_needed: Sequence[str],
) -> _DomainCapabilitySpec:
    return _DomainCapabilitySpec(
        authority_tier=authority_tier,
        freshness_class=freshness_class,
        use_case=tuple(str(item) for item in use_case if str(item).strip()),
        limitations=tuple(str(item) for item in limitations if str(item).strip()),
        score_contribution_allowed=bool(score_contribution_allowed),
        fallback_or_proxy=bool(fallback_or_proxy),
        next_evidence_needed=tuple(str(item) for item in next_evidence_needed if str(item).strip()),
    )


_SOURCE_SPECS: dict[str, _SourceSpec] = {
    "local_us_parquet": _SourceSpec(
        source_id="local_us_parquet",
        display_label="Local US Parquet",
        market_coverage=("us",),
        known_domains=("priceHistory", "technicals"),
        default_freshness_class="local",
        domain_specs={
            "priceHistory": _capability(
                authority_tier="score_grade",
                freshness_class="local",
                use_case=("local_first_history", "deterministic_daily_bars"),
                limitations=("Not yet wired into the current Home runtime path.",),
                score_contribution_allowed=True,
                fallback_or_proxy=False,
                next_evidence_needed=(),
            ),
            "technicals": _capability(
                authority_tier="score_grade",
                freshness_class="local",
                use_case=("local_derived_technicals", "history_backed_indicator_rebuild"),
                limitations=("Requires explicit Home adoption before runtime can claim this authority.",),
                score_contribution_allowed=True,
                fallback_or_proxy=False,
                next_evidence_needed=(),
            ),
        },
    ),
    "alpaca": _SourceSpec(
        source_id="alpaca",
        display_label="Alpaca Market Data",
        market_coverage=("us",),
        known_domains=("priceHistory",),
        default_freshness_class="realtime",
        domain_specs={
            "priceHistory": _capability(
                authority_tier="score_grade",
                freshness_class="realtime",
                use_case=("configured_quote_enrichment", "configured_ohlcv_reference"),
                limitations=("Entitlement and feed selection can downgrade realtime posture.",),
                score_contribution_allowed=True,
                fallback_or_proxy=False,
                next_evidence_needed=(),
            ),
        },
    ),
    "yfinance": _SourceSpec(
        source_id="yfinance",
        display_label="Yahoo Finance / yfinance",
        market_coverage=("us", "hk", "cn", "global"),
        known_domains=("priceHistory", "fundamentals", "earnings", "valuation"),
        default_freshness_class="delayed",
        domain_specs={
            "priceHistory": _capability(
                authority_tier="observation_only",
                freshness_class="delayed",
                use_case=("delayed_history_cross_check", "cheap_public_proxy_baseline"),
                limitations=("Unofficial and often delayed; do not treat as decision-grade live data.",),
                score_contribution_allowed=False,
                fallback_or_proxy=True,
                next_evidence_needed=("补充更高授权价格历史来源",),
            ),
            "fundamentals": _capability(
                authority_tier="observation_only",
                freshness_class="delayed",
                use_case=("fundamentals_cross_check", "cheap_research_baseline"),
                limitations=("Field freshness and provenance are weaker than bounded licensed sources.",),
                score_contribution_allowed=False,
                fallback_or_proxy=True,
                next_evidence_needed=("补充更高授权基本面来源",),
            ),
            "earnings": _capability(
                authority_tier="observation_only",
                freshness_class="delayed",
                use_case=("quarterly_series_cross_check", "fallback_earnings_reference"),
                limitations=("Quarterly series are useful for observation, not for direct score authority.",),
                score_contribution_allowed=False,
                fallback_or_proxy=True,
                next_evidence_needed=("补充更高授权财报来源",),
            ),
            "valuation": _capability(
                authority_tier="observation_only",
                freshness_class="delayed",
                use_case=("valuation_cross_check", "public_proxy_multiple_check"),
                limitations=("Valuation multiples depend on delayed public proxy data.",),
                score_contribution_allowed=False,
                fallback_or_proxy=True,
                next_evidence_needed=("补充更高授权估值来源",),
            ),
        },
    ),
    "polygon": _SourceSpec(
        source_id="polygon",
        display_label="Polygon",
        market_coverage=("us",),
        known_domains=(),
        default_freshness_class="unknown",
        domain_specs={},
    ),
    "alpha_vantage": _SourceSpec(
        source_id="alpha_vantage",
        display_label="Alpha Vantage",
        market_coverage=("us", "global"),
        known_domains=("fundamentals", "earnings", "technicals", "valuation"),
        default_freshness_class="manual_review",
        domain_specs={
            "fundamentals": _capability(
                authority_tier="fallback",
                freshness_class="manual_review",
                use_case=("deep_fundamentals_reference", "last_resort_overview_lookup"),
                limitations=("Very scarce quota; use only as bounded fallback evidence.",),
                score_contribution_allowed=False,
                fallback_or_proxy=True,
                next_evidence_needed=("补充主线基本面来源",),
            ),
            "earnings": _capability(
                authority_tier="fallback",
                freshness_class="manual_review",
                use_case=("income_statement_fallback", "manual_earnings_reference"),
                limitations=("Free quota is scarce and freshness requires manual review.",),
                score_contribution_allowed=False,
                fallback_or_proxy=True,
                next_evidence_needed=("补充主线财报来源",),
            ),
            "technicals": _capability(
                authority_tier="fallback",
                freshness_class="manual_review",
                use_case=("external_indicator_cross_check", "last_resort_technical_reference"),
                limitations=("External technical indicators are usually avoidable and quota-constrained.",),
                score_contribution_allowed=False,
                fallback_or_proxy=True,
                next_evidence_needed=("补充主线技术面来源",),
            ),
            "valuation": _capability(
                authority_tier="fallback",
                freshness_class="manual_review",
                use_case=("valuation_fallback_reference", "manual_multiple_cross_check"),
                limitations=("Valuation support is fallback-grade and not suited for direct score contribution.",),
                score_contribution_allowed=False,
                fallback_or_proxy=True,
                next_evidence_needed=("补充主线估值来源",),
            ),
        },
    ),
    "finnhub": _SourceSpec(
        source_id="finnhub",
        display_label="Finnhub",
        market_coverage=("us",),
        known_domains=("fundamentals", "news"),
        default_freshness_class="daily",
        domain_specs={
            "fundamentals": _capability(
                authority_tier="observation_only",
                freshness_class="daily",
                use_case=("bounded_metrics_fallback", "company_metric_cross_check"),
                limitations=("Plan dependence and per-symbol fanout mean Home should not overclaim score authority.",),
                score_contribution_allowed=False,
                fallback_or_proxy=False,
                next_evidence_needed=("补充主线基本面来源",),
            ),
            "news": _capability(
                authority_tier="observation_only",
                freshness_class="daily",
                use_case=("company_news_reference", "bounded_news_cross_check"),
                limitations=("Quota and entitlement posture vary by plan; keep as observation-only by default.",),
                score_contribution_allowed=False,
                fallback_or_proxy=False,
                next_evidence_needed=("补充更稳定新闻证据",),
            ),
        },
    ),
    "fmp": _SourceSpec(
        source_id="fmp",
        display_label="Financial Modeling Prep",
        market_coverage=("us", "global"),
        known_domains=("priceHistory", "fundamentals", "earnings", "valuation"),
        default_freshness_class="daily",
        domain_specs={
            "priceHistory": _capability(
                authority_tier="score_grade",
                freshness_class="daily",
                use_case=("bounded_ohlcv_reference", "supplemental_history_capture"),
                limitations=("Avoid broad OHLCV fanout when local deterministic history can satisfy the need.",),
                score_contribution_allowed=True,
                fallback_or_proxy=False,
                next_evidence_needed=(),
            ),
            "fundamentals": _capability(
                authority_tier="score_grade",
                freshness_class="daily",
                use_case=("primary_us_fundamentals", "statement_normalization"),
                limitations=("Best suited for bounded single-stock fundamentals, not scanner-wide fanout.",),
                score_contribution_allowed=True,
                fallback_or_proxy=False,
                next_evidence_needed=(),
            ),
            "earnings": _capability(
                authority_tier="score_grade",
                freshness_class="daily",
                use_case=("quarterly_financial_reference", "bounded_earnings_series"),
                limitations=("Authority depends on per-field validation and freshness gates in downstream assembly.",),
                score_contribution_allowed=True,
                fallback_or_proxy=False,
                next_evidence_needed=(),
            ),
            "valuation": _capability(
                authority_tier="score_grade",
                freshness_class="daily",
                use_case=("valuation_multiple_support", "primary_valuation_reference"),
                limitations=("Valuation still requires downstream freshness and completeness checks.",),
                score_contribution_allowed=True,
                fallback_or_proxy=False,
                next_evidence_needed=(),
            ),
        },
    ),
    "twelvedata": _SourceSpec(
        source_id="twelvedata",
        display_label="Twelve Data",
        market_coverage=("us", "hk"),
        known_domains=("priceHistory",),
        default_freshness_class="delayed",
        domain_specs={
            "priceHistory": _capability(
                authority_tier="observation_only",
                freshness_class="delayed",
                use_case=("bounded_quote_reference", "hk_us_ohlcv_cross_check"),
                limitations=("Quota is limited and Home runtime wiring is not currently proven for single-stock authority.",),
                score_contribution_allowed=False,
                fallback_or_proxy=False,
                next_evidence_needed=("补充主线价格历史来源",),
            ),
        },
    ),
    "gnews": _SourceSpec(
        source_id="gnews",
        display_label="GNews",
        market_coverage=("global",),
        known_domains=("news", "catalysts"),
        default_freshness_class="daily",
        domain_specs={
            "news": _capability(
                authority_tier="observation_only",
                freshness_class="daily",
                use_case=("top_n_news_enrichment", "recent_company_news_reference"),
                limitations=("Generic news quota is scarce and should remain observation-only by default.",),
                score_contribution_allowed=False,
                fallback_or_proxy=False,
                next_evidence_needed=("补充结构化新闻保留与排序证据",),
            ),
            "catalysts": _capability(
                authority_tier="observation_only",
                freshness_class="daily",
                use_case=("event_headline_reference", "recent_catalyst_observation"),
                limitations=("Catalyst importance still needs bounded ranking and preservation downstream.",),
                score_contribution_allowed=False,
                fallback_or_proxy=False,
                next_evidence_needed=("补充结构化催化剂证据",),
            ),
        },
    ),
    "fred": _SourceSpec(
        source_id="fred",
        display_label="FRED Existing Baseline",
        market_coverage=("us", "macro"),
        known_domains=("macroLiquidity",),
        default_freshness_class="daily",
        domain_specs={
            "macroLiquidity": _capability(
                authority_tier="observation_only",
                freshness_class="daily",
                use_case=("official_macro_baseline", "macro_reference_expansion"),
                limitations=("Official public release cadence is delayed and not intraday score-grade by default.",),
                score_contribution_allowed=False,
                fallback_or_proxy=False,
                next_evidence_needed=("补充官方缓存合格与覆盖证据",),
            ),
        },
    ),
    "treasury": _SourceSpec(
        source_id="treasury",
        display_label="US Treasury Existing Baseline",
        market_coverage=("us", "macro"),
        known_domains=("macroLiquidity",),
        default_freshness_class="daily",
        domain_specs={
            "macroLiquidity": _capability(
                authority_tier="observation_only",
                freshness_class="daily",
                use_case=("official_rate_reference", "macro_baseline_cross_check"),
                limitations=("Daily public release cadence is unsuitable for intraday score authority.",),
                score_contribution_allowed=False,
                fallback_or_proxy=False,
                next_evidence_needed=("补充官方利率缓存与时效证据",),
            ),
        },
    ),
    "cache_local_fixture": _SourceSpec(
        source_id="cache_local_fixture",
        display_label="Cache / Local Fixture",
        market_coverage=("us", "hk", "cn", "global", "macro"),
        known_domains=EVIDENCE_DOMAINS,
        default_freshness_class="fixture",
        domain_specs={
            domain: _capability(
                authority_tier="fixture_demo",
                freshness_class="fixture",
                use_case=("demo_only", "bounded_test_fixture"),
                limitations=("Fixture/cache-local demo data cannot grant score authority.",),
                score_contribution_allowed=False,
                fallback_or_proxy=True,
                next_evidence_needed=("补充真实来源证据",),
            )
            for domain in EVIDENCE_DOMAINS
        },
    ),
    "manual_unknown": _SourceSpec(
        source_id="manual_unknown",
        display_label="Manual / Unknown",
        market_coverage=("global",),
        known_domains=EVIDENCE_DOMAINS,
        default_freshness_class="unknown",
        domain_specs={
            domain: _capability(
                authority_tier="unknown",
                freshness_class="unknown",
                use_case=("manual_review", "unclassified_source_observation"),
                limitations=("Repository wiring does not prove this source/domain pair for Home single-stock use.",),
                score_contribution_allowed=False,
                fallback_or_proxy=False,
                next_evidence_needed=("补充来源身份与授权证据",),
            )
            for domain in EVIDENCE_DOMAINS
        },
    ),
}


def normalize_single_stock_source_id(source_id: str | None) -> str:
    normalized = str(source_id or "").strip().lower().replace("-", "_")
    return _SOURCE_ID_ALIASES.get(normalized, "manual_unknown")


def normalize_single_stock_evidence_domain(domain: str | None) -> str:
    normalized = str(domain or "").strip()
    if normalized in EVIDENCE_DOMAINS:
        return normalized
    lowered = normalized.lower()
    return _DOMAIN_ALIASES.get(lowered, "unknown")


def list_single_stock_source_capabilities() -> list[dict[str, Any]]:
    """Return the full inert matrix for known Home/single-stock sources."""

    items = [get_single_stock_source_capability(source_id) for source_id in sorted(_SOURCE_SPECS)]
    return deepcopy(items)


def get_single_stock_source_capability(source_id: str | None) -> dict[str, Any]:
    """Return all per-domain capability entries for a source."""

    normalized_source = normalize_single_stock_source_id(source_id)
    spec = _SOURCE_SPECS[normalized_source]
    proven_domains = [domain for domain in EVIDENCE_DOMAINS if domain in spec.known_domains]
    domain_capabilities = {
        domain: _domain_capability_dict(normalized_source, domain, proven_domains)
        for domain in EVIDENCE_DOMAINS
    }
    return {
        "contractVersion": SINGLE_STOCK_SOURCE_CAPABILITY_MATRIX_VERSION,
        "sourceId": spec.source_id,
        "displayLabel": spec.display_label,
        "domains": proven_domains,
        "domainCapabilities": domain_capabilities,
    }


def get_single_stock_source_domain_capability(source_id: str | None, domain: str | None) -> dict[str, Any]:
    """Return one fail-closed domain capability entry for a source/domain pair."""

    normalized_source = normalize_single_stock_source_id(source_id)
    normalized_domain = normalize_single_stock_evidence_domain(domain)
    if normalized_domain not in EVIDENCE_DOMAINS:
        normalized_domain = "unknown"

    spec = _SOURCE_SPECS[normalized_source]
    proven_domains = [item for item in EVIDENCE_DOMAINS if item in spec.known_domains]
    if normalized_domain == "unknown":
        return _unknown_domain_capability(spec, str(domain or ""), proven_domains)
    return _domain_capability_dict(normalized_source, normalized_domain, proven_domains)


def summarize_source_capabilities_by_domain(source_summary: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Summarize the strongest known capability posture per evidence domain."""

    payload = dict(source_summary or {})
    summary: dict[str, dict[str, Any]] = {}
    for raw_domain, raw_sources in payload.items():
        domain = normalize_single_stock_evidence_domain(raw_domain)
        if domain not in EVIDENCE_DOMAINS:
            continue

        source_ids = _extract_source_ids(raw_sources)
        if not source_ids:
            source_ids = ["manual_unknown"]
        capabilities = [get_single_stock_source_domain_capability(source_id, domain) for source_id in source_ids]
        best = max(capabilities, key=_capability_sort_key)
        score_allowed = any(item["scoreContributionAllowed"] is True for item in capabilities)
        market_coverage = _merge_market_coverage(capabilities)
        limitations = _merge_unique_lists(item["limitations"] for item in capabilities)
        next_evidence = _merge_unique_lists(item["nextEvidenceNeeded"] for item in capabilities)
        summary[domain] = {
            "domain": domain,
            "sourceIds": [item["sourceId"] for item in capabilities],
            "bestAuthorityTier": best["authorityTier"],
            "freshnessClass": best["freshnessClass"],
            "marketCoverage": market_coverage,
            "scoreContributionAllowed": score_allowed,
            "observationOnly": not score_allowed,
            "fallbackOrProxy": best["fallbackOrProxy"],
            "limitations": limitations,
            "nextEvidenceNeeded": next_evidence,
        }
    return summary


def _domain_capability_dict(source_id: str, domain: str, proven_domains: Sequence[str]) -> dict[str, Any]:
    spec = _SOURCE_SPECS[source_id]
    domain_spec = spec.domain_specs.get(domain)
    if domain_spec is None:
        return _unsupported_known_domain_capability(spec, domain, proven_domains)
    observation_only = domain_spec.authority_tier != "score_grade" or not domain_spec.score_contribution_allowed
    return {
        "sourceId": spec.source_id,
        "displayLabel": spec.display_label,
        "domains": list(proven_domains),
        "authorityTier": domain_spec.authority_tier,
        "freshnessClass": domain_spec.freshness_class,
        "marketCoverage": list(spec.market_coverage),
        "useCase": list(domain_spec.use_case),
        "limitations": list(domain_spec.limitations),
        "scoreContributionAllowed": domain_spec.score_contribution_allowed,
        "observationOnly": observation_only,
        "fallbackOrProxy": domain_spec.fallback_or_proxy,
        "nextEvidenceNeeded": list(domain_spec.next_evidence_needed),
    }


def _unsupported_known_domain_capability(
    spec: _SourceSpec,
    domain: str,
    proven_domains: Sequence[str],
) -> dict[str, Any]:
    return {
        "sourceId": spec.source_id,
        "displayLabel": spec.display_label,
        "domains": list(proven_domains),
        "authorityTier": "unknown",
        "freshnessClass": "unknown",
        "marketCoverage": list(spec.market_coverage),
        "useCase": ["unproven_for_domain"],
        "limitations": [f"Repository wiring has not proven {spec.source_id} supports {domain} for Home single-stock use."],
        "scoreContributionAllowed": False,
        "observationOnly": True,
        "fallbackOrProxy": False,
        "nextEvidenceNeeded": [f"补充 {domain} 来源授权证据"],
    }


def _unknown_domain_capability(
    spec: _SourceSpec,
    raw_domain: str,
    proven_domains: Sequence[str],
) -> dict[str, Any]:
    domain_label = str(raw_domain or "unknown").strip() or "unknown"
    return {
        "sourceId": spec.source_id,
        "displayLabel": spec.display_label,
        "domains": list(proven_domains),
        "authorityTier": "unknown",
        "freshnessClass": "unknown",
        "marketCoverage": list(spec.market_coverage),
        "useCase": ["manual_review", "unclassified_domain"],
        "limitations": [f"Repository wiring does not prove the requested domain '{domain_label}' for Home single-stock use."],
        "scoreContributionAllowed": False,
        "observationOnly": True,
        "fallbackOrProxy": False,
        "nextEvidenceNeeded": ["补充来源身份与域映射证据"],
    }


def _extract_source_ids(value: Any) -> list[str]:
    items: list[str] = []
    if isinstance(value, str):
        _append_unique(items, normalize_single_stock_source_id(value))
        return items
    if isinstance(value, Mapping):
        if any(key in value for key in ("sourceId", "source_id", "source")):
            raw_id = value.get("sourceId") or value.get("source_id") or value.get("source")
            _append_unique(items, normalize_single_stock_source_id(str(raw_id)))
            return items
        nested = value.get("sources")
        if nested is not None:
            return _extract_source_ids(nested)
        return items
    if isinstance(value, Sequence):
        for item in value:
            for source_id in _extract_source_ids(item):
                _append_unique(items, source_id)
    return items


def _capability_sort_key(capability: Mapping[str, Any]) -> tuple[int, int]:
    authority_rank = _AUTHORITY_RANK.get(str(capability.get("authorityTier") or "unknown"), 0)
    freshness_rank = _FRESHNESS_RANK.get(str(capability.get("freshnessClass") or "unknown"), 0)
    return authority_rank, freshness_rank


def _merge_market_coverage(capabilities: Sequence[Mapping[str, Any]]) -> list[str]:
    items: list[str] = []
    for capability in capabilities:
        for market in capability.get("marketCoverage") or []:
            normalized = str(market or "").strip().lower()
            if not normalized:
                continue
            _append_unique(items, normalized)
    return sorted(items, key=lambda item: (_MARKET_ORDER.get(item, 99), item))


def _merge_unique_lists(values: Sequence[Sequence[Any]]) -> list[str]:
    merged: list[str] = []
    for sequence in values:
        for item in sequence:
            text = str(item or "").strip()
            if not text:
                continue
            _append_unique(merged, text)
    return merged


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


__all__ = [
    "AUTHORITY_TIERS",
    "EVIDENCE_DOMAINS",
    "FRESHNESS_CLASSES",
    "SINGLE_STOCK_SOURCE_CAPABILITY_MATRIX_VERSION",
    "get_single_stock_source_capability",
    "get_single_stock_source_domain_capability",
    "list_single_stock_source_capabilities",
    "normalize_single_stock_evidence_domain",
    "normalize_single_stock_source_id",
    "summarize_source_capabilities_by_domain",
]
