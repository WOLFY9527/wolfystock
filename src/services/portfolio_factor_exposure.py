# -*- coding: utf-8 -*-
"""Advisory-only portfolio factor exposure projection helpers."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

from pydantic import BaseModel, Field

from api.v1.schemas.factors import FactorObservation
from src.services.factor_exposure import (
    FactorExposureWindow,
    build_factor_exposure_report,
)


class PortfolioFactorExposureWindow(BaseModel):
    as_of_start: str | None = None
    as_of_end: str | None = None
    as_of_count: int = 0
    observation_count: int = 0


class PortfolioFactorExposureCoverage(BaseModel):
    totalPositions: int = 0
    eligiblePositions: int = 0
    invalidWeightCount: int = 0
    zeroWeightCount: int = 0
    grossWeight: float = 0.0
    netWeight: float = 0.0


class PortfolioFactorExposureFactorReadModel(BaseModel):
    factorId: str
    exposure: float | None = None
    weightedExposure: float = 0.0
    grossExposure: float = 0.0
    netExposure: float = 0.0
    coverage: float = 0.0
    missingFactorCount: int = 0
    warnings: tuple[str, ...] = ()
    asOf: str | None = None
    window: PortfolioFactorExposureWindow = Field(default_factory=PortfolioFactorExposureWindow)


class PortfolioFactorExposureReadModel(BaseModel):
    readModelType: str = "portfolio_factor_exposure_advisory_v1"
    advisoryOnly: bool = True
    accountingMutation: bool = False
    brokerIntegration: bool = False
    tradeExecution: bool = False
    asOf: str | None = None
    window: PortfolioFactorExposureWindow = Field(default_factory=PortfolioFactorExposureWindow)
    coverage: PortfolioFactorExposureCoverage = Field(default_factory=PortfolioFactorExposureCoverage)
    warnings: tuple[str, ...] = ()
    exposuresByFactorId: Dict[str, PortfolioFactorExposureFactorReadModel] = Field(default_factory=dict)


class PortfolioFactorExposureService:
    """Build a deterministic read-only portfolio factor exposure projection."""

    def build_projection(
        self,
        *,
        snapshot: Mapping[str, Any],
        position_weights: Sequence[Mapping[str, Any] | object] | Mapping[str, Any],
        observations: Sequence[FactorObservation | Mapping[str, Any] | object],
    ) -> PortfolioFactorExposureReadModel:
        report = build_factor_exposure_report(
            observations=observations,
            weights=position_weights,
            scope="portfolio_factor_exposure",
        )
        exposures_by_factor_id = {
            item.factor_id: PortfolioFactorExposureFactorReadModel(
                factorId=item.factor_id,
                exposure=item.exposure,
                weightedExposure=item.weighted_exposure,
                grossExposure=item.gross_exposure,
                netExposure=item.net_exposure,
                coverage=item.coverage,
                missingFactorCount=item.missing_factor_count,
                warnings=item.warnings,
                asOf=item.window.as_of_end,
                window=self._window_model(item.window),
            )
            for item in report.factors
        }
        return PortfolioFactorExposureReadModel(
            asOf=self._optional_str(snapshot.get("as_of")),
            window=self._merge_windows([item.window for item in report.factors]),
            coverage=PortfolioFactorExposureCoverage(
                totalPositions=report.coverage.total_positions,
                eligiblePositions=report.coverage.eligible_positions,
                invalidWeightCount=report.coverage.invalid_weight_count,
                zeroWeightCount=report.coverage.zero_weight_count,
                grossWeight=report.coverage.gross_weight,
                netWeight=report.coverage.net_weight,
            ),
            warnings=report.warnings,
            exposuresByFactorId=exposures_by_factor_id,
        )

    def _merge_windows(self, windows: Sequence[FactorExposureWindow]) -> PortfolioFactorExposureWindow:
        as_ofs = sorted(
            {
                value
                for window in windows
                for value in (window.as_of_start, window.as_of_end)
                if value
            }
        )
        return PortfolioFactorExposureWindow(
            as_of_start=as_ofs[0] if as_ofs else None,
            as_of_end=as_ofs[-1] if as_ofs else None,
            as_of_count=max((window.as_of_count for window in windows), default=0),
            observation_count=sum(window.observation_count for window in windows),
        )

    def _window_model(self, window: FactorExposureWindow) -> PortfolioFactorExposureWindow:
        return PortfolioFactorExposureWindow(
            as_of_start=window.as_of_start,
            as_of_end=window.as_of_end,
            as_of_count=window.as_of_count,
            observation_count=window.observation_count,
        )

    def _optional_str(self, value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None


__all__ = [
    "PortfolioFactorExposureCoverage",
    "PortfolioFactorExposureFactorReadModel",
    "PortfolioFactorExposureReadModel",
    "PortfolioFactorExposureService",
    "PortfolioFactorExposureWindow",
]
