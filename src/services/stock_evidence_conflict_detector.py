# -*- coding: utf-8 -*-
"""Pure detector for conflicts across already-computed stock evidence fragments."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


CONTRACT_VERSION = "stock_evidence_conflict_detector_v1"
NO_ADVICE_DISCLOSURE = "Observation-only research conflict context; not personalized action instruction."

_FAMILY_ORDER = (
    "readiness_vs_structure",
    "peer_vs_symbol",
    "compare_vs_symbol",
    "freshness_gap",
    "missing_fundamental_context",
    "missing_peer_context",
    "data_quality_gap",
)
_SUPPORTIVE_STRUCTURE = {"breakout", "uptrend", "pullback"}
_WEAK_READINESS = {"partial", "insufficient"}
_STALE_STATUS = {"stale", "fallback", "delayed", "partial", "synthetic", "unavailable", "unknown", "missing"}
_FAMILY_LABELS = {
    "quote": "quote",
    "technical": "technical",
    "fundamental": "fundamental",
    "news": "news",
    "secfilingevidence": "secFilingEvidence",
    "sec_filing_evidence": "secFilingEvidence",
}
_COMPARE_LABELS = {
    "daily_ohlcv": "daily_price_history",
    "sufficient_daily_ohlcv_history": "history_coverage",
    "valid_daily_ohlcv_rows": "valid_history_rows",
    "benchmark_ohlcv": "benchmark_context",
    "symbol_validation": "symbol_review",
}


def detect_stock_evidence_conflicts(input_packet: Mapping[str, Any]) -> dict[str, Any]:
    """Return a bounded conflict summary from precomputed stock evidence fragments."""

    packet = _mapping(input_packet)
    item = _first_item(packet)
    readiness = _select(packet, item, "symbolEvidenceReadiness", "symbol_evidence_readiness")
    stock_packet = _select(packet, item, "stockEvidencePacket", "stock_evidence_packet")
    structure = _structure(packet)
    peer = _select(packet, structure, "peerCorrelationSnapshot", "peer_correlation_snapshot")
    compare = _select(packet, item, "symbolCompareEvidencePacket", "symbol_compare_evidence_packet")
    symbol = _detect_symbol(packet, readiness, stock_packet, structure, peer, compare)

    families: set[str] = set()
    confirming: list[dict[str, str]] = []
    contradictory: list[dict[str, str]] = []
    stale_inputs: list[dict[str, str]] = []
    missing_inputs: list[dict[str, str]] = []
    cap = 100

    def add_family(name: str) -> None:
        if name in _FAMILY_ORDER:
            families.add(name)

    def add_unique(target: list[dict[str, str]], entry: Mapping[str, str]) -> None:
        normalized = {str(key): str(value) for key, value in entry.items()}
        if normalized not in target:
            target.append(normalized)

    def miss(family: str, input_name: str) -> None:
        add_unique(missing_inputs, {"family": family, "input": input_name})

    def stale(family: str, input_name: str) -> None:
        add_unique(stale_inputs, {"family": family, "input": input_name})
        add_family("freshness_gap")

    def confirm(family: str, observation: str) -> None:
        add_unique(confirming, {"family": family, "observation": observation})

    def contradict(family: str, observation: str) -> None:
        add_unique(contradictory, {"family": family, "observation": observation})

    missing_readiness = not readiness
    missing_structure = not structure
    missing_peer = not peer
    missing_compare = not compare

    if missing_readiness:
        add_family("data_quality_gap")
        miss("symbol_evidence", "symbolEvidenceReadiness")
        cap = min(cap, 45)
    else:
        cap = min(cap, _cap_value(stock_packet, default=100))
        tier = _text(readiness.get("readinessTier")).lower()
        if tier == "sufficient":
            confirm("symbol_evidence", "Symbol evidence readiness is sufficient.")
        elif tier in _WEAK_READINESS:
            add_family("data_quality_gap")
            if _supportive_structure(structure):
                add_family("readiness_vs_structure")
                contradict(
                    "readiness_vs_structure",
                    "Readiness is weaker than the available structure context.",
                )
        for value in _sequence(readiness.get("evidenceMissing")):
            label = _evidence_label(value)
            miss("symbol_evidence", label)
            add_family("data_quality_gap")
            if label == "fundamental":
                add_family("missing_fundamental_context")
        for value in _sequence(readiness.get("conflictingEvidence")):
            miss("symbol_evidence", _evidence_label(value))
            add_family("data_quality_gap")
        for value in _sequence(readiness.get("staleInputs")):
            stale("symbol_evidence", _evidence_label(value))

    if missing_structure:
        add_family("data_quality_gap")
        miss("structure", "stockStructureDecision")
        cap = min(cap, 45)
    else:
        if _supportive_structure(structure):
            confirm("structure", "Structure evidence is supportive within the observation boundary.")
        quality = _mapping(structure.get("dataQuality"))
        if _text(quality.get("status")).lower() not in {"", "available"}:
            add_family("data_quality_gap")
            miss("structure", "structure_evidence")
        for value in _sequence(structure.get("missingEvidence")):
            miss("structure", _compare_label(_mapping(value).get("kind")))
            add_family("data_quality_gap")
        for value in _sequence(structure.get("degradedInputs")):
            stale("structure", _section_label(_mapping(value).get("section")))
        if _text(structure.get("structureState")).lower() == "lowconfidence":
            contradict("structure", "Structure evidence has low confidence.")

    if stock_packet:
        if _text(_mapping(stock_packet.get("thesisEligibility")).get("status")).lower() in {"blocked", "caution"}:
            add_family("data_quality_gap")
            contradict("data_quality_gap", "Stock evidence packet limits downstream research confidence.")
        for value in _sequence(stock_packet.get("dataGaps")):
            label = _evidence_label(_mapping(value).get("evidenceClass"))
            miss("symbol_evidence", label)
            add_family("data_quality_gap")
            if label == "fundamental":
                add_family("missing_fundamental_context")

    if missing_peer:
        add_family("missing_peer_context")
        miss("peer", "peerCorrelationSnapshot")
        cap = min(cap, 60)
    else:
        peer_state = _text(peer.get("correlationState")).lower()
        if peer_state == "aligned":
            confirm("peer", "Peer movement is aligned with the symbol context.")
        elif peer_state == "diverging":
            add_family("peer_vs_symbol")
            contradict("peer_vs_symbol", "Peer movement diverges from otherwise supportive symbol evidence.")
        else:
            add_family("missing_peer_context")
        if _sequence(peer.get("missingInputs")):
            add_family("missing_peer_context")
            miss("peer", "peer_context")
        if _sequence(peer.get("staleInputs")):
            stale("peer", "peer_context")

    if missing_compare:
        add_family("compare_vs_symbol")
        miss("compare", "symbolCompareEvidencePacket")
        cap = min(cap, 60)
    else:
        cap = min(cap, _cap_value(compare, default=100))
        compare_diverged = bool(_sequence(compare.get("divergentEvidence")))
        compare_incomplete = False
        if compare_diverged:
            add_family("compare_vs_symbol")
            contradict("compare_vs_symbol", "Compare evidence diverges across the symbol set.")
        for entries in _mapping(compare.get("missingEvidenceBySymbol")).values():
            for value in _sequence(entries):
                miss("compare", _compare_label(_mapping(value).get("kind")))
                compare_incomplete = True
        for raw_symbol, freshness in _mapping(compare.get("freshnessBySymbol")).items():
            status = _text(_mapping(freshness).get("status")).lower()
            if status in _STALE_STATUS and status != "available":
                stale("compare", _safe_symbol(raw_symbol))
                compare_incomplete = True
        if compare_incomplete:
            add_family("compare_vs_symbol")
            add_family("data_quality_gap")
            contradict("compare_vs_symbol", "Compare evidence is missing or incomplete for this symbol context.")
        if not compare_diverged and not compare_incomplete:
            compared = [_safe_symbol(value) for value in _sequence(compare.get("comparedSymbols"))]
            if symbol in compared or compared:
                confirm("compare", "Compare evidence is available within the observation boundary.")

    for value in _sequence(packet.get("evidenceProvenanceLedger")):
        entry = _mapping(value)
        family = _evidence_label(entry.get("evidenceFamily"))
        freshness = _text(entry.get("freshnessBucket") or entry.get("freshnessState")).lower()
        authority = _text(entry.get("authorityBucket") or entry.get("authorityTier")).lower()
        if freshness in _STALE_STATUS:
            stale("provenance", family)
        if authority in {"unknown", "redacted_input", "unavailable", "missing"}:
            add_family("data_quality_gap")
            miss("provenance", family)

    if "peer_vs_symbol" in families:
        cap = min(cap, 65)
    if "readiness_vs_structure" in families:
        cap = min(cap, 45)
    if "freshness_gap" in families:
        cap = min(cap, 65)
    if "data_quality_gap" in families:
        cap = min(cap, 55)
    if missing_peer and missing_compare:
        cap = min(cap, 40)

    ordered_families = [family for family in _FAMILY_ORDER if family in families]
    return {
        "contractVersion": CONTRACT_VERSION,
        "symbol": symbol,
        "conflictState": _state(
            ordered_families,
            missing_readiness=missing_readiness,
            missing_structure=missing_structure,
            missing_peer=missing_peer,
            missing_compare=missing_compare,
        ),
        "conflictFamilies": ordered_families,
        "confirmingEvidence": confirming,
        "contradictoryEvidence": contradictory,
        "staleInputs": stale_inputs,
        "missingInputs": missing_inputs,
        "confidenceCap": {"value": _bounded(cap), "label": _cap_label(cap)},
        "observationBoundary": {
            "observationOnly": True,
            "decisionGrade": False,
            "scoringImpact": "none",
            "rankingImpact": "none",
        },
        "researchNextSteps": _next_steps(ordered_families, stale_inputs, missing_inputs),
        "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
    }


def _state(
    families: Sequence[str],
    *,
    missing_readiness: bool,
    missing_structure: bool,
    missing_peer: bool,
    missing_compare: bool,
) -> str:
    if not families:
        return "aligned"
    if missing_readiness or missing_structure:
        return "insufficient_evidence"
    if set(families).issubset({"missing_peer_context", "compare_vs_symbol"}) and (missing_peer or missing_compare):
        return "insufficient_evidence"
    if missing_peer and missing_compare:
        return "insufficient_evidence"
    return "conflicting"


def _next_steps(
    families: Sequence[str],
    stale_inputs: Sequence[Mapping[str, str]],
    missing_inputs: Sequence[Mapping[str, str]],
) -> list[str]:
    if not families:
        return ["Continue cross-checking evidence fragments under the observation boundary."]
    steps: list[str] = []
    if missing_inputs:
        steps.append("Fill missing evidence fragments before deeper symbol research.")
    if stale_inputs:
        steps.append("Refresh stale or unavailable fragments before comparing research scenarios.")
    if "peer_vs_symbol" in families:
        steps.append("Review peer divergence alongside symbol-specific evidence.")
    if "compare_vs_symbol" in families:
        steps.append("Recheck compare coverage before using cross-symbol context.")
    if "readiness_vs_structure" in families:
        steps.append("Reconcile symbol readiness with structure evidence before thesis drafting.")
    return _dedupe(steps or ["Review conflicting evidence families together before downstream research."])


def _select(primary: Mapping[str, Any], secondary: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    for source in (primary, secondary):
        for key in keys:
            value = source.get(key)
            if isinstance(value, Mapping):
                return dict(value)
    return {}


def _structure(packet: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("stockStructureDecision", "structureDecision", "stock_structure_decision"):
        value = packet.get(key)
        if isinstance(value, Mapping):
            return dict(value)
    return dict(packet) if isinstance(packet.get("structureState"), str) else {}


def _first_item(packet: Mapping[str, Any]) -> dict[str, Any]:
    items = packet.get("items")
    if isinstance(items, Sequence) and not isinstance(items, (str, bytes, bytearray)) and items:
        return _mapping(items[0])
    return {}


def _detect_symbol(*sources: Mapping[str, Any]) -> str:
    for source in sources:
        for key in ("symbol", "ticker"):
            symbol = _safe_symbol(source.get(key))
            if symbol != "UNKNOWN":
                return symbol
        for value in _sequence(source.get("comparedSymbols")):
            symbol = _safe_symbol(value)
            if symbol != "UNKNOWN":
                return symbol
    return "UNKNOWN"


def _supportive_structure(structure: Mapping[str, Any]) -> bool:
    return (
        _text(structure.get("structureState")).lower() in _SUPPORTIVE_STRUCTURE
        and _text(structure.get("confidence")).lower() in {"high", "medium"}
    )


def _cap_value(payload: Mapping[str, Any], *, default: int) -> int:
    value = _mapping(payload.get("confidenceCap")).get("value")
    return _bounded(int(value)) if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def _cap_label(value: int) -> str:
    value = _bounded(value)
    if value >= 80:
        return "high"
    if value >= 55:
        return "medium"
    return "low"


def _bounded(value: int) -> int:
    return max(0, min(100, int(value)))


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _evidence_label(value: Any) -> str:
    normalized = _text(value).replace("-", "_").lower()
    return _FAMILY_LABELS.get(normalized, "symbol_evidence")


def _compare_label(value: Any) -> str:
    normalized = _text(value).replace("-", "_").lower()
    return _COMPARE_LABELS.get(normalized, "compare_context")


def _section_label(value: Any) -> str:
    normalized = _text(value).replace("-", "_").lower()
    return {
        "symbol": "symbol",
        "structureevidence": "structure_evidence",
        "structure_evidence": "structure_evidence",
        "comparativecontext": "compare_context",
        "sourcecontext": "research_context",
    }.get(normalized, "structure_context")


def _safe_symbol(value: Any) -> str:
    text = _text(value).upper()
    if not text or len(text) > 24:
        return "UNKNOWN"
    return text if all(char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_" for char in text) else "UNKNOWN"


def _dedupe(items: Sequence[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


__all__ = ["CONTRACT_VERSION", "NO_ADVICE_DISCLOSURE", "detect_stock_evidence_conflicts"]
