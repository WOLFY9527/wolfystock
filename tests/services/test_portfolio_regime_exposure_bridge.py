# -*- coding: utf-8 -*-
"""Contract tests for portfolio/regime exposure bridge synthesis."""

from __future__ import annotations

import copy
import json
from typing import Any

from src.services.portfolio_regime_exposure_bridge import (
    PORTFOLIO_REGIME_EXPOSURE_BRIDGE_VERSION,
    build_portfolio_regime_exposure_bridge,
)


def _portfolio_context(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "dominantExposure": {
            "type": "theme",
            "themeId": "ai_applications",
            "label": "AI Applications",
            "market": "US",
            "weightPct": 42.0,
        },
        "concentrationContext": {
            "state": "observable",
            "topWeightPct": 42.0,
            "alert": False,
        },
        "marketContext": {
            "state": "observable",
            "largestMarket": {"market": "US", "label": "US", "weightPct": 78.0},
            "benchmarkMappingState": "mapped",
            "factorMappingState": "mapped",
        },
        "staleInputs": [],
        "evidenceGaps": [],
        "researchNextSteps": [],
    }
    payload.update(overrides)
    return payload


def _risk_supportive_regime(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contractVersion": "market_regime_synthesis_research_v1",
        "primaryRegime": "risk_on_liquidity_expansion",
        "regimePosture": "risk_supportive",
        "confidence": 0.74,
        "confidenceLabel": "medium",
        "confidenceCap": {"value": 0.74, "label": "medium", "reasons": ["bounded_research_synthesis"]},
        "supportiveEvidence": [{"family": "breadth", "label": "Breadth confirmation", "observationOnly": True}],
        "contradictoryEvidence": [],
        "missingEvidence": [],
        "freshness": "fresh",
    }
    payload.update(overrides)
    return payload


def _broad_theme_snapshot(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contractVersion": "theme_correlation_breadth_snapshot_v1",
        "theme": {"id": "ai_applications", "name": "AI Applications", "market": "US"},
        "participationState": "broad_group",
        "leadershipConcentration": {"state": "balanced", "percent": 38.0, "topMembers": ["APP", "PLTR"]},
        "correlationEvidence": {"state": "aligned", "sameDirectionPercent": 82.0, "aboveVwapPercent": 75.0},
        "breadthEvidence": {"state": "broad", "percentUp": 84.0, "percentOutperformingBenchmark": 68.0},
        "staleInputs": [],
        "missingInputs": [],
    }
    payload.update(overrides)
    return payload


