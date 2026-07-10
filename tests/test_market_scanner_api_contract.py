# -*- coding: utf-8 -*-
"""Contract tests for market scanner endpoints."""

from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from api.v1.endpoints.scanner import (
    create_scanner_theme,
    get_scanner_themes,
    get_recent_watchlists,
    get_market_scan_run,
    get_market_scan_runs,
    get_scanner_strategy_simulation,
    get_scanner_operational_status,
    get_today_watchlist,
    run_market_scan,
)
from api.v1.schemas.scanner import ScannerRunRequest, ScannerThemeGenerateRequest
from src.services.market_scanner_service import MarketScannerService
from src.services.scanner_evidence_packet import build_scanner_evidence_packet


FORBIDDEN_CONSUMER_RESPONSE_FIELDS = (
    "fallback",
    "trustLevel",
    "reasonCode",
    "launchVerdict",
    "consumerVisible",
    "advisoryOnly",
    "liveEnforcement",
    "isFallback",
    "isStale",
    "isPartial",
    "sourceType",
    "scoreContributionAllowed",
    "observationOnly",
    "raw provider error",
    "Traceback",
    "https://",
    "api_key",
    "secret",
    "cookie",
    "session_id",
    "token",
)


def _assert_no_forbidden_consumer_response_fields(payload: dict) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    normalized = serialized.lower()
    for forbidden in FORBIDDEN_CONSUMER_RESPONSE_FIELDS:
        assert forbidden not in serialized
        assert forbidden.lower() not in normalized


def _make_candidate(symbol: str, rank: int, *, benchmark_code: str = "000300") -> dict:
    return {
        "symbol": symbol,
        "name": f"股票{symbol}",
        "rank": rank,
        "score": 80.0 - rank,
        "raw_score": 88.0 - rank,
        "final_score": 80.0 - rank,
        "quality_hint": "高优先级",
        "reason_summary": "趋势与量能共振。",
        "reasons": ["趋势结构完整。"],
        "key_metrics": [{"label": "最新价", "value": "18.20"}],
        "feature_signals": [{"label": "趋势结构", "value": "18.0 / 20"}],
        "risk_notes": ["需要确认竞价承接。"],
        "watch_context": [{"label": "观察触发", "value": "上破近 20 日高点。"}],
        "boards": ["AI算力"],
        "appeared_in_recent_runs": 0,
        "last_trade_date": "2026-04-10",
        "scan_timestamp": "2026-04-13T08:30:00",
        "ai_interpretation": {
            "available": True,
            "status": "generated",
            "summary": "AI 认为这更像趋势延续中的临界突破观察名单。",
            "opportunity_type": "临界突破",
            "risk_interpretation": "若竞价高开过多，承接不足时容易转成冲高回落。",
            "watch_plan": "盘前先看竞价承接，开盘后再看量能是否继续放大。",
            "review_commentary": "后续走势跑赢基准，说明强势题材与量能配合有效。",
            "provider": "gemini",
            "model": "gemini/gemini-2.5-flash",
            "generated_at": "2026-04-13T08:30:10",
            "message": None,
        },
        "realized_outcome": {
            "review_status": "ready",
            "outcome_label": "strong",
            "thesis_match": "validated",
            "review_window_days": 3,
            "anchor_date": "2026-04-10",
            "window_end_date": "2026-04-15",
            "same_day_close_return_pct": 2.3,
            "next_day_return_pct": 1.2,
            "review_window_return_pct": 5.6,
            "max_favorable_move_pct": 7.4,
            "max_adverse_move_pct": -1.5,
            "benchmark_code": benchmark_code,
            "benchmark_return_pct": 1.8,
            "outperformed_benchmark": True,
        },
        "diagnostics": {
            "history_source": "local_db",
            "score_explainability": {
                "raw_score": 88.0 - rank,
                "final_score": 80.0 - rank,
                "cap_reason": None,
                "degradation_reason": None,
                "score_confidence": 1.0,
                "evidence_coverage": 1.0,
                "missing_evidence": [],
            },
        },
    }


def _make_run_payload(
    run_id: int = 12,
    *,
    market: str = "cn",
    profile: str = "cn_preopen_v1",
    profile_label: str = "A股盘前扫描 v1",
    benchmark_code: str = "000300",
) -> dict:
    is_us = market == "us"
    universe_name = "us_preopen_watchlist_v1" if is_us else "cn_a_liquid_watchlist_v1"
    headline = "今日美股盘前优先观察：NVDA / AAPL" if is_us else "今日 A 股盘前优先观察：600001 / 600002"
    primary_symbol = "NVDA" if is_us else "600001"
    secondary_symbol = "AAPL" if is_us else "600002"
    shortlist = [
        _make_candidate(primary_symbol, 1, benchmark_code=benchmark_code),
        _make_candidate(secondary_symbol, 2, benchmark_code=benchmark_code),
    ]
    return {
        "id": run_id,
        "market": market,
        "profile": profile,
        "profile_label": profile_label,
        "status": "completed",
        "run_at": "2026-04-13T08:30:00",
        "completed_at": "2026-04-13T08:31:00",
        "watchlist_date": "2026-04-13",
        "trigger_mode": "manual",
        "universe_name": universe_name,
        "shortlist_size": 2,
        "universe_size": 180 if is_us else 300,
        "preselected_size": 40 if is_us else 60,
        "evaluated_size": 32 if is_us else 48,
        "source_summary": "universe=local_us_history; snapshot=optional_us_realtime_quote; history=local_us_first" if is_us else "stock_list=FakeList; snapshot=FakeSnapshot; history=local_first; sector=enabled",
        "headline": headline,
        "universe_notes": ["使用本地 US history universe。"] if is_us else ["剔除 ST 与停牌近似状态。"],
        "scoring_notes": ["流动性、趋势延续、相对强度与 gap context 共同决定排序。"] if is_us else ["趋势、量能、活跃度加权。"],
        "diagnostics": {
            "history_stats": {"local_hits": 10},
            "ai_interpretation": {
                "enabled": True,
                "status": "completed",
                "top_n": 2,
                "attempted_candidates": 2,
                "generated_candidates": 2,
                "failed_candidates": 0,
                "skipped_candidates": 0,
                "models_used": ["gemini/gemini-2.5-flash"],
                "fallback_used": False,
                "message": "已为前 2 名候选生成 AI 解读。",
            },
        },
        "notification": {
            "attempted": False,
            "status": "not_attempted",
            "success": None,
            "channels": [],
            "message": None,
            "report_path": None,
            "sent_at": None,
        },
        "failure_reason": None,
        "comparison_to_previous": {
            "available": True,
            "previous_run_id": 11,
            "previous_watchlist_date": "2026-04-10",
            "new_count": 1,
            "retained_count": 1,
            "dropped_count": 1,
            "new_symbols": [{"symbol": primary_symbol, "name": f"股票{primary_symbol}", "current_rank": 1, "previous_rank": None, "rank_delta": None}],
            "retained_symbols": [{"symbol": secondary_symbol, "name": f"股票{secondary_symbol}", "current_rank": 2, "previous_rank": 1, "rank_delta": -1}],
            "dropped_symbols": [{"symbol": "MSFT" if is_us else "600003", "name": f"股票{'MSFT' if is_us else '600003'}", "current_rank": None, "previous_rank": 2, "rank_delta": None}],
        },
        "review_summary": {
            "available": True,
            "review_window_days": 3,
            "review_status": "ready",
            "candidate_count": 2,
            "reviewed_count": 2,
            "pending_count": 0,
            "hit_rate_pct": 50.0,
            "outperform_rate_pct": 50.0,
            "avg_same_day_close_return_pct": 1.5,
            "avg_review_window_return_pct": 2.2,
            "avg_max_favorable_move_pct": 4.0,
            "avg_max_adverse_move_pct": -1.8,
            "strong_count": 1,
            "mixed_count": 0,
            "weak_count": 1,
            "best_symbol": "600001",
            "best_return_pct": 5.6,
            "weakest_symbol": "600002",
            "weakest_return_pct": -1.2,
        },
        "candidates": [],
        "selected": copy.deepcopy(shortlist),
        "shortlist": shortlist,
    }


