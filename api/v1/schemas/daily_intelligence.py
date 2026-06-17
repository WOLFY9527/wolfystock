# -*- coding: utf-8 -*-
"""Schemas for the daily intelligence briefing endpoint."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


DAILY_INTELLIGENCE_SCHEMA_VERSION = "daily_intelligence_briefing_v1"


class DailyIntelligenceMarketRegimeSummaryResponse(BaseModel):
    regime: str
    confidence: str
    summary: str
    supportingObservations: List[str] = Field(default_factory=list)
    invalidationObservations: List[str] = Field(default_factory=list)


class DailyIntelligenceEvidenceLinkResponse(BaseModel):
    label: str
    route: str
    section: str
    reason: Optional[str] = None


class DailyIntelligencePriorityItemResponse(BaseModel):
    label: str
    source: str
    priority: Optional[str] = None
    ticker: Optional[str] = None
    observations: List[str] = Field(default_factory=list)
    whatToVerify: List[str] = Field(default_factory=list)
    evidenceGaps: List[str] = Field(default_factory=list)
    evidenceLinks: List[DailyIntelligenceEvidenceLinkResponse] = Field(default_factory=list)


class DailyIntelligenceScannerHighlightResponse(BaseModel):
    ticker: str
    priority: str
    observations: List[str] = Field(default_factory=list)
    whatToVerify: List[str] = Field(default_factory=list)
    evidenceGaps: List[str] = Field(default_factory=list)
    riskFlags: List[str] = Field(default_factory=list)
    evidenceLinks: List[DailyIntelligenceEvidenceLinkResponse] = Field(default_factory=list)


class DailyIntelligenceWatchlistHighlightResponse(BaseModel):
    ticker: str
    structureState: str
    researchPriority: Optional[str] = None
    whyWatching: Optional[str] = None
    whatToVerify: List[str] = Field(default_factory=list)
    evidenceGaps: List[str] = Field(default_factory=list)
    riskFlags: List[str] = Field(default_factory=list)
    evidenceLinks: List[DailyIntelligenceEvidenceLinkResponse] = Field(default_factory=list)


class DailyIntelligencePortfolioStructureHighlightResponse(BaseModel):
    ticker: str
    structureState: str
    confidence: str
    watchNext: List[str] = Field(default_factory=list)
    riskFlags: List[str] = Field(default_factory=list)
    missingEvidence: List[str] = Field(default_factory=list)
    evidenceLinks: List[DailyIntelligenceEvidenceLinkResponse] = Field(default_factory=list)


class DailyIntelligenceScenarioRiskResponse(BaseModel):
    label: str
    source: str
    observations: List[str] = Field(default_factory=list)
    evidenceGaps: List[str] = Field(default_factory=list)


class DailyIntelligenceDegradedInputResponse(BaseModel):
    section: str
    status: Literal["degraded", "unavailable"]
    reason: str


class DailyIntelligenceResearchWorkflowStepResponse(BaseModel):
    surface: str
    status: Literal["available", "degraded", "unavailable"]
    summary: str
    drilldownTargets: List[DailyIntelligenceEvidenceLinkResponse] = Field(default_factory=list)


class DailyIntelligenceCrossSurfaceEvidenceResponse(BaseModel):
    surfaces: List[str] = Field(default_factory=list)
    observation: str
    drilldownTargets: List[DailyIntelligenceEvidenceLinkResponse] = Field(default_factory=list)


class DailyIntelligenceTopResearchQuestionResponse(BaseModel):
    question: str
    surface: str
    drilldownTargets: List[DailyIntelligenceEvidenceLinkResponse] = Field(default_factory=list)


class DailyIntelligenceEvidenceConflictResponse(BaseModel):
    surfaces: List[str] = Field(default_factory=list)
    summary: str
    drilldownTargets: List[DailyIntelligenceEvidenceLinkResponse] = Field(default_factory=list)


class DailyIntelligenceDegradedSurfaceSummaryResponse(BaseModel):
    surface: str
    status: Literal["available", "degraded", "unavailable"]
    reason: str
    drilldownTargets: List[DailyIntelligenceEvidenceLinkResponse] = Field(default_factory=list)


class DailyIntelligenceOnboardingGuidanceResponse(BaseModel):
    title: str
    summary: str
    conditionsDetected: List[str] = Field(default_factory=list)


class DailyIntelligenceEmptyStateActionResponse(BaseModel):
    label: str
    route: str
    description: str


class DailyIntelligenceSuggestedResearchEntrypointResponse(BaseModel):
    surface: str
    route: str
    description: str


class DailyIntelligenceBriefingResponse(BaseModel):
    schemaVersion: Literal["daily_intelligence_briefing_v1"] = DAILY_INTELLIGENCE_SCHEMA_VERSION
    generatedAt: str
    briefingDate: str
    sessionLabel: Optional[str] = None
    marketRegimeSummary: DailyIntelligenceMarketRegimeSummaryResponse
    whatChanged: List[str] = Field(default_factory=list)
    sectionLinks: List[DailyIntelligenceEvidenceLinkResponse] = Field(default_factory=list)
    topResearchPriorities: List[DailyIntelligencePriorityItemResponse] = Field(default_factory=list)
    scannerHighlights: List[DailyIntelligenceScannerHighlightResponse] = Field(default_factory=list)
    watchlistHighlights: List[DailyIntelligenceWatchlistHighlightResponse] = Field(default_factory=list)
    portfolioHighlights: List[DailyIntelligencePortfolioStructureHighlightResponse] = Field(default_factory=list)
    portfolioStructureHighlights: List[DailyIntelligencePortfolioStructureHighlightResponse] = Field(
        default_factory=list
    )
    scenarioRisks: List[DailyIntelligenceScenarioRiskResponse] = Field(default_factory=list)
    evidenceGaps: List[str] = Field(default_factory=list)
    degradedInputs: List[DailyIntelligenceDegradedInputResponse | Dict[str, Any]] = Field(default_factory=list)
    drilldownTargets: List[DailyIntelligenceEvidenceLinkResponse] = Field(default_factory=list)
    researchWorkflow: List[DailyIntelligenceResearchWorkflowStepResponse] = Field(default_factory=list)
    crossSurfaceEvidence: List[DailyIntelligenceCrossSurfaceEvidenceResponse] = Field(default_factory=list)
    topResearchQuestions: List[DailyIntelligenceTopResearchQuestionResponse] = Field(default_factory=list)
    priorityDrilldowns: List[DailyIntelligenceEvidenceLinkResponse] = Field(default_factory=list)
    evidenceConflicts: List[DailyIntelligenceEvidenceConflictResponse] = Field(default_factory=list)
    degradedSurfaceSummary: List[DailyIntelligenceDegradedSurfaceSummaryResponse] = Field(default_factory=list)
    nextObservationSteps: List[str] = Field(default_factory=list)
    onboardingGuidance: Optional[DailyIntelligenceOnboardingGuidanceResponse] = None
    emptyStateActions: List[DailyIntelligenceEmptyStateActionResponse] = Field(default_factory=list)
    starterResearchWorkflow: List[str] = Field(default_factory=list)
    firstRunChecklist: List[str] = Field(default_factory=list)
    suggestedResearchEntrypoints: List[DailyIntelligenceSuggestedResearchEntrypointResponse] = Field(
        default_factory=list
    )
    consumerIssues: List[Dict[str, str]] = Field(default_factory=list)
    noAdviceDisclosure: str
    observationOnly: Literal[True] = True
    decisionGrade: Literal[False] = False
