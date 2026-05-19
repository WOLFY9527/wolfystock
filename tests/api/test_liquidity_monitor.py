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
                "evidence": {
                    "contractVersion": "source_confidence_contract_v1",
                    "source": "fred",
                    "sourceLabel": "FRED VIXCLS",
                    "asOf": "2026-05-07T10:00:00+08:00",
                    "freshness": "live",
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": False,
                    "isUnavailable": False,
                    "coverage": 1.0,
                    "confidenceWeight": 1.0,
                    "inputs": [
                        {
                            "key": "VIX",
                            "label": "VIX",
                            "source": "fred",
                            "sourceLabel": "FRED VIXCLS",
                            "sourceType": "official_public",
                            "asOf": "2026-05-07T10:00:00+08:00",
                            "freshness": "live",
                            "isFallback": False,
                            "isStale": False,
                            "isPartial": False,
                            "isUnavailable": False,
                            "coverage": 1.0,
                            "confidenceWeight": 1.0,
                        }
                    ],
                },
                "coverageDiagnostics": {
                    "indicatorId": "vix_pressure",
                    "indicatorName": "VIX / 波动率压力",
                    "requiredInputs": ["VIX"],
                    "fulfilledInputs": ["VIX"],
                    "missingInputs": [],
                    "requiredProviderClass": "official_public.vix_or_volatility",
                    "configuredProviderAvailable": True,
                    "realSourceAvailable": True,
                    "proxyOnly": False,
                    "observationOnly": False,
                    "scoreContributionAllowed": True,
                    "scoreExclusionReason": None,
                    "requiredRealSourceForScore": True,
                    "proxyObservationOnlyReason": None,
                    "missingProviderReason": None,
                    "paidDataLikelyRequired": False,
                    "sourceTier": "official_public",
                    "freshness": "live",
                    "trustLevel": "reliable",
                    "contributesToScore": True,
                    "scoreContribution": 8,
                    "activationHint": "official VIX source active",
                },
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
    assert body["indicators"][0]["evidence"]["source"] == "fred"
    assert body["indicators"][0]["evidence"]["inputs"][0]["sourceType"] == "official_public"
    diagnostics = body["indicators"][0]["coverageDiagnostics"]
    assert diagnostics["requiredProviderClass"] == "official_public.vix_or_volatility"
    assert diagnostics["realSourceAvailable"] is True
    assert diagnostics["scoreContributionAllowed"] is True


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
                "evidence": {
                    "contractVersion": "source_confidence_contract_v1",
                    "source": "fallback",
                    "sourceLabel": "备用数据",
                    "asOf": "2026-05-07T10:00:00+08:00",
                    "freshness": "unavailable",
                    "isFallback": True,
                    "isStale": False,
                    "isPartial": False,
                    "isUnavailable": True,
                    "coverage": 0.0,
                    "confidenceWeight": 0.0,
                    "degradationReason": "fallback_source",
                    "capReason": "unavailable_source",
                    "inputs": [
                        {
                            "key": "cn_flows",
                            "label": "CN/HK 资金流",
                            "source": "fallback",
                            "sourceLabel": "备用数据",
                            "sourceType": "fallback_static",
                            "asOf": "2026-05-07T10:00:00+08:00",
                            "freshness": "fallback",
                            "isFallback": True,
                            "isStale": False,
                            "isPartial": False,
                            "isUnavailable": False,
                            "coverage": 0.0,
                            "confidenceWeight": 0.4,
                            "capReason": "fallback_source",
                        }
                    ],
                },
                "coverageDiagnostics": {
                    "indicatorId": "cn_hk_flows",
                    "indicatorName": "CN/HK 资金流",
                    "requiredInputs": ["NORTHBOUND", "SOUTHBOUND"],
                    "fulfilledInputs": [],
                    "missingInputs": ["NORTHBOUND", "SOUTHBOUND"],
                    "requiredProviderClass": "authorized.cn_hk_connect_flow",
                    "configuredProviderAvailable": True,
                    "realSourceAvailable": False,
                    "proxyOnly": False,
                    "observationOnly": True,
                    "scoreContributionAllowed": False,
                    "missingProviderReason": "requires_authorized.cn_hk_connect_flow",
                    "paidDataLikelyRequired": True,
                    "sourceTier": "static_fallback",
                    "freshness": "fallback",
                    "trustLevel": "unavailable",
                    "contributesToScore": False,
                    "scoreContribution": 0,
                    "capReason": "unavailable_source",
                    "degradationReason": "fallback_source",
                    "activationHint": "requires real CN/HK flow provider",
                },
            },
            {
                "key": "vix_pressure",
                "label": "VIX / 波动率压力",
                "status": "partial",
                "freshness": "delayed",
                "includedInScore": False,
                "scoreContribution": 0,
                "evidence": {
                    "contractVersion": "source_confidence_contract_v1",
                    "source": "yfinance_proxy",
                    "sourceLabel": "Yahoo Finance",
                    "asOf": "2026-05-07T10:00:00+08:00",
                    "freshness": "partial",
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": True,
                    "isUnavailable": False,
                    "coverage": 1.0,
                    "confidenceWeight": 0.7,
                    "degradationReason": "partial_coverage",
                    "capReason": "partial_coverage",
                    "inputs": [
                        {
                            "key": "VIX",
                            "label": "VIX",
                            "source": "yfinance_proxy",
                            "sourceLabel": "Yahoo Finance",
                            "sourceType": "unofficial_proxy",
                            "asOf": "2026-05-07T10:00:00+08:00",
                            "freshness": "delayed",
                            "isFallback": False,
                            "isStale": False,
                            "isPartial": False,
                            "isUnavailable": False,
                            "coverage": 1.0,
                            "confidenceWeight": 0.7,
                        }
                    ],
                },
                "coverageDiagnostics": {
                    "indicatorId": "vix_pressure",
                    "indicatorName": "VIX / 波动率压力",
                    "requiredInputs": ["VIX"],
                    "fulfilledInputs": ["VIX"],
                    "missingInputs": [],
                    "requiredProviderClass": "official_public.vix_or_volatility",
                    "configuredProviderAvailable": True,
                    "realSourceAvailable": False,
                    "proxyOnly": True,
                    "observationOnly": False,
                    "scoreContributionAllowed": False,
                    "scoreExclusionReason": "proxy_only_missing_real_source",
                    "requiredRealSourceForScore": True,
                    "proxyObservationOnlyReason": "proxy_only_missing_real_source",
                    "missingProviderReason": "requires_official_public.vix_or_volatility",
                    "paidDataLikelyRequired": False,
                    "sourceTier": "unofficial_public_api",
                    "freshness": "partial",
                    "trustLevel": "usable_with_caution",
                    "contributesToScore": False,
                    "scoreContribution": 0,
                    "capReason": "partial_coverage",
                    "degradationReason": "partial_coverage",
                    "activationHint": "proxy capped",
                },
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
    assert indicators["cn_hk_flows"]["evidence"]["isFallback"] is True
    assert indicators["cn_hk_flows"]["coverageDiagnostics"]["observationOnly"] is True
    assert indicators["cn_hk_flows"]["coverageDiagnostics"]["scoreContributionAllowed"] is False
    assert indicators["vix_pressure"]["status"] == "partial"
    assert indicators["vix_pressure"]["freshness"] == "delayed"
    assert indicators["vix_pressure"]["includedInScore"] is False
    assert indicators["vix_pressure"]["scoreContribution"] == 0
    assert indicators["vix_pressure"]["evidence"]["isPartial"] is True
    assert indicators["vix_pressure"]["coverageDiagnostics"]["proxyOnly"] is True
    assert indicators["vix_pressure"]["coverageDiagnostics"]["realSourceAvailable"] is False
    assert indicators["vix_pressure"]["coverageDiagnostics"]["scoreContributionAllowed"] is False
    assert indicators["vix_pressure"]["coverageDiagnostics"]["scoreExclusionReason"] == "proxy_only_missing_real_source"


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
