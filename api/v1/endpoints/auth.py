# -*- coding: utf-8 -*-
"""Authentication endpoints for Web admin login."""

from __future__ import annotations

import logging
import os
import secrets
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from api.deps import (
    get_system_config_service,
    require_admin_capability,
    require_admin_unlock_or_recent_reauth,
    require_recent_admin_reauth,
    resolve_current_user,
)
from src.admin_rbac import expand_admin_capabilities
from src.auth import (
    ADMIN_UNLOCK_MAX_AGE_MINUTES_DEFAULT,
    COOKIE_NAME,
    _get_session_max_age_seconds,
    change_password,
    check_rate_limit,
    clear_rate_limit,
    create_admin_unlock_token,
    create_session,
    get_admin_reauth_max_age_seconds,
    get_client_ip,
    get_session_expiry_datetime,
    has_rate_limit_failures,
    has_stored_password,
    hash_password_for_storage,
    is_auth_enabled,
    is_password_changeable,
    is_password_set,
    is_production_mode,
    mark_admin_session_reauthenticated,
    record_login_failure,
    refresh_auth_state,
    rotate_session_secret,
    safe_identifier_hash,
    set_initial_password,
    get_session_identity,
    get_session_revocation_id,
    password_hash_needs_upgrade,
    verify_stored_password_and_upgrade,
    verify_password_hash_string,
    ensure_bootstrap_admin_user_password_hash,
)
from src.config import Config, setup_env
from src.core.config_manager import ConfigManager
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID, BOOTSTRAP_ADMIN_USERNAME, ROLE_ADMIN, ROLE_USER
from src.repositories.auth_repo import AuthRepository
from src.services.execution_log_service import ExecutionLogService
from src.services.admin_mfa_service import (
    MfaSecretStorageUnavailable,
    create_enrollment_challenge,
    disable_mfa,
    enable_mfa,
    generate_recovery_codes,
    record_mfa_verification,
    verify_recovery_code,
    verify_totp_code,
)
from src.services.system_config_service import SystemConfigService
from src.utils.security import sanitize_metadata

logger = logging.getLogger(__name__)

router = APIRouter()


class LoginRequest(BaseModel):
    """Login or account-bootstrap request body."""

    model_config = {"populate_by_name": True}

    username: str = Field(default="", description="Username")
    display_name: str | None = Field(default=None, alias="displayName", description="Display name for first account creation")
    create_user: bool = Field(default=False, alias="createUser", description="Whether to create a new normal user account")
    password: str = Field(default="", description="Password")
    password_confirm: str | None = Field(default=None, alias="passwordConfirm", description="Confirm (first-time)")
    mfa_code: str | None = Field(default=None, alias="mfaCode", description="Pilot MFA TOTP code")
    mfa_recovery_code: str | None = Field(
        default=None,
        alias="mfaRecoveryCode",
        description="Pilot MFA recovery code",
    )
    break_glass_reason: str | None = Field(
        default=None,
        alias="breakGlassReason",
        description="Explicit admin break-glass reason for MFA recovery pilot",
    )


class ChangePasswordRequest(BaseModel):
    """Change password request body."""

    model_config = {"populate_by_name": True}

    current_password: str = Field(default="", alias="currentPassword")
    new_password: str = Field(default="", alias="newPassword")
    new_password_confirm: str = Field(default="", alias="newPasswordConfirm")


class PasswordResetRequest(BaseModel):
    """Password reset request body."""

    identifier: str = Field(default="", description="Username or email")


class AuthSettingsRequest(BaseModel):
    """Update auth enablement and initial password settings."""

    model_config = {"populate_by_name": True}

    auth_enabled: bool = Field(alias="authEnabled")
    password: str = Field(default="")
    password_confirm: str | None = Field(default=None, alias="passwordConfirm")
    current_password: str = Field(default="", alias="currentPassword")


class VerifyPasswordRequest(BaseModel):
    """Password verification request for unlocking admin settings."""

    model_config = {"populate_by_name": True}

    password: str = Field(default="", description="Admin password")
    password_confirm: str | None = Field(default=None, alias="passwordConfirm", description="Confirm password when setting initial secret")


class ReauthRequest(BaseModel):
    """Recent admin reauthentication request body."""

    password: str = Field(default="", description="Current password")


class MfaCodeRequest(BaseModel):
    """MFA verification request body."""

    code: str = Field(default="", description="Six-digit MFA code")


class MfaRecoveryCodeRequest(BaseModel):
    """MFA recovery code verification request body."""

    code: str = Field(default="", description="One-time MFA recovery code")


class CurrentUserResponse(BaseModel):
    id: str
    username: str
    display_name: str | None = Field(default=None, alias="displayName")
    role: str
    is_admin: bool = Field(alias="isAdmin")
    is_authenticated: bool = Field(alias="isAuthenticated")
    transitional: bool = False
    auth_enabled: bool = Field(alias="authEnabled")
    legacy_admin: bool = Field(default=False, alias="legacyAdmin")
    admin_capabilities: list[str] = Field(default_factory=list, alias="adminCapabilities")
    can_read_users: bool = Field(default=False, alias="canReadUsers")
    can_read_user_activity: bool = Field(default=False, alias="canReadUserActivity")
    can_read_user_portfolio: bool = Field(default=False, alias="canReadUserPortfolio")
    can_write_user_security: bool = Field(default=False, alias="canWriteUserSecurity")
    can_read_cost_observability: bool = Field(default=False, alias="canReadCostObservability")
    can_read_ops_logs: bool = Field(default=False, alias="canReadOpsLogs")
    can_read_providers: bool = Field(default=False, alias="canReadProviders")
    can_read_notifications: bool = Field(default=False, alias="canReadNotifications")
    can_read_system_config: bool = Field(default=False, alias="canReadSystemConfig")


class UserNotificationPreferencesRequest(BaseModel):
    """Update current-user notification preferences."""

    model_config = {"populate_by_name": True}

    enabled: bool = Field(default=False)
    email: str | None = Field(default=None)
    email_enabled: bool | None = Field(default=None, alias="emailEnabled")
    discord_enabled: bool = Field(default=False, alias="discordEnabled")
    discord_webhook: str | None = Field(default=None, alias="discordWebhook")


class UserNotificationPreferencesResponse(BaseModel):
    """Current-user notification preferences."""

    channel: str = Field(default="email")
    enabled: bool = Field(default=False)
    email: str | None = Field(default=None)
    email_enabled: bool = Field(default=False, alias="emailEnabled")
    discord_enabled: bool = Field(default=False, alias="discordEnabled")
    discord_webhook: str | None = Field(default=None, alias="discordWebhook")
    delivery_available: bool = Field(default=False, alias="deliveryAvailable")
    email_delivery_available: bool = Field(default=False, alias="emailDeliveryAvailable")
    discord_delivery_available: bool = Field(default=True, alias="discordDeliveryAvailable")
    updated_at: str | None = Field(default=None, alias="updatedAt")


def _cookie_params(request: Request) -> dict:
    """Build cookie params including Secure based on request."""
    secure = False
    if os.getenv("TRUST_X_FORWARDED_FOR", "false").lower() == "true":
        proto = request.headers.get("X-Forwarded-Proto", "").lower()
        secure = proto == "https"
    else:
        # Check URL scheme when not behind proxy
        secure = request.url.scheme == "https"
    if is_production_mode() and not secure:
        logger.warning(
            "Production auth cookie requested without HTTPS context; issuing Secure cookie. "
            "Configure HTTPS and trusted proxy headers with TRUST_X_FORWARDED_FOR/X-Forwarded-Proto."
        )
        secure = True

    return {
        "httponly": True,
        "samesite": "lax",
        "secure": secure,
        "path": "/",
        "max_age": _get_session_max_age_seconds(),
    }


