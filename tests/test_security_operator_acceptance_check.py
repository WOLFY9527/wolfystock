from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "security_operator_acceptance_check.py"


def _run_helper(path: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--artifact", str(path), *extra_args],
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
            "disableSwitchExplicit": True,
            "fallbackDisabled": True,
            "routeInventoryComplete": True,
            "coarseFallbackDisabledOrExceptionAccepted": True,
            "backendAdminRoutesExplicitCapabilities": True,
            "frontendAdminGatesCapabilityBased": True,
            "frontendAdminMissingCapabilitiesFailClosed": True,
            "legacyAdminDenied": True,
            "explicitCapabilitiesAccepted": True,
            "explicitCapabilityPayloadsPassWithoutFallback": True,
            "legacyMissingCapabilityUsersFailClosed": True,
            "rollbackPlanRecorded": True,
            "auditEvidenceSanitized": True,
            "runtimeDefaultUnchanged": True,
            "runtimeBehaviorChanged": False,
        },
        "breakGlassRecovery": {
            **base_section,
            "generationVerified": True,
            "displayOnceVerified": True,
            "plaintextStoredAfterDisplay": False,
            "hashStorageVerified": True,
            "singleUseConsumeVerified": True,
            "replayDeniedVerified": True,
            "rotationRevocationVerified": True,
            "breakGlassDefaultOff": True,
            "recoveryFallbackSampled": True,
            "rollbackPlanRecorded": True,
            "auditEvidenceSanitized": True,
            "runtimeDefaultUnchanged": True,
            "runtimeBehaviorChanged": False,
        },
        "adminRouteSampling": {
            **base_section,
            "sampledRoutes": ["/zh/admin/cost-observability", "/zh/settings/system"],
            "runtimeBehaviorChanged": False,
        },
    }


def _observe_artifact() -> dict:
    base_section = {
        "sanitizedOperator": "staging-operator-a",
        "timestamp": "2026-06-12T10:00:00Z",
        "environment": "staging",
        "outcome": "accepted",
        "sampledControls": ["route-inventory", "audit-redaction"],
        "evidenceRedactionVersion": "operator-redaction-v1",
    }
    return {
        "schemaVersion": "wolfystock_security_operator_acceptance_artifact_v1",
        "rbacFallbackObserve": {
            **base_section,
            "coarseAdminCompatibilityFallbackPresent": True,
            "fallbackObserveModeEnabled": True,
            "fallbackOffAccepted": False,
            "fallbackRemoved": False,
            "productionLeastPrivilegeAccepted": False,
            "publicLaunchApproved": False,
            "failClosedProductionEnforcementEnabled": False,
            "routeInventory": {
                "routeInventoryComplete": True,
                "inventoryCurrent": True,
                "adminRouteCount": 42,
                "unclassifiedAdminRouteCount": 0,
                "sourceArtifact": "tests/fixtures/auth/backend_route_capability_inventory.json",
                "requiredFieldsPresent": [
                    "endpoint",
                    "method",
                    "currentDependency",
                    "targetCapability",
                    "sensitivityTier",
                    "reasonRequirement",
                    "reauthRequirement",
                    "auditRequirement",
                ],
            },
            "explicitCapabilityPayloadProof": {
                "proofPresent": True,
                "sampleCount": 3,
                "allSampledPayloadsHaveExplicitCapabilities": True,
                "capabilityFields": ["capabilities", "adminCapabilities"],
            },
            "legacyMissingPayloadFailClosedObserveEvidence": {
                "legacyMissingCapabilityUsersFailClosed": True,
                "missingCapabilityPayloadsFailClosed": True,
                "denialResponsesSanitized": True,
                "observeOnlyNoRuntimeEnforcementChange": True,
            },
            "rollbackPosture": {
                "rollbackPlanRecorded": True,
                "fallbackStillEnabled": True,
                "runtimeDefaultUnchanged": True,
                "failClosedProductionEnforcementEnabled": False,
            },
            "sanitizedAuditExcerpts": [
                {
                    "routeFamily": "admin.system_config",
                    "requiredCapability": "ops:system_config:read",
                    "actorSafeHandle": "actor-hash-001",
                    "sourceSurface": "backend-route-sample",
                    "outcome": "fallback_only_grant_observed",
                    "rawValuesIncluded": False,
                }
            ],
            "runtimeBehaviorChanged": False,
        },
    }


