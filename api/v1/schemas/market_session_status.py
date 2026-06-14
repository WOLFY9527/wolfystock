# -*- coding: utf-8 -*-
"""Consumer-safe market session status contract for the homepage top bar."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MarketSessionStatus = Literal["ready", "unknown"]
MarketSessionMarket = Literal["US", "HK", "CN", "unknown"]
MarketSessionState = Literal["regular", "premarket", "after_hours", "closed", "holiday", "unknown"]
MarketSessionDataQuality = Literal["provided", "unknown"]

MARKET_SESSION_LABELS: dict[MarketSessionState, str] = {
    "regular": "正常交易",
    "premarket": "盘前",
    "after_hours": "盘后",
    "closed": "休市",
    "holiday": "非交易日",
    "unknown": "状态未知",
}
MARKET_SESSION_MESSAGES: dict[MarketSessionState, str] = {
    "regular": "市场处于常规交易时段，仅供状态展示",
    "premarket": "市场处于盘前时段，仅供状态展示",
    "after_hours": "市场处于盘后时段，仅供状态展示",
    "closed": "市场当前未处于交易时段，仅供状态展示",
    "holiday": "市场处于非交易日或节假日安排，仅供状态展示",
    "unknown": "当前缺少可靠交易时段信号，仅展示安全未知状态",
}
MARKET_SESSION_NO_ADVICE_DISCLOSURE = "仅供市场状态展示，不构成投资建议"
MARKET_SESSION_DEFAULT_TIMEZONE_BY_MARKET: dict[MarketSessionMarket, str] = {
    "US": "US/Eastern",
    "HK": "Asia/Hong_Kong",
    "CN": "Asia/Shanghai",
    "unknown": "UTC",
}
MARKET_SESSION_ALLOWED_TIMEZONES = frozenset(MARKET_SESSION_DEFAULT_TIMEZONE_BY_MARKET.values())

_FORBIDDEN_ADVICE_RE = re.compile(
    r"buy|sell|trade|order|target[-_\s]?price|stop[-_\s]?loss|take[-_\s]?profit|"
    r"买入|卖出|交易建议|投资建议|下单|止损|止盈|目标价",
    re.IGNORECASE,
)
_FORBIDDEN_LEAK_RE = re.compile(
    r"traceback|exception|reasoncode|trustlevel|sourcetype|provider|debug|rawpayload|"
    r"https?://|api[_-]?key|secret|cookie|session|token|/users/|/tmp/",
    re.IGNORECASE,
)


def _ensure_safe_text(value: Any, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if _FORBIDDEN_ADVICE_RE.search(text):
        raise ValueError(f"{field_name} contains forbidden trading advice text")
    if _FORBIDDEN_LEAK_RE.search(text):
        raise ValueError(f"{field_name} contains forbidden diagnostics or secret-like text")
    return text


def _ensure_no_leak_text(value: Any, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if _FORBIDDEN_LEAK_RE.search(text):
        raise ValueError(f"{field_name} contains forbidden diagnostics or secret-like text")
    return text


class MarketSessionStatusContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: MarketSessionStatus
    market: MarketSessionMarket
    sessionState: MarketSessionState
    label: str = Field(..., min_length=1, max_length=24)
    asOf: str | None = Field(default=None, max_length=64)
    timezone: str = Field(..., min_length=1, max_length=32)
    message: str = Field(..., min_length=1, max_length=80)
    dataQuality: MarketSessionDataQuality
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=40)

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        if value not in MARKET_SESSION_ALLOWED_TIMEZONES:
            raise ValueError("timezone must use an allowed canonical value")
        return value

    @model_validator(mode="after")
    def _validate_safe_copy(self) -> "MarketSessionStatusContract":
        self.label = _ensure_safe_text(self.label, field_name="label")
        self.message = _ensure_safe_text(self.message, field_name="message")
        self.noAdviceDisclosure = _ensure_no_leak_text(
            self.noAdviceDisclosure,
            field_name="noAdviceDisclosure",
        )
        if self.asOf is not None:
            self.asOf = _ensure_no_leak_text(self.asOf, field_name="asOf")
        return self
