# -*- coding: utf-8 -*-
"""Pure additive helper for Home report evidence citation frames."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.services.home_llm_evidence_input import build_home_llm_evidence_input_v1


HOME_REPORT_EVIDENCE_CITATION_FRAME_VERSION = "home_report_evidence_citation_frame_v1"

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
_CITATION_DOMAINS = frozenset(
    {
        "fundamentals",
        "earnings",
        "valuation",
        "news",
        "catalysts",
        "sentiment",
    }
)
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


def build_home_report_evidence_citation_frame_v1(
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Project existing Home evidence contracts into a report-safe citation frame."""

    payload = _mapping(value)
    packet = _mapping(payload.get("singleStockEvidencePacket"))
    fundamentals = _mapping(payload.get("fundamentalsEarnings"))
    news = _mapping(payload.get("newsCatalysts"))
    readiness = _mapping(payload.get("researchReadiness"))
    coverage = _mapping(payload.get("evidenceCoverageFrame"))
    adapter = _mapping(payload.get("homeLlmEvidenceInput"))
    if not adapter:
        adapter = build_home_llm_evidence_input_v1(
            {
                "singleStockEvidencePacket": packet,
                "fundamentalsEarnings": fundamentals,
                "newsCatalysts": news,
                "researchReadiness": readiness,
                "evidenceCoverageFrame": coverage,
                "debugRef": _first_present(
                    payload.get("debugRef"),
                    packet.get("debugRef"),
                    fundamentals.get("debugRef"),
                    news.get("debugRef"),
                ),
            }
        )

    domain_coverage = _build_domain_coverage(adapter.get("domainSummaries"))
    frame_state = _frame_state(domain_coverage)
    missing_evidence = _missing_domains(adapter.get("missingEvidence"), domain_coverage)
    blocking_reasons = _blocking_reasons(
        adapter=adapter,
        packet=packet,
        fundamentals=fundamentals,
        news=news,
        readiness=readiness,
        coverage=coverage,
        frame_state=frame_state,
    )
    next_evidence_needed = _next_evidence_needed(
        packet=packet,
        fundamentals=fundamentals,
        news=news,
        domain_coverage=domain_coverage,
    )
    cited_evidence = _cited_evidence(
        adapter=adapter,
        domain_coverage=domain_coverage,
        frame_state=frame_state,
    )

    return {
        "contractVersion": HOME_REPORT_EVIDENCE_CITATION_FRAME_VERSION,
        "frameState": frame_state,
        "symbol": _safe_symbol(_first_present(adapter.get("symbol"), packet.get("symbol"))),
        "market": _safe_market(_first_present(adapter.get("market"), packet.get("market"))),
        "citedEvidence": cited_evidence,
        "domainCoverage": domain_coverage,
        "missingEvidence": missing_evidence,
        "blockingReasons": blocking_reasons,
        "nextEvidenceNeeded": next_evidence_needed,
        "noAdviceBoundary": _no_advice_boundary(
            packet=packet,
            fundamentals=fundamentals,
            news=news,
            adapter=adapter,
        ),
        "debugRef": _sanitize_text(
            _first_present(
                payload.get("debugRef"),
                adapter.get("debugRef"),
                packet.get("debugRef"),
                fundamentals.get("debugRef"),
                news.get("debugRef"),
            ),
            limit=80,
        )
        or "redacted",
    }


def _build_domain_coverage(value: Any) -> list[dict[str, Any]]:
    summaries = _sequence(value)
    by_domain = {
        _safe_domain(_mapping(item).get("domain")): _mapping(item)
        for item in summaries
        if _safe_domain(_mapping(item).get("domain")) != "unknown"
    }
    coverage: list[dict[str, Any]] = []
    for domain in _DOMAIN_ORDER:
        summary = by_domain.get(domain)
        if not summary:
            continue
        coverage.append(
            {
                "domain": domain,
                "status": _safe_status(summary.get("status")),
                "authorityLabel": _safe_label(summary.get("authorityLabel"), limit=24),
                "freshnessLabel": _safe_label(summary.get("freshnessLabel"), limit=24),
                "evidenceRefIds": _safe_ids(summary.get("evidenceRefIds"), limit=3),
                "notes": _safe_notes(summary.get("notes"), limit=3),
            }
        )
    return coverage


