# -*- coding: utf-8 -*-
"""Owner-scoped in-app user alert endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import CurrentUser, get_current_user
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.user_alerts import (
    UserAlertDryRunRequest,
    UserAlertDryRunResponse,
    UserAlertEventListResponse,
    UserAlertRuleCreateRequest,
    UserAlertRuleDeleteResponse,
    UserAlertRuleListResponse,
    UserAlertRuleModel,
    UserAlertRuleUpdateRequest,
)
from src.services.execution_log_service import ExecutionLogService
from src.services.user_alert_dry_run_pipeline import build_user_alert_dry_run_pipeline_result
from src.services.user_alert_service import UserAlertService

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_user_alert_service() -> UserAlertService:
    return UserAlertService()


def _owner_id(current_user: CurrentUser) -> str:
    if not current_user.is_authenticated:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "Login required"},
        )
    return current_user.user_id


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"error": "validation_error", "message": str(exc)},
    )


def _not_found(rule_id: int) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": "not_found", "message": f"User alert rule not found: {rule_id}"},
    )


def _internal_error(message: str, exc: Exception) -> HTTPException:
    logger.error("%s: %s", message, exc, exc_info=True)
    return HTTPException(
        status_code=500,
        detail={"error": "internal_error", "message": f"{message}: {str(exc)}"},
    )


def _actor(current_user: CurrentUser) -> dict:
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "display_name": current_user.display_name,
        "role": "admin" if current_user.is_admin else "user",
        "actor_type": "admin" if current_user.is_admin else "user",
        "session_id": current_user.session_id,
    }


def _record_alert_audit(
    *,
    event_type: str,
    message: str,
    current_user: CurrentUser,
    rule: dict | None = None,
    rule_id: int | None = None,
    metadata: dict | None = None,
) -> None:
    try:
        payload = dict(metadata or {})
        if isinstance(rule, dict):
            payload.update(
                {
                    "rule_type": rule.get("rule_type"),
                    "symbol": rule.get("symbol"),
                    "direction": rule.get("direction"),
                    "enabled": bool(rule.get("enabled")),
                }
            )
            rule_id = int(rule.get("id")) if rule.get("id") is not None else rule_id
        ExecutionLogService().record_user_write_action(
            event_type=event_type,
            message=message,
            actor=_actor(current_user),
            domain="alert",
            target_type="alert_rule",
            target_id=rule_id,
            status="completed",
            metadata={"route_family": "user_alerts", **payload},
        )
    except Exception as exc:
        logger.warning("Record alert user action audit failed: %s", exc)


@router.get(
    "/rules",
    response_model=UserAlertRuleListResponse,
    responses={401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="List current user's in-app alert rules",
)
def list_alert_rules(
    current_user: CurrentUser = Depends(get_current_user),
) -> UserAlertRuleListResponse:
    service = _get_user_alert_service()
    try:
        owner_id = _owner_id(current_user)
        return UserAlertRuleListResponse(
            items=[UserAlertRuleModel(**item) for item in service.list_rules(owner_id=owner_id)],
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error("List user alert rules failed", exc) from exc


@router.post(
    "/rules",
    response_model=UserAlertRuleModel,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Create a watchlist price threshold alert rule",
)
def create_alert_rule(
    request: UserAlertRuleCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> UserAlertRuleModel:
    service = _get_user_alert_service()
    try:
        owner_id = _owner_id(current_user)
        created = service.create_rule(
            owner_id=owner_id,
            symbol=request.symbol,
            direction=request.direction,
            threshold_price=request.threshold_price,
            enabled=request.enabled,
            note=request.note,
        )
        _record_alert_audit(
            event_type="alert.rule_created",
            message="Alert rule created",
            current_user=current_user,
            rule=created,
        )
        return UserAlertRuleModel(**created)
    except HTTPException:
        raise
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except Exception as exc:
        raise _internal_error("Create user alert rule failed", exc) from exc


@router.patch(
    "/rules/{rule_id}",
    response_model=UserAlertRuleModel,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Update a watchlist price threshold alert rule",
)
def update_alert_rule(
    rule_id: int,
    request: UserAlertRuleUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> UserAlertRuleModel:
    service = _get_user_alert_service()
    try:
        owner_id = _owner_id(current_user)
        updated = service.update_rule(
            owner_id=owner_id,
            rule_id=rule_id,
            **request.model_dump(exclude_unset=True),
        )
        if updated is None:
            raise _not_found(rule_id)
        event_type = "alert.rule_updated"
        if request.enabled is True:
            event_type = "alert.rule_enabled"
        elif request.enabled is False:
            event_type = "alert.rule_disabled"
        _record_alert_audit(
            event_type=event_type,
            message="Alert rule updated",
            current_user=current_user,
            rule=updated,
            rule_id=rule_id,
        )
        return UserAlertRuleModel(**updated)
    except HTTPException:
        raise
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except Exception as exc:
        raise _internal_error("Update user alert rule failed", exc) from exc


@router.delete(
    "/rules/{rule_id}",
    response_model=UserAlertRuleDeleteResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Delete a watchlist price threshold alert rule",
)
def delete_alert_rule(
    rule_id: int,
    current_user: CurrentUser = Depends(get_current_user),
) -> UserAlertRuleDeleteResponse:
    service = _get_user_alert_service()
    try:
        owner_id = _owner_id(current_user)
        if not service.delete_rule(owner_id=owner_id, rule_id=rule_id):
            raise _not_found(rule_id)
        _record_alert_audit(
            event_type="alert.rule_deleted",
            message="Alert rule deleted",
            current_user=current_user,
            rule_id=rule_id,
        )
        return UserAlertRuleDeleteResponse(deleted=1)
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error("Delete user alert rule failed", exc) from exc


@router.post(
    "/rules/{rule_id}/dry-run",
    response_model=UserAlertDryRunResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Evaluate a current user's alert rule with caller-supplied local data",
)
def dry_run_alert_rule(
    rule_id: int,
    request: UserAlertDryRunRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> UserAlertDryRunResponse:
    service = _get_user_alert_service()
    try:
        owner_id = _owner_id(current_user)
        rule = service.get_rule(owner_id=owner_id, rule_id=rule_id)
        if rule is None:
            raise _not_found(rule_id)
        return UserAlertDryRunResponse(
            **build_user_alert_dry_run_pipeline_result(
                rule=rule,
                observed_price=request.observed_price,
                observed_at=request.observed_at,
                freshness=request.freshness.model_dump(by_alias=True, exclude_none=True),
                suppression=(
                    request.suppression.model_dump(by_alias=True, exclude_none=True)
                    if request.suppression is not None
                    else None
                ),
            )
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except Exception as exc:
        raise _internal_error("Dry-run user alert rule failed", exc) from exc


@router.get(
    "/events",
    response_model=UserAlertEventListResponse,
    responses={401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="List current user's in-app alert events",
)
def list_alert_events(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
) -> UserAlertEventListResponse:
    service = _get_user_alert_service()
    try:
        owner_id = _owner_id(current_user)
        return UserAlertEventListResponse(
            **service.list_events(owner_id=owner_id, limit=limit, offset=offset),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error("List user alert events failed", exc) from exc
