# -*- coding: utf-8 -*-
"""Offline tests for the inert Data Coverage Matrix row builder."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.services.data_coverage_matrix_builder import (
    build_data_coverage_matrix_row,
    resolve_data_coverage_surface_registry_entry,
)
from src.services.data_coverage_matrix_batch import build_data_coverage_matrix_batch
from src.services.data_coverage_matrix_contract import (
    RightToDisplay,
    project_consumer_data_coverage,
)
from src.services.data_coverage_surface_registry import DATA_COVERAGE_SURFACE_REGISTRY_BY_SURFACE_FIELD
from src.services.data_coverage_surface_snapshot import build_data_coverage_surface_snapshot


_SINGLE_STOCK_FORBIDDEN_CONSUMER_TERMS = (
    "provider",
    "providerId",
    "providerLabel",
    "source",
    "sourceId",
    "sourceLabel",
    "sourceType",
    "sourceTier",
    "cache",
    "cacheStatus",
    "cache_key",
    "debug",
    "backend",
    "reasonCode",
    "reason_code",
    "rawDiagnostics",
    "coverageRatio",
    "coverage_ratio",
    "sourceAuthorityAllowed",
    "scoreContributionAllowed",
    "authorityGrant",
    "decisionGrade",
    "rightToDisplay",
    "consumerBadge",
    "trustBadge",
    "trustLabel",
    "single_stock_summary_status",
    "single_stock_evidence",
)


def test_market_overview_builder_accepts_registry_entry_and_returns_valid_row() -> None:
    result = build_data_coverage_matrix_row(
        {
            "providerId": "polygon_primary",
            "providerLabel": "Polygon",
            "sourceId": "us_equities_feed",
            "sourceLabel": "US Equities Feed",
            "sourceType": "authorized_licensed_feed",
            "sourceTier": "official_public",
            "freshnessState": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "authorityGrant": True,
            "decisionGrade": True,
            "rightToDisplay": "granted",
        },
        registry_entry=DATA_COVERAGE_SURFACE_REGISTRY_BY_SURFACE_FIELD[("market_overview", "market_regime")],
    )

    assert result.validation.is_valid is True
    assert result.registry_entry.surface_id == "market_overview"
    assert result.normalized_contract.surface_id == "market_overview"
    assert result.normalized_contract.route_id == "/zh/market-overview"
    assert result.normalized_contract.audience == "consumer"
    assert result.normalized_contract.field_key == "market_regime"
    assert result.normalized_contract.evidence_family == "market_regime"
    assert result.normalized_contract.observation_only is False
    assert result.normalized_contract.right_to_display is RightToDisplay.GRANTED
    assert result.to_dict()["decisionGrade"] is True


def test_market_overview_adoption_proof_builds_fail_closed_row_batch_and_snapshot() -> None:
    metadata = {
        "providerId": "market_overview_provider_descriptor",
        "providerLabel": "Market Overview Provider Descriptor",
        "sourceId": "market_regime_source_descriptor",
        "sourceLabel": "Market Regime Source Descriptor",
        "sourceType": "authorized_licensed_feed",
        "sourceTier": "official_public",
        "freshnessState": "fresh",
        "asOf": "2026-06-08T09:30:00Z",
        "lastUpdated": "2026-06-08T09:31:00Z",
    }

    row_result = build_data_coverage_matrix_row(
        metadata,
        surface_id="market_overview",
        field_key="market_regime",
    )
    row = row_result.to_dict()
    issues = {issue.code for issue in row_result.validation.issues}

    assert issues >= {
        "missing_source_authority",
        "missing_score_contribution",
        "missing_right_to_display",
    }
    assert row["surfaceId"] == "market_overview"
    assert row["routeId"] == "/zh/market-overview"
    assert row["audience"] == "consumer"
    assert row["fieldKey"] == "market_regime"
    assert row["evidenceFamily"] == "market_regime"
    assert row["freshnessState"] == "fresh"
    assert row["sourceAuthorityAllowed"] is False
    assert row["scoreContributionAllowed"] is False
    assert row["authorityGrant"] is False
    assert row["decisionGrade"] is False
    assert row["observationOnly"] is True
    assert row["rightToDisplay"] == "unavailable"
    assert row["diagnosticOnly"] is True
    assert row["providerRuntimeCalled"] is False
    assert row["networkCallsEnabled"] is False
    assert row["marketCacheMutation"] is False

    batch_result = build_data_coverage_matrix_batch(
        [
            {
                **metadata,
                "surfaceId": "market_overview",
                "fieldKey": "market_regime",
            }
        ]
    )
    batch = batch_result.to_dict()

    assert batch["rowCounts"] == {
        "input": 1,
        "built": 1,
        "valid": 0,
        "invalid": 1,
        "errors": 1,
    }
    assert batch["rows"] == [row]
    assert batch["guardPosture"] == {
        "diagnosticOnly": True,
        "providerRuntimeCalled": False,
        "networkCallsEnabled": False,
        "marketCacheMutation": False,
    }
    assert set(batch["errors"][0]["codes"]) >= issues

    snapshot = build_data_coverage_surface_snapshot(batch["rows"]).to_dict()

    assert snapshot == {
        "snapshotVersion": "data_coverage_surface_snapshot_v1",
        "surfaceId": "market_overview",
        "routeId": "/zh/market-overview",
        "audience": "consumer",
        "consumerState": "UNAVAILABLE",
        "confidencePosture": "UNAVAILABLE",
        "consumerSummary": "UNAVAILABLE",
        "asOf": "2026-06-08T09:30:00Z",
        "rowCount": 1,
        "availableRowCount": 0,
        "limitedRowCount": 0,
        "blockedRowCount": 0,
        "unavailableRowCount": 1,
    }


def test_options_adoption_proof_builds_fail_closed_row_batch_and_snapshot() -> None:
    metadata = {
        "providerId": "options_market_structure_provider_descriptor",
        "providerLabel": "Options Market Structure Provider Descriptor",
        "sourceId": "options_market_structure_source_descriptor",
        "sourceLabel": "Options Market Structure Source Descriptor",
        "sourceType": "official_public",
        "sourceTier": "provider_descriptor_only",
        "freshnessState": "fresh",
        "asOf": "2026-06-08T09:35:00Z",
        "authorityGrant": True,
        "decisionGrade": True,
    }

    row_result = build_data_coverage_matrix_row(
        metadata,
        surface_id="options",
        field_key="options_setup_status",
    )
    row = row_result.to_dict()
    issues = {issue.code for issue in row_result.validation.issues}

    assert row_result.validation.is_valid is False
    assert issues >= {
        "missing_source_authority",
        "missing_score_contribution",
        "missing_right_to_display",
        "authority_grant_without_prerequisites",
        "decision_grade_without_prerequisites",
    }
    assert row_result.registry_entry.surface_id == "options"
    assert row_result.registry_entry.route_id == "/zh/options-lab"
    assert row_result.registry_entry.audience.value == "consumer"
    assert row_result.registry_entry.field_key == "options_setup_status"
    assert row_result.registry_entry.evidence_family == "options_market_structure"
    assert row_result.raw_contract.freshness_state.value == "fresh"
    assert row_result.raw_contract.provider_id == "options_market_structure_provider_descriptor"
    assert row_result.raw_contract.source_id == "options_market_structure_source_descriptor"
    assert row_result.normalized_contract.surface_id == "options"
    assert row_result.normalized_contract.route_id == "/zh/options-lab"
    assert row_result.normalized_contract.audience == "consumer"
    assert row_result.normalized_contract.field_key == "options_setup_status"
    assert row_result.normalized_contract.evidence_family == "options_market_structure"
    assert row_result.normalized_contract.source_authority_allowed is False
    assert row_result.normalized_contract.right_to_display is RightToDisplay.UNAVAILABLE
    assert row_result.normalized_contract.score_contribution_allowed is False
    assert row_result.normalized_contract.authority_grant is False
    assert row_result.normalized_contract.decision_grade is False
    assert row_result.normalized_contract.observation_only is True
    assert row["surfaceId"] == "options"
    assert row["routeId"] == "/zh/options-lab"
    assert row["audience"] == "consumer"
    assert row["fieldKey"] == "options_setup_status"
    assert row["evidenceFamily"] == "options_market_structure"
    assert row["freshnessState"] == "fresh"
    assert row["sourceAuthorityAllowed"] is False
    assert row["scoreContributionAllowed"] is False
    assert row["authorityGrant"] is False
    assert row["decisionGrade"] is False
    assert row["observationOnly"] is True
    assert row["rightToDisplay"] == "unavailable"
    assert row["diagnosticOnly"] is True
    assert row["providerRuntimeCalled"] is False
    assert row["networkCallsEnabled"] is False
    assert row["marketCacheMutation"] is False

    batch_result = build_data_coverage_matrix_batch(
        [
            {
                **metadata,
                "surfaceId": "options",
                "fieldKey": "options_setup_status",
            }
        ]
    )
    batch = batch_result.to_dict()

    assert batch["rowCounts"] == {
        "input": 1,
        "built": 1,
        "valid": 0,
        "invalid": 1,
        "errors": 1,
    }
    assert batch["rows"] == [row]
    assert batch["guardPosture"] == {
        "diagnosticOnly": True,
        "providerRuntimeCalled": False,
        "networkCallsEnabled": False,
        "marketCacheMutation": False,
    }
    assert set(batch["errors"][0]["codes"]) >= issues

    snapshot = build_data_coverage_surface_snapshot(batch["rows"]).to_dict()

    assert snapshot == {
        "snapshotVersion": "data_coverage_surface_snapshot_v1",
        "surfaceId": "options",
        "routeId": "/zh/options-lab",
        "audience": "consumer",
        "consumerState": "UNAVAILABLE",
        "confidencePosture": "UNAVAILABLE",
        "consumerSummary": "UNAVAILABLE",
        "asOf": "2026-06-08T09:35:00Z",
        "rowCount": 1,
        "availableRowCount": 0,
        "limitedRowCount": 0,
        "blockedRowCount": 0,
        "unavailableRowCount": 1,
    }
    snapshot_serialized = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
    for forbidden_consumer_badge_term in (
        "consumerBadge",
        "trustLabel",
        "providerLabel",
        "sourceType",
        "sourceTier",
        "sourceAuthorityAllowed",
        "scoreContributionAllowed",
        "authorityGrant",
        "decisionGrade",
        "rightToDisplay",
        "options_market_structure",
        "official_public",
    ):
        assert forbidden_consumer_badge_term not in snapshot_serialized


@pytest.mark.parametrize(
    (
        "metadata_overrides",
        "expected_issue_codes",
        "expected_freshness",
        "expected_right_to_display",
        "expected_consumer_state",
        "expected_confidence_posture",
        "expected_counts",
    ),
    [
        (
            {"freshnessState": "fresh"},
            {
                "missing_source_authority",
                "missing_score_contribution",
                "missing_right_to_display",
                "authority_grant_without_prerequisites",
                "decision_grade_without_prerequisites",
            },
            "fresh",
            "unavailable",
            "UNAVAILABLE",
            "UNAVAILABLE",
            {
                "availableRowCount": 0,
                "limitedRowCount": 0,
                "blockedRowCount": 0,
                "unavailableRowCount": 1,
            },
        ),
        (
            {
                "freshnessState": "stale",
                "isStale": True,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "rightToDisplay": "granted",
            },
            {
                "degraded_stale_source",
                "authority_grant_without_prerequisites",
                "decision_grade_without_prerequisites",
            },
            "stale",
            "limited",
            "DELAYED",
            "PARTIAL",
            {
                "availableRowCount": 0,
                "limitedRowCount": 1,
                "blockedRowCount": 0,
                "unavailableRowCount": 0,
            },
        ),
        (
            {
                "freshnessState": "partial",
                "isPartial": True,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "rightToDisplay": "granted",
            },
            {
                "degraded_partial_source",
                "authority_grant_without_prerequisites",
                "decision_grade_without_prerequisites",
            },
            "partial",
            "limited",
            "PARTIAL",
            "PARTIAL",
            {
                "availableRowCount": 0,
                "limitedRowCount": 1,
                "blockedRowCount": 0,
                "unavailableRowCount": 0,
            },
        ),
        (
            {
                "freshnessState": "fallback",
                "isFallback": True,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "rightToDisplay": "granted",
            },
            {
                "degraded_fallback_source",
                "authority_grant_without_prerequisites",
                "decision_grade_without_prerequisites",
            },
            "fallback",
            "limited",
            "PAUSED",
            "INSUFFICIENT",
            {
                "availableRowCount": 0,
                "limitedRowCount": 0,
                "blockedRowCount": 1,
                "unavailableRowCount": 0,
            },
        ),
        (
            {
                "freshnessState": "unknown",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "rightToDisplay": "granted",
            },
            {
                "unknown_freshness",
                "authority_grant_without_prerequisites",
                "decision_grade_without_prerequisites",
            },
            "unknown",
            "limited",
            "UPDATING",
            "PARTIAL",
            {
                "availableRowCount": 0,
                "limitedRowCount": 1,
                "blockedRowCount": 0,
                "unavailableRowCount": 0,
            },
        ),
    ],
)
def test_single_stock_adoption_proof_fails_closed_through_row_batch_snapshot(
    metadata_overrides: dict[str, object],
    expected_issue_codes: set[str],
    expected_freshness: str,
    expected_right_to_display: str,
    expected_consumer_state: str,
    expected_confidence_posture: str,
    expected_counts: dict[str, int],
) -> None:
    metadata = {
        "surfaceId": "forbidden_override",
        "routeId": "/should-not-win",
        "audience": "admin",
        "fieldKey": "wrong_field",
        "evidenceFamily": "wrong_family",
        "providerId": "single_stock_provider_descriptor",
        "providerLabel": "Single Stock Provider Descriptor",
        "sourceId": "single_stock_summary_source_descriptor",
        "sourceLabel": "Single Stock Summary Source Descriptor",
        "sourceType": "official_public",
        "sourceTier": "provider_descriptor_only",
        "asOf": "2026-06-08T09:50:00Z",
        "authorityGrant": True,
        "decisionGrade": True,
        "providerRuntimeCalled": True,
        "networkCallsEnabled": True,
        "marketCacheMutation": True,
        "cacheStatus": "hit",
        "cache_key": "single_stock_summary_cache_key",
        "coverageRatio": 1.0,
        "reasonCode": "backend_single_stock_debug_reason",
        "rawDiagnostics": {
            "backend_cache_debug": "do-not-project",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
        },
        **metadata_overrides,
    }

    row_result = build_data_coverage_matrix_row(
        metadata,
        surface_id="single_stock",
        field_key="single_stock_summary_status",
    )
    row = row_result.to_dict()
    issues = {issue.code for issue in row_result.validation.issues}

    assert row_result.validation.is_valid is False
    assert expected_issue_codes <= issues
    assert row_result.registry_entry.surface_id == "single_stock"
    assert row_result.registry_entry.route_id == "/zh"
    assert row_result.registry_entry.audience.value == "consumer"
    assert row_result.registry_entry.field_key == "single_stock_summary_status"
    assert row_result.registry_entry.evidence_family == "single_stock_evidence"
    assert row_result.raw_contract.provider_id == "single_stock_provider_descriptor"
    assert row_result.raw_contract.source_id == "single_stock_summary_source_descriptor"
    assert row_result.raw_contract.provider_runtime_called is True
    assert row_result.raw_contract.network_calls_enabled is True
    assert row_result.raw_contract.market_cache_mutation is True

    assert row["surfaceId"] == "single_stock"
    assert row["routeId"] == "/zh"
    assert row["audience"] == "consumer"
    assert row["fieldKey"] == "single_stock_summary_status"
    assert row["evidenceFamily"] == "single_stock_evidence"
    assert row["freshnessState"] == expected_freshness
    assert row["rightToDisplay"] == expected_right_to_display
    assert row["rightToDisplay"] != "granted"
    assert row["scoreContributionAllowed"] is False
    assert row["authorityGrant"] is False
    assert row["decisionGrade"] is False
    assert row["observationOnly"] is True
    assert row["diagnosticOnly"] is True
    assert row["providerRuntimeCalled"] is False
    assert row["networkCallsEnabled"] is False
    assert row["marketCacheMutation"] is False
    if "sourceAuthorityAllowed" not in metadata_overrides:
        assert row["sourceAuthorityAllowed"] is False

    batch_result = build_data_coverage_matrix_batch(
        [
            {
                **metadata,
                "surfaceId": "single_stock",
                "fieldKey": "single_stock_summary_status",
            }
        ]
    )
    batch = batch_result.to_dict()

    assert batch["rowCounts"] == {
        "input": 1,
        "built": 1,
        "valid": 0,
        "invalid": 1,
        "errors": 1,
    }
    assert batch["rows"] == [row]
    assert batch["guardPosture"] == {
        "diagnosticOnly": True,
        "providerRuntimeCalled": False,
        "networkCallsEnabled": False,
        "marketCacheMutation": False,
    }
    assert set(batch["errors"][0]["codes"]) >= issues

    snapshot = build_data_coverage_surface_snapshot(batch["rows"]).to_dict()
    projection = project_consumer_data_coverage(row).to_dict()
    projection_serialized = json.dumps(projection, ensure_ascii=False, sort_keys=True)
    snapshot_consumer_serialized = json.dumps(
        {
            "consumerState": snapshot["consumerState"],
            "confidencePosture": snapshot["confidencePosture"],
            "consumerSummary": snapshot["consumerSummary"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    row_serialized = json.dumps(row, ensure_ascii=False, sort_keys=True)

    assert snapshot["snapshotVersion"] == "data_coverage_surface_snapshot_v1"
    assert snapshot["surfaceId"] == "single_stock"
    assert snapshot["routeId"] == "/zh"
    assert snapshot["audience"] == "consumer"
    assert snapshot["consumerState"] == expected_consumer_state
    assert snapshot["confidencePosture"] == expected_confidence_posture
    assert snapshot["consumerSummary"] == expected_consumer_state
    assert snapshot["asOf"] == "2026-06-08T09:50:00Z"
    assert snapshot["rowCount"] == 1
    for key, expected_count in expected_counts.items():
        assert snapshot[key] == expected_count

    assert projection["status"] == expected_consumer_state
    assert projection["asOf"] == "2026-06-08T09:50:00Z"
    assert "_" not in projection_serialized
    assert "_" not in snapshot_consumer_serialized
    for forbidden_term in _SINGLE_STOCK_FORBIDDEN_CONSUMER_TERMS:
        assert forbidden_term not in projection_serialized
        assert forbidden_term not in snapshot_consumer_serialized

    for ignored_raw_term in (
        "cacheStatus",
        "cache_key",
        "coverageRatio",
        "reasonCode",
        "rawDiagnostics",
        "backend_cache_debug",
    ):
        assert ignored_raw_term not in row_serialized


def test_liquidity_builder_lookup_preserves_registry_fields_and_fails_closed_without_explicit_reviews() -> None:
    metadata = {
        "surfaceId": "forbidden_override",
        "routeId": "/should-not-win",
        "audience": "admin",
        "fieldKey": "wrong_field",
        "evidenceFamily": "wrong_family",
        "providerId": "liquidity_provider_descriptor",
        "providerLabel": "Liquidity Provider Descriptor",
        "sourceId": "liquidity_score_source_descriptor",
        "sourceLabel": "Liquidity Score Source Descriptor",
        "sourceType": "licensed_feed",
        "sourceTier": "authorized_partner",
        "freshnessState": "fresh",
        "asOf": "2026-06-08T09:30:00Z",
        "lastUpdated": "2026-06-08T09:31:00Z",
    }
    result = build_data_coverage_matrix_row(
        metadata,
        surface_id="liquidity",
        field_key="liquidity_score_status",
    )

    row = result.to_dict()
    issues = {issue.code for issue in result.validation.issues}

    assert issues >= {
        "missing_source_authority",
        "missing_score_contribution",
        "missing_right_to_display",
    }
    assert result.registry_entry.surface_id == "liquidity"
    assert result.registry_entry.route_id == "/zh/market/liquidity-monitor"
    assert result.registry_entry.audience.value == "consumer"
    assert result.registry_entry.field_key == "liquidity_score_status"
    assert result.registry_entry.evidence_family == "liquidity_monitor"
    assert result.normalized_contract.surface_id == "liquidity"
    assert result.normalized_contract.route_id == "/zh/market/liquidity-monitor"
    assert result.normalized_contract.audience == "consumer"
    assert result.normalized_contract.field_key == "liquidity_score_status"
    assert result.normalized_contract.evidence_family == "liquidity_monitor"
    assert result.normalized_contract.provider_id == "liquidity_provider_descriptor"
    assert result.normalized_contract.source_id == "liquidity_score_source_descriptor"
    assert result.normalized_contract.source_authority_allowed is False
    assert result.normalized_contract.right_to_display is RightToDisplay.UNAVAILABLE
    assert result.normalized_contract.score_contribution_allowed is False
    assert result.normalized_contract.authority_grant is False
    assert result.normalized_contract.decision_grade is False
    assert result.normalized_contract.observation_only is True
    assert row["surfaceId"] == "liquidity"
    assert row["routeId"] == "/zh/market/liquidity-monitor"
    assert row["audience"] == "consumer"
    assert row["fieldKey"] == "liquidity_score_status"
    assert row["evidenceFamily"] == "liquidity_monitor"
    assert row["sourceAuthorityAllowed"] is False
    assert row["scoreContributionAllowed"] is False
    assert row["authorityGrant"] is False
    assert row["decisionGrade"] is False
    assert row["observationOnly"] is True
    assert row["rightToDisplay"] == "unavailable"
    assert row["diagnosticOnly"] is True
    assert row["providerRuntimeCalled"] is False
    assert row["networkCallsEnabled"] is False
    assert row["marketCacheMutation"] is False

    batch = build_data_coverage_matrix_batch(
        [
            {
                **metadata,
                "surfaceId": "liquidity",
                "fieldKey": "liquidity_score_status",
            }
        ]
    ).to_dict()

    assert batch["rowCounts"] == {
        "input": 1,
        "built": 1,
        "valid": 0,
        "invalid": 1,
        "errors": 1,
    }
    assert batch["rows"] == [row]
    assert batch["guardPosture"] == {
        "diagnosticOnly": True,
        "providerRuntimeCalled": False,
        "networkCallsEnabled": False,
        "marketCacheMutation": False,
    }
    assert set(batch["errors"][0]["codes"]) >= issues


def test_rotation_adoption_proof_preserves_registry_fields_and_fails_closed_without_explicit_reviews() -> None:
    metadata = {
        "surfaceId": "forbidden_override",
        "routeId": "/should-not-win",
        "audience": "admin",
        "fieldKey": "wrong_field",
        "evidenceFamily": "wrong_family",
        "providerId": "rotation_provider_descriptor",
        "providerLabel": "Rotation Provider Descriptor",
        "sourceId": "rotation_score_source_descriptor",
        "sourceLabel": "Rotation Score Source Descriptor",
        "sourceType": "authorized_derived_snapshot",
        "sourceTier": "reviewed_internal",
        "freshnessState": "fresh",
        "asOf": "2026-06-08T09:30:00Z",
        "lastUpdated": "2026-06-08T09:31:00Z",
        "observationOnly": False,
        "diagnosticOnly": False,
        "providerRuntimeCalled": True,
        "networkCallsEnabled": True,
        "marketCacheMutation": True,
    }
    result = build_data_coverage_matrix_row(
        metadata,
        surface_id="rotation",
        field_key="rotation_score_status",
    )

    row = result.to_dict()
    issues = {issue.code for issue in result.validation.issues}

    assert issues >= {
        "missing_source_authority",
        "missing_score_contribution",
        "missing_right_to_display",
    }
    assert result.registry_entry.surface_id == "rotation"
    assert result.registry_entry.route_id == "/zh/market/rotation-radar"
    assert result.registry_entry.audience.value == "consumer"
    assert result.registry_entry.field_key == "rotation_score_status"
    assert result.registry_entry.evidence_family == "rotation_signal"
    assert result.normalized_contract.surface_id == "rotation"
    assert result.normalized_contract.route_id == "/zh/market/rotation-radar"
    assert result.normalized_contract.audience == "consumer"
    assert result.normalized_contract.field_key == "rotation_score_status"
    assert result.normalized_contract.evidence_family == "rotation_signal"
    assert result.normalized_contract.provider_id == "rotation_provider_descriptor"
    assert result.normalized_contract.source_id == "rotation_score_source_descriptor"
    assert result.normalized_contract.source_authority_allowed is False
    assert result.normalized_contract.right_to_display is RightToDisplay.UNAVAILABLE
    assert result.normalized_contract.score_contribution_allowed is False
    assert result.normalized_contract.authority_grant is False
    assert result.normalized_contract.decision_grade is False
    assert result.normalized_contract.observation_only is True
    assert row["surfaceId"] == "rotation"
    assert row["routeId"] == "/zh/market/rotation-radar"
    assert row["audience"] == "consumer"
    assert row["fieldKey"] == "rotation_score_status"
    assert row["evidenceFamily"] == "rotation_signal"
    assert row["sourceAuthorityAllowed"] is False
    assert row["scoreContributionAllowed"] is False
    assert row["authorityGrant"] is False
    assert row["decisionGrade"] is False
    assert row["observationOnly"] is True
    assert row["rightToDisplay"] == "unavailable"
    assert row["diagnosticOnly"] is True
    assert row["providerRuntimeCalled"] is False
    assert row["networkCallsEnabled"] is False
    assert row["marketCacheMutation"] is False

    batch = build_data_coverage_matrix_batch(
        [
            {
                **metadata,
                "surfaceId": "rotation",
                "fieldKey": "rotation_score_status",
            }
        ]
    ).to_dict()

    assert batch["rowCounts"] == {
        "input": 1,
        "built": 1,
        "valid": 0,
        "invalid": 1,
        "errors": 1,
    }
    assert batch["rows"] == [row]
    assert batch["guardPosture"] == {
        "diagnosticOnly": True,
        "providerRuntimeCalled": False,
        "networkCallsEnabled": False,
        "marketCacheMutation": False,
    }
    assert set(batch["errors"][0]["codes"]) >= issues

    snapshot = build_data_coverage_surface_snapshot(batch["rows"]).to_dict()

    assert snapshot == {
        "snapshotVersion": "data_coverage_surface_snapshot_v1",
        "surfaceId": "rotation",
        "routeId": "/zh/market/rotation-radar",
        "audience": "consumer",
        "consumerState": "UNAVAILABLE",
        "confidencePosture": "UNAVAILABLE",
        "consumerSummary": "UNAVAILABLE",
        "asOf": "2026-06-08T09:30:00Z",
        "rowCount": 1,
        "availableRowCount": 0,
        "limitedRowCount": 0,
        "blockedRowCount": 0,
        "unavailableRowCount": 1,
    }


def test_watchlist_adoption_proof_maps_score_status_context_without_source_authority() -> None:
    score_status_context = {
        "scope": "score_refresh_recency",
        "fresh_means": "persisted_scanner_score_refreshed",
        "source_freshness_implied": False,
        "source_authority_implied": False,
    }
    metadata = {
        "surfaceId": "forbidden_override",
        "routeId": "/should-not-win",
        "audience": "admin",
        "fieldKey": "wrong_field",
        "evidenceFamily": "wrong_family",
        "providerId": "watchlist_persisted_scanner_score",
        "providerLabel": "Watchlist Persisted Scanner Score",
        "sourceId": "watchlist_score_recency_context",
        "sourceLabel": "Watchlist Score Recency Context",
        "sourceType": "persisted_scanner_score_snapshot",
        "sourceTier": "score_recency_only",
        "asOf": "2026-06-08T09:45:00Z",
        "scoreStatus": "fresh",
        "scoreStatusContext": {
            "scope": score_status_context["scope"],
            "freshMeans": score_status_context["fresh_means"],
            "sourceFreshnessImplied": score_status_context["source_freshness_implied"],
            "sourceAuthorityImplied": score_status_context["source_authority_implied"],
        },
        "score_status_context": score_status_context,
        "scanner_run_id": 88,
        "reasonCode": "persisted_scanner_score_refresh",
        "rawDiagnostics": {
            "backend_cache_debug": "do-not-project",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
        },
    }

    result = build_data_coverage_matrix_row(
        metadata,
        surface_id="watchlist",
        field_key="watchlist_readiness_status",
    )
    row = result.to_dict()
    issues = {issue.code for issue in result.validation.issues}

    assert score_status_context["source_freshness_implied"] is False
    assert score_status_context["source_authority_implied"] is False
    assert result.validation.is_valid is False
    assert issues >= {
        "missing_source_authority",
        "missing_score_contribution",
        "missing_right_to_display",
        "unknown_freshness",
    }
    assert result.registry_entry.surface_id == "watchlist"
    assert result.registry_entry.route_id == "/zh/watchlist"
    assert result.registry_entry.audience.value == "consumer"
    assert result.registry_entry.field_key == "watchlist_readiness_status"
    assert result.registry_entry.evidence_family == "watchlist_candidate"
    assert result.normalized_contract.surface_id == "watchlist"
    assert result.normalized_contract.route_id == "/zh/watchlist"
    assert result.normalized_contract.audience == "consumer"
    assert result.normalized_contract.field_key == "watchlist_readiness_status"
    assert result.normalized_contract.evidence_family == "watchlist_candidate"
    assert result.raw_contract.freshness_state.value == "unknown"
    assert result.normalized_contract.freshness_state.value == "unknown"
    assert result.normalized_contract.source_authority_allowed is False
    assert result.normalized_contract.score_contribution_allowed is False
    assert result.normalized_contract.authority_grant is False
    assert result.normalized_contract.decision_grade is False
    assert result.normalized_contract.observation_only is True
    assert result.normalized_contract.right_to_display in {RightToDisplay.UNAVAILABLE, RightToDisplay.LIMITED}
    assert result.normalized_contract.right_to_display is RightToDisplay.UNAVAILABLE
    assert row["surfaceId"] == "watchlist"
    assert row["routeId"] == "/zh/watchlist"
    assert row["audience"] == "consumer"
    assert row["fieldKey"] == "watchlist_readiness_status"
    assert row["evidenceFamily"] == "watchlist_candidate"
    assert row["freshnessState"] == "unknown"
    assert row["sourceAuthorityAllowed"] is False
    assert row["scoreContributionAllowed"] is False
    assert row["authorityGrant"] is False
    assert row["decisionGrade"] is False
    assert row["observationOnly"] is True
    assert row["rightToDisplay"] == "unavailable"
    assert row["diagnosticOnly"] is True
    assert row["providerRuntimeCalled"] is False
    assert row["networkCallsEnabled"] is False
    assert row["marketCacheMutation"] is False

    batch = build_data_coverage_matrix_batch(
        [
            {
                **metadata,
                "surfaceId": "watchlist",
                "fieldKey": "watchlist_readiness_status",
            }
        ]
    ).to_dict()

    assert batch["rowCounts"] == {
        "input": 1,
        "built": 1,
        "valid": 0,
        "invalid": 1,
        "errors": 1,
    }
    assert batch["rows"] == [row]
    assert batch["guardPosture"] == {
        "diagnosticOnly": True,
        "providerRuntimeCalled": False,
        "networkCallsEnabled": False,
        "marketCacheMutation": False,
    }
    assert set(batch["errors"][0]["codes"]) >= issues

    snapshot = build_data_coverage_surface_snapshot(batch["rows"]).to_dict()

    assert snapshot == {
        "snapshotVersion": "data_coverage_surface_snapshot_v1",
        "surfaceId": "watchlist",
        "routeId": "/zh/watchlist",
        "audience": "consumer",
        "consumerState": "UPDATING",
        "confidencePosture": "PARTIAL",
        "consumerSummary": "UPDATING",
        "asOf": "2026-06-08T09:45:00Z",
        "rowCount": 1,
        "availableRowCount": 0,
        "limitedRowCount": 1,
        "blockedRowCount": 0,
        "unavailableRowCount": 0,
    }
    snapshot_serialized = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
    row_serialized = json.dumps(row, ensure_ascii=False, sort_keys=True)

    for forbidden_row_leak in (
        "scoreStatusContext",
        "score_status_context",
        "scanner_run_id",
        "reasonCode",
        "rawDiagnostics",
        "backend_cache_debug",
    ):
        assert forbidden_row_leak not in row_serialized

    for forbidden_projection_leak in (
        "providerId",
        "providerLabel",
        "sourceId",
        "sourceLabel",
        "sourceType",
        "sourceTier",
        "sourceAuthorityAllowed",
        "scoreContributionAllowed",
        "authorityGrant",
        "decisionGrade",
        "rightToDisplay",
        "reasonCode",
        "reason_code",
        "reasonFamilies",
        "reason_families",
        "scoreStatusContext",
        "score_status_context",
        "sourceFreshnessImplied",
        "source_freshness_implied",
        "sourceAuthorityImplied",
        "source_authority_implied",
        "scanner_run_id",
        "rawDiagnostics",
        "raw diagnostics",
        "backend",
        "cache",
        "debug",
        "watchlist_readiness_status",
        "watchlist_candidate",
        "persisted_scanner_score_snapshot",
        "score_recency_only",
    ):
        assert forbidden_projection_leak not in snapshot_serialized


@pytest.mark.parametrize(
    ("metadata", "issue_code", "expected_right_to_display"),
    [
        ({"freshnessState": "fallback", "isFallback": True}, "degraded_fallback_source", "limited"),
        ({"freshnessState": "stale", "isStale": True}, "degraded_stale_source", "limited"),
        ({"freshnessState": "partial", "isPartial": True}, "degraded_partial_source", "limited"),
        ({"freshnessState": "synthetic", "isSynthetic": True}, "degraded_synthetic_source", "unavailable"),
        ({"freshnessState": "unavailable", "isUnavailable": True}, "degraded_unavailable_source", "unavailable"),
        ({"freshnessState": "unknown"}, "unknown_freshness", "limited"),
    ],
)
def test_liquidity_degraded_or_unknown_states_cannot_grant_score_decision_authority_or_display(
    metadata: dict[str, object],
    issue_code: str,
    expected_right_to_display: str,
) -> None:
    result = build_data_coverage_matrix_row(
        {
            "providerId": "liquidity_provider_descriptor",
            "providerLabel": "Liquidity Provider Descriptor",
            "sourceId": "liquidity_score_source_descriptor",
            "sourceLabel": "Liquidity Score Source Descriptor",
            "sourceType": "licensed_feed",
            "sourceTier": "authorized_partner",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "authorityGrant": True,
            "decisionGrade": True,
            "rightToDisplay": "granted",
            **metadata,
        },
        surface_id="liquidity",
        field_key="liquidity_score_status",
    )

    row = result.to_dict()
    issues = {issue.code for issue in result.validation.issues}

    assert result.validation.is_valid is False
    assert issue_code in issues
    assert "authority_grant_without_prerequisites" in issues
    assert "decision_grade_without_prerequisites" in issues
    assert row["surfaceId"] == "liquidity"
    assert row["routeId"] == "/zh/market/liquidity-monitor"
    assert row["audience"] == "consumer"
    assert row["fieldKey"] == "liquidity_score_status"
    assert row["evidenceFamily"] == "liquidity_monitor"
    assert row["rightToDisplay"] == expected_right_to_display
    assert row["rightToDisplay"] != "granted"
    assert row["scoreContributionAllowed"] is False
    assert row["authorityGrant"] is False
    assert row["decisionGrade"] is False
    assert row["observationOnly"] is True
    assert row["diagnosticOnly"] is True
    assert row["providerRuntimeCalled"] is False
    assert row["networkCallsEnabled"] is False
    assert row["marketCacheMutation"] is False


def test_scanner_builder_lookup_fails_closed_when_score_posture_is_missing() -> None:
    result = build_data_coverage_matrix_row(
        {
            "providerId": "scanner_registry",
            "providerLabel": "Scanner Registry",
            "sourceId": "scanner_candidate_snapshot",
            "sourceLabel": "Scanner Candidate Snapshot",
            "sourceType": "authorized_derived_snapshot",
            "sourceTier": "reviewed_internal",
            "freshnessState": "fresh",
            "sourceAuthorityAllowed": True,
            "authorityGrant": True,
            "decisionGrade": True,
            "rightToDisplay": "granted",
        },
        surface_id="scanner",
        field_key="candidate_score_status",
    )

    issues = {issue.code for issue in result.validation.issues}

    assert "missing_score_contribution" in issues
    assert result.normalized_contract.right_to_display is RightToDisplay.GRANTED
    assert result.normalized_contract.score_contribution_allowed is False
    assert result.normalized_contract.authority_grant is False
    assert result.normalized_contract.decision_grade is False
    assert result.normalized_contract.observation_only is True


def test_backtest_builder_registry_entry_fails_closed_for_fallback_source() -> None:
    entry = resolve_data_coverage_surface_registry_entry(surface_id="backtest", field_key="backtest_result_status")
    result = build_data_coverage_matrix_row(
        {
            "providerId": "backtest_snapshot",
            "providerLabel": "Backtest Snapshot",
            "sourceId": "backtest_research_snapshot",
            "sourceLabel": "Backtest Research Snapshot",
            "sourceType": "reviewed_internal_snapshot",
            "sourceTier": "reviewed_internal",
            "freshnessState": "fallback",
            "isFallback": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "authorityGrant": True,
            "decisionGrade": True,
            "rightToDisplay": "granted",
        },
        registry_entry=entry,
    )

    issues = {issue.code for issue in result.validation.issues}

    assert "degraded_fallback_source" in issues
    assert result.normalized_contract.right_to_display is RightToDisplay.LIMITED
    assert result.normalized_contract.score_contribution_allowed is False
    assert result.normalized_contract.authority_grant is False
    assert result.normalized_contract.decision_grade is False
    assert result.normalized_contract.observation_only is True


def test_unknown_surface_lookup_raises() -> None:
    with pytest.raises(LookupError, match="Unknown data coverage surface registry entry"):
        build_data_coverage_matrix_row(surface_id="unknown_surface", field_key="unknown_field")


def test_builder_module_is_pure_and_only_loads_contract_and_registry_helpers() -> None:
    module_path = Path("src/services/data_coverage_matrix_builder.py")
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_modules.add(node.module or "")

    assert imported_modules <= {
        "__future__",
        "dataclasses",
        "typing",
        "src.services.data_coverage_matrix_contract",
        "src.services.data_coverage_surface_registry",
    }

    script = """
