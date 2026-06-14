# -*- coding: utf-8 -*-
"""Schemas for admin operational notification channels."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


NotificationChannelType = Literal["in_app", "webhook", "system_channel"]
NotificationSeverity = Literal["info", "warning", "critical"]
NotificationDeliveryMode = Literal["in_app", "webhook", "system_channel", "no_send", "unknown"]
NotificationSafeStatus = Literal["configured", "checked", "sent", "failed", "disabled", "unavailable", "unknown"]


class NotificationChannelBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    type: NotificationChannelType = "in_app"
    enabled: bool = True
    severity_min: NotificationSeverity = "warning"
    event_types: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)


class NotificationChannelCreateRequest(NotificationChannelBase):
    pass


class NotificationChannelUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    type: Optional[NotificationChannelType] = None
    enabled: Optional[bool] = None
    severity_min: Optional[NotificationSeverity] = None
    event_types: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None


class NotificationChannelModel(BaseModel):
    id: int
    name: str = ""
    enabled: bool = False
    configured: bool = False
    channel_type: NotificationChannelType = "in_app"
    delivery_mode: NotificationDeliveryMode = "unknown"
    last_checked_at: Optional[str] = None
    status: NotificationSafeStatus = "unknown"

    @classmethod
    def from_service_payload(cls, payload: Dict[str, Any]) -> "NotificationChannelModel":
        channel_type = _safe_channel_type(payload.get("channel_type") or payload.get("type"))
        enabled = bool(payload.get("enabled"))
        configured = _safe_configured(payload, channel_type=channel_type)
        return cls(
            id=int(payload.get("id") or 0),
            name=str(payload.get("name") or "")[:80],
            enabled=enabled,
            configured=configured,
            channel_type=channel_type,
            delivery_mode=_safe_delivery_mode(
                channel_type=channel_type,
                enabled=enabled,
                configured=configured,
            ),
            last_checked_at=payload.get("last_checked_at") or payload.get("last_tested_at"),
            status=_safe_status(payload, enabled=enabled, configured=configured),
        )


class NotificationChannelListResponse(BaseModel):
    items: List[NotificationChannelModel] = Field(default_factory=list)
    available_system_channels: List[str] = Field(default_factory=list)


class NotificationChannelTestResponse(BaseModel):
    success: bool
    dry_run: bool = False
    error: Optional[str] = None
    error_code: Optional[str] = None
    status: NotificationSafeStatus = "unknown"
    channel: NotificationChannelModel

    @classmethod
    def from_service_payload(cls, payload: Dict[str, Any]) -> "NotificationChannelTestResponse":
        channel = NotificationChannelModel.from_service_payload(payload.get("channel") or {})
        success = bool(payload.get("success"))
        return cls(
            success=success,
            dry_run=bool(payload.get("dry_run")),
            error=None if success else str(payload.get("error") or "Notification unavailable"),
            error_code=None if success else _safe_error_code(payload.get("error_code")),
            status="checked" if success and bool(payload.get("dry_run")) else ("sent" if success else "failed"),
            channel=channel,
        )


class NotificationEventModel(BaseModel):
    id: int
    event_type: str
    severity: NotificationSeverity
    title: str
    message: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    fingerprint: Optional[str] = None
    created_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    delivery_status: str
    deduped: bool = False


class NotificationEventListResponse(BaseModel):
    total: int = 0
    limit: int = 100
    offset: int = 0
    items: List[NotificationEventModel] = Field(default_factory=list)


class NotificationEventAckResponse(BaseModel):
    event: NotificationEventModel


def _safe_channel_type(value: Any) -> NotificationChannelType:
    channel_type = str(value or "").strip().lower()
    if channel_type in {"webhook", "system_channel"}:
        return channel_type  # type: ignore[return-value]
    return "in_app"


def _safe_configured(payload: Dict[str, Any], *, channel_type: NotificationChannelType) -> bool:
    if isinstance(payload.get("configured"), bool):
        return bool(payload["configured"])
    target_summary = str(payload.get("target_summary") or "").strip().lower()
    if target_summary.endswith(":unconfigured"):
        return False
    if target_summary.endswith(":configured"):
        return True
    config = payload.get("config")
    if isinstance(config, dict):
        if channel_type == "webhook":
            return bool(config.get("webhook_url"))
        if channel_type == "system_channel":
            return bool(config.get("channel"))
    return channel_type == "in_app"


def _safe_delivery_mode(
    *,
    channel_type: NotificationChannelType,
    enabled: bool,
    configured: bool,
) -> NotificationDeliveryMode:
    if not enabled or not configured:
        return "no_send"
    if channel_type in {"in_app", "webhook", "system_channel"}:
        return channel_type
    return "unknown"


def _safe_status(
    payload: Dict[str, Any],
    *,
    enabled: bool,
    configured: bool,
) -> NotificationSafeStatus:
    if not enabled:
        return "disabled"
    if not configured:
        return "unavailable"
    status = str(payload.get("status") or payload.get("last_status") or "").strip().lower()
    if status == "success":
        if payload.get("last_sent_at"):
            return "sent"
        return "checked"
    if status in {"failed", "disabled", "unavailable"}:
        return status  # type: ignore[return-value]
    if status in {"configured", "checked", "sent"}:
        return status  # type: ignore[return-value]
    return "configured"


def _safe_error_code(value: Any) -> Optional[str]:
    code = str(value or "").strip().lower()
    if code in {"ssl_certificate_verify_failed", "webhook_timeout", "webhook_delivery_failed"}:
        return code
    return "notification_unavailable" if code else None
