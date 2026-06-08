# -*- coding: utf-8 -*-
"""Tests for local user alert dry-run review summaries."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from src.services.user_alert_dry_run_summary import summarize_user_alert_dry_run_results


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src/services/user_alert_dry_run_summary.py"


FORBIDDEN_IMPORT_PREFIXES = (
    "api",
    "fastapi",
    "starlette",
    "server",
    "data_provider",
    "src.repositories",
    "src.storage",
    "duckdb",
    "psycopg",
    "redis",
    "sqlalchemy",
    "sqlite3",
    "src.services.market_cache",
    "src.services.market_cache_redis_backend",
    "src.notification",
    "src.services.notification_service",
    "main",
    "src.core",
    "apps",
    "dotenv",
    "decouple",
    "environs",
    "pydantic_settings",
    "src.config",
    "aiohttp",
    "httpx",
    "requests",
    "urllib",
    "urllib3",
    "websocket",
    "websockets",
)


def _matches_prefix(module_name: str, prefix: str) -> bool:
    return module_name == prefix or module_name.startswith(f"{prefix}.")


def _collect_imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
            continue
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_summary_counts_are_deterministic_and_sanitized() -> None:
    results = [
        {
            "status": "observed",
            "dryRun": True,
            "outboundAttempted": False,
            "liveOutbound": False,
            "alertDeliveryIntent": True,
            "reasonCode": "internal_only",
            "providerTrace": ["hidden"],
            "rawDiagnostics": {"hidden": True},
        },
        {
            "state": "suppressed_advisory_only",
            "dryRun": True,
            "outboundAttempted": False,
            "liveOutbound": False,
            "alertDeliveryIntent": False,
        },
        {
            "status": "insufficient-data",
            "dryRun": True,
            "outboundAttempted": False,
            "liveOutbound": False,
        },
        {
            "status": "failed",
            "dryRun": True,
            "outboundAttempted": False,
            "liveOutbound": False,
            "error": "internal detail",
        },
    ]

    expected = {
        "totalCount": 4,
        "observedCount": 1,
        "suppressedCount": 1,
        "insufficientDataCount": 1,
        "errorCount": 1,
        "safeStatus": "PARTIAL",
        "noSendReview": {
            "dryRun": True,
            "noSend": True,
            "outboundAttempted": False,
            "liveOutbound": False,
        },
        "consumerSummary": (
            "Alert review checked 4 items: 1 observed, 1 quiet, "
            "1 limited by data, 1 needs review. No messages were sent."
        ),
        "adminSummary": (
            "Local alert review: total 4, observed 1, suppressed 1, "
            "insufficient data 1, errors 1. Send boundary clear."
        ),
    }

    assert summarize_user_alert_dry_run_results(results) == expected
    assert summarize_user_alert_dry_run_results(tuple(results)) == expected

    serialized = json.dumps(expected, ensure_ascii=False)
    forbidden_fragments = (
        "reasonCode",
        "reason code",
        "provider",
        "trace",
        "raw",
        "diagnostic",
        "diagnostics",
        "_",
        "bu" + "y",
        "se" + "ll",
        "st" + "op",
        "tar" + "get",
        "position" + "-sizing",
    )
    for fragment in forbidden_fragments:
        assert fragment not in serialized


def test_live_outbound_flags_fail_closed_without_relabeling_as_observed() -> None:
    summary = summarize_user_alert_dry_run_results(
        [
            {
                "status": "observed",
                "dryRun": True,
                "outboundAttempted": True,
                "liveOutbound": False,
                "alertDeliveryIntent": True,
            },
            {
                "status": "suppressed",
                "dryRun": True,
                "outboundAttempted": False,
                "liveOutbound": False,
            },
        ]
    )

    assert summary == {
        "totalCount": 2,
        "observedCount": 0,
        "suppressedCount": 1,
        "insufficientDataCount": 0,
        "errorCount": 1,
        "safeStatus": "PAUSED",
        "noSendReview": {
            "dryRun": True,
            "noSend": False,
            "outboundAttempted": True,
            "liveOutbound": False,
        },
        "consumerSummary": (
            "Alert review paused because a send boundary flag was raised. "
            "Treat this as local review only."
        ),
        "adminSummary": (
            "Local alert review failed closed: total 2, observed 0, suppressed 1, "
            "insufficient data 0, errors 1. Send boundary flag detected."
        ),
    }


def test_helper_has_no_protected_runtime_imports() -> None:
    imported_modules = _collect_imported_modules(MODULE_PATH)
    violations = sorted(
        module_name
        for module_name in imported_modules
        if any(_matches_prefix(module_name, prefix) for prefix in FORBIDDEN_IMPORT_PREFIXES)
    )
    assert violations == []
