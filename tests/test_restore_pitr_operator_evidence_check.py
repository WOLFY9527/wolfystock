from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "restore_pitr_operator_evidence_check.py"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "restore_pitr_operator_evidence"


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


def _accepted_artifact() -> dict:
    return {
        "schemaVersion": "wolfystock_restore_pitr_operator_evidence_input_v1",
        "evidenceMode": "real-isolated-drill",
        "drillId": "restore-pitr-2026-05-08-001",
        "environment": "isolated-restore",
        "operator": "ops-oncall-sanitized",
        "startedAt": "2026-05-08T09:00:00Z",
        "completedAt": "2026-05-08T09:37:00Z",
        "backupArtifactRef": "backup-ref:sha256-0123456789abcdef",
        "restoreTarget": "restore-target:sandbox-pg-20260508",
        "restoreCommandExecuted": True,
        "destructiveProductionCommandExecuted": False,
        "pitrTargetTimestamp": "2026-05-08T08:45:00Z",
        "verificationQueries": [
            {
                "label": "auth-row-count",
                "resultKind": "count",
                "observedCount": 12,
                "expectedCount": 12,
                "checksum": "sha256:auth-count-fixture",
            },
            {
                "label": "portfolio-checksum",
                "resultKind": "checksum",
                "checksum": "sha256:portfolio-fixture",
            },
        ],
        "rpoObservedSeconds": 420,
        "rtoObservedSeconds": 2220,
        "outcome": "accepted",
        "evidenceRedactionVersion": "restore-pitr-redaction-v1",
        "isolatedTarget": {
            "targetLabel": "restore-target:sandbox-pg-20260508",
            "environment": "isolated-restore",
            "isolationBoundaryRef": "isolation-boundary:ticket-001",
            "productionStorageTouched": False,
        },
        "backupArtifactSummary": {
            "artifactRef": "backup-ref:sha256-0123456789abcdef",
            "artifactKind": "encrypted-base-backup",
            "walArchiveSummaryRef": "wal-range:sha256-abcdef0123456789",
            "sourceEnvironmentLabel": "source-backup-label",
            "rawPathIncluded": False,
        },
        "pitrTarget": {
            "targetTimestamp": "2026-05-08T08:45:00Z",
            "targetRef": "pitr-target:pre-drill-checkpoint",
            "walReplaySummaryRef": "wal-replay:bounded-summary",
        },
        "restoreExecutionSummary": {
            "restoreCommandExecuted": True,
            "executedOutsideValidator": True,
            "localOnlyDryRun": False,
            "productionDbMutation": False,
            "destructiveProductionCommandExecuted": False,
            "commandSummaryRef": "restore-command-summary:ticket-001",
        },
        "postRestoreSmoke": {
            "appBootReadiness": "pass",
            "schemaCompatibility": "pass",
            "sampledQuerySummaries": ["query-summary:auth-count", "query-summary:portfolio-checksum"],
        },
        "ownerIsolationSmoke": {
            "ownerScopeChecked": True,
            "crossOwnerAccessBlocked": True,
            "sampledOwnerLabelRefs": ["owner-sample:alpha", "owner-sample:beta"],
        },
        "rollbackDecisionPoint": {
            "decision": "rollback-not-required",
            "decidedAt": "2026-05-08T09:38:00Z",
            "decisionRef": "rollback-review:ticket-001",
        },
        "operatorApprovals": [
            {
                "role": "restore-operator",
                "approved": True,
                "approvedAt": "2026-05-08T09:39:00Z",
                "approvalRef": "approval:restore-operator",
            },
            {
                "role": "release-reviewer",
                "approved": True,
                "approvedAt": "2026-05-08T09:40:00Z",
                "approvalRef": "approval:release-reviewer",
            },
        ],
        "sanitizedArtifactReferences": [
            {
                "kind": "validator-output",
                "label": "restore-pitr-validator-output",
                "ref": "artifact-ref:restore-pitr-validator-output",
            },
            {
                "kind": "review-ticket",
                "label": "manual-review-ticket",
                "ref": "review-ticket:restore-pitr-001",
            },
        ],
        "localGeneration": {
            "checkerRanRestoreCommands": False,
            "networkCallsEnabled": False,
            "productionStorageTouched": False,
            "productionSecretsRead": False,
            "rawLogsIncluded": False,
            "runtimeBehaviorChanged": False,
        },
    }


