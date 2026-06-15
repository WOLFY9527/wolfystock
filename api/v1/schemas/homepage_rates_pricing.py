# -*- coding: utf-8 -*-
"""Standalone Rates Pricing contract for the homepage intelligence cockpit."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HomepageRatesPricingMode = Literal["proxy_only", "unavailable"]
HomepageRatesPricingAuthority = Literal["proxy_only", "unavailable", "no_evidence"]
HomepageRatesPolicyBias = Literal[
    "higher_for_longer",
    "easing_bias",
    "balanced",
    "uncertain",
]
HomepageRatesSignalState = Literal[
    "supportive",
    "restrictive",
    "mixed",
    "watch",
    "unavailable",
    "no_evidence",
]
HomepageRatesEvidenceQualityState = Literal[
    "proxy_observation",
    "needs_confirmation",
    "mixed",
    "unavailable",
    "no_evidence",
]
HomepageRatesDataQualityState = Literal["deterministic", "partial", "unavailable", "no_evidence"]

HOMEPAGE_RATES_PRICING_SCHEMA_VERSION = "homepage_rates_pricing_v1"
HOMEPAGE_RATES_PRICING_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_RATES_PRICING_NO_ADVICE_DISCLOSURE = (
    "仅用于利率背景观察与研究线索整理，不作为个性化决策依据。"
)

_FORBIDDEN_RATES_PRICING_RE = re.compile(
    r"交易指令|交易执行|交易建议|买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|"
    r"收益预测|AI推荐|智能选股|投资建议|下单|立即交易|"
    r"\b(?:buy|sell|add position|reduce position|clear position|broker|order|"
    r"trade execution|trading advice|investment advice|target[\s-]?price|"
    r"stop[\s-]?loss|take[\s-]?profit|guaranteed return|"
    r"live\s+(?:quote|data|market|pricing)|real[\s-]?time|realtime)\b|"
    r"provider|fallback|internal|diagnostic|debug|traceback|reasoncode|trustlevel|"
    r"sourcetype|raw|token|secret|cookie|session|api[_-]?key|https?://|/users/|/tmp/",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def contains_forbidden_homepage_rates_pricing_text(value: Any) -> bool:
    text = str(value or "")
    return bool(text and _FORBIDDEN_RATES_PRICING_RE.search(text))


def ensure_homepage_rates_pricing_text(
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
    if contains_forbidden_homepage_rates_pricing_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        if contains_forbidden_homepage_rates_pricing_text(value):
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


class _HomepageRatesPricingBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageRatesPricingModeSummary(_HomepageRatesPricingBase):
    mode: HomepageRatesPricingMode
    label: str
    fedFuturesPricing: HomepageRatesPricingAuthority
    oisPricing: HomepageRatesPricingAuthority
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_rates_pricing_text(
            value,
            field_name="pricingMode.label",
            max_length=40,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_rates_pricing_text(
            value,
            field_name="pricingMode.summary",
            max_length=180,
        )

    @model_validator(mode="after")
    def _validate_pricing_mode(self) -> "HomepageRatesPricingModeSummary":
        if self.mode == "proxy_only" and (
            self.fedFuturesPricing != "unavailable" or self.oisPricing != "unavailable"
        ):
            raise ValueError("proxy_only pricingMode cannot expose direct futures or OIS pricing")
        return self


class HomepageRatesPolicyExpectation(_HomepageRatesPricingBase):
    bias: HomepageRatesPolicyBias
    label: str
    pricingAuthority: HomepageRatesPricingAuthority
    observation: str
    missingEvidence: list[str] = Field(..., min_length=1, max_length=4)

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_rates_pricing_text(
            value,
            field_name="policyExpectation.label",
            max_length=48,
        )

    @field_validator("observation")
    @classmethod
    def _validate_observation(cls, value: str) -> str:
        return ensure_homepage_rates_pricing_text(
            value,
            field_name="policyExpectation.observation",
            max_length=180,
        )

    @field_validator("missingEvidence")
    @classmethod
    def _validate_missing_evidence(cls, value: list[str]) -> list[str]:
        return [
            ensure_homepage_rates_pricing_text(
                item,
                field_name="policyExpectation.missingEvidence",
                max_length=96,
            )
            for item in value
        ]


class HomepageRatesSignal(_HomepageRatesPricingBase):
    state: HomepageRatesSignalState
    label: str
    observation: str
    marketBackdropImplication: str
    evidenceQuality: HomepageRatesEvidenceQualityState

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_rates_pricing_text(
            value,
            field_name="ratesSignal.label",
            max_length=48,
        )

    @field_validator("observation", "marketBackdropImplication")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return ensure_homepage_rates_pricing_text(
            value,
            field_name="ratesSignal.text",
            max_length=180,
        )


class HomepageRatesAssetImplication(_HomepageRatesPricingBase):
    state: HomepageRatesSignalState
    label: str
    observation: str
    sensitivity: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_rates_pricing_text(
            value,
            field_name="assetImplication.label",
            max_length=48,
        )

    @field_validator("observation", "sensitivity")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return ensure_homepage_rates_pricing_text(
            value,
            field_name="assetImplication.text",
            max_length=180,
        )


class HomepageRatesQualitySummary(_HomepageRatesPricingBase):
    state: HomepageRatesEvidenceQualityState | HomepageRatesDataQualityState
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_rates_pricing_text(value, field_name="quality.label", max_length=48)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_rates_pricing_text(
            value,
            field_name="quality.summary",
            max_length=180,
        )


class HomepageRatesPricingSnapshot(_HomepageRatesPricingBase):
    schemaVersion: str = Field(default=HOMEPAGE_RATES_PRICING_SCHEMA_VERSION)
    asOf: str = Field(default=HOMEPAGE_RATES_PRICING_DEFAULT_AS_OF, min_length=1, max_length=40)
    pricingMode: HomepageRatesPricingModeSummary
    policyExpectation: HomepageRatesPolicyExpectation
    ratePathSummary: HomepageRatesSignal
    curveSignal: HomepageRatesSignal
    realYieldSignal: HomepageRatesSignal
    inflationPressure: HomepageRatesSignal
    equityImplication: HomepageRatesAssetImplication
    dollarImplication: HomepageRatesAssetImplication
    goldImplication: HomepageRatesAssetImplication
    watchPoints: list[str] = Field(..., min_length=1, max_length=8)
    evidenceQuality: HomepageRatesQualitySummary
    dataQuality: HomepageRatesQualitySummary
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=100)

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        return ensure_homepage_rates_pricing_text(value, field_name="asOf", max_length=40)

    @field_validator("watchPoints")
    @classmethod
    def _validate_watch_points(cls, value: list[str]) -> list[str]:
        return [
            ensure_homepage_rates_pricing_text(
                item,
                field_name="watchPoints",
                max_length=72,
            )
            for item in value
        ]

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_homepage_rates_pricing_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=100,
        )

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepageRatesPricingSnapshot":
        if self.schemaVersion != HOMEPAGE_RATES_PRICING_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        if self.pricingMode.mode == "proxy_only" and self.policyExpectation.pricingAuthority != "proxy_only":
            raise ValueError("policyExpectation must remain proxy_only when pricingMode is proxy_only")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_RATES_PRICING_DEFAULT_AS_OF",
    "HOMEPAGE_RATES_PRICING_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_RATES_PRICING_SCHEMA_VERSION",
    "HomepageRatesAssetImplication",
    "HomepageRatesDataQualityState",
    "HomepageRatesEvidenceQualityState",
    "HomepageRatesPolicyBias",
    "HomepageRatesPolicyExpectation",
    "HomepageRatesPricingAuthority",
    "HomepageRatesPricingMode",
    "HomepageRatesPricingModeSummary",
    "HomepageRatesPricingSnapshot",
    "HomepageRatesQualitySummary",
    "HomepageRatesSignal",
    "HomepageRatesSignalState",
    "contains_forbidden_homepage_rates_pricing_text",
    "ensure_homepage_rates_pricing_text",
]
