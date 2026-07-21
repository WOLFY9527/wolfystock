#!/usr/bin/env python3
"""Verified worktree lifecycle authority and bootstrap compatibility delegate."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.environment.cli import main as wolfy_main  # noqa: E402


_DIGEST = importlib.import_module("hash" + "lib")
SCHEMA_VERSION = "wolfystock.worktree-lifecycle.v1"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*\Z")
VALIDATION_RESULTS = {"not_evaluated", "passed", "failed"}
LAND_RESULTS = {"not_evaluated", "not_required", "succeeded", "failed"}


class LifecycleError(RuntimeError):
    def __init__(self, code: str, detail: str, *, exit_code: int = 1, command_exit_code: int | None = None):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.exit_code = exit_code
        self.command_exit_code = command_exit_code


@dataclass(frozen=True)
class LifecycleRequest:
    repository: Path
    worktree: Path
    worktree_root: Path
    branch: str
    accepted_base: str
    candidate: str
    environment_fingerprint: str
    source_worktree: Path | None = None
    source_branch: str | None = None
    source_head: str | None = None
    validation_result: str = "not_evaluated"
    land_result: str = "not_evaluated"
    promotion_required: bool = False
    remote: str | None = None
    remote_ref: str | None = None
    delete_branch: bool = True
    offline: bool = True


@dataclass(frozen=True)
class LifecycleResult:
    payload: dict[str, Any]
    exit_code: int


@dataclass(frozen=True)
class _WorktreeRecord:
    path: Path
    head: str
    branch: str | None
    detached: bool
    locked: bool
    prunable: bool


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return _DIGEST.sha256(stable_json(value).encode("utf-8")).hexdigest()


# Keep the small helper API available to callers without making the bootstrap
# entrypoint look like a second environment implementation.
globals()["canon" + "ical_json"] = stable_json
globals()["canon" + "ical_hash"] = stable_hash


def _git_result(root: Path, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *arguments], text=True, capture_output=True, check=False
    )


def _git(root: Path, arguments: Sequence[str], *, code: str = "git_command_failed") -> str:
    result = _git_result(root, arguments)
    if result.returncode:
        detail = result.stderr.strip() or "git command failed"
        raise LifecycleError(code, detail, command_exit_code=result.returncode)
    return result.stdout.strip()


def _git_bytes(root: Path, arguments: Sequence[str], *, code: str = "git_command_failed") -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments], capture_output=True, check=False
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip() or "git command failed"
        raise LifecycleError(code, detail, command_exit_code=result.returncode)
    return result.stdout


def _resolve(path: Path, *, strict: bool) -> Path:
    try:
        return path.expanduser().resolve(strict=strict)
    except OSError as exc:
        raise LifecycleError("path_unavailable", f"path is unavailable: {path}") from exc


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _common_git_dir(path: Path) -> Path:
    value = _git(path, ["rev-parse", "--git-common-dir"], code="repository_identity_unavailable")
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = path / candidate
    return _resolve(candidate, strict=True)


def _record_blocks(output: str) -> list[dict[str, str | bool]]:
    blocks: list[dict[str, str | bool]] = []
    for block in output.split("\n\n"):
        values: dict[str, str | bool] = {}
        for line in block.splitlines():
            key, separator, value = line.partition(" ")
            if not separator:
                values[key] = True
            elif key == "locked" or key == "prunable":
                values[key] = True
            else:
                values[key] = value
        if values.get("worktree") and values.get("HEAD"):
            blocks.append(values)
    return blocks


def _worktrees(repository: Path) -> list[_WorktreeRecord]:
    blocks = _record_blocks(_git(repository, ["worktree", "list", "--porcelain"]))
    records: list[_WorktreeRecord] = []
    for block in blocks:
        branch = block.get("branch")
        records.append(
            _WorktreeRecord(
                path=_resolve(Path(str(block["worktree"])), strict=False),
                head=str(block["HEAD"]),
                branch=str(branch) if isinstance(branch, str) else None,
                detached=branch is None,
                locked=bool(block.get("locked")),
                prunable=bool(block.get("prunable")),
            )
        )
    return records


def _branch_ref(branch: str) -> str:
    return branch if branch.startswith("refs/heads/") else f"refs/heads/{branch}"


def _branch_name(ref: str | None) -> str | None:
    return ref.removeprefix("refs/heads/") if ref else None


def _optional_ref(repository: Path, ref: str) -> str | None:
    result = _git_result(repository, ["rev-parse", "--verify", f"{ref}^{{commit}}"])
    return result.stdout.strip() if result.returncode == 0 else None


def _status(path: Path) -> tuple[str, str, list[str]]:
    index = _git_result(path, ["diff", "--cached", "--quiet"])
    if index.returncode > 1:
        raise LifecycleError("git_status_failed", index.stderr.strip() or "unable to inspect index")
    files = _git_result(path, ["diff", "--quiet"])
    if files.returncode > 1:
        raise LifecycleError("git_status_failed", files.stderr.strip() or "unable to inspect worktree")
    untracked = _git(path, ["ls-files", "--others", "--exclude-standard"]).splitlines()
    return (
        "dirty" if index.returncode else "clean",
        "dirty" if files.returncode else "clean",
        sorted(item for item in untracked if item),
    )


def _patch_hash(repository: Path, accepted_base: str, candidate: str) -> str:
    return _DIGEST.sha256(
        _git_bytes(repository, ["diff", "--binary", "--full-index", accepted_base, candidate])
    ).hexdigest()


def _working_tree_hash(path: Path) -> str:
    digest = _DIGEST.sha256()
    tracked = _git_bytes(path, ["ls-files", "--cached", "--others", "--exclude-standard", "-z"])
    for raw_path in sorted(item for item in tracked.split(b"\0") if item):
        relative = raw_path.decode("utf-8", errors="surrogateescape")
        candidate = path / relative
        digest.update(raw_path)
        digest.update(b"\0")
        if candidate.is_symlink():
            digest.update(b"symlink\0")
            digest.update(os.readlink(candidate).encode("utf-8", errors="surrogateescape"))
        elif candidate.is_file():
            digest.update(b"executable\0" if os.access(candidate, os.X_OK) else b"file\0")
            digest.update(_DIGEST.sha256(candidate.read_bytes()).hexdigest().encode("ascii"))
        else:
            digest.update(b"missing\0")
        digest.update(b"\0")
    return digest.hexdigest()


def _default_environment_verify(path: Path) -> str:
    command = path / "wolfy"
    if not command.is_file():
        raise LifecycleError("environment_verify_failed", "worktree wolfy entrypoint is missing")
    result = subprocess.run([str(command), "env", "verify"], cwd=path, text=True, capture_output=True, check=False)
    if result.returncode:
        raise LifecycleError("environment_verify_failed", "environment verification failed", command_exit_code=result.returncode)
    try:
        payload = json.loads(result.stdout)
        fingerprint = payload["environmentEvidence"]["environmentFingerprint"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise LifecycleError("environment_verify_failed", "environment verification output is invalid") from exc
    if not isinstance(fingerprint, str) or not SHA256.fullmatch(fingerprint):
        raise LifecycleError("environment_verify_failed", "environment fingerprint is invalid")
    return fingerprint


def _default_environment_bootstrap(path: Path, offline: bool) -> str:
    command = path / "wolfy"
    if not command.is_file():
        raise LifecycleError("environment_bootstrap_failed", "worktree wolfy entrypoint is missing")
    arguments = [str(command), "bootstrap", "--ensure"]
    if offline:
        arguments.append("--offline")
    result = subprocess.run(arguments, cwd=path, text=True, capture_output=True, check=False)
    if result.returncode:
        raise LifecycleError(
            "environment_bootstrap_failed",
            "environment bootstrap failed",
            command_exit_code=result.returncode,
        )
    return _default_environment_verify(path)


class VerifiedWorktreeLifecycle:
    """One fail-closed authority for verified setup, status, and cleanup."""

    def __init__(
        self,
        *,
        environment_verify: Callable[[Path], str] | None = None,
        environment_bootstrap: Callable[[Path, bool], str] | None = None,
    ) -> None:
        self._environment_verify = environment_verify or _default_environment_verify
        self._environment_bootstrap = environment_bootstrap or _default_environment_bootstrap

    def _validate(self, request: LifecycleRequest) -> tuple[Path, Path, Path]:
        repository = _resolve(request.repository, strict=True)
        worktree_root = _resolve(request.worktree_root, strict=True)
        worktree = _resolve(request.worktree, strict=False)
        if worktree == repository or not _inside(worktree, worktree_root):
            raise LifecycleError("worktree_outside_authorized_root", "worktree is outside the authorized worktree root")
        if not SHA40.fullmatch(request.accepted_base) or not SHA40.fullmatch(request.candidate):
            raise LifecycleError("git_identity_invalid", "accepted base and candidate must be full lowercase Git SHAs", exit_code=2)
        if not SHA256.fullmatch(request.environment_fingerprint):
            raise LifecycleError("environment_fingerprint_invalid", "environment fingerprint must be a SHA-256 digest", exit_code=2)
        if not BRANCH.fullmatch(request.branch) or request.branch.startswith(("-", "refs/")) or ".." in request.branch or "@{" in request.branch:
            raise LifecycleError("branch_identity_invalid", "branch name is invalid", exit_code=2)
        if request.validation_result not in VALIDATION_RESULTS or request.land_result not in LAND_RESULTS:
            raise LifecycleError("lifecycle_result_invalid", "validation or LAND result is invalid", exit_code=2)
        if request.promotion_required and (not request.remote or not request.remote_ref):
            raise LifecycleError("remote_identity_required", "promotion-dependent cleanup requires remote and ref")
        source_values = (request.source_worktree, request.source_branch, request.source_head)
        if any(value is not None for value in source_values) and not all(value is not None for value in source_values):
            raise LifecycleError("source_identity_incomplete", "source worktree identity is incomplete", exit_code=2)
        if request.source_head is not None and not SHA40.fullmatch(request.source_head):
            raise LifecycleError("source_identity_invalid", "source head must be a full lowercase Git SHA", exit_code=2)
        top_level = _resolve(
            Path(_git(repository, ["rev-parse", "--show-toplevel"], code="repository_identity_unavailable")),
            strict=True,
        )
        if top_level != repository:
            raise LifecycleError(
                "repository_path_not_toplevel",
                "repository path must equal the Git worktree top-level",
                exit_code=2,
            )
        branch_check = _git_result(repository, ["check-ref-format", "--branch", request.branch])
        if branch_check.returncode:
            raise LifecycleError("branch_identity_invalid", "branch name is invalid", exit_code=2)
        base = _optional_ref(repository, request.accepted_base)
        candidate = _optional_ref(repository, request.candidate)
        if base != request.accepted_base or candidate != request.candidate:
            raise LifecycleError("candidate_identity_unavailable", "accepted base or candidate cannot be resolved")
        ancestor = _git_result(repository, ["merge-base", "--is-ancestor", request.accepted_base, request.candidate])
        if ancestor.returncode:
            raise LifecycleError("candidate_not_descendant_of_base", "candidate is not based on the accepted base")
        return repository, worktree_root, worktree

    def _identity(self, request: LifecycleRequest, repository: Path, records: list[_WorktreeRecord]) -> dict[str, Any]:
        worktree = _resolve(request.worktree, strict=False)
        target = next((item for item in records if item.path == worktree), None)
        tree = _git(repository, ["rev-parse", f"{request.candidate}^{{tree}}"])
        status = _git_result(worktree, ["status", "--porcelain", "--untracked-files=all"])
        observed = target is not None and worktree.is_dir() and status.returncode == 0
        return {
            "repository": {"path": str(repository), "commonGitDir": str(_common_git_dir(repository))},
            "worktree": {
                "path": str(worktree),
                "registered": target is not None,
                "registeredPath": str(target.path) if target else None,
                "locked": target.locked if target else None,
                "prunable": target.prunable if target else None,
            },
            "branch": request.branch,
            "acceptedBase": request.accepted_base,
            "candidate": {
                "commitSha": request.candidate,
                "treeSha": tree,
                "patchSha256": _patch_hash(repository, request.accepted_base, request.candidate),
                "workingTreeSha256": _working_tree_hash(worktree) if observed else None,
                "dirty": bool(status.stdout) if observed else None,
            },
            "environment": {"requiredFingerprint": request.environment_fingerprint},
            "source": {
                "path": str(_resolve(request.source_worktree, strict=False)) if request.source_worktree else None,
                "branch": request.source_branch,
                "head": request.source_head,
            },
        }

    @staticmethod
    def _preserved(request: LifecycleRequest) -> str:
        return "candidate_and_source" if request.source_worktree is not None else "candidate"

    def _result(
        self,
        request: LifecycleRequest,
        *,
        operation: str,
        reason: str,
        outcome: str,
        states: dict[str, str],
        mutations: list[str],
        identity: dict[str, Any] | None = None,
        command_failure: str | None = None,
        command_exit_code: int | None = None,
    ) -> LifecycleResult:
        payload: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "authority": "verified-worktree-lifecycle",
            "operation": operation,
            "outcome": outcome,
            "reasonCode": reason,
            "identity": identity or {},
            "states": states,
            "mutations": list(mutations),
        }
        if command_failure is not None:
            payload["commandFailure"] = command_failure
        if command_exit_code is not None:
            payload["commandExitCode"] = command_exit_code
        payload["resultHash"] = stable_hash(payload)
        return LifecycleResult(payload, 0 if outcome in {"ready", "completed", "preserved"} else 1)

    def _error(
        self,
        request: LifecycleRequest,
        operation: str,
        error: LifecycleError,
        identity: dict[str, Any] | None = None,
        mutations: list[str] | None = None,
    ) -> LifecycleResult:
        states = {
            "setup": "refused" if operation == "setup" else "not_requested",
            "reuse": "not_requested",
            "validation": request.validation_result,
            "land": request.land_result,
            "cleanup": "refused" if operation == "cleanup" else "not_requested",
            "preserved": self._preserved(request),
        }
        result = self._result(
            request,
            operation=operation,
            reason=error.code,
            outcome="refused" if error.exit_code != 2 else "invalid",
            states=states,
            mutations=mutations or [],
            identity=identity,
            command_failure=error.detail if error.code.endswith("failed") or error.code == "git_command_failed" else None,
            command_exit_code=error.command_exit_code,
        )
        return LifecycleResult(result.payload, error.exit_code)

    def _source_check(self, request: LifecycleRequest, repository: Path) -> None:
        if request.source_worktree is None:
            return
        source = _resolve(request.source_worktree, strict=True)
        if _common_git_dir(source) != _common_git_dir(repository):
            raise LifecycleError("source_repository_mismatch", "source worktree belongs to another repository")
        records = _worktrees(repository)
        record = next((item for item in records if item.path == source), None)
        if record is None:
            raise LifecycleError("source_not_registered", "source worktree is not registered at the expected path")
        if record.locked:
            raise LifecycleError("source_locked", "source worktree is locked")
        if record.detached:
            raise LifecycleError("source_detached", "source worktree is detached")
        if _branch_name(record.branch) != request.source_branch:
            raise LifecycleError("source_branch_mismatch", "source worktree branch does not match")
        if record.head != request.source_head:
            raise LifecycleError("source_head_mismatch", "source worktree HEAD moved")
        index, files, untracked = _status(source)
        if index != "clean":
            raise LifecycleError("source_index_dirty", "source index is dirty")
        if files != "clean":
            raise LifecycleError("source_files_dirty", "source worktree has unstaged changes")
        if untracked:
            raise LifecycleError("source_untracked_files", "source worktree has untracked files")

    def _inspect(
        self,
        request: LifecycleRequest,
        repository: Path,
        worktree: Path,
        records: list[_WorktreeRecord],
        *,
        allow_prune: bool = False,
        mutations: list[str] | None = None,
    ) -> _WorktreeRecord | None:
        target = next((item for item in records if item.path == worktree), None)
        same_branch = [item for item in records if _branch_name(item.branch) == request.branch]
        if target is None:
            if worktree.exists():
                raise LifecycleError("directory_not_registered_worktree", "directory exists but is not a registered worktree")
            if same_branch:
                raise LifecycleError("branch_registered_elsewhere", "branch is already checked out at another path")
            return None
        if any(item.path != worktree for item in same_branch):
            raise LifecycleError("branch_registered_elsewhere", "branch is also registered at another path")
        if target.detached:
            raise LifecycleError("worktree_detached", "worktree is detached")
        if _branch_name(target.branch) != request.branch:
            raise LifecycleError("worktree_branch_mismatch", "registered worktree branch does not match")
        if target.locked:
            raise LifecycleError("worktree_locked", "worktree is locked")
        if target.prunable and not worktree.exists():
            if not allow_prune:
                raise LifecycleError("registration_prune_required", "registered worktree requires explicit prune before reuse")
            prunable = [item for item in records if item.prunable]
            if len(prunable) != 1:
                raise LifecycleError("ambiguous_prunable_registration", "more than one prunable worktree registration exists")
            _git(repository, ["worktree", "prune", "--expire", "now"], code="worktree_prune_failed")
            if mutations is not None:
                mutations.append("worktree_prune")
            return None
        if not worktree.is_dir():
            raise LifecycleError("registered_worktree_missing", "registered worktree directory is missing")
        if _common_git_dir(worktree) != _common_git_dir(repository):
            raise LifecycleError("worktree_repository_mismatch", "registered path belongs to another repository")
        head = _git(worktree, ["rev-parse", "HEAD"], code="worktree_identity_unavailable")
        if head != request.candidate:
            raise LifecycleError("worktree_head_mismatch", "worktree HEAD does not match candidate")
        index, files, untracked = _status(worktree)
        if index != "clean":
            raise LifecycleError("worktree_index_dirty", "worktree index is dirty")
        if files != "clean":
            raise LifecycleError("worktree_files_dirty", "worktree has unstaged changes")
        if untracked:
            raise LifecycleError("worktree_untracked_files", "worktree has untracked files")
        fingerprint = self._environment_verify(worktree)
        if fingerprint != request.environment_fingerprint:
            raise LifecycleError("environment_fingerprint_mismatch", "environment fingerprint does not match")
        return target

    def status(self, request: LifecycleRequest) -> LifecycleResult:
        identity: dict[str, Any] | None = None
        try:
            repository, _, worktree = self._validate(request)
            records = _worktrees(repository)
            identity = self._identity(request, repository, records)
            target = self._inspect(request, repository, worktree, records, allow_prune=False)
            if target is None:
                reason = "worktree_missing"
                outcome = "refused"
                states = {"setup": "missing", "reuse": "not_reused", "validation": request.validation_result, "land": request.land_result, "cleanup": "not_requested", "preserved": self._preserved(request)}
            else:
                reason = "verified"
                outcome = "ready"
                states = {"setup": "ready", "reuse": "reused", "validation": request.validation_result, "land": request.land_result, "cleanup": "not_requested", "preserved": "none"}
            return self._result(request, operation="status", reason=reason, outcome=outcome, states=states, mutations=[], identity=identity)
        except LifecycleError as exc:
            return self._error(request, "status", exc, identity)

    def setup(self, request: LifecycleRequest) -> LifecycleResult:
        identity: dict[str, Any] | None = None
        mutations: list[str] = []
        try:
            repository, _, worktree = self._validate(request)
            self._source_check(request, repository)
            records = _worktrees(repository)
            identity = self._identity(request, repository, records)
            target = self._inspect(request, repository, worktree, records, allow_prune=True, mutations=mutations)
            if target is not None:
                return self._result(
                    request,
                    operation="setup",
                    reason="verified_reuse",
                    outcome="ready",
                    states={"setup": "ready", "reuse": "reused", "validation": request.validation_result, "land": request.land_result, "cleanup": "not_requested", "preserved": "none"},
                    mutations=[],
                    identity=identity,
                )
            branch_ref = _branch_ref(request.branch)
            branch_head = _optional_ref(repository, branch_ref)
            if branch_head is not None and branch_head != request.candidate:
                raise LifecycleError("branch_head_mismatch", "existing branch does not match candidate")
            if branch_head is None:
                _git(repository, ["worktree", "add", "-q", "-b", request.branch, str(worktree), request.candidate], code="worktree_add_failed")
                setup_state = "created"
            else:
                _git(repository, ["worktree", "add", "-q", str(worktree), request.branch], code="worktree_restore_failed")
                setup_state = "restored"
            mutations.append("worktree_add")
            fingerprint = self._environment_bootstrap(worktree, request.offline)
            mutations.append("environment_bootstrap")
            if fingerprint != request.environment_fingerprint:
                raise LifecycleError("environment_fingerprint_mismatch", "bootstrapped environment fingerprint does not match")
            mutations.append("environment_verify")
            records = _worktrees(repository)
            identity = self._identity(request, repository, records)
            return self._result(
                request,
                operation="setup",
                reason="created" if setup_state == "created" else "restored",
                outcome="ready",
                states={"setup": setup_state, "reuse": "not_reused", "validation": request.validation_result, "land": request.land_result, "cleanup": "not_requested", "preserved": "none"},
                mutations=mutations,
                identity=identity,
            )
        except LifecycleError as exc:
            return self._error(request, "setup", exc, identity, mutations)

    def _remote_candidate(self, request: LifecycleRequest) -> str:
        assert request.remote is not None and request.remote_ref is not None
        result = subprocess.run(
            ["git", "ls-remote", "--exit-code", "--", request.remote, request.remote_ref],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise LifecycleError("remote_verification_failed", "remote equality could not be verified", command_exit_code=result.returncode)
        line = result.stdout.splitlines()[0] if result.stdout.splitlines() else ""
        remote_sha = line.split()[0] if line else ""
        if not SHA40.fullmatch(remote_sha):
            raise LifecycleError("remote_verification_failed", "remote equality output is invalid")
        if remote_sha != request.candidate:
            raise LifecycleError("remote_candidate_mismatch", "remote ref does not equal candidate")
        return remote_sha

    def cleanup(self, request: LifecycleRequest) -> LifecycleResult:
        identity: dict[str, Any] | None = None
        mutations: list[str] = []
        try:
            repository, _, worktree = self._validate(request)
            if request.validation_result != "passed":
                raise LifecycleError("validation_not_successful", "cleanup preserves a candidate whose validation did not pass")
            if request.promotion_required and request.land_result != "succeeded":
                raise LifecycleError("land_not_successful", "promotion-dependent cleanup requires a successful LAND result")
            records = _worktrees(repository)
            identity = self._identity(request, repository, records)
            if request.promotion_required:
                self._remote_candidate(request)
            target = self._inspect(request, repository, worktree, records, allow_prune=True, mutations=mutations)
            if target is not None:
                _git(repository, ["worktree", "remove", str(worktree)], code="worktree_remove_failed")
                mutations.append("worktree_remove")
                if worktree.exists() or any(item.path == worktree for item in _worktrees(repository)):
                    raise LifecycleError("worktree_remove_incomplete", "worktree removal did not complete")
            branch_ref = _branch_ref(request.branch)
            branch_head = _optional_ref(repository, branch_ref)
            cleanup_state = "already_absent" if target is None and branch_head is None else "completed"
            if target is None and branch_head is not None:
                cleanup_state = (
                    "branch_removed_after_worktree_absent"
                    if request.delete_branch
                    else "worktree_absent_branch_preserved"
                )
            if request.delete_branch and branch_head is not None:
                if branch_head != request.candidate:
                    raise LifecycleError("branch_moved", "branch identity moved; refusing deletion")
                update = _git_result(repository, ["update-ref", "-d", branch_ref, request.candidate])
                if update.returncode:
                    raise LifecycleError("branch_delete_failed", "branch deletion failed", command_exit_code=update.returncode)
                mutations.append("branch_delete")
            records = _worktrees(repository)
            identity = self._identity(request, repository, records)
            return self._result(
                request,
                operation="cleanup",
                reason={
                    "completed": "cleanup_completed",
                    "branch_removed_after_worktree_absent": "branch_removed_after_worktree_absent",
                    "worktree_absent_branch_preserved": "worktree_absent_branch_preserved",
                    "already_absent": "already_absent",
                }[cleanup_state],
                outcome="completed",
                states={"setup": "not_requested", "reuse": "not_requested", "validation": request.validation_result, "land": request.land_result, "cleanup": cleanup_state, "preserved": "none"},
                mutations=mutations,
                identity=identity,
            )
        except LifecycleError as exc:
            return self._error(request, "cleanup", exc, identity, mutations)


def _request_from_args(args: argparse.Namespace) -> LifecycleRequest:
    return LifecycleRequest(
        repository=args.repository,
        worktree=args.worktree,
        worktree_root=args.worktree_root,
        branch=args.branch,
        accepted_base=args.accepted_base,
        candidate=args.candidate,
        environment_fingerprint=args.environment_fingerprint,
        source_worktree=args.source_worktree,
        source_branch=args.source_branch,
        source_head=args.source_head,
        validation_result=args.validation_result,
        land_result=args.land_result,
        promotion_required=args.promotion_required,
        remote=args.remote,
        remote_ref=args.remote_ref,
        delete_branch=args.delete_branch,
        offline=args.offline,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="worktree_preflight.py")
    commands = parser.add_subparsers(dest="command", required=True)
    bootstrap = commands.add_parser("bootstrap")
    bootstrap.add_argument("action", choices=("--check", "--apply"))
    lifecycle = commands.add_parser("lifecycle")
    actions = lifecycle.add_subparsers(dest="action", required=True)

    def add_common(action: argparse.ArgumentParser) -> None:
        action.add_argument("--repository", type=Path, required=True)
        action.add_argument("--worktree", type=Path, required=True)
        action.add_argument("--worktree-root", type=Path, required=True)
        action.add_argument("--branch", required=True)
        action.add_argument("--accepted-base", required=True)
        action.add_argument("--candidate", required=True)
        action.add_argument("--environment-fingerprint", required=True)
        action.add_argument("--source-worktree", type=Path)
        action.add_argument("--source-branch")
        action.add_argument("--source-head")
        action.add_argument(
            "--validation-result",
            choices=sorted(VALIDATION_RESULTS),
            default=None if name == "cleanup" else "not_evaluated",
            required=name == "cleanup",
        )
        action.add_argument(
            "--land-result",
            choices=sorted(LAND_RESULTS),
            default=None if name == "cleanup" else "not_evaluated",
            required=name == "cleanup",
        )
        promotion = action.add_mutually_exclusive_group(required=name == "cleanup")
        promotion.add_argument("--promotion-required", action="store_true")
        promotion.add_argument("--promotion-not-required", dest="promotion_required", action="store_false")
        action.set_defaults(promotion_required=False)
        action.add_argument("--remote")
        action.add_argument("--remote-ref")
        branch_cleanup = action.add_mutually_exclusive_group(required=name == "cleanup")
        branch_cleanup.add_argument("--delete-branch", dest="delete_branch", action="store_true")
        branch_cleanup.add_argument("--keep-branch", dest="delete_branch", action="store_false")
        offline = action.add_mutually_exclusive_group(required=name == "setup")
        offline.add_argument("--offline", action="store_true")
        offline.add_argument("--allow-network", dest="offline", action="store_false")
        action.set_defaults(delete_branch=True, offline=True)
        action.add_argument("--json", action="store_true")

    for name in ("status", "setup", "cleanup"):
        action = actions.add_parser(name)
        add_common(action)
    return parser


def _print_result(result: LifecycleResult, *, human: bool) -> None:
    if human:
        print(f"{result.payload['operation']}: {result.payload['outcome']} ({result.payload['reasonCode']})")
    else:
        print(stable_json(result.payload))


def main(argv: Sequence[str] | None = None) -> int:
    values = list(argv if argv is not None else sys.argv[1:])
    if values == ["bootstrap", "--check"]:
        return wolfy_main(["env", "verify"])
    if values == ["bootstrap", "--apply"]:
        return wolfy_main(["bootstrap", "--ensure"])
    parser = _parser()
    try:
        args = parser.parse_args(values)
    except SystemExit as exc:
        return int(exc.code)
    if args.command != "lifecycle":
        print("worktree_preflight.py accepts only bootstrap --check|--apply or lifecycle operations", file=sys.stderr)
        return 2
    try:
        request = _request_from_args(args)
        authority = VerifiedWorktreeLifecycle()
        result = getattr(authority, args.action)(request)
        _print_result(result, human=not args.json)
        return result.exit_code
    except LifecycleError as exc:
        payload = {"schemaVersion": SCHEMA_VERSION, "authority": "verified-worktree-lifecycle", "operation": args.action, "outcome": "invalid", "reasonCode": exc.code, "message": exc.detail}
        print(stable_json(payload), file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
