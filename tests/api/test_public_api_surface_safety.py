# -*- coding: utf-8 -*-
"""Public API response safety matrix for launch-exposed surfaces."""

from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import src.auth as auth
from api.middlewares.auth import add_auth_middleware
from api.v1 import api_v1_router
from api.v1.endpoints import options, scanner


ABUSE_REHEARSAL_SECRET_BODY = "raw-abuse-body-token"
ABUSE_REHEARSAL_COOKIE = "raw-abuse-session-cookie"
ABUSE_REHEARSAL_BEARER = "raw-abuse-bearer-token"
ABUSE_REHEARSAL_DSN = "postgres://raw-user:raw-password@db.example.test/wolfystock"
ABUSE_REHEARSAL_DEBUG_PAYLOAD = "Traceback raw stack trace debug payload"

FORBIDDEN_SECRET_MARKERS = (
    "raw-secret-token",
    "raw-password-value",
    "raw-api-key-value",
    "raw-cookie-value",
    "raw-session-value",
    "provider-credential-value",
    "broker-credential-value",
    "sk-public-safety-fixture",
    ABUSE_REHEARSAL_SECRET_BODY,
    ABUSE_REHEARSAL_COOKIE,
    ABUSE_REHEARSAL_BEARER,
    ABUSE_REHEARSAL_DSN,
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
    "debug payload",
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
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROUTE_CLASSIFICATION_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "auth" / "backend_route_capability_inventory.json"
DOCS_AND_SCHEMA_CLASSIFICATIONS = {
    ("GET", "/docs"): "public_static_docs",
    ("GET", "/redoc"): "public_static_docs",
    ("GET", "/openapi.json"): "debug_or_schema_surface",
}
LEGACY_UNSUPPORTED_OPENAPI_PATH = "/api/v1/openapi.json"
DIAGNOSTIC_ROUTES_EXCLUDED_FROM_SAFE_BYPASS = {
    ("GET", "/api/v1/market/data-readiness"),
    ("GET", "/api/v1/market/cn-provider-health"),
    ("GET", "/api/v1/agent/status"),
    ("GET", "/api/v1/agent/models"),
    ("GET", "/api/v1/agent/provider-health"),
}
OPTIONS_FIXTURE_PUBLIC_API_SURFACES = {
    ("GET", "/api/v1/options/underlyings/{symbol}/summary"),
    ("GET", "/api/v1/options/underlyings/{symbol}/chain"),
    ("POST", "/api/v1/options/decision/evaluate"),
}


def _json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _route_surface_classifications() -> dict[tuple[str, str], str]:
    fixture = json.loads(BACKEND_ROUTE_CLASSIFICATION_FIXTURE.read_text(encoding="utf-8"))
    return {
        (entry["method"], entry["path"]): entry["surface_classification"]
        for entry in fixture["route_surface_classifications"]
    }


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


def _limiter_probe_client() -> TestClient:
    app = FastAPI()
    add_auth_middleware(app)

    @app.get("/api/v1/limiter-probe/fails")
    async def limiter_probe_fails():
        return JSONResponse(status_code=422, content={"error": "probe_validation_failed"})

    return TestClient(app)


def _limiter_infra_client() -> TestClient:
    app = FastAPI()
    add_auth_middleware(app)

    @app.get("/api/health")
    async def api_health():
        return {"status": "ok"}

    @app.get("/health")
    async def root_health():
        return {"status": "ok"}

    @app.get("/api/v1/limiter-probe/fails")
    async def limiter_probe_fails():
        return JSONResponse(status_code=422, content={"error": "probe_validation_failed"})

    return TestClient(app)


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._password_hash_value = None
    auth._rate_limit = {}
    auth._admin_reauth_markers = {}


def _reset_public_limiter_state_if_available() -> None:
    try:
        from api.middlewares.public_abuse_limiter import reset_public_api_abuse_limiter_state
    except ModuleNotFoundError:
        return
    reset_public_api_abuse_limiter_state()


def _limiter_snapshot() -> dict[str, object]:
    from api.middlewares.public_abuse_limiter import get_public_api_abuse_limiter_snapshot

    return get_public_api_abuse_limiter_snapshot()


def _prime_hot_public_bucket(client: TestClient, ip_address: str, *, auth_enabled: bool = False) -> None:
    with patch.object(auth, "_is_auth_enabled_from_env", return_value=auth_enabled):
        response = client.post(
            "/api/v1/options/decision/evaluate",
            content='{"symbol":"TEM"',
            headers={
                "content-type": "application/json",
                "X-Forwarded-For": ip_address,
            },
        )

    assert response.status_code == 422
    assert _limiter_snapshot()["limitedBucketCount"] == 1


def _liquidity_monitor_fallback_payload() -> dict[str, object]:
    return {
        "endpoint": "/api/v1/market/liquidity-monitor",
        "generatedAt": "2026-05-15T10:00:00+08:00",
        "score": {
            "value": 50,
            "regime": "unavailable",
            "confidence": 0.0,
            "includedIndicatorCount": 0,
            "possibleIndicatorWeight": 43,
            "includedIndicatorWeight": 0,
        },
        "freshness": {
            "status": "fallback",
            "weakestIndicatorFreshness": "fallback",
            "latestAsOf": "2026-05-15T10:00:00+08:00",
        },
        "indicators": [],
        "liquidityImpulseSynthesis": {
            "liquidityImpulse": "data_insufficient",
            "impulseLabel": "Data insufficient for a reliable liquidity call",
            "subtype": "data_insufficient",
            "confidence": 0.0,
            "confidenceLabel": "insufficient",
            "pillarScores": {
                "dollar_pressure": 0.0,
                "rates_pressure": 0.0,
                "volatility_stress": 0.0,
            },
            "directionScore": 0.0,
            "dominantDrivers": [],
            "counterEvidence": [],
            "dataGaps": [{"key": "liquidity_monitor:fallback", "reason": "fallback_payload"}],
            "narrativeBullets": ["Fallback payload preserves route availability without reliable liquidity evidence."],
            "evidenceQuality": {"dataGapCount": 1},
            "notInvestmentAdvice": True,
        },
        "advisoryDisclosure": "仅用于观察市场流动性环境，非买卖建议，不触发扫描、回测或组合动作。",
        "sourceMetadata": {
            "externalProviderCalls": False,
            "providerRuntimeChanged": False,
            "marketCacheMutation": False,
        },
    }


def _format_warning_messages(caught: list[warnings.WarningMessage]) -> list[str]:
    return [
        f"{warning.category.__name__}: {warning.message}"
        for warning in caught
    ]


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
        ("GET", "/api/v1/admin/mission-control"),
        ("GET", "/api/v1/admin/providers/circuits"),
        ("GET", "/api/v1/admin/logs/storage/summary"),
    }

    assert expected_matrix_routes <= routes


