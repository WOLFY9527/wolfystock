#!/usr/bin/env python3
"""Validate sanitized MFA operator evidence artifacts offline.

The checker reads one operator-sanitized JSON artifact, emits only aggregate
reason-code counts, and exits non-zero unless every required MFA evidence
category is accepted. It does not import auth runtime code, start the app,
connect to databases, call networks, read env files, or enable MFA.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from evidence_safety import finding as _finding
    from evidence_safety import normalize_key as _normalize_key
    from evidence_safety import scan_json_tree
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from scripts.evidence_safety import finding as _finding
    from scripts.evidence_safety import normalize_key as _normalize_key
    from scripts.evidence_safety import scan_json_tree


INPUT_SCHEMA_VERSION = "wolfystock_security_mfa_operator_evidence_v1"
SUMMARY_SCHEMA_VERSION = "wolfystock_security_mfa_operator_evidence_summary_v1"
REDACTION_VERSION = "security_mfa_operator_redaction_v1"

REQUIRED_CATEGORIES = (
    "mfaEnforcementPilot",
    "recoveryCodeDisplayOnce",
    "recoveryCodeHashConsumeOnce",
    "breakGlassPolicy",
    "rollbackPlan",
    "sessionStaleReauth",
)
COMMON_REQUIRED_FIELDS = (
    "environment",
    "operator",
    "observedAt",
    "outcome",
    "evidenceRedactionVersion",
    "sampledControlRefs",
    "runtimeBehaviorChanged",
)
ACCEPTED_PILOT_SCOPES = {
    "disabled",
    "admin_only",
    "admin_only_pilot",
    "narrow_admin_pilot",
    "narrow_pilot",
}
BREAK_GLASS_POLICY_STATES = {"present", "explicitly_absent"}
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

SAFE_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/@+-]{0,159}$")
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
TOTP_VALUE_PATTERNS = (
    re.compile(r"\botpauth://", re.IGNORECASE),
    re.compile(r"\b(?:totp[-_ ]?secret|mfa[-_ ]?secret|otp[-_ ]?seed)\s*[:=]\s*(?!\*{3}|redacted\b)[^\s,;&]+", re.IGNORECASE),
)
RECOVERY_CODE_VALUE_PATTERNS = (
    re.compile(r"\b(?:mfa[-_ ]?)?recovery[-_ ]?code\s*[:=]\s*(?!\*{3}|redacted\b)[^\s,;&]+", re.IGNORECASE),
    re.compile(r"\b[A-Z0-9]{4,8}(?:-[A-Z0-9]{4,8}){2,}\b"),
)
PASSWORD_HASH_VALUE_PATTERNS = (
    re.compile(r"\b(?:password|password[-_ ]?hash)\s*[:=]\s*(?!\*{3}|redacted\b)[^\s,;&]+", re.IGNORECASE),
    re.compile(r"\b(?:pbkdf2|bcrypt|scrypt|argon2)[A-Za-z0-9_$./=-]{8,}", re.IGNORECASE),
    re.compile(r"\$2[aby]\$\d{2}\$[A-Za-z0-9./]{20,}"),
    re.compile(r"\b(?:sha256|sha512)\$[A-Za-z0-9$./=-]{12,}", re.IGNORECASE),
)
SESSION_VALUE_PATTERNS = (
    re.compile(r"\bBearer\s+(?!\*{3}|redacted\b)[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    re.compile(r"\bSet-Cookie\s*:\s*[^;\s]+", re.IGNORECASE),
    re.compile(r"\b(?:cookie|session(?:[-_ ]?id)?|token)\s*[:=]\s*(?!\*{3}|redacted\b)[^\s,;&]+", re.IGNORECASE),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9_-]{12,})\b"),
)
ENV_SECRET_VALUE_PATTERNS = (
    re.compile(
        r"\b[A-Z][A-Z0-9_]*(?:SECRET|KEY|TOKEN|PASSWORD|COOKIE|SESSION)[A-Z0-9_]*\s*=\s*"
        r"(?!\*{3}|redacted\b|masked\b|missing\b|none\b)[^\s,;&]+"
    ),
)
STACK_TRACE_VALUE_PATTERNS = (
    re.compile(r"\bTraceback \(most recent call last\):", re.IGNORECASE),
    re.compile(r"\b(?:stack trace|stacktrace)\b", re.IGNORECASE),
    re.compile(r"\bFile \"[^\"]+\", line \d+, in \w+", re.IGNORECASE),
)
GLOBAL_MFA_APPROVAL_PATTERN = re.compile(
    r"\b(?:global|all[-_ ]?users?|production|public)\b.{0,60}\bMFA\b.{0,60}\b"
    r"(?:approved|required|enabled|enforced|ready|go)\b|"
    r"\bMFA\b.{0,60}\b(?:approved|required|enabled|enforced|ready|go)\b.{0,60}"
    r"\b(?:global|all[-_ ]?users?|production|public)\b",
    re.IGNORECASE,
)

TOTP_SECRET_KEYS = {"totpsecret", "mfasecret", "otpseed", "otpauthuri"}
RECOVERY_CODE_KEYS = {"recoverycode", "mfarecoverycode"}
PASSWORD_HASH_KEYS = {
    "password",
    "passwordhash",
    "mfarecoverycodeshash",
    "recoverycodehash",
    "hashedrecoverycodes",
}
SESSION_SECRET_KEYS = {"authorization", "bearer", "cookie", "setcookie", "sessionid", "token"}
ENV_SECRET_KEYS = {"envsecretvalue", "envvalue", "environmentsecretvalue"}
STACK_TRACE_KEYS = {"stacktrace", "traceback"}


def _safe_placeholder(value: Any) -> bool:
    return str(value or "").strip().lower() in SAFE_PLACEHOLDERS


def _safe_label(value: Any) -> bool:
    return isinstance(value, str) and bool(SAFE_LABEL_PATTERN.fullmatch(value))


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _compact_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _is_non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _safe_label_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_safe_label(item) for item in value)


def _unmasked_email(value: str) -> bool:
    for match in EMAIL_PATTERN.finditer(value):
        address = match.group(0)
        if "*" not in address and "redacted" not in address.lower() and "masked" not in address.lower():
            return True
    return False


def _scan_key(field: str, key: Any) -> list[dict[str, str]]:
    normalized = _normalize_key(key)
    compact = _compact_key(key)
    findings: list[dict[str, str]] = []
    if compact in STACK_TRACE_KEYS or normalized in {"stack_trace", "debug_trace"}:
        findings.append(_finding(field, "stack_trace_forbidden"))
    return findings


def _scan_entry(field: str, key: Any, value: Any) -> list[dict[str, str]]:
    if _safe_placeholder(value):
        return []
    compact = _compact_key(key)
    normalized = _normalize_key(key)
    if compact in TOTP_SECRET_KEYS:
        return [_finding(field, "raw_totp_secret_forbidden")]
    if compact in RECOVERY_CODE_KEYS:
        return [_finding(field, "raw_recovery_code_forbidden")]
    if compact in PASSWORD_HASH_KEYS:
        return [_finding(field, "raw_password_or_hash_forbidden")]
    if compact in SESSION_SECRET_KEYS or normalized in {"session_id", "cookie_header"}:
        return [_finding(field, "raw_session_cookie_or_token_forbidden")]
    if compact in ENV_SECRET_KEYS:
        return [_finding(field, "env_secret_value_forbidden")]
    if compact in STACK_TRACE_KEYS:
        return [_finding(field, "stack_trace_forbidden")]
    return []


def _scan_string(field: str, value: str) -> list[dict[str, str]]:
    if _safe_placeholder(value):
        return []
    findings: list[dict[str, str]] = []
    if any(pattern.search(value) for pattern in TOTP_VALUE_PATTERNS):
        findings.append(_finding(field, "raw_totp_secret_forbidden"))
    if any(pattern.search(value) for pattern in RECOVERY_CODE_VALUE_PATTERNS):
        findings.append(_finding(field, "raw_recovery_code_forbidden"))
    if any(pattern.search(value) for pattern in PASSWORD_HASH_VALUE_PATTERNS):
        findings.append(_finding(field, "raw_password_or_hash_forbidden"))
    if any(pattern.search(value) for pattern in SESSION_VALUE_PATTERNS):
        findings.append(_finding(field, "raw_session_cookie_or_token_forbidden"))
    if any(pattern.search(value) for pattern in ENV_SECRET_VALUE_PATTERNS):
        findings.append(_finding(field, "env_secret_value_forbidden"))
    if any(pattern.search(value) for pattern in STACK_TRACE_VALUE_PATTERNS):
        findings.append(_finding(field, "stack_trace_forbidden"))
    if _unmasked_email(value):
        findings.append(_finding(field, "unmasked_email_forbidden"))
    if GLOBAL_MFA_APPROVAL_PATTERN.search(value):
        findings.append(_finding(field, "global_mfa_approval_claim_forbidden"))
    return findings


def _scan_tree(payload: Any) -> list[dict[str, str]]:
    return scan_json_tree(
        payload,
        scan_key=_scan_key,
        scan_entry=_scan_entry,
        scan_string=_scan_string,
    )


def _common_section_findings(category_id: str, section: Any) -> tuple[dict[str, Any], list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    missing_fields: list[str] = []
    if not isinstance(section, dict):
        return (
            {
                "id": category_id,
                "status": "blocking",
                "missingFields": list(COMMON_REQUIRED_FIELDS),
                "reasonCodes": ["invalid_category"],
            },
            [_finding(category_id, "invalid_category")],
        )

    for field_name in COMMON_REQUIRED_FIELDS:
        if field_name not in section:
            missing_fields.append(field_name)
            findings.append(_finding(f"{category_id}.{field_name}", "missing_required_field"))

    if "environment" in section and not _safe_label(section.get("environment")):
        findings.append(_finding(f"{category_id}.environment", "invalid_safe_label"))
    if "operator" in section and not _safe_label(section.get("operator")):
        findings.append(_finding(f"{category_id}.operator", "invalid_safe_label"))
    if "observedAt" in section and not _valid_timestamp(section.get("observedAt")):
        findings.append(_finding(f"{category_id}.observedAt", "invalid_observed_at"))
    if "outcome" in section and section.get("outcome") != "accepted":
        findings.append(_finding(f"{category_id}.outcome", "outcome_not_accepted"))
    if "evidenceRedactionVersion" in section and section.get("evidenceRedactionVersion") != REDACTION_VERSION:
        findings.append(_finding(f"{category_id}.evidenceRedactionVersion", "invalid_redaction_version"))
    if "sampledControlRefs" in section and not _safe_label_list(section.get("sampledControlRefs")):
        findings.append(_finding(f"{category_id}.sampledControlRefs", "invalid_sampled_control_refs"))
    if "runtimeBehaviorChanged" in section and section.get("runtimeBehaviorChanged") is not False:
        findings.append(_finding(f"{category_id}.runtimeBehaviorChanged", "runtime_behavior_change_forbidden"))

    return (
        {
            "id": category_id,
            "missingFields": missing_fields,
        },
        findings,
    )


def _require_bool_true(section: dict[str, Any], category_id: str, field_name: str) -> list[dict[str, str]]:
    if section.get(field_name) is not True:
        return [_finding(f"{category_id}.{field_name}", "required_true_evidence_missing")]
    return []


def _require_bool_false(section: dict[str, Any], category_id: str, field_name: str, reason_code: str) -> list[dict[str, str]]:
    if section.get(field_name) is not False:
        return [_finding(f"{category_id}.{field_name}", reason_code)]
    return []


def _require_safe_ref(section: dict[str, Any], category_id: str, field_name: str) -> list[dict[str, str]]:
    if not _safe_label(section.get(field_name)):
        return [_finding(f"{category_id}.{field_name}", "evidence_ref_missing_or_unsafe")]
    return []


def _category_specific_findings(category_id: str, section: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if category_id == "mfaEnforcementPilot":
        pilot_scope = str(section.get("pilotScope") or "")
        findings.extend(
            _require_bool_false(
                section,
                category_id,
                "enabledByDefault",
                "mfa_enforcement_must_remain_disabled_by_default",
            )
        )
        findings.extend(
            _require_bool_false(
                section,
                category_id,
                "globalMfaRequired",
                "global_mfa_rollout_not_allowed",
            )
        )
        if pilot_scope not in ACCEPTED_PILOT_SCOPES:
            findings.append(_finding(f"{category_id}.pilotScope", "pilot_scope_not_disabled_or_narrow"))
        if pilot_scope != "disabled" and not _safe_label_list(section.get("pilotAccountLabels")):
            findings.append(_finding(f"{category_id}.pilotAccountLabels", "narrow_pilot_labels_missing"))
        findings.extend(_require_safe_ref(section, category_id, "pilotEvidenceRef"))
        if section.get("enabledByDefault") is True or section.get("globalMfaRequired") is True:
            findings.append(_finding(category_id, "global_mfa_rollout_not_allowed"))
    elif category_id == "recoveryCodeDisplayOnce":
        findings.extend(_require_bool_true(section, category_id, "displayOnceVerified"))
        findings.extend(
            _require_bool_false(
                section,
                category_id,
                "plaintextStoredAfterDisplay",
                "recovery_plaintext_storage_forbidden",
            )
        )
        findings.extend(_require_safe_ref(section, category_id, "displayOnceEvidenceRef"))
    elif category_id == "recoveryCodeHashConsumeOnce":
        findings.extend(_require_bool_true(section, category_id, "hashStorageVerified"))
        findings.extend(_require_bool_true(section, category_id, "consumeOnceVerified"))
        findings.extend(_require_bool_true(section, category_id, "replayDeniedVerified"))
        findings.extend(_require_safe_ref(section, category_id, "hashConsumeEvidenceRef"))
    elif category_id == "breakGlassPolicy":
        if section.get("policyState") not in BREAK_GLASS_POLICY_STATES:
            findings.append(_finding(f"{category_id}.policyState", "break_glass_policy_state_missing"))
        findings.extend(
            _require_bool_false(
                section,
                category_id,
                "breakGlassEnabledByDefault",
                "break_glass_default_on_forbidden",
            )
        )
        findings.extend(_require_safe_ref(section, category_id, "evidenceRef"))
    elif category_id == "rollbackPlan":
        findings.extend(_require_bool_true(section, category_id, "rollbackPlanPresent"))
        findings.extend(_require_bool_true(section, category_id, "rollbackSwitchIdentified"))
        findings.extend(_require_safe_ref(section, category_id, "rollbackEvidenceRef"))
    elif category_id == "sessionStaleReauth":
        findings.extend(_require_bool_true(section, category_id, "staleSessionDeniedVerified"))
        findings.extend(_require_bool_true(section, category_id, "recentReauthRequiredVerified"))
        findings.extend(_require_safe_ref(section, category_id, "sessionEvidenceRef"))
    return findings


def _validate_category(category_id: str, section: Any) -> tuple[dict[str, Any], list[dict[str, str]]]:
    category, findings = _common_section_findings(category_id, section)
    if isinstance(section, dict):
        findings.extend(_category_specific_findings(category_id, section))
    reason_codes = sorted({finding["reasonCode"] for finding in findings})
    category["status"] = "accepted" if not findings else "blocking"
    category["reasonCodes"] = reason_codes
    return category, findings


def _dedupe_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        {json.dumps(finding, sort_keys=True): finding for finding in findings}.values(),
        key=lambda item: (item["field"], item["reasonCode"]),
    )


def _reason_code_counts(findings: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        reason_code = finding["reasonCode"]
        counts[reason_code] = counts.get(reason_code, 0) + 1
    return dict(sorted(counts.items()))


def _reason_code_summaries(counts: dict[str, int]) -> list[dict[str, Any]]:
    return [{"reasonCode": reason_code, "count": count} for reason_code, count in counts.items()]


def validate_artifact(payload: Any) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    categories: list[dict[str, Any]] = []

    if not isinstance(payload, dict):
        findings.append(_finding("$", "invalid_json_object"))
        payload = {}

    if payload.get("schemaVersion") != INPUT_SCHEMA_VERSION:
        findings.append(_finding("schemaVersion", "invalid_schema_version"))

    for category_id in REQUIRED_CATEGORIES:
        if category_id not in payload:
            categories.append(
                {
                    "id": category_id,
                    "status": "blocking",
                    "missingFields": list(COMMON_REQUIRED_FIELDS),
                    "reasonCodes": ["missing_required_category"],
                }
            )
            findings.append(_finding(category_id, "missing_required_category"))
            continue
        category, category_findings = _validate_category(category_id, payload[category_id])
        categories.append(category)
        findings.extend(category_findings)

    findings.extend(_scan_tree(payload))
    deduped_findings = _dedupe_findings(findings)

    accepted_categories = sum(1 for category in categories if category["status"] == "accepted")
    blocking_categories = len(categories) - accepted_categories
    passed = not deduped_findings and blocking_categories == 0
    reason_codes = {finding["reasonCode"] for finding in deduped_findings}
    counts_by_reason_code = _reason_code_counts(deduped_findings)

    return {
        "schemaVersion": SUMMARY_SCHEMA_VERSION,
        "tool": "scripts/security_mfa_operator_evidence_check.py",
        "inputSchemaVersion": str(payload.get("schemaVersion") or "") if isinstance(payload, dict) else "",
        "status": "pass" if passed else "fail",
        "finalStatus": "EVIDENCE-READY" if passed else "NO-GO",
        "offlineOnly": True,
        "advisoryOnly": True,
        "launchApproved": False,
        "releaseApproved": False,
        "networkCallsExecutedByValidator": False,
        "databaseConnectionsExecutedByValidator": False,
        "appStartupExecutedByValidator": False,
        "runtimeBehaviorChanged": False,
        "authRuntimeBehaviorChanged": False,
        "globalMfaEnabledByValidator": False,
        "rawSecretsIncluded": False,
        "checks": {
            "requiredCategoriesPresent": not any(
                finding["reasonCode"] == "missing_required_category" for finding in deduped_findings
            ),
            "mfaPilotDisabledOrNarrow": not any(
                finding["reasonCode"]
                in {
                    "mfa_enforcement_must_remain_disabled_by_default",
                    "global_mfa_rollout_not_allowed",
                    "pilot_scope_not_disabled_or_narrow",
                    "narrow_pilot_labels_missing",
                }
                for finding in deduped_findings
            ),
            "recoveryCodeDisplayOnceEvidencePresent": not any(
                finding["field"].startswith("recoveryCodeDisplayOnce.") for finding in deduped_findings
            ),
            "recoveryCodeHashConsumeOnceEvidencePresent": not any(
                finding["field"].startswith("recoveryCodeHashConsumeOnce")
                or finding["field"] == "recoveryCodeHashConsumeOnce"
                for finding in deduped_findings
            ),
            "breakGlassPolicyRecorded": not any(
                finding["field"].startswith("breakGlassPolicy") for finding in deduped_findings
            ),
            "rollbackPlanEvidencePresent": not any(
                finding["field"].startswith("rollbackPlan") for finding in deduped_findings
            ),
            "sessionStaleReauthEvidencePresent": not any(
                finding["field"].startswith("sessionStaleReauth") for finding in deduped_findings
            ),
            "sensitiveValuesAbsent": not any(
                reason_code
                in {
                    "raw_totp_secret_forbidden",
                    "raw_recovery_code_forbidden",
                    "raw_password_or_hash_forbidden",
                    "raw_session_cookie_or_token_forbidden",
                    "unmasked_email_forbidden",
                    "env_secret_value_forbidden",
                    "stack_trace_forbidden",
                }
                for reason_code in reason_codes
            ),
            "globalMfaApprovalClaimsAbsent": "global_mfa_approval_claim_forbidden" not in reason_codes,
        },
        "summary": {
            "acceptedCategories": accepted_categories,
            "blockingCategories": blocking_categories,
            "findingCount": len(deduped_findings),
            "countsByReasonCode": counts_by_reason_code,
        },
        "blockingReasonSummaries": _reason_code_summaries(counts_by_reason_code),
        "categories": categories,
        "sanitization": {
            "findingDetailsIncluded": False,
            "rawTotpSecretsIncluded": False,
            "rawRecoveryCodesIncluded": False,
            "rawPasswordsOrHashesIncluded": False,
            "rawSessionCookiesOrTokensIncluded": False,
            "unmaskedEmailsIncluded": False,
            "envSecretValuesIncluded": False,
            "stackTracesIncluded": False,
            "runtimeDefaultsChanged": False,
        },
    }


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", nargs="?", help="Sanitized MFA operator evidence JSON artifact.")
    parser.add_argument("--artifact", dest="artifact_flag", help="Sanitized MFA operator evidence JSON artifact.")
    args = parser.parse_args(argv)
    artifact_arg = args.artifact_flag or args.artifact
    if not artifact_arg:
        parser.error("an evidence artifact path is required")

    artifact_path = Path(artifact_arg)
    try:
        payload = _load_json(artifact_path)
    except (OSError, json.JSONDecodeError):
        summary = validate_artifact({})
        counts_by_reason_code = dict(summary["summary"]["countsByReasonCode"])
        counts_by_reason_code["artifact_read_failed"] = counts_by_reason_code.get("artifact_read_failed", 0) + 1
        counts_by_reason_code = dict(sorted(counts_by_reason_code.items()))
        summary["summary"]["findingCount"] = int(summary["summary"]["findingCount"]) + 1
        summary["summary"]["countsByReasonCode"] = counts_by_reason_code
        summary["blockingReasonSummaries"] = _reason_code_summaries(counts_by_reason_code)
        summary["status"] = "fail"
        summary["finalStatus"] = "NO-GO"
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 1

    summary = validate_artifact(payload)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
