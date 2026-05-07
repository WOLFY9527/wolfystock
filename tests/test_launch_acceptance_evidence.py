from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "launch_acceptance_evidence.py"
ACCEPTED_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "release" / "launch_acceptance_evidence.accepted.json"
MISSING_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "release" / "launch_acceptance_evidence.missing.json"
EXPECTED_CATEGORY_IDS = {
    "mfa_pilot_acceptance",
    "rbac_fallback_disable_switch",
    "provider_credential_staging_dry_run",
    "provider_staging_probe_artifact",
    "provider_live_probe_opt_in_timeout",
    "provider_circuit_controlled_enforcement",
    "quota_pilot_acceptance",
    "budget_alert_dry_run_acceptance",
    "real_isolated_postgresql_restore_pitr",
    "staging_ingress_smoke",
    "public_api_frontend_no_secret_safety",
    "supply_chain_dependency_build_artifact_safety",
    "incident_response_audit_evidence",
    "ws2_sse_topology_polling_fallback",
    "admin_log_retention_capacity_rehearsal",
    "portfolio_backtest_export_browser_proof",
    "notifications_delivery_rehearsal",
    "user_data_privacy_export_deletion_rehearsal",
    "market_data_freshness_fallback_evidence",
    "ai_report_guest_preview_safety",
    "options_derivatives_safety",
    "api_abuse_request_safety",
    "final_clean_full_ci_gate",
}


