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
        self.calls: list[dict[str, Any]] = []
        self.batch_calls: list[dict[str, Any]] = []

    def get_structure_decision(
        self,
        ticker: str,
        *,
        context_source: str | None = None,
        context_section: str | None = None,
        context_reason: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "ticker": ticker,
                "context_source": context_source,
                "context_section": context_section,
                "context_reason": context_reason,
            }
        )
        return self.payload

    def get_structure_decisions_batch(
        self,
        tickers: list[str],
        *,
        benchmark: str | None = None,
        max_items: int | None = None,
    ) -> dict[str, Any]:
        self.batch_calls.append({"tickers": tickers, "benchmark": benchmark, "max_items": max_items})
        return {
            "schemaVersion": STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION,
            "items": [
                _payload(ticker="MSFT", structure_state="mixed", confidence="medium"),
                _payload(ticker="AAPL", structure_state="breakout", confidence="high"),
            ],
            "aggregateSummary": {
                "requestedCount": 3,
                "evaluatedCount": 2,
                "maxItems": 2,
                "truncated": True,
                "structureStateCounts": {"mixed": 1, "breakout": 1},
                "strongestStructures": [{"ticker": "AAPL", "structureState": "breakout", "score": 86}],
                "weakestEvidence": [{"ticker": "MSFT", "status": "available", "usableBars": 55}],
                "commonRiskFlags": [],
                "relativeStrength": {
                    "status": "available",
                    "benchmark": "SPY",
                    "ranking": [
                        {"rank": 1, "ticker": "AAPL", "relativeStrengthScore": 66},
                        {"rank": 2, "ticker": "MSFT", "relativeStrengthScore": 51},
                    ],
                },
            },
            "missingEvidence": [],
            "dataQuality": {
                "status": "available",
                "availableCount": 2,
                "partialCount": 0,
                "insufficientCount": 0,
                "unavailableCount": 0,
            },
            "symbolCompareEvidencePacket": {
                "comparedSymbols": ["MSFT", "AAPL"],
                "sharedEvidence": [
                    {
                        "kind": "daily_ohlcv",
                        "symbols": ["MSFT", "AAPL"],
                        "status": "available",
                        "period": "daily",
                        "source": "local_db",
                        "usableBarsMin": 55,
                        "usableBarsMax": 55,
                    }
                ],
                "divergentEvidence": [
                    {
                        "kind": "structure_state",
                        "symbols": ["MSFT", "AAPL"],
                        "values": {"MSFT": "mixed", "AAPL": "breakout"},
                    }
                ],
                "missingEvidenceBySymbol": {"MSFT": [], "AAPL": []},
                "freshnessBySymbol": {
                    "MSFT": {"status": "available", "source": "local_db", "period": "daily", "usableBars": 55},
                    "AAPL": {"status": "available", "source": "local_db", "period": "daily", "usableBars": 55},
                },
                "confidenceCap": {
                    "value": 100,
                    "reasonCodes": [],
                    "policyVersion": "symbol_compare_evidence_packet_v1",
                },
                "observationBoundary": {
                    "observationOnly": True,
                    "decisionGrade": False,
                    "rankingAllowed": False,
                    "adviceAllowed": False,
                },
                "researchNextSteps": [],
            },
            "noAdviceDisclosure": "Observation-only research context; not personalized financial advice and not an instruction.",
        }


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
        "symbol": ticker,
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
        "keyLevels": [{"kind": "recentRangeHigh", "value": 131.2, "description": "Upper observation from recent highs."}],
        "evidenceNotes": ["Breakout quality is supported by a close above the recent range and stronger volume."],
        "riskObservations": [
            "No dominant risk flag from deterministic OHLCV components.",
            "More complete OHLCV evidence may change the structure description.",
        ],
        "evidenceGaps": [item["message"] for item in (missing_evidence or [])],
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
        "degradedInputs": (
            []
            if data_status == "available"
            else [{"section": "structureEvidence", "status": "unavailable", "reason": "history_unavailable"}]
        ),
        "peerCorrelationSnapshot": {
            "symbol": ticker,
            "peerGroup": {"status": "unavailable", "label": None, "symbols": []},
            "correlationState": "insufficient_evidence",
            "peerEvidence": [],
            "divergenceEvidence": [],
            "staleInputs": [],
            "missingInputs": ["No verified local peer group metadata is available for this symbol."],
            "confidenceCap": "low",
            "observationBoundary": "Observation-only peer movement context; no personalized action instruction.",
            "researchNextSteps": [
                "Add verified local peer group metadata before interpreting peer movement.",
                "Load recent local daily OHLCV for the symbol and at least two verified peers.",
            ],
        },
        "consumerIssues": (
            []
            if data_status == "available"
            else [
                {
                    "label": "Structure evidence unavailable",
                    "message": "Daily structure evidence is not available for this symbol yet.",
                    "severity": "warning",
                    "category": "evidence",
                }
            ]
        ),
        "noAdviceDisclosure": "Observation-only research context; not personalized financial advice and not an instruction.",
        "observationOnly": True,
        "decisionGrade": False,
        "drilldownLinks": [],
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
    assert fake_service.calls == [
        {
            "ticker": "AAPL",
            "context_source": None,
            "context_section": None,
            "context_reason": None,
        }
    ]
    assert payload["schemaVersion"] == STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION
    assert payload["ticker"] == "AAPL"
    assert payload["symbol"] == "AAPL"
    for key in (
        "structureState",
        "confidence",
        "componentScores",
        "explanation",
        "researchNotes",
        "keyLevels",
        "evidenceNotes",
        "riskObservations",
        "evidenceGaps",
        "dataQuality",
        "missingEvidence",
        "degradedInputs",
        "peerCorrelationSnapshot",
        "consumerIssues",
        "noAdviceDisclosure",
        "observationOnly",
        "decisionGrade",
        "drilldownLinks",
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
    assert payload["consumerIssues"][0]["label"] == "Structure evidence unavailable"
    assert payload["degradedInputs"][0]["section"] == "structureEvidence"
    consumer_copy = json.dumps(
        {
            "consumerIssues": payload["consumerIssues"],
            "evidenceGaps": payload["evidenceGaps"],
            "drilldownLinks": payload["drilldownLinks"],
        },
        ensure_ascii=False,
    ).lower()
    assert "history_unavailable" not in consumer_copy
    assert "daily_ohlcv" not in consumer_copy
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in FORBIDDEN_ADVICE_TOKENS:
        assert forbidden not in serialized


def test_structure_decision_endpoint_keeps_drilldown_targets_on_safe_allowlist(monkeypatch) -> None:
    fake_service = _FakeStructureDecisionService(
        {
            **_payload(),
            "sourceContext": {
                "source": "researchRadar",
                "label": "Research Radar",
                "route": "/research/radar",
                "section": "scannerHighlights",
                "reason": "Scanner candidate context.",
            },
            "drilldownLinks": [
                {
                    "source": "researchRadar",
                    "label": "Research Radar",
                    "route": "/research/radar",
                    "section": "scannerHighlights",
                    "reason": "Scanner candidate context.",
                }
            ],
        }
    )
    monkeypatch.setattr(
        stocks_endpoint,
        "StockStructureDecisionService",
        lambda: fake_service,
        raising=False,
    )

    response = _client().get(
        "/api/v1/stocks/AAPL/structure-decision",
        params={
            "contextSource": "researchRadar",
            "contextSection": "scannerHighlights",
            "contextReason": "scanner_candidates_origin",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert fake_service.calls == [
        {
            "ticker": "AAPL",
            "context_source": "researchRadar",
            "context_section": "scannerHighlights",
            "context_reason": "scanner_candidates_origin",
        }
    ]
    assert payload["sourceContext"]["route"] == "/research/radar"
    assert payload["drilldownLinks"][0]["route"] == "/research/radar"
    assert payload["drilldownLinks"][0]["label"] == "Research Radar"
    assert payload["drilldownLinks"][0]["reason"] == "Scanner candidate context."


def test_structure_decision_batch_endpoint_returns_comparative_contract(monkeypatch) -> None:
    fake_service = _FakeStructureDecisionService(_payload())
    monkeypatch.setattr(
        stocks_endpoint,
        "StockStructureDecisionService",
        lambda: fake_service,
        raising=False,
    )

    response = _client().post(
        "/api/v1/stocks/structure-decisions/batch",
        json={"stockCodes": ["msft", "aapl", "msft"], "benchmark": "spy", "maxItems": 2},
    )

    assert response.status_code == 200
    payload = response.json()
    assert fake_service.batch_calls == [
        {"tickers": ["msft", "aapl", "msft"], "benchmark": "spy", "max_items": 2}
    ]
    assert payload["schemaVersion"] == STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION
    assert [item["ticker"] for item in payload["items"]] == ["MSFT", "AAPL"]
    assert payload["aggregateSummary"]["requestedCount"] == 3
    assert payload["aggregateSummary"]["evaluatedCount"] == 2
    assert payload["aggregateSummary"]["maxItems"] == 2
    assert payload["aggregateSummary"]["truncated"] is True
    assert payload["aggregateSummary"]["relativeStrength"]["status"] == "available"
    assert payload["aggregateSummary"]["relativeStrength"]["benchmark"] == "SPY"
    assert "missingEvidence" in payload
    assert "dataQuality" in payload
    assert payload["symbolCompareEvidencePacket"]["comparedSymbols"] == ["MSFT", "AAPL"]
    assert payload["symbolCompareEvidencePacket"]["observationBoundary"] == {
        "observationOnly": True,
        "decisionGrade": False,
        "rankingAllowed": False,
        "adviceAllowed": False,
    }
    assert payload["symbolCompareEvidencePacket"]["confidenceCap"]["value"] == 100
    assert payload["noAdviceDisclosure"]
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in FORBIDDEN_ADVICE_TOKENS:
        assert forbidden not in serialized
    assert "winner" not in serialized
    assert "loser" not in serialized
    assert "best" not in serialized


def test_structure_decision_batch_endpoint_rejects_empty_stock_codes(monkeypatch) -> None:
    fake_service = _FakeStructureDecisionService(_payload())
    monkeypatch.setattr(
        stocks_endpoint,
        "StockStructureDecisionService",
        lambda: fake_service,
        raising=False,
    )

    response = _client().post(
        "/api/v1/stocks/structure-decisions/batch",
        json={"stockCodes": [], "maxItems": 3},
    )

    assert response.status_code == 422
    assert fake_service.batch_calls == []


def test_structure_decision_openapi_locks_required_response_fields() -> None:
    schema = _client().get("/openapi.json").json()["components"]["schemas"]

    response_schema = schema["StockStructureDecisionResponse"]
    assert response_schema["required"] == [
        "schemaVersion",
        "ticker",
        "symbol",
        "structureState",
        "confidence",
        "componentScores",
        "explanation",
        "researchNotes",
        "keyLevels",
        "evidenceNotes",
        "riskObservations",
        "evidenceGaps",
        "dataQuality",
        "missingEvidence",
        "degradedInputs",
        "peerCorrelationSnapshot",
        "consumerIssues",
        "noAdviceDisclosure",
        "observationOnly",
        "decisionGrade",
        "drilldownLinks",
    ]
    properties = response_schema["properties"]
    assert properties["schemaVersion"]["type"] == "string"
    assert properties["ticker"]["type"] == "string"
    assert properties["symbol"]["type"] == "string"
    assert properties["structureState"]["type"] == "string"
    assert "StockPeerCorrelationSnapshot" in properties["peerCorrelationSnapshot"]["$ref"]
    assert properties["componentScores"]["additionalProperties"]["type"] == "integer"

    batch_schema = schema["StockStructureDecisionBatchResponse"]
    assert batch_schema["required"] == [
        "schemaVersion",
        "items",
        "aggregateSummary",
        "missingEvidence",
        "dataQuality",
        "symbolCompareEvidencePacket",
        "noAdviceDisclosure",
    ]
    compare_schema = schema["StockStructureDecisionBatchResponse"]["properties"]["symbolCompareEvidencePacket"]
    assert compare_schema["$ref"].endswith("StockSymbolCompareEvidencePacket")
    compare_packet_schema = schema["StockSymbolCompareEvidencePacket"]
    assert compare_packet_schema["required"] == [
        "comparedSymbols",
        "sharedEvidence",
        "divergentEvidence",
        "missingEvidenceBySymbol",
        "freshnessBySymbol",
        "confidenceCap",
        "observationBoundary",
        "researchNextSteps",
    ]
