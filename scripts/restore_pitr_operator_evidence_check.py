#!/usr/bin/env python3
"""Validate sanitized PostgreSQL restore/PITR operator evidence offline.

This helper reads one operator-sanitized JSON artifact and emits a bounded JSON
verdict. It does not run restore commands, connect to databases, read env
files, call networks, mutate storage, or approve launch.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "wolfystock_restore_pitr_operator_evidence_v1"
INPUT_SCHEMA_VERSION = "wolfystock_restore_pitr_operator_evidence_input_v1"
ALLOWED_ENVIRONMENTS = {"isolated-restore", "staging-restore", "sandbox"}
ALLOWED_OUTCOMES = {"accepted", "rejected", "needs-review"}
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
    "env_value",
    "password",
    "private_key",
    "raw_dump",
    "raw_log",
    "raw_payload",
    "raw_response",
    "session",
    "stack_trace",
    "stacktrace",
    "token",
    "traceback",
    "webhook_url",
)
SENSITIVE_VALUE_PATTERNS = (
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
    re.compile(r"\b(?:postgres|postgresql)://", re.IGNORECASE),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9_]{24,}|xox[baprs]-[A-Za-z0-9-]{20,})\b"),
    re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    re.compile(r"\bTraceback \(most recent call last\):"),
    re.compile(r"\b(?:File \"[^\"]+\", line \d+, in |Exception:|Stack trace:)", re.IGNORECASE),
)
RAW_SQL_PATTERNS = (
    re.compile(r"\b(?:CREATE|ALTER|DROP|TRUNCATE)\s+(?:TABLE|DATABASE|SCHEMA)\b", re.IGNORECASE),
    re.compile(r"\b(?:INSERT\s+INTO|COPY\s+\w+\s+FROM|pg_dump|pg_restore)\b", re.IGNORECASE),
    re.compile(r"^--\s*PostgreSQL database dump", re.IGNORECASE | re.MULTILINE),
)
DESTRUCTIVE_PRODUCTION_PATTERNS = (
    re.compile(r"\b(?:dropdb|createdb|pg_restore|psql)\b.*(?:prod|production|primary|live)", re.IGNORECASE),
    re.compile(r"\b(?:DROP|TRUNCATE)\s+(?:DATABASE|SCHEMA|TABLE)\b.*(?:prod|production|primary|live)", re.IGNORECASE),
    re.compile(r"\brestore\b.*(?:prod|production|primary|live)", re.IGNORECASE),
)
LAUNCH_GO_STRING_PATTERNS = (
    re.compile(r"\blaunch[-_ ]?approved\b", re.IGNORECASE),
    re.compile(r"\blaunch[-_ ]?go\b", re.IGNORECASE),
    re.compile(r"^\s*GO\s*$", re.IGNORECASE),
)
LAUNCH_GO_KEYS = {
    "launchapproved",
    "launchgo",
    "go",
    "goliveapproved",
    "releaseapproved",
}
REQUIRED_FIELDS = (
    "drillId",
    "environment",
    "operator",
    "startedAt",
    "completedAt",
    "backupArtifactRef",
    "restoreTarget",
    "restoreCommandExecuted",
    "destructiveProductionCommandExecuted",
    "pitrTargetTimestamp",
    "verificationQueries",
    "rpoObservedSeconds",
    "rtoObservedSeconds",
    "outcome",
    "evidenceRedactionVersion",
)
SAFE_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,159}$")


def _status(ok: bool) -> str:
    return "pass" if ok else "fail"


def _safe_text(value: str) -> bool:
    return value.strip().lower() in SAFE_TEXT_VALUES


def _path_join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _normalize_key(value: str) -> str:
    return value.lower().replace("-", "_").replace(" ", "_")


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _parse_timestamp(value: Any) -> datetime | None:
    if not _valid_timestamp(value):
        return None
    return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))


def _safe_label(value: Any) -> bool:
    return bool(SAFE_LABEL_PATTERN.fullmatch(str(value or "")))


def _load_artifact(path: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"[FAIL] Evidence file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[FAIL] Evidence file is not valid JSON: {exc}")
    if not isinstance(payload, dict):
        raise SystemExit("[FAIL] Evidence file must contain a JSON object")
    return payload


def _find_unsafe_values(value: Any, *, path: str = "") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            nested_path = _path_join(path, key_text)
            normalized_key = _normalize_key(key_text)
            if isinstance(nested, str) and any(marker in normalized_key for marker in SENSITIVE_KEY_MARKERS):
                if not _safe_text(nested):
                    findings.append({"path": nested_path, "reasonCode": "sensitive_key_contains_value"})
                    continue
            if normalized_key in {"sql", "rawsql", "raw_sql", "querytext", "query_text"}:
                findings.append({"path": nested_path, "reasonCode": "raw_sql_field_not_allowed"})
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
        for pattern in SENSITIVE_VALUE_PATTERNS:
            if pattern.search(value):
                findings.append({"path": path or "$", "reasonCode": "secret_like_value_detected"})
                return findings
        for pattern in RAW_SQL_PATTERNS:
            if pattern.search(value):
                findings.append({"path": path or "$", "reasonCode": "raw_sql_or_dump_detected"})
                return findings
        for pattern in DESTRUCTIVE_PRODUCTION_PATTERNS:
            if pattern.search(value):
                findings.append({"path": path or "$", "reasonCode": "destructive_production_command_marker"})
                return findings
    return findings


def _find_launch_claims(value: Any, *, path: str = "") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            nested_path = _path_join(path, key_text)
            compact_key = re.sub(r"[^a-z0-9]", "", key_text.lower())
            if compact_key in LAUNCH_GO_KEYS and nested is True:
                findings.append({"path": nested_path, "reasonCode": "launch_approval_boolean_not_allowed"})
                continue
            findings.extend(_find_launch_claims(nested, path=nested_path))
        return findings
    if isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_find_launch_claims(nested, path=f"{path}[{index}]"))
        return findings
    if isinstance(value, str):
        for pattern in LAUNCH_GO_STRING_PATTERNS:
            if pattern.search(value):
                findings.append({"path": path or "$", "reasonCode": "launch_approval_text_not_allowed"})
                break
    return findings


def _required_fields_check(payload: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    invalid_safe_labels = [
        field
        for field in ("drillId", "operator", "backupArtifactRef", "restoreTarget", "evidenceRedactionVersion")
        if field in payload and not _safe_label(payload.get(field))
    ]
    schema_ok = payload.get("schemaVersion") in {None, INPUT_SCHEMA_VERSION}
    environment = str(payload.get("environment") or "")
    outcome = str(payload.get("outcome") or "")
    ok = (
        not missing
        and not invalid_safe_labels
        and schema_ok
        and environment in ALLOWED_ENVIRONMENTS
        and outcome in ALLOWED_OUTCOMES
    )
    return {
        "id": "operator_artifact_required_fields_are_complete",
        "status": _status(ok),
        "evidence": {
            "missingFields": missing,
            "invalidSafeLabelFields": invalid_safe_labels,
            "schemaVersionAccepted": schema_ok,
            "environment": environment if environment in ALLOWED_ENVIRONMENTS else "invalid",
            "outcome": outcome if outcome in ALLOWED_OUTCOMES else "invalid",
        },
    }


def _target_safety_check(payload: dict[str, Any]) -> dict[str, Any]:
    restore_command_executed = payload.get("restoreCommandExecuted") is True
    destructive_prod = payload.get("destructiveProductionCommandExecuted") is True
    environment_ok = payload.get("environment") in ALLOWED_ENVIRONMENTS
    target_ok = _safe_label(payload.get("restoreTarget"))
    ok = restore_command_executed and not destructive_prod and environment_ok and target_ok
    return {
        "id": "restore_target_is_isolated_and_non_destructive",
        "status": _status(ok),
        "evidence": {
            "environmentExplicitlyIsolated": environment_ok,
            "restoreCommandExecuted": restore_command_executed,
            "destructiveProductionCommandExecuted": destructive_prod,
            "restoreTargetSanitizedLabel": target_ok,
        },
    }


def _timing_and_metrics_check(payload: dict[str, Any]) -> dict[str, Any]:
    started = _parse_timestamp(payload.get("startedAt"))
    completed = _parse_timestamp(payload.get("completedAt"))
    pitr_target_ok = _valid_timestamp(payload.get("pitrTargetTimestamp"))
    ordering_ok = bool(started and completed and started <= completed)
    rpo = payload.get("rpoObservedSeconds")
    rto = payload.get("rtoObservedSeconds")
    rpo_ok = isinstance(rpo, int) and rpo >= 0
    rto_ok = isinstance(rto, int) and rto >= 0
    ok = ordering_ok and pitr_target_ok and rpo_ok and rto_ok
    return {
        "id": "restore_pitr_timing_and_metrics_are_valid",
        "status": _status(ok),
        "evidence": {
            "startedAtValid": started is not None,
            "completedAtValid": completed is not None,
            "startedBeforeCompleted": ordering_ok,
            "pitrTargetTimestampValid": pitr_target_ok,
            "rpoObservedSecondsValid": rpo_ok,
            "rtoObservedSecondsValid": rto_ok,
        },
    }


def _verification_queries_check(payload: dict[str, Any]) -> dict[str, Any]:
    queries = payload.get("verificationQueries")
    invalid_entries = 0
    query_count = 0
    if isinstance(queries, list):
        for item in queries:
            query_count += 1
            if not isinstance(item, dict):
                invalid_entries += 1
                continue
            result_kind = str(item.get("resultKind") or "")
            has_raw_key = any(
                _normalize_key(str(key)) in {"sql", "rawsql", "raw_sql", "rawdump", "raw_dump", "querytext", "query_text"}
                for key in item
            )
            count_fields_ok = all(
                isinstance(item.get(key), int) and item.get(key) >= 0
                for key in item
                if key in {"observedCount", "expectedCount"}
            )
            checksum_ok = "checksum" not in item or _safe_label(item.get("checksum"))
            label_ok = _safe_label(item.get("label"))
            if result_kind not in {"count", "checksum"} or has_raw_key or not count_fields_ok or not checksum_ok or not label_ok:
                invalid_entries += 1
    else:
        invalid_entries = 1
    ok = isinstance(queries, list) and query_count > 0 and invalid_entries == 0
    return {
        "id": "verification_queries_are_sanitized_summaries",
        "status": _status(ok),
        "evidence": {
            "querySummaryCount": query_count,
            "invalidEntryCount": invalid_entries,
            "rawSqlAllowed": False,
        },
    }


def _sanitization_check(payload: dict[str, Any]) -> dict[str, Any]:
    findings = _find_unsafe_values(payload)
    return {
        "id": "artifact_contains_no_sensitive_or_raw_values",
        "status": _status(not findings),
        "evidence": {
            "unsafeFindingCount": len(findings),
            "findings": findings[:20],
            "findingValuesIncluded": False,
        },
    }


def _launch_claim_check(payload: dict[str, Any]) -> dict[str, Any]:
    findings = _find_launch_claims(payload)
    return {
        "id": "artifact_does_not_claim_launch_approval",
        "status": _status(not findings),
        "evidence": {
            "launchClaimCount": len(findings),
            "findings": findings[:20],
            "launchApprovedByValidator": False,
        },
    }


def _outcome_check(payload: dict[str, Any]) -> dict[str, Any]:
    outcome = str(payload.get("outcome") or "")
    return {
        "id": "operator_outcome_is_accepted",
        "status": _status(outcome == "accepted"),
        "evidence": {
            "outcome": outcome if outcome in ALLOWED_OUTCOMES else "invalid",
            "acceptedRequiredForEvidenceReady": True,
        },
    }


def _validator_safety_check(payload: dict[str, Any]) -> dict[str, Any]:
    generation = payload.get("localGeneration") if isinstance(payload.get("localGeneration"), dict) else {}
    required_false_flags = (
        "checkerRanRestoreCommands",
        "networkCallsEnabled",
        "productionStorageTouched",
        "productionSecretsRead",
        "rawLogsIncluded",
        "runtimeBehaviorChanged",
    )
    unexpected_true_flags = [flag for flag in required_false_flags if generation.get(flag) is True]
    return {
        "id": "validator_is_offline_advisory_only",
        "status": _status(not unexpected_true_flags),
        "evidence": {
            "databaseCommandsRunByValidator": False,
            "networkCallsEnabled": False,
            "productionStorageTouched": False,
            "launchApprovedByValidator": False,
            "unexpectedTrueFlags": unexpected_true_flags,
        },
    }


def _build_report(payload: dict[str, Any]) -> dict[str, Any]:
    checks = [
        _required_fields_check(payload),
        _target_safety_check(payload),
        _timing_and_metrics_check(payload),
        _verification_queries_check(payload),
        _sanitization_check(payload),
        _launch_claim_check(payload),
        _outcome_check(payload),
        _validator_safety_check(payload),
    ]
    passed = all(check["status"] == "pass" for check in checks)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "finalStatus": "EVIDENCE-READY" if passed else "NO-GO",
        "launchApproved": False,
        "runtimeBehaviorChanged": False,
        "databaseCommandsRunByValidator": False,
        "networkCallsEnabled": False,
        "productionStorageTouched": False,
        "artifactSummary": {
            "drillId": str(payload.get("drillId") or ""),
            "environment": str(payload.get("environment") or ""),
            "outcome": str(payload.get("outcome") or ""),
            "verificationQueryCount": len(payload.get("verificationQueries") or [])
            if isinstance(payload.get("verificationQueries"), list)
            else 0,
        },
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate sanitized restore/PITR operator evidence JSON.")
    parser.add_argument("--artifact", required=True, help="Path to sanitized external restore/PITR evidence JSON.")
    args = parser.parse_args(argv)

    payload = _load_artifact(args.artifact)
    report = _build_report(payload)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["finalStatus"] == "EVIDENCE-READY" else 1


if __name__ == "__main__":
    sys.exit(main())
