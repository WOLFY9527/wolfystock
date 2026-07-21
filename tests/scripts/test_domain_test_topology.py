from __future__ import annotations

from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest
from _pytest.unittest import SubtestContext, SubtestReport

from scripts import domain_test_topology as topology
from scripts import validation_changed_files as planner


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "validation" / "domain_test_topology.json"
OWNER_MANIFEST_PATH = ROOT / "validation" / "validation_owners.json"


def load_manifest() -> dict:
    return topology.load_manifest(MANIFEST_PATH)


def selector_plan_for(path: str) -> dict:
    manifest, manifest_hash = planner.load_owner_manifest(OWNER_MANIFEST_PATH, root=ROOT)
    change = {
        "path": path,
        "changeTypes": ["modified"],
        "sources": ["committed"],
        "ownershipTrees": ["base_and_candidate"],
        "observations": [],
    }
    candidate = {
        "commitSha": "2" * 40,
        "treeSha": "3" * 40,
        "workingTreeSha256": "4" * 64,
        "dirty": False,
    }
    return planner.build_validation_plan_from_changes(
        [change],
        manifest,
        root=ROOT,
        base_ref="base",
        base_sha="1" * 40,
        candidate_ref="candidate",
        candidate_sha="2" * 40,
        change_source="committed",
        manifest_hash=manifest_hash,
        candidate_identity=candidate,
    )


def selector_diagnostic(
    scenario: str,
    changed_file: str,
    expected_tier: str,
    expected_gates: set[str],
    plan: dict,
    reason: str = "",
) -> str:
    return (
        f"scenario={scenario}; changed_file={changed_file}; expected_tier={expected_tier}; "
        f"expected_gates={sorted(expected_gates)}; actual_tier={plan['risk']['class']}; "
        f"actual_gates={[gate['id'] for gate in plan['gates']]}; "
        f"rejection_reason={reason or '<none>'}"
    )


def test_manifest_schema_preserves_baseline_and_complete_surface_counts() -> None:
    manifest = load_manifest()

    result = topology.validate_manifest(manifest)

    assert result["status"] == "valid"
    assert result["baselineBackendTests"] == 7_609
    assert result["backendTests"] == 7_932
    assert result["vitestFiles"] == 176
    assert result["playwrightSpecs"] == 64
    assert result["playwrightProjectCases"] == 718
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

    for scenario, changed_file, expected_tier, expected_required in (
        ("topology-trigger-test-change", "tests/test_local_helper.py", "R1", True),
        ("topology-trigger-shared-source", "apps/dsa-web/src/components/SharedWidget.tsx", "R3", False),
    ):
        plan = selector_plan_for(changed_file)
        topology_gate = next(gate for gate in plan["gates"] if gate["id"] == "topology.verify")
        expected_gates = {
            gate_id
            for level in planner.RISK_CLASSES[: planner.RISK_CLASSES.index(expected_tier) + 1]
            for gate_id in planner.RISK_GATE_FLOORS[level]
        }
        if expected_tier == "R1":
            expected_gates.add("topology.verify")
        if expected_tier == "R3":
            expected_gates.add("browser.protected")
        diagnostic = selector_diagnostic(scenario, changed_file, expected_tier, expected_gates, plan)
        assert plan["risk"]["class"] == expected_tier, diagnostic
        assert {gate["id"] for gate in plan["gates"]} == expected_gates, diagnostic
        assert plan["risk"]["topologyMayChange"] is expected_required, diagnostic
        assert topology_gate["required"] is expected_required, diagnostic
        if expected_required:
            assert topology_gate["selectionReason"] == "topology_inventory_may_change", diagnostic


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

    assert len(specs) == 64
    assert len(cases) == 718
    assert playwright["inventory"]["projectCaseCounts"] == {
        "chromium": 357,
        "chromium-mobile": 357,
        "release-real-runtime": 4,
    }
    assert {spec["owner"] for spec in specs} == set(topology.PLAYWRIGHT_CLASSES)
    protected_auth_specs = [spec for spec in specs if any(word in spec["path"] for word in ("auth", "session", "rbac"))]
    assert protected_auth_specs
    assert all(spec["owner"] == "protected_critical" and spec["mandatory"] for spec in protected_auth_specs)
    protected_paths = {spec["path"] for spec in protected_auth_specs}
    assert all(case["mandatory"] for case in cases if case["spec"] in protected_paths)
    protected_behavior_cases = [case for case in cases if topology.playwright_case_requires_protection(case["id"])]
    assert protected_behavior_cases
    assert all(case["owner"] == "protected_critical" and case["mandatory"] for case in protected_behavior_cases)
    release_path = "apps/dsa-web/e2e/release-real-runtime.release.spec.ts"
    release_spec = next(spec for spec in specs if spec["path"] == release_path)
    release_cases = [case for case in cases if case["spec"] == release_path]
    assert release_spec == {"path": release_path, "owner": "bounded_integration", "mandatory": False}
    assert len(release_cases) == 4
    assert sum(case["owner"] == "protected_critical" and case["mandatory"] for case in release_cases) == 1
    assert sum(case["owner"] == "bounded_integration" and not case["mandatory"] for case in release_cases) == 3


