# -*- coding: utf-8 -*-
"""Pure helper for bounded single-stock news/catalyst evidence extraction."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from src.services.single_stock_source_capability_matrix import (
    normalize_single_stock_source_id,
    summarize_source_capabilities_by_domain,
)


SINGLE_STOCK_NEWS_CATALYST_EXTRACTOR_VERSION = (
    "single_stock_news_catalyst_extractor_v1"
)

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
    "token=",
    "token",
    "traceback",
    "trade now",
)
_TIMEOUT_STATUSES = frozenset({"timeout", "timed_out", "blocked", "failed", "error"})
_MISSING_STATUSES = frozenset(
    {"", "missing", "unknown", "unavailable", "unsupported", "weak", "empty"}
)
_DEGRADED_STATUSES = frozenset(
    {"partial", "degraded", "fallback", "stale", "delayed", "weak", "pending"}
)
_NEGATIVE_TOKENS = ("lawsuit", "probe", "fine", "downgrade", "miss", "risk", "fall")
_POSITIVE_TOKENS = ("beat", "raise", "guidance", "growth", "launch", "record", "buyback")
_DOMAIN_LABELS = {
    "news": "补充结构化新闻证据",
    "catalysts": "补充结构化催化剂证据",
    "sentiment": "补充情绪证据",
}
_CATALYST_KEYWORDS = (
    ("guidance", "guidance"),
    ("earnings", "earnings"),
    ("product", "product_launch"),
    ("launch", "product_launch"),
    ("wwdc", "product_launch"),
    ("partnership", "partnership"),
    ("buyback", "capital_return"),
    ("probe", "regulatory"),
    ("regulation", "regulatory"),
    ("lawsuit", "regulatory"),
)


def build_single_stock_news_catalyst_extractor_v1(
    value: Mapping[str, Any] | None,
    *,
    max_items_per_domain: int = 5,
) -> dict[str, Any]:
    """Normalize existing single-stock inputs into bounded news/catalyst evidence."""

    payload = _mapping(value)
    structured = _mapping(
        _first_present(payload.get("structuredAnalysis"), payload.get("structured_analysis"))
    )
    quality = _mapping(
        _first_present(payload.get("dataQualityReport"), payload.get("data_quality_report"))
    )
    runtime = _mapping(_first_present(payload.get("runtimeData"), payload.get("runtime_data")))
    runtime_news = _mapping(runtime.get("news"))
    runtime_sentiment = _mapping(runtime.get("sentiment"))
    sentiment_block = _mapping(
        _first_present(structured.get("sentiment_analysis"), structured.get("sentiment"))
    )
    catalyst_block = _mapping(structured.get("catalyst"))
    news_context = _sanitize_text(
        _first_present(payload.get("news_context"), structured.get("news_context"))
    )
    no_advice_boundary = _no_advice_boundary(payload.get("noAdviceBoundary"))

    top_news_items = _extract_news_items(
        sentiment_block=sentiment_block,
        news_context=news_context,
        max_items=max_items_per_domain,
    )
    top_catalyst_items = _extract_catalyst_items(
        catalyst_block=catalyst_block,
        sentiment_block=sentiment_block,
        news_context=news_context,
        max_items=max_items_per_domain,
    )

    source_summary = _build_source_summary(
        top_news_items=top_news_items,
        top_catalyst_items=top_catalyst_items,
        sentiment_block=sentiment_block,
        catalyst_block=catalyst_block,
        runtime_news=runtime_news,
        runtime_sentiment=runtime_sentiment,
    )

    news_domain = _domain_state(
        domain="news",
        items=top_news_items,
        block=sentiment_block,
        runtime=runtime_news,
        source_summary=source_summary["news"],
        context_only=bool(news_context) and not _has_structured_news(sentiment_block),
    )
    catalyst_domain = _domain_state(
        domain="catalysts",
        items=top_catalyst_items,
        block=catalyst_block,
        runtime=runtime_news,
        source_summary=source_summary["catalysts"],
        context_only=bool(news_context) and not _has_structured_catalysts(catalyst_block),
    )
    sentiment_domain = _domain_state(
        domain="sentiment",
        items=top_news_items,
        block=sentiment_block,
        runtime=runtime_sentiment,
        source_summary=source_summary["sentiment"],
        context_only=bool(news_context) and not _has_structured_news(sentiment_block),
    )

    missing_evidence: list[str] = []
    blocking_reasons: list[str] = []
    next_evidence_needed: list[str] = []
    for domain_state in (news_domain, catalyst_domain, sentiment_domain):
        if domain_state["status"] == "missing":
            _append_unique(missing_evidence, domain_state["domain"])
        for reason in domain_state["reasonCodes"]:
            _append_unique(blocking_reasons, reason)
        for needed in domain_state["nextEvidenceNeeded"]:
            _append_unique(next_evidence_needed, needed)

    for reason in _quality_reason_codes(quality):
        _append_unique(blocking_reasons, reason)
    if no_advice_boundary["state"] == "blocked":
        _append_unique(blocking_reasons, "no_advice_boundary_missing")

    extraction_state = _extraction_state(
        news_domain=news_domain,
        catalyst_domain=catalyst_domain,
        sentiment_domain=sentiment_domain,
        quality=quality,
        no_advice_boundary=no_advice_boundary,
    )

    source_summary.update(
        {
            "availableCount": sum(
                1 for domain_state in (news_domain, catalyst_domain, sentiment_domain)
                if domain_state["status"] == "available"
            ),
            "degradedCount": sum(
                1 for domain_state in (news_domain, catalyst_domain, sentiment_domain)
                if domain_state["status"] == "degraded"
            ),
            "missingCount": sum(
                1 for domain_state in (news_domain, catalyst_domain, sentiment_domain)
                if domain_state["status"] == "missing"
            ),
            "blockedCount": sum(
                1 for domain_state in (news_domain, catalyst_domain, sentiment_domain)
                if domain_state["status"] == "blocked"
            ),
        }
    )

    return {
        "contractVersion": SINGLE_STOCK_NEWS_CATALYST_EXTRACTOR_VERSION,
        "symbol": _safe_symbol(payload.get("symbol")),
        "market": _safe_market(payload.get("market")),
        "extractionState": extraction_state,
        "topNewsItems": top_news_items,
        "topCatalystItems": top_catalyst_items,
        "sentimentSummary": _sentiment_summary(
            sentiment_block=sentiment_block,
            sentiment_domain=sentiment_domain,
            source_summary=source_summary["sentiment"],
            top_news_items=top_news_items,
        ),
        "missingEvidence": missing_evidence,
        "blockingReasons": blocking_reasons,
        "nextEvidenceNeeded": next_evidence_needed,
        "sourceSummary": source_summary,
        "noAdviceBoundary": no_advice_boundary,
        "debugRef": _sanitize_debug_ref(payload.get("debugRef")),
    }


def _extract_news_items(
    *,
    sentiment_block: Mapping[str, Any],
    news_context: str,
    max_items: int,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_item in _sequence(sentiment_block.get("top_positive_items")):
        _append_item(items, seen, _normalize_item(raw_item, domain="news", default_sentiment="positive"))
    for raw_item in _sequence(sentiment_block.get("top_negative_items")):
        _append_item(items, seen, _normalize_item(raw_item, domain="news", default_sentiment="negative"))
    for raw_item in _sequence(sentiment_block.get("classified_items")):
        _append_item(items, seen, _normalize_item(raw_item, domain="news", default_sentiment=None))
    if not items and news_context:
        for index, sentence in enumerate(_split_news_context(news_context), start=1):
            _append_item(
                items,
                seen,
                _context_item(sentence=sentence, index=index, domain="news"),
            )
    return _sort_items(items)[: _bounded_max(max_items)]


def _extract_catalyst_items(
    *,
    catalyst_block: Mapping[str, Any],
    sentiment_block: Mapping[str, Any],
    news_context: str,
    max_items: int,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_item in _sequence(catalyst_block.get("classified_items")):
        _append_item(items, seen, _normalize_item(raw_item, domain="catalysts", default_sentiment=None))
    if not items:
        for raw_item in _sequence(sentiment_block.get("classified_items")):
            normalized = _normalize_item(raw_item, domain="catalysts", default_sentiment=None)
            if normalized and normalized["catalystType"] != "unknown":
                _append_item(items, seen, normalized)
    if not items and news_context:
        for index, sentence in enumerate(_split_news_context(news_context), start=1):
            normalized = _context_item(sentence=sentence, index=index, domain="catalysts")
            if normalized["catalystType"] != "unknown":
                _append_item(items, seen, normalized)
    return _sort_items(items)[: _bounded_max(max_items)]


def _build_source_summary(
    *,
    top_news_items: Sequence[Mapping[str, Any]],
    top_catalyst_items: Sequence[Mapping[str, Any]],
    sentiment_block: Mapping[str, Any],
    catalyst_block: Mapping[str, Any],
    runtime_news: Mapping[str, Any],
    runtime_sentiment: Mapping[str, Any],
) -> dict[str, Any]:
    raw = summarize_source_capabilities_by_domain(
        {
            "news": _source_ids_for_domain(
                top_news_items,
                sentiment_block.get("source"),
                runtime_news.get("source"),
            ),
            "catalysts": _source_ids_for_domain(
                top_catalyst_items,
                catalyst_block.get("source"),
                runtime_news.get("source"),
            ),
            "sentiment": _source_ids_for_domain(
                (),
                sentiment_block.get("source"),
                runtime_sentiment.get("source"),
            ),
        }
    )
    return {
        domain: {
            **raw.get(domain, _empty_source_summary(domain)),
            "status": "missing",
            "itemCount": len(top_news_items if domain == "news" else top_catalyst_items if domain == "catalysts" else (top_news_items if top_news_items else [])),
        }
        for domain in ("news", "catalysts", "sentiment")
    }


def _domain_state(
    *,
    domain: str,
    items: Sequence[Mapping[str, Any]],
    block: Mapping[str, Any],
    runtime: Mapping[str, Any],
    source_summary: dict[str, Any],
    context_only: bool,
) -> dict[str, Any]:
    reasons: list[str] = []
    next_needed: list[str] = []
    status_texts = {
        _status(block),
        _status(runtime),
    }
    raw_text = " ".join(
        [
            _sanitize_text(runtime.get("error")),
            _sanitize_text(block.get("failure_reason")),
            _sanitize_text(block.get("sentiment_summary")),
        ]
    ).lower()
    has_timeout = bool(status_texts & _TIMEOUT_STATUSES) or "provider_timeout" in raw_text
    if has_timeout:
        _append_unique(reasons, "provider_timeout")
        source_summary["status"] = "blocked"
        return {
            "domain": domain,
            "status": "blocked",
            "reasonCodes": reasons,
            "nextEvidenceNeeded": [_DOMAIN_LABELS[domain]],
        }

    if not items:
        if "no_reliable_news" in raw_text or "relevance_too_low" in raw_text:
            _append_unique(reasons, "no_reliable_news")
        if domain == "catalysts":
            _append_unique(reasons, "catalyst_items_missing")
        if domain == "sentiment":
            _append_unique(reasons, "sentiment_summary_missing")
        _append_unique(next_needed, _DOMAIN_LABELS[domain])
        source_summary["status"] = "missing"
        return {
            "domain": domain,
            "status": "missing",
            "reasonCodes": reasons,
            "nextEvidenceNeeded": next_needed,
        }

    degraded = context_only
    if context_only:
        _append_unique(reasons, "news_context_only")
        _append_unique(next_needed, _DOMAIN_LABELS[domain])

    freshness_values = {
        _freshness(block),
        _freshness(runtime),
        *(_freshness(item) for item in items),
    }
    if any(value in {"stale", "delayed"} for value in freshness_values):
        degraded = True
        _append_unique(reasons, "stale_evidence")
    if _is_fallback_like(block) or _is_fallback_like(runtime) or any(_is_fallback_like(item) for item in items):
        degraded = True
        _append_unique(reasons, "fallback_proxy_evidence")
    if source_summary.get("bestAuthorityTier") == "unknown" and (
        domain != "sentiment" or source_summary.get("sourceIds") == ["manual_unknown"]
    ):
        degraded = True
        _append_unique(reasons, "unknown_source_authority")
    if _status(block) in _DEGRADED_STATUSES or _status(runtime) in _DEGRADED_STATUSES:
        degraded = True

    final_status = "degraded" if degraded else "available"
    source_summary["status"] = final_status
    return {
        "domain": domain,
        "status": final_status,
        "reasonCodes": reasons,
        "nextEvidenceNeeded": next_needed,
    }


def _extraction_state(
    *,
    news_domain: Mapping[str, Any],
    catalyst_domain: Mapping[str, Any],
    sentiment_domain: Mapping[str, Any],
    quality: Mapping[str, Any],
    no_advice_boundary: Mapping[str, Any],
) -> str:
    if no_advice_boundary.get("state") == "blocked":
        return "blocked"
    if any(domain["status"] == "blocked" for domain in (news_domain, catalyst_domain, sentiment_domain)):
        return "blocked"
    quality_missing = {
        _normalize_domain_name(item)
        for item in _sequence(quality.get("missingRequiredDomains"))
    }
    if quality_missing & {"news", "catalysts", "sentiment"}:
        return "insufficient"
    if news_domain["status"] == "missing" and sentiment_domain["status"] == "missing":
        return "insufficient"
    if any(domain["status"] == "degraded" for domain in (news_domain, catalyst_domain, sentiment_domain)):
        return "observe_only"
    return "ready"


def _sentiment_summary(
    *,
    sentiment_block: Mapping[str, Any],
    sentiment_domain: Mapping[str, Any],
    source_summary: Mapping[str, Any],
    top_news_items: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    label = _sentiment_label(
        _first_present(sentiment_block.get("sentiment_summary"), _dominant_sentiment(top_news_items))
    )
    return {
        "status": sentiment_domain["status"],
        "label": label,
        "sourceIds": list(source_summary.get("sourceIds") or []),
        "bestAuthorityTier": str(source_summary.get("bestAuthorityTier") or "unknown"),
        "freshness": _freshness(sentiment_block) or str(source_summary.get("freshnessClass") or "unknown"),
        "scoreContributionAllowed": bool(source_summary.get("scoreContributionAllowed")),
        "limitations": list(source_summary.get("limitations") or []),
    }


def _normalize_item(
    raw_item: Any,
    *,
    domain: str,
    default_sentiment: str | None,
) -> dict[str, Any] | None:
    item = _mapping(raw_item)
    title = _sanitize_text(_first_present(item.get("headline"), item.get("title")))
    summary = _sanitize_text(_first_present(item.get("summary"), item.get("snippet"), item.get("description")))
    if not title and not summary:
        return None
    source_id = normalize_single_stock_source_id(_first_present(item.get("sourceId"), item.get("source")))
    source_summary = summarize_source_capabilities_by_domain({domain: [source_id]}).get(
        domain,
        _empty_source_summary(domain),
    )
    freshness = _freshness(item) or str(source_summary.get("freshnessClass") or "unknown")
    fallback_like = _is_fallback_like(item) or source_summary.get("bestAuthorityTier") in {
        "fallback",
        "fixture_demo",
        "unknown",
    }
    provider_authority = (
        "scoreGradeAllowed"
        if source_summary.get("scoreContributionAllowed") and not fallback_like
        else "observationOnly"
    )
    return {
        "id": _safe_id(_first_present(item.get("id"), item.get("news_id"), title)),
        "domain": domain,
        "title": title or summary[:80],
        "summary": summary or title[:120],
        "sourceId": source_id,
        "sourceTier": _safe_source_tier(
            _first_present(item.get("sourceTier"), item.get("source_tier"), source_summary.get("bestAuthorityTier"))
        ),
        "providerAuthority": provider_authority,
        "publishedAt": _safe_timestamp(
            _first_present(item.get("publishedAt"), item.get("published_at"), item.get("news_published_at"))
        ),
        "freshness": freshness,
        "sentiment": _sentiment_label(_first_present(item.get("sentiment"), default_sentiment, title, summary)),
        "catalystType": _catalyst_type(_first_present(item.get("catalyst_type"), item.get("catalystType"), title, summary)),
        "relevanceScore": _relevance_score(item, title, summary, domain),
        "limitations": list(source_summary.get("limitations") or [])[:3],
    }


def _context_item(*, sentence: str, index: int, domain: str) -> dict[str, Any]:
    title = _truncate(sentence.strip(), 88)
    return {
        "id": f"{domain}-context-{index}",
        "domain": domain,
        "title": title,
        "summary": _truncate(sentence.strip(), 160),
        "sourceId": "manual_unknown",
        "sourceTier": "unknown",
        "providerAuthority": "observationOnly",
        "publishedAt": None,
        "freshness": "unknown",
        "sentiment": _sentiment_label(sentence),
        "catalystType": _catalyst_type(sentence),
        "relevanceScore": _context_relevance(sentence, domain),
        "limitations": ["Derived from flattened news_context text; structured citation fields were unavailable."],
    }


def _sort_items(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in sorted(
            items,
            key=lambda item: (
                -float(item.get("relevanceScore") or 0.0),
                str(item.get("publishedAt") or ""),
                str(item.get("id") or ""),
            ),
            reverse=False,
        )
    ]


def _dominant_sentiment(items: Sequence[Mapping[str, Any]]) -> str:
    scores = {"positive": 0, "negative": 0, "neutral": 0}
    for item in items:
        label = _sentiment_label(item.get("sentiment"))
        scores[label] = scores.get(label, 0) + 1
    return max(scores, key=lambda key: (scores[key], key))


def _relevance_score(item: Mapping[str, Any], title: str, summary: str, domain: str) -> float:
    raw = item.get("relevance_score")
    if isinstance(raw, (int, float)):
        return round(max(0.0, min(float(raw), 1.0)), 2)
    return _context_relevance(f"{title} {summary}".strip(), domain)


def _context_relevance(text: str, domain: str) -> float:
    lowered = text.lower()
    score = 0.45
    if any(token in lowered for token in _POSITIVE_TOKENS):
        score += 0.25
    if any(token in lowered for token in _NEGATIVE_TOKENS):
        score += 0.15
    if domain == "catalysts" and _catalyst_type(text) != "unknown":
        score += 0.2
        catalyst_type = _catalyst_type(text)
        if catalyst_type == "guidance":
            score += 0.12
        elif catalyst_type == "product_launch":
            score += 0.08
        elif catalyst_type == "earnings":
            score += 0.04
    return round(min(score, 0.99), 2)


def _catalyst_type(value: Any) -> str:
    lowered = _sanitize_text(value).lower()
    for token, label in _CATALYST_KEYWORDS:
        if token in lowered:
            return label
    return "unknown"


def _sentiment_label(value: Any) -> str:
    lowered = _sanitize_text(value).lower()
    if any(token in lowered for token in _NEGATIVE_TOKENS):
        return "negative"
    if any(token in lowered for token in _POSITIVE_TOKENS):
        return "positive"
    if lowered in {"positive", "negative", "neutral"}:
        return lowered
    return "neutral"


def _has_structured_news(sentiment_block: Mapping[str, Any]) -> bool:
    return bool(
        _sequence(sentiment_block.get("top_positive_items"))
        or _sequence(sentiment_block.get("top_negative_items"))
        or _sequence(sentiment_block.get("classified_items"))
    )


def _has_structured_catalysts(catalyst_block: Mapping[str, Any]) -> bool:
    return bool(_sequence(catalyst_block.get("classified_items")))


def _source_ids_for_domain(
    items: Sequence[Mapping[str, Any]],
    *extra_sources: Any,
) -> list[str]:
    source_ids: list[str] = []
    for item in items:
        _append_unique(source_ids, normalize_single_stock_source_id(item.get("sourceId")))
    for source in extra_sources:
        text = str(source or "").strip()
        if text:
            _append_unique(source_ids, normalize_single_stock_source_id(text))
    return source_ids or ["manual_unknown"]


def _empty_source_summary(domain: str) -> dict[str, Any]:
    return {
        "domain": domain,
        "sourceIds": ["manual_unknown"],
        "bestAuthorityTier": "unknown",
        "freshnessClass": "unknown",
        "marketCoverage": [],
        "scoreContributionAllowed": False,
        "observationOnly": True,
        "fallbackOrProxy": False,
        "limitations": [],
        "nextEvidenceNeeded": [_DOMAIN_LABELS[domain]],
    }


def _quality_reason_codes(quality: Mapping[str, Any]) -> list[str]:
    reason_codes: list[str] = []
    for raw in _sequence(quality.get("reasonCodes")):
        text = _sanitize_text(raw).lower().replace(" ", "_")
        if text:
            _append_unique(reason_codes, text)
    return reason_codes


def _normalize_domain_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text == "catalyst":
        return "catalysts"
    return text


def _no_advice_boundary(value: Any) -> dict[str, str]:
    if value in (True, "true", "no_advice", "no-advice", "仅研究"):
        return {"state": "no_advice", "label": "仅研究，不构成投资建议"}
    return {"state": "blocked", "label": "仅研究，禁止转化为交易或执行建议"}


def _is_fallback_like(value: Any) -> bool:
    payload = _mapping(value)
    text = " ".join(
        [
            _sanitize_text(payload.get("source")),
            _sanitize_text(payload.get("sourceTier")),
            _sanitize_text(payload.get("providerAuthority")),
            _sanitize_text(payload.get("freshness")),
            _sanitize_text(payload.get("status")),
        ]
    ).lower()
    return bool(
        payload.get("proxyOnly")
        or payload.get("isFallback")
        or "proxy" in text
        or "fallback" in text
        or "fixture" in text
    )


def _freshness(value: Any) -> str:
    payload = _mapping(value)
    text = _sanitize_text(_first_present(payload.get("freshness"), payload.get("freshnessClass"))).lower()
    if text in {"fresh", "daily", "realtime", "local", "delayed", "stale", "fallback", "fixture", "unknown"}:
        return text
    return "unknown"


def _status(value: Any) -> str:
    payload = _mapping(value)
    text = _sanitize_text(payload.get("status")).lower()
    return text or "missing"


def _split_news_context(text: str) -> list[str]:
    parts = re.split(r"[。\.\n!?;]+", text)
    cleaned = [_sanitize_text(part) for part in parts]
    return [part for part in cleaned if part][:8]


def _sanitize_debug_ref(value: Any) -> str | None:
    text = _sanitize_text(value)
    if not text:
        return None
    return _truncate(re.sub(r"[^a-zA-Z0-9:/._-]+", "", text), 96)


def _safe_id(value: Any) -> str:
    text = _sanitize_text(value)
    text = re.sub(r"[^a-zA-Z0-9._:-]+", "-", text).strip("-")
    return text[:64] or "item-unknown"


def _safe_symbol(value: Any) -> str | None:
    text = _sanitize_text(value).upper()
    return text or None


def _safe_market(value: Any) -> str | None:
    text = _sanitize_text(value).lower()
    return text or None


def _safe_source_tier(value: Any) -> str:
    text = _sanitize_text(value).lower().replace(" ", "_")
    return text or "unknown"


def _safe_timestamp(value: Any) -> str | None:
    text = _sanitize_text(value)
    return text[:32] or None


def _sanitize_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if any(token in lowered for token in _FORBIDDEN_TEXT_MARKERS):
        return ""
    text = re.sub(r"\s+", " ", text)
    return _truncate(text, 180)


def _truncate(value: str, length: int) -> str:
    return value[:length].strip()


def _append_item(
    items: list[dict[str, Any]],
    seen: set[str],
    item: dict[str, Any] | None,
) -> None:
    if item is None:
        return
    key = str(item.get("id") or item.get("title") or "")
    if not key or key in seen:
        return
    seen.add(key)
    items.append(item)


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _bounded_max(value: int) -> int:
    return max(1, min(int(value), 10))


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []


def _first_present(*values: Any) -> Any:
    for value in values:
        if isinstance(value, str):
            if value.strip():
                return value
            continue
        if value not in (None, "", [], {}):
            return value
    return None


__all__ = [
    "SINGLE_STOCK_NEWS_CATALYST_EXTRACTOR_VERSION",
    "build_single_stock_news_catalyst_extractor_v1",
]
