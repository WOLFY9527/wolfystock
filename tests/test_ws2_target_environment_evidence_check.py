from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ws2_target_environment_evidence_check.py"
TEMPLATE = (
    REPO_ROOT
    / "docs"
    / "audits"
    / "ws2-target-environment-evidence-template.json"
)

REQUIRED_CHECK_KEYS = {
    "apiASubmitTransportExercised",
    "syntheticWorkerLeaseFlowVerified",
    "workerLeaseAcquired",
    "progressPersisted",
    "apiBDurableStatusReadback",
    "apiBPollingReplayVerified",
    "apiBDurablePollingReadback",
    "ownerHiddenStatusVerified",
    "ownerHiddenPollingVerified",
    "retryFailureSafetyVerified",
    "leaseExpiryRecoveryVerified",
    "staleWorkerWriteRejected",
    "retryCapVerified",
    "terminalFailurePollable",
    "ownerIsolationVerified",
    "sanitizedFailureOutputVerified",
    "sseLimitationRecorded",
    "crossInstanceSseNotClaimed",
    "durablePollingBaselineRecorded",
}

FORBIDDEN_OUTPUT_MARKERS = (
    "authorization",
    "bearer",
    "cookie",
    "password",
    "raw_payload",
    "raw_request",
    "raw_response",
    "session",
    "stack trace",
    "stacktrace",
    "token",
    "traceback",
)


def _artifact(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "artifactVersion": "wolfystock_ws2_target_environment_evidence_v1",
        "validationProfile": "PROFILE_DURABLE_PROTECTED",
        "evidenceClass": "accepted-staging",
        "targetEnvironmentLabel": "staging-api-ab-primary",
        "runId": "ws2-ab-run-20260612-001",
        "operator": "ws2-platform-ops",
        "capturedAt": "2026-06-12T10:30:00Z",
        "submittedAt": "2026-06-12T10:20:00Z",
        "completedAt": "2026-06-12T10:28:00Z",
        "reviewerAcceptanceStatus": "accepted-staging",
        "reviewerLabel": "release-reviewer",
        "evidenceRedactionVersion": "ws2_target_environment_evidence_redaction_v1",
        "evidenceBoundary": {
            "syntheticLocalDryRunEvidence": False,
            "ciSyntheticEvidence": False,
            "targetEnvironmentEvidence": True,
            "acceptedStagingEvidence": True,
            "publicLaunchApproval": False,
        },
        "topology": {
            "apiAInstanceLabel": "api-a",
            "apiBInstanceLabel": "api-b",
            "workerLabel": "worker-a",
            "storageLabel": "staging-postgresql",
            "sseBroadcastScope": "process-local",
            "durablePollingBaseline": True,
            "externalSseReplayImplemented": False,
            "productionQueueBrokerCutover": False,
        },
        "checks": {
            "apiASubmitTransportExercised": True,
            "syntheticWorkerLeaseFlowVerified": True,
            "workerLeaseAcquired": True,
            "progressPersisted": True,
            "apiBDurableStatusReadback": True,
            "apiBPollingReplayVerified": True,
            "apiBDurablePollingReadback": True,
            "ownerHiddenStatusVerified": True,
            "ownerHiddenPollingVerified": True,
            "retryFailureSafetyVerified": True,
            "leaseExpiryRecoveryVerified": True,
            "staleWorkerWriteRejected": True,
            "retryCapVerified": True,
            "terminalFailurePollable": True,
            "ownerIsolationVerified": True,
            "sanitizedFailureOutputVerified": True,
            "sseLimitationRecorded": True,
            "crossInstanceSseNotClaimed": True,
            "durablePollingBaselineRecorded": True,
        },
        "summaries": {
            "apiASubmitTransport": "API A accepted a synthetic analysis submit over the staging HTTPS API.",
            "workerLease": "One worker acquired a bounded lease and duplicate active lease was blocked.",
            "progressPersistence": "Durable progress rows were observed with bounded sequence metadata.",
            "apiBDurableStatusReadback": "API B read the durable task status without API A process memory.",
            "apiBPollingReplay": "API B replayed durable progress events after a sequence cursor.",
            "apiBDurablePolling": "API B read durable status and replayed progress after a cursor.",
            "ownerHiddenStatus": "Cross-owner status read returned hidden not-found.",
            "ownerHiddenPolling": "Cross-owner polling read returned hidden not-found.",
            "retryFailureSafety": "Retry cap and terminal failure behavior were summarized with safe reason codes.",
            "leaseExpiryRecovery": "A second worker reclaimed the task after lease expiry.",
            "staleWorkerWriteRejection": "The stale worker could not write terminal state after reclaim.",
            "ownerIsolation": "Cross-owner status and polling reads returned hidden not-found responses.",
            "sanitizedFailureOutput": "Failure output contained only safe reason codes and no traceback text.",
            "sseLimitation": "Process-local SSE limitation remained recorded; durable polling was the baseline.",
            "reviewNotes": "Sanitized staging/API A-B evidence accepted for manual review only.",
        },
    }
    payload.update(overrides)
    return payload


