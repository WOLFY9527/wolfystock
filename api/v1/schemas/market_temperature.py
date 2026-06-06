# -*- coding: utf-8 -*-
"""Schemas for the market temperature consumed response subset."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


MarketTemperatureFreshnessLabel = Literal[
    "live",
    "fresh",
    "cached",
    "delayed",
    "stale",
    "partial",
    "fallback",
    "mock",
    "synthetic",
    "unavailable",
    "error",
    "unknown",
]


class MarketTemperatureProviderHealth(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str
    status: str
    asOf: Optional[str] = None
    updatedAt: Optional[str] = None
    latencyMs: Optional[int] = Field(default=None, ge=0)
    errorSummary: Optional[str] = None
    isFallback: bool
    isStale: bool
    isRefreshing: bool
    sourceLabel: Optional[str] = None
    card: str


class MarketTemperatureEvidenceSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    contractVersion: str
    diagnosticOnly: bool
    cardKey: str
    endpoint: str
    source: str
    sourceLabel: Optional[str] = None
    sourceType: Optional[str] = None
    asOf: Optional[str] = None
    updatedAt: Optional[str] = None
    freshness: MarketTemperatureFreshnessLabel
    isFallback: bool
    isStale: bool
    isPartial: bool
    isSynthetic: bool
    isUnavailable: bool
    isFromSnapshot: bool
    isRefreshing: bool
    providerHealth: dict[str, Any]
    confidenceWeight: float = Field(ge=0, le=1)
    coverage: Optional[float] = Field(default=None, ge=0, le=1)
    degradationReason: Optional[str] = None
    capReason: Optional[str] = None
    sourceAuthorityAllowed: Optional[bool] = None
    scoreContributionAllowed: Optional[bool] = None
    observationOnly: bool
    scoreReliabilityAllowed: bool
    reasonFamilies: list[dict[str, Any]] = Field(default_factory=list)


class MarketTemperatureConsumedSubsetResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str
    updatedAt: str
    freshness: MarketTemperatureFreshnessLabel
    isFallback: bool
    isStale: bool
    isPartial: bool
    temperatureAvailable: bool
    conclusionAllowed: bool
    researchReadiness: dict[str, Any]
    marketActionabilityFrame: dict[str, Any]
    marketIntelligenceEvidenceFrame: dict[str, Any]
    regimeSummary: dict[str, Any]
    providerHealth: MarketTemperatureProviderHealth
    evidenceSnapshot: MarketTemperatureEvidenceSnapshot
