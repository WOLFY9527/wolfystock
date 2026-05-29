from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "launch_acceptance_evidence.py"
ACCEPTED_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "release" / "launch_acceptance_evidence.accepted.json"
MISSING_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "release" / "launch_acceptance_evidence.missing.json"
EXPECTED_CATEGORY_IDS = {
    "mfa_pilot_acceptance",
    "rbac_fallback_disable_switch",
    "provider_credential_staging_dry_run",
    "provider_staging_probe_artifact",
    "provider_live_probe_opt_in_timeout",
    "provider_circuit_controlled_enforcement",
    "quota_pilot_acceptance",
    "budget_alert_dry_run_acceptance",
    "real_isolated_postgresql_restore_pitr",
    "staging_ingress_smoke",
    "public_api_frontend_no_secret_safety",
    "supply_chain_dependency_build_artifact_safety",
    "incident_response_audit_evidence",
    "ws2_sse_topology_polling_fallback",
    "admin_log_retention_capacity_rehearsal",
    "portfolio_backtest_export_browser_proof",
    "notifications_delivery_rehearsal",
    "user_data_privacy_export_deletion_rehearsal",
    "market_data_freshness_fallback_evidence",
    "ai_report_guest_preview_safety",
    "options_derivatives_safety",
    "api_abuse_request_safety",
    "final_clean_full_ci_gate",
    "provider_operator_evidence",
    "restore_pitr_operator_evidence",
    "security_operator_acceptance",
    "quota_budget_operator_evidence",
    "staging_ingress_operator_evidence",
    "ws2_sse_operator_decision_evidence",
    "config_snapshot_evidence",
    "manual_release_approval_review_record",
}
NEW_OPERATOR_CATEGORY_IDS = {
    "provider_operator_evidence",
    "restore_pitr_operator_evidence",
    "security_operator_acceptance",
    "quota_budget_operator_evidence",
    "staging_ingress_operator_evidence",
    "ws2_sse_operator_decision_evidence",
    "config_snapshot_evidence",
    "manual_release_approval_review_record",
}


def _accepted_category(required_checks: list[str]) -> dict:
    return {
        "status": "accepted",
        "acceptedBy": "release-operator",
        "capturedAt": "2026-05-08T00:00:00Z",
        "evidenceRef": "synthetic-operator-evidence-json",
        "checks": {check: True for check in required_checks},
        "sanitization": {
            "externalServicesCalledByChecker": False,
            "realSecretsIncluded": False,
            "rawCredentialValuesIncluded": False,
            "rawProviderPayloadsIncluded": False,
            "responseBodiesIncluded": False,
            "productionDataPathsIncluded": False,
        },
    }