def _apply_auth_enabled(enabled: bool, request: Request | None = None) -> bool:
    """Persist auth toggle to .env and reload runtime config."""
    manager_applied = False
    if request is not None:
        try:
            service = get_system_config_service(request)
            service.apply_simple_updates(
                updates=[("ADMIN_AUTH_ENABLED", "true" if enabled else "false")],
                mask_token="******",
            )
            manager_applied = True
        except Exception as exc:
            logger.warning(
                "Failed to apply auth toggle via shared SystemConfigService, falling back: %s",
                exc,
                exc_info=True,
            )
            manager_applied = False

    if not manager_applied:
        try:
            manager = ConfigManager()
            manager.apply_updates(
                updates=[("ADMIN_AUTH_ENABLED", "true" if enabled else "false")],
                sensitive_keys=set(),
                mask_token="******",
            )
            SystemConfigService._sync_phase_g_config_shadow(
                raw_config_map=manager.read_config_map(),
            )
            manager_applied = True
        except Exception as exc:
            logger.error("Failed to apply auth toggle via ConfigManager: %s", exc, exc_info=True)
            manager_applied = False

    if not manager_applied:
        return False

    Config.reset_instance()
    setup_env(override=True)
    refresh_auth_state()
    return True


def _password_set_for_response(auth_enabled: bool) -> bool:
    """Avoid exposing stored-password state when auth is disabled."""
    return is_password_set() if auth_enabled else False


def _set_session_cookie(response: Response, session_value: str, request: Request) -> None:
    """Attach the admin session cookie to a response."""
    params = _cookie_params(request)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_value,
        httponly=params["httponly"],
        samesite=params["samesite"],
        secure=params["secure"],
        path=params["path"],
        max_age=params["max_age"],
    )


def _normalize_username(value: str | None) -> str:
    return str(value or "").strip()


def _capability_flags(capabilities: list[str]) -> dict[str, bool]:
    capability_set = set(capabilities)
    return {
        "canReadUsers": "users:read" in capability_set,
        "canReadUserActivity": "users:activity:read" in capability_set,
        "canReadUserPortfolio": "users:portfolio:read" in capability_set,
        "canWriteUserSecurity": "users:security:write" in capability_set,
        "canReadCostObservability": "cost:observability:read" in capability_set,
        "canReadOpsLogs": "ops:logs:read" in capability_set,
        "canReadProviders": "ops:providers:read" in capability_set,
        "canReadNotifications": "ops:notifications:read" in capability_set,
        "canReadSystemConfig": "ops:system_config:read" in capability_set,
    }


def _current_user_capability_summary(current_user) -> tuple[list[str], dict[str, bool]]:
    capabilities = sorted(getattr(current_user, "admin_capabilities", ()) or ())
    if not capabilities and bool(getattr(current_user, "legacy_admin", False)):
        capabilities = sorted(expand_admin_capabilities(current_user))
    return capabilities, _capability_flags(capabilities)


def _current_user_response(**kwargs) -> CurrentUserResponse:
    capabilities = list(kwargs.pop("adminCapabilities", []) or [])
    return CurrentUserResponse(
        **kwargs,
        adminCapabilities=capabilities,
        **_capability_flags(capabilities),
    )


def _serialize_current_user(request: Request) -> dict | None:
    current_user = resolve_current_user(request)
    if current_user is None:
        return None
    capabilities, flags = _current_user_capability_summary(current_user)
    return CurrentUserResponse(
        id=current_user.user_id,
        username=current_user.username,
        displayName=current_user.display_name,
        role=current_user.role,
        isAdmin=current_user.is_admin,
        isAuthenticated=current_user.is_authenticated,
        transitional=current_user.transitional,
        authEnabled=current_user.auth_enabled,
        legacyAdmin=current_user.legacy_admin,
        adminCapabilities=capabilities,
        **flags,
    ).model_dump(by_alias=True)


def _clear_current_user_cache(request: Request) -> None:
    state = getattr(request, "state", None)
    if state is not None and hasattr(state, "current_user"):
        delattr(state, "current_user")


def _generic_login_error(status_code: int = 401) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": "invalid_login", "message": "Invalid username or password"},
    )


def _rate_limited_error() -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": "rate_limited", "message": "Login temporarily unavailable. Please try again later."},
    )


def _audit_login_event(
    *,
    request: Request,
    action: str,
    username: str,
    outcome: str,
    status: str = "failed",
    user_id: str | None = None,
    admin: bool = False,
) -> None:
    safe_detail = sanitize_metadata(
        {
            "outcome": outcome,
            "account_hash": safe_identifier_hash(username, prefix="acct"),
            "user_hash": safe_identifier_hash(user_id, prefix="user") if user_id else None,
            "ip_hash": safe_identifier_hash(get_client_ip(request), prefix="ip"),
            "user_agent_hash": safe_identifier_hash(request.headers.get("User-Agent"), prefix="ua"),
            "admin_flow": bool(admin),
        }
    )
    try:
        ExecutionLogService().record_admin_action(
            action=action,
            message=f"Security auth event: {outcome}",
            actor={"actor_type": "anonymous", "role": "anonymous"},
            subsystem="security",
            destructive=False,
            detail=safe_detail,
            overall_status=status,
            result={"event": action, "metadata": safe_detail},
        )
    except Exception as exc:
        logger.warning("Failed to record auth security event: %s", exc)


def _env_flag_enabled(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _env_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _is_mfa_login_enforcement_enabled() -> bool:
    """Disabled-by-default pilot switch for MFA enforcement at login."""
    return _env_flag_enabled("WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED")


def _is_mfa_login_enforcement_admin_only() -> bool:
    """Keep the disabled pilot scoped to admin accounts unless explicitly changed later."""
    return _env_flag("WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ADMIN_ONLY", default=True)


def _mfa_login_enforcement_policy_scope() -> str:
    """Return the only supported MFA login enforcement rollout scope."""
    raw = str(os.getenv("WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_SCOPE") or "admin_only").strip().lower()
    normalized = raw.replace("-", "_")
    if normalized in {"admin", "admins", "admin_only"}:
        return "admin_only"
    return "unsupported"


def _is_mfa_login_break_glass_enabled() -> bool:
    """Disabled-by-default pilot switch for explicit admin MFA break-glass."""
    return _env_flag_enabled("WOLFYSTOCK_MFA_LOGIN_BREAK_GLASS_ENABLED")


def _mfa_required_error() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "error": "mfa_required",
            "message": "MFA verification required",
            "mfaRequired": True,
        },
    )


def _audit_mfa_login_event(
    *,
    request: Request,
    action: str,
    username: str,
    outcome: str,
    user_id: str | None,
    status: str = "failed",
    break_glass_reason: str | None = None,
) -> None:
    safe_detail = sanitize_metadata(
        {
            "outcome": outcome,
            "account_hash": safe_identifier_hash(username, prefix="acct"),
            "user_hash": safe_identifier_hash(user_id, prefix="user") if user_id else None,
            "ip_hash": safe_identifier_hash(get_client_ip(request), prefix="ip"),
            "user_agent_hash": safe_identifier_hash(request.headers.get("User-Agent"), prefix="ua"),
            "admin_flow": True,
            "mfa_login_enforcement": True,
            "break_glass_reason_provided": bool(str(break_glass_reason or "").strip()),
            "break_glass_reason_hash": (
                safe_identifier_hash(break_glass_reason, prefix="reason")
                if str(break_glass_reason or "").strip()
                else None
            ),
        }
    )
    try:
        ExecutionLogService().record_admin_action(
            action=action,
            message=f"Security MFA login event: {outcome}",
            actor={"actor_type": "anonymous", "role": "anonymous"},
            subsystem="security",
            destructive=False,
            detail=safe_detail,
            overall_status=status,
            result={"event": action, "metadata": safe_detail},
        )
    except Exception as exc:
        logger.warning("Failed to record MFA auth security event: %s", exc)


