from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "operator_evidence"
SANITIZED_COMPLETE = FIXTURE_ROOT / "sanitized_complete"
UNSAFE_REJECTED = FIXTURE_ROOT / "unsafe_rejected"
WORKFLOW_SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_workflow_run.py"

EXPECTED_FILES = {
    "provider_operator_evidence.json",
    "provider_sla_licensing_evidence.json",
    "notification_delivery_rehearsal_evidence.json",
    "restore_pitr_operator_evidence.json",
    "security_operator_acceptance.json",
    "quota_budget_operator_evidence.json",
    "staging_ingress_operator_evidence.json",
    "ws2_sse_operator_decision_evidence.json",
    "config_snapshot_evidence.json",
    "manual_release_approval_review_record.json",
}

FORBIDDEN_OUTPUT_PHRASES = (
    "launch-" + "approved",
    "production-" + "ready",
    "automatic-" + "go",
    "automatic " + "go",
    "public launch " + "go",
)
UNSAFE_FIXTURE_VALUES = (
    "fixture-unsafe-api-key-value-should-not-leak",
    "fixture-unsafe-raw-response-value-should-not-leak",
    "fixture-restore-raw-log-value-should-not-leak",
    "fixture-restore-username-should-not-leak",
)
SANITIZED_FORBIDDEN_MARKERS = (
    "://",
    "@",
    *UNSAFE_FIXTURE_VALUES,
)


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
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture_files(path: Path) -> set[str]:
    return {item.name for item in path.glob("*.json")}


def _combined_file_text(path: Path) -> str:
    return "\n".join(item.read_text(encoding="utf-8") for item in sorted(path.glob("*.json")))


def _assert_report_never_approves_launch(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_OUTPUT_PHRASES:
        assert phrase not in lowered


def test_operator_evidence_fixture_packs_have_current_workflow_files() -> None:
    assert _fixture_files(SANITIZED_COMPLETE) == EXPECTED_FILES
    assert _fixture_files(UNSAFE_REJECTED) == EXPECTED_FILES


def test_sanitized_complete_fixture_pack_runs_offline_as_review_required(tmp_path: Path) -> None:
    output_dir = tmp_path / "workflow-output"

    result = _run_workflow(SANITIZED_COMPLETE, output_dir)

    assert result.returncode == 0, result.stderr
    bundle = _read_json(output_dir / "bundle-summary.json")
    report = (output_dir / "release-review-report.md").read_text(encoding="utf-8")
    assert bundle["bundleStatus"] == "complete-review-required"
    assert bundle["runtimeBehaviorChanged"] is False
    assert bundle["networkCallsExecutedByValidator"] is False
    assert bundle["rawArtifactBodiesIncluded"] is False
    assert {artifact["status"] for artifact in bundle["artifacts"]} == {"needs-review"}
    assert "Manual operator review is required before any release decision." in report
    assert "does not approve launch" in report
    _assert_report_never_approves_launch(result.stdout + result.stderr + json.dumps(bundle) + report)


def test_unsafe_rejected_fixture_pack_fails_without_leaking_raw_values(tmp_path: Path) -> None:
    output_dir = tmp_path / "workflow-output"

    result = _run_workflow(UNSAFE_REJECTED, output_dir)

    assert result.returncode == 13
    bundle = _read_json(output_dir / "bundle-summary.json")
    report = (output_dir / "release-review-report.md").read_text(encoding="utf-8")
    combined = result.stdout + result.stderr + json.dumps(bundle) + report
    assert bundle["bundleStatus"] == "rejected-no-go"
    assert "unsafe_marker" in combined
    for unsafe_value in UNSAFE_FIXTURE_VALUES:
        assert unsafe_value not in combined
    _assert_report_never_approves_launch(combined)


def test_sanitized_fixture_files_contain_no_forbidden_markers() -> None:
    text = _combined_file_text(SANITIZED_COMPLETE).lower()

    for marker in SANITIZED_FORBIDDEN_MARKERS:
        assert marker not in text


def test_unsafe_marker_values_are_confined_to_unsafe_rejected_fixture_pack() -> None:
    safe_text = _combined_file_text(SANITIZED_COMPLETE)
    unsafe_text = _combined_file_text(UNSAFE_REJECTED)

    for unsafe_value in UNSAFE_FIXTURE_VALUES:
        assert unsafe_value not in safe_text
        assert unsafe_value in unsafe_text


def test_restore_pitr_unsafe_fixture_differs_from_review_template() -> None:
    safe_payload = _read_json(SANITIZED_COMPLETE / "restore_pitr_operator_evidence.json")
    unsafe_payload = _read_json(UNSAFE_REJECTED / "restore_pitr_operator_evidence.json")

    assert safe_payload["evidenceMode"] == "local-synthetic-preflight"
    assert safe_payload["outcome"] == "needs-review"
    assert unsafe_payload["evidenceMode"] == "real-isolated-drill"
    assert unsafe_payload["outcome"] == "accepted"
    assert unsafe_payload["restoreExecutionSummary"]["username"] == "fixture-restore-username-should-not-leak"
