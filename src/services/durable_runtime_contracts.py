# -*- coding: utf-8 -*-
"""Guarded Durable Runtime v1 prototype contracts.

This module is deliberately small and synthetic-only. It does not enable
production worker cutover and does not import provider, analysis, or backtest
runtime services.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


DURABLE_RUNTIME_V1_SCHEMA = "durable_runtime_v1"
DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE = "durable_runtime_v1_synthetic"
DURABLE_RUNTIME_PRODUCTION_CUTOVER_ENABLED = False

_ALLOWED_JOB_KINDS = frozenset({"analysis_fixture", "backtest_fixture"})
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
        envelope.update(extra_metadata)

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
