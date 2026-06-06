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


def test_stock_evidence_openapi_locks_item_metadata_schema() -> None:
    schema = _client().get("/openapi.json").json()["components"]["schemas"]

    item_schema = schema["StockEvidenceItemResponse"]["properties"]

    for block_key in ("quote", "technical", "fundamental", "news", "secFilingEvidence"):
        metadata_schema = next(
            option
            for option in item_schema[block_key]["anyOf"]
            if option.get("type") == "object"
        )
        assert metadata_schema["additionalProperties"] is True
        metadata_properties = metadata_schema["properties"]
        for field_name in (
            "status",
            "provider",
            "providerId",
            "providerName",
            "source",
            "sourceType",
            "sourceTier",
            "trustLevel",
            "freshness",
            "updatedAt",
            "asOf",
            "degradationReason",
            "isFallback",
            "isStale",
            "isPartial",
            "isSynthetic",
            "isUnavailable",
            "sourceConfidence",
            "observationOnly",
            "scoreContributionAllowed",
            "sourceAuthorityAllowed",
            "rawPayloadStored",
            "missingFields",
            "freshnessExpectation",
            "records",
        ):
            assert field_name in metadata_properties


def test_stock_evidence_endpoint_preserves_item_metadata_shape(
    monkeypatch,
) -> None:
    payload = _base_payload()
    payload["items"][0]["quote"] = {
        "status": "available",
        "provider": "existing_quote_adapter",
        "providerId": "quote-primary",
        "providerName": "Existing Quote Adapter",
        "source": "existing_quote_source",
        "sourceType": "provider_runtime",
        "sourceTier": "exchange_public",
        "trustLevel": "usable_with_caution",
        "freshness": "delayed",
        "updatedAt": "2026-06-02T09:31:00Z",
        "asOf": "2026-06-02",
        "degradationReason": "delayed_source",
        "isFallback": True,
        "isStale": True,
        "isPartial": True,
        "isSynthetic": False,
        "isUnavailable": False,
        "sourceConfidence": {
            "confidenceWeight": 0.7,
            "capReason": "delayed_source",
        },
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "sourceAuthorityAllowed": False,
        "rawPayloadStored": False,
        "freshnessExpectation": "near_real_time_venue_scoped",
        "extraHistoricalField": {"kept": True},
    }
    payload["items"][0]["technical"] = {
        "status": "partial",
        "provider": "stock_daily",
        "isPartial": True,
        "missingFields": ["rsi14", "support"],
        "extraTechnicalField": 42,
    }
    payload["items"][0]["fundamental"] = {
        "status": "partial",
        "provider": "analysis_history",
        "missingFields": ["fcfTtm"],
        "freshness": "unknown",
        "extraFundamentalField": "preserved",
    }
    payload["items"][0]["news"] = {
        "status": "unknown",
        "provider": None,
        "isUnavailable": True,
        "degradationReason": "news_unavailable",
    }
    payload["items"][0]["secFilingEvidence"] = {
        "status": "available",
        "provider": "sec_company_facts",
        "sourceType": "official_filing",
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "sourceAuthorityAllowed": False,
        "rawPayloadStored": False,
        "records": [{"form": "10-K", "filedAt": "2026-02-01"}],
        "extraSecField": "preserved",
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
    item = response.json()["items"][0]
    assert item["quote"]["providerId"] == "quote-primary"
    assert item["quote"]["providerName"] == "Existing Quote Adapter"
    assert item["quote"]["sourceType"] == "provider_runtime"
    assert item["quote"]["sourceTier"] == "exchange_public"
    assert item["quote"]["trustLevel"] == "usable_with_caution"
    assert item["quote"]["freshness"] == "delayed"
    assert item["quote"]["updatedAt"] == "2026-06-02T09:31:00Z"
    assert item["quote"]["asOf"] == "2026-06-02"
    assert item["quote"]["degradationReason"] == "delayed_source"
    assert item["quote"]["isFallback"] is True
    assert item["quote"]["isStale"] is True
    assert item["quote"]["isPartial"] is True
    assert item["quote"]["isSynthetic"] is False
    assert item["quote"]["isUnavailable"] is False
    assert item["quote"]["sourceConfidence"]["confidenceWeight"] == 0.7
    assert item["quote"]["observationOnly"] is True
    assert item["quote"]["scoreContributionAllowed"] is False
    assert item["quote"]["sourceAuthorityAllowed"] is False
    assert item["quote"]["rawPayloadStored"] is False
    assert item["quote"]["freshnessExpectation"] == "near_real_time_venue_scoped"
    assert item["quote"]["extraHistoricalField"] == {"kept": True}
    assert item["technical"]["missingFields"] == ["rsi14", "support"]
    assert item["technical"]["extraTechnicalField"] == 42
    assert item["fundamental"]["missingFields"] == ["fcfTtm"]
    assert item["fundamental"]["extraFundamentalField"] == "preserved"
    assert item["news"]["isUnavailable"] is True
    assert item["secFilingEvidence"]["sourceType"] == "official_filing"
    assert item["secFilingEvidence"]["records"] == [{"form": "10-K", "filedAt": "2026-02-01"}]
    assert item["secFilingEvidence"]["extraSecField"] == "preserved"


def test_stock_evidence_endpoint_does_not_fabricate_item_metadata(
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
    item = response.json()["items"][0]
    assert item["quote"] == {"status": "unknown", "provider": "realtime_quote"}
    assert item["technical"] == {"status": "missing", "provider": "stock_daily"}
    assert item["fundamental"] == {"status": "missing", "provider": "analysis_history"}
    assert item["news"] == {"status": "unknown", "latestHeadline": None, "provider": None}


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