def _run_checker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _json(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def test_launch_acceptance_evidence_missing_categories_remain_no_go() -> None:
    result = _run_checker("--evidence", str(MISSING_FIXTURE))

    assert result.returncode == 1
    evidence = _json(result)
    assert evidence["schemaVersion"] == "wolfystock_launch_acceptance_evidence_summary_v1"
    assert evidence["finalStatus"] == "NO-GO"
    assert evidence["releaseApproved"] is False
    assert evidence["sanitization"] == {
        "externalServicesCalled": False,
        "networkCallsEnabled": False,
        "realEnvFileRead": False,
        "secretValuesRead": False,
        "secretValuesIncluded": False,
        "rawPayloadsIncluded": False,
        "responseBodiesIncluded": False,
        "productionDataPathsRead": False,
        "runtimeDefaultsChanged": False,
    }
    assert evidence["summary"]["accepted"] == 0
    assert evidence["summary"]["blocking"] == 23
    blocker_ids = {item["id"] for item in evidence["hardBlockers"]}
    assert EXPECTED_CATEGORY_IDS == blocker_ids


def test_launch_acceptance_evidence_allow_no_go_returns_zero_for_review_attachment() -> None:
    result = _run_checker("--evidence", str(MISSING_FIXTURE), "--allow-no-go")

    assert result.returncode == 0
    assert _json(result)["finalStatus"] == "NO-GO"


def test_launch_acceptance_evidence_all_accepted_is_go_review_required_not_approved() -> None:
    result = _run_checker("--evidence", str(ACCEPTED_FIXTURE))

    assert result.returncode == 0
    evidence = _json(result)
    assert evidence["finalStatus"] == "GO-REVIEW-REQUIRED"
    assert evidence["releaseApproved"] is False
    assert evidence["statusReason"] == "All hard blockers have accepted sanitized evidence; release approval remains manual."
    assert evidence["summary"]["accepted"] == 23
    assert evidence["summary"]["blocking"] == 0
    assert evidence["hardBlockers"] == []
    categories = {item["id"]: item for item in evidence["categories"]}
    assert EXPECTED_CATEGORY_IDS == set(categories)
    assert categories["mfa_pilot_acceptance"]["requiredChecks"] == [
        "adminPilotPassed",
        "adminOnlyScopeRecorded",
        "unsupportedGlobalRolloutNoGo",
        "recoveryPathTested",
        "breakGlassDisabledByDefault",
        "rollbackPlanRecorded",
        "auditEvidenceSanitized",
        "secretEvidenceRedacted",
    ]
    assert categories["rbac_fallback_disable_switch"]["requiredChecks"] == [
        "disableSwitchExplicit",
        "routeInventoryComplete",
        "coarseFallbackDisabledOrExceptionAccepted",
        "explicitCapabilityPayloadsPassWithoutFallback",
        "legacyMissingCapabilityUsersFailClosed",
        "rollbackPlanRecorded",
        "auditEvidenceSanitized",
        "runtimeDefaultUnchanged",
    ]
    assert categories["provider_credential_staging_dry_run"]["requiredChecks"] == [
        "stagingDryRunPassed",
        "credentialPresenceOnly",
        "noLiveCallsByChecker",
        "entitlementMatrixAttached",
    ]
    assert categories["provider_staging_probe_artifact"]["requiredChecks"] == [
        "stagingProbeArtifactAttached",
        "credentialValuesRedacted",
        "entitlementAndFreshnessLabelsRecorded",
        "operatorCaptureMetadataRecorded",
        "noLiveCallsByChecker",
    ]
    assert categories["provider_live_probe_opt_in_timeout"]["requiredChecks"] == [
        "namedStagingProviderRecorded",
        "liveProbeOptInRecorded",
        "liveProbeTimeoutBounded",
        "probeResultSanitized",
        "noLiveCallsByChecker",
    ]
    assert categories["provider_circuit_controlled_enforcement"]["status"] == "accepted"
    assert categories["provider_circuit_controlled_enforcement"]["requiredChecks"] == [
        "controlledEnforcementPilotPassed",
        "boundedRouteRecorded",
        "rollbackSwitchRecorded",
        "degradedEvidenceSanitized",
    ]
    assert categories["quota_pilot_acceptance"]["requiredChecks"] == [
        "pilotPassed",
        "explicitOwnerAllowlistRecorded",
        "outOfScopeUsersAdvisoryOnly",
        "invoiceReconciliationAdvisoryOnly",
        "invoiceReconciliationNotEnforcementInput",
        "globalEnforcementDisabledByDefault",
        "rollbackSwitchRecorded",
        "statusLabelsRecorded",
    ]
    assert categories["budget_alert_dry_run_acceptance"]["requiredChecks"] == [
        "pilotBlockEmitsSanitizedBudgetAlertIntent",
        "budgetAlertEvidenceRedacted",
        "realOutboundDeliveryDisabledByDefault",
        "noLiveLlmProviderOrInvoiceCalls",
        "alertStatusLabelsRecorded",
    ]
    assert categories["supply_chain_dependency_build_artifact_safety"]["requiredChecks"] == [
        "dependencyManifestsInspected",
        "manifestsSanitized",
        "buildArtifactsSanitized",
        "frontendBuildWarningsVisible",
        "noDependencyOrLockfileChanges",
        "missingEvidenceNoGoVerified",
    ]
    assert categories["incident_response_audit_evidence"]["requiredChecks"] == [
        "incidentPackAttached",
        "adminCriticalActionsAudited",
        "previewFirstCleanupEvidence",
        "providerNotificationReleaseFailuresRecorded",
        "localNoNetworkGeneration",
        "auditEvidenceSanitized",
        "secretEvidenceRedacted",
    ]
    assert categories["ws2_sse_topology_polling_fallback"]["requiredChecks"] == [
        "processLocalSseLimitationRecorded",
        "durablePollingFallbackVerified",
        "apiABTopologyEvidenceAttached",
        "ownerIsolationEvidenceRecorded",
        "runtimeCutoverNotPerformed",
    ]
    assert categories["admin_log_retention_capacity_rehearsal"]["requiredChecks"] == [
        "retentionPolicyRecorded",
        "previewFirstCleanupVerified",
        "minimumRetentionGuardVerified",
        "storagePressureRehearsalPassed",
        "cleanupAuditSanitized",
        "runtimeDefaultUnchanged",
    ]
    assert categories["portfolio_backtest_export_browser_proof"]["requiredChecks"] == [
        "exportEvidenceAttached",
        "browserProofAttached",
        "noAdviceAndOrderVerbsAbsent",
        "ownerIsolationEvidenceRecorded",
        "brokerCredentialEvidenceRedacted",
        "runtimeMutationNotPerformed",
    ]
    assert categories["notifications_delivery_rehearsal"]["requiredChecks"] == [
        "deliveryRehearsalPassed",
        "routeChannelMappingRecorded",
        "failurePathAudited",
        "notificationSecretsRedacted",
        "realOutboundDisabledOrAccepted",
    ]
    assert categories["user_data_privacy_export_deletion_rehearsal"]["requiredChecks"] == [
        "privacyExportProjectionSanitized",
        "deletionPreviewRehearsed",
        "ownerIsolationEvidenceRecorded",
        "privacyAuditEvidenceSanitized",
        "rawUserDataNotExposed",
    ]
    assert categories["market_data_freshness_fallback_evidence"]["requiredChecks"] == [
        "providerAndAsOfLabelsRecorded",
        "staleFallbackDisclosureVerified",
        "confidenceCapBehaviorVerified",
        "rawProviderPayloadsRedacted",
        "runtimeDefaultUnchanged",
    ]
    assert categories["ai_report_guest_preview_safety"]["requiredChecks"] == [
        "guestPreviewSafetyVerified",
        "rawPromptAndLlmResponsesRedacted",
        "noAutoAnalysisSideEffects",
        "guestIsolationEvidenceRecorded",
        "noAdviceLabelsVerified",
    ]
    assert categories["options_derivatives_safety"]["requiredChecks"] == [
        "readOnlyNoOrderPostureVerified",
        "brokerAndPortfolioMutationAbsent",
        "fixtureDelayedFallbackCapsVerified",
        "guaranteedReturnWordingAbsent",
        "providerEvidenceSanitized",
    ]
    assert categories["api_abuse_request_safety"]["requiredChecks"] == [
        "abuseRehearsalPassed",
        "invalidRequestHandlingVerified",
        "oversizedPayloadSafetyVerified",
        "denialAuditEvidenceSanitized",
        "debugTracebackAndRequestBodiesRedacted",
        "runtimeDefaultUnchanged",
    ]


def test_launch_acceptance_evidence_keeps_provider_circuit_required_when_missing(tmp_path: Path) -> None:
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["categories"].pop("provider_circuit_controlled_enforcement")
    evidence_path = tmp_path / "missing-provider-circuit.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    evidence = _json(result)
    assert evidence["finalStatus"] == "NO-GO"
    assert evidence["summary"]["blocking"] == 1
    assert evidence["hardBlockers"] == [
        {
            "id": "provider_circuit_controlled_enforcement",
            "status": "blocking",
            "requiredEvidence": "controlled provider-circuit enforcement pilot, bounded route, rollback switch, and sanitized degraded-state evidence",
        }
    ]


def test_launch_acceptance_evidence_rejects_secret_like_values_without_leaking(tmp_path: Path) -> None:
    secret = "sk-" + ("A" * 40)
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["categories"]["provider_credential_staging_dry_run"]["evidenceRef"] = secret
    evidence_path = tmp_path / "unsafe-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert secret not in combined_output
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "provider_credential_staging_dry_run")
    assert category["status"] == "blocking"
    assert category["reasonCodes"] == ["sensitive_value_present"]


