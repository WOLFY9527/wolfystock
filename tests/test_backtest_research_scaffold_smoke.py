# -*- coding: utf-8 -*-
"""Smoke coverage for T-217B-G backtest research scaffolds."""

from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from datetime import date, timedelta
from typing import Any

from src.services.backtest_execution_cost_capacity import (
    ExecutionCostCapacityConfig,
    evaluate_execution_cost_capacity,
)
from src.services.backtest_factor_research_bridge import build_factor_research_backtest_inputs
from src.services.backtest_parameter_stability import (
    aggregate_parameter_stability_results,
    build_parameter_stability_plan,
)
from src.services.backtest_reproducibility_manifest import build_backtest_reproducibility_manifest
from src.services.backtest_walkforward_oos import (
    aggregate_walk_forward_oos_results,
    build_walk_forward_oos_validation_plan,
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
        "source_name": "smoke_fixture",
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


def _factor_bridge_inputs() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    observations = [
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
    ]
    report = build_factor_research_report(observations)
    manifest = build_factor_experiment_manifest(
        factor_ids=["trend.trend_strength_20d", "momentum.momentum_21d"],
        universe_id="alpha-core-us",
        symbols=["MSFT", "AAPL"],
        as_of="2026-05-17",
        window={"start": "2026-05-01", "end": "2026-05-17", "label": "research_window"},
        input_fingerprints=[
            {
                "kind": "observations",
                "name": "t217b_g_fixture_panel",
                "fingerprint": "obs:fixture:2026-05-17",
                "rows": len(observations),
            }
        ],
    )
    return observations, report, manifest


def _walkforward_observations(count: int = 10) -> list[dict[str, Any]]:
    start = date(2024, 1, 1)
    return [
        {
            "date": start + timedelta(days=index),
            "close": float(100 + index),
            "volume": float(1_000 + index * 10),
        }
        for index in range(count)
    ]


def test_backtest_research_scaffolds_compose_with_fixture_inputs_only() -> None:
    factor_observations, report, manifest = _factor_bridge_inputs()
    walkforward_observations = _walkforward_observations()
    trades = [
        {"trade_id": "buy-aapl", "symbol": "AAPL", "date": "2024-01-05", "side": "buy", "quantity": 200, "price": 50.0},
        {"trade_id": "sell-msft", "symbol": "MSFT", "date": "2024-01-06", "side": "sell", "quantity": 120, "price": 75.0},
    ]
    bars = [
        {"symbol": "AAPL", "date": "2024-01-05", "volume": 10_000},
        {"symbol": "MSFT", "date": "2024-01-06", "volume": 8_000},
    ]
    factor_observations_snapshot = deepcopy(factor_observations)
    report_snapshot = deepcopy(report)
    manifest_snapshot = deepcopy(manifest)
    walkforward_snapshot = deepcopy(walkforward_observations)
    trades_snapshot = deepcopy(trades)
    bars_snapshot = deepcopy(bars)

    factor_bridge = build_factor_research_backtest_inputs(
        observations=factor_observations,
        research_report=report,
        experiment_manifest=manifest,
        as_of="2026-05-17",
        max_symbols=2,
    )
    assert factor_bridge["state"] == "ready"
    assert factor_bridge["offline_only"] is True
    assert factor_bridge["execution_semantics"]["provider_calls_executed"] is False
    assert [item["symbol"] for item in factor_bridge["ranked_symbols"]] == ["MSFT", "AAPL"]

    walkforward_plan = build_walk_forward_oos_validation_plan(
        observations=walkforward_observations,
        strategy_id="fixture-ma-cross",
        config={"train_window": 4, "test_window": 2, "step": 2, "max_folds": 2},
        dataset_id="fixture-bars-v1",
        run_id="fixture-run-1",
    )
    fold_results = [
        {
            "fold_id": walkforward_plan["folds"][0]["fold_id"],
            "state": "completed",
            "metrics": {
                "total_return_pct": 1.5,
                "max_drawdown_pct": 2.0,
                "win_rate_pct": 50.0,
                "trade_count": 2,
            },
        },
        {
            "fold_id": walkforward_plan["folds"][1]["fold_id"],
            "state": "completed",
            "metrics": {
                "total_return_pct": 2.5,
                "max_drawdown_pct": 1.0,
                "win_rate_pct": 100.0,
                "trade_count": 1,
            },
        },
    ]
    walkforward_summary = aggregate_walk_forward_oos_results(plan=walkforward_plan, fold_results=fold_results)
    assert walkforward_summary["state"] == "available"
    assert walkforward_summary["diagnostic_only"] is True
    assert walkforward_summary["oos_result_summary"]["completed_fold_count"] == 2

    execution_cost = evaluate_execution_cost_capacity(
        trades,
        bars=bars,
        config=ExecutionCostCapacityConfig(
            commission_bps=5.0,
            slippage_bps=2.0,
            spread_bps=1.0,
            volume_participation_cap=0.5,
        ),
    )
    assert execution_cost["summary"]["trade_count"] == 2
    assert execution_cost["summary"]["total_cost"] == 15.2
    assert execution_cost["assumptions"]["default_zero_cost_preserves_backtest_math"] is False

    parameter_plan = build_parameter_stability_plan(
        strategy_id="fixture-ma-cross",
        dataset_id="fixture-bars-v1",
        base_parameters={"strategy_spec.signal.symbols": [item["symbol"] for item in factor_bridge["ranked_symbols"]]},
        parameter_grid={
            "strategy_spec.signal.fast_period": [5, 10],
            "strategy_spec.signal.slow_period": [20],
        },
        metric_keys=["total_return_pct", "max_drawdown_pct", "sharpe_ratio", "trade_count"],
        primary_metric="total_return_pct",
        risk_metric="max_drawdown_pct",
        min_completed_runs=2,
    )
    parameter_results = [
        {
            "planned_run_id": parameter_plan["grid_runs"][0]["planned_run_id"],
            "state": "completed",
            "external_run_id": "fixture-5-20",
            "metrics": {
                "total_return_pct": walkforward_summary["oos_result_summary"]["metric_aggregates"]["total_return_pct"]["mean"],
                "max_drawdown_pct": 2.0,
                "sharpe_ratio": 0.9,
                "trade_count": execution_cost["summary"]["trade_count"],
            },
        },
        {
            "planned_run_id": parameter_plan["grid_runs"][1]["planned_run_id"],
            "state": "completed",
            "external_run_id": "fixture-10-20",
            "metrics": {
                "total_return_pct": 3.0,
                "max_drawdown_pct": 1.5,
                "sharpe_ratio": 1.1,
                "trade_count": execution_cost["summary"]["trade_count"],
            },
        },
    ]
    parameter_surface = aggregate_parameter_stability_results(
        plan=parameter_plan,
        run_results=parameter_results,
    )
    assert parameter_surface["state"] == "available"
    assert parameter_surface["diagnostic_only"] is True
    assert parameter_surface["execution_semantics"]["provider_calls_executed"] is False
    assert parameter_surface["best_summary"]["best_value"] == 3.0

    reproducibility_manifest = build_backtest_reproducibility_manifest(
        generated_at="2026-05-18T00:00:00Z",
        strategy_type="rule_backtest_research_scaffold",
        strategy={"signal": {"fast_period": 5, "slow_period": 20}},
        data_window={"start": "2024-01-01", "end": "2024-01-10", "bar_count": len(walkforward_observations)},
        symbols=[item["symbol"] for item in factor_bridge["ranked_symbols"]],
        universe={"universe_id": factor_bridge["factor_universe"]["universe_id"], "selection_rule": "factor_bridge_fixture"},
        execution_cost_assumptions=execution_cost["assumptions"],
        walk_forward_config=walkforward_plan["configuration"],
        parameter_stability_config=parameter_plan["grid_spec"],
        factor_research_input=factor_bridge,
        engine_contract_flags={
            "provider_calls_executed": False,
            "engine_math_changed": False,
            "database_migration_required": False,
            "api_response_shapes_changed": False,
        },
        warnings=["diagnostic-only scaffold smoke"],
    ).to_dict()
    assert reproducibility_manifest["schema_version"] == "backtest_reproducibility_manifest.v1"
    assert reproducibility_manifest["symbols"] == ["AAPL", "MSFT"]
    assert reproducibility_manifest["walk_forward_config_fingerprint"]["state"] == "provided"
    assert reproducibility_manifest["parameter_stability_config_fingerprint"]["state"] == "provided"
    assert reproducibility_manifest["factor_research_input_fingerprint"]["state"] == "provided"

    assert factor_observations == factor_observations_snapshot
    assert report == report_snapshot
    assert manifest == manifest_snapshot
    assert walkforward_observations == walkforward_snapshot
    assert trades == trades_snapshot
    assert bars == bars_snapshot


def test_backtest_research_scaffold_imports_do_not_pull_runtime_domains() -> None:
    script = """
import json
import sys

import src.services.backtest_execution_cost_capacity
import src.services.backtest_factor_research_bridge
import src.services.backtest_parameter_stability
import src.services.backtest_reproducibility_manifest
import src.services.backtest_walkforward_oos

blocked = [
    "src.core.backtest_engine",
    "src.core.rule_backtest_engine",
    "src.services.backtest_service",
    "src.services.rule_backtest_service",
    "src.repositories.backtest_repo",
    "src.repositories.rule_backtest_repo",
    "data_provider",
    "api.v1.endpoints.backtest",
]
print(json.dumps({name: name in sys.modules for name in blocked}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    imported = json.loads(completed.stdout)
    assert imported == {name: False for name in imported}
