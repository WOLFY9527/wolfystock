# -*- coding: utf-8 -*-
"""Contract tests for the inert TrustEvidenceSnapshotV1 DTO shape."""

from __future__ import annotations

import json
from importlib import import_module

import pytest
from pydantic import ValidationError


def _complete_payload() -> dict[str, object]:
    return {
        "contractVersion": "trust_evidence_snapshot_v1",
        "surfaceKey": "market_overview",
        "entityKey": "market_overview.hero",
        "generatedAt": "2026-06-09T13:30:00Z",
        "asOf": "2026-06-09T13:00:00Z",
        "availabilityState": "partial",
        "freshnessState": "delayed",
        "sourceClass": "official_public",
        "hasFallback": True,
        "isStale": False,
        "isPartial": True,
        "isSynthetic": False,
        "isAdminOnlyDetail": False,
        "consumerState": "PARTIAL",
        "consumerMessageKey": "trust_evidence.partial",
        "consumerBadgeKeys": ["source_delayed", "source_partial", "source_fallback"],
        "adminDiagnosticRefs": ["trust-evidence:market-overview:macro-panel"],
    }


def _snapshot_schema_type() -> type:
    module = import_module("src.schemas.trust_evidence")
    assert module.TRUST_EVIDENCE_SNAPSHOT_CONTRACT_VERSION == "trust_evidence_snapshot_v1"
    return module.TrustEvidenceSnapshotV1


def test_trust_evidence_snapshot_serializes_canonical_required_shape() -> None:
    TrustEvidenceSnapshotV1 = _snapshot_schema_type()
    snapshot = TrustEvidenceSnapshotV1(**_complete_payload())

    payload = snapshot.model_dump(mode="json")

    assert payload == {
        "contractVersion": "trust_evidence_snapshot_v1",
        "surfaceKey": "market_overview",
        "entityKey": "market_overview.hero",
        "generatedAt": "2026-06-09T13:30:00Z",
        "asOf": "2026-06-09T13:00:00Z",
        "availabilityState": "partial",
        "freshnessState": "delayed",
        "sourceClass": "official_public",
        "hasFallback": True,
        "isStale": False,
        "isPartial": True,
        "isSynthetic": False,
        "isAdminOnlyDetail": False,
        "consumerState": "PARTIAL",
        "consumerMessageKey": "trust_evidence.partial",
        "consumerBadgeKeys": ["source_delayed", "source_partial", "source_fallback"],
        "adminDiagnosticRefs": ["trust-evidence:market-overview:macro-panel"],
    }
    assert json.loads(snapshot.model_dump_json()) == payload


def test_trust_evidence_snapshot_allows_future_additive_fields() -> None:
    TrustEvidenceSnapshotV1 = _snapshot_schema_type()
    payload = {
        **_complete_payload(),
        "coverageRatio": 0.86,
        "futureConsumerSafeKey": "trust_evidence.future",
    }

    snapshot = TrustEvidenceSnapshotV1(**payload)

    assert snapshot.model_dump(mode="json")["coverageRatio"] == 0.86
    assert snapshot.model_dump(mode="json")["futureConsumerSafeKey"] == "trust_evidence.future"