def _audit_mfa_enforcement_decision(
    *,
    request: Request,
    username: str,
    user_id: str | None,
    decision: str,
    policy_scope: str,
    status: str = "completed",
    user_role: str | None = None,
    eligible: bool = False,
    mfa_enabled: bool = False,
    totp_ref_present: bool = False,
    enabled_at_present: bool = False,
    recovery_set_ready: bool = False,
) -> None:
    safe_detail = sanitize_metadata(
        {
            "decision": decision,
            "policy_scope": policy_scope,
            "eligible": bool(eligible),
            "account_hash": safe_identifier_hash(username, prefix="acct"),
            "user_hash": safe_identifier_hash(user_id, prefix="user") if user_id else None,
            "ip_hash": safe_identifier_hash(get_client_ip(request), prefix="ip"),
            "user_agent_hash": safe_identifier_hash(request.headers.get("User-Agent"), prefix="ua"),
            "user_role": str(user_role or ""),
            "role_is_admin": str(user_role or "") == ROLE_ADMIN,
            "mfa_enabled": bool(mfa_enabled),
            "totp_ref_present": bool(totp_ref_present),
            "enabled_at_present": bool(enabled_at_present),
            "recovery_set_ready": bool(recovery_set_ready),
        }
    )
    try:
        ExecutionLogService().record_admin_action(
            action="security.mfa_login_enforcement_decision",
            message=f"Security MFA login enforcement decision: {decision}",
            actor={"actor_type": "anonymous", "role": "anonymous"},
            subsystem="security",
            destructive=False,
            detail=safe_detail,
            overall_status=status,
            result={"event": "security.mfa_login_enforcement_decision", "metadata": safe_detail},
        )
    except Exception as exc:
        logger.warning("Failed to record MFA enforcement decision: %s", exc)


def _has_active_mfa_recovery_codes(user_row) -> bool:
    raw = getattr(user_row, "mfa_recovery_codes_hash", None)
    if not raw:
        return False
    try:
        parsed = json.loads(str(raw))
    except Exception:
        return False
    if not isinstance(parsed, dict) or parsed.get("version") != 1:
        return False
    sets = parsed.get("sets")
    if not isinstance(sets, list):
        return False
    for recovery_set in reversed(sets):
        if not isinstance(recovery_set, dict) or recovery_set.get("replaced_at"):
            continue
        codes = recovery_set.get("codes")
        if not isinstance(codes, list):
            return False
        return any(isinstance(entry, dict) and not entry.get("used_at") for entry in codes)
    return False


def _verify_login_mfa_requirement(
    *,
    request: Request,
    username: str,
    user_row,
    body: LoginRequest,
) -> JSONResponse | None:
    if not _is_mfa_login_enforcement_enabled():
        return None

    admin_only = _is_mfa_login_enforcement_admin_only()
    policy_scope = _mfa_login_enforcement_policy_scope()
    user_role = str(getattr(user_row, "role", "") or "")
    user_id = str(getattr(user_row, "id", "") or "")
    if user_role != ROLE_ADMIN:
        _audit_mfa_enforcement_decision(
            request=request,
            username=username,
            user_id=user_id,
            decision="not_eligible_admin_only",
            policy_scope="admin_only",
            user_role=user_role,
            eligible=False,
        )
        return None

    if policy_scope != "admin_only" or not admin_only:
        _audit_mfa_enforcement_decision(
            request=request,
            username=username,
            user_id=user_id,
            decision="unsupported_scope",
            policy_scope="unsupported",
            status="failed",
            user_role=user_role,
            eligible=user_role == ROLE_ADMIN,
            mfa_enabled=bool(getattr(user_row, "mfa_enabled", False)),
            totp_ref_present=bool(getattr(user_row, "mfa_secret_ref", None)),
            enabled_at_present=bool(getattr(user_row, "mfa_enabled_at", None)),
            recovery_set_ready=_has_active_mfa_recovery_codes(user_row),
        )
        return _mfa_required_error()

    secret_ref = getattr(user_row, "mfa_secret_ref", None)
    mfa_enabled = bool(getattr(user_row, "mfa_enabled", False))
    enabled_at_present = bool(getattr(user_row, "mfa_enabled_at", None))
    recovery_set_ready = _has_active_mfa_recovery_codes(user_row)
    state_complete = bool(mfa_enabled and secret_ref and enabled_at_present and recovery_set_ready)
    if not state_complete:
        _audit_mfa_enforcement_decision(
            request=request,
            username=username,
            user_id=user_id,
            decision="mfa_state_incomplete",
            policy_scope=policy_scope,
            status="failed",
            user_role=user_role,
            eligible=True,
            mfa_enabled=mfa_enabled,
            totp_ref_present=bool(secret_ref),
            enabled_at_present=enabled_at_present,
            recovery_set_ready=recovery_set_ready,
        )
        return _mfa_required_error()

    if mfa_enabled and secret_ref and verify_totp_code(secret_ref=secret_ref, code=body.mfa_code):
        _audit_mfa_enforcement_decision(
            request=request,
            username=username,
            user_id=user_id,
            decision="totp_success",
            policy_scope=policy_scope,
            user_role=user_role,
            eligible=True,
            mfa_enabled=mfa_enabled,
            totp_ref_present=True,
            enabled_at_present=enabled_at_present,
            recovery_set_ready=recovery_set_ready,
        )
        return None

    if mfa_enabled and body.mfa_recovery_code:
        result = verify_recovery_code(user_id=user_id, code=body.mfa_recovery_code, repo=AuthRepository())
        if result.verified:
            _audit_mfa_enforcement_decision(
                request=request,
                username=username,
                user_id=user_id,
                decision="recovery_code_success",
                policy_scope=policy_scope,
                user_role=user_role,
                eligible=True,
                mfa_enabled=mfa_enabled,
                totp_ref_present=True,
                enabled_at_present=enabled_at_present,
                recovery_set_ready=recovery_set_ready,
            )
            _audit_mfa_login_event(
                request=request,
                action="security.mfa_recovery_code_login",
                username=username,
                outcome="mfa_recovery_code_success",
                user_id=user_id,
                status="completed",
            )
            return None

    reason = str(body.break_glass_reason or "").strip()
    if reason and _is_mfa_login_break_glass_enabled():
        _audit_mfa_enforcement_decision(
            request=request,
            username=username,
            user_id=user_id,
            decision="break_glass_success",
            policy_scope=policy_scope,
            user_role=user_role,
            eligible=True,
            mfa_enabled=mfa_enabled,
            totp_ref_present=True,
            enabled_at_present=enabled_at_present,
            recovery_set_ready=recovery_set_ready,
        )
        _audit_mfa_login_event(
            request=request,
            action="security.mfa_break_glass_login",
            username=username,
            outcome="mfa_break_glass_success",
            user_id=user_id,
            status="completed",
            break_glass_reason=reason,
        )
        return None

    _audit_mfa_enforcement_decision(
        request=request,
        username=username,
        user_id=user_id,
        decision="mfa_required",
        policy_scope=policy_scope,
        status="failed",
        user_role=user_role,
        eligible=True,
        mfa_enabled=mfa_enabled,
        totp_ref_present=bool(secret_ref),
        enabled_at_present=enabled_at_present,
        recovery_set_ready=recovery_set_ready,
    )
    _audit_mfa_login_event(
        request=request,
        action="security.mfa_login_required",
        username=username,
        outcome="mfa_required",
        user_id=user_id,
        break_glass_reason=reason,
    )
    return _mfa_required_error()


