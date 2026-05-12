# -*- coding: utf-8 -*-
"""Safe read-only projections for admin user directory APIs."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Iterable, Optional

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
    ) -> tuple[list[dict[str, Any]], int]:
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
            filtered.sort(
                key=lambda item: (
                    str(item.get("username") or "").lower(),
                    str(item.get("id") or ""),
                ),
                reverse=(sort == "username_desc"),
            )
        elif sort == "last_seen_asc":
            filtered.sort(key=lambda item: (str(item.get("last_seen_at") or ""), str(item.get("id") or "")))
        elif sort == "last_seen_desc":
            filtered.sort(
                key=lambda item: (str(item.get("last_seen_at") or ""), str(item.get("id") or "")),
                reverse=True,
            )
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
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
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

    def _project_user(self, user: Any, sessions: list[Any]) -> dict[str, Any]:
        password_hash = str(getattr(user, "password_hash", "") or "")
        session_summary = self._session_summary(sessions)
        user_id = str(getattr(user, "id", ""))
        return {
            "id": user_id,
            "username": str(getattr(user, "username", "")),
            "display_name": getattr(user, "display_name", None),
            "role": str(getattr(user, "role", "user")),
            "is_active": bool(getattr(user, "is_active", True)),
            "created_at": _iso(getattr(user, "created_at", None)),
            "updated_at": _iso(getattr(user, "updated_at", None)),
            "password_state": "set" if password_hash.strip() else "unset",
            "last_seen_at": session_summary.get("last_seen_at"),
            "session_summary": session_summary,
            "risk_badges": self._risk_badges(user, session_summary),
            "links": {
                "self": f"/api/v1/admin/users/{user_id}",
                "admin_logs": f"/api/v1/admin/logs?user_id={user_id}",
                "activity": f"/api/v1/admin/users/{user_id}/activity",
                "portfolio": None,
                "analysis": None,
                "scanner": None,
                "backtest": None,
            },
        }

    def _project_session(self, session: Any) -> dict[str, Any]:
        status = _session_status(session, datetime.now())
        return {
            "session_handle": _session_handle(str(getattr(session, "session_id", ""))),
            "status": status,
            "created_at": _iso(getattr(session, "created_at", None)),
            "last_seen_at": _iso(getattr(session, "last_seen_at", None)),
            "expires_at": _iso(getattr(session, "expires_at", None)),
            "revoked_at": _iso(getattr(session, "revoked_at", None)),
        }

    def _session_summary(self, sessions: Iterable[Any]) -> dict[str, Any]:
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
        return {
            "active_count": active_count,
            "expired_count": expired_count,
            "revoked_count": revoked_count,
            "last_seen_at": _iso(last_seen_at),
            "next_expires_at": _iso(next_expires_at),
        }

    def _risk_badges(self, user: Any, summary: dict[str, Any]) -> list[dict[str, Any]]:
        badges: list[dict[str, Any]] = []
        if str(getattr(user, "role", "")) == "admin":
            badges.append({"code": "admin_account", "label": "Admin account", "severity": "info", "source": "auth"})
        if not bool(getattr(user, "is_active", True)):
            badges.append({"code": "inactive_account", "label": "Inactive account", "severity": "warning", "source": "auth"})
        if not str(getattr(user, "password_hash", "") or "").strip():
            badges.append({"code": "password_unset", "label": "Password unset", "severity": "warning", "source": "auth"})
        total_sessions = (
            int(summary.get("active_count", 0))
            + int(summary.get("expired_count", 0))
            + int(summary.get("revoked_count", 0))
        )
        if total_sessions == 0:
            badges.append({"code": "sessionless", "label": "No sessions", "severity": "info", "source": "session"})
        elif int(summary.get("active_count", 0)) == 0 and int(summary.get("expired_count", 0)) > 0:
            badges.append(
                {"code": "all_sessions_expired", "label": "All sessions expired", "severity": "info", "source": "session"}
            )
        if int(summary.get("revoked_count", 0)) > 0:
            badges.append(
                {"code": "revoked_sessions_present", "label": "Revoked sessions present", "severity": "info", "source": "session"}
            )
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
            return lambda item: (str(item.get("updated_at") or ""), str(item.get("id") or ""))
        if sort.startswith("created_at"):
            return lambda item: (str(item.get("created_at") or ""), str(item.get("id") or ""))
        return lambda item: (str(item.get("created_at") or ""), str(item.get("id") or ""))

    @staticmethod
    def _matches_user(
        item: dict[str, Any],
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
            haystack = " ".join(
                [
                    str(item.get("id") or ""),
                    str(item.get("username") or ""),
                    str(item.get("display_name") or ""),
                ]
            ).lower()
            if needle not in haystack:
                return False
        if role and item.get("role") != role:
            return False
        if active is not None and item.get("is_active") is not active:
            return False
        if status == "active" and not item.get("is_active"):
            return False
        if status == "inactive" and item.get("is_active"):
            return False
        if status == "needs_password" and item.get("password_state") != "unset":
            return False
        summary = item.get("session_summary") if isinstance(item.get("session_summary"), dict) else {}
        total_sessions = (
            int(summary.get("active_count", 0))
            + int(summary.get("expired_count", 0))
            + int(summary.get("revoked_count", 0))
        )
        if status == "sessionless" and total_sessions > 0:
            return False
        if status == "stale_session" and int(summary.get("active_count", 0)) > 0:
            return False
        created_at = _parse_iso(str(item.get("created_at") or "") or None)
        last_seen = _parse_iso(str(item.get("last_seen_at") or "") or None)
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
