#!/usr/bin/env python3
"""Validate sanitized private-beta UAT evidence offline.

The checker reads one operator-filled JSON artifact, emits a sanitized summary,
and never opens browsers, reads credentials, calls networks, changes runtime
state, sends notifications, or approves public launch.
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
    from evidence_safety import is_iso_timestamp as _is_iso_timestamp
    from evidence_safety import scan_json_tree
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from scripts.evidence_safety import finding as _finding
    from scripts.evidence_safety import is_iso_timestamp as _is_iso_timestamp
    from scripts.evidence_safety import scan_json_tree


INPUT_SCHEMA_VERSION = "wolfystock_private_beta_uat_evidence_v1"
SUMMARY_SCHEMA_VERSION = "wolfystock_private_beta_uat_evidence_summary_v1"
REDACTION_VERSION = "private_beta_uat_redaction_v1"

ROUTE_SECTION_IDS = (
    "guestPublicRouteChecks",
    "authenticatedUserRouteChecks",
    "adminRouteBoundaryChecks",
)
SAFETY_SECTION_IDS = (
    "rawLeakageChecks",
    "adviceOrderExecutionLeakageChecks",
    "consoleNetworkOverflowChecks",
)
ALLOWED_OUTCOMES = {"accepted", "needs-review", "rejected"}

SENSITIVE_KEY_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "broker_account_id",
    "broker_account_ref",
    "cookie",
    "credential",
    "debug_payload",
    "debug_trace",
    "execution_id",
    "order_id",
    "owner_id",
    "password",
    "private_key",
    "provider_id",
    "provider_payload",
    "reason_code",
    "raw_payload",
    "raw_request",
    "raw_response",
    "request_id",
    "source_ref_id",
    "session_id",
    "stack_trace",
    "token",
    "traceback",
    "user_id",
    "webhook",
)
SAFE_SCHEMA_KEY_EXCEPTIONS = {
    "checkerreadcredentials",
    "hiddennavigationtreatedasauthorization",
    "rawproviderpayloadsabsent",
}
RAW_KEY_MARKERS = (
    "debug_payload",
    "debug_trace",
    "provider_payload",
    "raw_payload",
    "raw_request",
    "raw_response",
    "stack_trace",
    "traceback",
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\b(?:api[_-]?key|token|secret|password|cookie|session)\s*=", re.IGNORECASE),
)
CONTACT_PATTERNS = (
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"\b(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})\b"),
)
URL_PATTERN = re.compile(r"https?://[^\s\"']+", re.IGNORECASE)
PRIVATE_PATH_PATTERN = re.compile(r"(?:/Users/|C:\\Users\\)", re.IGNORECASE)
PLACEHOLDER_PATTERN = re.compile(r"<[^>]+>")
TRACEBACK_PATTERN = re.compile(r"Traceback \(most recent call last\):", re.IGNORECASE)
PUBLIC_LAUNCH_APPROVAL_PATTERN = re.compile(
    r"(?:launch[-\s]?approved|release[-\s]?approved|production[-\s]?ready|"
    r"approved\s+for\s+launch|go\s+for\s+public\s+launch|"
    r"public\s+launch\s+(?:go|approved)|automatic[-\s]?go|public[-\s]?ready)",
    re.IGNORECASE,
)
ADVICE_OR_EXECUTION_PATTERN = re.compile(
    r"(?:buy\s+now|sell\s+now|place\s+order|submit\s+order|execute\s+trade|"
    r"must\s+(?:buy|sell)|best\s+contract|position\s+sizing|ideal\s+entry|secondary\s+entry|"
    r"broker[-\s]?ready|guaranteed\s+(?:return|profit)|risk[-\s]?free|"
    r"AI\s+recommends\s+you\s+buy|target\s+price|必买|稳赚|保证收益|立即交易|"
    r"立即下单|买入按钮|AI建议买入|目标价|止损|止盈|目标位|目标区间|仓位建议|"
    r"理想买入点|次优买入点|作战计划|建仓策略)",
    re.IGNORECASE,
)
RAW_INTERNAL_VALUE_PATTERN = re.compile(
    r"(?:raw[_\s-]?(?:payload|response|request|prompt|result|ai_response)|"
    r"context_snapshot|debug[_\s-]?(?:payload|trace|schema|panel)|"
    r"reasonCode|sourceRefId|source-provenance:|/api/v1/|MarketCache|"
    r"stack\s+trace|traceback)",
    re.IGNORECASE,
)


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _path(path: str, field: str) -> str:
    return f"{path}.{field}" if path else field


def _compact_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _scan_key(field: str, key: Any) -> list[dict[str, str]]:
    lowered = str(key or "").strip().lower().replace("-", "_").replace(" ", "_")
    compacted = _compact_key(key)
    findings: list[dict[str, str]] = []
    if compacted in SAFE_SCHEMA_KEY_EXCEPTIONS:
        return findings
    raw_markers = {marker.replace("_", "") for marker in RAW_KEY_MARKERS}
    sensitive_markers = {marker.replace("_", "") for marker in SENSITIVE_KEY_MARKERS}
    if any(marker in lowered for marker in RAW_KEY_MARKERS) or any(marker in compacted for marker in raw_markers):
        findings.append(_finding(field, "raw_payload_marker_forbidden"))
    elif any(marker in lowered for marker in SENSITIVE_KEY_MARKERS) or any(
        marker in compacted for marker in sensitive_markers
    ):
        findings.append(_finding(field, "sensitive_identifier_or_secret_marker_forbidden"))
    return findings


def _scan_string(field: str, value: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if PLACEHOLDER_PATTERN.search(value):
        findings.append(_finding(field, "template_placeholder_unfilled"))
    if any(pattern.search(value) for pattern in CONTACT_PATTERNS):
        findings.append(_finding(field, "operator_contact_or_real_user_value_forbidden"))
    if URL_PATTERN.search(value):
        findings.append(_finding(field, "raw_url_value_forbidden"))
    if PRIVATE_PATH_PATTERN.search(value):
        findings.append(_finding(field, "private_machine_path_forbidden"))
    if any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
        findings.append(_finding(field, "secret_value_forbidden"))
    if TRACEBACK_PATTERN.search(value):
        findings.append(_finding(field, "traceback_forbidden"))
    if RAW_INTERNAL_VALUE_PATTERN.search(value):
        findings.append(_finding(field, "raw_internal_value_forbidden"))
    if PUBLIC_LAUNCH_APPROVAL_PATTERN.search(value):
        findings.append(_finding(field, "public_launch_approval_claim_forbidden"))
    if ADVICE_OR_EXECUTION_PATTERN.search(value):
        findings.append(_finding(field, "advice_order_execution_claim_forbidden"))
    return findings


def _scan_tree(payload: Any) -> list[dict[str, str]]:
    return scan_json_tree(payload, scan_key=_scan_key, scan_string=_scan_string)


def _require_mapping(payload: dict[str, Any], field: str, findings: list[dict[str, str]]) -> dict[str, Any]:
    value = payload.get(field)
    if not isinstance(value, dict):
        findings.append(_finding(field, "missing_or_invalid_section"))
        return {}
    return value


def _require_list(payload: dict[str, Any], field: str, findings: list[dict[str, str]]) -> list[Any]:
    value = payload.get(field)
    if not isinstance(value, list) or not value:
        findings.append(_finding(field, "missing_or_empty_section"))
        return []
    return value


def _require_text(section: dict[str, Any], path: str, field: str, findings: list[dict[str, str]]) -> None:
    if not _non_empty_text(section.get(field)):
        findings.append(_finding(_path(path, field), "missing_or_invalid_text"))


def _require_bool(
    section: dict[str, Any],
    path: str,
    field: str,
    expected: bool,
    findings: list[dict[str, str]],
) -> None:
    if section.get(field) is not expected:
        reason = "expected_true" if expected else "expected_false"
        findings.append(_finding(_path(path, field), reason))


def _validate_outcome(section: dict[str, Any], path: str, findings: list[dict[str, str]]) -> None:
    outcome = str(section.get("outcome") or "").strip()
    if outcome not in ALLOWED_OUTCOMES:
        findings.append(_finding(_path(path, "outcome"), "invalid_outcome"))
    elif outcome != "accepted":
        findings.append(_finding(_path(path, "outcome"), "operator_review_not_accepted"))


def _validate_candidate(candidate: dict[str, Any], findings: list[dict[str, str]]) -> None:
    for field in ("commitSha", "branchName", "gitStatusSummary", "recordedAt", "operatorLabel"):
        _require_text(candidate, "candidate", field, findings)
    commit = str(candidate.get("commitSha") or "")
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", commit):
        findings.append(_finding("candidate.commitSha", "invalid_commit_sha"))
    if "recordedAt" in candidate and not _is_iso_timestamp(candidate.get("recordedAt")):
        findings.append(_finding("candidate.recordedAt", "invalid_timestamp"))
    for field in ("cleanTreeRecorded", "stagedFilesAbsent", "unexpectedDirtyFilesAbsent"):
        _require_bool(candidate, "candidate", field, True, findings)


def _validate_runtime(runtime: dict[str, Any], findings: list[dict[str, str]]) -> None:
    for field in ("runtimePidLabel", "runtimeCwdLabel", "runtimeOwnerLabel", "recordedAt"):
        _require_text(runtime, "runtime", field, findings)
    if "recordedAt" in runtime and not _is_iso_timestamp(runtime.get("recordedAt")):
        findings.append(_finding("runtime.recordedAt", "invalid_timestamp"))
    port = runtime.get("runtimePort")
    if not isinstance(port, int) or not 1 <= port <= 65535:
        findings.append(_finding("runtime.runtimePort", "invalid_port"))
    _require_bool(runtime, "runtime", "portOwnerMatchesIntendedBetaRuntime", True, findings)
    _require_bool(runtime, "runtime", "unknownSharedServerReusedAsEvidence", False, findings)


def _validate_route_common(section_id: str, index: int, item: Any, findings: list[dict[str, str]]) -> dict[str, Any]:
    path = f"{section_id}[{index}]"
    if not isinstance(item, dict):
        findings.append(_finding(path, "invalid_route_check"))
        return {}
    for field in ("routeLabel", "pathPattern", "finalPathLabel", "evidenceRef", "outcome"):
        _require_text(item, path, field, findings)
    _validate_outcome(item, path, findings)
    return item


def _validate_guest_routes(routes: list[Any], findings: list[dict[str, str]]) -> None:
    for index, raw_item in enumerate(routes):
        item = _validate_route_common("guestPublicRouteChecks", index, raw_item, findings)
        if not item:
            continue
        _require_text(item, f"guestPublicRouteChecks[{index}]", "expectedBoundary", findings)
        _require_bool(item, f"guestPublicRouteChecks[{index}]", "routeIdentityPreserved", True, findings)
        _require_bool(item, f"guestPublicRouteChecks[{index}]", "privateDataMounted", False, findings)


def _validate_auth_routes(routes: list[Any], findings: list[dict[str, str]]) -> None:
    for index, raw_item in enumerate(routes):
        item = _validate_route_common("authenticatedUserRouteChecks", index, raw_item, findings)
        if not item:
            continue
        if item.get("authMeStatusClass") != "2xx":
            findings.append(_finding(f"authenticatedUserRouteChecks[{index}].authMeStatusClass", "auth_me_2xx_required"))
        _require_bool(item, f"authenticatedUserRouteChecks[{index}]", "routeIdentityPreserved", True, findings)
        _require_bool(item, f"authenticatedUserRouteChecks[{index}]", "brokerOrderTradePathExposed", False, findings)


def _validate_admin_routes(routes: list[Any], findings: list[dict[str, str]]) -> None:
    for index, raw_item in enumerate(routes):
        item = _validate_route_common("adminRouteBoundaryChecks", index, raw_item, findings)
        if not item:
            continue
        for field in ("guestDenied", "nonAdminDenied", "adminCapabilityAccepted"):
            _require_bool(item, f"adminRouteBoundaryChecks[{index}]", field, True, findings)
        _require_bool(
            item,
            f"adminRouteBoundaryChecks[{index}]",
            "hiddenNavigationTreatedAsAuthorization",
            False,
            findings,
        )


def _validate_raw_leakage(section: dict[str, Any], findings: list[dict[str, str]]) -> None:
    _validate_outcome(section, "rawLeakageChecks", findings)
    for field in (
        "defaultVisibleDomChecked",
        "accessibilityTextChecked",
        "forbiddenRawTermsAbsent",
        "rawProviderPayloadsAbsent",
        "debugDetailsCollapsed",
    ):
        _require_bool(section, "rawLeakageChecks", field, True, findings)
    _require_text(section, "rawLeakageChecks", "evidenceRef", findings)


def _validate_advice_leakage(section: dict[str, Any], findings: list[dict[str, str]]) -> None:
    _validate_outcome(section, "adviceOrderExecutionLeakageChecks", findings)
    for field in (
        "defaultVisibleDomChecked",
        "forbiddenAdviceTermsAbsent",
        "noBrokerOrderTradeCta",
        "noPersonalizedFinancialAdvice",
    ):
        _require_bool(section, "adviceOrderExecutionLeakageChecks", field, True, findings)
    _require_text(section, "adviceOrderExecutionLeakageChecks", "evidenceRef", findings)


def _validate_console_network_overflow(section: dict[str, Any], findings: list[dict[str, str]]) -> None:
    _validate_outcome(section, "consoleNetworkOverflowChecks", findings)
    for field in (
        "desktopViewportChecked",
        "mobileViewportChecked",
        "consoleErrorsAbsent",
        "unexpectedNetworkFailuresAbsent",
        "horizontalOverflowAbsent",
    ):
        _require_bool(section, "consoleNetworkOverflowChecks", field, True, findings)
    _require_text(section, "consoleNetworkOverflowChecks", "evidenceRef", findings)


def _validate_secret_scan(section: dict[str, Any], findings: list[dict[str, str]]) -> None:
    for field in ("command", "baseRef", "evidenceRef"):
        _require_text(section, "releaseSecretScan", field, findings)
    command = str(section.get("command") or "")
    if "release_secret_scan.sh" not in command:
        findings.append(_finding("releaseSecretScan.command", "release_secret_scan_command_required"))
    if "--local-only" in command:
        findings.append(_finding("releaseSecretScan.command", "local_only_secret_scan_forbidden"))
    if "--base-ref origin/main" not in command:
        findings.append(_finding("releaseSecretScan.command", "branch_aware_base_ref_required"))
    if section.get("baseRef") != "origin/main":
        findings.append(_finding("releaseSecretScan.baseRef", "origin_main_base_ref_required"))
    _require_bool(section, "releaseSecretScan", "passed", True, findings)
    _require_bool(section, "releaseSecretScan", "localOnlyUsedAsReleaseEvidence", False, findings)


def _validate_rollback(section: dict[str, Any], findings: list[dict[str, str]]) -> None:
    for field in ("rollbackTargetCommitSha", "rollbackMethod", "rollbackOwnerLabel", "rollbackEvidenceRef"):
        _require_text(section, "rollback", field, findings)
    target = str(section.get("rollbackTargetCommitSha") or "")
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", target):
        findings.append(_finding("rollback.rollbackTargetCommitSha", "invalid_rollback_target_sha"))
    method = str(section.get("rollbackMethod") or "")
    if "git revert" not in method:
        findings.append(_finding("rollback.rollbackMethod", "git_revert_required"))
    _require_bool(section, "rollback", "rollbackTargetRecorded", True, findings)
    _require_bool(section, "rollback", "productionDbRollbackRequired", False, findings)
    _require_bool(section, "rollback", "postRollbackGuestAuthAdminChecksPlanned", True, findings)


def _validate_public_boundary(section: dict[str, Any], findings: list[dict[str, str]]) -> None:
    _require_bool(section, "publicLaunchBoundary", "privateBetaBoundedAuthenticatedObservationFirst", True, findings)
    for field in (
        "publicLaunchApproved",
        "publicLaunchReady",
        "liveQuotaEnforcementEnabled",
        "providerRuntimeEnforcementEnabled",
        "brokerOrderTradePathEnabled",
        "externalNotificationsSent",
        "productionDbOperationsExecuted",
        "authSessionRuntimeChangedForEvidence",
        "globalMfaRbacRuntimeChanged",
    ):
        _require_bool(section, "publicLaunchBoundary", field, False, findings)
    if str(section.get("publicLaunchVerdict") or "").strip().upper() != "NO-GO":
        findings.append(_finding("publicLaunchBoundary.publicLaunchVerdict", "public_launch_no_go_required"))


def _validate_local_generation(section: dict[str, Any], findings: list[dict[str, str]]) -> None:
    for field in (
        "checkerOpenedBrowser",
        "checkerNetworkCallsEnabled",
        "checkerReadCredentials",
        "checkerChangedRuntimeBehavior",
        "realIdentifiersIncluded",
        "rawLogsOrPayloadsIncluded",
    ):
        _require_bool(section, "localGeneration", field, False, findings)
    if section.get("evidenceRedactionVersion") != REDACTION_VERSION:
        findings.append(_finding("localGeneration.evidenceRedactionVersion", "invalid_redaction_version"))


def _dedupe_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        {json.dumps(finding, sort_keys=True): finding for finding in findings}.values(),
        key=lambda item: (item["field"], item["reasonCode"]),
    )


def validate_private_beta_uat_evidence(payload: Any) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    if not isinstance(payload, dict):
        payload = {}
        findings.append(_finding("$", "invalid_json_object"))

    if payload.get("schemaVersion") != INPUT_SCHEMA_VERSION:
        findings.append(_finding("schemaVersion", "invalid_schema_version"))

    candidate = _require_mapping(payload, "candidate", findings)
    runtime = _require_mapping(payload, "runtime", findings)
    secret_scan = _require_mapping(payload, "releaseSecretScan", findings)
    rollback = _require_mapping(payload, "rollback", findings)
    public_boundary = _require_mapping(payload, "publicLaunchBoundary", findings)
    local_generation = _require_mapping(payload, "localGeneration", findings)

    _validate_candidate(candidate, findings)
    _validate_runtime(runtime, findings)
    _validate_guest_routes(_require_list(payload, "guestPublicRouteChecks", findings), findings)
    _validate_auth_routes(_require_list(payload, "authenticatedUserRouteChecks", findings), findings)
    _validate_admin_routes(_require_list(payload, "adminRouteBoundaryChecks", findings), findings)
    _validate_raw_leakage(_require_mapping(payload, "rawLeakageChecks", findings), findings)
    _validate_advice_leakage(_require_mapping(payload, "adviceOrderExecutionLeakageChecks", findings), findings)
    _validate_console_network_overflow(_require_mapping(payload, "consoleNetworkOverflowChecks", findings), findings)
    _validate_secret_scan(secret_scan, findings)
    _validate_rollback(rollback, findings)
    _validate_public_boundary(public_boundary, findings)
    _validate_local_generation(local_generation, findings)

    findings.extend(_scan_tree(payload))
    deduped_findings = _dedupe_findings(findings)
    passed = not deduped_findings

    route_counts = {
        section_id: len(payload.get(section_id, [])) if isinstance(payload.get(section_id), list) else 0
        for section_id in ROUTE_SECTION_IDS
    }
    section_statuses = {
        section_id: "accepted"
        if not any(finding["field"].startswith(section_id) for finding in deduped_findings)
        else "blocking"
        for section_id in (
            "candidate",
            "runtime",
            *ROUTE_SECTION_IDS,
            *SAFETY_SECTION_IDS,
            "releaseSecretScan",
            "rollback",
            "publicLaunchBoundary",
            "localGeneration",
        )
    }

    return {
        "schemaVersion": SUMMARY_SCHEMA_VERSION,
        "tool": "scripts/private_beta_uat_evidence_check.py",
        "inputSchemaVersion": str(payload.get("schemaVersion") or "") if isinstance(payload, dict) else "",
        "status": "pass" if passed else "fail",
        "finalStatus": "PRIVATE_BETA_REVIEW_READY" if passed else "REJECTED",
        "privateBetaOnly": True,
        "publicLaunchApproved": False,
        "publicLaunchReady": False,
        "launchAcceptanceIntegrated": False,
        "runtimeBehaviorChanged": False,
        "networkCallsExecutedByValidator": False,
        "browserOpenedByValidator": False,
        "outboundNotificationsSentByValidator": False,
        "productionDbOperationsExecutedByValidator": False,
        "checks": {
            "candidateCleanTreeRecorded": not any(
                finding["field"].startswith("candidate.") for finding in deduped_findings
            ),
            "runtimeOwnerRecorded": not any(finding["field"].startswith("runtime.") for finding in deduped_findings),
            "routeEvidenceAccepted": all(section_statuses[section_id] == "accepted" for section_id in ROUTE_SECTION_IDS),
            "rawLeakageEvidenceAccepted": section_statuses["rawLeakageChecks"] == "accepted",
            "adviceOrderExecutionEvidenceAccepted": section_statuses["adviceOrderExecutionLeakageChecks"] == "accepted",
            "consoleNetworkOverflowEvidenceAccepted": section_statuses["consoleNetworkOverflowChecks"] == "accepted",
            "branchAwareSecretScanRecorded": section_statuses["releaseSecretScan"] == "accepted",
            "rollbackRecorded": section_statuses["rollback"] == "accepted",
            "publicLaunchNoGoPreserved": section_statuses["publicLaunchBoundary"] == "accepted",
            "checkerSideEffectsAbsent": section_statuses["localGeneration"] == "accepted",
        },
        "summary": {
            "routeCounts": route_counts,
            "blockingSections": sorted(
                section_id for section_id, status in section_statuses.items() if status != "accepted"
            ),
            "findings": len(deduped_findings),
        },
        "sections": [
            {"id": section_id, "status": status} for section_id, status in sorted(section_statuses.items())
        ],
        "findings": deduped_findings,
        "sanitization": {
            "realSecretsIncluded": False,
            "rawCredentialValuesIncluded": False,
            "realUserSessionAccountBrokerProviderIdsIncluded": False,
            "rawProviderPayloadsIncluded": False,
            "rawLogsIncluded": False,
            "networkCallsByValidator": False,
            "runtimeDefaultsChanged": False,
        },
    }


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", nargs="?", help="Sanitized private-beta UAT evidence JSON artifact.")
    parser.add_argument("--evidence", dest="evidence", help="Sanitized private-beta UAT evidence JSON artifact.")
    args = parser.parse_args(argv)
    artifact_arg = args.evidence or args.artifact
    if not artifact_arg:
        parser.error("an evidence artifact path is required")

    try:
        payload = _load_json(Path(artifact_arg))
    except (OSError, json.JSONDecodeError):
        summary = validate_private_beta_uat_evidence({})
        summary["findings"].append(_finding("$", "artifact_read_failed"))
        summary["summary"]["findings"] = len(summary["findings"])
        summary["status"] = "fail"
        summary["finalStatus"] = "REJECTED"
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 1

    summary = validate_private_beta_uat_evidence(payload)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