def _run_checker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _json(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def test_launch_acceptance_evidence_missing_categories_remain_no_go() -> None:
    result = _run_checker("--evidence", str(MISSING_FIXTURE))

    assert result.returncode == 1
    evidence = _json(result)
    assert evidence["schemaVersion"] == "wolfystock_launch_acceptance_evidence_summary_v1"
    assert evidence["finalStatus"] == "NO-GO"
    assert evidence["releaseApproved"] is False
    assert evidence["sanitization"] == {
        "externalServicesCalled": False,
        "networkCallsEnabled": False,
        "realEnvFileRead": False,
        "secretValuesRead": False,
        "secretValuesIncluded": False,
        "rawPayloadsIncluded": False,
        "responseBodiesIncluded": False,
        "productionDataPathsRead": False,
        "runtimeDefaultsChanged": False,
    }
    assert evidence["summary"]["accepted"] == 0
    assert evidence["summary"]["blocking"] == 31
    blocker_ids = {item["id"] for item in evidence["hardBlockers"]}
    assert EXPECTED_CATEGORY_IDS == blocker_ids


def test_launch_acceptance_evidence_allow_no_go_returns_zero_for_review_attachment() -> None:
    result = _run_checker("--evidence", str(MISSING_FIXTURE), "--allow-no-go")

    assert result.returncode == 0
    assert _json(result)["finalStatus"] == "NO-GO"


def test_launch_acceptance_evidence_all_accepted_is_go_review_required_not_approved() -> None:
    result = _run_checker("--evidence", str(ACCEPTED_FIXTURE))

    assert result.returncode == 0
    evidence = _json(result)
    assert evidence["finalStatus"] == "GO-REVIEW-REQUIRED"
    assert evidence["releaseApproved"] is False
    assert evidence["statusReason"] == "All hard blockers have accepted sanitized evidence; release approval remains manual."
    assert evidence["summary"]["accepted"] == 31
    assert evidence["summary"]["blocking"] == 0
    assert evidence["hardBlockers"] == []
    categories = {item["id"]: item for item in evidence["categories"]}
    assert EXPECTED_CATEGORY_IDS == set(categories)
    assert categories["mfa_pilot_acceptance"]["requiredChecks"] == [
        "adminPilotPassed",
        "adminOnlyScopeRecorded",
        "unsupportedGlobalRolloutNoGo",
        "recoveryPathTested",
        "breakGlassDisabledByDefault",
        "rollbackPlanRecorded",
        "auditEvidenceSanitized",
        "secretEvidenceRedacted",
    ]
    assert categories["rbac_fallback_disable_switch"]["requiredChecks"] == [
        "disableSwitchExplicit",
        "routeInventoryComplete",
        "coarseFallbackDisabledOrExceptionAccepted",
        "explicitCapabilityPayloadsPassWithoutFallback",
        "legacyMissingCapabilityUsersFailClosed",
        "rollbackPlanRecorded",
        "auditEvidenceSanitized",
        "runtimeDefaultUnchanged",
    ]
    assert categories["provider_credential_staging_dry_run"]["requiredChecks"] == [
        "stagingDryRunPassed",
        "credentialPresenceOnly",
        "noLiveCallsByChecker",
        "entitlementMatrixAttached",
    ]
    assert categories["provider_staging_probe_artifact"]["requiredChecks"] == [
        "stagingProbeArtifactAttached",
        "credentialValuesRedacted",
        "entitlementAndFreshnessLabelsRecorded",
        "operatorCaptureMetadataRecorded",
        "noLiveCallsByChecker",
    ]
    assert categories["provider_live_probe_opt_in_timeout"]["requiredChecks"] == [
        "namedStagingProviderRecorded",
        "liveProbeOptInRecorded",
        "liveProbeTimeoutBounded",
        "probeResultSanitized",
        "noLiveCallsByChecker",
    ]
    assert categories["provider_circuit_controlled_enforcement"]["status"] == "accepted"
    assert categories["provider_circuit_controlled_enforcement"]["requiredChecks"] == [
        "controlledEnforcementPilotPassed",
        "boundedRouteRecorded",
        "rollbackSwitchRecorded",
        "degradedEvidenceSanitized",
    ]
    assert categories["quota_pilot_acceptance"]["requiredChecks"] == [
        "pilotPassed",
        "explicitOwnerAllowlistRecorded",
        "outOfScopeUsersAdvisoryOnly",
        "invoiceReconciliationAdvisoryOnly",
        "invoiceReconciliationNotEnforcementInput",
        "globalEnforcementDisabledByDefault",
        "rollbackSwitchRecorded",
        "statusLabelsRecorded",
    ]
    assert categories["budget_alert_dry_run_acceptance"]["requiredChecks"] == [
        "pilotBlockEmitsSanitizedBudgetAlertIntent",
        "budgetAlertEvidenceRedacted",
        "realOutboundDeliveryDisabledByDefault",
        "noLiveLlmProviderOrInvoiceCalls",
        "alertStatusLabelsRecorded",
    ]
    assert categories["supply_chain_dependency_build_artifact_safety"]["requiredChecks"] == [
        "dependencyManifestsInspected",
        "manifestsSanitized",
        "buildArtifactsSanitized",
        "frontendBuildWarningsVisible",
        "noDependencyOrLockfileChanges",
        "missingEvidenceNoGoVerified",
    ]
    assert categories["incident_response_audit_evidence"]["requiredChecks"] == [
        "incidentPackAttached",
        "adminCriticalActionsAudited",
        "previewFirstCleanupEvidence",
        "providerNotificationReleaseFailuresRecorded",
        "localNoNetworkGeneration",
        "auditEvidenceSanitized",
        "secretEvidenceRedacted",
    ]
    assert categories["ws2_sse_topology_polling_fallback"]["requiredChecks"] == [
        "processLocalSseLimitationRecorded",
        "durablePollingFallbackVerified",
        "apiABTopologyEvidenceAttached",
        "ownerIsolationEvidenceRecorded",
        "runtimeCutoverNotPerformed",
    ]
    assert categories["admin_log_retention_capacity_rehearsal"]["requiredChecks"] == [
        "retentionPolicyRecorded",
        "previewFirstCleanupVerified",
        "minimumRetentionGuardVerified",
        "storagePressureRehearsalPassed",
        "cleanupAuditSanitized",
        "runtimeDefaultUnchanged",
    ]
    assert categories["portfolio_backtest_export_browser_proof"]["requiredChecks"] == [
        "exportEvidenceAttached",
        "browserProofAttached",
        "noAdviceAndOrderVerbsAbsent",
        "ownerIsolationEvidenceRecorded",
        "brokerCredentialEvidenceRedacted",
        "runtimeMutationNotPerformed",
    ]
    assert categories["notifications_delivery_rehearsal"]["requiredChecks"] == [
        "deliveryRehearsalPassed",
        "routeChannelMappingRecorded",
        "failurePathAudited",
        "notificationSecretsRedacted",
        "realOutboundDisabledOrAccepted",
    ]
    assert categories["user_data_privacy_export_deletion_rehearsal"]["requiredChecks"] == [
        "privacyExportProjectionSanitized",
        "deletionPreviewRehearsed",
        "ownerIsolationEvidenceRecorded",
        "privacyAuditEvidenceSanitized",
        "rawUserDataNotExposed",
    ]
    assert categories["market_data_freshness_fallback_evidence"]["requiredChecks"] == [
        "providerAndAsOfLabelsRecorded",
        "staleFallbackDisclosureVerified",
        "confidenceCapBehaviorVerified",
        "rawProviderPayloadsRedacted",
        "runtimeDefaultUnchanged",
    ]
    assert categories["ai_report_guest_preview_safety"]["requiredChecks"] == [
        "guestPreviewSafetyVerified",
        "rawPromptAndLlmResponsesRedacted",
        "noAutoAnalysisSideEffects",
        "guestIsolationEvidenceRecorded",
        "noAdviceLabelsVerified",
    ]
    assert categories["options_derivatives_safety"]["requiredChecks"] == [
        "readOnlyNoOrderPostureVerified",
        "brokerAndPortfolioMutationAbsent",
        "fixtureDelayedFallbackCapsVerified",
        "guaranteedReturnWordingAbsent",
        "providerEvidenceSanitized",
    ]
    assert categories["api_abuse_request_safety"]["requiredChecks"] == [
        "abuseRehearsalPassed",
        "invalidRequestHandlingVerified",
        "oversizedPayloadSafetyVerified",
        "denialAuditEvidenceSanitized",
        "debugTracebackAndRequestBodiesRedacted",
        "runtimeDefaultUnchanged",
    ]
    assert categories["provider_operator_evidence"]["requiredChecks"] == [
        "providerOperatorValidatorPassed",
        "providerOperatorGuideReferenced",
        "artifactSummarySanitized",
        "networkCallsExecutedByValidatorFalse",
        "runtimeBehaviorUnchanged",
        "advisoryReviewGateRecorded",
    ]
    assert categories["restore_pitr_operator_evidence"]["requiredChecks"] == [
        "restorePitrOperatorValidatorPassed",
        "restorePitrGuideReferenced",
        "realRestoreArtifactSanitized",
        "databaseCommandsRunByValidatorFalse",
        "productionStorageUntouched",
        "manualReviewGateRecorded",
    ]
    assert categories["security_operator_acceptance"]["requiredChecks"] == [
        "securityOperatorValidatorPassed",
        "securityOperatorGuideReferenced",
        "mfaRbacSectionsAccepted",
        "releaseApprovedFalse",
        "runtimeBehaviorUnchanged",
        "manualReviewGateRecorded",
    ]
    assert categories["quota_budget_operator_evidence"]["requiredChecks"] == [
        "quotaOperatorValidatorPassed",
        "quotaBudgetGuideReferenced",
        "quotaBudgetSectionsAccepted",
        "outboundNotificationsSentByValidatorFalse",
        "runtimeBehaviorUnchanged",
        "advisoryReviewGateRecorded",
    ]
    assert categories["staging_ingress_operator_evidence"]["requiredChecks"] == [
        "stagingIngressOperatorValidatorPassed",
        "stagingIngressGuideReferenced",
        "stagingIngressArtifactSanitized",
        "networkCallsExecutedByValidatorFalse",
        "runtimeBehaviorUnchanged",
        "manualReviewGateRecorded",
    ]
    assert categories["ws2_sse_operator_decision_evidence"]["requiredChecks"] == [
        "ws2SseOperatorDecisionValidatorPassed",
        "ws2SseOperatorDecisionGuideReferenced",
        "topologyDecisionAccepted",
        "processLocalSseLimitationPreserved",
        "pollingFallbackOrSingleInstanceLimitationRecorded",
        "networkCallsExecutedByValidatorFalse",
        "runtimeBehaviorUnchanged",
        "manualReviewGateRecorded",
    ]
    assert categories["config_snapshot_evidence"]["requiredChecks"] == [
        "configSnapshotValidatorPassed",
        "configSnapshotGuideReferenced",
        "authProviderQuotaDatabaseSummariesRecorded",
        "secretPresenceOnlyOrRedacted",
        "rawConfigAndEnvValuesExcluded",
        "externalServicesCalledByValidatorFalse",
        "runtimeBehaviorUnchanged",
        "manualReviewGateRecorded",
    ]
    assert categories["manual_release_approval_review_record"]["requiredChecks"] == [
        "manualReleaseApprovalValidatorPassed",
        "manualReleaseApprovalGuideReferenced",
        "reviewRecordSanitized",
        "releaseApprovedFalse",
        "launchApprovedFalse",
        "manualApprovalDoesNotAutoApprove",
        "runtimeBehaviorUnchanged",
        "externalReleaseApprovalRemainsManual",
    ]


def test_launch_acceptance_evidence_missing_new_operator_categories_keep_no_go(tmp_path: Path) -> None:
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    for category_id in NEW_OPERATOR_CATEGORY_IDS:
        payload["categories"].pop(category_id, None)
    evidence_path = tmp_path / "missing-new-operator-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    evidence = _json(result)
    assert evidence["finalStatus"] == "NO-GO"
    assert evidence["releaseApproved"] is False
    assert evidence["summary"]["blocking"] == len(NEW_OPERATOR_CATEGORY_IDS)
    blocker_ids = {item["id"] for item in evidence["hardBlockers"]}
    assert blocker_ids == NEW_OPERATOR_CATEGORY_IDS


def test_launch_acceptance_evidence_admin_log_retention_capacity_rehearsal_is_backed_by_repo_local_offline_anchors() -> None:
    result = _run_checker("--evidence", str(ACCEPTED_FIXTURE))

    assert result.returncode == 0
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "admin_log_retention_capacity_rehearsal")
    assert category["status"] == "accepted"
    assert category["requiredChecks"] == [
        "retentionPolicyRecorded",
        "previewFirstCleanupVerified",
        "minimumRetentionGuardVerified",
        "storagePressureRehearsalPassed",
        "cleanupAuditSanitized",
        "runtimeDefaultUnchanged",
    ]

    accepted_payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    fixture_category = accepted_payload["categories"]["admin_log_retention_capacity_rehearsal"]
    assert fixture_category["evidenceRef"] == "admin-log-retention-capacity-rehearsal-synthetic-json"
    assert fixture_category["sanitization"] == {
        "externalServicesCalledByChecker": False,
        "realSecretsIncluded": False,
        "rawCredentialValuesIncluded": False,
        "rawProviderPayloadsIncluded": False,
        "responseBodiesIncluded": False,
        "productionDataPathsIncluded": False,
    }

    admin_logs_source = (REPO_ROOT / "tests" / "api" / "test_admin_logs.py").read_text(encoding="utf-8")
    execution_log_source = (REPO_ROOT / "tests" / "test_execution_log_service.py").read_text(encoding="utf-8")
    expected_anchor_tests = {
        "retentionPolicyRecorded": [
            ("admin_logs", "def test_storage_summary_exposes_explicit_admin_log_retention_tiers(self) -> None:"),
        ],
        "previewFirstCleanupVerified": [
            ("admin_logs", "def test_storage_summary_capacity_cleanup_plan_keeps_preview_metadata_explicit(self) -> None:"),
            ("admin_logs", "def test_cleanup_defaults_to_preview_and_does_not_emit_vacuum_note(self) -> None:"),
        ],
        "minimumRetentionGuardVerified": [
            ("admin_logs", "def test_capacity_cleanup_actual_run_preserves_min_retention(self) -> None:"),
        ],
        "storagePressureRehearsalPassed": [
            ("admin_logs", "def test_storage_summary_capacity_plan_is_preview_only_without_auto_cleanup(self) -> None:"),
            ("admin_logs", "def test_storage_summary_read_path_with_read_capability_never_calls_cleanup(self) -> None:"),
            ("admin_logs", "def test_capacity_cleanup_dry_run_does_not_delete_logs(self) -> None:"),
        ],
        "cleanupAuditSanitized": [
            ("admin_logs", "def test_capacity_cleanup_actual_run_emits_sanitized_audit_event(self) -> None:"),
            ("execution_log", "def test_admin_security_cost_provider_and_quota_actions_sanitize_incident_evidence(self) -> None:"),
        ],
        "runtimeDefaultUnchanged": [
            ("admin_logs", "def test_storage_summary_read_path_with_read_capability_never_calls_cleanup(self) -> None:"),
        ],
    }

    for check_name, anchor_tests in expected_anchor_tests.items():
        assert check_name in category["requiredChecks"]
        for source_name, anchor_test in anchor_tests:
            source = execution_log_source if source_name == "execution_log" else admin_logs_source
            assert anchor_test in source

    assert "storage summary must not invoke cleanup" in admin_logs_source
    assert "\"synthetic\"" in execution_log_source


