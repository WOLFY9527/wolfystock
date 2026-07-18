# -*- coding: utf-8 -*-
"""Execution-truth contracts for the canonical rule-backtest models."""

from __future__ import annotations

import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from src.core.rule_backtest_engine import (
    ExecutionModelConfig,
    RuleBacktestEngine,
    RuleBacktestParser,
)
from src.services.rule_backtest_execution_model_registry import (
    CURRENT_RULE_BACKTEST_EXECUTION_MODEL_ID,
    PERIODIC_RULE_BACKTEST_EXECUTION_MODEL_ID,
    RuleBacktestExecutionModelUnsupportedError,
    build_rule_backtest_execution_model_registry_metadata,
    resolve_rule_backtest_execution_model_request,
)


def _bars(
    closes: list[float],
    *,
    opens: list[float | None] | None = None,
    start: date = date(2024, 1, 1),
) -> list[SimpleNamespace]:
    resolved_opens = opens if opens is not None else list(closes)
    return [
        SimpleNamespace(
            code="SAFE",
            date=start + timedelta(days=index),
            open=resolved_opens[index],
            high=max(float(resolved_opens[index] or close), close) + 0.2,
            low=min(float(resolved_opens[index] or close), close) - 0.2,
            close=close,
            volume=1000.0 + index,
        )
        for index, close in enumerate(closes)
    ]


def _run_rule_strategy(
    *,
    opens: list[float | None],
    closes: list[float],
    fee_bps: float = 0.0,
    slippage_bps: float = 0.0,
    fee_bps_configured: bool = False,
    slippage_bps_configured: bool = False,
):
    return RuleBacktestEngine().run(
        code="SAFE",
        parsed_strategy=RuleBacktestParser().parse(
            "Buy when Close > MA3. Sell when Close < MA3."
        ),
        bars=_bars(closes, opens=opens),
        initial_capital=100000.0,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        fee_bps_configured=fee_bps_configured,
        slippage_bps_configured=slippage_bps_configured,
        lookback_bars=len(closes),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, len(closes)),
    ).to_dict()


def test_registry_inventory_maps_every_executable_model_to_one_engine_identity() -> None:
    registry = build_rule_backtest_execution_model_registry_metadata()
    executable_ids = {
        model_id
        for model_id, model in registry["models"].items()
        if model["executable"]
    }

    assert executable_ids == {
        CURRENT_RULE_BACKTEST_EXECUTION_MODEL_ID,
        PERIODIC_RULE_BACKTEST_EXECUTION_MODEL_ID,
    }

    engine = RuleBacktestEngine()
    selected_ids = {
        engine._build_execution_model(
            timeframe="daily",
            fee_bps=0.0,
            slippage_bps=0.0,
            strategy_type=strategy_type,
        ).model_id
        for strategy_type in ("rule_conditions", "periodic_accumulation")
    }
    assert selected_ids == executable_ids
    assert ExecutionModelConfig.from_dict({"version": "v1"}) is None
    for unsupported_timeframe in ("", "weekly"):
        with pytest.raises(RuleBacktestExecutionModelUnsupportedError):
            engine._build_execution_model(
                timeframe=unsupported_timeframe,
                fee_bps=0.0,
                slippage_bps=0.0,
                strategy_type="rule_conditions",
            )
    with pytest.raises(RuleBacktestExecutionModelUnsupportedError):
        resolve_rule_backtest_execution_model_request(
            None,
            fee_bps=1.0,
            fee_bps_configured=False,
        )


def test_registry_rejects_partial_fill_and_other_unsupported_assumptions() -> None:
    unsupported_requests = (
        {"version": "v1", "partial_fills": True},
        {"version": "v1", "entry_timing": "same_bar_close"},
        {"version": "v1", "slippage_model": "volume_participation"},
    )

    for request in unsupported_requests:
        with pytest.raises(RuleBacktestExecutionModelUnsupportedError) as exc_info:
            resolve_rule_backtest_execution_model_request(request)
        assert exc_info.value.to_error_detail()["unsupported_fields"] == sorted(
            set(request) - {"version", "model_id"}
        )

    embedded_conflicts = (
        ({"execution": {"signal_timing": "same_bar_close"}}, "strategy_spec.execution.signal_timing"),
        ({"execution": {"partial_fills": True}}, "strategy_spec.execution.partial_fills"),
        ({"end_behavior": {"policy": "hold_at_end"}}, "strategy_spec.end_behavior.policy"),
        ({"costs": {"fee_bps": 1.0}}, "strategy_spec.costs.fee_bps"),
        (
            {
                "strategy_type": "periodic_accumulation",
                "entry": {"price_basis": "close"},
            },
            "strategy_spec.entry.price_basis",
        ),
    )
    for strategy_spec, expected_field in embedded_conflicts:
        parsed = RuleBacktestParser().parse(
            "Buy when Close > MA3. Sell when Close < MA3."
        )
        parsed.strategy_spec = strategy_spec
        with pytest.raises(RuleBacktestExecutionModelUnsupportedError) as exc_info:
            RuleBacktestEngine().run(
                code="SAFE",
                parsed_strategy=parsed,
                bars=_bars([10.0, 10.0, 10.0, 11.0]),
                lookback_bars=4,
            )
        assert exc_info.value.to_error_detail()["unsupported_fields"] == [expected_field]