def test_restore_pitr_operator_evidence_accepts_sanitized_artifact(tmp_path: Path) -> None:
    path = tmp_path / "accepted-restore-pitr-evidence.json"
    path.write_text(json.dumps(_accepted_artifact()), encoding="utf-8")

    result = _run_helper("--artifact", str(path))

    assert result.returncode == 0
    evidence = _output(result)
    assert evidence["schemaVersion"] == "wolfystock_restore_pitr_operator_evidence_v1"
    assert evidence["finalStatus"] == "EVIDENCE-READY"
    assert evidence["launchApproved"] is False
    assert evidence["runtimeBehaviorChanged"] is False
    assert evidence["databaseCommandsRunByValidator"] is False
    assert evidence["checks"][0]["id"] == "operator_artifact_required_fields_are_complete"
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["real_drill_required_sections_are_complete"]["status"] == "pass"
    assert checks["real_drill_evidence_not_local_preflight_or_template"]["status"] == "pass"
    assert checks["backup_artifact_summary_is_sanitized_and_bounded"]["status"] == "pass"
    assert checks["restore_execution_summary_proves_real_isolated_drill"]["status"] == "pass"
    assert checks["post_restore_smoke_summaries_are_present"]["status"] == "pass"
    assert checks["owner_isolation_smoke_is_present"]["status"] == "pass"
    assert checks["rollback_decision_point_is_recorded"]["status"] == "pass"
    assert checks["operator_approvals_are_sanitized"]["status"] == "pass"
    assert checks["sanitized_artifact_references_are_bounded"]["status"] == "pass"
    assert {check["status"] for check in evidence["checks"]} == {"pass"}


def test_restore_pitr_operator_evidence_rejects_secret_values_without_echoing(tmp_path: Path) -> None:
    secret_value = "raw-secret-value-should-not-print"
    payload = _accepted_artifact()
    payload["backupArtifactRef"] = f"postgresql://restore_user:{secret_value}@prod.example.invalid/wolfystock"
    path = tmp_path / "unsafe-secret-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper("--artifact", str(path))

    assert result.returncode == 1
    assert secret_value not in result.stdout
    assert secret_value not in result.stderr
    evidence = _output(result)
    assert evidence["finalStatus"] == "NO-GO"
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["artifact_contains_no_sensitive_or_raw_values"]["status"] == "fail"
    assert checks["artifact_contains_no_sensitive_or_raw_values"]["evidence"]["unsafeFindingCount"] >= 1
    assert checks["artifact_contains_no_sensitive_or_raw_values"]["evidence"]["findingValuesIncluded"] is False


def test_restore_pitr_operator_evidence_rejects_raw_sql_dump(tmp_path: Path) -> None:
    payload = _accepted_artifact()
    payload["verificationQueries"].append(
        {
            "label": "unsafe-raw-dump",
            "resultKind": "raw",
            "rawDump": "CREATE TABLE users(id int); INSERT INTO users VALUES (1);",
        }
    )
    path = tmp_path / "raw-sql-dump-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper("--artifact", str(path))

    assert result.returncode == 1
    checks = {check["id"]: check for check in _output(result)["checks"]}
    assert checks["artifact_contains_no_sensitive_or_raw_values"]["status"] == "fail"


def test_restore_pitr_operator_evidence_rejects_production_destructive_marker(tmp_path: Path) -> None:
    payload = _accepted_artifact()
    payload["destructiveProductionCommandExecuted"] = True
    payload["operatorCommandSummary"] = "dropdb wolfystock_production"
    path = tmp_path / "destructive-production-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper("--artifact", str(path))

    assert result.returncode == 1
    evidence = _output(result)
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["restore_target_is_isolated_and_non_destructive"]["status"] == "fail"
    assert checks["artifact_contains_no_sensitive_or_raw_values"]["status"] == "fail"


def test_restore_pitr_operator_evidence_rejects_launch_approval_claim(tmp_path: Path) -> None:
    payload = _accepted_artifact()
    payload["outcome"] = "accepted"
    payload["launchApproved"] = True
    payload["operatorConclusion"] = "GO"
    path = tmp_path / "launch-approval-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper("--artifact", str(path))

    assert result.returncode == 1
    checks = {check["id"]: check for check in _output(result)["checks"]}
    assert checks["artifact_does_not_claim_launch_approval"]["status"] == "fail"


