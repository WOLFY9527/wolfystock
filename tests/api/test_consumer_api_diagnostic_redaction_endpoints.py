# -*- coding: utf-8 -*-
"""Endpoint guards for consumer API diagnostic redaction."""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user, get_optional_current_user
from api.v1.endpoints import market, market_overview
from tests.api.test_market_decision_cockpit_endpoint import _payload as _cockpit_payload


FORBIDDEN_MARKET_DIAGNOSTIC_FIELDS = (
    "diagnosticOnly",
    "endpointHost",
    "apiKeyPresent",
    "providerAttempted",
    "providerName",
    "providerClass",
    "requiredProviderClass",
    "activationHint",
    "officialOverlayFailureDetails",
    "exceptionClass",
    "exceptionChain",
    "timeoutSeconds",
    "caBundleSource",
    "requestedSeries",
    "attemptedAt",
    "calendarAssumption",
    "freshnessPolicy",
    "maxAcceptedLagDays",
    "maxAcceptedBusinessLagDays",
    "requestId",
    "traceId",
    "cacheKey",
)


def _assert_no_forbidden_consumer_terms(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    lowered = serialized.lower()
    for marker in (
        "providerTier",
        "providerName",
        "sourceRef",
        "sourceType",
        "sourceTier",
        "sourceAuthorityRouter",
        "reasonCodes",
        "debugRef",
        "requestId",
        "traceId",
        "rawPayload",
        "raw_provider_payload",
        "rawJson",
        "schemaVersion",
        "policyVersion",
        "fallback_source",
        "internalRoute",
        "diagnosticRef",
        "authorityDiagnostics",
        "provider_timeout",
        "tier_1_configured",
        "unofficial_proxy",
        "credential",
        "credentials",
        "api_key",
        "API_KEY",
        "token",
        "env",
        "missing_api_key",
        *FORBIDDEN_MARKET_DIAGNOSTIC_FIELDS,
    ):
        assert marker not in serialized
        assert marker.lower() not in lowered


def _admin_user() -> CurrentUser:
    return CurrentUser(
        user_id="admin-1",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("ops:providers:read",),
    )


class _DiagnosticCockpitService:
    def get_decision_cockpit(self, *, actor=None) -> dict[str, Any]:
        payload = _cockpit_payload()
        payload["providerTier"] = "tier_1_configured"
        payload["sourceAuthorityRouter"] = {"providerName": "raw-provider"}
        payload["researchQueuePreview"]["degradedState"]["reasonCodes"] = [
            "benchmark_missing",
            "provider_timeout",
        ]
        payload["debugRef"] = "market:decision-cockpit"
        payload["requestId"] = "REQ-raw"
        payload["rawPayload"] = {"sourceType": "unofficial_proxy"}
        return payload


class _LeakyOverviewService:
    def _payload(self) -> dict[str, Any]:
        return {
            "panel_name": "VolatilityCard",
            "status": "success",
            "freshness": "delayed",
            "warning": "数据不足，暂不形成结论。",
            "diagnosticOnly": True,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "items": [
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 18.2,
                    "freshness": "delayed",
                    "providerAttempted": True,
                    "providerName": "fred",
                    "providerClass": "official_daily",
                    "requiredProviderClass": "official_public.fed_liquidity",
                    "activationHint": "set_fred_api_key",
                    "sourceField": "sourceAuthorityAllowed",
                    "hint": "requiredProviderClass official_public.fed_liquidity is required",
                    "officialOverlayFailureDetails": {
                        "endpointHost": "api.stlouisfed.org",
                        "apiKeyPresent": True,
                        "requestedSeries": "VIXCLS",
                        "exceptionClass": "SSLCertVerificationError",
                        "exceptionChain": ["URLError", "SSLCertVerificationError"],
                        "timeoutSeconds": 0.5,
                        "caBundleSource": "certifi",
                        "attemptedAt": "2026-05-19T00:00:00Z",
                    },
                    "sourceFreshnessEvidence": {
                        "freshness": "delayed",
                        "freshnessPolicy": "official_daily_us_weekday_t_plus_1",
                        "calendarAssumption": "US/Eastern weekdays; holidays not modeled",
                        "maxAcceptedLagDays": 3,
                        "maxAcceptedBusinessLagDays": 1,
                    },
                    "nested": {
                        "diagnosticOnly": True,
                        "requestId": "REQ-raw",
                        "traceId": "TRACE-raw",
                        "cacheKey": "market:vix",
                        "reason": "sourceAuthorityAllowed blocked this observation",
                        "evidenceGaps": [
                            {
                                "label": "证据来源级别不足",
                                "category": "evidence",
                                "sourceField": "sourceAuthorityAllowed",
                            }
                        ],
                    },
                }
            ],
        }

    def get_volatility(self, *, actor=None) -> dict[str, Any]:
        return self._payload()

    def get_indices(self, *, actor=None) -> dict[str, Any]:
        return self._payload()

    def get_sentiment(self, *, actor=None) -> dict[str, Any]:
        return self._payload()

    def get_funds_flow(self, *, actor=None) -> dict[str, Any]:
        return self._payload()

    def get_macro(self, *, actor=None) -> dict[str, Any]:
        return self._payload()


