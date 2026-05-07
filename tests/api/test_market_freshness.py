# -*- coding: utf-8 -*-
"""Cache/freshness integration tests for market endpoints."""

from __future__ import annotations

import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from src.services.market_overview_service import (
    MarketOverviewService,
    classify_market_payload_reliability,
    get_freshness_status,
)


CN_TZ = timezone(timedelta(hours=8))


class MarketFreshnessCacheTestCase(unittest.TestCase):
    def setUp(self) -> None:
        MarketOverviewService._market_cache.clear()
        MarketOverviewService._market_data_cache.clear()

    def test_expired_cache_returns_old_snapshot_and_refreshes_in_background(self) -> None:
        service = MarketOverviewService()
        first_time = datetime(2026, 4, 30, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
        service._market_cache.set(
            "crypto",
            {
                "items": [{"symbol": "BTC", "price": 70000, "change": 1, "trend": [69000, 70000], "source": "binance", "last_update": first_time}],
                "last_update": first_time,
                "source": "binance",
                "fallback_used": False,
            },
            ttl_seconds=1,
        )
        entry = service._market_cache.get("crypto")
        entry.expires_at = entry.fetched_at - timedelta(seconds=1)
        refresh_started = threading.Event()
        release_refresh = threading.Event()
        refreshed_time = datetime(2026, 4, 30, 10, 1, tzinfo=CN_TZ).isoformat(timespec="seconds")

        def fetcher() -> dict:
            refresh_started.set()
            release_refresh.wait(2)
            return {
                "items": [{"symbol": "BTC", "price": 71000, "change": 2, "trend": [70000, 71000], "source": "binance", "last_update": refreshed_time}],
                "last_update": refreshed_time,
                "source": "binance",
                "fallback_used": False,
            }

        with patch.object(service, "_fetch_crypto_market_snapshot", side_effect=fetcher):
            stale_payload = service.get_crypto()
            self.assertEqual(stale_payload["items"][0]["price"], 70000)
            self.assertTrue(stale_payload["isRefreshing"])
            self.assertTrue(refresh_started.wait(1))
            release_refresh.set()
            self.assertTrue(service._market_cache.wait_for_refreshes(timeout=2))
            refreshed_payload = service.get_crypto()

        self.assertEqual(refreshed_payload["items"][0]["price"], 71000)
        self.assertFalse(refreshed_payload["isRefreshing"])

    def test_refresh_failure_preserves_old_snapshot_and_warning(self) -> None:
        service = MarketOverviewService()
        updated_at = datetime(2026, 4, 30, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
        service._market_cache.set(
            "sentiment",
            {
                "items": [{"symbol": "FGI", "price": 52, "change": 0, "trend": [50, 52], "source": "cnn", "last_update": updated_at}],
                "last_update": updated_at,
                "source": "cnn",
                "fallback_used": False,
            },
            ttl_seconds=1,
        )
        entry = service._market_cache.get("sentiment")
        entry.expires_at = entry.fetched_at - timedelta(seconds=1)

        with patch.object(service, "_fetch_market_sentiment_snapshot", side_effect=RuntimeError("cnn down")):
            stale_payload = service.get_market_sentiment()
            self.assertTrue(stale_payload["isRefreshing"])
            self.assertTrue(service._market_cache.wait_for_refreshes(timeout=2))
            payload = service.get_market_sentiment()

        self.assertEqual(payload["items"][0]["price"], 52)
        self.assertEqual(payload["warning"], "数据源刷新失败，当前显示最近快照")
        self.assertEqual(payload["lastError"], "数据源暂不可用")
        self.assertEqual(payload["providerHealth"]["errorSummary"], "数据源暂不可用")
        self.assertNotIn("cnn down", str(payload))

    def test_fallback_data_keeps_fallback_freshness(self) -> None:
        service = MarketOverviewService()

        with patch.object(service, "_fetch_cn_breadth_snapshot", Mock(side_effect=RuntimeError("provider down"))):
            payload = service.get_cn_breadth()

        self.assertEqual(payload["freshness"], "fallback")
        self.assertTrue(payload["isFallback"])
        self.assertNotEqual(payload["freshness"], "live")
        self.assertEqual(payload["items"][0]["freshness"], "fallback")

    def test_fallback_mock_and_delayed_states_are_not_disclosed_as_live(self) -> None:
        now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ)

        fallback = get_freshness_status(now.isoformat(timespec="seconds"), "crypto", "fallback", True, now=now)
        synthetic = get_freshness_status(now.isoformat(timespec="seconds"), "crypto", "mock", False, now=now)
        delayed = get_freshness_status(
            (now - timedelta(minutes=12)).isoformat(timespec="seconds"),
            "futures",
            "yahoo",
            False,
            now=now,
        )

        self.assertEqual(fallback["freshness"], "fallback")
        self.assertTrue(fallback["isFallback"])
        self.assertEqual(synthetic["freshness"], "mock")
        self.assertTrue(synthetic["isFallback"])
        self.assertEqual(delayed["freshness"], "delayed")
        self.assertFalse(delayed["isFallback"])
        self.assertNotIn("live", {fallback["freshness"], synthetic["freshness"], delayed["freshness"]})

    def test_synthetic_and_delayed_inputs_do_not_get_full_live_confidence(self) -> None:
        synthetic = classify_market_payload_reliability(
            {"symbol": "BTC", "value": 75800, "source": "mock", "freshness": "mock"},
            category="crypto",
        )
        delayed = classify_market_payload_reliability(
            {"symbol": "ES", "value": 5238, "source": "yahoo", "freshness": "delayed"},
            category="futures",
        )

        self.assertEqual(synthetic["kind"], "fallback")
        self.assertFalse(synthetic["isReliable"])
        self.assertEqual(synthetic["confidenceWeight"], 0.0)
        self.assertEqual(delayed["kind"], "real")
        self.assertTrue(delayed["isReliable"])
        self.assertLess(delayed["confidenceWeight"], 1.0)

    def test_overview_indices_slow_cold_fetch_returns_fallback_quickly(self) -> None:
        service = MarketOverviewService()
        service.MARKET_COLD_START_TIMEOUT_SECONDS = 0.05
        release_fetch = threading.Event()

        def fetcher() -> dict:
            release_fetch.wait(2)
            return {
                "panel_name": "IndexTrendsCard",
                "last_refresh_at": datetime(2026, 4, 30, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds"),
                "status": "success",
                "source": "yfinance",
                "items": [
                    {"symbol": "SPX", "label": "S&P 500", "value": 5100, "change_pct": 1, "trend": [5000, 5100], "source": "yfinance"}
                ],
            }

        start = time.monotonic()
        with patch.object(service, "_fetch_indices", side_effect=fetcher):
            payload = service.get_indices()
        elapsed = time.monotonic() - start

        self.assertLess(elapsed, 0.5)
        self.assertEqual(payload["panel_name"], "IndexTrendsCard")
        self.assertTrue(payload["items"])
        self.assertTrue(payload["isRefreshing"])
        self.assertEqual(payload["freshness"], "fallback")
        self.assertNotEqual(payload["freshness"], "live")
        release_fetch.set()
        self.assertTrue(service._market_cache.wait_for_refreshes(timeout=2))
        refreshed = service.get_indices()
        self.assertEqual(refreshed["items"][0]["value"], 5100)
        self.assertFalse(refreshed["isRefreshing"])


if __name__ == "__main__":
    unittest.main()