def test_launch_acceptance_evidence_rejects_mfa_secret_fields_without_leaking(tmp_path: Path) -> None:
    recovery_code = "RECOVERY-CODE-1234"
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["categories"]["mfa_pilot_acceptance"]["operatorArtifact"] = {
        "totp_secret": "totp-secret",
        "mfa_recovery_code": recovery_code,
        "session_id": "raw-session-id",
    }
    evidence_path = tmp_path / "unsafe-mfa-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert recovery_code not in combined_output
    assert "totp-secret" not in combined_output
    assert "raw-session-id" not in combined_output
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "mfa_pilot_acceptance")
    assert category["status"] == "blocking"
    assert category["reasonCodes"] == ["sensitive_value_present"]


def test_launch_acceptance_evidence_rejects_public_matrix_secret_aliases_without_leaking(tmp_path: Path) -> None:
    api_key = "api_key=launch-secret-123456"
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["categories"]["incident_response_audit_evidence"]["operatorArtifact"] = {
        "API key": api_key,
        "rawResponseBody": "{\"session\":\"raw-session-id\"}",
        "provider credential": "credential-value",
    }
    evidence_path = tmp_path / "unsafe-public-matrix-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert api_key not in combined_output
    assert "raw-session-id" not in combined_output
    assert "credential-value" not in combined_output
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "incident_response_audit_evidence")
    assert category["status"] == "blocking"
    assert category["reasonCodes"] == ["sensitive_value_present"]


