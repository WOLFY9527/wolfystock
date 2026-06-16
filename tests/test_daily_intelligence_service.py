# -*- coding: utf-8 -*-
"""Tests for the daily intelligence briefing aggregation service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.services.daily_intelligence_service import DailyIntelligenceService


class _FakeMarketOverviewService:
    def get_market_regime_decision(self, *, actor=None) -> dict[str, Any]:
        self.regime_actor = actor
        return {
            "regime": "riskOn",
            "confidence": "medium",
            "explanation": {
                "whyThisRegime": ["Breadth and liquidity observations are supportive."],
                "whatConfirmsIt": ["Breadth remains constructive."],
                "whatInvalidatesIt": ["Evidence weakens if breadth narrows materially."],
            },
        }

    def get_market_briefing(self, *, actor=None) -> dict[str, Any]:
        self.briefing_actor = actor
        return {
            "items": [
                {"title": "Regime observation updated", "message": "Research queue remains active."},
                {"title": "Liquidity observation updated", "message": "Follow-through needs verification."},
            ]
        }


class _FakeResearchRadarService:
    def build_from_latest_scanner_run(self, **kwargs: object) -> dict[str, object]:
        self.calls = [kwargs]
        return {
            "researchQueue": [
                {
                    "symbol": "ALFA",
                    "ticker": "ALFA",
                    "priority": "high",
                    "whyOnRadar": ["Relative strength and volume structure changed."],
                    "whatToVerify": ["Verify the latest structure evidence."],
                    "evidenceGaps": ["themeBreadth"],
                    "riskFlags": ["evidence_partial"],
                }
            ],
            "evidenceGaps": ["scannerCandidates"],
        }


class _FakeWatchlistOverlayService:
    def build_overlay(self, *, owner_id: str) -> dict[str, Any]:
        self.owner_id = owner_id
        return {
            "items": [
                {
                    "ticker": "NVDA",
                    "structureState": "structure_changed",
                    "researchPriority": "medium",
                    "whyWatching": "Structure changed and needs observation.",
                    "whatToVerify": ["Verify local OHLCV coverage."],
                    "evidenceGaps": ["local_ohlcv_evidence"],
                    "riskFlags": ["cached_or_stale_evidence"],
                }
            ],
            "missingEvidence": ["watchlist_research_context"],
        }


class _FakePortfolioStructureReviewService:
    def build_review(self, *, owner_id: str, max_items: int | None = None, **kwargs: object) -> dict[str, Any]:
        self.calls = [{"owner_id": owner_id, "max_items": max_items, **kwargs}]
        return {
            "holdingsStructure": [
                {
                    "ticker": "AAPL",
                    "structureState": "mixed",
                    "confidence": "medium",
                    "researchNotes": {
                        "watchNext": ["Verify whether the structure remains supported by cached holdings."],
                        "riskFlags": ["concentrated_exposure"],
                    },
                    "riskFlags": ["concentrated_exposure"],
                    "missingEvidence": ["cached_portfolio_holdings"],
                }
            ],
            "missingEvidence": ["theme_or_sector_exposure"],
        }


def test_build_briefing_projects_required_contract_and_degrades_scenario_risks() -> None:
    service = DailyIntelligenceService(
        market_overview_service=_FakeMarketOverviewService(),
        research_radar_service=_FakeResearchRadarService(),
        watchlist_overlay_service=_FakeWatchlistOverlayService(),
        portfolio_structure_review_service=_FakePortfolioStructureReviewService(),
        now=lambda: datetime(2026, 6, 15, 9, 30, tzinfo=timezone.utc),
    )

    payload = service.build_briefing(actor={"actor_type": "user"}, owner_id="user-1", market="us", profile="us_preopen_v1")

    assert payload["schemaVersion"] == "daily_intelligence_briefing_v1"
    assert payload["generatedAt"] == "2026-06-15T09:30:00+00:00"
    assert payload["briefingDate"] == "2026-06-15"
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert payload["marketRegimeSummary"]["regime"] == "riskOn"
    assert payload["whatChanged"]
    assert payload["topResearchPriorities"][0]["ticker"] == "ALFA"
    assert payload["topResearchPriorities"][0]["evidenceLinks"] == [
        {
            "label": "Research Radar",
            "route": "/research/radar",
            "section": "topResearchPriorities",
            "reason": "research_queue_origin",
        },
        {
            "label": "Stock Structure",
            "route": "/stocks/ALFA/structure-decision",
            "section": "topResearchPriorities",
            "reason": "symbol_structure_detail",
        },
    ]
    assert payload["scannerHighlights"][0]["ticker"] == "ALFA"
    assert payload["scannerHighlights"][0]["evidenceLinks"] == [
        {
            "label": "Research Radar",
            "route": "/research/radar",
            "section": "scannerHighlights",
            "reason": "research_queue_origin",
        },
        {
            "label": "Stock Structure",
            "route": "/stocks/ALFA/structure-decision",
            "section": "scannerHighlights",
            "reason": "symbol_structure_detail",
        },
    ]
    assert payload["watchlistHighlights"][0]["ticker"] == "NVDA"
    assert payload["watchlistHighlights"][0]["evidenceLinks"] == [
        {
            "label": "Watchlist",
            "route": "/watchlist",
            "section": "watchlistHighlights",
            "reason": "watchlist_research_context",
        },
        {
            "label": "Stock Structure",
            "route": "/stocks/NVDA/structure-decision",
            "section": "watchlistHighlights",
            "reason": "symbol_structure_detail",
        },
    ]
    assert payload["portfolioStructureHighlights"][0]["ticker"] == "AAPL"
    assert payload["portfolioStructureHighlights"][0]["evidenceLinks"] == [
        {
            "label": "Portfolio",
            "route": "/portfolio",
            "section": "portfolioStructureHighlights",
            "reason": "portfolio_structure_context",
        },
        {
            "label": "Stock Structure",
            "route": "/stocks/AAPL/structure-decision",
            "section": "portfolioStructureHighlights",
            "reason": "symbol_structure_detail",
        },
    ]
    assert payload["scenarioRisks"][0]["source"] == "degraded_state"
    assert "scenario_risk_read_model_unavailable" in payload["evidenceGaps"]
    assert payload["sectionLinks"] == [
        {
            "label": "Research Radar",
            "route": "/research/radar",
            "section": "topResearchPriorities",
            "reason": "research_queue_origin",
        },
        {
            "label": "Scanner",
            "route": "/scanner",
            "section": "scannerHighlights",
            "reason": "scanner_candidates_origin",
        },
        {
            "label": "Research Radar",
            "route": "/research/radar",
            "section": "scannerHighlights",
            "reason": "research_queue_origin",
        },
        {
            "label": "Watchlist",
            "route": "/watchlist",
            "section": "watchlistHighlights",
            "reason": "watchlist_research_context",
        },
        {
            "label": "Portfolio",
            "route": "/portfolio",
            "section": "portfolioStructureHighlights",
            "reason": "portfolio_structure_context",
        },
    ]
    assert any(item["section"] == "scenarioRisks" for item in payload["degradedInputs"])
    assert any(item["section"] == "watchlistHighlights" for item in payload["degradedInputs"]) is False
    assert not any(link["section"] == "scenarioRisks" for link in payload["sectionLinks"])


def test_build_briefing_does_not_invent_evidence_links_when_owner_context_is_missing() -> None:
    service = DailyIntelligenceService(
        market_overview_service=_FakeMarketOverviewService(),
        research_radar_service=_FakeResearchRadarService(),
        watchlist_overlay_service=_FakeWatchlistOverlayService(),
        portfolio_structure_review_service=_FakePortfolioStructureReviewService(),
        now=lambda: datetime(2026, 6, 15, 9, 30, tzinfo=timezone.utc),
    )

    payload = service.build_briefing(actor={"actor_type": "anonymous"}, owner_id=None, market="us", profile="us_preopen_v1")

    assert payload["topResearchPriorities"] == []
    assert payload["scannerHighlights"] == []
    assert payload["watchlistHighlights"] == []
    assert payload["portfolioStructureHighlights"] == []
    assert payload["sectionLinks"] == []
