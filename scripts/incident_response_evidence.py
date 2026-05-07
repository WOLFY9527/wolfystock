#!/usr/bin/env python3
"""Validate sanitized incident-response evidence for launch readiness review.

This helper consumes synthetic or operator-sanitized JSON. It does not read
real environment files, inspect production data paths, mutate runtime behavior,
or call external services.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "wolfystock_incident_response_evidence_v1"
INPUT_SCHEMA_VERSION = "wolfystock_incident_response_evidence_input_v1"

REQUIRED_ADMIN_FAMILIES = (
    "admin_security",
    "admin_cost",
    "admin_provider",
    "admin_quota",
)
REQUIRED_FAILURE_REASON_COUNT = 3

SAFE_TEXT_VALUES = {
    "",
    "***",
    "********",
    "[redacted]",
    "redacted",
    "<redacted>",
    "masked",
    "missing",
    "present",
    "sanitized",
    "none",
}
SENSITIVE_KEY_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "dsn",
    "password",
    "private_key",
    "session_id",
    "session_token",
    "token",
    "webhook_url",
)
SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"([?&](?:api[-_]?key|apikey|access_token|token|secret|password|cookie)=)(?!\*{3}|redacted)[^&#\s]+", re.IGNORECASE),
    re.compile(r"\b(?:api[-_]?key|apikey|access_token|token|secret|password|cookie|dsn)\s*[=:]\s*(?!\*{3}|redacted\b)[^\s,;&]+", re.IGNORECASE),
    re.compile(r"\bAuthorization\s*:\s*Bearer\s+(?!\*{3}|redacted\b)[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\bBearer\s+(?!\*{3}|redacted\b)[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\b(?:postgres|postgresql|mysql|redis)://[^:/@\s]+:[^@\s]+@", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
)


def _empty_evidence() -> dict[str, Any]:
    return {
        "schemaVersion": INPUT_SCHEMA_VERSION,
        "mode": "synthetic_empty",
        "adminAuditEvidence": {"events": []},
        "cleanupEvidence": {},
        "failureEvidence": {},
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


def _normalize_family(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


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


def _admin_audit_check(payload: dict[str, Any]) -> dict[str, Any]:
    audit = payload.get("adminAuditEvidence") if isinstance(payload.get("adminAuditEvidence"), dict) else {}
    events = audit.get("events") if isinstance(audit.get("events"), list) else []
    family_evidence: dict[str, dict[str, Any]] = {}
    unsafe_events = 0
    for item in events:
        if not isinstance(item, dict):
            unsafe_events += 1
            continue
        family = _normalize_family(item.get("family"))
        if family not in REQUIRED_ADMIN_FAMILIES:
            continue
        event_ok = (
            _bool(item, "actorIncluded")
            and _bool(item, "outcomeIncluded")
            and _bool(item, "sanitized")
            and _false(item, "rawPayloadIncluded")
            and _false(item, "secretValuesIncluded")
            and str(item.get("action") or "").strip() != ""
        )
        if event_ok:
            family_evidence[family] = {
                "action": str(item.get("action")),
                "actorIncluded": True,
                "outcomeIncluded": True,
                "sanitized": True,
            }
        else:
            unsafe_events += 1
    missing = [family for family in REQUIRED_ADMIN_FAMILIES if family not in family_evidence]
    ok = not missing and unsafe_events == 0
    return {
        "id": "admin_critical_actions_emit_sanitized_audit_evidence",
        "status": _status(ok),
        "evidence": {
            "requiredFamilies": list(REQUIRED_ADMIN_FAMILIES),
            "coveredFamilies": sorted(family_evidence),
            "missingFamilies": missing,
            "unsafeEventCount": unsafe_events,
            "eventsByFamily": family_evidence,
        },
    }


def _incident_sanitization_check(payload: dict[str, Any]) -> dict[str, Any]:
    findings = _find_unsafe_values(payload)
    return {
        "id": "incident_pack_contains_no_secret_values",
        "status": _status(not findings),
        "evidence": {
            "unsafeFindingCount": len(findings),
            "findings": findings[:20],
            "findingValuesIncluded": False,
        },
    }


def _cleanup_check(payload: dict[str, Any]) -> dict[str, Any]:
    cleanup = payload.get("cleanupEvidence") if isinstance(payload.get("cleanupEvidence"), dict) else {}
    required_true = (
        "dryRunDefaultVerified",
        "explicitExecuteRequired",
        "previewBeforeDelete",
        "minimumRetentionProtected",
        "sanitizedAuditTrail",
    )
    missing_true = [key for key in required_true if not _bool(cleanup, key)]
    ok = not missing_true and _false(cleanup, "destructiveByDefault")
    return {
        "id": "cleanup_and_retention_are_preview_first",
        "status": _status(ok),
        "evidence": {
            "missingRequiredTrueFlags": missing_true,
            "destructiveByDefault": bool(cleanup.get("destructiveByDefault")),
            "explicitActionRequired": _bool(cleanup, "explicitExecuteRequired"),
            "sanitizedAuditTrail": _bool(cleanup, "sanitizedAuditTrail"),
        },
    }


def _failure_path_check(payload: dict[str, Any]) -> dict[str, Any]:
    failure = payload.get("failureEvidence") if isinstance(payload.get("failureEvidence"), dict) else {}
    required_true = (
        "providerFailureSanitized",
        "notificationFailureSanitized",
        "releaseCheckFailureSanitized",
        "rawTracebacksExcluded",
        "rawResponseBodiesExcluded",
    )
    missing_true = [key for key in required_true if not _bool(failure, key)]
    reason_codes = failure.get("actionableReasonCodes") if isinstance(failure.get("actionableReasonCodes"), list) else []
    safe_reason_codes = [
        str(item)
        for item in reason_codes
        if re.fullmatch(r"[a-z0-9_.:-]+", str(item or ""))
    ]
    ok = not missing_true and len(safe_reason_codes) >= REQUIRED_FAILURE_REASON_COUNT and len(safe_reason_codes) == len(reason_codes)
    return {
        "id": "failure_paths_emit_actionable_sanitized_evidence",
        "status": _status(ok),
        "evidence": {
            "missingRequiredTrueFlags": missing_true,
            "actionableReasonCodeCount": len(safe_reason_codes),
            "requiredReasonCodeCount": REQUIRED_FAILURE_REASON_COUNT,
            "reasonCodesStable": len(safe_reason_codes) == len(reason_codes),
            "rawTracebacksExcluded": _bool(failure, "rawTracebacksExcluded"),
            "rawResponseBodiesExcluded": _bool(failure, "rawResponseBodiesExcluded"),
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
    )
    unsafe_flags = [key for key in required_false if not _false(local, key)]
    ok = not unsafe_flags and _bool(local, "stableJsonOutput")
    return {
        "id": "local_evidence_generation_is_safe",
        "status": _status(ok),
        "evidence": {
            "unsafeFlags": unsafe_flags,
            "stableJsonOutput": _bool(local, "stableJsonOutput"),
            "externalServicesCalled": bool(local.get("externalServicesCalled")),
            "productionSecretsRead": bool(local.get("productionSecretsRead")),
            "productionDataPathsRead": bool(local.get("productionDataPathsRead")),
            "runtimeBehaviorChanged": bool(local.get("runtimeBehaviorChanged")),
        },
    }


def build_summary(payload: dict[str, Any]) -> dict[str, Any]:
    checks = [
        _admin_audit_check(payload),
        _incident_sanitization_check(payload),
        _cleanup_check(payload),
        _failure_path_check(payload),
        _local_generation_check(payload),
    ]
    blockers = [
        {
            "id": check["id"],
            "reason": "required_incident_response_evidence_missing_or_unsafe",
        }
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
        "message": (
            "Incident-response evidence is ready for release review; launch approval remains manual."
            if final_status == "EVIDENCE-READY"
            else "Incident-response evidence is incomplete or unsafe; public launch remains blocked."
        ),
        "checks": checks,
        "blockers": blockers,
        "sanitization": {
            "externalServicesCalled": False,
            "networkCallsEnabled": False,
            "productionDataPathsRead": False,
            "productionSecretsRead": False,
            "rawPayloadsIncluded": False,
            "runtimeBehaviorChanged": False,
            "secretValuesIncluded": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate sanitized incident-response evidence JSON.")
    parser.add_argument("--evidence", help="Synthetic or operator-sanitized incident evidence JSON.")
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
