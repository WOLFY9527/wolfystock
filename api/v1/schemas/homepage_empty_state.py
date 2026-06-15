# -*- coding: utf-8 -*-
"""Standalone homepage empty-state copy contract."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HomepageEmptyStateStatus = Literal["no_evidence", "unavailable", "partial", "ready"]
HomepageEmptyStateModuleKey = Literal[
    "market_pulse",
    "money_flow",
    "event_radar",
    "personal_summary",
    "research_queue",
    "public_data_quality",
    "source_freshness",
    "homepage_intelligence",
]

HOMEPAGE_EMPTY_STATE_DEFAULT_AS_OF = "2026-06-14T09:30:00Z"
HOMEPAGE_EMPTY_STATE_NO_ADVICE_DISCLOSURE = "仅供首页缺省状态说明，不提供个性化建议。"
HOMEPAGE_EMPTY_STATE_MODULE_KEYS: tuple[str, ...] = (
    "market_pulse",
    "money_flow",
    "event_radar",
    "personal_summary",
    "research_queue",
    "public_data_quality",
    "source_freshness",
    "homepage_intelligence",
)

_FORBIDDEN_TEXT_RE = re.compile(
    r"买入|卖出|下单|交易信号|交易指令|目标价|止损|止盈|投资建议|交易建议|"
    r"\b(?:buy|sell|order|target[\s-]?price|stop[\s-]?loss|take[\s-]?profit)\b|"
    r"fallback|provider|diagnostic|debug|traceback|reasoncode|trustlevel|sourcetype|"
    r"raw|token|secret|cookie|session|api[_-]?key|https?://|/users/|"
    r"live data|实时数据|real[\s-]?time|realtime",
    re.IGNORECASE,
)
_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


def contains_forbidden_homepage_empty_state_text(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and _FORBIDDEN_TEXT_RE.search(text))


def ensure_homepage_empty_state_text(value: Any, *, field_name: str, max_length: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds max_length={max_length}")
    if contains_forbidden_homepage_empty_state_text(text):
        raise ValueError(f"{field_name} contains forbidden advice, live-data, or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        ensure_homepage_empty_state_text(value, field_name=field_name, max_length=120)
        return
    if isinstance(value, BaseModel):
        _assert_safe_nested_text(value.model_dump(mode="json"), field_name=field_name)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_safe_nested_text(item, field_name=f"{field_name}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_safe_nested_text(item, field_name=f"{field_name}[{index}]")


class _HomepageEmptyStateBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageEmptyStateDataQuality(_HomepageEmptyStateBase):
    state: HomepageEmptyStateStatus
    label: str
    available: bool
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_empty_state_text(value, field_name="dataQuality.label", max_length=24)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_empty_state_text(value, field_name="dataQuality.summary", max_length=72)


class HomepageEmptyStateCopy(_HomepageEmptyStateBase):
    moduleKey: HomepageEmptyStateModuleKey
    title: str
    message: str
    reviewPoint: str
    state: HomepageEmptyStateStatus

    @field_validator("moduleKey")
    @classmethod
    def _validate_module_key(cls, value: str) -> str:
        if value not in HOMEPAGE_EMPTY_STATE_MODULE_KEYS or not _IDENTIFIER_RE.match(value):
            raise ValueError("moduleKey is not an allowed homepage empty-state module")
        return value

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        return ensure_homepage_empty_state_text(value, field_name="title", max_length=24)

    @field_validator("message")
    @classmethod
    def _validate_message(cls, value: str) -> str:
        return ensure_homepage_empty_state_text(value, field_name="message", max_length=72)

    @field_validator("reviewPoint")
    @classmethod
    def _validate_review_point(cls, value: str) -> str:
        return ensure_homepage_empty_state_text(value, field_name="reviewPoint", max_length=48)


class HomepageEmptyStateContract(_HomepageEmptyStateBase):
    status: HomepageEmptyStateStatus
    asOf: str = Field(..., min_length=1, max_length=40)
    emptyStates: list[HomepageEmptyStateCopy]
    noAdviceDisclosure: str
    dataQuality: HomepageEmptyStateDataQuality

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_homepage_empty_state_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=48,
        )

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("asOf must not be empty")
        if len(text) > 40 or contains_forbidden_homepage_empty_state_text(text):
            raise ValueError("asOf contains forbidden content")
        return text

    @model_validator(mode="after")
    def _validate_contract(self) -> "HomepageEmptyStateContract":
        keys = [item.moduleKey for item in self.emptyStates]
        if keys != list(HOMEPAGE_EMPTY_STATE_MODULE_KEYS):
            raise ValueError("emptyStates must include the expected homepage modules in stable order")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_EMPTY_STATE_DEFAULT_AS_OF",
    "HOMEPAGE_EMPTY_STATE_MODULE_KEYS",
    "HOMEPAGE_EMPTY_STATE_NO_ADVICE_DISCLOSURE",
    "HomepageEmptyStateContract",
    "HomepageEmptyStateCopy",
    "HomepageEmptyStateDataQuality",
    "HomepageEmptyStateModuleKey",
    "HomepageEmptyStateStatus",
    "contains_forbidden_homepage_empty_state_text",
    "ensure_homepage_empty_state_text",
]
