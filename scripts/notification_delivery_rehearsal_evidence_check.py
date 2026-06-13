#!/usr/bin/env python3
"""Validate sanitized notification delivery rehearsal evidence offline.

The checker reads one JSON artifact, emits a sanitized summary, and exits
non-zero unless every evidence category is accepted. It never sends
notifications, calls providers, reads credentials, or changes runtime routing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from evidence_safety import finding as _finding
    from evidence_safety import is_iso_timestamp
    from evidence_safety import normalize_key as _normalize_key
    from evidence_safety import scan_json_tree
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from scripts.evidence_safety import finding as _finding
    from scripts.evidence_safety import is_iso_timestamp
    from scripts.evidence_safety import normalize_key as _normalize_key
    from scripts.evidence_safety import scan_json_tree


INPUT_SCHEMA_VERSION = "wolfystock_notification_delivery_rehearsal_evidence_v1"
SUMMARY_SCHEMA_VERSION = "wolfystock_notification_delivery_rehearsal_evidence_summary_v1"
REDACTION_VERSION = "notification_delivery_rehearsal_redaction_v1"
ACCEPTED_OUTCOMES = {"accepted", "needs-review", "rejected"}

CATEGORY_LABELS = {
    "dryRunNoSendProof": "dry-run/no-send proof",
    "channelMappingSummary": "channel mapping summary",
    "recipientChannelOwnershipEvidence": "recipient/channel ownership evidence",
    "failurePathAuditSummary": "failure-path audit summary",
    "outboundSafety": "outbound disabled/default-off posture",
}

REQUIRED_TOP_LEVEL_FIELDS = (
    "schemaVersion",
    "mode",
    "environment",
    "operator",
    "observedAt",
    "dryRunNoSendProof",
    "channelMappingSummary",
    "recipientChannelOwnershipEvidence",
    "failurePathAuditSummary",
    "outboundSafety",
    "outcome",
    "evidenceRedactionVersion",
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
    r"\bGO\b|launch[-_\s]?approved|production[-_\s]?ready|automatic[-_\s]?go|"
    r"release[-_\s]?approved|public launch approved",
    re.IGNORECASE,
)
RAW_NOTIFICATION_BODY_PATTERN = re.compile(
    r"\b(?:raw[_\s-]?notification[_\s-]?(?:body|payload|message)|notification[_\s-]?body)\b",
    re.IGNORECASE,
)
RAW_PROVIDER_PAYLOAD_PATTERN = re.compile(
    r"\b(?:raw[_\s-]?provider[_\s-]?payload|provider[_\s-]?payload|raw[_\s-]?payload)\b",
    re.IGNORECASE,
)
STACK_TRACE_PATTERN = re.compile(r"\b(?:Traceback \(most recent call last\):|stack trace|stacktrace)\b", re.IGNORECASE)

RAW_RECIPIENT_KEYS = ("raw_recipient", "raw_recipient_id", "recipient_id", "recipientid")
RAW_BODY_KEYS = ("raw_notification_body", "raw_notification_payload", "notification_body")
PROVIDER_PAYLOAD_KEYS = ("provider_payload", "raw_provider_payload")
STACK_TRACE_KEYS = ("stack_trace", "stacktrace", "traceback")
SAFE_INCLUDED_PROOF_KEYS = {
    "raw_recipient_id_included",
    "rawrecipientidincluded",
    "raw_notification_body_included",
    "rawnotificationbodyincluded",
    "provider_payload_included",
    "providerpayloadincluded",
    "stack_trace_included",
    "stacktraceincluded",
}
SECRET_KEY_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "password",
    "private_key",
    "secret",
    "session",
    "token",
)
URL_KEY_MARKERS = ("webhook", "url")


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _bool_is(value: Any, expected: bool) -> bool:
    return value is expected


def _required_fields(value: Any, fields: tuple[str, ...], parent: str) -> list[dict[str, str]]:
    if not isinstance(value, dict):
        return [_finding(parent, "invalid_category_shape")]
    return [_finding(f"{parent}.{field}", "missing_required_field") for field in fields if field not in value]


def _scan_key(field: str, key: Any) -> list[dict[str, str]]:
    normalized = _normalize_key(key)
    compacted = normalized.replace("_", "")
    if normalized in SAFE_INCLUDED_PROOF_KEYS or compacted in SAFE_INCLUDED_PROOF_KEYS:
        return []
    findings: list[dict[str, str]] = []
    if any(marker in normalized for marker in RAW_RECIPIENT_KEYS):
        findings.append(_finding(field, "raw_recipient_id_forbidden"))
    if any(marker in normalized for marker in RAW_BODY_KEYS):
        findings.append(_finding(field, "raw_notification_body_forbidden"))
    if any(marker in normalized for marker in PROVIDER_PAYLOAD_KEYS):
        findings.append(_finding(field, "provider_payload_forbidden"))
    if any(marker in normalized for marker in STACK_TRACE_KEYS):
        findings.append(_finding(field, "stack_trace_forbidden"))
    if any(marker in normalized for marker in SECRET_KEY_MARKERS):
        findings.append(_finding(field, "unsafe_secret_marker"))
    if any(marker in normalized for marker in URL_KEY_MARKERS):
        findings.append(_finding(field, "unsafe_url_value"))
    return findings


def _scan_string(field: str, value: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if EMAIL_PATTERN.search(value) or PHONE_PATTERN.search(value):
        findings.append(_finding(field, "unsafe_contact_value"))
    if URL_PATTERN.search(value):
        findings.append(_finding(field, "unsafe_url_value"))
    if any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
        findings.append(_finding(field, "unsafe_secret_marker"))
    if RAW_NOTIFICATION_BODY_PATTERN.search(value):
        findings.append(_finding(field, "raw_notification_body_forbidden"))
    if RAW_PROVIDER_PAYLOAD_PATTERN.search(value):
        findings.append(_finding(field, "provider_payload_forbidden"))
    if STACK_TRACE_PATTERN.search(value):
        findings.append(_finding(field, "stack_trace_forbidden"))
    if GO_CLAIM_PATTERN.search(value):
        findings.append(_finding(field, "launch_approval_claim_forbidden"))
    return findings


def _scan_tree(value: Any) -> list[dict[str, str]]:
    return scan_json_tree(value, scan_key=_scan_key, scan_string=_scan_string)


def _validate_dry_run(section: Any) -> list[dict[str, str]]:
    findings = _required_fields(
        section,
        (
            "dryRunOnly",
            "noOutboundSent",
            "deliveryClientPatchedOrDisabled",
            "providerCallsExecuted",
            "checkerNetworkCallsEnabled",
            "outcome",
        ),
        "dryRunNoSendProof",
    )
    if not isinstance(section, dict):
        return findings
    if not (
        _bool_is(section.get("dryRunOnly"), True)
        and _bool_is(section.get("noOutboundSent"), True)
        and _bool_is(section.get("deliveryClientPatchedOrDisabled"), True)
    ):
        findings.append(_finding("dryRunNoSendProof", "dry_run_no_send_required"))
    if section.get("providerCallsExecuted") is not False or section.get("checkerNetworkCallsEnabled") is not False:
        findings.append(_finding("dryRunNoSendProof", "external_provider_or_network_call_forbidden"))
    if str(section.get("outcome") or "").strip().lower() not in ACCEPTED_OUTCOMES:
        findings.append(_finding("dryRunNoSendProof.outcome", "invalid_outcome"))
    return findings


def _validate_channel_mapping(section: Any) -> list[dict[str, str]]:
    findings = _required_fields(section, ("mappingComplete", "routes"), "channelMappingSummary")
    if not isinstance(section, dict):
        return findings
    if section.get("mappingComplete") is not True:
        findings.append(_finding("channelMappingSummary.mappingComplete", "channel_mapping_incomplete"))
    routes = section.get("routes")
    if not isinstance(routes, list) or not routes:
        findings.append(_finding("channelMappingSummary.routes", "channel_mapping_missing"))
        return findings
    for index, route in enumerate(routes):
        field = f"channelMappingSummary.routes[{index}]"
        findings.extend(
            _required_fields(
                route,
                ("routeLabel", "channelLabel", "ownerLabel", "channelType", "mappingSourceLabel"),
                field,
            )
        )
        if isinstance(route, dict):
            for label_field in ("routeLabel", "channelLabel", "ownerLabel", "channelType", "mappingSourceLabel"):
                if label_field in route and not _non_empty_text(route.get(label_field)):
                    findings.append(_finding(f"{field}.{label_field}", "invalid_sanitized_label"))
    return findings


def _validate_ownership(section: Any) -> list[dict[str, str]]:
    findings = _required_fields(section, ("sanitizedLabelsOnly", "owners"), "recipientChannelOwnershipEvidence")
    if not isinstance(section, dict):
        return findings
    if section.get("sanitizedLabelsOnly") is not True:
        findings.append(_finding("recipientChannelOwnershipEvidence.sanitizedLabelsOnly", "sanitized_labels_required"))
    owners = section.get("owners")
    if not isinstance(owners, list) or not owners:
        findings.append(_finding("recipientChannelOwnershipEvidence.owners", "recipient_channel_ownership_missing"))
        return findings
    for index, owner in enumerate(owners):
        field = f"recipientChannelOwnershipEvidence.owners[{index}]"
        findings.extend(
            _required_fields(
                owner,
                (
                    "ownerLabel",
                    "channelLabel",
                    "ownershipEvidenceLabel",
                    "recipientLabel",
                    "manualApprovalRequired",
                    "rawRecipientIdIncluded",
                ),
                field,
            )
        )
        if isinstance(owner, dict):
            if owner.get("manualApprovalRequired") is not True:
                findings.append(_finding(f"{field}.manualApprovalRequired", "manual_approval_required"))
            if owner.get("rawRecipientIdIncluded") is not False:
                findings.append(_finding(f"{field}.rawRecipientIdIncluded", "raw_recipient_id_forbidden"))
    return findings


def _validate_failure_paths(section: Any) -> list[dict[str, str]]:
    findings = _required_fields(section, ("failurePathsAudited", "cases"), "failurePathAuditSummary")
    if not isinstance(section, dict):
        return findings
    if section.get("failurePathsAudited") is not True:
        findings.append(_finding("failurePathAuditSummary.failurePathsAudited", "failure_path_audit_missing"))
    cases = section.get("cases")
    if not isinstance(cases, list) or not cases:
        findings.append(_finding("failurePathAuditSummary.cases", "failure_path_audit_missing"))
        return findings
    for index, case in enumerate(cases):
        field = f"failurePathAuditSummary.cases[{index}]"
        findings.extend(
            _required_fields(
                case,
                (
                    "caseLabel",
                    "routeLabel",
                    "sanitizedReasonCode",
                    "coreFlowContinues",
                    "rawNotificationBodyIncluded",
                    "providerPayloadIncluded",
                    "stackTraceIncluded",
                ),
                field,
            )
        )
        if isinstance(case, dict):
            if case.get("coreFlowContinues") is not True:
                findings.append(_finding(f"{field}.coreFlowContinues", "core_flow_continuation_required"))
            if case.get("rawNotificationBodyIncluded") is not False:
                findings.append(_finding(f"{field}.rawNotificationBodyIncluded", "raw_notification_body_forbidden"))
            if case.get("providerPayloadIncluded") is not False:
                findings.append(_finding(f"{field}.providerPayloadIncluded", "provider_payload_forbidden"))
            if case.get("stackTraceIncluded") is not False:
                findings.append(_finding(f"{field}.stackTraceIncluded", "stack_trace_forbidden"))
    return findings


def _validate_outbound_safety(section: Any) -> list[dict[str, str]]:
    findings = _required_fields(
        section,
        (
            "outboundDisabledByDefault",
            "externalProviderCallsByChecker",
            "manualApprovalRequiredForRealDelivery",
            "realDeliveryRehearsalApproved",
            "runtimeNotificationBehaviorChanged",
            "releaseApproved",
            "publicLaunchReady",
        ),
        "outboundSafety",
    )
    if not isinstance(section, dict):
        return findings
    if section.get("outboundDisabledByDefault") is not True:
        findings.append(_finding("outboundSafety.outboundDisabledByDefault", "outbound_disabled_by_default_required"))
    if section.get("externalProviderCallsByChecker") is not False:
        findings.append(_finding("outboundSafety.externalProviderCallsByChecker", "external_provider_or_network_call_forbidden"))
    if section.get("manualApprovalRequiredForRealDelivery") is not True:
        findings.append(_finding("outboundSafety.manualApprovalRequiredForRealDelivery", "manual_approval_required"))
    if section.get("realDeliveryRehearsalApproved") is not False:
        findings.append(_finding("outboundSafety.realDeliveryRehearsalApproved", "real_delivery_approval_not_launch_evidence"))
    if section.get("runtimeNotificationBehaviorChanged") is not False:
        findings.append(_finding("outboundSafety.runtimeNotificationBehaviorChanged", "runtime_notification_behavior_change_forbidden"))
    if section.get("releaseApproved") is not False:
        findings.append(_finding("outboundSafety.releaseApproved", "release_approval_forbidden"))
    if section.get("publicLaunchReady") is not False:
        findings.append(_finding("outboundSafety.publicLaunchReady", "public_launch_ready_forbidden"))
    return findings


def _category_has_findings(category: str, findings: list[dict[str, str]]) -> bool:
    return any(finding["field"] == category or finding["field"].startswith(f"{category}.") for finding in findings)


def validate_artifact(payload: Any) -> dict[str, Any]:
    findings: list[dict[str, str]] = []

    if not isinstance(payload, dict):
        payload = {}
        findings.append(_finding("$", "invalid_json_object"))

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in payload:
            findings.append(_finding(field, "missing_required_field"))
            if field in CATEGORY_LABELS:
                findings.append(_finding(field, "missing_required_category"))

    if payload.get("schemaVersion") != INPUT_SCHEMA_VERSION:
        findings.append(_finding("schemaVersion", "invalid_schema_version"))
    if payload.get("mode") != "offline-sanitized-rehearsal":
        findings.append(_finding("mode", "invalid_mode"))
    if not _non_empty_text(payload.get("environment")):
        findings.append(_finding("environment", "invalid_required_field"))
    if not _non_empty_text(payload.get("operator")):
        findings.append(_finding("operator", "invalid_required_field"))
    if not is_iso_timestamp(payload.get("observedAt")):
        findings.append(_finding("observedAt", "invalid_observed_at"))
    if payload.get("evidenceRedactionVersion") != REDACTION_VERSION:
        findings.append(_finding("evidenceRedactionVersion", "invalid_redaction_version"))
    if str(payload.get("outcome") or "").strip().lower() not in ACCEPTED_OUTCOMES:
        findings.append(_finding("outcome", "invalid_outcome"))

    findings.extend(_validate_dry_run(payload.get("dryRunNoSendProof")))
    findings.extend(_validate_channel_mapping(payload.get("channelMappingSummary")))
    findings.extend(_validate_ownership(payload.get("recipientChannelOwnershipEvidence")))
    findings.extend(_validate_failure_paths(payload.get("failurePathAuditSummary")))
    findings.extend(_validate_outbound_safety(payload.get("outboundSafety")))
    findings.extend(_scan_tree(payload))

    deduped_findings = sorted(
        {json.dumps(item, sort_keys=True): item for item in findings}.values(),
        key=lambda item: (item["field"], item["reasonCode"]),
    )
    accepted_categories = [
        label
        for category, label in CATEGORY_LABELS.items()
        if category in payload and not _category_has_findings(category, deduped_findings)
    ]
    rejected_categories = [
        label
        for category, label in CATEGORY_LABELS.items()
        if category not in payload or _category_has_findings(category, deduped_findings)
    ]
    passed = not deduped_findings and len(accepted_categories) == len(CATEGORY_LABELS)

    return {
        "schemaVersion": SUMMARY_SCHEMA_VERSION,
        "tool": "scripts/notification_delivery_rehearsal_evidence_check.py",
        "inputSchemaVersion": str(payload.get("schemaVersion") or "") if isinstance(payload, dict) else "",
        "status": "pass" if passed else "fail",
        "finalStatus": "EVIDENCE-READY" if passed else "REJECTED",
        "releaseApproved": False,
        "publicLaunchReady": False,
        "manualApprovalRequiredForRealDelivery": not any(
            finding["reasonCode"] == "manual_approval_required" for finding in deduped_findings
        ),
        "networkCallsExecutedByValidator": False,
        "outboundNotificationsSentByValidator": False,
        "runtimeNotificationBehaviorChanged": False,
        "acceptedCategories": accepted_categories,
        "rejectedCategories": rejected_categories,
        "checks": {
            "dryRunNoSendProofRecorded": "dry-run/no-send proof" in accepted_categories,
            "channelMappingRecorded": "channel mapping summary" in accepted_categories,
            "recipientChannelOwnershipLabelsRecorded": "recipient/channel ownership evidence" in accepted_categories,
            "failurePathAuditSanitized": "failure-path audit summary" in accepted_categories,
            "outboundDisabledByDefault": not any(
                finding["reasonCode"] == "outbound_disabled_by_default_required" for finding in deduped_findings
            ),
            "noProviderNetworkCallsByChecker": not any(
                finding["reasonCode"] == "external_provider_or_network_call_forbidden" for finding in deduped_findings
            ),
            "manualApprovalRequiredForRealDelivery": not any(
                finding["reasonCode"] == "manual_approval_required" for finding in deduped_findings
            ),
            "releaseApprovedFalse": not any(
                finding["reasonCode"] == "release_approval_forbidden" for finding in deduped_findings
            ),
            "publicLaunchReadyFalse": not any(
                finding["reasonCode"] == "public_launch_ready_forbidden" for finding in deduped_findings
            ),
            "runtimeBehaviorUnchanged": not any(
                finding["reasonCode"] == "runtime_notification_behavior_change_forbidden" for finding in deduped_findings
            ),
        },
        "summary": {
            "acceptedCategories": len(accepted_categories),
            "rejectedCategories": len(rejected_categories),
            "findings": len(deduped_findings),
        },
        "findings": deduped_findings,
        "sanitization": {
            "realSecretsIncluded": False,
            "rawCredentialValuesIncluded": False,
            "rawRecipientIdsIncluded": False,
            "rawNotificationBodiesIncluded": False,
            "rawProviderPayloadsIncluded": False,
            "stackTracesIncluded": False,
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
    parser.add_argument("artifact", nargs="?", help="Sanitized notification delivery rehearsal evidence JSON artifact.")
    parser.add_argument("--evidence", dest="evidence", help="Sanitized notification delivery rehearsal evidence JSON artifact.")
    args = parser.parse_args(argv)
    artifact_arg = args.evidence or args.artifact
    if not artifact_arg:
        parser.error("an evidence artifact path is required")

    try:
        payload = _load_json(Path(artifact_arg))
    except (OSError, json.JSONDecodeError):
        summary = validate_artifact({})
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