def test_docs_openapi_and_backend_diagnostics_have_explicit_surface_classification() -> None:
    classifications = _route_surface_classifications()

    for signature, expected in DOCS_AND_SCHEMA_CLASSIFICATIONS.items():
        assert classifications[signature] == expected

    assert classifications[("POST", "/api/v1/agent/chat")] == "authenticated_member"
    assert classifications[("POST", "/api/v1/agent/chat/send")] == "admin_capability_required"
    assert classifications[("GET", "/api/v1/scanner/watchlists/today")] == "admin_capability_required"
    assert classifications[("GET", "/api/v1/scanner/watchlists/recent")] == "admin_capability_required"
    assert classifications[("GET", "/api/v1/scanner/status")] == "admin_capability_required"
    assert classifications[("GET", "/api/v1/usage/summary")] == "admin_capability_required"
    assert classifications[("GET", "/api/v1/admin/logs/storage/summary")] == "admin_capability_required"
    assert classifications[("POST", "/api/v1/admin/users/onboard")] == "admin_capability_required"
    assert classifications[("GET", "/api/v1/admin/mission-control")] == "admin_capability_required"
    assert classifications[("POST", "/api/v1/admin/cost/quota-dry-run")] == "admin_capability_required"
    assert classifications[("GET", "/api/v1/market/data-readiness")] == "operator_diagnostic"
    assert classifications[("GET", "/api/v1/agent/provider-health")] == "operator_diagnostic"

    api_routes_with_doc_labels = [
        signature
        for signature, classification in classifications.items()
        if signature[1].startswith("/api/v1/")
        and classification in {"public_static_docs", "debug_or_schema_surface"}
    ]
    assert api_routes_with_doc_labels == []


def test_legacy_api_v1_openapi_path_is_unsupported_not_a_docs_surface() -> None:
    app = FastAPI()
    app.include_router(api_v1_router)
    route_signatures = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }
    classifications = _route_surface_classifications()

    assert ("GET", LEGACY_UNSUPPORTED_OPENAPI_PATH) not in route_signatures
    assert ("GET", LEGACY_UNSUPPORTED_OPENAPI_PATH) not in classifications

    client = _auth_guarded_client()
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
            fail_closed_response = client.get(LEGACY_UNSUPPORTED_OPENAPI_PATH)
        _reset_auth_globals()
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=False):
            unsupported_response = client.get(LEGACY_UNSUPPORTED_OPENAPI_PATH)

        assert fail_closed_response.status_code == 401
        assert fail_closed_response.json() == {"error": "unauthorized", "message": "Login required"}
        _assert_public_surface_safe(fail_closed_response.json())
        assert unsupported_response.status_code == 404
    finally:
        client.close()
        _reset_auth_globals()


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


def test_market_briefing_public_preview_reaches_optional_user_endpoint_when_auth_enabled(monkeypatch) -> None:
    _reset_auth_globals()
    client = _auth_guarded_client()
    service = MagicMock()
    service.get_market_briefing.return_value = {
        "source": "fallback",
        "updatedAt": "2026-06-09T00:00:00Z",
        "items": [],
        "isFallback": True,
        "freshness": "fallback",
    }
    monkeypatch.setattr("api.v1.endpoints.market.MarketOverviewService", lambda: service)
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
            response = client.get("/api/v1/market/market-briefing")
            write_probe = client.post("/api/v1/market/market-briefing", json={})
            adjacent_market_read = client.get("/api/v1/market/temperature")

        assert response.status_code == 200
        assert response.json()["source"] == "fallback"
        assert write_probe.status_code == 401
        assert adjacent_market_read.status_code == 401
        service.get_market_briefing.assert_called_once()
        assert service.get_market_briefing.call_args.kwargs["actor"]["actor_type"] == "anonymous"
    finally:
        client.close()
        _reset_auth_globals()


def test_unauthenticated_admin_abuse_payloads_fail_closed_before_request_body_is_exposed() -> None:
    _reset_auth_globals()
    client = _auth_guarded_client()
    oversized_body = {
        "reason": "abuse rehearsal",
        "confirm": "DISABLE",
        "token": ABUSE_REHEARSAL_SECRET_BODY,
        "databaseDsn": ABUSE_REHEARSAL_DSN,
        "debug": ABUSE_REHEARSAL_DEBUG_PAYLOAD,
        "padding": "x" * 128_000,
    }
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
            responses = [
                client.post(
                    "/api/v1/admin/users/bootstrap-admin/disable",
                    json=oversized_body,
                    headers={
                        "Authorization": f"Bearer {ABUSE_REHEARSAL_BEARER}",
                        "Cookie": f"dsa_session={ABUSE_REHEARSAL_COOKIE}",
                    },
                ),
                client.post(
                    "/api/v1/admin/users/bootstrap-admin/disable",
                    content=(
                        '{"reason":"malformed",'
                        f'"token":"{ABUSE_REHEARSAL_SECRET_BODY}",'
                        f'"databaseDsn":"{ABUSE_REHEARSAL_DSN}"'
                    ),
                    headers={
                        "content-type": "application/json",
                        "Authorization": f"Bearer {ABUSE_REHEARSAL_BEARER}",
                        "Cookie": f"dsa_session={ABUSE_REHEARSAL_COOKIE}",
                    },
                ),
            ]

        assert [response.status_code for response in responses] == [401, 401]
        for response in responses:
            assert response.json() == {"error": "unauthorized", "message": "Login required"}
            _assert_public_surface_safe(response.json())
    finally:
        client.close()
        _reset_auth_globals()


