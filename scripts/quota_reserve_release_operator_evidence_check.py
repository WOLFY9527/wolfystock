#!/usr/bin/env python3
"""Validate sanitized quota reserve/release operator evidence offline.

This helper reads a sanitized JSON artifact, or a directory of sanitized JSON
artifacts, and emits an aggregate JSON verdict. It does not import route
handlers, quota services, storage, auth, providers, or live API clients.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from evidence_safety import Finding
    from evidence_safety import compact_key as _compact_key
    from evidence_safety import finding as _finding
    from evidence_safety import missing_fields as _missing_fields
    from evidence_safety import read_json_document as _read_json_document
    from evidence_safety import scan_json_tree
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from scripts.evidence_safety import Finding
    from scripts.evidence_safety import compact_key as _compact_key
    from scripts.evidence_safety import finding as _finding
    from scripts.evidence_safety import missing_fields as _missing_fields
    from scripts.evidence_safety import read_json_document as _read_json_document
    from scripts.evidence_safety import scan_json_tree


INPUT_SCHEMA_VERSION = "wolfystock_quota_reserve_release_operator_evidence_v1"
SUMMARY_SCHEMA_VERSION = "wolfystock_quota_reserve_release_operator_evidence_summary_v1"

REQUIRED_CATEGORIES = (
    "configSnapshot",
    "successReserveRelease",
    "reserveFailureFailOpen",
    "analysisFailureFinallyRelease",
    "releaseFailureFailOpen",
    "executionLogMetadataSafety",
    "quotaWindowBeforeAfter",
    "costLedgerReservationEvidence",
    "rollbackProof",
    "acceptedEvidencePacket",
)

ALLOWED_ROUTE_LABELS = {"sync_single_stock_only"}
ALLOWED_EVIDENCE_SCOPES = {"synthetic", "private_beta", "internal_private_beta"}
ALLOWED_OWNER_BOUNDARY_LABELS = {"explicit_owner_allowlist"}
ALLOWED_ROLLBACK_SWITCH_LABELS = {
    "pilot_disabled",
    "owner_allowlist_removal",
    "pilot_flag_or_owner_allowlist_removal",
}
ALLOWED_INVOICE_EXPORT_RECONCILIATION_STATUSES = {
    "missing",
    "not_implemented",
    "not_accepted",
    "advisory_only",
}
AGGREGATE_QUOTA_FIELDS = {"reserved_units", "consumed_units", "request_count"}
ALLOWED_TERMINAL_TRANSITION_OWNERS = {
    "not_wired",
    "route_pilot_estimated_units",
    "cost_ledger_reconciliation",
}

RESERVATION_ID_KEYS = {"reservationid", "quotareservationid", "rawreservationid"}
IDEMPOTENCY_KEYS = {"idempotencykey", "idempotencyhash", "idempotencymaterial"}
OWNER_ALLOWLIST_VALUE_KEYS = {
    "allowlistedowners",
    "allowlistowners",
    "allowlistvalues",
    "allowedowners",
    "ownerallowlist",
    "ownerallowlistentries",
    "ownerallowlistvalue",
    "ownerallowlistvalues",
}
RAW_REQUEST_CONTEXT_KEYS = {
    "authorization",
    "body",
    "cookie",
    "cookies",
    "header",
    "headers",
    "owner",
    "ownerid",
    "owneruserid",
    "rawbody",
    "rawowner",
    "rawownerid",
    "rawrequest",
    "rawrequestbody",
    "rawsession",
    "rawuser",
    "rawuserid",
    "request",
    "requestbody",
    "requestheader",
    "requestheaders",
    "session",
    "sessionid",
    "token",
    "user",
    "userid",
}
RAW_USER_TEXT_KEYS = {
    "originalquery",
    "prompt",
    "rawprompt",
    "rawtext",
    "rawusertext",
    "stockname",
    "userprompt",
    "usertext",
}
PROVIDER_OR_MODEL_PAYLOAD_KEYS = {
    "llmrawresponse",
    "llmresponse",
    "modelpayload",
    "modelresponse",
    "providerpayload",
    "providerresponse",
    "rawmodelpayload",
    "rawproviderpayload",
}
RAW_EXCEPTION_KEYS = {
    "errorstack",
    "exception",
    "exceptiontext",
    "rawexception",
    "rawexceptiontext",
    "stacktrace",
    "traceback",
}
SECRET_KEYS = {
    "apikey",
    "apiKey",
    "bearer",
    "credential",
    "credentials",
    "password",
    "privatekey",
    "secret",
    "webhook",
}
DB_ROW_ID_KEYS = {"databaserowid", "dbrowid", "rowid", "storagerowid"}
WINDOW_IDENTITY_KEYS = {"windowidentitykey"}
ROW_LEVEL_RESERVATION_KEYS = {
    "reservationdetails",
    "reservationlist",
    "reservationrecords",
    "reservationrow",
    "reservationrows",
    "reservations",
}
PROVIDER_INVOICE_EXPORT_KEYS = {
    "billingexport",
    "billingexportfile",
    "invoiceexportfile",
    "invoiceexportid",
    "invoiceexportref",
    "invoiceexportrows",
    "invoiceid",
    "providerbillingexport",
    "providerinvoiceexport",
    "providerinvoiceexportid",
    "providerinvoiceexportref",
    "providerinvoiceid",
    "rawbillingexport",
    "rawinvoiceexport",
    "rawproviderinvoiceexport",
}

SECRET_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("raw_reservation_identifier_forbidden", re.compile(r"\bqres_[A-Za-z0-9._:-]{4,}\b", re.IGNORECASE)),
    (
        "idempotency_material_forbidden",
        re.compile(r"\bquota:analysis_sync_single_stock:v[0-9]\b", re.IGNORECASE),
    ),
    ("window_identity_key_forbidden", re.compile(r"\bwindow_identity_key\b", re.IGNORECASE)),
    (
        "secret_like_value_forbidden",
        re.compile(
            r"\b(?:api[_-]?key|apikey|access_token|token|secret|password|cookie|session)\s*[=:]",
            re.IGNORECASE,
        ),
    ),
    (
        "secret_like_value_forbidden",
        re.compile(r"\b(?:bearer\s+|authorization\s*:\s*bearer\s+)[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    ),
    ("secret_like_value_forbidden", re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")),
    ("raw_exception_or_stack_trace_forbidden", re.compile(r"Traceback \(most recent call last\):", re.IGNORECASE)),
    ("raw_exception_or_stack_trace_forbidden", re.compile(r"\bStack trace\b|\bException:", re.IGNORECASE)),
    ("raw_exception_or_stack_trace_forbidden", re.compile(r"\bFile \"[^\"]+\", line \d+", re.IGNORECASE)),
    ("launch_approval_claim_forbidden", re.compile(r"\bGO\b|launch[-_\s]?approved|public launch approved", re.IGNORECASE)),
    ("live_enforcement_claim_forbidden", re.compile(r"\blive[-_\s]?enforcement[-_\s]?(?:enabled|approved)\b", re.IGNORECASE)),
    ("consume_wiring_claim_forbidden", re.compile(r"\bconsume[-_\s]?wiring[-_\s]?(?:enabled|approved)\b", re.IGNORECASE)),
    (
        "provider_invoice_export_data_forbidden",
        re.compile(r"\binv[-_](?:real[-_])?provider[-_][A-Za-z0-9._:-]{3,}\b", re.IGNORECASE),
    ),
)


def _bool_is(value: Any, expected: bool) -> bool:
    return isinstance(value, bool) and value is expected


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def _path_for_category(category_id: str, field: str) -> str:
    return f"{category_id}.{field}"


def _scan_key(field: str, key: Any) -> list[dict[str, str]]:
    compact = _compact_key(key)
    if compact in RESERVATION_ID_KEYS:
        return [_finding(field, "raw_reservation_identifier_forbidden")]
    if compact in IDEMPOTENCY_KEYS:
        return [_finding(field, "idempotency_material_forbidden")]
    if compact in OWNER_ALLOWLIST_VALUE_KEYS:
        return [_finding(field, "owner_allowlist_values_forbidden")]
    if compact in RAW_REQUEST_CONTEXT_KEYS:
        return [_finding(field, "raw_request_context_forbidden")]
    if compact in RAW_USER_TEXT_KEYS:
        return [_finding(field, "raw_user_text_forbidden")]
    if compact in PROVIDER_OR_MODEL_PAYLOAD_KEYS:
        return [_finding(field, "provider_or_model_payload_forbidden")]
    if compact in RAW_EXCEPTION_KEYS:
        return [_finding(field, "raw_exception_or_stack_trace_forbidden")]
    if compact in SECRET_KEYS:
        return [_finding(field, "secret_like_value_forbidden")]
    if compact in DB_ROW_ID_KEYS:
        return [_finding(field, "db_row_id_forbidden")]
    if compact in WINDOW_IDENTITY_KEYS:
        return [_finding(field, "window_identity_key_forbidden")]
    if compact in ROW_LEVEL_RESERVATION_KEYS:
        return [_finding(field, "row_level_reservation_data_forbidden")]
    if compact in PROVIDER_INVOICE_EXPORT_KEYS:
        return [_finding(field, "provider_invoice_export_data_forbidden")]
    return []


def _scan_entry(field: str, key: Any, value: Any) -> list[dict[str, str]]:
    compact = _compact_key(key)
    if compact in ROW_LEVEL_RESERVATION_KEYS and isinstance(value, list):
        return [_finding(field, "row_level_reservation_data_forbidden")]
    if compact == "ownerallowlistconfigured" and not isinstance(value, bool):
        return [_finding(field, "owner_allowlist_values_forbidden")]
    return []


def _scan_string(field: str, value: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for reason_code, pattern in SECRET_VALUE_PATTERNS:
        if pattern.search(value):
            findings.append(_finding(field, reason_code))
            break
    return findings


def _scan_forbidden_raw_evidence(value: Any) -> list[dict[str, str]]:
    return scan_json_tree(
        value,
        scan_key=_scan_key,
        scan_entry=_scan_entry,
        scan_string=_scan_string,
        recurse_on_key_findings=False,
    )


def _load_json_file(path: Path) -> tuple[Any | None, list[dict[str, str]]]:
    return _read_json_document(path, failure_reason_code="artifact_read_failed")


def _load_artifacts(path: Path) -> tuple[list[Any], list[dict[str, str]], int]:
    if path.is_dir():
        artifacts: list[Any] = []
        findings: list[dict[str, str]] = []
        json_paths = sorted(candidate for candidate in path.iterdir() if candidate.suffix.lower() == ".json")
        if not json_paths:
            return [], [_finding("$", "artifact_directory_contains_no_json")], 0
        for artifact_path in json_paths:
            artifact, artifact_findings = _load_json_file(artifact_path)
            findings.extend(artifact_findings)
            if artifact_findings:
                continue
            artifacts.append(artifact)
        return artifacts, findings, len(json_paths)
    artifact, findings = _load_json_file(path)
    return ([] if findings else [artifact], findings, 1)


def _extract_categories(artifacts: list[Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    categories: dict[str, Any] = {}
    findings: list[dict[str, str]] = []
    for artifact_index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            findings.append(_finding(f"artifact[{artifact_index}]", "artifact_must_be_json_object"))
            continue
        if artifact.get("schemaVersion") not in {None, INPUT_SCHEMA_VERSION}:
            findings.append(_finding(f"artifact[{artifact_index}].schemaVersion", "invalid_schema_version"))

        section_source = artifact.get("sections")
        if isinstance(section_source, dict):
            candidates = section_source
        else:
            candidates = artifact

        for category_id in REQUIRED_CATEGORIES:
            if category_id not in candidates:
                continue
            if category_id in categories:
                findings.append(_finding(category_id, "duplicate_required_category"))
                continue
            categories[category_id] = candidates[category_id]
    return categories, findings


def _validate_config_snapshot(category_id: str, category: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for field in _missing_fields(
        category,
        ("enabledByDefault", "ownerAllowlistConfigured", "publicGlobalEnablement", "routeLabel", "advisoryMode"),
    ):
        findings.append(_finding(_path_for_category(category_id, field), "missing_required_field"))
    if "enabledByDefault" in category and not _bool_is(category.get("enabledByDefault"), False):
        findings.append(_finding(_path_for_category(category_id, "enabledByDefault"), "default_off_required"))
    if "ownerAllowlistConfigured" in category and not isinstance(category.get("ownerAllowlistConfigured"), bool):
        findings.append(_finding(_path_for_category(category_id, "ownerAllowlistConfigured"), "invalid_boolean"))
    if "publicGlobalEnablement" in category and not _bool_is(category.get("publicGlobalEnablement"), False):
        findings.append(_finding(_path_for_category(category_id, "publicGlobalEnablement"), "public_enablement_forbidden"))
    if "routeLabel" in category and category.get("routeLabel") not in ALLOWED_ROUTE_LABELS:
        findings.append(_finding(_path_for_category(category_id, "routeLabel"), "invalid_route_label"))
    if "advisoryMode" in category and not _bool_is(category.get("advisoryMode"), True):
        findings.append(_finding(_path_for_category(category_id, "advisoryMode"), "advisory_mode_required"))
    return findings


def _validate_success_case(category_id: str, category: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    required = (
        "sourceScope",
        "routeLabel",
        "reserveAttempted",
        "reserveSucceeded",
        "releaseAttempted",
        "releaseSucceeded",
        "analysisCompleted",
        "responseShapeChanged",
    )
    for field in _missing_fields(category, required):
        findings.append(_finding(_path_for_category(category_id, field), "missing_required_field"))
    if "sourceScope" in category and category.get("sourceScope") not in ALLOWED_EVIDENCE_SCOPES:
        findings.append(_finding(_path_for_category(category_id, "sourceScope"), "invalid_evidence_scope"))
    if "routeLabel" in category and category.get("routeLabel") not in ALLOWED_ROUTE_LABELS:
        findings.append(_finding(_path_for_category(category_id, "routeLabel"), "invalid_route_label"))
    for field in ("reserveAttempted", "reserveSucceeded", "releaseAttempted", "releaseSucceeded", "analysisCompleted"):
        if field in category and not _bool_is(category.get(field), True):
            findings.append(_finding(_path_for_category(category_id, field), "expected_true"))
    if "responseShapeChanged" in category and not _bool_is(category.get("responseShapeChanged"), False):
        findings.append(_finding(_path_for_category(category_id, "responseShapeChanged"), "response_shape_change_forbidden"))
    return findings


def _validate_reserve_failure(category_id: str, category: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    required = (
        "routeLabel",
        "reserveAttempted",
        "reserveSucceeded",
        "analysisProceeded",
        "requestBlocked",
        "consumeAttempted",
        "failOpen",
    )
    for field in _missing_fields(category, required):
        findings.append(_finding(_path_for_category(category_id, field), "missing_required_field"))
    if "routeLabel" in category and category.get("routeLabel") not in ALLOWED_ROUTE_LABELS:
        findings.append(_finding(_path_for_category(category_id, "routeLabel"), "invalid_route_label"))
    for field in ("reserveAttempted", "analysisProceeded", "failOpen"):
        if field in category and not _bool_is(category.get(field), True):
            findings.append(_finding(_path_for_category(category_id, field), "expected_true"))
    for field in ("reserveSucceeded", "requestBlocked", "consumeAttempted"):
        if field in category and not _bool_is(category.get(field), False):
            findings.append(_finding(_path_for_category(category_id, field), "expected_false"))
    return findings


def _validate_analysis_failure(category_id: str, category: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    required = (
        "routeLabel",
        "reserveSucceeded",
        "analysisSucceeded",
        "releaseAttempted",
        "releaseFromFinally",
        "responseShapeChanged",
    )
    for field in _missing_fields(category, required):
        findings.append(_finding(_path_for_category(category_id, field), "missing_required_field"))
    if "routeLabel" in category and category.get("routeLabel") not in ALLOWED_ROUTE_LABELS:
        findings.append(_finding(_path_for_category(category_id, "routeLabel"), "invalid_route_label"))
    for field in ("reserveSucceeded", "releaseAttempted", "releaseFromFinally"):
        if field in category and not _bool_is(category.get(field), True):
            findings.append(_finding(_path_for_category(category_id, field), "expected_true"))
    for field in ("analysisSucceeded", "responseShapeChanged"):
        if field in category and not _bool_is(category.get(field), False):
            findings.append(_finding(_path_for_category(category_id, field), "expected_false"))
    return findings


def _validate_release_failure(category_id: str, category: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    required = (
        "routeLabel",
        "releaseAttempted",
        "releaseSucceeded",
        "warningRecorded",
        "requestBlocked",
        "consumeAttempted",
        "failOpen",
    )
    for field in _missing_fields(category, required):
        findings.append(_finding(_path_for_category(category_id, field), "missing_required_field"))
    if "routeLabel" in category and category.get("routeLabel") not in ALLOWED_ROUTE_LABELS:
        findings.append(_finding(_path_for_category(category_id, "routeLabel"), "invalid_route_label"))
    for field in ("releaseAttempted", "warningRecorded", "failOpen"):
        if field in category and not _bool_is(category.get(field), True):
            findings.append(_finding(_path_for_category(category_id, field), "expected_true"))
    for field in ("releaseSucceeded", "requestBlocked", "consumeAttempted"):
        if field in category and not _bool_is(category.get(field), False):
            findings.append(_finding(_path_for_category(category_id, field), "expected_false"))
    return findings


def _validate_metadata_safety(category_id: str, category: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    required = (
        "boundedMetadataOnly",
        "rawReservationIdAbsent",
        "idempotencyMaterialAbsent",
        "rawOwnerOrRequestAbsent",
        "rawProviderOrExceptionAbsent",
    )
    for field in _missing_fields(category, required):
        findings.append(_finding(_path_for_category(category_id, field), "missing_required_field"))
    for field in required:
        if field in category and not _bool_is(category.get(field), True):
            findings.append(_finding(_path_for_category(category_id, field), "expected_true"))
    return findings


def _validate_quota_totals(category_id: str, label: str, value: Any) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if not isinstance(value, dict):
        return [_finding(_path_for_category(category_id, label), "invalid_quota_window_summary")]
    for field in AGGREGATE_QUOTA_FIELDS:
        if field not in value:
            findings.append(_finding(_path_for_category(category_id, f"{label}.{field}"), "missing_required_field"))
        elif not _is_number(value.get(field)):
            findings.append(_finding(_path_for_category(category_id, f"{label}.{field}"), "invalid_aggregate_count"))
    return findings


def _validate_aggregate_counts(category_id: str, field: str, value: Any) -> list[dict[str, str]]:
    if not isinstance(value, dict):
        return [_finding(_path_for_category(category_id, field), "invalid_aggregate_counts")]
    findings: list[dict[str, str]] = []
    for key, count in value.items():
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", str(key)):
            findings.append(_finding(_path_for_category(category_id, field), "invalid_aggregate_label"))
        if not _is_number(count):
            findings.append(_finding(_path_for_category(category_id, field), "invalid_aggregate_count"))
    return findings


def _validate_quota_window(category_id: str, category: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for field in _missing_fields(category, ("before", "after", "aggregateOnly", "reservedUnitsLeaked")):
        findings.append(_finding(_path_for_category(category_id, field), "missing_required_field"))
    if "before" in category:
        findings.extend(_validate_quota_totals(category_id, "before", category.get("before")))
    if "after" in category:
        findings.extend(_validate_quota_totals(category_id, "after", category.get("after")))
    if "aggregateOnly" in category and not _bool_is(category.get("aggregateOnly"), True):
        findings.append(_finding(_path_for_category(category_id, "aggregateOnly"), "aggregate_only_required"))
    if "reservedUnitsLeaked" in category and not _bool_is(category.get("reservedUnitsLeaked"), False):
        findings.append(_finding(_path_for_category(category_id, "reservedUnitsLeaked"), "reserved_units_leaked"))
    for aggregate_field in ("countsByStatus", "countsByReason"):
        if aggregate_field in category:
            findings.extend(_validate_aggregate_counts(category_id, aggregate_field, category[aggregate_field]))
    return findings


def _validate_cost_ledger_reservation_evidence(category_id: str, category: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    required = (
        "routeLabel",
        "ledgerFieldAvailable",
        "routeReservationIdPropagated",
        "routeEstimatedUnitsOnly",
        "billingAuthoritativeActualProviderCost",
        "terminalTransitionOwner",
        "exactOnceActualCostConsumeAccepted",
        "rawReservationIdAbsent",
        "runtimeBehaviorChanged",
        "publicLaunchApproval",
    )
    for field in _missing_fields(category, required):
        findings.append(_finding(_path_for_category(category_id, field), "missing_required_field"))
    if "routeLabel" in category and category.get("routeLabel") not in ALLOWED_ROUTE_LABELS:
        findings.append(_finding(_path_for_category(category_id, "routeLabel"), "invalid_route_label"))
    if "ledgerFieldAvailable" in category and not _bool_is(category.get("ledgerFieldAvailable"), True):
        findings.append(_finding(_path_for_category(category_id, "ledgerFieldAvailable"), "expected_true"))
    if "routeReservationIdPropagated" in category and not isinstance(category.get("routeReservationIdPropagated"), bool):
        findings.append(_finding(_path_for_category(category_id, "routeReservationIdPropagated"), "invalid_boolean"))
    for field in ("routeEstimatedUnitsOnly", "rawReservationIdAbsent"):
        if field in category and not _bool_is(category.get(field), True):
            findings.append(_finding(_path_for_category(category_id, field), "expected_true"))
    if (
        "billingAuthoritativeActualProviderCost" in category
        and not _bool_is(category.get("billingAuthoritativeActualProviderCost"), False)
    ):
        findings.append(
            _finding(_path_for_category(category_id, "billingAuthoritativeActualProviderCost"), "billing_authority_claim_forbidden")
        )
    if "exactOnceActualCostConsumeAccepted" in category and not _bool_is(category.get("exactOnceActualCostConsumeAccepted"), False):
        findings.append(
            _finding(_path_for_category(category_id, "exactOnceActualCostConsumeAccepted"), "exact_once_actual_cost_consume_not_accepted")
        )
    if "runtimeBehaviorChanged" in category and not _bool_is(category.get("runtimeBehaviorChanged"), False):
        findings.append(_finding(_path_for_category(category_id, "runtimeBehaviorChanged"), "runtime_behavior_change_forbidden"))
    if "publicLaunchApproval" in category and not _bool_is(category.get("publicLaunchApproval"), False):
        findings.append(_finding(_path_for_category(category_id, "publicLaunchApproval"), "public_launch_approval_forbidden"))
    if (
        "terminalTransitionOwner" in category
        and category.get("terminalTransitionOwner") not in ALLOWED_TERMINAL_TRANSITION_OWNERS
    ):
        findings.append(_finding(_path_for_category(category_id, "terminalTransitionOwner"), "invalid_terminal_transition_owner"))
    return findings


def _validate_rollback(category_id: str, category: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for field in _missing_fields(category, ("routeOutOfScope", "responseShapeChanged")):
        findings.append(_finding(_path_for_category(category_id, field), "missing_required_field"))
    pilot_disabled = category.get("pilotDisabled")
    owner_removed = category.get("ownerRemovedFromAllowlist")
    if not (_bool_is(pilot_disabled, True) or _bool_is(owner_removed, True)):
        findings.append(_finding(category_id, "rollback_mechanism_required"))
    if "routeOutOfScope" in category and not _bool_is(category.get("routeOutOfScope"), True):
        findings.append(_finding(_path_for_category(category_id, "routeOutOfScope"), "expected_true"))
    if "responseShapeChanged" in category and not _bool_is(category.get("responseShapeChanged"), False):
        findings.append(_finding(_path_for_category(category_id, "responseShapeChanged"), "response_shape_change_forbidden"))
    return findings


def _is_non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_accepted_evidence_packet(category_id: str, category: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    required = (
        "sourceScope",
        "defaultOffPosture",
        "liveEnforcement",
        "ownerAllowlistBoundary",
        "routeLabel",
        "guestPublicQuotaMutation",
        "disabledModeVerified",
        "rollbackSwitchLabel",
        "adminVisibilityLabel",
        "operatorVisibilityLabel",
        "invoiceExportReconciliationStatus",
        "realProviderInvoiceExportAttached",
        "publicLaunchReady",
        "releaseApproved",
    )
    for field in _missing_fields(category, required):
        findings.append(_finding(_path_for_category(category_id, field), "missing_required_field"))
    if "sourceScope" in category and category.get("sourceScope") not in ALLOWED_EVIDENCE_SCOPES:
        findings.append(_finding(_path_for_category(category_id, "sourceScope"), "invalid_evidence_scope"))
    if "defaultOffPosture" in category and not _bool_is(category.get("defaultOffPosture"), True):
        findings.append(_finding(_path_for_category(category_id, "defaultOffPosture"), "default_off_required"))
    if "liveEnforcement" in category and not _bool_is(category.get("liveEnforcement"), False):
        findings.append(_finding(_path_for_category(category_id, "liveEnforcement"), "live_enforcement_forbidden"))
    if (
        "ownerAllowlistBoundary" in category
        and category.get("ownerAllowlistBoundary") not in ALLOWED_OWNER_BOUNDARY_LABELS
    ):
        findings.append(_finding(_path_for_category(category_id, "ownerAllowlistBoundary"), "invalid_owner_allowlist_boundary"))
    if "routeLabel" in category and category.get("routeLabel") not in ALLOWED_ROUTE_LABELS:
        findings.append(_finding(_path_for_category(category_id, "routeLabel"), "invalid_route_label"))
    if "guestPublicQuotaMutation" in category and not _bool_is(category.get("guestPublicQuotaMutation"), False):
        findings.append(
            _finding(_path_for_category(category_id, "guestPublicQuotaMutation"), "guest_public_quota_mutation_forbidden")
        )
    if "disabledModeVerified" in category and not _bool_is(category.get("disabledModeVerified"), True):
        findings.append(_finding(_path_for_category(category_id, "disabledModeVerified"), "disabled_mode_evidence_required"))
    if "rollbackSwitchLabel" in category and category.get("rollbackSwitchLabel") not in ALLOWED_ROLLBACK_SWITCH_LABELS:
        findings.append(_finding(_path_for_category(category_id, "rollbackSwitchLabel"), "invalid_rollback_switch_label"))
    for field in ("adminVisibilityLabel", "operatorVisibilityLabel"):
        if field in category and not _is_non_empty_text(category.get(field)):
            findings.append(_finding(_path_for_category(category_id, field), "visibility_label_required"))
    if "invoiceExportReconciliationStatus" in category:
        status = category.get("invoiceExportReconciliationStatus")
        if status == "accepted":
            findings.append(
                _finding(
                    _path_for_category(category_id, "invoiceExportReconciliationStatus"),
                    "invoice_export_reconciliation_not_accepted",
                )
            )
        elif status not in ALLOWED_INVOICE_EXPORT_RECONCILIATION_STATUSES:
            findings.append(
                _finding(
                    _path_for_category(category_id, "invoiceExportReconciliationStatus"),
                    "invalid_invoice_export_reconciliation_status",
                )
            )
    if "realProviderInvoiceExportAttached" in category and not _bool_is(
        category.get("realProviderInvoiceExportAttached"),
        False,
    ):
        findings.append(
            _finding(
                _path_for_category(category_id, "realProviderInvoiceExportAttached"),
                "provider_invoice_export_evidence_forbidden",
            )
        )
    if "publicLaunchReady" in category and not _bool_is(category.get("publicLaunchReady"), False):
        findings.append(_finding(_path_for_category(category_id, "publicLaunchReady"), "public_launch_ready_forbidden"))
    if "releaseApproved" in category and not _bool_is(category.get("releaseApproved"), False):
        findings.append(_finding(_path_for_category(category_id, "releaseApproved"), "release_approval_forbidden"))
    return findings


CATEGORY_VALIDATORS = {
    "configSnapshot": _validate_config_snapshot,
    "successReserveRelease": _validate_success_case,
    "reserveFailureFailOpen": _validate_reserve_failure,
    "analysisFailureFinallyRelease": _validate_analysis_failure,
    "releaseFailureFailOpen": _validate_release_failure,
    "executionLogMetadataSafety": _validate_metadata_safety,
    "quotaWindowBeforeAfter": _validate_quota_window,
    "costLedgerReservationEvidence": _validate_cost_ledger_reservation_evidence,
    "rollbackProof": _validate_rollback,
    "acceptedEvidencePacket": _validate_accepted_evidence_packet,
}


def _dedupe_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        {json.dumps(finding, sort_keys=True): finding for finding in findings}.values(),
        key=lambda item: (item["field"], item["reasonCode"]),
    )


def _aggregate_findings(findings: list[dict[str, str]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for finding in findings:
        reason_code = finding["reasonCode"]
        counts[reason_code] = counts.get(reason_code, 0) + 1
    return [
        {"reasonCode": reason_code, "count": count}
        for reason_code, count in sorted(counts.items())
    ]


def _validate_categories(categories: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    category_summaries: list[dict[str, Any]] = []
    findings: list[dict[str, str]] = []
    for category_id in REQUIRED_CATEGORIES:
        category = categories.get(category_id)
        category_findings: list[dict[str, str]] = []
        if category is None:
            category_findings.append(_finding(category_id, "missing_required_category"))
        elif not isinstance(category, dict):
            category_findings.append(_finding(category_id, "invalid_category"))
        else:
            category_findings.extend(CATEGORY_VALIDATORS[category_id](category_id, category))

        findings.extend(category_findings)
        category_summaries.append(
            {
                "id": category_id,
                "status": "pass" if not category_findings else "fail",
                "findingCount": len(category_findings),
                "reasonCodes": sorted({finding["reasonCode"] for finding in category_findings}),
            }
        )
    return category_summaries, findings


def validate_artifacts(artifacts: list[Any], *, artifact_count: int, load_findings: list[dict[str, str]]) -> dict[str, Any]:
    categories, category_extraction_findings = _extract_categories(artifacts)
    category_summaries, category_findings = _validate_categories(categories)
    forbidden_findings = _scan_forbidden_raw_evidence(artifacts)
    findings = _dedupe_findings(load_findings + category_extraction_findings + category_findings + forbidden_findings)
    aggregate_findings = _aggregate_findings(findings)
    passed = not findings
    reason_codes = {finding["reasonCode"] for finding in findings}
    return {
        "schemaVersion": SUMMARY_SCHEMA_VERSION,
        "tool": "scripts/quota_reserve_release_operator_evidence_check.py",
        "inputSchemaVersion": INPUT_SCHEMA_VERSION,
        "status": "pass" if passed else "fail",
        "finalStatus": "EVIDENCE-READY" if passed else "NO-GO",
        "reviewablePacketStatus": "quota-pilot-evidence-reviewable" if passed else "quota-pilot-evidence-no-go",
        "advisoryOnly": True,
        "publicLaunchReady": False,
        "releaseApproved": False,
        "launchApproved": False,
        "liveQuotaEnforcementApproved": False,
        "consumeWiringApproved": False,
        "guestPublicQuotaMutationApproved": False,
        "invoiceExportReconciliationAccepted": False,
        "runtimeBehaviorChanged": False,
        "networkCallsExecutedByValidator": False,
        "runtimeApisCalledByValidator": False,
        "storageAccessedByValidator": False,
        "categories": category_summaries,
        "checks": {
            "requiredCategoriesPresent": all(category_id in categories for category_id in REQUIRED_CATEGORIES),
            "forbiddenRawEvidenceAbsent": not forbidden_findings,
            "quotaWindowAggregateOnly": not any(
                finding["reasonCode"] in {"row_level_reservation_data_forbidden", "window_identity_key_forbidden"}
                for finding in findings
            ),
            "routeScopeAccepted": not any(finding["reasonCode"] == "invalid_route_label" for finding in findings),
            "guestPublicQuotaMutationAbsent": "guest_public_quota_mutation_forbidden" not in reason_codes,
            "operatorVisibilityLabelsRecorded": "visibility_label_required" not in reason_codes
            and "acceptedEvidencePacket" in categories,
            "invoiceExportReconciliationNotAccepted": "invoice_export_reconciliation_not_accepted" not in reason_codes
            and "provider_invoice_export_evidence_forbidden" not in reason_codes
            and "provider_invoice_export_data_forbidden" not in reason_codes,
            "advisoryModeOnly": not any(
                finding["reasonCode"]
                in {"live_enforcement_claim_forbidden", "consume_wiring_claim_forbidden", "launch_approval_claim_forbidden"}
                for finding in findings
            ),
        },
        "summary": {
            "categoriesPassed": sum(1 for category in category_summaries if category["status"] == "pass"),
            "categoriesFailed": sum(1 for category in category_summaries if category["status"] != "pass"),
            "findings": len(findings),
            "findingGroups": len(aggregate_findings),
        },
        "artifacts": {
            "jsonArtifactsChecked": artifact_count,
            "rowLevelReservationDataIncluded": False,
            "findingValuesIncluded": False,
        },
        "findings": aggregate_findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate sanitized quota reserve/release operator evidence JSON offline."
    )
    parser.add_argument("path", nargs="?", help="Sanitized JSON artifact or directory containing JSON artifacts.")
    parser.add_argument("--evidence", dest="evidence", help="Sanitized JSON artifact or directory.")
    args = parser.parse_args(argv)
    evidence_path = args.evidence or args.path
    if not evidence_path:
        parser.error("an evidence artifact path or directory is required")

    artifacts, load_findings, artifact_count = _load_artifacts(Path(evidence_path))
    summary = validate_artifacts(artifacts, artifact_count=artifact_count, load_findings=load_findings)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
