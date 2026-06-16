# -*- coding: utf-8 -*-
"""API tests for the Market Decision Cockpit endpoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import get_optional_current_user
from api.v1.endpoints import market


def _payload() -> dict:
    return {
        "schemaVersion": "market_decision_cockpit.v1",
        "generatedAt": "2026-06-15T00:00:00+00:00",
        "marketRegimeDecision": {
            "regime": "riskOn",
            "confidence": "medium",
            "driverScores": {},
            "explanation": {"whyThisRegime": [], "whatConfirmsIt": [], "whatInvalidatesIt": []},
            "invalidationConditions": [],
            "researchPriorities": {"watchToday": [], "needsMoreEvidence": [], "investigateNext": []},
        },
        "marketRegimeSummary": {
            "regime": "Risk-on observation",
            "confidence": "moderate",
            "summary": "Current regime observation is Risk-on observation.",
            "supportingObservations": [],
            "invalidationObservations": [],
        },
        "whatChanged": [
            "Current regime observation is Risk-on observation with moderate confidence.",
            "Research queue quality is thin.",
            "Options structure evidence is unavailable for this cockpit snapshot.",
        ],
        "topResearchPriorities": [],
        "scannerHighlights": [],
        "watchlistHighlights": [],
        "portfolioHighlights": [],
        "scenarioRisks": [
            {
                "label": "Regime confidence scenario",
                "source": "Scenario Lab",
                "observations": ["Options structure evidence is unavailable for this cockpit snapshot."],
                "evidenceGaps": ["Options structure evidence is unavailable."],
            }
        ],
        "evidenceGaps": ["Options structure evidence is unavailable."],
        "degradedInputs": [
            {
                "section": "scenarioRisks",
                "status": "unavailable",
                "reason": "Options structure evidence is unavailable.",
            }
        ],
        "drilldownTargets": [
            {
                "label": "Research Radar",
                "route": "/research/radar",
                "section": "topResearchPriorities",
                "reason": "Review the research queue.",
            }
        ],
        "observationOnly": True,
        "decisionGrade": False,
        "researchQueuePreview": {
            "topCandidates": [],
            "queueQuality": "thin",
            "evidenceGaps": ["research_candidates_unavailable"],
            "previewOnly": True,
            "degradedState": {"status": "empty", "reasonCodes": ["research_candidates_unavailable"]},
            "consumerIssues": [
                {
                    "label": "Research candidates unavailable",
                    "message": "Research candidates are not available for this payload.",
                    "severity": "warning",
                    "category": "research",
                }
            ],
        },
        "optionsStructureStatus": {
            "gammaEvidenceStatus": "unavailable",
            "observationOnly": True,
            "decisionGrade": False,
            "missingEvidence": [{"code": "missing_contracts", "field": "contracts", "contractSymbol": None}],
            "blockedReasonCodes": ["option_chain_unavailable", "missing_contracts"],
            "consumerIssues": [
                {
                    "label": "Options chain unavailable",
                    "message": "Options chain evidence is not available for this read.",
                    "severity": "warning",
                    "category": "options",
                }
            ],
        },
        "cockpitSummary": {
            "whatChanged": ["Regime selected as riskOn."],
            "whyItMatters": ["Research triage depends on confirmed evidence clusters."],
            "whatToWatch": ["Confirm breadth participation."],
            "confidenceLimits": ["Dealer gamma evidence is unavailable."],
        },
        "consumerIssues": [
            {
                "label": "Options chain unavailable",
                "message": "Options chain evidence is not available for this read.",
                "severity": "warning",
                "category": "options",
            }
        ],
        "noAdviceDisclosure": "Decision support for research context only; not investment advice or trading instruction.",
        "dataQuality": {
            "status": "degraded",
            "reasonCodes": ["option_chain_unavailable"],
            "consumerIssues": [
                {
                    "label": "Options chain unavailable",
                    "message": "Options chain evidence is not available for this read.",
                    "severity": "warning",
                    "category": "options",
                }
            ],
        },
    }


class _FakeCockpitService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get_decision_cockpit(self, *, actor=None) -> dict:
        self.calls.append({"actor": actor})
        return _payload()


def test_market_decision_cockpit_route_is_exposed() -> None:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    routes = {
        (method, route.path)
        for route in app.routes
        if hasattr(route, "methods")
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }

    assert ("GET", "/api/v1/market/decision-cockpit") in routes


def test_market_decision_cockpit_endpoint_returns_service_payload(monkeypatch) -> None:
    fake_service = _FakeCockpitService()
    monkeypatch.setattr(market, "MarketDecisionCockpitService", lambda: fake_service)
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    app.dependency_overrides[get_optional_current_user] = lambda: None

    response = TestClient(app).get("/api/v1/market/decision-cockpit")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schemaVersion"] == "market_decision_cockpit.v1"
    assert payload["marketRegimeDecision"]["regime"] == "riskOn"
    assert payload["researchQueuePreview"]["previewOnly"] is True
    assert payload["optionsStructureStatus"]["observationOnly"] is True
    assert payload["optionsStructureStatus"]["decisionGrade"] is False
    assert payload["marketRegimeSummary"]["regime"] == "Risk-on observation"
    assert payload["whatChanged"][0].startswith("Current regime observation")
    assert payload["topResearchPriorities"] == []
    assert payload["scannerHighlights"] == []
    assert payload["watchlistHighlights"] == []
    assert payload["portfolioHighlights"] == []
    assert payload["drilldownTargets"][0]["route"] == "/research/radar"
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert payload["consumerIssues"][0]["label"] == "Options chain unavailable"
    assert fake_service.calls == [
        {"actor": {"actor_type": "anonymous", "role": "anonymous", "display_name": "Anonymous"}}
    ]
