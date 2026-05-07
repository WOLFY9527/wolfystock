# -*- coding: utf-8 -*-
"""Public API response safety matrix for launch-exposed surfaces."""

from __future__ import annotations

import json
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import src.auth as auth
from api.middlewares.auth import add_auth_middleware
from api.v1 import api_v1_router
from api.v1.endpoints import options, scanner


FORBIDDEN_SECRET_MARKERS = (
    "raw-secret-token",
    "raw-password-value",
    "raw-api-key-value",
    "raw-cookie-value",
    "raw-session-value",
    "provider-credential-value",
    "broker-credential-value",
    "sk-public-safety-fixture",
)
FORBIDDEN_INTERNAL_MARKERS = (
    "raw_prompt",
    "system prompt",
    "provider_payload",
    "rawproviderpayload",
    "raw_payload",
    "debug_schema",
    "debugschema",
    "traceback",
    "stack trace",
    "internal exception",
)
FORBIDDEN_ADVICE_MARKERS = (
    "place order",
    "submit order",
    "buy now",
    "sell now",
    "guaranteed",
    "must buy",
    "must sell",
    "稳赚",
    "必买",
    "下单",
    "立即买入",
    "立即卖出",
)


def _json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _assert_public_surface_safe(payload: object) -> None:
    text = _json_text(payload).lower()
    for marker in (*FORBIDDEN_SECRET_MARKERS, *FORBIDDEN_INTERNAL_MARKERS, *FORBIDDEN_ADVICE_MARKERS):
        assert marker.lower() not in text


def _options_client() -> TestClient:
    app = FastAPI()
    app.include_router(options.router, prefix="/api/v1/options")
    return TestClient(app)


def _scanner_client() -> TestClient:
    app = FastAPI()
    app.include_router(scanner.router, prefix="/api/v1/scanner")
    return TestClient(app)


def _auth_guarded_client() -> TestClient:
    app = FastAPI()
    add_auth_middleware(app)
    app.include_router(api_v1_router)
    return TestClient(app)


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._password_hash_value = None
    auth._rate_limit = {}
    auth._admin_reauth_markers = {}


def test_launch_surface_route_inventory_remains_stable_and_fixture_safe() -> None:
    app = FastAPI()
    app.include_router(api_v1_router)
    routes = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }

    expected_matrix_routes = {
        ("POST", "/api/v1/analysis/preview"),
        ("GET", "/api/v1/options/underlyings/{symbol}/summary"),
        ("GET", "/api/v1/options/underlyings/{symbol}/chain"),
        ("POST", "/api/v1/options/decision/evaluate"),
        ("GET", "/api/v1/scanner/themes"),
        ("POST", "/api/v1/scanner/themes"),
        ("GET", "/api/v1/admin/users"),
        ("GET", "/api/v1/admin/providers/circuits"),
        ("GET", "/api/v1/admin/logs/storage/summary"),
    }

    assert expected_matrix_routes <= routes


def test_unauthenticated_admin_routes_fail_closed_with_sanitized_errors() -> None:
    _reset_auth_globals()
    client = _auth_guarded_client()
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
            responses = [
                client.get("/api/v1/admin/users"),
                client.get("/api/v1/admin/providers/circuits"),
                client.get("/api/v1/admin/logs/storage/summary"),
            ]

        assert [response.status_code for response in responses] == [401, 401, 401]
        for response in responses:
            assert response.json() == {"error": "unauthorized", "message": "Login required"}
            _assert_public_surface_safe(response.json())
    finally:
        client.close()
        _reset_auth_globals()


def test_options_launch_surface_matrix_is_fixture_backed_explicit_and_safe() -> None:
    client = _options_client()
    try:
        responses = [
            client.get("/api/v1/options/underlyings/TEM/summary", params={"forceRefresh": "true"}),
            client.get("/api/v1/options/underlyings/TEM/chain", params={"forceRefresh": "true"}),
            client.post(
                "/api/v1/options/decision/evaluate",
                json={
                    "symbol": "TEM",
                    "strategy": "bull_call_spread",
                    "expiration": "2026-06-19",
                    "targetPrice": 65,
                    "targetDate": "2026-06-19",
                    "riskBudget": 600,
                    "forceRefresh": True,
                },
            ),
        ]

        assert [response.status_code for response in responses] == [200, 200, 200]
        summary, chain, decision = [response.json() for response in responses]

        assert summary["metadata"]["fixtureBacked"] is True
        assert summary["metadata"]["noExternalCalls"] is True
        assert summary["metadata"]["noOrderPlacement"] is True
        assert summary["limitations"]["dataMayBeDelayedOrStale"] is True
        assert chain["metadata"]["providerName"] == "synthetic_fixture"
        assert chain["metadata"]["liveProviderEnabled"] is False
        assert all(item["dataQuality"]["tradeable"] is False for item in [*chain["calls"], *chain["puts"]])
        assert decision["metadata"]["noExternalCalls"] is True
        assert decision["metadata"]["noOrderPlacement"] is True
        assert "not personalized financial advice" in decision["noAdviceDisclosure"]

        for payload in (summary, chain, decision):
            _assert_public_surface_safe(payload)
    finally:
        client.close()


def test_options_live_provider_request_fails_closed_with_sanitized_error() -> None:
    client = _options_client()
    try:
        response = client.post(
            "/api/v1/options/decision/evaluate",
            json={
                "symbol": "TEM",
                "marketDataProvider": "tradier",
                "strategy": "bull_call_spread",
                "expiration": "2026-06-19",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
                "riskBudget": 600,
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == {
            "error": "options_provider_disabled",
            "message": "Requested Options Lab provider is fixture-only, disabled, or not implemented.",
        }
        _assert_public_surface_safe(response.json())
    finally:
        client.close()


def test_scanner_public_theme_generation_does_not_echo_raw_prompt_or_secret_markers() -> None:
    client = _scanner_client()
    raw_prompt = (
        "Find White House policy stocks but never echo raw_prompt system prompt "
        "token=raw-secret-token password=raw-password-value api_key=raw-api-key-value "
        "cookie=raw-cookie-value Traceback provider_payload debug_schema guaranteed must buy 必买 下单 "
        "place order buy now sell now 立即买入 立即卖出"
    )
    try:
        response = client.post(
            "/api/v1/scanner/themes",
            json={
                "id": "public_surface_prompt_guard",
                "label": "Public Surface Prompt Guard",
                "market": "us",
                "prompt": raw_prompt,
                "manual_symbols": ["MSFT"],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["theme"]["source"] == "ai_generated"
        assert payload["theme"]["requires_manual_maintenance"] is True
        assert payload["suggestions"]
        _assert_public_surface_safe(payload)
    finally:
        client.close()
