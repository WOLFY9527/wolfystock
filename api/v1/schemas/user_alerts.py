# -*- coding: utf-8 -*-
"""Owner-scoped in-app user alert schemas."""

from __future__ import annotations

import re
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.utils.symbol_normalization import canonical_stock_code


UserAlertRuleType = Literal["watchlist_price_threshold"]
UserAlertDirection = Literal["above", "below"]


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
