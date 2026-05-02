# -*- coding: utf-8 -*-
"""Admin-only operational notification channel APIs."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

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


def _request_language(request: Request) -> str:
    language = request.headers.get("accept-language", "").lower()
    if language.startswith("zh") or "zh-" in language:
        return "zh"
    return "en"


def _localize_delivery_error(
    *,
    error_code: Optional[str],
    error_message: str,
    diagnostics: Dict[str, Any],
    language: str,
) -> tuple[str, Dict[str, Any]]:
    if error_code == "ssl_certificate_verify_failed":
        if language == "zh":
            return (
                "Webhook SSL 证书校验失败。请检查证书链、受信任 CA 和主机名是否匹配。",
                {
                    **diagnostics,
                    "summary": "Webhook SSL 证书校验失败。",
                    "troubleshooting": [
                        "请确认 webhook 目标使用了受信任证书，而不是未受信任或自签名证书。",
                        "请检查证书链是否完整，并确认主机名与证书中的域名匹配。",
                        "如果前面有代理或网关，请确认它没有替换或截断 TLS 证书链。",
                    ],
                },
            )
        return (
            "Webhook SSL certificate verification failed. Check the certificate chain, trusted CA, and hostname.",
            {
                **diagnostics,
                "summary": "Webhook SSL certificate verification failed.",
                "troubleshooting": [
                    "Confirm the webhook endpoint uses a trusted certificate instead of a self-signed or expired one.",
                    "Check that the certificate chain is complete and the hostname matches the certificate.",
                    "If a proxy or gateway sits in front of the webhook, make sure it is not rewriting or truncating the TLS chain.",
                ],
            },
        )

    if error_code == "webhook_timeout":
        if language == "zh":
            return (
                "Webhook 投递超时。请检查目标服务、DNS、代理和上游延迟。",
                {
                    **diagnostics,
                    "summary": "Webhook 投递超时。",
                },
            )
        return (
            "Webhook delivery timed out. Check the target service, DNS, proxy, and upstream latency.",
            {
                **diagnostics,
                "summary": "Webhook delivery timed out.",
                },
            )

    if error_code == "webhook_delivery_failed":
        if language == "zh":
            return (
                "Webhook 投递失败。请检查目标服务、URL、认证凭据和网络连通性。",
                {
                    **diagnostics,
                    "summary": "Webhook 投递失败。",
                    "troubleshooting": [
                        "请确认 webhook URL 可访问，且没有被防火墙、代理或网关拦截。",
                        "请检查 token、签名或认证头是否与目标端要求一致。",
                        "如果目标服务返回了 HTTP 状态码，请根据原始诊断继续排查。",
                    ],
                },
            )
        return (
            "Webhook delivery failed. Check the target service, URL, credentials, and network connectivity.",
            {
                **diagnostics,
                "summary": "Webhook delivery failed.",
                "troubleshooting": [
                    "Confirm the webhook URL is reachable and not blocked by a firewall, proxy, or gateway.",
                    "Check that tokens, signatures, or auth headers match the target service requirements.",
                    "If the target returned an HTTP status code, use the raw diagnostic to continue troubleshooting.",
                ],
            },
        )

    return error_message, diagnostics


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
    service = NotificationService()
    return NotificationChannelListResponse(
        items=service.list_channels(),
        available_system_channels=service.list_system_channels(),
    )


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
    return {
        "success": True,
        "deleted_scope": "log_notification_association",
    }


@router.post(
    "/notification-channels/{channel_id}/test",
    response_model=NotificationChannelTestResponse,
    summary="Send a test notification through one channel",
)
def test_notification_channel(
    channel_id: int,
    request: Request,
    _: CurrentUser = Depends(require_admin_user),
):
    try:
        result = NotificationService().test_channel(channel_id)
        if not result.get("success"):
            error_code = result.get("error_code")
            diagnostics = result.get("diagnostics") or {}
            localized_error, localized_diagnostics = _localize_delivery_error(
                error_code=error_code,
                error_message=str(result.get("error") or ""),
                diagnostics=dict(diagnostics),
                language=_request_language(request),
            )
            result["error"] = localized_error
            result["diagnostics"] = localized_diagnostics
        return NotificationChannelTestResponse(**result)
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
