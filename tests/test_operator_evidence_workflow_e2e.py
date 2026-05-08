from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_workflow_run.py"
MANIFEST_SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_manifest_check.py"

EXPECTED_TEMPLATE_FILES = {
    "provider_operator_evidence.json",
    "restore_pitr_operator_evidence.json",
    "security_operator_acceptance.json",
    "quota_budget_operator_evidence.json",
    "staging_ingress_operator_evidence.json",
    "ws2_sse_operator_decision_evidence.json",
    "config_snapshot_evidence.json",
    "manual_release_approval_review_record.json",
}
EXPECTED_TEMPLATE_CATEGORIES = {
    "provider",
    "restore-pitr",
    "security",
    "quota-budget",
    "staging-ingress",
    "ws2-sse",
    "config-snapshot",
    "manual-release-approval",
}
FORBIDDEN_APPROVAL_PHRASES = (
    "launch-" + "approved",
    "production-" + "ready",
    "automatic-" + "go",
    "automatic " + "go",
    "public launch " + "go",
)
RAW_BODY_SENTINEL = "SENTINEL_BODY_CONTENT_NEVER_RENDER_20260508"


def _run_workflow(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(WORKFLOW_SCRIPT), *map(str, args)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_manifest_verify(artifact_dir: Path, manifest: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(MANIFEST_SCRIPT),
            "verify",
            "--artifact-dir",
            str(artifact_dir),
            "--manifest",
            str(manifest),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _init_artifacts(artifact_dir: Path) -> None:
    result = _run_workflow("init", "--output-dir", artifact_dir)
    assert result.returncode == 0, result.stderr
    assert {path.name for path in artifact_dir.glob("*.json")} == EXPECTED_TEMPLATE_FILES


def _assert_safe_output(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_APPROVAL_PHRASES:
        assert phrase not in lowered
    assert RAW_BODY_SENTINEL not in text


def _combined_outputs(*paths: Path, processes: subprocess.CompletedProcess[str] | None = None) -> str:
    text = ""
    if processes is not None:
        text += processes.stdout + processes.stderr
    for path in paths:
        text += path.read_text(encoding="utf-8")
    return text


def test_operator_evidence_workflow_smoke_generates_review_required_outputs(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "sanitized-artifacts"
    output_dir = tmp_path / "workflow-output"
    report_only = tmp_path / "report-only.md"

    _init_artifacts(artifact_dir)
    provider_path = artifact_dir / "provider_operator_evidence.json"
    provider = _read_json(provider_path)
    provider["notes"] = RAW_BODY_SENTINEL
    provider_path.write_text(json.dumps(provider), encoding="utf-8")

    check = _run_workflow("check", "--artifact-dir", artifact_dir, "--output-dir", output_dir)
    report = _run_workflow("report", "--bundle-summary", output_dir / "bundle-summary.json", "--output", report_only)

    assert check.returncode == 0, check.stderr
    assert report.returncode == 0, report.stderr
    manifest_path = output_dir / "evidence-manifest.json"
    bundle_path = output_dir / "bundle-summary.json"
    rendered_report_path = output_dir / "release-review-report.md"
    assert manifest_path.is_file()
    assert bundle_path.is_file()
    assert rendered_report_path.is_file()
    assert report_only.is_file()

    manifest = _read_json(manifest_path)
    bundle = _read_json(bundle_path)
    rendered_report = rendered_report_path.read_text(encoding="utf-8")
    assert manifest["schemaVersion"] == "wolfystock_operator_evidence_manifest_v1"
    assert bundle["bundleStatus"] == "complete-review-required"
    assert bundle["runtimeBehaviorChanged"] is False
    assert bundle["networkCallsExecutedByValidator"] is False
    assert bundle["rawArtifactBodiesIncluded"] is False
    assert {artifact["category"] for artifact in bundle["artifacts"]} == EXPECTED_TEMPLATE_CATEGORIES
    assert {artifact["pathLabel"] for artifact in bundle["artifacts"]} == EXPECTED_TEMPLATE_FILES
    assert bundle["advisories"] == []
    assert "unknown-extra-artifact" not in json.dumps(bundle)
    assert "Advisories:" not in rendered_report
    for category in EXPECTED_TEMPLATE_CATEGORIES:
        assert f"| {category} | needs-review |" in rendered_report
    assert "Manual operator review is required before any release decision." in rendered_report
    assert "This report is informational only and does not approve launch." in rendered_report
    assert "rawArtifactBodiesIncluded" not in rendered_report
    assert "rawArtifactBodiesIncluded" not in report_only.read_text(encoding="utf-8")

    combined = _combined_outputs(manifest_path, bundle_path, rendered_report_path, report_only, processes=check)
    combined += report.stdout + report.stderr
    _assert_safe_output(combined)


def test_operator_evidence_workflow_missing_artifact_is_incomplete_no_go(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "sanitized-artifacts"
    output_dir = tmp_path / "workflow-output"
    _init_artifacts(artifact_dir)
    (artifact_dir / "quota_budget_operator_evidence.json").unlink()

    result = _run_workflow("check", "--artifact-dir", artifact_dir, "--output-dir", output_dir)

    assert result.returncode != 0
    bundle = _read_json(output_dir / "bundle-summary.json")
    report = (output_dir / "release-review-report.md").read_text(encoding="utf-8")
    assert bundle["bundleStatus"] == "incomplete-no-go"
    assert "required_artifact_missing" in result.stderr
    assert "NO-GO - incomplete evidence bundle" in report
    assert "rawArtifactBodiesIncluded" not in report
    _assert_safe_output(result.stdout + result.stderr + json.dumps(bundle) + report)


def test_operator_evidence_workflow_manifest_detects_tampered_artifact(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "sanitized-artifacts"
    output_dir = tmp_path / "workflow-output"
    _init_artifacts(artifact_dir)
    check = _run_workflow("check", "--artifact-dir", artifact_dir, "--output-dir", output_dir)
    assert check.returncode == 0, check.stderr

    provider_path = artifact_dir / "provider_operator_evidence.json"
    provider = _read_json(provider_path)
    provider["notes"] = "tampered after manifest creation"
    provider_path.write_text(json.dumps(provider), encoding="utf-8")

    verify = _run_manifest_verify(artifact_dir, output_dir / "evidence-manifest.json")

    assert verify.returncode != 0
    payload = json.loads(verify.stdout)
    assert payload["verificationStatus"] == "fail"
    assert {
        "category": "provider",
        "fileLabel": "provider_operator_evidence.json",
        "reasonCode": "checksum_changed",
    } in payload["findings"]
    _assert_safe_output(verify.stdout + verify.stderr)
