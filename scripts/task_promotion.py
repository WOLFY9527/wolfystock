#!/usr/bin/env python3
"""Deterministic fail-closed task promotion authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import validation_changed_files as validation_planner  # noqa: E402
from scripts import validation_resume  # noqa: E402
from scripts.worktree_preflight import (  # noqa: E402
    LifecycleRequest,
    LifecycleResult,
    VerifiedWorktreeLifecycle,
)


SCHEMA_VERSION = "wolfystock.task-promotion.v1"
EVIDENCE_SCHEMA = "wolfystock.task-promotion-validation.v1"
SHA40 = frozenset("0123456789abcdef")
SHA256 = frozenset("0123456789abcdef")
TARGET_REF = "refs/heads/main"
REMOTE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*\Z")
ARTIFACT_KEYS = frozenset(
    {
        "riskPlan",
        "stagePlan",
        "shardPlan",
        "resumePlan",
        "shardSuiteResult",
        "executionResult",
    }
)


class PromotionError(RuntimeError):
    def __init__(self, code: str, detail: str, *, command_exit_code: int | None = None):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.command_exit_code = command_exit_code


@dataclass(frozen=True)
class EnvironmentIdentity:
    fingerprint: str
    dependency_lock: dict[str, Any]


@dataclass(frozen=True)
class VerifiedEvidence:
    evidence_path: Path
    evidence_sha256: str
    accepted_base: str
    candidate: str
    tree: str
    working_tree_sha256: str
    parent: str
    subject: str
    branch: str
    patch_sha256: str
    changed_files: list[str]
    changed_files_sha256: str
    remote: str
    remote_url: str
    target_ref: str
    environment_fingerprint: str
    dependency_lock: dict[str, Any]
    risk_class: str
    tier: str
    release_ready: bool
    identities: dict[str, str]


@dataclass(frozen=True)
class PromotionResult:
    payload: dict[str, Any]
    exit_code: int


@dataclass(frozen=True)
class _Preflight:
    canonical: Path
    worktree: Path
    common_git_dir: Path
    evidence: VerifiedEvidence
    expected_remote: str


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _valid_digest(value: object, length: int) -> bool:
    alphabet = SHA40 if length == 40 else SHA256
    return isinstance(value, str) and len(value) == length and set(value) <= alphabet


def _require_digest(value: object, label: str, length: int = 64) -> str:
    if not _valid_digest(value, length):
        raise PromotionError("validation_evidence_malformed", f"{label} is not a lowercase digest")
    return str(value)


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or "\n" in value or "\r" in value:
        raise PromotionError("validation_evidence_malformed", f"{label} is invalid")
    return value


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PromotionError("validation_evidence_malformed", f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_object_pairs)
    except PromotionError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PromotionError("validation_evidence_malformed", f"{label} is missing or malformed") from exc
    if not isinstance(value, dict):
        raise PromotionError("validation_evidence_malformed", f"{label} must be a JSON object")
    return value


def _contained_path(root: Path, value: object, label: str, *, directory: bool = False) -> Path:
    text = _require_string(value, label)
    relative = Path(text)
    if relative.is_absolute() or ".." in relative.parts:
        raise PromotionError("validation_evidence_malformed", f"{label} must be a contained relative path")
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise PromotionError("validation_evidence_malformed", f"{label} escapes the evidence directory") from exc
    exists = path.is_dir() if directory else path.is_file()
    if not exists:
        raise PromotionError("validation_evidence_missing", f"{label} does not exist")
    return path


def _contained_tree(root: Path, directory: Path, label: str) -> Path:
    root = root.resolve()
    for child in directory.rglob("*"):
        try:
            child.resolve().relative_to(root)
        except ValueError as exc:
            raise PromotionError("validation_evidence_path_invalid", f"{label} contains an escaping path") from exc
    return directory


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_path(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise PromotionError("validation_evidence_malformed", f"{label} artifact record is invalid")
    path = _contained_path(root, value["path"], f"{label}.path")
    expected = _require_digest(value["sha256"], f"{label}.sha256")
    if _file_hash(path) != expected:
        raise PromotionError("validation_artifact_mismatch", f"{label} artifact hash mismatch")
    return path


def _run_git(
    root: Path,
    arguments: Sequence[str],
    *,
    code: str = "git_command_failed",
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip() or "Git command failed"
        raise PromotionError(code, detail, command_exit_code=result.returncode)
    return result


def _git(root: Path, arguments: Sequence[str], *, code: str = "git_command_failed") -> str:
    return _run_git(root, arguments, code=code).stdout.strip()


def _git_bytes(root: Path, arguments: Sequence[str], *, code: str = "git_command_failed") -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip() or "Git command failed"
        raise PromotionError(code, detail, command_exit_code=result.returncode)
    return result.stdout


def git_patch_hash(root: Path, accepted_base: str, candidate: str) -> str:
    return hashlib.sha256(
        _git_bytes(root, ["diff", "--binary", "--full-index", accepted_base, candidate])
    ).hexdigest()


def _changed_files(root: Path, accepted_base: str, candidate: str) -> list[str]:
    output = _git_bytes(root, ["diff", "--name-only", "-z", accepted_base, candidate])
    return sorted(item.decode("utf-8", errors="surrogateescape") for item in output.split(b"\0") if item)


def _common_git_dir(root: Path) -> Path:
    value = Path(_git(root, ["rev-parse", "--git-common-dir"], code="repository_identity_unavailable"))
    return (root / value).resolve() if not value.is_absolute() else value.resolve()


def _worktree_records(root: Path) -> list[dict[str, Any]]:
    output = _git(root, ["worktree", "list", "--porcelain"], code="worktree_registration_unavailable")
    records: list[dict[str, Any]] = []
    for block in output.split("\n\n"):
        record: dict[str, Any] = {}
        for line in block.splitlines():
            key, separator, value = line.partition(" ")
            record[key] = value if separator else True
        if "worktree" in record and "HEAD" in record:
            record["worktree"] = str(Path(record["worktree"]).resolve())
            records.append(record)
    return records


def _clean(root: Path) -> bool:
    return not _git(root, ["status", "--porcelain", "--untracked-files=all"])


def _remote_sha(root: Path, remote: str, target_ref: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-remote", "--exit-code", "--refs", "--", remote, target_ref],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise PromotionError(
            "remote_identity_unavailable",
            "the requested remote ref could not be resolved",
            command_exit_code=result.returncode,
        )
    lines = result.stdout.splitlines()
    sha = lines[0].split()[0] if len(lines) == 1 and lines[0].split() else ""
    if not _valid_digest(sha, 40):
        raise PromotionError("remote_identity_unavailable", "the requested remote ref identity is invalid")
    return sha


def _default_environment_verify(worktree: Path) -> EnvironmentIdentity:
    command = worktree / "wolfy"
    try:
        result = subprocess.run(
            [str(command), "env", "verify"],
            cwd=worktree,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise PromotionError("environment_verify_failed", "environment verification could not start") from exc
    if result.returncode:
        raise PromotionError(
            "environment_verify_failed",
            "the repository environment authority refused verification",
            command_exit_code=result.returncode,
        )
    try:
        payload = json.loads(result.stdout)
        environment = payload["environmentEvidence"]
        fingerprint = environment["environmentFingerprint"]
        lock = environment["pythonLock"]
        dependency = {
            key: lock[key]
            for key in ("contentHash", "selectedLock", "selectedProjection", "selectedProjectionHash")
        }
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise PromotionError("environment_verify_failed", "environment verification output is invalid") from exc
    return EnvironmentIdentity(fingerprint=fingerprint, dependency_lock=dependency)


def _load_verified_evidence(worktree: Path, evidence_argument: Path) -> VerifiedEvidence:
    if evidence_argument.is_absolute() or ".." in evidence_argument.parts:
        raise PromotionError(
            "validation_evidence_path_invalid",
            "validation evidence must be a contained worktree-relative path",
        )
    evidence_path = (worktree / evidence_argument).resolve()
    try:
        evidence_path.relative_to(worktree)
    except ValueError as exc:
        raise PromotionError("validation_evidence_path_invalid", "validation evidence escapes the task worktree") from exc
    raw = _load_json(evidence_path, "validation evidence")
    required = {
        "schemaVersion",
        "state",
        "repository",
        "candidate",
        "changedFiles",
        "validation",
        "artifacts",
        "shardSuiteDirectory",
        "evidenceHash",
    }
    if set(raw) != required or raw.get("schemaVersion") != EVIDENCE_SCHEMA or raw.get("state") != "complete":
        raise PromotionError("validation_evidence_malformed", "validation evidence schema, fields, or state is invalid")
    expected_hash = _require_digest(raw["evidenceHash"], "evidenceHash")
    if expected_hash != canonical_hash({key: value for key, value in raw.items() if key != "evidenceHash"}):
        raise PromotionError("validation_evidence_hash_mismatch", "validation evidence hash mismatch")

    repository = raw["repository"]
    candidate = raw["candidate"]
    changed = raw["changedFiles"]
    validation = raw["validation"]
    artifacts = raw["artifacts"]
    if not all(isinstance(value, dict) for value in (repository, candidate, changed, validation, artifacts)):
        raise PromotionError("validation_evidence_malformed", "validation evidence contains a malformed section")
    if set(repository) != {"acceptedBase", "branch", "remote", "remoteUrl", "targetRef"}:
        raise PromotionError("validation_evidence_malformed", "repository evidence fields are invalid")
    if set(candidate) != {"commitSha", "treeSha", "parentSha", "subject", "patchSha256"}:
        raise PromotionError("validation_evidence_malformed", "candidate evidence fields are invalid")
    if set(changed) != {"paths", "sha256"} or not isinstance(changed.get("paths"), list):
        raise PromotionError("validation_evidence_malformed", "changed-file evidence is invalid")
    if set(validation) != {"status", "firstAttempt", "retryCount", "riskClass", "tier"}:
        raise PromotionError("validation_evidence_malformed", "validation summary fields are invalid")
    paths = changed["paths"]
    if paths != sorted(set(paths)) or any(not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts for path in paths):
        raise PromotionError("validation_evidence_malformed", "changed-file inventory is invalid")
    if changed.get("sha256") != canonical_hash(paths):
        raise PromotionError("changed_files_identity_mismatch", "changed-file inventory hash mismatch")
    if set(artifacts) != ARTIFACT_KEYS:
        raise PromotionError("validation_evidence_malformed", "validation artifact inventory is invalid")

    artifact_root = evidence_path.parent
    artifact_paths = {key: _artifact_path(artifact_root, artifacts[key], key) for key in sorted(ARTIFACT_KEYS)}
    risk_plan = _load_json(artifact_paths["riskPlan"], "risk plan")
    stage_plan = _load_json(artifact_paths["stagePlan"], "stage plan")
    shard_plan = _load_json(artifact_paths["shardPlan"], "shard plan")
    resume_plan = _load_json(artifact_paths["resumePlan"], "resume plan")
    execution_result = _load_json(artifact_paths["executionResult"], "execution result")
    shard_result = _load_json(artifact_paths["shardSuiteResult"], "shard suite result")

    try:
        validation_planner._validate_plan(risk_plan)
        validation_planner.validate_backend_stage_plan(stage_plan)
        context = validation_resume.build_resume_context(risk_plan, stage_plan, shard_plan)
        validation_resume._validated_resume_plan(resume_plan)
        from tests import conftest as shard_authority

        suite_directory = _contained_path(
            artifact_root,
            raw["shardSuiteDirectory"],
            "shardSuiteDirectory",
            directory=True,
        )
        _contained_tree(artifact_root, suite_directory, "shardSuiteDirectory")
        observed_shard_result = shard_authority.validate_backend_shard_suite(
            artifact_paths["shardPlan"], suite_directory
        )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise PromotionError("validation_authority_refused", str(exc)) from exc
    if observed_shard_result != shard_result or shard_result.get("status") != "passed":
        raise PromotionError("shard_result_mismatch", "shard suite evidence is not an exact successful result")
    if shard_result.get("zeroNewFailures") is not True:
        raise PromotionError("validation_failed", "shard suite did not establish zero new failures")

    shard_ids = sorted(item["id"] for item in context["shards"])
    if (
        resume_plan.get("tier") != context["tier"]
        or resume_plan.get("candidateShards") not in ([], shard_ids)
        or sorted(resume_plan.get("reusableShards", []) + resume_plan.get("remainingShards", [])) != shard_ids
        or resume_plan.get("rejectionReasons")
    ):
        raise PromotionError("resume_identity_mismatch", "resume plan does not match the selected shard inventory")

    gates = execution_result.get("gates")
    planned_gates = risk_plan.get("gates", [])
    if (
        execution_result.get("schemaVersion") != validation_planner.RISK_SELECTION_SCHEMA
        or execution_result.get("status") != "passed"
        or execution_result.get("exitCode") != 0
        or not isinstance(gates, list)
        or [item.get("gateId") for item in gates if isinstance(item, dict)] != [item["id"] for item in planned_gates]
    ):
        raise PromotionError("validation_incomplete", "validation execution result is incomplete or unsuccessful")
    for planned, result in zip(planned_gates, gates, strict=True):
        if not isinstance(result, dict) or result.get("retries") != []:
            raise PromotionError("validation_retried", "validation evidence contains a retry or malformed gate")
        allowed_status = "passed" if planned["required"] else "not_applicable"
        if result.get("status") not in ({"passed", allowed_status} if not planned["required"] else {allowed_status}):
            raise PromotionError("validation_incomplete", f"required validation gate is not successful: {planned['id']}")

    identity = shard_result.get("executionIdentity")
    if not isinstance(identity, dict):
        raise PromotionError("validation_evidence_malformed", "shard execution identity is missing")
    evidence_candidate = identity.get("candidate")
    if evidence_candidate != risk_plan.get("identity", {}).get("candidate"):
        raise PromotionError("candidate_identity_mismatch", "validation candidate identities differ")
    risk_identity = risk_plan.get("identity", {})
    if (
        not isinstance(evidence_candidate, dict)
        or evidence_candidate.get("commitSha") != candidate.get("commitSha")
        or evidence_candidate.get("treeSha") != candidate.get("treeSha")
        or evidence_candidate.get("dirty") is not False
        or risk_identity.get("baseSha") != repository.get("acceptedBase")
        or risk_identity.get("candidateSha") != candidate.get("commitSha")
        or risk_identity.get("candidateRef") != repository.get("branch")
        or risk_identity.get("changeSource") != "committed"
        or risk_plan.get("changedFiles") != paths
    ):
        raise PromotionError("candidate_identity_mismatch", "promotion and validation candidate identities differ")
    if stage_plan.get("releaseReady") is not False:
        raise PromotionError("release_ready_semantics_invalid", "releaseReady must remain false in candidate validation")
    if validation.get("status") != "passed" or validation.get("firstAttempt") is not True or validation.get("retryCount") != 0:
        raise PromotionError("validation_incomplete", "validation summary is not a successful unretried first attempt")
    if validation.get("riskClass") != risk_plan.get("risk", {}).get("class") or validation.get("tier") != stage_plan.get("tier"):
        raise PromotionError("risk_or_stage_mismatch", "validation risk or stage tier does not match its plans")

    environment = identity.get("environment", {})
    dependency = identity.get("dependencyLock")
    dependency_fields = {"contentHash", "selectedLock", "selectedProjection", "selectedProjectionHash"}
    if (
        not isinstance(environment, dict)
        or set(environment) != {"fingerprint"}
        or not isinstance(dependency, dict)
        or set(dependency) != dependency_fields
    ):
        raise PromotionError("validation_evidence_malformed", "environment or dependency-lock identity is missing")
    _require_digest(dependency["contentHash"], "dependencyLock.contentHash")
    _require_digest(dependency["selectedProjectionHash"], "dependencyLock.selectedProjectionHash")
    _require_string(dependency["selectedLock"], "dependencyLock.selectedLock")
    _require_string(dependency["selectedProjection"], "dependencyLock.selectedProjection")
    command_identity = identity.get("command")
    if not isinstance(command_identity, dict):
        raise PromotionError("command_identity_mismatch", "command identity is missing")
    return VerifiedEvidence(
        evidence_path=evidence_path,
        evidence_sha256=_file_hash(evidence_path),
        accepted_base=_require_digest(repository["acceptedBase"], "acceptedBase", 40),
        candidate=_require_digest(candidate["commitSha"], "candidate.commitSha", 40),
        tree=_require_digest(candidate["treeSha"], "candidate.treeSha", 40),
        working_tree_sha256=_require_digest(
            evidence_candidate.get("workingTreeSha256"), "candidate.workingTreeSha256"
        ),
        parent=_require_digest(candidate["parentSha"], "candidate.parentSha", 40),
        subject=_require_string(candidate["subject"], "candidate.subject"),
        branch=_require_string(repository["branch"], "repository.branch"),
        patch_sha256=_require_digest(candidate["patchSha256"], "candidate.patchSha256"),
        changed_files=list(paths),
        changed_files_sha256=_require_digest(changed["sha256"], "changedFiles.sha256"),
        remote=_require_string(repository["remote"], "repository.remote"),
        remote_url=_require_string(repository["remoteUrl"], "repository.remoteUrl"),
        target_ref=_require_string(repository["targetRef"], "repository.targetRef"),
        environment_fingerprint=_require_digest(environment.get("fingerprint"), "environment.fingerprint"),
        dependency_lock=dict(dependency),
        risk_class=validation["riskClass"],
        tier=validation["tier"],
        release_ready=False,
        identities={
            "riskPlan": risk_plan["planHash"],
            "stagePlan": stage_plan["planHash"],
            "shardPlan": shard_plan["planHash"],
            "resumePlan": resume_plan["planHash"],
            "selection": risk_plan["identity"]["selectionSha256"],
            "topology": identity["topology"]["sha256"],
            "command": canonical_hash(command_identity),
            "shardResult": _file_hash(artifact_paths["shardSuiteResult"]),
        },
    )


class PromotionAuthority:
    def __init__(
        self,
        *,
        evidence_loader: Callable[[Path, Path], VerifiedEvidence] | None = None,
        environment_verify: Callable[[Path], EnvironmentIdentity | str] | None = None,
        lifecycle_factory: Callable[..., VerifiedWorktreeLifecycle] = VerifiedWorktreeLifecycle,
    ) -> None:
        self._evidence_loader = evidence_loader or _load_verified_evidence
        self._environment_verify = environment_verify or _default_environment_verify
        self._lifecycle_factory = lifecycle_factory
        self.before_push: Callable[[], None] | None = None
        self.after_push: Callable[[], None] | None = None

    def _preflight(self, worktree_value: Path, evidence_argument: Path) -> _Preflight:
        try:
            worktree = worktree_value.expanduser().resolve(strict=True)
        except OSError as exc:
            raise PromotionError("task_worktree_unavailable", "task worktree is unavailable") from exc
        evidence = self._evidence_loader(worktree, evidence_argument)
        if evidence.target_ref != TARGET_REF:
            raise PromotionError("target_ref_invalid", "only the canonical main ref may be promoted")
        if (
            REMOTE_NAME.fullmatch(evidence.remote) is None
            or evidence.remote.startswith("-")
            or ".." in evidence.remote
            or "@{" in evidence.remote
        ):
            raise PromotionError("remote_identity_invalid", "remote name is invalid")
        common_git_dir = _common_git_dir(worktree)
        records = _worktree_records(worktree)
        task_record = next((item for item in records if item["worktree"] == str(worktree)), None)
        if task_record is None:
            raise PromotionError("task_worktree_unregistered", "task worktree is not registered")
        if task_record.get("detached") is True or not isinstance(task_record.get("branch"), str):
            raise PromotionError("task_worktree_detached", "task worktree is detached")
        if task_record["branch"] != f"refs/heads/{evidence.branch}":
            raise PromotionError("branch_mismatch", "task worktree branch differs from validation evidence")
        main_records = [item for item in records if item.get("branch") == TARGET_REF]
        if len(main_records) != 1:
            raise PromotionError("canonical_main_registration_invalid", "canonical main worktree is missing or ambiguous")
        canonical = Path(main_records[0]["worktree"])
        if _common_git_dir(canonical) != common_git_dir:
            raise PromotionError("repository_identity_mismatch", "canonical and task worktrees do not share a Git common directory")
        if not _clean(canonical):
            raise PromotionError("canonical_main_dirty", "canonical main worktree is dirty")
        if not _clean(worktree):
            raise PromotionError("task_worktree_dirty", "task worktree is dirty")
        head = _git(worktree, ["rev-parse", "HEAD"])
        if head != evidence.candidate or task_record.get("HEAD") != evidence.candidate:
            raise PromotionError("candidate_mismatch", "task candidate differs from validation evidence")
        tree = _git(worktree, ["rev-parse", "HEAD^{tree}"])
        if tree != evidence.tree:
            raise PromotionError("tree_mismatch", "candidate tree differs from validation evidence")
        current_candidate = validation_planner._candidate_identity(worktree, evidence.candidate)
        if (
            current_candidate.get("workingTreeSha256") != evidence.working_tree_sha256
            or current_candidate.get("dirty") is not False
        ):
            raise PromotionError("candidate_worktree_mismatch", "candidate working-tree identity differs from validation evidence")
        parents = _git(worktree, ["show", "-s", "--format=%P", evidence.candidate]).split()
        if parents != [evidence.accepted_base] or evidence.parent != evidence.accepted_base:
            raise PromotionError("parent_mismatch", "candidate is not exactly one task commit over the accepted base")
        if _git(worktree, ["show", "-s", "--format=%s", evidence.candidate]) != evidence.subject:
            raise PromotionError("subject_mismatch", "candidate subject differs from validation evidence")
        if git_patch_hash(worktree, evidence.accepted_base, evidence.candidate) != evidence.patch_sha256:
            raise PromotionError("patch_mismatch", "candidate patch differs from validation evidence")
        changed_files = _changed_files(worktree, evidence.accepted_base, evidence.candidate)
        if changed_files != evidence.changed_files or canonical_hash(changed_files) != evidence.changed_files_sha256:
            raise PromotionError("changed_files_mismatch", "candidate changed-file inventory differs from validation evidence")
        remote_url = _git(worktree, ["remote", "get-url", evidence.remote], code="remote_identity_unavailable")
        if remote_url != evidence.remote_url:
            raise PromotionError("remote_identity_mismatch", "configured remote differs from validation evidence")
        observed_environment = self._environment_verify(worktree)
        if isinstance(observed_environment, str):
            observed_fingerprint = observed_environment
        else:
            observed_fingerprint = observed_environment.fingerprint
            if observed_environment.dependency_lock != evidence.dependency_lock:
                raise PromotionError("dependency_lock_mismatch", "current dependency lock differs from validation evidence")
        if observed_fingerprint != evidence.environment_fingerprint:
            raise PromotionError("environment_mismatch", "current environment differs from validation evidence")
        expected_remote = _remote_sha(worktree, evidence.remote, evidence.target_ref)
        local_main = _git(canonical, ["rev-parse", TARGET_REF])
        if local_main != expected_remote:
            raise PromotionError("local_main_remote_mismatch", "local main does not equal the requested remote ref")
        ancestor = subprocess.run(
            ["git", "-C", str(worktree), "merge-base", "--is-ancestor", expected_remote, evidence.candidate],
            capture_output=True,
            check=False,
        )
        if ancestor.returncode:
            raise PromotionError("candidate_not_fast_forward", "candidate is not a fast-forward from the remote ref")
        if expected_remote != evidence.accepted_base:
            raise PromotionError("accepted_base_remote_mismatch", "accepted base does not equal the remote ref")
        return _Preflight(canonical, worktree, common_git_dir, evidence, expected_remote)

    @staticmethod
    def _payload(operation: str, preflight: _Preflight | None = None) -> dict[str, Any]:
        evidence = preflight.evidence if preflight else None
        payload: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "operation": operation,
            "repository": {
                "canonicalPath": str(preflight.canonical) if preflight else None,
                "commonGitDir": str(preflight.common_git_dir) if preflight else None,
            },
            "worktree": {"path": str(preflight.worktree) if preflight else None, "registered": bool(preflight)},
            "branch": evidence.branch if evidence else None,
            "acceptedBase": evidence.accepted_base if evidence else None,
            "candidate": {
                "commitSha": evidence.candidate if evidence else None,
                "treeSha": evidence.tree if evidence else None,
                "workingTreeSha256": evidence.working_tree_sha256 if evidence else None,
                "parentSha": evidence.parent if evidence else None,
                "subject": evidence.subject if evidence else None,
            },
            "changedFiles": {
                "paths": evidence.changed_files if evidence else [],
                "sha256": evidence.changed_files_sha256 if evidence else None,
            },
            "patchSha256": evidence.patch_sha256 if evidence else None,
            "validationEvidence": {
                "path": str(evidence.evidence_path) if evidence else None,
                "sha256": evidence.evidence_sha256 if evidence else None,
                "riskClass": evidence.risk_class if evidence else None,
                "tier": evidence.tier if evidence else None,
                "releaseReady": evidence.release_ready if evidence else None,
                "identities": evidence.identities if evidence else {},
            },
            "environment": {"fingerprint": evidence.environment_fingerprint if evidence else None},
            "dependencyLock": evidence.dependency_lock if evidence else {},
            "remote": evidence.remote if evidence else None,
            "remoteUrl": evidence.remote_url if evidence else None,
            "targetRef": evidence.target_ref if evidence else None,
            "expectedRemoteSha": preflight.expected_remote if preflight else None,
            "planResult": {"status": "passed" if preflight else "refused"},
            "promotionResult": {"status": "not_evaluated" if operation == "plan" else "not_attempted"},
            "localMainUpdate": {"status": "not_requested"},
            "cleanupResult": {"status": "not_requested"},
            "refusalCode": None,
            "detail": None,
            "finalLocalSha": preflight.expected_remote if preflight else None,
            "finalRemoteSha": preflight.expected_remote if preflight else None,
        }
        return payload

    @staticmethod
    def _seal(payload: dict[str, Any], exit_code: int) -> PromotionResult:
        payload["resultHash"] = canonical_hash(payload)
        return PromotionResult(payload, exit_code)

    def _refusal(
        self,
        operation: str,
        error: PromotionError,
        preflight: _Preflight | None = None,
        payload: dict[str, Any] | None = None,
    ) -> PromotionResult:
        result = payload or self._payload(operation, preflight)
        result["refusalCode"] = error.code
        result["detail"] = error.detail.replace("\n", " ")[:240]
        if error.command_exit_code is not None:
            result["commandExitCode"] = error.command_exit_code
        return self._seal(result, 1)

    def plan(self, worktree: Path, evidence_path: Path) -> PromotionResult:
        try:
            preflight = self._preflight(worktree, evidence_path)
        except PromotionError as exc:
            return self._refusal("plan", exc)
        return self._seal(self._payload("plan", preflight), 0)

    def land(self, worktree: Path, evidence_path: Path) -> PromotionResult:
        try:
            preflight = self._preflight(worktree, evidence_path)
        except PromotionError as exc:
            return self._refusal("land", exc)
        payload = self._payload("land", preflight)
        evidence = preflight.evidence
        try:
            _run_git(
                preflight.worktree,
                ["fetch", "--no-tags", evidence.remote, evidence.target_ref],
                code="final_fetch_failed",
            )
            fetched = _git(preflight.worktree, ["rev-parse", "FETCH_HEAD"])
            if fetched != preflight.expected_remote:
                raise PromotionError("remote_moved_before_push", "remote ref moved before promotion")
            final_preflight = self._preflight(worktree, evidence_path)
            if final_preflight.evidence != evidence:
                raise PromotionError("validation_evidence_changed", "validation evidence changed before promotion")
            if final_preflight.expected_remote != preflight.expected_remote:
                raise PromotionError("remote_moved_before_push", "remote ref moved before promotion")
            if self.before_push is not None:
                self.before_push()
            if _remote_sha(preflight.worktree, evidence.remote, evidence.target_ref) != preflight.expected_remote:
                raise PromotionError("remote_moved_before_push", "remote ref moved before promotion")
            push = subprocess.run(
                [
                    "git",
                    "-C",
                    str(preflight.worktree),
                    "push",
                    "--atomic",
                    "--porcelain",
                    evidence.remote,
                    f"{evidence.candidate}:{evidence.target_ref}",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            if push.returncode:
                observed = _remote_sha(preflight.worktree, evidence.remote, evidence.target_ref)
                code = "remote_moved_during_promotion" if observed != preflight.expected_remote else "push_rejected"
                raise PromotionError(code, "exact remote promotion was rejected", command_exit_code=push.returncode)
            payload["promotionResult"] = {"status": "push_succeeded_verification_pending"}
            if self.after_push is not None:
                self.after_push()
            remote_after = _remote_sha(preflight.worktree, evidence.remote, evidence.target_ref)
            if remote_after != evidence.candidate:
                raise PromotionError("remote_result_mismatch", "remote ref does not equal the candidate after promotion")
            payload["promotionResult"] = {"status": "succeeded", "remoteSha": remote_after}
            payload["finalRemoteSha"] = remote_after
        except PromotionError as exc:
            if payload["promotionResult"].get("status") == "push_succeeded_verification_pending":
                payload["promotionResult"] = {"status": "push_succeeded_verification_incomplete"}
            else:
                payload["promotionResult"] = {"status": "refused"}
            return self._refusal("land", exc, preflight, payload)

        try:
            _run_git(
                preflight.worktree,
                ["fetch", "--no-tags", evidence.remote, evidence.target_ref],
                code="remote_result_fetch_failed",
            )
            if _git(preflight.worktree, ["rev-parse", "FETCH_HEAD"]) != evidence.candidate:
                raise PromotionError("remote_result_mismatch", "fetched remote result does not equal the candidate")
            _run_git(
                preflight.canonical,
                ["merge", "--ff-only", evidence.candidate],
                code="local_main_update_failed",
            )
            local_after = _git(preflight.canonical, ["rev-parse", TARGET_REF])
            if local_after != evidence.candidate:
                raise PromotionError("local_main_update_failed", "local main did not reach the candidate")
            payload["localMainUpdate"] = {"status": "succeeded", "localSha": local_after}
            payload["finalLocalSha"] = local_after
        except PromotionError as exc:
            payload["localMainUpdate"] = {"status": "failed"}
            return self._refusal("land", exc, preflight, payload)

        lifecycle = self._lifecycle_factory(environment_verify=lambda _path: evidence.environment_fingerprint)
        cleanup = lifecycle.cleanup(
            LifecycleRequest(
                repository=preflight.canonical,
                worktree=preflight.worktree,
                worktree_root=preflight.worktree.parent,
                branch=evidence.branch,
                accepted_base=evidence.accepted_base,
                candidate=evidence.candidate,
                environment_fingerprint=evidence.environment_fingerprint,
                validation_result="passed",
                land_result="succeeded",
                promotion_required=True,
                remote=evidence.remote_url,
                remote_ref=evidence.target_ref,
                delete_branch=True,
            )
        )
        payload["cleanupResult"] = {
            "status": "succeeded" if cleanup.exit_code == 0 else "refused",
            "authority": cleanup.payload,
        }
        if cleanup.exit_code:
            payload["refusalCode"] = "cleanup_authority_refused"
            payload["detail"] = "LAND succeeded, cleanup incomplete"
            return self._seal(payload, 1)
        return self._seal(payload, 0)


def _human(result: PromotionResult) -> str:
    payload = result.payload
    if payload["refusalCode"]:
        status = str(payload["promotionResult"].get("status", ""))
        if status.startswith("push_succeeded"):
            return f"LAND push succeeded, verification incomplete: {payload['refusalCode']}"
        if status.startswith("succeeded"):
            return f"LAND succeeded, cleanup incomplete: {payload['refusalCode']}"
        return f"REFUSED: {payload['refusalCode']}: {payload['detail']}"
    if payload["operation"] == "plan":
        return f"PLAN PASSED: {payload['candidate']['commitSha']} -> {payload['targetRef']}"
    return f"LAND SUCCEEDED: {payload['candidate']['commitSha']} -> {payload['targetRef']}"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic task promotion authority")
    subparsers = parser.add_subparsers(dest="operation", required=True)
    for operation in ("plan", "land"):
        command = subparsers.add_parser(operation)
        command.add_argument("--worktree", required=True, type=Path)
        command.add_argument("--validation-evidence", required=True, type=Path)
        command.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    authority = PromotionAuthority()
    result = getattr(authority, args.operation)(args.worktree, args.validation_evidence)
    print(canonical_bytes(result.payload).decode("utf-8") if args.json else _human(result))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
