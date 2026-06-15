# -*- coding: utf-8 -*-
"""Standalone Volatility Positioning contract for the homepage intelligence cockpit."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HomepageVolatilityRegimeState = Literal["calm", "elevated", "stressed", "mixed", "unavailable"]
HomepageVolatilityPressureState = Literal[
    "low",
    "moderate",
    "elevated",
    "stressed",
    "mixed",
    "unavailable",
]
HomepageVolatilityAuthorityState = Literal["proxy_only", "unavailable", "no_evidence"]
HomepageVolatilityRiskAppetiteState = Literal[
    "supportive",
    "neutral",
    "pressure",
    "mixed",
    "unavailable",
]
HomepageVolatilityEvidenceQualityState = Literal[
    "proxy_observation",
    "needs_confirmation",
    "mixed",
    "unavailable",
    "no_evidence",
]
HomepageVolatilityDataQualityState = Literal[
    "deterministic",
    "partial",
    "unavailable",
    "no_evidence",
]

HOMEPAGE_VOLATILITY_POSITIONING_SCHEMA_VERSION = "homepage_volatility_positioning_v1"
HOMEPAGE_VOLATILITY_POSITIONING_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_VOLATILITY_POSITIONING_NO_ADVICE_DISCLOSURE = (
    "仅用于波动压力与期权需求代理观察，不作为个性化决策依据。"
)

_FORBIDDEN_VOLATILITY_POSITIONING_RE = re.compile(
    r"交易指令|交易执行|交易建议|买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|"
    r"收益预测|AI推荐|智能选股|投资建议|下单|立即交易|"
    r"\b(?:buy|sell|add position|reduce position|clear position|broker|order|"
    r"trade execution|trading advice|investment advice|target[\s-]?price|"
    r"stop[\s-]?loss|take[\s-]?profit|guaranteed return|"
    r"live\s+(?:option|options|quote|data|market|pricing)|real[\s-]?time|realtime)\b|"
    r"provider|fallback|internal|diagnostic|debug|traceback|reasoncode|trustlevel|"
    r"sourcetype|raw|token|secret|cookie|session|api[_-]?key|https?://|"
    r"/users/|/tmp/|/api/v",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def contains_forbidden_homepage_volatility_positioning_text(value: Any) -> bool:
    text = str(value or "")
    return bool(text and _FORBIDDEN_VOLATILITY_POSITIONING_RE.search(text))


def ensure_homepage_volatility_positioning_text(
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
    if contains_forbidden_homepage_volatility_positioning_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        if contains_forbidden_homepage_volatility_positioning_text(value):
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


class _HomepageVolatilityPositioningBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageVolatilityRegimeSummary(_HomepageVolatilityPositioningBase):
    state: HomepageVolatilityRegimeState
    label: str
    summary: str
    evidenceQuality: HomepageVolatilityEvidenceQualityState

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_volatility_positioning_text(
            value,
            field_name="volatilityRegime.label",
            max_length=48,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_volatility_positioning_text(
            value,
            field_name="volatilityRegime.summary",
            max_length=180,
        )


class HomepageVolatilityPressureSummary(_HomepageVolatilityPositioningBase):
    pressure: HomepageVolatilityPressureState
    label: str
    observation: str
    authority: HomepageVolatilityAuthorityState
    marketBackdropImplication: str
    evidenceQuality: HomepageVolatilityEvidenceQualityState

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_volatility_positioning_text(
            value,
            field_name="volatilityPressure.label",
            max_length=48,
        )

    @field_validator("observation", "marketBackdropImplication")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return ensure_homepage_volatility_positioning_text(
            value,
            field_name="volatilityPressure.text",
            max_length=180,
        )


class HomepageOptionsDemandProxy(_HomepageVolatilityPositioningBase):
    authority: HomepageVolatilityAuthorityState
    optionChainAuthority: HomepageVolatilityAuthorityState
    label: str
    observation: str
    proxySignals: list[str] = Field(..., min_length=1, max_length=6)
    missingEvidence: list[str] = Field(..., min_length=1, max_length=6)
    evidenceQuality: HomepageVolatilityEvidenceQualityState

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_volatility_positioning_text(
            value,
            field_name="optionsDemandProxy.label",
            max_length=48,
        )

    @field_validator("observation")
    @classmethod
    def _validate_observation(cls, value: str) -> str:
        return ensure_homepage_volatility_positioning_text(
            value,
            field_name="optionsDemandProxy.observation",
            max_length=180,
        )

    @field_validator("proxySignals", "missingEvidence")
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_homepage_volatility_positioning_text(
                item,
                field_name="optionsDemandProxy.list",
                max_length=96,
            )
            for item in value
        ]

    @model_validator(mode="after")
    def _validate_proxy_authority(self) -> "HomepageOptionsDemandProxy":
        if self.authority == "proxy_only" and self.optionChainAuthority != "unavailable":
            raise ValueError("proxy_only optionsDemandProxy cannot expose option-chain authority")
        if self.authority == "proxy_only" and not self.missingEvidence:
            raise ValueError("proxy_only optionsDemandProxy requires missingEvidence")
        return self


class HomepageVolatilityRiskAppetiteImplication(_HomepageVolatilityPositioningBase):
    state: HomepageVolatilityRiskAppetiteState
    label: str
    observation: str
    implication: str
    evidenceQuality: HomepageVolatilityEvidenceQualityState

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_volatility_positioning_text(
            value,
            field_name="riskAppetiteImplication.label",
            max_length=48,
        )

    @field_validator("observation", "implication")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return ensure_homepage_volatility_positioning_text(
            value,
            field_name="riskAppetiteImplication.text",
            max_length=180,
        )


class HomepageVolatilityContradictionSignal(_HomepageVolatilityPositioningBase):
    key: str = Field(..., min_length=1, max_length=40)
    label: str
    observation: str
    whyItMatters: str
    evidenceQuality: HomepageVolatilityEvidenceQualityState

    @field_validator("key")
    @classmethod
    def _validate_key(cls, value: str) -> str:
        return ensure_homepage_volatility_positioning_text(
            value,
            field_name="contradictionSignals.key",
            max_length=40,
        )

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_volatility_positioning_text(
            value,
            field_name="contradictionSignals.label",
            max_length=48,
        )

    @field_validator("observation", "whyItMatters")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return ensure_homepage_volatility_positioning_text(
            value,
            field_name="contradictionSignals.text",
            max_length=180,
        )


class HomepageVolatilityQualitySummary(_HomepageVolatilityPositioningBase):
    state: HomepageVolatilityEvidenceQualityState | HomepageVolatilityDataQualityState
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_volatility_positioning_text(
            value,
            field_name="quality.label",
            max_length=48,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_volatility_positioning_text(
            value,
            field_name="quality.summary",
            max_length=180,
        )


class HomepageVolatilityDataQuality(_HomepageVolatilityPositioningBase):
    state: HomepageVolatilityDataQualityState
    label: str
    available: bool
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_volatility_positioning_text(
            value,
            field_name="dataQuality.label",
            max_length=48,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_volatility_positioning_text(
            value,
            field_name="dataQuality.summary",
            max_length=180,
        )


class HomepageVolatilityPositioningSnapshot(_HomepageVolatilityPositioningBase):
    schemaVersion: str = Field(default=HOMEPAGE_VOLATILITY_POSITIONING_SCHEMA_VERSION)
    asOf: str = Field(default=HOMEPAGE_VOLATILITY_POSITIONING_DEFAULT_AS_OF, min_length=1, max_length=40)
    volatilityRegime: HomepageVolatilityRegimeSummary
    equityVolatility: HomepageVolatilityPressureSummary
    rateVolatility: HomepageVolatilityPressureSummary
    skewOrTailRisk: HomepageVolatilityPressureSummary
    optionsDemandProxy: HomepageOptionsDemandProxy
    riskAppetiteImplication: HomepageVolatilityRiskAppetiteImplication
    contradictionSignals: list[HomepageVolatilityContradictionSignal] = Field(
        default_factory=list,
        max_length=6,
    )
    watchPoints: list[str] = Field(..., min_length=1, max_length=8)
    evidenceQuality: HomepageVolatilityQualitySummary
    dataQuality: HomepageVolatilityDataQuality
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=100)

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        return ensure_homepage_volatility_positioning_text(value, field_name="asOf", max_length=40)

    @field_validator("watchPoints")
    @classmethod
    def _validate_watch_points(cls, value: list[str]) -> list[str]:
        return [
            ensure_homepage_volatility_positioning_text(
                item,
                field_name="watchPoints",
                max_length=96,
            )
            for item in value
        ]

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_homepage_volatility_positioning_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=100,
        )

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepageVolatilityPositioningSnapshot":
        if self.schemaVersion != HOMEPAGE_VOLATILITY_POSITIONING_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        if self.optionsDemandProxy.authority != "proxy_only":
            raise ValueError("optionsDemandProxy must remain proxy_only for this standalone contract")
        if self.optionsDemandProxy.optionChainAuthority != "unavailable":
            raise ValueError("proxy_only snapshot cannot expose option-chain authority")
        if self.evidenceQuality.state not in {"proxy_observation", "needs_confirmation", "mixed"}:
            raise ValueError("proxy_only snapshot requires proxy evidence quality")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_VOLATILITY_POSITIONING_DEFAULT_AS_OF",
    "HOMEPAGE_VOLATILITY_POSITIONING_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_VOLATILITY_POSITIONING_SCHEMA_VERSION",
    "HomepageOptionsDemandProxy",
    "HomepageVolatilityAuthorityState",
    "HomepageVolatilityContradictionSignal",
    "HomepageVolatilityDataQuality",
    "HomepageVolatilityDataQualityState",
    "HomepageVolatilityEvidenceQualityState",
    "HomepageVolatilityPositioningSnapshot",
    "HomepageVolatilityPressureState",
    "HomepageVolatilityPressureSummary",
    "HomepageVolatilityRegimeState",
    "HomepageVolatilityRegimeSummary",
    "HomepageVolatilityRiskAppetiteImplication",
    "HomepageVolatilityRiskAppetiteState",
    "HomepageVolatilityQualitySummary",
    "contains_forbidden_homepage_volatility_positioning_text",
    "ensure_homepage_volatility_positioning_text",
]
