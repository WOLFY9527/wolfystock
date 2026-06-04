# -*- coding: utf-8 -*-
"""Pure additive contract helper for bounded single-stock evidence packets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


SINGLE_STOCK_EVIDENCE_PACKET_VERSION = "single_stock_evidence_packet_v1"

_DOMAIN_ORDER = (
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
_CRITICAL_DOMAINS = frozenset(
    {
        "priceHistory",
        "technicals",
        "fundamentals",
        "earnings",
        "news",
        "catalysts",
        "sentiment",
        "valuation",
    }
)
_OPTIONAL_DEGRADE_OK = frozenset({"filings", "sectorTheme", "macroLiquidity"})
_STATUS_VALUES = frozenset({"available", "degraded", "missing", "blocked", "pending", "not_applicable"})
_WAITING_STATUSES = frozenset({"pending", "waiting", "queued", "loading", "scheduled", "in_progress"})
_BLOCKED_STATUSES = frozenset({"timeout", "timed_out", "failed", "error", "blocked"})
_MISSING_STATUSES = frozenset(
    {
        "missing",
        "unavailable",
        "not_supported",
        "unsupported",
        "not_configured",
        "skipped",
        "empty",
    }
)
_DEGRADED_STATUSES = frozenset({"partial", "degraded", "fallback", "stale", "weak", "delayed"})
_SAFE_TEXT_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_:-+./ #")
_SECRET_MARKERS = (
    "authorization",
    "api_key",
    "apikey",
    "bearer",
    "cookie",
    "password",
    "secret",
    "token",
    "router_debug",
    "cache_key",
    "internal_env",
    "stack trace",
    "traceback",
)
_FORBIDDEN_ADVICE_WORDS = ("buy", "sell", "order", "trade", "broker", "下单", "买入", "卖出", "交易")
_NEXT_EVIDENCE = {
    "priceHistory": "补充价格历史证据",
    "technicals": "补充技术面证据",
    "fundamentals": "补充基本面证据",
    "earnings": "补充财报证据",
    "filings": "补充申报文件证据",
    "news": "补充新闻证据",
    "catalysts": "补充催化剂证据",
    "sentiment": "补充情绪证据",
    "valuation": "补充估值证据",
    "sectorTheme": "补充行业主题证据",
    "macroLiquidity": "补充宏观流动性证据",
}
_DOMAIN_ALIASES = {
    "pricehistory": "priceHistory",
    "price_history": "priceHistory",
    "ohlcv": "priceHistory",
    "technicals": "technicals",
    "technical": "technicals",
    "fundamentals": "fundamentals",
    "fundamental": "fundamentals",
    "earnings": "earnings",
    "filings": "filings",
    "filing": "filings",
    "news": "news",
    "catalysts": "catalysts",
    "catalyst": "catalysts",
    "sentiment": "sentiment",
    "valuation": "valuation",
    "sectortheme": "sectorTheme",
    "sector_theme": "sectorTheme",
    "macroliquidity": "macroLiquidity",
    "macro_liquidity": "macroLiquidity",
    "macro": "macroLiquidity",
    "liquidity": "macroLiquidity",
}


@dataclass(frozen=True, slots=True)
class EvidenceDomainV1:
    status: str
    source_tier: str
    provider_authority: str
    freshness: str
    fallback_or_proxy: bool
    evidence_count: int
    top_evidence_refs: tuple[str, ...]
    missing_reasons: tuple[str, ...]
    next_evidence_needed: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "sourceTier": self.source_tier,
            "providerAuthority": self.provider_authority,
            "freshness": self.freshness,
            "fallbackOrProxy": self.fallback_or_proxy,
            "evidenceCount": self.evidence_count,
            "topEvidenceRefs": list(self.top_evidence_refs),
            "missingReasons": list(self.missing_reasons),
            "nextEvidenceNeeded": list(self.next_evidence_needed),
        }


def build_single_stock_evidence_packet_v1(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a bounded evidence packet assembled from caller-provided metadata."""

    payload = _mapping(value)
    structured = _mapping(_first_present(payload.get("structuredAnalysis"), payload.get("structured_analysis")))
    runtime = _mapping(_first_present(payload.get("runtimeData"), payload.get("runtime_data")))
    quality = _mapping(_first_present(payload.get("dataQualityReport"), payload.get("data_quality_report")))

    domains = {
        "priceHistory": _price_history_domain(structured, runtime, quality),
        "technicals": _technicals_domain(structured, quality),
        "fundamentals": _fundamentals_domain(payload, structured, runtime, quality),
        "earnings": _earnings_domain(payload, structured, quality),
        "filings": _filings_domain(structured, quality),
        "news": _news_domain(structured, runtime, quality),
        "catalysts": _catalysts_domain(structured, runtime, quality),
        "sentiment": _sentiment_domain(structured, runtime, quality),
        "valuation": _valuation_domain(payload, structured, runtime, quality),
        "sectorTheme": _sector_theme_domain(structured, quality),
        "macroLiquidity": _macro_liquidity_domain(structured, quality),
    }

    missing_evidence: list[str] = []
    blocking_reasons: list[str] = []
    next_evidence_needed: list[str] = []
    counts = {
        "availableCount": 0,
        "degradedCount": 0,
        "missingCount": 0,
        "blockedCount": 0,
        "pendingCount": 0,
    }

    for domain_name in _DOMAIN_ORDER:
        domain = domains[domain_name]
        if domain.status == "available":
            counts["availableCount"] += 1
        elif domain.status == "degraded":
            counts["degradedCount"] += 1
        elif domain.status == "missing":
            counts["missingCount"] += 1
            missing_evidence.append(domain_name)
        elif domain.status == "blocked":
            counts["blockedCount"] += 1
            missing_evidence.append(domain_name)
        elif domain.status == "pending":
            counts["pendingCount"] += 1
            missing_evidence.append(domain_name)

        if domain_name not in _CRITICAL_DOMAINS:
            continue
        if domain.status == "available":
            continue
        for reason in domain.missing_reasons:
            _append_unique(blocking_reasons, reason)
        if domain.next_evidence_needed:
            _append_unique(next_evidence_needed, domain.next_evidence_needed[0])

    no_advice_boundary = _no_advice_boundary(payload.get("noAdviceBoundary"))
    if no_advice_boundary["state"] == "blocked":
        _append_unique(blocking_reasons, "no_advice_boundary_missing")

    packet_state = _packet_state(domains, no_advice_boundary["state"])
    result = {
        "contractVersion": SINGLE_STOCK_EVIDENCE_PACKET_VERSION,
        "symbol": _safe_symbol(payload.get("symbol")),
        "market": _safe_market(payload.get("market")),
        "packetState": packet_state,
        "domains": {domain: domains[domain].to_dict() for domain in _DOMAIN_ORDER},
        "sourceSummary": counts,
        "missingEvidence": missing_evidence,
        "blockingReasons": blocking_reasons,
        "nextEvidenceNeeded": next_evidence_needed,
        "noAdviceBoundary": no_advice_boundary,
        "debugRef": _sanitize_text(payload.get("debugRef")) or "redacted",
    }
    return result


