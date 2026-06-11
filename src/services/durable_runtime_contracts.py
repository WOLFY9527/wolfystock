# -*- coding: utf-8 -*-
"""Guarded Durable Runtime v1 prototype contracts.

This module is deliberately small and synthetic-only. It does not enable
production worker cutover and does not import provider, analysis, or backtest
runtime services.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


DURABLE_RUNTIME_V1_SCHEMA = "durable_runtime_v1"
DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE = "durable_runtime_v1_synthetic"
DURABLE_RUNTIME_PRODUCTION_CUTOVER_ENABLED = False

_ALLOWED_JOB_KINDS = frozenset({"analysis_fixture", "backtest_fixture"})
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_SYNTHETIC_GUARD_METADATA_KEYS = frozenset(
    {
        "runtime_schema",
        "task_type",
        "job_kind",
        "fixture_name",
        "source",
        "production_cutover_enabled",
        "symbol",
    }
)
_SYNTHETIC_GUARD_METADATA_KEY_COMPACTS = frozenset(
    key.replace("_", "") for key in _SYNTHETIC_GUARD_METADATA_KEYS
)
_UNSAFE_METADATA_KEY_EXACT = frozenset(
    {
        "api_key",
        "provider_payload",
    }
)
_UNSAFE_METADATA_KEY_COMPACTS = frozenset(
    {
        "apikey",
        "providerpayload",
    }
)
_UNSAFE_METADATA_KEY_PARTS = frozenset(
    {
        "authorization",
        "cookie",
        "debug",
        "prompt",
        "secret",
        "session",
        "stack",
        "token",
        "trace",
        "url",
        "webhook",
    }
)
_STATUS_TO_API_STATUS = {
    "queued": "pending",
    "pending": "pending",
    "waiting_retry": "pending",
    "leased": "processing",
    "processing": "processing",
    "running": "processing",
    "completed": "completed",
    "failed": "failed",
    "cancelled": "failed",
    "canceled": "failed",
}


def _metadata_key_forms(key: object) -> tuple[str, str, set[str]]:
    text = str(key or "").strip()
    separated = _CAMEL_BOUNDARY_RE.sub("_", text)
    normalized = _NON_ALNUM_RE.sub("_", separated.lower()).strip("_")
    compact = _NON_ALNUM_RE.sub("", separated.lower())
    parts = {part for part in normalized.split("_") if part}
    return normalized, compact, parts


def _is_unsafe_extra_metadata_key(key: object) -> bool:
    normalized, compact, parts = _metadata_key_forms(key)
    if not normalized:
        return True
    if normalized in _SYNTHETIC_GUARD_METADATA_KEYS or compact in _SYNTHETIC_GUARD_METADATA_KEY_COMPACTS:
        return True
    if normalized == "raw" or normalized.startswith("raw_") or compact.startswith("raw"):
        return True
    if normalized in _UNSAFE_METADATA_KEY_EXACT or compact in _UNSAFE_METADATA_KEY_COMPACTS:
        return True
    return bool(parts.intersection(_UNSAFE_METADATA_KEY_PARTS))


def _sanitize_extra_metadata_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize_extra_metadata_value(item)
            for key, item in value.items()
            if not _is_unsafe_extra_metadata_key(key)
        }
    if isinstance(value, list):
        return [_sanitize_extra_metadata_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_extra_metadata_value(item) for item in value]
    return value


def _sanitize_extra_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: _sanitize_extra_metadata_value(value)
        for key, value in metadata.items()
        if not _is_unsafe_extra_metadata_key(key)
    }


def normalize_durable_runtime_status(status: object) -> str:
    """Project durable stored states into existing API-safe task statuses."""
    normalized = str(status or "").strip().lower()
    if not normalized:
        return "pending"
    return _STATUS_TO_API_STATUS.get(normalized, "processing")


def build_durable_runtime_envelope(
    *,
    job_kind: str,
    fixture_name: str,
    symbol: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build bounded metadata for a synthetic Durable Runtime v1 task."""
    normalized_job_kind = str(job_kind or "").strip()
    normalized_fixture_name = str(fixture_name or "").strip()
    if normalized_job_kind not in _ALLOWED_JOB_KINDS:
        raise ValueError("Durable Runtime v1 only accepts synthetic fixture job kinds")
    if not normalized_fixture_name:
        raise ValueError("fixture_name is required")

    envelope: Dict[str, Any] = {}
    if isinstance(extra_metadata, dict):
        envelope.update(_sanitize_extra_metadata(extra_metadata))

    envelope.update(
        {
            "runtime_schema": DURABLE_RUNTIME_V1_SCHEMA,
            "task_type": DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE,
            "job_kind": normalized_job_kind,
            "fixture_name": normalized_fixture_name[:80],
            "source": "synthetic_fixture",
            "production_cutover_enabled": DURABLE_RUNTIME_PRODUCTION_CUTOVER_ENABLED,
        }
    )
    if symbol is not None:
        envelope["symbol"] = str(symbol or "").strip()[:32]
    return envelope
