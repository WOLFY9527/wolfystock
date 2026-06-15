# -*- coding: utf-8 -*-
"""Standalone geopolitical and commodity risk contract for the homepage cockpit."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HomepageGeopoliticalCommodityRiskState = Literal[
    "rising",
    "falling",
    "elevated",
    "divergent",
    "monitoring",
    "mixed",
    "unavailable",
]
HomepageGeopoliticalCommodityRiskEvidenceQuality = Literal[
    "scenario_monitoring",
    "needs_confirmation",
    "limited",
    "unavailable",
]
HomepageGeopoliticalCommodityRiskDataQualityStatus = Literal[
    "sample_proxy",
    "no_evidence",
    "unavailable",
]

HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_SCHEMA_VERSION = (
    "homepage_geopolitical_commodity_risk_v1"
)
HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_NO_ADVICE_DISCLOSURE = (
    "For homepage scenario monitoring only; not a personalized decision basis."
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


def contains_forbidden_geopolitical_commodity_risk_text(value: Any) -> bool:
    text = str(value or "")
    return bool(text and _FORBIDDEN_TEXT_RE.search(text))


def ensure_geopolitical_commodity_risk_text(
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
    if contains_forbidden_geopolitical_commodity_risk_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        ensure_geopolitical_commodity_risk_text(value, field_name=field_name, max_length=260)
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


class _HomepageGeopoliticalCommodityRiskBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageGeopoliticalCommodityRiskDataQuality(_HomepageGeopoliticalCommodityRiskBase):
    status: HomepageGeopoliticalCommodityRiskDataQualityStatus
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_geopolitical_commodity_risk_text(
            value,
            field_name="dataQuality.label",
            max_length=48,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_geopolitical_commodity_risk_text(
            value,
            field_name="dataQuality.summary",
            max_length=180,
        )


class HomepageGeopoliticalCommodityRiskScenario(_HomepageGeopoliticalCommodityRiskBase):
    scenarioName: str
    researchLanguage: str
    affectedAssets: list[str] = Field(..., min_length=1, max_length=8)
    affectedSectors: list[str] = Field(..., min_length=1, max_length=8)
    affectedThemes: list[str] = Field(..., min_length=1, max_length=8)
    evidenceQuality: HomepageGeopoliticalCommodityRiskEvidenceQuality
    dataQuality: HomepageGeopoliticalCommodityRiskDataQualityStatus

    @field_validator("scenarioName")
    @classmethod
    def _validate_scenario_name(cls, value: str) -> str:
        return ensure_geopolitical_commodity_risk_text(
            value,
            field_name="scenarioName",
            max_length=88,
        )

    @field_validator("researchLanguage")
    @classmethod
    def _validate_research_language(cls, value: str) -> str:
        return ensure_geopolitical_commodity_risk_text(
            value,
            field_name="researchLanguage",
            max_length=220,
        )

    @field_validator("affectedAssets", "affectedSectors", "affectedThemes")
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_geopolitical_commodity_risk_text(
                item,
                field_name="scenario.listItem",
                max_length=80,
            )
            for item in value
        ]


class HomepageGeopoliticalCommodityRiskVector(_HomepageGeopoliticalCommodityRiskBase):
    key: str = Field(..., min_length=1, max_length=48)
    label: str
    state: HomepageGeopoliticalCommodityRiskState
    summary: str
    monitoringScenarios: list[HomepageGeopoliticalCommodityRiskScenario] = Field(
        ...,
        min_length=1,
        max_length=4,
    )
    confirmingSignals: list[str] = Field(..., min_length=1, max_length=5)
    invalidatingSignals: list[str] = Field(..., min_length=1, max_length=5)
    evidenceQuality: HomepageGeopoliticalCommodityRiskEvidenceQuality
    dataQuality: HomepageGeopoliticalCommodityRiskDataQualityStatus

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_geopolitical_commodity_risk_text(value, field_name="vector.label", max_length=64)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_geopolitical_commodity_risk_text(
            value,
            field_name="vector.summary",
            max_length=180,
        )

    @field_validator("confirmingSignals", "invalidatingSignals")
    @classmethod
    def _validate_signal_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_geopolitical_commodity_risk_text(
                item,
                field_name="vector.signal",
                max_length=140,
            )
            for item in value
        ]


class HomepageGeopoliticalCommodityRiskSnapshot(_HomepageGeopoliticalCommodityRiskBase):
    schemaVersion: str = Field(default=HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_SCHEMA_VERSION)
    asOf: str = Field(
        default=HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_DEFAULT_AS_OF,
        min_length=1,
        max_length=40,
    )
    riskWindow: str
    geopoliticalRiskPremium: HomepageGeopoliticalCommodityRiskVector
    oilRiskPremium: HomepageGeopoliticalCommodityRiskVector
    safeHavenDemand: HomepageGeopoliticalCommodityRiskVector
    shippingRisk: HomepageGeopoliticalCommodityRiskVector
    commodityPressure: HomepageGeopoliticalCommodityRiskVector
    affectedAssets: list[str] = Field(..., min_length=1, max_length=16)
    affectedSectors: list[str] = Field(..., min_length=1, max_length=16)
    affectedThemes: list[str] = Field(..., min_length=1, max_length=16)
    confirmingSignals: list[str] = Field(..., min_length=1, max_length=8)
    invalidatingSignals: list[str] = Field(..., min_length=1, max_length=8)
    watchPoints: list[str] = Field(..., min_length=1, max_length=10)
    evidenceQuality: HomepageGeopoliticalCommodityRiskEvidenceQuality
    dataQuality: HomepageGeopoliticalCommodityRiskDataQuality
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=100)

    @field_validator("asOf", "riskWindow")
    @classmethod
    def _validate_short_text(cls, value: str) -> str:
        return ensure_geopolitical_commodity_risk_text(
            value,
            field_name="snapshot.shortText",
            max_length=80,
        )

    @field_validator("affectedAssets", "affectedSectors", "affectedThemes")
    @classmethod
    def _validate_affected_lists(cls, value: list[str]) -> list[str]:
        return [
            ensure_geopolitical_commodity_risk_text(
                item,
                field_name="snapshot.affectedList",
                max_length=88,
            )
            for item in value
        ]

    @field_validator("confirmingSignals", "invalidatingSignals", "watchPoints")
    @classmethod
    def _validate_signal_lists(cls, value: list[str]) -> list[str]:
        return [
            ensure_geopolitical_commodity_risk_text(
                item,
                field_name="snapshot.signal",
                max_length=150,
            )
            for item in value
        ]

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_geopolitical_commodity_risk_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=100,
        )

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepageGeopoliticalCommodityRiskSnapshot":
        if self.schemaVersion != HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_DEFAULT_AS_OF",
    "HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_SCHEMA_VERSION",
    "HomepageGeopoliticalCommodityRiskDataQuality",
    "HomepageGeopoliticalCommodityRiskDataQualityStatus",
    "HomepageGeopoliticalCommodityRiskEvidenceQuality",
    "HomepageGeopoliticalCommodityRiskScenario",
    "HomepageGeopoliticalCommodityRiskSnapshot",
    "HomepageGeopoliticalCommodityRiskState",
    "HomepageGeopoliticalCommodityRiskVector",
    "contains_forbidden_geopolitical_commodity_risk_text",
    "ensure_geopolitical_commodity_risk_text",
]
