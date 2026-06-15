# -*- coding: utf-8 -*-
"""HTTP contract tests for the stock structure decision endpoint."""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import stocks as stocks_endpoint
from src.services.stock_structure_decision_service import STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION


FORBIDDEN_ADVICE_TOKENS = (
    "buy",
    "sell",
    "hold",
    "position",
    "target",
    "stop",
    "entry",
    "exit",
    "recommendation",
    "买入",
    "卖出",
    "持有",
    "仓位",
    "目标",
    "止损",
    "止盈",
    "推荐",
)


class _FakeStructureDecisionService:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def get_structure_decision(self, ticker: str) -> dict[str, Any]:
        self.calls.append(ticker)
        return self.payload


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(stocks_endpoint.router, prefix="/api/v1/stocks")
    return TestClient(app)


def _payload(
    *,
    ticker: str = "AAPL",
    structure_state: str = "breakout",
    confidence: str = "high",
    data_status: str = "available",
    missing_evidence: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "schemaVersion": STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION,
        "ticker": ticker,
        "structureState": structure_state,
        "confidence": confidence,
        "componentScores": {
            "trend": 78,
            "relativeStrength": 50,
            "volumePressure": 76,
            "volatilityCompression": 35,
            "breakoutQuality": 86,
            "pullbackHealth": 48,
            "riskExtension": 55,
            "evidenceQuality": 100,
        },
        "explanation": {
            "whyThisStructure": "Price closed above the recent observed range with expanded volume and positive trend evidence.",
            "whatConfirmsIt": ["Breakout quality is supported by a close above the recent range and stronger volume."],
            "whatInvalidatesIt": ["More complete OHLCV evidence may change the structure description."],
            "keyLevels": [{"kind": "recentRangeHigh", "value": 131.2, "description": "Upper observation from recent highs."}],
        },
        "researchNotes": {
            "watchNext": ["Observe whether closes remain outside the prior range with continued volume confirmation."],
            "needsMoreEvidence": [],
            "riskFlags": ["No dominant risk flag from deterministic OHLCV components."],
        },
        "dataQuality": {
            "status": data_status,
            "source": "local_db" if data_status == "available" else "unavailable",
            "period": "daily",
            "requestedDays": 90,
            "observedBars": 55 if data_status == "available" else 0,
            "usableBars": 55 if data_status == "available" else 0,
            "reason": "history_available" if data_status == "available" else "history_unavailable",
        },
        "missingEvidence": missing_evidence or [],
        "noAdviceDisclosure": "Observation-only research context; not personalized financial advice and not an instruction.",
    }


def test_structure_decision_endpoint_returns_required_contract(monkeypatch) -> None:
    fake_service = _FakeStructureDecisionService(_payload())
    monkeypatch.setattr(
        stocks_endpoint,
        "StockStructureDecisionService",
        lambda: fake_service,
        raising=False,
    )

    response = _client().get("/api/v1/stocks/AAPL/structure-decision")

    assert response.status_code == 200
    payload = response.json()
    assert fake_service.calls == ["AAPL"]
    assert payload["schemaVersion"] == STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION
    assert payload["ticker"] == "AAPL"
    for key in (
        "structureState",
        "confidence",
        "componentScores",
        "explanation",
        "researchNotes",
        "dataQuality",
        "missingEvidence",
        "noAdviceDisclosure",
    ):
        assert key in payload


def test_structure_decision_endpoint_returns_low_confidence_unavailable_payload(monkeypatch) -> None:
    fake_service = _FakeStructureDecisionService(
        _payload(
            structure_state="lowConfidence",
            confidence="low",
            data_status="unavailable",
            missing_evidence=[
                {
                    "kind": "daily_ohlcv",
                    "message": "Daily OHLCV history is unavailable, so the structure state is low confidence.",
                }
            ],
        )
    )
    monkeypatch.setattr(
        stocks_endpoint,
        "StockStructureDecisionService",
        lambda: fake_service,
        raising=False,
    )

    response = _client().get("/api/v1/stocks/AAPL/structure-decision")

    assert response.status_code == 200
    payload = response.json()
    assert payload["structureState"] == "lowConfidence"
    assert payload["confidence"] == "low"
    assert payload["dataQuality"]["status"] == "unavailable"
    assert payload["missingEvidence"][0]["kind"] == "daily_ohlcv"
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in FORBIDDEN_ADVICE_TOKENS:
        assert forbidden not in serialized


def test_structure_decision_openapi_locks_required_response_fields() -> None:
    schema = _client().get("/openapi.json").json()["components"]["schemas"]

    response_schema = schema["StockStructureDecisionResponse"]
    assert response_schema["required"] == [
        "schemaVersion",
        "ticker",
        "structureState",
        "confidence",
        "componentScores",
        "explanation",
        "researchNotes",
        "dataQuality",
        "missingEvidence",
        "noAdviceDisclosure",
    ]
    properties = response_schema["properties"]
    assert properties["schemaVersion"]["type"] == "string"
    assert properties["ticker"]["type"] == "string"
    assert properties["structureState"]["type"] == "string"
    assert properties["componentScores"]["additionalProperties"]["type"] == "integer"
