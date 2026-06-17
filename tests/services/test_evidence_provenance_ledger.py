# -*- coding: utf-8 -*-
"""Tests for the consumer-safe evidence provenance ledger helper."""

from __future__ import annotations

import ast
import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/evidence_provenance_ledger.py"
CONTRACT_PATH = REPO_ROOT / "src/contracts/evidence/provenance_ledger.py"

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


def test_builds_bounded_consumer_safe_ledger_shape() -> None:
    from src.services.evidence_provenance_ledger import (
        EVIDENCE_PROVENANCE_LEDGER_VERSION,
        build_evidence_provenance_ledger,
    )

    payload = build_evidence_provenance_ledger(
        [
            {
                "evidenceId": "request_id=raw-provider-abc123",
                "sourceSurface": "singleStockEvidencePacket",
                "evidenceDomain": "priceHistory",
                "freshnessState": "live",
                "authorityTier": "score_grade",
                "sourceLabel": "https://provider.example/raw?token=secret",
                "usedFor": ["price history", "buy now"],
                "limitation": "none",
                "observationOnly": False,
                "debugRef": "trace:raw-provider-request",
                "rawPayload": {"token": "secret-value"},
            },
            {
                "sourceSurface": "researchReadiness",
                "evidenceFamily": "news",
                "freshnessBucket": "stale",
                "authorityBucket": "public_proxy",
                "consumerSafeSourceLabel": "News context",
                "usedFor": "news catalysts",
                "limitations": ["provider_timeout", "token=secret"],
                "observationOnly": False,
            },
        ]
    )

    assert payload["contractVersion"] == EVIDENCE_PROVENANCE_LEDGER_VERSION
    assert set(payload) == {"contractVersion", "evidenceProvenanceLedger"}
    ledger = payload["evidenceProvenanceLedger"]
    assert [set(entry) for entry in ledger] == [LEDGER_ENTRY_FIELDS, LEDGER_ENTRY_FIELDS]
    assert ledger == [
        {
            "evidenceId": "evidence-1",
            "sourceSurface": "research_packet",
            "evidenceFamily": "market_data",
            "freshnessBucket": "current",
            "authorityBucket": "primary",
            "consumerSafeSourceLabel": "Primary market data summary",
            "usedFor": ["price_history"],
            "limitation": "none",
            "observationOnly": False,
        },
        {
            "evidenceId": "evidence-2",
            "sourceSurface": "research_packet",
            "evidenceFamily": "news",
            "freshnessBucket": "stale",
            "authorityBucket": "observation_only",
            "consumerSafeSourceLabel": "News context",
            "usedFor": ["news_context"],
            "limitation": "stale_or_delayed",
            "observationOnly": True,
        },
    ]
    assert json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True)) == payload


def test_unknown_and_unsafe_values_fail_closed_without_raw_diagnostics_or_advice() -> None:
    from src.services.evidence_provenance_ledger import build_evidence_provenance_ledger

    payload = build_evidence_provenance_ledger(
        [
            {
                "sourceSurface": "MarketCache runtime /Users/me/cache.duckdb",
                "evidenceFamily": "raw_provider_payload",
                "freshnessBucket": "cache_debug_trace",
                "authorityBucket": "sourceAuthorityAllowed",
                "consumerSafeSourceLabel": "Authorization bearer token=secret",
                "usedFor": ["target price", "scoreContributionAllowed"],
                "limitation": "raw provider payload trace",
                "observationOnly": False,
                "sourceRefId": "provider-trace-123",
            }
        ]
    )

    assert payload["evidenceProvenanceLedger"] == [
        {
            "evidenceId": "evidence-1",
            "sourceSurface": "general",
            "evidenceFamily": "general",
            "freshnessBucket": "unknown",
            "authorityBucket": "unknown",
            "consumerSafeSourceLabel": "Evidence source summary",
            "usedFor": ["research_context"],
            "limitation": "redacted_input",
            "observationOnly": True,
        }
    ]
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in (
        "authorization",
        "bearer",
        "cache.duckdb",
        "debug",
        "payload",
        "provider",
        "raw",
        "scorecontributionallowed",
        "sourceauthorityallowed",
        "sourcerefid",
        "target price",
        "token",
        "trace",
        "/users/",
    ):
        assert forbidden not in serialized


def test_contract_boundary_exports_builder_and_imports_stay_inert() -> None:
    service = importlib.import_module("src.services.evidence_provenance_ledger")
    package = importlib.import_module("src.contracts.evidence")
    boundary = importlib.import_module("src.contracts.evidence.provenance_ledger")

    assert package.build_evidence_provenance_ledger is service.build_evidence_provenance_ledger
    assert boundary.build_evidence_provenance_ledger is service.build_evidence_provenance_ledger
    for path in (HELPER_PATH, CONTRACT_PATH):
        imports = _imports(path)
        assert all(
            not _matches_prefix(module_name, forbidden)
            for module_name in imports
            for forbidden in FORBIDDEN_IMPORT_PREFIXES
        )

    script = """
import sys
before = set(sys.modules)
import src.services.evidence_provenance_ledger
import src.contracts.evidence.provenance_ledger
after = set(sys.modules)
for forbidden in [
    "data_provider",
    "requests",
    "httpx",
    "openai",
    "src.core.pipeline",
    "src.services.market_cache",
    "src.services.options_lab_service",
    "src.services.portfolio_service",
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
