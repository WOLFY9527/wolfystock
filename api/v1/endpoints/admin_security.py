# -*- coding: utf-8 -*-
"""Admin-only account security actions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import CurrentUser, require_admin_capability, require_recent_admin_reauth
from api.v1.schemas.admin_security import AdminSecurityActionRequest, AdminSecurityActionResponse
from src.auth import get_admin_reauth_max_age_seconds
from src.services.admin_security_service import AdminSecurityError, AdminSecurityResult, AdminSecurityService

router = APIRouter()


def _require_confirmation(body: AdminSecurityActionRequest, expected: str) -> None:
    if str(body.confirm or "").strip() != expected:
        raise HTTPException(
            status_code=400,
            detail={"error": "confirmation_mismatch", "message": f"confirm must be {expected}"},
        )


def _response(result: AdminSecurityResult) -> AdminSecurityActionResponse:
    return AdminSecurityActionResponse(
        targetUserId=result.target_user_id,
        action=result.action,
        status=result.status,
        changed=result.changed,
        sessionsRevoked=result.sessions_revoked,
        auditEventId=result.audit_event_id,
        message=result.message,
    )


def _raise_service_error(exc: AdminSecurityError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"error": exc.error, "message": exc.message},
    ) from None


def _require_admin_security_write(
    current_user: CurrentUser = Depends(require_admin_capability("users:security:write")),
) -> CurrentUser:
    if current_user.transitional and not current_user.auth_enabled and not current_user.is_authenticated:
        return current_user
    max_age_minutes = max(1, get_admin_reauth_max_age_seconds() // 60)
    return require_recent_admin_reauth(current_user, max_age_minutes=max_age_minutes)


@router.post(
    "/users/{user_id}/disable",
    response_model=AdminSecurityActionResponse,
    summary="Disable one app user account",
)
def disable_admin_user(
    user_id: str,
    body: AdminSecurityActionRequest,
    current_user: CurrentUser = Depends(_require_admin_security_write),
) -> AdminSecurityActionResponse:
    _require_confirmation(body, "DISABLE")
    try:
        result = AdminSecurityService().disable_user(
            target_user_id=user_id,
            current_user=current_user,
            reason=body.reason,
            revoke_sessions=body.revoke_sessions,
        )
    except AdminSecurityError as exc:
        _raise_service_error(exc)
    return _response(result)


@router.post(
    "/users/{user_id}/enable",
    response_model=AdminSecurityActionResponse,
    summary="Enable one app user account",
)
def enable_admin_user(
    user_id: str,
    body: AdminSecurityActionRequest,
    current_user: CurrentUser = Depends(_require_admin_security_write),
) -> AdminSecurityActionResponse:
    _require_confirmation(body, "ENABLE")
    try:
        result = AdminSecurityService().enable_user(
            target_user_id=user_id,
            current_user=current_user,
            reason=body.reason,
        )
    except AdminSecurityError as exc:
        _raise_service_error(exc)
    return _response(result)


@router.post(
    "/users/{user_id}/revoke-sessions",
    response_model=AdminSecurityActionResponse,
    summary="Revoke all sessions for one app user",
)
def revoke_admin_user_sessions(
    user_id: str,
    body: AdminSecurityActionRequest,
    current_user: CurrentUser = Depends(_require_admin_security_write),
) -> AdminSecurityActionResponse:
    _require_confirmation(body, "REVOKE_SESSIONS")
    if body.scope != "all":
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "scope must be all"})
    try:
        result = AdminSecurityService().revoke_sessions(
            target_user_id=user_id,
            current_user=current_user,
            reason=body.reason,
        )
    except AdminSecurityError as exc:
        _raise_service_error(exc)
    return _response(result)
