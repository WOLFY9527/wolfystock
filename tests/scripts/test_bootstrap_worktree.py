from __future__ import annotations

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


def test_python_delegate_contains_no_environment_authority(tmp_path: Path) -> None:
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
