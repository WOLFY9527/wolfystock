#!/usr/bin/env python3
"""Validate sanitized provider operator evidence artifacts.

This helper is intentionally offline. It reads one operator-supplied JSON file,
emits a sanitized validation summary, and does not import provider adapters,
read environment files, open sockets, or change runtime routing/fallback state.
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


SCHEMA_VERSION = "wolfystock_provider_operator_evidence_validation_v1"
ALLOWED_ENVIRONMENTS = {"staging", "production-like", "sandbox"}
ALLOWED_CREDENTIAL_PRESENCE = {"configured", "missing", "redacted"}
ALLOWED_OUTCOMES = {"accepted", "rejected", "needs-review"}
REQUIRED_FIELDS = (
    "providerName",
    "environment",
    "operator",
    "observedAt",
    "probeMode",
    "networkCallsEnabled",
    "credentialPresence",
    "circuitState",
    "fallbackState",
    "outcome",
    "evidenceRedactionVersion",
    "notes",
)

UNSAFE_KEY_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "debug_payload",
    "debug_trace",
    "dsn",
    "password",
    "passwd",
    "private_key",
    "provider_payload",
    "raw_payload",
    "raw_request",
    "raw_request_body",
    "raw_response",
    "session",
    "set_cookie",
    "stack_trace",
    "token",
    "traceback",
)
UNSAFE_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "unsafe_marker",
        re.compile(
            r"\b(?:api[-_\s]?key|apikey|password|passwd|secret|cookie|session|bearer|"
            r"private key|dsn|authorization|set-cookie)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "unsafe_debug_marker",
        re.compile(
            r"\b(?:raw[_\s-]?(?:response|request|payload)|raw[_\s-]?request[_\s-]?body|"
            r"debug[_\s-]?payload|debug[_\s-]?trace|traceback|stack trace)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "credential_bearing_url",
        re.compile(r"\bhttps?://[^\s?#]+[?][^\s]+", re.IGNORECASE),
    ),
)
FORBIDDEN_LAUNCH_APPROVAL_PATTERNS = (
    re.compile(r"\bgo\b", re.IGNORECASE),
    re.compile(r"\blaunch[-_\s]?approved\b", re.IGNORECASE),
    re.compile(r"\bproduction[-_\s]?ready\b", re.IGNORECASE),
    re.compile(r"\bautomatic[-_\s]?go\b", re.IGNORECASE),
    re.compile(r"\brelease[-_\s]?approved\b", re.IGNORECASE),
)


def _parse_observed_at(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _state_summary_present(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return bool(str(value.get("state") or value.get("summary") or "").strip())
    return False


def _scan_unsafe_key(field: str, key: Any) -> list[dict[str, str]]:
    normalized_key = _normalize_key(key)
    if not any(marker in normalized_key for marker in UNSAFE_KEY_MARKERS):
        return []
    reason = "unsafe_debug_marker" if any(
        marker in normalized_key
        for marker in (
            "debug_payload",
            "debug_trace",
            "raw_payload",
            "raw_request",
            "raw_response",
            "stack_trace",
            "traceback",
        )
    ) else "unsafe_marker"
    return [_finding(field, reason)]


def _scan_unsafe_string(field: str, value: Any) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for reason_code, pattern in UNSAFE_VALUE_PATTERNS:
        if pattern.search(value):
            findings.append(_finding(field, reason_code))
            break
    for pattern in FORBIDDEN_LAUNCH_APPROVAL_PATTERNS:
        if pattern.search(value):
            findings.append(_finding(field, "launch_approval_claim_forbidden"))
            break
    return findings


def _find_unsafe_markers(value: Any) -> list[dict[str, str]]:
    return scan_json_tree(
        value,
        scan_key=_scan_unsafe_key,
        scan_string=_scan_unsafe_string,
        recurse_on_key_findings=False,
    )


def _validate_artifact(artifact: Any) -> tuple[list[dict[str, str]], dict[str, bool]]:
    findings: list[dict[str, str]] = []
    checks = {
        "requiredFieldsPresent": False,
        "schemaValuesValid": False,
        "unsafeMarkersAbsent": False,
        "networkCallsEnabledAcceptedOutcome": False,
    }
    if not isinstance(artifact, dict):
        return [_finding("$", "artifact_must_be_json_object")], checks

    for field in REQUIRED_FIELDS:
        if field not in artifact:
            findings.append(_finding(field, "missing_required_field"))
    checks["requiredFieldsPresent"] = not any(
        finding["reasonCode"] == "missing_required_field" for finding in findings
    )

    string_fields = ("providerName", "operator", "probeMode", "evidenceRedactionVersion", "notes")
    for field in string_fields:
        if field in artifact and not _non_empty_string(artifact.get(field)):
            findings.append(_finding(field, "invalid_string_field"))

    if artifact.get("environment") not in ALLOWED_ENVIRONMENTS:
        findings.append(_finding("environment", "invalid_environment"))
    if artifact.get("credentialPresence") not in ALLOWED_CREDENTIAL_PRESENCE:
        findings.append(_finding("credentialPresence", "invalid_credential_presence"))
    if artifact.get("outcome") not in ALLOWED_OUTCOMES:
        findings.append(_finding("outcome", "invalid_outcome"))
    if "observedAt" in artifact and not _parse_observed_at(artifact.get("observedAt")):
        findings.append(_finding("observedAt", "invalid_observed_at"))
    if "networkCallsEnabled" in artifact and not isinstance(artifact.get("networkCallsEnabled"), bool):
        findings.append(_finding("networkCallsEnabled", "invalid_boolean"))
    if "circuitState" in artifact and not _state_summary_present(artifact.get("circuitState")):
        findings.append(_finding("circuitState", "missing_state_summary"))
    if "fallbackState" in artifact and not _state_summary_present(artifact.get("fallbackState")):
        findings.append(_finding("fallbackState", "missing_state_summary"))

    if artifact.get("networkCallsEnabled") is True and artifact.get("outcome") != "accepted":
        findings.append(_finding("networkCallsEnabled", "network_calls_enabled_requires_accepted_outcome"))

    findings.extend(_find_unsafe_markers(artifact))
    checks["unsafeMarkersAbsent"] = not any(
        finding["reasonCode"] in {"unsafe_marker", "unsafe_debug_marker", "credential_bearing_url"}
        for finding in findings
    )
    checks["schemaValuesValid"] = not any(
        finding["reasonCode"].startswith("invalid_") or finding["reasonCode"] == "missing_state_summary"
        for finding in findings
    )
    checks["networkCallsEnabledAcceptedOutcome"] = not (
        artifact.get("networkCallsEnabled") is True and artifact.get("outcome") != "accepted"
    )
    return findings, checks


def _sanitized_artifact_summary(artifact: Any) -> dict[str, Any]:
    if not isinstance(artifact, dict):
        return {}
    return {
        "providerName": str(artifact.get("providerName") or "<missing>"),
        "environment": str(artifact.get("environment") or "<missing>"),
        "operator": str(artifact.get("operator") or "<missing>"),
        "observedAt": str(artifact.get("observedAt") or "<missing>"),
        "probeMode": str(artifact.get("probeMode") or "<missing>"),
        "networkCallsEnabled": bool(artifact.get("networkCallsEnabled"))
        if isinstance(artifact.get("networkCallsEnabled"), bool)
        else False,
        "credentialPresence": str(artifact.get("credentialPresence") or "<missing>"),
        "outcome": str(artifact.get("outcome") or "<missing>"),
        "evidenceRedactionVersion": str(artifact.get("evidenceRedactionVersion") or "<missing>"),
    }


def validate_provider_operator_evidence(artifact: Any) -> dict[str, Any]:
    findings, checks = _validate_artifact(artifact)
    passed = not findings
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "pass" if passed else "fail",
        "advisoryOnly": True,
        "runtimeBehaviorChanged": False,
        "networkCallsExecutedByValidator": False,
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
        description="Validate a sanitized provider operator evidence JSON artifact without provider calls."
    )
    parser.add_argument("artifact", help="Path to sanitized provider operator evidence JSON")
    args = parser.parse_args(argv)

    artifact = _load_json(Path(args.artifact))
    result = validate_provider_operator_evidence(artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
