"""Inert context propagation primitive for bounded request correlation."""

from __future__ import annotations

import re
from contextvars import ContextVar, Token


REQUEST_ID_LENGTH = 32
REQUEST_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")

_request_id_context: ContextVar[str | None] = ContextVar(
    "api_request_correlation_id",
    default=None,
)


def get_request_id() -> str | None:
    """Return the current request ID, or ``None`` outside a bound context."""
    return _request_id_context.get()


def bind_request_id(request_id: str) -> Token[str | None]:
    """Bind a validated server-owned ID and return its reset token."""
    if not REQUEST_ID_PATTERN.fullmatch(str(request_id or "")):
        raise ValueError("request_id must be a 32-character lowercase hexadecimal value")
    return _request_id_context.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the exact context state that preceded ``bind_request_id``."""
    _request_id_context.reset(token)


__all__ = [
    "REQUEST_ID_LENGTH",
    "REQUEST_ID_PATTERN",
    "bind_request_id",
    "get_request_id",
    "reset_request_id",
]
