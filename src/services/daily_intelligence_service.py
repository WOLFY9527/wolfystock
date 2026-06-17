# -*- coding: utf-8 -*-
"""Read-only daily intelligence briefing aggregation service."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote

from src.repositories.scanner_repo import ScannerRepository
from src.services.market_overview_service import MarketOverviewService
from src.services.portfolio_structure_review_service import PortfolioStructureReviewService
from src.services.research_radar_service import ResearchRadarService
from src.services.watchlist_research_overlay_service import WatchlistResearchOverlayService
from src.services.consumer_issue_labels import build_consumer_issues


DAILY_INTELLIGENCE_SERVICE_SCHEMA_VERSION = "daily_intelligence_briefing_v1"
DAILY_INTELLIGENCE_NO_ADVICE_DISCLOSURE = (
    "Observation-only research briefing; not personalized financial advice."
)
_SCENARIO_RISK_UNAVAILABLE_REASON = "scenario_risk_read_model_unavailable"
_SAFE_REASON_LABELS = {
    "owner_context_missing": "Signed-in owner context is unavailable.",
    "research_radar_unavailable": "Research radar context is unavailable.",
    "scannerCandidates": "Scanner candidate evidence is thin.",
    "watchlist_unavailable": "Watchlist context is unavailable.",
    "watchlist_research_context": "Watchlist research context is unavailable.",
    "portfolio_structure_review_unavailable": "Portfolio structure review is unavailable.",
    "cached_portfolio_holdings": "Cached portfolio holdings are unavailable.",
    "theme_or_sector_exposure": "Theme or sector exposure details are unavailable.",
    _SCENARIO_RISK_UNAVAILABLE_REASON: "Scenario risk read model is unavailable for this briefing.",
    "research_queue_origin": "Research radar queue context.",
    "scanner_candidates_origin": "Scanner candidate context.",
    "symbol_structure_detail": "Symbol structure detail.",
    "portfolio_structure_context": "Portfolio structure context.",
    "degraded_state": "Degraded input state.",
    "themeBreadth": "Theme breadth evidence is incomplete.",
    "evidence_partial": "Evidence is partial.",
    "local_ohlcv_evidence": "Local OHLCV evidence is incomplete.",
    "cached_or_stale_evidence": "Evidence may be cached or stale.",
    "concentrated_exposure": "Concentrated exposure.",
}
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


class DailyIntelligenceService:
    """Assemble a bounded daily research briefing from existing read-only services."""

    def __init__(
        self,
        *,
        market_overview_service: MarketOverviewService | None = None,
        research_radar_service: ResearchRadarService | None = None,
        watchlist_overlay_service: WatchlistResearchOverlayService | None = None,
        portfolio_structure_review_service: PortfolioStructureReviewService | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.market_overview_service = market_overview_service or MarketOverviewService()
        self.research_radar_service = research_radar_service or ResearchRadarService(
            scanner_repository=ScannerRepository()
        )
        self.watchlist_overlay_service = watchlist_overlay_service or WatchlistResearchOverlayService()
        self.portfolio_structure_review_service = (
            portfolio_structure_review_service or PortfolioStructureReviewService()
        )
        self._now = now or (lambda: datetime.now(timezone.utc))

    def build_briefing(
        self,
        *,
        actor: Mapping[str, Any] | None = None,
        owner_id: str | None = None,
        market: str | None = None,
        profile: str | None = None,
    ) -> dict[str, Any]:
        generated_at = self._now()
        regime = self.market_overview_service.get_market_regime_decision(actor=dict(actor or {}))
        briefing = self.market_overview_service.get_market_briefing(actor=dict(actor or {}))

        degraded_inputs: list[dict[str, str]] = []
        evidence_gaps: list[str] = []

        market_regime_summary = self._market_regime_summary(regime)
        what_changed = self._what_changed(briefing)

        radar_payload = self._research_radar_payload(
            owner_id=owner_id,
            market=market,
            profile=profile,
            degraded_inputs=degraded_inputs,
            evidence_gaps=evidence_gaps,
        )
        watchlist_payload = self._watchlist_payload(
            owner_id=owner_id,
            degraded_inputs=degraded_inputs,
            evidence_gaps=evidence_gaps,
        )
        portfolio_payload = self._portfolio_payload(
            owner_id=owner_id,
            degraded_inputs=degraded_inputs,
            evidence_gaps=evidence_gaps,
        )
        self._append_degraded(
            degraded_inputs,
            section="scenarioRisks",
            status="unavailable",
            reason=_SCENARIO_RISK_UNAVAILABLE_REASON,
        )
        evidence_gaps.append(_SCENARIO_RISK_UNAVAILABLE_REASON)

        top_research_priorities = self._top_research_priorities(radar_payload)
        scanner_highlights = self._scanner_highlights(radar_payload)
        watchlist_highlights = self._watchlist_highlights(watchlist_payload)
        portfolio_highlights = self._portfolio_highlights(portfolio_payload)
        section_links = self._section_links(
            radar_payload=radar_payload,
            watchlist_payload=watchlist_payload,
            portfolio_payload=portfolio_payload,
        )
        scenario_risks = [
            {
                "label": "Scenario risk coverage",
                "source": "Daily Intelligence",
                "observations": [
                    "Scenario risk read model is unavailable for this briefing."
                ],
                "evidenceGaps": [_safe_reason_phrase(_SCENARIO_RISK_UNAVAILABLE_REASON)],
            }
        ]
        safe_evidence_gaps = _safe_phrase_list(evidence_gaps)
        safe_degraded_inputs = _safe_degraded_inputs(degraded_inputs)
        drilldown_targets = section_links
        consumer_issues = build_consumer_issues(
            evidence_gaps,
            degraded_inputs,
            [item.get("evidenceGaps") for item in top_research_priorities],
            [item.get("evidenceGaps") for item in scanner_highlights],
            [item.get("riskFlags") for item in scanner_highlights],
            [item.get("evidenceGaps") for item in watchlist_highlights],
            [item.get("riskFlags") for item in watchlist_highlights],
            [item.get("missingEvidence") for item in portfolio_highlights],
            [item.get("riskFlags") for item in portfolio_highlights],
        )
        synthesis = self._build_synthesis_contract(
            market_regime_summary=market_regime_summary,
            top_research_priorities=top_research_priorities,
            scanner_highlights=scanner_highlights,
            watchlist_highlights=watchlist_highlights,
            portfolio_highlights=portfolio_highlights,
            scenario_risks=scenario_risks,
            degraded_inputs=safe_degraded_inputs,
            drilldown_targets=drilldown_targets,
        )

        return {
            "schemaVersion": DAILY_INTELLIGENCE_SERVICE_SCHEMA_VERSION,
            "generatedAt": generated_at.isoformat(),
            "briefingDate": generated_at.date().isoformat(),
            "sessionLabel": self._session_label(generated_at),
            "marketRegimeSummary": market_regime_summary,
            "whatChanged": what_changed,
            "sectionLinks": section_links,
            "topResearchPriorities": top_research_priorities,
            "scannerHighlights": scanner_highlights,
            "watchlistHighlights": watchlist_highlights,
            "portfolioHighlights": portfolio_highlights,
            "portfolioStructureHighlights": portfolio_highlights,
            "scenarioRisks": scenario_risks,
            "evidenceGaps": safe_evidence_gaps,
            "degradedInputs": safe_degraded_inputs,
            "drilldownTargets": drilldown_targets,
            "researchWorkflow": synthesis["researchWorkflow"],
            "crossSurfaceEvidence": synthesis["crossSurfaceEvidence"],
            "topResearchQuestions": synthesis["topResearchQuestions"],
            "priorityDrilldowns": synthesis["priorityDrilldowns"],
            "evidenceConflicts": synthesis["evidenceConflicts"],
            "degradedSurfaceSummary": synthesis["degradedSurfaceSummary"],
            "nextObservationSteps": synthesis["nextObservationSteps"],
            "consumerIssues": consumer_issues,
            "noAdviceDisclosure": DAILY_INTELLIGENCE_NO_ADVICE_DISCLOSURE,
            "observationOnly": True,
            "decisionGrade": False,
        }

    def _research_radar_payload(
        self,
        *,
        owner_id: str | None,
        market: str | None,
        profile: str | None,
        degraded_inputs: list[dict[str, str]],
        evidence_gaps: list[str],
    ) -> dict[str, Any]:
        if not owner_id:
            self._append_degraded(
                degraded_inputs,
                section="topResearchPriorities",
                status="degraded",
                reason="owner_context_missing",
            )
            self._append_degraded(
                degraded_inputs,
                section="scannerHighlights",
                status="degraded",
                reason="owner_context_missing",
            )
            evidence_gaps.append("owner_context_missing")
            return {}

        try:
            payload = self.research_radar_service.build_from_latest_scanner_run(
                market=market,
                profile=profile,
                owner_id=owner_id,
                limit=10,
            )
        except Exception:
            self._append_degraded(
                degraded_inputs,
                section="topResearchPriorities",
                status="unavailable",
                reason="research_radar_unavailable",
            )
            self._append_degraded(
                degraded_inputs,
                section="scannerHighlights",
                status="unavailable",
                reason="research_radar_unavailable",
            )
            evidence_gaps.append("research_radar_unavailable")
            return {}

        queue = list(payload.get("researchQueue") or [])
        if not queue:
            self._append_degraded(
                degraded_inputs,
                section="scannerHighlights",
                status="degraded",
                reason="scannerCandidates",
            )
        evidence_gaps.extend(_safe_text_list(payload.get("evidenceGaps")))
        return payload

    def _watchlist_payload(
        self,
        *,
        owner_id: str | None,
        degraded_inputs: list[dict[str, str]],
        evidence_gaps: list[str],
    ) -> dict[str, Any]:
        if not owner_id:
            self._append_degraded(
                degraded_inputs,
                section="watchlistHighlights",
                status="degraded",
                reason="owner_context_missing",
            )
            evidence_gaps.append("owner_context_missing")
            return {}

        try:
            payload = self.watchlist_overlay_service.build_overlay(owner_id=owner_id)
        except Exception:
            self._append_degraded(
                degraded_inputs,
                section="watchlistHighlights",
                status="unavailable",
                reason="watchlist_unavailable",
            )
            evidence_gaps.append("watchlist_unavailable")
            return {}

        items = list(payload.get("items") or [])
        if not items:
            self._append_degraded(
                degraded_inputs,
                section="watchlistHighlights",
                status="degraded",
                reason="watchlist_research_context",
            )
        evidence_gaps.extend(_safe_text_list(payload.get("missingEvidence")))
        return payload

    def _portfolio_payload(
        self,
        *,
        owner_id: str | None,
        degraded_inputs: list[dict[str, str]],
        evidence_gaps: list[str],
    ) -> dict[str, Any]:
        if not owner_id:
            self._append_degraded(
                degraded_inputs,
                section="portfolioStructureHighlights",
                status="degraded",
                reason="owner_context_missing",
            )
            evidence_gaps.append("owner_context_missing")
            return {}

        try:
            payload = self.portfolio_structure_review_service.build_review(owner_id=owner_id, max_items=5)
        except Exception:
            self._append_degraded(
                degraded_inputs,
                section="portfolioStructureHighlights",
                status="unavailable",
                reason="portfolio_structure_review_unavailable",
            )
            evidence_gaps.append("portfolio_structure_review_unavailable")
            return {}

        items = list(payload.get("holdingsStructure") or [])
        if not items:
            self._append_degraded(
                degraded_inputs,
                section="portfolioStructureHighlights",
                status="degraded",
                reason="cached_portfolio_holdings",
            )
        evidence_gaps.extend(_missing_evidence_codes(payload.get("missingEvidence")))
        return payload

    def _market_regime_summary(self, regime: Mapping[str, Any]) -> dict[str, Any]:
        explanation = _mapping(regime.get("explanation"))
        regime_name = _text(regime.get("regime")) or "lowConfidence"
        confidence = _text(regime.get("confidence")) or "low"
        regime_label = _regime_label(regime_name)
        summary = _first_text(explanation.get("whyThisRegime")) or f"Current regime observation is {regime_label}."
        return {
            "regime": regime_label,
            "confidence": _confidence_label(confidence),
            "summary": _safe_public_text(summary),
            "supportingObservations": _safe_public_list(explanation.get("whatConfirmsIt")),
            "invalidationObservations": _safe_public_list(explanation.get("whatInvalidatesIt")),
        }

    def _what_changed(self, briefing: Mapping[str, Any]) -> list[str]:
        items = list(briefing.get("items") or [])
        messages: list[str] = []
        for item in items[:4]:
            payload = _mapping(item)
            title = _text(payload.get("title"))
            message = _text(payload.get("message"))
            if title and message:
                messages.append(_safe_public_text(f"{title}: {message}"))
            elif title:
                messages.append(_safe_public_text(title))
            elif message:
                messages.append(_safe_public_text(message))
        return messages

    def _top_research_priorities(self, radar_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        queue = list(radar_payload.get("researchQueue") or [])
        items: list[dict[str, Any]] = []
        for item in queue[:5]:
            payload = _mapping(item)
            ticker = _text(payload.get("ticker")) or _text(payload.get("symbol")) or None
            items.append(
                {
                    "label": f"{ticker or 'Unknown'} research queue",
                    "source": "Research Radar",
                    "priority": _text(payload.get("priority")) or None,
                    "ticker": ticker,
                    "observations": _safe_public_list(payload.get("whyOnRadar")),
                    "whatToVerify": _safe_public_list(payload.get("whatToVerify")),
                    "evidenceGaps": _safe_phrase_list(_safe_text_list(payload.get("evidenceGaps"))),
                    "evidenceLinks": self._item_links(
                        section="topResearchPriorities",
                        ticker=ticker,
                        primary_label="Research Radar",
                        primary_route="/research/radar",
                        primary_reason="research_queue_origin",
                    ),
                }
            )
        return items

    def _scanner_highlights(self, radar_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        queue = list(radar_payload.get("researchQueue") or [])
        highlights: list[dict[str, Any]] = []
        for item in queue[:3]:
            payload = _mapping(item)
            ticker = _text(payload.get("ticker")) or _text(payload.get("symbol")) or "UNKNOWN"
            highlights.append(
                {
                    "ticker": ticker,
                    "priority": _text(payload.get("priority")) or "medium",
                    "observations": _safe_public_list(payload.get("whyOnRadar")),
                    "whatToVerify": _safe_public_list(payload.get("whatToVerify")),
                    "evidenceGaps": _safe_phrase_list(_safe_text_list(payload.get("evidenceGaps"))),
                    "riskFlags": _safe_phrase_list(_safe_text_list(payload.get("riskFlags"))),
                    "evidenceLinks": self._item_links(
                        section="scannerHighlights",
                        ticker=ticker,
                        primary_label="Research Radar",
                        primary_route="/research/radar",
                        primary_reason="research_queue_origin",
                    ),
                }
            )
        return highlights

    def _watchlist_highlights(self, watchlist_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        items = list(watchlist_payload.get("items") or [])
        highlights: list[dict[str, Any]] = []
        for item in items[:3]:
            payload = _mapping(item)
            ticker = _text(payload.get("ticker")) or "UNKNOWN"
            highlights.append(
                {
                    "ticker": ticker,
                    "structureState": _safe_reason_phrase(_text(payload.get("structureState")) or "unavailable"),
                    "researchPriority": _confidence_label(_text(payload.get("researchPriority"))) or None,
                    "whyWatching": _safe_public_text(payload.get("whyWatching")) or None,
                    "whatToVerify": _safe_public_list(payload.get("whatToVerify")),
                    "evidenceGaps": _safe_phrase_list(_safe_text_list(payload.get("evidenceGaps"))),
                    "riskFlags": _safe_phrase_list(_safe_text_list(payload.get("riskFlags"))),
                    "evidenceLinks": self._item_links(
                        section="watchlistHighlights",
                        ticker=ticker,
                        primary_label="Watchlist",
                        primary_route="/watchlist",
                        primary_reason="watchlist_research_context",
                    ),
                }
            )
        return highlights

    def _portfolio_highlights(self, portfolio_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        items = list(portfolio_payload.get("holdingsStructure") or [])
        highlights: list[dict[str, Any]] = []
        for item in items[:3]:
            payload = _mapping(item)
            notes = _mapping(payload.get("researchNotes"))
            ticker = _text(payload.get("ticker")) or "UNKNOWN"
            highlights.append(
                {
                    "ticker": ticker,
                    "structureState": _safe_reason_phrase(_text(payload.get("structureState")) or "unavailable"),
                    "confidence": _confidence_label(_text(payload.get("confidence")) or "low"),
                    "watchNext": _safe_public_list(notes.get("watchNext")),
                    "riskFlags": (
                        _safe_phrase_list(_safe_text_list(payload.get("riskFlags")))
                        or _safe_phrase_list(_safe_text_list(notes.get("riskFlags")))
                    ),
                    "missingEvidence": _safe_phrase_list(_missing_evidence_codes(payload.get("missingEvidence"))),
                    "evidenceLinks": self._item_links(
                        section="portfolioStructureHighlights",
                        ticker=ticker,
                        primary_label="Portfolio",
                        primary_route="/portfolio",
                        primary_reason="portfolio_structure_context",
                    ),
                }
            )
        return highlights

    def _section_links(
        self,
        *,
        radar_payload: Mapping[str, Any],
        watchlist_payload: Mapping[str, Any],
        portfolio_payload: Mapping[str, Any],
    ) -> list[dict[str, str]]:
        links: list[dict[str, str]] = []
        if radar_payload:
            links.extend(
                [
                    self._evidence_link(
                        label="Research Radar",
                        route="/research/radar",
                        section="topResearchPriorities",
                        reason="research_queue_origin",
                    ),
                    self._evidence_link(
                        label="Scanner",
                        route="/scanner",
                        section="scannerHighlights",
                        reason="scanner_candidates_origin",
                    ),
                    self._evidence_link(
                        label="Research Radar",
                        route="/research/radar",
                        section="scannerHighlights",
                        reason="research_queue_origin",
                    ),
                ]
            )
        if watchlist_payload:
            links.append(
                self._evidence_link(
                    label="Watchlist",
                    route="/watchlist",
                    section="watchlistHighlights",
                    reason="watchlist_research_context",
                )
            )
        if portfolio_payload:
            links.append(
                self._evidence_link(
                    label="Portfolio",
                    route="/portfolio",
                    section="portfolioStructureHighlights",
                    reason="portfolio_structure_context",
                )
            )
        return _dedupe_links(links)

    def _build_synthesis_contract(
        self,
        *,
        market_regime_summary: Mapping[str, Any],
        top_research_priorities: Sequence[Mapping[str, Any]],
        scanner_highlights: Sequence[Mapping[str, Any]],
        watchlist_highlights: Sequence[Mapping[str, Any]],
        portfolio_highlights: Sequence[Mapping[str, Any]],
        scenario_risks: Sequence[Mapping[str, Any]],
        degraded_inputs: Sequence[Mapping[str, str]],
        drilldown_targets: Sequence[Mapping[str, str]],
    ) -> dict[str, Any]:
        priority_drilldowns = self._priority_drilldowns(
            top_research_priorities=top_research_priorities,
            scanner_highlights=scanner_highlights,
            watchlist_highlights=watchlist_highlights,
            portfolio_highlights=portfolio_highlights,
            drilldown_targets=drilldown_targets,
        )
        degraded_surface_summary = self._degraded_surface_summary(
            degraded_inputs=degraded_inputs,
            top_research_priorities=top_research_priorities,
            scanner_highlights=scanner_highlights,
            portfolio_highlights=portfolio_highlights,
            scenario_risks=scenario_risks,
        )

        return {
            "researchWorkflow": self._research_workflow(
                market_regime_summary=market_regime_summary,
                top_research_priorities=top_research_priorities,
                scanner_highlights=scanner_highlights,
                watchlist_highlights=watchlist_highlights,
                portfolio_highlights=portfolio_highlights,
                scenario_risks=scenario_risks,
                degraded_surface_summary=degraded_surface_summary,
                priority_drilldowns=priority_drilldowns,
            ),
            "crossSurfaceEvidence": self._cross_surface_evidence(
                top_research_priorities=top_research_priorities,
                portfolio_highlights=portfolio_highlights,
                scenario_risks=scenario_risks,
                priority_drilldowns=priority_drilldowns,
            ),
            "topResearchQuestions": self._top_research_questions(
                top_research_priorities=top_research_priorities,
                portfolio_highlights=portfolio_highlights,
                priority_drilldowns=priority_drilldowns,
            ),
            "priorityDrilldowns": priority_drilldowns,
            "evidenceConflicts": [],
            "degradedSurfaceSummary": degraded_surface_summary,
            "nextObservationSteps": self._next_observation_steps(
                top_research_priorities=top_research_priorities,
                portfolio_highlights=portfolio_highlights,
                priority_drilldowns=priority_drilldowns,
            ),
        }

    def _research_workflow(
        self,
        *,
        market_regime_summary: Mapping[str, Any],
        top_research_priorities: Sequence[Mapping[str, Any]],
        scanner_highlights: Sequence[Mapping[str, Any]],
        watchlist_highlights: Sequence[Mapping[str, Any]],
        portfolio_highlights: Sequence[Mapping[str, Any]],
        scenario_risks: Sequence[Mapping[str, Any]],
        degraded_surface_summary: Sequence[Mapping[str, Any]],
        priority_drilldowns: Sequence[Mapping[str, str]],
    ) -> list[dict[str, Any]]:
        degraded_surfaces = {
            str(item.get("surface") or ""): str(item.get("status") or "unavailable")
            for item in degraded_surface_summary
        }
        stock_links = [link for link in priority_drilldowns if "structure-decision" in str(link.get("route") or "")]
        regime_label = _text(market_regime_summary.get("regime")) or "Market regime observation"
        steps = [
            self._workflow_step(
                surface="Market Overview",
                status="available",
                summary=f"{regime_label} is the starting context for this briefing.",
                drilldown_targets=[self._surface_link("Market Overview", "/market-overview", "marketRegimeSummary")],
            ),
            self._workflow_step(
                surface="Research Radar",
                status=(
                    "available"
                    if top_research_priorities or scanner_highlights
                    else degraded_surfaces.get("Research Radar", "unavailable")
                ),
                summary=(
                    "Research Radar evidence is connected to the briefing queue."
                    if top_research_priorities or scanner_highlights
                    else "Research Radar evidence is unavailable for this briefing."
                ),
                drilldown_targets=[self._surface_link("Research Radar", "/research/radar", "topResearchPriorities")],
            ),
            self._workflow_step(
                surface="Portfolio Structure Review",
                status=(
                    "available"
                    if portfolio_highlights
                    else degraded_surfaces.get("Portfolio Structure Review", "unavailable")
                ),
                summary=(
                    "Portfolio structure observations are connected for owner context."
                    if portfolio_highlights
                    else "Portfolio structure observations need owner context or refreshed evidence."
                ),
                drilldown_targets=[self._surface_link("Portfolio", "/portfolio", "portfolioStructureHighlights")],
            ),
            self._workflow_step(
                surface="Scenario Lab",
                status="unavailable" if scenario_risks else "available",
                summary="Scenario Lab is tracked as a degraded planning surface for this briefing.",
                drilldown_targets=[self._surface_link("Scenario Lab", "/scenario-lab", "scenarioRisks")],
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
                or [
                    self._surface_link(
                        "Stock Structure",
                        "/stocks/structure-decision",
                        "topResearchPriorities",
                    )
                ],
            ),
            self._workflow_step(
                surface="Options / Gamma Observation",
                status="unavailable",
                summary=(
                    "Options and gamma evidence is marked unavailable until existing observation inputs are present."
                ),
                drilldown_targets=[self._surface_link("Options / Gamma", "/options-lab", "scenarioRisks")],
            ),
        ]
        if watchlist_highlights:
            steps.insert(
                3,
                self._workflow_step(
                    surface="Watchlist",
                    status="available",
                    summary="Watchlist observations are connected for owner context.",
                    drilldown_targets=[self._surface_link("Watchlist", "/watchlist", "watchlistHighlights")],
                ),
            )
        return steps

    def _cross_surface_evidence(
        self,
        *,
        top_research_priorities: Sequence[Mapping[str, Any]],
        portfolio_highlights: Sequence[Mapping[str, Any]],
        scenario_risks: Sequence[Mapping[str, Any]],
        priority_drilldowns: Sequence[Mapping[str, str]],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        radar_links = [link for link in priority_drilldowns if str(link.get("route")) == "/research/radar"]
        stock_links = [link for link in priority_drilldowns if "structure-decision" in str(link.get("route") or "")]
        portfolio_links = [link for link in priority_drilldowns if str(link.get("route")) == "/portfolio"]
        scenario_link = self._surface_link("Scenario Lab", "/scenario-lab", "scenarioRisks")
        options_link = self._surface_link("Options / Gamma", "/options-lab", "scenarioRisks")

        if top_research_priorities:
            items.append(
                {
                    "surfaces": ["Market Overview", "Research Radar"],
                    "observation": "Market context can be reviewed beside the active research queue.",
                    "drilldownTargets": _dedupe_links([*radar_links[:1], scenario_link]),
                }
            )
        if stock_links:
            items.append(
                {
                    "surfaces": ["Research Radar", "Stock Structure"],
                    "observation": "Symbols in the research queue have structure drilldowns for verification.",
                    "drilldownTargets": _dedupe_links([*radar_links[:1], *stock_links[:2]]),
                }
            )
        if portfolio_highlights:
            items.append(
                {
                    "surfaces": ["Portfolio Structure Review", "Stock Structure"],
                    "observation": "Portfolio structure observations can be checked against symbol structure detail.",
                    "drilldownTargets": _dedupe_links([*portfolio_links[:1], *stock_links[:2]]),
                }
            )
        if scenario_risks:
            items.append(
                {
                    "surfaces": ["Scenario Lab", "Options / Gamma Observation"],
                    "observation": "Scenario and options evidence are explicit degraded inputs for this briefing.",
                    "drilldownTargets": _dedupe_links([scenario_link, options_link]),
                }
            )
        return items

    def _top_research_questions(
        self,
        *,
        top_research_priorities: Sequence[Mapping[str, Any]],
        portfolio_highlights: Sequence[Mapping[str, Any]],
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
                    "drilldownTargets": _dedupe_links([*radar_links[:1], *stock_links[:2]]),
                }
            )
        if portfolio_highlights:
            questions.append(
                {
                    "question": "Which portfolio exposures need updated structure evidence?",
                    "surface": "Portfolio Structure Review",
                    "drilldownTargets": _dedupe_links([
                        self._surface_link("Portfolio", "/portfolio", "portfolioStructureHighlights"),
                        *stock_links[:2],
                    ]),
                }
            )
        questions.extend(
            [
                {
                    "question": "Which scenario assumptions would change the current regime observation?",
                    "surface": "Scenario Lab",
                    "drilldownTargets": [self._surface_link("Scenario Lab", "/scenario-lab", "scenarioRisks")],
                },
                {
                    "question": "Which options structure evidence is still unavailable for observation context?",
                    "surface": "Options / Gamma Observation",
                    "drilldownTargets": [self._surface_link("Options / Gamma", "/options-lab", "scenarioRisks")],
                },
            ]
        )
        return questions[:5]

    def _priority_drilldowns(
        self,
        *,
        top_research_priorities: Sequence[Mapping[str, Any]],
        scanner_highlights: Sequence[Mapping[str, Any]],
        watchlist_highlights: Sequence[Mapping[str, Any]],
        portfolio_highlights: Sequence[Mapping[str, Any]],
        drilldown_targets: Sequence[Mapping[str, str]],
    ) -> list[dict[str, str]]:
        if not drilldown_targets and not top_research_priorities and not scanner_highlights:
            return []
        links: list[Mapping[str, str]] = list(drilldown_targets)
        for collection in (
            top_research_priorities,
            scanner_highlights,
            watchlist_highlights,
            portfolio_highlights,
        ):
            for item in collection:
                links.extend(_mapping(item).get("evidenceLinks") or [])
        links.append(self._surface_link("Scenario Lab", "/scenario-lab", "scenarioRisks"))
        links.append(self._surface_link("Options / Gamma", "/options-lab", "scenarioRisks"))
        return _dedupe_links(links)[:10]

    def _degraded_surface_summary(
        self,
        *,
        degraded_inputs: Sequence[Mapping[str, str]],
        top_research_priorities: Sequence[Mapping[str, Any]],
        scanner_highlights: Sequence[Mapping[str, Any]],
        portfolio_highlights: Sequence[Mapping[str, Any]],
        scenario_risks: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        section_surface = {
            "topResearchPriorities": ("Research Radar", "/research/radar"),
            "scannerHighlights": ("Research Radar", "/research/radar"),
            "watchlistHighlights": ("Watchlist", "/watchlist"),
            "portfolioHighlights": ("Portfolio Structure Review", "/portfolio"),
            "portfolioStructureHighlights": ("Portfolio Structure Review", "/portfolio"),
            "scenarioRisks": ("Scenario Lab", "/scenario-lab"),
        }
        items: list[dict[str, Any]] = []
        for item in degraded_inputs:
            section = _text(item.get("section"))
            surface, route = section_surface.get(section, (_humanize_code(section), "/market/decision-cockpit"))
            items.append(
                {
                    "surface": surface,
                    "status": _text(item.get("status")) or "unavailable",
                    "reason": _safe_reason_phrase(item.get("reason")),
                    "drilldownTargets": [self._surface_link(surface, route, section or "degradedInputs")],
                }
            )
        if not top_research_priorities and not scanner_highlights:
            items.append(
                {
                    "surface": "Research Radar",
                    "status": "unavailable",
                    "reason": "Research Radar evidence is unavailable for this briefing.",
                    "drilldownTargets": [
                        self._surface_link("Research Radar", "/research/radar", "topResearchPriorities")
                    ],
                }
            )
        if not portfolio_highlights:
            items.append(
                {
                    "surface": "Portfolio Structure Review",
                    "status": "unavailable",
                    "reason": "Portfolio structure observations need owner context or refreshed evidence.",
                    "drilldownTargets": [self._surface_link("Portfolio", "/portfolio", "portfolioStructureHighlights")],
                }
            )
        if scenario_risks:
            items.append(
                {
                    "surface": "Scenario Lab",
                    "status": "unavailable",
                    "reason": "Scenario risk read model is unavailable for this briefing.",
                    "drilldownTargets": [self._surface_link("Scenario Lab", "/scenario-lab", "scenarioRisks")],
                }
            )
        items.append(
            {
                "surface": "Options / Gamma Observation",
                "status": "unavailable",
                "reason": "Options and gamma evidence is unavailable for this briefing.",
                "drilldownTargets": [self._surface_link("Options / Gamma", "/options-lab", "scenarioRisks")],
            }
        )
        return _dedupe_surface_summary(items)

    def _next_observation_steps(
        self,
        *,
        top_research_priorities: Sequence[Mapping[str, Any]],
        portfolio_highlights: Sequence[Mapping[str, Any]],
        priority_drilldowns: Sequence[Mapping[str, str]],
    ) -> list[str]:
        steps: list[str] = []
        if top_research_priorities:
            steps.append("Review Research Radar evidence with Stock Structure context.")
        if portfolio_highlights:
            steps.append("Compare portfolio structure observations with symbol structure detail.")
        if priority_drilldowns:
            steps.append("Open priority drilldowns before expanding the research queue.")
        steps.append("Keep Scenario Lab and Options/Gamma evidence in observation-only review.")
        return _dedupe(steps)[:4]

    def _workflow_step(
        self,
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
            "drilldownTargets": _dedupe_links(drilldown_targets),
        }

    def _surface_link(self, label: str, route: str, section: str) -> dict[str, str]:
        return self._evidence_link(
            label=label,
            route=route,
            section=section,
            reason=f"Open {label} context.",
        )

    def _item_links(
        self,
        *,
        section: str,
        ticker: str | None,
        primary_label: str,
        primary_route: str,
        primary_reason: str,
    ) -> list[dict[str, str]]:
        links = [self._evidence_link(label=primary_label, route=primary_route, section=section, reason=primary_reason)]
        symbol_link = self._stock_structure_link(section=section, ticker=ticker)
        if symbol_link is not None:
            links.append(symbol_link)
        return links

    @staticmethod
    def _evidence_link(*, label: str, route: str, section: str, reason: str) -> dict[str, str]:
        return {
            "label": label,
            "route": route,
            "section": section,
            "reason": _safe_reason_phrase(reason),
        }

    @staticmethod
    def _stock_structure_link(*, section: str, ticker: str | None) -> dict[str, str] | None:
        symbol = _text(ticker)
        if not symbol or symbol.upper() == "UNKNOWN":
            return None
        return {
            "label": "Stock Structure",
            "route": f"/stocks/{quote(symbol, safe='')}/structure-decision",
            "section": section,
            "reason": _safe_reason_phrase("symbol_structure_detail"),
        }

    @staticmethod
    def _session_label(generated_at: datetime) -> str:
        hour = generated_at.hour
        if hour < 6:
            return "overnight"
        if hour < 12:
            return "pre-market"
        if hour < 17:
            return "mid-session"
        return "after-close"

    @staticmethod
    def _append_degraded(
        items: list[dict[str, str]],
        *,
        section: str,
        status: str,
        reason: str,
    ) -> None:
        entry = {"section": section, "status": status, "reason": reason}
        if entry not in items:
            items.append(entry)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_text_list(value: Any) -> list[str]:
    if isinstance(value, str):
        text = _text(value)
        return [text] if text else []
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        return []
    items: list[str] = []
    for item in value:
        text = _text(item)
        if text:
            items.append(text)
    return _dedupe(items)


def _first_text(value: Any) -> str | None:
    for item in _safe_text_list(value):
        return item
    return None


def _regime_label(value: Any) -> str:
    text = _text(value)
    if not text:
        return "Low-confidence observation"
    return _REGIME_LABELS.get(text, f"{_humanize_code(text)} observation")


def _confidence_label(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    return _CONFIDENCE_LABELS.get(text.lower(), _humanize_code(text))


def _safe_public_text(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    for raw, replacement in {
        "riskOn": "Risk-on observation",
        "riskOff": "Risk-off observation",
        "lowConfidence": "Low-confidence observation",
        "research_radar": "Research Radar",
    }.items():
        text = text.replace(raw, replacement)
    return text


def _safe_public_list(value: Any) -> list[str]:
    return _dedupe([text for item in _safe_text_list(value) if (text := _safe_public_text(item))])


def _safe_reason_phrase(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    return _SAFE_REASON_LABELS.get(text, _humanize_code(text))


def _safe_phrase_list(values: Sequence[str]) -> list[str]:
    return _dedupe([text for value in values if (text := _safe_reason_phrase(value))])


def _safe_degraded_inputs(values: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in values:
        section = _text(item.get("section"))
        status = _text(item.get("status"))
        reason = _safe_reason_phrase(item.get("reason"))
        if not section or not status or not reason:
            continue
        entry = {"section": section, "status": status, "reason": reason}
        if entry not in result:
            result.append(entry)
    return result


def _humanize_code(value: str) -> str:
    text = value.replace("_", " ").replace(":", " ").replace("-", " ")
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = " ".join(text.split())
    return text[:1].upper() + text[1:] if text else ""


def _missing_evidence_codes(value: Any) -> list[str]:
    if isinstance(value, str):
        text = _text(value)
        return [text] if text else []
    items: list[str] = []
    for item in value or []:
        if isinstance(item, Mapping):
            code = _text(item.get("kind")) or _text(item.get("code"))
            if code:
                items.append(code)
        else:
            text = _text(item)
            if text:
                items.append(text)
    return _dedupe(items)


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _dedupe_links(values: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str, str]] = set()
    result: list[dict[str, str]] = []
    for item in values:
        label = _text(item.get("label"))
        route = _text(item.get("route"))
        section = _text(item.get("section"))
        reason = _text(item.get("reason"))
        if not label or not route or not section:
            continue
        key = (label, route, section, reason)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "label": label,
                "route": route,
                "section": section,
                "reason": reason,
            }
        )
    return result


def _dedupe_surface_summary(values: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in values:
        surface = _text(item.get("surface"))
        reason = _safe_reason_phrase(item.get("reason"))
        status = _text(item.get("status")) or "unavailable"
        if not surface or not reason:
            continue
        key = (surface, reason)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "surface": surface,
                "status": status if status in {"available", "degraded", "unavailable"} else "unavailable",
                "reason": reason,
                "drilldownTargets": _dedupe_links(item.get("drilldownTargets") or []),
            }
        )
    return result
