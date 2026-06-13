from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_workflow_run.py"

EXPECTED_TEMPLATE_FILES = {
    "api_abuse_safety_evidence.json",
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

FORBIDDEN_PHRASES = (
    "launch-approved",
    "production-ready",
    "automatic-go",
    "automatic go",
)


def _run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _init_templates(path: Path) -> subprocess.CompletedProcess[str]:
    return _run("init", "--output-dir", path)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_forbidden_phrases_absent(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in lowered


def test_init_creates_all_templates(tmp_path: Path) -> None:
    output_dir = tmp_path / "templates"

    result = _init_templates(output_dir)

    assert result.returncode == 0, result.stderr
    assert {path.name for path in output_dir.glob("*.json")} == EXPECTED_TEMPLATE_FILES


def test_check_on_complete_sanitized_fixture_produces_review_required_report(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    assert _init_templates(artifact_dir).returncode == 0
    output_dir = tmp_path / "workflow-output"

    result = _run("check", "--artifact-dir", artifact_dir, "--output-dir", output_dir)

    assert result.returncode == 0, result.stderr
    bundle = _read_json(output_dir / "bundle-summary.json")
    manifest = _read_json(output_dir / "evidence-manifest.json")
    report = (output_dir / "release-review-report.md").read_text(encoding="utf-8")
    assert bundle["bundleStatus"] == "complete-review-required"
    assert manifest["schemaVersion"] == "wolfystock_operator_evidence_manifest_v1"
    assert "Manual operator review is required before any release decision." in report
    assert "complete-review-required" in report
    assert "rawArtifactBodiesIncluded" not in report


def test_missing_artifact_exits_non_zero(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    assert _init_templates(artifact_dir).returncode == 0
    (artifact_dir / "quota_budget_operator_evidence.json").unlink()

    result = _run("check", "--artifact-dir", artifact_dir, "--output-dir", tmp_path / "output")

    assert result.returncode != 0
    bundle = _read_json(tmp_path / "output" / "bundle-summary.json")
    assert bundle["bundleStatus"] == "incomplete-no-go"
    assert "required_artifact_missing" in result.stderr


def test_rejected_artifact_exits_non_zero(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    assert _init_templates(artifact_dir).returncode == 0
    provider_path = artifact_dir / "provider_operator_evidence.json"
    provider_path.write_text("{not json", encoding="utf-8")

    result = _run("check", "--artifact-dir", artifact_dir, "--output-dir", tmp_path / "output")

    assert result.returncode != 0
    bundle = _read_json(tmp_path / "output" / "bundle-summary.json")
    assert bundle["bundleStatus"] == "rejected-no-go"
    assert "artifact_read_failed" in result.stderr


def test_unsafe_marker_detection_exits_with_dedicated_code(tmp_path: Path) -> None:
    unsafe_value = "raw-secret-token=sk-live-should-not-leak"
    artifact_dir = tmp_path / "artifacts"
    assert _init_templates(artifact_dir).returncode == 0
    provider_path = artifact_dir / "provider_operator_evidence.json"
    provider = _read_json(provider_path)
    provider["api_key"] = unsafe_value
    provider_path.write_text(json.dumps(provider), encoding="utf-8")

    result = _run("check", "--artifact-dir", artifact_dir, "--output-dir", tmp_path / "output")

    assert result.returncode == 13
    combined = result.stdout + result.stderr + (tmp_path / "output" / "bundle-summary.json").read_text(
        encoding="utf-8"
    )
    assert "unsafe marker detection" in result.stderr
    assert "unsafe_marker" in combined
    assert unsafe_value not in combined


def test_report_output_contains_no_raw_unsafe_marker_values(tmp_path: Path) -> None:
    unsafe_value = "raw-secret-token=sk-live-should-not-leak"
    bundle_summary = tmp_path / "bundle-summary.json"
    bundle_summary.write_text(
        json.dumps(
            {
                "schemaVersion": "wolfystock_operator_evidence_bundle_summary_v1",
                "generatedAt": "2026-05-08T10:30:00+00:00",
                "artifactDirectoryLabel": "operator-bundle",
                "bundleStatus": "rejected-no-go",
                "runtimeBehaviorChanged": False,
                "networkCallsExecutedByValidator": False,
                "rawArtifactBodiesIncluded": False,
                "artifacts": [
                    {
                        "category": unsafe_value,
                        "pathLabel": "../session-cookie-dump.json",
                        "status": "rejected",
                        "validatorName": "traceback_secret_validator.py",
                        "blockingReasonSummaries": [unsafe_value, "stack trace contains password"],
                    }
                ],
                "advisories": [],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "release-review-report.md"

    result = _run("report", "--bundle-summary", bundle_summary, "--output", output)

    assert result.returncode != 0
    combined = result.stdout + result.stderr + output.read_text(encoding="utf-8")
    assert unsafe_value not in combined
    assert "session-cookie" not in combined
    assert "traceback" not in combined.lower()
    assert "password" not in combined.lower()
    assert "[redacted]" in combined


def test_runner_never_emits_approval_phrases(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    output_dir = tmp_path / "workflow-output"
    init_result = _init_templates(artifact_dir)
    check_result = _run("check", "--artifact-dir", artifact_dir, "--output-dir", output_dir)
    report_result = _run(
        "report",
        "--bundle-summary",
        output_dir / "bundle-summary.json",
        "--output",
        tmp_path / "report-only.md",
    )

    combined = (
        init_result.stdout
        + init_result.stderr
        + check_result.stdout
        + check_result.stderr
        + report_result.stdout
        + report_result.stderr
        + (output_dir / "bundle-summary.json").read_text(encoding="utf-8")
        + (output_dir / "release-review-report.md").read_text(encoding="utf-8")
        + (tmp_path / "report-only.md").read_text(encoding="utf-8")
    )
    assert init_result.returncode == 0
    assert check_result.returncode == 0
    assert report_result.returncode == 0
    _assert_forbidden_phrases_absent(combined)
