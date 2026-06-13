#!/usr/bin/env python3
"""Validate sanitized production/staging config snapshot evidence offline.

The checker reads one operator-supplied JSON artifact and emits a sanitized
summary. It does not read environment variables, inspect deployment state, call
external services, or import runtime config modules.
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


SUMMARY_SCHEMA_VERSION = "wolfystock_config_snapshot_evidence_summary_v1"
ALLOWED_ENVIRONMENTS = {"staging", "production-like-staging", "production-review"}
ALLOWED_SECRET_PRESENCE = {"configured", "missing", "redacted only"}
ALLOWED_OUTCOMES = {"accepted", "rejected", "needs-review"}
ALLOWED_MANUAL_REVIEW_STATUSES = {"accepted", "rejected", "needs-review"}
POSTURE_EVIDENCE_FIELD = "postureEvidence"
MANUAL_REVIEW_FIELD = "manualReview"
REQUIRED_FIELDS = (
    "artifactVersion",
    "environment",
    "operator",
    "observedAt",
    "authConfigSummary",
    "providerConfigSummary",
    "quotaConfigSummary",
    "notificationConfigSummary",
    "databaseConfigSummary",
    "loggingRetentionSummary",
    "rollbackConfigSummary",
    "secretPresenceSummary",
    "unsafeDefaultsSummary",
    POSTURE_EVIDENCE_FIELD,
    MANUAL_REVIEW_FIELD,
    "releaseApproved",
    "publicLaunchReady",
    "outcome",
    "evidenceRedactionVersion",
)
CRITICAL_ACCEPTED_SUMMARIES = (
    "authConfigSummary",
    "providerConfigSummary",
    "quotaConfigSummary",
    "databaseConfigSummary",
)
REQUIRED_POSTURE_FIELDS = (
    "targetEnvironmentLabel",
    "productionMode",
    "authEnabled",
    "corsPosture",
    "csrfPosture",
    "trustedProxyPosture",
    "mfaEnforcementScope",
    "rbacFallbackPosture",
    "quotaMode",
    "backupPitrOptIn",
    "stagingIngressOptIn",
    "publicSearxngInstancePosture",
    "cryptoRealtimeDecisionPosture",
    "providerCredentialPresenceStates",
)
REQUIRED_PROVIDER_CREDENTIAL_GROUPS = (
    "llmProvider",
    "marketDataProvider",
    "optionsLiveProvider",
)
ALLOWED_POSTURE_VALUES = {
    "productionMode": {"production", "production-like-staging", "non-production", "needs-review"},
    "authEnabled": {"enabled", "disabled", "needs-review"},
    "corsPosture": {"restricted-origins", "allow-all", "needs-review"},
    "csrfPosture": {"trusted-origins-configured", "not-configured", "needs-review"},
    "trustedProxyPosture": {"explicit", "disabled", "needs-review"},
    "mfaEnforcementScope": {"disabled", "admin-only", "global", "needs-review"},
    "rbacFallbackPosture": {"disabled", "compatibility-enabled", "needs-review"},
    "quotaMode": {"disabled", "advisory", "pilot", "enforced", "needs-review"},
    "backupPitrOptIn": {"disabled", "enabled", "needs-review"},
    "stagingIngressOptIn": {"disabled", "enabled", "needs-review"},
    "publicSearxngInstancePosture": {"disabled", "enabled", "needs-review"},
    "cryptoRealtimeDecisionPosture": {"disabled", "enabled", "needs-review"},
}
RAW_CONFIG_KEY_MARKERS = (
    "config_dump",
    "configdump",
    "dotenv",
    "env_dump",
    "envdump",
    "environment_dump",
    "environmentdump",
    "raw_config",
    "rawconfig",
    "raw_env",
    "rawenv",
)
SECRET_KEY_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "database_url",
    "db_url",
    "dsn",
    "password",
    "passwd",
    "private_key",
    "secret",
    "session",
    "set_cookie",
    "token",
    "webhook",
)
RAW_PAYLOAD_KEY_MARKERS = (
    "debug_payload",
    "debug_trace",
    "raw_payload",
    "raw_request",
    "raw_request_body",
    "raw_response",
    "raw_response_body",
    "stack_trace",
    "traceback",
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"\b[A-Z][A-Z0-9_]{2,}\s*=\s*[^\s#]+"),
    re.compile(
        r"\b(?:api[_-]?key|apikey|token|secret|password|passwd|cookie|session)\s*[:=]\s*[^\s,;&]+",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb|redis)://[^:\s/@]+:[^@\s]+@[^\s]+", re.IGNORECASE),
    re.compile(r"\bhttps?://[^/\s:@]+:[^@\s]+@[^\s]+", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
RAW_URL_PATTERN = re.compile(r"\bhttps?://[^\s\"'<>]+", re.IGNORECASE)
PRIVATE_HOST_PATTERN = re.compile(
    r"\b(?:"
    r"localhost|"
    r"127\.0\.0\.1|"
    r"10\.(?:\d{1,3}\.){2}\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?:internal|local|corp|lan)"
    r")\b",
    re.IGNORECASE,
)
STACK_TRACE_PATTERN = re.compile(
    r"Traceback \(most recent call last\)|\b(?:Exception|Error):\s+.+\bat\s+",
    re.IGNORECASE,
)
RAW_CONFIG_VALUE_PATTERN = re.compile(
    r"\b(?:raw\s+)?(?:env|dotenv|environment|config)\s+dump\b|\.env\s+dump|raw\s+config\s+dump",
    re.IGNORECASE,
)
LAUNCH_APPROVAL_PATTERN = re.compile(
    r"(?<!NO-)\bGO\b|launch[-_\s]?approved|release[-_\s]?approved|production[-_\s]?ready|public launch approved",
    re.IGNORECASE,
)
ENV_VAR_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_observed_at(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _scan_key(field: str, key: object) -> list[dict[str, str]]:
    key_text = str(key or "")
    normalized = _normalize_key(key)
    findings: list[dict[str, str]] = []
    if normalized in {"secretpresencesummary", "providercredentialpresencestates"}:
        return findings
    if ENV_VAR_KEY_PATTERN.fullmatch(key_text):
        findings.append(_finding(field, "raw_config_dump_forbidden"))
    if any(marker in normalized for marker in RAW_CONFIG_KEY_MARKERS):
        findings.append(_finding(field, "raw_config_dump_forbidden"))
    elif any(marker in normalized for marker in RAW_PAYLOAD_KEY_MARKERS):
        findings.append(_finding(field, "raw_payload_forbidden"))
    elif any(marker in normalized for marker in SECRET_KEY_MARKERS):
        findings.append(_finding(field, "secret_like_value_detected"))
    return findings


def _scan_string(field: str, value: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
        findings.append(_finding(field, "secret_like_value_detected"))
    if RAW_URL_PATTERN.search(value):
        findings.append(_finding(field, "raw_url_forbidden"))
    if PRIVATE_HOST_PATTERN.search(value):
        findings.append(_finding(field, "private_hostname_forbidden"))
    if STACK_TRACE_PATTERN.search(value):
        findings.append(_finding(field, "stack_trace_forbidden"))
    if RAW_CONFIG_VALUE_PATTERN.search(value):
        findings.append(_finding(field, "raw_config_dump_forbidden"))
    if LAUNCH_APPROVAL_PATTERN.search(value):
        findings.append(_finding(field, "launch_approval_claim_forbidden"))
    return findings


def _scan_tree(value: Any) -> list[dict[str, str]]:
    return scan_json_tree(value, scan_key=_scan_key, scan_string=_scan_string)


def _field_path(*parts: str) -> str:
    return ".".join(parts)


def _normalized_label(value: object) -> str:
    return str(value or "").strip().lower()


def _validate_false_flag(
    findings: list[dict[str, str]],
    artifact: dict[str, Any],
    field: str,
    reason_code: str,
) -> bool:
    if artifact.get(field) is False:
        return True
    findings.append(_finding(field, reason_code))
    return False


def _validate_manual_review(artifact: dict[str, Any], findings: list[dict[str, str]]) -> bool:
    section = artifact.get(MANUAL_REVIEW_FIELD)
    if not isinstance(section, dict):
        findings.append(_finding(MANUAL_REVIEW_FIELD, "invalid_manual_review"))
        return False

    valid = True
    status = _normalized_label(section.get("status"))
    if status not in ALLOWED_MANUAL_REVIEW_STATUSES:
        findings.append(_finding(_field_path(MANUAL_REVIEW_FIELD, "status"), "invalid_manual_review_status"))
        valid = False
    if not _non_empty_string(section.get("reviewTicketRef")):
        findings.append(_finding(_field_path(MANUAL_REVIEW_FIELD, "reviewTicketRef"), "invalid_string_field"))
        valid = False
    if section.get("targetEnvironmentEvidenceRequired") is not True:
        findings.append(
            _finding(
                _field_path(MANUAL_REVIEW_FIELD, "targetEnvironmentEvidenceRequired"),
                "target_environment_evidence_required",
            )
        )
        valid = False
    return valid


def _validate_posture_evidence(artifact: dict[str, Any], findings: list[dict[str, str]]) -> tuple[bool, bool]:
    section = artifact.get(POSTURE_EVIDENCE_FIELD)
    if not isinstance(section, dict):
        findings.append(_finding(POSTURE_EVIDENCE_FIELD, "invalid_posture_evidence"))
        return False, False

    complete = True
    resolved = True
    for field in REQUIRED_POSTURE_FIELDS:
        if field not in section:
            findings.append(_finding(_field_path(POSTURE_EVIDENCE_FIELD, field), "missing_required_field"))
            complete = False
            resolved = False

    if not _non_empty_string(section.get("targetEnvironmentLabel")):
        findings.append(_finding(_field_path(POSTURE_EVIDENCE_FIELD, "targetEnvironmentLabel"), "invalid_string_field"))
        complete = False
        resolved = False

    for field, allowed in ALLOWED_POSTURE_VALUES.items():
        if field not in section:
            continue
        value = _normalized_label(section.get(field))
        if value not in allowed:
            findings.append(_finding(_field_path(POSTURE_EVIDENCE_FIELD, field), "invalid_posture_value"))
            complete = False
            resolved = False
        elif value == "needs-review":
            resolved = False

    provider_states = section.get("providerCredentialPresenceStates")
    if not isinstance(provider_states, dict):
        findings.append(
            _finding(
                _field_path(POSTURE_EVIDENCE_FIELD, "providerCredentialPresenceStates"),
                "invalid_provider_credential_presence_states",
            )
        )
        return complete and False, False

    for group in REQUIRED_PROVIDER_CREDENTIAL_GROUPS:
        field_path = _field_path(POSTURE_EVIDENCE_FIELD, "providerCredentialPresenceStates", group)
        if group not in provider_states:
            findings.append(_finding(field_path, "missing_required_field"))
            complete = False
            resolved = False
            continue
        state = _normalized_label(provider_states.get(group))
        if state not in {"configured", "missing", "redacted only", "needs-review"}:
            findings.append(_finding(field_path, "invalid_provider_credential_presence_state"))
            complete = False
            resolved = False
        elif state == "needs-review":
            resolved = False

    return complete, resolved


def _validate_artifact(artifact: Any) -> tuple[list[dict[str, str]], dict[str, bool]]:
    findings: list[dict[str, str]] = []
    checks = {
        "requiredFieldsPresent": False,
        "schemaValuesValid": False,
        "unsafeContentAbsent": False,
        "acceptedOutcomeHasCriticalSummaries": False,
        "postureEvidenceComplete": False,
        "manualReviewStatusValid": False,
        "acceptedOutcomeHasResolvedPostureEvidence": False,
        "releaseApprovedFalse": False,
        "publicLaunchReadyFalse": False,
    }
    if not isinstance(artifact, dict):
        return [_finding("$", "artifact_must_be_json_object")], checks

    for field in REQUIRED_FIELDS:
        if field not in artifact:
            findings.append(_finding(field, "missing_required_field"))

    text_fields = (
        "artifactVersion",
        "operator",
        "authConfigSummary",
        "providerConfigSummary",
        "quotaConfigSummary",
        "notificationConfigSummary",
        "databaseConfigSummary",
        "loggingRetentionSummary",
        "rollbackConfigSummary",
        "unsafeDefaultsSummary",
        "evidenceRedactionVersion",
    )
    for field in text_fields:
        if field in artifact and not _non_empty_string(artifact.get(field)):
            findings.append(_finding(field, "invalid_string_field"))

    if artifact.get("environment") not in ALLOWED_ENVIRONMENTS:
        findings.append(_finding("environment", "invalid_environment"))
    if artifact.get("secretPresenceSummary") not in ALLOWED_SECRET_PRESENCE:
        findings.append(_finding("secretPresenceSummary", "invalid_secret_presence_summary"))
    if artifact.get("outcome") not in ALLOWED_OUTCOMES:
        findings.append(_finding("outcome", "invalid_outcome"))
    if "observedAt" in artifact and not _valid_observed_at(artifact.get("observedAt")):
        findings.append(_finding("observedAt", "invalid_observed_at"))

    missing_critical = [
        field for field in CRITICAL_ACCEPTED_SUMMARIES if not _non_empty_string(artifact.get(field))
    ]
    if artifact.get("outcome") == "accepted" and missing_critical:
        findings.append(_finding("outcome", "accepted_missing_critical_summary"))

    posture_complete, posture_resolved = _validate_posture_evidence(artifact, findings)
    manual_review_valid = _validate_manual_review(artifact, findings)
    release_approved_false = _validate_false_flag(
        findings,
        artifact,
        "releaseApproved",
        "release_approval_forbidden",
    )
    public_launch_ready_false = _validate_false_flag(
        findings,
        artifact,
        "publicLaunchReady",
        "public_launch_ready_forbidden",
    )
    manual_review_status = ""
    if isinstance(artifact.get(MANUAL_REVIEW_FIELD), dict):
        manual_review_status = _normalized_label(artifact[MANUAL_REVIEW_FIELD].get("status"))
    accepted_posture_ok = artifact.get("outcome") != "accepted" or (
        posture_complete and posture_resolved and manual_review_status == "accepted"
    )
    if not accepted_posture_ok:
        findings.append(_finding("outcome", "accepted_missing_posture_evidence"))

    findings.extend(_scan_tree(artifact))
    checks["requiredFieldsPresent"] = not any(
        finding["reasonCode"] == "missing_required_field" for finding in findings
    )
    checks["schemaValuesValid"] = not any(
        finding["reasonCode"].startswith("invalid_") for finding in findings
    )
    checks["unsafeContentAbsent"] = not any(
        finding["reasonCode"]
        in {
            "launch_approval_claim_forbidden",
            "raw_config_dump_forbidden",
            "raw_payload_forbidden",
            "raw_url_forbidden",
            "secret_like_value_detected",
            "private_hostname_forbidden",
            "stack_trace_forbidden",
        }
        for finding in findings
    )
    checks["acceptedOutcomeHasCriticalSummaries"] = not (
        artifact.get("outcome") == "accepted" and missing_critical
    )
    checks["postureEvidenceComplete"] = posture_complete
    checks["manualReviewStatusValid"] = manual_review_valid
    checks["acceptedOutcomeHasResolvedPostureEvidence"] = accepted_posture_ok
    checks["releaseApprovedFalse"] = release_approved_false
    checks["publicLaunchReadyFalse"] = public_launch_ready_false
    return findings, checks


def _sanitized_artifact_summary(artifact: Any) -> dict[str, str]:
    if not isinstance(artifact, dict):
        return {}
    return {
        "artifactVersion": str(artifact.get("artifactVersion") or "<missing>"),
        "environment": str(artifact.get("environment") or "<missing>"),
        "operator": str(artifact.get("operator") or "<missing>"),
        "observedAt": str(artifact.get("observedAt") or "<missing>"),
        "secretPresenceSummary": str(artifact.get("secretPresenceSummary") or "<missing>"),
        "outcome": str(artifact.get("outcome") or "<missing>"),
        "manualReviewStatus": str(
            artifact.get(MANUAL_REVIEW_FIELD, {}).get("status")
            if isinstance(artifact.get(MANUAL_REVIEW_FIELD), dict)
            else "<missing>"
        ),
        "evidenceRedactionVersion": str(artifact.get("evidenceRedactionVersion") or "<missing>"),
    }


def validate_config_snapshot_evidence(artifact: Any) -> dict[str, Any]:
    findings, checks = _validate_artifact(artifact)
    passed = not findings
    return {
        "schemaVersion": SUMMARY_SCHEMA_VERSION,
        "status": "pass" if passed else "fail",
        "finalStatus": "EVIDENCE-READY" if passed else "EVIDENCE-BLOCKED",
        "advisoryOnly": True,
        "runtimeBehaviorChanged": False,
        "releaseApproved": False,
        "publicLaunchReady": False,
        "launchAcceptanceIntegrated": False,
        "networkCallsExecutedByValidator": False,
        "externalServicesCalledByValidator": False,
        "realEnvReadByValidator": False,
        "deploymentStateReadByValidator": False,
        "secretValuesPrintedByValidator": False,
        "checks": checks,
        "artifact": _sanitized_artifact_summary(artifact),
        "findings": findings,
    }


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"[FAIL] Evidence file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[FAIL] Evidence file is not valid JSON: {exc}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a sanitized config snapshot evidence JSON artifact offline."
    )
    parser.add_argument("artifact", help="Path to sanitized config snapshot evidence JSON")
    args = parser.parse_args(argv)

    artifact = _load_json(Path(args.artifact))
    result = validate_config_snapshot_evidence(artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