def test_launch_acceptance_evidence_market_data_freshness_fallback_is_backed_by_repo_local_offline_anchors() -> None:
    result = _run_checker("--evidence", str(ACCEPTED_FIXTURE))

    assert result.returncode == 0
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "market_data_freshness_fallback_evidence")
    assert category["status"] == "accepted"
    assert category["requiredChecks"] == [
        "providerAndAsOfLabelsRecorded",
        "staleFallbackDisclosureVerified",
        "confidenceCapBehaviorVerified",
        "rawProviderPayloadsRedacted",
        "runtimeDefaultUnchanged",
    ]

    accepted_payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    fixture_category = accepted_payload["categories"]["market_data_freshness_fallback_evidence"]
    assert fixture_category["evidenceRef"] == "market-data-freshness-fallback-evidence-synthetic-json"
    assert fixture_category["sanitization"] == {
        "externalServicesCalledByChecker": False,
        "realSecretsIncluded": False,
        "rawCredentialValuesIncluded": False,
        "rawProviderPayloadsIncluded": False,
        "responseBodiesIncluded": False,
        "productionDataPathsIncluded": False,
    }

    market_cache_source = (REPO_ROOT / "tests" / "api" / "test_market_cache.py").read_text(encoding="utf-8")
    fallback_contracts_source = (REPO_ROOT / "tests" / "test_market_cache_fallback_contracts.py").read_text(
        encoding="utf-8"
    )
    provider_operations_source = (
        REPO_ROOT / "tests" / "api" / "test_market_provider_operations.py"
    ).read_text(encoding="utf-8")
    provider_freshness_source = (REPO_ROOT / "tests" / "test_provider_freshness_contracts.py").read_text(
        encoding="utf-8"
    )
    stock_freshness_source = (REPO_ROOT / "tests" / "test_stock_api_freshness_contract.py").read_text(
        encoding="utf-8"
    )
    provider_reliability_audit_source = (REPO_ROOT / "scripts" / "provider_reliability_audit.py").read_text(
        encoding="utf-8"
    )

    expected_anchor_tests = {
        "providerAndAsOfLabelsRecorded": [
            (
                fallback_contracts_source,
                "def test_market_overview_live_payload_round_trips_through_json() -> None:",
            ),
            (
                stock_freshness_source,
                "def test_quote_endpoint_exposes_provider_source_and_market_timestamp_without_breaking_existing_fields() -> None:",
            ),
            (
                stock_freshness_source,
                "def test_intraday_endpoint_preserves_old_fields_and_adds_proxy_provenance_metadata() -> None:",
            ),
        ],
        "staleFallbackDisclosureVerified": [
            (
                provider_freshness_source,
                "def test_fallback_mock_and_synthetic_sources_are_never_labeled_live(source: str, expected_freshness: str) -> None:",
            ),
            (
                market_cache_source,
                "def test_fetcher_failure_uses_fallback_without_changing_freshness(self) -> None:",
            ),
            (
                fallback_contracts_source,
                "def test_process_local_scores_fallback_is_marked_stale_without_losing_source_metadata() -> None:",
            ),
            (
                provider_operations_source,
                "def test_unavailable_cache_metadata_is_represented_honestly() -> None:",
            ),
        ],
        "confidenceCapBehaviorVerified": [
            (
                market_cache_source,
                "def test_entry_metadata_can_be_projected_to_json_safe_shape(self) -> None:",
            ),
            (
                stock_freshness_source,
                "\"capReason\": None,",
            ),
        ],
        "rawProviderPayloadsRedacted": [
            (
                provider_freshness_source,
                "def test_provider_failure_cases_fall_back_without_relabeling_primary_as_live(primary, expected_reason: str) -> None:",
            ),
            (
                provider_operations_source,
                "def test_timeout_fallback_and_stale_cache_health_signals_stay_distinct_and_read_only() -> None:",
            ),
        ],
        "runtimeDefaultUnchanged": [
            (
                provider_freshness_source,
                "def test_offline_reliability_audit_cli_outputs_bounded_json_without_network_calls() -> None:",
            ),
            (
                provider_operations_source,
                "def test_aggregator_does_not_call_external_providers_or_cache_refresh() -> None:",
            ),
        ],
    }

    for check_name, anchor_tests in expected_anchor_tests.items():
        assert check_name in category["requiredChecks"]
        for source, anchor_test in anchor_tests:
            assert anchor_test in source

    assert "These tests are intentionally synthetic/offline. They must not call live" in provider_freshness_source
    assert "providers or change provider routing." in provider_freshness_source
    assert "\"networkCallsExecuted\": False," in provider_reliability_audit_source
    assert "without provider calls" in provider_reliability_audit_source
    assert "scoreReliabilityAllowed" in market_cache_source
    assert "\"sourceConfidence\"" in stock_freshness_source
    assert "assert \"authority\" not in str(summary).lower()" in provider_operations_source
    assert "assert \"decision\" not in str(summary).lower()" in provider_operations_source


