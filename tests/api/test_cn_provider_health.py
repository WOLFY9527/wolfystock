# -*- coding: utf-8 -*-
"""API contract tests for the CN provider health endpoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.v1.endpoints import market
from src.services import cn_provider_health_service as health_service_module


EXPECTED_ENTRY_FIELDS = {
    "providerName",
    "providerId",
    "sourceType",
    "sourceTier",
    "trustLevel",
    "freshnessExpectation",
    "observationOnly",
    "scoreContributionAllowed",
    "dependencyInstalled",
    "providerAvailable",
    "healthStatus",
    "supportedCapabilities",
    "unsupportedCapabilities",
    "contractCapabilities",
    "degradationReason",
    "missingProviderReason",
    "attemptedAt",
    "timeoutSeconds",
}
FORBIDDEN_PROVIDER_FIELDS = {
    "quotes",
    "quote",
    "kline",
    "klines",
    "symbols",
    "rawPayload",
    "score",
    "scoreContribution",
}


def _client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pytdx_probe,
    akshare_probe,
) -> TestClient:
    monkeypatch.setattr(
        market,
        "CNProviderHealthService",
        lambda: health_service_module.CNProviderHealthService(
            pytdx_probe=pytdx_probe,
            akshare_probe=akshare_probe,
        ),
    )
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    return TestClient(app)


def test_cn_provider_health_route_is_exposed() -> None:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    routes = {
        (method, route.path)
        for route in app.routes
        if hasattr(route, "methods")
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }

    assert ("GET", "/api/v1/market/cn-provider-health") in routes


def test_cn_provider_health_route_returns_metadata_only_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(
        monkeypatch,
        pytdx_probe=lambda timeout_seconds: {
            "providerName": "pytdx",
            "providerId": "pytdx",
            "dependencyInstalled": True,
            "providerAvailable": True,
            "supportedCapabilities": [
                "cn_history_daily",
                "cn_name_lookup",
                "cn_quote",
                "cn_realtime_quote",
            ],
            "unsupportedCapabilities": ["hk_history_daily", "us_quote"],
            "degradationReason": None,
            "missingProviderReason": None,
            "attemptedAt": "2026-05-19T02:03:04+00:00",
            "timeoutSeconds": timeout_seconds,
            "serverHealth": "reachable",
            "quotes": {"000001": {"price": 12.34}},
            "symbols": ["000001"],
            "score": {"value": 99},
        },
        akshare_probe=lambda timeout_seconds: {
            "providerName": "AKShare",
            "providerId": "akshare",
            "dependencyInstalled": True,
            "providerAvailable": True,
            "supportedCapabilities": [
                "cn_stock_list",
                "cn_realtime_snapshot",
                "cn_realtime_quote",
                "cn_history_daily",
                "cn_index_quote",
                "cn_market_stats",
                "cn_sector_rankings",
                "cn_etf_realtime_quote",
                "cn_etf_history_daily",
                "hk_realtime_quote",
                "hk_history_daily",
                "chip_distribution",
            ],
            "unsupportedCapabilities": ["hk_index_quote"],
            "degradationReason": None,
            "missingProviderReason": None,
            "attemptedAt": "2026-05-19T02:03:05+00:00",
            "timeoutSeconds": timeout_seconds,
            "interfaceHealth": "ok",
            "rawPayload": {"market": "CN"},
            "kline": [{"close": 1.0}],
        },
    )

    response = client.get("/api/v1/market/cn-provider-health")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert [item["providerId"] for item in payload] == ["pytdx", "akshare"]
    assert all(set(item) == EXPECTED_ENTRY_FIELDS for item in payload)
    assert all(not FORBIDDEN_PROVIDER_FIELDS.intersection(item) for item in payload)
    assert all(item["observationOnly"] is True for item in payload)
    assert all(item["scoreContributionAllowed"] is False for item in payload)
    assert next(item for item in payload if item["providerId"] == "pytdx")["trustLevel"] == "usable_with_caution"
    assert next(item for item in payload if item["providerId"] == "akshare")["trustLevel"] == "weak"
    assert next(item for item in payload if item["providerId"] == "pytdx")["healthStatus"] == "healthy"
    assert next(item for item in payload if item["providerId"] == "akshare")["healthStatus"] == "healthy"


def test_cn_provider_health_route_degrades_cleanly_when_dependency_missing_or_probe_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(
        monkeypatch,
        pytdx_probe=lambda timeout_seconds: (_ for _ in ()).throw(ImportError("pytdx missing")),
        akshare_probe=lambda timeout_seconds: (_ for _ in ()).throw(RuntimeError("upstream page changed")),
    )

    response = client.get("/api/v1/market/cn-provider-health")

    assert response.status_code == 200
    payload = {item["providerId"]: item for item in response.json()}

    pytdx = payload["pytdx"]
    assert pytdx["dependencyInstalled"] is False
    assert pytdx["providerAvailable"] is False
    assert pytdx["healthStatus"] == "missing_dependency"
    assert pytdx["missingProviderReason"] == "pytdx_not_installed"
    assert pytdx["observationOnly"] is True
    assert pytdx["scoreContributionAllowed"] is False

    akshare = payload["akshare"]
    assert akshare["dependencyInstalled"] is True
    assert akshare["providerAvailable"] is False
    assert akshare["healthStatus"] == "probe_failure"
    assert akshare["degradationReason"] == "akshare_probe_failed"
    assert akshare["missingProviderReason"] == "akshare_probe_failed"
    assert akshare["trustLevel"] == "weak"
    assert akshare["observationOnly"] is True
    assert akshare["scoreContributionAllowed"] is False
