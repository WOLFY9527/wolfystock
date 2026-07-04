# -*- coding: utf-8 -*-
"""HTTP contract tests for the stock structure decision endpoint."""

from __future__ import annotations

import json
import threading
import time
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import stocks as stocks_endpoint
from src.services import symbol_research_packet_service
from src.services.stock_structure_decision_service import (
    STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION,
    StockStructureDecisionService,
)


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


class _FakeStockService:
    def __init__(self, *, quote: dict[str, Any] | None, history: dict[str, Any]) -> None:
        self.quote = quote
        self.history = history
        self.quote_calls: list[str] = []
        self.history_calls: list[dict[str, Any]] = []

    def get_realtime_quote(self, stock_code: str) -> dict[str, Any] | None:
        self.quote_calls.append(stock_code)
        return self.quote

    def get_history_data(self, stock_code: str, period: str = "daily", days: int = 30) -> dict[str, Any]:
        self.history_calls.append({"stock_code": stock_code, "period": period, "days": days})
        return self.history


class _FakeStockEvidenceService:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.quote_adapter = SimpleNamespace(fetcher_manager=object())
        self.fetcher_manager = object()
        self.calls: list[list[str]] = []

    def get_stock_evidence(self, symbols: list[str], **_: Any) -> dict[str, Any]:
        self.calls.append(symbols)
        return self.payload


class _NoUSFundamentalsService:
    def get_us_fundamentals(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "state": "not_configured",
            "fieldsAvailable": [],
            "missingFieldReasons": {},
        }


class _BlockingHistoryService:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls: list[dict[str, Any]] = []

    def get_history_data(self, stock_code: str, period: str = "daily", days: int = 30) -> dict[str, Any]:
        self.calls.append({"stock_code": stock_code, "period": period, "days": days})
        self.started.set()
        self.release.wait(timeout=2.0)
        return _history_payload()


class _BlockingPeerRepository:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def get_local_peer_group(self, symbol: str) -> dict[str, Any] | None:
        del symbol
        self.started.set()
        self.release.wait(timeout=2.0)
        return {"label": "local verified peers", "symbols": ["MSFT", "NVDA"]}


def _regular_user() -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="alice",
        display_name="Alice",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


def _raise_unauthorized() -> None:
    raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Login required"})


