# -*- coding: utf-8 -*-
"""Standalone safe contract for homepage liquidity and credit stress."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


LiquidityCreditConditionState = Literal["supportive", "neutral", "stressful"]
LiquidityCreditEvidenceState = Literal[
    "strong",
    "medium",
    "weak",
    "needs_confirmation",
    "proxy_only",
]
LiquidityCreditDataQualityState = Literal["ready", "partial", "no_evidence", "unavailable"]

HOMEPAGE_LIQUIDITY_CREDIT_SCHEMA_VERSION = "homepage_liquidity_credit_v1"
HOMEPAGE_LIQUIDITY_CREDIT_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_LIQUIDITY_CREDIT_NO_ADVICE_DISCLOSURE = (
    "仅用于首页流动性与信用压力观察，不构成个性化建议。"
)

_FORBIDDEN_TEXT_RE = re.compile(
    r"交易指令|交易执行|交易建议|买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|"
    r"收益预测|AI推荐|智能选股|投资建议|下单|立即交易|权威|"
    r"\b(?:buy|sell|broker|order|trade[\s-]?execution|trading[\s-]?advice|"
    r"investment[\s-]?advice|target[\s-]?price|stop[\s-]?loss|take[\s-]?profit|"
    r"authoritative\s+credit\s+spread|actual\s+credit\s+spread|live\s+credit\s+spread|"
    r"official\s+credit\s+spread)\b|"
    r"provider|fallback|internal|diagnostic|debug|traceback|reasoncode|trustlevel|"
    r"sourcetype|raw|token|secret|cookie|session|api[_-]?key|https?://|/users/|/tmp/",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def contains_forbidden_homepage_liquidity_credit_text(value: Any) -> bool:
    text = str(value or "")
    return bool(text and _FORBIDDEN_TEXT_RE.search(text))


def ensure_homepage_liquidity_credit_text(
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
    if contains_forbidden_homepage_liquidity_credit_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        ensure_homepage_liquidity_credit_text(value, field_name=field_name, max_length=220)
        return
    if isinstance(value, BaseModel):
        _assert_safe_nested_text(value.model_dump(mode="json"), field_name=field_name)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "schemaVersion":
                continue
            _assert_safe_nested_text(item, field_name=f"{field_name}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_safe_nested_text(item, field_name=f"{field_name}[{index}]")


class _HomepageLiquidityCreditBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageLiquidityCreditCondition(_HomepageLiquidityCreditBase):
    state: LiquidityCreditConditionState
    evidenceState: LiquidityCreditEvidenceState
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_liquidity_credit_text(
            value,
            field_name="condition.label",
            max_length=40,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_liquidity_credit_text(
            value,
            field_name="condition.summary",
            max_length=160,
        )


class HomepageLiquidityCreditProxy(_HomepageLiquidityCreditBase):
    key: str = Field(..., min_length=1, max_length=48)
    label: str
    state: LiquidityCreditConditionState
    evidenceState: LiquidityCreditEvidenceState
    dataQuality: LiquidityCreditDataQualityState
    isProxy: bool
    summary: str
    interpretation: str

    @field_validator("key")
    @classmethod
    def _validate_key(cls, value: str) -> str:
        return ensure_homepage_liquidity_credit_text(
            value,
            field_name="proxy.key",
            max_length=48,
        )

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_liquidity_credit_text(
            value,
            field_name="proxy.label",
            max_length=48,
        )

    @field_validator("summary", "interpretation")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return ensure_homepage_liquidity_credit_text(
            value,
            field_name="proxy.text",
            max_length=170,
        )


class HomepageLiquidityCreditRiskAssetImplication(_HomepageLiquidityCreditBase):
    state: LiquidityCreditConditionState
    label: str
    summary: str
    observation: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_liquidity_credit_text(
            value,
            field_name="riskAssetImplication.label",
            max_length=48,
        )

    @field_validator("summary", "observation")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return ensure_homepage_liquidity_credit_text(
            value,
            field_name="riskAssetImplication.text",
            max_length=180,
        )


class HomepageLiquidityCreditEvidenceQuality(_HomepageLiquidityCreditBase):
    state: LiquidityCreditEvidenceState
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_liquidity_credit_text(
            value,
            field_name="evidenceQuality.label",
            max_length=48,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_liquidity_credit_text(
            value,
            field_name="evidenceQuality.summary",
            max_length=180,
        )


class HomepageLiquidityCreditDataQuality(_HomepageLiquidityCreditBase):
    state: LiquidityCreditDataQualityState
    label: str
    available: bool
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_homepage_liquidity_credit_text(
            value,
            field_name="dataQuality.label",
            max_length=48,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_homepage_liquidity_credit_text(
            value,
            field_name="dataQuality.summary",
            max_length=180,
        )


class HomepageLiquidityCreditSnapshot(_HomepageLiquidityCreditBase):
    schemaVersion: str = Field(default=HOMEPAGE_LIQUIDITY_CREDIT_SCHEMA_VERSION)
    asOf: str = Field(default=HOMEPAGE_LIQUIDITY_CREDIT_DEFAULT_AS_OF, min_length=1, max_length=40)
    liquidityCondition: HomepageLiquidityCreditCondition
    creditStressCondition: HomepageLiquidityCreditCondition
    fundingPressure: HomepageLiquidityCreditProxy
    highYieldProxy: HomepageLiquidityCreditProxy
    treasuryLiquidityProxy: HomepageLiquidityCreditProxy
    dollarLiquidity: HomepageLiquidityCreditProxy
    riskAssetImplication: HomepageLiquidityCreditRiskAssetImplication
    evidenceSummary: str
    missingEvidence: list[str] = Field(..., min_length=1, max_length=6)
    watchPoints: list[str] = Field(..., min_length=1, max_length=6)
    evidenceQuality: HomepageLiquidityCreditEvidenceQuality
    dataQuality: HomepageLiquidityCreditDataQuality
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=100)

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        return ensure_homepage_liquidity_credit_text(value, field_name="asOf", max_length=40)

    @field_validator("evidenceSummary")
    @classmethod
    def _validate_evidence_summary(cls, value: str) -> str:
        return ensure_homepage_liquidity_credit_text(
            value,
            field_name="evidenceSummary",
            max_length=200,
        )

    @field_validator("missingEvidence", "watchPoints")
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_homepage_liquidity_credit_text(
                item,
                field_name="snapshot.listItem",
                max_length=96,
            )
            for item in value
        ]

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_homepage_liquidity_credit_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=100,
        )

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepageLiquidityCreditSnapshot":
        if self.schemaVersion != HOMEPAGE_LIQUIDITY_CREDIT_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_LIQUIDITY_CREDIT_DEFAULT_AS_OF",
    "HOMEPAGE_LIQUIDITY_CREDIT_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_LIQUIDITY_CREDIT_SCHEMA_VERSION",
    "HomepageLiquidityCreditCondition",
    "HomepageLiquidityCreditDataQuality",
    "HomepageLiquidityCreditEvidenceQuality",
    "HomepageLiquidityCreditProxy",
    "HomepageLiquidityCreditRiskAssetImplication",
    "HomepageLiquidityCreditSnapshot",
    "LiquidityCreditConditionState",
    "LiquidityCreditDataQualityState",
    "LiquidityCreditEvidenceState",
    "contains_forbidden_homepage_liquidity_credit_text",
    "ensure_homepage_liquidity_credit_text",
]
