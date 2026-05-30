# -*- coding: utf-8 -*-
"""Regression tests for backtest endpoint contracts."""

from __future__ import annotations

import json
import unittest
import warnings
from unittest.mock import MagicMock, patch

from fastapi import BackgroundTasks, HTTPException
from fastapi.routing import APIRoute

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from api.v1.endpoints.backtest import (  # noqa: E402
    clear_backtest_samples,
    cancel_rule_backtest_run,
    compare_rule_backtest_runs,
    create_rule_backtest_universe_job,
    get_backtest_performance,
    get_backtest_stock_performance,
    get_rule_backtest_oos_parameter_readiness_json,
    get_rule_backtest_robustness_evidence_json,
    get_rule_backtest_regime_attribution_readiness_json,
    get_rule_backtest_execution_trace_csv,
    get_rule_backtest_execution_trace_json,
    get_rule_backtest_support_bundle_reproducibility_manifest,
    parse_rule_strategy,
    get_rule_backtest_run,
    get_rule_backtest_runs,
    get_rule_backtest_support_export_index,
    get_rule_backtest_support_bundle_manifest,
    get_rule_backtest_run_status,
    get_rule_backtest_universe_job_diagnostics,
    get_rule_backtest_universe_job_status,
    list_rule_backtest_universe_job_results,
    router as backtest_router,
    run_rule_backtest,
    run_rule_backtest_universe_job,
)
from api.v1.schemas.backtest import (  # noqa: E402
    BacktestCodeRequest,
    RuleBacktestCancelResponse,
    RuleBacktestCompareRequest,
    RuleBacktestCompareResponse,
    RuleBacktestHistoryResponse,
    RuleBacktestParseRequest,
    RuleBacktestParseResponse,
    RuleBacktestRunRequest,
    RuleBacktestRunResponse,
    RuleBacktestStatusResponse,
    RuleBacktestUniverseJobCreateRequest,
    RuleBacktestUniverseJobDiagnostics,
    RuleBacktestUniverseJobResponse,
    RuleBacktestUniverseResultsResponse,
    RuleBacktestExecutionTraceExportResponse,
    RuleBacktestOOSParameterReadinessExportResponse,
    RuleBacktestRegimeAttributionReadinessExportResponse,
    RuleBacktestRobustnessEvidenceExportResponse,
    RuleBacktestSupportExportIndexResponse,
    RuleBacktestSupportBundleManifestResponse,
    RuleBacktestSupportBundleReproducibilityManifestResponse,
)

EXPECTED_TRACE_EXPORT_JSON_KEYS = [
    "version",
    "source",
    "completeness",
    "missing_fields",
    "trace_rows",
    "assumptions",
    "execution_model",
    "execution_assumptions",
    "benchmark_summary",
    "fallback",
]

EXPECTED_TRACE_EXPORT_FIELD_LABELS = [
    "日期",
    "标的收盘价",
    "基准收盘价",
    "信号摘要",
    "动作",
    "成交价",
    "持股数",
    "现金",
    "持仓市值",
    "总资产",
    "当日盈亏",
    "当日收益率",
    "策略累计收益率",
    "基准累计收益率",
    "买入持有累计收益率",
    "仓位",
    "手续费",
    "滑点",
    "备注",
    "assumptions",
    "fallback",
]

FORBIDDEN_ROBUSTNESS_OPTIMIZER_TERMS = (
    "optimizer",
    "optimization",
    "parameter_tuning",
    "parameter tuning",
    "auto_tune",
    "auto-tune",
    "grid_search",
    "grid search",
    "winner",
    "winner_selection",
    "winner selection",
    "selected_parameters",
    "selected parameters",
    "trained_parameters",
    "trained parameters",
    "parameter_training",
    "parameter training",
    "training_score",
    "training score",
)


