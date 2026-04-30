# -*- coding: utf-8 -*-
"""Provider exception primitives and normalization helpers."""

from __future__ import annotations

import json
import socket
from typing import Any

from src.providers.types import ProviderCapability, ProviderReason, ProviderResult


class ProviderError(Exception):
    reason = ProviderReason.UNKNOWN_ERROR

    def __init__(self, message: str = "", *, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


class ProviderMissingCredentials(ProviderError):
    reason = ProviderReason.MISSING_API_KEY


class ProviderUnauthorized(ProviderError):
    reason = ProviderReason.UNAUTHORIZED


class ProviderForbidden(ProviderError):
    reason = ProviderReason.FORBIDDEN


class ProviderRateLimited(ProviderError):
    reason = ProviderReason.RATE_LIMITED


class ProviderTimeout(ProviderError):
    reason = ProviderReason.TIMEOUT


class ProviderInvalidPayload(ProviderError):
    reason = ProviderReason.INVALID_PAYLOAD


class ProviderNoData(ProviderError):
    reason = ProviderReason.NO_DATA


class ProviderUnsupported(ProviderError):
    reason = ProviderReason.UNSUPPORTED_CAPABILITY


class ProviderCircuitOpen(ProviderError):
    reason = ProviderReason.CIRCUIT_OPEN


def _http_status_from_exception(exc: BaseException) -> int | None:
    status = getattr(exc, "status_code", None) or getattr(exc, "http_status", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


def reason_from_http_status(http_status: int | None) -> ProviderReason | None:
    if http_status == 401:
        return ProviderReason.UNAUTHORIZED
    if http_status == 403:
        return ProviderReason.FORBIDDEN
    if http_status == 429:
        return ProviderReason.RATE_LIMITED
    return None


def _looks_like_timeout(exc: BaseException) -> bool:
    name = exc.__class__.__name__.lower()
    text = str(exc).lower()
    return "timeout" in name or "timed out" in text or isinstance(exc, socket.timeout)


def normalize_provider_exception(exc: BaseException) -> ProviderReason:
    if isinstance(exc, ProviderError):
        return exc.reason

    status_reason = reason_from_http_status(_http_status_from_exception(exc))
    if status_reason is not None:
        return status_reason

    if _looks_like_timeout(exc):
        return ProviderReason.TIMEOUT
    if isinstance(exc, (json.JSONDecodeError, KeyError, TypeError)):
        return ProviderReason.INVALID_PAYLOAD
    if isinstance(exc, ValueError):
        text = str(exc).lower()
        if "empty" in text or "no data" in text:
            return ProviderReason.NO_DATA
        if "json" in text or "payload" in text or "missing" in text or "field" in text:
            return ProviderReason.INVALID_PAYLOAD

    return ProviderReason.UNKNOWN_ERROR


def provider_failed_result_from_exception(
    exc: BaseException,
    *,
    provider: str,
    capability: ProviderCapability | str,
    data: Any | None = None,
    durationMs: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProviderResult:
    return ProviderResult.failed(
        provider=provider,
        capability=capability,
        reason=normalize_provider_exception(exc),
        errorMessage=str(exc) or exc.__class__.__name__,
        data=data,
        httpStatus=_http_status_from_exception(exc),
        durationMs=durationMs,
        metadata=metadata or {},
    )