def _packet_state(domains: Mapping[str, EvidenceDomainV1], no_advice_state: str) -> str:
    if no_advice_state == "blocked":
        return "blocked"
    if any(domains[name].status == "blocked" for name in _CRITICAL_DOMAINS):
        return "degraded"
    if any(domains[name].status == "pending" for name in _CRITICAL_DOMAINS):
        return "degraded"
    if any(domains[name].status in {"missing", "degraded"} for name in _CRITICAL_DOMAINS):
        return "degraded"
    if any(domains[name].status not in {"available", "not_applicable"} for name in _DOMAIN_ORDER if name not in _OPTIONAL_DEGRADE_OK):
        return "degraded"
    return "available"


def _price_history_domain(
    structured: Mapping[str, Any],
    runtime: Mapping[str, Any],
    quality: Mapping[str, Any],
) -> EvidenceDomainV1:
    technicals = _mapping(structured.get("technicals"))
    realtime = _mapping(structured.get("realtime_context"))
    runtime_market = _mapping(runtime.get("market"))
    refs = _top_refs(technicals, realtime)
    freshness = _domain_freshness(technicals, realtime, runtime_market)
    fallback = _domain_fallback_or_proxy(technicals, realtime, runtime_market)
    reasons = _quality_reason_list(quality, "priceHistory")
    status = _status_from_components(
        domain_name="priceHistory",
        statuses=(_normalized_status(technicals), _normalized_status(runtime_market)),
        freshness=freshness,
        fallback_or_proxy=fallback,
        evidence_count=max(len(refs), _count_present(realtime.get("price"), realtime.get("volume_ratio"), realtime.get("turnover_rate"))),
        reasons=reasons,
    )
    return EvidenceDomainV1(
        status=status,
        source_tier=_source_tier(technicals, runtime_market, default="score_grade"),
        provider_authority=_provider_authority(status, fallback, freshness, technicals, runtime_market),
        freshness=freshness,
        fallback_or_proxy=fallback,
        evidence_count=max(len(refs), _count_present(realtime.get("price"), realtime.get("volume_ratio"), realtime.get("turnover_rate"))),
        top_evidence_refs=refs,
        missing_reasons=tuple(reasons if status != "available" else ()),
        next_evidence_needed=_next_needed(status, "priceHistory"),
    )


