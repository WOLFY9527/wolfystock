#!/usr/bin/env python3
"""Validate sanitized staging ingress operator evidence offline.

The checker reads one operator-supplied JSON artifact, emits a sanitized
validation summary, and exits non-zero unless the artifact is structurally
sound and free of forbidden launch-evidence content. It never makes network
calls, changes ingress/runtime behavior, or integrates with launch acceptance.
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


SCHEMA_VERSION = "wolfystock_staging_ingress_operator_evidence_validation_v1"
ARTIFACT_VERSION = "wolfystock_staging_ingress_operator_evidence_v1"
REDACTION_VERSION = "staging_ingress_operator_redaction_v1"
ALLOWED_ENVIRONMENTS = {"staging", "production-like-staging", "sandbox"}
ALLOWED_OUTCOMES = {"accepted", "rejected", "needs-review"}
SAFE_PLACEHOLDERS = {"", "<redacted>", "[redacted]", "redacted", "sanitized", "none"}
SUMMARY_FIELDS = (
    "authBoundaryResult",
    "securityHeaderSummary",
    "csrfOrStateMutationSummary",
    "publicSurfaceSummary",
    "rateLimitOrAbuseSummary",
)
REQUIRED_FIELDS = (
    "artifactVersion",
    "environment",
    "operator",
    "observedAt",
    "baseUrlLabel",
    "networkCallsEnabled",
    "checkedRoutes",
    "authBoundaryResult",
    "securityHeaderSummary",
    "csrfOrStateMutationSummary",
    "publicSurfaceSummary",
    "rateLimitOrAbuseSummary",
    "outcome",
    "evidenceRedactionVersion",
    "notes",
)

URL_WITH_CREDENTIALS_PATTERN = re.compile(r"https?://[^/\s:@]+:[^@\s]+@[^/\s]+", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://[^\s\"']+", re.IGNORECASE)
GO_CLAIM_PATTERN = re.compile(
    r"\bgo\b|launch[-_\s]?approved|production[-_\s]?ready|automatic[-_\s]?go|release[-_\s]?approved",
    re.IGNORECASE,
)
RAW_PAYLOAD_PATTERN = re.compile(
    r"\b(?:raw[_\s-]?(?:request|response|payload|body)|request[_\s-]?body|response[_\s-]?body|"
    r"provider[_\s-]?payload|debug[_\s-]?payload|debug[_\s-]?trace|stack trace|traceback)\b",
    re.IGNORECASE,
)
SECRET_MARKER_PATTERN = re.compile(
    r"\b(?:token|api[_\s-]?key|apikey|password|passwd|secret|session|bearer|private key|dsn|authorization|cookie|set-cookie)\b",
    re.IGNORECASE,
)
DESTRUCTIVE_PATTERN = re.compile(
    r"\b(?:kubectl delete|helm uninstall|terraform destroy|drop database|delete from|truncate table|rm -rf|production mutation)\b",
    re.IGNORECASE,
)
SAFE_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SAFE_METHODS = {"DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"}
SAFE_STATUS_CLASSES = {"2xx", "3xx", "4xx", "5xx", "401-or-403", "200-or-204"}
SUMMARY_REASON_MAP = {
    "authBoundaryResult": "accepted_outcome_requires_auth_boundary_summary",
    "securityHeaderSummary": "accepted_outcome_requires_security_header_summary",
    "csrfOrStateMutationSummary": "accepted_outcome_requires_csrf_or_state_mutation_summary",
    "publicSurfaceSummary": "accepted_outcome_requires_public_surface_summary",
    "rateLimitOrAbuseSummary": "accepted_outcome_requires_rate_limit_or_abuse_summary",
}
SENSITIVE_KEY_MARKERS = (
    "token",
    "api_key",
    "apikey",
    "password",
    "passwd",
    "secret",
    "session",
    "bearer",
    "private_key",
    "privatekey",
    "dsn",
    "authorization",
    "cookie",
    "set_cookie",
    "setcookie",
)
RAW_KEY_MARKERS = (
    "raw_request",
    "rawrequest",
    "raw_response",
    "rawresponse",
    "request_body",
    "requestbody",
    "response_body",
    "responsebody",
    "provider_payload",
    "providerpayload",
    "debug_payload",
    "debugpayload",
    "debug_trace",
    "debugtrace",
    "stack_trace",
    "stacktrace",
    "traceback",
)


def _is_non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_safe_placeholder(value: Any) -> bool:
    return str(value).strip().lower() in SAFE_PLACEHOLDERS


def _is_iso_timestamp(value: Any) -> bool:
    if not _is_non_empty_text(value):
        return False
    try:
        datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _is_safe_base_label(value: Any) -> bool:
    if not _is_non_empty_text(value):
        return False
    text = str(value).strip()
    if any(marker in text for marker in ("://", "/", "?", "#", "@", " ")):
        return False
    return bool(SAFE_LABEL_PATTERN.fullmatch(text))


def _is_safe_path_pattern(value: Any) -> bool:
    if not _is_non_empty_text(value):
        return False
    text = str(value).strip()
    if not text.startswith("/"):
        return False
    if any(marker in text for marker in ("://", "@", "?", "#")):
        return False
    return True


def _summary_text(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, dict):
        summary = value.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
    return None


def _summary_is_safe(value: Any) -> bool:
    if _is_safe_placeholder(value):
        return True
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            normalized = _normalize_key(key_text)
            if any(marker in normalized for marker in RAW_KEY_MARKERS + SENSITIVE_KEY_MARKERS):
                return False
            if not _summary_is_safe(nested):
                return False
        return True
    if isinstance(value, list):
        return all(_summary_is_safe(item) for item in value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return True
        return not (
            URL_WITH_CREDENTIALS_PATTERN.search(text)
            or URL_PATTERN.search(text)
            or RAW_PAYLOAD_PATTERN.search(text)
            or SECRET_MARKER_PATTERN.search(text)
            or GO_CLAIM_PATTERN.search(text)
            or DESTRUCTIVE_PATTERN.search(text)
        )
    return True


def _scan_value_key(field: str, key: Any) -> list[dict[str, str]]:
    normalized = _normalize_key(key)
    if any(marker in normalized for marker in RAW_KEY_MARKERS):
        reason = "debug_trace_forbidden" if any(
            marker in normalized
            for marker in (
                "debug_payload",
                "debugpayload",
                "debug_trace",
                "debugtrace",
                "stack_trace",
                "stacktrace",
                "traceback",
            )
        ) else "raw_payload_forbidden"
        return [_finding(field, reason)]
    if any(marker in normalized for marker in SENSITIVE_KEY_MARKERS):
        return [_finding(field, "secret_or_header_marker_forbidden")]
    return []


def _scan_value_string(field: str, value: Any) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    text = value.strip()
    if not text or _is_safe_placeholder(text):
        return findings
    if URL_WITH_CREDENTIALS_PATTERN.search(text):
        findings.append(_finding(field, "credential_url_forbidden"))
    if RAW_PAYLOAD_PATTERN.search(text):
        reason = "debug_trace_forbidden" if re.search(
            r"(?i)\b(?:debug[_\s-]?payload|debug[_\s-]?trace|stack trace|traceback)\b",
            text,
        ) else "raw_payload_forbidden"
        findings.append(_finding(field, reason))
    if SECRET_MARKER_PATTERN.search(text):
        findings.append(_finding(field, "secret_or_header_marker_forbidden"))
    if GO_CLAIM_PATTERN.search(text):
        findings.append(_finding(field, "launch_approval_claim_forbidden"))
    if DESTRUCTIVE_PATTERN.search(text):
        findings.append(_finding(field, "production_mutation_or_destructive_command_forbidden"))
    return findings


def _scan_value(value: Any, *, field: str = "$") -> list[dict[str, str]]:
    return scan_json_tree(
        value,
        field=field,
        scan_key=_scan_value_key,
        scan_string=_scan_value_string,
        recurse_on_key_findings=False,
    )


def _validate_route(route: Any, index: int) -> list[dict[str, str]]:
    field = f"checkedRoutes[{index}]"
    findings: list[dict[str, str]] = []
    if not isinstance(route, dict):
        return [_finding(field, "invalid_checked_route")]

    required_keys = ("routeLabel", "method", "pathPattern", "statusClass", "summary")
    for key in required_keys:
        if key not in route:
            findings.append(_finding(f"{field}.{key}", "missing_required_field"))

    route_label = route.get("routeLabel")
    method = route.get("method")
    path_pattern = route.get("pathPattern")
    status_class = route.get("statusClass")
    summary = route.get("summary")

    if "routeLabel" in route and not _is_safe_base_label(route_label):
        findings.append(_finding(f"{field}.routeLabel", "invalid_route_label"))
    if "method" in route and (not _is_non_empty_text(method) or str(method).strip().upper() not in SAFE_METHODS):
        findings.append(_finding(f"{field}.method", "invalid_route_method"))
    if "pathPattern" in route and not _is_safe_path_pattern(path_pattern):
        findings.append(_finding(f"{field}.pathPattern", "invalid_route_path_pattern"))
    if "statusClass" in route and (not _is_non_empty_text(status_class) or str(status_class).strip() not in SAFE_STATUS_CLASSES):
        findings.append(_finding(f"{field}.statusClass", "invalid_route_status_class"))
    if "summary" in route and not _summary_text(summary):
        findings.append(_finding(f"{field}.summary", "missing_required_summary"))
    if not _summary_is_safe(route):
        findings.append(_finding(field, "unsafe_route_summary"))
    findings.extend(_scan_value(route, field=field))
    return findings


def _validate_summary_field(name: str, value: Any, *, outcome: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    text = _summary_text(value)
    if not text:
        findings.append(_finding(name, "missing_required_summary"))
        if outcome == "accepted" and name in SUMMARY_REASON_MAP:
            findings.append(_finding(name, SUMMARY_REASON_MAP[name]))
        return findings
    if not _summary_is_safe(value):
        findings.append(_finding(name, "unsafe_summary_value"))
    return findings


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
    base_url_label = artifact.get("baseUrlLabel")
    network_calls_enabled = artifact.get("networkCallsEnabled")
    checked_routes = artifact.get("checkedRoutes")
    outcome = str(artifact.get("outcome") or "").strip().lower()
    evidence_redaction_version = artifact.get("evidenceRedactionVersion")
    notes = artifact.get("notes")

    if artifact_version != ARTIFACT_VERSION:
        findings.append(_finding("artifactVersion", "invalid_artifact_version"))
    if environment not in ALLOWED_ENVIRONMENTS:
        findings.append(_finding("environment", "invalid_environment"))
    if not _is_non_empty_text(operator):
        findings.append(_finding("operator", "invalid_operator"))
    if not _is_iso_timestamp(observed_at):
        findings.append(_finding("observedAt", "invalid_observed_at"))
    if not _is_safe_base_label(base_url_label):
        findings.append(_finding("baseUrlLabel", "invalid_base_url_label"))
    if not isinstance(network_calls_enabled, bool):
        findings.append(_finding("networkCallsEnabled", "invalid_boolean"))
    if not isinstance(checked_routes, list) or not checked_routes:
        findings.append(_finding("checkedRoutes", "invalid_checked_routes"))
    if outcome not in ALLOWED_OUTCOMES:
        findings.append(_finding("outcome", "invalid_outcome"))
    if evidence_redaction_version != REDACTION_VERSION:
        findings.append(_finding("evidenceRedactionVersion", "invalid_redaction_version"))
    if not _is_non_empty_text(notes):
        findings.append(_finding("notes", "invalid_notes"))

    for name in SUMMARY_FIELDS:
        if name not in artifact:
            continue
        findings.extend(_validate_summary_field(name, artifact.get(name), outcome=outcome))

    if isinstance(checked_routes, list):
        for index, route in enumerate(checked_routes):
            findings.extend(_validate_route(route, index))

    findings.extend(_scan_value(artifact))

    if outcome == "accepted":
        if environment not in {"staging", "production-like-staging", "sandbox"}:
            findings.append(_finding("environment", "accepted_outcome_requires_staging_or_sandbox_environment"))
        for field in ("authBoundaryResult", "securityHeaderSummary", "csrfOrStateMutationSummary", "publicSurfaceSummary", "rateLimitOrAbuseSummary"):
            text = _summary_text(artifact.get(field))
            if not text:
                findings.append(_finding(field, SUMMARY_REASON_MAP[field]))

    sanitized_routes = []
    if isinstance(checked_routes, list):
        for route in checked_routes:
            if isinstance(route, dict):
                sanitized_routes.append(
                    {
                        "routeLabel": route.get("routeLabel") if _is_safe_base_label(route.get("routeLabel")) else "<invalid>",
                        "method": str(route.get("method") or "<missing>").strip().upper(),
                        "pathPattern": route.get("pathPattern") if _is_safe_path_pattern(route.get("pathPattern")) else "<invalid>",
                        "statusClass": str(route.get("statusClass") or "<missing>").strip(),
                    }
                )

    summary = {
        "artifactVersion": str(artifact_version or "<missing>"),
        "environment": str(environment or "<missing>"),
        "operator": str(operator or "<missing>"),
        "observedAt": str(observed_at or "<missing>"),
        "baseUrlLabel": str(base_url_label) if _is_safe_base_label(base_url_label) else "<invalid>",
        "networkCallsEnabled": isinstance(network_calls_enabled, bool) and network_calls_enabled,
        "checkedRouteCount": len(checked_routes) if isinstance(checked_routes, list) else 0,
        "checkedRoutes": sanitized_routes,
        "outcome": str(outcome or "<missing>"),
        "evidenceRedactionVersion": str(evidence_redaction_version or "<missing>"),
        "notes": str(notes) if _is_non_empty_text(notes) and _summary_is_safe(notes) else "<redacted>",
    }

    deduped_findings = sorted({json.dumps(item, sort_keys=True): item for item in findings}.values(), key=lambda item: (item["field"], item["reasonCode"]))
    return deduped_findings, summary


def validate_staging_ingress_operator_evidence(artifact: Any) -> dict[str, Any]:
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
            "sanitizedValuesAbsent": not any(
                finding["reasonCode"]
                in {
                    "credential_url_forbidden",
                    "debug_trace_forbidden",
                    "launch_approval_claim_forbidden",
                    "production_mutation_or_destructive_command_forbidden",
                    "raw_payload_forbidden",
                    "secret_or_header_marker_forbidden",
                }
                for finding in findings
            ),
            "acceptedOutcomeGuarded": not any(
                finding["reasonCode"].startswith("accepted_outcome_requires_") for finding in findings
            ),
            "environmentAllowed": not any(finding["reasonCode"] == "invalid_environment" for finding in findings),
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
    parser = argparse.ArgumentParser(description="Validate sanitized staging ingress operator evidence JSON offline.")
    parser.add_argument("artifact", help="Path to sanitized staging ingress operator evidence JSON")
    args = parser.parse_args(argv)

    artifact = _load_json(Path(args.artifact))
    result = validate_staging_ingress_operator_evidence(artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
