# -*- coding: utf-8 -*-
"""Pure leveraged ETF mapper calculations.

The service only uses caller-provided prices and curated static metadata. It
does not fetch quotes, call providers, read caches, or touch portfolios.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.data.leveraged_etf_mappings import (
    CURATED_LEVERAGED_ETF_MAPPINGS,
    LeveragedEtfMapping,
)


LIMITATION_CODES: tuple[str, ...] = (
    "same_day_reference_anchor_approximation",
    "daily_reset_path_dependency",
    "fees_financing_tracking_error_excluded",
    "overnight_multi_day_drift_not_modelled",
    "not_investment_advice",
    "no_order_placement",
    "no_portfolio_mutation",
)

WARNING_MESSAGES: tuple[str, ...] = (
    "Same-day reference-anchor approximation only; caller-provided reference prices are not fetched or verified.",
    "Daily reset and path dependency can make leveraged ETF outcomes diverge from this approximation.",
    "Fees, financing costs, distributions, spreads, tracking error, and volatility drag are excluded.",
    "Overnight and multi-day drift are not modelled.",
    "Analytical calculation only; not investment advice.",
    "No order placement, broker connection, or portfolio mutation is performed.",
)

CONTRACT_METADATA: dict[str, bool | str] = {
    "contractVersion": "leveraged_etf_mapper_v1",
    "calculationOnly": True,
    "externalProviderCalls": False,
    "providerRuntimeChanged": False,
    "marketCacheMutation": False,
    "noOrderPlacement": True,
    "noBrokerConnection": True,
    "noPortfolioMutation": True,
    "notInvestmentAdvice": True,
}


class LeveragedEtfMapperInputError(ValueError):
    """Validation error surfaced by the pure mapper service."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class _CalculationInputs:
    etf_symbol: str
    underlying_symbol: str
    etf_ref_price: float
    underlying_ref_price: float
    underlying_target_price: float | None
    etf_target_price: float | None


