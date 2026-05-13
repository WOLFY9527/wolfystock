# -*- coding: utf-8 -*-
"""API contract tests for the liquidity monitor endpoint."""

from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.v1.endpoints.liquidity_monitor as liquidity_monitor


def test_liquidity_monitor_route_returns_schema_compatible_payload() -> None:
    app = FastAPI()
    app.include_router(liquidity_monitor.router, prefix="/api/v1/market")

    payload = {
        "endpoint": "/api/v1/market/liquidity-monitor",
        "generatedAt": "2026-05-07T10:00:00+08:00",
        "score": {
            "value": 69,
            "regime": "supportive",
            "confidence": 0.44,
            "includedIndicatorCount": 3,
            "possibleIndicatorWeight": 43,
            "includedIndicatorWeight": 19,
        },
        "freshness": {
            "status": "delayed",
            "weakestIndicatorFreshness": "delayed",
            "latestAsOf": "2026-05-07T10:00:00+08:00",
        },
        "indicators": [
            {
                "key": "vix_pressure",
                "label": "VIX / 波动率压力",
                "status": "live",
                "freshness": "live",
                "includedInScore": True,
                "scoreContribution": 8,
            }
        ],
        "advisoryDisclosure": "仅用于观察市场流动性环境，非买卖建议，不触发扫描、回测或组合动作。",
        "sourceMetadata": {
            "externalProviderCalls": False,
            "providerRuntimeChanged": False,
            "marketCacheMutation": False,
        },
    }

    with patch("api.v1.endpoints.liquidity_monitor.LiquidityMonitorService") as mock_service:
        mock_service.return_value.get_liquidity_monitor.return_value = payload
        response = TestClient(app).get("/api/v1/market/liquidity-monitor")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"endpoint", "generatedAt", "score", "freshness", "indicators", "advisoryDisclosure", "sourceMetadata"}
    assert body["endpoint"] == "/api/v1/market/liquidity-monitor"
    assert body["score"]["regime"] == "supportive"
    assert set(body["sourceMetadata"]) == {"externalProviderCalls", "providerRuntimeChanged", "marketCacheMutation"}
    assert body["sourceMetadata"]["externalProviderCalls"] is False
