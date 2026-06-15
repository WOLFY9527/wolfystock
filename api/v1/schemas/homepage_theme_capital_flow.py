# -*- coding: utf-8 -*-
"""Standalone Theme Capital Flow contract for the homepage intelligence cockpit."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HomepageThemeFlowAuthority = Literal["authoritative", "proxy_only", "unavailable", "no_evidence"]
HomepageThemeFlowDirection = Literal["inflow", "outflow", "strengthening", "fading", "neutral"]
HomepageThemeFlowConviction = Literal["high", "medium", "low", "unavailable", "no_evidence"]
HomepageThemeEvidenceQualityStatus = Literal[
    "proxy_observation",
    "needs_confirmation",
    "mixed",
    "unavailable",
    "no_evidence",
]
HomepageThemeDataQualityStatus = Literal["ready", "partial", "unavailable", "no_evidence"]
HomepageThemeBreadthStatus = Literal["broadening", "selective", "narrow", "mixed", "no_evidence"]
HomepageThemeConcentrationStatus = Literal[
    "concentrated",
    "balanced",
    "diffuse",
    "mixed",
    "no_evidence",
]

HOMEPAGE_THEME_CAPITAL_FLOW_SCHEMA_VERSION = "homepage_theme_capital_flow_v1"
HOMEPAGE_THEME_CAPITAL_FLOW_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_THEME_CAPITAL_FLOW_NO_ADVICE_DISCLOSURE = (
    "仅用于主题资金观察与研究支持，不作为个性化决策依据。"
)

_FORBIDDEN_THEME_FLOW_RE = re.compile(
    r"交易指令|交易执行|交易建议|买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|"
    r"收益预测|AI推荐|智能选股|投资建议|"
    r"\b(?:buy|sell|add position|reduce position|clear position|broker|order|"
    r"trade execution|target[\s-]?price|stop[\s-]?loss|take[\s-]?profit|"
    r"guaranteed return)\b|"
    r"provider|diagnostic|debug|traceback|reasoncode|trustlevel|sourcetype|"
    r"fallback|raw|token|secret|cookie|session|api[_-]?key|https?://|/users/|/tmp/",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def contains_forbidden_homepage_theme_flow_text(value: Any) -> bool:
    return bool(_FORBIDDEN_THEME_FLOW_RE.search(str(value or "")))


def ensure_homepage_theme_flow_text(value: Any, *, field_name: str, max_length: int) -> str:
    text = _WHITESPACE_RE.sub(" ", str(value or "").strip())
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds max_length={max_length}")
    if contains_forbidden_homepage_theme_flow_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        if contains_forbidden_homepage_theme_flow_text(value):
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


class _HomepageThemeCapitalFlowModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageThemeFlowAuthorityDefinition(_HomepageThemeCapitalFlowModel):
    state: HomepageThemeFlowAuthority
    label: str
    meaning: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_theme_flow_text(
            value,
            field_name="flowAuthority.definition.label",
            max_length=32,
        )

    @field_validator("meaning")
    @classmethod
    def _validate_meaning(cls, value: str) -> str:
        return ensure_homepage_theme_flow_text(
            value,
            field_name="flowAuthority.definition.meaning",
            max_length=120,
        )


class HomepageThemeFlowAuthoritySummary(_HomepageThemeCapitalFlowModel):
    status: HomepageThemeFlowAuthority
    label: str
    summary: str
    authoritativeAvailable: bool
    definitions: list[HomepageThemeFlowAuthorityDefinition] = Field(min_length=4, max_length=4)

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_theme_flow_text(
            value,
            field_name="flowAuthority.label",
            max_length=40,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_theme_flow_text(
            value,
            field_name="flowAuthority.summary",
            max_length=180,
        )

    @model_validator(mode="after")
    def _validate_definitions(self) -> "HomepageThemeFlowAuthoritySummary":
        states = {definition.state for definition in self.definitions}
        expected = {"authoritative", "proxy_only", "unavailable", "no_evidence"}
        if states != expected:
            raise ValueError("flowAuthority.definitions must cover all authority states")
        if self.status == "authoritative" and not self.authoritativeAvailable:
            raise ValueError("authoritative status requires authoritativeAvailable")
        return self


class HomepageThemeFlowItem(_HomepageThemeCapitalFlowModel):
    key: str = Field(min_length=1, max_length=48)
    theme: str
    direction: HomepageThemeFlowDirection
    flowAuthority: HomepageThemeFlowAuthority
    proxyOnly: bool
    conviction: HomepageThemeFlowConviction
    evidenceQuality: HomepageThemeEvidenceQualityStatus
    dataQuality: HomepageThemeDataQualityStatus
    observation: str
    watchPoint: str

    @field_validator("theme")
    @classmethod
    def _validate_theme(cls, value: str) -> str:
        return ensure_homepage_theme_flow_text(value, field_name="theme", max_length=48)

    @field_validator("observation")
    @classmethod
    def _validate_observation(cls, value: str) -> str:
        return ensure_homepage_theme_flow_text(value, field_name="theme.observation", max_length=180)

    @field_validator("watchPoint")
    @classmethod
    def _validate_watch_point(cls, value: str) -> str:
        return ensure_homepage_theme_flow_text(value, field_name="theme.watchPoint", max_length=120)

    @model_validator(mode="after")
    def _validate_proxy_boundary(self) -> "HomepageThemeFlowItem":
        if self.flowAuthority == "authoritative" and self.proxyOnly:
            raise ValueError("authoritative theme cannot be proxyOnly")
        if self.flowAuthority != "authoritative" and not self.proxyOnly:
            raise ValueError("non-authoritative theme must be proxyOnly")
        return self


class HomepageThemeFlowAggregate(_HomepageThemeCapitalFlowModel):
    status: HomepageThemeConcentrationStatus | HomepageThemeBreadthStatus
    label: str
    summary: str
    evidenceQuality: HomepageThemeEvidenceQualityStatus

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_theme_flow_text(value, field_name="aggregate.label", max_length=32)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_theme_flow_text(value, field_name="aggregate.summary", max_length=160)


class HomepageThemeFlowEvidenceInput(_HomepageThemeCapitalFlowModel):
    key: str = Field(min_length=1, max_length=48)
    label: str
    authority: HomepageThemeFlowAuthority
    available: bool
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_theme_flow_text(
            value,
            field_name="evidenceInputs.label",
            max_length=48,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_theme_flow_text(
            value,
            field_name="evidenceInputs.summary",
            max_length=160,
        )

    @model_validator(mode="after")
    def _validate_availability(self) -> "HomepageThemeFlowEvidenceInput":
        if self.authority in {"unavailable", "no_evidence"} and self.available:
            raise ValueError("unavailable and no_evidence inputs cannot be available")
        return self


class HomepageThemeFlowEvidenceQuality(_HomepageThemeCapitalFlowModel):
    status: HomepageThemeEvidenceQualityStatus
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_theme_flow_text(
            value,
            field_name="evidenceQuality.label",
            max_length=40,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_theme_flow_text(
            value,
            field_name="evidenceQuality.summary",
            max_length=160,
        )


class HomepageThemeFlowDataQuality(_HomepageThemeCapitalFlowModel):
    status: HomepageThemeDataQualityStatus
    label: str
    available: bool
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_theme_flow_text(value, field_name="dataQuality.label", max_length=40)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_theme_flow_text(
            value,
            field_name="dataQuality.summary",
            max_length=160,
        )


class HomepageThemeCapitalFlowSnapshot(_HomepageThemeCapitalFlowModel):
    schemaVersion: str = Field(default=HOMEPAGE_THEME_CAPITAL_FLOW_SCHEMA_VERSION)
    asOf: str = Field(default=HOMEPAGE_THEME_CAPITAL_FLOW_DEFAULT_AS_OF, min_length=1, max_length=40)
    flowAuthority: HomepageThemeFlowAuthoritySummary
    proxyOnly: bool
    inflowThemes: list[HomepageThemeFlowItem] = Field(min_length=1, max_length=12)
    outflowThemes: list[HomepageThemeFlowItem] = Field(min_length=1, max_length=12)
    strengtheningThemes: list[HomepageThemeFlowItem] = Field(min_length=1, max_length=12)
    fadingThemes: list[HomepageThemeFlowItem] = Field(min_length=1, max_length=12)
    concentration: HomepageThemeFlowAggregate
    breadth: HomepageThemeFlowAggregate
    evidenceInputs: list[HomepageThemeFlowEvidenceInput] = Field(min_length=1, max_length=8)
    evidenceQuality: HomepageThemeFlowEvidenceQuality
    dataQuality: HomepageThemeFlowDataQuality
    noAdviceDisclosure: str = Field(min_length=1, max_length=100)

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        return ensure_homepage_theme_flow_text(value, field_name="asOf", max_length=40)

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_homepage_theme_flow_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=100,
        )

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepageThemeCapitalFlowSnapshot":
        if self.schemaVersion != HOMEPAGE_THEME_CAPITAL_FLOW_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        if self.proxyOnly != (self.flowAuthority.status == "proxy_only"):
            raise ValueError("proxyOnly must match flowAuthority.status")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_THEME_CAPITAL_FLOW_DEFAULT_AS_OF",
    "HOMEPAGE_THEME_CAPITAL_FLOW_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_THEME_CAPITAL_FLOW_SCHEMA_VERSION",
    "HomepageThemeBreadthStatus",
    "HomepageThemeCapitalFlowSnapshot",
    "HomepageThemeDataQualityStatus",
    "HomepageThemeEvidenceQualityStatus",
    "HomepageThemeFlowAggregate",
    "HomepageThemeFlowAuthority",
    "HomepageThemeFlowAuthorityDefinition",
    "HomepageThemeFlowAuthoritySummary",
    "HomepageThemeFlowConviction",
    "HomepageThemeFlowDataQuality",
    "HomepageThemeFlowDirection",
    "HomepageThemeFlowEvidenceInput",
    "HomepageThemeFlowEvidenceQuality",
    "HomepageThemeFlowItem",
    "contains_forbidden_homepage_theme_flow_text",
    "ensure_homepage_theme_flow_text",
]
