# -*- coding: utf-8 -*-
"""Admin-only operational notification channel APIs."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import CurrentUser, require_admin_user
from api.v1.schemas.admin_notifications import (
    NotificationChannelCreateRequest,
    NotificationChannelListResponse,
    NotificationChannelModel,
    NotificationChannelTestResponse,
    NotificationChannelUpdateRequest,
    NotificationEventAckResponse,
    NotificationEventListResponse,
)
from src.services.notification_service import NotificationService

router = APIRouter()


def _service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(exc)},
        )
    if isinstance(exc, ValueError):
        return HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=500,
        detail={"error": "notification_error", "message": str(exc)},
    )


@router.get(
    "/notification-channels",
    response_model=NotificationChannelListResponse,
    summary="List admin notification channels",
)
def list_notification_channels(
    _: CurrentUser = Depends(require_admin_user),
):
    return NotificationChannelListResponse(items=NotificationService().list_channels())


@router.post(
    "/notification-channels",
    response_model=NotificationChannelModel,
    summary="Create an admin notification channel",
)
def create_notification_channel(
    request: NotificationChannelCreateRequest,
    _: CurrentUser = Depends(require_admin_user),
):
    try:
        return NotificationChannelModel(**NotificationService().create_channel(**request.model_dump()))
    except Exception as exc:
        raise _service_error(exc) from exc


@router.patch(
    "/notification-channels/{channel_id}",
    response_model=NotificationChannelModel,
    summary="Update an admin notification channel",
)
def update_notification_channel(
    channel_id: int,
    request: NotificationChannelUpdateRequest,
    _: CurrentUser = Depends(require_admin_user),
):
    try:
        return NotificationChannelModel(
            **NotificationService().update_channel(
                channel_id,
                **request.model_dump(exclude_unset=True),
            )
        )
    except Exception as exc:
        raise _service_error(exc) from exc


@router.delete(
    "/notification-channels/{channel_id}",
    summary="Delete an admin notification channel",
)
def delete_notification_channel(
    channel_id: int,
    _: CurrentUser = Depends(require_admin_user),
):
    try:
        NotificationService().delete_channel(channel_id)
    except Exception as exc:
        raise _service_error(exc) from exc
    return {"success": True}


@router.post(
    "/notification-channels/{channel_id}/test",
    response_model=NotificationChannelTestResponse,
    summary="Send a test notification through one channel",
)
def test_notification_channel(
    channel_id: int,
    _: CurrentUser = Depends(require_admin_user),
):
    try:
        return NotificationChannelTestResponse(**NotificationService().test_channel(channel_id))
    except Exception as exc:
        raise _service_error(exc) from exc


@router.get(
    "/notifications",
    response_model=NotificationEventListResponse,
    summary="List admin notification events",
)
def list_notifications(
    event_type: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    include_acknowledged: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: CurrentUser = Depends(require_admin_user),
):
    try:
        return NotificationEventListResponse(
            **NotificationService().list_events(
                event_type=event_type,
                severity=severity,
                include_acknowledged=include_acknowledged,
                limit=limit,
                offset=offset,
            )
        )
    except Exception as exc:
        raise _service_error(exc) from exc


@router.post(
    "/notifications/{event_id}/ack",
    response_model=NotificationEventAckResponse,
    summary="Acknowledge an admin notification event",
)
def acknowledge_notification(
    event_id: int,
    current_user: CurrentUser = Depends(require_admin_user),
):
    try:
        event = NotificationService().acknowledge_event(event_id, acknowledged_by=current_user.user_id)
        return NotificationEventAckResponse(event=event)
    except Exception as exc:
        raise _service_error(exc) from exc
