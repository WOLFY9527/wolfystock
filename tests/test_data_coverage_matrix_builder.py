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
from src.services.data_coverage_matrix_contract import RightToDisplay
from src.services.data_coverage_surface_registry import DATA_COVERAGE_SURFACE_REGISTRY_BY_SURFACE_FIELD
from src.services.data_coverage_surface_snapshot import build_data_coverage_surface_snapshot


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


def test_liquidity_builder_lookup_preserves_registry_fields_and_fails_closed_without_display_review() -> None:
    result = build_data_coverage_matrix_row(
        {
            "surfaceId": "forbidden_override",
            "routeId": "/should-not-win",
            "fieldKey": "wrong_field",
            "evidenceFamily": "wrong_family",
            "providerId": "akshare_liquidity",
            "providerLabel": "AKShare",
            "sourceId": "cn_liquidity_feed",
            "sourceLabel": "CN Liquidity Feed",
            "sourceType": "licensed_feed",
            "sourceTier": "authorized_partner",
            "freshnessState": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "authorityGrant": True,
            "decisionGrade": True,
        },
        surface_id="liquidity",
        field_key="liquidity_score_status",
    )

    issues = {issue.code for issue in result.validation.issues}

    assert issues >= {"missing_right_to_display", "authority_grant_without_prerequisites", "decision_grade_without_prerequisites"}
    assert result.normalized_contract.surface_id == "liquidity"
    assert result.normalized_contract.route_id == "/zh/market/liquidity-monitor"
    assert result.normalized_contract.right_to_display is RightToDisplay.UNAVAILABLE
    assert result.normalized_contract.score_contribution_allowed is False
    assert result.normalized_contract.authority_grant is False
    assert result.normalized_contract.decision_grade is False
    assert result.normalized_contract.observation_only is True


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
