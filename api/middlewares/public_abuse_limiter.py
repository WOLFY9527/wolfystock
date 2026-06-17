# -*- coding: utf-8 -*-
"""Process-local limiter for unauthenticated public API abuse bursts."""

from __future__ import annotations

import os
import threading
import time
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api.route_access_policy import is_public_baseline_read
from api.security_headers import apply_security_headers
from src.auth import COOKIE_NAME, get_client_ip, get_session_identity, is_auth_enabled

PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS_DEFAULT = 300
PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES_DEFAULT = 12
PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS_DEFAULT = 4096
PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS_MIN = 60
PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS_MAX = 3600
PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES_MIN = 1
PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES_MAX = 100
PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS_MIN = 16
PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS_MAX = 65536

_TRACKED_FAILURE_STATUSES = frozenset({400, 401, 403, 405, 422})
_AUTH_FAIL_CLOSED_STATUSES = frozenset({401, 403})
_EXEMPT_PREFIXES = (
    "/api/v1/auth/",
    "/api/health",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
)
_SAFE_READ_BYPASS_ROUTES = frozenset(
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
_PUBLIC_API_ABUSE_BUCKETS: dict[str, tuple[int, float]] = {}
_PUBLIC_API_ABUSE_LOCK = threading.Lock()


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return min(maximum, max(minimum, value))


def _window_seconds() -> int:
    return _env_int(
        "PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS",
        PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS_DEFAULT,
        minimum=PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS_MIN,
        maximum=PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS_MAX,
    )


def _max_failures() -> int:
    return _env_int(
        "PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES",
        PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES_DEFAULT,
        minimum=PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES_MIN,
        maximum=PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES_MAX,
    )


def _max_buckets() -> int:
    return _env_int(
        "PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS",
        PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS_DEFAULT,
        minimum=PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS_MIN,
        maximum=PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS_MAX,
    )


def reset_public_api_abuse_limiter_state() -> None:
    """Clear process-local limiter state for deterministic tests."""
    with _PUBLIC_API_ABUSE_LOCK:
        _PUBLIC_API_ABUSE_BUCKETS.clear()


def get_public_api_abuse_limiter_snapshot() -> dict[str, int | bool | str]:
    """Return sanitized process-local limiter counters without client identities."""
    now = time.time()
    window = _window_seconds()
    max_failures = _max_failures()
    max_buckets = _max_buckets()
    with _PUBLIC_API_ABUSE_LOCK:
        _prune_buckets(now, window, max_buckets)
        counts = [count for count, _ in _PUBLIC_API_ABUSE_BUCKETS.values()]
        first_seen_values = [first_seen for _, first_seen in _PUBLIC_API_ABUSE_BUCKETS.values()]
        oldest_age = int(max(0, now - min(first_seen_values))) if first_seen_values else 0
        return {
            "bucketCount": len(counts),
            "totalFailures": sum(counts),
            "maxBucketFailures": max(counts, default=0),
            "limitedBucketCount": sum(1 for count in counts if count >= max_failures),
            "oldestBucketAgeSeconds": oldest_age,
            "windowSeconds": window,
            "maxFailures": max_failures,
            "maxBuckets": max_buckets,
            "processLocal": True,
            "identityRedaction": "client_identity_not_exposed",
        }


def _is_api_surface(path: str) -> bool:
    return path.startswith("/api/v1/")


def _normalize_path(path: str) -> str:
    return path.rstrip("/") or "/"


def _is_exempt(path: str) -> bool:
    normalized = _normalize_path(path)
    return any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in _EXEMPT_PREFIXES)


def _is_safe_read_bypass(method: str, path: str) -> bool:
    normalized = _normalize_path(path)
    return (method.upper(), normalized) in _SAFE_READ_BYPASS_ROUTES or is_public_baseline_read(method, normalized)


def _has_valid_session_cookie(request: Request) -> bool:
    cookie_value = (getattr(request, "cookies", {}) or {}).get(COOKIE_NAME)
    if not cookie_value:
        return False
    return get_session_identity(cookie_value) is not None


