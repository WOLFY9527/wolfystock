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

    def __init__(
        self,
        *,
        scanner_repository: object | None = None,
        backtest_sample_reader: object | None = None,
    ) -> None:
        self.scanner_repository = scanner_repository
        self.backtest_sample_reader = backtest_sample_reader

    def build_from_latest_scanner_run(self, **kwargs: object) -> dict[str, object]:
        self.__class__.calls.append(
            {
                **kwargs,
                "hasScannerRepository": self.scanner_repository is not None,
                "hasBacktestSampleReader": self.backtest_sample_reader is not None,
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
            "evidenceHub": {
                "scannerCandidates": {
                    "key": "scanner",
                    "label": "Scanner candidates",
                    "status": "available",
                    "summary": "Scanner candidate evidence is available for radar review.",
                    "blocker": None,
                    "nextDataAction": "Refresh scanner when candidate evidence needs a newer observation window.",
                    "evidenceCount": 1,
                    "totalCount": 1,
                    "symbols": ["ALFA"],
                    "details": ["ALFA is available for radar review."],
                    "observationOnly": True,
                    "decisionGrade": False,
                },
                "backtestSamples": {
                    "key": "backtest",
                    "label": "Backtest samples",
                    "status": "blocked",
                    "summary": "Backtest samples are unavailable for radar symbols.",
                    "blocker": "Backtest samples have not been prepared for the radar symbols.",
                    "nextDataAction": "Open Backtest and prepare or refresh samples for the radar symbols.",
                    "evidenceCount": 0,
                    "totalCount": 1,
                    "symbols": ["ALFA"],
                    "details": ["ALFA has no prepared backtest samples."],
                    "observationOnly": True,
                    "decisionGrade": False,
                },
                "stockReadiness": {
                    "key": "stock",
                    "label": "Stock readiness",
                    "status": "available",
                    "summary": "Stock technical readiness is available for radar symbols.",
                    "blocker": None,
                    "nextDataAction": "Refresh daily price history and technical evidence for radar symbols.",
                    "evidenceCount": 1,
                    "totalCount": 1,
                    "symbols": ["ALFA"],
                    "details": ["ALFA has technical readiness evidence."],
                    "observationOnly": True,
                    "decisionGrade": False,
                },
                "dataActivation": {
                    "key": "data",
                    "label": "Data activation",
                    "status": "partial",
                    "summary": "Research Radar evidence is partially activated.",
                    "blocker": "Backtest samples have not been prepared for the radar symbols.",
                    "nextDataAction": "Resolve blocked evidence slices, then refresh Research Radar.",
                    "evidenceCount": 2,
                    "totalCount": 3,
                    "symbols": [],
                    "details": [
                        "Scanner candidates status available.",
                        "Backtest samples status blocked.",
                        "Stock readiness status available.",
                    ],
                    "observationOnly": True,
                    "decisionGrade": False,
                },
                "missingEvidenceStates": [
                    {
                        "key": "backtest",
                        "label": "Backtest samples",
                        "status": "blocked",
                        "summary": "Backtest samples are unavailable for radar symbols.",
                        "blocker": "Backtest samples have not been prepared for the radar symbols.",
                        "nextDataAction": "Open Backtest and prepare or refresh samples for the radar symbols.",
                        "evidenceCount": 0,
                        "totalCount": 1,
                        "symbols": ["ALFA"],
                        "details": ["ALFA has no prepared backtest samples."],
                        "observationOnly": True,
                        "decisionGrade": False,
                    }
                ],
            },
            "observationOnly": True,
            "decisionGrade": False,
        }


class _FakeBacktestService:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs

    def get_sample_status(self, *, code: str | None) -> dict[str, object]:
        return {
            "code": code,
            "prepared_count": 0,
            "sample_readiness_state": "missing_cache",
            "execution_readiness": {"state": "data_disabled"},
        }


def _client(monkeypatch, *, regime_read_model: dict[str, object] | None = None) -> TestClient:
    from api.v1.endpoints import research

    _FakeResearchRadarService.calls = []
    monkeypatch.setattr(research, "ResearchRadarService", _FakeResearchRadarService)
    monkeypatch.setattr(research, "BacktestService", _FakeBacktestService)
    monkeypatch.setattr(research, "build_market_regime_read_model", lambda **_: regime_read_model)

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
    assert "schemaVersion" not in payload
    assert "researchBiasRaw" not in payload["researchQueue"][0]
    assert "evidenceGapsRaw" not in payload
    assert "evidenceGapsRaw" not in payload["researchQueue"][0]
    assert "missingEvidenceRaw" not in payload["dataQuality"]
    assert {
        "generatedAt",
        "researchQueue",
        "aggregateSummary",
        "evidenceGaps",
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
        "evidenceHub",
        "observationOnly",
        "decisionGrade",
    }.issubset(payload)
    assert payload["consumerSafeSourceLabel"] == "部分数据源暂不可用"
    assert payload["dataQualityState"] == "limited"
    assert payload["freshnessState"] == "limited"
    assert payload["observationBoundary"]
    assert payload["researchNextSteps"]
    assert payload["researchQueue"][0]["symbol"] == "ALFA"
    assert payload["researchQueue"][0]["researchBias"] == "Strength observation"
    assert "researchBiasRaw" not in payload["researchQueue"][0]
    assert payload["researchQueue"][0]["whyNotHigherPriority"] == [
        "Evidence quality is below the strong research threshold."
    ]
    assert payload["researchQueue"][0]["evidenceGaps"] == ["Theme breadth needs review"]
    assert "evidenceGapsRaw" not in payload["researchQueue"][0]
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
    assert payload["evidenceHub"]["scannerCandidates"]["status"] == "available"
    assert payload["evidenceHub"]["backtestSamples"]["blocker"] == (
        "Backtest samples have not been prepared for the radar symbols."
    )
    serialized_hub = str(payload["evidenceHub"])
    assert "provider" not in serialized_hub.lower()
    assert "request" not in serialized_hub.lower()
    assert "trace" not in serialized_hub.lower()
    assert "raw" not in serialized_hub.lower()
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert _FakeResearchRadarService.calls == [
        {
            "market": "us",
            "profile": "us_preopen_v1",
            "owner_id": "user-1",
            "limit": 5,
            "market_regime_read_model": None,
            "hasScannerRepository": True,
            "hasBacktestSampleReader": True,
        }
    ]


def test_get_research_radar_endpoint_uses_typed_response_model() -> None:
    from api.v1.endpoints import research

    route = next(
        route
        for route in research.router.routes
        if isinstance(route, APIRoute) and route.path == "/radar" and "GET" in route.methods
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
            "market_regime_read_model": None,
            "hasScannerRepository": True,
            "hasBacktestSampleReader": True,
        }
    ]


def test_get_research_radar_endpoint_passes_market_regime_read_model(monkeypatch) -> None:
    read_model = {
        "status": "ok",
        "readiness": {"label": "product_ready"},
        "regime": {"label": "risk_on_confirming"},
        "productSummary": "Market regime evidence is available from local inputs.",
        "evidenceCards": [],
        "dataQuality": {},
        "nextOperatorAction": "Market regime read model is available from local evidence inputs.",
    }

    response = _client(monkeypatch, regime_read_model=read_model).get("/api/v1/research/radar")

    assert response.status_code == 200, response.text
    assert _FakeResearchRadarService.calls == [
        {
            "market": None,
            "profile": None,
            "owner_id": "user-1",
            "limit": 20,
            "market_regime_read_model": read_model,
            "hasScannerRepository": True,
            "hasBacktestSampleReader": True,
        }
    ]
