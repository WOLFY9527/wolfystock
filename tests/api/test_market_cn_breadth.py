# -*- coding: utf-8 -*-
"""Contract and fallback tests for China market breadth endpoint."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from api.v1.endpoints import market
from src.services.market_overview_service import MarketOverviewService


class MarketCnBreadthApiTestCase(unittest.TestCase):
    def test_cn_breadth_endpoint_returns_stable_contract(self) -> None:
        payload = market.get_cn_breadth()

        self.assertTrue(payload["source"])
        self.assertTrue(payload["updatedAt"])
        self.assertTrue(payload["items"])
        metrics = {item["symbol"]: item for item in payload["items"]}
        self.assertIn("EFFECT", metrics)
        self.assertIsInstance(metrics["EFFECT"]["value"], (int, float))
        self.assertIn("explanation", payload)

    def test_cn_breadth_fallback_is_not_empty_when_provider_fails(self) -> None:
        service = MarketOverviewService()

        with patch.object(service, "_fetch_cn_breadth_snapshot", side_effect=RuntimeError("provider down")):
            payload = service.get_cn_breadth()

        self.assertEqual(payload["source"], "fallback")
        self.assertTrue(payload["fallbackUsed"])
        self.assertTrue(payload["items"])

    def test_cn_breadth_prefers_tickflow_market_stats_when_available(self) -> None:
        service = MarketOverviewService()
        service._market_cache.clear()
        MarketOverviewService._market_data_cache.clear()
        tickflow_snapshot = {
            "source": "tickflow",
            "sourceLabel": "TickFlow",
            "sourceType": "public_api",
            "updatedAt": "2026-05-14T09:30:00+08:00",
            "asOf": "2026-05-14T09:30:00+08:00",
            "advancers": 3210,
            "decliners": 1490,
            "limitUp": 88,
            "limitDown": 14,
            "advRatio": 66.6,
            "effect": 67,
        }

        with patch(
            "src.services.market_overview_service.fetch_tickflow_cn_breadth_snapshot",
            return_value=tickflow_snapshot,
        ):
            payload = service.get_cn_breadth()

        metrics = {item["symbol"]: item for item in payload["items"]}

        self.assertEqual(payload["source"], "tickflow")
        self.assertEqual(payload["sourceLabel"], "TickFlow")
        self.assertEqual(payload["sourceType"], "public_api")
        self.assertEqual(payload["asOf"], "2026-05-14T09:30:00+08:00")
        self.assertFalse(payload["fallbackUsed"])
        self.assertEqual(
            set(metrics),
            {"EFFECT", "ADVANCERS", "DECLINERS", "LIMIT_UP", "LIMIT_DOWN", "ADV_RATIO"},
        )
        self.assertEqual(metrics["ADVANCERS"]["value"], 3210)
        self.assertEqual(metrics["DECLINERS"]["value"], 1490)
        self.assertEqual(metrics["LIMIT_UP"]["value"], 88)
        self.assertEqual(metrics["LIMIT_DOWN"]["value"], 14)
        self.assertEqual(metrics["ADV_RATIO"]["value"], 66.6)
        self.assertEqual(metrics["EFFECT"]["value"], 67)
        self.assertFalse(any(item["isFallback"] for item in payload["items"]))
        self.assertTrue(payload["explanation"])

    def test_cn_breadth_sanitizes_tickflow_failure_reason(self) -> None:
        service = MarketOverviewService()
        service._market_cache.clear()
        MarketOverviewService._market_data_cache.clear()

        with patch(
            "src.services.market_overview_service.fetch_tickflow_cn_breadth_snapshot",
            side_effect=RuntimeError(
                "tickflow_permission_unavailable token=SECRET url=https://api.tickflow.test/raw"
            ),
        ):
            payload = service.get_cn_breadth()

        self.assertTrue(payload["fallbackUsed"])
        self.assertEqual(payload["freshness"], "fallback")
        self.assertEqual(payload["lastError"], "数据源暂不可用")
        self.assertEqual(payload["fallbackReason"], "tickflow_permission_unavailable")
        self.assertNotIn("SECRET", str(payload))
        self.assertNotIn("https://api.tickflow.test/raw", str(payload))

    def test_cn_breadth_keeps_tickflow_provenance_bounded_and_non_official(self) -> None:
        service = MarketOverviewService()
        service._market_cache.clear()
        MarketOverviewService._market_data_cache.clear()

        with patch(
            "src.services.market_overview_service.fetch_tickflow_cn_breadth_snapshot",
            return_value={
                "source": "tickflow",
                "sourceLabel": "TickFlow",
                "sourceType": "public_api",
                "updatedAt": "2026-05-14T09:30:00+08:00",
                "asOf": "2026-05-14T09:30:00+08:00",
                "advancers": 2800,
                "decliners": 1700,
                "limitUp": 72,
                "limitDown": 19,
                "advRatio": 61.2,
                "effect": 61,
            },
        ):
            payload = service.get_cn_breadth()

        self.assertEqual(payload["source"], "tickflow")
        self.assertEqual(payload["sourceLabel"], "TickFlow")
        self.assertEqual(payload["sourceType"], "public_api")
        self.assertNotIn(payload["sourceType"], {"official_public", "exchange_public"})
        self.assertTrue(all(item["source"] == "tickflow" for item in payload["items"]))
        self.assertTrue(all(item["sourceLabel"] == "TickFlow" for item in payload["items"]))
        self.assertTrue(all(item["sourceType"] == "public_api" for item in payload["items"]))

    def test_cn_breadth_falls_back_for_tickflow_guard_reason_codes(self) -> None:
        service = MarketOverviewService()
        service._market_cache.clear()
        MarketOverviewService._market_data_cache.clear()

        for reason in (
            "tickflow_not_configured",
            "tickflow_permission_unavailable",
            "tickflow_market_stats_empty",
            "tickflow_market_stats_malformed",
        ):
            with self.subTest(reason=reason):
                service._market_cache.clear()
                MarketOverviewService._market_data_cache.clear()
                with patch(
                    "src.services.market_overview_service.fetch_tickflow_cn_breadth_snapshot",
                    side_effect=RuntimeError(reason),
                ):
                    payload = service.get_cn_breadth()

                self.assertEqual(payload["source"], "fallback")
                self.assertTrue(payload["fallbackUsed"])
                self.assertEqual(payload["fallbackReason"], reason)
                self.assertTrue(payload["items"])


if __name__ == "__main__":
    unittest.main()