def _set_observe_value(payload: dict, path: tuple[str, ...], value: object) -> None:
    current = payload["rbacFallbackObserve"]
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value


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
    assert checks["rbac_fallback_off_operator_pilot_evidence"]["status"] == "pass"
    assert checks["rbac_fallback_off_operator_pilot_evidence"]["evidence"] == {
        "missingFields": [],
        "disableSwitchExplicit": True,
        "routeInventoryComplete": True,
        "coarseFallbackDisabledOrExceptionAccepted": True,
        "backendAdminRoutesExplicitCapabilities": True,
        "frontendAdminGatesCapabilityBased": True,
        "frontendAdminMissingCapabilitiesFailClosed": True,
        "explicitCapabilityPayloadsPassWithoutFallback": True,
        "legacyMissingCapabilityUsersFailClosed": True,
        "rollbackPlanRecorded": True,
        "auditEvidenceSanitized": True,
        "runtimeDefaultUnchanged": True,
    }
    assert checks["mfa_recovery_code_acceptance_evidence"]["status"] == "pass"
    assert checks["mfa_recovery_code_acceptance_evidence"]["evidence"] == {
        "missingFields": [],
        "generationVerified": True,
        "displayOnceVerified": True,
        "plaintextStoredAfterDisplay": True,
        "hashStorageVerified": True,
        "singleUseConsumeVerified": True,
        "replayDeniedVerified": True,
        "rotationRevocationVerified": True,
        "breakGlassDefaultOff": True,
        "recoveryFallbackSampled": True,
        "rollbackPlanRecorded": True,
        "auditEvidenceSanitized": True,
        "runtimeDefaultUnchanged": True,
    }
    assert checks["launch_approval_claims_absent"]["status"] == "pass"


def test_security_operator_acceptance_accepts_rbac_r5_observe_artifact(tmp_path: Path) -> None:
    artifact_path = tmp_path / "rbac-r5-observe.json"
    artifact_path.write_text(json.dumps(_observe_artifact()), encoding="utf-8")

    result = _run_helper(artifact_path, "--profile", "rbac-r5-observe")

    assert result.returncode == 0
    evidence = _json(result)
    assert evidence["profile"] == "rbac-r5-observe"
    assert evidence["finalStatus"] == "OBSERVE-EVIDENCE-READY"
    assert evidence["fallbackOffAccepted"] is False
    assert evidence["fallbackRemoved"] is False
    assert evidence["productionLeastPrivilegeAccepted"] is False
    assert evidence["launchApproved"] is False
    assert evidence["runtimeBehaviorChanged"] is False
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["rbac_r5_observe_section_is_complete"]["status"] == "pass"
    assert checks["rbac_r5_observe_route_inventory_complete"]["status"] == "pass"
    assert checks["rbac_r5_observe_explicit_capability_payload_proof"]["status"] == "pass"
    assert checks["rbac_r5_observe_legacy_missing_payload_fail_closed"]["status"] == "pass"
    assert checks["rbac_r5_observe_rollback_posture_recorded"]["status"] == "pass"
    assert checks["rbac_r5_observe_audit_excerpts_sanitized"]["status"] == "pass"
    assert checks["rbac_r5_unsafe_acceptance_claims_absent"]["status"] == "pass"
    assert "rbac_fallback_disable_is_explicit" not in checks


