#!/usr/bin/env python3
"""Validate sanitized manual release approval review records offline.

This helper validates the human review-record artifact expected after
GO-REVIEW-REQUIRED. It does not approve launch, derive release approval, call
networks, read runtime configuration, or integrate with launch acceptance.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "wolfystock_manual_release_approval_evidence_validation_v1"
ARTIFACT_VERSION = "wolfystock_manual_release_approval_review_record_v1"
REDACTION_VERSION = "manual-release-review-redaction-v1"
ALLOWED_DECISIONS = {"approved-for-manual-release-review", "rejected", "needs-review"}
REQUIRED_FIELDS = (
    "artifactVersion",
    "releaseCandidateSha",
    "reviewerRoleLabels",
    "approvalMeetingOrTicketRef",
    "approvalTimestamp",
    "evidenceBundleRef",
    "knownResidualRisks",
    "rollbackOwnerLabel",
    "goNoGoDecision",
    "evidenceRedactionVersion",
)

SAFE_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
ROLE_LABEL_PATTERN = re.compile(r"^[a-z][a-z0-9_:-]{1,63}$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{7,40}$")
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
URL_WITH_CREDENTIALS_PATTERN = re.compile(r"https?://[^/\s:@]+:[^@\s]+@[^/\s]+", re.IGNORECASE)
SECRET_PATTERN = re.compile(
    r"\b(?:api[_\s-]?key|apikey|authorization|bearer|cookie|password|passwd|"
    r"private[_\s-]?key|secret|session|token|set-cookie)\b",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERN = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9_]{24,}|"
    r"xox[baprs]-[A-Za-z0-9-]{20,}|Bearer\s+[A-Za-z0-9._~+/=-]{12,})\b",
    re.IGNORECASE,
)
RAW_RECORD_PATTERN = re.compile(
    r"\b(?:meeting transcript|transcript|chat log|chatlog|screenshot|screen shot|"
    r"raw[_\s-]?(?:meeting|chat|log|transcript|screenshot|request|response|payload)|"
    r"debug[_\s-]?(?:trace|payload)|stack trace|stacktrace|traceback)\b",
    re.IGNORECASE,
)
DEBUG_TRACE_PATTERN = re.compile(r"\b(?:debug[_\s-]?trace|stack trace|stacktrace|traceback)\b", re.IGNORECASE)
LAUNCH_APPROVAL_PATTERN = re.compile(
    r"\b(?:launch[-_\s]?approved|production[-_\s]?ready|automatic[-_\s]?go|"
    r"go\s+for\s+launch|launch\s+go|approved\s+for\s+launch|release[-_\s]?approved)\b",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _finding(field: str, reason_code: str) -> dict[str, str]:
    return {"field": field, "reasonCode": reason_code}


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"[FAIL] Evidence file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[FAIL] Evidence file is not valid JSON: {exc}")


def _is_non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_safe_label(value: Any) -> bool:
    return _is_non_empty_text(value) and bool(SAFE_LABEL_PATTERN.fullmatch(value.strip()))


def _is_role_label(value: Any) -> bool:
    return _is_non_empty_text(value) and bool(ROLE_LABEL_PATTERN.fullmatch(value.strip()))


def _is_iso_timestamp(value: Any) -> bool:
    if not _is_non_empty_text(value):
        return False
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _path(parent: str, key: str) -> str:
    return key if parent == "$" else f"{parent}.{key}"


def _scan_unsafe(value: Any, *, field: str = "$") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            nested_field = _path(field, key_text)
            normalized_key = re.sub(r"[^a-z0-9]+", "_", key_text.lower()).strip("_")
            compact_key = re.sub(r"[^a-z0-9]+", "", key_text.lower())
            if any(marker in normalized_key for marker in ("email", "user_name", "username", "person_name", "real_name")):
                findings.append(_finding(nested_field, "personal_identifier_field_forbidden"))
                findings.extend(_scan_unsafe(nested, field=nested_field))
                continue
            if DEBUG_TRACE_PATTERN.search(key_text):
                findings.append(_finding(nested_field, "debug_or_stack_trace_forbidden"))
                findings.extend(_scan_unsafe(nested, field=nested_field))
                continue
            if RAW_RECORD_PATTERN.search(key_text) or any(
                marker in compact_key
                for marker in ("rawmeeting", "rawtranscript", "rawchat", "chatlog", "screenshot")
            ):
                findings.append(_finding(nested_field, "raw_transcript_or_screenshot_forbidden"))
                findings.extend(_scan_unsafe(nested, field=nested_field))
                continue
            if SECRET_PATTERN.search(key_text):
                findings.append(_finding(nested_field, "secret_marker_forbidden"))
                findings.extend(_scan_unsafe(nested, field=nested_field))
                continue
            findings.extend(_scan_unsafe(nested, field=nested_field))
        return findings
    if isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_scan_unsafe(nested, field=f"{field}[{index}]"))
        return findings
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return findings
        if EMAIL_PATTERN.search(text):
            findings.append(_finding(field, "email_or_personal_identifier_forbidden"))
        if URL_WITH_CREDENTIALS_PATTERN.search(text):
            findings.append(_finding(field, "credential_url_forbidden"))
        if RAW_RECORD_PATTERN.search(text):
            findings.append(_finding(field, "raw_transcript_or_screenshot_forbidden"))
        if DEBUG_TRACE_PATTERN.search(text):
            findings.append(_finding(field, "debug_or_stack_trace_forbidden"))
        if SECRET_PATTERN.search(text) or SECRET_VALUE_PATTERN.search(text):
            findings.append(_finding(field, "secret_marker_forbidden"))
        if LAUNCH_APPROVAL_PATTERN.search(text) or text.upper() == "GO":
            findings.append(_finding(field, "launch_approval_claim_forbidden"))
    return findings


def _validate_artifact(artifact: Any) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if not isinstance(artifact, dict):
        return [_finding("$", "artifact_must_be_json_object")], {}

    findings: list[dict[str, str]] = []
    for field in REQUIRED_FIELDS:
        if field not in artifact:
            findings.append(_finding(field, "missing_required_field"))

    if artifact.get("artifactVersion") != ARTIFACT_VERSION:
        findings.append(_finding("artifactVersion", "invalid_artifact_version"))

    release_candidate_sha = artifact.get("releaseCandidateSha")
    if not (_is_non_empty_text(release_candidate_sha) and SHA_PATTERN.fullmatch(release_candidate_sha.strip())):
        findings.append(_finding("releaseCandidateSha", "missing_or_invalid_release_candidate_sha"))

    role_labels = artifact.get("reviewerRoleLabels")
    if not isinstance(role_labels, list) or not role_labels:
        findings.append(_finding("reviewerRoleLabels", "missing_reviewer_role_labels"))
    elif not all(_is_role_label(label) for label in role_labels):
        findings.append(_finding("reviewerRoleLabels", "unsafe_reviewer_role_label"))

    for field in ("approvalMeetingOrTicketRef", "evidenceBundleRef", "rollbackOwnerLabel"):
        if field in artifact and not _is_safe_label(artifact.get(field)):
            findings.append(_finding(field, "invalid_sanitized_label"))

    if not _is_iso_timestamp(artifact.get("approvalTimestamp")):
        findings.append(_finding("approvalTimestamp", "invalid_approval_timestamp"))

    risks = artifact.get("knownResidualRisks")
    if not isinstance(risks, list) or not risks:
        findings.append(_finding("knownResidualRisks", "missing_residual_risk_acknowledgement"))
    elif not all(_is_safe_label(risk) for risk in risks):
        findings.append(_finding("knownResidualRisks", "unsafe_residual_risk_label"))

    decision = str(artifact.get("goNoGoDecision") or "").strip()
    if decision not in ALLOWED_DECISIONS:
        findings.append(_finding("goNoGoDecision", "invalid_go_no_go_decision"))

    if artifact.get("evidenceRedactionVersion") != REDACTION_VERSION:
        findings.append(_finding("evidenceRedactionVersion", "invalid_redaction_version"))

    if artifact.get("releaseApproved") is True or artifact.get("launchApproved") is True:
        findings.append(_finding("releaseApproved", "release_approval_boolean_forbidden"))

    findings.extend(_scan_unsafe(artifact))
    deduped_findings = sorted(
        {json.dumps(item, sort_keys=True): item for item in findings}.values(),
        key=lambda item: (item["field"], item["reasonCode"]),
    )

    summary = {
        "artifactVersion": str(artifact.get("artifactVersion") or "<missing>"),
        "releaseCandidateSha": release_candidate_sha if _is_non_empty_text(release_candidate_sha) else "<missing>",
        "reviewerRoleLabelCount": len(role_labels) if isinstance(role_labels, list) else 0,
        "approvalMeetingOrTicketRef": artifact.get("approvalMeetingOrTicketRef")
        if _is_safe_label(artifact.get("approvalMeetingOrTicketRef"))
        else "<invalid>",
        "approvalTimestamp": artifact.get("approvalTimestamp") if _is_iso_timestamp(artifact.get("approvalTimestamp")) else "<invalid>",
        "evidenceBundleRef": artifact.get("evidenceBundleRef") if _is_safe_label(artifact.get("evidenceBundleRef")) else "<invalid>",
        "knownResidualRiskCount": len(risks) if isinstance(risks, list) else 0,
        "rollbackOwnerLabel": artifact.get("rollbackOwnerLabel") if _is_safe_label(artifact.get("rollbackOwnerLabel")) else "<invalid>",
        "goNoGoDecision": decision or "<missing>",
        "evidenceRedactionVersion": str(artifact.get("evidenceRedactionVersion") or "<missing>"),
    }
    return deduped_findings, summary


def validate_manual_release_approval_evidence(artifact: Any) -> dict[str, Any]:
    findings, artifact_summary = _validate_artifact(artifact)
    decision = artifact_summary.get("goNoGoDecision")
    if findings or decision == "rejected":
        manual_review_status = "rejected"
    elif decision == "needs-review":
        manual_review_status = "needs-review"
    else:
        manual_review_status = "review-record-valid"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": _now_iso(),
        "mode": "offline_manual_release_review_record_validation",
        "manualReviewStatus": manual_review_status,
        "releaseApproved": False,
        "launchApproved": False,
        "runtimeBehaviorChanged": False,
        "networkCallsExecutedByValidator": False,
        "launchAcceptanceIntegrated": False,
        "artifact": artifact_summary,
        "checks": {
            "requiredFieldsPresent": not any(finding["reasonCode"] == "missing_required_field" for finding in findings),
            "releaseCandidateShaPresent": not any(
                finding["reasonCode"] == "missing_or_invalid_release_candidate_sha" for finding in findings
            ),
            "residualRisksAcknowledged": not any(
                finding["reasonCode"] == "missing_residual_risk_acknowledgement" for finding in findings
            ),
            "sanitizedValuesOnly": not any(
                finding["reasonCode"]
                in {
                    "credential_url_forbidden",
                    "debug_or_stack_trace_forbidden",
                    "email_or_personal_identifier_forbidden",
                    "personal_identifier_field_forbidden",
                    "raw_transcript_or_screenshot_forbidden",
                    "secret_marker_forbidden",
                    "unsafe_residual_risk_label",
                    "unsafe_reviewer_role_label",
                }
                for finding in findings
            ),
            "launchApprovalClaimsAbsent": not any(
                finding["reasonCode"] in {"launch_approval_claim_forbidden", "release_approval_boolean_forbidden"}
                for finding in findings
            ),
        },
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a sanitized manual release approval review-record JSON artifact.")
    parser.add_argument("--artifact", required=True, help="Path to the sanitized manual release approval review-record JSON.")
    args = parser.parse_args(argv)

    result = validate_manual_release_approval_evidence(_load_json(Path(args.artifact)))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["manualReviewStatus"] == "review-record-valid" else 1


if __name__ == "__main__":
    sys.exit(main())
