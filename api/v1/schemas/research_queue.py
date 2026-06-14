# -*- coding: utf-8 -*-
"""Standalone contract models for homepage research queue prioritization."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
]
