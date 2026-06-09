# -*- coding: utf-8 -*-
"""Golden fixture tests for the Python-authoritative rule backtest compute boundary."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from src.core.rule_backtest_engine import ParsedStrategy, RuleBacktestEngine, RuleBacktestParser


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "backtest"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _load_fixture_text(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _make_bars(closes: list[float], *, start: date, opens: list[float]) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            code="SAFE",
            date=start + timedelta(days=index),
            open=float(opens[index]),
            high=float(max(opens[index], close) + 0.2),
            low=float(min(opens[index], close) - 0.2),
            close=float(close),
            volume=1000.0 + index,
        )
        for index, close in enumerate(closes)
    ]


def _make_explicit_bars(bars: list[dict]) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            code="SAFE",
            date=date.fromisoformat(bar["date"]),
            open=float(bar["open"]),
            high=float(bar["high"]),
            low=float(bar["low"]),
            close=float(bar["close"]),
            volume=float(bar["volume"]),
        )
        for bar in bars
    ]


def _parsed_strategy_from_fixture(payload: dict) -> ParsedStrategy:
    return ParsedStrategy(
        version=str(payload["version"]),
        timeframe=str(payload["timeframe"]),
        source_text=str(payload.get("source_text") or ""),
        normalized_text=str(payload.get("normalized_text") or ""),
        entry=dict(payload["entry"]),
        exit=dict(payload["exit"]),
        confidence=float(payload.get("confidence", 1.0)),
        needs_confirmation=bool(payload.get("needs_confirmation", False)),
        ambiguities=list(payload.get("ambiguities", [])),
        summary=dict(payload.get("summary", {})),
        max_lookback=int(payload["max_lookback"]),
        strategy_kind=str(payload["strategy_kind"]),
        setup=dict(payload.get("setup", {})),
        strategy_spec=dict(payload.get("strategy_spec", {})),
        executable=bool(payload.get("executable", False)),
        normalization_state=str(payload.get("normalization_state", "normalized_contract")),
        assumptions=list(payload.get("assumptions", [])),
        assumption_groups=list(payload.get("assumption_groups", [])),
        unsupported_reason=payload.get("unsupported_reason"),
        unsupported_details=list(payload.get("unsupported_details", [])),
        unsupported_extensions=list(payload.get("unsupported_extensions", [])),
        detected_strategy_family=payload.get("detected_strategy_family"),
        core_intent_summary=payload.get("core_intent_summary"),
        interpretation_confidence=float(payload.get("interpretation_confidence", payload.get("confidence", 1.0))),
        supported_portion_summary=payload.get("supported_portion_summary"),
        rewrite_suggestions=list(payload.get("rewrite_suggestions", [])),
        parse_warnings=list(payload.get("parse_warnings", [])),
    )


def _assert_close(actual: float, expected: float, *, tolerance: float = 1e-4) -> None:
    assert abs(actual - expected) <= tolerance, (actual, expected)


def test_rule_backtest_compute_basic_long_cash_golden_fixture_matches_python_engine() -> None:
    fixture = _load_fixture("rule_backtest_compute_basic_long_cash.json")
    parser = RuleBacktestParser()
    parsed = parser.parse(fixture["strategy_text"])
    engine = RuleBacktestEngine()

    bars = _make_bars(
        fixture["inputs"]["bars"]["close"],
        start=date.fromisoformat(fixture["inputs"]["bars"]["start_date"]),
        opens=fixture["inputs"]["bars"]["open"],
    )
    result = engine.run(
        code=fixture["inputs"]["code"],
        parsed_strategy=parsed,
        bars=bars,
        initial_capital=fixture["inputs"]["initial_capital"],
        fee_bps=fixture["inputs"]["execution"]["fee_bps"],
        slippage_bps=fixture["inputs"]["execution"]["slippage_bps"],
        lookback_bars=fixture["inputs"]["lookback_bars"],
        start_date=date.fromisoformat(fixture["inputs"]["date_window"]["start_date"]),
        end_date=date.fromisoformat(fixture["inputs"]["date_window"]["end_date"]),
    ).to_dict()

    expected = fixture["expected"]
    assert result["execution_model"]["entry_timing"] == "next_bar_open"
    assert result["execution_model"]["exit_timing"] == "next_bar_open"
    assert result["execution_model"]["fee_bps_per_side"] == fixture["inputs"]["execution"]["fee_bps"]
    assert result["execution_model"]["slippage_bps_per_side"] == fixture["inputs"]["execution"]["slippage_bps"]
    assert result["execution_assumptions"]["entry_fill_timing"] == "next_bar_open"
    assert result["execution_assumptions"]["exit_fill_timing"] == "next_bar_open; same_bar_close"

    for key, value in expected["metrics"].items():
        actual = result["metrics"][key]
        if isinstance(value, float):
            _assert_close(actual, value)
        else:
            assert actual == value

    selected_dates = {point["date"] for point in expected["selected_equity_points"]}
    actual_points = [
        {
            "date": point["date"],
            "action": point.get("executed_action"),
            "signal_summary": point.get("signal_summary"),
            "position": point["exposure_pct"],
            "total_portfolio_value": point["total_portfolio_value"],
        }
        for point in result["equity_curve"]
        if point["date"] in selected_dates
    ]
    assert actual_points == expected["selected_equity_points"]

    actual_trades = [
        {
            "entry_signal_date": trade["entry_signal_date"],
            "entry_date": trade["entry_date"],
            "exit_signal_date": trade["exit_signal_date"],
            "exit_date": trade["exit_date"],
            "entry_price": trade["entry_price"],
            "exit_price": trade["exit_price"],
            "return_pct": trade["return_pct"],
            "quantity": trade["quantity"],
            "fees": trade["fees"],
            "slippage": trade["slippage"],
            "entry_reason": trade["entry_reason"],
            "exit_reason": trade["exit_reason"],
            "signal_reason": trade["signal_reason"],
            "notes": trade["notes"],
        }
        for trade in result["trades"]
    ]
    assert actual_trades == expected["trades"]


def test_rule_backtest_semantics_freeze_fixture_matches_current_v1_engine() -> None:
    fixture = _load_fixture("rule_backtest_semantics_freeze_v1.json")
    template = fixture["deterministic_template_behavior"]
    parser = RuleBacktestParser()
    parsed = parser.parse(template["strategy_text"])

    expected_parse = template["expected_parse"]
    assert parsed.strategy_kind == expected_parse["strategy_kind"]
    assert parsed.entry["text"] == expected_parse["entry_text"]
    assert parsed.exit["text"] == expected_parse["exit_text"]
    assert parsed.max_lookback == expected_parse["max_lookback"]
    assert parsed.strategy_spec == expected_parse["strategy_spec"]

    cost_freeze = fixture["cost_slippage_current_treatment"]
    cost_source = _load_fixture(cost_freeze["source_fixture"])
    cost_bars = _make_bars(
        cost_source["inputs"]["bars"]["close"],
        start=date.fromisoformat(cost_source["inputs"]["bars"]["start_date"]),
        opens=cost_source["inputs"]["bars"]["open"],
    )
    cost_result = RuleBacktestEngine().run(
        code=cost_source["inputs"]["code"],
        parsed_strategy=parsed,
        bars=cost_bars,
        initial_capital=cost_source["inputs"]["initial_capital"],
        fee_bps=cost_freeze["fee_bps_per_side"],
        slippage_bps=cost_freeze["slippage_bps_per_side"],
        lookback_bars=cost_source["inputs"]["lookback_bars"],
        start_date=date.fromisoformat(cost_source["inputs"]["date_window"]["start_date"]),
        end_date=date.fromisoformat(cost_source["inputs"]["date_window"]["end_date"]),
    ).to_dict()
    expected_execution_model = {
        **template["expected_execution_model"],
        "fee_bps_per_side": cost_freeze["fee_bps_per_side"],
        "slippage_bps_per_side": cost_freeze["slippage_bps_per_side"],
    }
    assert cost_result["execution_model"] == expected_execution_model
    assert cost_result["execution_assumptions"]["fee_model"] == cost_freeze["model"]
    assert cost_result["execution_assumptions"]["slippage_model"] == cost_freeze["model"]
    for key in ("final_equity", "total_return_pct", "trade_count"):
        actual = cost_result["metrics"][key]
        expected = cost_freeze["expected"][key]
        if isinstance(expected, float):
            _assert_close(actual, expected)
        else:
            assert actual == expected
    assert len(cost_result["trades"]) == 1
    cost_trade = cost_result["trades"][0]
    for key in ("entry_price", "exit_price", "quantity", "fees", "slippage"):
        _assert_close(cost_trade[key], cost_freeze["expected"][key])
    for key in ("notes",):
        assert cost_trade[key] == cost_freeze["expected"][key]

    for case in fixture["sample_window_behavior"]["cases"]:
        case_inputs = case["inputs"]
        window_bars = _make_bars(
            case_inputs["bars"]["close"],
            start=date.fromisoformat(case_inputs["bars"]["start_date"]),
            opens=case_inputs["bars"]["open"],
        )
        date_window = case_inputs["date_window"]
        result = RuleBacktestEngine().run(
            code="SAFE",
            parsed_strategy=parsed,
            bars=window_bars,
            initial_capital=case_inputs["initial_capital"],
            fee_bps=case_inputs["fee_bps"],
            slippage_bps=case_inputs["slippage_bps"],
            lookback_bars=case_inputs["lookback_bars"],
            start_date=date.fromisoformat(date_window["start_date"]) if date_window["start_date"] else None,
            end_date=date.fromisoformat(date_window["end_date"]) if date_window["end_date"] else None,
        ).to_dict()

        expected = case["expected"]
        for key, expected_value in expected["metrics"].items():
            actual_value = result["metrics"][key]
            if isinstance(expected_value, float):
                _assert_close(actual_value, expected_value)
            else:
                assert actual_value == expected_value

        assert [
            {
                "date": point["date"],
                "executed_action": point["executed_action"],
                "signal_summary": point["signal_summary"],
                "position_state": point["position_state"],
                "exposure_pct": point["exposure_pct"],
                "total_portfolio_value": point["total_portfolio_value"],
                "notes": point["notes"],
            }
            for point in result["equity_curve"]
        ] == expected["selected_equity_points"]
        assert [
            {
                "entry_signal_date": trade["entry_signal_date"],
                "entry_date": trade["entry_date"],
                "exit_signal_date": trade["exit_signal_date"],
                "exit_date": trade["exit_date"],
                "entry_price": trade["entry_price"],
                "exit_price": trade["exit_price"],
                "return_pct": trade["return_pct"],
                "quantity": trade["quantity"],
                "fees": trade["fees"],
                "slippage": trade["slippage"],
                "entry_reason": trade["entry_reason"],
                "exit_reason": trade["exit_reason"],
                "signal_reason": trade["signal_reason"],
                "notes": trade["notes"],
            }
            for trade in result["trades"]
        ] == expected["trades"]

        serialized_result = json.dumps(result, ensure_ascii=False, sort_keys=True).lower()
        for marker in fixture["no_order_no_broker_boundary"]["forbidden_output_markers"]:
            assert marker.lower() not in serialized_result


def test_rule_backtest_shadow_cli_fixtures_match_python_engine_without_parser() -> None:
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
            "selected_dates": ["2024-01-04", "2024-01-05", "2024-01-06", "2024-01-07"],
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
            "selected_dates": ["2024-01-04", "2024-01-05", "2024-01-06", "2024-01-07"],
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
            "selected_dates": ["2024-01-05", "2024-01-06", "2024-01-07", "2024-01-08"],
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
            "selected_dates": ["2024-01-06", "2024-01-07", "2024-01-09", "2024-01-10"],
        },
    }

    for fixture_name, expected_case in expected_cases.items():
        fixture_text = _load_fixture_text(fixture_name)
        fixture = json.loads(fixture_text)

        assert fixture["contract_version"] == expected_case["contract_version"]
        assert fixture["case_id"] == expected_case["case_id"]
        assert "strategy_text" not in fixture_text
        assert "pyo3" not in fixture_text.lower()
        assert "maturin" not in fixture_text.lower()
        assert "cargo" not in fixture_text.lower()
        assert "rust runtime" not in fixture_text.lower()

        fixture_input = fixture["input"]
        expected_output = fixture["expected_output"]
        assert fixture_input["date_window"] == expected_case["date_window"]
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

        engine = RuleBacktestEngine()
        result = engine.run(
            code=fixture_input["code"],
            parsed_strategy=_parsed_strategy_from_fixture(fixture_input["parsed_strategy"]),
            bars=_make_explicit_bars(fixture_input["bars"]),
            initial_capital=fixture_input["initial_capital"],
            fee_bps=fixture_input["execution_model"]["fee_bps_per_side"],
            slippage_bps=fixture_input["execution_model"]["slippage_bps_per_side"],
            lookback_bars=fixture_input["lookback_bars"],
            start_date=date.fromisoformat(fixture_input["date_window"]["start_date"]),
            end_date=date.fromisoformat(fixture_input["date_window"]["end_date"]),
        ).to_dict()

        assert result["execution_model"] == fixture_input["execution_model"] == expected_output["execution_model"]
        assert result["execution_assumptions"] == expected_output["execution_assumptions"]

        for key, expected_value in expected_output["metrics"].items():
            actual_value = result["metrics"][key]
            if isinstance(expected_value, float):
                _assert_close(actual_value, expected_value)
            else:
                assert actual_value == expected_value
        assert result["metrics"]["trade_count"] == expected_case["trade_count"]

        actual_equity_points = [
            {
                "date": point["date"],
                "executed_action": point["executed_action"],
                "signal_summary": point["signal_summary"],
                "position_state": point["position_state"],
                "exposure_pct": point["exposure_pct"],
                "notes": point["notes"],
                "total_portfolio_value": point["total_portfolio_value"],
            }
            for point in result["equity_curve"]
            if point["date"] in {item["date"] for item in expected_output["selected_equity_points"]}
        ]
        assert [point["date"] for point in actual_equity_points] == expected_case["selected_dates"]
        for actual_point, expected_point in zip(actual_equity_points, expected_output["selected_equity_points"]):
            assert actual_point["date"] == expected_point["date"]
            assert actual_point["executed_action"] == expected_point["executed_action"]
            assert actual_point["signal_summary"] == expected_point["signal_summary"]
            assert actual_point["position_state"] == expected_point["position_state"]
            assert actual_point["notes"] == expected_point["notes"]
            _assert_close(actual_point["exposure_pct"], expected_point["exposure_pct"])
            _assert_close(actual_point["total_portfolio_value"], expected_point["total_portfolio_value"])

        assert len(result["trades"]) == len(expected_output["trades"]) == expected_case["trade_count"]
        for actual_trade, expected_trade in zip(result["trades"], expected_output["trades"]):
            assert actual_trade["entry_signal_date"] == expected_trade["entry_signal_date"]
            assert actual_trade["entry_date"] == expected_trade["entry_date"]
            assert actual_trade["exit_signal_date"] == expected_trade["exit_signal_date"]
            assert actual_trade["exit_date"] == expected_trade["exit_date"]
            assert actual_trade["entry_reason"] == expected_trade["entry_reason"]
            assert actual_trade["exit_reason"] == expected_trade["exit_reason"]
            assert actual_trade["signal_reason"] == expected_trade["signal_reason"]
            assert actual_trade["notes"] == expected_trade["notes"]
            for float_key in ("entry_price", "exit_price", "return_pct", "quantity", "fees", "slippage"):
                _assert_close(actual_trade[float_key], expected_trade[float_key])

        if expected_case["case_id"] == "rule_conditions_close_vs_ma3_terminal_forced_close":
            terminal_point = result["equity_curve"][-1]
            assert terminal_point["date"] == "2024-01-08"
            assert terminal_point["executed_action"] == "forced_close"
            assert terminal_point["notes"] == "forced_close_at_window_end"
            assert terminal_point["position_state"] == "flat"
            assert result["trades"][-1]["exit_signal_date"] == "2024-01-08"
            assert result["trades"][-1]["exit_date"] == "2024-01-08"
            assert result["trades"][-1]["exit_reason"] == "final_close"
            assert result["trades"][-1]["notes"] == "forced_close_at_window_end"
