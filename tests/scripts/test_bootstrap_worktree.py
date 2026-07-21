from __future__ import annotations

import dataclasses
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.environment.errors import EnvironmentFailure
from scripts.environment.manager import require_managed_python


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "bootstrap_worktree.sh"
CORE_PATH = REPO_ROOT / "scripts" / "worktree_preflight.py"
POWERSHELL_PATH = REPO_ROOT / "scripts" / "bootstrap_worktree.ps1"
FINGERPRINT = "e" * 64


def _load_preflight():
    spec = importlib.util.spec_from_file_location("worktree_preflight_delegate", CORE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_task_promotion():
    spec = importlib.util.spec_from_file_location("task_promotion_under_test", REPO_ROOT / "scripts" / "task_promotion.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _promotion_fixture(module, root: Path):
    canonical = root / "canonical"
    worktree_root = root / "worktrees"
    remote = root / "remote.git"
    canonical.mkdir(parents=True)
    worktree_root.mkdir()
    _git(canonical, "init", "-q", "--initial-branch=main")
    _git(canonical, "config", "user.name", "Fixture")
    _git(canonical, "config", "user.email", "fixture@example.test")
    (canonical / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(canonical, "add", "tracked.txt")
    _git(canonical, "commit", "-qm", "base")
    accepted_base = _git(canonical, "rev-parse", "HEAD")
    _git(root, "clone", "-q", "--bare", str(canonical), str(remote))
    _git(canonical, "remote", "add", "origin", str(remote))
    worktree = worktree_root / "topic"
    _git(canonical, "worktree", "add", "-qb", "topic", str(worktree), accepted_base)
    (worktree / "tracked.txt").write_text("candidate\n", encoding="utf-8")
    _git(worktree, "commit", "-qam", "candidate subject")
    candidate = _git(worktree, "rev-parse", "HEAD")
    evidence_path = worktree / "evidence.json"
    common_dir = Path(_git(worktree, "rev-parse", "--git-common-dir"))
    if not common_dir.is_absolute():
        common_dir = (worktree / common_dir).resolve()
    (common_dir / "info" / "exclude").write_text("evidence.json\n", encoding="utf-8")
    evidence_path.write_text("{}\n", encoding="utf-8")
    changed_files = ["tracked.txt"]
    evidence = module.VerifiedEvidence(
        evidence_path=evidence_path,
        evidence_sha256="1" * 64,
        accepted_base=accepted_base,
        candidate=candidate,
        tree=_git(worktree, "rev-parse", "HEAD^{tree}"),
        working_tree_sha256=module.validation_planner._candidate_identity(worktree, candidate)[
            "workingTreeSha256"
        ],
        parent=accepted_base,
        subject="candidate subject",
        branch="topic",
        patch_sha256=module.git_patch_hash(worktree, accepted_base, candidate),
        changed_files=changed_files,
        changed_files_sha256=module.canonical_hash(changed_files),
        remote="origin",
        remote_url=str(remote),
        target_ref="refs/heads/main",
        environment_fingerprint=FINGERPRINT,
        dependency_lock={
            "contentHash": "2" * 64,
            "selectedLock": "fixture.lock",
            "selectedProjection": "fixture-projection",
            "selectedProjectionHash": "3" * 64,
        },
        risk_class="R4",
        tier="canonical",
        release_ready=False,
        identities={
            "riskPlan": "4" * 64,
            "stagePlan": "5" * 64,
            "shardPlan": "6" * 64,
            "resumePlan": "7" * 64,
            "selection": "8" * 64,
            "topology": "9" * 64,
            "command": "a" * 64,
            "shardResult": "b" * 64,
        },
    )
    loader = lambda _worktree, _path: evidence
    authority = module.PromotionAuthority(
        evidence_loader=loader,
        environment_verify=lambda _path: FINGERPRINT,
    )
    return canonical, worktree_root, worktree, remote, evidence_path, evidence, authority


def _assert_task_promotion_contract(module, tmp_path: Path) -> None:
    canonical, worktree_root, worktree, remote, evidence_path, evidence, authority = _promotion_fixture(
        module, tmp_path / "success"
    )
    refs_before = _git(canonical, "for-each-ref", "--format=%(refname) %(objectname)")
    canonical_status_before = _git(canonical, "status", "--porcelain", "--untracked-files=all")
    worktree_status_before = _git(worktree, "status", "--porcelain", "--untracked-files=all")
    first = authority.plan(worktree, Path("evidence.json"))
    second = authority.plan(worktree, Path("evidence.json"))
    assert first.exit_code == 0
    assert module.canonical_bytes(first.payload) == module.canonical_bytes(second.payload)
    assert first.payload["schemaVersion"] == "wolfystock.task-promotion.v1"
    assert first.payload["planResult"]["status"] == "passed"
    assert first.payload["promotionResult"]["status"] == "not_evaluated"
    assert first.payload["resultHash"] == module.canonical_hash(
        {key: value for key, value in first.payload.items() if key != "resultHash"}
    )
    assert _git(canonical, "rev-parse", "main") == evidence.accepted_base
    assert _git(remote, "rev-parse", "refs/heads/main") == evidence.accepted_base
    assert _git(canonical, "for-each-ref", "--format=%(refname) %(objectname)") == refs_before
    assert _git(canonical, "status", "--porcelain", "--untracked-files=all") == canonical_status_before
    assert _git(worktree, "status", "--porcelain", "--untracked-files=all") == worktree_status_before
    assert module._human(first).startswith("PLAN PASSED:")

    landed = authority.land(worktree, Path("evidence.json"))
    assert landed.exit_code == 0
    assert landed.payload["promotionResult"]["status"] == "succeeded"
    assert landed.payload["localMainUpdate"]["status"] == "succeeded"
    assert landed.payload["cleanupResult"]["status"] == "succeeded"
    cleanup_identity = landed.payload["cleanupResult"]["authority"]
    assert cleanup_identity["states"]["validation"] == "passed"
    assert cleanup_identity["states"]["land"] == "succeeded"
    assert cleanup_identity["identity"]["candidate"]["commitSha"] == evidence.candidate
    assert cleanup_identity["identity"]["environment"]["requiredFingerprint"] == FINGERPRINT
    assert module._human(landed).startswith("LAND SUCCEEDED:")
    assert _git(canonical, "rev-parse", "main") == evidence.candidate
    assert _git(remote, "rev-parse", "refs/heads/main") == evidence.candidate
    assert not worktree.exists()
    assert _git(canonical, "branch", "--list", "topic") == ""
    repeated = authority.land(worktree, Path("evidence.json"))
    assert repeated.exit_code == 1
    assert repeated.payload["refusalCode"] == "task_worktree_unavailable"

    source = (REPO_ROOT / "scripts" / "task_promotion.py").read_text(encoding="utf-8")
    for forbidden in (
        "--force",
        "rebase",
        "cherry-pick",
        "reset --hard",
        "git stash",
        "shell=True",
        "newest",
        "time.time",
    ):
        assert forbidden not in source

    _, _, race_worktree, race_remote, _, race_evidence, race_authority = _promotion_fixture(
        module, tmp_path / "race"
    )
    race_clone = tmp_path / "race-writer"
    _git(tmp_path, "clone", "-q", str(race_remote), str(race_clone))
    _git(race_clone, "config", "user.name", "Fixture")
    _git(race_clone, "config", "user.email", "fixture@example.test")
    (race_clone / "race.txt").write_text("moved\n", encoding="utf-8")
    _git(race_clone, "add", "race.txt")
    _git(race_clone, "commit", "-qm", "remote movement")

    def move_remote() -> None:
        _git(race_clone, "push", "-q", "origin", "main")

    race_authority.before_push = move_remote
    raced = race_authority.land(race_worktree, Path("evidence.json"))
    assert raced.exit_code == 1
    assert raced.payload["refusalCode"] == "remote_moved_before_push"
    assert raced.payload["promotionResult"]["status"] == "refused"
    assert raced.payload["cleanupResult"]["status"] == "not_requested"
    assert race_worktree.exists()
    assert _git(race_remote, "rev-parse", "refs/heads/main") != race_evidence.candidate

    non_ff_canonical, _, non_ff_worktree, non_ff_remote, _, non_ff_evidence, non_ff_authority = _promotion_fixture(
        module, tmp_path / "non-fast-forward"
    )
    (non_ff_canonical / "competing.txt").write_text("competing\n", encoding="utf-8")
    _git(non_ff_canonical, "add", "competing.txt")
    _git(non_ff_canonical, "commit", "-qm", "competing main")
    _git(non_ff_canonical, "push", "-q", "origin", "main")
    non_ff = non_ff_authority.plan(non_ff_worktree, Path("evidence.json"))
    assert non_ff.payload["refusalCode"] == "candidate_not_fast_forward"
    assert _git(non_ff_remote, "rev-parse", "refs/heads/main") != non_ff_evidence.candidate

    for name, mutate, reason in (
        ("dirty-task", lambda c, w: (w / "untracked.txt").write_text("dirty\n", encoding="utf-8"), "task_worktree_dirty"),
        ("dirty-main", lambda c, w: (c / "untracked.txt").write_text("dirty\n", encoding="utf-8"), "canonical_main_dirty"),
        ("detached", lambda c, w: _git(w, "checkout", "-q", "--detach"), "task_worktree_detached"),
    ):
        case_canonical, _, case_worktree, case_remote, _, case_evidence, case_authority = _promotion_fixture(
            module, tmp_path / name
        )
        mutate(case_canonical, case_worktree)
        refused = case_authority.land(case_worktree, Path("evidence.json"))
        assert refused.exit_code == 1
        assert refused.payload["refusalCode"] == reason
        assert refused.payload["promotionResult"]["status"] == "not_attempted"
        assert _git(case_remote, "rev-parse", "refs/heads/main") == case_evidence.accepted_base

    for field, replacement, reason in (
        ("candidate", "c" * 40, "candidate_mismatch"),
        ("tree", "d" * 40, "tree_mismatch"),
        ("parent", "e" * 40, "parent_mismatch"),
        ("branch", "other", "branch_mismatch"),
        ("subject", "other subject", "subject_mismatch"),
        ("patch_sha256", "f" * 64, "patch_mismatch"),
        ("changed_files", ["other.txt"], "changed_files_mismatch"),
        ("environment_fingerprint", "0" * 64, "environment_mismatch"),
    ):
        case_canonical, _, case_worktree, case_remote, _, case_evidence, _ = _promotion_fixture(
            module, tmp_path / f"mismatch-{field}"
        )
        bad = dataclasses.replace(case_evidence, **{field: replacement})
        case_authority = module.PromotionAuthority(
            evidence_loader=lambda _worktree, _path, value=bad: value,
            environment_verify=lambda _path: FINGERPRINT,
        )
        refused = case_authority.land(case_worktree, Path("evidence.json"))
        assert refused.payload["refusalCode"] == reason
        assert _git(case_remote, "rev-parse", "refs/heads/main") == case_evidence.accepted_base
        assert _git(case_canonical, "rev-parse", "main") == case_evidence.accepted_base

    lock_canonical, _, lock_worktree, lock_remote, _, lock_evidence, _ = _promotion_fixture(
        module, tmp_path / "dependency-lock"
    )
    lock_authority = module.PromotionAuthority(
        evidence_loader=lambda _worktree, _path: lock_evidence,
        environment_verify=lambda _path: module.EnvironmentIdentity(FINGERPRINT, {"contentHash": "0" * 64}),
    )
    lock_refusal = lock_authority.land(lock_worktree, Path("evidence.json"))
    assert lock_refusal.payload["refusalCode"] == "dependency_lock_mismatch"
    assert _git(lock_remote, "rev-parse", "refs/heads/main") == lock_evidence.accepted_base
    assert _git(lock_canonical, "rev-parse", "main") == lock_evidence.accepted_base

    reject_canonical, _, reject_worktree, reject_remote, _, reject_evidence, reject_authority = _promotion_fixture(
        module, tmp_path / "push-rejected"
    )
    hook = reject_remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    rejected = reject_authority.land(reject_worktree, Path("evidence.json"))
    assert rejected.payload["refusalCode"] == "push_rejected"
    assert rejected.payload["cleanupResult"]["status"] == "not_requested"
    assert _git(reject_remote, "rev-parse", "refs/heads/main") == reject_evidence.accepted_base
    assert _git(reject_canonical, "rev-parse", "main") == reject_evidence.accepted_base

    verify_canonical, _, verify_worktree, verify_remote, _, verify_evidence, verify_authority = _promotion_fixture(
        module, tmp_path / "post-push-verification"
    )
    unavailable_remote = tmp_path / "post-push-remote-unavailable.git"
    verify_authority.after_push = lambda: verify_remote.rename(unavailable_remote)
    verification_failure = verify_authority.land(verify_worktree, Path("evidence.json"))
    assert verification_failure.payload["promotionResult"]["status"] == "push_succeeded_verification_incomplete"
    assert verification_failure.payload["refusalCode"] == "remote_identity_unavailable"
    assert verification_failure.payload["localMainUpdate"]["status"] == "not_requested"
    assert verification_failure.payload["cleanupResult"]["status"] == "not_requested"
    assert module._human(verification_failure).startswith("LAND push succeeded, verification incomplete:")
    assert _git(unavailable_remote, "rev-parse", "refs/heads/main") == verify_evidence.candidate
    assert _git(verify_canonical, "rev-parse", "main") == verify_evidence.accepted_base

    during_canonical, _, during_worktree, during_remote, _, during_evidence, during_authority = _promotion_fixture(
        module, tmp_path / "remote-moved-during"
    )
    writer = tmp_path / "during-writer"
    _git(tmp_path, "clone", "-q", str(during_remote), str(writer))
    _git(writer, "config", "user.name", "Fixture")
    _git(writer, "config", "user.email", "fixture@example.test")
    (writer / "moved.txt").write_text("moved\n", encoding="utf-8")
    _git(writer, "add", "moved.txt")
    _git(writer, "commit", "-qm", "move during push")
    moved_sha = _git(writer, "rev-parse", "HEAD")
    _git(writer, "push", "-q", "origin", f"{moved_sha}:refs/heads/race-source")
    common = Path(_git(during_worktree, "rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = (during_worktree / common).resolve()
    pre_push = common / "hooks" / "pre-push"
    pre_push.write_text(
        "#!/bin/sh\n"
        f"git --git-dir='{during_remote}' update-ref refs/heads/main {moved_sha}\n",
        encoding="utf-8",
    )
    pre_push.chmod(0o755)
    moved_during = during_authority.land(during_worktree, Path("evidence.json"))
    assert moved_during.payload["refusalCode"] == "remote_moved_during_promotion"
    assert moved_during.payload["cleanupResult"]["status"] == "not_requested"
    assert _git(during_remote, "rev-parse", "refs/heads/main") == moved_sha
    assert _git(during_canonical, "rev-parse", "main") == during_evidence.accepted_base
    assert _git(during_worktree, "rev-parse", "HEAD") == during_evidence.candidate

    local_canonical, _, local_worktree, local_remote, _, local_evidence, local_authority = _promotion_fixture(
        module, tmp_path / "local-failure"
    )

    def block_local_index() -> None:
        git_dir = Path(_git(local_canonical, "rev-parse", "--git-dir"))
        if not git_dir.is_absolute():
            git_dir = local_canonical / git_dir
        (git_dir / "index.lock").write_text("blocked\n", encoding="utf-8")

    local_authority.before_push = block_local_index
    local_failure = local_authority.land(local_worktree, Path("evidence.json"))
    assert local_failure.payload["promotionResult"]["status"] == "succeeded"
    assert local_failure.payload["localMainUpdate"]["status"] == "failed"
    assert local_failure.payload["cleanupResult"]["status"] == "not_requested"
    assert _git(local_remote, "rev-parse", "refs/heads/main") == local_evidence.candidate
    assert _git(local_canonical, "rev-parse", "main") == local_evidence.accepted_base
    assert local_worktree.exists()

    cleanup_canonical, _, cleanup_worktree, cleanup_remote, _, cleanup_evidence, _ = _promotion_fixture(
        module, tmp_path / "cleanup-refusal"
    )

    class RefusingLifecycle:
        def __init__(self, **_kwargs):
            pass

        def cleanup(self, _request):
            return module.LifecycleResult(
                {
                    "schemaVersion": "wolfystock.worktree-lifecycle.v1",
                    "outcome": "refused",
                    "reasonCode": "fixture_refusal",
                },
                1,
            )

    cleanup_authority = module.PromotionAuthority(
        evidence_loader=lambda _worktree, _path: cleanup_evidence,
        environment_verify=lambda _path: FINGERPRINT,
        lifecycle_factory=RefusingLifecycle,
    )
    cleanup_failure = cleanup_authority.land(cleanup_worktree, Path("evidence.json"))
    assert cleanup_failure.payload["promotionResult"]["status"] == "succeeded"
    assert cleanup_failure.payload["cleanupResult"]["status"] == "refused"
    assert cleanup_failure.payload["detail"] == "LAND succeeded, cleanup incomplete"
    assert _git(cleanup_remote, "rev-parse", "refs/heads/main") == cleanup_evidence.candidate
    assert _git(cleanup_canonical, "rev-parse", "main") == cleanup_evidence.candidate
    assert cleanup_worktree.exists()


def _write_json_artifact(module, path: Path, value: dict) -> dict[str, str]:
    path.write_bytes(module.canonical_bytes(value) + b"\n")
    return {"path": path.name, "sha256": module._file_hash(path)}


def _assert_task_promotion_evidence_parser(module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "promotion-evidence"
    suite = root / "suite"
    root.mkdir()
    suite.mkdir()
    candidate_identity = {
        "commitSha": "1" * 40,
        "treeSha": "2" * 40,
        "workingTreeSha256": "3" * 64,
        "dirty": False,
    }
    risk = {
        "planHash": "4" * 64,
        "identity": {
            "baseSha": "0" * 40,
            "candidateSha": "1" * 40,
            "candidateRef": "topic",
            "changeSource": "committed",
            "candidate": candidate_identity,
            "selectionSha256": "8" * 64,
        },
        "risk": {"class": "R4"},
        "changedFiles": ["tracked.txt"],
        "gates": [{"id": "scope.diff", "required": True}],
    }
    stage = {"planHash": "5" * 64, "tier": "canonical", "releaseReady": False}
    shard = {"planHash": "6" * 64}
    resume_plan = {
        "planHash": "7" * 64,
        "tier": "canonical",
        "candidateShards": ["shard-a"],
        "reusableShards": [],
        "remainingShards": ["shard-a"],
        "rejectionReasons": [],
    }
    execution = {
        "schemaVersion": module.validation_planner.RISK_SELECTION_SCHEMA,
        "status": "passed",
        "exitCode": 0,
        "gates": [{"gateId": "scope.diff", "status": "passed", "retries": []}],
    }
    dependency = {
        "contentHash": "a" * 64,
        "selectedLock": "fixture.lock",
        "selectedProjection": "fixture-projection",
        "selectedProjectionHash": "b" * 64,
    }
    shard_result = {
        "status": "passed",
        "zeroNewFailures": True,
        "executionIdentity": {
            "candidate": candidate_identity,
            "environment": {"fingerprint": FINGERPRINT},
            "dependencyLock": dependency,
            "command": {"selected": {"argv": ["fixture"], "sha256": "c" * 64}},
            "topology": {"count": 1, "sha256": "d" * 64},
        },
    }
    values = {
        "riskPlan": risk,
        "stagePlan": stage,
        "shardPlan": shard,
        "resumePlan": resume_plan,
        "shardSuiteResult": shard_result,
        "executionResult": execution,
    }
    artifacts = {
        key: _write_json_artifact(module, root / f"{key}.json", value)
        for key, value in values.items()
    }
    evidence = {
        "schemaVersion": module.EVIDENCE_SCHEMA,
        "state": "complete",
        "repository": {
            "acceptedBase": "0" * 40,
            "branch": "topic",
            "remote": "origin",
            "remoteUrl": "fixture.git",
            "targetRef": "refs/heads/main",
        },
        "candidate": {
            "commitSha": "1" * 40,
            "treeSha": "2" * 40,
            "parentSha": "0" * 40,
            "subject": "candidate subject",
            "patchSha256": "e" * 64,
        },
        "changedFiles": {"paths": ["tracked.txt"], "sha256": module.canonical_hash(["tracked.txt"])},
        "validation": {
            "status": "passed",
            "firstAttempt": True,
            "retryCount": 0,
            "riskClass": "R4",
            "tier": "canonical",
        },
        "artifacts": artifacts,
        "shardSuiteDirectory": "suite",
    }

    monkeypatch.setattr(module.validation_planner, "_validate_plan", lambda _value: None)
    monkeypatch.setattr(module.validation_planner, "validate_backend_stage_plan", lambda _value: None)
    monkeypatch.setattr(
        module.validation_resume,
        "build_resume_context",
        lambda *_values: {"tier": "canonical", "shards": [{"id": "shard-a"}]},
    )
    monkeypatch.setattr(module.validation_resume, "_validated_resume_plan", lambda value: value)
    from tests import conftest as shard_authority

    monkeypatch.setattr(shard_authority, "validate_backend_shard_suite", lambda *_values: shard_result)

    def seal_and_write(value: dict) -> Path:
        value["evidenceHash"] = module.canonical_hash(value)
        path = root / "evidence.json"
        path.write_bytes(module.canonical_bytes(value) + b"\n")
        return path

    loaded = module._load_verified_evidence(root, Path("evidence.json") if seal_and_write(evidence) else Path())
    assert loaded.candidate == "1" * 40
    assert loaded.release_ready is False
    assert loaded.environment_fingerprint == FINGERPRINT
    assert loaded.dependency_lock == dependency

    cases = []
    failed = json.loads(json.dumps(evidence))
    failed.pop("evidenceHash", None)
    failed_execution = json.loads(json.dumps(execution))
    failed_execution["status"] = "failed"
    failed["artifacts"]["executionResult"] = _write_json_artifact(
        module, root / "failed-execution.json", failed_execution
    )
    cases.append((failed, "validation_incomplete"))
    retried = json.loads(json.dumps(evidence))
    retried.pop("evidenceHash", None)
    retried_execution = json.loads(json.dumps(execution))
    retried_execution["gates"][0]["retries"] = [{"attempt": 1}]
    retried["artifacts"]["executionResult"] = _write_json_artifact(
        module, root / "retried-execution.json", retried_execution
    )
    cases.append((retried, "validation_retried"))
    release_ready = json.loads(json.dumps(evidence))
    release_ready.pop("evidenceHash", None)
    release_stage = json.loads(json.dumps(stage))
    release_stage["releaseReady"] = True
    release_ready["artifacts"]["stagePlan"] = _write_json_artifact(
        module, root / "release-ready-stage.json", release_stage
    )
    cases.append((release_ready, "release_ready_semantics_invalid"))
    malformed = json.loads(json.dumps(evidence))
    malformed.pop("evidenceHash", None)
    malformed["state"] = "incomplete"
    cases.append((malformed, "validation_evidence_malformed"))
    for index, (case, reason) in enumerate(cases):
        case["evidenceHash"] = module.canonical_hash(case)
        path = root / f"case-{index}.json"
        path.write_bytes(module.canonical_bytes(case) + b"\n")
        with pytest.raises(module.PromotionError) as raised:
            module._load_verified_evidence(root, Path(path.name))
        assert raised.value.code == reason


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=root, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _repository(tmp_path: Path, name: str = "repository") -> tuple[Path, Path, str, str]:
    repository = tmp_path / name
    worktree_root = tmp_path / f"{name}-worktrees"
    repository.mkdir()
    worktree_root.mkdir()
    _git(repository, "init", "-q", "--initial-branch=main")
    _git(repository, "config", "user.name", "Fixture")
    _git(repository, "config", "user.email", "fixture@example.test")
    (repository / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(repository, "add", "tracked.txt")
    _git(repository, "commit", "-qm", "base")
    accepted_base = _git(repository, "rev-parse", "HEAD")
    (repository / "tracked.txt").write_text("candidate\n", encoding="utf-8")
    _git(repository, "commit", "-qam", "candidate")
    candidate = _git(repository, "rev-parse", "HEAD")
    return repository, worktree_root, accepted_base, candidate


class _Environment:
    def __init__(self) -> None:
        self.fingerprints: dict[Path, str] = {}
        self.bootstrap_calls: list[tuple[Path, bool]] = []
        self.verify_error: str | None = None
        self.bootstrap_error: str | None = None

    def verify(self, path: Path) -> str:
        if self.verify_error:
            raise RuntimeError(self.verify_error)
        if path not in self.fingerprints:
            raise RuntimeError("worktree_pointer_invalid")
        return self.fingerprints[path]

    def bootstrap(self, path: Path, offline: bool) -> str:
        self.bootstrap_calls.append((path, offline))
        if self.bootstrap_error:
            raise RuntimeError(self.bootstrap_error)
        self.fingerprints[path] = FINGERPRINT
        return self.verify(path)


def _request(module, repository: Path, worktree_root: Path, accepted_base: str, candidate: str, **changes):
    values = {
        "repository": repository,
        "worktree": worktree_root / "topic",
        "worktree_root": worktree_root,
        "branch": "topic",
        "accepted_base": accepted_base,
        "candidate": candidate,
        "environment_fingerprint": FINGERPRINT,
        "source_worktree": repository,
        "source_branch": "main",
        "source_head": candidate,
        "validation_result": "passed",
        "land_result": "not_required",
        "promotion_required": False,
        "remote": None,
        "remote_ref": None,
        "delete_branch": True,
        "offline": True,
    }
    values.update(changes)
    return module.LifecycleRequest(**values)


def _authority(module, environment: _Environment):
    def verify(path: Path) -> str:
        try:
            return environment.verify(path)
        except RuntimeError as exc:
            raise module.LifecycleError("environment_verify_failed", str(exc)) from exc

    def bootstrap(path: Path, offline: bool) -> str:
        try:
            return environment.bootstrap(path, offline)
        except RuntimeError as exc:
            raise module.LifecycleError("environment_bootstrap_failed", str(exc)) from exc

    return module.VerifiedWorktreeLifecycle(
        environment_verify=verify,
        environment_bootstrap=bootstrap,
    )


def test_qualification_rejects_wrong_python_interpreter(tmp_path: Path) -> None:
    managed = tmp_path / ".venv" / "bin" / "python"
    managed.parent.mkdir(parents=True)
    managed.write_text("", encoding="utf-8")

    with pytest.raises(EnvironmentFailure, match="wrong_managed_interpreter"):
        require_managed_python(tmp_path, executable=tmp_path / "wrong" / "python")


def test_qualification_accepts_repository_python(tmp_path: Path) -> None:
    managed = tmp_path / ".venv" / "bin" / "python"
    managed.parent.mkdir(parents=True)
    managed.write_text("", encoding="utf-8")

    assert require_managed_python(tmp_path, executable=managed) == managed.resolve()

    module = _load_preflight()
    repository, worktree_root, accepted_base, candidate = _repository(tmp_path)
    environment = _Environment()
    authority = _authority(module, environment)
    request = _request(module, repository, worktree_root, accepted_base, candidate)

    created = authority.setup(request)
    assert created.exit_code == 0
    assert created.payload["states"]["setup"] == "created"
    assert created.payload["states"]["reuse"] == "not_reused"
    assert environment.bootstrap_calls == [(request.worktree, True)]

    reused = authority.setup(request)
    assert reused.exit_code == 0
    assert reused.payload["states"]["setup"] == "ready"
    assert reused.payload["states"]["reuse"] == "reused"
    assert environment.bootstrap_calls == [(request.worktree, True)]

    _git(repository, "worktree", "remove", str(request.worktree))
    restored = authority.setup(request)
    assert restored.exit_code == 0
    assert restored.payload["states"]["setup"] == "restored"
    assert environment.bootstrap_calls[-1] == (request.worktree, True)

    remote = tmp_path / "remote.git"
    _git(tmp_path, "clone", "-q", "--bare", str(repository), str(remote))
    _git(tmp_path, f"--git-dir={remote}", "update-ref", "refs/heads/topic", candidate)
    cleanup_request = _request(
        module,
        repository,
        worktree_root,
        accepted_base,
        candidate,
        promotion_required=True,
        remote=str(remote),
        remote_ref="refs/heads/topic",
        land_result="succeeded",
    )
    worktree_only = authority.cleanup(
        _request(
            module,
            repository,
            worktree_root,
            accepted_base,
            candidate,
            promotion_required=True,
            remote=str(remote),
            remote_ref="refs/heads/topic",
            land_result="succeeded",
            delete_branch=False,
        )
    )
    assert worktree_only.exit_code == 0
    assert worktree_only.payload["states"]["cleanup"] == "completed"
    assert not request.worktree.exists()
    assert _git(repository, "show-ref", "--verify", "refs/heads/topic").startswith(candidate)

    kept_again = authority.cleanup(
        _request(
            module,
            repository,
            worktree_root,
            accepted_base,
            candidate,
            promotion_required=True,
            remote=str(remote),
            remote_ref="refs/heads/topic",
            land_result="succeeded",
            delete_branch=False,
        )
    )
    assert kept_again.exit_code == 0
    assert kept_again.payload["states"]["cleanup"] == "worktree_absent_branch_preserved"
    assert _git(repository, "show-ref", "--verify", "refs/heads/topic").startswith(candidate)

    cleaned = authority.cleanup(cleanup_request)
    assert cleaned.exit_code == 0
    assert cleaned.payload["states"]["land"] == "succeeded"
    assert cleaned.payload["states"]["cleanup"] == "branch_removed_after_worktree_absent"
    assert subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", "refs/heads/topic"], cwd=repository
    ).returncode == 1

    repeated = authority.cleanup(cleanup_request)
    assert repeated.exit_code == 0
    assert repeated.payload["states"]["cleanup"] == "already_absent"


@pytest.mark.parametrize(
    ("arguments", "delegated"),
    [
        (["bootstrap", "--check"], ["env", "verify"]),
        (["bootstrap", "--apply"], ["bootstrap", "--ensure"]),
    ],
)
def test_python_compatibility_entrypoint_delegates_to_wolfy(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str], delegated: list[str]
) -> None:
    module = _load_preflight()
    calls: list[list[str]] = []
    monkeypatch.setattr(module, "wolfy_main", lambda values: calls.append(values) or 0)

    assert module.main(arguments) == 0
    assert calls == [delegated]


def test_python_compatibility_entrypoint_rejects_obsolete_commands(tmp_path: Path) -> None:
    module = _load_preflight()

    assert module.main(["fingerprint"]) == 2

    def scenario(name: str):
        root = tmp_path / name
        root.mkdir()
        return _repository(root)

    # Exact path, registration, branch, HEAD/base, source, and clean-tree identity fail closed.
    repository, worktree_root, accepted_base, candidate = scenario("identity")
    environment = _Environment()
    authority = _authority(module, environment)
    request = _request(module, repository, worktree_root, accepted_base, candidate)
    assert authority.setup(request).exit_code == 0

    (request.worktree / "staged.txt").write_text("staged\n", encoding="utf-8")
    _git(request.worktree, "add", "staged.txt")
    assert authority.status(request).payload["reasonCode"] == "worktree_index_dirty"
    _git(request.worktree, "restore", "--staged", "staged.txt")
    (request.worktree / "staged.txt").unlink()
    (request.worktree / "tracked.txt").write_text("dirty\n", encoding="utf-8")
    assert authority.status(request).payload["reasonCode"] == "worktree_files_dirty"
    _git(request.worktree, "restore", "tracked.txt")
    (request.worktree / "untracked.txt").write_text("dirty\n", encoding="utf-8")
    assert authority.status(request).payload["reasonCode"] == "worktree_untracked_files"
    (request.worktree / "untracked.txt").unlink()
    _git(request.worktree, "checkout", "--detach", "-q")
    assert authority.status(request).payload["reasonCode"] == "worktree_detached"

    repository, worktree_root, accepted_base, candidate = scenario("branch-elsewhere")
    environment = _Environment()
    authority = _authority(module, environment)
    elsewhere = worktree_root / "elsewhere"
    _git(repository, "worktree", "add", "-q", "-b", "topic", str(elsewhere), candidate)
    request = _request(module, repository, worktree_root, accepted_base, candidate)
    result = authority.setup(request)
    assert result.payload["reasonCode"] == "branch_registered_elsewhere"
    assert elsewhere.exists() and not request.worktree.exists()

    repository, worktree_root, accepted_base, candidate = scenario("wrong-head")
    environment = _Environment()
    authority = _authority(module, environment)
    tree = _git(repository, "rev-parse", f"{candidate}^{{tree}}")
    wrong = _git(repository, "commit-tree", tree, "-m", "unrelated")
    request = _request(
        module,
        repository,
        worktree_root,
        accepted_base,
        wrong,
        source_worktree=None,
        source_branch=None,
        source_head=None,
    )
    result = authority.setup(request)
    assert result.payload["reasonCode"] == "candidate_not_descendant_of_base"

    repository, worktree_root, accepted_base, candidate = scenario("moved-source")
    environment = _Environment()
    authority = _authority(module, environment)
    request = _request(module, repository, worktree_root, accepted_base, candidate, source_head=accepted_base)
    result = authority.setup(request)
    assert result.payload["reasonCode"] == "source_head_mismatch"
    assert not request.worktree.exists()

    (repository / "source-untracked.txt").write_text("dirty\n", encoding="utf-8")
    dirty_source = _request(
        module,
        repository,
        worktree_root,
        accepted_base,
        candidate,
    )
    assert authority.setup(dirty_source).payload["reasonCode"] == "source_untracked_files"
    (repository / "source-untracked.txt").unlink()

    repository, worktree_root, accepted_base, candidate = scenario("outside-root")
    environment = _Environment()
    authority = _authority(module, environment)
    request = _request(
        module,
        repository,
        worktree_root,
        accepted_base,
        candidate,
        worktree=tmp_path / "outside-topic",
    )
    assert authority.setup(request).payload["reasonCode"] == "worktree_outside_authorized_root"

    nested_repository = repository / "nested"
    nested_repository.mkdir()
    request = _request(
        module,
        nested_repository,
        worktree_root,
        accepted_base,
        candidate,
    )
    nested = authority.status(request)
    assert nested.exit_code == 2
    assert nested.payload["reasonCode"] == "repository_path_not_toplevel"

    repository, worktree_root, accepted_base, candidate = scenario("not-registered")
    environment = _Environment()
    authority = _authority(module, environment)
    request = _request(module, repository, worktree_root, accepted_base, candidate)
    request.worktree.mkdir()
    assert authority.setup(request).payload["reasonCode"] == "directory_not_registered_worktree"

    repository, worktree_root, accepted_base, candidate = scenario("stale-environment")
    environment = _Environment()
    authority = _authority(module, environment)
    request = _request(module, repository, worktree_root, accepted_base, candidate)
    assert authority.setup(request).exit_code == 0
    environment.fingerprints[request.worktree] = "f" * 64
    stale = authority.setup(request)
    assert stale.payload["reasonCode"] == "environment_fingerprint_mismatch"
    assert stale.payload["states"]["preserved"] == "candidate_and_source"
    environment.verify_error = "verified_pointer_corrupt"
    verify_failure = authority.status(request)
    assert verify_failure.payload["reasonCode"] == "environment_verify_failed"
    assert verify_failure.payload["commandFailure"] == "verified_pointer_corrupt"

    repository, worktree_root, accepted_base, candidate = scenario("bootstrap-failure")
    environment = _Environment()
    environment.bootstrap_error = "offline_material_unavailable"
    authority = _authority(module, environment)
    request = _request(module, repository, worktree_root, accepted_base, candidate)
    failed = authority.setup(request)
    assert failed.payload["reasonCode"] == "environment_bootstrap_failed"
    assert failed.payload["commandFailure"] == "offline_material_unavailable"
    assert request.worktree.exists()

    repository, worktree_root, accepted_base, candidate = scenario("prunable")
    environment = _Environment()
    authority = _authority(module, environment)
    request = _request(module, repository, worktree_root, accepted_base, candidate)
    assert authority.setup(request).exit_code == 0
    shutil.rmtree(request.worktree)
    before_status = _git(repository, "worktree", "list", "--porcelain")
    status = authority.status(request)
    assert status.payload["reasonCode"] == "registration_prune_required"
    assert _git(repository, "worktree", "list", "--porcelain") == before_status
    remote = tmp_path / "prunable-mismatch.git"
    _git(tmp_path, "clone", "-q", "--bare", str(repository), str(remote))
    _git(tmp_path, f"--git-dir={remote}", "update-ref", "refs/heads/topic", accepted_base)
    cleanup_before_remote_equality = authority.cleanup(
        _request(
            module,
            repository,
            worktree_root,
            accepted_base,
            candidate,
            promotion_required=True,
            remote=str(remote),
            remote_ref="refs/heads/topic",
            land_result="succeeded",
        )
    )
    assert cleanup_before_remote_equality.payload["reasonCode"] == "remote_candidate_mismatch"
    assert cleanup_before_remote_equality.payload["mutations"] == []
    assert _git(repository, "worktree", "list", "--porcelain") == before_status
    repaired = authority.setup(request)
    assert repaired.exit_code == 0
    assert repaired.payload["states"]["setup"] == "restored"
    assert repaired.payload["mutations"][0] == "worktree_prune"

    _git(repository, "worktree", "lock", str(request.worktree))
    assert authority.status(request).payload["reasonCode"] == "worktree_locked"
    _git(repository, "worktree", "unlock", str(request.worktree))

    repository, worktree_root, accepted_base, candidate = scenario("preservation")
    environment = _Environment()
    authority = _authority(module, environment)
    request = _request(module, repository, worktree_root, accepted_base, candidate)
    assert authority.setup(request).exit_code == 0
    failed_validation = _request(
        module,
        repository,
        worktree_root,
        accepted_base,
        candidate,
        validation_result="failed",
    )
    preserved = authority.cleanup(failed_validation)
    assert preserved.payload["reasonCode"] == "validation_not_successful"
    assert preserved.payload["states"]["preserved"] == "candidate_and_source"
    assert request.worktree.exists()

    remote = tmp_path / "mismatch.git"
    _git(tmp_path, "clone", "-q", "--bare", str(repository), str(remote))
    _git(tmp_path, f"--git-dir={remote}", "update-ref", "refs/heads/topic", accepted_base)
    cleanup_request = _request(
        module,
        repository,
        worktree_root,
        accepted_base,
        candidate,
        promotion_required=True,
        remote=str(remote),
        remote_ref="refs/heads/topic",
        land_result="succeeded",
    )
    mismatch = authority.cleanup(cleanup_request)
    assert mismatch.payload["reasonCode"] == "remote_candidate_mismatch"
    assert mismatch.payload["states"]["land"] == "succeeded"
    assert mismatch.payload["states"]["cleanup"] == "refused"
    assert request.worktree.exists()

    not_landed = authority.cleanup(
        _request(
            module,
            repository,
            worktree_root,
            accepted_base,
            candidate,
            promotion_required=True,
            remote=str(remote),
            remote_ref="refs/heads/topic",
            land_result="not_evaluated",
        )
    )
    assert not_landed.payload["reasonCode"] == "land_not_successful"
    assert not_landed.payload["states"]["land"] == "not_evaluated"
    assert not_landed.payload["states"]["cleanup"] == "refused"

    unavailable = _request(
        module,
        repository,
        worktree_root,
        accepted_base,
        candidate,
        promotion_required=True,
        remote=str(tmp_path / "missing.git"),
        remote_ref="refs/heads/topic",
        land_result="succeeded",
    )
    assert authority.cleanup(unavailable).payload["reasonCode"] == "remote_verification_failed"

    _git(repository, "worktree", "remove", str(request.worktree))
    _git(repository, "update-ref", "refs/heads/topic", accepted_base, candidate)
    moved_request = _request(
        module,
        repository,
        worktree_root,
        accepted_base,
        candidate,
        promotion_required=False,
        land_result="succeeded",
    )
    moved = authority.cleanup(moved_request)
    assert moved.payload["reasonCode"] == "branch_moved"
    assert _git(repository, "rev-parse", "refs/heads/topic") == accepted_base

    outside_cleanup = _request(
        module,
        repository,
        worktree_root,
        accepted_base,
        candidate,
        worktree=tmp_path / "outside-cleanup",
        land_result="succeeded",
    )
    assert authority.cleanup(outside_cleanup).payload["reasonCode"] == "worktree_outside_authorized_root"


def test_posix_entrypoint_is_a_thin_wolfy_delegate() -> None:
    content = SCRIPT_PATH.read_text(encoding="utf-8")

    assert '"${ROOT_DIR}/wolfy" env verify' in content
    assert '"${ROOT_DIR}/wolfy" bootstrap --ensure' in content
    for obsolete in ("worktree_preflight.py", "requirements.txt", "node_modules", "CANONICAL_ROOT"):
        assert obsolete not in content


def test_powershell_entrypoint_is_a_thin_wolfy_delegate() -> None:
    content = POWERSHELL_PATH.read_text(encoding="utf-8")

    assert "wolfy.ps1" in content
    assert "worktree_preflight.py" not in content
    assert "bootstrap" in content
    assert "verify" in content


def test_python_delegate_contains_no_environment_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_preflight()
    content = CORE_PATH.read_text(encoding="utf-8")

    assert "environment.cli" in content
    assert "environmentFingerprint" in content
    for forbidden in (
        "shutil.rmtree",
        "reset --hard",
        "git stash",
        "git clean",
        "worktree remove --force",
        "branch -D",
    ):
        assert forbidden not in content

    repository, worktree_root, accepted_base, candidate = _repository(tmp_path)
    environment = _Environment()
    authority = _authority(module, environment)
    request = _request(module, repository, worktree_root, accepted_base, candidate)
    first = authority.setup(request)
    second = authority.status(request)
    repeated = authority.status(request)

    assert first.payload["schemaVersion"] == "wolfystock.worktree-lifecycle.v1"
    assert second.payload == repeated.payload
    assert second.payload["resultHash"] == module.canonical_hash(
        {key: value for key, value in second.payload.items() if key != "resultHash"}
    )
    encoded = json.dumps(second.payload, sort_keys=True)
    assert candidate in encoded and accepted_base in encoded and FINGERPRINT in encoded

    promotion = _load_task_promotion()
    _assert_task_promotion_contract(promotion, tmp_path / "task-promotion-contract")
    _assert_task_promotion_evidence_parser(promotion, monkeypatch, tmp_path)
