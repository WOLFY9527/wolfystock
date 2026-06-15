# -*- coding: utf-8 -*-
"""Standalone safe contract for homepage cross-asset indicators."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CrossAssetPublicState = Literal[
    "ready",
    "partial",
    "delayed",
    "cached",
    "no_evidence",
    "unavailable",
]
CrossAssetEvidenceState = Literal[
    "strong",
    "medium",
    "weak",
    "needs_confirmation",
    "conflicting",
]
CrossAssetGroupKey = Literal[
    "volatility",
    "rates",
    "dollar",
    "commodities",
    "crypto",
    "creditProxy",
    "equityStyle",
]

HOMEPAGE_CROSS_ASSET_INDICATORS_SCHEMA_VERSION = "homepage_cross_asset_indicators_v1"
HOMEPAGE_CROSS_ASSET_INDICATORS_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_CROSS_ASSET_INDICATORS_NO_ADVICE_DISCLOSURE = (
    "仅用于市场背景观察与研究线索整理，不作为个性化决策依据。"
)

_FORBIDDEN_TEXT_RE = re.compile(
    r"交易指令|交易执行|交易建议|买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|"
    r"收益预测|AI推荐|智能选股|投资建议|下单|"
    r"\b(?:buy|sell|add|reduce|broker|order|trade\s+execution|trading\s+advice|"
    r"target[\s-]?price|stop[\s-]?loss|take[\s-]?profit|guaranteed|"
    r"live\s+(?:data|quote|market)|real[\s-]?time|realtime)\b|"
    r"实时数据|实时行情|provider|fallback|diagnostic|debug|traceback|reasoncode|"
    r"trustlevel|sourcetype|raw|token|secret|cookie|session|api[_-]?key|https?://|"
    r"/users/|/tmp/",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def contains_forbidden_cross_asset_indicators_text(value: Any) -> bool:
    text = str(value or "")
    return bool(text and _FORBIDDEN_TEXT_RE.search(text))


def ensure_cross_asset_indicators_text(
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
    if contains_forbidden_cross_asset_indicators_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        if contains_forbidden_cross_asset_indicators_text(value):
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


class _CrossAssetIndicatorsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CrossAssetIndicator(_CrossAssetIndicatorsModel):
    key: str = Field(..., min_length=1, max_length=48)
    label: str
    assetGroup: CrossAssetGroupKey
    valueLabel: str
    state: CrossAssetPublicState
    evidenceState: CrossAssetEvidenceState
    description: str
    interpretation: str
    watchPoints: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_cross_asset_indicators_text(
            value,
            field_name="indicator.label",
            max_length=48,
        )

    @field_validator("valueLabel")
    @classmethod
    def _validate_value_label(cls, value: str) -> str:
        return ensure_cross_asset_indicators_text(
            value,
            field_name="indicator.valueLabel",
            max_length=48,
        )

    @field_validator("description", "interpretation")
    @classmethod
    def _validate_summary_text(cls, value: str) -> str:
        return ensure_cross_asset_indicators_text(
            value,
            field_name="indicator.text",
            max_length=150,
        )

    @field_validator("watchPoints")
    @classmethod
    def _validate_watch_points(cls, value: list[str]) -> list[str]:
        return [
            ensure_cross_asset_indicators_text(
                item,
                field_name="indicator.watchPoints",
                max_length=64,
            )
            for item in value
        ]


class CrossAssetGroupSummary(_CrossAssetIndicatorsModel):
    key: CrossAssetGroupKey
    label: str
    state: CrossAssetPublicState
    evidenceState: CrossAssetEvidenceState
    indicatorKeys: list[str] = Field(..., min_length=1, max_length=4)
    summary: str
    watchPoints: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_cross_asset_indicators_text(
            value,
            field_name="assetGroup.label",
            max_length=48,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_cross_asset_indicators_text(
            value,
            field_name="assetGroup.summary",
            max_length=160,
        )

    @field_validator("indicatorKeys")
    @classmethod
    def _validate_indicator_keys(cls, value: list[str]) -> list[str]:
        return [
            ensure_cross_asset_indicators_text(
                item,
                field_name="assetGroup.indicatorKeys",
                max_length=48,
            )
            for item in value
        ]

    @field_validator("watchPoints")
    @classmethod
    def _validate_watch_points(cls, value: list[str]) -> list[str]:
        return [
            ensure_cross_asset_indicators_text(
                item,
                field_name="assetGroup.watchPoints",
                max_length=64,
            )
            for item in value
        ]


class CrossAssetContradiction(_CrossAssetIndicatorsModel):
    key: str = Field(..., min_length=1, max_length=48)
    label: str
    observation: str
    whyItMatters: str
    evidenceState: CrossAssetEvidenceState

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_cross_asset_indicators_text(
            value,
            field_name="contradiction.label",
            max_length=48,
        )

    @field_validator("observation", "whyItMatters")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return ensure_cross_asset_indicators_text(
            value,
            field_name="contradiction.text",
            max_length=150,
        )


class CrossAssetQualitySummary(_CrossAssetIndicatorsModel):
    state: CrossAssetEvidenceState
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_cross_asset_indicators_text(
            value,
            field_name="evidenceQuality.label",
            max_length=48,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_cross_asset_indicators_text(
            value,
            field_name="evidenceQuality.summary",
            max_length=160,
        )


class CrossAssetDataQuality(_CrossAssetIndicatorsModel):
    state: CrossAssetPublicState
    label: str
    available: bool
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_cross_asset_indicators_text(
            value,
            field_name="dataQuality.label",
            max_length=48,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_cross_asset_indicators_text(
            value,
            field_name="dataQuality.summary",
            max_length=160,
        )


class HomepageCrossAssetIndicatorsSnapshot(_CrossAssetIndicatorsModel):
    schemaVersion: str = Field(default=HOMEPAGE_CROSS_ASSET_INDICATORS_SCHEMA_VERSION)
    asOf: str = Field(default=HOMEPAGE_CROSS_ASSET_INDICATORS_DEFAULT_AS_OF)
    indicators: list[CrossAssetIndicator] = Field(..., min_length=1, max_length=16)
    assetGroups: list[CrossAssetGroupSummary] = Field(..., min_length=1, max_length=8)
    volatility: CrossAssetGroupSummary
    rates: CrossAssetGroupSummary
    dollar: CrossAssetGroupSummary
    commodities: CrossAssetGroupSummary
    crypto: CrossAssetGroupSummary
    creditProxy: CrossAssetGroupSummary
    equityStyle: CrossAssetGroupSummary
    summary: str
    contradictions: list[CrossAssetContradiction] = Field(default_factory=list, max_length=6)
    watchPoints: list[str] = Field(..., min_length=1, max_length=8)
    evidenceQuality: CrossAssetQualitySummary
    dataQuality: CrossAssetDataQuality
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=100)

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        return ensure_cross_asset_indicators_text(value, field_name="asOf", max_length=40)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_cross_asset_indicators_text(value, field_name="summary", max_length=180)

    @field_validator("watchPoints")
    @classmethod
    def _validate_watch_points(cls, value: list[str]) -> list[str]:
        return [
            ensure_cross_asset_indicators_text(item, field_name="watchPoints", max_length=72)
            for item in value
        ]

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_cross_asset_indicators_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=100,
        )

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepageCrossAssetIndicatorsSnapshot":
        if self.schemaVersion != HOMEPAGE_CROSS_ASSET_INDICATORS_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        indicator_keys = {item.key for item in self.indicators}
        for group in (
            *self.assetGroups,
            self.volatility,
            self.rates,
            self.dollar,
            self.commodities,
            self.crypto,
            self.creditProxy,
            self.equityStyle,
        ):
            unknown = set(group.indicatorKeys) - indicator_keys
            if unknown:
                raise ValueError(f"{group.key} references unknown indicators")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "CrossAssetContradiction",
    "CrossAssetDataQuality",
    "CrossAssetEvidenceState",
    "CrossAssetGroupKey",
    "CrossAssetGroupSummary",
    "CrossAssetIndicator",
    "CrossAssetPublicState",
    "CrossAssetQualitySummary",
    "HOMEPAGE_CROSS_ASSET_INDICATORS_DEFAULT_AS_OF",
    "HOMEPAGE_CROSS_ASSET_INDICATORS_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_CROSS_ASSET_INDICATORS_SCHEMA_VERSION",
    "HomepageCrossAssetIndicatorsSnapshot",
    "contains_forbidden_cross_asset_indicators_text",
    "ensure_cross_asset_indicators_text",
]
