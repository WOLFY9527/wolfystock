# -*- coding: utf-8 -*-
"""Contract tests for additive walk-forward / OOS backtest scaffolding."""

from __future__ import annotations

import copy
from datetime import date, timedelta

from src.services.backtest_walkforward_oos import (
    WALK_FORWARD_OOS_CONTRACT_VERSION,
    aggregate_walk_forward_oos_results,
    build_walk_forward_oos_contract_metadata,
    build_walk_forward_oos_validation_plan,
)


def _make_observations(dates: list[date]) -> list[dict[str, object]]:
    return [
        {
            "date": item,
            "close": float(index + 100),
            "volume": float(1000 + index),
        }
        for index, item in enumerate(dates)
    ]


def _date_range(start: date, count: int) -> list[date]:
    return [start + timedelta(days=index) for index in range(count)]


def test_build_walk_forward_oos_validation_plan_constructs_deterministic_rolling_windows() -> None:
    observations = _make_observations(_date_range(date(2024, 1, 1), 12))

    plan = build_walk_forward_oos_validation_plan(
        observations=observations,
        strategy_id="input-strategy",
        config={
            "train_window": 4,
            "test_window": 2,
            "step": 3,
            "max_folds": 3,
        },
    )

    assert plan["contract_version"] == WALK_FORWARD_OOS_CONTRACT_VERSION
    assert plan["state"] == "ready"
    assert [fold["fold_index"] for fold in plan["folds"]] == [1, 2, 3]
    assert [fold["fold_id"] for fold in plan["folds"]] == [
        "wf_oos_fold_0001_train_20240101_20240104_test_20240105_20240106",
        "wf_oos_fold_0002_train_20240104_20240107_test_20240108_20240109",
        "wf_oos_fold_0003_train_20240107_20240110_test_20240111_20240112",
    ]
    assert plan["folds"][0]["train_window"] == {
        "start_index": 0,
        "end_index": 3,
        "start_date": "2024-01-01",
        "end_date": "2024-01-04",
        "size": 4,
    }
    assert plan["folds"][0]["test_window"] == {
        "start_index": 4,
        "end_index": 5,
        "start_date": "2024-01-05",
        "end_date": "2024-01-06",
        "size": 2,
    }
    assert plan["strategy_selection"] == {
        "state": "diagnostic_only_placeholder",
        "selected_strategy_id": "input-strategy",
        "selection_rule": "reuse_input_strategy_without_optimizer_search",
        "candidate_count": 1,
        "optimizer_executed": False,
        "parameter_sweep_executed": False,
        "portfolio_allocation_backtest_executed": False,
        "winner_selection_executed": False,
    }


def test_aggregate_walk_forward_oos_results_sorts_folds_and_summarizes_metrics() -> None:
    observations = _make_observations(_date_range(date(2024, 1, 1), 12))
    plan = build_walk_forward_oos_validation_plan(
        observations=observations,
        strategy_id="input-strategy",
        config={
            "train_window": 4,
            "test_window": 2,
            "step": 3,
            "max_folds": 3,
        },
    )
    fold_results = [
        {
            "fold_id": plan["folds"][2]["fold_id"],
            "state": "completed",
            "metrics": {
                "total_return_pct": 3.0,
                "max_drawdown_pct": 1.5,
                "win_rate_pct": 50.0,
                "trade_count": 4,
            },
        },
        {
            "fold_id": plan["folds"][0]["fold_id"],
            "state": "completed",
            "metrics": {
                "total_return_pct": 1.0,
                "max_drawdown_pct": 2.5,
                "win_rate_pct": 75.0,
                "trade_count": 2,
            },
        },
        {
            "fold_id": plan["folds"][1]["fold_id"],
            "state": "completed",
            "metrics": {
                "total_return_pct": 2.0,
                "max_drawdown_pct": 1.0,
                "win_rate_pct": 25.0,
                "trade_count": 3,
            },
        },
    ]

    summary = aggregate_walk_forward_oos_results(
        plan=plan,
        fold_results=fold_results,
    )

    assert summary["state"] == "available"
    assert summary["fold_order"] == [fold["fold_id"] for fold in plan["folds"]]
    assert [fold["fold_id"] for fold in summary["fold_results"]] == summary["fold_order"]
    assert summary["oos_result_summary"] == {
        "state": "available",
        "completed_fold_count": 3,
        "missing_result_fold_count": 0,
        "metric_keys": ["total_return_pct", "max_drawdown_pct", "win_rate_pct", "trade_count"],
        "metric_aggregates": {
            "total_return_pct": {
                "count": 3,
                "min": 1.0,
                "max": 3.0,
                "mean": 2.0,
            },
            "max_drawdown_pct": {
                "count": 3,
                "min": 1.0,
                "max": 2.5,
                "mean": 1.666667,
            },
            "win_rate_pct": {
                "count": 3,
                "min": 25.0,
                "max": 75.0,
                "mean": 50.0,
            },
            "trade_count": {
                "count": 3,
                "min": 2.0,
                "max": 4.0,
                "mean": 3.0,
            },
        },
    }
    assert summary["fold_results"][0]["metrics"]["total_return_pct"] == 1.0
    assert summary["fold_results"][1]["metrics"]["total_return_pct"] == 2.0
    assert summary["fold_results"][2]["metrics"]["total_return_pct"] == 3.0