def _technicals_domain(structured: Mapping[str, Any], quality: Mapping[str, Any]) -> EvidenceDomainV1:
    technicals = _mapping(structured.get("technicals"))
    refs = _top_refs(technicals)
    freshness = _domain_freshness(technicals)
    fallback = _domain_fallback_or_proxy(technicals)
    reasons = _quality_reason_list(quality, "technicals")
    status = _status_from_components(
        domain_name="technicals",
        statuses=(_normalized_status(technicals),),
        freshness=freshness,
        fallback_or_proxy=fallback,
        evidence_count=max(len(refs), 1 if technicals else 0),
        reasons=reasons,
    )
    return EvidenceDomainV1(
        status=status,
        source_tier=_source_tier(technicals, default="unknown"),
        provider_authority=_provider_authority(status, fallback, freshness, technicals),
        freshness=freshness,
        fallback_or_proxy=fallback,
        evidence_count=max(len(refs), 1 if technicals else 0),
        top_evidence_refs=refs,
        missing_reasons=tuple(reasons if status != "available" else ()),
        next_evidence_needed=_next_needed(status, "technicals"),
    )


def _fundamentals_domain(
    payload: Mapping[str, Any],
    structured: Mapping[str, Any],
    runtime: Mapping[str, Any],
    quality: Mapping[str, Any],
) -> EvidenceDomainV1:
    fundamentals = _mapping(structured.get("fundamentals"))
    fundamental_context = _mapping(structured.get("fundamental_context"))
    runtime_fundamentals = _mapping(runtime.get("fundamentals"))
    refs = _top_refs(fundamentals)
    freshness = _domain_freshness(fundamentals, runtime_fundamentals)
    fallback = _domain_fallback_or_proxy(fundamentals, runtime_fundamentals)
    reasons = _quality_reason_list(quality, "fundamentals")
    if _fundamental_context_unavailable(payload, fundamental_context):
        _append_unique(reasons, "fundamental_context_unavailable")
    status = _status_from_components(
        domain_name="fundamentals",
        statuses=(_normalized_status(fundamentals), _normalized_status(runtime_fundamentals)),
        freshness=freshness,
        fallback_or_proxy=fallback,
        evidence_count=max(len(refs), 1 if fundamentals.get("normalized") else 0),
        reasons=reasons,
    )
    return EvidenceDomainV1(
        status=status,
        source_tier=_source_tier(fundamentals, runtime_fundamentals, default="unknown"),
        provider_authority=_provider_authority(status, fallback, freshness, fundamentals, runtime_fundamentals),
        freshness=freshness,
        fallback_or_proxy=fallback,
        evidence_count=max(len(refs), 1 if fundamentals.get("normalized") else 0),
        top_evidence_refs=refs,
        missing_reasons=tuple(reasons if status != "available" else ()),
        next_evidence_needed=_next_needed(status, "fundamentals"),
    )