def _record_login_failure_and_audit(
    request: Request,
    *,
    ip: str,
    username: str,
    outcome: str,
    user_id: str | None = None,
    admin: bool = False,
) -> None:
    record_login_failure(ip, username, reason=outcome, admin=admin)
    _audit_login_event(
        request=request,
        action="security.login_failed",
        username=username,
        outcome=outcome,
        user_id=user_id,
        admin=admin,
    )


def _normalize_notification_email(value: str | None) -> str | None:
    email = str(value or "").strip()
    if not email:
        return None
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("请输入有效的邮箱地址")
    return email


def _normalize_discord_webhook(value: str | None) -> str | None:
    webhook = str(value or "").strip()
    if not webhook:
        return None

    parsed = urlparse(webhook)
    host = str(parsed.netloc or "").lower()
    path = str(parsed.path or "")
    if (
        parsed.scheme != "https"
        or not host
        or "/api/webhooks/" not in path
        or not (host.endswith("discord.com") or host.endswith("discordapp.com"))
    ):
        raise ValueError("请输入有效的 Discord Webhook URL")
    return webhook


def _notification_delivery_available() -> bool:
    config = Config.get_instance()
    return bool(getattr(config, "email_sender", None) and getattr(config, "email_password", None))


def _serialize_user_notification_preferences(user_id: str) -> dict:
    repo = AuthRepository()
    preferences = repo.get_user_notification_preferences(user_id)
    email_delivery_available = _notification_delivery_available()
    return UserNotificationPreferencesResponse(
        channel=str(preferences.get("channel") or "email"),
        enabled=bool(preferences.get("enabled")),
        email=preferences.get("email"),
        emailEnabled=bool(preferences.get("email_enabled")),
        discordEnabled=bool(preferences.get("discord_enabled")),
        discordWebhook=preferences.get("discord_webhook"),
        deliveryAvailable=email_delivery_available,
        emailDeliveryAvailable=email_delivery_available,
        discordDeliveryAvailable=True,
        updatedAt=preferences.get("updated_at"),
    ).model_dump(by_alias=True)


def _require_admin_current_user(request: Request):
    current_user = resolve_current_user(request)
    if current_user is None:
        return None, JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": "Login required"},
        )
    if not current_user.is_admin:
        return None, JSONResponse(
            status_code=403,
            content={"error": "admin_required", "message": "Admin access required"},
        )
    return current_user, None


def _require_recent_admin_reauth_response(current_user):
    try:
        max_age_minutes = max(1, get_admin_reauth_max_age_seconds() // 60)
        require_recent_admin_reauth(current_user, max_age_minutes=max_age_minutes)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return None


def _persist_session_for_user(*, request: Request, user_id: str, username: str, role: str) -> str:
    session_id = secrets.token_hex(16)
    expires_at = get_session_expiry_datetime()
    repo = AuthRepository()
    repo.create_app_user_session(
        session_id=session_id,
        user_id=user_id,
        expires_at=expires_at,
    )
    return create_session(
        user_id=user_id,
        username=username,
        role=role,
        session_id=session_id,
        expires_at=int(expires_at.timestamp()),
    )


def _upgrade_app_user_password_hash_if_needed(user_row, password: str):
    stored_hash = getattr(user_row, "password_hash", None)
    if not password_hash_needs_upgrade(stored_hash):
        return user_row
    try:
        new_hash = hash_password_for_storage(password)
        return AuthRepository().create_or_update_app_user(
            user_id=str(user_row.id),
            username=str(user_row.username),
            display_name=getattr(user_row, "display_name", None) or str(user_row.username),
            role=str(user_row.role),
            password_hash=new_hash,
            is_active=bool(getattr(user_row, "is_active", True)),
        )
    except Exception as exc:  # pragma: no cover - best-effort compatibility path
        logger.warning("Failed to upgrade app user password KDF: %s", exc)
        return user_row


def _delete_session_cookie(response: Response, request: Request) -> None:
    params = _cookie_params(request)
    response.delete_cookie(
        key=COOKIE_NAME,
        path=params["path"],
        secure=params["secure"],
        httponly=params["httponly"],
        samesite=params["samesite"],
    )


def _get_auth_status_dict(request: Request | None = None) -> dict:
    """Helper to build consistent auth status response body."""
    auth_enabled = is_auth_enabled()
    stored_password_exists = has_stored_password()
    resolved_user_payload = _serialize_current_user(request) if request is not None else None
    current_user_payload = resolved_user_payload
    if current_user_payload and (
        not auth_enabled
        or not bool(current_user_payload.get("isAuthenticated"))
        or bool(current_user_payload.get("transitional"))
    ):
        current_user_payload = None
    logged_in = bool(current_user_payload and current_user_payload.get("isAuthenticated"))

    # setupState determination:
    # - enabled: auth is active and a valid bootstrap password exists
    # - password_retained: auth disabled but password exists
    # - no_password: no valid bootstrap password exists, even when auth is active
    if auth_enabled and stored_password_exists:
        setup_state = "enabled"
    elif stored_password_exists:
        setup_state = "password_retained"
    else:
        setup_state = "no_password"

    return {
        "authEnabled": auth_enabled,
        "loggedIn": logged_in,
        "passwordSet": _password_set_for_response(auth_enabled),
        "passwordChangeable": is_password_changeable() if auth_enabled else False,
        "setupState": setup_state,
        "currentUser": current_user_payload,
    }


@router.get(
    "/status",
    summary="Get auth status",
    description="Returns whether auth is enabled and if the current request is logged in.",
)
async def auth_status(request: Request):
    """Return authEnabled, loggedIn, passwordSet, passwordChangeable, setupState without requiring auth."""
    return _get_auth_status_dict(request)


@router.get(
    "/me",
    summary="Get current user",
    description="Returns the resolved current user identity for the request.",
)
async def auth_me(request: Request):
    current_user = _serialize_current_user(request)
    if current_user is None:
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": "Login required"},
        )
    return current_user


@router.get(
    "/preferences/notifications",
    summary="Get current-user notification preferences",
    description="Returns the personal notification target configuration for the authenticated user.",
)
async def auth_get_notification_preferences(request: Request):
    current_user = resolve_current_user(request)
    if current_user is None or not current_user.is_authenticated:
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": "Login required"},
        )
    return _serialize_user_notification_preferences(current_user.user_id)


@router.put(
    "/preferences/notifications",
    summary="Update current-user notification preferences",
    description="Updates the personal notification target configuration for the authenticated user.",
)
async def auth_update_notification_preferences(request: Request, body: UserNotificationPreferencesRequest):
    current_user = resolve_current_user(request)
    if current_user is None or not current_user.is_authenticated:
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": "Login required"},
        )

    try:
        normalized_email = _normalize_notification_email(body.email)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": "validation_error", "message": str(exc)},
        )
    try:
        normalized_discord_webhook = _normalize_discord_webhook(body.discord_webhook)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": "validation_error", "message": str(exc)},
        )

    email_enabled = body.email_enabled if body.email_enabled is not None else body.enabled

    if email_enabled and not normalized_email:
        return JSONResponse(
            status_code=400,
            content={"error": "validation_error", "message": "启用邮件通知前请先填写邮箱地址"},
        )
    if body.discord_enabled and not normalized_discord_webhook:
        return JSONResponse(
            status_code=400,
            content={"error": "validation_error", "message": "启用 Discord 通知前请先填写 Webhook URL"},
        )

    AuthRepository().upsert_user_notification_preferences(
        current_user.user_id,
        email=normalized_email,
        enabled=email_enabled,
        channel="multi" if email_enabled and body.discord_enabled else ("discord" if body.discord_enabled else "email"),
        discord_webhook=normalized_discord_webhook,
        discord_enabled=body.discord_enabled,
    )
    return _serialize_user_notification_preferences(current_user.user_id)


