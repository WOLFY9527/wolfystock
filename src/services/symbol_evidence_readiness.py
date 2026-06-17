# -*- coding: utf-8 -*-
"""Pure symbol evidence readiness projector.

Consumes already-built stock evidence items and emits a bounded research
readiness packet. It performs no provider calls, cache reads, DB access, or LLM
work.
"""

from __future__ import annotations

from typing import Any, Mapping


SYMBOL_EVIDENCE_READINESS_NO_ADVICE_DISCLOSURE = (
    "Observation-only research readiness; not personalized financial advice or an instruction."
)

_REQUIRED_FAMILIES = ("quote", "technical", "fundamental", "news")
_OPTIONAL_FAMILIES = ("secFilingEvidence",)
_ALL_FAMILIES = _REQUIRED_FAMILIES + _OPTIONAL_FAMILIES
_AVAILABLE_STATUSES = {"available", "ok", "success"}
_PARTIAL_STATUSES = {"partial"}
_MISSING_STATUSES = {"", "missing", "unknown", "unavailable", "error", "rejected", "placeholder"}
_STALE_FRESHNESS = {"stale", "fallback", "delayed", "partial", "synthetic"}
_STALE_SOURCE_TYPES = {"fallback", "synthetic", "unofficial_proxy"}
_NEWS_PLACEHOLDER_TOKENS = ("placeholder", "unknown", "no recent headlines", "not available")


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _status(payload: Mapping[str, Any]) -> str:
    return _text(payload.get("status"), "missing").lower() or "missing"


def _is_partial(payload: Mapping[str, Any]) -> bool:
    return _status(payload) in _PARTIAL_STATUSES


def _is_missing(payload: Mapping[str, Any]) -> bool:
    return _status(payload) in _MISSING_STATUSES


def _news_is_placeholder(news: Mapping[str, Any]) -> bool:
    headline = _text(news.get("latestHeadline") or news.get("headline")).lower()
    provider = _text(news.get("provider") or news.get("providerId") or news.get("providerName")).lower()
    if _is_missing(news):
        return True
    return any(token in headline or token in provider for token in _NEWS_PLACEHOLDER_TOKENS)


def _is_used(family: str, payload: Mapping[str, Any]) -> bool:
    if family == "news" and _news_is_placeholder(payload):
        return False
    return _status(payload) in _AVAILABLE_STATUSES or _is_partial(payload)


def _is_stale_input(payload: Mapping[str, Any]) -> bool:
    if not payload:
        return False
    if any(bool(payload.get(key)) for key in ("isStale", "isFallback", "isSynthetic")):
        return True
    freshness = _text(payload.get("freshness") or payload.get("freshnessClass")).lower()
    if freshness in _STALE_FRESHNESS:
        return True
    source_type = _text(payload.get("sourceType") or payload.get("sourceClass") or payload.get("sourceTier")).lower()
    return source_type in _STALE_SOURCE_TYPES


def _explicit_conflicting_families(families: Mapping[str, Mapping[str, Any]]) -> list[str]:
    conflicting: list[str] = []
    for family, payload in families.items():
        status = _status(payload)
        if status in {"conflict", "conflicting"} or payload.get("conflict") is True:
            conflicting.append(family)
    return conflicting


def _readiness_tier(
    *,
    evidence_used: list[str],
    evidence_missing: list[str],
    stale_inputs: list[str],
    conflicting_evidence: list[str],
) -> str:
    clean_required = [
        family
        for family in _REQUIRED_FAMILIES
        if family in evidence_used
        and family not in evidence_missing
        and family not in stale_inputs
        and family not in conflicting_evidence
    ]
    if len(clean_required) == len(_REQUIRED_FAMILIES):
        return "sufficient"

    required_used_count = len([family for family in _REQUIRED_FAMILIES if family in evidence_used])
    if required_used_count >= 2:
        return "partial"
    return "insufficient"


