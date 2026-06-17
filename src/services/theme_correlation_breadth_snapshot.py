# -*- coding: utf-8 -*-
"""Bounded theme correlation/breadth snapshot derived from existing theme fields."""

from __future__ import annotations

from typing import Any, Mapping


THEME_CORRELATION_BREADTH_SNAPSHOT_VERSION = "theme_correlation_breadth_snapshot_v1"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_number(value: Any) -> float | None:
    number = _number(value)
    return round(number, 1) if number is not None else None


def _string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    result: list[str] = []
    for item in value:
        text = _string(item)
        if text:
            result.append(text)
    return result


def _top_member_symbols(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value[:5]:
        if isinstance(item, Mapping):
            symbol = _string(item.get("symbol") or item.get("name"))
        else:
            symbol = _string(item)
        if symbol:
            result.append(symbol)
    return result


def _state_from_thresholds(value: float | None, *, broad: float, mixed: float) -> str:
    if value is None:
        return "missing"
    if value >= broad:
        return "broad"
    if value >= mixed:
        return "mixed"
    return "thin"


def _correlation_state(same_direction: float | None, above_vwap: float | None) -> str:
    values = [value for value in (same_direction, above_vwap) if value is not None]
    if not values:
        return "missing"
    if same_direction is not None and above_vwap is not None and min(same_direction, above_vwap) >= 70:
        return "aligned"
    if max(values) >= 50:
        return "mixed"
    return "weak"


def _leadership_state(concentration: float | None) -> str:
    if concentration is None:
        return "unknown"
    if concentration >= 60:
        return "concentrated"
    if concentration >= 45:
        return "moderate"
    return "balanced"


def _stale_inputs(theme: Mapping[str, Any], persistence: Mapping[str, Any]) -> list[str]:
    stale: list[str] = []
    freshness = str(theme.get("freshness") or "").strip().lower()
    if bool(theme.get("isFallback")) or freshness == "fallback":
        stale.append("fallback_source")
    if bool(theme.get("isStale")) or freshness == "stale":
        stale.append("stale_source")
    if bool(theme.get("isPartial")) or freshness == "partial":
        stale.append("partial_source")
    for window in _string_list(persistence.get("staleOrFallbackWindows")):
        stale.append(f"fallback_window:{window}")
    return list(dict.fromkeys(stale))


def _missing_inputs(
    theme: Mapping[str, Any],
    *,
    percent_up: float | None,
    outperform: float | None,
    same_direction: float | None,
    above_vwap: float | None,
    concentration: float | None,
) -> list[str]:
    missing: list[str] = []
    if percent_up is None:
        missing.append("breadth_percent_up")
    if outperform is None:
        missing.append("breadth_percent_outperforming_benchmark")
    if same_direction is None:
        missing.append("correlation_same_direction_percent")
    if above_vwap is None:
        missing.append("correlation_above_vwap_percent")
    if concentration is None:
        missing.append("leadership_concentration_percent")
    if bool(theme.get("staticThemeOnly")) or str(theme.get("source") or "") == "local_taxonomy":
        missing.append("market_runtime_evidence")
    return missing


def _participation_state(
    *,
    missing: list[str],
    breadth_state: str,
    correlation_state: str,
    leadership_state: str,
    percent_up: float | None,
    outperform: float | None,
) -> str:
    if "market_runtime_evidence" in missing:
        return "insufficient_evidence"
    if leadership_state == "concentrated" and (breadth_state == "thin" or (percent_up or 0.0) < 60 or (outperform or 0.0) < 50):
        return "leader_concentrated"
    if missing:
        return "insufficient_evidence"
    if breadth_state == "broad" and correlation_state == "aligned" and leadership_state in {"balanced", "moderate"}:
        return "broad_group"
    return "mixed_or_partial"


def _research_next_steps(participation_state: str, missing: list[str], stale: list[str]) -> list[str]:
    if participation_state == "broad_group":
        return ["Watch whether broad participation persists across the next observation window."]
    if participation_state == "leader_concentrated":
        return ["Compare top-member moves with the rest of the theme before drawing a group-level conclusion."]
    if missing:
        return ["Collect member-level breadth and synchronization evidence before classifying participation."]
    if stale:
        return ["Refresh stale theme inputs before treating the snapshot as current."]
    return ["Review whether breadth, synchronization, and leadership remain consistent in the next snapshot."]


def build_theme_correlation_breadth_snapshot(theme: Mapping[str, Any]) -> dict[str, Any]:
    """Return a bounded observation snapshot from an existing rotation theme payload."""

    theme_map = _mapping(theme)
    breadth = _mapping(theme_map.get("breadth"))
    synchronization = _mapping(theme_map.get("synchronization"))
    leadership = _mapping(theme_map.get("leadership"))
    persistence = _mapping(theme_map.get("persistenceEvidence"))

    percent_up = _round_number(breadth.get("percentUp"))
    outperform = _round_number(breadth.get("percentOutperformingBenchmark"))
    coverage = _round_number(breadth.get("coveragePercent"))
    observed_members = _number(breadth.get("observedMembers"))
    configured_members = _number(breadth.get("configuredMembers"))
    same_direction = _round_number(synchronization.get("sameDirectionPercent"))
    above_vwap = _round_number(synchronization.get("aboveVwapPercent"))
    persistence_percent = _round_number(synchronization.get("persistencePercent"))
    concentration = _round_number(leadership.get("leadershipConcentrationPercent"))
    broad_participation = _round_number(leadership.get("broadParticipationPercent"))

    stale = _stale_inputs(theme_map, persistence)
    missing = _missing_inputs(
        theme_map,
        percent_up=percent_up,
        outperform=outperform,
        same_direction=same_direction,
        above_vwap=above_vwap,
        concentration=concentration,
    )
    breadth_state = _state_from_thresholds(outperform, broad=60.0, mixed=45.0)
    corr_state = _correlation_state(same_direction, above_vwap)
    lead_state = _leadership_state(concentration)
    participation_state = _participation_state(
        missing=missing,
        breadth_state=breadth_state,
        correlation_state=corr_state,
        leadership_state=lead_state,
        percent_up=percent_up,
        outperform=outperform,
    )

    return {
        "contractVersion": THEME_CORRELATION_BREADTH_SNAPSHOT_VERSION,
        "theme": {
            "id": _string(theme_map.get("id")),
            "name": _string(theme_map.get("name")),
            "market": _string(theme_map.get("market")),
        },
        "participationState": participation_state,
        "leadershipConcentration": {
            "state": lead_state,
            "percent": concentration,
            "broadParticipationPercent": broad_participation,
            "topMembers": _top_member_symbols(leadership.get("topMembers")),
        },
        "correlationEvidence": {
            "state": corr_state,
            "sameDirectionPercent": same_direction,
            "aboveVwapPercent": above_vwap,
            "persistencePercent": persistence_percent,
        },
        "breadthEvidence": {
            "state": breadth_state,
            "observedMembers": int(observed_members) if observed_members is not None else None,
            "configuredMembers": int(configured_members) if configured_members is not None else None,
            "coveragePercent": coverage,
            "percentUp": percent_up,
            "percentOutperformingBenchmark": outperform,
        },
        "staleInputs": stale,
        "missingInputs": missing,
        "observationBoundary": {
            "scope": "existing_theme_fields",
            "rankingImpact": "none",
            "dataMutation": "none",
            "dataFetches": "none",
        },
        "researchNextSteps": _research_next_steps(participation_state, missing, stale),
    }


__all__ = [
    "THEME_CORRELATION_BREADTH_SNAPSHOT_VERSION",
    "build_theme_correlation_breadth_snapshot",
]
