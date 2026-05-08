from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "release_restore_rollback_drill.py"


def _run_helper(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        cwd=REPO_ROOT,
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
