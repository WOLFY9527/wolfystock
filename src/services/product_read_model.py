# -*- coding: utf-8 -*-
"""Product-facing read-model projections shared across research surfaces.

This module is intentionally pure and read-only. It consumes already-built
service contracts and projects them into a bounded consumer-facing vocabulary
without provider calls, storage writes, cache writes, or backtest execution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any


PRODUCT_READ_MODEL_CONTRACT_VERSION = "product_read_model_v1"

PRODUCT_READ_STATES = {
    "available",
    "partial",
    "stale",
    "unavailable",
    "insufficient",
    "no_evidence",
    "degraded",
    "rejected",
    "pending",
}

_STATE_ALIASES = {
    "": "no_evidence",
    "all_available": "available",
    "available": "available",
    "cached": "partial",
    "current": "available",
    "delayed": "stale",
    "disabled": "unavailable",
    "engine_disabled": "unavailable",
    "error": "unavailable",
    "failed": "unavailable",
    "failed_closed": "rejected",
    "fresh": "available",
    "insufficient_coverage": "insufficient",
    "limited": "partial",
    "missing": "no_evidence",
    "missing_cache": "no_evidence",
    "not_configured": "unavailable",
    "not_integrated": "unavailable",
    "ok": "available",
    "provider_missing": "unavailable",
    "provider_unavailable": "unavailable",
    "ready": "available",
    "research_prototype": "degraded",
    "usable": "available",
    "unknown": "no_evidence",
}
_CRITICAL_BLOCKING_STATES = {"no_evidence", "rejected", "unavailable", "insufficient"}
_DEGRADED_STATES = {"partial", "stale", "degraded", "pending"}
_SEVERITY_ORDER = (
    "rejected",
    "unavailable",
    "no_evidence",
    "insufficient",
    "stale",
    "degraded",
    "partial",
    "pending",
    "available",
)


def normalize_product_state(value: Any) -> str:
    text = _safe_text(value).lower()
    normalized = text.replace("-", "_").replace(" ", "_")
    if normalized in PRODUCT_READ_STATES:
        return normalized
    return _STATE_ALIASES.get(normalized, "no_evidence")


def aggregate_product_readiness(
    *,
    surface: str,
    children: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    normalized_children: list[dict[str, Any]] = []
    critical_states: dict[str, str] = {}
    blocking_children: list[str] = []
    child_states: list[str] = []
    noncritical_degraded = False

    for child in children or []:
        name = _safe_text(child.get("name") or child.get("key") or child.get("surface") or "unknown")
        state = normalize_product_state(child.get("state") or child.get("status") or child.get("readinessState"))
        critical = bool(child.get("critical"))
        normalized = {
            "name": name,
            "state": state,
            "critical": critical,
        }
        normalized_children.append(normalized)
        child_states.append(state)
        if critical:
            critical_states[name] = state
            if state in _CRITICAL_BLOCKING_STATES:
                blocking_children.append(name)
        elif state != "available":
            noncritical_degraded = True

    if blocking_children:
        state = _most_severe(critical_states[name] for name in blocking_children)
    elif any(state in {"stale", "degraded", "partial", "pending"} for state in critical_states.values()):
        state = _most_severe(
            state for state in critical_states.values() if state in {"stale", "degraded", "partial", "pending"}
        )
    elif noncritical_degraded:
        state = "partial"
    elif normalized_children:
        state = "available"
    else:
        state = "no_evidence"

    return {
        "contractVersion": PRODUCT_READ_MODEL_CONTRACT_VERSION,
        "surface": surface,
        "state": state,
        "ready": state == "available" and not blocking_children,
        "children": normalized_children,
        "criticalChildStates": critical_states,
        "blockingChildren": blocking_children,
        "aggregationRules": {
            "criticalBlockingStates": sorted(_CRITICAL_BLOCKING_STATES),
            "degradedStates": sorted(_DEGRADED_STATES),
            "readyRequiresAllCriticalAvailable": True,
        },
    }


def product_read_model_from_historical_foundation(
    foundation: Any,
    *,
    symbol: str,
    market: str,
    interval: str = "1d",
    required_bars: int = 0,
    stale_after_days: int = 5,
    as_of: date | datetime | None = None,
) -> dict[str, Any]:
    coverage = dict(foundation.coverage_range(symbol=symbol, market=market, interval=interval))
    freshness = dict(foundation.freshness_summary(symbol=symbol, market=market, interval=interval))
    provenance = dict(foundation.provenance_summary(symbol=symbol, market=market, interval=interval))
    bar_count = _safe_int(coverage.get("barCount"))
    coverage_state = "available"
    if bar_count <= 0:
        coverage_state = "no_evidence"
    elif required_bars and bar_count < required_bars:
        coverage_state = "insufficient"

    freshness_state = _historical_freshness_state(
        freshness.get("freshnessState"),
        as_of=freshness.get("asOf"),
        stale_after_days=stale_after_days,
        reference_date=as_of,
    )
    quality_state = normalize_product_state(freshness.get("qualityState"))
    if str(freshness.get("qualityState") or "").lower() == "usable":
        quality_state = "available"

    aggregate = aggregate_product_readiness(
        surface="historical_market_data",
        children=[
            {"name": "coverage", "state": coverage_state, "critical": True},
            {"name": "freshness", "state": freshness_state, "critical": True},
            {"name": "quality", "state": quality_state, "critical": True},
        ],
    )
    product_state = aggregate["state"]
    if (
        product_state == "insufficient"
        and coverage_state == "insufficient"
        and bar_count > 0
        and freshness_state not in {"no_evidence", "unavailable", "rejected"}
        and quality_state not in {"no_evidence", "unavailable", "rejected"}
    ):
        product_state = "partial"
    return {
        "contractVersion": PRODUCT_READ_MODEL_CONTRACT_VERSION,
        "surface": "historical_market_data",
        "state": product_state,
        "ready": product_state == "available" and aggregate["ready"],
        "coverage": {
            "state": coverage_state,
            "start": coverage.get("start"),
            "end": coverage.get("end"),
            "barCount": bar_count,
            "requiredBars": max(0, int(required_bars or 0)),
        },
        "freshness": {
            "state": freshness_state,
            "asOf": freshness.get("asOf"),
            "coveredDateRange": dict(freshness.get("coveredDateRange") or {}),
        },
        "quality": {
            "state": quality_state,
            "sourceQualityState": freshness.get("qualityState"),
        },
        "provenance": {
            "sourceClass": "historical_market_data",
            "asOf": freshness.get("asOf") or provenance.get("asOf"),
            "freshness": freshness_state,
            "quality": freshness.get("qualityState") or provenance.get("qualityState") or "unknown",
            "market": provenance.get("market"),
            "canonicalSymbol": provenance.get("canonicalSymbol"),
            "sourceObservationRange": dict(provenance.get("sourceObservationRange") or {}),
        },
        "blockingChildren": aggregate["blockingChildren"],
    }


def build_structure_decision_product_read_model(payload: Mapping[str, Any]) -> dict[str, Any]:
    data_quality = _mapping(payload.get("dataQuality"))
    readiness = _mapping(payload.get("historicalOhlcvReadiness"))
    confidence_state = _mapping(payload.get("confidenceState"))
    missing_evidence = _sequence(payload.get("missingEvidence"))
    raw_readiness_state = readiness.get("overallState")
    readiness_state = normalize_product_state(raw_readiness_state)
    if readiness_state == "no_evidence" and _safe_text(raw_readiness_state).lower() == "blocked":
        readiness_state = "insufficient" if _safe_int(readiness.get("usableBars")) > 0 else "no_evidence"
    data_quality_state = normalize_product_state(data_quality.get("status"))
    if data_quality_state == "available" and _safe_int(data_quality.get("usableBars")) <= 0:
        data_quality_state = "no_evidence"
    critical_missing = bool(missing_evidence) or readiness_state in _CRITICAL_BLOCKING_STATES
    confidence_label = _safe_text(confidence_state.get("label") or payload.get("confidence") or "low").lower()
    source_limited = bool(confidence_state.get("sourceQualityLimited")) or data_quality_state in {"degraded", "stale", "partial"}
    thesis_blocked = bool(confidence_state.get("thesisBlocked")) or critical_missing
    strong_allowed = (
        not critical_missing
        and not source_limited
        and not thesis_blocked
        and confidence_label in {"high", "medium"}
        and readiness_state == "available"
        and data_quality_state == "available"
    )
    display_state = _safe_text(payload.get("structureState") or "lowConfidence")
    if not strong_allowed and display_state not in {"lowConfidence", "mixed"}:
        display_state = "withheld"
    aggregate = aggregate_product_readiness(
        surface="Structure Decision",
        children=[
            {"name": "historical_coverage", "state": readiness_state, "critical": True},
            {"name": "data_quality", "state": data_quality_state, "critical": True},
            {"name": "confidence", "state": "available" if confidence_label in {"high", "medium"} else "insufficient", "critical": True},
        ],
    )
    state = "no_evidence" if critical_missing and data_quality_state in {"no_evidence", "unavailable"} else aggregate["state"]
    return {
        "contractVersion": PRODUCT_READ_MODEL_CONTRACT_VERSION,
        "surface": "Structure Decision",
        "state": state,
        "ready": False if state != "available" else aggregate["ready"],
        "classification": {
            "observedState": _safe_text(payload.get("structureState") or "lowConfidence"),
            "displayState": display_state,
            "strongConclusionAllowed": strong_allowed,
        },
        "confidence": {
            "label": confidence_label if confidence_label in {"high", "medium", "low"} else "low",
            "state": confidence_state.get("status") or ("ready" if strong_allowed else "evidence incomplete"),
            "strongConclusionAllowed": strong_allowed,
            "reasons": list(confidence_state.get("reasons") or []),
        },
        "evidence": {
            "missingEvidenceCount": len(missing_evidence),
            "readinessState": readiness_state,
            "dataQualityState": data_quality_state,
        },
        "observationOnly": bool(payload.get("observationOnly", True)),
        "decisionGrade": bool(payload.get("decisionGrade", False)),
        "blockingChildren": aggregate["blockingChildren"],
    }


def build_backtest_readiness_read_model(readiness: Mapping[str, Any]) -> dict[str, Any]:
    status = normalize_product_state(readiness.get("status") or readiness.get("overallState"))
    explicit_executable = "executable" in readiness
    executable = bool(readiness.get("executable")) if explicit_executable else status == "available"
    required_bars = _safe_int(readiness.get("requiredBarCount") or readiness.get("requiredBars"))
    available_bars = _safe_int(readiness.get("availableBarCount") or readiness.get("usableBars"))
    missing_classes = [str(item) for item in readiness.get("missingDataClasses") or readiness.get("missingRequirements") or []]
    coverage_state = "available"
    if required_bars and available_bars < required_bars:
        coverage_state = "insufficient"
    if "historical_ohlcv" in missing_classes or "symbol_ohlcv" in missing_classes:
        coverage_state = "no_evidence"
    raw_freshness = readiness.get("freshness") or readiness.get("freshnessState")
    freshness_state = normalize_product_state(raw_freshness)
    if raw_freshness is None and status == "available":
        freshness_state = "available"
    quality_state = "available" if status == "available" and executable else "degraded"
    aggregate = aggregate_product_readiness(
        surface="Backtest readiness",
        children=[
            {"name": "coverage", "state": coverage_state, "critical": True},
            {"name": "freshness", "state": freshness_state, "critical": True},
            {"name": "quality", "state": quality_state, "critical": True},
        ],
    )
    state = status if status != "available" else aggregate["state"]
    return {
        "contractVersion": PRODUCT_READ_MODEL_CONTRACT_VERSION,
        "surface": "Backtest readiness",
        "state": state,
        "ready": executable and state == "available" and aggregate["ready"],
        "readOnly": True,
        "backtestExecuted": False,
        "coverage": {
            "state": coverage_state,
            "requiredBars": required_bars,
            "availableBars": available_bars,
        },
        "freshness": {
            "state": freshness_state,
            "asOf": _clean_public_text(readiness.get("asOf")),
        },
        "quality": {
            "state": quality_state,
            "missingDataClasses": missing_classes,
        },
        "provenance": {
            "sourceClass": "historical_market_data",
            "asOf": _clean_public_text(readiness.get("asOf")),
            "freshness": freshness_state,
            "quality": quality_state,
        },
        "blockingChildren": aggregate["blockingChildren"],
    }


def _historical_freshness_state(
    value: Any,
    *,
    as_of: Any,
    stale_after_days: int,
    reference_date: date | datetime | None,
) -> str:
    state = normalize_product_state(value)
    if state != "available":
        return state
    parsed_as_of = _parse_date(as_of)
    parsed_reference = reference_date.date() if isinstance(reference_date, datetime) else reference_date
    if parsed_as_of is not None and parsed_reference is not None:
        if (parsed_reference - parsed_as_of).days > max(0, int(stale_after_days or 0)):
            return "stale"
    return "available"


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _safe_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _most_severe(states: Sequence[str] | Any) -> str:
    observed = {normalize_product_state(state) for state in states}
    for candidate in _SEVERITY_ORDER:
        if candidate in observed:
            return candidate
    return "no_evidence"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_public_text(value: Any) -> str | None:
    text = _safe_text(value)
    if not text:
        return None
    lower = text.lower()
    forbidden = (
        "apikey",
        "api_key",
        "cachekey",
        "credential",
        "debug",
        "providername",
        "rawpayload",
        "requestid",
        "secret",
        "token",
        "traceback",
        "traceid",
    )
    if any(item in lower.replace("_", "") for item in forbidden):
        return None
    return text[:120]


__all__ = [
    "PRODUCT_READ_MODEL_CONTRACT_VERSION",
    "PRODUCT_READ_STATES",
    "aggregate_product_readiness",
    "build_backtest_readiness_read_model",
    "build_structure_decision_product_read_model",
    "normalize_product_state",
    "product_read_model_from_historical_foundation",
]