def test_public_request_shape_errors_are_sanitized_for_malformed_json_and_unsupported_methods() -> None:
    client = _options_client()
    malformed_body = (
        '{"symbol":"TEM",'
        f'"token":"{ABUSE_REHEARSAL_SECRET_BODY}",'
        f'"databaseDsn":"{ABUSE_REHEARSAL_DSN}",'
        f'"debug":"{ABUSE_REHEARSAL_DEBUG_PAYLOAD}"'
    )
    try:
        malformed = client.post(
            "/api/v1/options/decision/evaluate",
            content=malformed_body,
            headers={"content-type": "application/json"},
        )
        unsupported = client.patch(
            "/api/v1/options/underlyings/TEM/summary",
            content=ABUSE_REHEARSAL_SECRET_BODY,
            headers={
                "content-type": "application/json",
                "Authorization": f"Bearer {ABUSE_REHEARSAL_BEARER}",
                "Cookie": f"dsa_session={ABUSE_REHEARSAL_COOKIE}",
            },
        )

        assert malformed.status_code == 422
        assert unsupported.status_code == 405
        for response in (malformed, unsupported):
            _assert_public_surface_safe(response.json())
    finally:
        client.close()


def test_api_abuse_rate_limit_readiness_has_global_public_limiter() -> None:
    app = FastAPI()
    add_auth_middleware(app)
    app.include_router(api_v1_router)

    middleware_names = {middleware.cls.__name__ for middleware in app.user_middleware}
    rate_limit_middleware_names = {
        name
        for name in middleware_names
        if name != "AuthMiddleware" and ("rate" in name.lower() or "limit" in name.lower())
    }
    evidence = {
        "authLoginRateLimitActive": callable(auth.check_rate_limit) and callable(auth.record_login_failure),
        "globalApiRateLimitActive": bool(rate_limit_middleware_names),
        "globalApiRateLimitScope": "public_unauthenticated_api_errors",
        "runtimeBehaviorChanged": True,
    }

    assert "AuthMiddleware" in middleware_names
    assert evidence == {
        "authLoginRateLimitActive": True,
        "globalApiRateLimitActive": True,
        "globalApiRateLimitScope": "public_unauthenticated_api_errors",
        "runtimeBehaviorChanged": True,
    }
    _assert_public_surface_safe(evidence)


def test_public_api_abuse_limiter_safe_market_read_allowlist_is_narrow() -> None:
    from api.middlewares import public_abuse_limiter as limiter

    expected = frozenset(
        {
            ("GET", "/api/v1/market/rates"),
            ("GET", "/api/v1/market/temperature"),
            ("GET", "/api/v1/market/liquidity-monitor"),
            ("GET", "/api/v1/market/fx-commodities"),
            ("GET", "/api/v1/market/crypto"),
            ("GET", "/api/v1/market/cn-indices"),
            ("GET", "/api/v1/market/cn-breadth"),
            ("GET", "/api/v1/market/cn-flows"),
            ("GET", "/api/v1/market/us-breadth"),
            ("GET", "/api/v1/market/futures"),
            ("GET", "/api/v1/market/sector-rotation"),
            ("GET", "/api/v1/market-overview/macro"),
        }
    )

    assert limiter._SAFE_READ_BYPASS_ROUTES == expected
    for method, path in expected:
        assert limiter._is_safe_read_bypass(method, path)

    assert not limiter._is_safe_read_bypass("POST", "/api/v1/market/rates")
    assert not limiter._is_safe_read_bypass("GET", "/api/v1/market/sentiment")
    assert not limiter._is_safe_read_bypass("GET", "/api/v1/admin/users")
    assert not limiter._is_safe_read_bypass("GET", "/api/v1/options/underlyings/TEM/summary")
    assert DIAGNOSTIC_ROUTES_EXCLUDED_FROM_SAFE_BYPASS.isdisjoint(limiter._SAFE_READ_BYPASS_ROUTES)


