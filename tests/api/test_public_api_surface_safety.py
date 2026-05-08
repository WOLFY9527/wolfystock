# -*- coding: utf-8 -*-
"""Public API response safety matrix for launch-exposed surfaces."""

from __future__ import annotations

import json
import logging
import warnings
from unittest.mock import patch

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


def _limiter_probe_client() -> TestClient:
    app = FastAPI()
    add_auth_middleware(app)

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
