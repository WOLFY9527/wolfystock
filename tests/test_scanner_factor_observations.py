# -*- coding: utf-8 -*-
"""Focused tests for additive scanner factor observation export."""

from __future__ import annotations

from copy import deepcopy

from src.services.scanner_factor_observations import (
    attach_scanner_factor_observations,
    build_scanner_factor_observations,
)


def _us_candidate() -> dict[str, object]:
    return {
        "symbol": "NVDA",
        "name": "NVIDIA",
        "rank": 1,
        "score": 82.2,
        "raw_score": 82.2,
        "final_score": 82.2,
        "ret_5d": 4.1,
        "ret_20d": 12.7,
        "benchmark_relative_20d": 4.2,
        "gap_pct": 1.8,
        "avg_amount_20": 1.2e10,
        "amount": 1.1e10,
        "avg_volume_20": 22_000_000,
        "volume_expansion_20": 1.2,
        "atr20_pct": 3.7,
        "ma20_slope_pct": 1.1,
        "distance_to_20d_high_pct": -1.4,
        "last_trade_date": "2026-05-16",
        "_relative_strength_pct": 0.81,
        "_matched_sectors": [],
        "_component_scores": {
            "trend": 18.0,
            "momentum": 12.0,
            "liquidity": 15.2,
            "activity": 9.8,
            "volatility_quality": 7.4,
            "relative_strength": 8.1,
            "benchmark_relative": 6.5,
            "gap_context": 5.2,
            "penalties": 0.0,
        },
        "_diagnostics": {
            "profile": "us_preopen_v1",
            "history": {
                "source": "local_db",
                "latest_trade_date": "2026-05-16",
                "rows": 130,
            },
            "quote_context": {
                "available": True,
                "source": "yfinance",
            },
            "score_explainability": {
                "score_confidence": 1.0,
                "evidence_coverage": 1.0,
                "degradation_reason": None,
                "missing_evidence": [],
                "source_confidence": {
                    "source": "yfinance",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "live",
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": False,
                    "confidenceWeight": 1.0,
                    "coverage": 1.0,
                    "degradationReason": None,
                    "capReason": None,
                },
            },
        },
    }


def _cn_candidate() -> dict[str, object]:
    return {
        "symbol": "600001",
        "name": "示例股份",
        "rank": 1,
        "score": 87.7,
        "raw_score": 87.7,
        "final_score": 87.7,
        "ret_5d": 5.6,
        "ret_20d": 14.4,
        "avg_amount_20": 8.4e8,
        "amount": 9.2e8,
        "avg_volume_20": 33_000_000,
        "volume_expansion_20": 1.6,
        "atr20_pct": 4.6,
        "ma20_slope_pct": 1.3,
        "distance_to_20d_high_pct": -1.2,
        "last_trade_date": "2026-05-16",
        "_relative_strength_pct": 0.94,
        "_matched_sectors": ["算力", "AI 基建"],
        "_component_scores": {
            "trend": 18.8,
            "momentum": 13.4,
            "breakout": 10.2,
            "liquidity": 9.6,
            "activity": 7.5,
            "volatility_quality": 4.7,
            "relative_strength": 4.7,
            "sector_bonus": 5.0,
            "penalties": 0.2,
        },
        "_diagnostics": {
            "profile": "cn_preopen_v1",
            "history": {
                "source": "local_db",
                "latest_trade_date": "2026-05-16",
                "rows": 130,
            },
            "score_explainability": {
                "score_confidence": 1.0,
                "evidence_coverage": 1.0,
                "degradation_reason": None,
                "missing_evidence": [],
                "source_confidence": {
                    "source": "local_db",
                    "sourceLabel": "本地数据库历史",
                    "freshness": "cached",
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": False,
                    "confidenceWeight": 1.0,
                    "coverage": 1.0,
                    "degradationReason": None,
                    "capReason": None,
                },
            },
        },
    }


def test_build_scanner_factor_observations_uses_deterministic_ids_and_contract_factor_ids() -> None:
    candidate = _us_candidate()

    first = build_scanner_factor_observations(candidate, market="us", observed_at="2026-05-16T13:40:00Z")
    second = build_scanner_factor_observations(candidate, market="us", observed_at="2026-05-16T13:40:00Z")

    assert [item["observation_id"] for item in first] == [item["observation_id"] for item in second]
    assert [item["factor_id"] for item in first] == [
        "trend.trend_strength_20d",
        "momentum.momentum_21d",
        "liquidity.liquidity_support_20d",
        "activity.activity_burst_10d",
        "volatility_quality.volatility_quality_21d",
        "relative_strength.relative_strength_63d",
        "relative_strength.benchmark_relative_20d",
        "trend.gap_context_1d",
    ]
    assert first[0]["observation_id"] == (
        "scanner_factor_observation:us:us_preopen_v1:nvda:trend.trend_strength_20d:trend:2026-05-16"
    )


def test_build_scanner_factor_observations_binds_symbol_and_timestamps_from_scanner_context() -> None:
    rows = build_scanner_factor_observations(
        _us_candidate(),
        market="us",
        observed_at="2026-05-16T13:40:00Z",
    )

    assert rows
    assert all(item["component"] for item in rows)
    assert all(item["observation"]["symbol"] == "NVDA" for item in rows)
    assert all(item["observation"]["as_of"] == "2026-05-16" for item in rows)
    assert all(item["observation"]["observed_at"] == "2026-05-16T13:40:00Z" for item in rows)
    assert all(item["observation"]["confidence"] == 1.0 for item in rows)
    assert all(item["profile"] == "us_preopen_v1" for item in rows)


def test_build_scanner_factor_observations_skips_missing_components_without_dropping_zero_values() -> None:
    candidate = _us_candidate()
    del candidate["_component_scores"]["gap_context"]
    candidate["_component_scores"]["benchmark_relative"] = 0.0

    rows = build_scanner_factor_observations(
        candidate,
        market="us",
        observed_at="2026-05-16T13:40:00Z",
    )

    components = [item["component"] for item in rows]
    assert "gap_context" not in components
    assert "benchmark_relative" in components
    benchmark_relative = next(item for item in rows if item["component"] == "benchmark_relative")
    assert benchmark_relative["observation"]["value"] == 0.0


def test_build_scanner_factor_observations_maps_cn_only_components_and_skips_quote_only_fields() -> None:
    rows = build_scanner_factor_observations(
        _cn_candidate(),
        market="cn",
        observed_at="2026-05-16T08:40:00+08:00",
    )

    assert [item["component"] for item in rows] == [
        "trend",
        "momentum",
        "breakout",
        "liquidity",
        "activity",
        "volatility_quality",
        "relative_strength",
        "sector_bonus",
    ]
    assert [item["factor_id"] for item in rows][-1] == "sector_context.sector_relative_breadth_20d"


def test_attach_scanner_factor_observations_does_not_mutate_score_or_ranking_fields() -> None:
    candidate = _us_candidate()
    baseline = deepcopy(candidate)

    exported = attach_scanner_factor_observations(
        candidate,
        market="us",
        observed_at="2026-05-16T13:40:00Z",
    )

    assert exported
    assert candidate["rank"] == baseline["rank"]
    assert candidate["score"] == baseline["score"]
    assert candidate["raw_score"] == baseline["raw_score"]
    assert candidate["final_score"] == baseline["final_score"]
    assert candidate["_component_scores"] == baseline["_component_scores"]
    assert candidate["_diagnostics"]["factor_observations"] == exported
