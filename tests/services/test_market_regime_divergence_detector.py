# -*- coding: utf-8 -*-
"""Focused tests for market regime divergence detection."""

from __future__ import annotations

import copy
import json

from src.services.market_regime_divergence_detector import detect_market_regime_divergence


def _aligned_packet() -> dict:
    return {
        "marketRegimeSynthesis": {
            "primaryRegime": "risk_on_liquidity_expansion",
            "regimePosture": "risk_supportive",
            "riskAppetite": 0.62,
            "breadthHealth": 0.54,
            "liquidityImpulse": 0.48,
            "confidence": 0.74,
            "freshness": "fresh",
            "missingEvidence": [],
        },
        "themeCorrelationBreadthSnapshot": {
            "participationState": "broad_group",
            "leadershipConcentration": {
                "state": "balanced",
                "percent": 38.0,
                "broadParticipationPercent": 62.0,
            },
            "correlationEvidence": {"state": "aligned"},
            "breadthEvidence": {
                "state": "broad",
                "percentUp": 83.3,
                "percentOutperformingBenchmark": 66.7,
            },
            "staleInputs": [],
            "missingInputs": [],
        },
        "liquidityImpulseSynthesis": {
            "classification": "expanding_liquidity",
            "liquidityImpulse": 0.52,
            "confidence": 0.7,
            "freshness": "fresh",
            "missingEvidence": [],
        },
        "scannerEvidencePacket": {
            "dataQualityState": "complete",
            "freshnessState": "fresh",
            "scoreConfidence": 0.82,
            "evidenceCoverage": 0.9,
            "missingEvidence": [],
            "warningFlags": [],
        },
    }


def test_aligned_packet_returns_aligned_contract() -> None:
    result = detect_market_regime_divergence(_aligned_packet())

    assert result["contractVersion"] == "market_regime_divergence_detector_v1"
    assert result["divergenceState"] == "aligned"
    assert result["divergenceFamilies"] == []
    assert result["staleInputs"] == []
    assert result["missingInputs"] == []
    assert result["confidenceCap"] >= 0.7
    assert result["observationBoundary"] == {
        "observationOnly": True,
        "decisionGrade": False,
        "scoreImpact": "none",
        "dataFetches": "none",
        "dataMutation": "none",
        "actionBoundary": "observation_only",
    }
    assert result["confirmingEvidence"]
    assert result["contradictoryEvidence"] == []
    assert result["researchNextSteps"] == ["Continue monitoring whether the aligned evidence persists in later observations."]


def test_index_strength_with_weak_breadth_returns_diverging_family() -> None:
    packet = _aligned_packet()
    packet["marketRegimeSynthesis"]["breadthHealth"] = -0.58
    packet["marketBreadthEvidence"] = {
        "state": "weak",
        "percentUp": 34.0,
        "percentOutperformingBenchmark": 31.0,
        "freshness": "fresh",
    }

    result = detect_market_regime_divergence(packet)

    assert result["divergenceState"] == "diverging"
    assert "index_vs_breadth" in result["divergenceFamilies"]
    assert any(item["family"] == "index_vs_breadth" for item in result["contradictoryEvidence"])
    assert result["confidenceCap"] <= 0.66


def test_theme_leadership_with_weak_participation_returns_diverging_family() -> None:
    packet = _aligned_packet()
    packet["themeCorrelationBreadthSnapshot"] = {
        "participationState": "leader_concentrated",
        "leadershipConcentration": {
            "state": "concentrated",
            "percent": 72.0,
            "broadParticipationPercent": 28.0,
        },
        "correlationEvidence": {"state": "mixed"},
        "breadthEvidence": {
            "state": "thin",
            "percentUp": 50.0,
            "percentOutperformingBenchmark": 33.3,
        },
        "staleInputs": [],
        "missingInputs": [],
    }

    result = detect_market_regime_divergence(packet)

    assert result["divergenceState"] == "diverging"
    assert "theme_leadership_vs_participation" in result["divergenceFamilies"]
    assert any(item["family"] == "theme_leadership_vs_participation" for item in result["contradictoryEvidence"])


def test_missing_or_stale_inputs_return_insufficient_or_capped_confidence() -> None:
    packet = {
        "marketRegimeSynthesis": {
            "primaryRegime": "risk_on_liquidity_expansion",
            "regimePosture": "risk_supportive",
            "riskAppetite": 0.62,
            "breadthHealth": 0.5,
            "freshness": "stale",
            "missingEvidence": ["rates_pressure"],
        },
        "themeCorrelationBreadthSnapshot": {
            "participationState": "insufficient_evidence",
            "staleInputs": ["fallback_source"],
            "missingInputs": ["market_runtime_evidence"],
        },
    }

    result = detect_market_regime_divergence(packet)

    assert result["divergenceState"] == "insufficient_evidence"
    assert "freshness_gap" in result["divergenceFamilies"]
    assert result["confidenceCap"] <= 0.35
    assert result["staleInputs"] == ["marketRegimeSynthesis", "themeCorrelationBreadthSnapshot"]
    assert "liquidityImpulseSynthesis" in result["missingInputs"]
    assert "scannerEvidencePacket" in result["missingInputs"]


def test_raw_provider_debug_request_trace_and_source_ref_data_are_dropped() -> None:
    packet = _aligned_packet()
    packet["rawPayload"] = {"providerName": "akshare", "debug": "leak-me"}
    packet["requestId"] = "req-secret"
    packet["traceId"] = "trace-secret"
    packet["sourceRefId"] = "source-ref-secret"
    packet["marketRegimeSynthesis"]["sourceRef"] = "source-ref-secret"
    packet["scannerEvidencePacket"]["providerObservation"] = {
        "providerName": "akshare",
        "rawError": "network timeout",
    }

    serialized = json.dumps(detect_market_regime_divergence(packet), ensure_ascii=False, sort_keys=True)

    for forbidden in [
        "akshare",
        "leak-me",
        "req-secret",
        "trace-secret",
        "source-ref-secret",
        "providerName",
        "providerObservation",
        "rawPayload",
        "rawError",
        "debug",
        "traceId",
        "requestId",
        "sourceRef",
    ]:
        assert forbidden not in serialized


def test_no_trade_instruction_vocabulary_in_serialized_output() -> None:
    result = detect_market_regime_divergence(_aligned_packet())
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True).lower()

    for forbidden in [
        "buy now",
        "sell now",
        "place order",
        "trade recommendation",
        "trading advice",
        "investment advice",
        "target price",
        "stop loss",
        "take profit",
        "position sizing",
        "risk-on instruction",
        "risk-off instruction",
        "买入",
        "卖出",
        "交易建议",
        "投资建议",
        "止损",
        "止盈",
        "目标价",
        "仓位建议",
    ]:
        assert forbidden not in serialized


def test_input_packet_is_not_mutated() -> None:
    packet = _aligned_packet()
    before = copy.deepcopy(packet)

    detect_market_regime_divergence(packet)

    assert packet == before