def test_trust_evidence_snapshot_json_schema_locks_required_fields_and_enums() -> None:
    TrustEvidenceSnapshotV1 = _snapshot_schema_type()

    schema = TrustEvidenceSnapshotV1.model_json_schema()

    assert schema["required"] == [
        "contractVersion",
        "surfaceKey",
        "entityKey",
        "generatedAt",
        "asOf",
        "availabilityState",
        "freshnessState",
        "sourceClass",
        "hasFallback",
        "isStale",
        "isPartial",
        "isSynthetic",
        "isAdminOnlyDetail",
        "consumerState",
        "consumerMessageKey",
        "consumerBadgeKeys",
        "adminDiagnosticRefs",
    ]
    assert set(schema["$defs"]["TrustEvidenceAvailabilityState"]["enum"]) == {
        "available",
        "updating",
        "delayed",
        "partial",
        "insufficient",
        "observation_only",
        "unavailable",
    }
    assert set(schema["$defs"]["TrustEvidenceFreshnessState"]["enum"]) == {
        "live",
        "fresh",
        "delayed",
        "cached",
        "stale",
        "fallback",
        "partial",
        "synthetic",
        "unavailable",
        "unknown",
    }
    assert set(schema["$defs"]["TrustEvidenceSourceClass"]["enum"]) == {
        "official_public",
        "licensed_authorized",
        "public_proxy",
        "local_cache",
        "synthetic",
        "unknown",
    }
    assert set(schema["$defs"]["TrustEvidenceConsumerState"]["enum"]) == {
        "AVAILABLE",
        "UPDATING",
        "DELAYED",
        "PARTIAL",
        "INSUFFICIENT",
        "OBSERVATION_ONLY",
        "UNAVAILABLE",
    }
    assert set(schema["$defs"]["TrustEvidenceConsumerBadgeKey"]["enum"]) == {
        "source_current",
        "source_delayed",
        "source_stale",
        "source_partial",
        "source_fallback",
        "source_unavailable",
        "observation_only",
    }
    assert schema["properties"]["consumerMessageKey"]["pattern"] == (
        "^trust_evidence\\.[a-z][a-z0-9_.-]*$"
    )


@pytest.mark.parametrize(
    "field_name",
    [
        "contractVersion",
        "surfaceKey",
        "entityKey",
        "generatedAt",
        "asOf",
        "availabilityState",
        "freshnessState",
        "sourceClass",
        "hasFallback",
        "isStale",
        "isPartial",
        "isSynthetic",
        "isAdminOnlyDetail",
        "consumerState",
        "consumerMessageKey",
        "consumerBadgeKeys",
        "adminDiagnosticRefs",
    ],
)
def test_trust_evidence_snapshot_fails_closed_when_required_fields_are_missing(field_name: str) -> None:
    TrustEvidenceSnapshotV1 = _snapshot_schema_type()
    payload = _complete_payload()
    payload.pop(field_name)

    with pytest.raises(ValidationError):
        TrustEvidenceSnapshotV1(**payload)


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("contractVersion", "trust_evidence_snapshot_v2"),
        ("availabilityState", "fallback_source"),
        ("freshnessState", "stale_official_row"),
        ("sourceClass", "yfinance_proxy"),
        ("consumerState", "MIXED"),
        ("consumerMessageKey", "providerRuntime.cache_stale"),
        ("consumerMessageKey", "trust_evidence.cache_stale"),
        ("consumerMessageKey", "trust_evidence.polygon"),
        ("consumerBadgeKeys", ["source_partial", "polygon"]),
    ],
)
def test_trust_evidence_snapshot_bounds_enums_and_consumer_keys(field_name: str, bad_value: object) -> None:
    TrustEvidenceSnapshotV1 = _snapshot_schema_type()
    payload = {**_complete_payload(), field_name: bad_value}

    with pytest.raises(ValidationError):
        TrustEvidenceSnapshotV1(**payload)


@pytest.mark.parametrize(
    ("badge_key", "flag_name"),
    [
        ("source_stale", "isStale"),
        ("source_partial", "isPartial"),
        ("source_fallback", "hasFallback"),
    ],
)
def test_trust_evidence_snapshot_rejects_badges_without_matching_limit_flags(
    badge_key: str,
    flag_name: str,
) -> None:
    TrustEvidenceSnapshotV1 = _snapshot_schema_type()
    payload = {
        **_complete_payload(),
        "consumerBadgeKeys": [badge_key],
        "hasFallback": False,
        "isStale": False,
        "isPartial": False,
    }

    with pytest.raises(ValidationError, match=f"{badge_key} requires {flag_name}=true"):
        TrustEvidenceSnapshotV1(**payload)
