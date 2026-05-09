from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_workflow_smoke.py"

EXPECTED_OUTPUT_FILES = {
    "evidence-manifest.json",
    "bundle-summary.json",
    "release-review-report.md",
}
FORBIDDEN_APPROVAL_PHRASES = (
    "launch-" + "approved",
    "production-" + "ready",
    "automatic-" + "go",
    "automatic " + "go",
    "public launch " + "go",
)
UNSAFE_FIXTURE_VALUES = (
    "fixture-unsafe-api-key-value-should-not-leak",
    "fixture-unsafe-raw-response-value-should-not-leak",
)


def _run_smoke(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SMOKE_SCRIPT), *map(str, args)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_bounded_sanitized_output(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_APPROVAL_PHRASES:
        assert phrase not in lowered
    for unsafe_value in UNSAFE_FIXTURE_VALUES:
        assert unsafe_value not in text
    for line in text.splitlines():
        assert len(line) <= 180
    assert "{" not in text
    assert "}" not in text


def test_operator_evidence_workflow_smoke_uses_synthetic_fixture_pack(tmp_path: Path) -> None:
    output_dir = tmp_path / "operator-evidence-smoke"

    result = _run_smoke("--output-dir", output_dir)

    assert result.returncode == 0, result.stderr
    assert {path.name for path in output_dir.iterdir()} == EXPECTED_OUTPUT_FILES
    manifest = _read_json(output_dir / "evidence-manifest.json")
    bundle = _read_json(output_dir / "bundle-summary.json")
    report = (output_dir / "release-review-report.md").read_text(encoding="utf-8")
    assert manifest["artifactDirectoryLabel"] == "sanitized_complete"
    assert len(manifest["entries"]) == 8
    assert bundle["bundleStatus"] == "complete-review-required"
    assert bundle["runtimeBehaviorChanged"] is False
    assert bundle["networkCallsExecutedByValidator"] is False
    assert bundle["rawArtifactBodiesIncluded"] is False
    assert "Manual operator review is required before any release decision." in report
    assert "does not approve launch" in report
    assert "smokeStatus=pass" in result.stdout
    assert "bundleStatus=complete-review-required" in result.stdout
    assert "unsafeFixtureStatus=rejected-safely" in result.stdout
    assert "approve" not in result.stdout.lower()
    _assert_bounded_sanitized_output(result.stdout + result.stderr)


def test_operator_evidence_workflow_smoke_fails_if_unsafe_fixture_is_not_rejected(tmp_path: Path) -> None:
    output_dir = tmp_path / "operator-evidence-smoke"
    safe_fixture = REPO_ROOT / "tests" / "fixtures" / "operator_evidence" / "sanitized_complete"

    result = _run_smoke(
        "--output-dir",
        output_dir,
        "--unsafe-artifact-dir",
        safe_fixture,
    )

    assert result.returncode != 0
    assert "unsafeFixtureStatus=unexpected-pass" in result.stderr
    assert "smokeStatus=pass" not in result.stdout
    assert "approve" not in (result.stdout + result.stderr).lower()
    _assert_bounded_sanitized_output(result.stdout + result.stderr)


def test_operator_evidence_workflow_smoke_rejects_non_fixture_artifact_dirs(tmp_path: Path) -> None:
    output_dir = tmp_path / "operator-evidence-smoke"
    non_fixture_dir = tmp_path / "operator-input"
    non_fixture_dir.mkdir()

    result = _run_smoke(
        "--artifact-dir",
        non_fixture_dir,
        "--output-dir",
        output_dir,
        "--skip-unsafe-check",
    )

    assert result.returncode != 0
    assert "artifactFixtureStatus=non-synthetic" in result.stderr
    assert "smokeStatus=pass" not in result.stdout
    _assert_bounded_sanitized_output(result.stdout + result.stderr)