def test_launch_acceptance_evidence_api_abuse_request_safety_is_backed_by_repo_local_offline_anchors() -> None:
    result = _run_checker("--evidence", str(ACCEPTED_FIXTURE))

    assert result.returncode == 0
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "api_abuse_request_safety")
    assert category["status"] == "accepted"
    assert category["requiredChecks"] == [
        "abuseRehearsalPassed",
        "invalidRequestHandlingVerified",
        "oversizedPayloadSafetyVerified",
        "denialAuditEvidenceSanitized",
        "debugTracebackAndRequestBodiesRedacted",
        "runtimeDefaultUnchanged",
    ]

    public_api_safety_source = (
        REPO_ROOT / "tests" / "api" / "test_public_api_surface_safety.py"
    ).read_text(encoding="utf-8")
    assert "def _assert_public_surface_safe(payload: object) -> None:" in public_api_safety_source
    assert "def test_launch_surface_route_inventory_remains_stable_and_fixture_safe() -> None:" in public_api_safety_source

    expected_anchor_tests = {
        "abuseRehearsalPassed": [
            "def test_api_abuse_rate_limit_readiness_has_global_public_limiter() -> None:",
            "def test_public_api_abuse_limiter_429_exposes_no_request_or_client_details(monkeypatch, caplog) -> None:",
        ],
        "invalidRequestHandlingVerified": [
            "def test_public_request_shape_errors_are_sanitized_for_malformed_json_and_unsupported_methods() -> None:",
        ],
        "oversizedPayloadSafetyVerified": [
            "def test_unauthenticated_admin_abuse_payloads_fail_closed_before_request_body_is_exposed() -> None:",
        ],
        "denialAuditEvidenceSanitized": [
            "def test_public_api_abuse_limiter_does_not_log_or_expose_raw_request_values(monkeypatch, caplog) -> None:",
            "def test_public_api_abuse_limiter_429_exposes_no_request_or_client_details(monkeypatch, caplog) -> None:",
        ],
        "debugTracebackAndRequestBodiesRedacted": [
            "def test_public_api_abuse_limiter_does_not_log_or_expose_raw_request_values(monkeypatch, caplog) -> None:",
            "def test_public_api_abuse_limiter_429_exposes_no_request_or_client_details(monkeypatch, caplog) -> None:",
        ],
        "runtimeDefaultUnchanged": [
            "def test_api_abuse_rate_limit_readiness_has_global_public_limiter() -> None:",
        ],
    }

    for check_name, anchor_tests in expected_anchor_tests.items():
        assert check_name in category["requiredChecks"]
        for anchor_test in anchor_tests:
            assert anchor_test in public_api_safety_source


