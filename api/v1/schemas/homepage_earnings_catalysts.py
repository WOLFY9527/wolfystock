# -*- coding: utf-8 -*-
"""Standalone earnings catalysts contract for the homepage intelligence cockpit."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HomepageEarningsCatalystsQualityState = Literal["sample_proxy", "no_evidence", "unavailable"]
HomepageEarningsCatalystsCategory = Literal[
    "earnings_observation",
    "guidance_sensitivity",
    "mega_cap_report",
    "sector_read_through",
    "theme_read_through",
]

HOMEPAGE_EARNINGS_CATALYSTS_SCHEMA_VERSION = "homepage_earnings_catalysts_v1"
HOMEPAGE_EARNINGS_CATALYSTS_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_EARNINGS_CATALYSTS_NO_ADVICE_DISCLOSURE = (
    "Research observation only; not a personalized decision basis."
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


def contains_forbidden_earnings_catalysts_text(value: Any) -> bool:
    text = str(value or "")
    return bool(text and _FORBIDDEN_TEXT_RE.search(text))


def ensure_earnings_catalysts_text(
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
    if contains_forbidden_earnings_catalysts_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        ensure_earnings_catalysts_text(value, field_name=field_name, max_length=280)
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


class _HomepageEarningsCatalystsBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageEarningsCatalystsQuality(_HomepageEarningsCatalystsBase):
    state: HomepageEarningsCatalystsQualityState
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_earnings_catalysts_text(
            value,
            field_name="quality.label",
            max_length=72,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_earnings_catalysts_text(
            value,
            field_name="quality.summary",
            max_length=220,
        )


class HomepageEarningsCatalystWindow(_HomepageEarningsCatalystsBase):
    label: str
    startsAt: str
    endsAt: str
    basis: HomepageEarningsCatalystsQualityState
    summary: str

    @field_validator("label", "startsAt", "endsAt")
    @classmethod
    def _validate_short_text(cls, value: str) -> str:
        return ensure_earnings_catalysts_text(
            value,
            field_name="catalystWindow.text",
            max_length=80,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_earnings_catalysts_text(
            value,
            field_name="catalystWindow.summary",
            max_length=220,
        )


class HomepageEarningsCatalystObservation(_HomepageEarningsCatalystsBase):
    key: str = Field(..., min_length=1, max_length=64)
    label: str
    category: HomepageEarningsCatalystsCategory
    basis: HomepageEarningsCatalystsQualityState
    evidenceState: HomepageEarningsCatalystsQualityState
    observation: str
    researchContext: str
    affectedAssets: list[str] = Field(..., min_length=1, max_length=8)
    affectedSectors: list[str] = Field(..., min_length=1, max_length=8)
    affectedThemes: list[str] = Field(..., min_length=1, max_length=8)
    confirmationSignals: list[str] = Field(..., min_length=1, max_length=6)
    missingEvidence: list[str] = Field(..., min_length=1, max_length=6)
    watchPoints: list[str] = Field(..., min_length=1, max_length=6)

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_earnings_catalysts_text(
            value,
            field_name="observation.label",
            max_length=80,
        )

    @field_validator("observation", "researchContext")
    @classmethod
    def _validate_sentence(cls, value: str) -> str:
        return ensure_earnings_catalysts_text(
            value,
            field_name="observation.text",
            max_length=220,
        )

    @field_validator(
        "affectedAssets",
        "affectedSectors",
        "affectedThemes",
        "confirmationSignals",
        "missingEvidence",
        "watchPoints",
    )
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_earnings_catalysts_text(
                item,
                field_name="observation.listItem",
                max_length=120,
            )
            for item in value
        ]


class HomepageEarningsCatalystsSection(_HomepageEarningsCatalystsBase):
    state: HomepageEarningsCatalystsQualityState
    summary: str
    observations: list[HomepageEarningsCatalystObservation] = Field(
        ...,
        min_length=1,
        max_length=8,
    )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_earnings_catalysts_text(
            value,
            field_name="section.summary",
            max_length=220,
        )


class HomepageEarningsCatalystsSnapshot(_HomepageEarningsCatalystsBase):
    schemaVersion: str = Field(default=HOMEPAGE_EARNINGS_CATALYSTS_SCHEMA_VERSION)
    asOf: str = Field(default=HOMEPAGE_EARNINGS_CATALYSTS_DEFAULT_AS_OF, min_length=1, max_length=40)
    catalystWindow: HomepageEarningsCatalystWindow
    earningsCatalysts: list[HomepageEarningsCatalystObservation] = Field(
        ...,
        min_length=1,
        max_length=8,
    )
    guidanceSensitivity: HomepageEarningsCatalystsSection
    megaCapImpact: HomepageEarningsCatalystsSection
    sectorReadThrough: HomepageEarningsCatalystsSection
    themeReadThrough: HomepageEarningsCatalystsSection
    affectedAssets: list[str] = Field(..., min_length=1, max_length=12)
    affectedSectors: list[str] = Field(..., min_length=1, max_length=12)
    affectedThemes: list[str] = Field(..., min_length=1, max_length=12)
    confirmationSignals: list[str] = Field(..., min_length=1, max_length=8)
    missingEvidence: list[str] = Field(..., min_length=1, max_length=8)
    watchPoints: list[str] = Field(..., min_length=1, max_length=8)
    evidenceQuality: HomepageEarningsCatalystsQuality
    dataQuality: HomepageEarningsCatalystsQuality
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=100)

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        return ensure_earnings_catalysts_text(value, field_name="asOf", max_length=40)

    @field_validator(
        "affectedAssets",
        "affectedSectors",
        "affectedThemes",
        "confirmationSignals",
        "missingEvidence",
        "watchPoints",
    )
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_earnings_catalysts_text(
                item,
                field_name="snapshot.listItem",
                max_length=120,
            )
            for item in value
        ]

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_earnings_catalysts_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=100,
        )

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepageEarningsCatalystsSnapshot":
        if self.schemaVersion != HOMEPAGE_EARNINGS_CATALYSTS_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_EARNINGS_CATALYSTS_DEFAULT_AS_OF",
    "HOMEPAGE_EARNINGS_CATALYSTS_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_EARNINGS_CATALYSTS_SCHEMA_VERSION",
    "HomepageEarningsCatalystObservation",
    "HomepageEarningsCatalystWindow",
    "HomepageEarningsCatalystsCategory",
    "HomepageEarningsCatalystsQuality",
    "HomepageEarningsCatalystsQualityState",
    "HomepageEarningsCatalystsSection",
    "HomepageEarningsCatalystsSnapshot",
    "contains_forbidden_earnings_catalysts_text",
    "ensure_earnings_catalysts_text",
]
