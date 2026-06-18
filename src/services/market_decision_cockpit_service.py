# -*- coding: utf-8 -*-
"""Deterministic market decision cockpit aggregate service.

This service only composes already-normalized market regime, research radar,
and options observation payloads. It does not fetch providers, mutate caches,
rank scanners, or change any protected-domain semantics.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote

from src.services.confidence_evidence_consistency import project_confidence_evidence_state
from src.services.market_overview_service import MarketOverviewService
from src.services.market_regime_decision_engine import build_market_regime_decision
from src.services.options_market_structure_observation import build_options_market_structure_observation
from src.services.research_radar_candidate_engine import build_research_radar_candidate_queue
from src.services.consumer_issue_labels import build_consumer_issues, sanitize_consumer_reason_payload


SCHEMA_VERSION = "market_decision_cockpit.v1"
NO_ADVICE_DISCLOSURE = "Observation-only market research; not personalized financial advice."
_RESEARCH_EMPTY_REASON = "research_candidates_unavailable"
_OPTION_CHAIN_EMPTY_REASON = "option_chain_unavailable"
_MARKET_REGIME_LOW_CONFIDENCE_REASON = "market_regime_low_confidence"
_REGIME_LABELS = {
    "riskOn": "Risk-on observation",
    "riskOff": "Risk-off observation",
    "lowConfidence": "Low-confidence observation",
    "mixed": "Mixed-regime observation",
    "rangeBound": "Range-bound observation",
}
_CONFIDENCE_LABELS = {
    "low": "low",
    "medium": "moderate",
    "high": "high",
}
_SAFE_REASON_LABELS = {
    _MARKET_REGIME_LOW_CONFIDENCE_REASON: "Market regime evidence is low confidence.",
    _RESEARCH_EMPTY_REASON: "Research candidates are unavailable.",
    _OPTION_CHAIN_EMPTY_REASON: "Options structure evidence is unavailable.",
    "options_observation_only": "Options structure remains observation-only.",
    "historical_baseline_unavailable": "Historical baseline is unavailable.",
    "dealerGamma:unavailable": "Options structure evidence is unavailable.",
    "live_gex_not_implemented_v1": "Live options gamma evidence is unavailable.",
    "observation_only_not_decision_grade": "Options structure remains observation-only.",
    "missing_spot_reference": "Options spot reference is unavailable.",
    "missing_contracts": "Options contract coverage is unavailable.",
    "mixed_driver_alignment": "Driver alignment is mixed.",
    "low_evidence": "Low evidence quality.",
    "thin": "Thin evidence coverage.",
    "mixed": "Mixed evidence coverage.",
    "strong": "Strong evidence coverage.",
}


class MarketDecisionCockpitService:
    """Compose market regime, research preview, and options observation."""

    def __init__(
        self,
        *,
        market_overview_service: MarketOverviewService | None = None,
        now_provider: Callable[[], str] | None = None,
    ) -> None:
        self._market_overview_service = market_overview_service or MarketOverviewService()
        self._now_provider = now_provider or self._default_now_provider

    def get_decision_cockpit(
        self,
        *,
        actor: Mapping[str, Any] | None = None,
        market_inputs: Mapping[str, Any] | None = None,
        market_regime_decision: Mapping[str, Any] | None = None,
        research_candidates: Sequence[Mapping[str, Any]] | None = None,
        option_contracts: Sequence[Any] | None = None,
        option_spot: float | int | str | None = None,
    ) -> dict[str, Any]:
        generated_at = self._now_provider()
        decision = self._build_market_regime_decision(
            actor=actor,
            market_inputs=market_inputs,
            market_regime_decision=market_regime_decision,
        )
        research_preview = self._build_research_queue_preview(
            decision,
            research_candidates=research_candidates,
        )
        options_status = self._build_options_structure_status(
            option_contracts=option_contracts,
            option_spot=option_spot,
        )
        cockpit_summary = self._build_cockpit_summary(decision, research_preview, options_status)
        data_quality = self._build_data_quality(decision, research_preview, options_status)
        what_changed = self._build_what_changed(
            decision,
            research_preview,
            options_status,
        )
        top_research_priorities = self._build_top_research_priorities(research_preview)
        scanner_highlights = self._build_scanner_highlights(research_preview)
        scenario_risks = self._build_scenario_risks(decision)
        evidence_gaps = self._build_evidence_gaps(decision, research_preview, options_status, data_quality)
        degraded_inputs = self._build_degraded_inputs(research_preview, options_status, data_quality)
        drilldown_targets = self._build_drilldown_targets(research_preview)
        driver_attribution = self._build_driver_attribution(decision)
        synthesis = self._build_synthesis_contract(
            decision=decision,
            research_preview=research_preview,
            options_status=options_status,
            top_research_priorities=top_research_priorities,
            scanner_highlights=scanner_highlights,
            scenario_risks=scenario_risks,
            degraded_inputs=degraded_inputs,
            drilldown_targets=drilldown_targets,
            driver_attribution=driver_attribution,
        )
        consumer_issues = build_consumer_issues(
            data_quality,
            decision.get("missingEvidence"),
            _driver_reason_codes(decision),
            research_preview,
            options_status,
        )

        return sanitize_consumer_reason_payload({
            "schemaVersion": SCHEMA_VERSION,
            "generatedAt": generated_at,
            "marketRegimeDecision": decision,
            "marketRegimeSummary": self._build_market_regime_summary(decision),
            "whatChanged": what_changed,
            "topResearchPriorities": top_research_priorities,
            "scannerHighlights": scanner_highlights,
            "watchlistHighlights": [],
            "portfolioHighlights": [],
            "scenarioRisks": scenario_risks,
            "evidenceGaps": evidence_gaps,
            "degradedInputs": degraded_inputs,
            "drilldownTargets": drilldown_targets,
            "researchWorkflow": synthesis["researchWorkflow"],
            "crossSurfaceEvidence": synthesis["crossSurfaceEvidence"],
            "topResearchQuestions": synthesis["topResearchQuestions"],
            "priorityDrilldowns": synthesis["priorityDrilldowns"],
            "evidenceConflicts": synthesis["evidenceConflicts"],
            "degradedSurfaceSummary": synthesis["degradedSurfaceSummary"],
            "nextObservationSteps": synthesis["nextObservationSteps"],
            "researchQueuePreview": research_preview,
            "optionsStructureStatus": options_status,
            "cockpitSummary": cockpit_summary,
            "driverAttribution": driver_attribution,
            "confidenceDiagnostics": self._build_confidence_diagnostics(
                decision,
                research_preview,
                options_status,
                data_quality,
            ),
            "watchTriggers": self._build_watch_triggers(decision, research_preview, options_status),
            "cockpitReadiness": self._build_cockpit_readiness(
                decision,
                research_preview,
                options_status,
                data_quality,
            ),
            "scenarioHints": self._build_scenario_hints(decision),
            "consumerIssues": consumer_issues,
            "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
            "observationOnly": True,
            "decisionGrade": False,
            "dataQuality": data_quality,
        })

    @staticmethod
    def _default_now_provider() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _build_market_regime_decision(
        self,
        *,
        actor: Mapping[str, Any] | None,
        market_inputs: Mapping[str, Any] | None,
        market_regime_decision: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if isinstance(market_regime_decision, Mapping):
            payload = dict(market_regime_decision)
        elif isinstance(market_inputs, Mapping):
            payload = build_market_regime_decision(market_inputs)
        else:
            payload = self._market_overview_decision(actor=actor)

        payload.setdefault("invalidationConditions", _invalidation_conditions(payload))
        payload["consumerIssues"] = build_consumer_issues(
            payload.get("missingEvidence"),
            _driver_reason_codes(payload),
            _mapping(payload.get("dataQuality")).get("confidenceCapReasons"),
        )
        return payload

    def _market_overview_decision(self, *, actor: Mapping[str, Any] | None) -> dict[str, Any]:
        try:
            payload = self._market_overview_service.get_market_regime_decision(
                actor=dict(actor) if isinstance(actor, Mapping) else None
            )
            if isinstance(payload, Mapping):
                return dict(payload)
        except Exception:
            pass

        fallback = build_market_regime_decision({})
        fallback["inputSource"] = "market_decision_cockpit_fallback_inputs"
        fallback["updatedAt"] = self._default_now_provider()
        fallback["invalidationConditions"] = _invalidation_conditions(fallback)
        return fallback

    def _build_research_queue_preview(
        self,
        market_regime_decision: Mapping[str, Any],
        *,
        research_candidates: Sequence[Mapping[str, Any]] | None,
    ) -> dict[str, Any]:
        candidates = list(research_candidates or [])
        queue = build_research_radar_candidate_queue(
            candidates,
            market_regime_context=market_regime_decision,
        )
        research_queue = list(queue.get("researchQueue") or [])
        summary = queue.get("summary") if isinstance(queue.get("summary"), Mapping) else {}
        preview: dict[str, Any] = {
            "topCandidates": research_queue[:3],
            "queueQuality": summary.get("queueQuality", "thin"),
            "evidenceGaps": list(summary.get("evidenceGaps") or []),
            "previewOnly": True,
        }
        if not candidates or not research_queue:
            preview["degradedState"] = {
                "status": "empty",
                "reasonCodes": [_RESEARCH_EMPTY_REASON],
            }
        preview["consumerIssues"] = build_consumer_issues(
            preview.get("evidenceGaps"),
            _mapping(preview.get("degradedState")).get("reasonCodes"),
        )
        return preview

    def _build_options_structure_status(
        self,
        *,
        option_contracts: Sequence[Any] | None,
        option_spot: float | int | str | None,
    ) -> dict[str, Any]:
        contracts = list(option_contracts or [])
        prerequisites_met = bool(contracts) and option_spot is not None
        observation = build_options_market_structure_observation(
            contracts,
            spot=option_spot,
            methodology_approved=prerequisites_met,
            coverage_thresholds_defined=prerequisites_met,
            provider_authority_verified=prerequisites_met,
            redistribution_rights_verified=prerequisites_met,
            decision_use_rights_verified=prerequisites_met,
            deliverable_handling_reviewed=prerequisites_met,
        )

        observation_state = str(observation.get("observationState") or "blocked")
        if observation_state == "ready":
            gamma_status = "ready_observation"
        elif observation_state == "degraded":
            gamma_status = "degraded"
        else:
            gamma_status = "unavailable"

        blocked_reason_codes = list(observation.get("blockedReasonCodes") or [])
        if gamma_status == "unavailable" and _OPTION_CHAIN_EMPTY_REASON not in blocked_reason_codes:
            blocked_reason_codes.insert(0, _OPTION_CHAIN_EMPTY_REASON)

        consumer_issues = build_consumer_issues(blocked_reason_codes, observation.get("missingEvidence"))
        return {
            "gammaEvidenceStatus": gamma_status,
            "observationOnly": bool(observation.get("observationOnly", True)),
            "decisionGrade": False,
            "missingEvidence": list(observation.get("missingEvidence") or []),
            "blockedReasonCodes": blocked_reason_codes,
            "consumerIssues": consumer_issues,
        }

    def _build_cockpit_summary(
        self,
        market_regime_decision: Mapping[str, Any],
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
    ) -> dict[str, Any]:
        regime = str(market_regime_decision.get("regime") or "lowConfidence")
        confidence = str(market_regime_decision.get("confidence") or "low")
        priorities = _mapping(market_regime_decision.get("researchPriorities"))
        regime_quality = _mapping(market_regime_decision.get("dataQuality"))
        evidence_gaps = list(research_preview.get("evidenceGaps") or [])
        blocked_reasons = list(options_status.get("blockedReasonCodes") or [])

        what_to_watch = _safe_public_list(priorities.get("watchToday") or [])
        what_to_watch.extend(_safe_public_list(priorities.get("investigateNext") or []))
        if not what_to_watch:
            what_to_watch.append("Await stronger market evidence before tightening the read.")

        confidence_limits = list(regime_quality.get("confidenceCapReasons") or [])
        confidence_limits.extend(evidence_gaps)
        confidence_limits.extend(blocked_reasons)

        return {
            "whatChanged": self._build_what_changed(market_regime_decision, research_preview, options_status),
            "whyItMatters": [
                "This cockpit keeps regime, research triage, and options observation in one read-only view.",
            ],
            "whatToWatch": what_to_watch,
            "confidenceLimits": _safe_phrase_list(confidence_limits),
        }

    def _build_market_regime_summary(self, market_regime_decision: Mapping[str, Any]) -> dict[str, Any]:
        explanation = _mapping(market_regime_decision.get("explanation"))
        regime_label = _regime_label(market_regime_decision.get("regime") or "lowConfidence")
        summary = _first_text(explanation.get("whyThisRegime")) or f"Current regime observation is {regime_label}."
        confidence_projection = _market_regime_confidence_projection(market_regime_decision)
        return {
            "regime": regime_label,
            "confidence": _confidence_label(confidence_projection["consumerConfidence"]),
            "rawConfidence": str(market_regime_decision.get("confidence") or "low"),
            "confidenceCap": _public_confidence_cap(confidence_projection["confidenceCap"]),
            "confidenceState": confidence_projection["confidenceState"],
            "summary": _safe_public_text(summary),
            "supportingObservations": _safe_public_list(explanation.get("whatConfirmsIt") or []),
            "invalidationObservations": _safe_public_list(explanation.get("whatInvalidatesIt") or []),
        }

    def _build_top_research_priorities(self, research_preview: Mapping[str, Any]) -> list[dict[str, Any]]:
        priorities: list[dict[str, Any]] = []
        for item in list(research_preview.get("topCandidates") or [])[:5]:
            payload = _mapping(item)
            ticker = str(payload.get("ticker") or payload.get("symbol") or "").strip() or None
            explanation = _mapping(payload.get("explanation"))
            priorities.append(
                {
                    "label": f"{ticker or 'Unknown'} research queue",
                    "source": "Research Radar",
                    "priority": _confidence_label(payload.get("priority") or ""),
                    "ticker": ticker,
                    "observations": _safe_public_list(explanation.get("whyOnRadar") or payload.get("whyOnRadar") or []),
                    "whatToVerify": _safe_public_list(
                        explanation.get("whatToVerify") or payload.get("whatToVerify") or []
                    ),
                    "evidenceGaps": _safe_phrase_list(
                        explanation.get("evidenceGaps") or payload.get("evidenceGaps") or []
                    ),
                    "drilldownTargets": self._symbol_drilldowns(ticker),
                }
            )
        return priorities

    def _build_scanner_highlights(self, research_preview: Mapping[str, Any]) -> list[dict[str, Any]]:
        highlights: list[dict[str, Any]] = []
        for item in list(research_preview.get("topCandidates") or [])[:3]:
            payload = _mapping(item)
            ticker = str(payload.get("ticker") or payload.get("symbol") or "").strip() or "UNKNOWN"
            explanation = _mapping(payload.get("explanation"))
            highlights.append(
                {
                    "ticker": ticker,
                    "priority": _confidence_label(payload.get("priority") or ""),
                    "observations": _safe_public_list(explanation.get("whyOnRadar") or payload.get("whyOnRadar") or []),
                    "whatToVerify": _safe_public_list(
                        explanation.get("whatToVerify") or payload.get("whatToVerify") or []
                    ),
                    "evidenceGaps": _safe_phrase_list(
                        explanation.get("evidenceGaps") or payload.get("evidenceGaps") or []
                    ),
                    "riskFlags": _safe_phrase_list(payload.get("riskFlags") or []),
                    "drilldownTargets": self._symbol_drilldowns(ticker),
                }
            )
        return highlights

    def _build_scenario_risks(self, market_regime_decision: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "label": "Regime confidence scenario",
                "source": "Scenario Lab",
                "observations": _safe_public_list(self._build_scenario_hints(market_regime_decision)[:2]),
                "evidenceGaps": _safe_phrase_list(market_regime_decision.get("missingEvidence") or []),
                "drilldownTargets": [
                    {
                        "label": "Scenario Lab",
                        "route": "/scenario-lab",
                        "section": "scenarioRisks",
                        "reason": "Review bounded scenario changes.",
                    }
                ],
            }
        ]

    def _build_evidence_gaps(
        self,
        market_regime_decision: Mapping[str, Any],
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
        data_quality: Mapping[str, Any],
    ) -> list[str]:
        raw: list[Any] = []
        raw.extend(market_regime_decision.get("missingEvidence") or [])
        raw.extend(research_preview.get("evidenceGaps") or [])
        raw.extend(options_status.get("blockedReasonCodes") or [])
        raw.extend(data_quality.get("reasonCodes") or [])
        return _safe_phrase_list(raw)

    def _build_degraded_inputs(
        self,
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
        data_quality: Mapping[str, Any],
    ) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        if data_quality.get("status") in {"blocked", "degraded"}:
            items.append(
                {
                    "section": "marketRegimeSummary",
                    "status": str(data_quality.get("status")),
                    "reason": _safe_reason_phrase(_MARKET_REGIME_LOW_CONFIDENCE_REASON),
                }
            )
        if not research_preview.get("topCandidates"):
            items.append(
                {
                    "section": "topResearchPriorities",
                    "status": "unavailable",
                    "reason": _safe_reason_phrase(_RESEARCH_EMPTY_REASON),
                }
            )
            items.append(
                {
                    "section": "scannerHighlights",
                    "status": "unavailable",
                    "reason": _safe_reason_phrase(_RESEARCH_EMPTY_REASON),
                }
            )
        if options_status.get("gammaEvidenceStatus") == "unavailable":
            items.append(
                {
                    "section": "scenarioRisks",
                    "status": "unavailable",
                    "reason": _safe_reason_phrase(_OPTION_CHAIN_EMPTY_REASON),
                }
            )
        items.append(
            {
                "section": "watchlistHighlights",
                "status": "unavailable",
                "reason": "Watchlist highlights are available from Daily Intelligence when owner context is present.",
            }
        )
        items.append(
            {
                "section": "portfolioHighlights",
                "status": "unavailable",
                "reason": "Portfolio highlights are available from Daily Intelligence when owner context is present.",
            }
        )
        return _dedupe_degraded(items)

    def _build_drilldown_targets(self, research_preview: Mapping[str, Any]) -> list[dict[str, str]]:
        targets = [
            {
                "label": "Daily Intelligence",
                "route": "/market/daily-intelligence",
                "section": "marketRegimeSummary",
                "reason": "Open the full daily briefing.",
            },
            {
                "label": "Research Radar",
                "route": "/research/radar",
                "section": "topResearchPriorities",
                "reason": "Review the research queue.",
            },
            {
                "label": "Scanner",
                "route": "/scanner",
                "section": "scannerHighlights",
                "reason": "Inspect scanner candidates.",
            },
            {
                "label": "Watchlist",
                "route": "/watchlist",
                "section": "watchlistHighlights",
                "reason": "Review owner watchlist context.",
            },
            {
                "label": "Portfolio",
                "route": "/portfolio",
                "section": "portfolioHighlights",
                "reason": "Review owner portfolio context.",
            },
            {
                "label": "Scenario Lab",
                "route": "/scenario-lab",
                "section": "scenarioRisks",
                "reason": "Review bounded scenario changes.",
            },
        ]
        for item in list(research_preview.get("topCandidates") or [])[:3]:
            ticker = str(_mapping(item).get("ticker") or _mapping(item).get("symbol") or "").strip()
            targets.extend(self._symbol_drilldowns(ticker))
        return _dedupe_targets(targets)

    @staticmethod
    def _symbol_drilldowns(ticker: str | None) -> list[dict[str, str]]:
        symbol = str(ticker or "").strip()
        if not symbol or symbol.upper() == "UNKNOWN":
            return []
        return [
            {
                "label": "Stock Structure",
                "route": f"/stocks/{quote(symbol, safe='')}/structure-decision",
                "section": "topResearchPriorities",
                "reason": "Open symbol structure detail.",
            }
        ]

    def _build_synthesis_contract(
        self,
        *,
        decision: Mapping[str, Any],
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
        top_research_priorities: Sequence[Mapping[str, Any]],
        scanner_highlights: Sequence[Mapping[str, Any]],
        scenario_risks: Sequence[Mapping[str, Any]],
        degraded_inputs: Sequence[Mapping[str, str]],
        drilldown_targets: Sequence[Mapping[str, str]],
        driver_attribution: Mapping[str, Any],
    ) -> dict[str, Any]:
        priority_drilldowns = self._build_priority_drilldowns(drilldown_targets)
        degraded_surface_summary = self._build_degraded_surface_summary(
            research_preview=research_preview,
            options_status=options_status,
            degraded_inputs=degraded_inputs,
            priority_drilldowns=priority_drilldowns,
        )
        return {
            "researchWorkflow": self._build_research_workflow(
                decision=decision,
                research_preview=research_preview,
                options_status=options_status,
                top_research_priorities=top_research_priorities,
                scanner_highlights=scanner_highlights,
                scenario_risks=scenario_risks,
                degraded_surface_summary=degraded_surface_summary,
                priority_drilldowns=priority_drilldowns,
            ),
            "crossSurfaceEvidence": self._build_cross_surface_evidence(
                top_research_priorities=top_research_priorities,
                scenario_risks=scenario_risks,
                options_status=options_status,
                priority_drilldowns=priority_drilldowns,
            ),
            "topResearchQuestions": self._build_top_research_questions(
                top_research_priorities=top_research_priorities,
                options_status=options_status,
                priority_drilldowns=priority_drilldowns,
            ),
            "priorityDrilldowns": priority_drilldowns,
            "evidenceConflicts": self._build_evidence_conflicts(
                driver_attribution=driver_attribution,
                priority_drilldowns=priority_drilldowns,
            ),
            "degradedSurfaceSummary": degraded_surface_summary,
            "nextObservationSteps": self._build_next_observation_steps(
                top_research_priorities=top_research_priorities,
                options_status=options_status,
                priority_drilldowns=priority_drilldowns,
            ),
        }

    def _build_research_workflow(
        self,
        *,
        decision: Mapping[str, Any],
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
        top_research_priorities: Sequence[Mapping[str, Any]],
        scanner_highlights: Sequence[Mapping[str, Any]],
        scenario_risks: Sequence[Mapping[str, Any]],
        degraded_surface_summary: Sequence[Mapping[str, Any]],
        priority_drilldowns: Sequence[Mapping[str, str]],
    ) -> list[dict[str, Any]]:
        degraded_surfaces = {
            str(item.get("surface") or ""): str(item.get("status") or "unavailable")
            for item in degraded_surface_summary
        }
        stock_links = [link for link in priority_drilldowns if "structure-decision" in str(link.get("route") or "")]
        regime_label = _regime_label(decision.get("regime") or "lowConfidence")
        options_ready = options_status.get("gammaEvidenceStatus") != "unavailable"
        return [
            self._workflow_step(
                surface="Market Overview",
                status="available",
                summary=f"{regime_label} is the starting context for this cockpit.",
                drilldown_targets=[_surface_link("Market Overview", "/market-overview", "marketRegimeSummary")],
            ),
            self._workflow_step(
                surface="Research Radar",
                status=(
                    "available"
                    if top_research_priorities or scanner_highlights
                    else degraded_surfaces.get("Research Radar", "unavailable")
                ),
                summary=(
                    "Research Radar evidence is connected to the cockpit queue."
                    if top_research_priorities or scanner_highlights
                    else "Research Radar evidence is unavailable for this cockpit."
                ),
                drilldown_targets=[_surface_link("Research Radar", "/research/radar", "topResearchPriorities")],
            ),
            self._workflow_step(
                surface="Portfolio Structure Review",
                status=degraded_surfaces.get("Portfolio Structure Review", "unavailable"),
                summary="Portfolio structure review remains a Daily Intelligence drilldown surface.",
                drilldown_targets=[_surface_link("Portfolio", "/portfolio", "portfolioHighlights")],
            ),
            self._workflow_step(
                surface="Scenario Lab",
                status="available" if scenario_risks else "unavailable",
                summary="Scenario Lab can review bounded changes against the current regime observation.",
                drilldown_targets=[_surface_link("Scenario Lab", "/scenario-lab", "scenarioRisks")],
            ),
            self._workflow_step(
                surface="Stock Structure",
                status="available" if stock_links else degraded_surfaces.get("Stock Structure", "unavailable"),
                summary=(
                    "Stock Structure drilldowns are available for symbols in focus."
                    if stock_links
                    else "Stock Structure drilldowns need a symbol in focus."
                ),
                drilldown_targets=stock_links[:3]
                or [_surface_link("Stock Structure", "/stocks/structure-decision", "topResearchPriorities")],
            ),
            self._workflow_step(
                surface="Options / Gamma Observation",
                status="available" if options_ready else "unavailable",
                summary=(
                    "Options and gamma evidence is available as observation-only context."
                    if options_ready
                    else "Options and gamma evidence is unavailable for this cockpit snapshot."
                ),
                drilldown_targets=[_surface_link("Options / Gamma", "/options-lab", "scenarioRisks")],
            ),
        ]

    def _build_cross_surface_evidence(
        self,
        *,
        top_research_priorities: Sequence[Mapping[str, Any]],
        scenario_risks: Sequence[Mapping[str, Any]],
        options_status: Mapping[str, Any],
        priority_drilldowns: Sequence[Mapping[str, str]],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        radar_links = [link for link in priority_drilldowns if str(link.get("route")) == "/research/radar"]
        stock_links = [link for link in priority_drilldowns if "structure-decision" in str(link.get("route") or "")]
        scenario_link = _surface_link("Scenario Lab", "/scenario-lab", "scenarioRisks")
        options_link = _surface_link("Options / Gamma", "/options-lab", "scenarioRisks")
        if top_research_priorities:
            items.append(
                {
                    "surfaces": ["Market Overview", "Research Radar"],
                    "observation": "Market context can be reviewed beside the active research queue.",
                    "drilldownTargets": _dedupe_targets([*radar_links[:1], scenario_link]),
                }
            )
        if stock_links:
            items.append(
                {
                    "surfaces": ["Research Radar", "Stock Structure"],
                    "observation": "Symbols in the research queue have structure drilldowns for verification.",
                    "drilldownTargets": _dedupe_targets([*radar_links[:1], *stock_links[:2]]),
                }
            )
        if scenario_risks:
            items.append(
                {
                    "surfaces": ["Market Overview", "Scenario Lab"],
                    "observation": "Scenario context can be reviewed against the current regime observation.",
                    "drilldownTargets": [scenario_link],
                }
            )
        if options_status.get("gammaEvidenceStatus") == "unavailable":
            items.append(
                {
                    "surfaces": ["Scenario Lab", "Options / Gamma Observation"],
                    "observation": "Options and gamma evidence is an explicit degraded input for scenario context.",
                    "drilldownTargets": _dedupe_targets([scenario_link, options_link]),
                }
            )
        return items

    def _build_top_research_questions(
        self,
        *,
        top_research_priorities: Sequence[Mapping[str, Any]],
        options_status: Mapping[str, Any],
        priority_drilldowns: Sequence[Mapping[str, str]],
    ) -> list[dict[str, Any]]:
        questions: list[dict[str, Any]] = []
        radar_links = [link for link in priority_drilldowns if str(link.get("route")) == "/research/radar"]
        stock_links = [link for link in priority_drilldowns if "structure-decision" in str(link.get("route") or "")]
        if top_research_priorities:
            questions.append(
                {
                    "question": "Which research queue items need structure verification first?",
                    "surface": "Research Radar",
                    "drilldownTargets": _dedupe_targets([*radar_links[:1], *stock_links[:2]]),
                }
            )
        else:
            questions.append(
                {
                    "question": "What evidence is needed before Research Radar can populate the queue?",
                    "surface": "Research Radar",
                    "drilldownTargets": [_surface_link("Research Radar", "/research/radar", "topResearchPriorities")],
                }
            )
        questions.append(
            {
                "question": "Which scenario assumptions would change the current regime observation?",
                "surface": "Scenario Lab",
                "drilldownTargets": [_surface_link("Scenario Lab", "/scenario-lab", "scenarioRisks")],
            }
        )
        if options_status.get("gammaEvidenceStatus") == "unavailable":
            questions.append(
                {
                    "question": "Which options structure evidence is still unavailable for observation context?",
                    "surface": "Options / Gamma Observation",
                    "drilldownTargets": [_surface_link("Options / Gamma", "/options-lab", "scenarioRisks")],
                }
            )
        return questions[:5]

    def _build_priority_drilldowns(self, drilldown_targets: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
        links = list(drilldown_targets)
        links.extend(
            [
                _surface_link("Market Overview", "/market-overview", "marketRegimeSummary"),
                _surface_link("Scenario Lab", "/scenario-lab", "scenarioRisks"),
                _surface_link("Options / Gamma", "/options-lab", "scenarioRisks"),
            ]
        )
        return _dedupe_targets(links)[:10]

    def _build_evidence_conflicts(
        self,
        *,
        driver_attribution: Mapping[str, Any],
        priority_drilldowns: Sequence[Mapping[str, str]],
    ) -> list[dict[str, Any]]:
        conflicts: list[dict[str, Any]] = []
        for item in list(driver_attribution.get("conflictingDrivers") or [])[:3]:
            payload = _mapping(item)
            condition = _safe_public_text(payload.get("condition"))
            if not condition:
                continue
            conflicts.append(
                {
                    "surfaces": ["Market Overview", "Scenario Lab"],
                    "summary": condition,
                    "drilldownTargets": _dedupe_targets([
                        _surface_link("Market Overview", "/market-overview", "marketRegimeSummary"),
                        _surface_link("Scenario Lab", "/scenario-lab", "scenarioRisks"),
                        *priority_drilldowns[:1],
                    ]),
                }
            )
        return conflicts

    def _build_degraded_surface_summary(
        self,
        *,
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
        degraded_inputs: Sequence[Mapping[str, str]],
        priority_drilldowns: Sequence[Mapping[str, str]],
    ) -> list[dict[str, Any]]:
        section_surface = {
            "marketRegimeSummary": ("Market Overview", "/market-overview"),
            "topResearchPriorities": ("Research Radar", "/research/radar"),
            "scannerHighlights": ("Research Radar", "/research/radar"),
            "watchlistHighlights": ("Watchlist", "/watchlist"),
            "portfolioHighlights": ("Portfolio Structure Review", "/portfolio"),
            "scenarioRisks": ("Scenario Lab", "/scenario-lab"),
        }
        items: list[dict[str, Any]] = []
        for item in degraded_inputs:
            section = str(item.get("section") or "").strip()
            surface, route = section_surface.get(section, (_humanize_code(section), "/market/decision-cockpit"))
            items.append(
                {
                    "surface": surface,
                    "status": str(item.get("status") or "unavailable"),
                    "reason": _safe_reason_phrase(item.get("reason")),
                    "drilldownTargets": [_surface_link(surface, route, section or "degradedInputs")],
                }
            )
        if not research_preview.get("topCandidates"):
            items.append(
                {
                    "surface": "Research Radar",
                    "status": "unavailable",
                    "reason": _safe_reason_phrase(_RESEARCH_EMPTY_REASON),
                    "drilldownTargets": [_surface_link("Research Radar", "/research/radar", "topResearchPriorities")],
                }
            )
            items.append(
                {
                    "surface": "Stock Structure",
                    "status": "unavailable",
                    "reason": "Stock Structure drilldowns need a symbol in focus.",
                    "drilldownTargets": [
                        _surface_link("Stock Structure", "/stocks/structure-decision", "topResearchPriorities")
                    ],
                }
            )
        items.append(
            {
                "surface": "Portfolio Structure Review",
                "status": "unavailable",
                "reason": "Portfolio highlights are available from Daily Intelligence when owner context is present.",
                "drilldownTargets": [_surface_link("Portfolio", "/portfolio", "portfolioHighlights")],
            }
        )
        if options_status.get("gammaEvidenceStatus") == "unavailable":
            items.append(
                {
                    "surface": "Options / Gamma Observation",
                    "status": "unavailable",
                    "reason": _safe_reason_phrase(_OPTION_CHAIN_EMPTY_REASON),
                    "drilldownTargets": [_surface_link("Options / Gamma", "/options-lab", "scenarioRisks")],
                }
            )
        return _dedupe_surface_summary(items, fallback_links=priority_drilldowns)

    def _build_next_observation_steps(
        self,
        *,
        top_research_priorities: Sequence[Mapping[str, Any]],
        options_status: Mapping[str, Any],
        priority_drilldowns: Sequence[Mapping[str, str]],
    ) -> list[str]:
        steps: list[str] = []
        if top_research_priorities:
            steps.append("Review Research Radar evidence with Stock Structure context.")
        else:
            steps.append("Review Research Radar once candidate evidence becomes available.")
        if priority_drilldowns:
            steps.append("Open priority drilldowns before expanding the research queue.")
        steps.append("Use Scenario Lab to compare bounded regime assumptions.")
        if options_status.get("gammaEvidenceStatus") == "unavailable":
            steps.append("Keep Options/Gamma evidence in degraded observation review.")
        else:
            steps.append("Keep Options/Gamma evidence separate from decision-grade confidence.")
        return _dedupe(steps)[:4]

    @staticmethod
    def _workflow_step(
        *,
        surface: str,
        status: str,
        summary: str,
        drilldown_targets: Sequence[Mapping[str, str]],
    ) -> dict[str, Any]:
        return {
            "surface": surface,
            "status": status if status in {"available", "degraded", "unavailable"} else "unavailable",
            "summary": _safe_public_text(summary),
            "drilldownTargets": _dedupe_targets(drilldown_targets),
        }

    def _build_data_quality(
        self,
        market_regime_decision: Mapping[str, Any],
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
    ) -> dict[str, Any]:
        regime_quality = _mapping(market_regime_decision.get("dataQuality"))
        reason_codes = list(market_regime_decision.get("missingEvidence") or [])
        if str(market_regime_decision.get("confidence") or "").lower() == "low":
            reason_codes.append(_MARKET_REGIME_LOW_CONFIDENCE_REASON)
        if not research_preview.get("topCandidates"):
            reason_codes.append(_RESEARCH_EMPTY_REASON)
        if options_status.get("gammaEvidenceStatus") == "unavailable":
            reason_codes.append(_OPTION_CHAIN_EMPTY_REASON)
        reason_codes.append("options_observation_only")

        available_driver_count = int(regime_quality.get("availableDriverCount") or 0)
        status = "blocked" if (
            available_driver_count == 0
            and not research_preview.get("topCandidates")
            and options_status.get("gammaEvidenceStatus") == "unavailable"
        ) else "degraded"

        return {
            "status": status,
            "reasonCodes": _dedupe(reason_codes),
            "regimeEvidenceGrade": regime_quality.get("evidenceGrade"),
            "availableDriverCount": available_driver_count,
            "proxyEvidenceCount": int(regime_quality.get("proxyEvidenceCount") or 0),
            "consumerIssues": build_consumer_issues(reason_codes, regime_quality.get("confidenceCapReasons")),
        }

    def _build_driver_attribution(self, market_regime_decision: Mapping[str, Any]) -> dict[str, Any]:
        drivers = _mapping(market_regime_decision.get("driverScores"))
        driver_items = [
            _driver_item(driver_name, driver_payload)
            for driver_name, driver_payload in drivers.items()
            if isinstance(driver_payload, Mapping)
        ]
        positive = sorted(
            (
                item
                for item in driver_items
                if item["score"] > 0 and item["evidenceState"] not in {"unavailable", "blocked"}
            ),
            key=lambda item: (-item["score"], item["driver"]),
        )
        negative = sorted(
            (
                item
                for item in driver_items
                if item["score"] < 0 and item["evidenceState"] not in {"unavailable", "blocked"}
            ),
            key=lambda item: (item["score"], item["driver"]),
        )
        unavailable = sorted(
            (item for item in driver_items if item["evidenceState"] in {"unavailable", "blocked"}),
            key=lambda item: (item["evidenceState"] != "unavailable", item["driver"]),
        )

        return {
            "topPositiveDrivers": positive[:3],
            "topNegativeDrivers": negative[:3],
            "conflictingDrivers": _conflicting_driver_items(
                str(market_regime_decision.get("regime") or ""),
                positive,
                negative,
            ),
            "unavailableDrivers": unavailable,
        }

    def _build_confidence_diagnostics(
        self,
        market_regime_decision: Mapping[str, Any],
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
        data_quality: Mapping[str, Any],
    ) -> dict[str, Any]:
        regime_quality = _mapping(market_regime_decision.get("dataQuality"))
        missing_evidence = list(market_regime_decision.get("missingEvidence") or [])
        reason_codes = list(data_quality.get("reasonCodes") or [])
        confidence_projection = _market_regime_confidence_projection(market_regime_decision)
        evidence_strength = {
            "confidence": market_regime_decision.get("confidence", "low"),
            "rawConfidence": market_regime_decision.get("confidence", "low"),
            "consumerConfidence": confidence_projection["consumerConfidence"],
            "confidenceCap": confidence_projection["confidenceCap"],
            "confidenceState": confidence_projection["confidenceState"],
            "confidenceScore": market_regime_decision.get("confidenceScore"),
            "regimeEvidenceGrade": regime_quality.get("evidenceGrade"),
            "availableDriverCount": int(regime_quality.get("availableDriverCount") or 0),
            "scoringDriverCount": int(regime_quality.get("scoringDriverCount") or 0),
            "blockedDriverCount": int(regime_quality.get("blockedDriverCount") or 0),
            "missingDriverCount": int(regime_quality.get("missingDriverCount") or 0),
            "researchQueueQuality": research_preview.get("queueQuality", "thin"),
            "optionsGammaEvidenceStatus": options_status.get("gammaEvidenceStatus", "unavailable"),
        }

        return {
            "confidenceCaps": _dedupe(regime_quality.get("confidenceCapReasons") or []),
            "confidencePenalties": _dedupe([*missing_evidence, *reason_codes]),
            "evidenceStrength": evidence_strength,
            "missingEvidenceImpact": [
                {
                    "evidence": _safe_missing_evidence_label(item),
                    "impact": _missing_evidence_impact(str(item)),
                }
                for item in _dedupe(missing_evidence or reason_codes)
            ],
        }

    def _build_watch_triggers(
        self,
        market_regime_decision: Mapping[str, Any],
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
    ) -> list[dict[str, str]]:
        explanation = _mapping(market_regime_decision.get("explanation"))
        priorities = _mapping(market_regime_decision.get("researchPriorities"))
        confirms = _dedupe(explanation.get("whatConfirmsIt") or [])
        invalidates = _dedupe(explanation.get("whatInvalidatesIt") or [])
        watch_items = _dedupe([
            *(priorities.get("watchToday") or []),
            *(priorities.get("investigateNext") or []),
        ])
        triggers: list[dict[str, str]] = []

        for index, condition in enumerate(watch_items[:3], start=1):
            triggers.append(
                {
                    "triggerName": f"Regime watch {index}",
                    "driver": _infer_driver_name(condition),
                    "condition": str(condition),
                    "whyItMatters": "It helps confirm whether the current regime evidence remains coherent.",
                    "currentEvidence": (
                        confirms[0]
                        if confirms
                        else str(market_regime_decision.get("regime") or "lowConfidence")
                    ),
                }
            )
        if invalidates:
            triggers.append(
                {
                    "triggerName": "Regime invalidation watch",
                    "driver": "marketRegimeDecision",
                    "condition": invalidates[0],
                    "whyItMatters": "It identifies evidence that would weaken the current regime read.",
                    "currentEvidence": str(market_regime_decision.get("confidence") or "low"),
                }
            )
        if not research_preview.get("topCandidates"):
            triggers.append(
                {
                    "triggerName": "Research radar availability",
                    "driver": "researchQueuePreview",
                    "condition": "Research candidates become available with enough evidence quality.",
                    "whyItMatters": (
                        "It determines whether regime context can be paired with concrete research queue evidence."
                    ),
                    "currentEvidence": str(research_preview.get("queueQuality") or "thin"),
                }
            )
        if options_status.get("gammaEvidenceStatus") == "unavailable":
            triggers.append(
                {
                    "triggerName": "Options observation availability",
                    "driver": "optionsStructureStatus",
                    "condition": "Options structure evidence becomes available for observation only.",
                    "whyItMatters": (
                        "It separates options market structure context from decision-grade regime evidence."
                    ),
                    "currentEvidence": "unavailable",
                }
            )
        return triggers[:5]

    def _build_what_changed(
        self,
        market_regime_decision: Mapping[str, Any],
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
    ) -> list[str]:
        regime_label = _regime_label(market_regime_decision.get("regime") or "lowConfidence")
        confidence_projection = _market_regime_confidence_projection(market_regime_decision)
        confidence_label = _confidence_label(confidence_projection["consumerConfidence"])
        queue_quality = _queue_quality_label(research_preview.get("queueQuality") or "thin")
        option_status = str(options_status.get("gammaEvidenceStatus") or "unavailable")
        option_sentence = (
            "Options structure evidence is unavailable for this cockpit snapshot."
            if option_status == "unavailable"
            else "Options structure remains observation-only for this cockpit snapshot."
        )
        return [
            f"Current regime observation is {regime_label} with {confidence_label} confidence.",
            f"Research queue quality is {queue_quality}.",
            option_sentence,
        ]

    def _build_cockpit_readiness(
        self,
        market_regime_decision: Mapping[str, Any],
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
        data_quality: Mapping[str, Any],
    ) -> dict[str, Any]:
        reasons: list[str] = []
        confidence = str(market_regime_decision.get("confidence") or "low").lower()
        regime_quality = _mapping(market_regime_decision.get("dataQuality"))
        scoring_driver_count = int(
            regime_quality.get("scoringDriverCount")
            or data_quality.get("availableDriverCount")
            or 0
        )
        research_ready = bool(research_preview.get("topCandidates"))
        options_ready = options_status.get("gammaEvidenceStatus") != "unavailable"

        if confidence == "low" or scoring_driver_count < 3:
            reasons.append("market regime evidence is insufficient")
        if not research_ready:
            reasons.append("research radar candidates are unavailable")
        if not options_ready:
            reasons.append("options structure evidence is unavailable")

        if not reasons:
            return {
                "status": "ready",
                "reasons": ["core evidence is available for read-only decision support"],
            }
        if data_quality.get("status") == "blocked" or len(reasons) >= 3:
            return {"status": "insufficient", "reasons": reasons}
        return {"status": "degraded", "reasons": reasons}

    def _build_scenario_hints(self, market_regime_decision: Mapping[str, Any]) -> list[str]:
        explanation = _mapping(market_regime_decision.get("explanation"))
        hints = [
            "Regime confidence could strengthen if more score-grade drivers align with the current read.",
            "Regime confidence could weaken if leading drivers move against the current read together.",
        ]
        if market_regime_decision.get("missingEvidence"):
            hints.append("Confidence could improve if missing evidence becomes available through approved inputs.")
        if _mapping(market_regime_decision.get("dataQuality")).get("confidenceCapReasons"):
            hints.append("Confidence remains capped until source-quality limits clear.")
        for item in explanation.get("whatConfirmsIt") or []:
            hints.append(f"Confirmation hint: {_without_numeric_details(_safe_public_text(item))}")
            break
        for item in explanation.get("whatInvalidatesIt") or []:
            hints.append(f"Invalidation hint: {_without_numeric_details(_safe_public_text(item))}")
            break
        return _dedupe(hints)[:5]


def build_market_decision_cockpit(
    *,
    actor: Mapping[str, Any] | None = None,
    market_inputs: Mapping[str, Any] | None = None,
    market_regime_decision: Mapping[str, Any] | None = None,
    research_candidates: Sequence[Mapping[str, Any]] | None = None,
    option_contracts: Sequence[Any] | None = None,
    option_spot: float | int | str | None = None,
    market_overview_service: MarketOverviewService | None = None,
    now_provider: Callable[[], str] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the v1 market decision cockpit payload."""

    now = (lambda: generated_at) if generated_at is not None else now_provider
    return MarketDecisionCockpitService(
        market_overview_service=market_overview_service,
        now_provider=now,
    ).get_decision_cockpit(
        actor=actor,
        market_inputs=market_inputs,
        market_regime_decision=market_regime_decision,
        research_candidates=research_candidates,
        option_contracts=option_contracts,
        option_spot=option_spot,
    )


