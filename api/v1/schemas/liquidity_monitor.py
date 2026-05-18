# -*- coding: utf-8 -*-
"""Schemas for the advisory liquidity monitor endpoint."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


FreshnessLabel = Literal["live", "cached", "delayed", "stale", "fallback", "mock", "error", "unavailable"]
LiquidityRegime = Literal["abundant", "supportive", "neutral", "tight", "stress", "unavailable"]
IndicatorStatus = Literal["live", "partial", "unavailable"]
EvidenceFreshnessLabel = Literal["live", "fresh", "cached", "delayed", "stale", "partial", "fallback", "synthetic", "unavailable", "unknown"]


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