import json
import sys
before = set(sys.modules)
import src.services.data_coverage_matrix_builder  # noqa: F401
after = set(sys.modules) - before
blocked = sorted(
    name for name in after
    if (
        name.startswith("data_provider")
        or name.startswith("api")
        or name.startswith("apps")
        or name.startswith("requests")
        or name.startswith("sqlalchemy")
        or name.startswith("duckdb")
        or name.startswith("aiohttp")
        or name.startswith("src.storage")
        or (
            name.startswith("src.services.")
            and name
            not in {
                "src.services",
                "src.services.data_coverage_matrix_builder",
                "src.services.data_coverage_matrix_contract",
                "src.services.data_coverage_surface_registry",
            }
        )
    )
)
print(json.dumps(blocked))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == []


def test_market_overview_adoption_helpers_do_not_load_runtime_or_product_semantic_modules() -> None:
    script = """
import json
import sys
before = set(sys.modules)
import src.services.data_coverage_surface_registry  # noqa: F401
import src.services.data_coverage_matrix_builder  # noqa: F401
import src.services.data_coverage_matrix_batch  # noqa: F401
import src.services.data_coverage_surface_snapshot  # noqa: F401
after = set(sys.modules) - before
blocked = sorted(
    name for name in after
    if (
        name.startswith("data_provider")
        or name.startswith("api")
        or name.startswith("apps")
        or name.startswith("src.schemas")
        or name.startswith("src.repositories")
        or name.startswith("src.services.market_overview_service")
        or name.startswith("src.services.liquidity_monitor_service")
        or name.startswith("src.services.options_")
        or name.startswith("src.services.market_scanner_service")
        or name.startswith("src.services.rule_backtest_service")
        or name.startswith("src.services.market_cache")
        or name.startswith("src.services.market_regime_synthesis_service")
        or name.startswith("src.services.market_decision_semantics")
    )
)
print(json.dumps(blocked))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == []
