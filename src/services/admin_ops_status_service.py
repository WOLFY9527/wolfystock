# -*- coding: utf-8 -*-
"""Read-only admin ops status snapshot aggregation."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

from sqlalchemy import func, select, text

from src.services.admin_logs_service import AdminLogsRetentionService
from src.services.llm_cost_ledger_service import LlmCostLedgerService
from src.services.quota_policy_service import QuotaPolicyService
from src.storage import (
    DatabaseManager,
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

    def build_status(self, *, app_state: object | None = None) -> Dict[str, Any]:
        generated_at = datetime.now()
        return {
            "generatedAt": generated_at.isoformat(),
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
            "providerStatusSummary": self._safe_source(self._build_provider_status_summary),
            "quotaCostAdvisoryStatusSummary": self._safe_source(
                lambda: self._build_quota_cost_advisory_status_summary(generated_at)
            ),
            "storageReadinessSummary": self._safe_source(self._build_storage_readiness_summary),
            "taskQueueStatusSummary": self._safe_source(lambda: self._build_task_queue_status_summary(app_state)),
            "adminLogEvidenceSummary": self._safe_source(self._build_admin_log_evidence_summary),
            "metadata": {
                "contract": "admin_ops_status_snapshot_v1",
                "gatingCapability": "ops:logs:read",
                "redaction": [
                    "actor_identifiers_bucketed",
                    "login_context_identifiers_omitted",
                    "external_source_bodies_omitted",
                    "request_content_omitted",
                    "auth_material_and_credential_values_omitted",
                    "diagnostic_trace_details_omitted",
                    "raw_exception_text_omitted",
                ],
                "mutationPaths": [],
                "dataSources": [
                    "provider_circuit_states",
                    "provider_circuit_events",
                    "provider_quota_windows",
                    "provider_probe_events",
                    "quota_policy_readiness_helpers",
                    "llm_cost_ledger_summary",
                    "database_session_check",
                    "task_queue_runtime_status",
                    "execution_log_sessions",
                    "execution_log_events",
                    "admin_log_retention_policy",
                ],
            },
        }

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
