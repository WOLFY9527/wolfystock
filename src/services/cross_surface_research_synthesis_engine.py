# -*- coding: utf-8 -*-
"""Pure cross-surface research synthesis packet composer."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


CROSS_SURFACE_RESEARCH_SYNTHESIS_CONTRACT_VERSION = "cross_surface_research_synthesis_v1"
CROSS_SURFACE_RESEARCH_SYNTHESIS_NO_ADVICE_DISCLOSURE = (
    "Observation-only research context; not personalized financial advice and not an instruction."
)

_STALE_STATES = {
    "cached",
    "delayed",
    "fallback",
    "partial",
    "stale",
    "stale_or_cached",
    "synthetic",
}
_MISSING_STATES = {
    "absent",
    "failed",
    "insufficient",
    "insufficient_evidence",
    "missing",
    "no_evidence",
    "unavailable",
    "unknown",
}
_CONTRADICTORY_STATES = {
    "conflict",
    "conflicting",
    "contradiction",
    "contradictory",
    "divergence",
    "divergent",
    "diverging",
    "mixed",
}
_UNSAFE_KEY_RE = re.compile(
    r"^(?:"
    r"admindiagnostics?|cache(?:key|state|trace)?|debug(?:ref|state|trace)?|"
    r"provider(?:diagnostics?|payload|route|runtime|state|trace)?|"
    r"raw(?:diagnostics?|json|payload|response|result)?|"
    r"reasoncodes?|requestids?|runtime(?:diagnostics?|trace)?|"
    r"sourcerefs?|sourcerefid|traceids?|trace"
    r")$",
    re.IGNORECASE,
)
_UNSAFE_TEXT_RE = re.compile(
    r"\b("
    r"api[_-]?key|authorization|bearer|cache|debug|diagnostics?|marketcache|"
    r"provider|raw\s*(?:diagnostics?|json|payload|response|result)?|"
    r"reason\s*codes?|request\s*ids?|runtime|secret|source\s*refs?|token|trace"
    r")\b|https?://|/users/",
    re.IGNORECASE,
)
_ADVICE_RE = re.compile(
    r"\b("
    r"buy|sell|hold|recommend(?:ation|ed)?|target\s*price|stop\s*loss|take\s*profit|"
    r"position\s*sizing|place\s*order|submit\s*order|trading\s*advice|investment\s*advice"
    r")\b|买入|卖出|持有|交易建议|投资建议|目标价|止损|止盈|仓位",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class _SurfaceSpec:
    surface_id: str
    label: str
    family: str
    aliases: tuple[str, ...]
    required: bool = True


_SURFACE_SPECS: tuple[_SurfaceSpec, ...] = (
    _SurfaceSpec(
        "market_regime",
        "Market regime",
        "macro",
        ("marketRegimeSynthesis", "market_regime_synthesis", "regimeSummary"),
    ),
    _SurfaceSpec(
        "research_queue",
        "Research queue",
        "research_context",
        ("researchQueue", "research_queue", "researchQueueV1", "research_queue_v1"),
    ),
    _SurfaceSpec(
        "scanner_overlay",
        "Scanner overlay",
        "scanner_context",
        ("scannerResearchOverlay", "scanner_research_overlay"),
    ),
    _SurfaceSpec(
        "watchlist_overlay",
        "Watchlist overlay",
        "watchlist_context",
        ("watchlistResearchOverlay", "watchlist_research_overlay"),
    ),
    _SurfaceSpec(
        "portfolio_exposure",
        "Portfolio exposure",
        "portfolio_context",
        ("portfolioExposureResearchContext", "exposureResearchContext"),
    ),
    _SurfaceSpec(
        "symbol_readiness",
        "Symbol readiness",
        "symbol_context",
        ("symbolEvidenceReadiness", "symbol_evidence_readiness"),
    ),
    _SurfaceSpec(
        "peer_correlation",
        "Peer correlation",
        "peer_context",
        ("peerCorrelationSnapshot", "peer_correlation_snapshot"),
    ),
    _SurfaceSpec(
        "symbol_comparison",
        "Symbol comparison",
        "comparison_context",
        ("symbolCompareEvidencePacket", "symbol_compare_evidence_packet"),
    ),
    _SurfaceSpec(
        "theme_breadth",
        "Theme breadth",
        "theme_context",
        ("themeCorrelationBreadthSnapshot", "theme_correlation_breadth_snapshot"),
    ),
    _SurfaceSpec(
        "evidence_provenance",
        "Evidence provenance",
        "provenance_context",
        ("evidenceProvenanceLedger", "provenanceLedger", "researchQueueEvidenceProvenanceLedger"),
    ),
    _SurfaceSpec(
        "research_gaps",
        "Research gaps",
        "gap_context",
        ("prioritizedResearchGaps", "researchGapPriorities", "researchGaps"),
        required=False,
    ),
    _SurfaceSpec(
        "research_checklist",
        "Research checklist",
        "checklist_context",
        ("researchChecklist", "researchChecklistPacket"),
        required=False,
    ),
)


def compose_cross_surface_research_synthesis(input_packet: Mapping[str, Any]) -> dict[str, Any]:
    """Compose a bounded cross-surface research synthesis packet."""

    packet = input_packet if isinstance(input_packet, Mapping) else {}
    redacted_input_count = _unsafe_input_count(packet)
    subject = _subject(packet)

    contributions: list[dict[str, Any]] = []
    confirming_evidence: list[dict[str, Any]] = []
    contradicting_evidence: list[dict[str, Any]] = []
    missing_evidence: list[dict[str, Any]] = []
    stale_evidence: list[dict[str, Any]] = []
    missing_inputs: list[str] = []

    for spec in _SURFACE_SPECS:
        payload = _first_present(packet, spec.aliases)
        if payload is None or not _has_payload(payload):
            if spec.required:
                label = f"{spec.label} input missing."
                missing_inputs.append(label)
                missing_evidence.append(_evidence_item(spec.label, label))
            continue

        stale = _has_stale_marker(payload)
        missing = _has_missing_marker(payload)
        contradictory = _has_contradictory_marker(payload)
        contribution_state = _contribution_state(
            stale=stale,
            missing=missing,
            contradictory=contradictory,
        )
        contribution = {
            "surface": spec.label,
            "state": contribution_state,
            "evidenceFamily": _family_label(spec.family),
            "observationOnly": True,
        }
        contributions.append(contribution)

        if contradictory:
            contradicting_evidence.append(
                _evidence_item(spec.label, f"{spec.label} contains divergence evidence for review.")
            )
        elif stale:
            stale_evidence.append(
                _evidence_item(spec.label, f"{spec.label} includes stale or delayed evidence.")
            )
        elif missing:
            missing_evidence.append(
                _evidence_item(spec.label, f"{spec.label} has missing evidence that needs review.")
            )
        else:
            confirming_evidence.append(
                _evidence_item(spec.label, f"{spec.label} is available for cross-surface research review.")
            )

    if redacted_input_count:
        missing_evidence.append(
            _evidence_item(
                "Input safety",
                "Input safety boundary requires review before synthesis confidence can rise.",
            )
        )

    primary_evidence_families = [item["surface"] for item in contributions]
    synthesis_state = _synthesis_state(
        contribution_count=len(contributions),
        missing_inputs=missing_inputs,
        stale_evidence=stale_evidence,
        contradicting_evidence=contradicting_evidence,
        redacted_input_count=redacted_input_count,
    )
    confidence_cap = _confidence_cap(
        synthesis_state=synthesis_state,
        missing_inputs=missing_inputs,
        stale_evidence=stale_evidence,
        contradicting_evidence=contradicting_evidence,
        redacted_input_count=redacted_input_count,
    )

    return {
        "contractVersion": CROSS_SURFACE_RESEARCH_SYNTHESIS_CONTRACT_VERSION,
        "subject": subject,
        "synthesisState": synthesis_state,
        "primaryEvidenceFamilies": primary_evidence_families,
        "confirmingEvidence": confirming_evidence,
        "contradictingEvidence": contradicting_evidence,
        "missingEvidence": _dedupe_evidence(missing_evidence),
        "missingInputs": _dedupe_text(missing_inputs),
        "staleEvidence": stale_evidence,
        "provenanceSummary": _provenance_summary(
            contributions=contributions,
            missing_inputs=missing_inputs,
            stale_evidence=stale_evidence,
            contradicting_evidence=contradicting_evidence,
            redacted_input_count=redacted_input_count,
            synthesis_state=synthesis_state,
        ),
        "confidenceCap": confidence_cap,
        "observationBoundary": {
            "observationOnly": True,
            "decisionGrade": False,
            "mutation": False,
            "externalCalls": False,
            "adviceBoundary": "no_advice",
            "message": CROSS_SURFACE_RESEARCH_SYNTHESIS_NO_ADVICE_DISCLOSURE,
        },
        "researchNextSteps": _research_next_steps(
            synthesis_state=synthesis_state,
            missing_inputs=missing_inputs,
            stale_evidence=stale_evidence,
            contradicting_evidence=contradicting_evidence,
            redacted_input_count=redacted_input_count,
        ),
        "surfaceContributions": contributions,
        "noAdviceDisclosure": CROSS_SURFACE_RESEARCH_SYNTHESIS_NO_ADVICE_DISCLOSURE,
    }


def _subject(packet: Mapping[str, Any]) -> dict[str, Any]:
    raw_subject = packet.get("subject")
    subject = dict(raw_subject) if isinstance(raw_subject, Mapping) else {}
    symbol = _safe_symbol(
        subject.get("symbol")
        or subject.get("ticker")
        or packet.get("symbol")
        or packet.get("ticker")
    )
    label = _safe_label(subject.get("label") or subject.get("name") or packet.get("subjectLabel"))
    result: dict[str, Any] = {}
    if symbol:
        result["symbol"] = symbol
    if label:
        result["label"] = label
    return result or {"label": "Cross-surface research context"}


def _first_present(packet: Mapping[str, Any], aliases: Sequence[str]) -> Any:
    for key in aliases:
        if key in packet:
            return packet.get(key)
    return None


def _has_payload(value: Any) -> bool:
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return bool(value)
    return value not in (None, "")


def _contribution_state(*, stale: bool, missing: bool, contradictory: bool) -> str:
    if contradictory:
        return "contradictory"
    if stale:
        return "stale"
    if missing:
        return "partial"
    return "available"


def _synthesis_state(
    *,
    contribution_count: int,
    missing_inputs: Sequence[str],
    stale_evidence: Sequence[Mapping[str, Any]],
    contradicting_evidence: Sequence[Mapping[str, Any]],
    redacted_input_count: int,
) -> str:
    if contribution_count < 2:
        return "insufficient_evidence"
    if redacted_input_count or contradicting_evidence:
        return "insufficient_evidence"
    if stale_evidence or missing_inputs:
        return "partial"
    return "complete"


def _confidence_cap(
    *,
    synthesis_state: str,
    missing_inputs: Sequence[str],
    stale_evidence: Sequence[Mapping[str, Any]],
    contradicting_evidence: Sequence[Mapping[str, Any]],
    redacted_input_count: int,
) -> dict[str, Any]:
    if synthesis_state == "complete":
        return {"value": 85, "label": "high", "reasons": []}

    reasons: list[str] = []
    if redacted_input_count:
        reasons.append("redacted_input_present")
    if contradicting_evidence:
        reasons.append("contradictory_evidence_present")
    if stale_evidence:
        reasons.append("stale_or_delayed_evidence_present")
    if missing_inputs:
        reasons.append("missing_cross_surface_inputs")
    if not reasons:
        reasons.append("insufficient_cross_surface_evidence")

    if reasons == ["missing_cross_surface_inputs"]:
        reasons = ["Insufficient cross-surface evidence."]
        return {"value": 20, "label": "low", "reasons": reasons}
    if redacted_input_count or contradicting_evidence:
        return {"value": 35, "label": "low", "reasons": [_reason_label(reason) for reason in reasons]}
    return {"value": 55, "label": "medium", "reasons": [_reason_label(reason) for reason in reasons]}


def _provenance_summary(
    *,
    contributions: Sequence[Mapping[str, Any]],
    missing_inputs: Sequence[str],
    stale_evidence: Sequence[Mapping[str, Any]],
    contradicting_evidence: Sequence[Mapping[str, Any]],
    redacted_input_count: int,
    synthesis_state: str,
) -> dict[str, Any]:
    return {
        "contributingSurfaceCount": len(contributions),
        "missingInputCount": len(_dedupe_text(missing_inputs)),
        "staleEvidenceCount": len(stale_evidence),
        "contradictionCount": len(contradicting_evidence),
        "redactedInputCount": redacted_input_count,
        "failClosed": synthesis_state == "insufficient_evidence",
        "evidenceSources": [str(item.get("surface")) for item in contributions],
    }


def _research_next_steps(
    *,
    synthesis_state: str,
    missing_inputs: Sequence[str],
    stale_evidence: Sequence[Mapping[str, Any]],
    contradicting_evidence: Sequence[Mapping[str, Any]],
    redacted_input_count: int,
) -> list[dict[str, Any]]:
    if redacted_input_count:
        return [_step("Review input safety boundaries before using this synthesis packet.", "high")]
    if contradicting_evidence:
        return [_step("Compare divergent evidence families before raising synthesis confidence.", "high")]
    if missing_inputs:
        return [_step("Attach the missing cross-surface inputs before relying on synthesis context.", "high")]
    if stale_evidence:
        return [_step("Refresh stale or delayed inputs before comparing research scenarios.", "medium")]
    if synthesis_state == "complete":
        return [_step("Review market, symbol, portfolio, and provenance context together.", "low")]
    return [_step("Collect at least two independent research surfaces before synthesis.", "high")]


def _step(label: str, priority: str) -> dict[str, Any]:
    return {
        "label": label,
        "priority": priority,
        "observationOnly": True,
    }


def _evidence_item(surface: str, label: str) -> dict[str, Any]:
    return {
        "surface": surface,
        "label": label,
        "observationOnly": True,
    }


def _family_label(value: str) -> str:
    labels = {
        "macro": "Macro context",
        "research_context": "Research context",
        "scanner_context": "Scanner context",
        "watchlist_context": "Watchlist context",
        "portfolio_context": "Portfolio context",
        "symbol_context": "Symbol context",
        "peer_context": "Peer context",
        "comparison_context": "Comparison context",
        "theme_context": "Theme context",
        "provenance_context": "Provenance context",
        "gap_context": "Evidence gap context",
        "checklist_context": "Checklist context",
    }
    return labels.get(value, "Research context")


def _reason_label(value: str) -> str:
    labels = {
        "redacted_input_present": "Input safety boundary requires review.",
        "contradictory_evidence_present": "Contradictory evidence requires review.",
        "stale_or_delayed_evidence_present": "Stale or delayed evidence present.",
        "missing_cross_surface_inputs": "Missing cross-surface inputs.",
        "insufficient_cross_surface_evidence": "Insufficient cross-surface evidence.",
    }
    return labels.get(value, "Research evidence requires review.")


def _has_stale_marker(value: Any) -> bool:
    return _contains_marker(value, keys={"staleinputs", "staleevidence"}, states=_STALE_STATES)


def _has_missing_marker(value: Any) -> bool:
    return _contains_marker(
        value,
        keys={
            "blockingreasons",
            "datagaps",
            "degradedinputs",
            "evidencegaps",
            "evidencemissing",
            "missingevidence",
            "missinginputs",
        },
        states=_MISSING_STATES,
    )


def _has_contradictory_marker(value: Any) -> bool:
    return _contains_marker(
        value,
        keys={
            "conflictingevidence",
            "contradictingevidence",
            "contradictoryevidence",
            "divergenceevidence",
        },
        states=_CONTRADICTORY_STATES,
    )


def _contains_marker(value: Any, *, keys: set[str], states: set[str]) -> bool:
    if value in (None, ""):
        return False
    if isinstance(value, str):
        return _state_token(value) in states
    if isinstance(value, Mapping):
        for raw_key, nested in value.items():
            key = _compact_key(raw_key)
            if key in keys and _has_payload(nested):
                return True
            if key in {"state", "status", "readinesstier", "correlationstate", "freshness"}:
                if _contains_marker(nested, keys=keys, states=states):
                    return True
            if _contains_marker(nested, keys=keys, states=states):
                return True
        return False
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return any(_contains_marker(item, keys=keys, states=states) for item in value)
    return False


def _unsafe_input_count(value: Any) -> int:
    count = 0
    if isinstance(value, Mapping):
        for raw_key, nested in value.items():
            if _is_unsafe_key(raw_key):
                count += 1
                continue
            count += _unsafe_input_count(nested)
        return count
    if isinstance(value, str):
        return 1 if _is_unsafe_text(value) else 0
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return sum(_unsafe_input_count(item) for item in value)
    return 0


def _is_unsafe_key(value: Any) -> bool:
    key = _compact_key(value)
    if key in {"providerroutingchanged"}:
        return False
    return bool(_UNSAFE_KEY_RE.search(str(value or "")) or key in {"sourceref", "sourcerefid"})


def _is_unsafe_text(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and (_UNSAFE_TEXT_RE.search(text) or _ADVICE_RE.search(text)))


def _safe_symbol(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text or _is_unsafe_text(text):
        return ""
    return re.sub(r"[^A-Z0-9._-]", "", text)[:24]


def _safe_label(value: Any) -> str:
    text = " ".join(str(value or "").split())
    if not text or _is_unsafe_text(text):
        return ""
    return text[:80]


def _state_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _compact_key(value: Any) -> str:
    return "".join(char for char in str(value or "").lower() if char.isalnum())


def _dedupe_text(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _dedupe_evidence(values: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        item = dict(value)
        key = (str(item.get("surface") or ""), str(item.get("label") or ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


__all__ = [
    "CROSS_SURFACE_RESEARCH_SYNTHESIS_CONTRACT_VERSION",
    "CROSS_SURFACE_RESEARCH_SYNTHESIS_NO_ADVICE_DISCLOSURE",
    "compose_cross_surface_research_synthesis",
]
