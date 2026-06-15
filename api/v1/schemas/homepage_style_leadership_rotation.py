# -*- coding: utf-8 -*-
"""Standalone Style Leadership Rotation contract for the homepage intelligence cockpit."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HomepageStyleGroup = Literal[
    "growth",
    "value",
    "quality",
    "momentum",
    "defensive",
    "cyclicals",
    "large_cap",
    "small_cap",
]
HomepageStyleRotationState = Literal[
    "confirmed",
    "proxy",
    "conflicting",
    "no_evidence",
    "unavailable",
]
HomepageStyleRotationTrend = Literal[
    "leading",
    "lagging",
    "mixed",
    "watch",
    "unavailable",
]
HomepageStyleRotationDataQualityState = Literal[
    "deterministic",
    "static_sample",
    "partial",
    "unavailable",
]

HOMEPAGE_STYLE_LEADERSHIP_ROTATION_SCHEMA_VERSION = "homepage_style_leadership_rotation_v1"
HOMEPAGE_STYLE_LEADERSHIP_ROTATION_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_STYLE_LEADERSHIP_ROTATION_NO_ADVICE_DISCLOSURE = (
    "仅用于首页风格轮动观察与研究线索整理，不作为个性化决策依据。"
)
HOMEPAGE_STYLE_GROUPS: tuple[HomepageStyleGroup, ...] = (
    "growth",
    "value",
    "quality",
    "momentum",
    "defensive",
    "cyclicals",
    "large_cap",
    "small_cap",
)

_FORBIDDEN_STYLE_ROTATION_RE = re.compile(
    r"交易指令|交易执行|交易建议|买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|"
    r"收益预测|AI推荐|智能选股|投资建议|下单|立即交易|"
    r"\b(?:buy|sell|add position|reduce position|clear position|broker|order|"
    r"trade execution|trading advice|investment advice|financial advice|"
    r"target[\s-]?price|stop[\s-]?loss|take[\s-]?profit|place[\s-]?order|"
    r"submit[\s-]?order|guaranteed return|live\s+(?:quote|data|market)|"
    r"real[\s-]?time|realtime)\b|"
    r"provider|fallback|internal|diagnostic|debug|traceback|reasoncode|trustlevel|"
    r"sourcetype|raw|token|secret|cookie|session|api[_-]?key|https?://|/users/|/tmp/",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def contains_forbidden_homepage_style_rotation_text(value: Any) -> bool:
    text = str(value or "")
    return bool(text and _FORBIDDEN_STYLE_ROTATION_RE.search(text))


def ensure_homepage_style_rotation_text(
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
    if contains_forbidden_homepage_style_rotation_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        ensure_homepage_style_rotation_text(value, field_name=field_name, max_length=260)
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


class _HomepageStyleRotationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageStyleRotationWindow(_HomepageStyleRotationBase):
    windowLabel: str
    lookbackDays: int = Field(ge=1, le=90)
    cadence: str
    comparisonBasis: str

    @field_validator("windowLabel", "cadence")
    @classmethod
    def _validate_short_text(cls, value: str) -> str:
        return ensure_homepage_style_rotation_text(
            value,
            field_name="rotationWindow.text",
            max_length=48,
        )

    @field_validator("comparisonBasis")
    @classmethod
    def _validate_comparison_basis(cls, value: str) -> str:
        return ensure_homepage_style_rotation_text(
            value,
            field_name="rotationWindow.comparisonBasis",
            max_length=120,
        )


class HomepageStyleRotationQualitySummary(_HomepageStyleRotationBase):
    state: HomepageStyleRotationState | HomepageStyleRotationDataQualityState
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_style_rotation_text(value, field_name="quality.label", max_length=48)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_style_rotation_text(
            value,
            field_name="quality.summary",
            max_length=180,
        )


class HomepageStyleLeadershipRegime(_HomepageStyleRotationBase):
    state: HomepageStyleRotationState
    label: str
    summary: str
    leadingStyles: list[HomepageStyleGroup] = Field(..., min_length=1, max_length=4)
    laggingStyles: list[HomepageStyleGroup] = Field(..., min_length=1, max_length=4)

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_style_rotation_text(
            value,
            field_name="leadershipRegime.label",
            max_length=60,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_style_rotation_text(
            value,
            field_name="leadershipRegime.summary",
            max_length=200,
        )


class HomepageStyleRotationEntry(_HomepageStyleRotationBase):
    styleGroup: HomepageStyleGroup
    label: str
    state: HomepageStyleRotationState
    trend: HomepageStyleRotationTrend
    observation: str
    confirmation: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_style_rotation_text(value, field_name="style.label", max_length=48)

    @field_validator("observation", "confirmation")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return ensure_homepage_style_rotation_text(value, field_name="style.text", max_length=180)


class HomepageStyleRotationSignal(_HomepageStyleRotationBase):
    styleGroup: HomepageStyleGroup
    state: HomepageStyleRotationState
    trend: HomepageStyleRotationTrend
    signalLabel: str
    observation: str
    missingConfirmation: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("signalLabel")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_style_rotation_text(
            value,
            field_name="rotationSignal.signalLabel",
            max_length=64,
        )

    @field_validator("observation")
    @classmethod
    def _validate_observation(cls, value: str) -> str:
        return ensure_homepage_style_rotation_text(
            value,
            field_name="rotationSignal.observation",
            max_length=180,
        )

    @field_validator("missingConfirmation")
    @classmethod
    def _validate_missing_confirmation(cls, value: list[str]) -> list[str]:
        return [
            ensure_homepage_style_rotation_text(
                item,
                field_name="rotationSignal.missingConfirmation",
                max_length=96,
            )
            for item in value
        ]


class HomepageStyleConfirmationSummary(_HomepageStyleRotationBase):
    state: HomepageStyleRotationState
    label: str
    summary: str
    confirmedBy: list[str] = Field(default_factory=list, max_length=4)
    needsConfirmation: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_style_rotation_text(
            value,
            field_name="confirmation.label",
            max_length=60,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_style_rotation_text(
            value,
            field_name="confirmation.summary",
            max_length=180,
        )

    @field_validator("confirmedBy", "needsConfirmation")
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_homepage_style_rotation_text(item, field_name="confirmation.listItem", max_length=96)
            for item in value
        ]


class HomepageStyleAffectedArea(_HomepageStyleRotationBase):
    name: str
    relationship: str
    state: HomepageStyleRotationState

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return ensure_homepage_style_rotation_text(value, field_name="affectedArea.name", max_length=64)

    @field_validator("relationship")
    @classmethod
    def _validate_relationship(cls, value: str) -> str:
        return ensure_homepage_style_rotation_text(
            value,
            field_name="affectedArea.relationship",
            max_length=160,
        )


class HomepageStyleLeadershipRotationSnapshot(_HomepageStyleRotationBase):
    schemaVersion: str = Field(default=HOMEPAGE_STYLE_LEADERSHIP_ROTATION_SCHEMA_VERSION)
    asOf: str = Field(default=HOMEPAGE_STYLE_LEADERSHIP_ROTATION_DEFAULT_AS_OF, min_length=1, max_length=40)
    rotationWindow: HomepageStyleRotationWindow
    leadershipRegime: HomepageStyleLeadershipRegime
    styleLeaders: list[HomepageStyleRotationEntry] = Field(..., min_length=1, max_length=8)
    styleLaggards: list[HomepageStyleRotationEntry] = Field(..., min_length=1, max_length=8)
    rotationSignals: list[HomepageStyleRotationSignal] = Field(..., min_length=8, max_length=8)
    confirmationStatus: HomepageStyleConfirmationSummary
    breadthConfirmation: HomepageStyleConfirmationSummary
    volatilityConfirmation: HomepageStyleConfirmationSummary
    ratesSensitivity: HomepageStyleConfirmationSummary
    affectedSectors: list[HomepageStyleAffectedArea] = Field(..., min_length=1, max_length=8)
    affectedThemes: list[HomepageStyleAffectedArea] = Field(..., min_length=1, max_length=8)
    missingEvidence: list[str] = Field(..., min_length=1, max_length=8)
    watchPoints: list[str] = Field(..., min_length=1, max_length=8)
    evidenceQuality: HomepageStyleRotationQualitySummary
    dataQuality: HomepageStyleRotationQualitySummary
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=100)

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        return ensure_homepage_style_rotation_text(value, field_name="asOf", max_length=40)

    @field_validator("missingEvidence", "watchPoints")
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_homepage_style_rotation_text(item, field_name="snapshot.listItem", max_length=120)
            for item in value
        ]

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_homepage_style_rotation_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=100,
        )

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepageStyleLeadershipRotationSnapshot":
        if self.schemaVersion != HOMEPAGE_STYLE_LEADERSHIP_ROTATION_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        signal_groups = tuple(signal.styleGroup for signal in self.rotationSignals)
        if signal_groups != HOMEPAGE_STYLE_GROUPS:
            raise ValueError("rotationSignals must include deterministic style groups in stable order")
        public_states = {signal.state for signal in self.rotationSignals}
        expected_states: set[HomepageStyleRotationState] = {
            "confirmed",
            "proxy",
            "conflicting",
            "no_evidence",
            "unavailable",
        }
        if not expected_states.issubset(public_states):
            raise ValueError("rotationSignals must expose all public evidence states")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_STYLE_GROUPS",
    "HOMEPAGE_STYLE_LEADERSHIP_ROTATION_DEFAULT_AS_OF",
    "HOMEPAGE_STYLE_LEADERSHIP_ROTATION_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_STYLE_LEADERSHIP_ROTATION_SCHEMA_VERSION",
    "HomepageStyleAffectedArea",
    "HomepageStyleConfirmationSummary",
    "HomepageStyleGroup",
    "HomepageStyleLeadershipRegime",
    "HomepageStyleLeadershipRotationSnapshot",
    "HomepageStyleRotationDataQualityState",
    "HomepageStyleRotationEntry",
    "HomepageStyleRotationQualitySummary",
    "HomepageStyleRotationSignal",
    "HomepageStyleRotationState",
    "HomepageStyleRotationTrend",
    "HomepageStyleRotationWindow",
    "contains_forbidden_homepage_style_rotation_text",
    "ensure_homepage_style_rotation_text",
]