@router.post(
    "/reauth",
    summary="Recently reauthenticate current admin session",
    description="Verifies the current admin password and records a short-lived session-bound reauth marker.",
)
async def auth_reauth(request: Request, body: ReauthRequest):
    current_user, error_response = _require_admin_current_user(request)
    if error_response is not None:
        return error_response
    if not current_user.is_authenticated or not current_user.session_id:
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": "Login required"},
        )

    password = (body.password or "").strip()
    if not password:
        return JSONResponse(
            status_code=400,
            content={"error": "password_required", "message": "请输入当前密码"},
        )

    ip = get_client_ip(request)
    if not check_rate_limit(ip, current_user.username, admin=True):
        _audit_login_event(
            request=request,
            action="security.reauth_rate_limited",
            username=current_user.username,
            outcome="rate_limited",
            status="failed",
            user_id=current_user.user_id,
            admin=True,
        )
        return _rate_limited_error()

    verified = False
    if current_user.user_id == BOOTSTRAP_ADMIN_USER_ID:
        ensure_bootstrap_admin_user_password_hash()
        verified = verify_stored_password_and_upgrade(password)
    else:
        user_row = AuthRepository().get_app_user(current_user.user_id)
        verified = bool(user_row and verify_password_hash_string(password, getattr(user_row, "password_hash", None)))
        if verified and user_row is not None:
            _upgrade_app_user_password_hash_if_needed(user_row, password)

    if not verified:
        _record_login_failure_and_audit(
            request,
            ip=ip,
            username=current_user.username,
            outcome="invalid_password",
            user_id=current_user.user_id,
            admin=True,
        )
        return _generic_login_error()

    reauthenticated_at = mark_admin_session_reauthenticated(
        user_id=current_user.user_id,
        session_id=current_user.session_id,
    )
    if reauthenticated_at is None:
        return JSONResponse(
            status_code=403,
            content={"error": "admin_reauth_required", "message": "Recent admin reauthentication required"},
        )

    clear_rate_limit(ip, current_user.username)
    ttl_seconds = get_admin_reauth_max_age_seconds()
    return {
        "ok": True,
        "ttlSeconds": ttl_seconds,
        "reauthExpiresAt": (reauthenticated_at + timedelta(seconds=ttl_seconds)).isoformat(),
    }


@router.post(
    "/mfa/enroll/start",
    summary="Start admin MFA enrollment",
    description="Creates a non-enforcing admin MFA enrollment challenge. Login enforcement remains disabled.",
)
async def auth_mfa_enroll_start(request: Request):
    current_user, error_response = _require_admin_current_user(request)
    if error_response is not None:
        return error_response
    if not current_user.is_authenticated or not current_user.session_id:
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": "Login required"},
        )

    repo = AuthRepository()
    user_row = repo.get_app_user(current_user.user_id)
    if user_row is None:
        return JSONResponse(
            status_code=404,
            content={"error": "user_not_found", "message": "Current user not found"},
        )

    try:
        challenge = create_enrollment_challenge(
            user_id=current_user.user_id,
            username=current_user.username,
            repo=repo,
        )
    except MfaSecretStorageUnavailable:
        return JSONResponse(
            status_code=503,
            content={
                "error": "mfa_secret_storage_unavailable",
                "message": "MFA secret storage is not available",
            },
        )
    return {
        "ok": True,
        "status": "pending",
        "secret": challenge.secret,
        "provisioningUri": challenge.provisioning_uri,
        "storageMode": challenge.storage_mode,
        "mfaRequiredForLogin": False,
    }


@router.post(
    "/mfa/enroll/verify",
    summary="Verify admin MFA enrollment",
    description="Verifies an enrollment code and enables MFA metadata. Login enforcement remains disabled.",
)
async def auth_mfa_enroll_verify(request: Request, body: MfaCodeRequest):
    current_user, error_response = _require_admin_current_user(request)
    if error_response is not None:
        return error_response
    reauth_error = _require_recent_admin_reauth_response(current_user)
    if reauth_error is not None:
        return reauth_error

    repo = AuthRepository()
    user_row = repo.get_app_user(current_user.user_id)
    if user_row is None:
        return JSONResponse(
            status_code=404,
            content={"error": "user_not_found", "message": "Current user not found"},
        )
    secret_ref = getattr(user_row, "mfa_secret_ref", None)
    if not secret_ref:
        return JSONResponse(
            status_code=400,
            content={"error": "mfa_enrollment_not_started", "message": "MFA enrollment has not been started"},
        )
    if not verify_totp_code(secret_ref=secret_ref, code=body.code):
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_mfa_code", "message": "Invalid MFA code"},
        )

    enable_mfa(user_id=current_user.user_id, secret_ref=secret_ref, repo=repo)
    return {
        "ok": True,
        "status": "enabled",
        "mfaRequiredForLogin": False,
    }


@router.post(
    "/mfa/verify",
    summary="Verify current admin MFA code",
    description="Verifies an MFA code for the current admin session. Login enforcement remains disabled.",
)
async def auth_mfa_verify(request: Request, body: MfaCodeRequest):
    current_user, error_response = _require_admin_current_user(request)
    if error_response is not None:
        return error_response

    repo = AuthRepository()
    user_row = repo.get_app_user(current_user.user_id)
    if user_row is None or not getattr(user_row, "mfa_enabled", False):
        return JSONResponse(
            status_code=400,
            content={"error": "mfa_not_enabled", "message": "MFA is not enabled"},
        )
    secret_ref = getattr(user_row, "mfa_secret_ref", None)
    if not verify_totp_code(secret_ref=secret_ref, code=body.code):
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_mfa_code", "message": "Invalid MFA code"},
        )

    record_mfa_verification(
        user_id=current_user.user_id,
        secret_ref=secret_ref,
        enabled=True,
        repo=repo,
    )
    return {
        "ok": True,
        "verified": True,
        "mfaRequiredForLogin": False,
    }


@router.post(
    "/mfa/disable",
    summary="Disable admin MFA",
    description="Disables admin MFA metadata for the current admin after recent reauthentication.",
)
async def auth_mfa_disable(request: Request):
    current_user, error_response = _require_admin_current_user(request)
    if error_response is not None:
        return error_response
    reauth_error = _require_recent_admin_reauth_response(current_user)
    if reauth_error is not None:
        return reauth_error

    repo = AuthRepository()
    user_row = repo.get_app_user(current_user.user_id)
    if user_row is None:
        return JSONResponse(
            status_code=404,
            content={"error": "user_not_found", "message": "Current user not found"},
        )
    disable_mfa(user_id=current_user.user_id, repo=repo)
    return {
        "ok": True,
        "status": "disabled",
        "mfaRequiredForLogin": False,
    }


@router.post(
    "/mfa/recovery-codes/generate",
    summary="Generate admin MFA recovery codes",
    description="Generates one-time admin MFA recovery codes. Plaintext codes are returned only in this response.",
)
async def auth_mfa_recovery_codes_generate(request: Request):
    current_user, error_response = _require_admin_current_user(request)
    if error_response is not None:
        return error_response
    reauth_error = _require_recent_admin_reauth_response(current_user)
    if reauth_error is not None:
        return reauth_error

    batch = generate_recovery_codes(user_id=current_user.user_id, repo=AuthRepository())
    if batch is None:
        return JSONResponse(
            status_code=400,
            content={"error": "mfa_not_enabled", "message": "MFA is not enabled"},
        )
    return {
        "ok": True,
        "status": "generated",
        "count": len(batch.codes),
        "remainingCount": batch.remaining_count,
        "generatedAt": batch.generated_at.isoformat(),
        "recoveryCodes": batch.codes,
        "mfaRequiredForLogin": False,
    }


