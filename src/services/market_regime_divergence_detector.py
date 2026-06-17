# -*- coding: utf-8 -*-
"""Pure market regime divergence detection from caller-supplied evidence packets."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence


MARKET_REGIME_DIVERGENCE_CONTRACT_VERSION = "market_regime_divergence_detector_v1"

_POSITIVE_REGIMES = {
    "risk_on_liquidity_expansion",
    "goldilocks_soft_landing",
    "soft_landing",
    "risk_supportive",
    "supportive",
    "positive",
}
_LIQUIDITY_STRESS_STATES = {
    "contracting_liquidity",
    "rates_driven_tightening",
    "dollar_squeeze",
    "risk_deleveraging",
    "funding_stress",
    "credit_or_funding_stress",
    "stress",
    "stressed",
    "tightening",
}
_WEAK_STATES = {"weak", "thin", "narrow", "poor", "low", "stressed", "degraded", "insufficient"}
_STALE_STATES = {"stale", "fallback", "partial", "synthetic", "mock", "unavailable", "missing", "error"}
_MISSING_STATES = {"missing", "unavailable", "insufficient", "insufficient_evidence", "unknown"}

_CORE_INPUTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("marketRegimeSynthesis", ("marketRegimeSynthesis", "market_regime_synthesis", "regimeSynthesis")),
    (
        "themeCorrelationBreadthSnapshot",
        ("themeCorrelationBreadthSnapshot", "theme_correlation_breadth_snapshot", "themeBreadthSnapshot"),
    ),
    ("liquidityImpulseSynthesis", ("liquidityImpulseSynthesis", "liquidity_impulse_synthesis", "liquiditySynthesis")),
    ("scannerEvidencePacket", ("scannerEvidencePacket", "scanner_evidence_packet", "scannerEvidence")),
)

_FAMILY_NEXT_STEPS = {
    "index_vs_breadth": "Refresh market breadth confirmation before interpreting headline index strength as broad participation.",
    "regime_vs_liquidity": "Compare the headline regime with liquidity stress observations in the next evidence refresh.",
    "theme_leadership_vs_participation": "Review whether theme leaders are broadening into member-level participation.",
    "risk_posture_vs_scanner_quality": "Check whether scanner evidence quality improves before using shortlist strength as confirmation.",
    "freshness_gap": "Refresh stale or missing evidence packets before increasing confidence in the synthesis.",
}


def detect_market_regime_divergence(input_packet: Mapping[str, Any]) -> dict[str, Any]:
    """Detect observation-only regime divergence without fetching or mutating data."""

    packet = input_packet if isinstance(input_packet, Mapping) else {}
    sources = {public_name: _first_mapping(packet, aliases) for public_name, aliases in _CORE_INPUTS}
    regime = sources["marketRegimeSynthesis"]
    theme = sources["themeCorrelationBreadthSnapshot"]
    liquidity = sources["liquidityImpulseSynthesis"]
    scanner = _scanner_mapping(packet, sources["scannerEvidencePacket"])
    breadth = _first_mapping(packet, ("marketBreadthEvidence", "market_breadth_evidence", "breadthEvidence"))
    rotation = _first_mapping(packet, ("rotationStateEvidence", "rotation_state_evidence", "rotationRadarEvidence"))

    missing_inputs = _missing_inputs(sources, scanner=scanner)
    stale_inputs = _stale_inputs(sources, scanner=scanner)
    if breadth and _has_stale_signal(breadth):
        stale_inputs = _append_unique(stale_inputs, "marketBreadthEvidence")
    if rotation and _has_stale_signal(rotation):
        stale_inputs = _append_unique(stale_inputs, "rotationStateEvidence")

    families: list[str] = []
    confirming: list[dict[str, str]] = []
    contradictory: list[dict[str, str]] = []

    headline_positive = _headline_positive(regime)
    breadth_weak = _breadth_weak(regime=regime, breadth=breadth, theme=theme)
    liquidity_stress = _liquidity_stress(regime=regime, liquidity=liquidity)
    theme_concentrated = _theme_concentrated(theme)
    scanner_limited = _scanner_limited(scanner)

    if headline_positive and breadth_weak:
        _record_divergence(
            families,
            contradictory,
            "index_vs_breadth",
            "Headline index strength is not confirmed by breadth evidence.",
        )
    elif headline_positive and regime:
        confirming.append(
            _evidence("index_vs_breadth", "headline_and_breadth_aligned", "Headline and breadth observations are aligned.")
        )

    if headline_positive and liquidity_stress:
        _record_divergence(
            families,
            contradictory,
            "regime_vs_liquidity",
            "Positive headline regime conflicts with liquidity stress evidence.",
        )
    elif headline_positive and liquidity:
        confirming.append(
            _evidence("regime_vs_liquidity", "liquidity_confirms_regime", "Liquidity observations do not contradict the headline regime.")
        )

    if theme_concentrated:
        _record_divergence(
            families,
            contradictory,
            "theme_leadership_vs_participation",
            "Theme leadership is concentrated while participation evidence is weak.",
        )
    elif theme:
        confirming.append(
            _evidence(
                "theme_leadership_vs_participation",
                "theme_participation_broad",
                "Theme participation evidence is broad or mixed without concentration stress.",
            )
        )

    if headline_positive and scanner_limited:
        _record_divergence(
            families,
            contradictory,
            "risk_posture_vs_scanner_quality",
            "Positive risk posture is not confirmed by scanner evidence quality.",
        )
    elif headline_positive and scanner:
        confirming.append(
            _evidence(
                "risk_posture_vs_scanner_quality",
                "scanner_quality_usable",
                "Scanner evidence quality is usable for observation-level confirmation.",
            )
        )

    if stale_inputs or missing_inputs:
        _append_unique(families, "freshness_gap")
        if stale_inputs:
            contradictory.append(_evidence("freshness_gap", "stale_inputs_present", "Some evidence packets are stale or fallback observations."))
        if missing_inputs:
            contradictory.append(_evidence("freshness_gap", "missing_inputs_present", "Some expected evidence packets are missing or incomplete."))

    state = _divergence_state(families=families, missing_inputs=missing_inputs, stale_inputs=stale_inputs, has_regime=bool(regime))
    confidence_cap = _confidence_cap(
        state=state,
        families=families,
        stale_inputs=stale_inputs,
        missing_inputs=missing_inputs,
        sources=(regime, theme, liquidity, scanner, breadth, rotation),
    )

    return {
        "contractVersion": MARKET_REGIME_DIVERGENCE_CONTRACT_VERSION,
        "divergenceState": state,
        "divergenceFamilies": families if state != "aligned" else [],
        "confirmingEvidence": confirming if state == "aligned" else confirming[:2],
        "contradictoryEvidence": contradictory,
        "staleInputs": stale_inputs,
        "missingInputs": missing_inputs,
        "confidenceCap": confidence_cap,
        "observationBoundary": {
            "observationOnly": True,
            "decisionGrade": False,
            "scoreImpact": "none",
            "dataFetches": "none",
            "dataMutation": "none",
            "actionBoundary": "observation_only",
        },
        "researchNextSteps": _research_next_steps(state, families),
        "noAdviceDisclosure": "Observation-only research evidence; no personalized action directive.",
    }


def _first_mapping(packet: Mapping[str, Any], names: Iterable[str]) -> Mapping[str, Any]:
    for name in names:
        value = packet.get(name)
        if isinstance(value, Mapping):
            return value
    return {}


def _scanner_mapping(packet: Mapping[str, Any], direct: Mapping[str, Any]) -> Mapping[str, Any]:
    if direct:
        return direct
    for name in ("scannerEvidencePackets", "scanner_evidence_packets"):
        values = packet.get(name)
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
            for item in values:
                if isinstance(item, Mapping):
                    return item
    return {}


def _missing_inputs(sources: Mapping[str, Mapping[str, Any]], *, scanner: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    for name, value in sources.items():
        source_value = scanner if name == "scannerEvidencePacket" else value
        if not source_value or _has_missing_signal(source_value):
            _append_unique(missing, name)
    return missing


def _stale_inputs(sources: Mapping[str, Mapping[str, Any]], *, scanner: Mapping[str, Any]) -> list[str]:
    stale: list[str] = []
    for name, value in sources.items():
        source_value = scanner if name == "scannerEvidencePacket" else value
        if source_value and _has_stale_signal(source_value):
            _append_unique(stale, name)
    return stale


def _headline_positive(regime: Mapping[str, Any]) -> bool:
    if not regime:
        return False
    risk_appetite = _number(regime.get("riskAppetite") or regime.get("risk_appetite"))
    if risk_appetite is not None and risk_appetite >= 0.25:
        return True
    for key in ("primaryRegime", "regimePosture", "headlineRegime", "state"):
        if _normalized(regime.get(key)) in _POSITIVE_REGIMES:
            return True
    return False


def _breadth_weak(*, regime: Mapping[str, Any], breadth: Mapping[str, Any], theme: Mapping[str, Any]) -> bool:
    breadth_health = _number(regime.get("breadthHealth") or regime.get("breadth_health"))
    if breadth_health is not None and breadth_health <= -0.2:
        return True

    for payload in (breadth, _mapping(theme.get("breadthEvidence"))):
        if not payload:
            continue
        if _normalized(payload.get("state")) in _WEAK_STATES:
            return True
        percent_up = _number(payload.get("percentUp") or payload.get("percent_up"))
        outperform = _number(payload.get("percentOutperformingBenchmark") or payload.get("percent_outperforming_benchmark"))
        values = [value for value in (percent_up, outperform) if value is not None]
        if values and min(values) < 45.0:
            return True
    return False


def _liquidity_stress(*, regime: Mapping[str, Any], liquidity: Mapping[str, Any]) -> bool:
    for payload in (liquidity, regime):
        if not payload:
            continue
        if _normalized(payload.get("classification") or payload.get("state") or payload.get("liquidityState")) in _LIQUIDITY_STRESS_STATES:
            return True
        impulse = _number(payload.get("liquidityImpulse") or payload.get("liquidity_impulse"))
        if impulse is not None and impulse <= -0.2:
            return True
    return False


def _theme_concentrated(theme: Mapping[str, Any]) -> bool:
    if not theme:
        return False
    participation = _normalized(theme.get("participationState") or theme.get("participation_state"))
    if participation == "leader_concentrated":
        return True
    leadership = _mapping(theme.get("leadershipConcentration"))
    if _normalized(leadership.get("state")) == "concentrated":
        broad_participation = _number(leadership.get("broadParticipationPercent"))
        breadth_state = _normalized(_mapping(theme.get("breadthEvidence")).get("state"))
        return broad_participation is None or broad_participation < 45.0 or breadth_state in _WEAK_STATES
    return False


def _scanner_limited(scanner: Mapping[str, Any]) -> bool:
    if not scanner:
        return False
    for key in ("dataQualityState", "freshnessState", "status"):
        if _normalized(scanner.get(key)) in (_WEAK_STATES | _STALE_STATES | _MISSING_STATES):
            return True
    score_confidence = _number(scanner.get("scoreConfidence") or scanner.get("confidence"))
    evidence_coverage = _number(scanner.get("evidenceCoverage") or scanner.get("coverage"))
    if score_confidence is not None and score_confidence < 0.5:
        return True
    if evidence_coverage is not None and evidence_coverage < 0.5:
        return True
    return bool(_sequence(scanner.get("missingEvidence")) or _sequence(scanner.get("warningFlags")))


def _has_missing_signal(value: Mapping[str, Any]) -> bool:
    for key in ("state", "status", "dataQualityState", "freshnessState", "participationState"):
        if _normalized(value.get(key)) in _MISSING_STATES:
            return True
    return bool(_sequence(value.get("missingInputs")) or _sequence(value.get("missingEvidence")))


def _has_stale_signal(value: Mapping[str, Any]) -> bool:
    for key in ("freshness", "freshnessState", "dataQualityState", "status"):
        if _normalized(value.get(key)) in _STALE_STATES:
            return True
    return bool(_sequence(value.get("staleInputs")) or _sequence(value.get("staleEvidence")))


def _divergence_state(*, families: Sequence[str], missing_inputs: Sequence[str], stale_inputs: Sequence[str], has_regime: bool) -> str:
    non_freshness_families = [family for family in families if family != "freshness_gap"]
    if not has_regime or len(missing_inputs) >= 2:
        return "insufficient_evidence"
    if not non_freshness_families and stale_inputs:
        return "insufficient_evidence"
    if non_freshness_families:
        return "diverging"
    return "aligned"


def _confidence_cap(
    *,
    state: str,
    families: Sequence[str],
    stale_inputs: Sequence[str],
    missing_inputs: Sequence[str],
    sources: Sequence[Mapping[str, Any]],
) -> float:
    cap = 0.82
    if any(family != "freshness_gap" for family in families):
        cap = min(cap, 0.66)
    if stale_inputs:
        cap = min(cap, 0.55)
    if missing_inputs:
        cap = min(cap, 0.45)
    if state == "insufficient_evidence":
        cap = min(cap, 0.35)
    for source in sources:
        source_cap = _number(source.get("confidenceCap") if source else None)
        if source_cap is not None:
            cap = min(cap, max(0.0, min(1.0, source_cap)))
    return round(cap, 2)


def _research_next_steps(state: str, families: Sequence[str]) -> list[str]:
    if state == "aligned":
        return ["Continue monitoring whether the aligned evidence persists in later observations."]
    steps = [_FAMILY_NEXT_STEPS[family] for family in families if family in _FAMILY_NEXT_STEPS]
    if state == "insufficient_evidence" and "freshness_gap" not in families:
        steps.append("Collect enough current evidence packets before classifying divergence.")
    return list(dict.fromkeys(steps)) or ["Review the next complete observation window before classifying divergence."]


def _record_divergence(target: list[str], evidence: list[dict[str, str]], family: str, summary: str) -> None:
    _append_unique(target, family)
    evidence.append(_evidence(family, "contradiction_detected", summary))


def _evidence(family: str, signal: str, summary: str) -> dict[str, str]:
    return {"family": family, "signal": signal, "summary": summary}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalized(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _append_unique(values: list[str], value: str) -> list[str]:
    if value and value not in values:
        values.append(value)
    return values


__all__ = [
    "MARKET_REGIME_DIVERGENCE_CONTRACT_VERSION",
    "detect_market_regime_divergence",
]
