# -*- coding: utf-8 -*-
"""Contract tests for bounded theme correlation/breadth snapshots."""

from __future__ import annotations

from datetime import datetime, timezone

from src.services.market_rotation_radar_service import MarketRotationRadarService
from src.services.theme_correlation_breadth_snapshot import (
    THEME_CORRELATION_BREADTH_SNAPSHOT_VERSION,
    build_theme_correlation_breadth_snapshot,
)


def _theme_payload(**overrides):
    payload = {
        "id": "ai_applications",
        "name": "AI Applications",
        "market": "US",
        "freshness": "delayed",
        "isFallback": False,
        "isStale": False,
        "isPartial": False,
        "staticThemeOnly": False,
        "asOf": "2026-05-07T09:45:00+00:00",
        "updatedAt": "2026-05-07T09:50:00+00:00",
        "breadth": {
            "observedMembers": 6,
            "configuredMembers": 6,
            "coveragePercent": 100.0,
            "percentUp": 83.3,
            "percentOutperformingBenchmark": 66.7,
        },
        "synchronization": {
            "sameDirectionPercent": 83.3,
            "aboveVwapPercent": 72.0,
            "persistencePercent": 75.0,
            "persistenceScore": 0.75,
            "label": "同步扩散",
        },
        "leadership": {
            "leadershipConcentrationPercent": 38.0,
            "broadParticipationPercent": 62.0,
            "topMembers": [{"symbol": "APP"}, {"symbol": "PLTR"}, {"symbol": "CRM"}],
        },
        "persistenceEvidence": {
            "availableWindows": ["5m", "15m", "60m", "1d"],
            "missingWindows": [],
            "staleOrFallbackWindows": [],
        },
    }
    payload.update(overrides)
    return payload


def test_broad_group_snapshot_uses_existing_theme_evidence_without_ranking_impact() -> None:
    snapshot = build_theme_correlation_breadth_snapshot(_theme_payload())

    assert snapshot["contractVersion"] == THEME_CORRELATION_BREADTH_SNAPSHOT_VERSION
    assert snapshot["theme"] == {"id": "ai_applications", "name": "AI Applications", "market": "US"}
    assert snapshot["participationState"] == "broad_group"
    assert snapshot["leadershipConcentration"]["state"] == "balanced"
    assert snapshot["leadershipConcentration"]["percent"] == 38.0
    assert snapshot["correlationEvidence"]["state"] == "aligned"
    assert snapshot["breadthEvidence"]["state"] == "broad"
    assert snapshot["staleInputs"] == []
    assert snapshot["missingInputs"] == []
    assert snapshot["observationBoundary"] == {
        "scope": "existing_theme_fields",
        "rankingImpact": "none",
        "dataMutation": "none",
        "dataFetches": "none",
    }
    assert snapshot["researchNextSteps"] == ["Watch whether broad participation persists across the next observation window."]


def test_leader_concentrated_snapshot_flags_few_leaders_without_advice_language() -> None:
    snapshot = build_theme_correlation_breadth_snapshot(
        _theme_payload(
            breadth={
                "observedMembers": 6,
                "configuredMembers": 6,
                "coveragePercent": 100.0,
                "percentUp": 50.0,
                "percentOutperformingBenchmark": 33.3,
            },
            synchronization={
                "sameDirectionPercent": 50.0,
                "aboveVwapPercent": 48.0,
                "persistencePercent": 50.0,
                "persistenceScore": 0.5,
                "label": "少数成员驱动",
            },
            leadership={
                "leadershipConcentrationPercent": 72.0,
                "broadParticipationPercent": 28.0,
                "topMembers": [{"symbol": "NVDA"}, {"symbol": "AVGO"}],
            },
        )
    )

    dumped = str(snapshot).lower()
    assert snapshot["participationState"] == "leader_concentrated"
    assert snapshot["leadershipConcentration"]["state"] == "concentrated"
    assert snapshot["breadthEvidence"]["state"] == "thin"
    assert snapshot["correlationEvidence"]["state"] == "mixed"
    assert snapshot["researchNextSteps"] == ["Compare top-member moves with the rest of the theme before drawing a group-level conclusion."]
    assert "buy" not in dumped
    assert "sell" not in dumped
    assert "trade recommendation" not in dumped


