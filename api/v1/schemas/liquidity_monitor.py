# -*- coding: utf-8 -*-
"""Schemas for the advisory liquidity monitor endpoint."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from src.contracts.source_confidence import MarketIntelligenceSourceTier
from src.services.market_data_quality import build_consumer_data_quality_state


FreshnessLabel = Literal["live", "cached", "delayed", "stale", "fallback", "mock", "error", "unavailable"]
LiquidityRegime = Literal["abundant", "supportive", "neutral", "tight", "stress", "unavailable"]
IndicatorStatus = Literal["live", "partial", "unavailable"]
EvidenceFreshnessLabel = Literal["live", "fresh", "cached", "delayed", "stale", "partial", "fallback", "synthetic", "unavailable", "unknown"]
SourceTierLabel = MarketIntelligenceSourceTier
TrustLevelLabel = Literal["reliable", "usable_with_caution", "weak", "unavailable"]
CapitalFlowRegimeLabel = Literal["inflow", "balanced", "outflow", "mixed", "insufficient_evidence"]
MarketRegimeLabel = Literal["risk_on", "balanced", "risk_off", "mixed", "insufficient_evidence"]
ThemeFlowStateLabel = Literal["leading", "broadening", "rotating", "crowded", "fading", "mixed", "insufficient_evidence"]
ConfidenceLabel = Literal["high", "medium", "low", "blocked"]
CapitalFlowDestinationLabel = Literal["growth_ai_software_semis", "oil", "gold", "btc", "defensives", "no_clear_edge"]
CapitalFlowPressureLabel = Literal["absorbing", "lagging", "easing", "tightening", "benign", "stress", "balanced"]
DataQualityState = Literal["ready", "delayed", "cached", "partial", "no_evidence", "unavailable"]


class ConsumerDataQuality(BaseModel):
    state: DataQualityState
    label: str
    available: bool = False


class CapitalFlowSourceAssetPressure(BaseModel):
    asset: str
    pressure: CapitalFlowPressureLabel
    changePercent: float | None = None
    freshness: EvidenceFreshnessLabel
    isFallback: bool = False
    isStale: bool = False
    isPartial: bool = False
    observationOnly: bool = True


class LiquidityMonitorCapitalFlowSignal(BaseModel):
    contractVersion: str
    diagnosticOnly: bool = True
    observationOnly: bool = True
    authorityGrant: bool = False
    decisionGrade: bool = False
    sourceAuthorityAllowed: bool = False
    scoreContributionAllowed: bool = False
    marketRegime: MarketRegimeLabel
    marketRegimeLabel: str
    capitalFlowRegime: CapitalFlowRegimeLabel
    capitalFlowLabel: str
    themeFlowState: ThemeFlowStateLabel
    themeFlowLabel: str
    confidenceLabel: ConfidenceLabel
    confidenceText: str
    confidence: ConfidenceLabel
    freshness: EvidenceFreshnessLabel
    isFallback: bool = False
    isStale: bool = False
    isPartial: bool = False
    reasonCodes: list[str] = Field(default_factory=list)
    contradictionCodes: list[str] = Field(default_factory=list)
    likelyDestination: CapitalFlowDestinationLabel
    sourceAssetPressure: list[CapitalFlowSourceAssetPressure] = Field(default_factory=list)
    contradictionSignals: list[str] = Field(default_factory=list)
    explanation: str


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
    sourceTier: Optional[str] = None
    trustLevel: Optional[str] = None
    asOf: Optional[str] = None
    freshness: EvidenceFreshnessLabel
    isFallback: bool = False
    isStale: bool = False
    isPartial: bool = False
    isUnavailable: bool = False
    observationOnly: Optional[bool] = None
    sourceAuthorityAllowed: Optional[bool] = None
    scoreContributionAllowed: Optional[bool] = None
    sourceAuthorityReason: Optional[str] = None
    sourceAuthorityRouteRejected: Optional[bool] = None
    routeRejectedReasonCodes: Optional[list[str]] = None
    officialSeriesId: Optional[str] = None
    officialObservationDate: Optional[str] = None
    officialAsOf: Optional[str] = None
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


class LiquidityImpulseSynthesisPayload(BaseModel):
    liquidityImpulse: str
    impulseLabel: str
    subtype: str
    confidence: float = Field(ge=0, le=1)
    confidenceLabel: str
    pillarScores: dict[str, float] = Field(default_factory=dict)
    directionScore: float = Field(ge=-1, le=1)
    dominantDrivers: list[dict[str, Any]] = Field(default_factory=list)
    counterEvidence: list[dict[str, Any]] = Field(default_factory=list)
    dataGaps: list[dict[str, Any]] = Field(default_factory=list)
    narrativeBullets: list[str] = Field(default_factory=list)
    evidenceQuality: dict[str, Any] = Field(default_factory=dict)
    notInvestmentAdvice: bool = True


class LiquidityMonitorResponse(BaseModel):
    endpoint: str
    generatedAt: str
    score: LiquidityMonitorScore
    freshness: LiquidityMonitorFreshnessSummary
    dataQuality: ConsumerDataQuality
    indicators: list[LiquidityMonitorIndicator] = Field(default_factory=list)
    capitalFlowSignal: LiquidityMonitorCapitalFlowSignal | None = None
    liquidityImpulseSynthesis: LiquidityImpulseSynthesisPayload
    advisoryDisclosure: str
    sourceMetadata: LiquidityMonitorSourceMetadata

    @model_validator(mode="before")
    @classmethod
    def _populate_data_quality(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "dataQuality" in value:
            return value
        payload = dict(value)
        freshness = payload.get("freshness") if isinstance(payload.get("freshness"), dict) else {}
        score = payload.get("score") if isinstance(payload.get("score"), dict) else {}
        payload["dataQuality"] = build_consumer_data_quality_state(
            {
                "freshness": freshness.get("status"),
                "isUnavailable": score.get("regime") == "unavailable" and not payload.get("indicators"),
                "isPartial": any(
                    isinstance(item, dict) and item.get("status") == "partial"
                    for item in payload.get("indicators") or []
                ),
            }
        )
        return payload
