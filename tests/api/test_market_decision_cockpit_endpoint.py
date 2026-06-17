# -*- coding: utf-8 -*-
"""API tests for the Market Decision Cockpit endpoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import get_optional_current_user
from api.v1.endpoints import market

FORBIDDEN_CONSUMER_REASON_TOKENS = (
    "_blocked",
    "_gate",
    "freshness_blocked",
    "proxy_or_sample_evidence_blocked",
    "source_authority_or_score_gate_blocked",
    "source_authority_blocked",
    "score_gate",
)


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
        "researchWorkflow": [
            {
                "surface": "Research Radar",
                "status": "unavailable",
                "summary": "Research candidates are unavailable.",
                "drilldownTargets": [
                    {
                        "label": "Research Radar",
                        "route": "/research/radar",
                        "section": "topResearchPriorities",
                        "reason": "Review the research queue.",
                    }
                ],
            }
        ],
        "crossSurfaceEvidence": [
            {
                "surfaces": ["Market Overview", "Scenario Lab"],
                "observation": "Scenario context can be reviewed against the current regime observation.",
                "drilldownTargets": [
                    {
                        "label": "Scenario Lab",
                        "route": "/scenario-lab",
                        "section": "scenarioRisks",
                        "reason": "Review bounded scenario changes.",
                    }
                ],
            }
        ],
        "topResearchQuestions": [
            {
                "question": "Which scenario assumptions would change the current regime observation?",
                "surface": "Scenario Lab",
                "drilldownTargets": [
                    {
                        "label": "Scenario Lab",
                        "route": "/scenario-lab",
                        "section": "scenarioRisks",
                        "reason": "Review bounded scenario changes.",
                    }
                ],
            }
        ],
        "priorityDrilldowns": [
            {
                "label": "Research Radar",
                "route": "/research/radar",
                "section": "topResearchPriorities",
                "reason": "Review the research queue.",
            }
        ],
        "evidenceConflicts": [],
        "degradedSurfaceSummary": [
            {
                "surface": "Research Radar",
                "status": "unavailable",
                "reason": "Research candidates are unavailable.",
                "drilldownTargets": [
                    {
                        "label": "Research Radar",
                        "route": "/research/radar",
                        "section": "topResearchPriorities",
                        "reason": "Review the research queue.",
                    }
                ],
            }
        ],
        "nextObservationSteps": ["Review the research queue when candidate evidence is available."],
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
        "noAdviceDisclosure": "Observation-only market research; not personalized financial advice.",
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


class _RawReasonCockpitService:
    def get_decision_cockpit(self, *, actor=None) -> dict:
        payload = _payload()
        payload["marketRegimeDecision"]["missingEvidence"] = [
            "freshness_blocked:fallback",
            "source_authority_or_score_gate_blocked",
        ]
        payload["marketRegimeDecision"]["driverScores"] = {
            "breadthParticipation": {
                "score": 0,
                "evidenceState": "blocked",
                "reasons": ["proxy_or_sample_evidence_blocked"],
            }
        }
        payload["dataQuality"]["reasonCodes"] = [
            "freshness_blocked:fallback",
            "score_gate",
        ]
        return payload


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
    assert payload["researchWorkflow"][0]["surface"] == "Research Radar"
    assert payload["crossSurfaceEvidence"][0]["surfaces"] == ["Market Overview", "Scenario Lab"]
    assert payload["topResearchQuestions"][0]["surface"] == "Scenario Lab"
    assert payload["priorityDrilldowns"][0]["route"] == "/research/radar"
    assert payload["evidenceConflicts"] == []
    assert payload["degradedSurfaceSummary"][0]["surface"] == "Research Radar"
    assert payload["nextObservationSteps"] == ["Review the research queue when candidate evidence is available."]
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert payload["consumerIssues"][0]["label"] == "Options chain unavailable"
    assert fake_service.calls == [
        {"actor": {"actor_type": "anonymous", "role": "anonymous", "display_name": "Anonymous"}}
    ]


def test_market_decision_cockpit_endpoint_redacts_raw_reason_codes(monkeypatch) -> None:
    monkeypatch.setattr(market, "MarketDecisionCockpitService", lambda: _RawReasonCockpitService())
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    app.dependency_overrides[get_optional_current_user] = lambda: None

    response = TestClient(app).get("/api/v1/market/decision-cockpit")

    assert response.status_code == 200
    payload = response.json()
    serialized = response.text.lower()
    for raw_token in FORBIDDEN_CONSUMER_REASON_TOKENS:
        assert raw_token not in serialized
    assert payload["marketRegimeDecision"]["missingEvidence"] == [
        "数据新鲜度尚未确认，当前仅显示降级观察结果",
        "当前数据源权威性或评分级别不足，暂不能形成可靠研究结论",
    ]
    assert payload["marketRegimeDecision"]["driverScores"]["breadthParticipation"]["reasons"] == [
        "当前仅有样本或代理证据，暂不足以代表完整市场结构"
    ]
