# -*- coding: utf-8 -*-
"""Retention and storage-health helpers for the Admin Logs center."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, delete, func, select, text

from src.config import get_config
from src.postgres_control_plane_store import PhaseGExecutionEvent, PhaseGExecutionSession
from src.services.notification_service import NotificationService
from src.storage import ExecutionLogEvent, ExecutionLogSession, get_db

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdminLogRetentionPolicy:
    retention_days: int = 90
    min_retention_days: int = 7
    storage_soft_limit_bytes: int = 512 * 1024 * 1024
    storage_hard_limit_bytes: int = 1024 * 1024 * 1024
    cleanup_batch_size: int = 1000
    auto_cleanup_enabled: bool = True
    warning_threshold_count: int = 50_000
    critical_threshold_count: int = 100_000
    warning_threshold_storage_bytes: Optional[int] = None
    config_warnings: List[str] = field(default_factory=list)


class AdminLogsRetentionService:
    """Summarize and clean existing execution-log tables."""

    _last_auto_cleanup_at: Optional[datetime] = None
    _auto_cleanup_min_interval = timedelta(minutes=5)

    def __init__(self) -> None:
        self.db = get_db()

    @staticmethod
    def _emit_notification_event(**kwargs: Any) -> None:
        try:
            NotificationService().emit_event(**kwargs)
        except Exception as exc:
            logger.warning("admin logs notification event emit failed: %s", exc)

    @staticmethod
    def _policy() -> AdminLogRetentionPolicy:
        config = get_config()
        config_warnings: List[str] = []
        retention_days = max(1, int(getattr(config, "admin_logs_retention_days", 90) or 90))
        min_retention_days = max(0, int(getattr(config, "admin_logs_min_retention_days", 7) or 0))
        if min_retention_days > retention_days:
            min_retention_days = retention_days
            config_warnings.append("min_retention_days_clamped_to_retention_days")
        storage_soft_limit_bytes = max(
            1,
            int(getattr(config, "admin_logs_storage_soft_limit_mb", 512) or 512) * 1024 * 1024,
        )
        storage_hard_limit_bytes = max(
            1,
            int(getattr(config, "admin_logs_storage_hard_limit_mb", 1024) or 1024) * 1024 * 1024,
        )
        if storage_hard_limit_bytes <= storage_soft_limit_bytes:
            storage_hard_limit_bytes = storage_soft_limit_bytes * 2
            config_warnings.append("hard_limit_adjusted_above_soft_limit")
        cleanup_batch_size = max(1, min(int(getattr(config, "admin_logs_cleanup_batch_size", 1000) or 1000), 5000))
        return AdminLogRetentionPolicy(
            retention_days=retention_days,
            min_retention_days=min_retention_days,
            storage_soft_limit_bytes=storage_soft_limit_bytes,
            storage_hard_limit_bytes=storage_hard_limit_bytes,
            cleanup_batch_size=cleanup_batch_size,
            auto_cleanup_enabled=bool(getattr(config, "admin_logs_auto_cleanup_enabled", True)),
            warning_threshold_count=max(1, int(getattr(config, "admin_logs_warning_threshold_count", 50_000) or 50_000)),
            critical_threshold_count=max(1, int(getattr(config, "admin_logs_critical_threshold_count", 100_000) or 100_000)),
            warning_threshold_storage_bytes=getattr(config, "admin_logs_warning_threshold_storage_bytes", None),
            config_warnings=config_warnings,
        )

    @staticmethod
    def _iso(value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    @staticmethod
    def _parse_cutoff(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        text_value = str(value).strip()
        if not text_value:
            return None
        try:
            return datetime.fromisoformat(text_value.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception as exc:
            raise ValueError(f"Invalid cleanup cutoff datetime: {value}") from exc

    def _storage_relation_scope(self) -> tuple[Optional[Any], Optional[str], Optional[str]]:
        phase_g_store = getattr(self.db, "_phase_g_store", None)
        phase_g_engine = getattr(phase_g_store, "_engine", None) if phase_g_store is not None else None
        if phase_g_engine is not None and getattr(phase_g_engine.dialect, "name", "") == "postgresql":
            return (
                phase_g_engine,
                PhaseGExecutionSession.__tablename__,
                PhaseGExecutionEvent.__tablename__,
            )

        engine = getattr(self.db, "_engine", None)
        if engine is not None and getattr(engine.dialect, "name", "") == "postgresql":
            return (
                engine,
                ExecutionLogSession.__tablename__,
                ExecutionLogEvent.__tablename__,
            )

        return None, None, None

    def _storage_bytes(self) -> Optional[int]:
        engine, session_table, event_table = self._storage_relation_scope()
        if engine is None or not session_table or not event_table:
            return None
        with engine.connect() as conn:
            value = conn.execute(
                text(
                    "SELECT "
                    "COALESCE(pg_total_relation_size(to_regclass(:session_table)), 0) + "
                    "COALESCE(pg_total_relation_size(to_regclass(:event_table)), 0)"
                ),
                {
                    "session_table": session_table,
                    "event_table": event_table,
                },
            ).scalar()
        return int(value) if value is not None else None

    @staticmethod
    def _format_bytes(value: Optional[int]) -> Optional[str]:
        if value is None:
            return None
        amount = float(value)
        for suffix in ("B", "KB", "MB", "GB", "TB"):
            if amount < 1024 or suffix == "TB":
                if suffix == "B":
                    return f"{int(amount)} B"
                return f"{amount:.1f} {suffix}"
            amount /= 1024
        return f"{int(value)} B"

    @staticmethod
    def _percentage(numerator: Optional[int], denominator: int) -> Optional[float]:
        if numerator is None or denominator <= 0:
            return None
        return round((float(numerator) / float(denominator)) * 100, 2)

    def _capacity_candidates(
        self,
        *,
        session,
        cutoff: datetime,
        batch_size: int,
    ) -> Dict[str, Any]:
        where_clause = ExecutionLogSession.started_at < cutoff
        session_ids = session.execute(
            select(ExecutionLogSession.session_id)
            .where(where_clause)
            .order_by(ExecutionLogSession.started_at.asc())
            .limit(batch_size)
        ).scalars().all()
        matched_log_count = int(session.execute(select(func.count(ExecutionLogSession.id)).where(where_clause)).scalar() or 0)
        matched_event_count = int(
            session.execute(select(func.count(ExecutionLogEvent.id)).where(ExecutionLogEvent.session_id.in_(session_ids))).scalar()
            if session_ids
            else 0
        )
        return {
            "session_ids": session_ids,
            "matched_log_count": matched_log_count,
            "matched_event_count": matched_event_count,
        }

    def capacity_cleanup_plan(self) -> Dict[str, Any]:
        policy = self._policy()
        now = datetime.now()
        min_retention_cutoff = now - timedelta(days=policy.min_retention_days)
        storage_bytes = self._storage_bytes()
        storage_available = storage_bytes is not None
        hard_limit_exceeded = bool(storage_available and storage_bytes >= policy.storage_hard_limit_bytes)
        with self.db.get_session() as session:
            total_logs = int(session.execute(select(func.count(ExecutionLogSession.id))).scalar() or 0)
            total_events = int(session.execute(select(func.count(ExecutionLogEvent.id))).scalar() or 0)
            candidates = self._capacity_candidates(
                session=session,
                cutoff=min_retention_cutoff,
                batch_size=policy.cleanup_batch_size,
            )
        cleanup_safe = storage_available and candidates["matched_log_count"] > 0
        reason = None
        if not storage_available:
            reason = "storage_size_unavailable"
        elif candidates["matched_log_count"] <= 0:
            reason = "no_logs_older_than_minimum_retention"
        elif not hard_limit_exceeded:
            reason = "hard_limit_not_exceeded"
        estimated_bytes_per_session = int(storage_bytes / total_logs) if storage_available and storage_bytes and total_logs > 0 else None
        estimated_reclaimable_bytes = (
            estimated_bytes_per_session * candidates["matched_log_count"]
            if estimated_bytes_per_session is not None
            else None
        )
        return {
            "mode": "capacity",
            "current_storage_bytes": storage_bytes,
            "target_storage_bytes": policy.storage_soft_limit_bytes,
            "soft_limit_bytes": policy.storage_soft_limit_bytes,
            "hard_limit_bytes": policy.storage_hard_limit_bytes,
            "hard_limit_exceeded": hard_limit_exceeded,
            "oldest_deletable_cutoff": self._iso(min_retention_cutoff),
            "estimated_candidate_sessions": candidates["matched_log_count"],
            "estimated_candidate_events": candidates["matched_event_count"],
            "cleanup_safe": cleanup_safe,
            "reason": reason,
            "storage_size_available": storage_available,
            "estimated_bytes_per_session": estimated_bytes_per_session,
            "estimated_reclaimable_bytes": estimated_reclaimable_bytes,
            "batch_size": policy.cleanup_batch_size,
        }

    def storage_summary(self) -> Dict[str, Any]:
        policy = self._policy()
        now = datetime.now()
        retention_cutoff = now - timedelta(days=policy.retention_days)
        with self.db.get_session() as session:
            total_logs = int(session.execute(select(func.count(ExecutionLogSession.id))).scalar() or 0)
            total_events = int(session.execute(select(func.count(ExecutionLogEvent.id))).scalar() or 0)
            oldest = session.execute(select(func.min(ExecutionLogSession.started_at))).scalar()
            newest = session.execute(select(func.max(ExecutionLogSession.started_at))).scalar()
            older_than_retention = int(
                session.execute(
                    select(func.count(ExecutionLogSession.id)).where(ExecutionLogSession.started_at < retention_cutoff)
                ).scalar()
                or 0
            )
        storage_bytes = self._storage_bytes()
        storage_available = storage_bytes is not None
        used_soft_pct = self._percentage(storage_bytes, policy.storage_soft_limit_bytes)
        used_hard_pct = self._percentage(storage_bytes, policy.storage_hard_limit_bytes)
        status = "ok"
        reasons = list(policy.config_warnings)
        if total_logs >= policy.critical_threshold_count:
            status = "critical"
            reasons.append("log_count_critical")
        elif total_logs >= policy.warning_threshold_count:
            status = "warning"
            reasons.append("log_count_warning")
        if older_than_retention > 0 and status == "ok":
            status = "warning"
        if older_than_retention > 0:
            reasons.append("older_than_retention")
        if storage_bytes is not None and storage_bytes >= policy.storage_hard_limit_bytes:
            status = "critical"
            reasons.append("storage_hard_limit_exceeded")
        elif storage_bytes is not None and storage_bytes >= policy.storage_soft_limit_bytes:
            status = "warning" if status == "ok" else status
            reasons.append("storage_soft_limit_exceeded")
        elif (
            storage_bytes is not None
            and policy.warning_threshold_storage_bytes is not None
            and storage_bytes >= policy.warning_threshold_storage_bytes
        ):
            status = "warning" if status == "ok" else status
            reasons.append("storage_warning")
        capacity_cleanup_recommended = bool(storage_bytes is not None and storage_bytes >= policy.storage_soft_limit_bytes)
        if status == "critical" and "storage_hard_limit_exceeded" in reasons:
            recommended = "Storage is over the hard limit. Run capacity cleanup; oldest eligible logs are protected by minimum retention."
        elif capacity_cleanup_recommended:
            recommended = "Storage is over the soft limit. Preview retention cleanup or capacity cleanup."
        elif older_than_retention > 0 or status in {"warning", "critical"}:
            recommended = "Preview cleanup, then delete logs older than retention."
        elif storage_bytes is None:
            recommended = "Storage size unavailable; retention and row-count checks are active."
        else:
            recommended = "No cleanup needed."
        capacity_plan = self.capacity_cleanup_plan()
        auto_cleanup_performed = False
        auto_cleanup_message = None
        auto_cleanup_recent = (
            self.__class__._last_auto_cleanup_at is not None
            and now - self.__class__._last_auto_cleanup_at < self.__class__._auto_cleanup_min_interval
        )
        cleanup_failed_message = None
        if (
            policy.auto_cleanup_enabled
            and storage_bytes is not None
            and storage_bytes >= policy.storage_hard_limit_bytes
            and capacity_plan["estimated_candidate_sessions"] > 0
            and not auto_cleanup_recent
        ):
            try:
                cleanup_result = self.cleanup(mode="capacity", dry_run=False, batch_size=policy.cleanup_batch_size)
                auto_cleanup_performed = cleanup_result["deleted_log_count"] > 0
                if auto_cleanup_performed:
                    self.__class__._last_auto_cleanup_at = now
                auto_cleanup_message = cleanup_result.get("message")
            except ValueError as exc:
                auto_cleanup_message = str(exc)
                cleanup_failed_message = str(exc)
        elif auto_cleanup_recent:
            auto_cleanup_message = "Automatic cleanup was recently attempted; waiting before the next batch."
        summary = {
            "total_log_count": total_logs,
            "total_event_count": total_events,
            "oldest_log_timestamp": self._iso(oldest),
            "newest_log_timestamp": self._iso(newest),
            "retention_days": policy.retention_days,
            "minimum_retention_days": policy.min_retention_days,
            "retention_cutoff": self._iso(retention_cutoff),
            "logs_older_than_retention_count": older_than_retention,
            "estimated_storage_bytes": storage_bytes,
            "storage_size_bytes": storage_bytes,
            "storage_size_label": self._format_bytes(storage_bytes),
            "storage_size_available": storage_available,
            "storage_soft_limit_bytes": policy.storage_soft_limit_bytes,
            "storage_hard_limit_bytes": policy.storage_hard_limit_bytes,
            "used_percentage_of_soft_limit": used_soft_pct,
            "used_percentage_of_hard_limit": used_hard_pct,
            "capacity_cleanup_recommended": capacity_cleanup_recommended,
            "auto_cleanup_enabled": policy.auto_cleanup_enabled,
            "auto_cleanup_performed": auto_cleanup_performed,
            "auto_cleanup_message": auto_cleanup_message,
            "capacity_cleanup_plan": capacity_plan,
            "postgres_vacuum_note": (
                "Deleted rows may require PostgreSQL autovacuum to reclaim physical disk space."
                if storage_bytes is not None and (status in {"warning", "critical"} or auto_cleanup_performed)
                else None
            ),
            "warning_threshold_count": policy.warning_threshold_count,
            "critical_threshold_count": policy.critical_threshold_count,
            "warning_threshold_storage_bytes": policy.warning_threshold_storage_bytes,
            "status": status,
            "status_reasons": reasons,
            "recommended_cleanup_action": recommended,
            "last_cleanup_timestamp": None,
        }
        if status in {"warning", "critical"}:
            self._emit_notification_event(
                event_type="admin_logs.storage",
                severity=status,
                title=f"Admin Logs storage {status}",
                message=recommended,
                payload={
                    "status": status,
                    "status_reasons": reasons,
                    "total_log_count": total_logs,
                    "total_event_count": total_events,
                    "storage_size_bytes": storage_bytes,
                    "capacity_cleanup_recommended": capacity_cleanup_recommended,
                },
                fingerprint=f"admin_logs.storage:{status}:{','.join(sorted(set(reasons))) or 'health'}",
                dedupe_window=timedelta(minutes=30),
            )
        if auto_cleanup_performed:
            self._emit_notification_event(
                event_type="admin_logs.cleanup",
                severity="warning",
                title="Admin Logs capacity cleanup performed",
                message=auto_cleanup_message or "Automatic Admin Logs capacity cleanup deleted old sessions.",
                payload={"mode": "capacity", "status": status, "auto_cleanup_performed": True},
                fingerprint="admin_logs.cleanup:auto",
                dedupe_window=timedelta(minutes=30),
            )
        if cleanup_failed_message:
            self._emit_notification_event(
                event_type="admin_logs.cleanup",
                severity="critical",
                title="Admin Logs capacity cleanup failed",
                message=cleanup_failed_message,
                payload={"mode": "capacity", "status": status},
                fingerprint=f"admin_logs.cleanup:failed:{cleanup_failed_message}",
                dedupe_window=timedelta(minutes=30),
            )
        return summary

    def cleanup(
        self,
        *,
        mode: Optional[str] = None,
        use_retention: bool = False,
        older_than: Optional[str] = None,
        dry_run: bool = True,
        status: Optional[str] = None,
        category: Optional[str] = None,
        batch_size: int = 1000,
    ) -> Dict[str, Any]:
        policy = self._policy()
        normalized_mode = str(mode or "").strip().lower()
        if use_retention:
            normalized_mode = "retention"
        if older_than and normalized_mode in {"", "retention"} and not use_retention:
            normalized_mode = "before_date"
        if not normalized_mode:
            raise ValueError("Cleanup requires mode=retention, mode=capacity, use_retention=true, or a valid older_than cutoff.")
        if normalized_mode not in {"retention", "before_date", "capacity"}:
            raise ValueError("Cleanup mode must be retention, before_date, or capacity.")
        if normalized_mode == "capacity":
            return self._cleanup_capacity(dry_run=dry_run, batch_size=batch_size)

        cutoff = datetime.now() - timedelta(days=policy.retention_days) if normalized_mode == "retention" else self._parse_cutoff(older_than)
        if cutoff is None:
            raise ValueError("Cleanup requires use_retention=true or a valid older_than cutoff.")
        if cutoff >= datetime.now():
            raise ValueError("Cleanup cutoff must be in the past.")

        safe_batch_size = max(1, min(int(batch_size or 1000), 5000))
        with self.db.session_scope() as session:
            filters = [ExecutionLogSession.started_at < cutoff]
            if status:
                filters.append(ExecutionLogSession.overall_status == status)
            if category:
                matched_ids = session.execute(
                    select(ExecutionLogEvent.session_id)
                    .where(and_(ExecutionLogEvent.phase == category, ExecutionLogEvent.event_at < cutoff))
                    .distinct()
                ).scalars().all()
                if not matched_ids:
                    return self._cleanup_payload(mode=normalized_mode, cutoff=cutoff, dry_run=dry_run, status=status, category=category)
                filters.append(ExecutionLogSession.session_id.in_(matched_ids))

            where_clause = and_(*filters)
            matching_sessions = session.execute(
                select(ExecutionLogSession.session_id)
                .where(where_clause)
                .order_by(ExecutionLogSession.started_at.asc())
                .limit(safe_batch_size)
            ).scalars().all()
            matched_log_count = int(session.execute(select(func.count(ExecutionLogSession.id)).where(where_clause)).scalar() or 0)
            matched_event_count = int(
                session.execute(select(func.count(ExecutionLogEvent.id)).where(ExecutionLogEvent.session_id.in_(matching_sessions))).scalar()
                if matching_sessions
                else 0
            )
            if dry_run or not matching_sessions:
                return self._cleanup_payload(
                    mode=normalized_mode,
                    cutoff=cutoff,
                    dry_run=dry_run,
                    status=status,
                    category=category,
                    matched_log_count=matched_log_count,
                    matched_event_count=matched_event_count,
                )
            deleted_event_count = int(
                session.execute(delete(ExecutionLogEvent).where(ExecutionLogEvent.session_id.in_(matching_sessions))).rowcount
                or 0
            )
            deleted_log_count = int(
                session.execute(delete(ExecutionLogSession).where(ExecutionLogSession.session_id.in_(matching_sessions))).rowcount
                or 0
            )
            return self._cleanup_payload(
                mode=normalized_mode,
                cutoff=cutoff,
                dry_run=False,
                status=status,
                category=category,
                matched_log_count=matched_log_count,
                matched_event_count=matched_event_count,
                deleted_log_count=deleted_log_count,
                deleted_event_count=deleted_event_count,
            )

    def _cleanup_capacity(self, *, dry_run: bool, batch_size: int) -> Dict[str, Any]:
        policy = self._policy()
        storage_bytes = self._storage_bytes()
        if storage_bytes is None:
            raise ValueError("Capacity cleanup requires PostgreSQL storage size; storage size is unavailable for this database.")
        min_retention_cutoff = datetime.now() - timedelta(days=policy.min_retention_days)
        safe_batch_size = max(1, min(int(batch_size or policy.cleanup_batch_size), policy.cleanup_batch_size, 5000))
        with self.db.session_scope() as session:
            total_logs = int(session.execute(select(func.count(ExecutionLogSession.id))).scalar() or 0)
            candidates = self._capacity_candidates(
                session=session,
                cutoff=min_retention_cutoff,
                batch_size=safe_batch_size,
            )
            matching_sessions = candidates["session_ids"]
            matched_log_count = candidates["matched_log_count"]
            matched_event_count = candidates["matched_event_count"]
            hard_limit_exceeded = storage_bytes >= policy.storage_hard_limit_bytes
            if dry_run or not matching_sessions or not hard_limit_exceeded:
                return self._cleanup_payload(
                    mode="capacity",
                    cutoff=min_retention_cutoff,
                    dry_run=dry_run,
                    status=None,
                    category=None,
                    matched_log_count=matched_log_count if hard_limit_exceeded else 0,
                    matched_event_count=matched_event_count if hard_limit_exceeded else 0,
                    additional_cleanup_needed=hard_limit_exceeded and matched_log_count > len(matching_sessions),
                    message="Capacity cleanup not needed." if not hard_limit_exceeded else None,
                )
            deleted_event_count = int(
                session.execute(delete(ExecutionLogEvent).where(ExecutionLogEvent.session_id.in_(matching_sessions))).rowcount
                or 0
            )
            deleted_log_count = int(
                session.execute(delete(ExecutionLogSession).where(ExecutionLogSession.session_id.in_(matching_sessions))).rowcount
                or 0
            )
            estimated_bytes_per_session = int(storage_bytes / total_logs) if total_logs > 0 else 0
            estimated_remaining_bytes = max(0, storage_bytes - (estimated_bytes_per_session * deleted_log_count))
            additional_cleanup_needed = estimated_remaining_bytes > policy.storage_soft_limit_bytes and matched_log_count > deleted_log_count
            result = self._cleanup_payload(
                mode="capacity",
                cutoff=min_retention_cutoff,
                dry_run=False,
                status=None,
                category=None,
                matched_log_count=matched_log_count,
                matched_event_count=matched_event_count,
                deleted_log_count=deleted_log_count,
                deleted_event_count=deleted_event_count,
                additional_cleanup_needed=additional_cleanup_needed,
                message=(
                    "Deleted rows may require PostgreSQL autovacuum to reclaim physical disk space."
                    if deleted_log_count > 0
                    else None
                ),
            )
            self._emit_notification_event(
                event_type="admin_logs.cleanup",
                severity="warning",
                title="Admin Logs capacity cleanup performed",
                message=f"Capacity cleanup deleted {deleted_log_count} sessions and {deleted_event_count} events.",
                payload={
                    "mode": "capacity",
                    "deleted_log_count": deleted_log_count,
                    "deleted_event_count": deleted_event_count,
                    "additional_cleanup_needed": additional_cleanup_needed,
                },
                fingerprint=f"admin_logs.cleanup:capacity:{deleted_log_count}:{deleted_event_count}:{additional_cleanup_needed}",
                dedupe_window=timedelta(minutes=30),
            )
            return result

    def _cleanup_payload(
        self,
        *,
        mode: str = "retention",
        cutoff: Optional[datetime] = None,
        dry_run: bool,
        status: Optional[str],
        category: Optional[str],
        matched_log_count: int = 0,
        matched_event_count: int = 0,
        deleted_log_count: int = 0,
        deleted_event_count: int = 0,
        additional_cleanup_needed: bool = False,
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "mode": mode,
            "dry_run": dry_run,
            "cutoff": self._iso(cutoff),
            "matched_log_count": matched_log_count,
            "matched_event_count": matched_event_count,
            "deleted_log_count": deleted_log_count,
            "deleted_event_count": deleted_event_count,
            "status_filter": status,
            "category_filter": category,
            "additional_cleanup_needed": additional_cleanup_needed,
            "message": message,
            "postgres_vacuum_note": (
                "Deleted rows may require PostgreSQL autovacuum to reclaim physical disk space."
                if deleted_log_count > 0 or mode == "capacity"
                else None
            ),
        }
