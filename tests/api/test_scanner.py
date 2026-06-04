# -*- coding: utf-8 -*-
"""Scanner API schema coverage for backward-compatible diagnostics."""

from api.v1.schemas.scanner import ScannerRunDetailResponse
from src.core.scanner_theme_registry import get_scanner_theme


def test_crypto_mining_theme_registry_has_11_symbols() -> None:
    theme = get_scanner_theme("crypto_miners")

    assert theme is not None
    assert theme.label_zh == "加密矿企"
    assert list(theme.symbols) == ["MARA", "RIOT", "CLSK", "IREN", "CIFR", "HUT", "BTDR", "WULF", "CORZ", "BITF", "HIVE"]


def test_scanner_run_response_accepts_legacy_shortlist_without_diagnostics() -> None:
    response = ScannerRunDetailResponse(
        id=1,
        market="us",
        profile="us_preopen_v1",
        status="completed",
        universe_name="us_liquid",
        shortlist_size=0,
        universe_size=0,
        preselected_size=0,
        evaluated_size=0,
    )

    assert response.shortlist == []
    assert response.selected == []
    assert response.candidates == []
    assert response.scannerContextFrame == {}
    assert response.summary.universe_count == 0


def test_scanner_run_response_accepts_additive_cn_blocked_scanner_context_frame() -> None:
    response = ScannerRunDetailResponse(
        id=2,
        market="cn",
        profile="cn_preopen_v1",
        status="failed",
        universe_name="cn_liquid",
        shortlist_size=0,
        universe_size=0,
        preselected_size=0,
        evaluated_size=0,
        scannerContextFrame={
            "marketReadiness": {
                "contractVersion": "research_readiness_v1",
                "researchReady": False,
                "market": "cn",
                "universeType": "default",
                "readinessState": "blocked",
                "blockingReasons": ["universe_source_unavailable"],
                "missingEvidence": ["technical", "freshness"],
                "providerAuthority": "unavailable",
                "freshness": "unavailable",
                "sourceTier": "unavailable",
                "nextEvidenceNeeded": ["补充技术面证据"],
                "noAdviceBoundary": True,
            },
            "universePolicy": {
                "type": "default",
                "label": "Profile default universe",
                "reason": "scanner_profile_default_universe",
            },
            "noAdviceBoundary": True,
        },
    )

    assert response.status == "failed"
    assert response.scannerContextFrame["marketReadiness"]["readinessState"] == "blocked"
    assert response.scannerContextFrame["marketReadiness"]["providerAuthority"] == "unavailable"
    assert response.scannerContextFrame["universePolicy"]["type"] == "default"


def test_scanner_run_response_accepts_additive_candidate_evidence_and_readiness_fields() -> None:
    response = ScannerRunDetailResponse(
        id=3,
        market="us",
        profile="us_preopen_v1",
        status="completed",
        universe_name="us_liquid",
        shortlist_size=1,
        universe_size=3,
        preselected_size=3,
        evaluated_size=3,
        shortlist=[
            {
                "symbol": "NVDA",
                "name": "NVIDIA",
                "rank": 1,
                "score": 82.0,
                "raw_score": 87.0,
                "final_score": 82.0,
                "candidateEvidenceFrame": {
                    "contractVersion": "scanner_candidate_evidence_v1",
                    "coverageState": "partial",
                    "domains": {
                        "technicals": {"state": "available"},
                        "fundamentals": {"state": "missing"},
                        "newsCatalyst": {"state": "missing"},
                    },
                },
                "candidateResearchReadiness": {
                    "contractVersion": "research_readiness_v1",
                    "researchReady": False,
                    "readinessState": "insufficient",
                    "missingEvidence": ["fundamentals", "news", "catalyst"],
                    "blockingReasons": ["missing_required_evidence"],
                    "evidenceCoverage": {
                        "scoreGradeCount": 1,
                        "observationOnlyCount": 0,
                        "missingCount": 3,
                        "totalCount": 4,
                    },
                    "sourceAuthority": "scoreGradeAllowed",
                    "freshnessFloor": "delayed",
                    "consumerActionBoundary": "no_advice",
                    "nextEvidenceNeeded": ["补充基本面证据"],
                    "debugRef": "scanner:candidate:NVDA",
                },
                "candidateResearchSummaryFrame": {
                    "contractVersion": "scanner_candidate_research_summary_v1",
                    "frameState": "insufficient",
                    "symbol": "NVDA",
                    "rank": 1,
                    "scoreBand": "medium",
                    "primaryResearchReason": "趋势与量能支持继续研究。",
                    "evidenceHighlights": ["Technicals available", "Liquidity available"],
                    "missingEvidence": ["fundamentals", "news", "catalyst"],
                    "blockingReasons": ["missing_required_evidence"],
                    "topDownContextRefs": [
                        {"key": "marketReadiness", "state": "ready", "label": "Top-down market context available"}
                    ],
                    "sourceAuthority": "scoreGradeAllowed",
                    "freshness": "delayed",
                    "nextResearchStep": "补充基本面证据",
                    "noAdviceBoundary": True,
                    "debugRef": "scanner:candidate_summary:NVDA",
                },
            }
        ],
        selected=[
            {
                "symbol": "NVDA",
                "name": "NVIDIA",
                "rank": 1,
                "score": 82.0,
                "raw_score": 87.0,
                "final_score": 82.0,
                "candidateEvidenceFrame": {
                    "contractVersion": "scanner_candidate_evidence_v1",
                    "coverageState": "partial",
                },
                "candidateResearchReadiness": {
                    "contractVersion": "research_readiness_v1",
                    "readinessState": "insufficient",
                },
                "candidateResearchSummaryFrame": {
                    "contractVersion": "scanner_candidate_research_summary_v1",
                    "frameState": "insufficient",
                    "symbol": "NVDA",
                    "rank": 1,
                    "scoreBand": "medium",
                    "primaryResearchReason": "趋势与量能支持继续研究。",
                    "evidenceHighlights": ["Technicals available", "Liquidity available"],
                    "missingEvidence": ["fundamentals", "news", "catalyst"],
                    "blockingReasons": ["missing_required_evidence"],
                    "topDownContextRefs": [
                        {"key": "marketReadiness", "state": "ready", "label": "Top-down market context available"}
                    ],
                    "sourceAuthority": "scoreGradeAllowed",
                    "freshness": "delayed",
                    "nextResearchStep": "补充基本面证据",
                    "noAdviceBoundary": True,
                    "debugRef": "scanner:candidate_summary:NVDA",
                },
            }
        ],
    )

    assert response.shortlist[0].candidateEvidenceFrame["contractVersion"] == "scanner_candidate_evidence_v1"
    assert response.shortlist[0].candidateResearchReadiness["readinessState"] == "insufficient"
    assert response.shortlist[0].candidateResearchSummaryFrame["contractVersion"] == "scanner_candidate_research_summary_v1"
    assert response.shortlist[0].candidateResearchSummaryFrame["nextResearchStep"] == "补充基本面证据"
    assert response.selected[0].candidateEvidenceFrame["coverageState"] == "partial"
    assert [
        (item.symbol, item.rank, item.score, item.raw_score, item.final_score)
        for item in response.shortlist
    ] == [
        (item.symbol, item.rank, item.score, item.raw_score, item.final_score)
        for item in response.selected
    ]
