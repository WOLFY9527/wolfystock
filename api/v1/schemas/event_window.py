# -*- coding: utf-8 -*-
"""Consumer-safe homepage event-window summary contract."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


EventWindowTopLevelStatus = Literal["ready", "partial", "no_evidence", "unavailable"]


class EventWindowCategory(str, Enum):
    EARNINGS = "earnings"
    MACRO = "macro"
    POLICY = "policy"
    COMPANY = "company"
    SECTOR_THEME = "sector_theme"
    WATCHLIST = "watchlist"
    PORTFOLIO = "portfolio"
    OTHER = "other"


class EventWindowState(str, Enum):
    UPCOMING = "upcoming"
    ACTIVE = "active"
    PASSED = "passed"
    UNKNOWN = "unknown"


class EventWindowDataQualityState(str, Enum):
    READY = "ready"
    REVIEW = "review"
    NO_EVIDENCE = "no_evidence"
    UNAVAILABLE = "unavailable"


class _EventWindowModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EventWindowDataQuality(_EventWindowModel):
    state: EventWindowDataQualityState
    label: str = Field(min_length=1, max_length=32)
    available: bool = False


class EventWindowItem(_EventWindowModel):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    category: EventWindowCategory
    windowState: EventWindowState
    startsAt: str | None = None
    endsAt: str | None = None
    relatedSymbols: list[str] = Field(default_factory=list)
    relatedThemes: list[str] = Field(default_factory=list)
    reviewReason: str = Field(min_length=1, max_length=240)
    dataQuality: EventWindowDataQuality


class EventWindowSummary(_EventWindowModel):
    status: EventWindowTopLevelStatus
    asOf: str | None = None
    windows: list[EventWindowItem] = Field(default_factory=list)
    sourceStatus: EventWindowTopLevelStatus
    dataQuality: EventWindowDataQuality
    noAdviceDisclosure: str = Field(min_length=1, max_length=200)


__all__ = [
    "EventWindowCategory",
    "EventWindowDataQuality",
    "EventWindowDataQualityState",
    "EventWindowItem",
    "EventWindowState",
    "EventWindowSummary",
    "EventWindowTopLevelStatus",
]
