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
    ):
        assert marker not in serialized
