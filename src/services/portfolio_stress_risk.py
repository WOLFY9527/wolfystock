# -*- coding: utf-8 -*-
"""Advisory-only portfolio stress and VaR projection helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, Field


MIN_RETURN_SAMPLE_COUNT = 5


class PortfolioStressRiskCoverage(BaseModel):
    totalPositions: int = 0
    positionsWithUsableWeight: int = 0
    positionsWithMarketValue: int = 0
    effectiveWeightSum: float = 0.0
    totalMarketValue: float | None = None


class PortfolioStressRiskPositionContribution(BaseModel):
    symbol: str
    weight: float = 0.0
    marketValue: float | None = None
    shockPct: float | None = None
    impactPct: float | None = None
    impactAmount: float | None = None
    contributionToScenarioLoss: float | None = None
    warnings: list[str] = Field(default_factory=list)


class PortfolioStressRiskScenarioResult(BaseModel):
    name: str
    portfolioImpactPct: float = 0.0
    portfolioImpactAmount: float | None = None
    coveredWeight: float = 0.0
    coveredMarketValue: float | None = None
    missingSymbols: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    positionContributions: list[PortfolioStressRiskPositionContribution] = Field(default_factory=list)


class PortfolioStressRiskHistoricalVarSummary(BaseModel):
    available: bool = False
    confidenceLevel: float = 0.95
    sampleCount: int = 0
    varLossPct: float | None = None
    cvarLossPct: float | None = None
    varLossAmount: float | None = None
    cvarLossAmount: float | None = None
    worstSampleReturnPct: float | None = None
    bestSampleReturnPct: float | None = None
    insufficientDataReasons: list[str] = Field(default_factory=list)
    missingDataWarnings: list[str] = Field(default_factory=list)


class PortfolioStressRiskDrawdownEstimate(BaseModel):
    lossPct: float = 0.0
    lossAmount: float | None = None
    source: str = "unavailable"
    methodology: str = "max_of_worst_scenario_and_historical_cvar"


class PortfolioStressRiskMetadata(BaseModel):
    deterministic: bool = True
    sideEffectFree: bool = True
    inputSource: str = "caller_supplied_positions_and_returns"
    noLivePrices: bool = True
    noBrokerSync: bool = True
    noAccountingMutation: bool = True
    noRuntimeWiring: bool = True
    advisoryOnly: bool = True


class PortfolioStressRiskReadModel(BaseModel):
    readModelType: str = "portfolio_stress_var_advisory_v1"
    advisoryOnly: bool = True
    accountingMutation: bool = False
    brokerIntegration: bool = False
    tradeExecution: bool = False
    executionReadiness: str = "advisory_only_not_trade_execution"
    asOf: str | None = None
    coverage: PortfolioStressRiskCoverage = Field(default_factory=PortfolioStressRiskCoverage)
    scenarios: list[PortfolioStressRiskScenarioResult] = Field(default_factory=list)
    drawdownEstimate: PortfolioStressRiskDrawdownEstimate = Field(default_factory=PortfolioStressRiskDrawdownEstimate)
    historicalVar: PortfolioStressRiskHistoricalVarSummary = Field(default_factory=PortfolioStressRiskHistoricalVarSummary)
    insufficientDataReasons: list[str] = Field(default_factory=list)
    missingDataWarnings: list[str] = Field(default_factory=list)
    metadata: PortfolioStressRiskMetadata = Field(default_factory=PortfolioStressRiskMetadata)


@dataclass(frozen=True)
class _NormalizedPosition:
    symbol: str
    raw_weight: float | None
    market_value: float | None
    effective_weight: float


class PortfolioStressRiskService:
    """Build deterministic advisory-only stress and VaR projections."""

    def build_projection(
        self,
        *,
        positions: Sequence[Mapping[str, Any] | object] | Mapping[str, Any],
        scenario_shocks: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None = None,
        return_samples: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None = None,
        as_of: str | None = None,
        confidence_level: float = 0.95,
    ) -> PortfolioStressRiskReadModel:
        normalized_positions, total_market_value = self._normalize_positions(positions)
        coverage = PortfolioStressRiskCoverage(
            totalPositions=len(normalized_positions),
            positionsWithUsableWeight=sum(1 for item in normalized_positions if item.effective_weight > 0),
            positionsWithMarketValue=sum(1 for item in normalized_positions if item.market_value is not None),
            effectiveWeightSum=self._round(sum(item.effective_weight for item in normalized_positions)),
            totalMarketValue=self._round(total_market_value) if total_market_value > 0 else None,
        )

        scenarios = self._build_scenarios(
            positions=normalized_positions,
            scenario_shocks=scenario_shocks,
            total_market_value=total_market_value,
        )
        historical_var = self._build_historical_var(
            positions=normalized_positions,
            return_samples=return_samples,
            total_market_value=total_market_value,
            confidence_level=confidence_level,
        )
        drawdown_estimate = self._build_drawdown_estimate(
            scenarios=scenarios,
            historical_var=historical_var,
            total_market_value=total_market_value,
        )

        insufficient_data_reasons: list[str] = []
        if not normalized_positions:
            insufficient_data_reasons.append("no_positions")
        if scenario_shocks and not scenarios:
            insufficient_data_reasons.append("no_usable_scenario_shocks")
        insufficient_data_reasons.extend(historical_var.insufficientDataReasons)

        missing_data_warnings = list(historical_var.missingDataWarnings)
        if any(item.warnings for item in scenarios):
            missing_data_warnings.append("scenario_shock_coverage_incomplete")

        return PortfolioStressRiskReadModel(
            asOf=self._optional_str(as_of),
            coverage=coverage,
            scenarios=scenarios,
            drawdownEstimate=drawdown_estimate,
            historicalVar=historical_var,
            insufficientDataReasons=self._unique(incomplete for incomplete in insufficient_data_reasons if incomplete),
            missingDataWarnings=self._unique(warning for warning in missing_data_warnings if warning),
        )

    def _normalize_positions(
        self,
        positions: Sequence[Mapping[str, Any] | object] | Mapping[str, Any],
    ) -> tuple[list[_NormalizedPosition], float]:
        aggregated: dict[str, dict[str, float | None]] = {}
        items = self._items_from_mapping_or_sequence(positions, value_key="weight")

        total_market_value = 0.0
        for item in items:
            symbol = self._normalize_symbol(self._field(item, "symbol"))
            if not symbol:
                continue
            row = aggregated.setdefault(symbol, {"raw_weight": 0.0, "has_weight": 0.0, "market_value": 0.0, "has_market_value": 0.0})
            raw_weight = self._coerce_weight_fraction(item)
            if raw_weight is not None and raw_weight > 0:
                row["raw_weight"] = float(row["raw_weight"] or 0.0) + raw_weight
                row["has_weight"] = 1.0
            market_value = self._coerce_money(
                self._first_present(item, "market_value", "marketValue", "market_value_base")
            )
            if market_value is not None and market_value > 0:
                row["market_value"] = float(row["market_value"] or 0.0) + market_value
                row["has_market_value"] = 1.0
                total_market_value += market_value

        preliminary_weights: dict[str, float] = {}
        for symbol, values in aggregated.items():
            raw_weight = float(values["raw_weight"] or 0.0) if values["has_weight"] else None
            market_value = float(values["market_value"] or 0.0) if values["has_market_value"] else None
            if raw_weight is not None and raw_weight > 0:
                preliminary_weights[symbol] = raw_weight
            elif market_value is not None and total_market_value > 0:
                preliminary_weights[symbol] = market_value / total_market_value

        total_weight = sum(preliminary_weights.values())
        normalized_positions = [
            _NormalizedPosition(
                symbol=symbol,
                raw_weight=(float(values["raw_weight"] or 0.0) if values["has_weight"] else None),
                market_value=(float(values["market_value"] or 0.0) if values["has_market_value"] else None),
                effective_weight=self._round(preliminary_weights.get(symbol, 0.0) / total_weight if total_weight > 0 else 0.0),
            )
            for symbol, values in sorted(
                aggregated.items(),
                key=lambda entry: (
                    -(float(entry[1]["market_value"] or 0.0)),
                    -preliminary_weights.get(entry[0], 0.0),
                    entry[0],
                ),
            )
        ]
        return normalized_positions, self._round(total_market_value)

    def _build_scenarios(
        self,
        *,
        positions: Sequence[_NormalizedPosition],
        scenario_shocks: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
        total_market_value: float,
    ) -> list[PortfolioStressRiskScenarioResult]:
        scenarios: list[PortfolioStressRiskScenarioResult] = []
        for index, scenario in enumerate(self._items_from_mapping_or_sequence(scenario_shocks, value_key="shocks")):
            name = self._optional_str(self._field(scenario, "name")) or f"scenario_{index + 1}"
            shocks = self._normalize_symbol_returns(self._field(scenario, "shocks"))
            if not shocks:
                continue

            contributions: list[PortfolioStressRiskPositionContribution] = []
            missing_symbols: list[str] = []
            amount_sum = 0.0
            amount_covered = False
            pct_sum = 0.0
            covered_weight = 0.0
            covered_market_value = 0.0

            for position in positions:
                shock = shocks.get(position.symbol)
                warnings: list[str] = []
                impact_pct: float | None = None
                impact_amount: float | None = None
                if shock is None:
                    missing_symbols.append(position.symbol)
                    warnings.append("missing_scenario_shock")
                else:
                    covered_weight += position.effective_weight
                    impact_pct = self._round(position.effective_weight * shock * 100.0)
                    pct_sum += impact_pct
                    if position.market_value is not None:
                        impact_amount = self._round(position.market_value * shock)
                        amount_sum += impact_amount
                        amount_covered = True
                        covered_market_value += position.market_value

                contributions.append(
                    PortfolioStressRiskPositionContribution(
                        symbol=position.symbol,
                        weight=position.effective_weight,
                        marketValue=self._round(position.market_value) if position.market_value is not None else None,
                        shockPct=self._round(shock * 100.0) if shock is not None else None,
                        impactPct=impact_pct,
                        impactAmount=impact_amount,
                        warnings=warnings,
                    )
                )

            portfolio_impact_amount = self._round(amount_sum) if amount_covered else None
            if total_market_value > 0 and amount_covered:
                portfolio_impact_pct = self._round(amount_sum / total_market_value * 100.0)
            else:
                portfolio_impact_pct = self._round(pct_sum)

            loss_basis = (
                portfolio_impact_amount
                if portfolio_impact_amount is not None and portfolio_impact_amount < 0
                else portfolio_impact_pct
            )
            for item in contributions:
                item.contributionToScenarioLoss = self._loss_contribution(
                    item=item,
                    loss_basis=loss_basis,
                    use_amount=portfolio_impact_amount is not None and portfolio_impact_amount < 0,
                )

            contributions.sort(
                key=lambda item: (
                    item.impactAmount is None and item.impactPct is None,
                    item.impactAmount if item.impactAmount is not None else item.impactPct if item.impactPct is not None else math.inf,
                    item.symbol,
                )
            )
            warnings = ["missing_scenario_shock"] if missing_symbols else []
            scenarios.append(
                PortfolioStressRiskScenarioResult(
                    name=name,
                    portfolioImpactPct=portfolio_impact_pct,
                    portfolioImpactAmount=portfolio_impact_amount,
                    coveredWeight=self._round(covered_weight),
                    coveredMarketValue=self._round(covered_market_value) if amount_covered else None,
                    missingSymbols=sorted(missing_symbols),
                    warnings=warnings,
                    positionContributions=contributions,
                )
            )
        return scenarios

    def _build_historical_var(
        self,
        *,
        positions: Sequence[_NormalizedPosition],
        return_samples: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
        total_market_value: float,
        confidence_level: float,
    ) -> PortfolioStressRiskHistoricalVarSummary:
        normalized_samples: list[tuple[float, float]] = []
        partial_coverage = False

        for sample in self._items_from_mapping_or_sequence(return_samples, value_key="returns"):
            returns = self._normalize_symbol_returns(self._field(sample, "returns"))
            if not returns:
                continue
            covered_weight = 0.0
            pct_sum = 0.0
            amount_sum = 0.0
            amount_covered = False
            for position in positions:
                sample_return = returns.get(position.symbol)
                if sample_return is None:
                    continue
                covered_weight += position.effective_weight
                pct_sum += position.effective_weight * sample_return * 100.0
                if position.market_value is not None:
                    amount_sum += position.market_value * sample_return
                    amount_covered = True
            if covered_weight <= 0:
                continue
            if covered_weight < 0.999999:
                partial_coverage = True
            sample_pct = self._round(amount_sum / total_market_value * 100.0) if total_market_value > 0 and amount_covered else self._round(pct_sum)
            normalized_samples.append((sample_pct, covered_weight))

        sample_count = len(normalized_samples)
        missing_data_warnings = ["partial_return_sample_coverage"] if partial_coverage else []
        insufficient_data_reasons: list[str] = []
        if sample_count < MIN_RETURN_SAMPLE_COUNT:
            insufficient_data_reasons.append("insufficient_return_samples")
            return PortfolioStressRiskHistoricalVarSummary(
                available=False,
                confidenceLevel=self._round(confidence_level),
                sampleCount=sample_count,
                insufficientDataReasons=insufficient_data_reasons,
                missingDataWarnings=missing_data_warnings,
            )

        ordered_returns = sorted(item[0] for item in normalized_samples)
        tail_count = max(1, int(math.ceil((1.0 - confidence_level) * sample_count)))
        tail_slice = ordered_returns[:tail_count]
        var_loss_pct = self._round(max(0.0, -ordered_returns[tail_count - 1]))
        cvar_loss_pct = self._round(max(0.0, -mean(tail_slice)))

        return PortfolioStressRiskHistoricalVarSummary(
            available=True,
            confidenceLevel=self._round(confidence_level),
            sampleCount=sample_count,
            varLossPct=var_loss_pct,
            cvarLossPct=cvar_loss_pct,
            varLossAmount=self._round(total_market_value * var_loss_pct / 100.0) if total_market_value > 0 else None,
            cvarLossAmount=self._round(total_market_value * cvar_loss_pct / 100.0) if total_market_value > 0 else None,
            worstSampleReturnPct=self._round(ordered_returns[0]),
            bestSampleReturnPct=self._round(ordered_returns[-1]),
            insufficientDataReasons=[],
            missingDataWarnings=missing_data_warnings,
        )

    def _build_drawdown_estimate(
        self,
        *,
        scenarios: Sequence[PortfolioStressRiskScenarioResult],
        historical_var: PortfolioStressRiskHistoricalVarSummary,
        total_market_value: float,
    ) -> PortfolioStressRiskDrawdownEstimate:
        worst_scenario: PortfolioStressRiskScenarioResult | None = None
        worst_scenario_loss = 0.0
        for scenario in scenarios:
            scenario_loss = max(0.0, -(scenario.portfolioImpactPct or 0.0))
            if scenario_loss > worst_scenario_loss:
                worst_scenario = scenario
                worst_scenario_loss = scenario_loss

        historical_cvar_loss = float(historical_var.cvarLossPct or 0.0)
        if worst_scenario_loss >= historical_cvar_loss and worst_scenario is not None:
            chosen_loss = worst_scenario_loss
            source = f"scenario_{worst_scenario.name}"
        elif historical_cvar_loss > 0:
            chosen_loss = historical_cvar_loss
            source = "historical_cvar"
        else:
            chosen_loss = 0.0
            source = "unavailable"

        return PortfolioStressRiskDrawdownEstimate(
            lossPct=self._round(chosen_loss),
            lossAmount=self._round(total_market_value * chosen_loss / 100.0) if total_market_value > 0 and chosen_loss > 0 else None,
            source=source,
        )

    def _items_from_mapping_or_sequence(
        self,
        value: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
        *,
        value_key: str,
    ) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, Mapping):
            items: list[Any] = []
            for key, item_value in value.items():
                if isinstance(item_value, Mapping):
                    payload = dict(item_value)
                    payload.setdefault("symbol" if value_key == "weight" else "name", key)
                    items.append(payload)
                else:
                    items.append({"symbol" if value_key == "weight" else "name": key, value_key: item_value})
            return items
        return list(value)

    def _normalize_symbol_returns(self, value: Any) -> dict[str, float]:
        if not isinstance(value, Mapping):
            return {}
        normalized: dict[str, float] = {}
        for symbol, item in value.items():
            normalized_symbol = self._normalize_symbol(symbol)
            normalized_return = self._coerce_return_fraction(item)
            if normalized_symbol and normalized_return is not None:
                normalized[normalized_symbol] = normalized_return
        return normalized

    def _coerce_weight_fraction(self, item: Any) -> float | None:
        explicit_pct = self._coerce_finite_number(self._first_present(item, "weight_pct", "weightPct"))
        if explicit_pct is not None:
            return explicit_pct / 100.0
        raw_weight = self._coerce_finite_number(self._field(item, "weight"))
        if raw_weight is None or raw_weight < 0:
            return None
        return raw_weight / 100.0 if raw_weight > 1.0 else raw_weight

    def _coerce_return_fraction(self, value: Any) -> float | None:
        numeric = self._coerce_finite_number(value)
        if numeric is None:
            return None
        return numeric / 100.0 if abs(numeric) > 1.0 else numeric

    def _coerce_money(self, value: Any) -> float | None:
        numeric = self._coerce_finite_number(value)
        if numeric is None or numeric < 0:
            return None
        return numeric

    def _coerce_finite_number(self, value: Any) -> float | None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(numeric):
            return None
        return numeric

    def _loss_contribution(
        self,
        *,
        item: PortfolioStressRiskPositionContribution,
        loss_basis: float | None,
        use_amount: bool,
    ) -> float | None:
        if loss_basis is None or loss_basis >= 0:
            return None
        numerator = item.impactAmount if use_amount else item.impactPct
        if numerator is None or numerator >= 0:
            return None
        return self._round(abs(numerator) / abs(loss_basis))

    def _field(self, value: Any, key: str) -> Any:
        if isinstance(value, Mapping):
            return value.get(key)
        return getattr(value, key, None)

    def _first_present(self, value: Any, *keys: str) -> Any:
        for key in keys:
            resolved = self._field(value, key)
            if resolved is not None:
                return resolved
        return None

    def _normalize_symbol(self, value: Any) -> str:
        text = str(value or "").strip().upper()
        return text

    def _optional_str(self, value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    def _round(self, value: float) -> float:
        return round(float(value), 4)

    def _unique(self, values: Sequence[str] | Any) -> list[str]:
        result: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in result:
                result.append(text)
        return result


__all__ = [
    "PortfolioStressRiskCoverage",
    "PortfolioStressRiskDrawdownEstimate",
    "PortfolioStressRiskHistoricalVarSummary",
    "PortfolioStressRiskMetadata",
    "PortfolioStressRiskPositionContribution",
    "PortfolioStressRiskReadModel",
    "PortfolioStressRiskScenarioResult",
    "PortfolioStressRiskService",
]
