# -*- coding: utf-8 -*-
"""Repository helpers for auth-facing app user, session, and preferences data."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from src.storage import DatabaseManager


class AuthRepository:
    """Narrow persistence seam for auth endpoint data access."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def get_user_notification_preferences(self, user_id: str) -> Dict[str, Any]:
        return self.db.get_user_notification_preferences(user_id)

    def upsert_user_notification_preferences(
        self,
        user_id: str,
        *,
        email: str | None,
        enabled: bool,
        channel: str,
        discord_webhook: str | None,
        discord_enabled: bool,
    ) -> Dict[str, Any]:
        return self.db.upsert_user_notification_preferences(
            user_id,
            email=email,
            enabled=enabled,
            channel=channel,
            discord_webhook=discord_webhook,
            discord_enabled=discord_enabled,
        )

    def create_app_user_session(
        self,
        *,
        session_id: str,
        user_id: str,
        expires_at: datetime,
    ):
        return self.db.create_app_user_session(
            session_id=session_id,
            user_id=user_id,
            expires_at=expires_at,
        )

    def ensure_bootstrap_admin_user(self):
        return self.db.ensure_bootstrap_admin_user()

    def get_app_user(self, user_id: str):
        return self.db.get_app_user(user_id)

    def get_app_user_by_username(self, username: str):
        return self.db.get_app_user_by_username(username)

    def reconcile_legacy_app_user_for_login(self, *, username: str, password: str):
        """Sync a legacy SQLite app-user into the active identity store after password proof."""
        if not getattr(self.db, "_phase_a_enabled", False) or getattr(self.db, "_phase_a_store", None) is None:
            return None
        get_legacy_user = getattr(self.db, "_sqlite_get_app_user_by_username", None)
        phase_a_store = getattr(self.db, "_phase_a_store", None)
        sync_legacy_user = getattr(self.db, "_sync_phase_a_user_from_legacy", None)
        if not callable(get_legacy_user) or not callable(sync_legacy_user) or phase_a_store is None:
            return None

        legacy_row = get_legacy_user(username)
        if legacy_row is None or not getattr(legacy_row, "is_active", True):
            return None
        if str(getattr(legacy_row, "role", "") or "").strip().lower() == "admin":
            return None

        from src.auth import verify_password_hash_string

        if not verify_password_hash_string(password, getattr(legacy_row, "password_hash", None)):
            return None
        phase_row = phase_a_store.get_app_user_by_username(username)
        if phase_row is not None:
            return phase_a_store.upsert_app_user(
                user_id=str(phase_row.id),
                username=str(legacy_row.username),
                role=str(legacy_row.role),
                display_name=getattr(legacy_row, "display_name", None),
                password_hash=getattr(legacy_row, "password_hash", None),
                mfa_enabled=bool(getattr(legacy_row, "mfa_enabled", False)),
                mfa_secret_ref=getattr(legacy_row, "mfa_secret_ref", None),
                mfa_recovery_codes_hash=getattr(legacy_row, "mfa_recovery_codes_hash", None),
                mfa_created_at=getattr(legacy_row, "mfa_created_at", None),
                mfa_enabled_at=getattr(legacy_row, "mfa_enabled_at", None),
                mfa_last_verified_at=getattr(legacy_row, "mfa_last_verified_at", None),
                is_active=bool(getattr(legacy_row, "is_active", True)),
                created_at=getattr(phase_row, "created_at", None),
            )
        return sync_legacy_user(legacy_row) or legacy_row

    def update_app_user_mfa(
        self,
        *,
        user_id: str,
        mfa_enabled: bool,
        mfa_secret_ref: str | None = None,
        mfa_recovery_codes_hash: str | None = None,
        mfa_created_at: datetime | None = None,
        mfa_enabled_at: datetime | None = None,
        mfa_last_verified_at: datetime | None = None,
    ):
        return self.db.update_app_user_mfa(
            user_id=user_id,
            mfa_enabled=mfa_enabled,
            mfa_secret_ref=mfa_secret_ref,
            mfa_recovery_codes_hash=mfa_recovery_codes_hash,
            mfa_created_at=mfa_created_at,
            mfa_enabled_at=mfa_enabled_at,
            mfa_last_verified_at=mfa_last_verified_at,
        )

    def list_app_users(self):
        return self.db.list_app_users()

    def list_app_user_sessions(self, user_id: str | None = None):
        return self.db.list_app_user_sessions(user_id)

    def list_admin_role_capabilities(self, role_key: str):
        return self.db.list_admin_role_capabilities(role_key)

    def list_admin_user_roles(self, user_id: str):
        return self.db.list_admin_user_roles(user_id)

    def list_admin_capabilities_for_user(self, user_id: str):
        return self.db.list_admin_capabilities_for_user(user_id)

    def create_or_update_app_user(
        self,
        *,
        user_id: str,
        username: str,
        display_name: str,
        role: str,
        password_hash: str | None,
        is_active: bool,
    ):
        return self.db.create_or_update_app_user(
            user_id=user_id,
            username=username,
            display_name=display_name,
            role=role,
            password_hash=password_hash,
            is_active=is_active,
        )

    def revoke_app_user_session(self, session_id: str) -> bool:
        session_row = self.db.get_app_user_session(session_id)
        revoked = self.db.revoke_app_user_session(session_id)
        if revoked and session_row is not None:
            from src.auth import clear_admin_session_reauth

            clear_admin_session_reauth(
                user_id=str(getattr(session_row, "user_id", "") or ""),
                session_id=str(session_id or ""),
            )
        return revoked

    def revoke_all_app_user_sessions(self, user_id: str) -> int:
        session_rows = list(self.db.list_app_user_sessions(user_id))
        revoked = self.db.revoke_all_app_user_sessions(user_id)
        if revoked:
            from src.auth import clear_admin_session_reauth

            for row in session_rows:
                if getattr(row, "revoked_at", None) is None:
                    clear_admin_session_reauth(
                        user_id=str(getattr(row, "user_id", "") or ""),
                        session_id=str(getattr(row, "session_id", "") or ""),
                    )
        return revoked
