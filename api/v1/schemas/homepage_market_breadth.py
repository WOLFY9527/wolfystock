# -*- coding: utf-8 -*-
"""Standalone market breadth contract for the homepage intelligence cockpit."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HomepageBreadthRegimeStatus = Literal[
    "broadening",
    "narrowing",
    "concentrated",
    "mixed",
    "no_evidence",
]
HomepageBreadthPublicStatus = Literal[
    "confirmed",
    "proxy",
    "needs_confirmation",
    "mixed",
    "conflicting",
    "no_evidence",
]

HOMEPAGE_MARKET_BREADTH_SCHEMA_VERSION = "homepage_market_breadth_v1"
HOMEPAGE_MARKET_BREADTH_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_MARKET_BREADTH_NO_ADVICE_DISCLOSURE = (
    "仅用于市场广度观察与研究支持，不作为个性化决策依据。"
)

_FORBIDDEN_MARKET_BREADTH_RE = re.compile(
    r"交易指令|交易执行|交易建议|买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|"
    r"收益预测|AI推荐|智能选股|投资建议|下单|立即交易|"
    r"\b(?:buy|sell|add position|reduce position|clear position|broker|order|"
    r"trade execution|trade recommendation|trading advice|investment advice|"
    r"financial advice|target[\s-]?price|stop[\s-]?loss|take[\s-]?profit|"
    r"guaranteed)\b|"
    r"provider|fallback|diagnostic|debug|traceback|reasoncode|trustlevel|"
    r"sourcetype|raw|token|secret|cookie|session|api[_-]?key|https?://|"
    r"/users/|/tmp/|/api/v",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def contains_forbidden_homepage_market_breadth_text(value: Any) -> bool:
    return bool(_FORBIDDEN_MARKET_BREADTH_RE.search(str(value or "")))


def ensure_homepage_market_breadth_text(value: Any, *, field_name: str, max_length: int) -> str:
    text = _WHITESPACE_RE.sub(" ", str(value or "").strip())
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds max_length={max_length}")
    if contains_forbidden_homepage_market_breadth_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        if contains_forbidden_homepage_market_breadth_text(value):
            raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
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


class _HomepageMarketBreadthModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageBreadthRegime(_HomepageMarketBreadthModel):
    status: HomepageBreadthRegimeStatus
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_market_breadth_text(value, field_name="breadthRegime.label", max_length=40)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_market_breadth_text(
            value,
            field_name="breadthRegime.summary",
            max_length=180,
        )


class HomepageBreadthPublicState(_HomepageMarketBreadthModel):
    status: HomepageBreadthPublicStatus
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_market_breadth_text(value, field_name="publicState.label", max_length=44)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_market_breadth_text(
            value,
            field_name="publicState.summary",
            max_length=180,
        )


class HomepageBreadthAxisState(_HomepageMarketBreadthModel):
    status: HomepageBreadthPublicStatus
    label: str
    summary: str
    evidenceState: HomepageBreadthPublicStatus

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_market_breadth_text(value, field_name="axis.label", max_length=44)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_market_breadth_text(value, field_name="axis.summary", max_length=180)


class HomepageBreadthQuality(_HomepageMarketBreadthModel):
    status: HomepageBreadthPublicStatus
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_market_breadth_text(value, field_name="quality.label", max_length=44)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_market_breadth_text(value, field_name="quality.summary", max_length=180)


class HomepageBreadthDataQuality(_HomepageMarketBreadthModel):
    status: Literal["ready", "partial", "unavailable", "no_evidence"]
    label: str
    available: bool
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_market_breadth_text(value, field_name="dataQuality.label", max_length=44)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_market_breadth_text(
            value,
            field_name="dataQuality.summary",
            max_length=180,
        )


class HomepageMarketBreadthSnapshot(_HomepageMarketBreadthModel):
    schemaVersion: str = Field(default=HOMEPAGE_MARKET_BREADTH_SCHEMA_VERSION)
    asOf: str = Field(default=HOMEPAGE_MARKET_BREADTH_DEFAULT_AS_OF, min_length=1, max_length=40)
    breadthRegime: HomepageBreadthRegime
    participationSummary: HomepageBreadthPublicState
    advancingVsDeclining: HomepageBreadthAxisState
    leadershipConcentration: HomepageBreadthAxisState
    themeConcentration: HomepageBreadthAxisState
    largeCapVsSmallCap: HomepageBreadthAxisState
    growthVsValue: HomepageBreadthAxisState
    offensiveVsDefensive: HomepageBreadthAxisState
    confirmationStatus: HomepageBreadthPublicState
    missingEvidence: list[str] = Field(default_factory=list, max_length=8)
    watchPoints: list[str] = Field(..., min_length=1, max_length=8)
    evidenceQuality: HomepageBreadthQuality
    dataQuality: HomepageBreadthDataQuality
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=100)

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        return ensure_homepage_market_breadth_text(value, field_name="asOf", max_length=40)

    @field_validator("missingEvidence", "watchPoints")
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_homepage_market_breadth_text(item, field_name="list.item", max_length=120)
            for item in value
        ]

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_homepage_market_breadth_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=100,
        )

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepageMarketBreadthSnapshot":
        if self.schemaVersion != HOMEPAGE_MARKET_BREADTH_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        if self.confirmationStatus.status in {"proxy", "needs_confirmation", "no_evidence"}:
            if not self.missingEvidence:
                raise ValueError("unconfirmed breadth requires missingEvidence")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_MARKET_BREADTH_DEFAULT_AS_OF",
    "HOMEPAGE_MARKET_BREADTH_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_MARKET_BREADTH_SCHEMA_VERSION",
    "HomepageBreadthAxisState",
    "HomepageBreadthDataQuality",
    "HomepageBreadthPublicState",
    "HomepageBreadthPublicStatus",
    "HomepageBreadthQuality",
    "HomepageBreadthRegime",
    "HomepageBreadthRegimeStatus",
    "HomepageMarketBreadthSnapshot",
    "contains_forbidden_homepage_market_breadth_text",
    "ensure_homepage_market_breadth_text",
]
