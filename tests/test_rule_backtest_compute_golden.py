# -*- coding: utf-8 -*-
"""Golden fixture tests for the Python-authoritative rule backtest compute boundary."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from src.core.rule_backtest_engine import RuleBacktestEngine, RuleBacktestParser


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "backtest"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


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
