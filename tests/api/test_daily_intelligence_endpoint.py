# -*- coding: utf-8 -*-
"""API tests for the daily intelligence briefing endpoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import get_optional_current_user
from api.v1.endpoints import market


class _FakeDailyIntelligenceService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def build_briefing(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return {
            "schemaVersion": "daily_intelligence_briefing_v1",
            "generatedAt": "2026-06-15T09:30:00+00:00",
            "briefingDate": "2026-06-15",
            "sessionLabel": "pre-market",
            "marketRegimeSummary": {
                "regime": "Risk-on observation",
                "confidence": "moderate",
                "summary": "Current regime observation is Risk-on observation.",
                "supportingObservations": ["Breadth remains constructive."],
                "invalidationObservations": ["Evidence weakens if breadth narrows materially."],
            },
            "whatChanged": ["Regime observation updated."],
            "topResearchPriorities": [],
            "sectionLinks": [
                {
                    "label": "Research Radar",
                    "route": "/research/radar",
                    "section": "topResearchPriorities",
                    "reason": "Research radar queue context.",
                }
            ],
            "scannerHighlights": [],
            "watchlistHighlights": [],
            "portfolioHighlights": [],
            "portfolioStructureHighlights": [],
            "scenarioRisks": [],
            "evidenceGaps": ["Scenario risk read model is unavailable for this briefing."],
            "degradedInputs": [
                {
                    "section": "scenarioRisks",
                    "status": "unavailable",
                    "reason": "Scenario risk read model is unavailable for this briefing.",
                }
            ],
            "drilldownTargets": [
                {
                    "label": "Research Radar",
                    "route": "/research/radar",
                    "section": "topResearchPriorities",
                    "reason": "Research radar queue context.",
                }
            ],
            "researchWorkflow": [
                {
                    "surface": "Research Radar",
                    "status": "available",
                    "summary": "Research queue evidence is available for observation.",
                    "drilldownTargets": [
                        {
                            "label": "Research Radar",
                            "route": "/research/radar",
                            "section": "topResearchPriorities",
                            "reason": "Research radar queue context.",
                        }
                    ],
                }
            ],
            "crossSurfaceEvidence": [
                {
                    "surfaces": ["Market Overview", "Research Radar"],
                    "observation": "Market context can be reviewed with the research queue.",
                    "drilldownTargets": [
                        {
                            "label": "Research Radar",
                            "route": "/research/radar",
                            "section": "topResearchPriorities",
                            "reason": "Research radar queue context.",
                        }
                    ],
                }
            ],
            "topResearchQuestions": [
                {
                    "question": "Which research queue items need structure verification first?",
                    "surface": "Research Radar",
                    "drilldownTargets": [
                        {
                            "label": "Research Radar",
                            "route": "/research/radar",
                            "section": "topResearchPriorities",
                            "reason": "Research radar queue context.",
                        }
                    ],
                }
            ],
            "priorityDrilldowns": [
                {
                    "label": "Research Radar",
                    "route": "/research/radar",
                    "section": "topResearchPriorities",
                    "reason": "Research radar queue context.",
                }
            ],
            "evidenceConflicts": [],
            "degradedSurfaceSummary": [
                {
                    "surface": "Scenario Lab",
                    "status": "unavailable",
                    "reason": "Scenario risk read model is unavailable for this briefing.",
                    "drilldownTargets": [],
                }
            ],
            "nextObservationSteps": ["Review research queue evidence with structure context."],
            "onboardingGuidance": {
                "title": "Start a research loop",
                "summary": "Use Market Overview, Watchlist, Scanner, and Research Radar to begin observation.",
                "conditionsDetected": ["Research Radar has no queue items yet."],
            },
            "emptyStateActions": [
                {
                    "label": "Open Market Overview",
                    "route": "/market-overview",
                    "description": "Start with broad market context.",
                }
            ],
            "starterResearchWorkflow": ["Open Market Overview to set broad context."],
            "firstRunChecklist": ["Market Overview checked for context."],
            "suggestedResearchEntrypoints": [
                {
                    "surface": "Market Overview",
                    "route": "/market-overview",
                    "description": "Review broad context before adding symbols.",
                }
            ],
            "consumerIssues": [
                {
                    "label": "Evidence needs review",
                    "message": "Some quality checks are not fully cleared yet.",
                    "severity": "info",
                    "category": "evidence",
                }
            ],
            "noAdviceDisclosure": "Observation-only research briefing; not personalized financial advice.",
            "observationOnly": True,
            "decisionGrade": False,
        }


def test_daily_intelligence_route_is_exposed() -> None:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    routes = {
        (method, route.path)
        for route in app.routes
        if hasattr(route, "methods")
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }
    assert ("GET", "/api/v1/market/daily-intelligence") in routes


def test_daily_intelligence_endpoint_uses_optional_user_context(monkeypatch) -> None:
    fake_service = _FakeDailyIntelligenceService()
    monkeypatch.setattr(market, "DailyIntelligenceService", lambda: fake_service)

    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    app.dependency_overrides[get_optional_current_user] = lambda: None

    response = TestClient(app).get("/api/v1/market/daily-intelligence")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schemaVersion"] == "daily_intelligence_briefing_v1"
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert payload["consumerIssues"][0]["label"] == "Evidence needs review"
    assert payload["sectionLinks"] == [
        {
            "label": "Research Radar",
            "route": "/research/radar",
            "section": "topResearchPriorities",
            "reason": "Research radar queue context.",
        }
    ]
    assert payload["portfolioHighlights"] == []
    assert payload["drilldownTargets"][0]["route"] == "/research/radar"
    assert payload["researchWorkflow"][0]["surface"] == "Research Radar"
    assert payload["crossSurfaceEvidence"][0]["surfaces"] == ["Market Overview", "Research Radar"]
    assert payload["topResearchQuestions"][0]["question"].startswith("Which research queue")
    assert payload["priorityDrilldowns"][0]["route"] == "/research/radar"
    assert payload["evidenceConflicts"] == []
    assert payload["degradedSurfaceSummary"][0]["surface"] == "Scenario Lab"
    assert payload["nextObservationSteps"] == ["Review research queue evidence with structure context."]
    assert payload["onboardingGuidance"]["title"] == "Start a research loop"
    assert payload["emptyStateActions"][0]["route"] == "/market-overview"
    assert payload["starterResearchWorkflow"] == ["Open Market Overview to set broad context."]
    assert payload["firstRunChecklist"] == ["Market Overview checked for context."]
    assert payload["suggestedResearchEntrypoints"][0]["surface"] == "Market Overview"
    assert payload["noAdviceDisclosure"] == "Observation-only research briefing; not personalized financial advice."
    assert fake_service.calls == [
        {
            "actor": {"actor_type": "anonymous", "role": "anonymous", "display_name": "Anonymous"},
            "owner_id": None,
            "market": None,
            "profile": None,
        }
    ]
