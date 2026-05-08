#!/usr/bin/env python3
"""Run a local synthetic smoke check for the operator evidence workflow.

This command wraps the existing offline workflow runner against repository
fixtures only. It writes the normal workflow outputs, checks that the best
status remains review-required, and verifies the unsafe fixture is rejected.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_workflow_run.py"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "operator_evidence"
DEFAULT_ARTIFACT_DIR = FIXTURE_ROOT / "sanitized_complete"
DEFAULT_UNSAFE_ARTIFACT_DIR = FIXTURE_ROOT / "unsafe_rejected"
EXPECTED_OUTPUTS = (
    "evidence-manifest.json",
    "bundle-summary.json",
    "release-review-report.md",
)
EXPECTED_BUNDLE_STATUS = "complete-review-required"
UNSAFE_REJECTION_CODES = {11, 13}
EXIT_OK = 0
EXIT_SMOKE_FAILED = 1


def _run_workflow(artifact_dir: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(WORKFLOW_SCRIPT),
            "check",
            "--artifact-dir",
            str(artifact_dir),
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={},
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("json_root_not_object")
    return payload


def _assert_expected_outputs(output_dir: Path) -> None:
    missing = [name for name in EXPECTED_OUTPUTS if not (output_dir / name).is_file()]
    if missing:
        raise RuntimeError("missingOutputs=" + ",".join(missing))


def _print(line: str, *, stderr: bool = False) -> None:
    print(f"[SMOKE] {line}", file=sys.stderr if stderr else sys.stdout)


def _fixture_dir(path: Path) -> Path:
    resolved = path.resolve()
    fixture_root = FIXTURE_ROOT.resolve()
    if not resolved.is_dir() or not resolved.is_relative_to(fixture_root):
        raise RuntimeError("artifactFixtureStatus=non-synthetic")
    return resolved


def _check_sanitized_fixture(artifact_dir: Path, output_dir: Path) -> str:
    result = _run_workflow(artifact_dir, output_dir)
    if result.returncode != 0:
        raise RuntimeError(f"sanitizedFixtureStatus=failed:{result.returncode}")
    _assert_expected_outputs(output_dir)

    bundle = _read_json_object(output_dir / "bundle-summary.json")
    bundle_status = str(bundle.get("bundleStatus") or "unknown")
    if bundle_status != EXPECTED_BUNDLE_STATUS:
        raise RuntimeError(f"bundleStatus={bundle_status}")
    if bundle.get("runtimeBehaviorChanged") is not False:
        raise RuntimeError("runtimeBehaviorChanged=unexpected")
    if bundle.get("networkCallsExecutedByValidator") is not False:
        raise RuntimeError("networkCallsExecutedByValidator=unexpected")
    if bundle.get("rawArtifactBodiesIncluded") is not False:
        raise RuntimeError("rawArtifactBodiesIncluded=unexpected")
    return bundle_status


def _check_unsafe_fixture(artifact_dir: Path, output_dir: Path) -> str:
    result = _run_workflow(artifact_dir, output_dir)
    if result.returncode == 0:
        return "unexpected-pass"
    if result.returncode not in UNSAFE_REJECTION_CODES:
        return f"unexpected-code:{result.returncode}"
    return "rejected-safely"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help="Synthetic sanitized fixture directory to smoke-check.",
    )
    parser.add_argument(
        "--unsafe-artifact-dir",
        type=Path,
        default=DEFAULT_UNSAFE_ARTIFACT_DIR,
        help="Synthetic unsafe fixture directory expected to fail safely.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for sanitized smoke outputs. Defaults to a new temp directory.",
    )
    parser.add_argument(
        "--skip-unsafe-check",
        action="store_true",
        help="Skip the unsafe fixture rejection check.",
    )
    args = parser.parse_args(argv)

    output_dir = args.output_dir or Path(tempfile.mkdtemp(prefix="operator-evidence-smoke-"))
    unsafe_output_dir = output_dir.parent / f"{output_dir.name}-unsafe-check"

    try:
        artifact_dir = _fixture_dir(args.artifact_dir)
        unsafe_artifact_dir = _fixture_dir(args.unsafe_artifact_dir)
        bundle_status = _check_sanitized_fixture(artifact_dir, output_dir)
        unsafe_status = "skipped"
        if not args.skip_unsafe_check:
            unsafe_status = _check_unsafe_fixture(unsafe_artifact_dir, unsafe_output_dir)
            if unsafe_status != "rejected-safely":
                _print(f"unsafeFixtureStatus={unsafe_status}", stderr=True)
                return EXIT_SMOKE_FAILED
    except (OSError, json.JSONDecodeError, RuntimeError, ValueError) as exc:
        _print(str(exc), stderr=True)
        return EXIT_SMOKE_FAILED

    _print("artifactFixture=synthetic-sanitized")
    _print(f"outputDir={output_dir}")
    _print(f"bundleStatus={bundle_status}")
    _print("outputs=" + ",".join(EXPECTED_OUTPUTS))
    _print(f"unsafeFixtureStatus={unsafe_status}")
    _print("smokeStatus=pass")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
