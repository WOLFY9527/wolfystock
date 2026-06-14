# -*- coding: utf-8 -*-
"""Safe contract DTOs for the homepage market-moving event radar."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator


EVENT_RADAR_SNAPSHOT_CONTRACT_VERSION = "event_radar_snapshot_v1"

_FORBIDDEN_ADVICE_PATTERNS = (
    re.compile(r"\bbuy\b", re.IGNORECASE),
    re.compile(r"\bsell\b", re.IGNORECASE),
    re.compile(r"\badd position\b", re.IGNORECASE),
    re.compile(r"\breduce position\b", re.IGNORECASE),
    re.compile(r"\bstop-loss\b", re.IGNORECASE),
    re.compile(r"\btake-profit\b", re.IGNORECASE),
    re.compile(r"\btarget price\b", re.IGNORECASE),
    re.compile(r"\bpredicted return\b", re.IGNORECASE),
    re.compile(r"\bai recommends\b", re.IGNORECASE),
    re.compile(r"\bplace order\b", re.IGNORECASE),
    re.compile(r"\bsubmit order\b", re.IGNORECASE),
)
_FORBIDDEN_LEAK_PATTERNS = (
    re.compile(r"traceback", re.IGNORECASE),
    re.compile(r"exception", re.IGNORECASE),
    re.compile(r"rawpayload", re.IGNORECASE),
    re.compile(r"providerpayload", re.IGNORECASE),
    re.compile(r"/users/", re.IGNORECASE),
    re.compile(r"api_key", re.IGNORECASE),
    re.compile(r"sessionid", re.IGNORECASE),
    re.compile(r"session_id", re.IGNORECASE),
    re.compile(r"bearer\s+", re.IGNORECASE),
    re.compile(r"sk-[a-z0-9]+", re.IGNORECASE),
)


class EventRadarCategory(str, Enum):
    MACRO = "macro"
    POLICY = "policy"
    EARNINGS = "earnings"
    COMPANY = "company"
    SECTOR_THEME = "sector_theme"
    WATCHLIST = "watchlist"
    PORTFOLIO = "portfolio"
    GEOPOLITICAL = "geopolitical"
    OTHER = "other"


class EventRadarImpactStatus(str, Enum):
    OBSERVE = "observe"
    REVIEW = "review"
    HIGH_ATTENTION = "high_attention"
    NO_EVIDENCE = "no_evidence"
    UNAVAILABLE = "unavailable"


class EventRadarSourceStatus(str, Enum):
    READY = "ready"
    NO_EVIDENCE = "no_evidence"
    UNAVAILABLE = "unavailable"


class EventRadarFreshness(str, Enum):
    FRESH = "fresh"
    DELAYED = "delayed"
    STALE = "stale"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


def _ensure_safe_text(value: str, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    for pattern in _FORBIDDEN_ADVICE_PATTERNS:
        if pattern.search(text):
            raise ValueError(f"{field_name} contains forbidden trading advice language")
    for pattern in _FORBIDDEN_LEAK_PATTERNS:
        if pattern.search(text):
            raise ValueError(f"{field_name} contains forbidden diagnostics or secret-like content")
    return text


def _normalize_safe_list(values: Iterable[Any], *, field_name: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _ensure_safe_text(str(value), field_name=field_name)
        if text not in seen:
            normalized.append(text)
            seen.add(text)
    return normalized


class EventRadarItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=160)
    category: EventRadarCategory
    impactStatus: EventRadarImpactStatus
    affectedSectors: list[str] = Field(default_factory=list)
    affectedThemes: list[str] = Field(default_factory=list)
    relatedSymbols: list[str] = Field(default_factory=list)
    relatedMarketSignals: list[str] = Field(default_factory=list)
    reviewModules: list[str] = Field(default_factory=list)
    sourceStatus: EventRadarSourceStatus
    freshness: EventRadarFreshness
    summary: str = Field(..., min_length=1, max_length=600)
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_safety_and_shape(self) -> "EventRadarItem":
        self.id = _ensure_safe_text(self.id, field_name="id")
        self.title = _ensure_safe_text(self.title, field_name="title")
        self.summary = _ensure_safe_text(self.summary, field_name="summary")
        self.noAdviceDisclosure = _ensure_safe_text(
            self.noAdviceDisclosure,
            field_name="noAdviceDisclosure",
        )
        self.affectedSectors = _normalize_safe_list(self.affectedSectors, field_name="affectedSectors")
        self.affectedThemes = _normalize_safe_list(self.affectedThemes, field_name="affectedThemes")
        self.relatedSymbols = _normalize_safe_list(self.relatedSymbols, field_name="relatedSymbols")
        self.relatedMarketSignals = _normalize_safe_list(
            self.relatedMarketSignals,
            field_name="relatedMarketSignals",
        )
        self.reviewModules = _normalize_safe_list(self.reviewModules, field_name="reviewModules")

        if not self.reviewModules:
            raise ValueError("reviewModules must include at least one review target")
        if not any(
            (
                self.affectedSectors,
                self.affectedThemes,
                self.relatedSymbols,
                self.relatedMarketSignals,
            )
        ):
            raise ValueError("event radar items must include impact-oriented affected fields")
        if self.sourceStatus is EventRadarSourceStatus.NO_EVIDENCE:
            raise ValueError("event items cannot claim sourceStatus=no_evidence")
        if self.sourceStatus is EventRadarSourceStatus.UNAVAILABLE:
            raise ValueError("event items cannot claim sourceStatus=unavailable")
        if self.impactStatus in {EventRadarImpactStatus.NO_EVIDENCE, EventRadarImpactStatus.UNAVAILABLE}:
            raise ValueError("event items must represent an actual impact-oriented event state")
        return self


class EventRadarSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: str = Field(default=EVENT_RADAR_SNAPSHOT_CONTRACT_VERSION)
    asOf: datetime
    sourceStatus: EventRadarSourceStatus
    freshness: EventRadarFreshness
    summary: str = Field(..., min_length=1, max_length=240)
    itemCount: int = Field(..., ge=0)
    items: list[EventRadarItem] = Field(default_factory=list)
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_snapshot(self) -> "EventRadarSnapshot":
        self.summary = _ensure_safe_text(self.summary, field_name="summary")
        self.noAdviceDisclosure = _ensure_safe_text(
            self.noAdviceDisclosure,
            field_name="noAdviceDisclosure",
        )

        if self.schemaVersion != EVENT_RADAR_SNAPSHOT_CONTRACT_VERSION:
            raise ValueError("schemaVersion mismatch")
        if self.itemCount != len(self.items):
            raise ValueError("itemCount must match items length")
        if self.sourceStatus is EventRadarSourceStatus.NO_EVIDENCE:
            if self.items:
                raise ValueError("no_evidence snapshots must not contain event items")
            if self.freshness is not EventRadarFreshness.UNAVAILABLE:
                raise ValueError("no_evidence snapshots must use freshness=unavailable")
        if self.sourceStatus is EventRadarSourceStatus.UNAVAILABLE:
            if self.items:
                raise ValueError("unavailable snapshots must not contain event items")
            if self.freshness is not EventRadarFreshness.UNAVAILABLE:
                raise ValueError("unavailable snapshots must use freshness=unavailable")
        return self


__all__ = [
    "EVENT_RADAR_SNAPSHOT_CONTRACT_VERSION",
    "EventRadarCategory",
    "EventRadarFreshness",
    "EventRadarImpactStatus",
    "EventRadarItem",
    "EventRadarSnapshot",
    "EventRadarSourceStatus",
]
