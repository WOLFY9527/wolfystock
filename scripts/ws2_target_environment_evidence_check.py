#!/usr/bin/env python3
"""Validate sanitized WS2 target-environment evidence offline.

This checker reads one operator-supplied JSON artifact and emits a bounded
validation summary. It does not call staging, import task runtime modules,
connect to storage, inspect environment values, or approve public launch.
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


SCHEMA_VERSION = "wolfystock_ws2_target_environment_evidence_validation_v1"
ARTIFACT_VERSION = "wolfystock_ws2_target_environment_evidence_v1"
VALIDATION_PROFILE = "PROFILE_DURABLE_PROTECTED"
ACCEPTANCE_EVIDENCE_PROFILE = "PROFILE_WS2_ACCEPTANCE_EVIDENCE_SCOPED"
REDACTION_VERSION = "ws2_target_environment_evidence_redaction_v1"

ALLOWED_EVIDENCE_CLASSES = {
    "synthetic-local-dry-run",
    "ci-synthetic",
    "target-environment",
    "accepted-staging",
}
ALLOWED_REVIEW_STATUSES = {
    "not-reviewed",
    "needs-review",
    "rejected",
    "accepted-staging",
}
ALLOWED_SSE_BROADCAST_SCOPES = {
    "process-local",
    "external-broadcast-required",
    "needs-review",
}
ALLOWED_SINGLE_INSTANCE_EXCEPTION_POSTURES = {
    "not-used",
    "needs-review",
    "accepted-single-instance-exception",
    "rejected",
}
ALLOWED_MANUAL_REVIEW_STATUSES = {
    "needs-review",
    "accepted-staging",
    "rejected",
}
REQUIRED_FIELDS = (
    "artifactVersion",
    "validationProfile",
    "evidenceClass",
    "targetEnvironmentLabel",
    "deploymentTopologyLabel",
    "runId",
    "operator",
    "capturedAt",
    "submittedAt",
    "completedAt",
    "reviewerAcceptanceStatus",
    "reviewerLabel",
    "releaseApproved",
    "publicLaunchReady",
    "evidenceRedactionVersion",
    "evidenceBoundary",
    "topology",
    "checks",
    "summaries",
    "manualReview",
)
BOUNDARY_FIELDS = (
    "syntheticLocalDryRunEvidence",
    "ciSyntheticEvidence",
    "targetEnvironmentEvidence",
    "acceptedStagingEvidence",
    "publicLaunchApproval",
)
TOPOLOGY_FIELDS = (
    "apiAInstanceLabel",
    "apiBInstanceLabel",
    "workerLabel",
    "storageLabel",
    "sseBroadcastScope",
    "durablePollingBaseline",
    "externalSseReplayImplemented",
    "productionQueueBrokerCutover",
)
REQUIRED_CHECK_FIELDS = (
    "apiASubmitTransportExercised",
    "syntheticWorkerLeaseFlowVerified",
    "workerLeaseAcquired",
    "progressPersisted",
    "apiBDurableStatusReadback",
    "apiBPollingReplayVerified",
    "apiBDurablePollingReadback",
    "ownerHiddenStatusVerified",
    "ownerHiddenPollingVerified",
    "retryFailureSafetyVerified",
    "leaseExpiryRecoveryVerified",
    "staleWorkerWriteRejected",
    "retryCapVerified",
    "terminalFailurePollable",
    "ownerIsolationVerified",
    "sanitizedFailureOutputVerified",
    "sseLimitationRecorded",
    "crossInstanceSseNotClaimed",
    "durablePollingBaselineRecorded",
)
SUMMARY_FIELDS = (
    "apiASubmitTransport",
    "workerLease",
    "progressPersistence",
    "apiBDurableStatusReadback",
    "apiBPollingReplay",
    "apiBDurablePolling",
    "ownerHiddenStatus",
    "ownerHiddenPolling",
    "retryFailureSafety",
    "leaseExpiryRecovery",
    "staleWorkerWriteRejection",
    "ownerIsolation",
    "sanitizedFailureOutput",
    "sseLimitation",
    "reviewNotes",
)
MANUAL_REVIEW_FIELDS = (
    "manualReviewRequired",
    "manualReviewStatus",
    "singleInstanceExceptionPosture",
    "rollbackOrDegradedNote",
)
ACCEPTANCE_DIMENSIONS = (
    (
        "api_a_submit",
        "API A submit",
        ("apiASubmitTransportExercised",),
    ),
    (
        "worker_lease_synthetic_worker",
        "Worker lease or synthetic worker behavior",
        ("syntheticWorkerLeaseFlowVerified", "workerLeaseAcquired", "progressPersisted"),
    ),
    (
        "api_b_durable_read",
        "API B durable read",
        ("apiBDurableStatusReadback",),
    ),
    (
        "polling_replay",
        "Polling replay",
        ("apiBPollingReplayVerified", "apiBDurablePollingReadback", "durablePollingBaselineRecorded"),
    ),
    (
        "owner_isolation",
        "Owner isolation",
        ("ownerHiddenStatusVerified", "ownerHiddenPollingVerified", "ownerIsolationVerified"),
    ),
    (
        "retry_failure_safety",
        "Retry and failure safety",
        (
            "retryFailureSafetyVerified",
            "leaseExpiryRecoveryVerified",
            "staleWorkerWriteRejected",
            "retryCapVerified",
            "terminalFailurePollable",
            "sanitizedFailureOutputVerified",
        ),
    ),
    (
        "sse_limitation_handling",
        "Explicit SSE limitation handling",
        ("sseLimitationRecorded", "crossInstanceSseNotClaimed", "durablePollingBaselineRecorded"),
    ),
)

SAFE_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,159}$")
URL_WITH_CREDENTIALS_PATTERN = re.compile(r"https?://[^/\s:@]+:[^@\s]+@[^/\s]+", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://[^\s\"']+", re.IGNORECASE)
PRIVATE_HOSTNAME_PATTERN = re.compile(
    r"\b(?:localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|[A-Za-z0-9.-]*(?:\.internal|\.local|\.lan|\.corp|\.private))\b",
    re.IGNORECASE,
)
RAW_DEBUG_OR_BODY_PATTERN = re.compile(
    r"\b(?:raw[_\s-]?(?:request|response|payload|body|log|logs)|request[_\s-]?body|"
    r"response[_\s-]?body|task[_\s-]?payload|debug[_\s-]?(?:payload|trace)|stack trace|stacktrace|"
    r"Traceback \(most recent call last\):)\b",
    re.IGNORECASE,
)
PROVIDER_PAYLOAD_PATTERN = re.compile(r"\bprovider[_\s-]?payload\b", re.IGNORECASE)
SECRET_OR_COOKIE_PATTERN = re.compile(
    r"\b(?:api[_\s-]?key|apikey|authorization|bearer|cookie|credential|password|passwd|"
    r"private key|secret|session|set-cookie|token|totp|webhook)\b",
    re.IGNORECASE,
)
LAUNCH_APPROVAL_TEXT_PATTERNS = (
    re.compile(r"\bgo\s+for\s+public\s+launch\b", re.IGNORECASE),
    re.compile(r"\bpublic\s+launch\s+go\b", re.IGNORECASE),
    re.compile(r"\bapproved\s+for\s+launch\b", re.IGNORECASE),
    re.compile(r"\blaunch[-_\s]?approved\b", re.IGNORECASE),
    re.compile(r"\brelease[-_\s]?approved\b", re.IGNORECASE),
    re.compile(r"\bproduction[-_\s]?ready\b", re.IGNORECASE),
)
CROSS_INSTANCE_SSE_PATTERNS = (
    re.compile(r"\bcross[-_\s]?instance\s+sse\b.{0,80}\b(?:safe|accepted|ready)\b", re.IGNORECASE),
    re.compile(r"\bsse\b.{0,80}\bworks\s+across\s+instances\b", re.IGNORECASE),
    re.compile(r"\bmulti[-_\s]?instance\s+sse\b.{0,80}\b(?:safe|accepted|ready)\b", re.IGNORECASE),
)
SENSITIVE_KEY_MARKERS = (
    "api_key",
    "apikey",
    "auth_header",
    "authheader",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "password",
    "passwd",
    "private_key",
    "secret",
    "session",
    "set_cookie",
    "setcookie",
    "token",
)
RAW_IDENTITY_KEY_MARKERS = (
    "actor_id",
    "client_id",
    "principal_id",
    "session_id",
    "task_id",
    "user_id",
    "userid",
)
RAW_DEBUG_KEY_MARKERS = (
    "debug_payload",
    "debugpayload",
    "debug_trace",
    "debugtrace",
    "raw_body",
    "raw_log",
    "raw_logs",
    "raw_payload",
    "raw_request",
    "raw_response",
    "request_body",
    "requestbody",
    "response_body",
    "responsebody",
    "stack_trace",
    "stacktrace",
    "task_payload",
    "taskpayload",
    "traceback",
)
PROVIDER_PAYLOAD_KEY_MARKERS = (
    "provider_payload",
    "providerpayload",
)
QUEUE_BROKER_KEY_MARKERS = (
    "broker_credential",
    "broker_password",
    "broker_secret",
    "broker_url",
    "brokerurl",
    "queue_credential",
    "queue_password",
    "queue_secret",
    "queue_url",
    "queueurl",
)
LAUNCH_APPROVAL_KEYS = {
    "go",
    "golive",
    "goliveapproved",
    "launchapproval",
    "launchapproved",
    "launchgo",
    "publiclaunchapproval",
    "publiclaunchapproved",
    "releaseapproved",
    "publiclaunchready",
}
RUNTIME_CHANGE_KEYS = {
    "runtimebehaviorchanged",
    "runtimecutover",
    "runtimecutoverapproved",
}


def _is_non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_safe_label(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if any(marker in text for marker in ("://", "/", "?", "#", " ")):
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
    compacted_key = compact_key(key)
    findings: list[dict[str, str]] = []
    if any(marker in normalized_key for marker in RAW_DEBUG_KEY_MARKERS):
        findings.append(_finding(field, "raw_debug_or_body_marker_forbidden"))
    if any(marker in compacted_key or marker in normalized_key for marker in RAW_IDENTITY_KEY_MARKERS):
        findings.append(_finding(field, "raw_identity_marker_forbidden"))
    if any(marker in compacted_key or marker in normalized_key for marker in PROVIDER_PAYLOAD_KEY_MARKERS):
        findings.append(_finding(field, "provider_payload_marker_forbidden"))
    if any(marker in compacted_key or marker in normalized_key for marker in QUEUE_BROKER_KEY_MARKERS):
        findings.append(_finding(field, "queue_broker_credential_marker_forbidden"))
    if any(marker in normalized_key for marker in SENSITIVE_KEY_MARKERS):
        findings.append(_finding(field, "secret_or_cookie_marker_forbidden"))
    return findings


def _scan_value_entry(field: str, key: Any, value: Any) -> list[dict[str, str]]:
    if compact_key(key) in LAUNCH_APPROVAL_KEYS and value is True:
        return [_finding(field, "launch_approval_claim_forbidden")]
    if compact_key(key) in RUNTIME_CHANGE_KEYS and value is True:
        return [_finding(field, "runtime_behavior_change_claim_forbidden")]
    return []


def _scan_value_string(field: str, value: Any) -> list[dict[str, str]]:
    text = value.strip()
    if not text:
        return []
    findings: list[dict[str, str]] = []
    if URL_WITH_CREDENTIALS_PATTERN.search(text):
        findings.append(_finding(field, "credential_url_forbidden"))
    if URL_PATTERN.search(text):
        findings.append(_finding(field, "raw_url_forbidden"))
    if PRIVATE_HOSTNAME_PATTERN.search(text):
        findings.append(_finding(field, "private_hostname_forbidden"))
    if RAW_DEBUG_OR_BODY_PATTERN.search(text):
        findings.append(_finding(field, "raw_debug_or_body_marker_forbidden"))
    if PROVIDER_PAYLOAD_PATTERN.search(text):
        findings.append(_finding(field, "provider_payload_marker_forbidden"))
    if SECRET_OR_COOKIE_PATTERN.search(text):
        findings.append(_finding(field, "secret_or_cookie_marker_forbidden"))
    if any(pattern.search(text) for pattern in LAUNCH_APPROVAL_TEXT_PATTERNS):
        findings.append(_finding(field, "launch_approval_claim_forbidden"))
    if any(pattern.search(text) for pattern in CROSS_INSTANCE_SSE_PATTERNS):
        findings.append(_finding(field, "cross_instance_sse_acceptance_forbidden"))
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


def _validate_required_object(
    artifact: dict[str, Any],
    field: str,
    required_keys: tuple[str, ...],
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    findings: list[dict[str, str]] = []
    value = artifact.get(field)
    if not isinstance(value, dict):
        return [_finding(field, "invalid_required_object")], {}
    for key in required_keys:
        if key not in value:
            findings.append(_finding(f"{field}.{key}", "missing_required_field"))
    return findings, value


def _summaries_have_required_text(summaries: dict[str, Any]) -> bool:
    return all(_is_non_empty_text(summaries.get(field)) for field in SUMMARY_FIELDS)


def _manual_review_complete(manual_review: dict[str, Any]) -> bool:
    return (
        manual_review.get("manualReviewRequired") is True
        and manual_review.get("manualReviewStatus") == "accepted-staging"
        and manual_review.get("singleInstanceExceptionPosture")
        in {"not-used", "accepted-single-instance-exception"}
        and _is_non_empty_text(manual_review.get("rollbackOrDegradedNote"))
    )


def _required_check_values_true(checks: dict[str, Any]) -> bool:
    return all(checks.get(field) is True for field in REQUIRED_CHECK_FIELDS)


def _accepted_staging_evidence_complete(
    *,
    evidence_class: str,
    review_status: str,
    boundary: dict[str, Any],
    checks: dict[str, Any],
    topology: dict[str, Any],
    summaries: dict[str, Any],
    manual_review: dict[str, Any],
) -> bool:
    return (
        evidence_class == "accepted-staging"
        and review_status == "accepted-staging"
        and boundary.get("targetEnvironmentEvidence") is True
        and boundary.get("acceptedStagingEvidence") is True
        and boundary.get("publicLaunchApproval") is False
        and _required_check_values_true(checks)
        and topology.get("sseBroadcastScope") == "process-local"
        and topology.get("durablePollingBaseline") is True
        and topology.get("externalSseReplayImplemented") is False
        and topology.get("productionQueueBrokerCutover") is False
        and _summaries_have_required_text(summaries)
        and _manual_review_complete(manual_review)
    )


def _artifact_status(review_status: str, accepted_complete: bool) -> str:
    if accepted_complete:
        return "accepted-staging-review-required"
    if review_status == "rejected":
        return "rejected-no-go"
    return "needs-review"


def _acceptance_dimension_matrix(
    *,
    checks: dict[str, Any],
    boundary: dict[str, Any],
    topology: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    synthetic_evidence = (
        boundary.get("syntheticLocalDryRunEvidence") is True
        or boundary.get("ciSyntheticEvidence") is True
    )
    matrix: dict[str, dict[str, Any]] = {}
    for dimension_id, label, required_checks in ACCEPTANCE_DIMENSIONS:
        passed = all(checks.get(field) is True for field in required_checks)
        entry: dict[str, Any] = {
            "label": label,
            "requiredChecks": list(required_checks),
            "passed": passed,
            "targetEnvironmentEvidence": boundary.get("targetEnvironmentEvidence") is True,
            "acceptedStagingEvidence": boundary.get("acceptedStagingEvidence") is True,
            "syntheticEvidence": synthetic_evidence,
            "publicLaunchReady": False,
        }
        if dimension_id == "sse_limitation_handling":
            entry.update(
                {
                    "sseBroadcastScope": str(topology.get("sseBroadcastScope") or "<missing>"),
                    "durablePollingBaseline": topology.get("durablePollingBaseline") is True,
                    "externalSseReplayImplemented": topology.get("externalSseReplayImplemented") is True,
                    "productionQueueBrokerCutover": topology.get("productionQueueBrokerCutover") is True,
                }
            )
        matrix[dimension_id] = entry
    return matrix


def _validate_artifact(
    artifact: Any,
) -> tuple[list[dict[str, str]], dict[str, Any], dict[str, bool], dict[str, dict[str, Any]], str]:
    findings: list[dict[str, str]] = []
    if not isinstance(artifact, dict):
        return [_finding("$", "artifact_must_be_json_object")], {}, {}, {}, "invalid"

    for field in REQUIRED_FIELDS:
        if field not in artifact:
            findings.append(_finding(field, "missing_required_field"))

    artifact_version = artifact.get("artifactVersion")
    validation_profile = artifact.get("validationProfile")
    evidence_class = str(artifact.get("evidenceClass") or "").strip()
    target_environment_label = artifact.get("targetEnvironmentLabel")
    deployment_topology_label = artifact.get("deploymentTopologyLabel")
    run_id = artifact.get("runId")
    operator = artifact.get("operator")
    captured_at = artifact.get("capturedAt")
    submitted_at = artifact.get("submittedAt")
    completed_at = artifact.get("completedAt")
    review_status = str(artifact.get("reviewerAcceptanceStatus") or "").strip()
    reviewer_label = artifact.get("reviewerLabel")
    release_approved = artifact.get("releaseApproved")
    public_launch_ready = artifact.get("publicLaunchReady")
    redaction_version = artifact.get("evidenceRedactionVersion")

    if artifact_version != ARTIFACT_VERSION:
        findings.append(_finding("artifactVersion", "invalid_artifact_version"))
    if validation_profile != VALIDATION_PROFILE:
        findings.append(_finding("validationProfile", "invalid_validation_profile"))
    if evidence_class not in ALLOWED_EVIDENCE_CLASSES:
        findings.append(_finding("evidenceClass", "invalid_evidence_class"))
    if not _is_safe_label(target_environment_label):
        findings.append(_finding("targetEnvironmentLabel", "invalid_target_environment_label"))
    if not _is_safe_label(deployment_topology_label):
        findings.append(_finding("deploymentTopologyLabel", "invalid_deployment_topology_label"))
    if not _is_safe_label(run_id):
        findings.append(_finding("runId", "invalid_run_id"))
    if not _is_safe_label(operator):
        findings.append(_finding("operator", "invalid_operator"))
    for field, value in (
        ("capturedAt", captured_at),
        ("submittedAt", submitted_at),
        ("completedAt", completed_at),
    ):
        if not _is_iso_timestamp(value):
            findings.append(_finding(field, "invalid_timestamp"))
    if review_status not in ALLOWED_REVIEW_STATUSES:
        findings.append(_finding("reviewerAcceptanceStatus", "invalid_reviewer_acceptance_status"))
    if not _is_safe_label(reviewer_label):
        findings.append(_finding("reviewerLabel", "invalid_reviewer_label"))
    if release_approved is not False:
        findings.append(_finding("releaseApproved", "launch_approval_claim_forbidden"))
    if public_launch_ready is not False:
        findings.append(_finding("publicLaunchReady", "launch_approval_claim_forbidden"))
    if redaction_version != REDACTION_VERSION:
        findings.append(_finding("evidenceRedactionVersion", "invalid_redaction_version"))

    boundary_findings, boundary = _validate_required_object(artifact, "evidenceBoundary", BOUNDARY_FIELDS)
    topology_findings, topology = _validate_required_object(artifact, "topology", TOPOLOGY_FIELDS)
    check_findings, checks = _validate_required_object(artifact, "checks", REQUIRED_CHECK_FIELDS)
    summary_findings, summaries = _validate_required_object(artifact, "summaries", SUMMARY_FIELDS)
    manual_review_findings, manual_review = _validate_required_object(
        artifact, "manualReview", MANUAL_REVIEW_FIELDS
    )
    findings.extend(boundary_findings)
    findings.extend(topology_findings)
    findings.extend(check_findings)
    findings.extend(summary_findings)
    findings.extend(manual_review_findings)

    for field in BOUNDARY_FIELDS:
        if field in boundary and not isinstance(boundary.get(field), bool):
            findings.append(_finding(f"evidenceBoundary.{field}", "invalid_boolean"))
    for field in REQUIRED_CHECK_FIELDS:
        if field in checks and not isinstance(checks.get(field), bool):
            findings.append(_finding(f"checks.{field}", "invalid_boolean"))
    if "manualReviewRequired" in manual_review and not isinstance(
        manual_review.get("manualReviewRequired"), bool
    ):
        findings.append(_finding("manualReview.manualReviewRequired", "invalid_boolean"))
    if (
        "manualReviewStatus" in manual_review
        and manual_review.get("manualReviewStatus") not in ALLOWED_MANUAL_REVIEW_STATUSES
    ):
        findings.append(_finding("manualReview.manualReviewStatus", "invalid_manual_review_status"))
    if (
        "singleInstanceExceptionPosture" in manual_review
        and manual_review.get("singleInstanceExceptionPosture")
        not in ALLOWED_SINGLE_INSTANCE_EXCEPTION_POSTURES
    ):
        findings.append(
            _finding(
                "manualReview.singleInstanceExceptionPosture",
                "invalid_single_instance_exception_posture",
            )
        )
    if "rollbackOrDegradedNote" in manual_review and not _is_non_empty_text(
        manual_review.get("rollbackOrDegradedNote")
    ):
        findings.append(_finding("manualReview.rollbackOrDegradedNote", "missing_rollback_or_degraded_note"))

    for field in ("apiAInstanceLabel", "apiBInstanceLabel", "workerLabel", "storageLabel"):
        if field in topology and not _is_safe_label(topology.get(field)):
            findings.append(_finding(f"topology.{field}", "invalid_topology_label"))
    sse_scope = topology.get("sseBroadcastScope")
    if "sseBroadcastScope" in topology and sse_scope not in ALLOWED_SSE_BROADCAST_SCOPES:
        findings.append(_finding("topology.sseBroadcastScope", "invalid_sse_broadcast_scope"))
    if topology.get("durablePollingBaseline") is not True:
        findings.append(_finding("topology.durablePollingBaseline", "durable_polling_baseline_required"))
    if topology.get("externalSseReplayImplemented") is True:
        findings.append(_finding("topology.externalSseReplayImplemented", "external_sse_replay_cutover_forbidden"))
    if topology.get("productionQueueBrokerCutover") is True:
        findings.append(_finding("topology.productionQueueBrokerCutover", "queue_broker_cutover_forbidden"))

    if boundary.get("publicLaunchApproval") is not False:
        findings.append(_finding("evidenceBoundary.publicLaunchApproval", "launch_approval_claim_forbidden"))

    if evidence_class == "synthetic-local-dry-run" and boundary.get("syntheticLocalDryRunEvidence") is not True:
        findings.append(_finding("evidenceBoundary.syntheticLocalDryRunEvidence", "evidence_class_boundary_mismatch"))
    if evidence_class == "ci-synthetic" and boundary.get("ciSyntheticEvidence") is not True:
        findings.append(_finding("evidenceBoundary.ciSyntheticEvidence", "evidence_class_boundary_mismatch"))
    if evidence_class in {"target-environment", "accepted-staging"}:
        if boundary.get("syntheticLocalDryRunEvidence") is True or boundary.get("ciSyntheticEvidence") is True:
            findings.append(_finding("evidenceBoundary", "target_evidence_cannot_be_synthetic"))
    if evidence_class == "accepted-staging":
        if review_status != "accepted-staging":
            findings.append(_finding("reviewerAcceptanceStatus", "accepted_staging_requires_reviewer_acceptance"))
        if boundary.get("targetEnvironmentEvidence") is not True:
            findings.append(
                _finding("evidenceBoundary.targetEnvironmentEvidence", "accepted_staging_requires_target_evidence")
            )
        if boundary.get("acceptedStagingEvidence") is not True:
            findings.append(
                _finding(
                    "evidenceBoundary.acceptedStagingEvidence",
                    "accepted_staging_requires_accepted_evidence",
                )
            )
        if not _required_check_values_true(checks):
            findings.append(_finding("checks", "accepted_staging_requires_required_checks_true"))
        if topology.get("sseBroadcastScope") != "process-local":
            findings.append(
                _finding(
                    "topology.sseBroadcastScope",
                    "accepted_staging_requires_process_local_sse_limitation",
                )
            )
        if not _summaries_have_required_text(summaries):
            findings.append(_finding("summaries", "accepted_staging_requires_required_summaries"))
        if not _manual_review_complete(manual_review):
            findings.append(
                _finding("manualReview", "accepted_staging_requires_manual_review_and_rollback")
            )

    if checks.get("sseLimitationRecorded") is not True or checks.get("durablePollingBaselineRecorded") is not True:
        findings.append(_finding("checks", "sse_limitation_and_polling_baseline_required"))

    findings.extend(_scan_value(artifact))

    deduped_findings = sorted(
        {json.dumps(item, sort_keys=True): item for item in findings}.values(),
        key=lambda item: (item["field"], item["reasonCode"]),
    )

    accepted_complete = _accepted_staging_evidence_complete(
        evidence_class=evidence_class,
        review_status=review_status,
        boundary=boundary,
        checks=checks,
        topology=topology,
        summaries=summaries,
        manual_review=manual_review,
    )
    checks_summary = {
        "requiredEvidenceFieldsPresent": not any(
            item["reasonCode"] == "missing_required_field" for item in deduped_findings
        ),
        "acceptedStagingEvidenceComplete": accepted_complete,
        "sseLimitationAndPollingBaselineRecorded": (
            checks.get("sseLimitationRecorded") is True
            and checks.get("durablePollingBaselineRecorded") is True
            and topology.get("durablePollingBaseline") is True
        ),
        "manualReviewAndRollbackRecorded": _manual_review_complete(manual_review),
        "targetEnvironmentIdentifierSanitized": _is_safe_label(target_environment_label),
        "deploymentTopologyLabelSanitized": _is_safe_label(deployment_topology_label),
        "timestampsAndRunIdBounded": _is_safe_label(run_id)
        and _is_iso_timestamp(captured_at)
        and _is_iso_timestamp(submitted_at)
        and _is_iso_timestamp(completed_at),
        "noLaunchApprovalClaim": not any(
            item["reasonCode"] == "launch_approval_claim_forbidden" for item in deduped_findings
        ),
        "noRuntimeCutoverClaim": not any(
            item["reasonCode"]
            in {
                "external_sse_replay_cutover_forbidden",
                "queue_broker_cutover_forbidden",
                "runtime_behavior_change_claim_forbidden",
            }
            for item in deduped_findings
        ),
    }
    acceptance_matrix = _acceptance_dimension_matrix(
        checks=checks,
        boundary=boundary,
        topology=topology,
    )

    sanitized_artifact = {
        "artifactVersion": str(artifact_version or "<missing>"),
        "validationProfile": str(validation_profile or "<missing>"),
        "evidenceClass": str(evidence_class or "<missing>"),
        "targetEnvironmentLabel": (
            str(target_environment_label) if _is_safe_label(target_environment_label) else "<invalid>"
        ),
        "deploymentTopologyLabel": (
            str(deployment_topology_label) if _is_safe_label(deployment_topology_label) else "<invalid>"
        ),
        "runId": str(run_id) if _is_safe_label(run_id) else "<invalid>",
        "operator": str(operator) if _is_safe_label(operator) else "<invalid>",
        "capturedAt": str(captured_at) if _is_iso_timestamp(captured_at) else "<invalid>",
        "submittedAt": str(submitted_at) if _is_iso_timestamp(submitted_at) else "<invalid>",
        "completedAt": str(completed_at) if _is_iso_timestamp(completed_at) else "<invalid>",
        "reviewerAcceptanceStatus": str(review_status or "<missing>"),
        "reviewerLabel": str(reviewer_label) if _is_safe_label(reviewer_label) else "<invalid>",
        "releaseApproved": release_approved is True,
        "publicLaunchReady": public_launch_ready is True,
        "evidenceBoundary": {field: boundary.get(field) is True for field in BOUNDARY_FIELDS},
        "topology": {
            "apiAInstanceLabel": topology.get("apiAInstanceLabel")
            if _is_safe_label(topology.get("apiAInstanceLabel"))
            else "<invalid>",
            "apiBInstanceLabel": topology.get("apiBInstanceLabel")
            if _is_safe_label(topology.get("apiBInstanceLabel"))
            else "<invalid>",
            "workerLabel": (
                topology.get("workerLabel") if _is_safe_label(topology.get("workerLabel")) else "<invalid>"
            ),
            "storageLabel": (
                topology.get("storageLabel") if _is_safe_label(topology.get("storageLabel")) else "<invalid>"
            ),
            "sseBroadcastScope": str(topology.get("sseBroadcastScope") or "<missing>"),
            "durablePollingBaseline": topology.get("durablePollingBaseline") is True,
            "externalSseReplayImplemented": topology.get("externalSseReplayImplemented") is True,
            "productionQueueBrokerCutover": topology.get("productionQueueBrokerCutover") is True,
        },
        "checks": {field: checks.get(field) is True for field in REQUIRED_CHECK_FIELDS},
        "summaryFieldsPresent": {
            field: _is_non_empty_text(summaries.get(field)) for field in SUMMARY_FIELDS
        },
        "manualReview": {
            "manualReviewRequired": manual_review.get("manualReviewRequired") is True,
            "manualReviewStatus": str(manual_review.get("manualReviewStatus") or "<missing>"),
            "singleInstanceExceptionPosture": str(
                manual_review.get("singleInstanceExceptionPosture") or "<missing>"
            ),
            "rollbackOrDegradedNotePresent": _is_non_empty_text(
                manual_review.get("rollbackOrDegradedNote")
            ),
        },
        "evidenceRedactionVersion": str(redaction_version or "<missing>"),
    }
    artifact_status = _artifact_status(review_status, accepted_complete)
    return deduped_findings, sanitized_artifact, checks_summary, acceptance_matrix, artifact_status


def validate_ws2_target_environment_evidence(artifact: Any) -> dict[str, Any]:
    findings, artifact_summary, checks_summary, acceptance_matrix, artifact_status = _validate_artifact(artifact)
    passed = not findings
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "pass" if passed else "fail",
        "artifactStatus": artifact_status,
        "validationProfile": VALIDATION_PROFILE,
        "acceptanceEvidenceProfile": ACCEPTANCE_EVIDENCE_PROFILE,
        "advisoryOnly": True,
        "manualReviewRequired": True,
        "releaseApproved": False,
        "launchAcceptanceIntegrated": False,
        "runtimeBehaviorChanged": False,
        "networkCallsExecutedByValidator": False,
        "publicLaunchReady": False,
        "checks": checks_summary,
        "acceptanceDimensions": acceptance_matrix,
        "artifact": artifact_summary,
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
    parser = argparse.ArgumentParser(description="Validate sanitized WS2 target-environment evidence JSON offline.")
    parser.add_argument("artifact", help="Path to sanitized WS2 target-environment evidence JSON")
    args = parser.parse_args(argv)

    artifact = _load_json(Path(args.artifact))
    result = validate_ws2_target_environment_evidence(artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
