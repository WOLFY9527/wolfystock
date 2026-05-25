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


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _text(value: Any, default: str = "unknown") -> str:
    text = str(value or "").strip()
    return text or default


def _lower(value: Any) -> str:
    return _text(value, "").lower()


def _is_positive(value: Any) -> bool:
    if value is True:
        return True
    return _lower(value) in {
        "available",
        "complete",
        "confirmed",
        "covered",
        "enabled",
        "explicit",
        "handled",
        "modeled",
        "modelled",
        "ready",
        "supported",
        "true",
        "verified",
        "yes",
    }


def _is_unknown(value: Any) -> bool:
    return _lower(value) in {"", "mixed", "n/a", "none", "not_applicable", "unknown", "unknown_or_mixed"}


def _has_value(value: Any) -> bool:
    return not _is_unknown(value)


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _authority_blockers(data_quality: dict[str, Any]) -> list[str]:
    status = _lower(data_quality.get("authority_status"))
    reasons = [str(item) for item in data_quality.get("authority_reason_codes") or [] if str(item or "").strip()]
    if "source_authority_unknown" in reasons:
        return reasons
    if status == "allowed" or not status:
        return []
    if status == "unknown":
        return reasons or ["source_authority_unknown"]
    if reasons:
        return reasons
    if status == "degraded_fill_only":
        return ["source_authority_degraded"]
    return ["source_authority_rejected"]


def _derive_adjusted_data(readiness: BacktestProfessionalReadiness, data_quality: dict[str, Any]) -> BacktestReadinessDescriptor:
    adjustment_mode = _lower(data_quality.get("adjustment_mode"))
    return_basis = _text(data_quality.get("return_basis"), "unknown")
    adjusted_ohlc = bool(data_quality.get("adjusted_ohlc_available")) or adjustment_mode in {
        "adjusted",
        "adjusted_ohlc",
        "adjusted_ohlcv",
        "fully_adjusted",
        "split_dividend_adjusted",
        "total_return_adjusted",
    }
    adjusted_close_only = adjustment_mode in {"adjusted_close", "close_adjusted"} or _is_positive(
        data_quality.get("adjusted_close_available")
    )

    readiness.adjusted_ohlc_available = bool(adjusted_ohlc)
    readiness.adjusted_close_only = "yes" if adjusted_close_only and not adjusted_ohlc else ("no" if adjusted_ohlc else "unknown")
    readiness.return_basis = "adjusted_total_return" if adjusted_ohlc and return_basis == "unknown" else return_basis
    if adjusted_ohlc:
        readiness.adjusted_data_state = "adjusted_ohlc"
        blockers: list[str] = []
    elif adjusted_close_only:
        readiness.adjusted_data_state = "adjusted_close_only"
        blockers = ["adjusted_ohlc_unavailable"]
    else:
        readiness.adjusted_data_state = "unknown_or_mixed"
        blockers = ["adjusted_ohlc_unavailable", "return_basis_unknown"]

    return _descriptor(
        state=readiness.adjusted_data_state,
        ready=not blockers,
        summary=(
            "Adjusted OHLC and return basis are explicit."
            if not blockers
            else "Adjusted OHLC basis is unknown or mixed; professional return claims are blocked."
        ),
        details={
            "adjusted_ohlc_available": readiness.adjusted_ohlc_available,
            "adjusted_close_only": readiness.adjusted_close_only,
            "return_basis": readiness.return_basis,
            "adjustment_mode": adjustment_mode or "unknown",
        },
        blockers=blockers,
    )


def _derive_corporate_actions(readiness: BacktestProfessionalReadiness, data_quality: dict[str, Any]) -> BacktestReadinessDescriptor:
    dividends_ready = _is_positive(data_quality.get("dividends_handled"))
    splits_ready = _is_positive(data_quality.get("splits_handled"))
    readiness.corporate_actions_ready = dividends_ready and splits_ready
    if readiness.corporate_actions_ready:
        readiness.corporate_action_state = "explicit"
    elif dividends_ready or splits_ready:
        readiness.corporate_action_state = "partial"
    else:
        readiness.corporate_action_state = "not_ready"

    blockers: list[str] = []
    if not splits_ready:
        blockers.append("split_policy_unverified")
    if not dividends_ready:
        blockers.append("dividend_policy_unverified")

    return _descriptor(
        state=readiness.corporate_action_state,
        ready=not blockers,
        summary=(
            "Dividend and split handling are explicit."
            if not blockers
            else "Corporate-action lineage is not explicit enough for professional backtest claims."
        ),
        details={
            "corporate_actions_ready": readiness.corporate_actions_ready,
            "dividends_handled": _text(data_quality.get("dividends_handled")),
            "splits_handled": _text(data_quality.get("splits_handled")),
        },
        blockers=blockers,
    )


