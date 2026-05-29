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


def test_rule_backtest_shadow_cli_fixture_matches_python_engine_without_parser() -> None:
    fixture_name = "rule_backtest_compute_shadow_cli_v1.json"
    fixture_text = _load_fixture_text(fixture_name)
    fixture = json.loads(fixture_text)

    assert fixture["contract_version"] == "shadow_cli_v1"
    assert fixture["case_id"] == "rule_conditions_close_vs_ma3_long_cash"
    assert "strategy_text" not in fixture_text
    assert "pyo3" not in fixture_text.lower()
    assert "maturin" not in fixture_text.lower()
    assert "cargo" not in fixture_text.lower()
    assert "rust runtime" not in fixture_text.lower()

    fixture_input = fixture["input"]
    expected_output = fixture["expected_output"]
    assert fixture_input["parsed_strategy"]["strategy_kind"] == "rule_conditions"
    assert fixture_input["parsed_strategy"]["entry"]["text"] == "Close > MA3"
    assert fixture_input["parsed_strategy"]["exit"]["text"] == "Close < MA3"
    assert fixture_input["parsed_strategy"]["max_lookback"] == 3
    assert fixture_input["parsed_strategy"]["strategy_spec"]["strategy_type"] == "rule_conditions"
    assert len(fixture_input["bars"]) == 8
    assert all(
        set(bar) == {"date", "open", "high", "low", "close", "volume"}
        for bar in fixture_input["bars"]
    )

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
    assert [point["date"] for point in actual_equity_points] == [
        "2024-01-04",
        "2024-01-05",
        "2024-01-06",
        "2024-01-07",
    ]
    for actual_point, expected_point in zip(actual_equity_points, expected_output["selected_equity_points"]):
        assert actual_point["date"] == expected_point["date"]
        assert actual_point["executed_action"] == expected_point["executed_action"]
        assert actual_point["signal_summary"] == expected_point["signal_summary"]
        assert actual_point["position_state"] == expected_point["position_state"]
        assert actual_point["notes"] == expected_point["notes"]
        _assert_close(actual_point["exposure_pct"], expected_point["exposure_pct"])
        _assert_close(actual_point["total_portfolio_value"], expected_point["total_portfolio_value"])

    assert len(result["trades"]) == len(expected_output["trades"]) == 1
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
