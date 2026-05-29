# -*- coding: utf-8 -*-
"""Fixture-only contract for backtest stress / Monte Carlo readiness evidence."""

from __future__ import annotations

import json
from copy import deepcopy

from src.services.rule_backtest_support_exports import (
    resolve_stored_robustness_evidence_payload,
)


def _assert_no_forbidden_semantics(payload: dict) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    for forbidden in (
        '"decision_grade": true',
        '"professional_quant_readiness_claimed": true',
        '"provider_calls_executed": true',
        "provider-backed replay",
        "provider_backed_replay",
        "institutional stress engine",
        "calibrated institutional",
        "liquidity tail",
        "regime tail",
        "parameter_sweep_executed\": true",
        "winner_run_ids",
        "winner_value",
        "selected_strategy",
        "strategy_execution_count\": 1",
        "automatic_winner_promotion\": true",
    ):
        assert forbidden not in serialized, forbidden


def test_stress_and_monte_carlo_readiness_stay_stored_projection_only_and_diagnostic() -> None:
    run = {
        "id": 676,
        "code": "600519",
        "timeframe": "1d",
        "period_start": "2024-01-02",
        "period_end": "2024-04-30",
        "summary": {
            "robustness_analysis": {
                "state": "research_prototype",
                "profile": "single_symbol_fixture",
                "source": "summary.robustness_analysis",
                "seed": 20260529,
                "contract_metadata": {
                    "diagnostic_only": True,
                    "parameter_selection_executed": False,
                    "parameter_sweep_executed": False,
                    "provider_calls_executed": False,
                    "portfolio_allocation_backtest_executed": False,
                    "professional_quant_readiness_claimed": False,
                    "walk_forward_validation_claimed": False,
                    "input_strategy_policy": "reuse_input_strategy_without_parameter_search",
                },
                "configuration": {
                    "walk_forward": {
                        "train_window": 36,
                        "test_window": 18,
                        "step": 9,
                        "max_windows": 2,
                    },
                    "monte_carlo": {
                        "simulation_count": 4,
                        "noise_scale": 0.5,
                        "seed": 20260529,
                    },
                    "stress_tests": {
                        "scenario_keys": [
                            "single_day_shock_down_15",
                            "volatility_whipsaw",
                        ],
                    },
                },
                "walk_forward": {
                    "analysis_mode": "diagnostic_replay",
                    "window_count": 1,
                    "windows": [
                        {
                            "window_index": 1,
                            "state": "completed",
                            "train_start": "2024-01-02",
                            "train_end": "2024-03-01",
                            "test_start": "2024-03-02",
                            "test_end": "2024-03-20",
                            "metrics": {
                                "total_return_pct": 2.1,
                                "max_drawdown_pct": 3.7,
                                "trade_count": 2,
                            },
                        }
                    ],
                    "aggregate_metrics": {"median_total_return_pct": 2.1},
                    "diagnostics": [],
                },
                "monte_carlo": {
                    "state": "available",
                    "simulation_count": 2,
                    "paths": [
                        {
                            "simulation_index": 1,
                            "state": "completed",
                            "metrics": {
                                "total_return_pct": 1.9,
                                "max_drawdown_pct": 4.8,
                            },
                        },
                        {
                            "simulation_index": 2,
                            "state": "completed",
                            "metrics": {
                                "total_return_pct": 2.4,
                                "max_drawdown_pct": 4.2,
                            },
                        },
                    ],
                    "aggregate_metrics": {
                        "total_return_pct": {"count": 2, "min": 1.9, "max": 2.4, "mean": 2.15},
                        "max_drawdown_pct": {"count": 2, "min": 4.2, "max": 4.8, "mean": 4.5},
                    },
                    "diagnostics": [],
                },
                "stress_tests": {
                    "state": "available",
                    "scenario_count": 2,
                    "scenarios": [
                        {
                            "scenario_key": "single_day_shock_down_15",
                            "label": "Single-day shock down 15%",
                            "state": "completed",
                            "metrics": {
                                "total_return_pct": -1.2,
                                "max_drawdown_pct": 6.4,
                            },
                        },
                        {
                            "scenario_key": "volatility_whipsaw",
                            "label": "Volatility whipsaw regime",
                            "state": "completed",
                            "metrics": {
                                "total_return_pct": 0.8,
                                "max_drawdown_pct": 5.1,
                            },
                        },
                    ],
                    "worst_scenario": {
                        "scenario_key": "single_day_shock_down_15",
                        "label": "Single-day shock down 15%",
                        "state": "completed",
                        "metrics": {
                            "total_return_pct": -1.2,
                            "max_drawdown_pct": 6.4,
                        },
                    },
                    "diagnostics": [],
                },
                "diagnostics": [],
            }
        },
    }
    original = deepcopy(run)
    expected_projection = deepcopy(run["summary"]["robustness_analysis"])

    payload = resolve_stored_robustness_evidence_payload(run)

    assert run == original
    assert payload["source"] == "summary.robustness_analysis"
    assert payload["state"] == "research_prototype"
    assert payload["monte_carlo"] == expected_projection["monte_carlo"]
    assert payload["stress_tests"] == expected_projection["stress_tests"]
    assert payload["configuration"]["stress_tests"]["scenario_keys"] == [
        "single_day_shock_down_15",
        "volatility_whipsaw",
    ]
    assert payload["stress_tests"]["worst_scenario"]["scenario_key"] == "single_day_shock_down_15"

    metadata = payload["contract_metadata"]
    assert metadata == {
        "diagnostic_only": True,
        "parameter_selection_executed": False,
        "parameter_sweep_executed": False,
        "provider_calls_executed": False,
        "portfolio_allocation_backtest_executed": False,
        "professional_quant_readiness_claimed": False,
        "walk_forward_validation_claimed": False,
        "input_strategy_policy": "reuse_input_strategy_without_parameter_search",
    }

    monte_carlo = payload["monte_carlo"]
    assert monte_carlo["state"] == "available"
    assert monte_carlo["simulation_count"] == 2
    assert [path["simulation_index"] for path in monte_carlo["paths"]] == [1, 2]
    assert monte_carlo["aggregate_metrics"]["total_return_pct"]["count"] == 2
    assert "calibration_model" not in monte_carlo
    assert "liquidity_tail_model" not in monte_carlo
    assert "regime_tail_model" not in monte_carlo

    stress_tests = payload["stress_tests"]
    assert stress_tests["state"] == "available"
    assert stress_tests["scenario_count"] == 2
    assert [scenario["scenario_key"] for scenario in stress_tests["scenarios"]] == [
        "single_day_shock_down_15",
        "volatility_whipsaw",
    ]
    assert "calibration_model" not in stress_tests
    assert "liquidity_tail_calibration" not in stress_tests
    assert "regime_tail_calibration" not in stress_tests

    oos_evidence = payload["walk_forward_oos_evidence"]
    assert oos_evidence["contract_kind"] == "backtest_walk_forward_oos_diagnostic_evidence"
    assert oos_evidence["read_mode"] == "stored_first"
    assert oos_evidence["diagnostic_only"] is True
    assert oos_evidence["decision_grade"] is False
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

    _assert_no_forbidden_semantics(payload)