def _data_quality_notes(
    *,
    readiness_tier: str,
    evidence_missing: list[str],
    stale_inputs: list[str],
    conflicting_evidence: list[str],
    evidence_used: list[str],
) -> list[str]:
    notes: list[str] = []
    if readiness_tier == "sufficient":
        notes.append("Core quote, technical, fundamental, and news evidence are present without stale markers.")
    elif readiness_tier == "partial":
        notes.append("Some symbol evidence is present, but the packet is not complete enough for a clean research handoff.")
    else:
        notes.append("Symbol evidence is too sparse for a clean research handoff.")

    if evidence_missing:
        notes.append(f"Missing or incomplete evidence families: {', '.join(evidence_missing)}.")
    if stale_inputs:
        notes.append(f"Stale or delayed input markers are present for: {', '.join(stale_inputs)}.")
    if conflicting_evidence:
        notes.append(f"Explicit conflict markers are present for: {', '.join(conflicting_evidence)}.")
    if "secFilingEvidence" in evidence_used:
        notes.append("SEC filing evidence is treated as observation-only context.")
    return notes


def _suggested_research_path(
    *,
    readiness_tier: str,
    evidence_missing: list[str],
    stale_inputs: list[str],
) -> list[str]:
    if readiness_tier == "sufficient":
        return [
            "Continue by reviewing quote, technical, fundamental, and news evidence together.",
            "Keep any downstream thesis work separate from trading instructions.",
        ]

    path: list[str] = []
    if readiness_tier == "insufficient":
        path.append("Collect core symbol evidence before symbol-specific thesis work.")
    if "quote" in evidence_missing:
        path.append("Confirm a quote snapshot and freshness context.")
    if "technical" in evidence_missing:
        path.append("Add recent OHLC or technical context.")
    if "fundamental" in evidence_missing:
        path.append("Add fundamental coverage before business-quality review.")
    if "news" in evidence_missing:
        path.append("Add recent news or filing context before catalyst review.")
    if stale_inputs:
        path.append("Refresh stale or delayed inputs before comparing research scenarios.")
    if not path:
        path.append("Review the available evidence and fill the weakest missing family first.")
    return path


def build_symbol_evidence_readiness(stock_evidence_item: Mapping[str, Any]) -> dict[str, Any]:
    """Build the bounded symbol-level evidence readiness packet."""

    item = _as_mapping(stock_evidence_item)
    symbol = _text(item.get("symbol"), "unknown").upper() or "unknown"
    families = {family: _as_mapping(item.get(family)) for family in _ALL_FAMILIES}

    evidence_used = [
        family
        for family in _ALL_FAMILIES
        if _is_used(family, families[family])
    ]
    evidence_missing = [
        family
        for family in _REQUIRED_FAMILIES
        if _is_missing(families[family]) or _is_partial(families[family])
    ]
    stale_inputs = [
        family
        for family in _ALL_FAMILIES
        if family in evidence_used and _is_stale_input(families[family])
    ]
    conflicting_evidence = _explicit_conflicting_families(families)
    readiness_tier = _readiness_tier(
        evidence_used=evidence_used,
        evidence_missing=evidence_missing,
        stale_inputs=stale_inputs,
        conflicting_evidence=conflicting_evidence,
    )

    return {
        "symbolEvidenceReadiness": True,
        "symbol": symbol,
        "readinessTier": readiness_tier,
        "evidenceUsed": evidence_used,
        "evidenceMissing": evidence_missing,
        "staleInputs": stale_inputs,
        "conflictingEvidence": conflicting_evidence,
        "dataQualityNotes": _data_quality_notes(
            readiness_tier=readiness_tier,
            evidence_missing=evidence_missing,
            stale_inputs=stale_inputs,
            conflicting_evidence=conflicting_evidence,
            evidence_used=evidence_used,
        ),
        "suggestedResearchPath": _suggested_research_path(
            readiness_tier=readiness_tier,
            evidence_missing=evidence_missing,
            stale_inputs=stale_inputs,
        ),
        "observationOnly": True,
        "noAdviceDisclosure": SYMBOL_EVIDENCE_READINESS_NO_ADVICE_DISCLOSURE,
    }


__all__ = [
    "SYMBOL_EVIDENCE_READINESS_NO_ADVICE_DISCLOSURE",
    "build_symbol_evidence_readiness",
]