def test_launch_acceptance_evidence_user_data_privacy_rehearsal_is_backed_by_repo_local_offline_anchors() -> None:
    result = _run_checker("--evidence", str(ACCEPTED_FIXTURE))

    assert result.returncode == 0
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "user_data_privacy_export_deletion_rehearsal")
    assert category["status"] == "accepted"
    assert category["requiredChecks"] == [
        "privacyExportProjectionSanitized",
        "deletionPreviewRehearsed",
        "ownerIsolationEvidenceRecorded",
        "privacyAuditEvidenceSanitized",
        "rawUserDataNotExposed",
    ]

    accepted_payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    fixture_category = accepted_payload["categories"]["user_data_privacy_export_deletion_rehearsal"]
    assert fixture_category["evidenceRef"] == "user-data-privacy-export-deletion-rehearsal-synthetic-json"
    assert fixture_category["sanitization"] == {
        "externalServicesCalledByChecker": False,
        "realSecretsIncluded": False,
        "rawCredentialValuesIncluded": False,
        "rawProviderPayloadsIncluded": False,
        "responseBodiesIncluded": False,
        "productionDataPathsIncluded": False,
    }

    admin_users_source = (REPO_ROOT / "tests" / "api" / "test_admin_users.py").read_text(encoding="utf-8")
    admin_user_activity_source = (REPO_ROOT / "tests" / "api" / "test_admin_user_activity.py").read_text(
        encoding="utf-8"
    )

    expected_anchor_tests = {
        "privacyExportProjectionSanitized": [
            (
                admin_users_source,
                "def test_user_directory_privacy_export_projection_is_read_only_and_sanitized(self) -> None:",
            ),
        ],
        "deletionPreviewRehearsed": [
            (
                admin_users_source,
                "def test_destructive_user_delete_route_remains_unsupported_and_read_only(self) -> None:",
            ),
        ],
        "ownerIsolationEvidenceRecorded": [
            (
                admin_users_source,
                "def test_cross_user_admin_detail_attempt_is_denied_with_sanitized_error(self) -> None:",
            ),
            (
                admin_user_activity_source,
                "def test_user_targeted_timeline_is_scoped_and_redacted(self) -> None:",
            ),
            (
                admin_user_activity_source,
                "def test_user_route_rejects_mismatched_target_user_filter(self) -> None:",
            ),
        ],
        "privacyAuditEvidenceSanitized": [
            (
                admin_user_activity_source,
                "def test_user_targeted_timeline_is_scoped_and_redacted(self) -> None:",
            ),
        ],
        "rawUserDataNotExposed": [
            (
                admin_users_source,
                "def test_user_directory_privacy_export_projection_is_read_only_and_sanitized(self) -> None:",
            ),
            (
                admin_user_activity_source,
                "def test_user_targeted_timeline_is_scoped_and_redacted(self) -> None:",
            ),
        ],
    }

    for check_name, anchor_tests in expected_anchor_tests.items():
        assert check_name in category["requiredChecks"]
        for source, anchor_test in anchor_tests:
            assert anchor_test in source

    assert "self._assert_no_privacy_export_leaks(response)" in admin_users_source
    assert 'self.assertTrue(set(getattr(route, "methods", set())) <= {"GET"})' in admin_users_source
    assert 'self.assertEqual(response.status_code, 405)' in admin_users_source
    assert 'self.assertEqual(self._count(AppUser), before_users)' in admin_users_source
    assert 'self.assertEqual(self._count(AppUserSession), before_sessions)' in admin_users_source
    assert 'self.assertNotIn("user-2", self._json_text(response))' in admin_users_source
    assert 'self.assertTrue(all(item["targetUser"]["id"] == "user-1" for item in payload["items"]))' in (
        admin_user_activity_source
    )
    assert 'self.assertNotIn("raw-token-value", text)' in admin_user_activity_source
    assert 'self.assertNotIn("RAW_PROVIDER_PAYLOAD", text)' in admin_user_activity_source
    assert 'self.assertNotIn("RAW_STACK_TRACE", text)' in admin_user_activity_source
    assert 'self.assertNotIn("RAW_REQUEST_BODY", text)' in admin_user_activity_source
    assert 'self.assertNotIn("MSFT", text)' in admin_user_activity_source