def _earnings_domain(payload: Mapping[str, Any], structured: Mapping[str, Any], quality: Mapping[str, Any]) -> EvidenceDomainV1:
    earnings = _mapping(structured.get("earnings_analysis"))
    fundamental_context = _mapping(structured.get("fundamental_context"))
    refs = _top_refs(earnings)
    freshness = _domain_freshness(earnings)
    reasons = _quality_reason_list(quality, "earnings")
    if _fundamental_context_unavailable(payload, fundamental_context):
        _append_unique(reasons, "fundamental_context_unavailable")
    has_series = bool(_mapping(fundamental_context.get("earnings")).get("data")) or bool(earnings.get("summary_flags"))
    status = _status_from_components(
        domain_name="earnings",
        statuses=(_normalized_status(earnings),),
        freshness=freshness,
        fallback_or_proxy=False,
        evidence_count=max(len(refs), 1 if has_series else 0),
        reasons=reasons,
    )
    return EvidenceDomainV1(
        status=status,
        source_tier=_source_tier(earnings, default="unknown"),
        provider_authority=_provider_authority(status, False, freshness, earnings),
        freshness=freshness,
        fallback_or_proxy=False,
        evidence_count=max(len(refs), 1 if has_series else 0),
        top_evidence_refs=refs,
        missing_reasons=tuple(reasons if status != "available" else ()),
        next_evidence_needed=_next_needed(status, "earnings"),
    )


def _filings_domain(structured: Mapping[str, Any], quality: Mapping[str, Any]) -> EvidenceDomainV1:
    filings = _mapping(structured.get("filings"))
    refs = _top_refs(filings)
    freshness = _domain_freshness(filings)
    reasons = _quality_reason_list(quality, "filings")
    status = _status_from_components(
        domain_name="filings",
        statuses=(_normalized_status(filings),),
        freshness=freshness,
        fallback_or_proxy=False,
        evidence_count=max(len(refs), 1 if filings else 0),
        reasons=reasons,
    )
    return EvidenceDomainV1(
        status=status,
        source_tier=_source_tier(filings, default="unknown"),
        provider_authority=_provider_authority(status, False, freshness, filings),
        freshness=freshness,
        fallback_or_proxy=False,
        evidence_count=max(len(refs), 1 if filings else 0),
        top_evidence_refs=refs,
        missing_reasons=tuple(reasons if status != "available" else ()),
        next_evidence_needed=_next_needed(status, "filings"),
    )


def _news_domain(structured: Mapping[str, Any], runtime: Mapping[str, Any], quality: Mapping[str, Any]) -> EvidenceDomainV1:
    sentiment = _mapping(structured.get("sentiment_analysis"))
    runtime_news = _mapping(runtime.get("news"))
    refs = _top_refs(sentiment)
    freshness = _domain_freshness(sentiment, runtime_news)
    fallback = _domain_fallback_or_proxy(sentiment, runtime_news)
    reasons = _quality_reason_list(quality, "news")
    if _is_timeout(runtime_news):
        _append_unique(reasons, "provider_timeout")
    status = _status_from_components(
        domain_name="news",
        statuses=(_normalized_status(sentiment), _normalized_status(runtime_news)),
        freshness=freshness,
        fallback_or_proxy=fallback,
        evidence_count=len(refs),
        reasons=reasons,
    )
    return EvidenceDomainV1(
        status=status,
        source_tier=_source_tier(sentiment, runtime_news, default="unknown"),
        provider_authority=_provider_authority(status, fallback, freshness, sentiment, runtime_news),
        freshness=freshness,
        fallback_or_proxy=fallback,
        evidence_count=len(refs),
        top_evidence_refs=refs,
        missing_reasons=tuple(reasons if status != "available" else ()),
        next_evidence_needed=_next_needed(status, "news"),
    )


def _catalysts_domain(structured: Mapping[str, Any], runtime: Mapping[str, Any], quality: Mapping[str, Any]) -> EvidenceDomainV1:
    catalyst = _mapping(structured.get("catalyst"))
    runtime_news = _mapping(runtime.get("news"))
    refs = _top_refs(catalyst)
    freshness = _domain_freshness(catalyst, runtime_news)
    fallback = _domain_fallback_or_proxy(catalyst, runtime_news)
    reasons = _quality_reason_list(quality, "catalysts")
    evidence_count = max(len(refs), len(_sequence(catalyst.get("classified_items"))))
    status = _status_from_components(
        domain_name="catalysts",
        statuses=(_normalized_status(catalyst),),
        freshness=freshness,
        fallback_or_proxy=fallback,
        evidence_count=evidence_count,
        reasons=reasons,
    )
    return EvidenceDomainV1(
        status=status,
        source_tier=_source_tier(catalyst, runtime_news, default="unknown"),
        provider_authority=_provider_authority(status, fallback, freshness, catalyst, runtime_news),
        freshness=freshness,
        fallback_or_proxy=fallback,
        evidence_count=evidence_count,
        top_evidence_refs=refs,
        missing_reasons=tuple(reasons if status != "available" else ()),
        next_evidence_needed=_next_needed(status, "catalysts"),
    )


