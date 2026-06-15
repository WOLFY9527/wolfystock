# -*- coding: utf-8 -*-
"""Standalone AI capex infrastructure monitor contract for the homepage cockpit."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HomepageAICapexInfrastructureQualityState = Literal["sample_proxy", "no_evidence", "unavailable"]

HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_SCHEMA_VERSION = "homepage_ai_capex_infrastructure_v1"
HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_NO_ADVICE_DISCLOSURE = (
    "For AI infrastructure research monitoring only; not an investment recommendation."
)

_FORBIDDEN_TEXT_RE = re.compile(
    r"交易指令|交易执行|交易建议|买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|"
    r"收益预测|AI推荐|智能选股|投资建议|下单|立即交易|"
    r"\b(?:buy|sell|broker|order|execution|trade[\s-]?execution|"
    r"trading[\s-]?advice|investment[\s-]?advice|financial[\s-]?advice|"
    r"target[\s-]?price|stop[\s-]?loss|take[\s-]?profit|guaranteed)\b|"
    r"provider|fallback|internal|diagnostic|debug|traceback|reasoncode|trustlevel|"
    r"sourcetype|raw|token|secret|cookie|session|api[_-]?key|https?://|/users/|/tmp/",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def contains_forbidden_ai_capex_infrastructure_text(value: Any) -> bool:
    text = str(value or "")
    return bool(text and _FORBIDDEN_TEXT_RE.search(text))


def ensure_ai_capex_infrastructure_text(
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
    if contains_forbidden_ai_capex_infrastructure_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        ensure_ai_capex_infrastructure_text(value, field_name=field_name, max_length=260)
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


class _HomepageAICapexInfrastructureBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageAICapexInfrastructureQuality(_HomepageAICapexInfrastructureBase):
    state: HomepageAICapexInfrastructureQualityState
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_ai_capex_infrastructure_text(value, field_name="quality.label", max_length=72)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_ai_capex_infrastructure_text(value, field_name="quality.summary", max_length=220)


class HomepageAICapexInfrastructureWindow(_HomepageAICapexInfrastructureBase):
    label: str
    startsAt: str
    endsAt: str
    basis: HomepageAICapexInfrastructureQualityState
    summary: str

    @field_validator("label", "startsAt", "endsAt")
    @classmethod
    def _validate_short_text(cls, value: str) -> str:
        return ensure_ai_capex_infrastructure_text(value, field_name="window.text", max_length=80)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_ai_capex_infrastructure_text(value, field_name="window.summary", max_length=220)


class HomepageAICapexInfrastructureSignal(_HomepageAICapexInfrastructureBase):
    key: str = Field(..., min_length=1, max_length=64)
    label: str
    evidenceState: HomepageAICapexInfrastructureQualityState
    observation: str
    researchContext: str
    relatedThemes: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_ai_capex_infrastructure_text(value, field_name="signal.label", max_length=80)

    @field_validator("observation", "researchContext")
    @classmethod
    def _validate_sentence(cls, value: str) -> str:
        return ensure_ai_capex_infrastructure_text(value, field_name="signal.text", max_length=220)

    @field_validator("relatedThemes")
    @classmethod
    def _validate_related_themes(cls, value: list[str]) -> list[str]:
        return [
            ensure_ai_capex_infrastructure_text(item, field_name="signal.relatedTheme", max_length=80)
            for item in value
        ]


class HomepageAICapexInfrastructureSection(_HomepageAICapexInfrastructureBase):
    state: HomepageAICapexInfrastructureQualityState
    label: str
    evidenceState: HomepageAICapexInfrastructureQualityState
    observation: str
    researchContext: str
    watchPoints: list[HomepageAICapexInfrastructureSignal] = Field(..., min_length=1, max_length=6)

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_ai_capex_infrastructure_text(value, field_name="section.label", max_length=80)

    @field_validator("observation", "researchContext")
    @classmethod
    def _validate_sentence(cls, value: str) -> str:
        return ensure_ai_capex_infrastructure_text(value, field_name="section.text", max_length=220)


class HomepageAICapexInfrastructureSnapshot(_HomepageAICapexInfrastructureBase):
    schemaVersion: str = Field(default=HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_SCHEMA_VERSION)
    asOf: str = Field(default=HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_DEFAULT_AS_OF, min_length=1, max_length=40)
    monitorWindow: HomepageAICapexInfrastructureWindow
    capexSignal: HomepageAICapexInfrastructureSignal
    demandSignals: list[HomepageAICapexInfrastructureSignal] = Field(..., min_length=1, max_length=8)
    supplyConstraints: list[HomepageAICapexInfrastructureSignal] = Field(..., min_length=1, max_length=8)
    computeSupplyChain: list[HomepageAICapexInfrastructureSignal] = Field(..., min_length=1, max_length=10)
    dataCenterDemand: HomepageAICapexInfrastructureSection
    powerConstraint: HomepageAICapexInfrastructureSection
    liquidCoolingConstraint: HomepageAICapexInfrastructureSection
    gridConstraint: HomepageAICapexInfrastructureSection
    affectedSectors: list[str] = Field(..., min_length=1, max_length=12)
    affectedThemes: list[str] = Field(..., min_length=1, max_length=12)
    confirmationSignals: list[HomepageAICapexInfrastructureSignal] = Field(..., min_length=1, max_length=8)
    missingEvidence: list[HomepageAICapexInfrastructureSignal] = Field(..., min_length=1, max_length=8)
    watchPoints: list[HomepageAICapexInfrastructureSignal] = Field(..., min_length=1, max_length=8)
    evidenceQuality: HomepageAICapexInfrastructureQuality
    dataQuality: HomepageAICapexInfrastructureQuality
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=120)

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        return ensure_ai_capex_infrastructure_text(value, field_name="asOf", max_length=40)

    @field_validator("affectedSectors", "affectedThemes")
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_ai_capex_infrastructure_text(item, field_name="snapshot.listItem", max_length=80)
            for item in value
        ]

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_ai_capex_infrastructure_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=120,
        )

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepageAICapexInfrastructureSnapshot":
        if self.schemaVersion != HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_DEFAULT_AS_OF",
    "HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_SCHEMA_VERSION",
    "HomepageAICapexInfrastructureQuality",
    "HomepageAICapexInfrastructureQualityState",
    "HomepageAICapexInfrastructureSection",
    "HomepageAICapexInfrastructureSignal",
    "HomepageAICapexInfrastructureSnapshot",
    "HomepageAICapexInfrastructureWindow",
    "contains_forbidden_ai_capex_infrastructure_text",
    "ensure_ai_capex_infrastructure_text",
]
