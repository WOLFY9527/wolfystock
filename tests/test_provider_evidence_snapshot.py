# -*- coding: utf-8 -*-
"""Tests for the inert provider evidence snapshot helper."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

from src.services.provider_evidence_snapshot import build_provider_evidence_snapshot


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = REPO_ROOT / "src/services/provider_evidence_snapshot.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "yfinance",
    "src.services.market_cache",
    "src.services.data_source_router",
)
FORBIDDEN_TOP_LEVEL_FIELDS = {
    "providerOrder",
    "providerRouting",
    "providerBudget",
    "routeRequest",
    "routeDecision",
    "routingChanged",
}


def _helper_imports() -> set[str]:
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _sample_indicator_evidence() -> list[dict[str, Any]]:
    return [
        {
            "key": "official_panel",
            "label": "Official Panel",
            "status": "live",
            "freshness": "cached",
            "asOf": "2026-05-30T09:30:00+08:00",
            "source": "fred",
            "sourceLabel": "FRED",
            "inputs": [
                {
                    "key": "VIX",
                    "label": "VIX",
                    "source": "fred",
                    "sourceLabel": "FRED",
                    "sourceType": "official_public",
                    "freshness": "cached",
                    "asOf": "2026-05-30T09:30:00+08:00",
                    "confidenceWeight": 1.0,
                    "coverage": 1.0,
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": False,
                    "isUnavailable": False,
                }
            ],
            "missingInputs": [],
            "warnings": [],
        },
        {
            "key": "degraded_panel",
            "label": "Degraded Panel",
            "status": "partial",
            "freshness": "partial",
            "asOf": "2026-05-30T08:00:00+08:00",
            "source": "yfinance_proxy",
            "sourceLabel": "Yahoo Finance",
            "proxyOnly": True,
            "inputs": [
                {
                    "key": "USD_TWI",
                    "label": "USD",
                    "source": "yfinance_proxy",
                    "sourceLabel": "Yahoo Finance",
                    "sourceType": "unofficial_proxy",
                    "freshness": "stale",
                    "asOf": "2026-05-30T08:00:00+08:00",
                    "confidenceWeight": 0.7,
                    "coverage": 1.0,
                    "isFallback": False,
                    "isStale": True,
                    "isPartial": False,
                    "isUnavailable": False,
                },
                {
                    "key": "FLOW",
                    "label": "Flow",
                    "source": "fallback",
                    "sourceLabel": "Fallback",
                    "sourceType": "fallback_static",
                    "freshness": "fallback",
                    "asOf": "2026-05-30T07:30:00+08:00",
                    "confidenceWeight": 0.9,
                    "coverage": 0.2,
                    "isFallback": True,
                    "isStale": False,
                    "isPartial": False,
                    "isUnavailable": False,
                },
                {
                    "key": "SYN",
                    "label": "Synthetic",
                    "source": "fixture",
                    "sourceLabel": "Fixture",
                    "sourceType": "synthetic_fixture",
                    "freshness": "synthetic",
                    "asOf": "2026-05-30T07:00:00+08:00",
                    "confidenceWeight": 0.8,
                    "coverage": 0.5,
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": False,
                    "isUnavailable": False,
                },
                {
                    "key": "MISS",
                    "label": "Missing",
                    "source": "unavailable",
                    "sourceLabel": "Unavailable",
                    "sourceType": "missing",
                    "freshness": "unavailable",
                    "asOf": None,
                    "confidenceWeight": 0.6,
                    "coverage": 0.0,
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": False,
                    "isUnavailable": True,
                },
            ],
            "missingInputs": ["USD_TWI", "FLOW"],
            "warnings": ["partial_coverage", "fallback_source"],
        },
    ]


def test_provider_evidence_snapshot_helper_is_pure_deterministic_and_inert() -> None:
    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    evidence = _sample_indicator_evidence()
    original = copy.deepcopy(evidence)

    first = build_provider_evidence_snapshot(evidence)
    second = build_provider_evidence_snapshot(evidence)

    assert evidence == original
    assert first == second
    assert json.loads(json.dumps(first, ensure_ascii=False)) == first


def test_provider_evidence_snapshot_helper_summarizes_degraded_posture_without_authority_or_routing() -> None:
    snapshot = build_provider_evidence_snapshot(_sample_indicator_evidence())

    assert snapshot["diagnosticOnly"] is True
    assert snapshot["observationOnly"] is True
    assert snapshot["authorityGrant"] is False
    assert snapshot["decisionGrade"] is False
    assert FORBIDDEN_TOP_LEVEL_FIELDS.isdisjoint(snapshot)

    assert snapshot["source"] == "mixed"
    assert snapshot["freshness"] == "unavailable"
    assert snapshot["isFallback"] is True
    assert snapshot["isStale"] is True
    assert snapshot["isPartial"] is True
    assert snapshot["isSynthetic"] is True
    assert snapshot["isUnavailable"] is True
    assert snapshot["fallbackInputCount"] == 1
    assert snapshot["staleInputCount"] == 1
    assert snapshot["partialInputCount"] == 1
    assert snapshot["syntheticInputCount"] == 1
    assert snapshot["unavailableInputCount"] == 1
    assert snapshot["missingInputCount"] == 2

    source_confidence = snapshot["sourceConfidence"]
    assert source_confidence["trustLevel"] == "unavailable"
    assert source_confidence["scoreCap"] == 0.0
    assert source_confidence["freshness"] == "unavailable"
    assert "fallback_source" in source_confidence["degradationReasons"]
    assert "stale_source" in source_confidence["degradationReasons"]
    assert "partial_coverage" in source_confidence["degradationReasons"]
    assert "synthetic_source" in source_confidence["degradationReasons"]
    assert "unavailable_source" in source_confidence["degradationReasons"]
    assert snapshot["capReason"] == "unavailable_source"


def test_provider_evidence_snapshot_helper_returns_safe_unavailable_summary_for_missing_evidence() -> None:
    snapshot = build_provider_evidence_snapshot([])

    assert snapshot == {
        "diagnosticOnly": True,
        "observationOnly": True,
        "authorityGrant": False,
        "decisionGrade": False,
        "externalProviderCalls": False,
        "providerRuntimeChanged": False,
        "marketCacheMutation": False,
        "indicatorCount": 0,
        "proxyInputCount": 0,
        "fallbackInputCount": 0,
        "staleInputCount": 0,
        "partialInputCount": 0,
        "syntheticInputCount": 0,
        "unavailableInputCount": 0,
        "missingInputCount": 0,
        "source": "unavailable",
        "sourceLabel": "未接入",
        "asOf": None,
        "freshness": "unavailable",
        "isFallback": False,
        "isStale": False,
        "isPartial": False,
        "isSynthetic": False,
        "isUnavailable": True,
        "coverage": 0.0,
        "confidenceWeight": 0.0,
        "degradationReason": "unavailable_source",
        "capReason": "unavailable_source",
        "indicatorEvidence": [],
        "missingInputs": [],
        "warnings": [],
        "sourceConfidence": {
            "isReliable": False,
            "trustLevel": "unavailable",
            "coverage": 0.0,
            "sourceTier": "unavailable",
            "freshness": "unavailable",
            "degradationReasons": ["unavailable_source", "no_coverage"],
            "scoreCap": 0.0,
            "conclusionAllowed": False,
            "warning": "Market intelligence data is unavailable; strong conclusions are blocked.",
        },
    }