def _sentiment_domain(structured: Mapping[str, Any], runtime: Mapping[str, Any], quality: Mapping[str, Any]) -> EvidenceDomainV1:
    sentiment = _mapping(structured.get("sentiment_analysis"))
    runtime_sentiment = _mapping(runtime.get("sentiment"))
    refs = _top_refs(sentiment)
    freshness = _domain_freshness(sentiment, runtime_sentiment)
    fallback = _domain_fallback_or_proxy(sentiment, runtime_sentiment)
    reasons = _quality_reason_list(quality, "sentiment")
    evidence_count = len(refs)
    status = _status_from_components(
        domain_name="sentiment",
        statuses=(_normalized_status(sentiment), _normalized_status(runtime_sentiment)),
        freshness=freshness,
        fallback_or_proxy=fallback,
        evidence_count=evidence_count,
        reasons=reasons,
    )
    return EvidenceDomainV1(
        status=status,
        source_tier=_source_tier(sentiment, runtime_sentiment, default="unknown"),
        provider_authority=_provider_authority(status, fallback, freshness, sentiment, runtime_sentiment),
        freshness=freshness,
        fallback_or_proxy=fallback,
        evidence_count=evidence_count,
        top_evidence_refs=refs,
        missing_reasons=tuple(reasons if status != "available" else ()),
        next_evidence_needed=_next_needed(status, "sentiment"),
    )


def _valuation_domain(
    payload: Mapping[str, Any],
    structured: Mapping[str, Any],
    runtime: Mapping[str, Any],
    quality: Mapping[str, Any],
) -> EvidenceDomainV1:
    fundamentals = _mapping(structured.get("fundamentals"))
    runtime_fundamentals = _mapping(runtime.get("fundamentals"))
    normalized = _mapping(fundamentals.get("normalized"))
    has_metrics = any(
        normalized.get(key) not in (None, "", 0)
        for key in ("trailingPE", "forwardPE", "priceToBook", "marketCap")
    )
    refs = _top_refs(fundamentals)
    freshness = _domain_freshness(fundamentals, runtime_fundamentals)
    fallback = _domain_fallback_or_proxy(fundamentals, runtime_fundamentals)
    reasons = _quality_reason_list(quality, "valuation")
    if _fundamental_context_unavailable(payload, _mapping(structured.get("fundamental_context"))):
        _append_unique(reasons, "fundamental_context_unavailable")
    status = _status_from_components(
        domain_name="valuation",
        statuses=(_normalized_status(fundamentals), _normalized_status(runtime_fundamentals)),
        freshness=freshness,
        fallback_or_proxy=fallback,
        evidence_count=1 if has_metrics else 0,
        reasons=reasons,
    )
    return EvidenceDomainV1(
        status=status,
        source_tier=_source_tier(fundamentals, runtime_fundamentals, default="unknown"),
        provider_authority=_provider_authority(status, fallback, freshness, fundamentals, runtime_fundamentals),
        freshness=freshness,
        fallback_or_proxy=fallback,
        evidence_count=1 if has_metrics else 0,
        top_evidence_refs=refs,
        missing_reasons=tuple(reasons if status != "available" else ()),
        next_evidence_needed=_next_needed(status, "valuation"),
    )


def _sector_theme_domain(structured: Mapping[str, Any], quality: Mapping[str, Any]) -> EvidenceDomainV1:
    market_context = _mapping(structured.get("market_context"))
    sector_theme = _mapping(market_context.get("sectorTheme"))
    refs = _top_refs(sector_theme, market_context)
    freshness = _domain_freshness(sector_theme, market_context)
    reasons = _quality_reason_list(quality, "sectorTheme")
    evidence_count = max(len(refs), _count_present(sector_theme.get("sector"), sector_theme.get("theme")))
    status = "available" if evidence_count > 0 else "missing"
    if status != "available":
        _append_unique(reasons, "sector_theme_missing")
    return EvidenceDomainV1(
        status=status,
        source_tier=_source_tier(sector_theme, market_context, default="unknown"),
        provider_authority="observationOnly" if status == "available" else "unavailable",
        freshness=freshness,
        fallback_or_proxy=False,
        evidence_count=evidence_count,
        top_evidence_refs=refs,
        missing_reasons=tuple(reasons if status != "available" else ()),
        next_evidence_needed=_next_needed(status, "sectorTheme"),
    )


