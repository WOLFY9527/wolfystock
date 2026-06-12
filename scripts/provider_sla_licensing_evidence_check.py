#!/usr/bin/env python3
"""Validate sanitized provider SLA/licensing evidence artifacts offline.

This helper reads one operator-supplied JSON file and emits a bounded summary.
It does not import provider adapters, read environment files, open sockets,
inspect credentials, mutate provider/cache state, or approve launch.
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
    from evidence_safety import compact_key as _compact_key
    from evidence_safety import finding as _finding
    from evidence_safety import normalize_key as _normalize_key
    from evidence_safety import scan_json_tree
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from scripts.evidence_safety import compact_key as _compact_key
    from scripts.evidence_safety import finding as _finding
    from scripts.evidence_safety import normalize_key as _normalize_key
    from scripts.evidence_safety import scan_json_tree


SCHEMA_VERSION = "wolfystock_provider_sla_licensing_evidence_summary_v1"
REQUIRED_FIELDS = (
    "artifactVersion",
    "environment",
    "operator",
    "observedAt",
    "providerFamily",
    "entitlementLicensingStatus",
    "credentialPresence",
    "allowedUsageScope",
    "stagingProbeResult",
    "degradedFallbackPolicy",
    "runtimeEnforcement",
    "publicReadinessClaim",
    "evidenceRedactionVersion",
)
ALLOWED_ENVIRONMENTS = {"staging", "production-like", "sandbox", "production-like-staging"}
ALLOWED_LICENSING_STATUS = {"accepted", "needs-review", "rejected", "not-required", "unknown"}
ALLOWED_CREDENTIAL_PRESENCE = {"configured", "missing", "redacted", "not-required"}
ALLOWED_STAGING_PROBE_RESULT = {"accepted", "needs-review", "rejected", "not-run", "not-required"}
ALLOWED_PUBLIC_READINESS_CLAIM = {"not-claimed", "evidence-ready-for-review", "public-ready"}
ALLOWED_RUNTIME_ENFORCEMENT_CLAIM = {"not-claimed", "accepted-artifact"}
SAFE_LABEL_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")
SAFE_ROUTE_LABEL_RE = re.compile(r"^/?[a-z0-9][a-z0-9_/.-]{0,119}$")

SAFE_KEY_COMPACTS = {
    _compact_key(key)
    for key in (
        *REQUIRED_FIELDS,
        "runtimeEnforcement",
        "publicReadinessEvidence",
        "stagingProbeAccepted",
        "licensingEvidenceAccepted",
        "fallbackPolicyAccepted",
        "manualReviewRequired",
        "acceptedArtifact",
        "artifactRef",
        "boundedRoute",
        "outcome",
        "rollbackSwitchRecorded",
        "runtimeDefaultUnchanged",
        "liveEnforcement",
        "wouldBlockCall",
        "dryRunOnly",
        "advisoryBlockCandidate",
        "notes",
        "adminProbePilotEvidence",
        "adminProbeOnly",
        "defaultOffPosture",
        "rollbackAvailable",
        "selectedBoundary",
        "selectedBoundaryOnly",
        "apiRoute",
        "providerCategory",
        "routeFamily",
        "lastDecisionCategory",
        "scopeMatched",
        "publicRuntimeProviderBlocking",
        "memberRuntimeProviderBlocking",
        "providerRuntimeEnforcement",
        "providerOrderFallbackCacheBehaviorChanged",
        "sanitizedFieldsOnly",
        "acceptedOperatorEvidencePresent",
        "publicLaunchReady",
        "remainingPublicLaunchNoGoItems",
    )
}
ADMIN_PROBE_EVIDENCE_FIELD = "adminProbePilotEvidence"
ADMIN_PROBE_CONTRACT_VERSION = "provider_admin_probe_pilot_evidence_v1"
ADMIN_PROBE_PROVIDER_CATEGORY = "data_source_validation"
ADMIN_PROBE_ROUTE_FAMILY = "admin_provider_probe"
ADMIN_PROBE_REQUIRED_FIELDS = (
    "contractVersion",
    "adminProbeOnly",
    "defaultOffPosture",
    "rollbackAvailable",
    "selectedBoundary",
    "apiRoute",
    "providerCategory",
    "routeFamily",
    "publicRuntimeProviderBlocking",
    "memberRuntimeProviderBlocking",
    "providerRuntimeEnforcement",
    "providerOrderFallbackCacheBehaviorChanged",
    "sanitizedFieldsOnly",
    "acceptedOperatorEvidencePresent",
    "publicLaunchReady",
    "remainingPublicLaunchNoGoItems",
)
ADMIN_PROBE_REQUIRED_NO_GO_ITEMS = {
    "public_provider_circuit_enforcement_not_accepted",
}
CREDENTIAL_KEY_MARKERS = (
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credentialvalue",
    "credentialvalues",
    "csrf",
    "databaseurl",
    "dburl",
    "dsn",
    "password",
    "passwd",
    "privatekey",
    "secret",
    "sessionid",
    "setcookie",
    "token",
    "webhook",
)
RAW_PAYLOAD_KEY_MARKERS = (
    "debugpayload",
    "debugtrace",
    "providerpayload",
    "rawpayload",
    "rawproviderpayload",
    "rawrequest",
    "rawrequestbody",
    "rawresponse",
    "rawresponsebody",
    "requestbody",
    "responsebody",
)
EXCEPTION_KEY_MARKERS = (
    "trace",
    "traceid",
    "exception",
    "exceptiontext",
    "rawlog",
    "stacktrace",
    "traceback",
)
IDENTIFIER_KEY_MARKERS = (
    "accountid",
    "accountidentifier",
    "brokeraccount",
    "customerid",
    "email",
    "ipaddress",
    "phonenumber",
    "tenantid",
    "userid",
)
REQUEST_ID_KEY_MARKERS = (
    "correlationid",
    "requestid",
    "xrequestid",
)
CACHE_KEY_MARKERS = (
    "cachekey",
    "rawcachekey",
)

SECRET_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "credential_leakage_forbidden",
        re.compile(
            r"\b(?:api[_\s-]?key|apikey|token|secret|password|passwd|cookie|session|csrf|"
            r"authorization|set-cookie)\s*[:=]\s*[^\s,;&]+",
            re.IGNORECASE,
        ),
    ),
    (
        "credential_leakage_forbidden",
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    ),
    (
        "credential_leakage_forbidden",
        re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    ),
    (
        "credential_leakage_forbidden",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}"),
    ),
    (
        "credential_leakage_forbidden",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ),
    (
        "credential_leakage_forbidden",
        re.compile(r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb|redis)://[^:\s/@]+:[^@\s]+@[^\s]+", re.IGNORECASE),
    ),
)
UNSAFE_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "url_query_string_forbidden",
        re.compile(r"\bhttps?://[^\s?#]+[?][^\s]+", re.IGNORECASE),
    ),
    (
        "payload_content_forbidden",
        re.compile(
            r"\b(?:raw[_\s-]?(?:provider[_\s-]?)?(?:payload|response|request)|"
            r"provider[_\s-]?payload|request[_\s-]?body|response[_\s-]?body|debug[_\s-]?payload)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "exception_or_stack_trace_forbidden",
        re.compile(r"\b(?:Traceback|stack trace|exception text|exception:|debug trace)\b", re.IGNORECASE),
    ),
    (
        "account_or_user_identifier_forbidden",
        re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    ),
    (
        "account_or_user_identifier_forbidden",
        re.compile(r"\b(?:account|user|customer|tenant)[_\s-]?(?:id|identifier)\s*[:=]\s*[A-Za-z0-9_.-]+", re.IGNORECASE),
    ),
)
LAUNCH_APPROVAL_PATTERN = re.compile(
    r"\bGO\b|launch[-_\s]?approved|release[-_\s]?approved|production[-_\s]?ready|approved for launch",
    re.IGNORECASE,
)
PUBLIC_READY_PATTERN = re.compile(r"\bpublic[-_\s]?ready\b", re.IGNORECASE)


def _safe_finding(field: str, reason_code: str) -> dict[str, str]:
    return _finding(_safe_field(field), reason_code)


def _safe_field(field: str) -> str:
    compact = _compact_key(field)
    unsafe_markers = (
        *CREDENTIAL_KEY_MARKERS,
        *RAW_PAYLOAD_KEY_MARKERS,
        *EXCEPTION_KEY_MARKERS,
        *IDENTIFIER_KEY_MARKERS,
        "rawurl",
        *REQUEST_ID_KEY_MARKERS,
        *CACHE_KEY_MARKERS,
    )
    if any(marker in compact for marker in unsafe_markers):
        return "[redacted]"
    if compact.endswith("url"):
        return "[redacted]"
    return field


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_observed_at(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _safe_label(value: Any, *, route: bool = False) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    if LAUNCH_APPROVAL_PATTERN.search(text) or PUBLIC_READY_PATTERN.search(text):
        return False
    pattern = SAFE_ROUTE_LABEL_RE if route else SAFE_LABEL_RE
    return bool(pattern.fullmatch(text))


def _scan_key(field: str, key: Any) -> list[dict[str, str]]:
    compact = _compact_key(key)
    if compact in SAFE_KEY_COMPACTS:
        return []
    if any(marker in compact for marker in RAW_PAYLOAD_KEY_MARKERS):
        return [_safe_finding(field, "payload_content_forbidden")]
    if any(marker in compact for marker in EXCEPTION_KEY_MARKERS):
        return [_safe_finding(field, "exception_or_stack_trace_forbidden")]
    if any(marker in compact for marker in REQUEST_ID_KEY_MARKERS):
        return [_safe_finding(field, "request_id_forbidden")]
    if any(marker in compact for marker in CACHE_KEY_MARKERS):
        return [_safe_finding(field, "cache_key_forbidden")]
    if any(marker in compact for marker in IDENTIFIER_KEY_MARKERS):
        return [_safe_finding(field, "account_or_user_identifier_forbidden")]
    if any(marker in compact for marker in CREDENTIAL_KEY_MARKERS):
        return [_safe_finding(field, "credential_leakage_forbidden")]
    if "credential" in compact and compact not in SAFE_KEY_COMPACTS:
        return [_safe_finding(field, "credential_leakage_forbidden")]
    if compact == "rawurl" or compact.endswith("url"):
        return [_safe_finding(field, "url_query_string_forbidden")]
    return []


def _validate_bool_field(
    findings: list[dict[str, str]],
    evidence: dict[str, Any],
    field: str,
) -> bool | None:
    value = evidence.get(field)
    if not isinstance(value, bool):
        findings.append(_finding(f"{ADMIN_PROBE_EVIDENCE_FIELD}.{field}", "invalid_boolean_field"))
        return None
    return value


def _validate_admin_probe_no_go_items(
    findings: list[dict[str, str]],
    evidence: dict[str, Any],
) -> None:
    field = f"{ADMIN_PROBE_EVIDENCE_FIELD}.remainingPublicLaunchNoGoItems"
    value = evidence.get("remainingPublicLaunchNoGoItems")
    if not isinstance(value, list) or not value:
        findings.append(_finding(field, "admin_probe_evidence_must_list_remaining_no_go_items"))
        return
    safe_items = {str(item) for item in value if _safe_label(item)}
    if len(safe_items) != len(value):
        findings.append(_finding(field, "invalid_sanitized_label"))
    if not ADMIN_PROBE_REQUIRED_NO_GO_ITEMS.issubset(safe_items):
        findings.append(_finding(field, "admin_probe_evidence_must_list_remaining_no_go_items"))


def _validate_admin_probe_pilot_evidence(artifact: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if ADMIN_PROBE_EVIDENCE_FIELD not in artifact:
        return findings
    evidence = artifact.get(ADMIN_PROBE_EVIDENCE_FIELD)
    if not isinstance(evidence, dict):
        return [_finding(ADMIN_PROBE_EVIDENCE_FIELD, "invalid_admin_probe_pilot_evidence")]

    for field in ADMIN_PROBE_REQUIRED_FIELDS:
        if field not in evidence:
            findings.append(_finding(f"{ADMIN_PROBE_EVIDENCE_FIELD}.{field}", "missing_required_field"))

    if evidence.get("contractVersion") != ADMIN_PROBE_CONTRACT_VERSION:
        findings.append(_finding(f"{ADMIN_PROBE_EVIDENCE_FIELD}.contractVersion", "invalid_sanitized_label"))
    if not _safe_label(evidence.get("selectedBoundary"), route=True):
        findings.append(_finding(f"{ADMIN_PROBE_EVIDENCE_FIELD}.selectedBoundary", "invalid_sanitized_label"))
    if not _safe_label(evidence.get("apiRoute"), route=True):
        findings.append(_finding(f"{ADMIN_PROBE_EVIDENCE_FIELD}.apiRoute", "invalid_sanitized_label"))
    if evidence.get("providerCategory") != ADMIN_PROBE_PROVIDER_CATEGORY:
        findings.append(_finding(f"{ADMIN_PROBE_EVIDENCE_FIELD}.providerCategory", "admin_probe_evidence_scope_must_match_admin_probe"))
    if evidence.get("routeFamily") != ADMIN_PROBE_ROUTE_FAMILY:
        findings.append(_finding(f"{ADMIN_PROBE_EVIDENCE_FIELD}.routeFamily", "admin_probe_evidence_scope_must_match_admin_probe"))

    admin_probe_only = _validate_bool_field(findings, evidence, "adminProbeOnly")
    default_off_posture = _validate_bool_field(findings, evidence, "defaultOffPosture")
    rollback_available = _validate_bool_field(findings, evidence, "rollbackAvailable")
    public_runtime_blocking = _validate_bool_field(findings, evidence, "publicRuntimeProviderBlocking")
    member_runtime_blocking = _validate_bool_field(findings, evidence, "memberRuntimeProviderBlocking")
    provider_runtime_enforcement = _validate_bool_field(findings, evidence, "providerRuntimeEnforcement")
    order_fallback_cache_changed = _validate_bool_field(
        findings,
        evidence,
        "providerOrderFallbackCacheBehaviorChanged",
    )
    sanitized_fields_only = _validate_bool_field(findings, evidence, "sanitizedFieldsOnly")
    accepted_operator_evidence = _validate_bool_field(findings, evidence, "acceptedOperatorEvidencePresent")
    public_launch_ready = _validate_bool_field(findings, evidence, "publicLaunchReady")

    if admin_probe_only is not True:
        findings.append(_finding(f"{ADMIN_PROBE_EVIDENCE_FIELD}.adminProbeOnly", "admin_probe_evidence_must_be_admin_probe_only"))
    if default_off_posture is not True:
        findings.append(_finding(f"{ADMIN_PROBE_EVIDENCE_FIELD}.defaultOffPosture", "admin_probe_evidence_must_show_default_off_posture"))
    if rollback_available is not True:
        findings.append(_finding(f"{ADMIN_PROBE_EVIDENCE_FIELD}.rollbackAvailable", "admin_probe_evidence_must_show_rollback_available"))
    if public_runtime_blocking is True:
        findings.append(_finding(
            f"{ADMIN_PROBE_EVIDENCE_FIELD}.publicRuntimeProviderBlocking",
            "admin_probe_evidence_must_not_claim_public_runtime_blocking",
        ))
    if member_runtime_blocking is True:
        findings.append(_finding(
            f"{ADMIN_PROBE_EVIDENCE_FIELD}.memberRuntimeProviderBlocking",
            "admin_probe_evidence_must_not_claim_member_runtime_blocking",
        ))
    if provider_runtime_enforcement is True:
        findings.append(_finding(
            f"{ADMIN_PROBE_EVIDENCE_FIELD}.providerRuntimeEnforcement",
            "admin_probe_evidence_must_not_claim_provider_runtime_enforcement",
        ))
    if order_fallback_cache_changed is True:
        findings.append(_finding(
            f"{ADMIN_PROBE_EVIDENCE_FIELD}.providerOrderFallbackCacheBehaviorChanged",
            "admin_probe_evidence_must_not_change_provider_order_fallback_or_cache",
        ))
    if sanitized_fields_only is not True:
        findings.append(_finding(f"{ADMIN_PROBE_EVIDENCE_FIELD}.sanitizedFieldsOnly", "admin_probe_evidence_must_be_sanitized_only"))
    if accepted_operator_evidence is True:
        findings.append(_finding(
            f"{ADMIN_PROBE_EVIDENCE_FIELD}.acceptedOperatorEvidencePresent",
            "admin_probe_operator_evidence_not_accepted_by_validator",
        ))
    if public_launch_ready is True:
        findings.append(_finding(
            f"{ADMIN_PROBE_EVIDENCE_FIELD}.publicLaunchReady",
            "public_ready_claim_requires_accepted_staging_evidence",
        ))

    _validate_admin_probe_no_go_items(findings, evidence)
    return findings


def _scan_string(field: str, value: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for reason_code, pattern in SECRET_VALUE_PATTERNS + UNSAFE_VALUE_PATTERNS:
        if pattern.search(value):
            findings.append(_safe_finding(field, reason_code))
            break
    if LAUNCH_APPROVAL_PATTERN.search(value):
        findings.append(_safe_finding(field, "launch_approval_claim_forbidden"))
    if PUBLIC_READY_PATTERN.search(value):
        findings.append(_safe_finding(field, "public_ready_claim_requires_accepted_staging_evidence"))
    return findings


def _scan_unsafe_content(artifact: Any) -> list[dict[str, str]]:
    return scan_json_tree(
        artifact,
        scan_key=_scan_key,
        scan_string=_scan_string,
        recurse_on_key_findings=False,
    )


def _runtime_enforcement_claim(runtime: Any) -> str:
    if not isinstance(runtime, dict):
        return "<missing>"
    claim = runtime.get("claim")
    if isinstance(claim, str) and claim in ALLOWED_RUNTIME_ENFORCEMENT_CLAIM:
        return claim
    return "<invalid-or-missing>"


def _runtime_accepted_artifact_present(runtime: dict[str, Any]) -> bool:
    accepted = runtime.get("acceptedArtifact")
    if not isinstance(accepted, dict):
        return False
    return (
        accepted.get("outcome") == "accepted"
        and _safe_label(accepted.get("artifactRef"))
        and _safe_label(accepted.get("boundedRoute"), route=True)
        and accepted.get("rollbackSwitchRecorded") is True
        and accepted.get("runtimeDefaultUnchanged") is True
    )


def _validate_runtime_enforcement(artifact: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    findings: list[dict[str, str]] = []
    runtime = artifact.get("runtimeEnforcement")
    summary = {
        "claim": "<missing>",
        "liveEnforcement": False,
        "wouldBlockCall": False,
    }
    if not isinstance(runtime, dict):
        return [_finding("runtimeEnforcement", "invalid_runtime_enforcement")], summary

    claim = runtime.get("claim")
    summary["claim"] = _runtime_enforcement_claim(runtime)
    live_enforcement = runtime.get("liveEnforcement")
    would_block_call = runtime.get("wouldBlockCall")
    if not isinstance(live_enforcement, bool):
        findings.append(_finding("runtimeEnforcement.liveEnforcement", "invalid_boolean_field"))
    if not isinstance(would_block_call, bool):
        findings.append(_finding("runtimeEnforcement.wouldBlockCall", "invalid_boolean_field"))
    summary["liveEnforcement"] = bool(live_enforcement) if isinstance(live_enforcement, bool) else False
    summary["wouldBlockCall"] = bool(would_block_call) if isinstance(would_block_call, bool) else False

    if claim not in ALLOWED_RUNTIME_ENFORCEMENT_CLAIM:
        findings.append(_finding("runtimeEnforcement.claim", "invalid_runtime_enforcement_claim"))
        return findings, summary

    accepted_artifact_present = _runtime_accepted_artifact_present(runtime)
    if claim == "accepted-artifact" and not accepted_artifact_present:
        findings.append(
            _finding("runtimeEnforcement", "runtime_enforcement_claim_requires_accepted_artifact")
        )
    if claim != "accepted-artifact" and (live_enforcement is True or would_block_call is True):
        findings.append(
            _finding("runtimeEnforcement", "runtime_enforcement_claim_requires_accepted_artifact")
        )
    return findings, summary


def _public_ready_evidence_accepted(artifact: dict[str, Any]) -> bool:
    evidence = artifact.get("publicReadinessEvidence")
    if not isinstance(evidence, dict):
        return False
    return (
        artifact.get("stagingProbeResult") == "accepted"
        and artifact.get("entitlementLicensingStatus") == "accepted"
        and evidence.get("stagingProbeAccepted") is True
        and evidence.get("licensingEvidenceAccepted") is True
        and evidence.get("fallbackPolicyAccepted") is True
        and evidence.get("manualReviewRequired") is True
    )


def _validate_public_readiness(artifact: dict[str, Any]) -> list[dict[str, str]]:
    claim = artifact.get("publicReadinessClaim")
    public_ready_claimed = (
        claim is True
        or (isinstance(claim, str) and PUBLIC_READY_PATTERN.search(claim))
        or artifact.get("publicReady") is True
    )
    if public_ready_claimed and not _public_ready_evidence_accepted(artifact):
        return [
            _finding(
                "publicReadinessClaim",
                "public_ready_claim_requires_accepted_staging_evidence",
            )
        ]
    return []


def _validate_artifact(artifact: Any) -> tuple[list[dict[str, str]], dict[str, bool], dict[str, Any]]:
    findings: list[dict[str, str]] = []
    checks = {
        "requiredFieldsPresent": False,
        "requiredEvidenceCategoriesPresent": False,
        "schemaValuesValid": False,
        "credentialLeakageAbsent": False,
        "providerPayloadContentAbsent": False,
        "unsafeContentAbsent": False,
        "publicReadySupportedByEvidence": False,
        "runtimeEnforcementClaimValid": False,
    }
    runtime_summary = {
        "claim": "<missing>",
        "liveEnforcement": False,
        "wouldBlockCall": False,
    }

    if not isinstance(artifact, dict):
        findings.append(_finding("$", "artifact_must_be_json_object"))
        return findings, checks, runtime_summary

    for field in REQUIRED_FIELDS:
        if field not in artifact:
            findings.append(_finding(field, "missing_required_field"))

    label_fields = (
        "artifactVersion",
        "operator",
        "providerFamily",
        "allowedUsageScope",
        "degradedFallbackPolicy",
        "evidenceRedactionVersion",
    )
    for field in label_fields:
        if field in artifact and not _safe_label(artifact.get(field)):
            findings.append(_finding(field, "invalid_sanitized_label"))

    if artifact.get("environment") not in ALLOWED_ENVIRONMENTS:
        findings.append(_finding("environment", "invalid_environment"))
    if artifact.get("entitlementLicensingStatus") not in ALLOWED_LICENSING_STATUS:
        findings.append(_finding("entitlementLicensingStatus", "invalid_entitlement_licensing_status"))
    if artifact.get("credentialPresence") not in ALLOWED_CREDENTIAL_PRESENCE:
        findings.append(_finding("credentialPresence", "invalid_credential_presence"))
    if artifact.get("stagingProbeResult") not in ALLOWED_STAGING_PROBE_RESULT:
        findings.append(_finding("stagingProbeResult", "invalid_staging_probe_result"))
    if artifact.get("publicReadinessClaim") not in ALLOWED_PUBLIC_READINESS_CLAIM:
        findings.append(_finding("publicReadinessClaim", "invalid_public_readiness_claim"))
    if "observedAt" in artifact and not _valid_observed_at(artifact.get("observedAt")):
        findings.append(_finding("observedAt", "invalid_observed_at"))
    if "notes" in artifact and not _non_empty_string(artifact.get("notes")):
        findings.append(_finding("notes", "invalid_string_field"))

    runtime_findings, runtime_summary = _validate_runtime_enforcement(artifact)
    findings.extend(runtime_findings)
    findings.extend(_validate_public_readiness(artifact))
    findings.extend(_validate_admin_probe_pilot_evidence(artifact))
    findings.extend(_scan_unsafe_content(artifact))

    checks["requiredFieldsPresent"] = not any(
        finding["reasonCode"] == "missing_required_field" for finding in findings
    )
    checks["requiredEvidenceCategoriesPresent"] = checks["requiredFieldsPresent"] and not any(
        finding["field"]
        in {
            "providerFamily",
            "entitlementLicensingStatus",
            "credentialPresence",
            "allowedUsageScope",
            "stagingProbeResult",
            "degradedFallbackPolicy",
        }
        for finding in findings
    )
    checks["schemaValuesValid"] = not any(
        finding["reasonCode"].startswith("invalid_") for finding in findings
    )
    checks["credentialLeakageAbsent"] = not any(
        finding["reasonCode"] == "credential_leakage_forbidden" for finding in findings
    )
    checks["providerPayloadContentAbsent"] = not any(
        finding["reasonCode"] == "payload_content_forbidden" for finding in findings
    )
    unsafe_reason_codes = {
        "account_or_user_identifier_forbidden",
        "credential_leakage_forbidden",
        "exception_or_stack_trace_forbidden",
        "launch_approval_claim_forbidden",
        "payload_content_forbidden",
        "request_id_forbidden",
        "cache_key_forbidden",
        "url_query_string_forbidden",
    }
    checks["unsafeContentAbsent"] = not any(
        finding["reasonCode"] in unsafe_reason_codes for finding in findings
    )
    checks["publicReadySupportedByEvidence"] = not any(
        finding["reasonCode"] == "public_ready_claim_requires_accepted_staging_evidence"
        for finding in findings
    )
    checks["runtimeEnforcementClaimValid"] = not any(
        finding["reasonCode"] == "runtime_enforcement_claim_requires_accepted_artifact"
        or finding["reasonCode"] == "invalid_runtime_enforcement_claim"
        for finding in findings
    )
    return findings, checks, runtime_summary


def _summary_value(artifact: dict[str, Any], field: str, *, allowed: set[str] | None = None) -> str:
    value = artifact.get(field)
    if allowed is not None:
        return str(value) if value in allowed else "<invalid-or-missing>"
    if _safe_label(value):
        return str(value)
    return "<invalid-or-missing>"


def _sanitized_artifact_summary(artifact: Any) -> dict[str, str]:
    if not isinstance(artifact, dict):
        return {}
    runtime = artifact.get("runtimeEnforcement")
    return {
        "artifactVersion": _summary_value(artifact, "artifactVersion"),
        "environment": _summary_value(artifact, "environment", allowed=ALLOWED_ENVIRONMENTS),
        "providerFamily": _summary_value(artifact, "providerFamily"),
        "entitlementLicensingStatus": _summary_value(
            artifact,
            "entitlementLicensingStatus",
            allowed=ALLOWED_LICENSING_STATUS,
        ),
        "credentialPresence": _summary_value(
            artifact,
            "credentialPresence",
            allowed=ALLOWED_CREDENTIAL_PRESENCE,
        ),
        "allowedUsageScope": _summary_value(artifact, "allowedUsageScope"),
        "stagingProbeResult": _summary_value(
            artifact,
            "stagingProbeResult",
            allowed=ALLOWED_STAGING_PROBE_RESULT,
        ),
        "degradedFallbackPolicy": _summary_value(artifact, "degradedFallbackPolicy"),
        "runtimeEnforcementClaim": _runtime_enforcement_claim(runtime),
        "publicReadinessClaim": _summary_value(
            artifact,
            "publicReadinessClaim",
            allowed=ALLOWED_PUBLIC_READINESS_CLAIM,
        ),
        "evidenceRedactionVersion": _summary_value(artifact, "evidenceRedactionVersion"),
    }


def validate_provider_sla_licensing_evidence(artifact: Any) -> dict[str, Any]:
    findings, checks, runtime_summary = _validate_artifact(artifact)
    passed = not findings
    runtime_accepted = (
        isinstance(artifact, dict)
        and isinstance(artifact.get("runtimeEnforcement"), dict)
        and artifact["runtimeEnforcement"].get("claim") == "accepted-artifact"
        and _runtime_accepted_artifact_present(artifact["runtimeEnforcement"])
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "pass" if passed else "fail",
        "finalStatus": "EVIDENCE-READY" if passed else "EVIDENCE-BLOCKED",
        "advisoryOnly": True,
        "runtimeBehaviorChanged": False,
        "providerRuntimeBehaviorChanged": False,
        "providerOrderChanged": False,
        "providerFallbackBehaviorChanged": False,
        "marketCacheBehaviorChanged": False,
        "apiBehaviorChanged": False,
        "launchApproved": False,
        "releaseApproved": False,
        "networkCallsExecutedByValidator": False,
        "externalServicesCalledByValidator": False,
        "providerCredentialsReadByValidator": False,
        "realEnvReadByValidator": False,
        "rawArtifactBodiesIncluded": False,
        "secretValuesPrintedByValidator": False,
        "runtimeEnforcementAccepted": runtime_accepted,
        "runtime": runtime_summary,
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


def _artifact_path(args: argparse.Namespace) -> Path:
    path = args.artifact_option or args.artifact
    if not path:
        raise SystemExit("[FAIL] Missing sanitized provider SLA/licensing evidence JSON path")
    return Path(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a sanitized provider SLA/licensing evidence JSON artifact offline."
    )
    parser.add_argument("artifact", nargs="?", help="Path to sanitized provider SLA/licensing evidence JSON")
    parser.add_argument("--artifact", dest="artifact_option", help="Path to sanitized evidence JSON")
    args = parser.parse_args(argv)

    artifact = _load_json(_artifact_path(args))
    result = validate_provider_sla_licensing_evidence(artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
