#!/usr/bin/env python3
"""Validate sanitized WS2/SSE operator topology decision evidence offline.

This helper reads one operator-supplied JSON artifact, emits a sanitized
validation summary, and exits non-zero unless the artifact is structurally
sound and free of forbidden launch or secret-bearing content. It never imports
task queue runtime code, opens sockets, changes SSE/polling behavior, or wires
into launch acceptance.
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
    from evidence_safety import compact_key
    from evidence_safety import finding as _finding
    from evidence_safety import normalize_key as _normalize_key
    from evidence_safety import scan_json_tree
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from scripts.evidence_safety import compact_key
    from scripts.evidence_safety import finding as _finding
    from scripts.evidence_safety import normalize_key as _normalize_key
    from scripts.evidence_safety import scan_json_tree


SCHEMA_VERSION = "wolfystock_ws2_sse_operator_decision_validation_v1"
ARTIFACT_VERSION = "wolfystock_ws2_sse_operator_decision_evidence_v1"
REDACTION_VERSION = "ws2_sse_operator_decision_redaction_v1"
ALLOWED_TOPOLOGY_MODES = {
    "single-instance-sse",
    "polling-fallback",
    "external-broadcast-required",
    "needs-review",
}
ALLOWED_SSE_BROADCAST_SCOPES = {
    "process-local",
    "external-broadcast-required",
    "needs-review",
}
ALLOWED_OUTCOMES = {"accepted", "rejected", "needs-review"}
REQUIRED_FIELDS = (
    "artifactVersion",
    "environment",
    "operator",
    "observedAt",
    "topologyMode",
    "sseBroadcastScope",
    "pollingFallbackAccepted",
    "multiInstanceRiskAccepted",
    "userImpactSummary",
    "rollbackOrMitigationSummary",
    "outcome",
    "evidenceRedactionVersion",
)
SAFE_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@+-]{0,159}$")
URL_WITH_CREDENTIALS_PATTERN = re.compile(r"https?://[^/\s:@]+:[^@\s]+@[^/\s]+", re.IGNORECASE)
SECRET_VALUE_PATTERN = re.compile(
    r"\b(?:api[-_\s]?key|apikey|access[-_\s]?token|token|secret|password|passwd|"
    r"session|cookie|bearer|authorization|set-cookie|private key|dsn)\b",
    re.IGNORECASE,
)
RAW_DEBUG_VALUE_PATTERN = re.compile(
    r"\b(?:raw[_\s-]?(?:log|logs|payload|request|response|body)|debug[_\s-]?"
    r"(?:payload|trace)|traceback|stack trace|stacktrace)\b",
    re.IGNORECASE,
)
SENSITIVE_KEY_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "dsn",
    "password",
    "passwd",
    "private_key",
    "secret",
    "session",
    "set_cookie",
    "token",
)
RAW_DEBUG_KEY_MARKERS = (
    "debug_payload",
    "debug_trace",
    "provider_payload",
    "raw_body",
    "raw_log",
    "raw_logs",
    "raw_payload",
    "raw_request",
    "raw_response",
    "stack_trace",
    "stacktrace",
    "traceback",
)
LAUNCH_APPROVAL_TEXT_PATTERNS = (
    re.compile(r"\blaunch[-_\s]?approved\b", re.IGNORECASE),
    re.compile(r"\blaunch[-_\s]?go\b", re.IGNORECASE),
    re.compile(r"\bproduction[-_\s]?ready\b", re.IGNORECASE),
    re.compile(r"\bautomatic[-_\s]?go\b", re.IGNORECASE),
    re.compile(r"\brelease[-_\s]?approved\b", re.IGNORECASE),
    re.compile(r"\bgo\b", re.IGNORECASE),
)
LAUNCH_APPROVAL_KEYS = {
    "go",
    "golive",
    "goliveapproved",
    "launchapproved",
    "launchgo",
    "releaseapproved",
}
MULTI_INSTANCE_SSE_CLAIM_PATTERNS = (
    re.compile(r"\baccepted\s+multi[-_\s]?instance\s+sse\b", re.IGNORECASE),
    re.compile(r"\bmulti[-_\s]?instance\s+sse\b.{0,80}\bbroadcast[-_\s]?safe\b", re.IGNORECASE),
    re.compile(r"\bsse\b.{0,80}\bworks\s+across\s+instances\b", re.IGNORECASE),
    re.compile(r"\bcross[-_\s]?instance\s+sse\b.{0,80}\b(?:safe|accepted|ready)\b", re.IGNORECASE),
)
MULTI_INSTANCE_REVIEW_TERMS = (
    "external-broadcast-required",
    "external broadcast required",
    "needs-review",
    "needs review",
)


def _is_non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_safe_label(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if any(marker in text for marker in ("://", "/", "?", "#")):
        return False
    return bool(SAFE_LABEL_PATTERN.fullmatch(text))


def _is_iso_timestamp(value: Any) -> bool:
    if not _is_non_empty_text(value):
        return False
    try:
        datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _scan_value_key(field: str, key: Any) -> list[dict[str, str]]:
    normalized_key = _normalize_key(key)
    if any(marker in normalized_key for marker in RAW_DEBUG_KEY_MARKERS):
        return [_finding(field, "raw_debug_or_trace_marker_forbidden")]
    if any(marker in normalized_key for marker in SENSITIVE_KEY_MARKERS):
        return [_finding(field, "secret_or_cookie_marker_forbidden")]
    return []


def _scan_value_entry(field: str, key: Any, value: Any) -> list[dict[str, str]]:
    if compact_key(key) in LAUNCH_APPROVAL_KEYS and value is True:
        return [_finding(field, "launch_approval_claim_forbidden")]
    return []


def _scan_value_string(field: str, value: Any) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    text = value.strip()
    if not text:
        return findings
    if URL_WITH_CREDENTIALS_PATTERN.search(text):
        findings.append(_finding(field, "credential_url_forbidden"))
    if RAW_DEBUG_VALUE_PATTERN.search(text):
        findings.append(_finding(field, "raw_debug_or_trace_marker_forbidden"))
    if SECRET_VALUE_PATTERN.search(text):
        findings.append(_finding(field, "secret_or_cookie_marker_forbidden"))
    for pattern in LAUNCH_APPROVAL_TEXT_PATTERNS:
        if pattern.search(text):
            findings.append(_finding(field, "launch_approval_claim_forbidden"))
            break
    return findings


def _scan_value(value: Any, *, field: str = "$") -> list[dict[str, str]]:
    return scan_json_tree(
        value,
        field=field,
        scan_key=_scan_value_key,
        scan_entry=_scan_value_entry,
        scan_string=_scan_value_string,
        recurse_on_key_findings=False,
    )


def _has_forbidden_multi_instance_sse_claim(artifact: dict[str, Any]) -> bool:
    text_fields = (
        "topologyMode",
        "sseBroadcastScope",
        "userImpactSummary",
        "rollbackOrMitigationSummary",
    )
    combined = " ".join(str(artifact.get(field) or "") for field in text_fields).strip().lower()
    if not combined:
        return False
    if any(term in combined for term in MULTI_INSTANCE_REVIEW_TERMS):
        return False
    return any(pattern.search(combined) for pattern in MULTI_INSTANCE_SSE_CLAIM_PATTERNS)


def _validate_artifact(artifact: Any) -> tuple[list[dict[str, str]], dict[str, Any]]:
    findings: list[dict[str, str]] = []
    if not isinstance(artifact, dict):
        return [_finding("$", "artifact_must_be_json_object")], {}

    for field in REQUIRED_FIELDS:
        if field not in artifact:
            findings.append(_finding(field, "missing_required_field"))

    artifact_version = artifact.get("artifactVersion")
    environment = artifact.get("environment")
    operator = artifact.get("operator")
    observed_at = artifact.get("observedAt")
    topology_mode = str(artifact.get("topologyMode") or "").strip()
    sse_broadcast_scope = str(artifact.get("sseBroadcastScope") or "").strip()
    polling_fallback_accepted = artifact.get("pollingFallbackAccepted")
    multi_instance_risk_accepted = artifact.get("multiInstanceRiskAccepted")
    user_impact_summary = artifact.get("userImpactSummary")
    rollback_or_mitigation_summary = artifact.get("rollbackOrMitigationSummary")
    outcome = str(artifact.get("outcome") or "").strip()
    evidence_redaction_version = artifact.get("evidenceRedactionVersion")

    if artifact_version != ARTIFACT_VERSION:
        findings.append(_finding("artifactVersion", "invalid_artifact_version"))
    if not _is_safe_label(environment):
        findings.append(_finding("environment", "invalid_environment"))
    if not _is_safe_label(operator):
        findings.append(_finding("operator", "invalid_operator"))
    if not _is_iso_timestamp(observed_at):
        findings.append(_finding("observedAt", "invalid_observed_at"))
    if topology_mode not in ALLOWED_TOPOLOGY_MODES:
        findings.append(_finding("topologyMode", "invalid_topology_mode"))
    if sse_broadcast_scope not in ALLOWED_SSE_BROADCAST_SCOPES:
        findings.append(_finding("sseBroadcastScope", "invalid_sse_broadcast_scope"))
    if not isinstance(polling_fallback_accepted, bool):
        findings.append(_finding("pollingFallbackAccepted", "invalid_boolean"))
    if not isinstance(multi_instance_risk_accepted, bool):
        findings.append(_finding("multiInstanceRiskAccepted", "invalid_boolean"))
    if not _is_non_empty_text(user_impact_summary):
        findings.append(_finding("userImpactSummary", "missing_required_summary"))
    if not _is_non_empty_text(rollback_or_mitigation_summary):
        findings.append(_finding("rollbackOrMitigationSummary", "missing_required_summary"))
    if outcome not in ALLOWED_OUTCOMES:
        findings.append(_finding("outcome", "invalid_outcome"))
    if evidence_redaction_version != REDACTION_VERSION:
        findings.append(_finding("evidenceRedactionVersion", "invalid_redaction_version"))

    if outcome == "accepted":
        if topology_mode not in ALLOWED_TOPOLOGY_MODES:
            findings.append(_finding("topologyMode", "accepted_outcome_requires_explicit_topology_mode"))
        if topology_mode == "needs-review":
            findings.append(_finding("topologyMode", "accepted_outcome_cannot_use_needs_review_topology"))
        if topology_mode == "polling-fallback" and polling_fallback_accepted is not True:
            findings.append(_finding("pollingFallbackAccepted", "accepted_polling_fallback_requires_true"))
        if topology_mode == "single-instance-sse":
            if sse_broadcast_scope != "process-local":
                findings.append(_finding("sseBroadcastScope", "single_instance_sse_requires_process_local_scope"))
            if multi_instance_risk_accepted is not True:
                findings.append(_finding("multiInstanceRiskAccepted", "single_instance_sse_requires_explicit_risk_acceptance"))
        if topology_mode == "external-broadcast-required" and sse_broadcast_scope != "external-broadcast-required":
            findings.append(_finding("sseBroadcastScope", "external_broadcast_required_scope_mismatch"))

    if _has_forbidden_multi_instance_sse_claim(artifact):
        findings.append(_finding("userImpactSummary", "multi_instance_sse_acceptance_forbidden"))

    findings.extend(_scan_value(artifact))

    summary = {
        "artifactVersion": str(artifact_version or "<missing>"),
        "environment": str(environment or "<missing>") if _is_safe_label(environment) else "<invalid>",
        "operator": str(operator or "<missing>") if _is_safe_label(operator) else "<invalid>",
        "observedAt": str(observed_at or "<missing>"),
        "topologyMode": topology_mode or "<missing>",
        "sseBroadcastScope": sse_broadcast_scope or "<missing>",
        "pollingFallbackAccepted": polling_fallback_accepted if isinstance(polling_fallback_accepted, bool) else False,
        "multiInstanceRiskAccepted": multi_instance_risk_accepted if isinstance(multi_instance_risk_accepted, bool) else False,
        "outcome": outcome or "<missing>",
        "evidenceRedactionVersion": str(evidence_redaction_version or "<missing>"),
    }

    deduped_findings = sorted(
        {json.dumps(item, sort_keys=True): item for item in findings}.values(),
        key=lambda item: (item["field"], item["reasonCode"]),
    )
    return deduped_findings, summary


def validate_ws2_sse_operator_decision(artifact: Any) -> dict[str, Any]:
    findings, summary = _validate_artifact(artifact)
    passed = not findings
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "pass" if passed else "fail",
        "advisoryOnly": True,
        "launchAcceptanceIntegrated": False,
        "runtimeBehaviorChanged": False,
        "networkCallsExecutedByValidator": False,
        "checks": {
            "requiredFieldsPresent": not any(finding["reasonCode"] == "missing_required_field" for finding in findings),
            "topologyDecisionExplicit": not any(
                finding["reasonCode"]
                in {
                    "accepted_outcome_requires_explicit_topology_mode",
                    "accepted_outcome_cannot_use_needs_review_topology",
                    "invalid_topology_mode",
                    "invalid_sse_broadcast_scope",
                }
                for finding in findings
            ),
            "unsafeMultiInstanceSseClaimAbsent": not any(
                finding["reasonCode"] == "multi_instance_sse_acceptance_forbidden" for finding in findings
            ),
            "sanitizedValuesAbsent": not any(
                finding["reasonCode"]
                in {
                    "credential_url_forbidden",
                    "launch_approval_claim_forbidden",
                    "raw_debug_or_trace_marker_forbidden",
                    "secret_or_cookie_marker_forbidden",
                }
                for finding in findings
            ),
        },
        "artifact": summary,
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
    parser = argparse.ArgumentParser(description="Validate sanitized WS2/SSE operator decision evidence JSON offline.")
    parser.add_argument("artifact", help="Path to sanitized WS2/SSE operator decision evidence JSON")
    args = parser.parse_args(argv)

    artifact = _load_json(Path(args.artifact))
    result = validate_ws2_sse_operator_decision(artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
