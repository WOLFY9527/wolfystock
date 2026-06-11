# -*- coding: utf-8 -*-
"""Pure Intelligence Report Engine v2 packet composer.

This helper normalizes evidence/readiness/provenance metadata that callers
already built. It does not call providers, read runtime config, route models, or
promote observation-only evidence into score-grade conclusions.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping


INTELLIGENCE_REPORT_PACKET_VERSION = "intelligence_report_packet_v2"

_UNSAFE_TEXT_REPLACEMENTS = (
    (re.compile(r"\bstop[\s-]?loss\b", re.IGNORECASE), "risk boundary"),
    (re.compile(r"\btarget\s+price\b", re.IGNORECASE), "upper observation zone"),
    (re.compile(r"\bposition\s+sizing\b", re.IGNORECASE), "exposure reference"),
    (re.compile(r"\border\b", re.IGNORECASE), "request"),
    (re.compile(r"\btrade\b", re.IGNORECASE), "market action"),
    (re.compile(r"\bbuy(?:ing)?\b", re.IGNORECASE), "positive assessment"),
    (re.compile(r"\bsell(?:ing)?\b", re.IGNORECASE), "negative assessment"),
    (re.compile(r"止损"), "风险边界"),
    (re.compile(r"目标价"), "上方观察区"),
    (re.compile(r"仓位建议"), "风险暴露参考"),
    (re.compile(r"交易建议"), "研究观察"),
    (re.compile(r"投资建议"), "研究参考"),
    (re.compile(r"下单"), "提交请求"),
    (re.compile(r"买入"), "正向评估"),
    (re.compile(r"卖出"), "负向评估"),
)
_UNSAFE_TEXT_PATTERNS = tuple(pattern for pattern, _replacement in _UNSAFE_TEXT_REPLACEMENTS)

_DEGRADED_FRESHNESS = {"stale", "fallback", "synthetic", "unavailable", "unknown"}
_SOURCE_AUTHORITY_SCORE_GRADE = {"scoregradeallowed", "score_grade", "scoregrade", "trusted_public"}
_COUNTER_DOMAINS = ("valuation", "risk", "macro", "sentiment", "news")
_SAFE_DOMAIN_LABELS = {
    "pricehistory": "priceHistory",
    "price_history": "priceHistory",
    "market_data": "marketData",
    "technical": "technicals",
    "technicals": "technicals",
    "fundamental": "fundamentals",
    "fundamentals": "fundamentals",
    "earnings": "earnings",
    "filings": "filings",
    "news": "news",
    "catalyst": "catalysts",
    "catalysts": "catalysts",
    "sentiment": "sentiment",
    "valuation": "valuation",
    "risk": "risk",
    "macro": "macro",
    "sector_theme": "sectorTheme",
    "sectortheme": "sectorTheme",
    "macro_liquidity": "macroLiquidity",
    "macroliquidity": "macroLiquidity",
    "liquidity_context": "liquidityContext",
    "liquiditycontext": "liquidityContext",
    "general": "general",
}
_INTERNAL_TEXT_REPLACEMENTS = (
    (re.compile(r"\bdebug[_\s-]?ref\b\s*[:=]?\s*[\w:./-]*", re.IGNORECASE), "reference label"),
    (re.compile(r"\braw[_\s-]?prompt\b\s*[:=]?\s*[\w:./-]*", re.IGNORECASE), "input text"),
    (re.compile(r"\bprompt\s*:\s*[^.;\n]+", re.IGNORECASE), "input text"),
    (re.compile(r"\bprovider[_\s-]?payload(?:[_\s-]?ref)?\b\s*[:=]?\s*[\w:./-]*", re.IGNORECASE), "internal reference"),
    (re.compile(r"\bpayload[-_:][A-Za-z0-9_.:-]+", re.IGNORECASE), "internal reference"),
    (re.compile(r"\btraceback\b(?:\s*\([^)]*\))?", re.IGNORECASE), "diagnostic trace"),
    (re.compile(r"\bstack\s+trace\b", re.IGNORECASE), "diagnostic trace"),
    (re.compile(r"\bmost recent call last\b", re.IGNORECASE), "diagnostic trace"),
    (re.compile(r"\binternal[_\s-]?diagnostic(?:[_\s-]?token)?\b\s*[:=]?\s*[\w:./-]*", re.IGNORECASE), "internal note"),
    (re.compile(r"\bdiag[-_][A-Za-z0-9_.:-]+", re.IGNORECASE), "internal note"),
    (re.compile(r"\bquery[-_][A-Za-z0-9_.:-]+", re.IGNORECASE), "request reference"),
    (re.compile(r"\bsourceid\b\s*[:=]?\s*[\w:./-]*", re.IGNORECASE), "source label"),
    (re.compile(r"\b[A-Za-z]+-source-\d+[A-Za-z0-9_.:-]*\b", re.IGNORECASE), "source label"),
    (re.compile(r"\b(?:authorization|bearer)\b\s*[:=]?\s*[\w:./-]*", re.IGNORECASE), "credential marker"),
    (re.compile(r"\btoken\s*=\s*[\w:./-]+", re.IGNORECASE), "credential marker"),
    (re.compile(r"\bsecret[-_][A-Za-z0-9_.:-]+\b", re.IGNORECASE), "credential marker"),
)


def build_intelligence_report_packet_v2(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a consumer-safe structured research packet from existing evidence."""

    payload = dict(value or {})
    standard_report = _mapping(_get(payload, "standardReport", "standard_report"))
    readiness = _mapping(_get(payload, "researchReadiness", "research_readiness"))
    data_quality = _mapping(_get(payload, "dataQualityReport", "data_quality_report"))
    citation_frame = _mapping(_get(payload, "evidenceCitationFrame", "evidence_citation_frame"))
    source_frame = _list_of_mappings(_get(payload, "sourceProvenanceFrame", "source_provenance_frame"))

    unsafe_text_detected = _contains_unsafe_text(
        _get(payload, "thesis"),
        _nested_get(standard_report, "summaryPanel", "oneSentence"),
        _nested_get(standard_report, "summary_panel", "one_sentence"),
        _nested_get(standard_report, "decisionPanel", "keyAction"),
        _nested_get(standard_report, "decision_panel", "key_action"),
    )

    thesis = _build_thesis(payload, standard_report, unsafe_text_detected=unsafe_text_detected)
    missing_data = _string_list(
        _get(readiness, "missingEvidence", "missing_evidence")
        or _get(data_quality, "missingDomains", "missingRequiredDomains", "missing_domains")
    )
    source_authority = _build_source_authority(readiness, source_frame)
    freshness = _build_freshness(readiness, data_quality, source_frame)
    confidence = _build_confidence(
        readiness=readiness,
        data_quality=data_quality,
        source_authority=source_authority,
        freshness=freshness,
        missing_data=missing_data,
        unsafe_text_detected=unsafe_text_detected,
    )
    packet_state = _packet_state(readiness, confidence)

    packet = {
        "contractVersion": INTELLIGENCE_REPORT_PACKET_VERSION,
        "packetState": packet_state,
        "consumerActionBoundary": _consumer_boundary(readiness),
        "noAdviceBoundary": _get(payload, "noAdviceBoundary", "no_advice_boundary") is not False,
        "thesis": thesis,
        "evidence": _build_evidence_items(citation_frame, source_frame),
        "counterEvidence": _build_counter_evidence(standard_report, citation_frame, source_frame),
        "missingData": missing_data,
        "confidence": confidence,
        "sourceAuthority": source_authority,
        "freshness": freshness,
        "scenarioRisks": _build_scenario_risks(standard_report),
        "nextVerificationSteps": _next_verification_steps(readiness, missing_data),
    }
    return packet


