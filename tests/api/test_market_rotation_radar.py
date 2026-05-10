# -*- coding: utf-8 -*-
"""API contract tests for the market rotation radar endpoint."""

from __future__ import annotations

import json
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import market


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    return TestClient(app)


def test_market_rotation_radar_route_is_exposed() -> None:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    routes = {
        (method, route.path)
        for route in app.routes
        if hasattr(route, "methods")
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }

    assert ("GET", "/api/v1/market/rotation-radar") in routes


def test_market_rotation_radar_response_is_safe_and_read_only() -> None:
    client = _client()
    try:
        response = client.get("/api/v1/market/rotation-radar")

        assert response.status_code == 200
        payload = response.json()
        assert payload["endpoint"] == "/api/v1/market/rotation-radar"
        assert payload["metadata"]["noExternalCalls"] is True
        assert payload["metadata"]["schemaVersion"] == "market_rotation_radar_phase4_v1"
        assert payload["metadata"]["timeWindows"] == ["5m", "15m", "60m", "1d"]
        assert payload["metadata"]["proxyQualityRequired"] is True
        assert payload["metadata"]["alertsAreReadOnlyEvidence"] is True
        assert payload["metadata"]["notificationDeliveryEnabled"] is False
        assert payload["isFallback"] is True
        assert payload["freshness"] == "fallback"
        assert payload["themes"]
        assert all(theme["freshness"] != "live" for theme in payload["themes"])
        assert all(theme["confidence"] <= 0.25 for theme in payload["themes"])
        assert all(set(theme["timeWindows"]) == {"5m", "15m", "60m", "1d"} for theme in payload["themes"])
        assert all(theme["themeDetail"]["watchlistSafe"] is True for theme in payload["themes"])
        assert all("benchmarkProxies" in theme for theme in payload["themes"])
        assert all("proxyQuality" in theme for theme in payload["themes"])
        assert all("rotationStateEvidence" in theme for theme in payload["themes"])
        assert all(theme["rotationStateEvidence"]["schemaVersion"] == "rotation_state_evidence_v1" for theme in payload["themes"])
        assert all(theme["rotationStateEvidence"]["flowLanguageAllowed"] is False for theme in payload["themes"])
        assert all(theme["proxyQuality"]["coveragePercent"] <= 100 for theme in payload["themes"])
        assert all("persistenceEvidence" in theme for theme in payload["themes"])
        assert "watchlistSortingExplanation" in payload["summary"]
        assert "非买卖建议" in payload["summary"]["watchlistSortingExplanation"]
        assert all(theme["alertCandidates"] == [] for theme in payload["themes"])

        text = json.dumps(payload, ensure_ascii=False).lower()
        for marker in (
            "raw_payload",
            "provider_payload",
            "api_key",
            "password",
            "session_id",
            "cookie",
            "secret",
            "token=",
            "buy now",
            "sell now",
            "建议买入",
            "下单",
        ):
            assert marker not in text
    finally:
        client.close()


def test_market_rotation_radar_market_query_switches_theme_universe() -> None:
    client = _client()
    try:
        cn_response = client.get("/api/v1/market/rotation-radar?market=CN")
        hk_response = client.get("/api/v1/market/rotation-radar?market=HK")
        us_response = client.get("/api/v1/market/rotation-radar")

        assert cn_response.status_code == 200
        assert hk_response.status_code == 200
        assert us_response.status_code == 200

        cn_payload = cn_response.json()
        hk_payload = hk_response.json()
        us_payload = us_response.json()

        assert cn_payload["market"] == "CN"
        assert hk_payload["market"] == "HK"
        assert us_payload["market"] == "US"
        assert len(cn_payload["themes"]) >= 25
        assert len(hk_payload["themes"]) >= 8
        assert len(us_payload["themes"]) >= 18
        assert any(theme["name"] == "AI算力" for theme in cn_payload["themes"])
        assert any(theme["name"] == "港股科技" for theme in hk_payload["themes"])
        assert any(theme["englishName"] == "AI Applications" for theme in us_payload["themes"])
        assert all(theme["market"] == "CN" for theme in cn_payload["themes"])
        assert all(theme["staticThemeOnly"] is True for theme in cn_payload["themes"])
        assert all(theme["dataQuality"] in {"taxonomy_only", "local_only", "proxy_backed"} for theme in cn_payload["themes"])
        assert all(theme["confidenceLabel"] == "待行情确认" for theme in cn_payload["themes"])
        assert all(theme["rotationStateEvidence"]["state"] == "insufficient_evidence" for theme in cn_payload["themes"])
        assert all(theme["rotationStateEvidence"]["flowEvidenceType"] == "none" for theme in cn_payload["themes"])
        assert "静态主题库" in cn_payload["warning"]
    finally:
        client.close()


def test_market_rotation_radar_crypto_market_is_available_when_tab_exists() -> None:
    client = _client()
    try:
        response = client.get("/api/v1/market/rotation-radar?market=CRYPTO")

        assert response.status_code == 200
        payload = response.json()
        assert payload["market"] == "CRYPTO"
        assert len(payload["themes"]) >= 8
        assert any(theme["name"] == "Layer 1" for theme in payload["themes"])
        assert all(theme["staticThemeOnly"] is True for theme in payload["themes"])
        assert all(theme["source"] == "local_taxonomy" for theme in payload["themes"])
    finally:
        client.close()
