# -*- coding: utf-8 -*-
"""Prioritize missing research evidence without mutating source packets."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from src.services.consumer_issue_labels import build_consumer_issues


DEFAULT_RESEARCH_GAP_LIMIT = 8

_GAP_VALUE_KEYS = {
    "missingevidence",
    "missingevidenceraw",
    "missingevidencefamilies",
    "evidencegaps",
    "evidencegapsraw",
    "blockingreasons",
    "blockedreasoncodes",
    "confidencecapreasons",
    "degradedinputs",
    "riskflags",
    "warningflags",
    "needsmoreevidence",
    "nextevidenceneeded",
    "reasonfamilies",
}
_REASON_CODE_KEYS = {
    "reason",
    "reasons",
    "reasoncode",
    "reasoncodes",
    "rawcode",
    "family",
    "scope",
    "capreason",
    "degradationreason",
    "unavailablereason",
    "disabledreason",
    "fallbackreason",
    "sourceauthorityreason",
}
_STATE_KEYS = {
    "status",
    "state",
    "readinessstate",
    "framestate",
    "freshness",
    "freshnessstate",
    "dataqualitystate",
}
_KNOWN_GAP_WORDS = (
    "missing",
    "stale",
    "cached",
    "fallback",
    "blocked",
    "unavailable",
    "insufficient",
    "degraded",
    "partial",
    "unknown",
    "proxy",
    "sample",
    "thin",
    "not_allowed",
)
_ADVICE_RE = re.compile(
    r"\b(buy|sell|hold|recommendation|target|stop|position\s*sizing)\b|"
    r"买入|卖出|持有|目标价|止损|仓位",
    re.IGNORECASE,
)
_GENERIC_LABEL = "Evidence needs review"
_INTERNAL_TOKEN_RE = re.compile(
    r"_blocked|_gate|sourceRefs?|reasonCodes?|sourceRefId|rawCode|provider_runtime|"
    r"[a-z][a-z0-9]*:[a-zA-Z0-9_.=-]+",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class _GapCandidate:
    token: str
    safe_label: str
    family: str
    impact: str
    blocking_level: str
    verification_step: str
    stale_or_missing_reason: str
    score: int
    order: int


def prioritize_research_gaps(*sources: Any, limit: int = DEFAULT_RESEARCH_GAP_LIMIT) -> dict[str, list[dict[str, Any]]]:
    """Return consumer-safe research gaps ordered by research-quality impact.

    The function only inspects already-built packets. It does not mutate input
    mappings, create jobs, call providers, or change scoring decisions.
    """

    max_items = max(int(limit or DEFAULT_RESEARCH_GAP_LIMIT), 0)
    candidates = _dedupe_candidates(_collect_candidates(sources))
    ordered = sorted(candidates, key=lambda item: (-item.score, item.safe_label.casefold(), item.order))
    return {
        "prioritizedResearchGaps": [_candidate_to_contract(item) for item in ordered[:max_items]],
    }


def _collect_candidates(sources: Iterable[Any]) -> list[_GapCandidate]:
    tokens = _collect_gap_tokens(sources)
    candidates: list[_GapCandidate] = []
    for order, token in enumerate(tokens):
        candidate = _candidate_from_token(token, order)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _collect_gap_tokens(value: Any) -> list[str]:
    tokens: list[str] = []
    _walk(value, tokens=tokens, parent_key="")
    return _dedupe_text(tokens)


def _walk(value: Any, *, tokens: list[str], parent_key: str) -> None:
    if value in (None, ""):
        return
    key = _normalize_key(parent_key)
    if isinstance(value, str):
        if _is_gap_key(key) or _looks_like_gap_token(value):
            tokens.append(value)
        return
    if isinstance(value, Mapping):
        if _looks_like_reason_family(value):
            token = _first_text(value.get("rawCode"), value.get("family"), value.get("scope"))
            if token:
                tokens.append(token)
        for nested_key, nested_value in value.items():
            normalized_key = _normalize_key(nested_key)
            if normalized_key in {"sourcerefs", "sourcerefid", "providertrace", "rawpayload", "admindiagnostics"}:
                continue
            if _is_gap_key(normalized_key) or _is_reason_key(normalized_key):
                tokens.extend(_tokens_from_known_gap_value(nested_value))
                continue
            if normalized_key in _STATE_KEYS:
                state = _first_text(nested_value)
                if state and _looks_like_gap_token(state):
                    tokens.append(state)
                continue
            _walk(nested_value, tokens=tokens, parent_key=str(nested_key))
        return
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        for item in value:
            _walk(item, tokens=tokens, parent_key=parent_key)


def _tokens_from_known_gap_value(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        if _looks_like_reason_family(value):
            token = _first_text(value.get("rawCode"), value.get("family"), value.get("scope"))
            return [token] if token else []
        result: list[str] = []
        for key in ("code", "kind", "label", "message", "reason", "rawCode", "family", "scope", "status", "state"):
            token = _first_text(value.get(key))
            if token:
                result.append(token)
        for key in (
            "missingEvidence",
            "evidenceGaps",
            "reasonCodes",
            "blockedReasonCodes",
            "confidenceCapReasons",
            "degradedInputs",
        ):
            result.extend(_tokens_from_known_gap_value(value.get(key)))
        return result
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        result: list[str] = []
        for item in value:
            result.extend(_tokens_from_known_gap_value(item))
        return result
    return []


def _candidate_from_token(token: str, order: int) -> _GapCandidate | None:
    raw = str(token or "").strip()
    if not raw:
        return None
    issue = _consumer_issue(raw)
    safe_label = _safe_label(raw, issue)
    if not safe_label:
        return None
    family = _family_for(raw, safe_label, issue)
    impact = _impact_for(raw, family, safe_label)
    blocking_level = _blocking_level_for(raw, impact)
    verification_step = _verification_step_for(family, raw)
    stale_or_missing_reason = _stale_or_missing_reason_for(raw, family)
    score = _priority_score(raw, family, impact, blocking_level)
    return _GapCandidate(
        token=raw,
        safe_label=safe_label,
        family=family,
        impact=impact,
        blocking_level=blocking_level,
        verification_step=verification_step,
        stale_or_missing_reason=stale_or_missing_reason,
        score=score,
        order=order,
    )


def _candidate_to_contract(candidate: _GapCandidate) -> dict[str, Any]:
    return {
        "gapId": _gap_id(candidate.safe_label, candidate.family),
        "gapFamily": candidate.family,
        "safeGapLabel": candidate.safe_label,
        "impactOnResearchQuality": candidate.impact,
        "blockingLevel": candidate.blocking_level,
        "suggestedVerificationStep": candidate.verification_step,
        "staleOrMissingReason": candidate.stale_or_missing_reason,
        "observationOnly": True,
    }


def _consumer_issue(raw: str) -> Mapping[str, str]:
    issues = build_consumer_issues([raw])
    return issues[0] if issues else {"label": _GENERIC_LABEL, "category": "evidence"}


def _safe_label(raw: str, issue: Mapping[str, str]) -> str:
    label = str(issue.get("label") or "").strip()
    if label != _GENERIC_LABEL and _is_safe_public_text(label):
        return label
    if _looks_like_internal_or_advice(raw):
        return _GENERIC_LABEL
    if _is_safe_public_text(raw):
        return raw
    return _GENERIC_LABEL


def _family_for(raw: str, safe_label: str, issue: Mapping[str, str]) -> str:
    issue_category = str(issue.get("category") or "").strip()
    issue_label = str(issue.get("label") or "").strip()
    if issue_category and issue_label != _GENERIC_LABEL:
        return issue_category
    text = f"{raw} {safe_label}".casefold()
    if any(token in text for token in ("fresh", "stale", "cached", "delayed", "as_of", "time")):
        return "freshness"
    if any(token in text for token in ("right", "authority", "source", "license", "entitlement", "redistribution")):
        return "sourceAuthority"
    if any(token in text for token in ("option", "gamma", "contract", "strike", "expiration", "iv", "multiplier")):
        return "options"
    if any(token in text for token in ("methodology", "formula", "coverage", "threshold", "sign convention")):
        return "methodology"
    if any(token in text for token in ("event", "catalyst")):
        return "events"
    if any(token in text for token in ("liquidity",)):
        return "liquidity"
    if any(token in text for token in ("research", "scanner", "watchlist", "candidate", "context", "ohlcv", "score")):
        return "researchContext"
    return "evidence"


def _impact_for(raw: str, family: str, safe_label: str) -> str:
    text = raw.casefold()
    if safe_label == _GENERIC_LABEL and _looks_like_internal_or_advice(raw):
        return "medium"
    if any(token in text for token in ("blocked", "not_allowed", "unavailable", "source_authority", "score_gate")):
        return "critical"
    if family in {"sourceAuthority", "freshness"} and any(token in text for token in ("missing", "stale", "fallback")):
        return "high"
    if any(token in text for token in ("missing", "insufficient", "thin", "degraded", "partial")):
        return "high"
    if family in {"methodology", "options", "researchContext"}:
        return "medium"
    return "medium"


def _blocking_level_for(raw: str, impact: str) -> str:
    text = raw.casefold()
    if any(token in text for token in ("blocked", "not_allowed", "unavailable", "source_authority", "score_gate")):
        return "blocking"
    if impact == "critical":
        return "blocking"
    if impact == "high":
        return "major"
    return "moderate"


def _verification_step_for(family: str, raw: str) -> str:
    text = raw.casefold()
    if family == "freshness":
        return "Verify the observation timestamp and refresh stale or cached evidence."
    if family == "sourceAuthority":
        return "Verify source authority, usage rights, and score-grade eligibility before relying on the evidence."
    if family == "options":
        return "Verify options contract coverage, greeks, and observation timestamps."
    if family == "methodology":
        return "Verify methodology, coverage thresholds, and calculation metadata."
    if family == "events":
        return "Verify event evidence, timing, and source confirmation."
    if family == "liquidity":
        return "Verify liquidity coverage and whether recent volume evidence is complete."
    if family == "researchContext" or any(token in text for token in ("scanner", "watchlist", "ohlcv", "score")):
        return "Verify scanner, watchlist, and symbol evidence packets before raising research confidence."
    return "Verify the missing supporting evidence before raising research confidence."


def _stale_or_missing_reason_for(raw: str, family: str) -> str:
    text = raw.casefold()
    if any(token in text for token in ("stale", "cached", "fallback", "delayed")):
        return "Evidence is present but may be stale, cached, delayed, or fallback-only."
    if any(token in text for token in ("unavailable", "blocked", "not_allowed")):
        return "Evidence cannot currently support a stronger research conclusion."
    if "proxy" in text or "sample" in text:
        return "Evidence is proxy or sample-based and does not represent the full research context."
    if family == "sourceAuthority":
        return "Source authority or usage rights are incomplete."
    if family == "freshness":
        return "Evidence freshness is missing or not verified."
    return "Supporting evidence is missing, stale, or not strong enough."


def _priority_score(raw: str, family: str, impact: str, blocking_level: str) -> int:
    score = {
        "critical": 300,
        "high": 220,
        "medium": 140,
        "low": 80,
    }.get(impact, 100)
    score += {
        "blocking": 80,
        "major": 40,
        "moderate": 15,
        "minor": 0,
    }.get(blocking_level, 0)
    if family == "sourceAuthority":
        score += 35
    elif family == "freshness":
        score += 25
    elif family in {"evidence", "researchContext"}:
        score += 15
    text = raw.casefold()
    if "source_authority" in text or "score_gate" in text:
        score += 35
    if "missing" in text:
        score += 12
    if any(token in text for token in ("stale", "cached", "fallback")):
        score += 8
    return score


def _dedupe_candidates(candidates: Sequence[_GapCandidate]) -> list[_GapCandidate]:
    result: list[_GapCandidate] = []
    seen: set[str] = set()
    for item in candidates:
        key = item.safe_label.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _gap_id(safe_label: str, family: str) -> str:
    digest = hashlib.sha1(f"{family}:{safe_label}".encode("utf-8")).hexdigest()[:10]
    return f"gap-{digest}"


def _looks_like_reason_family(value: Mapping[str, Any]) -> bool:
    return any(key in value for key in ("rawCode", "family", "scope")) and any(
        _first_text(value.get(key)) for key in ("rawCode", "family", "scope")
    )


def _is_gap_key(key: str) -> bool:
    return key in _GAP_VALUE_KEYS or key.endswith("missingevidence") or key.endswith("evidencegaps")


def _is_reason_key(key: str) -> bool:
    return key in _REASON_CODE_KEYS or key.endswith("reason") or key.endswith("reasons") or key.endswith("reasoncodes")


def _looks_like_gap_token(value: Any) -> bool:
    text = str(value or "").strip().casefold()
    if not text:
        return False
    return any(token in text for token in _KNOWN_GAP_WORDS)


def _looks_like_internal_or_advice(value: str) -> bool:
    return bool(_INTERNAL_TOKEN_RE.search(value) or _ADVICE_RE.search(value))


def _is_safe_public_text(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return not _looks_like_internal_or_advice(text)


def _normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").strip().casefold())


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _dedupe_text(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


__all__ = [
    "DEFAULT_RESEARCH_GAP_LIMIT",
    "prioritize_research_gaps",
]