def _make_operational_status_payload(
    *,
    market: str = "cn",
    profile: str = "cn_preopen_v1",
    profile_label: str = "A股盘前扫描 v1",
    benchmark_code: str = "000300",
) -> dict:
    is_us = market == "us"
    headline = "今日美股盘前优先观察：NVDA / AAPL" if is_us else "今日 A 股盘前优先观察：600001 / 600002"
    return {
        "market": market,
        "profile": profile,
        "profile_label": profile_label,
        "watchlist_date": "2026-04-13",
        "today_trading_day": True,
        "schedule_enabled": True,
        "schedule_time": "21:20" if is_us else "08:40",
        "schedule_run_immediately": False,
        "notification_enabled": True,
        "dataReadiness": {
            "state": "not_run",
            "market": market,
            "profile": profile,
            "universeAvailability": "unknown",
            "universeSize": 0,
            "quoteCoverage": "unknown",
            "historyCoverage": "unknown",
            "freshness": "unknown",
            "candidateEvaluationCount": 0,
            "selectedCount": 0,
            "rejectedCount": 0,
            "failedCount": 0,
            "blockerBucket": "unknown",
            "consumerSummary": "Scanner 尚未运行，暂时没有数据准备度结论。",
            "nextDataAction": "运行 Scanner 后查看数据准备度。",
        },
        "today_watchlist": {
            "id": 12,
            "watchlist_date": "2026-04-13",
            "trigger_mode": "scheduled",
            "status": "completed",
            "run_at": "2026-04-13T08:40:00",
            "headline": headline,
            "shortlist_size": 2,
            "notification_status": "success",
            "failure_reason": None,
        },
        "last_run": {
            "id": 12,
            "watchlist_date": "2026-04-13",
            "trigger_mode": "scheduled",
            "status": "completed",
            "run_at": "2026-04-13T08:40:00",
            "headline": headline,
            "shortlist_size": 2,
            "notification_status": "success",
            "failure_reason": None,
        },
        "last_scheduled_run": {
            "id": 12,
            "watchlist_date": "2026-04-13",
            "trigger_mode": "scheduled",
            "status": "completed",
            "run_at": "2026-04-13T08:40:00",
            "headline": headline,
            "shortlist_size": 2,
            "notification_status": "success",
            "failure_reason": None,
        },
        "last_manual_run": {
            "id": 11,
            "watchlist_date": "2026-04-13",
            "trigger_mode": "manual",
            "status": "completed",
            "run_at": "2026-04-13T08:32:00",
            "headline": headline,
            "shortlist_size": 2,
            "notification_status": "not_attempted",
            "failure_reason": None,
        },
        "latest_failure": None,
        "quality_summary": {
            "available": True,
            "review_window_days": 3,
            "benchmark_code": benchmark_code,
            "run_count": 5,
            "reviewed_run_count": 4,
            "reviewed_candidate_count": 18,
            "review_coverage_pct": 90.0,
            "avg_candidates_per_run": 4.2,
            "avg_shortlist_return_pct": 1.8,
            "positive_run_rate_pct": 75.0,
            "hit_rate_pct": 61.1,
            "outperform_rate_pct": 55.6,
            "positive_candidate_avg_score": 82.4,
            "negative_candidate_avg_score": 74.2,
        },
    }