def test_missing_next_open_records_unfilled_without_price_or_cost() -> None:
    result = _run_rule_strategy(
        opens=[10.0, 10.0, 10.0, 10.2, None],
        closes=[10.0, 10.0, 10.0, 11.0, 12.0],
        fee_bps=2.5,
        slippage_bps=1.25,
        fee_bps_configured=True,
        slippage_bps_configured=True,
    )

    unfilled_events = [
        event
        for point in result["equity_curve"]
        for event in point["execution_events"]
        if event["state"] == "unfilled"
    ]
    assert unfilled_events == [
        {
            "event_type": "strategy_entry_order",
            "state": "unfilled",
            "side": "entry",
            "signal_date": "2024-01-04",
            "execution_date": "2024-01-05",
            "fill_date": None,
            "timing": "next_bar_open",
            "price_basis": "open",
            "fill_basis": None,
            "fill_price": None,
            "fee_amount": 0.0,
            "slippage_amount": 0.0,
            "reason": "required_open_unavailable",
        }
    ]
    assert result["trades"] == []
    assert "close_fallback" not in json.dumps(result, sort_keys=True)


def test_terminal_liquidation_is_not_recorded_as_an_ordinary_strategy_signal() -> None:
    result = _run_rule_strategy(
        opens=[10.0, 10.0, 10.0, 10.0, 10.1, 10.3, 11.2, 12.2],
        closes=[10.0, 10.0, 10.0, 10.0, 10.2, 11.0, 12.0, 13.0],
        fee_bps=2.5,
        slippage_bps=1.25,
        fee_bps_configured=True,
        slippage_bps_configured=True,
    )

    trade = result["trades"][-1]
    terminal_event = result["equity_curve"][-1]["execution_events"][-1]
    assert trade["exit_signal_date"] is None
    assert trade["exit_event_type"] == "terminal_liquidation"
    assert trade["exit_reason"] == "terminal_liquidation"
    assert trade["terminal_liquidation_policy_id"] == "window_end_close_liquidation_v1"
    assert terminal_event["event_type"] == "terminal_liquidation"
    assert terminal_event["state"] == "filled"
    assert terminal_event["signal_date"] is None
    assert terminal_event["fill_basis"] == "close"
    assert terminal_event["reason"] == "window_end_policy"


def test_valid_fill_costs_are_applied_exactly_once_with_explicit_configuration() -> None:
    result = _run_rule_strategy(
        opens=[10.0, 10.1, 9.9, 10.2, 11.2, 11.8, 8.7, 8.1],
        closes=[10.0, 10.0, 10.0, 11.0, 12.0, 9.0, 8.0, 10.0],
        fee_bps=2.5,
        slippage_bps=1.25,
        fee_bps_configured=True,
        slippage_bps_configured=True,
    )

    trade = result["trades"][0]
    quantity = trade["quantity"]
    assert trade["entry_fee_amount"] == pytest.approx(
        quantity * 11.2 * (1.0 + (1.25 / 10000.0)) * (2.5 / 10000.0),
        abs=3e-6,
    )
    assert trade["exit_fee_amount"] == pytest.approx(
        quantity * 8.7 * (1.0 - (1.25 / 10000.0)) * (2.5 / 10000.0),
        abs=3e-6,
    )
    assert trade["entry_slippage_amount"] == pytest.approx(
        quantity * 11.2 * (1.25 / 10000.0),
        abs=3e-6,
    )
    assert trade["exit_slippage_amount"] == pytest.approx(
        quantity * 8.7 * (1.25 / 10000.0),
        abs=3e-6,
    )
    assert trade["fees"] == pytest.approx(
        trade["entry_fee_amount"] + trade["exit_fee_amount"], abs=1e-6
    )
    assert trade["slippage"] == pytest.approx(
        trade["entry_slippage_amount"] + trade["exit_slippage_amount"], abs=1e-6
    )
    assert trade["gross_pnl"] - trade["net_pnl"] == pytest.approx(
        trade["fees"] + trade["slippage"], abs=1e-6
    )
    assert result["execution_model"]["cost_configuration"]["fee"]["state"] == "explicit_non_zero"
    assert result["execution_model"]["cost_configuration"]["slippage"]["state"] == "explicit_non_zero"


def test_bar_close_strategy_signals_never_fill_on_their_signal_bar() -> None:
    result = _run_rule_strategy(
        opens=[10.0, 10.1, 9.9, 10.2, 11.2, 11.8, 8.7, 8.1],
        closes=[10.0, 10.0, 10.0, 11.0, 12.0, 9.0, 8.0, 10.0],
    )

    strategy_fills = [
        event
        for point in result["equity_curve"]
        for event in point["execution_events"]
        if event["event_type"].startswith("strategy_") and event["state"] == "filled"
    ]
    assert strategy_fills
    assert all(event["signal_date"] < event["fill_date"] for event in strategy_fills)


