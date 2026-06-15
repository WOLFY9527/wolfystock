# -*- coding: utf-8 -*-
"""API tests for the scanner research overlay endpoint."""

from __future__ import annotations

import copy

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user, get_database_manager
from api.v1.router import router as api_v1_router


DETAIL_PAYLOAD = {
    "id": 42,
    "market": "us",
    "profile": "us_preopen_v1",
    "status": "completed",
    "universe_name": "us_liquid",
    "shortlist_size": 1,
    "universe_size": 3,
    "preselected_size": 3,
    "evaluated_size": 3,
    "scannerContextFrame": {
        "marketReadiness": {"readinessState": "ready"},
        "themeFrame": {"state": "available"},
    },
    "shortlist": [
        {
            "symbol": "ALFA",
            "name": "Alfa Corp",
            "rank": 1,
            "score": 82.0,
            "raw_score": 83.0,
            "final_score": 82.0,
            "boards": ["AI Infrastructure"],
            "candidateEvidenceFrame": {
                "coverageState": "available",
                "coverage": {"availableCount": 7, "partialCount": 1, "missingCount": 0, "totalCount": 8},
            },
            "candidateResearchReadiness": {
                "readinessState": "ready",
                "missingEvidence": [],
                "consumerActionBoundary": "no_advice",
            },
            "candidateResearchSummaryFrame": {
                "frameState": "ready",
                "primaryResearchReason": "Evidence explains why this scanner candidate merits research today.",
                "evidenceHighlights": ["Technicals available"],
                "missingEvidence": [],
                "nextResearchStep": "Confirm evidence persistence.",
                "noAdviceBoundary": True,
            },
        }
    ],
    "selected": [
        {
            "symbol": "ALFA",
            "name": "Alfa Corp",
            "rank": 1,
            "score": 82.0,
            "raw_score": 83.0,
            "final_score": 82.0,
        }
    ],
}


def _user(*, admin: bool = False) -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="alice",
        display_name="Alice",
        role="admin" if admin else "user",
        is_admin=admin,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="session-1",
    )


class _FakeScannerService:
    calls: list[dict[str, object]] = []

    def __init__(self, payloads: dict[str, object] | None = None) -> None:
        self.payloads = payloads or {"user": copy.deepcopy(DETAIL_PAYLOAD), "system": None}

    def get_run_detail(self, run_id: int, *, scope: str) -> dict[str, object] | None:
        self.__class__.calls.append({"run_id": run_id, "scope": scope})
        key = "system" if scope == "system" else "user"
        payload = self.payloads.get(key)
        return copy.deepcopy(payload) if isinstance(payload, dict) else None


def _client(monkeypatch, *, service: _FakeScannerService | None = None, admin: bool = False) -> TestClient:
    from api.v1.endpoints import scanner

    _FakeScannerService.calls = []
    fake_service = service or _FakeScannerService()
    monkeypatch.setattr(scanner, "_build_scanner_service", lambda db_manager, current_user: fake_service)

    app = FastAPI()
    app.include_router(api_v1_router)
    app.dependency_overrides[get_current_user] = lambda: _user(admin=admin)
    app.dependency_overrides[get_database_manager] = lambda: object()
    return TestClient(app)


def test_get_scanner_research_overlay_returns_additive_projection_without_mutating_detail(monkeypatch) -> None:
    source_payload = copy.deepcopy(DETAIL_PAYLOAD)
    service = _FakeScannerService(payloads={"user": source_payload, "system": None})

    response = _client(monkeypatch, service=service).get("/api/v1/scanner/runs/42/research-overlay")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert {
        "schemaVersion",
        "items",
        "aggregateSummary",
        "queueDiversity",
        "dataQuality",
        "missingEvidence",
        "noAdviceDisclosure",
    }.issubset(payload)
    assert payload["items"][0]["ticker"] == "ALFA"
    assert payload["items"][0]["originalScannerCandidateState"] == {
        "ticker": "ALFA",
        "rank": 1,
        "score": 82.0,
        "rawScore": 83.0,
        "finalScore": 82.0,
        "status": "selected",
    }
    assert payload["items"][0]["researchPriority"] == "high"
    assert payload["items"][0]["whyThisMattersToday"]
    assert _FakeScannerService.calls == [{"run_id": 42, "scope": "user"}]
    assert source_payload == DETAIL_PAYLOAD


def test_get_scanner_research_overlay_uses_admin_system_fallback(monkeypatch) -> None:
    service = _FakeScannerService(payloads={"user": None, "system": copy.deepcopy(DETAIL_PAYLOAD)})

    response = _client(monkeypatch, service=service, admin=True).get("/api/v1/scanner/runs/42/research-overlay")

    assert response.status_code == 200, response.text
    assert response.json()["runId"] == 42
    assert _FakeScannerService.calls == [
        {"run_id": 42, "scope": "user"},
        {"run_id": 42, "scope": "system"},
    ]


def test_get_scanner_research_overlay_returns_404_when_run_is_not_visible(monkeypatch) -> None:
    service = _FakeScannerService(payloads={"user": None, "system": copy.deepcopy(DETAIL_PAYLOAD)})

    response = _client(monkeypatch, service=service, admin=False).get("/api/v1/scanner/runs/42/research-overlay")

    assert response.status_code == 404, response.text
    assert _FakeScannerService.calls == [{"run_id": 42, "scope": "user"}]
