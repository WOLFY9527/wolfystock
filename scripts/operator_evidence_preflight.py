#!/usr/bin/env python3
"""Run bounded offline operator evidence preflight checks.

The preflight wraps existing local checks and emits a small JSON summary for
manual review. It does not read environment values, call networks, inspect
deployment state, print raw artifact bodies, mutate runtime behavior, or
integrate with launch acceptance.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_SMOKE_SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_workflow_smoke.py"
WORKFLOW_RUN_SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_workflow_run.py"
SCHEMA_VERSION = "wolfystock_operator_evidence_preflight_v1"
PASS_STATUS = "preflight-pass-review-required"
FAIL_STATUS = "preflight-fail-review-required"
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


class CheckSpec(NamedTuple):
    check_id: str
    command: tuple[str, ...]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run_check(check: CheckSpec) -> dict[str, object]:
    result = subprocess.run(
        list(check.command),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={},
    )
    entry: dict[str, object] = {
        "id": check.check_id,
        "status": "pass" if result.returncode == 0 else "fail",
        "exitCode": result.returncode,
    }
    if result.returncode != 0:
        entry["failureSummary"] = f"exit_code_{result.returncode}"
    return entry


def _default_checks(temp_root: Path) -> tuple[CheckSpec, ...]:
    workflow_output = temp_root / "workflow-smoke"
    return (
        CheckSpec(
            "workflow-smoke",
            (
                sys.executable,
                str(WORKFLOW_SMOKE_SCRIPT),
                "--output-dir",
                str(workflow_output),
            ),
        ),
        CheckSpec(
            "docs-safety-guard",
            (
                sys.executable,
                "-m",
                "pytest",
                "tests/test_operator_evidence_docs_safety.py",
                "-q",
            ),
        ),
        CheckSpec(
            "evidence-gap-analysis",
            (
                sys.executable,
                "-m",
                "pytest",
                "tests/test_operator_evidence_gap_analyzer.py",
                "-q",
            ),
        ),
        CheckSpec(
            "fixture-pack-validation",
            (
                sys.executable,
                "-m",
                "pytest",
                "tests/test_operator_evidence_fixture_pack.py",
                "-q",
            ),
        ),
    )


def _artifact_check(artifact_dir: Path, temp_root: Path) -> CheckSpec:
    return CheckSpec(
        "local-artifact-workflow",
        (
            sys.executable,
            str(WORKFLOW_RUN_SCRIPT),
            "check",
            "--artifact-dir",
            str(artifact_dir),
            "--output-dir",
            str(temp_root / "local-artifact-workflow"),
        ),
    )


def run_preflight(
    checks: tuple[CheckSpec, ...],
    *,
    temp_root: Path | None = None,
    artifact_dir: Path | None = None,
) -> tuple[int, dict[str, object]]:
    owned_temp: tempfile.TemporaryDirectory[str] | None = None
    if temp_root is None:
        owned_temp = tempfile.TemporaryDirectory(prefix="operator-evidence-preflight-")
        temp_root = Path(owned_temp.name)
    temp_root.mkdir(parents=True, exist_ok=True)

    selected_checks = checks
    modes = ["synthetic"]
    if artifact_dir is not None:
        modes.append("artifact-dir")
        selected_checks = (*selected_checks, _artifact_check(artifact_dir, temp_root))

    try:
        check_results = [_run_check(check) for check in selected_checks]
    finally:
        if owned_temp is not None:
            owned_temp.cleanup()

    failed = any(check["status"] != "pass" for check in check_results)
    summary: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": _now_iso(),
        "preflightStatus": FAIL_STATUS if failed else PASS_STATUS,
        "modes": modes,
        "manualReviewRequired": True,
        "releaseApproved": False,
        "launchApproved": False,
        "runtimeBehaviorChanged": False,
        "networkCallsExecuted": False,
        "rawArtifactBodiesIncluded": False,
        "checks": check_results,
    }
    return (EXIT_FAILED if failed else EXIT_OK), summary


def _write_summary(summary: dict[str, object]) -> None:
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--synthetic",
        action="store_true",
        required=True,
        help="Acknowledge that the default preflight uses repository synthetic fixtures only.",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        help="Optional local sanitized artifact directory for an additional workflow check.",
    )
    args = parser.parse_args(argv)

    artifact_dir = args.artifact_dir
    if artifact_dir is not None and not artifact_dir.is_dir():
        summary = {
            "schemaVersion": SCHEMA_VERSION,
            "generatedAt": _now_iso(),
            "preflightStatus": FAIL_STATUS,
            "modes": ["synthetic", "artifact-dir"],
            "manualReviewRequired": True,
            "releaseApproved": False,
            "launchApproved": False,
            "runtimeBehaviorChanged": False,
            "networkCallsExecuted": False,
            "rawArtifactBodiesIncluded": False,
            "checks": [
                {
                    "id": "local-artifact-workflow",
                    "status": "fail",
                    "exitCode": EXIT_USAGE,
                    "failureSummary": "artifact_dir_not_found",
                }
            ],
        }
        _write_summary(summary)
        return EXIT_FAILED

    with tempfile.TemporaryDirectory(prefix="operator-evidence-preflight-") as temp_dir:
        temp_root = Path(temp_dir)
        exit_code, summary = run_preflight(
            _default_checks(temp_root),
            temp_root=temp_root,
            artifact_dir=artifact_dir,
        )
        _write_summary(summary)
        return exit_code


if __name__ == "__main__":
    sys.exit(main())
