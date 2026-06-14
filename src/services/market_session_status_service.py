# -*- coding: utf-8 -*-
"""Inert market session status mapper for the homepage top bar."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from api.v1.schemas.market_session_status import (
    MARKET_SESSION_DEFAULT_TIMEZONE_BY_MARKET,
    MARKET_SESSION_LABELS,
    MARKET_SESSION_MESSAGES,
    MARKET_SESSION_NO_ADVICE_DISCLOSURE,
    MarketSessionDataQuality,
    MarketSessionMarket,
    MarketSessionState,
    MarketSessionStatus,
    MarketSessionStatusContract,
)


_FORBIDDEN_TEXT_RE = re.compile(
    r"traceback|exception|reasoncode|trustlevel|sourcetype|provider|debug|rawpayload|"
    r"https?://|api[_-]?key|secret|cookie|session|token|/users/|/tmp/",
    re.IGNORECASE,
)
_SESSION_STATE_ALIASES: dict[str, MarketSessionState] = {
    "regular": "regular",
    "regular_open": "regular",
    "regular_session": "regular",
    "open": "regular",
    "market_open": "regular",
    "premarket": "premarket",
    "pre_market": "premarket",
    "pre_market_open": "premarket",
    "pre_open": "premarket",
    "pre": "premarket",
    "after_hours": "after_hours",
    "afterhours": "after_hours",
    "postmarket": "after_hours",
    "post_market": "after_hours",
    "post_close": "after_hours",
    "closed": "closed",
    "market_closed": "closed",
    "closed_market": "closed",
    "holiday": "holiday",
    "holiday_like": "holiday",
    "holiday_like_closed": "holiday",
    "non_trading_day": "holiday",
    "unknown": "unknown",
}
_MARKET_ALIASES: dict[str, MarketSessionMarket] = {
    "us": "US",
    "usa": "US",
    "nyse": "US",
    "nasdaq": "US",
    "hk": "HK",
    "hkex": "HK",
    "hong_kong": "HK",
    "cn": "CN",
    "ashare": "CN",
    "a_share": "CN",
    "sse": "CN",
    "szse": "CN",
}
_TIMEZONE_ALIASES = {
    "us_eastern": "US/Eastern",
    "america_new_york": "US/Eastern",
    "asia_hong_kong": "Asia/Hong_Kong",
    "asia_shanghai": "Asia/Shanghai",
    "utc": "UTC",
}


class MarketSessionStatusService:
    """Normalize caller-supplied session state into a bounded safe contract."""

    def build_status(self, payload: Mapping[str, Any] | None = None) -> MarketSessionStatusContract:
        raw = self._mapping(payload)
        session_state, has_session_signal = self._normalize_session_state(
            self._first_value(
                raw,
                "sessionState",
                "session_state",
                "state",
                "marketSessionState",
                "market_session_state",
            )
        )
        market = self._normalize_market(self._first_value(raw, "market", "exchange"))
        timezone = self._normalize_timezone(
            self._first_value(raw, "timezone", "timeZone", "tz"),
            market=market,
        )
        status: MarketSessionStatus = "ready" if has_session_signal else "unknown"
        data_quality: MarketSessionDataQuality = "provided" if has_session_signal else "unknown"

        return MarketSessionStatusContract(
            status=status,
            market=market,
            sessionState=session_state,
            label=MARKET_SESSION_LABELS[session_state],
            asOf=self._safe_text(
                self._first_value(raw, "asOf", "as_of", "timestamp", "updatedAt", "updated_at")
            ),
            timezone=timezone,
            message=MARKET_SESSION_MESSAGES[session_state],
            dataQuality=data_quality,
            noAdviceDisclosure=MARKET_SESSION_NO_ADVICE_DISCLOSURE,
        )

    def _normalize_session_state(self, value: Any) -> tuple[MarketSessionState, bool]:
        text = self._safe_text(value)
        token = self._slug(text)
        normalized = _SESSION_STATE_ALIASES.get(token, "unknown")
        if normalized == "unknown":
            return "unknown", False
        return normalized, True

    def _normalize_market(self, value: Any) -> MarketSessionMarket:
        text = self._safe_text(value)
        token = self._slug(text)
        return _MARKET_ALIASES.get(token, "unknown")

    def _normalize_timezone(self, value: Any, *, market: MarketSessionMarket) -> str:
        text = self._safe_text(value)
        token = self._slug(text)
        if token in _TIMEZONE_ALIASES:
            return _TIMEZONE_ALIASES[token]
        return MARKET_SESSION_DEFAULT_TIMEZONE_BY_MARKET[market]

    def _safe_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or _FORBIDDEN_TEXT_RE.search(text):
            return None
        return text[:64]

    def _mapping(self, value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        return {}

    def _first_value(self, payload: Mapping[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in payload and payload[key] is not None:
                return payload[key]
        return None

    def _slug(self, value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def build_market_session_status(payload: Mapping[str, Any] | None = None) -> MarketSessionStatusContract:
    return MarketSessionStatusService().build_status(payload)
