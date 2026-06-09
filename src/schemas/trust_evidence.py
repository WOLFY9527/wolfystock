# -*- coding: utf-8 -*-
"""Canonical TrustEvidenceSnapshotV1 DTO schema."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator


TRUST_EVIDENCE_SNAPSHOT_CONTRACT_VERSION = "trust_evidence_snapshot_v1"

TrustEvidenceKey = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$",
    ),
]


class TrustEvidenceAvailabilityState(str, Enum):
    AVAILABLE = "available"
    UPDATING = "updating"
    DELAYED = "delayed"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"
    OBSERVATION_ONLY = "observation_only"
    UNAVAILABLE = "unavailable"


class TrustEvidenceFreshnessState(str, Enum):
    LIVE = "live"
    FRESH = "fresh"
    DELAYED = "delayed"
    CACHED = "cached"
    STALE = "stale"
    FALLBACK = "fallback"
    PARTIAL = "partial"
    SYNTHETIC = "synthetic"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class TrustEvidenceSourceClass(str, Enum):
    OFFICIAL_PUBLIC = "official_public"
    LICENSED_AUTHORIZED = "licensed_authorized"
    PUBLIC_PROXY = "public_proxy"
    LOCAL_CACHE = "local_cache"
    SYNTHETIC = "synthetic"
    UNKNOWN = "unknown"


class TrustEvidenceConsumerState(str, Enum):
    AVAILABLE = "AVAILABLE"
    UPDATING = "UPDATING"
    DELAYED = "DELAYED"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    OBSERVATION_ONLY = "OBSERVATION_ONLY"
    UNAVAILABLE = "UNAVAILABLE"


TrustEvidenceConsumerMessageKey = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^trust_evidence\.[a-z][a-z0-9_.-]*$",
    ),
]


class TrustEvidenceConsumerBadgeKey(str, Enum):
    SOURCE_CURRENT = "source_current"
    SOURCE_DELAYED = "source_delayed"
    SOURCE_STALE = "source_stale"
    SOURCE_PARTIAL = "source_partial"
    SOURCE_FALLBACK = "source_fallback"
    SOURCE_UNAVAILABLE = "source_unavailable"
    OBSERVATION_ONLY = "observation_only"


_BADGE_FLAG_REQUIREMENTS = {
    TrustEvidenceConsumerBadgeKey.SOURCE_STALE.value: "isStale",
    TrustEvidenceConsumerBadgeKey.SOURCE_PARTIAL.value: "isPartial",
    TrustEvidenceConsumerBadgeKey.SOURCE_FALLBACK.value: "hasFallback",
}
_FORBIDDEN_CONSUMER_KEY_FRAGMENTS = (
    "cache_stale",
    "fallback_source",
    "fallback_used",
    "fred",
    "marketcache",
    "official_overlay_stale_using_proxy",
    "polygon",
    "providerruntime",
    "proxy_only_missing_real_source",
    "routerejected",
    "scorecontributionallowed",
    "sourceauthorityallowed",
    "stale_official_row",
    "tushare",
    "yfinance_proxy",
)


class TrustEvidenceSnapshotV1(BaseModel):
    """Inert additive DTO boundary for trust/evidence snapshots."""

    model_config = ConfigDict(extra="allow", use_enum_values=True)

    contractVersion: Literal["trust_evidence_snapshot_v1"]
    surfaceKey: TrustEvidenceKey
    entityKey: Optional[TrustEvidenceKey]
    generatedAt: datetime
    asOf: datetime | date | None
    availabilityState: TrustEvidenceAvailabilityState
    freshnessState: TrustEvidenceFreshnessState
    sourceClass: TrustEvidenceSourceClass
    hasFallback: bool
    isStale: bool
    isPartial: bool
    isSynthetic: bool
    isAdminOnlyDetail: bool
    consumerState: TrustEvidenceConsumerState
    consumerMessageKey: TrustEvidenceConsumerMessageKey
    consumerBadgeKeys: list[TrustEvidenceConsumerBadgeKey]
    adminDiagnosticRefs: list[TrustEvidenceKey]

    @field_validator("consumerMessageKey")
    @classmethod
    def validate_consumer_message_key_is_not_raw_debug_text(cls, value: str) -> str:
        normalized = value.lower()
        for fragment in _FORBIDDEN_CONSUMER_KEY_FRAGMENTS:
            if fragment in normalized:
                raise ValueError(f"consumerMessageKey contains raw debug fragment: {fragment}")
        return value

    @model_validator(mode="after")
    def validate_consumer_badges_match_limit_flags(self) -> "TrustEvidenceSnapshotV1":
        for badge_key, flag_name in _BADGE_FLAG_REQUIREMENTS.items():
            if badge_key in self.consumerBadgeKeys and not getattr(self, flag_name):
                raise ValueError(f"{badge_key} requires {flag_name}=true")
        return self


__all__ = [
    "TRUST_EVIDENCE_SNAPSHOT_CONTRACT_VERSION",
    "TrustEvidenceAvailabilityState",
    "TrustEvidenceConsumerBadgeKey",
    "TrustEvidenceConsumerMessageKey",
    "TrustEvidenceConsumerState",
    "TrustEvidenceFreshnessState",
    "TrustEvidenceKey",
    "TrustEvidenceSnapshotV1",
    "TrustEvidenceSourceClass",
]
