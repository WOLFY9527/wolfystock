from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from scripts.operator_evidence_template_pack import TEMPLATE_SPECS
from scripts.operator_evidence_template_pack import _build_templates

SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_bundle_check.py"
EXPECTED_TEMPLATE_FILENAMES = {spec.filename for spec in TEMPLATE_SPECS}
EXPECTED_TEMPLATE_CATEGORIES = {spec.category for spec in TEMPLATE_SPECS}


def _provider_artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "providerName": "tradier",
        "environment": "staging",
        "operator": "provider-ops",
        "observedAt": "2026-05-08T10:30:00Z",
        "probeMode": "manual_provider_probe",
        "networkCallsEnabled": True,
        "credentialPresence": "redacted",
        "circuitState": {"state": "closed", "summary": "No forced circuit override recorded."},
        "fallbackState": {"state": "unchanged", "summary": "Runtime fallback policy was observed only."},
        "outcome": "accepted",
        "evidenceRedactionVersion": "provider_operator_redaction_v1",
        "notes": "Sanitized operator artifact for later review.",
    }
    payload.update(overrides)
    return payload


def _provider_sla_artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifactVersion": "wolfystock_provider_sla_licensing_evidence_v1",
        "environment": "staging",
        "operator": "provider-ops",
        "observedAt": "2026-05-08T10:30:00Z",
        "providerFamily": "data-source-validation",
        "entitlementLicensingStatus": "needs-review",
        "credentialPresence": "redacted",
        "allowedUsageScope": "admin-probe-review",
        "stagingProbeResult": "not-run",
        "degradedFallbackPolicy": "unchanged",
        "runtimeEnforcement": {
            "claim": "not-claimed",
            "liveEnforcement": False,
            "wouldBlockCall": False,
        },
        "publicReadinessClaim": "not-claimed",
        "adminProbePilotEvidence": {
            "contractVersion": "provider_admin_probe_pilot_evidence_v1",
            "adminProbeOnly": True,
            "defaultOffPosture": True,
            "rollbackAvailable": True,
            "selectedBoundary": "admin-provider-probe",
            "apiRoute": "/api/admin/provider-circuits/diagnostics",
            "providerCategory": "data_source_validation",
            "routeFamily": "admin_provider_probe",
            "publicRuntimeProviderBlocking": False,
            "memberRuntimeProviderBlocking": False,
            "providerRuntimeEnforcement": False,
            "providerOrderFallbackCacheBehaviorChanged": False,
            "sanitizedFieldsOnly": True,
            "acceptedOperatorEvidencePresent": False,
            "publicLaunchReady": False,
            "remainingPublicLaunchNoGoItems": [
                "public_provider_circuit_enforcement_not_accepted",
                "target_environment_provider_sla_evidence_missing",
                "provider_entitlement_licensing_not_accepted",
            ],
        },
        "outcome": "accepted",
        "evidenceRedactionVersion": "provider-sla-licensing-redaction-v1",
        "notes": "Sanitized provider admin probe evidence for later review.",
    }
    payload.update(overrides)
    return payload


