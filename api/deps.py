# -*- coding: utf-8 -*-
"""
===================================
API 依赖注入模块
===================================

职责：
1. 提供数据库 Session 依赖
2. 提供配置依赖
3. 提供服务层依赖
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Generator, Sequence

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from src.admin_rbac import expand_admin_capabilities, has_admin_capability
from src.auth import (
    COOKIE_NAME,
    get_admin_reauth_max_age_seconds,
    get_admin_session_reauthenticated_at,
    get_admin_unlock_identity,
    get_session_identity,
    is_auth_enabled,
    is_production_mode,
)
from src.multi_user import ROLE_ADMIN
from src.storage import DatabaseManager
from src.config import get_config, Config
from src.repositories.auth_repo import AuthRepository
from src.services.system_config_service import SystemConfigService


@dataclass(frozen=True)
class CurrentUser:
    """Resolved current-user view shared by API dependencies and middleware."""

    user_id: str
    username: str
    display_name: str | None
    role: str
    is_admin: bool
    is_authenticated: bool
    transitional: bool
    auth_enabled: bool
    session_id: str | None = None
    legacy_admin: bool = False
    admin_capabilities: tuple[str, ...] = field(default_factory=tuple)


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库 Session 依赖
    
    使用 FastAPI 依赖注入机制，确保请求结束后自动关闭 Session
    
    Yields:
        Session: SQLAlchemy Session 对象
        
    Example:
        @router.get("/items")
        async def get_items(db: Session = Depends(get_db)):
            ...
    """
    db_manager = DatabaseManager.get_instance()
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


def get_config_dep() -> Config:
    """
    获取配置依赖
    
    Returns:
        Config: 配置单例对象
    """
    return get_config()


def get_database_manager() -> DatabaseManager:
    """
    获取数据库管理器依赖
    
    Returns:
        DatabaseManager: 数据库管理器单例对象
    """
    return DatabaseManager.get_instance()


def get_system_config_service(request: Request) -> SystemConfigService:
    """Get app-lifecycle shared SystemConfigService instance."""
    return request.app.state.runtime_container.system_config_service


def resolve_current_user(request: Request) -> CurrentUser | None:
    """Resolve the effective current user from session cookie or transitional fallback."""
    state = getattr(request, "state", None)
    cache_miss = object()
    if state is not None:
        cached = getattr(state, "current_user", cache_miss)
        if cached is not cache_miss:
            return cached

    db = DatabaseManager.get_instance()
    auth_enabled = is_auth_enabled()
    cookies = getattr(request, "cookies", {}) or {}
    cookie_val = cookies.get(COOKIE_NAME)
    identity = get_session_identity(cookie_val) if cookie_val else None

    if identity is not None:
        user_row = db.get_app_user(identity.user_id)
        if user_row is not None and getattr(user_row, "is_active", True):
            current_user = CurrentUser(
                user_id=str(user_row.id),
                username=str(user_row.username),
                display_name=getattr(user_row, "display_name", None),
                role=str(user_row.role),
                is_admin=str(user_row.role) == "admin",
                is_authenticated=True,
                transitional=False,
                auth_enabled=auth_enabled,
                session_id=identity.session_id,
                legacy_admin=identity.legacy_admin,
            )
            object.__setattr__(
                current_user,
                "admin_capabilities",
                tuple(sorted(expand_admin_capabilities(current_user))),
            )
            if state is not None:
                state.current_user = current_user
            return current_user

    if not auth_enabled and not is_production_mode():
        bootstrap_user = db.ensure_bootstrap_admin_user()
        current_user = CurrentUser(
            user_id=str(bootstrap_user.id),
            username=str(bootstrap_user.username),
            display_name=getattr(bootstrap_user, "display_name", None),
            role=str(bootstrap_user.role),
            is_admin=str(bootstrap_user.role) == "admin",
            is_authenticated=False,
            transitional=True,
            auth_enabled=False,
            session_id=None,
            legacy_admin=False,
        )
        object.__setattr__(
            current_user,
            "admin_capabilities",
            tuple(sorted(expand_admin_capabilities(current_user))),
        )
        if state is not None:
            state.current_user = current_user
        return current_user

    if state is not None:
        state.current_user = None
    return None


def get_optional_current_user(request: Request) -> CurrentUser | None:
    """Return the resolved current user when available."""
    return resolve_current_user(request)


def get_current_user_id(current_user: object | None) -> str | None:
    """Extract a user id from a resolved current-user object when available."""
    user_id = getattr(current_user, "user_id", None)
    if not user_id:
        return None
    return str(user_id)


