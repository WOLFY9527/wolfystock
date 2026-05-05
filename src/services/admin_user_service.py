# -*- coding: utf-8 -*-
"""Safe read-only projections for admin user directory APIs."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Iterable, Optional

from api.v1.schemas.admin_users import (
    AdminDataLinks,
    AdminSessionSummary,
    AdminSessionSummaryCounts,
    AdminUserListItem,
    AdminUserRiskBadge,
)
from src.repositories.auth_repo import AuthRepository


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if isinstance(value, datetime) else None


def _session_status(session: Any, now: datetime) -> str:
    if getattr(session, "revoked_at", None) is not None:
        return "revoked"
    expires_at = getattr(session, "expires_at", None)
    if isinstance(expires_at, datetime) and expires_at <= now:
        return "expired"
    return "active"


def _session_handle(session_id: str) -> str:
    digest = hashlib.sha256(f"admin-session:{session_id}".encode("utf-8")).hexdigest()
    return f"sess_{digest[:12]}"


def _id_hash(value: str) -> str:
    digest = hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()
    return f"sha256:{digest[:16]}"


class AdminUserService:
    """Build safe user and session projections without exposing credentials."""

    def __init__(self, repo: AuthRepository | None = None):
        self.repo = repo or AuthRepository()

    def list_users(
        self,
        *,
        q: str | None = None,
        role: str | None = None,
        status: str = "all",
        active: bool | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        last_seen_from: datetime | None = None,
        last_seen_to: datetime | None = None,
        sort: str = "created_at_desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AdminUserListItem], int]:
        users = list(self.repo.list_app_users())
        sessions_by_user = self._sessions_by_user(self.repo.list_app_user_sessions())
        items = [
            self._project_user(user, sessions_by_user.get(str(getattr(user, "id", "")), []))
            for user in users
        ]
        filtered = [
            item
            for item in items
            if self._matches_user(
                item,
                q=q,
                role=role,
                status=status,
                active=active,
                created_from=created_from,
                created_to=created_to,
                last_seen_from=last_seen_from,
                last_seen_to=last_seen_to,
            )
        ]
        filtered.sort(key=self._sort_key(sort), reverse=sort.endswith("_desc"))
        if sort in {"username_asc", "username_desc"}:
            filtered.sort(key=lambda item: (item.username.lower(), item.id), reverse=(sort == "username_desc"))
        elif sort == "last_seen_asc":
            filtered.sort(key=lambda item: (item.last_seen_at or "", item.id))
        elif sort == "last_seen_desc":
            filtered.sort(key=lambda item: (item.last_seen_at or "", item.id), reverse=True)
        total = len(filtered)
        start = max(0, int(offset))
        return filtered[start:start + max(1, int(limit))], total

    def get_user_detail(
        self,
        user_id: str,
        *,
        include_sessions: bool = True,
        session_limit: int = 20,
        session_status: str = "all",
    ) -> tuple[AdminUserListItem | None, list[AdminSessionSummary]]:
        user = self.repo.get_app_user(user_id)
        if user is None:
            return None, []
        sessions = list(self.repo.list_app_user_sessions(user_id))
        item = self._project_user(user, sessions)
        if not include_sessions:
            return item, []
        summaries = [
            self._project_session(row)
            for row in sessions
            if session_status == "all" or _session_status(row, datetime.now()) == session_status
        ]
        return item, summaries[:max(1, int(session_limit))]

    def _project_user(self, user: Any, sessions: list[Any]) -> AdminUserListItem:
        password_hash = str(getattr(user, "password_hash", "") or "")
        session_summary = self._session_summary(sessions)
        user_id = str(getattr(user, "id", ""))
        return AdminUserListItem(
            id=user_id,
            username=str(getattr(user, "username", "")),
            displayName=getattr(user, "display_name", None),
            role=str(getattr(user, "role", "user")),
            isActive=bool(getattr(user, "is_active", True)),
            createdAt=_iso(getattr(user, "created_at", None)),
            updatedAt=_iso(getattr(user, "updated_at", None)),
            passwordState="set" if password_hash.strip() else "unset",
            lastSeenAt=session_summary.last_seen_at,
            sessionSummary=session_summary,
            riskBadges=self._risk_badges(user, session_summary),
            links=AdminDataLinks(
                self=f"/api/v1/admin/users/{user_id}",
                adminLogs=f"/api/v1/admin/logs?user_id={user_id}",
                activity=f"/api/v1/admin/users/{user_id}/activity",
                portfolio=None,
                analysis=None,
                scanner=None,
                backtest=None,
            ),
        )

    def _project_session(self, session: Any) -> AdminSessionSummary:
        status = _session_status(session, datetime.now())
        return AdminSessionSummary(
            sessionHandle=_session_handle(str(getattr(session, "session_id", ""))),
            status=status,
            createdAt=_iso(getattr(session, "created_at", None)),
            lastSeenAt=_iso(getattr(session, "last_seen_at", None)),
            expiresAt=_iso(getattr(session, "expires_at", None)),
            revokedAt=_iso(getattr(session, "revoked_at", None)),
        )

    def _session_summary(self, sessions: Iterable[Any]) -> AdminSessionSummaryCounts:
        now = datetime.now()
        active_count = 0
        expired_count = 0
        revoked_count = 0
        last_seen_at: datetime | None = None
        next_expires_at: datetime | None = None
        for row in sessions:
            status = _session_status(row, now)
            if status == "active":
                active_count += 1
                expires_at = getattr(row, "expires_at", None)
                if isinstance(expires_at, datetime) and (next_expires_at is None or expires_at < next_expires_at):
                    next_expires_at = expires_at
            elif status == "expired":
                expired_count += 1
            else:
                revoked_count += 1
            seen = getattr(row, "last_seen_at", None)
            if isinstance(seen, datetime) and (last_seen_at is None or seen > last_seen_at):
                last_seen_at = seen
        return AdminSessionSummaryCounts(
            activeCount=active_count,
            expiredCount=expired_count,
            revokedCount=revoked_count,
            lastSeenAt=_iso(last_seen_at),
            nextExpiresAt=_iso(next_expires_at),
        )

    def _risk_badges(self, user: Any, summary: AdminSessionSummaryCounts) -> list[AdminUserRiskBadge]:
        badges: list[AdminUserRiskBadge] = []
        if str(getattr(user, "role", "")) == "admin":
            badges.append(AdminUserRiskBadge(code="admin_account", label="Admin account", severity="info", source="auth"))
        if not bool(getattr(user, "is_active", True)):
            badges.append(AdminUserRiskBadge(code="inactive_account", label="Inactive account", severity="warning", source="auth"))
        if not str(getattr(user, "password_hash", "") or "").strip():
            badges.append(AdminUserRiskBadge(code="password_unset", label="Password unset", severity="warning", source="auth"))
        total_sessions = summary.active_count + summary.expired_count + summary.revoked_count
        if total_sessions == 0:
            badges.append(AdminUserRiskBadge(code="sessionless", label="No sessions", severity="info", source="session"))
        elif summary.active_count == 0 and summary.expired_count > 0:
            badges.append(AdminUserRiskBadge(code="all_sessions_expired", label="All sessions expired", severity="info", source="session"))
        if summary.revoked_count > 0:
            badges.append(AdminUserRiskBadge(code="revoked_sessions_present", label="Revoked sessions present", severity="info", source="session"))
        return badges

    @staticmethod
    def _sessions_by_user(sessions: Iterable[Any]) -> dict[str, list[Any]]:
        grouped: dict[str, list[Any]] = {}
        for row in sessions:
            grouped.setdefault(str(getattr(row, "user_id", "")), []).append(row)
        return grouped

    @staticmethod
    def _sort_key(sort: str):
        if sort.startswith("updated_at"):
            return lambda item: (item.updated_at or "", item.id)
        if sort.startswith("created_at"):
            return lambda item: (item.created_at or "", item.id)
        return lambda item: (item.created_at or "", item.id)

    @staticmethod
    def _matches_user(
        item: AdminUserListItem,
        *,
        q: str | None,
        role: str | None,
        status: str,
        active: bool | None,
        created_from: datetime | None,
        created_to: datetime | None,
        last_seen_from: datetime | None,
        last_seen_to: datetime | None,
    ) -> bool:
        if q:
            needle = q.lower()
            haystack = " ".join([item.id, item.username, item.display_name or ""]).lower()
            if needle not in haystack:
                return False
        if role and item.role != role:
            return False
        if active is not None and item.is_active is not active:
            return False
        if status == "active" and not item.is_active:
            return False
        if status == "inactive" and item.is_active:
            return False
        if status == "needs_password" and item.password_state != "unset":
            return False
        if status == "sessionless" and (
            item.session_summary.active_count + item.session_summary.expired_count + item.session_summary.revoked_count
        ) > 0:
            return False
        if status == "stale_session" and item.session_summary.active_count > 0:
            return False
        created_at = _parse_iso(item.created_at)
        last_seen = _parse_iso(item.last_seen_at)
        if created_from and created_at and created_at < created_from:
            return False
        if created_to and created_at and created_at > created_to:
            return False
        if last_seen_from and (last_seen is None or last_seen < last_seen_from):
            return False
        if last_seen_to and (last_seen is None or last_seen > last_seen_to):
            return False
        return True


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


__all__ = ["AdminUserService", "_id_hash", "_session_handle"]
