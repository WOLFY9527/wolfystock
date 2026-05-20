# -*- coding: utf-8 -*-
"""Tests for the append-only market persistence snapshot contract."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from src.services.market_persistence_evidence_service import synthesize_market_persistence
from src.services.market_persistence_snapshot_store import (
    InMemoryMarketPersistenceSnapshotStore,
    MarketPersistenceSnapshotDTO,
    normalize_persistence_snapshot,
    select_persistence_snapshot_windows,
    snapshots_to_persistence_evidence,
)


BASE_TIME = datetime(2026, 5, 20, 10, tzinfo=timezone.utc)


def _iso(days_ago: int, *, hour_offset: int = 0) -> str:
    return (BASE_TIME - timedelta(days=days_ago, hours=hour_offset)).isoformat()


def _snapshot(
    days_ago: int,
    *,
    surface: str = "market_overview",
    metric_key: str = "liquidity_regime",
    value: float = 0.74,
    score: float | None = None,
    state_label: str = "risk_on",
    source: str = "official_fixture",
    source_type: str = "official_public",
    source_tier: str = "official_public",
    trust_level: str = "high",
    freshness: str = "fresh",
    observation_only: bool = False,
    score_contribution_allowed: bool = True,
    degradation_reason: str | None = None,
    missing_provider_reason: str | None = None,
    is_fallback: bool = False,
    is_stale: bool = False,
    is_partial: bool = False,
    is_unavailable: bool = False,
    provider_id: str = "official_fixture",
    capability: str = "market_regime",
    taxonomy_only: bool = False,
    snapshot_created_days_ago: int | None = None,
) -> dict:
    created_days = days_ago if snapshot_created_days_ago is None else snapshot_created_days_ago
    return {
        "surface": surface,
        "metricKey": metric_key,
        "value": value,
        "score": value if score is None else score,
        "stateLabel": state_label,
        "source": source,
        "sourceType": source_type,
        "sourceTier": source_tier,
        "trustLevel": trust_level,
        "freshness": freshness,
        "observationOnly": observation_only,
        "scoreContributionAllowed": score_contribution_allowed,
        "asOf": _iso(days_ago),
        "updatedAt": _iso(days_ago),
        "snapshotCreatedAt": _iso(created_days, hour_offset=-1),
        "degradationReason": degradation_reason,
        "missingProviderReason": missing_provider_reason,
        "isFallback": is_fallback,
        "isStale": is_stale,
        "isPartial": is_partial,
        "isUnavailable": is_unavailable,
        "providerId": provider_id,
        "capability": capability,
        "schemaVersion": "market_persistence_snapshot_v1",
        "algorithmVersion": "unit-test-v1",
        "taxonomyOnly": taxonomy_only,
    }


def test_append_only_distinct_snapshots_are_preserved_and_source_confidence_fields_survive() -> None:
    store = InMemoryMarketPersistenceSnapshotStore()
    records = store.append_many([_snapshot(0), _snapshot(1), _snapshot(5), _snapshot(20)])

    assert len(records) == 4
    assert len(store.all_snapshots()) == 4
    assert len({record.snapshot_id for record in records}) == 4
    assert [record.as_of for record in store.all_snapshots()] == [_iso(0), _iso(1), _iso(5), _iso(20)]

    payload = records[0].to_dict()
    assert payload["source"] == "official_fixture"
    assert payload["sourceType"] == "official_public"
    assert payload["sourceTier"] == "official_public"
    assert payload["trustLevel"] == "high"
    assert payload["freshness"] == "fresh"
    assert payload["observationOnly"] is False
    assert payload["scoreContributionAllowed"] is True
    assert payload["payloadHash"]
    assert payload["inputHash"]


def test_duplicate_identical_payloads_are_de_duplicated_without_rewriting_history() -> None:
    store = InMemoryMarketPersistenceSnapshotStore()
    payload = _snapshot(0)

    first = store.append(payload)
    second = store.append(dict(payload))

    assert first == second
    assert len(store.all_snapshots()) == 1
    assert store.deduplicated_count == 1


def test_repeated_cached_snapshot_with_same_as_of_cannot_count_as_multiple_windows() -> None:
    repeated_cache_loads = [
        _snapshot(
            0,
            source="market_overview_snapshot",
            source_type="cache_snapshot",
            source_tier="cache_snapshot",
            trust_level="usable_with_caution",
            freshness="cached",
            snapshot_created_days_ago=created_days,
        )
        for created_days in (0, 1, 5, 20)
    ]
    store = InMemoryMarketPersistenceSnapshotStore(repeated_cache_loads)

    windows = select_persistence_snapshot_windows(store.all_snapshots())

    assert len(store.all_snapshots()) == 4
    assert [window.window for window in windows] == ["latest"]
    assert windows[0].snapshot.as_of == _iso(0)


def test_fallback_mock_static_synthetic_taxonomy_and_unavailable_snapshots_are_not_trend_authority() -> None:
    rejected = [
        _snapshot(0, source_type="mock", freshness="mock"),
        _snapshot(1, source_tier="static_fallback", is_fallback=True),
        _snapshot(5, source_type="synthetic_fixture", source="synthetic_fixture"),
        _snapshot(20, taxonomy_only=True, capability="taxonomy_theme"),
        _snapshot(
            21,
            source_tier="unavailable",
            trust_level="unavailable",
            freshness="unavailable",
            is_unavailable=True,
            missing_provider_reason="provider_unavailable",
        ),
    ]
    accepted = _snapshot(0, metric_key="credit_stress", value=0.31)

    windows = select_persistence_snapshot_windows([*rejected, accepted])
    evidence = snapshots_to_persistence_evidence([*rejected, accepted])

    assert [window.snapshot.metric_key for window in windows] == ["credit_stress"]
    assert all(window.authority_level == "score_grade" for window in windows)
    assert [item.metric for item in evidence] == ["credit_stress"]


def test_stale_snapshots_are_degraded_context_and_lower_t224h_quality() -> None:
    fresh = [_snapshot(days, value=value) for days, value in ((0, 0.82), (1, 0.8), (5, 0.78), (20, 0.76))]
    stale = [
        _snapshot(
            days,
            value=value,
            freshness="stale",
            is_stale=True,
            degradation_reason="snapshot_stale",
        )
        for days, value in ((0, 0.82), (1, 0.8), (5, 0.78), (20, 0.76))
    ]

    stale_windows = select_persistence_snapshot_windows(stale, include_degraded_context=True)
    fresh_result = synthesize_market_persistence(snapshots_to_persistence_evidence(fresh))
    stale_result = synthesize_market_persistence(snapshots_to_persistence_evidence(stale))

    assert {window.authority_level for window in stale_windows} == {"degraded_context"}
    assert stale_result.evidence_quality["averageEvidenceWeight"] < fresh_result.evidence_quality["averageEvidenceWeight"]
    assert all(item["freshness"] == "stale" for item in stale_result.evidence_items)


def test_only_latest_converted_record_returns_insufficient_history_through_t224h() -> None:
    evidence = snapshots_to_persistence_evidence([_snapshot(0, value=0.44)])
    result = synthesize_market_persistence(evidence)

    assert len(evidence) == 1
    assert isinstance(evidence[0], MarketPersistenceSnapshotDTO.evidence_snapshot_type())
    assert result.persistence_status == "insufficient_history"
    assert tuple(result.windows) == ("latest",)


def test_1d_5d_20d_window_selection_returns_expected_distinct_records() -> None:
    snapshots = [
        _snapshot(0, metric_key="latest_metric", value=0.7),
        _snapshot(1, metric_key="one_day_metric", value=0.68),
        _snapshot(5, metric_key="five_day_metric", value=0.65),
        _snapshot(20, metric_key="twenty_day_metric", value=0.61),
        _snapshot(20, metric_key="duplicate_twenty_day_metric", value=0.99, snapshot_created_days_ago=19),
    ]

    windows = select_persistence_snapshot_windows(snapshots)

    assert [window.window for window in windows] == ["latest", "1d", "5d", "20d"]
    assert [window.snapshot.metric_key for window in windows] == [
        "latest_metric",
        "one_day_metric",
        "five_day_metric",
        "duplicate_twenty_day_metric",
    ]
    assert len({window.bucket_key for window in windows}) == 4


def test_normalization_accepts_camel_and_snake_case_and_generates_stable_ids() -> None:
    camel = normalize_persistence_snapshot(_snapshot(0))
    snake = normalize_persistence_snapshot(
        {
            **_snapshot(0),
            "metric_key": "liquidity_regime",
            "source_type": "official_public",
            "source_tier": "official_public",
            "trust_level": "high",
            "snapshot_created_at": _iso(0, hour_offset=-1),
            "provider_id": "official_fixture",
            "score_contribution_allowed": True,
        }
    )

    assert camel.snapshot_id == snake.snapshot_id
    assert camel.payload_hash == snake.payload_hash
    assert camel.metric_key == "liquidity_regime"
    assert camel.schema_version == "market_persistence_snapshot_v1"
    assert camel.algorithm_version == "unit-test-v1"


def test_sanitized_contract_emits_no_raw_provider_payload_or_secret_like_fields() -> None:
    record = normalize_persistence_snapshot(
        {
            **_snapshot(0),
            "rawProviderPayload": {"close": 100, "api_key": "SECRET_KEY_VALUE"},
            "providerPayload": {"token": "SECRET_TOKEN_VALUE"},
            "debug": {"password": "SECRET_PASSWORD_VALUE"},
            "api_key": "SECRET_KEY_VALUE",
            "accessToken": "SECRET_TOKEN_VALUE",
        }
    )

    dumped = json.dumps(record.to_dict(), sort_keys=True)

    for forbidden in (
        "rawProviderPayload",
        "providerPayload",
        "SECRET_KEY_VALUE",
        "SECRET_TOKEN_VALUE",
        "SECRET_PASSWORD_VALUE",
        "api_key",
        "accessToken",
        "password",
    ):
        assert forbidden not in dumped
