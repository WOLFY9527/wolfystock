# -*- coding: utf-8 -*-
"""Small security helpers for masking secrets before API/log exposure."""

from __future__ import annotations

import re
from typing import Any

_SENSITIVE_KEY_RE = re.compile(
    r"(api[-_]?key|apikey|access[-_]?token|refresh[-_]?token|session[-_]?token|token|authorization|bearer|credential|private[-_]?key|secret|password)",
    re.IGNORECASE,
)
_QUERY_SECRET_RE = re.compile(
    r"([?&](?:api[-_]?key|apikey|access[-_]?token|refresh[-_]?token|session[-_]?token|token|authorization|secret|password|credential|private[-_]?key)=)[^&#\s]+",
    re.IGNORECASE,
)
_KV_SECRET_RE = re.compile(
    r"\b(api[-_]?key|apikey|access[-_]?token|refresh[-_]?token|session[-_]?token|token|authorization|secret|password|credential|private[-_]?key)\b\s*[:=]\s*([^\s,;&]+)",
    re.IGNORECASE,
)
_AUTH_HEADER_RE = re.compile(r"\b(Authorization)\s*:\s*([^\r\n,;]+)", re.IGNORECASE)
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)


def is_sensitive_key(key: str) -> bool:
    """Return whether a config/metadata key name should be treated as secret."""
    return bool(_SENSITIVE_KEY_RE.search(str(key or "")))


def mask_secret(value: str) -> str:
    """Return a display-only masked representation for a secret value."""
    secret = str(value or "").strip()
    if not secret:
        return ""
    if secret.lower().startswith("sk-") and len(secret) > 7:
        return f"sk-...{secret[-4:]}"
    if len(secret) <= 8:
        return "已配置"
    return f"{secret[:4]}...{secret[-4:]}"


def is_masked_secret(value: str, current_value: str = "", mask_token: str = "******") -> bool:
    """Return whether *value* is a display placeholder, not a new secret."""
    text = str(value or "").strip()
    if not text:
        return False
    placeholders = {str(mask_token or "").strip(), "已配置", "***"}
    if current_value:
        placeholders.add(mask_secret(current_value))
    return text in placeholders or bool(re.fullmatch(r".{1,12}\.\.\..{1,12}", text))


def sanitize_url(url: str) -> str:
    """Mask secret-like query parameters in a URL or URL-like string."""
    text = str(url or "")
    if not text:
        return text
    return _QUERY_SECRET_RE.sub(r"\1***", text)


def sanitize_message(message: str) -> str:
    """Mask secret-like fragments inside free-form text."""
    text = sanitize_url(str(message or ""))
    if not text:
        return text
    text = _AUTH_HEADER_RE.sub(r"\1: ***", text)
    text = _BEARER_RE.sub("Bearer ***", text)
    text = _KV_SECRET_RE.sub(r"\1=***", text)
    return text


def sanitize_metadata(obj: Any) -> Any:
    """Recursively mask secret values in JSON-like metadata."""
    if isinstance(obj, dict):
        sanitized: dict[str, Any] = {}
        for key, value in obj.items():
            key_text = str(key)
            if is_sensitive_key(key_text):
                sanitized[key_text] = "***" if value not in (None, "") else value
            else:
                sanitized[key_text] = sanitize_metadata(value)
        return sanitized
    if isinstance(obj, list):
        return [sanitize_metadata(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(sanitize_metadata(item) for item in obj)
    if isinstance(obj, str):
        return sanitize_message(obj)
    return obj
