#!/usr/bin/env python3
"""Validate sanitized API abuse and request-safety evidence offline.

This checker consumes only synthetic or operator-sanitized JSON artifacts. It
does not import API middleware, read runtime config, inspect traffic logs, call
networks, or change rate-limit/auth/session/RBAC behavior.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from evidence_safety import compact_key
    from evidence_safety import finding as _finding
    from evidence_safety import normalize_key
    from evidence_safety import scan_json_tree
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from scripts.evidence_safety import compact_key
    from scripts.evidence_safety import finding as _finding
    from scripts.evidence_safety import normalize_key
    from scripts.evidence_safety import scan_json_tree


SUMMARY_SCHEMA_VERSION = "wolfystock_api_abuse_request_safety_evidence_summary_v1"
ARTIFACT_VERSION = "wolfystock_api_abuse_request_safety_evidence_v1"
REDACTION_VERSION = "api-abuse-request-safety-redaction-v1"
ALLOWED_ENVIRONMENTS = {"local", "staging", "production-like-staging", "production-review"}
ALLOWED_EVIDENCE_MODES = {"offline-synthetic-review", "operator-sanitized-review"}
ALLOWED_OUTCOMES = {"accepted", "needs-review", "rejected"}
REQUIRED_FIELDS = (
    "artifactVersion",
    "environment",
    "operator",
    "observedAt",
    "evidenceMode",
    "rateLimitInvalidRequestSummary",
    "oversizedPayloadSafety",
    "malformedInputRejectionSummary",
    "denialSanitization",
    "auditLogRedactionProof",
    "leakageReview",
    "runtimeDefaults",
    "manualReview",
    "releaseApproved",
    "publicLaunchReady",
    "outcome",
    "evidenceRedactionVersion",
)
SECTION_FIELDS = {
    "rateLimitInvalidRequestSummary": (
        "rateLimitProbe",
        "invalidRequestHandling",
        "clientIdentifierMaterialIncluded",
        "sensitiveRouteMaterialIncluded",
    ),
    "oversizedPayloadSafety": (
        "payloadBodyStoredOrPrinted",
        "resultSummary",
        "maxBodyLabel",
    ),
    "malformedInputRejectionSummary": (
        "malformedJsonRejected",
        "malformedFormRejected",
        "bodyEchoed",
    ),
    "denialSanitization": (
        "authDenialSanitized",
        "adminDenialSanitized",
        "browserStateMaterialIncluded",
        "authHeaderMaterialIncluded",
        "principalIdentifierMaterialIncluded",
    ),
    "auditLogRedactionProof": (
        "auditEventsUseReasonCodes",
        "bodyMaterialLogged",
        "networkAddressLogged",
        "principalIdentifierLogged",
    ),
    "leakageReview": (
        "errorDetailsIncluded",
        "diagnosticPayloadIncluded",
        "sensitiveQueryStringsIncluded",
        "privateUrlsIncluded",
    ),
    "runtimeDefaults": (
        "apiMiddlewareChanged",
        "rateLimitImplementationChanged",
        "identityAccessRuntimeChanged",
        "publicApiDefaultsChanged",
        "runtimeDefaultUnchanged",
    ),
    "manualReview": (
        "manualReviewRequired",
        "reviewTicketRef",
    ),
}
MUST_BE_TRUE = {
    "malformedInputRejectionSummary.malformedJsonRejected",
    "malformedInputRejectionSummary.malformedFormRejected",
    "denialSanitization.authDenialSanitized",
    "denialSanitization.adminDenialSanitized",
    "auditLogRedactionProof.auditEventsUseReasonCodes",
    "runtimeDefaults.runtimeDefaultUnchanged",
    "manualReview.manualReviewRequired",
}
MUST_BE_FALSE = {
    "rateLimitInvalidRequestSummary.clientIdentifierMaterialIncluded",
    "rateLimitInvalidRequestSummary.sensitiveRouteMaterialIncluded",
    "oversizedPayloadSafety.payloadBodyStoredOrPrinted",
    "malformedInputRejectionSummary.bodyEchoed",
    "denialSanitization.browserStateMaterialIncluded",
    "denialSanitization.authHeaderMaterialIncluded",
    "denialSanitization.principalIdentifierMaterialIncluded",
    "auditLogRedactionProof.bodyMaterialLogged",
    "auditLogRedactionProof.networkAddressLogged",
    "auditLogRedactionProof.principalIdentifierLogged",
    "leakageReview.errorDetailsIncluded",
    "leakageReview.diagnosticPayloadIncluded",
    "leakageReview.sensitiveQueryStringsIncluded",
    "leakageReview.privateUrlsIncluded",
    "runtimeDefaults.apiMiddlewareChanged",
    "runtimeDefaults.rateLimitImplementationChanged",
    "runtimeDefaults.identityAccessRuntimeChanged",
    "runtimeDefaults.publicApiDefaultsChanged",
}
SAFE_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
SECRET_KEY_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "password",
    "private_key",
    "secret",
    "session",
    "set_cookie",
    "token",
)
RAW_REQUEST_KEY_MARKERS = (
    "debug_payload",
    "debugpayload",
    "raw_body",
    "raw_request",
    "rawrequest",
    "raw_request_body",
    "request_body",
    "requestbody",
)
IDENTIFIER_KEY_MARKERS = (
    "client_ip",
    "clientip",
    "ip_address",
    "ipaddress",
    "raw_ip",
    "session_id",
    "sessionid",
    "user_id",
    "userid",
)
SECRET_VALUE_PATTERN = re.compile(
    r"\b(?:api[_-]?key|apikey|authorization|bearer|cookie|password|secret|session|token)\b"
    r"\s*[:=]\s*(?!\*{3}|redacted\b)[^\s,;&]+|"
    r"\bBearer\s+(?!\*{3}|redacted\b)[A-Za-z0-9._~+/=-]{6,}|"
    r"\b(?:dsa_session|session|cookie)=[^\s,;&]+",
    re.IGNORECASE,
)
RAW_REQUEST_VALUE_PATTERN = re.compile(
    r"\b(?:raw|debug)[_\s-]+(?:request|body|payload|form|json)(?:[_\s-]*(?:body|payload|data))?\b|"
    r"\b(?:request|response)[_\s-]+body\b",
    re.IGNORECASE,
)
DEBUG_TRACE_PATTERN = re.compile(r"\b(?:Traceback \(most recent call last\):|stack trace|stacktrace|traceback)\b", re.IGNORECASE)
PRIVATE_URL_PATTERN = re.compile(r"\bhttps?://[^\s]+", re.IGNORECASE)
SENSITIVE_QUERY_PATH_PATTERN = re.compile(
    r"/[A-Za-z0-9_./-]+\?[^\s]*(?:api[_-]?key|authorization|bearer|cookie|password|secret|session|token)=",
    re.IGNORECASE,
)
IP_OR_IDENTIFIER_PATTERN = re.compile(
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b|"
    r"\b(?:user|account|session)[-_](?:real|prod|private|id|account)[-_A-Za-z0-9]{3,}\b",
    re.IGNORECASE,
)
LAUNCH_APPROVAL_PATTERN = re.compile(
    r"\b(?:launch[-_\s]?approved|public[-_\s]?launch[-_\s]?ready|production[-_\s]?ready|"
    r"release[-_\s]?approved|go\s+for\s+launch|approved\s+for\s+launch)\b",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"[FAIL] Evidence file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[FAIL] Evidence file is not valid JSON: {exc}")


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _safe_label(value: Any) -> bool:
    return _non_empty_string(value) and bool(SAFE_LABEL_PATTERN.fullmatch(value.strip()))


def _iso_timestamp(value: Any) -> bool:
    if not _non_empty_string(value):
        return False
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _safe_placeholder(value: Any) -> bool:
    if value is False or value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"", "***", "[redacted]", "<redacted>", "redacted", "sanitized"}
    return False


def _scan_key(field: str, key: Any) -> list[dict[str, str]]:
    normalized = normalize_key(key)
    compact = compact_key(key)
    findings: list[dict[str, str]] = []
    if any(marker in normalized or marker in compact for marker in SECRET_KEY_MARKERS):
        findings.append(_finding(field, "secret_or_header_marker_forbidden"))
    if any(marker in normalized or marker in compact for marker in RAW_REQUEST_KEY_MARKERS):
        findings.append(_finding(field, "raw_request_material_forbidden"))
    if any(marker in normalized or marker in compact for marker in IDENTIFIER_KEY_MARKERS):
        findings.append(_finding(field, "raw_ip_or_session_identifier_forbidden"))
    if "traceback" in compact or "stacktrace" in compact:
        findings.append(_finding(field, "debug_or_stack_trace_forbidden"))
    return findings


def _scan_entry(field: str, key: Any, value: Any) -> list[dict[str, str]]:
    if _safe_placeholder(value):
        return []
    return _scan_key(field, key)


def _scan_string(field: str, value: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if SECRET_VALUE_PATTERN.search(value):
        findings.append(_finding(field, "secret_or_header_marker_forbidden"))
    if SENSITIVE_QUERY_PATH_PATTERN.search(value) or RAW_REQUEST_VALUE_PATTERN.search(value):
        findings.append(_finding(field, "raw_request_material_forbidden"))
    if DEBUG_TRACE_PATTERN.search(value):
        findings.append(_finding(field, "debug_or_stack_trace_forbidden"))
    if PRIVATE_URL_PATTERN.search(value):
        findings.append(_finding(field, "private_url_forbidden"))
    if IP_OR_IDENTIFIER_PATTERN.search(value):
        findings.append(_finding(field, "raw_ip_or_session_identifier_forbidden"))
    if LAUNCH_APPROVAL_PATTERN.search(value):
        findings.append(_finding(field, "public_launch_approval_forbidden"))
    return findings


def _scan_unsafe(value: Any) -> list[dict[str, str]]:
    return scan_json_tree(
        value,
        scan_entry=_scan_entry,
        scan_string=_scan_string,
        recurse_on_key_findings=False,
    )


def _section(artifact: dict[str, Any], field: str) -> dict[str, Any]:
    value = artifact.get(field)
    return value if isinstance(value, dict) else {}


def _field_path(section: str, key: str) -> str:
    return f"{section}.{key}"


def _validate_artifact(artifact: Any) -> tuple[list[dict[str, str]], dict[str, bool]]:
    checks = {
        "rateLimitInvalidRequestSummaryPresent": False,
        "oversizedPayloadSafetyPresent": False,
        "malformedInputRejectionPresent": False,
        "denialSanitizationPresent": False,
        "auditLogRedactionProofPresent": False,
        "leakageReviewPresent": False,
        "runtimeDefaultsUnchanged": False,
        "manualReviewAndNoLaunchApproval": False,
        "unsafeContentAbsent": False,
    }
    if not isinstance(artifact, dict):
        return [_finding("$", "artifact_must_be_json_object")], checks

    findings: list[dict[str, str]] = []
    for field in REQUIRED_FIELDS:
        if field not in artifact:
            findings.append(_finding(field, "missing_required_field"))

    if artifact.get("artifactVersion") != ARTIFACT_VERSION:
        findings.append(_finding("artifactVersion", "invalid_artifact_version"))
    if artifact.get("environment") not in ALLOWED_ENVIRONMENTS:
        findings.append(_finding("environment", "invalid_environment"))
    if artifact.get("evidenceMode") not in ALLOWED_EVIDENCE_MODES:
        findings.append(_finding("evidenceMode", "invalid_evidence_mode"))
    if not _safe_label(artifact.get("operator")):
        findings.append(_finding("operator", "invalid_sanitized_label"))
    if not _iso_timestamp(artifact.get("observedAt")):
        findings.append(_finding("observedAt", "invalid_observed_at"))
    if artifact.get("outcome") not in ALLOWED_OUTCOMES:
        findings.append(_finding("outcome", "invalid_outcome"))
    if artifact.get("evidenceRedactionVersion") != REDACTION_VERSION:
        findings.append(_finding("evidenceRedactionVersion", "invalid_redaction_version"))
    if artifact.get("releaseApproved") is not False:
        findings.append(_finding("releaseApproved", "public_launch_approval_forbidden"))
    if artifact.get("publicLaunchReady") is not False:
        findings.append(_finding("publicLaunchReady", "public_launch_approval_forbidden"))

    for section, required_fields in SECTION_FIELDS.items():
        section_value = artifact.get(section)
        if not isinstance(section_value, dict):
            findings.append(_finding(section, "missing_section"))
            continue
        for key in required_fields:
            if key not in section_value:
                findings.append(_finding(_field_path(section, key), "missing_required_field"))

    if artifact.get("outcome") == "accepted":
        for path in MUST_BE_TRUE:
            section, key = path.split(".", 1)
            if _section(artifact, section).get(key) is not True:
                findings.append(_finding(path, "required_true_field_not_true"))
    for path in MUST_BE_FALSE:
        section, key = path.split(".", 1)
        if _section(artifact, section).get(key) is not False:
            findings.append(_finding(path, "required_false_field_not_false"))

    for section, keys in (
        ("rateLimitInvalidRequestSummary", ("rateLimitProbe", "invalidRequestHandling")),
        ("oversizedPayloadSafety", ("resultSummary", "maxBodyLabel")),
        ("manualReview", ("reviewTicketRef",)),
    ):
        for key in keys:
            if key in _section(artifact, section) and not _safe_label(_section(artifact, section).get(key)):
                findings.append(_finding(_field_path(section, key), "invalid_sanitized_label"))

    unsafe_findings = _scan_unsafe(artifact)
    findings.extend(unsafe_findings)
    deduped = sorted(
        {json.dumps(item, sort_keys=True): item for item in findings}.values(),
        key=lambda item: (item["field"], item["reasonCode"]),
    )

    reason_codes = {finding["reasonCode"] for finding in deduped}
    missing_or_invalid = {"missing_required_field", "missing_section"}
    checks["rateLimitInvalidRequestSummaryPresent"] = not any(
        finding["field"].startswith("rateLimitInvalidRequestSummary")
        and finding["reasonCode"] in missing_or_invalid
        for finding in deduped
    )
    checks["oversizedPayloadSafetyPresent"] = not any(
        finding["field"].startswith("oversizedPayloadSafety") and finding["reasonCode"] in missing_or_invalid
        for finding in deduped
    )
    checks["malformedInputRejectionPresent"] = not any(
        finding["field"].startswith("malformedInputRejectionSummary")
        and finding["reasonCode"] in missing_or_invalid
        for finding in deduped
    )
    checks["denialSanitizationPresent"] = not any(
        finding["field"].startswith("denialSanitization") and finding["reasonCode"] in missing_or_invalid
        for finding in deduped
    )
    checks["auditLogRedactionProofPresent"] = not any(
        finding["field"].startswith("auditLogRedactionProof") and finding["reasonCode"] in missing_or_invalid
        for finding in deduped
    )
    checks["leakageReviewPresent"] = not any(
        finding["field"].startswith("leakageReview") and finding["reasonCode"] in missing_or_invalid
        for finding in deduped
    )
    checks["runtimeDefaultsUnchanged"] = not any(
        finding["field"].startswith("runtimeDefaults") and finding["reasonCode"] in missing_or_invalid | {"required_true_field_not_true", "required_false_field_not_false"}
        for finding in deduped
    )
    checks["manualReviewAndNoLaunchApproval"] = not (
        any(finding["field"].startswith("manualReview") for finding in deduped)
        or "public_launch_approval_forbidden" in reason_codes
    )
    checks["unsafeContentAbsent"] = not any(
        reason
        in {
            "debug_or_stack_trace_forbidden",
            "private_url_forbidden",
            "public_launch_approval_forbidden",
            "raw_ip_or_session_identifier_forbidden",
            "raw_request_material_forbidden",
            "secret_or_header_marker_forbidden",
        }
        for reason in reason_codes
    )
    return deduped, checks


def _artifact_summary(artifact: Any) -> dict[str, str]:
    if not isinstance(artifact, dict):
        return {}
    return {
        "artifactVersion": str(artifact.get("artifactVersion") or "<missing>"),
        "environment": str(artifact.get("environment") or "<missing>"),
        "operator": artifact.get("operator") if _safe_label(artifact.get("operator")) else "<invalid>",
        "observedAt": artifact.get("observedAt") if _iso_timestamp(artifact.get("observedAt")) else "<invalid>",
        "evidenceMode": str(artifact.get("evidenceMode") or "<missing>"),
        "outcome": str(artifact.get("outcome") or "<missing>"),
        "evidenceRedactionVersion": str(artifact.get("evidenceRedactionVersion") or "<missing>"),
    }


def validate_api_abuse_request_safety_evidence(artifact: Any) -> dict[str, Any]:
    findings, checks = _validate_artifact(artifact)
    safe_for_review = not findings
    evidence_ready = safe_for_review and isinstance(artifact, dict) and artifact.get("outcome") == "accepted"
    return {
        "schemaVersion": SUMMARY_SCHEMA_VERSION,
        "generatedAt": _now_iso(),
        "status": "pass" if safe_for_review else "fail",
        "finalStatus": "EVIDENCE-READY" if evidence_ready else "REVIEW-REQUIRED" if safe_for_review else "EVIDENCE-BLOCKED",
        "manualReviewRequired": True,
        "releaseApproved": False,
        "publicLaunchReady": False,
        "runtimeBehaviorChanged": False,
        "networkCallsExecutedByValidator": False,
        "externalServicesCalledByValidator": False,
        "runtimeConfigReadByValidator": False,
        "trafficLogsReadByValidator": False,
        "rawRequestDataIncluded": False,
        "launchAcceptanceIntegrated": False,
        "checks": checks,
        "artifact": _artifact_summary(artifact),
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a sanitized API abuse/request-safety evidence JSON artifact offline."
    )
    parser.add_argument("artifact", help="Path to sanitized API abuse/request-safety evidence JSON")
    args = parser.parse_args(argv)

    result = validate_api_abuse_request_safety_evidence(_load_json(Path(args.artifact)))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