@router.post(
    "/mfa/recovery-codes/verify",
    summary="Verify admin MFA recovery code",
    description="Verifies and consumes one active admin MFA recovery code. Login enforcement remains disabled.",
)
async def auth_mfa_recovery_codes_verify(request: Request, body: MfaRecoveryCodeRequest):
    current_user, error_response = _require_admin_current_user(request)
    if error_response is not None:
        return error_response

    result = verify_recovery_code(user_id=current_user.user_id, code=body.code, repo=AuthRepository())
    if not result.verified:
        return JSONResponse(
            status_code=401,
            content={
                "error": "invalid_recovery_code",
                "message": "Invalid recovery code",
                "remainingCount": result.remaining_count,
            },
        )
    return {
        "ok": True,
        "verified": True,
        "remainingCount": result.remaining_count,
        "mfaRequiredForLogin": False,
    }


@router.post(
    "/mfa/recovery-codes/rotate",
    summary="Rotate admin MFA recovery codes",
    description="Replaces active admin MFA recovery codes after recent reauthentication.",
)
async def auth_mfa_recovery_codes_rotate(request: Request):
    current_user, error_response = _require_admin_current_user(request)
    if error_response is not None:
        return error_response
    reauth_error = _require_recent_admin_reauth_response(current_user)
    if reauth_error is not None:
        return reauth_error

    batch = generate_recovery_codes(user_id=current_user.user_id, repo=AuthRepository())
    if batch is None:
        return JSONResponse(
            status_code=400,
            content={"error": "mfa_not_enabled", "message": "MFA is not enabled"},
        )
    return {
        "ok": True,
        "status": "rotated",
        "count": len(batch.codes),
        "remainingCount": batch.remaining_count,
        "generatedAt": batch.generated_at.isoformat(),
        "recoveryCodes": batch.codes,
        "mfaRequiredForLogin": False,
    }


@router.post(
    "/verify-password",
    summary="Verify admin password for settings unlock",
    description=(
        "Verifies the admin password and returns a short-lived unlock token for admin-only "
        "settings edits. If no stored password exists yet, accepts password + passwordConfirm "
        "to bootstrap the initial admin password."
    ),
)
async def auth_verify_password(request: Request, body: VerifyPasswordRequest):
    """Verify or initialize admin password and return a short-lived unlock token."""
    current_user, error_response = _require_admin_current_user(request)
    if error_response is not None:
        return error_response

    password = (body.password or "").strip()
    if not password:
        return JSONResponse(
            status_code=400,
            content={"error": "password_required", "message": "请输入管理员密码"},
        )

    ip = get_client_ip(request)
    if not check_rate_limit(ip, current_user.username, admin=True):
        _audit_login_event(
            request=request,
            action="security.login_rate_limited",
            username=current_user.username,
            outcome="rate_limited",
            status="failed",
            user_id=current_user.user_id,
            admin=True,
        )
        return _rate_limited_error()

    bootstrap_admin = current_user.user_id == BOOTSTRAP_ADMIN_USER_ID

    if bootstrap_admin and not has_stored_password():
        confirm = (body.password_confirm or "").strip()
        if not confirm:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "password_confirm_required",
                    "message": "当前尚未设置管理员密码，请输入并确认初始密码。",
                },
            )
        if password != confirm:
            _record_login_failure_and_audit(
                request,
                ip=ip,
                username=current_user.username,
                outcome="password_mismatch",
                user_id=current_user.user_id,
                admin=True,
            )
            return JSONResponse(
                status_code=400,
                content={"error": "password_mismatch", "message": "两次输入的密码不一致"},
            )
        err = set_initial_password(password)
        if err:
            _record_login_failure_and_audit(
                request,
                ip=ip,
                username=current_user.username,
                outcome="invalid_password_policy",
                user_id=current_user.user_id,
                admin=True,
            )
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_password", "message": err},
            )
    else:
        verified = False
        if bootstrap_admin:
            ensure_bootstrap_admin_user_password_hash()
            verified = verify_stored_password_and_upgrade(password)
        else:
            user_row = AuthRepository().get_app_user(current_user.user_id)
            verified = bool(user_row and verify_password_hash_string(password, getattr(user_row, "password_hash", None)))
            if verified and user_row is not None:
                _upgrade_app_user_password_hash_if_needed(user_row, password)
        if not verified:
            _record_login_failure_and_audit(
                request,
                ip=ip,
                username=current_user.username,
                outcome="invalid_password",
                user_id=current_user.user_id,
                admin=True,
            )
            return _generic_login_error()

    clear_rate_limit(ip, current_user.username)
    unlock_token = create_admin_unlock_token(
        user_id=current_user.user_id,
        username=current_user.username,
        role=current_user.role,
    )
    if not unlock_token:
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "Failed to create admin unlock token"},
        )

    try:
        ttl_minutes = int(os.getenv("ADMIN_UNLOCK_MAX_AGE_MINUTES", str(ADMIN_UNLOCK_MAX_AGE_MINUTES_DEFAULT)))
    except ValueError:
        ttl_minutes = ADMIN_UNLOCK_MAX_AGE_MINUTES_DEFAULT
    expires_in_seconds = max(60, ttl_minutes * 60)

    return {
        "ok": True,
        "unlockToken": unlock_token,
        "expiresInSeconds": expires_in_seconds,
    }


