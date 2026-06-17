# -*- coding: utf-8 -*-
"""Tests for adapting research queue packets into evidence provenance ledgers."""

from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from src.services.research_queue_evidence_provenance_adapter import (
    build_research_queue_evidence_provenance_ledger,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = REPO_ROOT / "src/services/research_queue_evidence_provenance_adapter.py"

LEDGER_ENTRY_FIELDS = {
    "evidenceId",
    "sourceSurface",
    "evidenceFamily",
    "freshnessBucket",
    "authorityBucket",
    "consumerSafeSourceLabel",
    "usedFor",
    "limitation",
    "observationOnly",
}
FORBIDDEN_IMPORT_PREFIXES = (
    "api",
    "apps",
    "data_provider",
    "dotenv",
    "duckdb",
    "fastapi",
    "httpx",
    "redis",
    "requests",
    "server",
    "sqlalchemy",
    "src.config",
    "src.core",
    "src.repositories",
    "src.services.market_cache",
    "src.storage",
    "starlette",
    "urllib",
    "urllib3",
)
FORBIDDEN_PUBLIC_TERMS = (
    "buy",
    "sell",
    "hold",
    "recommendation",
    "target price",
    "stop loss",
    "position sizing",
    "买入",
    "卖出",
    "持有",
    "交易建议",
    "投资建议",
    "目标价",
    "止损",
    "仓位",
)
FORBIDDEN_RAW_TERMS = (
    "provider",
    "request id",
    "trace id",
    "source_ref",
    "sourceref",
    "reasoncode",
    "debug",
    "raw payload",
    "raw diagnostics",
    "runtime",
    "marketcache",
    "token",
    "https://",
    "/users/",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _matches_prefix(module_name: str, prefix: str) -> bool:
    return module_name == prefix or module_name.startswith(f"{prefix}.")


def _serialized_values(payload: object) -> str:
    values: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, str):
            values.append(value)
            return
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    visit(payload)
    return json.dumps(values, ensure_ascii=False, sort_keys=True).lower()


def test_adapts_research_queue_items_to_t1708_ledger_without_mutating_input() -> None:
    research_queue_packet: dict[str, Any] = {
        "schemaVersion": "research_queue_v1",
        "researchQueue": [
            {
                "queueItemId": "scanner-ALFA-run-42-rank-1-item-1",
                "sourceSurface": "scanner",
                "symbol": "ALFA",
                "evidenceUsed": ["Technicals available", "News catalyst context"],
                "evidenceGaps": [],
                "freshness": {"state": "current", "lastReviewedAt": "2026-06-15T09:30:00+00:00"},
                "observationOnly": True,
                "diagnostics": {
                    "providerTrace": "provider debug trace id should never leak",
                    "raw_payload": "raw payload should never leak",
                },
            },
            {
                "queueItemId": "watchlist-MSFT-item-1",
                "sourceSurface": "watchlist",
                "symbol": "MSFT",
                "evidenceUsed": [],
                "evidenceGaps": ["Fundamental evidence is missing."],
                "freshness": {"state": "needs_review", "lastReviewedAt": None},
                "observationOnly": True,
            },
            {
                "queueItemId": "market-SPY-item-1",
                "sourceSurface": "market",
                "symbol": "SPY",
                "evidenceUsed": ["Macro context available"],
                "evidenceGaps": [],
                "freshness": {"state": "unknown", "lastReviewedAt": None},
                "observationOnly": True,
            },
        ],
        "observationOnly": True,
        "decisionGrade": False,
    }
    original_packet = copy.deepcopy(research_queue_packet)

    payload = build_research_queue_evidence_provenance_ledger(research_queue_packet)

    assert research_queue_packet == original_packet
    assert set(payload) == {"contractVersion", "evidenceProvenanceLedger"}
    ledger = payload["evidenceProvenanceLedger"]
    assert [set(entry) for entry in ledger] == [LEDGER_ENTRY_FIELDS] * 4
    assert ledger == [
        {
            "evidenceId": "evidence-1",
            "sourceSurface": "scanner_overlay",
            "evidenceFamily": "market_data",
            "freshnessBucket": "current",
            "authorityBucket": "observation_only",
            "consumerSafeSourceLabel": "Primary market data summary",
            "usedFor": ["technical_context"],
            "limitation": "observation_only",
            "observationOnly": True,
        },
        {
            "evidenceId": "evidence-2",
            "sourceSurface": "scanner_overlay",
            "evidenceFamily": "news",
            "freshnessBucket": "current",
            "authorityBucket": "observation_only",
            "consumerSafeSourceLabel": "News context",
            "usedFor": ["news_context"],
            "limitation": "observation_only",
            "observationOnly": True,
        },
        {
            "evidenceId": "evidence-3",
            "sourceSurface": "watchlist_overlay",
            "evidenceFamily": "fundamentals",
            "freshnessBucket": "partial",
            "authorityBucket": "observation_only",
            "consumerSafeSourceLabel": "Fundamentals summary",
            "usedFor": ["fundamentals_review"],
            "limitation": "limited_coverage",
            "observationOnly": True,
        },
        {
            "evidenceId": "evidence-4",
            "sourceSurface": "market_research",
            "evidenceFamily": "macro",
            "freshnessBucket": "unknown",
            "authorityBucket": "observation_only",
            "consumerSafeSourceLabel": "Macro context summary",
            "usedFor": ["macro_context"],
            "limitation": "observation_only",
            "observationOnly": True,
        },
    ]


def test_adapter_fail_closed_against_advice_and_raw_diagnostic_values() -> None:
    payload = build_research_queue_evidence_provenance_ledger(
        {
            "schemaVersion": "research_queue_v1",
            "researchQueue": [
                {
                    "queueItemId": "provider-trace-marker",
                    "sourceSurface": "provider runtime /Users/me/cache.duckdb",
                    "symbol": "RAW",
                    "evidenceUsed": [
                        "provider runtime debug says buy now at target price",
                        "https://provider.example/raw-payload?token=placeholder",
                    ],
                    "evidenceGaps": ["sourceRefId reasonCode provider_timeout trace id"],
                    "freshness": {"state": "MarketCache debug trace"},
                    "observationOnly": False,
                    "rawJson": {"sourceRefs": ["provider-request-id"]},
                }
            ],
        }
    )

    assert payload["evidenceProvenanceLedger"] == [
        {
            "evidenceId": "evidence-1",
            "sourceSurface": "general",
            "evidenceFamily": "research_context",
            "freshnessBucket": "unknown",
            "authorityBucket": "observation_only",
            "consumerSafeSourceLabel": "Research context",
            "usedFor": ["research_context"],
            "limitation": "limited_coverage",
            "observationOnly": True,
        }
    ]
    serialized = _serialized_values(payload)
    for forbidden in (*FORBIDDEN_PUBLIC_TERMS, *FORBIDDEN_RAW_TERMS):
        assert forbidden.lower() not in serialized


def test_adapter_imports_stay_inert() -> None:
    imports = _imports(ADAPTER_PATH)
    assert all(
        not _matches_prefix(module_name, forbidden)
        for module_name in imports
        for forbidden in FORBIDDEN_IMPORT_PREFIXES
    )

    script = """
import sys
before = set(sys.modules)
import src.services.research_queue_evidence_provenance_adapter
after = set(sys.modules)
for forbidden in [
    "data_provider",
    "requests",
    "httpx",
    "openai",
    "src.core.pipeline",
    "src.repositories.scanner_repo",
    "src.services.market_cache",
    "src.services.market_scanner_service",
    "src.services.research_queue_aggregator_service",
]:
    assert forbidden not in after - before, f"unexpected import side effect: {forbidden}"
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
