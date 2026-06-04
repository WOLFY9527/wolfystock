# -*- coding: utf-8 -*-
"""Pure helper for normalizing bounded fundamentals/earnings evidence."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.services.single_stock_source_capability_matrix import (
    get_single_stock_source_domain_capability,
    normalize_single_stock_source_id,
)


SINGLE_STOCK_FUNDAMENTALS_EARNINGS_NORMALIZER_VERSION = (
    "single_stock_fundamentals_earnings_normalizer_v1"
)

_DOMAIN_ORDER = ("fundamentals", "earnings", "valuation", "filings")
_CORE_DOMAINS = frozenset({"fundamentals", "earnings", "valuation"})
_AUTHORITY_RANK = {
    "unknown": 0,
    "fixture_demo": 1,
    "fallback": 2,
    "observation_only": 3,
    "score_grade": 4,
}
_FRESHNESS_RANK = {
    "unknown": 0,
    "fixture": 1,
    "fallback": 2,
    "stale": 3,
    "delayed": 4,
    "daily": 5,
    "fresh": 6,
    "local": 7,
    "realtime": 8,
}
_FORBIDDEN_TEXT_MARKERS = (
    "authorization",
    "api_key",
    "apikey",
    "bearer",
    "broker",
    "buy now",
    "cache_key",
    "cookie",
    "internal_env",
    "order",
    "prompt:",
    "router_debug",
    "secret",
    "sell now",
    "stack trace",
    "submit order",
    "token",
    "traceback",
    "trade now",
)
_STATUS_MISSING = frozenset(
    {"missing", "unavailable", "unsupported", "not_supported", "empty", "not available"}
)
_STATUS_DEGRADED = frozenset(
    {"partial", "degraded", "fallback", "stale", "delayed", "weak", "timeout", "timed_out"}
)
_VALUATION_LABELS = {
    "trailingPE": "市盈率(TTM)",
    "forwardPE": "前瞻市盈率",
    "priceToBook": "市净率",
    "marketCap": "总市值",
}
_FUNDAMENTAL_LABELS = {
    "marketCap": "总市值",
    "revenueGrowth": "营收增速",
    "freeCashflow": "自由现金流",
    "returnOnEquity": "净资产收益率",
    "totalRevenue": "总营收",
    "netIncome": "净利润",
    "operatingMargins": "营业利润率",
}


def build_single_stock_fundamentals_earnings_normalizer_v1(
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Normalize existing single-stock inputs into a bounded evidence contract."""

    payload = _mapping(value)
    structured = _mapping(
        _first_present(payload.get("structuredAnalysis"), payload.get("structured_analysis"))
    )
    quality = _mapping(
        _first_present(payload.get("dataQualityReport"), payload.get("data_quality_report"))
    )
    context = _mapping(
        _first_present(
            structured.get("fundamental_context"),
            payload.get("fundamental_context"),
        )
    )
    no_advice_boundary = _no_advice_boundary(payload.get("noAdviceBoundary"))

    refs_by_domain = {
        "fundamentals": _fundamentals_refs(structured, context),
        "earnings": _earnings_refs(structured, context),
        "valuation": _valuation_refs(structured, context),
        "filings": _filings_refs(structured),
    }
    source_summary = {
        domain: _source_summary(domain, refs, _raw_domain_source(structured, domain))
        for domain, refs in refs_by_domain.items()
    }
    domains = {
        domain: _domain_summary(
            domain=domain,
            refs=refs_by_domain[domain],
            source_summary=source_summary[domain],
            structured=structured,
            context=context,
            quality=quality,
            market=_safe_market(payload.get("market")),
        )
        for domain in _DOMAIN_ORDER
    }

    missing_evidence: list[str] = []
    blocking_reasons: list[str] = []
    next_evidence_needed: list[str] = []
    for domain_name in _DOMAIN_ORDER:
        domain = domains[domain_name]
        if domain["status"] == "missing":
            missing_evidence.append(domain_name)
        for reason in domain.get("reasonCodes", []):
            _append_unique(blocking_reasons, reason)
        for needed in domain.get("nextEvidenceNeeded", []):
            _append_unique(next_evidence_needed, needed)

    for reason in _quality_reason_codes(quality):
        _append_unique(blocking_reasons, reason)
    if no_advice_boundary["state"] == "blocked":
        _append_unique(blocking_reasons, "no_advice_boundary_missing")

    normalizer_state = _normalizer_state(domains, no_advice_boundary, source_summary)

    return {
        "contractVersion": SINGLE_STOCK_FUNDAMENTALS_EARNINGS_NORMALIZER_VERSION,
        "symbol": _safe_symbol(payload.get("symbol")),
        "market": _safe_market(payload.get("market")),
        "normalizerState": normalizer_state,
        "domains": {domain: _public_domain_summary(domains[domain]) for domain in _DOMAIN_ORDER},
        "evidenceRefs": [
            ref
            for domain_name in _DOMAIN_ORDER
            for ref in refs_by_domain[domain_name]
        ],
        "missingEvidence": missing_evidence,
        "blockingReasons": blocking_reasons,
        "nextEvidenceNeeded": next_evidence_needed,
        "sourceSummary": source_summary,
        "noAdviceBoundary": no_advice_boundary,
        "debugRef": _sanitize_debug_ref(payload.get("debugRef")),
    }


