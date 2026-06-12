# -*- coding: utf-8 -*-
"""Small helpers for safe API error envelopes."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def build_safe_error_payload(
    *,
    error: str,
    message: str,
    detail: Any = None,
) -> dict[str, Any]:
    """Build the flat ErrorResponse shape without exception-derived text."""
    payload: dict[str, Any] = {
        "error": str(error or "internal_error"),
        "message": str(message or "Request could not be processed."),
    }
    if detail is not None:
        payload["detail"] = detail
    return payload


def safe_api_error(
    *,
    status_code: int,
    error: str,
    message: str,
    detail: Any = None,
) -> HTTPException:
    """Return an HTTPException whose public body is a stable safe envelope."""
    return HTTPException(
        status_code=status_code,
        detail=build_safe_error_payload(error=error, message=message, detail=detail),
    )
