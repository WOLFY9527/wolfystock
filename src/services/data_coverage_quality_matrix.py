# -*- coding: utf-8 -*-
"""Pure cross-surface data coverage quality matrix builder.

The builder only reads caller-supplied research fragments. It performs no
provider, network, storage, cache, API, or LLM work.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


DATA_COVERAGE_QUALITY_MATRIX_CONTRACT_VERSION = "data_coverage_quality_matrix_v2"
DATA_COVERAGE_QUALITY_MATRIX_NO_ADVICE_DISCLOSURE = (
    "Observation-only research coverage; not a personalized financial instruction."
)

_COMPLETE = "complete"
_PARTIAL = "partial"
_STALE = "stale"
_INSUFFICIENT = "insufficient_evidence"
_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
_STATE_ALIASES = {
    "ready": _COMPLETE,
    "available": _COMPLETE,
    "complete": _COMPLETE,
    "sufficient": _COMPLETE,
    "partial": _PARTIAL,
    "degraded": _PARTIAL,
    "stale": _STALE,
    "delayed": _STALE,
    "cached": _STALE,
    "stale_or_cached": _STALE,
    "insufficient": _INSUFFICIENT,
    "insufficient_evidence": _INSUFFICIENT,
    "missing": _INSUFFICIENT,
    "no_evidence": _INSUFFICIENT,
    "unavailable": _INSUFFICIENT,
    "unknown": _INSUFFICIENT,
}
_STALE_VALUES = {
    "cached",
    "delayed",
    "fallback",
    "partial",
    "recent_but_limited",
    "stale",
    "stale_or_cached",
    "synthetic",
    "unknown",
    "unavailable",
}
_UNSAFE_KEY_MARKERS = (
    "provider",
    "debug",
    "runtime",
    "cache",
    "source_ref",
    "sourceref",
    "reason_code",
    "reasoncode",
    "request_id",
    "requestid",
    "trace",
    "raw",
)
_UNSAFE_TEXT_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "debug",
    "diagnostic",
    "duckdb",
    "payload",
    "provider",
    "request_id",
    "requestid",
    "runtime",
    "secret",
    "source_ref",
    "sourceref",
    "token",
    "trace",
    "raw",
)
_ADVICE_WORD_MARKERS = {"buy", "sell", "hold", "recommend"}
_ADVICE_PHRASE_MARKERS = (
    "target price",
    "stop loss",
    "position sizing",
    "position-sizing",
)
_ADVICE_CJK_MARKERS = ("买入", "卖出", "持有", "推荐", "目标价", "止损", "仓位建议")

_SURFACES: tuple[dict[str, Any], ...] = (
    {
        "surface": "symbol_evidence_readiness",
        "input_key": "symbolEvidenceReadiness",
        "aliases": ("symbolEvidenceReadiness",),
        "family": "symbol_evidence",
        "critical": True,
        "kind": "symbol",
    },
    {
        "surface": "peer_correlation",
        "input_key": "peerCorrelationSnapshot",
        "aliases": ("peerCorrelationSnapshot",),
        "family": "peer_correlation",
        "kind": "peer",
    },
    {
        "surface": "symbol_compare_evidence",
        "input_key": "symbolCompareEvidencePacket",
        "aliases": ("symbolCompareEvidencePacket",),
        "family": "symbol_compare",
        "kind": "compare",
    },
    {
        "surface": "theme_correlation_breadth",
        "input_key": "themeCorrelationBreadthSnapshot",
        "aliases": ("themeCorrelationBreadthSnapshot",),
        "family": "theme_correlation",
    },
    {
        "surface": "market_regime_synthesis",
        "input_key": "marketRegimeSynthesis",
        "aliases": ("marketRegimeSynthesis",),
        "family": "market_regime",
        "conflict_keys": ("conflictingInputs", "conflictingEvidence", "contradictoryEvidence"),
    },
    {
        "surface": "scanner_candidate_research",
        "input_key": "scannerCandidateResearchPacket",
        "aliases": ("scannerCandidateResearchPacket", "candidateResearchPacket", "scannerResearchOverlay"),
        "family": "scanner_candidate",
        "state_keys": ("coverageState", "readinessState", "overlayState", "candidateResearchState", "status"),
        "missing_keys": ("missingInputs", "missingEvidence", "evidenceMissing", "evidenceGaps"),
    },
    {
        "surface": "watchlist_research_priority",
        "input_key": "watchlistResearchPriorityQueue",
        "aliases": ("watchlistResearchPriorityQueue", "researchPriorityQueue", "watchlistResearchOverlay"),
        "family": "watchlist_research",
        "kind": "watchlist",
        "state_keys": ("coverageState", "queueState", "overlayState", "readinessState", "status"),
        "missing_keys": ("missingInputs", "missingEvidence", "evidenceMissing", "evidenceGaps"),
    },
    {
        "surface": "portfolio_exposure_research",
        "input_key": "portfolioExposureResearchContext",
        "aliases": ("portfolioExposureResearchContext", "exposureResearchContext", "portfolioResearchContext"),
        "family": "portfolio_exposure",
        "missing_keys": ("missingInputs", "missingEvidence", "evidenceMissing", "evidenceGaps"),
    },
    {
        "surface": "evidence_provenance_ledger",
        "input_key": "evidenceProvenanceLedger",
        "aliases": ("evidenceProvenanceLedger", "provenanceLedger"),
        "family": "evidence_provenance",
        "critical": True,
        "kind": "provenance",
    },
)


def build_data_coverage_quality_matrix(input_packet: Mapping[str, Any]) -> dict[str, Any]:
    """Build a deterministic fail-closed coverage matrix from computed inputs."""

    packet = input_packet if isinstance(input_packet, Mapping) else {}
    summaries = [_summarize_surface(packet, spec) for spec in _SURFACES]
    missing_critical = [
        item["inputKey"]
        for item in summaries
        if item["critical"] and (not item["evidencePresent"] or item["coverageState"] == _INSUFFICIENT)
    ]
    stale_inputs = _issue_rows(summaries, "staleInputs")
    conflicting_inputs = _issue_rows(summaries, "conflictingInputs")
    families_present = [
        item["evidenceFamily"]
        for item in summaries
        if item["evidencePresent"] and item["coverageState"] != _INSUFFICIENT
    ]
    families_missing = [
        item["evidenceFamily"]
        for item in summaries
        if not item["evidencePresent"] or item["coverageState"] == _INSUFFICIENT
    ]
    coverage_state = _aggregate_state(
        summaries,
        missing_critical=missing_critical,
        stale_inputs=stale_inputs,
        conflicting_inputs=conflicting_inputs,
        families_missing=families_missing,
    )

    return {
        "contractVersion": DATA_COVERAGE_QUALITY_MATRIX_CONTRACT_VERSION,
        "subject": _subject(packet),
        "coverageState": coverage_state,
        "coverageBySurface": {item["surface"]: item for item in summaries},
        "missingCriticalInputs": missing_critical,
        "staleInputs": stale_inputs,
        "conflictingInputs": conflicting_inputs,
        "evidenceFamiliesPresent": _dedupe(families_present),
        "evidenceFamiliesMissing": _dedupe(families_missing),
        "confidenceCap": _aggregate_confidence(summaries, coverage_state),
        "observationBoundary": {
            "observationOnly": True,
            "decisionGrade": False,
            "personalizedInstruction": False,
        },
        "researchNextSteps": _research_next_steps(
            missing_critical=missing_critical,
            families_missing=families_missing,
            stale_inputs=stale_inputs,
            conflicting_inputs=conflicting_inputs,
        ),
        "noAdviceDisclosure": DATA_COVERAGE_QUALITY_MATRIX_NO_ADVICE_DISCLOSURE,
    }


def _summarize_surface(packet: Mapping[str, Any], spec: Mapping[str, Any]) -> dict[str, Any]:
    value, present = _lookup(packet, spec)
    if not present:
        return _surface_result(spec, present=False, state=_INSUFFICIENT, missing=("input not present",))

    unsafe = _has_unsafe_material(value)
    if spec.get("kind") == "provenance":
        return _summarize_provenance(spec, value, unsafe=unsafe)
    if not isinstance(value, Mapping):
        return _surface_result(
            spec,
            present=True,
            state=_INSUFFICIENT,
            missing=("input malformed",),
            unsafe=unsafe,
        )
    if spec.get("kind") == "symbol":
        return _surface_result(
            spec,
            present=True,
            state=_state(value.get("readinessTier")),
            missing=_safe_list(value.get("evidenceMissing")),
            stale=_safe_list(value.get("staleInputs")),
            conflicts=_safe_list(value.get("conflictingEvidence")),
            confidence=_confidence(value.get("confidenceCap")),
            unsafe=unsafe,
        )
    if spec.get("kind") == "peer":
        correlation_state = _text(value.get("correlationState")).lower()
        conflicts = ("peer movement divergence",) if correlation_state == "diverging" or _non_empty(value.get("divergenceEvidence")) else ()
        state = _INSUFFICIENT if correlation_state == _INSUFFICIENT else _COMPLETE
        return _surface_result(
            spec,
            present=True,
            state=state,
            missing=_safe_list(value.get("missingInputs")),
            stale=_safe_list(value.get("staleInputs")),
            conflicts=conflicts,
            confidence=_confidence(value.get("confidenceCap")),
            unsafe=unsafe,
        )
    if spec.get("kind") == "compare":
        missing = list(_missing_from_compare(value))
        if not _non_empty(value.get("sharedEvidence")):
            missing.append("shared comparison evidence")
        conflicts = ("cross-symbol divergence",) if _non_empty(value.get("divergentEvidence")) else ()
        return _surface_result(
            spec,
            present=True,
            state=_COMPLETE,
            missing=missing,
            conflicts=conflicts,
            confidence=_confidence(value.get("confidenceCap")),
            unsafe=unsafe,
        )

    result = _generic_summary(spec, value, unsafe=unsafe)
    if spec.get("kind") == "watchlist" and _is_empty_sequence(value.get("items")) and result["coverageState"] == _COMPLETE:
        result["coverageState"] = _PARTIAL
        result["confidenceCap"] = _min_confidence(result["confidenceCap"], "medium")
        result["missingInputs"] = _dedupe([*result["missingInputs"], "research queue items"])
    return result


def _generic_summary(spec: Mapping[str, Any], value: Mapping[str, Any], *, unsafe: bool) -> dict[str, Any]:
    return _surface_result(
        spec,
        present=True,
        state=_state(_first_present(value, *spec.get("state_keys", ("coverageState", "readinessState", "status", "state")))),
        missing=_safe_list(_first_present(value, *spec.get("missing_keys", ("missingInputs", "missingEvidence", "evidenceMissing")))),
        stale=_safe_list(_first_present(value, *spec.get("stale_keys", ("staleInputs", "degradedInputs")))),
        conflicts=_safe_list(_first_present(value, *spec.get("conflict_keys", ("conflictingInputs", "conflictingEvidence", "divergentEvidence")))),
        confidence=_confidence(value.get("confidenceCap")),
        unsafe=unsafe,
    )


def _summarize_provenance(spec: Mapping[str, Any], value: Any, *, unsafe: bool) -> dict[str, Any]:
    entries = _provenance_entries(value)
    if not entries:
        return _surface_result(
            spec,
            present=True,
            state=_INSUFFICIENT,
            missing=("ledger entries",),
            unsafe=unsafe,
        )

    stale: list[str] = []
    missing: list[str] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            missing.append("ledger entry")
            continue
        freshness = _text(_first_present(entry, "freshnessBucket", "freshnessState", "freshness")).lower()
        limitation = _text(_first_present(entry, "limitation", "limitations")).lower()
        if freshness in _STALE_VALUES or limitation in {"limited_coverage", "stale_or_delayed"}:
            stale.append(_safe_text(_first_present(entry, "evidenceFamily", "family")) or "evidence entry")
    return _surface_result(spec, present=True, state=_COMPLETE, missing=missing, stale=stale, unsafe=unsafe)


def _surface_result(
    spec: Mapping[str, Any],
    *,
    present: bool,
    state: str,
    missing: Sequence[str] = (),
    stale: Sequence[str] = (),
    conflicts: Sequence[str] = (),
    confidence: str = "high",
    unsafe: bool = False,
) -> dict[str, Any]:
    safe_missing = _dedupe(_safe_list(missing))
    safe_stale = _dedupe(_safe_list(stale))
    safe_conflicts = _dedupe(_safe_list(conflicts))

    effective_state = state
    if effective_state == _COMPLETE and (safe_missing or safe_conflicts or unsafe):
        effective_state = _PARTIAL
    if safe_stale:
        effective_state = _STALE

    if effective_state == _INSUFFICIENT or safe_stale or safe_conflicts or unsafe:
        confidence = _min_confidence(confidence, "low")
    elif effective_state == _PARTIAL:
        confidence = _min_confidence(confidence, "medium")

    return {
        "surface": str(spec["surface"]),
        "inputKey": str(spec["input_key"]),
        "evidenceFamily": str(spec["family"]),
        "critical": bool(spec.get("critical")),
        "evidencePresent": present,
        "coverageState": effective_state,
        "confidenceCap": confidence,
        "missingInputs": safe_missing,
        "staleInputs": safe_stale,
        "conflictingInputs": safe_conflicts,
        "sanitizationApplied": unsafe,
        "observationOnly": True,
    }


def _aggregate_state(
    summaries: Sequence[Mapping[str, Any]],
    *,
    missing_critical: Sequence[str],
    stale_inputs: Sequence[Mapping[str, Any]],
    conflicting_inputs: Sequence[Mapping[str, Any]],
    families_missing: Sequence[str],
) -> str:
    if missing_critical:
        return _INSUFFICIENT
    if stale_inputs or any(item["coverageState"] == _STALE for item in summaries):
        return _STALE
    if (
        conflicting_inputs
        or families_missing
        or any(item["coverageState"] == _PARTIAL or item["sanitizationApplied"] for item in summaries)
    ):
        return _PARTIAL
    return _COMPLETE


def _aggregate_confidence(summaries: Sequence[Mapping[str, Any]], coverage_state: str) -> str:
    caps = [str(item["confidenceCap"]) for item in summaries if item["evidencePresent"]]
    if not caps:
        return "low"
    if coverage_state in {_INSUFFICIENT, _STALE}:
        caps.append("low")
    elif coverage_state == _PARTIAL:
        caps.append("medium")
    return min(caps, key=lambda cap: _CONFIDENCE_ORDER.get(cap, 0))


def _research_next_steps(
    *,
    missing_critical: Sequence[str],
    families_missing: Sequence[str],
    stale_inputs: Sequence[Mapping[str, Any]],
    conflicting_inputs: Sequence[Mapping[str, Any]],
) -> list[str]:
    steps: list[str] = []
    if missing_critical:
        steps.append("Add critical evidence inputs before using this matrix for research gating.")
    if families_missing:
        steps.append("Fill missing evidence families before expanding research conclusions.")
    if stale_inputs:
        steps.append("Refresh stale evidence surfaces before comparing research scenarios.")
    if conflicting_inputs:
        steps.append("Reconcile contradictory evidence surfaces before summarizing a research view.")
    return steps or ["Continue monitoring coverage freshness across the included surfaces."]


def _issue_rows(summaries: Sequence[Mapping[str, Any]], key: str) -> list[dict[str, Any]]:
    return [
        {"surface": str(item["surface"]), "items": list(item[key])}
        for item in summaries
        if item[key]
    ]


def _subject(packet: Mapping[str, Any]) -> dict[str, str]:
    subject = packet.get("subject")
    if isinstance(subject, Mapping):
        safe_subject = {
            key: _safe_text(value)
            for key, value in subject.items()
            if key in {"symbol", "market", "name", "assetClass", "scope"} and _safe_text(value)
        }
        if safe_subject:
            return safe_subject

    for key in ("symbolEvidenceReadiness", "peerCorrelationSnapshot"):
        value = packet.get(key)
        if isinstance(value, Mapping):
            symbol = _safe_text(_first_present(value, "symbol", "ticker"))
            if symbol:
                return {"symbol": symbol}
    return {"scope": "cross_surface_research"}


def _lookup(packet: Mapping[str, Any], spec: Mapping[str, Any]) -> tuple[Any, bool]:
    for key in spec["aliases"]:
        if key in packet:
            return packet[key], True
    return None, False


def _provenance_entries(value: Any) -> list[Any]:
    if isinstance(value, Mapping):
        nested = value.get("evidenceProvenanceLedger")
        return list(nested) if _is_sequence(nested) else []
    return list(value) if _is_sequence(value) else []


def _missing_from_compare(value: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    missing_by_symbol = value.get("missingEvidenceBySymbol")
    if isinstance(missing_by_symbol, Mapping):
        for symbol, entries in missing_by_symbol.items():
            if _non_empty(entries):
                missing.append(f"{_safe_text(symbol) or 'symbol'} comparison evidence")
    return _dedupe(missing)


def _state(value: Any) -> str:
    text = _text(value).lower()
    if not text:
        return _COMPLETE
    return _STATE_ALIASES.get(text, _PARTIAL)


def _confidence(value: Any) -> str:
    if isinstance(value, Mapping):
        numeric = _to_float(value.get("value"))
        if numeric is not None:
            return "high" if numeric >= 80 else "medium" if numeric >= 50 else "low"
        return _confidence(_first_present(value, "cap", "state", "label"))
    text = _text(value).lower()
    return text if text in _CONFIDENCE_ORDER else "high"


def _min_confidence(left: str, right: str) -> str:
    return min((left, right), key=lambda cap: _CONFIDENCE_ORDER.get(cap, 0))


def _has_unsafe_material(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if (_has_unsafe_key(key) and _non_empty(nested)) or _has_unsafe_material(nested):
                return True
        return False
    if _is_sequence(value):
        return any(_has_unsafe_material(item) for item in value)
    return _has_unsafe_text(value)


def _has_unsafe_key(value: Any) -> bool:
    lowered = _text(value).lower().replace("-", "_")
    return any(marker in lowered for marker in _UNSAFE_KEY_MARKERS)


def _has_unsafe_text(value: Any) -> bool:
    lowered = _text(value).lower()
    return bool(lowered) and any(marker in lowered for marker in _UNSAFE_TEXT_MARKERS)


def _has_advice_text(value: Any) -> bool:
    lowered = _text(value).lower()
    if not lowered:
        return False
    tokens = {"".join(char for char in token if char.isalnum()) for token in lowered.replace("-", " ").split()}
    return (
        bool(_ADVICE_WORD_MARKERS.intersection(tokens))
        or any(marker in lowered for marker in _ADVICE_PHRASE_MARKERS)
        or any(marker in lowered for marker in _ADVICE_CJK_MARKERS)
    )


def _safe_list(value: Any) -> list[str]:
    result: list[str] = []
    for item in _as_sequence(value):
        text = _safe_text(item)
        if text:
            result.append(text)
    return _dedupe(result)


def _safe_text(value: Any) -> str:
    if isinstance(value, Mapping):
        value = _first_present(value, "label", "message", "input", "kind", "status")
    if _is_sequence(value):
        return ""
    text = " ".join(_text(value).split())
    if not text:
        return ""
    if _has_unsafe_text(text) or _has_advice_text(text):
        return "internal detail"
    return text[:120]


def _first_present(entry: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in entry and entry[key] not in (None, ""):
            return entry[key]
    return None


def _as_sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes, bytearray)):
        return [value]
    if isinstance(value, Mapping):
        return [value]
    return list(value) if _is_sequence(value) else [value]


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _is_empty_sequence(value: Any) -> bool:
    return _is_sequence(value) and not value


def _non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, Mapping):
        return bool(value)
    if _is_sequence(value):
        return bool(value)
    return bool(value)


def _dedupe(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _to_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result in {float("inf"), float("-inf")}:
        return None
    return result


__all__ = [
    "DATA_COVERAGE_QUALITY_MATRIX_CONTRACT_VERSION",
    "DATA_COVERAGE_QUALITY_MATRIX_NO_ADVICE_DISCLOSURE",
    "build_data_coverage_quality_matrix",
]