class _LeakyMarketOverviewService(_LeakyOverviewService):
    def get_rates(self, *, actor=None) -> dict[str, Any]:
        return self._payload()

    def get_us_breadth(self, *, actor=None) -> dict[str, Any]:
        payload = self._payload()
        payload["readiness"] = "degraded"
        payload["items"][0]["freshness"] = "stale"
        return payload


class _DiagnosticDataReadiness:
    def to_dict(self) -> dict[str, Any]:
        return {
            "diagnosticOnly": True,
            "providerRuntimeCalled": False,
            "networkCallsEnabled": False,
            "checks": [
                {
                    "id": "provider",
                    "providerName": "operator-diagnostic",
                    "endpointHost": "ops.example.invalid",
                }
            ],
        }


class _LeakyRotationRadarService:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def get_rotation_radar(self, *, market: str = "US") -> dict[str, Any]:
        return {
            "endpoint": "/api/v1/market/rotation-radar",
            "market": market,
            "generatedAt": "2026-05-19T00:00:00Z",
            "metadata": {
                "schemaVersion": "market_rotation_radar_phase4_v1",
                "quoteProvider": {
                    "status": "partial",
                    "providerDiagnostics": {
                        "providerName": "alpaca",
                        "endpointHost": "data.alpaca.markets",
                        "apiKeyPresent": True,
                        "timeoutSeconds": 2.5,
                    },
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                },
            },
            "consumerEvidenceSnapshot": {
                "freshness": "partial",
                "providerState": {
                    "status": "partial",
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "providerName": "alpaca",
                    "reasonCodes": ["credentials"],
                },
            },
            "themes": [
                {
                    "id": "ai",
                    "name": "AI",
                    "freshness": "delayed",
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "reasonCodes": ["credentials"],
                    "providerAttempted": True,
                    "breadthEvidence": {
                        "scoreContributionAllowed": False,
                        "diagnosticOnly": True,
                    },
                }
            ],
        }


def test_market_decision_cockpit_endpoint_projects_consumer_safe_diagnostics(monkeypatch) -> None:
    monkeypatch.setattr(market, "MarketDecisionCockpitService", lambda: _DiagnosticCockpitService())
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    app.dependency_overrides[get_optional_current_user] = lambda: None

    response = TestClient(app).get("/api/v1/market/decision-cockpit")

    assert response.status_code == 200
    payload = response.json()
    _assert_no_forbidden_consumer_terms(payload)
    assert payload["consumerSafeSourceLabel"] == "部分数据源暂不可用"
    assert payload["missingInputs"]
    assert payload["evidenceGaps"]
    assert payload["researchNextSteps"]


def test_market_overview_public_endpoints_project_consumer_safe_diagnostics(monkeypatch) -> None:
    monkeypatch.setattr(market_overview, "MarketOverviewService", lambda: _LeakyOverviewService())
    app = FastAPI()
    app.include_router(market_overview.router, prefix="/api/v1/market-overview")
    app.dependency_overrides[get_optional_current_user] = lambda: None

    with TestClient(app) as client:
        for path in ("/indices", "/volatility", "/sentiment", "/funds-flow", "/macro"):
            response = client.get(f"/api/v1/market-overview{path}")
            assert response.status_code == 200
            payload = response.json()
            _assert_no_forbidden_consumer_terms(payload)
            serialized = json.dumps(payload, ensure_ascii=False)
            assert "requiredProviderClass" not in serialized
            assert "sourceAuthorityAllowed" not in serialized
            assert payload["freshness"] == "delayed"
            assert payload["items"][0]["freshness"] == "delayed"
            assert payload["warning"] == "数据不足，暂不形成结论。"
            assert payload["items"][0]["sourceFreshnessEvidence"]["freshness"] == "delayed"
            assert payload["items"][0]["sourceField"] == "evidence"
            assert payload["items"][0]["nested"]["evidenceGaps"][0]["sourceField"] == "evidence"
            assert payload["noAdviceDisclosure"]


