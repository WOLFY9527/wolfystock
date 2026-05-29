# -*- coding: utf-8 -*-
"""Focused tests for the internal backend metrics snapshot service."""

from __future__ import annotations

import ast
import copy
import importlib
import json
from pathlib import Path
import pytest

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
    "opentelemetry",
    "prometheus_client",
    "sentry_sdk",
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


def test_from_provider_operations_payload_maps_provider_and_cache_counts_without_mutating_inputs() -> None:
    service = BackendMetricsSnapshotService()
    input_payload = {
        "summary": {
            "fallbackCount": "2",
            "staleCount": 1,
            "budgetSkipCount": -5,
        },
        "metadata": {
            "providerDiagnostics": {
                "tickflowCnBreadth": {
                    "status": "timeout",
                    "credentialState": "configured",
                    "reachabilityState": "timeout",
                    "reasonCode": "tickflow_timeout",
                },
                "backupProvider": {
                    "status": "permission_denied",
                    "credentialState": "missing",
                    "breadthEntitlementState": "permission_denied",
                    "reasonCode": "tickflow_permission_unavailable",
                },
            }
        },
        "marketCacheEventSummary": {
            "metadata": {"countersSource": "process_local"},
            "totals": {
                "hits": 4,
                "misses": "1",
                "staleServed": 2,
                "coldFallbacks": 1,
                "refreshStarted": 1,
                "refreshCompleted": 1,
                "refreshFailed": 0,
            },
        },
    }
    original = copy.deepcopy(input_payload)

    payload = service.from_provider_operations_payload(input_payload)

    assert input_payload == original
    assert payload["groups"]["provider_diagnostics"]["sources"] == [
        "market_provider_operations_payload",
        "provider_diagnostics_projection",
    ]
    assert payload["groups"]["provider_diagnostics"]["counts"] == {
        "configured_provider_count": 2,
        "missing_credential_count": 1,
        "permission_denied_count": 1,
        "timeout_count": 1,
        "fallback_served_count": 2,
        "stale_cache_count": 1,
        "budget_skip_count": 0,
    }
    assert payload["groups"]["market_cache_diagnostics"]["counts"] == {
        "hit_count": 4,
        "miss_count": 1,
        "stale_served_count": 2,
        "cold_fallback_count": 1,
        "refresh_started_count": 1,
        "refresh_completed_count": 1,
        "refresh_failed_count": 0,
    }


def test_from_market_cache_event_summary_maps_totals_without_mutating_inputs() -> None:
    service = BackendMetricsSnapshotService()
    summary = {
        "metadata": {"countersSource": "process_local"},
        "totals": {
            "hits": -3,
            "misses": "5",
            "staleServed": 2.4,
            "coldFallbacks": True,
            "refreshStarted": 2,
            "refreshCompleted": None,
            "refreshFailed": 1,
        },
    }
    original = copy.deepcopy(summary)

    payload = service.from_market_cache_event_summary(summary)

    assert summary == original
    assert payload["groups"]["market_cache_diagnostics"]["sources"] == ["market_cache_event_summary"]
    assert payload["groups"]["market_cache_diagnostics"]["counts"] == {
        "hit_count": 0,
        "miss_count": 5,
        "stale_served_count": 0,
        "cold_fallback_count": 0,
        "refresh_started_count": 2,
        "refresh_completed_count": 0,
        "refresh_failed_count": 1,
    }


def test_from_backtest_support_export_index_maps_available_exports_without_mutating_inputs() -> None:
    service = BackendMetricsSnapshotService()
    index_payload = {
        "run_id": 7001,
        "status": "completed",
        "exports": [
            {"key": "support_bundle_manifest_json", "available": True},
            {"key": "execution_model_metadata_json", "available": True},
            {"key": "oos_parameter_readiness_json", "available": "1"},
            {"key": "regime_attribution_readiness_json", "available": False},
            {"key": "robustness_evidence_json", "available": 1},
        ],
    }
    original = copy.deepcopy(index_payload)

    payload = service.from_backtest_support_export_index(index_payload)

    assert index_payload == original
    assert payload["groups"]["backtest_diagnostics_readiness_exports"]["sources"] == [
        "backtest_support_export_index",
        "stored_readiness_exports",
    ]
    assert payload["groups"]["backtest_diagnostics_readiness_exports"]["counts"] == {
        "rule_run_count": 1,
        "export_index_count": 1,
        "execution_model_metadata_export_count": 1,
        "oos_parameter_readiness_export_count": 1,
        "regime_attribution_readiness_export_count": 0,
        "robustness_evidence_export_count": 1,
        "support_bundle_manifest_export_count": 1,
    }


def test_from_release_gate_summary_maps_foundation_evidence_statuses_without_mutating_inputs() -> None:
    service = BackendMetricsSnapshotService()
    summary_payload = {
        "completedFoundationEvidence": [
            {"id": "provider_sla_live_readiness_preflight", "status": "foundation_evidence_present"},
            {
                "id": "api_abuse_request_safety_completed_foundation_evidence",
                "status": "completed_foundation_evidence_only",
            },
            {
                "id": "operator_evidence_bundle_review_support",
                "status": "review_support_available",
            },
            {
                "id": "manual_release_approval_review_record_validator",
                "status": "offline_validator_available_manual_review_required",
            },
        ],
        "hardBlockers": [
            {"id": "provider_live_probe_opt_in_timeout", "status": "blocking"},
            {"id": "quota_pilot_acceptance", "status": "blocking"},
        ],
    }
    original = copy.deepcopy(summary_payload)

    payload = service.from_release_gate_summary(summary_payload)

    assert summary_payload == original
    assert payload["groups"]["release_gate_foundation_evidence_diagnostics"]["sources"] == [
        "release_gate_summary",
        "foundation_evidence_summary",
    ]
    assert payload["groups"]["release_gate_foundation_evidence_diagnostics"]["counts"] == {
        "foundation_evidence_category_count": 4,
        "accepted_evidence_count": 2,
        "review_required_evidence_count": 2,
        "missing_evidence_count": 2,
        "operator_validator_ready_count": 1,
    }


@pytest.mark.parametrize(
    ("method_name", "target_group"),
    [
        ("from_provider_operations_payload", "provider_diagnostics"),
        ("from_market_cache_event_summary", "market_cache_diagnostics"),
        ("from_backtest_support_export_index", "backtest_diagnostics_readiness_exports"),
        ("from_release_gate_summary", "release_gate_foundation_evidence_diagnostics"),
    ],
)
def test_adapter_methods_degrade_missing_inputs_to_zero_and_unavailable(
    method_name: str,
    target_group: str,
) -> None:
    service = BackendMetricsSnapshotService()

    payload = getattr(service, method_name)({})

    group = payload["groups"][target_group]
    assert group["provenance"] == BACKEND_METRICS_PROVENANCE
    assert group["sources"] == ["unavailable"]
    assert all(value == 0 for value in group["counts"].values())


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