def test_hot_public_bucket_allows_safe_market_get_routes_to_serve_fallback_payloads(monkeypatch) -> None:
    from src.services.market_overview_service import MarketOverviewService

    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    client = _auth_guarded_client()
    ip_address = "203.0.113.214"
    market_service = MarketOverviewService()
    try:
        _prime_hot_public_bucket(client, ip_address)

        with patch.object(
            market_service,
            "_cached_payload",
            side_effect=lambda _key, _fetcher, fallback_factory: fallback_factory(),
        ), patch.object(
            market_service,
            "_fetch_rates_snapshot",
            side_effect=AssertionError("rates fetcher should not run for fallback payloads"),
        ), patch.object(
            market_service,
            "_fetch_macro",
            side_effect=AssertionError("macro fetcher should not run for fallback payloads"),
        ), patch.object(
            market_service,
            "_build_market_temperature_inputs",
            side_effect=AssertionError("temperature inputs should not build for fallback payloads"),
        ), patch(
            "api.v1.endpoints.market.MarketOverviewService",
            return_value=market_service,
        ), patch(
            "api.v1.endpoints.market_overview.MarketOverviewService",
            return_value=market_service,
        ), patch(
            "api.v1.endpoints.liquidity_monitor.LiquidityMonitorService",
        ) as mock_liquidity_service, patch.object(
            auth,
            "_is_auth_enabled_from_env",
            return_value=False,
        ):
            mock_liquidity_service.return_value.get_liquidity_monitor.return_value = _liquidity_monitor_fallback_payload()
            responses = {
                "/api/v1/market/rates": client.get("/api/v1/market/rates", headers={"X-Forwarded-For": ip_address}),
                "/api/v1/market/temperature": client.get("/api/v1/market/temperature", headers={"X-Forwarded-For": ip_address}),
                "/api/v1/market-overview/macro": client.get("/api/v1/market-overview/macro", headers={"X-Forwarded-For": ip_address}),
                "/api/v1/market/liquidity-monitor": client.get("/api/v1/market/liquidity-monitor", headers={"X-Forwarded-For": ip_address}),
            }

        assert {path: response.status_code for path, response in responses.items()} == {
            "/api/v1/market/rates": 200,
            "/api/v1/market/temperature": 200,
            "/api/v1/market-overview/macro": 200,
            "/api/v1/market/liquidity-monitor": 200,
        }
        assert responses["/api/v1/market/rates"].json()["source"] == "fallback"
        assert responses["/api/v1/market/temperature"].json()["isFallback"] is True
        assert responses["/api/v1/market-overview/macro"].json()["fallbackUsed"] is True
        assert responses["/api/v1/market/liquidity-monitor"].json()["freshness"]["status"] == "fallback"
        assert _limiter_snapshot()["limitedBucketCount"] == 1
        mock_liquidity_service.return_value.get_liquidity_monitor.assert_called_once_with()
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_hot_public_bucket_still_limits_non_exempt_routes(monkeypatch) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    client = _auth_guarded_client()
    ip_address = "203.0.113.215"
    try:
        _prime_hot_public_bucket(client, ip_address)

        with patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
            admin_response = client.get(
                "/api/v1/admin/users",
                headers={"X-Forwarded-For": ip_address},
            )

        with patch.object(auth, "_is_auth_enabled_from_env", return_value=False):
            public_response = client.get(
                "/api/v1/options/underlyings/TEM/summary",
                headers={"X-Forwarded-For": ip_address},
            )

        assert admin_response.status_code == 429
        assert public_response.status_code == 429
        for response in (admin_response, public_response):
            assert response.json() == {
                "error": "rate_limited",
                "message": "Too many public API errors; retry later.",
            }
            _assert_public_surface_safe(response.json())
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_public_malformed_json_bursts_eventually_receive_sanitized_rate_limit(monkeypatch) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "2")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    client = _auth_guarded_client()
    malformed_body = (
        '{"symbol":"TEM",'
        f'"token":"{ABUSE_REHEARSAL_SECRET_BODY}",'
        f'"databaseDsn":"{ABUSE_REHEARSAL_DSN}",'
        f'"debug":"{ABUSE_REHEARSAL_DEBUG_PAYLOAD}"'
    )
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=False):
            responses = [
                client.post(
                    "/api/v1/options/decision/evaluate",
                    content=malformed_body,
                    headers={
                        "content-type": "application/json",
                        "X-Forwarded-For": "203.0.113.44",
                    },
                )
                for _ in range(3)
            ]

        assert [response.status_code for response in responses] == [422, 422, 429]
        assert responses[-1].json() == {
            "error": "rate_limited",
            "message": "Too many public API errors; retry later.",
        }
        assert responses[-1].headers["Retry-After"] == "300"
        for response in responses:
            _assert_public_surface_safe(response.json())
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_public_middleware_order_keeps_shape_errors_sanitized_until_limit(monkeypatch) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    client = _auth_guarded_client()
    malformed_body = (
        '{"symbol":"TEM",'
        f'"token":"{ABUSE_REHEARSAL_SECRET_BODY}",'
        f'"databaseDsn":"{ABUSE_REHEARSAL_DSN}",'
        f'"debug":"{ABUSE_REHEARSAL_DEBUG_PAYLOAD}"'
    )
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=False):
            before_limit = client.post(
                "/api/v1/options/decision/evaluate",
                content=malformed_body,
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {ABUSE_REHEARSAL_BEARER}",
                    "Cookie": f"dsa_session={ABUSE_REHEARSAL_COOKIE}",
                    "X-Forwarded-For": "203.0.113.210",
                },
            )
            after_limit = client.post(
                "/api/v1/options/decision/evaluate",
                content=malformed_body,
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {ABUSE_REHEARSAL_BEARER}",
                    "Cookie": f"dsa_session={ABUSE_REHEARSAL_COOKIE}",
                    "X-Forwarded-For": "203.0.113.210",
                },
            )

        assert [before_limit.status_code, after_limit.status_code] == [422, 429]
        assert after_limit.json() == {
            "error": "rate_limited",
            "message": "Too many public API errors; retry later.",
        }
        assert _limiter_snapshot()["limitedBucketCount"] == 1
        for response in (before_limit, after_limit):
            _assert_public_surface_safe(response.json())
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_public_unsupported_method_bursts_eventually_receive_sanitized_rate_limit(monkeypatch) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    client = _auth_guarded_client()
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=False):
            first = client.patch(
                "/api/v1/options/underlyings/TEM/summary",
                content=ABUSE_REHEARSAL_SECRET_BODY,
                headers={
                    "content-type": "application/json",
                    "X-Forwarded-For": "203.0.113.46",
                },
            )
            limited = client.patch(
                "/api/v1/options/underlyings/TEM/summary",
                content=ABUSE_REHEARSAL_SECRET_BODY,
                headers={
                    "content-type": "application/json",
                    "X-Forwarded-For": "203.0.113.46",
                },
            )

        assert [first.status_code, limited.status_code] == [405, 429]
        for response in (first, limited):
            _assert_public_surface_safe(response.json())
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_public_api_abuse_limiter_state_can_be_reset_for_tests(monkeypatch) -> None:
    from api.middlewares.public_abuse_limiter import reset_public_api_abuse_limiter_state

    _reset_auth_globals()
    reset_public_api_abuse_limiter_state()
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    client = _auth_guarded_client()
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
            first = client.post(
                "/api/v1/admin/users/bootstrap-admin/disable",
                content=(
                    '{"reason":"malformed",'
                    f'"token":"{ABUSE_REHEARSAL_SECRET_BODY}",'
                    f'"databaseDsn":"{ABUSE_REHEARSAL_DSN}"'
                ),
                headers={
                    "content-type": "application/json",
                    "X-Forwarded-For": "203.0.113.45",
                },
            )
            limited = client.post(
                "/api/v1/admin/users/bootstrap-admin/disable",
                content=ABUSE_REHEARSAL_SECRET_BODY,
                headers={
                    "content-type": "application/json",
                    "X-Forwarded-For": "203.0.113.45",
                },
            )

            reset_public_api_abuse_limiter_state()
            after_reset = client.post(
                "/api/v1/admin/users/bootstrap-admin/disable",
                content=ABUSE_REHEARSAL_SECRET_BODY,
                headers={
                    "content-type": "application/json",
                    "X-Forwarded-For": "203.0.113.45",
                },
            )

        assert [first.status_code, limited.status_code, after_reset.status_code] == [401, 429, 401]
        for response in (first, limited, after_reset):
            _assert_public_surface_safe(response.json())
    finally:
        client.close()
        reset_public_api_abuse_limiter_state()
        _reset_auth_globals()


