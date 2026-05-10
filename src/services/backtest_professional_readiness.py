# -*- coding: utf-8 -*-
"""Additive professional-readiness diagnostics for backtest outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BacktestReadinessCategory(str, Enum):
    ADJUSTED_DATA = "adjusted_data"
    CORPORATE_ACTIONS = "corporate_actions"
    TRADING_CALENDAR = "trading_calendar"
    FILL_MODEL = "fill_model"
    COST_MODEL = "cost_model"
    ANTI_LEAKAGE = "anti_leakage"
    REPRODUCIBILITY = "reproducibility"
    UNIVERSE_BIAS = "universe_bias"
    LOCAL_DATA_COVERAGE = "local_data_coverage"


@dataclass(slots=True)
class BacktestReadinessDescriptor:
    state: str
    ready: bool
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "ready": self.ready,
            "summary": self.summary,
            "details": dict(self.details or {}),
            "blockers": list(self.blockers or []),
        }


@dataclass(slots=True)
class BacktestProfessionalReadiness:
    overall_state: str = "research_prototype"
    professional_quant_ready: bool = False
    adjusted_data_state: str = "unknown_or_mixed"
    adjusted_ohlc_available: bool = False
    adjusted_close_only: str = "unknown"
    return_basis: str = "unknown"
    corporate_action_state: str = "not_ready"
    corporate_actions_ready: bool = False
    trading_calendar_state: str = "available_bars_only"
    trading_calendar_ready: bool = False
    fill_model: str = "next_open_baseline"
    terminal_fallback: str = "same_bar_close"
    open_missing_fallback: str = "close_fallback_when_open_missing"
    no_fill_supported: bool = False
    partial_fill_supported: bool = False
    volume_participation_limit: float | None = None
    cost_model_state: str = "baseline_bps_only"
    commission_model: str = "bps_per_side"
    tax_model: str = "not_modelled"
    stamp_duty_model: str = "not_modelled"
    spread_model: str = "not_modelled"
    market_impact_model: str = "not_modelled"
    minimum_fee_model: str = "not_modelled"
    anti_leakage_state: str = "basic_bar_close_to_next_open"
    reproducibility_state: str = "partial_without_dataset_lineage"
    dataset_version: str = "unknown"
    professional_reproducibility_ready: bool = False
    point_in_time_universe: bool = False
    survivorship_bias_state: str = "not_applicable_single_symbol"
    local_data_coverage_state: str = "not_applicable_single_symbol"
    provider_calls: bool = False
    categories: dict[str, BacktestReadinessDescriptor] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_state": self.overall_state,
            "professional_quant_ready": self.professional_quant_ready,
            "adjusted_data_state": self.adjusted_data_state,
            "adjusted_ohlc_available": self.adjusted_ohlc_available,
            "adjusted_close_only": self.adjusted_close_only,
            "return_basis": self.return_basis,
            "corporate_action_state": self.corporate_action_state,
            "corporate_actions_ready": self.corporate_actions_ready,
            "trading_calendar_state": self.trading_calendar_state,
            "trading_calendar_ready": self.trading_calendar_ready,
            "calendar_state": self.trading_calendar_state,
            "fill_model": self.fill_model,
            "terminal_fallback": self.terminal_fallback,
            "open_missing_fallback": self.open_missing_fallback,
            "no_fill_supported": self.no_fill_supported,
            "partial_fill_supported": self.partial_fill_supported,
            "volume_participation_limit": self.volume_participation_limit,
            "cost_model_state": self.cost_model_state,
            "commission_model": self.commission_model,
            "tax_model": self.tax_model,
            "stamp_duty_model": self.stamp_duty_model,
            "spread_model": self.spread_model,
            "market_impact_model": self.market_impact_model,
            "minimum_fee_model": self.minimum_fee_model,
            "anti_leakage_state": self.anti_leakage_state,
            "reproducibility_state": self.reproducibility_state,
            "dataset_version": self.dataset_version,
            "professional_reproducibility_ready": self.professional_reproducibility_ready,
            "point_in_time_universe": self.point_in_time_universe,
            "survivorship_bias_state": self.survivorship_bias_state,
            "local_data_coverage_state": self.local_data_coverage_state,
            "provider_calls": self.provider_calls,
            "categories": {
                key: value.to_dict()
                for key, value in (self.categories or {}).items()
            },
        }


def _descriptor(
    *,
    state: str,
    ready: bool,
    summary: str,
    details: dict[str, Any] | None = None,
    blockers: list[str] | None = None,
) -> BacktestReadinessDescriptor:
    return BacktestReadinessDescriptor(
        state=state,
        ready=ready,
        summary=summary,
        details=dict(details or {}),
        blockers=list(blockers or []),
    )


def build_backtest_professional_readiness(
    *,
    universe_mode: bool = False,
    local_data_coverage_state: str = "not_applicable_single_symbol",
    point_in_time_universe: bool = False,
    provider_calls: bool = False,
    dataset_version: str = "unknown",
) -> BacktestProfessionalReadiness:
    survivorship_bias_state = "uncontrolled" if universe_mode else "not_applicable_single_symbol"
    readiness = BacktestProfessionalReadiness(
        dataset_version=str(dataset_version or "unknown"),
        point_in_time_universe=bool(point_in_time_universe),
        survivorship_bias_state=survivorship_bias_state,
        local_data_coverage_state=str(local_data_coverage_state or "unknown"),
        provider_calls=bool(provider_calls),
    )
    readiness.categories = {
        BacktestReadinessCategory.ADJUSTED_DATA.value: _descriptor(
            state=readiness.adjusted_data_state,
            ready=False,
            summary="Adjusted OHLC basis is unknown or mixed; professional return claims are blocked.",
            details={
                "adjusted_ohlc_available": readiness.adjusted_ohlc_available,
                "adjusted_close_only": readiness.adjusted_close_only,
                "return_basis": readiness.return_basis,
            },
            blockers=["adjusted_ohlc_unavailable", "return_basis_unknown"],
        ),
        BacktestReadinessCategory.CORPORATE_ACTIONS.value: _descriptor(
            state=readiness.corporate_action_state,
            ready=False,
            summary="Corporate-action lineage is not explicit enough for professional backtest claims.",
            details={"corporate_actions_ready": readiness.corporate_actions_ready},
            blockers=["split_policy_unverified", "dividend_policy_unverified"],
        ),
        BacktestReadinessCategory.TRADING_CALENDAR.value: _descriptor(
            state=readiness.trading_calendar_state,
            ready=False,
            summary="Calendar handling is based on available bars only and is not a market-calendar contract.",
            details={"trading_calendar_ready": readiness.trading_calendar_ready},
            blockers=["holiday_calendar_not_modelled", "half_day_policy_unverified"],
        ),
        BacktestReadinessCategory.FILL_MODEL.value: _descriptor(
            state=readiness.fill_model,
            ready=False,
            summary="Execution assumes next-open baseline fills with terminal same-bar-close fallback.",
            details={
                "terminal_fallback": readiness.terminal_fallback,
                "open_missing_fallback": readiness.open_missing_fallback,
                "no_fill_supported": readiness.no_fill_supported,
                "partial_fill_supported": readiness.partial_fill_supported,
                "volume_participation_limit": readiness.volume_participation_limit,
            },
            blockers=["partial_fill_model_missing", "liquidity_constraints_not_modelled"],
        ),
        BacktestReadinessCategory.COST_MODEL.value: _descriptor(
            state=readiness.cost_model_state,
            ready=False,
            summary="Costs are limited to baseline bps commission/slippage assumptions.",
            details={
                "commission_model": readiness.commission_model,
                "tax_model": readiness.tax_model,
                "stamp_duty_model": readiness.stamp_duty_model,
                "spread_model": readiness.spread_model,
                "market_impact_model": readiness.market_impact_model,
                "minimum_fee_model": readiness.minimum_fee_model,
            },
            blockers=["tax_model_missing", "market_impact_model_missing"],
        ),
        BacktestReadinessCategory.ANTI_LEAKAGE.value: _descriptor(
            state=readiness.anti_leakage_state,
            ready=False,
            summary="The current anti-leakage posture is a deterministic baseline, not a full professional leakage-control contract.",
            blockers=["same_dataset_lineage_unverified"],
        ),
        BacktestReadinessCategory.REPRODUCIBILITY.value: _descriptor(
            state=readiness.reproducibility_state,
            ready=False,
            summary="Stored outputs are reproducible for research use, but dataset and lineage versioning remain incomplete.",
            details={
                "dataset_version": readiness.dataset_version,
                "professional_reproducibility_ready": readiness.professional_reproducibility_ready,
            },
            blockers=["dataset_version_unknown", "calendar_version_unknown"],
        ),
        BacktestReadinessCategory.UNIVERSE_BIAS.value: _descriptor(
            state=readiness.survivorship_bias_state,
            ready=False,
            summary=(
                "Universe bias remains uncontrolled without point-in-time membership history."
                if universe_mode
                else "Universe-bias diagnostics are not applicable to the single-symbol path."
            ),
            details={
                "point_in_time_universe": readiness.point_in_time_universe,
                "survivorship_bias_state": readiness.survivorship_bias_state,
            },
            blockers=(["point_in_time_universe_missing"] if universe_mode else []),
        ),
        BacktestReadinessCategory.LOCAL_DATA_COVERAGE.value: _descriptor(
            state=readiness.local_data_coverage_state,
            ready=False,
            summary=(
                "Universe execution remains local-data-only and coverage is diagnostic-only."
                if universe_mode
                else "Local-data coverage is not a single-symbol professional-readiness gate in this response."
            ),
            details={"provider_calls": readiness.provider_calls},
            blockers=(["local_data_coverage_incomplete"] if universe_mode else []),
        ),
    }
    return readiness
