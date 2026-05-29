# -*- coding: utf-8 -*-
"""Focused tests for the internal backend metrics snapshot service."""

from __future__ import annotations

import ast
import copy
import importlib
import json
from pathlib import Path

from src.services.backend_metrics_snapshot_service import (
    BACKEND_METRICS_GROUP_COUNT_NAMES,
    BACKEND_METRICS_PROVENANCE,
    BackendMetricsSnapshotService,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "admin_observability"
    / "backend_metrics_snapshot_contract.json"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "api.v1.endpoints",
    "data_provider",
    "httpx",
    "requests",
    "src.services.analysis_provider_planner",
    "src.services.execution_log_service",
    "src.services.market_cache",
    "src.services.market_provider_operations_service",
    "src.services.provider_usage_ledger",
)


def _load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_build_snapshot_matches_t692_group_contract_shape() -> None:
    fixture = _load_fixture()
    service = BackendMetricsSnapshotService()

    payload = service.build_snapshot(fixture["groups"])

    assert payload["snapshot_meta"] == {
        "surface": "backend_metrics_snapshot",
        "read_only": True,
        **BACKEND_METRICS_PROVENANCE,
    }
    assert payload["normalization"] == fixture["normalization"]
    assert payload["sanitization_rules"] == fixture["sanitization_rules"]
    assert payload["deferred_production_metrics_stack"] == fixture["deferred_production_metrics_stack"]
    assert payload["groups"] == fixture["groups"]


def test_build_snapshot_defaults_missing_groups_to_zero_and_unavailable() -> None:
    service = BackendMetricsSnapshotService()

    payload = service.build_snapshot(
        {
            "provider_diagnostics": {
                "sources": ["provider_fixture"],
                "counts": {"configured_provider_count": 2},
            }
        }
    )

    for group_name, expected_counts in BACKEND_METRICS_GROUP_COUNT_NAMES.items():
        group = payload["groups"][group_name]
        assert group["provenance"] == BACKEND_METRICS_PROVENANCE
        assert set(group["counts"]) == expected_counts

        if group_name == "provider_diagnostics":
            assert group["sources"] == ["provider_fixture"]
            assert group["counts"]["configured_provider_count"] == 2
        else:
            assert group["sources"] == ["unavailable"]
            assert all(value == 0 for value in group["counts"].values())


def test_build_snapshot_normalizes_invalid_counts_without_mutating_inputs() -> None:
    service = BackendMetricsSnapshotService()
    input_payload = {
        "groups": {
            "market_cache_diagnostics": {
                "sources": ["market_cache_fixture"],
                "counts": {
                    "hit_count": -3,
                    "miss_count": "4",
                    "stale_served_count": 2.5,
                    "cold_fallback_count": True,
                    "refresh_started_count": 1,
                    "refresh_completed_count": None,
                    "refresh_failed_count": 0,
                },
            }
        }
    }
    original = copy.deepcopy(input_payload)

    payload = service.build_snapshot(input_payload)

    assert input_payload == original
    assert payload["groups"]["market_cache_diagnostics"]["counts"] == {
        "hit_count": 0,
        "miss_count": 4,
        "stale_served_count": 0,
        "cold_fallback_count": 0,
        "refresh_started_count": 1,
        "refresh_completed_count": 0,
        "refresh_failed_count": 0,
    }


def test_build_snapshot_keeps_production_metrics_stack_deferred_only() -> None:
    service = BackendMetricsSnapshotService()

    payload = service.build_snapshot({})

    for status in payload["deferred_production_metrics_stack"].values():
        assert status == {"status": "deferred", "implemented": False}


def test_service_module_stays_local_only_and_has_no_live_provider_imports() -> None:
    module = importlib.import_module("src.services.backend_metrics_snapshot_service")
    source_path = Path(module.__file__ or "")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))

    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    for imported in imported_modules:
        assert not any(
            imported == prefix or imported.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_IMPORT_PREFIXES
        ), imported