def test_public_api_abuse_limiter_snapshot_redacts_client_identity(monkeypatch) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "2")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    client = _auth_guarded_client()
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=False):
            response = client.post(
                "/api/v1/options/decision/evaluate",
                content='{"symbol":"TEM"',
                headers={
                    "content-type": "application/json",
                    "X-Forwarded-For": "203.0.113.150",
                },
            )

        assert response.status_code == 422
        snapshot = _limiter_snapshot()
        assert snapshot["bucketCount"] == 1
        assert snapshot["totalFailures"] == 1
        assert snapshot["maxBucketFailures"] == 1
        assert snapshot["identityRedaction"] == "client_identity_not_exposed"
        assert "buckets" not in snapshot
        assert "clients" not in snapshot
        snapshot_text = _json_text(snapshot)
        assert "203.0.113.150" not in snapshot_text
        _assert_public_surface_safe(snapshot)
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_public_api_abuse_limiter_does_not_log_or_expose_raw_request_values(monkeypatch, caplog) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    client = _auth_guarded_client()
    raw_header = "raw-abuse-header-token"
    try:
        with caplog.at_level(logging.INFO), patch.object(auth, "_is_auth_enabled_from_env", return_value=False):
            first = client.post(
                "/api/v1/options/decision/evaluate",
                content=(
                    '{"symbol":"TEM",'
                    f'"token":"{ABUSE_REHEARSAL_SECRET_BODY}",'
                    f'"databaseDsn":"{ABUSE_REHEARSAL_DSN}"'
                ),
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {ABUSE_REHEARSAL_BEARER}",
                    "Cookie": f"dsa_session={ABUSE_REHEARSAL_COOKIE}",
                    "X-Abuse-Rehearsal": raw_header,
                },
            )
            limited = client.post(
                "/api/v1/options/decision/evaluate",
                content=ABUSE_REHEARSAL_SECRET_BODY,
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {ABUSE_REHEARSAL_BEARER}",
                    "Cookie": f"dsa_session={ABUSE_REHEARSAL_COOKIE}",
                    "X-Abuse-Rehearsal": raw_header,
                },
            )

        assert [first.status_code, limited.status_code] == [422, 429]
        exposed_text = "\n".join(
            [
                caplog.text,
                _json_text(first.json()),
                _json_text(limited.json()),
                _json_text(dict(limited.headers)),
                _json_text(_limiter_snapshot()),
            ]
        )
        for marker in (
            ABUSE_REHEARSAL_SECRET_BODY,
            ABUSE_REHEARSAL_COOKIE,
            ABUSE_REHEARSAL_BEARER,
            ABUSE_REHEARSAL_DSN,
            raw_header,
        ):
            assert marker not in exposed_text
        _assert_public_surface_safe(first.json())
        _assert_public_surface_safe(limited.json())
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_public_api_abuse_limiter_retry_after_is_bounded_and_stable(monkeypatch) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "999999")
    client = _auth_guarded_client()
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=False):
            responses = [
                client.post(
                    "/api/v1/options/decision/evaluate",
                    content='{"symbol":"TEM"',
                    headers={"content-type": "application/json"},
                )
                for _ in range(3)
            ]

        assert [response.status_code for response in responses] == [422, 429, 429]
        assert [response.headers.get("Retry-After") for response in responses[1:]] == ["3600", "3600"]
        for response in responses:
            _assert_public_surface_safe(response.json())
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_public_api_abuse_limiter_snapshot_prunes_expired_buckets(monkeypatch) -> None:
    from api.middlewares import public_abuse_limiter as limiter

    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    current_time = [1_000.0]
    monkeypatch.setattr(limiter.time, "time", lambda: current_time[0])
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "2")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "60")
    client = _auth_guarded_client()
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=False):
            response = client.post(
                "/api/v1/options/decision/evaluate",
                content='{"symbol":"TEM"',
                headers={"content-type": "application/json"},
            )

        assert response.status_code == 422
        assert _limiter_snapshot()["bucketCount"] == 1
        current_time[0] = 1_061.0
        snapshot = _limiter_snapshot()
        assert snapshot["bucketCount"] == 0
        assert snapshot["totalFailures"] == 0
        assert snapshot["oldestBucketAgeSeconds"] == 0
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_public_api_abuse_limiter_prunes_expired_buckets_before_cap_eviction(monkeypatch) -> None:
    from api.middlewares import public_abuse_limiter as limiter

    _reset_public_limiter_state_if_available()
    current_time = [1_000.0]
    monkeypatch.setattr(limiter.time, "time", lambda: current_time[0])
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS", "16")
    try:
        with limiter._PUBLIC_API_ABUSE_LOCK:
            limiter._PUBLIC_API_ABUSE_BUCKETS["expired-client"] = (1, 900.0)
            for index in range(16):
                limiter._PUBLIC_API_ABUSE_BUCKETS[f"active-client-{index}"] = (1, 960.0 + index)

        snapshot = _limiter_snapshot()

        assert snapshot["bucketCount"] == 16
        with limiter._PUBLIC_API_ABUSE_LOCK:
            assert "expired-client" not in limiter._PUBLIC_API_ABUSE_BUCKETS
            assert set(limiter._PUBLIC_API_ABUSE_BUCKETS) == {
                f"active-client-{index}" for index in range(16)
            }
    finally:
        _reset_public_limiter_state_if_available()


def test_public_api_abuse_limiter_evicts_oldest_buckets_over_cap(monkeypatch) -> None:
    from api.middlewares import public_abuse_limiter as limiter

    _reset_public_limiter_state_if_available()
    current_time = [1_000.0]
    monkeypatch.setattr(limiter.time, "time", lambda: current_time[0])
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS", "16")
    try:
        with limiter._PUBLIC_API_ABUSE_LOCK:
            for index in range(17):
                limiter._PUBLIC_API_ABUSE_BUCKETS[f"client-{index}"] = (1, 800.0 + index)

        snapshot = _limiter_snapshot()

        assert snapshot["bucketCount"] == 16
        with limiter._PUBLIC_API_ABUSE_LOCK:
            assert "client-0" not in limiter._PUBLIC_API_ABUSE_BUCKETS
            assert set(limiter._PUBLIC_API_ABUSE_BUCKETS) == {
                f"client-{index}" for index in range(1, 17)
            }
    finally:
        _reset_public_limiter_state_if_available()