def _frame_state(domain_coverage: Sequence[Mapping[str, Any]]) -> str:
    core_statuses = [
        str(item.get("status") or "")
        for item in domain_coverage
        if _safe_domain(item.get("domain")) in _CITATION_DOMAINS
    ]
    if any(status in {"missing", "blocked", "pending"} for status in core_statuses):
        return "blocked"
    if any(status == "degraded" for status in core_statuses):
        return "observe_only"
    return "ready"


def _missing_domains(
    missing_notes: Any,
    domain_coverage: Sequence[Mapping[str, Any]],
) -> list[str]:
    domains: list[str] = []
    for item in _sequence(missing_notes):
        domain = _safe_domain(_mapping(item).get("domain"))
        if domain in _CITATION_DOMAINS and domain not in domains:
            domains.append(domain)
    for item in domain_coverage:
        domain = _safe_domain(item.get("domain"))
        if domain not in _CITATION_DOMAINS:
            continue
        if str(item.get("status") or "") in {"missing", "blocked", "pending"}:
            if domain not in domains:
                domains.append(domain)
    return domains


def _blocking_reasons(
    *,
    adapter: Mapping[str, Any],
    packet: Mapping[str, Any],
    fundamentals: Mapping[str, Any],
    news: Mapping[str, Any],
    readiness: Mapping[str, Any],
    coverage: Mapping[str, Any],
    frame_state: str,
) -> list[str]:
    if frame_state == "ready":
        return []
    reasons: list[str] = []
    for item in _sequence(adapter.get("blockedEvidence")):
        reason = _safe_reason(_mapping(item).get("reasonCode"))
        if reason:
            _append_unique(reasons, reason)
    if frame_state == "blocked":
        for item in _sequence(adapter.get("missingEvidence")):
            reason = _safe_reason(_mapping(item).get("reasonCode"))
            if reason:
                _append_unique(reasons, reason)
        for item in _sequence(adapter.get("degradedEvidence")):
            reason = _safe_reason(_mapping(item).get("reasonCode"))
            if reason:
                _append_unique(reasons, reason)
    for source in (
        packet.get("blockingReasons"),
        fundamentals.get("blockingReasons"),
        news.get("blockingReasons"),
        readiness.get("blockingReasons"),
    ):
        for item in _sequence(source):
            reason = _safe_reason(item)
            if reason:
                _append_unique(reasons, reason)
    for item in coverage.values() if isinstance(coverage, Mapping) else ():
        for reason in _sequence(_mapping(item).get("missingReasons")):
            safe_reason = _safe_reason(reason)
            if safe_reason:
                _append_unique(reasons, safe_reason)
    return reasons


def _next_evidence_needed(
    *,
    packet: Mapping[str, Any],
    fundamentals: Mapping[str, Any],
    news: Mapping[str, Any],
    domain_coverage: Sequence[Mapping[str, Any]],
) -> list[str]:
    items: list[str] = []
    for source in (
        packet.get("nextEvidenceNeeded"),
        fundamentals.get("nextEvidenceNeeded"),
        news.get("nextEvidenceNeeded"),
    ):
        for item in _sequence(source):
            text = _sanitize_text(item, limit=48)
            if text:
                _append_unique(items, text)
    if items:
        return items
    for item in domain_coverage:
        domain = _safe_domain(item.get("domain"))
        if domain not in _CITATION_DOMAINS:
            continue
        if str(item.get("status") or "") in {"missing", "blocked", "degraded"}:
            label = _fallback_next_evidence_label(domain)
            if label:
                _append_unique(items, label)
    return items


