# -*- coding: utf-8 -*-
"""Shared pytest setup and process-state isolation."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from tests.litellm_stub import ensure_litellm_stub


ensure_litellm_stub()


_BACKEND_SHARD_PLAN_SCHEMA = "wolfystock.backend-shard-plan.v1"
_BACKEND_SHARD_METADATA_SCHEMA = "wolfystock.backend-shard-metadata.v1"
_BACKEND_SHARD_SUITE_SCHEMA = "wolfystock.backend-shard-suite.v1"
_BACKEND_SHARD_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_SHARD_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_BACKEND_SHARD_EXPECTED_FILES = (
    "requirements-dev.txt",
    "requirements-lock.json",
    "scripts/ci_gate.sh",
    "tests/conftest.py",
)
_BACKEND_SHARD_RESOURCE_ENV = {
    "cacheRoot": "XDG_CACHE_HOME",
    "coverage": "COVERAGE_FILE",
    "database": "DATABASE_PATH",
    "duckdb": "DUCKDB_DATABASE_PATH",
    "environment": "ENV_FILE",
    "frontendOutput": "WOLFYSTOCK_FRONTEND_OUTPUT_DIR",
    "home": "HOME",
    "logs": "LOG_DIR",
    "serviceState": "WOLFYSTOCK_SERVICE_STATE_DIR",
    "temporary": "TMPDIR",
    "temporaryCompat": "TMP",
    "temporaryWindows": "TEMP",
    "uploads": "WOLFYSTOCK_TEST_UPLOAD_DIR",
}
_PYTEST_SESSION_CONFIG: pytest.Config | None = None


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is missing or malformed: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _task_record(audit: Mapping[str, Any], task_id: str) -> dict[str, Any]:
    records = [
        item
        for item in audit.get("roadmap", [])
        if isinstance(item, dict) and item.get("taskId") == task_id
    ]
    if len(records) != 1:
        raise ValueError(f"audit must contain exactly one {task_id} task record")
    return records[0]


def _validate_backend_shard_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    from scripts import domain_test_topology as topology

    value = dict(plan)
    if value.get("schemaVersion") != _BACKEND_SHARD_PLAN_SCHEMA:
        raise ValueError("backend shard plan schema is invalid")
    expected_hash = topology.canonical_json_hash(
        {key: item for key, item in value.items() if key != "planHash"}
    )
    if value.get("planHash") != expected_hash:
        raise ValueError("backend shard plan hash mismatch")
    shards = value.get("shards")
    if not isinstance(shards, list) or len(shards) != 2:
        raise ValueError("backend shard plan must contain exactly two shards")
    shard_ids = [item.get("id") for item in shards if isinstance(item, dict)]
    if len(shard_ids) != 2 or len(set(shard_ids)) != 2:
        raise ValueError("backend shard plan IDs must be unique")
    selected = [node_id for shard in shards for node_id in shard.get("nodeIds", [])]
    expected = value.get("selection", {})
    if (
        len(selected) != expected.get("count")
        or topology.inventory_hash(selected) != expected.get("sha256")
        or len(selected) != len(set(selected))
    ):
        raise ValueError("backend shard plan selection is incomplete or duplicated")
    return value


def build_backend_shard_plan(
    risk_plan_path: Path,
    *,
    scope: str,
    topology_path: Path = Path("validation/domain_test_topology.json"),
    audit_path: Path = Path("validation/t569_test_redundancy_performance_audit.json"),
) -> dict[str, Any]:
    """Bind deterministic T633 shards to the exact T631 canonical selection."""

    from scripts import domain_test_topology as topology
    from scripts import validation_changed_files as planner

    if scope not in {"proof", "full"}:
        raise ValueError("backend shard scope must be proof or full")
    risk_plan = _load_json_object(risk_plan_path, "T631 risk plan")
    planner._validate_plan(risk_plan)
    manifest = topology.load_manifest(topology_path)
    topology.validate_manifest(manifest)
    audit = _load_json_object(audit_path, "T569 audit")
    t633 = _task_record(audit, "T633")
    t632 = _task_record(audit, "T632")
    if tuple(t633.get("expectedFiles", ())) != _BACKEND_SHARD_EXPECTED_FILES:
        raise ValueError("T633 expected-files authority is inconsistent")
    if (
        t633.get("candidateNodeIds") != []
        or t633.get("dependencies") != ["T631", "T632"]
        or t633.get("expectedNodeChange") != 0
        or t633.get("commitSubject") != "perf(test): shard isolated backend owners"
    ):
        raise ValueError("T633 machine authority is inconsistent")
    isolated_paths = tuple(t632.get("expectedFiles", ()))
    if isolated_paths != (
        "tests/test_portfolio_api.py",
        "tests/test_portfolio_risk_service.py",
        "tests/test_portfolio_service.py",
    ):
        raise ValueError("T632 isolated owner authority is inconsistent")
    isolated_ids = sorted(t632.get("candidateNodeIds", ()))
    if not isolated_ids or t632.get("expectedNodeChange") != 0:
        raise ValueError("T632 isolated node authority is empty or inconsistent")

    canonical = next(
        (gate for gate in risk_plan.get("gates", []) if gate.get("id") == "backend.canonical"),
        None,
    )
    if canonical is None or canonical.get("structuredEvidence") != "T630":
        raise ValueError("T631 plan does not contain canonical T630 backend evidence")
    selected = next(
        (gate for gate in risk_plan.get("gates", []) if gate.get("id") == "owners.affected"),
        None,
    )
    if selected is None or selected.get("structuredEvidence") != "T630":
        raise ValueError("T631 plan does not contain selected T630 backend evidence")
    canonical_command = canonical.get("structuredCommand")
    selected_command = selected.get("structuredCommand")
    if not isinstance(canonical_command, list) or not isinstance(selected_command, list):
        raise ValueError("T631 structured backend commands are missing")
    domains = tuple(canonical.get("domains", ()))
    if domains != topology.BACKEND_DOMAINS:
        raise ValueError("T631 canonical backend domains are incomplete or reordered")
    entries = [entry for entry in manifest["backend"]["tests"] if entry["domain"] in domains]
    entry_by_id = {entry["id"]: entry for entry in entries}
    canonical_ids = sorted(entry_by_id)
    if canonical.get("expectedSelection") != {
        "count": len(canonical_ids),
        "sha256": topology.inventory_hash(canonical_ids),
    }:
        raise ValueError("T631 canonical selection differs from topology authority")
    missing_isolated = sorted(set(isolated_ids) - set(entry_by_id))
    if missing_isolated:
        raise ValueError(f"T632 isolated nodes are absent from topology: {missing_isolated}")
    if any(
        entry_by_id[node_id]["domain"] != "portfolio_broker"
        or node_id.split("::", 1)[0] not in isolated_paths
        for node_id in isolated_ids
    ):
        raise ValueError("T632 isolated nodes escaped their authorized portfolio owners")

    def shard(shard_id: str, role: str, node_ids: Sequence[str]) -> dict[str, Any]:
        ordered = sorted(node_ids)
        return {
            "id": shard_id,
            "role": role,
            "nodeIds": ordered,
            "owners": sorted({entry_by_id[node_id]["domain"] for node_id in ordered}),
            "selection": {
                "count": len(ordered),
                "sha256": topology.inventory_hash(ordered),
            },
        }

    if scope == "proof":
        api_ids = [node_id for node_id in isolated_ids if node_id.startswith(f"{isolated_paths[0]}::")]
        service_ids = sorted(set(isolated_ids) - set(api_ids))
        shards = [
            shard("isolated-api", "T632-isolated-portfolio-owner", api_ids),
            shard("isolated-service", "T632-isolated-portfolio-owners", service_ids),
        ]
        selected_ids = isolated_ids
    else:
        serial_ids = sorted(set(canonical_ids) - set(isolated_ids))
        shards = [
            shard("serialized-backend", "explicitly-serialized-unsafe-owners", serial_ids),
            shard("isolated-portfolio", "T632-isolated-portfolio-owners", isolated_ids),
        ]
        selected_ids = canonical_ids
    if any(not item["nodeIds"] for item in shards):
        raise ValueError("backend shard plan contains an empty shard")
    plan: dict[str, Any] = {
        "schemaVersion": _BACKEND_SHARD_PLAN_SCHEMA,
        "authority": "T631-risk-selection+T632-isolation+T633",
        "scope": scope,
        "riskPlanHash": risk_plan["planHash"],
        "candidate": risk_plan["identity"]["candidate"],
        "topology": manifest["backend"]["currentInventory"],
        "canonicalSelection": canonical["expectedSelection"],
        "commandIdentity": {
            "canonical": {
                "argv": canonical_command,
                "sha256": topology.canonical_json_hash(canonical_command),
            },
            "selected": {
                "argv": selected_command,
                "sha256": topology.canonical_json_hash(selected_command),
            },
        },
        "selection": {
            "count": len(selected_ids),
            "sha256": topology.inventory_hash(selected_ids),
        },
        "shards": shards,
        "serializedOwners": shards[0]["owners"] if scope == "full" else [],
        "isolatedOwners": list(isolated_paths),
    }
    plan["planHash"] = topology.canonical_json_hash(plan)
    return _validate_backend_shard_plan(plan)


def _pytest_cache_path() -> Path:
    arguments = shlex.split(os.environ.get("PYTEST_ADDOPTS", ""))
    for index, argument in enumerate(arguments):
        if argument == "-o" and index + 1 < len(arguments):
            key, separator, value = arguments[index + 1].partition("=")
            if separator and key == "cache_dir":
                return Path(value)
        key, separator, value = argument.partition("=")
        if separator and key == "cache_dir":
            return Path(value)
    raise pytest.UsageError("backend shard requires an explicit pytest cache directory")


def _backend_shard_resources() -> tuple[Path, dict[str, dict[str, str]]]:
    home = os.environ.get("HOME")
    if not home:
        raise pytest.UsageError("backend shard requires a managed HOME")
    run_root = Path(home).resolve().parent
    raw_paths: dict[str, Path] = {}
    for label, environment_name in _BACKEND_SHARD_RESOURCE_ENV.items():
        value = os.environ.get(environment_name)
        if not value:
            raise pytest.UsageError(f"backend shard resource is missing: {environment_name}")
        raw_paths[label] = Path(value)
    raw_paths["pytestCache"] = _pytest_cache_path()
    resources: dict[str, dict[str, str]] = {}
    for label, path in sorted(raw_paths.items()):
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(run_root)
        except ValueError as exc:
            raise pytest.UsageError(f"backend shard resource escaped its run root: {label}") from exc
        resources[label] = {
            "relative": relative.as_posix(),
            "sha256": hashlib.sha256(str(resolved).encode("utf-8")).hexdigest(),
        }
    return run_root, resources


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, allow_nan=False, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


@pytest.hookimpl(tryfirst=True, specname="pytest_configure")
def pytest_configure_t633(config: pytest.Config) -> None:
    global _PYTEST_SESSION_CONFIG
    _PYTEST_SESSION_CONFIG = config


@pytest.hookimpl(tryfirst=True, specname="pytest_runtest_logreport")
def pytest_runtest_logreport_t633(report: pytest.TestReport) -> None:
    config = _PYTEST_SESSION_CONFIG
    if config is None or getattr(config, "_test_result_evidence", None) is None:
        return
    from scripts import domain_test_topology as topology

    topology._ACTIVE_TEST_RESULT_CONFIG = config


def pytest_collection_finish(session: pytest.Session) -> None:
    output = os.environ.get("WOLFYSTOCK_BACKEND_SHARD_METADATA_OUTPUT")
    if not output:
        return
    shard_id = os.environ.get("WOLFYSTOCK_BACKEND_SHARD_ID", "")
    plan_hash = os.environ.get("WOLFYSTOCK_BACKEND_SHARD_PLAN_HASH", "")
    run_id = os.environ.get("WOLFYSTOCK_TEST_RUN_ID", "")
    if _BACKEND_SHARD_ID.fullmatch(shard_id) is None:
        raise pytest.UsageError("backend shard ID is missing or invalid")
    if re.fullmatch(r"[0-9a-f]{64}", plan_hash) is None:
        raise pytest.UsageError("backend shard plan hash is missing or invalid")
    if re.fullmatch(r"run-[0-9a-f]+", run_id) is None:
        raise pytest.UsageError("backend shard run namespace is missing or invalid")
    run_root, resources = _backend_shard_resources()
    nodes = [
        {
            "id": item.nodeid,
            "markers": sorted({marker.name for marker in item.iter_markers()}),
        }
        for item in sorted(session.items, key=lambda item: item.nodeid)
    ]
    from scripts import domain_test_topology as topology

    payload = {
        "schemaVersion": _BACKEND_SHARD_METADATA_SCHEMA,
        "shardId": shard_id,
        "planHash": plan_hash,
        "runNamespace": run_id,
        "runRootSha256": hashlib.sha256(str(run_root).encode("utf-8")).hexdigest(),
        "resources": resources,
        "nodeIdentity": {
            "count": len(nodes),
            "sha256": topology.inventory_hash(item["id"] for item in nodes),
        },
        "markerIdentity": {
            "count": len(nodes),
            "sha256": topology.canonical_json_hash(nodes),
        },
        "nodes": nodes,
    }
    _write_json_atomic(Path(output), payload)


_AUTH_STATE_ATTRIBUTES = (
    "_auth_enabled",
    "_session_secret",
    "_password_hash_salt",
    "_password_hash_stored",
    "_password_hash_value",
    "_rate_limit",
    "_admin_reauth_markers",
    "_rate_limit_lock",
)


def _snapshot_attributes(module: Any, names: Iterable[str]) -> dict[str, tuple[Any, Any]] | None:
    if module is None:
        return None
    snapshot: dict[str, tuple[Any, Any]] = {}
    for name in names:
        value = getattr(module, name)
        snapshot[name] = (value, copy.deepcopy(value) if isinstance(value, dict) else value)
    return snapshot


def _restore_attributes(module: Any, snapshot: Mapping[str, tuple[Any, Any]]) -> None:
    for name, (original, saved_value) in snapshot.items():
        if isinstance(original, dict):
            original.clear()
            original.update(saved_value)
        setattr(module, name, original)


def _loaded_apps(extra_apps: Iterable[Any]) -> list[Any]:
    apps = list(extra_apps)
    app_module = sys.modules.get("api.app")
    canonical_app = getattr(app_module, "app", None) if app_module is not None else None
    if canonical_app is not None:
        apps.append(canonical_app)

    unique_apps: list[Any] = []
    seen: set[int] = set()
    for app in apps:
        if id(app) not in seen:
            seen.add(id(app))
            unique_apps.append(app)
    return unique_apps


def _snapshot_app_state(app: Any) -> tuple[dict[Any, Any], dict[str, Any]]:
    return dict(app.dependency_overrides), dict(app.state._state)


def _restore_app_state(app: Any, snapshot: tuple[dict[Any, Any], dict[str, Any]]) -> None:
    dependency_overrides, state = snapshot
    app.dependency_overrides.clear()
    app.dependency_overrides.update(dependency_overrides)
    app.state._state.clear()
    app.state._state.update(state)


@contextmanager
def preserve_runtime_test_state(*, apps: Iterable[Any] = ()) -> Iterator[None]:
    """Restore only the process-scoped owners exercised by canonical runtime tests."""

    environment = dict(os.environ)
    auth_module = sys.modules.get("src.auth")
    auth_state = _snapshot_attributes(auth_module, _AUTH_STATE_ATTRIBUTES)
    provider_module = sys.modules.get("src.services.rotation_radar_quote_provider")
    provider_state = _snapshot_attributes(provider_module, ("_UNAVAILABLE_SYMBOL_STATE",))
    config_module = sys.modules.get("src.config")
    config_class = getattr(config_module, "Config", None) if config_module is not None else None
    config_instance = getattr(config_class, "_instance", None) if config_class is not None else None
    app_states = [(app, _snapshot_app_state(app)) for app in _loaded_apps(apps)]

    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(environment)

        loaded_auth = sys.modules.get("src.auth")
        if auth_state is not None and loaded_auth is not None:
            _restore_attributes(loaded_auth, auth_state)
        elif loaded_auth is not None:
            for name in _AUTH_STATE_ATTRIBUTES:
                setattr(loaded_auth, name, {} if name in {"_rate_limit", "_admin_reauth_markers"} else None)

        loaded_provider = sys.modules.get("src.services.rotation_radar_quote_provider")
        if provider_state is not None and loaded_provider is not None:
            _restore_attributes(loaded_provider, provider_state)
        elif loaded_provider is not None:
            loaded_provider._UNAVAILABLE_SYMBOL_STATE.clear()

        loaded_config = sys.modules.get("src.config")
        loaded_config_class = getattr(loaded_config, "Config", None) if loaded_config is not None else None
        if loaded_config_class is not None:
            loaded_config_class._instance = config_instance

        for app, app_state in app_states:
            _restore_app_state(app, app_state)


def _t633_injection_mode() -> str:
    return os.environ.get("WOLFYSTOCK_BACKEND_SHARD_INJECTION", "none")


def pytest_sessionstart(session: pytest.Session) -> None:
    mode = _t633_injection_mode()
    if mode == "crash":
        os._exit(86)
    if mode == "timeout":
        delay = float(os.environ.get("WOLFYSTOCK_BACKEND_SHARD_TIMEOUT_DELAY", "3600"))
        time.sleep(max(delay, 0.0))


def pytest_runtest_call(item: pytest.Item) -> None:
    if _t633_injection_mode() != "failure":
        return
    target = os.environ.get("WOLFYSTOCK_BACKEND_SHARD_FAILURE_NODE", "")
    if target and item.nodeid == target:
        raise AssertionError("T633 controlled shard failure injection")


def _backend_shard_semantics(attempt: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    from scripts import domain_test_topology as topology

    parents = [
        {
            key: value
            for key, value in record.items()
            if key not in {"durationSeconds"}
        }
        for record in attempt["parents"]
    ]
    children = [
        {
            key: value
            for key, value in record.items()
            if key not in {"durationSeconds", "id", "contextSha256", "presentation"}
        }
        for record in attempt["children"]
    ]
    return {
        "parents": sorted(parents, key=lambda item: item["id"]),
        "children": sorted(
            children,
            key=lambda item: (
                item["parentId"],
                item["outcome"],
                item.get("failureFamily") or "",
                topology.canonical_json_hash(item),
            ),
        ),
    }


def _backend_shard_semantics_hash(attempts: Sequence[Mapping[str, Any]]) -> str:
    from scripts import domain_test_topology as topology

    semantics = [_backend_shard_semantics(attempt) for attempt in attempts]
    combined = {
        "parents": sorted(
            (record for value in semantics for record in value["parents"]),
            key=lambda item: item["id"],
        ),
        "children": sorted(
            (record for value in semantics for record in value["children"]),
            key=lambda item: (
                item["parentId"],
                item["outcome"],
                item.get("failureFamily") or "",
                topology.canonical_json_hash(item),
            ),
        ),
    }
    return topology.canonical_json_hash(combined)


def _backend_shard_outcome_counts(
    attempts: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, int]]:
    from scripts import domain_test_topology as topology

    return {
        group: {
            outcome: sum(attempt["counts"][group][outcome] for attempt in attempts)
            for outcome in topology.TEST_OUTCOMES
        }
        for group in ("parents", "children")
    }


def _load_backend_shard_plan(path: Path) -> dict[str, Any]:
    return _validate_backend_shard_plan(_load_json_object(path, "backend shard plan"))


def _backend_shard_by_id(plan: Mapping[str, Any], shard_id: str) -> dict[str, Any]:
    matches = [item for item in plan["shards"] if item.get("id") == shard_id]
    if len(matches) != 1:
        raise ValueError(f"backend shard is not present exactly once: {shard_id}")
    return matches[0]


def _validate_backend_shard_metadata(
    metadata_path: Path,
    *,
    plan: Mapping[str, Any],
    shard: Mapping[str, Any],
    expected_ids: Sequence[str],
) -> dict[str, Any]:
    from scripts import domain_test_topology as topology

    metadata = _load_json_object(metadata_path, "backend shard metadata")
    if metadata.get("schemaVersion") != _BACKEND_SHARD_METADATA_SCHEMA:
        raise ValueError("backend shard metadata schema is invalid")
    if metadata.get("shardId") != shard["id"] or metadata.get("planHash") != plan["planHash"]:
        raise ValueError("backend shard metadata plan or shard identity mismatches")
    run_namespace = metadata.get("runNamespace", "")
    if re.fullmatch(r"run-[0-9a-f]+", run_namespace) is None:
        raise ValueError("backend shard metadata run namespace is invalid")
    nodes = metadata.get("nodes")
    expected_nodes = sorted(expected_ids)
    if not isinstance(nodes, list) or [item.get("id") for item in nodes] != expected_nodes:
        raise ValueError("backend shard metadata node inventory differs from plan")
    if metadata.get("nodeIdentity") != {
        "count": len(expected_nodes),
        "sha256": topology.inventory_hash(expected_nodes),
    }:
        raise ValueError("backend shard metadata node identity mismatch")
    if metadata.get("markerIdentity", {}).get("count") != len(expected_nodes):
        raise ValueError("backend shard metadata marker count mismatch")
    if metadata["markerIdentity"].get("sha256") != topology.canonical_json_hash(nodes):
        raise ValueError("backend shard metadata marker identity mismatch")
    resources = metadata.get("resources")
    if not isinstance(resources, dict) or set(resources) != set(_BACKEND_SHARD_RESOURCE_ENV) | {"pytestCache"}:
        raise ValueError("backend shard metadata resource inventory is incomplete")
    for label, resource in resources.items():
        if (
            not isinstance(resource, dict)
            or not resource.get("relative")
            or Path(resource["relative"]).is_absolute()
            or ".." in Path(resource["relative"]).parts
        ):
            raise ValueError(f"backend shard resource is malformed: {label}")
        if re.fullmatch(r"[0-9a-f]{64}", resource.get("sha256", "")) is None:
            raise ValueError(f"backend shard resource identity is malformed: {label}")
    return metadata


def _load_backend_shard_attempt(
    shard_dir: Path,
    *,
    plan: Mapping[str, Any],
    shard: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    from scripts import domain_test_topology as topology

    envelope_path = shard_dir / "shard-result.json"
    envelope = _load_json_object(envelope_path, "backend shard result")
    if envelope.get("schemaVersion") != _BACKEND_SHARD_METADATA_SCHEMA:
        raise ValueError("backend shard result schema is invalid")
    if envelope.get("shardId") != shard["id"] or envelope.get("planHash") != plan["planHash"]:
        raise ValueError("backend shard result plan or shard identity mismatches")
    attempt_path = shard_dir / "attempt-0.json"
    metadata_path = shard_dir / "metadata.json"
    if envelope.get("attemptPath") != attempt_path.name or envelope.get("metadataPath") != metadata_path.name:
        raise ValueError("backend shard result artifact paths are invalid")
    attempt = topology.load_test_result_evidence(attempt_path)
    if attempt["attempt"] != {"index": 0, "kind": "first"}:
        raise ValueError("backend shard must contain exactly one first attempt")
    expected_ids = shard["nodeIds"]
    identity = attempt["identity"]
    if identity["candidate"] != plan["candidate"] or identity["topology"] != plan["topology"]:
        raise ValueError("backend shard candidate or topology identity mismatch")
    if identity["selection"] != shard["selection"]:
        raise ValueError("backend shard selection identity mismatch")
    if identity["command"] != plan["commandIdentity"]["selected"]:
        raise ValueError("backend shard command identity mismatch")
    parent_ids = [record["id"] for record in attempt["parents"]]
    if parent_ids != sorted(expected_ids):
        raise ValueError("backend shard parent inventory differs from deterministic selection")
    owner_by_id = {entry["id"]: entry["domain"] for entry in manifest["backend"]["tests"]}
    if any(record["owner"] != owner_by_id.get(record["id"]) for record in attempt["parents"]):
        raise ValueError("backend shard parent owner differs from topology authority")
    metadata = _validate_backend_shard_metadata(
        metadata_path,
        plan=plan,
        shard=shard,
        expected_ids=expected_ids,
    )
    if envelope.get("attemptSha256") != hashlib.sha256(attempt_path.read_bytes()).hexdigest():
        raise ValueError("backend shard attempt hash mismatch")
    if envelope.get("metadataSha256") != hashlib.sha256(metadata_path.read_bytes()).hexdigest():
        raise ValueError("backend shard metadata hash mismatch")
    if envelope.get("exitCode") != attempt["exitCode"] or envelope.get("status") != attempt["status"]:
        raise ValueError("backend shard result outcome differs from structured attempt")
    return attempt, metadata


def validate_backend_shard_suite(
    plan_path: Path,
    suite_dir: Path,
    *,
    serial_attempt_path: Path | None = None,
) -> dict[str, Any]:
    from scripts import domain_test_topology as topology

    plan = _load_backend_shard_plan(plan_path)
    manifest = topology.load_manifest()
    topology.validate_manifest(manifest)
    workers = _load_json_object(suite_dir / "workers.json", "backend shard worker manifest")
    if workers.get("schemaVersion") != _BACKEND_SHARD_SUITE_SCHEMA:
        raise ValueError("backend shard worker manifest schema is invalid")
    if workers.get("planHash") != plan["planHash"]:
        raise ValueError("backend shard worker manifest plan hash mismatch")
    entries = workers.get("workers")
    if (
        not isinstance(entries, list)
        or len(entries) != len(plan["shards"])
        or not all(isinstance(item, dict) for item in entries)
        or {item.get("shardId") for item in entries} != {item["id"] for item in plan["shards"]}
    ):
        raise ValueError("backend shard worker manifest does not cover the plan")
    loaded: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    run_namespaces: set[str] = set()
    run_roots: set[str] = set()
    resource_identities: set[tuple[str, str, str]] = set()
    execution_identity: dict[str, Any] | None = None
    for entry in sorted(entries, key=lambda item: item["shardId"]):
        shard = _backend_shard_by_id(plan, entry["shardId"])
        if entry.get("returnCode") is None or entry.get("timedOut"):
            raise ValueError(f"backend shard did not complete: {entry['shardId']}")
        attempt, shard_metadata = _load_backend_shard_attempt(
            suite_dir / entry["shardId"], plan=plan, shard=shard, manifest=manifest
        )
        if entry["returnCode"] != attempt["exitCode"]:
            raise ValueError("backend shard worker exit differs from structured attempt")
        shard_execution_identity = {
            key: attempt["identity"][key]
            for key in ("environment", "dependencyLock", "command")
        }
        if execution_identity is None:
            execution_identity = shard_execution_identity
        elif execution_identity != shard_execution_identity:
            raise ValueError("backend shard execution identities differ")
        if shard_metadata["runNamespace"] in run_namespaces:
            raise ValueError("backend shards reused a managed run namespace")
        run_namespaces.add(shard_metadata["runNamespace"])
        root_hash = shard_metadata["runRootSha256"]
        if root_hash in run_roots:
            raise ValueError("backend shards reused a managed run root")
        run_roots.add(root_hash)
        for label, resource in shard_metadata["resources"].items():
            identity = (root_hash, label, resource["sha256"])
            if identity in resource_identities:
                raise ValueError("backend shards reused a managed resource identity")
            resource_identities.add(identity)
        loaded.append(attempt)
        metadata.append(shard_metadata)
    all_ids = [record["id"] for attempt in loaded for record in attempt["parents"]]
    expected_ids = sorted(node_id for shard in plan["shards"] for node_id in shard["nodeIds"])
    if sorted(all_ids) != expected_ids or len(all_ids) != len(set(all_ids)):
        raise ValueError("backend shard union is missing, unexpected, or duplicated")
    counts = _backend_shard_outcome_counts(loaded)
    fail_closed_outcomes = {
        outcome: counts["parents"][outcome] + counts["children"][outcome]
        for outcome in ("cancelled", "incomplete", "missing", "unknown")
        if counts["parents"][outcome] + counts["children"][outcome]
    }
    if fail_closed_outcomes:
        raise ValueError(f"backend shard contains fail-closed outcomes: {fail_closed_outcomes}")
    failed_ids = sorted(
        {
            node_id
            for attempt in loaded
            for node_id in topology._failed_parent_ids(attempt)
        }
    )
    classification = topology.classify_failures(
        failed_ids,
        manifest["backend"].get("knownBaselineFailures", []),
    )
    semantic_hash = _backend_shard_semantics_hash(loaded)
    serial_hash = None
    serial_result = None
    if serial_attempt_path is not None:
        serial = topology.load_test_result_evidence(serial_attempt_path)
        if (
            serial["identity"]["candidate"] != plan["candidate"]
            or serial["identity"]["topology"] != plan["topology"]
        ):
            raise ValueError("serial parity candidate or topology identity mismatch")
        if serial["identity"]["command"] != plan["commandIdentity"]["canonical"]:
            raise ValueError("serial parity command identity mismatch")
        if execution_identity is None or any(
            serial["identity"][key] != execution_identity[key]
            for key in ("environment", "dependencyLock")
        ):
            raise ValueError("serial and sharded execution identities differ")
        if serial["identity"]["selection"] != plan["canonicalSelection"]:
            raise ValueError("serial parity attempt is not the T631 canonical selection")
        serial_ids = sorted(record["id"] for record in serial["parents"])
        if (
            plan["scope"] == "full"
            and (
                len(serial_ids) != plan["canonicalSelection"]["count"]
                or topology.inventory_hash(serial_ids) != plan["canonicalSelection"]["sha256"]
            )
        ):
            raise ValueError("serial parity attempt inventory differs from canonical selection")
        serial_hash = _backend_shard_semantics_hash([serial])
        if serial_hash != semantic_hash:
            raise ValueError("serial and sharded semantic outcomes differ")
        serial_result = {
            "counts": serial["counts"],
            "durationSeconds": serial["timing"]["wallSeconds"],
            "semanticHash": serial_hash,
            "status": serial["status"],
        }
    duration_seconds = workers.get("durationSeconds")
    if (
        isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, (int, float))
        or duration_seconds < 0
    ):
        raise ValueError("backend shard worker duration is invalid")
    shard_results = []
    entries_by_id = {entry["shardId"]: entry for entry in entries}
    for shard, attempt, shard_metadata in zip(
        sorted(plan["shards"], key=lambda item: item["id"]),
        loaded,
        metadata,
        strict=True,
    ):
        entry = entries_by_id[shard["id"]]
        attempt_path = suite_dir / shard["id"] / "attempt-0.json"
        shard_results.append(
            {
                "id": shard["id"],
                "selection": shard["selection"],
                "nodeIdentity": shard_metadata["nodeIdentity"],
                "markerIdentity": shard_metadata["markerIdentity"],
                "runNamespace": shard_metadata["runNamespace"],
                "runRootSha256": shard_metadata["runRootSha256"],
                "attemptPath": f"{shard['id']}/attempt-0.json",
                "attemptSha256": hashlib.sha256(attempt_path.read_bytes()).hexdigest(),
                "exitCode": entry["returnCode"],
                "status": attempt["status"],
                "durationSeconds": attempt["timing"]["wallSeconds"],
                "counts": attempt["counts"],
            }
        )
    result = {
        "schemaVersion": _BACKEND_SHARD_SUITE_SCHEMA,
        "authority": "deterministic-backend-shard-orchestration",
        "structuredResultAuthority": topology.TEST_RESULT_SCHEMA_VERSION,
        "scope": plan["scope"],
        "planHash": plan["planHash"],
        "riskPlanHash": plan["riskPlanHash"],
        "selection": plan["selection"],
        "executionIdentity": {
            "candidate": plan["candidate"],
            "topology": plan["topology"],
            "environment": execution_identity["environment"] if execution_identity else None,
            "dependencyLock": execution_identity["dependencyLock"] if execution_identity else None,
            "command": plan["commandIdentity"],
        },
        "durationSeconds": round(float(duration_seconds), 6),
        "counts": counts,
        "shards": shard_results,
        "semanticHash": semantic_hash,
        "serialSemanticHash": serial_hash,
        "serial": serial_result,
        **classification,
        "zeroNewFailures": not classification["unknownFirstAttemptFailures"],
        "status": "passed" if all(entry["returnCode"] == 0 for entry in entries) else "failed_tests",
    }
    return result


def _run_backend_shard(plan_path: Path, shard_id: str, output_dir: Path) -> int:
    from scripts import domain_test_topology as topology

    plan = _load_backend_shard_plan(plan_path)
    shard = _backend_shard_by_id(plan, shard_id)
    manifest = topology.load_manifest()
    topology.validate_manifest(manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    mode = _t633_injection_mode()
    if mode == "crash":
        os._exit(86)
    if mode == "timeout":
        time.sleep(float(os.environ.get("WOLFYSTOCK_BACKEND_SHARD_TIMEOUT_DELAY", "3600")))
    if mode == "missing":
        return 0
    selection_path = output_dir / "selection.json"
    topology.write_json(selection_path, shard["nodeIds"])
    os.environ["WOLFYSTOCK_BACKEND_SHARD_ID"] = shard_id
    os.environ["WOLFYSTOCK_BACKEND_SHARD_PLAN_HASH"] = plan["planHash"]
    os.environ["WOLFYSTOCK_BACKEND_SHARD_METADATA_OUTPUT"] = str(output_dir / "metadata.json")
    if mode == "failure":
        os.environ["WOLFYSTOCK_BACKEND_SHARD_FAILURE_NODE"] = shard["nodeIds"][0]
    rc, attempt, attempt_path = topology._run_backend_attempt(
        manifest,
        output_dir=output_dir,
        selected_ids=shard["nodeIds"],
        attempt_index=0,
        selection_args=("--domain-topology-select-file", str(selection_path)),
    )
    envelope = {
        "schemaVersion": _BACKEND_SHARD_METADATA_SCHEMA,
        "shardId": shard_id,
        "planHash": plan["planHash"],
        "attemptPath": attempt_path.name,
        "metadataPath": "metadata.json",
        "attemptSha256": hashlib.sha256(attempt_path.read_bytes()).hexdigest(),
        "metadataSha256": hashlib.sha256((output_dir / "metadata.json").read_bytes()).hexdigest(),
        "exitCode": rc,
        "status": attempt["status"],
    }
    _write_json_atomic(output_dir / "shard-result.json", envelope)
    return rc


def run_backend_shard_suite(
    plan_path: Path,
    output_dir: Path,
    *,
    launch_order: Sequence[str] | None = None,
    timeout_seconds: float = 900.0,
    injection: str = "none",
    tamper: str = "none",
    serial_attempt_path: Path | None = None,
) -> int:
    plan = _load_backend_shard_plan(plan_path)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"backend shard output directory is not empty: {output_dir}")
    if not timeout_seconds > 0:
        raise ValueError("backend shard timeout must be positive")
    output_dir.mkdir(parents=True, exist_ok=True)
    order = list(launch_order or [item["id"] for item in plan["shards"]])
    if len(order) != len(plan["shards"]) or set(order) != {item["id"] for item in plan["shards"]}:
        raise ValueError("backend shard launch order must cover each shard exactly once")
    if injection not in {"none", "failure", "crash", "timeout", "missing"}:
        raise ValueError(f"unsupported backend shard injection: {injection}")
    workers: list[dict[str, Any]] = []
    processes: list[tuple[dict[str, Any], subprocess.Popen[str], Any]] = []
    started = time.monotonic()
    for shard_id in order:
        worker_dir = output_dir / shard_id
        worker_dir.mkdir(parents=True, exist_ok=True)
        log_handle = (worker_dir / "worker.log").open("w", encoding="utf-8")
        worker_injection = injection if injection != "none" and shard_id == order[0] else "none"
        env_tokens = [
            f"WOLFYSTOCK_BACKEND_SHARD_INJECTION={worker_injection}",
            "WOLFYSTOCK_BACKEND_SHARD_TIMEOUT_DELAY=3600",
        ]
        command = [
            str(_BACKEND_SHARD_ROOT / "wolfy"), "exec", "--profile", "test", "--", "env",
            *env_tokens, "python", "-m", "tests.conftest", "run-backend-shard",
            "--plan", str(plan_path.resolve()), "--shard", shard_id, "--output-dir", str(worker_dir.resolve()),
        ]
        process = subprocess.Popen(
            command,
            cwd=_BACKEND_SHARD_ROOT,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        entry = {
            "shardId": shard_id,
            "pid": process.pid,
            "returnCode": None,
            "timedOut": False,
            "logPath": f"{shard_id}/worker.log",
            "injection": worker_injection,
        }
        workers.append(entry)
        processes.append((entry, process, log_handle))
    pending = list(processes)
    deadline = started + timeout_seconds
    while pending:
        for item in list(pending):
            entry, process, log_handle = item
            return_code = process.poll()
            if return_code is not None:
                entry["returnCode"] = return_code
                log_handle.close()
                pending.remove(item)
        if pending and time.monotonic() >= deadline:
            for entry, process, _ in pending:
                entry["timedOut"] = True
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            grace_deadline = time.monotonic() + 2.0
            while pending and time.monotonic() < grace_deadline:
                for item in list(pending):
                    entry, process, log_handle = item
                    return_code = process.poll()
                    if return_code is not None:
                        entry["returnCode"] = return_code
                        log_handle.close()
                        pending.remove(item)
                time.sleep(0.05)
            for entry, process, log_handle in pending:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                entry["returnCode"] = -signal.SIGKILL
                log_handle.close()
            pending.clear()
        elif pending:
            time.sleep(0.1)
    worker_manifest = {
        "schemaVersion": _BACKEND_SHARD_SUITE_SCHEMA,
        "planHash": plan["planHash"],
        "launchOrder": order,
        "timeoutSeconds": timeout_seconds,
        "durationSeconds": round(time.monotonic() - started, 6),
        "workers": workers,
    }
    _write_json_atomic(output_dir / "workers.json", worker_manifest)
    if tamper == "mismatch":
        metadata_path = output_dir / order[0] / "metadata.json"
        metadata = _load_json_object(metadata_path, "backend shard metadata")
        metadata["planHash"] = "0" * 64
        _write_json_atomic(metadata_path, metadata)
    try:
        result = validate_backend_shard_suite(plan_path, output_dir, serial_attempt_path=serial_attempt_path)
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    result["launchOrder"] = order
    result["workerManifest"] = "workers.json"
    _write_json_atomic(output_dir / "suite-result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


def _backend_shard_cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="T633 deterministic backend shard authority")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build-backend-shard-plan")
    build.add_argument("--risk-plan", required=True, type=Path)
    build.add_argument("--scope", choices=("proof", "full"), required=True)
    build.add_argument("--output", required=True, type=Path)
    run = subparsers.add_parser("run-backend-shard")
    run.add_argument("--plan", required=True, type=Path)
    run.add_argument("--shard", required=True)
    run.add_argument("--output-dir", required=True, type=Path)
    suite = subparsers.add_parser("run-backend-shard-suite")
    suite.add_argument("--plan", required=True, type=Path)
    suite.add_argument("--output-dir", required=True, type=Path)
    suite.add_argument("--launch-order", choices=("forward", "reverse"), default="forward")
    suite.add_argument("--timeout-seconds", type=float, default=900.0)
    suite.add_argument("--inject", choices=("none", "failure", "crash", "timeout", "missing"), default="none")
    suite.add_argument("--tamper", choices=("none", "mismatch"), default="none")
    suite.add_argument("--serial-attempt", type=Path)
    validate = subparsers.add_parser("validate-backend-shard-suite")
    validate.add_argument("--plan", required=True, type=Path)
    validate.add_argument("--output-dir", required=True, type=Path)
    validate.add_argument("--serial-attempt", type=Path)
    args = parser.parse_args(argv)
    if args.command == "build-backend-shard-plan":
        plan = build_backend_shard_plan(args.risk_plan, scope=args.scope)
        _write_json_atomic(args.output, plan)
        print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "run-backend-shard":
        return _run_backend_shard(args.plan, args.shard, args.output_dir)
    if args.command == "run-backend-shard-suite":
        plan = _load_backend_shard_plan(args.plan)
        order = [item["id"] for item in plan["shards"]]
        if args.launch_order == "reverse":
            order.reverse()
        return run_backend_shard_suite(
            args.plan,
            args.output_dir,
            launch_order=order,
            timeout_seconds=args.timeout_seconds,
            injection=args.inject,
            tamper=args.tamper,
            serial_attempt_path=args.serial_attempt,
        )
    result = validate_backend_shard_suite(args.plan, args.output_dir, serial_attempt_path=args.serial_attempt)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(_backend_shard_cli())
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