def test_restore_pitr_operator_evidence_rejects_public_launch_ready_claim(tmp_path: Path) -> None:
    payload = _accepted_artifact()
    payload["publicLaunchReady"] = True
    path = tmp_path / "public-launch-ready-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper("--artifact", str(path))

    assert result.returncode == 1
    evidence = _output(result)
    assert evidence["launchApproved"] is False
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["artifact_does_not_claim_launch_approval"]["status"] == "fail"


def test_restore_pitr_operator_evidence_rejects_needs_review_outcome(tmp_path: Path) -> None:
    payload = _accepted_artifact()
    payload["outcome"] = "needs-review"
    path = tmp_path / "needs-review-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper("--artifact", str(path))

    assert result.returncode == 1
    evidence = _output(result)
    assert evidence["finalStatus"] == "NO-GO"
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["operator_outcome_is_accepted"]["status"] == "fail"


def test_restore_pitr_operator_evidence_rejects_template_or_local_preflight_as_real(
    tmp_path: Path,
) -> None:
    payload = _accepted_artifact()
    payload["evidenceMode"] = "local-synthetic-preflight"
    payload["templatePlaceholders"] = {"replaceBeforeReview": ["<review-ticket-label>"]}
    payload["restoreExecutionSummary"]["localOnlyDryRun"] = True
    path = tmp_path / "local-preflight-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper("--artifact", str(path))

    assert result.returncode == 1
    checks = {check["id"]: check for check in _output(result)["checks"]}
    assert checks["real_drill_evidence_not_local_preflight_or_template"]["status"] == "fail"


def test_restore_pitr_operator_evidence_rejects_private_hosts_usernames_paths_and_stacktraces(
    tmp_path: Path,
) -> None:
    payload = _accepted_artifact()
    payload["backupArtifactSummary"]["internalHostSummary"] = "primary-db.internal"
    payload["restoreExecutionSummary"]["username"] = "restore_admin"
    payload["sanitizedArtifactReferences"].append(
        {
            "kind": "operator-log",
            "label": "unsafe-log-reference",
            "ref": "/Users/operator/private-backups/restore.log",
        }
    )
    payload["postRestoreSmoke"]["diagnosticSummary"] = "Traceback (most recent call last): unsafe-stack"
    path = tmp_path / "unsafe-sensitive-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper("--artifact", str(path))

    assert result.returncode == 1
    assert "restore_admin" not in result.stdout
    assert "/Users/operator/private-backups/restore.log" not in result.stdout
    assert "unsafe-stack" not in result.stdout
    checks = {check["id"]: check for check in _output(result)["checks"]}
    assert checks["artifact_contains_no_sensitive_or_raw_values"]["status"] == "fail"
    reason_codes = {
        finding["reasonCode"]
        for finding in checks["artifact_contains_no_sensitive_or_raw_values"]["evidence"]["findings"]
    }
    assert {
        "private_hostname_detected",
        "sensitive_key_contains_value",
        "sensitive_path_detected",
        "secret_like_value_detected",
    }.issubset(reason_codes)


def test_restore_pitr_operator_evidence_accepts_valid_real_drill_fixture() -> None:
    result = _run_helper("--artifact", str(FIXTURE_ROOT / "real_isolated_drill_valid.json"))

    assert result.returncode == 0
    evidence = _output(result)
    assert evidence["finalStatus"] == "EVIDENCE-READY"
    assert evidence["artifactSummary"]["evidenceMode"] == "real-isolated-drill"
    assert {check["status"] for check in evidence["checks"]} == {"pass"}


def test_restore_pitr_operator_evidence_rejects_local_preflight_fixture() -> None:
    result = _run_helper("--artifact", str(FIXTURE_ROOT / "local_preflight_rejected.json"))

    assert result.returncode == 1
    evidence = _output(result)
    assert evidence["finalStatus"] == "NO-GO"
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["real_drill_evidence_not_local_preflight_or_template"]["status"] == "fail"
    assert checks["restore_execution_summary_proves_real_isolated_drill"]["status"] == "fail"
