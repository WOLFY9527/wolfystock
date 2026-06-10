# -*- coding: utf-8 -*-
"""Contracts for the additive backtest parameter stability scaffold."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.services.backtest_parameter_stability import (
    PARAMETER_STABILITY_CONTRACT_VERSION,
    aggregate_parameter_stability_results,
    build_parameter_stability_evidence_from_compare_summary,
    build_parameter_stability_evidence_from_scenario_summary,
    build_parameter_stability_plan,
)


def _build_plan(
    *,
    parameter_grid: dict[str, list[Any]] | None = None,
    robust_region: dict[str, float] | None = None,
    min_completed_runs: int = 2,
) -> dict[str, Any]:
    return build_parameter_stability_plan(
        strategy_id="ma-cross-fixture",
        dataset_id="fixture-bars-v1",
        base_parameters={
            "strategy_spec.signal.fast_type": "simple",
            "strategy_spec.signal.slow_type": "simple",
        },
        parameter_grid=parameter_grid
        or {
            "strategy_spec.signal.slow_period": [50, 20],
            "strategy_spec.signal.fast_period": [10, 5],
        },
        metric_keys=["total_return_pct", "max_drawdown_pct", "sharpe_ratio"],
        primary_metric="total_return_pct",
        risk_metric="max_drawdown_pct",
        robust_region=robust_region,
        min_completed_runs=min_completed_runs,
    )


def _grid_row_by_values(plan: dict[str, Any], fast_period: int, slow_period: int) -> dict[str, Any]:
    for row in plan["grid_runs"]:
        if row["parameter_values"] == {
            "strategy_spec.signal.fast_period": fast_period,
            "strategy_spec.signal.slow_period": slow_period,
        }:
            return row
    raise AssertionError(f"missing grid row for fast={fast_period}, slow={slow_period}")


def _completed_results(plan: dict[str, Any]) -> list[dict[str, Any]]:
    metrics_by_values = {
        (5, 20): {"total_return_pct": 8.0, "max_drawdown_pct": 4.0, "sharpe_ratio": 0.8},
        (5, 50): {"total_return_pct": 12.0, "max_drawdown_pct": 5.0, "sharpe_ratio": 1.1},
        (10, 20): {"total_return_pct": 14.0, "max_drawdown_pct": 8.0, "sharpe_ratio": 1.3},
        (10, 50): {"total_return_pct": 10.0, "max_drawdown_pct": 3.0, "sharpe_ratio": 1.0},
    }
    rows: list[dict[str, Any]] = []
    for fast_period, slow_period in [(10, 50), (5, 20), (10, 20), (5, 50)]:
        grid_row = _grid_row_by_values(plan, fast_period, slow_period)
        rows.append(
            {
                "planned_run_id": grid_row["planned_run_id"],
                "state": "completed",
                "external_run_id": f"fixture-{fast_period}-{slow_period}",
                "metrics": metrics_by_values[(fast_period, slow_period)],
            }
        )
    return rows


def _assert_no_public_selection_terms(payload: dict[str, Any]) -> None:
    serialized = str(payload).lower()
    for forbidden in (
        "optimizer",
        "optimization",
        "grid_search",
        "grid search",
        "winner",
        "best",
        "recommended",
        "oos",
        "out_of_sample",
        "out-of-sample",
    ):
        assert forbidden not in serialized, forbidden


def test_parameter_grid_expansion_is_deterministic_and_diagnostic_only() -> None:
    plan = _build_plan()

    assert plan["contract_kind"] == "backtest_parameter_stability_surface_scaffold"
    assert plan["contract_version"] == PARAMETER_STABILITY_CONTRACT_VERSION
    assert plan["state"] == "ready"
    assert plan["grid_spec"]["parameter_count"] == 2
    assert plan["grid_spec"]["grid_size"] == 4
    assert plan["grid_spec"]["parameters"] == [
        {"parameter_key": "strategy_spec.signal.fast_period", "values": [5, 10]},
        {"parameter_key": "strategy_spec.signal.slow_period", "values": [20, 50]},
    ]
    assert [row["grid_index"] for row in plan["grid_runs"]] == [1, 2, 3, 4]
    assert [row["parameter_values"] for row in plan["grid_runs"]] == [
        {"strategy_spec.signal.fast_period": 5, "strategy_spec.signal.slow_period": 20},
        {"strategy_spec.signal.fast_period": 5, "strategy_spec.signal.slow_period": 50},
        {"strategy_spec.signal.fast_period": 10, "strategy_spec.signal.slow_period": 20},
        {"strategy_spec.signal.fast_period": 10, "strategy_spec.signal.slow_period": 50},
    ]
    assert plan["execution_semantics"] == {
        "execution_mode": "caller_supplied_results_only",
        "strategy_execution_count": 0,
        "provider_calls_executed": False,
        "hidden_optimizer_executed": False,
        "automatic_winner_promotion": False,
        "live_strategy_selection": False,
        "engine_math_changed": False,
        "runtime_defaults_changed": False,
        "portfolio_allocation_backtest_executed": False,
    }


def test_bounded_parameter_grid_descriptor_and_request_bundle_truncate_deterministically() -> None:
    plan = build_parameter_stability_plan(
        strategy_id="ma-cross-fixture",
        dataset_id="fixture-bars-v1",
        base_parameters={"strategy_spec.signal.fast_type": "simple"},
        parameter_grid={
            "strategy_spec.signal.slow_period": [50, 20],
            "strategy_spec.signal.fast_period": [10, 5],
            "strategy_spec.risk.stop_loss_pct": [2, 1],
        },
        metric_keys=["total_return_pct", "max_drawdown_pct"],
        max_combinations=5,
        overflow_policy="truncate",
    )

    descriptor = plan["parameter_grid_descriptor"]
    request_bundle = plan["parameter_grid_request_bundle"]

    assert descriptor["contract_kind"] == "backtest_parameter_grid_descriptor_request_bundle"
    assert descriptor["contract_version"] == PARAMETER_STABILITY_CONTRACT_VERSION
    assert descriptor["state"] == "truncated"
    assert descriptor["diagnostic_only"] is True
    assert descriptor["execution_count"] == 0
    assert descriptor["optimizer_executed"] is False
    assert descriptor["winner_promotion"] is False
    assert descriptor["decision_grade"] is False
    assert descriptor["boundedness"] == {
        "max_combinations": 5,
        "requested_combinations": 8,
        "accepted_combinations": 5,
        "overflow_policy": "truncate",
        "truncated": True,
        "rejected": False,
        "reason_code": "max_combinations_truncated",
    }
    assert descriptor["parameter_ordering"] == "parameter_key_ascending"
    assert descriptor["value_ordering"] == "canonical_value_ascending"
    assert descriptor["request_bundle_id"] == request_bundle["request_bundle_id"]
    assert len(descriptor["grid_descriptor_hash_sha256"]) == 64
    assert plan["grid_spec"]["requested_grid_size"] == 8
    assert plan["grid_spec"]["grid_size"] == 5
    assert [row["parameter_values"] for row in plan["grid_runs"]] == [
        {
            "strategy_spec.risk.stop_loss_pct": 1,
            "strategy_spec.signal.fast_period": 5,
            "strategy_spec.signal.slow_period": 20,
        },
        {
            "strategy_spec.risk.stop_loss_pct": 1,
            "strategy_spec.signal.fast_period": 5,
            "strategy_spec.signal.slow_period": 50,
        },
        {
            "strategy_spec.risk.stop_loss_pct": 1,
            "strategy_spec.signal.fast_period": 10,
            "strategy_spec.signal.slow_period": 20,
        },
        {
            "strategy_spec.risk.stop_loss_pct": 1,
            "strategy_spec.signal.fast_period": 10,
            "strategy_spec.signal.slow_period": 50,
        },
        {
            "strategy_spec.risk.stop_loss_pct": 2,
            "strategy_spec.signal.fast_period": 5,
            "strategy_spec.signal.slow_period": 20,
        },
    ]
    assert request_bundle["state"] == "truncated"
    assert request_bundle["execution_count"] == 0
    assert request_bundle["optimizer_executed"] is False
    assert request_bundle["winner_promotion"] is False
    assert request_bundle["decision_grade"] is False
    assert request_bundle["requests"] == [
        {
            "request_index": row["grid_index"],
            "planned_run_id": row["planned_run_id"],
            "parameter_values": row["parameter_values"],
            "execution_count": 0,
            "optimizer_executed": False,
            "winner_promotion": False,
            "decision_grade": False,
        }
        for row in plan["grid_runs"]
    ]

    shuffled = build_parameter_stability_plan(
        strategy_id="ma-cross-fixture",
        dataset_id="fixture-bars-v1",
        base_parameters={"strategy_spec.signal.fast_type": "simple"},
        parameter_grid={
            "strategy_spec.risk.stop_loss_pct": [1, 2],
            "strategy_spec.signal.fast_period": [5, 10],
            "strategy_spec.signal.slow_period": [20, 50],
        },
        metric_keys=["max_drawdown_pct", "total_return_pct"],
        max_combinations=5,
        overflow_policy="truncate",
    )
    assert shuffled["parameter_grid_descriptor"] == descriptor
    assert shuffled["parameter_grid_request_bundle"] == request_bundle


def test_bounded_parameter_grid_descriptor_can_reject_over_limit_without_requests() -> None:
    plan = build_parameter_stability_plan(
        strategy_id="ma-cross-fixture",
        dataset_id="fixture-bars-v1",
        parameter_grid={
            "strategy_spec.signal.fast_period": [5, 10],
            "strategy_spec.signal.slow_period": [20, 50],
        },
        max_combinations=3,
        overflow_policy="reject",
    )

    descriptor = plan["parameter_grid_descriptor"]
    request_bundle = plan["parameter_grid_request_bundle"]

    assert plan["state"] == "insufficient_data"
    assert plan["grid_spec"]["requested_grid_size"] == 4
    assert plan["grid_spec"]["grid_size"] == 0
    assert plan["grid_runs"] == []
    assert plan["insufficient_data"] == {
        "reason_code": "max_combinations_rejected",
        "max_combinations": 3,
        "requested_combinations": 4,
        "available_grid_points": 0,
    }
    assert descriptor["state"] == "rejected"
    assert descriptor["boundedness"] == {
        "max_combinations": 3,
        "requested_combinations": 4,
        "accepted_combinations": 0,
        "overflow_policy": "reject",
        "truncated": False,
        "rejected": True,
        "reason_code": "max_combinations_rejected",
    }
    assert descriptor["execution_count"] == 0
    assert descriptor["optimizer_executed"] is False
    assert descriptor["winner_promotion"] is False
    assert descriptor["decision_grade"] is False
    assert request_bundle["state"] == "rejected"
    assert request_bundle["requests"] == []
    assert request_bundle["execution_count"] == 0
    assert request_bundle["optimizer_executed"] is False
    assert request_bundle["winner_promotion"] is False
    assert request_bundle["decision_grade"] is False


def test_stable_run_ids_and_ordering_ignore_input_order_and_change_with_values() -> None:
    ordered_plan = _build_plan(
        parameter_grid={
            "strategy_spec.signal.fast_period": [5, 10],
            "strategy_spec.signal.slow_period": [20, 50],
        }
    )
    shuffled_plan = _build_plan(
        parameter_grid={
            "strategy_spec.signal.slow_period": [50, 20],
            "strategy_spec.signal.fast_period": [10, 5],
        }
    )
    changed_plan = _build_plan(
        parameter_grid={
            "strategy_spec.signal.fast_period": [6],
            "strategy_spec.signal.slow_period": [20],
        }
    )

    ordered_ids = [row["planned_run_id"] for row in ordered_plan["grid_runs"]]
    shuffled_ids = [row["planned_run_id"] for row in shuffled_plan["grid_runs"]]
    assert shuffled_ids == ordered_ids
    assert len(set(ordered_ids)) == 4
    assert all(run_id.startswith("bt_param_stability_") for run_id in ordered_ids)
    assert [row["parameter_values"] for row in shuffled_plan["grid_runs"]] == [
        row["parameter_values"] for row in ordered_plan["grid_runs"]
    ]
    assert changed_plan["grid_runs"][0]["planned_run_id"] != ordered_plan["grid_runs"][0]["planned_run_id"]


def test_metric_surface_aggregates_caller_supplied_results_without_execution() -> None:
    plan = _build_plan()

    surface = aggregate_parameter_stability_results(
        plan=plan,
        run_results=_completed_results(plan),
    )

    assert surface["state"] == "available"
    assert surface["execution_semantics"]["strategy_execution_count"] == 0
    assert surface["metric_surface"]["row_order"] == [row["planned_run_id"] for row in plan["grid_runs"]]
    assert [row["planned_run_id"] for row in surface["metric_surface"]["rows"]] == surface["metric_surface"]["row_order"]
    assert surface["metric_surface"]["metric_aggregates"]["total_return_pct"] == {
        "count": 4,
        "min": 8.0,
        "max": 14.0,
        "mean": 11.0,
    }
    assert surface["metric_surface"]["metric_aggregates"]["max_drawdown_pct"] == {
        "count": 4,
        "min": 3.0,
        "max": 8.0,
        "mean": 5.0,
    }
    best_run = _grid_row_by_values(plan, 10, 20)
    assert surface["best_summary"] == {
        "state": "available",
        "selection_rule": "diagnostic_primary_metric_leader_only",
        "primary_metric": "total_return_pct",
        "preference": "higher_is_better",
        "candidate_count": 4,
        "best_run_ids": [best_run["planned_run_id"]],
        "best_value": 14.0,
        "automatic_winner_promotion": False,
        "live_strategy_selection": False,
    }


def test_robust_region_summary_uses_explicit_thresholds_without_promoting_winners() -> None:
    plan = _build_plan(robust_region={"primary_metric_min": 10.0, "risk_metric_max": 5.0})

    surface = aggregate_parameter_stability_results(
        plan=plan,
        run_results=_completed_results(plan),
    )

    robust = surface["robust_region_summary"]
    assert robust["state"] == "available"
    assert robust["selection_rule"] == "configured_threshold_filter"
    assert robust["thresholds"] == {
        "primary_metric_min": 10.0,
        "risk_metric_max": 5.0,
    }
    assert robust["member_run_ids"] == [
        _grid_row_by_values(plan, 5, 50)["planned_run_id"],
        _grid_row_by_values(plan, 10, 50)["planned_run_id"],
    ]
    assert robust["parameter_ranges"] == {
        "strategy_spec.signal.fast_period": {"min": 5, "max": 10, "values": [5, 10]},
        "strategy_spec.signal.slow_period": {"min": 50, "max": 50, "values": [50]},
    }
    assert robust["automatic_winner_promotion"] is False
    assert robust["live_strategy_selection"] is False


def test_missing_metrics_and_insufficient_runs_are_reported_explicitly() -> None:
    plan = _build_plan(
        parameter_grid={
            "strategy_spec.signal.fast_period": [5, 10],
            "strategy_spec.signal.slow_period": [20],
        },
        min_completed_runs=2,
    )
    completed_row = _grid_row_by_values(plan, 5, 20)

    surface = aggregate_parameter_stability_results(
        plan=plan,
        run_results=[
            {
                "planned_run_id": completed_row["planned_run_id"],
                "state": "completed",
                "metrics": {"total_return_pct": 3.0},
            }
        ],
    )

    assert surface["state"] == "insufficient_results"
    assert surface["insufficient_data"] == {
        "reason_code": "insufficient_completed_runs",
        "required_completed_runs": 2,
        "completed_run_count": 1,
        "missing_result_run_count": 1,
    }
    rows = surface["metric_surface"]["rows"]
    assert rows[0]["metrics"]["max_drawdown_pct"] == {"state": "missing_metric", "value": None}
    assert rows[1]["state"] == "missing_result"
    assert surface["metric_surface"]["missing_metric_counts"]["max_drawdown_pct"] == 1
    assert surface["metric_surface"]["missing_result_run_count"] == 1
    assert surface["robust_region_summary"]["state"] == "not_configured"


def test_parameter_stability_helpers_do_not_mutate_inputs() -> None:
    base_parameters = {
        "strategy_spec.signal.fast_type": "simple",
        "nested": {"keep": ["original"]},
    }
    parameter_grid = {
        "strategy_spec.signal.fast_period": [5, 10],
        "strategy_spec.signal.slow_period": [20],
    }
    plan = build_parameter_stability_plan(
        strategy_id="ma-cross-fixture",
        dataset_id="fixture-bars-v1",
        base_parameters=base_parameters,
        parameter_grid=parameter_grid,
        metric_keys=["total_return_pct", "max_drawdown_pct"],
    )
    run_results = [
        {
            "planned_run_id": plan["grid_runs"][0]["planned_run_id"],
            "state": "completed",
            "metrics": {"total_return_pct": 1.0, "max_drawdown_pct": 2.0},
        }
    ]
    base_snapshot = deepcopy(base_parameters)
    grid_snapshot = deepcopy(parameter_grid)
    results_snapshot = deepcopy(run_results)
    plan_snapshot = deepcopy(plan)

    aggregate_parameter_stability_results(plan=plan, run_results=run_results)

    assert base_parameters == base_snapshot
    assert parameter_grid == grid_snapshot
    assert run_results == results_snapshot
    assert plan == plan_snapshot


def test_compare_summary_adapter_outputs_diagnostic_evidence_without_selection_terms() -> None:
    compare_summary = {
        "comparison_source": "stored_rule_backtest_runs",
        "read_mode": "stored_first",
        "requested_run_ids": [101, 202, 999],
        "resolved_run_ids": [101, 202],
        "comparable_run_ids": [101, 202],
        "missing_run_ids": [999],
        "unavailable_runs": [],
        "parameter_comparison": {
            "state": "same_family_comparable",
            "differing_parameter_keys": [
                "strategy_spec.signal.fast_period",
                "strategy_spec.signal.slow_period",
            ],
        },
        "items": [
            {
                "metadata": {"id": 101, "status": "completed"},
                "parsed_strategy": {
                    "strategy_spec": {
                        "strategy_family": "moving_average_crossover",
                        "strategy_type": "moving_average_crossover",
                        "signal": {"fast_period": 5, "slow_period": 20},
                    }
                },
                "metrics": {
                    "total_return_pct": 12.4,
                    "max_drawdown_pct": 5.2,
                    "sharpe_ratio": 1.1,
                },
            },
            {
                "metadata": {"id": 202, "status": "completed"},
                "parsed_strategy": {
                    "strategy_spec": {
                        "strategy_family": "moving_average_crossover",
                        "strategy_type": "moving_average_crossover",
                        "signal": {"fast_period": 10, "slow_period": 30},
                    }
                },
                "metrics": {
                    "total_return_pct": 14.6,
                    "max_drawdown_pct": 6.0,
                    "sharpe_ratio": 1.3,
                },
            },
        ],
    }

    evidence = build_parameter_stability_evidence_from_compare_summary(compare_summary)

    assert evidence["contract_kind"] == "backtest_parameter_stability_diagnostic_evidence"
    assert evidence["contract_version"] == PARAMETER_STABILITY_CONTRACT_VERSION
    assert evidence["source"] == "stored_compare_summary"
    assert evidence["read_mode"] == "stored_first"
    assert evidence["diagnostic_only"] is True
    assert evidence["decision_grade"] is False
    assert evidence["parameter_keys"] == [
        "strategy_spec.signal.fast_period",
        "strategy_spec.signal.slow_period",
    ]
    assert evidence["parameter_set_count"] == 2
    assert evidence["compatible_run_coverage"] == {
        "requested_run_count": 3,
        "resolved_run_count": 2,
        "compatible_run_count": 2,
        "missing_run_count": 1,
        "skipped_run_count": 0,
        "compatible_run_ids": [101, 202],
        "missing_run_ids": [999],
        "skipped_run_ids": [],
    }
    assert evidence["missing_run_diagnostics"] == [{"run_id": 999, "reason": "missing_run"}]
    assert evidence["metric_dispersion"]["total_return_pct"] == {
        "state": "available",
        "count": 2,
        "min": 12.4,
        "max": 14.6,
        "mean": 13.5,
        "range": 2.2,
    }
    assert evidence["metric_dispersion"]["max_drawdown_pct"]["range"] == 0.8
    assert evidence["authority"] == {
        "input_mode": "stored_compare_summary",
        "execution_count": 0,
        "strategy_execution_count": 0,
        "provider_calls_executed": False,
        "engine_math_changed": False,
        "strategy_parameters_mutated": False,
    }
    assert "best_summary" not in evidence
    _assert_no_public_selection_terms(evidence)


def test_compare_summary_adapter_reports_skipped_and_missing_parameter_sets() -> None:
    compare_summary = {
        "requested_run_ids": [101, 202, 303],
        "resolved_run_ids": [101, 202, 303],
        "comparable_run_ids": [101, 202],
        "missing_run_ids": [],
        "parameter_comparison": {
            "state": "partial",
            "differing_parameter_keys": ["strategy_spec.signal.fast_period"],
        },
        "items": [
            {
                "metadata": {"id": 101, "status": "completed"},
                "parsed_strategy": {"strategy_spec": {"signal": {"fast_period": 5}}},
                "metrics": {"total_return_pct": 12.0, "max_drawdown_pct": 4.0},
            },
            {
                "metadata": {"id": 202, "status": "completed"},
                "parsed_strategy": {"strategy_spec": {"signal": {"fast_period": 10}}},
                "metrics": {"total_return_pct": 13.0},
            },
            {
                "metadata": {"id": 303, "status": "failed"},
                "parsed_strategy": {"strategy_spec": {"signal": {"fast_period": 15}}},
                "metrics": {"total_return_pct": 14.0, "max_drawdown_pct": 6.0},
            },
        ],
    }

    evidence = build_parameter_stability_evidence_from_compare_summary(compare_summary)

    assert evidence["state"] == "available"
    assert evidence["parameter_set_count"] == 2
    assert evidence["compatible_run_coverage"]["skipped_run_ids"] == [303]
    assert evidence["skipped_run_diagnostics"] == [
        {"run_id": 303, "reason": "run_not_completed", "status": "failed"}
    ]
    assert evidence["metric_dispersion"]["max_drawdown_pct"] == {
        "state": "available",
        "count": 1,
        "min": 4.0,
        "max": 4.0,
        "mean": 4.0,
        "range": 0.0,
    }
    assert evidence["metric_missing_counts"]["max_drawdown_pct"] == 1
    _assert_no_public_selection_terms(evidence)


def test_scenario_summary_adapter_reuses_parameter_stability_helpers() -> None:
    evidence = build_parameter_stability_evidence_from_scenario_summary(
        {
            "scenarios": [
                {
                    "scenario_key": "base_path",
                    "metrics": {"total_return_pct": 5.0, "max_drawdown_pct": 2.0},
                },
                {
                    "scenario_key": "stress_down",
                    "metrics": {"total_return_pct": -3.0, "max_drawdown_pct": 8.0},
                },
            ],
        }
    )

    assert evidence["source"] == "stored_scenario_summary"
    assert evidence["parameter_keys"] == ["scenario_key"]
    assert evidence["parameter_set_count"] == 2
    assert evidence["metric_dispersion"]["total_return_pct"]["range"] == 8.0
    assert evidence["authority"]["input_mode"] == "stored_scenario_summary"
    _assert_no_public_selection_terms(evidence)
