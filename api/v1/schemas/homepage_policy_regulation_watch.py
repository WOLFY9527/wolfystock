# -*- coding: utf-8 -*-
"""Standalone policy and regulation watch contract for the homepage intelligence cockpit."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HomepagePolicyRegulationCategory = Literal[
    "Fed communication",
    "Treasury issuance / auction pressure",
    "fiscal spending",
    "industrial policy",
    "AI regulation",
    "energy policy",
    "China policy support",
    "market-structure regulation",
]
HomepagePolicyRegulationEvidenceState = Literal["sample_proxy", "no_evidence", "unavailable"]
HomepagePolicyRegulationConfidence = Literal["low", "medium", "unavailable"]

HOMEPAGE_POLICY_REGULATION_WATCH_SCHEMA_VERSION = "homepage_policy_regulation_watch_v1"
HOMEPAGE_POLICY_REGULATION_WATCH_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_POLICY_REGULATION_WATCH_NO_ADVICE_DISCLOSURE = (
    "observation-only research context; not a personalized decision basis."
)

_FORBIDDEN_TEXT_RE = re.compile(
    r"交易指令|交易执行|交易建议|买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|"
    r"收益预测|AI推荐|智能选股|投资建议|下单|立即交易|"
    r"\b(?:buy|sell|broker|order|trade[\s-]?execution|trading[\s-]?advice|"
    r"investment[\s-]?advice|financial[\s-]?advice|target[\s-]?price|"
    r"stop[\s-]?loss|take[\s-]?profit|place[\s-]?order|submit[\s-]?order)\b|"
    r"provider|fallback|internal|diagnostic|debug|traceback|reasoncode|trustlevel|"
    r"sourcetype|raw|token|secret|cookie|session|api[_-]?key|https?://|/users/|/tmp/",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def contains_forbidden_policy_regulation_watch_text(value: Any) -> bool:
    text = str(value or "")
    return bool(text and _FORBIDDEN_TEXT_RE.search(text))


def ensure_policy_regulation_watch_text(value: Any, *, field_name: str, max_length: int) -> str:
    text = _WHITESPACE_RE.sub(" ", str(value or "").strip())
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds max_length={max_length}")
    if contains_forbidden_policy_regulation_watch_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        ensure_policy_regulation_watch_text(value, field_name=field_name, max_length=260)
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


class _HomepagePolicyRegulationWatchBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepagePolicyRegulationWatchWindow(_HomepagePolicyRegulationWatchBase):
    label: str
    scope: str
    evidenceState: HomepagePolicyRegulationEvidenceState

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_policy_regulation_watch_text(value, field_name="policyWindow.label", max_length=80)

    @field_validator("scope")
    @classmethod
    def _validate_scope(cls, value: str) -> str:
        return ensure_policy_regulation_watch_text(value, field_name="policyWindow.scope", max_length=180)


class HomepagePolicyRegulationWatchEvent(_HomepagePolicyRegulationWatchBase):
    category: HomepagePolicyRegulationCategory
    observation: str
    marketArea: str
    affectedAssets: list[str] = Field(..., min_length=1, max_length=8)
    affectedSectors: list[str] = Field(..., min_length=1, max_length=8)
    affectedThemes: list[str] = Field(..., min_length=1, max_length=8)
    evidenceState: HomepagePolicyRegulationEvidenceState

    @field_validator("observation")
    @classmethod
    def _validate_observation(cls, value: str) -> str:
        return ensure_policy_regulation_watch_text(value, field_name="event.observation", max_length=220)

    @field_validator("marketArea")
    @classmethod
    def _validate_market_area(cls, value: str) -> str:
        return ensure_policy_regulation_watch_text(value, field_name="event.marketArea", max_length=120)

    @field_validator("affectedAssets", "affectedSectors", "affectedThemes")
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_policy_regulation_watch_text(item, field_name="policyRegulationWatch.listItem", max_length=120)
            for item in value
        ]


class HomepagePolicyRegulationWatchContext(_HomepagePolicyRegulationWatchBase):
    label: str
    observation: str
    marketTransmission: str
    evidenceState: HomepagePolicyRegulationEvidenceState

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_policy_regulation_watch_text(value, field_name="context.label", max_length=80)

    @field_validator("observation")
    @classmethod
    def _validate_observation(cls, value: str) -> str:
        return ensure_policy_regulation_watch_text(value, field_name="context.observation", max_length=220)

    @field_validator("marketTransmission")
    @classmethod
    def _validate_market_transmission(cls, value: str) -> str:
        return ensure_policy_regulation_watch_text(value, field_name="context.marketTransmission", max_length=220)


class HomepagePolicyRegulationWatchQuality(_HomepagePolicyRegulationWatchBase):
    state: HomepagePolicyRegulationEvidenceState
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_policy_regulation_watch_text(value, field_name="quality.label", max_length=80)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_policy_regulation_watch_text(value, field_name="quality.summary", max_length=220)


class HomepagePolicyRegulationWatchSnapshot(_HomepagePolicyRegulationWatchBase):
    schemaVersion: str = Field(default=HOMEPAGE_POLICY_REGULATION_WATCH_SCHEMA_VERSION)
    asOf: str = Field(default=HOMEPAGE_POLICY_REGULATION_WATCH_DEFAULT_AS_OF, min_length=1, max_length=40)
    policyWindow: HomepagePolicyRegulationWatchWindow
    policyEvents: list[HomepagePolicyRegulationWatchEvent] = Field(..., min_length=1, max_length=8)
    regulationEvents: list[HomepagePolicyRegulationWatchEvent] = Field(..., min_length=1, max_length=8)
    monetaryPolicyContext: HomepagePolicyRegulationWatchContext
    fiscalPolicyContext: HomepagePolicyRegulationWatchContext
    industrialPolicyContext: HomepagePolicyRegulationWatchContext
    affectedAssets: list[str] = Field(..., min_length=1, max_length=12)
    affectedSectors: list[str] = Field(..., min_length=1, max_length=12)
    affectedThemes: list[str] = Field(..., min_length=1, max_length=12)
    confidence: HomepagePolicyRegulationConfidence
    missingEvidence: list[str] = Field(..., min_length=1, max_length=10)
    watchPoints: list[str] = Field(..., min_length=1, max_length=10)
    evidenceQuality: HomepagePolicyRegulationWatchQuality
    dataQuality: HomepagePolicyRegulationWatchQuality
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=120)

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        return ensure_policy_regulation_watch_text(value, field_name="asOf", max_length=40)

    @field_validator("affectedAssets", "affectedSectors", "affectedThemes", "missingEvidence", "watchPoints")
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_policy_regulation_watch_text(item, field_name="policyRegulationWatch.listItem", max_length=140)
            for item in value
        ]

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_policy_regulation_watch_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=120,
        )

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepagePolicyRegulationWatchSnapshot":
        if self.schemaVersion != HOMEPAGE_POLICY_REGULATION_WATCH_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_POLICY_REGULATION_WATCH_DEFAULT_AS_OF",
    "HOMEPAGE_POLICY_REGULATION_WATCH_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_POLICY_REGULATION_WATCH_SCHEMA_VERSION",
    "HomepagePolicyRegulationCategory",
    "HomepagePolicyRegulationConfidence",
    "HomepagePolicyRegulationEvidenceState",
    "HomepagePolicyRegulationWatchContext",
    "HomepagePolicyRegulationWatchEvent",
    "HomepagePolicyRegulationWatchQuality",
    "HomepagePolicyRegulationWatchSnapshot",
    "HomepagePolicyRegulationWatchWindow",
    "contains_forbidden_policy_regulation_watch_text",
    "ensure_policy_regulation_watch_text",
]
