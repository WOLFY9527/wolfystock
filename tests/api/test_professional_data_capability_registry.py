# -*- coding: utf-8 -*-
"""API tests for the professional data capability registry."""

from __future__ import annotations

import json
from typing import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import market


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


def _admin_without_capability() -> CurrentUser:
    return CurrentUser(
        user_id="admin-2",
        username="ops",
        display_name="Ops",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("users:read",),
    )


def _regular_user() -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="alice",
        display_name="Alice",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


def _client(user_factory: Callable[[], CurrentUser] | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    if user_factory is not None:
        app.dependency_overrides[get_current_user] = user_factory
    return TestClient(app)


def test_professional_data_capability_consumer_route_is_safe() -> None:
    with _client() as client:
        response = client.get("/api/v1/market/professional-data-capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["consumerSafe"] is True
    assert "options_structure" in payload["categories"]
    assert all("adminDiagnostics" not in item for item in payload["capabilities"])
    capabilities = {
        item["capabilityId"]: item
        for item in payload["capabilities"]
    }
    earnings_calendar = capabilities["stock.earnings_calendar"]
    assert earnings_calendar["status"] == "configured_missing"
    assert earnings_calendar["earningsCalendarReadiness"]["overallState"] == "not_configured"
    assert earnings_calendar["earningsCalendarReadiness"]["components"]["nextEarningsDate"]["state"] == "not_configured"
    breadth = capabilities["market.breadth_readiness"]
    readiness = breadth["readiness"]
    assert readiness["contractVersion"] == "market_breadth_readiness_v1"
    assert readiness["readinessStates"] == [
        "available",
        "missing",
        "stale",
        "not_configured",
        "disabled_by_flag",
    ]
    assert {item["measureId"] for item in readiness["measures"]} == {
        "advance_decline",
        "new_highs_lows",
        "percent_above_ma",
        "sector_participation",
        "volume_breadth",
        "equal_weight_cap_weight_proxy",
    }
    assert {item["market"] for item in readiness["markets"]} == {"US", "CN", "HK"}
    assert all(item["state"] != "available" for item in readiness["measures"])
    assert readiness["scoreEligible"] is False
    for capability_id in (
        "stock.news",
        "market.news",
        "events.earnings_calendar",
        "macro.policy_catalyst",
    ):
        assert capability_id in capabilities
        assert capabilities[capability_id]["sourceLabel"] == (
            "News/catalyst readiness registry"
        )
    assert capabilities["stock.news"]["status"] == "configured_missing"
    assert capabilities["market.news"]["status"] == "configured_missing"
    assert capabilities["events.earnings_calendar"]["status"] == "configured_missing"
    assert capabilities["macro.policy_catalyst"]["status"] == "degraded"
    assert "headline" not in json.dumps(
        [capabilities["stock.news"], capabilities["market.news"]],
        ensure_ascii=False,
    ).lower()

    serialized = json.dumps(payload, ensure_ascii=False)
    lowered = serialized.lower()
    for marker in (
        "requiredProviderClass",
        "sourceAuthorityAllowed",
        "scoreContributionAllowed",
        "providerClass",
        "providerName",
        "providerAttempted",
        "sourceAuthorityRouter",
        "endpointHost",
        "apiKeyPresent",
        "exceptionClass",
        "exceptionChain",
        "requestId",
        "traceId",
        "cacheKey",
        "rawPayload",
        "raw_payload",
        "credential",
        "token",
        "env",
        "stackTrace",
        "breadthScore",
        "breadthThrust",
        "participationScore",
        "adLine",
    ):
        assert marker not in serialized
        assert marker.lower() not in lowered


def test_professional_data_capability_admin_route_is_gated() -> None:
    with _client(_regular_user) as client:
        response = client.get("/api/v1/market/professional-data-capabilities/admin")
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "admin_required"

    with _client(_admin_without_capability) as client:
        response = client.get("/api/v1/market/professional-data-capabilities/admin")
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "admin_capability_required"


def test_professional_data_capability_admin_route_includes_bounded_diagnostics() -> None:
    with _client(_admin_user) as client:
        response = client.get("/api/v1/market/professional-data-capabilities/admin")

    assert response.status_code == 200
    payload = response.json()
    assert payload["consumerSafe"] is False
    assert all("adminDiagnostics" in item for item in payload["capabilities"])

    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for marker in (
        "apikeypresent",
        "endpointhost",
        "exceptionchain",
        "rawpayload",
        "raw_payload",
        "credential",
        "token",
        "requestid",
        "traceid",
        "cachekey",
        "stacktrace",
    ):
        assert marker not in serialized