def test_launch_acceptance_evidence_input_release_approved_true_is_ignored(tmp_path: Path) -> None:
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["releaseApproved"] = True
    payload["launchApproved"] = True
    evidence_path = tmp_path / "input-release-approved-ignored.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 0
    evidence = _json(result)
    assert evidence["finalStatus"] == "GO-REVIEW-REQUIRED"
    assert evidence["releaseApproved"] is False


def test_manual_approval_evidence_cannot_auto_approve_release(tmp_path: Path) -> None:
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["categories"]["manual_release_approval_review_record"]["releaseApproved"] = True
    payload["categories"]["manual_release_approval_review_record"]["launchApproved"] = True
    evidence_path = tmp_path / "manual-approval-cannot-auto-approve.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    evidence = _json(result)
    assert evidence["finalStatus"] == "NO-GO"
    assert evidence["releaseApproved"] is False
    category = next(item for item in evidence["categories"] if item["id"] == "manual_release_approval_review_record")
    assert category["status"] == "blocking"
    assert category["reasonCodes"] == ["release_approval_boolean_present"]


def test_launch_acceptance_evidence_keeps_provider_circuit_required_when_missing(tmp_path: Path) -> None:
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["categories"].pop("provider_circuit_controlled_enforcement")
    evidence_path = tmp_path / "missing-provider-circuit.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    evidence = _json(result)
    assert evidence["finalStatus"] == "NO-GO"
    assert evidence["summary"]["blocking"] == 1
    assert evidence["hardBlockers"] == [
        {
            "id": "provider_circuit_controlled_enforcement",
            "status": "blocking",
            "requiredEvidence": "controlled provider-circuit enforcement pilot, bounded route, rollback switch, and sanitized degraded-state evidence",
        }
    ]


