# -*- coding: utf-8 -*-
"""Retention and storage-health helpers for the Admin Logs center."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import and_, delete, func, select, text

from src.config import get_config
from src.storage import ExecutionLogEvent, ExecutionLogSession, get_db


@dataclass(frozen=True)
class AdminLogRetentionPolicy:
    retention_days: int = 90
    warning_threshold_count: int = 50_000
    critical_threshold_count: int = 100_000
    warning_threshold_storage_bytes: Optional[int] = None


class AdminLogsRetentionService:
    """Summarize and clean existing execution-log tables."""

    def __init__(self) -> None:
        self.db = get_db()

    @staticmethod
    def _policy() -> AdminLogRetentionPolicy:
        config = get_config()
        return AdminLogRetentionPolicy(
            retention_days=max(1, int(getattr(config, "admin_logs_retention_days", 90) or 90)),
            warning_threshold_count=max(1, int(getattr(config, "admin_logs_warning_threshold_count", 50_000) or 50_000)),
            critical_threshold_count=max(1, int(getattr(config, "admin_logs_critical_threshold_count", 100_000) or 100_000)),
            warning_threshold_storage_bytes=getattr(config, "admin_logs_warning_threshold_storage_bytes", None),
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

    def _storage_bytes(self) -> Optional[int]:
        engine = getattr(self.db, "_engine", None)
        if engine is None or getattr(engine.dialect, "name", "") != "postgresql":
            return None
        with engine.connect() as conn:
            value = conn.execute(
                text(
                    "SELECT "
                    "pg_total_relation_size('execution_log_sessions') + "
                    "pg_total_relation_size('execution_log_events')"
                )
            ).scalar()
        return int(value) if value is not None else None

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
        status = "ok"
        reasons = []
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
        if (
            storage_bytes is not None
            and policy.warning_threshold_storage_bytes is not None
            and storage_bytes >= policy.warning_threshold_storage_bytes
        ):
            status = "warning" if status == "ok" else status
            reasons.append("storage_warning")
        recommended = (
            "Preview cleanup, then delete logs older than retention."
            if older_than_retention > 0 or status in {"warning", "critical"}
            else "No cleanup needed."
        )
        return {
            "total_log_count": total_logs,
            "total_event_count": total_events,
            "oldest_log_timestamp": self._iso(oldest),
            "newest_log_timestamp": self._iso(newest),
            "retention_days": policy.retention_days,
            "retention_cutoff": self._iso(retention_cutoff),
            "logs_older_than_retention_count": older_than_retention,
            "estimated_storage_bytes": storage_bytes,
            "warning_threshold_count": policy.warning_threshold_count,
            "critical_threshold_count": policy.critical_threshold_count,
            "warning_threshold_storage_bytes": policy.warning_threshold_storage_bytes,
            "status": status,
            "status_reasons": reasons,
            "recommended_cleanup_action": recommended,
            "last_cleanup_timestamp": None,
        }

    def cleanup(
        self,
        *,
        use_retention: bool = False,
        older_than: Optional[str] = None,
        dry_run: bool = True,
        status: Optional[str] = None,
        category: Optional[str] = None,
        batch_size: int = 1000,
    ) -> Dict[str, Any]:
        policy = self._policy()
        cutoff = datetime.now() - timedelta(days=policy.retention_days) if use_retention else self._parse_cutoff(older_than)
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
                    return self._cleanup_payload(cutoff=cutoff, dry_run=dry_run, status=status, category=category)
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
                cutoff=cutoff,
                dry_run=False,
                status=status,
                category=category,
                matched_log_count=matched_log_count,
                matched_event_count=matched_event_count,
                deleted_log_count=deleted_log_count,
                deleted_event_count=deleted_event_count,
            )

    def _cleanup_payload(
        self,
        *,
        cutoff: Optional[datetime] = None,
        dry_run: bool,
        status: Optional[str],
        category: Optional[str],
        matched_log_count: int = 0,
        matched_event_count: int = 0,
        deleted_log_count: int = 0,
        deleted_event_count: int = 0,
    ) -> Dict[str, Any]:
        return {
            "dry_run": dry_run,
            "cutoff": self._iso(cutoff),
            "matched_log_count": matched_log_count,
            "matched_event_count": matched_event_count,
            "deleted_log_count": deleted_log_count,
            "deleted_event_count": deleted_event_count,
            "status_filter": status,
            "category_filter": category,
        }
