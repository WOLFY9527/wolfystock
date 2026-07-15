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
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_REF = (
    os.environ.get("VALIDATION_BASE_REF")
    or os.environ.get("CI_GATE_BASE_REF")
    or os.environ.get("RELEASE_SECRET_SCAN_BASE_REF")
    or "origin/main"
)
DEFAULT_DIFF_FILTER = "ACMRTUXB"
SHADOW_DIFF_FILTER = "ACDMRTUXB"
DEFAULT_OWNER_MANIFEST = Path("validation/validation_owners.json")
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.root = args.root.resolve()

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
            "classification": classification,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print_files(files, args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
