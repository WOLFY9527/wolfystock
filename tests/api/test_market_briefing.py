# -*- coding: utf-8 -*-
"""Contract and fallback tests for market briefing endpoint."""

from __future__ import annotations

import copy
import unittest
from unittest.mock import MagicMock, patch

from api.v1.endpoints import market
from src.services.market_overview_service import MarketOverviewService


class MarketBriefingApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        MarketOverviewService._market_cache.clear()
        MarketOverviewService._market_data_cache.clear()

    def test_get_market_briefing_returns_rule_items(self) -> None:
        service = MagicMock()
        service.get_market_briefing.return_value = {
            "source": "computed",
            "updatedAt": "2026-04-30T10:00:00+08:00",
            "items": [
                {"title": "美股风险偏好偏暖", "message": "主要指数走强。", "severity": "positive", "category": "us"},
                {"title": "A股赚钱效应中性", "message": "市场宽度一般。", "severity": "neutral", "category": "cn"},
                {"title": "宏观压力仍需关注", "message": "美元走强。", "severity": "warning", "category": "macro"},
            ],
        }

        with patch("api.v1.endpoints.market.MarketOverviewService", return_value=service):
            payload = market.get_market_briefing()

        self.assertEqual(payload["source"], "computed")
        self.assertTrue(payload["updatedAt"])
        self.assertGreaterEqual(len(payload["items"]), 3)
        for item in payload["items"]:
            self.assertIn(item["severity"], {"positive", "neutral", "warning", "risk"})
            self.assertTrue(item["title"])
            self.assertTrue(item["message"])
            self.assertTrue(item["category"])

    def test_get_market_briefing_falls_back_when_inputs_fail(self) -> None:
        service = MarketOverviewService()
        with patch.object(service, "_build_market_temperature_inputs", side_effect=RuntimeError("provider down")):
            payload = service.get_market_briefing()

        self.assertTrue(payload["updatedAt"])
        self.assertGreaterEqual(len(payload["items"]), 3)
        self.assertFalse(payload["isReliable"])
        self.assertEqual(payload["confidence"], 0.0)
        self.assertIn("真实数据不足", payload["warning"])
        self.assertFalse(payload["temperatureAvailable"])
        self.assertTrue(payload["insufficientReliableInputs"])
        self.assertEqual(payload["disabledReason"], "insufficient_reliable_inputs")
        self.assertEqual(payload["unavailableReason"], "insufficient_reliable_inputs")
        self.assertFalse(payload["conclusionAllowed"])
        for item in payload["items"]:
            self.assertIn(item["severity"], {"neutral", "warning", "risk"})
            self.assertNotEqual(item["severity"], "positive")
            self.assertIn("confidence", item)

    def test_get_market_briefing_fallback_only_avoids_positive_strong_judgement(self) -> None:
        service = MarketOverviewService()
        with patch.object(service, "_build_market_temperature_inputs", return_value=service._fallback_market_temperature_inputs()):
            payload = service.get_market_briefing()

        self.assertFalse(payload["isReliable"])
        self.assertEqual(payload["source"], "fallback")
        self.assertEqual(payload["freshness"], "fallback")
        self.assertEqual(payload["confidence"], 0.0)
        self.assertIn("暂不生成强市场判断", payload["warning"])
        self.assertFalse(payload["temperatureAvailable"])
        self.assertTrue(payload["insufficientReliableInputs"])
        self.assertEqual(payload["disabledReason"], "insufficient_reliable_inputs")
        self.assertEqual(payload["unavailableReason"], "insufficient_reliable_inputs")
        self.assertFalse(payload["conclusionAllowed"])
        self.assertTrue(any("暂不生成强市场判断" in item["message"] for item in payload["items"]))
        self.assertFalse(any(item["severity"] == "positive" for item in payload["items"]))
        self.assertTrue(all(item["severity"] in {"warning", "neutral", "risk"} for item in payload["items"]))

    def test_get_market_briefing_low_coverage_mixed_inputs_avoids_positive_strong_judgement(self) -> None:
        service = MarketOverviewService()
        inputs = copy.deepcopy(service._fallback_market_temperature_inputs())

        for key, source in (("indices", "sina"), ("rates", "sina"), ("crypto", "binance")):
            panel = inputs[key]
            panel["source"] = source
            panel["sourceLabel"] = "实时数据"
            panel["fallbackUsed"] = False
            panel["isFallback"] = False
            panel["freshness"] = "live"
            for idx, item in enumerate(panel.get("items", [])):
                if idx != 0:
                    continue
                item["source"] = source
                item["sourceLabel"] = "实时数据"
                item["fallbackUsed"] = False
                item["isFallback"] = False
                item["freshness"] = "live"

        with patch.object(service, "_build_market_temperature_inputs", return_value=inputs):
            payload = service.get_market_briefing()

        self.assertFalse(payload["isReliable"])
        self.assertLess(payload["confidence"], 0.25)
        self.assertEqual(payload["source"], "mixed")
        self.assertEqual(payload["sourceLabel"], "多来源")
        self.assertEqual(payload["sourceType"], "")
        self.assertEqual(payload["freshness"], "partial")
        self.assertTrue(payload["fallbackUsed"])
        self.assertFalse(payload["isFallback"])
        self.assertEqual(payload["providerHealth"]["status"], "partial")
        self.assertIn("暂不生成强市场判断", payload["warning"])
        self.assertFalse(payload["temperatureAvailable"])
        self.assertTrue(payload["insufficientReliableInputs"])
        self.assertEqual(payload["disabledReason"], "insufficient_reliable_inputs")
        self.assertEqual(payload["unavailableReason"], "insufficient_reliable_inputs")
        self.assertFalse(payload["conclusionAllowed"])
        self.assertFalse(any(item["severity"] == "positive" for item in payload["items"]))
        self.assertEqual(
            [(item["title"], item["message"], item["severity"], item["category"]) for item in payload["items"]],
            [
                ("当前真实数据不足", "当前真实数据不足，暂不生成强市场判断。", "warning", "risk"),
                ("备用数据已降级", "备用示例数据仅用于保持界面结构，不参与市场温度评分。", "neutral", "risk"),
                ("等待真实行情源", "接入足够真实输入后，再恢复风险偏好、赚钱效应和流动性判断。", "neutral", "risk"),
            ],
        )

    def test_get_market_briefing_mixed_enough_data_can_still_be_reliable(self) -> None:
        service = MarketOverviewService()
        inputs = copy.deepcopy(service._fallback_market_temperature_inputs())

        for key, source in (("indices", "sina"), ("rates", "sina"), ("crypto", "binance")):
            panel = inputs[key]
            panel["source"] = source
            panel["sourceLabel"] = "实时数据"
            panel["fallbackUsed"] = False
            panel["isFallback"] = False
            panel["freshness"] = "live"
            for item in panel.get("items", []):
                item["source"] = source
                item["sourceLabel"] = "实时数据"
                item["fallbackUsed"] = False
                item["isFallback"] = False
                item["freshness"] = "live"

        inputs["fx"]["source"] = "fallback"
        inputs["fx"]["sourceLabel"] = "备用数据"
        inputs["fx"]["fallbackUsed"] = True
        inputs["fx"]["isFallback"] = True
        inputs["fx"]["freshness"] = "fallback"

        with patch.object(service, "_build_market_temperature_inputs", return_value=inputs):
            payload = service.get_market_briefing()

        self.assertTrue(payload["isReliable"])
        self.assertTrue(payload["temperatureAvailable"])
        self.assertTrue(payload["conclusionAllowed"])
        self.assertIsNone(payload["disabledReason"])
        self.assertEqual(payload["source"], "mixed")
        self.assertGreater(payload["confidence"], 0.25)
        self.assertEqual(payload["warning"], "部分解读已排除备用数据。")
        self.assertFalse(any(item["severity"] == "risk" for item in payload["items"][:-1]))

    def test_get_market_briefing_adds_source_authority_diagnostics_for_non_authoritative_inputs(self) -> None:
        service = MarketOverviewService()
        inputs = copy.deepcopy(service._fallback_market_temperature_inputs())

        inputs["indices"]["items"][0].update(
            {
                "source": "sec_edgar",
                "sourceType": "official_public",
                "freshness": "live",
                "isFallback": False,
            }
        )
        inputs["futures"]["items"][0].update(
            {
                "source": "yahooquery",
                "sourceType": "unofficial_proxy",
                "freshness": "delayed",
                "isFallback": False,
            }
        )
        inputs["crypto"]["items"][0].update(
            {
                "source": "coinbase_public",
                "sourceType": "exchange_public",
                "freshness": "live",
                "isFallback": False,
            }
        )

        with patch.object(service, "_build_market_temperature_inputs", return_value=inputs):
            payload = service.get_market_briefing()

        diagnostics = payload["sourceAuthorityDiagnostics"]
        self.assertEqual(diagnostics["useCase"], "market_briefing")
        self.assertGreaterEqual(diagnostics["nonAuthoritativeInputCount"], 3)

        items_by_symbol = {item["symbol"]: item for item in diagnostics["items"]}

        self.assertFalse(items_by_symbol["000001.SH"]["sourceAuthorityAllowed"])
        self.assertTrue(items_by_symbol["000001.SH"]["sourceAuthorityRouteRejected"])
        self.assertIn("provider_forbidden_for_use_case", items_by_symbol["000001.SH"]["routeRejectedReasonCodes"])
        self.assertEqual(items_by_symbol["000001.SH"]["sourceAuthorityRouter"]["request"]["useCase"], "market_briefing")
        self.assertEqual(items_by_symbol["000001.SH"]["sourceAuthorityRouter"]["request"]["capability"], "index_quote")

        self.assertFalse(items_by_symbol["NQ"]["sourceAuthorityAllowed"])
        self.assertFalse(items_by_symbol["NQ"]["sourceAuthorityRouteRejected"])
        self.assertEqual(items_by_symbol["NQ"]["sourceAuthorityReason"], "proxy_context_only")
        self.assertEqual(items_by_symbol["NQ"]["sourceAuthorityRouter"]["request"]["capability"], "futures")
        self.assertFalse(items_by_symbol["NQ"]["sourceAuthorityRouter"]["request"]["allowNetwork"])

        self.assertFalse(items_by_symbol["BTC"]["sourceAuthorityAllowed"])
        self.assertTrue(items_by_symbol["BTC"]["sourceAuthorityRouteRejected"])
        self.assertIn("provider_forbidden_for_use_case", items_by_symbol["BTC"]["routeRejectedReasonCodes"])
        self.assertEqual(items_by_symbol["BTC"]["sourceAuthorityRouter"]["request"]["capability"], "crypto_ticker")


if __name__ == "__main__":
    unittest.main()
