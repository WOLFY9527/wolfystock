# -*- coding: utf-8 -*-
"""HTTP contract tests for the single-stock evidence endpoint."""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import stocks as stocks_endpoint


class _FakeStockEvidenceService:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[list[str]] = []

    def get_stock_evidence(self, symbols: list[str], **_: Any) -> dict[str, Any]:
        self.calls.append(symbols)
        return self.payload


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(stocks_endpoint.router, prefix="/api/v1/stocks")
    return TestClient(app)


def _base_payload(symbol: str = "AAPL") -> dict[str, Any]:
    return {
        "symbols": [symbol],
        "items": [
            {
                "symbol": symbol,
                "market": "US",
                "quote": {"status": "unknown", "provider": "realtime_quote"},
                "technical": {"status": "missing", "provider": "stock_daily"},
                "fundamental": {"status": "missing", "provider": "analysis_history"},
                "news": {"status": "unknown", "latestHeadline": None, "provider": None},
                "stockEvidencePacket": {
                    "schemaVersion": "stock_evidence_packet_v1",
                    "symbol": symbol,
                    "notInvestmentAdvice": True,
                    "observationOnly": True,
                },
            }
        ],
        "meta": {
            "generatedAt": "2026-06-02T00:00:00Z",
            "source": "read_only_evidence_v2",
        },
    }


def test_stock_evidence_endpoint_serializes_fundamentals_summary(
    monkeypatch,
) -> None:
    payload = _base_payload()
    payload["items"][0]["stockEvidencePacket"]["fundamentalsSummary"] = {
        "status": "available",
        "marketCap": 2800000000000,
        "peTtm": 28.5,
        "pb": 36.2,
        "beta": 1.1,
        "revenueTtm": 390000000000,
        "netIncomeTtm": 97000000000,
        "fcfTtm": 90000000000,
        "grossMargin": 0.44,
        "operatingMargin": 0.31,
        "roe": 1.01,
        "roa": 0.58,
        "period": "mixed",
        "source": "analysis_history",
        "freshness": "unknown",
        "missingFields": [],
        "notInvestmentAdvice": True,
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "sourceAuthorityAllowed": False,
    }
    fake_service = _FakeStockEvidenceService(payload)
    monkeypatch.setattr(
        stocks_endpoint,
        "StockEvidenceService",
        lambda: fake_service,
        raising=False,
    )

    response = _client().get("/api/v1/stocks/AAPL/evidence")

    assert response.status_code == 200
    data = response.json()
    assert fake_service.calls == [["AAPL"]]
    summary = data["items"][0]["stockEvidencePacket"]["fundamentalsSummary"]
    assert summary["marketCap"] == 2800000000000
    assert summary["peTtm"] == 28.5
    assert summary["grossMargin"] == 0.44
    assert summary["operatingMargin"] == 0.31
    assert summary["roe"] == 1.01
    assert summary["roa"] == 0.58
    assert summary["notInvestmentAdvice"] is True
    assert summary["observationOnly"] is True
    assert summary["scoreContributionAllowed"] is False
    assert summary["sourceAuthorityAllowed"] is False


def test_stock_evidence_endpoint_does_not_fabricate_missing_fundamentals_summary(
    monkeypatch,
) -> None:
    fake_service = _FakeStockEvidenceService(_base_payload())
    monkeypatch.setattr(
        stocks_endpoint,
        "StockEvidenceService",
        lambda: fake_service,
        raising=False,
    )

    response = _client().get("/api/v1/stocks/AAPL/evidence")

    assert response.status_code == 200
    packet = response.json()["items"][0]["stockEvidencePacket"]
    assert "fundamentalsSummary" not in packet


def test_stock_evidence_endpoint_filters_forbidden_fundamentals_fields(
    monkeypatch,
) -> None:
    payload = _base_payload()
    payload["items"][0]["stockEvidencePacket"]["fundamentalsSummary"] = {
        "status": "available",
        "marketCap": 2800000000000,
        "source": "analysis_history",
        "freshness": "unknown",
        "missingFields": [],
        "notInvestmentAdvice": True,
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "sourceAuthorityAllowed": False,
        "rawProviderPayload": {"token": "must-not-emit"},
        "adminDiagnostics": {"providerRoute": "must-not-emit"},
        "providerRoute": "must-not-emit",
        "valuationOpinion": "must-not-emit",
        "buyAdvice": "must-not-emit",
        "sellAdvice": "must-not-emit",
        "undervaluedAdvice": "must-not-emit",
        "overvaluedAdvice": "must-not-emit",
    }
    fake_service = _FakeStockEvidenceService(payload)
    monkeypatch.setattr(
        stocks_endpoint,
        "StockEvidenceService",
        lambda: fake_service,
        raising=False,
    )

    response = _client().get("/api/v1/stocks/AAPL/evidence")

    assert response.status_code == 200
    summary = response.json()["items"][0]["stockEvidencePacket"]["fundamentalsSummary"]
    serialized = json.dumps(summary, sort_keys=True)
    for forbidden_key in (
        "rawProviderPayload",
        "adminDiagnostics",
        "providerRoute",
        "valuationOpinion",
        "buyAdvice",
        "sellAdvice",
        "undervaluedAdvice",
        "overvaluedAdvice",
        "must-not-emit",
    ):
        assert forbidden_key not in summary
        assert forbidden_key not in serialized
    assert summary["notInvestmentAdvice"] is True
    assert summary["observationOnly"] is True
    assert summary["scoreContributionAllowed"] is False
    assert summary["sourceAuthorityAllowed"] is False


def test_stock_evidence_endpoint_returns_not_found_for_invalid_symbol_payload(
    monkeypatch,
) -> None:
    fake_service = _FakeStockEvidenceService(
        {
            "symbols": [],
            "items": [],
            "meta": {
                "generatedAt": "2026-06-02T00:00:00Z",
                "source": "read_only_evidence_v2",
            },
        }
    )
    monkeypatch.setattr(
        stocks_endpoint,
        "StockEvidenceService",
        lambda: fake_service,
        raising=False,
    )

    response = _client().get("/api/v1/stocks/HK/evidence")

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "not_found"


def test_stock_evidence_endpoint_preserves_unknown_symbol_degraded_payload(
    monkeypatch,
) -> None:
    payload = _base_payload(symbol="UNKNOWN1")
    fake_service = _FakeStockEvidenceService(payload)
    monkeypatch.setattr(
        stocks_endpoint,
        "StockEvidenceService",
        lambda: fake_service,
        raising=False,
    )

    response = _client().get("/api/v1/stocks/UNKNOWN1/evidence")

    assert response.status_code == 200
    data = response.json()
    assert data["symbols"] == ["UNKNOWN1"]
    assert data["items"][0]["symbol"] == "UNKNOWN1"
    assert data["items"][0]["quote"]["status"] == "unknown"
    assert data["items"][0]["fundamental"]["status"] == "missing"
