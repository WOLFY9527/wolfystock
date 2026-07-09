# -*- coding: utf-8 -*-
"""Small helpers for safe API error envelopes."""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

_UNSAFE_PUBLIC_ERROR_RE = re.compile(
    r"("
    r"traceback|"
    r"\b(?:runtimeerror|valueerror|keyerror|typeerror|httpexception|exception)\b|"
    r"https?://|"
    r"(?:^|[\s\"'=])/(?:users|srv|var|tmp|private|applications|library)/|"
    r"\b(?:api[-_]?key|authorization|bearer|cookie|password|private[-_]?key|secret|session[-_]?id|"
    r"session[-_]?token|token)\b|"
    r"\b(?:provider[-_]?url|api[-_]?base[-_]?url|reasoncode|trustlevel|launch\s*verdict|"
    r"fallback|internal\s*phase|phase)\b"
    r")",
    re.IGNORECASE,
)
_SAFE_ERROR_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def safe_public_error_message(message: str, *, fallback: str = "Request could not be processed.") -> str:
    """Return a consumer-safe message, replacing internal-looking text."""
    text = str(message or "").strip()
    if not text:
        return fallback
    if _UNSAFE_PUBLIC_ERROR_RE.search(text):
        return fallback
    return text


def safe_error_identifier(value: Any) -> str | None:
    """Return a bounded client-safe identifier for error metadata, or None."""
    text = str(value or "").strip()
    if not text:
        return None
    if not _SAFE_ERROR_IDENTIFIER_RE.fullmatch(text):
        return None
    if _UNSAFE_PUBLIC_ERROR_RE.search(text):
        return None
    return text


def build_safe_error_payload(
    *,
    error: str,
    message: str,
    status_code: int | None = None,
    retryable: bool | None = None,
    detail: Any = None,
    fallback_message: str = "Request could not be processed.",
) -> dict[str, Any]:
    """Build the flat ErrorResponse shape without exception-derived text."""
    error_code = str(error or "internal_error")
    payload: dict[str, Any] = {
        "error": error_code,
        "code": error_code,
        "message": safe_public_error_message(message, fallback=fallback_message),
    }
    if status_code is not None:
        payload["status"] = int(status_code)
    payload["reason"] = error_code
    payload["consumerSafeMessage"] = payload["message"]
    if retryable is not None:
        payload["retryable"] = bool(retryable)
    if detail is not None:
        payload["detail"] = detail
    return payload


def safe_api_error(
    *,
    status_code: int,
    error: str,
    message: str,
    retryable: bool | None = None,
    detail: Any = None,
    fallback_message: str = "Request could not be processed.",
) -> HTTPException:
    """Return an HTTPException whose public body is a stable safe envelope."""
    return HTTPException(
        status_code=status_code,
        detail=build_safe_error_payload(
            error=error,
            message=message,
            status_code=status_code,
            retryable=retryable,
            detail=detail,
            fallback_message=fallback_message,
        ),
    )
