# -*- coding: utf-8 -*-
"""Offline tests for the inert Data Coverage Matrix batch builder."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.services.data_coverage_matrix_batch import (
    DATA_COVERAGE_MATRIX_BATCH_GUARD_POSTURE,
    DataCoverageMatrixBatchBuildError,
    build_data_coverage_matrix_batch,
)
from src.services.data_coverage_surface_snapshot import build_data_coverage_surface_snapshot


def _valid_metadata(surface_id: str, field_key: str, *, provider_id: str) -> dict[str, object]:
    return {
        "surfaceId": surface_id,
        "fieldKey": field_key,
        "providerId": provider_id,
        "providerLabel": "Reviewed Provider",
        "sourceId": f"{provider_id}_source",
        "sourceLabel": "Reviewed Source",
        "sourceType": "authorized_licensed_feed",
        "sourceTier": "reviewed_authorized",
        "freshnessState": "fresh",
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
        "authorityGrant": True,
        "decisionGrade": True,
        "rightToDisplay": "granted",
    }


def _fallback_metadata() -> dict[str, object]:
    payload = _valid_metadata(
        "backtest",
        "backtest_result_status",
        provider_id="backtest_snapshot",
    )
    payload.update(
        {
            "freshnessState": "fallback",
            "isFallback": True,
        }
    )
    return payload


def _rotation_reviewed_metadata(provider_id: str) -> dict[str, object]:
    payload = _valid_metadata("rotation", "rotation_score_status", provider_id=provider_id)
    payload.update(
        {
            "providerLabel": "Reviewed Rotation Provider",
            "sourceId": f"{provider_id}_rotation_source",
            "sourceLabel": "Reviewed Rotation Source",
            "sourceType": "authorized_derived_snapshot",
            "sourceTier": "reviewed_internal",
            "asOf": "2026-06-08T09:30:00Z",
        }
    )
    return payload


def _rotation_missing_review_metadata() -> dict[str, object]:
    return {
        "surfaceId": "rotation",
        "fieldKey": "rotation_score_status",
        "providerId": "rotation_review_pending",
        "providerLabel": "Rotation Review Pending Provider",
        "sourceId": "rotation_review_pending_source",
        "sourceLabel": "Rotation Review Pending Source",
        "sourceType": "authorized_derived_snapshot",
        "sourceTier": "review_pending",
        "freshnessState": "partial",
        "isPartial": True,
        "asOf": "2026-06-08T09:35:00Z",
        "authorityGrant": True,
        "decisionGrade": True,
        "observationOnly": False,
        "diagnosticOnly": False,
        "providerRuntimeCalled": True,
        "networkCallsEnabled": True,
        "marketCacheMutation": True,
    }


def test_successful_batch_returns_valid_rows_counts_and_inert_guard_posture() -> None:
    result = build_data_coverage_matrix_batch(
        [
            _valid_metadata("market_overview", "market_regime", provider_id="polygon_primary"),
            _valid_metadata("scanner", "candidate_score_status", provider_id="scanner_registry"),
        ]
    )
    payload = result.to_dict()

    assert payload["rowCounts"] == {
        "input": 2,
        "built": 2,
        "valid": 2,
        "invalid": 0,
        "errors": 0,
    }
    assert payload["guardPosture"] == DATA_COVERAGE_MATRIX_BATCH_GUARD_POSTURE
    assert payload["errors"] == []
    assert [row["surfaceId"] for row in payload["rows"]] == ["market_overview", "scanner"]
    assert [row["fieldKey"] for row in payload["rows"]] == ["market_regime", "candidate_score_status"]
    assert all(row["diagnosticOnly"] is True for row in payload["rows"])
    assert all(row["providerRuntimeCalled"] is False for row in payload["rows"])
    assert all(row["networkCallsEnabled"] is False for row in payload["rows"])
    assert all(row["marketCacheMutation"] is False for row in payload["rows"])


def test_rotation_batch_preserves_caller_order_and_fails_closed_for_missing_reviews() -> None:
    rows = [
        _rotation_reviewed_metadata("rotation_reviewed"),
        _rotation_missing_review_metadata(),
    ]

    payload = build_data_coverage_matrix_batch(rows).to_dict()

    assert payload["rowCounts"] == {
        "input": 2,
        "built": 2,
        "valid": 1,
        "invalid": 1,
        "errors": 1,
    }
    assert [row["surfaceId"] for row in payload["rows"]] == ["rotation", "rotation"]
    assert [row["fieldKey"] for row in payload["rows"]] == [
        "rotation_score_status",
        "rotation_score_status",
    ]
    assert [row["providerId"] for row in payload["rows"]] == [
        "rotation_reviewed",
        "rotation_review_pending",
    ]
    assert payload["errors"][0]["rowIndex"] == 1
    assert payload["errors"][0]["surfaceId"] == "rotation"
    assert payload["errors"][0]["fieldKey"] == "rotation_score_status"
    assert payload["errors"][0]["errorType"] == "validation_error"
    assert set(payload["errors"][0]["codes"]) >= {
        "missing_source_authority",
        "missing_score_contribution",
        "missing_right_to_display",
        "degraded_partial_source",
        "provider_runtime_side_effect",
        "network_calls_enabled",
        "market_cache_mutation",
        "diagnostic_only_required",
    }

    reviewed_row, fail_closed_row = payload["rows"]
    assert reviewed_row["sourceAuthorityAllowed"] is True
    assert reviewed_row["scoreContributionAllowed"] is True
    assert reviewed_row["authorityGrant"] is True
    assert reviewed_row["decisionGrade"] is True
    assert reviewed_row["observationOnly"] is False
    assert reviewed_row["diagnosticOnly"] is True
    assert reviewed_row["providerRuntimeCalled"] is False
    assert reviewed_row["networkCallsEnabled"] is False
    assert reviewed_row["marketCacheMutation"] is False

    assert fail_closed_row["freshnessState"] == "partial"
    assert fail_closed_row["isPartial"] is True
    assert fail_closed_row["sourceAuthorityAllowed"] is False
    assert fail_closed_row["scoreContributionAllowed"] is False
    assert fail_closed_row["authorityGrant"] is False
    assert fail_closed_row["decisionGrade"] is False
    assert fail_closed_row["observationOnly"] is True
    assert fail_closed_row["rightToDisplay"] == "unavailable"
    assert fail_closed_row["diagnosticOnly"] is True
    assert fail_closed_row["providerRuntimeCalled"] is False
    assert fail_closed_row["networkCallsEnabled"] is False
    assert fail_closed_row["marketCacheMutation"] is False

    consumer_projection = build_data_coverage_surface_snapshot(payload["rows"]).to_dict()
    assert consumer_projection == {
        "snapshotVersion": "data_coverage_surface_snapshot_v1",
        "surfaceId": "rotation",
        "routeId": "/zh/market/rotation-radar",
        "audience": "consumer",
        "consumerState": "PARTIAL",
        "confidencePosture": "PARTIAL",
        "consumerSummary": "PARTIAL",
        "asOf": "2026-06-08T09:35:00Z",
        "rowCount": 2,
        "availableRowCount": 1,
        "limitedRowCount": 1,
        "blockedRowCount": 0,
        "unavailableRowCount": 0,
    }
    serialized_projection = json.dumps(consumer_projection, ensure_ascii=False, sort_keys=True)
    for forbidden in (
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
        "freshnessState",
        "isPartial",
        "providerRuntimeCalled",
        "networkCallsEnabled",
        "marketCacheMutation",
        "missing_source_authority",
    ):
        assert forbidden not in serialized_projection

    with pytest.raises(DataCoverageMatrixBatchBuildError) as exc_info:
        build_data_coverage_matrix_batch(rows, raise_on_error=True)

    assert exc_info.value.result.to_dict()["rowCounts"] == payload["rowCounts"]


def test_partial_failure_preserves_input_order_and_reports_per_row_errors_without_throwing() -> None:
    result = build_data_coverage_matrix_batch(
        [
            _valid_metadata("market_overview", "market_regime", provider_id="polygon_primary"),
            _valid_metadata("market_overview", "unknown_field", provider_id="polygon_primary"),
            _fallback_metadata(),
        ]
    )
    payload = result.to_dict()

    assert payload["rowCounts"] == {
        "input": 3,
        "built": 2,
        "valid": 1,
        "invalid": 2,
        "errors": 2,
    }
    assert [row["surfaceId"] for row in payload["rows"]] == ["market_overview", "backtest"]
    assert [error["rowIndex"] for error in payload["errors"]] == [1, 2]
    assert payload["errors"][0]["codes"] == ["unknown_surface_field"]
    assert "degraded_fallback_source" in payload["errors"][1]["codes"]


def test_unknown_field_fails_closed_as_row_error_without_building_runtime_row() -> None:
    result = build_data_coverage_matrix_batch(
        [_valid_metadata("liquidity", "unknown_field", provider_id="liquidity_registry")]
    )
    payload = result.to_dict()

    assert payload["rows"] == []
    assert payload["rowCounts"] == {
        "input": 1,
        "built": 0,
        "valid": 0,
        "invalid": 1,
        "errors": 1,
    }
    assert payload["guardPosture"] == DATA_COVERAGE_MATRIX_BATCH_GUARD_POSTURE
    assert payload["errors"] == [
        {
            "rowIndex": 0,
            "surfaceId": "liquidity",
            "fieldKey": "unknown_field",
            "errorType": "lookup_error",
            "codes": ["unknown_surface_field"],
            "messages": [
                "Unknown data coverage surface registry entry for surface_id='liquidity' field_key='unknown_field'."
            ],
        }
    ]


def test_unsafe_degraded_metadata_builds_fail_closed_row_and_reports_validation_error() -> None:
    result = build_data_coverage_matrix_batch([_fallback_metadata()])
    payload = result.to_dict()

    assert payload["rowCounts"] == {
        "input": 1,
        "built": 1,
        "valid": 0,
        "invalid": 1,
        "errors": 1,
    }
    row = payload["rows"][0]
    assert row["surfaceId"] == "backtest"
    assert row["fieldKey"] == "backtest_result_status"
    assert row["freshnessState"] == "fallback"
    assert row["isFallback"] is True
    assert row["rightToDisplay"] == "limited"
    assert row["scoreContributionAllowed"] is False
    assert row["authorityGrant"] is False
    assert row["decisionGrade"] is False
    assert row["observationOnly"] is True
    assert row["diagnosticOnly"] is True
    assert row["providerRuntimeCalled"] is False
    assert row["networkCallsEnabled"] is False
    assert row["marketCacheMutation"] is False
    assert payload["errors"][0]["errorType"] == "validation_error"
    assert "degraded_fallback_source" in payload["errors"][0]["codes"]


def test_missing_review_metadata_builds_fail_closed_row_and_reports_validation_error() -> None:
    result = build_data_coverage_matrix_batch(
        [
            {
                "surfaceId": "watchlist",
                "fieldKey": "watchlist_readiness_status",
                "providerId": "watchlist_snapshot",
                "providerLabel": "Watchlist Snapshot",
                "sourceId": "watchlist_snapshot_source",
                "sourceLabel": "Watchlist Snapshot Source",
                "sourceType": "reviewed_internal_snapshot",
                "sourceTier": "reviewed_internal",
            }
        ]
    )
    payload = result.to_dict()

    assert payload["rowCounts"] == {
        "input": 1,
        "built": 1,
        "valid": 0,
        "invalid": 1,
        "errors": 1,
    }
    row = payload["rows"][0]
    assert row["surfaceId"] == "watchlist"
    assert row["fieldKey"] == "watchlist_readiness_status"
    assert row["freshnessState"] == "unknown"
    assert row["rightToDisplay"] == "unavailable"
    assert row["scoreContributionAllowed"] is False
    assert row["authorityGrant"] is False
    assert row["decisionGrade"] is False
    assert row["observationOnly"] is True
    assert payload["errors"][0]["codes"] == [
        "missing_source_authority",
        "missing_score_contribution",
        "missing_right_to_display",
        "unknown_freshness",
    ]


def test_raise_on_error_raises_after_collecting_batch_errors() -> None:
    with pytest.raises(DataCoverageMatrixBatchBuildError) as exc_info:
        build_data_coverage_matrix_batch(
            [
                _valid_metadata("market_overview", "market_regime", provider_id="polygon_primary"),
                _valid_metadata("market_overview", "unknown_field", provider_id="polygon_primary"),
            ],
            raise_on_error=True,
        )

    payload = exc_info.value.result.to_dict()

    assert payload["rowCounts"] == {
        "input": 2,
        "built": 1,
        "valid": 1,
        "invalid": 1,
        "errors": 1,
    }
    assert payload["errors"][0]["codes"] == ["unknown_surface_field"]


def test_batch_output_is_deterministic_for_same_input() -> None:
    rows = [
        _valid_metadata("market_overview", "market_regime", provider_id="polygon_primary"),
        _fallback_metadata(),
    ]

    first = build_data_coverage_matrix_batch(rows).to_dict()
    second = build_data_coverage_matrix_batch(rows).to_dict()

    assert first == second
    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(
        second,
        ensure_ascii=False,
        sort_keys=True,
    )


def test_batch_module_is_pure_and_only_loads_builder_helpers() -> None:
    module_path = Path("src/services/data_coverage_matrix_batch.py")
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
        "src.services.data_coverage_matrix_builder",
    }

    script = """
import json
import sys
before = set(sys.modules)
import src.services.data_coverage_matrix_batch  # noqa: F401
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
                "src.services.data_coverage_matrix_batch",
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
