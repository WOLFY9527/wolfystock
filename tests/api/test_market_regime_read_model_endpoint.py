# -*- coding: utf-8 -*-
"""API contract tests for the Market Regime read model endpoint."""

from __future__ import annotations

import json
import importlib
from datetime import date, datetime, timedelta, timezone

import pandas as pd
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
START_DATE = date(2026, 1, 2)
SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"]


def _series(start: float, step: float, bars: int = 60) -> list[float]:
    return [round(start + (index * step), 4) for index in range(bars)]


def _write_ohlcv(cache_dir, values_by_symbol: dict[str, list[float]]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    for symbol, closes in values_by_symbol.items():
        rows = [
            {
                "date": (START_DATE + timedelta(days=index)).isoformat(),
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1_000_000 + index,
                "adjusted_close": close,
            }
            for index, close in enumerate(closes)
        ]
        pd.DataFrame(rows).to_parquet(cache_dir / f"{symbol}.parquet", index=False)


def _write_quote_cache(cache_path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "symbol": symbol,
            "market": "us",
            "last": 100.0 + index,
            "previousClose": 99.5 + index,
            "volume": 1_000_000 + index,
            "asOf": datetime.now(timezone.utc).isoformat(),
            "currency": "USD",
            "source": "local_quote_snapshot_cache",
        }
        for index, symbol in enumerate(SYMBOLS)
    ]
    cache_path.write_text(json.dumps({"quotes": rows}), encoding="utf-8")