def _notification_rehearsal_artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schemaVersion": "wolfystock_notification_delivery_rehearsal_evidence_v1",
        "mode": "offline-sanitized-rehearsal",
        "environment": "staging",
        "operator": "notification-ops",
        "observedAt": "2026-05-08T10:30:00Z",
        "dryRunNoSendProof": {
            "dryRunOnly": True,
            "noOutboundSent": True,
            "deliveryClientPatchedOrDisabled": True,
            "providerCallsExecuted": False,
            "checkerNetworkCallsEnabled": False,
            "outcome": "accepted",
        },
        "channelMappingSummary": {
            "mappingComplete": True,
            "routes": [
                {
                    "routeLabel": "admin-notification-rehearsal",
                    "channelLabel": "ops-channel-alpha",
                    "ownerLabel": "owner-label-alpha",
                    "channelType": "email",
                    "mappingSourceLabel": "mapping-ref-alpha",
                }
            ],
        },
        "recipientChannelOwnershipEvidence": {
            "sanitizedLabelsOnly": True,
            "owners": [
                {
                    "ownerLabel": "owner-label-alpha",
                    "channelLabel": "ops-channel-alpha",
                    "ownershipEvidenceLabel": "ownership-proof-alpha",
                    "recipientLabel": "recipient-label-alpha",
                    "manualApprovalRequired": True,
                    "rawRecipientIdIncluded": False,
                }
            ],
        },
        "failurePathAuditSummary": {
            "failurePathsAudited": True,
            "cases": [
                {
                    "caseLabel": "delivery-timeout-synthetic",
                    "routeLabel": "admin-notification-rehearsal",
                    "sanitizedReasonCode": "synthetic_delivery_timeout",
                    "coreFlowContinues": True,
                    "rawNotificationBodyIncluded": False,
                    "providerPayloadIncluded": False,
                    "stackTraceIncluded": False,
                }
            ],
        },
        "outboundSafety": {
            "outboundDisabledByDefault": True,
            "externalProviderCallsByChecker": False,
            "manualApprovalRequiredForRealDelivery": True,
            "realDeliveryRehearsalApproved": False,
            "runtimeNotificationBehaviorChanged": False,
            "releaseApproved": False,
            "publicLaunchReady": False,
        },
        "outcome": "accepted",
        "evidenceRedactionVersion": "notification_delivery_rehearsal_redaction_v1",
        "notes": "Sanitized no-send notification rehearsal evidence.",
    }
    payload.update(overrides)
    return payload


def _restore_artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
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
            }
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
            "sampledQuerySummaries": ["query-summary:auth-count"],
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
            }
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
    payload.update(overrides)
    return payload


def _security_artifact() -> dict[str, object]:
    base_section: dict[str, object] = {
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


QUOTA_SECTIONS = (
    "quotaPilot",
    "budgetAlertDryRun",
    "ownerScopeSampling",
    "disabledPreferenceSuppression",
    "notificationNoOutboundProof",
)


def _quota_section(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "environment": "staging-sanitized",
        "operator": "cost-ops-operator",
        "observedAt": "2026-05-08T10:30:00Z",
        "sampledOwnerLabels": ["owner-alpha", "owner-beta"],
        "thresholdPolicyVersion": "quota-budget-thresholds-v1",
        "dryRunOnly": True,
        "outboundSent": False,
        "outcome": "accepted",
        "evidenceRedactionVersion": "quota_budget_operator_redaction_v1",
        "notes": "Sanitized dry-run operator evidence.",
    }
    payload.update(overrides)
    return payload


def _quota_artifact() -> dict[str, object]:
    return {
        "schemaVersion": "wolfystock_quota_operator_evidence_v1",
        "mode": "operator_sanitized",
        **{section_id: _quota_section() for section_id in QUOTA_SECTIONS},
    }


def _ingress_artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifactVersion": "wolfystock_staging_ingress_operator_evidence_v1",
        "environment": "staging",
        "operator": "staging-ingress-ops",
        "observedAt": "2026-05-08T10:30:00Z",
        "baseUrlLabel": "staging-ingress-primary",
        "networkCallsEnabled": True,
        "checkedRoutes": [
            {
                "routeLabel": "health-ready",
                "method": "GET",
                "pathPattern": "/api/health/ready",
                "statusClass": "2xx",
                "summary": "Public readiness route returned bounded health metadata.",
            }
        ],
        "authBoundaryResult": {
            "status": "accepted",
            "summary": "Protected routes failed closed for unauthenticated access.",
        },
        "securityHeaderSummary": {
            "status": "accepted",
            "summary": "Expected security header names were observed without header values.",
        },
        "csrfOrStateMutationSummary": {
            "status": "accepted",
            "summary": "No state-changing operation was attempted during evidence collection.",
        },
        "publicSurfaceSummary": {
            "status": "accepted",
            "summary": "Only bounded public health surfaces were sampled.",
        },
        "rateLimitOrAbuseSummary": {
            "status": "accepted",
            "summary": "Abuse-control posture was summarized with counters only.",
        },
        "outcome": "accepted",
        "evidenceRedactionVersion": "staging_ingress_operator_redaction_v1",
        "notes": "Sanitized staging ingress operator artifact for later launch review.",
    }
    payload.update(overrides)
    return payload


