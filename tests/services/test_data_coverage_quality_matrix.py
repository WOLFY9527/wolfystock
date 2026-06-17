# -*- coding: utf-8 -*-
"""Contracts for the inert data coverage quality matrix service."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

from src.services.data_coverage_quality_matrix import (
    DATA_COVERAGE_QUALITY_MATRIX_CONTRACT_VERSION,
    build_data_coverage_quality_matrix,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE_PATH = REPO_ROOT / "src/services/data_coverage_quality_matrix.py"

FORBIDDEN_IMPORT_PREFIXES = (
    "api",
    "data_provider",
    "dotenv",
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
FORBIDDEN_OUTPUT_TERMS = (
    "provider",
    "debug",
    "runtime",
    "cache",
    "sourceref",
    "source_ref",
    "reasoncode",
    "reason_code",
    "requestid",
    "request_id",
    "trace",
    "raw",
    "must-not-emit",
)
FORBIDDEN_ADVICE_TERMS = (
    "buy",
    "sell",
    "hold",
    "recommend",
    "target price",
    "stop loss",
    "position sizing",
    "position-sizing",
    "买入",
    "卖出",
    "持有",
    "推荐",
    "目标价",
    "止损",
    "仓位建议",
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


def _complete_packet() -> dict[str, Any]:
    return {
        "subject": {"symbol": "AAPL", "market": "US"},
        "symbolEvidenceReadiness": {
            "symbol": "AAPL",
            "readinessTier": "sufficient",
            "evidenceUsed": ["quote", "technical", "fundamental", "news"],
            "evidenceMissing": [],
            "staleInputs": [],
            "conflictingEvidence": [],
        },
        "peerCorrelationSnapshot": {
            "correlationState": "aligned",
            "missingInputs": [],
            "staleInputs": [],
            "divergenceEvidence": [],
            "confidenceCap": "medium",
        },
        "symbolCompareEvidencePacket": {
            "comparedSymbols": ["AAPL", "MSFT"],
            "sharedEvidence": [{"kind": "daily_ohlcv", "status": "available"}],
            "divergentEvidence": [],
            "missingEvidenceBySymbol": {"AAPL": [], "MSFT": []},
            "confidenceCap": {"value": 100, "reasonCodes": []},
        },
        "themeCorrelationBreadthSnapshot": {
            "coverageState": "complete",
            "missingInputs": [],
            "staleInputs": [],
        },
        "marketRegimeSynthesis": {
            "coverageState": "complete",
            "missingInputs": [],
            "staleInputs": [],
            "confidenceCap": "high",
        },
        "scannerCandidateResearchPacket": {
            "readinessState": "ready",
            "missingEvidence": [],
            "staleInputs": [],
            "observationOnly": True,
        },
        "watchlistResearchPriorityQueue": {
            "queueState": "ready",
            "items": [{"symbol": "AAPL", "readinessState": "ready"}],
            "missingInputs": [],
            "staleInputs": [],
            "observationOnly": True,
        },
        "portfolioExposureResearchContext": {
            "coverageState": "complete",
            "missingInputs": [],
            "staleInputs": [],
            "observationOnly": True,
        },
        "evidenceProvenanceLedger": [
            {
                "evidenceFamily": "market_data",
                "freshnessBucket": "current",
                "limitation": "none",
                "observationOnly": False,
            },
            {
                "evidenceFamily": "fundamentals",
                "freshnessBucket": "current",
                "limitation": "none",
                "observationOnly": False,
            },
            {
                "evidenceFamily": "news",
                "freshnessBucket": "recent",
                "limitation": "none",
                "observationOnly": False,
            },
        ],
    }


def test_complete_multi_surface_packet_returns_complete_with_safe_labels() -> None:
    matrix = build_data_coverage_quality_matrix(_complete_packet())

    assert matrix["contractVersion"] == DATA_COVERAGE_QUALITY_MATRIX_CONTRACT_VERSION
    assert matrix["subject"] == {"symbol": "AAPL", "market": "US"}
    assert matrix["coverageState"] == "complete"
    assert set(matrix) == {
        "contractVersion",
        "subject",
        "coverageState",
        "coverageBySurface",
        "missingCriticalInputs",
        "staleInputs",
        "conflictingInputs",
        "evidenceFamiliesPresent",
        "evidenceFamiliesMissing",
        "confidenceCap",
        "observationBoundary",
        "researchNextSteps",
        "noAdviceDisclosure",
    }
    assert matrix["missingCriticalInputs"] == []
    assert matrix["staleInputs"] == []
    assert matrix["conflictingInputs"] == []
    assert matrix["confidenceCap"] == "medium"
    assert matrix["observationBoundary"] == {
        "observationOnly": True,
        "decisionGrade": False,
        "personalizedInstruction": False,
    }
    assert matrix["noAdviceDisclosure"] == (
        "Observation-only research coverage; not a personalized financial instruction."
    )
    assert matrix["coverageBySurface"]["symbol_evidence_readiness"]["coverageState"] == "complete"
    assert matrix["coverageBySurface"]["scanner_candidate_research"]["coverageState"] == "complete"

    serialized = json.dumps(matrix, ensure_ascii=False).lower()
    for forbidden in FORBIDDEN_OUTPUT_TERMS:
        assert forbidden not in serialized


def test_missing_critical_inputs_returns_insufficient_evidence() -> None:
    matrix = build_data_coverage_quality_matrix(
        {"peerCorrelationSnapshot": {"correlationState": "aligned"}}
    )

    assert matrix["coverageState"] == "insufficient_evidence"
    assert "symbolEvidenceReadiness" in matrix["missingCriticalInputs"]
    assert "evidenceProvenanceLedger" in matrix["missingCriticalInputs"]
    assert matrix["confidenceCap"] == "low"
    assert matrix["evidenceFamiliesPresent"] == ["peer_correlation"]
    assert "symbol_evidence" in matrix["evidenceFamiliesMissing"]
    assert matrix["researchNextSteps"]


def test_stale_inputs_are_represented_and_cap_confidence() -> None:
    packet = _complete_packet()
    packet["symbolEvidenceReadiness"]["staleInputs"] = ["quote"]
    packet["marketRegimeSynthesis"]["coverageState"] = "stale"
    packet["marketRegimeSynthesis"]["staleInputs"] = ["market breadth"]
    packet["evidenceProvenanceLedger"][0]["freshnessBucket"] = "stale"

    matrix = build_data_coverage_quality_matrix(packet)

    assert matrix["coverageState"] == "stale"
    assert matrix["confidenceCap"] == "low"
    assert {
        "surface": "symbol_evidence_readiness",
        "items": ["quote"],
    } in matrix["staleInputs"]
    assert {
        "surface": "market_regime_synthesis",
        "items": ["market breadth"],
    } in matrix["staleInputs"]
    assert matrix["coverageBySurface"]["evidence_provenance_ledger"]["coverageState"] == "stale"


def test_contradictory_inputs_are_represented_without_advice_language() -> None:
    packet = _complete_packet()
    packet["symbolEvidenceReadiness"]["conflictingEvidence"] = ["technical", "news"]
    packet["peerCorrelationSnapshot"]["correlationState"] = "diverging"
    packet["symbolCompareEvidencePacket"]["divergentEvidence"] = [
        {"kind": "structure_state", "symbols": ["AAPL", "MSFT"]}
    ]

    matrix = build_data_coverage_quality_matrix(packet)

    assert matrix["coverageState"] == "partial"
    assert {
        "surface": "symbol_evidence_readiness",
        "items": ["technical", "news"],
    } in matrix["conflictingInputs"]
    assert {
        "surface": "peer_correlation",
        "items": ["peer movement divergence"],
    } in matrix["conflictingInputs"]
    assert {
        "surface": "symbol_compare_evidence",
        "items": ["cross-symbol divergence"],
    } in matrix["conflictingInputs"]
    serialized = json.dumps(matrix, ensure_ascii=False).lower()
    for forbidden in FORBIDDEN_ADVICE_TERMS:
        assert forbidden not in serialized


def test_raw_diagnostics_and_adversarial_values_are_dropped() -> None:
    packet = _complete_packet()
    packet["symbolEvidenceReadiness"]["providerDiagnostics"] = {
        "requestId": "must-not-emit",
        "trace": "must-not-emit",
        "rawPayload": {"debug": "must-not-emit"},
    }
    packet["peerCorrelationSnapshot"]["sourceRef"] = "must-not-emit"
    packet["symbolCompareEvidencePacket"]["reasonCode"] = "must-not-emit"
    packet["marketRegimeSynthesis"]["cacheDebug"] = "must-not-emit buy now"
    packet["scannerCandidateResearchPacket"]["providerRuntime"] = "must-not-emit"

    matrix = build_data_coverage_quality_matrix(packet)

    assert matrix["coverageState"] in {"partial", "stale"}
    serialized = json.dumps(matrix, ensure_ascii=False).lower()
    for forbidden in (*FORBIDDEN_OUTPUT_TERMS, *FORBIDDEN_ADVICE_TERMS):
        assert forbidden not in serialized


def test_input_packet_is_not_mutated() -> None:
    packet = _complete_packet()
    before = copy.deepcopy(packet)

    build_data_coverage_quality_matrix(packet)

    assert packet == before


def test_serialized_output_contains_no_advice_vocabulary() -> None:
    packet = _complete_packet()
    packet["symbolEvidenceReadiness"]["conflictingEvidence"] = ["news"]
    packet["symbolCompareEvidencePacket"]["divergentEvidence"] = [
        {"kind": "confidence", "symbols": ["AAPL", "MSFT"], "values": {"AAPL": "high", "MSFT": "low"}}
    ]

    serialized = json.dumps(build_data_coverage_quality_matrix(packet), ensure_ascii=False).lower()

    for forbidden in FORBIDDEN_ADVICE_TERMS:
        assert forbidden not in serialized


def test_service_imports_stay_inert() -> None:
    imports = _imports(SERVICE_PATH)

    assert all(
        not _matches_prefix(module_name, forbidden)
        for module_name in imports
        for forbidden in FORBIDDEN_IMPORT_PREFIXES
    )
