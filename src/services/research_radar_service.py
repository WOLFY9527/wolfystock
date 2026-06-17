# -*- coding: utf-8 -*-
"""Read-only Research Radar API projection service."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import quote

from src.multi_user import OWNERSHIP_SCOPE_USER
from src.services.market_scanner_candidate_evidence import (
    build_scanner_candidate_evidence_frame,
    build_scanner_candidate_research_readiness,
)
from src.services.market_scanner_candidate_summary import build_scanner_candidate_research_summary_frame
from src.services.research_radar_candidate_engine import build_research_radar_candidate_queue


RESEARCH_RADAR_API_SCHEMA_VERSION = "research_radar_api_v1"
NO_ADVICE_DISCLOSURE = "Research-only queue; verify evidence gaps before further review."
_MISSING_SCANNER_CANDIDATES = "scannerCandidates"
_PRIORITIES = ("high", "medium", "low")
_OBSERVATION_ONLY = True
_DECISION_GRADE = False
_STARTER_RESEARCH_WORKFLOW = [
    "Open Market Overview to set broad context.",
    "Create one watchlist item for a symbol you already want to observe.",
    "Run scanner to generate research candidates for review.",
    "Return to Research Radar after adding watchlist context.",
]
_FIRST_RUN_CHECKLIST = [
    "Market Overview checked for context.",
    "First watchlist item created by the user.",
    "Scanner run completed by the user.",
    "Research Radar reviewed again after watchlist context exists.",
]
_EMPTY_STATE_ACTIONS = [
    {
        "label": "Open Market Overview",
        "route": "/market-overview",
        "description": "Start with broad market context before choosing symbols to observe.",
    },
    {
        "label": "Create first watchlist item",
        "route": "/watchlist",
        "description": "Add a symbol you already want to observe so research surfaces have user context.",
    },
    {
        "label": "Run scanner",
        "route": "/scanner",
        "description": "Generate research candidates for observation and evidence review.",
    },
    {
        "label": "Review Research Radar again",
        "route": "/research/radar",
        "description": "Return after watchlist or scanner context exists.",
    },
]
_SUGGESTED_RESEARCH_ENTRYPOINTS = [
    {
        "surface": "Market Overview",
        "route": "/market-overview",
        "description": "Review broad context before adding symbols.",
    },
    {
        "surface": "Watchlist",
        "route": "/watchlist",
        "description": "Create the first user-chosen symbol to observe.",
    },
    {
        "surface": "Scanner",
        "route": "/scanner",
        "description": "Run scanner to produce user-scoped research candidates.",
    },
    {
        "surface": "Research Radar",
        "route": "/research/radar",
        "description": "Recheck the queue after watchlist or scanner evidence exists.",
    },
]

_DEFAULT_CONSUMER_DESCRIPTOR = {
    "label": "Evidence needs review",
    "message": "Some quality checks are not fully cleared yet.",
    "severity": "info",
    "category": "evidence",
}

_RESEARCH_BIAS_DESCRIPTORS = {
    "avoidlowevidence": {
        "label": "Low-evidence filter active",
        "message": "The queue is keeping this item cautious until evidence improves.",
        "severity": "warning",
        "category": "research",
    },
    "strengthcontinuation": {
        "label": "Strength observation",
        "message": "Relative strength and structure are visible enough for research follow-up.",
        "severity": "info",
        "category": "research",
    },
    "volatilityrisk": {
        "label": "Volatility risk needs review",
        "message": "Volatility may limit confidence until the setup stabilizes.",
        "severity": "warning",
        "category": "risk",
    },
    "pullbackwatch": {
        "label": "Pullback structure watch",
        "message": "The item needs follow-up around its pullback structure.",
        "severity": "info",
        "category": "research",
    },
    "eventdriven": {
        "label": "Event-driven observation",
        "message": "Event context is visible and needs confirmation.",
        "severity": "info",
        "category": "events",
    },
    "breakoutwatch": {
        "label": "Breakout structure watch",
        "message": "Structure and participation need continued verification.",
        "severity": "info",
        "category": "research",
    },
    "mixed": {
        "label": "Mixed evidence profile",
        "message": "Drivers are mixed, so the item remains in research review.",
        "severity": "info",
        "category": "research",
    },
}

_RISK_FLAG_DESCRIPTORS = {
    "low_liquidity": {
        "label": "Liquidity is limited",
        "message": "Liquidity evidence is limited for this item.",
        "severity": "warning",
        "category": "liquidity",
    },
    "missing_evidence": {
        "label": "Evidence missing",
        "message": "Required evidence is missing.",
        "severity": "warning",
        "category": "evidence",
    },
    "low_evidence_quality": {
        "label": "Evidence quality is limited",
        "message": "Evidence quality is not strong enough for a higher-confidence read.",
        "severity": "warning",
        "category": "evidence",
    },
    "theme_regime_conflict": {
        "label": "Market backdrop conflict",
        "message": "Theme context conflicts with the current market backdrop.",
        "severity": "warning",
        "category": "market",
    },
    "mixed_regime": {
        "label": "Mixed market backdrop",
        "message": "The market backdrop is mixed, so confidence remains capped.",
        "severity": "info",
        "category": "market",
    },
    "theme_concentration": {
        "label": "Theme concentration",
        "message": "Similar theme entries are limiting queue diversity.",
        "severity": "info",
        "category": "research",
    },
    "extreme_extension": {
        "label": "Extended structure",
        "message": "The structure appears extended and needs follow-up.",
        "severity": "warning",
        "category": "risk",
    },
    "elevated_volatility": {
        "label": "Volatility elevated",
        "message": "Volatility is elevated and needs follow-up.",
        "severity": "warning",
        "category": "risk",
    },
}

_EVIDENCE_GAP_DESCRIPTORS = {
    "fundamentals": {
        "label": "Company evidence missing",
        "message": "Company-level evidence is missing.",
        "severity": "info",
        "category": "evidence",
    },
    "news": {
        "label": "Media context missing",
        "message": "Media context is missing.",
        "severity": "info",
        "category": "evidence",
    },
    "catalyst": {
        "label": "Event context missing",
        "message": "Event context is missing.",
        "severity": "info",
        "category": "events",
    },
    "freshness": {
        "label": "Recency check missing",
        "message": "A recency check is missing.",
        "severity": "info",
        "category": "recency",
    },
    "themebreadth": {
        "label": "Theme breadth needs review",
        "message": "Theme breadth needs more confirmation.",
        "severity": "info",
        "category": "evidence",
    },
    "scannercandidates": {
        "label": "Research candidates unavailable",
        "message": "Research candidates are not available for this payload.",
        "severity": "warning",
        "category": "research",
    },
    "staleevidence": {
        "label": "Recency check needs review",
        "message": "Evidence recency needs review.",
        "severity": "warning",
        "category": "recency",
    },
    "fallbackevidence": {
        "label": "Fallback evidence present",
        "message": "Some evidence uses fallback context.",
        "severity": "warning",
        "category": "evidence",
    },
    "proxyevidence": {
        "label": "Proxy evidence present",
        "message": "Some evidence uses proxy context.",
        "severity": "warning",
        "category": "evidence",
    },
    "sampleonlyevidence": {
        "label": "Sample-only evidence present",
        "message": "Some evidence is sample-only.",
        "severity": "warning",
        "category": "evidence",
    },
    "evidencequality": {
        "label": "Evidence quality needs review",
        "message": "Evidence quality needs review.",
        "severity": "warning",
        "category": "evidence",
    },
}


class ResearchRadarService:
    """Build a consumer-safe research radar queue from already-available evidence."""

    def __init__(
        self,
        *,
        scanner_repository: object | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.scanner_repository = scanner_repository
        self._now = now or (lambda: datetime.now(timezone.utc))

    def build_from_latest_scanner_run(
        self,
        *,
        market: str | None = None,
        profile: str | None = None,
        owner_id: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Read recent scanner candidates and build a fail-closed radar payload."""

        source = {
            "type": "scanner",
            "scannerRunId": None,
            "market": _optional_token(market),
            "profile": _optional_token(profile),
        }
        if self.scanner_repository is None or not owner_id:
            return self.build_radar(candidates=[], source=source)

        try:
            runs = self.scanner_repository.get_recent_runs(
                market=_optional_token(market),
                profile=_optional_token(profile),
                limit=max(1, min(int(limit or 20), 20)),
                scope=OWNERSHIP_SCOPE_USER,
                owner_id=str(owner_id),
                include_all_owners=False,
            )
            for run in runs:
                if _text(getattr(run, "status", "")).lower() != "completed":
                    continue
                candidates = list(self.scanner_repository.get_candidates_for_run(int(getattr(run, "id"))))
                if not candidates:
                    continue
                source.update(
                    {
                        "scannerRunId": int(getattr(run, "id")),
                        "market": _optional_token(getattr(run, "market", None)),
                        "profile": _optional_token(getattr(run, "profile", None)),
                    }
                )
                return self.build_radar(
                    candidates=[_scanner_candidate_to_engine_input(candidate) for candidate in candidates],
                    source=source,
                )
        except Exception:
            source["readState"] = "degraded"
            return self.build_radar(candidates=[], source=source)

        return self.build_radar(candidates=[], source=source)

    def build_radar(
        self,
        *,
        candidates: Sequence[Mapping[str, Any] | Any] | None,
        market_regime_context: Mapping[str, Any] | Any | None = None,
        stock_structure_context: Mapping[str, Any] | Any | None = None,
        theme_leadership_context: Mapping[str, Any] | Any | None = None,
        evidence_quality_metadata: Mapping[str, Any] | Any | None = None,
        source: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Project candidate-engine output into the backend API contract."""

        candidate_payloads = [_mapping(candidate) for candidate in candidates or []]
        candidate_payloads = [candidate for candidate in candidate_payloads if _symbol_from(candidate)]
        by_symbol = {_symbol_from(candidate): candidate for candidate in candidate_payloads}

        engine_payload = build_research_radar_candidate_queue(
            candidate_payloads,
            market_regime_context=market_regime_context,
            stock_structure_context=stock_structure_context,
            theme_leadership_context=theme_leadership_context,
            evidence_quality_metadata=evidence_quality_metadata,
        )
        engine_summary = _mapping(engine_payload.get("summary"))
        queue = [
            self._project_queue_item(item, by_symbol.get(_symbol_from(item), {}))
            for item in list(engine_payload.get("researchQueue") or [])
        ]
        evidence_gaps_raw = _dedupe(
            [
                *list(engine_summary.get("evidenceGaps") or []),
                *[
                    gap
                    for item in queue
                    for gap in list(_mapping(item.get("evidenceQuality")).get("missingEvidenceRaw") or [])
                ],
                *[
                    gap
                    for item in queue
                    for gap in list(item.get("evidenceGapsRaw") or [])
                ],
            ]
        )
        if not queue:
            evidence_gaps_raw = [_MISSING_SCANNER_CANDIDATES]
        evidence_gaps = _descriptor_labels(_evidence_gap_descriptors(evidence_gaps_raw))

        market_context_fit = _text(engine_summary.get("marketContextFit")) or "neutral"
        if not queue and not _mapping(market_regime_context):
            market_context_fit = "unavailable"

        aggregate_summary = self._aggregate_summary(
            queue=queue,
            engine_summary=engine_summary,
            source=source,
            candidate_count=len(candidate_payloads),
        )
        data_quality = self._data_quality(queue=queue, evidence_gaps_raw=evidence_gaps_raw)
        consumer_issues = _dedupe_descriptors(
            [
                *list(data_quality.get("consumerIssues") or []),
                *[
                    issue
                    for item in queue
                    for issue in list(item.get("consumerIssues") or [])
                ],
            ]
        )
        drilldown_targets = _dedupe_drilldown_targets(
            target
            for item in queue
            for target in list(item.get("drilldownTargets") or [])
        )
        onboarding_contract = _empty_consumer_onboarding_contract(
            queue=queue,
            candidate_count=len(candidate_payloads),
            queue_quality=_text(aggregate_summary.get("queueQuality")),
        )

        return {
            "schemaVersion": RESEARCH_RADAR_API_SCHEMA_VERSION,
            "generatedAt": _iso_timestamp(self._now()),
            "researchQueue": queue,
            "aggregateSummary": aggregate_summary,
            "evidenceGaps": evidence_gaps,
            "evidenceGapsRaw": evidence_gaps_raw,
            "marketContextFit": market_context_fit,
            "drilldownTargets": drilldown_targets,
            "consumerIssues": consumer_issues,
            "onboardingGuidance": onboarding_contract["onboardingGuidance"],
            "emptyStateActions": onboarding_contract["emptyStateActions"],
            "starterResearchWorkflow": onboarding_contract["starterResearchWorkflow"],
            "firstRunChecklist": onboarding_contract["firstRunChecklist"],
            "suggestedResearchEntrypoints": onboarding_contract["suggestedResearchEntrypoints"],
            "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
            "dataQuality": data_quality,
            "observationOnly": _OBSERVATION_ONLY,
            "decisionGrade": _DECISION_GRADE,
        }

    def _project_queue_item(
        self,
        item: Mapping[str, Any],
        source_candidate: Mapping[str, Any],
    ) -> dict[str, Any]:
        symbol = _symbol_from(item)
        explanation = _mapping(item.get("explanation"))
        driver_scores = _mapping(item.get("driverScores"))
        evidence_quality = _candidate_evidence_quality(source_candidate, driver_scores)
        research_bias_raw = _text(item.get("researchBias")) or "mixed"
        research_bias = _research_bias_descriptor(research_bias_raw)
        evidence_gaps_raw = _safe_text_list(explanation.get("evidenceGaps"))
        evidence_gap_descriptors = _evidence_gap_descriptors(evidence_gaps_raw)
        risk_flags_raw = _safe_text_list(item.get("riskFlags"))
        risk_flag_descriptors = _risk_flag_descriptors(risk_flags_raw)
        evidence_quality["missingEvidenceRaw"] = _safe_text_list(evidence_quality.get("missingEvidence"))
        evidence_quality["missingEvidence"] = _descriptor_labels(
            _evidence_gap_descriptors(evidence_quality["missingEvidenceRaw"])
        )
        consumer_issues = _dedupe_descriptors(
            [
                research_bias,
                *evidence_gap_descriptors,
                *risk_flag_descriptors,
                *_evidence_gap_descriptors(evidence_quality.get("missingEvidenceRaw") or []),
            ]
        )
        drilldown_targets = _drilldown_targets(symbol)
        return {
            "symbol": symbol,
            "ticker": symbol,
            "priority": _priority(item.get("priority")),
            "researchBias": research_bias["label"],
            "researchBiasRaw": research_bias_raw,
            "researchBiasLabel": research_bias["label"],
            "researchBiasMessage": research_bias["message"],
            "driverScores": dict(driver_scores),
            "whyOnRadar": _safe_text_list(explanation.get("whyOnRadar")),
            "whatToVerify": _safe_text_list(explanation.get("whatToVerify")),
            "whyNotHigherPriority": _safe_text_list(explanation.get("whyNotHigherPriority")),
            "evidenceGaps": _descriptor_labels(evidence_gap_descriptors),
            "evidenceGapsRaw": evidence_gaps_raw,
            "consumerEvidenceGaps": evidence_gap_descriptors,
            "invalidationObservations": _safe_text_list(explanation.get("invalidationObservations")),
            "duplicateEvidenceMerged": int(item.get("duplicateEvidenceMerged") or 0),
            "riskFlags": _descriptor_labels(risk_flag_descriptors),
            "riskFlagsRaw": risk_flags_raw,
            "riskFlagLabels": _descriptor_labels(risk_flag_descriptors),
            "evidenceQuality": evidence_quality,
            "consumerIssues": consumer_issues,
            "drilldownTargets": drilldown_targets,
            "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
            "observationOnly": _OBSERVATION_ONLY,
            "decisionGrade": _DECISION_GRADE,
        }

    def _aggregate_summary(
        self,
        *,
        queue: Sequence[Mapping[str, Any]],
        engine_summary: Mapping[str, Any],
        source: Mapping[str, Any] | None,
        candidate_count: int,
    ) -> dict[str, Any]:
        priority_counts = {
            priority: sum(1 for item in queue if item.get("priority") == priority)
            for priority in _PRIORITIES
        }
        queue_quality = _text(engine_summary.get("queueQuality")) or "thin"
        if not queue:
            queue_quality = "degraded"
        return {
            "candidateCount": int(candidate_count),
            "queueCount": len(queue),
            "priorityCounts": priority_counts,
            "dominantThemes": _safe_text_list(engine_summary.get("dominantThemes")),
            "queueQuality": queue_quality,
            "duplicateEvidenceMerged": int(engine_summary.get("duplicateEvidenceMerged") or 0),
            "queueDiversity": dict(_mapping(engine_summary.get("queueDiversity"))),
            "source": dict(source or {"type": "direct"}),
        }

    @staticmethod
    def _data_quality(
        *,
        queue: Sequence[Mapping[str, Any]],
        evidence_gaps_raw: Sequence[str],
    ) -> dict[str, Any]:
        evidence_gaps = _descriptor_labels(_evidence_gap_descriptors(evidence_gaps_raw))
        if not queue:
            return {
                "status": "degraded",
                "availableCandidateCount": 0,
                "reliableCandidateCount": 0,
                "missingEvidence": list(evidence_gaps),
                "missingEvidenceRaw": list(evidence_gaps_raw),
                "consumerIssues": _evidence_gap_descriptors(evidence_gaps_raw),
            }

        quality_payloads = [_mapping(item.get("evidenceQuality")) for item in queue]
        reliable_count = sum(
            1
            for item in quality_payloads
            if _text(item.get("status")) in {"complete", "available"} and float(item.get("score") or 0) >= 60
        )
        weak_count = sum(1 for item in quality_payloads if _text(item.get("status")) in {"missing", "unavailable"})
        status = "ready" if reliable_count == len(queue) and not evidence_gaps else "partial"
        if weak_count == len(queue):
            status = "degraded"
        return {
            "status": status,
            "availableCandidateCount": len(queue),
            "reliableCandidateCount": reliable_count,
            "missingEvidence": list(evidence_gaps),
            "missingEvidenceRaw": list(evidence_gaps_raw),
            "consumerIssues": _evidence_gap_descriptors(evidence_gaps_raw),
        }


def _research_bias_descriptor(value: Any) -> dict[str, str]:
    return _descriptor_for(value, _RESEARCH_BIAS_DESCRIPTORS)


def _risk_flag_descriptors(values: Sequence[str]) -> list[dict[str, str]]:
    return _dedupe_descriptors(_descriptor_for(value, _RISK_FLAG_DESCRIPTORS) for value in values)


def _evidence_gap_descriptors(values: Sequence[str]) -> list[dict[str, str]]:
    return _dedupe_descriptors(_descriptor_for(value, _EVIDENCE_GAP_DESCRIPTORS) for value in values)


def _descriptor_for(value: Any, mapping: Mapping[str, Mapping[str, str]]) -> dict[str, str]:
    raw = _text(value)
    key = raw.lower()
    descriptor = mapping.get(key) or mapping.get(_compact_descriptor_key(raw)) or _DEFAULT_CONSUMER_DESCRIPTOR
    return dict(descriptor)


def _compact_descriptor_key(value: Any) -> str:
    return "".join(ch for ch in _text(value).lower() if ch.isalnum())


def _descriptor_labels(descriptors: Sequence[Mapping[str, str]]) -> list[str]:
    return _dedupe(str(descriptor.get("label") or "") for descriptor in descriptors)


def _dedupe_descriptors(descriptors: Iterable[Mapping[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for descriptor in descriptors:
        item = {
            "label": _text(descriptor.get("label")) or _DEFAULT_CONSUMER_DESCRIPTOR["label"],
            "message": _text(descriptor.get("message")) or _DEFAULT_CONSUMER_DESCRIPTOR["message"],
            "severity": _text(descriptor.get("severity")) or _DEFAULT_CONSUMER_DESCRIPTOR["severity"],
            "category": _text(descriptor.get("category")) or _DEFAULT_CONSUMER_DESCRIPTOR["category"],
        }
        key = (item["label"], item["message"], item["severity"], item["category"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _drilldown_targets(symbol: str) -> list[dict[str, str]]:
    if not symbol:
        return []
    encoded_symbol = quote(symbol, safe="")
    return [
        {
            "label": "Structure detail",
            "route": f"/stocks/{encoded_symbol}/structure-decision",
            "reason": "Open the structure workspace for this ticker.",
        }
    ]


def _dedupe_drilldown_targets(targets: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for target in targets:
        label = _text(target.get("label"))
        route = _text(target.get("route"))
        reason = _text(target.get("reason"))
        if not label or not route:
            continue
        key = (label, route, reason)
        if key in seen:
            continue
        seen.add(key)
        item = {"label": label, "route": route}
        if reason:
            item["reason"] = reason
        result.append(item)
    return result


def _empty_consumer_onboarding_contract(
    *,
    queue: Sequence[Mapping[str, Any]],
    candidate_count: int,
    queue_quality: str,
) -> dict[str, Any]:
    is_thin_queue = _text(queue_quality).lower() in {"thin", "low_evidence", "degraded"}
    if queue and not is_thin_queue:
        return {
            "onboardingGuidance": None,
            "emptyStateActions": [],
            "starterResearchWorkflow": [],
            "firstRunChecklist": [],
            "suggestedResearchEntrypoints": [],
        }

    conditions = []
    if queue:
        conditions.append("Research Radar queue is thin.")
    else:
        conditions.append("Research Radar has no queue items yet.")
    if candidate_count <= 0 and not queue:
        conditions.append("No scanner candidates were found for this user scope.")
    return {
        "onboardingGuidance": {
            "title": "Start a research loop",
            "summary": (
                "Use Market Overview, Watchlist, Scanner, and Research Radar to build an observation-only "
                "research loop."
            ),
            "conditionsDetected": conditions,
        },
        "emptyStateActions": [dict(item) for item in _EMPTY_STATE_ACTIONS],
        "starterResearchWorkflow": list(_STARTER_RESEARCH_WORKFLOW),
        "firstRunChecklist": list(_FIRST_RUN_CHECKLIST),
        "suggestedResearchEntrypoints": [dict(item) for item in _SUGGESTED_RESEARCH_ENTRYPOINTS],
    }


def _scanner_candidate_to_engine_input(candidate: Any) -> dict[str, Any]:
    diagnostics = _json_load(getattr(candidate, "diagnostics_json", None), {})
    component_scores = _mapping(diagnostics.get("component_scores"))
    payload = {
        "symbol": _text(getattr(candidate, "symbol", "")).upper(),
        "name": _text(getattr(candidate, "name", "")),
        "rank": _safe_int(getattr(candidate, "rank", 0)) or 0,
        "score": _safe_float(getattr(candidate, "score", None)) or 0.0,
        "final_score": _safe_float(getattr(candidate, "score", None)) or 0.0,
        "quality_hint": _text(getattr(candidate, "quality_hint", "")),
        "reason_summary": _text(getattr(candidate, "reason_summary", "")),
        "reasons": _json_load(getattr(candidate, "reasons_json", None), []),
        "key_metrics": _json_load(getattr(candidate, "key_metrics_json", None), []),
        "feature_signals": _json_load(getattr(candidate, "feature_signals_json", None), []),
        "risk_notes": _json_load(getattr(candidate, "risk_notes_json", None), []),
        "watch_context": _json_load(getattr(candidate, "watch_context_json", None), []),
        "boards": _json_load(getattr(candidate, "boards_json", None), []),
        "diagnostics": diagnostics,
    }
    evidence_frame = build_scanner_candidate_evidence_frame(payload)
    readiness = build_scanner_candidate_research_readiness(payload, candidate_evidence_frame=evidence_frame)
    summary = build_scanner_candidate_research_summary_frame(
        payload,
        candidate_evidence_frame=evidence_frame,
        candidate_research_readiness=readiness,
    )
    missing_evidence = _dedupe(
        [
            *list(readiness.get("missingEvidence") or []),
            *list(summary.get("missingEvidence") or []),
        ]
    )
    evidence_score = _evidence_score_from_frame(evidence_frame)
    return {
        "ticker": payload["symbol"],
        "relativeStrength": payload["score"],
        "volumeExpansion": _safe_float(component_scores.get("volume")) or None,
        "trendScore": _safe_float(component_scores.get("trend")) or None,
        "trendStructure": summary.get("scoreBand") or payload.get("quality_hint") or "mixed",
        "themes": payload["boards"],
        "avgDollarVolume": _first_number(
            payload,
            diagnostics,
            keys=("avgDollarVolume", "avg_dollar_volume", "avg_amount_20", "amount", "turnover"),
        ),
        "evidenceQuality": {
            "state": _evidence_status_from_readiness(readiness, evidence_score),
            "score": evidence_score,
            "missing": missing_evidence,
        },
    }


def _candidate_evidence_quality(
    source_candidate: Mapping[str, Any],
    driver_scores: Mapping[str, Any],
) -> dict[str, Any]:
    raw = _mapping(
        source_candidate.get("evidenceQuality")
        or source_candidate.get("evidence_quality")
        or source_candidate.get("evidence")
    )
    score = _safe_int(driver_scores.get("evidenceQuality")) or _safe_int(raw.get("score")) or 0
    status = _text(raw.get("state") or raw.get("status") or raw.get("evidenceQuality") or raw.get("quality"))
    if not status:
        if score >= 70:
            status = "complete"
        elif score >= 45:
            status = "partial"
        else:
            status = "missing"
    missing = _safe_text_list(raw.get("missing") or raw.get("missingEvidence") or raw.get("evidenceGaps") or raw.get("gaps"))
    if status in {"missing", "insufficient", "unavailable", "blocked"} and not missing:
        missing = ["evidenceQuality"]
    return {
        "status": _public_evidence_status(status),
        "score": score,
        "missingEvidence": missing,
    }


def _evidence_score_from_frame(frame: Mapping[str, Any]) -> int:
    coverage = _mapping(frame.get("coverage"))
    total = _safe_int(coverage.get("totalCount")) or 0
    if total <= 0:
        return 0
    available = _safe_int(coverage.get("availableCount")) or 0
    partial = _safe_int(coverage.get("partialCount")) or 0
    return int(round(((available + partial * 0.5) / total) * 100))


def _evidence_status_from_readiness(readiness: Mapping[str, Any], score: int) -> str:
    state = _text(readiness.get("readinessState")).lower()
    if state == "ready" or score >= 70:
        return "complete"
    if state in {"blocked", "unavailable"} or score < 35:
        return "missing"
    return "partial"


def _public_evidence_status(status: str) -> str:
    normalized = _text(status).lower()
    if normalized in {"complete", "confirmed", "available", "sufficient", "deterministic"}:
        return "complete" if normalized == "complete" else "available"
    if normalized in {"missing", "insufficient"}:
        return "missing"
    if normalized in {"unavailable", "blocked"}:
        return "unavailable"
    return "partial"


def _priority(value: Any) -> str:
    normalized = _text(value).lower()
    return normalized if normalized in _PRIORITIES else "low"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _json_load(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _symbol_from(value: Mapping[str, Any]) -> str:
    return _text(value.get("ticker") or value.get("symbol") or value.get("code")).upper()


def _optional_token(value: Any) -> str | None:
    token = _text(value).lower()
    return token or None


def _safe_text_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, Mapping):
        values: Iterable[Any] = value.values()
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = [value]
    return _dedupe(_text(item) for item in values if _text(item))


def _dedupe(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = _text(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _first_number(*mappings: Mapping[str, Any], keys: Sequence[str]) -> float | None:
    for mapping in mappings:
        for key in keys:
            number = _safe_float(mapping.get(key))
            if number is not None:
                return number
    return None


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
    "NO_ADVICE_DISCLOSURE",
    "RESEARCH_RADAR_API_SCHEMA_VERSION",
    "ResearchRadarService",
]