def test_omitted_and_explicit_zero_costs_remain_distinct_in_result_evidence() -> None:
    inputs = {
        "opens": [10.0, 10.1, 9.9, 10.2, 11.2, 11.8, 8.7, 8.1],
        "closes": [10.0, 10.0, 10.0, 11.0, 12.0, 9.0, 8.0, 10.0],
    }
    omitted = _run_rule_strategy(**inputs)
    explicit_zero = _run_rule_strategy(
        **inputs,
        fee_bps_configured=True,
        slippage_bps_configured=True,
    )

    assert omitted["execution_model"]["cost_configuration"] == {
        "fee": {
            "state": "unspecified",
            "bps_per_side": 0.0,
            "omitted_policy": "no_cost_applied",
            "application": "filled_side_exactly_once",
        },
        "slippage": {
            "state": "unspecified",
            "bps_per_side": 0.0,
            "omitted_policy": "no_cost_applied",
            "application": "filled_side_exactly_once",
        },
    }
    assert explicit_zero["execution_model"]["cost_configuration"]["fee"]["state"] == "explicit_zero"
    assert explicit_zero["execution_model"]["cost_configuration"]["slippage"]["state"] == "explicit_zero"
    assert omitted["metrics"] == explicit_zero["metrics"]


def test_periodic_execution_uses_registered_identity_and_explicit_terminal_policy() -> None:
    from src.services.rule_backtest_service import RuleBacktestService

    service = RuleBacktestService(None)
    parsed_payload = service.parse_strategy(
        "资金1000，从2024-01-01到2024-01-03，每天买300元SAFE，买到区间结束",
        code="SAFE",
        start_date="2024-01-01",
        end_date="2024-01-03",
        initial_capital=1000.0,
    )
    parsed = service._dict_to_parsed_strategy(parsed_payload, parsed_payload["source_text"])
    result = RuleBacktestEngine().run(
        code="SAFE",
        parsed_strategy=parsed,
        bars=_bars([10.0, 10.1, 10.2]),
        initial_capital=1000.0,
        fee_bps=0.0,
        slippage_bps=0.0,
        fee_bps_configured=True,
        slippage_bps_configured=True,
        lookback_bars=3,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 3),
    ).to_dict()

    assert result["execution_model"]["model_id"] == PERIODIC_RULE_BACKTEST_EXECUTION_MODEL_ID
    assert result["execution_model"]["signal_evaluation_timing"] == "scheduled_before_session_open"
    assert result["execution_model"]["entry_timing"] == "same_session_open"
    assert result["trades"][-1]["exit_event_type"] == "terminal_liquidation"
    assert result["trades"][-1]["exit_signal_date"] is None


def test_periodic_insufficient_cash_preserves_rejected_orders_without_costs() -> None:
    from src.services.rule_backtest_service import RuleBacktestService

    service = RuleBacktestService(None)
    parsed_payload = service.parse_strategy(
        "资金1000，从2024-01-01到2024-01-03，每天买600元SAFE，买到区间结束",
        code="SAFE",
        start_date="2024-01-01",
        end_date="2024-01-03",
        initial_capital=1000.0,
        fee_bps=2.5,
        slippage_bps=1.25,
    )
    parsed = service._dict_to_parsed_strategy(parsed_payload, parsed_payload["source_text"])
    result = RuleBacktestEngine().run(
        code="SAFE",
        parsed_strategy=parsed,
        bars=_bars([10.0, 10.1, 10.2]),
        initial_capital=1000.0,
        fee_bps=2.5,
        slippage_bps=1.25,
        fee_bps_configured=True,
        slippage_bps_configured=True,
        lookback_bars=3,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 3),
    ).to_dict()

    rejected_events = [
        event
        for point in result["equity_curve"]
        for event in point["execution_events"]
        if event["state"] == "rejected"
    ]
    assert rejected_events
    assert all(event["reason"] == "insufficient_cash" for event in rejected_events)
    assert all(event["execution_date"] == event["signal_date"] for event in rejected_events)
    assert all(event["fill_date"] is None for event in rejected_events)
    assert all(event["fill_price"] is None for event in rejected_events)
    assert all(event["fee_amount"] == 0.0 for event in rejected_events)
    assert all(event["slippage_amount"] == 0.0 for event in rejected_events)


def test_repeated_runs_preserve_identical_model_identity_and_execution_evidence() -> None:
    inputs = {
        "opens": [10.0, 10.1, 9.9, 10.2, 11.2, 11.8, 8.7, 8.1],
        "closes": [10.0, 10.0, 10.0, 11.0, 12.0, 9.0, 8.0, 10.0],
        "fee_bps": 2.5,
        "slippage_bps": 1.25,
        "fee_bps_configured": True,
        "slippage_bps_configured": True,
    }

    first = _run_rule_strategy(**inputs)
    second = _run_rule_strategy(**inputs)

    assert first == second
    assert first["execution_model"]["model_id"] == CURRENT_RULE_BACKTEST_EXECUTION_MODEL_ID
