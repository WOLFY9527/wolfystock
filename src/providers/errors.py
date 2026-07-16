# -*- coding: utf-8 -*-
"""Provider exception primitives and normalization helpers."""

from __future__ import annotations

import json
import re
import socket
import ssl
from dataclasses import dataclass
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


@dataclass(frozen=True)
class ProviderRetryDisposition:
    """Independent provider failure decisions without raw error details."""

    retry_same_target: bool
    fallback_allowed: bool
    counts_toward_transport_circuit: bool


_RETRYABLE_HTTP_STATUSES = frozenset({408, 425})
_PROVIDER_SCOPED_FALLBACK_REASONS = frozenset(
    {
        ProviderReason.MISSING_API_KEY,
        ProviderReason.NOT_CONFIGURED,
        ProviderReason.UNAUTHORIZED,
        ProviderReason.FORBIDDEN,
        ProviderReason.RATE_LIMITED,
        ProviderReason.TIMEOUT,
        ProviderReason.NO_DATA,
        ProviderReason.CIRCUIT_OPEN,
        ProviderReason.PROVIDER_UNHEALTHY,
        ProviderReason.UNSUPPORTED_MARKET,
        ProviderReason.UNSUPPORTED_CAPABILITY,
    }
)
_STRUCTURED_REASON_ALIASES = {
    "missing_api_key": ProviderReason.MISSING_API_KEY,
    "not_configured": ProviderReason.NOT_CONFIGURED,
    "unauthorized": ProviderReason.UNAUTHORIZED,
    "forbidden": ProviderReason.FORBIDDEN,
    "rate_limited": ProviderReason.RATE_LIMITED,
    "quota": ProviderReason.RATE_LIMITED,
    "quota_exceeded": ProviderReason.RATE_LIMITED,
    "timeout": ProviderReason.TIMEOUT,
    "transport_error": ProviderReason.PROVIDER_UNHEALTHY,
    "empty_response": ProviderReason.PROVIDER_UNHEALTHY,
    "truncated_response": ProviderReason.PROVIDER_UNHEALTHY,
    "provider_unhealthy": ProviderReason.PROVIDER_UNHEALTHY,
    "invalid_payload": ProviderReason.INVALID_PAYLOAD,
    "invalid_request": ProviderReason.INVALID_PAYLOAD,
    "parse_error": ProviderReason.INVALID_PAYLOAD,
    "contract_error": ProviderReason.INVALID_PAYLOAD,
    "no_data": ProviderReason.NO_DATA,
    "unsupported_market": ProviderReason.UNSUPPORTED_MARKET,
    "unsupported_capability": ProviderReason.UNSUPPORTED_CAPABILITY,
    "unsupported_payload": ProviderReason.UNSUPPORTED_CAPABILITY,
    "circuit_open": ProviderReason.CIRCUIT_OPEN,
}


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


def _reason_from_structured_value(value: object) -> ProviderReason | None:
    if isinstance(value, ProviderReason):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        try:
            return ProviderReason(normalized)
        except ValueError:
            return _STRUCTURED_REASON_ALIASES.get(normalized)
    return None


def _reason_from_status_for_retry(http_status: int | None) -> ProviderReason | None:
    status_reason = reason_from_http_status(http_status)
    if status_reason is not None:
        return status_reason
    if http_status in _RETRYABLE_HTTP_STATUSES or (http_status is not None and 500 <= http_status <= 599):
        return ProviderReason.PROVIDER_UNHEALTHY
    if http_status is not None and 400 <= http_status <= 499:
        return ProviderReason.INVALID_PAYLOAD
    return None


def _reason_from_exception_type(exc: BaseException) -> ProviderReason | None:
    if _looks_like_timeout(exc):
        return ProviderReason.TIMEOUT
    if isinstance(exc, (ssl.SSLCertVerificationError, json.JSONDecodeError, KeyError, TypeError, ValueError, AssertionError)):
        return ProviderReason.INVALID_PAYLOAD
    if isinstance(exc, (ConnectionError, socket.gaierror, socket.herror)):
        return ProviderReason.PROVIDER_UNHEALTHY
    if isinstance(exc, ssl.SSLError):
        return ProviderReason.PROVIDER_UNHEALTHY

    name = exc.__class__.__name__.lower()
    if any(
        marker in name
        for marker in (
            "connectionerror",
            "connecterror",
            "chunkedencodingerror",
            "incompleteread",
            "protocolerror",
            "remotedisconnected",
        )
    ):
        return ProviderReason.PROVIDER_UNHEALTHY
    return None


def _has_certificate_verification_failure(exc: BaseException) -> bool:
    pending: list[BaseException] = [exc]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, ssl.SSLCertVerificationError):
            return True
        for related in (
            getattr(current, "__cause__", None),
            getattr(current, "__context__", None),
            getattr(current, "reason", None),
        ):
            if isinstance(related, BaseException):
                pending.append(related)
    return False


def _reason_from_compatibility_text(exc: BaseException) -> ProviderReason | None:
    text = str(exc).lower()
    if "certificate verify" in text or "certificate validation" in text:
        return ProviderReason.INVALID_PAYLOAD

    status_match = re.search(r"(?<!\d)(401|403|408|425|429|5\d\d)(?!\d)", text)
    if status_match is not None:
        return _reason_from_status_for_retry(int(status_match.group(1)))

    if any(marker in text for marker in ("invalid api key", "invalid_api_key", "authentication failed")):
        return ProviderReason.UNAUTHORIZED
    if any(marker in text for marker in ("permission denied", "not authorized")):
        return ProviderReason.FORBIDDEN
    if any(marker in text for marker in ("rate limit", "rate_limit", "quota exceeded", "quota exhausted")):
        return ProviderReason.RATE_LIMITED
    if any(marker in text for marker in ("bad request", "invalid request", "invalid payload", "unsupported payload")):
        return ProviderReason.INVALID_PAYLOAD
    if any(
        marker in text
        for marker in (
            "connection reset",
            "connection refused",
            "connection aborted",
            "name resolution",
            "temporary failure in name resolution",
            "premature chunk",
            "truncated response",
            "incomplete read",
        )
    ):
        return ProviderReason.PROVIDER_UNHEALTHY
    return None


def classify_provider_retry_disposition(
    failure: BaseException | ProviderReason | str,
    *,
    http_status: int | None = None,
) -> ProviderRetryDisposition:
    """Classify retry, fallback and circuit decisions for one provider failure."""

    if isinstance(failure, BaseException) and _has_certificate_verification_failure(failure):
        reason = ProviderReason.INVALID_PAYLOAD
    else:
        reason = _reason_from_structured_value(failure)
    if reason == ProviderReason.UNKNOWN_ERROR:
        reason = None
    if reason is None and isinstance(failure, BaseException):
        reason = _reason_from_structured_value(getattr(failure, "reason", None))
        if reason == ProviderReason.UNKNOWN_ERROR:
            reason = None
        if reason is None:
            extracted_status = http_status if http_status is not None else _http_status_from_exception(failure)
            reason = _reason_from_status_for_retry(extracted_status)
        if reason is None:
            reason = _reason_from_exception_type(failure)
        if reason is None:
            reason = _reason_from_compatibility_text(failure)
    elif reason is None:
        reason = _reason_from_status_for_retry(http_status)

    retry_same_target = reason in {ProviderReason.TIMEOUT, ProviderReason.PROVIDER_UNHEALTHY}
    return ProviderRetryDisposition(
        retry_same_target=retry_same_target,
        fallback_allowed=reason in _PROVIDER_SCOPED_FALLBACK_REASONS,
        counts_toward_transport_circuit=retry_same_target,
    )


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