def test_malformed_request_bursts_from_separate_clients_stay_isolated(monkeypatch) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    client = _auth_guarded_client()
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=False):
            first_client_failure = client.post(
                "/api/v1/options/decision/evaluate",
                content='{"symbol":"TEM"',
                headers={"content-type": "application/json", "X-Forwarded-For": "203.0.113.160"},
            )
            first_client_limited = client.post(
                "/api/v1/options/decision/evaluate",
                content='{"symbol":"TEM"',
                headers={"content-type": "application/json", "X-Forwarded-For": "203.0.113.160"},
            )
            second_client_failure = client.post(
                "/api/v1/options/decision/evaluate",
                content='{"symbol":"TEM"',
                headers={"content-type": "application/json", "X-Forwarded-For": "203.0.113.161"},
            )

        assert [
            first_client_failure.status_code,
            first_client_limited.status_code,
            second_client_failure.status_code,
        ] == [422, 429, 422]
        assert _limiter_snapshot()["bucketCount"] == 2
        for response in (first_client_failure, first_client_limited, second_client_failure):
            _assert_public_surface_safe(response.json())
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_public_api_abuse_limiter_env_values_are_bounded_and_safe(monkeypatch) -> None:
    from api.middlewares import public_abuse_limiter as limiter

    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "5")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "0")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS", "0")
    assert limiter._window_seconds() == 60
    assert limiter._max_failures() == 1
    assert limiter._max_buckets() == 16

    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "999999")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "999999")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS", "999999")
    assert limiter._window_seconds() == 3600
    assert limiter._max_failures() == 100
    assert limiter._max_buckets() == 65536

    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "not-an-int")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "not-an-int")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS", "not-an-int")
    assert limiter._window_seconds() == limiter.PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS_DEFAULT
    assert limiter._max_failures() == limiter.PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES_DEFAULT
    assert limiter._max_buckets() == limiter.PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS_DEFAULT