def test_build_walk_forward_oos_validation_plan_reports_insufficient_data_when_windows_cannot_start() -> None:
    observations = _make_observations(_date_range(date(2024, 1, 1), 5))

    plan = build_walk_forward_oos_validation_plan(
        observations=observations,
        strategy_id="input-strategy",
        config={
            "train_window": 4,
            "test_window": 2,
            "step": 1,
        },
    )

    assert plan["state"] == "insufficient_data"
    assert plan["folds"] == []
    assert plan["insufficient_data"] == {
        "reason_code": "insufficient_observations_for_initial_fold",
        "required_observations": 6,
        "available_observations": 5,
        "train_window": 4,
        "test_window": 2,
    }
    assert plan["oos_result_summary"] == {
        "state": "insufficient_data",
        "completed_fold_count": 0,
        "missing_result_fold_count": 0,
        "metric_keys": ["total_return_pct", "max_drawdown_pct", "win_rate_pct", "trade_count"],
        "metric_aggregates": {},
    }


def test_walk_forward_oos_plan_is_deterministic_for_unsorted_inputs_and_stable_fold_ids() -> None:
    ordered_observations = _make_observations(_date_range(date(2024, 1, 1), 10))
    reversed_observations = list(reversed(ordered_observations))

    ordered_plan = build_walk_forward_oos_validation_plan(
        observations=ordered_observations,
        strategy_id="input-strategy",
        config={
            "train_window": 3,
            "test_window": 2,
            "step": 2,
            "max_folds": 3,
        },
    )
    reversed_plan = build_walk_forward_oos_validation_plan(
        observations=reversed_observations,
        strategy_id="input-strategy",
        config={
            "train_window": 3,
            "test_window": 2,
            "step": 2,
            "max_folds": 3,
        },
    )

    assert [fold["fold_id"] for fold in ordered_plan["folds"]] == [
        "wf_oos_fold_0001_train_20240101_20240103_test_20240104_20240105",
        "wf_oos_fold_0002_train_20240103_20240105_test_20240106_20240107",
        "wf_oos_fold_0003_train_20240105_20240107_test_20240108_20240109",
    ]
    assert [fold["fold_id"] for fold in reversed_plan["folds"]] == [fold["fold_id"] for fold in ordered_plan["folds"]]
    assert [fold["train_window"]["start_date"] for fold in reversed_plan["folds"]] == [
        "2024-01-01",
        "2024-01-03",
        "2024-01-05",
    ]


def test_walk_forward_oos_contract_metadata_is_diagnostic_only_and_not_optimizer() -> None:
    metadata = build_walk_forward_oos_contract_metadata(
        strategy_id="input-strategy",
        observation_count=12,
        train_window=4,
        test_window=2,
        step=3,
        max_folds=3,
    )

    assert metadata == {
        "contract_kind": "backtest_walk_forward_oos_validation_scaffold",
        "contract_version": WALK_FORWARD_OOS_CONTRACT_VERSION,
        "diagnostic_only": True,
        "optimizer_executed": False,
        "parameter_sweep_executed": False,
        "portfolio_allocation_backtest_executed": False,
        "engine_math_changed": False,
        "provider_behavior_changed": False,
        "strategy_selection_mode": "placeholder_input_strategy_reuse",
        "fold_ordering": "fold_index_ascending",
        "fold_id_policy": "stable_from_window_bounds",
    }


def test_walk_forward_oos_helpers_do_not_mutate_inputs() -> None:
    observations = _make_observations(_date_range(date(2024, 1, 1), 12))
    config = {
        "train_window": 4,
        "test_window": 2,
        "step": 3,
        "max_folds": 3,
    }
    fold_results = [
        {
            "fold_id": "wf_oos_fold_0001_train_20240101_20240104_test_20240105_20240106",
            "state": "completed",
            "metrics": {
                "total_return_pct": 1.0,
                "max_drawdown_pct": 1.0,
            },
        }
    ]
    observations_snapshot = copy.deepcopy(observations)
    config_snapshot = copy.deepcopy(config)
    fold_results_snapshot = copy.deepcopy(fold_results)

    plan = build_walk_forward_oos_validation_plan(
        observations=observations,
        strategy_id="input-strategy",
        config=config,
    )
    aggregate_walk_forward_oos_results(plan=plan, fold_results=fold_results)

    assert observations == observations_snapshot
    assert config == config_snapshot
    assert fold_results == fold_results_snapshot