def _derive_calendar(readiness: BacktestProfessionalReadiness, data_quality: dict[str, Any], execution_assumptions: dict[str, Any]) -> BacktestReadinessDescriptor:
    calendar = _text(
        execution_assumptions.get("trading_calendar")
        or execution_assumptions.get("market_calendar")
        or data_quality.get("trading_calendar"),
        "",
    )
    holiday_ready = _is_positive(execution_assumptions.get("holiday_calendar")) or _is_positive(
        execution_assumptions.get("holiday_policy")
    )
    half_day_ready = _is_positive(execution_assumptions.get("half_day_policy"))
    readiness.trading_calendar_ready = bool(calendar) and holiday_ready and half_day_ready
    if readiness.trading_calendar_ready:
        readiness.trading_calendar_state = "explicit_market_calendar"
    elif calendar:
        readiness.trading_calendar_state = "partial_market_calendar"
    else:
        readiness.trading_calendar_state = "available_bars_only"

    blockers: list[str] = []
    if not calendar or not holiday_ready:
        blockers.append("holiday_calendar_not_modelled")
    if not half_day_ready:
        blockers.append("half_day_policy_unverified")

    return _descriptor(
        state=readiness.trading_calendar_state,
        ready=not blockers,
        summary=(
            "Market calendar, holiday, and half-day policies are explicit."
            if not blockers
            else "Calendar handling is based on available bars only and is not a market-calendar contract."
        ),
        details={"trading_calendar_ready": readiness.trading_calendar_ready, "trading_calendar": calendar or "unknown"},
        blockers=blockers,
    )


def _derive_fill_model(readiness: BacktestProfessionalReadiness, execution_assumptions: dict[str, Any]) -> BacktestReadinessDescriptor:
    volume_limit = _optional_float(execution_assumptions.get("volume_participation_limit"))
    partial_fill_supported = _is_positive(execution_assumptions.get("partial_fill_supported"))
    no_fill_supported = _is_positive(execution_assumptions.get("no_fill_supported"))
    limit_ready = _is_positive(execution_assumptions.get("limit_up_down_handling"))
    halt_ready = _is_positive(execution_assumptions.get("halt_handling"))

    readiness.volume_participation_limit = volume_limit
    readiness.partial_fill_supported = partial_fill_supported
    readiness.no_fill_supported = no_fill_supported
    readiness.fill_model = (
        "explicit_capacity_and_fallback_controls"
        if volume_limit is not None and partial_fill_supported and no_fill_supported and limit_ready and halt_ready
        else "next_open_baseline"
    )

    blockers: list[str] = []
    if not partial_fill_supported:
        blockers.append("partial_fill_model_missing")
    if not no_fill_supported:
        blockers.append("no_fill_policy_missing")
    if volume_limit is None:
        blockers.append("liquidity_constraints_not_modelled")
    if not limit_ready or not halt_ready:
        blockers.append("limit_halt_handling_not_modelled")

    return _descriptor(
        state=readiness.fill_model,
        ready=not blockers,
        summary=(
            "Capacity, no-fill, partial-fill, limit, and halt controls are explicit."
            if not blockers
            else "Execution assumes next-open baseline fills with terminal same-bar-close fallback."
        ),
        details={
            "terminal_fallback": readiness.terminal_fallback,
            "open_missing_fallback": readiness.open_missing_fallback,
            "no_fill_supported": readiness.no_fill_supported,
            "partial_fill_supported": readiness.partial_fill_supported,
            "volume_participation_limit": readiness.volume_participation_limit,
            "limit_up_down_handling": _text(execution_assumptions.get("limit_up_down_handling"), "not_modelled"),
            "halt_handling": _text(execution_assumptions.get("halt_handling"), "not_modelled"),
        },
        blockers=blockers,
    )


