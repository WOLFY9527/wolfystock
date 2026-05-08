#!/usr/bin/env python3
"""Validate sanitized quota pilot and budget-alert operator evidence offline.

The checker reads one JSON artifact, emits a sanitized JSON summary, and exits
non-zero unless every required section is accepted. It never calls network,
quota, billing, notification, provider, auth, or storage runtime code.
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


INPUT_SCHEMA_VERSION = "wolfystock_quota_operator_evidence_v1"
SUMMARY_SCHEMA_VERSION = "wolfystock_quota_operator_evidence_summary_v1"
REDACTION_VERSION = "quota_budget_operator_redaction_v1"

REQUIRED_SECTIONS = (
    "quotaPilot",
    "budgetAlertDryRun",
    "ownerScopeSampling",
    "disabledPreferenceSuppression",
    "notificationNoOutboundProof",
)
REQUIRED_FIELDS = (
    "environment",
    "operator",
    "observedAt",
    "sampledOwnerLabels",
    "thresholdPolicyVersion",
    "dryRunOnly",
    "outboundSent",
    "outcome",
    "evidenceRedactionVersion",
)
ACCEPTED_OUTCOMES = {"accepted", "needs-review", "rejected"}

SENSITIVE_KEY_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "debug_payload",
    "debugpayload",
    "password",
    "raw_request",
    "raw_request_body",
    "raw_response",
    "raw_response_body",
    "request_body",
    "requestbody",
    "response_body",
    "responsebody",
    "secret",
    "session",
    "stack_trace",
    "stacktrace",
    "token",
    "traceback",
    "webhook",
)
RAW_PAYLOAD_KEY_MARKERS = (
    "debug_payload",
    "debugpayload",
    "raw_request",
    "raw_request_body",
    "raw_response",
    "raw_response_body",
    "request_body",
    "requestbody",
    "response_body",
    "responsebody",
)
MUTATION_KEY_MARKERS = (
    "enforcement_changed",
    "enforcement_mutation",
    "enforcementchanged",
    "enforcementmutation",
    "threshold_changed",
    "threshold_mutation",
    "thresholdchanged",
    "thresholdmutation",
)

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"\b(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})\b")
URL_PATTERN = re.compile(r"https?://[^\s\"']+", re.IGNORECASE)
SECRET_VALUE_PATTERNS = (
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\b(?:api[_-]?key|token|secret|password|cookie|session)\s*=", re.IGNORECASE),
)
GO_CLAIM_PATTERN = re.compile(
    r"\bGO\b|launch[-\s]?approved|production[-\s]?ready|automatic[-\s]?go|"
    r"release[-\s]?approved|public launch approved",
    re.IGNORECASE,
)
MUTATION_VALUE_PATTERN = re.compile(
    r"(?:threshold|enforcement)\s+(?:changed|enabled|mutated|raised|lowered|updated|wired)",
    re.IGNORECASE,
)
TRACEBACK_PATTERN = re.compile(r"Traceback \(most recent call last\):", re.IGNORECASE)


def _normalize_outcome(value: object) -> str:
    return str(value or "").strip().lower()


def _is_non_empty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_valid_observed_at(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _scan_key(field: str, key: object) -> list[dict[str, str]]:
    lowered = _normalize_key(key)
    findings: list[dict[str, str]] = []
    if any(marker in lowered for marker in RAW_PAYLOAD_KEY_MARKERS):
        findings.append(_finding(field, "raw_payload_forbidden"))
    elif any(marker in lowered for marker in SENSITIVE_KEY_MARKERS):
        findings.append(_finding(field, "unsafe_secret_marker"))
    if any(marker in lowered for marker in MUTATION_KEY_MARKERS):
        findings.append(_finding(field, "threshold_or_enforcement_mutation_claim"))
    return findings


def _scan_string(field: str, value: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if EMAIL_PATTERN.search(value) or PHONE_PATTERN.search(value):
        findings.append(_finding(field, "unsafe_contact_value"))
    if URL_PATTERN.search(value):
        findings.append(_finding(field, "unsafe_url_value"))
    if any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
        findings.append(_finding(field, "unsafe_secret_marker"))
    if GO_CLAIM_PATTERN.search(value):
        findings.append(_finding(field, "launch_approval_claim_forbidden"))
    if MUTATION_VALUE_PATTERN.search(value):
        findings.append(_finding(field, "threshold_or_enforcement_mutation_claim"))
    if TRACEBACK_PATTERN.search(value):
        findings.append(_finding(field, "traceback_forbidden"))
    return findings


def _scan_tree(value: Any) -> list[dict[str, str]]:
    return scan_json_tree(value, scan_key=_scan_key, scan_string=_scan_string)


def _validate_section(section_id: str, section: Any) -> tuple[dict[str, Any], list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    missing_fields: list[str] = []
    status = "accepted"

    if not isinstance(section, dict):
        return (
            {
                "id": section_id,
                "status": "blocking",
                "missingFields": list(REQUIRED_FIELDS),
                "reasonCodes": ["invalid_section"],
            },
            [_finding(section_id, "invalid_section")],
        )

    for field_name in REQUIRED_FIELDS:
        field_path = f"{section_id}.{field_name}"
        if field_name not in section:
            missing_fields.append(field_name)
            findings.append(_finding(field_path, "missing_required_field"))

    if "environment" in section and not _is_non_empty_text(section.get("environment")):
        findings.append(_finding(f"{section_id}.environment", "invalid_required_field"))
    if "operator" in section and not _is_non_empty_text(section.get("operator")):
        findings.append(_finding(f"{section_id}.operator", "invalid_required_field"))
    if "observedAt" in section and not _is_valid_observed_at(section.get("observedAt")):
        findings.append(_finding(f"{section_id}.observedAt", "invalid_observed_at"))

    sampled_owner_labels = section.get("sampledOwnerLabels")
    if "sampledOwnerLabels" in section:
        if not isinstance(sampled_owner_labels, list) or not sampled_owner_labels:
            findings.append(_finding(f"{section_id}.sampledOwnerLabels", "owner_scope_missing"))
        elif not all(_is_non_empty_text(label) for label in sampled_owner_labels):
            findings.append(_finding(f"{section_id}.sampledOwnerLabels", "invalid_owner_scope_label"))

    if "thresholdPolicyVersion" in section and not _is_non_empty_text(section.get("thresholdPolicyVersion")):
        findings.append(_finding(f"{section_id}.thresholdPolicyVersion", "invalid_required_field"))
    if "dryRunOnly" in section and section.get("dryRunOnly") is not True:
        findings.append(_finding(f"{section_id}.dryRunOnly", "dry_run_only_required"))
    if "evidenceRedactionVersion" in section and section.get("evidenceRedactionVersion") != REDACTION_VERSION:
        findings.append(_finding(f"{section_id}.evidenceRedactionVersion", "invalid_redaction_version"))

    outcome = _normalize_outcome(section.get("outcome"))
    if "outcome" in section and outcome not in ACCEPTED_OUTCOMES:
        findings.append(_finding(f"{section_id}.outcome", "invalid_outcome"))
    if outcome != "accepted":
        status = outcome if outcome in {"needs-review", "rejected"} else "blocking"

    outbound_sent = section.get("outboundSent")
    if "outboundSent" in section and outbound_sent is not False:
        rehearsal_scope = str(section.get("rehearsalScope") or section.get("evidenceScope") or "").strip()
        if rehearsal_scope == "separate_non_launch_rehearsal" and outcome in {"needs-review", "rejected"}:
            findings.append(_finding(f"{section_id}.outboundSent", "outbound_non_launch_rehearsal_not_launch_evidence"))
            status = outcome
        else:
            findings.append(_finding(f"{section_id}.outboundSent", "outbound_sent_forbidden"))
            status = "blocking"

    if missing_fields:
        status = "blocking"

    reason_codes = sorted({finding["reasonCode"] for finding in findings})
    return (
        {
            "id": section_id,
            "status": status if not reason_codes or status in {"needs-review", "rejected"} else "blocking",
            "missingFields": missing_fields,
            "reasonCodes": reason_codes,
        },
        findings,
    )


def validate_artifact(payload: Any) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    sections: list[dict[str, Any]] = []

    if not isinstance(payload, dict):
        findings.append(_finding("$", "invalid_json_object"))
        payload = {}

    if payload.get("schemaVersion") != INPUT_SCHEMA_VERSION:
        findings.append(_finding("schemaVersion", "invalid_schema_version"))

    for section_id in REQUIRED_SECTIONS:
        if section_id not in payload:
            sections.append(
                {
                    "id": section_id,
                    "status": "blocking",
                    "missingFields": list(REQUIRED_FIELDS),
                    "reasonCodes": ["missing_required_section"],
                }
            )
            findings.append(_finding(section_id, "missing_required_section"))
            continue
        section_summary, section_findings = _validate_section(section_id, payload[section_id])
        sections.append(section_summary)
        findings.extend(section_findings)

    findings.extend(_scan_tree(payload))
    deduped_findings = sorted(
        {json.dumps(item, sort_keys=True): item for item in findings}.values(),
        key=lambda item: (item["field"], item["reasonCode"]),
    )
    accepted_sections = sum(1 for section in sections if section["status"] == "accepted")
    blocking_sections = sum(1 for section in sections if section["status"] != "accepted")
    passed = not deduped_findings and blocking_sections == 0

    return {
        "schemaVersion": SUMMARY_SCHEMA_VERSION,
        "tool": "scripts/quota_operator_evidence_check.py",
        "inputSchemaVersion": str(payload.get("schemaVersion") or "") if isinstance(payload, dict) else "",
        "status": "pass" if passed else "fail",
        "finalStatus": "ACCEPTED" if passed else "REJECTED",
        "advisoryOnly": True,
        "launchAcceptanceIntegrated": False,
        "networkCallsExecutedByValidator": False,
        "outboundNotificationsSentByValidator": False,
        "runtimeBehaviorChanged": False,
        "checks": {
            "requiredSectionsPresent": all(section["id"] in payload for section in sections) if isinstance(payload, dict) else False,
            "ownerScopeRecorded": not any(
                finding["reasonCode"] == "owner_scope_missing" for finding in deduped_findings
            ),
            "dryRunOnly": not any(finding["reasonCode"] == "dry_run_only_required" for finding in deduped_findings),
            "outboundDisabled": not any(
                finding["reasonCode"] in {"outbound_sent_forbidden", "outbound_non_launch_rehearsal_not_launch_evidence"}
                for finding in deduped_findings
            ),
            "sensitiveValuesAbsent": not any(
                finding["reasonCode"] in {"unsafe_contact_value", "unsafe_url_value", "unsafe_secret_marker"}
                for finding in deduped_findings
            ),
            "rawPayloadsAbsent": not any(
                finding["reasonCode"] in {"raw_payload_forbidden", "traceback_forbidden"} for finding in deduped_findings
            ),
            "launchApprovalClaimsAbsent": not any(
                finding["reasonCode"] == "launch_approval_claim_forbidden" for finding in deduped_findings
            ),
            "thresholdAndEnforcementMutationClaimsAbsent": not any(
                finding["reasonCode"] == "threshold_or_enforcement_mutation_claim" for finding in deduped_findings
            ),
        },
        "summary": {
            "acceptedSections": accepted_sections,
            "blockingSections": blocking_sections,
            "findings": len(deduped_findings),
        },
        "sections": sections,
        "findings": deduped_findings,
        "sanitization": {
            "realSecretsIncluded": False,
            "rawCredentialValuesIncluded": False,
            "rawRequestBodiesIncluded": False,
            "rawResponseBodiesIncluded": False,
            "rawDebugPayloadsIncluded": False,
            "webhookUrlsIncluded": False,
            "operatorContactDataIncluded": False,
            "networkCallsByValidator": False,
            "runtimeDefaultsChanged": False,
        },
    }


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", nargs="?", help="Sanitized quota/budget operator evidence JSON artifact.")
    parser.add_argument("--evidence", dest="evidence", help="Sanitized quota/budget operator evidence JSON artifact.")
    args = parser.parse_args(argv)
    artifact_arg = args.evidence or args.artifact
    if not artifact_arg:
        parser.error("an evidence artifact path is required")

    try:
        payload = _load_json(Path(artifact_arg))
    except (OSError, json.JSONDecodeError):
        payload = {}
        summary = validate_artifact(payload)
        summary["findings"].append(_finding("$", "artifact_read_failed"))
        summary["summary"]["findings"] = len(summary["findings"])
        summary["status"] = "fail"
        summary["finalStatus"] = "REJECTED"
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 1

    summary = validate_artifact(payload)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