@router.post(
    "/settings",
    summary="Update auth settings",
    description=(
        "Enable or disable password login. When enabling without an existing password, "
        "password + passwordConfirm are required. When re-enabling with a stored password, "
        "currentPassword is required."
    ),
)
async def auth_update_settings(request: Request, body: AuthSettingsRequest):
    """Manage auth enablement from the settings page."""
    current_user, error_response = _require_admin_current_user(request)
    if error_response is not None:
        return error_response
    if current_user.is_authenticated:
        try:
            current_user = require_admin_capability("ops:system_config:write")(current_user)
            require_admin_unlock_or_recent_reauth(
                current_user,
                admin_unlock_token=request.headers.get("X-Admin-Unlock-Token"),
            )
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    target_enabled = body.auth_enabled
    current_enabled = is_auth_enabled()
    stored_password_exists = has_stored_password()

    password = (body.password or "").strip()
    confirm = (body.password_confirm or "").strip()
    current_password = (body.current_password or "").strip()

    if target_enabled:
        if password or confirm:
            if stored_password_exists:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "password_already_set",
                        "message": "已存在管理员密码，请启用认证后通过修改密码功能更新",
                    },
                )
            if not password:
                return JSONResponse(
                    status_code=400,
                    content={"error": "password_required", "message": "请输入要设置的管理员密码"},
                )
            if password != confirm:
                return JSONResponse(
                    status_code=400,
                    content={"error": "password_mismatch", "message": "两次输入的密码不一致"},
                )
            if has_stored_password():
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "password_already_set",
                        "message": "已存在管理员密码，请启用认证后通过修改密码功能更新",
                    },
                )
            err = set_initial_password(password)
            if err:
                return JSONResponse(
                    status_code=400,
                    content={"error": "invalid_password", "message": err},
                )
        elif not stored_password_exists:
            return JSONResponse(
                status_code=400,
                content={"error": "password_required", "message": "开启密码登录前请先设置密码"},
            )
        else:
            # P1 Vulnerability Fix: Enforce current-password check independent of global cached flag
            # We must verify they actually possess a valid admin session, otherwise an attacker
            # could hit a race condition when auth becomes enabled mid-flight.
            # This triggers whenever trying to enable/keep enabled an existing auth setup.
            cookie_val = request.cookies.get(COOKIE_NAME)
            # if target_enabled is True here, they are requesting to enable or keep auth enabled
            is_valid_session = cookie_val and get_session_identity(cookie_val) is not None
            
            if not is_valid_session:
                if not current_password:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "current_required", "message": "重新开启认证前请输入当前密码"},
                    )
                ip = get_client_ip(request)
                if not check_rate_limit(ip):
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "rate_limited",
                            "message": "Too many failed attempts. Please try again later.",
                        },
                    )
                if not verify_stored_password_and_upgrade(current_password):
                    record_login_failure(ip)
                    return JSONResponse(
                        status_code=401,
                        content={"error": "invalid_password", "message": "当前密码错误"},
                    )
                clear_rate_limit(ip)
    else:
        if current_enabled:
            cookie_val = request.cookies.get(COOKIE_NAME)
            is_valid_session = cookie_val and get_session_identity(cookie_val) is not None

            if not is_valid_session:
                if not current_password:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "current_required", "message": "关闭认证前请输入当前密码"},
                    )
                ip = get_client_ip(request)
                if not check_rate_limit(ip):
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "rate_limited",
                            "message": "Too many failed attempts. Please try again later.",
                        },
                    )
                if not verify_stored_password_and_upgrade(current_password):
                    record_login_failure(ip)
                    return JSONResponse(
                        status_code=401,
                        content={"error": "invalid_password", "message": "当前密码错误"},
                    )
                clear_rate_limit(ip)

    if target_enabled != current_enabled:
        if not _apply_auth_enabled(target_enabled, request=request):
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "Failed to update auth settings"},
            )
        if not rotate_session_secret():
            rollback_ok = _apply_auth_enabled(current_enabled, request=request)
            if not rollback_ok:
                logger.error("Failed to roll back auth state after session secret rotation failure")
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "Failed to rotate session secret"},
            )
    else:
        if not _apply_auth_enabled(target_enabled, request=request):
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "Failed to update auth settings"},
            )

    if target_enabled:
        session_val = _persist_session_for_user(
            request=request,
            user_id=current_user.user_id,
            username=current_user.username,
            role=current_user.role,
        )
        if not session_val:
            rollback_ok = _apply_auth_enabled(current_enabled, request=request)
            if not rollback_ok:
                logger.error("Failed to roll back auth state after session creation failure")
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "Failed to create session"},
            )
        _clear_current_user_cache(request)
        # We manually set loggedIn=True because the cookie is being set in this response
        # and won't be visible in request.cookies until the NEXT request.
        content = _get_auth_status_dict(request)
        content["loggedIn"] = True
        capabilities, flags = _current_user_capability_summary(current_user)
        content["currentUser"] = CurrentUserResponse(
            id=current_user.user_id,
            username=current_user.username,
            displayName=current_user.display_name,
            role=current_user.role,
            isAdmin=current_user.is_admin,
            isAuthenticated=True,
            transitional=False,
            authEnabled=True,
            legacyAdmin=current_user.legacy_admin,
            adminCapabilities=capabilities,
            **flags,
        ).model_dump(by_alias=True)
        resp = JSONResponse(content=content)
        _set_session_cookie(resp, session_val, request)
        return resp

    _clear_current_user_cache(request)
    resp = JSONResponse(content=_get_auth_status_dict(request))
    _delete_session_cookie(resp, request)
    return resp



@router.post(
    "/login",
    summary="Login or create initial user credentials",
    description="Verify a user password and set the session cookie. Can bootstrap the admin password or create a new normal-user account.",
)
async def auth_login(request: Request, body: LoginRequest):
    """Login or create a minimal app-user credential and issue an authenticated session."""
    if not is_auth_enabled():
        return JSONResponse(
            status_code=400,
            content={"error": "auth_disabled", "message": "Authentication is not configured"},
        )

    username = _normalize_username(body.username) or BOOTSTRAP_ADMIN_USERNAME
    password = (body.password or "").strip()
    confirm = (body.password_confirm or "").strip()
    create_user = bool(body.create_user)
    if not password:
        return JSONResponse(
            status_code=400,
            content={"error": "password_required", "message": "请输入密码"},
        )

    ip = get_client_ip(request)
    admin_flow = username == BOOTSTRAP_ADMIN_USERNAME
    if not check_rate_limit(ip, username, admin=admin_flow):
        _audit_login_event(
            request=request,
            action="security.login_rate_limited",
            username=username,
            outcome="rate_limited",
            status="failed",
            admin=admin_flow,
        )
        return _rate_limited_error()

    repo = AuthRepository()
    user_row = repo.get_app_user_by_username(username)
    created_user = False

    if username == BOOTSTRAP_ADMIN_USERNAME:
        ensure_bootstrap_admin_user_password_hash()
        if user_row is None:
            user_row = repo.ensure_bootstrap_admin_user()
        if user_row is not None and not getattr(user_row, "is_active", True):
            _record_login_failure_and_audit(
                request,
                ip=ip,
                username=username,
                outcome="disabled_user",
                user_id=str(getattr(user_row, "id", "") or ""),
                admin=True,
            )
            return _generic_login_error()
        if not has_stored_password():
            if not confirm:
                return JSONResponse(
                    status_code=400,
                    content={"error": "password_confirm_required", "message": "请确认管理员初始密码"},
                )
            if password != confirm:
                _record_login_failure_and_audit(
                    request,
                    ip=ip,
                    username=username,
                    outcome="password_mismatch",
                    admin=True,
                )
                return JSONResponse(
                    status_code=400,
                    content={"error": "password_mismatch", "message": "两次输入的密码不一致"},
                )
            err = set_initial_password(password)
            if err:
                _record_login_failure_and_audit(
                    request,
                    ip=ip,
                    username=username,
                    outcome="invalid_password_policy",
                    admin=True,
                )
                return JSONResponse(
                    status_code=400,
                    content={"error": "invalid_password", "message": err},
                )
            ensure_bootstrap_admin_user_password_hash()
            user_row = repo.get_app_user(BOOTSTRAP_ADMIN_USER_ID)
            created_user = True
        elif not verify_stored_password_and_upgrade(password):
            _record_login_failure_and_audit(
                request,
                ip=ip,
                username=username,
                outcome="invalid_password",
                user_id=str(getattr(user_row, "id", "") or ""),
                admin=True,
            )
            return _generic_login_error()
    else:
        if user_row is None:
            if not create_user and not confirm:
                _record_login_failure_and_audit(
                    request,
                    ip=ip,
                    username=username,
                    outcome="unknown_user",
                )
                return _generic_login_error()
            if password != confirm:
                _record_login_failure_and_audit(
                    request,
                    ip=ip,
                    username=username,
                    outcome="password_mismatch",
                )
                return JSONResponse(
                    status_code=400,
                    content={"error": "password_mismatch", "message": "两次输入的密码不一致"},
                )
            try:
                password_hash = hash_password_for_storage(password)
            except ValueError as exc:
                _record_login_failure_and_audit(
                    request,
                    ip=ip,
                    username=username,
                    outcome="invalid_password_policy",
                )
                return JSONResponse(
                    status_code=400,
                    content={"error": "invalid_password", "message": str(exc)},
                )
            user_row = repo.create_or_update_app_user(
                user_id=f"user-{secrets.token_hex(8)}",
                username=username,
                display_name=(body.display_name or "").strip() or username,
                role=ROLE_USER,
                password_hash=password_hash,
                is_active=True,
            )
            created_user = True
        else:
            if not getattr(user_row, "is_active", True):
                _record_login_failure_and_audit(
                    request,
                    ip=ip,
                    username=username,
                    outcome="disabled_user",
                    user_id=str(getattr(user_row, "id", "") or ""),
                )
                return _generic_login_error()
            stored_hash = getattr(user_row, "password_hash", None)
            if not stored_hash:
                if not confirm:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "password_not_initialized", "message": "该账户尚未设置密码"},
                    )
                if password != confirm:
                    _record_login_failure_and_audit(
                        request,
                        ip=ip,
                        username=username,
                        outcome="password_mismatch",
                        user_id=str(getattr(user_row, "id", "") or ""),
                    )
                    return JSONResponse(
                        status_code=400,
                        content={"error": "password_mismatch", "message": "两次输入的密码不一致"},
                    )
                try:
                    password_hash = hash_password_for_storage(password)
                except ValueError as exc:
                    _record_login_failure_and_audit(
                        request,
                        ip=ip,
                        username=username,
                        outcome="invalid_password_policy",
                        user_id=str(getattr(user_row, "id", "") or ""),
                    )
                    return JSONResponse(
                        status_code=400,
                        content={"error": "invalid_password", "message": str(exc)},
                    )
                user_row = repo.create_or_update_app_user(
                    user_id=str(user_row.id),
                    username=str(user_row.username),
                    display_name=getattr(user_row, "display_name", None) or str(user_row.username),
                    role=str(user_row.role),
                    password_hash=password_hash,
                    is_active=bool(getattr(user_row, "is_active", True)),
                )
            elif not verify_password_hash_string(password, stored_hash):
                reconciled_row = repo.reconcile_legacy_app_user_for_login(
                    username=username,
                    password=password,
                )
                if reconciled_row is None:
                    _record_login_failure_and_audit(
                        request,
                        ip=ip,
                        username=username,
                        outcome="invalid_password",
                        user_id=str(getattr(user_row, "id", "") or ""),
                    )
                    return _generic_login_error()
                user_row = reconciled_row
            else:
                user_row = _upgrade_app_user_password_hash_if_needed(user_row, password)

    mfa_error = _verify_login_mfa_requirement(
        request=request,
        username=username,
        user_row=user_row,
        body=body,
    )
    if mfa_error is not None:
        return mfa_error

    if str(getattr(user_row, "id", "") or "") == BOOTSTRAP_ADMIN_USER_ID:
        repo.ensure_bootstrap_admin_role_assignment()

    had_failures = has_rate_limit_failures(ip, username)
    clear_rate_limit(ip, username)
    if had_failures:
        _audit_login_event(
            request=request,
            action="security.login_success_after_failures",
            username=username,
            outcome="success_after_failures",
            status="completed",
            user_id=str(getattr(user_row, "id", "") or ""),
            admin=str(getattr(user_row, "role", "")) == ROLE_ADMIN,
        )
    session_val = _persist_session_for_user(
        request=request,
        user_id=str(user_row.id),
        username=str(user_row.username),
        role=str(user_row.role),
    )
    if not session_val:
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "Failed to create session"},
        )

    resp = JSONResponse(
        content={
            "ok": True,
            "createdUser": created_user,
            "currentUser": _current_user_response(
                id=str(user_row.id),
                username=str(user_row.username),
                displayName=getattr(user_row, "display_name", None),
                role=str(user_row.role),
                isAdmin=str(user_row.role) == ROLE_ADMIN,
                isAuthenticated=True,
                transitional=False,
                authEnabled=True,
                legacyAdmin=False,
                adminCapabilities=sorted(expand_admin_capabilities(user_row)),
            ).model_dump(by_alias=True),
        }
    )
    _set_session_cookie(resp, session_val, request)
    return resp


