from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ws2_multi_instance_smoke.py"
EXPECTED_CHECK_IDS = {
    "api_a_submit",
    "worker_lease",
    "api_b_durable_read",
    "polling_replay",
    "owner_isolation",
    "lease_expiry_retry",
    "failure_safety",
}
FORBIDDEN_OUTPUT_MARKERS = (
    "api_key",
    "authorization",
    "bearer",
    "cookie",
    "password",
    "raw_payload",
    "raw_request",
    "raw_response",
    "secret",
    "session",
    "stack trace",
    "stacktrace",
    "token",
    "traceback",
)


def _run_preflight(*args: object, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    safe_env = os.environ.copy()
    safe_env.pop("WOLFYSTOCK_WS2_MULTI_INSTANCE_SMOKE_ENABLE_NETWORK", None)
    if env:
        safe_env.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=safe_env,
    )


def _stdout_json(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(result.stdout)


def _combined(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


def _assert_bounded_sanitized_output(result: subprocess.CompletedProcess[str]) -> None:
    combined = _combined(result)
    assert len(combined) <= 24_000
    for line in combined.splitlines():
        assert len(line) <= 420
    lowered = combined.lower()
    for marker in FORBIDDEN_OUTPUT_MARKERS:
        assert marker not in lowered


def test_dry_run_outputs_planned_offline_multi_instance_checks() -> None:
    result = _run_preflight("--dry-run")

    assert result.returncode == 0, result.stderr
    payload = _stdout_json(result)
    assert payload["schemaVersion"] == "wolfystock_ws2_multi_instance_smoke_preflight_v1"
    assert payload["validationProfile"] == "PROFILE_DURABLE_PROTECTED"
    assert payload["acceptanceEvidenceProfile"] == "PROFILE_WS2_ACCEPTANCE_EVIDENCE_SCOPED"
    assert payload["preflightStatus"] == "dry-run-review-required"
    assert payload["mode"] == "dry-run"
    assert payload["manualReviewRequired"] is True
    assert payload["runtimeBehaviorChanged"] is False
    assert payload["networkCallsExecuted"] is False
    assert payload["stagingCallsEnabled"] is False
    assert payload["storageMode"] == "disposable-sqlite"
    assert payload["evidenceBoundary"] == {
        "acceptedStagingEvidence": False,
        "ciSyntheticEvidence": False,
        "durablePollingBaseline": True,
        "liveStagingCallsImplemented": False,
        "publicLaunchReady": False,
        "sseCrossInstanceReliable": False,
        "syntheticLocalDryRunEvidence": False,
        "targetEnvironmentEvidence": False,
    }
    assert payload["sseLimitation"] == {
        "broadcastScope": "process-local",
        "durableFallback": "durable-task-polling",
        "externalReplayImplemented": False,
        "operatorMessage": "process-local SSE is not cross-instance reliable; durable polling remains the multi-instance baseline",
    }
    assert payload["payloadPolicy"] == {
        "credentialValuesIncluded": False,
        "rawBodiesIncluded": False,
        "exceptionDetailsIncluded": False,
    }
    checks = payload["checks"]
    assert {check["id"] for check in checks} == EXPECTED_CHECK_IDS
    assert {check["status"] for check in checks} == {"planned"}
    assert all(check["wouldCheck"] for check in checks)
    _assert_bounded_sanitized_output(result)


def test_synthetic_preflight_runs_disposable_smoke_and_sanitized_evidence() -> None:
    result = _run_preflight("--synthetic")

    assert result.returncode == 0, result.stderr
    payload = _stdout_json(result)
    assert payload["preflightStatus"] == "preflight-pass-review-required"
    assert payload["mode"] == "synthetic"
    assert payload["validationProfile"] == "PROFILE_DURABLE_PROTECTED"
    assert payload["acceptanceEvidenceProfile"] == "PROFILE_WS2_ACCEPTANCE_EVIDENCE_SCOPED"
    assert payload["manualReviewRequired"] is True
    assert payload["runtimeBehaviorChanged"] is False
    assert payload["networkCallsExecuted"] is False
    assert payload["stagingCallsEnabled"] is False
    assert payload["storageMode"] == "disposable-sqlite"
    assert payload["apiRuntimeTouched"] is False
    assert payload["taskRuntimeSemanticsChanged"] is False
    checks = payload["checks"]
    assert {check["id"] for check in checks} == EXPECTED_CHECK_IDS
    assert {check["status"] for check in checks} == {"pass"}
    evidence_by_id = {check["id"]: check["evidence"] for check in checks}
    assert evidence_by_id["api_a_submit"]["apiInstance"] == "api-a"
    assert evidence_by_id["api_a_submit"]["transportExercised"] is False
    assert evidence_by_id["api_a_submit"]["targetEnvironmentEvidence"] is False
    assert evidence_by_id["api_a_submit"]["storedStatus"] == "queued"
    assert evidence_by_id["worker_lease"]["progressPersisted"] is True
    assert evidence_by_id["worker_lease"]["progressEventRecorded"] is True
    assert evidence_by_id["worker_lease"]["duplicateActiveLeaseBlocked"] is True
    assert evidence_by_id["api_b_durable_read"]["apiInstance"] == "api-b"
    assert evidence_by_id["api_b_durable_read"]["processMemoryShared"] is False
    assert evidence_by_id["api_b_durable_read"]["pollingFallbackUsed"] is True
    assert evidence_by_id["api_b_durable_read"]["visibleStatus"] == "completed"
    assert evidence_by_id["api_b_durable_read"]["latestSequence"] == 4
    assert evidence_by_id["polling_replay"]["durablePollingBaseline"] is True
    assert evidence_by_id["polling_replay"]["replaySequences"] == [2, 3]
    assert evidence_by_id["polling_replay"]["latestSequence"] == 4
    assert evidence_by_id["polling_replay"]["boundedByLimit"] is True
    assert evidence_by_id["owner_isolation"]["ownerValueIncluded"] is False
    assert evidence_by_id["owner_isolation"]["syntheticOwnerIsolationRepresented"] is True
    assert evidence_by_id["owner_isolation"]["crossOwnerStatusCode"] == 404
    assert evidence_by_id["owner_isolation"]["crossOwnerPollStatusCode"] == 404
    assert evidence_by_id["lease_expiry_retry"]["leaseExpirySimulated"] is True
    assert evidence_by_id["lease_expiry_retry"]["reclaimedAttemptCount"] == 2
    assert evidence_by_id["lease_expiry_retry"]["staleWorkerWriteRejected"] is True
    assert evidence_by_id["lease_expiry_retry"]["terminalWriteAccepted"] is True
    assert evidence_by_id["failure_safety"]["retryCapEnforced"] is True
    assert evidence_by_id["failure_safety"]["retryStatuses"] == ["retry_queued", "failed"]
    assert evidence_by_id["failure_safety"]["failedTaskPollable"] is True
    assert evidence_by_id["failure_safety"]["failureEventRecorded"] is True
    assert evidence_by_id["failure_safety"]["credentialValueIncluded"] is False
    assert evidence_by_id["failure_safety"]["safeFailureCode"] == "non_retryable_synthetic_error"
    assert payload["evidenceBoundary"]["syntheticLocalDryRunEvidence"] is True
    assert payload["evidenceBoundary"]["acceptedStagingEvidence"] is False
    assert payload["evidenceBoundary"]["targetEnvironmentEvidence"] is False
    assert payload["evidenceBoundary"]["publicLaunchReady"] is False
    _assert_bounded_sanitized_output(result)


def test_staging_target_is_dry_run_only_without_network_opt_in() -> None:
    result = _run_preflight("--dry-run", "--staging-base-url", "https://staging.example.invalid")

    assert result.returncode == 0, result.stderr
    payload = _stdout_json(result)
    assert payload["mode"] == "dry-run"
    assert payload["networkCallsExecuted"] is False
    assert payload["stagingCallsEnabled"] is False
    assert payload["stagingOptInSatisfied"] is False
    assert payload["stagingTargetLabel"] == "staging-url-configured"
    _assert_bounded_sanitized_output(result)


def test_staging_target_opt_in_remains_non_network_non_approval_evidence() -> None:
    result = _run_preflight(
        "--dry-run",
        "--staging-base-url",
        "https://staging.example.invalid",
        env={"WOLFYSTOCK_WS2_MULTI_INSTANCE_SMOKE_ENABLE_NETWORK": "1"},
    )

    assert result.returncode == 0, result.stderr
    payload = _stdout_json(result)
    assert payload["mode"] == "dry-run"
    assert payload["networkCallsExecuted"] is False
    assert payload["stagingCallsEnabled"] is False
    assert payload["stagingOptInSatisfied"] is False
    assert payload["releaseApproved"] is False
    assert payload["publicLaunchReady"] is False
    _assert_bounded_sanitized_output(result)


def test_script_help_runs_directly() -> None:
    result = _run_preflight("--help")

    assert result.returncode == 0
    assert "--dry-run" in result.stdout
    assert "--synthetic" in result.stdout
    assert "WOLFYSTOCK_WS2_MULTI_INSTANCE_SMOKE_ENABLE_NETWORK" not in result.stdout
