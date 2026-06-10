#!/usr/bin/env python3
"""Validate isolated PostgreSQL restore smoke evidence offline.

This scaffold is intentionally advisory. It emits sanitized JSON, does not
connect to databases, does not run restore commands, and never marks public
launch ready.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "wolfystock_isolated_pg_restore_smoke_v1"
INPUT_SCHEMA_VERSION = "wolfystock_isolated_pg_restore_smoke_input_v1"
ALLOWED_SOURCE_ENVIRONMENTS = {
    "anonymized",
    "isolated-restore",
    "sandbox",
    "sanitized",
    "staging",
    "staging-restore",
    "synthetic",
}
SAFE_TEXT_VALUES = {
    "",
    "***",
    "********",
    "[redacted]",
    "<redacted>",
    "masked",
    "missing",
    "none",
    "not_applicable",
    "not_provided",
    "present",
    "redacted",
    "sanitized",
}
SENSITIVE_KEY_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "connection_string",
    "cookie",
    "credential",
    "database_url",
    "db_url",
    "dsn",
    "env_value",
    "password",
    "private_key",
    "raw_dump",
    "raw_log",
    "raw_path",
    "raw_payload",
    "raw_response",
    "session",
    "stack_trace",
    "stacktrace",
    "token",
    "traceback",
    "webhook_url",
)
SENSITIVE_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("raw_dsn", re.compile(r"\b(?:postgres|postgresql|mysql|redis)://", re.IGNORECASE)),
    (
        "secret_assignment",
        re.compile(
            r"\b(?:api[-_]?key|apikey|access[-_]?token|token|secret|password|passwd|cookie|session|dsn|"
            r"database[-_]?url|db[-_]?url|connection[-_]?string|webhook[-_]?url)\s*"
            r"[=:]\s*(?!\*{3}|redacted\b)[^\s,;&]+",
            re.IGNORECASE,
        ),
    ),
    ("env_assignment", re.compile(r"\b[A-Z][A-Z0-9_]{2,}\s*=")),
    (
        "bearer_token",
        re.compile(r"\b(?:Authorization\s*:\s*)?Bearer\s+(?!\*{3}|redacted\b)[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    ),
    ("known_token", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9_]{24,}|xox[baprs]-[A-Za-z0-9-]{20,})\b")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("traceback", re.compile(r"\b(?:Traceback \(most recent call last\):|Stack trace:|File \"[^\"]+\", line \d+)", re.IGNORECASE)),
    ("credential_url", re.compile(r"\bhttps?://[^/\s:@]+:[^@\s]+@[^/\s]+", re.IGNORECASE)),
    ("credential_url", re.compile(r"\bhttps?://[^\s?#]+[?][^\s]+", re.IGNORECASE)),
    (
        "production_host",
        re.compile(
            r"\b(?:(?:prod(?:uction)?|primary|live)[a-z0-9.-]*(?:db|pg|postgres|rds|database)|"
            r"(?:db|pg|postgres|rds|database)[a-z0-9.-]*(?:prod(?:uction)?|primary|live))"
            r"[a-z0-9.-]*\b",
            re.IGNORECASE,
        ),
    ),
    (
        "raw_path",
        re.compile(
            r"(^|[\s\"'=])(?:/[A-Za-z0-9._-]+){2,}|[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)+",
            re.IGNORECASE,
        ),
    ),
    (
        "raw_sql_or_dump",
        re.compile(
            r"\b(?:CREATE|ALTER|DROP|TRUNCATE)\s+(?:TABLE|DATABASE|SCHEMA)\b|"
            r"\b(?:INSERT\s+INTO|COPY\s+\w+\s+FROM|pg_dump|pg_restore)\b|"
            r"^--\s*PostgreSQL database dump",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
)
SAFE_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,159}$")
TARGET_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,159}$")
ENV_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
PRODUCTION_MARKERS = ("prod", "production", "primary", "live")
ISOLATED_MARKERS = ("isolated", "sandbox", "synthetic", "disposable", "restore-smoke")


def _status(ok: bool) -> str:
    return "pass" if ok else "fail"


def _safe_text(value: str) -> bool:
    return value.strip().lower() in SAFE_TEXT_VALUES


def _normalize_key(value: str) -> str:
    return value.lower().replace("-", "_").replace(" ", "_")


def _path_join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _safe_label(value: Any) -> bool:
    return isinstance(value, str) and bool(SAFE_LABEL_PATTERN.fullmatch(value.strip()))


def _safe_label_list(values: Any) -> bool:
    return isinstance(values, list) and bool(values) and all(_safe_label(value) for value in values)


def _is_safe_env_name(value: str | None) -> bool:
    return value is None or bool(ENV_NAME_PATTERN.fullmatch(value))


def _load_artifact(path: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit("[FAIL] Evidence file not found")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[FAIL] Evidence file is not valid JSON: {exc}")
    if not isinstance(payload, dict):
        raise SystemExit("[FAIL] Evidence file must contain a JSON object")
    return payload


def _find_unsafe_values(value: Any, *, path: str = "") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for raw_key, nested in value.items():
            key = str(raw_key)
            nested_path = _path_join(path, key)
            normalized_key = _normalize_key(key)
            if isinstance(nested, str) and any(marker in normalized_key for marker in SENSITIVE_KEY_MARKERS):
                if not _safe_text(nested):
                    findings.append({"path": nested_path, "reasonCode": "sensitive_key_contains_value"})
                    continue
            if normalized_key in {"path", "file_path", "backup_path", "dump_path", "artifact_path"}:
                if isinstance(nested, str) and not _safe_text(nested):
                    findings.append({"path": nested_path, "reasonCode": "path_value_not_allowed"})
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
        for reason_code, pattern in SENSITIVE_VALUE_PATTERNS:
            if pattern.search(value):
                findings.append({"path": path or "$", "reasonCode": reason_code})
                return findings
    return findings


def _target_check(payload: dict[str, Any], *, override_label: str | None = None) -> dict[str, Any]:
    label = override_label if override_label is not None else payload.get("isolatedTargetLabel")
    label_text = str(label or "").strip()
    label_lower = label_text.lower()
    label_safe = bool(TARGET_LABEL_PATTERN.fullmatch(label_text))
    isolated_marker = any(marker in label_lower for marker in ISOLATED_MARKERS)
    production_marker = any(marker in label_lower for marker in PRODUCTION_MARKERS)
    ok = label_safe and isolated_marker and not production_marker
    return {
        "id": "restore_target_is_explicitly_isolated",
        "status": _status(ok),
        "evidence": {
            "isolatedTargetLabel": label_text if ok else "<invalid-or-unsafe>",
            "safeLabel": label_safe,
            "isolatedMarkerPresent": isolated_marker,
            "productionMarkerDetected": production_marker,
        },
    }


def _required_fields_check(payload: dict[str, Any]) -> dict[str, Any]:
    required = (
        "isolatedTargetLabel",
        "restoreTimestamp",
        "pitrTargetTimestamp",
        "restoreEvidence",
        "pitrEvidence",
        "appBootReadinessSmoke",
        "ownerIsolationSmoke",
        "checksumManifestRefs",
        "noSecretConfirmation",
        "teardownQuarantineConfirmation",
    )
    missing = [field for field in required if field not in payload]
    schema_ok = payload.get("schemaVersion") in {None, INPUT_SCHEMA_VERSION}
    source = str(payload.get("sourceEnvironment") or "").strip()
    source_ok = source in ALLOWED_SOURCE_ENVIRONMENTS
    return {
        "id": "required_evidence_fields_are_complete",
        "status": _status(not missing and schema_ok and source_ok),
        "evidence": {
            "missingFields": missing,
            "schemaVersionAccepted": schema_ok,
            "sourceEnvironment": source if source_ok else "invalid",
        },
    }


def _timestamp_check(payload: dict[str, Any]) -> dict[str, Any]:
    restore_valid = _valid_timestamp(payload.get("restoreTimestamp"))
    pitr_valid = _valid_timestamp(payload.get("pitrTargetTimestamp"))
    return {
        "id": "restore_timestamps_are_valid",
        "status": _status(restore_valid and pitr_valid),
        "evidence": {
            "restoreTimestampValid": restore_valid,
            "pitrTargetTimestampValid": pitr_valid,
        },
    }


def _result_section_passed(section: Any, *, executed_key: str | None = None) -> bool:
    if not isinstance(section, dict):
        return False
    if str(section.get("status") or "").lower() != "pass":
        return False
    if executed_key and section.get(executed_key) is not True:
        return False
    ref = section.get("artifactRef") or section.get("evidenceRef")
    return _safe_label(ref)


def _restore_pitr_check(payload: dict[str, Any]) -> dict[str, Any]:
    restore_ok = _result_section_passed(payload.get("restoreEvidence"), executed_key="restoreExecuted")
    pitr_ok = _result_section_passed(payload.get("pitrEvidence"), executed_key="pitrExecuted")
    return {
        "id": "restore_and_pitr_evidence_present",
        "status": _status(restore_ok and pitr_ok),
        "evidence": {
            "restoreEvidencePass": restore_ok,
            "pitrEvidencePass": pitr_ok,
        },
    }


def _smoke_check(payload: dict[str, Any]) -> dict[str, Any]:
    app_boot_ok = _result_section_passed(payload.get("appBootReadinessSmoke"))
    owner_isolation_ok = _result_section_passed(payload.get("ownerIsolationSmoke"))
    return {
        "id": "post_restore_smoke_checks_pass",
        "status": _status(app_boot_ok and owner_isolation_ok),
        "evidence": {
            "appBootReadinessSmokePass": app_boot_ok,
            "ownerIsolationSmokePass": owner_isolation_ok,
        },
    }


def _manifest_check(payload: dict[str, Any]) -> dict[str, Any]:
    refs = payload.get("checksumManifestRefs")
    ok = _safe_label_list(refs)
    return {
        "id": "checksum_or_manifest_references_present",
        "status": _status(ok),
        "evidence": {
            "checksumManifestRefCount": len(refs) if isinstance(refs, list) else 0,
            "valuesIncluded": False,
        },
    }


def _cleanup_confirmation_check(payload: dict[str, Any]) -> dict[str, Any]:
    no_secret_ok = payload.get("noSecretConfirmation") is True
    teardown_ok = _result_section_passed(payload.get("teardownQuarantineConfirmation"))
    blockers = payload.get("blockers")
    blockers_ok = isinstance(blockers, list) and not blockers
    return {
        "id": "no_secret_and_teardown_confirmations_present",
        "status": _status(no_secret_ok and teardown_ok and blockers_ok),
        "evidence": {
            "noSecretConfirmation": no_secret_ok,
            "teardownOrQuarantineConfirmation": teardown_ok,
            "blockersEmpty": blockers_ok,
        },
    }


def _sanitization_check(payload: dict[str, Any]) -> dict[str, Any]:
    findings = _find_unsafe_values(payload)
    return {
        "id": "artifact_contains_no_raw_dsn_secret_or_path_values",
        "status": _status(not findings),
        "evidence": {
            "unsafeFindingCount": len(findings),
            "findings": findings[:20],
            "findingValuesIncluded": False,
        },
    }


def _validator_safety_check() -> dict[str, Any]:
    return {
        "id": "validator_is_offline_no_db_no_network",
        "status": "pass",
        "evidence": {
            "databaseCommandsRunByValidator": False,
            "restoreCommandsRunByValidator": False,
            "networkCallsEnabled": False,
            "productionStorageTouched": False,
            "runtimeStorageChanged": False,
            "schemaChanged": False,
        },
    }


def _artifact_summary(payload: dict[str, Any], target_check: dict[str, Any]) -> dict[str, Any]:
    target_evidence = target_check.get("evidence") if isinstance(target_check.get("evidence"), dict) else {}
    refs = payload.get("checksumManifestRefs")
    return {
        "isolatedTargetLabel": str(target_evidence.get("isolatedTargetLabel") or "<invalid-or-unsafe>"),
        "sourceEnvironment": str(payload.get("sourceEnvironment") or ""),
        "hasPitrTargetTimestamp": _valid_timestamp(payload.get("pitrTargetTimestamp")),
        "checksumManifestRefCount": len(refs) if isinstance(refs, list) else 0,
    }


def _base_report(*, mode: str, final_status: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": mode,
        "finalStatus": final_status,
        "dryRun": mode in {"dry-run", "local-target-scaffold"},
        "publicLaunchReady": False,
        "launchApproved": False,
        "databaseCommandsRunByValidator": False,
        "restoreCommandsRunByValidator": False,
        "networkCallsEnabled": False,
        "productionStorageTouched": False,
        "runtimeBehaviorChanged": False,
        "schemaChanged": False,
        "checks": checks,
    }


def _build_dry_run_report(*, target_label: str | None = None, connection_env_name: str | None = None) -> dict[str, Any]:
    checks = [
        {
            "id": "dry_run_no_artifact_supplied",
            "status": "pass",
            "evidence": {
                "artifactSupplied": False,
                "restoreExecutionEnabled": False,
                "pitrExecutionEnabled": False,
                "connectionValuesRead": False,
            },
        },
        _validator_safety_check(),
    ]
    mode = "dry-run"
    if target_label is not None or connection_env_name is not None:
        target_check = _target_check({}, override_label=target_label or "")
        env_ok = _is_safe_env_name(connection_env_name)
        checks.extend(
            [
                target_check,
                {
                    "id": "connection_info_is_env_name_only",
                    "status": _status(env_ok),
                    "evidence": {
                        "envNameAccepted": env_ok,
                        "envValueRead": False,
                        "valuesIncluded": False,
                    },
                },
            ]
        )
        mode = "local-target-scaffold"
    final_status = "DRY-RUN" if all(check["status"] == "pass" for check in checks) else "NO-GO"
    report = _base_report(mode=mode, final_status=final_status, checks=checks)
    report["operatorInstructions"] = {
        "supplySanitizedArtifactWith": [
            "isolatedTargetLabel",
            "restoreTimestamp",
            "pitrTargetTimestamp",
            "appBootReadinessSmoke",
            "ownerIsolationSmoke",
            "checksumManifestRefs",
            "noSecretConfirmation",
            "teardownQuarantineConfirmation",
        ],
        "restoreCommandsRunByThisTool": False,
        "rawDsnAccepted": False,
    }
    return report


def _build_artifact_report(payload: dict[str, Any]) -> dict[str, Any]:
    target_check = _target_check(payload)
    checks = [
        _required_fields_check(payload),
        target_check,
        _timestamp_check(payload),
        _restore_pitr_check(payload),
        _smoke_check(payload),
        _manifest_check(payload),
        _cleanup_confirmation_check(payload),
        _sanitization_check(payload),
        _validator_safety_check(),
    ]
    final_status = "EVIDENCE-READY" if all(check["status"] == "pass" for check in checks) else "NO-GO"
    report = _base_report(mode="artifact-validation", final_status=final_status, checks=checks)
    report["artifactSummary"] = _artifact_summary(payload, target_check)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate isolated PostgreSQL restore smoke evidence offline.")
    parser.add_argument("--artifact", help="Path to a sanitized isolated PostgreSQL restore smoke evidence JSON artifact.")
    parser.add_argument("--isolated-target-label", help="Sanitized local disposable target label only; no host, DSN, or path.")
    parser.add_argument("--connection-env-name", help="Optional env var name label only. The value is never read or printed.")
    args = parser.parse_args(argv)

    if args.artifact:
        payload = _load_artifact(args.artifact)
        report = _build_artifact_report(payload)
    else:
        report = _build_dry_run_report(
            target_label=args.isolated_target_label,
            connection_env_name=args.connection_env_name,
        )

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["finalStatus"] in {"DRY-RUN", "EVIDENCE-READY"} else 1


if __name__ == "__main__":
    sys.exit(main())
