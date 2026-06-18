# -*- coding: utf-8 -*-
"""Tests for consumer confidence/evidence consistency projection."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from src.services.confidence_evidence_consistency import (
    CONFIDENCE_EVIDENCE_CONSISTENCY_VERSION,
    project_confidence_evidence_state,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/confidence_evidence_consistency.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "api",
    "apps",
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib",
    "yfinance",
    "src.services.market_cache",
    "src.services.stock_service",
    "src.services.market_overview_service",
    "src.services.options_market_data_provider",
)


def test_helper_is_pure_deterministic_and_inert() -> None:
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")

    assert not [name for name in imports if name.startswith(FORBIDDEN_IMPORT_PREFIXES)]

    first = project_confidence_evidence_state(
        raw_confidence_label="high",
        evidence_gaps=["Benchmark OHLCV is unavailable."],
    )
    second = project_confidence_evidence_state(
        raw_confidence_label="high",
        evidence_gaps=["Benchmark OHLCV is unavailable."],
    )

    assert first == second
    assert json.loads(json.dumps(first, ensure_ascii=False)) == first
    assert first["version"] == CONFIDENCE_EVIDENCE_CONSISTENCY_VERSION


def test_raw_high_confidence_with_blocked_thesis_caps_to_low_evidence_limited() -> None:
    projection = project_confidence_evidence_state(
        raw_confidence_label="high",
        raw_confidence_score=0.92,
        thesis_eligibility={"status": "blocked", "reasonCodes": ["missing_quote"]},
        missing_inputs=["Quote evidence is missing."],
    )

    assert projection["consumerConfidence"] == "low"
    assert projection["confidenceCap"] == {
        "value": 35,
        "label": "low",
        "reasons": ["research thesis blocked", "critical evidence missing"],
        "policyVersion": CONFIDENCE_EVIDENCE_CONSISTENCY_VERSION,
    }
    assert projection["confidenceState"] == {
        "status": "evidence limited",
        "label": "low",
        "reasons": ["research thesis blocked", "critical evidence missing"],
        "freshnessConstrained": False,
        "sourceQualityLimited": False,
        "thesisBlocked": True,
    }


def test_raw_high_confidence_with_benchmark_gap_is_capped_below_high() -> None:
    projection = project_confidence_evidence_state(
        raw_confidence_label="high",
        evidence_gaps=["Benchmark OHLCV is unavailable, so relative-strength evidence is neutral."],
    )

    assert projection["consumerConfidence"] == "medium"
    assert projection["confidenceCap"]["value"] == 60
    assert projection["confidenceCap"]["label"] == "medium"
    assert projection["confidenceCap"]["reasons"] == ["critical evidence missing"]
    assert projection["confidenceState"]["status"] == "evidence limited"


def test_medium_confidence_with_stale_inputs_marks_freshness_constrained() -> None:
    projection = project_confidence_evidence_state(
        raw_confidence_label="medium",
        stale_inputs=["Local daily OHLCV does not reach the newest peer date."],
    )

    assert projection["consumerConfidence"] == "medium"
    assert projection["confidenceCap"]["value"] == 70
    assert projection["confidenceCap"]["label"] == "medium"
    assert projection["confidenceCap"]["reasons"] == ["freshness constrained"]
    assert projection["confidenceState"]["status"] == "freshness constrained"
    assert projection["confidenceState"]["freshnessConstrained"] is True


def test_low_confidence_without_gaps_is_unchanged() -> None:
    projection = project_confidence_evidence_state(raw_confidence_label="low")

    assert projection["consumerConfidence"] == "low"
    assert projection["confidenceCap"] == {
        "value": 100,
        "label": "high",
        "reasons": [],
        "policyVersion": CONFIDENCE_EVIDENCE_CONSISTENCY_VERSION,
    }
    assert projection["confidenceState"]["status"] == "ready"


def test_nested_consumer_payload_projection_caps_high_confidence_by_evidence_gaps() -> None:
    payload = {
        "confidence": "high",
        "evidenceGaps": ["Peer evidence is missing."],
        "peerCorrelationSnapshot": {
            "missingInputs": ["No verified local peer group metadata is available for AAPL."],
            "staleInputs": [],
            "confidenceCap": "low",
        },
    }

    projection = project_confidence_evidence_state(payload=payload)

    assert projection["consumerConfidence"] == "medium"
    assert projection["confidenceState"]["status"] == "evidence limited"
    assert projection["confidenceCap"]["reasons"] == ["critical evidence missing"]
    assert "rawConfidence" not in projection["confidenceState"]
