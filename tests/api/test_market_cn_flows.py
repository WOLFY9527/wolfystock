# -*- coding: utf-8 -*-
"""Contract and fallback tests for China and Hong Kong flow endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from api.v1.endpoints import market
from src.services.cn_hk_flow_contracts import AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID
from src.services.market_data_source_registry import project_source_provenance
from src.services.market_overview_service import MarketOverviewService


CN_TZ = timezone(timedelta(hours=8))


def _clear_cn_flow_caches() -> None:
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.pop("cn_flows", None)


def _authorized_provider_payload(*, as_of: str) -> dict[str, object]:
    return {
        "providerId": AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID,
        "source": AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID,
        "sourceType": "authorized_licensed_feed",
        "sourceTier": "authorized_licensed_feed",
        "asOf": as_of,
        "tradingDate": "2026-05-23",
        "session": "morning",
        "freshness": "delayed",
        "observations": [
            {"symbol": "NORTHBOUND", "value": 42.6, "unit": "亿 CNY", "currency": "CNY"},
            {"symbol": "SOUTHBOUND", "value": 28.4, "unit": "亿 HKD", "currency": "HKD"},
            {"symbol": "CN_ETF", "value": 15.8, "unit": "亿 CNY", "currency": "CNY"},
        ],
    }


class MarketCnFlowsApiTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        _clear_cn_flow_caches()

    def test_cn_flows_endpoint_returns_stable_contract(self) -> None:
        _clear_cn_flow_caches()
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
        _clear_cn_flow_caches()
        service = MarketOverviewService()

        with patch.object(service, "_fetch_cn_flows_snapshot", side_effect=RuntimeError("provider down")):
            payload = service.get_cn_flows()

        self.assertEqual(payload["source"], "fallback")
        self.assertTrue(payload["fallbackUsed"])
        self.assertTrue(payload["items"])

    def test_cn_flows_remain_fallback_and_do_not_reuse_tickflow_breadth(self) -> None:
        _clear_cn_flow_caches()
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
        _clear_cn_flow_caches()
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
        _clear_cn_flow_caches()
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

    def test_authorized_cn_hk_flow_provider_result_surfaces_diagnostic_metadata(self) -> None:
        _clear_cn_flow_caches()
        as_of = datetime.now(CN_TZ).replace(microsecond=0).isoformat()
        service = MarketOverviewService(
            cn_hk_connect_flow_provider=lambda: _authorized_provider_payload(as_of=as_of),
        )

        payload = service.get_cn_flows()

        self.assertEqual(payload["providerId"], AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID)
        self.assertEqual(payload["source"], AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID)
        self.assertEqual(payload["sourceType"], "authorized_licensed_feed")
        self.assertEqual(payload["sourceTier"], "authorized_licensed_feed")
        self.assertEqual(payload["freshness"], "delayed")
        self.assertFalse(payload["fallbackUsed"])
        self.assertFalse(payload["isFallback"])
        self.assertTrue(payload["cacheOnly"])
        self.assertTrue(payload["observationOnly"])
        self.assertTrue(payload["sourceAuthorityAllowed"])
        self.assertFalse(payload["scoreContributionAllowed"])
        self.assertEqual(payload["fulfilledMetrics"], ["NORTHBOUND", "SOUTHBOUND", "CN_ETF"])
        self.assertEqual(payload["missingMetrics"], ["MAINLAND_MAIN", "MARGIN_BALANCE"])
        self.assertEqual(payload["coverageRatio"], 0.6)
        self.assertIn("sourceFreshnessEvidence", payload)
        self.assertEqual(payload["providerHealth"]["provider"], AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID)
        self.assertIn(payload["providerHealth"]["status"], {"cache", "partial"})
        northbound = next(item for item in payload["items"] if item["symbol"] == "NORTHBOUND")
        self.assertEqual(northbound["source"], AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID)
        self.assertEqual(northbound["sourceType"], "authorized_licensed_feed")
        self.assertTrue(northbound["observationOnly"])
        self.assertFalse(northbound["scoreContributionAllowed"])

    def test_authorized_cn_hk_flow_provider_failures_fall_back_without_raw_payload(self) -> None:
        for provider_payload in (
            {"observations": []},
            {"errorCode": "permission_denied", "message": "403 SECRET"},
            {
                "asOf": datetime(2026, 5, 20, tzinfo=CN_TZ).isoformat(),
                "observations": [
                    {"symbol": "NORTHBOUND", "value": 42.6, "unit": "亿 CNY"},
                    {"symbol": "SOUTHBOUND", "value": 28.4, "unit": "亿 HKD"},
                ],
            },
        ):
            _clear_cn_flow_caches()
            service = MarketOverviewService(cn_hk_connect_flow_provider=lambda payload=provider_payload: payload)

            payload = service.get_cn_flows()

            self.assertEqual(payload["source"], "fallback")
            self.assertTrue(payload["fallbackUsed"])
            provenance = project_source_provenance(
                source=payload.get("source"),
                source_type=payload.get("sourceType"),
                source_label=payload.get("sourceLabel"),
                freshness=payload.get("freshness"),
                is_fallback=bool(payload.get("isFallback") or payload.get("fallbackUsed")),
                is_stale=bool(payload.get("isStale")),
            )
            self.assertEqual(provenance["sourceType"], "fallback_static")
            self.assertNotIn("SECRET", str(payload))
            self.assertNotIn("providerPayload", str(payload))


if __name__ == "__main__":
    unittest.main()
