# -*- coding: utf-8 -*-
"""Inert shared enums and guards for event intelligence contracts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum


EVENT_INTELLIGENCE_CONTRACT_VERSION = "event_intelligence_contract_v1"


class EventIntelligenceType(str, Enum):
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    CORPORATE_ACTION = "corporate_action"
    REGULATORY = "regulatory"
    MACRO = "macro"
    MANAGEMENT = "management"
    PRODUCT = "product"
    ANALYST = "analyst"
    CALENDAR = "calendar"
    OTHER = "other"


class EventIntelligenceSourceType(str, Enum):
    COMPANY_FILING = "company_filing"
    EXCHANGE_NOTICE = "exchange_notice"
    NEWSWIRE = "newswire"
    COMPANY_IR = "company_ir"
    GOVERNMENT_RELEASE = "government_release"
    ANALYST_RESEARCH = "analyst_research"
    EARNINGS_CALENDAR = "earnings_calendar"
    CURATED_DATASET = "curated_dataset"
    OTHER = "other"


class EventIntelligenceDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class EventIntelligenceFreshnessStatus(str, Enum):
    LIVE = "live"
    FRESH = "fresh"
    DELAYED = "delayed"
    STALE = "stale"
    FALLBACK = "fallback"
    UNKNOWN = "unknown"


class EventIntelligenceProvenance(str, Enum):
    OFFICIAL_PUBLIC = "official_public"
    EXCHANGE_PUBLIC = "exchange_public"
    COMPANY_PRIMARY = "company_primary"
    LICENSED_THIRD_PARTY = "licensed_third_party"
    PUBLIC_PROXY = "public_proxy"
    UNOFFICIAL_PROXY = "unofficial_proxy"
    FALLBACK_STATIC = "fallback_static"
    SYNTHETIC_FIXTURE = "synthetic_fixture"
    UNKNOWN = "unknown"


_LIVE_OR_FRESH_STATUSES = frozenset(
    {
        EventIntelligenceFreshnessStatus.LIVE,
        EventIntelligenceFreshnessStatus.FRESH,
    }
)
_NON_LIVE_PROVENANCE = frozenset(
    {
        EventIntelligenceProvenance.FALLBACK_STATIC,
        EventIntelligenceProvenance.SYNTHETIC_FIXTURE,
        EventIntelligenceProvenance.UNKNOWN,
    }
)


def validate_event_intelligence_visibility(*, published_at: datetime, as_of: datetime) -> None:
    if published_at > as_of:
        raise ValueError("published_at cannot be after as_of")


def validate_event_intelligence_freshness_claim(
    *,
    provenance: EventIntelligenceProvenance,
    freshness_status: EventIntelligenceFreshnessStatus,
) -> None:
    if provenance in _NON_LIVE_PROVENANCE and freshness_status in _LIVE_OR_FRESH_STATUSES:
        raise ValueError("unknown or fallback states cannot claim live or fresh")


__all__ = [
    "EVENT_INTELLIGENCE_CONTRACT_VERSION",
    "EventIntelligenceDirection",
    "EventIntelligenceFreshnessStatus",
    "EventIntelligenceProvenance",
    "EventIntelligenceSourceType",
    "EventIntelligenceType",
    "validate_event_intelligence_freshness_claim",
    "validate_event_intelligence_visibility",
]