def test_security_operator_acceptance_observe_rejects_unsafe_acceptance_claims(tmp_path: Path) -> None:
    unsafe_cases = [
        ("fallback-off", "fallbackOffAccepted", "fallback-off accepted"),
        ("fallback-removed", "fallbackRemoved", "fallback removed"),
        ("least-privilege", "productionLeastPrivilegeAccepted", "production least privilege accepted"),
        ("public-launch", "publicLaunchApproved", "public launch approved"),
    ]
    for name, key, text in unsafe_cases:
        payload = _observe_artifact()
        payload["rbacFallbackObserve"][key] = True
        payload["rbacFallbackObserve"]["operatorSummary"] = text
        artifact_path = tmp_path / f"unsafe-observe-claim-{name}.json"
        artifact_path.write_text(json.dumps(payload), encoding="utf-8")

        result = _run_helper(artifact_path, "--profile", "rbac-r5-observe")

        assert result.returncode == 1, name
        checks = {check["id"]: check for check in _json(result)["checks"]}
        assert checks["rbac_r5_unsafe_acceptance_claims_absent"]["status"] == "fail"


def test_security_operator_acceptance_observe_requires_core_evidence_groups(tmp_path: Path) -> None:
    unsafe_cases = [
        (
            "inventory-fields",
            ("routeInventory", "requiredFieldsPresent"),
            ["endpoint", "method", "targetCapability"],
            "rbac_r5_observe_route_inventory_complete",
        ),
        (
            "explicit-payload-proof",
            ("explicitCapabilityPayloadProof", "allSampledPayloadsHaveExplicitCapabilities"),
            False,
            "rbac_r5_observe_explicit_capability_payload_proof",
        ),
        (
            "missing-payload-fail-closed",
            ("legacyMissingPayloadFailClosedObserveEvidence", "missingCapabilityPayloadsFailClosed"),
            False,
            "rbac_r5_observe_legacy_missing_payload_fail_closed",
        ),
        (
            "rollback-posture",
            ("rollbackPosture", "rollbackPlanRecorded"),
            False,
            "rbac_r5_observe_rollback_posture_recorded",
        ),
        (
            "audit-excerpts",
            ("sanitizedAuditExcerpts",),
            [],
            "rbac_r5_observe_audit_excerpts_sanitized",
        ),
    ]
    for name, path, value, failed_check in unsafe_cases:
        payload = _observe_artifact()
        _set_observe_value(payload, path, value)
        artifact_path = tmp_path / f"unsafe-observe-{name}.json"
        artifact_path.write_text(json.dumps(payload), encoding="utf-8")

        result = _run_helper(artifact_path, "--profile", "rbac-r5-observe")

        assert result.returncode == 1, name
        checks = {check["id"]: check for check in _json(result)["checks"]}
        assert checks[failed_check]["status"] == "fail"


def test_security_operator_acceptance_observe_rejects_raw_audit_excerpts_without_echoing(tmp_path: Path) -> None:
    sensitive_value = "cookie=observe-raw-session-value-should-not-print"
    payload = _observe_artifact()
    payload["rbacFallbackObserve"]["sanitizedAuditExcerpts"][0]["rawRequestBody"] = sensitive_value
    artifact_path = tmp_path / "unsafe-observe-audit-excerpt.json"
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper(artifact_path, "--profile", "rbac-r5-observe")

    assert result.returncode == 1
    assert sensitive_value not in result.stdout
    assert sensitive_value not in result.stderr
    checks = {check["id"]: check for check in _json(result)["checks"]}
    assert checks["artifact_contains_no_sensitive_or_raw_payload_values"]["status"] == "fail"


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
        ("global-mfa", ("mfaAdminPilot", "notes", "global MFA approved for all production users"), "launch_approval_claims_absent"),
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


