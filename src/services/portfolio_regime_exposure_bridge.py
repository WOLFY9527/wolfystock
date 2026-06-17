# -*- coding: utf-8 -*-
"""Pure portfolio exposure bridge for existing regime and theme evidence."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Sequence


PORTFOLIO_REGIME_EXPOSURE_BRIDGE_VERSION = "portfolio_regime_exposure_bridge_v1"
NO_ADVICE_DISCLOSURE = (
    "Observation-only portfolio/regime research context; not personalized financial advice "
    "and not an instruction."
)

_RISK_SUPPORTIVE_REGIMES = {
    "risk_on_liquidity_expansion",
    "goldilocks_soft_landing",
}
_RISK_DEFENSIVE_REGIMES = {
    "risk_off_deleveraging",
    "rates_shock_duration_pressure",
    "dollar_squeeze",
    "credit_or_funding_stress",
    "term_premium_or_inflation_scare",
}
_FRESHNESS_STALE = {"stale", "fallback", "partial", "delayed", "cached", "unavailable"}
_BREADTH_WEAK_STATES = {"thin", "weak", "missing"}
_PARTICIPATION_WEAK_STATES = {"leader_concentrated", "insufficient_evidence"}
_LEADERSHIP_CONCENTRATED_STATES = {"concentrated"}
_UNSAFE_TEXT_PATTERN = re.compile(
    r"\b(?:b"
    r"uy|s"
    r"ell|h"
    r"old|recommend(?:ation|ed)?|target(?: price)?|stop loss|take profit|"
    r"position sizing|rebalance|allocation instruction|provider(?:diagnostics|trace|payload|runtime)?|"
    r"debug|runtime|cache(?:[_ -]?(?:key|hit|miss|state|payload))?|source"
    r"ref(?:id|ids)?|reason"
    r"codes?|request"
    r"id|trace(?:id)?|raw(?:[_ -]?(?:json|payload|diagnostics|result|response|body))?|payload)\b",
    re.IGNORECASE,
)


def build_portfolio_regime_exposure_bridge(input_packet: Mapping[str, Any]) -> dict:
    """Bridge already-computed portfolio, regime, and theme evidence.

    This function is intentionally pure: it only reads the supplied mapping,
    never calls providers, never mutates accounting state, and never changes
    portfolio inputs.
    """

    packet = _mapping(input_packet)
    portfolio = _first_mapping(
        packet,
        "portfolioExposureResearchContext",
        "exposureResearchContext",
        "portfolio_exposure_research_context",
    )
    regime = _first_mapping(packet, "marketRegimeSynthesis", "regimeSummary", "market_regime_synthesis")
    theme = _first_mapping(
        packet,
        "themeCorrelationBreadthSnapshot",
        "theme_correlation_breadth_snapshot",
    )

    dominant = _dominant_exposure_context(portfolio, theme)
    portfolio_scope = _portfolio_scope(portfolio, dominant)
    regime_evidence = _regime_alignment_evidence(regime, dominant, theme)
    theme_evidence = _theme_breadth_exposure_evidence(theme, dominant)
    concentration = _concentration_evidence(portfolio, dominant, theme_evidence)
    stale_inputs = _stale_inputs(portfolio=portfolio, regime=regime, theme=theme)
    missing_inputs = _missing_inputs(portfolio=portfolio, regime=regime, theme=theme)

    bridge_state = _bridge_state(
        portfolio=portfolio,
        regime=regime,
        theme=theme,
        regime_evidence=regime_evidence,
        theme_evidence=theme_evidence,
        concentration=concentration,
        missing_inputs=missing_inputs,
    )
    confidence_cap = _confidence_cap(
        bridge_state=bridge_state,
        regime=regime,
        theme_evidence=theme_evidence,
        concentration=concentration,
        stale_inputs=stale_inputs,
        missing_inputs=missing_inputs,
    )

    return {
        "contractVersion": PORTFOLIO_REGIME_EXPOSURE_BRIDGE_VERSION,
        "portfolioScope": portfolio_scope,
        "bridgeState": bridge_state,
        "dominantExposureContext": dominant,
        "regimeAlignmentEvidence": regime_evidence,
        "themeBreadthExposureEvidence": theme_evidence,
        "concentrationEvidence": concentration,
        "staleInputs": stale_inputs,
        "missingInputs": missing_inputs,
        "confidenceCap": confidence_cap,
        "observationBoundary": {
            "observationOnly": True,
            "decisionGrade": False,
            "externalCalls": "none",
            "networkCalls": "none",
            "llmCalls": "none",
            "dataFetches": "none",
            "dataMutation": "none",
            "portfolioAccountingMutation": False,
            "consumerActionBoundary": "no_advice",
        },
        "researchNextSteps": _research_next_steps(
            bridge_state=bridge_state,
            stale_inputs=stale_inputs,
            missing_inputs=missing_inputs,
            theme_evidence=theme_evidence,
            concentration=concentration,
            packet=packet,
        ),
        "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _first_mapping(packet: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = packet.get(key)
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _safe_text(value: Any, *, fallback: str | None = None) -> str | None:
    text = _text(value)
    if not text:
        return fallback
    if _UNSAFE_TEXT_PATTERN.search(text):
        return fallback
    if text[:1] in {"{", "["} and text[-1:] in {"}", "]"}:
        return fallback
    return text


def _safe_key(value: Any, *, fallback: str | None = None) -> str | None:
    text = _safe_text(value, fallback=fallback)
    if text is None:
        return None
    return text.strip().lower().replace(" ", "_").replace("-", "_")


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _unit(value: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    if number > 1:
        number = number / 100
    return round(max(0.0, min(1.0, number)), 3)


def _pct(value: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return round(max(0.0, min(100.0, number)), 1)


def _dedupe(items: Iterable[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for item in items:
        marker = repr(item)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


def _dominant_exposure_context(portfolio: Mapping[str, Any], theme: Mapping[str, Any]) -> dict[str, Any]:
    dominant = _mapping(portfolio.get("dominantExposure"))
    theme_info = _mapping(theme.get("theme"))
    exposure_type = _safe_key(dominant.get("type"), fallback="unknown") or "unknown"
    theme_id = _safe_key(
        dominant.get("themeId")
        or dominant.get("theme_id")
        or dominant.get("theme")
        or dominant.get("sectorTheme")
        or theme_info.get("id")
    )
    label = _safe_text(
        dominant.get("label")
        or dominant.get("name")
        or theme_info.get("name")
        or dominant.get("symbol")
        or dominant.get("market"),
        fallback="Dominant exposure",
    )
    return {
        "type": exposure_type,
        "label": label,
        "symbol": _safe_text(dominant.get("symbol")),
        "themeId": theme_id,
        "market": _safe_text(dominant.get("market") or theme_info.get("market")),
        "currency": _safe_text(dominant.get("currency")),
        "weightPct": _pct(dominant.get("weightPct") or dominant.get("weight_pct")),
        "source": _safe_key(dominant.get("source"), fallback="existing_portfolio_context"),
    }


def _portfolio_scope(portfolio: Mapping[str, Any], dominant: Mapping[str, Any]) -> dict[str, Any]:
    has_context = bool(portfolio)
    market_context = _mapping(portfolio.get("marketContext"))
    largest_market = _mapping(market_context.get("largestMarket"))
    return {
        "hasPortfolioContext": has_context,
        "dominantExposureType": dominant.get("type") if has_context else "missing",
        "dominantExposureLabel": dominant.get("label") if has_context else None,
        "dominantThemeId": dominant.get("themeId") if has_context else None,
        "dominantMarket": dominant.get("market") or _safe_text(largest_market.get("market")),
        "dominantWeightPct": dominant.get("weightPct"),
        "marketContextState": _safe_key(market_context.get("state"), fallback="missing") if has_context else "missing",
    }


def _regime_alignment_evidence(
    regime: Mapping[str, Any],
    dominant: Mapping[str, Any],
    theme: Mapping[str, Any],
) -> dict[str, Any]:
    if not regime:
        return {
            "state": "insufficient_evidence",
            "primaryRegime": None,
            "regimePosture": "missing",
            "confidence": None,
            "supportiveEvidenceCount": 0,
            "contradictoryEvidenceCount": 0,
            "summary": "Market regime synthesis is missing.",
        }

    primary = _safe_key(regime.get("primaryRegime"), fallback="data_insufficient") or "data_insufficient"
    posture = _safe_key(regime.get("regimePosture")) or _infer_regime_posture(primary)
    confidence = _unit(regime.get("confidence"))
    theme_state = _theme_state(theme)

    if posture == "data_insufficient" or primary == "data_insufficient":
        state = "insufficient_evidence"
    elif posture == "risk_supportive" and theme_state == "broad":
        state = "aligned"
    elif posture == "risk_supportive" and theme_state == "weak":
        state = "diverging"
    elif posture == "risk_defensive" and _exposure_weight(dominant) >= 60:
        state = "diverging"
    else:
        state = "mixed"

    return {
        "state": state,
        "primaryRegime": primary,
        "regimePosture": posture,
        "confidence": confidence,
        "confidenceLabel": _safe_key(regime.get("confidenceLabel")),
        "supportiveEvidenceCount": len(_sequence(regime.get("supportiveEvidence") or regime.get("topDrivers"))),
        "contradictoryEvidenceCount": len(_sequence(regime.get("contradictoryEvidence") or regime.get("counterEvidence"))),
        "freshness": _safe_key(regime.get("freshness"), fallback="unknown"),
        "summary": _regime_summary(state, posture, theme_state),
    }


def _theme_breadth_exposure_evidence(theme: Mapping[str, Any], dominant: Mapping[str, Any]) -> dict[str, Any]:
    if not theme:
        return {
            "state": "insufficient_evidence",
            "themeId": dominant.get("themeId"),
            "participationState": "missing",
            "breadthState": "missing",
            "correlationState": "missing",
            "leadershipState": "unknown",
            "summary": "Theme breadth/correlation snapshot is missing.",
        }

    theme_info = _mapping(theme.get("theme"))
    breadth = _mapping(theme.get("breadthEvidence"))
    correlation = _mapping(theme.get("correlationEvidence"))
    leadership = _mapping(theme.get("leadershipConcentration"))
    participation = _safe_key(theme.get("participationState"), fallback="insufficient_evidence") or "insufficient_evidence"
    breadth_state = _safe_key(breadth.get("state"), fallback="missing") or "missing"
    correlation_state = _safe_key(correlation.get("state"), fallback="missing") or "missing"
    leadership_state = _safe_key(leadership.get("state"), fallback="unknown") or "unknown"

    if participation == "broad_group" and breadth_state in {"broad", "mixed"} and correlation_state in {"aligned", "mixed"}:
        state = "aligned"
    elif (
        participation in _PARTICIPATION_WEAK_STATES
        or breadth_state in _BREADTH_WEAK_STATES
        or leadership_state in _LEADERSHIP_CONCENTRATED_STATES
    ):
        state = "diverging"
    else:
        state = "mixed"

    return {
        "state": state,
        "themeId": _safe_key(theme_info.get("id") or dominant.get("themeId")),
        "themeName": _safe_text(theme_info.get("name") or dominant.get("label"), fallback="Theme exposure"),
        "participationState": participation,
        "breadthState": breadth_state,
        "correlationState": correlation_state,
        "leadershipState": leadership_state,
        "percentUp": _pct(breadth.get("percentUp")),
        "percentOutperformingBenchmark": _pct(breadth.get("percentOutperformingBenchmark")),
        "leadershipConcentrationPercent": _pct(leadership.get("percent")),
        "summary": _theme_summary(state, participation, breadth_state, leadership_state),
    }


def _concentration_evidence(
    portfolio: Mapping[str, Any],
    dominant: Mapping[str, Any],
    theme_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    concentration = _mapping(portfolio.get("concentrationContext"))
    top_weight = _pct(concentration.get("topWeightPct") or concentration.get("top_weight_pct"))
    dominant_weight = _exposure_weight(dominant)
    effective_weight = top_weight if top_weight is not None else dominant_weight
    concentration_state = _safe_key(concentration.get("state"), fallback="missing") or "missing"
    alert = bool(concentration.get("alert"))

    if concentration_state == "missing" and effective_weight == 0:
        state = "missing"
    elif alert or concentration_state == "elevated" or effective_weight >= 60:
        state = "concentrated"
    elif theme_evidence.get("leadershipState") == "concentrated":
        state = "concentrated"
    else:
        state = "observable"

    return {
        "state": state,
        "portfolioConcentrationState": concentration_state,
        "topWeightPct": top_weight,
        "dominantWeightPct": dominant_weight or None,
        "alert": alert,
        "themeLeadershipState": theme_evidence.get("leadershipState"),
        "themeLeadershipConcentrationPercent": theme_evidence.get("leadershipConcentrationPercent"),
    }


def _stale_inputs(*, portfolio: Mapping[str, Any], regime: Mapping[str, Any], theme: Mapping[str, Any]) -> list[dict[str, str]]:
    stale: list[dict[str, str]] = []
    for item in _sequence(portfolio.get("staleInputs")):
        normalized = _normalize_stale_item(item, default_input="portfolio_context")
        if normalized:
            stale.append(normalized)

    freshness = _safe_key(regime.get("freshness"))
    if regime and freshness in _FRESHNESS_STALE:
        stale.append(
            {
                "input": "market_regime_synthesis",
                "status": freshness or "stale",
                "reason": "freshness_limited",
            }
        )

    for item in _sequence(theme.get("staleInputs")):
        text = _safe_key(item, fallback="stale_source")
        if text:
            stale.append(
                {
                    "input": "theme_correlation_breadth",
                    "status": "stale",
                    "reason": text,
                }
            )
    return _dedupe(stale)


def _normalize_stale_item(item: Any, *, default_input: str) -> dict[str, str] | None:
    if isinstance(item, Mapping):
        input_name = _safe_key(item.get("input") or item.get("section"), fallback=default_input)
        status = _safe_key(item.get("status"), fallback="limited")
        reason = _safe_key(item.get("reason"), fallback="evidence_limited")
    else:
        input_name = default_input
        status = "limited"
        reason = _safe_key(item, fallback="evidence_limited")
    if not input_name:
        return None
    return {"input": input_name, "status": status or "limited", "reason": reason or "evidence_limited"}


def _missing_inputs(*, portfolio: Mapping[str, Any], regime: Mapping[str, Any], theme: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    if not portfolio:
        missing.append("portfolioExposureResearchContext")
    if not regime:
        missing.append("marketRegimeSynthesis")
    if not theme:
        missing.append("themeCorrelationBreadthSnapshot")

    for item in _sequence(portfolio.get("evidenceGaps")):
        key = _safe_key(item)
        if key:
            missing.append(f"portfolio:{key}")
    for item in _sequence(regime.get("missingEvidence") or regime.get("dataGaps")):
        key = _missing_evidence_key(item)
        if key:
            missing.append(f"regime:{key}")
    for item in _sequence(theme.get("missingInputs")):
        key = _safe_key(item)
        if key:
            missing.append(f"theme:{key}")
    return _dedupe(missing)


def _missing_evidence_key(item: Any) -> str | None:
    if isinstance(item, Mapping):
        return _safe_key(item.get("key") or item.get("family") or item.get("pillar") or item.get("label"))
    return _safe_key(item)


def _bridge_state(
    *,
    portfolio: Mapping[str, Any],
    regime: Mapping[str, Any],
    theme: Mapping[str, Any],
    regime_evidence: Mapping[str, Any],
    theme_evidence: Mapping[str, Any],
    concentration: Mapping[str, Any],
    missing_inputs: Sequence[str],
) -> str:
    if not portfolio or not regime or not theme:
        return "insufficient_evidence"
    if any(item.startswith("theme:market_runtime_evidence") for item in missing_inputs):
        return "insufficient_evidence"
    if regime_evidence.get("state") == "insufficient_evidence" or theme_evidence.get("state") == "insufficient_evidence":
        return "insufficient_evidence"
    if concentration.get("state") == "concentrated":
        return "concentrated"
    if regime_evidence.get("state") == "diverging" or theme_evidence.get("state") == "diverging":
        return "diverging"
    if regime_evidence.get("state") == "aligned" and theme_evidence.get("state") == "aligned":
        return "aligned"
    return "diverging" if regime_evidence.get("state") == "diverging" else "insufficient_evidence"


def _confidence_cap(
    *,
    bridge_state: str,
    regime: Mapping[str, Any],
    theme_evidence: Mapping[str, Any],
    concentration: Mapping[str, Any],
    stale_inputs: Sequence[Mapping[str, str]],
    missing_inputs: Sequence[str],
) -> dict[str, Any]:
    regime_cap = _mapping(regime.get("confidenceCap"))
    cap = _unit(regime_cap.get("value") if regime_cap else regime.get("confidence"))
    if cap is None:
        cap = 0.75
    reasons: list[str] = []
    for reason in _sequence(regime_cap.get("reasons")):
        safe = _safe_key(reason)
        if safe:
            reasons.append(safe)

    if bridge_state == "insufficient_evidence" or missing_inputs:
        cap = min(cap, 0.35)
        reasons.append("missing_inputs")
    if stale_inputs:
        cap = min(cap, 0.4)
        reasons.append("stale_inputs")
    if theme_evidence.get("breadthState") in _BREADTH_WEAK_STATES:
        cap = min(cap, 0.55)
        reasons.append("thin_theme_participation")
    if concentration.get("state") == "concentrated":
        cap = min(cap, 0.58)
        reasons.append("concentration_elevated")
    if bridge_state == "diverging":
        cap = min(cap, 0.5)
        reasons.append("regime_exposure_conflict")

    cap = round(max(0.0, min(1.0, cap)), 3)
    return {
        "value": cap,
        "label": _confidence_label(cap),
        "reasons": _dedupe(reasons or ["bounded_research_synthesis"]),
    }


def _research_next_steps(
    *,
    bridge_state: str,
    stale_inputs: Sequence[Mapping[str, str]],
    missing_inputs: Sequence[str],
    theme_evidence: Mapping[str, Any],
    concentration: Mapping[str, Any],
    packet: Mapping[str, Any],
) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    if missing_inputs:
        steps.append(
            {
                "key": "fill_missing_inputs",
                "label": "Fill missing research inputs",
                "detail": "Collect portfolio, regime, and theme breadth context before raising confidence.",
            }
        )
    if stale_inputs:
        steps.append(
            {
                "key": "refresh_stale_inputs",
                "label": "Refresh stale evidence",
                "detail": "Re-check stale portfolio, regime, or theme inputs before expanding conclusions.",
            }
        )
    if theme_evidence.get("state") == "diverging":
        steps.append(
            {
                "key": "verify_theme_participation",
                "label": "Verify theme participation",
                "detail": "Compare member-level breadth and synchronization before treating the theme as broad.",
            }
        )
    if concentration.get("state") == "concentrated":
        steps.append(
            {
                "key": "review_concentration_context",
                "label": "Review concentration context",
                "detail": "Compare dominant exposure with regime and theme breadth evidence.",
            }
        )
    if bridge_state == "diverging":
        steps.append(
            {
                "key": "review_regime_conflict",
                "label": "Review regime conflict",
                "detail": "Compare conflicting regime and theme evidence before increasing confidence.",
            }
        )
    for note in _safe_exposure_notes(packet)[:2]:
        steps.append(
            {
                "key": "review_exposure_note",
                "label": "Review exposure note",
                "detail": note,
            }
        )
    if not steps:
        steps.append(
            {
                "key": "monitor_persistence",
                "label": "Monitor persistence",
                "detail": "Look for repeated confirmation across regime, breadth, and portfolio context.",
            }
        )
    return _dedupe(steps)


def _safe_exposure_notes(packet: Mapping[str, Any]) -> list[str]:
    notes: list[str] = []
    for key in (
        "watchlistExposureNotes",
        "researchQueueExposureNotes",
        "exposureNotes",
        "watchlistResearchQueueExposureNotes",
    ):
        for item in _sequence(packet.get(key)):
            if isinstance(item, Mapping):
                text = _safe_text(item.get("summary") or item.get("note") or item.get("researchNextStep"))
            else:
                text = _safe_text(item)
            if text:
                notes.append(text)
    return _dedupe(notes)


def _infer_regime_posture(primary: str) -> str:
    if primary in _RISK_SUPPORTIVE_REGIMES:
        return "risk_supportive"
    if primary in _RISK_DEFENSIVE_REGIMES:
        return "risk_defensive"
    if primary == "data_insufficient":
        return "data_insufficient"
    return "mixed_or_transition"


def _theme_state(theme: Mapping[str, Any]) -> str:
    if not theme:
        return "missing"
    participation = _safe_key(theme.get("participationState"), fallback="insufficient_evidence")
    breadth = _mapping(theme.get("breadthEvidence"))
    breadth_state = _safe_key(breadth.get("state"), fallback="missing")
    leadership = _mapping(theme.get("leadershipConcentration"))
    leadership_state = _safe_key(leadership.get("state"), fallback="unknown")
    if participation == "broad_group" and breadth_state in {"broad", "mixed"}:
        return "broad"
    if participation in _PARTICIPATION_WEAK_STATES or breadth_state in _BREADTH_WEAK_STATES:
        return "weak"
    if leadership_state in _LEADERSHIP_CONCENTRATED_STATES:
        return "weak"
    return "mixed"


def _exposure_weight(dominant: Mapping[str, Any]) -> float:
    return float(dominant.get("weightPct") or 0.0)


def _confidence_label(value: float) -> str:
    if value <= 0.35:
        return "insufficient"
    if value < 0.5:
        return "low"
    if value < 0.75:
        return "medium"
    return "high"


def _regime_summary(state: str, posture: str, theme_state: str) -> str:
    if state == "aligned":
        return "Regime posture and theme participation point in the same research direction."
    if state == "diverging":
        return "Portfolio exposure needs review because regime posture and theme participation do not confirm each other."
    if state == "insufficient_evidence":
        return "Regime evidence is insufficient for portfolio exposure bridging."
    return f"Regime posture is {posture}; theme participation is {theme_state}."


def _theme_summary(state: str, participation: str, breadth: str, leadership: str) -> str:
    if state == "aligned":
        return "Theme evidence shows broad participation around the dominant exposure context."
    if state == "diverging":
        return "Theme evidence is narrow or leadership-concentrated relative to the exposure context."
    if state == "insufficient_evidence":
        return "Theme breadth and correlation inputs are insufficient."
    return f"Theme participation is {participation}; breadth is {breadth}; leadership is {leadership}."


__all__ = [
    "NO_ADVICE_DISCLOSURE",
    "PORTFOLIO_REGIME_EXPOSURE_BRIDGE_VERSION",
    "build_portfolio_regime_exposure_bridge",
]