def _bucket_key(request: Request) -> str:
    return get_client_ip(request)


def _prune_expired(now: float, window_seconds: int) -> None:
    expired = [
        key
        for key, (_, first_seen) in _PUBLIC_API_ABUSE_BUCKETS.items()
        if now - first_seen > window_seconds
    ]
    for key in expired:
        del _PUBLIC_API_ABUSE_BUCKETS[key]


def _prune_to_max_buckets(max_buckets: int) -> None:
    overflow = len(_PUBLIC_API_ABUSE_BUCKETS) - max_buckets
    if overflow <= 0:
        return

    oldest_keys = [
        key
        for _, key in sorted(
            (first_seen, key) for key, (_, first_seen) in _PUBLIC_API_ABUSE_BUCKETS.items()
        )[:overflow]
    ]
    for key in oldest_keys:
        del _PUBLIC_API_ABUSE_BUCKETS[key]


def _prune_buckets(now: float, window_seconds: int, max_buckets: int) -> None:
    _prune_expired(now, window_seconds)
    _prune_to_max_buckets(max_buckets)


def _bucket_limited(key: str) -> bool:
    now = time.time()
    window = _window_seconds()
    with _PUBLIC_API_ABUSE_LOCK:
        _prune_buckets(now, window, _max_buckets())
        count, _ = _PUBLIC_API_ABUSE_BUCKETS.get(key, (0, now))
        return count >= _max_failures()


def _record_failure(key: str) -> None:
    now = time.time()
    window = _window_seconds()
    with _PUBLIC_API_ABUSE_LOCK:
        max_buckets = _max_buckets()
        _prune_buckets(now, window, max_buckets)
        count, first_seen = _PUBLIC_API_ABUSE_BUCKETS.get(key, (0, now))
        if now - first_seen > window:
            _PUBLIC_API_ABUSE_BUCKETS[key] = (1, now)
            _prune_to_max_buckets(max_buckets)
            return
        _PUBLIC_API_ABUSE_BUCKETS[key] = (count + 1, first_seen)
        _prune_to_max_buckets(max_buckets)


def _rate_limited_response(request: Request) -> JSONResponse:
    response = JSONResponse(
        status_code=429,
        content={
            "error": "rate_limited",
            "message": "Too many public API errors; retry later.",
        },
        headers={"Retry-After": str(_window_seconds())},
    )
    return apply_security_headers(response, request)


async def _call_next_and_record_public_failure(
    request: Request,
    call_next: Callable,
    *,
    key: str,
    auth_enabled_for_request: bool,
) -> Response:
    response = await call_next(request)
    auth_fail_closed = auth_enabled_for_request and response.status_code in _AUTH_FAIL_CLOSED_STATUSES
    if response.status_code in _TRACKED_FAILURE_STATUSES and not auth_fail_closed:
        _record_failure(key)
    return response


class PublicApiAbuseLimiterMiddleware(BaseHTTPMiddleware):
    """Throttle bursts of unauthenticated public API error responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        method = request.method.upper()

        if method == "OPTIONS" or not _is_api_surface(path) or _is_exempt(path) or _has_valid_session_cookie(request):
            return await call_next(request)

        key = _bucket_key(request)
        auth_enabled_for_request = is_auth_enabled()
        if _bucket_limited(key) and not _is_safe_read_bypass(method, path):
            if auth_enabled_for_request:
                response = await _call_next_and_record_public_failure(
                    request,
                    call_next,
                    key=key,
                    auth_enabled_for_request=auth_enabled_for_request,
                )
                if response.status_code in _AUTH_FAIL_CLOSED_STATUSES:
                    return response
            return _rate_limited_response(request)

        return await _call_next_and_record_public_failure(
            request,
            call_next,
            key=key,
            auth_enabled_for_request=auth_enabled_for_request,
        )


def add_public_api_abuse_limiter(app) -> None:
    """Register the public API abuse limiter middleware."""
    app.add_middleware(PublicApiAbuseLimiterMiddleware)
