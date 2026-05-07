#!/usr/bin/env python3
"""Validate sanitized rollback rehearsal evidence for release review.

This helper consumes synthetic or operator-sanitized JSON only. It does not
read environment files, inspect production data, call external services, change
git history, run deployment commands, or touch databases.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "wolfystock_rollback_rehearsal_evidence_v1"
INPUT_SCHEMA_VERSION = "wolfystock_rollback_rehearsal_evidence_input_v1"

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
    "log_body",
    "password",
    "private_key",
    "provider_payload",
    "raw_log",
    "rawlog",
    "raw_payload",
    "raw_response",
    "rawresponse",
    "response_body",
    "responsebody",
    "session",
    "token",
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
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9_]{24,}|xox[baprs]-[A-Za-z0-9-]{20,})\b"),
    re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
)
FORBIDDEN_DEFAULT_COMMAND_PATTERNS = (
    re.compile(r"\bgit\s+reset\b", re.IGNORECASE),
    re.compile(r"\bgit\s+push\s+.*--force", re.IGNORECASE),
    re.compile(r"\b(?:alembic|flask|django-admin|manage\.py)\s+(?:downgrade|migrate\s+.*rollback)\b", re.IGNORECASE),
    re.compile(r"\b(?:drop|truncate)\s+(?:table|database|schema)\b", re.IGNORECASE),
    re.compile(r"\b(?:restore|promote|failover)\s+production\b", re.IGNORECASE),
    re.compile(r"\b(?:kubectl|helm|fly|vercel|netlify|railway|terraform|pulumi)\s+.*\b(?:deploy|apply|destroy|rollback)\b", re.IGNORECASE),
    re.compile(r"\bdocker\s+compose\s+.*\b(?:up|down|rm)\b", re.IGNORECASE),
)
ROLLBACK_GROUPS = {
    "security/auth",
    "rbac",
    "options",
    "data_pipeline",
    "cost/quota",
    "provider_circuit",
    "db/schema",
    "frontend-only",
    "docs-only",
}
SAFE_GATE_STATUSES = {"pass", "passed", "blocked", "failed", "not_run", "not_applicable", "review_only", "no_go", "no-go"}


def _empty_evidence() -> dict[str, Any]:
    return {
        "schemaVersion": INPUT_SCHEMA_VERSION,
        "mode": "synthetic_empty",
        "releaseReference": {},
        "operator": {},
        "gateStatus": {},
        "rollbackPlan": {},
        "verificationSteps": [],
        "localGeneration": {},
    }


def _load_evidence(path: str | None) -> dict[str, Any]:
    if not path:
        return _empty_evidence()
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"[FAIL] Evidence file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[FAIL] Evidence file is not valid JSON: {exc}")
    if not isinstance(payload, dict):
        raise SystemExit("[FAIL] Evidence file must contain a JSON object")
    return payload


def _status(ok: bool) -> str:
    return "pass" if ok else "fail"


def _bool(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is True


def _false(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is False


def _safe_text(value: str) -> bool:
    return value.strip().lower() in SAFE_TEXT_VALUES


def _path_join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _find_unsafe_values(value: Any, *, path: str = "") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            nested_path = _path_join(path, key_text)
            normalized_key = key_text.lower().replace("-", "_")
            if isinstance(nested, str) and any(marker in normalized_key for marker in SENSITIVE_KEY_MARKERS):
                if not _safe_text(nested):
                    findings.append({"path": nested_path, "reasonCode": "sensitive_key_contains_value"})
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
                break
    return findings


def _find_forbidden_default_commands(value: Any, *, path: str = "") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            findings.extend(_find_forbidden_default_commands(nested, path=_path_join(path, str(key))))
        return findings
    if isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_find_forbidden_default_commands(nested, path=f"{path}[{index}]"))
        return findings
    if isinstance(value, str):
        for pattern in FORBIDDEN_DEFAULT_COMMAND_PATTERNS:
            if pattern.search(value):
                findings.append({"path": path or "$", "reasonCode": "forbidden_default_command"})
                break
    return findings


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    normalized = value.strip().replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return True


def _safe_label(value: Any) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}", str(value or "")))


def _metadata_check(payload: dict[str, Any]) -> dict[str, Any]:
    reference = payload.get("releaseReference") if isinstance(payload.get("releaseReference"), dict) else {}
    operator = payload.get("operator") if isinstance(payload.get("operator"), dict) else {}
    gate = payload.get("gateStatus") if isinstance(payload.get("gateStatus"), dict) else {}

    commit = str(reference.get("commit") or "")
    tag = str(reference.get("tag") or "")
    branch = str(reference.get("branch") or "")
    gate_values = {
        str(key): str(value).strip().lower()
        for key, value in gate.items()
        if isinstance(value, str)
    }

    issues: list[str] = []
    if not re.fullmatch(r"[0-9a-f]{7,40}", commit):
        issues.append("commit_missing_or_invalid")
    if not tag or not _safe_label(tag):
        issues.append("tag_missing_or_invalid")
    if branch != "main":
        issues.append("branch_not_main")
    if not _valid_timestamp(operator.get("timestamp")):
        issues.append("operator_timestamp_missing_or_invalid")
    if not str(operator.get("actorLabel") or "").strip():
        issues.append("operator_label_missing")
    if not gate_values:
        issues.append("gate_status_missing")
    unsupported_gate_values = [
        f"{key}:{value}"
        for key, value in sorted(gate_values.items())
        if value not in SAFE_GATE_STATUSES
    ]
    if unsupported_gate_values:
        issues.append("gate_status_unsupported")
    if gate.get("launchGo") is True or str(gate.get("launchDecision") or "").strip().upper() == "GO":
        issues.append("launch_go_not_allowed")

    return {
        "id": "rollback_rehearsal_metadata_is_complete",
        "status": _status(not issues),
        "evidence": {
            "issues": issues,
            "commitRecorded": bool(commit),
            "tagRecorded": bool(tag),
            "operatorTimestampRecorded": _valid_timestamp(operator.get("timestamp")),
            "gateStatusKeys": sorted(gate_values),
            "launchGo": gate.get("launchGo") is True,
            "unsupportedGateValues": unsupported_gate_values,
        },
    }


def _rollback_plan_check(payload: dict[str, Any]) -> dict[str, Any]:
    plan = payload.get("rollbackPlan") if isinstance(payload.get("rollbackPlan"), dict) else {}
    group = str(plan.get("rollbackGroup") or "").strip().lower().replace("-", "_")
    if group == "frontend_only":
        group = "frontend-only"
    if group == "docs_only":
        group = "docs-only"

    required_true = (
        "dryRunRehearsal",
        "operatorApprovalRequired",
        "diffReviewRequired",
        "dataImpactReviewed",
        "verificationRequiredBeforeCompletion",
    )
    required_false = (
        "realExecutionApproved",
        "destructiveActionDefault",
        "gitHistoryRewriteAllowed",
        "productionDatabaseActionDefault",
        "deploymentCommandDefault",
    )
    missing_true = [key for key in required_true if not _bool(plan, key)]
    unsafe_false = [key for key in required_false if not _false(plan, key)]
    command_findings = _find_forbidden_default_commands(plan.get("defaultCommands", []))
    issues = list(missing_true) + unsafe_false
    if group not in ROLLBACK_GROUPS:
        issues.append("rollback_group_missing_or_unknown")
    if not str(plan.get("rollbackTarget") or "").strip():
        issues.append("rollback_target_missing")
    if command_findings:
        issues.append("forbidden_default_command")

    return {
        "id": "rollback_plan_is_dry_run_operator_driven",
        "status": _status(not issues),
        "evidence": {
            "issues": issues,
            "rollbackGroup": group or "missing",
            "missingRequiredTrueFlags": missing_true,
            "unsafeDefaultFlags": unsafe_false,
            "forbiddenDefaultCommandCount": len(command_findings),
            "forbiddenDefaultCommandFindings": command_findings[:20],
            "realExecutionApproved": bool(plan.get("realExecutionApproved")),
            "destructiveActionDefault": bool(plan.get("destructiveActionDefault")),
        },
    }


def _verification_steps_check(payload: dict[str, Any]) -> dict[str, Any]:
    steps = payload.get("verificationSteps") if isinstance(payload.get("verificationSteps"), list) else []
    safe_steps: list[str] = []
    unsafe_steps = 0
    required_step_types = {"focused_tests", "secret_scan", "diff_check"}
    covered_step_types: set[str] = set()
    for item in steps:
        if not isinstance(item, dict):
            unsafe_steps += 1
            continue
        step_type = str(item.get("type") or "").strip().lower()
        command = str(item.get("command") or "").strip()
        expected = str(item.get("expectedResult") or "").strip()
        if step_type:
            covered_step_types.add(step_type)
        if not step_type or not command or not expected:
            unsafe_steps += 1
            continue
        if _find_forbidden_default_commands(command):
            unsafe_steps += 1
            continue
        safe_steps.append(step_type)
    missing_types = sorted(required_step_types - covered_step_types)
    ok = unsafe_steps == 0 and not missing_types and len(safe_steps) >= len(required_step_types)
    return {
        "id": "verification_steps_are_offline_and_bounded",
        "status": _status(ok),
        "evidence": {
            "stepCount": len(steps),
            "safeStepCount": len(safe_steps),
            "unsafeStepCount": unsafe_steps,
            "requiredStepTypes": sorted(required_step_types),
            "missingStepTypes": missing_types,
        },
    }


def _sanitization_check(payload: dict[str, Any]) -> dict[str, Any]:
    findings = _find_unsafe_values(payload)
    return {
        "id": "rollback_evidence_contains_no_sensitive_values",
        "status": _status(not findings),
        "evidence": {
            "unsafeFindingCount": len(findings),
            "findings": findings[:20],
            "findingValuesIncluded": False,
        },
    }


def _local_generation_check(payload: dict[str, Any]) -> dict[str, Any]:
    local = payload.get("localGeneration") if isinstance(payload.get("localGeneration"), dict) else {}
    required_false = (
        "externalServicesCalled",
        "networkCallsEnabled",
        "productionSecretsRead",
        "productionDataPathsRead",
        "runtimeBehaviorChanged",
        "deploymentCommandsRun",
        "databaseActionsRun",
        "gitHistoryChanged",
    )
    unsafe_flags = [key for key in required_false if not _false(local, key)]
    ok = not unsafe_flags and _bool(local, "stableJsonOutput")
    return {
        "id": "local_rehearsal_generation_is_non_destructive",
        "status": _status(ok),
        "evidence": {
            "unsafeFlags": unsafe_flags,
            "stableJsonOutput": _bool(local, "stableJsonOutput"),
            "externalServicesCalled": bool(local.get("externalServicesCalled")),
            "deploymentCommandsRun": bool(local.get("deploymentCommandsRun")),
            "databaseActionsRun": bool(local.get("databaseActionsRun")),
            "gitHistoryChanged": bool(local.get("gitHistoryChanged")),
        },
    }


def build_summary(payload: dict[str, Any]) -> dict[str, Any]:
    checks = [
        _metadata_check(payload),
        _rollback_plan_check(payload),
        _verification_steps_check(payload),
        _sanitization_check(payload),
        _local_generation_check(payload),
    ]
    blockers = [
        {"id": check["id"], "reason": "required_rollback_rehearsal_evidence_missing_or_unsafe"}
        for check in checks
        if check["status"] != "pass"
    ]
    final_status = "EVIDENCE-READY" if not blockers else "NO-GO"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "inputSchemaVersion": payload.get("schemaVersion") or "unknown",
        "mode": str(payload.get("mode") or "operator_sanitized"),
        "finalStatus": final_status,
        "releaseApproved": False,
        "launchApproved": False,
        "message": (
            "Rollback rehearsal evidence is ready for operator review; launch approval remains manual."
            if final_status == "EVIDENCE-READY"
            else "Rollback rehearsal evidence is incomplete or unsafe; launch remains blocked."
        ),
        "checks": checks,
        "blockers": blockers,
        "sanitization": {
            "databaseActionsRun": False,
            "deploymentCommandsRun": False,
            "externalServicesCalled": False,
            "gitHistoryChanged": False,
            "networkCallsEnabled": False,
            "productionDataPathsRead": False,
            "productionSecretsRead": False,
            "rawPayloadsIncluded": False,
            "runtimeBehaviorChanged": False,
            "secretValuesIncluded": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate sanitized rollback rehearsal evidence JSON.")
    parser.add_argument("--evidence", help="Synthetic or operator-sanitized rollback rehearsal evidence JSON.")
    parser.add_argument(
        "--allow-no-go",
        action="store_true",
        help="Return exit 0 even when evidence keeps finalStatus as NO-GO.",
    )
    args = parser.parse_args(argv)

    payload = _load_evidence(args.evidence)
    summary = build_summary(payload)
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    if summary["finalStatus"] == "NO-GO" and not args.allow_no_go:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
