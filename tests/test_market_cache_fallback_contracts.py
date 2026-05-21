# -*- coding: utf-8 -*-
"""MarketCache stale/fallback contracts for provider reliability hardening."""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.services.market_cache import MarketCache
from src.services.market_overview_service import MarketOverviewService
from src.storage import DatabaseManager


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


def test_clear_invalidates_in_flight_refresh_from_prior_generation() -> None:
    cache = MarketCache(max_workers=2)
    cache.set("cn_indices", {"source": "stale", "value": 17680.3}, ttl_seconds=1)
    entry = cache.get("cn_indices")
    assert entry is not None
    entry.expires_at = entry.fetched_at - timedelta(seconds=1)

    started = threading.Event()
    release_old_refresh = threading.Event()
    old_refresh_finished = threading.Event()

    def old_fetcher() -> dict:
        started.set()
        release_old_refresh.wait(2)
        old_refresh_finished.set()
        return {"source": "old_refresh", "value": 17680.3}

    stale_payload = cache.get_or_refresh(
        "cn_indices",
        1,
        old_fetcher,
        allow_stale=True,
        background_refresh=True,
    )
    assert stale_payload["value"] == 17680.3
    assert stale_payload["isRefreshing"] is True
    assert started.wait(1)

    cache.clear()

    release_new_refresh = threading.Event()
    new_refresh_started = threading.Event()

    def new_fetcher() -> dict:
        new_refresh_started.set()
        release_new_refresh.wait(2)
        return {"source": "new_refresh", "value": 25675.182}

    fresh_payload = cache.get_or_refresh(
        "cn_indices",
        30,
        new_fetcher,
        fallback_factory=lambda: {"source": "fallback", "value": 17680.3, "freshness": "fallback", "isFallback": True},
        allow_stale=True,
        background_refresh=True,
        cold_start_timeout_seconds=0.05,
    )
    assert new_refresh_started.wait(1)
    assert fresh_payload["value"] == 17680.3
    assert fresh_payload["source"] == "fallback"
    assert fresh_payload["isRefreshing"] is True

    release_old_refresh.set()
    assert old_refresh_finished.wait(1)
    time.sleep(0.05)

    current = cache.get("cn_indices")
    assert current is not None
    assert current.data["value"] == 17680.3
    assert current.data["source"] == "fallback"

    release_new_refresh.set()
    assert cache.wait_for_refreshes(timeout=2)


def test_market_briefing_degrades_instead_of_emitting_strong_narrative_from_legacy_sentiment_shape_only() -> None:
    service = MarketOverviewService()
    service._market_cache.clear()
    service._market_data_cache.clear()

    legacy_sentiment_panel = {
        "source": "cnn",
        "sourceLabel": "CNN",
        "freshness": "live",
        "isFallback": False,
        "items": [
            {
                "symbol": "FGI",
                "label": "Fear & Greed",
                "value": 52,
                "unit": "score",
                "change_pct": -3.0,
                "trend": [60, 55, 52],
                "source": "cnn",
                "freshness": "live",
                "isFallback": False,
            }
        ],
    }
    inputs = {
        "indices": {"items": []},
        "breadth": {"items": []},
        "flows": {"items": []},
        "sectors": {"items": []},
        "rates": {"items": []},
        "fx": {"items": []},
        "futures": {"items": []},
        "sentiment": legacy_sentiment_panel,
        "crypto": {"items": []},
        "fallback_notice": True,
    }

    with patch.object(service, "_build_market_temperature_inputs", return_value=inputs):
        payload = service.get_market_briefing()

    assert payload["source"] == "fallback"
    assert payload["warning"] == "当前真实数据不足，暂不生成强市场判断。"
    assert [item["title"] for item in payload["items"]] == [
        "当前真实数据不足",
        "备用数据已降级",
        "等待真实行情源",
    ]
    assert all(item["category"] == "risk" for item in payload["items"])
    assert all(item["severity"] in {"warning", "neutral"} for item in payload["items"])


def test_persistent_cross_panel_sentiment_snapshot_is_served_stale_not_live(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "t145-sentiment-persistent.sqlite"
    DatabaseManager.reset_instance()
    DatabaseManager(db_url=f"sqlite:///{db_path}")
    DatabaseManager.get_instance().save_market_overview_snapshot(
        key="market_overview:sentiment",
        payload={
            "source": "computed",
            "updatedAt": "2026-05-15T10:00:00+08:00",
            "scores": {"overall": {"value": 62, "label": "偏暖"}},
        },
    )

    service = MarketOverviewService()
    service._market_cache.clear()
    service._market_data_cache.clear()
    with patch.dict(os.environ, {"MARKET_OVERVIEW_SNAPSHOT_TEST_DB": "1"}, clear=False):
        with patch.object(service, "_fetch_market_sentiment_snapshot", side_effect=RuntimeError("provider down")):
            payload = service.get_market_sentiment()

    assert payload["isFromSnapshot"] is True
    assert payload["freshness"] == "stale"
    assert payload["freshness"] != "live"
    assert payload["items"] == []
    assert payload["warning"] == "数据源刷新失败，当前显示最近成功快照"
    assert payload["providerHealth"]["status"] not in {"live", "cache"}
    assert payload["providerHealth"]["sourceLabel"] == "Snapshot"

    DatabaseManager.reset_instance()
