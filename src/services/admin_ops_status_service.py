# -*- coding: utf-8 -*-
"""Read-only admin ops status snapshot aggregation."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

from sqlalchemy import func, select, text

from src.logging_config import describe_runtime_file_logging
from src.services.build_provenance_service import BuildProvenanceService, build_unknown_provenance
from src.services.admin_logs_service import AdminLogsRetentionService
from src.services.llm_cost_ledger_service import LlmCostLedgerService
from src.services.quota_policy_service import QuotaPolicyService
from src.storage import (
    AdminRole,
    AdminRoleCapability,
    AdminUserRole,
    AppUser,
    DatabaseManager,
    DurableTaskState,
    ExecutionLogEvent,
    ExecutionLogSession,
    ProviderCircuitEvent,
    ProviderCircuitState,
    ProviderProbeEvent,
    ProviderQuotaWindow,
)


class AdminOpsStatusService:
    """Aggregate existing admin evidence without changing runtime behavior."""

    _HEALTHY_PROVIDER_STATES = frozenset({"closed", "healthy", "ok"})
    _LAUNCH_COCKPIT_PRIORITY_PROFILES = {
        "security_rbac_mfa": {
            "sortOrder": 10,
            "priorityTier": "critical",
            "impactLevel": "critical",
            "ownerSurface": "security_access_control",
            "remediationSurface": "/admin/users",
            "recommendedNextAction": "Review sanitized MFA/RBAC operator evidence before changing access posture.",
            "blockingReasonSummary": "Access-control launch gate lacks staged operator evidence.",
        },
        "storage_restore": {
            "sortOrder": 20,
            "priorityTier": "critical",
            "impactLevel": "critical",
            "ownerSurface": "data_integrity_recovery",
            "remediationSurface": "/admin/evidence-workflow",
            "recommendedNextAction": "Review storage readiness and restore acceptance evidence without running migrations or cleanup.",
            "blockingReasonSummary": "Restore and PITR acceptance evidence is missing for data recovery readiness.",
        },
        "ws2_async": {
            "sortOrder": 30,
            "priorityTier": "high",
            "impactLevel": "high",
            "ownerSurface": "runtime_operations",
            "remediationSurface": "/admin/evidence-workflow",
            "recommendedNextAction": "Record process-local runtime limitations and verify durable polling acceptance evidence.",
            "blockingReasonSummary": "Runtime topology remains limited until multi-instance acceptance evidence is recorded.",
        },
        "portfolio_backtest": {
            "sortOrder": 40,
            "priorityTier": "high",
            "impactLevel": "high",
            "ownerSurface": "research_safety",
            "remediationSurface": "/admin/evidence-workflow",
            "recommendedNextAction": "Review stored-first portfolio/backtest safety evidence and owner-isolation proof.",
            "blockingReasonSummary": "Portfolio/backtest safety proof is incomplete for research-loop readiness.",
        },
        "provider_reliability": {
            "sortOrder": 50,
            "priorityTier": "high",
            "impactLevel": "high",
            "ownerSurface": "provider_reliability",
            "remediationSurface": "/admin/provider-circuits",
            "recommendedNextAction": "Inspect provider SLA diagnostics and entitlement evidence without changing provider order or fallback.",
            "blockingReasonSummary": "Provider reliability is diagnostic-only and live-data entitlement evidence is incomplete.",
        },
        "quota_cost": {
            "sortOrder": 60,
            "priorityTier": "high",
            "impactLevel": "high",
            "ownerSurface": "cost_controls",
            "remediationSurface": "/admin/cost-observability",
            "recommendedNextAction": "Inspect cost observability and quota evidence without creating reservations or live blocking.",
            "blockingReasonSummary": "Quota/cost controls remain advisory; live route enforcement is approval-gated.",
        },
        "route_classification": {
            "sortOrder": 70,
            "priorityTier": "medium",
            "impactLevel": "medium",
            "ownerSurface": "route_inventory",
            "remediationSurface": "/admin/evidence-workflow",
            "recommendedNextAction": "Compare route inventory with admin capability expectations and keep release approval external.",
            "blockingReasonSummary": "Route inventory is present but manual release review remains external.",
        },
        "notifications": {
            "sortOrder": 80,
            "priorityTier": "medium",
            "impactLevel": "medium",
            "ownerSurface": "notification_operations",
            "remediationSurface": "/admin/notifications",
            "recommendedNextAction": "Review channel coverage and event evidence without sending notifications.",
            "blockingReasonSummary": "Delivery rehearsal evidence is missing and sends remain disabled.",
        },
        "frontend_private_beta_safety": {
            "sortOrder": 90,
            "priorityTier": "watch",
            "impactLevel": "low",
            "ownerSurface": "frontend_private_beta",
            "remediationSurface": "/settings/system",
            "recommendedNextAction": "Run bounded admin cockpit smoke with mocked data before private-beta review.",
            "blockingReasonSummary": "Private-beta browser evidence is pending; public launch approval remains external.",
        },
    }
    _SENSITIVE_TEXT_MARKERS = (
        "traceback",
        "exception",
        "postgres://",
        "sqlite://",
        "api_key",
        "apikey",
        "secret",
        "token",
        "cookie",
        "bearer",
        "authorization",
        "password",
        "scripts/",
        "docs/",
        "tests/",
        "api/v1/endpoints/",
        "/users/",
        ".py",
        ".md",
        "://",
    )

    def build_status(
        self,
        *,
        app_state: object | None = None,
        include_section_summaries: bool = False,
    ) -> Dict[str, Any]:
        """Build the public bounded snapshot, with opt-in typed summaries for internal admin projections."""
        generated_at = datetime.now()
        generated_at_iso = generated_at.isoformat()
        provider_status = self._safe_source(self._build_provider_status_summary)
        quota_status = self._safe_source(lambda: self._build_quota_cost_advisory_status_summary(generated_at))
        storage_status = self._safe_source(self._build_storage_readiness_summary)
        task_queue_status = self._safe_source(lambda: self._build_task_queue_status_summary(app_state))
        admin_log_status = self._safe_source(self._build_admin_log_evidence_summary)
        runtime_log_sink_status = self._safe_source(self._build_runtime_log_sink_summary)
        retention_policy_status = self._safe_source(self._build_retention_policy_status)
        execution_log_retention_risk = self._safe_source(self._build_execution_log_retention_risk)
        db_size_risk = self._safe_source(self._build_db_size_risk)
        admin_role_assignment_status = self._safe_source(self._build_admin_role_assignment_status)
        durable_task_backlog_status = self._safe_source(self._build_durable_task_backlog_status)
        build_provenance = self._safe_build_provenance(app_state)
        return {
            "generatedAt": generated_at_iso,
            "readOnly": True,
            "noExternalCalls": True,
            "liveEnforcement": False,
            "runtimeBehaviorChanged": False,
            "consumerVisible": False,
            "advisoryVsEnforcement": {
                "label": "advisory_snapshot",
                "enforcementLabel": "not_launch_control",
                "sourceUnavailableBehavior": "degrade_to_unavailable",
                "readOnly": True,
                "noExternalCalls": True,
                "liveEnforcement": False,
                "runtimeBehaviorChanged": False,
                "consumerVisible": False,
            },
            "providerStatusSummary": self._project_section(
                service="provider_reliability",
                snapshot=provider_status,
                configured=bool(provider_status.get("available")),
                last_checked_at=generated_at_iso if provider_status.get("available") else None,
                message=self._provider_status_message(provider_status),
                include_summary=include_section_summaries,
            ),
            "quotaCostAdvisoryStatusSummary": self._project_section(
                service="quota_cost",
                snapshot=quota_status,
                configured=bool(quota_status.get("available")),
                last_checked_at=generated_at_iso if quota_status.get("available") else None,
                message=self._quota_status_message(quota_status),
                include_summary=include_section_summaries,
            ),
            "storageReadinessSummary": self._project_section(
                service="storage",
                snapshot=storage_status,
                configured=bool(storage_status.get("available")),
                last_checked_at=generated_at_iso if storage_status.get("available") else None,
                message=self._storage_status_message(storage_status),
                include_summary=include_section_summaries,
            ),
            "taskQueueStatusSummary": self._project_section(
                service="task_queue",
                snapshot=task_queue_status,
                configured=getattr(app_state, "task_queue", None) is not None,
                last_checked_at=generated_at_iso if task_queue_status.get("available") else None,
                message=self._task_queue_status_message(task_queue_status),
                include_summary=include_section_summaries,
            ),
            "adminLogEvidenceSummary": self._project_section(
                service="admin_logs",
                snapshot=admin_log_status,
                configured=bool(admin_log_status.get("available")),
                last_checked_at=generated_at_iso if admin_log_status.get("available") else None,
                message=self._admin_log_status_message(admin_log_status),
                include_summary=include_section_summaries,
            ),
            "runtimeLogSinkSummary": self._project_runtime_log_sink_section(
                snapshot=runtime_log_sink_status,
                last_checked_at=generated_at_iso,
            ),
            "retentionPolicyStatus": self._project_maintenance_section(
                service="retention_policy",
                snapshot=retention_policy_status,
                configured=bool(retention_policy_status.get("available")),
                last_checked_at=generated_at_iso if retention_policy_status.get("available") else None,
                message=self._retention_policy_status_message(retention_policy_status),
            ),
            "executionLogRetentionRisk": self._project_maintenance_section(
                service="execution_log_retention",
                snapshot=execution_log_retention_risk,
                configured=bool(execution_log_retention_risk.get("available")),
                last_checked_at=generated_at_iso if execution_log_retention_risk.get("available") else None,
                message=self._execution_log_retention_risk_message(execution_log_retention_risk),
            ),
            "dbSizeRisk": self._project_maintenance_section(
                service="db_size",
                snapshot=db_size_risk,
                configured=bool(db_size_risk.get("available")),
                last_checked_at=generated_at_iso if db_size_risk.get("available") else None,
                message=self._db_size_risk_message(db_size_risk),
            ),
            "adminRoleAssignmentStatus": self._project_maintenance_section(
                service="admin_role_assignment",
                snapshot=admin_role_assignment_status,
                configured=bool(admin_role_assignment_status.get("available")),
                last_checked_at=generated_at_iso if admin_role_assignment_status.get("available") else None,
                message=self._admin_role_assignment_status_message(admin_role_assignment_status),
            ),
            "durableTaskBacklogStatus": self._project_maintenance_section(
                service="durable_task_backlog",
                snapshot=durable_task_backlog_status,
                configured=bool(durable_task_backlog_status.get("available")),
                last_checked_at=generated_at_iso if durable_task_backlog_status.get("available") else None,
                message=self._durable_task_backlog_status_message(durable_task_backlog_status),
            ),
            "recommendedMaintenanceActions": self._recommended_maintenance_actions(
                retention_policy_status=retention_policy_status,
                execution_log_retention_risk=execution_log_retention_risk,
                db_size_risk=db_size_risk,
                admin_role_assignment_status=admin_role_assignment_status,
                durable_task_backlog_status=durable_task_backlog_status,
            ),
            "buildProvenance": build_provenance,
            "launchCockpit": self._safe_launch_cockpit(generated_at_iso),
            "metadata": {
                "contract": "admin_ops_status_snapshot_v2",
                "projection": "bounded_admin_diagnostics",
                "publicLaunchNoGo": True,
                "categories": [
                    "provider_reliability",
                    "quota_cost",
                    "storage",
                    "task_queue",
                    "admin_logs",
                    "runtime_log_sink",
                    "retention_policy",
                    "execution_log_retention",
                    "db_size",
                    "admin_role_assignment",
                    "durable_task_backlog",
                    "build_provenance",
                    "launch_readiness",
                ],
            },
        }

    @classmethod
    def _project_section(
        cls,
        *,
        service: str,
        snapshot: Dict[str, Any],
        configured: bool,
        last_checked_at: str | None,
        message: str,
        include_summary: bool = False,
    ) -> Dict[str, Any]:
        section = cls._section(
            available=bool(snapshot.get("available", False)),
            status=str(snapshot.get("status") or "unavailable"),
            service=service,
            configured=bool(configured),
            lastCheckedAt=last_checked_at,
            message=message,
            label="bounded_admin_diagnostic",
            reasonCode=snapshot.get("reasonCode"),
            dataSources=[],
            summary=dict(snapshot.get("summary") or {}) if include_summary else {},
            limitations=[],
        )
        return section

    @classmethod
    def _project_maintenance_section(
        cls,
        *,
        service: str,
        snapshot: Dict[str, Any],
        configured: bool,
        last_checked_at: str | None,
        message: str,
    ) -> Dict[str, Any]:
        raw_summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
        raw_data_sources = snapshot.get("dataSources") if isinstance(snapshot.get("dataSources"), list) else []
        raw_limitations = snapshot.get("limitations") if isinstance(snapshot.get("limitations"), list) else []
        return cls._section(
            available=bool(snapshot.get("available", False)),
            status=str(snapshot.get("status") or "unavailable"),
            service=service,
            configured=bool(configured),
            lastCheckedAt=last_checked_at,
            message=message,
            label="bounded_admin_maintenance_diagnostic",
            reasonCode=snapshot.get("reasonCode"),
            dataSources=[str(item) for item in raw_data_sources if str(item).strip()],
            summary=dict(raw_summary),
            limitations=[str(item) for item in raw_limitations if str(item).strip()],
        )

    @staticmethod
    def _provider_status_message(snapshot: Dict[str, Any]) -> str:
        status = str(snapshot.get("status") or "unavailable")
        if status == "degraded_observed":
            return "Stored provider reliability snapshot shows degraded observations; provider names, URLs, and payloads are omitted."
        if status == "observed":
            return "Stored provider reliability snapshot available; provider names, URLs, and payloads are omitted."
        if status == "no_evidence":
            return "No stored provider reliability evidence observed yet."
        return "Provider reliability snapshot unavailable."

    @staticmethod
    def _quota_status_message(snapshot: Dict[str, Any]) -> str:
        if snapshot.get("available"):
            return "Quota and cost advisory snapshot available; live enforcement remains disabled."
        return "Quota and cost advisory snapshot unavailable."

    @staticmethod
    def _storage_status_message(snapshot: Dict[str, Any]) -> str:
        if snapshot.get("available"):
            return "Storage readiness session check available; connection details are omitted."
        return "Storage readiness snapshot unavailable."

    @staticmethod
    def _task_queue_status_message(snapshot: Dict[str, Any]) -> str:
        if snapshot.get("available"):
            return "Task queue runtime snapshot available; worker details and warnings are bounded."
        return "Task queue runtime snapshot unavailable."

    @staticmethod
    def _admin_log_status_message(snapshot: Dict[str, Any]) -> str:
        if snapshot.get("available"):
            return "Admin log evidence snapshot available; raw identifiers and file paths are omitted."
        return "Admin log evidence snapshot unavailable."

    @staticmethod
    def _runtime_log_sink_status_message(snapshot: Dict[str, Any]) -> str:
        status = str(snapshot.get("status") or "unavailable")
        if status == "active":
            return "Runtime API file log sink is active; path and log contents are omitted."
        if status == "file_present_not_attached":
            return "Runtime API log file exists, but no matching active file handler was observed."
        if status == "missing":
            return "Runtime API dated file log sink was not observed."
        return "Runtime API file log sink snapshot unavailable."

    @staticmethod
    def _retention_policy_status_message(snapshot: Dict[str, Any]) -> str:
        if snapshot.get("available"):
            return "Retention policy status is advisory; cleanup requires a separate explicit admin action."
        return "Retention policy status unavailable."

    @staticmethod
    def _execution_log_retention_risk_message(snapshot: Dict[str, Any]) -> str:
        if snapshot.get("available"):
            return "Execution log retention risk is summarized with bucketed counts; raw log rows are omitted."
        return "Execution log retention risk unavailable."

    @staticmethod
    def _db_size_risk_message(snapshot: Dict[str, Any]) -> str:
        if snapshot.get("available"):
            return "Database size risk is summarized without exposing the database path."
        return "Database size risk unavailable."

    @staticmethod
    def _admin_role_assignment_status_message(snapshot: Dict[str, Any]) -> str:
        if snapshot.get("available"):
            return "Admin role assignment status is summarized without user identifiers or credentials."
        return "Admin role assignment status unavailable."

    @staticmethod
    def _durable_task_backlog_status_message(snapshot: Dict[str, Any]) -> str:
        if snapshot.get("available"):
            return "Durable task backlog status is summarized with bucketed counts; task identifiers are omitted."
        return "Durable task backlog status unavailable."

    def _safe_launch_cockpit(self, generated_at: str) -> Dict[str, Any]:
        try:
            raw = self._build_launch_cockpit()
        except Exception:
            return self._fallback_launch_cockpit()
        return self._project_launch_cockpit(raw, generated_at=generated_at)

    @staticmethod
    def _safe_build_provenance(app_state: object | None) -> Dict[str, Any]:
        try:
            return BuildProvenanceService().build(app_state=app_state)
        except Exception:
            return build_unknown_provenance(reason_code="build_provenance_unavailable")

    def _project_launch_cockpit(self, snapshot: Dict[str, Any], *, generated_at: str) -> Dict[str, Any]:
        raw_domains = [
            item
            for item in list(snapshot.get("domains") or [])
            if isinstance(item, dict)
        ]
        ranked_domains = self._rank_launch_cockpit_domains(raw_domains)
        projected_domains = [
            self._project_launch_cockpit_domain(item)
            for item in ranked_domains
        ]
        priority_counts = self._launch_cockpit_priority_counts(projected_domains)
        summary_counts = dict(snapshot.get("summaryCounts") or {})
        summary_counts.update(priority_counts)
        return {
            "contract": str(snapshot.get("contract") or "admin_ops_launch_cockpit_v1"),
            "status": "no_go" if bool(snapshot.get("publicLaunchNoGo", True)) else "advisory",
            "lastCheckedAt": generated_at,
            "message": "Private beta launch readiness snapshot is advisory only; detailed evidence references are omitted.",
            "readOnly": True,
            "advisoryOnly": True,
            "noExternalCalls": True,
            "publicLaunchApproved": bool(snapshot.get("publicLaunchApproved", False)),
            "publicLaunchNoGo": bool(snapshot.get("publicLaunchNoGo", True)),
            "liveEnforcement": False,
            "runtimeBehaviorChanged": False,
            "approvalRequired": bool(snapshot.get("approvalRequired", True)),
            "summaryCounts": summary_counts,
            "unsafeActionStates": {
                str(key): bool(value)
                for key, value in dict(snapshot.get("unsafeActionStates") or {}).items()
            },
            "domains": projected_domains,
            "recommendedMaintenanceQueue": [
                self._project_launch_cockpit_queue_item(item)
                for item in projected_domains
            ],
            "blockers": [
                self._project_launch_cockpit_blocker(item)
                for item in list(snapshot.get("blockers") or [])
                if isinstance(item, dict)
            ],
            "safeNextActions": self._sanitize_messages(
                snapshot.get("safeNextActions"),
                fallback=["Review bounded admin evidence and keep public launch blocked."],
            ),
            "limitations": ["bounded_admin_projection", "no_raw_internal_references"],
            "prioritySummary": priority_counts,
        }

    def _fallback_launch_cockpit(self) -> Dict[str, Any]:
        return {
            "contract": "admin_ops_launch_cockpit_v1",
            "status": "unavailable",
            "lastCheckedAt": None,
            "message": "Admin launch readiness snapshot unavailable.",
            "readOnly": True,
            "advisoryOnly": True,
            "noExternalCalls": True,
            "publicLaunchApproved": False,
            "publicLaunchNoGo": True,
            "liveEnforcement": False,
            "runtimeBehaviorChanged": False,
            "approvalRequired": True,
            "summaryCounts": {},
            "unsafeActionStates": {},
            "domains": [],
            "recommendedMaintenanceQueue": [],
            "blockers": [
                {
                    "blockerKey": "public_launch_no_go",
                    "title": "Public launch remains NO-GO",
                    "severity": "critical",
                    "publicLaunchNoGo": True,
                    "approvalRequired": True,
                    "affectedDomains": [],
                    "evidenceRefs": [],
                    "nextAction": "Use existing admin evidence surfaces until the bounded snapshot is available.",
                }
            ],
            "safeNextActions": ["Use existing admin evidence surfaces until the bounded snapshot is available."],
            "limitations": ["bounded_snapshot_unavailable"],
            "prioritySummary": {},
        }

    def _project_launch_cockpit_domain(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "domainKey": str(snapshot.get("domainKey") or ""),
            "label": str(snapshot.get("label") or ""),
            "status": str(snapshot.get("status") or "unknown"),
            "statusLabel": self._safe_message(
                snapshot.get("statusLabel"),
                fallback="Read-only bounded admin diagnostic.",
            ),
            "detailRoute": self._safe_internal_route(snapshot.get("detailRoute")),
            "foundationLanded": bool(snapshot.get("foundationLanded")),
            "evidenceToolingPresent": bool(snapshot.get("evidenceToolingPresent")),
            "realOperatorEvidenceMissing": bool(snapshot.get("realOperatorEvidenceMissing", True)),
            "approvalRequired": bool(snapshot.get("approvalRequired", True)),
            "publicLaunchNoGo": bool(snapshot.get("publicLaunchNoGo", True)),
            "readOnly": True,
            "advisoryOnly": True,
            "noExternalCalls": True,
            "liveEnforcement": False,
            "runtimeBehaviorChanged": False,
            "providerRuntimeChanged": bool(snapshot.get("providerRuntimeChanged", False)),
            "externalActionsEnabled": False,
            "evidenceRefs": [],
            "blockerRefs": [],
            "safeNextActions": self._sanitize_messages(snapshot.get("safeNextActions")),
            "limitations": [],
            "priorityRank": int(snapshot.get("priorityRank") or 0),
            "priorityTier": str(snapshot.get("priorityTier") or "watch"),
            "impactLevel": str(snapshot.get("impactLevel") or "low"),
            "recommendedNextAction": self._safe_message(
                snapshot.get("recommendedNextAction"),
                fallback="Review bounded admin evidence before changing launch posture.",
            ),
            "blockingReasonSummary": self._safe_message(
                snapshot.get("blockingReasonSummary"),
                fallback="Bounded admin evidence remains incomplete for launch review.",
            ),
            "ownerSurface": str(snapshot.get("ownerSurface") or "admin_maintenance"),
            "remediationSurface": self._safe_internal_route(snapshot.get("remediationSurface") or snapshot.get("detailRoute")),
            "followUpProposals": [],
        }

    def _rank_launch_cockpit_domains(self, domains: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        ranked_domains: list[Dict[str, Any]] = []
        for domain in domains:
            domain_key = str(domain.get("domainKey") or "")
            profile = self._LAUNCH_COCKPIT_PRIORITY_PROFILES.get(domain_key, {})
            sort_order = int(profile.get("sortOrder") or 1000)
            ranked_domain = dict(domain)
            ranked_domain.update(
                {
                    "prioritySortOrder": sort_order,
                    "priorityTier": profile.get("priorityTier", "watch"),
                    "impactLevel": profile.get("impactLevel", "low"),
                    "recommendedNextAction": profile.get(
                        "recommendedNextAction",
                        "Review bounded admin evidence before changing launch posture.",
                    ),
                    "blockingReasonSummary": profile.get(
                        "blockingReasonSummary",
                        "Bounded admin evidence remains incomplete for launch review.",
                    ),
                    "ownerSurface": profile.get("ownerSurface", "admin_maintenance"),
                    "remediationSurface": profile.get(
                        "remediationSurface",
                        domain.get("detailRoute") or "/admin",
                    ),
                }
            )
            ranked_domains.append(ranked_domain)

        ranked_domains.sort(
            key=lambda item: (
                int(item.get("prioritySortOrder") or 1000),
                str(item.get("domainKey") or ""),
            )
        )
        for rank, domain in enumerate(ranked_domains, start=1):
            domain["priorityRank"] = rank
        return ranked_domains

    @staticmethod
    def _launch_cockpit_priority_counts(domains: list[Dict[str, Any]]) -> Dict[str, int]:
        counts = {
            "criticalPriorityCount": 0,
            "highPriorityCount": 0,
            "mediumPriorityCount": 0,
            "watchPriorityCount": 0,
        }
        for domain in domains:
            tier = str(domain.get("priorityTier") or "watch")
            if tier == "critical":
                counts["criticalPriorityCount"] += 1
            elif tier == "high":
                counts["highPriorityCount"] += 1
            elif tier == "medium":
                counts["mediumPriorityCount"] += 1
            else:
                counts["watchPriorityCount"] += 1
        return counts

    def _project_launch_cockpit_queue_item(self, domain: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "domainKey": str(domain.get("domainKey") or ""),
            "label": str(domain.get("label") or ""),
            "status": str(domain.get("status") or "unknown"),
            "priorityRank": int(domain.get("priorityRank") or 0),
            "priorityTier": str(domain.get("priorityTier") or "watch"),
            "impactLevel": str(domain.get("impactLevel") or "low"),
            "recommendedNextAction": self._safe_message(
                domain.get("recommendedNextAction"),
                fallback="Review bounded admin evidence before changing launch posture.",
            ),
            "blockingReasonSummary": self._safe_message(
                domain.get("blockingReasonSummary"),
                fallback="Bounded admin evidence remains incomplete for launch review.",
            ),
            "ownerSurface": str(domain.get("ownerSurface") or "admin_maintenance"),
            "remediationSurface": self._safe_internal_route(domain.get("remediationSurface") or domain.get("detailRoute")),
        }

    def _project_launch_cockpit_blocker(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        affected_domains = snapshot.get("affectedDomains")
        return {
            "blockerKey": str(snapshot.get("blockerKey") or ""),
            "title": self._safe_message(snapshot.get("title"), fallback="Admin launch blocker"),
            "severity": str(snapshot.get("severity") or "high"),
            "publicLaunchNoGo": bool(snapshot.get("publicLaunchNoGo", True)),
            "approvalRequired": bool(snapshot.get("approvalRequired", True)),
            "affectedDomains": [
                str(item)
                for item in list(affected_domains or [])
                if str(item).strip()
            ],
            "evidenceRefs": [],
            "nextAction": self._safe_message(
                snapshot.get("nextAction"),
                fallback="Review bounded admin evidence before changing launch posture.",
            ),
        }

    def _sanitize_messages(self, values: Any, *, fallback: list[str] | None = None) -> list[str]:
        items: list[str] = []
        for value in list(values or []):
            safe_value = self._safe_message(value, fallback="")
            if safe_value and safe_value not in items:
                items.append(safe_value)
        if items:
            return items
        return list(fallback or [])

    def _safe_message(self, value: Any, *, fallback: str) -> str:
        text = str(value or "").strip()
        if not text or self._looks_sensitive_text(text):
            return fallback
        return text

    def _looks_sensitive_text(self, value: str) -> bool:
        text = str(value or "").strip().lower()
        if not text:
            return False
        return any(marker in text for marker in self._SENSITIVE_TEXT_MARKERS)

    @staticmethod
    def _safe_internal_route(value: Any) -> str:
        route = str(value or "").strip()
        if route.startswith("/admin/"):
            return route
        return "/admin"

    def _safe_source(self, builder: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
        try:
            return builder()
        except Exception:
            return self._section(
                available=False,
                status="unavailable",
                reasonCode="source_unavailable",
                limitations=["source_unavailable"],
            )

    @classmethod
    def _section(cls, **overrides: Any) -> Dict[str, Any]:
        section = {
            "available": False,
            "status": "unavailable",
            "service": "",
            "configured": False,
            "lastCheckedAt": None,
            "message": "",
            "label": "advisory",
            "reasonCode": None,
            "readOnly": True,
            "noExternalCalls": True,
            "advisoryOnly": True,
            "liveEnforcement": False,
            "enforcementEnabled": False,
            "runtimeBehaviorChanged": False,
            "consumerVisible": False,
            "providerBehaviorChanged": False,
            "marketCacheBehaviorChanged": False,
            "deleteAllowed": False,
            "dataSources": [],
            "summary": {},
            "limitations": [],
        }
        section.update(overrides)
        return section

    @classmethod
    def _project_runtime_log_sink_section(
        cls,
        *,
        snapshot: Dict[str, Any],
        last_checked_at: str,
    ) -> Dict[str, Any]:
        summary = dict(snapshot.get("summary") or {})
        return cls._section(
            available=bool(snapshot.get("available", False)),
            status=str(snapshot.get("status") or "unavailable"),
            service="runtime_log_sink",
            configured=snapshot.get("status") == "active",
            lastCheckedAt=last_checked_at,
            message=cls._runtime_log_sink_status_message(snapshot),
            label="bounded_admin_diagnostic",
            reasonCode=snapshot.get("reasonCode"),
            dataSources=[],
            summary={
                "logPrefix": str(summary.get("logPrefix") or ""),
                "fileName": str(summary.get("fileName") or ""),
                "date": str(summary.get("date") or ""),
                "fileExists": bool(summary.get("fileExists", False)),
                "handlerAttached": bool(summary.get("handlerAttached", False)),
                "alreadyConfigured": bool(summary.get("alreadyConfigured", False)),
                "pathIncluded": False,
                "contentsIncluded": False,
                "sensitiveValuesIncluded": False,
            },
            limitations=["file_metadata_only", "no_log_content_read", "absolute_path_omitted"],
        )

    @staticmethod
    def _count_bucket(value: int) -> str:
        count = max(0, int(value or 0))
        if count == 0:
            return "0"
        if count == 1:
            return "1"
        if count <= 10:
            return "2-10"
        if count <= 100:
            return "11-100"
        if count <= 1000:
            return "101-1000"
        return "1000+"

    @staticmethod
    def _maintenance_count_bucket(value: int) -> str:
        count = max(0, int(value or 0))
        if count == 0:
            return "0"
        if count <= 9:
            return "1-9"
        if count <= 100:
            return "10-100"
        if count <= 1000:
            return "101-1000"
        return "1000+"

    @staticmethod
    def _size_bucket(value: int | None) -> str:
        if value is None:
            return "unavailable"
        size = max(0, int(value))
        mb = 1024 * 1024
        gb = 1024 * mb
        if size == 0:
            return "0"
        if size < 64 * mb:
            return "under_64mb"
        if size < 256 * mb:
            return "64mb_to_256mb"
        if size < 512 * mb:
            return "256mb_to_512mb"
        if size < gb:
            return "512mb_to_1gb"
        if size < 5 * gb:
            return "1gb_to_5gb"
        return "5gb_plus"

    @staticmethod
    def _unique_actions(values: list[str]) -> list[str]:
        actions: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in actions:
                actions.append(text)
        return actions

    @staticmethod
    def _pending_task_statuses() -> tuple[str, ...]:
        return ("pending", "queued", "processing", "running", "waiting_retry")

    def _build_retention_policy_status(self) -> Dict[str, Any]:
        policy = AdminLogsRetentionService._policy()
        return self._section(
            available=True,
            status="partial_policy",
            dataSources=["admin_log_retention_policy", "db_retention_backup_restore_plan"],
            summary={
                "executionLogPolicy": "preview_first_retention_cleanup",
                "executionLogRetentionDays": int(policy.retention_days),
                "executionLogMinimumRetentionDays": int(policy.min_retention_days),
                "durableTaskRetentionPolicy": "not_configured",
                "adminRoleAssignmentRetentionPolicy": "not_applicable",
                "cleanupCalled": False,
                "migrationRun": False,
                "deleteAllowed": False,
            },
            limitations=[
                "execution_log_cleanup_requires_separate_write_capability",
                "durable_task_lifecycle_retention_not_configured",
                "admin_role_assignment_audit_is_status_only",
            ],
        )

    def _build_execution_log_retention_risk(self) -> Dict[str, Any]:
        db = DatabaseManager.get_instance()
        policy = AdminLogsRetentionService._policy()
        retention_cutoff = datetime.now() - timedelta(days=policy.retention_days)
        with db.get_session() as session:
            total_logs = int(session.execute(select(func.count(ExecutionLogSession.id))).scalar() or 0)
            total_events = int(session.execute(select(func.count(ExecutionLogEvent.id))).scalar() or 0)
            older_than_retention = int(
                session.execute(
                    select(func.count(ExecutionLogSession.id)).where(
                        ExecutionLogSession.started_at < retention_cutoff
                    )
                ).scalar()
                or 0
            )
            oldest = session.execute(select(func.min(ExecutionLogSession.started_at))).scalar()

        status = "warning" if older_than_retention > 0 or total_logs >= policy.warning_threshold_count else "ok"
        if total_logs >= policy.critical_threshold_count:
            status = "critical"
        return self._section(
            available=True,
            status=status,
            dataSources=["execution_log_sessions", "execution_log_events", "admin_log_retention_policy"],
            summary={
                "sessionCountBucket": self._maintenance_count_bucket(total_logs),
                "eventCountBucket": self._maintenance_count_bucket(total_events),
                "logsOlderThanRetentionCountBucket": self._maintenance_count_bucket(older_than_retention),
                "oldestLogPresent": oldest is not None,
                "retentionDays": int(policy.retention_days),
                "cleanupCalled": False,
                "deleteAllowed": False,
                "rawRowsIncluded": False,
            },
            limitations=["bounded_counts_only", "no_log_row_payloads", "cleanup_requires_separate_write_capability"],
        )

    def _build_db_size_risk(self) -> Dict[str, Any]:
        policy = AdminLogsRetentionService._policy()
        measurement = AdminLogsRetentionService()._storage_measurement()
        storage_bytes = measurement.get("size_bytes")
        size_value = int(storage_bytes) if storage_bytes is not None else None
        over_hard = bool(size_value is not None and size_value >= policy.storage_hard_limit_bytes)
        over_soft = bool(size_value is not None and size_value >= policy.storage_soft_limit_bytes)
        measurement_status = str(measurement.get("measurement_status") or "unavailable")
        if over_hard:
            status = "critical"
        elif over_soft or measurement_status != "available":
            status = "warning"
        else:
            status = "ok"
        return self._section(
            available=True,
            status=status,
            reasonCode=None if measurement_status == "available" else "db_size_measurement_unavailable",
            dataSources=["database_storage_measurement"],
            summary={
                "measurementStatus": measurement_status,
                "measurementScope": str(measurement.get("measurement_scope") or "unavailable"),
                "sizeBucket": self._size_bucket(size_value),
                "overSoftLimit": over_soft,
                "overHardLimit": over_hard,
                "softLimitBucket": self._size_bucket(policy.storage_soft_limit_bytes),
                "hardLimitBucket": self._size_bucket(policy.storage_hard_limit_bytes),
                "databasePathIncluded": False,
                "measurementReasonIncluded": False,
            },
            limitations=["no_database_path", "bounded_size_bucket_only", "no_vacuum_or_cleanup"],
        )

    def _build_admin_role_assignment_status(self) -> Dict[str, Any]:
        db = DatabaseManager.get_instance()
        with db.get_session() as session:
            role_count = int(session.execute(select(func.count(AdminRole.role_key))).scalar() or 0)
            capability_count = int(session.execute(select(func.count(AdminRoleCapability.id))).scalar() or 0)
            assignment_count = int(session.execute(select(func.count(AdminUserRole.id))).scalar() or 0)
            legacy_admin_count = int(
                session.execute(
                    select(func.count(AppUser.id)).where(
                        AppUser.role == "admin",
                        AppUser.is_active.is_(True),
                    )
                ).scalar()
                or 0
            )

        if assignment_count == 0 and legacy_admin_count > 0:
            status = "legacy_admin_fallback_active"
        elif assignment_count > 0:
            status = "explicit_assignments_present"
        else:
            status = "no_admin_assignments_observed"
        return self._section(
            available=True,
            status=status,
            dataSources=["admin_roles", "admin_role_capabilities", "admin_user_roles", "app_users"],
            summary={
                "adminRoleCountBucket": self._maintenance_count_bucket(role_count),
                "adminCapabilityCountBucket": self._maintenance_count_bucket(capability_count),
                "explicitAssignmentCountBucket": self._maintenance_count_bucket(assignment_count),
                "legacyAdminUserCountBucket": self._maintenance_count_bucket(legacy_admin_count),
                "coarseFallbackObserved": assignment_count == 0 and legacy_admin_count > 0,
                "accessBehaviorChanged": False,
                "userIdentifiersIncluded": False,
                "credentialsIncluded": False,
            },
            limitations=["compatibility_status_only", "does_not_assign_roles", "does_not_change_auth_or_rbac_enforcement"],
        )

    def _build_durable_task_backlog_status(self) -> Dict[str, Any]:
        db = DatabaseManager.get_instance()
        pending_statuses = self._pending_task_statuses()
        with db.get_session() as session:
            total_tasks = int(session.execute(select(func.count(DurableTaskState.id))).scalar() or 0)
            pending_count = int(
                session.execute(
                    select(func.count(DurableTaskState.id)).where(
                        DurableTaskState.status.in_(pending_statuses)
                    )
                ).scalar()
                or 0
            )
            oldest_pending = session.execute(
                select(func.min(DurableTaskState.created_at)).where(
                    DurableTaskState.status.in_(pending_statuses)
                )
            ).scalar()

        status = "warning" if pending_count > 0 else "ok"
        if pending_count >= 1000:
            status = "critical"
        return self._section(
            available=True,
            status=status,
            dataSources=["durable_task_states"],
            summary={
                "totalTaskCountBucket": self._maintenance_count_bucket(total_tasks),
                "pendingBacklogCountBucket": self._maintenance_count_bucket(pending_count),
                "oldestPendingPresent": oldest_pending is not None,
                "retentionPolicy": "not_configured",
                "cleanupCalled": False,
                "taskIdentifiersIncluded": False,
                "ownerIdentifiersIncluded": False,
            },
            limitations=["bounded_counts_only", "does_not_claim_or_repair_tasks", "no_task_cleanup"],
        )

    def _recommended_maintenance_actions(
        self,
        *,
        retention_policy_status: Dict[str, Any],
        execution_log_retention_risk: Dict[str, Any],
        db_size_risk: Dict[str, Any],
        admin_role_assignment_status: Dict[str, Any],
        durable_task_backlog_status: Dict[str, Any],
    ) -> list[str]:
        actions: list[str] = [
            "Review DB retention policy acceptance before enabling any cleanup job.",
        ]
        if execution_log_retention_risk.get("status") in {"warning", "critical"}:
            actions.append("Use the existing admin log cleanup preview before any explicit delete action.")
        if db_size_risk.get("status") in {"warning", "critical"}:
            actions.append("Plan a storage capacity review with backup/restore evidence before cleanup.")
        if admin_role_assignment_status.get("status") == "legacy_admin_fallback_active":
            actions.append("Record an admin role assignment migration plan before changing RBAC enforcement.")
        if durable_task_backlog_status.get("status") in {"warning", "critical"}:
            actions.append("Investigate durable task backlog health before adding retention or repair jobs.")
        if retention_policy_status.get("status") != "ok":
            actions.append("Keep retention diagnostics advisory until operator approval is captured.")
        return self._unique_actions(actions)

    def _build_provider_status_summary(self) -> Dict[str, Any]:
        db = DatabaseManager.get_instance()
        with db.get_session() as session:
            state_count = int(session.execute(select(func.count(ProviderCircuitState.id))).scalar() or 0)
            degraded_state_count = int(
                session.execute(
                    select(func.count(ProviderCircuitState.id)).where(
                        ProviderCircuitState.state.not_in(tuple(self._HEALTHY_PROVIDER_STATES))
                    )
                ).scalar()
                or 0
            )
            event_count = int(session.execute(select(func.count(ProviderCircuitEvent.id))).scalar() or 0)
            quota_window_count = int(session.execute(select(func.count(ProviderQuotaWindow.id))).scalar() or 0)
            probe_event_count = int(session.execute(select(func.count(ProviderProbeEvent.id))).scalar() or 0)

        status = "no_evidence"
        if degraded_state_count > 0:
            status = "degraded_observed"
        elif state_count or event_count or quota_window_count or probe_event_count:
            status = "observed"

        return self._section(
            available=True,
            status=status,
            dataSources=[
                "provider_circuit_states",
                "provider_circuit_events",
                "provider_quota_windows",
                "provider_probe_events",
            ],
            summary={
                "stateCountBucket": self._count_bucket(state_count),
                "degradedStateCountBucket": self._count_bucket(degraded_state_count),
                "eventCountBucket": self._count_bucket(event_count),
                "quotaWindowCountBucket": self._count_bucket(quota_window_count),
                "probeEventCountBucket": self._count_bucket(probe_event_count),
                "providerPayloadsIncluded": False,
                "providerNamesIncluded": False,
            },
            limitations=["diagnostic_storage_only", "no_live_provider_checks"],
        )

    def _build_quota_cost_advisory_status_summary(self, generated_at: datetime) -> Dict[str, Any]:
        quota_service = QuotaPolicyService(enforcement_enabled=False, global_kill_switch=False)
        shadow = quota_service.classify_shadow_preflight(
            owner_user_id=None,
            route_family="analysis",
            estimated_units=1,
            pricing_status="ok",
            now=generated_at,
        )
        pilot = quota_service.classify_pilot_readiness_preflight(
            owner_user_id=None,
            route_family="analysis",
            estimated_units=1,
            pricing_status="ok",
            pilot_enforcement_enabled=False,
            owner_authenticated=False,
            owner_transitional=False,
            auth_enabled=True,
            now=generated_at,
        )

        ledger_total = {}
        try:
            ledger_summary = LlmCostLedgerService().get_summary(
                from_dt=generated_at - timedelta(hours=24),
                to_dt=generated_at,
                limit=1,
            )
            total = ledger_summary.get("total") if isinstance(ledger_summary, dict) else {}
            ledger_total = {
                "callsBucket": self._count_bucket(int((total or {}).get("calls") or 0)),
                "totalTokensBucket": self._count_bucket(int((total or {}).get("total_tokens") or 0)),
                "totalCostObserved": str((total or {}).get("total_cost_usd") or "0"),
            }
        except Exception:
            ledger_total = {"available": False, "status": "unavailable"}

        return self._section(
            available=True,
            status=pilot.state,
            dataSources=["quota_policy_readiness_helpers", "llm_cost_ledger_summary"],
            summary={
                "quotaMode": "advisory",
                "quotaShadowState": shadow.state,
                "quotaShadowWouldBlock": bool(shadow.would_block),
                "pilotState": pilot.state,
                "pilotReasonCode": pilot.reason_code,
                "requestBlocked": False,
                "reservationCreated": False,
                "reserveConsumeReleaseCalled": False,
                "ledgerTotal24h": ledger_total,
            },
            limitations=["not_live_route_boundary_enforcement", "invoice_reconciliation_not_enforcement_input"],
        )

    def _build_storage_readiness_summary(self) -> Dict[str, Any]:
        db = DatabaseManager.get_instance()
        with db.get_session() as session:
            session.execute(text("SELECT 1"))

        return self._section(
            available=True,
            status="ok",
            dataSources=["database_session_check"],
            summary={
                "sessionCheck": "ok",
                "schemaMutation": False,
                "cleanupMutation": False,
                "migrationRun": False,
            },
            limitations=["storage_session_check_only"],
        )

    def _build_task_queue_status_summary(self, app_state: object | None) -> Dict[str, Any]:
        queue = getattr(app_state, "task_queue", None) if app_state is not None else None
        if queue is None:
            return self._section(
                available=False,
                status="unavailable",
                reasonCode="task_queue_runtime_unavailable",
                dataSources=["task_queue_runtime_status"],
                limitations=["task_queue_not_initialized_on_app_state"],
            )

        runtime = queue.get_runtime_status()
        topology_ok = bool(runtime.get("topology_ok", True))
        shutdown = bool(runtime.get("shutdown", False))
        status = "ok" if topology_ok and not shutdown else "not_ready"
        warning_code = "process_local_sse_topology_warning" if runtime.get("warning") else None

        return self._section(
            available=True,
            status=status,
            reasonCode=warning_code,
            dataSources=["task_queue_runtime_status"],
            summary={
                "mode": str(runtime.get("mode") or "unknown"),
                "singleProcessRequired": bool(runtime.get("single_process_required", True)),
                "configuredWorkerCount": int(runtime.get("configured_worker_count") or 0),
                "topologyOk": topology_ok,
                "shutdown": shutdown,
                "acceptingNewTasks": bool(runtime.get("accepting_new_tasks", False)),
                "launchStatus": str(runtime.get("launch_status") or "unknown"),
                "warningTextIncluded": False,
            },
            limitations=["process_local_status_only", "does_not_create_or_activate_queue"],
        )

    def _build_admin_log_evidence_summary(self) -> Dict[str, Any]:
        db = DatabaseManager.get_instance()
        policy = AdminLogsRetentionService._policy()
        with db.get_session() as session:
            total_logs = int(session.execute(select(func.count(ExecutionLogSession.id))).scalar() or 0)
            total_events = int(session.execute(select(func.count(ExecutionLogEvent.id))).scalar() or 0)
            oldest = session.execute(select(func.min(ExecutionLogSession.started_at))).scalar()
            newest = session.execute(select(func.max(ExecutionLogSession.started_at))).scalar()

        measurement = AdminLogsRetentionService()._storage_measurement()
        measurement_status = str(measurement.get("measurement_status") or "unavailable")
        status = "ok"
        if total_logs >= int(policy.critical_threshold_count):
            status = "critical"
        elif total_logs >= int(policy.warning_threshold_count) or measurement_status != "available":
            status = "warning"

        return self._section(
            available=True,
            status=status,
            dataSources=["execution_log_sessions", "execution_log_events", "admin_log_retention_policy"],
            summary={
                "sessionCountBucket": self._count_bucket(total_logs),
                "eventCountBucket": self._count_bucket(total_events),
                "oldestLogPresent": oldest is not None,
                "newestLogPresent": newest is not None,
                "retentionDays": int(policy.retention_days),
                "minimumRetentionDays": int(policy.min_retention_days),
                "storageMeasurementStatus": measurement_status,
                "notificationEmitted": False,
                "cleanupCalled": False,
            },
            limitations=["admin_log_evidence_only", "cleanup_requires_separate_write_capability"],
        )

    def _build_runtime_log_sink_summary(self) -> Dict[str, Any]:
        try:
            from src.config import get_config

            log_dir = str(get_config().log_dir or "./logs")
        except Exception:
            log_dir = "./logs"
        sink = describe_runtime_file_logging(log_prefix="api_server", log_dir=log_dir)
        status = str(sink.get("status") or "unavailable")
        return self._section(
            available=status in {"active", "file_present_not_attached", "missing"},
            status=status,
            reasonCode=sink.get("reasonCode"),
            dataSources=["python_logging_handlers", "dated_runtime_log_file_metadata"],
            summary={
                "logPrefix": str(sink.get("logPrefix") or "api_server"),
                "fileName": str(sink.get("fileName") or ""),
                "date": str(sink.get("date") or ""),
                "fileExists": bool(sink.get("fileExists", False)),
                "handlerAttached": status == "active",
                "alreadyConfigured": bool(sink.get("alreadyConfigured", False)),
                "pathIncluded": False,
                "contentsIncluded": False,
                "sensitiveValuesIncluded": False,
            },
            limitations=["file_metadata_only", "no_log_content_read", "absolute_path_omitted"],
        )

    @staticmethod
    def _follow_up(
        *,
        proposal_key: str,
        title: str,
        likely_files: list[str],
        risk: str,
        validation: list[str],
    ) -> Dict[str, Any]:
        return {
            "proposalKey": proposal_key,
            "title": title,
            "approvalNeeded": True,
            "likelyFiles": likely_files,
            "risk": risk,
            "validation": validation,
        }

    @staticmethod
    def _cockpit_domain(
        *,
        domain_key: str,
        label: str,
        status: str,
        status_label: str,
        detail_route: str,
        foundation_landed: bool,
        evidence_tooling_present: bool,
        real_operator_evidence_missing: bool,
        evidence_refs: list[str],
        blocker_refs: list[str],
        safe_next_actions: list[str],
        limitations: list[str],
        follow_up_proposals: list[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        return {
            "domainKey": domain_key,
            "label": label,
            "status": status,
            "statusLabel": status_label,
            "detailRoute": detail_route,
            "foundationLanded": foundation_landed,
            "evidenceToolingPresent": evidence_tooling_present,
            "realOperatorEvidenceMissing": real_operator_evidence_missing,
            "approvalRequired": True,
            "publicLaunchNoGo": True,
            "readOnly": True,
            "advisoryOnly": True,
            "noExternalCalls": True,
            "liveEnforcement": False,
            "runtimeBehaviorChanged": False,
            "providerRuntimeChanged": False,
            "externalActionsEnabled": False,
            "evidenceRefs": evidence_refs,
            "blockerRefs": blocker_refs,
            "safeNextActions": safe_next_actions,
            "limitations": limitations,
            "followUpProposals": follow_up_proposals or [],
        }

    def _build_launch_cockpit(self) -> Dict[str, Any]:
        domains = [
            self._cockpit_domain(
                domain_key="security_rbac_mfa",
                label="Security / RBAC / MFA",
                status="approval_required_no_go",
                status_label="Foundation and tooling present; staged operator evidence missing",
                detail_route="/admin/users",
                foundation_landed=True,
                evidence_tooling_present=True,
                real_operator_evidence_missing=True,
                evidence_refs=[
                    "scripts/admin_rbac_route_inventory.py",
                    "scripts/security_mfa_operator_evidence_check.py",
                    "tests/api/test_auth_rbac_release_contracts.py",
                    "tests/test_security_mfa_operator_evidence_check.py",
                ],
                blocker_refs=[
                    "docs/audits/public-launch-gap-register.md#securityrbac",
                    "docs/audits/index-security-rbac-mfa.md",
                ],
                safe_next_actions=[
                    "Review route inventory and sanitized MFA/RBAC operator evidence.",
                    "Keep MFA enforcement and RBAC fallback changes behind separate approval.",
                ],
                limitations=[
                    "real_staged_mfa_pilot_evidence_missing",
                    "rbac_fallback_disable_not_approved",
                ],
                follow_up_proposals=[
                    self._follow_up(
                        proposal_key="security_rbac_operator_acceptance",
                        title="Run staged MFA/RBAC acceptance with sanitized operator artifacts",
                        likely_files=[
                            "scripts/security_mfa_operator_evidence_check.py",
                            "scripts/admin_rbac_route_inventory.py",
                            "tests/api/test_auth_rbac_release_contracts.py",
                        ],
                        risk="admin_access_lockout_or_overbroad_admin_access",
                        validation=[
                            "focused auth/RBAC API tests",
                            "sanitized operator evidence validator",
                            "route inventory review",
                        ],
                    ),
                ],
            ),
            self._cockpit_domain(
                domain_key="quota_cost",
                label="Quota / Cost",
                status="advisory_no_go",
                status_label="Advisory helpers present; live quota enforcement not approved",
                detail_route="/admin/cost-observability",
                foundation_landed=True,
                evidence_tooling_present=True,
                real_operator_evidence_missing=True,
                evidence_refs=[
                    "src/services/quota_policy_service.py",
                    "scripts/quota_reserve_release_operator_evidence_check.py",
                    "tests/test_quota_policy_service.py",
                    "tests/test_quota_reserve_release_operator_evidence_check.py",
                ],
                blocker_refs=[
                    "docs/audits/public-launch-gap-register.md#costquota",
                    "docs/audits/quota-reserve-release-operator-evidence-checklist.md",
                ],
                safe_next_actions=[
                    "Inspect cost observability and quota evidence without creating reservations.",
                    "Keep route-boundary live blocking out of this cockpit.",
                ],
                limitations=[
                    "live_route_enforcement_missing",
                    "real_budget_operator_evidence_missing",
                ],
                follow_up_proposals=[
                    self._follow_up(
                        proposal_key="quota_route_pilot_approval",
                        title="Pilot one low-risk quota route only after explicit approval",
                        likely_files=[
                            "api/v1/endpoints/analysis.py",
                            "src/services/quota_policy_service.py",
                            "tests/api/test_analysis_quota_route_pilot.py",
                        ],
                        risk="public_usage_without_hard_spend_caps",
                        validation=[
                            "reserve/release lifecycle tests",
                            "rollback flag proof",
                            "sanitized quota operator artifact",
                        ],
                    ),
                ],
            ),
            self._cockpit_domain(
                domain_key="provider_reliability",
                label="Provider Reliability",
                status="diagnostic_no_go",
                status_label="Diagnostics present; provider runtime enforcement not approved",
                detail_route="/admin/provider-circuits",
                foundation_landed=True,
                evidence_tooling_present=True,
                real_operator_evidence_missing=True,
                evidence_refs=[
                    "src/services/provider_circuit_observer.py",
                    "scripts/provider_sla_licensing_evidence_check.py",
                    "scripts/provider_operator_evidence_check.py",
                    "tests/api/test_admin_provider_circuit_diagnostics.py",
                ],
                blocker_refs=[
                    "docs/audits/public-launch-gap-register.md#provider-reliability",
                    "docs/audits/index-provider-data-options.md",
                ],
                safe_next_actions=[
                    "Review provider SLA diagnostics and licensing evidence status.",
                    "Keep provider order, fallback, retry, timeout, and cache behavior unchanged.",
                ],
                limitations=[
                    "real_entitlement_evidence_missing",
                    "provider_circuit_enforcement_pilot_not_approved",
                ],
            ),
            self._cockpit_domain(
                domain_key="storage_restore",
                label="Storage / Restore",
                status="tooling_no_go",
                status_label="Readiness helpers present; real restore/PITR evidence missing",
                detail_route="/admin/evidence-workflow",
                foundation_landed=True,
                evidence_tooling_present=True,
                real_operator_evidence_missing=True,
                evidence_refs=[
                    "scripts/storage_migration_readiness_report.py",
                    "scripts/isolated_pg_restore_smoke.py",
                    "scripts/restore_pitr_operator_evidence_check.py",
                    "docs/audits/storage-migration-readiness.md",
                ],
                blocker_refs=[
                    "docs/audits/public-launch-gap-register.md#dbdeployment",
                    "docs/audits/index-db-ws2-deployment.md",
                ],
                safe_next_actions=[
                    "Review report-only storage readiness and restore evidence requirements.",
                    "Do not run restore, PITR, migrations, cleanup, or deletion from cockpit.",
                ],
                limitations=[
                    "real_isolated_postgres_restore_missing",
                    "retention_tiers_not_accepted",
                ],
            ),
            self._cockpit_domain(
                domain_key="ws2_async",
                label="WS2 / Async Runtime",
                status="limited_no_go",
                status_label="Durable/synthetic contracts present; multi-instance acceptance missing",
                detail_route="/admin/evidence-workflow",
                foundation_landed=False,
                evidence_tooling_present=True,
                real_operator_evidence_missing=True,
                evidence_refs=[
                    "docs/operations/background-job-queue-boundary.md",
                    "scripts/ws2_multi_instance_smoke.py",
                    "scripts/ws2_sse_operator_decision_check.py",
                    "tests/test_ws2_durable_task_worker.py",
                ],
                blocker_refs=[
                    "docs/audits/public-launch-gap-register.md#ws2multi-instance",
                    "docs/audits/index-db-ws2-deployment.md",
                ],
                safe_next_actions=[
                    "Record process-local SSE limitations and durable polling expectations.",
                    "Treat synthetic worker evidence as non-production evidence.",
                ],
                limitations=[
                    "process_local_sse_limitation",
                    "staging_api_ab_worker_smoke_missing",
                ],
            ),
            self._cockpit_domain(
                domain_key="notifications",
                label="Notifications",
                status="no_send_no_go",
                status_label="No-send contracts present; delivery rehearsal missing",
                detail_route="/admin/notifications",
                foundation_landed=False,
                evidence_tooling_present=True,
                real_operator_evidence_missing=True,
                evidence_refs=[
                    "tests/api/test_notification_channels.py",
                    "tests/test_quota_cost_notification_release_contracts.py",
                    "tests/test_user_notification_preferences.py",
                ],
                blocker_refs=[
                    "docs/audits/public-launch-readiness-master.md#manual-release-criteria",
                    "docs/audits/operator-evidence-real-runbook.md",
                ],
                safe_next_actions=[
                    "Review channel coverage and recent events without testing or sending.",
                    "Keep acknowledgement, create, delete, and test-send actions on detail pages.",
                ],
                limitations=[
                    "real_delivery_rehearsal_missing",
                    "external_sends_not_approved",
                ],
            ),
            self._cockpit_domain(
                domain_key="portfolio_backtest",
                label="Portfolio / Backtest",
                status="partial_no_go",
                status_label="Read-only/stored-first evidence present; staged safety proof missing",
                detail_route="/admin/evidence-workflow",
                foundation_landed=False,
                evidence_tooling_present=True,
                real_operator_evidence_missing=True,
                evidence_refs=[
                    "tests/api/test_portfolio_history.py",
                    "tests/api/test_portfolio_owner_isolation.py",
                    "tests/test_backtest_api_contract.py",
                    "docs/backtest-system.md",
                ],
                blocker_refs=[
                    "docs/audits/public-launch-gap-register.md#portfoliobacktest",
                    "docs/audits/backtest-portfolio-public-safety-audit.md",
                ],
                safe_next_actions=[
                    "Review stored-first backtest and portfolio owner-isolation evidence.",
                    "Keep accounting formulas and backtest engine behavior unchanged.",
                ],
                limitations=[
                    "broader_accounting_invariant_evidence_missing",
                    "staged_owner_isolation_smoke_missing",
                ],
            ),
            self._cockpit_domain(
                domain_key="route_classification",
                label="Route Classification",
                status="foundation_ready_review_required",
                status_label="Route inventory frozen; release approval still external",
                detail_route="/admin/evidence-workflow",
                foundation_landed=True,
                evidence_tooling_present=True,
                real_operator_evidence_missing=False,
                evidence_refs=[
                    "scripts/admin_rbac_route_inventory.py",
                    "tests/fixtures/auth/backend_route_capability_inventory.json",
                    "tests/test_auth_route_capability_inventory.py",
                    "tests/api/test_public_api_surface_safety.py",
                ],
                blocker_refs=[
                    "docs/audits/public-launch-readiness-master.md#manual-release-criteria",
                    "docs/AI_PROJECT_MANUAL.md#production-readiness-documentation-authority",
                ],
                safe_next_actions=[
                    "Compare backend route inventory against admin capability expectations.",
                    "Keep route classification as release evidence, not release approval.",
                ],
                limitations=[
                    "manual_release_review_still_required",
                    "frontend_route_smoke_not_complete_for_every_admin_surface",
                ],
            ),
            self._cockpit_domain(
                domain_key="frontend_private_beta_safety",
                label="Frontend / Private-Beta Safety",
                status="surface_review_no_go",
                status_label="Admin surfaces exist; bounded private-beta smoke still required",
                detail_route="/settings/system",
                foundation_landed=False,
                evidence_tooling_present=True,
                real_operator_evidence_missing=True,
                evidence_refs=[
                    "apps/dsa-web/e2e/admin-ops-launch-surfaces.spec.ts",
                    "apps/dsa-web/e2e/readiness-browser-acceptance.smoke.spec.ts",
                    "apps/dsa-web/src/__tests__/AppRoutes.test.tsx",
                    "docs/release/small-private-beta-release-checklist.md",
                ],
                blocker_refs=[
                    "docs/audits/public-launch-gap-register.md#highest-risk-blockers",
                    "docs/audits/public-launch-readiness-master.md",
                ],
                safe_next_actions=[
                    "Run bounded admin cockpit smoke with mocked/safe data.",
                    "Keep private-beta readiness distinct from public launch approval.",
                ],
                limitations=[
                    "bounded_browser_evidence_pending",
                    "public_launch_approval_external",
                ],
            ),
        ]

        blockers = [
            {
                "blockerKey": "public_launch_no_go",
                "title": "Public launch remains NO-GO",
                "severity": "critical",
                "publicLaunchNoGo": True,
                "approvalRequired": True,
                "affectedDomains": [domain["domainKey"] for domain in domains],
                "evidenceRefs": [
                    "docs/audits/public-launch-readiness-master.md",
                    "docs/audits/public-launch-gap-register.md",
                ],
                "nextAction": "Collect missing real operator evidence and complete manual release review outside cockpit.",
            },
            {
                "blockerKey": "real_operator_evidence_missing",
                "title": "Real target-environment operator evidence is missing",
                "severity": "high",
                "publicLaunchNoGo": True,
                "approvalRequired": True,
                "affectedDomains": [
                    domain["domainKey"]
                    for domain in domains
                    if domain["realOperatorEvidenceMissing"]
                ],
                "evidenceRefs": [
                    "docs/audits/operator-evidence-real-runbook.md",
                    "docs/audits/launch-acceptance-evidence-pack.md",
                ],
                "nextAction": "Use existing validators on sanitized operator artifacts after approval.",
            },
        ]

        return {
            "contract": "admin_ops_launch_cockpit_v1",
            "readOnly": True,
            "advisoryOnly": True,
            "noExternalCalls": True,
            "publicLaunchApproved": False,
            "publicLaunchNoGo": True,
            "liveEnforcement": False,
            "runtimeBehaviorChanged": False,
            "approvalRequired": True,
            "summaryCounts": {
                "domainCount": len(domains),
                "foundationLandedCount": sum(1 for domain in domains if domain["foundationLanded"]),
                "evidenceToolingPresentCount": sum(
                    1 for domain in domains if domain["evidenceToolingPresent"]
                ),
                "realEvidenceMissingCount": sum(
                    1 for domain in domains if domain["realOperatorEvidenceMissing"]
                ),
                "approvalRequiredCount": sum(1 for domain in domains if domain["approvalRequired"]),
                "publicLaunchNoGoCount": sum(1 for domain in domains if domain["publicLaunchNoGo"]),
                "blockerCount": len(blockers),
            },
            "unsafeActionStates": {
                "quotaLiveBlockingEnabled": False,
                "providerCircuitBlockingEnabled": False,
                "mfaEnforcementEnabled": False,
                "rbacFallbackRemoved": False,
                "dbMigrationOrRestoreRun": False,
                "cleanupOrDeleteRun": False,
                "notificationSendEnabled": False,
                "providerLiveCallsEnabled": False,
                "productionConfigChanged": False,
            },
            "domains": domains,
            "blockers": blockers,
            "safeNextActions": [
                "Open domain detail pages for read-only evidence review.",
                "Record missing operator evidence and approval-required follow-ups.",
                "Keep private-beta readiness separate from public launch approval.",
            ],
            "limitations": [
                "cockpit_does_not_execute_validators",
                "cockpit_does_not_approve_public_launch",
                "cockpit_does_not_change_runtime_behavior",
            ],
        }
