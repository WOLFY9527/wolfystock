# -*- coding: utf-8 -*-
"""Schemas for the AI Stock Research contract scaffold."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


RESEARCH_CONSUMER_ACTION_BOUNDARY = "no_advice"
RESEARCH_NO_ADVICE_DISCLOSURE = (
    "No advice: structured research context only; not a directive or instruction "
    "for any market action."
)


class ResearchSummary(BaseModel):
    status: Literal["available", "degraded", "unavailable"]
    text: str
    evidence_count: int = 0


class ResearchFactor(BaseModel):
    label: str
    evidence: list[str] = Field(default_factory=list)
    status: Literal["available", "degraded", "unavailable", "uncertain"] = "uncertain"


class ResearchDataQuality(BaseModel):
    status: Literal["available", "degraded", "unavailable"]
    evidence_status: Literal["available", "degraded", "unavailable"]
    missing_evidence: list[str] = Field(default_factory=list)
    external_calls_executed: bool = False
    llm_execution: bool = False


class ResearchFreshness(BaseModel):
    status: Literal["fresh", "delayed", "stale", "unavailable", "unknown"]
    as_of: str | None = None
    source_count: int = 0


class ResearchSource(BaseModel):
    name: str
    category: str
    status: Literal["ready", "delayed", "cached", "partial", "unavailable", "no_evidence"]
    as_of: str | None = None


class ResearchUnavailableState(BaseModel):
    state: Literal["unavailable", "degraded"]
    reason: str
    message: str


class AIStockResearchResponse(BaseModel):
    ticker: str
    market: str
    research_window: str
    generated_at: str
    as_of: str
    data_quality: ResearchDataQuality
    evidence_status: Literal["available", "degraded", "unavailable"]
    summary: ResearchSummary
    bullish_factors: list[ResearchFactor] = Field(default_factory=list)
    bearish_factors: list[ResearchFactor] = Field(default_factory=list)
    neutral_or_uncertain_factors: list[ResearchFactor] = Field(default_factory=list)
    technical_state: dict[str, Any] | None = None
    portfolio_watchlist_relevance: dict[str, Any] | None = None
    sources: list[ResearchSource] = Field(default_factory=list)
    freshness: ResearchFreshness
    risk_disclosure: str
    no_advice_disclosure: str
    consumer_action_boundary: Literal["no_advice"] = RESEARCH_CONSUMER_ACTION_BOUNDARY
    unavailable: ResearchUnavailableState | None = None
