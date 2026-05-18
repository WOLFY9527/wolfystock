# -*- coding: utf-8 -*-
"""Tests for scanner evidence packet diagnostics."""

from __future__ import annotations

import json

from src.services.scanner_evidence_packet import build_scanner_evidence_packet


def _candidate_fixture() -> dict:
    return {
        "symbol": "PLTR",
        "name": "Palantir",
        "market": "us",
        "rank": 1,
        "score": 81.6,
        "price": 27.4,
        "change_pct": 7.03,
        "ret_5d": 6.8,
        "ret_20d": 18.4,
        "ret_60d": 36.2,
        "amount": 7.67e8,
        "avg_amount_20": 7.6e8,
        "avg_volume_20": 34_000_000,
        "volume_expansion_20": 1.7,
        "atr20_pct": 4.8,
        "distance_to_20d_high_pct": -1.2,
        "quote_available": False,
        "_relative_strength_pct": 0.92,
        "_matched_sectors": ["AI软件"],
        "boards": ["AI软件", "国防科技"],
        "reasons": ["20 日趋势保持上行。", "量能扩张支撑突破观察。"],
        "risk_notes": ["缺少实时竞价确认，需人工复核。"],
        "_component_scores": {
            "trend": 18.5,
            "momentum": 13.2,
            "liquidity": 14.0,
            "activity": 10.4,
            "volatility_quality": 6.6,
            "relative_strength": 9.2,
            "benchmark_relative": 7.1,
            "gap_context": 4.0,
            "penalties": 1.0,
        },
        "_diagnostics": {
            "history": {
                "source": "local_partial_fallback",
                "latest_trade_date": "2026-05-08",
                "rows": 42,
                "partial_local_fallback": True,
                "network_failed": True,
                "stale": True,
            },
            "quote_context": {
                "available": False,
                "source": "synthetic",
                "gap_pct": None,
            },
            "benchmark_code": "SPY",
            "profile": "us_preopen_v1",
        },
    }


def test_build_scanner_evidence_packet_maps_missing_and_internal_terms_to_safe_labels() -> None:
    packet = build_scanner_evidence_packet(
        _candidate_fixture(),
        {
            "market": "us",
            "run_id": 42,
            "evidence_version": "scanner_evidence_v1",
            "score_explainability": {
                "raw_score": 81.6,
                "final_score": 40.0,
                "cap_reason": "fallback_source",
                "degradation_reason": "fallback_source",
                "score_confidence": 0.4,
                "evidence_coverage": 1.0,
            },
            "internal_reason_codes": [
                "not_enough_history",
                "optional_news_timeout",
                "fundamentals_unavailable",
                "provider_timeout",
            ],
        },
    )

    assert packet["symbol"] == "PLTR"
    assert packet["market"] == "us"
    assert packet["rank"] == 1
    assert packet["score"] == 40.0
    assert packet["rawScore"] == 81.6
    assert packet["finalScore"] == 40.0
    assert packet["capReason"] == "fallback_source"
    assert packet["degradationReason"] == "fallback_source"
    assert packet["scoreConfidence"] == 0.4
    assert packet["evidenceVersion"] == "scanner_evidence_v1"
    assert packet["runId"] == 42
    assert packet["freshnessState"] == "fallback"
    assert packet["dataQualityState"] == "partial"
    assert packet["userFacingLabels"] == [
        "历史数据不足",
        "部分外部数据暂不可用",
        "仅供观察",
        "需人工复核",
        "依据需复核",
    ]
    assert packet["adminReasonCodes"] == [
        "history_insufficient",
        "history_stale",
        "provider_unavailable",
        "external_optional_unavailable",
        "fundamental_context_unavailable",
    ]

    serialized = json.dumps(packet, ensure_ascii=False)
    for forbidden in [
        "provider_timeout",
        "not_enough_history",
        "fundamentals_unavailable",
        "optional_news_timeout",
        "debug",
        "schema",
        "trace",
        "MarketCache",
        "local_db",
        "generatedCandidates",
        "failedCandidates",
        "fixture",
        "mock",
    ]:
        assert forbidden not in serialized


def test_build_scanner_evidence_packet_preserves_supported_evidence_buckets_without_raw_payloads() -> None:
    packet = build_scanner_evidence_packet(
        _candidate_fixture(),
        {
            "market": "us",
            "run_id": 7,
            "evidence_version": "scanner_evidence_v1",
            "score_explainability": {
                "raw_score": 81.6,
                "final_score": 40.0,
                "cap_reason": "fallback_source",
                "degradation_reason": "fallback_source",
                "score_confidence": 0.4,
                "evidence_coverage": 1.0,
            },
        },
    )

    assert packet["trendEvidence"]["state"] == "complete"
    assert packet["momentumEvidence"]["state"] == "complete"
    assert packet["volumeEvidence"]["state"] == "complete"
    assert packet["volatilityRiskEvidence"]["state"] == "complete"
    assert packet["liquidityEvidence"]["state"] == "complete"
    assert packet["relativeStrengthEvidence"]["state"] == "complete"
    assert packet["sectorThemeContext"]["state"] == "complete"
    assert packet["missingEvidence"] == []
    assert packet["warningFlags"] == ["仅供观察", "需人工复核", "依据需复核"]
    assert packet["freshnessDetail"]["quoteState"] == "fallback"
    assert packet["freshnessDetail"]["historyState"] == "stale"
    assert packet["rawScore"] == 81.6
    assert packet["finalScore"] == 40.0
