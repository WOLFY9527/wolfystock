# -*- coding: utf-8 -*-
"""TickFlow-backed CN breadth provider for Market Overview only."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Dict, Optional

from data_provider.tickflow_fetcher import TickFlowFetcher
from src.config import get_config


CN_TZ = timezone(timedelta(hours=8))
_TICKFLOW_SOURCE = "tickflow"
_TICKFLOW_SOURCE_LABEL = "TickFlow"
_TICKFLOW_SOURCE_TYPE = "public_api"


class MarketOverviewTickFlowBreadthProvider:
    """Reuse TickFlow market-stats access for the CN breadth card only."""

    def __init__(self) -> None:
        self._fetcher: Optional[TickFlowFetcher] = None
        self._api_key: Optional[str] = None
        self._lock = RLock()

    def fetch_snapshot(self) -> Dict[str, Any]:
        fetcher = self._get_fetcher()
        try:
            stats = fetcher.get_market_stats()
        except Exception as exc:
            raise RuntimeError(self._reason_code_for_error(exc)) from exc

        if not stats:
            if getattr(fetcher, "_universe_query_supported", None) is False:
                raise RuntimeError("tickflow_permission_unavailable")
            raise RuntimeError("tickflow_market_stats_empty")

        advancers = self._non_negative_int(stats, "up_count")
        decliners = self._non_negative_int(stats, "down_count")
        unchanged = self._non_negative_int(stats, "flat_count")
        limit_up = self._non_negative_int(stats, "limit_up_count")
        limit_down = self._non_negative_int(stats, "limit_down_count")
        total = advancers + decliners + unchanged
        if total <= 0:
            raise RuntimeError("tickflow_market_stats_malformed")

        adv_ratio = round((advancers / total) * 100.0, 1)
        effect = int(round(adv_ratio))
        updated_at = self._now_iso()
        return {
            "source": _TICKFLOW_SOURCE,
            "sourceLabel": _TICKFLOW_SOURCE_LABEL,
            "sourceType": _TICKFLOW_SOURCE_TYPE,
            "updatedAt": updated_at,
            "asOf": updated_at,
            "advancers": advancers,
            "decliners": decliners,
            "limitUp": limit_up,
            "limitDown": limit_down,
            "advRatio": adv_ratio,
            "effect": effect,
        }

    def close(self) -> None:
        with self._lock:
            fetcher = self._fetcher
            self._fetcher = None
            self._api_key = None
        if fetcher is not None:
            try:
                fetcher.close()
            except Exception:
                return

    def _get_fetcher(self) -> TickFlowFetcher:
        api_key = (getattr(get_config(), "tickflow_api_key", None) or "").strip()
        if not api_key:
            self.close()
            raise RuntimeError("tickflow_not_configured")

        with self._lock:
            if self._fetcher is not None and self._api_key == api_key:
                return self._fetcher

            previous = self._fetcher
            self._fetcher = None
            self._api_key = None
            if previous is not None:
                try:
                    previous.close()
                except Exception:
                    pass

            try:
                fetcher = TickFlowFetcher(api_key=api_key)
            except Exception as exc:
                raise RuntimeError("tickflow_unavailable") from exc

            self._fetcher = fetcher
            self._api_key = api_key
            return fetcher

    @staticmethod
    def _non_negative_int(payload: Dict[str, Any], key: str) -> int:
        value = payload.get(key)
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("tickflow_market_stats_malformed") from exc
        if number < 0:
            raise RuntimeError("tickflow_market_stats_malformed")
        return number

    @staticmethod
    def _reason_code_for_error(exc: Exception) -> str:
        message = f"{getattr(exc, 'message', '')} {exc}".strip().lower()
        if TickFlowFetcher._is_universe_permission_error(exc):
            return "tickflow_permission_unavailable"
        if "timeout" in message or "timed out" in message or "超时" in message:
            return "tickflow_timeout"
        if "invalid" in message or "malformed" in message or "schema" in message:
            return "tickflow_market_stats_malformed"
        return "tickflow_unavailable"

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(CN_TZ).isoformat(timespec="seconds")


_provider = MarketOverviewTickFlowBreadthProvider()


def fetch_tickflow_cn_breadth_snapshot() -> Dict[str, Any]:
    return _provider.fetch_snapshot()
