from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from scripts import domain_test_topology as topology


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "validation" / "domain_test_topology.json"


def load_manifest() -> dict:
    return topology.load_manifest(MANIFEST_PATH)


def test_manifest_schema_preserves_baseline_and_complete_surface_counts() -> None:
    manifest = load_manifest()

    result = topology.validate_manifest(manifest)

    assert result["status"] == "valid"
    assert result["baselineBackendTests"] == 7_609
    assert result["backendTests"] >= result["baselineBackendTests"]
    assert result["vitestFiles"] == 176
    assert result["playwrightSpecs"] == 61
    assert result["playwrightProjectCases"] == 700
    assert manifest["backend"]["baselineCapture"] == {
        "baseSha": topology.BASE_SHA,
        "count": 7_609,
        "sha256": "445301088c77a7235c8ed97c90367203124ec54c87a1e5adc614af43a0aca2f4",
    }


def test_manifest_validator_preserves_explicit_historical_baseline_collection_gap() -> None:
    manifest = load_manifest()
    broken = deepcopy(manifest)
    removed = next(entry for entry in broken["backend"]["tests"] if entry["baseline"])
    broken["backend"]["tests"].remove(removed)
    broken["backend"]["baselineCollectionGaps"] = sorted(
        [*broken["backend"]["baselineCollectionGaps"], removed["id"]]
    )
    current_ids = [entry["id"] for entry in broken["backend"]["tests"]]
    broken["backend"]["currentInventory"] = {
        "count": len(current_ids),
        "sha256": topology.inventory_hash(current_ids),
    }

    result = topology.validate_manifest(broken)

    assert result["baselineBackendTests"] == 7_609
    assert result["backendTests"] == len(current_ids)


def test_backend_ownership_is_unique_sorted_and_represents_every_domain() -> None:
    manifest = load_manifest()
    entries = manifest["backend"]["tests"]
    nodeids = [entry["id"] for entry in entries]

    assert nodeids == sorted(nodeids)
    assert len(nodeids) == len(set(nodeids))
    assert {entry["domain"] for entry in entries} == set(topology.BACKEND_DOMAINS)
    assert topology.inventory_hash(nodeids) == manifest["backend"]["currentInventory"]["sha256"]


def test_inventory_comparison_fails_closed_for_add_delete_rename_and_duplicates() -> None:
    expected = ["tests/test_alpha.py::test_one", "tests/test_beta.py::test_two"]

    assert topology.compare_inventory(expected, expected) == {
        "duplicateExpected": [],
        "duplicateActual": [],
        "missing": [],
        "unowned": [],
    }
    assert topology.compare_inventory(expected, [expected[0], "tests/test_gamma.py::test_three"]) == {
        "duplicateExpected": [],
        "duplicateActual": [],
        "missing": [expected[1]],
        "unowned": ["tests/test_gamma.py::test_three"],
    }
    duplicate = topology.compare_inventory(expected + [expected[0]], expected)
    assert duplicate["duplicateExpected"] == [expected[0]]


def test_manifest_validator_rejects_duplicate_and_unstable_backend_entries() -> None:
    manifest = load_manifest()
    broken = deepcopy(manifest)
    broken["backend"]["tests"].insert(0, deepcopy(broken["backend"]["tests"][0]))

    with pytest.raises(topology.TopologyError, match="duplicate backend ownership"):
        topology.validate_manifest(broken)

    broken = deepcopy(manifest)
    broken["backend"]["tests"][0], broken["backend"]["tests"][1] = (
        broken["backend"]["tests"][1],
        broken["backend"]["tests"][0],
    )
    with pytest.raises(topology.TopologyError, match="sorted deterministically"):
        topology.validate_manifest(broken)


def test_backend_classifier_is_deterministic_for_protected_and_residual_domains() -> None:
    examples = {
        "tests/api/test_auth_rbac.py::test_denied": "auth_security",
        "tests/test_yfinance_provider.py::test_quote": "provider_external_network",
        "tests/test_market_overview.py::test_state": "market",
        "tests/test_scanner_service.py::test_rank": "scanner",
        "tests/test_backtest_engine.py::test_fill": "backtest",
        "tests/test_portfolio_ledger.py::test_cash": "portfolio_broker",
        "tests/test_storage_migration.py::test_upgrade": "database_storage_migrations",
        "tests/api/test_health_endpoint.py::test_shape": "api_schema_contracts",
        "tests/scripts/test_tool.py::test_cli": "runtime_operator_tooling",
        "tests/test_miscellaneous.py::test_integration": "residual_repository_integration",
    }

    assert {nodeid: topology.classify_backend(nodeid) for nodeid in examples} == examples


def test_vitest_ownership_has_explicit_milestones_and_identifies_large_files() -> None:
    manifest = load_manifest()
    entries = manifest["vitest"]["files"]

    assert len(entries) == len({entry["path"] for entry in entries}) == 176
    assert {entry["owner"] for entry in entries} <= set(manifest["vitest"]["owners"])
    assert any(entry["owner"] == "milestone_t448_consumer_product" for entry in entries)
    assert any(entry["owner"] == "milestone_t451_auth_session" for entry in entries)
    assert manifest["vitest"]["largeOwnerFiles"]
    assert all(entry["bytes"] >= manifest["vitest"]["largeFileThresholdBytes"] for entry in manifest["vitest"]["largeOwnerFiles"])


def test_playwright_ownership_retains_projects_and_mandatory_auth_cases() -> None:
    manifest = load_manifest()
    playwright = manifest["playwright"]
    specs = playwright["specs"]
    cases = playwright["projectCases"]

    assert len(specs) == 61
    assert len(cases) == 700
    assert playwright["inventory"]["projectCaseCounts"] == {"chromium": 350, "chromium-mobile": 350}
    assert {spec["owner"] for spec in specs} == set(topology.PLAYWRIGHT_CLASSES)
    protected_auth_specs = [spec for spec in specs if any(word in spec["path"] for word in ("auth", "session", "rbac"))]
    assert protected_auth_specs
    assert all(spec["owner"] == "protected_critical" and spec["mandatory"] for spec in protected_auth_specs)
    protected_paths = {spec["path"] for spec in protected_auth_specs}
    assert all(case["mandatory"] for case in cases if case["spec"] in protected_paths)
    protected_behavior_cases = [case for case in cases if topology.playwright_case_requires_protection(case["id"])]
    assert protected_behavior_cases
    assert all(case["owner"] == "protected_critical" and case["mandatory"] for case in protected_behavior_cases)


def test_first_attempts_and_retries_are_never_coalesced() -> None:
    records = [
        {"id": "case-a", "retry": 0, "status": "failed"},
        {"id": "case-a", "retry": 1, "status": "passed"},
        {"id": "case-b", "retry": 0, "status": "passed"},
    ]

    result = topology.split_attempt_records(records)

    assert [record["id"] for record in result["firstAttempts"]] == ["case-a", "case-b"]
    assert result["firstAttempts"][0]["status"] == "failed"
    assert result["retries"] == [{"id": "case-a", "retry": 1, "status": "passed"}]
    classification = topology.classify_failures(["test-a", "test-b"], ["test-b", "test-c"])
    assert classification == {
        "establishedBaselineFailures": ["test-b"],
        "unknownFirstAttemptFailures": ["test-a"],
    }
