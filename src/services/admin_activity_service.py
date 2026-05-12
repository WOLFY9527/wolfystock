# -*- coding: utf-8 -*-
"""Conservative admin activity timeline projection service."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any, Optional

from src.repositories.auth_repo import AuthRepository
from src.services.execution_log_service import ExecutionLogService
from src.storage import AnalysisHistory, AppUserSession, DatabaseManager
from src.utils.security import sanitize_metadata, sanitize_message


def hash_reference(value: Any, *, prefix: str = "sha256") -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:16]}"


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if isinstance(value, datetime) else None


def _status(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"success", "succeeded", "completed", "ok"}:
        return "success"
    if text in {"partial", "partial_success"}:
        return "partial"
    if text in {"failed", "failure", "error", "invalid_response", "empty_result", "timed_out", "timeout"}:
        return "failed"
    if text in {"running", "started", "in_progress"}:
        return "running"
    if text in {"skipped", "not_configured"}:
        return "skipped"
    if text in {"cancelled", "canceled"}:
        return "cancelled"
    return "unknown"


def _outcome(status: str, source_value: Any = None) -> str:
    text = str(source_value or status or "").strip().lower()
    if "timeout" in text:
        return "timeout"
    if status == "success":
        return "ok"
    if status == "partial":
        return "partial"
    if status == "failed":
        return "failed"
    if status == "skipped":
        return "ok"
    return "unknown"


class AdminActivityService:
    """Normalize safe activity events from existing read-only sources."""

    def __init__(
        self,
        db_manager: DatabaseManager | None = None,
        auth_repo: AuthRepository | None = None,
        execution_log_service: ExecutionLogService | None = None,
    ):
        self.db = db_manager or DatabaseManager.get_instance()
        self.auth_repo = auth_repo or AuthRepository(self.db)
        self.execution_logs = execution_log_service or ExecutionLogService()

    def list_activity(
        self,
        *,
        target_user_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        family: str | None = None,
        status: str | None = None,
        entity_type: str | None = None,
        actor_type: str | None = None,
        q: str | None = None,
        include_system: bool = False,
        include_admin: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        date_to = date_to or datetime.now()
        date_from = date_from or (date_to - timedelta(days=1))
        events: list[dict[str, Any]] = []
        events.extend(self._execution_log_events(target_user_id=target_user_id, date_from=date_from, date_to=date_to))
        events.extend(self._analysis_events(target_user_id=target_user_id, date_from=date_from, date_to=date_to))
        if target_user_id:
            events.extend(self._session_events(target_user_id=target_user_id, date_from=date_from, date_to=date_to))

        filtered = [
            event
            for event in events
            if self._matches(
                event,
                family=family,
                status=status,
                entity_type=entity_type,
                actor_type=actor_type,
                q=q,
                include_system=include_system,
                include_admin=include_admin,
            )
        ]
        filtered.sort(key=lambda item: (str(item.get("timestamp") or ""), str(item.get("id") or "")), reverse=True)
        total = len(filtered)
        start = max(0, int(offset))
        return filtered[start:start + max(1, int(limit))], total

    def _execution_log_events(
        self,
        *,
        target_user_id: str | None,
        date_from: datetime,
        date_to: datetime,
    ) -> list[dict[str, Any]]:
        items, _ = self.execution_logs.list_business_events(
            user_id=target_user_id,
            date_from=date_from,
            date_to=date_to,
            limit=200,
            offset=0,
        )
        events: list[dict[str, Any]] = []
        for item in items:
            user_id = str(item.get("userId") or target_user_id or "").strip() or None
            if target_user_id and user_id != target_user_id:
                continue
            started_at = str(item.get("startedAt") or item.get("finishedAt") or "")
            if not started_at:
                continue
            normalized_status = _status(item.get("status"))
            raw_event_id = str(item.get("id") or "")
            family = str(item.get("category") or "system").strip() or "system"
            action = str(item.get("type") or item.get("eventType") or item.get("event") or f"{family}.event")
            request_hash = hash_reference(item.get("requestId"))
            session_hash = hash_reference(raw_event_id)
            events.append(
                {
                    "id": hash_reference(f"execution:{raw_event_id}") or "sha256:unknown",
                    "timestamp": started_at,
                    "actor": {
                        "type": str(item.get("actorType") or "unknown"),
                        "user_id": user_id if item.get("actorType") == "user" else None,
                        "label": item.get("actorLabel"),
                        "request_id_hash": request_hash,
                    },
                    "target_user": {"id": user_id, "label": None},
                    "family": family,
                    "action": action,
                    "entity": {
                        "type": self._entity_type_from_business_event(item),
                        "id_hash": hash_reference(item.get("recordId") or item.get("analysisType") or raw_event_id),
                        "label": sanitize_message(str(item.get("subject") or item.get("summary") or ""))[:160] or None,
                        "symbol": item.get("symbol"),
                        "market": item.get("market"),
                        "source_table": "execution_log_sessions",
                    },
                    "status": normalized_status,
                    "outcome": _outcome(normalized_status, item.get("status")),
                    "request_id_hash": request_hash,
                    "session_id_hash": session_hash,
                    "source": {
                        "kind": "execution_log_business_event",
                        "table": "execution_log_sessions",
                        "confidence": "confirmed" if user_id else "unknown",
                    },
                    "redacted_metadata": sanitize_metadata(
                        {
                            "provider": item.get("provider"),
                            "route": item.get("route"),
                            "endpoint": item.get("endpoint"),
                            "reason": item.get("reason"),
                            "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
                        }
                    ),
                    "log_links": [{"kind": "admin_logs.business_event", "id_hash": session_hash}] if session_hash else [],
                }
            )
        return events

    def _analysis_events(
        self,
        *,
        target_user_id: str | None,
        date_from: datetime,
        date_to: datetime,
    ) -> list[dict[str, Any]]:
        with self.db.get_session() as session:
            conditions = [AnalysisHistory.created_at >= date_from, AnalysisHistory.created_at <= date_to]
            if target_user_id:
                conditions.append(AnalysisHistory.owner_id == target_user_id)
            from sqlalchemy import and_, desc, select

            rows = session.execute(
                select(AnalysisHistory)
                .where(and_(*conditions))
                .order_by(desc(AnalysisHistory.created_at), desc(AnalysisHistory.id))
                .limit(200)
            ).scalars().all()

        events: list[dict[str, Any]] = []
        for row in rows:
            owner_id = str(getattr(row, "owner_id", "") or "").strip() or None
            if target_user_id and owner_id != target_user_id:
                continue
            summary = sanitize_message(str(getattr(row, "analysis_summary", "") or ""))[:160]
            events.append(
                {
                    "id": hash_reference(f"analysis:{getattr(row, 'id', '')}") or "sha256:unknown",
                    "timestamp": _iso(getattr(row, "created_at", None)) or datetime.now().isoformat(),
                    "actor": {"type": "user", "user_id": owner_id, "label": None},
                    "target_user": {"id": owner_id, "label": None},
                    "family": "analysis",
                    "action": "analysis.completed",
                    "entity": {
                        "type": "analysis_history",
                        "id_hash": hash_reference(getattr(row, "id", None)),
                        "label": f"{getattr(row, 'code', '')} {getattr(row, 'report_type', '')}".strip() or None,
                        "symbol": getattr(row, "code", None),
                        "source_table": "analysis_history",
                    },
                    "status": "success",
                    "outcome": "ok",
                    "request_id_hash": hash_reference(getattr(row, "query_id", None)),
                    "session_id_hash": None,
                    "source": {
                        "kind": "analysis_history",
                        "table": "analysis_history",
                        "confidence": "confirmed",
                    },
                    "redacted_metadata": sanitize_metadata(
                        {
                            "reportType": getattr(row, "report_type", None),
                            "summary": summary,
                            "isTest": bool(getattr(row, "is_test", False)),
                        }
                    ),
                    "log_links": [],
                }
            )
        return events

    def _session_events(
        self,
        *,
        target_user_id: str,
        date_from: datetime,
        date_to: datetime,
    ) -> list[dict[str, Any]]:
        rows = [
            row
            for row in self.auth_repo.list_app_user_sessions(target_user_id)
            if isinstance(getattr(row, "created_at", None), datetime)
            and date_from <= getattr(row, "created_at") <= date_to
        ]
        events: list[dict[str, Any]] = []
        for row in rows:
            session_hash = hash_reference(getattr(row, "session_id", None))
            events.append(
                {
                    "id": hash_reference(f"auth_session:{getattr(row, 'session_id', '')}") or "sha256:unknown",
                    "timestamp": _iso(getattr(row, "created_at", None)) or datetime.now().isoformat(),
                    "actor": {"type": "user", "user_id": target_user_id, "session_id_hash": session_hash},
                    "target_user": {"id": target_user_id, "label": None},
                    "family": "auth",
                    "action": "auth.session.created",
                    "entity": {
                        "type": "auth_session",
                        "id_hash": session_hash,
                        "label": "Session created",
                        "source_table": "app_user_sessions",
                    },
                    "status": "success",
                    "outcome": "ok",
                    "session_id_hash": session_hash,
                    "source": {
                        "kind": "auth_session_snapshot",
                        "table": "app_user_sessions",
                        "confidence": "confirmed",
                    },
                    "redacted_metadata": {},
                    "log_links": [],
                }
            )
        return events

    @staticmethod
    def _matches(
        event: dict[str, Any],
        *,
        family: str | None,
        status: str | None,
        entity_type: str | None,
        actor_type: str | None,
        q: str | None,
        include_system: bool,
        include_admin: bool,
    ) -> bool:
        actor = event.get("actor") if isinstance(event.get("actor"), dict) else {}
        entity = event.get("entity") if isinstance(event.get("entity"), dict) else {}
        source = event.get("source") if isinstance(event.get("source"), dict) else {}

        if not include_system and actor.get("type") == "system":
            return False
        if not include_admin and actor.get("type") == "admin":
            return False
        if family and event.get("family") != family:
            return False
        if status and event.get("status") != _status(status):
            return False
        if entity_type and entity.get("type") != entity_type:
            return False
        if actor_type and actor.get("type") != actor_type:
            return False
        if q:
            needle = q.lower()
            haystack = " ".join(
                str(value or "")
                for value in (
                    event.get("family"),
                    event.get("action"),
                    entity.get("label"),
                    entity.get("symbol"),
                    source.get("kind"),
                    event.get("status"),
                )
            ).lower()
            if needle not in haystack:
                return False
        return True

    @staticmethod
    def _entity_type_from_business_event(item: dict[str, Any]) -> str:
        if item.get("analysisType") or item.get("category") == "analysis":
            return "analysis_history"
        if item.get("scannerId") or item.get("category") == "scanner":
            return "scanner_run"
        if item.get("backtestId") or item.get("category") == "backtest":
            return "backtest_run"
        if item.get("category") == "portfolio":
            return "portfolio_activity"
        if item.get("category") == "admin":
            return "admin_view"
        return str(item.get("category") or "execution_log_event")


__all__ = ["AdminActivityService", "hash_reference"]
