# -*- coding: utf-8 -*-
"""API contract tests for the liquidity monitor endpoint."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.v1.endpoints.liquidity_monitor as liquidity_monitor
from api.v1.schemas.liquidity_monitor import LiquidityMonitorResponse
from src.services.liquidity_monitor_service import LiquidityMonitorService
from src.services.market_cache import MarketCache


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "liquidity_monitor"
CN_TZ = timezone(timedelta(hours=8))
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
        "liquidityImpulseSynthesis": {
            "liquidityImpulse": "contracting_liquidity",
            "impulseLabel": "Liquidity appears to be contracting",
            "subtype": "rates_driven_tightening",
            "confidence": 0.71,
            "confidenceLabel": "high",
            "pillarScores": {
                "dollar_pressure": 0.42,
                "rates_pressure": 0.63,
                "volatility_stress": 0.51,
            },
            "directionScore": -0.58,
            "dominantDrivers": [{"key": "liquidity_monitor:us_rates_pressure", "label": "US Rates / 利率压力"}],
            "counterEvidence": [],
            "dataGaps": [],
            "narrativeBullets": ["Rates and dollar pressure are dominating the current liquidity signal."],
            "evidenceQuality": {"scoringPillarCount": 3},
            "notInvestmentAdvice": True,
        },
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
    assert set(body) == {
        "endpoint",
        "generatedAt",
        "score",
        "freshness",
        "indicators",
        "liquidityImpulseSynthesis",
        "advisoryDisclosure",
        "sourceMetadata",
    }
    assert body["endpoint"] == "/api/v1/market/liquidity-monitor"
    assert body["score"]["regime"] == "supportive"
    assert set(body["sourceMetadata"]) == {"externalProviderCalls", "providerRuntimeChanged", "marketCacheMutation"}
    assert body["sourceMetadata"]["externalProviderCalls"] is False
    assert body["liquidityImpulseSynthesis"]["liquidityImpulse"] == "contracting_liquidity"
    assert body["indicators"][0]["evidence"]["source"] == "fred"
    assert body["indicators"][0]["evidence"]["inputs"][0]["sourceType"] == "official_public"
    diagnostics = body["indicators"][0]["coverageDiagnostics"]
    assert diagnostics["requiredProviderClass"] == "official_public.vix_or_volatility"
    assert diagnostics["realSourceAvailable"] is True
    assert diagnostics["scoreContributionAllowed"] is True


def test_liquidity_monitor_route_preserves_evidence_input_authority_metadata() -> None:
    app = FastAPI()
    app.include_router(liquidity_monitor.router, prefix="/api/v1/market")

    payload = {
        "endpoint": "/api/v1/market/liquidity-monitor",
        "generatedAt": "2026-05-07T10:00:00+08:00",
        "score": {
            "value": 50,
            "regime": "unavailable",
            "confidence": 0.2,
            "includedIndicatorCount": 0,
            "possibleIndicatorWeight": 43,
            "includedIndicatorWeight": 0,
        },
        "freshness": {
            "status": "delayed",
            "weakestIndicatorFreshness": "delayed",
            "latestAsOf": "2026-05-07T10:00:00+08:00",
        },
        "indicators": [
            {
                "key": "vix_pressure",
                "label": "VIX pressure",
                "status": "partial",
                "freshness": "delayed",
                "includedInScore": False,
                "scoreContribution": 0,
                "evidence": {
                    "contractVersion": "source_confidence_contract_v1",
                    "source": "yfinance_proxy",
                    "sourceLabel": "Yahoo Finance proxy",
                    "asOf": "2026-05-07T10:00:00+08:00",
                    "freshness": "partial",
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": True,
                    "isUnavailable": False,
                    "coverage": 1.0,
                    "confidenceWeight": 0.7,
                    "degradationReason": "proxy_only_missing_real_source",
                    "capReason": "proxy_only_missing_real_source",
                    "inputs": [
                        {
                            "key": "VIX",
                            "label": "VIX",
                            "source": "yfinance_proxy",
                            "sourceLabel": "Yahoo Finance proxy",
                            "sourceType": "unofficial_proxy",
                            "sourceTier": "unofficial_public_api",
                            "trustLevel": "usable_with_caution",
                            "asOf": "2026-05-07T10:00:00+08:00",
                            "freshness": "delayed",
                            "isFallback": False,
                            "isStale": False,
                            "isPartial": False,
                            "isUnavailable": False,
                            "observationOnly": False,
                            "sourceAuthorityAllowed": False,
                            "scoreContributionAllowed": False,
                            "sourceAuthorityReason": "proxy_only_missing_real_source",
                            "sourceAuthorityRouteRejected": True,
                            "routeRejectedReasonCodes": ["provider_forbidden_for_use_case"],
                            "officialSeriesId": "VIXCLS",
                            "officialObservationDate": "2026-05-06",
                            "officialAsOf": "2026-05-07T09:00:00+08:00",
                            "coverage": 1.0,
                            "confidenceWeight": 0.7,
                            "degradationReason": "proxy_only_missing_real_source",
                            "capReason": "proxy_only_missing_real_source",
                        },
                        {
                            "key": "fallback_liquidity_proxy",
                            "label": "Fallback liquidity proxy",
                            "source": "fallback",
                            "sourceLabel": "Static fallback",
                            "sourceType": "fallback_static",
                            "sourceTier": "static_fallback",
                            "trustLevel": "unavailable",
                            "asOf": "2026-05-07T10:00:00+08:00",
                            "freshness": "fallback",
                            "isFallback": True,
                            "isStale": False,
                            "isPartial": False,
                            "isUnavailable": True,
                            "observationOnly": True,
                            "sourceAuthorityAllowed": False,
                            "scoreContributionAllowed": False,
                            "sourceAuthorityReason": "fallback_not_score_grade",
                            "sourceAuthorityRouteRejected": False,
                            "routeRejectedReasonCodes": [],
                            "officialSeriesId": "FALLBACK_PROXY",
                            "officialObservationDate": "2026-05-06",
                            "officialAsOf": "2026-05-07T09:00:00+08:00",
                            "coverage": 0.0,
                            "confidenceWeight": 0.0,
                            "degradationReason": "fallback_source",
                            "capReason": "unavailable_source",
                        },
                    ],
                },
                "coverageDiagnostics": {
                    "indicatorId": "vix_pressure",
                    "indicatorName": "VIX pressure",
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
                    "capReason": "proxy_only_missing_real_source",
                    "degradationReason": "proxy_only_missing_real_source",
                    "sourceAuthorityRouteRejected": True,
                    "sourceAuthorityReason": "proxy_only_missing_real_source",
                    "routeRejectedReasonCodes": ["provider_forbidden_for_use_case"],
                    "activationHint": "proxy capped",
                },
            }
        ],
        "liquidityImpulseSynthesis": {
            "liquidityImpulse": "data_insufficient",
            "impulseLabel": "Data insufficient for a reliable liquidity call",
            "subtype": "data_insufficient",
            "confidence": 0.2,
            "confidenceLabel": "insufficient",
            "pillarScores": {},
            "directionScore": 0.0,
            "dominantDrivers": [],
            "counterEvidence": [],
            "dataGaps": [{"key": "liquidity_monitor:vix_pressure", "reason": "score_contribution_not_allowed"}],
            "narrativeBullets": ["Available evidence is degraded or non-score-eligible."],
            "evidenceQuality": {"proxyOnlyScoringCount": 0},
            "notInvestmentAdvice": True,
        },
        "advisoryDisclosure": "Advisory-only liquidity monitor output.",
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
    indicator = body["indicators"][0]
    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert indicator["coverageDiagnostics"]["scoreContributionAllowed"] is False
    assert indicator["coverageDiagnostics"]["contributesToScore"] is False

    proxy_input, fallback_input = indicator["evidence"]["inputs"]
    for evidence_input in (proxy_input, fallback_input):
        assert set(
            [
                "sourceAuthorityAllowed",
                "scoreContributionAllowed",
                "sourceAuthorityReason",
                "sourceAuthorityRouteRejected",
                "routeRejectedReasonCodes",
                "officialSeriesId",
                "officialObservationDate",
                "officialAsOf",
                "sourceLabel",
                "sourceTier",
                "trustLevel",
                "freshness",
                "asOf",
                "isFallback",
                "isUnavailable",
                "isPartial",
                "observationOnly",
            ]
        ).issubset(evidence_input)
        assert evidence_input["sourceAuthorityAllowed"] is False
        assert evidence_input["scoreContributionAllowed"] is False

    assert proxy_input["sourceLabel"] == "Yahoo Finance proxy"
    assert proxy_input["sourceTier"] == "unofficial_public_api"
    assert proxy_input["trustLevel"] == "usable_with_caution"
    assert proxy_input["freshness"] == "delayed"
    assert proxy_input["asOf"] == "2026-05-07T10:00:00+08:00"
    assert proxy_input["isFallback"] is False
    assert proxy_input["isUnavailable"] is False
    assert proxy_input["isPartial"] is False
    assert proxy_input["observationOnly"] is False
    assert proxy_input["sourceAuthorityReason"] == "proxy_only_missing_real_source"
    assert proxy_input["sourceAuthorityRouteRejected"] is True
    assert proxy_input["routeRejectedReasonCodes"] == ["provider_forbidden_for_use_case"]
    assert proxy_input["officialSeriesId"] == "VIXCLS"
    assert proxy_input["officialObservationDate"] == "2026-05-06"
    assert proxy_input["officialAsOf"] == "2026-05-07T09:00:00+08:00"

    assert fallback_input["sourceLabel"] == "Static fallback"
    assert fallback_input["sourceTier"] == "static_fallback"
    assert fallback_input["trustLevel"] == "unavailable"
    assert fallback_input["freshness"] == "fallback"
    assert fallback_input["asOf"] == "2026-05-07T10:00:00+08:00"
    assert fallback_input["isFallback"] is True
    assert fallback_input["isUnavailable"] is True
    assert fallback_input["isPartial"] is False
    assert fallback_input["observationOnly"] is True
    assert fallback_input["sourceAuthorityReason"] == "fallback_not_score_grade"
    assert fallback_input["sourceAuthorityRouteRejected"] is False
    assert fallback_input["routeRejectedReasonCodes"] == []
    assert fallback_input["officialSeriesId"] == "FALLBACK_PROXY"
    assert fallback_input["officialObservationDate"] == "2026-05-06"
    assert fallback_input["officialAsOf"] == "2026-05-07T09:00:00+08:00"


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
        "liquidityImpulseSynthesis": {
            "liquidityImpulse": "data_insufficient",
            "impulseLabel": "Data insufficient for a reliable liquidity call",
            "subtype": "data_insufficient",
            "confidence": 0.2,
            "confidenceLabel": "insufficient",
            "pillarScores": {
                "dollar_pressure": 0.0,
                "rates_pressure": 0.0,
                "volatility_stress": 0.0,
            },
            "directionScore": 0.0,
            "dominantDrivers": [],
            "counterEvidence": [],
            "dataGaps": [{"key": "liquidity_monitor:vix_pressure", "reason": "score_contribution_not_allowed"}],
            "narrativeBullets": ["Available evidence is degraded or non-score-eligible."],
            "evidenceQuality": {"dataGapCount": 1},
            "notInvestmentAdvice": True,
        },
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
    body = response.json()
    assert body["liquidityImpulseSynthesis"]["liquidityImpulse"] == "data_insufficient"
    assert body["liquidityImpulseSynthesis"]["dataGaps"]
    indicators = {item["key"]: item for item in body["indicators"]}
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
        payload = LiquidityMonitorResponse(**_load_fixture(fixture_name)).model_dump(exclude_none=True)

        with patch("api.v1.endpoints.liquidity_monitor.LiquidityMonitorService") as mock_service:
            mock_service.return_value.get_liquidity_monitor.return_value = payload
            response = TestClient(app).get("/api/v1/market/liquidity-monitor")

        assert response.status_code == 200
        assert response.json() == payload


def test_liquidity_monitor_route_accepts_authorized_licensed_source_tier() -> None:
    app = FastAPI()
    app.include_router(liquidity_monitor.router, prefix="/api/v1/market")

    payload = {
        "endpoint": "/api/v1/market/liquidity-monitor",
        "generatedAt": "2026-05-23T10:00:00+08:00",
        "score": {
            "value": 50,
            "regime": "unavailable",
            "confidence": 0.0,
            "includedIndicatorCount": 0,
            "possibleIndicatorWeight": 49,
            "includedIndicatorWeight": 0,
        },
        "freshness": {
            "status": "delayed",
            "weakestIndicatorFreshness": "delayed",
            "latestAsOf": "2026-05-23T10:00:00+08:00",
        },
        "indicators": [
            {
                "key": "us_etf_flow_proxy",
                "label": "US ETF 资金代理",
                "status": "partial",
                "freshness": "delayed",
                "includedInScore": False,
                "scoreContribution": 0,
                "scoreWeight": 5,
                "summary": "licensed feed projection",
                "updatedAt": "2026-05-23T10:00:00+08:00",
                "evidence": {
                    "contractVersion": "source_confidence_contract_v1",
                    "source": "polygon_us_grouped_daily",
                    "sourceLabel": "Polygon grouped daily US equities",
                    "asOf": "2026-05-23T10:00:00+08:00",
                    "freshness": "delayed",
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": False,
                    "isUnavailable": False,
                    "coverage": 1.0,
                    "confidenceWeight": 0.9,
                    "inputs": [
                        {
                            "key": "ETF",
                            "label": "ETF",
                            "source": "polygon_us_grouped_daily",
                            "sourceLabel": "Polygon grouped daily US equities",
                            "sourceType": "authorized_licensed_feed",
                            "sourceTier": "authorized_licensed_feed",
                            "trustLevel": "reliable",
                            "asOf": "2026-05-23T10:00:00+08:00",
                            "freshness": "delayed",
                            "isFallback": False,
                            "isStale": False,
                            "isPartial": False,
                            "isUnavailable": False,
                            "coverage": 1.0,
                            "confidenceWeight": 0.9,
                        }
                    ],
                },
                "coverageDiagnostics": {
                    "indicatorId": "us_etf_flow_proxy",
                    "indicatorName": "US ETF 资金代理",
                    "requiredInputs": ["ETF"],
                    "fulfilledInputs": ["ETF"],
                    "missingInputs": [],
                    "requiredProviderClass": "authorized.us_etf_flow",
                    "configuredProviderAvailable": True,
                    "realSourceAvailable": False,
                    "proxyOnly": False,
                    "observationOnly": False,
                    "scoreContributionAllowed": False,
                    "scoreExclusionReason": "licensed_feed_projection_test",
                    "requiredRealSourceForScore": True,
                    "proxyObservationOnlyReason": None,
                    "missingProviderReason": None,
                    "paidDataLikelyRequired": True,
                    "sourceTier": "authorized_licensed_feed",
                    "freshness": "delayed",
                    "trustLevel": "reliable",
                    "contributesToScore": False,
                    "scoreContribution": 0,
                    "capReason": "licensed_feed_projection_test",
                    "degradationReason": "licensed_feed_projection_test",
                    "sourceAuthorityRouteRejected": False,
                    "sourceAuthorityReason": None,
                    "routeRejectedReasonCodes": [],
                    "activationHint": "licensed feed projection",
                },
            }
        ],
        "liquidityImpulseSynthesis": {
            "liquidityImpulse": "neutral_liquidity",
            "impulseLabel": "Liquidity is mixed",
            "subtype": "observation_only",
            "confidence": 0.0,
            "confidenceLabel": "low",
            "pillarScores": {},
            "directionScore": 0.0,
            "dominantDrivers": [],
            "counterEvidence": [],
            "dataGaps": [],
            "narrativeBullets": [],
            "evidenceQuality": {},
            "notInvestmentAdvice": True,
        },
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
    assert response.json()["indicators"][0]["coverageDiagnostics"]["sourceTier"] == "authorized_licensed_feed"


def test_liquidity_monitor_route_returns_degraded_payload_when_reason_codes_are_malformed() -> None:
    app = FastAPI()
    app.include_router(liquidity_monitor.router, prefix="/api/v1/market")

    class _RouteDb:
        @staticmethod
        def get_market_overview_snapshot(_: str):
            return None

    service = LiquidityMonitorService(cache=MarketCache(), db=_RouteDb())
    now = datetime(2026, 5, 30, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "us_breadth",
        {
            "source": "authorized_feed",
            "freshness": "fallback",
            "updatedAt": now,
            "asOf": now,
            "items": [
                {
                    "symbol": "ADVANCERS",
                    "label": "Advancers",
                    "value": 100,
                    "source": "authorized_feed",
                    "sourceType": "authorized_licensed_feed",
                    "routeRejectedReasonCodes": 123,
                },
                {
                    "symbol": "DECLINERS",
                    "label": "Decliners",
                    "value": 200,
                    "source": "authorized_feed",
                    "sourceType": "authorized_licensed_feed",
                },
                {
                    "symbol": "UNCHANGED",
                    "label": "Unchanged",
                    "value": 10,
                    "source": "authorized_feed",
                    "sourceType": "authorized_licensed_feed",
                },
                {
                    "symbol": "ADVANCE_DECLINE_RATIO",
                    "label": "Advance / Decline Ratio",
                    "value": 0.5,
                    "source": "authorized_feed",
                    "sourceType": "authorized_licensed_feed",
                },
                {
                    "symbol": "NEW_HIGHS",
                    "label": "New Highs",
                    "value": 5,
                    "source": "authorized_feed",
                    "sourceType": "authorized_licensed_feed",
                },
                {
                    "symbol": "NEW_LOWS",
                    "label": "New Lows",
                    "value": 10,
                    "source": "authorized_feed",
                    "sourceType": "authorized_licensed_feed",
                },
                {
                    "symbol": "HIGH_LOW_RATIO",
                    "label": "High / Low Ratio",
                    "value": 0.5,
                    "source": "authorized_feed",
                    "sourceType": "authorized_licensed_feed",
                },
            ],
            "cacheBundleDiagnostics": {
                "scoreContributionAllowed": False,
                "realSourceAvailable": False,
                "reasonCodes": 456,
                "degradationReason": "provider_unavailable",
            },
        },
        ttl_seconds=30,
    )

    with patch("api.v1.endpoints.liquidity_monitor.LiquidityMonitorService", return_value=service):
        response = TestClient(app).get("/api/v1/market/liquidity-monitor")

    assert response.status_code == 200
    body = response.json()
    indicator = next(item for item in body["indicators"] if item["key"] == "us_breadth_proxy")
    assert body["score"]["regime"] == "unavailable"
    assert body["sourceMetadata"]["externalProviderCalls"] is False
    assert indicator["coverageDiagnostics"]["degradationReason"] == "fallback_source"
    assert indicator["coverageDiagnostics"]["routeRejectedReasonCodes"] == ["proxy_or_placeholder_not_authorized_breadth"]
    assert all(isinstance(code, str) for code in indicator["evidence"]["inputs"][0]["routeRejectedReasonCodes"])
