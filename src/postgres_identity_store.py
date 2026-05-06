# -*- coding: utf-8 -*-
"""Narrow Phase A persistence adapter for PostgreSQL-backed identity/preferences."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

from sqlalchemy import (
    Column,
    Index,
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    delete,
    select,
)
from sqlalchemy.orm import Session, declarative_base

from src.multi_user import BOOTSTRAP_ADMIN_USER_ID, ROLE_USER, normalize_role
from src.postgres_store_utils import (
    apply_baseline_schema,
    baseline_sql_doc_path,
    build_schema_apply_report,
    create_session_factory,
    create_store_engine,
    describe_store_runtime,
    load_baseline_sql_statements,
    managed_session_scope,
)

logger = logging.getLogger(__name__)

PhaseABase = declarative_base()

_BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")
_PHASE_A_TABLES = {
    "app_users",
    "app_user_sessions",
    "guest_sessions",
    "user_preferences",
    "notification_targets",
}
_PHASE_A_INDEXES = {
    "idx_app_users_role_active",
    "ix_app_user_sessions_last_seen_at",
    "idx_app_user_sessions_user_expiry",
    "idx_app_user_sessions_user_revoked_expiry",
    "idx_guest_sessions_expires",
    "idx_guest_sessions_started",
    "idx_notification_targets_user_channel",
}


class PhaseAAppUser(PhaseABase):
    __tablename__ = "app_users"

    id = Column(String(64), primary_key=True)
    username = Column(String(128), nullable=False, unique=True, index=True)
    display_name = Column(String(128))
    role = Column(String(16), nullable=False, default=ROLE_USER, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    password_hash = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)

    __table_args__ = (
        Index("idx_app_users_role_active", "role", "is_active"),
    )


class PhaseAAppUserSession(PhaseABase):
    __tablename__ = "app_user_sessions"

    session_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("app_users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    last_seen_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), index=True)

    __table_args__ = (
        Index("idx_app_user_sessions_user_expiry", "user_id", "expires_at"),
        Index("idx_app_user_sessions_user_revoked_expiry", "user_id", "revoked_at", "expires_at"),
    )


class PhaseAGuestSession(PhaseABase):
    __tablename__ = "guest_sessions"

    session_id = Column(String(64), primary_key=True)
    session_kind = Column(String(32), nullable=False, default="anonymous_preview")
    status = Column(String(16), nullable=False, default="active")
    started_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    last_seen_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    origin_json = Column(JSON, nullable=False, default=dict)
    transient_state_json = Column(JSON, nullable=False, default=dict)

    __table_args__ = (
        Index("idx_guest_sessions_expires", "expires_at"),
        Index("idx_guest_sessions_started", "started_at"),
        CheckConstraint(
            "status in ('active', 'expired', 'revoked')",
            name="ck_phase_a_guest_sessions_status",
        ),
    )


class PhaseAUserPreference(PhaseABase):
    __tablename__ = "user_preferences"

    user_id = Column(String(64), ForeignKey("app_users.id"), primary_key=True)
    ui_locale = Column(String(32))
    report_language = Column(String(16))
    market_color_convention = Column(String(32))
    ui_preferences_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)


class PhaseANotificationTarget(PhaseABase):
    __tablename__ = "notification_targets"

    id = Column(_BIGINT_PK, primary_key=True, autoincrement=True)
    user_id = Column(String(64), ForeignKey("app_users.id"), nullable=False, index=True)
    channel_type = Column(String(16), nullable=False)
    target_value = Column(Text, nullable=False)
    target_secret_json = Column(JSON, nullable=False, default=dict)
    is_default = Column(Boolean, nullable=False, default=False)
    is_enabled = Column(Boolean, nullable=False, default=True)
    delivery_metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "channel_type",
            "target_value",
            name="uq_phase_a_notification_targets_user_channel_value",
        ),
        CheckConstraint(
            "channel_type in ('email', 'discord', 'telegram', 'webhook', 'wechat', 'feishu')",
            name="ck_phase_a_notification_targets_channel_type",
        ),
    )


def _phase_a_sql_doc_path() -> Path:
    return baseline_sql_doc_path()


def load_phase_a_sql_statements() -> list[str]:
    """Extract only the Phase A DDL statements from the authoritative baseline SQL doc."""
    return load_baseline_sql_statements(
        table_names=_PHASE_A_TABLES,
        index_names=_PHASE_A_INDEXES,
        source_path=_phase_a_sql_doc_path(),
    )


class PostgresPhaseAStore:
    """Narrow storage adapter for the PostgreSQL Phase A baseline."""
    SCHEMA_KEY = "phase_a"
    MODE = "bridge_shadow"
    EXPECTED_TABLES = _PHASE_A_TABLES
    EXPECTED_INDEXES = _PHASE_A_INDEXES
    EXPECTED_CONSTRAINTS: tuple[tuple[str, str], ...] = ()

    def __init__(self, db_url: str, *, auto_apply_schema: bool = True):
        if not str(db_url or "").strip():
            raise ValueError("db_url is required for PostgresPhaseAStore")

        self.db_url = str(db_url).strip()
        self._engine = create_store_engine(self.db_url)
        self._SessionLocal = create_session_factory(self._engine)
        self._last_schema_apply_report = build_schema_apply_report(
            schema_key=self.SCHEMA_KEY,
            status="skipped" if not auto_apply_schema else "pending",
            source_path=_phase_a_sql_doc_path(),
            dialect=self._engine.dialect.name,
            skip_reason="auto_apply_schema_disabled" if not auto_apply_schema else None,
        )

        if auto_apply_schema:
            self.apply_schema()

    def dispose(self) -> None:
        self._engine.dispose()

    def apply_schema(self) -> None:
        try:
            self._last_schema_apply_report = apply_baseline_schema(
                self._engine,
                schema_key=self.SCHEMA_KEY,
                metadata=PhaseABase.metadata,
                table_names=self.EXPECTED_TABLES,
                index_names=self.EXPECTED_INDEXES,
                constraint_names=self.EXPECTED_CONSTRAINTS,
                source_path=_phase_a_sql_doc_path(),
            )
        except Exception as exc:
            self._last_schema_apply_report = build_schema_apply_report(
                schema_key=self.SCHEMA_KEY,
                status="failed",
                source_path=_phase_a_sql_doc_path(),
                dialect=self._engine.dialect.name,
                error=f"{exc.__class__.__name__}: {exc}",
            )
            logger.exception("Phase A schema initialization failed")
            raise

    def get_session(self) -> Session:
        return self._SessionLocal()

    @contextmanager
    def session_scope(self):
        with managed_session_scope(self._SessionLocal) as session:
            yield session

    def describe_runtime(self, *, include_connection_probe: bool = False) -> dict[str, Any]:
        return describe_store_runtime(
            self._engine,
            schema_key=self.SCHEMA_KEY,
            mode=self.MODE,
            source_path=_phase_a_sql_doc_path(),
            expected_tables=self.EXPECTED_TABLES,
            expected_indexes=self.EXPECTED_INDEXES,
            expected_constraints=self.EXPECTED_CONSTRAINTS,
            last_schema_apply_report=self._last_schema_apply_report,
            include_connection_probe=include_connection_probe,
        )

    def _require_user_exists(self, user_id: str) -> None:
        if self.get_app_user(user_id) is None:
            raise ValueError(f"Unknown app user: {user_id}")

    def get_app_user(self, user_id: str) -> Optional[PhaseAAppUser]:
        normalized = str(user_id or "").strip()
        if not normalized:
            return None
        with self.get_session() as session:
            return session.execute(
                select(PhaseAAppUser).where(PhaseAAppUser.id == normalized).limit(1)
            ).scalar_one_or_none()

    def get_app_user_by_username(self, username: str) -> Optional[PhaseAAppUser]:
        normalized = str(username or "").strip()
        if not normalized:
            return None
        with self.get_session() as session:
            return session.execute(
                select(PhaseAAppUser).where(PhaseAAppUser.username == normalized).limit(1)
            ).scalar_one_or_none()

    def list_app_users(self) -> list[PhaseAAppUser]:
        with self.get_session() as session:
            return list(
                session.execute(
                    select(PhaseAAppUser).order_by(PhaseAAppUser.created_at.desc(), PhaseAAppUser.id.desc())
                ).scalars().all()
            )

    def upsert_app_user(
        self,
        *,
        user_id: str,
        username: str,
        role: str = ROLE_USER,
        display_name: Optional[str] = None,
        password_hash: Optional[str] = None,
        is_active: bool = True,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> PhaseAAppUser:
        normalized_id = str(user_id or "").strip()
        normalized_username = str(username or "").strip()
        if not normalized_id:
            raise ValueError("user_id is required")
        if not normalized_username:
            raise ValueError("username is required")

        normalized_role = normalize_role(role)
        now = updated_at or datetime.now()

        with self.session_scope() as session:
            row = session.execute(
                select(PhaseAAppUser).where(PhaseAAppUser.id == normalized_id).limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = PhaseAAppUser(
                    id=normalized_id,
                    username=normalized_username,
                    display_name=(display_name or "").strip() or None,
                    password_hash=password_hash,
                    role=normalized_role,
                    is_active=bool(is_active),
                    created_at=created_at or now,
                    updated_at=updated_at or now,
                )
                session.add(row)
            else:
                row.username = normalized_username
                row.display_name = (display_name or "").strip() or row.display_name
                row.password_hash = password_hash if password_hash is not None else row.password_hash
                row.role = normalized_role
                row.is_active = bool(is_active)
                row.updated_at = now
            session.flush()
            return row

    def upsert_app_user_session(
        self,
        *,
        session_id: str,
        user_id: str,
        expires_at: datetime,
        created_at: Optional[datetime] = None,
        last_seen_at: Optional[datetime] = None,
        revoked_at: Optional[datetime] = None,
    ) -> PhaseAAppUserSession:
        normalized_session_id = str(session_id or "").strip()
        normalized_user_id = str(user_id or "").strip()
        if not normalized_session_id:
            raise ValueError("session_id is required")
        if not normalized_user_id:
            raise ValueError("user_id is required")
        if not isinstance(expires_at, datetime):
            raise ValueError("expires_at must be a datetime")

        self._require_user_exists(normalized_user_id)
        now = datetime.now()

        with self.session_scope() as session:
            row = session.execute(
                select(PhaseAAppUserSession)
                .where(PhaseAAppUserSession.session_id == normalized_session_id)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = PhaseAAppUserSession(
                    session_id=normalized_session_id,
                    user_id=normalized_user_id,
                    created_at=created_at or now,
                    last_seen_at=last_seen_at or now,
                    expires_at=expires_at,
                    revoked_at=revoked_at,
                )
                session.add(row)
            else:
                row.user_id = normalized_user_id
                row.last_seen_at = last_seen_at or now
                row.expires_at = expires_at
                row.revoked_at = revoked_at
            session.flush()
            return row

    def get_app_user_session(self, session_id: str) -> Optional[PhaseAAppUserSession]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return None
        with self.get_session() as session:
            return session.execute(
                select(PhaseAAppUserSession)
                .where(PhaseAAppUserSession.session_id == normalized_session_id)
                .limit(1)
            ).scalar_one_or_none()

    def list_app_user_sessions(self, user_id: str | None = None) -> list[PhaseAAppUserSession]:
        normalized_user_id = str(user_id or "").strip()
        with self.get_session() as session:
            query = select(PhaseAAppUserSession)
            if normalized_user_id:
                query = query.where(PhaseAAppUserSession.user_id == normalized_user_id)
            return list(
                session.execute(
                    query.order_by(PhaseAAppUserSession.created_at.desc(), PhaseAAppUserSession.session_id.desc())
                ).scalars().all()
            )

    def touch_app_user_session(self, session_id: str) -> bool:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return False
        with self.session_scope() as session:
            row = session.execute(
                select(PhaseAAppUserSession)
                .where(PhaseAAppUserSession.session_id == normalized_session_id)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return False
            row.last_seen_at = datetime.now()
            return True

    def revoke_app_user_session(self, session_id: str) -> bool:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return False
        now = datetime.now()
        with self.session_scope() as session:
            row = session.execute(
                select(PhaseAAppUserSession)
                .where(PhaseAAppUserSession.session_id == normalized_session_id)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return False
            row.revoked_at = now
            row.last_seen_at = now
            return True

    def revoke_all_app_user_sessions(self, user_id: str) -> int:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            return 0
        now = datetime.now()
        with self.session_scope() as session:
            rows = session.execute(
                select(PhaseAAppUserSession).where(
                    PhaseAAppUserSession.user_id == normalized_user_id,
                    PhaseAAppUserSession.revoked_at.is_(None),
                )
            ).scalars().all()
            for row in rows:
                row.revoked_at = now
                row.last_seen_at = now
            return len(rows)

    def list_active_app_user_session_ids(self, user_id: str) -> list[str]:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            return []
        with self.get_session() as session:
            rows = session.execute(
                select(PhaseAAppUserSession.session_id).where(
                    PhaseAAppUserSession.user_id == normalized_user_id,
                    PhaseAAppUserSession.revoked_at.is_(None),
                )
            ).scalars().all()
            return [str(value) for value in rows if str(value or "").strip()]

    def get_user_notification_preferences(self, user_id: str) -> Dict[str, Any]:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            raise ValueError("user_id is required")

        with self.get_session() as session:
            pref_row = session.execute(
                select(PhaseAUserPreference)
                .where(PhaseAUserPreference.user_id == normalized_user_id)
                .limit(1)
            ).scalar_one_or_none()
            target_rows = session.execute(
                select(PhaseANotificationTarget)
                .where(PhaseANotificationTarget.user_id == normalized_user_id)
                .order_by(PhaseANotificationTarget.updated_at.desc())
            ).scalars().all()

        email_target = next((row for row in target_rows if row.channel_type == "email"), None)
        discord_target = next((row for row in target_rows if row.channel_type == "discord"), None)

        email = str(getattr(email_target, "target_value", "") or "").strip() or None
        email_enabled = bool(getattr(email_target, "is_enabled", False)) and bool(email)
        discord_webhook = str(getattr(discord_target, "target_value", "") or "").strip() or None
        discord_enabled = bool(getattr(discord_target, "is_enabled", False)) and bool(discord_webhook)

        if email_enabled and discord_enabled:
            channel = "multi"
        elif discord_enabled:
            channel = "discord"
        else:
            channel = "email"

        updated_candidates = [
            getattr(pref_row, "updated_at", None),
            getattr(email_target, "updated_at", None),
            getattr(discord_target, "updated_at", None),
        ]
        updated_at = max(
            (value for value in updated_candidates if isinstance(value, datetime)),
            default=None,
        )

        return {
            "channel": channel,
            "enabled": email_enabled,
            "email": email,
            "email_enabled": email_enabled,
            "discord_webhook": discord_webhook,
            "discord_enabled": discord_enabled,
            "updated_at": updated_at.isoformat() if updated_at else None,
        }

    def upsert_user_notification_preferences(
        self,
        user_id: str,
        *,
        email: Optional[str],
        enabled: bool,
        channel: str = "email",
        discord_webhook: Optional[str] = None,
        discord_enabled: bool = False,
        updated_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            raise ValueError("user_id is required")

        self._require_user_exists(normalized_user_id)

        normalized_channel = str(channel or "email").strip().lower() or "email"
        if normalized_channel not in {"email", "discord", "multi"}:
            raise ValueError("unsupported notification channel")

        normalized_email = str(email or "").strip() or None
        normalized_enabled = bool(enabled) and bool(normalized_email)
        normalized_discord_webhook = str(discord_webhook or "").strip() or None
        normalized_discord_enabled = bool(discord_enabled) and bool(normalized_discord_webhook)
        if normalized_enabled and normalized_discord_enabled:
            normalized_channel = "multi"
        elif normalized_discord_enabled and not normalized_enabled:
            normalized_channel = "discord"
        else:
            normalized_channel = "email"

        now = updated_at or datetime.now()
        email_is_default = bool(normalized_email) and normalized_channel != "discord"
        discord_is_default = bool(normalized_discord_webhook) and not email_is_default

        with self.session_scope() as session:
            pref_row = session.execute(
                select(PhaseAUserPreference)
                .where(PhaseAUserPreference.user_id == normalized_user_id)
                .limit(1)
            ).scalar_one_or_none()
            if pref_row is None:
                pref_row = PhaseAUserPreference(
                    user_id=normalized_user_id,
                    ui_preferences_json={},
                    created_at=now,
                    updated_at=now,
                )
                session.add(pref_row)
            else:
                pref_row.updated_at = now

            session.execute(
                delete(PhaseANotificationTarget).where(
                    PhaseANotificationTarget.user_id == normalized_user_id,
                    PhaseANotificationTarget.channel_type.in_(("email", "discord")),
                )
            )

            if normalized_email:
                session.add(
                    PhaseANotificationTarget(
                        user_id=normalized_user_id,
                        channel_type="email",
                        target_value=normalized_email,
                        target_secret_json={},
                        is_default=email_is_default,
                        is_enabled=normalized_enabled,
                        delivery_metadata_json={},
                        created_at=now,
                        updated_at=now,
                    )
                )
            if normalized_discord_webhook:
                session.add(
                    PhaseANotificationTarget(
                        user_id=normalized_user_id,
                        channel_type="discord",
                        target_value=normalized_discord_webhook,
                        target_secret_json={},
                        is_default=discord_is_default,
                        is_enabled=normalized_discord_enabled,
                        delivery_metadata_json={},
                        created_at=now,
                        updated_at=now,
                    )
                )

        return self.get_user_notification_preferences(normalized_user_id)

    def import_legacy_notification_preferences(
        self,
        user_id: str,
        payload: Dict[str, Any],
        *,
        updated_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return self.get_user_notification_preferences(user_id)
        return self.upsert_user_notification_preferences(
            user_id,
            email=payload.get("email"),
            enabled=bool(payload.get("email_enabled", payload.get("enabled"))),
            channel=str(payload.get("channel") or "email"),
            discord_webhook=payload.get("discord_webhook"),
            discord_enabled=bool(payload.get("discord_enabled")),
            updated_at=updated_at,
        )

    def list_non_bootstrap_user_ids(self) -> list[str]:
        with self.get_session() as session:
            rows = session.execute(
                select(PhaseAAppUser.id).where(PhaseAAppUser.id != BOOTSTRAP_ADMIN_USER_ID)
            ).scalars().all()
        return [str(value) for value in rows if str(value or "").strip()]

    def clear_non_bootstrap_state(self, user_ids: Sequence[str]) -> Dict[str, int]:
        normalized_user_ids = [str(value).strip() for value in user_ids if str(value or "").strip()]
        if not normalized_user_ids:
            return {
                "notification_targets": 0,
                "user_preferences": 0,
                "app_user_sessions": 0,
                "app_users": 0,
            }

        with self.session_scope() as session:
            counts = {
                "notification_targets": session.execute(
                    delete(PhaseANotificationTarget).where(
                        PhaseANotificationTarget.user_id.in_(normalized_user_ids)
                    )
                ).rowcount or 0,
                "user_preferences": session.execute(
                    delete(PhaseAUserPreference).where(
                        PhaseAUserPreference.user_id.in_(normalized_user_ids)
                    )
                ).rowcount or 0,
                "app_user_sessions": session.execute(
                    delete(PhaseAAppUserSession).where(
                        PhaseAAppUserSession.user_id.in_(normalized_user_ids)
                    )
                ).rowcount or 0,
                "app_users": session.execute(
                    delete(PhaseAAppUser).where(
                        PhaseAAppUser.id.in_(normalized_user_ids)
                    )
                ).rowcount or 0,
            }
        return counts
