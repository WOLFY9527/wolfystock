# -*- coding: utf-8 -*-
"""Standalone homepage event-window summary normalizer.

This service is intentionally inert. It only normalizes caller-supplied event
windows into a bounded contract and never fetches external calendar/news data.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any

from api.v1.schemas.event_window import (
    EventWindowCategory,
    EventWindowDataQuality,
    EventWindowDataQualityState,
    EventWindowItem,
    EventWindowState,
    EventWindowSummary,
)


EVENT_WINDOW_NO_ADVICE_DISCLOSURE = "Research observation only; not personalized financial advice."
EVENT_WINDOW_MAX_RELATED_SYMBOLS = 4
EVENT_WINDOW_MAX_RELATED_THEMES = 4

_NO_EVIDENCE_TITLE = "Event window needs review."
_NO_EVIDENCE_REASON = "Review event window context."
_FORBIDDEN_TEXT_RE = re.compile(
    r"traceback|reasoncode|trustlevel|sourcetype|rawpayload|providerpayload|"
    r"providerroute|provider[_ -]?url|https?://|/users/|api[_-]?key|apikey|"
    r"token|session|secret|debug|fallback",
    re.IGNORECASE,
)
_FORBIDDEN_ADVICE_RE = re.compile(
    r"\bbuy\b|\bsell\b|buy now|sell now|add position|reduce position|clear position|place order|submit order|"
    r"trade execution|stop-loss|stop loss|take-profit|take profit|target price|predicted return|"
    r"买入|卖出|加仓|减仓|清仓|下单|立即交易|止损|止盈|目标价",
    re.IGNORECASE,
)
_CATEGORY_ALIASES = {
    "earnings": EventWindowCategory.EARNINGS,
    "macro": EventWindowCategory.MACRO,
    "policy": EventWindowCategory.POLICY,
    "company": EventWindowCategory.COMPANY,
    "sector_theme": EventWindowCategory.SECTOR_THEME,
    "sector": EventWindowCategory.SECTOR_THEME,
    "theme": EventWindowCategory.SECTOR_THEME,
    "watchlist": EventWindowCategory.WATCHLIST,
    "portfolio": EventWindowCategory.PORTFOLIO,
    "other": EventWindowCategory.OTHER,
}
_WINDOW_STATE_ALIASES = {
    "upcoming": EventWindowState.UPCOMING,
    "starts_soon": EventWindowState.UPCOMING,
    "scheduled": EventWindowState.UPCOMING,
    "future": EventWindowState.UPCOMING,
    "active": EventWindowState.ACTIVE,
    "current": EventWindowState.ACTIVE,
    "live": EventWindowState.ACTIVE,
    "in_progress": EventWindowState.ACTIVE,
    "passed": EventWindowState.PASSED,
    "ended": EventWindowState.PASSED,
    "complete": EventWindowState.PASSED,
    "completed": EventWindowState.PASSED,
    "historical": EventWindowState.PASSED,
    "unknown": EventWindowState.UNKNOWN,
}
_DATA_QUALITY_LABELS = {
    EventWindowDataQualityState.READY: "正常",
    EventWindowDataQualityState.REVIEW: "复核",
    EventWindowDataQualityState.NO_EVIDENCE: "暂无证据",
    EventWindowDataQualityState.UNAVAILABLE: "暂不可用",
}


class EventWindowService:
    """Normalize safe caller-provided event windows for homepage consumption."""

    def build_summary(self, payload: Mapping[str, Any] | None = None) -> EventWindowSummary:
        raw = self._mapping(payload)
        as_of = self._safe_timestamp(raw.get("asOf"))
        windows = self._build_windows(raw.get("windows"))

        if not windows:
            quality = self._quality(EventWindowDataQualityState.NO_EVIDENCE)
            return EventWindowSummary(
                status="no_evidence",
                asOf=as_of,
                windows=[],
                sourceStatus="no_evidence",
                dataQuality=quality,
                noAdviceDisclosure=EVENT_WINDOW_NO_ADVICE_DISCLOSURE,
            )

        status = self._derive_status(windows)
        quality = self._top_level_quality(status)
        return EventWindowSummary(
            status=status,
            asOf=as_of,
            windows=windows,
            sourceStatus=status,
            dataQuality=quality,
            noAdviceDisclosure=EVENT_WINDOW_NO_ADVICE_DISCLOSURE,
        )

    def _build_windows(self, value: Any) -> list[EventWindowItem]:
        windows: list[EventWindowItem] = []
        for index, raw_item in enumerate(self._sequence(value), start=1):
            row = self._mapping(raw_item)
            if not row:
                continue
            windows.append(
                EventWindowItem(
                    id=self._safe_id(self._first_value(row, "id"), index=index),
                    title=self._safe_text(
                        self._first_value(row, "title"),
                        default=_NO_EVIDENCE_TITLE,
                    ),
                    category=self._category(self._first_value(row, "category")),
                    windowState=self._window_state(self._first_value(row, "windowState", "window_state")),
                    startsAt=self._safe_timestamp(self._first_value(row, "startsAt", "starts_at")),
                    endsAt=self._safe_timestamp(self._first_value(row, "endsAt", "ends_at")),
                    relatedSymbols=self._safe_symbols(
                        self._first_value(row, "relatedSymbols", "related_symbols")
                    ),
                    relatedThemes=self._safe_themes(
                        self._first_value(row, "relatedThemes", "related_themes")
                    ),
                    reviewReason=self._safe_text(
                        self._first_value(row, "reviewReason", "review_reason"),
                        default=_NO_EVIDENCE_REASON,
                    ),
                    dataQuality=self._data_quality(
                        self._first_value(row, "dataQuality", "data_quality"),
                    ),
                )
            )
        return windows

    def _derive_status(self, windows: Sequence[EventWindowItem]) -> str:
        states = {window.dataQuality.state for window in windows}
        if states == {EventWindowDataQualityState.READY}:
            return "ready"
        if states <= {EventWindowDataQualityState.NO_EVIDENCE}:
            return "no_evidence"
        if EventWindowDataQualityState.UNAVAILABLE in states and states <= {
            EventWindowDataQualityState.UNAVAILABLE,
            EventWindowDataQualityState.NO_EVIDENCE,
        }:
            return "unavailable"
        return "partial"

    def _top_level_quality(self, status: str) -> EventWindowDataQuality:
        if status == "ready":
            return self._quality(EventWindowDataQualityState.READY)
        if status == "unavailable":
            return self._quality(EventWindowDataQualityState.UNAVAILABLE)
        if status == "no_evidence":
            return self._quality(EventWindowDataQualityState.NO_EVIDENCE)
        return self._quality(EventWindowDataQualityState.REVIEW)

    def _data_quality(self, value: Any) -> EventWindowDataQuality:
        token = self._slug(value)
        if token in {"ready", "available", "fresh", "normal", "bounded"}:
            return self._quality(EventWindowDataQualityState.READY)
        if token in {
            "review",
            "partial",
            "delayed",
            "stale",
            "trusted_source",
            "provider_timeout",
            "needs_review",
            "cached",
        }:
            return self._quality(EventWindowDataQualityState.REVIEW)
        if token in {"unavailable", "error", "failed"}:
            return self._quality(EventWindowDataQualityState.UNAVAILABLE)
        return self._quality(EventWindowDataQualityState.NO_EVIDENCE)

    def _quality(self, state: EventWindowDataQualityState) -> EventWindowDataQuality:
        return EventWindowDataQuality(
            state=state,
            label=_DATA_QUALITY_LABELS[state],
            available=state in {EventWindowDataQualityState.READY, EventWindowDataQualityState.REVIEW},
        )

    def _category(self, value: Any) -> EventWindowCategory:
        token = self._slug(value)
        if token in _CATEGORY_ALIASES:
            return _CATEGORY_ALIASES[token]
        if "earning" in token or "guidance" in token:
            return EventWindowCategory.EARNINGS
        if any(marker in token for marker in ("fomc", "fed", "rate", "policy")):
            return EventWindowCategory.POLICY
        if any(marker in token for marker in ("macro", "cpi", "ppi", "payroll", "inflation", "gdp")):
            return EventWindowCategory.MACRO
        if any(marker in token for marker in ("sector", "theme")):
            return EventWindowCategory.SECTOR_THEME
        return EventWindowCategory.OTHER

    def _window_state(self, value: Any) -> EventWindowState:
        token = self._slug(value)
        if token in _WINDOW_STATE_ALIASES:
            return _WINDOW_STATE_ALIASES[token]
        if any(marker in token for marker in ("soon", "next", "schedule", "upcoming")):
            return EventWindowState.UPCOMING
        if any(marker in token for marker in ("active", "live", "current")):
            return EventWindowState.ACTIVE
        if any(marker in token for marker in ("passed", "ended", "histor")):
            return EventWindowState.PASSED
        return EventWindowState.UNKNOWN

    def _safe_id(self, value: Any, *, index: int) -> str:
        token = self._slug(self._safe_text(value, default=""), separator="-")
        return token or f"event-window-{index}"

    def _safe_symbols(self, value: Any) -> list[str]:
        items: list[str] = []
        seen: set[str] = set()
        for raw_symbol in self._sequence(value):
            text = self._safe_text(raw_symbol, default="")
            if not text:
                continue
            normalized = re.sub(r"\s+", "", text.upper())
            normalized = re.sub(r"[^A-Z0-9._-]", "", normalized)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            items.append(normalized)
            if len(items) >= EVENT_WINDOW_MAX_RELATED_SYMBOLS:
                break
        return items

    def _safe_themes(self, value: Any) -> list[str]:
        items: list[str] = []
        seen: set[str] = set()
        for raw_theme in self._sequence(value):
            text = self._safe_text(raw_theme, default="")
            token = self._slug(text)
            if not token or token in seen:
                continue
            seen.add(token)
            items.append(token)
            if len(items) >= EVENT_WINDOW_MAX_RELATED_THEMES:
                break
        return items

    def _safe_timestamp(self, value: Any) -> str | None:
        text = self._text(value)
        if not text or _FORBIDDEN_TEXT_RE.search(text):
            return None
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text):
            return text
        return None

    def _safe_text(self, value: Any, *, default: str) -> str:
        text = self._text(value)
        if not text:
            return default
        if _FORBIDDEN_TEXT_RE.search(text) or _FORBIDDEN_ADVICE_RE.search(text):
            return default
        return text

    def _first_value(self, payload: Mapping[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in payload:
                return payload.get(key)
        return None

    def _mapping(self, value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        return {}

    def _sequence(self, value: Any) -> list[Any]:
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return list(value)
        return []

    def _text(self, value: Any) -> str | None:
        if value is None or isinstance(value, Mapping):
            return None
        text = str(value).strip()
        return text or None

    def _slug(self, value: Any, *, separator: str = "_") -> str:
        text = self._text(value)
        if not text:
            return ""
        escaped = re.escape(separator)
        normalized = re.sub(r"[^a-z0-9]+", separator, text.lower()).strip(separator)
        return re.sub(rf"{escaped}+", separator, normalized)


__all__ = [
    "EVENT_WINDOW_MAX_RELATED_SYMBOLS",
    "EVENT_WINDOW_MAX_RELATED_THEMES",
    "EVENT_WINDOW_NO_ADVICE_DISCLOSURE",
    "EventWindowService",
]
