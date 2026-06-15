# -*- coding: utf-8 -*-
"""Standalone public evidence-quality contract for the homepage cockpit."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HomepageEvidenceQualityState = Literal[
    "strong",
    "medium",
    "weak",
    "needs_confirmation",
    "conflicting",
    "unavailable",
]
HomepageEvidenceDataState = Literal[
    "ready",
    "partial",
    "delayed",
    "cached",
    "no_evidence",
    "unavailable",
]
HomepageEvidenceSectionKey = Literal[
    "market_structure",
    "breadth_confirmation",
    "news_catalyst",
    "cross_asset_context",
    "flow_confirmation",
]

HOMEPAGE_EVIDENCE_QUALITY_SCHEMA_VERSION = "homepage_evidence_quality_v1"
HOMEPAGE_EVIDENCE_QUALITY_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_EVIDENCE_QUALITY_NO_ADVICE_DISCLOSURE = (
    "本合约仅说明首页结论的公开证据支持强度，不构成个性化建议。"
)

_FORBIDDEN_TEXT_RE = re.compile(
    r"交易指令|交易执行|交易建议|买入|卖出|加仓|减仓|清仓|止损|止盈|"
    r"目标价|收益预测|AI推荐|智能选股|"
    r"\b(?:buy|sell|add|reduce|broker|order|execution|target[\s-]?price|"
    r"stop[\s-]?loss|take[\s-]?profit|trade recommendation|trading advice|"
    r"investment advice|financial advice|guaranteed)\b|"
    r"fallback|trustlevel|sourcetype|sourcetier|sourceauthority|scorecontribution|"
    r"reasoncode|reason_code|reasonfamilies|debugref|diagnostic|provider|raw|"
    r"traceback|stack trace|exception|routeRejected|cache_key|synthetic_|bearer|sk-|"
    r"token|secret|cookie|session|api[_-]?key|https?://|/users/|/tmp/|/api/v",
    re.IGNORECASE,
)
_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{1,48}$")
_WHITESPACE_RE = re.compile(r"\s+")


def contains_forbidden_homepage_evidence_quality_text(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and _FORBIDDEN_TEXT_RE.search(text))


def ensure_homepage_evidence_quality_text(value: Any, *, field_name: str, max_length: int) -> str:
    text = _WHITESPACE_RE.sub(" ", str(value or "").strip())
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds max_length={max_length}")
    if contains_forbidden_homepage_evidence_quality_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostic content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        ensure_homepage_evidence_quality_text(value, field_name=field_name, max_length=220)
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


class _HomepageEvidenceQualityBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageEvidenceQualityLabel(_HomepageEvidenceQualityBase):
    state: HomepageEvidenceQualityState
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_evidence_quality_text(
            value,
            field_name="evidenceQuality.label",
            max_length=32,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_evidence_quality_text(
            value,
            field_name="evidenceQuality.summary",
            max_length=140,
        )


class HomepageEvidenceDataFreshness(_HomepageEvidenceQualityBase):
    state: HomepageEvidenceDataState
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_evidence_quality_text(
            value,
            field_name="dataFreshness.label",
            max_length=32,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_evidence_quality_text(
            value,
            field_name="dataFreshness.summary",
            max_length=140,
        )


class HomepageEvidenceDataQuality(_HomepageEvidenceQualityBase):
    state: HomepageEvidenceDataState
    label: str
    available: bool
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_evidence_quality_text(
            value,
            field_name="dataQuality.label",
            max_length=32,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_evidence_quality_text(
            value,
            field_name="dataQuality.summary",
            max_length=140,
        )


class HomepageEvidenceQualitySection(_HomepageEvidenceQualityBase):
    sectionKey: HomepageEvidenceSectionKey
    sectionLabel: str
    conclusionAllowed: bool
    evidenceQuality: HomepageEvidenceQualityLabel
    evidenceSummary: str
    supportingEvidence: list[str] = Field(default_factory=list, max_length=5)
    missingEvidence: list[str] = Field(default_factory=list, max_length=5)
    conflictingEvidence: list[str] = Field(default_factory=list, max_length=5)
    dataFreshness: HomepageEvidenceDataFreshness
    publicConfidenceLabel: str

    @field_validator("sectionKey")
    @classmethod
    def _validate_section_key(cls, value: str) -> str:
        if not _IDENTIFIER_RE.match(value):
            raise ValueError("sectionKey must be a stable public identifier")
        return value

    @field_validator("sectionLabel")
    @classmethod
    def _validate_section_label(cls, value: str) -> str:
        return ensure_homepage_evidence_quality_text(
            value,
            field_name="sectionLabel",
            max_length=32,
        )

    @field_validator("evidenceSummary")
    @classmethod
    def _validate_evidence_summary(cls, value: str) -> str:
        return ensure_homepage_evidence_quality_text(
            value,
            field_name="evidenceSummary",
            max_length=160,
        )

    @field_validator("publicConfidenceLabel")
    @classmethod
    def _validate_public_confidence_label(cls, value: str) -> str:
        return ensure_homepage_evidence_quality_text(
            value,
            field_name="publicConfidenceLabel",
            max_length=32,
        )

    @field_validator("supportingEvidence", "missingEvidence", "conflictingEvidence")
    @classmethod
    def _validate_evidence_lists(cls, value: list[str]) -> list[str]:
        return [
            ensure_homepage_evidence_quality_text(
                item,
                field_name="evidenceList.item",
                max_length=96,
            )
            for item in value
        ]


class HomepageEvidenceQualityProjection(_HomepageEvidenceQualityBase):
    schemaVersion: Literal["homepage_evidence_quality_v1"] = HOMEPAGE_EVIDENCE_QUALITY_SCHEMA_VERSION
    asOf: str = Field(default=HOMEPAGE_EVIDENCE_QUALITY_DEFAULT_AS_OF, min_length=1, max_length=40)
    sections: list[HomepageEvidenceQualitySection] = Field(..., min_length=1, max_length=8)
    dataQuality: HomepageEvidenceDataQuality
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=80)

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        return ensure_homepage_evidence_quality_text(value, field_name="asOf", max_length=40)

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_homepage_evidence_quality_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=80,
        )

    @model_validator(mode="after")
    def _validate_public_projection(self) -> "HomepageEvidenceQualityProjection":
        keys = [section.sectionKey for section in self.sections]
        if len(keys) != len(set(keys)):
            raise ValueError("sections must use unique sectionKey values")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_EVIDENCE_QUALITY_DEFAULT_AS_OF",
    "HOMEPAGE_EVIDENCE_QUALITY_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_EVIDENCE_QUALITY_SCHEMA_VERSION",
    "HomepageEvidenceDataFreshness",
    "HomepageEvidenceDataQuality",
    "HomepageEvidenceDataState",
    "HomepageEvidenceQualityLabel",
    "HomepageEvidenceQualityProjection",
    "HomepageEvidenceQualitySection",
    "HomepageEvidenceQualityState",
    "HomepageEvidenceSectionKey",
    "contains_forbidden_homepage_evidence_quality_text",
    "ensure_homepage_evidence_quality_text",
]
