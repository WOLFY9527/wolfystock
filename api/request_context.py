"""API-owned request correlation lifecycle and middleware."""

from __future__ import annotations

import logging
import re
import secrets
import time
from typing import Any, Awaitable, Callable, MutableMapping

from src.request_context import (
    REQUEST_ID_LENGTH,
    REQUEST_ID_PATTERN,
    bind_request_id,
    get_request_id,
    reset_request_id,
)


logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
SLOW_REQUEST_THRESHOLD_MS = 2000.0

_SAFE_ROUTE_CHARACTER_RE = re.compile(r"[^A-Za-z0-9_./:{}-]")


def generate_request_id() -> str:
    """Return a bounded, non-semantic, server-owned correlation identifier."""
    request_id = secrets.token_hex(REQUEST_ID_LENGTH // 2)
    if not REQUEST_ID_PATTERN.fullmatch(request_id):  # pragma: no cover - stdlib invariant
        raise RuntimeError("Generated request correlation ID violated its contract")
    return request_id


def request_id_from_scope(scope: MutableMapping[str, Any]) -> str | None:
    """Read only a validated server-owned ID retained on one request scope."""
    state = scope.get("state")
    value = state.get("request_id") if isinstance(state, dict) else None
    request_id = str(value or "")
    if REQUEST_ID_PATTERN.fullmatch(request_id):
        return request_id
    return get_request_id()


def _safe_route(scope: MutableMapping[str, Any]) -> str:
    route = scope.get("route")
    route_path = getattr(route, "path", None)
    raw_path = str(route_path or scope.get("path") or "/")
    return _SAFE_ROUTE_CHARACTER_RE.sub("_", raw_path)[:200] or "/"


def _request_actor(scope: MutableMapping[str, Any], request_id: str) -> dict[str, Any]:
    state = scope.get("state")
    current_user = state.get("current_user") if isinstance(state, dict) else None
    if current_user is not None:
        from api.actor_projection import project_authenticated_audit_actor

        return project_authenticated_audit_actor(current_user, request_id=request_id)
    return {
        "actor_type": "anonymous",
        "role": "anonymous",
        "display_name": "Anonymous",
        "request_id": request_id,
    }


def _record_request(
    *,
    scope: MutableMapping[str, Any],
    request_id: str,
    status_code: int,
    duration_ms: float,
) -> None:
    if status_code < 400 and duration_ms < SLOW_REQUEST_THRESHOLD_MS:
        return
    try:
        from src.services.execution_log_service import ExecutionLogService

        ExecutionLogService().record_api_request(
            route=_safe_route(scope),
            method=str(scope.get("method") or "").upper(),
            status_code=status_code,
            duration_ms=duration_ms,
            request_id=request_id,
            actor=_request_actor(scope, request_id),
        )
    except Exception:
        logger.warning(
            "API request execution-log persistence failed request_id=%s",
            request_id,
            exc_info=True,
        )


class RequestCorrelationMiddleware:
    """Own one correlation identity for each API HTTP request."""

    def __init__(self, app: Callable[..., Awaitable[None]]):
        self.app = app

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[..., Awaitable[dict[str, Any]]],
        send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
    ) -> None:
        if scope.get("type") != "http" or not str(scope.get("path") or "").startswith("/api"):
            await self.app(scope, receive, send)
            return

        request_id = generate_request_id()
        token = bind_request_id(request_id)
        state = scope.setdefault("state", {})
        if isinstance(state, dict):
            state["request_id"] = request_id
        started_at = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: MutableMapping[str, Any]) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status") or 500)
                header_name = REQUEST_ID_HEADER.lower().encode("ascii")
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if bytes(name).lower() != header_name
                ]
                headers.append((header_name, request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except BaseException:
            duration_ms = (time.perf_counter() - started_at) * 1000
            logger.error(
                "API request raised before completion method=%s route=%r request_id=%s",
                str(scope.get("method") or "").upper(),
                _safe_route(scope),
                request_id,
                exc_info=True,
            )
            _record_request(
                scope=scope,
                request_id=request_id,
                status_code=500,
                duration_ms=duration_ms,
            )
            raise
        else:
            duration_ms = (time.perf_counter() - started_at) * 1000
            level = logging.ERROR if status_code >= 500 else logging.WARNING if (
                status_code >= 400 or duration_ms >= SLOW_REQUEST_THRESHOLD_MS
            ) else logging.INFO
            logger.log(
                level,
                "API request completed method=%s route=%r status=%d duration_ms=%.0f request_id=%s",
                str(scope.get("method") or "").upper(),
                _safe_route(scope),
                status_code,
                duration_ms,
                request_id,
            )
            _record_request(
                scope=scope,
                request_id=request_id,
                status_code=status_code,
                duration_ms=duration_ms,
            )
        finally:
            reset_request_id(token)


__all__ = [
    "REQUEST_ID_HEADER",
    "REQUEST_ID_LENGTH",
    "RequestCorrelationMiddleware",
    "bind_request_id",
    "generate_request_id",
    "get_request_id",
    "request_id_from_scope",
    "reset_request_id",
]
