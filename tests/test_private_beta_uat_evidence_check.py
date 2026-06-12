# -*- coding: utf-8 -*-
"""Offline private-beta UAT evidence validator tests."""

from __future__ import annotations

import json
import ast
from copy import deepcopy
from pathlib import Path

from tests.helpers.cli_validator import make_cli_validator, stdout_json as _stdout_json


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "private_beta_uat_evidence_check.py"
TEMPLATE = REPO_ROOT / "docs" / "release" / "private-beta-uat-evidence-template.json"
_write_json, _run_validator = make_cli_validator(
    SCRIPT,
    cwd=REPO_ROOT,
    artifact_name="private-beta-uat-evidence.json",
)


def _route(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "routeLabel": "route-label",
        "pathPattern": "/route",
        "finalPathLabel": "/route",
        "evidenceRef": "uat-ticket-1503",
        "outcome": "accepted",
    }
    payload.update(overrides)
    return payload


def _artifact() -> dict[str, object]:
    return {
        "schemaVersion": "wolfystock_private_beta_uat_evidence_v1",
        "mode": "operator_sanitized",
        "candidate": {
            "commitSha": "abc1234",
            "branchName": "codex/private-beta-candidate",
            "recordedAt": "2026-06-12T10:30:00Z",
            "operatorLabel": "beta-ops",
            "gitStatusSummary": "clean tree recorded by operator",
            "cleanTreeRecorded": True,
            "stagedFilesAbsent": True,
            "unexpectedDirtyFilesAbsent": True,
        },
        "runtime": {
            "runtimePidLabel": "pid-recorded",
            "runtimeCwdLabel": "task-worktree",
            "runtimePort": 4179,
            "runtimeOwnerLabel": "beta-ops",
            "recordedAt": "2026-06-12T10:35:00Z",
            "portOwnerMatchesIntendedBetaRuntime": True,
            "unknownSharedServerReusedAsEvidence": False,
        },
        "guestPublicRouteChecks": [
            _route(
                routeLabel="guest-home",
                pathPattern="/guest",
                finalPathLabel="/guest",
                expectedBoundary="guest-preview",
                routeIdentityPreserved=True,
                privateDataMounted=False,
            )
        ],
        "authenticatedUserRouteChecks": [
            _route(
                routeLabel="home",
                pathPattern="/",
                finalPathLabel="/",
                authMeStatusClass="2xx",
                routeIdentityPreserved=True,
                brokerOrderTradePathExposed=False,
            )
        ],
        "adminRouteBoundaryChecks": [
            _route(
                routeLabel="admin-ops-status",
                pathPattern="/admin/ops-status",
                finalPathLabel="/admin/ops-status",
                guestDenied=True,
                nonAdminDenied=True,
                adminCapabilityAccepted=True,
                hiddenNavigationTreatedAsAuthorization=False,
            )
        ],
        "rawLeakageChecks": {
            "defaultVisibleDomChecked": True,
            "accessibilityTextChecked": True,
            "forbiddenRawTermsAbsent": True,
            "rawProviderPayloadsAbsent": True,
            "debugDetailsCollapsed": True,
            "evidenceRef": "uat-ticket-1503",
            "outcome": "accepted",
        },
        "adviceOrderExecutionLeakageChecks": {
            "defaultVisibleDomChecked": True,
            "forbiddenAdviceTermsAbsent": True,
            "noBrokerOrderTradeCta": True,
            "noPersonalizedFinancialAdvice": True,
            "evidenceRef": "uat-ticket-1503",
            "outcome": "accepted",
        },
        "consoleNetworkOverflowChecks": {
            "desktopViewportChecked": True,
            "mobileViewportChecked": True,
            "consoleErrorsAbsent": True,
            "unexpectedNetworkFailuresAbsent": True,
            "horizontalOverflowAbsent": True,
            "evidenceRef": "uat-ticket-1503",
            "outcome": "accepted",
        },
        "releaseSecretScan": {
            "command": "./scripts/release_secret_scan.sh --base-ref origin/main",
            "baseRef": "origin/main",
            "passed": True,
            "localOnlyUsedAsReleaseEvidence": False,
            "evidenceRef": "release-secret-scan-log",
        },
        "rollback": {
            "rollbackTargetCommitSha": "abc1234",
            "rollbackTargetRecorded": True,
            "rollbackMethod": "git revert abc1234",
            "rollbackOwnerLabel": "beta-ops",
            "rollbackEvidenceRef": "rollback-runbook-ticket",
            "productionDbRollbackRequired": False,
            "postRollbackGuestAuthAdminChecksPlanned": True,
        },
        "publicLaunchBoundary": {
            "privateBetaBoundedAuthenticatedObservationFirst": True,
            "publicLaunchVerdict": "NO-GO",
            "publicLaunchApproved": False,
            "publicLaunchReady": False,
            "liveQuotaEnforcementEnabled": False,
            "providerRuntimeEnforcementEnabled": False,
            "brokerOrderTradePathEnabled": False,
            "externalNotificationsSent": False,
            "productionDbOperationsExecuted": False,
            "authSessionRuntimeChangedForEvidence": False,
            "globalMfaRbacRuntimeChanged": False,
        },
        "localGeneration": {
            "checkerOpenedBrowser": False,
            "checkerNetworkCallsEnabled": False,
            "checkerReadCredentials": False,
            "checkerChangedRuntimeBehavior": False,
            "realIdentifiersIncluded": False,
            "rawLogsOrPayloadsIncluded": False,
            "evidenceRedactionVersion": "private_beta_uat_redaction_v1",
        },
    }


