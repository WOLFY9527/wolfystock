# -*- coding: utf-8 -*-
"""Pure additive adapter for bounded Home LLM evidence input."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


HOME_LLM_EVIDENCE_INPUT_VERSION = "home_llm_evidence_input_v1"

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
_EVIDENCE_DOMAIN_ORDER = (
    "fundamentals",
    "earnings",
    "valuation",
    "news",
    "catalysts",
    "sentiment",
)
_DOMAIN_LIMITS = {
    "fundamentals": 3,
    "earnings": 2,
    "valuation": 2,
    "news": 3,
    "catalysts": 2,
    "sentiment": 1,
}
_FORBIDDEN_TEXT_MARKERS = (
    "authorization",
    "api_key",
    "apikey",
    "bearer",
    "broker",
    "cache_key",
    "cookie",
    "internal_env",
    "order",
    "prompt:",
    "prompt_dump",
    "raw_prompt",
    "router_debug",
    "secret",
    "stack trace",
    "submit order",
    "token",
    "traceback",
    "trade",
)
_REASON_LABELS = {
    "fundamental_context_unavailable": "当前市场不支持可用的基础面上下文字段，必须明确为证据不足。",
    "provider_timeout": "相关新闻或催化剂抓取超时，必须保留为阻塞证据。",
    "news_context_only": "仅有扁平化上下文文本，没有结构化新闻条目。",
    "fallback_proxy_evidence": "当前证据来自回退或代理来源，只能作观察说明。",
    "stale_evidence": "当前证据新鲜度不足，不能推导高把握结论。",
    "manual_unknown": "来源权威性未知，不能视为已验证事实。",
    "unsupported_market": "当前市场不支持该证据域的可靠输入。",
    "no_structured_items": "当前缺少可引用的结构化条目。",
    "no_score_grade_source": "当前没有可作为高权威依据的来源。",
    "observation_only_evidence": "当前证据仅支持观察说明，不支持强化判断。",
    "missing_required_evidence": "当前缺少必要证据，禁止补全为已支持结论。",
    "sentiment_summary_missing": "当前缺少结构化情绪摘要。",
    "catalyst_items_missing": "当前缺少结构化催化剂条目。",
    "no_reliable_news": "当前没有足够可靠的相关新闻证据。",
}
_STATUS_REASON_DEFAULTS = {
    "missing": "missing_required_evidence",
    "blocked": "provider_timeout",
    "degraded": "observation_only_evidence",
    "pending": "manual_unknown",
}
_AUTHORITY_LABELS = {
    "scoreGradeAllowed": "scoreGrade",
    "score_grade": "scoreGrade",
    "observationOnly": "observationOnly",
    "observation_only": "observationOnly",
    "official_public": "observationOnly",
    "unknown": "unavailable",
}
_FRESHNESS_LABELS = {
    "fresh": "fresh",
    "realtime": "fresh",
    "local": "fresh",
    "daily": "fresh",
    "delayed": "delayed",
    "fallback": "delayed",
    "stale": "stale",
    "unknown": "unknown",
    "unavailable": "unavailable",
}


def build_home_llm_evidence_input_v1(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a prompt-safe Home evidence input object."""

    payload = _mapping(value)
    packet = _mapping(payload.get("singleStockEvidencePacket"))
    fundamentals = _mapping(payload.get("fundamentalsEarnings"))
    news = _mapping(payload.get("newsCatalysts"))
    readiness = _mapping(payload.get("researchReadiness"))
    coverage = _mapping(payload.get("evidenceCoverageFrame"))

    evidence_index = _build_evidence_index(fundamentals, news)
    domain_summaries = _build_domain_summaries(
        packet=packet,
        fundamentals=fundamentals,
        news=news,
        coverage=coverage,
        evidence_index=evidence_index,
    )
    missing_evidence = _collect_domain_notes(domain_summaries, statuses={"missing"})
    degraded_evidence = _collect_domain_notes(domain_summaries, statuses={"degraded"})
    blocked_evidence = _collect_domain_notes(domain_summaries, statuses={"blocked", "pending"})
    authority_notes = _collect_authority_notes(domain_summaries)
    freshness_notes = _collect_freshness_notes(domain_summaries)
    input_state = _input_state(
        packet=packet,
        fundamentals=fundamentals,
        news=news,
        readiness=readiness,
        domain_summaries=domain_summaries,
    )

    return {
        "contractVersion": HOME_LLM_EVIDENCE_INPUT_VERSION,
        "symbol": _safe_symbol(_first_present(packet.get("symbol"), fundamentals.get("symbol"), news.get("symbol"))),
        "market": _safe_market(_first_present(packet.get("market"), fundamentals.get("market"), news.get("market"))),
        "inputState": input_state,
        "domainSummaries": domain_summaries,
        "evidenceIndex": evidence_index,
        "missingEvidence": missing_evidence,
        "degradedEvidence": degraded_evidence,
        "blockedEvidence": blocked_evidence,
        "authorityNotes": authority_notes,
        "freshnessNotes": freshness_notes,
        "noAdviceBoundary": _no_advice_boundary(packet, fundamentals, news),
        "debugRef": _sanitize_text(
            _first_present(
                payload.get("debugRef"),
                packet.get("debugRef"),
                fundamentals.get("debugRef"),
                news.get("debugRef"),
            ),
            limit=80,
        )
        or "redacted",
    }