def _ws2_sse_artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifactVersion": "wolfystock_ws2_sse_operator_decision_evidence_v1",
        "environment": "staging",
        "operator": "ws2-topology-ops",
        "observedAt": "2026-05-08T10:30:00Z",
        "topologyMode": "polling-fallback",
        "sseBroadcastScope": "process-local",
        "pollingFallbackAccepted": True,
        "multiInstanceRiskAccepted": False,
        "userImpactSummary": "Cross-instance status relies on durable owner-scoped polling while SSE remains process-local.",
        "rollbackOrMitigationSummary": "Keep polling fallback documented until external broadcast is designed.",
        "outcome": "accepted",
        "evidenceRedactionVersion": "ws2_sse_operator_decision_redaction_v1",
    }
    payload.update(overrides)
    return payload


def _ws2_target_environment_artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifactVersion": "wolfystock_ws2_target_environment_evidence_v1",
        "validationProfile": "PROFILE_DURABLE_PROTECTED",
        "evidenceClass": "accepted-staging",
        "targetEnvironmentLabel": "staging-api-ab-primary",
        "deploymentTopologyLabel": "api-a-api-b-worker-durable-polling",
        "runId": "ws2-ab-run-20260508-001",
        "operator": "ws2-platform-ops",
        "capturedAt": "2026-05-08T10:30:00Z",
        "submittedAt": "2026-05-08T10:20:00Z",
        "completedAt": "2026-05-08T10:28:00Z",
        "reviewerAcceptanceStatus": "accepted-staging",
        "reviewerLabel": "release-reviewer",
        "releaseApproved": False,
        "publicLaunchReady": False,
        "evidenceRedactionVersion": "ws2_target_environment_evidence_redaction_v1",
        "evidenceBoundary": {
            "syntheticLocalDryRunEvidence": False,
            "ciSyntheticEvidence": False,
            "targetEnvironmentEvidence": True,
            "acceptedStagingEvidence": True,
            "publicLaunchApproval": False,
        },
        "topology": {
            "apiAInstanceLabel": "api-a",
            "apiBInstanceLabel": "api-b",
            "workerLabel": "worker-a",
            "storageLabel": "staging-postgresql",
            "sseBroadcastScope": "process-local",
            "durablePollingBaseline": True,
            "externalSseReplayImplemented": False,
            "productionQueueBrokerCutover": False,
        },
        "checks": {
            "apiASubmitTransportExercised": True,
            "syntheticWorkerLeaseFlowVerified": True,
            "workerLeaseAcquired": True,
            "progressPersisted": True,
            "apiBDurableStatusReadback": True,
            "apiBPollingReplayVerified": True,
            "apiBDurablePollingReadback": True,
            "ownerHiddenStatusVerified": True,
            "ownerHiddenPollingVerified": True,
            "retryFailureSafetyVerified": True,
            "leaseExpiryRecoveryVerified": True,
            "staleWorkerWriteRejected": True,
            "retryCapVerified": True,
            "terminalFailurePollable": True,
            "ownerIsolationVerified": True,
            "sanitizedFailureOutputVerified": True,
            "sseLimitationRecorded": True,
            "crossInstanceSseNotClaimed": True,
            "durablePollingBaselineRecorded": True,
        },
        "summaries": {
            "apiASubmitTransport": "API A accepted a synthetic analysis submit over the staging HTTPS API.",
            "workerLease": "One worker acquired a bounded lease and duplicate active lease was blocked.",
            "progressPersistence": "Durable progress rows were observed with bounded sequence metadata.",
            "apiBDurableStatusReadback": "API B read durable task status without API A process memory.",
            "apiBPollingReplay": "API B replayed durable progress events after a sequence cursor.",
            "apiBDurablePolling": "API B read durable status and replayed progress after a cursor.",
            "ownerHiddenStatus": "Cross-owner status read returned hidden not-found.",
            "ownerHiddenPolling": "Cross-owner polling read returned hidden not-found.",
            "retryFailureSafety": "Retry cap and terminal failure behavior used safe reason codes.",
            "leaseExpiryRecovery": "A second worker reclaimed the task after lease expiry.",
            "staleWorkerWriteRejection": "The stale worker could not write terminal state after reclaim.",
            "ownerIsolation": "Cross-owner status and polling reads returned hidden not-found responses.",
            "sanitizedFailureOutput": "Failure output contained only safe reason codes.",
            "sseLimitation": "Process-local SSE limitation remained recorded; durable polling was the baseline.",
            "reviewNotes": "Sanitized staging/API A-B evidence accepted for manual review only.",
        },
        "manualReview": {
            "manualReviewRequired": True,
            "manualReviewStatus": "accepted-staging",
            "singleInstanceExceptionPosture": "not-used",
            "rollbackOrDegradedNote": "Rollback to single API process remains documented if target topology degrades.",
        },
    }
    payload.update(overrides)
    return payload


