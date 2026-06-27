# -*- coding: utf-8 -*-
"""Scanner API schema coverage for backward-compatible diagnostics."""

from __future__ import annotations

import json

from api.v1.schemas.scanner import (
    ScannerConsumerDiagnosticsMetadata,
    ScannerEvidencePacketMetadata,
    ScannerCandidateResponse,
    ScannerRunDetailResponse,
    ScannerScoreExplainabilityMetadata,
    sanitize_scanner_consumer_payload,
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


def test_scanner_run_response_preserves_current_coarse_empty_reason_without_evidence_detail() -> None:
    response = ScannerRunDetailResponse(
        id=3,
        market="us",
        profile="us_preopen_v1",
        status="empty",
        universe_name="us_liquid",
        shortlist_size=0,
        universe_size=0,
        preselected_size=0,
        evaluated_size=0,
        source_summary="scanner=empty",
        diagnostics={
            "empty_reason": "扫描宇宙为空，无法生成候选名单",
            "operation": {
                "trigger_mode": "manual",
                "request_source": "api",
                "watchlist_date": "2026-06-09",
            },
            "dataReadiness": {
                "state": "blocked",
                "market": "us",
                "profile": "us_preopen_v1",
                "universeSize": 0,
                "quoteCoverage": "unknown",
                "historyCoverage": "unknown",
                "freshness": "unknown",
                "blockerBucket": "empty_universe",
                "consumerSummary": "候选池为空，Scanner 暂时无法生成候选。",
                "nextDataAction": "补充可扫描标的池后重新运行 Scanner。",
            },
        },
    )

    serialized = response.model_dump()

    assert serialized["status"] == "empty"
    assert serialized["shortlist"] == []
    assert serialized["selected"] == []
    assert serialized["candidates"] == []
    assert serialized["diagnostics"]["empty_reason"] == "扫描宇宙为空，无法生成候选名单"
    assert set(serialized["diagnostics"]) == {"empty_reason", "operation", "dataReadiness"}
    assert serialized["diagnostics"]["dataReadiness"]["blockerBucket"] == "empty_universe"
    assert "coverage_summary" not in serialized["diagnostics"]
    assert "candidate_diagnostics" not in serialized["diagnostics"]
    assert "universe_selection" not in serialized["diagnostics"]
    assert serialized["accepted_symbols_count"] == 0


def test_scanner_consumer_payload_recursively_redacts_ohlcv_readiness_forbidden_diagnostics() -> None:
    payload = {
        "id": 99,
        "market": "us",
        "profile": "us_preopen_v1",
        "status": "completed",
        "universe_name": "us_liquid",
        "shortlist_size": 1,
        "universe_size": 1,
        "preselected_size": 1,
        "evaluated_size": 1,
        "diagnostics": {
            "providerName": "LeakyProvider",
            "requestId": "rq-secret",
            "rawPayload": {"token": "secret-token"},
            "dataReadiness": {
                "state": "blocked",
                "availabilityState": "not_available",
                "executionState": "blocked",
                "universeReadiness": {
                    "state": "available",
                    "reason": "fixture_universe",
                    "providerName": "LeakyProvider",
                    "rawPayload": {"token": "secret-token"},
                },
                "quoteReadiness": {
                    "state": "missing",
                    "reason": "provider_error",
                    "traceId": "trace-secret",
                },
                "historyReadiness": {
                    "state": "missing",
                    "reason": "provider_unavailable",
                    "exceptionClass": "RuntimeError",
                },
                "benchmarkReadiness": {
                    "state": "missing",
                    "reason": "missing_benchmark",
                    "requestId": "rq-secret",
                },
                "candidateGenerationState": "blocked",
                "candidateGenerationBlockers": ["provider_missing", "missing_benchmark"],
                "missingRequirements": ["provider_missing"],
                "scannerUniverseReadiness": {
                    "contractVersion": "scanner_universe_readiness_v1",
                    "status": "insufficient_coverage",
                    "market": "US",
                    "universeSize": 2,
                    "requiredDataClasses": ["universe", "historical_ohlcv", "quote_snapshot"],
                    "availableDataClasses": ["universe"],
                    "missingDataClasses": ["historical_ohlcv", "quote_snapshot"],
                    "blockedProductSurfaces": ["Scanner", "Market Overview", "Backtest"],
                    "consumerSafeMessage": "标的池可用，但行情或历史覆盖不足，暂不生成候选。",
                    "operatorNextAction": "Refresh local universe; token=secret requestId=rq-secret",
                    "requestId": "rq-secret",
                    "traceId": "trace-secret",
                    "cacheKey": "cache-secret",
                    "rawPayload": {"token": "secret-token"},
                },
                "ohlcvReadiness": {
                    "providerClass": "LeakyClass",
                    "traceId": "trace-secret",
                    "raw_provider_payload": {"credential": "secret"},
                },
            },
        },
        "shortlist": [
            {
                "symbol": "NVDA",
                "name": "NVIDIA",
                "rank": 1,
                "score": 0,
                "historicalOhlcvReadiness": {
                    "contractVersion": "historical_ohlcv_readiness_v1",
                    "symbol": "NVDA",
                    "market": "us",
                    "timeframe": "1d",
                    "requiredBars": 70,
                    "usableBars": 0,
                    "missingBars": 70,
                    "providerState": "provider_missing",
                    "overallState": "blocked",
                    "missingRequirements": ["provider_missing", "insufficient_history"],
                    "providerName": "LeakyProvider",
                    "endpointHost": "provider.example.test",
                    "apiKeyPresent": True,
                    "exceptionClass": "RuntimeError",
                    "exceptionChain": ["Traceback token secret"],
                    "requestId": "rq-secret",
                    "traceId": "trace-secret",
                    "cacheKey": "cache-secret",
                    "rawPayload": {"API_KEY": "secret"},
                    "raw_provider_payload": {"PASSWORD": "secret"},
                    "credential": "secret",
                    "env": "SECRET",
                    "PRIVATE_KEY": "secret",
                },
                "consumerDiagnostics": {
                    "status": "limited",
                    "missingEvidence": ["provider_missing"],
                    "warningFlags": ["provider_missing"],
                },
            }
        ],
    }

    sanitized = sanitize_scanner_consumer_payload(payload)
    response = ScannerRunDetailResponse(**sanitized).model_dump()
    serialized = json.dumps(response, ensure_ascii=False).lower()

    for forbidden in (
        "leakyprovider",
        "leakyclass",
        "provider.example.test",
        "rq-secret",
        "trace-secret",
        "cache-secret",
        "secret-token",
        "api_key",
        "password",
        "private_key",
        "traceback",
        "exceptionclass",
        "raw_provider_payload",
        "rawpayload",
        "credential",
    ):
        assert forbidden not in serialized
    assert response["diagnostics"]["dataReadiness"]["universeReadiness"]["state"] == "available"
    assert response["diagnostics"]["dataReadiness"]["scannerUniverseReadiness"]["status"] == "insufficient_coverage"
    assert "operatorNextAction" not in response["diagnostics"]["dataReadiness"]["scannerUniverseReadiness"]
    assert response["diagnostics"]["dataReadiness"]["quoteReadiness"]["state"] == "missing"
    assert response["diagnostics"]["dataReadiness"]["benchmarkReadiness"]["state"] == "missing"
    assert response["diagnostics"]["dataReadiness"]["candidateGenerationState"] == "blocked"
    readiness = response["shortlist"][0]["historicalOhlcvReadiness"]
    assert readiness["providerState"] == "provider_missing"
    assert readiness["requiredBars"] == 70
    assert readiness["missingBars"] == 70


def test_scanner_run_response_accepts_additive_candidate_evidence_and_readiness_fields() -> None:
    response = ScannerRunDetailResponse(
        id=4,
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


def test_scanner_candidate_research_packet_summarizes_why_and_limits_without_ranking_drift() -> None:
    response = ScannerRunDetailResponse(
        id=41,
        market="us",
        profile="us_preopen_v1",
        status="completed",
        universe_name="us_liquid",
        shortlist_size=2,
        universe_size=5,
        preselected_size=5,
        evaluated_size=5,
        shortlist=[
            {
                "symbol": "NVDA",
                "name": "NVIDIA",
                "rank": 1,
                "score": 82.0,
                "raw_score": 87.0,
                "final_score": 82.0,
                "reason_summary": "趋势与量能支持继续研究。",
                "reasons": ["20 日趋势改善", "相对成交活跃"],
                "risk_notes": ["基本面与新闻催化证据仍有限"],
                "key_metrics": [{"label": "20日动量", "value": "+8.2%"}],
                "feature_signals": [{"label": "趋势", "value": "18.0 / 20"}],
                "candidateResearchReadiness": {
                    "readinessState": "insufficient",
                    "missingEvidence": ["fundamentals", "news"],
                    "nextEvidenceNeeded": ["补充基本面证据"],
                    "consumerActionBoundary": "no_advice",
                    "debugRef": "scanner:candidate:NVDA",
                },
                "candidateResearchSummaryFrame": {
                    "primaryResearchReason": "趋势与量能支持继续研究。",
                    "evidenceHighlights": ["Technicals available", "Liquidity available"],
                    "missingEvidence": ["fundamentals", "news"],
                    "blockingReasons": ["missing_required_evidence"],
                    "nextResearchStep": "补充基本面证据",
                    "debugRef": "scanner:candidate_summary:NVDA",
                },
                "consumerDiagnostics": {
                    "reasonLabel": "已进入本轮观察名单",
                    "dataQualityState": "partial",
                    "freshnessState": "delayed",
                    "missingEvidence": ["fundamentals", "news"],
                    "warningFlags": ["需人工复核"],
                },
            },
            {
                "symbol": "MSFT",
                "name": "Microsoft",
                "rank": 2,
                "score": 79.0,
                "raw_score": 79.0,
                "final_score": 79.0,
                "reason_summary": "趋势结构稳定。",
                "reasons": ["趋势稳定"],
            },
        ],
        selected=[
            {
                "symbol": "NVDA",
                "name": "NVIDIA",
                "rank": 1,
                "score": 82.0,
                "raw_score": 87.0,
                "final_score": 82.0,
                "reason_summary": "趋势与量能支持继续研究。",
                "reasons": ["20 日趋势改善", "相对成交活跃"],
                "candidateResearchSummaryFrame": {
                    "primaryResearchReason": "趋势与量能支持继续研究。",
                    "evidenceHighlights": ["Technicals available", "Liquidity available"],
                    "missingEvidence": ["fundamentals", "news"],
                    "nextResearchStep": "补充基本面证据",
                },
                "candidateResearchReadiness": {
                    "readinessState": "insufficient",
                    "missingEvidence": ["fundamentals", "news"],
                    "nextEvidenceNeeded": ["补充基本面证据"],
                    "consumerActionBoundary": "no_advice",
                },
                "consumerDiagnostics": {
                    "reasonLabel": "已进入本轮观察名单",
                    "dataQualityState": "partial",
                    "freshnessState": "delayed",
                    "missingEvidence": ["fundamentals", "news"],
                    "warningFlags": ["需人工复核"],
                },
            }
        ],
    )

    serialized = response.model_dump()

    assert [(item["symbol"], item["rank"], item["score"]) for item in serialized["shortlist"]] == [
        ("NVDA", 1, 82.0),
        ("MSFT", 2, 79.0),
    ]
    packet = serialized["shortlist"][0]["candidateResearchPacket"]
    assert packet == serialized["selected"][0]["candidateResearchPacket"]
    assert packet["whySurfaced"] == "趋势与量能支持继续研究。"
    assert packet["primaryEvidence"] == ["Technicals available", "Liquidity available"]
    assert "fundamentals" in packet["limitingEvidence"]
    assert "news" in packet["limitingEvidence"]
    assert packet["dataQualityNotes"]
    assert packet["rejectedOrLimitedReasonSafeLabel"] == "已进入本轮观察名单"
    assert packet["researchNextStep"] == "补充基本面证据"
    assert packet["evidenceBoundaries"]["noAdvice"] is True
    assert packet["evidenceBoundaries"]["decisionGrade"] is False
    assert packet["noAdviceLabel"] == "Observation-only research context; not investment advice."
    assert packet["observationOnly"] is True
    assert serialized["shortlist"][0]["evidenceBoundaries"]["noAdvice"] is True
    assert serialized["shortlist"][0]["rankingConfidence"]["rankingUse"] == "relative_observation_only"


def test_scanner_candidate_research_packet_is_bounded_and_no_advice() -> None:
    candidate = ScannerCandidateResponse(
        symbol="SAFE",
        name="Safe Candidate",
        rank=3,
        score=40.0,
        raw_score=81.0,
        final_score=40.0,
        reason_summary="fallback_source provider_timeout _blocked request_id=abc should not leak",
        reasons=["buy now", "relative volume improved"],
        risk_notes=["rawProviderPayload hidden", "需补充成交确认"],
        candidateResearchReadiness={
            "readinessState": "_gate_failed",
            "missingEvidence": ["raw_provider_error", "history_depth", "_blocked"],
            "nextEvidenceNeeded": ["place order", "补充历史行情覆盖"],
        },
        candidateResearchSummaryFrame={
            "primaryResearchReason": "raw diagnostics provider_timeout requestId=abc",
            "evidenceHighlights": ["trace_id=abc", "趋势结构改善"],
            "missingEvidence": ["raw_payload", "成交覆盖不足"],
            "blockingReasons": ["_gate", "provider_error"],
            "nextResearchStep": "buy now",
        },
        consumerDiagnostics={
            "reasonLabel": "raw_provider_error",
            "nextEvidence": "等待更多历史行情覆盖后再复核。",
            "dataQualityState": "partial",
        },
        diagnostics={
            "rawProviderPayload": {"secret": "hidden"},
            "requestId": "abc",
            "provider_timeout": True,
        },
    )

    packet = candidate.model_dump()["candidateResearchPacket"]
    serialized_text = json.dumps(packet, ensure_ascii=False).lower()

    assert packet["whySurfaced"] == "relative volume improved"
    assert packet["primaryEvidence"] == ["趋势结构改善"]
    assert packet["limitingEvidence"] == ["成交覆盖不足"]
    assert packet["rejectedOrLimitedReasonSafeLabel"] == "证据有限，需补充研究"
    assert packet["researchNextStep"] == "等待更多历史行情覆盖后再复核。"
    assert packet["observationOnly"] is True
    for forbidden in (
        "buy now",
        "place order",
        "rawproviderpayload",
        "raw_payload",
        "raw_provider",
        "provider_timeout",
        "request_id",
        "requestid",
        "_blocked",
        "_gate",
        "secret",
    ):
        assert forbidden not in serialized_text


def test_scanner_run_response_locks_score_explainability_metadata_without_score_order_drift() -> None:
    response = ScannerRunDetailResponse(
        id=5,
        market="cn",
        profile="cn_preopen_v1",
        status="completed",
        universe_name="cn_liquid",
        shortlist_size=2,
        universe_size=5,
        preselected_size=5,
        evaluated_size=5,
        summary={"limited_by_result_cap": True},
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
    assert serialized["summary"]["limited_by_result_cap"] is True
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


def test_scanner_run_response_keeps_mixed_quality_candidates_fail_closed() -> None:
    def candidate(
        *,
        symbol: str,
        rank: int,
        freshness: str,
        source_authority_allowed: bool,
        score_contribution_allowed: bool,
        flags: dict[str, bool] | None = None,
    ) -> dict:
        score = 90.0 - rank
        confidence_weight = 1.0 if score_contribution_allowed else 0.35
        return {
            "symbol": symbol,
            "name": f"股票{symbol}",
            "rank": rank,
            "score": score,
            "raw_score": score,
            "final_score": score,
            "diagnostics": {
                "score_explainability": {
                    "raw_score": score,
                    "final_score": score,
                    "score_confidence": confidence_weight,
                    "evidence_coverage": confidence_weight,
                    "cap_reason": None if score_contribution_allowed else f"{freshness}_evidence",
                    "degradation_reason": None if score_contribution_allowed else f"{freshness}_evidence",
                    "score_grade_allowed": score_contribution_allowed,
                    "source_confidence": {
                        "source": "official_feed" if source_authority_allowed else f"{freshness}_candidate",
                        "sourceType": "official_public" if source_authority_allowed else freshness,
                        "freshness": freshness,
                        "confidenceWeight": confidence_weight,
                        "coverage": confidence_weight,
                        "sourceAuthorityAllowed": source_authority_allowed,
                        "scoreContributionAllowed": score_contribution_allowed,
                        "observationOnly": not score_contribution_allowed,
                        **(flags or {}),
                    },
                }
            },
            "consumerDiagnostics": {
                "status": "available" if score_contribution_allowed else "limited",
                "scoreGradeAllowed": score_contribution_allowed,
                "scoreConfidence": confidence_weight,
                "freshnessState": freshness,
                "sourceClass": "official" if source_authority_allowed else "limited",
            },
        }

    response = ScannerRunDetailResponse(
        id=5,
        market="us",
        profile="us_preopen_v1",
        status="completed",
        universe_name="us_liquid",
        shortlist_size=6,
        universe_size=6,
        preselected_size=6,
        evaluated_size=6,
        shortlist=[
            candidate(
                symbol="OFFICIAL",
                rank=1,
                freshness="fresh",
                source_authority_allowed=True,
                score_contribution_allowed=True,
            ),
            candidate(
                symbol="FALLB",
                rank=2,
                freshness="fallback",
                source_authority_allowed=False,
                score_contribution_allowed=False,
                flags={"isFallback": True},
            ),
            candidate(
                symbol="STALE",
                rank=3,
                freshness="stale",
                source_authority_allowed=False,
                score_contribution_allowed=False,
                flags={"isStale": True},
            ),
            candidate(
                symbol="PARTL",
                rank=4,
                freshness="partial",
                source_authority_allowed=False,
                score_contribution_allowed=False,
                flags={"isPartial": True},
            ),
            candidate(
                symbol="SYNTH",
                rank=5,
                freshness="synthetic",
                source_authority_allowed=False,
                score_contribution_allowed=False,
                flags={"isSynthetic": True},
            ),
            candidate(
                symbol="UNAVL",
                rank=6,
                freshness="unavailable",
                source_authority_allowed=False,
                score_contribution_allowed=False,
                flags={"isUnavailable": True},
            ),
        ],
    )

    serialized = response.model_dump()
    by_symbol = {item["symbol"]: item for item in serialized["shortlist"]}
    official_confidence = by_symbol["OFFICIAL"]["diagnostics"]["score_explainability"]["source_confidence"]
    assert official_confidence["sourceAuthorityAllowed"] is True
    assert official_confidence["scoreContributionAllowed"] is True

    for symbol in ("FALLB", "STALE", "PARTL", "SYNTH", "UNAVL"):
        source_confidence = by_symbol[symbol]["diagnostics"]["score_explainability"]["source_confidence"]
        assert source_confidence["sourceAuthorityAllowed"] is False
        assert source_confidence["scoreContributionAllowed"] is False
        assert source_confidence["observationOnly"] is True
        assert by_symbol[symbol]["consumerDiagnostics"]["scoreGradeAllowed"] is False
