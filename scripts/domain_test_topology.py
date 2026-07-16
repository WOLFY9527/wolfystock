#!/usr/bin/env python3
"""Build, verify, list, and run the shadow domain-owned test topology."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "apps" / "dsa-web"
DEFAULT_MANIFEST = ROOT / "validation" / "domain_test_topology.json"
BASE_SHA = "1f554d42ca7fee0e4c71f80f0b1c15680526032a"

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
    baseline = backend.get("baselineCapture", {})
    if baseline.get("baseSha") != BASE_SHA:
        raise TopologyError(f"backend baseline baseSha must be {BASE_SHA}")
    if baseline.get("count") != len(baseline_ids) or baseline.get("sha256") != inventory_hash(baseline_ids):
        raise TopologyError("backend baseline capture count/hash does not match baseline=true entries")
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
    if not set(known).issubset(baseline_ids):
        raise TopologyError("backend.knownBaselineFailures must reference baseline-owned test IDs")
    return {"backendTests": len(ids), "baselineBackendTests": len(baseline_ids), "networkTests": len(network_ids)}


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
    if missing_baseline:
        raise TopologyError(f"T446 removed or renamed baseline backend tests: {missing_baseline[:10]}")
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


def _backend_command(*extra: str) -> list[str]:
    return [sys.executable, "-m", "pytest", "-q", "--tb=short", *extra]


def _attempt_summary(attempt: dict[str, Any], relative_path: str) -> dict[str, Any]:
    return {
        "path": relative_path,
        "attemptIndex": attempt["attemptIndex"],
        "durationSeconds": attempt["durationSeconds"],
        "exitCode": attempt["exitCode"],
        "counts": attempt["counts"],
        "domains": attempt["domains"],
        "failures": attempt["failures"],
    }


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
    attempt_path = output_dir / "attempt-0.json"
    command = _backend_command(
        "--domain-topology-verify-full",
        "--domain-topology-attempt-output",
        str(attempt_path),
        "--domain-topology-attempt-index",
        "0",
        *selection_args,
    )
    first_rc = subprocess.run(command, cwd=ROOT).returncode
    if not attempt_path.exists():
        raise TopologyError(f"backend attempt did not write evidence: {attempt_path}")
    first = json.loads(attempt_path.read_text(encoding="utf-8"))
    retry_summaries: list[dict[str, Any]] = []
    remaining = list(first["failures"])
    for attempt_index in range(1, retry_failures + 1):
        if not remaining:
            break
        retry_selection = output_dir / f"retry-{attempt_index}-selection.json"
        write_json(retry_selection, remaining)
        retry_path = output_dir / f"attempt-{attempt_index}.json"
        retry_command = _backend_command(
            "--domain-topology-attempt-output",
            str(retry_path),
            "--domain-topology-attempt-index",
            str(attempt_index),
            "--domain-topology-select-file",
            str(retry_selection),
        )
        subprocess.run(retry_command, cwd=ROOT)
        retry = json.loads(retry_path.read_text(encoding="utf-8"))
        retry_summaries.append(_attempt_summary(retry, retry_path.name))
        remaining = list(retry["failures"])

    first_failures = set(first["failures"])
    classification = classify_failures(first_failures, manifest["backend"].get("knownBaselineFailures", []))
    result = {
        "schemaVersion": 1,
        "surface": "backend-domain-aggregate",
        "shadowOnly": True,
        "createdAt": datetime.now(UTC).isoformat(),
        "domains": list(domains),
        "selectedCount": len(selected),
        "durationSeconds": round(time.perf_counter() - started, 6),
        "firstAttempt": _attempt_summary(first, attempt_path.name),
        "retries": retry_summaries,
        **classification,
        "remainingFailuresAfterRetries": remaining,
        "status": "passed" if first_rc == 0 else "failed_first_attempt",
    }
    write_json(output_dir / "result.json", result)
    return first_rc, result


def reclassify_backend_result(manifest: dict[str, Any], result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("surface") != "backend-domain-aggregate" or not isinstance(result.get("firstAttempt"), dict):
        raise TopologyError(f"not a backend aggregate result: {result_path}")
    classification = classify_failures(
        result["firstAttempt"].get("failures", []), manifest["backend"].get("knownBaselineFailures", [])
    )
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
