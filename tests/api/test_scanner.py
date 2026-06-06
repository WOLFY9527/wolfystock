# -*- coding: utf-8 -*-
"""Scanner API schema coverage for backward-compatible diagnostics."""

from api.v1.schemas.scanner import (
    ScannerConsumerDiagnosticsMetadata,
    ScannerEvidencePacketMetadata,
    ScannerRunDetailResponse,
    ScannerScoreExplainabilityMetadata,
)
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
                "candidateSourceProvenanceFrame": {
                    "contractVersion": "source_provenance_v1",
                    "entryCount": 1,
                    "authorityTierCounts": {"unknown": 1},
                    "freshnessStateCounts": {"unknown": 1},
                    "evidenceDomainCounts": {"market_data": 1},
                    "fallbackOrProxyCount": 1,
                    "observationOnlyCount": 1,
                    "scoreContributionAllowedCount": 0,
                    "entries": [],
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
    assert response.shortlist[0].candidateSourceProvenanceFrame["contractVersion"] == "source_provenance_v1"
    assert response.shortlist[0].candidateSourceProvenanceFrame["scoreContributionAllowedCount"] == 0
    assert response.selected[0].candidateEvidenceFrame["coverageState"] == "partial"
    assert [
        (item.symbol, item.rank, item.score, item.raw_score, item.final_score)
        for item in response.shortlist
    ] == [
        (item.symbol, item.rank, item.score, item.raw_score, item.final_score)
        for item in response.selected
    ]


def test_scanner_run_response_locks_score_explainability_metadata_without_score_order_drift() -> None:
    response = ScannerRunDetailResponse(
        id=4,
        market="cn",
        profile="cn_preopen_v1",
        status="completed",
        universe_name="cn_liquid",
        shortlist_size=2,
        universe_size=5,
        preselected_size=5,
        evaluated_size=5,
        shortlist=[
            {
                "symbol": "600001",
                "name": "股票600001",
                "rank": 1,
                "score": 40.0,
                "raw_score": 81.6,
                "final_score": 40.0,
                "diagnostics": {
                    "history_source": "local_partial_fallback",
                    "score_explainability": {
                        "raw_score": 81.6,
                        "final_score": 40.0,
                        "score_delta": -41.6,
                        "score_cap": 40.0,
                        "score_confidence": 0.4,
                        "evidence_coverage": 0.76,
                        "cap_reason": "fallback_source",
                        "degradation_reason": "fallback_source",
                        "cap_applied": True,
                        "missing_evidence": ["history_depth", "quote_context"],
                        "reason_codes": ["fallback_source"],
                        "score_grade_allowed": False,
                        "source_confidence": {
                            "source": "fallback_snapshot",
                            "sourceLabel": "Fallback snapshot",
                            "sourceType": "fallback_static",
                            "freshness": "fallback",
                            "isFallback": True,
                            "isStale": True,
                            "isPartial": True,
                            "isSynthetic": False,
                            "isUnavailable": False,
                            "confidenceWeight": 0.4,
                            "coverage": 0.76,
                            "capReason": "fallback_source",
                            "degradationReason": "fallback_source",
                            "sourceAuthorityAllowed": False,
                            "scoreContributionAllowed": False,
                            "observationOnly": True,
                            "proxyOnly": False,
                        },
                    },
                    "evidence_packet": {
                        "symbol": "600001",
                        "market": "cn",
                        "rank": 1,
                        "score": 40.0,
                        "rawScore": 81.6,
                        "finalScore": 40.0,
                        "scoreConfidence": 0.4,
                        "evidenceCoverage": 0.76,
                        "capReason": "fallback_source",
                        "degradationReason": "fallback_source",
                        "evidenceVersion": "scanner_evidence_v1",
                        "runId": 4,
                        "dataQualityState": "partial",
                        "freshnessState": "fallback",
                        "freshnessDetail": {
                            "quoteState": "fallback",
                            "historyState": "stale",
                            "latestTradeDate": "2026-05-08",
                        },
                        "providerObservation": {
                            "observationOnly": True,
                            "scoreContributionAllowed": False,
                            "entries": [
                                {
                                    "stage": "snapshot",
                                    "providerName": "akshare",
                                    "sourceType": "public_proxy",
                                    "observationOnly": True,
                                    "scoreContributionAllowed": False,
                                }
                            ],
                        },
                        "missingEvidence": ["history_depth", "quote_context"],
                        "userFacingLabels": ["仅供观察", "需人工复核"],
                        "warningFlags": ["仅供观察", "需人工复核"],
                    },
                },
                "consumerDiagnostics": {
                    "status": "limited",
                    "scoreGradeAllowed": False,
                    "scoreConfidence": 0.4,
                    "capReason": "fallback_source",
                    "degradationReason": "fallback_source",
                    "dataQualityState": "partial",
                    "freshnessState": "fallback",
                    "sourceClass": "fallback",
                    "missingEvidence": ["history_depth", "quote_context"],
                    "userFacingLabels": ["仅供观察", "需人工复核"],
                    "warningFlags": ["仅供观察", "需人工复核"],
                },
            },
            {
                "symbol": "600002",
                "name": "股票600002",
                "rank": 2,
                "score": 39.0,
                "raw_score": 39.0,
                "final_score": 39.0,
            },
        ],
    )

    serialized = response.model_dump()
    assert [(item["symbol"], item["rank"], item["score"]) for item in serialized["shortlist"]] == [
        ("600001", 1, 40.0),
        ("600002", 2, 39.0),
    ]

    explainability = ScannerScoreExplainabilityMetadata.model_validate(
        serialized["shortlist"][0]["diagnostics"]["score_explainability"]
    )
    source_confidence = explainability.source_confidence
    assert explainability.raw_score == 81.6
    assert explainability.final_score == 40.0
    assert explainability.score_delta == -41.6
    assert explainability.score_cap == 40.0
    assert explainability.score_confidence == 0.4
    assert explainability.evidence_coverage == 0.76
    assert explainability.cap_reason == "fallback_source"
    assert explainability.degradation_reason == "fallback_source"
    assert explainability.cap_applied is True
    assert explainability.missing_evidence == ["history_depth", "quote_context"]
    assert explainability.reason_codes == ["fallback_source"]
    assert explainability.score_grade_allowed is False
    assert source_confidence is not None
    assert source_confidence.source == "fallback_snapshot"
    assert source_confidence.sourceType == "fallback_static"
    assert source_confidence.isFallback is True
    assert source_confidence.isStale is True
    assert source_confidence.isPartial is True
    assert source_confidence.confidenceWeight == 0.4
    assert source_confidence.sourceAuthorityAllowed is False
    assert source_confidence.scoreContributionAllowed is False
    assert source_confidence.observationOnly is True

    evidence_packet = ScannerEvidencePacketMetadata.model_validate(
        serialized["shortlist"][0]["diagnostics"]["evidence_packet"]
    )
    assert evidence_packet.rawScore == 81.6
    assert evidence_packet.finalScore == 40.0
    assert evidence_packet.scoreConfidence == 0.4
    assert evidence_packet.capReason == "fallback_source"
    assert evidence_packet.dataQualityState == "partial"
    assert evidence_packet.freshnessState == "fallback"
    assert evidence_packet.freshnessDetail is not None
    assert evidence_packet.freshnessDetail.quoteState == "fallback"
    assert evidence_packet.freshnessDetail.historyState == "stale"
    assert evidence_packet.providerObservation is not None
    assert evidence_packet.providerObservation.entries[0]["sourceType"] == "public_proxy"
    assert evidence_packet.missingEvidence == ["history_depth", "quote_context"]

    consumer_diagnostics = ScannerConsumerDiagnosticsMetadata.model_validate(
        serialized["shortlist"][0]["consumerDiagnostics"]
    )
    assert consumer_diagnostics.scoreGradeAllowed is False
    assert consumer_diagnostics.scoreConfidence == 0.4
    assert consumer_diagnostics.capReason == "fallback_source"
    assert consumer_diagnostics.degradationReason == "fallback_source"
    assert consumer_diagnostics.dataQualityState == "partial"
    assert consumer_diagnostics.freshnessState == "fallback"
    assert consumer_diagnostics.sourceClass == "fallback"