def _fundamentals_refs(
    structured: Mapping[str, Any],
    context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    block = _mapping(_first_present(structured.get("fundamentals"), structured.get("fundamental_summary")))
    normalized = _mapping(_first_present(block.get("normalized"), block.get("raw"), block.get("metrics")))
    field_sources = _mapping(block.get("field_sources"))
    field_periods = _mapping(block.get("field_periods"))
    refs: list[dict[str, Any]] = []
    for key in ("marketCap", "revenueGrowth", "freeCashflow", "returnOnEquity"):
        value = _clean_metric_value(normalized.get(key))
        if value is None:
            continue
        refs.append(
            _make_ref(
                domain="fundamentals",
                label=_FUNDAMENTAL_LABELS[key],
                value=value,
                source=_first_present(field_sources.get(key), block.get("source")),
                source_tier=block.get("sourceTier"),
                provider_authority=block.get("providerAuthority"),
                freshness=_first_present(block.get("freshness"), block.get("freshnessClass")),
                period=field_periods.get(key),
                as_of=_first_present(block.get("asOf"), context.get("asOf")),
                proxy_only=block.get("proxyOnly"),
                fallback=block.get("isFallback"),
            )
        )
    if refs:
        return refs[:4]

    valuation_data = _mapping(_mapping(context.get("valuation")).get("data"))
    market_cap = _clean_metric_value(valuation_data.get("marketCap"))
    if market_cap is not None:
        refs.append(
            _make_ref(
                domain="fundamentals",
                label="总市值",
                value=market_cap,
                source="fundamental_context",
                source_tier=None,
                provider_authority=None,
                freshness=None,
                period="latest",
                as_of=None,
                proxy_only=False,
                fallback=False,
            )
        )
    return refs


def _earnings_refs(
    structured: Mapping[str, Any],
    context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    block = _mapping(_first_present(structured.get("earnings_analysis"), structured.get("earnings")))
    refs: list[dict[str, Any]] = []
    quarterly = _sequence(block.get("quarterly_series"))
    if quarterly:
        latest = _mapping(quarterly[0])
        latest_value = {
            "revenue": _clean_metric_value(latest.get("revenue")),
            "netIncome": _clean_metric_value(_first_present(latest.get("net_income"), latest.get("netIncome"))),
        }
        latest_value = {key: value for key, value in latest_value.items() if value is not None}
        if latest_value:
            refs.append(
                _make_ref(
                    domain="earnings",
                    label="最新季度财报",
                    value=latest_value,
                    source=block.get("source"),
                    source_tier=block.get("sourceTier"),
                    provider_authority=block.get("providerAuthority"),
                    freshness=_first_present(block.get("freshness"), block.get("freshnessClass")),
                    period=_first_present(latest.get("quarter"), block.get("reporting_basis")),
                    as_of=_first_present(latest.get("fiscalDateEnding"), latest.get("reportDate")),
                    proxy_only=block.get("proxyOnly"),
                    fallback=block.get("isFallback"),
                )
            )
    derived = _mapping(block.get("derived_metrics"))
    growth_value = {
        "yoyRevenueGrowth": _clean_metric_value(derived.get("yoy_revenue_growth")),
        "yoyNetIncomeChange": _clean_metric_value(derived.get("yoy_net_income_change")),
    }
    growth_value = {key: value for key, value in growth_value.items() if value is not None}
    if growth_value:
        refs.append(
            _make_ref(
                domain="earnings",
                label="财报趋势摘要",
                value=growth_value,
                source=block.get("source"),
                source_tier=block.get("sourceTier"),
                provider_authority=block.get("providerAuthority"),
                freshness=_first_present(block.get("freshness"), block.get("freshnessClass")),
                period=_first_present(block.get("summary_basis"), block.get("reporting_basis")),
                as_of=None,
                proxy_only=block.get("proxyOnly"),
                fallback=block.get("isFallback"),
            )
        )

    earnings_data = _mapping(_mapping(context.get("earnings")).get("data"))
    report = _mapping(earnings_data.get("financial_report"))
    if report:
        report_value = {
            "revenue": _clean_metric_value(report.get("revenue")),
            "netIncome": _clean_metric_value(_first_present(report.get("netIncome"), report.get("net_income"))),
        }
        report_value = {key: value for key, value in report_value.items() if value is not None}
        if report_value:
            refs.append(
                _make_ref(
                    domain="earnings",
                    label="财报摘要",
                    value=report_value,
                    source=_first_present(block.get("source"), "fundamental_context"),
                    source_tier=block.get("sourceTier"),
                    provider_authority=block.get("providerAuthority"),
                    freshness=_first_present(block.get("freshness"), block.get("freshnessClass")),
                    period="financial_report",
                    as_of=_first_present(report.get("reportDate"), report.get("fiscalDateEnding")),
                    proxy_only=False,
                    fallback=False,
                )
            )
    dividend = _mapping(earnings_data.get("dividend"))
    dividend_yield = _clean_metric_value(_first_present(dividend.get("dividendYield"), dividend.get("yield")))
    if dividend_yield is not None:
        refs.append(
            _make_ref(
                domain="earnings",
                label="股息信息",
                value={
                    "dividendYield": dividend_yield,
                    "dividendPerShare": _clean_metric_value(dividend.get("dividendPerShare")),
                },
                source=_first_present(block.get("source"), "fundamental_context"),
                source_tier=block.get("sourceTier"),
                provider_authority=block.get("providerAuthority"),
                freshness=_first_present(block.get("freshness"), block.get("freshnessClass")),
                period="latest",
                as_of=dividend.get("asOfDate"),
                proxy_only=False,
                fallback=False,
            )
        )
    return refs[:4]


def _valuation_refs(
    structured: Mapping[str, Any],
    context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    block = _mapping(structured.get("fundamentals"))
    normalized = _mapping(_first_present(block.get("normalized"), block.get("raw"), block.get("metrics")))
    field_sources = _mapping(block.get("field_sources"))
    field_periods = _mapping(block.get("field_periods"))
    valuation_data = _mapping(_mapping(context.get("valuation")).get("data"))
    refs: list[dict[str, Any]] = []
    for key in ("trailingPE", "forwardPE", "priceToBook"):
        value = _clean_metric_value(_first_present(normalized.get(key), valuation_data.get(key)))
        if value is None:
            continue
        refs.append(
            _make_ref(
                domain="valuation",
                label=_VALUATION_LABELS[key],
                value=value,
                source=_first_present(field_sources.get(key), block.get("source"), "fundamental_context"),
                source_tier=block.get("sourceTier"),
                provider_authority=block.get("providerAuthority"),
                freshness=_first_present(block.get("freshness"), block.get("freshnessClass")),
                period=_first_present(field_periods.get(key), "latest"),
                as_of=block.get("asOf"),
                proxy_only=block.get("proxyOnly"),
                fallback=block.get("isFallback"),
            )
        )
    return refs[:4]


def _filings_refs(structured: Mapping[str, Any]) -> list[dict[str, Any]]:
    block = _mapping(structured.get("filings"))
    refs: list[dict[str, Any]] = []
    for item in _sequence(_first_present(block.get("items"), block.get("rows"), block.get("entries"))):
        filing = _mapping(item)
        form_type = _sanitize_text(_first_present(filing.get("formType"), filing.get("form_type")))
        filed_at = _sanitize_date(_first_present(filing.get("filedAt"), filing.get("filed_at")))
        period_end = _sanitize_date(_first_present(filing.get("periodEnd"), filing.get("period_end")))
        if not form_type and not filed_at:
            continue
        refs.append(
            _make_ref(
                domain="filings",
                label=form_type or "申报文件",
                value={
                    "formType": form_type or "filing",
                    "accessionNumber": _sanitize_text(filing.get("accessionNumber")),
                },
                source=_first_present(block.get("source"), "sec_10q"),
                source_tier=block.get("sourceTier"),
                provider_authority=block.get("providerAuthority"),
                freshness=_first_present(block.get("freshness"), block.get("freshnessClass"), "daily"),
                period=period_end or "latest",
                as_of=filed_at,
                proxy_only=block.get("proxyOnly"),
                fallback=block.get("isFallback"),
            )
        )
    return refs[:4]


def _make_ref(
    *,
    domain: str,
    label: str,
    value: Any,
    source: Any,
    source_tier: Any,
    provider_authority: Any,
    freshness: Any,
    period: Any,
    as_of: Any,
    proxy_only: Any,
    fallback: Any,
) -> dict[str, Any]:
    profile = _source_profile(
        raw_source=source,
        domain=domain,
        raw_source_tier=source_tier,
        raw_provider_authority=provider_authority,
        raw_freshness=freshness,
        proxy_only=bool(proxy_only),
        fallback=bool(fallback),
    )
    safe_label = _sanitize_text(label) or domain
    safe_value = _sanitize_value(value)
    return {
        "id": _ref_id(domain, safe_label, profile["sourceId"]),
        "domain": domain,
        "label": safe_label,
        "value": safe_value,
        "period": _sanitize_text(period) or "latest",
        "asOf": _sanitize_date(as_of) or "unknown",
        "sourceId": profile["sourceId"],
        "sourceTier": profile["sourceTier"],
        "providerAuthority": profile["providerAuthority"],
        "freshness": profile["freshness"],
        "confidence": profile["confidence"],
        "limitations": profile["limitations"],
    }


def _source_profile(
    *,
    raw_source: Any,
    domain: str,
    raw_source_tier: Any,
    raw_provider_authority: Any,
    raw_freshness: Any,
    proxy_only: bool,
    fallback: bool,
) -> dict[str, Any]:
    normalized_source = _normalized_source_id(raw_source)
    if normalized_source == "sec_filing":
        capability = {
            "sourceId": "sec_filing",
            "authorityTier": "observation_only",
            "freshnessClass": "daily",
            "scoreContributionAllowed": False,
            "fallbackOrProxy": False,
            "limitations": [
                "Official filing metadata is useful for observation and citation, not direct score authority."
            ],
        }
    else:
        capability = get_single_stock_source_domain_capability(normalized_source, domain)

    authority_tier = str(capability.get("authorityTier") or "unknown")
    freshness = _normalize_freshness(raw_freshness, capability.get("freshnessClass"))
    source_tier = _normalize_source_tier(raw_source_tier, authority_tier)
    limitations = [item for item in capability.get("limitations") or [] if _sanitize_text(item)]
    if fallback or freshness in {"fallback", "fixture"}:
        authority_tier = "fallback" if freshness == "fallback" else "fixture_demo"
    if proxy_only:
        authority_tier = "observation_only"
        _append_unique(limitations, "Proxy or public fallback evidence cannot be treated as decision-grade.")
    if normalized_source == "manual_unknown":
        authority_tier = "unknown"
    if freshness in {"stale", "unknown"} and authority_tier == "score_grade":
        authority_tier = "observation_only"
    score_allowed = bool(capability.get("scoreContributionAllowed")) and authority_tier == "score_grade"
    if _truthy_observation_authority(raw_provider_authority):
        score_allowed = False
        if authority_tier == "score_grade":
            authority_tier = "observation_only"
    provider_authority = "scoreGradeAllowed" if score_allowed else "observationOnly"
    return {
        "sourceId": normalized_source,
        "sourceTier": source_tier,
        "freshness": freshness,
        "confidence": _confidence(authority_tier, freshness),
        "providerAuthority": provider_authority,
        "limitations": limitations,
    }


def _source_summary(
    domain: str,
    refs: Sequence[Mapping[str, Any]],
    raw_source: Any,
) -> dict[str, Any]:
    source_ids: list[str] = []
    best_authority = "unknown"
    best_freshness = "unknown"
    score_allowed = False
    limitations: list[str] = []
    if refs:
        for ref in refs:
            source_id = str(ref.get("sourceId") or "manual_unknown")
            _append_unique(source_ids, source_id)
            authority_tier = _authority_from_ref(ref)
            if _AUTHORITY_RANK.get(authority_tier, 0) > _AUTHORITY_RANK.get(best_authority, 0):
                best_authority = authority_tier
            freshness = str(ref.get("freshness") or "unknown")
            if _FRESHNESS_RANK.get(freshness, 0) > _FRESHNESS_RANK.get(best_freshness, 0):
                best_freshness = freshness
            score_allowed = score_allowed or str(ref.get("providerAuthority")) == "scoreGradeAllowed"
            for item in ref.get("limitations") or []:
                _append_unique(limitations, item)
    else:
        inferred = _normalized_source_id(raw_source)
        source_ids = [inferred]
        profile = _source_profile(
            raw_source=raw_source,
            domain=domain,
            raw_source_tier=None,
            raw_provider_authority=None,
            raw_freshness=None,
            proxy_only=False,
            fallback=False,
        )
        best_authority = _authority_from_ref(profile)
        best_freshness = str(profile.get("freshness") or "unknown")
        limitations = list(profile.get("limitations") or [])
    return {
        "domain": domain,
        "sourceIds": source_ids,
        "bestAuthorityTier": best_authority,
        "freshnessClass": best_freshness,
        "scoreContributionAllowed": score_allowed,
        "observationOnly": not score_allowed,
        "limitations": limitations,
        "nextEvidenceNeeded": _next_evidence_needed(domain, best_authority),
    }


def _domain_summary(
    *,
    domain: str,
    refs: Sequence[Mapping[str, Any]],
    source_summary: Mapping[str, Any],
    structured: Mapping[str, Any],
    context: Mapping[str, Any],
    quality: Mapping[str, Any],
    market: str,
) -> dict[str, Any]:
    block = _domain_block(structured, domain)
    explicit_status = _normalize_status(block.get("status"))
    evidence_count = len(refs)
    missing_codes = _domain_missing_reason_codes(domain, block, context, quality, market, evidence_count)
    status = "available"
    if evidence_count == 0 or explicit_status in _STATUS_MISSING:
        status = "missing"
    elif explicit_status in _STATUS_DEGRADED or any(
        code in {"stale_evidence", "fallback_proxy_evidence"} for code in missing_codes
    ):
        status = "degraded"
    return {
        "domain": domain,
        "status": status,
        "evidenceCount": evidence_count,
        "sourceIds": list(source_summary.get("sourceIds") or []),
        "bestAuthorityTier": str(source_summary.get("bestAuthorityTier") or "unknown"),
        "freshness": str(source_summary.get("freshnessClass") or "unknown"),
        "scoreContributionAllowed": bool(source_summary.get("scoreContributionAllowed")),
        "limitations": list(source_summary.get("limitations") or []),
        "reasonCodes": missing_codes,
        "nextEvidenceNeeded": _next_evidence_needed(domain, source_summary.get("bestAuthorityTier")),
    }


def _domain_missing_reason_codes(
    domain: str,
    block: Mapping[str, Any],
    context: Mapping[str, Any],
    quality: Mapping[str, Any],
    market: str,
    evidence_count: int,
) -> list[str]:
    reasons: list[str] = []
    quality_reasons = _quality_reason_codes(quality)
    if domain in _quality_missing_domains(quality):
        if domain == "valuation":
            _append_unique(reasons, "valuation_metrics_missing")
        else:
            _append_unique(reasons, f"{domain}_missing")
    for reason in quality_reasons:
        if reason in {"fundamental_context_unavailable", "stale_evidence", "fallback_proxy_evidence"}:
            _append_unique(reasons, reason)
    status = _normalize_status(block.get("status"))
    if status in _STATUS_MISSING:
        if domain == "valuation":
            _append_unique(reasons, "valuation_metrics_missing")
        else:
            _append_unique(reasons, f"{domain}_missing")
    if status in _STATUS_DEGRADED and "stale_evidence" not in reasons:
        lowered = str(block.get("freshness") or "").strip().lower()
        if lowered in {"stale", "fallback", "fixture", "delayed"}:
            _append_unique(reasons, "stale_evidence")
    if _is_unsupported_fundamental_context(context, market) and domain in _CORE_DOMAINS and evidence_count == 0:
        _append_unique(reasons, "fundamental_context_unavailable")
    return reasons


def _normalizer_state(
    domains: Mapping[str, Mapping[str, Any]],
    no_advice_boundary: Mapping[str, Any],
    source_summary: Mapping[str, Mapping[str, Any]],
) -> str:
    if no_advice_boundary.get("state") == "blocked":
        return "blocked"
    if any(domains[domain]["status"] == "missing" for domain in _CORE_DOMAINS):
        return "insufficient"
    if any(domains[domain]["status"] == "degraded" for domain in _DOMAIN_ORDER):
        return "observe_only"
    if any(
        not bool(source_summary[domain].get("scoreContributionAllowed"))
        for domain in _CORE_DOMAINS
        if domains[domain]["evidenceCount"] > 0
    ):
        return "observe_only"
    return "ready"


def _quality_reason_codes(quality: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    for item in _sequence(quality.get("reasonCodes")):
        text = _sanitize_text(item)
        if not text:
            continue
        if text == "stale_required_source":
            text = "stale_evidence"
        _append_unique(reasons, text)
    return reasons


def _quality_missing_domains(quality: Mapping[str, Any]) -> set[str]:
    missing: set[str] = set()
    for key in ("missingRequiredDomains", "importantDomainsMissing"):
        for item in _sequence(quality.get(key)):
            text = str(item or "").strip()
            if text in _DOMAIN_ORDER:
                missing.add(text)
    return missing


def _domain_block(structured: Mapping[str, Any], domain: str) -> Mapping[str, Any]:
    if domain == "earnings":
        return _mapping(_first_present(structured.get("earnings_analysis"), structured.get("earnings")))
    return _mapping(structured.get(domain))


def _raw_domain_source(structured: Mapping[str, Any], domain: str) -> Any:
    block = _domain_block(structured, domain)
    return block.get("source")


def _next_evidence_needed(domain: str, authority_tier: Any) -> list[str]:
    best = str(authority_tier or "unknown")
    if domain == "fundamentals":
        return ["补充基本面证据"] if best != "score_grade" else []
    if domain == "earnings":
        return ["补充财报证据"] if best != "score_grade" else []
    if domain == "valuation":
        return ["补充估值证据"] if best != "score_grade" else []
    if domain == "filings":
        return ["补充申报文件证据"] if best != "score_grade" else []
    return []


def _no_advice_boundary(value: Any) -> dict[str, str]:
    if value is True:
        return {"state": "no_advice", "label": "仅研究，不构成投资建议"}
    return {"state": "blocked", "label": "仅研究，禁止转化为交易或执行建议"}


def _public_domain_summary(domain: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "domain": domain["domain"],
        "status": domain["status"],
        "evidenceCount": domain["evidenceCount"],
        "sourceIds": list(domain["sourceIds"]),
        "bestAuthorityTier": domain["bestAuthorityTier"],
        "freshness": domain["freshness"],
        "scoreContributionAllowed": domain["scoreContributionAllowed"],
        "limitations": list(domain["limitations"]),
    }


def _normalized_source_id(source: Any) -> str:
    text = str(source or "").strip().lower().replace("-", "_")
    if not text:
        return "manual_unknown"
    if any(token in text for token in ("sec", "edgar", "companyfacts", "10_q", "10_k")):
        return "sec_filing"
    if "fmp" in text:
        return "fmp"
    if "finnhub" in text:
        return "finnhub"
    if "yfinance" in text or "yahoo" in text:
        return "yfinance"
    if "alpha" in text:
        return "alpha_vantage"
    if "twelve" in text:
        return "twelvedata"
    if "fixture" in text or "cache/local_fixture" in text:
        return "cache_local_fixture"
    if "gnews" in text:
        return "gnews"
    if "fred" in text:
        return "fred"
    if "treasury" in text:
        return "treasury"
    return normalize_single_stock_source_id(text)


def _normalize_status(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _normalize_source_tier(raw_source_tier: Any, authority_tier: str) -> str:
    text = _sanitize_text(raw_source_tier)
    if text:
        return text
    if authority_tier == "score_grade":
        return "score_grade"
    if authority_tier in {"fallback", "fixture_demo"}:
        return authority_tier
    return "observation_only" if authority_tier == "observation_only" else "unknown"


def _normalize_freshness(raw_freshness: Any, fallback: Any) -> str:
    text = str(_sanitize_text(raw_freshness) or _sanitize_text(fallback) or "unknown").lower()
    if text in {"realtime", "local", "daily", "delayed", "fixture", "unknown", "fallback", "stale", "fresh"}:
        return text
    if text in {"manual_review", "manual review"}:
        return "delayed"
    return "unknown"


def _confidence(authority_tier: str, freshness: str) -> float:
    base = {
        "score_grade": 0.9,
        "observation_only": 0.55,
        "fallback": 0.4,
        "fixture_demo": 0.25,
        "unknown": 0.2,
    }.get(authority_tier, 0.2)
    freshness_penalty = {
        "fresh": 0.0,
        "realtime": 0.0,
        "local": 0.02,
        "daily": 0.05,
        "delayed": 0.12,
        "stale": 0.2,
        "fallback": 0.2,
        "fixture": 0.25,
        "unknown": 0.28,
    }.get(freshness, 0.28)
    return round(max(0.05, base - freshness_penalty), 2)


def _authority_from_ref(ref: Mapping[str, Any]) -> str:
    if str(ref.get("providerAuthority") or "") == "scoreGradeAllowed":
        return "score_grade"
    source_tier = str(ref.get("sourceTier") or "")
    if source_tier in _AUTHORITY_RANK:
        return source_tier
    if str(ref.get("sourceId") or "") == "manual_unknown":
        return "unknown"
    return "observation_only"


def _truthy_observation_authority(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in {"observationonly", "observation_only", "observation only"}


def _is_unsupported_fundamental_context(context: Mapping[str, Any], market: str) -> bool:
    status = _normalize_status(context.get("status"))
    if market not in {"us", "hk"}:
        return False
    if status in {"market_not_supported", "not_supported", "unsupported"}:
        return True
    reason = _sanitize_text(context.get("reason"))
    return bool(reason and "fundamental_context" in reason and "unavailable" in reason)


def _ref_id(domain: str, label: str, source_id: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in label).strip("-")
    slug = "-".join(part for part in slug.split("-") if part) or "evidence"
    return f"{domain}:{source_id}:{slug}"[:96]


def _clean_metric_value(value: Any) -> Any:
    cleaned = _sanitize_value(value)
    if cleaned in ("", {}, [], None):
        return None
    return cleaned


def _sanitize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 6)
    if isinstance(value, str):
        text = _sanitize_text(value)
        return text or None
    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = _sanitize_text(raw_key)
            if not key or _contains_forbidden_text(key):
                continue
            cleaned = _sanitize_value(raw_value)
            if cleaned in (None, "", {}, []):
                continue
            safe[key] = cleaned
        return safe
    if isinstance(value, Sequence):
        safe_items = []
        for item in value[:4]:
            cleaned = _sanitize_value(item)
            if cleaned in (None, "", {}, []):
                continue
            safe_items.append(cleaned)
        return safe_items
    text = _sanitize_text(value)
    return text or None


def _sanitize_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if _contains_forbidden_text(lowered):
        return ""
    return text[:160]


def _contains_forbidden_text(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _FORBIDDEN_TEXT_MARKERS)


def _sanitize_debug_ref(value: Any) -> str:
    text = _sanitize_text(value)
    if not text:
        return "redacted"
    if "://" in text or "?" in text or _contains_forbidden_text(text):
        return "redacted"
    return text


def _sanitize_date(value: Any) -> str:
    text = _sanitize_text(value)
    if not text:
        return ""
    return text[:32]


def _safe_symbol(value: Any) -> str:
    text = _sanitize_text(value)
    return text or "UNKNOWN"


def _safe_market(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"us", "hk", "cn", "global"} else "unknown"


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


__all__ = [
    "SINGLE_STOCK_FUNDAMENTALS_EARNINGS_NORMALIZER_VERSION",
    "build_single_stock_fundamentals_earnings_normalizer_v1",
]
