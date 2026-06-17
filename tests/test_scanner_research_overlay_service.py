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
from tests.helpers.packet_redaction_fuzzer import (
    assert_packet_output_redacted,
    redaction_fuzzer_strings,
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
FORBIDDEN_INTERNAL_TOKENS = (
    "candidateevidenceframe",
    "candidateresearchreadiness",
    "candidateresearchsummaryframe",
    "insufficient_candidate_evidence",
    "delayed_evidence",
    "stale_evidence",
    "fallback_evidence",
    "evidence_gaps_present",
    "scannercandidates",
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
            missing_evidence=["fundamentals", "candidateResearchReadiness"],
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
    assert payload["overlayState"] == "degraded"
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert set(payload["themeLeadershipPacket"]) == {
        "theme",
        "leadershipState",
        "leadingSymbols",
        "laggingSymbols",
        "breadthEvidence",
        "concentrationEvidence",
        "evidenceGaps",
        "freshness",
        "suggestedResearchPath",
        "observationOnly",
    }
    assert payload["themeLeadershipPacket"]["observationOnly"] is True
    assert payload["themeLeadershipPacket"]["theme"] == "AI Infrastructure"
    assert payload["researchSummary"]
    assert payload["riskObservations"]
    assert payload["evidenceGaps"] == [
        "Fundamental evidence is missing.",
        "Research readiness evidence is missing.",
    ]
    assert [item["ticker"] for item in payload["items"]] == ["ALFA", "BETA"]
    assert [item["originalScannerCandidateState"]["rank"] for item in payload["items"]] == [1, 2]
    assert [item["originalScannerCandidateState"]["score"] for item in payload["items"]] == [82.0, 74.0]
    assert payload["items"][0]["overlayState"] == "available"
    assert payload["items"][0]["researchSummary"]
    assert payload["items"][0]["drilldownTargets"] == [
        {
            "label": "Stock Structure",
            "route": "/stocks/ALFA/structure-decision",
            "section": "scannerOverlay",
            "reason": "Open ticker-specific structure context for follow-up research.",
        }
    ]
    assert payload["items"][0]["researchPriority"] == "high"
    assert payload["items"][0]["regimeFit"]["state"] == "aligned"
    assert payload["items"][0]["themeAlignment"]["themes"] == ["AI Infrastructure"]
    assert payload["items"][0]["whyThisMattersToday"]
    assert payload["items"][0]["whatToVerify"]
    assert payload["items"][1]["overlayState"] == "degraded"
    assert payload["items"][1]["evidenceGaps"] == [
        "Fundamental evidence is missing.",
        "Research readiness evidence is missing.",
    ]
    assert any("新鲜度" in item for item in payload["items"][1]["riskObservations"])
    assert payload["items"][1]["drilldownTargets"] == [
        {
            "label": "Stock Structure",
            "route": "/stocks/BETA/structure-decision",
            "section": "scannerOverlay",
            "reason": "Open ticker-specific structure context for follow-up research.",
        }
    ]
    assert payload["aggregateSummary"]["candidateCount"] == 2
    assert payload["aggregateSummary"]["priorityCounts"]["high"] == 1
    assert payload["queueDiversity"]["themeCount"] == 2
    assert payload["dataQuality"]["status"] == "partial"
    assert payload["missingEvidence"] == [
        "Fundamental evidence is missing.",
        "Research readiness evidence is missing.",
    ]
    assert payload["drilldownTargets"][0]["route"] == "/stocks/ALFA/structure-decision"

    leaked = [term for term in FORBIDDEN_PUBLIC_TERMS if term in _serialized_values(payload)]
    assert leaked == []
    internal_leaks = [term for term in FORBIDDEN_INTERNAL_TOKENS if term in _serialized_values(payload)]
    assert internal_leaks == []


def test_build_overlay_theme_leadership_packet_identifies_broadening_theme_universe() -> None:
    candidates = [
        _candidate(symbol="ALFA", rank=1, score=84.0, boards=["AI Infrastructure"]),
        _candidate(symbol="BETA", rank=2, score=81.0, boards=["AI Infrastructure"]),
        _candidate(symbol="GAMMA", rank=3, score=78.0, boards=["AI Infrastructure"]),
        _candidate(symbol="DELTA", rank=4, score=75.0, boards=["AI Infrastructure"]),
    ]
    original = copy.deepcopy(candidates)

    payload = ScannerResearchOverlayService(now=_fixed_now).build_overlay(
        run={
            "id": 46,
            "market": "us",
            "profile": "us_preopen_v1",
            "scannerContextFrame": {
                "themeFrame": {
                    "state": "supportive",
                    "freshness": "cached",
                    "themes": [{"label": "AI Infrastructure", "state": "broadening"}],
                },
                "universePolicy": {
                    "type": "theme",
                    "label": "AI Infrastructure",
                    "themeId": "ai_infrastructure",
                },
            },
        },
        candidates=candidates,
    )

    assert candidates == original
    packet = payload["themeLeadershipPacket"]
    assert packet["theme"] == "AI Infrastructure"
    assert packet["leadershipState"] == "broadening"
    assert packet["leadingSymbols"] == ["ALFA", "BETA", "GAMMA"]
    assert packet["laggingSymbols"] == ["DELTA"]
    assert packet["breadthEvidence"]["themeCandidateCount"] == 4
    assert packet["breadthEvidence"]["participationPercent"] == 100.0
    assert packet["concentrationEvidence"]["topSymbolScoreSharePercent"] < 30
    assert packet["freshness"] == "cached"
    assert packet["observationOnly"] is True
    assert packet["suggestedResearchPath"]
    assert "ai_infrastructure" not in _serialized_values(packet)


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

    assert payload["overlayState"] == "degraded"
    assert payload["items"][0]["overlayState"] == "degraded"
    assert payload["items"][0]["researchPriority"] == "insufficient_evidence"
    assert payload["items"][0]["researchSummary"] == "Core scanner evidence is unavailable, so this candidate stays in evidence review only."
    assert payload["items"][0]["regimeFit"]["state"] == "insufficient_evidence"
    assert payload["items"][0]["themeAlignment"]["state"] == "insufficient_evidence"
    assert payload["items"][0]["evidenceQuality"]["status"] == "insufficient"
    assert payload["items"][0]["whyThisMattersToday"] == []
    assert payload["items"][0]["whatToVerify"]
    assert payload["items"][0]["riskFlags"] == ["Evidence coverage is too thin for a stronger research read."]
    assert payload["items"][0]["riskObservations"] == ["Evidence coverage is too thin for a stronger research read."]
    assert payload["dataQuality"]["status"] == "degraded"
    assert "Core scanner evidence is unavailable." in payload["missingEvidence"]
    assert payload["items"][0]["evidenceGaps"] == ["Core scanner evidence is unavailable."]
    assert payload["themeLeadershipPacket"]["leadershipState"] == "insufficient_evidence"
    assert payload["themeLeadershipPacket"]["observationOnly"] is True


def test_build_overlay_empty_input_returns_degraded_read_only_payload() -> None:
    payload = ScannerResearchOverlayService(now=_fixed_now).build_overlay(
        run={"id": 44, "market": "hk", "profile": "hk_momentum_v1"},
        candidates=[],
    )

    assert payload["items"] == []
    assert payload["overlayState"] == "unavailable"
    assert payload["aggregateSummary"]["candidateCount"] == 0
    assert payload["dataQuality"]["status"] == "degraded"
    assert payload["missingEvidence"] == ["Scanner candidates are unavailable for this overlay."]
    assert payload["evidenceGaps"] == ["Scanner candidates are unavailable for this overlay."]
    assert payload["drilldownTargets"] == []
    assert payload["queueDiversity"]["status"] == "unavailable"
    assert payload["themeLeadershipPacket"]["leadershipState"] == "insufficient_evidence"
    assert payload["themeLeadershipPacket"]["leadingSymbols"] == []
    assert payload["themeLeadershipPacket"]["laggingSymbols"] == []


def test_build_overlay_filters_unsafe_consumer_copy_from_summary_and_checks() -> None:
    candidate = _candidate(symbol="GAMMA", rank=3, score=79.0)
    fuzzer_text = " ".join(redaction_fuzzer_strings())
    candidate["reason_summary"] = f"Buy after breakout once the setup confirms. {fuzzer_text}"
    candidate["candidateResearchSummaryFrame"]["primaryResearchReason"] = (
        f"Set a target after scanner confirmation. {fuzzer_text}"
    )
    candidate["watch_context"] = [f"Use a stop loss if the move fails. {fuzzer_text}"]
    candidate["risk_notes"] = [f"Position sizing should wait for more evidence. {fuzzer_text}"]

    payload = ScannerResearchOverlayService(now=_fixed_now).build_overlay(
        run={"id": 45, "market": "us", "profile": "us_preopen_v1"},
        candidates=[candidate],
    )

    consumer_blob = _serialized(
        {
            "researchSummary": payload["researchSummary"],
            "itemResearchSummary": payload["items"][0]["researchSummary"],
            "whyThisMattersToday": payload["items"][0]["whyThisMattersToday"],
            "whatToVerify": payload["items"][0]["whatToVerify"],
            "riskObservations": payload["items"][0]["riskObservations"],
            "consumerIssues": payload["consumerIssues"],
        }
    )
    leaked = [term for term in FORBIDDEN_PUBLIC_TERMS if term in consumer_blob]
    assert leaked == []
    assert_packet_output_redacted(
        {
            "researchSummary": payload["researchSummary"],
            "itemResearchSummary": payload["items"][0]["researchSummary"],
            "whyThisMattersToday": payload["items"][0]["whyThisMattersToday"],
            "whatToVerify": payload["items"][0]["whatToVerify"],
            "riskObservations": payload["items"][0]["riskObservations"],
            "consumerIssues": payload["consumerIssues"],
        },
        surface="scanner_research_overlay.consumer_visible",
    )


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
