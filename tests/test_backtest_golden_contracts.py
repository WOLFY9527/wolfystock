# -*- coding: utf-8 -*-
"""Golden fixture contract tests for public backtest DTO boundaries."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from api.v1.schemas.backtest import (
    RuleBacktestCompareResponse,
    RuleBacktestExecutionTraceExportResponse,
    RuleBacktestRobustnessEvidenceExportResponse,
    RuleBacktestRunResponse,
    RuleBacktestSupportBundleManifestResponse,
    RuleBacktestSupportExportIndexResponse,
    RuleBacktestUniverseJobDiagnostics,
    RuleBacktestUniverseResultsResponse,
)


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "backtest"
FORBIDDEN_PUBLIC_TERMS = (
    "authorization",
    "bearer ",
    "cookie",
    "set-cookie",
    "session_id",
    "api_key",
    "access_token",
    "refresh_token",
    "password",
    "credential",
    "raw_provider_payload",
    "raw_payload",
    "provider_payload",
    "request_body",
    "response_body",
    "stack_trace",
    "traceback",
)
RESULT_REQUIRED_KEYS = {
    "id",
    "code",
    "status",
    "strategy_text",
    "parsed_strategy",
    "trade_count",
    "total_return_pct",
    "benchmark_return_pct",
    "buy_and_hold_return_pct",
    "max_drawdown_pct",
    "win_rate_pct",
    "final_equity",
    "execution_model",
    "artifact_availability",
    "readback_integrity",
    "result_authority",
}
EXPORT_KEYS = [
    "support_bundle_manifest_json",
    "support_bundle_reproducibility_manifest_json",
    "execution_trace_json",
    "execution_trace_csv",
    "robustness_evidence_json",
    "regime_attribution_readiness_json",
    "execution_model_metadata_json",
    "oos_parameter_readiness_json",
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
)
FACTOR_LAB_DIMENSION_STATE_VALUES = {"available", "missing", "ambiguous"}
FACTOR_LAB_TRACKED_DIMENSIONS = (
    ("p0", "pit_as_of", "Point-in-time universe and as-of policy"),
    ("p0", "survivorship_delisted", "Survivorship and delisted-symbol handling"),
    ("p0", "corporate_actions", "Corporate action adjusted OHLC lineage"),
    ("p0", "calendar_session_halt_constraints", "Calendar, session, and halt constraints"),
    ("p0", "transaction_cost_realism", "Transaction cost, slippage, and impact model"),
    ("p0", "portfolio_rebalance_model", "Portfolio rebalance model"),
    ("p0", "dataset_snapshot_version_source_authority", "Dataset snapshot, version, and authority"),
    ("p1", "decile_returns", "Decile returns"),
    ("p1", "panel_contract", "Panel contract"),
    ("p1", "forward_return_generation", "Forward return generation"),
    ("p1", "neutralization", "Neutralization"),
    ("p1", "factor_correlation", "Factor correlation"),
    ("p1", "multi_factor_composition", "Multi-factor composition"),
    ("p1", "oos_walk_forward", "Out-of-sample walk-forward"),
    ("p1", "parameter_stability", "Parameter stability"),
)
FACTOR_LAB_SUPPORT_EXPORT_FORBIDDEN_EXPORT_KEYS = {
    "factor_lab_readiness_json",
    "backtest_factor_lab_readiness_json",
    "professional_readiness_json",
    "factor_lab_professional_readiness_json",
}
FACTOR_LAB_SUPPORT_EXPORT_FORBIDDEN_TERMS = (
    "packetkind",
    "packet_kind",
    "professionalready",
    "professional_ready",
    "productstate",
    "product_state",
    "dimensioncounts",
    "dimension_counts",
    "factorlabreadiness",
    "factor_lab_readiness",
    "factor-lab-readiness",
    "backtest_factor_lab_readiness",
)
FACTOR_LAB_PACKET_FORBIDDEN_ADVICE_TERMS = (
    "personalized financial advice",
    "trade recommendation",
    "order ticket",
    "execution ready",
    "guaranteed return",
    "professional quant ready",
)


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _iter_strings(item)
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)
        return
    if isinstance(value, str):
        yield value


def _assert_iso_timestamp(value: str | None) -> None:
    assert value
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def _assert_no_sensitive_public_payload(value: Any) -> None:
    public_text = "\n".join(_iter_strings(value)).lower()
    for term in FORBIDDEN_PUBLIC_TERMS:
        assert term not in public_text


def _assert_no_live_provider_authority(value: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True).lower()
    assert '"source": "live"' not in serialized
    assert '"is_live": true' not in serialized
    assert '"live_provider_calls_executed": true' not in serialized
    assert '"providercalls": true' not in serialized
    assert "rerun" not in serialized
    assert "recalculate" not in serialized


def _assert_no_robustness_optimizer_semantics(value: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True).lower()
    for term in FORBIDDEN_ROBUSTNESS_OPTIMIZER_TERMS:
        assert term not in serialized


def _extract_dimension_state(metadata: dict[str, Any], dimension_id: str) -> str | None:
    raw_value = metadata.get(dimension_id)
    if isinstance(raw_value, str) and raw_value in FACTOR_LAB_DIMENSION_STATE_VALUES:
        return raw_value
    if isinstance(raw_value, dict):
        for key in ("state", "availability", "status"):
            value = raw_value.get(key)
            if isinstance(value, str) and value in FACTOR_LAB_DIMENSION_STATE_VALUES:
                return value
    return None


def _missing_prerequisite_state(missing_professional_prerequisites: Any, dimension_id: str) -> str | None:
    if isinstance(missing_professional_prerequisites, dict):
        return "missing" if dimension_id in missing_professional_prerequisites else None
    if isinstance(missing_professional_prerequisites, (list, tuple, set)):
        return "missing" if dimension_id in missing_professional_prerequisites else None
    return None


def _missing_reason_codes(missing_professional_prerequisites: Any, dimension_id: str, state: str) -> list[str]:
    if state == "available":
        return []
    if state == "ambiguous":
        return [f"{dimension_id}_ambiguous_or_not_supplied"]
    if isinstance(missing_professional_prerequisites, dict):
        reasons = missing_professional_prerequisites.get(dimension_id)
        if isinstance(reasons, list) and all(isinstance(item, str) for item in reasons):
            return reasons
        if isinstance(reasons, str):
            return [reasons]
    return [f"{dimension_id}_missing"]


def build_backtest_factor_lab_readiness_packet(
    *,
    backtest_readiness: dict[str, Any],
    factor_metrics_availability: dict[str, Any],
    bridge_manifest: dict[str, Any],
    data_lineage: dict[str, Any],
    missing_professional_prerequisites: Any,
) -> dict[str, Any]:
    metadata_sources = (
        ("backtest_readiness", backtest_readiness),
        ("factor_metrics_availability", factor_metrics_availability),
        ("bridge_manifest", bridge_manifest),
        ("data_lineage", data_lineage),
    )
    dimensions: dict[str, list[dict[str, Any]]] = {"p0": [], "p1": []}
    dimension_counts = {"total": 0, "available": 0, "missing": 0, "ambiguous": 0}

    for priority, dimension_id, label in FACTOR_LAB_TRACKED_DIMENSIONS:
        states = [
            state
            for _, metadata in metadata_sources
            if (state := _extract_dimension_state(metadata, dimension_id)) is not None
        ]
        missing_state = _missing_prerequisite_state(missing_professional_prerequisites, dimension_id)
        if missing_state is not None:
            states.append(missing_state)

        state_set = set(states)
        state = states[0] if len(state_set) == 1 else "ambiguous"
        if not states:
            state = "ambiguous"

        ready = state == "available"
        source_sections = [
            source_name
            for source_name, metadata in metadata_sources
            if _extract_dimension_state(metadata, dimension_id) is not None
        ]
        if missing_state is not None:
            source_sections.append("missing_professional_prerequisites")
        source_sections = source_sections or ["not_supplied_by_caller"]
        missing_reason_codes = _missing_reason_codes(missing_professional_prerequisites, dimension_id, state)
        summary = {
            "available": "Caller supplied explicit positive evidence.",
            "missing": "Caller supplied explicit missing prerequisite evidence.",
            "ambiguous": "Caller evidence is absent, unknown, or mixed.",
        }[state]

        dimensions[priority].append(
            {
                "id": dimension_id,
                "priority": priority,
                "label": label,
                "state": state,
                "ready": ready,
                "summary": summary,
                "missingReasonCodes": missing_reason_codes,
                "components": [
                    {
                        "id": "caller_supplied_metadata",
                        "label": "Caller supplied metadata",
                        "state": state,
                        "ready": ready,
                        "summary": summary,
                        "missingReasonCodes": missing_reason_codes,
                        "evidencePaths": [f"{section}.{dimension_id}" for section in source_sections],
                        "sourceSections": source_sections,
                    }
                ],
            }
        )
        dimension_counts["total"] += 1
        dimension_counts[state] += 1

    blocking_dimension_ids = [
        dimension["id"]
        for priority_dimensions in dimensions.values()
        for dimension in priority_dimensions
        if not dimension["ready"]
    ]
    professional_ready = not blocking_dimension_ids
    blocking_priority = None
    if any(not dimension["ready"] for dimension in dimensions["p0"]):
        blocking_priority = "p0"
    elif any(not dimension["ready"] for dimension in dimensions["p1"]):
        blocking_priority = "p1"

    return {
        "packetKind": "backtest_factor_lab_readiness",
        "packetVersion": "v1",
        "observeOnly": True,
        "professionalReady": professional_ready,
        "productState": "professional_ready" if professional_ready else "observe_only_not_professional_ready",
        "summary": "Research-readiness metadata packet built from caller-supplied evidence only.",
        "inputObservations": {
            "inputSource": "caller_supplied_metadata_only",
            "callerSuppliedSections": [source_name for source_name, _ in metadata_sources]
            + ["missing_professional_prerequisites"],
            "runtimePathsExecuted": {
                "engineRunsExecuted": False,
                "providerCallsExecuted": False,
                "marketCacheAccessed": False,
                "dbPathsExecuted": False,
                "apiPathsExecuted": False,
                "frontendPathsExecuted": False,
            },
        },
        "dimensionCounts": dimension_counts,
        "blockingPriority": blocking_priority,
        "blockingDimensionIds": blocking_dimension_ids,
        "dimensions": dimensions,
    }


def _assert_no_factor_lab_readiness_support_export_keys(value: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True).lower()
    for term in FACTOR_LAB_SUPPORT_EXPORT_FORBIDDEN_TERMS:
        assert term not in serialized


def _assert_no_factor_lab_readiness_advice_or_execution_overclaim(value: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True).lower()
    for term in FACTOR_LAB_PACKET_FORBIDDEN_ADVICE_TERMS:
        assert term not in serialized


def test_backtest_result_summary_golden_fixture_matches_public_readback_contract() -> None:
    payload = _load_fixture("rule_backtest_result_summary_dto.json")

    assert RESULT_REQUIRED_KEYS <= set(payload)
    result = RuleBacktestRunResponse(**payload).model_dump(by_alias=True)

    assert result["id"] == 7001
    assert result["code"] == "AAPL"
    assert result["status"] == "completed"
    _assert_iso_timestamp(result["run_at"])
    _assert_iso_timestamp(result["completed_at"])
    assert result["trade_count"] == 4
    assert result["total_return_pct"] == 12.4
    assert result["benchmark_return_pct"] == 8.1
    assert result["buy_and_hold_return_pct"] == 8.1
    assert result["max_drawdown_pct"] == 5.2
    assert result["win_rate_pct"] == 75.0
    assert result["final_equity"] == 112400.0
    assert result["summary"]["request"]["robustness_config"]["walk_forward"] == {
        "train_window": 36,
        "test_window": 18,
        "step": 9,
        "max_windows": 3,
    }
    assert result["summary"]["request"]["robustness_config"]["monte_carlo"] == {
        "simulation_count": 16,
        "seed": 4242,
        "noise_scale": 0.5,
    }
    assert result["summary"]["drawdown_regime_attribution"]["state"] == "unavailable"
    assert result["summary"]["drawdown_regime_attribution"]["source"] == "unavailable"
    assert result["summary"]["drawdown_regime_attribution"]["unavailable_reason"] == "stored_audit_rows_missing"
    assert result["robustness_analysis"]["seed"] == 4242
    assert result["robustness_analysis"]["configuration"]["walk_forward"] == {
        "train_window": 36,
        "test_window": 18,
        "step": 9,
        "max_windows": 3,
    }
    assert result["robustness_analysis"]["configuration"]["monte_carlo"] == {
        "simulation_count": 16,
        "seed": 4242,
        "noise_scale": 0.5,
    }

    strategy = result["parsed_strategy"]
    assert strategy["strategy_kind"] == "moving_average_crossover"
    assert strategy["strategy_spec"]["strategy_family"] == "moving_average_crossover"
    assert strategy["strategy_spec"]["symbol"] == "AAPL"

    execution_model = result["execution_model"]
    assert execution_model["signal_evaluation_timing"] == "bar_close"
    assert execution_model["entry_timing"] == "next_bar_open"
    assert execution_model["position_sizing"] == "single_position_full_notional"

    artifact_availability = result["artifact_availability"]
    assert artifact_availability["has_summary"] is True
    assert artifact_availability["has_metrics"] is True
    assert artifact_availability["has_execution_model"] is True
    assert artifact_availability["has_execution_trace"] is True

    readback_integrity = result["readback_integrity"]
    assert readback_integrity["integrity_level"] == "stored_complete"
    assert readback_integrity["used_legacy_fallback"] is False
    assert readback_integrity["used_live_storage_repair"] is False

    authority = result["result_authority"]
    assert authority["read_mode"] == "stored_first"
    assert authority["contract_version"] == "v1"
    assert {"summary", "metrics", "execution_model", "trade_rows", "execution_trace"} <= set(authority["domains"])
    assert authority["domains"]["metrics"]["source"] == "summary.metrics"
    assert authority["domains"]["execution_trace"]["state"] == "available"

    _assert_no_sensitive_public_payload(result)
    _assert_no_live_provider_authority(result)


def test_rule_backtest_compute_golden_fixture_is_compact_deterministic_and_sanitized() -> None:
    payload = _load_fixture("rule_backtest_compute_basic_long_cash.json")

    assert payload["fixture_kind"] == "rule_backtest_compute_golden"
    assert payload["fixture_version"] == "v1"
    assert payload["scenario"] == "basic_long_cash_next_open_with_costs"
    assert payload["strategy_text"] == "Buy when Close > MA3. Sell when Close < MA3."

    inputs = payload["inputs"]
    assert inputs["code"] == "SAFE"
    assert inputs["lookback_bars"] == 20
    assert inputs["execution"] == {"fee_bps": 2.5, "slippage_bps": 1.25}
    assert inputs["date_window"] == {"start_date": "2024-01-01", "end_date": "2024-01-08"}
    assert inputs["bars"]["start_date"] == "2024-01-01"
    assert len(inputs["bars"]["open"]) == 8
    assert len(inputs["bars"]["close"]) == 8

    expected = payload["expected"]
    assert expected["metrics"]["trade_count"] == 1
    assert expected["metrics"]["bars_used"] == 8
    assert expected["metrics"]["final_equity"] == 77620.334341
    assert expected["metrics"]["total_return_pct"] == -22.3797
    assert expected["metrics"]["max_drawdown_pct"] == 27.5272
    assert len(expected["selected_equity_points"]) == 4
    assert [point["date"] for point in expected["selected_equity_points"]] == [
        "2024-01-04",
        "2024-01-05",
        "2024-01-06",
        "2024-01-07",
    ]
    assert expected["trades"] == [
        {
            "entry_signal_date": "2024-01-04",
            "entry_date": "2024-01-05",
            "exit_signal_date": "2024-01-06",
            "exit_date": "2024-01-07",
            "entry_price": 11.2014,
            "exit_price": 8.698912,
            "return_pct": -22.3797,
            "quantity": 8925.224191,
            "fees": 44.403688,
            "slippage": 22.201495,
            "entry_reason": "signal_entry",
            "exit_reason": "signal_exit",
            "signal_reason": "rule_conditions",
            "notes": "exit_signal_next_bar_open",
        }
    ]

    _assert_no_sensitive_public_payload(payload)
    _assert_no_live_provider_authority(payload)


def test_rule_backtest_semantics_freeze_fixture_covers_current_v1_boundaries() -> None:
    payload = _load_fixture("rule_backtest_semantics_freeze_v1.json")

    assert payload["fixture_kind"] == "rule_backtest_semantics_freeze"
    assert payload["fixture_version"] == "v1"
    assert payload["scope"] == {
        "execution_model_id": "rule_backtest_default_execution_model_v1",
        "lane": "single_symbol_deterministic_rule_backtest",
        "standard_historical_evaluation_lane": "out_of_scope",
        "stored_result_semantics": "unchanged",
    }

    template = payload["deterministic_template_behavior"]
    assert template["strategy_text"] == "Buy when Close > MA3. Sell when Close < MA3."
    assert template["expected_parse"] == {
        "strategy_kind": "rule_conditions",
        "entry_text": "Close > MA3",
        "exit_text": "Close < MA3",
        "max_lookback": 3,
        "strategy_spec": {},
    }
    assert template["expected_execution_model"]["entry_timing"] == "next_bar_open"
    assert template["expected_execution_model"]["exit_timing"] == "next_bar_open"
    assert template["expected_execution_model"]["position_sizing"] == "single_position_full_notional"
    assert template["expected_execution_model"]["market_rules"] == {
        "trading_day_execution": "available_bars_only",
        "terminal_bar_fill_fallback": "same_bar_close",
        "window_end_position_handling": "force_flatten",
    }

    costs = payload["cost_slippage_current_treatment"]
    assert costs["source_fixture"] == "rule_backtest_compute_basic_long_cash.json"
    assert costs["model"] == "bps_per_side"
    assert costs["fee_bps_per_side"] == 2.5
    assert costs["slippage_bps_per_side"] == 1.25
    assert costs["expected"] == {
        "final_equity": 77620.334341,
        "total_return_pct": -22.3797,
        "trade_count": 1,
        "entry_price": 11.2014,
        "exit_price": 8.698912,
        "quantity": 8925.224191,
        "fees": 44.403688,
        "slippage": 22.201495,
        "notes": "exit_signal_next_bar_open",
    }
    assert costs["non_goals"] == [
        "spread_simulation",
        "market_impact",
        "partial_fills",
        "tax_or_stamp_duty_model",
        "volume_participation_cap",
    ]

    cases = payload["sample_window_behavior"]["cases"]
    assert [case["case_id"] for case in cases] == [
        "tail_window_from_lookback_bars_without_explicit_dates",
        "explicit_date_window_ignores_larger_lookback_tail_selection",
    ]
    assert cases[0]["inputs"]["lookback_bars"] == 3
    assert cases[0]["inputs"]["date_window"] == {"start_date": None, "end_date": None}
    assert cases[0]["expected"]["metrics"]["period_start"] == "2024-01-04"
    assert cases[0]["expected"]["metrics"]["period_end"] == "2024-01-06"
    assert cases[0]["expected"]["metrics"]["bars_used"] == 3
    assert cases[1]["inputs"]["lookback_bars"] == 20
    assert cases[1]["inputs"]["date_window"] == {
        "start_date": "2024-01-04",
        "end_date": "2024-01-06",
    }
    assert cases[1]["expected"]["metrics"]["period_start"] == "2024-01-04"
    assert cases[1]["expected"]["metrics"]["period_end"] == "2024-01-06"
    assert cases[1]["expected"]["metrics"]["bars_used"] == 3
    for case in cases:
        assert case["expected"]["selected_equity_points"][-1]["executed_action"] == "forced_close"
        assert case["expected"]["selected_equity_points"][-1]["notes"] == "forced_close_at_window_end"
        assert case["expected"]["trades"][-1]["exit_reason"] == "final_close"

    boundary = payload["no_order_no_broker_boundary"]
    assert boundary["runtime_paths_executed"] == {
        "broker_calls_executed": False,
        "order_placement_executed": False,
        "portfolio_mutation_executed": False,
        "provider_calls_required": False,
        "live_provider_calls_required": False,
    }
    assert set(boundary["forbidden_output_markers"]) == {
        "/api/v1/broker",
        "/api/v1/orders",
        "broker_order_execution",
        "order_placement",
        "place_order",
        "submit_order",
        "execute_order",
        "portfolio_mutation",
    }
    assert all(value is False for value in boundary["runtime_paths_executed"].values())

    assert payload["future_change_policy"] == {
        "engine_behavior_change_requires_new_fixture_version": True,
        "api_contract_change_out_of_scope": True,
        "provider_runtime_change_out_of_scope": True,
        "broker_or_order_execution_out_of_scope": True,
        "frontend_redesign_out_of_scope": True,
    }
    _assert_no_sensitive_public_payload(payload)
    _assert_no_live_provider_authority(payload)


def test_rule_backtest_shadow_cli_fixtures_are_parser_free_explicit_and_sanitized() -> None:
    expected_cases = {
        "rule_backtest_compute_shadow_cli_v1.json": {
            "contract_version": "shadow_cli_v1",
            "case_id": "rule_conditions_close_vs_ma3_long_cash",
            "date_window": {"start_date": "2024-01-01", "end_date": "2024-01-08"},
            "strategy_kind": "rule_conditions",
            "entry_text": "Close > MA3",
            "exit_text": "Close < MA3",
            "max_lookback": 3,
            "strategy_spec": {
                "strategy_type": "rule_conditions",
                "indicator_family": "sma_close_rule_conditions",
                "price_basis": "close",
                "signal_window": 3,
            },
            "bars_count": 8,
            "trade_count": 1,
            "final_equity": 77620.334341,
            "total_return_pct": -22.3797,
            "selected_actions": [None, "buy", None, "sell"],
            "selected_dates": ["2024-01-04", "2024-01-05", "2024-01-06", "2024-01-07"],
            "trades": [
                {
                    "entry_signal_date": "2024-01-04",
                    "entry_date": "2024-01-05",
                    "exit_signal_date": "2024-01-06",
                    "exit_date": "2024-01-07",
                    "entry_price": 11.2014,
                    "exit_price": 8.698912,
                    "return_pct": -22.3797,
                    "quantity": 8925.224191,
                    "fees": 44.403688,
                    "slippage": 22.201495,
                    "entry_reason": "signal_entry",
                    "exit_reason": "signal_exit",
                    "signal_reason": "rule_conditions",
                    "notes": "exit_signal_next_bar_open",
                }
            ],
        },
        "rule_backtest_compute_shadow_cli_v2.json": {
            "contract_version": "shadow_cli_v1",
            "case_id": "rule_conditions_close_vs_ma3_no_trade",
            "date_window": {"start_date": "2024-01-01", "end_date": "2024-01-08"},
            "strategy_kind": "rule_conditions",
            "entry_text": "Close > MA3",
            "exit_text": "Close < MA3",
            "max_lookback": 3,
            "strategy_spec": {
                "strategy_type": "rule_conditions",
                "indicator_family": "sma_close_rule_conditions",
                "price_basis": "close",
                "signal_window": 3,
            },
            "bars_count": 8,
            "trade_count": 0,
            "final_equity": 100000.0,
            "total_return_pct": 0.0,
            "selected_actions": [None, None, None, None],
            "selected_dates": ["2024-01-04", "2024-01-05", "2024-01-06", "2024-01-07"],
            "trades": [],
        },
        "rule_backtest_compute_shadow_cli_v3_terminal_forced_close.json": {
            "contract_version": "shadow_cli_v1",
            "case_id": "rule_conditions_close_vs_ma3_terminal_forced_close",
            "date_window": {"start_date": "2024-01-01", "end_date": "2024-01-08"},
            "strategy_kind": "rule_conditions",
            "entry_text": "Close > MA3",
            "exit_text": "Close < MA3",
            "max_lookback": 3,
            "strategy_spec": {
                "strategy_type": "rule_conditions",
                "indicator_family": "sma_close_rule_conditions",
                "price_basis": "close",
                "signal_window": 3,
            },
            "bars_count": 8,
            "trade_count": 1,
            "final_equity": 126118.967526,
            "total_return_pct": 26.119,
            "selected_actions": [None, "buy", None, "forced_close"],
            "selected_dates": ["2024-01-05", "2024-01-06", "2024-01-07", "2024-01-08"],
            "trades": [
                {
                    "entry_signal_date": "2024-01-05",
                    "entry_date": "2024-01-06",
                    "exit_signal_date": "2024-01-08",
                    "exit_date": "2024-01-08",
                    "entry_price": 10.301288,
                    "exit_price": 12.998375,
                    "return_pct": 26.119,
                    "quantity": 9705.098149,
                    "fees": 56.531378,
                    "slippage": 28.266098,
                    "entry_reason": "signal_entry",
                    "exit_reason": "final_close",
                    "signal_reason": "rule_conditions",
                    "notes": "forced_close_at_window_end",
                }
            ],
        },
        "rule_backtest_compute_shadow_cli_v4_ma_crossover.json": {
            "contract_version": "shadow_cli_v4",
            "case_id": "moving_average_crossover_fast_slow_long_cash",
            "date_window": {"start_date": "2024-01-01", "end_date": "2024-01-10"},
            "strategy_kind": "moving_average_crossover",
            "entry_text": None,
            "exit_text": None,
            "max_lookback": 5,
            "strategy_spec": {
                "version": "v1",
                "strategy_type": "moving_average_crossover",
                "strategy_family": "moving_average_crossover",
                "symbol": "SAFE",
                "timeframe": "daily",
                "max_lookback": 5,
                "date_range": {
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-10",
                },
                "capital": {
                    "initial_capital": 100000.0,
                    "currency": "USD",
                },
                "costs": {
                    "fee_bps": 2.5,
                    "slippage_bps": 1.25,
                },
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
                "end_behavior": {
                    "policy": "liquidate_at_end",
                    "price_basis": "close",
                },
                "support": {
                    "executable": True,
                    "normalization_state": "ready",
                    "requires_confirmation": False,
                    "unsupported_reason": None,
                    "detected_strategy_family": "moving_average_crossover",
                },
            },
            "bars_count": 10,
            "trade_count": 1,
            "final_equity": 71250.889614,
            "total_return_pct": -28.7491,
            "selected_actions": [None, "buy", None, "sell"],
            "selected_dates": ["2024-01-06", "2024-01-07", "2024-01-09", "2024-01-10"],
            "trades": [
                {
                    "entry_signal_date": "2024-01-06",
                    "entry_date": "2024-01-07",
                    "exit_signal_date": "2024-01-09",
                    "exit_date": "2024-01-10",
                    "entry_price": 11.501437,
                    "exit_price": 8.198975,
                    "return_pct": -28.7491,
                    "quantity": 8692.392255,
                    "fees": 42.810928,
                    "slippage": 21.405016,
                    "entry_reason": "signal_entry",
                    "exit_reason": "signal_exit",
                    "signal_reason": "rule_conditions",
                    "notes": "moving_average_crossover_exit_next_bar_open",
                }
            ],
        },
    }

    for fixture_name, expected_case in expected_cases.items():
        fixture_path = FIXTURE_DIR / fixture_name
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        serialized = fixture_path.read_text(encoding="utf-8").lower()

        assert payload["contract_version"] == expected_case["contract_version"]
        assert payload["case_id"] == expected_case["case_id"]
        assert set(payload) == {"contract_version", "case_id", "input", "expected_output"}
        assert "strategy_text" not in serialized
        assert "pyo3" not in serialized
        assert "maturin" not in serialized
        assert "cargo" not in serialized
        assert "runtime integration" not in serialized

        fixture_input = payload["input"]
        assert fixture_input["contract_version"] == payload["contract_version"]
        assert fixture_input["case_id"] == payload["case_id"]
        assert fixture_input["code"] == "SAFE"
        assert fixture_input["initial_capital"] == 100000.0
        assert fixture_input["lookback_bars"] == 20
        assert fixture_input["date_window"] == expected_case["date_window"]
        assert fixture_input["execution_model"]["entry_timing"] == "next_bar_open"
        assert fixture_input["execution_model"]["exit_timing"] == "next_bar_open"
        assert fixture_input["execution_model"]["market_rules"]["terminal_bar_fill_fallback"] == "same_bar_close"
        assert fixture_input["parsed_strategy"]["strategy_kind"] == expected_case["strategy_kind"]
        assert fixture_input["parsed_strategy"].get("entry", {}).get("text") == expected_case["entry_text"]
        assert fixture_input["parsed_strategy"].get("exit", {}).get("text") == expected_case["exit_text"]
        assert fixture_input["parsed_strategy"]["max_lookback"] == expected_case["max_lookback"]
        assert fixture_input["parsed_strategy"]["strategy_spec"] == expected_case["strategy_spec"]
        assert len(fixture_input["bars"]) == expected_case["bars_count"]
        assert all(
            set(bar) == {"date", "open", "high", "low", "close", "volume"}
            for bar in fixture_input["bars"]
        )
        if expected_case["strategy_kind"] == "moving_average_crossover":
            assert fixture_input["parsed_strategy"]["normalized_text"] == "SMA3 上穿 SMA5 买入，SMA3 下穿 SMA5 卖出。"
            assert fixture_input["parsed_strategy"]["summary"] == {
                "entry": "买入条件：SMA3 上穿 SMA5",
                "exit": "卖出条件：SMA3 下穿 SMA5",
                "strategy": "均线交叉策略",
            }
            assert fixture_input["parsed_strategy"]["executable"] is True
            assert fixture_input["parsed_strategy"]["normalization_state"] == "ready"
            assert fixture_input["parsed_strategy"]["assumptions"] == []
            assert fixture_input["parsed_strategy"]["assumption_groups"] == []
            assert fixture_input["parsed_strategy"]["detected_strategy_family"] == "moving_average_crossover"

        expected_output = payload["expected_output"]
        assert expected_output["contract_version"] == payload["contract_version"]
        assert expected_output["case_id"] == payload["case_id"]
        assert expected_output["execution_model"] == fixture_input["execution_model"]
        assert expected_output["execution_assumptions"]["entry_fill_timing"] == "next_bar_open"
        assert expected_output["execution_assumptions"]["exit_fill_timing"] == "next_bar_open; same_bar_close"
        assert expected_output["metrics"]["trade_count"] == expected_case["trade_count"]
        assert expected_output["metrics"]["final_equity"] == expected_case["final_equity"]
        assert expected_output["metrics"]["total_return_pct"] == expected_case["total_return_pct"]
        assert [point["date"] for point in expected_output["selected_equity_points"]] == expected_case["selected_dates"]
        assert [point["executed_action"] for point in expected_output["selected_equity_points"]] == expected_case[
            "selected_actions"
        ]
        assert expected_output["trades"] == expected_case["trades"]

        _assert_no_sensitive_public_payload(payload)
        _assert_no_live_provider_authority(payload)


def test_execution_trace_export_fixture_freezes_compact_public_trace_shape() -> None:
    payload = _load_fixture("rule_backtest_execution_trace_dto.json")

    trace = RuleBacktestExecutionTraceExportResponse(**payload).model_dump()

    assert trace["version"] == "v1"
    assert trace["source"] == "summary.execution_trace"
    assert trace["completeness"] == "complete"
    assert trace["missing_fields"] == []
    assert len(trace["trace_rows"]) == 3
    for row in trace["trace_rows"]:
        assert {"date", "event_type", "action", "signal_summary", "position", "total_portfolio_value"} <= set(row)
        assert "provider_response" not in row
        assert "request_headers" not in row

    rows_by_event = {row["event_type"]: row for row in trace["trace_rows"]}
    assert rows_by_event["action"]["action"] == "buy"
    assert rows_by_event["fallback"]["fallback"]["code"] == "open_missing_close_fallback"
    assert rows_by_event["anomaly"]["anomaly"]["code"] == "insufficient_next_bar_open"
    assert trace["fallback"]["run_fallback"] is False
    assert trace["fallback"]["trace_rebuilt"] is False
    assert trace["fallback"]["provider_authority"] == "none"

    _assert_no_sensitive_public_payload(trace)
    _assert_no_live_provider_authority(trace)


def test_robustness_evidence_export_fixture_freezes_stored_payload_shape() -> None:
    payload = _load_fixture("rule_backtest_robustness_evidence_dto.json")

    evidence = RuleBacktestRobustnessEvidenceExportResponse(**payload).model_dump()

    assert evidence["state"] == "research_prototype"
    assert evidence["profile"] == "single_symbol_fixture"
    assert evidence["source"] == "summary.robustness_analysis"
    assert evidence["seed"] == 4242
    assert evidence["configuration"]["walk_forward"] == {
        "train_window": 36,
        "test_window": 18,
        "step": 9,
        "max_windows": 3,
    }
    assert evidence["configuration"]["monte_carlo"] == {
        "simulation_count": 16,
        "seed": 4242,
        "noise_scale": 0.5,
    }

    _assert_no_sensitive_public_payload(evidence)
    _assert_no_live_provider_authority(evidence)
    _assert_no_robustness_optimizer_semantics(evidence)


def test_export_index_and_support_bundle_fixtures_freeze_stored_first_export_boundary() -> None:
    export_index = RuleBacktestSupportExportIndexResponse(
        **_load_fixture("rule_backtest_export_index_dto.json")
    ).model_dump()
    manifest = RuleBacktestSupportBundleManifestResponse(
        **_load_fixture("rule_backtest_support_bundle_manifest_dto.json")
    ).model_dump()
    reproducibility_authority_projection = {
        domain_name: {
            "source": domain_payload["source"],
            "completeness": domain_payload["completeness"],
            "state": domain_payload["state"],
        }
        for domain_name, domain_payload in manifest["result_authority"]["domains"].items()
    }

    assert export_index["run_id"] == 7001
    assert export_index["status"] == "completed"
    assert [item["key"] for item in export_index["exports"]] == EXPORT_KEYS
    assert [item["payload_class"] for item in export_index["exports"]] == [
        "compact",
        "compact",
        "heavy",
        "heavy",
        "heavy",
        "compact",
        "compact",
        "compact",
    ]
    for item in export_index["exports"]:
        assert item["delivery_mode"] == "api"
        assert item["endpoint_path"].startswith("/api/v1/backtest/rule/runs/7001/")
    assert export_index["exports"][0]["available"] is True
    assert export_index["exports"][1]["available"] is True
    assert export_index["exports"][2]["available"] is False
    assert export_index["exports"][2]["availability_reason"] == "execution_trace_rows_missing"
    assert export_index["exports"][3]["available"] is False
    assert export_index["exports"][3]["availability_reason"] == "execution_trace_rows_missing"
    assert export_index["exports"][4]["available"] is True
    assert export_index["exports"][4]["availability_reason"] == "stored_robustness_analysis_present"
    assert export_index["exports"][4]["endpoint_path"] == "/api/v1/backtest/rule/runs/7001/robustness-evidence.json"
    assert export_index["exports"][5]["available"] is True
    assert export_index["exports"][5]["availability_reason"] == "run_exists_readiness_projection_available"
    assert export_index["exports"][5]["endpoint_path"] == "/api/v1/backtest/rule/runs/7001/regime-attribution-readiness.json"
    assert export_index["exports"][6]["available"] is True
    assert (
        export_index["exports"][6]["availability_reason"]
        == "run_exists_execution_model_metadata_projection_available"
    )
    assert export_index["exports"][6]["endpoint_path"] == "/api/v1/backtest/rule/runs/7001/execution-model-metadata.json"
    assert export_index["exports"][7]["available"] is True
    assert (
        export_index["exports"][7]["availability_reason"]
        == "run_exists_oos_parameter_readiness_projection_available"
    )
    assert export_index["exports"][7]["endpoint_path"] == "/api/v1/backtest/rule/runs/7001/oos-parameter-readiness.json"

    assert manifest["manifest_kind"] == "rule_backtest_support_bundle"
    assert manifest["run"]["id"] == export_index["run_id"]
    assert manifest["result_authority"]["read_mode"] == "stored_first"
    assert manifest["result_authority"]["contract_version"] == "v1"
    assert reproducibility_authority_projection["execution_trace"] == {
        "source": "summary.execution_trace",
        "completeness": "complete",
        "state": "available",
    }
    assert reproducibility_authority_projection["summary"] == {
        "source": "row.summary_json",
        "completeness": "complete",
        "state": "available",
    }
    assert manifest["result_authority"]["domains"]["execution_trace"]["source"] == "summary.execution_trace"
    assert manifest["result_authority"]["domains"]["execution_trace"]["state"] == "available"
    assert manifest["artifact_availability"]["has_summary"] is True
    assert manifest["readback_integrity"]["integrity_level"] == "stored_complete"
    assert manifest["artifact_counts"]["execution_trace_rows_count"] == 3
    assert manifest["artifact_counts"]["execution_trace_rows_count"] > 0
    assert not ({"trades", "equity_curve", "audit_rows", "execution_trace"} & set(manifest))

    _assert_no_sensitive_public_payload(export_index)
    _assert_no_sensitive_public_payload(manifest)
    _assert_no_live_provider_authority(export_index)
    _assert_no_live_provider_authority(manifest)


def test_factor_lab_readiness_packet_stays_observe_only_and_outside_support_export_boundary() -> None:
    packet = build_backtest_factor_lab_readiness_packet(
        backtest_readiness={
            "pit_as_of": {"state": "available", "evidence": "fixture-pit-policy"},
            "survivorship_delisted": {"state": "missing", "evidence": "delisted-policy-not-supplied"},
            "corporate_actions": {"state": "available", "evidence": "adjusted-ohlc-lineage"},
            "transaction_cost_realism": {"state": "available", "evidence": "cost-model-metadata"},
        },
        factor_metrics_availability={
            "decile_returns": {"state": "available", "evidence": "decile-table-metadata"},
            "neutralization": {"state": "ambiguous", "evidence": "neutralization-not-declared"},
            "parameter_stability": {"state": "missing", "evidence": "oos-stability-not-supplied"},
        },
        bridge_manifest={
            "panel_contract": {"state": "available", "evidence": "panel-contract-v1"},
            "forward_return_generation": {"state": "available", "evidence": "forward-return-rule"},
        },
        data_lineage={
            "dataset_snapshot_version_source_authority": {
                "state": "ambiguous",
                "evidence": "snapshot-authority-not-declared",
            }
        },
        missing_professional_prerequisites={
            "survivorship_delisted": ["survivorship_delisted_missing"],
            "calendar_session_halt_constraints": ["calendar_session_halt_constraints_missing"],
            "portfolio_rebalance_model": ["portfolio_rebalance_model_missing"],
        },
    )

    assert set(packet) == {
        "packetKind",
        "packetVersion",
        "observeOnly",
        "professionalReady",
        "productState",
        "summary",
        "inputObservations",
        "dimensionCounts",
        "blockingPriority",
        "blockingDimensionIds",
        "dimensions",
    }
    assert packet["packetKind"] == "backtest_factor_lab_readiness"
    assert packet["packetVersion"] == "v1"
    assert packet["observeOnly"] is True
    assert packet["professionalReady"] is False
    assert packet["productState"] == "observe_only_not_professional_ready"
    assert packet["blockingPriority"] == "p0"
    assert {"survivorship_delisted", "calendar_session_halt_constraints", "portfolio_rebalance_model"} <= set(
        packet["blockingDimensionIds"]
    )
    assert packet["dimensionCounts"]["total"] == len(FACTOR_LAB_TRACKED_DIMENSIONS)
    assert packet["dimensionCounts"]["missing"] >= 3
    assert packet["dimensionCounts"]["ambiguous"] >= 1
    assert packet["inputObservations"]["inputSource"] == "caller_supplied_metadata_only"
    assert all(value is False for value in packet["inputObservations"]["runtimePathsExecuted"].values())
    assert json.loads(json.dumps(packet, ensure_ascii=False, sort_keys=True)) == packet
    _assert_no_factor_lab_readiness_advice_or_execution_overclaim(packet)

    raw_export_index = _load_fixture("rule_backtest_export_index_dto.json")
    raw_manifest = _load_fixture("rule_backtest_support_bundle_manifest_dto.json")
    support_export_keys = [item["key"] for item in raw_export_index["exports"]]

    assert support_export_keys == EXPORT_KEYS
    assert FACTOR_LAB_SUPPORT_EXPORT_FORBIDDEN_EXPORT_KEYS.isdisjoint(support_export_keys)
    _assert_no_factor_lab_readiness_support_export_keys(raw_export_index)
    _assert_no_factor_lab_readiness_support_export_keys(raw_manifest)


def test_compare_golden_fixture_is_stored_first_and_contains_no_recalculation_semantics() -> None:
    payload = _load_fixture("rule_backtest_compare_dto.json")
    payload["heatmap_projection"] = _load_fixture("rule_backtest_compare_heatmap_dto.json")

    compare = RuleBacktestCompareResponse(**payload).model_dump()

    assert compare["comparison_source"] == "stored_rule_backtest_runs"
    assert compare["read_mode"] == "stored_first"
    assert compare["requested_run_ids"] == [7001, 7002, 7999]
    assert compare["resolved_run_ids"] == [7001, 7002]
    assert compare["comparable_run_ids"] == [7001, 7002]
    assert compare["missing_run_ids"] == [7999]
    assert compare["comparison_summary"]["baseline"]["run_id"] == 7001
    assert compare["comparison_summary"]["baseline"]["selection_rule"] == "first_comparable_run_by_request_order"
    assert compare["market_code_comparison"]["relationship"] == "same_code"
    assert compare["period_comparison"]["relationship"] == "overlapping"
    assert compare["parameter_comparison"]["state"] == "same_family_comparable"
    assert compare["robustness_summary"]["overall_state"] == "partially_comparable"
    assert compare["comparison_profile"]["primary_profile"] == "same_strategy_parameter_variants"
    assert compare["comparison_highlights"]["highlights"]["total_return_pct"]["state"] == "limited_context_winner"
    assert compare["parameter_stability_evidence"]["contract_kind"] == "backtest_parameter_stability_diagnostic_evidence"
    assert compare["parameter_stability_evidence"]["source"] == "stored_compare_summary"
    assert compare["parameter_stability_evidence"]["diagnostic_only"] is True
    assert compare["parameter_stability_evidence"]["decision_grade"] is False
    assert compare["parameter_stability_evidence"]["parameter_set_count"] == 2
    assert compare["parameter_stability_evidence"]["authority"]["execution_count"] == 0
    assert compare["parameter_stability_evidence"]["authority"]["provider_calls_executed"] is False
    assert compare["heatmap_projection"]["source"] == "stored_compare_projection"
    assert compare["heatmap_projection"]["read_mode"] == "stored_projection_only"
    assert compare["heatmap_projection"]["authority"]["execution_count"] == 0
    assert compare["heatmap_projection"]["authority"]["provider_calls_executed"] is False
    assert compare["heatmap_projection"]["authority"]["authority_scope"] == "stored_compare_derived_heatmap_only"
    assert compare["heatmap_projection"]["axes"]["x"]["axis_key"] == "strategy_spec.signal.fast_period"
    assert compare["heatmap_projection"]["metric_keys"] == ["total_return_pct", "max_drawdown_pct"]
    assert len(compare["items"]) == 2
    assert compare["items"][0]["metadata"]["id"] == 7001
    assert compare["items"][1]["metadata"]["id"] == 7002
    for item in compare["items"]:
        assert item["metadata"]["status"] == "completed"
        assert item["result_authority"]["read_mode"] == "stored_first"
        assert {"trade_count", "total_return_pct", "max_drawdown_pct", "win_rate_pct", "final_equity"} <= set(
            item["metrics"]
        )

    _assert_no_sensitive_public_payload(compare)
    _assert_no_live_provider_authority(compare)
    _assert_no_robustness_optimizer_semantics(compare["heatmap_projection"])
    _assert_no_robustness_optimizer_semantics(compare["parameter_stability_evidence"])


def test_compare_heatmap_golden_fixture_freezes_stored_compare_projection_vocabulary() -> None:
    heatmap = _load_fixture("rule_backtest_compare_heatmap_dto.json")

    assert heatmap["contract_kind"] == "rule_backtest_compare_heatmap_projection"
    assert heatmap["contract_version"] == "v1"
    assert heatmap["source"] == "stored_compare_projection"
    assert heatmap["read_mode"] == "stored_projection_only"

    authority = heatmap["authority"]
    assert authority["projection_basis"] == "stored_compare_payloads"
    assert authority["execution_mode"] == "no_reexecution"
    assert authority["execution_count"] == 0
    assert authority["provider_calls_executed"] is False
    assert authority["compare_payload_reused"] is True
    assert authority["authority_scope"] == "stored_compare_derived_heatmap_only"

    assert heatmap["source_run_ids"] == [7001, 7002, 7003]
    assert heatmap["requested_compare_run_ids"] == [7001, 7002, 7003, 7999]
    assert heatmap["resolved_compare_run_ids"] == [7001, 7002, 7003]
    assert heatmap["missing_run_ids"] == [7999]
    assert heatmap["metric_keys"] == ["total_return_pct", "max_drawdown_pct"]

    x_axis = heatmap["axes"]["x"]
    y_axis = heatmap["axes"]["y"]
    assert x_axis["axis_key"] == "strategy_spec.signal.fast_period"
    assert x_axis["values"] == [5, 10]
    assert y_axis["axis_key"] == "strategy_spec.signal.slow_period"
    assert y_axis["values"] == [20, 50, None]

    cells = heatmap["cells"]
    assert len(cells) == 4
    states = {(cell["x_value"], cell["y_value"]): cell["availability_state"] for cell in cells}
    assert states[(5, 20)] == "available"
    assert states[(10, 50)] == "available"
    assert states[(5, 50)] == "missing"
    assert states[(10, None)] == "ambiguous"

    available_cell = next(cell for cell in cells if cell["x_value"] == 5 and cell["y_value"] == 20)
    assert available_cell["source_run_ids"] == [7001]
    assert available_cell["metrics"]["total_return_pct"]["value"] == 12.4
    assert available_cell["metrics"]["max_drawdown_pct"]["value"] == 5.2

    missing_cell = next(cell for cell in cells if cell["availability_state"] == "missing")
    assert missing_cell["source_run_ids"] == []
    assert missing_cell["metrics"]["total_return_pct"]["state"] == "missing"
    assert missing_cell["metrics"]["max_drawdown_pct"]["state"] == "missing"

    ambiguous_cell = next(cell for cell in cells if cell["availability_state"] == "ambiguous")
    assert ambiguous_cell["source_run_ids"] == [7002, 7003]
    assert ambiguous_cell["metrics"]["total_return_pct"]["state"] == "ambiguous"
    assert ambiguous_cell["metrics"]["max_drawdown_pct"]["state"] == "ambiguous"

    forbidden_compact_terms = {"trades", "equity_curve", "audit_rows", "execution_trace", "provider_payload"}
    assert not forbidden_compact_terms & set(heatmap)

    _assert_no_sensitive_public_payload(heatmap)
    _assert_no_live_provider_authority(heatmap)
    _assert_no_robustness_optimizer_semantics(heatmap)


def test_universe_job_golden_fixtures_freeze_local_only_diagnostics_and_compact_rows() -> None:
    diagnostics = RuleBacktestUniverseJobDiagnostics(
        **_load_fixture("rule_backtest_universe_job_diagnostics_dto.json")
    ).model_dump()
    results = RuleBacktestUniverseResultsResponse(**_load_fixture("rule_backtest_universe_results_dto.json")).model_dump()

    assert diagnostics["job_id"] == 9001
    assert diagnostics["progress"]["status"] == "completed_with_failures"
    assert diagnostics["progress"]["total_count"] == 3
    assert diagnostics["progress"]["processed_count"] == 3
    assert diagnostics["progress"]["progress_pct"] == 100.0
    reasons = {item["reason_code"]: item for item in diagnostics["reason_summary"]}
    assert reasons["completed"]["count"] == 2
    assert reasons["blocked_missing_local_data"]["sample_symbols"] == ["ZZZ"]
    assert diagnostics["local_data_coverage"] == {
        "ready": 2,
        "partial": 0,
        "missing": 1,
        "insufficient_data": 0,
        "unknown": 0,
    }
    metadata = diagnostics["metadata"]
    assert metadata["local_only"] is True
    assert metadata["live_provider_calls_executed"] is False
    assert metadata["concurrency_enabled"] is False
    assert metadata["professionalReadiness"]["local_data_coverage_state"] == metadata["localDataCoverageState"]
    assert metadata["localDataCoverageState"] == "mixed"
    assert metadata["pointInTimeUniverse"] is False
    assert metadata["survivorshipBiasState"] == "uncontrolled"
    assert metadata["professionalReadiness"]["provider_calls"] is False
    assert metadata["providerCalls"] is False
    assert metadata["professionalReadiness"]["overall_state"] == "research_prototype"
    assert metadata["professionalReadiness"]["professional_quant_ready"] is False

    assert results["job_id"] == diagnostics["job_id"]
    assert results["total"] == 3
    assert [item["symbol"] for item in results["items"]] == ["AAPL", "MSFT", "ZZZ"]
    for row in results["items"]:
        assert {
            "id",
            "job_id",
            "sequence_index",
            "symbol",
            "status",
            "reason_code",
            "runtime_ms",
            "metrics",
            "total_return_pct",
            "max_drawdown_pct",
            "win_rate_pct",
            "trades_count",
            "single_run_id",
        } <= set(row)
        assert "execution_trace" not in row
        assert "equity_curve" not in row
        assert "trades" not in row
    assert results["items"][0]["metrics"]["local_data_preflight"]["state"] == "ready"
    assert results["items"][2]["status"] == "skipped"
    assert results["items"][2]["reason_code"] == "blocked_missing_local_data"

    _assert_no_sensitive_public_payload(diagnostics)
    _assert_no_sensitive_public_payload(results)
    _assert_no_live_provider_authority(diagnostics)
    _assert_no_live_provider_authority(results)


def test_all_backtest_golden_fixtures_are_sanitized_and_explicitly_enumerated() -> None:
    fixture_paths = sorted(FIXTURE_DIR.glob("*.json"))

    assert {path.name for path in fixture_paths} == {
        "rule_backtest_compute_basic_long_cash.json",
        "rule_backtest_pit_adjusted_data_readiness_v1.json",
        "rule_backtest_compute_shadow_cli_v1.json",
        "rule_backtest_compute_shadow_cli_v2.json",
        "rule_backtest_compute_shadow_cli_v3_terminal_forced_close.json",
        "rule_backtest_compute_shadow_cli_v4_ma_crossover.json",
        "rule_backtest_compare_dto.json",
        "rule_backtest_compare_heatmap_dto.json",
        "rule_backtest_data_provenance_projection_v1.json",
        "rule_backtest_execution_model_v1_metadata.json",
        "rule_backtest_execution_trace_dto.json",
        "rule_backtest_export_index_dto.json",
        "rule_backtest_robustness_evidence_dto.json",
        "rule_backtest_result_summary_dto.json",
        "rule_backtest_semantics_freeze_v1.json",
        "rule_backtest_support_bundle_manifest_dto.json",
        "rule_backtest_universe_job_diagnostics_dto.json",
        "rule_backtest_universe_results_dto.json",
    }
    for path in fixture_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        _assert_no_sensitive_public_payload(payload)
        _assert_no_live_provider_authority(payload)