def test_security_operator_acceptance_requires_complete_recovery_code_evidence(tmp_path: Path) -> None:
    required_true_fields = (
        "generationVerified",
        "displayOnceVerified",
        "hashStorageVerified",
        "singleUseConsumeVerified",
        "replayDeniedVerified",
        "rotationRevocationVerified",
        "breakGlassDefaultOff",
        "recoveryFallbackSampled",
        "rollbackPlanRecorded",
        "auditEvidenceSanitized",
        "runtimeDefaultUnchanged",
    )

    for field in required_true_fields:
        payload = _accepted_artifact()
        payload["breakGlassRecovery"][field] = False
        artifact_path = tmp_path / f"recovery-code-missing-{field}.json"
        artifact_path.write_text(json.dumps(payload), encoding="utf-8")

        result = _run_helper(artifact_path)

        assert result.returncode == 1, field
        checks = {check["id"]: check for check in _json(result)["checks"]}
        check = checks["mfa_recovery_code_acceptance_evidence"]
        assert check["status"] == "fail"
        assert field in check["evidence"]["missingFields"]


def test_security_operator_acceptance_requires_no_recovery_plaintext_storage(tmp_path: Path) -> None:
    payload = _accepted_artifact()
    payload["breakGlassRecovery"]["plaintextStoredAfterDisplay"] = True
    artifact_path = tmp_path / "recovery-code-plaintext-storage.json"
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper(artifact_path)

    assert result.returncode == 1
    checks = {check["id"]: check for check in _json(result)["checks"]}
    check = checks["mfa_recovery_code_acceptance_evidence"]
    assert check["status"] == "fail"
    assert "plaintextStoredAfterDisplay" in check["evidence"]["missingFields"]


def test_security_operator_acceptance_rejects_raw_recovery_codes_without_echoing(tmp_path: Path) -> None:
    raw_code = "ABCD-EFGH-IJKL"
    payload = _accepted_artifact()
    payload["breakGlassRecovery"]["recoveryCodes"] = [raw_code]
    artifact_path = tmp_path / "raw-recovery-code.json"
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper(artifact_path)

    assert result.returncode == 1
    assert raw_code not in result.stdout
    assert raw_code not in result.stderr
    checks = {check["id"]: check for check in _json(result)["checks"]}
    assert checks["artifact_contains_no_sensitive_or_raw_payload_values"]["status"] == "fail"


def test_security_operator_acceptance_rejects_runtime_behavior_change_flags(tmp_path: Path) -> None:
    payload = _accepted_artifact()
    payload["breakGlassRecovery"]["authRuntimeChanged"] = True
    artifact_path = tmp_path / "runtime-changed.json"
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper(artifact_path)

    assert result.returncode == 1
    checks = {check["id"]: check for check in _json(result)["checks"]}
    assert checks["runtime_behavior_unchanged"]["status"] == "fail"


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


def test_security_operator_acceptance_requires_complete_rbac_fallback_off_pilot_evidence(tmp_path: Path) -> None:
    required_fields = (
        "disableSwitchExplicit",
        "routeInventoryComplete",
        "coarseFallbackDisabledOrExceptionAccepted",
        "backendAdminRoutesExplicitCapabilities",
        "frontendAdminGatesCapabilityBased",
        "frontendAdminMissingCapabilitiesFailClosed",
        "explicitCapabilityPayloadsPassWithoutFallback",
        "legacyMissingCapabilityUsersFailClosed",
        "rollbackPlanRecorded",
        "auditEvidenceSanitized",
        "runtimeDefaultUnchanged",
    )

    for field in required_fields:
        payload = _accepted_artifact()
        payload["rbacFallbackDisable"][field] = False
        artifact_path = tmp_path / f"rbac-fallback-off-missing-{field}.json"
        artifact_path.write_text(json.dumps(payload), encoding="utf-8")

        result = _run_helper(artifact_path)

        assert result.returncode == 1, field
        checks = {check["id"]: check for check in _json(result)["checks"]}
        check = checks["rbac_fallback_off_operator_pilot_evidence"]
        assert check["status"] == "fail"
        assert field in check["evidence"]["missingFields"]
        assert "raw-session-id" not in result.stdout
        assert "raw-password" not in result.stdout


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
