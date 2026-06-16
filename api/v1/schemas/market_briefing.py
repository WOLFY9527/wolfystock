# -*- coding: utf-8 -*-
"""Typed consumer-safe contract for the market briefing endpoint."""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MARKET_OVERVIEW_BRIEFING_SCHEMA_VERSION = "market_overview_briefing_v1"
DataQualityState = Literal["ready", "delayed", "cached", "partial", "no_evidence", "unavailable"]
FreshnessState = Literal[
    "live",
    "fresh",
    "cached",
    "delayed",
    "stale",
    "partial",
    "fallback",
    "mock",
    "synthetic",
    "unavailable",
    "error",
    "unknown",
]
BriefingSeverity = Literal["positive", "neutral", "warning", "risk"]
DegradedInputStatus = Literal["degraded", "unavailable"]

_INTERNAL_CODE_RE = re.compile(r"[a-z][a-z0-9]*_[a-z0-9_]+|[a-zA-Z]+:[a-zA-Z0-9_.-]+|=")
_FORBIDDEN_ADVICE_RE = re.compile(
    r"\b(buy|sell|hold|recommendation|target|stop|position\s*sizing)\b|买入|卖出|持有|目标价|止损|仓位",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def _safe_consumer_text(value: str, *, field_name: str, max_length: int) -> str:
    text = _WHITESPACE_RE.sub(" ", str(value or "").strip())
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds max_length={max_length}")
    if _INTERNAL_CODE_RE.search(text):
        raise ValueError(f"{field_name} contains internal-looking tokens")
    if _FORBIDDEN_ADVICE_RE.search(text):
        raise ValueError(f"{field_name} contains forbidden advice wording")
    return text


def _default_data_quality(payload: dict) -> dict[str, object]:
    freshness = str(payload.get("freshness") or "").strip().lower()
    if payload.get("isUnavailable") is True or freshness in {"unavailable", "error", "mock", "synthetic"}:
        state = "unavailable"
    elif payload.get("isPartial") is True or freshness == "partial":
        state = "partial"
    elif payload.get("isStale") is True or freshness in {"stale", "delayed"}:
        state = "delayed"
    elif payload.get("isFallback") is True or freshness in {"fallback", "cached"}:
        state = "cached"
    elif freshness in {"live", "fresh", "ready"}:
        state = "ready"
    else:
        state = "no_evidence"
    labels = {
        "ready": "正常",
        "delayed": "数据延迟",
        "cached": "使用缓存数据",
        "partial": "部分数据缺失",
        "no_evidence": "暂无证据",
        "unavailable": "暂不可用",
    }
    summaries = {
        "ready": "当前摘要可用于市场结构观察。",
        "delayed": "部分输入存在延迟，当前摘要仅保留观察用途。",
        "cached": "部分输入来自缓存或最近可用数据，当前摘要仅保留结构观察。",
        "partial": "关键输入仍不完整，当前摘要仅保留结构观察。",
        "no_evidence": "当前缺少足够输入，摘要仅保留结构观察。",
        "unavailable": "新鲜输入暂不可用，摘要仅保留结构观察。",
    }
    return {
        "state": state,
        "label": labels[state],
        "available": state == "ready",
        "summary": summaries[state],
    }


def _default_freshness_status(payload: dict) -> dict[str, str]:
    state = str(payload.get("freshness") or "").strip().lower() or "unknown"
    labels = {
        "live": "更新正常",
        "fresh": "更新正常",
        "cached": "使用缓存",
        "delayed": "更新延迟",
        "stale": "数据过期",
        "partial": "部分输入缺失",
        "fallback": "已降级到最近可用输入",
        "mock": "当前输入不可用",
        "synthetic": "当前输入不可用",
        "unavailable": "新鲜输入暂不可用",
        "error": "新鲜输入暂不可用",
        "unknown": "输入状态待确认",
    }
    messages = {
        "live": "主要输入已按当前节奏更新，可继续做结构观察。",
        "fresh": "主要输入已按当前节奏更新，可继续做结构观察。",
        "cached": "部分摘要来自缓存输入，请把结论视为结构观察。",
        "delayed": "部分输入存在延迟，请先把摘要视为观察线索。",
        "stale": "部分输入已经过期，请等待更新后再加强判断。",
        "partial": "关键输入仍不完整，请先把摘要视为观察线索。",
        "fallback": "当前摘要使用最近可用输入维持结构观察，不代表实时状态。",
        "mock": "当前缺少可用新鲜输入，请等待后续更新。",
        "synthetic": "当前缺少可用新鲜输入，请等待后续更新。",
        "unavailable": "新鲜输入暂不可用，请等待后续更新。",
        "error": "当前无法确认新鲜输入，请等待后续更新。",
        "unknown": "当前输入状态仍在确认中，请保持观察。",
    }
    return {
        "state": state,
        "label": labels.get(state, "输入状态待确认"),
        "message": messages.get(state, "当前输入状态仍在确认中，请保持观察。"),
    }


def _default_summary_sections(items: list[dict]) -> list[dict[str, object]]:
    fallback_keys = [
        "usRiskAppetite",
        "cnMoneyEffect",
        "macroPressure",
        "liquidity",
        "riskWatch",
    ]
    sections: list[dict[str, object]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        sections.append(
            {
                "key": fallback_keys[index] if index < len(fallback_keys) else f"summarySection{index + 1}",
                "title": str(item.get("title") or ""),
                "message": str(item.get("message") or ""),
                "severity": str(item.get("severity") or "neutral"),
                "category": str(item.get("category") or "risk"),
                **({"confidence": item.get("confidence")} if item.get("confidence") is not None else {}),
            }
        )
    return sections


class MarketOverviewBriefingConsumerIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    message: str
    severity: str
    category: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return _safe_consumer_text(value, field_name="consumerIssues.label", max_length=80)

    @field_validator("message")
    @classmethod
    def _validate_message(cls, value: str) -> str:
        return _safe_consumer_text(value, field_name="consumerIssues.message", max_length=160)


class MarketOverviewBriefingItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str
    message: str
    severity: BriefingSeverity
    category: str
    confidence: Optional[float] = Field(default=None, ge=0, le=1)

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        return _safe_consumer_text(value, field_name="items.title", max_length=48)

    @field_validator("message")
    @classmethod
    def _validate_message(cls, value: str) -> str:
        return _safe_consumer_text(value, field_name="items.message", max_length=160)


class MarketOverviewBriefingSummarySection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    message: str
    severity: BriefingSeverity
    category: str
    confidence: Optional[float] = Field(default=None, ge=0, le=1)

    @field_validator("key")
    @classmethod
    def _validate_key(cls, value: str) -> str:
        text = _WHITESPACE_RE.sub(" ", str(value or "").strip())
        if not text:
            raise ValueError("marketSummarySections.key must not be empty")
        if _INTERNAL_CODE_RE.search(text):
            raise ValueError("marketSummarySections.key contains internal-looking tokens")
        return text

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        return _safe_consumer_text(value, field_name="marketSummarySections.title", max_length=48)

    @field_validator("message")
    @classmethod
    def _validate_message(cls, value: str) -> str:
        return _safe_consumer_text(value, field_name="marketSummarySections.message", max_length=160)


class MarketOverviewBriefingDataQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: DataQualityState
    label: str
    available: bool = False
    summary: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return _safe_consumer_text(value, field_name="dataQuality.label", max_length=40)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return _safe_consumer_text(value, field_name="dataQuality.summary", max_length=160)


class MarketOverviewBriefingFreshnessStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: FreshnessState
    label: str
    message: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return _safe_consumer_text(value, field_name="freshnessStatus.label", max_length=40)

    @field_validator("message")
    @classmethod
    def _validate_message(cls, value: str) -> str:
        return _safe_consumer_text(value, field_name="freshnessStatus.message", max_length=160)


class MarketOverviewBriefingDegradedInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section: str
    status: DegradedInputStatus
    label: str
    message: str

    @field_validator("section")
    @classmethod
    def _validate_section(cls, value: str) -> str:
        text = _WHITESPACE_RE.sub(" ", str(value or "").strip())
        if not text:
            raise ValueError("degradedInputs.section must not be empty")
        if _INTERNAL_CODE_RE.search(text):
            raise ValueError("degradedInputs.section contains internal-looking tokens")
        return text

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return _safe_consumer_text(value, field_name="degradedInputs.label", max_length=48)

    @field_validator("message")
    @classmethod
    def _validate_message(cls, value: str) -> str:
        return _safe_consumer_text(value, field_name="degradedInputs.message", max_length=160)


class MarketOverviewBriefingResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    schemaVersion: Literal["market_overview_briefing_v1"] = MARKET_OVERVIEW_BRIEFING_SCHEMA_VERSION
    source: str
    updatedAt: str
    items: list[MarketOverviewBriefingItem] = Field(default_factory=list)
    sourceLabel: Optional[str] = None
    providerHealth: Optional[dict] = None
    asOf: Optional[str] = None
    freshness: Optional[FreshnessState] = None
    isFallback: Optional[bool] = None
    isStale: Optional[bool] = None
    isPartial: Optional[bool] = None
    isRefreshing: Optional[bool] = None
    delayMinutes: Optional[int] = Field(default=None, ge=0)
    warning: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    reliableInputCount: Optional[int] = Field(default=None, ge=0)
    fallbackInputCount: Optional[int] = Field(default=None, ge=0)
    excludedInputCount: Optional[int] = Field(default=None, ge=0)
    isReliable: Optional[bool] = None
    temperatureAvailable: Optional[bool] = None
    insufficientReliableInputs: Optional[bool] = None
    disabledReason: Optional[str] = None
    unavailableReason: Optional[str] = None
    conclusionAllowed: Optional[bool] = None
    marketSummarySections: list[MarketOverviewBriefingSummarySection] = Field(default_factory=list)
    dataQuality: MarketOverviewBriefingDataQuality
    freshnessStatus: MarketOverviewBriefingFreshnessStatus
    consumerIssues: list[MarketOverviewBriefingConsumerIssue] = Field(default_factory=list)
    degradedInputs: list[MarketOverviewBriefingDegradedInput] = Field(default_factory=list)
    noAdviceDisclosure: str
    observationOnly: Literal[True] = True
    decisionGrade: Literal[False] = False

    @model_validator(mode="before")
    @classmethod
    def _populate_contract_defaults(cls, value):
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        payload.setdefault("schemaVersion", MARKET_OVERVIEW_BRIEFING_SCHEMA_VERSION)
        if "marketSummarySections" not in payload:
            payload["marketSummarySections"] = _default_summary_sections(
                payload.get("items") if isinstance(payload.get("items"), list) else []
            )
        payload.setdefault("dataQuality", _default_data_quality(payload))
        payload.setdefault("freshnessStatus", _default_freshness_status(payload))
        payload.setdefault("degradedInputs", [])
        payload.setdefault("consumerIssues", [])
        payload.setdefault(
            "noAdviceDisclosure",
            "仅供市场结构观察与研究整理，不用于个性化决策或执行。",
        )
        payload.setdefault("observationOnly", True)
        payload.setdefault("decisionGrade", False)
        return payload

    @field_validator("warning", "noAdviceDisclosure")
    @classmethod
    def _validate_optional_text(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        max_length = 160 if info.field_name == "warning" else 120
        return _safe_consumer_text(value, field_name=info.field_name, max_length=max_length)


__all__ = [
    "MARKET_OVERVIEW_BRIEFING_SCHEMA_VERSION",
    "MarketOverviewBriefingResponse",
]
