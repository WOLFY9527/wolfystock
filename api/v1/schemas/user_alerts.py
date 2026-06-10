# -*- coding: utf-8 -*-
"""Owner-scoped in-app user alert schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.utils.symbol_normalization import canonical_stock_code


UserAlertRuleType = Literal["watchlist_price_threshold"]
UserAlertDirection = Literal["above", "below"]
UserAlertDryRunFreshnessStatus = Literal[
    "fresh",
    "live",
    "cached",
    "delayed",
    "stale",
    "partial",
    "fallback",
    "synthetic",
    "unavailable",
    "unknown",
]


class _UserAlertSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class UserAlertRuleCreateRequest(_UserAlertSchema):
    symbol: str = Field(..., min_length=1, max_length=16)
    direction: UserAlertDirection
    threshold_price: float = Field(..., gt=0, alias="thresholdPrice")
    enabled: bool = True
    note: Optional[str] = Field(None, max_length=500)

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        normalized = canonical_stock_code(value).strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        if len(normalized) > 16:
            raise ValueError("symbol must be at most 16 characters")
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]*", normalized):
            raise ValueError("symbol contains invalid characters")
        return normalized

    @field_validator("note")
    @classmethod
    def _normalize_note(cls, value: Optional[str]) -> Optional[str]:
        normalized = str(value or "").strip()
        return normalized or None


class UserAlertRuleUpdateRequest(_UserAlertSchema):
    symbol: Optional[str] = Field(None, min_length=1, max_length=16)
    direction: Optional[UserAlertDirection] = None
    threshold_price: Optional[float] = Field(None, gt=0, alias="thresholdPrice")
    enabled: Optional[bool] = None
    note: Optional[str] = Field(None, max_length=500)

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = canonical_stock_code(value).strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        if len(normalized) > 16:
            raise ValueError("symbol must be at most 16 characters")
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]*", normalized):
            raise ValueError("symbol contains invalid characters")
        return normalized

    @field_validator("note")
    @classmethod
    def _normalize_note(cls, value: Optional[str]) -> Optional[str]:
        normalized = str(value or "").strip()
        return normalized or None


class UserAlertRuleModel(_UserAlertSchema):
    id: int
    contract_version: str = Field("user_alert_contract_v1", alias="contractVersion")
    rule_type: UserAlertRuleType = Field("watchlist_price_threshold", alias="ruleType")
    symbol: str
    direction: UserAlertDirection
    threshold_price: float = Field(..., alias="thresholdPrice")
    enabled: bool
    note: Optional[str] = None
    delivery_mode: Literal["in_app"] = Field("in_app", alias="deliveryMode")
    in_app_only: bool = Field(True, alias="inAppOnly")
    owner_scoped: bool = Field(True, alias="ownerScoped")
    created_at: Optional[str] = Field(None, alias="createdAt")
    updated_at: Optional[str] = Field(None, alias="updatedAt")


class UserAlertRuleListResponse(_UserAlertSchema):
    contract_version: str = Field("user_alert_contract_v1", alias="contractVersion")
    delivery_mode: Literal["in_app"] = Field("in_app", alias="deliveryMode")
    in_app_only: bool = Field(True, alias="inAppOnly")
    owner_scoped: bool = Field(True, alias="ownerScoped")
    items: List[UserAlertRuleModel] = Field(default_factory=list)


class UserAlertRuleDeleteResponse(BaseModel):
    deleted: int


class UserAlertEventModel(_UserAlertSchema):
    id: int
    contract_version: str = Field("user_alert_contract_v1", alias="contractVersion")
    event_type: str = Field(..., alias="eventType")
    rule_id: Optional[int] = Field(None, alias="ruleId")
    symbol: Optional[str] = None
    direction: Optional[UserAlertDirection] = None
    threshold_price: Optional[float] = Field(None, alias="thresholdPrice")
    title: str
    message: str = ""
    delivery_mode: Literal["in_app"] = Field("in_app", alias="deliveryMode")
    in_app_only: bool = Field(True, alias="inAppOnly")
    owner_scoped: bool = Field(True, alias="ownerScoped")
    read_at: Optional[str] = Field(None, alias="readAt")
    created_at: Optional[str] = Field(None, alias="createdAt")


class UserAlertEventListResponse(_UserAlertSchema):
    contract_version: str = Field("user_alert_contract_v1", alias="contractVersion")
    delivery_mode: Literal["in_app"] = Field("in_app", alias="deliveryMode")
    in_app_only: bool = Field(True, alias="inAppOnly")
    owner_scoped: bool = Field(True, alias="ownerScoped")
    total: int = 0
    limit: int = 100
    offset: int = 0
    items: List[UserAlertEventModel] = Field(default_factory=list)


class UserAlertDryRunFreshnessInput(_UserAlertSchema):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    status: UserAlertDryRunFreshnessStatus
    max_age_minutes: Optional[int] = Field(None, ge=1, alias="maxAgeMinutes")


class UserAlertDryRunSuppressionContext(_UserAlertSchema):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    muted: bool = False
    snoozed_until: Optional[datetime] = Field(None, alias="snoozedUntil")
    cooldown_started_at: Optional[datetime] = Field(None, alias="cooldownStartedAt")
    cooldown_seconds: Optional[int] = Field(None, ge=1, alias="cooldownSeconds")
    previous_fingerprint: Optional[str] = Field(None, min_length=1, max_length=256, alias="previousFingerprint")
    previous_time_bucket: Optional[str] = Field(None, min_length=1, max_length=32, alias="previousTimeBucket")

    @model_validator(mode="after")
    def _validate_policy_pairs(self):
        cooldown_values = (self.cooldown_started_at, self.cooldown_seconds)
        if any(value is not None for value in cooldown_values) and not all(
            value is not None for value in cooldown_values
        ):
            raise ValueError("cooldownStartedAt and cooldownSeconds must be provided together")
        duplicate_values = (self.previous_fingerprint, self.previous_time_bucket)
        if any(value is not None for value in duplicate_values) and not all(
            value is not None for value in duplicate_values
        ):
            raise ValueError("previousFingerprint and previousTimeBucket must be provided together")
        return self


class UserAlertDryRunRequest(_UserAlertSchema):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    observed_price: Decimal = Field(..., gt=0, alias="observedPrice")
    observed_at: datetime = Field(..., alias="observedAt")
    freshness: UserAlertDryRunFreshnessInput
    suppression: Optional[UserAlertDryRunSuppressionContext] = None


class UserAlertDryRunResponse(_UserAlertSchema):
    dry_run: Literal[True] = Field(True, alias="dryRun")
    no_send: Literal[True] = Field(True, alias="noSend")
    outbound_attempted: Literal[False] = Field(False, alias="outboundAttempted")
    live_outbound: Literal[False] = Field(False, alias="liveOutbound")
    local_only: Literal[True] = Field(True, alias="localOnly")
    suppressed_local_record: bool = Field(False, alias="suppressedLocalRecord")
    evaluation: Dict[str, Any]
    suppression: Dict[str, Any]
    event_packet: Optional[Dict[str, Any]] = Field(None, alias="eventPacket")
