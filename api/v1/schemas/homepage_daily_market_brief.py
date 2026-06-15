# -*- coding: utf-8 -*-
"""Standalone daily market brief contract for the homepage intelligence cockpit."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


DailyMarketBriefEvidenceQuality = Literal["证据整理", "需要复核", "证据增强", "证据不足"]
DailyMarketBriefDataQuality = Literal["研究支持", "需要复核", "证据增强", "证据不足"]
DailyMarketBriefRiskTone = Literal["市场观察", "需要复核", "证据增强", "证据不足"]

DAILY_MARKET_BRIEF_SCHEMA_VERSION = "homepage_daily_market_brief_v1"
MAX_KEY_DRIVERS = 4
MAX_WATCH_POINTS = 4
MAX_INDEX_SUMMARIES = 3
MAX_LABEL_LENGTH = 24
MAX_SUMMARY_LENGTH = 96
MAX_TEXT_LENGTH = 140

FORBIDDEN_DAILY_MARKET_BRIEF_RE = re.compile(
    r"买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|收益预测|交易指令|交易建议|AI推荐|智能选股|"
    r"\b(?:broker|order|trade execution|buy now|sell now|target price|stop loss|take profit)\b|"
    r"traceback|provider|token|session_id|api[_-]?key|secret|reasoncode|trustlevel|sourcetype|"
    r"raw|debug|https?://|/users/|/tmp/",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def contains_forbidden_daily_market_brief_text(value: Any) -> bool:
    return bool(FORBIDDEN_DAILY_MARKET_BRIEF_RE.search(str(value or "")))


def ensure_daily_market_brief_text(value: Any, *, field_name: str, max_length: int) -> str:
    text = _WHITESPACE_RE.sub(" ", str(value or "").strip())
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds max_length={max_length}")
    if contains_forbidden_daily_market_brief_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostic content")
    return text


class _DailyMarketBriefModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_public_text(self):
        self._assert_safe_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self

    @classmethod
    def _assert_safe_text(cls, value: Any, *, field_name: str) -> None:
        if isinstance(value, str):
            if contains_forbidden_daily_market_brief_text(value):
                raise ValueError(f"{field_name} contains forbidden advice or diagnostic content")
            return
        if isinstance(value, dict):
            for key, item in value.items():
                cls._assert_safe_text(item, field_name=f"{field_name}.{key}")
            return
        if isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                cls._assert_safe_text(item, field_name=f"{field_name}[{index}]")


class DailyMarketBriefIndexSummary(_DailyMarketBriefModel):
    label: str
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_daily_market_brief_text(
            value,
            field_name="indexSummary.label",
            max_length=MAX_LABEL_LENGTH,
        )

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return ensure_daily_market_brief_text(
            value,
            field_name="indexSummary.summary",
            max_length=MAX_SUMMARY_LENGTH,
        )


class HomepageDailyMarketBriefResponse(_DailyMarketBriefModel):
    schemaVersion: Literal["homepage_daily_market_brief_v1"]
    asOf: str
    sessionLabel: str
    headline: str
    marketNarrative: str
    keyDrivers: list[str] = Field(min_length=1, max_length=MAX_KEY_DRIVERS)
    riskTone: DailyMarketBriefRiskTone
    indexSummary: list[DailyMarketBriefIndexSummary] = Field(
        min_length=1,
        max_length=MAX_INDEX_SUMMARIES,
    )
    breadthSummary: str
    liquiditySummary: str
    volatilitySummary: str
    ratesSummary: str
    dollarSummary: str
    crossAssetSummary: str
    todayWatchPoints: list[str] = Field(min_length=1, max_length=MAX_WATCH_POINTS)
    evidenceQuality: DailyMarketBriefEvidenceQuality
    dataQuality: DailyMarketBriefDataQuality
    noAdviceDisclosure: str

    @field_validator(
        "asOf",
        "sessionLabel",
        "headline",
        "marketNarrative",
        "breadthSummary",
        "liquiditySummary",
        "volatilitySummary",
        "ratesSummary",
        "dollarSummary",
        "crossAssetSummary",
        "noAdviceDisclosure",
    )
    @classmethod
    def _validate_text_field(cls, value: str) -> str:
        return ensure_daily_market_brief_text(
            value,
            field_name="dailyMarketBrief",
            max_length=MAX_TEXT_LENGTH,
        )

    @field_validator("keyDrivers", "todayWatchPoints")
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_daily_market_brief_text(
                item,
                field_name="dailyMarketBrief.listItem",
                max_length=MAX_SUMMARY_LENGTH,
            )
            for item in value
        ]


__all__ = [
    "DAILY_MARKET_BRIEF_SCHEMA_VERSION",
    "DailyMarketBriefDataQuality",
    "DailyMarketBriefEvidenceQuality",
    "DailyMarketBriefIndexSummary",
    "DailyMarketBriefRiskTone",
    "FORBIDDEN_DAILY_MARKET_BRIEF_RE",
    "HomepageDailyMarketBriefResponse",
    "contains_forbidden_daily_market_brief_text",
    "ensure_daily_market_brief_text",
]