class LeveragedEtfMapperService:
    def __init__(self, mappings: Iterable[LeveragedEtfMapping] | None = None) -> None:
        mapping_items = tuple(mappings or CURATED_LEVERAGED_ETF_MAPPINGS)
        self._mappings_by_symbol = {
            _normalize_symbol(mapping.etf_symbol): mapping for mapping in mapping_items
        }

    def list_mappings(self) -> list[dict[str, object]]:
        return [
            self._mappings_by_symbol[symbol].to_public_dict()
            for symbol in sorted(self._mappings_by_symbol)
        ]

    def list_mappings_payload(self) -> dict[str, object]:
        return {
            "mappings": self.list_mappings(),
            "limitationCodes": list(LIMITATION_CODES),
            "warnings": list(WARNING_MESSAGES),
            "metadata": dict(CONTRACT_METADATA),
        }

    def calculate(
        self,
        *,
        etf_symbol: str,
        underlying_symbol: str,
        etf_ref_price: float,
        underlying_ref_price: float,
        underlying_target_price: float | None = None,
        etf_target_price: float | None = None,
    ) -> dict[str, object]:
        inputs = self._validate_inputs(
            etf_symbol=etf_symbol,
            underlying_symbol=underlying_symbol,
            etf_ref_price=etf_ref_price,
            underlying_ref_price=underlying_ref_price,
            underlying_target_price=underlying_target_price,
            etf_target_price=etf_target_price,
        )
        mapping = self._resolve_mapping(inputs.etf_symbol, inputs.underlying_symbol)

        estimated_etf_price: float | None = None
        implied_underlying_price: float | None = None
        status = "ok"
        invalid_reason: str | None = None
        warning_codes = list(LIMITATION_CODES)

        if inputs.underlying_target_price is not None:
            raw_estimated = inputs.etf_ref_price * (
                1
                + mapping.leverage
                * (inputs.underlying_target_price / inputs.underlying_ref_price - 1)
            )
            if raw_estimated <= 0:
                status = "invalid_low_confidence"
                invalid_reason = "non_positive_estimated_etf_price"
                warning_codes.append(invalid_reason)
            else:
                estimated_etf_price = _round_price(raw_estimated)

        if inputs.etf_target_price is not None:
            raw_implied = inputs.underlying_ref_price * (
                1 + (inputs.etf_target_price / inputs.etf_ref_price - 1) / mapping.leverage
            )
            if raw_implied <= 0:
                status = "invalid_low_confidence"
                invalid_reason = invalid_reason or "non_positive_implied_underlying_price"
                warning_codes.append("non_positive_implied_underlying_price")
            else:
                implied_underlying_price = _round_price(raw_implied)

        return {
            "status": status,
            "mapping": mapping.to_public_dict(),
            "input": {
                "etfSymbol": inputs.etf_symbol,
                "underlyingSymbol": inputs.underlying_symbol,
                "etfRefPrice": inputs.etf_ref_price,
                "underlyingRefPrice": inputs.underlying_ref_price,
                "underlyingTargetPrice": inputs.underlying_target_price,
                "etfTargetPrice": inputs.etf_target_price,
            },
            "estimatedEtfPrice": estimated_etf_price,
            "impliedUnderlyingPrice": implied_underlying_price,
            "invalidReason": invalid_reason,
            "limitationCodes": list(LIMITATION_CODES),
            "warningCodes": warning_codes,
            "warnings": _warnings_for_status(warning_codes),
            "metadata": dict(CONTRACT_METADATA),
        }

    def _resolve_mapping(self, etf_symbol: str, underlying_symbol: str) -> LeveragedEtfMapping:
        mapping = self._mappings_by_symbol.get(etf_symbol)
        if mapping is None:
            raise LeveragedEtfMapperInputError(
                "unsupported_mapping",
                f"Unsupported leveraged ETF mapping: {etf_symbol}",
            )
        if mapping.leverage <= 0:
            raise LeveragedEtfMapperInputError(
                "unsupported_leverage",
                "Leveraged ETF mapper v1 supports positive leverage only.",
            )
        if _normalize_symbol(mapping.underlying_symbol) != underlying_symbol:
            raise LeveragedEtfMapperInputError(
                "unsupported_mapping_mismatch",
                f"{etf_symbol} is mapped to {mapping.underlying_symbol}, not {underlying_symbol}.",
            )
        return mapping

    def _validate_inputs(
        self,
        *,
        etf_symbol: str,
        underlying_symbol: str,
        etf_ref_price: float,
        underlying_ref_price: float,
        underlying_target_price: float | None,
        etf_target_price: float | None,
    ) -> _CalculationInputs:
        normalized_etf = _normalize_symbol(etf_symbol)
        normalized_underlying = _normalize_symbol(underlying_symbol)
        if not normalized_etf or not normalized_underlying:
            raise LeveragedEtfMapperInputError(
                "missing_symbol",
                "Both etfSymbol and underlyingSymbol are required.",
            )
        if etf_ref_price <= 0 or underlying_ref_price <= 0:
            raise LeveragedEtfMapperInputError(
                "invalid_reference_price",
                "etfRefPrice and underlyingRefPrice must be positive.",
            )
        if underlying_target_price is None and etf_target_price is None:
            raise LeveragedEtfMapperInputError(
                "missing_target_input",
                "Provide underlyingTargetPrice or etfTargetPrice.",
            )
        if underlying_target_price is not None and underlying_target_price <= 0:
            raise LeveragedEtfMapperInputError(
                "invalid_target_price",
                "underlyingTargetPrice must be positive when provided.",
            )
        if etf_target_price is not None and etf_target_price <= 0:
            raise LeveragedEtfMapperInputError(
                "invalid_target_price",
                "etfTargetPrice must be positive when provided.",
            )
        return _CalculationInputs(
            etf_symbol=normalized_etf,
            underlying_symbol=normalized_underlying,
            etf_ref_price=float(etf_ref_price),
            underlying_ref_price=float(underlying_ref_price),
            underlying_target_price=(
                float(underlying_target_price)
                if underlying_target_price is not None
                else None
            ),
            etf_target_price=float(etf_target_price) if etf_target_price is not None else None,
        )


def _normalize_symbol(value: str | None) -> str:
    return str(value or "").strip().upper()


def _round_price(value: float) -> float:
    return round(value, 6)


def _warnings_for_status(warning_codes: list[str]) -> list[str]:
    warnings = list(WARNING_MESSAGES)
    if "non_positive_estimated_etf_price" in warning_codes:
        warnings.append(
            "The forward formula produced a non-positive ETF value under the provided scenario, so no usable ETF price is returned."
        )
    if "non_positive_implied_underlying_price" in warning_codes:
        warnings.append(
            "The reverse formula produced a non-positive underlying value under the provided scenario, so no usable underlying price is returned."
        )
    return warnings