def _serialize(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def test_portfolio_exposure_aligned_with_regime_returns_aligned() -> None:
    result = build_portfolio_regime_exposure_bridge(
        {
            "portfolioExposureResearchContext": _portfolio_context(),
            "marketRegimeSynthesis": _risk_supportive_regime(),
            "themeCorrelationBreadthSnapshot": _broad_theme_snapshot(),
        }
    )

    assert result["contractVersion"] == PORTFOLIO_REGIME_EXPOSURE_BRIDGE_VERSION
    assert result["bridgeState"] == "aligned"
    assert result["portfolioScope"]["hasPortfolioContext"] is True
    assert result["dominantExposureContext"]["themeId"] == "ai_applications"
    assert result["regimeAlignmentEvidence"]["state"] == "aligned"
    assert result["themeBreadthExposureEvidence"]["state"] == "aligned"
    assert result["concentrationEvidence"]["state"] == "observable"
    assert result["confidenceCap"]["label"] == "medium"
    assert result["observationBoundary"] == {
        "observationOnly": True,
        "decisionGrade": False,
        "externalCalls": "none",
        "networkCalls": "none",
        "llmCalls": "none",
        "dataFetches": "none",
        "dataMutation": "none",
        "portfolioAccountingMutation": False,
        "consumerActionBoundary": "no_advice",
    }


def test_concentrated_exposure_with_weak_theme_breadth_returns_concentrated_diverging_evidence() -> None:
    result = build_portfolio_regime_exposure_bridge(
        {
            "portfolioExposureResearchContext": _portfolio_context(
                dominantExposure={
                    "type": "theme",
                    "themeId": "ai_applications",
                    "label": "AI Applications",
                    "weightPct": 68.0,
                },
                concentrationContext={"state": "elevated", "topWeightPct": 68.0, "alert": True},
            ),
            "marketRegimeSynthesis": _risk_supportive_regime(),
            "themeCorrelationBreadthSnapshot": _broad_theme_snapshot(
                participationState="leader_concentrated",
                leadershipConcentration={"state": "concentrated", "percent": 72.0, "topMembers": ["NVDA", "AVGO"]},
                correlationEvidence={"state": "weak", "sameDirectionPercent": 42.0, "aboveVwapPercent": 35.0},
                breadthEvidence={"state": "thin", "percentUp": 48.0, "percentOutperformingBenchmark": 32.0},
            ),
        }
    )

    assert result["bridgeState"] == "concentrated"
    assert result["concentrationEvidence"]["state"] == "concentrated"
    assert result["themeBreadthExposureEvidence"]["state"] == "diverging"
    assert result["themeBreadthExposureEvidence"]["breadthState"] == "thin"
    assert "thin_theme_participation" in result["confidenceCap"]["reasons"]
    assert any(step["key"] == "verify_theme_participation" for step in result["researchNextSteps"])


def test_missing_regime_or_portfolio_context_returns_insufficient_evidence() -> None:
    missing_regime = build_portfolio_regime_exposure_bridge(
        {"portfolioExposureResearchContext": _portfolio_context(), "themeCorrelationBreadthSnapshot": _broad_theme_snapshot()}
    )
    missing_portfolio = build_portfolio_regime_exposure_bridge(
        {"marketRegimeSynthesis": _risk_supportive_regime(), "themeCorrelationBreadthSnapshot": _broad_theme_snapshot()}
    )

    for result in (missing_regime, missing_portfolio):
        assert result["bridgeState"] == "insufficient_evidence"
        assert result["missingInputs"]
        assert result["confidenceCap"]["label"] == "insufficient"
        assert result["confidenceCap"]["value"] <= 0.35


def test_stale_inputs_are_represented_and_cap_confidence() -> None:
    result = build_portfolio_regime_exposure_bridge(
        {
            "portfolioExposureResearchContext": _portfolio_context(
                staleInputs=[{"input": "portfolio_snapshot", "status": "stale", "reason": "cached"}],
            ),
            "marketRegimeSynthesis": _risk_supportive_regime(
                freshness="stale",
                confidence=0.8,
                confidenceCap={"value": 0.7, "label": "medium", "reasons": ["bounded_research_synthesis"]},
            ),
            "themeCorrelationBreadthSnapshot": _broad_theme_snapshot(staleInputs=["stale_source"]),
        }
    )

    assert result["staleInputs"] == [
        {"input": "portfolio_snapshot", "status": "stale", "reason": "cached"},
        {"input": "market_regime_synthesis", "status": "stale", "reason": "freshness_limited"},
        {"input": "theme_correlation_breadth", "status": "stale", "reason": "stale_source"},
    ]
    assert result["confidenceCap"]["label"] == "low"
    assert result["confidenceCap"]["value"] <= 0.4
    assert "stale_inputs" in result["confidenceCap"]["reasons"]


def test_raw_diagnostics_adversarial_values_are_dropped() -> None:
    packet = {
        "portfolioExposureResearchContext": _portfolio_context(
            providerDiagnostics={"requestId": "REQ-RAW-1", "trace": "raw provider trace"},
            dominantExposure={
                "type": "theme",
                "themeId": "ai_applications",
                "label": "provider debug says buy now",
                "sourceRef": "sourceRef-secret",
                "weightPct": 42.0,
            },
        ),
        "marketRegimeSynthesis": _risk_supportive_regime(
            raw_payload={"provider": "debug-provider"},
            requestId="REQ-RAW-2",
            trace="trace-secret",
            supportiveEvidence=[
                {"label": "Clean breadth evidence", "reasonCode": "provider_timeout", "sourceRef": "source-secret"}
            ],
        ),
        "themeCorrelationBreadthSnapshot": _broad_theme_snapshot(
            adminDiagnostics={"providerTrace": "trace-secret"},
            sourceRef="source-secret",
        ),
    }

    serialized = _serialize(build_portfolio_regime_exposure_bridge(packet)).lower()

    for forbidden in (
        "providerdiagnostics",
        "provider",
        "raw_payload",
        "requestid",
        "source_ref",
        "sourceref",
        "reasoncode",
        "trace-secret",
        "req-raw",
        "buy now",
        "debug-provider",
    ):
        assert forbidden not in serialized


def test_input_packet_is_not_mutated() -> None:
    packet = {
        "portfolioExposureResearchContext": _portfolio_context(),
        "marketRegimeSynthesis": _risk_supportive_regime(),
        "themeCorrelationBreadthSnapshot": _broad_theme_snapshot(),
    }
    original = copy.deepcopy(packet)

    build_portfolio_regime_exposure_bridge(packet)

    assert packet == original


def test_serialized_output_contains_no_actionable_advice_vocabulary() -> None:
    result = build_portfolio_regime_exposure_bridge(
        {
            "portfolioExposureResearchContext": _portfolio_context(
                researchNextSteps=[
                    {"topic": "unsafe", "check": "sell now and use target price stop loss"},
                    {"topic": "safe", "check": "Review member-level evidence before expanding conclusions."},
                ]
            ),
            "marketRegimeSynthesis": _risk_supportive_regime(),
            "themeCorrelationBreadthSnapshot": _broad_theme_snapshot(),
            "watchlistExposureNotes": [
                {"note": "buy more", "summary": "Compare watchlist evidence breadth."},
            ],
        }
    )

    serialized = _serialize(result).lower()
    for forbidden in (
        "buy",
        "sell",
        "rebalance",
        "position sizing",
        "target price",
        "stop loss",
        "reduce",
        "add exposure",
        "allocation instruction",
        "trade recommendation",
        "investment advice",
    ):
        assert forbidden not in serialized
