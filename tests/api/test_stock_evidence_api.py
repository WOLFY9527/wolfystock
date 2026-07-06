# -*- coding: utf-8 -*-
"""HTTP contract tests for the single-stock evidence endpoint."""

from __future__ import annotations

import json
from typing import Any
from types import SimpleNamespace

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


def _assert_no_forbidden_keys(value: Any, forbidden_keys: tuple[str, ...]) -> None:
    normalized_forbidden = {
        "".join(ch for ch in key.lower() if ch.isalnum())
        for key in forbidden_keys
    }
    found: list[str] = []

    def walk(node: Any, path: str = "$") -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                normalized_key = "".join(ch for ch in str(key).lower() if ch.isalnum())
                child_path = f"{path}.{key}"
                if normalized_key in normalized_forbidden:
                    found.append(child_path)
                walk(child, child_path)
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{path}[{index}]")

    walk(value)
    assert found == []


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


def test_stock_evidence_endpoint_serializes_symbol_evidence_readiness(
    monkeypatch,
) -> None:
    payload = _base_payload()
    payload["items"][0]["symbolEvidenceReadiness"] = {
        "symbolEvidenceReadiness": True,
        "symbol": "AAPL",
        "readinessTier": "partial",
        "evidenceUsed": ["quote", "fundamental"],
        "evidenceMissing": ["technical", "news"],
        "staleInputs": ["quote"],
        "conflictingEvidence": [],
        "dataQualityNotes": [
            "已返回部分标的证据，但仍有关键缺口，暂不形成完整研究交接。",
        ],
        "suggestedResearchPath": [
            "Add recent OHLC or technical context.",
            "Add recent news or filing context before catalyst review.",
        ],
        "observationOnly": True,
        "noAdviceDisclosure": "仅供研究观察，不构成个性化行动指令。",
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
    readiness = response.json()["items"][0]["symbolEvidenceReadiness"]
    assert readiness["symbolEvidenceReadiness"] is True
    assert readiness["symbol"] == "AAPL"
    assert readiness["readinessTier"] == "partial"
    assert readiness["evidenceUsed"] == ["quote", "fundamental"]
    assert readiness["evidenceMissing"] == ["technical", "news"]
    assert readiness["staleInputs"] == ["quote"]
    assert readiness["conflictingEvidence"] == []
    assert readiness["observationOnly"] is True
    assert readiness["noAdviceDisclosure"] == "仅供研究观察，不构成个性化行动指令。"


def test_stock_evidence_endpoint_projects_product_read_model_for_stale_precise_technicals(
    monkeypatch,
) -> None:
    payload = _base_payload()
    payload["items"][0]["quote"] = {
        "status": "available",
        "freshness": "stale",
        "asOf": "2026-06-01",
        "isStale": True,
        "price": 192.34,
    }
    payload["items"][0]["technical"] = {
        "status": "available",
        "freshness": "stale",
        "asOf": "2026-06-01",
        "isStale": True,
        "rsi14": 62.5,
        "ma20": 188.4,
        "ma50": 180.2,
        "missingFields": [],
    }
    payload["items"][0]["fundamental"] = {
        "status": "partial",
        "freshness": "unknown",
        "missingFields": ["fcfTtm"],
    }
    payload["items"][0]["news"] = {
        "status": "unknown",
        "isUnavailable": True,
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
    assert item["technical"]["rsi14"] == 62.5
    assert item["technical"]["ma20"] == 188.4
    assert item["technical"]["ma50"] == 180.2
    read_model = item["productReadModel"]
    assert read_model["contractVersion"] == "product_read_model_v1"
    assert read_model["surface"] == "Stock Evidence"
    assert read_model["state"] == "stale"
    assert read_model["ready"] is False
    assert read_model["criticalChildStates"] == {
        "quote": "stale",
        "technical": "stale",
        "fundamental": "partial",
        "news": "unavailable",
    }
    assert read_model["freshness"]["state"] == "stale"
    assert read_model["freshness"]["asOf"] == "2026-06-01"
    assert read_model["provenance"]["sourceClass"] == "stock_evidence"
    assert read_model["provenance"]["asOf"] == "2026-06-01"
    assert read_model["evidence"]["blockers"] == ["news"]
    _assert_no_forbidden_keys(
        read_model,
        (
            "providerId",
            "providerName",
            "rawPayload",
            "records",
            "sourceConfidence",
        ),
    )


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
    assert "schemaVersion" not in packet
    assert packet["symbol"] == "AAPL"
    assert packet["notInvestmentAdvice"] is True
    assert packet["observationOnly"] is True
    assert packet["consumerSafeSourceLabel"] == "部分数据源暂不可用"
    assert packet["dataQualityState"] == "limited"
    assert packet["freshnessState"] == "limited"
    assert "fundamentalsSummary" not in packet
    _assert_no_forbidden_keys(
        packet,
        (
            "researchPacketV1",
            "researchPacket",
            "research_packet_v1",
            "runtimePosture",
            "dataCoverageRows",
            "lanes",
            "laneInternals",
            "laneDiagnostics",
        ),
    )


def test_stock_evidence_openapi_locks_item_metadata_schema() -> None:
    schema = _client().get("/openapi.json").json()["components"]["schemas"]

    item_schema = schema["StockEvidenceItemResponse"]["properties"]
    assert "symbolEvidenceReadiness" in item_schema
    assert item_schema["productReadModel"]["type"] == "object"

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
    assert "providerId" not in item["quote"]
    assert "providerName" not in item["quote"]
    assert "sourceType" not in item["quote"]
    assert "sourceTier" not in item["quote"]
    assert item["quote"]["trustLevel"] == "usable_with_caution"
    assert item["quote"]["freshness"] == "delayed"
    assert item["quote"]["updatedAt"] == "2026-06-02T09:31:00Z"
    assert item["quote"]["asOf"] == "2026-06-02"
    assert item["quote"]["degradationReason"] == "Freshness is constrained for this observation."
    assert item["quote"]["isFallback"] is True
    assert item["quote"]["isStale"] is True
    assert item["quote"]["isPartial"] is True
    assert item["quote"]["isSynthetic"] is False
    assert item["quote"]["isUnavailable"] is False
    assert "sourceConfidence" not in item["quote"]
    assert item["quote"]["observationOnly"] is True
    assert item["quote"]["scoreContributionAllowed"] is False
    assert item["quote"]["sourceAuthorityAllowed"] is False
    assert "rawPayloadStored" not in item["quote"]
    assert item["quote"]["freshnessExpectation"] == "near_real_time_venue_scoped"
    assert item["quote"]["extraHistoricalField"] == {"kept": True}
    assert item["technical"]["missingFields"] == ["rsi14", "support"]
    assert item["technical"]["extraTechnicalField"] == 42
    assert item["fundamental"]["missingFields"] == ["fcfTtm"]
    assert item["fundamental"]["extraFundamentalField"] == "preserved"
    assert item["news"]["isUnavailable"] is True
    assert "sourceType" not in item["secFilingEvidence"]
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
    for block_key in ("quote", "technical", "fundamental", "news"):
        assert "provider" not in item[block_key]
        assert item[block_key]["consumerSafeSourceLabel"] == "部分数据源暂不可用"
        assert item[block_key]["dataQualityState"] == "limited"
    assert item["quote"]["status"] == "unknown"
    assert item["technical"]["status"] == "missing"
    assert item["fundamental"]["status"] == "missing"
    assert item["news"]["status"] == "unknown"
    assert "latestHeadline" not in item["news"]


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
        "rawSourcePayload": {"provider": "must-not-emit"},
        "rawCachePayload": {"cacheKey": "must-not-emit"},
        "rawLaneInternals": {"lane": "must-not-emit"},
        "adminDiagnostics": {"providerRoute": "must-not-emit"},
        "providerRoute": "must-not-emit",
        "cacheDebug": {"cacheKey": "must-not-emit"},
        "reasonCode": "must-not-emit",
        "reasonFamilies": ["must-not-emit"],
        "backendTrace": "must-not-emit",
        "debugRef": "must-not-emit",
        "internalDiagnostics": {"backend": "must-not-emit"},
        "researchPacketV1": {"raw": "must-not-emit"},
        "researchPacket": {"raw": "must-not-emit"},
        "research_packet_v1": {"raw": "must-not-emit"},
        "runtimePosture": {"authorityGrant": "must-not-emit"},
        "dataCoverageRows": [{"lane": "must-not-emit"}],
        "lanes": {"fundamentals": {"status": "must-not-emit"}},
        "laneInternals": {"fundamentals": "must-not-emit"},
        "laneDiagnostics": {"fundamentals": "must-not-emit"},
        "sourceTier": "must-not-emit",
        "providerAuthority": "must-not-emit",
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
        "rawSourcePayload",
        "rawCachePayload",
        "rawLaneInternals",
        "adminDiagnostics",
        "providerRoute",
        "cacheDebug",
        "reasonCode",
        "reasonFamilies",
        "backendTrace",
        "debugRef",
        "internalDiagnostics",
        "researchPacketV1",
        "researchPacket",
        "research_packet_v1",
        "runtimePosture",
        "dataCoverageRows",
        "lanes",
        "laneInternals",
        "laneDiagnostics",
        "sourceTier",
        "providerAuthority",
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


def test_stock_evidence_endpoint_internal_error_is_consumer_safe(
    monkeypatch,
) -> None:
    raw_error = (
        "Traceback NameError _ReadOnlyEvidenceFetcherManager /srv/wolfystock/internal.py "
        "requestId=req-raw traceId=trace-raw cacheKey=cache-raw raw payload "
        "credential token API_KEY=secret"
    )

    class _FailingStockEvidenceService:
        quote_adapter = SimpleNamespace(fetcher_manager=object())
        fetcher_manager = object()

        def get_stock_evidence(self, symbols: list[str], **_: Any) -> dict[str, Any]:
            raise RuntimeError(raw_error)

    monkeypatch.setattr(
        stocks_endpoint,
        "StockEvidenceService",
        _FailingStockEvidenceService,
        raising=False,
    )

    response = _client().get("/api/v1/stocks/ORCL/evidence")

    assert response.status_code == 500
    payload = response.json()["detail"]
    assert payload["error"] == "internal_error"
    assert payload["message"] == "Stock evidence is temporarily unavailable. Please retry later."
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for marker in (
        "Traceback",
        "NameError",
        "_ReadOnlyEvidenceFetcherManager",
        "/srv/wolfystock/internal.py",
        "requestId",
        "traceId",
        "cacheKey",
        "raw payload",
        "credential",
        "token",
        "API_KEY",
        "secret",
    ):
        assert marker not in serialized


def test_stock_evidence_endpoint_preserves_quote_diagnostic_metadata_and_readonly_seam(
    monkeypatch,
) -> None:
    instances: list[Any] = []

    class _FakeServiceWithQuoteSeam:
        def __init__(self) -> None:
            self.quote_adapter = SimpleNamespace(fetcher_manager=object())
            self.fetcher_manager = object()
            self.calls: list[list[str]] = []
            instances.append(self)

        def get_stock_evidence(self, symbols: list[str], **_: Any) -> dict[str, Any]:
            self.calls.append(symbols)
            assert type(self.quote_adapter.fetcher_manager).__name__ == "_ReadOnlyEvidenceFetcherManager"
            assert type(self.fetcher_manager).__name__ == "_ReadOnlyEvidenceFetcherManager"
            payload = _base_payload(symbols[0])
            payload["items"][0]["quote"] = {
                "status": "available",
                "price": 214.55,
                "changePct": 1.23,
                "currency": "USD",
                "provider": "alpaca",
                "updatedAt": "2026-05-13T08:30:00Z",
                "source": "alpaca",
                "sourceType": "local_or_reported",
                "freshness": "unknown",
                "asOf": "2026-05-13T08:30:00Z",
                "degradationReason": "freshness_not_proven",
                "isFallback": False,
                "isStale": False,
                "isPartial": False,
                "isSynthetic": False,
                "isUnavailable": False,
                "observationOnly": True,
                "scoreContributionAllowed": False,
                "sourceAuthorityAllowed": False,
                "rawPayloadStored": False,
                "sourceConfidence": {
                    "source": "alpaca",
                    "sourceLabel": "alpaca",
                    "asOf": "2026-05-13T08:30:00Z",
                    "freshness": "unknown",
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": False,
                    "isSynthetic": False,
                    "isUnavailable": False,
                    "confidenceWeight": 0.3,
                    "coverage": 1.0,
                    "degradationReason": "freshness_not_proven",
                    "capReason": "freshness_not_proven",
                },
            }
            return payload

    monkeypatch.setattr(
        stocks_endpoint,
        "StockEvidenceService",
        _FakeServiceWithQuoteSeam,
        raising=False,
    )

    response = _client().get("/api/v1/stocks/AAPL/evidence")

    assert response.status_code == 200
    assert len(instances) == 1
    assert instances[0].calls == [["AAPL"]]
    quote = response.json()["items"][0]["quote"]
    assert "provider" not in quote
    assert quote["source"] == "alpaca"
    assert "sourceType" not in quote
    assert quote["consumerSafeSourceLabel"] == "部分数据源暂不可用"
    assert quote["dataQualityState"] == "limited"
    assert quote["freshness"] == "unknown"
    assert quote["asOf"] == "2026-05-13T08:30:00Z"
    assert quote["isFallback"] is False
    assert quote["isStale"] is False
    assert quote["isPartial"] is False
    assert quote["isSynthetic"] is False
    assert quote["isUnavailable"] is False
    assert quote["observationOnly"] is True
    assert quote["scoreContributionAllowed"] is False
    assert quote["sourceAuthorityAllowed"] is False
    assert "rawPayloadStored" not in quote
    assert "sourceConfidence" not in quote
    for deferred_key in (
        "providerId",
        "sourceTier",
        "trustLevel",
        "freshnessExpectation",
        "readinessState",
        "authorityGrant",
    ):
        assert deferred_key not in quote