def test_insufficient_snapshot_bounds_missing_and_stale_inputs() -> None:
    snapshot = build_theme_correlation_breadth_snapshot(
        _theme_payload(
            source="local_taxonomy",
            staticThemeOnly=True,
            freshness="fallback",
            isFallback=True,
            breadth={
                "observedMembers": 0,
                "configuredMembers": 5,
                "coveragePercent": 0,
                "percentUp": None,
                "percentOutperformingBenchmark": None,
            },
            synchronization={
                "sameDirectionPercent": None,
                "aboveVwapPercent": None,
                "persistencePercent": None,
                "persistenceScore": 0.0,
                "label": "分类观察",
            },
            leadership={
                "leadershipConcentrationPercent": None,
                "broadParticipationPercent": None,
                "topMembers": [],
            },
            persistenceEvidence={
                "availableWindows": [],
                "missingWindows": ["5m", "15m", "60m", "1d"],
                "staleOrFallbackWindows": ["5m", "15m", "60m", "1d"],
            },
        )
    )

    assert snapshot["participationState"] == "insufficient_evidence"
    assert snapshot["leadershipConcentration"]["state"] == "unknown"
    assert snapshot["correlationEvidence"]["state"] == "missing"
    assert snapshot["breadthEvidence"]["state"] == "missing"
    assert snapshot["staleInputs"] == ["fallback_source", "fallback_window:5m", "fallback_window:15m", "fallback_window:60m", "fallback_window:1d"]
    assert snapshot["missingInputs"] == [
        "breadth_percent_up",
        "breadth_percent_outperforming_benchmark",
        "correlation_same_direction_percent",
        "correlation_above_vwap_percent",
        "leadership_concentration_percent",
        "market_runtime_evidence",
    ]
    assert snapshot["researchNextSteps"] == ["Collect member-level breadth and synchronization evidence before classifying participation."]


def test_rotation_radar_themes_include_snapshot_without_changing_ranking_score() -> None:
    quotes = {
        "QQQ": {"symbol": "QQQ", "price": 100, "changePercent": 0.8, "volume": 1_000_000, "averageVolume": 1_000_000},
        "SPY": {"symbol": "SPY", "price": 100, "changePercent": 0.4, "volume": 1_000_000, "averageVolume": 1_000_000},
        "IWM": {"symbol": "IWM", "price": 100, "changePercent": 0.2, "volume": 1_000_000, "averageVolume": 1_000_000},
        "APP": {"symbol": "APP", "price": 100, "changePercent": 4.8, "volume": 2_000_000, "averageVolume": 1_000_000},
        "PLTR": {"symbol": "PLTR", "price": 100, "changePercent": 4.2, "volume": 1_800_000, "averageVolume": 1_000_000},
        "CRM": {"symbol": "CRM", "price": 100, "changePercent": 2.6, "volume": 1_500_000, "averageVolume": 1_000_000},
    }
    payload = MarketRotationRadarService(
        quote_provider=lambda symbols: {symbol: quotes[symbol] for symbol in symbols if symbol in quotes},
        now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
    ).get_rotation_radar()
    theme = next(item for item in payload["themes"] if item["id"] == "ai_applications")
    score_before_contract = theme["scoreBreakdown"]["finalScore"]

    assert theme["themeCorrelationBreadthSnapshot"]["theme"]["id"] == "ai_applications"
    assert theme["themeCorrelationBreadthSnapshot"]["observationBoundary"]["rankingImpact"] == "none"
    assert theme["rotationScore"] == score_before_contract
