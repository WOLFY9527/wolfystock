"""Pytest hooks for explicit domain ownership and attempt evidence."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "validation" / "domain_test_topology.json"
_ACTIVE_CONFIG: pytest.Config | None = None


def _load_manifest(config: pytest.Config) -> dict[str, Any]:
    configured = Path(config.getoption("--domain-topology-manifest"))
    path = configured if configured.is_absolute() else ROOT / configured
    try:
        from scripts.domain_test_topology import load_manifest, validate_manifest

        manifest = load_manifest(path)
        validate_manifest(manifest)
        return manifest
    except (OSError, ValueError) as exc:
        raise pytest.UsageError(f"invalid domain topology manifest {path}: {exc}") from exc


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("domain-topology", "domain-owned test topology")
    group.addoption(
        "--domain-topology-manifest",
        default=str(DEFAULT_MANIFEST.relative_to(ROOT)),
        help="Domain topology manifest path relative to the repository root.",
    )
    group.addoption("--domain-topology-verify-full", action="store_true", default=False)
    group.addoption("--domain-topology-bootstrap", action="store_true", default=False, help=argparse.SUPPRESS)
    group.addoption("--domain-topology-collect-output", default=None, metavar="PATH")
    group.addoption("--domain-topology-attempt-output", default=None, metavar="PATH")
    group.addoption("--domain-topology-attempt-index", type=int, default=0)
    group.addoption("--domain-topology-select-file", default=None, metavar="PATH")


def pytest_configure(config: pytest.Config) -> None:
    global _ACTIVE_CONFIG
    _ACTIVE_CONFIG = config
    config._domain_topology_started_at = datetime.now(UTC).isoformat()  # type: ignore[attr-defined]
    config._domain_topology_timer = time.perf_counter()  # type: ignore[attr-defined]
    config._domain_topology_records = defaultdict(  # type: ignore[attr-defined]
        lambda: {"durationSeconds": 0.0, "outcome": None}
    )


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(
    session: pytest.Session,
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    all_ids = [item.nodeid for item in items]
    config._domain_topology_collected_ids = all_ids  # type: ignore[attr-defined]
    config._domain_topology_network_tests = [  # type: ignore[attr-defined]
        {
            "id": item.nodeid,
            "owner": item.get_closest_marker("network").kwargs.get("owner"),
            "reason": item.get_closest_marker("network").kwargs.get("reason"),
            "audit": item.get_closest_marker("network").kwargs.get("audit"),
        }
        for item in items
        if item.get_closest_marker("network") is not None
    ]
    if config.getoption("--domain-topology-bootstrap"):
        config._domain_topology_domains = {}  # type: ignore[attr-defined]
        return

    manifest = _load_manifest(config)
    ownership = {entry["id"]: entry["domain"] for entry in manifest["backend"]["tests"]}
    unowned = sorted(set(all_ids) - set(ownership))
    if unowned:
        raise pytest.UsageError("unowned backend tests (manifest update required):\n- " + "\n- ".join(unowned))
    if config.getoption("--domain-topology-verify-full"):
        missing = sorted(set(ownership) - set(all_ids))
        if missing:
            raise pytest.UsageError("manifest-owned backend tests missing from discovery:\n- " + "\n- ".join(missing))
        if config._domain_topology_network_tests != manifest["backend"]["networkTests"]:  # type: ignore[attr-defined]
            raise pytest.UsageError("audited network marker inventory differs from the domain topology manifest")

    selected_path = config.getoption("--domain-topology-select-file")
    if selected_path:
        selected = set(json.loads(Path(selected_path).read_text(encoding="utf-8")))
        unknown = sorted(selected - set(all_ids))
        if unknown:
            raise pytest.UsageError("retry selection contains unknown tests:\n- " + "\n- ".join(unknown))
        deselected = [item for item in items if item.nodeid not in selected]
        items[:] = [item for item in items if item.nodeid in selected]
        config.hook.pytest_deselected(items=deselected)

    config._domain_topology_domains = ownership  # type: ignore[attr-defined]
    config._domain_topology_selected_ids = [item.nodeid for item in items]  # type: ignore[attr-defined]


def pytest_collection_finish(session: pytest.Session) -> None:
    output = session.config.getoption("--domain-topology-collect-output")
    if output:
        _write_json(
            Path(output),
            {
                "ids": sorted(getattr(session.config, "_domain_topology_collected_ids", [])),
                "networkTests": sorted(
                    getattr(session.config, "_domain_topology_network_tests", []), key=lambda item: item["id"]
                ),
            },
        )


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    config = _ACTIVE_CONFIG
    if config is None:
        return
    records = getattr(config, "_domain_topology_records", None)
    if records is None:
        return
    record = records[report.nodeid]
    record["durationSeconds"] += report.duration
    if report.when == "setup" and report.skipped:
        record["outcome"] = "skipped"
    elif report.when == "setup" and report.failed:
        record["outcome"] = "error"
    elif report.when == "call":
        record["outcome"] = "passed" if report.passed else "skipped" if report.skipped else "failed"
    elif report.when == "teardown" and report.failed:
        record["outcome"] = "error"


def _attempt_payload(session: pytest.Session, exitstatus: int) -> dict[str, Any]:
    config = session.config
    domains = getattr(config, "_domain_topology_domains", {})
    records = getattr(config, "_domain_topology_records", {})
    selected = getattr(config, "_domain_topology_selected_ids", [])
    tests: list[dict[str, Any]] = []
    for nodeid in sorted(selected):
        record = records.get(nodeid, {"durationSeconds": 0.0, "outcome": "error"})
        tests.append(
            {
                "id": nodeid,
                "domain": domains[nodeid],
                "outcome": record.get("outcome") or "error",
                "durationSeconds": round(float(record.get("durationSeconds", 0.0)), 6),
            }
        )
    counts = Counter(test["outcome"] for test in tests)
    domain_payload: dict[str, Any] = {}
    for test in tests:
        domain = domain_payload.setdefault(
            test["domain"],
            {"counts": {"passed": 0, "failed": 0, "skipped": 0, "error": 0}, "durationSeconds": 0.0},
        )
        domain["counts"][test["outcome"]] += 1
        domain["durationSeconds"] += test["durationSeconds"]
    for value in domain_payload.values():
        value["durationSeconds"] = round(value["durationSeconds"], 6)
    return {
        "schemaVersion": 1,
        "surface": "backend",
        "attemptIndex": config.getoption("--domain-topology-attempt-index"),
        "startedAt": config._domain_topology_started_at,  # type: ignore[attr-defined]
        "durationSeconds": round(time.perf_counter() - config._domain_topology_timer, 6),  # type: ignore[attr-defined]
        "exitCode": int(exitstatus),
        "collectedCount": len(getattr(config, "_domain_topology_collected_ids", [])),
        "selectedCount": len(selected),
        "counts": {outcome: counts.get(outcome, 0) for outcome in ("passed", "failed", "skipped", "error")},
        "domains": dict(sorted(domain_payload.items())),
        "failures": [test["id"] for test in tests if test["outcome"] in {"failed", "error"}],
        "tests": tests,
    }


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    global _ACTIVE_CONFIG
    output = session.config.getoption("--domain-topology-attempt-output")
    if output and hasattr(session.config, "_domain_topology_domains"):
        _write_json(Path(output), _attempt_payload(session, exitstatus))
    _ACTIVE_CONFIG = None