def _regime_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "Low-confidence observation"
    return _REGIME_LABELS.get(text, f"{_humanize_code(text)} observation")


def _confidence_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return _CONFIDENCE_LABELS.get(text.lower(), _humanize_code(text))


def _queue_quality_label(value: Any) -> str:
    text = str(value or "").strip().lower()
    return {
        "thin": "thin",
        "mixed": "mixed",
        "strong": "strong",
        "low_evidence": "low-evidence",
    }.get(text, _humanize_code(text).lower())


def _first_text(value: Any) -> str | None:
    for item in _safe_public_list(value):
        return item
    return None


def _safe_public_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for raw, replacement in {
        "riskOn": "Risk-on observation",
        "riskOff": "Risk-off observation",
        "lowConfidence": "Low-confidence observation",
        "research_candidates_unavailable": "research candidates are unavailable",
        "option_chain_unavailable": "options structure evidence is unavailable",
        "dealerGamma:unavailable": "options structure evidence is unavailable",
        "live_gex_not_implemented_v1": "live options gamma evidence is unavailable",
    }.items():
        text = text.replace(raw, replacement)
    return text


def _safe_public_list(value: Any) -> list[str]:
    if isinstance(value, str):
        text = _safe_public_text(value)
        return [text] if text else []
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        return []
    return _dedupe([text for item in value if (text := _safe_public_text(item))])


