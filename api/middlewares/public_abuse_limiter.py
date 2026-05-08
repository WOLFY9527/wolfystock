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

from api.security_headers import apply_security_headers
from src.auth import COOKIE_NAME, get_client_ip, get_session_identity

PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS_DEFAULT = 300
PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES_DEFAULT = 12

_TRACKED_FAILURE_STATUSES = frozenset({400, 401, 403, 405, 422})
_EXEMPT_PREFIXES = (
    "/api/v1/auth/",
    "/api/health",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
)
_PUBLIC_API_ABUSE_BUCKETS: dict[str, tuple[int, float]] = {}
_PUBLIC_API_ABUSE_LOCK = threading.Lock()


def _env_int(name: str, default: int, *, minimum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, value)


def _window_seconds() -> int:
    return _env_int(
        "PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS",
        PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS_DEFAULT,
        minimum=60,
    )


def _max_failures() -> int:
    return _env_int(
        "PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES",
        PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES_DEFAULT,
        minimum=1,
    )


def reset_public_api_abuse_limiter_state() -> None:
    """Clear process-local limiter state for deterministic tests."""
    with _PUBLIC_API_ABUSE_LOCK:
        _PUBLIC_API_ABUSE_BUCKETS.clear()


def _is_api_surface(path: str) -> bool:
    return path.startswith("/api/v1/")


def _is_exempt(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    return any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in _EXEMPT_PREFIXES)


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


def _bucket_limited(key: str) -> bool:
    now = time.time()
    window = _window_seconds()
    with _PUBLIC_API_ABUSE_LOCK:
        _prune_expired(now, window)
        count, _ = _PUBLIC_API_ABUSE_BUCKETS.get(key, (0, now))
        return count >= _max_failures()


def _record_failure(key: str) -> None:
    now = time.time()
    window = _window_seconds()
    with _PUBLIC_API_ABUSE_LOCK:
        _prune_expired(now, window)
        count, first_seen = _PUBLIC_API_ABUSE_BUCKETS.get(key, (0, now))
        if now - first_seen > window:
            _PUBLIC_API_ABUSE_BUCKETS[key] = (1, now)
            return
        _PUBLIC_API_ABUSE_BUCKETS[key] = (count + 1, first_seen)


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


class PublicApiAbuseLimiterMiddleware(BaseHTTPMiddleware):
    """Throttle bursts of unauthenticated public API error responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        method = request.method.upper()

        if method == "OPTIONS" or not _is_api_surface(path) or _is_exempt(path) or _has_valid_session_cookie(request):
            return await call_next(request)

        key = _bucket_key(request)
        if _bucket_limited(key):
            return _rate_limited_response(request)

        response = await call_next(request)
        if response.status_code in _TRACKED_FAILURE_STATUSES:
            _record_failure(key)
        return response


def add_public_api_abuse_limiter(app) -> None:
    """Register the public API abuse limiter middleware."""
    app.add_middleware(PublicApiAbuseLimiterMiddleware)