def _config_snapshot_artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifactVersion": "config-snapshot-evidence-v1",
        "environment": "production-like-staging",
        "operator": "release-ops",
        "observedAt": "2026-05-08T10:30:00Z",
        "authConfigSummary": "Admin auth and RBAC posture documented without raw config values.",
        "providerConfigSummary": "Provider posture documented with redacted-only credential status.",
        "quotaConfigSummary": "Quota and alert posture documented without owner identifiers.",
        "notificationConfigSummary": "Notification routing posture documented without webhook values.",
        "databaseConfigSummary": "Database storage posture documented without DSNs.",
        "loggingRetentionSummary": "Retention window documented without raw logs.",
        "rollbackConfigSummary": "Rollback expectations documented without command output.",
        "secretPresenceSummary": "redacted only",
        "unsafeDefaultsSummary": "Unsafe defaults reviewed without raw values.",
        "outcome": "accepted",
        "evidenceRedactionVersion": "config_snapshot_redaction_v1",
    }
    payload.update(overrides)
    return payload


def _manual_release_review_artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifactVersion": "wolfystock_manual_release_approval_review_record_v1",
        "releaseCandidateSha": "5a72431e4baf7fa87d43ecae73a10d831451bafb",
        "reviewerRoleLabels": ["release-manager", "security-reviewer"],
        "approvalMeetingOrTicketRef": "release-review-ticket-2026-05-08",
        "approvalTimestamp": "2026-05-08T10:45:00Z",
        "evidenceBundleRef": "operator-evidence-bundle-v1",
        "knownResidualRisks": [
            "async-enrichment-risk-acknowledged",
            "manual-rollback-risk-acknowledged",
        ],
        "rollbackOwnerLabel": "release-rollback-owner",
        "goNoGoDecision": "approved-for-manual-release-review",
        "evidenceRedactionVersion": "manual-release-review-redaction-v1",
    }
    payload.update(overrides)
    return payload