def is_admin_user(current_user: object | None) -> bool:
    """Return True when the resolved current user has the admin role."""
    return bool(getattr(current_user, "is_admin", False))


def ensure_current_user_matches_owner(
    owner_id: str | None,
    current_user: object | None,
    *,
    allow_admin_override: bool = False,
) -> None:
    """Validate that an explicit owner id matches the resolved current user."""
    normalized_owner_id = str(owner_id or "").strip()
    if not normalized_owner_id:
        return

    current_user_id = get_current_user_id(current_user)
    if current_user_id and normalized_owner_id == current_user_id:
        return
    if allow_admin_override and is_admin_user(current_user):
        return

    raise HTTPException(
        status_code=403,
        detail={
            "error": "owner_mismatch",
            "message": "The requested owner_id does not match the current user",
        },
    )


def get_current_user(request: Request) -> CurrentUser:
    """Require an authenticated or transitional current user."""
    current_user = resolve_current_user(request)
    if current_user is None:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "Login required"},
        )
    return current_user


def require_admin_user(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Require the resolved current user to be an admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail={"error": "admin_required", "message": "Admin access required"},
        )
    return current_user


def _admin_capabilities_for_user(current_user: CurrentUser) -> set[str]:
    cached = set(getattr(current_user, "admin_capabilities", ()) or ())
    if cached:
        return cached
    if bool(getattr(current_user, "legacy_admin", False)):
        return expand_admin_capabilities(current_user)
    return set()


def _raise_admin_capability_required() -> None:
    raise HTTPException(
        status_code=403,
        detail={
            "error": "admin_capability_required",
            "message": "Required admin capability is not available",
        },
    )


def require_admin_capability(capability: str) -> Callable[[CurrentUser], CurrentUser]:
    """Build a future route dependency for one admin capability.

    Phase R2 intentionally leaves existing routes on ``require_admin_user()``.
    """
    normalized = str(capability or "").strip()

    def dependency(current_user: CurrentUser = Depends(require_admin_user)) -> CurrentUser:
        admin_user = require_admin_user(current_user)
        if not normalized or normalized not in _admin_capabilities_for_user(admin_user):
            _raise_admin_capability_required()
        return admin_user

    return dependency


def require_any_admin_capability(capabilities: Sequence[str]) -> Callable[[CurrentUser], CurrentUser]:
    """Build a future route dependency that accepts any listed capability."""
    normalized = tuple(str(capability or "").strip() for capability in capabilities if str(capability or "").strip())

    def dependency(current_user: CurrentUser = Depends(require_admin_user)) -> CurrentUser:
        admin_user = require_admin_user(current_user)
        effective = _admin_capabilities_for_user(admin_user)
        if not normalized or not any(capability in effective for capability in normalized):
            _raise_admin_capability_required()
        return admin_user

    return dependency


def _raise_admin_unlock_required() -> None:
    raise HTTPException(
        status_code=403,
        detail={
            "error": "admin_unlock_required",
            "message": "Admin unlock or recent reauthentication required",
        },
    )


def _admin_unlock_token_matches_current_user(current_user: CurrentUser, unlock_token: str | None) -> bool:
    normalized = str(unlock_token or "").strip()
    if not normalized:
        return False

    identity = get_admin_unlock_identity(normalized)
    if identity is None or not identity.is_admin:
        return False

    return str(identity.user_id) == str(getattr(current_user, "user_id", "") or "")


