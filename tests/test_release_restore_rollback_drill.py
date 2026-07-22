from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "release_restore_rollback_drill.py"


def _run_helper(*args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def _output(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def _write_json(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "release-restore-rollback-drill.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _candidate_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def _candidate_tree() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def _accepted_artifact() -> dict:
    return {
        "schemaVersion": "wolfystock_release_restore_rollback_drill_input_v1",
        "backupLabel": "backup-ref-20260509-main",
        "restoreDrillLabel": "restore-drill-20260509-isolated",
        "rollbackOwnerLabel": "release-rollback-owner",
        "releaseCandidateLabel": "rc-main-ff199f88",
        "rpoRtoNotes": "rpo-15m-rto-60m-reviewed",
        "frontendRollbackPlan": "manual-route-withdrawal-and-ui-revert-reviewed",
        "backendRollbackPlan": "manual-service-revert-after-diff-review",
        "databaseRollbackRestorePlan": "manual-isolated-restore-review-before-db-action",
        "adminAuthRecoveryNote": "admin-reauth-and-break-glass-review-recorded",
        "operatorAssertions": {
            "productionDbConnected": False,
            "secretsRead": False,
            "migrationsRun": False,
            "databasesRestored": False,
            "filesDeleted": False,
            "notificationsSent": False,
            "networkCallsMade": False,
            "destructiveOperationsExecuted": False,
        },
    }


def test_offline_default_mode_is_review_required_no_go() -> None:
    result = _run_helper("--offline")

    assert result.returncode == 0
    payload = _output(result)
    assert payload["drillStatus"] == "NO-GO"
    assert payload["restoreReady"] is False
    assert payload["rollbackReady"] is False
    assert payload["destructiveOperationsExecuted"] is False
    assert payload["networkCallsExecuted"] is False
    assert payload["manualReviewRequired"] is True
    assert payload["releaseApproved"] is False
    assert payload["checks"]["requiredFields"]["missingFields"] == [
        "backupLabel",
        "restoreDrillLabel",
        "rollbackOwnerLabel",
        "releaseCandidateLabel",
        "rpoRtoNotes",
        "frontendRollbackPlan",
        "backendRollbackPlan",
        "databaseRollbackRestorePlan",
        "adminAuthRecoveryNote",
    ]


def test_sanitized_operator_artifact_is_review_ready_without_release_approval(tmp_path: Path) -> None:
    artifact = _write_json(tmp_path, _accepted_artifact())

    result = _run_helper("--offline", "--artifact", str(artifact))

    assert result.returncode == 0
    payload = _output(result)
    assert payload["drillStatus"] == "REVIEW-READY"
    assert payload["restoreReady"] is True
    assert payload["rollbackReady"] is True
    assert payload["manualReviewRequired"] is True
    assert payload["releaseApproved"] is False
    assert payload["destructiveOperationsExecuted"] is False
    assert payload["networkCallsExecuted"] is False
    assert payload["checks"]["requiredFields"]["missingFields"] == []
    assert payload["checks"]["safety"]["unsafeFindingCount"] == 0

    candidate_sha = _candidate_sha()
    local_result = _run_helper("--local-isolated", "--expected-sha", candidate_sha)

    assert local_result.returncode == 0
    local_payload = _output(local_result)
    assert local_payload["mode"] == "local_isolated_execution"
    assert local_payload["drillStatus"] == "QUALIFIED_LOCAL_ISOLATED"
    assert local_payload["restoreReady"] is True
    assert local_payload["rollbackReady"] is True
    assert local_payload["releaseApproved"] is False
    assert local_payload["manualReviewRequired"] is True
    assert local_payload["productionStorageTouched"] is False
    assert local_payload["networkCallsExecuted"] is False
    assert local_payload["productionDestructiveOperationsExecuted"] is False
    assert local_payload["isolatedDatabaseActionsExecuted"] is True
    assert local_payload["isolatedRollbackTargetReplacementExecuted"] is True
    assert local_payload["qualificationScope"] == "local_isolated_release_profile"
    assert local_payload["candidate"]["sha"] == candidate_sha
    assert local_payload["candidate"]["tree"] == _candidate_tree()
    assert local_payload["identities"]["configurationSha256"]
    assert local_payload["identities"]["backupMetadataSha256"]
    assert local_payload["identities"]["backupSha256"]
    assert local_payload["identities"]["restoreSha256"]
    assert local_payload["identities"]["schemaSha256"]
    assert local_payload["rollbackDecision"] == "executed_to_verified_backup"
    assert local_payload["observedRpoSeconds"] == 0
    assert local_payload["observedRtoSeconds"] >= 0
    assert {check["id"] for check in local_payload["checks"]} == {
        "managed_test_isolation",
        "candidate_identity",
        "backup_metadata_and_checksum",
        "restore_to_separate_clean_target",
        "restored_application_startup",
        "user_session_role_and_owner_isolation",
        "schema_identity",
        "controlled_rollback",
    }
    assert {check["status"] for check in local_payload["checks"]} == {"pass"}

    mismatched_candidate = _run_helper("--local-isolated", "--expected-sha", "0" * 40)

    assert mismatched_candidate.returncode == 1
    mismatch_payload = _output(mismatched_candidate)
    assert mismatch_payload["drillStatus"] == "NO-GO"
    assert mismatch_payload["restoreReady"] is False
    assert mismatch_payload["rollbackReady"] is False
    assert mismatch_payload["failureCode"] == "candidate_identity_mismatch"
    assert mismatch_payload["productionStorageTouched"] is False
    assert mismatch_payload["productionDestructiveOperationsExecuted"] is False
    assert mismatch_payload["isolatedDatabaseActionsExecuted"] is False
    assert mismatch_payload["isolatedRollbackTargetReplacementExecuted"] is False


def test_missing_fields_keep_drill_in_no_go_posture(tmp_path: Path) -> None:
    payload = _accepted_artifact()
    payload.pop("databaseRollbackRestorePlan")
    artifact = _write_json(tmp_path, payload)

    result = _run_helper("--offline", "--artifact", str(artifact))

    assert result.returncode == 1
    evidence = _output(result)
    assert evidence["drillStatus"] == "NO-GO"
    assert evidence["restoreReady"] is False
    assert evidence["rollbackReady"] is False
    assert evidence["manualReviewRequired"] is True
    assert evidence["releaseApproved"] is False
    assert evidence["checks"]["requiredFields"]["missingFields"] == ["databaseRollbackRestorePlan"]


def test_unsafe_paths_and_secret_like_values_are_rejected_without_echoing(tmp_path: Path) -> None:
    secret_value = "raw-secret-value-should-not-print"
    payload = _accepted_artifact()
    payload["backupLabel"] = f"postgresql://restore_user:{secret_value}@prod.example.invalid/wolfystock"
    payload["frontendRollbackPlan"] = "/etc/passwd"
    artifact = _write_json(tmp_path, payload)

    result = _run_helper("--offline", "--artifact", str(artifact))

    assert result.returncode == 1
    assert secret_value not in result.stdout
    assert secret_value not in result.stderr
    evidence = _output(result)
    assert evidence["drillStatus"] == "NO-GO"
    findings = evidence["checks"]["safety"]["findings"]
    reason_codes = {finding["reasonCode"] for finding in findings}
    assert "secret_like_value_detected" in reason_codes
    assert "unsafe_path_like_value" in reason_codes
    assert evidence["checks"]["safety"]["findingValuesIncluded"] is False


def test_destructive_text_is_rejected_and_no_destructive_operations_run(tmp_path: Path) -> None:
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    payload = _accepted_artifact()
    payload["databaseRollbackRestorePlan"] = "dropdb wolfystock_production"
    artifact = _write_json(tmp_path, payload)

    result = _run_helper("--offline", "--artifact", str(artifact))

    assert result.returncode == 1
    assert sentinel.read_text(encoding="utf-8") == "keep"
    evidence = _output(result)
    assert evidence["destructiveOperationsExecuted"] is False
    assert evidence["networkCallsExecuted"] is False
    reason_codes = {finding["reasonCode"] for finding in evidence["checks"]["safety"]["findings"]}
    assert "destructive_operation_text_not_allowed" in reason_codes


def test_output_is_bounded_and_omits_raw_input_values(tmp_path: Path) -> None:
    payload = _accepted_artifact()
    payload["extraLargeOperatorNote"] = "token=raw-secret-value-should-not-print " * 200
    artifact = _write_json(tmp_path, payload)

    result = _run_helper("--offline", "--artifact", str(artifact))

    assert result.returncode == 1
    assert len(result.stdout) < 8000
    assert "raw-secret-value-should-not-print" not in result.stdout
    evidence = _output(result)
    assert len(evidence["checks"]["safety"]["findings"]) <= 20
    assert set(evidence) == {
        "schemaVersion",
        "inputSchemaVersion",
        "mode",
        "drillStatus",
        "restoreReady",
        "rollbackReady",
        "destructiveOperationsExecuted",
        "networkCallsExecuted",
        "manualReviewRequired",
        "releaseApproved",
        "runtimeBehaviorChanged",
        "checks",
    }