def _macro_liquidity_domain(structured: Mapping[str, Any], quality: Mapping[str, Any]) -> EvidenceDomainV1:
    market_context = _mapping(structured.get("market_context"))
    refs = _top_refs(market_context)
    freshness = _domain_freshness(market_context)
    reasons = _quality_reason_list(quality, "macroLiquidity")
    has_macro = bool(_mapping(market_context.get("macro")))
    has_liquidity = bool(_mapping(market_context.get("liquidity")))
    evidence_count = max(len(refs), _count_present(has_macro, has_liquidity))
    status = "degraded" if evidence_count > 0 else "missing"
    if status == "missing":
        _append_unique(reasons, "macro_liquidity_missing")
    return EvidenceDomainV1(
        status=status,
        source_tier=_source_tier(market_context, default="unknown"),
        provider_authority="observationOnly" if evidence_count > 0 else "unavailable",
        freshness=freshness,
        fallback_or_proxy=False,
        evidence_count=evidence_count,
        top_evidence_refs=refs,
        missing_reasons=tuple(reasons if status != "available" else ()),
        next_evidence_needed=_next_needed(status, "macroLiquidity"),
    )


def _status_from_components(
    *,
    domain_name: str,
    statuses: Sequence[str],
    freshness: str,
    fallback_or_proxy: bool,
    evidence_count: int,
    reasons: list[str],
) -> str:
    statuses = tuple(item for item in statuses if item)
    if any(item in _WAITING_STATUSES for item in statuses):
        return "pending"
    if any(item in _BLOCKED_STATUSES for item in statuses) or "provider_timeout" in reasons:
        return "blocked"
    if any(item in _MISSING_STATUSES for item in statuses):
        return "missing"
    if evidence_count <= 0 and domain_name == "valuation":
        return "missing"
    if evidence_count <= 0 and (any(item in _DEGRADED_STATUSES for item in statuses) or fallback_or_proxy):
        return "degraded"
    if evidence_count <= 0:
        return "missing"
    if domain_name in {"news", "catalysts", "sentiment"} and not evidence_count:
        return "missing"
    if any(item in _DEGRADED_STATUSES for item in statuses):
        return "degraded"
    if fallback_or_proxy:
        return "degraded"
    if freshness in {"stale", "fallback"}:
        return "degraded"
    return "available"


def _provider_authority(
    status: str,
    fallback_or_proxy: bool,
    freshness: str,
    *blocks: Mapping[str, Any],
) -> str:
    if status in {"missing", "blocked", "pending"}:
        return "unavailable"
    authority = "observationOnly"
    for block in blocks:
        raw = _sanitize_authority(block.get("providerAuthority"))
        if raw != "unavailable":
            authority = raw
            break
    if status != "available" or fallback_or_proxy or freshness in {"stale", "fallback"}:
        return "observationOnly"
    return authority


def _quality_reason_list(quality: Mapping[str, Any], domain_name: str) -> list[str]:
    reasons: list[str] = []
    mapped_domain = domain_name
    for raw in _sequence(quality.get("missingRequiredDomains")) + _sequence(quality.get("importantDomainsMissing")):
        alias = _domain_alias(raw)
        if alias == mapped_domain:
            _append_unique(reasons, "required_evidence_missing")
    for raw in _sequence(quality.get("reasonCodes")):
        text = _sanitize_reason(raw)
        if not text:
            continue
        if text == "provider_timeout" and domain_name != "news":
            continue
        if text == "stale_required_source":
            _append_unique(reasons, "stale_evidence")
            continue
        if text == "fallback_proxy_evidence":
            _append_unique(reasons, "fallback_proxy_evidence")
            continue
        _append_unique(reasons, text)
    return reasons


