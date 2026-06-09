# -*- coding: utf-8 -*-
"""Pure backend projection helper for TrustEvidenceSnapshotV1."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

from src.schemas.trust_evidence import (
    TRUST_EVIDENCE_SNAPSHOT_CONTRACT_VERSION,
    TrustEvidenceAvailabilityState,
    TrustEvidenceConsumerBadgeKey,
    TrustEvidenceConsumerMessageKey,
    TrustEvidenceConsumerState,
    TrustEvidenceFreshnessState,
    TrustEvidenceKey,
    TrustEvidenceSnapshotV1,
    TrustEvidenceSourceClass,
)


def build_trust_evidence_snapshot_v1(
    *,
    surface_key: TrustEvidenceKey,
    generated_at: datetime,
    availability_state: TrustEvidenceAvailabilityState | str,
    freshness_state: TrustEvidenceFreshnessState | str,
    source_class: TrustEvidenceSourceClass | str,
    consumer_state: TrustEvidenceConsumerState | str,
    consumer_message_key: TrustEvidenceConsumerMessageKey,
    consumer_badge_keys: Iterable[TrustEvidenceConsumerBadgeKey | str] = (),
    entity_key: TrustEvidenceKey | None = None,
    as_of: datetime | date | None = None,
    has_fallback: bool = False,
    is_stale: bool = False,
    is_partial: bool = False,
    is_synthetic: bool = False,
    is_admin_only_detail: bool = False,
    admin_diagnostic_refs: Iterable[TrustEvidenceKey | str] = (),
) -> TrustEvidenceSnapshotV1:
    """Build the V1 trust/evidence DTO from already-sanitized explicit fields."""

    return TrustEvidenceSnapshotV1(
        contractVersion=TRUST_EVIDENCE_SNAPSHOT_CONTRACT_VERSION,
        surfaceKey=surface_key,
        entityKey=entity_key,
        generatedAt=generated_at,
        asOf=as_of,
        availabilityState=availability_state,
        freshnessState=freshness_state,
        sourceClass=source_class,
        hasFallback=has_fallback,
        isStale=is_stale,
        isPartial=is_partial,
        isSynthetic=is_synthetic,
        isAdminOnlyDetail=is_admin_only_detail,
        consumerState=consumer_state,
        consumerMessageKey=consumer_message_key,
        consumerBadgeKeys=list(consumer_badge_keys),
        adminDiagnosticRefs=list(admin_diagnostic_refs),
    )


__all__ = ["build_trust_evidence_snapshot_v1"]
