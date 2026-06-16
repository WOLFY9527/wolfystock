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
                "regime": "riskOn",
                "confidence": "medium",
                "summary": "Current regime observation is riskOn.",
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
                    "reason": "research_queue_origin",
                }
            ],
            "scannerHighlights": [],
            "watchlistHighlights": [],
            "portfolioStructureHighlights": [],
            "scenarioRisks": [],
            "evidenceGaps": ["scenario_risk_read_model_unavailable"],
            "degradedInputs": [{"section": "scenarioRisks", "status": "unavailable", "reason": "scenario_risk_read_model_unavailable"}],
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
    assert payload["sectionLinks"] == [
        {
            "label": "Research Radar",
            "route": "/research/radar",
            "section": "topResearchPriorities",
            "reason": "research_queue_origin",
        }
    ]
    assert fake_service.calls == [
        {
            "actor": {"actor_type": "anonymous", "role": "anonymous", "display_name": "Anonymous"},
            "owner_id": None,
            "market": None,
            "profile": None,
        }
    ]
