from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "rollback_rehearsal_evidence.py"
ACCEPTED_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "release" / "rollback_rehearsal_evidence.accepted.json"


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
    return json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))


def test_rollback_rehearsal_evidence_accepts_sanitized_local_pack() -> None:
    result = _run_helper("--evidence", str(ACCEPTED_FIXTURE))

    assert result.returncode == 0
    evidence = _output(result)
    assert evidence["schemaVersion"] == "wolfystock_rollback_rehearsal_evidence_v1"
    assert evidence["finalStatus"] == "EVIDENCE-READY"
    assert evidence["releaseApproved"] is False
    assert evidence["launchApproved"] is False
    assert evidence["sanitization"] == {
        "databaseActionsRun": False,
        "deploymentCommandsRun": False,
        "externalServicesCalled": False,
        "gitHistoryChanged": False,
        "networkCallsEnabled": False,
        "productionDataPathsRead": False,
        "productionSecretsRead": False,
        "rawPayloadsIncluded": False,
        "runtimeBehaviorChanged": False,
        "secretValuesIncluded": False,
    }
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["rollback_rehearsal_metadata_is_complete"]["status"] == "pass"
    assert checks["rollback_plan_is_dry_run_operator_driven"]["status"] == "pass"
    assert checks["verification_steps_are_offline_and_bounded"]["status"] == "pass"
    assert checks["rollback_evidence_contains_no_sensitive_values"]["status"] == "pass"
    assert checks["local_rehearsal_generation_is_non_destructive"]["status"] == "pass"


def test_rollback_rehearsal_evidence_default_mode_is_safe_no_go() -> None:
    result = _run_helper("--allow-no-go")

    assert result.returncode == 0
    evidence = _output(result)
    assert evidence["mode"] == "synthetic_empty"
    assert evidence["finalStatus"] == "NO-GO"
    assert evidence["releaseApproved"] is False
    assert evidence["launchApproved"] is False
    assert evidence["sanitization"]["deploymentCommandsRun"] is False
    assert evidence["sanitization"]["databaseActionsRun"] is False
    assert evidence["sanitization"]["gitHistoryChanged"] is False


def test_rollback_rehearsal_evidence_rejects_sensitive_values_without_echoing(tmp_path: Path) -> None:
    sensitive_value = "raw-value-should-not-print"
    payload = _accepted_evidence()
    payload["rollbackPlan"]["operatorNotes"] = f"provider failed with token={sensitive_value}"
    path = tmp_path / "unsafe-rollback-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper("--evidence", str(path))

    assert result.returncode == 1
    assert sensitive_value not in result.stdout
    assert sensitive_value not in result.stderr
    evidence = _output(result)
    assert evidence["finalStatus"] == "NO-GO"
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["rollback_evidence_contains_no_sensitive_values"]["status"] == "fail"
    assert checks["rollback_evidence_contains_no_sensitive_values"]["evidence"]["unsafeFindingCount"] == 1
    assert checks["rollback_evidence_contains_no_sensitive_values"]["evidence"]["findingValuesIncluded"] is False


def test_rollback_rehearsal_evidence_rejects_sensitive_evidence_classes_without_echoing(tmp_path: Path) -> None:
    sensitive_value = "raw-value-should-not-print"
    private_key_header = "-----BEGIN " + "PRIVATE KEY-----"
    unsafe_cases = [
        ("password", {"operator": {"password": sensitive_value}}),
        ("api-key", {"rollbackPlan": {"apiKey": sensitive_value}}),
        ("session", {"rollbackPlan": {"sessionId": sensitive_value}}),
        ("cookie", {"rollbackPlan": {"cookie": sensitive_value}}),
        ("dsn", {"rollbackPlan": {"databaseDsn": f"postgresql://user:{sensitive_value}@example.invalid/db"}}),
        ("private-key", {"rollbackPlan": {"privateKey": f"{private_key_header}\n{sensitive_value}"}}),
        ("provider-credential", {"rollbackPlan": {"providerCredential": sensitive_value}}),
        ("raw-response", {"rollbackPlan": {"rawResponse": sensitive_value}}),
        ("raw-log-body", {"rollbackPlan": {"rawLogBody": sensitive_value}}),
    ]
    for name, patch in unsafe_cases:
        payload = _accepted_evidence()
        for top_key, nested in patch.items():
            payload[top_key].update(nested)
        path = tmp_path / f"unsafe-{name}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")

        result = _run_helper("--evidence", str(path))

        assert result.returncode == 1, name
        assert sensitive_value not in result.stdout
        assert sensitive_value not in result.stderr
        checks = {check["id"]: check for check in _output(result)["checks"]}
        assert checks["rollback_evidence_contains_no_sensitive_values"]["status"] == "fail"
        assert checks["rollback_evidence_contains_no_sensitive_values"]["evidence"]["unsafeFindingCount"] >= 1


def test_rollback_rehearsal_evidence_rejects_credential_bearing_urls_without_echoing(tmp_path: Path) -> None:
    sensitive_value = "raw-value-should-not-print"
    payload = _accepted_evidence()
    payload["verificationSteps"].append(
        {
            "type": "secret_scan",
            "command": f"curl https://example.invalid/health?token={sensitive_value}",
            "expectedResult": "unsafe URL must fail evidence validation",
        }
    )
    path = tmp_path / "unsafe-url-rollback-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper("--evidence", str(path))

    assert result.returncode == 1
    assert sensitive_value not in result.stdout
    assert sensitive_value not in result.stderr
    checks = {check["id"]: check for check in _output(result)["checks"]}
    assert checks["rollback_evidence_contains_no_sensitive_values"]["status"] == "fail"


def test_rollback_rehearsal_evidence_rejects_destructive_default_commands(tmp_path: Path) -> None:
    payload = _accepted_evidence()
    payload["rollbackPlan"]["defaultCommands"].append("git reset --hard HEAD~1")
    path = tmp_path / "destructive-rollback-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper("--evidence", str(path))

    assert result.returncode == 1
    checks = {check["id"]: check for check in _output(result)["checks"]}
    assert checks["rollback_plan_is_dry_run_operator_driven"]["status"] == "fail"
    assert checks["rollback_plan_is_dry_run_operator_driven"]["evidence"]["forbiddenDefaultCommandCount"] == 1


def test_rollback_rehearsal_evidence_rejects_launch_go_claim(tmp_path: Path) -> None:
    payload = _accepted_evidence()
    payload["gateStatus"]["launchGo"] = True
    path = tmp_path / "launch-go-rollback-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper("--evidence", str(path))

    assert result.returncode == 1
    checks = {check["id"]: check for check in _output(result)["checks"]}
    assert checks["rollback_rehearsal_metadata_is_complete"]["status"] == "fail"
    assert "launch_go_not_allowed" in checks["rollback_rehearsal_metadata_is_complete"]["evidence"]["issues"]
