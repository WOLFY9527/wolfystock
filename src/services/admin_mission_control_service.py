# -*- coding: utf-8 -*-
"""Read-only Admin Mission Control posture projection."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional

from src.services.admin_ops_status_service import AdminOpsStatusService


def _ref(kind: str, label: str, ref: str) -> Dict[str, str]:
    return {"kind": kind, "label": label, "ref": ref}


def _posture(
    *,
    landed_foundation: bool,
    evidence_tooling_exists: bool,
    real_operator_evidence_missing: bool,
    approval_required: bool,
    public_launch_no_go: bool,
) -> Dict[str, bool]:
    return {
        "landedFoundation": landed_foundation,
        "evidenceToolingExists": evidence_tooling_exists,
        "realOperatorEvidenceMissing": real_operator_evidence_missing,
        "approvalRequired": approval_required,
        "publicLaunchNoGo": public_launch_no_go,
    }


class AdminMissionControlService:
    """Build a sanitized operator cockpit without touching live controls."""

    _POSTURE_LEGEND = {
        "landedFoundation": "Foundational code, docs, or fixtures are present.",
        "evidenceToolingExists": "Offline validators, read models, or smoke helpers exist.",
        "realOperatorEvidenceMissing": "Target-environment operator evidence is still missing.",
        "approvalRequired": "A manual or external approval gate remains required.",
        "publicLaunchNoGo": "This domain does not approve public launch.",
    }

    _OPS_UNAVAILABLE = {
        "available": False,
        "status": "unavailable",
        "reasonCode": "source_unavailable",
        "readOnly": True,
        "noExternalCalls": True,
        "advisoryOnly": True,
        "liveEnforcement": False,
        "runtimeBehaviorChanged": False,
        "summary": {},
        "limitations": ["source_unavailable"],
    }

    _DOMAINS: List[Dict[str, Any]] = [
        {
            "id": "security_rbac_mfa",
            "title": "Security / RBAC / MFA",
            "status": "no_go",
            "statusLabel": "foundation plus missing operator acceptance",
            "summary": "RBAC and MFA foundations exist, but broad MFA enforcement and fallback removal still require operator evidence.",
            "posture": _posture(
                landed_foundation=True,
                evidence_tooling_exists=True,
                real_operator_evidence_missing=True,
                approval_required=True,
                public_launch_no_go=True,
            ),
            "dataSources": ["admin_capability_flags", "route_inventory_fixtures", "security_operator_evidence_docs"],
            "evidenceRefs": [
                _ref("doc", "Security index", "docs/audits/index-security-rbac-mfa.md"),
                _ref("fixture", "Backend route inventory", "tests/fixtures/auth/backend_route_capability_inventory.json"),
                _ref("fixture", "Frontend route inventory", "tests/fixtures/auth/frontend_route_capability_inventory.json"),
            ],
            "blockerRefs": [
                _ref("doc", "Launch blocker register", "docs/audits/public-launch-gap-register.md"),
            ],
            "approvalRefs": [
                _ref("script", "Security operator acceptance", "scripts/security_operator_acceptance_check.py"),
            ],
            "linkedAdminRoutes": ["/admin/users"],
            "limitations": ["mfa_login_enforcement_not_enabled", "coarse_rbac_fallback_not_launch_accepted"],
        },
        {
            "id": "quota_cost",
            "title": "Quota / Cost",
            "status": "advisory",
            "statusLabel": "observability without route enforcement",
            "summary": "Cost and quota evidence is visible as read-only diagnostics; live route-boundary enforcement is not enabled.",
            "opsKey": "quotaCostAdvisoryStatusSummary",
            "posture": _posture(
                landed_foundation=True,
                evidence_tooling_exists=True,
                real_operator_evidence_missing=True,
                approval_required=True,
                public_launch_no_go=True,
            ),
            "dataSources": ["quota_policy_readiness_helpers", "llm_cost_ledger_summary"],
            "evidenceRefs": [
                _ref("api", "Ops status", "GET /api/v1/admin/ops/status"),
                _ref("api", "Cost summary", "GET /api/v1/admin/cost/duplicate-summary"),
                _ref("api", "Quota dry-run estimate", "POST /api/v1/admin/cost/quota-dry-run"),
                _ref("doc", "Cost / quota index", "docs/audits/index-cost-quota-observability.md"),
            ],
            "blockerRefs": [
                _ref("doc", "Launch blocker register", "docs/audits/public-launch-gap-register.md"),
            ],
            "approvalRefs": [
                _ref("script", "Quota operator evidence", "scripts/quota_operator_evidence_check.py"),
            ],
            "linkedAdminRoutes": ["/admin/cost-observability"],
            "limitations": ["estimate_only", "reserve_consume_release_not_called", "invoice_reconciliation_not_authoritative"],
        },
        {
            "id": "provider_reliability",
            "title": "Provider Reliability",
            "status": "diagnostic",
            "statusLabel": "SLA and circuit evidence without provider blocking",
            "summary": "Provider operations, SLA, circuit, quota-window, and probe diagnostics exist; runtime provider order and fallback stay unchanged.",
            "opsKey": "providerStatusSummary",
            "posture": _posture(
                landed_foundation=True,
                evidence_tooling_exists=True,
                real_operator_evidence_missing=True,
                approval_required=True,
                public_launch_no_go=True,
            ),
            "dataSources": ["provider_circuit_states", "provider_circuit_events", "provider_quota_windows", "provider_probe_events"],
            "evidenceRefs": [
                _ref("api", "Provider operations", "GET /api/v1/admin/market-providers/operations"),
                _ref("api", "Provider SLA readiness", "GET /api/v1/admin/providers/sla-readiness"),
                _ref("api", "Provider operations matrix", "GET /api/v1/admin/providers/operations-matrix"),
                _ref("doc", "Provider / data index", "docs/audits/index-provider-data-options.md"),
            ],
            "blockerRefs": [
                _ref("doc", "Launch blocker register", "docs/audits/public-launch-gap-register.md"),
            ],
            "approvalRefs": [
                _ref("script", "Provider operator evidence", "scripts/provider_operator_evidence_check.py"),
            ],
            "linkedAdminRoutes": ["/admin/market-providers", "/admin/provider-circuits"],
            "limitations": ["no_live_provider_checks", "provider_order_unchanged", "fallback_behavior_unchanged"],
        },
        {
            "id": "storage_restore",
            "title": "Storage / Restore",
            "status": "no_go",
            "statusLabel": "session check only; restore proof missing",
            "summary": "Storage session and offline restore validators exist, but real isolated restore and PITR evidence is still missing.",
            "opsKey": "storageReadinessSummary",
            "posture": _posture(
                landed_foundation=True,
                evidence_tooling_exists=True,
                real_operator_evidence_missing=True,
                approval_required=True,
                public_launch_no_go=True,
            ),
            "dataSources": ["database_session_check", "restore_pitr_operator_evidence_docs"],
            "evidenceRefs": [
                _ref("api", "Ops status", "GET /api/v1/admin/ops/status"),
                _ref("doc", "DB / WS2 / deployment index", "docs/audits/index-db-ws2-deployment.md"),
                _ref("doc", "Backup restore drill plan", "docs/audits/db-retention-backup-restore-drill-plan.md"),
            ],
            "blockerRefs": [
                _ref("doc", "Launch blocker register", "docs/audits/public-launch-gap-register.md"),
            ],
            "approvalRefs": [
                _ref("script", "Restore PITR operator evidence", "scripts/restore_pitr_operator_evidence_check.py"),
            ],
            "linkedAdminRoutes": ["/admin/logs"],
            "limitations": ["session_check_only", "cleanup_not_called", "migration_not_run", "restore_not_run"],
        },
        {
            "id": "ws2_async",
            "title": "WS2 / Async",
            "status": "limited",
            "statusLabel": "process-local posture visible",
            "summary": "Task queue status is visible, but multi-instance WS2 and SSE operator evidence remains required.",
            "opsKey": "taskQueueStatusSummary",
            "posture": _posture(
                landed_foundation=True,
                evidence_tooling_exists=True,
                real_operator_evidence_missing=True,
                approval_required=True,
                public_launch_no_go=True,
            ),
            "dataSources": ["task_queue_runtime_status", "ws2_operator_evidence_docs"],
            "evidenceRefs": [
                _ref("api", "Ops status", "GET /api/v1/admin/ops/status"),
                _ref("doc", "WS2 smoke design", "docs/audits/ws2-multi-instance-smoke-test-design.md"),
                _ref("doc", "DB / WS2 / deployment index", "docs/audits/index-db-ws2-deployment.md"),
            ],
            "blockerRefs": [
                _ref("doc", "Launch blocker register", "docs/audits/public-launch-gap-register.md"),
            ],
            "approvalRefs": [
                _ref("script", "WS2 SSE operator decision", "scripts/ws2_sse_operator_decision_check.py"),
            ],
            "linkedAdminRoutes": ["/admin/logs"],
            "limitations": ["process_local_status_only", "multi_instance_evidence_missing", "sse_cross_instance_not_claimed"],
        },
        {
            "id": "notifications",
            "title": "Notifications",
            "status": "foundation",
            "statusLabel": "channels and events exist; no sends from cockpit",
            "summary": "Notification channel and event read APIs exist; delivery rehearsal evidence remains separate and this cockpit never sends.",
            "posture": _posture(
                landed_foundation=True,
                evidence_tooling_exists=True,
                real_operator_evidence_missing=True,
                approval_required=True,
                public_launch_no_go=True,
            ),
            "dataSources": ["notification_channels", "notification_events"],
            "evidenceRefs": [
                _ref("api", "Notification channels", "GET /api/v1/admin/notification-channels"),
                _ref("api", "Notification events", "GET /api/v1/admin/notifications"),
                _ref("doc", "Launch master", "docs/audits/public-launch-readiness-master.md"),
            ],
            "blockerRefs": [
                _ref("doc", "Launch blocker register", "docs/audits/public-launch-gap-register.md"),
            ],
            "approvalRefs": [
                _ref("doc", "Operator evidence runbook", "docs/audits/operator-evidence-real-runbook.md"),
            ],
            "linkedAdminRoutes": ["/admin/notifications"],
            "limitations": ["notification_send_not_attempted", "delivery_rehearsal_evidence_required"],
        },
        {
            "id": "portfolio_backtest",
            "title": "Portfolio / Backtest",
            "status": "no_go",
            "statusLabel": "read models and fixtures exist; broader safety proof missing",
            "summary": "Portfolio admin read models and backtest fixtures exist; launch still needs owner-isolation and safety acceptance.",
            "posture": _posture(
                landed_foundation=True,
                evidence_tooling_exists=True,
                real_operator_evidence_missing=True,
                approval_required=True,
                public_launch_no_go=True,
            ),
            "dataSources": ["admin_portfolio_read_models", "backtest_readiness_fixtures"],
            "evidenceRefs": [
                _ref("api", "Admin user portfolio summary", "GET /api/v1/admin/users/{user_id}/portfolio-summary"),
                _ref("fixture", "OOS parameter readiness", "tests/fixtures/backtest/rule_backtest_oos_parameter_readiness_export.json"),
                _ref("doc", "Backtest portfolio safety audit", "docs/audits/backtest-portfolio-public-safety-audit.md"),
            ],
            "blockerRefs": [
                _ref("doc", "Launch blocker register", "docs/audits/public-launch-gap-register.md"),
            ],
            "approvalRefs": [
                _ref("test", "Portfolio/backtest safety tests", "tests/test_backtest_oos_parameter_readiness_contract.py"),
            ],
            "linkedAdminRoutes": ["/admin/users"],
            "limitations": ["target_user_portfolio_not_read_by_cockpit", "owner_isolation_acceptance_required"],
        },
        {
            "id": "route_classification",
            "title": "Route Classification",
            "status": "evidence_tooling",
            "statusLabel": "route inventory frozen; fallback removal not approved",
            "summary": "Backend and frontend route classification fixtures exist, but fallback removal still requires review evidence.",
            "posture": _posture(
                landed_foundation=True,
                evidence_tooling_exists=True,
                real_operator_evidence_missing=True,
                approval_required=True,
                public_launch_no_go=True,
            ),
            "dataSources": ["backend_route_capability_inventory", "frontend_route_capability_inventory"],
            "evidenceRefs": [
                _ref("fixture", "Backend route inventory", "tests/fixtures/auth/backend_route_capability_inventory.json"),
                _ref("fixture", "Frontend route inventory", "tests/fixtures/auth/frontend_route_capability_inventory.json"),
                _ref("test", "Route inventory test", "tests/test_admin_rbac_route_inventory.py"),
            ],
            "blockerRefs": [
                _ref("doc", "RBAC fallback removal plan", "docs/audits/admin-rbac-r5-coarse-fallback-removal-plan.md"),
            ],
            "approvalRefs": [
                _ref("script", "Security operator acceptance", "scripts/security_operator_acceptance_check.py"),
            ],
            "linkedAdminRoutes": ["/admin/users", "/settings/system"],
            "limitations": ["fallback_removal_not_approved", "route_inventory_is_evidence_not_enforcement"],
        },
        {
            "id": "private_beta_readiness",
            "title": "Private-beta Readiness",
            "status": "review_required",
            "statusLabel": "beta evidence exists; public launch remains NO-GO",
            "summary": "Private-beta smoke and safety evidence exists, but it does not grant public launch approval.",
            "posture": _posture(
                landed_foundation=True,
                evidence_tooling_exists=True,
                real_operator_evidence_missing=True,
                approval_required=True,
                public_launch_no_go=True,
            ),
            "dataSources": ["readiness_smoke_tests", "public_launch_docs"],
            "evidenceRefs": [
                _ref("test", "Readiness browser acceptance", "apps/dsa-web/e2e/readiness-browser-acceptance.smoke.spec.ts"),
                _ref("test", "Critical route launch smoke", "apps/dsa-web/e2e/critical-route-launch-smoke.spec.ts"),
                _ref("doc", "Launch master", "docs/audits/public-launch-readiness-master.md"),
            ],
            "blockerRefs": [
                _ref("doc", "Launch blocker register", "docs/audits/public-launch-gap-register.md"),
            ],
            "approvalRefs": [
                _ref("script", "Manual release review record", "scripts/manual_release_approval_evidence_check.py"),
            ],
            "linkedAdminRoutes": ["/admin/evidence-workflow"],
            "limitations": ["private_beta_not_public_launch_approval", "manual_release_review_required"],
        },
    ]

    def build_snapshot(self, *, app_state: object | None = None) -> Dict[str, Any]:
        generated_at = datetime.now().isoformat()
        ops_status, ops_available, ops_reason = self._safe_ops_status(app_state=app_state)
        domains = [self._build_domain(domain, ops_status) for domain in self._DOMAINS]
        summary = self._build_summary(domains)
        return {
            "generatedAt": generated_at,
            "readOnly": True,
            "noExternalCalls": True,
            "liveEnforcement": False,
            "runtimeBehaviorChanged": False,
            "publicLaunchApproved": False,
            "releaseApproved": False,
            "launchVerdict": "NO_GO",
            "opsSnapshotAvailable": ops_available,
            "summary": summary,
            "domains": domains,
            "postureLegend": self._POSTURE_LEGEND,
            "metadata": {
                "contract": "admin_mission_control_v1",
                "gatingCapability": "ops:logs:read",
                "opsSnapshotReasonCode": ops_reason,
                "mutationPaths": [],
                "externalCallsMade": False,
                "providerCallsAttempted": False,
                "notificationSendAttempted": False,
                "portfolioTargetReadsAttempted": False,
                "cleanupCalled": False,
                "restoreCalled": False,
                "migrationRun": False,
                "authBehaviorChanged": False,
                "productionConfigMutation": False,
                "publicLaunchApprovalAdded": False,
                "redaction": [
                    "raw_identifiers_omitted",
                    "auth_material_omitted",
                    "external_payloads_omitted",
                    "trace_details_omitted",
                    "target_user_portfolio_details_not_read",
                ],
            },
        }

    def _safe_ops_status(self, *, app_state: object | None) -> tuple[Dict[str, Any], bool, Optional[str]]:
        try:
            return AdminOpsStatusService().build_status(app_state=app_state), True, None
        except Exception:
            return {}, False, "source_unavailable"

    def _build_domain(self, blueprint: Mapping[str, Any], ops_status: Mapping[str, Any]) -> Dict[str, Any]:
        item = deepcopy(dict(blueprint))
        ops_key = item.pop("opsKey", None)
        ops_section = None
        if ops_key:
            raw_section = ops_status.get(str(ops_key))
            ops_section = raw_section if isinstance(raw_section, dict) else self._OPS_UNAVAILABLE
        item.update(
            {
                "readOnly": True,
                "noExternalCalls": True,
                "liveEnforcement": False,
                "runtimeBehaviorChanged": False,
                "opsStatus": ops_section,
            }
        )
        return item

    @staticmethod
    def _build_summary(domains: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
        domain_list = list(domains)

        def _count(flag: str) -> int:
            return sum(1 for domain in domain_list if bool((domain.get("posture") or {}).get(flag)))

        return {
            "domainCount": len(domain_list),
            "landedFoundationCount": _count("landedFoundation"),
            "evidenceToolingCount": _count("evidenceToolingExists"),
            "realOperatorEvidenceMissingCount": _count("realOperatorEvidenceMissing"),
            "approvalRequiredCount": _count("approvalRequired"),
            "publicLaunchNoGoCount": _count("publicLaunchNoGo"),
        }