def _write_json(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "ws2-target-environment-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run_validator(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _stdout_json(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return json.loads(result.stdout)


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


def test_accepts_sanitized_accepted_staging_api_ab_evidence(tmp_path: Path) -> None:
    path = _write_json(tmp_path, _artifact())

    result = _run_validator(path)

    assert result.returncode == 0, result.stderr
    payload = _stdout_json(result)
    assert payload["schemaVersion"] == "wolfystock_ws2_target_environment_evidence_validation_v1"
    assert payload["status"] == "pass"
    assert payload["artifactStatus"] == "accepted-staging-review-required"
    assert payload["validationProfile"] == "PROFILE_DURABLE_PROTECTED"
    assert payload["acceptanceEvidenceProfile"] == "PROFILE_WS2_ACCEPTANCE_EVIDENCE_SCOPED"
    assert payload["advisoryOnly"] is True
    assert payload["manualReviewRequired"] is True
    assert payload["launchAcceptanceIntegrated"] is False
    assert payload["runtimeBehaviorChanged"] is False
    assert payload["networkCallsExecutedByValidator"] is False
    assert payload["publicLaunchReady"] is False
    assert payload["checks"]["requiredEvidenceFieldsPresent"] is True
    assert payload["checks"]["acceptedStagingEvidenceComplete"] is True
    assert payload["checks"]["sseLimitationAndPollingBaselineRecorded"] is True
    assert payload["checks"]["noLaunchApprovalClaim"] is True
    assert set(payload["acceptanceDimensions"]) == {
        "api_a_submit",
        "worker_lease_synthetic_worker",
        "api_b_durable_read",
        "polling_replay",
        "owner_isolation",
        "retry_failure_safety",
        "sse_limitation_handling",
    }
    assert all(dimension["passed"] is True for dimension in payload["acceptanceDimensions"].values())
    assert all(
        dimension["publicLaunchReady"] is False
        for dimension in payload["acceptanceDimensions"].values()
    )
    assert payload["acceptanceDimensions"]["api_b_durable_read"]["requiredChecks"] == [
        "apiBDurableStatusReadback"
    ]
    assert payload["acceptanceDimensions"]["polling_replay"]["requiredChecks"] == [
        "apiBPollingReplayVerified",
        "apiBDurablePollingReadback",
        "durablePollingBaselineRecorded",
    ]
    assert payload["acceptanceDimensions"]["sse_limitation_handling"]["sseBroadcastScope"] == "process-local"
    assert payload["acceptanceDimensions"]["sse_limitation_handling"]["externalSseReplayImplemented"] is False
    assert payload["artifact"]["targetEnvironmentLabel"] == "staging-api-ab-primary"
    assert payload["artifact"]["runId"] == "ws2-ab-run-20260612-001"
    assert payload["artifact"]["reviewerAcceptanceStatus"] == "accepted-staging"
    assert payload["artifact"]["evidenceBoundary"] == {
        "syntheticLocalDryRunEvidence": False,
        "ciSyntheticEvidence": False,
        "targetEnvironmentEvidence": True,
        "acceptedStagingEvidence": True,
        "publicLaunchApproval": False,
    }
    assert set(payload["artifact"]["checks"]) == REQUIRED_CHECK_KEYS
    assert set(payload["artifact"]["checks"].values()) == {True}


def test_sanitized_template_validates_as_needs_review_without_acceptance() -> None:
    result = _run_validator(TEMPLATE)

    assert result.returncode == 0, result.stderr
    payload = _stdout_json(result)
    assert payload["status"] == "pass"
    assert payload["artifactStatus"] == "needs-review"
    assert payload["publicLaunchReady"] is False
    assert payload["artifact"]["reviewerAcceptanceStatus"] == "needs-review"
    assert payload["artifact"]["evidenceBoundary"]["targetEnvironmentEvidence"] is False
    assert payload["artifact"]["evidenceBoundary"]["acceptedStagingEvidence"] is False
    assert payload["artifact"]["evidenceBoundary"]["publicLaunchApproval"] is False
    assert payload["checks"]["acceptedStagingEvidenceComplete"] is False
    assert payload["acceptanceDimensions"]["api_a_submit"]["passed"] is False
    assert payload["acceptanceDimensions"]["sse_limitation_handling"]["passed"] is True


def test_accepted_staging_requires_all_target_evidence_fields_true(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact["checks"]["apiBPollingReplayVerified"] = False
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert payload["status"] == "fail"
    assert {
        finding["reasonCode"] for finding in payload["findings"]
    } >= {"accepted_staging_requires_required_checks_true"}
    assert payload["acceptanceDimensions"]["polling_replay"]["passed"] is False


def test_secret_raw_debug_and_launch_claims_are_rejected_without_echoing_values(tmp_path: Path) -> None:
    unsafe_value = "Be" + "arer should-not-appear-in-output"
    artifact = _artifact(
        publicLaunchApproval=True,
        operatorNotes={
            "authHeader": unsafe_value,
            "debugTrace": "Traceback (most recent call last): sanitized",
        },
        summaries={
            **_artifact()["summaries"],
            "reviewNotes": "Launch-approved. GO for public launch with raw_response captured.",
        },
    )
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    combined = _combined_output(result)
    assert result.returncode == 1
    assert unsafe_value not in combined
    assert "should-not-appear" not in combined
    payload = _stdout_json(result)
    assert {
        finding["reasonCode"] for finding in payload["findings"]
    } >= {
        "launch_approval_claim_forbidden",
        "raw_debug_or_body_marker_forbidden",
        "secret_or_cookie_marker_forbidden",
    }


def test_rejects_cross_instance_sse_and_runtime_cutover_claims(tmp_path: Path) -> None:
    artifact = _artifact(
        topology={
            **_artifact()["topology"],
            "sseBroadcastScope": "cross-instance",
            "durablePollingBaseline": False,
            "externalSseReplayImplemented": True,
            "productionQueueBrokerCutover": True,
        },
        summaries={
            **_artifact()["summaries"],
            "sseLimitation": "Cross-instance SSE is safe and accepted for the public topology.",
        },
    )
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert {
        finding["reasonCode"] for finding in payload["findings"]
    } >= {
        "invalid_sse_broadcast_scope",
        "durable_polling_baseline_required",
        "external_sse_replay_cutover_forbidden",
        "queue_broker_cutover_forbidden",
        "cross_instance_sse_acceptance_forbidden",
    }


def test_script_stays_offline_and_imports_no_runtime_modules() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])

    assert not ({"api", "src", "requests", "httpx", "urllib", "socket"} & imported_roots)

    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("urlopen", "requests.", "httpx.", "socket.", "DatabaseManager"):
        assert forbidden not in source
