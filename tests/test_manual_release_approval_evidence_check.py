from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "manual_release_approval_evidence_check.py"


def _artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifactVersion": "wolfystock_manual_release_approval_review_record_v1",
        "releaseCandidateSha": "5a72431e4baf7fa87d43ecae73a10d831451bafb",
        "reviewerRoleLabels": ["release-manager", "security-reviewer"],
        "approvalMeetingOrTicketRef": "release-review-ticket-2026-05-08",
        "approvalTimestamp": "2026-05-08T10:45:00Z",
        "evidenceBundleRef": "launch-acceptance-evidence-pack-v1",
        "knownResidualRisks": [
            "async-enrichment-risk-acknowledged",
            "manual-rollback-risk-acknowledged",
        ],
        "rollbackOwnerLabel": "release-rollback-owner",
        "goNoGoDecision": "approved-for-manual-release-review",
        "evidenceRedactionVersion": "manual-release-review-redaction-v1",
    }
    payload.update(overrides)
    return payload


def _write_json(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "manual-release-approval-review-record.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run_validator(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--artifact", str(path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _stdout_json(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(result.stdout)


def test_sanitized_manual_review_record_is_valid_without_release_approval(tmp_path: Path) -> None:
    result = _run_validator(_write_json(tmp_path, _artifact()))

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["manualReviewStatus"] == "review-record-valid"
    assert payload["releaseApproved"] is False
    assert payload["runtimeBehaviorChanged"] is False
    assert payload["launchAcceptanceIntegrated"] is False
    assert payload["artifact"]["goNoGoDecision"] == "approved-for-manual-release-review"


def test_input_release_approved_true_is_rejected_and_not_echoed_as_approval(tmp_path: Path) -> None:
    result = _run_validator(_write_json(tmp_path, _artifact(releaseApproved=True)))

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert payload["manualReviewStatus"] == "rejected"
    assert payload["releaseApproved"] is False
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "release_approval_boolean_forbidden" in reason_codes


def test_unsafe_pii_secrets_and_raw_logs_are_rejected_without_echoing_values(tmp_path: Path) -> None:
    secret_value = "sk-" + "a" * 30
    payload = _artifact(
        reviewerRoleLabels=["release-manager", "person@example.invalid"],
        rawMeetingTranscript="Operator said api_key=" + secret_value,
        debugTrace="Traceback (most recent call last): should-not-print",
    )
    result = _run_validator(_write_json(tmp_path, payload))

    assert result.returncode == 1
    assert secret_value not in result.stdout
    assert secret_value not in result.stderr
    assert "should-not-print" not in result.stdout
    assert "should-not-print" not in result.stderr
    evidence = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in evidence["findings"]}
    assert "unsafe_reviewer_role_label" in reason_codes
    assert "raw_transcript_or_screenshot_forbidden" in reason_codes
    assert "debug_or_stack_trace_forbidden" in reason_codes
    assert "secret_marker_forbidden" in reason_codes


def test_missing_residual_risk_acknowledgement_is_rejected(tmp_path: Path) -> None:
    result = _run_validator(_write_json(tmp_path, _artifact(knownResidualRisks=[])))

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert payload["manualReviewStatus"] == "rejected"
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "missing_residual_risk_acknowledgement" in reason_codes


def test_go_or_launch_approved_wording_is_rejected(tmp_path: Path) -> None:
    payload = _artifact(
        approvalMeetingOrTicketRef="launch-approved",
        notes="Production-ready automatic-GO approved for launch.",
    )
    result = _run_validator(_write_json(tmp_path, payload))

    assert result.returncode == 1
    evidence = _stdout_json(result)
    assert evidence["manualReviewStatus"] == "rejected"
    assert evidence["releaseApproved"] is False
    reason_codes = {finding["reasonCode"] for finding in evidence["findings"]}
    assert "launch_approval_claim_forbidden" in reason_codes
