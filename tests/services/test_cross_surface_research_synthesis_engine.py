# -*- coding: utf-8 -*-
"""Focused tests for the cross-surface research synthesis engine."""

from __future__ import annotations

import ast
import copy
import json
import re
from pathlib import Path
from typing import Any

from src.services.cross_surface_research_synthesis_engine import (
    CROSS_SURFACE_RESEARCH_SYNTHESIS_CONTRACT_VERSION,
    compose_cross_surface_research_synthesis,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE_PATH = REPO_ROOT / "src/services/cross_surface_research_synthesis_engine.py"

EXPECTED_TOP_LEVEL_KEYS = {
    "contractVersion",
    "subject",
    "synthesisState",
    "primaryEvidenceFamilies",
    "confirmingEvidence",
    "contradictingEvidence",
    "missingEvidence",
    "missingInputs",
    "staleEvidence",
    "provenanceSummary",
    "confidenceCap",
    "observationBoundary",
    "researchNextSteps",
    "surfaceContributions",
    "noAdviceDisclosure",
}

FORBIDDEN_ADVICE_TERMS = (
    "buy",
    "sell",
    "hold",
    "recommend",
    "target price",
    "stop loss",
    "take profit",
    "position sizing",
    "place order",
    "submit order",
    "trading advice",
    "investment advice",
    "买入",
    "卖出",
    "持有",
    "交易建议",
    "投资建议",
    "目标价",
    "止损",
    "止盈",
    "仓位",
)

FORBIDDEN_RAW_TERMS = (
    "provider",
    "runtime",
    "cache",
    "debug",
    "diagnostic",
    "raw",
    "requestid",
    "request id",
    "trace",
    "sourceref",
    "source ref",
    "reasoncode",
    "reason code",
    "marketcache",
    "schemaVersion",
    "http://",
    "https://",
    "/users/",
    "token",
    "secret",
    "sourceid",
    "sourcetype",
    "sourcetier",
    "providerauthority",
    "sourceauthorityallowed",
    "scorecontributionallowed",
)

FORBIDDEN_IMPORT_PREFIXES = (
    "api",
    "data_provider",
    "dotenv",
    "duckdb",
    "fastapi",
    "httpx",
    "openai",
    "redis",
    "requests",
    "server",
    "sqlalchemy",
    "src.config",
    "src.core",
    "src.repositories",
    "src.services.market_cache",
    "src.storage",
    "urllib",
    "urllib3",
)

INTERNAL_CODE_RE = re.compile(r"[a-z][a-z0-9]*_[a-z0-9_]+|[a-zA-Z]+:[a-zA-Z0-9_.-]+|=")


def _serialized(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _lower_serialized(payload: Any) -> str:
    return _serialized(payload).lower()


def _consumer_visible_strings(payload: dict[str, Any]) -> list[str]:
    fragments = {
        key: payload[key]
        for key in (
            "confirmingEvidence",
            "contradictingEvidence",
            "missingEvidence",
            "staleEvidence",
            "researchNextSteps",
            "surfaceContributions",
            "noAdviceDisclosure",
        )
        if key in payload
    }
    values: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, str):
            values.append(value)
            return
        if isinstance(value, dict):
            for nested in value.values():
                visit(nested)
            return
        if isinstance(value, (list, tuple)):
            for nested in value:
                visit(nested)

    visit(fragments)
    return values


def _assert_consumer_visible_strings_are_safe(payload: dict[str, Any]) -> None:
    serialized_values = json.dumps(_consumer_visible_strings(payload), ensure_ascii=False, sort_keys=True)
    assert INTERNAL_CODE_RE.search(serialized_values) is None
    lower = serialized_values.lower()
    for forbidden in (*FORBIDDEN_ADVICE_TERMS, *FORBIDDEN_RAW_TERMS):
        assert forbidden.lower() not in lower


def _complete_input_packet() -> dict[str, Any]:
    return {
        "subject": {"symbol": "AAPL", "label": "Apple research context"},
        "researchQueue": {
            "schemaVersion": "research_queue_v1",
            "researchQueue": [
                {
                    "sourceSurface": "scanner",
                    "symbol": "AAPL",
                    "evidenceUsed": ["quote", "fundamentals", "news"],
                    "evidenceGaps": [],
                    "freshness": {"state": "current"},
                    "observationOnly": True,
                }
            ],
        },
        "scannerResearchOverlay": {
            "overlayState": "ready",
            "primaryEvidence": ["price history", "fundamentals"],
            "missingEvidence": [],
        },
        "watchlistResearchOverlay": {
            "overlayState": "ready",
            "researchPriorityQueue": [
                {
                    "symbol": "AAPL",
                    "priorityReasonSafeLabel": "Watchlist research context is available.",
                    "missingEvidence": [],
                }
            ],
        },
        "portfolioExposureResearchContext": {
            "dominantExposure": {"type": "position", "symbol": "AAPL"},
            "staleInputs": [],
            "evidenceGaps": [],
            "researchNextSteps": ["Review exposure concentration with other research context."],
        },
        "symbolEvidenceReadiness": {
            "symbolEvidenceReadiness": True,
            "symbol": "AAPL",
            "readinessTier": "sufficient",
            "evidenceUsed": ["quote", "technical", "fundamental", "news"],
            "evidenceMissing": [],
            "staleInputs": [],
            "conflictingEvidence": [],
        },
        "peerCorrelationSnapshot": {
            "symbol": "AAPL",
            "correlationState": "aligned",
            "peerEvidence": [{"peerSymbol": "MSFT", "state": "aligned"}],
            "divergenceEvidence": [],
            "missingInputs": [],
            "staleInputs": [],
        },
        "symbolCompareEvidencePacket": {
            "comparedSymbols": ["MSFT", "AAPL"],
            "evidenceFamilies": ["relative strength", "correlation"],
            "missingEvidence": [],
            "staleInputs": [],
        },
        "themeCorrelationBreadthSnapshot": {
            "theme": {"id": "ai_applications", "label": "AI applications"},
            "correlationState": "broad_confirmation",
            "missingInputs": [],
            "staleInputs": [],
        },
        "marketRegimeSynthesis": {
            "primaryRegime": "risk_on_liquidity_expansion",
            "confidenceLabel": "elevated",
            "dataGaps": [],
            "staleInputs": [],
            "notInvestmentAdvice": True,
        },
        "evidenceProvenanceLedger": {
            "evidenceProvenanceLedger": [
                {
                    "sourceSurface": "research_packet",
                    "evidenceFamily": "market_data",
                    "freshnessBucket": "current",
                    "authorityBucket": "primary",
                    "consumerSafeSourceLabel": "Primary market data summary",
                    "usedFor": ["research_context"],
                    "limitation": "none",
                    "observationOnly": False,
                }
            ]
        },
    }


def test_complete_packet_with_multiple_evidence_families_becomes_complete_with_safe_labels() -> None:
    payload = compose_cross_surface_research_synthesis(_complete_input_packet())

    assert set(payload) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["contractVersion"] == CROSS_SURFACE_RESEARCH_SYNTHESIS_CONTRACT_VERSION
    assert payload["synthesisState"] == "complete"
    assert payload["subject"] == {"symbol": "AAPL", "label": "Apple research context"}
    assert payload["confidenceCap"]["label"] == "high"
    assert payload["confidenceCap"]["value"] == 85
    assert payload["missingInputs"] == []
    assert payload["staleEvidence"] == []
    assert payload["contradictingEvidence"] == []
    assert {
        "Market regime",
        "Research queue",
        "Scanner overlay",
        "Watchlist overlay",
        "Portfolio exposure",
        "Symbol readiness",
        "Peer correlation",
        "Symbol comparison",
        "Theme breadth",
        "Evidence provenance",
    }.issubset(set(payload["primaryEvidenceFamilies"]))
    assert payload["provenanceSummary"]["contributingSurfaceCount"] == 10
    provenance_text = _lower_serialized(payload["provenanceSummary"])
    for forbidden in (
        "sourceid",
        "sourcetype",
        "sourcetier",
        "providerauthority",
        "sourceauthorityallowed",
        "scorecontributionallowed",
        "debugref",
        "requestid",
        "sourceref",
        "reasoncodes",
    ):
        assert forbidden not in provenance_text
    assert payload["observationBoundary"] == {
        "observationOnly": True,
        "decisionGrade": False,
        "mutation": False,
        "externalCalls": False,
        "adviceBoundary": "no_advice",
        "message": payload["noAdviceDisclosure"],
    }
    serialized = _lower_serialized(payload)
    for forbidden in (*FORBIDDEN_ADVICE_TERMS, *FORBIDDEN_RAW_TERMS):
        assert forbidden.lower() not in serialized
    _assert_consumer_visible_strings_are_safe(payload)


def test_missing_inputs_fail_closed_to_insufficient_evidence() -> None:
    payload = compose_cross_surface_research_synthesis({})

    assert payload["synthesisState"] == "insufficient_evidence"
    assert payload["confirmingEvidence"] == []
    assert payload["contradictingEvidence"] == []
    assert payload["surfaceContributions"] == []
    assert payload["missingInputs"]
    assert payload["missingEvidence"]
    assert payload["confidenceCap"] == {
        "value": 20,
        "label": "low",
        "reasons": ["Insufficient cross-surface evidence."],
    }
    assert payload["provenanceSummary"]["failClosed"] is True


def test_contradictory_evidence_is_preserved_as_contradiction_not_advice() -> None:
    packet = _complete_input_packet()
    packet["peerCorrelationSnapshot"] = {
        "symbol": "AAPL",
        "correlationState": "diverging",
        "peerEvidence": [{"peerSymbol": "MSFT", "state": "diverging"}],
        "divergenceEvidence": [{"peerSymbol": "MSFT", "state": "diverging"}],
        "missingInputs": [],
        "staleInputs": [],
    }
    packet["symbolEvidenceReadiness"]["conflictingEvidence"] = ["technical"]

    payload = compose_cross_surface_research_synthesis(packet)

    assert payload["synthesisState"] == "insufficient_evidence"
    assert payload["contradictingEvidence"]
    assert payload["confidenceCap"]["value"] <= 35
    labels = [item["label"] for item in payload["contradictingEvidence"]]
    assert "Peer correlation contains divergence evidence for review." in labels
    serialized = _lower_serialized(payload)
    for forbidden in FORBIDDEN_ADVICE_TERMS:
        assert forbidden.lower() not in serialized
    _assert_consumer_visible_strings_are_safe(payload)


def test_stale_inputs_lower_confidence_and_move_to_stale_evidence() -> None:
    packet = _complete_input_packet()
    packet["marketRegimeSynthesis"]["freshness"] = "stale"
    packet["symbolEvidenceReadiness"]["staleInputs"] = ["quote", "news"]
    packet["themeCorrelationBreadthSnapshot"]["freshness"] = {"state": "delayed"}

    payload = compose_cross_surface_research_synthesis(packet)

    assert payload["synthesisState"] == "partial"
    assert payload["staleEvidence"]
    assert payload["confidenceCap"]["value"] == 55
    stale_surfaces = {item["surface"] for item in payload["staleEvidence"]}
    assert {"Market regime", "Symbol readiness", "Theme breadth"}.issubset(stale_surfaces)


def test_raw_diagnostics_and_adversarial_provider_data_are_dropped() -> None:
    packet = _complete_input_packet()
    packet["marketRegimeSynthesis"]["providerTrace"] = {
        "requestId": "req-123",
        "trace": "trace-abc",
        "sourceRef": "raw-provider-source",
        "rawJson": {"token": "secret"},
    }
    packet["scannerResearchOverlay"]["debug"] = {
        "reasonCode": "provider_runtime_timeout",
        "cacheKey": "/Users/me/MarketCache/raw.json",
    }
    packet["watchlistResearchOverlay"]["researchPriorityQueue"][0][
        "priorityReasonSafeLabel"
    ] = "buy now from https://provider.example.test/raw?token=secret"

    payload = compose_cross_surface_research_synthesis(packet)

    assert payload["synthesisState"] == "insufficient_evidence"
    assert payload["provenanceSummary"]["redactedInputCount"] >= 3
    serialized = _serialized(payload)
    lower = serialized.lower()
    for forbidden in (*FORBIDDEN_RAW_TERMS, *FORBIDDEN_ADVICE_TERMS):
        assert forbidden.lower() not in lower
    assert "req-123" not in serialized
    assert "trace-abc" not in serialized
    _assert_consumer_visible_strings_are_safe(payload)


def test_input_packet_is_not_mutated() -> None:
    packet = _complete_input_packet()
    original = copy.deepcopy(packet)

    compose_cross_surface_research_synthesis(packet)

    assert packet == original


def test_service_imports_stay_inert_and_avoid_provider_runtime_boundaries() -> None:
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    for module_name in imported_modules:
        for forbidden in FORBIDDEN_IMPORT_PREFIXES:
            assert module_name != forbidden
            assert not module_name.startswith(f"{forbidden}.")
