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


SUMMARY_SCHEMA_VERSION = "wolfystock_config_snapshot_evidence_summary_v1"
ALLOWED_ENVIRONMENTS = {"staging", "production-like-staging", "production-review"}
ALLOWED_SECRET_PRESENCE = {"configured", "missing", "redacted only"}
ALLOWED_OUTCOMES = {"accepted", "rejected", "needs-review"}
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
    "outcome",
    "evidenceRedactionVersion",
)
CRITICAL_ACCEPTED_SUMMARIES = (
    "authConfigSummary",
    "providerConfigSummary",
    "quotaConfigSummary",
    "databaseConfigSummary",
)
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
RAW_CONFIG_VALUE_PATTERN = re.compile(
    r"\b(?:raw\s+)?(?:env|dotenv|environment|config)\s+dump\b|\.env\s+dump|raw\s+config\s+dump",
    re.IGNORECASE,
)
LAUNCH_APPROVAL_PATTERN = re.compile(
    r"\bGO\b|launch[-_\s]?approved|release[-_\s]?approved|production[-_\s]?ready|public launch approved",
    re.IGNORECASE,
)
ENV_VAR_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")


def _finding(field: str, reason_code: str) -> dict[str, str]:
    return {"field": field, "reasonCode": reason_code}


def _normalize_key(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


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
    if normalized == "secretpresencesummary":
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
    if RAW_CONFIG_VALUE_PATTERN.search(value):
        findings.append(_finding(field, "raw_config_dump_forbidden"))
    if LAUNCH_APPROVAL_PATTERN.search(value):
        findings.append(_finding(field, "launch_approval_claim_forbidden"))
    return findings


def _scan_tree(value: Any, field: str = "$") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_field = f"{field}.{key}" if field != "$" else str(key)
            findings.extend(_scan_key(child_field, key))
            findings.extend(_scan_tree(child, child_field))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_scan_tree(child, f"{field}[{index}]"))
    elif isinstance(value, str):
        findings.extend(_scan_string(field, value))
    return findings


def _validate_artifact(artifact: Any) -> tuple[list[dict[str, str]], dict[str, bool]]:
    findings: list[dict[str, str]] = []
    checks = {
        "requiredFieldsPresent": False,
        "schemaValuesValid": False,
        "unsafeContentAbsent": False,
        "acceptedOutcomeHasCriticalSummaries": False,
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
            "secret_like_value_detected",
        }
        for finding in findings
    )
    checks["acceptedOutcomeHasCriticalSummaries"] = not (
        artifact.get("outcome") == "accepted" and missing_critical
    )
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