def test_launch_acceptance_evidence_rejects_secret_like_values_without_leaking(tmp_path: Path) -> None:
    secret = "sk-" + ("A" * 40)
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["categories"]["provider_credential_staging_dry_run"]["evidenceRef"] = secret
    evidence_path = tmp_path / "unsafe-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert secret not in combined_output
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "provider_credential_staging_dry_run")
    assert category["status"] == "blocking"
    assert category["reasonCodes"] == ["sensitive_value_present"]


def test_launch_acceptance_evidence_rejects_mfa_secret_fields_without_leaking(tmp_path: Path) -> None:
    recovery_code = "RECOVERY-CODE-1234"
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["categories"]["mfa_pilot_acceptance"]["operatorArtifact"] = {
        "totp_secret": "totp-secret",
        "mfa_recovery_code": recovery_code,
        "session_id": "raw-session-id",
    }
    evidence_path = tmp_path / "unsafe-mfa-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert recovery_code not in combined_output
    assert "totp-secret" not in combined_output
    assert "raw-session-id" not in combined_output
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "mfa_pilot_acceptance")
    assert category["status"] == "blocking"
    assert category["reasonCodes"] == ["sensitive_value_present"]


def test_launch_acceptance_evidence_rejects_public_matrix_secret_aliases_without_leaking(tmp_path: Path) -> None:
    api_key = "api_key=launch-secret-123456"
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["categories"]["incident_response_audit_evidence"]["operatorArtifact"] = {
        "API key": api_key,
        "rawResponseBody": "{\"session\":\"raw-session-id\"}",
        "provider credential": "credential-value",
    }
    evidence_path = tmp_path / "unsafe-public-matrix-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert api_key not in combined_output
    assert "raw-session-id" not in combined_output
    assert "credential-value" not in combined_output
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "incident_response_audit_evidence")
    assert category["status"] == "blocking"
    assert category["reasonCodes"] == ["sensitive_value_present"]


def test_launch_acceptance_evidence_rejects_traceback_debug_markers_without_leaking(tmp_path: Path) -> None:
    request_body = "debug_payload=raw-body request_body=raw-request"
    traceback_marker = "Traceback (most recent call last):"
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["categories"]["api_abuse_request_safety"]["operatorArtifact"] = {
        "traceback": traceback_marker,
        "debugPayload": request_body,
    }
    evidence_path = tmp_path / "unsafe-traceback-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert traceback_marker not in combined_output
    assert "raw-body" not in combined_output
    assert "raw-request" not in combined_output
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "api_abuse_request_safety")
    assert category["status"] == "blocking"
    assert category["reasonCodes"] == ["sensitive_value_present"]


