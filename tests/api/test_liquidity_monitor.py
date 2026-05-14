# -*- coding: utf-8 -*-
"""API contract tests for the liquidity monitor endpoint."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.v1.endpoints.liquidity_monitor as liquidity_monitor
from api.v1.schemas.liquidity_monitor import LiquidityMonitorResponse


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "liquidity_monitor"
FIXTURE_NAMES = (
    "official_cached_macro_rates_context.json",
    "mixed_official_proxy_context.json",
    "missing_macro_rates_proxy_fallback_context.json",
    "credit_stress_observation_only_context.json",
    "delayed_proxy_fx_commodities_context.json",
    "provider_unavailable_stale_malformed_context.json",
)


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


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


def test_liquidity_monitor_route_preserves_explicit_non_live_indicator_contracts() -> None:
    app = FastAPI()
    app.include_router(liquidity_monitor.router, prefix="/api/v1/market")

    payload = {
        "endpoint": "/api/v1/market/liquidity-monitor",
        "generatedAt": "2026-05-07T10:00:00+08:00",
        "score": {
            "value": 50,
            "regime": "unavailable",
            "confidence": 0.25,
            "includedIndicatorCount": 1,
            "possibleIndicatorWeight": 43,
            "includedIndicatorWeight": 8,
        },
        "freshness": {
            "status": "fallback",
            "weakestIndicatorFreshness": "fallback",
            "latestAsOf": "2026-05-07T10:00:00+08:00",
        },
        "indicators": [
            {
                "key": "cn_hk_flows",
                "label": "CN/HK 资金流",
                "status": "unavailable",
                "freshness": "fallback",
                "includedInScore": False,
                "scoreContribution": 0,
            },
            {
                "key": "vix_pressure",
                "label": "VIX / 波动率压力",
                "status": "partial",
                "freshness": "delayed",
                "includedInScore": True,
                "scoreContribution": 8,
            },
        ],
        "advisoryDisclosure": "仅用于观察市场流动性环境，非买卖建议，不触发扫描、回测或组合动作。",
        "sourceMetadata": {
            "externalProviderCalls": True,
            "providerRuntimeChanged": False,
            "marketCacheMutation": False,
        },
    }

    with patch("api.v1.endpoints.liquidity_monitor.LiquidityMonitorService") as mock_service:
        mock_service.return_value.get_liquidity_monitor.return_value = payload
        response = TestClient(app).get("/api/v1/market/liquidity-monitor")

    assert response.status_code == 200
    indicators = {item["key"]: item for item in response.json()["indicators"]}
    assert indicators["cn_hk_flows"]["status"] == "unavailable"
    assert indicators["cn_hk_flows"]["freshness"] == "fallback"
    assert indicators["cn_hk_flows"]["includedInScore"] is False
    assert indicators["vix_pressure"]["status"] == "partial"
    assert indicators["vix_pressure"]["freshness"] == "delayed"
    assert indicators["vix_pressure"]["includedInScore"] is True


def test_liquidity_monitor_route_accepts_all_golden_fixture_payloads() -> None:
    app = FastAPI()
    app.include_router(liquidity_monitor.router, prefix="/api/v1/market")

    for fixture_name in FIXTURE_NAMES:
        payload = LiquidityMonitorResponse(**_load_fixture(fixture_name)).model_dump()

        with patch("api.v1.endpoints.liquidity_monitor.LiquidityMonitorService") as mock_service:
            mock_service.return_value.get_liquidity_monitor.return_value = payload
            response = TestClient(app).get("/api/v1/market/liquidity-monitor")

        assert response.status_code == 200
        assert response.json() == payload
