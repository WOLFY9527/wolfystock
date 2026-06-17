# -*- coding: utf-8 -*-
"""API tests for the Research Radar backend endpoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user, get_database_manager
from api.v1.router import router as api_v1_router


def _user() -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="alice",
        display_name="Alice",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="session-1",
    )


class _FakeResearchRadarService:
    calls: list[dict[str, object]] = []

    def __init__(self, *, scanner_repository: object | None = None) -> None:
        self.scanner_repository = scanner_repository

    def build_from_latest_scanner_run(self, **kwargs: object) -> dict[str, object]:
        self.__class__.calls.append(
            {
                **kwargs,
                "hasScannerRepository": self.scanner_repository is not None,
            }
        )
        return {
            "schemaVersion": "research_radar_api_v1",
            "generatedAt": "2026-06-15T09:30:00+00:00",
            "researchQueue": [
                {
                    "symbol": "ALFA",
                    "ticker": "ALFA",
                    "priority": "medium",
                    "researchBias": "Strength observation",
                    "researchBiasRaw": "strengthContinuation",
                    "researchBiasLabel": "Strength observation",
                    "researchBiasMessage": "Relative strength and structure are visible enough for research follow-up.",
                    "driverScores": {"relativeStrength": 70},
                    "whyOnRadar": ["Relative strength is above the research threshold."],
                    "whatToVerify": ["Verify relative strength persists versus the benchmark."],
                    "whyNotHigherPriority": ["Evidence quality is below the strong research threshold."],
                    "evidenceGaps": ["Theme breadth needs review"],
                    "evidenceGapsRaw": ["themeBreadth"],
                    "invalidationObservations": ["Relative strength fades below benchmark behavior."],
                    "duplicateEvidenceMerged": 1,
                    "riskFlags": [],
                    "riskFlagsRaw": [],
                    "riskFlagLabels": [],
                    "consumerEvidenceGaps": [
                        {
                            "label": "Theme breadth needs review",
                            "message": "Theme breadth needs more confirmation.",
                            "severity": "info",
                            "category": "evidence",
                        }
                    ],
                    "evidenceQuality": {
                        "status": "partial",
                        "score": 54,
                        "missingEvidence": ["Theme breadth needs review"],
                        "missingEvidenceRaw": ["themeBreadth"],
                    },
                    "consumerIssues": [
                        {
                            "label": "Evidence needs review",
                            "message": "Some quality checks are not fully cleared yet.",
                            "severity": "info",
                            "category": "evidence",
                        }
                    ],
                    "drilldownTargets": [
                        {
                            "label": "Structure detail",
                            "route": "/stocks/ALFA/structure-decision",
                            "reason": "Open the structure workspace for this ticker.",
                        }
                    ],
                    "noAdviceDisclosure": "Research-only queue; verify evidence gaps before further review.",
                    "observationOnly": True,
                    "decisionGrade": False,
                }
            ],
            "aggregateSummary": {
                "queueQuality": "mixed",
                "priorityCounts": {"medium": 1},
                "duplicateEvidenceMerged": 1,
                "queueDiversity": {"status": "mixed"},
            },
            "evidenceGaps": ["Theme breadth needs review"],
            "evidenceGapsRaw": ["themeBreadth"],
            "marketContextFit": "neutral",
            "drilldownTargets": [
                {
                    "label": "Structure detail",
                    "route": "/stocks/ALFA/structure-decision",
                    "reason": "Open the structure workspace for this ticker.",
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
            "onboardingGuidance": None,
            "emptyStateActions": [],
            "starterResearchWorkflow": [],
            "firstRunChecklist": [],
            "suggestedResearchEntrypoints": [],
            "noAdviceDisclosure": "Research-only queue; verify evidence gaps before further review.",
            "dataQuality": {
                "status": "partial",
                "missingEvidence": ["Theme breadth needs review"],
                "missingEvidenceRaw": ["themeBreadth"],
                "consumerIssues": [
                    {
                        "label": "Evidence needs review",
                        "message": "Some quality checks are not fully cleared yet.",
                        "severity": "info",
                        "category": "evidence",
                    }
                ],
            },
            "observationOnly": True,
            "decisionGrade": False,
        }


def _client(monkeypatch) -> TestClient:
    from api.v1.endpoints import research

    _FakeResearchRadarService.calls = []
    monkeypatch.setattr(research, "ResearchRadarService", _FakeResearchRadarService)

    app = FastAPI()
    app.include_router(api_v1_router)
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_database_manager] = lambda: object()
    return TestClient(app)


def test_get_research_radar_endpoint_is_registered_and_returns_contract(monkeypatch) -> None:
    response = _client(monkeypatch).get(
        "/api/v1/research/radar",
        params={"market": "us", "profile": "us_preopen_v1", "limit": 5},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert {
        "schemaVersion",
        "generatedAt",
        "researchQueue",
        "aggregateSummary",
        "evidenceGaps",
        "evidenceGapsRaw",
        "marketContextFit",
        "drilldownTargets",
        "consumerIssues",
        "onboardingGuidance",
        "emptyStateActions",
        "starterResearchWorkflow",
        "firstRunChecklist",
        "suggestedResearchEntrypoints",
        "noAdviceDisclosure",
        "dataQuality",
        "observationOnly",
        "decisionGrade",
    }.issubset(payload)
    assert payload["researchQueue"][0]["symbol"] == "ALFA"
    assert payload["researchQueue"][0]["researchBias"] == "Strength observation"
    assert payload["researchQueue"][0]["researchBiasRaw"] == "strengthContinuation"
    assert payload["researchQueue"][0]["whyNotHigherPriority"] == [
        "Evidence quality is below the strong research threshold."
    ]
    assert payload["researchQueue"][0]["evidenceGaps"] == ["Theme breadth needs review"]
    assert payload["researchQueue"][0]["evidenceGapsRaw"] == ["themeBreadth"]
    assert payload["researchQueue"][0]["consumerIssues"][0]["label"] == "Evidence needs review"
    assert payload["researchQueue"][0]["drilldownTargets"][0]["route"] == "/stocks/ALFA/structure-decision"
    assert payload["consumerIssues"][0]["label"] == "Evidence needs review"
    assert payload["onboardingGuidance"] is None
    assert payload["emptyStateActions"] == []
    assert payload["starterResearchWorkflow"] == []
    assert payload["firstRunChecklist"] == []
    assert payload["suggestedResearchEntrypoints"] == []
    assert payload["researchQueue"][0]["duplicateEvidenceMerged"] == 1
    assert payload["aggregateSummary"]["duplicateEvidenceMerged"] == 1
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert _FakeResearchRadarService.calls == [
        {
            "market": "us",
            "profile": "us_preopen_v1",
            "owner_id": "user-1",
            "limit": 5,
            "hasScannerRepository": True,
        }
    ]


def test_get_research_radar_endpoint_uses_typed_response_model() -> None:
    route = next(
        route
        for route in api_v1_router.routes
        if isinstance(route, APIRoute) and route.path == "/api/v1/research/radar" and "GET" in route.methods
    )

    assert route.response_model is not None
    assert route.response_model.__name__ == "ResearchRadarResponse"


def test_get_research_radar_endpoint_clamps_limit_and_passes_optional_filters(monkeypatch) -> None:
    response = _client(monkeypatch).get("/api/v1/research/radar", params={"limit": 100})

    assert response.status_code == 200, response.text
    assert _FakeResearchRadarService.calls == [
        {
            "market": None,
            "profile": None,
            "owner_id": "user-1",
            "limit": 20,
            "hasScannerRepository": True,
        }
    ]
