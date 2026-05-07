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
        assert payload["metadata"]["schemaVersion"] == "market_rotation_radar_phase2_v1"
        assert payload["metadata"]["timeWindows"] == ["5m", "15m", "60m", "1d"]
        assert payload["isFallback"] is True
        assert payload["freshness"] == "fallback"
        assert payload["themes"]
        assert all(theme["freshness"] != "live" for theme in payload["themes"])
        assert all(theme["confidence"] <= 0.25 for theme in payload["themes"])
        assert all(set(theme["timeWindows"]) == {"5m", "15m", "60m", "1d"} for theme in payload["themes"])
        assert all(theme["themeDetail"]["watchlistSafe"] is True for theme in payload["themes"])
        assert all("benchmarkProxies" in theme for theme in payload["themes"])

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
