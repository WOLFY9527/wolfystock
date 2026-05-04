# -*- coding: utf-8 -*-
"""Contract and fallback tests for market sentiment endpoint."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from api.v1.endpoints import market
from src.services.market_overview_service import MarketOverviewService


CN_TZ = timezone(timedelta(hours=8))


class MarketSentimentApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        MarketOverviewService._market_cache.clear()
        MarketOverviewService._market_data_cache.clear()

    def test_get_sentiment_returns_contract_payload(self) -> None:
        service = MagicMock()
        service.get_market_sentiment.return_value = {
            "items": [
                {
                    "symbol": "FGI",
                    "price": 26,
                    "change": -7.0,
                    "trend": [42, 38, 33, 26],
                    "last_update": "2026-04-29T10:00:00",
                    "error": None,
                }
            ],
            "last_update": "2026-04-29T10:00:00",
            "error": None,
            "fallback_used": False,
            "source": "alternative_me",
        }

        with patch("api.v1.endpoints.market.MarketOverviewService", return_value=service):
            payload = market.get_sentiment()

        self.assertEqual(payload["source"], "alternative_me")
        self.assertFalse(payload["fallback_used"])
        self.assertEqual(payload["items"][0]["symbol"], "FGI")
        self.assertIn("price", payload["items"][0])
        self.assertIn("change", payload["items"][0])
        self.assertIn("trend", payload["items"][0])
        self.assertIn("last_update", payload["items"][0])
        self.assertIn("error", payload["items"][0])

    def test_get_sentiment_falls_back_to_last_successful_snapshot(self) -> None:
        service = MarketOverviewService()
        service._market_data_cache["sentiment"] = {
            "items": [
                {
                    "symbol": "FGI",
                    "price": 33,
                    "change": -2.0,
                    "trend": [38, 36, 33],
                    "last_update": "2026-04-29T09:00:00",
                    "error": None,
                }
            ],
            "last_update": "2026-04-29T09:00:00",
            "error": None,
            "fallback_used": False,
            "source": "alternative_me",
        }

        with patch.object(service, "_fetch_market_sentiment_snapshot", side_effect=RuntimeError("cnn unavailable")):
            payload = service.get_market_sentiment()

        self.assertTrue(payload["fallback_used"])
        self.assertEqual(payload["items"][0]["price"], 33)
        self.assertEqual(payload["error"], "更新失败：已回退到最近一次有效数据")
        self.assertEqual(payload["providerHealth"]["errorSummary"], "数据源暂不可用")
        self.assertNotIn("cnn unavailable", str(payload))

    def test_get_sentiment_uses_cache_within_ttl(self) -> None:
        calls = 0

        def fetcher(self: MarketOverviewService) -> dict:
            nonlocal calls
            calls += 1
            updated_at = datetime(2026, 4, 30, 10, calls, tzinfo=CN_TZ).isoformat(timespec="seconds")
            return {
                "items": [
                    {
                        "symbol": "FGI",
                        "price": 50 + calls,
                        "change": 1.0,
                        "trend": [48, 50 + calls],
                        "last_update": updated_at,
                        "source": "cnn",
                    }
                ],
                "last_update": updated_at,
                "source": "cnn",
                "fallback_used": False,
            }

        with patch.object(MarketOverviewService, "_fetch_market_sentiment_snapshot", fetcher):
            first = market.get_sentiment()
            second = market.get_sentiment()

        self.assertEqual(calls, 1)
        self.assertEqual(second["items"][0]["price"], first["items"][0]["price"])
        self.assertIn("isRefreshing", second)


if __name__ == "__main__":
    unittest.main()
