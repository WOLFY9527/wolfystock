# -*- coding: utf-8 -*-
"""Tests for the pure market persistence evidence foundation."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.services.market_persistence_evidence_service import (
    PERSISTENCE_STATUSES,
    PERSISTENCE_WINDOWS,
    MarketPersistenceEvidenceService,
    MarketPersistenceEvidenceSnapshot,
    synthesize_market_persistence,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = REPO_ROOT / "src/services/market_persistence_evidence_service.py"


def _snapshot(
    days_ago: int,
    *,
    key: str = "market_regime",
    surface: str = "market_overview",
    metric: str = "regime_score",
    value: float = 0.7,
    score: float | None = None,
    signal_label: str | None = "risk_on_liquidity_expansion",
    source: str = "unit_fixture",
    source_tier: str = "official_public",
    trust_level: str = "high",
    freshness: str = "fresh",
    observation_only: bool = False,
    score_contribution_allowed: bool = True,
    degradation_reason: str | None = None,
) -> MarketPersistenceEvidenceSnapshot:
    timestamp = (datetime(2026, 5, 20, 10, tzinfo=timezone(timedelta(hours=8))) - timedelta(days=days_ago)).isoformat()
    return MarketPersistenceEvidenceSnapshot(
        key=key,
        surface=surface,
        metric=metric,
        value=value,
        score=score if score is not None else value,
        signal_label=signal_label,
        as_of=timestamp,
        updated_at=timestamp,
        source=source,
        source_tier=source_tier,
        trust_level=trust_level,
        freshness=freshness,
        observation_only=observation_only,
        score_contribution_allowed=score_contribution_allowed,
        degradation_reason=degradation_reason,
    )


def test_stable_same_regime_snapshots_classify_persistent() -> None:
    result = synthesize_market_persistence(
        [
            _snapshot(0, value=0.82),
            _snapshot(1, value=0.8),
            _snapshot(5, value=0.78),
            _snapshot(20, value=0.76),
        ]
    )

    assert result.persistence_status == "persistent"
    assert tuple(result.windows) == PERSISTENCE_WINDOWS
    assert result.trend_direction in {"stable", "strengthening"}
    assert result.acceleration in {"stable", "accelerating"}
    assert result.consistency_score >= 0.8
    assert result.confidence >= 0.7
    assert result.confidence_label in {"medium", "high"}
    assert not result.counter_evidence


def test_latest_shift_after_neutral_history_classifies_emerging() -> None:
    result = MarketPersistenceEvidenceService().synthesize(
        [
            _snapshot(0, value=0.72, signal_label="risk_on_liquidity_expansion"),
            _snapshot(1, value=0.05, signal_label="neutral"),
            _snapshot(5, value=0.02, signal_label="neutral"),
            _snapshot(20, value=0.01, signal_label="neutral"),
        ]
    )

    assert result.persistence_status == "emerging"
    assert tuple(result.windows) == PERSISTENCE_WINDOWS
    assert result.trend_direction == "strengthening"
    assert result.acceleration == "accelerating"
    assert result.consistency_score < 0.75
    assert result.narrative_bullets


def test_weakening_latest_vs_strong_prior_classifies_fading() -> None:
    result = synthesize_market_persistence(
        [
            _snapshot(0, value=0.24),
            _snapshot(1, value=0.64),
            _snapshot(5, value=0.83),
            _snapshot(20, value=0.88),
        ]
    )

    assert result.persistence_status == "fading"
    assert result.trend_direction == "weakening"
    assert result.acceleration == "decelerating"
    assert result.counter_evidence


def test_alternating_states_classify_volatile_and_emit_counter_evidence() -> None:
    result = synthesize_market_persistence(
        [
            _snapshot(0, value=-0.62, signal_label="risk_off_deleveraging"),
            _snapshot(1, value=0.58, signal_label="risk_on_liquidity_expansion"),
            _snapshot(5, value=-0.54, signal_label="risk_off_deleveraging"),
            _snapshot(20, value=0.61, signal_label="risk_on_liquidity_expansion"),
        ]
    )

    assert result.persistence_status == "volatile"
    assert result.trend_direction == "mixed"
    assert result.acceleration == "mixed"
    assert result.consistency_score < 0.45
    assert result.counter_evidence
    assert result.narrative_bullets


def test_only_latest_record_returns_insufficient_history() -> None:
    result = synthesize_market_persistence([_snapshot(0, value=0.44)])

    assert result.persistence_status == "insufficient_history"
    assert tuple(result.windows) == ("latest",)
    assert result.confidence_label == "insufficient"
    assert any(gap["reason"] == "insufficient_history" for gap in result.data_gaps)


def test_stale_proxy_observation_only_evidence_lowers_confidence() -> None:
    fresh = synthesize_market_persistence(
        [
            _snapshot(0, value=0.82),
            _snapshot(1, value=0.8),
            _snapshot(5, value=0.78),
            _snapshot(20, value=0.76),
        ]
    )
    degraded = synthesize_market_persistence(
        [
            _snapshot(
                0,
                value=0.82,
                source_tier="unofficial_proxy",
                trust_level="usable_with_caution",
                freshness="stale",
                observation_only=True,
                source="proxy_fixture",
            ),
            _snapshot(
                1,
                value=0.8,
                source_tier="unofficial_proxy",
                trust_level="usable_with_caution",
                freshness="stale",
                observation_only=True,
                source="proxy_fixture",
            ),
            _snapshot(
                5,
                value=0.78,
                source_tier="unofficial_proxy",
                trust_level="usable_with_caution",
                freshness="stale",
                observation_only=True,
                source="proxy_fixture",
            ),
            _snapshot(
                20,
                value=0.76,
                source_tier="unofficial_proxy",
                trust_level="usable_with_caution",
                freshness="stale",
                observation_only=True,
                source="proxy_fixture",
            ),
        ]
    )

    assert fresh.persistence_status == "persistent"
    assert degraded.persistence_status == "persistent"
    assert degraded.confidence < fresh.confidence
    assert degraded.confidence_label in {"low", "medium"}
    assert any(item["observationOnly"] for item in degraded.evidence_items)


def test_non_score_eligible_evidence_cannot_dominate_and_returns_data_insufficient() -> None:
    result = synthesize_market_persistence(
        [
            _snapshot(
                0,
                value=0.95,
                score_contribution_allowed=False,
                observation_only=True,
            ),
            _snapshot(
                1,
                value=0.92,
                score_contribution_allowed=False,
                observation_only=True,
            ),
            _snapshot(
                5,
                value=0.89,
                score_contribution_allowed=False,
                observation_only=True,
            ),
            _snapshot(
                20,
                value=0.9,
                score_contribution_allowed=False,
                observation_only=True,
            ),
        ]
    )

    assert result.persistence_status == "data_insufficient"
    assert result.confidence_label == "insufficient"
    assert any(gap["reason"] == "score_contribution_not_allowed" for gap in result.data_gaps)


def test_output_includes_data_gaps_counter_evidence_and_narrative_bullets() -> None:
    result = synthesize_market_persistence(
        [
            _snapshot(0, value=-0.48, signal_label="risk_off_deleveraging"),
            _snapshot(1, value=0.35, signal_label="risk_on_liquidity_expansion"),
            _snapshot(
                5,
                value=None,
                score=None,
                signal_label=None,
                freshness="unavailable",
                trust_level="unavailable",
                score_contribution_allowed=False,
                degradation_reason="provider_unavailable",
            ),
            _snapshot(20, value=-0.58, signal_label="risk_off_deleveraging"),
        ]
    )
    payload = result.to_dict()

    for key in (
        "persistenceStatus",
        "windows",
        "evidenceItems",
        "trendDirection",
        "acceleration",
        "consistencyScore",
        "confidence",
        "confidenceLabel",
        "dataGaps",
        "counterEvidence",
        "narrativeBullets",
        "notInvestmentAdvice",
    ):
        assert key in payload
    assert payload["dataGaps"]
    assert payload["counterEvidence"]
    assert payload["narrativeBullets"]
    assert payload["notInvestmentAdvice"] is True
    assert result.persistence_status in PERSISTENCE_STATUSES


def test_windows_only_include_supported_history_buckets() -> None:
    result = synthesize_market_persistence(
        [
            _snapshot(0, value=0.61),
            _snapshot(1, value=0.55),
            _snapshot(5, value=0.52),
        ]
    )

    assert tuple(result.windows) == ("latest", "1d", "5d")
    assert "20d" not in result.windows


def test_input_dto_accepts_camel_case_mapping_without_provider_calls() -> None:
    result = synthesize_market_persistence(
        [
            {
                "key": "market_regime",
                "surface": "market_overview",
                "metric": "regime_score",
                "value": 0.81,
                "score": 0.81,
                "signalLabel": "risk_on_liquidity_expansion",
                "source": "cache_fixture",
                "sourceTier": "cache_snapshot",
                "trustLevel": "usable_with_caution",
                "freshness": "cached",
                "observationOnly": False,
                "scoreContributionAllowed": True,
                "asOf": "2026-05-20T10:00:00+08:00",
                "updatedAt": "2026-05-20T10:00:00+08:00",
            },
            {
                "key": "market_regime",
                "surface": "market_overview",
                "metric": "regime_score",
                "value": 0.76,
                "score": 0.76,
                "signalLabel": "risk_on_liquidity_expansion",
                "source": "cache_fixture",
                "sourceTier": "cache_snapshot",
                "trustLevel": "usable_with_caution",
                "freshness": "cached",
                "observationOnly": False,
                "scoreContributionAllowed": True,
                "asOf": "2026-05-19T10:00:00+08:00",
                "updatedAt": "2026-05-19T10:00:00+08:00",
            },
        ]
    )

    assert result.persistence_status in {"persistent", "insufficient_history"}


def test_service_module_has_no_provider_network_runtime_or_endpoint_imports() -> None:
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")

    forbidden_prefixes = (
        "api",
        "apps",
        "bot",
        "data_provider",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "yfinance",
        "src.services.market_overview_service",
        "src.services.liquidity_monitor_service",
        "src.services.market_rotation_radar_service",
        "src.services.market_cache",
    )
    assert not [name for name in imports if name.startswith(forbidden_prefixes)]

    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "DataFetcherManager",
        "MarketOverviewService",
        "LiquidityMonitorService",
        "MarketRotationRadarService",
        "ObservationCache",
        "FastAPI",
    ):
        assert forbidden not in source
