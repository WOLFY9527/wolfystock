# -*- coding: utf-8 -*-
"""Contract tests for the scanner research overlay service."""

from __future__ import annotations

import ast
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.scanner_research_overlay_service import (
    SCANNER_RESEARCH_OVERLAY_SCHEMA_VERSION,
    SCANNER_RESEARCH_OVERLAY_NO_ADVICE_DISCLOSURE,
    ScannerResearchOverlayService,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
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
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "src.providers",
    "src.services.market_scanner_service",
    "src.services.watchlist_service",
    "src.repositories",
    "src.storage",
)


def _fixed_now() -> datetime:
    return datetime(2026, 6, 15, 9, 30, tzinfo=timezone.utc)


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def _candidate(
    *,
    symbol: str,
    rank: int,
    score: float,
    boards: list[str] | None = None,
    missing_evidence: list[str] | None = None,
    freshness: str = "fresh",
    evidence_state: str = "available",
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "name": f"{symbol} Corp",
        "rank": rank,
        "score": score,
        "raw_score": score + 1,
        "final_score": score,
        "reason_summary": "Trend and liquidity evidence support research review.",
        "reasons": ["relative strength", "volume expansion"],
        "key_metrics": [{"label": "Relative strength", "value": "strong"}],
        "feature_signals": [{"label": "Trend", "value": "confirmed"}],
        "risk_notes": ["Evidence requires confirmation."],
        "watch_context": ["Verify evidence persistence."],
        "boards": boards or ["AI Infrastructure"],
        "consumerDiagnostics": {
            "status": "available",
            "dataQualityState": "ready",
            "freshnessState": freshness,
            "missingEvidence": missing_evidence or [],
        },
        "candidateEvidenceFrame": {
            "coverageState": evidence_state,
            "coverage": {
                "availableCount": 6,
                "partialCount": 1,
                "missingCount": len(missing_evidence or []),
                "totalCount": 8,
            },
            "domains": {
                "technicals": {"state": "available"},
                "liquidity": {"state": "available"},
                "trend": {"state": "available"},
                "theme": {"state": "available"},
                "fundamentals": {"state": "missing" if missing_evidence else "partial"},
            },
        },
        "candidateResearchReadiness": {
            "readinessState": "ready" if not missing_evidence else "insufficient",
            "missingEvidence": missing_evidence or [],
            "sourceAuthority": "scoreGradeAllowed",
            "freshnessFloor": freshness,
            "nextEvidenceNeeded": ["Confirm evidence persistence."],
            "consumerActionBoundary": "no_advice",
        },
        "candidateResearchSummaryFrame": {
            "frameState": "ready" if not missing_evidence else "insufficient",
            "scoreBand": "high" if score >= 75 else "medium",
            "primaryResearchReason": "Evidence explains why this scanner candidate merits research today.",
            "evidenceHighlights": ["Technicals available", "Liquidity available"],
            "missingEvidence": missing_evidence or [],
            "nextResearchStep": "Confirm evidence persistence.",
            "noAdviceBoundary": True,
        },
    }