def test_launch_acceptance_evidence_rejects_traceback_debug_markers_without_leaking(tmp_path: Path) -> None:
    request_body = "debug_payload=raw-body request_body=raw-request"
    traceback_marker = "Traceback (most recent call last):"
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["categories"]["api_abuse_request_safety"]["operatorArtifact"] = {
        "traceback": traceback_marker,
        "debugPayload": request_body,
    }
    evidence_path = tmp_path / "unsafe-traceback-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert traceback_marker not in combined_output
    assert "raw-body" not in combined_output
    assert "raw-request" not in combined_output
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "api_abuse_request_safety")
    assert category["status"] == "blocking"
    assert category["reasonCodes"] == ["sensitive_value_present"]


def test_launch_acceptance_evidence_requires_provider_live_probe_contract_checks(tmp_path: Path) -> None:
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    checks = payload["categories"]["provider_live_probe_opt_in_timeout"]["checks"]
    checks.pop("liveProbeOptInRecorded")
    checks.pop("liveProbeTimeoutBounded")
    evidence_path = tmp_path / "missing-provider-live-probe-contract.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "provider_live_probe_opt_in_timeout")
    assert category["status"] == "blocking"
    assert category["missingChecks"] == ["liveProbeOptInRecorded", "liveProbeTimeoutBounded"]
    assert category["reasonCodes"] == ["missing_required_checks"]


def test_launch_acceptance_evidence_requires_quota_pilot_checks(tmp_path: Path) -> None:
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    checks = payload["categories"]["quota_pilot_acceptance"]["checks"]
    checks.pop("explicitOwnerAllowlistRecorded", None)
    evidence_path = tmp_path / "missing-quota-pilot-alert-safety-checks.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "quota_pilot_acceptance")
    assert category["status"] == "blocking"
    assert category["missingChecks"] == ["explicitOwnerAllowlistRecorded"]
    assert category["reasonCodes"] == ["missing_required_checks"]


def test_launch_acceptance_evidence_requires_budget_alert_dry_run_checks(tmp_path: Path) -> None:
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    checks = payload["categories"]["budget_alert_dry_run_acceptance"]["checks"]
    checks.pop("pilotBlockEmitsSanitizedBudgetAlertIntent", None)
    checks.pop("realOutboundDeliveryDisabledByDefault", None)
    checks.pop("noLiveLlmProviderOrInvoiceCalls", None)
    evidence_path = tmp_path / "missing-budget-alert-dry-run-checks.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "budget_alert_dry_run_acceptance")
    assert category["status"] == "blocking"
    assert category["missingChecks"] == [
        "pilotBlockEmitsSanitizedBudgetAlertIntent",
        "realOutboundDeliveryDisabledByDefault",
        "noLiveLlmProviderOrInvoiceCalls",
    ]
    assert category["reasonCodes"] == ["missing_required_checks"]


def test_launch_acceptance_evidence_rejects_build_artifact_secret_patterns_without_leaking(tmp_path: Path) -> None:
    secret = "postgresql://launch_user:secret-pass@example.test:5432/wolfy"
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["categories"]["supply_chain_dependency_build_artifact_safety"]["artifactEvidence"] = {
        "file": "dist/assets/app.js",
        "dsn": secret,
    }
    evidence_path = tmp_path / "unsafe-artifact-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert secret not in combined_output
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "supply_chain_dependency_build_artifact_safety")
    assert category["status"] == "blocking"
    assert category["reasonCodes"] == ["sensitive_value_present"]


def test_launch_acceptance_evidence_requires_supply_chain_manifest_and_artifact_checks(tmp_path: Path) -> None:
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    checks = payload["categories"]["supply_chain_dependency_build_artifact_safety"]["checks"]
    checks.pop("dependencyManifestsInspected")
    checks.pop("buildArtifactsSanitized")
    evidence_path = tmp_path / "missing-supply-chain-checks.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "supply_chain_dependency_build_artifact_safety")
    assert category["status"] == "blocking"
    assert category["missingChecks"] == ["dependencyManifestsInspected", "buildArtifactsSanitized"]
    assert category["reasonCodes"] == ["missing_required_checks"]