def test_accepts_sanitized_private_beta_uat_artifact(tmp_path: Path) -> None:
    result = _run_validator(_write_json(tmp_path, _artifact()))

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["status"] == "pass"
    assert payload["finalStatus"] == "PRIVATE_BETA_REVIEW_READY"
    assert payload["privateBetaOnly"] is True
    assert payload["publicLaunchApproved"] is False
    assert payload["publicLaunchReady"] is False
    assert payload["networkCallsExecutedByValidator"] is False
    assert payload["browserOpenedByValidator"] is False
    assert payload["runtimeBehaviorChanged"] is False
    assert payload["checks"]["branchAwareSecretScanRecorded"] is True


def test_template_is_safe_but_not_accepted_until_operator_fills_it() -> None:
    result = _run_validator(TEMPLATE)

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert payload["status"] == "fail"
    assert payload["publicLaunchApproved"] is False
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "template_placeholder_unfilled" in reason_codes
    assert "operator_review_not_accepted" in reason_codes


def test_rejects_local_only_secret_scan_and_public_launch_approval_claim(tmp_path: Path) -> None:
    artifact = deepcopy(_artifact())
    secret_scan = artifact["releaseSecretScan"]
    boundary = artifact["publicLaunchBoundary"]
    assert isinstance(secret_scan, dict)
    assert isinstance(boundary, dict)
    secret_scan["command"] = "./scripts/release_secret_scan.sh --local-only"
    secret_scan["localOnlyUsedAsReleaseEvidence"] = True
    boundary["publicLaunchApproved"] = True
    boundary["publicLaunchVerdict"] = "GO for public launch"

    result = _run_validator(_write_json(tmp_path, artifact))

    assert result.returncode == 1
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "local_only_secret_scan_forbidden" in reason_codes
    assert "branch_aware_base_ref_required" in reason_codes
    assert "expected_false" in reason_codes
    assert "public_launch_approval_claim_forbidden" in reason_codes


def test_rejects_raw_identifiers_secrets_urls_and_paths_without_echoing_values(tmp_path: Path) -> None:
    secret_value = "sk-" + "a" * 30
    raw_url = "https://internal.example.invalid/api?token=should-not-print"
    private_path = "/Users/private-person/project"
    artifact = _artifact()
    artifact["runtime"] = {
        **artifact["runtime"],  # type: ignore[dict-item]
        "runtimeCwdLabel": private_path,
    }
    artifact["rawProviderPayload"] = {"api_key": secret_value, "url": raw_url}
    artifact["operatorEmail"] = "person@example.invalid"

    result = _run_validator(_write_json(tmp_path, artifact))

    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert secret_value not in combined
    assert raw_url not in combined
    assert private_path not in combined
    reason_codes = {finding["reasonCode"] for finding in _stdout_json(result)["findings"]}
    assert "raw_payload_marker_forbidden" in reason_codes
    assert "secret_value_forbidden" in reason_codes
    assert "raw_url_value_forbidden" in reason_codes
    assert "private_machine_path_forbidden" in reason_codes
    assert "operator_contact_or_real_user_value_forbidden" in reason_codes


def test_rejects_advice_order_execution_and_forbidden_runtime_boundaries(tmp_path: Path) -> None:
    artifact = deepcopy(_artifact())
    advice = artifact["adviceOrderExecutionLeakageChecks"]
    boundary = artifact["publicLaunchBoundary"]
    assert isinstance(advice, dict)
    assert isinstance(boundary, dict)
    advice["evidenceRef"] = "AI recommends you buy and place order"
    boundary["providerRuntimeEnforcementEnabled"] = True
    boundary["externalNotificationsSent"] = True
    boundary["productionDbOperationsExecuted"] = True

    result = _run_validator(_write_json(tmp_path, artifact))

    assert result.returncode == 1
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "advice_order_execution_claim_forbidden" in reason_codes
    assert "expected_false" in reason_codes


def test_rejects_broader_advice_and_raw_internal_uat_terms(tmp_path: Path) -> None:
    artifact = deepcopy(_artifact())
    raw = artifact["rawLeakageChecks"]
    advice = artifact["adviceOrderExecutionLeakageChecks"]
    assert isinstance(raw, dict)
    assert isinstance(advice, dict)
    raw["evidenceRef"] = "raw_result sourceRefId /api/v1/internal MarketCache"
    advice["evidenceRef"] = "目标价 and position sizing imply an order plan"

    result = _run_validator(_write_json(tmp_path, artifact))

    assert result.returncode == 1
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "raw_internal_value_forbidden" in reason_codes
    assert "advice_order_execution_claim_forbidden" in reason_codes


def test_missing_route_evidence_blocks_review(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact["guestPublicRouteChecks"] = []
    auth_route = artifact["authenticatedUserRouteChecks"][0]  # type: ignore[index]
    assert isinstance(auth_route, dict)
    auth_route["authMeStatusClass"] = "401"

    result = _run_validator(_write_json(tmp_path, artifact))

    assert result.returncode == 1
    payload = _stdout_json(result)
    findings = {(finding["field"], finding["reasonCode"]) for finding in payload["findings"]}
    assert ("guestPublicRouteChecks", "missing_or_empty_section") in findings
    assert ("authenticatedUserRouteChecks[0].authMeStatusClass", "auth_me_2xx_required") in findings


def test_checker_stays_offline_and_does_not_import_runtime_or_network_modules() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert not imported.intersection(
        {
            "api",
            "src",
            "data_provider",
            "requests",
            "httpx",
            "socket",
            "webbrowser",
            "playwright",
            "selenium",
        }
    )