def _base_payload(*, status: str = "ok", readiness_label: str = "product_ready") -> dict:
    return {
        "consumerSafe": True,
        "noAdvice": True,
        "contractVersion": "market_regime_read_model_v1",
        "sourceEvidenceContractVersion": "market_regime_evidence_pack_v1",
        "status": status,
        "market": "US",
        "symbols": ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"],
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
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "get" in paths["/api/v1/market/regime-read-model"]
    assert "get" in paths["/api/v1/market/regime-evidence-pack"]


def test_market_regime_runtime_contracts_are_registered_on_default_app(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    api_app = importlib.import_module("api.app")
    market_overview_endpoint = importlib.import_module("api.v1.endpoints.market_overview")
    cockpit_service_module = importlib.import_module("src.services.market_decision_cockpit_service")
    read_model_service = importlib.import_module("src.services.market_regime_read_model_service")
    cockpit_service = importlib.import_module("src.services.market_decision_cockpit_service")

    class NoProviderMarketOverviewService:
        def get_indices(self, **_kwargs):
            return {"status": "success", "providerCallsEnabled": False}

        def get_volatility(self, **_kwargs):
            return {"status": "success", "providerCallsEnabled": False}

        def get_sentiment(self, **_kwargs):
            return {"status": "success", "providerCallsEnabled": False}

        def get_funds_flow(self, **_kwargs):
            return {"status": "success", "providerCallsEnabled": False}

        def get_macro(self, **_kwargs):
            return {"status": "success", "providerCallsEnabled": False}

        def get_market_regime_decision(self, **_kwargs):
            return {
                "regime": "lowConfidence",
                "confidence": "low",
                "confidenceScore": 0,
                "driverScores": {},
                "explanation": {},
                "researchPriorities": {},
                "missingEvidence": ["market_regime_low_confidence"],
            }

    def failed_closed_read_model():
        return {
            "status": "failed_closed",
            "readiness": "failed_closed",
            "label": "insufficient_data",
            "regimeEvidenceProjection": read_model_service.project_market_regime_evidence(None),
        }

    monkeypatch.setattr(market_overview_endpoint, "MarketOverviewService", lambda: NoProviderMarketOverviewService())
    monkeypatch.setattr(cockpit_service_module, "MarketOverviewService", lambda: NoProviderMarketOverviewService())
    monkeypatch.setattr(
        market,
        "MarketDecisionCockpitService",
        lambda: cockpit_service.MarketDecisionCockpitService(
            market_overview_service=NoProviderMarketOverviewService(),
            market_regime_read_model_provider=failed_closed_read_model,
        ),
    )
    client = TestClient(api_app.app)

    evidence_response = client.get("/api/v1/market/regime-evidence-pack")
    overview_response = client.get("/api/v1/market-overview")
    cockpit_response = client.get("/api/v1/market/decision-cockpit")

    assert evidence_response.status_code == 200
    assert evidence_response.json()["contractVersion"] == "market_regime_evidence_pack_v1"

    assert overview_response.status_code == 200
    overview_projection = overview_response.json()["regimeEvidenceProjection"]
    assert overview_projection["contractVersion"] == "market_regime_evidence_projection_v1"

    assert cockpit_response.status_code == 200
    cockpit_projection = cockpit_response.json()["marketRegimeReadModel"]["regimeEvidenceProjection"]
    assert cockpit_projection["contractVersion"] == "market_regime_evidence_projection_v1"


def test_market_regime_evidence_pack_endpoint_returns_ready_computed_contract(tmp_path, monkeypatch) -> None:
    ohlcv_dir = tmp_path / "us-parquet-cache"
    quote_path = tmp_path / "quote-snapshot-cache" / "us-starter-quotes.json"
    _write_ohlcv(
        ohlcv_dir,
        {
            "SPY": _series(100, 1.0),
            "QQQ": _series(100, 1.25),
            "AAPL": _series(90, 0.9),
            "MSFT": _series(95, 1.1),
            "NVDA": _series(110, 1.4),
            "TSLA": _series(80, 0.7),
        },
    )
    _write_quote_cache(quote_path)
    monkeypatch.setenv("LOCAL_US_PARQUET_DIR", str(ohlcv_dir))
    monkeypatch.setenv("LOCAL_US_QUOTE_SNAPSHOT_CACHE_PATH", str(quote_path))

    response = _client().get("/api/v1/market/regime-evidence-pack")

    assert response.status_code == 200
    payload = response.json()
    assert payload["contractVersion"] == "market_regime_evidence_pack_v1"
    assert payload["status"] == "ready"
    assert payload["readiness"] == "ready"
    assert payload["consumerSafe"] is True
    assert payload["noAdviceDisclosure"]
    assert payload["tier"] == "tier1"
    assert payload["evaluatedSymbols"] == SYMBOLS
    assert payload["regimeSummary"]["label"] == "risk_on"
    assert payload["regimeSummary"]["confidence"] > 0
    assert payload["evidence"]["indexTrend"]["return20d"] is not None
    assert payload["evidence"]["momentum"]["shortWindowReturn"] is not None
    assert payload["evidence"]["breadth"]["aboveMovingAverageCount"] == len(SYMBOLS)
    assert payload["evidence"]["volatilityRisk"]["realizedVolatility20d"] is not None
    assert payload["evidence"]["concentrationLeadership"]["state"] in {"leaders_ahead", "leaders_inline", "leaders_lagging"}
    assert payload["evidence"]["dataCoverage"]["usedSymbols"] == SYMBOLS
    assert payload["networkCallsEnabled"] is False
    assert payload["mutationEnabled"] is False
    assert payload["providerCallsEnabled"] is False


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
    assert calls[0]["symbols"] == ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"]
    assert calls[0]["require_adjusted"] is True


def test_market_regime_read_model_endpoint_does_not_default_to_legacy_unconfigured_cache(
    monkeypatch,
) -> None:
    calls: list[dict] = []

    def fake_build_read_model(**kwargs) -> dict:
        calls.append(kwargs)
        return _base_payload(status="failed_closed", readiness_label="failed_closed")

    monkeypatch.delenv("LOCAL_US_PARQUET_DIR", raising=False)
    monkeypatch.delenv("US_STOCK_PARQUET_DIR", raising=False)
    monkeypatch.delenv("LOCAL_US_QUOTE_SNAPSHOT_CACHE_PATH", raising=False)
    monkeypatch.delenv("US_QUOTE_SNAPSHOT_CACHE_PATH", raising=False)
    monkeypatch.delenv("WOLFYSTOCK_US_QUOTE_SNAPSHOT_CACHE_PATH", raising=False)
    monkeypatch.delenv("QUOTE_SNAPSHOT_CACHE_PATH", raising=False)
    monkeypatch.setattr(market, "build_market_regime_read_model", fake_build_read_model)

    response = _client().get("/api/v1/market/regime-read-model")

    assert response.status_code == 200
    assert calls[0]["ohlcv_cache_dir"] is None
    assert calls[0]["quote_snapshot_cache_path"] is None


def test_market_regime_read_model_endpoint_resolves_configured_quote_snapshot_cache(
    tmp_path,
    monkeypatch,
) -> None:
    ohlcv_dir = tmp_path / "us-parquet-cache"
    quote_path = tmp_path / "quote-snapshot-cache" / "us-starter-quotes.json"
    _write_ohlcv(
        ohlcv_dir,
        {
            "SPY": _series(100, 1.0),
            "QQQ": _series(100, 1.25),
            "AAPL": _series(90, 0.9),
            "MSFT": _series(95, 1.1),
            "NVDA": _series(110, 1.4),
            "TSLA": _series(80, 0.7),
        },
    )
    _write_quote_cache(quote_path)
    monkeypatch.setenv("LOCAL_US_PARQUET_DIR", str(ohlcv_dir))
    monkeypatch.setenv("LOCAL_US_QUOTE_SNAPSHOT_CACHE_PATH", str(quote_path))

    response = _client().get("/api/v1/market/regime-read-model")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["dataQuality"]["quoteSnapshotCoverage"]["state"] == "available"
    assert payload["dataQuality"]["quoteSnapshotCoverage"]["availabilityState"] == "available"
    assert payload["evidenceCards"][4]["id"] == "quote_snapshot"
    assert payload["evidenceCards"][4]["cardId"] == "quote_snapshot"
    assert payload["evidenceCards"][4]["status"] == "positive"
    assert payload["surfaceHints"][0]["statusHint"] == "evidence_available"


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
