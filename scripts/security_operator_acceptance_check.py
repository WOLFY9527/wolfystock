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


SCHEMA_VERSION = "wolfystock_security_operator_acceptance_check_v1"
INPUT_SCHEMA_VERSION = "wolfystock_security_operator_acceptance_artifact_v1"
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
    ("credential_bearing_url", re.compile(r"(?i)\bhttps?://[^\s?#]+[?][^\s]+")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("provider_token", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9_]{24,}|xox[baprs]-[A-Za-z0-9-]{20,})\b")),
    ("stack_trace", re.compile(r"(?i)\b(?:traceback \(most recent call last\)|stack trace|stacktrace)\b")),
    ("debug_payload", re.compile(r"(?i)\b(?:raw|debug|provider)[_\s-]+(?:payload|request|response|body)\b")),
)
LAUNCH_APPROVAL_PATTERN = re.compile(
    r"\b(?:launch[-_\s]?approved|production[-_\s]?ready|automatic[-_\s]?go|"
    r"release[-_\s]?approved)\b",
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


def _path_join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _compact_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _key_matches(value: str, markers: tuple[str, ...]) -> bool:
    normalized = _normalized_key(value)
    compact = _compact_key(value)
    return any(marker in normalized or marker.replace("_", "") in compact for marker in markers)


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
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            nested_path = _path_join(path, key_text)
            if _key_matches(key_text, RAW_PAYLOAD_KEY_MARKERS):
                if nested not in (False, None):
                    findings.append({"path": nested_path, "reasonCode": "raw_or_debug_payload_field_present"})
                    continue
            if isinstance(nested, str) and _key_matches(key_text, SENSITIVE_KEY_MARKERS):
                if not _safe_placeholder(nested):
                    findings.append({"path": nested_path, "reasonCode": "sensitive_key_contains_value"})
                    continue
            findings.extend(_find_unsafe_values(nested, path=nested_path))
        return findings
    if isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_find_unsafe_values(nested, path=f"{path}[{index}]"))
        return findings
    if isinstance(value, str):
        if _safe_placeholder(value):
            return findings
        for reason_code, pattern in SENSITIVE_VALUE_PATTERNS:
            if pattern.search(value):
                findings.append({"path": path or "$", "reasonCode": reason_code})
                break
    return findings


def _find_launch_approval_claims(value: Any, *, path: str = "") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            nested_path = _path_join(path, key_text)
            compact_key = _compact_key(key_text)
            if compact_key in {"launchapproved", "releaseapproved", "approvedforlaunch"} and nested is True:
                findings.append({"path": nested_path, "reasonCode": "approval_boolean_not_allowed"})
                continue
            if compact_key in {"launchdecision", "launchstatus", "finalstatus", "releasedecision"}:
                text = str(nested).strip().lower()
                if text in {"go", "launch-approved", "launch_approved", "approved"} or LAUNCH_APPROVAL_PATTERN.search(text):
                    findings.append({"path": nested_path, "reasonCode": "launch_go_claim_not_allowed"})
                    continue
            findings.extend(_find_launch_approval_claims(nested, path=nested_path))
        return findings
    if isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_find_launch_approval_claims(nested, path=f"{path}[{index}]"))
        return findings
    if isinstance(value, str) and LAUNCH_APPROVAL_PATTERN.search(value.strip()):
        findings.append({"path": path or "$", "reasonCode": "launch_approved_text_not_allowed"})
    return findings


def _section_completion_issues(artifact: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for section_name in REQUIRED_SECTIONS:
        section = artifact.get(section_name)
        if not isinstance(section, dict):
            issues.append(f"{section_name}:missing")
            continue
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


def _runtime_change_flags(value: Any, *, path: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            nested_path = _path_join(path, str(key))
            compact_key = _compact_key(str(key))
            if compact_key in {"runtimebehaviorchanged", "authruntimechanged", "rbacruntimechanged"}:
                if nested is not False:
                    findings.append(nested_path)
                    continue
            findings.extend(_runtime_change_flags(nested, path=nested_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_runtime_change_flags(nested, path=f"{path}[{index}]"))
    return findings


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


def _build_summary(artifact: dict[str, Any]) -> dict[str, Any]:
    section_issues = _section_completion_issues(artifact)
    unsafe_findings = _find_unsafe_values(artifact)
    approval_findings = _find_launch_approval_claims(artifact)
    runtime_change_findings = _runtime_change_flags(artifact)
    mfa_role_issues = _mfa_role_label_issues(artifact)
    rbac_section = artifact.get("rbacFallbackDisable") if isinstance(artifact.get("rbacFallbackDisable"), dict) else {}
    mfa_section = artifact.get("mfaAdminPilot") if isinstance(artifact.get("mfaAdminPilot"), dict) else {}
    fallback_disabled = rbac_section.get("fallbackDisabled")
    rbac_pilot_missing_fields = _rbac_fallback_off_operator_pilot_missing_fields(rbac_section)

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, help="Path to sanitized operator acceptance JSON artifact.")
    args = parser.parse_args(argv)

    artifact = _load_artifact(args.artifact)
    summary = _build_summary(artifact)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["finalStatus"] == "EVIDENCE-READY" else 1


if __name__ == "__main__":
    sys.exit(main())
