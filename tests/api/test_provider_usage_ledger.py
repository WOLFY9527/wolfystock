# -*- coding: utf-8 -*-
"""Read-only provider usage ledger API tests."""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import provider_usage_ledger
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
from src.services.provider_usage_ledger import ProviderUsageEvent, get_provider_usage_ledger


def _admin_with_provider_read() -> CurrentUser:
    return CurrentUser(
        user_id=BOOTSTRAP_ADMIN_USER_ID,
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("ops:providers:read",),
    )


def _admin_without_provider_read() -> CurrentUser:
    return CurrentUser(
        user_id=BOOTSTRAP_ADMIN_USER_ID,
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("ops:logs:read",),
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


def _client(user_factory) -> TestClient:
    app = FastAPI()
    app.include_router(provider_usage_ledger.router, prefix="/api/v1/admin")
    app.dependency_overrides[get_current_user] = user_factory
    return TestClient(app)


def setup_function() -> None:
    get_provider_usage_ledger().clear_for_tests()


def teardown_function() -> None:
    get_provider_usage_ledger().clear_for_tests()


def test_provider_usage_ledger_endpoint_requires_provider_read_capability() -> None:
    regular_client = _client(_regular_user)
    regular_response = regular_client.get("/api/v1/admin/provider-usage-ledger")
    assert regular_response.status_code == 403

    no_capability_client = _client(_admin_without_provider_read)
    no_capability_response = no_capability_client.get("/api/v1/admin/provider-usage-ledger")
    assert no_capability_response.status_code == 403
    assert "ops:providers:read" not in no_capability_response.text


def test_provider_usage_ledger_endpoint_returns_sanitized_events_and_summary() -> None:
    ledger = get_provider_usage_ledger()
    ledger.record(
        ProviderUsageEvent(
            research_mode="quick",
            symbol="ORCL",
            market="us",
            category="quote",
            provider="alpaca",
            action="timeout",
            outcome="failed",
            reason_code="timeout token=SECRET",
            metadata={
                "api_key": "SECRET",
                "raw_payload": {"price": 1},
                "safe": "visible",
            },
        )
    )
    ledger.record(
        ProviderUsageEvent(
            research_mode="deep",
            category="news",
            provider="gnews",
            action="success",
            outcome="ok",
        )
    )

    client = _client(_admin_with_provider_read)
    response = client.get(
        "/api/v1/admin/provider-usage-ledger",
        params={"limit": 5, "researchMode": "quick", "windowSeconds": 3600},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["readOnly"] is True
    assert payload["metadata"]["durableStorage"] is False
    assert payload["metadata"]["externalProviderCalls"] is False
    assert len(payload["events"]) == 1
    assert payload["events"][0]["researchMode"] == "quick"
    assert payload["events"][0]["metadata"] == {"safe": "visible"}
    assert payload["summary"]["timeout"] == 1

    dumped = json.dumps(payload, sort_keys=True)
    assert "SECRET" not in dumped
    assert "api_key" not in dumped
    assert "raw_payload" not in dumped
