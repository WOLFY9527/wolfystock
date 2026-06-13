from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "api_abuse_request_safety_evidence_check.py"
VALID_FIXTURE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "api_abuse_request_safety_evidence"
    / "accepted.synthetic.valid.json"
)
UNSAFE_FIXTURE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "api_abuse_request_safety_evidence"
    / "unsafe.synthetic.invalid.json"
)


def _run(fixture: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(fixture)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _json(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def test_api_abuse_request_safety_evidence_valid_fixture_is_evidence_ready() -> None:
    result = _run(VALID_FIXTURE)

    assert result.returncode == 0, result.stderr
    payload = _json(result)
    assert payload["schemaVersion"] == "wolfystock_api_abuse_request_safety_evidence_summary_v1"
    assert payload["status"] == "pass"
    assert payload["finalStatus"] == "EVIDENCE-READY"
    assert payload["manualReviewRequired"] is True
    assert payload["releaseApproved"] is False
    assert payload["publicLaunchReady"] is False
    assert payload["runtimeBehaviorChanged"] is False
    assert payload["networkCallsExecutedByValidator"] is False
    assert payload["rawRequestDataIncluded"] is False
    assert payload["checks"] == {
        "rateLimitInvalidRequestSummaryPresent": True,
        "oversizedPayloadSafetyPresent": True,
        "malformedInputRejectionPresent": True,
        "denialSanitizationPresent": True,
        "auditLogRedactionProofPresent": True,
        "leakageReviewPresent": True,
        "runtimeDefaultsUnchanged": True,
        "manualReviewAndNoLaunchApproval": True,
        "unsafeContentAbsent": True,
    }
    assert payload["artifact"]["operator"] == "sanitized-operator-label"
    assert payload["findings"] == []


def test_api_abuse_request_safety_evidence_rejects_unsafe_request_material_without_leaking() -> None:
    result = _run(UNSAFE_FIXTURE)

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    for forbidden in (
        "Bearer should-not-print",
        "dsa_session=should-not-print",
        "Traceback (most recent call last):",
        "password=should-not-print",
        "192.0.2.55",
        "user-real-account-123",
    ):
        assert forbidden not in combined_output
    payload = _json(result)
    assert payload["status"] == "fail"
    assert payload["finalStatus"] == "EVIDENCE-BLOCKED"
    assert payload["releaseApproved"] is False
    assert payload["publicLaunchReady"] is False
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert {
        "secret_or_header_marker_forbidden",
        "raw_request_material_forbidden",
        "debug_or_stack_trace_forbidden",
        "raw_ip_or_session_identifier_forbidden",
        "public_launch_approval_forbidden",
    }.issubset(reason_codes)
