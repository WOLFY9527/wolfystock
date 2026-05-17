# -*- coding: utf-8 -*-
"""Event intelligence DTOs for bounded backend contract work."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.services.event_intelligence_contracts import (
    EventIntelligenceDirection,
    EventIntelligenceFreshnessStatus,
    EventIntelligenceProvenance,
    EventIntelligenceSourceType,
    EventIntelligenceType,
    validate_event_intelligence_freshness_claim,
    validate_event_intelligence_visibility,
)


class EventIntelligenceItem(BaseModel):
    model_config = ConfigDict()

    id: str = Field(..., min_length=1)
    symbol: str = Field(..., min_length=1)
    market: str = Field(..., min_length=1)
    event_type: EventIntelligenceType
    subtype: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    source_type: EventIntelligenceSourceType
    source_name: str = Field(..., min_length=1)
    source_url: Optional[str] = None
    published_at: datetime
    event_at: datetime
    confirmed_at: Optional[datetime] = None
    as_of: datetime
    confidence: float = Field(..., ge=0.0, le=1.0)
    importance_score: float = Field(..., ge=0.0, le=1.0)
    direction: EventIntelligenceDirection
    freshness_status: EventIntelligenceFreshnessStatus
    provenance: EventIntelligenceProvenance
    related_period: Optional[str] = None
    payload_refs: Optional[list[str]] = None

    @model_validator(mode="after")
    def validate_contract_guards(self) -> "EventIntelligenceItem":
        validate_event_intelligence_visibility(
            published_at=self.published_at,
            as_of=self.as_of,
        )
        validate_event_intelligence_freshness_claim(
            provenance=self.provenance,
            freshness_status=self.freshness_status,
        )
        return self


__all__ = [
    "EventIntelligenceDirection",
    "EventIntelligenceFreshnessStatus",
    "EventIntelligenceItem",
    "EventIntelligenceProvenance",
    "EventIntelligenceSourceType",
    "EventIntelligenceType",
]
