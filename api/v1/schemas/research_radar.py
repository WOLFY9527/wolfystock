# -*- coding: utf-8 -*-
"""Typed response models for the Research Radar API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


RESEARCH_RADAR_RESPONSE_SCHEMA_VERSION = "research_radar_api_v1"


class _ResearchRadarModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResearchRadarConsumerIssueResponse(_ResearchRadarModel):
    label: str
    message: str
    severity: str
    category: str


class ResearchRadarDrilldownTargetResponse(_ResearchRadarModel):
    label: str
    route: str
    reason: str | None = None


class ResearchRadarOnboardingGuidanceResponse(_ResearchRadarModel):
    title: str
    summary: str
    conditionsDetected: list[str] = Field(default_factory=list)


class ResearchRadarEmptyStateActionResponse(_ResearchRadarModel):
    label: str
    route: str
    description: str


class ResearchRadarSuggestedResearchEntrypointResponse(_ResearchRadarModel):
    surface: str
    route: str
    description: str


class ResearchRadarEvidenceQualityResponse(_ResearchRadarModel):
    status: str
    score: int | float | None = None
    missingEvidence: list[str] = Field(default_factory=list)
    missingEvidenceRaw: list[str] = Field(default_factory=list)


class ResearchRadarEvidenceHubItemResponse(_ResearchRadarModel):
    key: str
    label: str
    status: str
    summary: str
    blocker: str | None = None
    nextDataAction: str
    evidenceCount: int = 0
    totalCount: int = 0
    symbols: list[str] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)
    observationOnly: Literal[True] = True
    decisionGrade: Literal[False] = False


class ResearchRadarEvidenceHubResponse(_ResearchRadarModel):
    scannerCandidates: ResearchRadarEvidenceHubItemResponse
    backtestSamples: ResearchRadarEvidenceHubItemResponse
    stockReadiness: ResearchRadarEvidenceHubItemResponse
    dataActivation: ResearchRadarEvidenceHubItemResponse
    missingEvidenceStates: list[ResearchRadarEvidenceHubItemResponse] = Field(default_factory=list)


class ResearchRadarMarketLevelFallbackCardResponse(_ResearchRadarModel):
    cardId: str
    title: str
    status: str
    severity: str
    headline: str
    reasons: list[str] = Field(default_factory=list)
    observationOnly: Literal[True] = True
    decisionGrade: Literal[False] = False


class ResearchRadarMarketLevelFallbackResponse(_ResearchRadarModel):
    available: Literal[True] = True
    label: str
    summary: str
    candidateGenerationExecuted: bool = False
    candidateUnavailableReason: str
    regime: dict[str, Any] = Field(default_factory=dict)
    productSummary: str
    evidenceCards: list[ResearchRadarMarketLevelFallbackCardResponse] = Field(default_factory=list)
    dataQuality: dict[str, Any] = Field(default_factory=dict)
    readiness: dict[str, Any] = Field(default_factory=dict)
    missingDataFamilies: list[str] = Field(default_factory=list)
    blockedProductSurfaces: list[str] = Field(default_factory=list)
    nextOperatorAction: str
    observationOnly: Literal[True] = True
    decisionGrade: Literal[False] = False


class ResearchRadarQueueItemResponse(_ResearchRadarModel):
    symbol: str
    ticker: str
    priority: Literal["high", "medium", "low"]
    researchBias: str
    researchBiasRaw: str
    researchBiasLabel: str
    researchBiasMessage: str
    driverScores: dict[str, int | float] = Field(default_factory=dict)
    whyOnRadar: list[str] = Field(default_factory=list)
    whatToVerify: list[str] = Field(default_factory=list)
    whyNotHigherPriority: list[str] = Field(default_factory=list)
    evidenceGaps: list[str] = Field(default_factory=list)
    evidenceGapsRaw: list[str] = Field(default_factory=list)
    consumerEvidenceGaps: list[ResearchRadarConsumerIssueResponse] = Field(default_factory=list)
    invalidationObservations: list[str] = Field(default_factory=list)
    duplicateEvidenceMerged: int = 0
    riskFlags: list[str] = Field(default_factory=list)
    riskFlagsRaw: list[str] = Field(default_factory=list)
    riskFlagLabels: list[str] = Field(default_factory=list)
    evidenceQuality: ResearchRadarEvidenceQualityResponse
    consumerIssues: list[ResearchRadarConsumerIssueResponse] = Field(default_factory=list)
    drilldownTargets: list[ResearchRadarDrilldownTargetResponse] = Field(default_factory=list)
    noAdviceDisclosure: str
    observationOnly: Literal[True] = True
    decisionGrade: Literal[False] = False


class ResearchRadarAggregateSummaryResponse(_ResearchRadarModel):
    candidateCount: int = 0
    queueCount: int = 0
    priorityCounts: dict[str, int] = Field(default_factory=dict)
    dominantThemes: list[str] = Field(default_factory=list)
    queueQuality: str
    duplicateEvidenceMerged: int = 0
    queueDiversity: dict[str, Any] = Field(default_factory=dict)
    source: dict[str, Any] = Field(default_factory=dict)


class ResearchRadarDataQualityResponse(_ResearchRadarModel):
    status: str
    availableCandidateCount: int = 0
    reliableCandidateCount: int = 0
    missingEvidence: list[str] = Field(default_factory=list)
    missingEvidenceRaw: list[str] = Field(default_factory=list)
    consumerIssues: list[ResearchRadarConsumerIssueResponse] = Field(default_factory=list)


class ResearchRadarResponse(_ResearchRadarModel):
    schemaVersion: Literal["research_radar_api_v1"] = RESEARCH_RADAR_RESPONSE_SCHEMA_VERSION
    generatedAt: str
    researchQueue: list[ResearchRadarQueueItemResponse] = Field(default_factory=list)
    aggregateSummary: ResearchRadarAggregateSummaryResponse
    evidenceGaps: list[str] = Field(default_factory=list)
    evidenceGapsRaw: list[str] = Field(default_factory=list)
    marketContextFit: str
    drilldownTargets: list[ResearchRadarDrilldownTargetResponse] = Field(default_factory=list)
    consumerIssues: list[ResearchRadarConsumerIssueResponse] = Field(default_factory=list)
    onboardingGuidance: ResearchRadarOnboardingGuidanceResponse | None = None
    emptyStateActions: list[ResearchRadarEmptyStateActionResponse] = Field(default_factory=list)
    starterResearchWorkflow: list[str] = Field(default_factory=list)
    firstRunChecklist: list[str] = Field(default_factory=list)
    suggestedResearchEntrypoints: list[ResearchRadarSuggestedResearchEntrypointResponse] = Field(
        default_factory=list
    )
    noAdviceDisclosure: str
    dataQuality: ResearchRadarDataQualityResponse
    evidenceHub: ResearchRadarEvidenceHubResponse
    marketLevelFallback: ResearchRadarMarketLevelFallbackResponse | None = None
    observationOnly: Literal[True] = True
    decisionGrade: Literal[False] = False


__all__ = [
    "RESEARCH_RADAR_RESPONSE_SCHEMA_VERSION",
    "ResearchRadarAggregateSummaryResponse",
    "ResearchRadarConsumerIssueResponse",
    "ResearchRadarDataQualityResponse",
    "ResearchRadarDrilldownTargetResponse",
    "ResearchRadarEvidenceHubItemResponse",
    "ResearchRadarEvidenceHubResponse",
    "ResearchRadarEvidenceQualityResponse",
    "ResearchRadarEmptyStateActionResponse",
    "ResearchRadarMarketLevelFallbackCardResponse",
    "ResearchRadarMarketLevelFallbackResponse",
    "ResearchRadarOnboardingGuidanceResponse",
    "ResearchRadarQueueItemResponse",
    "ResearchRadarResponse",
    "ResearchRadarSuggestedResearchEntrypointResponse",
]
