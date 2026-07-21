#!/usr/bin/env python3
"""Collect changed files for conservative validation tiers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any, Callable, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_BASE_REF = (
    os.environ.get("VALIDATION_BASE_REF")
    or os.environ.get("CI_GATE_BASE_REF")
    or os.environ.get("RELEASE_SECRET_SCAN_BASE_REF")
    or "origin/main"
)
DEFAULT_DIFF_FILTER = "ACMRTUXB"
SHADOW_DIFF_FILTER = "ACDMRTUXB"
DEFAULT_OWNER_MANIFEST = Path("validation/validation_owners.json")
DEFAULT_TOPOLOGY_MANIFEST = Path("validation/domain_test_topology.json")
SHADOW_TIERS = (
    "direct_owner",
    "bounded_integration",
    "complete_domain",
    "browser_owned",
    "protected_baseline_comparison",
    "milestone",
    "release",
)

BINARY_SUFFIXES = {
    ".7z",
    ".avif",
    ".bz2",
    ".db",
    ".duckdb",
    ".eot",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp4",
    ".otf",
    ".parquet",
    ".pdf",
    ".pkl",
    ".png",
    ".pyc",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".tgz",
    ".ttf",
    ".webp",
    ".woff",
    ".woff2",
    ".xz",
    ".zip",
}

SKIPPED_PARTS = {
    ".cache",
    ".electron-builder-cache",
    ".git",
    ".next",
    ".pytest_cache",
    ".turbo",
    ".vite",
    ".venv",
    "__pycache__",
    "blob-report",
    "build",
    "coverage",
    "dist",
    "generated",
    "htmlcov",
    "node_modules",
    "playwright-report",
    "static",
    "test-results",
    "tmp",
    "vendor",
    "venv",
}

FRONTEND_LINT_SUFFIXES = {".cjs", ".js", ".jsx", ".mjs", ".ts", ".tsx"}
FRONTEND_RELATED_SUFFIXES = {".cjs", ".css", ".js", ".jsx", ".mjs", ".ts", ".tsx"}
DESIGN_SUFFIXES = {".css", ".ts", ".tsx"}
DOC_SUFFIXES = {".md", ".mdx", ".rst", ".txt", ".json", ".yml", ".yaml"}

PROTECTED_PREFIXES = (
    "api/",
    "data_provider/",
    "src/",
)
PROTECTED_PARTS = {
    "migrations",
}
PROTECTED_FRONTEND_PREFIXES = (
    "apps/dsa-web/src/api/",
    "apps/dsa-web/src/services/auth",
    "apps/dsa-web/src/stores/auth",
)
FULL_GATE_FILES = {
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.py",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}

RISK_CLASSES = ("R0", "R1", "R2", "R3", "R4", "R5")
RISK_SELECTION_SCHEMA = "wolfystock.validation-selection.v1"
RISK_SELECTOR_VERSION = "t631-r1"
RISK_GATE_FLOORS: dict[str, tuple[str, ...]] = {
    "R0": ("scope.diff", "security.changed"),
    "R1": ("syntax.changed", "tests.backend.changed", "tests.frontend.changed"),
    "R2": ("owners.affected", "consumers.affected"),
    "R3": ("contracts.cross_owner", "topology.verify", "security.branch"),
    "R4": ("protected.owners", "architecture.global", "backend.canonical", "browser.protected"),
    "R5": ("frontend.full", "browser.full", "uat.runtime", "release.real_runtime"),
}
RISK_GATE_ORDER = tuple(
    gate_id
    for risk_class in RISK_CLASSES
    for gate_id in RISK_GATE_FLOORS[risk_class]
)
RISK_GATE_MINIMUM = {
    gate_id: risk_class
    for risk_class in RISK_CLASSES
    for gate_id in RISK_GATE_FLOORS[risk_class]
}
RISK_GATE_EVIDENCE = {
    gate_id: "T630" if gate_id in {"owners.affected", "backend.canonical"} else "command"
    for gate_id in RISK_GATE_ORDER
}
RISK_GATE_CHANGE_PATHS = {
    "scripts/ci_gate.sh",
    "scripts/ci_gate_fast.sh",
    "scripts/validation_changed_files.py",
    "validation/validation_owners.json",
    "validation/domain_test_topology.json",
    "scripts/domain_test_topology.py",
}
BACKEND_STAGE_SCHEMA = "wolfystock.backend-validation-stages.v1"
BACKEND_VALIDATION_TIERS = ("canonical", "release")
BACKEND_RELEASE_ONLY_NODE_IDS = (
    "tests/test_operator_evidence_preflight.py::test_artifact_dir_mode_adds_local_workflow_check_without_approving_launch",
    "tests/test_operator_evidence_preflight.py::test_preflight_failure_summary_is_bounded_and_does_not_echo_command_output",
    "tests/test_operator_evidence_preflight.py::test_preflight_requires_synthetic_acknowledgement",
    "tests/test_operator_evidence_preflight.py::test_synthetic_preflight_passes_with_review_required_non_approval_summary",
    "tests/test_release_secret_scan.py::test_release_secret_scan_allows_checked_in_admin_auth_fixture",
    "tests/test_release_secret_scan.py::test_release_secret_scan_allows_env_example_placeholders",
    "tests/test_release_secret_scan.py::test_release_secret_scan_allows_frontend_e2e_state_placeholders",
    "tests/test_release_secret_scan.py::test_release_secret_scan_files_from_scans_only_listed_files",
    "tests/test_release_secret_scan.py::test_release_secret_scan_files_from_skips_generated_static_paths",
    "tests/test_release_secret_scan.py::test_release_secret_scan_flags_committed_branch_bearer_token",
    "tests/test_release_secret_scan.py::test_release_secret_scan_flags_frontend_e2e_api_key_assignment",
    "tests/test_release_secret_scan.py::test_release_secret_scan_flags_frontend_e2e_password_assignment",
    "tests/test_release_secret_scan.py::test_release_secret_scan_flags_staged_password_assignment",
    "tests/test_release_secret_scan.py::test_release_secret_scan_flags_worktree_api_key",
    "tests/test_release_secret_scan.py::test_release_secret_scan_local_only_skips_committed_branch_changes",
    "tests/test_release_secret_scan.py::test_release_secret_scan_rejects_credentials_inside_candidate_archive",
    "tests/test_release_secret_scan.py::test_release_secret_scan_rejects_private_paths_in_generated_evidence",
    "tests/test_release_secret_scan.py::test_release_secret_scan_treats_only_topology_test_ids_as_reviewed_fixture_data",
)
BACKEND_RELEASE_STAGE_EXACT_TRIGGERS = {
    ".github/workflows/release.yml",
    "scripts/ci_gate.sh",
    "scripts/ci_gate_fast.sh",
    "scripts/domain_test_topology.py",
    "scripts/validation_changed_files.py",
    "tests/conftest.py",
    "tests/scripts/test_domain_test_topology.py",
    "tests/scripts/test_validation_owner_planner.py",
    "validation/domain_test_topology.json",
    "validation/validation_owners.json",
}
BACKEND_RELEASE_STAGE_PREFIX_TRIGGERS = (
    "scripts/operator_evidence_",
    "scripts/release_",
    "src/runtime/",
    "tests/test_operator_evidence_",
    "tests/test_release_",
)


class SelectionError(ValueError):
    """Raised when a risk plan or structured result cannot be trusted."""


def run_git(args: list[str], *, root: Path = ROOT, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=check,
    )


def git_lines(args: list[str], *, root: Path = ROOT) -> list[str]:
    result = run_git(args, root=root)
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def base_ref_available(base_ref: str) -> bool:
    return run_git(["rev-parse", "--verify", base_ref]).returncode == 0


def normalize_path(value: str, *, root: Path = ROOT) -> str | None:
    raw = value.strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute():
        try:
            raw = path.resolve().relative_to(root).as_posix()
        except ValueError:
            return None
    raw = raw.replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    if raw in {"", "."} or raw.startswith("../") or "/../" in raw:
        return None
    return raw


def unique_sorted(paths: Iterable[str]) -> list[str]:
    return sorted({path for path in paths if path})


def has_skipped_part(path: str) -> bool:
    parts = set(path.split("/"))
    return bool(parts & SKIPPED_PARTS)


def is_generated_static_binary_or_cache(path: str) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in BINARY_SUFFIXES or has_skipped_part(path)


def path_exists(path: str, *, root: Path = ROOT) -> bool:
    return (root / path).is_file()


def is_frontend_path(path: str) -> bool:
    return path.startswith("apps/dsa-web/")


def is_python_path(path: str) -> bool:
    return path.endswith(".py")


def is_doc_path(path: str) -> bool:
    return path.startswith("docs/") or Path(path).suffix.lower() in DOC_SUFFIXES


def scope_allows(path: str, scope: str) -> bool:
    if is_generated_static_binary_or_cache(path):
        return False
    suffix = Path(path).suffix.lower()
    if scope in {"all", "secret"}:
        return True
    if scope == "frontend":
        return is_frontend_path(path)
    if scope == "frontend-lint":
        return is_frontend_path(path) and suffix in FRONTEND_LINT_SUFFIXES
    if scope == "frontend-related":
        return is_frontend_path(path) and suffix in FRONTEND_RELATED_SUFFIXES
    if scope == "design":
        return path.startswith("apps/dsa-web/src/") and suffix in DESIGN_SUFFIXES
    if scope == "python":
        return is_python_path(path)
    if scope == "docs":
        return is_doc_path(path)
    raise ValueError(f"unknown scope: {scope}")


def read_files_from(path: str, *, root: Path = ROOT) -> list[str]:
    if path == "-":
        return [line for line in sys.stdin.read().splitlines() if line.strip()]
    content_path = Path(path)
    if not content_path.is_absolute():
        content_path = root / content_path
    return content_path.read_text(encoding="utf-8").splitlines()


def collect_raw(mode: str, base_ref: str, diff_filter: str) -> dict[str, list[str] | bool]:
    branch: list[str] = []
    local_staged: list[str] = []
    local_worktree: list[str] = []
    local_untracked: list[str] = []
    base_available = base_ref_available(base_ref)

    if mode in {"all", "active", "branch", "branch-release"}:
        if base_available:
            separator = ".." if mode == "branch-release" else "..."
            branch = git_lines(["diff", "--name-only", f"--diff-filter={diff_filter}", f"{base_ref}{separator}HEAD"])
        else:
            print(f"[WARN] base ref not available: {base_ref}", file=sys.stderr)

    if mode in {"all", "active", "local", "staged"}:
        local_staged = git_lines(["diff", "--cached", "--name-only", f"--diff-filter={diff_filter}"])
    if mode in {"all", "active", "local", "worktree"}:
        local_worktree = git_lines(["diff", "--name-only", f"--diff-filter={diff_filter}"])
    if mode in {"all", "active", "local", "untracked"}:
        local_untracked = git_lines(["ls-files", "--others", "--exclude-standard"])

    local = unique_sorted([*local_staged, *local_worktree, *local_untracked])
    if mode == "active":
        selected = local if local else branch
    elif mode == "local":
        selected = local
    elif mode == "staged":
        selected = local_staged
    elif mode == "worktree":
        selected = local_worktree
    elif mode == "untracked":
        selected = local_untracked
    elif mode in {"branch", "branch-release"}:
        selected = branch
    else:
        selected = [*branch, *local]

    return {
        "baseRefAvailable": base_available,
        "branchFiles": unique_sorted(normalize_path(path) or "" for path in branch),
        "stagedFiles": unique_sorted(normalize_path(path) or "" for path in local_staged),
        "worktreeFiles": unique_sorted(normalize_path(path) or "" for path in local_worktree),
        "untrackedFiles": unique_sorted(normalize_path(path) or "" for path in local_untracked),
        "localFiles": unique_sorted(normalize_path(path) or "" for path in local),
        "selectedFiles": unique_sorted(normalize_path(path) or "" for path in selected),
    }


def is_protected_domain(path: str) -> bool:
    parts = set(path.split("/"))
    if parts & PROTECTED_PARTS:
        return True
    return path.startswith(PROTECTED_PREFIXES) or path.startswith(PROTECTED_FRONTEND_PREFIXES)


def needs_full_gate(path: str) -> bool:
    if path in FULL_GATE_FILES or Path(path).name in FULL_GATE_FILES:
        return True
    if path.startswith(".github/workflows/"):
        return True
    if path.endswith("-lock.json") or path.endswith(".lock"):
        return True
    return False


def is_known_validation_path(path: str) -> bool:
    if is_doc_path(path):
        return True
    if path.startswith("scripts/"):
        return True
    if path.startswith("tests/"):
        return True
    if path.startswith("apps/dsa-web/"):
        return True
    if path in {"AGENTS.md", "CLAUDE.md"}:
        return True
    return False


def classify(files: list[str], *, root: Path = ROOT) -> dict[str, object]:
    """Return collector-only metadata; validation gates use the risk plan below."""
    protected_files = [path for path in files if is_protected_domain(path)]
    full_gate_files = [path for path in files if needs_full_gate(path)]
    unknown_files = [path for path in files if not is_known_validation_path(path)]
    frontend_files = [path for path in files if is_frontend_path(path)]
    frontend_shared = [
        path
        for path in frontend_files
        if path.startswith(
            (
                "apps/dsa-web/src/components/",
                "apps/dsa-web/src/hooks/",
                "apps/dsa-web/src/lib/",
                "apps/dsa-web/src/styles/",
                "apps/dsa-web/src/utils/",
            )
        )
    ]
    backend_report_files = [
        path
        for path in files
        if path.startswith(("src/services/report", "src/schemas/report", "tests/"))
        and ("report" in path.lower() or "renderer" in path.lower())
    ]

    if protected_files:
        tier = "protected-domain"
    elif full_gate_files or unknown_files:
        tier = "full-gate"
    elif backend_report_files:
        tier = "backend-report"
    elif frontend_shared:
        tier = "frontend-shared"
    elif frontend_files:
        tier = "frontend-component"
    elif all(is_doc_path(path) for path in files) if files else False:
        tier = "copy-only"
    else:
        tier = "script-doc"

    return {
        "tier": tier,
        "hasFrontend": bool(frontend_files),
        "hasFrontendShared": bool(frontend_shared),
        "hasPython": any(is_python_path(path) for path in files),
        "hasDocs": any(is_doc_path(path) for path in files),
        "hasProtectedDomain": bool(protected_files),
        "hasFullGateRisk": bool(full_gate_files),
        "hasUnknown": bool(unknown_files),
        "protectedFiles": protected_files,
        "fullGateFiles": full_gate_files,
        "unknownFiles": unknown_files,
        "frontendFiles": frontend_files,
        "frontendSharedFiles": frontend_shared,
        "backendReportFiles": backend_report_files,
    }


class OwnerManifestError(ValueError):
    """Raised when the shadow owner manifest cannot fail closed."""


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def stable_hash(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_path(path: Path, *, root: Path) -> Path:
    return path if path.is_absolute() else root / path


def load_owner_manifest(path: Path = DEFAULT_OWNER_MANIFEST, *, root: Path = ROOT) -> tuple[dict[str, Any], str]:
    resolved = manifest_path(path, root=root)
    try:
        raw = resolved.read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OwnerManifestError(f"cannot load owner manifest {resolved}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise OwnerManifestError("owner manifest root must be an object")
    return manifest, hashlib.sha256(raw).hexdigest()


def glob_regex(pattern: str) -> re.Pattern[str]:
    """Compile a small, path-separator-aware glob used by the JSON manifest."""

    pieces = ["^"]
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                index += 2
                if index < len(pattern) and pattern[index] == "/":
                    pieces.append("(?:.*/)?")
                    index += 1
                else:
                    pieces.append(".*")
                continue
            pieces.append("[^/]*")
        elif char == "?":
            pieces.append("[^/]")
        else:
            pieces.append(re.escape(char))
        index += 1
    pieces.append("$")
    return re.compile("".join(pieces))


def path_matches(path: str, pattern: str) -> bool:
    return bool(glob_regex(pattern).match(path))


def matching_rules(path: str, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for rule in manifest["rules"]:
        included = any(path_matches(path, pattern) for pattern in rule["include"])
        excluded = any(path_matches(path, pattern) for pattern in rule.get("exclude", []))
        if included and not excluded:
            matches.append(rule)
    return sorted(matches, key=lambda item: item["id"])


def target_matches(root: Path, pattern: str) -> list[str]:
    wildcard_at = min((pattern.find(char) for char in "*?" if char in pattern), default=len(pattern))
    prefix = pattern[:wildcard_at].rsplit("/", 1)[0] if wildcard_at < len(pattern) else pattern
    if wildcard_at == len(pattern):
        candidate = root / pattern
        return [pattern] if candidate.is_file() else []

    search_root = root / prefix if prefix else root
    if not search_root.is_dir():
        return []
    matches: list[str] = []
    for candidate in search_root.rglob("*"):
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(root).as_posix()
        if path_matches(relative, pattern):
            matches.append(relative)
    return sorted(matches)


def validate_owner_manifest(
    manifest: dict[str, Any],
    *,
    root: Path = ROOT,
    manifest_hash: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    if manifest.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    if not isinstance(manifest.get("manifestVersion"), str) or not manifest["manifestVersion"]:
        errors.append("manifestVersion must be a non-empty string")
    if manifest.get("shadowOnly") is not True:
        errors.append("shadowOnly must be true")
    if tuple(manifest.get("tierOrder", [])) != SHADOW_TIERS:
        errors.append(f"tierOrder must be {list(SHADOW_TIERS)}")

    owners = manifest.get("owners")
    rules = manifest.get("rules")
    if not isinstance(owners, dict) or not owners:
        errors.append("owners must be a non-empty object")
        owners = {}
    if not isinstance(rules, list) or not rules:
        errors.append("rules must be a non-empty array")
        rules = []

    resolved_targets: dict[str, list[str]] = {}
    for owner_id, owner in sorted(owners.items()):
        if not isinstance(owner, dict):
            errors.append(f"owner {owner_id} must be an object")
            continue
        if owner.get("tier") not in SHADOW_TIERS:
            errors.append(f"owner {owner_id} has invalid tier {owner.get('tier')!r}")
        kind = owner.get("kind")
        if kind not in {"command", "command_template", "npm_script", "owner_identifier"}:
            errors.append(f"owner {owner_id} has invalid kind {kind!r}")
        if kind in {"command", "command_template", "npm_script"}:
            command = owner.get("command")
            if not isinstance(command, list) or not command or not all(isinstance(token, str) for token in command):
                errors.append(f"owner {owner_id} must define a non-empty string command array")
        if kind == "owner_identifier" and not owner.get("identifier"):
            errors.append(f"owner {owner_id} must define identifier")

        owner_targets: list[str] = []
        for target in owner.get("targets", []):
            if not isinstance(target, str) or not target:
                errors.append(f"owner {owner_id} contains an invalid target")
                continue
            matches = target_matches(root, target)
            if not matches:
                errors.append(f"owner {owner_id} target cannot be listed: {target}")
            owner_targets.extend(matches)
        resolved_targets[owner_id] = unique_sorted(owner_targets)

        if kind == "npm_script":
            package_path = owner.get("package")
            script = owner.get("script")
            if not isinstance(package_path, str) or not isinstance(script, str):
                errors.append(f"owner {owner_id} must define package and script")
            else:
                try:
                    package = json.loads((root / package_path).read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    errors.append(f"owner {owner_id} package cannot be loaded: {exc}")
                else:
                    if script not in package.get("scripts", {}):
                        errors.append(f"owner {owner_id} npm script does not exist: {script}")

    rule_ids: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            errors.append("each rule must be an object")
            continue
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id:
            errors.append("each rule must have a non-empty id")
            continue
        if rule_id in rule_ids:
            errors.append(f"duplicate rule id: {rule_id}")
        rule_ids.add(rule_id)
        includes = rule.get("include")
        if not isinstance(includes, list) or not includes or not all(isinstance(item, str) for item in includes):
            errors.append(f"rule {rule_id} must define include patterns")
        rule_owners = rule.get("owners")
        if not isinstance(rule_owners, dict) or not rule_owners:
            errors.append(f"rule {rule_id} must define owners")
            continue
        for tier, owner_ids in rule_owners.items():
            if tier not in SHADOW_TIERS or not isinstance(owner_ids, list) or not owner_ids:
                errors.append(f"rule {rule_id} has invalid owner tier {tier}")
                continue
            for owner_id in owner_ids:
                if owner_id not in owners:
                    errors.append(f"rule {rule_id} references nonexistent owner {owner_id}")
                elif owners[owner_id].get("tier") != tier:
                    errors.append(f"rule {rule_id} places owner {owner_id} in the wrong tier")
        if rule.get("protected"):
            if not rule.get("reason"):
                errors.append(f"protected rule {rule_id} must define a reason")
            for tier in ("protected_baseline_comparison", "milestone", "release"):
                if tier not in rule_owners:
                    errors.append(f"protected rule {rule_id} must escalate to {tier}")

    unknown = manifest.get("unknownEscalation")
    if not isinstance(unknown, dict) or not unknown.get("reason"):
        errors.append("unknownEscalation must define a reason")
    else:
        unknown_owners = unknown.get("owners", [])
        unknown_tiers = {owners[owner_id]["tier"] for owner_id in unknown_owners if owner_id in owners}
        for owner_id in unknown_owners:
            if owner_id not in owners:
                errors.append(f"unknownEscalation references nonexistent owner {owner_id}")
        for tier in ("protected_baseline_comparison", "milestone", "release"):
            if tier not in unknown_tiers:
                errors.append(f"unknownEscalation must include a {tier} owner")

    overflow = manifest.get("ownerOverflow")
    if not isinstance(overflow, dict):
        errors.append("ownerOverflow must be an object")
    else:
        for tier, policy in overflow.items():
            if tier not in SHADOW_TIERS or not isinstance(policy, dict):
                errors.append(f"invalid overflow policy for {tier}")
                continue
            if not isinstance(policy.get("maxOwners"), int) or policy["maxOwners"] < 1:
                errors.append(f"overflow policy {tier} must define positive maxOwners")
            if not policy.get("reason"):
                errors.append(f"overflow policy {tier} must define a reason")
            for owner_id in policy.get("owners", []):
                if owner_id not in owners:
                    errors.append(f"overflow policy {tier} references nonexistent owner {owner_id}")

    if errors:
        raise OwnerManifestError("; ".join(errors))
    return {
        "schemaVersion": manifest["schemaVersion"],
        "manifestVersion": manifest["manifestVersion"],
        "manifestHash": manifest_hash or stable_hash(manifest),
        "ownerCount": len(owners),
        "ruleCount": len(rules),
        "resolvedTargets": {key: value for key, value in resolved_targets.items() if value},
        "status": "valid",
    }


def run_git_bytes(args: list[str], *, root: Path = ROOT) -> bytes:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True)
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise OwnerManifestError(f"git {' '.join(args)} failed: {message}")
    return result.stdout


def resolve_git_ref(ref: str, *, root: Path = ROOT) -> str:
    result = run_git(["rev-parse", "--verify", f"{ref}^{{commit}}"], root=root)
    if result.returncode != 0:
        raise OwnerManifestError(f"git ref is not available: {ref}")
    return result.stdout.strip()


def decode_z_paths(raw: bytes) -> list[str]:
    text = raw.decode("utf-8", errors="surrogateescape")
    parts = text.split("\0")
    if parts and parts[-1] == "":
        parts.pop()
    return parts


def observation(
    path: str,
    *,
    source: str,
    status: str,
    change_type: str,
    ownership_tree: str,
    paired_path: str | None = None,
) -> dict[str, str]:
    item = {
        "path": path,
        "source": source,
        "status": status,
        "changeType": change_type,
        "ownershipTree": ownership_tree,
    }
    if paired_path is not None:
        item["pairedPath"] = paired_path
    return item


def parse_name_status(raw: bytes, *, source: str) -> list[dict[str, str]]:
    parts = decode_z_paths(raw)
    observations: list[dict[str, str]] = []
    index = 0
    simple_types = {
        "A": "added",
        "B": "broken_pair",
        "D": "deleted",
        "M": "modified",
        "T": "type_changed",
        "U": "unmerged",
        "X": "unknown_git_status",
    }
    while index < len(parts):
        status = parts[index]
        index += 1
        code = status[:1]
        if code in {"R", "C"}:
            if index + 1 >= len(parts):
                raise OwnerManifestError(f"incomplete {status} record from {source}")
            old_path = normalize_path(parts[index])
            new_path = normalize_path(parts[index + 1])
            index += 2
            if old_path is None or new_path is None:
                raise OwnerManifestError(f"invalid path in {status} record from {source}")
            source_type = "rename_source" if code == "R" else "copy_source"
            destination_type = "rename_destination" if code == "R" else "copy_destination"
            source_tree = "base" if source == "committed" else ("head" if source == "staged" else "index")
            destination_tree = "candidate" if source == "committed" else ("index" if source == "staged" else "worktree")
            observations.append(
                observation(
                    old_path,
                    source=source,
                    status=status,
                    change_type=source_type,
                    ownership_tree=source_tree,
                    paired_path=new_path,
                )
            )
            observations.append(
                observation(
                    new_path,
                    source=source,
                    status=status,
                    change_type=destination_type,
                    ownership_tree=destination_tree,
                    paired_path=old_path,
                )
            )
            continue

        if code not in simple_types or index >= len(parts):
            raise OwnerManifestError(f"unsupported or incomplete git status {status!r} from {source}")
        path = normalize_path(parts[index])
        index += 1
        if path is None:
            raise OwnerManifestError(f"invalid path in {status} record from {source}")
        if code == "D":
            tree = "base" if source == "committed" else ("head" if source == "staged" else "index")
        elif code == "A":
            tree = "candidate" if source == "committed" else ("index" if source == "staged" else "worktree")
        else:
            tree = "base_and_candidate" if source == "committed" else (
                "head_and_index" if source == "staged" else "index_and_worktree"
            )
        observations.append(
            observation(
                path,
                source=source,
                status=status,
                change_type=simple_types[code],
                ownership_tree=tree,
            )
        )
    return observations


def collect_shadow_observations(
    base_ref: str,
    candidate_ref: str,
    *,
    root: Path = ROOT,
    change_source: str = "union",
) -> tuple[list[dict[str, str]], str, str]:
    base_sha = resolve_git_ref(base_ref, root=root)
    candidate_sha = resolve_git_ref(candidate_ref, root=root)
    diff_args = [
        "diff",
        "--name-status",
        "-z",
        "--find-renames",
        "--find-copies",
        "--find-copies-harder",
        f"--diff-filter={SHADOW_DIFF_FILTER}",
        base_sha,
        candidate_sha,
    ]
    observations = parse_name_status(run_git_bytes(diff_args, root=root), source="committed")
    if change_source == "committed":
        return observations, base_sha, candidate_sha
    if change_source != "union":
        raise OwnerManifestError(f"unknown shadow change source: {change_source}")
    head_sha = resolve_git_ref("HEAD", root=root)
    if candidate_sha != head_sha:
        raise OwnerManifestError("union shadow plans require --candidate HEAD; use committed mode for historical candidates")

    staged_args = [
        "diff",
        "--cached",
        "--name-status",
        "-z",
        "--find-renames",
        "--find-copies",
        "--find-copies-harder",
        f"--diff-filter={SHADOW_DIFF_FILTER}",
    ]
    unstaged_args = [
        "diff",
        "--name-status",
        "-z",
        "--find-renames",
        "--find-copies",
        "--find-copies-harder",
        f"--diff-filter={SHADOW_DIFF_FILTER}",
    ]
    observations.extend(parse_name_status(run_git_bytes(staged_args, root=root), source="staged"))
    observations.extend(parse_name_status(run_git_bytes(unstaged_args, root=root), source="unstaged"))
    for path in decode_z_paths(run_git_bytes(["ls-files", "--others", "--exclude-standard", "-z"], root=root)):
        normalized = normalize_path(path, root=root)
        if normalized is None:
            raise OwnerManifestError(f"invalid untracked path: {path!r}")
        observations.append(
            observation(
                normalized,
                source="untracked",
                status="?",
                change_type="untracked",
                ownership_tree="worktree",
            )
        )
    return observations, base_sha, candidate_sha


def aggregate_observations(observations: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_path: dict[str, list[dict[str, str]]] = {}
    for item in observations:
        by_path.setdefault(item["path"], []).append(item)
    changes: list[dict[str, Any]] = []
    for path, items in sorted(by_path.items()):
        ordered = sorted(
            items,
            key=lambda item: (
                item["source"],
                item["changeType"],
                item["status"],
                item.get("pairedPath", ""),
            ),
        )
        changes.append(
            {
                "path": path,
                "changeTypes": unique_sorted(item["changeType"] for item in ordered),
                "sources": unique_sorted(item["source"] for item in ordered),
                "ownershipTrees": unique_sorted(item["ownershipTree"] for item in ordered),
                "observations": ordered,
            }
        )
    return changes


def infer_related_pytests(path: str, *, root: Path = ROOT) -> list[str]:
    if not path.endswith(".py") or path.startswith("tests/"):
        return []
    stem = Path(path).stem
    patterns = (
        f"test_{stem}.py",
        f"test_{stem}_*.py",
        f"*_{stem}.py",
        f"*{stem}*_test.py",
    )
    matches: set[str] = set()
    tests_root = root / "tests"
    if not tests_root.is_dir():
        return []
    for pattern in patterns:
        for candidate in tests_root.rglob(pattern):
            if candidate.is_file():
                matches.add(candidate.relative_to(root).as_posix())
    return sorted(matches)


def owner_ids_for_rules(rules: list[dict[str, Any]]) -> list[str]:
    owner_ids: set[str] = set()
    for rule in rules:
        for tier_owners in rule["owners"].values():
            owner_ids.update(tier_owners)
    return sorted(owner_ids)


def expand_command(
    command: list[str],
    *,
    expansions: dict[str, list[str]],
) -> tuple[list[str] | None, str | None]:
    rendered: list[str] = []
    missing: list[str] = []
    for token in command:
        if token.startswith("{") and token.endswith("}"):
            values = expansions.get(token[1:-1])
            if not values:
                missing.append(token)
            else:
                rendered.extend(values)
        else:
            rendered.append(token)
    if missing:
        return None, f"no concrete paths for {', '.join(missing)}"
    return rendered, None


def render_owner(
    owner_id: str,
    owner: dict[str, Any],
    *,
    root: Path,
    expansions: dict[str, list[str]],
) -> dict[str, Any]:
    rendered: dict[str, Any] = {
        "id": owner_id,
        "kind": owner["kind"],
        "tier": owner["tier"],
    }
    if owner.get("identifier"):
        rendered["identifier"] = owner["identifier"]
    targets: list[str] = []
    for pattern in owner.get("targets", []):
        targets.extend(target_matches(root, pattern))
    targets = unique_sorted(targets)
    if targets:
        rendered["targets"] = targets
    if owner.get("inferenceOnly"):
        rendered["inferenceOnly"] = True
    if "command" in owner:
        owner_expansions = dict(expansions)
        owner_expansions["owner_targets"] = targets
        command, unavailable_reason = expand_command(owner["command"], expansions=owner_expansions)
        if command is not None:
            rendered["command"] = command
        else:
            rendered["commandTemplate"] = owner["command"]
            rendered["commandUnavailableReason"] = unavailable_reason
    return rendered


def apply_owner_overflow(
    owner_ids: set[str],
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    owners = manifest["owners"]
    escalations: list[dict[str, Any]] = []
    for tier in SHADOW_TIERS:
        policy = manifest.get("ownerOverflow", {}).get(tier)
        if not policy:
            continue
        tier_count = sum(1 for owner_id in owner_ids if owners[owner_id]["tier"] == tier)
        if tier_count <= policy["maxOwners"]:
            continue
        escalation_owners = sorted(policy["owners"])
        owner_ids.update(escalation_owners)
        escalations.append(
            {
                "tier": tier,
                "ownerCount": tier_count,
                "maxOwners": policy["maxOwners"],
                "reason": policy["reason"],
                "addedOwners": escalation_owners,
                "ownersRetained": True,
            }
        )
    return escalations


def build_shadow_plan_from_changes(
    changes: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    root: Path = ROOT,
    base_ref: str,
    base_sha: str,
    candidate_ref: str,
    candidate_sha: str,
    change_source: str,
    manifest_hash: str,
    manifest_file: str = "validation/validation_owners.json",
) -> dict[str, Any]:
    owners = manifest["owners"]
    unknown_escalation = manifest["unknownEscalation"]
    all_owner_ids: set[str] = set()
    unknown_paths: list[str] = []
    protected_paths: list[str] = []
    related_pytests: set[str] = set()
    planned_changes: list[dict[str, Any]] = []

    for change in sorted(changes, key=lambda item: item["path"]):
        path = change["path"]
        rules = matching_rules(path, manifest)
        rule_owner_ids = set(owner_ids_for_rules(rules))
        inferred_targets = infer_related_pytests(path, root=root)
        inferred_owner_ids: list[str] = []
        if inferred_targets:
            inferred_owner_ids.append("direct.pytest.related_inference")
            related_pytests.update(inferred_targets)

        escalation_reasons = unique_sorted(
            rule["reason"] for rule in rules if rule.get("protected") and rule.get("reason")
        )
        if any(rule.get("protected") for rule in rules):
            protected_paths.append(path)
        if not rules:
            unknown_paths.append(path)
            rule_owner_ids.update(unknown_escalation["owners"])
            escalation_reasons.append(unknown_escalation["reason"])

        path_owner_ids = rule_owner_ids | set(inferred_owner_ids)
        all_owner_ids.update(path_owner_ids)
        selected_tiers = sorted(
            {owners[owner_id]["tier"] for owner_id in path_owner_ids},
            key=SHADOW_TIERS.index,
        )
        planned_change = dict(change)
        planned_change.update(
            {
                "matchedRules": [rule["id"] for rule in rules],
                "selectedTiers": selected_tiers,
                "ownerIds": sorted(path_owner_ids),
                "escalationReasons": unique_sorted(escalation_reasons),
                "authoritySource": "manifest_rule" if rules else "explicit_unknown_escalation",
            }
        )
        if inferred_owner_ids:
            planned_change["inferredOwners"] = inferred_owner_ids
            planned_change["inferredOwnerTargets"] = inferred_targets
        planned_changes.append(planned_change)

    overflow_escalations = apply_owner_overflow(all_owner_ids, manifest)
    changed_paths = [change["path"] for change in planned_changes]
    non_runnable_change_types = {"deleted", "rename_source"}
    runnable_paths = {
        change["path"]
        for change in planned_changes
        if not set(change["changeTypes"]).issubset(non_runnable_change_types)
    }
    expansions = {
        "changed_existing_python_paths": [
            path for path in changed_paths if path.endswith(".py") and path in runnable_paths
        ],
        "changed_pytest_paths": [
            path
            for path in changed_paths
            if path.startswith("tests/") and path.endswith(".py") and path in runnable_paths
        ],
        "related_pytest_paths": sorted(related_pytests),
        "changed_existing_web_source_paths": [
            path.removeprefix("apps/dsa-web/")
            for path in changed_paths
            if path.startswith("apps/dsa-web/")
            and Path(path).suffix.lower() in FRONTEND_RELATED_SUFFIXES
            and path in runnable_paths
        ],
        "changed_browser_specs": [
            path.removeprefix("apps/dsa-web/")
            for path in changed_paths
            if path.startswith("apps/dsa-web/e2e/")
            and path.endswith((".spec.ts", ".spec.tsx"))
            and path in runnable_paths
        ],
    }
    rendered_owners = [
        render_owner(owner_id, owners[owner_id], root=root, expansions=expansions)
        for owner_id in sorted(all_owner_ids, key=lambda item: (SHADOW_TIERS.index(owners[item]["tier"]), item))
    ]
    selected_tiers = [tier for tier in SHADOW_TIERS if any(owner["tier"] == tier for owner in rendered_owners)]
    plan = {
        "schemaVersion": 1,
        "shadowOnly": True,
        "authoritativeGateUnchanged": True,
        "identity": {
            "baseRef": base_ref,
            "baseSha": base_sha,
            "candidateRef": candidate_ref,
            "candidateSha": candidate_sha,
            "changeSource": change_source,
        },
        "manifest": {
            "path": manifest_file,
            "version": manifest["manifestVersion"],
            "hash": manifest_hash,
        },
        "changes": planned_changes,
        "changedPaths": changed_paths,
        "selectedTiers": selected_tiers,
        "owners": rendered_owners,
        "unknownPaths": sorted(unknown_paths),
        "protectedPaths": sorted(protected_paths),
        "escalations": overflow_escalations,
        "ownerListsTruncated": False,
    }
    plan["planHash"] = stable_hash(plan)
    return plan


def build_shadow_plan(
    base_ref: str,
    candidate_ref: str,
    manifest: dict[str, Any],
    *,
    root: Path = ROOT,
    change_source: str = "union",
    manifest_hash: str,
    manifest_file: str = "validation/validation_owners.json",
) -> dict[str, Any]:
    observations, base_sha, candidate_sha = collect_shadow_observations(
        base_ref,
        candidate_ref,
        root=root,
        change_source=change_source,
    )
    return build_shadow_plan_from_changes(
        aggregate_observations(observations),
        manifest,
        root=root,
        base_ref=base_ref,
        base_sha=base_sha,
        candidate_ref=candidate_ref,
        candidate_sha=candidate_sha,
        change_source=change_source,
        manifest_hash=manifest_hash,
        manifest_file=manifest_file,
    )


def _risk_index(risk_class: str) -> int:
    try:
        return RISK_CLASSES.index(risk_class)
    except ValueError as exc:
        raise SelectionError(f"invalid risk class: {risk_class}") from exc


def _max_risk(*risk_classes: str) -> str:
    return max(risk_classes, key=_risk_index, default="R0")


def _candidate_identity(root: Path, candidate_ref: str) -> dict[str, Any]:
    commit = resolve_git_ref(candidate_ref, root=root)
    tree = run_git(["rev-parse", f"{commit}^{{tree}}"], root=root).stdout.strip()
    if not tree:
        raise SelectionError(f"candidate tree identity is unavailable: {candidate_ref}")
    status = run_git(["status", "--porcelain", "--untracked-files=all"], root=root)
    if status.returncode:
        raise SelectionError("candidate working-tree identity is unavailable")
    digest = hashlib.sha256()
    for raw_path in sorted(run_git_bytes(["ls-files", "--cached", "--others", "--exclude-standard", "-z"], root=root).split(b"\0")):
        if not raw_path:
            continue
        relative = raw_path.decode("utf-8", errors="surrogateescape")
        path = root / relative
        digest.update(raw_path)
        digest.update(b"\0")
        if path.is_symlink():
            digest.update(b"symlink\0")
            digest.update(os.readlink(path).encode("utf-8", errors="surrogateescape"))
        elif path.is_file():
            digest.update(b"executable\0" if os.access(path, os.X_OK) else b"file\0")
            digest.update(file_hash(path).encode("ascii"))
        else:
            digest.update(b"missing\0")
        digest.update(b"\0")
    return {
        "commitSha": commit,
        "treeSha": tree,
        "workingTreeSha256": digest.hexdigest(),
        "dirty": bool(status.stdout),
    }


def _risk_change_class(path: str, rules: list[dict[str, Any]]) -> tuple[str, list[str], list[str]]:
    reasons: list[str] = []
    protected_owners: set[str] = set()
    protected_rules = [rule for rule in rules if rule.get("protected")]
    for rule in protected_rules:
        reasons.append(str(rule.get("reason") or rule["id"]))
        for tier_owners in rule.get("owners", {}).values():
            protected_owners.update(tier_owners)
    if protected_rules or path in RISK_GATE_CHANGE_PATHS:
        if path in RISK_GATE_CHANGE_PATHS and not protected_rules:
            reasons.append("validation_gate_authority_change")
        return "R4", sorted(set(reasons)), sorted(protected_owners)
    if not rules:
        return "R3", ["unknown_validation_relevant_path"], []
    if is_doc_path(path):
        return "R0", ["documentation_or_non_executable_artifact"], []
    if path.startswith("tests/") or path == "conftest.py":
        return "R1", ["test_only_or_mechanically_local_change"], []
    if path.startswith("apps/dsa-web/") and re.search(r"(?:^|/)(?:__tests__/|[^/]+\.(?:test|spec)\.)", path):
        return "R1", ["frontend_test_only_change"], []
    if path.startswith("apps/dsa-web/src/"):
        if path.startswith(
            (
                "apps/dsa-web/src/components/",
                "apps/dsa-web/src/hooks/",
                "apps/dsa-web/src/lib/",
                "apps/dsa-web/src/styles/",
                "apps/dsa-web/src/utils/",
            )
        ):
            return "R3", ["shared_frontend_owner_boundary"], []
        return "R2", ["one_bounded_frontend_owner"], []
    if path.startswith("scripts/") or path == "test.sh":
        return "R1", ["mechanically_local_tooling_change"], []
    if len(rules) > 1:
        return "R3", ["multiple_owner_rules"], []
    return "R2", ["one_bounded_production_owner"], []


def _topology_inventory_may_change(path: str) -> bool:
    if path in {"validation/domain_test_topology.json", "scripts/domain_test_topology.py", "conftest.py"}:
        return True
    if path.startswith("tests/") and path.endswith(".py"):
        return True
    if path.startswith("apps/dsa-web/e2e/") and path.endswith((".spec.ts", ".spec.tsx")):
        return True
    return path.startswith("apps/dsa-web/src/") and bool(
        re.search(r"(?:^|/)(?:__tests__/|[^/]+\.(?:test|spec)\.)", path)
    )


def _backend_domains_for_paths(paths: Sequence[str], *, root: Path = ROOT) -> list[str]:
    from scripts import domain_test_topology

    domains: set[str] = set()
    manifest = domain_test_topology.load_manifest()
    entries = manifest["backend"]["tests"]

    def add_owned_test_file(test_path: str) -> bool:
        owned = {
            entry["domain"]
            for entry in entries
            if entry["id"].startswith(f"{test_path}::")
        }
        domains.update(owned)
        return bool(owned)

    for path in paths:
        if path.startswith("tests/"):
            if not add_owned_test_file(path):
                domains.add(domain_test_topology.classify_backend(f"{path}::validation_placeholder"))
        elif path.endswith(".py"):
            for related in infer_related_pytests(path, root=root):
                add_owned_test_file(related)
            if path.startswith("scripts/"):
                domains.add("runtime_operator_tooling")
            elif path.startswith("api/"):
                domains.add("api_schema_contracts")
        lowered = path.lower()
        for marker, domain in (
            ("auth", "auth_security"),
            ("provider", "provider_external_network"),
            ("scanner", "scanner"),
            ("backtest", "backtest"),
            ("portfolio", "portfolio_broker"),
            ("migration", "database_storage_migrations"),
            ("schema", "api_schema_contracts"),
        ):
            if marker in lowered:
                domains.add(domain)
    return sorted(domains)


def _backend_expected_selection(domains: Sequence[str]) -> dict[str, Any]:
    from scripts import domain_test_topology

    manifest = domain_test_topology.load_manifest()
    ids = [entry["id"] for entry in manifest["backend"]["tests"] if entry["domain"] in domains]
    return {"count": len(ids), "sha256": domain_test_topology.inventory_hash(ids)}


def _structured_backend_command(domains: Sequence[str]) -> list[str]:
    from scripts import domain_test_topology

    output = "$OUTPUT"
    command = [
        "$PYTHON",
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "-p",
        "scripts.domain_test_topology",
        "--domain-topology-verify-full",
        "--test-result-evidence-output",
        f"{output}/attempt-0.json",
        "--test-result-evidence-context",
        f"{output}/attempt-0-context.json",
        f"--junitxml={output}/attempt-0.junit.xml",
    ]
    if tuple(domains) != tuple(domain_test_topology.BACKEND_DOMAINS):
        command.extend(["--domain-topology-select-file", f"{output}/selection.json"])
    return command


def _gate_command(gate_id: str, *, base_ref: str, candidate_sha: str, changed_paths: Sequence[str], domains: Sequence[str]) -> list[str] | None:
    if gate_id == "scope.diff":
        return ["git", "diff", "--check"]
    if gate_id == "security.changed":
        return ["bash", "scripts/release_secret_scan.sh", "--files-from", "$CHANGED_FILES"]
    if gate_id == "security.branch":
        return ["bash", "scripts/release_secret_scan.sh", "--base-ref", base_ref]
    if gate_id == "syntax.changed":
        return ["$PYTHON", "-m", "py_compile", "$CHANGED_PYTHON"]
    if gate_id == "tests.backend.changed":
        return ["$PYTHON", "-m", "pytest", "-q", "$CHANGED_TESTS"]
    if gate_id == "tests.frontend.changed":
        return ["npm", "--prefix", "apps/dsa-web", "run", "test:related", "--", "$CHANGED_WEB"]
    if gate_id == "owners.affected":
        return [
            "$PYTHON",
            "scripts/domain_test_topology.py",
            "run-backend",
            "--domains",
            ",".join(domains),
            "--output-dir",
            f"$OUTPUT/{gate_id}",
            "--retry-failures",
            "0",
        ]
    if gate_id == "consumers.affected":
        return ["npm", "--prefix", "apps/dsa-web", "run", "test:related", "--", "$CHANGED_WEB"]
    if gate_id == "contracts.cross_owner":
        if any(path.startswith("apps/dsa-web/") for path in changed_paths):
            return ["npm", "--prefix", "apps/dsa-web", "run", "test"]
        return [
            "$PYTHON",
            "scripts/domain_test_topology.py",
            "run-backend",
            "--domains",
            ",".join(domains),
            "--output-dir",
            f"$OUTPUT/{gate_id}",
            "--retry-failures",
            "0",
        ]
    if gate_id == "topology.verify":
        return ["$PYTHON", "scripts/domain_test_topology.py", "verify-all"]
    if gate_id == "protected.owners":
        return ["$PYTHON", "-m", "pytest", "-m", "not network"]
    if gate_id == "architecture.global":
        return ["$PYTHON", "-m", "pytest", "-q", "tests/architecture"]
    if gate_id == "backend.canonical":
        return [
            "$PYTHON",
            "scripts/domain_test_topology.py",
            "run-backend",
            "--domains",
            ",".join(domains),
            "--output-dir",
            f"$OUTPUT/{gate_id}",
            "--retry-failures",
            "0",
        ]
    if gate_id == "browser.protected":
        from scripts import domain_test_topology

        protected_specs = [
            entry["path"].removeprefix("apps/dsa-web/")
            for entry in domain_test_topology.load_manifest()["playwright"]["specs"]
            if entry["owner"] == "protected_critical"
        ]
        if not protected_specs:
            raise SelectionError("protected browser selection is empty")
        return [
            "npm",
            "--prefix",
            "apps/dsa-web",
            "run",
            "test:e2e",
            "--",
            "--project=chromium",
            "--project=chromium-mobile",
            *protected_specs,
        ]
    if gate_id == "frontend.full":
        return ["npm", "--prefix", "apps/dsa-web", "run", "test"]
    if gate_id == "browser.full":
        return [
            "npm",
            "--prefix",
            "apps/dsa-web",
            "run",
            "test:e2e",
            "--",
            "--project=chromium",
            "--project=chromium-mobile",
        ]
    if gate_id == "uat.runtime":
        return ["$PYTHON", "scripts/uat_runtime_harness.py", "--expected-sha", candidate_sha]
    if gate_id == "release.real_runtime":
        return ["npm", "--prefix", "apps/dsa-web", "run", "test:e2e", "--", "--project=release-real-runtime"]
    return None


def _validation_config(*, manifest_hash: str) -> dict[str, Any]:
    return {"selectorVersion": RISK_SELECTOR_VERSION, "ownerManifestHash": manifest_hash}


def _selection_binding(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "changedFiles": plan["changedFiles"],
        "riskClass": plan["risk"]["class"],
        "affectedOwners": plan["affectedOwners"],
        "protectedOwners": plan["risk"]["protectedOwners"],
        "requestedGates": plan["requested"]["gates"],
        "gateIds": [gate["id"] for gate in plan["gates"]],
    }


def _seal_plan(plan: dict[str, Any]) -> dict[str, Any]:
    plan["identity"]["configSha256"] = stable_hash(plan["config"])
    plan["identity"]["selectionSha256"] = stable_hash(plan["selection"])
    plan["planHash"] = stable_hash({key: value for key, value in plan.items() if key != "planHash"})
    return plan


def build_validation_plan_from_changes(
    changes: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    root: Path = ROOT,
    base_ref: str,
    base_sha: str,
    candidate_ref: str,
    candidate_sha: str,
    change_source: str,
    manifest_hash: str,
    candidate_identity: dict[str, Any] | None = None,
    requested_risk: str | None = None,
    requested_gates: Sequence[str] = (),
    frozen_release: bool = False,
    accepted_integration: bool = False,
    user_facing: bool = False,
    release_runtime: bool = False,
) -> dict[str, Any]:
    requested_risk = requested_risk or "R0"
    _risk_index(requested_risk)
    requested_gates = tuple(sorted(set(requested_gates)))
    unknown_requested = sorted(set(requested_gates) - set(RISK_GATE_ORDER))
    if unknown_requested:
        raise SelectionError(f"unknown requested gate: {unknown_requested}")
    planned_changes: list[dict[str, Any]] = []
    risk_reasons: set[str] = set()
    protected_owners: set[str] = set()
    affected_owners: set[str] = set()
    unknown_paths: list[str] = []
    for raw_change in sorted(changes, key=lambda item: item["path"]):
        path = raw_change["path"]
        rules = matching_rules(path, manifest)
        risk_class, reasons, owners = _risk_change_class(path, rules)
        if not rules:
            unknown_paths.append(path)
            owner_ids = list(manifest["unknownEscalation"]["owners"])
        else:
            owner_ids = owner_ids_for_rules(rules)
        inferred_targets = infer_related_pytests(path, root=root)
        if inferred_targets:
            owner_ids = sorted(set(owner_ids) | {"direct.pytest.related_inference"})
        affected_owners.update(owner_ids)
        risk_reasons.update(reasons)
        protected_owners.update(owners)
        item = dict(raw_change)
        item.update(
            {
                "matchedRules": [rule["id"] for rule in rules],
                "riskClass": risk_class,
                "riskReasons": reasons,
                "ownerIds": owner_ids,
                "protectedOwners": owners,
                "authoritySource": "manifest_rule" if rules else "explicit_unknown_escalation",
            }
        )
        if inferred_targets:
            item["inferredOwnerTargets"] = inferred_targets
        planned_changes.append(item)

    classified_risk = _max_risk(
        requested_risk,
        *(item["riskClass"] for item in planned_changes),
        "R5" if frozen_release else "R0",
    )
    changed_paths = [item["path"] for item in planned_changes]
    topology_may_change = any(_topology_inventory_may_change(item["path"]) for item in planned_changes)
    frontend_changed = any(path.startswith("apps/dsa-web/") for path in changed_paths)
    backend_related = any(
        path.endswith(".py")
        and path.startswith(("api/", "bot/", "data_provider/", "scripts/", "src/", "tests/"))
        for path in changed_paths
    )
    changed_backend_tests = [path for path in changed_paths if path.startswith("tests/") and path.endswith(".py")]
    changed_frontend_tests = [
        path
        for path in changed_paths
        if path.startswith("apps/dsa-web/")
        and re.search(r"(?:^|/)(?:__tests__/|[^/]+\.(?:test|spec)\.)", path)
    ]
    requested_floor = requested_risk
    domains = _backend_domains_for_paths(changed_paths, root=root)
    if not domains:
        domains = ["residual_repository_integration"]
    full_domains = list(__import__("scripts.domain_test_topology", fromlist=["BACKEND_DOMAINS"]).BACKEND_DOMAINS)
    gate_ids: list[str] = []
    for risk_class in RISK_CLASSES:
        if _risk_index(risk_class) <= _risk_index(classified_risk):
            gate_ids.extend(RISK_GATE_FLOORS[risk_class])
    if accepted_integration and _risk_index(classified_risk) >= _risk_index("R3"):
        gate_ids.append("backend.canonical")
    if unknown_paths:
        gate_ids.append("backend.canonical")
    if topology_may_change:
        gate_ids.append("topology.verify")
    if frontend_changed and _risk_index(classified_risk) >= _risk_index("R3"):
        gate_ids.append("browser.protected")
    if user_facing and _risk_index(classified_risk) >= _risk_index("R3"):
        gate_ids.append("uat.runtime")
    if release_runtime and _risk_index(classified_risk) >= _risk_index("R4"):
        gate_ids.append("release.real_runtime")
    for gate_id in requested_gates:
        if gate_id not in gate_ids:
            gate_ids.append(gate_id)
    gate_ids = [gate_id for gate_id in RISK_GATE_ORDER if gate_id in set(gate_ids)]

    actual_candidate = candidate_identity or _candidate_identity(root, candidate_ref)
    if candidate_sha != actual_candidate.get("commitSha"):
        raise SelectionError("candidate commit identity mismatch while building validation plan")
    config = _validation_config(manifest_hash=manifest_hash)
    plan: dict[str, Any] = {
        "schemaVersion": RISK_SELECTION_SCHEMA,
        "kind": "validation-plan",
        "state": "complete",
        "authority": "risk-selection",
        "identity": {
            "baseRef": base_ref,
            "baseSha": base_sha,
            "candidateRef": candidate_ref,
            "candidateSha": candidate_sha,
            "candidate": dict(actual_candidate),
            "changeSource": change_source,
        },
        "config": config,
        "changedFiles": changed_paths,
        "affectedOwners": sorted(affected_owners),
        "changes": planned_changes,
        "requested": {
            "riskClass": requested_floor,
            "gates": list(requested_gates),
            "frozenRelease": frozen_release,
            "acceptedIntegration": accepted_integration,
            "userFacing": user_facing,
            "releaseRuntime": release_runtime,
        },
        "risk": {
            "class": classified_risk,
            "reasons": sorted(risk_reasons),
            "protectedOwners": sorted(protected_owners),
            "unknownPaths": sorted(unknown_paths),
            "topologyMayChange": topology_may_change,
        },
        "selection": {},
        "gates": [],
    }
    plan["selection"] = _selection_binding(plan)
    for gate_id in gate_ids:
        gate_domains = full_domains if gate_id == "backend.canonical" else domains
        command = _gate_command(
            gate_id,
            base_ref=base_ref,
            candidate_sha=actual_candidate["commitSha"],
            changed_paths=changed_paths,
            domains=gate_domains,
        )
        applicable = True
        if gate_id == "syntax.changed":
            applicable = any(path.endswith(".py") for path in changed_paths)
        elif gate_id == "tests.backend.changed":
            applicable = bool(changed_backend_tests)
        elif gate_id == "tests.frontend.changed":
            applicable = bool(changed_frontend_tests)
        elif gate_id == "owners.affected":
            applicable = backend_related
        elif gate_id == "contracts.cross_owner":
            applicable = backend_related or frontend_changed
        elif gate_id == "topology.verify":
            applicable = topology_may_change
        elif gate_id == "architecture.global":
            applicable = classified_risk in {"R4", "R5"}
        elif gate_id == "consumers.affected":
            applicable = frontend_changed
        elif gate_id in {"frontend.full", "browser.full"}:
            applicable = frontend_changed or classified_risk == "R5"
        elif gate_id == "browser.protected":
            applicable = frontend_changed or classified_risk == "R5"
        elif gate_id == "uat.runtime":
            applicable = user_facing or classified_risk == "R5"
        elif gate_id == "release.real_runtime":
            applicable = release_runtime or classified_risk == "R5"
        if gate_id in requested_gates:
            applicable = True
        reason = "cumulative_tier_requirement"
        if gate_id in requested_gates:
            reason = "explicit_task_gate"
        elif gate_id == "backend.canonical" and accepted_integration:
            reason = "accepted_integration_batch"
        elif gate_id == "backend.canonical" and unknown_paths:
            reason = "unknown_change_fail_closed"
        elif gate_id == "topology.verify" and topology_may_change:
            reason = "topology_inventory_may_change"
        elif gate_id == "browser.protected" and frontend_changed:
            reason = "frontend_critical_route_trigger"
        gate: dict[str, Any] = {
            "id": gate_id,
            "minimumRisk": RISK_GATE_MINIMUM[gate_id],
            "required": applicable,
            "command": command,
            "retryCount": 0,
            "selectionReason": reason,
            "evidence": {"kind": RISK_GATE_EVIDENCE[gate_id], "inferenceAllowed": False},
        }
        backend_covered = "backend.canonical" in gate_ids and (
            gate_id in {"tests.backend.changed", "owners.affected", "protected.owners", "architecture.global"}
            or (gate_id == "contracts.cross_owner" and not frontend_changed)
        )
        owner_covered = (
            gate_id == "contracts.cross_owner"
            and backend_related
            and not frontend_changed
            and "owners.affected" in gate_ids
        )
        if backend_covered or owner_covered:
            gate["command"] = None
            gate["satisfiedBy"] = "backend.canonical" if backend_covered else "owners.affected"
            gate["evidence"]["kind"] = "T630-covered-selection"
            source_domains = full_domains if backend_covered else domains
            gate["coverageRequirement"] = {
                "kind": "backend-domain-superset",
                "requiredDomains": gate_domains,
                "sourceDomains": source_domains,
            }
        if gate_id in {"owners.affected", "backend.canonical"}:
            gate["domains"] = gate_domains
            gate["expectedSelection"] = _backend_expected_selection(gate_domains)
            gate["structuredCommand"] = _structured_backend_command(gate_domains)
            gate["structuredEvidence"] = "T630"
        plan["gates"].append(gate)
    plan["selection"] = _selection_binding(plan)
    return _seal_plan(plan)


def _validate_plan(plan: dict[str, Any]) -> None:
    if plan.get("schemaVersion") != RISK_SELECTION_SCHEMA or plan.get("kind") != "validation-plan":
        raise SelectionError("validation plan schema or kind is invalid")
    if plan.get("state") != "complete" or plan.get("authority") != "risk-selection":
        raise SelectionError("validation plan is incomplete or has the wrong authority")
    if plan.get("identity", {}).get("configSha256") != stable_hash(plan.get("config")):
        raise SelectionError("validation plan config identity mismatch")
    if plan.get("identity", {}).get("selectionSha256") != stable_hash(plan.get("selection")):
        raise SelectionError("validation plan selection identity mismatch")
    if plan.get("planHash") != stable_hash({key: value for key, value in plan.items() if key != "planHash"}):
        raise SelectionError("validation plan hash mismatch")


def _stage_inventory(node_ids: Iterable[str]) -> dict[str, Any]:
    from scripts import domain_test_topology

    ordered = sorted(node_ids)
    if len(ordered) != len(set(ordered)):
        raise SelectionError("backend stage plan contains duplicate node IDs")
    return {
        "count": len(ordered),
        "sha256": domain_test_topology.inventory_hash(ordered),
        "nodeIds": ordered,
    }


def _release_stage_trigger_reasons(risk_plan: dict[str, Any], tier: str) -> list[str]:
    reasons: list[str] = []
    if tier == "release":
        reasons.append("explicit_release_tier")
    risk = risk_plan["risk"]
    requested = risk_plan["requested"]
    if risk["class"] == "R5":
        reasons.append("r5_release_risk")
    if risk["unknownPaths"]:
        reasons.append("unknown_change_fail_closed")
    if risk["protectedOwners"]:
        reasons.append("protected_owner_fail_closed")
    if requested["userFacing"]:
        reasons.append("user_facing_qualification")
    if requested["releaseRuntime"]:
        reasons.append("release_runtime_qualification")
    for path in risk_plan["changedFiles"]:
        if path in BACKEND_RELEASE_STAGE_EXACT_TRIGGERS or path.startswith(BACKEND_RELEASE_STAGE_PREFIX_TRIGGERS):
            reasons.append(f"release_or_validation_authority:{path}")
    return sorted(set(reasons))


def build_backend_stage_plan(
    risk_plan: dict[str, Any],
    *,
    tier: str,
    topology_manifest_path: Path = DEFAULT_TOPOLOGY_MANIFEST,
) -> dict[str, Any]:
    """Partition the backend topology into one canonical and one release-owned stage."""

    if tier not in BACKEND_VALIDATION_TIERS:
        raise SelectionError(f"unknown backend validation tier: {tier}")
    _validate_plan(risk_plan)
    from scripts import domain_test_topology

    manifest = domain_test_topology.load_manifest(topology_manifest_path)
    domain_test_topology.validate_manifest(manifest)
    all_ids = sorted(entry["id"] for entry in manifest["backend"]["tests"])
    release_only = sorted(BACKEND_RELEASE_ONLY_NODE_IDS)
    missing = sorted(set(release_only) - set(all_ids))
    if missing:
        raise SelectionError(f"release-only backend nodes are missing from topology: {missing}")
    canonical_ids = sorted(set(all_ids) - set(release_only))
    trigger_reasons = _release_stage_trigger_reasons(risk_plan, tier)
    release_required = bool(trigger_reasons)
    stages = [
        {
            "id": "backend.canonical",
            "tierOwnership": "canonical",
            "required": True,
            **_stage_inventory(canonical_ids),
        },
        {
            "id": "backend.release-only",
            "tierOwnership": "release",
            "purpose": (
                "release packaging, operator evidence, candidate distribution, and final release secret validation; "
                "canonical changed-file and branch secret gates remain mandatory"
            ),
            "required": release_required,
            "selectionReasons": trigger_reasons,
            **_stage_inventory(release_only),
        },
    ]
    execution_ids = [node_id for stage in stages if stage["required"] for node_id in stage["nodeIds"]]
    plan = {
        "schemaVersion": BACKEND_STAGE_SCHEMA,
        "authority": "tiered-backend-stage-selection",
        "tier": tier,
        "riskPlanHash": risk_plan["planHash"],
        "topology": manifest["backend"]["currentInventory"],
        "stages": stages,
        "execution": _stage_inventory(execution_ids),
        "releaseInventory": _stage_inventory(all_ids),
        "releaseQualificationRequired": tier == "release",
        "releaseReady": False,
    }
    plan["planHash"] = stable_hash(plan)
    validate_backend_stage_plan(plan, topology_manifest_path=topology_manifest_path)
    return plan


def validate_backend_stage_plan(
    plan: dict[str, Any],
    *,
    topology_manifest_path: Path = DEFAULT_TOPOLOGY_MANIFEST,
) -> None:
    from scripts import domain_test_topology

    if plan.get("schemaVersion") != BACKEND_STAGE_SCHEMA or plan.get("authority") != "tiered-backend-stage-selection":
        raise SelectionError("backend stage plan schema or authority is invalid")
    if plan.get("tier") not in BACKEND_VALIDATION_TIERS or plan.get("releaseReady") is not False:
        raise SelectionError("backend stage plan tier or release-ready state is invalid")
    if plan.get("planHash") != stable_hash({key: value for key, value in plan.items() if key != "planHash"}):
        raise SelectionError("backend stage plan hash mismatch")
    manifest = domain_test_topology.load_manifest(topology_manifest_path)
    domain_test_topology.validate_manifest(manifest)
    if plan.get("topology") != manifest["backend"]["currentInventory"]:
        raise SelectionError("backend stage plan topology identity mismatch")
    stages = plan.get("stages")
    if not isinstance(stages, list) or [stage.get("id") for stage in stages] != [
        "backend.canonical",
        "backend.release-only",
    ]:
        raise SelectionError("backend stage plan inventory is malformed")
    if [stage.get("tierOwnership") for stage in stages] != ["canonical", "release"]:
        raise SelectionError("backend stage plan tier ownership is malformed")
    for stage in stages:
        node_ids = stage.get("nodeIds")
        if not isinstance(node_ids, list) or stage.get("required") not in {True, False}:
            raise SelectionError("backend stage plan stage is malformed")
        if _stage_inventory(node_ids) != {key: stage.get(key) for key in ("count", "sha256", "nodeIds")}:
            raise SelectionError("backend stage plan stage identity mismatch")
    canonical_ids = set(stages[0]["nodeIds"])
    release_only_ids = set(stages[1]["nodeIds"])
    if release_only_ids != set(BACKEND_RELEASE_ONLY_NODE_IDS) or canonical_ids & release_only_ids:
        raise SelectionError("backend stage plan ownership is incomplete or overlapping")
    expected_release = _stage_inventory(entry["id"] for entry in manifest["backend"]["tests"])
    if plan.get("releaseInventory") != expected_release or canonical_ids | release_only_ids != set(expected_release["nodeIds"]):
        raise SelectionError("backend stage plan release inventory is incomplete")
    execution_ids = [node_id for stage in stages if stage["required"] for node_id in stage["nodeIds"]]
    if plan.get("execution") != _stage_inventory(execution_ids):
        raise SelectionError("backend stage plan execution identity mismatch")
    if plan["tier"] == "release" and (not stages[1]["required"] or not plan.get("releaseQualificationRequired")):
        raise SelectionError("backend stage plan release tier is incomplete")


def project_backend_shard_plan(
    risk_plan: dict[str, Any],
    shard_plan: dict[str, Any],
    *,
    tier: str,
) -> dict[str, Any]:
    """Project a T633 full plan onto the selected T637 backend stages."""

    from scripts import domain_test_topology

    _validate_plan(risk_plan)
    stages = build_backend_stage_plan(risk_plan, tier=tier)
    if shard_plan.get("schemaVersion") != "wolfystock.backend-shard-plan.v1":
        raise SelectionError("backend shard plan schema is invalid")
    if shard_plan.get("planHash") != stable_hash(
        {key: value for key, value in shard_plan.items() if key != "planHash"}
    ):
        raise SelectionError("backend shard plan hash mismatch")
    if shard_plan.get("riskPlanHash") != risk_plan["planHash"]:
        raise SelectionError("backend shard plan risk identity mismatch")
    expected_full = {key: stages["releaseInventory"][key] for key in ("count", "sha256")}
    if shard_plan.get("selection") != expected_full:
        raise SelectionError("backend shard plan is not the complete release inventory")
    source_shards = shard_plan.get("shards")
    if (
        not isinstance(source_shards, list)
        or len(source_shards) != 2
        or not all(isinstance(shard, dict) and isinstance(shard.get("nodeIds"), list) for shard in source_shards)
        or len({shard.get("id") for shard in source_shards}) != 2
    ):
        raise SelectionError("backend shard plan shard inventory is malformed")
    source_ids = [node_id for shard in source_shards for node_id in shard["nodeIds"]]
    if _stage_inventory(source_ids) != stages["releaseInventory"]:
        raise SelectionError("backend shard plan source inventory is incomplete or duplicated")
    selected = set(stages["execution"]["nodeIds"])
    projected = dict(shard_plan)
    projected_shards = []
    for shard in source_shards:
        node_ids = sorted(selected & set(shard["nodeIds"]))
        if not node_ids:
            raise SelectionError(f"backend shard plan projection emptied shard: {shard.get('id')}")
        selection = {
            key: value
            for key, value in _stage_inventory(node_ids).items()
            if key != "nodeIds"
        }
        projected_shards.append({**shard, "nodeIds": node_ids, "selection": selection})
    projected["authority"] = f"{shard_plan['authority']}+T637-tiering"
    projected["structuredResultAuthority"] = domain_test_topology.TEST_RESULT_SCHEMA_VERSION
    projected["validationStages"] = stages
    projected["selection"] = {key: stages["execution"][key] for key in ("count", "sha256")}
    projected["shards"] = projected_shards
    projected["planHash"] = stable_hash({key: value for key, value in projected.items() if key != "planHash"})
    return projected


def consume_structured_backend_result(
    plan: dict[str, Any],
    result_path: Path,
    *,
    gate_id: str,
    topology_manifest_path: Path = DEFAULT_TOPOLOGY_MANIFEST,
) -> dict[str, Any]:
    _validate_plan(plan)
    gate = next((gate for gate in plan["gates"] if gate["id"] == gate_id), None)
    if gate is None or gate.get("structuredEvidence") != "T630":
        raise SelectionError(f"gate does not consume T630 evidence: {gate_id}")
    try:
        raw = json.loads(result_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SelectionError(f"missing structured result: {result_path}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SelectionError(f"malformed structured result: {result_path}") from exc
    if raw.get("state") != "completed":
        raise SelectionError("structured result is incomplete")
    if raw.get("retries"):
        raise SelectionError("structured result contains an unauthorized retry")
    first = raw.get("firstAttempt")
    if not isinstance(first, dict) or first.get("state") != "completed":
        raise SelectionError("first attempt evidence is incomplete")
    if first.get("counts", {}).get("parents", {}).get("skipped", 0) or first.get("counts", {}).get("children", {}).get("skipped", 0):
        raise SelectionError("skipped structured evidence is not a pass")
    try:
        from scripts import domain_test_topology

        manifest = domain_test_topology.load_manifest(topology_manifest_path)
        validated = domain_test_topology.reclassify_backend_result(manifest, result_path)
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, json.JSONDecodeError, domain_test_topology.TopologyError) as exc:
        raise SelectionError(f"structured result validation failed: {exc}") from exc
    if result.get("status") != "passed":
        raise SelectionError(f"selected structured check failed: {result.get('status')}")
    evidence_identity = result.get("identity", {})
    candidate = plan["identity"]["candidate"]
    if evidence_identity.get("candidate") != candidate:
        raise SelectionError("candidate identity mismatch")
    expected_selection = gate["expectedSelection"]
    if evidence_identity.get("selection") != expected_selection:
        raise SelectionError("selection identity mismatch")
    if evidence_identity.get("topology") != manifest["backend"]["currentInventory"]:
        raise SelectionError("topology identity mismatch")
    if gate.get("structuredCommand") and evidence_identity.get("command", {}).get("argv") != gate["structuredCommand"]:
        raise SelectionError("structured command identity mismatch")
    if result.get("selectedCount") != expected_selection["count"]:
        raise SelectionError("structured selected-count identity mismatch")
    return {"gateId": gate_id, "status": "passed", "result": validated}


def _render_validation_command(command: Sequence[str], *, plan: dict[str, Any], output_dir: Path, root: Path) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    changed = output_dir / "changed-files.txt"
    changed.write_text("\n".join(plan["changedFiles"]) + ("\n" if plan["changedFiles"] else ""), encoding="utf-8")
    python_paths = [path for path in plan["changedFiles"] if path.endswith(".py") and (root / path).is_file()]
    test_paths = [path for path in plan["changedFiles"] if path.startswith("tests/") and (root / path).is_file()]
    web_paths = [
        path.removeprefix("apps/dsa-web/")
        for path in plan["changedFiles"]
        if path.startswith("apps/dsa-web/") and (root / path).is_file()
    ]
    expansions = {
        "$CHANGED_FILES": [str(changed)],
        "$CHANGED_PYTHON": python_paths,
        "$CHANGED_TESTS": test_paths,
        "$CHANGED_WEB": web_paths,
    }
    rendered: list[str] = []
    for token in command:
        if token in expansions:
            if not expansions[token]:
                raise SelectionError(f"required command input unavailable: {token}")
            rendered.extend(expansions[token])
            continue
        value = token.replace("$PYTHON", sys.executable).replace("$CANDIDATE_SHA", plan["identity"]["candidate"]["commitSha"])
        value = value.replace("$OUTPUT", str(output_dir))
        rendered.append(value)
    return rendered


def execute_validation_plan(
    plan: dict[str, Any],
    *,
    output_dir: Path,
    root: Path = ROOT,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    candidate_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _validate_plan(plan)
    output_dir.mkdir(parents=True, exist_ok=True)
    actual_candidate = candidate_identity or _candidate_identity(root, plan["identity"]["candidateRef"])
    if actual_candidate != plan["identity"]["candidate"]:
        payload = {
            "schemaVersion": RISK_SELECTION_SCHEMA,
            "status": "failed",
            "exitCode": 2,
            "reason": "validation plan candidate identity is stale or mismatched",
            "gates": [],
        }
        (output_dir / "execution-result.json").write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        return payload
    results: list[dict[str, Any]] = []
    results_by_gate: dict[str, dict[str, Any]] = {}
    for gate in plan["gates"]:
        if not gate["required"]:
            gate_result = {"gateId": gate["id"], "status": "not_applicable", "retries": []}
            results.append(gate_result)
            results_by_gate[gate["id"]] = gate_result
            continue
        if gate.get("satisfiedBy"):
            gate_result = {
                "gateId": gate["id"],
                "status": "pending_evidence",
                "evidenceFrom": gate["satisfiedBy"],
                "retries": [],
            }
            results.append(gate_result)
            results_by_gate[gate["id"]] = gate_result
            continue
        command = gate.get("command")
        if not command:
            gate_result = {"gateId": gate["id"], "status": "not_run", "retries": []}
            results.append(gate_result)
            results_by_gate[gate["id"]] = gate_result
            payload = {"schemaVersion": RISK_SELECTION_SCHEMA, "status": "failed", "exitCode": 2, "gates": results}
            (output_dir / "execution-result.json").write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            return payload
        try:
            rendered = _render_validation_command(command, plan=plan, output_dir=output_dir, root=root)
        except SelectionError as exc:
            gate_result = {
                "gateId": gate["id"],
                "status": "failed",
                "exitCode": 2,
                "command": command,
                "reason": str(exc),
                "retries": [],
            }
            results.append(gate_result)
            results_by_gate[gate["id"]] = gate_result
            payload = {"schemaVersion": RISK_SELECTION_SCHEMA, "status": "failed", "exitCode": 2, "gates": results}
            (output_dir / "execution-result.json").write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            return payload
        try:
            completed = runner(rendered, cwd=root, text=True, encoding="utf-8", errors="replace")
        except OSError as exc:
            gate_result = {
                "gateId": gate["id"],
                "status": "failed",
                "exitCode": 127,
                "command": command,
                "reason": f"command launch failed: {exc}",
                "retries": [],
            }
            results.append(gate_result)
            results_by_gate[gate["id"]] = gate_result
            payload = {"schemaVersion": RISK_SELECTION_SCHEMA, "status": "failed", "exitCode": 127, "gates": results}
            (output_dir / "execution-result.json").write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            return payload
        gate_result = {
            "gateId": gate["id"],
            "status": "passed" if completed.returncode == 0 else "failed",
            "exitCode": completed.returncode,
            "command": command,
            "retries": [],
        }
        results.append(gate_result)
        results_by_gate[gate["id"]] = gate_result
        if completed.returncode:
            payload = {"schemaVersion": RISK_SELECTION_SCHEMA, "status": "failed", "exitCode": completed.returncode, "gates": results}
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "execution-result.json").write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            return payload
        if gate.get("structuredEvidence") == "T630":
            result_path = output_dir / gate["id"] / "result.json"
            try:
                evidence_result = consume_structured_backend_result(plan, result_path, gate_id=gate["id"])
            except SelectionError as exc:
                gate_result["status"] = "failed"
                gate_result["reason"] = str(exc)
                payload = {"schemaVersion": RISK_SELECTION_SCHEMA, "status": "failed", "exitCode": 2, "gates": results}
                (output_dir / "execution-result.json").write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
                return payload
            gate_result["structuredEvidence"] = evidence_result["status"]

    gates_by_id = {gate["id"]: gate for gate in plan["gates"]}
    for gate_result in results:
        if gate_result["status"] != "pending_evidence":
            continue
        gate = gates_by_id[gate_result["gateId"]]
        source_id = gate["satisfiedBy"]
        source = results_by_gate.get(source_id)
        source_gate = gates_by_id.get(source_id)
        coverage = gate.get("coverageRequirement", {})
        valid_coverage = (
            coverage.get("kind") == "backend-domain-superset"
            and source is not None
            and source.get("status") == "passed"
            and source.get("structuredEvidence") == "passed"
            and source_gate is not None
            and source_gate.get("structuredEvidence") == "T630"
            and set(source_gate.get("domains", [])) == set(coverage.get("sourceDomains", []))
            and set(coverage.get("requiredDomains", [])).issubset(set(source_gate.get("domains", [])))
        )
        if not valid_coverage:
            gate_result["status"] = "failed"
            gate_result["reason"] = f"required coverage evidence was not established by {source_id}"
            payload = {
                "schemaVersion": RISK_SELECTION_SCHEMA,
                "status": "failed",
                "exitCode": 2,
                "gates": results,
            }
            (output_dir / "execution-result.json").write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            return payload
        gate_result["status"] = "passed"
        gate_result["coverage"] = "validated_structured_domain_superset"
    payload = {"schemaVersion": RISK_SELECTION_SCHEMA, "status": "passed", "exitCode": 0, "gates": results}
    (output_dir / "execution-result.json").write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return payload


def tracked_path_inventory(
    manifest: dict[str, Any],
    *,
    root: Path = ROOT,
    manifest_hash: str,
) -> dict[str, Any]:
    tracked_paths = unique_sorted(decode_z_paths(run_git_bytes(["ls-files", "-z"], root=root)))
    explicit_paths: list[str] = []
    unknown_paths: list[str] = []
    path_rules: list[dict[str, Any]] = []
    for path in tracked_paths:
        rules = matching_rules(path, manifest)
        if rules:
            explicit_paths.append(path)
            path_rules.append({"path": path, "matchedRules": [rule["id"] for rule in rules]})
        else:
            unknown_paths.append(path)
            path_rules.append(
                {
                    "path": path,
                    "matchedRules": [],
                    "unknownEscalation": manifest["unknownEscalation"]["reason"],
                }
            )
    inventory = {
        "schemaVersion": 1,
        "shadowOnly": True,
        "manifestVersion": manifest["manifestVersion"],
        "manifestHash": manifest_hash,
        "trackedValidationRelevantPathCount": len(tracked_paths),
        "explicitRulePathCount": len(explicit_paths),
        "unknownEscalationPathCount": len(unknown_paths),
        "unknownEscalationPaths": unknown_paths,
        "silentlyUnmappedPaths": [],
        "paths": path_rules,
    }
    inventory["inventoryHash"] = stable_hash(inventory)
    return inventory


def resolve_output_path(path: str, relative_to: str | None, *, root: Path = ROOT) -> str | None:
    if not relative_to:
        return path
    base = root / relative_to
    absolute = root / path
    try:
        return absolute.relative_to(base).as_posix()
    except ValueError:
        return None


def selected_files(args: argparse.Namespace) -> tuple[dict[str, object], list[str], list[str]]:
    if args.files is not None or args.files_from:
        provided: list[str] = []
        for path in args.files or []:
            provided.append(path)
        for file_list in args.files_from or []:
            provided.extend(read_files_from(file_list, root=args.root))
        raw = {
            "baseRefAvailable": base_ref_available(args.base_ref),
            "branchFiles": [],
            "stagedFiles": [],
            "worktreeFiles": [],
            "untrackedFiles": [],
            "localFiles": [],
            "selectedFiles": unique_sorted(normalize_path(path, root=args.root) or "" for path in provided),
        }
    else:
        raw = collect_raw(args.mode, args.base_ref, args.diff_filter)

    normalized = raw["selectedFiles"]
    assert isinstance(normalized, list)
    skipped = [path for path in normalized if is_generated_static_binary_or_cache(path)]
    filtered = [path for path in normalized if scope_allows(path, args.scope)]
    if args.existing:
        filtered = [path for path in filtered if path_exists(path, root=args.root)]

    output_files: list[str] = []
    for path in filtered:
        rendered = resolve_output_path(path, args.relative_to, root=args.root)
        if rendered is not None:
            output_files.append(rendered)
    return raw, unique_sorted(output_files), unique_sorted(skipped)


def print_files(files: list[str], output_format: str) -> None:
    if output_format == "lines":
        for path in files:
            print(path)
        return
    if output_format == "nul":
        sys.stdout.buffer.write(b"".join(path.encode("utf-8") + b"\0" for path in files))
        return
    if output_format == "shell":
        print(" ".join(shlex.quote(path) for path in files))
        return
    raise ValueError(f"unsupported file output format: {output_format}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect changed files for local validation tiers without writing repo cache files.",
        epilog=(
            "Examples:\n"
            "  python3 scripts/validation_changed_files.py --mode active --scope frontend-lint\n"
            "  python3 scripts/validation_changed_files.py --files-from /tmp/files.txt --scope secret\n"
            "  python3 scripts/validation_changed_files.py --scope frontend-lint --relative-to apps/dsa-web --exec eslint"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--base-ref", default=DEFAULT_BASE_REF, help=f"base ref for branch diffs (default: {DEFAULT_BASE_REF})")
    parser.add_argument(
        "--mode",
        choices=("active", "all", "branch", "branch-release", "local", "staged", "worktree", "untracked"),
        default="active",
        help="changed-file source; active uses local files when present, otherwise branch files",
    )
    parser.add_argument(
        "--scope",
        choices=("all", "secret", "frontend", "frontend-lint", "frontend-related", "design", "python", "docs"),
        default="all",
        help="filter files to a validation domain",
    )
    parser.add_argument("--format", choices=("lines", "nul", "shell", "json"), default="lines", help="output format")
    parser.add_argument("--diff-filter", default=DEFAULT_DIFF_FILTER, help=f"git diff-filter letters (default: {DEFAULT_DIFF_FILTER})")
    parser.add_argument("--files", nargs="*", help="explicit file paths to filter instead of collecting git changes")
    parser.add_argument("--files-from", action="append", help="read explicit file paths from a newline-delimited file, or '-' for stdin")
    parser.add_argument("--existing", action="store_true", help="only return files that exist in the working tree")
    parser.add_argument("--relative-to", help="render output paths relative to this repo-local directory")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--skip-message", default="[SKIP] no changed files matched the requested validation scope")
    parser.add_argument("--exec", nargs=argparse.REMAINDER, help="run the command after -- with selected files appended")
    shadow = parser.add_mutually_exclusive_group()
    shadow.add_argument(
        "--shadow-plan",
        action="store_true",
        help="emit the deterministic validation-owner shadow plan without running owners",
    )
    shadow.add_argument(
        "--validate-owner-manifest",
        action="store_true",
        help="validate owner references, test targets, npm scripts, and escalation structure",
    )
    shadow.add_argument(
        "--inventory-owner-coverage",
        action="store_true",
        help="emit exhaustive tracked-path owner coverage and explicit unknown escalations",
    )
    parser.add_argument("--candidate", default="HEAD", help="candidate commit for the shadow planner (default: HEAD)")
    parser.add_argument(
        "--shadow-change-source",
        choices=("union", "committed"),
        default="union",
        help="union includes committed, staged, unstaged, and untracked changes; committed is for historical corpus comparison",
    )
    parser.add_argument(
        "--owner-manifest",
        type=Path,
        default=DEFAULT_OWNER_MANIFEST,
        help="JSON owner manifest for shadow planning",
    )
    parser.add_argument(
        "--risk-plan",
        action="store_true",
        help="emit the deterministic cumulative R0-R5 validation selection plan",
    )
    parser.add_argument(
        "--execute-validation-plan",
        type=Path,
        help="execute a previously emitted validation plan and consume structured evidence",
    )
    parser.add_argument("--backend-stage-plan", type=Path, help="emit tier stages for a sealed risk plan")
    parser.add_argument(
        "--project-backend-shard-plan",
        type=Path,
        help="project a sealed T633 full shard plan onto explicit backend tier stages",
    )
    parser.add_argument("--risk-plan-input", type=Path, help="sealed T631 plan used by backend stage operations")
    parser.add_argument("--validation-tier", choices=BACKEND_VALIDATION_TIERS)
    parser.add_argument("--requested-risk", choices=RISK_CLASSES, default=None)
    parser.add_argument("--requested-gate", action="append", default=[])
    parser.add_argument("--frozen-release", action="store_true")
    parser.add_argument("--accepted-integration", action="store_true")
    parser.add_argument("--user-facing", action="store_true")
    parser.add_argument("--release-runtime", action="store_true")
    parser.add_argument("--execution-output-dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.root = args.root.resolve()

    if args.backend_stage_plan is not None or args.project_backend_shard_plan is not None:
        try:
            if args.backend_stage_plan is not None and args.project_backend_shard_plan is not None:
                raise SelectionError("backend stage plan and shard projection operations are mutually exclusive")
            if args.validation_tier is None:
                raise SelectionError("--validation-tier is required for backend stage operations")
            if args.project_backend_shard_plan is not None and args.risk_plan_input is None:
                raise SelectionError("--risk-plan-input is required for shard plan projection")
            risk_path = args.backend_stage_plan or args.risk_plan_input
            assert risk_path is not None
            risk_plan = json.loads(risk_path.read_text(encoding="utf-8"))
            if args.project_backend_shard_plan is None:
                payload = build_backend_stage_plan(risk_plan, tier=args.validation_tier)
            else:
                shard_plan = json.loads(args.project_backend_shard_plan.read_text(encoding="utf-8"))
                payload = project_backend_shard_plan(
                    risk_plan,
                    shard_plan,
                    tier=args.validation_tier,
                )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, SelectionError) as exc:
            print(json.dumps({"status": "error", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if args.execute_validation_plan is not None:
        try:
            plan = json.loads(args.execute_validation_plan.read_text(encoding="utf-8"))
            if args.execution_output_dir is None:
                raise SelectionError("--execution-output-dir is required for validation-plan execution")
            output_dir = args.execution_output_dir
            payload = execute_validation_plan(plan, output_dir=output_dir, root=args.root)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, SelectionError) as exc:
            print(json.dumps({"status": "error", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return int(payload.get("exitCode", 2))

    if args.risk_plan:
        try:
            manifest, manifest_hash = load_owner_manifest(args.owner_manifest, root=args.root)
            validate_owner_manifest(manifest, root=args.root, manifest_hash=manifest_hash)
            observations, base_sha, candidate_sha = collect_shadow_observations(
                args.base_ref,
                args.candidate,
                root=args.root,
                change_source=args.shadow_change_source,
            )
            plan = build_validation_plan_from_changes(
                aggregate_observations(observations),
                manifest,
                root=args.root,
                base_ref=args.base_ref,
                base_sha=base_sha,
                candidate_ref=args.candidate,
                candidate_sha=candidate_sha,
                change_source=args.shadow_change_source,
                manifest_hash=manifest_hash,
                candidate_identity=_candidate_identity(args.root, args.candidate),
                requested_risk=args.requested_risk,
                requested_gates=args.requested_gate,
                frozen_release=args.frozen_release,
                accepted_integration=args.accepted_integration,
                user_facing=args.user_facing,
                release_runtime=args.release_runtime,
            )
            print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        except (OSError, ValueError, KeyError, json.JSONDecodeError, OwnerManifestError, SelectionError) as exc:
            print(json.dumps({"status": "error", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2

    if args.shadow_plan or args.validate_owner_manifest or args.inventory_owner_coverage:
        try:
            manifest, manifest_hash = load_owner_manifest(args.owner_manifest, root=args.root)
            validation = validate_owner_manifest(
                manifest,
                root=args.root,
                manifest_hash=manifest_hash,
            )
            resolved_manifest = manifest_path(args.owner_manifest, root=args.root)
            try:
                manifest_file = resolved_manifest.relative_to(args.root).as_posix()
            except ValueError:
                manifest_file = resolved_manifest.as_posix()
            if args.validate_owner_manifest:
                payload = validation
            elif args.inventory_owner_coverage:
                payload = tracked_path_inventory(manifest, root=args.root, manifest_hash=manifest_hash)
            else:
                payload = build_shadow_plan(
                    args.base_ref,
                    args.candidate,
                    manifest,
                    root=args.root,
                    change_source=args.shadow_change_source,
                    manifest_hash=manifest_hash,
                    manifest_file=manifest_file,
                )
        except OwnerManifestError as exc:
            print(f"[FAIL] shadow owner planner: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    raw, files, skipped = selected_files(args)
    classification = classify(raw["selectedFiles"])  # type: ignore[arg-type]

    if args.exec is not None:
        command = list(args.exec)
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            parser.error("--exec requires a command after --")
        if not files:
            print(args.skip_message)
            return 0
        return subprocess.call([*command, *files])

    if args.format == "json":
        payload = {
            "root": str(args.root),
            "baseRef": args.base_ref,
            "mode": args.mode,
            "scope": args.scope,
            "baseRefAvailable": raw["baseRefAvailable"],
            "branchFiles": raw["branchFiles"],
            "stagedFiles": raw["stagedFiles"],
            "worktreeFiles": raw["worktreeFiles"],
            "untrackedFiles": raw["untrackedFiles"],
            "localFiles": raw["localFiles"],
            "selectedFiles": raw["selectedFiles"],
            "files": files,
            "skippedGeneratedStaticBinaryOrCache": skipped,
            "collectorMetadata": classification,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print_files(files, args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