@router.post(
    "/reset-password/request",
    summary="Request password reset",
    description="Trigger the backend password-reset flow without revealing whether the account exists.",
)
async def auth_request_password_reset(body: PasswordResetRequest):
    """Accept a password reset request and return a generic non-enumerating response."""
    identifier = (body.identifier or "").strip()
    if not identifier:
        return JSONResponse(
            status_code=400,
            content={"error": "identifier_required", "message": "请输入邮箱地址或用户名"},
        )

    logger.info(
        "Password reset requested identifier_hash=%s",
        safe_identifier_hash(identifier, prefix="acct"),
    )
    return JSONResponse(
        status_code=202,
        content={
            "ok": True,
            "message": "如果该账户存在，系统已接受重置请求。请按后续提示完成密码重置。",
        },
    )


@router.post(
    "/change-password",
    summary="Change password",
    description="Change password. Requires valid session.",
)
async def auth_change_password(request: Request, body: ChangePasswordRequest):
    """Change password. Requires login."""
    if not is_password_changeable():
        return JSONResponse(
            status_code=400,
            content={"error": "not_changeable", "message": "Password cannot be changed via web"},
        )

    current = (body.current_password or "").strip()
    new_pwd = (body.new_password or "").strip()
    new_confirm = (body.new_password_confirm or "").strip()

    if not current:
        return JSONResponse(
            status_code=400,
            content={"error": "current_required", "message": "请输入当前密码"},
        )
    if new_pwd != new_confirm:
        return JSONResponse(
            status_code=400,
            content={"error": "password_mismatch", "message": "两次输入的新密码不一致"},
        )

    current_user = resolve_current_user(request)
    if current_user is None:
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": "Login required"},
        )

    if current_user.user_id == BOOTSTRAP_ADMIN_USER_ID:
        err = change_password(current, new_pwd)
        if err:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_password", "message": err},
            )
        if current_user.session_id:
            AuthRepository().revoke_all_app_user_sessions(current_user.user_id)
    else:
        repo = AuthRepository()
        user_row = repo.get_app_user(current_user.user_id)
        if user_row is None:
            return JSONResponse(
                status_code=404,
                content={"error": "user_not_found", "message": "Current user not found"},
            )
        if not verify_password_hash_string(current, getattr(user_row, "password_hash", None)):
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_password", "message": "当前密码错误"},
            )
        try:
            new_hash = hash_password_for_storage(new_pwd)
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_password", "message": str(exc)},
            )
        repo.create_or_update_app_user(
            user_id=str(user_row.id),
            username=str(user_row.username),
            display_name=getattr(user_row, "display_name", None) or str(user_row.username),
            role=str(user_row.role),
            password_hash=new_hash,
            is_active=bool(getattr(user_row, "is_active", True)),
        )
        if current_user.session_id:
            repo.revoke_all_app_user_sessions(current_user.user_id)

    return Response(status_code=204)


@router.post(
    "/logout",
    summary="Logout",
    description="Clear session cookie.",
)
async def auth_logout(request: Request):
    """Clear session cookie."""
    resp = Response(status_code=204)
    _delete_session_cookie(resp, request)
    cookie_value = str((getattr(request, "cookies", {}) or {}).get(COOKIE_NAME) or "")
    identity = get_session_identity(cookie_value) if cookie_value else None
    if identity is None:
        return resp

    try:
        repo = AuthRepository()
        session_id = get_session_revocation_id(cookie_value, identity)
        if identity.session_id is None:
            repo.create_app_user_session(
                session_id=session_id,
                user_id=identity.user_id,
                expires_at=datetime.fromtimestamp(identity.expires_at, tz=timezone.utc),
            )
        repo.revoke_app_user_session(session_id)
    except Exception as exc:  # pragma: no cover - defensive persistence path
        logger.error("Failed to terminate current auth session: %s", exc)
        resp.status_code = 500
    return resp