def test_public_api_abuse_limiter_isolates_failure_buckets_per_client(monkeypatch) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    client = _auth_guarded_client()
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
            first_client_first_failure = client.post(
                "/api/v1/admin/users/bootstrap-admin/disable",
                json={"reason": "public abuse limiter bucket isolation", "confirm": "DISABLE"},
                headers={"X-Forwarded-For": "203.0.113.100"},
            )
            first_client_limited = client.post(
                "/api/v1/admin/users/bootstrap-admin/disable",
                json={"reason": "public abuse limiter bucket isolation", "confirm": "DISABLE"},
                headers={"X-Forwarded-For": "203.0.113.100"},
            )
            second_client_first_failure = client.post(
                "/api/v1/admin/users/bootstrap-admin/disable",
                json={"reason": "public abuse limiter bucket isolation", "confirm": "DISABLE"},
                headers={"X-Forwarded-For": "203.0.113.101"},
            )

        assert [
            first_client_first_failure.status_code,
            first_client_limited.status_code,
            second_client_first_failure.status_code,
        ] == [401, 429, 401]
        assert first_client_limited.headers["Retry-After"] == "300"
        for response in (first_client_first_failure, first_client_limited, second_client_first_failure):
            _assert_public_surface_safe(response.json())
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_valid_session_cookie_bypasses_public_api_abuse_limiter(monkeypatch, tmp_path) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setattr(auth, "_get_data_dir", lambda: tmp_path)
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    auth._auth_enabled = True
    auth.set_initial_password("adminpass123")
    session_cookie = auth.create_session()
    client = _limiter_probe_client()
    client.cookies.set(auth.COOKIE_NAME, session_cookie)
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
            responses = [
                client.get(
                    "/api/v1/limiter-probe/fails",
                    headers={"X-Forwarded-For": "203.0.113.102"},
                )
                for _ in range(3)
            ]

        assert [response.status_code for response in responses] == [422, 422, 422]
        assert _limiter_snapshot()["bucketCount"] == 0
        for response in responses:
            _assert_public_surface_safe(response.json())
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_public_api_test_client_raw_body_and_cookie_patterns_are_warning_free(monkeypatch, tmp_path) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setattr(auth, "_get_data_dir", lambda: tmp_path)
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    auth._auth_enabled = True
    auth.set_initial_password("adminpass123")
    session_cookie = auth.create_session()
    client = _auth_guarded_client()
    client.cookies.set(auth.COOKIE_NAME, session_cookie)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("default")
            with patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
                malformed = client.post(
                    "/api/v1/options/decision/evaluate",
                    content='{"symbol":"TEM"',
                    headers={"content-type": "application/json", "X-Forwarded-For": "203.0.113.104"},
                )
                valid_cookie = client.get(
                    "/api/v1/admin/users",
                    headers={"X-Forwarded-For": "203.0.113.104"},
                )

        assert [malformed.status_code, valid_cookie.status_code] == [422, 200]
        assert _format_warning_messages(caught) == []
        assert _limiter_snapshot()["bucketCount"] == 0
        for response in (malformed, valid_cookie):
            _assert_public_surface_safe(response.json())
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_public_api_abuse_limiter_excludes_auth_routes(monkeypatch) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    client = _auth_guarded_client()
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
            responses = [
                client.patch(
                    "/api/v1/auth/status",
                    content=ABUSE_REHEARSAL_SECRET_BODY,
                    headers={"content-type": "application/json", "X-Forwarded-For": "203.0.113.103"},
                )
                for _ in range(3)
            ]

        assert [response.status_code for response in responses] == [405, 405, 405]
        assert _limiter_snapshot()["bucketCount"] == 0
        for response in responses:
            _assert_public_surface_safe(response.json())
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_public_api_abuse_limiter_excludes_auth_login_failures_from_buckets(monkeypatch) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    username = "public-limiter-auth-route-safety"
    ip_address = "203.0.113.211"
    auth.clear_rate_limit(ip_address, username)
    client = _auth_guarded_client()
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
            responses = [
                client.post(
                    "/api/v1/auth/login",
                    json={"username": username, "password": "wrong-password"},
                    headers={"X-Forwarded-For": ip_address},
                )
                for _ in range(3)
            ]

        assert all(response.status_code != 429 for response in responses)
        assert _limiter_snapshot()["bucketCount"] == 0
        for response in responses:
            _assert_public_surface_safe(response.json())
    finally:
        client.close()
        auth.clear_rate_limit(ip_address, username)
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_public_api_abuse_limiter_excludes_options_docs_openapi_and_health(monkeypatch) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    client = _limiter_infra_client()
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
            responses = [
                client.options(
                    "/api/v1/limiter-probe/fails",
                    headers={"X-Forwarded-For": "203.0.113.212"},
                ),
                client.get("/docs", headers={"X-Forwarded-For": "203.0.113.212"}),
                client.get("/openapi.json", headers={"X-Forwarded-For": "203.0.113.212"}),
                client.get("/api/health", headers={"X-Forwarded-For": "203.0.113.212"}),
                client.get("/health", headers={"X-Forwarded-For": "203.0.113.212"}),
            ]

        assert [response.status_code for response in responses] == [405, 200, 200, 200, 200]
        assert _limiter_snapshot()["bucketCount"] == 0
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_valid_session_bypasses_hot_public_bucket_for_same_client(monkeypatch, tmp_path) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setattr(auth, "_get_data_dir", lambda: tmp_path)
    monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    client = _auth_guarded_client()
    raw_client_ip = "203.0.113.213"
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=False):
            public_failure = client.post(
                "/api/v1/options/decision/evaluate",
                content='{"symbol":"TEM"',
                headers={"content-type": "application/json", "X-Forwarded-For": raw_client_ip},
            )

        assert public_failure.status_code == 422
        assert _limiter_snapshot()["limitedBucketCount"] == 1

        auth._auth_enabled = True
        auth.set_initial_password("adminpass123")
        client.cookies.set(auth.COOKIE_NAME, auth.create_session())
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
            authenticated = client.get(
                "/api/v1/admin/users",
                headers={"X-Forwarded-For": raw_client_ip},
            )

        assert authenticated.status_code == 200
        assert _limiter_snapshot()["limitedBucketCount"] == 1
        _assert_public_surface_safe(public_failure.json())
        _assert_public_surface_safe(authenticated.json())
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_public_api_abuse_limiter_429_exposes_no_request_or_client_details(monkeypatch, caplog) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    client = _auth_guarded_client()
    raw_client_ip = "203.0.113.214"
    raw_header = "raw-429-header-token"
    try:
        with caplog.at_level(logging.INFO), patch.object(auth, "_is_auth_enabled_from_env", return_value=False):
            first = client.post(
                "/api/v1/options/decision/evaluate",
                content=(
                    '{"symbol":"TEM",'
                    f'"token":"{ABUSE_REHEARSAL_SECRET_BODY}",'
                    f'"databaseDsn":"{ABUSE_REHEARSAL_DSN}",'
                    f'"debug":"{ABUSE_REHEARSAL_DEBUG_PAYLOAD}"'
                ),
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {ABUSE_REHEARSAL_BEARER}",
                    "Cookie": f"dsa_session={ABUSE_REHEARSAL_COOKIE}",
                    "X-Forwarded-For": raw_client_ip,
                    "X-Abuse-Rehearsal": raw_header,
                },
            )
            limited = client.post(
                "/api/v1/options/decision/evaluate",
                content=ABUSE_REHEARSAL_SECRET_BODY,
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {ABUSE_REHEARSAL_BEARER}",
                    "Cookie": f"dsa_session={ABUSE_REHEARSAL_COOKIE}",
                    "X-Forwarded-For": raw_client_ip,
                    "X-Abuse-Rehearsal": raw_header,
                },
            )

        assert [first.status_code, limited.status_code] == [422, 429]
        assert limited.json() == {
            "error": "rate_limited",
            "message": "Too many public API errors; retry later.",
        }
        assert "set-cookie" not in {key.lower() for key in limited.headers}
        exposed_text = "\n".join(
            [
                caplog.text,
                _json_text(limited.json()),
                _json_text(dict(limited.headers)),
                _json_text(_limiter_snapshot()),
            ]
        ).lower()
        for marker in (
            ABUSE_REHEARSAL_SECRET_BODY,
            ABUSE_REHEARSAL_COOKIE,
            ABUSE_REHEARSAL_BEARER,
            ABUSE_REHEARSAL_DSN,
            ABUSE_REHEARSAL_DEBUG_PAYLOAD,
            raw_client_ip,
            raw_header,
            "authorization",
            "cookie",
            "x-forwarded-for",
            "x-abuse-rehearsal",
            "traceback",
            "stack trace",
        ):
            assert marker.lower() not in exposed_text
        _assert_public_surface_safe(limited.json())
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_public_api_abuse_limiter_operator_env_knobs_are_clamped_in_snapshot(monkeypatch) -> None:
    from api.middlewares import public_abuse_limiter as limiter

    _reset_public_limiter_state_if_available()
    try:
        monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "5")
        monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "0")
        monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS", "0")
        assert _limiter_snapshot() == {
            "bucketCount": 0,
            "totalFailures": 0,
            "maxBucketFailures": 0,
            "limitedBucketCount": 0,
            "oldestBucketAgeSeconds": 0,
            "windowSeconds": 60,
            "maxFailures": 1,
            "maxBuckets": 16,
            "processLocal": True,
            "identityRedaction": "client_identity_not_exposed",
        }

        monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "999999")
        monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "999999")
        monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS", "999999")
        high_snapshot = _limiter_snapshot()
        assert high_snapshot["windowSeconds"] == 3600
        assert high_snapshot["maxFailures"] == 100
        assert high_snapshot["maxBuckets"] == 65536

        monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "not-an-int")
        monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "not-an-int")
        monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS", "not-an-int")
        invalid_snapshot = _limiter_snapshot()
        assert invalid_snapshot["windowSeconds"] == limiter.PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS_DEFAULT
        assert invalid_snapshot["maxFailures"] == limiter.PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES_DEFAULT
        assert invalid_snapshot["maxBuckets"] == limiter.PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS_DEFAULT
    finally:
        _reset_public_limiter_state_if_available()


