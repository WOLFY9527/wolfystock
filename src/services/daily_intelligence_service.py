# -*- coding: utf-8 -*-
"""Read-only daily intelligence briefing aggregation service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote

from src.repositories.scanner_repo import ScannerRepository
from src.services.market_overview_service import MarketOverviewService
from src.services.portfolio_structure_review_service import PortfolioStructureReviewService
from src.services.research_radar_service import ResearchRadarService
from src.services.watchlist_research_overlay_service import WatchlistResearchOverlayService


DAILY_INTELLIGENCE_SERVICE_SCHEMA_VERSION = "daily_intelligence_briefing_v1"
_SCENARIO_RISK_UNAVAILABLE_REASON = "scenario_risk_read_model_unavailable"


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

        return {
            "schemaVersion": DAILY_INTELLIGENCE_SERVICE_SCHEMA_VERSION,
            "generatedAt": generated_at.isoformat(),
            "briefingDate": generated_at.date().isoformat(),
            "sessionLabel": self._session_label(generated_at),
            "marketRegimeSummary": market_regime_summary,
            "whatChanged": what_changed,
            "sectionLinks": self._section_links(
                radar_payload=radar_payload,
                watchlist_payload=watchlist_payload,
                portfolio_payload=portfolio_payload,
            ),
            "topResearchPriorities": top_research_priorities,
            "scannerHighlights": scanner_highlights,
            "watchlistHighlights": watchlist_highlights,
            "portfolioStructureHighlights": portfolio_highlights,
            "scenarioRisks": [
                {
                    "label": "Scenario risk section unavailable",
                    "source": "degraded_state",
                    "observations": [
                        "A stored owner-scoped scenario read model is not available in this aggregation path."
                    ],
                    "evidenceGaps": [_SCENARIO_RISK_UNAVAILABLE_REASON],
                }
            ],
            "evidenceGaps": _dedupe(evidence_gaps),
            "degradedInputs": degraded_inputs,
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
        summary = _first_text(explanation.get("whyThisRegime")) or f"Current regime observation is {regime_name}."
        return {
            "regime": regime_name,
            "confidence": confidence,
            "summary": summary,
            "supportingObservations": _safe_text_list(explanation.get("whatConfirmsIt")),
            "invalidationObservations": _safe_text_list(explanation.get("whatInvalidatesIt")),
        }

    def _what_changed(self, briefing: Mapping[str, Any]) -> list[str]:
        items = list(briefing.get("items") or [])
        messages: list[str] = []
        for item in items[:4]:
            payload = _mapping(item)
            title = _text(payload.get("title"))
            message = _text(payload.get("message"))
            if title and message:
                messages.append(f"{title}: {message}")
            elif title:
                messages.append(title)
            elif message:
                messages.append(message)
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
                    "source": "research_radar",
                    "priority": _text(payload.get("priority")) or None,
                    "ticker": ticker,
                    "observations": _safe_text_list(payload.get("whyOnRadar")),
                    "whatToVerify": _safe_text_list(payload.get("whatToVerify")),
                    "evidenceGaps": _safe_text_list(payload.get("evidenceGaps")),
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
                    "observations": _safe_text_list(payload.get("whyOnRadar")),
                    "whatToVerify": _safe_text_list(payload.get("whatToVerify")),
                    "evidenceGaps": _safe_text_list(payload.get("evidenceGaps")),
                    "riskFlags": _safe_text_list(payload.get("riskFlags")),
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
                    "structureState": _text(payload.get("structureState")) or "unavailable",
                    "researchPriority": _text(payload.get("researchPriority")) or None,
                    "whyWatching": _text(payload.get("whyWatching")) or None,
                    "whatToVerify": _safe_text_list(payload.get("whatToVerify")),
                    "evidenceGaps": _safe_text_list(payload.get("evidenceGaps")),
                    "riskFlags": _safe_text_list(payload.get("riskFlags")),
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
                    "structureState": _text(payload.get("structureState")) or "unavailable",
                    "confidence": _text(payload.get("confidence")) or "low",
                    "watchNext": _safe_text_list(notes.get("watchNext")),
                    "riskFlags": _safe_text_list(payload.get("riskFlags")) or _safe_text_list(notes.get("riskFlags")),
                    "missingEvidence": _missing_evidence_codes(payload.get("missingEvidence")),
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
            "reason": reason,
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
            "reason": "symbol_structure_detail",
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
