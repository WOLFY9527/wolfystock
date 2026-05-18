# -*- coding: utf-8 -*-
"""Advisory-only portfolio risk attribution projection helpers."""

from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Sequence

from pydantic import BaseModel, Field


class PortfolioRiskAttributionEvidenceMetadata(BaseModel):
    snapshotSource: str = "read_only_snapshot"
    asOf: str | None = None
    deterministic: bool = True
    sideEffectFree: bool = True
    advisoryOnly: bool = True
    accountingMutation: bool = False
    brokerIntegration: bool = False
    tradeExecution: bool = False


class PortfolioRiskAttributionMetadata(BaseModel):
    evidence: PortfolioRiskAttributionEvidenceMetadata = Field(
        default_factory=PortfolioRiskAttributionEvidenceMetadata
    )


class PortfolioRiskAttributionCoverage(BaseModel):
    totalPositions: int = 0
    eligiblePositions: int = 0
    invalidWeightCount: int = 0
    zeroWeightCount: int = 0
    grossWeight: float = 0.0
    netWeight: float = 0.0
    totalMarketValue: float = 0.0
    marketValueCount: int = 0
    missingMarketValueCount: int = 0
    sectorCount: int = 0
    missingSectorCount: int = 0
    industryCount: int = 0
    missingIndustryCount: int = 0
    positionRiskMetricCount: int = 0
    missingPositionRiskMetricCount: int = 0
    invalidPositionRiskMetricCount: int = 0
    positionsWithAnyFactorExposureCount: int = 0
    factorCoverageById: Dict[str, int] = Field(default_factory=dict)


class PortfolioRiskAttributionPositionReadModel(BaseModel):
    symbol: str
    weight: float
    weightPct: float
    marketValue: float = 0.0
    marketValueWeightPct: float = 0.0
    sector: str = "UNCLASSIFIED"
    industry: str = "UNCLASSIFIED"
    concentrationContribution: float = 0.0
    specificRiskContribution: float = 0.0
    factorContribution: float = 0.0
    totalContribution: float = 0.0
    contributionPct: float = 0.0
    warnings: tuple[str, ...] = ()


class PortfolioRiskAttributionGroupReadModel(BaseModel):
    label: str
    positionCount: int = 0
    weight: float = 0.0
    weightPct: float = 0.0
    marketValue: float = 0.0
    marketValueWeightPct: float = 0.0
    totalContribution: float = 0.0
    contributionPct: float = 0.0


class PortfolioRiskAttributionFactorReadModel(BaseModel):
    factorId: str
    weightedExposure: float = 0.0
    factorRisk: float = 1.0
    contribution: float = 0.0
    contributionPct: float = 0.0
    coveredPositionCount: int = 0
    missingPositionCount: int = 0
    warnings: tuple[str, ...] = ()


class PortfolioRiskContributionSummary(BaseModel):
    symbol: str
    sector: str = "UNCLASSIFIED"
    industry: str = "UNCLASSIFIED"
    totalContribution: float = 0.0
    contributionPct: float = 0.0
    dominantComponent: str = "concentration"


class PortfolioRiskAttributionConcentrationReadModel(BaseModel):
    hhi: float = 0.0
    effectivePositionCount: float = 0.0
    contribution: float = 0.0
    contributionPct: float = 0.0
    topPositions: list[PortfolioRiskContributionSummary] = Field(default_factory=list)


class PortfolioRiskAttributionReadModel(BaseModel):
    readModelType: str = "portfolio_risk_attribution_advisory_v1"
    asOf: str | None = None
    currency: str = "CNY"
    advisoryOnly: bool = True
    accountingMutation: bool = False
    brokerIntegration: bool = False
    tradeExecution: bool = False
    executionReadiness: str = "advisory_only_not_trade_execution"
    coverage: PortfolioRiskAttributionCoverage = Field(default_factory=PortfolioRiskAttributionCoverage)
    warnings: tuple[str, ...] = ()
    byPosition: list[PortfolioRiskAttributionPositionReadModel] = Field(default_factory=list)
    bySector: list[PortfolioRiskAttributionGroupReadModel] = Field(default_factory=list)
    byIndustry: list[PortfolioRiskAttributionGroupReadModel] = Field(default_factory=list)
    byFactorId: Dict[str, PortfolioRiskAttributionFactorReadModel] = Field(default_factory=dict)
    concentrationContribution: PortfolioRiskAttributionConcentrationReadModel = Field(
        default_factory=PortfolioRiskAttributionConcentrationReadModel
    )
    topRiskContributors: list[PortfolioRiskContributionSummary] = Field(default_factory=list)
    metadata: PortfolioRiskAttributionMetadata = Field(default_factory=PortfolioRiskAttributionMetadata)


