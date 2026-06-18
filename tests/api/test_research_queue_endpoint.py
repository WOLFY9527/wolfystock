# -*- coding: utf-8 -*-
"""API tests for the unified research queue endpoint."""

from __future__ import annotations

import copy
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user, get_database_manager
from api.v1.router import router as api_v1_router


SCANNER_PAYLOAD = {
    "id": 42,
    "completed_at": "2026-06-15T09:30:00+00:00",
    "shortlist": [
        {
            "symbol": "ALFA",
            "rank": 1,
            "score": 82.0,
            "consumerDiagnostics": {"freshnessState": "fresh"},
            "candidateResearchPacket": {
                "whySurfaced": "Scanner evidence explains why this candidate merits research today.",
                "primaryEvidence": ["Technicals available"],
                "limitingEvidence": [],
                "dataQualityNotes": ["freshness: fresh"],
                "researchNextStep": "Confirm evidence persistence.",
                "observationOnly": True,
            },
        }
    ],
}
WATCHLIST_OVERLAY = {
    "researchPriorityQueue": [
        {
            "symbol": "MSFT",
            "priorityTier": "attention",
            "priorityReasonSafeLabel": "Missing evidence needs review.",
            "evidenceAge": {"state": "no_evidence", "lastReviewedAt": None},
            "missingEvidence": ["Price-history evidence"],
            "suggestedResearchPath": [
                {
                    "label": "Stock Structure",
                    "route": "/stocks/MSFT/structure-decision",
                    "section": "watchlistResearchOverlay",
                    "reason": "Open symbol structure detail.",
                }
            ],
            "observationOnly": True,
        }
    ],
}


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


def _serialized_values(payload: object) -> str:
    values: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, str):
            values.append(value)
            return
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    visit(payload)
    return json.dumps(values, ensure_ascii=False, sort_keys=True).lower()


def _client(monkeypatch) -> tuple[TestClient, dict[str, object]]:
    from api.v1.endpoints import research

    calls: dict[str, object] = {"scanner": [], "watchlist": []}

    def fake_scanner_payload(**kwargs: object) -> dict[str, object]:
        calls["scanner"].append(kwargs)
        return copy.deepcopy(SCANNER_PAYLOAD)

    def fake_watchlist_overlay(*, owner_id: str | None) -> dict[str, object]:
        calls["watchlist"].append({"owner_id": owner_id})
        return copy.deepcopy(WATCHLIST_OVERLAY)

    monkeypatch.setattr(research, "_latest_scanner_research_payload", fake_scanner_payload)
    monkeypatch.setattr(research, "_watchlist_research_overlay_payload", fake_watchlist_overlay)

    app = FastAPI()
    app.include_router(api_v1_router)
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_database_manager] = lambda: object()
    return TestClient(app), calls


def test_get_research_queue_returns_bounded_unified_contract(monkeypatch) -> None:
    client, calls = _client(monkeypatch)

    response = client.get(
        "/api/v1/research/queue",
        params={"market": "us", "profile": "us_preopen_v1", "scanner_limit": 7, "queue_limit": 4},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "schemaVersion" not in payload
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert payload["consumerSafeSourceLabel"] == "部分数据源暂不可用"
    assert payload["dataQualityState"] == "limited"
    assert payload["freshnessState"] == "limited"
    assert payload["observationBoundary"]
    assert payload["researchNextSteps"]
    assert payload["sourceSurfacesAggregated"] == ["watchlist", "scanner"]
    assert payload["aggregateSummary"] == {
        "itemCount": 2,
        "limit": 4,
        "bounded": False,
        "bySourceSurface": {"watchlist": 1, "scanner": 1},
        "byPriorityTier": {"urgent_review": 1, "follow_up": 1, "monitor": 0},
    }
    assert [item["sourceSurface"] for item in payload["researchQueue"]] == ["watchlist", "scanner"]
    assert [item["symbol"] for item in payload["researchQueue"]] == ["MSFT", "ALFA"]
    assert payload["researchQueue"][0]["priorityTier"] == "urgent_review"
    assert payload["researchQueue"][1]["priorityTier"] == "follow_up"
    assert payload["researchQueue"][1]["suggestedResearchPath"][0]["route"] == "/stocks/ALFA/structure-decision"
    assert payload["evidenceGaps"] == ["Price-history evidence"]
    assert payload["dataQuality"]["state"] == "ready"

    scanner_call = calls["scanner"][0]
    assert scanner_call["market"] == "us"
    assert scanner_call["profile"] == "us_preopen_v1"
    assert scanner_call["limit"] == 7
    assert calls["watchlist"] == [{"owner_id": "user-1"}]

    serialized_queue = _serialized_values(payload["researchQueue"])
    for forbidden in ("buy", "sell", "hold", "target price", "stop loss", "provider", "trace id", "debug"):
        assert forbidden not in serialized_queue


def test_get_research_queue_fails_closed_when_sources_are_empty(monkeypatch) -> None:
    from api.v1.endpoints import research

    monkeypatch.setattr(research, "_latest_scanner_research_payload", lambda **kwargs: None)
    monkeypatch.setattr(research, "_watchlist_research_overlay_payload", lambda **kwargs: None)

    app = FastAPI()
    app.include_router(api_v1_router)
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_database_manager] = lambda: object()

    response = TestClient(app).get("/api/v1/research/queue")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["researchQueue"] == []
    assert payload["dataQuality"]["state"] == "no_evidence"
    assert payload["dataQuality"]["failClosed"] is True
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
