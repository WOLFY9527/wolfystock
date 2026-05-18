# -*- coding: utf-8 -*-
"""Contracts for the offline factor-research to backtest-input bridge."""

from __future__ import annotations

import json
import random
import subprocess
import sys
from typing import Any

from src.services.backtest_factor_research_bridge import (
    BACKTEST_FACTOR_RESEARCH_BRIDGE_CONTRACT_KIND,
    BACKTEST_FACTOR_RESEARCH_BRIDGE_CONTRACT_VERSION,
    build_factor_research_backtest_inputs,
)
from src.services.factor_experiment_manifest import build_factor_experiment_manifest
from src.services.factor_research_report import build_factor_research_report


def _observation(
    *,
    factor_id: str,
    symbol: str,
    value: float,
    as_of: str,
    percentile: float | None = None,
    z_score: float | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "factor_id": factor_id,
        "symbol": symbol,
        "value": value,
        "source_name": "unit_fixture",
        "source_type": "synthetic_fixture",
        "as_of": as_of,
        "observed_at": f"{as_of}T15:00:00Z",
        "freshness_status": "partial",
        "confidence": 0.6,
        "is_partial": True,
    }
    if percentile is not None:
        payload["percentile"] = percentile
    if z_score is not None:
        payload["z_score"] = z_score
    return payload


def _bridge_inputs(*, shuffled: bool = False) -> tuple[list[dict[str, Any]], Any, Any]:
    usable_observations = [
        _observation(
            factor_id="momentum.momentum_21d",
            symbol="MSFT",
            value=0.7,
            percentile=0.92,
            as_of="2026-05-17",
        ),
        _observation(
            factor_id="momentum.momentum_21d",
            symbol="AAPL",
            value=0.5,
            percentile=0.74,
            as_of="2026-05-17",
        ),
        _observation(
            factor_id="momentum.momentum_21d",
            symbol="TSLA",
            value=-0.3,
            percentile=0.18,
            as_of="2026-05-17",
        ),
        _observation(
            factor_id="trend.trend_strength_20d",
            symbol="MSFT",
            value=0.4,
            z_score=1.2,
            as_of="2026-05-17",
        ),
        _observation(
            factor_id="trend.trend_strength_20d",
            symbol="AAPL",
            value=0.8,
            z_score=1.8,
            as_of="2026-05-17",
        ),
        _observation(
            factor_id="trend.trend_strength_20d",
            symbol="TSLA",
            value=-0.2,
            z_score=-0.8,
            as_of="2026-05-17",
        ),
    ]
    observations = [
        *usable_observations,
        _observation(
            factor_id="momentum.momentum_21d",
            symbol="NVDA",
            value=0.99,
            percentile=0.99,
            as_of="2026-05-19",
        ),
    ]
    if shuffled:
        random.Random(17).shuffle(observations)

    report = build_factor_research_report(usable_observations)
    manifest = build_factor_experiment_manifest(
        factor_ids=["trend.trend_strength_20d", "momentum.momentum_21d"],
        universe_id="alpha-core-us",
        symbols=["TSLA", "MSFT", "AAPL"],
        as_of="2026-05-17",
        window={"start": "2026-05-01", "end": "2026-05-17", "label": "research_window"},
        input_fingerprints=[
            {
                "kind": "observations",
                "name": "alpha_factory_panel",
                "fingerprint": "obs:fixture:2026-05-17",
                "rows": 6,
            }
        ],
    )
    return observations, report, manifest


