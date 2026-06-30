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
        backtest_sample_reader: Callable[[str], Mapping[str, Any] | None] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.scanner_repository = scanner_repository
        self.backtest_sample_reader = backtest_sample_reader
        self._now = now or (lambda: datetime.now(timezone.utc))

    def build_from_latest_scanner_run(
        self,
        *,
        market: str | None = None,
        profile: str | None = None,
        owner_id: str | None = None,
        limit: int = 20,
        market_regime_read_model: Mapping[str, Any] | Any | None = None,
    ) -> dict[str, Any]:
        """Read recent scanner candidates and build a fail-closed radar payload."""

        source = {
            "type": "scanner",
            "scannerRunId": None,
            "market": _optional_token(market),
            "profile": _optional_token(profile),
        }
        if self.scanner_repository is None or not owner_id:
            return self.build_radar(
                candidates=[],
                source=source,
                market_regime_read_model=market_regime_read_model,
            )

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
                scanner_lineage = _scanner_lineage_from_run(run)
                if scanner_lineage:
                    source["scannerLineage"] = scanner_lineage
                engine_candidates = [_scanner_candidate_to_engine_input(candidate) for candidate in candidates]
                engine_candidates = _filter_candidates_by_scanner_lineage(engine_candidates, scanner_lineage)
                return self.build_radar(
                    candidates=engine_candidates,
                    source=source,
                    market_regime_read_model=market_regime_read_model,
                )
        except Exception:
            source["readState"] = "degraded"
            return self.build_radar(
                candidates=[],
                source=source,
                market_regime_read_model=market_regime_read_model,
            )

        return self.build_radar(
            candidates=[],
            source=source,
            market_regime_read_model=market_regime_read_model,
        )

    def build_radar(
        self,
        *,
        candidates: Sequence[Mapping[str, Any] | Any] | None,
        market_regime_context: Mapping[str, Any] | Any | None = None,
        stock_structure_context: Mapping[str, Any] | Any | None = None,
        theme_leadership_context: Mapping[str, Any] | Any | None = None,
        evidence_quality_metadata: Mapping[str, Any] | Any | None = None,
        market_regime_read_model: Mapping[str, Any] | Any | None = None,
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
        evidence_hub = self._evidence_hub(
            queue=queue,
            candidate_payloads=candidate_payloads,
            data_quality=data_quality,
        )
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
            "evidenceHub": evidence_hub,
            "marketLevelFallback": _market_level_fallback(
                queue=queue,
                market_regime_read_model=market_regime_read_model,
            ),
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
            "reason": _safe_public_sentence(
                source_candidate.get("reason") or source_candidate.get("reason_summary"),
                fallback="Scanner surfaced this symbol from observable price, volume, or structure evidence.",
            ),
            "limitation": _safe_public_sentence(
                source_candidate.get("limitation"),
                fallback="Evidence remains observation-only and needs a freshness check before further research.",
            ),
            "nextCheck": _safe_public_sentence(
                source_candidate.get("nextCheck") or source_candidate.get("next_check"),
                fallback="Recheck price, volume, and evidence freshness on the next scanner run.",
            ),
            "dataFreshness": dict(_mapping(source_candidate.get("dataFreshness") or source_candidate.get("data_freshness"))),
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
            "scannerLineage": dict(_mapping(source_candidate.get("scannerLineage"))),
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

    def _evidence_hub(
        self,
        *,
        queue: Sequence[Mapping[str, Any]],
        candidate_payloads: Sequence[Mapping[str, Any]],
        data_quality: Mapping[str, Any],
    ) -> dict[str, Any]:
        scanner = _scanner_evidence_item(queue=queue, candidate_count=len(candidate_payloads))
        backtest = self._backtest_sample_evidence_item(queue=queue)
        stock = _stock_readiness_evidence_item(candidate_payloads=candidate_payloads, queue=queue)
        data_activation = _data_activation_evidence_item(
            scanner=scanner,
            backtest=backtest,
            stock=stock,
            data_quality=data_quality,
        )
        missing_states = [
            item
            for item in (scanner, backtest, stock, data_activation)
            if item["status"] != "available"
        ]
        return {
            "scannerCandidates": scanner,
            "backtestSamples": backtest,
            "stockReadiness": stock,
            "dataActivation": data_activation,
            "missingEvidenceStates": missing_states,
        }

    def _backtest_sample_evidence_item(
        self,
        *,
        queue: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        symbols = _dedupe(_symbol_from(item) for item in queue)[:5]
        if not symbols:
            return _evidence_item(
                key="backtest",
                label="Backtest samples",
                status="blocked",
                summary="Backtest sample evidence cannot be checked until a radar symbol exists.",
                blocker="No radar symbol is available for backtest sample lookup.",
                next_data_action="Run scanner to create radar symbols, then prepare backtest samples.",
            )
        if self.backtest_sample_reader is None:
            return _evidence_item(
                key="backtest",
                label="Backtest samples",
                status="blocked",
                summary="Backtest sample evidence is not connected for this radar view.",
                blocker="Backtest sample status is unavailable for this radar view.",
                next_data_action="Open Backtest and prepare samples for the radar symbols.",
                total_count=len(symbols),
                symbols=symbols,
            )

        rows: list[dict[str, Any]] = []
        for symbol in symbols:
            try:
                payload = _mapping(self.backtest_sample_reader(symbol) or {})
            except Exception:
                payload = {"_readFailed": True}
            rows.append(_backtest_symbol_sample_state(symbol, payload))

        available_count = sum(1 for row in rows if row["status"] == "available")
        partial_count = sum(1 for row in rows if row["status"] == "partial")
        status = "available" if available_count == len(rows) else "partial" if available_count or partial_count else "blocked"
        first_blocker = next((row["blocker"] for row in rows if row.get("blocker")), None)
        if status == "available":
            summary = "Prepared backtest samples are available for radar symbols."
            blocker = None
        elif status == "partial":
            summary = "Backtest sample evidence is partial across radar symbols."
            blocker = first_blocker or "Some radar symbols still need prepared backtest samples."
        else:
            summary = "Backtest samples are unavailable for radar symbols."
            blocker = first_blocker or "Backtest samples have not been prepared for the radar symbols."
        return _evidence_item(
            key="backtest",
            label="Backtest samples",
            status=status,
            summary=summary,
            blocker=blocker,
            next_data_action="Open Backtest and prepare or refresh samples for the radar symbols.",
            evidence_count=available_count,
            total_count=len(rows),
            symbols=symbols,
            details=[row["detail"] for row in rows],
        )


def _research_bias_descriptor(value: Any) -> dict[str, str]:
    return _descriptor_for(value, _RESEARCH_BIAS_DESCRIPTORS)


def _risk_flag_descriptors(values: Sequence[str]) -> list[dict[str, str]]:
    return _dedupe_descriptors(_descriptor_for(value, _RISK_FLAG_DESCRIPTORS) for value in values)


def _evidence_gap_descriptors(values: Sequence[str]) -> list[dict[str, str]]:
    return _dedupe_descriptors(_descriptor_for(value, _EVIDENCE_GAP_DESCRIPTORS) for value in values)


def _evidence_item(
    *,
    key: str,
    label: str,
    status: str,
    summary: str,
    blocker: str | None = None,
    next_data_action: str,
    evidence_count: int = 0,
    total_count: int = 0,
    symbols: Sequence[str] | None = None,
    details: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": _evidence_hub_status(status),
        "summary": summary,
        "blocker": blocker,
        "nextDataAction": next_data_action,
        "evidenceCount": max(0, int(evidence_count or 0)),
        "totalCount": max(0, int(total_count or 0)),
        "symbols": _dedupe(_text(symbol).upper() for symbol in symbols or []),
        "details": _dedupe(_text(detail) for detail in details or []),
        "observationOnly": _OBSERVATION_ONLY,
        "decisionGrade": _DECISION_GRADE,
    }


def _market_level_fallback(
    *,
    queue: Sequence[Mapping[str, Any]],
    market_regime_read_model: Mapping[str, Any] | Any | None,
) -> dict[str, Any] | None:
    if queue:
        return None
    read_model = _mapping(market_regime_read_model)
    if not read_model:
        return None

    readiness = _safe_readiness(read_model)
    regime = _safe_regime(read_model)
    cards = _market_level_fallback_cards(read_model)
    product_summary = _safe_public_sentence(
        read_model.get("productSummary"),
        fallback="Market-level evidence is available for context while candidate research is unavailable.",
    )
    next_operator_action = _safe_public_sentence(
        read_model.get("nextOperatorAction") or readiness.get("nextOperatorAction"),
        fallback="Resolve missing market evidence inputs, then rerun the read model.",
    )
    missing_families = _safe_text_list(
        read_model.get("missingDataFamilies") or readiness.get("missingDataFamilies")
    )
    blocked_surfaces = _safe_text_list(
        read_model.get("blockedProductSurfaces") or readiness.get("blockedProductSurfaces")
    )
    return {
        "available": True,
        "label": "Market-level context",
        "summary": (
            "Market-level evidence is available while candidate research is unavailable or has not executed."
            if readiness.get("label") == "product_ready"
            else "Market-level evidence is degraded or blocked; candidate research is unavailable or has not executed."
        ),
        "candidateGenerationExecuted": False,
        "candidateUnavailableReason": "scanner_candidates_unavailable",
        "regime": regime,
        "productSummary": product_summary,
        "evidenceCards": cards,
        "dataQuality": _safe_market_data_quality(read_model.get("dataQuality")),
        "readiness": readiness,
        "missingDataFamilies": missing_families,
        "blockedProductSurfaces": blocked_surfaces,
        "nextOperatorAction": next_operator_action,
        "observationOnly": _OBSERVATION_ONLY,
        "decisionGrade": _DECISION_GRADE,
    }


def _safe_regime(read_model: Mapping[str, Any]) -> dict[str, str]:
    regime = _mapping(read_model.get("regime"))
    return {
        "label": _safe_token(read_model.get("regimeLabel") or regime.get("label"), fallback="insufficient_data"),
        "status": _safe_token(read_model.get("regimeStatus") or regime.get("status") or read_model.get("status"), fallback="failed_closed"),
    }


def _safe_readiness(read_model: Mapping[str, Any]) -> dict[str, Any]:
    readiness = _mapping(read_model.get("readiness"))
    missing = _safe_text_list(readiness.get("missingDataFamilies") or read_model.get("missingDataFamilies"))
    blocked = _safe_text_list(readiness.get("blockedProductSurfaces") or read_model.get("blockedProductSurfaces"))
    return {
        "label": _safe_token(readiness.get("label"), fallback="failed_closed"),
        "status": _safe_token(readiness.get("status") or read_model.get("status"), fallback="failed_closed"),
        "missingDataFamilies": missing,
        "blockedProductSurfaces": blocked,
        "nextOperatorAction": _safe_public_sentence(
            readiness.get("nextOperatorAction") or read_model.get("nextOperatorAction"),
            fallback="Resolve missing market evidence inputs, then rerun the read model.",
        ),
    }


def _safe_market_data_quality(value: Any) -> dict[str, Any]:
    data_quality = _mapping(value)
    return {
        "adjustedCoverageState": _safe_token(data_quality.get("adjustedCoverageState"), fallback="missing"),
        "ohlcvCoverage": _safe_coverage_state(data_quality.get("ohlcvCoverage")),
        "quoteSnapshotCoverage": _safe_coverage_state(data_quality.get("quoteSnapshotCoverage")),
        "missingDataFamilies": _safe_text_list(data_quality.get("missingDataFamilies")),
        "blockedProductSurfaces": _safe_text_list(data_quality.get("blockedProductSurfaces")),
        "failClosedReasons": _safe_text_list(data_quality.get("failClosedReasons")),
    }


def _safe_coverage_state(value: Any) -> dict[str, Any]:
    coverage = _mapping(value)
    result = {
        "state": _safe_token(coverage.get("state"), fallback="missing"),
    }
    for key in ("requiredBars",):
        if _safe_int(coverage.get(key)) is not None:
            result[key] = _safe_int(coverage.get(key))
    return result


def _market_level_fallback_cards(read_model: Mapping[str, Any]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for raw_card in list(read_model.get("evidenceCards") or []):
        card = _mapping(raw_card)
        card_id = _safe_token(card.get("cardId") or card.get("id"), fallback="")
        title = _safe_public_sentence(card.get("title"), fallback="")
        headline = _safe_public_sentence(card.get("headline"), fallback="")
        if not card_id or not title or not headline:
            continue
        cards.append(
            {
                "cardId": card_id,
                "title": title,
                "status": _safe_token(card.get("status"), fallback="unavailable"),
                "severity": _safe_token(card.get("severity"), fallback="blocker"),
                "headline": headline,
                "reasons": [
                    _safe_public_sentence(reason, fallback="Evidence needs review.")
                    for reason in _safe_text_list(card.get("reasons"))
                ][:3],
                "observationOnly": _OBSERVATION_ONLY,
                "decisionGrade": _DECISION_GRADE,
            }
        )
        if len(cards) >= 3:
            break
    return cards


def _evidence_hub_status(value: Any) -> str:
    normalized = _text(value).lower()
    if normalized in {"available", "ready", "complete", "current", "executable"}:
        return "available"
    if normalized in {"partial", "mixed", "observe_only", "observe-only", "degraded"}:
        return "partial"
    return "blocked"


def _scanner_evidence_item(
    *,
    queue: Sequence[Mapping[str, Any]],
    candidate_count: int,
) -> dict[str, Any]:
    symbols = _dedupe(_symbol_from(item) for item in queue)[:5]
    if not queue:
        return _evidence_item(
            key="scanner",
            label="Scanner candidates",
            status="blocked",
            summary="Scanner candidate evidence is unavailable for this radar view.",
            blocker="No scanner candidates were found for this user scope.",
            next_data_action="Run scanner to create user-scoped research candidates.",
            total_count=max(0, int(candidate_count or 0)),
        )
    return _evidence_item(
        key="scanner",
        label="Scanner candidates",
        status="available",
        summary="Scanner candidate evidence is available for radar review.",
        next_data_action="Refresh scanner when candidate evidence needs a newer observation window.",
        evidence_count=len(queue),
        total_count=max(len(queue), int(candidate_count or 0)),
        symbols=symbols,
        details=[f"{symbol} is available for radar review." for symbol in symbols],
    )


def _backtest_symbol_sample_state(symbol: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("_readFailed"):
        return {
            "status": "blocked",
            "blocker": "Backtest sample status could not be read safely.",
            "detail": f"{symbol} sample status is unavailable.",
        }

    prepared_count = _safe_int(payload.get("prepared_count") or payload.get("preparedCount")) or 0
    sample_state = _text(payload.get("sample_readiness_state") or payload.get("sampleReadinessState")).lower()
    execution_state = _text(_mapping(payload.get("execution_readiness") or payload.get("executionReadiness")).get("state")).lower()
    if prepared_count > 0 and (
        sample_state in {"ready", "available"}
        or execution_state in {"executable", "degraded", "available"}
    ):
        return {
            "status": "available",
            "blocker": None,
            "detail": f"{symbol} has {prepared_count} prepared backtest samples.",
        }
    if prepared_count > 0:
        return {
            "status": "partial",
            "blocker": _backtest_blocker(sample_state, execution_state),
            "detail": f"{symbol} has {prepared_count} prepared samples with readiness limits.",
        }
    return {
        "status": "blocked",
        "blocker": _backtest_blocker(sample_state, execution_state),
        "detail": f"{symbol} has no prepared backtest samples.",
    }


def _backtest_blocker(sample_state: str, execution_state: str) -> str:
    states = {sample_state, execution_state}
    if "engine_disabled" in states:
        return "Backtest execution readiness is disabled for this radar view."
    if {"insufficient_history", "data_insufficient"} & states:
        return "Backtest sample history is too short for the evaluation window."
    if {"missing_cache", "missing", "no_samples", "data_disabled"} & states:
        return "Backtest samples have not been prepared for the radar symbols."
    return "Backtest sample readiness is blocked."


def _stock_readiness_evidence_item(
    *,
    candidate_payloads: Sequence[Mapping[str, Any]],
    queue: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    queue_symbols = {_symbol_from(item) for item in queue}
    rows = [
        _stock_readiness_from_candidate(candidate)
        for candidate in candidate_payloads
        if not queue_symbols or _symbol_from(candidate) in queue_symbols
    ]
    rows = [row for row in rows if row["symbol"]]
    if not rows:
        return _evidence_item(
            key="stock",
            label="Stock readiness",
            status="blocked",
            summary="Stock technical readiness is unavailable for current radar symbols.",
            blocker="Technical readiness is unavailable for current radar symbols.",
            next_data_action="Refresh daily price history and technical evidence for radar symbols.",
        )

    available_count = sum(1 for row in rows if row["status"] == "available")
    partial_count = sum(1 for row in rows if row["status"] == "partial")
    status = "available" if available_count == len(rows) else "partial" if available_count or partial_count else "blocked"
    first_blocker = next((row["blocker"] for row in rows if row.get("blocker")), None)
    if status == "available":
        summary = "Stock technical readiness is available for radar symbols."
        blocker = None
    elif status == "partial":
        summary = "Stock technical readiness is partial for radar symbols."
        blocker = first_blocker or "Some radar symbols still need technical evidence."
    else:
        summary = "Stock technical readiness is blocked for radar symbols."
        blocker = first_blocker or "Technical readiness is unavailable for current radar symbols."
    return _evidence_item(
        key="stock",
        label="Stock readiness",
        status=status,
        summary=summary,
        blocker=blocker,
        next_data_action="Refresh daily price history and technical evidence for radar symbols.",
        evidence_count=available_count,
        total_count=len(rows),
        symbols=[row["symbol"] for row in rows],
        details=[row["detail"] for row in rows],
    )


def _stock_readiness_from_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    symbol = _symbol_from(candidate)
    explicit = _mapping(candidate.get("stockReadiness") or candidate.get("stock_readiness"))
    if explicit:
        status = _evidence_hub_status(explicit.get("status") or explicit.get("readinessState"))
        blocker = _text(explicit.get("blocker")) or None
        detail = _text(explicit.get("detail")) or f"{symbol} technical readiness is {status}."
        return {"symbol": symbol, "status": status, "blocker": blocker, "detail": detail}

    present: list[str] = []
    if _safe_float(candidate.get("trendScore")) is not None or _text(candidate.get("trendStructure")).lower() not in {
        "",
        "blocked",
        "missing",
        "weak",
    }:
        present.append("technical structure")
    if _safe_float(candidate.get("relativeStrength")) is not None:
        present.append("relative strength")
    if _safe_float(candidate.get("volumeExpansion")) is not None:
        present.append("volume participation")
    if _safe_float(candidate.get("avgDollarVolume")) is not None:
        present.append("liquidity")

    status = "available" if len(present) >= 3 else "partial" if present else "blocked"
    if status == "available":
        blocker = None
        detail = f"{symbol} has technical readiness evidence."
    elif status == "partial":
        blocker = "Stock technical evidence is incomplete for this radar symbol."
        detail = f"{symbol} has partial technical readiness evidence."
    else:
        blocker = "Technical readiness is unavailable for current radar symbols."
        detail = f"{symbol} has no technical readiness evidence."
    return {"symbol": symbol, "status": status, "blocker": blocker, "detail": detail}


def _stock_readiness_from_scanner_frame(
    *,
    symbol: str,
    evidence_frame: Mapping[str, Any],
) -> dict[str, Any]:
    domains = _mapping(evidence_frame.get("domains"))
    domain_labels = {
        "technicals": "technical indicators",
        "priceHistory": "price history",
        "liquidity": "liquidity",
        "volume": "volume participation",
        "trend": "trend structure",
    }
    states = {
        key: _text(_mapping(domains.get(key)).get("state")).lower()
        for key in domain_labels
    }
    available_count = sum(1 for state in states.values() if state == "available")
    partial_count = sum(1 for state in states.values() if state == "partial")
    missing = [label for key, label in domain_labels.items() if states.get(key) not in {"available", "partial"}]
    status = (
        "available"
        if states.get("technicals") == "available"
        and states.get("priceHistory") == "available"
        and states.get("trend") == "available"
        and states.get("liquidity") in {"available", "partial"}
        else "partial"
        if available_count or partial_count
        else "blocked"
    )
    if status == "available":
        blocker = None
        detail = f"{symbol} has technical indicators, price history, trend structure, and liquidity evidence."
    elif status == "partial":
        blocker = f"{missing[0].capitalize()} is missing for stock readiness." if missing else "Stock readiness is partial."
        detail = f"{symbol} has partial stock readiness evidence."
    else:
        blocker = "Technical readiness is unavailable for current radar symbols."
        detail = f"{symbol} has no stock readiness evidence."
    return {
        "status": status,
        "blocker": blocker,
        "detail": detail,
        "evidenceCount": available_count,
        "totalCount": len(domain_labels),
    }


def _data_activation_evidence_item(
    *,
    scanner: Mapping[str, Any],
    backtest: Mapping[str, Any],
    stock: Mapping[str, Any],
    data_quality: Mapping[str, Any],
) -> dict[str, Any]:
    slices = [scanner, backtest, stock]
    available_count = sum(1 for item in slices if item.get("status") == "available")
    partial_count = sum(1 for item in slices if item.get("status") == "partial")
    data_status = _text(data_quality.get("status")).lower()
    status = (
        "available"
        if available_count == len(slices) and data_status in {"ready", "available", "complete"}
        else "partial"
        if available_count or partial_count or data_status in {"partial", "ready"}
        else "blocked"
    )
    first_blocker = next((_text(item.get("blocker")) for item in slices if _text(item.get("blocker"))), None)
    if status == "available":
        summary = "Scanner, backtest sample, and stock readiness evidence are available."
        blocker = None
    elif status == "partial":
        summary = "Research Radar evidence is partially activated."
        blocker = first_blocker or "Some evidence slices still need data activation."
    else:
        summary = "Research Radar evidence is blocked until upstream data is activated."
        blocker = first_blocker or "Research Radar has no usable upstream evidence."
    return _evidence_item(
        key="data",
        label="Data activation",
        status=status,
        summary=summary,
        blocker=blocker,
        next_data_action="Resolve blocked evidence slices, then refresh Research Radar.",
        evidence_count=available_count,
        total_count=len(slices),
        details=[
            f"{_text(item.get('label'))} status {item.get('status')}."
            for item in slices
            if _text(item.get("label"))
        ],
    )


def _descriptor_for(value: Any, mapping: Mapping[str, Mapping[str, str]]) -> dict[str, str]:
    raw = _text(value)
    key = raw.lower()
    descriptor = mapping.get(key) or mapping.get(_compact_descriptor_key(raw)) or _DEFAULT_CONSUMER_DESCRIPTOR
    return dict(descriptor)


def _compact_descriptor_key(value: Any) -> str:
    return "".join(ch for ch in _text(value).lower() if ch.isalnum())


def _descriptor_labels(descriptors: Sequence[Mapping[str, str]]) -> list[str]:
    return _dedupe(str(descriptor.get("label") or "") for descriptor in descriptors)


def _safe_token(value: Any, *, fallback: str) -> str:
    token = _text(value).strip()
    if not token:
        return fallback
    return "".join(character for character in token if character.isalnum() or character in {"_", "-", "."})[:80] or fallback


def _safe_public_sentence(value: Any, *, fallback: str) -> str:
    text = _text(value).strip()
    if not text:
        return fallback
    lowered = text.lower()
    unsafe_markers = (
        "request_id",
        "requestid",
        "trace_id",
        "traceid",
        "provider",
        "raw",
        "debug",
        "token",
        "secret",
        "cache key",
        "schema",
        "source authority",
    )
    if any(marker in lowered for marker in unsafe_markers):
        return fallback
    if any(term in lowered for term in ("buy", "sell", "hold", "recommendation", "target price", "stop loss", "position sizing")):
        return fallback
    if any(term in text for term in ("买入", "卖出", "持有", "推荐", "目标价", "止损", "仓位")):
        return fallback
    return text[:320]


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
    scanner_lineage = _mapping(diagnostics.get("scannerLineage"))
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
    risk_notes = payload["risk_notes"] if isinstance(payload["risk_notes"], list) else []
    watch_context = payload["watch_context"] if isinstance(payload["watch_context"], list) else []
    limitation = _first_text(risk_notes) or "Evidence remains observation-only and needs a freshness check before further research."
    next_check = _watch_context_text(watch_context) or "Recheck price, volume, and evidence freshness on the next scanner run."
    quote_context = _mapping(diagnostics.get("quote_context"))
    history = _mapping(diagnostics.get("history"))
    return {
        "ticker": payload["symbol"],
        "symbol": payload["symbol"],
        "reason": payload["reason_summary"] or "Scanner surfaced this symbol from observable price, volume, or structure evidence.",
        "limitation": limitation,
        "nextCheck": next_check,
        "dataFreshness": {
            "historySource": history.get("source") or "unknown",
            "historyLatestTradeDate": history.get("latest_trade_date"),
            "quoteState": "available" if quote_context.get("available") is True else "unavailable_or_stale",
            "quoteSource": quote_context.get("source"),
        },
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
        "stockReadiness": {
            "symbol": payload["symbol"],
            **_stock_readiness_from_scanner_frame(
                symbol=payload["symbol"],
                evidence_frame=evidence_frame,
            ),
        },
        "scannerLineage": scanner_lineage,
    }


def _scanner_lineage_from_run(run: Any) -> dict[str, Any]:
    diagnostics = _json_load(getattr(run, "diagnostics_json", None), {})
    readiness = _mapping(diagnostics.get("dataReadiness"))
    lineage = _mapping(diagnostics.get("scannerLineage") or readiness.get("scannerLineage"))
    if not lineage:
        return {}
    return {
        "source": _text(lineage.get("source") or lineage.get("universeSource")),
        "universeMode": _text(lineage.get("universeMode")),
        "universeSymbols": _safe_text_list(lineage.get("universeSymbols")),
        "generatedAt": _text(lineage.get("generatedAt")) or None,
        "runId": lineage.get("runId") or getattr(run, "id", None),
        "symbolsEvaluated": _safe_text_list(lineage.get("symbolsEvaluated")),
        "symbolsSkipped": [
            {
                "symbol": _text(_mapping(item).get("symbol")).upper(),
                "reason": _text(_mapping(item).get("reason")) or "limited",
            }
            for item in list(lineage.get("symbolsSkipped") or [])
            if isinstance(item, Mapping) and _text(item.get("symbol"))
        ],
    }


def _filter_candidates_by_scanner_lineage(
    candidates: Sequence[Mapping[str, Any]],
    scanner_lineage: Mapping[str, Any],
) -> list[dict[str, Any]]:
    lineage = _mapping(scanner_lineage)
    if _text(lineage.get("universeMode")) != "bounded_starter_local":
        return [dict(candidate) for candidate in candidates]
    allowed_symbols = {_text(symbol).upper() for symbol in lineage.get("universeSymbols") or [] if _text(symbol)}
    if not allowed_symbols:
        return [dict(candidate) for candidate in candidates]
    filtered: list[dict[str, Any]] = []
    for candidate in candidates:
        symbol = _symbol_from(candidate)
        if symbol not in allowed_symbols:
            continue
        payload = dict(candidate)
        payload["scannerLineage"] = dict(lineage)
        filtered.append(payload)
    return filtered


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


def _first_text(values: Sequence[Any]) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _watch_context_text(values: Sequence[Any]) -> str:
    for value in values:
        if isinstance(value, Mapping):
            text = _text(value.get("value") or value.get("label"))
        else:
            text = _text(value)
        if text:
            return text
    return ""


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