def _has_recent_admin_reauth(current_user: CurrentUser) -> bool:
    try:
        max_age_minutes = max(1, get_admin_reauth_max_age_seconds() // 60)
        require_recent_admin_reauth(current_user, max_age_minutes=max_age_minutes)
        return True
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        if detail.get("error") == "admin_reauth_required":
            return False
        raise


def require_admin_unlock_or_recent_reauth(
    current_user: CurrentUser,
    *,
    admin_unlock_token: str | None = None,
) -> CurrentUser:
    """Require a valid admin unlock token or recent admin reauth for dangerous actions."""
    admin_user = require_admin_user(current_user)
    if not bool(getattr(admin_user, "is_authenticated", False)):
        _raise_admin_unlock_required()
    if _admin_unlock_token_matches_current_user(admin_user, admin_unlock_token):
        return admin_user
    if _has_recent_admin_reauth(admin_user):
        return admin_user
    _raise_admin_unlock_required()


def _capability_label_from_dependency(dependency: Callable[[CurrentUser], CurrentUser]) -> str | None:
    closure = getattr(dependency, "__closure__", None) or ()
    for cell in closure:
        value = getattr(cell, "cell_contents", None)
        if isinstance(value, str) and ":" in value:
            return value
    return None


def require_admin_capability_with_unlock(
    capability_dependency: Callable[[CurrentUser], CurrentUser],
) -> Callable[[CurrentUser, str | None], CurrentUser]:
    """Wrap a capability dependency with unlock/recent-reauth enforcement."""
    capability_label = _capability_label_from_dependency(capability_dependency)

    def dependency(
        current_user: CurrentUser = Depends(capability_dependency),
        admin_unlock_token: str | None = Header(default=None, alias="X-Admin-Unlock-Token"),
    ) -> CurrentUser:
        _ = capability_label
        return require_admin_unlock_or_recent_reauth(
            current_user,
            admin_unlock_token=admin_unlock_token,
        )

    return dependency


def require_sensitive_reason(reason: str, *, max_length: int = 500) -> str:
    """Validate a bounded admin action reason without exposing request details."""
    normalized = str(reason or "").strip()
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail={"error": "reason_required", "message": "reason is required"},
        )
    if len(normalized) > max_length:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": "reason is too long"},
        )
    return normalized


def require_recent_admin_reauth(
    current_user: CurrentUser,
    *,
    reauthenticated_at: datetime | None = None,
    max_age_minutes: int = 15,
) -> CurrentUser:
    """Validate recent admin reauthentication for the current admin session."""
    admin_user = require_admin_user(current_user)
    observed_at = reauthenticated_at or getattr(admin_user, "admin_reauthenticated_at", None)
    if observed_at is None:
        session_id = str(getattr(admin_user, "session_id", "") or "").strip()
        user_id = str(getattr(admin_user, "user_id", "") or "").strip()
        if session_id and user_id:
            session_row = DatabaseManager.get_instance().get_app_user_session(session_id)
            if (
                session_row is not None
                and str(getattr(session_row, "user_id", "") or "") == user_id
                and getattr(session_row, "revoked_at", None) is None
            ):
                expires_at = getattr(session_row, "expires_at", None)
                if not isinstance(expires_at, datetime) or datetime.now(tz=expires_at.tzinfo) <= expires_at:
                    observed_at = get_admin_session_reauthenticated_at(
                        user_id=user_id,
                        session_id=session_id,
                        max_age_seconds=max(1, max_age_minutes) * 60,
                    )
    if not isinstance(observed_at, datetime):
        raise HTTPException(
            status_code=403,
            detail={"error": "admin_reauth_required", "message": "Recent admin reauthentication required"},
        )

    now = datetime.now(tz=observed_at.tzinfo) if observed_at.tzinfo else datetime.now()
    if now - observed_at > timedelta(minutes=max(1, max_age_minutes)):
        raise HTTPException(
            status_code=403,
            detail={"error": "admin_reauth_required", "message": "Recent admin reauthentication required"},
        )
    return admin_user


def assert_not_self_destructive_action(current_user: CurrentUser, target_user_id: str) -> None:
    """Block future self-destructive admin actions before service execution."""
    actor_id = str(getattr(current_user, "user_id", "") or "").strip()
    target_id = str(target_user_id or "").strip()
    if actor_id and target_id and actor_id == target_id:
        raise HTTPException(
            status_code=403,
            detail={"error": "self_action_blocked", "message": "Admins cannot perform this action on themselves"},
        )


def assert_not_last_super_admin(target_user_id: str, *, repo: AuthRepository | None = None) -> None:
    """Block future actions that would remove or disable the last super-admin."""
    normalized_target = str(target_user_id or "").strip()
    if not normalized_target:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": "Invalid user_id"},
        )

    auth_repo = repo or AuthRepository()
    target_user = auth_repo.get_app_user(normalized_target)
    if target_user is None:
        return
    if not _is_active_admin_with_super_capability(target_user):
        return

    active_super_admin_count = sum(
        1 for user in auth_repo.list_app_users() if _is_active_admin_with_super_capability(user)
    )
    if active_super_admin_count <= 1:
        raise HTTPException(
            status_code=409,
            detail={"error": "last_super_admin_blocked", "message": "Cannot remove the last active super-admin"},
        )


def _is_active_admin_with_super_capability(user: object) -> bool:
    if str(getattr(user, "role", "") or "").strip() != ROLE_ADMIN:
        return False
    if not bool(getattr(user, "is_active", True)):
        return False
    return has_admin_capability(user, "users:security:write")
