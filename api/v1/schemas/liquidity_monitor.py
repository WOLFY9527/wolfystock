# -*- coding: utf-8 -*-
"""Schemas for the advisory liquidity monitor endpoint."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


FreshnessLabel = Literal["live", "cached", "delayed", "stale", "fallback", "mock", "error", "unavailable"]
LiquidityRegime = Literal["abundant", "supportive", "neutral", "tight", "stress", "unavailable"]
IndicatorStatus = Literal["live", "partial", "unavailable"]
EvidenceFreshnessLabel = Literal["live", "fresh", "cached", "delayed", "stale", "partial", "fallback", "synthetic", "unavailable", "unknown"]
SourceTierLabel = Literal[
    "official_public",
    "exchange_public",
    "broker_authorized",
    "unofficial_public_api",
    "public_web_fallback",
    "snapshot",
    "static_fallback",
    "synthetic",
    "unavailable",
]
TrustLevelLabel = Literal["reliable", "usable_with_caution", "weak", "unavailable"]


class LiquidityMonitorScore(BaseModel):
    value: int = Field(ge=0, le=100)
    regime: LiquidityRegime
    confidence: float = Field(ge=0, le=0.95)
    includedIndicatorCount: int = Field(ge=0)
    possibleIndicatorWeight: int = Field(ge=0)
    includedIndicatorWeight: int = Field(ge=0)


class LiquidityMonitorEvidenceInput(BaseModel):
    key: str
    label: str
    source: str
    sourceLabel: Optional[str] = None
    sourceType: Optional[str] = None
    asOf: Optional[str] = None
    freshness: EvidenceFreshnessLabel
    isFallback: bool = False
    isStale: bool = False
    isPartial: bool = False
    isUnavailable: bool = False
    coverage: Optional[float] = Field(default=None, ge=0, le=1)
    confidenceWeight: float = Field(ge=0, le=1)
    degradationReason: Optional[str] = None
    capReason: Optional[str] = None


class LiquidityMonitorEvidenceSnapshot(BaseModel):
    contractVersion: str
    source: str
    sourceLabel: Optional[str] = None
    asOf: Optional[str] = None
    freshness: EvidenceFreshnessLabel
    isFallback: bool = False
    isStale: bool = False
    isPartial: bool = False
    isUnavailable: bool = False
    coverage: Optional[float] = Field(default=None, ge=0, le=1)
    confidenceWeight: float = Field(ge=0, le=1)
    degradationReason: Optional[str] = None
    capReason: Optional[str] = None
    inputs: list[LiquidityMonitorEvidenceInput] = Field(default_factory=list)


class LiquidityMonitorCoverageDiagnostics(BaseModel):
    indicatorId: str
    indicatorName: str
    requiredInputs: list[str] = Field(default_factory=list)
    fulfilledInputs: list[str] = Field(default_factory=list)
    missingInputs: list[str] = Field(default_factory=list)
    requiredProviderClass: Optional[str] = None
    configuredProviderAvailable: bool = False
    realSourceAvailable: bool = False
    proxyOnly: bool = False
    observationOnly: bool = False
    scoreContributionAllowed: bool = False
    scoreExclusionReason: Optional[str] = None
    requiredRealSourceForScore: bool = False
    proxyObservationOnlyReason: Optional[str] = None
    missingProviderReason: Optional[str] = None
    paidDataLikelyRequired: bool = False
    sourceTier: SourceTierLabel
    freshness: EvidenceFreshnessLabel
    trustLevel: TrustLevelLabel
    contributesToScore: bool = False
    scoreContribution: int = 0
    capReason: Optional[str] = None
    degradationReason: Optional[str] = None
    sourceAuthorityRouteRejected: bool = False
    sourceAuthorityReason: Optional[str] = None
    routeRejectedReasonCodes: list[str] = Field(default_factory=list)
    activationHint: Optional[str] = None


class LiquidityMonitorIndicator(BaseModel):
    key: str
    label: str
    status: IndicatorStatus
    freshness: FreshnessLabel
    includedInScore: bool = False
    scoreContribution: int = 0
    scoreWeight: int = 0
    summary: Optional[str] = None
    updatedAt: Optional[str] = None
    evidence: Optional[LiquidityMonitorEvidenceSnapshot] = None
    coverageDiagnostics: Optional[LiquidityMonitorCoverageDiagnostics] = None


class LiquidityMonitorFreshnessSummary(BaseModel):
    status: FreshnessLabel
    weakestIndicatorFreshness: FreshnessLabel
    latestAsOf: Optional[str] = None


class LiquidityMonitorSourceMetadata(BaseModel):
    externalProviderCalls: bool = False
    providerRuntimeChanged: bool = False
    marketCacheMutation: bool = False


class LiquidityMonitorResponse(BaseModel):
    endpoint: str
    generatedAt: str
    score: LiquidityMonitorScore
    freshness: LiquidityMonitorFreshnessSummary
    indicators: list[LiquidityMonitorIndicator] = Field(default_factory=list)
    advisoryDisclosure: str
    sourceMetadata: LiquidityMonitorSourceMetadata
