from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "incident_response_evidence.py"


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


def _accepted_evidence() -> dict:
    return {
        "schemaVersion": "wolfystock_incident_response_evidence_input_v1",
        "mode": "synthetic_local",
        "adminAuditEvidence": {
            "events": [
                {
                    "family": "admin_security",
                    "action": "mfa_break_glass_denied",
                    "actorIncluded": True,
                    "outcomeIncluded": True,
                    "sanitized": True,
                    "rawPayloadIncluded": False,
                    "secretValuesIncluded": False,
                },
                {
                    "family": "admin_cost",
                    "action": "budget_alert_dry_run",
                    "actorIncluded": True,
                    "outcomeIncluded": True,
                    "sanitized": True,
                    "rawPayloadIncluded": False,
                    "secretValuesIncluded": False,
                },
                {
                    "family": "admin_provider",
                    "action": "provider_circuit_probe_failed",
                    "actorIncluded": True,
                    "outcomeIncluded": True,
                    "sanitized": True,
                    "rawPayloadIncluded": False,
                    "secretValuesIncluded": False,
                },
                {
                    "family": "admin_quota",
                    "action": "quota_reservation_would_block",
                    "actorIncluded": True,
                    "outcomeIncluded": True,
                    "sanitized": True,
                    "rawPayloadIncluded": False,
                    "secretValuesIncluded": False,
                },
            ]
        },
        "cleanupEvidence": {
            "dryRunDefaultVerified": True,
            "explicitExecuteRequired": True,
            "previewBeforeDelete": True,
            "minimumRetentionProtected": True,
            "sanitizedAuditTrail": True,
            "destructiveByDefault": False,
        },
        "failureEvidence": {
            "providerFailureSanitized": True,
            "notificationFailureSanitized": True,
            "releaseCheckFailureSanitized": True,
            "actionableReasonCodes": ["provider_forbidden", "notification_delivery_failed", "secret_scan_failed"],
            "rawTracebacksExcluded": True,
            "rawResponseBodiesExcluded": True,
        },
        "localGeneration": {
            "externalServicesCalled": False,
            "networkCallsEnabled": False,
            "productionSecretsRead": False,
            "productionDataPathsRead": False,
            "runtimeBehaviorChanged": False,
            "stableJsonOutput": True,
        },
    }


def test_incident_response_evidence_accepts_sanitized_local_pack(tmp_path: Path) -> None:
    path = tmp_path / "incident-evidence.json"
    path.write_text(json.dumps(_accepted_evidence()), encoding="utf-8")

    result = _run_helper("--evidence", str(path))

    assert result.returncode == 0
    evidence = _output(result)
    assert evidence["schemaVersion"] == "wolfystock_incident_response_evidence_v1"
    assert evidence["finalStatus"] == "EVIDENCE-READY"
    assert evidence["releaseApproved"] is False
    assert evidence["sanitization"] == {
        "externalServicesCalled": False,
        "networkCallsEnabled": False,
        "productionDataPathsRead": False,
        "productionSecretsRead": False,
        "rawPayloadsIncluded": False,
        "runtimeBehaviorChanged": False,
        "secretValuesIncluded": False,
    }
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["admin_critical_actions_emit_sanitized_audit_evidence"]["status"] == "pass"
    assert checks["cleanup_and_retention_are_preview_first"]["status"] == "pass"
    assert checks["failure_paths_emit_actionable_sanitized_evidence"]["status"] == "pass"
    assert checks["local_evidence_generation_is_safe"]["status"] == "pass"


def test_incident_response_evidence_rejects_secret_values_without_echoing_them(tmp_path: Path) -> None:
    secret_value = "raw-token-value-should-not-print"
    payload = _accepted_evidence()
    payload["failureEvidence"]["providerError"] = f"provider failed token={secret_value}"
    path = tmp_path / "unsafe-incident-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper("--evidence", str(path))

    assert result.returncode == 1
    assert secret_value not in result.stdout
    assert secret_value not in result.stderr
    evidence = _output(result)
    assert evidence["finalStatus"] == "NO-GO"
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["incident_pack_contains_no_secret_values"]["status"] == "fail"
    assert checks["incident_pack_contains_no_secret_values"]["evidence"]["unsafeFindingCount"] == 1


def test_incident_response_evidence_missing_admin_family_is_no_go(tmp_path: Path) -> None:
    payload = _accepted_evidence()
    payload["adminAuditEvidence"]["events"] = [
        event for event in payload["adminAuditEvidence"]["events"] if event["family"] != "admin_quota"
    ]
    path = tmp_path / "missing-quota-family.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper("--evidence", str(path))

    assert result.returncode == 1
    checks = {check["id"]: check for check in _output(result)["checks"]}
    assert checks["admin_critical_actions_emit_sanitized_audit_evidence"]["status"] == "fail"
    assert checks["admin_critical_actions_emit_sanitized_audit_evidence"]["evidence"]["missingFamilies"] == ["admin_quota"]


def test_incident_response_evidence_default_mode_is_safe_no_go() -> None:
    result = _run_helper("--allow-no-go")

    assert result.returncode == 0
    evidence = _output(result)
    assert evidence["mode"] == "synthetic_empty"
    assert evidence["finalStatus"] == "NO-GO"
    assert evidence["sanitization"]["externalServicesCalled"] is False
    assert evidence["sanitization"]["productionSecretsRead"] is False
