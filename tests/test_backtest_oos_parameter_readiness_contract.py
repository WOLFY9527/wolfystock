# -*- coding: utf-8 -*-
"""Fixture-only contract for OOS and parameter-readiness backtest evidence."""

from __future__ import annotations

import copy
import json

from src.services.backtest_parameter_stability import (
    build_parameter_stability_evidence_from_compare_summary,
)
from src.services.backtest_walkforward_oos import (
    build_walk_forward_oos_evidence_from_stored_robustness,
)


def _assert_no_promoted_selection_terms(payload: dict) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    for forbidden in (
        "winner",
        "recommended",
        "selected_strategy",
        "optimized_parameters",
        "decision-ready",
        "decision ready",
    ):
        assert forbidden not in serialized, forbidden


def test_oos_and_parameter_readiness_evidence_stay_fixture_only_and_diagnostic() -> None:
    stored_robustness = {
        "source": "summary.robustness_analysis",
        "configuration": {
            "walk_forward": {
                "train_window": 40,
                "test_window": 10,
                "step": 10,
                "max_windows": 2,
            }
        },
        "walk_forward": {
            "state": "available",
            "windows": [
                {
                    "window_index": 2,
                    "train_start": "2024-02-01",
                    "train_end": "2024-03-11",
                    "test_start": "2024-03-12",
                    "test_end": "2024-03-21",
                    "state": "completed",
                    "metrics": {
                        "total_return_pct": 1.5,
                        "max_drawdown_pct": 2.0,
                        "win_rate_pct": 50.0,
                        "trade_count": 2,
                    },
                },
                {
                    "window_index": 1,
                    "train_start": "2024-01-01",
                    "train_end": "2024-02-09",
                    "test_start": "2024-02-10",
                    "test_end": "2024-02-19",
                    "state": "completed",
                    "metrics": {
                        "total_return_pct": 2.5,
                        "max_drawdown_pct": 1.0,
                        "win_rate_pct": 100.0,
                        "trade_count": 1,
                    },
                },
            ],
            "diagnostics": [],
        },
    }
    compare_summary = {
        "read_mode": "stored_first",
        "requested_run_ids": [7001, 7002, 7999],
        "resolved_run_ids": [7001, 7002],
        "missing_run_ids": [7999],
        "parameter_comparison": {
            "state": "same_family_comparable",
            "differing_parameter_keys": [
                "strategy_spec.signal.fast_period",
                "strategy_spec.signal.slow_period",
            ],
        },
        "items": [
            {
                "metadata": {"id": 7001, "status": "completed"},
                "parsed_strategy": {
                    "strategy_spec": {
                        "strategy_family": "moving_average_crossover",
                        "strategy_type": "moving_average_crossover",
                        "signal": {"fast_period": 5, "slow_period": 20},
                    }
                },
                "metrics": {
                    "total_return_pct": 8.0,
                    "max_drawdown_pct": 4.0,
                    "trade_count": 3,
                },
            },
            {
                "metadata": {"id": 7002, "status": "completed"},
                "parsed_strategy": {
                    "strategy_spec": {
                        "strategy_family": "moving_average_crossover",
                        "strategy_type": "moving_average_crossover",
                        "signal": {"fast_period": 10, "slow_period": 50},
                    }
                },
                "metrics": {
                    "total_return_pct": 12.0,
                    "max_drawdown_pct": 5.0,
                    "trade_count": 4,
                },
            },
        ],
    }
    robustness_snapshot = copy.deepcopy(stored_robustness)
    compare_snapshot = copy.deepcopy(compare_summary)

    oos_evidence = build_walk_forward_oos_evidence_from_stored_robustness(
        stored_robustness,
        run_metadata={"id": 9001},
    )
    parameter_evidence = build_parameter_stability_evidence_from_compare_summary(
        compare_summary,
    )

    assert stored_robustness == robustness_snapshot
    assert compare_summary == compare_snapshot

    assert oos_evidence["contract_kind"] == "backtest_walk_forward_oos_diagnostic_evidence"
    assert oos_evidence["source"] == "stored_robustness_analysis.walk_forward"
    assert oos_evidence["read_mode"] == "stored_first"
    assert oos_evidence["source_run_id"] == 9001
    assert oos_evidence["source_run_ids"] == [9001]
    assert oos_evidence["diagnostic_only"] is True
    assert oos_evidence["decision_grade"] is False
    assert oos_evidence["fold_order"] == [
        "wf_oos_fold_0001_train_20240101_20240209_test_20240210_20240219",
        "wf_oos_fold_0002_train_20240201_20240311_test_20240312_20240321",
    ]
    assert oos_evidence["oos_result_summary"]["completed_fold_count"] == 2
    assert oos_evidence["authority"] == {
        "input_mode": "stored_robustness_analysis_walk_forward",
        "adapter_execution_count": 0,
        "new_strategy_execution_count": 0,
        "optimizer_executed": False,
        "parameter_sweep_executed": False,
        "provider_calls_executed": False,
        "engine_math_changed": False,
        "strategy_parameters_mutated": False,
    }

    assert parameter_evidence["contract_kind"] == "backtest_parameter_stability_diagnostic_evidence"
    assert parameter_evidence["source"] == "stored_compare_summary"
    assert parameter_evidence["read_mode"] == "stored_first"
    assert parameter_evidence["diagnostic_only"] is True
    assert parameter_evidence["decision_grade"] is False
    assert parameter_evidence["parameter_keys"] == [
        "strategy_spec.signal.fast_period",
        "strategy_spec.signal.slow_period",
    ]
    assert parameter_evidence["parameter_set_count"] == 2
    assert parameter_evidence["compatible_run_coverage"] == {
        "requested_run_count": 3,
        "resolved_run_count": 2,
        "compatible_run_count": 2,
        "missing_run_count": 1,
        "skipped_run_count": 0,
        "compatible_run_ids": [7001, 7002],
        "missing_run_ids": [7999],
        "skipped_run_ids": [],
    }
    assert parameter_evidence["missing_run_diagnostics"] == [
        {"run_id": 7999, "reason": "missing_run"},
    ]
    assert parameter_evidence["authority"] == {
        "input_mode": "stored_compare_summary",
        "execution_count": 0,
        "strategy_execution_count": 0,
        "provider_calls_executed": False,
        "engine_math_changed": False,
        "strategy_parameters_mutated": False,
    }
    assert "best_summary" not in parameter_evidence

    _assert_no_promoted_selection_terms(oos_evidence)
    _assert_no_promoted_selection_terms(parameter_evidence)
