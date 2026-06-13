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
REAL_DRILL_EVIDENCE_MODE = "real-isolated-drill"
ALLOWED_BACKUP_ARTIFACT_KINDS = {
    "encrypted-base-backup",
    "encrypted-snapshot",
    "base-backup-with-wal",
    "snapshot-with-wal",
}
ALLOWED_REFERENCE_KINDS = {
    "manifest",
    "operator-log",
    "real-drill-summary",
    "review-ticket",
    "smoke-summary",
    "validator-output",
}
ALLOWED_ROLLBACK_DECISIONS = {
    "rollback-not-required",
    "rollback-required",
    "manual-review-required",
}
ALLOWED_SMOKE_STATUSES = {"pass", "accepted"}
PLACEHOLDER_VALUES = {
    "review-ticket-label",
    "sanitized-operator-label",
    "staging-environment-label",
    "redacted-or-configured",
    "release-candidate-sha",
    "<review-ticket-label>",
    "<sanitized-operator-label>",
    "<staging-environment-label>",
    "<redacted-or-configured>",
    "<release-candidate-sha>",
}
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
    "user_name",
    "username",
    "webhook_url",
)
SENSITIVE_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "secret_like_value_detected",
        re.compile(
            r"([?&](?:api[-_]?key|apikey|access_token|token|secret|password|cookie|session)=)"
            r"(?!\*{3}|redacted)[^&#\s]+",
            re.IGNORECASE,
        ),
    ),
    (
        "secret_like_value_detected",
        re.compile(
            r"\b(?:api[-_]?key|apikey|access[-_]?token|token|secret|password|passwd|cookie|session|"
            r"dsn|database[-_]?url|db[-_]?url|connection[-_]?string)\s*"
            r"[=:]\s*(?!\*{3}|redacted\b)[^\s,;&]+",
            re.IGNORECASE,
        ),
    ),
    (
        "secret_like_value_detected",
        re.compile(r"\bAuthorization\s*:\s*Bearer\s+(?!\*{3}|redacted\b)[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    ),
    (
        "secret_like_value_detected",
        re.compile(r"\bBearer\s+(?!\*{3}|redacted\b)[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    ),
    (
        "raw_connection_string_detected",
        re.compile(r"\b(?:postgres|postgresql|mysql|redis)://", re.IGNORECASE),
    ),
    (
        "secret_like_value_detected",
        re.compile(r"\b(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9_]{24,}|xox[baprs]-[A-Za-z0-9-]{20,})\b"),
    ),
    (
        "secret_like_value_detected",
        re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    ),
    (
        "secret_like_value_detected",
        re.compile(r"\b(?:Traceback \(most recent call last\):|File \"[^\"]+\", line \d+, in |Exception:|Stack trace:)", re.IGNORECASE),
    ),
    (
        "private_hostname_detected",
        re.compile(
            r"\b(?:(?:prod(?:uction)?|primary|live)[a-z0-9.-]*(?:db|pg|postgres|rds|database)|"
            r"(?:db|pg|postgres|rds|database)[a-z0-9.-]*(?:prod(?:uction)?|primary|live)|"
            r"[a-z0-9.-]+\.(?:internal|local|corp|lan))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "sensitive_path_detected",
        re.compile(
            r"(^|[\s\"'=])(?:/Users/[^/\s]+|/home/[^/\s]+|/var/lib/postgresql|/etc/|/private/|"
            r"[A-Za-z]:\\(?:Users|Documents and Settings)\\)",
            re.IGNORECASE,
        ),
    ),
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
    re.compile(r"\bproduction[-_ ]?ready\b", re.IGNORECASE),
    re.compile(r"\bautomatic[-_ ]?go\b", re.IGNORECASE),
    re.compile(r"\brelease[-_ ]?approved\b", re.IGNORECASE),
    re.compile(r"^\s*GO\s*$", re.IGNORECASE),
)
LAUNCH_GO_KEYS = {
    "launchapproved",
    "launchgo",
    "launchready",
    "go",
    "goliveapproved",
    "productionready",
    "publiclaunchready",
    "releaseapproved",
    "releaseready",
}
REQUIRED_FIELDS = (
    "drillId",
    "evidenceMode",
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
    "isolatedTarget",
    "backupArtifactSummary",
    "pitrTarget",
    "restoreExecutionSummary",
    "postRestoreSmoke",
    "ownerIsolationSmoke",
    "rollbackDecisionPoint",
    "operatorApprovals",
    "sanitizedArtifactReferences",
)
SAFE_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,159}$")
LOCAL_PRELIGHT_MARKER_KEYS = {
    "dryrunonly",
    "fixtureonly",
    "localonly",
    "localonlydryrun",
    "mockonly",
    "preflightonly",
    "reviewonly",
    "syntheticonly",
}


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


def _safe_label_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_safe_label(item) and not _is_placeholder_value(item) for item in value)


def _is_placeholder_value(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    lowered = text.lower()
    if lowered in PLACEHOLDER_VALUES:
        return True
    return text.startswith("<") and text.endswith(">") and not _safe_text(text)


def _safe_real_label(value: Any) -> bool:
    return _safe_label(value) and not _is_placeholder_value(value)


def _section(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _non_empty_dict(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def _non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def _valid_ref_item(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    kind = str(item.get("kind") or "")
    return (
        kind in ALLOWED_REFERENCE_KINDS
        and _safe_real_label(item.get("label"))
        and _safe_real_label(item.get("ref"))
    )


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
            if normalized_key in {"path", "file_path", "backup_path", "dump_path", "artifact_path", "raw_path"}:
                if isinstance(nested, str) and not _safe_text(nested):
                    findings.append({"path": nested_path, "reasonCode": "sensitive_path_detected"})
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
        for reason_code, pattern in SENSITIVE_VALUE_PATTERNS:
            if pattern.search(value):
                findings.append({"path": path or "$", "reasonCode": reason_code})
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


def _find_placeholder_markers(value: Any, *, path: str = "") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            nested_path = _path_join(path, str(key))
            if _normalize_key(str(key)) == "templateplaceholders":
                findings.append({"path": nested_path, "reasonCode": "template_placeholder_block_present"})
                continue
            findings.extend(_find_placeholder_markers(nested, path=nested_path))
        return findings
    if isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_find_placeholder_markers(nested, path=f"{path}[{index}]"))
        return findings
    if _is_placeholder_value(value):
        findings.append({"path": path or "$", "reasonCode": "placeholder_value_detected"})
    return findings


def _find_local_preflight_markers(value: Any, *, path: str = "") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            nested_path = _path_join(path, str(key))
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized_key in LOCAL_PRELIGHT_MARKER_KEYS and nested is True:
                findings.append({"path": nested_path, "reasonCode": "local_preflight_marker_not_real_drill"})
                continue
            findings.extend(_find_local_preflight_markers(nested, path=nested_path))
        return findings
    if isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_find_local_preflight_markers(nested, path=f"{path}[{index}]"))
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


def _isolated_target_summary_check(payload: dict[str, Any]) -> dict[str, Any]:
    target = _section(payload.get("isolatedTarget"))
    target_label_ok = _safe_real_label(target.get("targetLabel"))
    target_matches = target.get("targetLabel") == payload.get("restoreTarget")
    environment = str(target.get("environment") or "")
    environment_ok = environment in ALLOWED_ENVIRONMENTS and environment == payload.get("environment")
    isolation_ref_ok = _safe_real_label(target.get("isolationBoundaryRef"))
    production_touched = target.get("productionStorageTouched") is True
    ok = target_label_ok and target_matches and environment_ok and isolation_ref_ok and not production_touched
    return {
        "id": "isolated_target_summary_is_sanitized_and_non_production",
        "status": _status(ok),
        "evidence": {
            "targetLabelSanitized": target_label_ok,
            "matchesTopLevelRestoreTarget": target_matches,
            "environmentAccepted": environment_ok,
            "isolationBoundaryRefSanitized": isolation_ref_ok,
            "productionStorageTouched": production_touched,
        },
    }


def _real_drill_required_sections_check(payload: dict[str, Any]) -> dict[str, Any]:
    section_specs = {
        "isolatedTarget": _non_empty_dict,
        "backupArtifactSummary": _non_empty_dict,
        "pitrTarget": _non_empty_dict,
        "restoreExecutionSummary": _non_empty_dict,
        "postRestoreSmoke": _non_empty_dict,
        "ownerIsolationSmoke": _non_empty_dict,
        "rollbackDecisionPoint": _non_empty_dict,
        "operatorApprovals": _non_empty_list,
        "sanitizedArtifactReferences": _non_empty_list,
    }
    invalid_sections = [
        field
        for field, validator in section_specs.items()
        if field in payload and not validator(payload.get(field))
    ]
    missing_sections = [field for field in section_specs if field not in payload]
    ok = not missing_sections and not invalid_sections
    return {
        "id": "real_drill_required_sections_are_complete",
        "status": _status(ok),
        "evidence": {
            "missingSections": missing_sections,
            "invalidSections": invalid_sections,
        },
    }


def _real_drill_mode_check(payload: dict[str, Any]) -> dict[str, Any]:
    evidence_mode = str(payload.get("evidenceMode") or "")
    placeholder_findings = _find_placeholder_markers(payload)
    local_preflight_findings = _find_local_preflight_markers(payload)
    ok = evidence_mode == REAL_DRILL_EVIDENCE_MODE and not placeholder_findings and not local_preflight_findings
    return {
        "id": "real_drill_evidence_not_local_preflight_or_template",
        "status": _status(ok),
        "evidence": {
            "evidenceMode": evidence_mode if evidence_mode == REAL_DRILL_EVIDENCE_MODE else "invalid",
            "placeholderFindingCount": len(placeholder_findings),
            "localPreflightFindingCount": len(local_preflight_findings),
            "findings": (placeholder_findings + local_preflight_findings)[:20],
        },
    }


def _pitr_target_summary_check(payload: dict[str, Any]) -> dict[str, Any]:
    target = _section(payload.get("pitrTarget"))
    target_timestamp_ok = (
        _valid_timestamp(target.get("targetTimestamp"))
        and target.get("targetTimestamp") == payload.get("pitrTargetTimestamp")
    )
    target_ref_ok = _safe_real_label(target.get("targetRef"))
    replay_ref_ok = _safe_real_label(target.get("walReplaySummaryRef"))
    ok = target_timestamp_ok and target_ref_ok and replay_ref_ok
    return {
        "id": "pitr_target_summary_is_sanitized_and_bounded",
        "status": _status(ok),
        "evidence": {
            "matchesTopLevelPitrTargetTimestamp": target_timestamp_ok,
            "targetRefSanitized": target_ref_ok,
            "walReplaySummaryRefSanitized": replay_ref_ok,
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


def _backup_artifact_summary_check(payload: dict[str, Any]) -> dict[str, Any]:
    summary = _section(payload.get("backupArtifactSummary"))
    artifact_ref_ok = _safe_real_label(summary.get("artifactRef"))
    kind = str(summary.get("artifactKind") or "")
    kind_ok = kind in ALLOWED_BACKUP_ARTIFACT_KINDS
    wal_ref_ok = _safe_real_label(summary.get("walArchiveSummaryRef"))
    source_label_ok = _safe_real_label(summary.get("sourceEnvironmentLabel"))
    raw_path_included = summary.get("rawPathIncluded") is True
    top_level_matches = summary.get("artifactRef") == payload.get("backupArtifactRef")
    ok = artifact_ref_ok and kind_ok and wal_ref_ok and source_label_ok and not raw_path_included and top_level_matches
    return {
        "id": "backup_artifact_summary_is_sanitized_and_bounded",
        "status": _status(ok),
        "evidence": {
            "artifactRefSanitized": artifact_ref_ok,
            "artifactKindAccepted": kind_ok,
            "walArchiveSummaryRefSanitized": wal_ref_ok,
            "sourceEnvironmentLabelSanitized": source_label_ok,
            "rawPathIncluded": raw_path_included,
            "matchesTopLevelBackupArtifactRef": top_level_matches,
        },
    }


def _restore_execution_summary_check(payload: dict[str, Any]) -> dict[str, Any]:
    summary = _section(payload.get("restoreExecutionSummary"))
    restore_executed = payload.get("restoreCommandExecuted") is True and summary.get("restoreCommandExecuted") is True
    outside_validator = summary.get("executedOutsideValidator") is True
    local_dry_run = summary.get("localOnlyDryRun") is True
    production_mutation = summary.get("productionDbMutation") is True
    destructive_prod = (
        payload.get("destructiveProductionCommandExecuted") is True
        or summary.get("destructiveProductionCommandExecuted") is True
    )
    command_ref_ok = _safe_real_label(summary.get("commandSummaryRef"))
    ok = restore_executed and outside_validator and not local_dry_run and not production_mutation and not destructive_prod and command_ref_ok
    return {
        "id": "restore_execution_summary_proves_real_isolated_drill",
        "status": _status(ok),
        "evidence": {
            "restoreCommandExecuted": restore_executed,
            "executedOutsideValidator": outside_validator,
            "localOnlyDryRun": local_dry_run,
            "productionDbMutation": production_mutation,
            "destructiveProductionCommandExecuted": destructive_prod,
            "commandSummaryRefSanitized": command_ref_ok,
        },
    }


def _post_restore_smoke_check(payload: dict[str, Any]) -> dict[str, Any]:
    smoke = _section(payload.get("postRestoreSmoke"))
    app_status = str(smoke.get("appBootReadiness") or "")
    schema_status = str(smoke.get("schemaCompatibility") or "")
    summaries_ok = _safe_label_list(smoke.get("sampledQuerySummaries"))
    ok = app_status in ALLOWED_SMOKE_STATUSES and schema_status in ALLOWED_SMOKE_STATUSES and summaries_ok
    return {
        "id": "post_restore_smoke_summaries_are_present",
        "status": _status(ok),
        "evidence": {
            "appBootReadiness": app_status if app_status in ALLOWED_SMOKE_STATUSES else "invalid",
            "schemaCompatibility": schema_status if schema_status in ALLOWED_SMOKE_STATUSES else "invalid",
            "sampledQuerySummariesSanitized": summaries_ok,
        },
    }


def _owner_isolation_smoke_check(payload: dict[str, Any]) -> dict[str, Any]:
    smoke = _section(payload.get("ownerIsolationSmoke"))
    owner_scope_checked = smoke.get("ownerScopeChecked") is True
    cross_owner_blocked = smoke.get("crossOwnerAccessBlocked") is True
    sampled_refs_ok = _safe_label_list(smoke.get("sampledOwnerLabelRefs"))
    ok = owner_scope_checked and cross_owner_blocked and sampled_refs_ok
    return {
        "id": "owner_isolation_smoke_is_present",
        "status": _status(ok),
        "evidence": {
            "ownerScopeChecked": owner_scope_checked,
            "crossOwnerAccessBlocked": cross_owner_blocked,
            "sampledOwnerLabelRefsSanitized": sampled_refs_ok,
        },
    }


def _rollback_decision_point_check(payload: dict[str, Any]) -> dict[str, Any]:
    decision_point = _section(payload.get("rollbackDecisionPoint"))
    decision = str(decision_point.get("decision") or "")
    decision_ok = decision in ALLOWED_ROLLBACK_DECISIONS
    decided_at_ok = _valid_timestamp(decision_point.get("decidedAt"))
    decision_ref_ok = _safe_real_label(decision_point.get("decisionRef"))
    ok = decision_ok and decided_at_ok and decision_ref_ok
    return {
        "id": "rollback_decision_point_is_recorded",
        "status": _status(ok),
        "evidence": {
            "decision": decision if decision_ok else "invalid",
            "decidedAtValid": decided_at_ok,
            "decisionRefSanitized": decision_ref_ok,
        },
    }


def _operator_approvals_check(payload: dict[str, Any]) -> dict[str, Any]:
    approvals = payload.get("operatorApprovals")
    invalid_entries = 0
    approval_count = 0
    if isinstance(approvals, list):
        for item in approvals:
            approval_count += 1
            if not isinstance(item, dict):
                invalid_entries += 1
                continue
            if (
                not _safe_real_label(item.get("role"))
                or item.get("approved") is not True
                or not _valid_timestamp(item.get("approvedAt"))
                or not _safe_real_label(item.get("approvalRef"))
            ):
                invalid_entries += 1
    else:
        invalid_entries = 1
    ok = isinstance(approvals, list) and approval_count >= 2 and invalid_entries == 0
    return {
        "id": "operator_approvals_are_sanitized",
        "status": _status(ok),
        "evidence": {
            "approvalCount": approval_count,
            "minimumApprovalCount": 2,
            "invalidEntryCount": invalid_entries,
        },
    }


def _sanitized_artifact_references_check(payload: dict[str, Any]) -> dict[str, Any]:
    references = payload.get("sanitizedArtifactReferences")
    reference_count = 0
    invalid_entries = 0
    if isinstance(references, list):
        for item in references:
            reference_count += 1
            if not _valid_ref_item(item):
                invalid_entries += 1
    else:
        invalid_entries = 1
    ok = isinstance(references, list) and reference_count > 0 and invalid_entries == 0
    return {
        "id": "sanitized_artifact_references_are_bounded",
        "status": _status(ok),
        "evidence": {
            "referenceCount": reference_count,
            "invalidEntryCount": invalid_entries,
            "allowedKinds": sorted(ALLOWED_REFERENCE_KINDS),
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
        _isolated_target_summary_check(payload),
        _real_drill_required_sections_check(payload),
        _real_drill_mode_check(payload),
        _timing_and_metrics_check(payload),
        _backup_artifact_summary_check(payload),
        _pitr_target_summary_check(payload),
        _restore_execution_summary_check(payload),
        _post_restore_smoke_check(payload),
        _owner_isolation_smoke_check(payload),
        _rollback_decision_point_check(payload),
        _operator_approvals_check(payload),
        _sanitized_artifact_references_check(payload),
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
            "evidenceMode": str(payload.get("evidenceMode") or ""),
            "outcome": str(payload.get("outcome") or ""),
            "verificationQueryCount": len(payload.get("verificationQueries") or [])
            if isinstance(payload.get("verificationQueries"), list)
            else 0,
            "sanitizedArtifactReferenceCount": len(payload.get("sanitizedArtifactReferences") or [])
            if isinstance(payload.get("sanitizedArtifactReferences"), list)
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
