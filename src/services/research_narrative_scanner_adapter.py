# -*- coding: utf-8 -*-
"""Narrow scanner-packet adapter for the research narrative composer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
import re

from src.services.research_narrative_composer import ResearchNarrative, compose_research_narrative


_SCANNER_EVIDENCE_BUCKETS: tuple[tuple[str, str], ...] = (
    ("trendEvidence", "Trend evidence"),
    ("momentumEvidence", "Momentum evidence"),
    ("volumeEvidence", "Volume evidence"),
    ("volatilityRiskEvidence", "Risk evidence"),
    ("liquidityEvidence", "Liquidity evidence"),
    ("relativeStrengthEvidence", "Relative strength evidence"),
    ("sectorThemeContext", "Theme context"),
)
_ADVICE_OR_INTERNAL_RE = re.compile(
    r"\b("
    r"buy|sell|hold|recommend|recommendation|target price|stop loss|"
    r"position sizing|provider|cache|runtime|debug|diagnostic|raw|payload|"
    r"schema|trace|token|authorization|sourceauthorityallowed|"
    r"scorecontributionallowed|reasoncode|adminreasoncodes|fallback_source|"
    r"provider_unavailable|history_insufficient"
    r")\b",
    re.IGNORECASE,
)
_ZH_ADVICE_MARKERS = ("买入", "卖出", "持有", "推荐", "目标价", "止损", "止盈", "仓位", "下单")
_FRESHNESS_LABELS = {
    "complete": "fresh",
    "fresh": "fresh",
    "fallback": "fallback",
    "partial": "partial",
    "stale": "stale",
    "missing": "missing",
    "unavailable": "unavailable",
}


def compose_scanner_candidate_research_narrative(value: Mapping[str, Any] | None) -> ResearchNarrative:
    """Compose an observation-only narrative from an existing scanner packet shape."""

    return compose_research_narrative(scanner_candidate_packet_to_research_narrative_input(value))


def scanner_candidate_packet_to_research_narrative_input(
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Project a scanner candidate/evidence packet into the composer input shape."""

    source = _mapping(value)
    packet = _scanner_evidence_packet(source)
    symbol = _safe_symbol(packet.get("symbol") or source.get("symbol"))
    freshness = _freshness(packet)

    return {
        "symbol": symbol,
        "currentObservation": _current_observation(symbol),
        "supportingEvidence": _supporting_evidence(packet),
        "limitingEvidence": _limiting_evidence(packet),
        "researchNextStep": _research_next_step(packet),
        "asOf": _latest_trade_date(packet),
        "freshness": freshness,
    }


def _scanner_evidence_packet(source: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics = _mapping(source.get("diagnostics"))
    nested = _mapping(diagnostics.get("evidence_packet"))
    if nested:
        return nested
    nested = _mapping(source.get("evidence_packet"))
    if nested:
        return nested
    if any(key in source for key, _label in _SCANNER_EVIDENCE_BUCKETS):
        return dict(source)
    return {}


def _current_observation(symbol: str) -> str:
    if symbol:
        return f"{symbol} scanner evidence is available for observation-only review."
    return "Scanner evidence is available for observation-only review."


def _supporting_evidence(packet: Mapping[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for key, label in _SCANNER_EVIDENCE_BUCKETS:
        bucket = _mapping(packet.get(key))
        if not bucket:
            continue
        summary = _bucket_summary(bucket)
        if summary:
            items.append({"label": label, "summary": summary})
    return items


def _bucket_summary(bucket: Mapping[str, Any]) -> str:
    state = _display_state(bucket.get("state"))
    facts = _bucket_facts(bucket)
    if facts:
        return f"{state} evidence observed: {'; '.join(facts)}"
    return f"{state} evidence observed."


def _bucket_facts(bucket: Mapping[str, Any]) -> list[str]:
    facts: list[str] = []
    for raw_fact in _sequence(bucket.get("facts")):
        fact = _mapping(raw_fact)
        label = _safe_text(fact.get("label"))
        value = _safe_text(fact.get("value"))
        if label and value:
            facts.append(f"{label} {value}")
        elif label:
            facts.append(label)
        elif value:
            facts.append(value)
        if len(facts) >= 2:
            break
    return facts


def _limiting_evidence(packet: Mapping[str, Any]) -> list[str]:
    items: list[str] = []
    quality = _safe_state(packet.get("dataQualityState"))
    if quality and quality != "complete":
        items.append(f"Data quality is {_display_state(quality).lower()}.")

    freshness = _safe_state(packet.get("freshnessState"))
    if freshness and freshness != "complete":
        items.append("Evidence freshness needs review before confidence can improve.")

    for raw_gap in _sequence(packet.get("missingEvidence")):
        label = _safe_label(raw_gap)
        if label:
            items.append(f"Missing evidence: {label}.")

    for raw_flag in _sequence(packet.get("warningFlags")):
        label = _safe_text(raw_flag)
        if label:
            items.append(f"Review note: {label}.")
    return _dedupe(items)


def _research_next_step(packet: Mapping[str, Any]) -> list[str]:
    missing = [_safe_label(item) for item in _sequence(packet.get("missingEvidence"))]
    missing = [item for item in missing if item]
    if missing:
        return [f"Review {missing[0].lower()} evidence before expanding the research view."]
    return ["Review the scanner evidence buckets with one independent confirmation point."]


def _latest_trade_date(packet: Mapping[str, Any]) -> str:
    detail = _mapping(packet.get("freshnessDetail"))
    return _safe_date(detail.get("latestTradeDate"))


def _freshness(packet: Mapping[str, Any]) -> str:
    state = _safe_state(packet.get("freshnessState"))
    return _FRESHNESS_LABELS.get(state, "unknown")


def _safe_symbol(value: Any) -> str:
    text = str(value or "").strip().upper()
    safe = "".join(char for char in text if char.isalnum() or char in ".-_")
    return safe[:24]


def _safe_state(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not text or _ADVICE_OR_INTERNAL_RE.search(text):
        return ""
    return text[:40]


def _display_state(value: Any) -> str:
    state = _safe_state(value)
    if not state:
        return "Available"
    return state.replace("_", " ").capitalize()


def _safe_label(value: Any) -> str:
    text = _safe_text(value)
    if not text:
        return ""
    return text.replace("_", " ").replace("-", " ").strip().capitalize()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).strip().split())
    if not text:
        return ""
    if any(marker in text for marker in _ZH_ADVICE_MARKERS):
        return ""
    if _ADVICE_OR_INTERNAL_RE.search(text):
        return ""
    if any(char in text for char in "{}[]"):
        return ""
    return text[:96].rstrip(" ,;:-")


def _safe_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text or _ADVICE_OR_INTERNAL_RE.search(text):
        return ""
    if not re.match(r"^\d{4}-\d{2}-\d{2}(?:[T ][0-9:.\-+Z]+)?$", text):
        return ""
    return text[:25]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _dedupe(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


__all__ = [
    "compose_scanner_candidate_research_narrative",
    "scanner_candidate_packet_to_research_narrative_input",
]
