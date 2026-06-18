# -*- coding: utf-8 -*-
"""Endpoint guards for consumer API diagnostic redaction."""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import get_optional_current_user
from api.v1.endpoints import market
from tests.api.test_market_decision_cockpit_endpoint import _payload as _cockpit_payload


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
    ):
        assert marker not in serialized
        assert marker.lower() not in lowered


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


def test_options_decision_endpoint_omits_debug_ref_and_provider_reason_codes() -> None:
    from api.v1.endpoints import options

    app = FastAPI()
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