def _build_thesis(
    payload: Mapping[str, Any],
    standard_report: Mapping[str, Any],
    *,
    unsafe_text_detected: bool,
) -> dict[str, Any]:
    raw_thesis = _get(payload, "thesis")
    thesis_text = _get(raw_thesis, "summary") if isinstance(raw_thesis, Mapping) else raw_thesis
    if thesis_text is None:
        thesis_text = (
            _nested_get(standard_report, "summaryPanel", "oneSentence")
            or _nested_get(standard_report, "summary_panel", "one_sentence")
            or _nested_get(standard_report, "reasonLayer", "latestKeyUpdate")
            or _nested_get(standard_report, "reason_layer", "latest_key_update")
        )
    confidence_label = _get(raw_thesis, "confidenceLabel", "confidence_label") if isinstance(raw_thesis, Mapping) else None
    if confidence_label is None:
        confidence_label = (
            _nested_get(standard_report, "decisionPanel", "confidence")
            or _nested_get(standard_report, "decision_panel", "confidence")
        )
    return {
        "summary": _consumer_text(thesis_text, "Evidence packet remains incomplete; continue observation only."),
        "confidenceLabel": _consumer_text(confidence_label, "Capped" if unsafe_text_detected else "Evidence-backed"),
    }


def _build_evidence_items(
    citation_frame: Mapping[str, Any],
    source_frame: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    cited = _list_of_mappings(_get(citation_frame, "citedEvidence", "cited_evidence"))
    items: list[dict[str, Any]] = []
    for index, item in enumerate(cited):
        domain = _safe_domain(_get(item, "domain"), default="general")
        source = _source_for_domain(domain, source_frame)
        items.append(
            {
                "id": f"evidence-{index + 1}",
                "domain": domain,
                "summary": _consumer_text(
                    _get(item, "summary", "label"),
                    f"{domain} evidence referenced.",
                ),
                "sourceId": _source_public_label(source, fallback_index=index + 1, domain=domain),
                "authority": _text(_get(source, "authorityTier", "authority_tier"), default="unknown"),
                "freshness": _text(_get(source, "freshnessState", "freshness_state"), default="unknown"),
            }
        )
    return items


def _build_counter_evidence(
    standard_report: Mapping[str, Any],
    citation_frame: Mapping[str, Any],
    source_frame: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, text in enumerate(_risk_texts(standard_report)):
        items.append(
            {
                "id": f"counter-{index + 1}",
                "domain": "risk",
                "summary": _consumer_text(text, "Risk context requires continued verification."),
                "authority": "observation_only",
                "freshness": _freshness_from_sources(source_frame),
            }
        )
    if items:
        return items[:6]

    coverage = _list_of_mappings(_get(citation_frame, "domainCoverage", "domain_coverage"))
    for item in coverage:
        domain = _safe_domain(_get(item, "domain"), default="")
        status = _text(_get(item, "status"), default="").lower()
        if domain in _COUNTER_DOMAINS or status in {"observe_only", "blocked", "missing"}:
            items.append(
                {
                    "id": f"counter-{len(items) + 1}",
                    "domain": domain or "risk",
                    "summary": _consumer_text(_get(item, "summary", "status"), "Counter-evidence requires review."),
                    "authority": "observation_only",
                    "freshness": _freshness_from_sources(source_frame),
                }
            )
    return items[:6]


def _build_scenario_risks(standard_report: Mapping[str, Any]) -> list[str]:
    return [_consumer_text(item, "Risk context requires continued verification.") for item in _risk_texts(standard_report)][:6]


def _risk_texts(standard_report: Mapping[str, Any]) -> list[Any]:
    reason_layer = _mapping(_get(standard_report, "reasonLayer", "reason_layer"))
    highlights = _mapping(_get(standard_report, "highlights"))
    values: list[Any] = []
    values.append(_get(reason_layer, "topRisk", "top_risk"))
    values.extend(_iterable(_get(highlights, "riskAlerts", "risk_alerts")))
    values.extend(_iterable(_get(highlights, "bearishFactors", "bearish_factors")))
    return _dedupe_text(values)


def _build_source_authority(
    readiness: Mapping[str, Any],
    source_frame: list[Mapping[str, Any]],
) -> dict[str, Any]:
    coverage = _mapping(_get(readiness, "evidenceCoverage", "evidence_coverage"))
    score_grade_count = _int(_get(coverage, "scoreGradeCount", "score_grade_count"))
    observation_only_count = _int(_get(coverage, "observationOnlyCount", "observation_only_count"))
    missing_count = _int(_get(coverage, "missingCount", "missing_count"))
    if not coverage and source_frame:
        score_grade_count = sum(1 for item in source_frame if _bool(_get(item, "scoreContributionAllowed", "score_contribution_allowed")))
        observation_only_count = sum(1 for item in source_frame if _bool(_get(item, "observationOnly", "observation_only")))
    state = _text(_get(readiness, "sourceAuthority", "source_authority"), default="unavailable")
    return {
        "state": state,
        "scoreGradeCount": score_grade_count,
        "observationOnlyCount": observation_only_count,
        "missingCount": missing_count,
        "sourceCount": len(source_frame),
    }


def _build_freshness(
    readiness: Mapping[str, Any],
    data_quality: Mapping[str, Any],
    source_frame: list[Mapping[str, Any]],
) -> dict[str, Any]:
    floor = _text(_get(readiness, "freshnessFloor", "freshness_floor"), default="")
    if not floor:
        floor = _freshness_from_sources(source_frame)
    stale_sources = _public_source_labels_from_values(_get(data_quality, "staleSources", "stale_sources"))
    fallback_sources = [
        _source_public_label(item, fallback_index=index + 1)
        for index, item in enumerate(source_frame)
        if _bool(_get(item, "fallbackOrProxy", "fallback_or_proxy"))
    ]
    return {
        "floor": floor or "unknown",
        "staleSources": stale_sources,
        "fallbackOrProxySources": list(dict.fromkeys(fallback_sources)),
    }


def _build_confidence(
    *,
    readiness: Mapping[str, Any],
    data_quality: Mapping[str, Any],
    source_authority: Mapping[str, Any],
    freshness: Mapping[str, Any],
    missing_data: list[str],
    unsafe_text_detected: bool,
) -> dict[str, Any]:
    cap = _bounded_float(
        _get(data_quality, "confidenceCap", "confidence_cap", "scoreCap", "score_cap")
        or _get(readiness, "confidenceCap", "confidence_cap"),
        default=1.0,
    )
    capped_by = _string_list(_get(readiness, "blockingReasons", "blocking_reasons"))
    authority_state = _normalize_key(_get(source_authority, "state"))
    freshness_floor = _normalize_key(_get(freshness, "floor"))

    if authority_state not in _SOURCE_AUTHORITY_SCORE_GRADE:
        cap = min(cap, 0.4)
        _append_unique(capped_by, "source_authority_not_score_grade")
    if missing_data:
        cap = min(cap, 0.6)
        _append_unique(capped_by, "missing_required_evidence")
    if freshness_floor in _DEGRADED_FRESHNESS:
        cap = min(cap, 0.6)
        _append_unique(capped_by, f"{freshness_floor}_freshness")
    if unsafe_text_detected:
        cap = min(cap, 0.4)
        _append_unique(capped_by, "unsafe_conclusion_text_sanitized")

    readiness_state = _normalize_key(_get(readiness, "readinessState", "readiness_state"))
    high_confidence_allowed = bool(
        cap >= 0.8
        and readiness_state == "ready"
        and authority_state in _SOURCE_AUTHORITY_SCORE_GRADE
        and not missing_data
        and not unsafe_text_detected
    )
    return {
        "cap": round(cap, 4),
        "label": "High-confidence allowed" if high_confidence_allowed else "Confidence capped",
        "highConfidenceAllowed": high_confidence_allowed,
        "cappedBy": capped_by,
    }


def _packet_state(readiness: Mapping[str, Any], confidence: Mapping[str, Any]) -> str:
    state = _normalize_key(_get(readiness, "readinessState", "readiness_state"))
    if state in {"ready", "observe_only", "insufficient", "blocked", "waiting"}:
        return state
    return "ready" if _bool(_get(confidence, "highConfidenceAllowed")) else "insufficient"


def _consumer_boundary(readiness: Mapping[str, Any]) -> str:
    boundary = _text(_get(readiness, "consumerActionBoundary", "consumer_action_boundary"), default="no_advice")
    return boundary or "no_advice"


def _next_verification_steps(readiness: Mapping[str, Any], missing_data: list[str]) -> list[str]:
    explicit = _string_list(_get(readiness, "nextEvidenceNeeded", "next_evidence_needed"))
    if explicit:
        return explicit[:8]
    return [f"补充{item}证据" for item in missing_data[:8]]


def _source_for_domain(domain: str, source_frame: list[Mapping[str, Any]]) -> Mapping[str, Any]:
    normalized = _normalize_key(domain)
    aliases = {
        normalized,
        "market_data" if normalized in {"technical", "technicals", "pricehistory", "price_history"} else normalized,
    }
    for item in source_frame:
        item_domain = _normalize_key(_get(item, "evidenceDomain", "evidence_domain"))
        if item_domain in aliases:
            return item
    return source_frame[0] if source_frame else {}


def _freshness_from_sources(source_frame: list[Mapping[str, Any]]) -> str:
    values = [_normalize_key(_get(item, "freshnessState", "freshness_state")) for item in source_frame]
    if any(value in {"synthetic", "fixture"} for value in values):
        return "synthetic"
    if any(value == "fallback" for value in values):
        return "fallback"
    if any(value == "stale" for value in values):
        return "stale"
    if any(value == "delayed" for value in values):
        return "delayed"
    if any(value in {"fresh", "cached"} for value in values):
        return "fresh"
    return "unknown"


def _contains_unsafe_text(*values: Any) -> bool:
    combined = " ".join(str(value or "") for value in values)
    return any(pattern.search(combined) for pattern in _UNSAFE_TEXT_PATTERNS)


def _consumer_text(value: Any, fallback: str) -> str:
    text = " ".join(str(value or "").split())
    if not text or text.lower() in {"none", "null", "nan", "n/a", "na", "-"}:
        text = fallback
    for pattern, replacement in _INTERNAL_TEXT_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    for pattern, replacement in _UNSAFE_TEXT_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text[:420]


def _safe_domain(value: Any, *, default: str) -> str:
    normalized = _normalize_key(value)
    if not normalized:
        return default
    return _SAFE_DOMAIN_LABELS.get(normalized, default)


def _source_public_label(
    source: Mapping[str, Any],
    *,
    fallback_index: int,
    domain: str | None = None,
) -> str:
    label_domain = domain or _safe_domain(_get(source, "evidenceDomain", "evidence_domain"), default="")
    if label_domain:
        return f"source-{_normalize_key(label_domain) or fallback_index}"
    return f"source-{fallback_index}"


def _public_source_labels_from_values(value: Any) -> list[str]:
    labels: list[str] = []
    for index, item in enumerate(_iterable(value), start=1):
        domain = _safe_domain(item, default="")
        label = f"source-{_normalize_key(domain)}" if domain else f"source-{index}"
        _append_unique(labels, label)
    return labels


def _dedupe_text(values: Iterable[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _string_list(value: Any) -> list[str]:
    return [_consumer_text(item, str(item or "evidence_required")) for item in _iterable(value)]


def _list_of_mappings(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in _iterable(value) if isinstance(item, Mapping)]


def _iterable(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes, bytearray)):
        return [value]
    if isinstance(value, Iterable):
        return list(value)
    return [value]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _get(payload: Any, *keys: str) -> Any:
    if not isinstance(payload, Mapping):
        return None
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _nested_get(payload: Mapping[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        current = _get(current, key)
        if current is None:
            return None
    return current


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _bounded_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed < 0:
        return 0.0
    if parsed > 1:
        return parsed / 100 if parsed <= 100 else 1.0
    return parsed


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


__all__ = (
    "INTELLIGENCE_REPORT_PACKET_VERSION",
    "build_intelligence_report_packet_v2",
)
