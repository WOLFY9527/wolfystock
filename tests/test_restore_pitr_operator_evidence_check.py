from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "restore_pitr_operator_evidence_check.py"


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
