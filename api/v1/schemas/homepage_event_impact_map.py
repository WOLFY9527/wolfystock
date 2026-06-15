# -*- coding: utf-8 -*-
"""Standalone event impact map contract for the homepage intelligence cockpit."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HomepageEventImpactConfidence = Literal["medium", "needs_confirmation", "scenario"]
HomepageEventImpactEvidenceQuality = Literal["placeholder", "needs_confirmation", "scenario"]
HomepageEventImpactDataQualityStatus = Literal[
    "placeholder",
    "needs_confirmation",
    "scenario",
    "unavailable",
]

HOMEPAGE_EVENT_IMPACT_MAP_SCHEMA_VERSION = "homepage_event_impact_map_v1"
HOMEPAGE_EVENT_IMPACT_MAP_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_EVENT_IMPACT_MAP_NO_ADVICE_DISCLOSURE = (
    "仅用于事件影响观察、证据整理与研究支持，不作为个性化决策依据。"
)

_FORBIDDEN_TEXT_RE = re.compile(
    r"交易指令|交易执行|交易建议|买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|"
    r"收益预测|AI推荐|智能选股|"
    r"\b(?:broker|order|execution|buy now|sell now|place order|submit order|"
    r"trading advice|investment advice|financial advice|target price|stop loss|take profit|"
    r"guaranteed|position sizing)\b|"
    r"provider|internal|diagnostic|debug|traceback|fallback|reasoncode|trustlevel|"
    r"sourcetype|raw|token|secret|cookie|session_id|api[_-]?key|https?://|/users/|/tmp/",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def contains_forbidden_event_impact_map_text(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and _FORBIDDEN_TEXT_RE.search(text))


def ensure_event_impact_map_text(value: Any, *, field_name: str, max_length: int) -> str:
    text = _WHITESPACE_RE.sub(" ", str(value or "").strip())
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds max_length={max_length}")
    if contains_forbidden_event_impact_map_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        ensure_event_impact_map_text(value, field_name=field_name, max_length=220)
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


class _HomepageEventImpactMapBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageEventImpactWindow(_HomepageEventImpactMapBase):
    label: str
    startsAt: str
    endsAt: str
    basis: str

    @field_validator("label", "startsAt", "endsAt", "basis")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return ensure_event_impact_map_text(value, field_name="eventWindow", max_length=96)


class HomepageEventImpactDataQuality(_HomepageEventImpactMapBase):
    status: HomepageEventImpactDataQualityStatus
    label: str
    available: bool
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_event_impact_map_text(value, field_name="dataQuality.label", max_length=48)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_event_impact_map_text(value, field_name="dataQuality.summary", max_length=160)


class HomepageEventImpactEvent(_HomepageEventImpactMapBase):
    key: str = Field(..., min_length=1, max_length=64)
    label: str
    observation: str
    affectedAssets: list[str] = Field(..., min_length=1, max_length=8)
    affectedSectors: list[str] = Field(..., min_length=1, max_length=8)
    affectedThemes: list[str] = Field(..., min_length=1, max_length=8)
    implication: str
    confidence: HomepageEventImpactConfidence
    evidenceQuality: HomepageEventImpactEvidenceQuality
    monitorNext: list[str] = Field(..., min_length=1, max_length=5)
    relatedMacroVariables: list[str] = Field(default_factory=list, max_length=6)
    relatedResearchAreas: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_event_impact_map_text(value, field_name="event.label", max_length=56)

    @field_validator("observation", "implication")
    @classmethod
    def _validate_sentence(cls, value: str) -> str:
        return ensure_event_impact_map_text(value, field_name="event.text", max_length=160)

    @field_validator(
        "affectedAssets",
        "affectedSectors",
        "affectedThemes",
        "monitorNext",
        "relatedMacroVariables",
        "relatedResearchAreas",
    )
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_event_impact_map_text(item, field_name="event.list", max_length=72)
            for item in value
        ]


class HomepageEventImpactMapResponse(_HomepageEventImpactMapBase):
    schemaVersion: str = Field(default=HOMEPAGE_EVENT_IMPACT_MAP_SCHEMA_VERSION)
    asOf: str = Field(default=HOMEPAGE_EVENT_IMPACT_MAP_DEFAULT_AS_OF, min_length=1, max_length=40)
    eventWindow: HomepageEventImpactWindow
    events: list[HomepageEventImpactEvent] = Field(..., min_length=1, max_length=12)
    affectedAssets: list[str] = Field(..., min_length=1, max_length=16)
    affectedSectors: list[str] = Field(..., min_length=1, max_length=16)
    affectedThemes: list[str] = Field(..., min_length=1, max_length=16)
    implication: str
    confidence: HomepageEventImpactConfidence
    evidenceQuality: HomepageEventImpactEvidenceQuality
    monitorNext: list[str] = Field(..., min_length=1, max_length=8)
    relatedMacroVariables: list[str] = Field(..., min_length=1, max_length=12)
    relatedResearchAreas: list[str] = Field(..., min_length=1, max_length=12)
    dataQuality: HomepageEventImpactDataQuality
    noAdviceDisclosure: str

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        return ensure_event_impact_map_text(value, field_name="asOf", max_length=40)

    @field_validator("implication")
    @classmethod
    def _validate_implication(cls, value: str) -> str:
        return ensure_event_impact_map_text(value, field_name="implication", max_length=180)

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_event_impact_map_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=100,
        )

    @field_validator(
        "affectedAssets",
        "affectedSectors",
        "affectedThemes",
        "monitorNext",
        "relatedMacroVariables",
        "relatedResearchAreas",
    )
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_event_impact_map_text(item, field_name="eventImpactMap.list", max_length=72)
            for item in value
        ]

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepageEventImpactMapResponse":
        if self.schemaVersion != HOMEPAGE_EVENT_IMPACT_MAP_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_EVENT_IMPACT_MAP_DEFAULT_AS_OF",
    "HOMEPAGE_EVENT_IMPACT_MAP_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_EVENT_IMPACT_MAP_SCHEMA_VERSION",
    "HomepageEventImpactConfidence",
    "HomepageEventImpactDataQuality",
    "HomepageEventImpactDataQualityStatus",
    "HomepageEventImpactEvent",
    "HomepageEventImpactEvidenceQuality",
    "HomepageEventImpactMapResponse",
    "HomepageEventImpactWindow",
    "contains_forbidden_event_impact_map_text",
    "ensure_event_impact_map_text",
]
