# -*- coding: utf-8 -*-
"""Contracts for the additive backtest execution cost/capacity helper."""

from __future__ import annotations

from copy import deepcopy
from datetime import date

from src.services.backtest_execution_cost_capacity import (
    ExecutionCostCapacityConfig,
    evaluate_execution_cost_capacity,
)


def _config(**kwargs):
    return ExecutionCostCapacityConfig(**kwargs)


def _evaluate(trades, *, bars=None, config=None):
    return evaluate_execution_cost_capacity(trades, bars=bars, config=config)


def test_zero_cost_default_preserves_requested_fill_and_no_costs() -> None:
    result = _evaluate([
        {"trade_id": "t1", "symbol": "AAPL", "date": date(2024, 1, 2), "side": "buy", "quantity": 100, "price": 50.0},
    ])

    trade = result["trades"][0]
    assert trade["fill_status"] == "filled"
    assert trade["filled_quantity"] == 100.0
    assert trade["filled_notional"] == 5000.0
    assert trade["total_cost"] == 0.0
    assert result["summary"]["total_cost"] == 0.0
    assert result["assumptions"]["default_zero_cost_preserves_backtest_math"] is True


def test_fee_and_slippage_costs_are_calculated_on_filled_notional() -> None:
    result = _evaluate(
        [{"trade_id": "t1", "symbol": "AAPL", "date": "2024-01-02", "side": "buy", "quantity": 100, "price": 100.0}],
        config=_config(commission_bps=10.0, slippage_bps=5.0),
    )

    trade = result["trades"][0]
    assert trade["commission_cost"] == 10.0
    assert trade["slippage_cost"] == 5.0
    assert trade["spread_cost"] == 0.0
    assert trade["total_cost"] == 15.0
    assert trade["cash_effect_after_cost"] == -10015.0
    assert result["summary"]["commission_cost"] == 10.0
    assert result["summary"]["slippage_cost"] == 5.0


def test_spread_cost_is_calculated_as_explicit_one_way_bps_cost() -> None:
    result = _evaluate(
        [{"trade_id": "t1", "symbol": "AAPL", "date": "2024-01-02", "side": "sell", "quantity": 200, "price": 25.0}],
        config=_config(spread_bps=8.0),
    )

    trade = result["trades"][0]
    assert trade["filled_notional"] == 5000.0
    assert trade["spread_cost"] == 4.0
    assert trade["total_cost"] == 4.0
    assert trade["cash_effect_after_cost"] == 4996.0
    assert result["assumptions"]["spread_model"] == "one_way_bps_on_filled_notional"


def test_minimum_fee_applies_only_to_filled_trades() -> None:
    result = _evaluate(
        [
            {"trade_id": "small", "symbol": "AAPL", "date": "2024-01-02", "side": "buy", "quantity": 10, "price": 10.0},
            {"trade_id": "blocked", "symbol": "MSFT", "date": "2024-01-02", "side": "buy", "quantity": 10, "price": 10.0},
        ],
        bars=[
            {"symbol": "AAPL", "date": "2024-01-02", "volume": 1000},
            {"symbol": "MSFT", "date": "2024-01-02", "volume": 0},
        ],
        config=_config(commission_bps=1.0, minimum_fee=2.0, volume_participation_cap=0.1),
    )

    rows = {row["trade_id"]: row for row in result["trades"]}
    assert rows["small"]["commission_cost"] == 2.0
    assert rows["small"]["total_cost"] == 2.0
    assert rows["blocked"]["fill_status"] == "no_fill"
    assert rows["blocked"]["commission_cost"] == 0.0
    assert rows["blocked"]["total_cost"] == 0.0


def test_volume_participation_cap_creates_partial_fill_and_capacity_warning() -> None:
    result = _evaluate(
        [{"trade_id": "large", "symbol": "AAPL", "date": "2024-01-02", "side": "buy", "quantity": 1000, "price": 10.0}],
        bars=[{"symbol": "AAPL", "date": "2024-01-02", "volume": 2000}],
        config=_config(volume_participation_cap=0.2),
    )

    trade = result["trades"][0]
    assert trade["fill_status"] == "partial"
    assert trade["filled_quantity"] == 400.0
    assert trade["unfilled_quantity"] == 600.0
    assert trade["fill_reason"] == "volume_participation_cap"
    assert trade["capacity_warning_codes"] == ["volume_participation_cap"]
    assert result["summary"]["partial_fill_count"] == 1
    assert result["summary"]["capacity_warnings"][0]["code"] == "volume_participation_cap"


def test_max_notional_cap_limits_trade_size_without_mutating_requested_notional() -> None:
    result = _evaluate(
        [{"trade_id": "notional", "symbol": "AAPL", "date": "2024-01-02", "side": "buy", "quantity": 1000, "price": 10.0}],
        config=_config(max_notional_per_trade=3000.0),
    )

    trade = result["trades"][0]
    assert trade["requested_quantity"] == 1000.0
    assert trade["requested_notional"] == 10000.0
    assert trade["fill_status"] == "partial"
    assert trade["filled_quantity"] == 300.0
    assert trade["filled_notional"] == 3000.0
    assert trade["fill_reason"] == "max_notional_per_trade"


def test_missing_and_insufficient_volume_create_no_fills() -> None:
    result = _evaluate(
        [
            {"trade_id": "missing", "symbol": "AAPL", "date": "2024-01-02", "side": "buy", "quantity": 10, "price": 10.0},
            {"trade_id": "zero", "symbol": "MSFT", "date": "2024-01-02", "side": "buy", "quantity": 10, "price": 10.0},
        ],
        bars=[{"symbol": "MSFT", "date": "2024-01-02", "volume": 0}],
        config=_config(volume_participation_cap=0.1),
    )

    rows = {row["trade_id"]: row for row in result["trades"]}
    assert rows["missing"]["fill_status"] == "no_fill"
    assert rows["missing"]["fill_reason"] == "missing_volume"
    assert rows["zero"]["fill_status"] == "no_fill"
    assert rows["zero"]["fill_reason"] == "insufficient_volume"
    assert result["summary"]["no_fill_count"] == 2
    assert [warning["code"] for warning in result["summary"]["capacity_warnings"]] == [
        "insufficient_volume",
        "missing_volume",
    ]


def test_output_ordering_is_deterministic_by_date_symbol_and_input_sequence() -> None:
    result = _evaluate([
        {"trade_id": "late", "symbol": "MSFT", "date": "2024-01-03", "side": "buy", "quantity": 1, "price": 10.0},
        {"trade_id": "early-b", "symbol": "MSFT", "date": "2024-01-02", "side": "buy", "quantity": 1, "price": 10.0},
        {"trade_id": "early-a", "symbol": "AAPL", "date": "2024-01-02", "side": "buy", "quantity": 1, "price": 10.0},
    ])

    assert [row["trade_id"] for row in result["trades"]] == ["early-a", "early-b", "late"]
    assert [row["input_sequence"] for row in result["trades"]] == [2, 1, 0]


def test_trade_and_bar_inputs_are_not_mutated() -> None:
    trades = [
        {"trade_id": "t1", "symbol": "AAPL", "date": "2024-01-02", "side": "buy", "quantity": 1000, "price": 10.0},
    ]
    bars = [{"symbol": "AAPL", "date": "2024-01-02", "volume": 2000}]
    original_trades = deepcopy(trades)
    original_bars = deepcopy(bars)

    _evaluate(trades, bars=bars, config=_config(volume_participation_cap=0.1, commission_bps=5.0))

    assert trades == original_trades
    assert bars == original_bars