def _top_refs(*blocks: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for block in blocks:
        for item in _sequence(block.get("topEvidenceRefs")):
            safe = _sanitize_ref(item)
            if safe:
                _append_unique(refs, safe)
    if refs:
        return tuple(refs[:3])
    for block in blocks:
        for key in ("top_positive_items", "top_negative_items", "classified_items"):
            for item in _sequence(block.get(key)):
                safe = _sanitize_ref(item)
                if safe:
                    _append_unique(refs, safe)
    return tuple(refs[:3])


def _sanitize_ref(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key in ("id", "ref", "evidenceRef", "headline", "title", "summary", "label"):
            safe = _sanitize_text(value.get(key))
            if safe:
                return safe
        return None
    return _sanitize_text(value)


def _domain_freshness(*blocks: Mapping[str, Any]) -> str:
    for block in blocks:
        text = str(block.get("freshness") or "").strip().lower()
        if text in {"fresh", "delayed", "stale", "fallback", "pending"}:
            return "pending" if text == "pending" else text
    return "unknown"


def _domain_fallback_or_proxy(*blocks: Mapping[str, Any]) -> bool:
    for block in blocks:
        text = " ".join(
            str(block.get(key) or "").strip().lower()
            for key in ("source", "sourceTier", "providerAuthority", "freshness")
        )
        if block.get("proxyOnly") or block.get("isFallback"):
            return True
        if "proxy" in text or "fallback" in text:
            return True
    return False


def _normalized_status(block: Mapping[str, Any]) -> str:
    text = str(block.get("status") or "").strip().lower().replace(" ", "_")
    if not text:
        return ""
    if text == "ok":
        return "available"
    if text in {"market_not_supported", "not_supported"}:
        return "missing"
    if text in _STATUS_VALUES:
        return text
    return text


def _fundamental_context_unavailable(payload: Mapping[str, Any], fundamental_context: Mapping[str, Any]) -> bool:
    market = _safe_market(payload.get("market"))
    status = str(fundamental_context.get("status") or "").strip().lower()
    if market not in {"us", "hk"}:
        return False
    if "not supported" in status or "unsupported" in status:
        return True
    return False


def _is_timeout(block: Mapping[str, Any]) -> bool:
    status = str(block.get("status") or "").strip().lower()
    error_text = " ".join(str(block.get(key) or "").strip().lower() for key in ("error", "reason", "message"))
    return "timeout" in status or "timeout" in error_text


def _next_needed(status: str, domain_name: str) -> tuple[str, ...]:
    if status in {"available", "not_applicable"}:
        return ()
    return (_NEXT_EVIDENCE[domain_name],)


def _safe_symbol(value: Any) -> str:
    text = str(value or "").strip().upper()
    safe = "".join(char for char in text if char.isalnum() or char in ".-_")
    return safe[:24] or "UNKNOWN"


def _safe_market(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"us", "hk", "cn"} else "unknown"


def _no_advice_boundary(value: Any) -> dict[str, str]:
    if value is True:
        return {
            "state": "no_advice",
            "label": "仅研究，不构成投资建议",
        }
    return {
        "state": "blocked",
        "label": "仅研究，禁止转化为交易或执行建议",
    }


def _source_tier(*blocks: Mapping[str, Any], default: str) -> str:
    for block in blocks:
        safe = _sanitize_text(block.get("sourceTier"))
        if safe:
            return safe
    return default


def _sanitize_authority(value: Any) -> str:
    text = str(value or "").strip()
    return text if text in {"scoreGradeAllowed", "observationOnly", "unavailable"} else "unavailable"


def _count_present(*values: Any) -> int:
    total = 0
    for value in values:
        if isinstance(value, bool):
            total += int(value)
        elif value not in (None, "", 0, 0.0, False):
            total += 1
    return total


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _append_unique(target: list[str], value: str | None) -> None:
    text = str(value or "").strip()
    if text and text not in target:
        target.append(text)


def _domain_alias(value: Any) -> str | None:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _DOMAIN_ALIASES.get(text)


def _sanitize_reason(value: Any) -> str | None:
    text = str(value or "").strip().lower().replace(" ", "_")
    if not text:
        return None
    if any(marker in text for marker in _SECRET_MARKERS):
        return None
    return text[:64]


def _sanitize_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        return None
    if any(word in lowered for word in _FORBIDDEN_ADVICE_WORDS):
        return None
    if "{" in text or "}" in text or "[" in text or "]" in text:
        return None
    if len(text) > 96:
        return None
    for char in text:
        lower = char.lower()
        if lower not in _SAFE_TEXT_CHARS and not char.isascii():
            return None
        if lower not in _SAFE_TEXT_CHARS and char.isascii() and not char.isalnum():
            return None
    return text
