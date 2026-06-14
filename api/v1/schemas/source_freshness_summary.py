# -*- coding: utf-8 -*-
"""Standalone public source freshness summary contract."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SourceFreshnessStatus = Literal["ready", "limited", "unavailable", "no_evidence"]
SourceFreshnessLevel = Literal["fresh", "recent", "stale", "no_evidence", "unavailable", "unknown"]
SourceFreshnessCategory = Literal["market", "research", "event", "watchlist", "other"]

SOURCE_FRESHNESS_NO_ADVICE_DISCLOSURE = "仅供研究观察，不构成投资建议。"

_CATEGORY_LABELS: dict[SourceFreshnessCategory, str] = {
    "market": "市场数据",
    "research": "研究资料",
    "event": "事件观察",
    "watchlist": "自选观察",
    "other": "观察来源",
}
_DEFAULT_SOURCE_MESSAGES: dict[SourceFreshnessLevel, str] = {
    "fresh": "来源更新及时，适合观察。",
    "recent": "来源较新，仍可用于观察。",
    "stale": "来源时间偏旧，建议谨慎观察。",
    "no_evidence": "暂无足够来源新鲜度证据。",
    "unavailable": "来源暂不可用，请稍后再看。",
    "unknown": "来源新鲜度暂不明确，请谨慎观察。",
}
_DEFAULT_SUMMARY_MESSAGES: dict[SourceFreshnessStatus, str] = {
    "ready": "来源新鲜度满足观察需要。",
    "limited": "部分来源已过时或暂不可用，当前仅适合谨慎观察。",
    "unavailable": "关键来源暂不可用，当前不适合依赖该摘要观察。",
    "no_evidence": "暂无足够来源新鲜度证据，当前仅保留观察位。",
}
_CATEGORY_ALIASES = {
    "market": "market",
    "marketdata": "market",
    "market_data": "market",
    "research": "research",
    "researchdata": "research",
    "event": "event",
    "events": "event",
    "watchlist": "watchlist",
    "watch_list": "watchlist",
}
_FRESHNESS_ALIASES = {
    "fresh": "fresh",
    "ready": "fresh",
    "updated": "fresh",
    "recent": "recent",
    "current": "recent",
    "stale": "stale",
    "delayed": "stale",
    "old": "stale",
    "noevidence": "no_evidence",
    "no_evidence": "no_evidence",
    "missing": "no_evidence",
    "empty": "no_evidence",
    "unavailable": "unavailable",
    "error": "unavailable",
    "failed": "unavailable",
    "unknown": "unknown",
}
_FORBIDDEN_TEXT_RE = re.compile(
    r"traceback|provider|reasoncode|diagnostic|debug|token|secret|session|cookie|api[_-]?key|"
    r"https?://|www\\.|timeout|stack|exception|error|path|query|raw",
    re.IGNORECASE,
)
_FORBIDDEN_ADVICE_RE = re.compile(
    r"buy now|sell now|trade recommendation|trading advice|investment advice|target price|stop loss|"
    r"take profit|place order|submit order|立即交易|交易指令|投资建议|目标价|止损|止盈|买入|卖出|下单",
    re.IGNORECASE,
)
_SAFE_TEXT_RE = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff _./():+-]+")
_TIMESTAMP_RE = re.compile(r"^[0-9T:Z+\-./ ]{4,40}$")


def normalize_source_category(value: object) -> SourceFreshnessCategory:
    normalized = re.sub(r"[^0-9a-z]+", "", str(value or "").strip().lower())
    mapped = _CATEGORY_ALIASES.get(normalized)
    if mapped in _CATEGORY_LABELS:
        return mapped  # type: ignore[return-value]
    return "other"


def normalize_source_freshness(value: object) -> SourceFreshnessLevel:
    text = str(value or "").strip().lower()
    if not text:
        return "no_evidence"
    normalized = re.sub(r"[^0-9a-z_]+", "", text)
    mapped = _FRESHNESS_ALIASES.get(normalized)
    if mapped is not None:
        return mapped  # type: ignore[return-value]
    return "unknown"


def default_source_label(category: SourceFreshnessCategory) -> str:
    return _CATEGORY_LABELS.get(category, _CATEGORY_LABELS["other"])


def default_source_message(freshness: SourceFreshnessLevel) -> str:
    return _DEFAULT_SOURCE_MESSAGES[freshness]


def default_summary_message(status: SourceFreshnessStatus) -> str:
    return _DEFAULT_SUMMARY_MESSAGES[status]


def sanitize_source_key(value: object, *, category: SourceFreshnessCategory) -> str:
    raw = str(value or "").strip()
    normalized = re.sub(r"[^0-9a-z]+", "_", raw.lower()).strip("_")
    if not normalized or _FORBIDDEN_TEXT_RE.search(raw):
        return category if category != "other" else "source"
    if any(marker in normalized for marker in ("provider", "token", "secret", "session", "debug", "query", "path")):
        return category if category != "other" else "source"
    return normalized[:48] or (category if category != "other" else "source")


def sanitize_public_label(value: object, *, category: SourceFreshnessCategory) -> str:
    text = sanitize_public_text(value, fallback=default_source_label(category), max_length=32)
    if text == default_source_label(category):
        return text
    cleaned = _SAFE_TEXT_RE.sub(" ", text).strip(" ._-")
    return cleaned or default_source_label(category)


def sanitize_timestamp_text(value: object) -> str | None:
    text = str(value or "").strip()
    if not text or _FORBIDDEN_TEXT_RE.search(text):
        return None
    if not _TIMESTAMP_RE.match(text):
        return None
    return text[:40]


def sanitize_public_text(value: object, *, fallback: str, max_length: int = 80) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    if _FORBIDDEN_TEXT_RE.search(text) or _FORBIDDEN_ADVICE_RE.search(text):
        return fallback
    cleaned = _SAFE_TEXT_RE.sub(" ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return fallback
    return cleaned[:max_length]


class SourceFreshnessItem(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    key: str
    label: str
    category: SourceFreshnessCategory
    freshness: SourceFreshnessLevel
    as_of: str | None = Field(default=None, alias="asOf")
    public_message: str = Field(alias="publicMessage")

    @field_validator("as_of", mode="before")
    @classmethod
    def _validate_as_of(cls, value: object) -> str | None:
        return sanitize_timestamp_text(value)


class SourceFreshnessSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    status: SourceFreshnessStatus
    as_of: str | None = Field(default=None, alias="asOf")
    sources: list[SourceFreshnessItem]
    overall_freshness: SourceFreshnessLevel = Field(alias="overallFreshness")
    stale_count: int = Field(alias="staleCount", ge=0)
    unavailable_count: int = Field(alias="unavailableCount", ge=0)
    message: str
    no_advice_disclosure: str = Field(
        default=SOURCE_FRESHNESS_NO_ADVICE_DISCLOSURE,
        alias="noAdviceDisclosure",
    )

    @field_validator("as_of", mode="before")
    @classmethod
    def _validate_summary_as_of(cls, value: object) -> str | None:
        return sanitize_timestamp_text(value)
