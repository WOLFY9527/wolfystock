# -*- coding: utf-8 -*-
"""Limited admin account security controls built on existing auth primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from src.auth_context import AdminActorContext
from src.repositories.auth_repo import AuthRepository
from src.services.admin_governance_audit_service import AdminGovernanceAuditService


class AdminSecurityError(Exception):
    def __init__(self, *, status_code: int, error: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.error = error
        self.message = message


@dataclass(frozen=True)
class AdminSecurityResult:
    target_user_id: str
    action: Literal["disable", "enable", "revoke_sessions"]
    status: Literal["completed", "blocked", "failed"]
    changed: bool
    sessions_revoked: int
    audit_event_id: str | None
    message: str


class AdminSecurityService:
    """Perform bounded account disable/enable/session revocation actions."""

    def __init__(
        self,
        repo: AuthRepository | None = None,
        audit: AdminGovernanceAuditService | None = None,
    ):
        self.repo = repo or AuthRepository()
        self.audit = audit or AdminGovernanceAuditService()

    def disable_user(
        self,
        *,
        target_user_id: str,
        actor: AdminActorContext,
        reason: str,
        revoke_sessions: bool = False,
    ) -> AdminSecurityResult:
        return self._execute(
            action="disable",
            event="admin_security.account_disabled",
            target_user_id=target_user_id,
            actor=actor,
            reason=reason,
            revoke_sessions=revoke_sessions,
        )

    def enable_user(
        self,
        *,
        target_user_id: str,
        actor: AdminActorContext,
        reason: str,
    ) -> AdminSecurityResult:
        return self._execute(
            action="enable",
            event="admin_security.account_enabled",
            target_user_id=target_user_id,
            actor=actor,
            reason=reason,
            revoke_sessions=False,
        )

    def revoke_sessions(
        self,
        *,
        target_user_id: str,
        actor: AdminActorContext,
        reason: str,
    ) -> AdminSecurityResult:
        return self._execute(
            action="revoke_sessions",
            event="admin_security.sessions_revoked",
            target_user_id=target_user_id,
            actor=actor,
            reason=reason,
            revoke_sessions=True,
        )

    def _execute(
        self,
        *,
        action: Literal["disable", "enable", "revoke_sessions"],
        event: str,
        target_user_id: str,
        actor: AdminActorContext,
        reason: str,
        revoke_sessions: bool,
    ) -> AdminSecurityResult:
        normalized_target = _normalize_user_id(target_user_id)
        normalized_reason = _normalize_reason(reason)
        target_user = self.repo.get_app_user(normalized_target)
        if target_user is None:
            audit_id = self._record_audit(
                event=event,
                actor=actor,
                target_user_id=normalized_target,
                reason=normalized_reason,
                outcome="not_found",
                overall_status="failed",
                metadata={"changed": False, "sessions_revoked": 0},
            )
            raise AdminSecurityError(
                status_code=404,
                error="not_found",
                message="User not found",
            ) from None

        try:
            if action == "disable":
                self._guard_disable(target_user=target_user, actor=actor)
                was_active = bool(getattr(target_user, "is_active", True))
                if was_active:
                    self._save_user(target_user, is_active=False)
                revoked = self.repo.revoke_all_app_user_sessions(normalized_target) if revoke_sessions else 0
                audit_id = self._record_audit(
                    event=event,
                    actor=actor,
                    target_user_id=normalized_target,
                    reason=normalized_reason,
                    outcome="success",
                    overall_status="completed",
                    metadata={"changed": was_active, "sessions_revoked": revoked},
                )
                return AdminSecurityResult(
                    target_user_id=normalized_target,
                    action="disable",
                    status="completed",
                    changed=was_active,
                    sessions_revoked=revoked,
                    audit_event_id=audit_id,
                    message="User disabled",
                )

            if action == "enable":
                was_inactive = not bool(getattr(target_user, "is_active", True))
                if was_inactive:
                    self._save_user(target_user, is_active=True)
                audit_id = self._record_audit(
                    event=event,
                    actor=actor,
                    target_user_id=normalized_target,
                    reason=normalized_reason,
                    outcome="success",
                    overall_status="completed",
                    metadata={"changed": was_inactive, "sessions_revoked": 0},
                )
                return AdminSecurityResult(
                    target_user_id=normalized_target,
                    action="enable",
                    status="completed",
                    changed=was_inactive,
                    sessions_revoked=0,
                    audit_event_id=audit_id,
                    message="User enabled",
                )

            revoked = self.repo.revoke_all_app_user_sessions(normalized_target)
            audit_id = self._record_audit(
                event=event,
                actor=actor,
                target_user_id=normalized_target,
                reason=normalized_reason,
                outcome="success",
                overall_status="completed",
                metadata={"changed": revoked > 0, "sessions_revoked": revoked, "scope": "all"},
            )
            return AdminSecurityResult(
                target_user_id=normalized_target,
                action="revoke_sessions",
                status="completed",
                changed=revoked > 0,
                sessions_revoked=revoked,
                audit_event_id=audit_id,
                message="User sessions revoked",
            )
        except AdminSecurityError as exc:
            self._record_audit(
                event=event,
                actor=actor,
                target_user_id=normalized_target,
                reason=normalized_reason,
                outcome=exc.error,
                overall_status="failed",
                metadata={"changed": False, "sessions_revoked": 0},
            )
            raise

    def _guard_disable(self, *, target_user: Any, actor: AdminActorContext) -> None:
        target_user_id = str(getattr(target_user, "id", "") or "").strip()
        if target_user_id == str(actor.user_id or "").strip():
            raise AdminSecurityError(
                status_code=403,
                error="self_disable_blocked",
                message="Admins cannot disable their own account",
            )
        if str(getattr(target_user, "role", "") or "").strip() != "admin":
            return
        active_admin_count = sum(
            1
            for user in self.repo.list_app_users()
            if str(getattr(user, "role", "") or "").strip() == "admin"
            and bool(getattr(user, "is_active", True))
        )
        if bool(getattr(target_user, "is_active", True)) and active_admin_count <= 1:
            raise AdminSecurityError(
                status_code=409,
                error="last_admin_disable_blocked",
                message="Cannot disable the last active admin account",
            )

    def _save_user(self, user: Any, *, is_active: bool) -> Any:
        return self.repo.create_or_update_app_user(
            user_id=str(getattr(user, "id")),
            username=str(getattr(user, "username")),
            display_name=getattr(user, "display_name", None) or str(getattr(user, "username")),
            role=str(getattr(user, "role", "user")),
            password_hash=getattr(user, "password_hash", None),
            is_active=is_active,
        )

    def _record_audit(
        self,
        *,
        event: str,
        actor: AdminActorContext,
        target_user_id: str,
        reason: str,
        outcome: str,
        overall_status: str,
        metadata: dict[str, Any],
    ) -> str | None:
        return self.audit.record_action(
            action=event,
            actor=actor,
            target_user_id=target_user_id,
            reason=reason,
            subsystem="security",
            destructive=True,
            overall_status=overall_status,
            metadata={
                "outcome": outcome,
                "route_family": "admin_security",
                **metadata,
            },
        )


def _normalize_user_id(user_id: str) -> str:
    normalized = str(user_id or "").strip()
    if not normalized or len(normalized) > 64:
        raise AdminSecurityError(status_code=400, error="validation_error", message="Invalid user_id")
    return normalized


def _normalize_reason(reason: str) -> str:
    normalized = str(reason or "").strip()
    if not normalized:
        raise AdminSecurityError(status_code=400, error="reason_required", message="reason is required")
    if len(normalized) > 500:
        raise AdminSecurityError(status_code=400, error="validation_error", message="reason is too long")
    return normalized
