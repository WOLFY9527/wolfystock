#!/usr/bin/env python3
"""Generate sanitized operator evidence JSON templates offline.

The generator emits template artifacts for human operators to fill in later.
It does not read deployment state, inspect environment values, call networks,
execute probes, or connect to databases.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TEMPLATE_TIMESTAMP = "1970-01-01T00:00:00Z"
PLACEHOLDER_VALUES = (
    "<sanitized-operator-label>",
    "<staging-environment-label>",
    "<redacted-or-configured>",
    "<review-ticket-label>",
    "<release-candidate-sha>",
)


def _template_placeholders() -> dict[str, list[str]]:
    return {
        "replaceBeforeReview": list(PLACEHOLDER_VALUES),
    }


def _provider_template() -> dict[str, Any]:
    return {
        "providerName": "<redacted-or-configured>",
        "environment": "staging",
        "operator": "<sanitized-operator-label>",
        "observedAt": TEMPLATE_TIMESTAMP,
        "probeMode": "<redacted-or-configured>",
        "networkCallsEnabled": False,
        "credentialPresence": "redacted",
        "circuitState": {
            "state": "<redacted-or-configured>",
            "summary": "<redacted-or-configured>",
        },
        "fallbackState": {
            "state": "<redacted-or-configured>",
            "summary": "<redacted-or-configured>",
        },
        "outcome": "needs-review",
        "evidenceRedactionVersion": "provider_operator_redaction_v1",
        "notes": "<review-ticket-label>",
        "templatePlaceholders": _template_placeholders(),
    }


def _provider_sla_licensing_template() -> dict[str, Any]:
    return {
        "artifactVersion": "wolfystock_provider_sla_licensing_evidence_v1",
        "environment": "staging",
        "operator": "sanitized-operator-label",
        "observedAt": TEMPLATE_TIMESTAMP,
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
        "outcome": "needs-review",
        "evidenceRedactionVersion": "provider-sla-licensing-redaction-v1",
        "notes": "<review-ticket-label>",
        "templatePlaceholders": _template_placeholders(),
    }


def _restore_pitr_template() -> dict[str, Any]:
    return {
        "schemaVersion": "wolfystock_restore_pitr_operator_evidence_input_v1",
        "evidenceMode": "local-synthetic-preflight",
        "drillId": "review-ticket-label",
        "environment": "isolated-restore",
        "operator": "sanitized-operator-label",
        "startedAt": TEMPLATE_TIMESTAMP,
        "completedAt": TEMPLATE_TIMESTAMP,
        "backupArtifactRef": "review-ticket-label",
        "restoreTarget": "staging-environment-label",
        "restoreCommandExecuted": False,
        "destructiveProductionCommandExecuted": False,
        "pitrTargetTimestamp": TEMPLATE_TIMESTAMP,
        "verificationQueries": [
            {
                "label": "redacted-or-configured",
                "resultKind": "count",
                "observedCount": 0,
                "expectedCount": 0,
                "checksum": "redacted-or-configured",
            }
        ],
        "rpoObservedSeconds": 0,
        "rtoObservedSeconds": 0,
        "outcome": "needs-review",
        "reviewOnly": True,
        "publicLaunchReady": False,
        "launchApproved": False,
        "evidenceRedactionVersion": "restore-pitr-redaction-v1",
        "isolatedTarget": {
            "targetLabel": "staging-environment-label",
            "environment": "isolated-restore",
            "isolationBoundaryRef": "review-ticket-label",
            "productionStorageTouched": False,
        },
        "backupArtifactSummary": {
            "artifactRef": "review-ticket-label",
            "artifactKind": "encrypted-base-backup",
            "walArchiveSummaryRef": "review-ticket-label",
            "sourceEnvironmentLabel": "redacted-or-configured",
            "rawPathIncluded": False,
        },
        "pitrTarget": {
            "targetTimestamp": TEMPLATE_TIMESTAMP,
            "targetRef": "review-ticket-label",
            "walReplaySummaryRef": "review-ticket-label",
        },
        "restoreExecutionSummary": {
            "restoreCommandExecuted": False,
            "executedOutsideValidator": False,
            "localOnlyDryRun": True,
            "productionDbMutation": False,
            "destructiveProductionCommandExecuted": False,
            "commandSummaryRef": "review-ticket-label",
        },
        "postRestoreSmoke": {
            "appBootReadiness": "needs-review",
            "schemaCompatibility": "needs-review",
            "sampledQuerySummaries": ["redacted-or-configured"],
        },
        "ownerIsolationSmoke": {
            "ownerScopeChecked": False,
            "crossOwnerAccessBlocked": False,
            "sampledOwnerLabelRefs": ["redacted-or-configured"],
        },
        "rollbackDecisionPoint": {
            "decision": "manual-review-required",
            "decidedAt": TEMPLATE_TIMESTAMP,
            "decisionRef": "review-ticket-label",
        },
        "operatorApprovals": [
            {
                "role": "restore-operator",
                "approved": False,
                "approvedAt": TEMPLATE_TIMESTAMP,
                "approvalRef": "review-ticket-label",
            },
            {
                "role": "release-reviewer",
                "approved": False,
                "approvedAt": TEMPLATE_TIMESTAMP,
                "approvalRef": "review-ticket-label",
            },
        ],
        "sanitizedArtifactReferences": [
            {
                "kind": "validator-output",
                "label": "restore-pitr-validator-output",
                "ref": "review-ticket-label",
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
        "templatePlaceholders": _template_placeholders(),
    }


def _security_section() -> dict[str, Any]:
    return {
        "sanitizedOperator": "sanitized-operator-label",
        "timestamp": TEMPLATE_TIMESTAMP,
        "environment": "staging-environment-label",
        "outcome": "needs-review",
        "sampledControls": ["review-ticket-label"],
        "evidenceRedactionVersion": "redacted-or-configured",
        "runtimeBehaviorChanged": False,
    }


def _security_template() -> dict[str, Any]:
    return {
        "schemaVersion": "wolfystock_security_operator_acceptance_artifact_v1",
        "mfaAdminPilot": {
            **_security_section(),
            "testAccountRoleLabels": ["redacted_role"],
        },
        "rbacFallbackDisable": {
            **_security_section(),
            "disableSwitchExplicit": False,
            "fallbackDisabled": False,
            "routeInventoryComplete": False,
            "coarseFallbackDisabledOrExceptionAccepted": False,
            "backendAdminRoutesExplicitCapabilities": False,
            "frontendAdminGatesCapabilityBased": False,
            "frontendAdminMissingCapabilitiesFailClosed": False,
            "explicitCapabilityPayloadsPassWithoutFallback": False,
            "legacyMissingCapabilityUsersFailClosed": False,
            "rollbackPlanRecorded": False,
            "auditEvidenceSanitized": False,
            "runtimeDefaultUnchanged": False,
        },
        "rbacFallbackObserve": {
            **_security_section(),
            "coarseAdminCompatibilityFallbackPresent": True,
            "fallbackObserveModeEnabled": False,
            "fallbackOffAccepted": False,
            "fallbackRemoved": False,
            "productionLeastPrivilegeAccepted": False,
            "publicLaunchApproved": False,
            "failClosedProductionEnforcementEnabled": False,
            "routeInventory": {
                "routeInventoryComplete": False,
                "inventoryCurrent": False,
                "adminRouteCount": 0,
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
                "proofPresent": False,
                "sampleCount": 0,
                "allSampledPayloadsHaveExplicitCapabilities": False,
                "capabilityFields": ["capabilities"],
            },
            "legacyMissingPayloadFailClosedObserveEvidence": {
                "legacyMissingCapabilityUsersFailClosed": False,
                "missingCapabilityPayloadsFailClosed": False,
                "denialResponsesSanitized": False,
                "observeOnlyNoRuntimeEnforcementChange": False,
            },
            "rollbackPosture": {
                "rollbackPlanRecorded": False,
                "fallbackStillEnabled": True,
                "runtimeDefaultUnchanged": False,
                "failClosedProductionEnforcementEnabled": False,
            },
            "sanitizedAuditExcerpts": [
                {
                    "routeFamily": "redacted.route.family",
                    "requiredCapability": "ops:system_config:read",
                    "actorSafeHandle": "actor-safe-handle",
                    "sourceSurface": "operator-review",
                    "outcome": "needs-review",
                    "rawValuesIncluded": False,
                }
            ],
        },
        "breakGlassRecovery": {
            **_security_section(),
            "generationVerified": False,
            "displayOnceVerified": False,
            "plaintextStoredAfterDisplay": False,
            "hashStorageVerified": False,
            "singleUseConsumeVerified": False,
            "replayDeniedVerified": False,
            "rotationRevocationVerified": False,
            "breakGlassDefaultOff": False,
            "recoveryFallbackSampled": False,
            "rollbackPlanRecorded": False,
            "auditEvidenceSanitized": False,
            "runtimeDefaultUnchanged": False,
        },
        "adminRouteSampling": {
            **_security_section(),
            "sampledRoutes": ["/redacted-or-configured"],
        },
        "templatePlaceholders": _template_placeholders(),
    }


def _quota_section() -> dict[str, Any]:
    return {
        "environment": "<staging-environment-label>",
        "operator": "<sanitized-operator-label>",
        "observedAt": TEMPLATE_TIMESTAMP,
        "sampledOwnerLabels": ["<redacted-or-configured>"],
        "thresholdPolicyVersion": "<redacted-or-configured>",
        "dryRunOnly": True,
        "outboundSent": False,
        "outcome": "needs-review",
        "evidenceRedactionVersion": "quota_budget_operator_redaction_v1",
        "notes": "<review-ticket-label>",
    }


def _quota_budget_template() -> dict[str, Any]:
    return {
        "schemaVersion": "wolfystock_quota_operator_evidence_v1",
        "mode": "operator_sanitized_template",
        "quotaPilot": _quota_section(),
        "budgetAlertDryRun": _quota_section(),
        "ownerScopeSampling": _quota_section(),
        "disabledPreferenceSuppression": _quota_section(),
        "notificationNoOutboundProof": _quota_section(),
        "templatePlaceholders": _template_placeholders(),
    }


def _staging_ingress_template() -> dict[str, Any]:
    return {
        "artifactVersion": "wolfystock_staging_ingress_operator_evidence_v1",
        "environment": "staging",
        "operator": "<sanitized-operator-label>",
        "observedAt": TEMPLATE_TIMESTAMP,
        "baseUrlLabel": "staging-environment-label",
        "networkCallsEnabled": False,
        "checkedRoutes": [
            {
                "routeLabel": "review-ticket-label",
                "method": "GET",
                "pathPattern": "/redacted-or-configured",
                "statusClass": "4xx",
                "summary": "<redacted-or-configured>",
            }
        ],
        "authBoundaryResult": {"summary": "<redacted-or-configured>"},
        "securityHeaderSummary": {"summary": "<redacted-or-configured>"},
        "csrfOrStateMutationSummary": {"summary": "<redacted-or-configured>"},
        "publicSurfaceSummary": {"summary": "<redacted-or-configured>"},
        "rateLimitOrAbuseSummary": {"summary": "<redacted-or-configured>"},
        "outcome": "needs-review",
        "evidenceRedactionVersion": "staging_ingress_operator_redaction_v1",
        "notes": "<review-ticket-label>",
        "templatePlaceholders": _template_placeholders(),
    }


def _ws2_sse_template() -> dict[str, Any]:
    return {
        "artifactVersion": "wolfystock_ws2_sse_operator_decision_evidence_v1",
        "environment": "staging-environment-label",
        "operator": "sanitized-operator-label",
        "observedAt": TEMPLATE_TIMESTAMP,
        "topologyMode": "needs-review",
        "sseBroadcastScope": "needs-review",
        "pollingFallbackAccepted": False,
        "multiInstanceRiskAccepted": False,
        "userImpactSummary": "<redacted-or-configured>",
        "rollbackOrMitigationSummary": "<review-ticket-label>",
        "outcome": "needs-review",
        "evidenceRedactionVersion": "ws2_sse_operator_decision_redaction_v1",
        "templatePlaceholders": _template_placeholders(),
    }


def _config_snapshot_template() -> dict[str, Any]:
    return {
        "artifactVersion": "wolfystock_config_snapshot_evidence_v1",
        "environment": "staging",
        "operator": "<sanitized-operator-label>",
        "observedAt": TEMPLATE_TIMESTAMP,
        "authConfigSummary": "<redacted-or-configured>",
        "providerConfigSummary": "<redacted-or-configured>",
        "quotaConfigSummary": "<redacted-or-configured>",
        "notificationConfigSummary": "<redacted-or-configured>",
        "databaseConfigSummary": "<redacted-or-configured>",
        "loggingRetentionSummary": "<redacted-or-configured>",
        "rollbackConfigSummary": "<review-ticket-label>",
        "secretPresenceSummary": "redacted only",
        "unsafeDefaultsSummary": "<redacted-or-configured>",
        "outcome": "needs-review",
        "evidenceRedactionVersion": "config-snapshot-redaction-v1",
        "templatePlaceholders": _template_placeholders(),
    }


def _manual_release_template() -> dict[str, Any]:
    return {
        "artifactVersion": "wolfystock_manual_release_approval_review_record_v1",
        "releaseCandidateSha": "0000000",
        "releaseCandidateShaTemplate": "<release-candidate-sha>",
        "reviewerRoleLabels": ["release_reviewer"],
        "approvalMeetingOrTicketRef": "review-ticket-label",
        "approvalTimestamp": TEMPLATE_TIMESTAMP,
        "evidenceBundleRef": "review-ticket-label",
        "knownResidualRisks": ["redacted-or-configured"],
        "rollbackOwnerLabel": "sanitized-operator-label",
        "goNoGoDecision": "needs-review",
        "evidenceRedactionVersion": "manual-release-review-redaction-v1",
        "templatePlaceholders": _template_placeholders(),
    }


TemplateFactory = Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class TemplateSpec:
    category: str
    filename: str
    factory: TemplateFactory


TEMPLATE_SPECS: tuple[TemplateSpec, ...] = (
    TemplateSpec("provider", "provider_operator_evidence.json", _provider_template),
    TemplateSpec(
        "provider-sla-licensing",
        "provider_sla_licensing_evidence.json",
        _provider_sla_licensing_template,
    ),
    TemplateSpec("restore-pitr", "restore_pitr_operator_evidence.json", _restore_pitr_template),
    TemplateSpec("security", "security_operator_acceptance.json", _security_template),
    TemplateSpec("quota-budget", "quota_budget_operator_evidence.json", _quota_budget_template),
    TemplateSpec("staging-ingress", "staging_ingress_operator_evidence.json", _staging_ingress_template),
    TemplateSpec("ws2-sse", "ws2_sse_operator_decision_evidence.json", _ws2_sse_template),
    TemplateSpec("config-snapshot", "config_snapshot_evidence.json", _config_snapshot_template),
    TemplateSpec(
        "manual-release-approval",
        "manual_release_approval_review_record.json",
        _manual_release_template,
    ),
)


def _selected_specs(category: str) -> tuple[TemplateSpec, ...]:
    if category == "all":
        return TEMPLATE_SPECS
    return tuple(spec for spec in TEMPLATE_SPECS if spec.category == category)


def _build_templates(category: str) -> dict[str, dict[str, Any]]:
    return {spec.filename: spec.factory() for spec in _selected_specs(category)}


def _write_templates(output_dir: Path, templates: dict[str, dict[str, Any]], *, force: bool) -> None:
    existing = [filename for filename in templates if (output_dir / filename).exists()]
    if existing and not force:
        joined = ", ".join(sorted(existing))
        raise SystemExit(f"[FAIL] Refusing to overwrite existing template file(s): {joined}")

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in templates.items():
        path = output_dir / filename
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output_dir",
        nargs="?",
        help="Directory where template JSON files should be written. Not required with --stdout.",
    )
    parser.add_argument(
        "--category",
        default="all",
        choices=("all", *(spec.category for spec in TEMPLATE_SPECS)),
        help="Generate one template category or all categories.",
    )
    parser.add_argument("--stdout", action="store_true", help="Print templates as JSON instead of writing files.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing template files.")
    args = parser.parse_args(argv)

    templates = _build_templates(args.category)
    if args.stdout:
        print(json.dumps(templates, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if not args.output_dir:
        parser.error("output_dir is required unless --stdout is used")

    _write_templates(Path(args.output_dir), templates, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