def _cited_evidence(
    *,
    adapter: Mapping[str, Any],
    domain_coverage: Sequence[Mapping[str, Any]],
    frame_state: str,
) -> list[dict[str, Any]]:
    if frame_state not in {"ready", "observe_only"}:
        return []
    domain_status = {
        _safe_domain(item.get("domain")): str(item.get("status") or "")
        for item in domain_coverage
    }
    citations: list[dict[str, Any]] = []
    for item in _sequence(adapter.get("evidenceIndex")):
        entry = _mapping(item)
        domain = _safe_domain(entry.get("domain"))
        if domain_status.get(domain) not in {"available", "degraded"}:
            continue
        label = _sanitize_text(entry.get("label"), limit=72)
        summary = _sanitize_text(entry.get("summary"), limit=160)
        evidence_id = _sanitize_text(entry.get("id"), limit=48)
        if not (label and summary and evidence_id):
            continue
        citations.append(
            {
                "id": evidence_id,
                "domain": domain,
                "label": label,
                "summary": summary,
                "sourceId": _sanitize_text(entry.get("sourceId"), limit=32) or "manual_unknown",
                "providerAuthority": _safe_label(entry.get("providerAuthority"), limit=24) or "observationOnly",
                "freshness": _safe_label(entry.get("freshness"), limit=24) or "unknown",
                "asOf": _sanitize_text(entry.get("asOf"), limit=32) or None,
                "limitation": _sanitize_text(entry.get("limitation"), limit=96) or None,
            }
        )
    return citations


def _no_advice_boundary(
    *,
    packet: Mapping[str, Any],
    fundamentals: Mapping[str, Any],
    news: Mapping[str, Any],
    adapter: Mapping[str, Any],
) -> bool:
    if _sequence(adapter.get("noAdviceBoundary")):
        return True
    for source in (
        packet.get("noAdviceBoundary"),
        fundamentals.get("noAdviceBoundary"),
        news.get("noAdviceBoundary"),
    ):
        state = str(_mapping(source).get("state") or "").strip().lower()
        if state == "ready":
            return True
    return False


def _fallback_next_evidence_label(domain: str) -> str:
    mapping = {
        "priceHistory": "补充价格历史证据",
        "technicals": "补充技术面证据",
        "fundamentals": "补充基本面证据",
        "earnings": "补充财报证据",
        "filings": "补充披露文件证据",
        "news": "补充新闻证据",
        "catalysts": "补充催化剂证据",
        "sentiment": "补充情绪证据",
        "valuation": "补充估值证据",
        "sectorTheme": "补充行业主题证据",
        "macroLiquidity": "补充宏观流动性证据",
    }
    return mapping.get(domain, "")


def _safe_symbol(value: Any) -> str:
    text = _sanitize_text(value, limit=24)
    return text.upper() if text else "UNKNOWN"


def _safe_market(value: Any) -> str:
    text = _sanitize_text(value, limit=12).lower()
    return text if text in {"us", "hk", "cn"} else "unknown"


def _safe_domain(value: Any) -> str:
    text = _sanitize_text(value, limit=40)
    return text if text in _DOMAIN_ORDER else "unknown"


def _safe_status(value: Any) -> str:
    text = str(_sanitize_text(value, limit=24) or "").lower()
    if text in {"available", "degraded", "missing", "blocked", "pending"}:
        return text
    if text in {"ok", "ready"}:
        return "available"
    if text in {"partial", "stale", "delayed", "observe_only"}:
        return "degraded"
    return "missing"


def _safe_reason(value: Any) -> str:
    text = _sanitize_text(value, limit=48).lower()
    return text.replace(" ", "_") if text else ""


def _safe_label(value: Any, *, limit: int) -> str:
    return _sanitize_text(value, limit=limit)


def _safe_ids(value: Any, *, limit: int) -> list[str]:
    items: list[str] = []
    for item in _sequence(value)[:limit]:
        text = _sanitize_text(item, limit=48)
        if text:
            items.append(text)
    return items


def _safe_notes(value: Any, *, limit: int) -> list[str]:
    items: list[str] = []
    for item in _sequence(value)[:limit]:
        text = _sanitize_text(item, limit=120)
        if text:
            items.append(text)
    return items


def _sanitize_text(value: Any, *, limit: int = 160) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).strip().split())
    lowered = text.lower()
    if not text or any(marker in lowered for marker in _FORBIDDEN_TEXT_MARKERS):
        return ""
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
