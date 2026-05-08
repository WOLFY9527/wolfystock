# -*- coding: utf-8 -*-
"""MarketCache stale/fallback contracts for provider reliability hardening."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from src.services.market_cache import MarketCache
from src.services.market_overview_service import MarketOverviewService


CN_TZ = timezone(timedelta(hours=8))


def test_cold_start_timeout_fallback_returns_quickly_and_is_not_live() -> None:
    cache = MarketCache(max_workers=1)
    release_fetch = threading.Event()

    def fetcher() -> dict:
        release_fetch.wait(2)
        return {"source": "binance", "value": 2}

    started = time.monotonic()
    payload = cache.get_or_refresh(
        "crypto",
        30,
        fetcher,
        fallback_factory=lambda: {"source": "fallback", "value": 1, "freshness": "fallback", "isFallback": True},
        cold_start_timeout_seconds=0.05,
    )
    elapsed = time.monotonic() - started

    assert elapsed < 0.5
    assert payload["source"] == "fallback"
    assert payload["freshness"] == "fallback"
    assert payload["isFallback"] is True
    assert payload["isRefreshing"] is True
    assert payload["freshness"] != "live"
    release_fetch.set()
    assert cache.wait_for_refreshes(timeout=2)


def test_stale_market_snapshot_is_served_with_refreshing_metadata() -> None:
    service = MarketOverviewService()
    service._market_cache.clear()
    service._market_data_cache.clear()
    stale_as_of = datetime(2026, 5, 3, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service._market_cache.set(
        "cn_indices",
        {
            "source": "sina",
            "sourceLabel": "新浪财经",
            "updatedAt": stale_as_of,
            "asOf": stale_as_of,
            "items": [
                {
                    "name": "上证指数",
                    "symbol": "000001.SH",
                    "value": 4100.0,
                    "change": 1.0,
                    "changePercent": 0.1,
                    "sparkline": [4090.0, 4100.0],
                    "source": "sina",
                    "sourceLabel": "新浪财经",
                    "asOf": stale_as_of,
                }
            ],
        },
        ttl_seconds=1,
    )
    entry = service._market_cache.get("cn_indices")
    entry.expires_at = entry.fetched_at - timedelta(seconds=1)
    refresh_started = threading.Event()
    release_refresh = threading.Event()

    def fetcher() -> dict:
        refresh_started.set()
        release_refresh.wait(2)
        return {
            "source": "sina",
            "items": [{"symbol": "000001.SH", "value": 4200.0, "source": "sina"}],
            "updatedAt": datetime.now(CN_TZ).isoformat(timespec="seconds"),
        }

    with patch.object(service, "_fetch_cn_indices_snapshot", side_effect=fetcher):
        payload = service.get_cn_indices()

    assert refresh_started.wait(1)
    assert payload["source"] == "sina"
    assert payload["sourceLabel"] == "新浪财经"
    assert payload["freshness"] == "stale"
    assert payload["isStale"] is True
    assert payload["isRefreshing"] is True
    assert payload["providerHealth"]["status"] == "refreshing"
    assert payload["items"][0]["freshness"] == "stale"
    assert payload["items"][0]["isStale"] is True
    release_refresh.set()
    assert service._market_cache.wait_for_refreshes(timeout=2)


def test_refresh_failure_preserves_old_safe_snapshot_and_sanitized_metadata() -> None:
    cache = MarketCache(max_workers=1)
    cache.set("sentiment", {"source": "cnn", "value": 52, "freshness": "live"}, ttl_seconds=1)
    entry = cache.get("sentiment")
    entry.expires_at = entry.fetched_at - timedelta(seconds=1)

    first = cache.get_or_refresh(
        "sentiment",
        1,
        Mock(side_effect=RuntimeError("provider timeout token=SECRET")),
        allow_stale=True,
        background_refresh=True,
    )
    assert first["value"] == 52
    assert first["isRefreshing"] is True
    assert cache.wait_for_refreshes(timeout=2)

    second = cache.get_or_refresh(
        "sentiment",
        1,
        Mock(side_effect=RuntimeError("still down")),
        allow_stale=True,
        background_refresh=False,
    )

    assert second["value"] == 52
    assert second["warning"] == "数据源刷新失败，当前显示最近快照"
    assert second["isStale"] is True
    assert second["isRefreshing"] is False
    assert cache.get("sentiment").data["value"] == 52
