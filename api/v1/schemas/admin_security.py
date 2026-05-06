# -*- coding: utf-8 -*-
"""Safe admin account security action schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _AdminSecurityModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class AdminSecurityActionRequest(_AdminSecurityModel):
    reason: str = Field(min_length=1, max_length=500)
    confirm: str = Field(min_length=1, max_length=64)
    revoke_sessions: bool = Field(default=False, alias="revokeSessions")
    scope: str = Field(default="all", max_length=32)


class AdminSecurityActionResponse(_AdminSecurityModel):
    target_user_id: str = Field(alias="targetUserId")
    action: Literal["disable", "enable", "revoke_sessions"]
    status: Literal["completed", "blocked", "failed"]
    changed: bool
    sessions_revoked: int = Field(default=0, alias="sessionsRevoked")
    audit_event_id: str | None = Field(default=None, alias="auditEventId")
    message: str