def _safe_reason_phrase(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return _SAFE_REASON_LABELS.get(text, _humanize_code(text))


def _safe_missing_evidence_label(value: Any) -> str:
    sanitized = sanitize_consumer_reason_payload({"reason": str(value or "")})
    return str(_mapping(sanitized).get("reason") or "")


def _safe_phrase_list(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        values = list(value)
    else:
        values = []
    return _dedupe([text for item in values if (text := _safe_reason_phrase(item))])


def _market_regime_confidence_projection(market_regime_decision: Mapping[str, Any]) -> dict[str, Any]:
    regime_quality = _mapping(market_regime_decision.get("dataQuality"))
    missing_evidence = [
        _safe_missing_evidence_label(item)
        for item in list(market_regime_decision.get("missingEvidence") or [])
        if _safe_missing_evidence_label(item)
    ]
    cap_reasons = _safe_phrase_list(regime_quality.get("confidenceCapReasons") or [])
    return project_confidence_evidence_state(
        raw_confidence_label=market_regime_decision.get("confidence"),
        raw_confidence_score=market_regime_decision.get("confidenceScore"),
        evidence_gaps=[*missing_evidence, *cap_reasons],
        evidence_completeness=regime_quality.get("evidenceGrade"),
    )


def _public_confidence_cap(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "value": int(value.get("value") or 0),
        "label": str(value.get("label") or "low"),
        "reasons": list(value.get("reasons") or []),
    }


def _dedupe_degraded(values: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        section = str(item.get("section") or "").strip()
        status = str(item.get("status") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if not section or not status or not reason:
            continue
        key = (section, status, reason)
        if key in seen:
            continue
        seen.add(key)
        result.append({"section": section, "status": status, "reason": reason})
    return result


def _dedupe_targets(values: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        label = str(item.get("label") or "").strip()
        route = str(item.get("route") or "").strip()
        section = str(item.get("section") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if not label or not route or not section:
            continue
        key = (label, route, section)
        if key in seen:
            continue
        seen.add(key)
        result.append({"label": label, "route": route, "section": section, "reason": reason})
    return result


def _surface_link(label: str, route: str, section: str) -> dict[str, str]:
    return {
        "label": label,
        "route": route,
        "section": section,
        "reason": f"Open {label} context.",
    }


def _dedupe_surface_summary(
    values: Sequence[Mapping[str, Any]],
    *,
    fallback_links: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in values:
        surface = str(item.get("surface") or "").strip()
        status = str(item.get("status") or "unavailable").strip()
        reason = _safe_reason_phrase(item.get("reason"))
        if not surface or not reason:
            continue
        key = (surface, reason)
        if key in seen:
            continue
        seen.add(key)
        links = _dedupe_targets(item.get("drilldownTargets") or [])
        if not links:
            links = list(fallback_links[:1])
        result.append(
            {
                "surface": surface,
                "status": status if status in {"available", "degraded", "unavailable"} else "unavailable",
                "reason": reason,
                "drilldownTargets": links,
            }
        )
    return result


def _humanize_code(value: str) -> str:
    text = value.replace("_", " ").replace(":", " ").replace("-", " ")
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = " ".join(text.split())
    return text[:1].upper() + text[1:] if text else ""


def _invalidation_conditions(payload: Mapping[str, Any]) -> list[str]:
    explanation = payload.get("explanation")
    if not isinstance(explanation, Mapping):
        return []
    return list(explanation.get("whatInvalidatesIt") or [])


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _driver_item(driver: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    score = _int_value(payload.get("score"))
    evidence_state = str(payload.get("evidenceState") or "unavailable")
    observations = _dedupe(payload.get("observations") or [])
    reasons = _dedupe(payload.get("reasons") or [])
    return {
        "driver": driver,
        "score": score,
        "evidenceState": evidence_state,
        "whyItMatters": _driver_why_it_matters(driver, score),
        "currentEvidence": observations or ["No current driver observation is available."],
        "reasonCodes": reasons,
        "consumerIssues": build_consumer_issues(reasons, evidence_state),
    }


def _driver_reason_codes(payload: Mapping[str, Any]) -> list[str]:
    drivers = _mapping(payload.get("driverScores"))
    reasons: list[str] = []
    for driver_payload in drivers.values():
        if not isinstance(driver_payload, Mapping):
            continue
        reasons.extend(str(reason) for reason in list(driver_payload.get("reasons") or []) if str(reason))
    return _dedupe(reasons)


def _conflicting_driver_items(
    regime: str,
    positive: Sequence[Mapping[str, Any]],
    negative: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not positive or not negative:
        return []
    negative_regimes = {"riskOff", "downsideAccelerationRisk", "eventRisk"}
    if regime in negative_regimes:
        return [
            {
                "driver": str(item["driver"]),
                "score": int(item["score"]),
                "condition": "Positive driver conflicts with negative regime evidence.",
                "currentEvidence": list(item.get("currentEvidence") or []),
            }
            for item in positive[:2]
        ]
    return [
        {
            "driver": str(item["driver"]),
            "score": int(item["score"]),
            "condition": "Negative driver conflicts with positive regime evidence.",
            "currentEvidence": list(item.get("currentEvidence") or []),
        }
        for item in negative[:2]
    ]


def _driver_why_it_matters(driver: str, score: int) -> str:
    direction = "positive" if score > 0 else "negative" if score < 0 else "neutral"
    labels = {
        "dealerGamma": "Options structure context can cap confidence when unavailable.",
        "breadthParticipation": "Breadth shows whether participation is broad or narrow.",
        "volatilityStructure": "Volatility helps separate orderly risk from stress.",
        "ratesDollar": "Rates-dollar pressure can change market liquidity conditions.",
        "liquidityCredit": (
            "Liquidity-credit evidence shows whether funding conditions are supportive or restrictive."
        ),
        "crossAssetRisk": "Cross-asset evidence checks whether adjacent markets confirm the read.",
        "sectorThemeRotation": "Sector-theme rotation shows whether leadership is concentrated or broadening.",
        "eventCatalyst": "Event catalyst evidence flags whether scheduled or unscheduled events dominate.",
    }
    return labels.get(driver, f"{driver} is a {direction} contributor to the current regime read.")


def _missing_evidence_impact(reason: str) -> str:
    if reason.startswith("dealerGamma"):
        return "Options structure remains observation-only and cannot raise regime confidence."
    if reason.startswith("research") or reason == _RESEARCH_EMPTY_REASON:
        return "Research queue context is thinner until candidate evidence is available."
    if reason.startswith("option") or reason == _OPTION_CHAIN_EMPTY_REASON:
        return "Options market structure remains unavailable for observation context."
    if "low_confidence" in reason:
        return "The cockpit should stay degraded until more score-grade drivers align."
    if "blocked" in reason:
        return "Blocked evidence cannot contribute to the regime read."
    return "Missing evidence limits confidence in the current regime read."


def _infer_driver_name(condition: Any) -> str:
    text = str(condition).lower()
    if "breadth" in text:
        return "breadthParticipation"
    if "volatility" in text:
        return "volatilityStructure"
    if "rate" in text or "dollar" in text:
        return "ratesDollar"
    if "liquidity" in text or "credit" in text:
        return "liquidityCredit"
    if "cross-asset" in text:
        return "crossAssetRisk"
    if "sector" in text or "theme" in text or "rotation" in text:
        return "sectorThemeRotation"
    if "event" in text:
        return "eventCatalyst"
    if "gamma" in text:
        return "dealerGamma"
    return "marketRegimeDecision"


def _without_numeric_details(value: Any) -> str:
    text = str(value)
    cleaned = "".join(" " if char.isdigit() else char for char in text)
    return " ".join(cleaned.split())


def _int_value(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    if number != number or number in {float("inf"), float("-inf")}:
        return 0
    return int(round(number))


def _dedupe(items: Sequence[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


__all__ = [
    "MarketDecisionCockpitService",
    "NO_ADVICE_DISCLOSURE",
    "SCHEMA_VERSION",
    "build_market_decision_cockpit",
]
