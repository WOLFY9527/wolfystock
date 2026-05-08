#!/usr/bin/env python3
"""Validate a release restore/rollback drill packet offline.

This helper is advisory only. It does not connect to databases, read secrets,
run migrations, restore data, delete files, send notifications, or call
networks. Operators provide sanitized labels and plan notes for review.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "wolfystock_release_restore_rollback_drill_v1"
INPUT_SCHEMA_VERSION = "wolfystock_release_restore_rollback_drill_input_v1"
MAX_ARTIFACT_BYTES = 32768
MAX_FINDINGS = 20
REQUIRED_FIELDS = (
    "backupLabel",
    "restoreDrillLabel",
    "rollbackOwnerLabel",
    "releaseCandidateLabel",
    "rpoRtoNotes",
    "frontendRollbackPlan",
    "backendRollbackPlan",
    "databaseRollbackRestorePlan",
    "adminAuthRecoveryNote",
)
RESTORE_FIELDS = {
    "backupLabel",
    "restoreDrillLabel",
    "rpoRtoNotes",
    "databaseRollbackRestorePlan",
    "adminAuthRecoveryNote",
}
ROLLBACK_FIELDS = {
    "rollbackOwnerLabel",
    "releaseCandidateLabel",
    "frontendRollbackPlan",
    "backendRollbackPlan",
    "databaseRollbackRestorePlan",
    "adminAuthRecoveryNote",
}
REQUIRED_FALSE_ASSERTIONS = (
    "productionDbConnected",
    "secretsRead",
    "migrationsRun",
    "databasesRestored",
    "filesDeleted",
    "notificationsSent",
    "networkCallsMade",
    "destructiveOperationsExecuted",
)
SAFE_TEXT_VALUES = {
    "",
    "***",
    "********",
    "[redacted]",
    "redacted",
    "<redacted>",
    "masked",
    "missing",
    "none",
    "not_applicable",
    "present",
    "sanitized",
}
SENSITIVE_KEY_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "dsn",
    "env",
    "password",
    "private_key",
    "raw_log",
    "raw_payload",
    "raw_response",
    "secret",
    "session",
    "token",
    "webhook",
)
SAFE_FIELD_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:/@+-]{2,479}$")
ABSOLUTE_PATH_PATTERN = re.compile(r"(^|\s)(?:/[^/\s][^\s]*|~[/\\][^\s]*|[A-Za-z]:[\\/][^\s]*)")
SECRET_VALUE_PATTERNS = (
    re.compile(
        r"([?&](?:api[-_]?key|apikey|access_token|token|secret|password|cookie|session)=)"
        r"(?!\*{3}|redacted)[^&#\s]+",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:api[-_]?key|apikey|access_token|token|secret|password|cookie|session|dsn)\s*"
        r"[=:]\s*(?!\*{3}|redacted\b)[^\s,;&]+",
        re.IGNORECASE,
    ),
    re.compile(r"\bAuthorization\s*:\s*Bearer\s+(?!\*{3}|redacted\b)[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\bBearer\s+(?!\*{3}|redacted\b)[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    re.compile(r"\b(?:postgres|postgresql|mysql|redis)://[^:/@\s]+:[^@\s]+@", re.IGNORECASE),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9_]{24,}|xox[baprs]-[A-Za-z0-9-]{20,})\b"),
    re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
)
DESTRUCTIVE_TEXT_PATTERNS = (
    re.compile(r"\b(?:dropdb|createdb|pg_restore|psql)\b.*(?:prod|production|primary|live)", re.IGNORECASE),
    re.compile(r"\b(?:DROP|TRUNCATE)\s+(?:DATABASE|SCHEMA|TABLE)\b", re.IGNORECASE),
    re.compile(r"\b(?:rm\s+-rf|unlink|shred)\b", re.IGNORECASE),
    re.compile(r"\b(?:restore|promote|failover)\s+(?:prod|production|primary|live)\b", re.IGNORECASE),
)
NETWORK_TEXT_PATTERNS = (
    re.compile(r"\b(?:curl|wget|httpie|nc|telnet)\b", re.IGNORECASE),
    re.compile(r"\bhttps?://", re.IGNORECASE),
)
APPROVAL_CLAIM_PATTERNS = (
    re.compile(r"\blaunch[-_ ]?approved\b", re.IGNORECASE),
    re.compile(r"\blaunch[-_ ]?go\b", re.IGNORECASE),
    re.compile(r"\brelease[-_ ]?approved\b", re.IGNORECASE),
    re.compile(r"^\s*GO\s*$", re.IGNORECASE),
)
APPROVAL_KEYS = {"launchapproved", "releaseapproved", "launchgo", "go"}


def _empty_artifact() -> dict[str, Any]:
    return {
        "schemaVersion": INPUT_SCHEMA_VERSION,
        "mode": "offline_empty",
    }


def _load_artifact(path: Path) -> dict[str, Any]:
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError("artifact_too_large")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("artifact_invalid_json") from exc
    if not isinstance(payload, dict):
        raise ValueError("artifact_not_json_object")
    return payload


def _status(ok: bool) -> str:
    return "pass" if ok else "fail"


def _path_join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _normalize_key(value: str) -> str:
    return value.lower().replace("-", "_").replace(" ", "_")


def _compact_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _safe_text(value: str) -> bool:
    return value.strip().lower() in SAFE_TEXT_VALUES


def _finding(path: str, reason: str) -> dict[str, str]:
    return {"path": path or "$", "reasonCode": reason}


def _find_unsafe_values(value: Any, *, path: str = "") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            nested_path = _path_join(path, key_text)
            normalized_key = _normalize_key(key_text)
            compact_key = _compact_key(key_text)
            if compact_key in APPROVAL_KEYS and nested is True:
                findings.append(_finding(nested_path, "release_or_launch_approval_claim_not_allowed"))
                continue
            if isinstance(nested, str) and any(marker in normalized_key for marker in SENSITIVE_KEY_MARKERS):
                if not _safe_text(nested):
                    findings.append(_finding(nested_path, "sensitive_key_contains_value"))
                    continue
            findings.extend(_find_unsafe_values(nested, path=nested_path))
        return findings
    if isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_find_unsafe_values(nested, path=f"{path}[{index}]"))
        return findings
    if isinstance(value, str):
        if _safe_text(value):
            return findings
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                findings.append(_finding(path, "secret_like_value_detected"))
                return findings
        if ABSOLUTE_PATH_PATTERN.search(value):
            findings.append(_finding(path, "unsafe_path_like_value"))
            return findings
        for pattern in DESTRUCTIVE_TEXT_PATTERNS:
            if pattern.search(value):
                findings.append(_finding(path, "destructive_operation_text_not_allowed"))
                return findings
        for pattern in NETWORK_TEXT_PATTERNS:
            if pattern.search(value):
                findings.append(_finding(path, "network_call_text_not_allowed"))
                return findings
        for pattern in APPROVAL_CLAIM_PATTERNS:
            if pattern.search(value):
                findings.append(_finding(path, "release_or_launch_approval_claim_not_allowed"))
                return findings
    return findings


def _required_fields_check(payload: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    invalid = [
        field
        for field in REQUIRED_FIELDS
        if field in payload and not (isinstance(payload[field], str) and SAFE_FIELD_PATTERN.fullmatch(payload[field]))
    ]
    schema_ok = payload.get("schemaVersion") in {None, INPUT_SCHEMA_VERSION}
    ok = not missing and not invalid and schema_ok
    return {
        "status": _status(ok),
        "requiredFieldCount": len(REQUIRED_FIELDS),
        "presentFieldCount": len([field for field in REQUIRED_FIELDS if field in payload]),
        "missingFields": missing,
        "invalidFields": invalid,
        "schemaVersionAccepted": schema_ok,
    }


def _operator_assertions_check(payload: dict[str, Any]) -> dict[str, Any]:
    assertions = payload.get("operatorAssertions")
    if assertions is None:
        assertions = {}
    if not isinstance(assertions, dict):
        return {
            "status": "fail",
            "requiredFalseFlags": list(REQUIRED_FALSE_ASSERTIONS),
            "unsafeTrueFlags": ["operatorAssertions"],
        }
    unsafe_true = [flag for flag in REQUIRED_FALSE_ASSERTIONS if assertions.get(flag) is True]
    return {
        "status": _status(not unsafe_true),
        "requiredFalseFlags": list(REQUIRED_FALSE_ASSERTIONS),
        "unsafeTrueFlags": unsafe_true,
    }


def _safety_check(payload: dict[str, Any], load_error: str | None = None) -> dict[str, Any]:
    findings = _find_unsafe_values(payload)
    if load_error:
        findings.insert(0, _finding("artifact", load_error))
    bounded_findings = findings[:MAX_FINDINGS]
    return {
        "status": _status(not findings),
        "unsafeFindingCount": len(findings),
        "findings": bounded_findings,
        "findingValuesIncluded": False,
        "maxFindingsEmitted": MAX_FINDINGS,
    }


def _build_report(payload: dict[str, Any], *, load_error: str | None = None) -> dict[str, Any]:
    required = _required_fields_check(payload)
    safety = _safety_check(payload, load_error=load_error)
    assertions = _operator_assertions_check(payload)
    field_ok = required["status"] == "pass"
    safety_ok = safety["status"] == "pass" and assertions["status"] == "pass"
    restore_ready = field_ok and safety_ok and all(field not in required["missingFields"] for field in RESTORE_FIELDS)
    rollback_ready = field_ok and safety_ok and all(field not in required["missingFields"] for field in ROLLBACK_FIELDS)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "inputSchemaVersion": payload.get("schemaVersion") or "unknown",
        "mode": "offline_operator_review",
        "drillStatus": "REVIEW-READY" if restore_ready and rollback_ready else "NO-GO",
        "restoreReady": restore_ready,
        "rollbackReady": rollback_ready,
        "destructiveOperationsExecuted": False,
        "networkCallsExecuted": False,
        "manualReviewRequired": True,
        "releaseApproved": False,
        "runtimeBehaviorChanged": False,
        "checks": {
            "requiredFields": required,
            "safety": safety,
            "operatorAssertions": assertions,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate release restore/rollback drill labels offline.")
    parser.add_argument("--offline", action="store_true", required=True, help="Run offline advisory validation only.")
    parser.add_argument("--artifact", help="Path to sanitized operator-supplied drill JSON.")
    parser.add_argument("--allow-no-go", action="store_true", help="Return exit 0 even when the drill remains NO-GO.")
    args = parser.parse_args(argv)

    load_error: str | None = None
    payload = _empty_artifact()
    artifact_supplied = bool(args.artifact)
    if args.artifact:
        try:
            payload = _load_artifact(Path(args.artifact))
        except OSError:
            load_error = "artifact_not_readable"
            payload = _empty_artifact()
        except ValueError as exc:
            load_error = str(exc)
            payload = _empty_artifact()

    report = _build_report(payload, load_error=load_error)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    if report["drillStatus"] != "REVIEW-READY" and artifact_supplied and not args.allow_no_go:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
