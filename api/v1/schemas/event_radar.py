# -*- coding: utf-8 -*-
"""Safe contract DTOs for the homepage market-moving event radar."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator


EVENT_RADAR_SNAPSHOT_CONTRACT_VERSION = "event_radar_snapshot_v1"
EVENT_RADAR_MAX_AFFECTED_SECTORS = 3
EVENT_RADAR_MAX_AFFECTED_THEMES = 3
EVENT_RADAR_MAX_RELATED_SYMBOLS = 4
EVENT_RADAR_MAX_RELATED_MARKET_SIGNALS = 4
EVENT_RADAR_MAX_REVIEW_MODULES = 3
EVENT_RADAR_ALLOWED_MARKET_SIGNALS = (
    "money_flow",
    "rates",
    "volatility",
    "breadth",
    "sector_rotation",
    "watchlist",
    "portfolio",
    "earnings",
)

_FORBIDDEN_ADVICE_PATTERNS = (
    re.compile(r"\bbuy\b", re.IGNORECASE),
    re.compile(r"\bsell\b", re.IGNORECASE),
    re.compile(r"\badd position\b", re.IGNORECASE),
    re.compile(r"\breduce position\b", re.IGNORECASE),
    re.compile(r"\bstop-loss\b", re.IGNORECASE),
    re.compile(r"\btake-profit\b", re.IGNORECASE),
    re.compile(r"\btarget price\b", re.IGNORECASE),
    re.compile(r"\bpredicted return\b", re.IGNORECASE),
    re.compile(r"\bai recommends\b", re.IGNORECASE),
    re.compile(r"\bplace order\b", re.IGNORECASE),
    re.compile(r"\bsubmit order\b", re.IGNORECASE),
    re.compile(r"买入|卖出|加仓|减仓|交易建议|投资建议|止损|止盈|目标价"),
)
_FORBIDDEN_LEAK_PATTERNS = (
    re.compile(r"traceback", re.IGNORECASE),
    re.compile(r"exception", re.IGNORECASE),
    re.compile(r"reasoncode", re.IGNORECASE),
    re.compile(r"providerroute", re.IGNORECASE),
    re.compile(r"sourceauthority", re.IGNORECASE),
    re.compile(r"debugref", re.IGNORECASE),
    re.compile(r"rawpayload", re.IGNORECASE),
    re.compile(r"providerpayload", re.IGNORECASE),
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"/users/", re.IGNORECASE),
    re.compile(r"api_key", re.IGNORECASE),
    re.compile(r"sessionid", re.IGNORECASE),
    re.compile(r"session_id", re.IGNORECASE),
    re.compile(r"bearer\s+", re.IGNORECASE),
    re.compile(r"sk-[a-z0-9]+", re.IGNORECASE),
)
_ITEM_KEY_ALIASES = {
    "id": "id",
    "title": "title",
    "category": "category",
    "impactstatus": "impactStatus",
    "impactdirection": "impactDirection",
    "affectedsectors": "affectedSectors",
    "affectedthemes": "affectedThemes",
    "relatedsymbols": "relatedSymbols",
    "relatedmarketsignals": "relatedMarketSignals",
    "reviewmodules": "reviewModules",
    "sourcestatus": "sourceStatus",
    "freshness": "freshness",
    "summary": "summary",
    "noadvicedisclosure": "noAdviceDisclosure",
}
_FORBIDDEN_FEED_KEYS = {
    "headline",
    "url",
    "sourceurl",
    "rawpayload",
    "providerpayload",
    "author",
    "html",
    "page",
    "cursor",
    "limit",
    "offset",
    "nextcursor",
    "hasmore",
}
_EVENT_RADAR_ALLOWED_MARKET_SIGNAL_SET = set(EVENT_RADAR_ALLOWED_MARKET_SIGNALS)
_IMPACT_STATUS_ALIASES = {
    "observe": "observe",
    "observation": "observe",
    "observe_only": "observe",
    "monitor": "observe",
    "review": "review",
    "needs_review": "review",
    "under_review": "review",
    "high_attention": "high_attention",
    "highattention": "high_attention",
    "urgent": "high_attention",
    "critical": "high_attention",
}
_IMPACT_DIRECTION_ALIASES = {
    "positive": "positive",
    "upside": "positive",
    "bullish": "positive",
    "tailwind": "positive",
    "negative": "negative",
    "downside": "negative",
    "bearish": "negative",
    "headwind": "negative",
    "pressure": "negative",
    "mixed": "mixed",
    "cross_current": "mixed",
    "cross_currents": "mixed",
    "divergent": "mixed",
    "neutral": "neutral",
    "balanced": "neutral",
    "flat": "neutral",
    "unclear": "neutral",
    "unknown": "neutral",
}
_SOURCE_STATUS_ALIASES = {
    "ready": "ready",
    "available": "ready",
    "fresh": "ready",
    "no_evidence": "no_evidence",
    "missing": "no_evidence",
    "unknown": "no_evidence",
    "unavailable": "unavailable",
    "error": "unavailable",
    "failed": "unavailable",
    "provider_down": "unavailable",
}
_FRESHNESS_ALIASES = {
    "fresh": "fresh",
    "ready": "fresh",
    "live": "fresh",
    "delayed": "delayed",
    "stale": "stale",
    "unknown": "unknown",
    "no_evidence": "unavailable",
    "unavailable": "unavailable",
}


class EventRadarCategory(str, Enum):
    MACRO = "macro"
    POLICY = "policy"
    EARNINGS = "earnings"
    COMPANY = "company"
    SECTOR_THEME = "sector_theme"
    WATCHLIST = "watchlist"
    PORTFOLIO = "portfolio"
    GEOPOLITICAL = "geopolitical"
    OTHER = "other"


class EventRadarImpactStatus(str, Enum):
    OBSERVE = "observe"
    REVIEW = "review"
    HIGH_ATTENTION = "high_attention"
    NO_EVIDENCE = "no_evidence"
    UNAVAILABLE = "unavailable"


class EventRadarImpactDirection(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    NEUTRAL = "neutral"


class EventRadarSourceStatus(str, Enum):
    READY = "ready"
    NO_EVIDENCE = "no_evidence"
    UNAVAILABLE = "unavailable"


class EventRadarFreshness(str, Enum):
    FRESH = "fresh"
    DELAYED = "delayed"
    STALE = "stale"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


def _ensure_safe_text(value: str, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    for pattern in _FORBIDDEN_ADVICE_PATTERNS:
        if pattern.search(text):
            raise ValueError(f"{field_name} contains forbidden trading advice language")
    for pattern in _FORBIDDEN_LEAK_PATTERNS:
        if pattern.search(text):
            raise ValueError(f"{field_name} contains forbidden diagnostics or secret-like content")
    return text


def _normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _normalize_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _coerce_iterable(values: Any) -> list[Any]:
    if values is None:
        return []
    if isinstance(values, (list, tuple, set)):
        return list(values)
    return [values]


def _normalize_label_token(value: Any, *, field_name: str) -> str:
    text = _ensure_safe_text(str(value), field_name=field_name)
    token = _normalize_token(text)
    if not token:
        raise ValueError(f"{field_name} must not be empty")
    return token


def _normalize_symbol(value: Any, *, field_name: str) -> str:
    text = _ensure_safe_text(str(value), field_name=field_name)
    normalized = re.sub(r"\s+", "", text.upper())
    normalized = re.sub(r"[^A-Z0-9._-]", "", normalized)
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _normalize_market_signal(value: Any, *, field_name: str) -> str | None:
    token = _normalize_label_token(value, field_name=field_name)
    if token in _EVENT_RADAR_ALLOWED_MARKET_SIGNAL_SET:
        return token
    if any(marker in token for marker in ("money", "fund_flow", "capital_flow", "liquidity")):
        return "money_flow"
    if any(marker in token for marker in ("rate", "yield", "treasury", "bond", "duration")):
        return "rates"
    if any(marker in token for marker in ("vol", "vix")):
        return "volatility"
    if "breadth" in token:
        return "breadth"
    if any(marker in token for marker in ("sector", "theme", "rotation", "leadership")):
        return "sector_rotation"
    if "watchlist" in token or token == "watch_list":
        return "watchlist"
    if any(marker in token for marker in ("portfolio", "holding", "position", "correlation")):
        return "portfolio"
    if any(marker in token for marker in ("earning", "guidance", "eps", "revenue")):
        return "earnings"
    return None


def _normalize_safe_list(
    values: Iterable[Any],
    *,
    field_name: str,
    max_items: int | None = None,
    normalizer: Callable[..., str | None] | None = None,
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = (
            normalizer(value, field_name=field_name)
            if normalizer is not None
            else _ensure_safe_text(str(value), field_name=field_name)
        )
        if text is None:
            continue
        if text not in seen:
            normalized.append(text)
            seen.add(text)
        if max_items is not None and len(normalized) >= max_items:
            break
    return normalized


def _normalize_status_value(value: Any, aliases: Mapping[str, str], *, default: str) -> str:
    token = _normalize_token(value)
    if not token:
        return default
    if token in aliases:
        return aliases[token]
    for candidate, normalized in aliases.items():
        if candidate and candidate in token:
            return normalized
    return default


class EventRadarItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=160)
    category: EventRadarCategory
    impactStatus: EventRadarImpactStatus
    impactDirection: EventRadarImpactDirection = EventRadarImpactDirection.NEUTRAL
    affectedSectors: list[str] = Field(default_factory=list)
    affectedThemes: list[str] = Field(default_factory=list)
    relatedSymbols: list[str] = Field(default_factory=list)
    relatedMarketSignals: list[str] = Field(default_factory=list)
    reviewModules: list[str] = Field(default_factory=list)
    sourceStatus: EventRadarSourceStatus
    freshness: EventRadarFreshness
    summary: str = Field(..., min_length=1, max_length=600)
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=200)

    @model_validator(mode="before")
    @classmethod
    def normalize_input(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value

        payload: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            normalized_key = _normalize_key(raw_key)
            if normalized_key in _FORBIDDEN_FEED_KEYS:
                continue
            canonical_key = _ITEM_KEY_ALIASES.get(normalized_key)
            payload[canonical_key or str(raw_key)] = raw_value

        payload["impactStatus"] = _normalize_status_value(
            payload.get("impactStatus"),
            _IMPACT_STATUS_ALIASES,
            default=EventRadarImpactStatus.OBSERVE.value,
        )
        payload["impactDirection"] = _normalize_status_value(
            payload.get("impactDirection"),
            _IMPACT_DIRECTION_ALIASES,
            default=EventRadarImpactDirection.NEUTRAL.value,
        )
        payload["sourceStatus"] = _normalize_status_value(
            payload.get("sourceStatus"),
            _SOURCE_STATUS_ALIASES,
            default=EventRadarSourceStatus.READY.value,
        )
        payload["freshness"] = _normalize_status_value(
            payload.get("freshness"),
            _FRESHNESS_ALIASES,
            default=EventRadarFreshness.UNKNOWN.value,
        )
        payload["affectedSectors"] = _normalize_safe_list(
            _coerce_iterable(payload.get("affectedSectors")),
            field_name="affectedSectors",
            max_items=EVENT_RADAR_MAX_AFFECTED_SECTORS,
            normalizer=_normalize_label_token,
        )
        payload["affectedThemes"] = _normalize_safe_list(
            _coerce_iterable(payload.get("affectedThemes")),
            field_name="affectedThemes",
            max_items=EVENT_RADAR_MAX_AFFECTED_THEMES,
            normalizer=_normalize_label_token,
        )
        payload["relatedSymbols"] = _normalize_safe_list(
            _coerce_iterable(payload.get("relatedSymbols")),
            field_name="relatedSymbols",
            max_items=EVENT_RADAR_MAX_RELATED_SYMBOLS,
            normalizer=_normalize_symbol,
        )
        payload["relatedMarketSignals"] = _normalize_safe_list(
            _coerce_iterable(payload.get("relatedMarketSignals")),
            field_name="relatedMarketSignals",
            max_items=EVENT_RADAR_MAX_RELATED_MARKET_SIGNALS,
            normalizer=_normalize_market_signal,
        )
        payload["reviewModules"] = _normalize_safe_list(
            _coerce_iterable(payload.get("reviewModules")),
            field_name="reviewModules",
            max_items=EVENT_RADAR_MAX_REVIEW_MODULES,
            normalizer=_normalize_label_token,
        )
        return payload

    @model_validator(mode="after")
    def validate_safety_and_shape(self) -> "EventRadarItem":
        self.id = _ensure_safe_text(self.id, field_name="id")
        self.title = _ensure_safe_text(self.title, field_name="title")
        self.summary = _ensure_safe_text(self.summary, field_name="summary")
        self.noAdviceDisclosure = _ensure_safe_text(
            self.noAdviceDisclosure,
            field_name="noAdviceDisclosure",
        )
        self.affectedSectors = _normalize_safe_list(
            self.affectedSectors,
            field_name="affectedSectors",
            max_items=EVENT_RADAR_MAX_AFFECTED_SECTORS,
            normalizer=_normalize_label_token,
        )
        self.affectedThemes = _normalize_safe_list(
            self.affectedThemes,
            field_name="affectedThemes",
            max_items=EVENT_RADAR_MAX_AFFECTED_THEMES,
            normalizer=_normalize_label_token,
        )
        self.relatedSymbols = _normalize_safe_list(
            self.relatedSymbols,
            field_name="relatedSymbols",
            max_items=EVENT_RADAR_MAX_RELATED_SYMBOLS,
            normalizer=_normalize_symbol,
        )
        self.relatedMarketSignals = _normalize_safe_list(
            self.relatedMarketSignals,
            field_name="relatedMarketSignals",
            max_items=EVENT_RADAR_MAX_RELATED_MARKET_SIGNALS,
            normalizer=_normalize_market_signal,
        )
        self.reviewModules = _normalize_safe_list(
            self.reviewModules,
            field_name="reviewModules",
            max_items=EVENT_RADAR_MAX_REVIEW_MODULES,
            normalizer=_normalize_label_token,
        )

        if not self.reviewModules:
            raise ValueError("reviewModules must include at least one review target")
        if not any(
            (
                self.affectedSectors,
                self.affectedThemes,
                self.relatedSymbols,
                self.relatedMarketSignals,
            )
        ):
            raise ValueError("event radar items must include impact-oriented affected fields")
        if self.sourceStatus is EventRadarSourceStatus.NO_EVIDENCE:
            raise ValueError("event items cannot claim sourceStatus=no_evidence")
        if self.sourceStatus is EventRadarSourceStatus.UNAVAILABLE:
            raise ValueError("event items cannot claim sourceStatus=unavailable")
        if self.impactStatus in {EventRadarImpactStatus.NO_EVIDENCE, EventRadarImpactStatus.UNAVAILABLE}:
            raise ValueError("event items must represent an actual impact-oriented event state")
        return self


class EventRadarSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: str = Field(default=EVENT_RADAR_SNAPSHOT_CONTRACT_VERSION)
    asOf: datetime
    sourceStatus: EventRadarSourceStatus
    freshness: EventRadarFreshness
    summary: str = Field(..., min_length=1, max_length=240)
    itemCount: int = Field(..., ge=0)
    items: list[EventRadarItem] = Field(default_factory=list)
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_snapshot(self) -> "EventRadarSnapshot":
        self.summary = _ensure_safe_text(self.summary, field_name="summary")
        self.noAdviceDisclosure = _ensure_safe_text(
            self.noAdviceDisclosure,
            field_name="noAdviceDisclosure",
        )

        if self.schemaVersion != EVENT_RADAR_SNAPSHOT_CONTRACT_VERSION:
            raise ValueError("schemaVersion mismatch")
        if self.itemCount != len(self.items):
            raise ValueError("itemCount must match items length")
        if self.sourceStatus is EventRadarSourceStatus.NO_EVIDENCE:
            if self.items:
                raise ValueError("no_evidence snapshots must not contain event items")
            if self.freshness is not EventRadarFreshness.UNAVAILABLE:
                raise ValueError("no_evidence snapshots must use freshness=unavailable")
        if self.sourceStatus is EventRadarSourceStatus.UNAVAILABLE:
            if self.items:
                raise ValueError("unavailable snapshots must not contain event items")
            if self.freshness is not EventRadarFreshness.UNAVAILABLE:
                raise ValueError("unavailable snapshots must use freshness=unavailable")
        return self


__all__ = [
    "EVENT_RADAR_SNAPSHOT_CONTRACT_VERSION",
    "EVENT_RADAR_ALLOWED_MARKET_SIGNALS",
    "EventRadarCategory",
    "EventRadarFreshness",
    "EventRadarImpactDirection",
    "EventRadarImpactStatus",
    "EventRadarItem",
    "EventRadarSnapshot",
    "EventRadarSourceStatus",
]