class MarketScannerApiContractTestCase(unittest.TestCase):
    def test_run_market_scan_passes_request_to_service(self) -> None:
        service = MagicMock()
        service.run_manual_scan.return_value = _make_run_payload()

        request = ScannerRunRequest(
            market="cn",
            profile="cn_preopen_v1",
            shortlist_size=5,
            universe_limit=300,
            detail_limit=60,
        )

        with patch("api.v1.endpoints.scanner.MarketScannerOperationsService", return_value=service):
            response = run_market_scan(request, db_manager=MagicMock())

        self.assertEqual(response.id, 12)
        self.assertEqual(response.shortlist[0].symbol, "600001")
        self.assertEqual(response.shortlist[0].realized_outcome.review_status, "ready")
        self.assertTrue(response.shortlist[0].ai_interpretation.available)
        self.assertEqual(response.shortlist[0].ai_interpretation.opportunity_type, "临界突破")
        self.assertEqual(response.watchlist_date, "2026-04-13")
        self.assertEqual(response.trigger_mode, "manual")
        self.assertEqual(response.comparison_to_previous.new_count, 1)
        self.assertEqual(response.review_summary.best_symbol, "600001")
        self.assertEqual(response.diagnostics["ai_interpretation"]["status"], "completed")
        self.assertEqual(response.shortlist[0].raw_score, 87.0)
        self.assertEqual(response.shortlist[0].final_score, 79.0)
        self.assertEqual(response.shortlist[0].score, 79.0)
        service.run_manual_scan.assert_called_once_with(
            market="cn",
            profile="cn_preopen_v1",
            shortlist_size=5,
            universe_limit=300,
            detail_limit=60,
            universe_type="default",
            theme_id=None,
            symbols=[],
            request_source="api",
            notify=False,
        )

    def test_run_market_scan_supports_us_profile_request(self) -> None:
        service = MagicMock()
        service.run_manual_scan.return_value = _make_run_payload(
            run_id=24,
            market="us",
            profile="us_preopen_v1",
            profile_label="US Pre-open Scanner v1",
            benchmark_code="SPY",
        )

        request = ScannerRunRequest(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=5,
            universe_limit=180,
            detail_limit=40,
        )

        with patch("api.v1.endpoints.scanner.MarketScannerOperationsService", return_value=service):
            response = run_market_scan(request, db_manager=MagicMock())

        self.assertEqual(response.id, 24)
        self.assertEqual(response.market, "us")
        self.assertEqual(response.profile, "us_preopen_v1")
        self.assertEqual(response.profile_label, "US Pre-open Scanner v1")
        self.assertEqual(response.shortlist[0].symbol, "NVDA")
        self.assertEqual(response.shortlist[0].realized_outcome.benchmark_code, "SPY")
        service.run_manual_scan.assert_called_once_with(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=5,
            universe_limit=180,
            detail_limit=40,
            universe_type="default",
            theme_id=None,
            symbols=[],
            request_source="api",
            notify=False,
        )

    def test_run_market_scan_preserves_selected_signature_when_projection_frames_are_present(self) -> None:
        service = MagicMock()
        payload = _make_run_payload(
            run_id=24,
            market="us",
            profile="us_preopen_v1",
            profile_label="US Pre-open Scanner v1",
            benchmark_code="SPY",
        )
        payload["scannerContextFrame"] = {
            "marketReadiness": {
                "contractVersion": "research_readiness_v1",
                "researchReady": True,
                "readinessState": "ready",
                "blockingReasons": [],
                "missingEvidence": [],
                "evidenceCoverage": {
                    "scoreGradeCount": 2,
                    "observationOnlyCount": 0,
                    "missingCount": 0,
                    "totalCount": 2,
                },
                "sourceAuthority": "scoreGradeAllowed",
                "freshnessFloor": "delayed",
                "consumerActionBoundary": "no_advice",
                "nextEvidenceNeeded": [],
                "debugRef": "scanner:24:context",
            },
            "noAdviceBoundary": True,
        }
        payload["shortlist"][0]["candidateEvidenceFrame"] = {
            "contractVersion": "scanner_candidate_evidence_v1",
            "coverageState": "partial",
        }
        payload["shortlist"][0]["candidateResearchReadiness"] = {
            "contractVersion": "research_readiness_v1",
            "readinessState": "insufficient",
        }
        payload["shortlist"][0]["candidateSourceProvenanceFrame"] = {
            "contractVersion": "source_provenance_v1",
            "entryCount": 1,
            "authorityTierCounts": {"unknown": 1},
            "freshnessStateCounts": {"unknown": 1},
            "evidenceDomainCounts": {"market_data": 1},
            "fallbackOrProxyCount": 1,
            "observationOnlyCount": 1,
            "scoreContributionAllowedCount": 0,
            "entries": [
                {
                    "contractVersion": "source_provenance_v1",
                    "sourceId": "unknown_source",
                    "sourceLabel": "未知来源",
                    "evidenceDomain": "market_data",
                    "authorityTier": "unknown",
                    "freshnessState": "unknown",
                    "sourceTier": "unknown",
                    "fallbackOrProxy": True,
                    "observationOnly": True,
                    "scoreContributionAllowed": False,
                    "limitations": ["unknown_source"],
                    "nextEvidenceNeeded": ["verified_source_metadata"],
                    "debugRef": "source-provenance:unknown",
                }
            ],
        }
        payload["selected"][0]["candidateEvidenceFrame"] = copy.deepcopy(payload["shortlist"][0]["candidateEvidenceFrame"])
        payload["selected"][0]["candidateResearchReadiness"] = copy.deepcopy(
            payload["shortlist"][0]["candidateResearchReadiness"]
        )
        payload["selected"][0]["candidateSourceProvenanceFrame"] = copy.deepcopy(
            payload["shortlist"][0]["candidateSourceProvenanceFrame"]
        )
        service.run_manual_scan.return_value = payload

        request = ScannerRunRequest(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=5,
            universe_limit=180,
            detail_limit=40,
        )

        with patch("api.v1.endpoints.scanner.MarketScannerOperationsService", return_value=service):
            response = run_market_scan(request, db_manager=MagicMock())

        shortlist_signature = [
            (item.symbol, item.rank, item.score, item.raw_score, item.final_score)
            for item in response.shortlist
        ]
        selected_signature = [
            (item.symbol, item.rank, item.score, item.raw_score, item.final_score)
            for item in response.selected
        ]
        self.assertEqual(selected_signature, shortlist_signature)
        serialized = response.model_dump()
        self.assertEqual(
            [item["symbol"] for item in serialized["shortlist"]],
            [item["symbol"] for item in payload["shortlist"]],
        )
        self.assertEqual(serialized["shortlist"][0]["candidateSourceProvenanceFrame"], {})
        self.assertEqual(
            serialized["selected"][0]["candidateSourceProvenanceFrame"],
            serialized["shortlist"][0]["candidateSourceProvenanceFrame"],
        )
        _assert_no_forbidden_consumer_response_fields(serialized)

    def test_run_market_scan_preserves_additive_scanner_context_frame(self) -> None:
        service = MagicMock()
        payload = _make_run_payload(
            run_id=24,
            market="us",
            profile="us_preopen_v1",
            profile_label="US Pre-open Scanner v1",
            benchmark_code="SPY",
        )
        payload["scannerContextFrame"] = {
            "marketReadiness": {
                "contractVersion": "research_readiness_v1",
                "researchReady": True,
                "readinessState": "ready",
                "verdictLabel": "研究证据可用",
                "blockingReasons": [],
                "missingEvidence": [],
                "evidenceCoverage": {
                    "scoreGradeCount": 2,
                    "observationOnlyCount": 0,
                    "missingCount": 0,
                    "totalCount": 2,
                },
                "sourceAuthority": "scoreGradeAllowed",
                "freshnessFloor": "delayed",
                "consumerActionBoundary": "no_advice",
                "nextEvidenceNeeded": [],
                "debugRef": "scanner:24:context",
            },
            "macroRegime": {
                "state": "supportive",
                "label": "Supportive macro regime",
                "source": "computed",
                "freshness": "cached",
                "confidence": {"value": 0.78, "label": "high"},
                "blockers": [],
                "observationOnly": False,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
            },
            "liquidityFrame": {
                "state": "supportive",
                "label": "Liquidity supports equity leadership",
                "source": "market_overview",
                "freshness": "cached",
                "observationOnly": False,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "proxyOnly": False,
                "blockers": [],
            },
            "assetClassBias": {
                "state": "supportive",
                "label": "Equities preferred",
                "observationOnly": False,
                "blockers": [],
            },
            "themeFrame": {
                "state": "supportive",
                "label": "AI/software/semis leadership intact",
                "freshness": "cached",
                "observationOnly": False,
                "proxyOnly": False,
                "blockers": [],
                "themes": [
                    {"id": "ai", "label": "AI", "state": "leading"},
                    {"id": "software", "label": "Software", "state": "broadening"},
                ],
            },
            "universePolicy": {
                "type": "default",
                "label": "Profile default universe",
                "reason": "scanner_profile_default_universe",
            },
            "noAdviceBoundary": True,
        }
        service.run_manual_scan.return_value = payload

        request = ScannerRunRequest(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=5,
            universe_limit=180,
            detail_limit=40,
        )

        with patch("api.v1.endpoints.scanner.MarketScannerOperationsService", return_value=service):
            response = run_market_scan(request, db_manager=MagicMock())

        self.assertEqual(response.scannerContextFrame["marketReadiness"]["readinessState"], "ready")
        self.assertEqual(response.scannerContextFrame["macroRegime"]["state"], "supportive")
        self.assertEqual(response.scannerContextFrame["liquidityFrame"]["state"], "supportive")
        self.assertEqual(response.scannerContextFrame["themeFrame"]["themes"][0]["id"], "ai")
        self.assertTrue(response.scannerContextFrame["noAdviceBoundary"])
        serialized = response.model_dump()
        self.assertEqual(serialized["scannerContextFrame"]["assetClassBias"]["state"], "supportive")
        self.assertEqual(serialized["scannerContextFrame"]["universePolicy"]["type"], "default")

    def test_run_market_scan_sanitizes_consumer_provider_diagnostics_in_response_model(self) -> None:
        service = MagicMock()
        payload = _make_run_payload()
        provider_observation = {
            "observationOnly": True,
            "scoreContributionAllowed": False,
            "entries": [
                {
                    "stage": "snapshot",
                    "capability": "cn_realtime_quote",
                    "providerName": "akshare",
                    "sourceType": "public_proxy",
                    "sourceTier": "unofficial_public_api",
                    "trustLevel": "weak",
                    "freshnessExpectation": "best_effort_realtime_quote_and_daily_history",
                    "observationOnly": True,
                    "scoreContributionAllowed": False,
                    "degradationReason": "fallback_source",
                    "rawProviderError": "Traceback (most recent call last): https://provider.example.test?token=secret",
                    "asOf": "2026-05-19T08:40:00+08:00",
                    "updatedAt": "2026-05-19T08:40:00+08:00",
                }
            ],
        }
        payload["shortlist"][0]["diagnostics"]["score_explainability"]["cap_reason"] = "fallback_source"
        payload["shortlist"][0]["diagnostics"]["score_explainability"]["degradation_reason"] = "fallback_source"
        payload["shortlist"][0]["diagnostics"]["score_explainability"]["score_confidence"] = 0.4
        payload["shortlist"][0]["diagnostics"]["score_explainability"]["source_confidence"] = {
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "observationOnly": True,
            "sourceType": "fallback_static",
            "capReason": "fallback_source",
            "degradationReason": "fallback_source",
        }
        payload["shortlist"][0]["diagnostics"]["cn_provider_observation"] = provider_observation
        payload["shortlist"][0]["diagnostics"]["evidence_packet"] = {
            "symbol": "600001",
            "capReason": "fallback_source",
            "degradationReason": "fallback_source",
            "userFacingLabels": ["仅供观察", "需人工复核"],
            "providerObservation": provider_observation,
        }
        payload["shortlist"][0]["consumerDiagnostics"] = {
            "status": "limited",
            "confidenceCategory": "low",
            "freshnessCategory": "fallback",
            "scoreGradeAllowed": False,
            "scoreConfidence": 0.4,
            "capReason": "fallback_source",
            "degradationReason": "fallback_source",
            "dataQualityState": "partial",
            "freshnessState": "fallback",
            "userFacingLabels": ["仅供观察", "需人工复核"],
            "warningFlags": ["仅供观察", "需人工复核"],
            "missingEvidence": [],
            "sourceClass": "fallback",
        }
        payload["candidates"] = [
            {
                "symbol": "600001",
                "name": "股票600001",
                "rank": 1,
                "status": "selected",
                "score": 79.0,
                "provider": "akshare",
                "reason": "passed",
                "failed_rules": [],
                "missing_fields": [],
                "metrics": {},
                "cn_provider_observation": provider_observation,
            }
        ]
        service.run_manual_scan.return_value = payload

        request = ScannerRunRequest(
            market="cn",
            profile="cn_preopen_v1",
            shortlist_size=5,
            universe_limit=300,
            detail_limit=60,
        )

        with patch("api.v1.endpoints.scanner.MarketScannerOperationsService", return_value=service):
            response = run_market_scan(request, db_manager=MagicMock())

        serialized = response.model_dump()
        self.assertEqual(serialized["shortlist"][0]["diagnostics"], {})
        self.assertEqual(serialized["shortlist"][0]["candidateSourceProvenanceFrame"], {})
        self.assertEqual(serialized["candidates"][0]["cn_provider_observation"], {})
        consumer_projection = serialized["shortlist"][0]["consumerDiagnostics"]
        self.assertEqual(consumer_projection["dataQualityState"], "partial")
        self.assertIn(consumer_projection["dataQualityState"], {"ready", "delayed", "cached", "partial", "no_evidence", "unavailable"})
        self.assertEqual(
            serialized["shortlist"][0]["noAdviceLabel"],
            "Observation-only research context; not investment advice.",
        )
        self.assertTrue(serialized["shortlist"][0]["evidenceBoundaries"]["noAdvice"])
        self.assertFalse(serialized["shortlist"][0]["evidenceBoundaries"]["decisionGrade"])
        self.assertEqual(
            serialized["shortlist"][0]["rankingConfidence"]["rankingUse"],
            "relative_observation_only",
        )
        self.assertEqual(serialized["shortlist"][0]["candidateResearchPacket"], {})
        _assert_no_forbidden_consumer_response_fields(serialized)

    def test_admin_gated_scanner_watchlist_keeps_diagnostics_for_admin_surface(self) -> None:
        service = MagicMock()
        payload = _make_run_payload()
        payload["shortlist"][0]["diagnostics"]["score_explainability"]["source_confidence"] = {
            "sourceType": "fallback_static",
            "isFallback": True,
            "scoreContributionAllowed": False,
            "observationOnly": True,
        }
        payload["shortlist"][0]["diagnostics"]["evidence_packet"] = {
            "providerObservation": {
                "entries": [
                    {
                        "providerName": "akshare",
                        "sourceType": "public_proxy",
                        "scoreContributionAllowed": False,
                    }
                ]
            }
        }
        service.get_today_watchlist.return_value = payload

        with patch("api.v1.endpoints.scanner.MarketScannerService", return_value=service):
            response = get_today_watchlist(market="cn", profile="cn_preopen_v1", db_manager=MagicMock(), _=MagicMock())

        serialized = response.model_dump()
        self.assertEqual(
            serialized["shortlist"][0]["diagnostics"]["score_explainability"]["source_confidence"]["sourceType"],
            "fallback_static",
        )
        self.assertEqual(
            serialized["shortlist"][0]["diagnostics"]["evidence_packet"]["providerObservation"]["entries"][0]["providerName"],
            "akshare",
        )

    def test_run_market_scan_preserves_additive_candidate_evidence_and_readiness_fields(self) -> None:
        service = MagicMock()
        payload = _make_run_payload(
            run_id=26,
            market="us",
            profile="us_preopen_v1",
            profile_label="US Pre-open Scanner v1",
            benchmark_code="SPY",
        )
        payload["shortlist"][0]["candidateEvidenceFrame"] = {
            "contractVersion": "scanner_candidate_evidence_v1",
            "coverageState": "partial",
            "domains": {
                "technicals": {"state": "available", "observationOnly": False, "scoreGradeAllowed": True},
                "fundamentals": {"state": "missing", "observationOnly": False, "scoreGradeAllowed": False},
                "newsCatalyst": {"state": "missing", "observationOnly": False, "scoreGradeAllowed": False},
            },
            "coverage": {
                "availableCount": 1,
                "partialCount": 0,
                "observeOnlyCount": 0,
                "missingCount": 2,
                "totalCount": 3,
            },
            "noAdviceBoundary": True,
        }
        payload["shortlist"][0]["candidateResearchReadiness"] = {
            "contractVersion": "research_readiness_v1",
            "researchReady": False,
            "readinessState": "insufficient",
            "verdictLabel": "证据不足",
            "blockingReasons": ["missing_required_evidence"],
            "missingEvidence": ["fundamentals", "news", "catalyst"],
            "evidenceCoverage": {
                "scoreGradeCount": 1,
                "observationOnlyCount": 0,
                "missingCount": 3,
                "totalCount": 4,
            },
            "sourceAuthority": "scoreGradeAllowed",
            "freshnessFloor": "delayed",
            "consumerActionBoundary": "no_advice",
            "nextEvidenceNeeded": ["补充基本面证据", "补充新闻证据", "补充催化剂证据"],
            "debugRef": "scanner:candidate:NVDA",
            "noAdviceBoundary": True,
        }
        payload["shortlist"][0]["candidateResearchSummaryFrame"] = {
            "contractVersion": "scanner_candidate_research_summary_v1",
            "frameState": "insufficient",
            "symbol": "NVDA",
            "rank": 1,
            "scoreBand": "medium",
            "primaryResearchReason": "趋势与量能支持继续研究。",
            "evidenceHighlights": ["Technicals available", "Liquidity available", "Trend structure available"],
            "missingEvidence": ["fundamentals", "news", "catalyst"],
            "blockingReasons": ["missing_required_evidence"],
            "topDownContextRefs": [
                {"key": "marketReadiness", "state": "ready", "label": "Top-down market context available"},
                {"key": "themeFrame", "state": "supportive", "label": "Theme leadership supports the shortlist"},
            ],
            "sourceAuthority": "scoreGradeAllowed",
            "freshness": "delayed",
            "nextResearchStep": "补充基本面证据",
            "noAdviceBoundary": True,
            "debugRef": "scanner:candidate_summary:NVDA",
        }
        payload["shortlist"][0]["candidateSourceProvenanceFrame"] = {
            "contractVersion": "source_provenance_v1",
            "entryCount": 1,
            "authorityTierCounts": {"observation_only": 1},
            "freshnessStateCounts": {"delayed": 1},
            "evidenceDomainCounts": {"market_data": 1},
            "fallbackOrProxyCount": 0,
            "observationOnlyCount": 1,
            "scoreContributionAllowedCount": 0,
            "entries": [
                {
                    "contractVersion": "source_provenance_v1",
                    "sourceId": "scanner_public_projection",
                    "sourceLabel": "Scanner public projection",
                    "evidenceDomain": "market_data",
                    "authorityTier": "observation_only",
                    "freshnessState": "delayed",
                    "sourceTier": "stored_snapshot",
                    "fallbackOrProxy": False,
                    "observationOnly": True,
                    "scoreContributionAllowed": False,
                    "limitations": ["observation_only"],
                    "nextEvidenceNeeded": ["score_grade_authority_source"],
                    "debugRef": "source-provenance:scanner-public-projection",
                }
            ],
        }
        service.run_manual_scan.return_value = payload

        request = ScannerRunRequest(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=5,
            universe_limit=180,
            detail_limit=40,
        )

        with patch("api.v1.endpoints.scanner.MarketScannerOperationsService", return_value=service):
            response = run_market_scan(request, db_manager=MagicMock())

        self.assertEqual(response.shortlist[0].candidateEvidenceFrame["contractVersion"], "scanner_candidate_evidence_v1")
        self.assertEqual(response.shortlist[0].candidateEvidenceFrame["domains"]["technicals"]["state"], "available")
        self.assertEqual(response.shortlist[0].candidateResearchReadiness["readinessState"], "insufficient")
        self.assertIn("fundamentals", response.shortlist[0].candidateResearchReadiness["missingEvidence"])
        self.assertEqual(
            response.shortlist[0].candidateResearchSummaryFrame["contractVersion"],
            "scanner_candidate_research_summary_v1",
        )
        self.assertEqual(response.shortlist[0].candidateResearchSummaryFrame["frameState"], "insufficient")
        serialized = response.model_dump()
        self.assertEqual(
            serialized["shortlist"][0]["candidateEvidenceFrame"]["coverage"]["missingCount"],
            2,
        )
        self.assertEqual(
            serialized["shortlist"][0]["candidateResearchReadiness"]["nextEvidenceNeeded"][0],
            "补充基本面证据",
        )
        self.assertEqual(
            serialized["shortlist"][0]["candidateResearchSummaryFrame"]["nextResearchStep"],
            "补充基本面证据",
        )
        self.assertEqual(serialized["shortlist"][0]["candidateSourceProvenanceFrame"], {})
        self.assertEqual([item["symbol"] for item in serialized["shortlist"]], ["NVDA", "AAPL"])
        provenance_json = json.dumps(serialized["shortlist"][0]["candidateSourceProvenanceFrame"], ensure_ascii=False).lower()
        for forbidden in ("token", "cookie", "session", "payload", "stack", "trace", "internal", "raw"):
            self.assertNotIn(forbidden, provenance_json)

    def test_public_candidate_dict_adds_consumer_diagnostics_projection(self) -> None:
        service = object.__new__(MarketScannerService)
        service.ai_service = MagicMock()
        service.ai_service.public_payload_from_diagnostics.return_value = {"available": False, "status": "skipped"}
        candidate = _make_candidate("600001", 1)
        diagnostics = dict(candidate.pop("diagnostics"))
        diagnostics["history"] = {
            "source": "local_partial_fallback",
            "latest_trade_date": "2026-05-08",
            "rows": 42,
            "partial_local_fallback": True,
            "stale": True,
        }
        diagnostics["quote_context"] = {
            "available": True,
            "source": "akshare",
            "sourceType": "public_proxy",
        }
        provider_observation = {
            "observationOnly": True,
            "scoreContributionAllowed": False,
            "entries": [
                {
                    "stage": "snapshot",
                    "capability": "cn_realtime_quote",
                    "providerName": "akshare",
                    "providerId": "akshare",
                    "sourceType": "public_proxy",
                    "sourceTier": "unofficial_public_api",
                    "trustLevel": "weak",
                    "observationOnly": True,
                    "scoreContributionAllowed": False,
                }
            ],
        }
        diagnostics["cn_provider_observation"] = provider_observation
        diagnostics["score_explainability"] = {
            "raw_score": 87.0,
            "final_score": 40.0,
            "cap_reason": "fallback_source",
            "degradation_reason": "fallback_source",
            "score_confidence": 0.4,
            "evidence_coverage": 1.0,
            "source_confidence": {
                "sourceAuthorityAllowed": False,
                "scoreContributionAllowed": False,
                "observationOnly": True,
                "sourceType": "fallback_static",
            },
        }
        candidate["_diagnostics"] = diagnostics
        candidate["_component_scores"] = {"trend": 18.0}
        diagnostics["evidence_packet"] = build_scanner_evidence_packet(
            candidate,
            {
                "market": "cn",
                "run_id": 99,
                "evidence_version": "scanner_evidence_v1",
                "score_explainability": diagnostics["score_explainability"],
            },
        )

        public_payload = service._public_candidate_dict(candidate)

        self.assertIn("diagnostics", public_payload)
        self.assertIn("consumerDiagnostics", public_payload)
        self.assertEqual(public_payload["diagnostics"]["cn_provider_observation"], provider_observation)
        self.assertEqual(public_payload["consumerDiagnostics"]["status"], "limited")
        self.assertFalse(public_payload["consumerDiagnostics"]["scoreGradeAllowed"])
        self.assertEqual(public_payload["consumerDiagnostics"]["scoreConfidence"], 0.4)
        self.assertEqual(public_payload["consumerDiagnostics"]["capReason"], "fallback_source")
        self.assertEqual(public_payload["consumerDiagnostics"]["sourceClass"], "fallback")
        investor_signal = public_payload["consumerDiagnostics"]["investorSignal"]
        self.assertEqual(investor_signal["contractVersion"], "investor_signal_contract_v1")
        self.assertFalse(investor_signal["sourceAuthorityAllowed"])
        self.assertEqual(investor_signal["freshness"], "fallback")
        self.assertEqual(investor_signal["confidenceLabel"], "blocked")
        self.assertIn("fallback_source", investor_signal["reasonCodes"])
        self.assertIn("source_authority_missing", investor_signal["reasonCodes"])

        projection_json = json.dumps(public_payload["consumerDiagnostics"], ensure_ascii=False)
        for forbidden in [
            "providerObservation",
            "cn_provider_observation",
            "providerName",
            "providerId",
            "akshare",
            "public_proxy",
            "cn_realtime_quote",
            "source_confidence",
            "sourceType",
            "sourceTier",
            "trustLevel",
            "adminReasonCodes",
        ]:
            self.assertNotIn(forbidden, projection_json)
        investor_signal_json = json.dumps(investor_signal, ensure_ascii=False)
        self.assertNotIn("source", investor_signal)
        self.assertNotIn("sourceType", investor_signal)
        for forbidden in ["providerName", "providerId", "akshare", "public_proxy"]:
            self.assertNotIn(forbidden, investor_signal_json)

    def test_get_scanner_themes_returns_registry_items(self) -> None:
        response = get_scanner_themes()

        self.assertGreaterEqual(len(response.items), 1)
        crypto = next(item for item in response.items if item.id == "crypto_miners")
        self.assertEqual(crypto.market, "us")
        self.assertIn("MARA", crypto.symbols)
        self.assertIn("BTDR", crypto.symbols)
        self.assertTrue(crypto.is_seed_list)
        self.assertIn("not an authoritative", crypto.description)

        ai_semis = next(item for item in response.items if item.id == "ai_semiconductors")
        self.assertEqual(ai_semis.market, "us")
        self.assertIn("ASML", ai_semis.symbols)

        cpo_cn = next(item for item in response.items if item.id == "optical_module_cpo_cn")
        self.assertEqual(cpo_cn.market, "cn")
        self.assertEqual(cpo_cn.symbols, [])
        self.assertTrue(cpo_cn.requires_manual_maintenance)

    def test_create_scanner_theme_generates_ai_backed_custom_universe(self) -> None:
        response = create_scanner_theme(
            ScannerThemeGenerateRequest(
                id="white_house_stocks_test",
                label="White House Stocks",
                market="us",
                prompt="Stocks associated with White House policy, federal contracts, and government decisions.",
            )
        )

        self.assertEqual(response.theme.id, "white_house_stocks_test")
        self.assertEqual(response.theme.market, "us")
        self.assertFalse(response.theme.is_seed_list)
        self.assertEqual(response.theme.source, "ai_generated")
        self.assertIn("PLTR", response.theme.symbols)
        self.assertGreaterEqual(len(response.suggestions), 1)
        self.assertIn("federal", response.message.lower())

        themes = get_scanner_themes(market="us")
        generated = next(item for item in themes.items if item.id == "white_house_stocks_test")
        self.assertIn("PLTR", generated.symbols)

    def test_create_scanner_theme_rejects_invalid_theme_id(self) -> None:
        with self.assertRaises(HTTPException) as context:
            create_scanner_theme(
                ScannerThemeGenerateRequest(
                    id="White House!",
                    label="White House Stocks",
                    market="us",
                    prompt="Stocks associated with White House policy and government decisions.",
                )
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail["error"], "validation_error")
        self.assertEqual(
            context.exception.detail["message"],
            "Scanner request could not be processed.",
        )
        self.assertNotIn("theme id", str(context.exception.detail).lower())

    def test_scanner_validation_error_does_not_expose_raw_exception_text(self) -> None:
        service = MagicMock()
        raw_error = r"database shard omega unavailable at C:\internal\worker.py"
        service.run_manual_scan.side_effect = ValueError(raw_error)
        request = ScannerRunRequest(
            market="cn",
            profile="cn_preopen_v1",
            shortlist_size=5,
            universe_limit=50,
            detail_limit=10,
        )

        with patch("api.v1.endpoints.scanner._build_scanner_ops_service", return_value=service):
            with self.assertRaises(HTTPException) as context:
                run_market_scan(request, db_manager=MagicMock())

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail["error"], "validation_error")
        self.assertEqual(
            context.exception.detail["message"],
            "Scanner request could not be processed.",
        )
        self.assertNotIn(raw_error, str(context.exception.detail))

    def test_run_market_scan_passes_theme_universe_request_to_service(self) -> None:
        service = MagicMock()
        service.run_manual_scan.return_value = _make_run_payload(
            run_id=30,
            market="us",
            profile="us_preopen_v1",
            profile_label="US Pre-open Scanner v1",
            benchmark_code="SPY",
        )

        request = ScannerRunRequest(
            market="us",
            profile="us_preopen_v1",
            universe_type="theme",
            theme_id="crypto_miners",
            shortlist_size=5,
            universe_limit=180,
            detail_limit=40,
        )

        with patch("api.v1.endpoints.scanner.MarketScannerOperationsService", return_value=service):
            response = run_market_scan(request, db_manager=MagicMock())

        self.assertEqual(response.id, 30)
        service.run_manual_scan.assert_called_once_with(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=5,
            universe_limit=180,
            detail_limit=40,
            universe_type="theme",
            theme_id="crypto_miners",
            symbols=[],
            request_source="api",
            notify=False,
        )

    def test_run_request_normalizes_custom_symbols(self) -> None:
        request = ScannerRunRequest(
            market="us",
            universe_type="symbols",
            symbols=[" mara ", "RIOT", "mara", "", "clsk"],
        )

        self.assertEqual(request.symbols, ["MARA", "RIOT", "CLSK"])

    def test_get_market_scan_runs_serializes_history(self) -> None:
        service = MagicMock()
        service.list_runs.return_value = {
            "total": 1,
            "page": 1,
            "limit": 10,
            "items": [
                {
                    "id": 12,
                    "market": "cn",
                    "profile": "cn_preopen_v1",
                    "profile_label": "A股盘前扫描 v1",
                    "status": "completed",
                    "run_at": "2026-04-13T08:30:00",
                    "completed_at": "2026-04-13T08:31:00",
                    "watchlist_date": "2026-04-13",
                    "trigger_mode": "scheduled",
                    "universe_name": "cn_a_liquid_watchlist_v1",
                    "shortlist_size": 2,
                    "universe_size": 300,
                    "preselected_size": 60,
                    "evaluated_size": 48,
                    "source_summary": "test",
                    "headline": "headline",
                    "top_symbols": ["600001", "600002"],
                    "notification_status": "success",
                    "failure_reason": None,
                    "change_summary": {
                        "available": True,
                        "previous_run_id": 11,
                        "previous_watchlist_date": "2026-04-10",
                        "new_count": 1,
                        "retained_count": 1,
                        "dropped_count": 1,
                        "new_symbols": [{"symbol": "600001", "name": "股票600001", "current_rank": 1, "previous_rank": None, "rank_delta": None}],
                        "retained_symbols": [{"symbol": "600002", "name": "股票600002", "current_rank": 2, "previous_rank": 1, "rank_delta": -1}],
                        "dropped_symbols": [{"symbol": "600003", "name": "股票600003", "current_rank": None, "previous_rank": 2, "rank_delta": None}],
                    },
                    "review_summary": {
                        "available": True,
                        "review_window_days": 3,
                        "review_status": "ready",
                        "candidate_count": 2,
                        "reviewed_count": 2,
                        "pending_count": 0,
                        "hit_rate_pct": 50.0,
                        "outperform_rate_pct": 50.0,
                        "avg_same_day_close_return_pct": 1.5,
                        "avg_review_window_return_pct": 2.2,
                        "avg_max_favorable_move_pct": 4.0,
                        "avg_max_adverse_move_pct": -1.8,
                        "strong_count": 1,
                        "mixed_count": 0,
                        "weak_count": 1,
                        "best_symbol": "600001",
                        "best_return_pct": 5.6,
                        "weakest_symbol": "600002",
                        "weakest_return_pct": -1.2,
                    },
                }
            ],
        }

        with patch("api.v1.endpoints.scanner.MarketScannerService", return_value=service):
            response = get_market_scan_runs(db_manager=MagicMock())

        self.assertEqual(response.total, 1)
        self.assertEqual(response.items[0].top_symbols, ["600001", "600002"])
        self.assertEqual(response.items[0].notification_status, "success")
        self.assertEqual(response.items[0].change_summary.new_count, 1)
        service.list_runs.assert_called_once()

    def test_get_scanner_strategy_simulation_uses_persisted_history_service(self) -> None:
        service = MagicMock()
        service.build_strategy_simulation.return_value = {
            "theme": "crypto_miners",
            "profile": "us_preopen_v1",
            "market": "us",
            "window": {"lookbackDays": 90, "forwardDays": 5, "runCount": 2},
            "status": "ready",
            "summary": {
                "historicalRuns": 2,
                "selectionEvents": 3,
                "avgSelectedPerRun": 1.5,
                "hitRate": 0.67,
                "avgForwardReturnPct": 3.2,
                "medianForwardReturnPct": 1.8,
                "avgBenchmarkReturnPct": 1.1,
                "avgExcessReturnPct": 2.1,
                "positiveSelectionRate": 0.67,
                "bestSymbol": "WULF",
                "worstSymbol": "MARA",
                "dataCoverage": 1.0,
            },
            "runs": [
                {
                    "runId": 12,
                    "runAt": "2026-05-01T08:45:00",
                    "selectedCount": 1,
                    "rejectedCount": 10,
                    "selectedSymbols": ["WULF"],
                    "avgForwardReturnPct": 2.5,
                    "benchmarkReturnPct": 0.8,
                    "excessReturnPct": 1.7,
                }
            ],
            "symbols": [
                {
                    "symbol": "WULF",
                    "selectionCount": 2,
                    "avgScore": 62.0,
                    "avgForwardReturnPct": 4.4,
                    "hitRate": 0.5,
                    "bestForwardReturnPct": 12.1,
                    "worstForwardReturnPct": -6.2,
                }
            ],
            "warnings": [],
        }

        with patch("api.v1.endpoints.scanner.MarketScannerService", return_value=service):
            response = get_scanner_strategy_simulation(
                theme="crypto_miners",
                profile="us_preopen_v1",
                market="us",
                lookback_days=90,
                forward_days=5,
                limit=50,
                db_manager=MagicMock(),
            )

        self.assertEqual(response.status, "ready")
        self.assertEqual(response.window.run_count, 2)
        self.assertEqual(response.summary.avg_forward_return_pct, 3.2)
        self.assertEqual(response.runs[0].selected_symbols, ["WULF"])
        self.assertEqual(response.symbols[0].best_forward_return_pct, 12.1)
        service.build_strategy_simulation.assert_called_once()

    def test_get_market_scan_run_returns_404_when_missing(self) -> None:
        service = MagicMock()
        service.get_run_detail.return_value = None

        with patch("api.v1.endpoints.scanner.MarketScannerService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                get_market_scan_run(999, db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["error"], "not_found")

    def test_get_market_scan_run_sanitizes_failure_details_and_preserves_context_frame(self) -> None:
        service = MagicMock()
        payload = _make_run_payload()
        raw_error = r"provider token secret-value at C:\internal\scanner_worker.py"
        payload["status"] = "failed"
        payload["shortlist"] = []
        payload["selected"] = []
        payload["failure_reason"] = raw_error
        payload["diagnostics"]["failure"] = {
            "message": raw_error,
            "updated_at": "2026-04-13T08:31:00",
        }
        payload["notification"] = {
            "attempted": True,
            "status": "failed",
            "success": False,
            "channels": ["feishu"],
            "message": raw_error,
            "report_path": "/private/tmp/scanner_watchlist.md",
            "sent_at": "2026-04-13T08:31:00",
        }
        payload["scannerContextFrame"] = {
            "marketReadiness": {
                "contractVersion": "research_readiness_v1",
                "researchReady": False,
                "market": "cn",
                "universeType": "default",
                "readinessState": "blocked",
                "verdictLabel": "研究结论受限",
                "blockingReasons": [
                    "no_realtime_snapshot_available",
                    "akshare_snapshot_fetch_failed",
                ],
                "missingEvidence": ["technical", "freshness"],
                "evidenceCoverage": {
                    "scoreGradeCount": 0,
                    "observationOnlyCount": 0,
                    "missingCount": 2,
                    "totalCount": 2,
                },
                "sourceAuthority": "unavailable",
                "providerAuthority": "unavailable",
                "freshnessFloor": "unknown",
                "freshness": "unavailable",
                "sourceTier": "unavailable",
                "consumerActionBoundary": "no_advice",
                "nextEvidenceNeeded": ["补充技术面证据", "补充新鲜度证据"],
                "noAdviceBoundary": True,
                "debugRef": "scanner:12:cn_runtime",
            },
            "universePolicy": {
                "type": "default",
                "label": "Profile default universe",
                "reason": "scanner_profile_default_universe",
            },
            "noAdviceBoundary": True,
        }
        service.get_run_detail.return_value = payload

        with patch("api.v1.endpoints.scanner.MarketScannerService", return_value=service):
            response = get_market_scan_run(12, db_manager=MagicMock())

        self.assertEqual(response.status, "failed")
        self.assertEqual(
            response.failure_reason,
            "Scanner execution failed. Review readiness and retry.",
        )
        self.assertEqual(response.notification.message, "Scanner notification failed.")
        self.assertIsNone(response.notification.report_path)
        self.assertEqual(response.scannerContextFrame["marketReadiness"]["readinessState"], "blocked")
        self.assertEqual(response.scannerContextFrame["marketReadiness"]["providerAuthority"], "unavailable")
        self.assertEqual(response.scannerContextFrame["marketReadiness"]["freshness"], "unavailable")
        self.assertTrue(response.scannerContextFrame["marketReadiness"]["noAdviceBoundary"])
        self.assertNotIn(raw_error, json.dumps(response.model_dump(), ensure_ascii=False))
        self.assertNotIn("/private/tmp/scanner_watchlist.md", json.dumps(response.model_dump(), ensure_ascii=False))

    def test_get_today_watchlist_returns_404_when_missing(self) -> None:
        service = MagicMock()
        service.get_today_watchlist.return_value = None

        with patch("api.v1.endpoints.scanner.MarketScannerService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                get_today_watchlist(db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["error"], "not_found")

    def test_get_recent_watchlists_serializes_daily_history(self) -> None:
        service = MagicMock()
        service.list_recent_watchlists.return_value = {
            "total": 1,
            "page": 1,
            "limit": 7,
            "items": [
                {
                    "id": 12,
                    "market": "cn",
                    "profile": "cn_preopen_v1",
                    "profile_label": "A股盘前扫描 v1",
                    "status": "completed",
                    "run_at": "2026-04-13T08:40:00",
                    "completed_at": "2026-04-13T08:41:00",
                    "watchlist_date": "2026-04-13",
                    "trigger_mode": "scheduled",
                    "universe_name": "cn_a_liquid_watchlist_v1",
                    "shortlist_size": 2,
                    "universe_size": 300,
                    "preselected_size": 60,
                    "evaluated_size": 48,
                    "source_summary": "scanner=daily",
                    "headline": "今日 A 股盘前优先观察：600001 / 600002",
                    "top_symbols": ["600001", "600002"],
                    "notification_status": "success",
                    "failure_reason": None,
                    "change_summary": {
                        "available": True,
                        "previous_run_id": 11,
                        "previous_watchlist_date": "2026-04-10",
                        "new_count": 1,
                        "retained_count": 1,
                        "dropped_count": 1,
                        "new_symbols": [{"symbol": "600001", "name": "股票600001", "current_rank": 1, "previous_rank": None, "rank_delta": None}],
                        "retained_symbols": [{"symbol": "600002", "name": "股票600002", "current_rank": 2, "previous_rank": 1, "rank_delta": -1}],
                        "dropped_symbols": [{"symbol": "600003", "name": "股票600003", "current_rank": None, "previous_rank": 2, "rank_delta": None}],
                    },
                    "review_summary": {
                        "available": True,
                        "review_window_days": 3,
                        "review_status": "ready",
                        "candidate_count": 2,
                        "reviewed_count": 2,
                        "pending_count": 0,
                        "hit_rate_pct": 50.0,
                        "outperform_rate_pct": 50.0,
                        "avg_same_day_close_return_pct": 1.5,
                        "avg_review_window_return_pct": 2.2,
                        "avg_max_favorable_move_pct": 4.0,
                        "avg_max_adverse_move_pct": -1.8,
                        "strong_count": 1,
                        "mixed_count": 0,
                        "weak_count": 1,
                        "best_symbol": "600001",
                        "best_return_pct": 5.6,
                        "weakest_symbol": "600002",
                        "weakest_return_pct": -1.2,
                    },
                }
            ],
        }

        with patch("api.v1.endpoints.scanner.MarketScannerService", return_value=service):
            response = get_recent_watchlists(db_manager=MagicMock())

        self.assertEqual(response.total, 1)
        self.assertEqual(response.items[0].watchlist_date, "2026-04-13")
        self.assertEqual(response.items[0].trigger_mode, "scheduled")
        self.assertEqual(response.items[0].notification_status, "success")
        self.assertEqual(response.items[0].review_summary.review_status, "ready")
        service.list_recent_watchlists.assert_called_once()

    def test_get_recent_watchlists_supports_us_profile_filters(self) -> None:
        service = MagicMock()
        service.list_recent_watchlists.return_value = {
            "total": 1,
            "page": 1,
            "limit": 5,
            "items": [
                {
                    "id": 22,
                    "market": "us",
                    "profile": "us_preopen_v1",
                    "profile_label": "US Pre-open Scanner v1",
                    "status": "completed",
                    "run_at": "2026-04-13T21:20:00",
                    "completed_at": "2026-04-13T21:21:00",
                    "watchlist_date": "2026-04-13",
                    "trigger_mode": "scheduled",
                    "universe_name": "us_preopen_watchlist_v1",
                    "shortlist_size": 2,
                    "universe_size": 180,
                    "preselected_size": 40,
                    "evaluated_size": 32,
                    "source_summary": "us_history=local",
                    "headline": "今日美股盘前优先观察：NVDA / AAPL",
                    "top_symbols": ["NVDA", "AAPL"],
                    "notification_status": "success",
                    "failure_reason": None,
                    "change_summary": {
                        "available": False,
                        "previous_run_id": None,
                        "previous_watchlist_date": None,
                        "new_count": 0,
                        "retained_count": 0,
                        "dropped_count": 0,
                        "new_symbols": [],
                        "retained_symbols": [],
                        "dropped_symbols": [],
                    },
                    "review_summary": {
                        "available": True,
                        "review_window_days": 3,
                        "review_status": "ready",
                        "candidate_count": 2,
                        "reviewed_count": 2,
                        "pending_count": 0,
                        "hit_rate_pct": 50.0,
                        "outperform_rate_pct": 50.0,
                        "avg_same_day_close_return_pct": 1.1,
                        "avg_review_window_return_pct": 2.8,
                        "avg_max_favorable_move_pct": 4.7,
                        "avg_max_adverse_move_pct": -2.0,
                        "strong_count": 1,
                        "mixed_count": 1,
                        "weak_count": 0,
                        "best_symbol": "NVDA",
                        "best_return_pct": 4.9,
                        "weakest_symbol": "AAPL",
                        "weakest_return_pct": 0.7,
                    },
                }
            ],
        }

        with patch("api.v1.endpoints.scanner.MarketScannerService", return_value=service):
            response = get_recent_watchlists(
                market="us",
                profile="us_preopen_v1",
                limit_days=5,
                db_manager=MagicMock(),
            )

        self.assertEqual(response.items[0].market, "us")
        self.assertEqual(response.items[0].profile, "us_preopen_v1")
        service.list_recent_watchlists.assert_called_once_with(
            market="us",
            profile="us_preopen_v1",
            limit_days=5,
        )

    def test_get_scanner_operational_status_serializes_status_summary(self) -> None:
        service = MagicMock()
        service.get_operational_status.return_value = _make_operational_status_payload()

        with patch("api.v1.endpoints.scanner.MarketScannerOperationsService", return_value=service):
            response = get_scanner_operational_status(db_manager=MagicMock())

        self.assertTrue(response.schedule_enabled)
        self.assertEqual(response.schedule_time, "08:40")
        self.assertEqual(response.today_watchlist.id, 12)
        self.assertEqual(response.last_manual_run.trigger_mode, "manual")
        self.assertTrue(response.quality_summary.available)
        self.assertEqual(response.quality_summary.run_count, 5)
        self.assertEqual(response.dataReadiness["state"], "not_run")
        self.assertEqual(response.dataReadiness["blockerBucket"], "unknown")
        service.get_operational_status.assert_called_once()


if __name__ == "__main__":
    unittest.main()