def _derive_cost_model(
    readiness: BacktestProfessionalReadiness,
    execution_assumptions: dict[str, Any],
    cost_capacity_diagnostics: dict[str, Any],
) -> BacktestReadinessDescriptor:
    fee_model = _mapping(execution_assumptions.get("fee_model"))
    slippage_model = _mapping(execution_assumptions.get("slippage_model"))
    cost_assumptions = _mapping(cost_capacity_diagnostics.get("assumptions"))
    commission_bps = _optional_float(fee_model.get("commission_bps"))
    slippage_bps = _optional_float(slippage_model.get("slippage_bps"))
    spread_bps = _optional_float(cost_assumptions.get("spread_bps"))
    minimum_fee = _optional_float(cost_assumptions.get("minimum_fee"))

    if fee_model or "fee_bps_per_side" in execution_assumptions or "commission_bps" in execution_assumptions:
        readiness.commission_model = "bps_per_side" if (commission_bps or 0.0) > 0 else "none"
    readiness.spread_model = "one_way_bps" if (spread_bps or 0.0) > 0 else "not_modelled"
    readiness.minimum_fee_model = "fixed_minimum_per_filled_trade" if (minimum_fee or 0.0) > 0 else "not_modelled"
    readiness.cost_model_state = (
        "explicit_cost_capacity_diagnostics"
        if (commission_bps or 0.0) > 0 or (slippage_bps or 0.0) > 0 or (spread_bps or 0.0) > 0 or cost_assumptions
        else "baseline_bps_only"
    )

    tax_ready = _is_positive(execution_assumptions.get("tax_modelled")) or _has_value(execution_assumptions.get("tax_model"))
    impact_ready = _is_positive(execution_assumptions.get("market_impact_modelled")) or _has_value(
        execution_assumptions.get("market_impact_model")
    )
    blockers: list[str] = []
    if not tax_ready:
        blockers.append("tax_model_missing")
    if not impact_ready:
        blockers.append("market_impact_model_missing")

    return _descriptor(
        state=readiness.cost_model_state,
        ready=not blockers,
        summary="Costs include explicit professional assumptions." if not blockers else "Costs are limited to baseline bps commission/slippage assumptions.",
        details={
            "commission_model": readiness.commission_model,
            "tax_model": readiness.tax_model,
            "stamp_duty_model": readiness.stamp_duty_model,
            "spread_model": readiness.spread_model,
            "market_impact_model": readiness.market_impact_model,
            "minimum_fee_model": readiness.minimum_fee_model,
            "commission_bps": commission_bps,
            "slippage_bps": slippage_bps,
            "spread_bps": spread_bps,
        },
        blockers=blockers,
    )


def _derive_reproducibility(
    readiness: BacktestProfessionalReadiness,
    data_quality: dict[str, Any],
    result_authority: dict[str, Any],
    dataset_version: str,
) -> BacktestReadinessDescriptor:
    authority_blockers = _authority_blockers(data_quality)
    authority_status = _lower(data_quality.get("authority_status"))
    snapshot = _mapping(result_authority.get("domains")).get("execution_assumptions_snapshot")
    snapshot_complete = isinstance(snapshot, dict) and _lower(snapshot.get("completeness")) == "complete"
    readiness.dataset_version = _text(dataset_version)
    readiness.professional_reproducibility_ready = (
        _has_value(readiness.dataset_version)
        and readiness.dataset_version != "unknown"
        and not authority_blockers
        and (snapshot_complete or _is_positive(result_authority.get("reproducibility_ready")))
    )
    if authority_blockers:
        readiness.reproducibility_state = (
            "degraded_source_authority" if authority_status == "degraded_fill_only" else "blocked_source_authority"
        )
    elif readiness.professional_reproducibility_ready:
        readiness.reproducibility_state = "explicit_dataset_lineage"
    else:
        readiness.reproducibility_state = "partial_without_dataset_lineage"

    blockers = list(authority_blockers)
    if not _has_value(readiness.dataset_version) or readiness.dataset_version == "unknown":
        blockers.append("dataset_version_unknown")
    if not readiness.professional_reproducibility_ready and "calendar_version_unknown" not in blockers:
        blockers.append("calendar_version_unknown")

    return _descriptor(
        state=readiness.reproducibility_state,
        ready=not blockers,
        summary=(
            "Dataset lineage and reproducibility authority are explicit."
            if not blockers
            else "Stored outputs are reproducible for research use, but dataset and lineage versioning remain incomplete."
        ),
        details={
            "dataset_version": readiness.dataset_version,
            "professional_reproducibility_ready": readiness.professional_reproducibility_ready,
            "authority_status": authority_status or "unknown",
        },
        blockers=blockers,
    )


