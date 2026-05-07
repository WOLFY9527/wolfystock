#!/usr/bin/env python3
"""Validate sanitized operator evidence for public launch acceptance review.

This checker consumes synthetic or operator-sanitized JSON. It does not read
real environment files, inspect production data paths, print secret values, or
call external services.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INPUT_SCHEMA_VERSION = "wolfystock_launch_acceptance_evidence_input_v1"
SUMMARY_SCHEMA_VERSION = "wolfystock_launch_acceptance_evidence_summary_v1"

REDACTED_VALUES = {
    "",
    "[redacted]",
    "redacted",
    "<redacted>",
    "***",
    "not_recorded",
    "not_provided",
    "none",
}
SENSITIVE_KEY_MARKERS = (
    ".env",
    "api key",
    "cookie id",
    "dsn",
    "env_file",
    "envfile",
    "password",
    "token",
    "secret",
    "cookie",
    "session",
    "totp",
    "mfa_code",
    "recovery_code",
    "api_key",
    "apikey",
    "provider credential",
    "key_material",
    "private_key",
    "raw body",
    "webhook_url",
    "credential",
    "provider_payload",
    "providerpayload",
    "raw_payload",
    "rawpayload",
    "raw response",
    "raw response body",
    "rawresponsebody",
    "response_body",
    "responsebody",
)
SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"\bpostgres(?:ql)?://", re.IGNORECASE),
    re.compile(r"\b(?:password|token|secret|api[\s_-]?key|cookie|session|dsn)\s*=", re.IGNORECASE),
    re.compile(r"['\"](?:password|token|secret|api[\s_-]?key|cookie|session|dsn|response[_\s-]?body)['\"]\s*:", re.IGNORECASE),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"https?://[^\s?#]+[?][^\s]+", re.IGNORECASE),
)

REQUIRED_SANITIZATION: dict[str, bool] = {
    "externalServicesCalledByChecker": False,
    "realSecretsIncluded": False,
    "rawCredentialValuesIncluded": False,
    "rawProviderPayloadsIncluded": False,
    "responseBodiesIncluded": False,
    "productionDataPathsIncluded": False,
}


@dataclass(frozen=True)
class CategorySpec:
    id: str
    title: str
    required_evidence: str
    required_checks: tuple[str, ...]


CATEGORY_SPECS: tuple[CategorySpec, ...] = (
    CategorySpec(
        id="mfa_pilot_acceptance",
        title="MFA pilot acceptance evidence",
        required_evidence=(
            "accepted admin-only MFA pilot, recovery-path, rollback, unsupported rollout NO-GO, "
            "break-glass default-off, and sanitized audit evidence"
        ),
        required_checks=(
            "adminPilotPassed",
            "adminOnlyScopeRecorded",
            "unsupportedGlobalRolloutNoGo",
            "recoveryPathTested",
            "breakGlassDisabledByDefault",
            "rollbackPlanRecorded",
            "auditEvidenceSanitized",
            "secretEvidenceRedacted",
        ),
    ),
    CategorySpec(
        id="rbac_fallback_disable_switch",
        title="RBAC fallback disable switch evidence",
        required_evidence=(
            "RBAC fallback disable switch or accepted production exception, complete route inventory, "
            "fail-closed payload evidence, rollback, and sanitized audit evidence"
        ),
        required_checks=(
            "disableSwitchExplicit",
            "routeInventoryComplete",
            "coarseFallbackDisabledOrExceptionAccepted",
            "explicitCapabilityPayloadsPassWithoutFallback",
            "legacyMissingCapabilityUsersFailClosed",
            "rollbackPlanRecorded",
            "auditEvidenceSanitized",
            "runtimeDefaultUnchanged",
        ),
    ),
    CategorySpec(
        id="provider_credential_staging_dry_run",
        title="Provider credential staging dry-run evidence",
        required_evidence=(
            "staging credential dry-run, presence-only credential contract, entitlement matrix, and no checker live calls"
        ),
        required_checks=(
            "stagingDryRunPassed",
            "credentialPresenceOnly",
            "noLiveCallsByChecker",
            "entitlementMatrixAttached",
        ),
    ),
    CategorySpec(
        id="provider_live_probe_opt_in_timeout",
        title="Provider live probe opt-in and bounded-timeout evidence",
        required_evidence=(
            "explicit provider live-probe opt-in for a named staging provider, bounded timeout, sanitized result, "
            "and proof the launch checker made no live calls"
        ),
        required_checks=(
            "namedStagingProviderRecorded",
            "liveProbeOptInRecorded",
            "liveProbeTimeoutBounded",
            "probeResultSanitized",
            "noLiveCallsByChecker",
        ),
    ),
    CategorySpec(
        id="provider_circuit_controlled_enforcement",
        title="Provider circuit controlled-enforcement evidence",
        required_evidence=(
            "controlled provider-circuit enforcement pilot, bounded route, rollback switch, and sanitized degraded-state evidence"
        ),
        required_checks=(
            "controlledEnforcementPilotPassed",
            "boundedRouteRecorded",
            "rollbackSwitchRecorded",
            "degradedEvidenceSanitized",
        ),
    ),
    CategorySpec(
        id="quota_pilot_acceptance",
        title="Quota pilot acceptance evidence",
        required_evidence=(
            "controlled quota pilot with explicit owner allowlist, out-of-scope advisory behavior, "
            "advisory-only invoice reconciliation, global enforcement disabled by default, rollback switch, "
            "and user/admin status-label evidence"
        ),
        required_checks=(
            "pilotPassed",
            "explicitOwnerAllowlistRecorded",
            "outOfScopeUsersAdvisoryOnly",
            "invoiceReconciliationAdvisoryOnly",
            "invoiceReconciliationNotEnforcementInput",
            "globalEnforcementDisabledByDefault",
            "rollbackSwitchRecorded",
            "statusLabelsRecorded",
        ),
    ),
    CategorySpec(
        id="budget_alert_dry_run_acceptance",
        title="Budget alert dry-run acceptance evidence",
        required_evidence=(
            "sanitized dry-run budget alert intent, outbound delivery disabled by default, "
            "no live LLM/provider/invoice calls, and user/admin alert-label evidence"
        ),
        required_checks=(
            "pilotBlockEmitsSanitizedBudgetAlertIntent",
            "budgetAlertEvidenceRedacted",
            "realOutboundDeliveryDisabledByDefault",
            "noLiveLlmProviderOrInvoiceCalls",
            "alertStatusLabelsRecorded",
        ),
    ),
    CategorySpec(
        id="real_isolated_postgresql_restore_pitr",
        title="Real isolated PostgreSQL restore/PITR evidence",
        required_evidence=(
            "real isolated PostgreSQL restore, PITR execution, isolated target, and post-restore smoke evidence"
        ),
        required_checks=(
            "isolatedTargetUsed",
            "restoreExecuted",
            "pitrExecuted",
            "postRestoreSmokePassed",
        ),
    ),
    CategorySpec(
        id="staging_ingress_smoke",
        title="Staging ingress smoke evidence",
        required_evidence=(
            "HTTPS staging ingress smoke, backend port exposure proof, synthetic users/data, and live opt-in evidence"
        ),
        required_checks=(
            "httpsIngressSmokePassed",
            "backend8000NotPublic",
            "syntheticUsersAndData",
            "liveOptInRecorded",
        ),
    ),
    CategorySpec(
        id="public_api_frontend_no_secret_safety",
        title="Public API/frontend no-secret public-safety evidence",
        required_evidence=(
            "public API, frontend DOM, route payload, and release secret-scan no-secret evidence"
        ),
        required_checks=(
            "publicApiNoSecret",
            "frontendDomNoSecret",
            "publicRoutesNoRawPayloads",
            "releaseSecretScanPassed",
        ),
    ),
    CategorySpec(
        id="supply_chain_dependency_build_artifact_safety",
        title="Dependency and build artifact safety evidence",
        required_evidence=(
            "sanitized dependency-manifest inspection, build/test artifact scan, visible frontend build warnings, "
            "no dependency or lockfile changes, and NO-GO behavior for missing required evidence"
        ),
        required_checks=(
            "dependencyManifestsInspected",
            "manifestsSanitized",
            "buildArtifactsSanitized",
            "frontendBuildWarningsVisible",
            "noDependencyOrLockfileChanges",
            "missingEvidenceNoGoVerified",
        ),
    ),
    CategorySpec(
        id="incident_response_audit_evidence",
        title="Incident response and audit evidence",
        required_evidence=(
            "sanitized incident-response evidence for admin-critical actions, preview-first cleanup, "
            "provider/notification/release failure paths, local no-network generation, and audit redaction"
        ),
        required_checks=(
            "incidentPackAttached",
            "adminCriticalActionsAudited",
            "previewFirstCleanupEvidence",
            "providerNotificationReleaseFailuresRecorded",
            "localNoNetworkGeneration",
            "auditEvidenceSanitized",
            "secretEvidenceRedacted",
        ),
    ),
    CategorySpec(
        id="final_clean_full_ci_gate",
        title="Final clean full ci_gate evidence",
        required_evidence=(
            "clean worktree, full ci_gate, release secret scan, and final diff check evidence"
        ),
        required_checks=(
            "cleanWorktree",
            "fullCiGatePassed",
            "releaseSecretScanPassed",
            "diffCheckPassed",
        ),
    ),
)


def _empty_contract() -> dict[str, Any]:
    return {
        "schemaVersion": INPUT_SCHEMA_VERSION,
        "mode": "synthetic_empty",
        "categories": {},
    }


def _load_contract(path: str | None) -> dict[str, Any]:
    if not path:
        return _empty_contract()
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit("[FAIL] Evidence file not found")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[FAIL] Evidence file is not valid JSON: {exc.msg}")
    if not isinstance(payload, dict):
        raise SystemExit("[FAIL] Evidence file must contain a JSON object")
    return payload


def _parse_timestamp(raw_value: Any) -> bool:
    value = str(raw_value or "")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return True


def _contains_sensitive_value(value: Any, key_path: str = "") -> bool:
    if isinstance(value, dict):
        for raw_key, raw_child in value.items():
            key = str(raw_key)
            child_path = f"{key_path}.{key}" if key_path else key
            lowered_key = key.lower()
            if any(marker in lowered_key for marker in SENSITIVE_KEY_MARKERS):
                if isinstance(raw_child, str) and raw_child.strip().lower() not in REDACTED_VALUES:
                    return True
                if not isinstance(raw_child, (str, bool, int, float, type(None))):
                    return True
            if _contains_sensitive_value(raw_child, child_path):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_sensitive_value(item, f"{key_path}[]") for item in value)
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in SENSITIVE_VALUE_PATTERNS)
    return False


def _check_truthy(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str) and value.strip().lower() == "pass":
        return True
    return False


def _category_result(spec: CategorySpec, raw_category: Any) -> dict[str, Any]:
    reason_codes: list[str] = []
    missing_checks: list[str] = []
    failed_checks: list[str] = []
    missing_sanitization: list[str] = []
    invalid_sanitization: list[str] = []

    if raw_category is None:
        reason_codes.append("missing_evidence")
        return {
            "id": spec.id,
            "title": spec.title,
            "status": "blocking",
            "requiredEvidence": spec.required_evidence,
            "requiredChecks": list(spec.required_checks),
            "missingChecks": list(spec.required_checks),
            "reasonCodes": reason_codes,
            "acceptedEvidence": False,
        }
    if not isinstance(raw_category, dict):
        reason_codes.append("invalid_category_shape")
        return {
            "id": spec.id,
            "title": spec.title,
            "status": "blocking",
            "requiredEvidence": spec.required_evidence,
            "requiredChecks": list(spec.required_checks),
            "missingChecks": list(spec.required_checks),
            "reasonCodes": reason_codes,
            "acceptedEvidence": False,
        }
    if _contains_sensitive_value(raw_category):
        reason_codes.append("sensitive_value_present")
    elif str(raw_category.get("status") or "").strip().lower() != "accepted":
        reason_codes.append("status_not_accepted")
    else:
        if not str(raw_category.get("acceptedBy") or "").strip():
            reason_codes.append("missing_accepted_by")
        if not str(raw_category.get("evidenceRef") or "").strip():
            reason_codes.append("missing_evidence_ref")
        if not _parse_timestamp(raw_category.get("capturedAt")):
            reason_codes.append("invalid_captured_at")

        checks = raw_category.get("checks")
        if not isinstance(checks, dict):
            reason_codes.append("missing_checks_object")
            missing_checks = list(spec.required_checks)
        else:
            for check_name in spec.required_checks:
                if check_name not in checks:
                    missing_checks.append(check_name)
                elif not _check_truthy(checks.get(check_name)):
                    failed_checks.append(check_name)
            if missing_checks:
                reason_codes.append("missing_required_checks")
            if failed_checks:
                reason_codes.append("required_checks_not_passed")

        sanitization = raw_category.get("sanitization")
        if not isinstance(sanitization, dict):
            reason_codes.append("missing_sanitization_object")
            missing_sanitization = sorted(REQUIRED_SANITIZATION)
        else:
            for field, expected in REQUIRED_SANITIZATION.items():
                if field not in sanitization:
                    missing_sanitization.append(field)
                elif sanitization.get(field) is not expected:
                    invalid_sanitization.append(field)
            if missing_sanitization:
                reason_codes.append("missing_sanitization_fields")
            if invalid_sanitization:
                reason_codes.append("unsafe_sanitization_fields")

    accepted = not reason_codes
    result: dict[str, Any] = {
        "id": spec.id,
        "title": spec.title,
        "status": "accepted" if accepted else "blocking",
        "requiredEvidence": spec.required_evidence,
        "requiredChecks": list(spec.required_checks),
        "missingChecks": missing_checks,
        "failedChecks": failed_checks,
        "missingSanitizationFields": missing_sanitization,
        "invalidSanitizationFields": invalid_sanitization,
        "reasonCodes": reason_codes,
        "acceptedEvidence": accepted,
    }
    if accepted:
        result["evidenceRef"] = str(raw_category.get("evidenceRef"))
    return result


def build_summary(contract: dict[str, Any]) -> dict[str, Any]:
    categories = contract.get("categories") if isinstance(contract.get("categories"), dict) else {}
    category_results = [_category_result(spec, categories.get(spec.id)) for spec in CATEGORY_SPECS]
    blockers = [
        {
            "id": item["id"],
            "status": "blocking",
            "requiredEvidence": item["requiredEvidence"],
        }
        for item in category_results
        if item["status"] != "accepted"
    ]
    final_status = "GO-REVIEW-REQUIRED" if not blockers else "NO-GO"
    status_reason = (
        "All hard blockers have accepted sanitized evidence; release approval remains manual."
        if not blockers
        else "Public launch remains blocked until every hard blocker has accepted sanitized operator evidence."
    )
    return {
        "schemaVersion": SUMMARY_SCHEMA_VERSION,
        "tool": "scripts/launch_acceptance_evidence.py",
        "inputSchemaVersion": str(contract.get("schemaVersion") or ""),
        "mode": str(contract.get("mode") or "unspecified"),
        "finalStatus": final_status,
        "releaseApproved": False,
        "statusReason": status_reason,
        "categories": category_results,
        "hardBlockers": blockers,
        "summary": {
            "total": len(category_results),
            "accepted": len(category_results) - len(blockers),
            "blocking": len(blockers),
        },
        "sanitization": {
            "externalServicesCalled": False,
            "networkCallsEnabled": False,
            "realEnvFileRead": False,
            "secretValuesRead": False,
            "secretValuesIncluded": False,
            "rawPayloadsIncluded": False,
            "responseBodiesIncluded": False,
            "productionDataPathsRead": False,
            "runtimeDefaultsChanged": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate sanitized launch acceptance evidence JSON.")
    parser.add_argument("--evidence", help="Synthetic or operator-sanitized evidence JSON.")
    parser.add_argument(
        "--allow-no-go",
        action="store_true",
        help="Return exit 0 even when evidence keeps finalStatus as NO-GO.",
    )
    args = parser.parse_args(argv)

    summary = build_summary(_load_contract(args.evidence))
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["finalStatus"] == "NO-GO" and not args.allow_no_go:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