def _client(*, authenticated: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(stocks_endpoint.router, prefix="/api/v1/stocks")
    app.dependency_overrides[get_current_user] = _regular_user if authenticated else _raise_unauthorized
    return TestClient(app)


def _payload(
    *,
    ticker: str = "AAPL",
    structure_state: str = "breakout",
    confidence: str = "high",
    data_status: str = "available",
    missing_evidence: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    usable_bars = 120 if data_status == "available" else 0
    required_bars = 90
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
            "observedBars": usable_bars,
            "usableBars": usable_bars,
            "reason": "history_available" if data_status == "available" else "history_unavailable",
        },
        "historicalOhlcvReadiness": {
            "contractVersion": "historical_ohlcv_readiness_v1",
            "symbol": ticker,
            "market": "unknown",
            "timeframe": "1d",
            "requestedRange": {"start": None, "end": None},
            "lookbackBars": 90,
            "requiredBars": required_bars,
            "usableBars": usable_bars,
            "missingBars": max(0, required_bars - usable_bars),
            "freshnessState": "unknown",
            "adjustmentState": "not_required",
            "benchmarkState": "not_requested",
            "providerState": "available" if data_status == "available" else "provider_missing",
            "overallState": "ready" if data_status == "available" else "blocked",
            "missingRequirements": [] if data_status == "available" else ["provider_missing", "insufficient_history"],
            "consumerSafe": True,
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
            "missingInputs": ["同业对比信息待确认。"],
            "confidenceCap": "low",
            "observationBoundary": "Observation-only peer movement context; no personalized action instruction.",
            "researchNextSteps": [
                "补齐本地同业分组后再复核同业走势。",
                "补齐标的及至少两个同业的近期日线数据。",
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


def _history_payload(*, status: str = "ok", source: str = "local_db", rows: int = 2) -> dict[str, Any]:
    data = [
        {"date": "2026-05-27", "open": 210.0, "high": 215.0, "low": 209.0, "close": 214.0, "volume": 1000.0},
        {"date": "2026-05-28", "open": 214.0, "high": 216.0, "low": 213.0, "close": 215.0, "volume": 1200.0},
    ][:rows]
    return {
        "stock_code": "AAPL",
        "stock_name": "Apple",
        "period": "daily",
        "data": data,
        "source": source,
        "diagnostics": {
            "status": status,
            "reason": "history_available" if data else "history_unavailable",
            "rows": len(data),
        },
        "sourceConfidence": {
            "freshness": "fresh" if status == "ok" else "unavailable",
            "isFallback": False,
            "isStale": False,
            "isPartial": False,
            "isSynthetic": False,
            "isUnavailable": not data,
        },
    }


def _history_payload_with_valid_rows(*, rows: int, source: str = "local_db") -> dict[str, Any]:
    data = []
    for index in range(rows):
        bar_date = date(2026, 1, 1) + timedelta(days=index)
        close = 100.0 + index * 0.5
        data.append(
            {
                "date": bar_date.isoformat(),
                "open": round(close - 0.2, 4),
                "high": round(close + 0.5, 4),
                "low": round(close - 0.5, 4),
                "close": round(close, 4),
                "volume": 1000.0 + index,
            }
        )
    return {
        "stock_code": "AAPL",
        "stock_name": "Apple",
        "period": "daily",
        "data": data,
        "source": source,
        "diagnostics": {"status": "ok", "reason": "history_available", "rows": len(data)},
    }


def _evidence_payload(symbol: str = "AAPL") -> dict[str, Any]:
    return {
        "symbols": [symbol],
        "items": [
            {
                "symbol": symbol,
                "market": "us",
                "fundamental": {"status": "missing", "missingFields": ["marketCap", "peTtm"]},
                "news": {"status": "missing"},
                "secFilingEvidence": {"status": "missing", "records": []},
                "stockEvidencePacket": {
                    "symbol": symbol,
                    "notInvestmentAdvice": True,
                    "observationOnly": True,
                },
            }
        ],
    }


def test_research_packet_endpoint_assembles_existing_data_and_missing_families(monkeypatch) -> None:
    fake_stock = _FakeStockService(
        quote={
            "stock_code": "AAPL",
            "stock_name": "Apple",
            "current_price": 214.55,
            "change_percent": 1.11,
            "market_timestamp": "2026-05-28T09:30:00Z",
            "observed_at": "2026-05-28T09:31:00Z",
            "freshness": "live",
            "is_fallback": False,
            "is_stale": False,
            "is_partial": False,
            "is_synthetic": False,
        },
        history=_history_payload(),
    )
    fake_structure = _FakeStructureDecisionService(_payload())
    fake_evidence = _FakeStockEvidenceService(_evidence_payload())
    monkeypatch.setattr(symbol_research_packet_service, "StockService", lambda: fake_stock, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "StockStructureDecisionService", lambda: fake_structure, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "StockEvidenceService", lambda: fake_evidence, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "USFundamentalsService", lambda: _NoUSFundamentalsService(), raising=False)

    response = _client().get("/api/v1/stocks/AAPL/research-packet", params={"market": "us"})

    assert response.status_code == 200
    payload = response.json()
    assert fake_stock.quote_calls == ["AAPL"]
    assert fake_stock.history_calls == [{"stock_code": "AAPL", "period": "daily", "days": 90}]
    assert fake_structure.calls[0]["ticker"] == "AAPL"
    assert fake_evidence.calls == [["AAPL"]]
    assert payload["symbol"] == "AAPL"
    assert payload["market"] == "us"
    assert payload["identity"] == {"name": "Apple", "exchange": None, "sector": None, "industry": None}
    assert payload["quote"] == {
        "state": "available",
        "price": 214.55,
        "changePercent": 1.11,
        "asOf": "2026-05-28T09:30:00Z",
    }
    assert payload["history"] == {
        "state": "available",
        "bars": 2,
        "period": "daily",
        "asOf": "2026-05-28",
    }
    assert payload["structure"]["state"] == "available"
    assert payload["structure"]["label"] == "breakout"
    assert payload["structure"]["confidence"] == "high"
    assert payload["fundamentals"]["state"] == "missing"
    assert payload["fundamentals"]["readinessState"] == "missing"
    assert payload["fundamentals"]["fieldsAvailable"] == []
    assert payload["fundamentals"]["missingFields"]["valuation"] == ["marketCap", "peTtm", "pb", "beta"]
    assert payload["events"] == {"state": "missing", "latest": []}
    assert payload["peer"] == {"state": "missing", "benchmark": None}
    assert payload["missingData"] == ["fundamentals", "filing_event_catalyst", "peer_benchmark"]
    assert payload["researchStatus"] == "partial"
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert payload["noAdviceDisclosure"] == "Observation-only research packet; no personalized action instruction."
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in FORBIDDEN_ADVICE_TOKENS:
        assert forbidden not in serialized
    for raw_key in ("sourceType", "sourceConfidence", "providerName", "providerClass", "providerAttempted", "cacheKey", "traceId", "requestId"):
        assert raw_key not in json.dumps(payload, ensure_ascii=False)


def test_research_packet_endpoint_exposes_fundamentals_readiness_contract(monkeypatch) -> None:
    fake_stock = _FakeStockService(
        quote={
            "stock_code": "AAPL",
            "stock_name": "Apple",
            "current_price": 214.55,
            "change_percent": 1.11,
            "market_timestamp": "2026-05-28T09:30:00Z",
            "freshness": "live",
        },
        history=_history_payload(),
    )
    fake_structure = _FakeStructureDecisionService(_payload())
    evidence_payload = _evidence_payload()
    evidence_payload["items"][0]["fundamental"] = {
        "status": "partial",
        "marketCap": 2800000000000,
        "peTtm": 28.5,
        "freshness": "stale",
        "missingFields": ["revenueTtm", "grossMargin", "earningsDate"],
        "providerName": "must-not-emit",
        "requestId": "req-must-not-emit",
        "rawPayload": {"token": "must-not-emit"},
    }
    evidence_payload["items"][0]["stockEvidencePacket"]["fundamentalsSummary"] = {
        "status": "partial",
        "marketCap": 2800000000000,
        "peTtm": 28.5,
        "freshness": "stale",
        "missingFields": ["revenueTtm", "grossMargin", "earningsDate"],
        "notInvestmentAdvice": True,
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "sourceAuthorityAllowed": False,
    }
    fake_evidence = _FakeStockEvidenceService(evidence_payload)
    monkeypatch.setattr(symbol_research_packet_service, "StockService", lambda: fake_stock, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "StockStructureDecisionService", lambda: fake_structure, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "StockEvidenceService", lambda: fake_evidence, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "USFundamentalsService", lambda: _NoUSFundamentalsService(), raising=False)

    response = _client().get("/api/v1/stocks/AAPL/research-packet", params={"market": "us"})

    assert response.status_code == 200
    fundamentals = response.json()["fundamentals"]
    assert fundamentals["state"] == "stale"
    assert fundamentals["readinessState"] == "stale"
    assert fundamentals["fieldsAvailable"] == ["marketCap", "peTtm"]
    assert fundamentals["supportedFields"]["valuation"] == ["marketCap", "peTtm", "pb", "beta"]
    assert fundamentals["availableFields"]["valuation"] == ["marketCap", "peTtm"]
    assert fundamentals["missingFields"]["financialStatements"] == ["revenueTtm", "netIncomeTtm", "fcfTtm"]
    assert fundamentals["missingFields"]["margins"] == ["grossMargin", "operatingMargin", "roe", "roa"]
    assert fundamentals["missingFields"]["balanceSheet"] == ["totalDebt", "cashAndEquivalents", "totalAssets", "totalLiabilities"]
    assert fundamentals["missingFields"]["earnings"] == ["earningsDate", "epsTtm", "revenueGrowth"]
    assert fundamentals["categories"]["companyProfile"]["state"] == "missing"
    assert fundamentals["categories"]["valuation"]["state"] == "stale"
    assert fundamentals["categories"]["financialStatements"]["state"] == "missing"
    assert fundamentals["categories"]["earnings"]["state"] == "missing"
    assert fundamentals["providerNeutralNextDataAction"] == (
        "Connect a fundamentals data path for company profile, financial statements, valuation, earnings, and ownership or flow fields."
    )
    assert "基本面数据缺失" in fundamentals["consumerSafeCopy"]
    serialized = json.dumps(response.json(), ensure_ascii=False)
    for forbidden in (
        "providerName",
        "providerClass",
        "providerAttempted",
        "apiKey",
        "token",
        "credential",
        "env",
        "requestId",
        "traceId",
        "cacheKey",
        "rawPayload",
        "exceptionClass",
        "Traceback",
        "stack",
        "buy",
        "sell",
        "hold",
        "recommendation",
        "target",
        "stop",
        "position",
    ):
        assert forbidden not in serialized


def test_research_packet_endpoint_marks_fundamentals_not_configured(monkeypatch) -> None:
    fake_stock = _FakeStockService(quote=None, history=_history_payload(status="unavailable", source="unavailable", rows=0))
    fake_structure = _FakeStructureDecisionService(_payload(data_status="unavailable"))
    fake_evidence = _FakeStockEvidenceService({"symbols": [], "items": []})
    monkeypatch.setattr(symbol_research_packet_service, "StockService", lambda: fake_stock, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "StockStructureDecisionService", lambda: fake_structure, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "StockEvidenceService", lambda: fake_evidence, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "USFundamentalsService", lambda: _NoUSFundamentalsService(), raising=False)

    response = _client().get("/api/v1/stocks/AAPL/research-packet", params={"market": "us"})

    assert response.status_code == 200
    fundamentals = response.json()["fundamentals"]
    assert fundamentals["state"] == "not_configured"
    assert fundamentals["readinessState"] == "not_configured"
    assert fundamentals["availableFields"]["valuation"] == []
    assert fundamentals["missingFields"]["companyProfile"] == ["companyName", "sector", "industry", "exchange", "country"]
    assert fundamentals["consumerSafeCopy"] == "基本面数据路径尚未配置，暂不展示财务或估值指标。"


def test_research_packet_endpoint_marks_fundamentals_permission_blocked(monkeypatch) -> None:
    fake_stock = _FakeStockService(quote=None, history=_history_payload(status="unavailable", source="unavailable", rows=0))
    fake_structure = _FakeStructureDecisionService(_payload(data_status="unavailable"))
    evidence_payload = _evidence_payload()
    evidence_payload["items"][0]["fundamental"] = {
        "status": "insufficient_permissions",
        "missingFields": ["marketCap", "revenueTtm", "earningsDate"],
        "providerClass": "must-not-emit",
        "credential": "must-not-emit",
    }
    fake_evidence = _FakeStockEvidenceService(evidence_payload)
    monkeypatch.setattr(symbol_research_packet_service, "StockService", lambda: fake_stock, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "StockStructureDecisionService", lambda: fake_structure, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "StockEvidenceService", lambda: fake_evidence, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "USFundamentalsService", lambda: _NoUSFundamentalsService(), raising=False)

    response = _client().get("/api/v1/stocks/AAPL/research-packet", params={"market": "us"})

    assert response.status_code == 200
    payload = response.json()
    fundamentals = payload["fundamentals"]
    assert fundamentals["state"] == "insufficient_permissions"
    assert fundamentals["readinessState"] == "insufficient_permissions"
    assert fundamentals["blockedFields"]["valuation"] == ["marketCap"]
    assert fundamentals["blockedFields"]["financialStatements"] == ["revenueTtm"]
    assert fundamentals["blockedFields"]["earnings"] == ["earningsDate"]
    assert fundamentals["consumerSafeCopy"] == "基本面数据权限不足，暂不展示财务或估值指标。"
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "providerClass" not in serialized
    assert "credential" not in serialized


def test_research_packet_endpoint_marks_fundamentals_available_without_fake_missing(monkeypatch) -> None:
    fake_stock = _FakeStockService(quote=None, history=_history_payload())
    fake_structure = _FakeStructureDecisionService(_payload())
    evidence_payload = _evidence_payload()
    evidence_payload["items"][0]["fundamental"] = {
        "status": "available",
        "marketCap": 2800000000000,
        "peTtm": 28.5,
        "pb": 36.2,
        "beta": 1.1,
    }
    evidence_payload["items"][0]["stockEvidencePacket"]["fundamentalsSummary"] = {
        "status": "available",
        "marketCap": 2800000000000,
        "peTtm": 28.5,
        "pb": 36.2,
        "beta": 1.1,
        "missingFields": [],
        "notInvestmentAdvice": True,
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "sourceAuthorityAllowed": False,
    }
    fake_evidence = _FakeStockEvidenceService(evidence_payload)
    monkeypatch.setattr(symbol_research_packet_service, "StockService", lambda: fake_stock, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "StockStructureDecisionService", lambda: fake_structure, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "StockEvidenceService", lambda: fake_evidence, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "USFundamentalsService", lambda: _NoUSFundamentalsService(), raising=False)

    response = _client().get("/api/v1/stocks/AAPL/research-packet", params={"market": "us"})

    assert response.status_code == 200
    fundamentals = response.json()["fundamentals"]
    assert fundamentals["state"] == "available"
    assert fundamentals["readinessState"] == "available"
    assert fundamentals["availableFields"]["valuation"] == ["marketCap", "peTtm", "pb", "beta"]
    assert fundamentals["missingFields"]["valuation"] == []
    assert fundamentals["categories"]["valuation"]["state"] == "available"
    assert "revenueTtm" not in fundamentals["availableFields"]["financialStatements"]


def test_research_packet_endpoint_uses_us_fundamentals_service_for_company_context(monkeypatch) -> None:
    fake_stock = _FakeStockService(
        quote={
            "stock_code": "AAPL",
            "stock_name": "Apple",
            "current_price": 214.55,
            "change_percent": 1.11,
            "market_timestamp": "2026-05-28T09:30:00Z",
            "freshness": "live",
        },
        history=_history_payload(),
    )
    fake_structure = _FakeStructureDecisionService(_payload())
    fake_evidence = _FakeStockEvidenceService(_evidence_payload())

    class _FakeUSFundamentalsService:
        calls: list[str] = []

        def get_us_fundamentals(self, symbol: str) -> dict[str, Any]:
            self.calls.append(symbol)
            return {
                "symbol": symbol,
                "state": "partial",
                "companyName": "Apple Inc.",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "marketCap": 3_000_000_000_000.0,
                "revenueTtm": 390_000_000_000.0,
                "profitabilityMargin": 0.31,
                "valuationRatio": 29.4,
                "fiscalPeriod": "mixed",
                "asOf": "2026-07-01T00:00:00+00:00",
                "source": "yfinance",
                "freshness": "current",
                "fieldsAvailable": [
                    "companyName",
                    "sector",
                    "industry",
                    "marketCap",
                    "revenueTtm",
                    "profitabilityMargin",
                    "valuationRatio",
                ],
                "missingFieldReasons": {
                    "companyName": "",
                    "sector": "",
                    "industry": "",
                    "marketCap": "",
                    "revenueTtm": "",
                    "profitabilityMargin": "",
                    "valuationRatio": "",
                    "fiscalPeriod": "mixed_periods",
                    "asOf": "",
                    "source": "",
                    "freshness": "",
                },
            }

    fake_us_fundamentals = _FakeUSFundamentalsService()
    monkeypatch.setattr(symbol_research_packet_service, "StockService", lambda: fake_stock, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "StockStructureDecisionService", lambda: fake_structure, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "StockEvidenceService", lambda: fake_evidence, raising=False)
    monkeypatch.setattr(
        symbol_research_packet_service,
        "USFundamentalsService",
        lambda: fake_us_fundamentals,
        raising=False,
    )

    response = _client().get("/api/v1/stocks/AAPL/research-packet", params={"market": "us"})

    assert response.status_code == 200
    payload = response.json()
    assert fake_us_fundamentals.calls == ["AAPL"]
    assert payload["identity"] == {
        "name": "Apple Inc.",
        "exchange": None,
        "sector": "Technology",
        "industry": "Consumer Electronics",
    }
    fundamentals = payload["fundamentals"]
    assert fundamentals["state"] == "partial"
    assert fundamentals["readinessState"] == "partial"
    assert fundamentals["fieldsAvailable"] == [
        "companyName",
        "sector",
        "industry",
        "marketCap",
        "revenueTtm",
        "profitabilityMargin",
        "valuationRatio",
    ]
    assert fundamentals["availableFields"]["companyProfile"] == ["companyName", "sector", "industry"]
    assert fundamentals["availableFields"]["financialStatements"] == ["revenueTtm"]
    assert fundamentals["availableFields"]["margins"] == ["profitabilityMargin"]
    assert fundamentals["availableFields"]["valuation"] == ["marketCap", "valuationRatio"]
    assert fundamentals["categories"]["companyProfile"]["state"] == "available"
    assert fundamentals["categories"]["financialStatements"]["state"] == "partial"
    assert fundamentals["categories"]["valuation"]["state"] == "available"
    assert fundamentals["fiscalPeriod"] == "mixed"
    assert fundamentals["asOf"] == "2026-07-01T00:00:00+00:00"
    assert fundamentals["source"] == "yfinance"
    assert fundamentals["freshness"] == "current"
    assert fundamentals["missingFieldReasons"]["fiscalPeriod"] == "mixed_periods"
    assert payload["missingData"] == ["filing_event_catalyst", "peer_benchmark"]


def test_research_packet_endpoint_sanitizes_us_fundamentals_provider_unavailable(monkeypatch) -> None:
    fake_stock = _FakeStockService(quote=None, history=_history_payload(status="unavailable", source="unavailable", rows=0))
    fake_structure = _FakeStructureDecisionService(_payload(data_status="unavailable"))
    fake_evidence = _FakeStockEvidenceService({"symbols": [], "items": []})

    class _FakeUSFundamentalsService:
        def get_us_fundamentals(self, symbol: str) -> dict[str, Any]:
            return {
                "symbol": symbol,
                "state": "provider_unavailable",
                "companyName": None,
                "sector": None,
                "industry": None,
                "marketCap": None,
                "revenueTtm": None,
                "profitabilityMargin": None,
                "valuationRatio": None,
                "fiscalPeriod": None,
                "asOf": None,
                "source": "unavailable",
                "freshness": "unknown",
                "fieldsAvailable": [],
                "missingFieldReasons": {
                    "companyName": "provider_unavailable",
                    "sector": "provider_unavailable",
                    "industry": "provider_unavailable",
                    "marketCap": "provider_unavailable",
                    "revenueTtm": "provider_unavailable",
                    "profitabilityMargin": "provider_unavailable",
                    "valuationRatio": "provider_unavailable",
                    "fiscalPeriod": "provider_unavailable",
                    "asOf": "provider_unavailable",
                    "source": "provider_unavailable",
                    "freshness": "provider_unavailable",
                },
            }

    monkeypatch.setattr(symbol_research_packet_service, "StockService", lambda: fake_stock, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "StockStructureDecisionService", lambda: fake_structure, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "StockEvidenceService", lambda: fake_evidence, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "USFundamentalsService", lambda: _FakeUSFundamentalsService(), raising=False)

    response = _client().get("/api/v1/stocks/AAPL/research-packet", params={"market": "us"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["fundamentals"]["state"] == "provider_unavailable"
    assert payload["fundamentals"]["readinessState"] == "provider_unavailable"
    assert payload["fundamentals"]["missingFieldReasons"]["marketCap"] == "Evidence is limited for this observation."
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "timeout" not in serialized.lower()
    assert "traceback" not in serialized.lower()
    assert "token" not in serialized.lower()


def test_research_packet_endpoint_fail_closes_absent_quote_history_and_evidence(monkeypatch) -> None:
    fake_stock = _FakeStockService(
        quote={
            "stock_code": "AAPL",
            "stock_name": "Apple",
            "current_price": 0.0,
            "change_percent": None,
            "market_timestamp": None,
            "observed_at": "2026-05-28T09:31:00Z",
            "freshness": "synthetic",
            "is_fallback": False,
            "is_stale": False,
            "is_partial": True,
            "is_synthetic": True,
        },
        history=_history_payload(status="unavailable", source="unavailable", rows=0),
    )
    fake_structure = _FakeStructureDecisionService(_payload(data_status="unavailable"))
    fake_evidence = _FakeStockEvidenceService({"symbols": [], "items": []})
    monkeypatch.setattr(symbol_research_packet_service, "StockService", lambda: fake_stock, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "StockStructureDecisionService", lambda: fake_structure, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "StockEvidenceService", lambda: fake_evidence, raising=False)
    monkeypatch.setattr(symbol_research_packet_service, "USFundamentalsService", lambda: _NoUSFundamentalsService(), raising=False)

    response = _client().get("/api/v1/stocks/AAPL/research-packet", params={"market": "us"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["quote"] == {"state": "missing", "price": None, "changePercent": None, "asOf": None}
    assert payload["history"] == {"state": "missing", "bars": 0, "period": "daily", "asOf": None}
    assert payload["structure"]["state"] == "missing"
    assert payload["fundamentals"]["state"] == "not_configured"
    assert payload["fundamentals"]["readinessState"] == "not_configured"
    assert payload["events"]["state"] == "not_integrated"
    assert payload["peer"]["state"] == "missing"
    assert payload["missingData"] == [
        "quote",
        "price_history",
        "structure_analysis",
        "fundamentals",
        "filing_event_catalyst",
        "peer_benchmark",
    ]
    assert payload["researchStatus"] == "blocked"
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in FORBIDDEN_ADVICE_TOKENS:
        assert forbidden not in serialized


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
    assert "schemaVersion" not in payload
    assert payload["consumerSafeSourceLabel"] == "部分数据源暂不可用"
    assert payload["dataQualityState"] == "limited"
    assert payload["freshnessState"] == "limited"
    assert payload["observationBoundary"]
    assert payload["researchNextSteps"]
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
        "historicalOhlcvReadiness",
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


def test_structure_decision_endpoint_requires_authenticated_user(monkeypatch) -> None:
    fake_service = _FakeStructureDecisionService(_payload())
    monkeypatch.setattr(
        stocks_endpoint,
        "StockStructureDecisionService",
        lambda: fake_service,
        raising=False,
    )

    response = _client(authenticated=False).get("/api/v1/stocks/AAPL/structure-decision")

    assert response.status_code == 401
    assert response.json() == {"detail": {"error": "unauthorized", "message": "Login required"}}
    assert fake_service.calls == []


def test_structure_decision_endpoint_includes_consumer_safe_ohlcv_readiness(monkeypatch) -> None:
    leaky_payload = {
        **_payload(),
        "historicalOhlcvReadiness": {
            "contractVersion": "historical_ohlcv_readiness_v1",
            "symbol": "AAPL",
            "market": "unknown",
            "timeframe": "1d",
            "requestedRange": {"start": None, "end": None},
            "lookbackBars": 90,
            "requiredBars": 90,
            "usableBars": 120,
            "missingBars": 0,
            "freshnessState": "unknown",
            "adjustmentState": "not_required",
            "benchmarkState": "not_requested",
            "providerState": "available",
            "overallState": "ready",
            "missingRequirements": [],
            "consumerSafe": True,
        },
    }
    fake_service = _FakeStructureDecisionService(leaky_payload)
    monkeypatch.setattr(
        stocks_endpoint,
        "StockStructureDecisionService",
        lambda: fake_service,
        raising=False,
    )

    response = _client().get("/api/v1/stocks/AAPL/structure-decision")

    assert response.status_code == 200
    payload = response.json()
    readiness = payload["historicalOhlcvReadiness"]
    assert readiness["consumerSafe"] is True
    assert readiness["overallState"] == "ready"
    assert readiness["usableBars"] >= readiness["requiredBars"]
    assert readiness["missingBars"] == 0
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in (
        "providername",
        "providerclass",
        "providerattempted",
        "requiredproviderclass",
        "endpointhost",
        "apikeypresent",
        "exceptionclass",
        "exceptionchain",
        "requestid",
        "traceid",
        "cachekey",
        "rawpayload",
        "raw_provider_payload",
        "credential",
        "token",
        "env",
        "api_key",
        "password",
        "secret",
        "private_key",
        "traceback",
    ):
        assert forbidden not in serialized


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


def test_structure_decision_endpoint_returns_controlled_unavailable_payload_on_latency_boundary(monkeypatch) -> None:
    blocking_history = _BlockingHistoryService()
    monkeypatch.setattr(
        stocks_endpoint,
        "StockStructureDecisionService",
        lambda: StockStructureDecisionService(
            history_service=blocking_history,
            timeout_seconds=0.01,
        ),
        raising=False,
    )

    started_at = time.monotonic()
    try:
        response = _client().get("/api/v1/stocks/AAPL/structure-decision")
    finally:
        blocking_history.release.set()
    elapsed = time.monotonic() - started_at

    assert response.status_code == 200
    assert blocking_history.started.is_set()
    assert elapsed < 0.5
    payload = response.json()
    assert payload["structureState"] == "lowConfidence"
    assert payload["confidence"] == "low"
    assert payload["dataQuality"]["status"] == "unavailable"
    assert payload["dataQuality"]["source"] == "unavailable"
    assert payload["dataQuality"]["period"] == "daily"
    assert payload["dataQuality"]["requestedDays"] == 90
    assert payload["dataQuality"]["observedBars"] == 0
    assert payload["dataQuality"]["usableBars"] == 0
    assert payload["dataQuality"]["reason"] == "Evidence is limited for this observation."
    assert payload["degradedInputs"][0]["section"] == "structureEvidence"
    assert payload["degradedInputs"][0]["status"] == "unavailable"
    assert payload["degradedInputs"][0]["reason"] == "Evidence is limited for this observation."
    assert payload["consumerIssues"][0]["label"] == "Structure evidence unavailable"
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    assert "traceback" not in serialized
    assert "exception" not in serialized
    assert "secret" not in serialized
    for forbidden in FORBIDDEN_ADVICE_TOKENS:
        assert forbidden not in serialized


def test_structure_decision_endpoint_preserves_ohlcv_readiness_when_computation_times_out(monkeypatch) -> None:
    fake_history = _FakeStockService(
        quote=None,
        history=_history_payload_with_valid_rows(rows=40),
    )
    blocking_peer_repo = _BlockingPeerRepository()
    monkeypatch.setattr(
        stocks_endpoint,
        "StockStructureDecisionService",
        lambda: StockStructureDecisionService(
            history_service=fake_history,
            stock_repo=blocking_peer_repo,
            timeout_seconds=0.01,
        ),
        raising=False,
    )

    started_at = time.monotonic()
    try:
        response = _client().get("/api/v1/stocks/AAPL/structure-decision")
    finally:
        blocking_peer_repo.release.set()
    elapsed = time.monotonic() - started_at

    assert response.status_code == 200
    assert fake_history.history_calls == [{"stock_code": "AAPL", "period": "daily", "days": 90}]
    assert blocking_peer_repo.started.is_set()
    assert elapsed < 0.5
    payload = response.json()
    assert payload["structureState"] == "lowConfidence"
    assert payload["confidence"] == "low"
    assert payload["dataQuality"]["status"] == "partial"
    assert payload["dataQuality"]["observedBars"] == 40
    assert payload["dataQuality"]["usableBars"] == 40
    assert payload["dataQuality"]["reason"] == "Evidence is limited for this observation."
    readiness = payload["historicalOhlcvReadiness"]
    assert readiness["overallState"] == "blocked"
    assert readiness["requiredBars"] == 90
    assert readiness["usableBars"] == 40
    assert readiness["missingBars"] == 50
    assert readiness["missingRequirements"] == ["insufficient_history"]
    assert payload["structureComputation"]["status"] == "degraded"
    assert payload["structureComputation"]["stateReason"] == "timed_out"
    assert (
        payload["structureComputation"]["message"]
        == "Daily OHLCV data is available, but structure computation timed out; this read remains observation-only."
    )
    assert any(
        item.get("section") == "structureComputation"
        and item.get("status") == "degraded"
        and item.get("reason") == "Evidence is limited for this observation."
        for item in payload["degradedInputs"]
    )
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in (
        "traceback",
        "exception",
        "secret",
        "providerclass",
        "rawpayload",
        "requestid",
        "traceid",
        "cachekey",
    ):
        assert forbidden not in serialized
    for forbidden in FORBIDDEN_ADVICE_TOKENS:
        assert forbidden not in serialized


def test_structure_decision_endpoint_preserves_confidence_evidence_guard_fields(monkeypatch) -> None:
    fake_service = _FakeStructureDecisionService(
        {
            **_payload(confidence="medium"),
            "rawConfidence": "high",
            "confidenceCap": {
                "value": 60,
                "label": "medium",
                "reasons": ["critical evidence missing"],
                "policyVersion": "confidence_evidence_consistency_v1",
            },
            "confidenceState": {
                "status": "evidence incomplete",
                "label": "medium",
                "reasons": ["critical evidence missing"],
                "freshnessConstrained": False,
                "sourceQualityLimited": False,
                "thesisBlocked": False,
            },
        }
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
    assert payload["confidence"] == "medium"
    assert "rawConfidence" not in payload
    assert payload["confidenceCap"]["value"] == 60
    assert payload["confidenceCap"]["label"] == "medium"
    assert payload["confidenceCap"]["reasons"] == ["critical evidence missing"]
    assert "policyVersion" not in payload["confidenceCap"]
    assert payload["confidenceState"]["status"] == "evidence incomplete"
    assert payload["confidenceState"]["label"] == "medium"
    assert payload["confidenceState"]["reasons"] == ["critical evidence missing"]
    assert payload["confidenceState"]["freshnessConstrained"] is False
    assert payload["confidenceState"]["sourceQualityLimited"] is False
    assert payload["confidenceState"]["thesisBlocked"] is False


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
    assert "schemaVersion" not in payload
    assert payload["consumerSafeSourceLabel"] == "部分数据源暂不可用"
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
        "historicalOhlcvReadiness",
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
    assert "rawConfidence" not in properties
    assert properties["confidenceCap"]["anyOf"][0]["$ref"].endswith("StockStructureConfidenceCap")
    assert properties["confidenceState"]["anyOf"][0]["$ref"].endswith("StockStructureConfidenceState")
    cap_schema = schema["StockStructureConfidenceCap"]["properties"]
    state_schema = schema["StockStructureConfidenceState"]["properties"]
    assert "policyVersion" not in cap_schema
    assert "reasonCodes" not in cap_schema
    assert "reasonCodes" not in state_schema
    assert cap_schema["reasons"]["items"]["type"] == "string"
    assert state_schema["reasons"]["items"]["type"] == "string"
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