def build_backtest_professional_readiness(
    *,
    universe_mode: bool = False,
    local_data_coverage_state: str = "not_applicable_single_symbol",
    point_in_time_universe: bool = False,
    provider_calls: bool = False,
    dataset_version: str = "unknown",
    data_quality: dict[str, Any] | None = None,
    execution_assumptions: dict[str, Any] | None = None,
    execution_model: dict[str, Any] | None = None,
    result_authority: dict[str, Any] | None = None,
    cost_capacity_diagnostics: dict[str, Any] | None = None,
) -> BacktestProfessionalReadiness:
    data_quality_payload = _mapping(data_quality)
    execution_assumptions_payload = _mapping(execution_assumptions)
    execution_model_payload = _mapping(execution_model)
    result_authority_payload = _mapping(result_authority)
    cost_capacity_payload = _mapping(cost_capacity_diagnostics)
    survivorship_bias_state = "uncontrolled" if universe_mode else "not_applicable_single_symbol"
    readiness = BacktestProfessionalReadiness(
        dataset_version=_text(dataset_version),
        point_in_time_universe=bool(point_in_time_universe),
        survivorship_bias_state=survivorship_bias_state,
        local_data_coverage_state=str(local_data_coverage_state or "unknown"),
        provider_calls=bool(provider_calls),
    )
    readiness.categories = {
        BacktestReadinessCategory.ADJUSTED_DATA.value: _derive_adjusted_data(readiness, data_quality_payload),
        BacktestReadinessCategory.CORPORATE_ACTIONS.value: _derive_corporate_actions(readiness, data_quality_payload),
        BacktestReadinessCategory.TRADING_CALENDAR.value: _derive_calendar(
            readiness,
            data_quality_payload,
            execution_assumptions_payload,
        ),
        BacktestReadinessCategory.FILL_MODEL.value: _derive_fill_model(readiness, execution_assumptions_payload),
        BacktestReadinessCategory.COST_MODEL.value: _derive_cost_model(
            readiness,
            {**execution_assumptions_payload, **execution_model_payload},
            cost_capacity_payload,
        ),
        BacktestReadinessCategory.ANTI_LEAKAGE.value: _descriptor(
            state=readiness.anti_leakage_state,
            ready=False,
            summary="The current anti-leakage posture is a deterministic baseline, not a full professional leakage-control contract.",
            blockers=["same_dataset_lineage_unverified"],
        ),
        BacktestReadinessCategory.REPRODUCIBILITY.value: _derive_reproducibility(
            readiness,
            data_quality_payload,
            result_authority_payload,
            dataset_version,
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
    required_categories = [
        BacktestReadinessCategory.ADJUSTED_DATA.value,
        BacktestReadinessCategory.CORPORATE_ACTIONS.value,
        BacktestReadinessCategory.TRADING_CALENDAR.value,
        BacktestReadinessCategory.FILL_MODEL.value,
        BacktestReadinessCategory.COST_MODEL.value,
        BacktestReadinessCategory.ANTI_LEAKAGE.value,
        BacktestReadinessCategory.REPRODUCIBILITY.value,
    ]
    if universe_mode:
        required_categories.extend(
            [
                BacktestReadinessCategory.UNIVERSE_BIAS.value,
                BacktestReadinessCategory.LOCAL_DATA_COVERAGE.value,
            ]
        )
    readiness.professional_quant_ready = all(
        bool(readiness.categories[category].ready) for category in required_categories
    )
    readiness.overall_state = "professional_ready" if readiness.professional_quant_ready else "research_prototype"
    return readiness
