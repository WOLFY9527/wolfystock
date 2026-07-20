#!/usr/bin/env python3
"""Build, verify, list, and run the shadow domain-owned test topology."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

import pytest


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "apps" / "dsa-web"
DEFAULT_MANIFEST = ROOT / "validation" / "domain_test_topology.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BASE_SHA = "1f554d42ca7fee0e4c71f80f0b1c15680526032a"
TEST_RESULT_SCHEMA_VERSION = "wolfystock.test-result.v1"
TEST_OUTCOMES = (
    "passed",
    "failed",
    "skipped",
    "error",
    "cancelled",
    "incomplete",
    "missing",
    "unknown",
)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
GIT_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
SAFE_FAILURE_FAMILY_PATTERN = re.compile(r"[a-z0-9_.:-]+")

BACKEND_DOMAINS = (
    "auth_security",
    "provider_external_network",
    "market",
    "scanner",
    "backtest",
    "portfolio_broker",
    "database_storage_migrations",
    "api_schema_contracts",
    "runtime_operator_tooling",
    "residual_repository_integration",
)

BACKEND_DOMAIN_LABELS = {
    "auth_security": "auth/security",
    "provider_external_network": "provider/external network",
    "market": "market",
    "scanner": "scanner",
    "backtest": "backtest",
    "portfolio_broker": "portfolio/broker",
    "database_storage_migrations": "database/storage/migrations",
    "api_schema_contracts": "API/schema/contracts",
    "runtime_operator_tooling": "runtime/operator/tooling",
    "residual_repository_integration": "residual repository integration",
}

VITEST_OWNERS = {
    "milestone_t448_consumer_product": {"kind": "milestone", "milestone": "T448"},
    "milestone_t451_auth_session": {"kind": "milestone", "milestone": "T451"},
    "market": {"kind": "domain"},
    "scanner": {"kind": "domain"},
    "backtest": {"kind": "domain"},
    "portfolio_broker": {"kind": "domain"},
    "api_schema_contracts": {"kind": "domain"},
    "runtime_operator_tooling": {"kind": "domain"},
    "frontend_shared": {"kind": "domain"},
}

PLAYWRIGHT_CLASSES = (
    "route_owner",
    "bounded_integration",
    "protected_critical",
    "uat",
    "milestone",
)

PLAYWRIGHT_PROTECTED_CASE_PATTERN = re.compile(
    r"\b(?:auth|authenticated|unauthenticated|rbac|session|login|permission|capability|non-admin|protected)\b"
    r"|\bblocks? the route\b|\bdenies?\b.*\baccess\b|\badmin gating\b"
    r"|\bguest\b.*\badmin\b|\badmin\b.*\bguest\b",
    re.IGNORECASE,
)


class TopologyError(ValueError):
    """Raised when an ownership inventory is incomplete or ambiguous."""


def canonical_json_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _require_object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TopologyError(f"structured evidence {field} must be an object")
    return value


def _require_list(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise TopologyError(f"structured evidence {field} must be a list")
    return value


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise TopologyError(f"structured evidence {field} must be a non-empty string")
    return value


def _require_digest(value: object, field: str, pattern: re.Pattern[str] = SHA256_PATTERN) -> str:
    text = _require_string(value, field)
    if pattern.fullmatch(text) is None:
        raise TopologyError(f"structured evidence {field} must be a lowercase digest")
    return text


def _require_utc_timestamp(value: object, field: str) -> datetime:
    text = _require_string(value, field)
    if not text.endswith("Z"):
        raise TopologyError(f"structured evidence {field} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(f"{text[:-1]}+00:00")
    except ValueError as exc:
        raise TopologyError(f"structured evidence {field} must be a UTC timestamp") from exc
    if parsed.tzinfo != UTC:
        raise TopologyError(f"structured evidence {field} must be a UTC timestamp")
    return parsed


def _require_non_negative_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise TopologyError(f"structured evidence {field} must be a finite non-negative number")
    return float(value)


def _validate_test_result_identity(identity: object) -> dict[str, Any]:
    value = _require_object(identity, "identity")
    candidate = _require_object(value.get("candidate"), "identity.candidate")
    _require_digest(candidate.get("commitSha"), "identity.candidate.commitSha", GIT_SHA_PATTERN)
    _require_digest(candidate.get("treeSha"), "identity.candidate.treeSha", GIT_SHA_PATTERN)
    _require_digest(candidate.get("workingTreeSha256"), "identity.candidate.workingTreeSha256")
    if not isinstance(candidate.get("dirty"), bool):
        raise TopologyError("structured evidence identity.candidate.dirty must be boolean")

    environment = _require_object(value.get("environment"), "identity.environment")
    _require_digest(environment.get("fingerprint"), "identity.environment.fingerprint")

    dependency = _require_object(value.get("dependencyLock"), "identity.dependencyLock")
    _require_digest(dependency.get("contentHash"), "identity.dependencyLock.contentHash")
    _require_string(dependency.get("selectedLock"), "identity.dependencyLock.selectedLock")
    _require_string(dependency.get("selectedProjection"), "identity.dependencyLock.selectedProjection")
    _require_digest(dependency.get("selectedProjectionHash"), "identity.dependencyLock.selectedProjectionHash")

    command = _require_object(value.get("command"), "identity.command")
    argv = _require_list(command.get("argv"), "identity.command.argv")
    if not argv or any(not isinstance(argument, str) or not argument for argument in argv):
        raise TopologyError("structured evidence identity.command.argv must contain non-empty strings")
    if command.get("sha256") != canonical_json_hash(argv):
        raise TopologyError("structured evidence command identity hash mismatch")

    for field in ("selection", "topology"):
        inventory = _require_object(value.get(field), f"identity.{field}")
        count = inventory.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise TopologyError(f"structured evidence identity.{field}.count must be a non-negative integer")
        _require_digest(inventory.get("sha256"), f"identity.{field}.sha256")
    return value


def _validate_outcome_record(record: object, *, child: bool) -> dict[str, Any]:
    label = "child" if child else "parent"
    value = _require_object(record, label)
    _require_string(value.get("id"), f"{label} id")
    expected_kind = "unittest_subtest" if child else "parent"
    if value.get("kind") != expected_kind:
        raise TopologyError(f"structured evidence {label} kind must be {expected_kind}")
    owner = _require_string(value.get("owner"), f"{label} owner")
    if owner not in BACKEND_DOMAINS:
        raise TopologyError(f"structured evidence {label} owner is invalid: {owner}")
    outcome = value.get("outcome")
    if outcome not in TEST_OUTCOMES:
        raise TopologyError(f"structured evidence {label} outcome is invalid or missing")
    _require_non_negative_number(value.get("durationSeconds"), f"{label} durationSeconds")
    family = value.get("failureFamily")
    if family is not None and (not isinstance(family, str) or SAFE_FAILURE_FAMILY_PATTERN.fullmatch(family) is None):
        raise TopologyError(f"structured evidence {label} failureFamily must be null or a stable token")
    if child:
        _require_string(value.get("parentId"), "child parentId")
        _require_digest(value.get("contextSha256"), "child contextSha256")
        _require_string(value.get("presentation"), "child presentation")
    return value


def _outcome_counts(records: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(record["outcome"] for record in records)
    return {outcome: counts.get(outcome, 0) for outcome in TEST_OUTCOMES}


def _test_result_status(*, state: str, exit_code: int, counts: dict[str, dict[str, int]]) -> str:
    if state == "incomplete":
        return "incomplete"
    totals = Counter()
    for group in counts.values():
        totals.update(group)
    if exit_code == pytest.ExitCode.INTERRUPTED or totals["cancelled"]:
        return "cancelled"
    for outcome in ("missing", "incomplete", "unknown"):
        if totals[outcome]:
            return outcome
    if totals["failed"] or totals["error"]:
        return "failed"
    if exit_code != pytest.ExitCode.OK:
        return "unknown"
    if sum(totals.values()) == totals["skipped"]:
        return "skipped" if totals["skipped"] else "missing"
    return "passed"


def _test_result_exit_code(*, process_exit_code: int, status: str) -> int:
    if status in {"passed", "skipped"}:
        return process_exit_code
    return process_exit_code or 1


def validate_test_result_evidence(
    evidence: object,
    *,
    expected_identity: dict[str, Any] | None = None,
    require_completed: bool = True,
) -> dict[str, Any]:
    payload = _require_object(evidence, "root")
    if payload.get("schemaVersion") != TEST_RESULT_SCHEMA_VERSION or payload.get("kind") != "attempt":
        raise TopologyError("unsupported structured test-result schema or kind")
    state = payload.get("state")
    if state not in {"incomplete", "completed"}:
        raise TopologyError("structured evidence state must be incomplete or completed")
    if require_completed and state != "completed":
        raise TopologyError("structured test evidence is incomplete")
    if payload.get("surface") != "backend":
        raise TopologyError("structured test evidence surface must be backend")
    identity = _validate_test_result_identity(payload.get("identity"))
    if expected_identity is not None and identity != expected_identity:
        raise TopologyError("structured test evidence identity mismatch")

    attempt = _require_object(payload.get("attempt"), "attempt")
    if isinstance(attempt.get("index"), bool) or not isinstance(attempt.get("index"), int) or attempt["index"] < 0:
        raise TopologyError("structured evidence attempt.index must be a non-negative integer")
    expected_attempt_kind = "first" if attempt["index"] == 0 else "retry"
    if attempt.get("kind") != expected_attempt_kind:
        raise TopologyError("structured evidence attempt kind/index mismatch")

    timing = _require_object(payload.get("timing"), "timing")
    started_at = _require_utc_timestamp(timing.get("startedAtUtc"), "timing.startedAtUtc")
    ended_at = _require_utc_timestamp(timing.get("endedAtUtc"), "timing.endedAtUtc")
    if ended_at < started_at:
        raise TopologyError("structured evidence timing end precedes start")
    _require_non_negative_number(timing.get("wallSeconds"), "timing.wallSeconds")
    if isinstance(payload.get("exitCode"), bool) or not isinstance(payload.get("exitCode"), int):
        raise TopologyError("structured evidence exitCode must be an integer")

    parents = [
        _validate_outcome_record(record, child=False)
        for record in _require_list(payload.get("parents"), "parents")
    ]
    children = [
        _validate_outcome_record(record, child=True)
        for record in _require_list(payload.get("children"), "children")
    ]
    parent_ids = [record["id"] for record in parents]
    child_ids = [record["id"] for record in children]
    if _duplicates(parent_ids) or _duplicates(child_ids):
        raise TopologyError("structured evidence parent/child identities must be unique")
    parent_by_id = {record["id"]: record for record in parents}
    for child in children:
        parent = parent_by_id.get(child["parentId"])
        if parent is None or parent["owner"] != child["owner"]:
            raise TopologyError("structured evidence child must reference its owned parent")

    counts = _require_object(payload.get("counts"), "counts")
    expected_counts = {"parents": _outcome_counts(parents), "children": _outcome_counts(children)}
    if counts != expected_counts:
        raise TopologyError("structured evidence parent/child counts do not match records")
    selection = identity["selection"]
    if state == "completed" and (
        len(parent_ids) != selection["count"] or inventory_hash(parent_ids) != selection["sha256"]
    ):
        raise TopologyError("structured evidence completed parent inventory does not match selection identity")

    expected_status = _test_result_status(
        state=state,
        exit_code=payload["exitCode"],
        counts=expected_counts,
    )
    if state == "completed" and payload.get("status") != expected_status:
        raise TopologyError("structured evidence status does not match outcomes and exit code")
    if state == "incomplete" and payload.get("status") != "incomplete":
        raise TopologyError("incomplete structured evidence must retain incomplete status")

    artifacts = _require_list(payload.get("artifacts"), "artifacts")
    if state == "completed":
        artifact_kinds: set[str] = set()
        for raw in artifacts:
            artifact = _require_object(raw, "artifact")
            artifact_kinds.add(_require_string(artifact.get("kind"), "artifact kind"))
            path = _require_string(artifact.get("path"), "artifact path")
            if Path(path).is_absolute() or ".." in Path(path).parts:
                raise TopologyError("structured evidence artifact paths must be relative and contained")
            _require_digest(artifact.get("sha256"), "artifact sha256")
        if len(artifacts) != 2 or artifact_kinds != {"junit", "log"}:
            raise TopologyError("completed structured evidence requires exactly junit and log artifacts")
    return payload


def load_test_result_evidence(
    path: Path,
    *,
    expected_identity: dict[str, Any] | None = None,
    require_completed: bool = True,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TopologyError(f"missing or malformed structured test evidence: {path.name}") from exc
    validated = validate_test_result_evidence(
        payload,
        expected_identity=expected_identity,
        require_completed=require_completed,
    )
    if require_completed:
        for artifact in validated["artifacts"]:
            artifact_path = path.parent / artifact["path"]
            if not artifact_path.is_file() or file_hash(artifact_path) != artifact["sha256"]:
                raise TopologyError(f"structured test evidence artifact is missing or mismatched: {artifact['kind']}")
    return validated


def _git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        raise TopologyError(f"git identity command failed: git {' '.join(args)}")
    return result.stdout.strip()


def _working_tree_fingerprint() -> str:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
    )
    if result.returncode:
        raise TopologyError("candidate working-tree inventory failed")
    digest = hashlib.sha256()
    paths = sorted(path for path in result.stdout.split(b"\0") if path)
    for raw_path in paths:
        relative = raw_path.decode("utf-8", errors="surrogateescape")
        path = ROOT / relative
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
    return digest.hexdigest()


def build_test_result_identity(
    manifest: dict[str, Any],
    *,
    command: Sequence[str],
    selected_ids: Sequence[str],
) -> dict[str, Any]:
    environment_fingerprint = os.environ.get("WOLFYSTOCK_ENV_FINGERPRINT", "")
    if SHA256_PATTERN.fullmatch(environment_fingerprint) is None:
        raise TopologyError("WOLFYSTOCK_ENV_FINGERPRINT is required for structured test evidence")

    from scripts.environment.python_lock import load_python_lock

    lock = load_python_lock(
        ROOT,
        os_name=platform.system(),
        architecture=platform.machine(),
        python_version=platform.python_version(),
        python_implementation=platform.python_implementation(),
        profile="development",
    ).evidence()
    topology_inventory = manifest["backend"]["currentInventory"]
    status = _git_output("status", "--porcelain", "--untracked-files=all")
    identity = {
        "candidate": {
            "commitSha": _git_output("rev-parse", "HEAD"),
            "treeSha": _git_output("rev-parse", "HEAD^{tree}"),
            "workingTreeSha256": _working_tree_fingerprint(),
            "dirty": bool(status),
        },
        "environment": {"fingerprint": environment_fingerprint},
        "dependencyLock": {
            "contentHash": lock["contentHash"],
            "selectedLock": lock["selectedLock"],
            "selectedProjection": lock["selectedProjection"],
            "selectedProjectionHash": lock["selectedProjectionHash"],
        },
        "command": {"argv": list(command), "sha256": canonical_json_hash(list(command))},
        "selection": {"count": len(selected_ids), "sha256": inventory_hash(selected_ids)},
        "topology": {
            "count": topology_inventory["count"],
            "sha256": topology_inventory["sha256"],
        },
    }
    return _validate_test_result_identity(identity)


def inventory_hash(values: Iterable[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def _duplicates(values: Sequence[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def compare_inventory(expected: Iterable[str], actual: Iterable[str]) -> dict[str, list[str]]:
    expected_list = list(expected)
    actual_list = list(actual)
    return {
        "duplicateExpected": _duplicates(expected_list),
        "duplicateActual": _duplicates(actual_list),
        "missing": sorted(set(expected_list) - set(actual_list)),
        "unowned": sorted(set(actual_list) - set(expected_list)),
    }


def _raise_inventory_mismatch(surface: str, comparison: dict[str, list[str]]) -> None:
    failures = {key: value for key, value in comparison.items() if value}
    if failures:
        raise TopologyError(f"{surface} inventory mismatch: {json.dumps(failures, ensure_ascii=False)}")


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TopologyError("domain topology manifest root must be an object")
    return payload


def _validate_backend(manifest: dict[str, Any]) -> dict[str, int]:
    backend = manifest.get("backend")
    if not isinstance(backend, dict):
        raise TopologyError("backend must be an object")
    if tuple(backend.get("domainOrder", [])) != BACKEND_DOMAINS:
        raise TopologyError("backend.domainOrder must equal the canonical domain order")
    domains = backend.get("domains")
    if not isinstance(domains, dict) or set(domains) != set(BACKEND_DOMAINS):
        raise TopologyError("backend.domains must define every canonical domain exactly once")
    entries = backend.get("tests")
    if not isinstance(entries, list) or not entries:
        raise TopologyError("backend.tests must be a non-empty list")
    ids = [entry.get("id") for entry in entries if isinstance(entry, dict)]
    if len(ids) != len(entries) or any(not isinstance(nodeid, str) or not nodeid for nodeid in ids):
        raise TopologyError("every backend test entry requires a non-empty id")
    duplicates = _duplicates(ids)
    if duplicates:
        raise TopologyError(f"duplicate backend ownership: {duplicates[:10]}")
    if ids != sorted(ids):
        raise TopologyError("backend.tests must be sorted deterministically by id")
    invalid_domains = sorted(
        {entry.get("domain") for entry in entries if entry.get("domain") not in BACKEND_DOMAINS}, key=str
    )
    if invalid_domains:
        raise TopologyError(f"backend tests reference invalid domains: {invalid_domains}")
    missing_domains = sorted(set(BACKEND_DOMAINS) - {entry["domain"] for entry in entries})
    if missing_domains:
        raise TopologyError(f"backend domains have no owned tests: {missing_domains}")
    if any(not isinstance(entry.get("baseline"), bool) for entry in entries):
        raise TopologyError("every backend test entry requires a boolean baseline flag")

    baseline_ids = [entry["id"] for entry in entries if entry["baseline"]]
    baseline_gaps = backend.get("baselineCollectionGaps", [])
    if (
        not isinstance(baseline_gaps, list)
        or any(not isinstance(nodeid, str) or not nodeid for nodeid in baseline_gaps)
        or baseline_gaps != sorted(set(baseline_gaps))
    ):
        raise TopologyError("backend.baselineCollectionGaps must be a unique, sorted list of test IDs")
    if set(baseline_gaps) & set(ids):
        raise TopologyError("backend.baselineCollectionGaps must only contain tests absent from current discovery")
    historical_baseline_ids = [*baseline_ids, *baseline_gaps]
    baseline = backend.get("baselineCapture", {})
    if baseline.get("baseSha") != BASE_SHA:
        raise TopologyError(f"backend baseline baseSha must be {BASE_SHA}")
    if baseline.get("count") != len(historical_baseline_ids) or baseline.get("sha256") != inventory_hash(
        historical_baseline_ids
    ):
        raise TopologyError("backend baseline capture count/hash does not match baseline entries and collection gaps")
    current = backend.get("currentInventory", {})
    if current.get("count") != len(ids) or current.get("sha256") != inventory_hash(ids):
        raise TopologyError("backend current inventory count/hash does not match test entries")
    network_entries = backend.get("networkTests")
    if not isinstance(network_entries, list):
        raise TopologyError("backend.networkTests must be a list")
    network_ids = [entry.get("id") for entry in network_entries if isinstance(entry, dict)]
    if len(network_ids) != len(network_entries) or _duplicates(network_ids):
        raise TopologyError("backend.networkTests contains malformed or duplicate entries")
    if sorted(network_ids) != network_ids or not set(network_ids).issubset(ids):
        raise TopologyError("backend.networkTests must be sorted and owned by backend.tests")
    for entry in network_entries:
        if any(not entry.get(field) for field in ("owner", "reason", "audit")):
            raise TopologyError(f"network test lacks audited marker fields: {entry.get('id')}")
    known = backend.get("knownBaselineFailures", [])
    if not isinstance(known, list) or known != sorted(set(known)):
        raise TopologyError("backend.knownBaselineFailures must be a unique, sorted list")
    if not set(known).issubset(historical_baseline_ids):
        raise TopologyError("backend.knownBaselineFailures must reference baseline-owned test IDs")
    return {
        "backendTests": len(ids),
        "baselineBackendTests": len(historical_baseline_ids),
        "networkTests": len(network_ids),
    }


def _validate_vitest(manifest: dict[str, Any]) -> dict[str, int]:
    vitest = manifest.get("vitest")
    if not isinstance(vitest, dict):
        raise TopologyError("vitest must be an object")
    owners = vitest.get("owners")
    if not isinstance(owners, dict) or set(owners) != set(VITEST_OWNERS):
        raise TopologyError("vitest.owners must equal the canonical owner set")
    entries = vitest.get("files")
    if not isinstance(entries, list) or not entries:
        raise TopologyError("vitest.files must be a non-empty list")
    paths = [entry.get("path") for entry in entries if isinstance(entry, dict)]
    if len(paths) != len(entries) or _duplicates(paths) or paths != sorted(paths):
        raise TopologyError("vitest.files must contain unique, sorted paths")
    invalid = sorted({entry.get("owner") for entry in entries if entry.get("owner") not in owners}, key=str)
    if invalid:
        raise TopologyError(f"vitest files reference invalid owners: {invalid}")
    inventory = vitest.get("inventory", {})
    if inventory.get("count") != len(paths) or inventory.get("sha256") != inventory_hash(paths):
        raise TopologyError("vitest inventory count/hash does not match files")
    entry_by_path = {entry["path"]: entry for entry in entries}
    large = vitest.get("largeOwnerFiles")
    if not isinstance(large, list):
        raise TopologyError("vitest.largeOwnerFiles must be a list")
    large_paths = [entry.get("path") for entry in large if isinstance(entry, dict)]
    if _duplicates(large_paths) or large_paths != sorted(large_paths):
        raise TopologyError("vitest.largeOwnerFiles must contain unique, sorted paths")
    for entry in large:
        owned = entry_by_path.get(entry.get("path"))
        if owned is None or entry.get("owner") != owned["owner"]:
            raise TopologyError(f"large Vitest file is not consistently owned: {entry.get('path')}")
    return {"vitestFiles": len(paths), "largeVitestFiles": len(large)}


def _validate_playwright(manifest: dict[str, Any]) -> dict[str, int]:
    playwright = manifest.get("playwright")
    if not isinstance(playwright, dict):
        raise TopologyError("playwright must be an object")
    if tuple(playwright.get("ownershipClasses", [])) != PLAYWRIGHT_CLASSES:
        raise TopologyError("playwright.ownershipClasses must equal the canonical class order")
    projects = playwright.get("projects")
    if not isinstance(projects, list) or not projects:
        raise TopologyError("playwright.projects must be non-empty")
    specs = playwright.get("specs")
    cases = playwright.get("projectCases")
    if not isinstance(specs, list) or not isinstance(cases, list):
        raise TopologyError("playwright specs/projectCases must be lists")
    spec_paths = [entry.get("path") for entry in specs if isinstance(entry, dict)]
    case_ids = [entry.get("id") for entry in cases if isinstance(entry, dict)]
    if _duplicates(spec_paths) or spec_paths != sorted(spec_paths):
        raise TopologyError("playwright.specs must contain unique, sorted paths")
    if _duplicates(case_ids) or case_ids != sorted(case_ids):
        raise TopologyError("playwright.projectCases must contain unique, sorted IDs")
    spec_by_path = {entry["path"]: entry for entry in specs}
    for spec in specs:
        owner = spec.get("owner")
        if owner not in PLAYWRIGHT_CLASSES:
            raise TopologyError(f"invalid Playwright owner for {spec.get('path')}: {owner}")
        if spec.get("mandatory") is not (owner == "protected_critical"):
            raise TopologyError(f"Playwright spec mandatory flag is inconsistent: {spec.get('path')}")
        if re.search(r"auth|rbac|session", spec["path"], re.IGNORECASE):
            if owner != "protected_critical" or spec.get("mandatory") is not True:
                raise TopologyError(f"protected auth/RBAC/session spec is not mandatory: {spec['path']}")
    for case in cases:
        spec = spec_by_path.get(case.get("spec"))
        if spec is None:
            raise TopologyError(f"Playwright case has no owned spec: {case.get('id')}")
        protected = spec["owner"] == "protected_critical" or playwright_case_requires_protection(case.get("id", ""))
        expected_owner = "protected_critical" if protected else spec["owner"]
        if case.get("owner") != expected_owner:
            raise TopologyError(f"Playwright case has inconsistent protected/spec ownership: {case.get('id')}")
        if case.get("project") not in projects:
            raise TopologyError(f"Playwright case has unknown project: {case.get('id')}")
        if case.get("mandatory") is not protected:
            raise TopologyError(f"Playwright case mandatory flag is inconsistent: {case.get('id')}")
    inventory = playwright.get("inventory", {})
    if inventory.get("specCount") != len(spec_paths) or inventory.get("specSha256") != inventory_hash(spec_paths):
        raise TopologyError("Playwright spec inventory count/hash does not match specs")
    if inventory.get("projectCaseCount") != len(case_ids) or inventory.get("projectCaseSha256") != inventory_hash(
        case_ids
    ):
        raise TopologyError("Playwright project-case inventory count/hash does not match cases")
    if Counter(case["project"] for case in cases) != Counter(inventory.get("projectCaseCounts", {})):
        raise TopologyError("Playwright per-project case counts do not match inventory")
    return {"playwrightSpecs": len(spec_paths), "playwrightProjectCases": len(case_ids)}


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schemaVersion") != 1 or manifest.get("manifestVersion") != "1.0.0":
        raise TopologyError("unsupported domain topology schema/manifest version")
    if manifest.get("shadowOnly") is not True:
        raise TopologyError("domain topology must remain shadowOnly")
    counts = {}
    counts.update(_validate_backend(manifest))
    counts.update(_validate_vitest(manifest))
    counts.update(_validate_playwright(manifest))
    return {"status": "valid", **counts}


def _run_json_command(command: Sequence[str], *, cwd: Path) -> Any:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode:
        output = (result.stdout + "\n" + result.stderr)[-6000:]
        raise TopologyError(f"collection command failed ({result.returncode}): {' '.join(command)}\n{output}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise TopologyError(f"collection command did not return JSON: {' '.join(command)}") from exc


def _npm_command(*args: str) -> list[str]:
    return ["npm.cmd" if os.name == "nt" else "npm", "exec", "--", *args]


def discover_backend(*, bootstrap: bool = False) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="domain-topology-") as temporary:
        output = Path(temporary) / "backend-collection.json"
        command = [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-qq",
            "--disable-warnings",
            "--domain-topology-collect-output",
            str(output),
        ]
        command.append("--domain-topology-bootstrap" if bootstrap else "--domain-topology-verify-full")
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace")
        if result.returncode or not output.exists():
            detail = (result.stdout + "\n" + result.stderr)[-8000:]
            raise TopologyError(f"backend collection failed ({result.returncode})\n{detail}")
        payload = json.loads(output.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {"ids": payload, "networkTests": []}
    return payload


def discover_vitest_files() -> list[str]:
    payload = _run_json_command(_npm_command("vitest", "list", "--filesOnly", "--json"), cwd=WEB_ROOT)
    raw = payload.get("testFiles") or payload.get("files") or [] if isinstance(payload, dict) else payload
    files: list[str] = []
    for item in raw:
        value = item if isinstance(item, str) else item.get("filepath") or item.get("file") or item.get("name")
        path = Path(value).resolve()
        try:
            files.append(path.relative_to(ROOT).as_posix())
        except ValueError as exc:
            raise TopologyError(f"Vitest discovered a file outside the repository: {path}") from exc
    return sorted(files)


def _playwright_spec_path(raw: str) -> str:
    normalized = raw.replace("\\", "/")
    if normalized.startswith("apps/dsa-web/"):
        return normalized
    if normalized.startswith("e2e/"):
        return f"apps/dsa-web/{normalized}"
    return f"apps/dsa-web/e2e/{normalized}"


def _walk_playwright_suite(
    suite: dict[str, Any],
    cases: list[dict[str, Any]],
    parents: tuple[str, ...] = (),
) -> None:
    title = suite.get("title") or ""
    next_parents = parents + ((title,) if title else ())
    suite_file = suite.get("file") or ""
    for spec in suite.get("specs", []):
        path = _playwright_spec_path(spec.get("file") or suite_file)
        titles = next_parents + ((spec.get("title") or "<untitled>"),)
        for test in spec.get("tests", []):
            project = test.get("projectName") or test.get("projectId") or ""
            case_id = f"{project}::{path}::{' › '.join(titles)}"
            cases.append({"id": case_id, "spec": path, "project": project})
    for child in suite.get("suites", []):
        _walk_playwright_suite(child, cases, next_parents)


def discover_playwright() -> tuple[list[str], list[dict[str, str]]]:
    payload = _run_json_command(_npm_command("playwright", "test", "--list", "--reporter=json"), cwd=WEB_ROOT)
    cases: list[dict[str, str]] = []
    for suite in payload.get("suites", []):
        _walk_playwright_suite(suite, cases)
    case_ids = [case["id"] for case in cases]
    if _duplicates(case_ids):
        raise TopologyError(f"Playwright collection produced duplicate project cases: {_duplicates(case_ids)[:10]}")
    cases.sort(key=lambda item: item["id"])
    return sorted({case["spec"] for case in cases}), cases


def classify_backend(nodeid: str) -> str:
    path = nodeid.split("::", 1)[0].lower()
    if path.startswith("tests/scripts/"):
        return "runtime_operator_tooling"
    rules = (
        ("auth_security", r"auth|rbac|security|mfa|csrf|cors|password|session|token|login|credential"),
        ("backtest", r"backtest|walk_forward|execution_model|benchmark"),
        ("portfolio_broker", r"portfolio|broker|ibkr|holding|ledger|cost_basis|transaction|accounting|\bfx\b"),
        ("scanner", r"scanner|universe"),
        (
            "database_storage_migrations",
            r"database|migration|storage|repository|persistence|backup|restore|pitr|retention|postgres|sqlite|db_",
        ),
        (
            "provider_external_network",
            r"provider|offline_network|yfinance|akshare|efinance|tushare|pytdx|baostock|tickflow|coinbase|data_source|searx|search_|sec_edgar|official_macro_transport|notification_sender",
        ),
        ("market", r"market|stock|quote|price|ohlcv|options|liquidity|rotation|macro|breadth|fundamental|symbol"),
    )
    for domain, pattern in rules:
        if re.search(pattern, path):
            return domain
    if path.startswith("tests/api/") or re.search(r"schema|contract|endpoint|openapi|api_", path):
        return "api_schema_contracts"
    if re.search(r"runtime|operator|tool|cli|script|config|deploy|release|uat|workflow|manual|asset|smoke", path):
        return "runtime_operator_tooling"
    return "residual_repository_integration"


def classify_vitest(path: str) -> str:
    lowered = path.lower()
    if re.search(r"auth|session|login|resetpassword|password|rbac", lowered):
        return "milestone_t451_auth_session"
    if re.search(r"backtest", lowered):
        return "backtest"
    if re.search(r"portfolio|broker|ibkr|holding", lowered):
        return "portfolio_broker"
    if re.search(r"scanner|watchlist|stockpool", lowered):
        return "scanner"
    if re.search(r"market|rotation|liquidity|chart|quote|options|stockstructure", lowered):
        return "market"
    if "/pages/__tests__/" in lowered and not re.search(r"/admin|settings|system", lowered):
        return "milestone_t448_consumer_product"
    if re.search(r"api|schema|contract|client", lowered):
        return "api_schema_contracts"
    if re.search(r"admin|settings|design-constitution|taskqueue|routing", lowered):
        return "runtime_operator_tooling"
    return "frontend_shared"


def classify_playwright(path: str) -> str:
    name = Path(path).name.lower()
    if re.search(r"auth|rbac|session|no-secret|critical-route|public-safety|runtime-contract|route-truth", name):
        return "protected_critical"
    if re.search(r"uat|controlled-user-testing|browser-qualification|readiness-browser|ux-audit", name):
        return "uat"
    if re.match(r"(?:t|g)\d+", name):
        return "milestone"
    if re.match(r"admin|backtest|home|market|portfolio|rotation|scanner|settings|watchlist", name) and ".smoke." not in name:
        return "route_owner"
    return "bounded_integration"


def playwright_case_requires_protection(case_id: str) -> bool:
    return PLAYWRIGHT_PROTECTED_CASE_PATTERN.search(case_id) is not None


def _large_vitest_files(files: list[dict[str, str]], threshold: int) -> list[dict[str, Any]]:
    large: list[dict[str, Any]] = []
    for entry in files:
        path = ROOT / entry["path"]
        size = path.stat().st_size
        if size < threshold:
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        large.append({"path": entry["path"], "owner": entry["owner"], "bytes": size, "lines": line_count})
    return sorted(large, key=lambda item: item["path"])


def build_manifest(
    *,
    baseline_backend_ids: set[str],
    known_baseline_failures: set[str],
    base_sha: str,
    capture_date: str,
) -> dict[str, Any]:
    if base_sha != BASE_SHA:
        raise TopologyError(f"capture base must be {BASE_SHA}")
    backend = discover_backend(bootstrap=True)
    backend_ids = sorted(backend["ids"])
    missing_baseline = sorted(baseline_backend_ids - set(backend_ids))
    unknown_baseline_failures = sorted(known_baseline_failures - baseline_backend_ids)
    if unknown_baseline_failures:
        raise TopologyError(f"known failures are not baseline backend tests: {unknown_baseline_failures[:10]}")
    backend_entries = [
        {"id": nodeid, "domain": classify_backend(nodeid), "baseline": nodeid in baseline_backend_ids}
        for nodeid in backend_ids
    ]
    vitest_paths = discover_vitest_files()
    vitest_files = [{"path": path, "owner": classify_vitest(path)} for path in vitest_paths]
    spec_paths, raw_cases = discover_playwright()
    specs = []
    for path in spec_paths:
        owner = classify_playwright(path)
        specs.append({"path": path, "owner": owner, "mandatory": owner == "protected_critical"})
    owner_by_spec = {spec["path"]: spec for spec in specs}
    cases = []
    for case in raw_cases:
        spec_owner = owner_by_spec[case["spec"]]["owner"]
        owner = "protected_critical" if playwright_case_requires_protection(case["id"]) else spec_owner
        cases.append({**case, "owner": owner, "mandatory": owner == "protected_critical"})
    project_counts = dict(sorted(Counter(case["project"] for case in cases).items()))
    return {
        "schemaVersion": 1,
        "manifestVersion": "1.0.0",
        "shadowOnly": True,
        "capturedOn": capture_date,
        "authoritativeGates": [
            "bash scripts/ci_gate.sh",
            "cd apps/dsa-web && npm test",
            "cd apps/dsa-web && npm run test:e2e",
        ],
        "backend": {
            "domainOrder": list(BACKEND_DOMAINS),
            "domains": {domain: {"label": BACKEND_DOMAIN_LABELS[domain]} for domain in BACKEND_DOMAINS},
            "baselineCapture": {
                "baseSha": base_sha,
                "count": len(baseline_backend_ids),
                "sha256": inventory_hash(baseline_backend_ids),
            },
            "currentInventory": {"count": len(backend_ids), "sha256": inventory_hash(backend_ids)},
            "tests": backend_entries,
            "baselineCollectionGaps": missing_baseline,
            "networkTests": sorted(backend.get("networkTests", []), key=lambda item: item["id"]),
            "knownBaselineFailures": sorted(known_baseline_failures),
            "offlinePolicy": {
                "default": "deny_non_loopback_sockets",
                "networkMarkerFields": ["owner", "reason", "audit"],
                "explicitOptIn": "python -m pytest -m network --allow-test-network --network-audit <audit-id>",
                "standardAndLandBehavior": "network_marked_tests_skipped_and_all_other_tests_socket_denied",
            },
        },
        "vitest": {
            "owners": VITEST_OWNERS,
            "inventory": {"count": len(vitest_paths), "sha256": inventory_hash(vitest_paths)},
            "files": vitest_files,
            "largeFileThresholdBytes": 50_000,
            "largeOwnerFiles": _large_vitest_files(vitest_files, 50_000),
        },
        "playwright": {
            "ownershipClasses": list(PLAYWRIGHT_CLASSES),
            "projects": sorted(project_counts),
            "inventory": {
                "specCount": len(spec_paths),
                "specSha256": inventory_hash(spec_paths),
                "projectCaseCount": len(cases),
                "projectCaseSha256": inventory_hash(case["id"] for case in cases),
                "projectCaseCounts": project_counts,
            },
            "specs": specs,
            "projectCases": cases,
            "attemptRecording": {
                "source": "Playwright JSON reporter",
                "firstAttemptSelector": "retry == 0",
                "retrySelector": "retry > 0",
                "normalizer": "python scripts/domain_test_topology.py record-playwright",
            },
            "caseOwnerPolicy": "protected behavior overrides spec ownership; all other cases inherit the spec owner",
        },
    }


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def verify_backend(manifest: dict[str, Any]) -> dict[str, Any]:
    discovered = discover_backend()
    expected = [entry["id"] for entry in manifest["backend"]["tests"]]
    _raise_inventory_mismatch("backend", compare_inventory(expected, discovered["ids"]))
    expected_network = manifest["backend"]["networkTests"]
    if discovered.get("networkTests", []) != expected_network:
        raise TopologyError("backend audited network marker inventory differs from the manifest")
    return {"count": len(expected), "sha256": inventory_hash(expected), "networkCount": len(expected_network)}


def verify_vitest(manifest: dict[str, Any]) -> dict[str, Any]:
    actual = discover_vitest_files()
    expected = [entry["path"] for entry in manifest["vitest"]["files"]]
    _raise_inventory_mismatch("Vitest", compare_inventory(expected, actual))
    return {"count": len(expected), "sha256": inventory_hash(expected)}


def verify_playwright(manifest: dict[str, Any]) -> dict[str, Any]:
    actual_specs, actual_cases = discover_playwright()
    expected_specs = [entry["path"] for entry in manifest["playwright"]["specs"]]
    expected_cases = [entry["id"] for entry in manifest["playwright"]["projectCases"]]
    _raise_inventory_mismatch("Playwright specs", compare_inventory(expected_specs, actual_specs))
    _raise_inventory_mismatch(
        "Playwright project cases", compare_inventory(expected_cases, [entry["id"] for entry in actual_cases])
    )
    return {
        "specCount": len(expected_specs),
        "projectCaseCount": len(expected_cases),
        "projectCaseCounts": dict(sorted(Counter(entry["project"] for entry in actual_cases).items())),
    }


_ACTIVE_TEST_RESULT_CONFIG: pytest.Config | None = None


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("structured-test-result", "versioned structured test-result evidence")
    group.addoption("--test-result-evidence-output", default=None, metavar="PATH")
    group.addoption("--test-result-evidence-context", default=None, metavar="PATH")


def pytest_configure(config: pytest.Config) -> None:
    global _ACTIVE_TEST_RESULT_CONFIG
    output = config.getoption("--test-result-evidence-output")
    context_path = config.getoption("--test-result-evidence-context")
    if not output and not context_path:
        return
    if not output or not context_path:
        raise pytest.UsageError("structured test evidence requires both output and context paths")
    try:
        context = json.loads(Path(context_path).read_text(encoding="utf-8"))
        identity = _validate_test_result_identity(context.get("identity"))
        attempt = _require_object(context.get("attempt"), "attempt")
        manifest = load_manifest()
        validate_manifest(manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise pytest.UsageError(f"invalid structured test evidence context: {exc}") from exc
    config._test_result_evidence = {  # type: ignore[attr-defined]
        "output": Path(output),
        "identity": identity,
        "attempt": attempt,
        "startedAtUtc": _utc_now(),
        "timer": time.perf_counter(),
        "parents": {},
        "children": [],
        "childOrdinals": Counter(),
        "owners": {entry["id"]: entry["domain"] for entry in manifest["backend"]["tests"]},
        "selectedIds": [],
    }
    _ACTIVE_TEST_RESULT_CONFIG = config


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    state = getattr(config, "_test_result_evidence", None)
    if state is not None:
        state["selectedIds"] = [item.nodeid for item in items]


def pytest_collection_finish(session: pytest.Session) -> None:
    state = getattr(session.config, "_test_result_evidence", None)
    if state is not None:
        state["selectedIds"] = [item.nodeid for item in session.items]


def _report_failure_family(report: pytest.TestReport) -> str | None:
    for name, raw_value in getattr(report, "user_properties", []):
        if name != "failure_family":
            continue
        if not isinstance(raw_value, str):
            raise TopologyError("failure_family test property must be a stable token")
        value = raw_value.strip().lower()
        if SAFE_FAILURE_FAMILY_PATTERN.fullmatch(value) is None:
            raise TopologyError("failure_family test property must be a stable token")
        return value
    return None


def _report_outcome(report: pytest.TestReport) -> str:
    if report.passed:
        return "passed"
    if report.skipped:
        return "skipped"
    return "failed"


def _stable_subtest_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return {"pythonType": "builtins.float", "sha256": hashlib.sha256(repr(value).encode()).hexdigest()}
    if isinstance(value, bytes):
        return {"pythonType": "builtins.bytes", "sha256": hashlib.sha256(value).hexdigest()}
    if isinstance(value, dict):
        entries = [
            [_stable_subtest_value(key), _stable_subtest_value(item)]
            for key, item in value.items()
        ]
        return {"pythonType": "builtins.dict", "entries": sorted(entries, key=canonical_json_hash)}
    if isinstance(value, (list, tuple)):
        return {
            "pythonType": f"builtins.{type(value).__name__}",
            "items": [_stable_subtest_value(item) for item in value],
        }
    if isinstance(value, (set, frozenset)):
        items = [_stable_subtest_value(item) for item in value]
        return {
            "pythonType": f"builtins.{type(value).__name__}",
            "items": sorted(items, key=canonical_json_hash),
        }
    value_type = type(value)
    return {"pythonType": f"{value_type.__module__}.{value_type.__qualname__}"}


@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    config = _ACTIVE_TEST_RESULT_CONFIG
    if config is None:
        return
    state = getattr(config, "_test_result_evidence", None)
    if state is None:
        return
    owner = state["owners"].get(report.nodeid)
    if owner is None:
        return
    context = getattr(report, "context", None)
    if context is not None:
        context_payload = {
            "message": _stable_subtest_value(context.msg),
            "parameters": _stable_subtest_value(dict(context.kwargs)),
        }
        context_hash = canonical_json_hash(context_payload)
        ordinal_key = (report.nodeid, context_hash)
        ordinal = state["childOrdinals"][ordinal_key]
        state["childOrdinals"][ordinal_key] += 1
        outcome = _report_outcome(report)
        status = "SUBFAILED" if outcome == "failed" else "SUBSKIPPED" if outcome == "skipped" else "SUBPASSED"
        state["children"].append(
            {
                "id": f"{report.nodeid}::subtest:{context_hash}:{ordinal}",
                "parentId": report.nodeid,
                "kind": "unittest_subtest",
                "owner": owner,
                "outcome": outcome,
                "failureFamily": _report_failure_family(report),
                "durationSeconds": round(float(report.duration), 6),
                "contextSha256": context_hash,
                "presentation": f"{status}(<context:{context_hash[:12]}>)",
            }
        )
        return

    record = state["parents"].setdefault(
        report.nodeid,
        {
            "id": report.nodeid,
            "kind": "parent",
            "owner": owner,
            "outcome": None,
            "failureFamily": None,
            "durationSeconds": 0.0,
        },
    )
    record["durationSeconds"] = round(record["durationSeconds"] + float(report.duration), 6)
    if report.when == "setup" and report.skipped:
        record["outcome"] = "skipped"
    elif report.when == "setup" and report.failed:
        record["outcome"] = "error"
    elif report.when == "call":
        record["outcome"] = _report_outcome(report)
        record["failureFamily"] = _report_failure_family(report)
    elif report.when == "teardown" and report.failed:
        record["outcome"] = "error"
        record["failureFamily"] = _report_failure_family(report)


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    global _ACTIVE_TEST_RESULT_CONFIG
    state = getattr(session.config, "_test_result_evidence", None)
    if state is None:
        return
    unreported_outcome = (
        "cancelled"
        if exitstatus == pytest.ExitCode.INTERRUPTED
        else "unknown"
        if exitstatus in {pytest.ExitCode.INTERNAL_ERROR, pytest.ExitCode.USAGE_ERROR, pytest.ExitCode.NO_TESTS_COLLECTED}
        else "missing"
    )
    parents = []
    for nodeid in state["selectedIds"]:
        record = state["parents"].get(nodeid)
        if record is None:
            record = {
                "id": nodeid,
                "kind": "parent",
                "owner": state["owners"][nodeid],
                "outcome": unreported_outcome,
                "failureFamily": None,
                "durationSeconds": 0.0,
            }
        elif record["outcome"] not in TEST_OUTCOMES:
            record["outcome"] = unreported_outcome
        parents.append(record)
    parents.sort(key=lambda record: record["id"])
    children = sorted(state["children"], key=lambda record: record["id"])
    payload = {
        "schemaVersion": TEST_RESULT_SCHEMA_VERSION,
        "kind": "attempt",
        "state": "incomplete",
        "surface": "backend",
        "identity": state["identity"],
        "attempt": state["attempt"],
        "timing": {
            "startedAtUtc": state["startedAtUtc"],
            "endedAtUtc": _utc_now(),
            "wallSeconds": round(time.perf_counter() - state["timer"], 6),
        },
        "exitCode": int(exitstatus),
        "status": "incomplete",
        "counts": {"parents": _outcome_counts(parents), "children": _outcome_counts(children)},
        "parents": parents,
        "children": children,
        "artifacts": [],
    }
    write_json(state["output"], payload)
    _ACTIVE_TEST_RESULT_CONFIG = None


def _backend_command(*extra: str) -> list[str]:
    return [sys.executable, "-m", "pytest", "-q", "--tb=short", *extra]


def _display_command(command: Sequence[str], *, output_dir: Path) -> list[str]:
    displayed: list[str] = []
    root = str(ROOT)
    output = str(output_dir)
    for argument in command:
        value = "$PYTHON" if argument == sys.executable else argument
        value = value.replace(output, "$OUTPUT").replace(root, "$ROOT")
        displayed.append(value)
    return displayed


def _run_logged(command: Sequence[str], *, log_path: Path) -> int:
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log.write(line)
            log.flush()
        return process.wait()


def _attempt_summary(attempt: dict[str, Any], path: Path) -> dict[str, Any]:
    failures = _failed_parent_ids(attempt)
    return {
        "path": path.name,
        "sha256": file_hash(path),
        "state": attempt["state"],
        "attemptIndex": attempt["attempt"]["index"],
        "startedAtUtc": attempt["timing"]["startedAtUtc"],
        "endedAtUtc": attempt["timing"]["endedAtUtc"],
        "durationSeconds": attempt["timing"]["wallSeconds"],
        "exitCode": attempt["exitCode"],
        "status": attempt["status"],
        "counts": attempt["counts"],
        "failures": failures,
        "identity": attempt["identity"],
    }


def _failed_parent_ids(attempt: dict[str, Any]) -> list[str]:
    failed = {
        record["id"]
        for record in attempt["parents"]
        if record["outcome"] in {"failed", "error"}
    }
    failed.update(
        record["parentId"]
        for record in attempt["children"]
        if record["outcome"] in {"failed", "error"}
    )
    return sorted(failed)


def _run_backend_attempt(
    manifest: dict[str, Any],
    *,
    output_dir: Path,
    selected_ids: Sequence[str],
    attempt_index: int,
    selection_args: Sequence[str],
) -> tuple[int, dict[str, Any], Path]:
    attempt_path = output_dir / f"attempt-{attempt_index}.json"
    context_path = output_dir / f"attempt-{attempt_index}-context.json"
    log_path = output_dir / f"attempt-{attempt_index}.log"
    junit_path = output_dir / f"attempt-{attempt_index}.junit.xml"
    topology_args = ("--domain-topology-verify-full",) if attempt_index == 0 else ()
    command = _backend_command(
        "-p",
        "scripts.domain_test_topology",
        *topology_args,
        "--test-result-evidence-output",
        str(attempt_path),
        "--test-result-evidence-context",
        str(context_path),
        f"--junitxml={junit_path}",
        *selection_args,
    )
    identity = build_test_result_identity(
        manifest,
        command=_display_command(command, output_dir=output_dir),
        selected_ids=selected_ids,
    )
    attempt = {"index": attempt_index, "kind": "first" if attempt_index == 0 else "retry"}
    started_at = _utc_now()
    write_json(context_path, {"identity": identity, "attempt": attempt})
    write_json(
        attempt_path,
        {
            "schemaVersion": TEST_RESULT_SCHEMA_VERSION,
            "kind": "attempt",
            "state": "incomplete",
            "surface": "backend",
            "identity": identity,
            "attempt": attempt,
            "timing": {"startedAtUtc": started_at, "endedAtUtc": started_at, "wallSeconds": 0.0},
            "exitCode": 2,
            "status": "incomplete",
            "counts": {
                "parents": {outcome: 0 for outcome in TEST_OUTCOMES},
                "children": {outcome: 0 for outcome in TEST_OUTCOMES},
            },
            "parents": [],
            "children": [],
            "artifacts": [],
        },
    )

    process_rc = _run_logged(command, log_path=log_path)
    raw = load_test_result_evidence(
        attempt_path,
        expected_identity=identity,
        require_completed=False,
    )
    if raw["attempt"] != attempt or raw["exitCode"] != process_rc:
        raise TopologyError("structured test evidence attempt or exit-code identity mismatch")
    parent_ids = [record["id"] for record in raw["parents"]]
    if len(parent_ids) != len(selected_ids) or inventory_hash(parent_ids) != inventory_hash(selected_ids):
        raise TopologyError("structured test evidence remained incomplete: parent inventory differs from selection")
    if not log_path.is_file() or not junit_path.is_file():
        raise TopologyError("structured test evidence remained incomplete: log or JUnit artifact missing")

    raw["state"] = "completed"
    raw["status"] = _test_result_status(
        state=raw["state"],
        exit_code=process_rc,
        counts=raw["counts"],
    )
    raw["artifacts"] = [
        {"kind": "junit", "path": junit_path.name, "sha256": file_hash(junit_path)},
        {"kind": "log", "path": log_path.name, "sha256": file_hash(log_path)},
    ]
    validate_test_result_evidence(raw, expected_identity=identity)
    write_json(attempt_path, raw)
    raw = load_test_result_evidence(attempt_path, expected_identity=identity)
    context_path.unlink()
    return process_rc, raw, attempt_path


def classify_failures(failures: Iterable[str], known_baseline_failures: Iterable[str]) -> dict[str, list[str]]:
    failure_set = set(failures)
    known = set(known_baseline_failures)
    return {
        "establishedBaselineFailures": sorted(failure_set & known),
        "unknownFirstAttemptFailures": sorted(failure_set - known),
    }


def run_backend(
    manifest: dict[str, Any],
    *,
    output_dir: Path,
    domains: Sequence[str],
    retry_failures: int,
) -> tuple[int, dict[str, Any]]:
    invalid = sorted(set(domains) - set(BACKEND_DOMAINS))
    if invalid:
        raise TopologyError(f"unknown backend domains: {invalid}")
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = [entry["id"] for entry in manifest["backend"]["tests"] if entry["domain"] in domains]
    selection_args: list[str] = []
    if set(domains) != set(BACKEND_DOMAINS):
        selection_path = output_dir / "selection.json"
        write_json(selection_path, selected)
        selection_args = ["--domain-topology-select-file", str(selection_path)]

    started = time.perf_counter()
    first_rc, first, attempt_path = _run_backend_attempt(
        manifest,
        output_dir=output_dir,
        selected_ids=selected,
        attempt_index=0,
        selection_args=selection_args,
    )
    retry_summaries: list[dict[str, Any]] = []
    remaining = _failed_parent_ids(first)
    for attempt_index in range(1, retry_failures + 1):
        if not remaining:
            break
        retry_selection = output_dir / f"retry-{attempt_index}-selection.json"
        write_json(retry_selection, remaining)
        _, retry, retry_path = _run_backend_attempt(
            manifest,
            output_dir=output_dir,
            selected_ids=remaining,
            attempt_index=attempt_index,
            selection_args=("--domain-topology-select-file", str(retry_selection)),
        )
        retry_summaries.append(_attempt_summary(retry, retry_path))
        remaining = _failed_parent_ids(retry)

    first_failures = _failed_parent_ids(first)
    classification = classify_failures(first_failures, manifest["backend"].get("knownBaselineFailures", []))
    ended_at = _utc_now()
    result = {
        "schemaVersion": TEST_RESULT_SCHEMA_VERSION,
        "kind": "aggregate",
        "state": "completed",
        "surface": "backend-domain-aggregate",
        "authority": "structured-test-result",
        "createdAt": ended_at,
        "identity": first["identity"],
        "domains": list(domains),
        "selectedCount": len(selected),
        "durationSeconds": round(time.perf_counter() - started, 6),
        "firstAttempt": _attempt_summary(first, attempt_path),
        "retries": retry_summaries,
        **classification,
        "remainingFailuresAfterRetries": remaining,
        "status": (
            first["status"]
            if first["status"] in {"passed", "skipped"}
            else f"{first['status']}_first_attempt"
        ),
    }
    write_json(output_dir / "result.json", result)
    decision_rc = _test_result_exit_code(process_exit_code=first_rc, status=first["status"])
    return decision_rc, result


def _load_summarized_attempt(
    result_path: Path,
    summary_value: object,
    *,
    expected_index: int,
) -> dict[str, Any]:
    summary = _require_object(summary_value, f"attempt-{expected_index} summary")
    relative_path = _require_string(summary.get("path"), f"attempt-{expected_index} summary path")
    if Path(relative_path).name != relative_path:
        raise TopologyError("structured attempt summary path must be a contained filename")
    expected_hash = _require_digest(summary.get("sha256"), f"attempt-{expected_index} summary sha256")
    attempt_path = result_path.parent / relative_path
    if not attempt_path.is_file() or file_hash(attempt_path) != expected_hash:
        raise TopologyError(f"structured attempt-{expected_index} evidence is missing or mismatched")
    identity = _validate_test_result_identity(summary.get("identity"))
    attempt = load_test_result_evidence(attempt_path, expected_identity=identity)
    if attempt["attempt"]["index"] != expected_index or summary != _attempt_summary(attempt, attempt_path):
        raise TopologyError(f"structured attempt-{expected_index} summary does not match attempt evidence")
    return attempt


def reclassify_backend_result(manifest: dict[str, Any], result_path: Path) -> dict[str, Any]:
    result = _require_object(json.loads(result_path.read_text(encoding="utf-8")), "aggregate")
    if (
        result.get("schemaVersion") != TEST_RESULT_SCHEMA_VERSION
        or result.get("kind") != "aggregate"
        or result.get("state") != "completed"
        or result.get("surface") != "backend-domain-aggregate"
        or result.get("authority") != "structured-test-result"
    ):
        raise TopologyError(f"not a backend aggregate result: {result_path}")
    identity = _validate_test_result_identity(result.get("identity"))
    _require_utc_timestamp(result.get("createdAt"), "aggregate.createdAt")
    _require_non_negative_number(result.get("durationSeconds"), "aggregate.durationSeconds")
    selected_count = result.get("selectedCount")
    if isinstance(selected_count, bool) or not isinstance(selected_count, int) or selected_count != identity["selection"]["count"]:
        raise TopologyError("structured aggregate selectedCount does not match selection identity")
    first = _load_summarized_attempt(result_path, result.get("firstAttempt"), expected_index=0)
    if first["identity"] != identity:
        raise TopologyError("structured aggregate identity does not match first attempt")
    retries = _require_list(result.get("retries"), "aggregate.retries")
    attempts = [first]
    for expected_index, summary in enumerate(retries, start=1):
        attempts.append(_load_summarized_attempt(result_path, summary, expected_index=expected_index))
    expected_remaining = _failed_parent_ids(attempts[-1])
    if result.get("remainingFailuresAfterRetries") != expected_remaining:
        raise TopologyError("structured aggregate retry result does not match attempt evidence")
    expected_status = (
        first["status"]
        if first["status"] in {"passed", "skipped"}
        else f"{first['status']}_first_attempt"
    )
    if result.get("status") != expected_status:
        raise TopologyError("structured aggregate status does not match first attempt")
    classification = classify_failures(_failed_parent_ids(first), manifest["backend"]["knownBaselineFailures"])
    result.update(classification)
    write_json(result_path, result)
    return {"path": str(result_path), **classification}


def split_attempt_records(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    first = sorted((record for record in records if int(record.get("retry", 0)) == 0), key=lambda item: item["id"])
    retries = sorted(
        (record for record in records if int(record.get("retry", 0)) > 0),
        key=lambda item: (int(item["retry"]), item["id"]),
    )
    return {"firstAttempts": first, "retries": retries}


def _playwright_report_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def walk(suite: dict[str, Any], parents: tuple[str, ...] = ()) -> None:
        title = suite.get("title") or ""
        next_parents = parents + ((title,) if title else ())
        suite_file = suite.get("file") or ""
        for spec in suite.get("specs", []):
            path = _playwright_spec_path(spec.get("file") or suite_file)
            titles = next_parents + ((spec.get("title") or "<untitled>"),)
            for test in spec.get("tests", []):
                project = test.get("projectName") or test.get("projectId") or ""
                case_id = f"{project}::{path}::{' › '.join(titles)}"
                for result in test.get("results", []):
                    records.append(
                        {
                            "id": case_id,
                            "retry": int(result.get("retry", 0)),
                            "status": result.get("status", "unknown"),
                            "durationMs": result.get("duration", 0),
                        }
                    )
        for child in suite.get("suites", []):
            walk(child, next_parents)

    for suite in payload.get("suites", []):
        walk(suite)
    return records


def record_playwright(report_path: Path, output_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    records = _playwright_report_records(payload)
    expected = {entry["id"] for entry in manifest["playwright"]["projectCases"]}
    unknown = sorted({record["id"] for record in records} - expected)
    if unknown:
        raise TopologyError(f"Playwright report contains unowned cases: {unknown[:10]}")
    split = split_attempt_records(records)
    result = {"schemaVersion": 1, "surface": "playwright", **split}
    write_json(output_path, result)
    return result


def _manifest_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST.relative_to(ROOT)))
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate-manifest")
    subparsers.add_parser("verify-backend")
    subparsers.add_parser("verify-vitest")
    subparsers.add_parser("verify-playwright")
    subparsers.add_parser("verify-all")
    list_backend = subparsers.add_parser("list-backend")
    list_backend.add_argument("--domain", choices=BACKEND_DOMAINS)
    subparsers.add_parser("list-network")
    run = subparsers.add_parser("run-backend")
    run.add_argument("--domains", default=",".join(BACKEND_DOMAINS))
    run.add_argument("--output-dir", required=True)
    run.add_argument("--retry-failures", type=int, default=0)
    capture = subparsers.add_parser("capture-manifest")
    capture.add_argument("--baseline-backend-json", required=True)
    capture.add_argument("--known-baseline-failures-json")
    capture.add_argument("--base-sha", required=True)
    capture.add_argument("--capture-date", default=date.today().isoformat())
    classify = subparsers.add_parser("classify-backend-result")
    classify.add_argument("--result", required=True)
    record = subparsers.add_parser("record-playwright")
    record.add_argument("--report", required=True)
    record.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest_path = _manifest_path(args.manifest)
    try:
        if args.command == "capture-manifest":
            baseline_payload = json.loads(Path(args.baseline_backend_json).read_text(encoding="utf-8"))
            if baseline_payload.get("baseSha") != args.base_sha:
                raise TopologyError("baseline capture SHA does not match --base-sha")
            known_baseline_failures: set[str] = set()
            if args.known_baseline_failures_json:
                known_payload = json.loads(Path(args.known_baseline_failures_json).read_text(encoding="utf-8"))
                known_values = known_payload.get("failures") if isinstance(known_payload, dict) else known_payload
                if not isinstance(known_values, list) or not all(isinstance(value, str) for value in known_values):
                    raise TopologyError("known baseline failure evidence must be a list or an object with failures")
                known_baseline_failures = set(known_values)
            manifest = build_manifest(
                baseline_backend_ids=set(baseline_payload["ids"]),
                known_baseline_failures=known_baseline_failures,
                base_sha=args.base_sha,
                capture_date=args.capture_date,
            )
            validate_manifest(manifest)
            write_json(manifest_path, manifest)
            print(json.dumps({"status": "captured", "path": str(manifest_path), **validate_manifest(manifest)}, indent=2))
            return 0

        manifest = load_manifest(manifest_path)
        validation = validate_manifest(manifest)
        if args.command == "validate-manifest":
            payload = validation
        elif args.command == "verify-backend":
            payload = verify_backend(manifest)
        elif args.command == "verify-vitest":
            payload = verify_vitest(manifest)
        elif args.command == "verify-playwright":
            payload = verify_playwright(manifest)
        elif args.command == "verify-all":
            payload = {
                "manifest": validation,
                "backend": verify_backend(manifest),
                "vitest": verify_vitest(manifest),
                "playwright": verify_playwright(manifest),
            }
        elif args.command == "list-backend":
            entries = manifest["backend"]["tests"]
            payload = [entry for entry in entries if args.domain is None or entry["domain"] == args.domain]
        elif args.command == "list-network":
            payload = manifest["backend"]["networkTests"]
        elif args.command == "run-backend":
            domains = tuple(part.strip() for part in args.domains.split(",") if part.strip())
            rc, payload = run_backend(
                manifest,
                output_dir=_manifest_path(args.output_dir),
                domains=domains,
                retry_failures=args.retry_failures,
            )
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return rc
        elif args.command == "classify-backend-result":
            payload = reclassify_backend_result(manifest, _manifest_path(args.result))
        elif args.command == "record-playwright":
            payload = record_playwright(Path(args.report), Path(args.output), manifest)
        else:  # pragma: no cover - argparse enforces commands
            raise TopologyError(f"unsupported command: {args.command}")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
