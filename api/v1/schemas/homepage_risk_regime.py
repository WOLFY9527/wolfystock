# -*- coding: utf-8 -*-
"""Standalone safe contract for homepage risk-regime market pricing."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HomepageRiskRegime = Literal["risk_on", "neutral", "risk_off", "mixed", "unavailable"]
HomepageRiskSignalState = Literal["supportive", "neutral", "pressure", "mixed", "unavailable"]
HomepageRiskEvidenceQuality = Literal["confirmed", "needs_confirmation", "mixed", "unavailable"]
HomepageRiskDataQualityStatus = Literal["ready", "partial", "no_evidence", "unavailable"]

HOMEPAGE_RISK_REGIME_SCHEMA_VERSION = "homepage_risk_regime_v1"
HOMEPAGE_RISK_REGIME_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_RISK_REGIME_NO_ADVICE_DISCLOSURE = (
    "本合约仅用于首页市场背景观察，不构成个性化建议。"
)

_FORBIDDEN_TEXT_RE = re.compile(
    r"买入|卖出|加仓|减仓|清仓|下单|交易指令|交易执行|交易建议|投资建议|"
    r"目标价|止损|止盈|个性化配置|"
    r"\b(?:buy|sell|add|reduce|broker|order|execution|target[\s-]?price|"
    r"personalized[\s-]?allocation)\b|"
    r"provider|diagnostic|debug|traceback|reasoncode|trustlevel|sourcetype|"
    r"raw|token|secret|cookie|session|api[_-]?key|https?://|/users/",
    re.IGNORECASE,
)


def contains_forbidden_homepage_risk_regime_text(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and _FORBIDDEN_TEXT_RE.search(text))


def ensure_homepage_risk_regime_text(value: Any, *, field_name: str, max_length: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds max_length={max_length}")
    if contains_forbidden_homepage_risk_regime_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        ensure_homepage_risk_regime_text(value, field_name=field_name, max_length=220)
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


class _HomepageRiskRegimeBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageRiskRegimeEvidence(_HomepageRiskRegimeBase):
    key: str = Field(..., min_length=1, max_length=40)
    label: str
    observation: str
    implication: str
    evidenceQuality: HomepageRiskEvidenceQuality

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(value, field_name="evidence.label", max_length=48)

    @field_validator("observation")
    @classmethod
    def _validate_observation(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(value, field_name="evidence.observation", max_length=140)

    @field_validator("implication")
    @classmethod
    def _validate_implication(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(value, field_name="evidence.implication", max_length=140)


class HomepageRiskRegimeContradiction(_HomepageRiskRegimeBase):
    key: str = Field(..., min_length=1, max_length=40)
    label: str
    observation: str
    whyItMatters: str
    evidenceQuality: HomepageRiskEvidenceQuality

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(
            value,
            field_name="contradictions.label",
            max_length=48,
        )

    @field_validator("observation")
    @classmethod
    def _validate_observation(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(
            value,
            field_name="contradictions.observation",
            max_length=140,
        )

    @field_validator("whyItMatters")
    @classmethod
    def _validate_why_it_matters(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(
            value,
            field_name="contradictions.whyItMatters",
            max_length=140,
        )


class HomepageMarketPricingItem(_HomepageRiskRegimeBase):
    key: str = Field(..., min_length=1, max_length=40)
    label: str
    affectedVariables: list[str] = Field(..., min_length=1, max_length=6)
    pricingLanguage: str
    implication: str
    evidenceQuality: HomepageRiskEvidenceQuality
    watchPoints: list[str] = Field(..., min_length=1, max_length=4)

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(
            value,
            field_name="marketPricing.label",
            max_length=48,
        )

    @field_validator("pricingLanguage")
    @classmethod
    def _validate_pricing_language(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(
            value,
            field_name="marketPricing.pricingLanguage",
            max_length=160,
        )

    @field_validator("implication")
    @classmethod
    def _validate_implication(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(
            value,
            field_name="marketPricing.implication",
            max_length=140,
        )

    @field_validator("affectedVariables", "watchPoints")
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_homepage_risk_regime_text(item, field_name="marketPricing.list", max_length=64)
            for item in value
        ]


class HomepageRiskSignal(_HomepageRiskRegimeBase):
    state: HomepageRiskSignalState
    label: str
    summary: str
    affectedVariables: list[str] = Field(default_factory=list, max_length=6)
    evidenceQuality: HomepageRiskEvidenceQuality
    watchPoints: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(value, field_name="signal.label", max_length=48)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(value, field_name="signal.summary", max_length=160)

    @field_validator("affectedVariables", "watchPoints")
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_homepage_risk_regime_text(item, field_name="signal.list", max_length=64)
            for item in value
        ]


class HomepageRiskEvidenceQualitySummary(_HomepageRiskRegimeBase):
    state: HomepageRiskEvidenceQuality
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(
            value,
            field_name="evidenceQuality.label",
            max_length=40,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(
            value,
            field_name="evidenceQuality.summary",
            max_length=140,
        )


class HomepageRiskDataQuality(_HomepageRiskRegimeBase):
    status: HomepageRiskDataQualityStatus
    label: str
    available: bool
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(value, field_name="dataQuality.label", max_length=40)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(
            value,
            field_name="dataQuality.summary",
            max_length=140,
        )


class HomepageRiskRegimeSnapshot(_HomepageRiskRegimeBase):
    schemaVersion: str = Field(default=HOMEPAGE_RISK_REGIME_SCHEMA_VERSION)
    asOf: str = Field(default=HOMEPAGE_RISK_REGIME_DEFAULT_AS_OF, min_length=1, max_length=40)
    regime: HomepageRiskRegime
    regimeLabel: str
    summary: str
    evidence: list[HomepageRiskRegimeEvidence] = Field(..., min_length=1, max_length=8)
    contradictions: list[HomepageRiskRegimeContradiction] = Field(default_factory=list, max_length=6)
    marketPricing: list[HomepageMarketPricingItem] = Field(..., min_length=1, max_length=12)
    ratesPricing: HomepageRiskSignal
    volatilitySignal: HomepageRiskSignal
    dollarSignal: HomepageRiskSignal
    creditSignal: HomepageRiskSignal
    commoditySignal: HomepageRiskSignal
    cryptoSignal: HomepageRiskSignal
    equityStyleSignal: HomepageRiskSignal
    defensiveVsOffensiveSignal: HomepageRiskSignal
    watchPoints: list[str] = Field(..., min_length=1, max_length=8)
    evidenceQuality: HomepageRiskEvidenceQualitySummary
    dataQuality: HomepageRiskDataQuality
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=80)

    @field_validator("regimeLabel")
    @classmethod
    def _validate_regime_label(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(value, field_name="regimeLabel", max_length=32)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(value, field_name="summary", max_length=180)

    @field_validator("watchPoints")
    @classmethod
    def _validate_watch_points(cls, value: list[str]) -> list[str]:
        return [
            ensure_homepage_risk_regime_text(item, field_name="watchPoints", max_length=72)
            for item in value
        ]

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_homepage_risk_regime_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=80,
        )

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("asOf must not be empty")
        if len(text) > 40 or contains_forbidden_homepage_risk_regime_text(text):
            raise ValueError("asOf contains forbidden content")
        return text

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepageRiskRegimeSnapshot":
        if self.schemaVersion != HOMEPAGE_RISK_REGIME_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_RISK_REGIME_DEFAULT_AS_OF",
    "HOMEPAGE_RISK_REGIME_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_RISK_REGIME_SCHEMA_VERSION",
    "HomepageMarketPricingItem",
    "HomepageRiskDataQuality",
    "HomepageRiskDataQualityStatus",
    "HomepageRiskEvidenceQuality",
    "HomepageRiskEvidenceQualitySummary",
    "HomepageRiskRegime",
    "HomepageRiskRegimeContradiction",
    "HomepageRiskRegimeEvidence",
    "HomepageRiskRegimeSnapshot",
    "HomepageRiskSignal",
    "HomepageRiskSignalState",
    "contains_forbidden_homepage_risk_regime_text",
    "ensure_homepage_risk_regime_text",
]
