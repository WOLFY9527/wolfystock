# -*- coding: utf-8 -*-
"""Standalone after-close developments contract for the homepage intelligence cockpit."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HomepageAfterCloseQualityState = Literal["sample_proxy", "no_evidence", "unavailable"]
HomepageAfterCloseCategory = Literal[
    "overnight_context",
    "futures_tone",
    "earnings_catalyst",
    "macro_event",
    "geopolitical_event",
    "commodity_move",
    "rates_move",
]

HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_SCHEMA_VERSION = "homepage_after_close_developments_v1"
HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_NO_ADVICE_DISCLOSURE = (
    "仅用于收盘后市场背景观察与研究线索整理，不构成个性化建议。"
)

_FORBIDDEN_TEXT_RE = re.compile(
    r"交易指令|交易执行|交易建议|买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|"
    r"收益预测|AI推荐|智能选股|投资建议|下单|立即交易|"
    r"\b(?:buy|sell|broker|order|execution|trade[\s-]?execution|"
    r"trading[\s-]?advice|investment[\s-]?advice|financial[\s-]?advice|"
    r"target[\s-]?price|stop[\s-]?loss|take[\s-]?profit|guaranteed)\b|"
    r"provider|fallback|internal|diagnostic|debug|traceback|reasoncode|trustlevel|"
    r"sourcetype|raw|token|secret|cookie|session_id|api[_-]?key|https?://|/users/|/tmp/",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def contains_forbidden_after_close_developments_text(value: Any) -> bool:
    text = str(value or "")
    return bool(text and _FORBIDDEN_TEXT_RE.search(text))


def ensure_after_close_developments_text(
    value: Any,
    *,
    field_name: str,
    max_length: int,
) -> str:
    text = _WHITESPACE_RE.sub(" ", str(value or "").strip())
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds max_length={max_length}")
    if contains_forbidden_after_close_developments_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        ensure_after_close_developments_text(value, field_name=field_name, max_length=240)
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


class _HomepageAfterCloseDevelopmentsBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageAfterCloseQuality(_HomepageAfterCloseDevelopmentsBase):
    state: HomepageAfterCloseQualityState
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_after_close_developments_text(
            value,
            field_name="quality.label",
            max_length=56,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_after_close_developments_text(
            value,
            field_name="quality.summary",
            max_length=180,
        )


class HomepageAfterCloseLatestSession(_HomepageAfterCloseDevelopmentsBase):
    label: str
    regularCloseAt: str
    nextRegularOpenAt: str
    basis: HomepageAfterCloseQualityState
    summary: str

    @field_validator("label", "regularCloseAt", "nextRegularOpenAt")
    @classmethod
    def _validate_short_text(cls, value: str) -> str:
        return ensure_after_close_developments_text(
            value,
            field_name="latestSession.text",
            max_length=80,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_after_close_developments_text(
            value,
            field_name="latestSession.summary",
            max_length=180,
        )


class HomepageAfterCloseDevelopment(_HomepageAfterCloseDevelopmentsBase):
    key: str = Field(..., min_length=1, max_length=64)
    label: str
    category: HomepageAfterCloseCategory
    basis: HomepageAfterCloseQualityState
    evidenceState: HomepageAfterCloseQualityState
    observation: str
    researchContext: str
    relatedAssets: list[str] = Field(..., min_length=1, max_length=8)
    watchPoints: list[str] = Field(..., min_length=1, max_length=6)

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_after_close_developments_text(
            value,
            field_name="development.label",
            max_length=64,
        )

    @field_validator("observation", "researchContext")
    @classmethod
    def _validate_sentence(cls, value: str) -> str:
        return ensure_after_close_developments_text(
            value,
            field_name="development.text",
            max_length=180,
        )

    @field_validator("relatedAssets", "watchPoints")
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_after_close_developments_text(
                item,
                field_name="development.listItem",
                max_length=80,
            )
            for item in value
        ]


class HomepageAfterCloseSectionItem(_HomepageAfterCloseDevelopmentsBase):
    key: str = Field(..., min_length=1, max_length=64)
    label: str
    basis: HomepageAfterCloseQualityState
    evidenceState: HomepageAfterCloseQualityState
    observation: str
    researchContext: str
    watchPoints: list[str] = Field(..., min_length=1, max_length=5)

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_after_close_developments_text(
            value,
            field_name="sectionItem.label",
            max_length=64,
        )

    @field_validator("observation", "researchContext")
    @classmethod
    def _validate_sentence(cls, value: str) -> str:
        return ensure_after_close_developments_text(
            value,
            field_name="sectionItem.text",
            max_length=180,
        )

    @field_validator("watchPoints")
    @classmethod
    def _validate_watch_points(cls, value: list[str]) -> list[str]:
        return [
            ensure_after_close_developments_text(
                item,
                field_name="sectionItem.watchPoint",
                max_length=80,
            )
            for item in value
        ]


class HomepageAfterCloseSection(_HomepageAfterCloseDevelopmentsBase):
    state: HomepageAfterCloseQualityState
    summary: str
    items: list[HomepageAfterCloseSectionItem] = Field(..., min_length=1, max_length=8)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_after_close_developments_text(
            value,
            field_name="section.summary",
            max_length=180,
        )


class HomepageAfterCloseWatchPoint(_HomepageAfterCloseDevelopmentsBase):
    key: str = Field(..., min_length=1, max_length=64)
    label: str
    basis: HomepageAfterCloseQualityState
    evidenceState: HomepageAfterCloseQualityState
    observation: str
    researchContext: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_after_close_developments_text(
            value,
            field_name="watchPoint.label",
            max_length=64,
        )

    @field_validator("observation", "researchContext")
    @classmethod
    def _validate_sentence(cls, value: str) -> str:
        return ensure_after_close_developments_text(
            value,
            field_name="watchPoint.text",
            max_length=180,
        )


class HomepageAfterCloseDevelopmentsSnapshot(_HomepageAfterCloseDevelopmentsBase):
    schemaVersion: str = Field(default=HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_SCHEMA_VERSION)
    asOf: str = Field(
        default=HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_DEFAULT_AS_OF,
        min_length=1,
        max_length=40,
    )
    latestSession: HomepageAfterCloseLatestSession
    afterCloseDevelopments: list[HomepageAfterCloseDevelopment] = Field(
        ...,
        min_length=1,
        max_length=12,
    )
    overnightContext: HomepageAfterCloseSection
    futuresTone: HomepageAfterCloseSection
    earningsCatalysts: HomepageAfterCloseSection
    macroEvents: HomepageAfterCloseSection
    geopoliticalEvents: HomepageAfterCloseSection
    commodityMoves: HomepageAfterCloseSection
    ratesMoves: HomepageAfterCloseSection
    todayWatchPoints: list[HomepageAfterCloseWatchPoint] = Field(
        ...,
        min_length=1,
        max_length=10,
    )
    evidenceQuality: HomepageAfterCloseQuality
    dataQuality: HomepageAfterCloseQuality
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=100)

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        return ensure_after_close_developments_text(value, field_name="asOf", max_length=40)

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_after_close_developments_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=100,
        )

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepageAfterCloseDevelopmentsSnapshot":
        if self.schemaVersion != HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_DEFAULT_AS_OF",
    "HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_SCHEMA_VERSION",
    "HomepageAfterCloseCategory",
    "HomepageAfterCloseDevelopment",
    "HomepageAfterCloseDevelopmentsSnapshot",
    "HomepageAfterCloseLatestSession",
    "HomepageAfterCloseQuality",
    "HomepageAfterCloseQualityState",
    "HomepageAfterCloseSection",
    "HomepageAfterCloseSectionItem",
    "HomepageAfterCloseWatchPoint",
    "contains_forbidden_after_close_developments_text",
    "ensure_after_close_developments_text",
]
