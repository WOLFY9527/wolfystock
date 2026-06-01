# -*- coding: utf-8 -*-
"""Advisory-only portfolio scenario risk projection helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, Field


class PortfolioScenarioRiskCoverage(BaseModel):
    totalPositions: int = 0
    positionsWithUsableWeight: int = 0
    positionsWithMarketValue: int = 0
    effectiveWeightSum: float = 0.0
    totalMarketValue: float | None = None
    explicitExposureRows: int = 0
    labelsWithExplicitCoverage: list[str] = Field(default_factory=list)


class PortfolioScenarioRiskAppliedShock(BaseModel):
    label: str
    labelType: str = "explicit_label"
    shockPct: float = 0.0
    exposure: float = 1.0
    impactPct: float | None = None
    impactAmount: float | None = None


class PortfolioScenarioRiskPositionContribution(BaseModel):
    symbol: str
    bucket: str | None = None
    weight: float = 0.0
    marketValue: float | None = None
    impactPct: float | None = None
    impactAmount: float | None = None
    contributionToScenarioLoss: float | None = None
    warnings: list[str] = Field(default_factory=list)
    appliedShocks: list[PortfolioScenarioRiskAppliedShock] = Field(default_factory=list)


class PortfolioScenarioRiskBucketContribution(BaseModel):
    bucket: str
    positionCount: int = 0
    impactPct: float | None = None
    impactAmount: float | None = None
    contributionToScenarioLoss: float | None = None


class PortfolioScenarioRiskMissingCoverage(BaseModel):
    label: str
    labelType: str = "explicit_label"
    missingSymbols: list[str] = Field(default_factory=list)


class PortfolioScenarioRiskScenarioResult(BaseModel):
    name: str
    portfolioImpactPct: float = 0.0
    portfolioImpactAmount: float | None = None
    coveredWeight: float = 0.0
    coveredMarketValue: float | None = None
    warnings: list[str] = Field(default_factory=list)
    missingCoverage: list[PortfolioScenarioRiskMissingCoverage] = Field(default_factory=list)
    positionContributions: list[PortfolioScenarioRiskPositionContribution] = Field(default_factory=list)
    bucketContributions: list[PortfolioScenarioRiskBucketContribution] = Field(default_factory=list)


class PortfolioScenarioRiskMetadata(BaseModel):
    deterministic: bool = True
    sideEffectFree: bool = True
    inputSource: str = "caller_supplied_positions_exposures_and_scenarios"
    noLivePrices: bool = True
    noBrokerSync: bool = True
    noAccountingMutation: bool = True
    noOrderPlacement: bool = True
    notInvestmentAdvice: bool = True
    noProviderRuntime: bool = True
    advisoryOnly: bool = True


class PortfolioScenarioRiskReadModel(BaseModel):
    readModelType: str = "portfolio_scenario_risk_advisory_v1"
    advisoryOnly: bool = True
    accountingMutation: bool = False
    brokerIntegration: bool = False
    tradeExecution: bool = False
    executionReadiness: str = "advisory_only_not_trade_execution"
    asOf: str | None = None
    coverage: PortfolioScenarioRiskCoverage = Field(default_factory=PortfolioScenarioRiskCoverage)
    scenarios: list[PortfolioScenarioRiskScenarioResult] = Field(default_factory=list)
    insufficientDataReasons: list[str] = Field(default_factory=list)
    missingDataWarnings: list[str] = Field(default_factory=list)
    metadata: PortfolioScenarioRiskMetadata = Field(default_factory=PortfolioScenarioRiskMetadata)


@dataclass(frozen=True)
class _Position:
    symbol: str
    weight: float
    market_value: float | None
    bucket: str | None


@dataclass(frozen=True)
class _Exposure:
    symbol: str
    label: str
    label_type: str
    exposure: float


class PortfolioScenarioRiskService:
    """Build deterministic advisory-only scenario projections from caller inputs."""

    def build_projection(
        self,
        *,
        positions: Sequence[Mapping[str, Any] | object] | Mapping[str, Any],
        scenario_shocks: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
        exposures: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None = None,
        as_of: str | None = None,
    ) -> PortfolioScenarioRiskReadModel:
        normalized_positions, total_market_value = self._positions(positions)
        normalized_exposures = self._exposures(exposures)
        scenarios = [
            self._scenario_result(
                name=name,
                positions=normalized_positions,
                exposures=normalized_exposures,
                shocks=shocks,
                total_market_value=total_market_value,
            )
            for name, shocks in self._scenario_inputs(scenario_shocks)
        ]

        return PortfolioScenarioRiskReadModel(
            asOf=self._text(as_of),
            coverage=PortfolioScenarioRiskCoverage(
                totalPositions=len(normalized_positions),
                positionsWithUsableWeight=sum(1 for item in normalized_positions if item.weight > 0),
                positionsWithMarketValue=sum(1 for item in normalized_positions if item.market_value is not None),
                effectiveWeightSum=self._round(sum(item.weight for item in normalized_positions)),
                totalMarketValue=self._round(total_market_value) if total_market_value > 0 else None,
                explicitExposureRows=len(normalized_exposures),
                labelsWithExplicitCoverage=sorted({item.label for item in normalized_exposures}),
            ),
            scenarios=scenarios,
            insufficientDataReasons=self._insufficient_reasons(normalized_positions, scenario_shocks, scenarios),
            missingDataWarnings=["scenario_coverage_incomplete"] if any(item.missingCoverage for item in scenarios) else [],
        )

    def _positions(
        self,
        positions: Sequence[Mapping[str, Any] | object] | Mapping[str, Any],
    ) -> tuple[list[_Position], float]:
        rows: dict[str, dict[str, Any]] = {}
        total_market_value = 0.0

        for item in self._items(positions, value_key="weight"):
            symbol = self._key(self._field(item, "symbol"))
            if not symbol:
                continue
            row = rows.setdefault(
                symbol,
                {"weight": 0.0, "has_weight": False, "market_value": 0.0, "has_market_value": False, "bucket": None},
            )
            weight = self._weight(item)
            if weight is not None and weight > 0:
                row["weight"] = float(row["weight"]) + weight
                row["has_weight"] = True
            market_value = self._money(self._first(item, "market_value", "marketValue", "market_value_base"))
            if market_value is not None and market_value > 0:
                row["market_value"] = float(row["market_value"]) + market_value
                row["has_market_value"] = True
                total_market_value += market_value
            bucket = self._text(self._first(item, "bucket", "bucketLabel", "theme", "currency", "factor"))
            if bucket and not row["bucket"]:
                row["bucket"] = bucket

        raw_weights: dict[str, float] = {}
        for symbol, row in rows.items():
            market_value = float(row["market_value"]) if row["has_market_value"] else None
            if row["has_weight"]:
                raw_weights[symbol] = float(row["weight"])
            elif market_value is not None and total_market_value > 0:
                raw_weights[symbol] = market_value / total_market_value

        weight_sum = sum(raw_weights.values())
        normalized = [
            _Position(
                symbol=symbol,
                weight=self._round(raw_weights.get(symbol, 0.0) / weight_sum if weight_sum > 0 else 0.0),
                market_value=self._round(row["market_value"]) if row["has_market_value"] else None,
                bucket=row["bucket"],
            )
            for symbol, row in sorted(
                rows.items(),
                key=lambda entry: (-(float(entry[1]["market_value"] or 0.0)), -raw_weights.get(entry[0], 0.0), entry[0]),
            )
        ]
        return normalized, self._round(total_market_value)

    def _exposures(
        self,
        exposures: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
    ) -> list[_Exposure]:
        merged: dict[tuple[str, str], _Exposure] = {}
        for item in self._exposure_items(exposures):
            symbol = self._key(self._field(item, "symbol"))
            label = self._key(self._first(item, "label", "shock_label", "proxy", "name"))
            if not symbol or not label:
                continue
            exposure = self._number(self._first(item, "exposure", "weight", "coverage"))
            if exposure is None:
                exposure = 1.0
            if exposure < 0:
                continue
            label_type = self._text(self._first(item, "label_type", "labelType", "type")) or "explicit_label"
            existing = merged.get((label, symbol))
            merged[(label, symbol)] = _Exposure(
                symbol=symbol,
                label=label,
                label_type=label_type,
                exposure=self._round((existing.exposure if existing else 0.0) + exposure),
            )
        return sorted(merged.values(), key=lambda item: (item.label, item.symbol))

    def _scenario_result(
        self,
        *,
        name: str,
        positions: Sequence[_Position],
        exposures: Sequence[_Exposure],
        shocks: Mapping[str, tuple[float, str]],
        total_market_value: float,
    ) -> PortfolioScenarioRiskScenarioResult:
        positions_by_symbol = {item.symbol: item for item in positions}
        exposures_by_label: dict[str, list[_Exposure]] = {}
        label_types: dict[str, str] = {}
        for exposure in exposures:
            exposures_by_label.setdefault(exposure.label, []).append(exposure)
            label_types.setdefault(exposure.label, exposure.label_type)

        applied: dict[str, list[PortfolioScenarioRiskAppliedShock]] = {item.symbol: [] for item in positions}
        warnings: dict[str, set[str]] = {item.symbol: set() for item in positions}
        missing_coverage: list[PortfolioScenarioRiskMissingCoverage] = []

        for label, (shock, shock_label_type) in shocks.items():
            if label in positions_by_symbol:
                applied[label].append(self._applied(positions_by_symbol[label], label, "symbol", shock, 1.0))
                continue

            label_exposures = [item for item in exposures_by_label.get(label, []) if item.symbol in positions_by_symbol]
            covered = {item.symbol for item in label_exposures}
            missing = sorted(symbol for symbol in positions_by_symbol if symbol not in covered)
            if missing:
                label_type = label_types.get(label) or shock_label_type
                missing_coverage.append(
                    PortfolioScenarioRiskMissingCoverage(label=label, labelType=label_type, missingSymbols=missing)
                )
                for symbol in missing:
                    warnings[symbol].add("missing_scenario_coverage")
            for exposure in label_exposures:
                applied[exposure.symbol].append(
                    self._applied(
                        positions_by_symbol[exposure.symbol],
                        label,
                        label_types.get(label, exposure.label_type),
                        shock,
                        exposure.exposure,
                    )
                )

        position_rows, amount_sum, pct_sum, covered_weight, covered_market_value = self._position_rows(
            positions,
            applied,
            warnings,
        )
        has_amount = any(item.impactAmount is not None for item in position_rows)
        impact_amount = self._round(amount_sum) if has_amount else None
        impact_pct = (
            self._round(amount_sum / total_market_value * 100.0)
            if total_market_value > 0 and has_amount
            else self._round(pct_sum)
        )
        loss_basis = impact_amount if impact_amount is not None else impact_pct

        for item in position_rows:
            item.contributionToScenarioLoss = self._loss_share(item.impactAmount, item.impactPct, loss_basis, has_amount)

        bucket_rows = self._bucket_rows(position_rows, loss_basis, has_amount)
        position_rows.sort(key=self._position_sort_key)
        bucket_rows.sort(key=self._bucket_sort_key)

        return PortfolioScenarioRiskScenarioResult(
            name=name,
            portfolioImpactPct=impact_pct,
            portfolioImpactAmount=impact_amount,
            coveredWeight=self._round(covered_weight),
            coveredMarketValue=self._round(covered_market_value) if has_amount else None,
            warnings=["missing_scenario_coverage"] if missing_coverage else [],
            missingCoverage=missing_coverage,
            positionContributions=position_rows,
            bucketContributions=bucket_rows,
        )

    def _position_rows(
        self,
        positions: Sequence[_Position],
        applied: Mapping[str, Sequence[PortfolioScenarioRiskAppliedShock]],
        warnings: Mapping[str, set[str]],
    ) -> tuple[list[PortfolioScenarioRiskPositionContribution], float, float, float, float]:
        rows: list[PortfolioScenarioRiskPositionContribution] = []
        amount_sum = 0.0
        pct_sum = 0.0
        covered_weight = 0.0
        covered_market_value = 0.0

        for position in positions:
            shocks = list(applied[position.symbol])
            impact_pct = self._sum(item.impactPct for item in shocks)
            impact_amount = self._sum(item.impactAmount for item in shocks)
            if shocks:
                covered_weight += position.weight
                pct_sum += impact_pct or 0.0
                amount_sum += impact_amount or 0.0
                if position.market_value is not None:
                    covered_market_value += position.market_value
            rows.append(
                PortfolioScenarioRiskPositionContribution(
                    symbol=position.symbol,
                    bucket=position.bucket,
                    weight=position.weight,
                    marketValue=position.market_value,
                    impactPct=impact_pct,
                    impactAmount=impact_amount,
                    warnings=sorted(warnings[position.symbol]),
                    appliedShocks=shocks,
                )
            )
        return rows, amount_sum, pct_sum, covered_weight, covered_market_value

    def _bucket_rows(
        self,
        positions: Sequence[PortfolioScenarioRiskPositionContribution],
        loss_basis: float | None,
        use_amount: bool,
    ) -> list[PortfolioScenarioRiskBucketContribution]:
        grouped: dict[str, dict[str, float | int | bool]] = {}
        for position in positions:
            if not position.bucket or (position.impactPct is None and position.impactAmount is None):
                continue
            row = grouped.setdefault(position.bucket, {"count": 0, "pct": 0.0, "amount": 0.0, "has_amount": False})
            row["count"] = int(row["count"]) + 1
            row["pct"] = float(row["pct"]) + float(position.impactPct or 0.0)
            if position.impactAmount is not None:
                row["amount"] = float(row["amount"]) + position.impactAmount
                row["has_amount"] = True

        rows = []
        for bucket, values in grouped.items():
            impact_pct = self._round(float(values["pct"]))
            impact_amount = self._round(float(values["amount"])) if values["has_amount"] else None
            rows.append(
                PortfolioScenarioRiskBucketContribution(
                    bucket=bucket,
                    positionCount=int(values["count"]),
                    impactPct=impact_pct,
                    impactAmount=impact_amount,
                    contributionToScenarioLoss=self._loss_share(impact_amount, impact_pct, loss_basis, use_amount),
                )
            )
        return rows

    def _applied(
        self,
        position: _Position,
        label: str,
        label_type: str,
        shock: float,
        exposure: float,
    ) -> PortfolioScenarioRiskAppliedShock:
        return PortfolioScenarioRiskAppliedShock(
            label=label,
            labelType=label_type,
            shockPct=self._round(shock * 100.0),
            exposure=self._round(exposure),
            impactPct=self._round(position.weight * shock * exposure * 100.0),
            impactAmount=self._round(position.market_value * shock * exposure) if position.market_value is not None else None,
        )

    def _scenario_inputs(
        self,
        scenario_shocks: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
    ) -> list[tuple[str, dict[str, tuple[float, str]]]]:
        scenarios = []
        for index, item in enumerate(self._items(scenario_shocks, value_key="shocks")):
            shocks = self._shocks(self._field(item, "shocks"))
            if shocks:
                scenarios.append((self._text(self._field(item, "name")) or f"scenario_{index + 1}", shocks))
        return scenarios

    def _shocks(self, value: Any) -> dict[str, tuple[float, str]]:
        if not isinstance(value, Mapping):
            return {}
        shocks: dict[str, tuple[float, str]] = {}
        for raw_label, raw_value in value.items():
            label = self._key(raw_label)
            label_type = "explicit_label"
            shock_value = raw_value
            if isinstance(raw_value, Mapping):
                shock_value = self._first(raw_value, "shock", "shock_pct", "shockPct", "return")
                label_type = self._text(self._first(raw_value, "label_type", "labelType", "type")) or label_type
            shock = self._return_fraction(shock_value)
            if label and shock is not None:
                shocks[label] = (shock, label_type)
        return shocks

    def _items(
        self,
        value: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
        *,
        value_key: str,
    ) -> list[Any]:
        if value is None:
            return []
        if not isinstance(value, Mapping):
            return list(value)
        if value_key in value:
            return [value]
        key_name = "symbol" if value_key == "weight" else "name"
        return [
            ({**item, key_name: key} if isinstance(item, Mapping) else {key_name: key, value_key: item})
            for key, item in value.items()
        ]

    def _exposure_items(self, value: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None) -> list[Any]:
        if value is None or not isinstance(value, Mapping):
            return list(value or [])
        items: list[Any] = []
        for label, covered in value.items():
            if isinstance(covered, Mapping) and isinstance(covered.get("symbols"), Sequence):
                for symbol in covered["symbols"]:
                    items.append(
                        {
                            "label": label,
                            "symbol": symbol,
                            "exposure": covered.get("exposure", 1.0),
                            "label_type": covered.get("label_type") or covered.get("labelType"),
                        }
                    )
            elif isinstance(covered, Sequence) and not isinstance(covered, (str, bytes, bytearray)):
                items.extend({"label": label, "symbol": symbol, "exposure": 1.0} for symbol in covered)
            elif isinstance(covered, Mapping):
                items.append({**covered, "label": label})
            else:
                items.append({"label": label, "symbol": covered, "exposure": 1.0})
        return items

    def _insufficient_reasons(
        self,
        positions: Sequence[_Position],
        scenario_shocks: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
        scenarios: Sequence[PortfolioScenarioRiskScenarioResult],
    ) -> list[str]:
        reasons = []
        if not positions:
            reasons.append("no_positions")
        if scenario_shocks and not scenarios:
            reasons.append("no_usable_scenario_shocks")
        return reasons

    def _weight(self, item: Any) -> float | None:
        explicit_pct = self._number(self._first(item, "weight_pct", "weightPct"))
        if explicit_pct is not None:
            return explicit_pct / 100.0
        weight = self._number(self._field(item, "weight"))
        if weight is None or weight < 0:
            return None
        return weight / 100.0 if weight > 1.0 else weight

    def _money(self, value: Any) -> float | None:
        number = self._number(value)
        return number if number is not None and number >= 0 else None

    def _return_fraction(self, value: Any) -> float | None:
        number = self._number(value)
        if number is None:
            return None
        return number / 100.0 if abs(number) > 1.0 else number

    def _number(self, value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    def _sum(self, values: Any) -> float | None:
        present = [float(value) for value in values if value is not None]
        return self._round(sum(present)) if present else None

    def _loss_share(self, impact_amount: float | None, impact_pct: float | None, loss_basis: float | None, use_amount: bool) -> float | None:
        numerator = impact_amount if use_amount else impact_pct
        if loss_basis is None or loss_basis >= 0 or numerator is None or numerator >= 0:
            return None
        return self._round(abs(numerator) / abs(loss_basis))

    def _position_sort_key(self, item: PortfolioScenarioRiskPositionContribution) -> tuple[bool, float, str]:
        impact = item.impactAmount if item.impactAmount is not None else item.impactPct
        return (impact is None, impact if impact is not None else 0.0, item.symbol)

    def _bucket_sort_key(self, item: PortfolioScenarioRiskBucketContribution) -> tuple[bool, float, str]:
        impact = item.impactAmount if item.impactAmount is not None else item.impactPct
        return (impact is None, impact if impact is not None else 0.0, item.bucket)

    def _field(self, value: Any, key: str) -> Any:
        if isinstance(value, Mapping):
            return value.get(key)
        return getattr(value, key, None)

    def _first(self, value: Any, *keys: str) -> Any:
        for key in keys:
            item = self._field(value, key)
            if item is not None:
                return item
        return None

    def _key(self, value: Any) -> str:
        return str(value or "").strip().upper()

    def _text(self, value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    def _round(self, value: float) -> float:
        return round(float(value), 4)


__all__ = [
    "PortfolioScenarioRiskAppliedShock",
    "PortfolioScenarioRiskBucketContribution",
    "PortfolioScenarioRiskCoverage",
    "PortfolioScenarioRiskMetadata",
    "PortfolioScenarioRiskMissingCoverage",
    "PortfolioScenarioRiskPositionContribution",
    "PortfolioScenarioRiskReadModel",
    "PortfolioScenarioRiskScenarioResult",
    "PortfolioScenarioRiskService",
]
