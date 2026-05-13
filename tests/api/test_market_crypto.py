# -*- coding: utf-8 -*-
"""Contract and fallback tests for market crypto endpoint."""

from __future__ import annotations

import unittest
import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from api.v1.endpoints import market
from src.services.market_overview_service import MarketOverviewService


CN_TZ = timezone(timedelta(hours=8))


class MarketCryptoApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        MarketOverviewService._market_cache.clear()
        MarketOverviewService._market_data_cache.clear()

    def test_get_crypto_returns_contract_payload(self) -> None:
        service = MagicMock()
        service.get_crypto.return_value = {
            "items": [
                {
                    "symbol": "BTC",
                    "price": 76837.04,
                    "change": 1.47,
                    "trend": [74211.0, 75120.0, 76837.04],
                    "last_update": "2026-04-29T10:00:00",
                    "error": None,
                }
            ],
            "last_update": "2026-04-29T10:00:00",
            "error": None,
            "fallback_used": False,
            "source": "binance",
        }

        with patch("api.v1.endpoints.market.MarketOverviewService", return_value=service):
            payload = market.get_crypto()

        self.assertEqual(payload["source"], "binance")
        self.assertFalse(payload["fallback_used"])
        self.assertEqual(payload["items"][0]["symbol"], "BTC")
        self.assertIn("price", payload["items"][0])
        self.assertIn("change", payload["items"][0])
        self.assertIn("trend", payload["items"][0])
        self.assertIn("last_update", payload["items"][0])
        self.assertIn("error", payload["items"][0])

    def test_get_crypto_falls_back_to_last_successful_snapshot(self) -> None:
        service = MarketOverviewService()
        service._market_data_cache["crypto"] = {
            "items": [
                {
                    "symbol": "BTC",
                    "price": 73000.0,
                    "change": 0.5,
                    "trend": [70000.0, 72000.0, 73000.0],
                    "last_update": "2026-04-29T09:00:00",
                    "error": None,
                }
            ],
            "last_update": "2026-04-29T09:00:00",
            "error": None,
            "fallback_used": False,
            "source": "binance",
        }

        with patch.object(service, "_fetch_crypto_market_snapshot", side_effect=RuntimeError("binance down")):
            payload = service.get_crypto()

        self.assertTrue(payload["fallback_used"])
        self.assertEqual(payload["items"][0]["price"], 73000.0)
        self.assertEqual(payload["error"], "更新失败：已回退到最近一次有效数据")
        self.assertEqual(payload["providerHealth"]["errorSummary"], "数据源暂不可用")
        self.assertNotIn("binance down", str(payload))

    def test_get_crypto_uses_cache_within_ttl(self) -> None:
        calls = 0

        def fetcher(self: MarketOverviewService) -> dict:
            nonlocal calls
            calls += 1
            updated_at = datetime(2026, 4, 30, 10, calls, tzinfo=CN_TZ).isoformat(timespec="seconds")
            return {
                "items": [
                    {
                        "symbol": "BTC",
                        "price": 70000 + calls,
                        "change": 1.0,
                        "trend": [69000, 70000 + calls],
                        "last_update": updated_at,
                        "source": "binance",
                    }
                ],
                "last_update": updated_at,
                "source": "binance",
                "fallback_used": False,
            }

        with patch.object(MarketOverviewService, "_fetch_crypto_market_snapshot", fetcher):
            first = market.get_crypto()
            second = market.get_crypto()

        self.assertEqual(calls, 1)
        self.assertEqual(second["items"][0]["price"], first["items"][0]["price"])
        self.assertIn("isRefreshing", second)

    def test_crypto_cold_cache_fast_fallback_when_binance_slow(self) -> None:
        service = MarketOverviewService()
        service.MARKET_COLD_START_TIMEOUT_SECONDS = 0.05
        release_fetch = threading.Event()

        def fetcher() -> dict:
            release_fetch.wait(2)
            return {
                "items": [{"symbol": "BTC", "price": 71000, "change": 1, "trend": [70000, 71000], "source": "binance"}],
                "last_update": datetime(2026, 4, 30, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds"),
                "source": "binance",
                "fallback_used": False,
            }

        start = time.monotonic()
        with patch.object(service, "_fetch_crypto_market_snapshot", side_effect=fetcher):
            payload = service.get_crypto()
        elapsed = time.monotonic() - start

        self.assertLess(elapsed, 0.5)
        self.assertTrue(payload["items"])
        self.assertEqual(payload["freshness"], "fallback")
        self.assertTrue(payload["isFallback"])
        self.assertTrue(payload["isRefreshing"])
        self.assertEqual(payload["source"], "fallback")
        self.assertEqual(payload["sourceLabel"], "备用数据")
        self.assertIn("正在获取实时加密货币行情", payload["warning"])
        release_fetch.set()
        self.assertTrue(service._market_cache.wait_for_refreshes(timeout=2))

    def test_crypto_cache_hit_does_not_refetch(self) -> None:
        service = MarketOverviewService()
        calls = 0

        def fetcher() -> dict:
            nonlocal calls
            calls += 1
            return {
                "items": [{"symbol": "BTC", "price": 70000 + calls, "change": 1, "trend": [69000, 70000 + calls], "source": "binance"}],
                "last_update": datetime(2026, 4, 30, 10, calls, tzinfo=CN_TZ).isoformat(timespec="seconds"),
                "source": "binance",
                "fallback_used": False,
            }

        with patch.object(service, "_fetch_crypto_market_snapshot", side_effect=fetcher):
            first = service.get_crypto()
            second = service.get_crypto()

        self.assertEqual(calls, 1)
        self.assertEqual(second["items"][0]["price"], first["items"][0]["price"])
        self.assertFalse(second["isRefreshing"])

    def test_crypto_stale_returns_old_snapshot_and_refreshes(self) -> None:
        service = MarketOverviewService()
        old_time = datetime(2026, 4, 30, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
        new_time = datetime(2026, 4, 30, 10, 1, tzinfo=CN_TZ).isoformat(timespec="seconds")
        service._market_cache.set(
            "crypto",
            {
                "items": [{"symbol": "BTC", "price": 70000, "change": 1, "trend": [69000, 70000], "source": "binance", "last_update": old_time}],
                "last_update": old_time,
                "source": "binance",
                "fallback_used": False,
            },
            ttl_seconds=1,
        )
        entry = service._market_cache.get("crypto")
        entry.expires_at = entry.fetched_at - timedelta(seconds=1)
        release_refresh = threading.Event()

        def fetcher() -> dict:
            release_refresh.wait(2)
            return {
                "items": [{"symbol": "BTC", "price": 72000, "change": 2, "trend": [70000, 72000], "source": "binance", "last_update": new_time}],
                "last_update": new_time,
                "source": "binance",
                "fallback_used": False,
            }

        with patch.object(service, "_fetch_crypto_market_snapshot", side_effect=fetcher):
            stale = service.get_crypto()
            self.assertEqual(stale["items"][0]["price"], 70000)
            self.assertEqual(stale["source"], "binance")
            self.assertEqual(stale["sourceLabel"], "Binance")
            self.assertEqual(stale["freshness"], "stale")
            self.assertTrue(stale["isStale"])
            self.assertFalse(stale["isFallback"])
            self.assertTrue(stale["isRefreshing"])
            self.assertEqual(stale["items"][0]["freshness"], "stale")
            self.assertTrue(stale["items"][0]["isStale"])
            self.assertFalse(stale["items"][0]["isFallback"])
            release_refresh.set()
            self.assertTrue(service._market_cache.wait_for_refreshes(timeout=2))
            refreshed = service.get_crypto()

        self.assertEqual(refreshed["items"][0]["price"], 72000)
        self.assertFalse(refreshed["isRefreshing"])

    def test_crypto_fallback_shape_matches_frontend(self) -> None:
        service = MarketOverviewService()

        with patch.object(service, "_fetch_crypto_market_snapshot", side_effect=RuntimeError("binance down")):
            payload = service.get_crypto()

        symbols = {item["symbol"] for item in payload["items"]}
        self.assertTrue({"BTC", "ETH", "BNB"}.issubset(symbols))
        self.assertEqual(payload["freshness"], "fallback")
        self.assertTrue(payload["isFallback"])
        self.assertNotEqual(payload["freshness"], "live")
        for item in payload["items"]:
            self.assertIn("symbol", item)
            self.assertIn("name", item)
            self.assertIn("value", item)
            self.assertIn("changePercent", item)
            self.assertIn("sparkline", item)

    def test_crypto_real_snapshot_counts_as_real(self) -> None:
        service = MarketOverviewService()
        updated_at = datetime.now(CN_TZ).isoformat(timespec="seconds")
        snapshot = {
            "items": [
                {
                    "symbol": "BTC",
                    "label": "Bitcoin",
                    "price": 87000.0,
                    "value": 87000.0,
                    "change": 1.2,
                    "changePercent": 1.2,
                    "trend": [86000.0, 86500.0, 87000.0],
                    "source": "binance",
                    "last_update": updated_at,
                }
            ],
            "last_update": updated_at,
            "updatedAt": updated_at,
            "asOf": updated_at,
            "fallback_used": False,
            "fallbackUsed": False,
            "source": "binance",
        }

        with patch.object(service, "_fetch_crypto_market_snapshot", return_value=snapshot):
            payload = service.get_crypto()

        self.assertEqual(payload["source"], "binance")
        self.assertFalse(payload["isFallback"])
        self.assertIn(payload["freshness"], {"live", "delayed", "cached"})

        with patch.object(service, "get_crypto", return_value=payload):
            inputs = service._build_market_temperature_inputs()

        crypto_items = inputs["crypto"]["items"]
        self.assertTrue(any(item["symbol"] == "BTC" and not item["isFallback"] for item in crypto_items))
        self.assertGreater(service._summarize_market_temperature_confidence({"crypto": inputs["crypto"]})["reliableInputCount"], 0)


if __name__ == "__main__":
    unittest.main()
