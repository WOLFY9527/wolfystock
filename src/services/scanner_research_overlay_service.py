# -*- coding: utf-8 -*-
"""Read-only research overlay projection for finalized scanner candidates."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping, Sequence

from src.services.consumer_issue_labels import build_consumer_issues


SCANNER_RESEARCH_OVERLAY_SCHEMA_VERSION = "scanner_research_overlay_v1"
SCANNER_RESEARCH_OVERLAY_NO_ADVICE_DISCLOSURE = (
    "Research-only scanner overlay; verify evidence gaps before further review."
)

_CORE_EVIDENCE_KEYS = ("candidateEvidenceFrame", "candidateResearchReadiness", "candidateResearchSummaryFrame")
_MISSING_SCANNER_CANDIDATES = "scannerCandidates"


class ScannerResearchOverlayService:
    """Build an additive scanner research overlay from already-finalized candidates."""

    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(timezone.utc))

    def build_overlay(
        self,
        *,
        run: Mapping[str, Any] | None,
        candidates: Sequence[Mapping[str, Any] | Any] | None,
    ) -> dict[str, Any]:
        run_payload = copy.deepcopy(_mapping(run))
        candidate_payloads = [copy.deepcopy(_mapping(candidate)) for candidate in candidates or []]
        candidate_payloads = [candidate for candidate in candidate_payloads if _ticker(candidate)]

        items = [self._candidate_overlay(candidate, run_payload) for candidate in candidate_payloads]
        missing_evidence = _dedupe(
            [
                gap
                for item in items
                for gap in list(item.get("evidenceGaps") or [])
            ]
        )
        if not candidate_payloads:
            missing_evidence = [_MISSING_SCANNER_CANDIDATES]

        data_quality = self._data_quality(items=items, missing_evidence=missing_evidence)
        return {
            "schemaVersion": SCANNER_RESEARCH_OVERLAY_SCHEMA_VERSION,
            "generatedAt": _iso_timestamp(self._now()),
            "runId": _safe_int(run_payload.get("id")),
            "market": _text(run_payload.get("market")),
            "profile": _text(run_payload.get("profile")),
            "items": items,
            "aggregateSummary": self._aggregate_summary(items),
            "queueDiversity": self._queue_diversity(items),
            "dataQuality": data_quality,
            "missingEvidence": missing_evidence,
            "consumerIssues": build_consumer_issues(
                missing_evidence,
                data_quality,
                [item.get("riskFlags") for item in items],
                [item.get("evidenceGaps") for item in items],
            ),
            "noAdviceDisclosure": SCANNER_RESEARCH_OVERLAY_NO_ADVICE_DISCLOSURE,
        }

    def _candidate_overlay(
        self,
        candidate: Mapping[str, Any],
        run: Mapping[str, Any],
    ) -> dict[str, Any]:
        ticker = _ticker(candidate)
        evidence_quality = _evidence_quality(candidate)
        evidence_gaps = _candidate_evidence_gaps(candidate, evidence_quality)
        sufficient = evidence_quality["status"] != "insufficient"
        risk_flags = _risk_flags(candidate, evidence_quality, evidence_gaps)

        if not sufficient:
            risk_flags = [
                "insufficient_candidate_evidence",
                *[flag for flag in risk_flags if flag != "insufficient_candidate_evidence"],
            ]

        return {
            "ticker": ticker,
            "originalScannerCandidateState": {
                "ticker": ticker,
                "rank": _safe_int(candidate.get("rank")) or 0,
                "score": _safe_float(candidate.get("score")),
                "rawScore": _safe_float(candidate.get("raw_score") or candidate.get("rawScore")),
                "finalScore": _safe_float(candidate.get("final_score") or candidate.get("finalScore")),
                "status": _text(candidate.get("status")) or "selected",
            },
            "researchPriority": _research_priority(candidate, evidence_quality, sufficient),
            "regimeFit": _regime_fit(run, sufficient),
            "themeAlignment": _theme_alignment(candidate, run, sufficient),
            "evidenceQuality": evidence_quality,
            "whyThisMattersToday": _why_this_matters_today(candidate, run) if sufficient else [],
            "whatToVerify": _what_to_verify(candidate, evidence_gaps),
            "riskFlags": risk_flags,
            "evidenceGaps": evidence_gaps,
            "consumerIssues": build_consumer_issues(evidence_gaps, risk_flags, evidence_quality),
            "noAdviceDisclosure": SCANNER_RESEARCH_OVERLAY_NO_ADVICE_DISCLOSURE,
        }

    @staticmethod
    def _aggregate_summary(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        priorities = ("high", "medium", "low", "insufficient_evidence")
        return {
            "candidateCount": len(items),
            "priorityCounts": {
                priority: sum(1 for item in items if item.get("researchPriority") == priority)
                for priority in priorities
            },
            "riskFlagCount": sum(len(item.get("riskFlags") or []) for item in items),
            "evidenceGapCount": len(_dedupe(gap for item in items for gap in list(item.get("evidenceGaps") or []))),
        }

    @staticmethod
    def _queue_diversity(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        themes = _dedupe(
            theme
            for item in items
            for theme in list(_mapping(item.get("themeAlignment")).get("themes") or [])
        )
        if not items:
            status = "unavailable"
        elif len(themes) <= 1:
            status = "concentrated"
        elif len(themes) >= min(3, len(items)):
            status = "diversified"
        else:
            status = "mixed"
        return {
            "status": status,
            "themeCount": len(themes),
            "themes": themes[:8],
        }

    @staticmethod
    def _data_quality(
        *,
        items: Sequence[Mapping[str, Any]],
        missing_evidence: Sequence[str],
    ) -> dict[str, Any]:
        if not items:
            return {
                "status": "degraded",
                "availableCandidateCount": 0,
                "reliableCandidateCount": 0,
                "missingEvidence": list(missing_evidence),
                "consumerIssues": build_consumer_issues(missing_evidence),
            }
        reliable_count = sum(
            1
            for item in items
            if _mapping(item.get("evidenceQuality")).get("status") in {"available", "complete"}
            and int(_mapping(item.get("evidenceQuality")).get("score") or 0) >= 60
        )
        insufficient_count = sum(
            1
            for item in items
            if _mapping(item.get("evidenceQuality")).get("status") == "insufficient"
        )
        if insufficient_count == len(items):
            status = "degraded"
        elif missing_evidence or insufficient_count:
            status = "partial"
        else:
            status = "ready"
        return {
            "status": status,
            "availableCandidateCount": len(items),
            "reliableCandidateCount": reliable_count,
            "missingEvidence": list(missing_evidence),
            "consumerIssues": build_consumer_issues(missing_evidence),
        }


def _evidence_quality(candidate: Mapping[str, Any]) -> dict[str, Any]:
    if not all(isinstance(candidate.get(key), Mapping) and candidate.get(key) for key in _CORE_EVIDENCE_KEYS):
        return {
            "status": "insufficient",
            "score": 0,
            "missingEvidence": [key for key in _CORE_EVIDENCE_KEYS if not _mapping(candidate.get(key))],
        }

    evidence_frame = _mapping(candidate.get("candidateEvidenceFrame"))
    readiness = _mapping(candidate.get("candidateResearchReadiness"))
    summary = _mapping(candidate.get("candidateResearchSummaryFrame"))
    coverage = _mapping(evidence_frame.get("coverage"))
    total = _safe_int(coverage.get("totalCount")) or 0
    available = _safe_int(coverage.get("availableCount")) or 0
    partial = _safe_int(coverage.get("partialCount")) or 0
    missing = _safe_int(coverage.get("missingCount")) or 0
    score = int(round(((available + partial * 0.5) / total) * 100)) if total > 0 else 0
    missing_evidence = _dedupe(
        [
            *list(readiness.get("missingEvidence") or []),
            *list(summary.get("missingEvidence") or []),
        ]
    )
    readiness_state = _text(readiness.get("readinessState") or summary.get("frameState")).lower()
    if score == 0 and missing:
        status = "insufficient"
    elif readiness_state in {"ready", "available"} and not missing_evidence:
        status = "complete"
    elif score >= 60:
        status = "available"
    elif score >= 35:
        status = "partial"
    else:
        status = "insufficient"
    return {
        "status": status,
        "score": score,
        "missingEvidence": missing_evidence,
    }


def _candidate_evidence_gaps(
    candidate: Mapping[str, Any],
    evidence_quality: Mapping[str, Any],
) -> list[str]:
    gaps = _dedupe(
        [
            *list(evidence_quality.get("missingEvidence") or []),
            *list(_mapping(candidate.get("consumerDiagnostics")).get("missingEvidence") or []),
            *list(_mapping(candidate.get("candidateResearchReadiness")).get("missingEvidence") or []),
            *list(_mapping(candidate.get("candidateResearchSummaryFrame")).get("missingEvidence") or []),
        ]
    )
    if evidence_quality.get("status") == "insufficient" and not gaps:
        return ["candidateEvidenceFrame"]
    return gaps


def _research_priority(
    candidate: Mapping[str, Any],
    evidence_quality: Mapping[str, Any],
    sufficient: bool,
) -> str:
    if not sufficient:
        return "insufficient_evidence"
    score = _safe_float(candidate.get("final_score") or candidate.get("score")) or 0.0
    evidence_score = int(evidence_quality.get("score") or 0)
    if score >= 78 and evidence_score >= 65:
        return "high"
    if score >= 60 and evidence_score >= 45:
        return "medium"
    return "low"


def _regime_fit(run: Mapping[str, Any], sufficient: bool) -> dict[str, Any]:
    if not sufficient:
        return {
            "state": "insufficient_evidence",
            "signals": [],
        }
    context = _mapping(run.get("scannerContextFrame"))
    refs = []
    for key in ("marketReadiness", "macroRegime", "liquidityFrame", "assetClassBias"):
        payload = _mapping(context.get(key))
        state = _text(payload.get("readinessState") or payload.get("state"))
        if state:
            refs.append({"key": key, "state": state})
    state_tokens = " ".join(ref["state"].lower() for ref in refs)
    if any(token in state_tokens for token in ("blocked", "unavailable")):
        state = "strained"
    elif refs:
        state = "aligned"
    else:
        state = "unknown"
    return {
        "state": state,
        "signals": refs,
    }


def _theme_alignment(
    candidate: Mapping[str, Any],
    run: Mapping[str, Any],
    sufficient: bool,
) -> dict[str, Any]:
    themes = _dedupe([*_text_list(candidate.get("boards")), *_text_list(candidate.get("themes"))])
    if not sufficient:
        return {
            "state": "insufficient_evidence",
            "themes": themes,
            "signals": [],
        }
    context = _mapping(run.get("scannerContextFrame"))
    theme_frame = _mapping(context.get("themeFrame"))
    signals = []
    if theme_frame:
        state = _text(theme_frame.get("readinessState") or theme_frame.get("state"))
        if state:
            signals.append({"key": "themeFrame", "state": state})
    return {
        "state": "aligned" if themes else "unknown",
        "themes": themes,
        "signals": signals,
    }


def _why_this_matters_today(candidate: Mapping[str, Any], run: Mapping[str, Any]) -> list[str]:
    summary = _mapping(candidate.get("candidateResearchSummaryFrame"))
    highlights = _text_list(summary.get("evidenceHighlights"))
    reason = _text(summary.get("primaryResearchReason") or candidate.get("reason_summary"))
    result = []
    if reason:
        result.append(reason)
    result.extend(highlights[:2])
    if _mapping(run.get("scannerContextFrame")).get("marketReadiness"):
        result.append("Scanner context is available for today's research review.")
    return _dedupe(result)[:4]


def _what_to_verify(candidate: Mapping[str, Any], evidence_gaps: Sequence[str]) -> list[str]:
    summary = _mapping(candidate.get("candidateResearchSummaryFrame"))
    readiness = _mapping(candidate.get("candidateResearchReadiness"))
    checks = [
        *_text_list(summary.get("nextResearchStep")),
        *_text_list(readiness.get("nextEvidenceNeeded")),
        *_text_list(candidate.get("watch_context")),
    ]
    if evidence_gaps:
        checks.append(f"Verify missing evidence: {', '.join(evidence_gaps[:3])}.")
    if not checks:
        checks.append("Verify evidence freshness and whether the scanner setup still fits today's context.")
    return _dedupe(checks)[:5]


def _risk_flags(
    candidate: Mapping[str, Any],
    evidence_quality: Mapping[str, Any],
    evidence_gaps: Sequence[str],
) -> list[str]:
    flags = _text_list(candidate.get("risk_notes"))
    diagnostics = _mapping(candidate.get("consumerDiagnostics"))
    flags.extend(_text_list(diagnostics.get("warningFlags")))
    if evidence_quality.get("status") == "insufficient":
        return ["insufficient_candidate_evidence"]
    freshness = _text(diagnostics.get("freshnessState")).lower()
    if freshness in {"stale", "fallback", "delayed"}:
        flags.append(f"{freshness}_evidence")
    if evidence_gaps:
        flags.append("evidence_gaps_present")
    return _dedupe(flags)[:8]


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _text_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    values: Iterable[Any]
    if isinstance(value, Mapping):
        values = value.values()
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = [value]
    return _dedupe(_text(item) for item in values if _text(item))


def _dedupe(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _ticker(candidate: Mapping[str, Any]) -> str:
    return _text(candidate.get("ticker") or candidate.get("symbol") or candidate.get("code")).upper()


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, "") or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    number = _safe_float(value)
    return int(round(number)) if number is not None else None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _iso_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


__all__ = [
    "SCANNER_RESEARCH_OVERLAY_NO_ADVICE_DISCLOSURE",
    "SCANNER_RESEARCH_OVERLAY_SCHEMA_VERSION",
    "ScannerResearchOverlayService",
]