class PortfolioRiskAttributionService:
    """Build a deterministic read-only portfolio risk attribution projection."""

    def build_projection(
        self,
        *,
        snapshot: Mapping[str, Any],
        position_weights: Sequence[Mapping[str, Any] | object] | Mapping[str, Any],
        position_market_values: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None = None,
        classifications: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None = None,
        factor_exposures: Sequence[Mapping[str, Any] | object] | None = None,
        risk_metrics: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None = None,
        top_n: int = 10,
    ) -> PortfolioRiskAttributionReadModel:
        normalized_weights, counts = self._normalize_weights(position_weights)
        market_values = self._normalize_number_map(position_market_values, "market_value")
        class_index = self._normalize_classifications(classifications)
        risk_index, invalid_risk_metric_count = self._normalize_number_map_with_invalid_count(
            risk_metrics,
            "risk_metric",
        )
        factor_index, factor_risk_index, factor_warnings = self._normalize_factor_exposures(factor_exposures)

        total_market_value = sum(market_values.get(symbol, 0.0) for symbol in normalized_weights)
        factor_ids = sorted(factor_index)
        symbols_with_any_factor = {
            symbol
            for exposures in factor_index.values()
            for symbol in exposures
            if symbol in normalized_weights
        }

        position_rows: list[PortfolioRiskAttributionPositionReadModel] = []
        market_value_count = 0
        sector_count = 0
        industry_count = 0
        position_risk_metric_count = 0

        for symbol in sorted(normalized_weights):
            weight = normalized_weights[symbol]
            market_value = market_values.get(symbol, 0.0)
            if symbol in market_values:
                market_value_count += 1
            classification = class_index.get(symbol, {})
            sector = classification.get("sector") or "UNCLASSIFIED"
            industry = classification.get("industry") or "UNCLASSIFIED"
            if sector != "UNCLASSIFIED":
                sector_count += 1
            if industry != "UNCLASSIFIED":
                industry_count += 1
            risk_metric = risk_index.get(symbol)
            if risk_metric is not None:
                position_risk_metric_count += 1

            concentration_contribution = weight * weight
            specific_risk_contribution = weight * risk_metric if risk_metric is not None else 0.0
            factor_contribution = 0.0
            for factor_id in factor_ids:
                factor_value = factor_index.get(factor_id, {}).get(symbol)
                if factor_value is None:
                    continue
                factor_risk = factor_risk_index.get(factor_id, 1.0)
                factor_contribution += weight * abs(factor_value) * factor_risk

            warnings = []
            if symbol not in market_values:
                warnings.append("missing_market_value")
            if sector == "UNCLASSIFIED":
                warnings.append("missing_sector")
            if industry == "UNCLASSIFIED":
                warnings.append("missing_industry")
            if risk_metric is None:
                warnings.append("missing_position_risk_metric")
            if factor_ids and symbol not in symbols_with_any_factor:
                warnings.append("missing_factor_exposure")

            position_rows.append(
                PortfolioRiskAttributionPositionReadModel(
                    symbol=symbol,
                    weight=self._round(weight),
                    weightPct=self._round_pct(weight * 100.0),
                    marketValue=self._round(market_value),
                    marketValueWeightPct=self._round_pct(
                        (market_value / total_market_value * 100.0) if total_market_value > 0 else 0.0
                    ),
                    sector=sector,
                    industry=industry,
                    concentrationContribution=self._round(concentration_contribution),
                    specificRiskContribution=self._round(specific_risk_contribution),
                    factorContribution=self._round(factor_contribution),
                    totalContribution=self._round(
                        concentration_contribution + specific_risk_contribution + factor_contribution
                    ),
                    warnings=tuple(warnings),
                )
            )

        total_contribution = sum(item.totalContribution for item in position_rows)
        for item in position_rows:
            item.contributionPct = self._round_pct(
                (item.totalContribution / total_contribution * 100.0) if total_contribution > 0 else 0.0
            )
        position_rows.sort(
            key=lambda item: (
                -float(item.totalContribution),
                -float(item.marketValue),
                item.symbol,
            )
        )

        factor_rows = self._build_factor_rows(
            factor_ids=factor_ids,
            factor_index=factor_index,
            factor_risk_index=factor_risk_index,
            factor_warnings=factor_warnings,
            normalized_weights=normalized_weights,
            total_contribution=total_contribution,
        )
        by_sector = self._build_group_rows(
            position_rows,
            group_key="sector",
            total_market_value=total_market_value,
            total_contribution=total_contribution,
        )
        by_industry = self._build_group_rows(
            position_rows,
            group_key="industry",
            total_market_value=total_market_value,
            total_contribution=total_contribution,
        )

        top_risk_contributors = [
            PortfolioRiskContributionSummary(
                symbol=item.symbol,
                sector=item.sector,
                industry=item.industry,
                totalContribution=item.totalContribution,
                contributionPct=item.contributionPct,
                dominantComponent=self._dominant_component(item),
            )
            for item in position_rows[: max(top_n, 0)]
        ]

        concentration_total = sum(item.concentrationContribution for item in position_rows)
        concentration = PortfolioRiskAttributionConcentrationReadModel(
            hhi=self._round(concentration_total),
            effectivePositionCount=self._round(
                (1.0 / concentration_total) if concentration_total > 0 else 0.0,
                digits=4,
            ),
            contribution=self._round(concentration_total),
            contributionPct=self._round_pct(
                (concentration_total / total_contribution * 100.0) if total_contribution > 0 else 0.0
            ),
            topPositions=top_risk_contributors[: max(top_n, 0)],
        )

        missing_market_value_count = max(len(normalized_weights) - market_value_count, 0)
        missing_sector_count = max(len(normalized_weights) - sector_count, 0)
        missing_industry_count = max(len(normalized_weights) - industry_count, 0)
        missing_position_risk_metric_count = max(len(normalized_weights) - position_risk_metric_count, 0)
        coverage = PortfolioRiskAttributionCoverage(
            totalPositions=counts["total_positions"],
            eligiblePositions=len(normalized_weights),
            invalidWeightCount=counts["invalid_weight_count"],
            zeroWeightCount=counts["zero_weight_count"],
            grossWeight=self._round(sum(normalized_weights.values())),
            netWeight=self._round(sum(normalized_weights.values())),
            totalMarketValue=self._round(total_market_value),
            marketValueCount=market_value_count,
            missingMarketValueCount=missing_market_value_count,
            sectorCount=sector_count,
            missingSectorCount=missing_sector_count,
            industryCount=industry_count,
            missingIndustryCount=missing_industry_count,
            positionRiskMetricCount=position_risk_metric_count,
            missingPositionRiskMetricCount=missing_position_risk_metric_count,
            invalidPositionRiskMetricCount=invalid_risk_metric_count,
            positionsWithAnyFactorExposureCount=len(symbols_with_any_factor),
            factorCoverageById={
                factor_id: sum(1 for symbol in normalized_weights if symbol in factor_index.get(factor_id, {}))
                for factor_id in factor_ids
            },
        )

        warnings = []
        if counts["invalid_weight_count"]:
            warnings.append("invalid_weight")
        if counts["zero_weight_count"]:
            warnings.append("zero_weight")
        if missing_market_value_count:
            warnings.append("missing_market_value")
        if missing_sector_count:
            warnings.append("missing_sector")
        if missing_position_risk_metric_count:
            warnings.append("missing_position_risk_metric")
        if factor_ids and len(symbols_with_any_factor) < len(normalized_weights):
            warnings.append("missing_factor_exposure")
        if invalid_risk_metric_count:
            warnings.append("invalid_position_risk_metric")
        warnings.extend(
            warning
            for warning in ("invalid_factor_exposure", "invalid_factor_risk")
            if factor_warnings.get(warning, 0) > 0
        )

        return PortfolioRiskAttributionReadModel(
            asOf=self._optional_text(snapshot.get("as_of")),
            currency=self._optional_text(snapshot.get("currency")) or "CNY",
            coverage=coverage,
            warnings=tuple(warnings),
            byPosition=position_rows,
            bySector=by_sector,
            byIndustry=by_industry,
            byFactorId=factor_rows,
            concentrationContribution=concentration,
            topRiskContributors=top_risk_contributors,
            metadata=PortfolioRiskAttributionMetadata(
                evidence=PortfolioRiskAttributionEvidenceMetadata(
                    snapshotSource="read_only_snapshot",
                    asOf=self._optional_text(snapshot.get("as_of")),
                )
            ),
        )

    def _build_factor_rows(
        self,
        *,
        factor_ids: list[str],
        factor_index: dict[str, dict[str, float]],
        factor_risk_index: dict[str, float],
        factor_warnings: dict[str, dict[str, int]],
        normalized_weights: dict[str, float],
        total_contribution: float,
    ) -> Dict[str, PortfolioRiskAttributionFactorReadModel]:
        rows: Dict[str, PortfolioRiskAttributionFactorReadModel] = {}
        eligible_positions = len(normalized_weights)
        for factor_id in factor_ids:
            covered_position_count = 0
            weighted_exposure = 0.0
            contribution = 0.0
            factor_risk = factor_risk_index.get(factor_id, 1.0)
            for symbol in sorted(normalized_weights):
                exposure = factor_index.get(factor_id, {}).get(symbol)
                if exposure is None:
                    continue
                covered_position_count += 1
                weight = normalized_weights[symbol]
                weighted_exposure += weight * exposure
                contribution += weight * abs(exposure) * factor_risk

            warnings = []
            if covered_position_count < eligible_positions:
                warnings.append("missing_factor_exposure")
            if factor_warnings.get(factor_id, {}).get("invalid_factor_exposure", 0) > 0:
                warnings.append("invalid_factor_exposure")
            if factor_warnings.get(factor_id, {}).get("invalid_factor_risk", 0) > 0:
                warnings.append("invalid_factor_risk")

            rows[factor_id] = PortfolioRiskAttributionFactorReadModel(
                factorId=factor_id,
                weightedExposure=self._round(weighted_exposure),
                factorRisk=self._round(factor_risk),
                contribution=self._round(contribution),
                contributionPct=self._round_pct(
                    (contribution / total_contribution * 100.0) if total_contribution > 0 else 0.0
                ),
                coveredPositionCount=covered_position_count,
                missingPositionCount=max(eligible_positions - covered_position_count, 0),
                warnings=tuple(warnings),
            )
        return rows

    def _build_group_rows(
        self,
        rows: Sequence[PortfolioRiskAttributionPositionReadModel],
        *,
        group_key: str,
        total_market_value: float,
        total_contribution: float,
    ) -> list[PortfolioRiskAttributionGroupReadModel]:
        grouped: dict[str, dict[str, float]] = {}
        for item in rows:
            label = getattr(item, group_key)
            bucket = grouped.setdefault(
                label,
                {
                    "position_count": 0,
                    "weight": 0.0,
                    "market_value": 0.0,
                    "total_contribution": 0.0,
                },
            )
            bucket["position_count"] += 1
            bucket["weight"] += float(item.weight)
            bucket["market_value"] += float(item.marketValue)
            bucket["total_contribution"] += float(item.totalContribution)

        results = [
            PortfolioRiskAttributionGroupReadModel(
                label=label,
                positionCount=int(bucket["position_count"]),
                weight=self._round(bucket["weight"]),
                weightPct=self._round_pct(bucket["weight"] * 100.0),
                marketValue=self._round(bucket["market_value"]),
                marketValueWeightPct=self._round_pct(
                    (bucket["market_value"] / total_market_value * 100.0) if total_market_value > 0 else 0.0
                ),
                totalContribution=self._round(bucket["total_contribution"]),
                contributionPct=self._round_pct(
                    (bucket["total_contribution"] / total_contribution * 100.0) if total_contribution > 0 else 0.0
                ),
            )
            for label, bucket in grouped.items()
        ]
        results.sort(
            key=lambda item: (
                -float(item.totalContribution),
                -float(item.marketValue),
                item.label,
            )
        )
        return results

    def _normalize_weights(
        self,
        values: Sequence[Mapping[str, Any] | object] | Mapping[str, Any],
    ) -> tuple[dict[str, float], dict[str, int]]:
        totals: dict[str, float] = {}
        invalid_weight_count = 0
        zero_weight_count = 0
        total_positions = 0
        for item in self._iter_symbol_keyed_items(values, "weight"):
            total_positions += 1
            symbol = self._normalize_symbol(self._field(item, "symbol"))
            weight = self._coerce_non_negative_number(self._field(item, "weight"))
            if not symbol or weight is None:
                invalid_weight_count += 1
                continue
            if math.isclose(weight, 0.0, abs_tol=1e-12):
                zero_weight_count += 1
                continue
            totals[symbol] = totals.get(symbol, 0.0) + weight
        return totals, {
            "total_positions": total_positions,
            "invalid_weight_count": invalid_weight_count,
            "zero_weight_count": zero_weight_count,
        }

    def _normalize_classifications(
        self,
        values: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
    ) -> dict[str, dict[str, str]]:
        index: dict[str, dict[str, str]] = {}
        for item in self._iter_symbol_keyed_items(values, None):
            symbol = self._normalize_symbol(self._field(item, "symbol"))
            if not symbol:
                continue
            index[symbol] = {
                "sector": self._optional_text(self._field(item, "sector")) or "UNCLASSIFIED",
                "industry": self._optional_text(self._field(item, "industry")) or "UNCLASSIFIED",
            }
        return index

    def _normalize_factor_exposures(
        self,
        values: Sequence[Mapping[str, Any] | object] | None,
    ) -> tuple[dict[str, dict[str, float]], dict[str, float], dict[str, dict[str, int]]]:
        index: dict[str, dict[str, float]] = {}
        factor_risk_values: dict[str, list[float]] = {}
        warnings: dict[str, dict[str, int]] = {}
        for item in values or ():
            factor_id = self._optional_text(self._field(item, "factor_id"))
            symbol = self._normalize_symbol(self._field(item, "symbol"))
            if not factor_id or not symbol:
                continue
            factor_warning_bucket = warnings.setdefault(
                factor_id,
                {"invalid_factor_exposure": 0, "invalid_factor_risk": 0},
            )
            exposure = self._coerce_number(self._field(item, "exposure"))
            if exposure is None:
                factor_warning_bucket["invalid_factor_exposure"] += 1
                continue
            factor_risk = self._coerce_non_negative_number(self._field(item, "factor_risk"))
            if self._field(item, "factor_risk") is not None and factor_risk is None:
                factor_warning_bucket["invalid_factor_risk"] += 1
            index.setdefault(factor_id, {})[symbol] = exposure
            if factor_risk is not None:
                factor_risk_values.setdefault(factor_id, []).append(factor_risk)

        factor_risk_index = {
            factor_id: self._round(sum(values) / len(values))
            for factor_id, values in sorted(factor_risk_values.items())
            if values
        }
        return index, factor_risk_index, warnings

    def _normalize_number_map(
        self,
        values: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
        field_name: str,
    ) -> dict[str, float]:
        index, _ = self._normalize_number_map_with_invalid_count(values, field_name)
        return index

    def _normalize_number_map_with_invalid_count(
        self,
        values: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
        field_name: str,
    ) -> tuple[dict[str, float], int]:
        index: dict[str, float] = {}
        invalid_count = 0
        for item in self._iter_symbol_keyed_items(values, field_name):
            symbol = self._normalize_symbol(self._field(item, "symbol"))
            if not symbol:
                continue
            value = self._coerce_non_negative_number(self._field(item, field_name))
            if value is None:
                if self._field(item, field_name) is not None:
                    invalid_count += 1
                continue
            index[symbol] = value
        return index, invalid_count

    def _iter_symbol_keyed_items(
        self,
        values: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
        value_field: str | None,
    ) -> Sequence[Any]:
        if values is None:
            return ()
        if isinstance(values, Mapping):
            items = []
            for symbol, raw_value in values.items():
                if isinstance(raw_value, Mapping):
                    row = {"symbol": symbol}
                    row.update(dict(raw_value))
                else:
                    row = {"symbol": symbol}
                    if value_field:
                        row[value_field] = raw_value
                items.append(row)
            return items
        return list(values)

    @staticmethod
    def _field(value: Mapping[str, Any] | object, name: str) -> Any:
        if isinstance(value, Mapping):
            return value.get(name)
        return getattr(value, name, None)

    @staticmethod
    def _normalize_symbol(value: Any) -> str:
        text = str(value or "").strip().upper()
        return text

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _coerce_number(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number):
            return None
        return number

    def _coerce_non_negative_number(self, value: Any) -> float | None:
        number = self._coerce_number(value)
        if number is None or number < 0:
            return None
        return number

    @staticmethod
    def _round(value: float, *, digits: int = 6) -> float:
        return round(float(value), digits)

    @staticmethod
    def _round_pct(value: float) -> float:
        return round(float(value), 4)

    @staticmethod
    def _dominant_component(item: PortfolioRiskAttributionPositionReadModel) -> str:
        ranked = [
            ("factor", float(item.factorContribution)),
            ("specific_risk", float(item.specificRiskContribution)),
            ("concentration", float(item.concentrationContribution)),
        ]
        ranked.sort(key=lambda pair: (-pair[1], pair[0]))
        return ranked[0][0]


__all__ = [
    "PortfolioRiskAttributionConcentrationReadModel",
    "PortfolioRiskAttributionCoverage",
    "PortfolioRiskAttributionEvidenceMetadata",
    "PortfolioRiskAttributionFactorReadModel",
    "PortfolioRiskAttributionGroupReadModel",
    "PortfolioRiskAttributionMetadata",
    "PortfolioRiskAttributionPositionReadModel",
    "PortfolioRiskAttributionReadModel",
    "PortfolioRiskAttributionService",
    "PortfolioRiskContributionSummary",
]