class BacktestApiContractTestCase(unittest.TestCase):
    @staticmethod
    def _payload_without_allowed_oos_authority_flags(payload: dict) -> dict:
        normalized = json.loads(json.dumps(payload, ensure_ascii=False))
        evidence = normalized.get("walk_forward_oos_evidence")
        if isinstance(evidence, dict):
            authority = evidence.get("authority")
            if isinstance(authority, dict) and authority.get("optimizer_executed") is False:
                authority.pop("optimizer_executed")
        return normalized

    @staticmethod
    def _assert_robustness_payload_stays_research_prototype(payload: dict) -> None:
        assert payload["state"] == "research_prototype"
        assert payload["source"] == "summary.robustness_analysis"
        assert "professional_quant_ready" not in payload

        contract_metadata = dict(payload.get("contract_metadata") or {})
        assert contract_metadata.get("diagnostic_only") is True
        assert contract_metadata.get("parameter_selection_executed") is False
        assert contract_metadata.get("parameter_sweep_executed") is False
        assert contract_metadata.get("provider_calls_executed") is False
        assert contract_metadata.get("portfolio_allocation_backtest_executed") is False
        assert contract_metadata.get("professional_quant_readiness_claimed") is False
        assert contract_metadata.get("walk_forward_validation_claimed") is False
        assert contract_metadata.get("input_strategy_policy") == "reuse_input_strategy_without_parameter_search"

        walk_forward = dict(payload.get("walk_forward") or {})
        if walk_forward:
            assert walk_forward.get("analysis_mode") == "diagnostic_replay"
            serialized = str(walk_forward).lower()
            for forbidden in ("validation_score", "validated_strategy", "selected_strategy", "optimized_parameters"):
                assert forbidden not in serialized, forbidden

        oos_evidence = dict(payload.get("walk_forward_oos_evidence") or {})
        if oos_evidence:
            assert oos_evidence["contract_kind"] == "backtest_walk_forward_oos_diagnostic_evidence"
            assert oos_evidence["diagnostic_only"] is True
            assert oos_evidence["decision_grade"] is False
            assert oos_evidence["authority"]["optimizer_executed"] is False
            assert oos_evidence["authority"]["provider_calls_executed"] is False
            assert oos_evidence["authority"]["engine_math_changed"] is False

        monte_carlo = dict(payload.get("monte_carlo") or {})
        assert monte_carlo["state"] == "available"
        assert monte_carlo["simulation_count"] == 2
        assert len(monte_carlo["paths"]) == monte_carlo["simulation_count"]
        assert [path["simulation_index"] for path in monte_carlo["paths"]] == [1, 2]
        assert all(path["state"] == "completed" for path in monte_carlo["paths"])
        assert all("total_return_pct" in path["metrics"] for path in monte_carlo["paths"])
        assert monte_carlo["aggregate_metrics"]["total_return_pct"]["count"] == 2
        assert monte_carlo["diagnostics"] == []

        stress_tests = dict(payload.get("stress_tests") or {})
        assert stress_tests["state"] == "available"
        assert stress_tests["scenario_count"] == 2
        assert [scenario["scenario_key"] for scenario in stress_tests["scenarios"]] == [
            "single_day_shock_down_15",
            "volatility_whipsaw",
        ]
        assert stress_tests["worst_scenario"]["scenario_key"] == "single_day_shock_down_15"
        assert stress_tests["diagnostics"] == []

        serialized = str(BacktestApiContractTestCase._payload_without_allowed_oos_authority_flags(payload)).lower()
        for needle in FORBIDDEN_ROBUSTNESS_OPTIMIZER_TERMS:
            assert needle not in serialized, needle

    @staticmethod
    def _professional_readiness_payload(*, local_data_coverage_state: str = "not_applicable_single_symbol") -> dict:
        return {
            "overall_state": "research_prototype",
            "professional_quant_ready": False,
            "adjusted_data_state": "unknown_or_mixed",
            "adjusted_ohlc_available": False,
            "adjusted_close_only": "unknown",
            "return_basis": "unknown",
            "corporate_actions_ready": False,
            "trading_calendar_ready": False,
            "calendar_state": "available_bars_only",
            "fill_model": "next_open_baseline",
            "terminal_fallback": "same_bar_close",
            "open_missing_fallback": "close_fallback_when_open_missing",
            "no_fill_supported": False,
            "partial_fill_supported": False,
            "volume_participation_limit": None,
            "commission_model": "bps_per_side",
            "tax_model": "not_modelled",
            "stamp_duty_model": "not_modelled",
            "spread_model": "not_modelled",
            "market_impact_model": "not_modelled",
            "minimum_fee_model": "not_modelled",
            "point_in_time_universe": False,
            "survivorship_bias_state": "uncontrolled",
            "dataset_version": "unknown",
            "professional_reproducibility_ready": False,
            "local_data_coverage_state": local_data_coverage_state,
            "provider_calls": False,
            "categories": {
                "adjusted_data": {"state": "unknown_or_mixed", "ready": False},
                "corporate_actions": {"state": "not_ready", "ready": False},
                "trading_calendar": {"state": "available_bars_only", "ready": False},
                "fill_model": {"state": "next_open_baseline", "ready": False},
                "cost_model": {"state": "baseline_bps_only", "ready": False},
                "anti_leakage": {"state": "basic_bar_close_to_next_open", "ready": False},
                "reproducibility": {"state": "partial_without_dataset_lineage", "ready": False},
                "universe_bias": {"state": "uncontrolled", "ready": False},
                "local_data_coverage": {"state": local_data_coverage_state, "ready": False},
            },
        }

    def test_performance_routes_are_bound_to_canonical_contract_handlers(self) -> None:
        route_handlers = {
            (next(iter(route.methods)), route.path): route.endpoint
            for route in backtest_router.routes
            if isinstance(route, APIRoute)
            and route.methods == {"GET"}
            and route.path in {"/performance", "/performance/{code}"}
        }

        self.assertIs(route_handlers[("GET", "/performance")], get_backtest_performance)
        self.assertIs(route_handlers[("GET", "/performance/{code}")], get_backtest_stock_performance)

    @staticmethod
    def _performance_payload(*, scope: str = "overall", code: str | None = None) -> dict:
        return {
            "scope": scope,
            "code": code,
            "eval_window_days": 10,
            "evaluation_window_trading_bars": 10,
            "engine_version": "v1",
            "computed_at": "2026-04-27T09:00:00Z",
            "total_evaluations": 12,
            "completed_count": 10,
            "insufficient_count": 2,
            "long_count": 7,
            "cash_count": 3,
            "win_count": 6,
            "loss_count": 2,
            "neutral_count": 2,
            "direction_accuracy_pct": 70.0,
            "win_rate_pct": 75.0,
            "neutral_rate_pct": 20.0,
            "avg_stock_return_pct": 4.5,
            "avg_simulated_return_pct": 5.1,
            "stop_loss_trigger_rate": 10.0,
            "take_profit_trigger_rate": 30.0,
            "ambiguous_rate": 5.0,
            "avg_days_to_first_hit": 4.0,
            "advice_breakdown": {"buy": 8, "hold": 2},
            "diagnostics": {"source": "summary_table"},
            "evaluation_mode": "standard",
            "requested_mode": "local_first" if code else "auto",
            "resolved_source": "LocalParquet" if code else "DatabaseCache",
            "fallback_used": False,
            "execution_assumptions": {"entry_timing": "next_bar_open"},
        }

    @staticmethod
    def _rule_run_payload(*, run_id: int = 123, status: str = "queued") -> dict:
        artifact_availability = {
            "version": "v1",
            "source": "summary.artifact_availability",
            "completeness": "complete",
            "has_summary": True,
            "has_parsed_strategy": True,
            "has_metrics": True,
            "has_execution_model": True,
            "has_comparison": status == "completed",
            "has_trade_rows": status == "completed",
            "has_equity_curve": status == "completed",
            "has_execution_trace": status == "completed",
            "has_run_diagnostics": True,
            "has_run_timing": True,
        }
        readback_integrity = {
            "version": "v1",
            "source": "derived_from_result_authority",
            "completeness": "complete",
            "used_legacy_fallback": False,
            "used_live_storage_repair": False,
            "has_summary_storage_drift": False,
            "drift_domains": [],
            "missing_summary_fields": [],
            "integrity_level": "stored_complete",
        }
        return {
            "id": run_id,
            "code": "600519",
            "strategy_text": "Buy when Close > MA3. Sell when Close < MA3.",
            "parsed_strategy": {},
            "strategy_hash": "abc123",
            "timeframe": "daily",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "lookback_bars": 20,
            "initial_capital": 100000.0,
            "fee_bps": 0.0,
            "slippage_bps": 0.0,
            "status": status,
            "run_at": "2024-01-01T00:00:00",
            "completed_at": "2024-01-01T00:05:00" if status == "completed" else None,
            "status_history": [{"status": status, "at": "2024-01-01T00:00:00"}],
            "run_timing": {
                "created_at": "2024-01-01T00:00:00",
                "started_at": None,
                "finished_at": "2024-01-01T00:05:00" if status == "completed" else None,
                "failed_at": None,
                "cancelled_at": None,
                "last_updated_at": "2024-01-01T00:05:00" if status == "completed" else "2024-01-01T00:00:00",
                "queue_duration_seconds": None,
                "run_duration_seconds": None,
            },
            "run_diagnostics": {},
            "run_diagnostics": {
                "current_status": status,
                "terminal_status": status if status in {"completed", "failed", "cancelled"} else None,
                "reason_code": None,
                "message": None,
                "last_transition_at": "2024-01-01T00:00:00",
                "last_transition_message": None,
                "last_non_terminal_status": None,
            },
            "trade_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "annualized_return_pct": 0.0,
            "sharpe_ratio": None,
            "benchmark_mode": "auto",
            "benchmark_code": None,
            "benchmark_return_pct": None,
            "excess_return_vs_benchmark_pct": None,
            "buy_and_hold_return_pct": 0.0,
            "excess_return_vs_buy_and_hold_pct": 0.0,
            "total_return_pct": 0.0,
            "win_rate_pct": 0.0,
            "avg_trade_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "avg_holding_days": 0.0,
            "avg_holding_bars": 0.0,
            "avg_holding_calendar_days": 0.0,
            "final_equity": 100000.0,
            "summary": {
                "artifact_availability": artifact_availability,
                "readback_integrity": readback_integrity,
            },
            "artifact_availability": artifact_availability,
            "readback_integrity": readback_integrity,
            "professionalReadiness": BacktestApiContractTestCase._professional_readiness_payload(),
            "adjustedDataState": "unknown_or_mixed",
            "corporateActionState": "not_ready",
            "tradingCalendarState": "available_bars_only",
            "fillModelState": "next_open_baseline",
            "costModelState": "baseline_bps_only",
            "antiLeakageState": "basic_bar_close_to_next_open",
            "reproducibilityState": "partial_without_dataset_lineage",
            "universeBiasState": "not_applicable_single_symbol",
            "result_authority": {
                "contract_version": "v1",
                "read_mode": "stored_first",
                "summary_source": "row.summary_json",
                "summary_completeness": "complete",
                "summary_missing_fields": [],
                "parsed_strategy_source": "row.parsed_strategy_json",
                "parsed_strategy_completeness": "complete",
                "parsed_strategy_missing_fields": [],
                "comparison_source": "summary.visualization.comparison",
                "comparison_completeness": "complete",
                "comparison_missing_sections": [],
                "metrics_source": "summary.metrics",
                "metrics_completeness": "complete",
                "metrics_missing_fields": [],
                "execution_model_source": "summary.execution_model",
                "execution_model_completeness": "complete",
                "execution_model_missing_fields": [],
                "execution_assumptions_source": "summary.execution_assumptions_snapshot",
                "trade_rows_source": "stored_rule_backtest_trades",
                "trade_rows_completeness": "complete",
                "trade_rows_missing_fields": [],
                "execution_trace_source": "summary.execution_trace",
                "execution_trace_completeness": "complete",
                "execution_trace_missing_fields": [],
                "domains": {
                    "summary": {
                        "source": "row.summary_json",
                        "completeness": "complete",
                        "state": "available",
                        "missing": [],
                        "missing_kind": "fields",
                    },
                    "metrics": {
                        "source": "summary.metrics",
                        "completeness": "complete",
                        "state": "available",
                        "missing": [],
                        "missing_kind": "fields",
                    },
                    "execution_model": {
                        "source": "summary.execution_model",
                        "completeness": "complete",
                        "state": "available",
                        "missing": [],
                        "missing_kind": "fields",
                    },
                    "execution_assumptions_snapshot": {
                        "source": "summary.execution_assumptions_snapshot",
                        "completeness": "complete",
                        "state": "available",
                        "missing": [],
                        "missing_kind": "keys",
                    },
                    "comparison": {
                        "source": "summary.visualization.comparison",
                        "completeness": "complete",
                        "state": "available",
                        "missing": [],
                        "missing_kind": "sections",
                    },
                    "replay_payload": {
                        "source": "summary.visualization.audit_rows",
                        "completeness": "complete",
                        "state": "available",
                        "missing": [],
                        "missing_kind": "sections",
                    },
                    "trade_rows": {
                        "source": "stored_rule_backtest_trades",
                        "completeness": "complete",
                        "state": "available",
                        "missing": [],
                        "missing_kind": "fields",
                    },
                    "execution_trace": {
                        "source": "summary.execution_trace",
                        "completeness": "complete",
                        "state": "available",
                        "missing": [],
                        "missing_kind": "fields",
                    },
                },
            },
            "execution_trace": {
                "version": "v1",
                "source": "summary.execution_trace",
                "completeness": "complete",
                "missing_fields": [],
                "rows": [],
                "assumptions_defaults": {"items": [], "summary_text": "默认/推断：无额外默认值"},
                "execution_model": {},
                "execution_assumptions": {},
                "fallback": {
                    "run_fallback": False,
                    "trace_rebuilt": False,
                    "note": "标准执行路径",
                },
            },
            "execution_assumptions_snapshot": {
                "version": "v1",
                "source": "summary.execution_assumptions_snapshot",
                "completeness": "complete",
                "missing_keys": [],
                "payload": {
                    "timeframe": "daily",
                    "indicator_price_basis": "close",
                },
            },
            "execution_model": {
                "version": "v1",
                "timeframe": "daily",
                "signal_evaluation_timing": "bar_close",
                "entry_timing": "next_bar_open",
                "exit_timing": "next_bar_open",
                "entry_fill_price_basis": "open",
                "exit_fill_price_basis": "open",
                "position_sizing": "single_position_full_notional",
                "fee_model": "bps_per_side",
                "fee_bps_per_side": 0.0,
                "slippage_model": "bps_per_side",
                "slippage_bps_per_side": 0.0,
                "market_rules": {
                    "trading_day_execution": "available_bars_only",
                    "terminal_bar_fill_fallback": "same_bar_close",
                    "window_end_position_handling": "force_flatten",
                },
            },
            "execution_assumptions": {},
            "benchmark_curve": [],
            "benchmark_summary": {"method": "same_symbol_buy_and_hold", "resolved_mode": "same_symbol_buy_and_hold"},
            "buy_and_hold_curve": [],
            "buy_and_hold_summary": {"method": "same_symbol_buy_and_hold", "resolved_mode": "same_symbol_buy_and_hold"},
            "audit_rows": [],
            "daily_return_series": [],
            "exposure_curve": [],
            "equity_curve": [],
            "trades": [],
        }

    @classmethod
    def _support_bundle_manifest_payload(cls, *, status: str = "completed") -> dict:
        run_payload = cls._rule_run_payload(status=status)
        return {
            "manifest_version": "v1",
            "manifest_kind": "rule_backtest_support_bundle",
            "run": {
                "id": run_payload["id"],
                "code": run_payload["code"],
                "status": run_payload["status"],
                "status_message": run_payload.get("status_message"),
                "run_at": run_payload["run_at"],
                "completed_at": run_payload["completed_at"],
                "strategy_hash": run_payload["strategy_hash"],
                "timeframe": run_payload["timeframe"],
                "lookback_bars": run_payload["lookback_bars"],
                "period_start": run_payload["period_start"],
                "period_end": run_payload["period_end"],
                "benchmark_mode": run_payload["benchmark_mode"],
                "benchmark_code": run_payload["benchmark_code"],
                "trade_count": run_payload["trade_count"],
                "total_return_pct": run_payload["total_return_pct"],
                "max_drawdown_pct": run_payload["max_drawdown_pct"],
                "final_equity": run_payload["final_equity"],
                "no_result_reason": run_payload.get("no_result_reason"),
                "no_result_message": run_payload.get("no_result_message"),
            },
            "run_timing": run_payload["run_timing"],
            "run_diagnostics": run_payload["run_diagnostics"],
            "artifact_availability": run_payload["artifact_availability"],
            "readback_integrity": run_payload["readback_integrity"],
            "result_authority": {
                "contract_version": run_payload["result_authority"]["contract_version"],
                "read_mode": run_payload["result_authority"]["read_mode"],
                "domains": run_payload["result_authority"]["domains"],
            },
            "artifact_counts": {
                "status_history_count": len(run_payload.get("status_history") or []),
                "warning_count": len(run_payload.get("warnings") or []),
                "trade_rows_count": len(run_payload.get("trades") or []),
                "equity_curve_points": len(run_payload.get("equity_curve") or []),
                "audit_rows_count": len(run_payload.get("audit_rows") or []),
                "daily_return_series_count": len(run_payload.get("daily_return_series") or []),
                "exposure_curve_count": len(run_payload.get("exposure_curve") or []),
                "execution_trace_rows_count": len((run_payload.get("execution_trace") or {}).get("rows") or []),
            },
        }

    @classmethod
    def _support_bundle_reproducibility_manifest_payload(cls, *, status: str = "completed") -> dict:
        run_payload = cls._rule_run_payload(status=status)
        return {
            "manifest_version": "v1",
            "manifest_kind": "rule_backtest_reproducibility_manifest",
            "run": {
                "id": run_payload["id"],
                "code": run_payload["code"],
                "status": run_payload["status"],
                "run_at": run_payload["run_at"],
                "completed_at": run_payload["completed_at"],
                "strategy_hash": run_payload["strategy_hash"],
                "timeframe": run_payload["timeframe"],
                "lookback_bars": run_payload["lookback_bars"],
                "period_start": run_payload["period_start"],
                "period_end": run_payload["period_end"],
                "benchmark_mode": run_payload["benchmark_mode"],
                "benchmark_code": run_payload["benchmark_code"],
            },
            "run_timing": run_payload["run_timing"],
            "run_diagnostics": run_payload["run_diagnostics"],
            "artifact_availability": run_payload["artifact_availability"],
            "readback_integrity": run_payload["readback_integrity"],
            "execution_assumptions_fingerprint": {
                "source": "summary.execution_assumptions_snapshot",
                "completeness": "complete",
                "summary_text": "next bar open / long only",
                "hash_sha256": "abc123",
            },
            "result_authority": {
                "contract_version": run_payload["result_authority"]["contract_version"],
                "read_mode": run_payload["result_authority"]["read_mode"],
                "domains": {
                    domain_name: {
                        "source": domain_payload["source"],
                        "completeness": domain_payload["completeness"],
                        "state": domain_payload["state"],
                    }
                    for domain_name, domain_payload in run_payload["result_authority"]["domains"].items()
                },
            },
        }

    @staticmethod
    def _robustness_evidence_payload() -> dict:
        return {
            "state": "research_prototype",
            "profile": "single_symbol_fixture",
            "source": "summary.robustness_analysis",
            "seed": 4242,
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
                    "max_windows": 3,
                },
                "monte_carlo": {
                    "simulation_count": 16,
                    "seed": 4242,
                    "noise_scale": 0.5,
                },
                "stress_tests": {
                    "scenario_keys": ["single_day_shock_down_15", "volatility_whipsaw"],
                },
            },
            "walk_forward": {
                "analysis_mode": "diagnostic_replay",
                "window_count": 2,
                "windows": [
                    {
                        "window_index": 1,
                        "state": "completed",
                        "train_start": "2024-01-01",
                        "train_end": "2024-02-05",
                        "test_start": "2024-02-06",
                        "test_end": "2024-02-23",
                        "trade_count": 3,
                        "metrics": {"total_return_pct": 3.2},
                    }
                ],
                "aggregate_metrics": {"median_total_return_pct": 3.2},
                "diagnostics": [],
            },
            "monte_carlo": {
                "state": "available",
                "simulation_count": 2,
                "paths": [
                    {
                        "simulation_index": 1,
                        "state": "completed",
                        "metrics": {"total_return_pct": 2.8, "max_drawdown_pct": 4.2},
                    },
                    {
                        "simulation_index": 2,
                        "state": "completed",
                        "metrics": {"total_return_pct": 3.5, "max_drawdown_pct": 3.8},
                    },
                ],
                "aggregate_metrics": {
                    "total_return_pct": {"count": 2, "min": 2.8, "max": 3.5, "mean": 3.15},
                    "max_drawdown_pct": {"count": 2, "min": 3.8, "max": 4.2, "mean": 4.0},
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
                        "metrics": {"total_return_pct": -1.4, "max_drawdown_pct": 6.1},
                    },
                    {
                        "scenario_key": "volatility_whipsaw",
                        "label": "Volatility whipsaw regime",
                        "state": "completed",
                        "metrics": {"total_return_pct": 1.1, "max_drawdown_pct": 5.2},
                    },
                ],
                "worst_scenario": {
                    "scenario_key": "single_day_shock_down_15",
                    "label": "Single-day shock down 15%",
                    "state": "completed",
                    "metrics": {"total_return_pct": -1.4, "max_drawdown_pct": 6.1},
                },
                "diagnostics": [],
            },
            "diagnostics": [],
            "walk_forward_oos_evidence": {
                "contract_kind": "backtest_walk_forward_oos_diagnostic_evidence",
                "contract_version": "v1",
                "state": "available",
                "source": "stored_robustness_analysis.walk_forward",
                "read_mode": "stored_first",
                "diagnostic_only": True,
                "decision_grade": False,
                "source_run_id": 123,
                "source_run_ids": [123],
                "code": "600519",
                "timeframe": "1d",
                "period_start": "2024-01-01",
                "period_end": "2024-02-23",
                "configuration": {
                    "train_window": 36,
                    "test_window": 18,
                    "step": 9,
                    "max_windows": 3,
                    "max_folds": 3,
                    "metric_keys": ["total_return_pct", "max_drawdown_pct", "win_rate_pct", "trade_count"],
                    "window_unit": "bars",
                },
                "fold_order": ["wf_oos_fold_0001_train_20240101_20240205_test_20240206_20240223"],
                "folds": [
                    {
                        "fold_id": "wf_oos_fold_0001_train_20240101_20240205_test_20240206_20240223",
                        "fold_index": 1,
                        "state": "completed",
                        "train_window": {
                            "start_date": "2024-01-01",
                            "end_date": "2024-02-05",
                            "size": 36,
                        },
                        "test_window": {
                            "start_date": "2024-02-06",
                            "end_date": "2024-02-23",
                            "size": 18,
                        },
                        "metrics": {"total_return_pct": 3.2},
                    }
                ],
                "fold_results": [
                    {
                        "fold_id": "wf_oos_fold_0001_train_20240101_20240205_test_20240206_20240223",
                        "fold_index": 1,
                        "state": "completed",
                        "train_window": {
                            "start_date": "2024-01-01",
                            "end_date": "2024-02-05",
                            "size": 36,
                        },
                        "test_window": {
                            "start_date": "2024-02-06",
                            "end_date": "2024-02-23",
                            "size": 18,
                        },
                        "metrics": {"total_return_pct": 3.2},
                    }
                ],
                "oos_result_summary": {
                    "state": "available",
                    "completed_fold_count": 1,
                    "missing_result_fold_count": 0,
                    "metric_keys": ["total_return_pct", "max_drawdown_pct", "win_rate_pct", "trade_count"],
                    "metric_aggregates": {
                        "total_return_pct": {"count": 1, "min": 3.2, "max": 3.2, "mean": 3.2},
                    },
                },
                "coverage": {
                    "available_fold_count": 1,
                    "missing_fold_count": 0,
                    "skipped_fold_count": 0,
                    "diagnostics": [],
                },
                "reproducibility": {
                    "config_hash_sha256": "fixture-hash",
                    "input_ordering": "stored_walk_forward_window_index_ascending",
                    "fold_id_policy": "stable_from_window_bounds",
                    "result_ordering": "fold_index_ascending",
                },
                "authority": {
                    "input_mode": "stored_robustness_analysis_walk_forward",
                    "adapter_execution_count": 0,
                    "new_strategy_execution_count": 0,
                    "provider_calls_executed": False,
                    "engine_math_changed": False,
                    "strategy_parameters_mutated": False,
                    "optimizer_executed": False,
                    "parameter_sweep_executed": False,
                },
            },
        }

    @staticmethod
    def _regime_attribution_readiness_payload() -> dict:
        return {
            "exportKind": "rule_backtest_regime_attribution_readiness",
            "version": "v1",
            "runId": 123,
            "code": "600519",
            "status": "completed",
            "timeframe": "daily",
            "period": {"start": "2025-01-01", "end": "2025-12-31"},
            "source": "stored_rule_backtest_readback_projection",
            "readMode": "stored_first",
            "storedFirst": True,
            "diagnosticOnly": True,
            "engineReexecuted": False,
            "mathChanged": False,
            "attributionEngineAvailable": False,
            "pnlCausalityAvailable": False,
            "runtimeEngineStatement": "not_a_runtime_attribution_engine",
            "mathSnapshot": {
                "trade_count": 0,
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "win_rate_pct": 0.0,
                "final_equity": 100000.0,
            },
            "evidenceAvailability": {
                "trades": {"available": False, "availabilityReason": "stored_trade_rows_missing"},
                "dailyAudit": {"available": False, "availabilityReason": "stored_audit_rows_missing"},
            },
            "gapReasons": [
                {
                    "code": "missing_date_level_market_regime_labels",
                    "message": "Date-level market regime labels are not stored on the run.",
                },
                {
                    "code": "missing_regime_source_version",
                    "message": "No regime source or version is stored for reproducible attribution.",
                },
                {
                    "code": "missing_trade_to_regime_join_policy",
                    "message": "No policy exists for joining trades to market regime labels.",
                },
                {
                    "code": "missing_daily_pnl_allocation_policy",
                    "message": "No policy exists for allocating daily PnL across regimes.",
                },
                {
                    "code": "missing_holding_period_allocation_rules",
                    "message": "No rules exist for assigning multi-day holding periods to regimes.",
                },
            ],
            "limitations": [
                "diagnostic_readiness_projection_only",
                "not_a_runtime_attribution_engine",
                "no_market_regime_classification",
                "no_pnl_by_regime_allocation",
            ],
        }

    @staticmethod
    def _oos_parameter_readiness_payload(
        *,
        oos_available: bool = True,
        parameter_available: bool = False,
    ) -> dict:
        return {
            "export_kind": "rule_backtest_oos_parameter_readiness",
            "version": "v1",
            "run_id": 123,
            "code": "600519",
            "status": "completed",
            "timeframe": "daily",
            "source": "stored_rule_backtest_support_projection",
            "read_mode": "stored_first",
            "stored_first": True,
            "diagnostic_only": True,
            "decision_grade": False,
            "overall_state": "available" if oos_available and parameter_available else "partial",
            "oos_readiness": {
                "state": "available" if oos_available else "unavailable",
                "source": "stored_robustness_analysis.walk_forward" if oos_available else "stored_robustness_analysis_missing",
                "read_mode": "stored_first",
                "availability_reason": (
                    "stored_walk_forward_oos_evidence_present"
                    if oos_available
                    else "stored_robustness_analysis_missing"
                ),
                "diagnostic_only": True,
                "decision_grade": False,
                "evidence": {
                    "contract_kind": "backtest_walk_forward_oos_diagnostic_evidence"
                }
                if oos_available
                else None,
            },
            "parameter_readiness": {
                "state": "available" if parameter_available else "unavailable",
                "source": "stored_compare_summary" if parameter_available else "compare_summary_unavailable",
                "read_mode": "stored_first",
                "projection_source": (
                    "caller_supplied_compare_summary"
                    if parameter_available
                    else "stored_first_no_compare_summary"
                ),
                "availability_reason": (
                    "caller_supplied_compare_summary_present"
                    if parameter_available
                    else "stored_compare_summary_missing"
                ),
                "diagnostic_only": True,
                "decision_grade": False,
                "evidence": {
                    "contract_kind": "backtest_parameter_stability_diagnostic_evidence"
                }
                if parameter_available
                else None,
            },
            "guardrails": {
                "engine_math_changed": False,
                "optimizer_executed": False,
                "parameter_sweep_executed": False,
                "provider_calls_executed": False,
                "winner_promotion": False,
            },
            "limitations": [
                "diagnostic_readiness_projection_only",
                "not_a_runtime_oos_or_parameter_stability_engine",
                "no_strategy_execution",
                "no_optimizer_execution",
                "no_parameter_sweep_execution",
                "no_winner_promotion",
                "no_provider_calls",
            ],
        }

    @classmethod
    def _support_export_index_payload(cls, *, status: str = "completed", robustness_available: bool = True) -> dict:
        run_payload = cls._rule_run_payload(status=status)
        run_id = int(run_payload["id"])
        return {
            "run_id": run_id,
            "status": run_payload["status"],
            "exports": [
                {
                    "key": "support_bundle_manifest_json",
                    "available": True,
                    "availability_reason": "run_exists",
                    "format": "json",
                    "media_type": "application/json",
                    "delivery_mode": "api",
                    "endpoint_path": f"/api/v1/backtest/rule/runs/{run_id}/support-bundle-manifest",
                    "payload_class": "compact",
                },
                {
                    "key": "support_bundle_reproducibility_manifest_json",
                    "available": True,
                    "availability_reason": "run_exists",
                    "format": "json",
                    "media_type": "application/json",
                    "delivery_mode": "api",
                    "endpoint_path": f"/api/v1/backtest/rule/runs/{run_id}/support-bundle-reproducibility-manifest",
                    "payload_class": "compact",
                },
                {
                    "key": "execution_trace_json",
                    "available": True,
                    "availability_reason": "execution_trace_rows_present",
                    "format": "json",
                    "media_type": "application/json",
                    "delivery_mode": "api",
                    "endpoint_path": f"/api/v1/backtest/rule/runs/{run_id}/execution-trace.json",
                    "payload_class": "heavy",
                },
                {
                    "key": "execution_trace_csv",
                    "available": True,
                    "availability_reason": "execution_trace_rows_present",
                    "format": "csv",
                    "media_type": "text/csv",
                    "delivery_mode": "api",
                    "endpoint_path": f"/api/v1/backtest/rule/runs/{run_id}/execution-trace.csv",
                    "payload_class": "heavy",
                },
                {
                    "key": "robustness_evidence_json",
                    "available": robustness_available,
                    "availability_reason": (
                        "stored_robustness_analysis_present"
                        if robustness_available
                        else "stored_robustness_analysis_missing"
                    ),
                    "format": "json",
                    "media_type": "application/json",
                    "delivery_mode": "api",
                    "endpoint_path": f"/api/v1/backtest/rule/runs/{run_id}/robustness-evidence.json",
                    "payload_class": "heavy",
                },
                {
                    "key": "regime_attribution_readiness_json",
                    "available": True,
                    "availability_reason": "run_exists_readiness_projection_available",
                    "format": "json",
                    "media_type": "application/json",
                    "delivery_mode": "api",
                    "endpoint_path": f"/api/v1/backtest/rule/runs/{run_id}/regime-attribution-readiness.json",
                    "payload_class": "compact",
                },
                {
                    "key": "execution_model_metadata_json",
                    "available": True,
                    "availability_reason": "run_exists_execution_model_metadata_projection_available",
                    "format": "json",
                    "media_type": "application/json",
                    "delivery_mode": "api",
                    "endpoint_path": f"/api/v1/backtest/rule/runs/{run_id}/execution-model-metadata.json",
                    "payload_class": "compact",
                },
                {
                    "key": "oos_parameter_readiness_json",
                    "available": True,
                    "availability_reason": "run_exists_oos_parameter_readiness_projection_available",
                    "format": "json",
                    "media_type": "application/json",
                    "delivery_mode": "api",
                    "endpoint_path": f"/api/v1/backtest/rule/runs/{run_id}/oos-parameter-readiness.json",
                    "payload_class": "compact",
                },
            ],
        }

    def _assert_support_bundle_api_surface(
        self,
        *,
        service: MagicMock,
        manifest_payload: dict,
        reproducibility_payload: dict,
        export_index_payload: dict,
        trace_json_payload: dict | None,
        trace_csv_text: str | None,
        robustness_payload: dict | None,
    ) -> None:
        service.get_support_bundle_manifest.return_value = manifest_payload
        service.get_support_bundle_reproducibility_manifest.return_value = reproducibility_payload
        service.get_support_export_index.return_value = export_index_payload
        if trace_json_payload is None:
            service.get_execution_trace_export_json.side_effect = ValueError("Run 123 has no audit rows to export.")
        else:
            service.get_execution_trace_export_json.return_value = trace_json_payload
        if trace_csv_text is None:
            service.get_execution_trace_export_csv_text.side_effect = ValueError("Run 123 has no audit rows to export.")
        else:
            service.get_execution_trace_export_csv_text.return_value = trace_csv_text
        if robustness_payload is None:
            service.get_robustness_evidence_export_json.side_effect = ValueError(
                "Run 123 has no stored robustness evidence to export."
            )
        else:
            service.get_robustness_evidence_export_json.return_value = robustness_payload
        regime_readiness_payload = self._regime_attribution_readiness_payload()
        oos_parameter_readiness_payload = self._oos_parameter_readiness_payload()
        service.get_regime_attribution_readiness_export.return_value = regime_readiness_payload
        service.get_oos_parameter_readiness_export.return_value = oos_parameter_readiness_payload

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            manifest_response = get_rule_backtest_support_bundle_manifest(123, db_manager=MagicMock())
            reproducibility_response = get_rule_backtest_support_bundle_reproducibility_manifest(
                123,
                db_manager=MagicMock(),
            )
            export_index_response = get_rule_backtest_support_export_index(123, db_manager=MagicMock())
            readiness_response = get_rule_backtest_regime_attribution_readiness_json(
                123,
                db_manager=MagicMock(),
            )
            oos_parameter_readiness_response = get_rule_backtest_oos_parameter_readiness_json(
                123,
                db_manager=MagicMock(),
            )

            self.assertEqual(manifest_response.run["id"], 123)
            self.assertEqual(reproducibility_response.run["id"], 123)
            self.assertEqual(export_index_response.run_id, 123)
            self.assertEqual(readiness_response.runId, 123)
            self.assertEqual(oos_parameter_readiness_response.run_id, 123)
            self.assertEqual(manifest_response.run["status"], export_index_response.status)
            self.assertEqual(reproducibility_response.run["status"], export_index_response.status)
            self.assertTrue(readiness_response.diagnosticOnly)
            self.assertFalse(readiness_response.engineReexecuted)
            self.assertFalse(readiness_response.mathChanged)
            self.assertTrue(oos_parameter_readiness_response.diagnostic_only)
            self.assertFalse(oos_parameter_readiness_response.decision_grade)
            self.assertEqual(oos_parameter_readiness_response.overall_state, "partial")
            self.assertEqual(
                oos_parameter_readiness_response.oos_readiness["source"],
                "stored_robustness_analysis.walk_forward",
            )
            self.assertEqual(
                oos_parameter_readiness_response.oos_readiness["evidence"]["contract_kind"],
                "backtest_walk_forward_oos_diagnostic_evidence",
            )
            self.assertEqual(
                oos_parameter_readiness_response.parameter_readiness["state"],
                "unavailable",
            )
            self.assertEqual(
                oos_parameter_readiness_response.parameter_readiness["availability_reason"],
                "stored_compare_summary_missing",
            )
            self.assertIsNone(oos_parameter_readiness_response.parameter_readiness["evidence"])
            self.assertEqual(manifest_response.run_timing, reproducibility_response.run_timing)
            self.assertEqual(manifest_response.run_diagnostics, reproducibility_response.run_diagnostics)
            self.assertEqual(manifest_response.artifact_availability, reproducibility_response.artifact_availability)
            self.assertEqual(manifest_response.readback_integrity, reproducibility_response.readback_integrity)
            self.assertEqual(
                manifest_response.result_authority["contract_version"],
                reproducibility_response.result_authority["contract_version"],
            )
            self.assertEqual(
                manifest_response.result_authority["read_mode"],
                reproducibility_response.result_authority["read_mode"],
            )
            self.assertEqual(manifest_response.result_authority["read_mode"], "stored_first")
            self.assertEqual(
                reproducibility_response.result_authority["domains"],
                {
                    domain_name: {
                        "source": domain_payload["source"],
                        "completeness": domain_payload["completeness"],
                        "state": domain_payload["state"],
                    }
                    for domain_name, domain_payload in manifest_response.result_authority["domains"].items()
                },
            )
            self.assertEqual(
                reproducibility_response.execution_assumptions_fingerprint["source"],
                reproducibility_response.result_authority["domains"]["execution_assumptions_snapshot"]["source"],
            )
            self.assertEqual(
                reproducibility_response.execution_assumptions_fingerprint["completeness"],
                reproducibility_response.result_authority["domains"]["execution_assumptions_snapshot"]["completeness"],
            )
            self.assertEqual(
                reproducibility_response.execution_assumptions_fingerprint["hash_sha256"],
                reproducibility_payload["execution_assumptions_fingerprint"]["hash_sha256"],
            )
            self.assertEqual(
                manifest_response.result_authority["domains"]["execution_trace"],
                manifest_payload["result_authority"]["domains"]["execution_trace"],
            )
            self.assertEqual(
                reproducibility_response.result_authority["domains"]["execution_trace"],
                reproducibility_payload["result_authority"]["domains"]["execution_trace"],
            )
            self.assertEqual(
                [item.key for item in export_index_response.exports],
                [
                    "support_bundle_manifest_json",
                    "support_bundle_reproducibility_manifest_json",
                    "execution_trace_json",
                    "execution_trace_csv",
                    "robustness_evidence_json",
                    "regime_attribution_readiness_json",
                    "execution_model_metadata_json",
                    "oos_parameter_readiness_json",
                ],
            )
            self.assertEqual(
                [item.endpoint_path for item in export_index_response.exports],
                [
                    "/api/v1/backtest/rule/runs/123/support-bundle-manifest",
                    "/api/v1/backtest/rule/runs/123/support-bundle-reproducibility-manifest",
                    "/api/v1/backtest/rule/runs/123/execution-trace.json",
                    "/api/v1/backtest/rule/runs/123/execution-trace.csv",
                    "/api/v1/backtest/rule/runs/123/robustness-evidence.json",
                    "/api/v1/backtest/rule/runs/123/regime-attribution-readiness.json",
                    "/api/v1/backtest/rule/runs/123/execution-model-metadata.json",
                    "/api/v1/backtest/rule/runs/123/oos-parameter-readiness.json",
                ],
            )
            self.assertEqual(
                [
                    (item.format, item.media_type, item.delivery_mode, item.payload_class)
                    for item in export_index_response.exports
                ],
                [
                    ("json", "application/json", "api", "compact"),
                    ("json", "application/json", "api", "compact"),
                    ("json", "application/json", "api", "heavy"),
                    ("csv", "text/csv", "api", "heavy"),
                    ("json", "application/json", "api", "heavy"),
                    ("json", "application/json", "api", "compact"),
                    ("json", "application/json", "api", "compact"),
                    ("json", "application/json", "api", "compact"),
                ],
            )
            self.assertEqual(manifest_response.manifest_kind, "rule_backtest_support_bundle")
            self.assertEqual(
                reproducibility_response.manifest_kind,
                "rule_backtest_reproducibility_manifest",
            )

            if trace_json_payload is None:
                with self.assertRaises(HTTPException) as json_ctx:
                    get_rule_backtest_execution_trace_json(123, db_manager=MagicMock())
                with self.assertRaises(HTTPException) as csv_ctx:
                    get_rule_backtest_execution_trace_csv(123, db_manager=MagicMock())
                self.assertEqual(json_ctx.exception.status_code, 409)
                self.assertEqual(csv_ctx.exception.status_code, 409)
                self.assertFalse(export_index_response.exports[2].available)
                self.assertFalse(export_index_response.exports[3].available)
                self.assertEqual(
                    export_index_response.exports[2].availability_reason,
                    "execution_trace_rows_missing",
                )
                self.assertEqual(
                    export_index_response.exports[3].availability_reason,
                    "execution_trace_rows_missing",
                )
                self.assertEqual(
                    manifest_response.result_authority["domains"]["execution_trace"]["state"],
                    "unavailable",
                )
                self.assertEqual(
                    reproducibility_response.result_authority["domains"]["execution_trace"]["state"],
                    "unavailable",
                )
            else:
                trace_json_response = get_rule_backtest_execution_trace_json(123, db_manager=MagicMock())
                trace_csv_response = get_rule_backtest_execution_trace_csv(123, db_manager=MagicMock())
                self.assertTrue(export_index_response.exports[2].available)
                self.assertTrue(export_index_response.exports[3].available)
                self.assertEqual(
                    reproducibility_response.result_authority["domains"]["execution_trace"]["source"],
                    trace_json_response.source,
                )
                self.assertEqual(
                    reproducibility_response.result_authority["domains"]["execution_trace"]["completeness"],
                    trace_json_response.completeness,
                )
                self.assertEqual(
                    manifest_response.result_authority["domains"]["execution_trace"]["source"],
                    trace_json_response.source,
                )
                self.assertEqual(
                    manifest_response.result_authority["domains"]["execution_trace"]["completeness"],
                    trace_json_response.completeness,
                )
                self.assertEqual(
                    manifest_response.result_authority["domains"]["execution_trace"]["state"],
                    "available",
                )
                self.assertEqual(
                    reproducibility_response.result_authority["domains"]["execution_trace"]["state"],
                    "available",
                )
                self.assertEqual(
                    list(trace_json_response.model_dump().keys()),
                    EXPECTED_TRACE_EXPORT_JSON_KEYS,
                )
                self.assertEqual(
                    list(trace_json_response.trace_rows[0].keys()),
                    EXPECTED_TRACE_EXPORT_FIELD_LABELS,
                )
                self.assertEqual(
                    trace_csv_response.headers["content-type"],
                    "text/csv; charset=utf-8",
                )
                self.assertEqual(
                    trace_csv_response.body.decode("utf-8").splitlines()[0].split(","),
                    EXPECTED_TRACE_EXPORT_FIELD_LABELS,
                )
                self.assertEqual(trace_json_response.source, trace_json_payload["source"])
                self.assertEqual(
                    len(trace_json_response.trace_rows),
                    manifest_response.artifact_counts["execution_trace_rows_count"],
                )
                self.assertEqual(
                    trace_json_response.benchmark_summary["requested_mode"],
                    manifest_response.run["benchmark_mode"],
                )
                self.assertIn("rule-backtest-123-execution-trace.csv", trace_csv_response.headers["Content-Disposition"])
                self.assertEqual(
                    trace_json_response.benchmark_summary,
                    trace_json_payload["benchmark_summary"],
                )

            if robustness_payload is None:
                with self.assertRaises(HTTPException) as robustness_ctx:
                    get_rule_backtest_robustness_evidence_json(123, db_manager=MagicMock())
                self.assertEqual(robustness_ctx.exception.status_code, 409)
                self.assertFalse(export_index_response.exports[4].available)
                self.assertEqual(
                    export_index_response.exports[4].availability_reason,
                    "stored_robustness_analysis_missing",
                )
            else:
                robustness_response = get_rule_backtest_robustness_evidence_json(123, db_manager=MagicMock())
                self.assertTrue(export_index_response.exports[4].available)
                self.assertEqual(
                    export_index_response.exports[4].availability_reason,
                    "stored_robustness_analysis_present",
                )
                self.assertEqual(robustness_response.model_dump(), robustness_payload)
                self._assert_robustness_payload_stays_research_prototype(robustness_response.model_dump())
            self.assertEqual(readiness_response.model_dump(), regime_readiness_payload)
            self.assertTrue(export_index_response.exports[5].available)
            self.assertEqual(
                export_index_response.exports[5].availability_reason,
                "run_exists_readiness_projection_available",
            )

    def test_run_rule_backtest_async_path_enqueues_background_processing(self) -> None:
        request = RuleBacktestRunRequest(
            code="600519",
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            start_date="2025-01-01",
            end_date="2025-12-31",
            benchmark_mode="index_hs300",
            robustness_config={
                "walk_forward": {
                    "train_window": 48,
                    "test_window": 24,
                    "step": 12,
                    "max_windows": 5,
                },
                "monte_carlo": {"simulation_count": 16, "noise_scale": 0.5, "seed": 20260513},
            },
            wait_for_completion=False,
            confirmed=True,
        )
        background_tasks = BackgroundTasks()
        service = MagicMock()
        service.submit_backtest.return_value = self._rule_run_payload(status="queued")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = run_rule_backtest(request, background_tasks, db_manager=MagicMock())

        self.assertEqual(response.id, 123)
        service.submit_backtest.assert_called_once()
        self.assertEqual(service.submit_backtest.call_args.kwargs["start_date"], "2025-01-01")
        self.assertEqual(service.submit_backtest.call_args.kwargs["end_date"], "2025-12-31")
        self.assertEqual(service.submit_backtest.call_args.kwargs["benchmark_mode"], "index_hs300")
        self.assertEqual(
            service.submit_backtest.call_args.kwargs["robustness_config"],
            {
                "walk_forward": {
                    "train_window": 48,
                    "test_window": 24,
                    "step": 12,
                    "max_windows": 5,
                },
                "monte_carlo": {"simulation_count": 16, "noise_scale": 0.5, "seed": 20260513},
            },
        )
        service.run_backtest.assert_not_called()
        self.assertEqual(len(background_tasks.tasks), 1)
        background_task = background_tasks.tasks[0]
        self.assertEqual(background_task.args, (123,))
        self.assertEqual(background_task.kwargs, {})
        self.assertEqual(json.loads(json.dumps(list(background_task.args))), [123])

    def test_run_rule_backtest_wait_mode_executes_inline(self) -> None:
        request = RuleBacktestRunRequest(
            code="600519",
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            start_date="2025-01-01",
            end_date="2025-12-31",
            benchmark_mode="custom_code",
            benchmark_code="SPY",
            robustness_config={
                "walk_forward": {
                    "train_window": 30,
                    "test_window": 15,
                    "step": 5,
                    "max_windows": 4,
                },
                "monte_carlo": {"simulation_count": 6, "noise_scale": 0.25},
            },
            wait_for_completion=True,
            confirmed=True,
        )
        background_tasks = BackgroundTasks()
        service = MagicMock()
        service.run_backtest.return_value = self._rule_run_payload(status="completed")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = run_rule_backtest(request, background_tasks, db_manager=MagicMock())

        self.assertEqual(response.status, "completed")
        self.assertEqual(response.benchmark_summary["method"], "same_symbol_buy_and_hold")
        self.assertEqual(response.execution_model.entry_timing, "next_bar_open")
        service.run_backtest.assert_called_once()
        self.assertEqual(service.run_backtest.call_args.kwargs["start_date"], "2025-01-01")
        self.assertEqual(service.run_backtest.call_args.kwargs["end_date"], "2025-12-31")
        self.assertEqual(service.run_backtest.call_args.kwargs["benchmark_mode"], "custom_code")
        self.assertEqual(service.run_backtest.call_args.kwargs["benchmark_code"], "SPY")
        self.assertEqual(
            service.run_backtest.call_args.kwargs["robustness_config"],
            {
                "walk_forward": {
                    "train_window": 30,
                    "test_window": 15,
                    "step": 5,
                    "max_windows": 4,
                },
                "monte_carlo": {"simulation_count": 6, "noise_scale": 0.25},
            },
        )
        service.submit_backtest.assert_not_called()
        self.assertEqual(len(background_tasks.tasks), 0)

    def test_run_rule_backtest_accepts_explicit_v1_execution_model_request(self) -> None:
        request = RuleBacktestRunRequest(
            code="600519",
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            execution_model={"version": "v1"},
            wait_for_completion=False,
            confirmed=True,
        )
        background_tasks = BackgroundTasks()
        service = MagicMock()
        service.submit_backtest.return_value = self._rule_run_payload(status="queued")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = run_rule_backtest(request, background_tasks, db_manager=MagicMock())

        self.assertEqual(response.id, 123)
        service.submit_backtest.assert_called_once()
        self.assertEqual(service.submit_backtest.call_args.kwargs["execution_model"], {"version": "v1"})
        service.run_backtest.assert_not_called()
        self.assertEqual(len(background_tasks.tasks), 1)

    def test_run_rule_backtest_rejects_v2_before_service_or_background_task(self) -> None:
        request = RuleBacktestRunRequest(
            code="600519",
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            execution_model={"version": "v2"},
            wait_for_completion=False,
            confirmed=True,
        )
        background_tasks = BackgroundTasks()

        with patch("api.v1.endpoints.backtest.RuleBacktestService") as service_cls:
            with self.assertRaises(HTTPException) as ctx:
                run_rule_backtest(request, background_tasks, db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(
            ctx.exception.detail,
            {
                "error": "unsupported_execution_model",
                "message": "Unsupported rule backtest execution model. Current supported execution model is v1.",
                "requested_version": "v2",
                "supported_versions": ["v1"],
            },
        )
        service_cls.assert_not_called()
        self.assertEqual(len(background_tasks.tasks), 0)

    def test_run_rule_backtest_rejects_unknown_execution_model_with_stable_error(self) -> None:
        request = RuleBacktestRunRequest(
            code="600519",
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            execution_model={"version": "quant-v9"},
            wait_for_completion=True,
            confirmed=True,
        )

        with patch("api.v1.endpoints.backtest.RuleBacktestService") as service_cls:
            with self.assertRaises(HTTPException) as ctx:
                run_rule_backtest(request, BackgroundTasks(), db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail["error"], "unsupported_execution_model")
        self.assertEqual(ctx.exception.detail["requested_version"], "quant-v9")
        self.assertEqual(ctx.exception.detail["supported_versions"], ["v1"])
        service_cls.assert_not_called()

    def test_run_rule_backtest_rejects_string_v2_execution_model_with_stable_error(self) -> None:
        request = RuleBacktestRunRequest(
            code="600519",
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            execution_model="v2",
            wait_for_completion=False,
            confirmed=True,
        )

        with patch("api.v1.endpoints.backtest.RuleBacktestService") as service_cls:
            with self.assertRaises(HTTPException) as ctx:
                run_rule_backtest(request, BackgroundTasks(), db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail["error"], "unsupported_execution_model")
        self.assertEqual(ctx.exception.detail["requested_version"], "v2")
        service_cls.assert_not_called()

    def test_run_rule_backtest_request_keeps_legacy_setup_backed_parsed_strategy_payload(self) -> None:
        request = RuleBacktestRunRequest(
            code="AAPL",
            strategy_text="MACD金叉买入，死叉卖出",
            parsed_strategy={
                "strategy_kind": "macd_crossover",
                "setup": {
                    "symbol": "AAPL",
                    "indicator_family": "macd",
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9,
                },
                "strategy_spec": {},
            },
            start_date="2025-01-01",
            end_date="2025-12-31",
            wait_for_completion=True,
            confirmed=True,
        )
        background_tasks = BackgroundTasks()
        service = MagicMock()
        service.run_backtest.return_value = self._rule_run_payload(status="completed")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            run_rule_backtest(request, background_tasks, db_manager=MagicMock())

        self.assertEqual(service.run_backtest.call_args.kwargs["parsed_strategy"]["setup"]["indicator_family"], "macd")
        self.assertEqual(service.run_backtest.call_args.kwargs["parsed_strategy"]["strategy_spec"], {})

    def test_rule_backtest_universe_job_endpoints_are_bound_to_compact_contracts(self) -> None:
        service = MagicMock()
        service.create_universe_job.return_value = {
            "id": 42,
            "request_label": "local preflight",
            "status": "completed_with_failures",
            "strategy_hash": "abc123",
            "symbol_count": 2,
            "completed_count": 1,
            "skipped_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "running_count": 0,
            "processed_count": 2,
            "cancel_requested": False,
            "local_data_only": True,
            "execution_mode": "preflight_only",
            "professionalReadiness": self._professional_readiness_payload(local_data_coverage_state="mixed"),
            "localDataCoverageState": "mixed",
            "universeBiasState": "uncontrolled",
            "reproducibilityState": "partial_without_dataset_lineage",
            "created_at": "2026-05-09T10:00:00",
            "started_at": "2026-05-09T10:00:00",
            "completed_at": "2026-05-09T10:00:01",
        }
        service.get_universe_job_status.return_value = dict(service.create_universe_job.return_value)
        service.run_universe_job_sequential.return_value = {
            **service.create_universe_job.return_value,
            "status": "completed_with_failures",
            "execution_mode": "sequential_local",
        }
        service.list_universe_job_results.return_value = {
            "job_id": 42,
            "total": 2,
            "page": 1,
            "limit": 1,
            "items": [
                {
                    "id": 7,
                    "job_id": 42,
                    "sequence_index": 0,
                    "symbol": "AAPL",
                    "status": "ready_local_data",
                    "reason_code": None,
                    "reason_message": None,
                    "runtime_ms": 0,
                    "metrics": {},
                    "total_return_pct": 1.23,
                    "max_drawdown_pct": -0.5,
                    "win_rate_pct": 50.0,
                    "trades_count": 2,
                    "single_run_id": None,
                    "created_at": "2026-05-09T10:00:00",
                    "updated_at": "2026-05-09T10:00:00",
                }
            ],
        }
        service.get_universe_job_diagnostics.return_value = {
            "job_id": 42,
            "progress": {
                "status": "completed_with_failures",
                "total_count": 2,
                "processed_count": 2,
                "succeeded_count": 1,
                "failed_count": 0,
                "skipped_count": 1,
                "progress_pct": 100.0,
                "started_at": "2026-05-09T10:00:00",
                "completed_at": "2026-05-09T10:00:01",
            },
            "reason_summary": [
                {
                    "reason_code": "blocked_missing_local_data",
                    "count": 1,
                    "sample_symbols": ["MSFT"],
                }
            ],
            "performance_summary": {
                "top_return_symbols": [],
                "worst_return_symbols": [],
                "worst_drawdown_symbols": [],
                "best_win_rate_symbols": [],
                "average_total_return_pct": None,
                "average_max_drawdown_pct": None,
                "average_win_rate_pct": None,
            },
            "local_data_coverage": {
                "ready": 1,
                "partial": 0,
                "missing": 1,
                "insufficient_data": 0,
                "unknown": 0,
            },
            "metadata": {
                "local_only": True,
                "live_provider_calls_executed": False,
                "concurrency_enabled": False,
                "professionalReadiness": self._professional_readiness_payload(local_data_coverage_state="mixed"),
                "localDataCoverageState": "mixed",
                "pointInTimeUniverse": False,
                "survivorshipBiasState": "uncontrolled",
                "providerCalls": False,
            },
        }
        request = RuleBacktestUniverseJobCreateRequest(
            symbols=["MSFT", "AAPL"],
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            start_date="2025-01-01",
            end_date="2025-01-31",
            request_label="local preflight",
        )

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            created = create_rule_backtest_universe_job(request, db_manager=MagicMock())
            run = run_rule_backtest_universe_job(42, db_manager=MagicMock())
            status = get_rule_backtest_universe_job_status(42, db_manager=MagicMock())
            diagnostics = get_rule_backtest_universe_job_diagnostics(42, db_manager=MagicMock())
            results = list_rule_backtest_universe_job_results(
                42,
                page=1,
                limit=1,
                status="completed",
                reason_code=None,
                symbol="AA",
                sort="total_return_pct",
                order="desc",
                db_manager=MagicMock(),
            )

        self.assertIsInstance(created, RuleBacktestUniverseJobResponse)
        self.assertIsInstance(run, RuleBacktestUniverseJobResponse)
        self.assertIsInstance(status, RuleBacktestUniverseJobResponse)
        self.assertIsInstance(diagnostics, RuleBacktestUniverseJobDiagnostics)
        self.assertIsInstance(results, RuleBacktestUniverseResultsResponse)
        self.assertEqual(created.execution_mode, "preflight_only")
        self.assertEqual(run.execution_mode, "sequential_local")
        self.assertTrue(created.local_data_only)
        self.assertEqual(created.professionalReadiness["overall_state"], "research_prototype")
        self.assertFalse(created.professionalReadiness["professional_quant_ready"])
        self.assertEqual(created.localDataCoverageState, "mixed")
        self.assertEqual(diagnostics.progress.progress_pct, 100.0)
        self.assertEqual(diagnostics.reason_summary[0].reason_code, "blocked_missing_local_data")
        self.assertTrue(diagnostics.metadata.local_only)
        self.assertEqual(diagnostics.metadata.professionalReadiness["overall_state"], "research_prototype")
        self.assertFalse(diagnostics.metadata.professionalReadiness["professional_quant_ready"])
        self.assertEqual(diagnostics.metadata.localDataCoverageState, "mixed")
        self.assertFalse(diagnostics.metadata.pointInTimeUniverse)
        self.assertEqual(diagnostics.metadata.survivorshipBiasState, "uncontrolled")
        self.assertFalse(diagnostics.metadata.providerCalls)
        self.assertEqual(results.items[0].symbol, "AAPL")
        self.assertEqual(results.items[0].sequence_index, 0)
        self.assertEqual(results.items[0].total_return_pct, 1.23)
        service.create_universe_job.assert_called_once()
        service.run_universe_job_sequential.assert_called_once_with(42)
        service.get_universe_job_diagnostics.assert_called_once_with(42)
        self.assertEqual(service.create_universe_job.call_args.kwargs["symbols"], ["MSFT", "AAPL"])
        self.assertEqual(service.list_universe_job_results.call_args.kwargs["limit"], 1)
        self.assertEqual(service.list_universe_job_results.call_args.kwargs["status"], "completed")
        self.assertEqual(service.list_universe_job_results.call_args.kwargs["symbol"], "AA")
        self.assertEqual(service.list_universe_job_results.call_args.kwargs["sort"], "total_return_pct")
        self.assertEqual(service.list_universe_job_results.call_args.kwargs["order"], "desc")

    def test_get_backtest_performance_returns_global_summary_contract(self) -> None:
        service = MagicMock()
        service.get_global_summary.return_value = self._performance_payload(scope="overall")

        with patch("api.v1.endpoints.backtest.BacktestService", return_value=service):
            response = get_backtest_performance(eval_window_days=10, db_manager=MagicMock())

        self.assertEqual(response.scope, "overall")
        self.assertIsNone(response.code)
        self.assertEqual(response.requested_mode, "auto")
        self.assertEqual(response.resolved_source, "DatabaseCache")
        service.get_global_summary.assert_called_once_with(eval_window_days=10)

    def test_get_backtest_stock_performance_returns_stock_summary_contract(self) -> None:
        service = MagicMock()
        service.get_stock_summary.return_value = self._performance_payload(scope="stock", code="AAPL")

        with patch("api.v1.endpoints.backtest.BacktestService", return_value=service):
            response = get_backtest_stock_performance(code="AAPL", eval_window_days=5, db_manager=MagicMock())

        self.assertEqual(response.scope, "stock")
        self.assertEqual(response.code, "AAPL")
        self.assertEqual(response.requested_mode, "local_first")
        self.assertEqual(response.resolved_source, "LocalParquet")
        service.get_stock_summary.assert_called_once_with("AAPL", eval_window_days=5)

    def test_get_backtest_performance_falls_back_to_rule_run_aggregate_when_standard_summary_missing(self) -> None:
        service = MagicMock()
        service.get_global_summary.return_value = None
        rule_service = MagicMock()
        rule_service.list_runs.return_value = {
            "total": 2,
            "page": 1,
            "limit": 100,
            "items": [
                {
                    "id": 201,
                    "code": "AAPL",
                    "status": "completed",
                    "total_return_pct": 12.5,
                    "final_equity": 112500.0,
                    "run_at": "2026-04-27T09:00:00Z",
                    "completed_at": "2026-04-27T09:01:00Z",
                },
                {
                    "id": 202,
                    "code": "MSFT",
                    "status": "completed",
                    "total_return_pct": -3.5,
                    "final_equity": 96500.0,
                    "run_at": "2026-04-27T10:00:00Z",
                    "completed_at": "2026-04-27T10:01:00Z",
                },
            ],
        }

        with patch("api.v1.endpoints.backtest.BacktestService", return_value=service), \
             patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=rule_service):
            response = get_backtest_performance(eval_window_days=10, db_manager=MagicMock())

        self.assertEqual(response.scope, "overall")
        self.assertEqual(response.total_evaluations, 2)
        self.assertEqual(response.completed_count, 2)
        self.assertEqual(response.win_rate_pct, 50.0)
        self.assertEqual(response.avg_simulated_return_pct, 4.5)
        self.assertEqual(response.resolved_source, "stored_rule_backtest_runs")
        self.assertEqual(response.evaluation_mode, "rule_deterministic_fallback")

    def test_get_backtest_performance_returns_zero_state_payload_when_no_summary_exists(self) -> None:
        service = MagicMock()
        service.get_global_summary.return_value = None
        rule_service = MagicMock()
        rule_service.list_runs.return_value = {
            "total": 0,
            "page": 1,
            "limit": 100,
            "items": [],
        }

        with patch("api.v1.endpoints.backtest.BacktestService", return_value=service), \
             patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=rule_service):
            response = get_backtest_performance(eval_window_days=10, db_manager=MagicMock())

        self.assertEqual(response.scope, "overall")
        self.assertEqual(response.total_evaluations, 0)
        self.assertEqual(response.completed_count, 0)
        self.assertEqual(response.resolved_source, "no_backtest_data")
        self.assertEqual(response.evaluation_mode, "empty_state")

    def test_get_rule_backtest_run_serializes_canonical_audit_rows_field(self) -> None:
        service = MagicMock()
        service.get_run.return_value = self._rule_run_payload(status="completed")
        service.get_run.return_value["parsed_strategy"] = {
            "strategy_kind": "macd_crossover",
            "strategy_spec": {
                "version": "v1",
                "strategy_type": "macd_crossover",
                "strategy_family": "macd_crossover",
                "symbol": "AAPL",
                "timeframe": "daily",
                "max_lookback": 35,
                "date_range": {"start_date": "2025-01-01", "end_date": "2025-12-31"},
                "capital": {"initial_capital": 100000.0, "currency": "USD"},
                "costs": {"fee_bps": 0.0, "slippage_bps": 0.0},
                "signal": {
                    "indicator_family": "macd",
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9,
                    "entry_condition": "macd_crosses_above_signal",
                    "exit_condition": "macd_crosses_below_signal",
                },
                "execution": {
                    "frequency": "daily",
                    "signal_timing": "bar_close",
                    "fill_timing": "next_bar_open",
                },
                "position_behavior": {
                    "direction": "long_only",
                    "entry_sizing": "all_in",
                    "max_positions": 1,
                    "pyramiding": False,
                },
                "end_behavior": {"policy": "liquidate_at_end", "price_basis": "close"},
                "support": {
                    "executable": True,
                    "normalization_state": "assumed",
                    "requires_confirmation": False,
                    "unsupported_reason": None,
                    "detected_strategy_family": "macd_crossover",
                },
            },
        }
        service.get_run.return_value["audit_rows"] = [
            {
                "date": "2025-01-02",
                "symbol_close": 101.0,
                "benchmark_close": 202.0,
                "position": 1.0,
                "shares": 100.0,
                "cash": 0.0,
                "holdings_value": 10100.0,
                "total_portfolio_value": 10100.0,
                "daily_pnl": 100.0,
                "daily_return": 1.0,
                "cumulative_return": 1.0,
                "benchmark_cumulative_return": 0.5,
                "buy_hold_cumulative_return": 0.75,
                "action": "hold",
                "fill_price": None,
            }
        ]
        service.get_run.return_value["result_authority"].update(
            {
                "replay_payload_source": "summary.visualization.audit_rows",
                "replay_payload_completeness": "complete",
                "replay_payload_missing_sections": [],
            }
        )

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = get_rule_backtest_run(123, db_manager=MagicMock())

        payload = response.model_dump(by_alias=True)
        self.assertIn("auditRows", payload)
        self.assertNotIn("audit_rows", payload)
        self.assertEqual(len(payload["auditRows"]), 1)
        self.assertEqual(payload["auditRows"][0]["symbol_close"], 101.0)
        self.assertEqual(payload["result_authority"]["contract_version"], "v1")
        self.assertEqual(payload["result_authority"]["read_mode"], "stored_first")
        self.assertEqual(payload["result_authority"]["summary_source"], "row.summary_json")
        self.assertEqual(payload["result_authority"]["summary_completeness"], "complete")
        self.assertEqual(payload["result_authority"]["summary_missing_fields"], [])
        self.assertEqual(payload["result_authority"]["parsed_strategy_source"], "row.parsed_strategy_json")
        self.assertEqual(payload["result_authority"]["parsed_strategy_completeness"], "complete")
        self.assertEqual(payload["result_authority"]["parsed_strategy_missing_fields"], [])
        self.assertEqual(payload["result_authority"]["comparison_source"], "summary.visualization.comparison")
        self.assertEqual(payload["result_authority"]["comparison_completeness"], "complete")
        self.assertEqual(payload["result_authority"]["comparison_missing_sections"], [])
        self.assertEqual(payload["result_authority"]["replay_payload_source"], "summary.visualization.audit_rows")
        self.assertEqual(payload["result_authority"]["replay_payload_completeness"], "complete")
        self.assertEqual(payload["result_authority"]["replay_payload_missing_sections"], [])
        self.assertEqual(payload["result_authority"]["metrics_source"], "summary.metrics")
        self.assertEqual(payload["result_authority"]["metrics_completeness"], "complete")
        self.assertEqual(payload["result_authority"]["metrics_missing_fields"], [])
        self.assertEqual(payload["result_authority"]["execution_model_source"], "summary.execution_model")
        self.assertEqual(payload["result_authority"]["execution_model_completeness"], "complete")
        self.assertEqual(payload["result_authority"]["execution_model_missing_fields"], [])
        self.assertEqual(payload["result_authority"]["execution_assumptions_source"], "summary.execution_assumptions_snapshot")
        self.assertEqual(payload["result_authority"]["trade_rows_source"], "stored_rule_backtest_trades")
        self.assertEqual(payload["result_authority"]["trade_rows_completeness"], "complete")
        self.assertEqual(payload["result_authority"]["trade_rows_missing_fields"], [])
        self.assertEqual(payload["result_authority"]["execution_trace_source"], "summary.execution_trace")
        self.assertEqual(payload["result_authority"]["execution_trace_completeness"], "complete")
        self.assertEqual(payload["result_authority"]["execution_trace_missing_fields"], [])
        self.assertIsNone(payload["sharpe_ratio"])
        self.assertEqual(payload["artifact_availability"]["source"], "summary.artifact_availability")
        self.assertTrue(payload["artifact_availability"]["has_trade_rows"])
        self.assertEqual(payload["summary"]["artifact_availability"], payload["artifact_availability"])
        self.assertEqual(payload["readback_integrity"]["integrity_level"], "stored_complete")
        self.assertFalse(payload["readback_integrity"]["used_legacy_fallback"])
        self.assertEqual(payload["summary"]["readback_integrity"], payload["readback_integrity"])
        self.assertEqual(
            payload["result_authority"]["domains"]["execution_model"],
            {
                "source": "summary.execution_model",
                "completeness": "complete",
                "state": "available",
                "missing": [],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(
            payload["result_authority"]["domains"]["replay_payload"],
            {
                "source": "summary.visualization.audit_rows",
                "completeness": "complete",
                "state": "available",
                "missing": [],
                "missing_kind": "sections",
            },
        )
        self.assertEqual(
            payload["result_authority"]["domains"]["trade_rows"],
            {
                "source": "stored_rule_backtest_trades",
                "completeness": "complete",
                "state": "available",
                "missing": [],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(payload["execution_assumptions_snapshot"]["version"], "v1")
        self.assertEqual(payload["execution_assumptions_snapshot"]["source"], "summary.execution_assumptions_snapshot")
        self.assertEqual(payload["execution_trace"]["version"], "v1")
        self.assertEqual(payload["execution_trace"]["completeness"], "complete")
        self.assertEqual(payload["parsed_strategy"]["strategy_spec"]["strategy_type"], "macd_crossover")
        self.assertEqual(payload["parsed_strategy"]["strategy_spec"]["signal"]["signal_period"], 9)
        self.assertNotIn("unexpected_field", payload["parsed_strategy"]["strategy_spec"])

    def test_get_rule_backtest_runs_serializes_history_authority_parity_contract(self) -> None:
        service = MagicMock()
        item = self._rule_run_payload(status="completed")
        item["parsed_strategy"] = {
            "version": "v1",
            "timeframe": "daily",
            "strategy_kind": "rule_conditions",
            "strategy_spec": {
                "version": "v1",
                "strategy_type": "rule_conditions",
                "strategy_family": "rule_conditions",
                "timeframe": "daily",
                "max_lookback": 1,
            },
        }
        item["result_authority"].update(
            {
                "replay_payload_source": "omitted_without_detail_read",
                "replay_payload_completeness": "omitted",
                "replay_payload_missing_sections": [],
                "trade_rows_source": "omitted_without_detail_read",
                "trade_rows_completeness": "omitted",
                "trade_rows_missing_fields": [],
                "equity_curve_source": "omitted_without_detail_read",
                "equity_curve_completeness": "omitted",
                "equity_curve_missing_fields": [],
                "execution_trace_source": "omitted_without_detail_read",
                "execution_trace_completeness": "omitted",
                "execution_trace_missing_fields": [],
            }
        )
        item["result_authority"]["domains"].update(
            {
                "parsed_strategy": {
                    "source": "row.parsed_strategy_json",
                    "completeness": "complete",
                    "state": "available",
                    "missing": [],
                    "missing_kind": "fields",
                },
                "equity_curve": {
                    "source": "omitted_without_detail_read",
                    "completeness": "omitted",
                    "state": "omitted",
                    "missing": [],
                    "missing_kind": "fields",
                },
            }
        )
        service.list_runs.return_value = {"total": 1, "items": [item]}

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = get_rule_backtest_runs(code="600519", page=1, limit=10, db_manager=MagicMock())

        self.assertIsInstance(response, RuleBacktestHistoryResponse)
        with warnings.catch_warnings(record=True) as captured_warnings:
            warnings.simplefilter("always")
            payload = response.model_dump(by_alias=True)
        serializer_warnings = [
            warning
            for warning in captured_warnings
            if "PydanticSerializationUnexpectedValue" in str(warning.message)
        ]
        self.assertEqual(serializer_warnings, [])
        self.assertEqual(payload["total"], 1)
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["result_authority"]["summary_source"], "row.summary_json")
        self.assertEqual(payload["items"][0]["result_authority"]["summary_completeness"], "complete")
        self.assertEqual(payload["items"][0]["result_authority"]["parsed_strategy_source"], "row.parsed_strategy_json")
        self.assertEqual(payload["items"][0]["result_authority"]["parsed_strategy_completeness"], "complete")
        self.assertEqual(
            payload["items"][0]["result_authority"]["replay_payload_source"],
            "omitted_without_detail_read",
        )
        self.assertEqual(payload["items"][0]["result_authority"]["replay_payload_completeness"], "omitted")
        self.assertEqual(payload["items"][0]["result_authority"]["trade_rows_source"], "omitted_without_detail_read")
        self.assertEqual(payload["items"][0]["result_authority"]["trade_rows_completeness"], "omitted")
        self.assertEqual(payload["items"][0]["result_authority"]["equity_curve_source"], "omitted_without_detail_read")
        self.assertEqual(payload["items"][0]["result_authority"]["equity_curve_completeness"], "omitted")
        self.assertEqual(
            payload["items"][0]["result_authority"]["execution_trace_source"],
            "omitted_without_detail_read",
        )
        self.assertEqual(payload["items"][0]["result_authority"]["execution_trace_completeness"], "omitted")
        self.assertIsNone(payload["items"][0]["sharpe_ratio"])
        self.assertEqual(payload["items"][0]["artifact_availability"]["source"], "summary.artifact_availability")
        self.assertTrue(payload["items"][0]["artifact_availability"]["has_trade_rows"])
        self.assertEqual(payload["items"][0]["readback_integrity"]["integrity_level"], "stored_complete")

    def test_compare_rule_backtest_runs_serializes_stored_first_compare_contract(self) -> None:
        service = MagicMock()
        base_item = self._rule_run_payload(status="completed")
        base_item["parsed_strategy"] = {
            "strategy_kind": "moving_average_crossover",
            "strategy_spec": {
                "version": "v1",
                "strategy_type": "moving_average_crossover",
                "strategy_family": "moving_average_crossover",
                "symbol": "600519",
                "timeframe": "daily",
                "max_lookback": 20,
                "date_range": {"start_date": "2025-01-01", "end_date": "2025-12-31"},
                "capital": {"initial_capital": 100000.0, "currency": "CNY"},
                "costs": {"fee_bps": 0.0, "slippage_bps": 0.0},
                "signal": {
                    "indicator_family": "moving_average",
                    "fast_period": 3,
                    "slow_period": 5,
                    "fast_type": "simple",
                    "slow_type": "simple",
                    "entry_condition": "fast_crosses_above_slow",
                    "exit_condition": "fast_crosses_below_slow",
                },
                "execution": {
                    "frequency": "daily",
                    "signal_timing": "bar_close",
                    "fill_timing": "next_bar_open",
                },
                "position_behavior": {
                    "direction": "long_only",
                    "entry_sizing": "all_in",
                    "max_positions": 1,
                    "pyramiding": False,
                },
                "end_behavior": {"policy": "liquidate_at_end", "price_basis": "close"},
                "support": {
                    "executable": True,
                    "normalization_state": "assumed",
                    "requires_confirmation": False,
                    "unsupported_reason": None,
                    "detected_strategy_family": "moving_average_crossover",
                },
            },
        }
        service.compare_runs.return_value = {
            "comparison_source": "stored_rule_backtest_runs",
            "read_mode": "stored_first",
            "requested_run_ids": [101, 202, 999],
            "resolved_run_ids": [101, 202],
            "comparable_run_ids": [101, 202],
            "missing_run_ids": [999],
            "unavailable_runs": [],
            "field_groups": ["metadata", "parsed_strategy", "metrics", "benchmark", "execution_model"],
            "market_code_comparison": {
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "same_code",
                "state": "direct",
                "directly_comparable": True,
                "runs": [
                    {
                        "run_id": 101,
                        "code": base_item["code"],
                        "normalized_code": base_item["code"],
                        "market": "cn",
                        "availability": "complete",
                        "diagnostics": [],
                    },
                    {
                        "run_id": 202,
                        "code": f"SH{base_item['code']}",
                        "normalized_code": base_item["code"],
                        "market": "cn",
                        "availability": "complete",
                        "diagnostics": [],
                    },
                ],
                "pairs": [
                    {
                        "run_id": 202,
                        "relationship": "same_code",
                        "state": "direct",
                        "directly_comparable": True,
                        "baseline_code": base_item["code"],
                        "candidate_code": base_item["code"],
                        "baseline_market": "cn",
                        "candidate_market": "cn",
                        "diagnostics": ["same_normalized_code"],
                    }
                ],
                "diagnostics": ["same_normalized_code"],
            },
            "period_comparison": {
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "overlapping",
                "state": "comparable",
                "meaningfully_comparable": True,
                "period_bounds": [
                    {
                        "run_id": 101,
                        "period_start": base_item["period_start"],
                        "period_end": base_item["period_end"],
                        "availability": "complete",
                    },
                    {
                        "run_id": 202,
                        "period_start": "2025-03-01",
                        "period_end": "2025-12-31",
                        "availability": "complete",
                    },
                ],
                "pairs": [
                    {
                        "run_id": 202,
                        "relationship": "overlapping",
                        "state": "comparable",
                        "meaningfully_comparable": True,
                        "overlap_start": "2025-03-01",
                        "overlap_end": "2025-12-31",
                        "overlap_days": 306,
                        "gap_days": None,
                        "diagnostics": ["overlapping_periods"],
                    }
                ],
            },
            "comparison_summary": {
                "baseline": {
                    "run_id": 101,
                    "selection_rule": "first_comparable_run_by_request_order",
                    "code": base_item["code"],
                    "timeframe": base_item["timeframe"],
                    "start_date": base_item["start_date"],
                    "end_date": base_item["end_date"],
                    "strategy_family": "moving_average_crossover",
                    "strategy_type": "moving_average_crossover",
                },
                "context": {
                    "code_values": [base_item["code"]],
                    "timeframe_values": [base_item["timeframe"]],
                    "strategy_family_values": ["moving_average_crossover"],
                    "strategy_type_values": ["moving_average_crossover"],
                    "date_ranges": [
                        {"run_id": 101, "start_date": base_item["start_date"], "end_date": base_item["end_date"]},
                        {"run_id": 202, "start_date": base_item["start_date"], "end_date": base_item["end_date"]},
                    ],
                    "all_same_code": True,
                    "all_same_timeframe": True,
                    "all_same_date_range": True,
                },
                "metric_deltas": {
                    "total_return_pct": {
                        "label": "total_return_pct",
                        "state": "comparable",
                        "baseline_run_id": 101,
                        "baseline_value": base_item["total_return_pct"],
                        "available_run_ids": [101, 202],
                        "unavailable_run_ids": [],
                        "deltas": [
                            {"run_id": 101, "value": base_item["total_return_pct"], "delta_vs_baseline": 0.0},
                            {"run_id": 202, "value": base_item["total_return_pct"], "delta_vs_baseline": 0.0},
                        ],
                    },
                    "annualized_return_pct": {
                        "label": "annualized_return_pct",
                        "state": "partial",
                        "baseline_run_id": 101,
                        "baseline_value": base_item["annualized_return_pct"],
                        "available_run_ids": [101],
                        "unavailable_run_ids": [202],
                        "deltas": [
                            {"run_id": 101, "value": base_item["annualized_return_pct"], "delta_vs_baseline": 0.0},
                        ],
                    },
                },
            },
            "robustness_summary": {
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "overall_state": "partially_comparable",
                "directly_comparable": False,
                "aligned_dimensions": ["market_code"],
                "partial_dimensions": ["metrics_baseline", "parameter_set", "periods"],
                "divergent_dimensions": [],
                "unavailable_dimensions": [],
                "dimensions": {
                    "market_code": {
                        "state": "aligned",
                        "source_state": "direct",
                        "relationship": "same_code",
                        "directly_comparable": True,
                        "diagnostics": ["same_normalized_code"],
                    },
                    "metrics_baseline": {
                        "state": "partial",
                        "comparable_metric_keys": ["total_return_pct"],
                        "partial_metric_keys": ["annualized_return_pct"],
                        "unavailable_metric_keys": [],
                        "diagnostics": ["partial_metric_deltas"],
                    },
                    "parameter_set": {
                        "state": "partial",
                        "source_state": "partial",
                        "shared_parameter_keys": ["strategy_spec.execution.signal_timing"],
                        "differing_parameter_keys": ["strategy_spec.signal.fast_period"],
                        "missing_parameter_keys": ["strategy_spec.signal.slow_type"],
                        "diagnostics": ["partial_parameter_context"],
                    },
                    "periods": {
                        "state": "partial",
                        "source_state": "limited",
                        "relationship": "partial",
                        "meaningfully_comparable": False,
                        "diagnostics": ["missing_period_end"],
                    },
                },
                "diagnostics": [
                    "partial_metric_deltas",
                    "partial_parameter_context",
                    "missing_period_end",
                ],
            },
            "comparison_profile": {
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "primary_profile": "same_code_different_periods",
                "aligned_dimensions": ["market_code", "metrics_baseline"],
                "driving_dimensions": ["periods"],
                "dimension_flags": {
                    "same_code": True,
                    "same_market": True,
                    "cross_market": False,
                    "same_strategy_family": True,
                    "parameter_differences_present": True,
                    "period_differences_present": True,
                },
                "diagnostics": ["overlapping_periods"],
            },
            "comparison_highlights": {
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "primary_profile": "same_code_different_periods",
                "overall_context_state": "partially_comparable",
                "highlights": {
                    "total_return_pct": {
                        "metric": "total_return_pct",
                        "preference": "higher_is_better",
                        "state": "limited_context_winner",
                        "winner_run_ids": [202],
                        "winner_value": 18.0,
                        "available_run_ids": [101, 202],
                        "candidate_count": 2,
                        "diagnostics": [
                            "partially_comparable_context",
                            "profile_same_code_different_periods",
                        ],
                    },
                    "max_drawdown_pct": {
                        "metric": "max_drawdown_pct",
                        "preference": "lower_is_better",
                        "state": "limited_context_tie",
                        "winner_run_ids": [101, 202],
                        "winner_value": 8.5,
                        "available_run_ids": [101, 202],
                        "candidate_count": 2,
                        "diagnostics": [
                            "partially_comparable_context",
                            "profile_same_code_different_periods",
                        ],
                    },
                    "annualized_return_pct": {
                        "metric": "annualized_return_pct",
                        "preference": "higher_is_better",
                        "state": "unavailable",
                        "winner_run_ids": [],
                        "winner_value": None,
                        "available_run_ids": [],
                        "candidate_count": 0,
                        "diagnostics": ["metric_unavailable"],
                    },
                },
                "diagnostics": [
                    "partially_comparable_context",
                    "profile_same_code_different_periods",
                    "metric_unavailable",
                ],
            },
            "parameter_comparison": {
                "state": "same_family_comparable",
                "strategy_family_values": ["moving_average_crossover"],
                "strategy_type_values": ["moving_average_crossover"],
                "shared_parameter_keys": [
                    "strategy_spec.execution.signal_timing",
                    "strategy_spec.execution.fill_timing",
                ],
                "differing_parameter_keys": [
                    "strategy_spec.signal.fast_period",
                    "strategy_spec.signal.slow_period",
                ],
                "missing_parameter_keys": [
                    "strategy_spec.signal.slow_type",
                ],
                "shared_parameters": {
                    "strategy_spec.execution.signal_timing": "bar_close",
                    "strategy_spec.execution.fill_timing": "next_bar_open",
                },
                "differing_parameters": {
                    "strategy_spec.signal.fast_period": {
                        "state": "different",
                        "values": [
                            {"run_id": 101, "value": 5},
                            {"run_id": 202, "value": 10},
                        ],
                    },
                },
                "missing_parameters": {
                    "strategy_spec.signal.slow_type": {
                        "state": "partial",
                        "available_run_ids": [101],
                        "unavailable_run_ids": [202],
                        "values": [
                            {"run_id": 101, "value": "simple"},
                        ],
                    },
                },
            },
            "heatmap_projection": {
                "contract_kind": "rule_backtest_compare_heatmap_projection",
                "contract_version": "v1",
                "source": "stored_compare_projection",
                "read_mode": "stored_projection_only",
                "authority": {
                    "projection_basis": "stored_compare_payloads",
                    "comparison_source": "stored_rule_backtest_runs",
                    "execution_mode": "no_reexecution",
                    "execution_count": 0,
                    "provider_calls_executed": False,
                    "compare_payload_reused": True,
                    "authority_scope": "stored_compare_derived_heatmap_only",
                },
                "requested_compare_run_ids": [101, 202, 999],
                "resolved_compare_run_ids": [101, 202],
                "source_run_ids": [101, 202],
                "missing_run_ids": [999],
                "axes": {
                    "x": {
                        "axis_key": "strategy_spec.signal.fast_period",
                        "axis_label": "fast_period",
                        "value_type": "integer",
                        "values": [5, 10],
                    },
                    "y": {
                        "axis_key": "strategy_spec.signal.slow_period",
                        "axis_label": "slow_period",
                        "value_type": "integer",
                        "values": [20, 30],
                    },
                },
                "metric_keys": ["total_return_pct", "max_drawdown_pct"],
                "cell_availability_states": ["available", "missing", "ambiguous"],
                "cells": [
                    {
                        "x_value": 5,
                        "y_value": 20,
                        "availability_state": "available",
                        "source_run_ids": [101],
                        "metrics": {
                            "total_return_pct": {"state": "available", "value": 0.0},
                            "max_drawdown_pct": {"state": "available", "value": 0.0},
                        },
                    },
                    {
                        "x_value": 10,
                        "y_value": 30,
                        "availability_state": "available",
                        "source_run_ids": [202],
                        "metrics": {
                            "total_return_pct": {"state": "available", "value": 0.0},
                            "max_drawdown_pct": {"state": "available", "value": 0.0},
                        },
                    },
                    {
                        "x_value": 5,
                        "y_value": 30,
                        "availability_state": "missing",
                        "source_run_ids": [],
                        "metrics": {
                            "total_return_pct": {"state": "missing", "value": None},
                            "max_drawdown_pct": {"state": "missing", "value": None},
                        },
                    },
                    {
                        "x_value": 10,
                        "y_value": 20,
                        "availability_state": "missing",
                        "source_run_ids": [],
                        "metrics": {
                            "total_return_pct": {"state": "missing", "value": None},
                            "max_drawdown_pct": {"state": "missing", "value": None},
                        },
                    },
                ],
            },
            "parameter_stability_evidence": {
                "contract_kind": "backtest_parameter_stability_diagnostic_evidence",
                "contract_version": "v1",
                "state": "available",
                "source": "stored_compare_summary",
                "read_mode": "stored_first",
                "diagnostic_only": True,
                "decision_grade": False,
                "parameter_keys": [
                    "strategy_spec.signal.fast_period",
                    "strategy_spec.signal.slow_period",
                ],
                "parameter_set_count": 2,
                "metric_keys": ["total_return_pct", "max_drawdown_pct"],
                "metric_dispersion": {
                    "total_return_pct": {
                        "state": "available",
                        "count": 2,
                        "min": 12.4,
                        "max": 18.0,
                        "mean": 15.2,
                        "range": 5.6,
                    }
                },
                "metric_missing_counts": {},
                "compatible_run_coverage": {
                    "requested_run_count": 3,
                    "resolved_run_count": 2,
                    "compatible_run_count": 2,
                    "missing_run_count": 1,
                    "skipped_run_count": 0,
                    "compatible_run_ids": [101, 202],
                    "missing_run_ids": [999],
                    "skipped_run_ids": [],
                },
                "skipped_run_diagnostics": [],
                "missing_run_diagnostics": [{"run_id": 999, "reason": "missing_run"}],
                "authority": {
                    "input_mode": "stored_compare_summary",
                    "execution_count": 0,
                    "strategy_execution_count": 0,
                    "provider_calls_executed": False,
                    "engine_math_changed": False,
                    "strategy_parameters_mutated": False,
                },
            },
            "items": [
                {
                    "metadata": {
                        "id": 101,
                        "code": base_item["code"],
                        "status": "completed",
                        "run_at": base_item["run_at"],
                        "completed_at": base_item["completed_at"],
                        "timeframe": base_item["timeframe"],
                        "start_date": base_item["start_date"],
                        "end_date": base_item["end_date"],
                        "period_start": base_item["period_start"],
                        "period_end": base_item["period_end"],
                        "lookback_bars": base_item["lookback_bars"],
                        "initial_capital": base_item["initial_capital"],
                        "fee_bps": base_item["fee_bps"],
                        "slippage_bps": base_item["slippage_bps"],
                    },
                    "parsed_strategy": base_item["parsed_strategy"],
                    "metrics": {
                        "trade_count": base_item["trade_count"],
                        "win_count": base_item["win_count"],
                        "loss_count": base_item["loss_count"],
                        "total_return_pct": base_item["total_return_pct"],
                        "annualized_return_pct": base_item["annualized_return_pct"],
                        "benchmark_return_pct": base_item["benchmark_return_pct"],
                        "excess_return_vs_benchmark_pct": base_item["excess_return_vs_benchmark_pct"],
                        "buy_and_hold_return_pct": base_item["buy_and_hold_return_pct"],
                        "excess_return_vs_buy_and_hold_pct": base_item["excess_return_vs_buy_and_hold_pct"],
                        "win_rate_pct": base_item["win_rate_pct"],
                        "avg_trade_return_pct": base_item["avg_trade_return_pct"],
                        "max_drawdown_pct": base_item["max_drawdown_pct"],
                        "avg_holding_days": base_item["avg_holding_days"],
                        "avg_holding_bars": base_item["avg_holding_bars"],
                        "avg_holding_calendar_days": base_item["avg_holding_calendar_days"],
                        "final_equity": base_item["final_equity"],
                    },
                    "benchmark": {
                        "benchmark_mode": base_item["benchmark_mode"],
                        "benchmark_code": base_item["benchmark_code"],
                        "benchmark_summary": base_item["benchmark_summary"],
                        "buy_and_hold_summary": base_item["buy_and_hold_summary"],
                    },
                    "execution_model": base_item["execution_model"],
                    "result_authority": base_item["result_authority"],
                },
                {
                    "metadata": {
                        "id": 202,
                        "code": base_item["code"],
                        "status": "completed",
                        "run_at": base_item["run_at"],
                        "completed_at": base_item["completed_at"],
                        "timeframe": base_item["timeframe"],
                        "start_date": base_item["start_date"],
                        "end_date": base_item["end_date"],
                        "period_start": base_item["period_start"],
                        "period_end": base_item["period_end"],
                        "lookback_bars": base_item["lookback_bars"],
                        "initial_capital": base_item["initial_capital"],
                        "fee_bps": base_item["fee_bps"],
                        "slippage_bps": base_item["slippage_bps"],
                    },
                    "parsed_strategy": base_item["parsed_strategy"],
                    "metrics": {
                        "trade_count": base_item["trade_count"],
                        "win_count": base_item["win_count"],
                        "loss_count": base_item["loss_count"],
                        "total_return_pct": base_item["total_return_pct"],
                        "annualized_return_pct": base_item["annualized_return_pct"],
                        "benchmark_return_pct": base_item["benchmark_return_pct"],
                        "excess_return_vs_benchmark_pct": base_item["excess_return_vs_benchmark_pct"],
                        "buy_and_hold_return_pct": base_item["buy_and_hold_return_pct"],
                        "excess_return_vs_buy_and_hold_pct": base_item["excess_return_vs_buy_and_hold_pct"],
                        "win_rate_pct": base_item["win_rate_pct"],
                        "avg_trade_return_pct": base_item["avg_trade_return_pct"],
                        "max_drawdown_pct": base_item["max_drawdown_pct"],
                        "avg_holding_days": base_item["avg_holding_days"],
                        "avg_holding_bars": base_item["avg_holding_bars"],
                        "avg_holding_calendar_days": base_item["avg_holding_calendar_days"],
                        "final_equity": base_item["final_equity"],
                    },
                    "benchmark": {
                        "benchmark_mode": base_item["benchmark_mode"],
                        "benchmark_code": base_item["benchmark_code"],
                        "benchmark_summary": base_item["benchmark_summary"],
                        "buy_and_hold_summary": base_item["buy_and_hold_summary"],
                    },
                    "execution_model": base_item["execution_model"],
                    "result_authority": base_item["result_authority"],
                },
            ],
        }

        request = RuleBacktestCompareRequest(run_ids=[101, 202, 999])
        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = compare_rule_backtest_runs(request, db_manager=MagicMock())

        self.assertIsInstance(response, RuleBacktestCompareResponse)
        payload = response.model_dump(by_alias=True)
        self.assertEqual(payload["comparison_source"], "stored_rule_backtest_runs")
        self.assertEqual(payload["read_mode"], "stored_first")
        self.assertEqual(payload["missing_run_ids"], [999])
        self.assertEqual(payload["field_groups"], ["metadata", "parsed_strategy", "metrics", "benchmark", "execution_model"])
        self.assertEqual(payload["market_code_comparison"]["relationship"], "same_code")
        self.assertEqual(payload["market_code_comparison"]["state"], "direct")
        self.assertTrue(payload["market_code_comparison"]["directly_comparable"])
        self.assertEqual(
            payload["market_code_comparison"]["pairs"][0]["diagnostics"],
            ["same_normalized_code"],
        )
        self.assertEqual(payload["period_comparison"]["relationship"], "overlapping")
        self.assertEqual(payload["period_comparison"]["state"], "comparable")
        self.assertTrue(payload["period_comparison"]["meaningfully_comparable"])
        self.assertEqual(
            payload["period_comparison"]["pairs"][0]["diagnostics"],
            ["overlapping_periods"],
        )
        self.assertEqual(payload["comparison_summary"]["baseline"]["run_id"], 101)
        self.assertEqual(
            payload["comparison_summary"]["baseline"]["selection_rule"],
            "first_comparable_run_by_request_order",
        )
        self.assertTrue(payload["comparison_summary"]["context"]["all_same_code"])
        self.assertEqual(
            payload["comparison_summary"]["metric_deltas"]["total_return_pct"]["state"],
            "comparable",
        )
        self.assertEqual(
            payload["comparison_summary"]["metric_deltas"]["annualized_return_pct"]["state"],
            "partial",
        )
        self.assertEqual(
            payload["comparison_summary"]["metric_deltas"]["annualized_return_pct"]["unavailable_run_ids"],
            [202],
        )
        self.assertEqual(payload["robustness_summary"]["overall_state"], "partially_comparable")
        self.assertFalse(payload["robustness_summary"]["directly_comparable"])
        self.assertEqual(
            payload["robustness_summary"]["partial_dimensions"],
            ["metrics_baseline", "parameter_set", "periods"],
        )
        self.assertEqual(
            payload["robustness_summary"]["dimensions"]["metrics_baseline"]["partial_metric_keys"],
            ["annualized_return_pct"],
        )
        self.assertEqual(payload["comparison_profile"]["primary_profile"], "same_code_different_periods")
        self.assertEqual(payload["comparison_profile"]["driving_dimensions"], ["periods"])
        self.assertTrue(payload["comparison_profile"]["dimension_flags"]["same_code"])
        self.assertTrue(payload["comparison_profile"]["dimension_flags"]["period_differences_present"])
        self.assertEqual(payload["comparison_highlights"]["primary_profile"], "same_code_different_periods")
        self.assertEqual(payload["comparison_highlights"]["overall_context_state"], "partially_comparable")
        self.assertEqual(payload["comparison_highlights"]["highlights"]["total_return_pct"]["state"], "limited_context_winner")
        self.assertEqual(payload["comparison_highlights"]["highlights"]["total_return_pct"]["winner_run_ids"], [202])
        self.assertEqual(payload["comparison_highlights"]["highlights"]["max_drawdown_pct"]["state"], "limited_context_tie")
        self.assertEqual(payload["comparison_highlights"]["highlights"]["annualized_return_pct"]["state"], "unavailable")
        self.assertEqual(payload["parameter_comparison"]["state"], "same_family_comparable")
        self.assertEqual(
            payload["parameter_comparison"]["differing_parameter_keys"],
            ["strategy_spec.signal.fast_period", "strategy_spec.signal.slow_period"],
        )
        self.assertEqual(
            payload["parameter_comparison"]["missing_parameters"]["strategy_spec.signal.slow_type"]["state"],
            "partial",
        )
        self.assertEqual(payload["heatmap_projection"]["source"], "stored_compare_projection")
        self.assertEqual(payload["heatmap_projection"]["read_mode"], "stored_projection_only")
        self.assertEqual(payload["heatmap_projection"]["authority"]["execution_count"], 0)
        self.assertFalse(payload["heatmap_projection"]["authority"]["provider_calls_executed"])
        self.assertEqual(
            payload["heatmap_projection"]["metric_keys"],
            ["total_return_pct", "max_drawdown_pct"],
        )
        self.assertEqual(
            payload["heatmap_projection"]["axes"]["x"]["axis_key"],
            "strategy_spec.signal.fast_period",
        )
        self.assertEqual(
            payload["heatmap_projection"]["cells"][0]["availability_state"],
            "available",
        )
        self.assertEqual(
            payload["parameter_stability_evidence"]["contract_kind"],
            "backtest_parameter_stability_diagnostic_evidence",
        )
        self.assertEqual(payload["parameter_stability_evidence"]["source"], "stored_compare_summary")
        self.assertTrue(payload["parameter_stability_evidence"]["diagnostic_only"])
        self.assertFalse(payload["parameter_stability_evidence"]["decision_grade"])
        self.assertFalse(payload["parameter_stability_evidence"]["authority"]["provider_calls_executed"])
        self.assertEqual(
            payload["parameter_stability_evidence"]["compatible_run_coverage"]["missing_run_ids"],
            [999],
        )
        self.assertEqual(len(payload["items"]), 2)
        self.assertEqual(payload["items"][0]["metadata"]["id"], 101)
        self.assertEqual(payload["items"][0]["parsed_strategy"]["strategy_kind"], base_item["parsed_strategy"]["strategy_kind"])
        self.assertEqual(
            payload["items"][0]["result_authority"]["domains"]["comparison"]["source"],
            "summary.visualization.comparison",
        )

    def test_compare_rule_backtest_runs_returns_validation_error_for_incomplete_compare_set(self) -> None:
        request = RuleBacktestCompareRequest(run_ids=[101, 202])
        service = MagicMock()
        service.compare_runs.side_effect = ValueError("At least two completed accessible rule backtest runs are required for comparison")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                compare_rule_backtest_runs(request, db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail["error"], "validation_error")

    def test_get_rule_backtest_run_returns_404_not_found_contract(self) -> None:
        service = MagicMock()
        service.get_run.return_value = None

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                get_rule_backtest_run(123, db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["error"], "not_found")

    def test_get_rule_backtest_run_status_returns_lightweight_contract(self) -> None:
        service = MagicMock()
        service.get_run_status.return_value = {
            "id": 123,
            "code": "600519",
            "status": "running",
            "status_message": "正在执行规则回测。",
            "status_history": [{"status": "queued", "at": "2024-01-01T00:00:00"}],
            "run_at": "2024-01-01T00:00:00",
            "completed_at": None,
            "no_result_reason": None,
            "no_result_message": None,
            "trade_count": 0,
            "parsed_confidence": 0.8,
            "needs_confirmation": False,
            "professionalReadiness": self._professional_readiness_payload(),
            "adjustedDataState": "unknown_or_mixed",
            "corporateActionState": "not_ready",
            "tradingCalendarState": "available_bars_only",
            "fillModelState": "next_open_baseline",
            "costModelState": "baseline_bps_only",
            "antiLeakageState": "basic_bar_close_to_next_open",
            "reproducibilityState": "partial_without_dataset_lineage",
            "universeBiasState": "not_applicable_single_symbol",
            "artifact_availability": {
                "version": "v1",
                "source": "summary.artifact_availability",
                "completeness": "complete",
                "has_summary": True,
                "has_parsed_strategy": False,
                "has_metrics": False,
                "has_execution_model": True,
                "has_comparison": False,
                "has_trade_rows": False,
                "has_equity_curve": False,
                "has_execution_trace": False,
                "has_run_diagnostics": True,
                "has_run_timing": True,
            },
            "readback_integrity": {
                "version": "v1",
                "source": "stored_status_summary",
                "completeness": "complete",
                "used_legacy_fallback": False,
                "used_live_storage_repair": False,
                "has_summary_storage_drift": False,
                "drift_domains": [],
                "missing_summary_fields": [],
                "integrity_level": "stored_complete",
            },
        }

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = get_rule_backtest_run_status(123, db_manager=MagicMock())

        self.assertIsInstance(response, RuleBacktestStatusResponse)
        self.assertEqual(response.status, "running")
        self.assertEqual(response.status_history[0]["status"], "queued")
        self.assertEqual(response.artifact_availability["source"], "summary.artifact_availability")
        self.assertFalse(response.artifact_availability["has_trade_rows"])
        self.assertEqual(response.professionalReadiness["overall_state"], "research_prototype")
        self.assertFalse(response.professionalReadiness["professional_quant_ready"])
        self.assertEqual(response.adjustedDataState, "unknown_or_mixed")
        self.assertEqual(response.fillModelState, "next_open_baseline")
        self.assertEqual(response.readback_integrity["source"], "stored_status_summary")
        self.assertEqual(response.readback_integrity["integrity_level"], "stored_complete")
        service.get_run_status.assert_called_once_with(123)

    def test_get_rule_backtest_support_bundle_manifest_returns_compact_contract(self) -> None:
        service = MagicMock()
        payload = self._support_bundle_manifest_payload(status="completed")
        payload["dataset_lineage"] = {
            "source": "local_us_parquet",
            "provider": "Local US Parquet",
            "authority_status": "allowed",
            "authority_source_type": "cache_snapshot",
            "authority_reason_codes": [],
            "authority_reason_families": [],
            "authority_allowed": True,
            "degraded_fill_only": False,
            "requested_range": {"start": "2024-01-01", "end": "2024-01-31"},
            "actual_range": {"start": "2024-01-02", "end": "2024-01-31"},
            "bar_count": 21,
            "dataset_version": "unknown",
        }
        service.get_support_bundle_manifest.return_value = payload

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = get_rule_backtest_support_bundle_manifest(123, db_manager=MagicMock())

        self.assertIsInstance(response, RuleBacktestSupportBundleManifestResponse)
        self.assertEqual(response.manifest_version, "v1")
        self.assertEqual(response.manifest_kind, "rule_backtest_support_bundle")
        self.assertEqual(response.run["id"], 123)
        self.assertEqual(response.run["status"], "completed")
        self.assertEqual(response.artifact_availability["source"], "summary.artifact_availability")
        self.assertEqual(response.readback_integrity["integrity_level"], "stored_complete")
        self.assertEqual(response.result_authority["contract_version"], "v1")
        self.assertEqual(response.result_authority["read_mode"], "stored_first")
        self.assertIn("trade_rows", response.result_authority["domains"])
        self.assertEqual(response.artifact_counts["trade_rows_count"], 0)
        self.assertEqual(response.dataset_lineage.model_dump(), payload["dataset_lineage"])
        self.assertEqual(response.dataset_lineage.authority_reason_codes, [])
        self.assertEqual(response.dataset_lineage.authority_reason_families, [])
        self.assertTrue(response.dataset_lineage.authority_allowed)
        self.assertFalse(response.dataset_lineage.degraded_fill_only)
        service.get_support_bundle_manifest.assert_called_once_with(123)

    def test_get_rule_backtest_support_bundle_manifest_exposes_unknown_authority_degradation(self) -> None:
        service = MagicMock()
        payload = self._support_bundle_manifest_payload(status="completed")
        payload["dataset_lineage"] = {
            "source": "Unknown",
            "provider": "Unknown",
            "authority_status": "degraded_fill_only",
            "authority_source_type": "missing",
            "authority_reason_codes": ["source_authority_unknown"],
            "authority_reason_families": [
                {
                    "raw_code": "source_authority_unknown",
                    "family": "reproducibility_degraded",
                    "scope": "backtest_authority",
                }
            ],
            "authority_allowed": False,
            "degraded_fill_only": True,
            "requested_range": {"start": "2024-01-01", "end": "2024-01-31"},
            "actual_range": {"start": "2024-01-02", "end": "2024-01-31"},
            "bar_count": 21,
            "dataset_version": "unknown",
        }
        service.get_support_bundle_manifest.return_value = payload

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = get_rule_backtest_support_bundle_manifest(123, db_manager=MagicMock())

        self.assertEqual(response.dataset_lineage.model_dump(), payload["dataset_lineage"])
        self.assertEqual(response.dataset_lineage.authority_reason_codes, ["source_authority_unknown"])
        self.assertEqual(
            [item.model_dump() for item in response.dataset_lineage.authority_reason_families],
            [
                {
                    "raw_code": "source_authority_unknown",
                    "family": "reproducibility_degraded",
                    "scope": "backtest_authority",
                }
            ],
        )
        self.assertFalse(response.dataset_lineage.authority_allowed)
        self.assertTrue(response.dataset_lineage.degraded_fill_only)
        service.get_support_bundle_manifest.assert_called_once_with(123)

    def test_get_rule_backtest_support_bundle_manifest_preserves_drift_signals(self) -> None:
        service = MagicMock()
        payload = self._support_bundle_manifest_payload(status="completed")
        payload["artifact_availability"].update(
            {
                "source": "summary.artifact_availability+live_storage_repair",
                "completeness": "stored_partial_repaired",
                "has_trade_rows": False,
            }
        )
        payload["readback_integrity"].update(
            {
                "source": "derived_from_result_authority+live_storage_repair",
                "completeness": "stored_partial_repaired",
                "used_live_storage_repair": True,
                "has_summary_storage_drift": True,
                "drift_domains": ["trade_rows"],
                "integrity_level": "drift_repaired",
            }
        )
        payload["result_authority"]["domains"]["trade_rows"] = {
            "source": "unavailable",
            "completeness": "unavailable",
            "state": "unavailable",
            "missing": ["stored_trade_rows"],
            "missing_kind": "fields",
        }
        payload["artifact_counts"]["trade_rows_count"] = 0
        service.get_support_bundle_manifest.return_value = payload

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = get_rule_backtest_support_bundle_manifest(123, db_manager=MagicMock())

        self.assertFalse(response.artifact_availability["has_trade_rows"])
        self.assertEqual(
            response.artifact_availability["source"],
            "summary.artifact_availability+live_storage_repair",
        )
        self.assertTrue(response.readback_integrity["used_live_storage_repair"])
        self.assertTrue(response.readback_integrity["has_summary_storage_drift"])
        self.assertEqual(response.readback_integrity["drift_domains"], ["trade_rows"])
        self.assertEqual(response.readback_integrity["integrity_level"], "drift_repaired")
        self.assertEqual(response.result_authority["domains"]["trade_rows"]["source"], "unavailable")

    def test_get_rule_backtest_support_bundle_manifest_returns_not_found(self) -> None:
        service = MagicMock()
        service.get_support_bundle_manifest.side_effect = ValueError("Run 123 not found.")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                get_rule_backtest_support_bundle_manifest(123, db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["error"], "not_found")
        service.get_support_bundle_manifest.assert_called_once_with(123)

    def test_get_rule_backtest_support_bundle_reproducibility_manifest_returns_compact_contract(self) -> None:
        service = MagicMock()
        payload = self._support_bundle_reproducibility_manifest_payload(status="completed")
        payload["dataset_lineage"] = {
            "source": "local_us_parquet",
            "provider": "Local US Parquet",
            "authority_status": "allowed",
            "authority_source_type": "cache_snapshot",
            "authority_reason_codes": ["proxy_source_not_reproducible"],
            "authority_reason_families": [
                {
                    "raw_code": "proxy_source_not_reproducible",
                    "family": "reproducibility_degraded",
                    "scope": "backtest_authority",
                }
            ],
            "authority_allowed": True,
            "degraded_fill_only": False,
            "requested_range": {"start": "2024-01-01", "end": "2024-01-31"},
            "actual_range": {"start": "2024-01-02", "end": "2024-01-31"},
            "bar_count": 21,
            "dataset_version": "unknown",
        }
        service.get_support_bundle_reproducibility_manifest.return_value = payload

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = get_rule_backtest_support_bundle_reproducibility_manifest(123, db_manager=MagicMock())

        self.assertIsInstance(response, RuleBacktestSupportBundleReproducibilityManifestResponse)
        self.assertEqual(response.manifest_version, "v1")
        self.assertEqual(response.manifest_kind, "rule_backtest_reproducibility_manifest")
        self.assertEqual(response.run["id"], 123)
        self.assertEqual(response.run_diagnostics["current_status"], "completed")
        self.assertEqual(response.execution_assumptions_fingerprint["source"], "summary.execution_assumptions_snapshot")
        self.assertEqual(response.result_authority["read_mode"], "stored_first")
        self.assertEqual(response.dataset_lineage.model_dump(), payload["dataset_lineage"])
        self.assertEqual(response.dataset_lineage.authority_reason_codes, ["proxy_source_not_reproducible"])
        self.assertEqual(
            [item.model_dump() for item in response.dataset_lineage.authority_reason_families],
            [
                {
                    "raw_code": "proxy_source_not_reproducible",
                    "family": "reproducibility_degraded",
                    "scope": "backtest_authority",
                }
            ],
        )
        self.assertTrue(response.dataset_lineage.authority_allowed)
        self.assertFalse(response.dataset_lineage.degraded_fill_only)
        service.get_support_bundle_reproducibility_manifest.assert_called_once_with(123)

    def test_get_rule_backtest_support_bundle_reproducibility_manifest_preserves_drift_signals(self) -> None:
        service = MagicMock()
        payload = self._support_bundle_reproducibility_manifest_payload(status="completed")
        payload["artifact_availability"].update(
            {
                "source": "summary.artifact_availability+live_storage_repair",
                "completeness": "stored_partial_repaired",
                "has_trade_rows": False,
            }
        )
        payload["readback_integrity"].update(
            {
                "source": "derived_from_result_authority+live_storage_repair",
                "completeness": "stored_partial_repaired",
                "used_live_storage_repair": True,
                "has_summary_storage_drift": True,
                "drift_domains": ["trade_rows"],
                "integrity_level": "drift_repaired",
            }
        )
        payload["result_authority"]["domains"]["trade_rows"] = {
            "source": "unavailable",
            "completeness": "unavailable",
            "state": "unavailable",
        }
        service.get_support_bundle_reproducibility_manifest.return_value = payload

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = get_rule_backtest_support_bundle_reproducibility_manifest(123, db_manager=MagicMock())

        self.assertFalse(response.artifact_availability["has_trade_rows"])
        self.assertTrue(response.readback_integrity["used_live_storage_repair"])
        self.assertEqual(response.readback_integrity["drift_domains"], ["trade_rows"])
        self.assertEqual(response.result_authority["domains"]["trade_rows"]["source"], "unavailable")

    def test_get_rule_backtest_support_bundle_reproducibility_manifest_returns_not_found(self) -> None:
        service = MagicMock()
        service.get_support_bundle_reproducibility_manifest.side_effect = ValueError("Run 123 not found.")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                get_rule_backtest_support_bundle_reproducibility_manifest(123, db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["error"], "not_found")
        service.get_support_bundle_reproducibility_manifest.assert_called_once_with(123)

    def test_get_rule_backtest_support_export_index_returns_compact_discovery_contract(self) -> None:
        service = MagicMock()
        service.get_support_export_index.return_value = self._support_export_index_payload(status="completed")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = get_rule_backtest_support_export_index(123, db_manager=MagicMock())

        self.assertIsInstance(response, RuleBacktestSupportExportIndexResponse)
        self.assertEqual(response.run_id, 123)
        self.assertEqual(response.status, "completed")
        self.assertEqual(len(response.exports), 8)
        self.assertEqual(
            [item.key for item in response.exports],
            [
                "support_bundle_manifest_json",
                "support_bundle_reproducibility_manifest_json",
                "execution_trace_json",
                "execution_trace_csv",
                "robustness_evidence_json",
                "regime_attribution_readiness_json",
                "execution_model_metadata_json",
                "oos_parameter_readiness_json",
            ],
        )
        self.assertEqual(response.exports[0].key, "support_bundle_manifest_json")
        self.assertTrue(response.exports[0].available)
        self.assertEqual(response.exports[0].delivery_mode, "api")
        self.assertEqual(
            response.exports[0].endpoint_path,
            "/api/v1/backtest/rule/runs/123/support-bundle-manifest",
        )
        self.assertEqual(response.exports[1].key, "support_bundle_reproducibility_manifest_json")
        self.assertTrue(response.exports[1].available)
        self.assertEqual(response.exports[1].payload_class, "compact")
        self.assertEqual(response.exports[1].delivery_mode, "api")
        self.assertEqual(
            response.exports[1].endpoint_path,
            "/api/v1/backtest/rule/runs/123/support-bundle-reproducibility-manifest",
        )
        self.assertEqual(response.exports[2].key, "execution_trace_json")
        self.assertTrue(response.exports[2].available)
        self.assertEqual(response.exports[2].payload_class, "heavy")
        self.assertEqual(response.exports[2].delivery_mode, "api")
        self.assertEqual(
            response.exports[2].endpoint_path,
            "/api/v1/backtest/rule/runs/123/execution-trace.json",
        )
        self.assertEqual(response.exports[3].key, "execution_trace_csv")
        self.assertEqual(response.exports[3].media_type, "text/csv")
        self.assertEqual(response.exports[3].delivery_mode, "api")
        self.assertEqual(
            response.exports[3].endpoint_path,
            "/api/v1/backtest/rule/runs/123/execution-trace.csv",
        )
        self.assertEqual(response.exports[4].key, "robustness_evidence_json")
        self.assertTrue(response.exports[4].available)
        self.assertEqual(response.exports[4].payload_class, "heavy")
        self.assertEqual(response.exports[4].delivery_mode, "api")
        self.assertEqual(
            response.exports[4].endpoint_path,
            "/api/v1/backtest/rule/runs/123/robustness-evidence.json",
        )
        self.assertEqual(response.exports[5].key, "regime_attribution_readiness_json")
        self.assertTrue(response.exports[5].available)
        self.assertEqual(response.exports[5].payload_class, "compact")
        self.assertEqual(response.exports[5].delivery_mode, "api")
        self.assertEqual(
            response.exports[5].endpoint_path,
            "/api/v1/backtest/rule/runs/123/regime-attribution-readiness.json",
        )
        self.assertEqual(response.exports[6].key, "execution_model_metadata_json")
        self.assertTrue(response.exports[6].available)
        self.assertEqual(response.exports[6].payload_class, "compact")
        self.assertEqual(response.exports[6].delivery_mode, "api")
        self.assertEqual(
            response.exports[6].endpoint_path,
            "/api/v1/backtest/rule/runs/123/execution-model-metadata.json",
        )
        self.assertEqual(response.exports[7].key, "oos_parameter_readiness_json")
        self.assertTrue(response.exports[7].available)
        self.assertEqual(response.exports[7].payload_class, "compact")
        self.assertEqual(response.exports[7].delivery_mode, "api")
        self.assertEqual(
            response.exports[7].endpoint_path,
            "/api/v1/backtest/rule/runs/123/oos-parameter-readiness.json",
        )
        service.get_support_export_index.assert_called_once_with(123)

    def test_get_rule_backtest_execution_trace_json_returns_compact_contract(self) -> None:
        service = MagicMock()
        service.get_execution_trace_export_json.return_value = {
            "version": "v1",
            "source": "stored_execution_trace",
            "completeness": "complete",
            "missing_fields": [],
            "trace_rows": [{"日期": "2024-01-02", "动作": "买"}],
            "assumptions": {"summary_text": "next bar open / long only"},
            "execution_model": {"entry_timing": "next_bar_open"},
            "execution_assumptions": {"position_sizing": "all_available_capital"},
            "fallback": {"trace_rebuilt": False},
        }

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = get_rule_backtest_execution_trace_json(123, db_manager=MagicMock())

        self.assertIsInstance(response, RuleBacktestExecutionTraceExportResponse)
        self.assertEqual(response.version, "v1")
        self.assertEqual(response.source, "stored_execution_trace")
        self.assertEqual(response.trace_rows[0]["动作"], "买")
        self.assertEqual(response.assumptions["summary_text"], "next bar open / long only")
        service.get_execution_trace_export_json.assert_called_once_with(123)

    def test_get_rule_backtest_execution_trace_json_returns_unavailable_when_trace_missing(self) -> None:
        service = MagicMock()
        service.get_execution_trace_export_json.side_effect = ValueError("Run 123 has no audit rows to export.")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                get_rule_backtest_execution_trace_json(123, db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail["error"], "export_unavailable")
        service.get_execution_trace_export_json.assert_called_once_with(123)

    def test_get_rule_backtest_robustness_evidence_json_returns_stored_payload(self) -> None:
        service = MagicMock()
        service.get_robustness_evidence_export_json.return_value = self._robustness_evidence_payload()

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = get_rule_backtest_robustness_evidence_json(123, db_manager=MagicMock())

        self.assertIsInstance(response, RuleBacktestRobustnessEvidenceExportResponse)
        self.assertEqual(response.model_dump()["state"], "research_prototype")
        self.assertEqual(response.model_dump()["source"], "summary.robustness_analysis")
        self.assertEqual(response.model_dump()["seed"], 4242)
        self._assert_robustness_payload_stays_research_prototype(response.model_dump())
        service.get_robustness_evidence_export_json.assert_called_once_with(123)

    def test_get_rule_backtest_robustness_evidence_json_returns_unavailable_when_missing(self) -> None:
        service = MagicMock()
        service.get_robustness_evidence_export_json.side_effect = ValueError(
            "Run 123 has no stored robustness evidence to export."
        )

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                get_rule_backtest_robustness_evidence_json(123, db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail["error"], "export_unavailable")
        service.get_robustness_evidence_export_json.assert_called_once_with(123)

    def test_get_rule_backtest_regime_attribution_readiness_json_returns_stored_projection(self) -> None:
        service = MagicMock()
        service.get_regime_attribution_readiness_export.return_value = (
            self._regime_attribution_readiness_payload()
        )

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = get_rule_backtest_regime_attribution_readiness_json(123, db_manager=MagicMock())

        self.assertIsInstance(response, RuleBacktestRegimeAttributionReadinessExportResponse)
        self.assertEqual(response.exportKind, "rule_backtest_regime_attribution_readiness")
        self.assertEqual(response.readMode, "stored_first")
        self.assertTrue(response.diagnosticOnly)
        self.assertFalse(response.engineReexecuted)
        self.assertFalse(response.mathChanged)
        self.assertFalse(response.attributionEngineAvailable)
        self.assertFalse(response.pnlCausalityAvailable)
        self.assertEqual(
            [item["code"] for item in response.gapReasons],
            [
                "missing_date_level_market_regime_labels",
                "missing_regime_source_version",
                "missing_trade_to_regime_join_policy",
                "missing_daily_pnl_allocation_policy",
                "missing_holding_period_allocation_rules",
            ],
        )
        service.get_regime_attribution_readiness_export.assert_called_once_with(123)

    def test_get_rule_backtest_regime_attribution_readiness_json_returns_not_found(self) -> None:
        service = MagicMock()
        service.get_regime_attribution_readiness_export.side_effect = ValueError("Run 123 not found.")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                get_rule_backtest_regime_attribution_readiness_json(123, db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["error"], "not_found")
        service.get_regime_attribution_readiness_export.assert_called_once_with(123)

    def test_get_rule_backtest_oos_parameter_readiness_json_returns_partial_projection(self) -> None:
        service = MagicMock()
        service.get_oos_parameter_readiness_export.return_value = self._oos_parameter_readiness_payload()

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = get_rule_backtest_oos_parameter_readiness_json(123, db_manager=MagicMock())

        self.assertIsInstance(response, RuleBacktestOOSParameterReadinessExportResponse)
        self.assertEqual(response.export_kind, "rule_backtest_oos_parameter_readiness")
        self.assertEqual(response.read_mode, "stored_first")
        self.assertTrue(response.stored_first)
        self.assertTrue(response.diagnostic_only)
        self.assertFalse(response.decision_grade)
        self.assertEqual(response.overall_state, "partial")
        self.assertEqual(response.oos_readiness["source"], "stored_robustness_analysis.walk_forward")
        self.assertEqual(
            response.oos_readiness["evidence"]["contract_kind"],
            "backtest_walk_forward_oos_diagnostic_evidence",
        )
        self.assertEqual(response.parameter_readiness["state"], "unavailable")
        self.assertEqual(
            response.parameter_readiness["availability_reason"],
            "stored_compare_summary_missing",
        )
        self.assertIsNone(response.parameter_readiness["evidence"])
        self.assertFalse(response.guardrails["provider_calls_executed"])
        self.assertFalse(response.guardrails["optimizer_executed"])
        self.assertFalse(response.guardrails["parameter_sweep_executed"])
        self.assertFalse(response.guardrails["winner_promotion"])
        service.get_oos_parameter_readiness_export.assert_called_once_with(123)

    def test_get_rule_backtest_oos_parameter_readiness_json_returns_not_found(self) -> None:
        service = MagicMock()
        service.get_oos_parameter_readiness_export.side_effect = ValueError("Run 123 not found.")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                get_rule_backtest_oos_parameter_readiness_json(123, db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["error"], "not_found")
        service.get_oos_parameter_readiness_export.assert_called_once_with(123)

    def test_get_rule_backtest_execution_trace_csv_returns_csv_response(self) -> None:
        service = MagicMock()
        service.get_execution_trace_export_csv_text.return_value = "日期,动作\r\n2024-01-02,买\r\n"

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = get_rule_backtest_execution_trace_csv(123, db_manager=MagicMock())

        self.assertEqual(response.media_type, "text/csv; charset=utf-8")
        self.assertIn('rule-backtest-123-execution-trace.csv', response.headers["Content-Disposition"])
        self.assertIn("日期,动作", response.body.decode("utf-8"))
        service.get_execution_trace_export_csv_text.assert_called_once_with(123)

    def test_get_rule_backtest_execution_trace_csv_returns_unavailable_when_trace_missing(self) -> None:
        service = MagicMock()
        service.get_execution_trace_export_csv_text.side_effect = ValueError("Run 123 has no audit rows to export.")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                get_rule_backtest_execution_trace_csv(123, db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail["error"], "export_unavailable")
        service.get_execution_trace_export_csv_text.assert_called_once_with(123)

    def test_get_rule_backtest_support_export_index_truthfully_marks_missing_trace_exports(self) -> None:
        service = MagicMock()
        payload = self._support_export_index_payload(status="completed")
        payload["exports"][2]["available"] = False
        payload["exports"][2]["availability_reason"] = "execution_trace_rows_missing"
        payload["exports"][3]["available"] = False
        payload["exports"][3]["availability_reason"] = "execution_trace_rows_missing"
        service.get_support_export_index.return_value = payload

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = get_rule_backtest_support_export_index(123, db_manager=MagicMock())

        self.assertTrue(response.exports[0].available)
        self.assertTrue(response.exports[1].available)
        self.assertFalse(response.exports[2].available)
        self.assertFalse(response.exports[3].available)
        self.assertTrue(response.exports[4].available)
        self.assertTrue(response.exports[5].available)
        self.assertEqual(response.exports[2].availability_reason, "execution_trace_rows_missing")
        self.assertEqual(response.exports[3].availability_reason, "execution_trace_rows_missing")

    def test_get_rule_backtest_support_export_index_returns_not_found(self) -> None:
        service = MagicMock()
        service.get_support_export_index.side_effect = ValueError("Run 123 not found.")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                get_rule_backtest_support_export_index(123, db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["error"], "not_found")

    def test_support_bundle_api_surface_forms_coherent_stored_first_contract(self) -> None:
        service = MagicMock()
        manifest_payload = self._support_bundle_manifest_payload(status="completed")
        manifest_payload["artifact_counts"]["execution_trace_rows_count"] = 1
        self._assert_support_bundle_api_surface(
            service=service,
            manifest_payload=manifest_payload,
            reproducibility_payload=self._support_bundle_reproducibility_manifest_payload(status="completed"),
            export_index_payload=self._support_export_index_payload(status="completed"),
            trace_json_payload={
                "version": "v1",
                "source": "summary.execution_trace",
                "completeness": "complete",
                "missing_fields": [],
                "trace_rows": [
                    {
                        "日期": "2024-01-02",
                        "标的收盘价": "10.2",
                        "基准收盘价": "10.1",
                        "信号摘要": "Close > MA3",
                        "动作": "买",
                        "成交价": "10.3",
                        "持股数": "100",
                        "现金": "90000",
                        "持仓市值": "1030",
                        "总资产": "91030",
                        "当日盈亏": "30",
                        "当日收益率": "0.0003",
                        "策略累计收益率": "0.0103",
                        "基准累计收益率": "0.0088",
                        "买入持有累计收益率": "0.0091",
                        "仓位": "0.0113",
                        "手续费": "1.2",
                        "滑点": "0.5",
                        "备注": "",
                        "assumptions": "next bar open / long only",
                        "fallback": "",
                    }
                ],
                "assumptions": {"summary_text": "next bar open / long only"},
                "execution_model": {"entry_timing": "next_bar_open"},
                "execution_assumptions": {"position_sizing": "all_available_capital"},
                "benchmark_summary": {
                    "method": "same_symbol_buy_and_hold",
                    "requested_mode": "auto",
                    "resolved_mode": "same_symbol_buy_and_hold",
                },
                "fallback": {"trace_rebuilt": False},
            },
            trace_csv_text=(
                "日期,标的收盘价,基准收盘价,信号摘要,动作,成交价,持股数,现金,持仓市值,总资产,当日盈亏,当日收益率,"
                "策略累计收益率,基准累计收益率,买入持有累计收益率,仓位,手续费,滑点,备注,assumptions,fallback\r\n"
                "2024-01-02,10.2,10.1,Close > MA3,买,10.3,100,90000,1030,91030,30,0.0003,0.0103,0.0088,0.0091,0.0113,1.2,0.5,,next bar open / long only,\r\n"
            ),
            robustness_payload=self._robustness_evidence_payload(),
        )

    def test_support_bundle_api_surface_preserves_live_storage_repair_signals(self) -> None:
        service = MagicMock()
        manifest_payload = self._support_bundle_manifest_payload(status="completed")
        reproducibility_payload = self._support_bundle_reproducibility_manifest_payload(status="completed")
        export_index_payload = self._support_export_index_payload(status="completed")
        manifest_payload["artifact_counts"]["execution_trace_rows_count"] = 1
        for payload in (manifest_payload, reproducibility_payload):
            payload["artifact_availability"].update(
                {
                    "source": "summary.artifact_availability+live_storage_repair",
                    "completeness": "stored_partial_repaired",
                    "has_trade_rows": False,
                }
            )
            payload["readback_integrity"].update(
                {
                    "source": "derived_from_result_authority+live_storage_repair",
                    "completeness": "stored_partial_repaired",
                    "used_live_storage_repair": True,
                    "has_summary_storage_drift": True,
                    "drift_domains": ["trade_rows"],
                    "integrity_level": "drift_repaired",
                }
            )
        manifest_payload["result_authority"]["domains"]["trade_rows"] = {
            "source": "unavailable",
            "completeness": "unavailable",
            "state": "unavailable",
            "missing": ["stored_trade_rows"],
            "missing_kind": "fields",
        }
        reproducibility_payload["result_authority"]["domains"]["trade_rows"] = {
            "source": "unavailable",
            "completeness": "unavailable",
            "state": "unavailable",
        }

        self._assert_support_bundle_api_surface(
            service=service,
            manifest_payload=manifest_payload,
            reproducibility_payload=reproducibility_payload,
            export_index_payload=export_index_payload,
            trace_json_payload={
                "version": "v1",
                "source": "summary.execution_trace",
                "completeness": "complete",
                "missing_fields": [],
                "trace_rows": [
                    {
                        "日期": "2024-01-02",
                        "标的收盘价": "10.2",
                        "基准收盘价": "10.1",
                        "信号摘要": "Close > MA3",
                        "动作": "买",
                        "成交价": "10.3",
                        "持股数": "100",
                        "现金": "90000",
                        "持仓市值": "1030",
                        "总资产": "91030",
                        "当日盈亏": "30",
                        "当日收益率": "0.0003",
                        "策略累计收益率": "0.0103",
                        "基准累计收益率": "0.0088",
                        "买入持有累计收益率": "0.0091",
                        "仓位": "0.0113",
                        "手续费": "1.2",
                        "滑点": "0.5",
                        "备注": "",
                        "assumptions": "next bar open / long only",
                        "fallback": "",
                    }
                ],
                "assumptions": {"summary_text": "next bar open / long only"},
                "execution_model": {"entry_timing": "next_bar_open"},
                "execution_assumptions": {"position_sizing": "all_available_capital"},
                "benchmark_summary": {
                    "method": "same_symbol_buy_and_hold",
                    "requested_mode": "auto",
                    "resolved_mode": "same_symbol_buy_and_hold",
                },
                "fallback": {"trace_rebuilt": False},
            },
            trace_csv_text=(
                "日期,标的收盘价,基准收盘价,信号摘要,动作,成交价,持股数,现金,持仓市值,总资产,当日盈亏,当日收益率,"
                "策略累计收益率,基准累计收益率,买入持有累计收益率,仓位,手续费,滑点,备注,assumptions,fallback\r\n"
                "2024-01-02,10.2,10.1,Close > MA3,买,10.3,100,90000,1030,91030,30,0.0003,0.0103,0.0088,0.0091,0.0113,1.2,0.5,,next bar open / long only,\r\n"
            ),
            robustness_payload=self._robustness_evidence_payload(),
        )

    def test_support_bundle_api_surface_truthfully_closes_missing_trace_contract(self) -> None:
        service = MagicMock()
        manifest_payload = self._support_bundle_manifest_payload(status="completed")
        reproducibility_payload = self._support_bundle_reproducibility_manifest_payload(status="completed")
        export_index_payload = self._support_export_index_payload(status="completed")
        manifest_payload["artifact_availability"]["has_execution_trace"] = False
        reproducibility_payload["artifact_availability"]["has_execution_trace"] = False
        manifest_payload["artifact_counts"]["execution_trace_rows_count"] = 0
        manifest_payload["result_authority"]["domains"]["execution_trace"] = {
            "source": "unavailable",
            "completeness": "unavailable",
            "state": "unavailable",
            "missing": ["stored_execution_trace"],
            "missing_kind": "fields",
        }
        reproducibility_payload["result_authority"]["domains"]["execution_trace"] = {
            "source": "unavailable",
            "completeness": "unavailable",
            "state": "unavailable",
        }
        export_index_payload["exports"][2]["available"] = False
        export_index_payload["exports"][2]["availability_reason"] = "execution_trace_rows_missing"
        export_index_payload["exports"][3]["available"] = False
        export_index_payload["exports"][3]["availability_reason"] = "execution_trace_rows_missing"

        self._assert_support_bundle_api_surface(
            service=service,
            manifest_payload=manifest_payload,
            reproducibility_payload=reproducibility_payload,
            export_index_payload=export_index_payload,
            trace_json_payload=None,
            trace_csv_text=None,
            robustness_payload=self._robustness_evidence_payload(),
        )
        service.get_support_export_index.assert_called_once_with(123)

    def test_support_bundle_api_surface_truthfully_closes_missing_robustness_contract(self) -> None:
        service = MagicMock()
        manifest_payload = self._support_bundle_manifest_payload(status="completed")
        reproducibility_payload = self._support_bundle_reproducibility_manifest_payload(status="completed")
        export_index_payload = self._support_export_index_payload(
            status="completed",
            robustness_available=False,
        )
        manifest_payload["artifact_counts"]["execution_trace_rows_count"] = 1

        self._assert_support_bundle_api_surface(
            service=service,
            manifest_payload=manifest_payload,
            reproducibility_payload=reproducibility_payload,
            export_index_payload=export_index_payload,
            trace_json_payload={
                "version": "v1",
                "source": "summary.execution_trace",
                "completeness": "complete",
                "missing_fields": [],
                "trace_rows": [
                    {
                        "日期": "2024-01-02",
                        "标的收盘价": "10.2",
                        "基准收盘价": "10.1",
                        "信号摘要": "Close > MA3",
                        "动作": "买",
                        "成交价": "10.3",
                        "持股数": "100",
                        "现金": "90000",
                        "持仓市值": "1030",
                        "总资产": "91030",
                        "当日盈亏": "30",
                        "当日收益率": "0.0003",
                        "策略累计收益率": "0.0103",
                        "基准累计收益率": "0.0088",
                        "买入持有累计收益率": "0.0091",
                        "仓位": "0.0113",
                        "手续费": "1.2",
                        "滑点": "0.5",
                        "备注": "",
                        "assumptions": "next bar open / long only",
                        "fallback": ""
                    }
                ],
                "assumptions": {"summary_text": "next bar open / long only"},
                "execution_model": {"entry_timing": "next_bar_open"},
                "execution_assumptions": {"position_sizing": "all_available_capital"},
                "benchmark_summary": {
                    "method": "same_symbol_buy_and_hold",
                    "requested_mode": "auto",
                    "resolved_mode": "same_symbol_buy_and_hold",
                },
                "fallback": {"trace_rebuilt": False},
            },
            trace_csv_text=(
                "日期,标的收盘价,基准收盘价,信号摘要,动作,成交价,持股数,现金,持仓市值,总资产,当日盈亏,当日收益率,"
                "策略累计收益率,基准累计收益率,买入持有累计收益率,仓位,手续费,滑点,备注,assumptions,fallback\r\n"
                "2024-01-02,10.2,10.1,Close > MA3,买,10.3,100,90000,1030,91030,30,0.0003,0.0103,0.0088,0.0091,0.0113,1.2,0.5,,next bar open / long only,\r\n"
            ),
            robustness_payload=None,
        )

    def test_cancel_rule_backtest_run_returns_cancel_contract(self) -> None:
        service = MagicMock()
        service.cancel_run.return_value = {
            "id": 123,
            "code": "600519",
            "status": "cancelled",
            "status_message": "规则回测已取消。",
            "status_history": [
                {"status": "queued", "at": "2024-01-01T00:00:00"},
                {"status": "cancelled", "at": "2024-01-01T00:00:01"},
            ],
            "run_timing": {
                "created_at": "2024-01-01T00:00:00",
                "started_at": None,
                "finished_at": "2024-01-01T00:00:01",
                "failed_at": None,
                "cancelled_at": "2024-01-01T00:00:01",
                "last_updated_at": "2024-01-01T00:00:01",
                "queue_duration_seconds": None,
                "run_duration_seconds": None,
            },
            "run_diagnostics": {
                "current_status": "cancelled",
                "terminal_status": "cancelled",
                "reason_code": "cancelled",
                "message": "规则回测已取消。",
                "last_transition_at": "2024-01-01T00:00:01",
                "last_transition_message": "规则回测已取消。",
                "last_non_terminal_status": "queued",
            },
            "run_at": "2024-01-01T00:00:00",
            "completed_at": "2024-01-01T00:00:01",
            "no_result_reason": "cancelled",
            "no_result_message": "规则回测已取消。",
            "trade_count": 0,
            "parsed_confidence": 0.8,
            "needs_confirmation": False,
        }

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = cancel_rule_backtest_run(123, db_manager=MagicMock())

        self.assertIsInstance(response, RuleBacktestCancelResponse)
        self.assertEqual(response.status, "cancelled")
        self.assertEqual(response.no_result_reason, "cancelled")
        self.assertEqual(response.run_timing["cancelled_at"], "2024-01-01T00:00:01")
        self.assertEqual(response.run_timing["finished_at"], "2024-01-01T00:00:01")
        self.assertEqual(response.run_diagnostics["terminal_status"], "cancelled")
        self.assertEqual(response.run_diagnostics["last_non_terminal_status"], "queued")
        service.cancel_run.assert_called_once_with(123)

    def test_rule_backtest_run_response_uses_supported_family_strategy_spec_contract(self) -> None:
        response = RuleBacktestRunResponse(
            **{
                **self._rule_run_payload(status="completed"),
                "parsed_strategy": {
                    "strategy_kind": "periodic_accumulation",
                    "strategy_spec": {
                        "version": "v1",
                        "strategy_type": "periodic_accumulation",
                        "strategy_family": "periodic_accumulation",
                        "symbol": "ORCL",
                        "timeframe": "daily",
                        "max_lookback": 1,
                        "date_range": {"start_date": "2025-01-01", "end_date": "2025-12-31"},
                        "capital": {"initial_capital": 100000.0, "currency": "USD"},
                        "costs": {"fee_bps": 0.0, "slippage_bps": 0.0},
                        "schedule": {"frequency": "daily", "timing": "session_open"},
                        "entry": {
                            "side": "buy",
                            "order": {"mode": "fixed_shares", "quantity": 100.0, "amount": None},
                            "price_basis": "open",
                        },
                        "exit": {"policy": "close_at_end", "price_basis": "close"},
                        "position_behavior": {"accumulate": True, "cash_policy": "stop_when_insufficient_cash"},
                        "support": {
                            "executable": True,
                            "normalization_state": "assumed",
                            "requires_confirmation": True,
                            "unsupported_reason": None,
                            "detected_strategy_family": "periodic_accumulation",
                        },
                        "unexpected_field": "drop_me",
                    },
                },
            }
        )

        payload = response.model_dump()
        self.assertEqual(payload["parsed_strategy"]["strategy_spec"]["strategy_type"], "periodic_accumulation")
        self.assertEqual(payload["parsed_strategy"]["strategy_spec"]["entry"]["order"]["mode"], "fixed_shares")
        self.assertNotIn("unexpected_field", payload["parsed_strategy"]["strategy_spec"])

    def test_parse_rule_strategy_returns_normalization_metadata(self) -> None:
        request = RuleBacktestParseRequest(
            code="AAPL",
            strategy_text="MACD金叉买入，死叉卖出",
            start_date="2025-01-01",
            end_date="2025-12-31",
            initial_capital=100000,
        )
        service = MagicMock()
        service.parse_strategy.return_value = {
            "strategy_kind": "macd_crossover",
            "strategy_spec": {"strategy_type": "macd_crossover", "symbol": "AAPL"},
            "confidence": 0.96,
            "needs_confirmation": True,
            "ambiguities": [],
            "summary": {"entry": "买入条件：MACD(12,26,9) 金叉", "exit": "卖出条件：MACD(12,26,9) 死叉"},
            "max_lookback": 35,
            "executable": True,
            "normalization_state": "assumed",
            "assumptions": [{"key": "macd_periods", "value": "12,26,9"}],
            "assumption_groups": [{"key": "indicator_defaults", "label": "指标默认值", "items": [{"key": "macd_periods"}]}],
            "detected_strategy_family": "macd_crossover",
            "unsupported_reason": None,
            "unsupported_details": [],
            "unsupported_extensions": [],
            "core_intent_summary": "已识别为 MACD 金叉 / 死叉主规则。",
            "interpretation_confidence": 0.96,
            "supported_portion_summary": "已识别为 MACD 金叉 / 死叉主规则。",
            "rewrite_suggestions": [],
            "parse_warnings": [],
        }

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = parse_rule_strategy(request, db_manager=MagicMock())

        self.assertEqual(response.normalized_strategy_family, "macd_crossover")
        self.assertEqual(response.detected_strategy_family, "macd_crossover")
        self.assertTrue(response.executable)
        self.assertEqual(response.normalization_state, "assumed")
        self.assertEqual(len(response.assumptions), 1)
        self.assertEqual(len(response.assumption_groups), 1)
        self.assertEqual(response.core_intent_summary, "已识别为 MACD 金叉 / 死叉主规则。")
        self.assertEqual(response.interpretation_confidence, 0.96)
        self.assertEqual(response.supported_portion_summary, "已识别为 MACD 金叉 / 死叉主规则。")
        service.parse_strategy.assert_called_once()
        self.assertEqual(service.parse_strategy.call_args.kwargs["start_date"], "2025-01-01")
        self.assertEqual(service.parse_strategy.call_args.kwargs["end_date"], "2025-12-31")

    def test_parse_response_uses_supported_family_strategy_spec_contract(self) -> None:
        response = RuleBacktestParseResponse(
            code="AAPL",
            strategy_text="RSI 小于 30 买入，大于 70 卖出",
            parsed_strategy={
                "strategy_kind": "rsi_threshold",
                "strategy_spec": {
                    "version": "v1",
                    "strategy_type": "rsi_threshold",
                    "strategy_family": "rsi_threshold",
                    "symbol": "AAPL",
                    "timeframe": "daily",
                    "max_lookback": 14,
                    "date_range": {"start_date": "2025-01-01", "end_date": "2025-12-31"},
                    "capital": {"initial_capital": 100000.0, "currency": "USD"},
                    "costs": {"fee_bps": 0.0, "slippage_bps": 0.0},
                    "signal": {
                        "indicator_family": "rsi",
                        "period": 14,
                        "lower_threshold": 30.0,
                        "upper_threshold": 70.0,
                        "entry_condition": "rsi_crosses_below_lower_threshold",
                        "exit_condition": "rsi_crosses_above_upper_threshold",
                    },
                    "execution": {
                        "frequency": "daily",
                        "signal_timing": "bar_close",
                        "fill_timing": "next_bar_open",
                    },
                    "position_behavior": {
                        "direction": "long_only",
                        "entry_sizing": "all_in",
                        "max_positions": 1,
                        "pyramiding": False,
                    },
                    "end_behavior": {"policy": "liquidate_at_end", "price_basis": "close"},
                    "support": {
                        "executable": True,
                        "normalization_state": "assumed",
                        "requires_confirmation": False,
                        "unsupported_reason": None,
                        "detected_strategy_family": "rsi_threshold",
                    },
                    "unexpected_field": "drop_me",
                },
            },
            normalized_strategy_family="rsi_threshold",
            detected_strategy_family="rsi_threshold",
            executable=True,
            normalization_state="assumed",
        )

        payload = response.model_dump()
        self.assertEqual(payload["parsed_strategy"]["strategy_spec"]["strategy_type"], "rsi_threshold")
        self.assertEqual(payload["parsed_strategy"]["strategy_spec"]["signal"]["period"], 14)
        self.assertNotIn("unexpected_field", payload["parsed_strategy"]["strategy_spec"])

    def test_parse_response_keeps_generic_strategy_spec_fallback_for_unsupported_payload(self) -> None:
        response = RuleBacktestParseResponse(
            code="AAPL",
            strategy_text="如果大盘跌破均线则空仓，否则按自定义规则执行",
            parsed_strategy={
                "strategy_kind": "rule_conditions",
                "strategy_spec": {
                    "version": "v1",
                    "strategy_type": "custom_unsupported_strategy",
                    "strategy_family": "custom_unsupported_strategy",
                    "symbol": "AAPL",
                    "timeframe": "daily",
                    "support": {
                        "executable": False,
                        "normalization_state": "unsupported",
                        "requires_confirmation": True,
                        "unsupported_reason": "nested_logic",
                        "detected_strategy_family": "moving_average_crossover",
                    },
                    "custom_branching": {"if": "index_below_ma", "then": "flat"},
                    "custom_threshold": 5,
                },
            },
            normalized_strategy_family=None,
            detected_strategy_family="moving_average_crossover",
            executable=False,
            normalization_state="unsupported",
        )

        payload = response.model_dump()
        self.assertEqual(payload["parsed_strategy"]["strategy_spec"]["strategy_type"], "custom_unsupported_strategy")
        self.assertEqual(payload["parsed_strategy"]["strategy_spec"]["custom_branching"]["if"], "index_below_ma")
        self.assertEqual(payload["parsed_strategy"]["strategy_spec"]["custom_threshold"], 5)

    def test_clear_backtest_samples_maps_value_error_to_validation_error(self) -> None:
        service = MagicMock()
        service.clear_backtest_samples.side_effect = ValueError("code is required")

        with patch("api.v1.endpoints.backtest.BacktestService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                clear_backtest_samples(BacktestCodeRequest(code=""), db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail["error"], "validation_error")
        self.assertEqual(ctx.exception.detail["message"], "code is required")


if __name__ == "__main__":
    unittest.main()
