# -*- coding: utf-8 -*-
"""Standalone contract models for homepage and unified research queues."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


UNIFIED_RESEARCH_QUEUE_RESPONSE_SCHEMA_VERSION = "research_queue_v1"

ResearchQueueCategory = Literal[
    "market",
    "liquidity",
    "money_flow",
    "event",
    "watchlist",
    "portfolio",
    "research",
    "data_quality",
]
ResearchQueueItemStatus = Literal["observe", "review", "high_attention", "no_evidence", "unavailable"]
ResearchQueueEvidenceStatus = Literal["available", "partial", "no_evidence", "unavailable"]
ResearchQueueTopLevelStatus = Literal["ready", "partial", "no_evidence", "unavailable"]


class _ResearchQueueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResearchQueueSeedItem(_ResearchQueueModel):
    id: str | None = None
    title: str | None = None
    reason: str | None = None
    category: ResearchQueueCategory | None = None
    reviewModule: str | None = None
    status: ResearchQueueItemStatus = "observe"
    relatedSymbols: list[str] = Field(default_factory=list)
    relatedThemes: list[str] = Field(default_factory=list)
    evidenceStatus: ResearchQueueEvidenceStatus = "no_evidence"
    priorityHint: int | None = Field(default=None, ge=1)


class ResearchQueueBuildInputs(_ResearchQueueModel):
    asOf: str | None = None
    market: list[ResearchQueueSeedItem] = Field(default_factory=list)
    liquidity: list[ResearchQueueSeedItem] = Field(default_factory=list)
    moneyFlow: list[ResearchQueueSeedItem] = Field(default_factory=list)
    event: list[ResearchQueueSeedItem] = Field(default_factory=list)
    watchlist: list[ResearchQueueSeedItem] = Field(default_factory=list)
    portfolio: list[ResearchQueueSeedItem] = Field(default_factory=list)
    research: list[ResearchQueueSeedItem] = Field(default_factory=list)
    dataQuality: list[ResearchQueueSeedItem] = Field(default_factory=list)
    moneyFlowSummary: Any | None = None
    eventRadarSummary: Any | None = None
    personalSummary: Any | None = None
    dataQualitySummary: Any | None = None


class ResearchQueueItem(_ResearchQueueModel):
    id: str
    priority: int = Field(ge=1)
    title: str
    reason: str
    category: ResearchQueueCategory
    reviewModule: str
    status: ResearchQueueItemStatus
    relatedSymbols: list[str] = Field(default_factory=list)
    relatedThemes: list[str] = Field(default_factory=list)
    evidenceStatus: ResearchQueueEvidenceStatus
    noAdviceDisclosure: str


class ResearchQueueDataQuality(_ResearchQueueModel):
    status: ResearchQueueTopLevelStatus
    summary: str
    availableDomains: list[str] = Field(default_factory=list)
    missingDomains: list[str] = Field(default_factory=list)


class ResearchQueueResponse(_ResearchQueueModel):
    status: ResearchQueueTopLevelStatus
    asOf: str | None = None
    items: list[ResearchQueueItem] = Field(default_factory=list)
    dataQuality: ResearchQueueDataQuality
    noAdviceDisclosure: str


class UnifiedResearchQueueFreshnessResponse(_ResearchQueueModel):
    state: Literal["current", "needs_review", "unavailable", "unknown"]
    lastReviewedAt: str | None = None


class UnifiedResearchQueueSuggestedResearchPathResponse(_ResearchQueueModel):
    label: str
    route: str
    section: str
    reason: str


class UnifiedResearchQueueItemResponse(_ResearchQueueModel):
    queueItemId: str
    sourceSurface: Literal["scanner", "watchlist", "market", "manual_gap"]
    symbol: str
    title: str
    priorityTier: Literal["urgent_review", "follow_up", "monitor"]
    whyQueued: list[str] = Field(default_factory=list)
    evidenceUsed: list[str] = Field(default_factory=list)
    evidenceGaps: list[str] = Field(default_factory=list)
    freshness: UnifiedResearchQueueFreshnessResponse
    suggestedResearchPath: list[UnifiedResearchQueueSuggestedResearchPathResponse] = Field(default_factory=list)
    observationOnly: Literal[True] = True


class UnifiedResearchQueueAggregateSummaryResponse(_ResearchQueueModel):
    itemCount: int = 0
    limit: int = 10
    bounded: bool = False
    bySourceSurface: dict[str, int] = Field(default_factory=dict)
    byPriorityTier: dict[str, int] = Field(default_factory=dict)


class UnifiedResearchQueueDataQualityResponse(_ResearchQueueModel):
    state: Literal["ready", "no_evidence"]
    itemCount: int = 0
    sourceSurfacesAvailable: list[str] = Field(default_factory=list)
    sourceSurfacesExpected: list[Literal["scanner", "watchlist", "market", "manual_gap"]] = Field(
        default_factory=list
    )
    failClosed: bool = True


class UnifiedResearchQueueResponse(_ResearchQueueModel):
    schemaVersion: Literal["research_queue_v1"] = UNIFIED_RESEARCH_QUEUE_RESPONSE_SCHEMA_VERSION
    researchQueue: list[UnifiedResearchQueueItemResponse] = Field(default_factory=list, max_length=10)
    aggregateSummary: UnifiedResearchQueueAggregateSummaryResponse
    sourceSurfacesAggregated: list[Literal["scanner", "watchlist", "market", "manual_gap"]] = Field(
        default_factory=list
    )
    evidenceGaps: list[str] = Field(default_factory=list)
    dataQuality: UnifiedResearchQueueDataQualityResponse
    noAdviceDisclosure: str
    observationOnly: Literal[True] = True
    decisionGrade: Literal[False] = False


__all__ = [
    "ResearchQueueBuildInputs",
    "ResearchQueueCategory",
    "ResearchQueueDataQuality",
    "ResearchQueueEvidenceStatus",
    "ResearchQueueItem",
    "ResearchQueueItemStatus",
    "ResearchQueueResponse",
    "ResearchQueueSeedItem",
    "ResearchQueueTopLevelStatus",
    "UNIFIED_RESEARCH_QUEUE_RESPONSE_SCHEMA_VERSION",
    "UnifiedResearchQueueAggregateSummaryResponse",
    "UnifiedResearchQueueDataQualityResponse",
    "UnifiedResearchQueueFreshnessResponse",
    "UnifiedResearchQueueItemResponse",
    "UnifiedResearchQueueResponse",
    "UnifiedResearchQueueSuggestedResearchPathResponse",
]