def test_build_overlay_preserves_candidate_order_and_projects_required_contract() -> None:
    candidates = [
        _candidate(symbol="ALFA", rank=1, score=82.0, boards=["AI Infrastructure"]),
        _candidate(
            symbol="BETA",
            rank=2,
            score=74.0,
            boards=["Robotics"],
            missing_evidence=["fundamentals"],
            freshness="delayed",
        ),
    ]
    original = copy.deepcopy(candidates)

    payload = ScannerResearchOverlayService(now=_fixed_now).build_overlay(
        run={
            "id": 42,
            "market": "us",
            "profile": "us_preopen_v1",
            "scannerContextFrame": {
                "marketReadiness": {"readinessState": "ready"},
                "macroRegime": {"state": "risk_on"},
                "themeFrame": {"state": "available"},
            },
            "summary": {"selected_count": 2},
        },
        candidates=candidates,
    )

    assert candidates == original
    assert payload["schemaVersion"] == SCANNER_RESEARCH_OVERLAY_SCHEMA_VERSION
    assert payload["generatedAt"] == "2026-06-15T09:30:00+00:00"
    assert payload["runId"] == 42
    assert payload["market"] == "us"
    assert payload["profile"] == "us_preopen_v1"
    assert payload["noAdviceDisclosure"] == SCANNER_RESEARCH_OVERLAY_NO_ADVICE_DISCLOSURE
    assert [item["ticker"] for item in payload["items"]] == ["ALFA", "BETA"]
    assert [item["originalScannerCandidateState"]["rank"] for item in payload["items"]] == [1, 2]
    assert payload["items"][0]["researchPriority"] == "high"
    assert payload["items"][0]["regimeFit"]["state"] == "aligned"
    assert payload["items"][0]["themeAlignment"]["themes"] == ["AI Infrastructure"]
    assert payload["items"][0]["whyThisMattersToday"]
    assert payload["items"][0]["whatToVerify"]
    assert payload["items"][1]["evidenceGaps"] == ["fundamentals"]
    assert payload["aggregateSummary"]["candidateCount"] == 2
    assert payload["aggregateSummary"]["priorityCounts"]["high"] == 1
    assert payload["queueDiversity"]["themeCount"] == 2
    assert payload["dataQuality"]["status"] == "partial"
    assert payload["missingEvidence"] == ["fundamentals"]

    leaked = [term for term in FORBIDDEN_PUBLIC_TERMS if term in _serialized(payload)]
    assert leaked == []


def test_build_overlay_fails_closed_when_candidate_evidence_is_insufficient() -> None:
    payload = ScannerResearchOverlayService(now=_fixed_now).build_overlay(
        run={"id": 43, "market": "us", "profile": "us_preopen_v1"},
        candidates=[
            {
                "symbol": "THIN",
                "name": "Thin Corp",
                "rank": 1,
                "score": 91.0,
                "raw_score": 92.0,
                "final_score": 91.0,
            }
        ],
    )

    assert payload["items"][0]["researchPriority"] == "insufficient_evidence"
    assert payload["items"][0]["regimeFit"]["state"] == "insufficient_evidence"
    assert payload["items"][0]["themeAlignment"]["state"] == "insufficient_evidence"
    assert payload["items"][0]["evidenceQuality"]["status"] == "insufficient"
    assert payload["items"][0]["whyThisMattersToday"] == []
    assert payload["items"][0]["whatToVerify"]
    assert payload["items"][0]["riskFlags"] == ["insufficient_candidate_evidence"]
    assert payload["dataQuality"]["status"] == "degraded"
    assert "candidateEvidenceFrame" in payload["missingEvidence"]


def test_build_overlay_empty_input_returns_degraded_read_only_payload() -> None:
    payload = ScannerResearchOverlayService(now=_fixed_now).build_overlay(
        run={"id": 44, "market": "hk", "profile": "hk_momentum_v1"},
        candidates=[],
    )

    assert payload["items"] == []
    assert payload["aggregateSummary"]["candidateCount"] == 0
    assert payload["dataQuality"]["status"] == "degraded"
    assert payload["missingEvidence"] == ["scannerCandidates"]
    assert payload["queueDiversity"]["status"] == "unavailable"


def test_scanner_research_overlay_service_has_no_runtime_or_persistence_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "scanner_research_overlay_service.py"
    tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
            continue
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported_modules.add(node.module)
            imported_modules.update(f"{node.module}.{alias.name}" for alias in node.names if alias.name != "*")

    violations = sorted(
        module
        for module in imported_modules
        if any(module == prefix or module.startswith(f"{prefix}.") for prefix in FORBIDDEN_IMPORT_PREFIXES)
    )
    assert violations == []
