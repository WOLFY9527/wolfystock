# -*- coding: utf-8 -*-
"""Fixture-only contract for current backtest execution-realism readiness."""

from __future__ import annotations

from copy import deepcopy

from src.services.backtest_professional_readiness import (
    build_backtest_professional_readiness,
)


def test_execution_realism_readiness_stays_research_only_with_bps_assumptions() -> None:
    data_quality = {
        "authority_status": "allowed",
        "authority_reason_codes": [],
        "adjustment_mode": "unknown",
        "return_basis": "unknown",
        "dividends_handled": "unknown",
        "splits_handled": "unknown",
    }
    execution_assumptions = {
        "entry_fill_timing": "next_bar_open",
        "exit_fill_timing": "next_bar_open; same_bar_close",
        "fee_bps_per_side": 1.0,
        "slippage_bps_per_side": 2.0,
        "fee_model": {"commission_bps": 1.0},
        "slippage_model": {"slippage_bps": 2.0},
        "limit_up_down_handling": "not_modelled",
        "halt_handling": "not_modelled",
        "partial_fill_supported": False,
        "no_fill_supported": True,
        "open_missing_behavior": "unfilled",
        "terminal_position_behavior": "terminal_liquidation_event",
        "volume_participation_limit": None,
    }
    execution_model = {
        "model_id": "rule_backtest_default_execution_model_v1",
        "version": "v1",
        "entry_timing": "next_bar_open",
        "exit_timing": "next_bar_open",
        "entry_fill_price_basis": "open",
        "exit_fill_price_basis": "open",
        "fee_bps_per_side": 1.0,
        "slippage_bps_per_side": 2.0,
        "capabilities": {
            "partial_fills_supported": False,
            "missing_required_price_state": "unfilled",
            "terminal_liquidation_supported": True,
        },
        "terminal_liquidation": {
            "event_type": "terminal_liquidation",
            "policy_id": "window_end_close_liquidation_v1",
        },
        "market_rules": {
            "trading_day_execution": "available_bars_only",
            "missing_required_fill_price": "unfilled",
            "window_end_position_handling": "terminal_liquidation_event",
        },
    }
    result_authority = {
        "domains": {
            "execution_assumptions_snapshot": {
                "completeness": "complete",
            }
        }
    }

    snapshots = (
        deepcopy(data_quality),
        deepcopy(execution_assumptions),
        deepcopy(execution_model),
        deepcopy(result_authority),
    )

    readiness = build_backtest_professional_readiness(
        data_quality=data_quality,
        execution_assumptions=execution_assumptions,
        execution_model=execution_model,
        result_authority=result_authority,
        dataset_version="unknown",
    ).to_dict()

    assert data_quality == snapshots[0]
    assert execution_assumptions == snapshots[1]
    assert execution_model == snapshots[2]
    assert result_authority == snapshots[3]

    assert readiness["overall_state"] == "research_prototype"
    assert readiness["professional_quant_ready"] is False
    assert readiness["fill_model"] == "next_open_with_explicit_no_fill"
    assert readiness["terminal_fallback"] == "terminal_liquidation"
    assert readiness["open_missing_fallback"] == "unfilled"
    assert readiness["commission_model"] == "bps_per_side"
    assert readiness["cost_model_state"] == "explicit_cost_capacity_diagnostics"
    assert readiness["tax_model"] == "not_modelled"
    assert readiness["stamp_duty_model"] == "not_modelled"
    assert readiness["spread_model"] == "not_modelled"
    assert readiness["market_impact_model"] == "not_modelled"
    assert readiness["minimum_fee_model"] == "not_modelled"
    assert readiness["partial_fill_supported"] is False
    assert readiness["no_fill_supported"] is True
    assert readiness["volume_participation_limit"] is None
    assert readiness["trading_calendar_state"] == "available_bars_only"
    assert readiness["trading_calendar_ready"] is False
    assert readiness["corporate_action_state"] == "not_ready"
    assert readiness["corporate_actions_ready"] is False
    assert readiness["adjusted_data_state"] == "unknown_or_mixed"
    assert readiness["reproducibility_state"] == "partial_without_dataset_lineage"
    assert readiness["professional_reproducibility_ready"] is False
    assert readiness["dataset_version"] == "unknown"

    fill_category = readiness["categories"]["fill_model"]
    assert fill_category["ready"] is False
    assert fill_category["state"] == "next_open_with_explicit_no_fill"
    assert fill_category["summary"] == (
        "Execution uses next-open fills, preserves missing required prices as unfilled, "
        "and records terminal liquidation separately."
    )
    assert fill_category["blockers"] == [
        "partial_fill_model_missing",
        "liquidity_constraints_not_modelled",
        "limit_halt_handling_not_modelled",
    ]

    cost_category = readiness["categories"]["cost_model"]
    assert cost_category["ready"] is False
    assert cost_category["state"] == "explicit_cost_capacity_diagnostics"
    assert cost_category["summary"] == "Costs are limited to baseline bps commission/slippage assumptions."
    assert cost_category["details"]["commission_bps"] == 1.0
    assert cost_category["details"]["slippage_bps"] == 2.0
    assert cost_category["blockers"] == [
        "tax_model_missing",
        "market_impact_model_missing",
    ]

    calendar_category = readiness["categories"]["trading_calendar"]
    assert calendar_category["ready"] is False
    assert calendar_category["state"] == "available_bars_only"
    assert calendar_category["summary"] == (
        "Calendar handling is based on available bars only and is not a market-calendar contract."
    )
    assert calendar_category["blockers"] == [
        "holiday_calendar_not_modelled",
        "half_day_policy_unverified",
    ]

    corporate_actions_category = readiness["categories"]["corporate_actions"]
    assert corporate_actions_category["ready"] is False
    assert corporate_actions_category["state"] == "not_ready"
    assert corporate_actions_category["summary"] == (
        "Corporate-action lineage is not explicit enough for professional backtest claims."
    )
    assert corporate_actions_category["blockers"] == [
        "split_policy_unverified",
        "dividend_policy_unverified",
    ]
