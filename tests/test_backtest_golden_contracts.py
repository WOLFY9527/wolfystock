# -*- coding: utf-8 -*-
"""Golden fixture contract tests for public backtest DTO boundaries."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from api.v1.schemas.backtest import RuleBacktestRunResponse
from src.services.rule_backtest_support_exports import build_execution_trace_export_csv_text


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
    parser_defaults = payload["parser_default_template_behavior"]
    assert parser_defaults["strategy_text"] == "5日均线上穿20日均线买入"
    assert parser_defaults["expected_parse"] == {
        "version": "v1",
        "strategy_kind": "moving_average_crossover",
        "normalized_text": "MA5 上穿 MA20 买入，MA5 下穿 MA20 卖出。",
        "needs_confirmation": True,
        "max_lookback": 20,
        "ambiguity_codes": [
            "default_fast_ma_type",
            "default_slow_ma_type",
            "default_reverse_exit",
        ],
        "summary": {
            "entry": "买入条件：MA5 上穿 MA20",
            "exit": "卖出条件：MA5 下穿 MA20",
            "strategy": "均线交叉策略",
        },
        "setup": {
            "indicator_family": "moving_average",
            "fast_period": 5,
            "slow_period": 20,
            "fast_type": "simple",
            "slow_type": "simple",
        },
        "strategy_spec": {},
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


def test_execution_trace_csv_export_escapes_spreadsheet_formula_prefixes() -> None:
    run = _load_fixture("rule_backtest_result_summary_dto.json")
    execution_trace = run["execution_trace"]
    execution_trace["rows"] = [
        {
            "date": "=1+1",
            "symbol_close": -12.5,
            "signal_summary": "+1+1",
            "action_display": "-1+1",
            "cash": -250,
            "daily_pnl": -35.5,
            "notes": "@SUM(1,1)",
            "assumptions_defaults": "  =1+1",
            "fallback": "\x7f@SUM(1,1)",
        },
        {
            "date": "2025-01-09",
            "symbol_close": 102,
            "signal_summary": "profit +1+1 later",
            "action": "hold",
            "cash": 100000,
            "daily_pnl": 0,
            "notes": '腾讯控股, quote "and"\nmultiline',
            "assumptions_defaults": "\r-1+1",
            "fallback": "\t+1+1",
        },
    ]
    trace_columns = [
        ("date", "date"),
        ("symbol_close", "symbol_close"),
        ("signal_summary", "signal"),
        ("action_display", "action"),
        ("cash", "cash"),
        ("daily_pnl", "daily_pnl"),
        ("notes", "notes"),
        ("assumptions_defaults", "assumptions"),
        ("fallback", "fallback"),
    ]

    trace_csv = build_execution_trace_export_csv_text(
        run,
        trace_columns,
        action_formatter=lambda action: action,
    )
    rows = list(csv.DictReader(io.StringIO(trace_csv)))

    assert rows[0]["date"] == "'=1+1"
    assert rows[0]["symbol_close"] == "-12.5"
    assert rows[0]["signal"] == "'+1+1"
    assert rows[0]["action"] == "'-1+1"
    assert rows[0]["cash"] == "-250"
    assert rows[0]["daily_pnl"] == "-35.5"
    assert rows[0]["notes"] == "'@SUM(1,1)"
    assert rows[0]["assumptions"] == "'=1+1"
    assert rows[0]["fallback"] == "'\x7f@SUM(1,1)"
    assert rows[1]["signal"] == "profit +1+1 later"
    assert rows[1]["notes"] == '腾讯控股, quote "and"\nmultiline'
    assert rows[1]["assumptions"] == "'-1+1"
    assert rows[1]["fallback"] == "'+1+1"