def test_first_attempts_and_retries_are_never_coalesced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_active_config = topology._ACTIVE_TEST_RESULT_CONFIG
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

    parent_id = "tests/scripts/test_fixture.py::FixtureCase::test_parent"
    child_id = f"{parent_id}::subtest:{'a' * 64}:0"
    event_state = {
        "owners": {parent_id: "runtime_operator_tooling"},
        "children": [],
        "childOrdinals": Counter(),
    }
    event_config = type("EventConfig", (), {"_test_result_evidence": event_state})()
    monkeypatch.setattr(topology, "_ACTIVE_TEST_RESULT_CONFIG", event_config)
    topology.pytest_runtest_logreport(
        SubtestReport(
            nodeid=parent_id,
            location=("tests/scripts/test_fixture.py", 1, "test_parent"),
            keywords={},
            outcome="failed",
            longrepr="fixture failure",
            when="call",
            duration=0.1,
            context=SubtestContext(msg=None, kwargs={"reason": "not_configured"}),
        )
    )
    assert event_state["children"][0]["outcome"] == "failed"
    assert event_state["children"][0]["presentation"].startswith("SUBFAILED(")
    assert event_state["children"][0]["parentId"] == parent_id

    selected_ids = [parent_id]
    command = ["python", "-m", "pytest", "--domain-topology-verify-full"]
    identity = {
        "candidate": {
            "commitSha": "1" * 40,
            "treeSha": "2" * 40,
            "workingTreeSha256": "3" * 64,
            "dirty": False,
        },
        "environment": {"fingerprint": "4" * 64},
        "dependencyLock": {
            "contentHash": "5" * 64,
            "selectedLock": "requirements-python311-dev.lock",
            "selectedProjection": "darwin-arm64-cpython311-development",
            "selectedProjectionHash": "6" * 64,
        },
        "command": {
            "argv": command,
            "sha256": topology.canonical_json_hash(command),
        },
        "selection": {
            "count": 1,
            "sha256": topology.inventory_hash(selected_ids),
        },
        "topology": {
            "count": 1,
            "sha256": topology.inventory_hash(selected_ids),
        },
    }
    evidence = {
        "schemaVersion": topology.TEST_RESULT_SCHEMA_VERSION,
        "kind": "attempt",
        "state": "completed",
        "surface": "backend",
        "identity": identity,
        "attempt": {"index": 0, "kind": "first"},
        "timing": {
            "startedAtUtc": "2026-07-19T12:00:00Z",
            "endedAtUtc": "2026-07-19T12:00:01Z",
            "wallSeconds": 1.0,
        },
        "exitCode": 1,
        "status": "failed",
        "counts": {
            "parents": {outcome: int(outcome == "passed") for outcome in topology.TEST_OUTCOMES},
            "children": {outcome: int(outcome == "failed") for outcome in topology.TEST_OUTCOMES},
        },
        "parents": [
            {
                "id": parent_id,
                "kind": "parent",
                "owner": "runtime_operator_tooling",
                "outcome": "passed",
                "failureFamily": None,
                "durationSeconds": 1.0,
            }
        ],
        "children": [
            {
                "id": child_id,
                "parentId": parent_id,
                "kind": "unittest_subtest",
                "owner": "runtime_operator_tooling",
                "outcome": "failed",
                "failureFamily": None,
                "durationSeconds": 0.0,
                "contextSha256": "a" * 64,
                "presentation": "SUBFAILED(reason='not_configured')",
            }
        ],
        "artifacts": [
            {"kind": "log", "path": "attempt-0.log", "sha256": "7" * 64},
            {"kind": "junit", "path": "attempt-0.junit.xml", "sha256": "8" * 64},
        ],
    }

    validated = topology.validate_test_result_evidence(evidence, expected_identity=identity)

    assert validated["counts"]["parents"]["passed"] == 1
    assert validated["counts"]["parents"]["failed"] == 0
    assert validated["counts"]["children"]["failed"] == 1
    assert validated["children"][0]["presentation"].startswith("SUBFAILED(")
    assert topology._failed_parent_ids(validated) == [parent_id]

    successful = deepcopy(evidence)
    successful["exitCode"] = 0
    successful["status"] = "passed"
    successful["children"] = []
    successful["counts"] = {
        "parents": {outcome: int(outcome == "passed") for outcome in topology.TEST_OUTCOMES},
        "children": {outcome: 0 for outcome in topology.TEST_OUTCOMES},
    }
    assert topology.validate_test_result_evidence(successful)["status"] == "passed"

    terminal_outcomes = {
        "skipped": 0,
        "cancelled": 2,
        "missing": 3,
        "unknown": 3,
    }
    for outcome, exit_code in terminal_outcomes.items():
        terminal = deepcopy(successful)
        terminal["exitCode"] = exit_code
        terminal["status"] = outcome
        terminal["parents"][0]["outcome"] = outcome
        terminal["counts"]["parents"] = {
            candidate: int(candidate == outcome) for candidate in topology.TEST_OUTCOMES
        }
        assert topology.validate_test_result_evidence(terminal)["status"] == outcome
        assert terminal["status"] != "passed"
        misclassified = deepcopy(terminal)
        misclassified["status"] = "passed"
        with pytest.raises(topology.TopologyError, match="status does not match"):
            topology.validate_test_result_evidence(misclassified)

    assert topology._test_result_exit_code(process_exit_code=0, status="passed") == 0
    assert topology._test_result_exit_code(process_exit_code=0, status="skipped") == 0
    assert topology._test_result_exit_code(process_exit_code=1, status="failed") == 1
    assert topology._test_result_exit_code(process_exit_code=2, status="cancelled") == 2
    assert topology._test_result_exit_code(process_exit_code=0, status="missing") == 1
    assert topology._test_result_exit_code(process_exit_code=0, status="unknown") == 1

    emitted_outcomes = {
        pytest.ExitCode.OK: "missing",
        pytest.ExitCode.INTERRUPTED: "cancelled",
        pytest.ExitCode.INTERNAL_ERROR: "unknown",
    }
    for exit_status, expected_outcome in emitted_outcomes.items():
        emitted_path = tmp_path / f"emitted-{int(exit_status)}.json"
        emitted_state = {
            "output": emitted_path,
            "identity": identity,
            "attempt": {"index": 0, "kind": "first"},
            "startedAtUtc": "2026-07-19T12:00:00Z",
            "timer": topology.time.perf_counter(),
            "parents": {},
            "children": [],
            "owners": {parent_id: "runtime_operator_tooling"},
            "selectedIds": [parent_id],
        }
        emitted_config = type("EmittedConfig", (), {"_test_result_evidence": emitted_state})()
        emitted_session = type("EmittedSession", (), {"config": emitted_config})()
        monkeypatch.setattr(topology, "_ACTIVE_TEST_RESULT_CONFIG", emitted_config)
        topology.pytest_sessionfinish(emitted_session, exit_status)
        emitted = topology.load_test_result_evidence(emitted_path, require_completed=False)
        assert emitted["status"] == "incomplete"
        assert emitted["parents"][0]["outcome"] == expected_outcome
        assert emitted["counts"]["parents"][expected_outcome] == 1

    retry = deepcopy(evidence)
    retry["attempt"] = {"index": 1, "kind": "retry"}
    assert topology.validate_test_result_evidence(retry)["attempt"]["kind"] == "retry"
    retry["attempt"]["kind"] = "first"
    with pytest.raises(topology.TopologyError, match="kind/index mismatch"):
        topology.validate_test_result_evidence(retry)

    collapsed_child_failure = deepcopy(evidence)
    collapsed_child_failure["status"] = "passed"
    with pytest.raises(topology.TopologyError, match="status does not match"):
        topology.validate_test_result_evidence(collapsed_child_failure)

    malformed = deepcopy(evidence)
    del malformed["children"][0]["outcome"]
    with pytest.raises(topology.TopologyError, match="child outcome"):
        topology.validate_test_result_evidence(malformed)

    missing_path = tmp_path / "missing.json"
    with pytest.raises(topology.TopologyError, match="missing or malformed"):
        topology.load_test_result_evidence(missing_path)
    malformed_path = tmp_path / "malformed.json"
    malformed_path.write_text("{", encoding="utf-8")
    with pytest.raises(topology.TopologyError, match="missing or malformed"):
        topology.load_test_result_evidence(malformed_path)

    incomplete = deepcopy(evidence)
    incomplete["state"] = "incomplete"
    with pytest.raises(topology.TopologyError, match="incomplete"):
        topology.validate_test_result_evidence(incomplete)

    mismatched_identity = deepcopy(identity)
    mismatched_identity["command"]["sha256"] = "9" * 64
    with pytest.raises(topology.TopologyError, match="identity mismatch"):
        topology.validate_test_result_evidence(evidence, expected_identity=mismatched_identity)

    monkeypatch.setattr(topology, "_ACTIVE_TEST_RESULT_CONFIG", original_active_config)
    selector_plan = selector_plan_for("tests/scripts/test_domain_test_topology.py")
    for scenario, field, value in (
        ("candidate-commit-identity-mismatch", "commitSha", "8" * 40),
        ("candidate-tree-identity-mismatch", "treeSha", "9" * 40),
        ("candidate-worktree-identity-mismatch", "workingTreeSha256", "a" * 64),
    ):
        mismatched = deepcopy(identity)
        mismatched["candidate"][field] = value
        diagnostic = selector_diagnostic(
            scenario,
            "tests/scripts/test_domain_test_topology.py",
            "R1",
            {
                "scope.diff",
                "security.changed",
                "syntax.changed",
                "tests.backend.changed",
                "tests.frontend.changed",
                "topology.verify",
            },
            selector_plan,
        )
        try:
            topology.validate_test_result_evidence(evidence, expected_identity=mismatched)
        except topology.TopologyError as exc:
            assert "identity mismatch" in str(exc), f"{diagnostic}; actual={exc}"
        else:
            pytest.fail(f"{diagnostic}; actual=accepted")

    topology_mismatch = deepcopy(identity)
    topology_mismatch["topology"]["sha256"] = "b" * 64
    diagnostic = selector_diagnostic(
        "topology-identity-mismatch",
        "tests/scripts/test_domain_test_topology.py",
        "R1",
        {
            "scope.diff",
            "security.changed",
            "syntax.changed",
            "tests.backend.changed",
            "tests.frontend.changed",
            "topology.verify",
        },
        selector_plan,
    )
    try:
        topology.validate_test_result_evidence(evidence, expected_identity=topology_mismatch)
    except topology.TopologyError as exc:
        assert "identity mismatch" in str(exc), f"{diagnostic}; actual={exc}"
    else:
        pytest.fail(f"{diagnostic}; actual=accepted")

    gate = (ROOT / "scripts" / "ci_gate.sh").read_text(encoding="utf-8")
    assert "domain_test_topology.py" in gate
    assert "run-backend" in gate
    assert "--retry-failures 0" in gate
    assert '"${PYTHON_BIN}" -m pytest --domain-topology-verify-full' not in gate
    fast_gate = (ROOT / "scripts" / "ci_gate_fast.sh").read_text(encoding="utf-8")
    assert 'mktemp -d "${ROOT_DIR}/output/ci_gate_fast.XXXXXX"' in fast_gate
    assert '--project-backend-shard-plan "${RAW_FULL_PLAN}"' in gate
    assert 'VALIDATION_TIER="canonical"' in gate
    assert 'RELEASE_CANDIDATE="output/release/candidate/release-candidate.json"' in gate
    assert "release candidate evidence requires --tier release" in gate
    assert 'VALIDATION_TIER="release"' in gate
    assert 'local plan_args=(' in gate
    assert '"${plan_args[@]}"' in gate
    assert "release_args" not in gate
    assert "release-ready=false" in gate
    assert "--backend-stage-plan" in fast_gate
    assert "--validation-tier" in fast_gate
    assert "--deselect" not in gate + fast_gate
    assert "--ignore" not in gate + fast_gate
    from tests import conftest as shard

    manifest, manifest_hash = planner.load_owner_manifest(OWNER_MANIFEST_PATH, root=ROOT)
    risk_plan = planner.build_validation_plan_from_changes(
        [
            {
                "path": "docs/audit-note.md",
                "changeTypes": ["modified"],
                "sources": ["committed"],
                "ownershipTrees": ["base_and_candidate"],
                "observations": [],
            }
        ],
        manifest,
        root=ROOT,
        base_ref="base",
        base_sha="1" * 40,
        candidate_ref="candidate",
        candidate_sha="2" * 40,
        change_source="committed",
        manifest_hash=manifest_hash,
        candidate_identity={
            "commitSha": "2" * 40,
            "treeSha": "3" * 40,
            "workingTreeSha256": "4" * 64,
            "dirty": False,
        },
        requested_risk="R3",
        accepted_integration=True,
    )
    risk_path = tmp_path / "risk-plan.json"
    risk_path.write_bytes(planner.canonical_json_bytes(risk_plan) + b"\n")
    full = shard.build_backend_shard_plan(risk_path, scope="full")

    canonical = planner.project_backend_shard_plan(risk_plan, full, tier="canonical")
    release = planner.project_backend_shard_plan(risk_plan, full, tier="release")

    assert canonical["schemaVersion"] == full["schemaVersion"]
    assert canonical["structuredResultAuthority"] == topology.TEST_RESULT_SCHEMA_VERSION
    assert canonical["topology"] == load_manifest()["backend"]["currentInventory"]
    assert canonical["selection"]["count"] == 7_914
    assert release["selection"]["count"] == 7_932
    assert release["selection"] == full["selection"]
    assert set(canonical["validationStages"]["execution"]["nodeIds"]) == {
        node_id for item in canonical["shards"] for node_id in item["nodeIds"]
    }
    assert len(canonical["shards"]) == len(release["shards"]) == 2
    assert all(item["nodeIds"] for item in canonical["shards"])
    assert shard._validate_backend_shard_plan(canonical) == canonical
    assert shard._validate_backend_shard_plan(release) == release

    malformed = deepcopy(full)
    malformed["planHash"] = "0" * 64
    with pytest.raises(planner.SelectionError, match="shard plan"):
        planner.project_backend_shard_plan(risk_plan, malformed, tier="canonical")
