# -*- coding: utf-8 -*-
"""Standalone homepage research priorities contract."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HOMEPAGE_RESEARCH_PRIORITIES_SCHEMA_VERSION = "homepage_research_priorities_v1"
HOMEPAGE_RESEARCH_PRIORITIES_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_RESEARCH_PRIORITIES_NO_ADVICE_DISCLOSURE = "仅供今日研究观察，不替代自主判断。"

HomepageResearchPriorityLevel = Literal["今日重点观察", "优先复核", "研究队列"]
HomepageResearchEvidenceStatus = Literal["证据增强", "证据不足", "适合继续观察", "需要确认"]
HomepageResearchQualityStatus = Literal["证据增强", "证据不足", "需要确认"]

_FORBIDDEN_TEXT_RE = re.compile(
    r"交易指令|交易执行|交易建议|买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|收益预测|"
    r"AI推荐|智能选股|券商|下单|委托|成交|"
    r"\b(?:buy|sell|add\s+position|reduce\s+position|clear\s+position|stop[\s-]?loss|"
    r"take[\s-]?profit|target[\s-]?price|broker|order|execution|recommendation)\b|"
    r"fallback|provider|diagnostic|debug|traceback|reasoncode|trustlevel|sourcetype|"
    r"raw|runtime|cache|token|secret|cookie|session|api[_-]?key|https?://|/users/",
    re.IGNORECASE,
)


def contains_forbidden_homepage_research_priorities_text(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and _FORBIDDEN_TEXT_RE.search(text))


def ensure_homepage_research_priorities_text(value: Any, *, field_name: str, max_length: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds max_length={max_length}")
    if contains_forbidden_homepage_research_priorities_text(text):
        raise ValueError(f"{field_name} contains forbidden advice, order, or internal content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        ensure_homepage_research_priorities_text(value, field_name=field_name, max_length=160)
        return
    if isinstance(value, BaseModel):
        _assert_safe_nested_text(value.model_dump(mode="json"), field_name=field_name)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "schemaVersion":
                continue
            _assert_safe_nested_text(item, field_name=f"{field_name}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_safe_nested_text(item, field_name=f"{field_name}[{index}]")


class _HomepageResearchPrioritiesBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageResearchPriority(_HomepageResearchPrioritiesBase):
    priorityLevel: HomepageResearchPriorityLevel
    theme: str
    whyNow: str
    evidenceStatus: HomepageResearchEvidenceStatus
    supportingSignals: list[str] = Field(min_length=1, max_length=4)
    missingConfirmation: list[str] = Field(min_length=1, max_length=4)
    relatedEvents: list[str] = Field(default_factory=list, max_length=4)
    relatedMacroDrivers: list[str] = Field(default_factory=list, max_length=4)
    reviewModule: str

    @field_validator("theme")
    @classmethod
    def _validate_theme(cls, value: str) -> str:
        text = ensure_homepage_research_priorities_text(value, field_name="theme", max_length=40)
        if not text.startswith("观察主题："):
            raise ValueError("theme must use observation-topic public wording")
        return text

    @field_validator("whyNow")
    @classmethod
    def _validate_why_now(cls, value: str) -> str:
        return ensure_homepage_research_priorities_text(value, field_name="whyNow", max_length=96)

    @field_validator("supportingSignals", "missingConfirmation", "relatedEvents", "relatedMacroDrivers")
    @classmethod
    def _validate_text_list(cls, values: list[str]) -> list[str]:
        return [
            ensure_homepage_research_priorities_text(item, field_name="researchPriority.listItem", max_length=48)
            for item in values
        ]

    @field_validator("reviewModule")
    @classmethod
    def _validate_review_module(cls, value: str) -> str:
        text = ensure_homepage_research_priorities_text(value, field_name="reviewModule", max_length=40)
        if not text.startswith("复核方向："):
            raise ValueError("reviewModule must use review-direction public wording")
        return text

    @model_validator(mode="after")
    def _validate_priority(self) -> "HomepageResearchPriority":
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


class HomepageResearchQuality(_HomepageResearchPrioritiesBase):
    status: HomepageResearchQualityStatus
    summary: str

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_research_priorities_text(value, field_name="quality.summary", max_length=80)


class HomepageResearchPrioritiesContract(_HomepageResearchPrioritiesBase):
    schemaVersion: str = Field(default=HOMEPAGE_RESEARCH_PRIORITIES_SCHEMA_VERSION)
    asOf: str = Field(..., min_length=1, max_length=40)
    researchPriorities: list[HomepageResearchPriority] = Field(min_length=1, max_length=6)
    evidenceQuality: HomepageResearchQuality
    dataQuality: HomepageResearchQuality
    noAdviceDisclosure: str

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        return ensure_homepage_research_priorities_text(value, field_name="asOf", max_length=40)

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_homepage_research_priorities_text(value, field_name="noAdviceDisclosure", max_length=48)

    @model_validator(mode="after")
    def _validate_contract(self) -> "HomepageResearchPrioritiesContract":
        if self.schemaVersion != HOMEPAGE_RESEARCH_PRIORITIES_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_RESEARCH_PRIORITIES_DEFAULT_AS_OF",
    "HOMEPAGE_RESEARCH_PRIORITIES_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_RESEARCH_PRIORITIES_SCHEMA_VERSION",
    "HomepageResearchEvidenceStatus",
    "HomepageResearchPrioritiesContract",
    "HomepageResearchPriority",
    "HomepageResearchPriorityLevel",
    "HomepageResearchQuality",
    "HomepageResearchQualityStatus",
    "contains_forbidden_homepage_research_priorities_text",
    "ensure_homepage_research_priorities_text",
]
