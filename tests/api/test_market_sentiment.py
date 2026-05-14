# -*- coding: utf-8 -*-
"""Contract and fallback tests for market sentiment endpoint."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

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
        service._market_data_cache[service.MARKET_SENTIMENT_CACHE_KEY] = {
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

    def test_sentiment_prefers_cnn_before_alternative(self) -> None:
        service = MarketOverviewService()

        with patch.object(
            service,
            "_fetch_cnn_fear_greed_snapshot",
            return_value={"history": [{"value": 20}, {"value": 30}, {"value": 40}], "source": "cnn"},
        ) as cnn_fetch, patch.object(
            service,
            "_fetch_alternative_fear_greed_snapshot",
            side_effect=AssertionError("Alternative.me should not run when CNN succeeds"),
        ) as alternative_fetch:
            payload = service._fetch_market_sentiment_snapshot()

        cnn_fetch.assert_called_once_with()
        alternative_fetch.assert_not_called()
        self.assertEqual(payload["source"], "cnn")
        self.assertIsNone(payload["error"])
        self.assertTrue(all(item["source"] == "cnn" for item in payload["items"]))

    def test_sentiment_uses_alternative_only_after_cnn_failure(self) -> None:
        service = MarketOverviewService()

        with patch.object(
            service,
            "_fetch_cnn_fear_greed_snapshot",
            side_effect=RuntimeError("cnn unavailable"),
        ) as cnn_fetch, patch.object(
            service,
            "_fetch_alternative_fear_greed_snapshot",
            return_value={"history": [{"value": 22}, {"value": 24}, {"value": 35}], "source": "alternative_me"},
        ) as alternative_fetch:
            payload = service._fetch_market_sentiment_snapshot()

        cnn_fetch.assert_called_once_with()
        alternative_fetch.assert_called_once_with()
        self.assertEqual(payload["source"], "alternative_me")
        self.assertEqual(payload["error"], "cnn unavailable")
        self.assertTrue(all(item["source"] == "alternative_me" for item in payload["items"]))

    def test_get_sentiment_service_owns_provider_order_and_public_metadata_from_transport_payloads(self) -> None:
        service = MarketOverviewService()
        alternative_payload = {
            "data": [
                {"value": "21"},
                {"value": "28"},
                {"value": "34"},
            ]
        }

        with patch(
            "src.services.market_overview_service.fetch_cnn_fear_greed_payload",
            side_effect=RuntimeError("cnn unavailable"),
        ) as cnn_fetch, patch(
            "src.services.market_overview_service.fetch_alternative_fear_greed_payload",
            return_value=alternative_payload,
        ) as alternative_fetch:
            payload = service.get_market_sentiment()

        cnn_fetch.assert_called_once_with()
        alternative_fetch.assert_called_once_with()
        self.assertEqual(payload["source"], "alternative_me")
        self.assertEqual(payload["sourceLabel"], "Alternative.me")
        self.assertFalse(payload["fallback_used"])
        self.assertFalse(payload["isFallback"])
        self.assertEqual(payload["providerHealth"]["provider"], "alternative_me")
        self.assertIn(payload["providerHealth"]["status"], {"live", "cache"})
        self.assertTrue(all(item["source"] == "alternative_me" for item in payload["items"]))
        self.assertTrue(all(item["sourceLabel"] == "Alternative.me" for item in payload["items"]))


class _ExecutionLogStub:
    def record_market_overview_fetch(self, **_: object) -> str:
        return "log-sentiment"


def test_market_sentiment_cache_key_does_not_accept_legacy_overview_item_family() -> None:
    service = MarketOverviewService()
    service._market_cache.clear()
    service._market_data_cache.clear()
    service._market_cache.set(
        "sentiment",
        {
            "panel_name": "MarketSentimentCard",
            "last_refresh_at": "2026-05-15T10:00:00+08:00",
            "status": "success",
            "source": "cnn",
            "items": [
                {
                    "symbol": "FGI",
                    "label": "Fear & Greed",
                    "value": 52,
                    "unit": "score",
                    "change_pct": -3.0,
                    "trend": [60, 55, 52],
                    "risk_direction": "increasing",
                    "source": "cnn",
                }
            ],
        },
        ttl_seconds=1800,
    )

    with patch.object(
        service,
        "_fetch_market_sentiment_snapshot",
        return_value={
            "items": [
                {
                    "symbol": "FGI",
                    "label": "Fear & Greed",
                    "price": 48,
                    "change": -2.0,
                    "trend": [55, 52, 48],
                    "last_update": "2026-05-15T10:01:00+08:00",
                    "error": None,
                    "source": "cnn",
                }
            ],
            "last_update": "2026-05-15T10:01:00+08:00",
            "error": None,
            "fallback_used": False,
            "source": "cnn",
        },
    ), patch("src.services.market_overview_service.ExecutionLogService", _ExecutionLogStub):
        payload = service.get_market_sentiment()

    first_item = payload["items"][0]
    assert first_item["price"] == 48
    assert "price" in first_item
    assert "change" in first_item
    assert "value" not in first_item
    assert "change_pct" not in first_item


def test_market_overview_sentiment_cache_key_does_not_accept_market_snapshot_item_family() -> None:
    service = MarketOverviewService()
    service._market_cache.clear()
    service._market_data_cache.clear()
    service._market_cache.set(
        "sentiment",
        {
            "items": [
                {
                    "symbol": "FGI",
                    "label": "Fear & Greed",
                    "price": 52,
                    "change": -3.0,
                    "trend": [60, 55, 52],
                    "last_update": "2026-05-15T10:00:00+08:00",
                    "error": None,
                    "source": "cnn",
                }
            ],
            "last_update": "2026-05-15T10:00:00+08:00",
            "error": None,
            "fallback_used": False,
            "source": "cnn",
        },
        ttl_seconds=1800,
    )

    with patch.object(
        service,
        "_fetch_sentiment",
        return_value={
            "panel_name": "MarketSentimentCard",
            "last_refresh_at": "2026-05-15T10:01:00+08:00",
            "status": "success",
            "error_message": None,
            "source": "cnn",
            "items": [
                {
                    "symbol": "FGI",
                    "label": "Fear & Greed",
                    "value": 48,
                    "unit": "score",
                    "change_pct": -2.0,
                    "trend": [55, 52, 48],
                    "risk_direction": "increasing",
                    "source": "cnn",
                }
            ],
        },
    ), patch("src.services.market_overview_service.ExecutionLogService", _ExecutionLogStub):
        payload = service.get_sentiment()

    first_item = payload["items"][0]
    assert first_item["value"] == 48
    assert "value" in first_item
    assert "change_pct" in first_item
    assert "price" not in first_item
    assert "change" not in first_item


if __name__ == "__main__":
    unittest.main()
