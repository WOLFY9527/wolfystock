#!/usr/bin/env python3
"""Validate sanitized security operator acceptance artifacts offline.

This helper consumes only operator-sanitized JSON. It does not import auth
runtime code, read environment files, call networks, touch databases, or alter
RBAC/MFA behavior.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from evidence_safety import compact_key as _compact_key
    from evidence_safety import finding as _finding
    from evidence_safety import matches_marker as _key_matches
    from evidence_safety import scan_json_tree
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from scripts.evidence_safety import scan_json_tree
    from scripts.evidence_safety import compact_key as _compact_key
    from scripts.evidence_safety import finding as _finding
    from scripts.evidence_safety import matches_marker as _key_matches


SCHEMA_VERSION = "wolfystock_security_operator_acceptance_check_v1"
INPUT_SCHEMA_VERSION = "wolfystock_security_operator_acceptance_artifact_v1"
DEFAULT_PROFILE = "operator-acceptance"
RBAC_R5_OBSERVE_PROFILE = "rbac-r5-observe"
REQUIRED_SECTIONS = (
    "mfaAdminPilot",
    "rbacFallbackDisable",
    "breakGlassRecovery",
    "adminRouteSampling",
)
REQUIRED_SECTION_FIELDS = (
    "sanitizedOperator",
    "timestamp",
    "environment",
    "outcome",
    "sampledControls",
    "evidenceRedactionVersion",
)
RBAC_FALLBACK_OFF_OPERATOR_PILOT_FIELDS = (
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
RBAC_R5_OBSERVE_ROUTE_INVENTORY_FIELDS = (
    "endpoint",
    "method",
    "currentDependency",
    "targetCapability",
    "sensitivityTier",
    "reasonRequirement",
    "reauthRequirement",
    "auditRequirement",
)
RBAC_R5_FORBIDDEN_TRUE_KEYS = {
    "coarsefallbackremoved",
    "fallbackoffaccepted",
    "fallbackremoved",
    "leastprivilegeaccepted",
    "productionleastprivilegeaccepted",
    "publiclaunchapproved",
    "rbacfallbackoffaccepted",
    "rbacfallbackremoved",
}
MFA_RECOVERY_CODE_ACCEPTANCE_TRUE_FIELDS = (
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
MFA_RECOVERY_CODE_ACCEPTANCE_FALSE_FIELDS = (
    "plaintextStoredAfterDisplay",
)
SAFE_PLACEHOLDERS = {
    "",
    "***",
    "********",
    "[redacted]",
    "<redacted>",
    "masked",
    "missing",
    "none",
    "not_applicable",
    "redacted",
    "sanitized",
}
SENSITIVE_KEY_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "email",
    "mfa_secret",
    "otp_seed",
    "otpseed",
    "password",
    "private_key",
    "recovery_code",
    "recoverycode",
    "session",
    "totp_secret",
    "token",
    "user_id",
    "userid",
    "username",
)
RAW_PAYLOAD_KEY_MARKERS = (
    "debug_payload",
    "debugpayload",
    "debug_trace",
    "debugtrace",
    "provider_payload",
    "providerpayload",
    "raw_payload",
    "rawpayload",
    "raw_request",
    "rawrequest",
    "raw_response",
    "rawresponse",
    "request_body",
    "requestbody",
    "response_body",
    "responsebody",
    "stack_trace",
    "stacktrace",
)
SENSITIVE_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "secret_assignment",
        re.compile(
            r"\b(?:api[-_]?key|apikey|authorization|bearer|cookie|mfa[-_]?secret|"
            r"otp[-_]?seed|password|private[-_]?key|recovery[-_]?code|session|"
            r"totp[-_]?secret|token)\b\s*[:=]\s*(?!\*{3}|redacted\b)[^\s,;&]+",
            re.IGNORECASE,
        ),
    ),
    ("bearer_token", re.compile(r"\bBearer\s+(?!\*{3}|redacted\b)[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE)),
    ("cookie_header", re.compile(r"\bSet-Cookie\s*:\s*[^;\s]+", re.IGNORECASE)),
    ("credential_bearing_url", re.compile(r"(?i)\bhttps?://[^\s?#]+[?][^\s]+")),
    ("private_url", re.compile(r"(?i)\bhttps?://[^\s]+")),
    ("totp_uri", re.compile(r"(?i)\botpauth://")),
    ("raw_recovery_code", re.compile(r"\b[A-Z0-9]{4,8}(?:-[A-Z0-9]{4,8}){2,}\b")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("provider_token", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9_]{24,}|xox[baprs]-[A-Za-z0-9-]{20,})\b")),
    (
        "production_credential_assignment",
        re.compile(
            r"\b[A-Z][A-Z0-9_]*(?:SECRET|KEY|TOKEN|PASSWORD|COOKIE|SESSION)[A-Z0-9_]*\s*=\s*"
            r"(?!\*{3}|redacted\b|masked\b|missing\b|none\b)[^\s,;&]+"
        ),
    ),
    ("stack_trace", re.compile(r"(?i)\b(?:traceback \(most recent call last\)|stack trace|stacktrace)\b")),
    ("debug_payload", re.compile(r"(?i)\b(?:raw|debug|provider)[_\s-]+(?:payload|request|response|body)\b")),
)
LAUNCH_APPROVAL_PATTERN = re.compile(
    r"\b(?:launch[-_\s]?approved|production[-_\s]?ready|automatic[-_\s]?go|"
    r"public[-_\s]?launch[-_\s]?(?:approved|ready)|release[-_\s]?approved)\b",
    re.IGNORECASE,
)
GLOBAL_MFA_ENFORCEMENT_PATTERN = re.compile(
    r"\b(?:global|all[-_\s]?users?|production|public)\b.{0,60}\bMFA\b.{0,60}"
    r"\b(?:approved|required|enabled|enforced|ready|go)\b|"
    r"\bMFA\b.{0,60}\b(?:approved|required|enabled|enforced|ready|go)\b.{0,60}"
    r"\b(?:global|all[-_\s]?users?|production|public)\b",
    re.IGNORECASE,
)
RBAC_R5_UNSAFE_ACCEPTANCE_PATTERN = re.compile(
    r"\b(?:(?:rbac[-_\s]?)?fallback[-_\s]?(?:removed|deleted|eliminated)|"
    r"coarse[-_\s]admin[-_\s]fallback[-_\s]?(?:removed|deleted|eliminated)|"
    r"fallback[-_\s]?off[-_\s]?(?:accepted|approved)|"
    r"(?:production[-_\s]?)?least[-_\s]?privilege[-_\s]?(?:accepted|approved|ready))\b",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_artifact(path: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"[FAIL] Artifact file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[FAIL] Artifact file is not valid JSON: {exc}")
    if not isinstance(payload, dict):
        raise SystemExit("[FAIL] Artifact file must contain a JSON object")
    return payload


def _status(ok: bool) -> str:
    return "pass" if ok else "fail"


def _safe_placeholder(value: Any) -> bool:
    return str(value).strip().lower() in SAFE_PLACEHOLDERS


def _safe_label(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}", value))


def _safe_role_label(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[a-z][a-z0-9_:-]{1,63}", value))


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _find_unsafe_values(value: Any, *, path: str = "") -> list[dict[str, str]]:
    def _scan_entry(field: str, key: Any, nested: Any) -> list[dict[str, str]]:
        key_text = str(key)
        if _key_matches(key_text, RAW_PAYLOAD_KEY_MARKERS) and nested not in (False, None):
            return [_finding(field, "raw_or_debug_payload_field_present", field_key="path")]
        if isinstance(nested, str) and _key_matches(key_text, SENSITIVE_KEY_MARKERS) and not _safe_placeholder(nested):
            return [_finding(field, "sensitive_key_contains_value", field_key="path")]
        return []

    def _scan_string(field: str, text: Any) -> list[dict[str, str]]:
        value = str(text)
        if _safe_placeholder(value):
            return []
        for reason_code, pattern in SENSITIVE_VALUE_PATTERNS:
            if pattern.search(str(value)):
                return [_finding(field, reason_code, field_key="path")]
        return []

    return scan_json_tree(
        value,
        field=path or "$",
        scan_entry=_scan_entry,
        scan_string=_scan_string,
        recurse_on_key_findings=False,
    )


def _find_launch_approval_claims(value: Any, *, path: str = "") -> list[dict[str, str]]:
    def _scan_entry(field: str, key: Any, nested: Any) -> list[dict[str, str]]:
        compact_key = _compact_key(key)
        if compact_key in {
            "launchapproved",
            "releaseapproved",
            "approvedforlaunch",
            "publiclaunchapproval",
            "publiclaunchapproved",
            "publiclaunchready",
        } and nested is True:
            return [_finding(field, "approval_boolean_not_allowed", field_key="path")]
        if compact_key in {
            "globalmfaenabled",
            "globalmfaenforced",
            "globalmfarequired",
            "mfaenforcementenabled",
            "publicmfarequired",
        } and nested is True:
            return [_finding(field, "global_mfa_enforcement_claim_not_allowed", field_key="path")]
        if compact_key in {"launchdecision", "launchstatus", "finalstatus", "releasedecision"}:
            text = str(nested).strip().lower()
            if text in {"go", "launch-approved", "launch_approved", "approved"} or LAUNCH_APPROVAL_PATTERN.search(text):
                return [_finding(field, "launch_go_claim_not_allowed", field_key="path")]
        return []

    def _scan_string(field: str, text: Any) -> list[dict[str, str]]:
        value = str(text).strip()
        if LAUNCH_APPROVAL_PATTERN.search(value):
            return [_finding(field, "launch_approved_text_not_allowed", field_key="path")]
        if GLOBAL_MFA_ENFORCEMENT_PATTERN.search(value):
            return [_finding(field, "global_mfa_enforcement_claim_not_allowed", field_key="path")]
        return []

    return scan_json_tree(
        value,
        field=path or "$",
        scan_entry=_scan_entry,
        scan_string=_scan_string,
        recurse_on_key_findings=False,
    )


def _claim_value_is_negative(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() in {
        "false",
        "no",
        "not-accepted",
        "not_accepted",
        "not accepted",
        "not-approved",
        "not_approved",
        "not approved",
    }


def _find_rbac_r5_unsafe_acceptance_claims(value: Any, *, path: str = "") -> list[dict[str, str]]:
    def _scan_entry(field: str, key: Any, nested: Any) -> list[dict[str, str]]:
        compact_key = _compact_key(key)
        if compact_key in RBAC_R5_FORBIDDEN_TRUE_KEYS and nested not in (False, None):
            if not _claim_value_is_negative(nested):
                return [_finding(field, "rbac_r5_acceptance_claim_not_allowed", field_key="path")]
        return []

    def _scan_string(field: str, text: Any) -> list[dict[str, str]]:
        if RBAC_R5_UNSAFE_ACCEPTANCE_PATTERN.search(str(text).strip()):
            return [_finding(field, "rbac_r5_accepted_or_removed_text_not_allowed", field_key="path")]
        return []

    return scan_json_tree(
        value,
        field=path or "$",
        scan_entry=_scan_entry,
        scan_string=_scan_string,
        recurse_on_key_findings=False,
    )


def _section_base_completion_issues(section_name: str, section: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(section, dict):
        return [f"{section_name}:missing"]
    for field in REQUIRED_SECTION_FIELDS:
        if field not in section:
            issues.append(f"{section_name}:{field}:missing")
    if not _safe_label(section.get("sanitizedOperator")):
        issues.append(f"{section_name}:sanitizedOperator:invalid")
    if not isinstance(section.get("timestamp"), str) or not section["timestamp"].strip():
        issues.append(f"{section_name}:timestamp:missing")
    if not _safe_label(section.get("environment")):
        issues.append(f"{section_name}:environment:invalid")
    if section.get("outcome") != "accepted":
        issues.append(f"{section_name}:outcome:not_accepted")
    controls = _string_list(section.get("sampledControls"))
    if not controls or len(controls) != len(section.get("sampledControls", [])):
        issues.append(f"{section_name}:sampledControls:invalid")
    elif not all(_safe_label(control) for control in controls):
        issues.append(f"{section_name}:sampledControls:unsafe_label")
    if not _safe_label(section.get("evidenceRedactionVersion")):
        issues.append(f"{section_name}:evidenceRedactionVersion:invalid")
    return issues


def _section_completion_issues(artifact: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for section_name in REQUIRED_SECTIONS:
        issues.extend(_section_base_completion_issues(section_name, artifact.get(section_name)))
    return issues


def _runtime_change_flags(value: Any, *, path: str = "") -> list[str]:
    def _scan_entry(field: str, key: Any, nested: Any) -> list[dict[str, str]]:
        compact_key = _compact_key(key)
        if compact_key in {"runtimebehaviorchanged", "authruntimechanged", "rbacruntimechanged"} and nested is not False:
            return [_finding(field, "runtime_change_flag_not_false", field_key="path")]
        return []

    return [
        finding["path"]
        for finding in scan_json_tree(
            value,
            field=path or "$",
            scan_entry=_scan_entry,
            recurse_on_key_findings=False,
        )
    ]


def _mfa_role_label_issues(artifact: dict[str, Any]) -> list[str]:
    section = artifact.get("mfaAdminPilot") if isinstance(artifact.get("mfaAdminPilot"), dict) else {}
    issues: list[str] = []
    role_labels = section.get("testAccountRoleLabels")
    if not isinstance(role_labels, list) or not role_labels:
        issues.append("testAccountRoleLabels:missing")
    elif not all(_safe_role_label(label) for label in role_labels):
        issues.append("testAccountRoleLabels:unsafe")
    for forbidden_key in ("testAccounts", "accounts", "users", "usernames", "emails"):
        if forbidden_key in section:
            issues.append(f"{forbidden_key}:not_allowed")
    return issues


def _rbac_fallback_off_operator_pilot_missing_fields(section: dict[str, Any]) -> list[str]:
    return [
        field
        for field in RBAC_FALLBACK_OFF_OPERATOR_PILOT_FIELDS
        if section.get(field) is not True
    ]


def _rbac_r5_observe_section_issues(section: Any) -> list[str]:
    issues = _section_base_completion_issues("rbacFallbackObserve", section)
    if not isinstance(section, dict):
        return issues
    for field in ("coarseAdminCompatibilityFallbackPresent", "fallbackObserveModeEnabled"):
        if section.get(field) is not True:
            issues.append(f"{field}:must_be_true")
    for field in (
        "fallbackOffAccepted",
        "fallbackRemoved",
        "productionLeastPrivilegeAccepted",
        "publicLaunchApproved",
        "failClosedProductionEnforcementEnabled",
    ):
        if section.get(field) is not False:
            issues.append(f"{field}:must_be_false")
    return issues


def _rbac_r5_observe_route_inventory_issues(section: dict[str, Any]) -> list[str]:
    inventory = section.get("routeInventory")
    issues: list[str] = []
    if not isinstance(inventory, dict):
        return ["routeInventory:missing"]
    if inventory.get("routeInventoryComplete") is not True:
        issues.append("routeInventoryComplete:not_true")
    if inventory.get("inventoryCurrent") is not True:
        issues.append("inventoryCurrent:not_true")
    admin_route_count = inventory.get("adminRouteCount")
    if type(admin_route_count) is not int or admin_route_count <= 0:
        issues.append("adminRouteCount:invalid")
    if inventory.get("unclassifiedAdminRouteCount") != 0:
        issues.append("unclassifiedAdminRouteCount:not_zero")
    if not _safe_label(inventory.get("sourceArtifact")):
        issues.append("sourceArtifact:invalid")
    fields = _string_list(inventory.get("requiredFieldsPresent"))
    if not fields or len(fields) != len(inventory.get("requiredFieldsPresent", [])):
        issues.append("requiredFieldsPresent:invalid")
    missing_fields = [field for field in RBAC_R5_OBSERVE_ROUTE_INVENTORY_FIELDS if field not in fields]
    if missing_fields:
        issues.append(f"requiredFieldsPresent:missing:{','.join(missing_fields)}")
    elif not all(_safe_label(field) for field in fields):
        issues.append("requiredFieldsPresent:unsafe_label")
    return issues


def _rbac_r5_observe_capability_payload_issues(section: dict[str, Any]) -> list[str]:
    proof = section.get("explicitCapabilityPayloadProof")
    issues: list[str] = []
    if not isinstance(proof, dict):
        return ["explicitCapabilityPayloadProof:missing"]
    if proof.get("proofPresent") is not True:
        issues.append("proofPresent:not_true")
    sample_count = proof.get("sampleCount")
    if type(sample_count) is not int or sample_count <= 0:
        issues.append("sampleCount:invalid")
    if proof.get("allSampledPayloadsHaveExplicitCapabilities") is not True:
        issues.append("allSampledPayloadsHaveExplicitCapabilities:not_true")
    capability_fields = _string_list(proof.get("capabilityFields"))
    if not capability_fields or len(capability_fields) != len(proof.get("capabilityFields", [])):
        issues.append("capabilityFields:invalid")
    elif not all(_safe_label(field) for field in capability_fields):
        issues.append("capabilityFields:unsafe_label")
    return issues


def _rbac_r5_observe_legacy_missing_payload_issues(section: dict[str, Any]) -> list[str]:
    evidence = section.get("legacyMissingPayloadFailClosedObserveEvidence")
    issues: list[str] = []
    if not isinstance(evidence, dict):
        return ["legacyMissingPayloadFailClosedObserveEvidence:missing"]
    for field in (
        "legacyMissingCapabilityUsersFailClosed",
        "missingCapabilityPayloadsFailClosed",
        "denialResponsesSanitized",
        "observeOnlyNoRuntimeEnforcementChange",
    ):
        if evidence.get(field) is not True:
            issues.append(f"{field}:not_true")
    return issues


def _rbac_r5_observe_rollback_issues(section: dict[str, Any]) -> list[str]:
    rollback = section.get("rollbackPosture")
    issues: list[str] = []
    if not isinstance(rollback, dict):
        return ["rollbackPosture:missing"]
    for field in ("rollbackPlanRecorded", "fallbackStillEnabled", "runtimeDefaultUnchanged"):
        if rollback.get(field) is not True:
            issues.append(f"{field}:not_true")
    if rollback.get("failClosedProductionEnforcementEnabled") is not False:
        issues.append("failClosedProductionEnforcementEnabled:not_false")
    return issues


def _rbac_r5_observe_audit_excerpt_issues(section: dict[str, Any]) -> list[str]:
    excerpts = section.get("sanitizedAuditExcerpts")
    issues: list[str] = []
    if not isinstance(excerpts, list) or not excerpts:
        return ["sanitizedAuditExcerpts:missing"]
    for index, excerpt in enumerate(excerpts):
        if not isinstance(excerpt, dict):
            issues.append(f"sanitizedAuditExcerpts[{index}]:invalid")
            continue
        for field in ("routeFamily", "requiredCapability", "actorSafeHandle", "sourceSurface", "outcome"):
            if not _safe_label(excerpt.get(field)):
                issues.append(f"sanitizedAuditExcerpts[{index}]:{field}:invalid")
        if excerpt.get("rawValuesIncluded") is not False:
            issues.append(f"sanitizedAuditExcerpts[{index}]:rawValuesIncluded:not_false")
    return issues


def _mfa_recovery_code_acceptance_missing_fields(section: dict[str, Any]) -> list[str]:
    missing = [
        field
        for field in MFA_RECOVERY_CODE_ACCEPTANCE_TRUE_FIELDS
        if section.get(field) is not True
    ]
    missing.extend(
        field
        for field in MFA_RECOVERY_CODE_ACCEPTANCE_FALSE_FIELDS
        if section.get(field) is not False
    )
    return missing


def _build_summary(artifact: dict[str, Any]) -> dict[str, Any]:
    section_issues = _section_completion_issues(artifact)
    unsafe_findings = _find_unsafe_values(artifact)
    approval_findings = _find_launch_approval_claims(artifact)
    runtime_change_findings = _runtime_change_flags(artifact)
    mfa_role_issues = _mfa_role_label_issues(artifact)
    rbac_section = artifact.get("rbacFallbackDisable") if isinstance(artifact.get("rbacFallbackDisable"), dict) else {}
    mfa_section = artifact.get("mfaAdminPilot") if isinstance(artifact.get("mfaAdminPilot"), dict) else {}
    recovery_section = artifact.get("breakGlassRecovery") if isinstance(artifact.get("breakGlassRecovery"), dict) else {}
    fallback_disabled = rbac_section.get("fallbackDisabled")
    rbac_pilot_missing_fields = _rbac_fallback_off_operator_pilot_missing_fields(rbac_section)
    recovery_missing_fields = _mfa_recovery_code_acceptance_missing_fields(recovery_section)

    checks = [
        {
            "id": "required_sections_are_complete",
            "status": _status(not section_issues),
            "evidence": {
                "requiredSections": list(REQUIRED_SECTIONS),
                "issueCount": len(section_issues),
                "issues": section_issues[:30],
            },
        },
        {
            "id": "artifact_contains_no_sensitive_or_raw_payload_values",
            "status": _status(not unsafe_findings),
            "evidence": {
                "unsafeFindingCount": len(unsafe_findings),
                "findings": unsafe_findings[:30],
                "findingValuesIncluded": False,
            },
        },
        {
            "id": "mfa_admin_pilot_uses_sanitized_role_labels",
            "status": _status(not mfa_role_issues),
            "evidence": {
                "roleLabelCount": len(_string_list(mfa_section.get("testAccountRoleLabels"))),
                "issues": mfa_role_issues[:20],
            },
        },
        {
            "id": "mfa_recovery_code_acceptance_evidence",
            "status": _status(not recovery_missing_fields),
            "evidence": {
                "missingFields": recovery_missing_fields,
                **{
                    field: recovery_section.get(field) is True
                    for field in MFA_RECOVERY_CODE_ACCEPTANCE_TRUE_FIELDS
                },
                **{
                    field: recovery_section.get(field) is False
                    for field in MFA_RECOVERY_CODE_ACCEPTANCE_FALSE_FIELDS
                },
            },
        },
        {
            "id": "rbac_fallback_disable_is_explicit",
            "status": _status(fallback_disabled is True),
            "evidence": {
                "fallbackDisabled": fallback_disabled is True,
            },
        },
        {
            "id": "rbac_fallback_off_operator_pilot_evidence",
            "status": _status(fallback_disabled is True and not rbac_pilot_missing_fields),
            "evidence": {
                "missingFields": rbac_pilot_missing_fields,
                **{field: rbac_section.get(field) is True for field in RBAC_FALLBACK_OFF_OPERATOR_PILOT_FIELDS},
            },
        },
        {
            "id": "runtime_behavior_unchanged",
            "status": _status(not runtime_change_findings),
            "evidence": {
                "changedFlagCount": len(runtime_change_findings),
                "changedFlagPaths": runtime_change_findings[:20],
            },
        },
        {
            "id": "launch_approval_claims_absent",
            "status": _status(not approval_findings),
            "evidence": {
                "claimCount": len(approval_findings),
                "claims": approval_findings[:20],
            },
        },
    ]
    failed = sum(1 for check in checks if check["status"] == "fail")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "inputSchemaVersion": str(artifact.get("schemaVersion") or INPUT_SCHEMA_VERSION),
        "profile": DEFAULT_PROFILE,
        "generatedAt": _now_iso(),
        "mode": "offline_operator_artifact_validation",
        "checkerNetworkCallsEnabled": False,
        "releaseApproved": False,
        "launchApproved": False,
        "runtimeBehaviorChanged": False,
        "checks": checks,
        "summary": {
            "total": len(checks),
            "passed": len(checks) - failed,
            "failed": failed,
        },
        "finalStatus": "EVIDENCE-READY" if failed == 0 else "NO-GO",
    }


def _build_rbac_r5_observe_summary(artifact: dict[str, Any]) -> dict[str, Any]:
    section = artifact.get("rbacFallbackObserve") if isinstance(artifact.get("rbacFallbackObserve"), dict) else {}
    section_issues = _rbac_r5_observe_section_issues(section)
    unsafe_findings = _find_unsafe_values(artifact)
    approval_findings = _find_launch_approval_claims(artifact)
    rbac_claim_findings = _find_rbac_r5_unsafe_acceptance_claims(artifact)
    runtime_change_findings = _runtime_change_flags(artifact)
    route_inventory_issues = _rbac_r5_observe_route_inventory_issues(section)
    capability_payload_issues = _rbac_r5_observe_capability_payload_issues(section)
    legacy_missing_payload_issues = _rbac_r5_observe_legacy_missing_payload_issues(section)
    rollback_issues = _rbac_r5_observe_rollback_issues(section)
    audit_excerpt_issues = _rbac_r5_observe_audit_excerpt_issues(section)

    checks = [
        {
            "id": "rbac_r5_observe_section_is_complete",
            "status": _status(not section_issues),
            "evidence": {
                "issueCount": len(section_issues),
                "issues": section_issues[:30],
                "coarseAdminCompatibilityFallbackPresent": section.get("coarseAdminCompatibilityFallbackPresent") is True,
                "fallbackObserveModeEnabled": section.get("fallbackObserveModeEnabled") is True,
                "fallbackOffAccepted": section.get("fallbackOffAccepted") is True,
                "fallbackRemoved": section.get("fallbackRemoved") is True,
                "productionLeastPrivilegeAccepted": section.get("productionLeastPrivilegeAccepted") is True,
            },
        },
        {
            "id": "artifact_contains_no_sensitive_or_raw_payload_values",
            "status": _status(not unsafe_findings),
            "evidence": {
                "unsafeFindingCount": len(unsafe_findings),
                "findings": unsafe_findings[:30],
                "findingValuesIncluded": False,
            },
        },
        {
            "id": "rbac_r5_observe_route_inventory_complete",
            "status": _status(not route_inventory_issues),
            "evidence": {
                "issues": route_inventory_issues[:20],
                "requiredFields": list(RBAC_R5_OBSERVE_ROUTE_INVENTORY_FIELDS),
            },
        },
        {
            "id": "rbac_r5_observe_explicit_capability_payload_proof",
            "status": _status(not capability_payload_issues),
            "evidence": {
                "issues": capability_payload_issues[:20],
            },
        },
        {
            "id": "rbac_r5_observe_legacy_missing_payload_fail_closed",
            "status": _status(not legacy_missing_payload_issues),
            "evidence": {
                "issues": legacy_missing_payload_issues[:20],
            },
        },
        {
            "id": "rbac_r5_observe_rollback_posture_recorded",
            "status": _status(not rollback_issues),
            "evidence": {
                "issues": rollback_issues[:20],
            },
        },
        {
            "id": "rbac_r5_observe_audit_excerpts_sanitized",
            "status": _status(not audit_excerpt_issues),
            "evidence": {
                "issues": audit_excerpt_issues[:20],
                "excerptCount": len(section.get("sanitizedAuditExcerpts", []))
                if isinstance(section.get("sanitizedAuditExcerpts"), list)
                else 0,
                "excerptValuesIncluded": False,
            },
        },
        {
            "id": "runtime_behavior_unchanged",
            "status": _status(not runtime_change_findings),
            "evidence": {
                "changedFlagCount": len(runtime_change_findings),
                "changedFlagPaths": runtime_change_findings[:20],
            },
        },
        {
            "id": "launch_approval_claims_absent",
            "status": _status(not approval_findings),
            "evidence": {
                "claimCount": len(approval_findings),
                "claims": approval_findings[:20],
            },
        },
        {
            "id": "rbac_r5_unsafe_acceptance_claims_absent",
            "status": _status(not rbac_claim_findings),
            "evidence": {
                "claimCount": len(rbac_claim_findings),
                "claims": rbac_claim_findings[:20],
            },
        },
    ]
    failed = sum(1 for check in checks if check["status"] == "fail")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "inputSchemaVersion": str(artifact.get("schemaVersion") or INPUT_SCHEMA_VERSION),
        "profile": RBAC_R5_OBSERVE_PROFILE,
        "generatedAt": _now_iso(),
        "mode": "offline_rbac_r5_fallback_observe_validation",
        "checkerNetworkCallsEnabled": False,
        "releaseApproved": False,
        "launchApproved": False,
        "fallbackOffAccepted": False,
        "fallbackRemoved": False,
        "productionLeastPrivilegeAccepted": False,
        "runtimeBehaviorChanged": False,
        "checks": checks,
        "summary": {
            "total": len(checks),
            "passed": len(checks) - failed,
            "failed": failed,
        },
        "finalStatus": "OBSERVE-EVIDENCE-READY" if failed == 0 else "NO-GO",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, help="Path to sanitized operator acceptance JSON artifact.")
    parser.add_argument(
        "--profile",
        choices=(DEFAULT_PROFILE, RBAC_R5_OBSERVE_PROFILE),
        default=DEFAULT_PROFILE,
        help="Validation profile. Use rbac-r5-observe for fallback observe-mode evidence.",
    )
    args = parser.parse_args(argv)

    artifact = _load_artifact(args.artifact)
    summary = (
        _build_rbac_r5_observe_summary(artifact)
        if args.profile == RBAC_R5_OBSERVE_PROFILE
        else _build_summary(artifact)
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["finalStatus"] in {"EVIDENCE-READY", "OBSERVE-EVIDENCE-READY"} else 1


if __name__ == "__main__":
    sys.exit(main())
