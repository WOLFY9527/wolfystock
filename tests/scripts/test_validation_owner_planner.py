from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

from scripts import domain_test_topology as topology
from scripts import validation_changed_files as planner
from scripts import validation_resume as resume


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "validation" / "validation_owners.json"
TOPOLOGY_PATH = ROOT / "validation" / "domain_test_topology.json"
DUMMY_SHA = "1" * 40
DUMMY_CANDIDATE_SHA = "2" * 40
DUMMY_TREE = "3" * 40
DUMMY_WORKTREE = "4" * 64


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def write(repo: Path, path: str, content: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def init_repo(repo: Path) -> str:
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "validation@example.invalid")
    git(repo, "config", "user.name", "Validation Test")
    git(repo, "config", "core.autocrlf", "false")
    write(repo, "README.md", "base\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    return git(repo, "rev-parse", "HEAD")


def load_manifest() -> tuple[dict, str]:
    return planner.load_owner_manifest(MANIFEST_PATH, root=ROOT)


def changed(path: str, change_type: str = "modified") -> dict:
    return {
        "path": path,
        "changeTypes": [change_type],
        "sources": ["committed"],
        "ownershipTrees": ["base_and_candidate"],
        "observations": [
            {
                "path": path,
                "source": "committed",
                "status": "M",
                "changeType": change_type,
                "ownershipTree": "base_and_candidate",
            }
        ],
    }


def plan_for(paths: list[str], *, manifest: dict | None = None) -> dict:
    loaded, manifest_hash = load_manifest()
    selected_manifest = manifest or loaded
    return planner.build_shadow_plan_from_changes(
        [changed(path) for path in paths],
        selected_manifest,
        root=ROOT,
        base_ref="base",
        base_sha=DUMMY_SHA,
        candidate_ref="candidate",
        candidate_sha="2" * 40,
        change_source="committed",
        manifest_hash=manifest_hash,
    )


def change_by_path(plan: dict, path: str) -> dict:
    return next(change for change in plan["changes"] if change["path"] == path)


def candidate_identity() -> dict:
    return {
        "commitSha": DUMMY_CANDIDATE_SHA,
        "treeSha": DUMMY_TREE,
        "workingTreeSha256": DUMMY_WORKTREE,
        "dirty": False,
    }


def risk_change(path: str, *change_types: str) -> dict:
    return changed(path, change_types[0] if change_types else "modified")


def risk_plan_for(
    paths: list[str],
    *,
    changes: list[dict] | None = None,
    requested_risk: str | None = None,
    requested_gates: tuple[str, ...] = (),
    frozen_release: bool = False,
    accepted_integration: bool = False,
    user_facing: bool = False,
    release_runtime: bool = False,
) -> dict:
    manifest, manifest_hash = load_manifest()
    raw_changes = changes if changes is not None else [risk_change(path) for path in paths]
    return planner.build_validation_plan_from_changes(
        raw_changes,
        manifest,
        root=ROOT,
        base_ref="base",
        base_sha=DUMMY_SHA,
        candidate_ref="candidate",
        candidate_sha=DUMMY_CANDIDATE_SHA,
        change_source="committed",
        manifest_hash=manifest_hash,
        candidate_identity=candidate_identity(),
        requested_risk=requested_risk,
        requested_gates=requested_gates,
        frozen_release=frozen_release,
        accepted_integration=accepted_integration,
        user_facing=user_facing,
        release_runtime=release_runtime,
    )


def scenario_diagnostic(
    scenario: str,
    changed_file: str,
    expected_tier: str,
    expected_gates: set[str],
    plan: dict,
    *,
    reason: str = "",
) -> str:
    actual_gates = {gate["id"] for gate in plan.get("gates", [])}
    return (
        f"scenario={scenario}; changed_file={changed_file}; expected_tier={expected_tier}; "
        f"expected_gates={sorted(expected_gates)}; actual_tier={plan.get('risk', {}).get('class')}; "
        f"actual_gates={sorted(actual_gates)}; rejection_reason={reason or '<none>'}"
    )


def cumulative_gate_ids(risk_class: str) -> set[str]:
    index = planner.RISK_CLASSES.index(risk_class)
    return {
        gate_id
        for level in planner.RISK_CLASSES[: index + 1]
        for gate_id in planner.RISK_GATE_FLOORS[level]
    }


def _write_aggregate(
    tmp_path: Path,
    plan: dict,
    *,
    gate_id: str = "backend.canonical",
    outcome: str = "passed",
    retry: bool = False,
) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    gate = next(gate for gate in plan["gates"] if gate["id"] == gate_id)
    manifest = topology.load_manifest(TOPOLOGY_PATH)
    selected_ids = [
        entry["id"] for entry in manifest["backend"]["tests"] if entry["domain"] in gate["domains"]
    ]
    attempt_identity = {
        "candidate": plan["identity"]["candidate"],
        "environment": {"fingerprint": "5" * 64},
        "dependencyLock": {
            "contentHash": "6" * 64,
            "selectedLock": "requirements-python311-dev.lock",
            "selectedProjection": "darwin-arm64-cpython311-development",
            "selectedProjectionHash": "7" * 64,
        },
        "command": {
            "argv": gate["structuredCommand"],
            "sha256": topology.canonical_json_hash(gate["structuredCommand"]),
        },
        "selection": {"count": len(selected_ids), "sha256": topology.inventory_hash(selected_ids)},
        "topology": manifest["backend"]["currentInventory"],
    }
    exit_code = {"passed": 0, "skipped": 0, "cancelled": 2, "missing": 3, "unknown": 3}[outcome]
    owners = {entry["id"]: entry["domain"] for entry in manifest["backend"]["tests"]}
    parents = [
        {
            "id": node_id,
            "kind": "parent",
            "owner": owners[node_id],
            "outcome": outcome,
            "failureFamily": None,
            "durationSeconds": 0.0,
        }
        for node_id in selected_ids
    ]
    attempt = {
        "schemaVersion": topology.TEST_RESULT_SCHEMA_VERSION,
        "kind": "attempt",
        "state": "completed",
        "surface": "backend",
        "identity": attempt_identity,
        "attempt": {"index": 0, "kind": "first"},
        "timing": {
            "startedAtUtc": "2026-07-19T12:00:00Z",
            "endedAtUtc": "2026-07-19T12:00:01Z",
            "wallSeconds": 1.0,
        },
        "exitCode": exit_code,
        "status": outcome,
        "counts": {
            "parents": {
                candidate: len(selected_ids) if candidate == outcome else 0
                for candidate in topology.TEST_OUTCOMES
            },
            "children": {candidate: 0 for candidate in topology.TEST_OUTCOMES},
        },
        "parents": parents,
        "children": [],
        "artifacts": [],
    }
    log = tmp_path / "attempt-0.log"
    junit = tmp_path / "attempt-0.junit.xml"
    log.write_text("fixture\n", encoding="utf-8")
    junit.write_text("<testsuite/>\n", encoding="utf-8")
    attempt["artifacts"] = [
        {"kind": "junit", "path": junit.name, "sha256": planner.file_hash(junit)},
        {"kind": "log", "path": log.name, "sha256": planner.file_hash(log)},
    ]
    topology.validate_test_result_evidence(attempt, expected_identity=attempt_identity)
    attempt_path = tmp_path / "attempt-0.json"
    attempt_path.write_text(json.dumps(attempt, sort_keys=True), encoding="utf-8")
    summary = {
        "path": attempt_path.name,
        "sha256": planner.file_hash(attempt_path),
        "state": "completed",
        "attemptIndex": 0,
        "startedAtUtc": attempt["timing"]["startedAtUtc"],
        "endedAtUtc": attempt["timing"]["endedAtUtc"],
        "durationSeconds": 1.0,
        "exitCode": exit_code,
        "status": outcome,
        "counts": attempt["counts"],
        "failures": [],
        "identity": attempt_identity,
    }
    aggregate = {
        "schemaVersion": topology.TEST_RESULT_SCHEMA_VERSION,
        "kind": "aggregate",
        "state": "completed",
        "surface": "backend-domain-aggregate",
        "authority": "structured-test-result",
        "createdAt": "2026-07-19T12:00:01Z",
        "identity": attempt_identity,
        "domains": gate["domains"],
        "selectedCount": len(selected_ids),
        "durationSeconds": 1.0,
        "firstAttempt": summary,
        "retries": [summary] if retry else [],
        "establishedBaselineFailures": [],
        "unknownFirstAttemptFailures": [],
        "remainingFailuresAfterRetries": [],
        "status": outcome if outcome in {"passed", "skipped"} else f"{outcome}_first_attempt",
    }
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(aggregate, sort_keys=True), encoding="utf-8")
    return result_path


