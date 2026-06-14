# -*- coding: utf-8 -*-
"""Bounded personal summary contract for homepage-safe portfolio/watchlist context."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


PersonalSummaryStatus = Literal["ready", "partial", "no_evidence", "unavailable"]
PersonalSummarySignalStatus = Literal[
    "normal",
    "observe",
    "review",
    "no_evidence",
    "unavailable",
    "stale",
    "stronger",
    "weaker",
    "volume_expanded",
    "range_bound",
    "sample_data",
]

PERSONAL_SUMMARY_NO_ADVICE_DISCLOSURE = (
    "Personal summary only; not personalized financial advice or a recommendation."
)


class PersonalSummaryPortfolioSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    totalValue: Optional[float] = None
    dailyChange: Optional[float] = None
    cashPercent: Optional[float] = None
    largestExposure: Optional[float] = None
    beta: Optional[float] = None
    riskScore: Optional[float] = None
    riskStatus: PersonalSummarySignalStatus = "no_evidence"
    concentrationStatus: PersonalSummarySignalStatus = "no_evidence"
    connected: bool = False
    sampleData: bool = False


class PersonalSummaryWatchlistException(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    displayName: Optional[str] = None
    symbolStatus: PersonalSummarySignalStatus = "no_evidence"
    movementStatus: PersonalSummarySignalStatus = "no_evidence"
    relativeStrengthStatus: PersonalSummarySignalStatus = "no_evidence"
    volumeStatus: PersonalSummarySignalStatus = "no_evidence"
    evidenceStatus: PersonalSummarySignalStatus = "no_evidence"
    researchStatus: PersonalSummarySignalStatus = "no_evidence"
    lastReviewedAt: Optional[str] = None
    reviewReason: Optional[str] = None


class PersonalSummaryWatchlistExceptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PersonalSummaryStatus
    items: List[PersonalSummaryWatchlistException] = Field(default_factory=list)
    staleCount: int = 0
    noEvidenceCount: int = 0


class PersonalSummaryResearchCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PersonalSummaryStatus
    missingSymbols: List[str] = Field(default_factory=list)
    staleSymbols: List[str] = Field(default_factory=list)
    coveredSymbols: List[str] = Field(default_factory=list)


class PersonalSummaryReviewQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    displayName: Optional[str] = None
    priorityStatus: PersonalSummarySignalStatus = "observe"
    evidenceStatus: PersonalSummarySignalStatus = "no_evidence"
    researchStatus: PersonalSummarySignalStatus = "no_evidence"
    lastReviewedAt: Optional[str] = None
    reviewReason: Optional[str] = None


class PersonalSummaryReviewQueue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PersonalSummaryStatus
    items: List[PersonalSummaryReviewQueueItem] = Field(default_factory=list)


class PersonalSummaryDataQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PersonalSummaryStatus
    portfolioStatus: PersonalSummaryStatus
    watchlistStatus: PersonalSummaryStatus
    researchStatus: PersonalSummaryStatus
    sampleData: bool = False
    connected: bool = False


class PersonalSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PersonalSummaryStatus
    portfolioSnapshot: PersonalSummaryPortfolioSnapshot
    watchlistExceptions: PersonalSummaryWatchlistExceptions
    researchCoverage: PersonalSummaryResearchCoverage
    reviewQueue: PersonalSummaryReviewQueue
    dataQuality: PersonalSummaryDataQuality
    noAdviceDisclosure: str = PERSONAL_SUMMARY_NO_ADVICE_DISCLOSURE
