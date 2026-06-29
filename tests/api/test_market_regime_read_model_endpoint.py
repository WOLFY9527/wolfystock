# -*- coding: utf-8 -*-
"""API contract tests for the Market Regime read model endpoint."""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import get_optional_current_user
from api.v1.endpoints import market

FORBIDDEN_ADVICE_TERMS = (
    "buy",
    "sell",
    "hold",
    "recommendation",
    "target price",
    "enter",
    "exit",
    "long",
    "short",
    "加仓",
    "减仓",
    "买入",
    "卖出",
    "持有",
    "目标价",
    "推荐",
)


def _base_payload(*, status: str = "ok", readiness_label: str = "product_ready") -> dict:
    return {
        "consumerSafe": True,
        "noAdvice": True,
        "contractVersion": "market_regime_read_model_v1",
        "sourceEvidenceContractVersion": "market_regime_evidence_pack_v1",
        "status": status,
        "market": "US",
        "symbols": ["SPY", "QQQ", "AAPL", "MSFT"],
        "benchmarkSymbol": "SPY",
        "growthProxySymbol": "QQQ",
        "regime": {"label": "risk_on_confirming", "status": status, "source": "deterministic_evidence_fields"},
        "productSummary": "Risk-on confirming evidence is currently present because local evidence fields align.",
        "evidenceCards": [
            {
                "id": "benchmark_trend",
                "title": "Benchmark Trend",
                "status": "positive",
                "severity": "info",
                "headline": "Benchmark trend evidence is positive.",
                "metrics": [{"label": "return20d", "value": 0.1}],
                "reasons": ["Benchmark local trend fields are aligned."],
                "sourceFields": ["evidence.benchmarkTrend.return20d"],
                "consumerSafe": True,
            },
            {
                "id": "growth_risk_proxy",
                "title": "Growth Risk Proxy",
                "status": "positive",
                "severity": "info",
                "headline": "Growth proxy evidence is positive.",
                "metrics": [{"label": "relativeReturn20d", "value": 0.03}],
                "reasons": ["Growth proxy relative return is available."],
                "sourceFields": ["evidence.growthRiskProxy.relativeReturn20d"],
                "consumerSafe": True,
            },
            {
                "id": "breadth",
                "title": "Breadth",
                "status": "positive",
                "severity": "info",
                "headline": "Breadth evidence is broad.",
                "metrics": [{"label": "percentAboveMa20", "value": 1.0}],
                "reasons": ["Breadth evidence is available."],
                "sourceFields": ["evidence.breadthProxy.percentAboveMa20"],
                "consumerSafe": True,
            },
            {
                "id": "volatility",
                "title": "Volatility",
                "status": "neutral",
                "severity": "info",
                "headline": "Volatility evidence is normal.",
                "metrics": [{"label": "volatilityState", "value": "normal"}],
                "reasons": ["Volatility evidence is available."],
                "sourceFields": ["evidence.volatilityProxy.volatilityState"],
                "consumerSafe": True,
            },
            {
                "id": "quote_snapshot",
                "title": "Quote Snapshot",
                "status": "positive",
                "severity": "info",
                "headline": "Quote snapshot evidence is available.",
                "metrics": [{"label": "availabilityState", "value": "available"}],
                "reasons": ["Quote snapshot rows are available."],
                "sourceFields": ["quoteSnapshotEvidence.availabilityState"],
                "consumerSafe": True,
            },
            {
                "id": "data_quality",
                "title": "Data Quality",
                "status": "positive",
                "severity": "info",
                "headline": "Data quality is product-ready.",
                "metrics": [{"label": "missingDataFamilies", "value": []}],
                "reasons": ["No missing evidence families are present."],
                "sourceFields": ["missingDataFamilies"],
                "consumerSafe": True,
            },
        ],
        "symbolContext": [],
        "dataQuality": {
            "adjustedCoverageState": "available",
            "missingDataFamilies": [],
            "blockedProductSurfaces": [],
        },
        "readiness": {
            "label": readiness_label,
            "status": status,
            "missingDataFamilies": [],
            "blockedProductSurfaces": [],
            "nextOperatorAction": "Market regime read model is available from local evidence inputs.",
        },
        "surfaceHints": [{"surface": "market_overview", "readOnly": True}],
        "missingDataFamilies": [],
        "blockedProductSurfaces": [],
        "nextOperatorAction": "Market regime read model is available from local evidence inputs.",
        "networkCallsEnabled": False,
        "mutationEnabled": False,
        "providerCallsEnabled": False,
    }


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    app.dependency_overrides[get_optional_current_user] = lambda: None
    return TestClient(app)