def format_home_llm_evidence_input_prompt_section(value: Mapping[str, Any] | None) -> str:
    """Render the bounded evidence input as a compact prompt section."""

    payload = _mapping(value)
    if not payload:
        return ""
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return (
        "[STRUCTURED_HOME_EVIDENCE_INPUT_V1]\n"
        "以下对象仅供研究解释，不得将缺失/降级/阻塞证据补全为已支持事实；"
        "禁止输出买入/卖出/下单/交易/经纪商执行语言。\n"
        f"{serialized}\n"
        "[/STRUCTURED_HOME_EVIDENCE_INPUT_V1]"
    )


def _build_evidence_index(
    fundamentals: Mapping[str, Any],
    news: Mapping[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    evidence_refs = _sequence(fundamentals.get("evidenceRefs"))
    for domain in ("fundamentals", "earnings", "valuation"):
        refs = [item for item in evidence_refs if _safe_domain(_mapping(item).get("domain")) == domain]
        for ref in refs[: _DOMAIN_LIMITS[domain]]:
            normalized = _normalize_fundamental_ref(ref, domain)
            if normalized:
                items.append(normalized)
    for item in _sequence(news.get("topNewsItems"))[: _DOMAIN_LIMITS["news"]]:
        normalized = _normalize_news_item(item, domain="news")
        if normalized:
            items.append(normalized)
    for item in _sequence(news.get("topCatalystItems"))[: _DOMAIN_LIMITS["catalysts"]]:
        normalized = _normalize_news_item(item, domain="catalysts")
        if normalized:
            items.append(normalized)
    sentiment_summary = _mapping(news.get("sentimentSummary"))
    sentiment_item = _normalize_sentiment_summary(sentiment_summary)
    if sentiment_item:
        items.append(sentiment_item)
    return items


def _normalize_fundamental_ref(value: Any, domain: str) -> dict[str, Any] | None:
    ref = _mapping(value)
    label = _sanitize_text(ref.get("label"), limit=64)
    if not label:
        return None
    summary = _summarize_value(ref.get("value"))
    if not summary:
        return None
    return {
        "id": _safe_id(ref.get("id"), fallback=label),
        "domain": domain,
        "label": label,
        "summary": _truncate(f"{label}: {summary}", 160),
        "sourceId": _safe_source_id(ref.get("sourceId")),
        "providerAuthority": _safe_provider_authority(ref.get("providerAuthority")),
        "freshness": _safe_freshness(ref.get("freshness")),
        "asOf": _safe_timestamp(ref.get("asOf")),
        "limitation": _primary_limitation(ref.get("limitations")),
    }


def _normalize_news_item(value: Any, domain: str) -> dict[str, Any] | None:
    item = _mapping(value)
    label = _sanitize_text(_first_present(item.get("title"), item.get("headline")), limit=72)
    summary = _sanitize_text(item.get("summary"), limit=120)
    if not label and not summary:
        return None
    effective_label = label or summary
    effective_summary = summary or effective_label
    return {
        "id": _safe_id(item.get("id"), fallback=effective_label),
        "domain": domain,
        "label": effective_label,
        "summary": effective_summary,
        "sourceId": _safe_source_id(item.get("sourceId")),
        "providerAuthority": _safe_provider_authority(item.get("providerAuthority")),
        "freshness": _safe_freshness(item.get("freshness")),
        "asOf": _safe_timestamp(_first_present(item.get("publishedAt"), item.get("asOf"))),
        "limitation": _primary_limitation(item.get("limitations")),
    }


def _normalize_sentiment_summary(value: Mapping[str, Any]) -> dict[str, Any] | None:
    if not value:
        return None
    label = _sanitize_text(value.get("label"), limit=40)
    status = _sanitize_text(value.get("status"), limit=24)
    if not label and not status:
        return None
    summary = _truncate(
        f"Sentiment summary: label={label or 'unknown'}; status={status or 'unknown'}",
        160,
    )
    return {
        "id": "sentiment-summary",
        "domain": "sentiment",
        "label": "Sentiment summary",
        "summary": summary,
        "sourceId": _safe_source_id((_sequence(value.get("sourceIds")) or ["manual_unknown"])[0]),
        "providerAuthority": (
            "scoreGradeAllowed" if bool(value.get("scoreContributionAllowed")) else "observationOnly"
        ),
        "freshness": _safe_freshness(value.get("freshness")),
        "asOf": None,
        "limitation": _primary_limitation(value.get("limitations")),
    }


def _build_domain_summaries(
    *,
    packet: Mapping[str, Any],
    fundamentals: Mapping[str, Any],
    news: Mapping[str, Any],
    coverage: Mapping[str, Any],
    evidence_index: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    packet_domains = _mapping(packet.get("domains"))
    fundamentals_domains = _mapping(fundamentals.get("domains"))
    news_source_summary = _mapping(news.get("sourceSummary"))
    evidence_ids_by_domain = _evidence_ids_by_domain(evidence_index)

    summaries: list[dict[str, Any]] = []
    for domain in _DOMAIN_ORDER:
        packet_domain = _mapping(packet_domains.get(domain))
        fundamental_domain = _mapping(fundamentals_domains.get(domain))
        coverage_domain = _mapping(coverage.get(domain))
        news_domain_summary = _mapping(news_source_summary.get(domain))
        status = _domain_status(packet_domain, fundamental_domain, coverage_domain, news_domain_summary)
        reason_codes = _domain_reason_codes(packet_domain, fundamental_domain, coverage_domain, news_domain_summary, status)
        notes = [_reason_note(reason) for reason in reason_codes][:3]
        authority_label = _authority_label(packet_domain, fundamental_domain, coverage_domain, news_domain_summary)
        freshness_label = _freshness_label(packet_domain, fundamental_domain, coverage_domain, news_domain_summary)
        summaries.append(
            {
                "domain": domain,
                "status": status,
                "authorityLabel": authority_label,
                "freshnessLabel": freshness_label,
                "evidenceRefIds": list(evidence_ids_by_domain.get(domain, ()))[:3],
                "notes": notes,
            }
        )
    return summaries


def _domain_status(
    packet_domain: Mapping[str, Any],
    fundamental_domain: Mapping[str, Any],
    coverage_domain: Mapping[str, Any],
    news_domain_summary: Mapping[str, Any],
) -> str:
    for source in (packet_domain, fundamental_domain, coverage_domain, news_domain_summary):
        raw = _sanitize_text(source.get("status"), limit=24).lower()
        if raw in {"available", "degraded", "missing", "blocked", "pending"}:
            return raw
        if raw in {"ok", "ready"}:
            return "available"
        if raw in {"observe_only", "partial", "stale", "delayed"}:
            return "degraded"
    return "missing"


def _domain_reason_codes(
    packet_domain: Mapping[str, Any],
    fundamental_domain: Mapping[str, Any],
    coverage_domain: Mapping[str, Any],
    news_domain_summary: Mapping[str, Any],
    status: str,
) -> list[str]:
    reasons: list[str] = []
    for key in ("missingReasons", "reasonCodes"):
        for source in (packet_domain, fundamental_domain, coverage_domain, news_domain_summary):
            for item in _sequence(source.get(key)):
                text = _sanitize_reason_code(item)
                if text:
                    _append_unique(reasons, text)
    if not reasons:
        default_reason = _STATUS_REASON_DEFAULTS.get(status)
        if default_reason:
            reasons.append(default_reason)
    return reasons


def _collect_domain_notes(
    domain_summaries: Sequence[Mapping[str, Any]],
    *,
    statuses: set[str],
) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for summary in domain_summaries:
        if str(summary.get("status")) not in statuses:
            continue
        summary_notes = _sequence(summary.get("notes"))
        reason_code = _reason_code_from_message(summary_notes[0] if summary_notes else "") or _STATUS_REASON_DEFAULTS.get(
            str(summary.get("status")),
            "manual_unknown",
        )
        notes.append(
            {
                "domain": _safe_domain(summary.get("domain")),
                "reasonCode": reason_code,
                "note": _sanitize_text(summary_notes[0] if summary_notes else _reason_note(reason_code), limit=120),
            }
        )
    return notes


def _collect_authority_notes(domain_summaries: Sequence[Mapping[str, Any]]) -> list[str]:
    notes: list[str] = []
    for summary in domain_summaries:
        authority_label = str(summary.get("authorityLabel") or "")
        domain = _safe_domain(summary.get("domain"))
        if authority_label == "observationOnly":
            _append_unique(notes, f"{domain}: 当前仅可作为观察说明证据。")
        elif authority_label == "unavailable":
            _append_unique(notes, f"{domain}: 当前没有可确认的来源权威性。")
    return notes[:6]


def _collect_freshness_notes(domain_summaries: Sequence[Mapping[str, Any]]) -> list[str]:
    notes: list[str] = []
    for summary in domain_summaries:
        freshness_label = str(summary.get("freshnessLabel") or "")
        domain = _safe_domain(summary.get("domain"))
        if freshness_label == "stale":
            _append_unique(notes, f"{domain}: 当前证据已陈旧，不能强化最新结论。")
        elif freshness_label == "delayed":
            _append_unique(notes, f"{domain}: 当前证据存在延迟，只能保守引用。")
        elif freshness_label in {"unknown", "unavailable"}:
            _append_unique(notes, f"{domain}: 当前证据新鲜度无法确认。")
    return notes[:6]


def _input_state(
    *,
    packet: Mapping[str, Any],
    fundamentals: Mapping[str, Any],
    news: Mapping[str, Any],
    readiness: Mapping[str, Any],
    domain_summaries: Sequence[Mapping[str, Any]],
) -> str:
    statuses = {str(item.get("status") or "") for item in domain_summaries}
    if "blocked" in statuses or str(news.get("extractionState") or "") == "blocked":
        return "blocked"
    if "pending" in statuses or str(packet.get("packetState") or "") == "waiting":
        return "waiting"
    readiness_state = str(readiness.get("readinessState") or "").strip().lower()
    if readiness_state == "blocked":
        return "blocked"
    if readiness_state == "waiting":
        return "waiting"
    if readiness_state == "insufficient" or str(fundamentals.get("normalizerState") or "") == "insufficient":
        return "insufficient"
    if "missing" in statuses:
        return "insufficient"
    if readiness_state == "observe_only":
        return "observe_only"
    if any(status == "degraded" for status in statuses):
        return "observe_only"
    if str(packet.get("packetState") or "") == "degraded":
        return "observe_only"
    return "ready"


def _no_advice_boundary(
    packet: Mapping[str, Any],
    fundamentals: Mapping[str, Any],
    news: Mapping[str, Any],
) -> list[str]:
    states = [
        _mapping(packet.get("noAdviceBoundary")).get("state"),
        _mapping(fundamentals.get("noAdviceBoundary")).get("state"),
        _mapping(news.get("noAdviceBoundary")).get("state"),
    ]
    state = "ready" if any(str(item).strip().lower() == "ready" for item in states) else "blocked"
    notes = [
        "仅供研究说明，不构成投资建议。",
        "缺失、降级或阻塞证据必须显式保留，不得补写为已支持结论。",
        "禁止输出买入、卖出、下单、交易或经纪商执行语言。",
    ]
    if state != "ready":
        notes.append("noAdviceBoundary 未完整确认，按禁止判断处理。")
    return notes


def _authority_label(
    packet_domain: Mapping[str, Any],
    fundamental_domain: Mapping[str, Any],
    coverage_domain: Mapping[str, Any],
    news_domain_summary: Mapping[str, Any],
) -> str:
    candidates = (
        packet_domain.get("providerAuthority"),
        coverage_domain.get("sourceAuthority"),
        fundamental_domain.get("bestAuthorityTier"),
        news_domain_summary.get("bestAuthorityTier"),
    )
    for raw in candidates:
        text = _sanitize_text(raw, limit=32)
        if not text:
            continue
        normalized = _AUTHORITY_LABELS.get(text, _AUTHORITY_LABELS.get(text.lower()))
        if normalized:
            return normalized
    return "unavailable"


def _freshness_label(
    packet_domain: Mapping[str, Any],
    fundamental_domain: Mapping[str, Any],
    coverage_domain: Mapping[str, Any],
    news_domain_summary: Mapping[str, Any],
) -> str:
    candidates = (
        packet_domain.get("freshness"),
        coverage_domain.get("freshness"),
        fundamental_domain.get("freshness"),
        news_domain_summary.get("freshnessClass"),
    )
    for raw in candidates:
        text = _sanitize_text(raw, limit=24)
        if not text:
            continue
        normalized = _FRESHNESS_LABELS.get(text, _FRESHNESS_LABELS.get(text.lower()))
        if normalized:
            return normalized
    return "unknown"


def _summarize_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return _sanitize_text(str(value), limit=80)
    if isinstance(value, str):
        return _sanitize_text(value, limit=120)
    if isinstance(value, Mapping):
        parts: list[str] = []
        for key, item in list(value.items())[:3]:
            key_text = _sanitize_text(key, limit=24)
            value_text = _sanitize_text(item, limit=40)
            if key_text and value_text:
                parts.append(f"{key_text}={value_text}")
        return _truncate(", ".join(parts), 120)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        parts = [_sanitize_text(item, limit=32) for item in list(value)[:3]]
        parts = [item for item in parts if item]
        return _truncate(", ".join(parts), 120)
    return ""


def _primary_limitation(value: Any) -> str | None:
    for item in _sequence(value):
        text = _sanitize_text(item, limit=96)
        if text:
            return text
    return None


def _evidence_ids_by_domain(value: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for item in value:
        domain = _safe_domain(item.get("domain"))
        grouped.setdefault(domain, [])
        evidence_id = _safe_id(item.get("id"), fallback=domain)
        if evidence_id not in grouped[domain]:
            grouped[domain].append(evidence_id)
    return grouped


def _reason_note(reason_code: str) -> str:
    return _REASON_LABELS.get(reason_code, "当前证据受限，必须保持保守表述。")


def _reason_code_from_message(value: str) -> str | None:
    for reason_code, note in _REASON_LABELS.items():
        if value == note:
            return reason_code
    return None


def _sanitize_reason_code(value: Any) -> str | None:
    text = _sanitize_text(value, limit=48).lower()
    if not text:
        return None
    return text.replace(" ", "_")


def _safe_domain(value: Any) -> str:
    text = _sanitize_text(value, limit=40)
    if text in _DOMAIN_ORDER or text in _EVIDENCE_DOMAIN_ORDER:
        return text
    return "unknown"


def _safe_symbol(value: Any) -> str:
    text = _sanitize_text(value, limit=24)
    return text.upper() if text else "UNKNOWN"


def _safe_market(value: Any) -> str:
    text = _sanitize_text(value, limit=12).lower()
    return text if text in {"us", "hk", "cn"} else "unknown"


def _safe_id(value: Any, *, fallback: str) -> str:
    text = _sanitize_text(value, limit=48)
    if text:
        return text
    return _sanitize_text(fallback, limit=48) or "unknown-id"


def _safe_source_id(value: Any) -> str:
    text = _sanitize_text(value, limit=32)
    return text or "manual_unknown"


def _safe_provider_authority(value: Any) -> str:
    text = _sanitize_text(value, limit=24)
    return text if text in {"scoreGradeAllowed", "observationOnly"} else "observationOnly"


def _safe_freshness(value: Any) -> str:
    text = _sanitize_text(value, limit=24).lower()
    return _FRESHNESS_LABELS.get(text, "unknown")


def _safe_timestamp(value: Any) -> str | None:
    text = _sanitize_text(value, limit=32)
    return text or None


def _sanitize_text(value: Any, *, limit: int = 160) -> str:
    if value is None:
        return ""
    if isinstance(value, Mapping):
        try:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except TypeError:
            text = str(value)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        try:
            text = json.dumps(list(value), ensure_ascii=False)
        except TypeError:
            text = str(value)
    else:
        text = str(value)
    text = " ".join(text.strip().split())
    lowered = text.lower()
    if not text or any(marker in lowered for marker in _FORBIDDEN_TEXT_MARKERS):
        return ""
    return _truncate(text, limit)


def _truncate(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _append_unique(target: list[str], value: str) -> None:
    if value and value not in target:
        target.append(value)


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
