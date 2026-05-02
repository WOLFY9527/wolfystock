# -*- coding: utf-8 -*-
"""Schemas for admin operational notification channels."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


NotificationChannelType = Literal["in_app", "webhook"]
NotificationSeverity = Literal["info", "warning", "critical"]


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


class NotificationChannelModel(NotificationChannelBase):
    id: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_tested_at: Optional[str] = None
    last_sent_at: Optional[str] = None
    last_error: Optional[str] = None


class NotificationChannelListResponse(BaseModel):
    items: List[NotificationChannelModel] = Field(default_factory=list)


class NotificationChannelTestResponse(BaseModel):
    success: bool
    error: Optional[str] = None
    channel: NotificationChannelModel


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
