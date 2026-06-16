# -*- coding: utf-8 -*-
"""Tests for the daily intelligence briefing aggregation service."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from src.services.daily_intelligence_service import DailyIntelligenceService


FORBIDDEN_RAW_TOKENS = (
    "riskOn",
    "lowConfidence",
    "research_queue_origin",
    "scanner_candidates_origin",
    "symbol_structure_detail",
    "watchlist_research_context",
    "portfolio_structure_context",
    "scenario_risk_read_model_unavailable",
    "degraded_state",
    "scannerCandidates",
    "themeBreadth",
    "evidence_partial",
    "local_ohlcv_evidence",
    "cached_or_stale_evidence",
    "cached_portfolio_holdings",
    "theme_or_sector_exposure",
    "concentrated_exposure",
    "owner_context_missing",
)
FORBIDDEN_ADVICE_WORDS = ("buy", "sell", "hold", "recommendation", "target", "stop")
ROUTE_RE = re.compile(r"^/[A-Za-z0-9][A-Za-z0-9/_-]*(?:\?[A-Za-z0-9=&._%-]+)?$")


def _serialized_narrative_values(payload: object) -> str:
    values: list[str] = []
    skip_keys = {"route", "section", "ticker", "symbol", "schemaVersion", "generatedAt", "briefingDate"}

    def visit(value: object) -> None:
        if isinstance(value, str):
            values.append(value)
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if key in skip_keys:
                    continue
                visit(item)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    visit(payload)
    return json.dumps(values, ensure_ascii=False, sort_keys=True)


def _assert_consumer_safe_narrative(payload: dict[str, Any]) -> None:
    narrative = {
        key: payload[key]
        for key in (
            "marketRegimeSummary",
            "whatChanged",
            "topResearchPriorities",
            "scannerHighlights",
            "watchlistHighlights",
            "portfolioHighlights",
            "scenarioRisks",
            "evidenceGaps",
            "degradedInputs",
            "drilldownTargets",
            "noAdviceDisclosure",
        )
    }
    serialized = _serialized_narrative_values(narrative)
    serialized_lower = serialized.lower()
    for token in FORBIDDEN_RAW_TOKENS:
        assert token not in serialized
    assert re.search(r"\b[a-z]+(?:_[a-z0-9]+)+\b", serialized_lower) is None
    assert re.search(r"\b[a-z][a-z0-9]+:[a-z0-9_]+\b", serialized_lower) is None
    for word in FORBIDDEN_ADVICE_WORDS:
        assert re.search(rf"\b{re.escape(word)}\b", serialized_lower) is None
    assert "position sizing" not in serialized_lower


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
    assert payload["marketRegimeSummary"]["regime"] == "Risk-on observation"
    assert payload["whatChanged"]
    assert payload["noAdviceDisclosure"] == "Observation-only research briefing; not personalized financial advice."
    assert payload["topResearchPriorities"][0]["ticker"] == "ALFA"
    assert payload["topResearchPriorities"][0]["evidenceLinks"] == [
        {
            "label": "Research Radar",
            "route": "/research/radar",
            "section": "topResearchPriorities",
            "reason": "Research radar queue context.",
        },
        {
            "label": "Stock Structure",
            "route": "/stocks/ALFA/structure-decision",
            "section": "topResearchPriorities",
            "reason": "Symbol structure detail.",
        },
    ]
    assert payload["scannerHighlights"][0]["ticker"] == "ALFA"
    assert payload["scannerHighlights"][0]["evidenceLinks"] == [
        {
            "label": "Research Radar",
            "route": "/research/radar",
            "section": "scannerHighlights",
            "reason": "Research radar queue context.",
        },
        {
            "label": "Stock Structure",
            "route": "/stocks/ALFA/structure-decision",
            "section": "scannerHighlights",
            "reason": "Symbol structure detail.",
        },
    ]
    assert payload["watchlistHighlights"][0]["ticker"] == "NVDA"
    assert payload["watchlistHighlights"][0]["evidenceLinks"] == [
        {
            "label": "Watchlist",
            "route": "/watchlist",
            "section": "watchlistHighlights",
            "reason": "Watchlist research context is unavailable.",
        },
        {
            "label": "Stock Structure",
            "route": "/stocks/NVDA/structure-decision",
            "section": "watchlistHighlights",
            "reason": "Symbol structure detail.",
        },
    ]
    assert payload["portfolioStructureHighlights"][0]["ticker"] == "AAPL"
    assert payload["portfolioHighlights"] == payload["portfolioStructureHighlights"]
    assert payload["portfolioStructureHighlights"][0]["evidenceLinks"] == [
        {
            "label": "Portfolio",
            "route": "/portfolio",
            "section": "portfolioStructureHighlights",
            "reason": "Portfolio structure context.",
        },
        {
            "label": "Stock Structure",
            "route": "/stocks/AAPL/structure-decision",
            "section": "portfolioStructureHighlights",
            "reason": "Symbol structure detail.",
        },
    ]
    assert payload["scenarioRisks"][0]["source"] == "Daily Intelligence"
    assert "Scenario risk read model is unavailable for this briefing." in payload["evidenceGaps"]
    assert payload["sectionLinks"] == [
        {
            "label": "Research Radar",
            "route": "/research/radar",
            "section": "topResearchPriorities",
            "reason": "Research radar queue context.",
        },
        {
            "label": "Scanner",
            "route": "/scanner",
            "section": "scannerHighlights",
            "reason": "Scanner candidate context.",
        },
        {
            "label": "Research Radar",
            "route": "/research/radar",
            "section": "scannerHighlights",
            "reason": "Research radar queue context.",
        },
        {
            "label": "Watchlist",
            "route": "/watchlist",
            "section": "watchlistHighlights",
            "reason": "Watchlist research context is unavailable.",
        },
        {
            "label": "Portfolio",
            "route": "/portfolio",
            "section": "portfolioStructureHighlights",
            "reason": "Portfolio structure context.",
        },
    ]
    assert any(item["section"] == "scenarioRisks" for item in payload["degradedInputs"])
    assert any(item["section"] == "watchlistHighlights" for item in payload["degradedInputs"]) is False
    assert not any(link["section"] == "scenarioRisks" for link in payload["sectionLinks"])
    assert payload["drilldownTargets"]
    for target in payload["drilldownTargets"]:
        assert ROUTE_RE.fullmatch(target["route"])
        assert not target["route"].startswith("/api/")
    _assert_consumer_safe_narrative(payload)


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
    assert payload["portfolioHighlights"] == []
    assert payload["sectionLinks"] == []
    assert payload["drilldownTargets"] == []
    assert payload["noAdviceDisclosure"] == "Observation-only research briefing; not personalized financial advice."
    _assert_consumer_safe_narrative(payload)