def _api_abuse_request_safety_artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifactVersion": "wolfystock_api_abuse_request_safety_evidence_v1",
        "environment": "staging",
        "operator": "sanitized-operator-label",
        "observedAt": "2026-05-08T10:30:00Z",
        "evidenceMode": "operator-sanitized-review",
        "rateLimitInvalidRequestSummary": {
            "rateLimitProbe": "sanitized-status-only",
            "invalidRequestHandling": "sanitized-reason-codes-only",
            "clientIdentifierMaterialIncluded": False,
            "sensitiveRouteMaterialIncluded": False,
        },
        "oversizedPayloadSafety": {
            "payloadBodyStoredOrPrinted": False,
            "resultSummary": "sanitized-rejection-summary",
            "maxBodyLabel": "configured-limit-label",
        },
        "malformedInputRejectionSummary": {
            "malformedJsonRejected": True,
            "malformedFormRejected": True,
            "bodyEchoed": False,
        },
        "denialSanitization": {
            "authDenialSanitized": True,
            "adminDenialSanitized": True,
            "browserStateMaterialIncluded": False,
            "authHeaderMaterialIncluded": False,
            "principalIdentifierMaterialIncluded": False,
        },
        "auditLogRedactionProof": {
            "auditEventsUseReasonCodes": True,
            "bodyMaterialLogged": False,
            "networkAddressLogged": False,
            "principalIdentifierLogged": False,
        },
        "leakageReview": {
            "errorDetailsIncluded": False,
            "diagnosticPayloadIncluded": False,
            "sensitiveQueryStringsIncluded": False,
            "privateUrlsIncluded": False,
        },
        "runtimeDefaults": {
            "apiMiddlewareChanged": False,
            "rateLimitImplementationChanged": False,
            "identityAccessRuntimeChanged": False,
            "publicApiDefaultsChanged": False,
            "runtimeDefaultUnchanged": True,
        },
        "manualReview": {
            "manualReviewRequired": True,
            "reviewTicketRef": "review-ticket-label",
        },
        "releaseApproved": False,
        "publicLaunchReady": False,
        "outcome": "accepted",
        "evidenceRedactionVersion": "api-abuse-request-safety-redaction-v1",
    }
    payload.update(overrides)
    return payload


def _write_bundle(tmp_path: Path, artifacts: dict[str, object]) -> Path:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for filename, payload in artifacts.items():
        (bundle / filename).write_text(json.dumps(payload), encoding="utf-8")
    return bundle


def _accepted_artifacts() -> dict[str, object]:
    return {
        "api_abuse_safety_evidence.json": _api_abuse_request_safety_artifact(),
        "provider_operator_evidence.json": _provider_artifact(),
        "provider_sla_licensing_evidence.json": _provider_sla_artifact(),
        "notification_delivery_rehearsal_evidence.json": _notification_rehearsal_artifact(),
        "restore_pitr_operator_evidence.json": _restore_artifact(),
        "security_operator_acceptance.json": _security_artifact(),
        "quota_budget_operator_evidence.json": _quota_artifact(),
        "staging_ingress_operator_evidence.json": _ingress_artifact(),
        "ws2_target_environment_evidence.json": _ws2_target_environment_artifact(),
        "ws2_sse_operator_decision_evidence.json": _ws2_sse_artifact(),
        "config_snapshot_evidence.json": _config_snapshot_artifact(),
        "manual_release_approval_review_record.json": _manual_release_review_artifact(),
    }


def _template_pack_artifacts() -> dict[str, object]:
    return _build_templates("all")


