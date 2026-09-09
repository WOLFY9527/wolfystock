"""Canonical completion truth for persisted historical Backtest runs."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional


def effective_backtest_run_status(
    row: Any,
    *,
    summary: Optional[Dict[str, Any]] = None,
) -> str:
    """Expose completed only when persisted calculation evidence is present."""
    status = str(getattr(row, "status", None) or "").strip().lower()
    if status != "completed":
        return status or "blocked"

    stored_summary = dict(summary or {}) if isinstance(summary, dict) else {}
    if not stored_summary:
        raw_summary = getattr(row, "summary_json", None)
        if raw_summary:
            try:
                parsed_summary = json.loads(raw_summary)
            except (TypeError, ValueError):
                parsed_summary = {}
            if isinstance(parsed_summary, dict):
                stored_summary = parsed_summary

    calculation_counts = (
        getattr(row, "completed", 0),
        getattr(row, "completed_count", 0),
        stored_summary.get("completed_count", 0),
    )
    try:
        has_completed_calculation = any(int(value or 0) > 0 for value in calculation_counts)
        persisted_result_count = max(
            int(getattr(row, "saved", 0) or 0),
            int(getattr(row, "result_count", 0) or 0),
        )
        has_legacy_result_evidence = (
            persisted_result_count > 0
            and int(getattr(row, "insufficient", 0) or 0) == 0
            and int(getattr(row, "errors", 0) or 0) == 0
        )
    except (TypeError, ValueError):
        has_completed_calculation = False
        has_legacy_result_evidence = False
    return "completed" if has_completed_calculation or has_legacy_result_evidence else "blocked"