def test_market_overview_indices_remains_public_and_sanitized(monkeypatch) -> None:
    monkeypatch.setattr(market_overview, "MarketOverviewService", lambda: _LeakyOverviewService())
    app = FastAPI()
    app.include_router(market_overview.router, prefix="/api/v1/market-overview")

    response = TestClient(app).get("/api/v1/market-overview/indices")

    assert response.status_code == 200
    payload = response.json()
    _assert_no_forbidden_consumer_terms(payload)
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "requiredProviderClass" not in serialized
    assert "sourceAuthorityAllowed" not in serialized
    assert payload["items"][0]["sourceField"] == "evidence"
    assert payload["noAdviceDisclosure"]


def test_market_public_endpoint_projects_provider_diagnostics_without_hiding_quality_labels(
    monkeypatch,
) -> None:
    monkeypatch.setattr(market, "MarketOverviewService", lambda: _LeakyMarketOverviewService())
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    app.dependency_overrides[get_optional_current_user] = lambda: None

    with TestClient(app) as client:
        response = client.get("/api/v1/market/rates")
        breadth_response = client.get("/api/v1/market/us-breadth")

    assert response.status_code == 200
    payload = response.json()
    _assert_no_forbidden_consumer_terms(payload)
    assert payload["freshness"] == "delayed"
    assert payload["items"][0]["freshness"] == "delayed"
    assert payload["warning"] == "数据不足，暂不形成结论。"

    assert breadth_response.status_code == 200
    breadth_payload = breadth_response.json()
    _assert_no_forbidden_consumer_terms(breadth_payload)
    assert breadth_payload["readiness"] == "degraded"
    assert breadth_payload["items"][0]["freshness"] == "stale"


def test_market_operator_diagnostic_routes_require_provider_read_and_preserve_admin_diagnostics(
    monkeypatch,
) -> None:
    monkeypatch.setattr(market, "build_market_data_readiness_diagnostics", lambda **_: _DiagnosticDataReadiness())
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    app.dependency_overrides[get_current_user] = lambda: (_ for _ in ()).throw(
        HTTPException(status_code=401, detail={"error": "unauthorized"})
    )

    with TestClient(app) as client:
        unauthenticated = client.get("/api/v1/market/data-readiness")

    assert unauthenticated.status_code == 401

    app.dependency_overrides[get_current_user] = _admin_user
    with TestClient(app) as client:
        admin_response = client.get("/api/v1/market/data-readiness")

    assert admin_response.status_code == 200
    payload = admin_response.json()
    assert payload["diagnosticOnly"] is True
    assert payload["checks"][0]["providerName"] == "operator-diagnostic"
    assert payload["checks"][0]["endpointHost"] == "ops.example.invalid"


def test_market_rotation_radar_public_route_removes_provider_diagnostics(monkeypatch) -> None:
    monkeypatch.setattr(market, "MarketRotationRadarService", _LeakyRotationRadarService)
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    app.dependency_overrides[get_optional_current_user] = lambda: None

    with TestClient(app) as client:
        response = client.get("/api/v1/market/rotation-radar")

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, ensure_ascii=False)
    for marker in FORBIDDEN_MARKET_DIAGNOSTIC_FIELDS:
        assert marker not in serialized
        assert marker.lower() not in serialized.lower()
    for marker in ("credential", "credentials", "API_KEY", "api_key", "token", "env"):
        assert marker not in serialized
        assert marker.lower() not in serialized.lower()
    assert payload["metadata"]["schemaVersion"] == "market_rotation_radar_phase4_v1"
    assert payload["metadata"]["quoteProvider"]["status"] == "partial"
    assert payload["consumerEvidenceSnapshot"]["freshness"] == "partial"
    assert payload["themes"][0]["freshness"] == "delayed"


def test_options_decision_endpoint_omits_debug_ref_and_provider_reason_codes() -> None:
    from api.v1.endpoints import options

    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id="options-member",
        username="options-member",
        display_name="Options Member",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )
    app.include_router(options.router, prefix="/api/v1/options")
    response = TestClient(app).post(
        "/api/v1/options/decision/evaluate",
        json={
            "symbol": "TEM",
            "strategy": "long_call",
            "expiration": "2026-06-19",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "riskBudget": 600,
            "forceRefresh": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    _assert_no_forbidden_consumer_terms(payload)
    assert "failClosedReasonCodes" not in payload
    assert "debugRef" not in json.dumps(payload, ensure_ascii=False)
    assert payload["evidenceGaps"]
    assert payload["researchNextSteps"]
