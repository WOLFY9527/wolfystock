# -*- coding: utf-8 -*-
"""Schemas for the pure leveraged ETF mapper endpoint."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


ReferenceType = Literal["single_stock", "proxy_etf"]
CalculationStatus = Literal["ok", "invalid_low_confidence"]


class LeveragedEtfMappingItem(BaseModel):
    etfSymbol: str
    underlyingSymbol: str
    leverage: float = Field(gt=0)
    referenceType: ReferenceType
    sourceLabel: str
    effectiveLabel: str
    notes: list[str] = Field(default_factory=list)


class LeveragedEtfMapperMetadata(BaseModel):
    contractVersion: str = "leveraged_etf_mapper_v1"
    calculationOnly: bool = True
    externalProviderCalls: bool = False
    providerRuntimeChanged: bool = False
    marketCacheMutation: bool = False
    noOrderPlacement: bool = True
    noBrokerConnection: bool = True
    noPortfolioMutation: bool = True
    notInvestmentAdvice: bool = True


class LeveragedEtfMappingsResponse(BaseModel):
    mappings: list[LeveragedEtfMappingItem] = Field(default_factory=list)
    limitationCodes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: LeveragedEtfMapperMetadata


class LeveragedEtfMapperCalculateRequest(BaseModel):
    etfSymbol: str = Field(min_length=1)
    underlyingSymbol: str = Field(min_length=1)
    etfRefPrice: float = Field(gt=0)
    underlyingRefPrice: float = Field(gt=0)
    underlyingTargetPrice: float | None = Field(default=None, gt=0)
    etfTargetPrice: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_target_input(self) -> "LeveragedEtfMapperCalculateRequest":
        if self.underlyingTargetPrice is None and self.etfTargetPrice is None:
            raise ValueError("Provide underlyingTargetPrice or etfTargetPrice.")
        return self


class LeveragedEtfMapperCalculationInput(BaseModel):
    etfSymbol: str
    underlyingSymbol: str
    etfRefPrice: float
    underlyingRefPrice: float
    underlyingTargetPrice: float | None = None
    etfTargetPrice: float | None = None


class LeveragedEtfMapperCalculateResponse(BaseModel):
    status: CalculationStatus
    mapping: LeveragedEtfMappingItem
    input: LeveragedEtfMapperCalculationInput
    estimatedEtfPrice: float | None = None
    impliedUnderlyingPrice: float | None = None
    invalidReason: str | None = None
    limitationCodes: list[str] = Field(default_factory=list)
    warningCodes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: LeveragedEtfMapperMetadata
