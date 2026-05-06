# -*- coding: utf-8 -*-
"""
Auth middleware: protect /api/v1/* when admin auth is enabled.
"""

from __future__ import annotations

import logging
from typing import Callable
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api.deps import resolve_current_user
from src.auth import COOKIE_NAME, is_auth_enabled, is_production_mode

logger = logging.getLogger(__name__)

EXEMPT_PATHS = frozenset({
    "/api/v1/auth/login",
    "/api/v1/auth/reset-password/request",
    "/api/v1/auth/status",
    "/api/v1/auth/me",
    "/api/v1/auth/verify-password",
    "/api/v1/analysis/preview",
    "/api/health",
    "/api/health/live",
    "/api/health/ready",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
})

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _path_exempt(path: str) -> bool:
    """Check if path is exempt from auth."""
    normalized = path.rstrip("/") or "/"
    return normalized in EXEMPT_PATHS


def _origin_from_value(value: str | None) -> str | None:
    parsed = urlparse(str(value or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _trusted_origins() -> set[str]:
    import os

    origins = {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    }
    for env_name in ("CORS_ORIGINS", "CSRF_TRUSTED_ORIGINS"):
        raw = os.getenv(env_name, "")
        origins.update(origin for origin in (_origin_from_value(item) for item in raw.split(",")) if origin)
    return origins


def _request_origin(request: Request) -> str | None:
    origin = _origin_from_value(request.headers.get("Origin"))
    if origin:
        return origin
    return _origin_from_value(request.headers.get("Referer"))


def _csrf_origin_allowed(request: Request) -> bool:
    origin = _request_origin(request)
    if origin is None:
        return not is_production_mode()
    return origin in _trusted_origins()


class AuthMiddleware(BaseHTTPMiddleware):
    """Require valid session for /api/v1/* when auth is enabled."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ):
        path = request.url.path
        current_user = resolve_current_user(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        if not is_auth_enabled():
            return await call_next(request)

        if _path_exempt(path):
            return await call_next(request)

        if not path.startswith("/api/v1/"):
            return await call_next(request)

        if current_user is None:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Login required",
                },
            )

        if (
            request.method.upper() in UNSAFE_METHODS
            and COOKIE_NAME in (getattr(request, "cookies", {}) or {})
            and not _csrf_origin_allowed(request)
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_origin_forbidden",
                    "message": "Request origin is not allowed",
                },
            )

        return await call_next(request)


def add_auth_middleware(app):
    """Add auth middleware to protect API routes.

    The middleware is always registered; whether auth is enforced is determined
    at request time by is_auth_enabled() so the decision stays consistent across
    any runtime configuration reload.
    """
    app.add_middleware(AuthMiddleware)
