# -*- coding: utf-8 -*-
"""Contract and fallback tests for China and Hong Kong flow endpoint."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from api.v1.endpoints import market
from src.services.market_data_source_registry import project_source_provenance
from src.services.market_overview_service import MarketOverviewService


class MarketCnFlowsApiTestCase(unittest.TestCase):
    def test_cn_flows_endpoint_returns_stable_contract(self) -> None:
        payload = market.get_cn_flows()

        self.assertTrue(payload["source"])
        self.assertTrue(payload["updatedAt"])
        self.assertTrue(payload["items"])
        symbols = {item["symbol"] for item in payload["items"]}
        self.assertIn("NORTHBOUND", symbols)
        self.assertIn("SOUTHBOUND", symbols)
        for item in payload["items"]:
            self.assertIsInstance(item["value"], (int, float))
            self.assertIn("changePercent", item)

    def test_cn_flows_fallback_is_not_empty_when_provider_fails(self) -> None:
        service = MarketOverviewService()

        with patch.object(service, "_fetch_cn_flows_snapshot", side_effect=RuntimeError("provider down")):
            payload = service.get_cn_flows()

        self.assertEqual(payload["source"], "fallback")
        self.assertTrue(payload["fallbackUsed"])
        self.assertTrue(payload["items"])

    def test_cn_flows_remain_fallback_and_do_not_reuse_tickflow_breadth(self) -> None:
        service = MarketOverviewService()
        service._market_cache.clear()
        MarketOverviewService._market_data_cache.clear()

        with patch(
            "src.services.market_overview_service.fetch_tickflow_cn_breadth_snapshot",
            side_effect=AssertionError("CN flows must not reuse TickFlow breadth"),
        ):
            payload = service.get_cn_flows()

        self.assertEqual(payload["source"], "fallback")
        self.assertEqual(payload["sourceLabel"], "备用数据")
        self.assertTrue(payload["fallbackUsed"])
        self.assertEqual(payload["freshness"], "fallback")
        self.assertTrue(all(item["source"] == "fallback" for item in payload["items"]))
        self.assertTrue(all(item["isFallback"] for item in payload["items"]))
        self.assertTrue(all(item["freshness"] == "fallback" for item in payload["items"]))
        self.assertNotIn("tickflow", str(payload).lower())
        self.assertNotIn("TickFlow", str(payload))

    def test_cn_flows_fallback_snapshot_stays_explicitly_non_live(self) -> None:
        payload = MarketOverviewService().get_cn_flows()

        self.assertEqual(payload["source"], "fallback")
        self.assertEqual(payload["freshness"], "fallback")
        self.assertTrue(payload["isFallback"])
        self.assertTrue(payload["fallbackUsed"])
        self.assertEqual(payload["providerHealth"]["status"], "fallback")
        self.assertTrue(all(item["source"] == "fallback" for item in payload["items"]))
        self.assertTrue(all(item["freshness"] == "fallback" for item in payload["items"]))
        self.assertTrue(all(item["isFallback"] is True for item in payload["items"]))
        self.assertFalse(any(item["freshness"] == "live" for item in payload["items"]))

    def test_cn_hk_flows_project_to_fallback_static_not_official_or_live(self) -> None:
        payload = MarketOverviewService().get_cn_flows()
        provenance = project_source_provenance(
            source=payload.get("source"),
            source_type=payload.get("sourceType"),
            source_label=payload.get("sourceLabel"),
            freshness=payload.get("freshness"),
            is_fallback=bool(payload.get("isFallback") or payload.get("fallbackUsed")),
            is_stale=bool(payload.get("isStale")),
        )

        self.assertEqual(provenance["sourceType"], "fallback_static")
        self.assertEqual(provenance["sourceLabel"], "备用数据")
        self.assertNotEqual(provenance["freshnessLabel"], "实时")
        for item in payload["items"]:
            item_provenance = project_source_provenance(
                source=item.get("source"),
                source_type=item.get("sourceType"),
                source_label=item.get("sourceLabel"),
                freshness=item.get("freshness"),
                is_fallback=bool(item.get("isFallback") or item.get("fallbackUsed")),
                is_stale=bool(item.get("isStale")),
            )
            self.assertEqual(item_provenance["sourceType"], "fallback_static")


if __name__ == "__main__":
    unittest.main()
