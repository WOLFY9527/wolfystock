# -*- coding: utf-8 -*-
"""Admin-only read APIs for safe user directory and activity projections."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import CurrentUser, require_admin_capability, require_recent_admin_reauth
from api.v1.schemas.admin_activity import AdminActivityEvent, AdminActivityResponse, AdminActivityWindow
from api.v1.schemas.admin_security import AdminUserOnboardRequest, AdminUserOnboardResponse
from api.v1.schemas.admin_users import (
    AdminDataLinks,
    AdminSessionSummary,
    AdminSessionSummaryCounts,
    AdminUserDetailResponse,
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserRiskBadge,
)
from src.auth import get_admin_reauth_max_age_seconds
from src.auth_context import AdminActorContext
from src.services.admin_activity_service import AdminActivityService
from src.services.admin_user_onboarding_service import AdminUserOnboardingError, AdminUserOnboardingService
from src.services.admin_user_service import AdminUserService

router = APIRouter()

USER_SORT_VALUES = {
    "created_at_desc",
    "created_at_asc",
    "updated_at_desc",
    "username_asc",
    "username_desc",
    "last_seen_desc",
    "last_seen_asc",
}
USER_STATUS_VALUES = {"all", "active", "inactive", "needs_password", "sessionless", "stale_session"}
SESSION_STATUS_VALUES = {"all", "active", "expired", "revoked"}
ROLE_VALUES = {"admin", "user"}
ACTOR_TYPE_VALUES = {"admin", "user", "guest", "anonymous", "system"}


def _parse_optional_datetime(value: Optional[str], *, name: str) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": f"Invalid datetime for {name}"},
        ) from None


def _validate_value(value: Optional[str], allowed: set[str], *, name: str) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized not in allowed:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": f"Invalid {name}: {value}"},
        )
    return normalized


def _default_activity_window(*, route: str, date_from: Optional[str], date_to: Optional[str]) -> tuple[datetime, datetime, int]:
    end = _parse_optional_datetime(date_to, name="to") or datetime.now()
    start = _parse_optional_datetime(date_from, name="from")
    if route == "user":
        max_days = 90
        default_days = 7
    else:
        max_days = 30
        default_days = 1
    if start is None:
        start = end - timedelta(days=default_days)
    if start > end:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": "from must be before to"},
        )
    if end - start > timedelta(days=max_days):
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": f"window exceeds {max_days} days"},
        )
    return start, end, max_days


def _build_activity_response(
    *,
    items: list[dict[str, Any]],
    total: int,
    limit: int,
    offset: int,
    start: datetime,
    end: datetime,
    max_days: int,
) -> AdminActivityResponse:
    return AdminActivityResponse(
        items=[AdminActivityEvent.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
        hasMore=offset + limit < total,
        window=AdminActivityWindow(**{"from": start.isoformat(), "to": end.isoformat(), "maxDays": max_days}),
        limitations=[
            "scanner_backtest_portfolio_domain_projections_deferred",
            "raw_payloads_excluded",
        ],
    )


def _build_user_list_item(item: dict[str, Any]) -> AdminUserListItem:
    session_summary = AdminSessionSummaryCounts.model_validate(item.get("session_summary") or {})
    risk_badges = [
        AdminUserRiskBadge.model_validate(badge)
        for badge in item.get("risk_badges") or []
    ]
    links = AdminDataLinks.model_validate(item.get("links") or {})
    return AdminUserListItem.model_validate(
        {
            **item,
            "session_summary": session_summary,
            "risk_badges": risk_badges,
            "links": links,
        }
    )


def _build_session_summary(item: dict[str, Any]) -> AdminSessionSummary:
    return AdminSessionSummary.model_validate(item)


def _to_admin_actor(current_user: CurrentUser) -> AdminActorContext:
    return AdminActorContext(
        user_id=current_user.user_id,
        username=current_user.username,
        display_name=current_user.display_name,
        role=current_user.role,
        is_admin=current_user.is_admin,
    )


def _require_onboarding_security_write(
    current_user: CurrentUser = Depends(require_admin_capability("users:security:write")),
) -> CurrentUser:
    if current_user.transitional and not current_user.auth_enabled and not current_user.is_authenticated:
        return current_user
    max_age_minutes = max(1, get_admin_reauth_max_age_seconds() // 60)
    try:
        return require_recent_admin_reauth(current_user, max_age_minutes=max_age_minutes)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        if detail.get("error") == "admin_reauth_required":
            AdminUserOnboardingService().record_failure_audit(
                actor=_to_admin_actor(current_user),
                reason_code="admin_reauth_required",
            )
        raise


@router.get(
    "/users",
    response_model=AdminUserListResponse,
    summary="List safe admin user directory entries",
)
def list_admin_users(
    q: Optional[str] = Query(default=None, max_length=128),
    role: Optional[str] = Query(default=None),
    status: str = Query(default="all"),
    active: Optional[bool] = Query(default=None),
    created_from: Optional[str] = Query(default=None),
    created_to: Optional[str] = Query(default=None),
    last_seen_from: Optional[str] = Query(default=None),
    last_seen_to: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=10000),
    sort: str = Query(default="created_at_desc"),
    _: CurrentUser = Depends(require_admin_capability("users:read")),
) -> AdminUserListResponse:
    role = _validate_value(role, ROLE_VALUES, name="role")
    status = _validate_value(status, USER_STATUS_VALUES, name="status") or "all"
    sort = _validate_value(sort, USER_SORT_VALUES, name="sort") or "created_at_desc"
    if status == "active" and active is False:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "status and active conflict"})
    if status == "inactive" and active is True:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "status and active conflict"})

    service = AdminUserService()
    items, total = service.list_users(
        q=str(q).strip() if isinstance(q, str) and q.strip() else None,
        role=role,
        status=status,
        active=active,
        created_from=_parse_optional_datetime(created_from, name="created_from"),
        created_to=_parse_optional_datetime(created_to, name="created_to"),
        last_seen_from=_parse_optional_datetime(last_seen_from, name="last_seen_from"),
        last_seen_to=_parse_optional_datetime(last_seen_to, name="last_seen_to"),
        sort=sort,
        limit=limit,
        offset=offset,
    )
    validated_items = [_build_user_list_item(item) for item in items]
    return AdminUserListResponse(
        items=validated_items,
        total=total,
        limit=limit,
        offset=offset,
        hasMore=offset + limit < total,
    )


@router.get(
    "/users/{user_id}",
    response_model=AdminUserDetailResponse,
    summary="Read one safe admin user detail projection",
)
def get_admin_user_detail(
    user_id: str,
    include_sessions: bool = Query(default=True),
    session_limit: int = Query(default=20, ge=1, le=50),
    session_status: str = Query(default="all"),
    _: CurrentUser = Depends(require_admin_capability("users:read")),
) -> AdminUserDetailResponse:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id or len(normalized_user_id) > 64:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "Invalid user_id"})
    session_status = _validate_value(session_status, SESSION_STATUS_VALUES, name="session_status") or "all"

    service = AdminUserService()
    user, sessions = service.get_user_detail(
        normalized_user_id,
        include_sessions=include_sessions,
        session_limit=session_limit,
        session_status=session_status,
    )
    if user is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "User not found"})
    validated_user = _build_user_list_item(user)
    validated_sessions = [_build_session_summary(session) for session in sessions]
    return AdminUserDetailResponse(
        user=validated_user,
        sessions=validated_sessions,
        dataLinks=AdminDataLinks(
            self=f"/api/v1/admin/users/{normalized_user_id}",
            adminLogs=f"/api/v1/admin/logs?user_id={normalized_user_id}",
            activity=f"/api/v1/admin/users/{normalized_user_id}/activity",
            portfolio=None,
            analysis=None,
            scanner=None,
            backtest=None,
        ),
        limitations=[
            "failed_login_count_unavailable",
            "client_device_metadata_unavailable",
        ],
    )


@router.post(
    "/users/onboard",
    response_model=AdminUserOnboardResponse,
    summary="Create a normal active user for private-beta onboarding",
    description=(
        "Creates a normal active private-beta user. The response returns initialPassword "
        "exactly once with passwordDelivery=returned_once; clients and operators must treat "
        "it as one-time secret material and must not log or persist the response body."
    ),
)
def onboard_admin_user(
    body: AdminUserOnboardRequest,
    current_user: CurrentUser = Depends(_require_onboarding_security_write),
) -> AdminUserOnboardResponse:
    try:
        result = AdminUserOnboardingService().create_user(
            actor=_to_admin_actor(current_user),
            username=body.username,
            display_name=body.display_name,
            email=body.email,
            password=body.password,
            reason=body.reason,
        )
    except AdminUserOnboardingError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.error, "message": exc.message},
        ) from None

    payload = {
        "targetUserId": result.target_user_id,
        "username": result.username,
        "role": "user",
        "created": result.created,
        "passwordDelivery": "returned_once",
        "initialPassword": result.initial_password,
        "auditEventId": result.audit_event_id,
        "message": result.message,
    }
    return AdminUserOnboardResponse.model_validate(payload)


@router.get(
    "/users/{user_id}/activity",
    response_model=AdminActivityResponse,
    summary="List safe admin activity for one user",
)
def list_admin_user_activity(
    user_id: str,
    date_from: Optional[str] = Query(default=None, alias="from"),
    date_from_alias: Optional[str] = Query(default=None, alias="date_from"),
    date_to: Optional[str] = Query(default=None, alias="to"),
    date_to_alias: Optional[str] = Query(default=None, alias="date_to"),
    family: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    entity_type: Optional[str] = Query(default=None),
    actor_type: Optional[str] = Query(default=None),
    target_user: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None, max_length=128),
    include_system: bool = Query(default=False),
    include_admin: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    _: CurrentUser = Depends(require_admin_capability("users:activity:read")),
) -> AdminActivityResponse:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id or len(normalized_user_id) > 64:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "Invalid user_id"})
    if target_user and str(target_user).strip() != normalized_user_id:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "target_user must match path user_id"})
    if actor_type:
        actor_type = _validate_value(actor_type, ACTOR_TYPE_VALUES, name="actor_type")
    start, end, max_days = _default_activity_window(
        route="user",
        date_from=date_from or date_from_alias,
        date_to=date_to or date_to_alias,
    )
    service = AdminActivityService()
    items, total = service.list_activity(
        target_user_id=normalized_user_id,
        date_from=start,
        date_to=end,
        family=family or category,
        status=status,
        entity_type=entity_type,
        actor_type=actor_type,
        q=str(q).strip() if isinstance(q, str) and q.strip() else None,
        include_system=include_system,
        include_admin=include_admin,
        limit=limit,
        offset=offset,
    )
    return _build_activity_response(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        start=start,
        end=end,
        max_days=max_days,
    )


@router.get(
    "/activity",
    response_model=AdminActivityResponse,
    summary="List safe global admin activity",
)
def list_admin_activity(
    date_from: Optional[str] = Query(default=None, alias="from"),
    date_from_alias: Optional[str] = Query(default=None, alias="date_from"),
    date_to: Optional[str] = Query(default=None, alias="to"),
    date_to_alias: Optional[str] = Query(default=None, alias="date_to"),
    family: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    entity_type: Optional[str] = Query(default=None),
    actor_type: Optional[str] = Query(default=None),
    target_user: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None, max_length=128),
    include_system: bool = Query(default=False),
    include_admin: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    _: CurrentUser = Depends(require_admin_capability("users:activity:read")),
) -> AdminActivityResponse:
    if actor_type:
        actor_type = _validate_value(actor_type, ACTOR_TYPE_VALUES, name="actor_type")
    normalized_target = str(target_user or "").strip() or None
    start, end, max_days = _default_activity_window(
        route="global",
        date_from=date_from or date_from_alias,
        date_to=date_to or date_to_alias,
    )
    service = AdminActivityService()
    items, total = service.list_activity(
        target_user_id=normalized_target,
        date_from=start,
        date_to=end,
        family=family or category,
        status=status,
        entity_type=entity_type,
        actor_type=actor_type,
        q=str(q).strip() if isinstance(q, str) and q.strip() else None,
        include_system=include_system,
        include_admin=include_admin,
        limit=limit,
        offset=offset,
    )
    return _build_activity_response(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        start=start,
        end=end,
        max_days=max_days,
    )
