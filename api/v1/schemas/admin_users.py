# -*- coding: utf-8 -*-
"""Safe admin user directory schemas."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class _AdminModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class AdminSessionSummaryCounts(_AdminModel):
    active_count: int = Field(default=0, alias="activeCount")
    expired_count: int = Field(default=0, alias="expiredCount")
    revoked_count: int = Field(default=0, alias="revokedCount")
    last_seen_at: Optional[str] = Field(default=None, alias="lastSeenAt")
    next_expires_at: Optional[str] = Field(default=None, alias="nextExpiresAt")


class AdminSessionSummary(_AdminModel):
    session_handle: str = Field(alias="sessionHandle")
    status: Literal["active", "expired", "revoked"]
    created_at: Optional[str] = Field(default=None, alias="createdAt")
    last_seen_at: Optional[str] = Field(default=None, alias="lastSeenAt")
    expires_at: Optional[str] = Field(default=None, alias="expiresAt")
    revoked_at: Optional[str] = Field(default=None, alias="revokedAt")


class AdminUserRiskBadge(_AdminModel):
    code: str
    label: str
    severity: Literal["info", "warning", "critical"] = "info"
    reason: Optional[str] = None
    source: Literal["auth", "session", "future_activity", "future_security"] = "auth"


class AdminDataLinks(_AdminModel):
    self: Optional[str] = None
    admin_logs: Optional[str] = Field(default=None, alias="adminLogs")
    activity: Optional[str] = None
    portfolio: Optional[str] = None
    analysis: Optional[str] = None
    scanner: Optional[str] = None
    backtest: Optional[str] = None


class AdminUserListItem(_AdminModel):
    id: str
    username: str
    display_name: Optional[str] = Field(default=None, alias="displayName")
    role: str
    is_active: bool = Field(alias="isActive")
    created_at: Optional[str] = Field(default=None, alias="createdAt")
    updated_at: Optional[str] = Field(default=None, alias="updatedAt")
    password_state: Literal["set", "unset", "unknown"] = Field(alias="passwordState")
    last_seen_at: Optional[str] = Field(default=None, alias="lastSeenAt")
    session_summary: AdminSessionSummaryCounts = Field(alias="sessionSummary")
    risk_badges: list[AdminUserRiskBadge] = Field(default_factory=list, alias="riskBadges")
    links: AdminDataLinks


class AdminUserListResponse(_AdminModel):
    items: list[AdminUserListItem] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    has_more: bool = Field(default=False, alias="hasMore")


class AdminUserDetailResponse(_AdminModel):
    user: AdminUserListItem
    sessions: list[AdminSessionSummary] = Field(default_factory=list)
    data_links: AdminDataLinks = Field(alias="dataLinks")
    limitations: list[str] = Field(default_factory=list)