def test_bridge_builds_deterministic_research_inputs_without_executing_backtests() -> None:
    observations, report, manifest = _bridge_inputs()

    bridge = build_factor_research_backtest_inputs(
        observations=observations,
        research_report=report,
        experiment_manifest=manifest,
        as_of="2026-05-17",
    )

    assert bridge["contract_kind"] == BACKTEST_FACTOR_RESEARCH_BRIDGE_CONTRACT_KIND
    assert bridge["contract_version"] == BACKTEST_FACTOR_RESEARCH_BRIDGE_CONTRACT_VERSION
    assert bridge["state"] == "ready"
    assert bridge["factor_universe"]["factor_ids"] == [
        "momentum.momentum_21d",
        "trend.trend_strength_20d",
    ]
    assert bridge["factor_universe"]["universe_id"] == "alpha-core-us"
    assert [item["symbol"] for item in bridge["ranked_symbols"]] == ["MSFT", "AAPL", "TSLA"]
    assert [item["rank"] for item in bridge["ranked_symbols"]] == [1, 2, 3]
    assert bridge["ranked_symbols"][0]["factor_count"] == 2
    assert bridge["ranked_symbols"][0]["ranking_policy"] == "average_caller_supplied_factor_scores"

    momentum_buckets = bridge["factor_buckets"][0]
    assert momentum_buckets["factor_id"] == "momentum.momentum_21d"
    assert [(bucket["bucket"], bucket["symbols"]) for bucket in momentum_buckets["buckets"]] == [
        ("top", ["MSFT"]),
        ("middle", ["AAPL"]),
        ("bottom", ["TSLA"]),
    ]

    assert bridge["as_of"] == {
        "value": "2026-05-17",
        "source": "explicit",
    }
    assert bridge["window"] == {
        "start": "2026-05-01",
        "end": "2026-05-17",
        "label": "research_window",
        "source": "experiment_manifest",
        "observation_count": 6,
    }
    assert bridge["no_lookahead_guard"] == {
        "policy": "exclude_observations_after_as_of",
        "as_of": "2026-05-17",
        "input_observation_count": 7,
        "usable_observation_count": 6,
        "future_observations_excluded": 1,
        "future_observations_used": 0,
        "lookahead_bias_state": "guarded_future_rows_excluded",
    }
    assert ("observations", "future_observation_excluded") in [
        (item["section"], item["reason"]) for item in bridge["missing_data_reasons"]
    ]
    assert bridge["execution_semantics"] == {
        "execution_mode": "caller_supplied_research_inputs_only",
        "strategy_execution_count": 0,
        "automatic_backtest_run": False,
        "optimizer_executed": False,
        "provider_calls_executed": False,
        "engine_math_changed": False,
        "api_response_shapes_changed": False,
        "database_migration_required": False,
        "frontend_runtime_wiring_changed": False,
    }
    assert bridge["reproducibility"]["input_content_hash"]
    assert bridge["reproducibility"]["ranked_symbols_hash"]
    assert bridge["reproducibility"]["factor_buckets_hash"]


def test_bridge_output_order_and_fingerprints_ignore_input_order() -> None:
    ordered_observations, ordered_report, ordered_manifest = _bridge_inputs(shuffled=False)
    shuffled_observations, shuffled_report, shuffled_manifest = _bridge_inputs(shuffled=True)

    ordered = build_factor_research_backtest_inputs(
        observations=ordered_observations,
        research_report=ordered_report,
        experiment_manifest=ordered_manifest,
    )
    shuffled = build_factor_research_backtest_inputs(
        observations=shuffled_observations,
        research_report=shuffled_report,
        experiment_manifest=shuffled_manifest,
    )

    assert ordered["ranked_symbols"] == shuffled["ranked_symbols"]
    assert ordered["factor_buckets"] == shuffled["factor_buckets"]
    assert ordered["reproducibility"] == shuffled["reproducibility"]


def test_bridge_reports_missing_factor_rows_without_fabricating_ranked_symbols() -> None:
    manifest = build_factor_experiment_manifest(
        factor_ids=["momentum.momentum_21d", "relative_strength.relative_strength_63d"],
        universe_id="alpha-core-us",
        symbols=["AAPL", "MSFT"],
        as_of="2026-05-17",
    )

    bridge = build_factor_research_backtest_inputs(
        observations=[
            _observation(
                factor_id="momentum.momentum_21d",
                symbol="AAPL",
                value=0.5,
                percentile=0.8,
                as_of="2026-05-17",
            )
        ],
        experiment_manifest=manifest,
    )

    assert bridge["state"] == "ready_with_missing_data"
    assert bridge["ranked_symbols"] == [
        {
            "rank": 1,
            "symbol": "AAPL",
            "score": 0.8,
            "factor_count": 1,
            "factor_scores": [
                {
                    "factor_id": "momentum.momentum_21d",
                    "score": 0.8,
                    "basis": "percentile",
                    "as_of": "2026-05-17",
                }
            ],
            "ranking_policy": "average_caller_supplied_factor_scores",
        }
    ]
    assert {
        (item["section"], item["reason"], item.get("factor_id"), item.get("symbol"))
        for item in bridge["missing_data_reasons"]
    } >= {
        ("observations", "manifest_symbol_missing_factor_observation", "momentum.momentum_21d", "MSFT"),
        ("observations", "manifest_factor_missing_observations", "relative_strength.relative_strength_63d", None),
    }


def test_bridge_import_has_no_backtest_runtime_provider_or_frontend_side_effects() -> None:
    script = """
import json
import src.services.backtest_factor_research_bridge
blocked = [
    "src.core.backtest_engine",
    "src.core.rule_backtest_engine",
    "src.services.rule_backtest_service",
    "src.services.backtest_service",
    "data_provider",
    "api.v1.endpoints.backtest",
]
print(json.dumps({name: name in __import__('sys').modules for name in blocked}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    imported = json.loads(completed.stdout)
    assert imported == {name: False for name in imported}