def test_launch_acceptance_evidence_rejects_new_operator_unsafe_markers_without_leaking(tmp_path: Path) -> None:
    unsafe_cases = {
        "provider_operator_evidence": (
            "providerOperatorValidatorPassed",
            "providerPayload",
            "provider credential raw body should-not-print",
        ),
        "restore_pitr_operator_evidence": (
            "restorePitrOperatorValidatorPassed",
            "dsn",
            "postgresql://operator:should-not-print@example.invalid/wolfy",
        ),
        "security_operator_acceptance": (
            "securityOperatorValidatorPassed",
            "sessionCookie",
            "session=should-not-print",
        ),
        "quota_budget_operator_evidence": (
            "quotaOperatorValidatorPassed",
            "requestBody",
            "request_body=should-not-print",
        ),
        "staging_ingress_operator_evidence": (
            "stagingIngressOperatorValidatorPassed",
            "debugPayload",
            "Traceback (most recent call last): should-not-print",
        ),
        "ws2_sse_operator_decision_evidence": (
            "ws2SseOperatorDecisionValidatorPassed",
            "sessionCookie",
            "session=should-not-print",
        ),
        "config_snapshot_evidence": (
            "configSnapshotValidatorPassed",
            "rawEnvDump",
            "APP_ENV=should-not-print",
        ),
        "manual_release_approval_review_record": (
            "manualReleaseApprovalValidatorPassed",
            "rawMeetingTranscript",
            "meeting transcript should-not-print",
        ),
    }
    for category_id, (first_check, unsafe_key, unsafe_value) in unsafe_cases.items():
        payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
        category = payload["categories"].get(category_id) or _accepted_category([first_check])
        category["operatorArtifact"] = {unsafe_key: unsafe_value}
        payload["categories"][category_id] = category
        evidence_path = tmp_path / f"unsafe-{category_id}.json"
        evidence_path.write_text(json.dumps(payload), encoding="utf-8")

        result = _run_checker("--evidence", str(evidence_path))

        assert result.returncode == 1, category_id
        combined_output = result.stdout + result.stderr
        assert "should-not-print" not in combined_output
        evidence = _json(result)
        category_result = next(item for item in evidence["categories"] if item["id"] == category_id)
        assert category_result["status"] == "blocking"
        assert category_result["reasonCodes"] == ["sensitive_value_present"]


def test_launch_acceptance_evidence_requires_provider_live_probe_contract_checks(tmp_path: Path) -> None:
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    checks = payload["categories"]["provider_live_probe_opt_in_timeout"]["checks"]
    checks.pop("liveProbeOptInRecorded")
    checks.pop("liveProbeTimeoutBounded")
    evidence_path = tmp_path / "missing-provider-live-probe-contract.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "provider_live_probe_opt_in_timeout")
    assert category["status"] == "blocking"
    assert category["missingChecks"] == ["liveProbeOptInRecorded", "liveProbeTimeoutBounded"]
    assert category["reasonCodes"] == ["missing_required_checks"]


def test_launch_acceptance_evidence_requires_quota_pilot_checks(tmp_path: Path) -> None:
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    checks = payload["categories"]["quota_pilot_acceptance"]["checks"]
    checks.pop("explicitOwnerAllowlistRecorded", None)
    evidence_path = tmp_path / "missing-quota-pilot-alert-safety-checks.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "quota_pilot_acceptance")
    assert category["status"] == "blocking"
    assert category["missingChecks"] == ["explicitOwnerAllowlistRecorded"]
    assert category["reasonCodes"] == ["missing_required_checks"]


def test_launch_acceptance_evidence_requires_budget_alert_dry_run_checks(tmp_path: Path) -> None:
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    checks = payload["categories"]["budget_alert_dry_run_acceptance"]["checks"]
    checks.pop("pilotBlockEmitsSanitizedBudgetAlertIntent", None)
    checks.pop("realOutboundDeliveryDisabledByDefault", None)
    checks.pop("noLiveLlmProviderOrInvoiceCalls", None)
    evidence_path = tmp_path / "missing-budget-alert-dry-run-checks.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "budget_alert_dry_run_acceptance")
    assert category["status"] == "blocking"
    assert category["missingChecks"] == [
        "pilotBlockEmitsSanitizedBudgetAlertIntent",
        "realOutboundDeliveryDisabledByDefault",
        "noLiveLlmProviderOrInvoiceCalls",
    ]
    assert category["reasonCodes"] == ["missing_required_checks"]


def test_launch_acceptance_evidence_rejects_build_artifact_secret_patterns_without_leaking(tmp_path: Path) -> None:
    secret = "postgresql://launch_user:secret-pass@example.test:5432/wolfy"
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["categories"]["supply_chain_dependency_build_artifact_safety"]["artifactEvidence"] = {
        "file": "dist/assets/app.js",
        "dsn": secret,
    }
    evidence_path = tmp_path / "unsafe-artifact-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert secret not in combined_output
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "supply_chain_dependency_build_artifact_safety")
    assert category["status"] == "blocking"
    assert category["reasonCodes"] == ["sensitive_value_present"]


def test_launch_acceptance_evidence_requires_supply_chain_manifest_and_artifact_checks(tmp_path: Path) -> None:
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    checks = payload["categories"]["supply_chain_dependency_build_artifact_safety"]["checks"]
    checks.pop("dependencyManifestsInspected")
    checks.pop("buildArtifactsSanitized")
    evidence_path = tmp_path / "missing-supply-chain-checks.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "supply_chain_dependency_build_artifact_safety")
    assert category["status"] == "blocking"
    assert category["missingChecks"] == ["dependencyManifestsInspected", "buildArtifactsSanitized"]
    assert category["reasonCodes"] == ["missing_required_checks"]