def _run_checker(bundle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(bundle)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _stdout_json(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(result.stdout)


def test_all_sanitized_accepted_artifacts_require_manual_review(tmp_path: Path) -> None:
    result = _run_checker(_write_bundle(tmp_path, _accepted_artifacts()))

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["bundleStatus"] == "complete-review-required"
    assert {artifact["category"] for artifact in payload["artifacts"]} == EXPECTED_TEMPLATE_CATEGORIES
    statuses_by_category = {artifact["category"]: artifact["status"] for artifact in payload["artifacts"]}
    assert statuses_by_category["manual-release-approval"] == "needs-review"
    assert {status for category, status in statuses_by_category.items() if category != "manual-release-approval"} == {
        "accepted"
    }
    assert all(Path(artifact["pathLabel"]).name == artifact["pathLabel"] for artifact in payload["artifacts"])
    assert "launch-approved" not in result.stdout.lower()
    assert "production-ready" not in result.stdout.lower()
    assert "release-approved" not in result.stdout.lower()


def test_all_template_pack_artifacts_are_recognized_without_unknown_advisories(tmp_path: Path) -> None:
    result = _run_checker(_write_bundle(tmp_path, _template_pack_artifacts()))

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["bundleStatus"] == "complete-review-required"
    assert {artifact["category"] for artifact in payload["artifacts"]} == EXPECTED_TEMPLATE_CATEGORIES
    assert {artifact["pathLabel"] for artifact in payload["artifacts"]} == EXPECTED_TEMPLATE_FILENAMES
    assert all(artifact["status"] == "needs-review" for artifact in payload["artifacts"])
    assert payload["advisories"] == []


def test_manual_release_review_record_cannot_approve_bundle(tmp_path: Path) -> None:
    result = _run_checker(_write_bundle(tmp_path, _template_pack_artifacts()))

    assert result.returncode == 0
    payload = _stdout_json(result)
    manual = next(
        artifact for artifact in payload["artifacts"] if artifact["category"] == "manual-release-approval"
    )
    assert manual["status"] == "needs-review"
    assert payload["bundleStatus"] == "complete-review-required"
    assert payload["runtimeBehaviorChanged"] is False
    assert "launchApproved" not in result.stdout
    assert "releaseApproved" not in result.stdout


def test_missing_required_artifact_is_incomplete_no_go(tmp_path: Path) -> None:
    artifacts = _accepted_artifacts()
    artifacts.pop("quota_budget_operator_evidence.json")

    result = _run_checker(_write_bundle(tmp_path, artifacts))

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert payload["bundleStatus"] == "incomplete-no-go"
    quota = next(artifact for artifact in payload["artifacts"] if artifact["category"] == "quota-budget")
    assert quota["status"] == "missing"
    assert quota["blockingReasonSummaries"] == ["required_artifact_missing"]


def test_rejected_artifact_is_rejected_no_go(tmp_path: Path) -> None:
    artifacts = _accepted_artifacts()
    rejected_restore = deepcopy(artifacts["restore_pitr_operator_evidence.json"])
    assert isinstance(rejected_restore, dict)
    rejected_restore["outcome"] = "rejected"
    artifacts["restore_pitr_operator_evidence.json"] = rejected_restore

    result = _run_checker(_write_bundle(tmp_path, artifacts))

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert payload["bundleStatus"] == "rejected-no-go"
    restore = next(artifact for artifact in payload["artifacts"] if artifact["category"] == "restore-pitr")
    assert restore["status"] == "rejected"
    assert "operator_outcome_is_accepted:fail" in restore["blockingReasonSummaries"]


def test_unsafe_marker_does_not_leak_into_summary_output(tmp_path: Path) -> None:
    unsafe_value = "raw-secret-value-should-not-leak"
    artifacts = _accepted_artifacts()
    artifacts["provider_operator_evidence.json"] = _provider_artifact(api_key=unsafe_value)

    result = _run_checker(_write_bundle(tmp_path, artifacts))

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert unsafe_value not in combined_output
    assert "api_key" not in combined_output
    payload = _stdout_json(result)
    provider = next(artifact for artifact in payload["artifacts"] if artifact["category"] == "provider")
    assert provider["status"] == "rejected"
    assert provider["blockingReasonSummaries"] == ["unsafe_marker"]


def test_unknown_extra_artifact_is_reported_as_advisory_only(tmp_path: Path) -> None:
    artifacts = _accepted_artifacts()
    artifacts["unexpected_operator_dump.json"] = {"raw": "ignored"}

    result = _run_checker(_write_bundle(tmp_path, artifacts))

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["bundleStatus"] == "complete-review-required"
    assert payload["advisories"] == [
        {
            "category": "unknown-extra-artifact",
            "pathLabel": "unexpected_operator_dump.json",
            "status": "needs-review",
            "validatorName": "operator_evidence_bundle_check.py",
            "blockingReasonSummaries": ["unknown_artifact_not_validated"],
        }
    ]