def test_market_regime_read_model_route_is_exposed() -> None:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    routes = {
        (method, route.path)
        for route in app.routes
        if hasattr(route, "methods")
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }

    assert ("GET", "/api/v1/market/regime-read-model") in routes


def test_market_regime_read_model_endpoint_returns_product_ready_payload(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_build_read_model(**kwargs) -> dict:
        calls.append(kwargs)
        return _base_payload()

    monkeypatch.setattr(market, "build_market_regime_read_model", fake_build_read_model)

    response = _client().get("/api/v1/market/regime-read-model")

    assert response.status_code == 200
    payload = response.json()
    assert payload["contractVersion"] == "market_regime_read_model_v1"
    assert payload["sourceEvidenceContractVersion"] == "market_regime_evidence_pack_v1"
    assert payload["status"] == "ok"
    assert payload["readiness"]["label"] == "product_ready"
    assert payload["consumerSafe"] is True
    assert payload["noAdvice"] is True
    assert payload["networkCallsEnabled"] is False
    assert payload["mutationEnabled"] is False
    assert payload["providerCallsEnabled"] is False
    assert {card["id"] for card in payload["evidenceCards"]} == {
        "benchmark_trend",
        "growth_risk_proxy",
        "breadth",
        "volatility",
        "quote_snapshot",
        "data_quality",
    }
    assert calls
    assert calls[0]["market"] == "US"
    assert calls[0]["symbols"] == ["SPY", "QQQ", "AAPL", "MSFT"]
    assert calls[0]["require_adjusted"] is True


def test_market_regime_read_model_endpoint_preserves_blocked_families(monkeypatch) -> None:
    blocked = _base_payload(status="partial", readiness_label="blocked")
    blocked["regime"] = {"label": "insufficient_data", "status": "partial", "source": "deterministic_evidence_fields"}
    blocked["missingDataFamilies"] = ["adjusted_prices", "quote_snapshot"]
    blocked["blockedProductSurfaces"] = ["Market Overview"]
    blocked["readiness"]["missingDataFamilies"] = ["adjusted_prices", "quote_snapshot"]
    blocked["readiness"]["blockedProductSurfaces"] = ["Market Overview"]
    blocked["dataQuality"]["missingDataFamilies"] = ["adjusted_prices", "quote_snapshot"]
    blocked["dataQuality"]["blockedProductSurfaces"] = ["Market Overview"]
    blocked["nextOperatorAction"] = "Resolve missing local evidence families or blocked product surfaces, then rerun."
    monkeypatch.setattr(market, "build_market_regime_read_model", lambda **_: blocked)

    response = _client().get("/api/v1/market/regime-read-model")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "partial"
    assert payload["readiness"]["label"] == "blocked"
    assert payload["missingDataFamilies"] == ["adjusted_prices", "quote_snapshot"]
    assert payload["blockedProductSurfaces"] == ["Market Overview"]


def test_market_regime_read_model_endpoint_fails_closed_without_raw_exception_leakage(monkeypatch) -> None:
    def raising_build_read_model(**_kwargs) -> dict:
        raise RuntimeError("boom C:\\Users\\leeyi\\secret\\cache.parquet token=abc")

    monkeypatch.setattr(market, "build_market_regime_read_model", raising_build_read_model)

    response = _client().get("/api/v1/market/regime-read-model?ohlcvCacheDir=C:%5CUsers%5Cleeyi%5Csecret")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed_closed"
    assert payload["readiness"]["label"] == "failed_closed"
    assert payload["regime"]["label"] == "insufficient_data"
    serialized = response.text.lower()
    for forbidden in ("runtimeerror", "traceback", "exception", "c:\\users", "secret", "token", "boom"):
        assert forbidden not in serialized


def test_market_regime_read_model_endpoint_contains_no_advice_terms(monkeypatch) -> None:
    monkeypatch.setattr(market, "build_market_regime_read_model", lambda **_: _base_payload())

    response = _client().get("/api/v1/market/regime-read-model")

    assert response.status_code == 200
    serialized = json.dumps(response.json(), ensure_ascii=False).lower()
    for term in FORBIDDEN_ADVICE_TERMS:
        assert term not in serialized
