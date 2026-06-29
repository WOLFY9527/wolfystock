# -*- coding: utf-8 -*-
"""Consumer-safe issue labels for backend response contracts.

The helpers in this module only format already-produced status and reason
codes. They do not alter provider behavior, scoring, caching, storage, or
authorization decisions.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any


ConsumerIssue = dict[str, str]

_GENERIC_ISSUE: ConsumerIssue = {
    "label": "Evidence needs review",
    "message": "Some quality checks are not fully cleared yet.",
    "severity": "info",
    "category": "evidence",
}

_ISSUES: dict[str, ConsumerIssue] = {
    "freshness_blocked:fallback": {
        "label": "数据新鲜度尚未确认，当前仅显示降级观察结果",
        "message": "数据新鲜度尚未确认，当前仅显示降级观察结果",
        "severity": "warning",
        "category": "freshness",
    },
    "freshness_blocked:unavailable": {
        "label": "数据新鲜度暂不可用，当前仅保留观察结果",
        "message": "数据新鲜度暂不可用，当前仅保留观察结果",
        "severity": "warning",
        "category": "freshness",
    },
    "proxy_or_sample_evidence_blocked": {
        "label": "当前仅有样本或代理证据，暂不足以代表完整市场结构",
        "message": "当前仅有样本或代理证据，暂不足以代表完整市场结构",
        "severity": "warning",
        "category": "evidence",
    },
    "source_authority_or_score_gate_blocked": {
        "label": "当前数据源权威性或评分级别不足，暂不能形成可靠研究结论",
        "message": "当前数据源权威性或评分级别不足，暂不能形成可靠研究结论",
        "severity": "warning",
        "category": "evidence",
    },
    "source_authority_blocked": {
        "label": "证据来源级别不足",
        "message": "证据来源级别不足",
        "severity": "warning",
        "category": "evidence",
    },
    "score_gate": {
        "label": "评分门槛未满足",
        "message": "评分门槛未满足",
        "severity": "warning",
        "category": "evidence",
    },
    "live_gex_not_implemented_v1": {
        "label": "Options gamma unavailable",
        "message": "Live gamma context is not available in this version.",
        "severity": "info",
        "category": "options",
    },
    "option_chain_unavailable": {
        "label": "Options chain unavailable",
        "message": "Options chain evidence is not available for this read.",
        "severity": "warning",
        "category": "options",
    },
    "missing_gamma": {
        "label": "Gamma evidence missing",
        "message": "Some option records are missing gamma values for this observation.",
        "severity": "warning",
        "category": "options",
    },
    "missing_open_interest": {
        "label": "Open interest missing",
        "message": "Some option records are missing open interest values for this observation.",
        "severity": "warning",
        "category": "options",
    },
    "missing_multiplier": {
        "label": "Contract size missing",
        "message": "Some option records are missing contract size values for this observation.",
        "severity": "warning",
        "category": "options",
    },
    "missing_strike": {
        "label": "Strike missing",
        "message": "Some option records are missing strike values for this observation.",
        "severity": "warning",
        "category": "options",
    },
    "missing_expiration": {
        "label": "Expiration missing",
        "message": "Some option records are missing expiration dates for this observation.",
        "severity": "warning",
        "category": "options",
    },
    "missing_side": {
        "label": "Contract type missing",
        "message": "Some option records are missing call or put direction for this observation.",
        "severity": "warning",
        "category": "options",
    },
    "missing_iv": {
        "label": "Implied volatility missing",
        "message": "Some option records are missing implied volatility values for this observation.",
        "severity": "warning",
        "category": "options",
    },
    "missing_as_of": {
        "label": "Observation time missing",
        "message": "Some option records are missing the observation time for this read.",
        "severity": "warning",
        "category": "freshness",
    },
    "freshness_unknown": {
        "label": "Freshness needs verification",
        "message": "The observation time cannot be verified from the current evidence.",
        "severity": "warning",
        "category": "freshness",
    },
    "freshness_degraded": {
        "label": "Freshness is limited",
        "message": "The observation time is older or less direct than preferred.",
        "severity": "warning",
        "category": "freshness",
    },
    "options_gamma_evidence_unavailable": {
        "label": "Options gamma evidence unavailable",
        "message": "Options gamma evidence is not available for this observation.",
        "severity": "warning",
        "category": "options",
    },
    "observation_only_not_decision_grade": {
        "label": "Observation-only context",
        "message": "This evidence is available only as research context.",
        "severity": "info",
        "category": "evidence",
    },
    "observation_only_evidence_blocked": {
        "label": "Observation-only evidence capped",
        "message": "Observation-only evidence cannot raise confidence for this read.",
        "severity": "info",
        "category": "evidence",
    },
    "event_evidence_missing": {
        "label": "Event evidence missing",
        "message": "Event evidence is not available yet.",
        "severity": "warning",
        "category": "events",
    },
    "missing_spot_reference": {
        "label": "Spot reference missing",
        "message": "The underlying spot reference is missing.",
        "severity": "warning",
        "category": "options",
    },
    "missing_contracts": {
        "label": "Option contracts missing",
        "message": "Option contract evidence is missing.",
        "severity": "warning",
        "category": "options",
    },
    "insufficient_usable_contracts": {
        "label": "Usable option coverage is insufficient",
        "message": "There are not enough usable option contracts for this observation.",
        "severity": "warning",
        "category": "options",
    },
    "methodology_approval_missing": {
        "label": "Methodology review missing",
        "message": "The observation methodology has not cleared review.",
        "severity": "info",
        "category": "methodology",
    },
    "provider_authority_missing": {
        "label": "Source authority not confirmed",
        "message": "Source authority has not been confirmed for this evidence.",
        "severity": "warning",
        "category": "rights",
    },
    "redistribution_rights_missing": {
        "label": "Data sharing rights not confirmed",
        "message": "Data sharing rights have not been confirmed.",
        "severity": "info",
        "category": "rights",
    },
    "decision_use_rights_missing": {
        "label": "Use rights not confirmed",
        "message": "Use rights have not been confirmed for this evidence.",
        "severity": "info",
        "category": "rights",
    },
    "provider_rights_incomplete": {
        "label": "Provider rights review incomplete",
        "message": "Provider rights are not fully confirmed for this observation.",
        "severity": "warning",
        "category": "rights",
    },
    "deliverable_handling_missing": {
        "label": "Deliverable handling review missing",
        "message": "Deliverable handling has not cleared review.",
        "severity": "info",
        "category": "rights",
    },
    "formula_version_missing": {
        "label": "Formula version missing",
        "message": "The gamma calculation version is not recorded for this observation.",
        "severity": "warning",
        "category": "methodology",
    },
    "formula_version_unsupported": {
        "label": "Formula version needs review",
        "message": "The recorded gamma calculation version does not match this observation contract.",
        "severity": "warning",
        "category": "methodology",
    },
    "sign_convention_missing": {
        "label": "Sign convention missing",
        "message": "The gamma sign convention is not recorded for this observation.",
        "severity": "warning",
        "category": "methodology",
    },
    "sign_convention_unsupported": {
        "label": "Sign convention needs review",
        "message": "The recorded gamma sign convention does not match this observation contract.",
        "severity": "warning",
        "category": "methodology",
    },
    "coverage_thresholds_missing": {
        "label": "Coverage thresholds missing",
        "message": "Coverage thresholds are not defined for this observation.",
        "severity": "info",
        "category": "methodology",
    },
    "coverage_threshold_missing": {
        "label": "Coverage threshold missing",
        "message": "The review threshold for coverage is not recorded for this observation.",
        "severity": "warning",
        "category": "methodology",
    },
    "coverage_missing": {
        "label": "Coverage check unavailable",
        "message": "Coverage cannot be confirmed for this observation.",
        "severity": "warning",
        "category": "methodology",
    },
    "coverage_below_threshold": {
        "label": "Coverage below review threshold",
        "message": "Coverage is below the review threshold for this observation.",
        "severity": "warning",
        "category": "methodology",
    },
    "limited_source_quality_present": {
        "label": "Limited source quality present",
        "message": "Some evidence has limited source quality.",
        "severity": "warning",
        "category": "evidence",
    },
    "non_score_grade_freshness_present": {
        "label": "Freshness is not score-grade",
        "message": "Some freshness evidence cannot support a stronger confidence read.",
        "severity": "info",
        "category": "freshness",
    },
    "observation_only_evidence_present": {
        "label": "Observation-only evidence present",
        "message": "Some evidence is available only for observation.",
        "severity": "info",
        "category": "evidence",
    },
    "proxy_or_sample_evidence_present": {
        "label": "Proxy or sample evidence present",
        "message": "Some evidence comes from proxy or sample inputs.",
        "severity": "warning",
        "category": "evidence",
    },
    "research_candidates_unavailable": {
        "label": "Research candidates unavailable",
        "message": "Research candidates are not available for this payload.",
        "severity": "warning",
        "category": "research",
    },
    "market_regime_read_model_failed_closed": {
        "label": "Market Regime Read Model failed closed",
        "message": "Market regime evidence inputs are unavailable for the primary read.",
        "severity": "warning",
        "category": "evidence",
    },
    "market_regime_read_model_degraded": {
        "label": "Market Regime Read Model degraded",
        "message": "Market regime evidence inputs are degraded for the primary read.",
        "severity": "warning",
        "category": "evidence",
    },
    "secondary_research_evidence_unavailable": {
        "label": "Secondary Research Radar evidence unavailable",
        "message": "Research Radar evidence is unavailable as secondary context.",
        "severity": "info",
        "category": "research",
    },
    "secondary_options_evidence_unavailable": {
        "label": "Secondary options structure evidence unavailable",
        "message": "Options structure evidence is unavailable as secondary context.",
        "severity": "info",
        "category": "options",
    },
    "advanced_evidence_observation_only": {
        "label": "Advanced evidence observation-only",
        "message": "Advanced evidence remains secondary observation context.",
        "severity": "info",
        "category": "evidence",
    },
    "avoidlowevidence": {
        "label": "Low-evidence filter active",
        "message": "The queue is avoiding low-evidence candidates.",
        "severity": "warning",
        "category": "research",
    },
    "low_liquidity": {
        "label": "Liquidity is limited",
        "message": "Liquidity evidence is limited for this item.",
        "severity": "warning",
        "category": "liquidity",
    },
    "missing_evidence": {
        "label": "Evidence missing",
        "message": "Required evidence is missing.",
        "severity": "warning",
        "category": "evidence",
    },
    "candidate_evidence_incomplete": {
        "label": "Candidate evidence incomplete",
        "message": "The candidate still needs more evidence before the read is complete.",
        "severity": "warning",
        "category": "evidence",
    },
    "core_candidate_evidence_missing": {
        "label": "Core candidate evidence missing",
        "message": "Core scanner evidence is unavailable.",
        "severity": "warning",
        "category": "evidence",
    },
    "research_readiness_missing": {
        "label": "Research readiness evidence missing",
        "message": "Research readiness evidence is missing.",
        "severity": "warning",
        "category": "evidence",
    },
    "research_summary_missing": {
        "label": "Research summary evidence missing",
        "message": "Research summary evidence is missing.",
        "severity": "info",
        "category": "research",
    },
    "candidate_evidence_thin": {
        "label": "Evidence coverage is thin",
        "message": "Evidence coverage is too thin for a stronger research read.",
        "severity": "warning",
        "category": "evidence",
    },
    "scanner_overlay_candidates_unavailable": {
        "label": "Scanner overlay unavailable",
        "message": "Scanner candidates are unavailable for this overlay.",
        "severity": "warning",
        "category": "research",
    },
    "research_context_missing": {
        "label": "Research context missing",
        "message": "The saved research context still needs to be added or refreshed.",
        "severity": "info",
        "category": "research",
    },
    "local_ohlcv_evidence_missing": {
        "label": "Local price history missing",
        "message": "Local price-history evidence is not available for this read.",
        "severity": "warning",
        "category": "evidence",
    },
    "scanner_score_evidence_missing": {
        "label": "Scanner score evidence missing",
        "message": "The latest scanner score evidence is not available for this read.",
        "severity": "info",
        "category": "research",
    },
    "score_grade_not_cleared": {
        "label": "Score-grade conclusion not cleared",
        "message": "Evidence quality is not cleared for a stronger score-grade conclusion.",
        "severity": "warning",
        "category": "evidence",
    },
    "watchlist_data_unavailable": {
        "label": "Watchlist data unavailable",
        "message": "Watchlist research data is temporarily unavailable.",
        "severity": "warning",
        "category": "research",
    },
    "scanner_data_unavailable": {
        "label": "Scanner data unavailable",
        "message": "Scanner evidence is temporarily unavailable for this read.",
        "severity": "warning",
        "category": "research",
    },
    "fundamentals": {
        "label": "Fundamental evidence missing",
        "message": "Fundamental evidence is missing.",
        "severity": "info",
        "category": "evidence",
    },
    "news": {
        "label": "News evidence missing",
        "message": "News evidence is missing.",
        "severity": "info",
        "category": "evidence",
    },
    "catalyst": {
        "label": "Catalyst evidence missing",
        "message": "Catalyst evidence is missing.",
        "severity": "info",
        "category": "events",
    },
    "freshness": {
        "label": "Freshness evidence missing",
        "message": "Freshness evidence is missing.",
        "severity": "info",
        "category": "freshness",
    },
}

_ALIASES = {
    "fallback": "freshness_blocked:fallback",
    "stale": "freshness_blocked:fallback",
    "cached": "freshness_blocked:fallback",
    "delayed": "freshness_blocked:fallback",
    "stale_evidence": "freshness_blocked:fallback",
    "cached_or_stale_evidence": "freshness_blocked:fallback",
    "delayed_evidence": "freshness_blocked:fallback",
    "fresh_evidence": "freshness",
    "unavailable": "freshness_blocked:unavailable",
    "unknown_freshness": "freshness_blocked:unavailable",
    "stale_freshness": "freshness_blocked:fallback",
    "proxyevidence": "proxy_or_sample_evidence_present",
    "fallbackevidence": "proxy_or_sample_evidence_present",
    "sampleonlyevidence": "proxy_or_sample_evidence_present",
    "scannerCandidates": "scanner_overlay_candidates_unavailable",
    "scannercandidates": "scanner_overlay_candidates_unavailable",
    "scanner_candidates": "scanner_overlay_candidates_unavailable",
    "candidateEvidenceFrame": "core_candidate_evidence_missing",
    "candidateResearchReadiness": "research_readiness_missing",
    "candidateResearchSummaryFrame": "research_summary_missing",
    "insufficient_candidate_evidence": "candidate_evidence_thin",
    "evidence_gaps_present": "missing_evidence",
    "watchlist_research_context": "research_context_missing",
    "local_ohlcv_evidence": "local_ohlcv_evidence_missing",
    "missing_local_ohlcv": "local_ohlcv_evidence_missing",
    "scanner_score_evidence": "scanner_score_evidence_missing",
    "score_grade_not_allowed": "score_grade_not_cleared",
    "watchlist_data_unavailable": "watchlist_data_unavailable",
    "scanner_data_unavailable": "scanner_data_unavailable",
    "insufficient_research_evidence": "missing_evidence",
}


def build_consumer_issues(*sources: Any) -> list[ConsumerIssue]:
    """Return deduped consumer-safe issue descriptions for raw status values."""

    issues: list[ConsumerIssue] = []
    seen: set[tuple[str, str, str, str]] = set()
    for token in _issue_tokens(sources):
        issue = dict(_issue_for(token))
        key = (issue["label"], issue["message"], issue["severity"], issue["category"])
        if key in seen:
            continue
        seen.add(key)
        issues.append(issue)
    return issues


def build_consumer_message(issues: Sequence[Mapping[str, str]] | None) -> str | None:
    labels = []
    for issue in issues or []:
        label = str(issue.get("label") or "").strip()
        if label and label not in labels:
            labels.append(label)
    if not labels:
        return None
    return "; ".join(labels) + "."


def consumer_safe_reason_label(value: Any) -> str:
    """Return a consumer-facing reason label without echoing raw codes."""

    return _issue_for(str(value or ""))["label"]


def sanitize_consumer_reason_payload(value: Any) -> Any:
    """Redact raw reason codes from consumer-facing reason-like fields."""

    if isinstance(value, Mapping):
        if _looks_like_reason_family(value):
            return _sanitize_reason_family(value)
        sanitized: dict[str, Any] = {}
        for key, nested in value.items():
            if _is_reason_value_key(str(key)):
                sanitized[str(key)] = _sanitize_reason_value(nested)
            else:
                sanitized[str(key)] = sanitize_consumer_reason_payload(nested)
        return sanitized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [sanitize_consumer_reason_payload(item) for item in value]
    return value


def _issue_for(token: str) -> ConsumerIssue:
    key = _normalized_key(token)
    alias = _ALIASES.get(key) or _ALIASES.get(str(token or "").strip())
    if alias:
        key = _normalized_key(alias)
    return _ISSUES.get(key, _GENERIC_ISSUE)


def _normalized_key(value: Any) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if lowered == "avoidlowevidence":
        return "avoidlowevidence"
    return lowered


def _issue_tokens(values: Iterable[Any]) -> list[str]:
    tokens: list[str] = []
    for value in values:
        tokens.extend(_tokens_from_value(value))
    return _dedupe(tokens)


def _tokens_from_value(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, Mapping):
        tokens: list[str] = []
        for key in (
            "code",
            "kind",
            "reason",
            "status",
            "state",
            "researchBias",
            "freshness",
            "degradationReason",
            "capReason",
            "unavailableReason",
            "disabledReason",
        ):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                tokens.append(raw.strip())
        for key in (
            "reasonCodes",
            "blockedReasonCodes",
            "confidenceCapReasons",
            "evidenceGaps",
            "riskFlags",
            "missingEvidence",
            "degradedInputs",
            "dataQualityLabels",
        ):
            tokens.extend(_tokens_from_value(value.get(key)))
        return tokens
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        tokens = []
        for item in value:
            tokens.extend(_tokens_from_value(item))
        return tokens
    return []


def _dedupe(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _is_reason_value_key(key: str) -> bool:
    normalized = key.strip()
    lowered = normalized.lower()
    return (
        lowered in {
            "reason",
            "reasons",
            "reasoncode",
            "reasoncodes",
            "blockedreasoncodes",
            "confidencecapreasons",
            "confidencecaps",
            "confidencepenalties",
            "missingevidence",
            "needsmoreevidence",
            "evidencegaps",
            "degradedinputs",
            "degradationreason",
            "capreason",
            "unavailablereason",
            "disabledreason",
            "fallbackreason",
            "sourceauthorityreason",
            "excludereason",
            "rawcode",
            "family",
            "scope",
        }
        or lowered.endswith("reason")
        or lowered.endswith("reasons")
        or lowered.endswith("reasoncodes")
    )


def _sanitize_reason_value(value: Any) -> Any:
    if isinstance(value, str):
        return _safe_reason_text(value)
    if isinstance(value, Mapping):
        return sanitize_consumer_reason_payload(value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [_sanitize_reason_value(item) for item in value]
    return value


def _safe_reason_text(value: str) -> str:
    issue = _issue_for(value)
    if issue != _GENERIC_ISSUE:
        return issue["label"]
    if _looks_like_internal_reason_token(value):
        return _GENERIC_ISSUE["label"]
    return value


def _looks_like_internal_reason_token(value: str) -> bool:
    lowered = str(value or "").strip().lower()
    return (
        "_blocked" in lowered
        or "_gate" in lowered
        or lowered.startswith("freshness_blocked")
        or lowered in {
            "proxy_or_sample_evidence_blocked",
            "source_authority_or_score_gate_blocked",
            "source_authority_blocked",
            "score_gate",
        }
    )


def _looks_like_reason_family(value: Mapping[str, Any]) -> bool:
    if "rawCode" in value:
        return True
    for key in ("family", "scope"):
        token = str(value.get(key) or "").strip()
        if not token:
            continue
        if _issue_for(token) != _GENERIC_ISSUE or _looks_like_internal_reason_token(token):
            return True
    return False


def _sanitize_reason_family(value: Mapping[str, Any]) -> dict[str, Any]:
    issue = _reason_family_issue(value)
    result = {
        "label": issue["label"],
        "category": issue["category"],
    }
    source_field = str(value.get("sourceField") or "").strip()
    if source_field:
        result["sourceField"] = source_field
    return result


def _reason_family_issue(value: Mapping[str, Any]) -> ConsumerIssue:
    for key in ("rawCode", "family", "scope"):
        token = str(value.get(key) or "").strip()
        if not token:
            continue
        issue = _issue_for(token)
        if issue != _GENERIC_ISSUE:
            return issue
    return _GENERIC_ISSUE


__all__ = [
    "ConsumerIssue",
    "build_consumer_issues",
    "build_consumer_message",
    "consumer_safe_reason_label",
    "sanitize_consumer_reason_payload",
]
