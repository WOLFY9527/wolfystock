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
    portfolioStructureHighlights: List[DailyIntelligencePortfolioStructureHighlightResponse] = Field(
        default_factory=list
    )
    scenarioRisks: List[DailyIntelligenceScenarioRiskResponse] = Field(default_factory=list)
    evidenceGaps: List[str] = Field(default_factory=list)
    degradedInputs: List[DailyIntelligenceDegradedInputResponse | Dict[str, Any]] = Field(default_factory=list)
    observationOnly: Literal[True] = True
    decisionGrade: Literal[False] = False
