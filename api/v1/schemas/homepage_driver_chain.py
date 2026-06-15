# -*- coding: utf-8 -*-
"""Standalone safe contract for homepage macro driver chains."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HomepageDriverChainEvidenceQuality = Literal[
    "confirmed",
    "needs_confirmation",
    "mixed",
    "unavailable",
]
HomepageDriverChainDataQuality = Literal[
    "deterministic",
    "partial",
    "no_evidence",
    "unavailable",
]

HOMEPAGE_DRIVER_CHAIN_SCHEMA_VERSION = "homepage_driver_chain_v1"
HOMEPAGE_DRIVER_CHAIN_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_DRIVER_CHAIN_NO_ADVICE_DISCLOSURE = (
    "本合约仅用于首页宏观因果链观察与研究排序，不构成个性化建议。"
)

_FORBIDDEN_TEXT_RE = re.compile(
    r"交易指令|交易执行|交易建议|买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|"
    r"收益预测|AI推荐|智能选股|投资建议|下单|立即交易|"
    r"\b(?:buy|sell|broker|order|trade[\s-]?execution|trading[\s-]?advice|"
    r"investment[\s-]?advice|target[\s-]?price|stop[\s-]?loss|take[\s-]?profit)\b|"
    r"provider|fallback|internal|diagnostic|debug|traceback|reasoncode|trustlevel|"
    r"sourcetype|raw|token|secret|cookie|session|api[_-]?key|https?://|/users/",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def contains_forbidden_homepage_driver_chain_text(value: Any) -> bool:
    text = str(value or "")
    return bool(text and _FORBIDDEN_TEXT_RE.search(text))


def ensure_homepage_driver_chain_text(
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
    if contains_forbidden_homepage_driver_chain_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        ensure_homepage_driver_chain_text(value, field_name=field_name, max_length=240)
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


class _HomepageDriverChainBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageDriverChain(_HomepageDriverChainBase):
    key: str = Field(..., min_length=1, max_length=48)
    macroDriver: str
    marketMechanism: str
    riskRegimeImplication: str
    affectedAssets: list[str] = Field(..., min_length=1, max_length=6)
    affectedSectors: list[str] = Field(..., min_length=1, max_length=6)
    affectedThemes: list[str] = Field(..., min_length=1, max_length=6)
    researchImplication: str
    confirmingEvidence: list[str] = Field(..., min_length=1, max_length=5)
    missingEvidence: list[str] = Field(..., min_length=1, max_length=5)
    contradiction: str
    evidenceQuality: HomepageDriverChainEvidenceQuality
    dataQuality: HomepageDriverChainDataQuality

    @field_validator(
        "macroDriver",
        "marketMechanism",
        "riskRegimeImplication",
        "researchImplication",
        "contradiction",
    )
    @classmethod
    def _validate_sentence(cls, value: str) -> str:
        return ensure_homepage_driver_chain_text(
            value,
            field_name="driverChain.text",
            max_length=180,
        )

    @field_validator(
        "affectedAssets",
        "affectedSectors",
        "affectedThemes",
        "confirmingEvidence",
        "missingEvidence",
    )
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_homepage_driver_chain_text(
                item,
                field_name="driverChain.listItem",
                max_length=96,
            )
            for item in value
        ]


class HomepageDriverChainSnapshot(_HomepageDriverChainBase):
    schemaVersion: str = Field(default=HOMEPAGE_DRIVER_CHAIN_SCHEMA_VERSION)
    asOf: str = Field(default=HOMEPAGE_DRIVER_CHAIN_DEFAULT_AS_OF, min_length=1, max_length=40)
    driverChains: list[HomepageDriverChain] = Field(..., min_length=1, max_length=8)
    evidenceQuality: HomepageDriverChainEvidenceQuality
    dataQuality: HomepageDriverChainDataQuality
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=100)

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        return ensure_homepage_driver_chain_text(value, field_name="asOf", max_length=40)

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_homepage_driver_chain_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=100,
        )

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepageDriverChainSnapshot":
        if self.schemaVersion != HOMEPAGE_DRIVER_CHAIN_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_DRIVER_CHAIN_DEFAULT_AS_OF",
    "HOMEPAGE_DRIVER_CHAIN_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_DRIVER_CHAIN_SCHEMA_VERSION",
    "HomepageDriverChain",
    "HomepageDriverChainDataQuality",
    "HomepageDriverChainEvidenceQuality",
    "HomepageDriverChainSnapshot",
    "contains_forbidden_homepage_driver_chain_text",
    "ensure_homepage_driver_chain_text",
]