def assert_rejected(
    scenario: str,
    changed_file: str,
    plan: dict,
    result_path: Path,
    expected_message: str,
) -> None:
    expected_tier = plan["risk"]["class"]
    expected_gates = {gate["id"] for gate in plan["gates"]}
    try:
        planner.consume_structured_backend_result(plan, result_path, gate_id="backend.canonical")
    except planner.SelectionError as exc:
        assert expected_message in str(exc), scenario_diagnostic(
            scenario, changed_file, expected_tier, expected_gates, plan, reason=str(exc)
        )
        return
    pytest.fail(
        scenario_diagnostic(
            scenario, changed_file, expected_tier, expected_gates, plan, reason="evidence accepted"
        )
    )


def test_clean_base_and_branch_ahead_commit_are_collected(tmp_path: Path) -> None:
    base_sha = init_repo(tmp_path)
    clean_observations, _, _ = planner.collect_shadow_observations(base_sha, "HEAD", root=tmp_path)
    assert clean_observations == []

    write(tmp_path, "scripts/tool.py", "print('shadow')\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "branch ahead")

    observations, resolved_base, candidate_sha = planner.collect_shadow_observations(
        base_sha,
        "HEAD",
        root=tmp_path,
    )
    changes = planner.aggregate_observations(observations)

    assert resolved_base == base_sha
    assert candidate_sha == git(tmp_path, "rev-parse", "HEAD")
    assert [change["path"] for change in changes] == ["scripts/tool.py"]
    assert changes[0]["sources"] == ["committed"]
    assert changes[0]["changeTypes"] == ["added"]

    empty_plan = risk_plan_for([])
    expected_gates = cumulative_gate_ids("R0")
    diagnostic = scenario_diagnostic("empty-changed-input", "<empty>", "R0", expected_gates, empty_plan)
    assert empty_plan["risk"]["class"] == "R0", diagnostic
    assert {gate["id"] for gate in empty_plan["gates"]} == expected_gates, diagnostic
    assert all(
        gate["command"] != [planner.sys.executable, "-m", "pytest", "-q"]
        for gate in empty_plan["gates"]
    ), diagnostic


def test_branch_staged_unstaged_and_untracked_are_a_lossless_union(tmp_path: Path) -> None:
    write(tmp_path, "src/core.py", "VALUE = 1\n")
    write(tmp_path, "docs/guide.md", "base\n")
    base_sha = init_repo(tmp_path)

    write(tmp_path, "bot/committed.py", "COMMITTED = True\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "branch ahead")
    write(tmp_path, "api/staged.py", "STAGED = True\n")
    git(tmp_path, "add", "api/staged.py")
    write(tmp_path, "docs/guide.md", "unstaged\n")
    write(tmp_path, "mystery/untracked.bin", "untracked\n")

    observations, _, _ = planner.collect_shadow_observations(base_sha, "HEAD", root=tmp_path)
    changes = {change["path"]: change for change in planner.aggregate_observations(observations)}

    assert set(changes) == {
        "api/staged.py",
        "bot/committed.py",
        "docs/guide.md",
        "mystery/untracked.bin",
    }
    assert changes["bot/committed.py"]["sources"] == ["committed"]
    assert changes["api/staged.py"]["sources"] == ["staged"]
    assert changes["docs/guide.md"]["sources"] == ["unstaged"]
    assert changes["mystery/untracked.bin"]["sources"] == ["untracked"]


def test_rename_deletion_and_copy_include_source_and_destination_ownership(tmp_path: Path) -> None:
    write(tmp_path, "src/old_name.py", "RENAMED = 'unique'\n")
    write(tmp_path, "api/deleted.py", "DELETED = True\n")
    write(tmp_path, "src/copy_source.py", "COPIED = 'different unique content'\n")
    base_sha = init_repo(tmp_path)

    git(tmp_path, "mv", "src/old_name.py", "src/new_name.py")
    git(tmp_path, "rm", "-q", "api/deleted.py")
    write(tmp_path, "src/copy_destination.py", (tmp_path / "src/copy_source.py").read_text(encoding="utf-8"))
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "rename delete copy")

    observations, _, _ = planner.collect_shadow_observations(
        base_sha,
        "HEAD",
        root=tmp_path,
        change_source="committed",
    )
    changes = {change["path"]: change for change in planner.aggregate_observations(observations)}

    assert "rename_source" in changes["src/old_name.py"]["changeTypes"]
    assert changes["src/old_name.py"]["ownershipTrees"] == ["base"]
    assert "rename_destination" in changes["src/new_name.py"]["changeTypes"]
    assert "deleted" in changes["api/deleted.py"]["changeTypes"]
    assert changes["api/deleted.py"]["ownershipTrees"] == ["base"]
    assert "copy_source" in changes["src/copy_source.py"]["changeTypes"]
    assert "copy_destination" in changes["src/copy_destination.py"]["changeTypes"]

    deleted_path = "tests/removed_validation.py"
    deleted_plan = risk_plan_for([], changes=[risk_change(deleted_path, "deleted")])
    calls: list[list[str]] = []

    def runner(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    execution = planner.execute_validation_plan(
        deleted_plan,
        output_dir=tmp_path / "deleted-plan",
        root=ROOT,
        runner=runner,
        candidate_identity=candidate_identity(),
    )
    expected_gates = cumulative_gate_ids("R1") | {"topology.verify"}
    diagnostic = scenario_diagnostic(
        "deleted-input-empty-suite-fail-closed",
        deleted_path,
        "R1",
        expected_gates,
        deleted_plan,
        reason=execution["gates"][-1].get("reason", ""),
    )
    assert deleted_plan["changes"][0]["changeTypes"] == ["deleted"], diagnostic
    assert execution["status"] == "failed" and execution["exitCode"] == 2, diagnostic
    assert "required command input unavailable" in execution["gates"][-1]["reason"], diagnostic
    assert all(command != [planner.sys.executable, "-m", "pytest", "-q"] for command in calls), diagnostic


def test_overlapping_rules_union_all_owners_and_tiers() -> None:
    path = "src/services/market_scanner_service.py"

    plan = plan_for([path])
    item = change_by_path(plan, path)

    assert {"backend-python", "protected-scanner"}.issubset(item["matchedRules"])
    assert "direct.python.syntax" in item["ownerIds"]
    assert "complete.backend.non_network" in item["ownerIds"]
    assert "complete.scanner.contracts" in item["ownerIds"]
    assert "protected.baseline.compare" in item["ownerIds"]
    assert {"direct_owner", "bounded_integration", "complete_domain", "milestone", "release"}.issubset(
        item["selectedTiers"]
    )

    previous: set[str] = set()
    for level in planner.RISK_CLASSES:
        cumulative = risk_plan_for(
            ["docs/audit-note.md"],
            requested_risk=level,
            accepted_integration=level in {"R3", "R4", "R5"},
            frozen_release=level == "R5",
        )
        expected = cumulative_gate_ids(level)
        if level in {"R3", "R4", "R5"}:
            expected.add("backend.canonical")
        actual = {gate["id"] for gate in cumulative["gates"]}
        diagnostic = scenario_diagnostic(
            f"cumulative-{level}", "docs/audit-note.md", level, expected, cumulative
        )
        assert cumulative["risk"]["class"] == level, diagnostic
        assert actual == expected, diagnostic
        assert previous.issubset(actual), diagnostic
        previous = actual

    override = risk_plan_for(
        ["tests/test_local_helper.py"],
        requested_risk="R2",
        requested_gates=("release.real_runtime",),
    )
    expected_override = cumulative_gate_ids("R2") | {"topology.verify", "release.real_runtime"}
    override_gate = next(gate for gate in override["gates"] if gate["id"] == "release.real_runtime")
    diagnostic = scenario_diagnostic(
        "explicit-risk-and-gate-override",
        "tests/test_local_helper.py",
        "R2",
        expected_override,
        override,
    )
    assert override["risk"]["class"] == "R2", diagnostic
    assert {gate["id"] for gate in override["gates"]} == expected_override, diagnostic
    assert override_gate["required"] is True, diagnostic
    assert override_gate["selectionReason"] == "explicit_task_gate", diagnostic
    assert override_gate["evidence"]["inferenceAllowed"] is False, diagnostic


def test_large_owner_union_is_retained_and_escalates_instead_of_truncating(tmp_path: Path) -> None:
    manifest, _ = load_manifest()
    expanded = deepcopy(manifest)
    synthetic_owner_ids = []
    for index in range(30):
        owner_id = f"direct.synthetic.{index:02d}"
        synthetic_owner_ids.append(owner_id)
        expanded["owners"][owner_id] = {
            "tier": "direct_owner",
            "kind": "owner_identifier",
            "identifier": owner_id,
        }
    expanded["rules"].append(
        {
            "id": "synthetic-large-owner-union",
            "include": ["src/large_union.py"],
            "owners": {"direct_owner": synthetic_owner_ids},
        }
    )

    plan = plan_for(["src/large_union.py"], manifest=expanded)
    selected_owner_ids = {owner["id"] for owner in plan["owners"]}

    assert set(synthetic_owner_ids).issubset(selected_owner_ids)
    assert plan["ownerListsTruncated"] is False
    assert any(escalation["tier"] == "direct_owner" for escalation in plan["escalations"])
    assert "bounded.repository.integration" in selected_owner_ids
    assert "complete.repository.validation" in selected_owner_ids

    changed_file = "src/services/watchlist_service.py"
    canonical_plan = risk_plan_for([changed_file])
    canonical_gate = next(gate for gate in canonical_plan["gates"] if gate["id"] == "backend.canonical")
    expected_gates = cumulative_gate_ids("R4")
    diagnostic = scenario_diagnostic(
        "canonical-backend-zero-retry",
        changed_file,
        "R4",
        expected_gates,
        canonical_plan,
    )
    assert canonical_gate["command"][-2:] == ["--retry-failures", "0"], diagnostic
    assert canonical_gate["retryCount"] == 0, diagnostic
    assert canonical_gate["structuredEvidence"] == "T630", diagnostic
    assert set(canonical_gate["domains"]) == set(topology.BACKEND_DOMAINS), diagnostic

    missing = tmp_path / "missing" / "result.json"
    assert_rejected("missing-t630-result", changed_file, canonical_plan, missing, "missing")

    malformed = tmp_path / "malformed" / "result.json"
    malformed.parent.mkdir(parents=True)
    malformed.write_text("{", encoding="utf-8")
    assert_rejected("malformed-t630-result", changed_file, canonical_plan, malformed, "malformed")

    incomplete = _write_aggregate(tmp_path / "incomplete", canonical_plan)
    incomplete_payload = json.loads(incomplete.read_text(encoding="utf-8"))
    incomplete_payload["firstAttempt"]["state"] = "incomplete"
    incomplete.write_text(json.dumps(incomplete_payload, sort_keys=True), encoding="utf-8")
    assert_rejected("incomplete-first-attempt", changed_file, canonical_plan, incomplete, "incomplete")

    for outcome in ("skipped", "cancelled", "missing", "unknown"):
        terminal = _write_aggregate(tmp_path / outcome, canonical_plan, outcome=outcome)
        assert_rejected(
            f"{outcome}-is-not-passed",
            changed_file,
            canonical_plan,
            terminal,
            outcome,
        )

    retry = _write_aggregate(tmp_path / "retry", canonical_plan, retry=True)
    assert_rejected("retry-is-not-first-attempt", changed_file, canonical_plan, retry, "retry")

    for scenario, identity_field, expected_message in (
        ("config-identity-mismatch", "configSha256", "config"),
        ("selection-identity-mismatch", "selectionSha256", "selection"),
    ):
        mismatched_plan = risk_plan_for([changed_file])
        result_path = _write_aggregate(tmp_path / scenario, mismatched_plan)
        mismatched_plan["identity"][identity_field] = "9" * 64
        assert_rejected(scenario, changed_file, mismatched_plan, result_path, expected_message)

    command_plan = risk_plan_for([changed_file])
    command_path = _write_aggregate(tmp_path / "command-identity", command_plan)
    command_payload = json.loads(command_path.read_text(encoding="utf-8"))
    mismatched_command = ["python", "-m", "pytest", "unexpected"]
    mismatched_command_identity = {
        "argv": mismatched_command,
        "sha256": topology.canonical_json_hash(mismatched_command),
    }
    attempt_path = command_path.parent / "attempt-0.json"
    attempt_payload = json.loads(attempt_path.read_text(encoding="utf-8"))
    attempt_payload["identity"]["command"] = mismatched_command_identity
    attempt_path.write_text(json.dumps(attempt_payload, sort_keys=True), encoding="utf-8")
    command_payload["identity"]["command"] = mismatched_command_identity
    command_payload["firstAttempt"]["identity"]["command"] = mismatched_command_identity
    command_payload["firstAttempt"]["sha256"] = planner.file_hash(attempt_path)
    command_path.write_text(json.dumps(command_payload, sort_keys=True), encoding="utf-8")
    assert_rejected("command-identity-mismatch", changed_file, command_plan, command_path, "command")

    def canonical_runner(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if "run-backend" in command:
            _write_aggregate(tmp_path / "canonical-success" / "backend.canonical", canonical_plan)
        return subprocess.CompletedProcess(command, 0, "", "")

    canonical_result = planner.execute_validation_plan(
        canonical_plan,
        output_dir=tmp_path / "canonical-success",
        root=ROOT,
        runner=canonical_runner,
        candidate_identity=candidate_identity(),
    )
    by_id = {gate["gateId"]: gate for gate in canonical_result["gates"]}
    diagnostic = scenario_diagnostic(
        "canonical-evidence-declared-gates-only",
        changed_file,
        "R4",
        expected_gates,
        canonical_plan,
        reason=canonical_result.get("reason", ""),
    )
    assert canonical_result["status"] == "passed", diagnostic
    assert by_id["backend.canonical"]["structuredEvidence"] == "passed", diagnostic
    for gate_id in ("owners.affected", "contracts.cross_owner", "protected.owners", "architecture.global"):
        assert by_id[gate_id]["status"] == "passed", diagnostic
        assert by_id[gate_id]["evidenceFrom"] == "backend.canonical", diagnostic
        assert by_id[gate_id]["coverage"] == "validated_structured_domain_superset", diagnostic


def test_unknown_path_has_explicit_fail_closed_escalation() -> None:
    path = "unknown-zone/new-validation-input.xyz"

    plan = plan_for([path])
    item = change_by_path(plan, path)

    assert item["matchedRules"] == []
    assert item["authoritySource"] == "explicit_unknown_escalation"
    assert item["escalationReasons"] == ["unknown_validation_relevant_path"]
    assert path in plan["unknownPaths"]
    assert {"protected_baseline_comparison", "milestone", "release"}.issubset(item["selectedTiers"])

    risk_plan = risk_plan_for([path])
    canonical = next(gate for gate in risk_plan["gates"] if gate["id"] == "backend.canonical")
    expected_gates = cumulative_gate_ids("R3") | {"backend.canonical"}
    diagnostic = scenario_diagnostic("unknown-change-fail-closed", path, "R3", expected_gates, risk_plan)
    assert risk_plan["risk"]["class"] == "R3", diagnostic
    assert risk_plan["risk"]["unknownPaths"] == [path], diagnostic
    assert canonical["required"] is True, diagnostic
    assert canonical["selectionReason"] == "unknown_change_fail_closed", diagnostic


@pytest.mark.parametrize(
    ("path", "rule_id"),
    [
        ("data_provider/base.py", "protected-provider"),
        ("src/services/watchlist_service.py", "protected-existing-gate-domain-baseline"),
        ("src/core/scanner_profile.py", "protected-scanner"),
        ("src/core/backtest_engine.py", "protected-backtest"),
        ("src/services/portfolio_service.py", "protected-portfolio"),
        ("src/auth.py", "protected-auth-security"),
        ("src/services/portfolio_ibkr_sync_service.py", "protected-broker-order"),
        ("bot/feishu.py", "protected-external-network"),
        ("validation/validation_owners.json", "protected-owner-manifest"),
    ],
)
def test_every_agents_protected_domain_escalates(path: str, rule_id: str) -> None:
    plan = plan_for([path])
    item = change_by_path(plan, path)

    assert rule_id in item["matchedRules"]
    assert path in plan["protectedPaths"]
    assert {"protected_baseline_comparison", "milestone", "release"}.issubset(item["selectedTiers"])

    risk_plan = risk_plan_for([path])
    expected_gates = cumulative_gate_ids("R4")
    diagnostic = scenario_diagnostic(
        f"protected-owner-{rule_id}", path, "R4", expected_gates, risk_plan
    )
    assert risk_plan["risk"]["class"] == "R4", diagnostic
    assert risk_plan["risk"]["protectedOwners"], diagnostic


@pytest.mark.parametrize(
    ("path", "rule_id"),
    [
        ("setup.cfg", "protected-root-config-lockfile"),
        ("apps/dsa-web/package-lock.json", "protected-root-config-lockfile"),
        ("api/v1/schemas/common.py", "protected-schema-contract"),
        (".github/workflows/ci.yml", "protected-workflow"),
        ("src/postgres_schema_bootstrap.py", "protected-database-migration"),
        ("apps/dsa-web/src/setupTests.ts", "protected-global-setup"),
    ],
)
def test_root_config_lock_schema_workflow_migration_and_global_setup_escalate(path: str, rule_id: str) -> None:
    plan = plan_for([path])
    item = change_by_path(plan, path)

    assert rule_id in item["matchedRules"]
    assert {"protected_baseline_comparison", "milestone", "release"}.issubset(item["selectedTiers"])


def test_related_test_inference_adds_but_does_not_replace_manifest_authority(tmp_path: Path) -> None:
    path = "src/providers/validation.py"

    plan = plan_for([path])
    item = change_by_path(plan, path)

    assert item["authoritySource"] == "manifest_rule"
    assert item["matchedRules"]
    assert item["inferredOwners"] == ["direct.pytest.related_inference"]
    assert "tests/test_provider_validation.py" in item["inferredOwnerTargets"]

    risk_plan = risk_plan_for([path])
    assert risk_plan["affectedOwners"] == sorted(owner["id"] for owner in plan["owners"])
    assert risk_plan["selection"]["affectedOwners"] == risk_plan["affectedOwners"]

    evidence_path = "scripts/check_ai_assets.py"
    evidence_plan = risk_plan_for([evidence_path], requested_risk="R3")
    owners_gate = next(gate for gate in evidence_plan["gates"] if gate["id"] == "owners.affected")
    contracts_gate = next(gate for gate in evidence_plan["gates"] if gate["id"] == "contracts.cross_owner")

    def runner(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if "run-backend" in command:
            _write_aggregate(tmp_path / "owners.affected", evidence_plan, gate_id="owners.affected")
        return subprocess.CompletedProcess(command, 0, "", "")

    result = planner.execute_validation_plan(
        evidence_plan,
        output_dir=tmp_path,
        root=ROOT,
        runner=runner,
        candidate_identity=candidate_identity(),
    )
    by_id = {gate["gateId"]: gate for gate in result["gates"]}
    expected_gates = cumulative_gate_ids("R3")
    diagnostic = scenario_diagnostic(
        "affected-owner-t630-cross-owner-coverage",
        evidence_path,
        "R3",
        expected_gates,
        evidence_plan,
        reason=result.get("reason", ""),
    )
    assert "backend.canonical" not in {gate["id"] for gate in evidence_plan["gates"]}, diagnostic
    assert owners_gate["structuredEvidence"] == "T630", diagnostic
    assert contracts_gate["satisfiedBy"] == "owners.affected", diagnostic
    assert result["status"] == "passed", diagnostic
    assert by_id["owners.affected"]["structuredEvidence"] == "passed", diagnostic
    assert by_id["contracts.cross_owner"]["coverage"] == "validated_structured_domain_superset", diagnostic


def test_deterministic_ordering_and_stable_output_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resume_current = {
        "tier": "canonical",
        "riskPlanHash": "1" * 64,
        "stagePlanHash": "2" * 64,
        "shardPlanHash": "3" * 64,
        "candidate": candidate_identity(),
        "topology": {"count": 2, "sha256": "4" * 64},
        "shards": [
            {
                "id": "serialized-backend",
                "selection": {"count": 1, "sha256": "5" * 64},
                "stageIds": ["backend.canonical"],
            },
            {
                "id": "isolated-portfolio",
                "selection": {"count": 1, "sha256": "6" * 64},
                "stageIds": ["backend.canonical"],
            },
        ],
    }
    first_resume = resume.build_resume_plan(resume_current, prior=None)
    second_resume = resume.build_resume_plan(resume_current, prior=None)
    assert first_resume == second_resume
    assert first_resume["reusableShards"] == []
    assert first_resume["remainingShards"] == ["isolated-portfolio", "serialized-backend"]
    assert first_resume["planHash"] == resume.canonical_hash(
        {key: value for key, value in first_resume.items() if key != "planHash"}
    )

    canonical_source = resume.build_resume_source(resume_current)
    matching_resume = resume.build_resume_plan(resume_current, canonical_source)
    assert matching_resume["candidateShards"] == ["isolated-portfolio", "serialized-backend"]
    assert matching_resume["reusableShards"] == []
    assert matching_resume["remainingShards"] == ["isolated-portfolio", "serialized-backend"]

    mismatch_cases = {
        "candidate": {**candidate_identity(), "commitSha": "9" * 40},
        "topology": {"count": 2, "sha256": "9" * 64},
        "riskPlanHash": "9" * 64,
        "stagePlanHash": "9" * 64,
        "shardPlanHash": "9" * 64,
    }
    for field, value in mismatch_cases.items():
        mismatched = deepcopy(resume_current)
        mismatched[field] = value
        rejected = resume.build_resume_plan(mismatched, canonical_source)
        assert rejected["reusableShards"] == []
        assert rejected["remainingShards"] == ["isolated-portfolio", "serialized-backend"]
        assert rejected["rejectionReasons"] == [f"identity mismatch: {field}"]

    malformed = deepcopy(canonical_source)
    malformed["sourceHash"] = "0" * 64
    malformed_resume = resume.build_resume_plan(resume_current, malformed)
    assert malformed_resume["reusableShards"] == []
    assert malformed_resume["rejectionReasons"] == ["resume evidence hash mismatch"]

    duplicate = deepcopy(canonical_source)
    duplicate["shards"].append(deepcopy(duplicate["shards"][0]))
    duplicate["sourceHash"] = resume.canonical_hash({key: value for key, value in duplicate.items() if key != "sourceHash"})
    duplicate_resume = resume.build_resume_plan(resume_current, duplicate)
    assert duplicate_resume["reusableShards"] == []
    assert duplicate_resume["rejectionReasons"] == ["resume evidence contains duplicate shard records"]

    contradictory = deepcopy(canonical_source)
    contradictory["shards"][0]["stageIds"] = ["backend.release-only"]
    contradictory["sourceHash"] = resume.canonical_hash(
        {key: value for key, value in contradictory.items() if key != "sourceHash"}
    )
    contradictory_resume = resume.build_resume_plan(resume_current, contradictory)
    assert contradictory_resume["reusableShards"] == []
    assert contradictory_resume["rejectionReasons"] == [
        "resume evidence shard identity mismatch: serialized-backend"
    ]

    release_current = deepcopy(resume_current)
    release_current.update(
        {
            "tier": "release",
            "riskPlanHash": "7" * 64,
            "stagePlanHash": "8" * 64,
            "shardPlanHash": "9" * 64,
        }
    )
    release_current["shards"][0]["stageIds"] = ["backend.canonical", "backend.release-only"]
    release_source = resume.build_resume_source(release_current)
    release_resume = resume.build_resume_plan(release_current, release_source)
    assert release_resume["candidateShards"] == ["isolated-portfolio", "serialized-backend"]
    assert release_resume["reusableShards"] == []
    assert release_current["shards"][1]["stageIds"] == ["backend.canonical"]
    canonical_to_release = resume.build_resume_plan(release_current, canonical_source)
    assert canonical_to_release["reusableShards"] == []
    assert "identity mismatch: tier" in canonical_to_release["rejectionReasons"]

    for status in ("failed", "error", "cancelled", "incomplete", "missing", "unknown", "skipped"):
        with pytest.raises(resume.ResumeError, match="successful|incomplete"):
            resume.successful_terminal_result(
                {"state": "completed" if status != "incomplete" else "incomplete", "status": status, "exitCode": 1}
            )
    with pytest.raises(resume.ResumeError, match="first attempt"):
        resume.successful_terminal_result(
            {"state": "completed", "status": "passed", "exitCode": 0, "attempt": {"index": 1, "kind": "retry"}}
        )

    artifact_context = {
        **resume_current,
        "_shardPlan": {"shards": deepcopy(resume_current["shards"])},
    }
    artifact_source = resume.build_resume_source(artifact_context)
    artifact_path = tmp_path / "resume-source.json"
    artifact_path.write_bytes(resume.canonical_bytes(artifact_source) + b"\n")
    for shard in artifact_source["shards"]:
        directory = artifact_path.parent / shard["directory"]
        directory.mkdir(parents=True)
        (directory / "attempt-0.json").write_text("{}\n", encoding="utf-8")
    structured_identity = {
        "candidate": candidate_identity(),
        "environment": {"fingerprint": "7" * 64},
        "dependencyLock": {
            "contentHash": "8" * 64,
            "selectedLock": "requirements-python311-dev.lock",
            "selectedProjection": "darwin-arm64-cpython311-development",
            "selectedProjectionHash": "9" * 64,
        },
        "command": {"argv": ["$PYTHON", "-m", "pytest"], "sha256": "a" * 64},
        "selection": {"count": 1, "sha256": "b" * 64},
        "topology": {"count": 2, "sha256": "4" * 64},
    }
    attempts = {
        shard["id"]: {
            "state": "completed",
            "status": "passed",
            "exitCode": 0,
            "attempt": {"index": 0, "kind": "first"},
            "identity": structured_identity,
        }
        for shard in artifact_source["shards"]
    }

    def load_attempt(_: Path, *, shard: dict, **__: object) -> tuple[dict, dict]:
        outcome = attempts[shard["id"]]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome, {}

    from tests import conftest as shard_authority

    monkeypatch.setattr(shard_authority, "_load_backend_shard_attempt", load_attempt)
    monkeypatch.setattr(resume, "_current_result_identity", lambda *_: structured_identity)

    fully_reused, _ = resume.plan_from_evidence(artifact_context, artifact_path)
    assert fully_reused["reusableShards"] == ["isolated-portfolio", "serialized-backend"]
    assert fully_reused["remainingShards"] == []
    assert len(fully_reused["acceptedPriorResultIdentities"]) == 2

    attempts["isolated-portfolio"] = {
        **attempts["isolated-portfolio"],
        "state": "incomplete",
        "status": "incomplete",
        "exitCode": 2,
    }
    interrupted, _ = resume.plan_from_evidence(artifact_context, artifact_path)
    assert interrupted["reusableShards"] == ["serialized-backend"]
    assert interrupted["remainingShards"] == ["isolated-portfolio"]
    assert interrupted["rejectionReasons"] == ["isolated-portfolio: structured result is incomplete"]

    attempts["isolated-portfolio"] = {
        **attempts["isolated-portfolio"],
        "state": "completed",
        "status": "failed",
        "exitCode": 1,
    }
    failed, _ = resume.plan_from_evidence(artifact_context, artifact_path)
    assert failed["reusableShards"] == ["serialized-backend"]
    assert failed["remainingShards"] == ["isolated-portfolio"]
    assert failed["rejectionReasons"] == ["isolated-portfolio: terminal outcome is not successful: failed"]

    attempts["isolated-portfolio"] = ValueError("missing or malformed structured result")
    malformed_result, _ = resume.plan_from_evidence(artifact_context, artifact_path)
    assert malformed_result["reusableShards"] == ["serialized-backend"]
    assert malformed_result["remainingShards"] == ["isolated-portfolio"]
    assert malformed_result["rejectionReasons"] == [
        "isolated-portfolio: missing or malformed structured result"
    ]

    attempts["isolated-portfolio"] = {
        "state": "completed",
        "status": "passed",
        "exitCode": 0,
        "attempt": {"index": 0, "kind": "first"},
        "identity": {**structured_identity, "command": {"argv": ["unexpected"], "sha256": "c" * 64}},
    }
    command_mismatch, _ = resume.plan_from_evidence(artifact_context, artifact_path)
    assert command_mismatch["reusableShards"] == ["serialized-backend"]
    assert command_mismatch["remainingShards"] == ["isolated-portfolio"]
    assert command_mismatch["rejectionReasons"] == [
        "isolated-portfolio: environment, dependency-lock, or command identity mismatch"
    ]

    manifest, manifest_hash = load_manifest()
    changes = [changed("docs/README.md"), changed("src/providers/validation.py")]
    kwargs = {
        "root": ROOT,
        "base_ref": "base",
        "base_sha": DUMMY_SHA,
        "candidate_ref": "candidate",
        "candidate_sha": "2" * 40,
        "change_source": "committed",
        "manifest_hash": manifest_hash,
    }

    first = planner.build_shadow_plan_from_changes(changes, manifest, **kwargs)
    second = planner.build_shadow_plan_from_changes(list(reversed(changes)), manifest, **kwargs)

    assert first == second
    assert first["changedPaths"] == sorted(first["changedPaths"])
    assert first["planHash"] == planner.stable_hash(
        {key: value for key, value in first.items() if key != "planHash"}
    )

    risk_cases = (
        ("r0-docs", "docs/audit-note.md", "R0", set()),
        ("r1-backend-test", "tests/test_local_helper.py", "R1", {"topology.verify"}),
        ("r2-frontend-owner", "apps/dsa-web/src/pages/MarketPage.tsx", "R2", set()),
        (
            "r3-shared-frontend-owner",
            "apps/dsa-web/src/components/SharedWidget.tsx",
            "R3",
            {"browser.protected"},
        ),
        ("r4-protected-owner", "src/services/watchlist_service.py", "R4", set()),
    )
    for scenario, changed_file, expected_tier, extra_gates in risk_cases:
        expected_gates = cumulative_gate_ids(expected_tier) | extra_gates
        first_risk = risk_plan_for([changed_file])
        second_risk = risk_plan_for([changed_file])
        diagnostic = scenario_diagnostic(
            scenario, changed_file, expected_tier, expected_gates, second_risk
        )
        assert first_risk == second_risk, diagnostic
        assert second_risk["risk"]["class"] == expected_tier, diagnostic
        assert {gate["id"] for gate in second_risk["gates"]} == expected_gates, diagnostic
        assert second_risk["authority"] == "risk-selection", diagnostic
        assert second_risk["planHash"] == planner.stable_hash(
            {key: value for key, value in second_risk.items() if key != "planHash"}
        ), diagnostic

    failure_plan = risk_plan_for(["docs/audit-note.md"])
    calls: list[list[str]] = []

    def failing_runner(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 7, "", "selected failure")

    failure_result = planner.execute_validation_plan(
        failure_plan,
        output_dir=tmp_path / "selected-failure",
        root=ROOT,
        runner=failing_runner,
        candidate_identity=candidate_identity(),
    )
    diagnostic = scenario_diagnostic(
        "selected-command-failure-propagates",
        "docs/audit-note.md",
        "R0",
        cumulative_gate_ids("R0"),
        failure_plan,
        reason="selected failure",
    )
    assert failure_result["status"] == "failed" and failure_result["exitCode"] == 7, diagnostic
    assert calls == [["git", "diff", "--check"]], diagnostic
    assert failure_result["gates"][0]["retries"] == [], diagnostic


def test_t437_t438_locale_corpus_adds_bounded_and_browser_owners_to_current_classification(tmp_path: Path) -> None:
    from tests import conftest as shard_authority

    locale_paths = [
        "apps/dsa-web/e2e/locale-route-switch.spec.ts",
        "apps/dsa-web/src/App.tsx",
        "apps/dsa-web/src/__tests__/AppLocaleRouting.test.tsx",
        "apps/dsa-web/src/contexts/UiLanguageContext.tsx",
        "apps/dsa-web/src/contexts/__tests__/UiLanguageContext.test.tsx",
        "apps/dsa-web/src/i18n/__tests__/bootstrap.test.ts",
        "apps/dsa-web/src/i18n/catalogs/en.ts",
        "apps/dsa-web/src/i18n/catalogs/zh.ts",
        "apps/dsa-web/src/i18n/core.ts",
        "apps/dsa-web/src/main.tsx",
    ]

    current = planner.classify(locale_paths, root=ROOT)
    shadow = plan_for(locale_paths)
    owner_ids = {owner["id"] for owner in shadow["owners"]}

    assert current["tier"] == "frontend-component"
    assert current["hasProtectedDomain"] is False
    assert "bounded.web.locale" in owner_ids
    assert "browser.locale.route" in owner_ids
    assert "browser.changed.specs" in owner_ids
    assert shadow["unknownPaths"] == []
    assert shadow["ownerListsTruncated"] is False

    changed_file = "apps/dsa-web/src/pages/MarketPage.tsx"
    release_plan = risk_plan_for([changed_file], frozen_release=True)
    gates = {gate["id"]: gate for gate in release_plan["gates"]}
    expected_gates = cumulative_gate_ids("R5") | {"browser.protected"}
    diagnostic = scenario_diagnostic(
        "r5-frozen-release-explicit-browser-uat-runtime",
        changed_file,
        "R5",
        expected_gates,
        release_plan,
    )
    assert release_plan["risk"]["class"] == "R5", diagnostic
    assert set(gates) == expected_gates, diagnostic
    for gate_id in ("browser.protected", "browser.full", "uat.runtime", "release.real_runtime"):
        assert gates[gate_id]["required"] is True, diagnostic
        assert gates[gate_id]["command"], diagnostic
        assert gates[gate_id]["evidence"]["inferenceAllowed"] is False, diagnostic
    assert "--project=release-real-runtime" not in gates["browser.protected"]["command"], diagnostic
    assert "--project=release-real-runtime" not in gates["browser.full"]["command"], diagnostic
    assert "--project=release-real-runtime" in gates["release.real_runtime"]["command"], diagnostic
    risk_plan = risk_plan_for(
        ["docs/audit-note.md"],
        requested_risk="R3",
        accepted_integration=True,
    )
    risk_path = tmp_path / "t638-risk-plan.json"
    risk_path.write_bytes(planner.canonical_json_bytes(risk_plan) + b"\n")
    raw_shard_plan = shard_authority.build_backend_shard_plan(risk_path, scope="full")
    projected_shard_plan = planner.project_backend_shard_plan(risk_plan, raw_shard_plan, tier="canonical")
    t638_context = resume.build_resume_context(
        risk_plan,
        planner.build_backend_stage_plan(risk_plan, tier="canonical"),
        projected_shard_plan,
    )
    t638_source = resume.build_resume_source(t638_context)
    assert t638_context["tier"] == "canonical"
    assert t638_context["topology"] == topology.load_manifest(TOPOLOGY_PATH)["backend"]["currentInventory"]
    assert t638_context["shards"] == [
        {
            "id": item["id"],
            "selection": item["selection"],
            "stageIds": ["backend.canonical"],
        }
        for item in sorted(projected_shard_plan["shards"], key=lambda item: item["id"])
    ]
    assert all(not Path(item["directory"]).is_absolute() for item in t638_source["shards"])
    assert t638_source["sourceHash"] == resume.canonical_hash(
        {key: value for key, value in t638_source.items() if key != "sourceHash"}
    )

    canonical = planner.build_backend_stage_plan(risk_plan, tier="canonical")
    canonical_again = planner.build_backend_stage_plan(risk_plan, tier="canonical")
    release = planner.build_backend_stage_plan(risk_plan, tier="release")

    assert canonical == canonical_again
    assert canonical["schemaVersion"] == "wolfystock.backend-validation-stages.v1"
    assert canonical["planHash"] == planner.stable_hash(
        {key: value for key, value in canonical.items() if key != "planHash"}
    )
    assert canonical["releaseReady"] is False
    assert release["releaseReady"] is False

    canonical_stage, release_stage = canonical["stages"]
    assert canonical_stage["id"] == "backend.canonical"
    assert canonical_stage["tierOwnership"] == "canonical"
    assert canonical_stage["required"] is True
    assert release_stage["id"] == "backend.release-only"
    assert release_stage["tierOwnership"] == "release"
    assert release_stage["required"] is False
    assert len(release_stage["nodeIds"]) == 18
    audit = json.loads(
        (ROOT / "validation" / "t569_test_redundancy_performance_audit.json").read_text(encoding="utf-8")
    )
    task = next(item for item in audit["roadmap"] if item["taskId"] == "T637")
    assert release_stage["nodeIds"] == sorted(task["candidateNodeIds"])
    assert "canonical changed-file and branch secret gates remain mandatory" in release_stage["purpose"]

    canonical_ids = set(canonical_stage["nodeIds"])
    release_only_ids = set(release_stage["nodeIds"])
    release_ids = set(release["execution"]["nodeIds"])
    assert canonical_ids.isdisjoint(release_only_ids)
    assert canonical_ids | release_only_ids == release_ids
    assert len(canonical_ids) == 7_914
    assert len(release_ids) == 7_932
    assert set(canonical["execution"]["nodeIds"]) < release_ids
    assert release["stages"][1]["required"] is True
    assert release["releaseQualificationRequired"] is True
    scenarios = (
        ("release-tool", ["scripts/release_secret_scan.sh"], {}),
        ("validation-authority", ["scripts/validation_changed_files.py"], {}),
        ("unknown", ["unknown-zone/new-validation-input.xyz"], {}),
        ("protected-runtime", ["src/runtime/settings.py"], {}),
        ("user-facing", ["docs/audit-note.md"], {"user_facing": True, "requested_risk": "R3"}),
    )
    for scenario, paths, kwargs in scenarios:
        risk_plan = risk_plan_for(paths, accepted_integration=True, **kwargs)
        stage_plan = planner.build_backend_stage_plan(risk_plan, tier="canonical")
        release_stage = next(stage for stage in stage_plan["stages"] if stage["id"] == "backend.release-only")
        assert release_stage["required"] is True, scenario
        assert stage_plan["execution"] == stage_plan["releaseInventory"], scenario
        assert stage_plan["releaseReady"] is False, scenario
    risk_plan = risk_plan_for(
        ["docs/audit-note.md"],
        requested_risk="R3",
        accepted_integration=True,
    )
    with pytest.raises(planner.SelectionError, match="unknown backend validation tier"):
        planner.build_backend_stage_plan(risk_plan, tier="preview")

    malformed = planner.build_backend_stage_plan(risk_plan, tier="canonical")
    malformed["execution"]["count"] += 1
    with pytest.raises(planner.SelectionError, match="stage plan"):
        planner.validate_backend_stage_plan(malformed)
