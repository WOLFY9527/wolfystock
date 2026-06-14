# -*- coding: utf-8 -*-
"""Bounded admin-only onboarding flow for normal private-beta users."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

from src.auth import hash_password_for_storage, safe_identifier_hash
from src.auth_context import AdminActorContext
from src.multi_user import ROLE_ADMIN, ROLE_USER
from src.repositories.auth_repo import AuthRepository
from src.services.admin_governance_audit_service import AdminGovernanceAuditService


class AdminUserOnboardingError(Exception):
    def __init__(self, *, status_code: int, error: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.error = error
        self.message = message


@dataclass(frozen=True)
class AdminUserOnboardingResult:
    target_user_id: str
    username: str
    role: str
    created: bool
    initial_password: str
    audit_event_id: str | None
    message: str


class AdminUserOnboardingService:
    """Create a normal active user through an admin-only bounded workflow."""

    def __init__(
        self,
        repo: AuthRepository | None = None,
        audit: AdminGovernanceAuditService | None = None,
    ):
        self.repo = repo or AuthRepository()
        self.audit = audit or AdminGovernanceAuditService()

    def create_user(
        self,
        *,
        actor: AdminActorContext,
        username: str,
        display_name: str | None,
        email: str | None,
        password: str | None,
        reason: str,
    ) -> AdminUserOnboardingResult:
        normalized_username = str(username or "").strip()
        normalized_email = str(email or "").strip().lower() or None
        normalized_reason = str(reason or "").strip()
        try:
            normalized_username = _normalize_username(username)
            normalized_display_name = _normalize_display_name(display_name, fallback=normalized_username)
            normalized_email = _normalize_email(email)
            normalized_reason = _normalize_reason(reason)
        except AdminUserOnboardingError as exc:
            self.record_failure_audit(
                actor=actor,
                reason_code=_audit_failure_reason_code(exc.error),
                username=normalized_username,
                email=normalized_email,
                reason=normalized_reason,
            )
            raise

        existing_user = self.repo.get_app_user_by_username(normalized_username)
        if existing_user is not None:
            self._record_audit(
                actor=actor,
                target_user_id=str(getattr(existing_user, "id", "") or "pending"),
                username=normalized_username,
                email=normalized_email,
                reason=normalized_reason,
                overall_status="failed",
                outcome="duplicate_username",
                metadata={"created": False, "reason_code": "duplicate_username"},
            )
            raise AdminUserOnboardingError(
                status_code=409,
                error="duplicate_username",
                message="Username already exists",
            ) from None

        if normalized_email:
            duplicate_email_user_id = self._find_user_id_by_email(normalized_email)
            if duplicate_email_user_id is not None:
                self._record_audit(
                    actor=actor,
                    target_user_id=duplicate_email_user_id,
                    username=normalized_username,
                    email=normalized_email,
                    reason=normalized_reason,
                    overall_status="failed",
                    outcome="duplicate_email",
                    metadata={"created": False, "reason_code": "duplicate_email"},
                )
                raise AdminUserOnboardingError(
                    status_code=409,
                    error="duplicate_email",
                    message="Email already exists",
                ) from None

        initial_password = str(password or "").strip() or _generate_initial_password()
        try:
            password_hash = hash_password_for_storage(initial_password)
        except ValueError as exc:
            self.record_failure_audit(
                actor=actor,
                reason_code="validation_error",
                username=normalized_username,
                email=normalized_email,
                reason=normalized_reason,
            )
            raise AdminUserOnboardingError(
                status_code=400,
                error="invalid_password",
                message=str(exc),
            ) from None

        user_id = f"user-{secrets.token_hex(8)}"
        user = self.repo.create_or_update_app_user(
            user_id=user_id,
            username=normalized_username,
            display_name=normalized_display_name,
            role=ROLE_USER,
            password_hash=password_hash,
            is_active=True,
        )
        if normalized_email:
            self.repo.upsert_user_notification_preferences(
                user_id=user_id,
                email=normalized_email,
                enabled=False,
                channel="email",
                discord_webhook=None,
                discord_enabled=False,
            )

        audit_event_id = self._record_audit(
            actor=actor,
            target_user_id=str(getattr(user, "id", user_id) or user_id),
            username=normalized_username,
            email=normalized_email,
            reason=normalized_reason,
            overall_status="completed",
            outcome="success",
            metadata={
                "created": True,
                "role": ROLE_USER,
                "active": True,
                "password_delivery": "returned_once",
                "email_stored": bool(normalized_email),
            },
        )
        return AdminUserOnboardingResult(
            target_user_id=str(getattr(user, "id", user_id) or user_id),
            username=normalized_username,
            role=ROLE_USER,
            created=True,
            initial_password=initial_password,
            audit_event_id=audit_event_id,
            message="User created",
        )

    def record_failure_audit(
        self,
        *,
        actor: AdminActorContext,
        reason_code: str,
        username: str | None = None,
        email: str | None = None,
        reason: str | None = None,
        target_user_id: str = "pending",
    ) -> str | None:
        normalized_reason_code = _audit_failure_reason_code(reason_code)
        return self._record_audit(
            actor=actor,
            target_user_id=target_user_id,
            username=str(username or "").strip(),
            email=str(email or "").strip().lower() or None,
            reason=str(reason or "").strip(),
            overall_status="failed",
            outcome=normalized_reason_code,
            metadata={
                "created": False,
                "reason_code": normalized_reason_code,
            },
        )

    def _find_user_id_by_email(self, email: str) -> str | None:
        for user in self.repo.list_app_users():
            user_id = str(getattr(user, "id", "") or "").strip()
            if not user_id:
                continue
            preferences = self.repo.get_user_notification_preferences(user_id)
            existing_email = str(preferences.get("email") or "").strip().lower()
            if existing_email and existing_email == email.lower():
                return user_id
        return None

    def _record_audit(
        self,
        *,
        actor: AdminActorContext,
        target_user_id: str,
        username: str,
        email: str | None,
        reason: str,
        overall_status: str,
        outcome: str,
        metadata: dict[str, Any],
    ) -> str | None:
        return self.audit.record_action(
            action="admin_user_onboarding.user_created",
            actor=actor,
            target_user_id=target_user_id,
            reason=safe_identifier_hash(reason, prefix="reason") or "reason:redacted",
            subsystem="security",
            destructive=False,
            overall_status=overall_status,
            metadata={
                "route_family": "admin_user_onboarding",
                "outcome": outcome,
                "username_hash": safe_identifier_hash(username, prefix="acct"),
                "email_hash": safe_identifier_hash(email, prefix="email") if email else None,
                "reason_present": bool(reason),
                **metadata,
            },
        )


def _normalize_username(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise AdminUserOnboardingError(status_code=400, error="validation_error", message="username is required")
    if len(normalized) > 128:
        raise AdminUserOnboardingError(status_code=400, error="validation_error", message="username is too long")
    if normalized.lower() == "admin":
        raise AdminUserOnboardingError(
            status_code=400,
            error="role_not_allowed",
            message="Bootstrap admin username is not allowed for this flow",
        )
    return normalized


def _normalize_display_name(value: str | None, *, fallback: str) -> str:
    normalized = str(value or "").strip()
    if normalized and len(normalized) > 128:
        raise AdminUserOnboardingError(status_code=400, error="validation_error", message="display_name is too long")
    return normalized or fallback


def _normalize_email(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if len(normalized) > 320 or "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise AdminUserOnboardingError(status_code=400, error="validation_error", message="Invalid email")
    return normalized.lower()


def _normalize_reason(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise AdminUserOnboardingError(status_code=400, error="reason_required", message="reason is required")
    if len(normalized) > 500:
        raise AdminUserOnboardingError(status_code=400, error="validation_error", message="reason is too long")
    return normalized


def _audit_failure_reason_code(error: str) -> str:
    normalized = str(error or "").strip()
    if normalized in {
        "admin_reauth_required",
        "duplicate_username",
        "duplicate_email",
        "role_not_allowed",
        "reserved_username",
        "permission_denied",
        "admin_required",
    }:
        return normalized
    return "validation_error"


def _generate_initial_password() -> str:
    return f"Beta-{secrets.token_urlsafe(12)}9!"


__all__ = [
    "AdminUserOnboardingError",
    "AdminUserOnboardingResult",
    "AdminUserOnboardingService",
]
