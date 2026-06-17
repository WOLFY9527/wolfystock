# -*- coding: utf-8 -*-
"""Deterministic observation-only composer for structured research packets."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
import re


RESEARCH_NARRATIVE_COMPOSER_VERSION = "research_narrative_composer_v1"
RESEARCH_NARRATIVE_SECTION_TITLES: tuple[str, ...] = (
    "Current observation",
    "Evidence supporting the observation",
    "Evidence limiting the observation",
    "Data freshness",
    "Research next step",
    "No-advice disclosure",
)
RESEARCH_NARRATIVE_NO_ADVICE_DISCLOSURE = (
    "For research observation only. It does not provide personalized financial "
    "advice or account action instructions."
)

_MAX_SECTION_ITEMS = 3
_MAX_TEXT_LENGTH = 180
_EN_ADVICE_PATTERN = re.compile(
    r"\b("
    r"buy|sell|hold|recommend|recommends|recommended|recommending|recommendation|"
    r"target|stop|take profit|position sizing|place order|submit order"
    r")\b",
    re.IGNORECASE,
)
_ZH_ADVICE_MARKERS = (
    "买入",
    "卖出",
    "持有",
    "推荐",
    "目标价",
    "目标位",
    "止损",
    "止盈",
    "仓位",
    "下单",
)
_INTERNAL_TEXT_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "debug",
    "diagnostic",
    "fallback_static",
    "marketcache",
    "provider",
    "raw_payload",
    "raw_result",
    "reasoncode",
    "reasonfamilies",
    "runtime",
    "schema",
    "scorecontributionallowed",
    "sourceauthorityallowed",
    "source_ref_id",
    "stack_trace",
    "synthetic_fixture",
    "token",
    "trace",
)
_UNSAFE_BRACKETS = frozenset("{}[]")
_FRESHNESS_LABELS = {
    "fresh": "fresh",
    "live": "fresh",
    "realtime": "fresh",
    "current": "fresh",
    "delayed": "delayed",
    "stale": "stale",
    "partial": "partial",
    "missing": "missing",
    "unavailable": "unavailable",
    "unknown": "unknown",
    "cached": "recent snapshot",
    "cache": "recent snapshot",
    "snapshot": "recent snapshot",
    "fallback": "limited",
    "proxy": "limited",
    "synthetic": "limited",
    "fixture": "limited",
    "mock": "limited",
}
_FRESHNESS_ORDER = {
    "fresh": 0,
    "recent snapshot": 1,
    "delayed": 2,
    "partial": 3,
    "stale": 4,
    "limited": 5,
    "missing": 6,
    "unavailable": 7,
    "unknown": 8,
}


@dataclass(slots=True)
class ResearchNarrativeSection:
    title: str
    body: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "body": list(self.body),
        }


@dataclass(slots=True)
class ResearchNarrative:
    contract_version: str = RESEARCH_NARRATIVE_COMPOSER_VERSION
    sections: list[ResearchNarrativeSection] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contractVersion": self.contract_version,
            "sections": [section.to_dict() for section in self.sections],
        }

    def to_markdown(self) -> str:
        blocks: list[str] = []
        for section in self.sections:
            blocks.append(f"## {section.title}")
            if len(section.body) == 1:
                blocks.append(section.body[0])
            else:
                blocks.extend(f"- {item}" for item in section.body)
        return "\n\n".join(blocks)


def compose_research_narrative(value: Mapping[str, Any] | None) -> ResearchNarrative:
    """Compose a short safe narrative from caller-supplied research evidence."""

    packet = _mapping(value)
    sections = [
        ResearchNarrativeSection(
            title="Current observation",
            body=[_current_observation(packet)],
        ),
        ResearchNarrativeSection(
            title="Evidence supporting the observation",
            body=_supporting_evidence(packet),
        ),
        ResearchNarrativeSection(
            title="Evidence limiting the observation",
            body=_limiting_evidence(packet),
        ),
        ResearchNarrativeSection(
            title="Data freshness",
            body=_data_freshness(packet),
        ),
        ResearchNarrativeSection(
            title="Research next step",
            body=_research_next_step(packet),
        ),
        ResearchNarrativeSection(
            title="No-advice disclosure",
            body=[RESEARCH_NARRATIVE_NO_ADVICE_DISCLOSURE],
        ),
    ]
    return ResearchNarrative(sections=sections)


def _current_observation(packet: Mapping[str, Any]) -> str:
    observation = _first_safe_text(
        packet,
        (
            "currentObservation",
            "current_observation",
            "observation",
            "safeSummary",
            "safe_summary",
            "summary",
            "headline",
        ),
    )
    if observation:
        return observation

    consumer_projection = _mapping(packet.get("consumerProjection"))
    headline = _first_safe_text(consumer_projection, ("headline", "summary"))
    if headline:
        return headline

    supporting = _supporting_evidence(packet)
    if supporting and not supporting[0].startswith("No displayable"):
        return f"The packet highlights {supporting[0].rstrip('.')}."

    subject = _subject_label(packet)
    if subject:
        return f"{subject} has a structured research packet, but the current observation needs more evidence."
    return "The structured research packet does not yet provide a displayable current observation."


def _supporting_evidence(packet: Mapping[str, Any]) -> list[str]:
    candidates = _items_from_keys(
        packet,
        (
            "supportingEvidence",
            "supporting_evidence",
            "evidenceSupportingObservation",
            "evidence_supporting_observation",
            "supportingSignals",
            "supporting_signals",
        ),
    )
    citations = _sequence(packet.get("evidenceCitations")) + _sequence(packet.get("citations"))
    candidates.extend(citations)

    items = _evidence_sentences(candidates)
    if items:
        return items

    return ["No displayable supporting evidence was supplied."]


def _limiting_evidence(packet: Mapping[str, Any]) -> list[str]:
    candidates = _items_from_keys(
        packet,
        (
            "limitingEvidence",
            "limiting_evidence",
            "evidenceLimitingObservation",
            "evidence_limiting_observation",
            "limitations",
            "evidenceGaps",
            "evidence_gaps",
            "missingEvidence",
            "missing_evidence",
            "missingConfirmation",
            "missing_confirmation",
        ),
    )
    candidates.extend(_lane_limitations(packet))

    items = _evidence_sentences(candidates)
    if items:
        return items

    return ["No displayable limiting evidence was supplied."]


def _data_freshness(packet: Mapping[str, Any]) -> list[str]:
    as_of_values = _safe_dates(
        [
            packet.get("asOf"),
            packet.get("as_of"),
            packet.get("generatedAt"),
            packet.get("generated_at"),
            *(_raw_date(item) for item in _all_evidence_items(packet)),
        ]
    )
    freshness_values = _freshness_values(packet)

    items: list[str] = []
    if as_of_values:
        items.append(f"Latest evidence timestamp observed: {max(as_of_values)}.")
    else:
        items.append("No displayable evidence timestamp was supplied.")

    if freshness_values:
        constrained = max(freshness_values, key=lambda item: _FRESHNESS_ORDER.get(item, _FRESHNESS_ORDER["unknown"]))
        joined = ", ".join(_dedupe(freshness_values)[:4])
        items.append(f"Freshness labels observed: {joined}; most constrained label: {constrained}.")
    else:
        items.append("Freshness labels were not supplied.")
    return items


def _research_next_step(packet: Mapping[str, Any]) -> list[str]:
    candidates = _items_from_keys(
        packet,
        (
            "researchNextStep",
            "research_next_step",
            "nextResearchStep",
            "next_research_step",
            "nextEvidenceNeeded",
            "next_evidence_needed",
            "nextStep",
            "next_step",
        ),
    )
    candidates.extend(_lane_next_steps(packet))
    items = _evidence_sentences(candidates)
    if items:
        return items
    return ["Collect one additional independent evidence point before expanding the research view."]


def _items_from_keys(packet: Mapping[str, Any], keys: Sequence[str]) -> list[Any]:
    values: list[Any] = []
    for key in keys:
        raw = packet.get(key)
        if raw is None:
            continue
        if isinstance(raw, Mapping):
            values.append(raw)
        elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
            values.extend(raw)
        else:
            values.append(raw)
    return values


def _evidence_sentences(candidates: Sequence[Any]) -> list[str]:
    items: list[str] = []
    for candidate in candidates:
        sentence = _evidence_sentence(candidate)
        if sentence:
            _append_unique(items, sentence)
        if len(items) >= _MAX_SECTION_ITEMS:
            break
    return items


def _evidence_sentence(candidate: Any) -> str:
    if isinstance(candidate, Mapping):
        label = _first_safe_text(candidate, ("label", "title", "name", "lane", "domain", "theme", "metric"))
        summary = _first_safe_text(
            candidate,
            ("summary", "description", "observation", "value", "headline", "status", "state"),
        )
        as_of = _safe_date(_raw_date(candidate))
        parts: list[str] = []
        if label and summary and label.lower() != summary.lower():
            parts.append(f"{label}: {summary}")
        elif summary:
            parts.append(summary)
        elif label:
            parts.append(label)
        if not parts:
            return ""
        sentence = parts[0].rstrip(".")
        if as_of:
            sentence = f"{sentence} (as of {as_of})"
        return f"{sentence}."
    return _safe_consumer_text(candidate)


def _lane_limitations(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    lanes = _mapping(packet.get("lanes"))
    items: list[dict[str, Any]] = []
    for lane_name, raw_lane in lanes.items():
        lane = _mapping(raw_lane)
        for limitation in _sequence(lane.get("limitations")):
            items.append({"label": lane_name, "summary": limitation})
    return items


def _lane_next_steps(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    lanes = _mapping(packet.get("lanes"))
    items: list[dict[str, Any]] = []
    for lane_name, raw_lane in lanes.items():
        lane = _mapping(raw_lane)
        for next_step in _sequence(lane.get("nextEvidenceNeeded")) + _sequence(lane.get("next_evidence_needed")):
            items.append({"label": lane_name, "summary": next_step})
    return items


def _freshness_values(packet: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("freshness", "freshnessClass", "freshness_class", "freshnessLabel"):
        label = _freshness_label(packet.get(key))
        if label:
            values.append(label)
    for item in _all_evidence_items(packet):
        if isinstance(item, Mapping):
            for key in ("freshness", "freshnessClass", "freshness_class", "freshnessLabel", "status", "state"):
                label = _freshness_label(item.get(key))
                if label:
                    values.append(label)
    for raw_lane in _mapping(packet.get("lanes")).values():
        lane = _mapping(raw_lane)
        for key in ("freshness", "status", "consumerState"):
            label = _freshness_label(lane.get(key))
            if label:
                values.append(label)
    return values


def _all_evidence_items(packet: Mapping[str, Any]) -> list[Any]:
    items: list[Any] = []
    for key in (
        "supportingEvidence",
        "supporting_evidence",
        "limitingEvidence",
        "limiting_evidence",
        "evidenceCitations",
        "citations",
    ):
        items.extend(_items_from_keys(packet, (key,)))
    return items


def _freshness_label(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not text:
        return ""
    return _FRESHNESS_LABELS.get(text, "")


def _raw_date(value: Any) -> Any:
    if isinstance(value, Mapping):
        for key in ("asOf", "as_of", "publishedAt", "published_at", "updatedAt", "updated_at"):
            if value.get(key):
                return value.get(key)
        return None
    return value


def _safe_dates(values: Sequence[Any]) -> list[str]:
    dates: list[str] = []
    for value in values:
        date = _safe_date(value)
        if date:
            _append_unique(dates, date)
    return dates


def _safe_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text or _contains_blocked_text(text):
        return ""
    if not re.match(r"^\d{4}-\d{2}-\d{2}(?:[T ][0-9:.\-+Z]+)?$", text):
        return ""
    return text[:25]


def _first_safe_text(packet: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        text = _safe_consumer_text(packet.get(key))
        if text:
            return text
    return ""


def _safe_consumer_text(value: Any) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).strip().split())
    if not text:
        return ""
    if any(char in text for char in _UNSAFE_BRACKETS):
        return ""
    if _contains_blocked_text(text):
        return ""
    return text[:_MAX_TEXT_LENGTH].rstrip(" ,;:-")


def _contains_blocked_text(text: str) -> bool:
    lowered = text.lower()
    compact = re.sub(r"[\s_\-:.]+", "", lowered)
    if _EN_ADVICE_PATTERN.search(lowered):
        return True
    if any(marker in text for marker in _ZH_ADVICE_MARKERS):
        return True
    for marker in _INTERNAL_TEXT_MARKERS:
        if re.sub(r"[\s_\-:.]+", "", marker.lower()) in compact:
            return True
    return False


def _subject_label(packet: Mapping[str, Any]) -> str:
    for key in ("symbol", "ticker", "name", "title"):
        text = _safe_consumer_text(packet.get(key))
        if text:
            return text[:32]
    identity = _mapping(packet.get("packetIdentity"))
    for key in ("symbol", "market"):
        text = _safe_consumer_text(identity.get(key))
        if text:
            return text[:32]
    return ""


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _dedupe(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        _append_unique(result, value)
    return result


def _append_unique(values: list[str], value: str) -> None:
    text = str(value or "").strip()
    if text and text not in values:
        values.append(text)


__all__ = [
    "RESEARCH_NARRATIVE_COMPOSER_VERSION",
    "RESEARCH_NARRATIVE_NO_ADVICE_DISCLOSURE",
    "RESEARCH_NARRATIVE_SECTION_TITLES",
    "ResearchNarrative",
    "ResearchNarrativeSection",
    "compose_research_narrative",
]
