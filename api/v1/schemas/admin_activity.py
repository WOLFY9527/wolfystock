# -*- coding: utf-8 -*-
"""Safe admin activity timeline schemas."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class _AdminActivityModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class AdminActivityActor(_AdminActivityModel):
    type: Literal["admin", "user", "guest", "anonymous", "system", "unknown"] = "unknown"
    user_id: Optional[str] = Field(default=None, alias="userId")
    label: Optional[str] = None
    role: Optional[str] = None
    session_id_hash: Optional[str] = Field(default=None, alias="sessionIdHash")
    request_id_hash: Optional[str] = Field(default=None, alias="requestIdHash")


class AdminActivityTargetUser(_AdminActivityModel):
    id: Optional[str] = None
    label: Optional[str] = None


class AdminActivityEntity(_AdminActivityModel):
    type: str
    id_hash: Optional[str] = Field(default=None, alias="idHash")
    label: Optional[str] = None
    symbol: Optional[str] = None
    market: Optional[str] = None
    source_table: Optional[str] = Field(default=None, alias="sourceTable")


class AdminActivitySource(_AdminActivityModel):
    kind: str
    table: Optional[str] = None
    confidence: Literal["confirmed", "inferred", "unknown"] = "unknown"


class AdminActivityLogLink(_AdminActivityModel):
    kind: str
    id_hash: Optional[str] = Field(default=None, alias="idHash")


class AdminActivityEvent(_AdminActivityModel):
    id: str
    timestamp: str
    actor: AdminActivityActor
    target_user: AdminActivityTargetUser = Field(alias="targetUser")
    family: str
    action: str
    entity: AdminActivityEntity
    status: Literal["success", "failed", "partial", "running", "skipped", "cancelled", "unknown"] = "unknown"
    outcome: Literal["ok", "warning", "failed", "timeout", "partial", "unknown"] = "unknown"
    request_id_hash: Optional[str] = Field(default=None, alias="requestIdHash")
    session_id_hash: Optional[str] = Field(default=None, alias="sessionIdHash")
    source: AdminActivitySource
    redacted_metadata: Dict[str, Any] = Field(default_factory=dict, alias="redactedMetadata")
    log_links: list[AdminActivityLogLink] = Field(default_factory=list, alias="logLinks")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=True)


class AdminActivityWindow(_AdminActivityModel):
    date_from: str = Field(alias="from")
    date_to: str = Field(alias="to")
    max_days: int = Field(alias="maxDays")


class AdminActivityResponse(_AdminActivityModel):
    items: list[AdminActivityEvent] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    has_more: bool = Field(default=False, alias="hasMore")
    window: AdminActivityWindow
    limitations: list[str] = Field(default_factory=list)
