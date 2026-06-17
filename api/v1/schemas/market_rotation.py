# -*- coding: utf-8 -*-
"""Schemas for the read-only market rotation radar endpoint."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


FreshnessLabel = Literal["live", "delayed", "cached", "stale", "fallback", "mock", "error"]
RankingLane = Literal["headline", "observation", "taxonomy"]
RotationSignalType = Literal[
    "real_flow",
    "relative_strength",
    "momentum_proxy",
    "observation_only",
    "taxonomy_fallback",
    "insufficient_evidence",
]
RotationEvidenceQuality = Literal[
    "score_grade_proxy",
    "degraded_proxy",
    "observation_only",
    "taxonomy_only",
    "insufficient",
    "score_grade_real_flow",
]
RotationStage = Literal[
    "early_watch",
    "confirmed_rotation",
    "extended_watch",
    "cooling_watch",
    "weak_or_no_signal",
]
RotationRiskLabel = Literal[
    "gap_fade_risk",
    "thin_breadth",
    "single_name_driven",
    "stale_or_incomplete_windows",
]
DataQualityState = Literal["ready", "delayed", "cached", "partial", "no_evidence", "unavailable"]


class ConsumerDataQualityModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: DataQualityState
    label: str
    available: bool = False


def _default_unavailable_data_quality() -> ConsumerDataQualityModel:
    return ConsumerDataQualityModel(state="unavailable", label="暂不可用", available=False)


class RotationRadarTimeWindowModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    window: Literal["5m", "15m", "60m", "1d"]
    label: str
    available: bool = False
    changePercent: Optional[float] = None
    relativeVolume: Optional[float] = None
    freshness: FreshnessLabel = "fallback"
    isFallback: bool = False
    isStale: bool = False
    source: Optional[str] = None
    sourceLabel: Optional[str] = None
    asOf: Optional[str] = None
    reason: Optional[str] = None


class RotationRadarBenchmarkModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str
    changePercent: Optional[float] = None
    timeWindows: Dict[str, RotationRadarTimeWindowModel] = Field(default_factory=dict)
    freshness: FreshnessLabel = "fallback"
    isFallback: bool = False
    isStale: bool = False
    source: Optional[str] = None
    sourceLabel: Optional[str] = None
    sourceType: Optional[str] = None
    sourceTier: Optional[str] = None
    providerTier: Optional[str] = None
    asOf: Optional[str] = None


class RotationRadarMemberModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str
    name: str
    observed: bool = False
    price: Optional[float] = None
    changePercent: Optional[float] = None
    relativeStrengthVsBenchmark: Optional[float] = None
    volumeRatio: Optional[float] = None
    timeWindows: Dict[str, RotationRadarTimeWindowModel] = Field(default_factory=dict)
    priceAboveVwap: Optional[bool] = None
    persistenceScore: Optional[float] = None
    leadershipLabel: Optional[str] = None
    freshnessLabel: Optional[str] = None
    freshness: FreshnessLabel = "fallback"
    isFallback: bool = False
    isStale: bool = False
    source: Optional[str] = None
    sourceLabel: Optional[str] = None
    asOf: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


class RotationRadarThemeModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    market: Optional[str] = None
    taxonomyType: Optional[str] = None
    name: str
    englishName: str
    themeDefinition: Dict[str, Any] = Field(default_factory=dict)
    focus: str
    benchmark: str
    sectorBenchmark: Optional[str] = None
    membersConfigured: List[str] = Field(default_factory=list)
    representativeLabels: List[str] = Field(default_factory=list)
    representativeSymbols: List[str] = Field(default_factory=list)
    proxySymbols: List[str] = Field(default_factory=list)
    mappedConcepts: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)
    rotationScore: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    confidenceLabel: Optional[str] = None
    dataQuality: Optional[str] = None
    dataCoverage: Optional[str] = None
    sourceClass: Optional[str] = None
    staticThemeOnly: bool = False
    rankEligible: bool = False
    rankExclusionReason: Optional[str] = None
    taxonomyOnly: bool = False
    observationOnly: bool = False
    headlineEligible: bool = False
    rankingLane: RankingLane = "observation"
    scoreContributionAllowed: bool = False
    signalType: RotationSignalType = "insufficient_evidence"
    flowEvidenceType: str = "none"
    flowLanguageAllowed: bool = False
    sourceAuthorityAllowed: bool = False
    evidenceQuality: RotationEvidenceQuality = "insufficient"
    dataGaps: List[str] = Field(default_factory=list)
    sourceTier: Optional[str] = None
    trustLevel: Optional[str] = None
    scoreCap: Optional[float] = None
    conclusionAllowed: bool = False
    degradationReasons: List[str] = Field(default_factory=list)
    rankingTrust: Dict[str, Any] = Field(default_factory=dict)
    stage: RotationStage
    stageExplanation: Optional[str] = None
    riskLabels: List[RotationRiskLabel] = Field(default_factory=list)
    riskExplanations: List[str] = Field(default_factory=list)
    newslessRotation: bool = False
    newslessRotationEvidence: Optional[str] = None
    persistenceScore: Optional[float] = None
    persistenceEvidence: Dict[str, Any] = Field(default_factory=dict)
    alertCandidates: List[Dict[str, Any]] = Field(default_factory=list)
    relativeStrength: Dict[str, Any] = Field(default_factory=dict)
    proxyQuality: Dict[str, Any] = Field(default_factory=dict)
    proxyEvidence: Dict[str, Any] = Field(default_factory=dict)
    constituentCoverage: Dict[str, Any] = Field(default_factory=dict)
    scoreBreakdown: Dict[str, Any] = Field(default_factory=dict)
    weightBreakdown: Dict[str, Any] = Field(default_factory=dict)
    coveragePenalty: Optional[float] = None
    fallbackPenalty: Optional[float] = None
    missingProxySymbols: List[str] = Field(default_factory=list)
    missingConstituentSymbols: List[str] = Field(default_factory=list)
    benchmarkProxies: Dict[str, Any] = Field(default_factory=dict)
    timeWindows: Dict[str, RotationRadarTimeWindowModel] = Field(default_factory=dict)
    volume: Dict[str, Any] = Field(default_factory=dict)
    breadth: Dict[str, Any] = Field(default_factory=dict)
    synchronization: Dict[str, Any] = Field(default_factory=dict)
    leadership: Dict[str, Any] = Field(default_factory=dict)
    themeDetail: Dict[str, Any] = Field(default_factory=dict)
    freshness: FreshnessLabel = "fallback"
    isFallback: bool = False
    isStale: bool = False
    source: str = "fallback"
    sourceLabel: Optional[str] = None
    asOf: Optional[str] = None
    updatedAt: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)
    members: List[RotationRadarMemberModel] = Field(default_factory=list)
    rotationStateEvidence: Dict[str, Any] = Field(default_factory=dict)
    themeCorrelationBreadthSnapshot: Dict[str, Any] = Field(default_factory=dict)
    themeFlowSignal: Dict[str, Any] = Field(default_factory=dict)
    noAdviceDisclosure: str


class RotationRadarSummaryItemModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    rotationScore: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    stage: RotationStage
    freshness: FreshnessLabel
    isFallback: bool
    riskLabels: List[RotationRiskLabel] = Field(default_factory=list)
    rankEligible: bool = False
    rankExclusionReason: Optional[str] = None
    taxonomyOnly: bool = False
    observationOnly: bool = False
    headlineEligible: bool = False
    rankingLane: RankingLane = "observation"
    scoreContributionAllowed: bool = False
    signalType: RotationSignalType = "insufficient_evidence"
    flowEvidenceType: str = "none"
    flowLanguageAllowed: bool = False
    sourceAuthorityAllowed: bool = False
    evidenceQuality: RotationEvidenceQuality = "insufficient"
    dataGaps: List[str] = Field(default_factory=list)
    sourceTier: Optional[str] = None
    trustLevel: Optional[str] = None


class RotationRadarSummaryModel(BaseModel):
    strongestThemes: List[RotationRadarSummaryItemModel] = Field(default_factory=list)
    acceleratingThemes: List[RotationRadarSummaryItemModel] = Field(default_factory=list)
    fadingThemes: List[RotationRadarSummaryItemModel] = Field(default_factory=list)
    observationThemes: List[RotationRadarSummaryItemModel] = Field(default_factory=list)
    taxonomyThemes: List[RotationRadarSummaryItemModel] = Field(default_factory=list)
    rotationFamilyRollup: List[Dict[str, Any]] = Field(default_factory=list)
    eligibleThemeCount: int = 0
    headlineEligibleThemeCount: int = 0
    observationThemeCount: int = 0
    headlineWarning: Optional[str] = None
    noHeadlineReason: Optional[str] = None
    rankingPolicy: Optional[str] = None
    watchlistSortingExplanation: Optional[str] = None
    safeWording: List[str] = Field(default_factory=list)
    watchlistSignals: List[Dict[str, Any]] = Field(default_factory=list)


class RotationRadarEtfLeadershipDiagnosticsModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = False
    source: Optional[str] = None
    asOf: Optional[str] = None
    eligibleSymbols: List[str] = Field(default_factory=list)
    leadingSymbols: List[str] = Field(default_factory=list)
    laggingSymbols: List[str] = Field(default_factory=list)
    leadershipSpread: Optional[float] = None
    confidenceLabel: Optional[str] = None
    reasonCodes: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)


class RotationRadarConsumerProviderStateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    present: bool = False
    status: str = "absent"
    quoteMode: str = "proxy"
    sourceType: str = "missing"
    sourceTier: str = "unknown"
    providerTier: str = "unknown"
    freshness: str = "fallback"
    dataQuality: ConsumerDataQualityModel = Field(default_factory=_default_unavailable_data_quality)
    asOf: Optional[str] = None
    coverage: Dict[str, Any] = Field(default_factory=dict)
    sourceAuthorityAllowed: bool = False
    scoreContributionAllowed: bool = False
    noExternalCalls: bool = True


class RotationRadarConsumerEtfProxySummaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    present: bool = False
    proxyOnly: bool = True
    label: str = "ETF proxy-only leadership evidence; not real fund-flow authority."
    fundFlowAuthorityAllowed: bool = False
    enabled: bool = False
    source: Optional[str] = None
    asOf: Optional[str] = None
    eligibleSymbolCount: int = 0
    leadingSymbols: List[str] = Field(default_factory=list)
    laggingSymbols: List[str] = Field(default_factory=list)
    reasonCodes: List[str] = Field(default_factory=list)


class RotationRadarConsumerThemeQualityModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    rankEligible: bool = False
    headlineEligible: bool = False
    rankingLane: RankingLane = "observation"
    observationOnly: bool = False
    taxonomyOnly: bool = False
    scoreContributionAllowed: bool = False
    freshness: str = "fallback"
    isFallback: bool = False
    isStale: bool = False
    isPartial: bool = False
    dataQuality: ConsumerDataQualityModel = Field(default_factory=_default_unavailable_data_quality)
    evidenceQuality: str = "insufficient"
    dataGaps: List[str] = Field(default_factory=list)
    breadthEvidence: Optional["RotationRadarConsumerThemeBreadthEvidenceModel"] = None


class RotationRadarConsumerThemeBreadthEvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "rotation_theme_quote_breadth"
    observationOnly: bool = True
    authorityGrant: bool = False
    scoreContributionAllowed: bool = False
    observedMembers: Optional[int] = None
    configuredMembers: Optional[int] = None
    coveragePercent: Optional[float] = None
    percentUp: Optional[float] = None
    percentOutperformingBenchmark: Optional[float] = None


class RotationRadarConsumerEvidenceSnapshotModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market: str
    generatedAt: Optional[str] = None
    asOf: Optional[str] = None
    freshness: str = "fallback"
    isFallback: bool = False
    isStale: bool = False
    isPartial: bool = False
    dataQuality: ConsumerDataQualityModel = Field(default_factory=_default_unavailable_data_quality)
    headlineEligibleThemeCount: int = 0
    observationThemeCount: int = 0
    taxonomyThemeCount: int = 0
    scoreContributionAllowed: bool = False
    authorityGrant: Optional[bool] = None
    reasonCodes: List[str] = Field(default_factory=list)
    providerState: RotationRadarConsumerProviderStateModel = Field(
        default_factory=RotationRadarConsumerProviderStateModel
    )
    etfProxySummary: RotationRadarConsumerEtfProxySummaryModel = Field(
        default_factory=RotationRadarConsumerEtfProxySummaryModel
    )
    rotationFamilyRollup: List[Dict[str, Any]] = Field(default_factory=list)
    themes: List[RotationRadarConsumerThemeQualityModel] = Field(default_factory=list)


class MarketRotationRadarResponse(BaseModel):
    endpoint: str
    market: str = "US"
    supportedMarkets: List[str] = Field(default_factory=list)
    generatedAt: str
    source: str
    sourceLabel: Optional[str] = None
    freshness: FreshnessLabel
    isFallback: bool = False
    isStale: bool = False
    warning: Optional[str] = None
    noAdviceDisclosure: str
    benchmarks: Dict[str, RotationRadarBenchmarkModel] = Field(default_factory=dict)
    etfLeadershipDiagnostics: RotationRadarEtfLeadershipDiagnosticsModel = Field(
        default_factory=RotationRadarEtfLeadershipDiagnosticsModel
    )
    summary: RotationRadarSummaryModel
    themes: List[RotationRadarThemeModel] = Field(default_factory=list)
    consumerEvidenceSnapshot: RotationRadarConsumerEvidenceSnapshotModel
    metadata: Dict[str, Any] = Field(default_factory=dict)
