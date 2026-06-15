# -*- coding: utf-8 -*-
"""Standalone pre-session research checklist contract for the homepage cockpit."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PreSessionConfidenceState = Literal["high", "medium", "low", "needs_review"]
PreSessionEvidenceQualityState = Literal[
    "template_only",
    "needs_confirmation",
    "mixed",
    "limited",
]
PreSessionDataQualityState = Literal["static_contract", "partial", "unavailable"]

HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_SCHEMA_VERSION = (
    "homepage_pre_session_research_checklist_v1"
)
HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_NO_ADVICE_DISCLOSURE = (
    "For research review only; not a personalized decision basis."
)

_FORBIDDEN_TEXT_RE = re.compile(
    r"交易指令|交易执行|交易建议|买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|"
    r"收益预测|AI推荐|智能选股|投资建议|下单|立即交易|"
    r"\b(?:buy|sell|broker|order|trade[\s-]?execution|trading[\s-]?advice|"
    r"investment[\s-]?advice|financial[\s-]?advice|target[\s-]?price|"
    r"stop[\s-]?loss|take[\s-]?profit|place[\s-]?order|submit[\s-]?order)\b|"
    r"provider|fallback|internal|diagnostic|debug|traceback|reasoncode|trustlevel|"
    r"sourcetype|raw|token|secret|cookie|session_id|api[_-]?key|https?://|/users/|/tmp/",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def contains_forbidden_pre_session_research_checklist_text(value: Any) -> bool:
    text = str(value or "")
    return bool(text and _FORBIDDEN_TEXT_RE.search(text))


def ensure_pre_session_research_checklist_text(
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
    if contains_forbidden_pre_session_research_checklist_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        ensure_pre_session_research_checklist_text(
            value,
            field_name=field_name,
            max_length=260,
        )
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


class _HomepagePreSessionResearchChecklistBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepagePreSessionContext(_HomepagePreSessionResearchChecklistBase):
    label: str
    reviewWindow: str
    purpose: str

    @field_validator("label", "reviewWindow")
    @classmethod
    def _validate_short_text(cls, value: str) -> str:
        return ensure_pre_session_research_checklist_text(
            value,
            field_name="sessionContext.shortText",
            max_length=80,
        )

    @field_validator("purpose")
    @classmethod
    def _validate_purpose(cls, value: str) -> str:
        return ensure_pre_session_research_checklist_text(
            value,
            field_name="sessionContext.purpose",
            max_length=180,
        )


class HomepagePreSessionChecklistItem(_HomepagePreSessionResearchChecklistBase):
    id: str = Field(..., min_length=1, max_length=72)
    title: str
    reviewPrompt: str
    researchQuestion: str
    confirmationGates: list[str] = Field(..., min_length=1, max_length=5)
    evidenceNeeded: list[str] = Field(..., min_length=1, max_length=6)
    relatedSections: list[str] = Field(..., min_length=1, max_length=6)
    relatedAssets: list[str] = Field(..., min_length=1, max_length=8)
    relatedSectors: list[str] = Field(..., min_length=1, max_length=8)
    relatedThemes: list[str] = Field(..., min_length=1, max_length=8)
    reviewModule: str
    confidence: PreSessionConfidenceState
    evidenceQuality: PreSessionEvidenceQualityState
    dataQuality: PreSessionDataQualityState

    @field_validator("id", "title", "reviewModule")
    @classmethod
    def _validate_short_text(cls, value: str) -> str:
        return ensure_pre_session_research_checklist_text(
            value,
            field_name="checklistItem.shortText",
            max_length=96,
        )

    @field_validator("reviewPrompt", "researchQuestion")
    @classmethod
    def _validate_prompt_text(cls, value: str) -> str:
        return ensure_pre_session_research_checklist_text(
            value,
            field_name="checklistItem.promptText",
            max_length=180,
        )

    @field_validator(
        "confirmationGates",
        "evidenceNeeded",
        "relatedSections",
        "relatedAssets",
        "relatedSectors",
        "relatedThemes",
    )
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_pre_session_research_checklist_text(
                item,
                field_name="checklistItem.listItem",
                max_length=120,
            )
            for item in value
        ]


class HomepagePreSessionQuality(_HomepagePreSessionResearchChecklistBase):
    state: PreSessionEvidenceQualityState | PreSessionDataQualityState | PreSessionConfidenceState
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_pre_session_research_checklist_text(
            value,
            field_name="quality.label",
            max_length=64,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_pre_session_research_checklist_text(
            value,
            field_name="quality.summary",
            max_length=180,
        )


class HomepagePreSessionResearchChecklistSnapshot(_HomepagePreSessionResearchChecklistBase):
    schemaVersion: str = Field(default=HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_SCHEMA_VERSION)
    asOf: str = Field(
        default=HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_DEFAULT_AS_OF,
        min_length=1,
        max_length=40,
    )
    sessionContext: HomepagePreSessionContext
    checklistItems: list[HomepagePreSessionChecklistItem] = Field(..., min_length=1, max_length=10)
    researchQuestions: list[str] = Field(..., min_length=1, max_length=12)
    confirmationGates: list[str] = Field(..., min_length=1, max_length=24)
    evidenceNeeded: list[str] = Field(..., min_length=1, max_length=24)
    relatedSections: list[str] = Field(..., min_length=1, max_length=24)
    relatedAssets: list[str] = Field(..., min_length=1, max_length=24)
    relatedSectors: list[str] = Field(..., min_length=1, max_length=24)
    relatedThemes: list[str] = Field(..., min_length=1, max_length=24)
    reviewModules: list[str] = Field(..., min_length=1, max_length=12)
    confidence: HomepagePreSessionQuality
    evidenceQuality: HomepagePreSessionQuality
    dataQuality: HomepagePreSessionQuality
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=100)

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        return ensure_pre_session_research_checklist_text(value, field_name="asOf", max_length=40)

    @field_validator(
        "researchQuestions",
        "confirmationGates",
        "evidenceNeeded",
        "relatedSections",
        "relatedAssets",
        "relatedSectors",
        "relatedThemes",
        "reviewModules",
    )
    @classmethod
    def _validate_snapshot_lists(cls, value: list[str]) -> list[str]:
        return [
            ensure_pre_session_research_checklist_text(
                item,
                field_name="snapshot.listItem",
                max_length=140,
            )
            for item in value
        ]

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_pre_session_research_checklist_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=100,
        )

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepagePreSessionResearchChecklistSnapshot":
        if self.schemaVersion != HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_DEFAULT_AS_OF",
    "HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_SCHEMA_VERSION",
    "HomepagePreSessionChecklistItem",
    "HomepagePreSessionContext",
    "HomepagePreSessionQuality",
    "HomepagePreSessionResearchChecklistSnapshot",
    "PreSessionConfidenceState",
    "PreSessionDataQualityState",
    "PreSessionEvidenceQualityState",
    "contains_forbidden_pre_session_research_checklist_text",
    "ensure_pre_session_research_checklist_text",
]