def test_public_api_abuse_limiter_operator_bucket_cap_evicts_oldest_process_local_entries(monkeypatch) -> None:
    from api.middlewares import public_abuse_limiter as limiter

    _reset_public_limiter_state_if_available()
    current_time = [1_000.0]
    monkeypatch.setattr(limiter.time, "time", lambda: current_time[0])
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS", "16")
    try:
        with limiter._PUBLIC_API_ABUSE_LOCK:
            for index in range(18):
                limiter._PUBLIC_API_ABUSE_BUCKETS[f"operator-client-{index}"] = (1, 800.0 + index)

        snapshot = _limiter_snapshot()

        assert snapshot["bucketCount"] == 16
        assert snapshot["maxBuckets"] == 16
        assert snapshot["processLocal"] is True
        with limiter._PUBLIC_API_ABUSE_LOCK:
            assert set(limiter._PUBLIC_API_ABUSE_BUCKETS) == {
                f"operator-client-{index}" for index in range(2, 18)
            }
    finally:
        _reset_public_limiter_state_if_available()


def test_public_api_abuse_limiter_operator_snapshot_exposes_only_redacted_aggregate_fields(monkeypatch) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "2")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "300")
    client = _auth_guarded_client()
    raw_header = "raw-operator-header-token"
    raw_client_ip = "203.0.113.175"
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=False):
            response = client.post(
                "/api/v1/options/decision/evaluate",
                content=(
                    '{"symbol":"TEM",'
                    f'"token":"{ABUSE_REHEARSAL_SECRET_BODY}",'
                    f'"databaseDsn":"{ABUSE_REHEARSAL_DSN}"'
                ),
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {ABUSE_REHEARSAL_BEARER}",
                    "Cookie": f"dsa_session={ABUSE_REHEARSAL_COOKIE}",
                    "X-Forwarded-For": raw_client_ip,
                    "X-Operator-Rehearsal": raw_header,
                },
            )

        assert response.status_code == 422
        snapshot = _limiter_snapshot()
        assert set(snapshot) == {
            "bucketCount",
            "totalFailures",
            "maxBucketFailures",
            "limitedBucketCount",
            "oldestBucketAgeSeconds",
            "windowSeconds",
            "maxFailures",
            "maxBuckets",
            "processLocal",
            "identityRedaction",
        }
        assert snapshot["bucketCount"] == 1
        assert snapshot["identityRedaction"] == "client_identity_not_exposed"
        snapshot_text = _json_text(snapshot)
        for marker in (
            raw_client_ip,
            raw_header,
            ABUSE_REHEARSAL_SECRET_BODY,
            ABUSE_REHEARSAL_COOKIE,
            ABUSE_REHEARSAL_BEARER,
            ABUSE_REHEARSAL_DSN,
            "headers",
            "cookies",
            "session",
            "validation",
            "traceback",
        ):
            assert marker.lower() not in snapshot_text.lower()
        _assert_public_surface_safe(snapshot)
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_public_api_abuse_limiter_operator_retry_after_uses_bounded_window(monkeypatch) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    client = _auth_guarded_client()
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=False):
            monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
            monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "5")
            low_first = client.post(
                "/api/v1/options/decision/evaluate",
                content='{"symbol":"TEM"',
                headers={"content-type": "application/json", "X-Forwarded-For": "203.0.113.176"},
            )
            low_limited = client.post(
                "/api/v1/options/decision/evaluate",
                content='{"symbol":"TEM"',
                headers={"content-type": "application/json", "X-Forwarded-For": "203.0.113.176"},
            )

            _reset_public_limiter_state_if_available()
            monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "999999")
            high_first = client.post(
                "/api/v1/options/decision/evaluate",
                content='{"symbol":"TEM"',
                headers={"content-type": "application/json", "X-Forwarded-For": "203.0.113.177"},
            )
            high_limited = client.post(
                "/api/v1/options/decision/evaluate",
                content='{"symbol":"TEM"',
                headers={"content-type": "application/json", "X-Forwarded-For": "203.0.113.177"},
            )

        assert [low_first.status_code, low_limited.status_code] == [422, 429]
        assert [high_first.status_code, high_limited.status_code] == [422, 429]
        assert low_limited.headers["Retry-After"] == "60"
        assert high_limited.headers["Retry-After"] == "3600"
        for response in (low_first, low_limited, high_first, high_limited):
            _assert_public_surface_safe(response.json())
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_public_api_abuse_limiter_operator_valid_session_bypass_survives_strict_env(monkeypatch, tmp_path) -> None:
    _reset_auth_globals()
    _reset_public_limiter_state_if_available()
    monkeypatch.setattr(auth, "_get_data_dir", lambda: tmp_path)
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES", "1")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS", "5")
    monkeypatch.setenv("PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS", "0")
    auth._auth_enabled = True
    auth.set_initial_password("adminpass123")
    session_cookie = auth.create_session()
    client = _limiter_probe_client()
    client.cookies.set(auth.COOKIE_NAME, session_cookie)
    try:
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
            responses = [
                client.get(
                    "/api/v1/limiter-probe/fails",
                    headers={"X-Forwarded-For": "203.0.113.178"},
                )
                for _ in range(3)
            ]

        assert [response.status_code for response in responses] == [422, 422, 422]
        assert _limiter_snapshot()["bucketCount"] == 0
        assert all("Retry-After" not in response.headers for response in responses)
        for response in responses:
            _assert_public_surface_safe(response.json())
    finally:
        client.close()
        _reset_public_limiter_state_if_available()
        _reset_auth_globals()


def test_options_launch_surface_matrix_is_fixture_backed_explicit_and_safe() -> None:
    route_classifications = _route_surface_classifications()
    assert {
        signature: route_classifications[signature]
        for signature in OPTIONS_FIXTURE_PUBLIC_API_SURFACES
    } == {
        signature: "public_fixture_analysis"
        for signature in OPTIONS_FIXTURE_PUBLIC_API_SURFACES
    }

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
