from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "security_operator_acceptance_check.py"


def _run_helper(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--artifact", str(path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _json(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def _accepted_artifact() -> dict:
    base_section = {
        "sanitizedOperator": "staging-operator-a",
        "timestamp": "2026-05-08T10:00:00Z",
        "environment": "staging",
        "outcome": "accepted",
        "sampledControls": ["control-review", "redaction-check"],
        "evidenceRedactionVersion": "operator-redaction-v1",
    }
    return {
        "schemaVersion": "wolfystock_security_operator_acceptance_artifact_v1",
        "mfaAdminPilot": {
            **base_section,
            "testAccountRoleLabels": ["admin_mfa_pilot", "support_admin"],
            "runtimeBehaviorChanged": False,
        },
        "rbacFallbackDisable": {
            **base_section,
            "fallbackDisabled": True,
            "legacyAdminDenied": True,
            "explicitCapabilitiesAccepted": True,
            "runtimeBehaviorChanged": False,
        },
        "breakGlassRecovery": {
            **base_section,
            "breakGlassDefaultOff": True,
            "recoveryFallbackSampled": True,
            "runtimeBehaviorChanged": False,
        },
        "adminRouteSampling": {
            **base_section,
            "sampledRoutes": ["/zh/admin/cost-observability", "/zh/settings/system"],
            "runtimeBehaviorChanged": False,
        },
    }


def test_security_operator_acceptance_accepts_sanitized_artifact(tmp_path: Path) -> None:
    artifact_path = tmp_path / "operator-acceptance.json"
    artifact_path.write_text(json.dumps(_accepted_artifact()), encoding="utf-8")

    result = _run_helper(artifact_path)

    assert result.returncode == 0
    evidence = _json(result)
    assert evidence["schemaVersion"] == "wolfystock_security_operator_acceptance_check_v1"
    assert evidence["finalStatus"] == "EVIDENCE-READY"
    assert evidence["releaseApproved"] is False
    assert evidence["launchApproved"] is False
    assert evidence["runtimeBehaviorChanged"] is False
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["required_sections_are_complete"]["status"] == "pass"
    assert checks["artifact_contains_no_sensitive_or_raw_payload_values"]["status"] == "pass"
    assert checks["mfa_admin_pilot_uses_sanitized_role_labels"]["status"] == "pass"
    assert checks["rbac_fallback_disable_is_explicit"]["status"] == "pass"
    assert checks["launch_approval_claims_absent"]["status"] == "pass"


def test_security_operator_acceptance_rejects_sensitive_values_without_echoing(tmp_path: Path) -> None:
    sensitive_value = "raw-value-should-not-print"
    payload = _accepted_artifact()
    payload["mfaAdminPilot"]["totpSecret"] = sensitive_value
    artifact_path = tmp_path / "unsafe-operator-acceptance.json"
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper(artifact_path)

    assert result.returncode == 1
    assert sensitive_value not in result.stdout
    assert sensitive_value not in result.stderr
    checks = {check["id"]: check for check in _json(result)["checks"]}
    assert checks["artifact_contains_no_sensitive_or_raw_payload_values"]["status"] == "fail"
    assert checks["artifact_contains_no_sensitive_or_raw_payload_values"]["evidence"]["unsafeFindingCount"] == 1


def test_security_operator_acceptance_rejects_raw_payloads_debug_and_go_claims(tmp_path: Path) -> None:
    unsafe_cases = [
        ("raw-request", ("adminRouteSampling", "rawRequestBody", "{\"cookie\":\"redacted\"}"), "artifact_contains_no_sensitive_or_raw_payload_values"),
        ("stack-trace", ("breakGlassRecovery", "stackTrace", "Traceback (most recent call last)"), "artifact_contains_no_sensitive_or_raw_payload_values"),
        ("launch-go", ("mfaAdminPilot", "launchDecision", "GO"), "launch_approval_claims_absent"),
    ]
    for name, (section, key, value), failed_check in unsafe_cases:
        payload = _accepted_artifact()
        payload[section][key] = value
        artifact_path = tmp_path / f"unsafe-{name}.json"
        artifact_path.write_text(json.dumps(payload), encoding="utf-8")

        result = _run_helper(artifact_path)

        assert result.returncode == 1, name
        checks = {check["id"]: check for check in _json(result)["checks"]}
        assert checks[failed_check]["status"] == "fail"


def test_security_operator_acceptance_requires_rbac_fallback_disabled_true(tmp_path: Path) -> None:
    payload = _accepted_artifact()
    payload["rbacFallbackDisable"]["fallbackDisabled"] = False
    artifact_path = tmp_path / "rbac-fallback-not-disabled.json"
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper(artifact_path)

    assert result.returncode == 1
    checks = {check["id"]: check for check in _json(result)["checks"]}
    assert checks["rbac_fallback_disable_is_explicit"]["status"] == "fail"
    assert checks["rbac_fallback_disable_is_explicit"]["evidence"]["fallbackDisabled"] is False


def test_security_operator_acceptance_requires_sanitized_role_labels_only(tmp_path: Path) -> None:
    unsafe_cases = [
        ("missing-labels", {"testAccountRoleLabels": []}),
        ("raw-account", {"testAccounts": [{"username": "admin@example.invalid", "role": "admin"}]}),
        ("unsafe-label", {"testAccountRoleLabels": ["admin@example.invalid"]}),
    ]
    for name, patch in unsafe_cases:
        payload = _accepted_artifact()
        payload["mfaAdminPilot"].update(patch)
        artifact_path = tmp_path / f"unsafe-mfa-{name}.json"
        artifact_path.write_text(json.dumps(payload), encoding="utf-8")

        result = _run_helper(artifact_path)

        assert result.returncode == 1, name
        checks = {check["id"]: check for check in _json(result)["checks"]}
        assert checks["mfa_admin_pilot_uses_sanitized_role_labels"]["status"] == "fail"
