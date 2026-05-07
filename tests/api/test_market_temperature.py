# -*- coding: utf-8 -*-
"""Contract and fallback tests for market temperature endpoint."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from api.v1.endpoints import market
from src.services.market_overview_service import MarketOverviewService, classify_market_payload_reliability


class MarketTemperatureApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        MarketOverviewService._market_cache.clear()
        MarketOverviewService._market_data_cache.clear()

    def test_get_temperature_returns_stable_scores(self) -> None:
        service = MagicMock()
        service.get_market_temperature.return_value = {
            "source": "computed",
            "updatedAt": "2026-04-30T10:00:00+08:00",
            "scores": {
                "overall": {"value": 62, "label": "偏暖", "trend": "improving", "description": "风险偏好改善。"},
                "usRiskAppetite": {"value": 68, "label": "偏暖", "trend": "improving", "description": "美股改善。"},
                "cnMoneyEffect": {"value": 55, "label": "中性", "trend": "stable", "description": "市场宽度一般。"},
                "macroPressure": {"value": 58, "label": "中性偏高", "trend": "rising", "description": "利率压力。"},
                "liquidity": {"value": 52, "label": "中性", "trend": "stable", "description": "资金平稳。"},
            },
        }

        with patch("api.v1.endpoints.market.MarketOverviewService", return_value=service):
            payload = market.get_temperature()

        self.assertEqual(payload["source"], "computed")
        self.assertTrue(payload["updatedAt"])
        self.assertEqual(set(payload["scores"].keys()), {"overall", "usRiskAppetite", "cnMoneyEffect", "macroPressure", "liquidity"})
        for score in payload["scores"].values():
            self.assertGreaterEqual(score["value"], 0)
            self.assertLessEqual(score["value"], 100)
            self.assertTrue(score["label"])
            self.assertTrue(score["description"])

    def test_get_temperature_falls_back_when_inputs_fail(self) -> None:
        service = MarketOverviewService()
        with patch.object(service, "_build_market_temperature_inputs", side_effect=RuntimeError("provider down")):
            payload = service.get_market_temperature()

        self.assertIn(payload["source"], {"computed", "fallback", "mixed"})
        self.assertTrue(payload["updatedAt"])
        self.assertEqual(payload["freshness"], "fallback")
        self.assertTrue(payload["isFallback"])
        self.assertIn("真实数据不足", payload["warning"])
        self.assertEqual(payload["confidence"], 0.0)
        self.assertEqual(payload["reliableInputCount"], 0)
        self.assertGreater(payload["fallbackInputCount"], 0)
        self.assertGreater(payload["excludedInputCount"], 0)
        self.assertFalse(payload["isReliable"])
        self.assertEqual(set(payload["scores"].keys()), {"overall", "usRiskAppetite", "cnMoneyEffect", "macroPressure", "liquidity"})
        for score in payload["scores"].values():
            self.assertGreaterEqual(score["value"], 0)
            self.assertLessEqual(score["value"], 100)
            self.assertEqual(score["label"], "数据不足")

    def test_fallback_inputs_do_not_drive_warm_temperature(self) -> None:
        service = MarketOverviewService()
        with patch.object(service, "_build_market_temperature_inputs", return_value=service._fallback_market_temperature_inputs()):
            payload = service.get_market_temperature()

        self.assertFalse(payload["isReliable"])
        self.assertEqual(payload["scores"]["overall"]["label"], "数据不足")
        self.assertNotIn(payload["scores"]["overall"]["label"], {"偏暖", "过热"})

    def test_mixed_input_confidence_averages_item_level_sources(self) -> None:
        service = MarketOverviewService()
        inputs = {
            "indices": {
                "items": [
                    {"symbol": "SPX", "freshness": "live", "source": "yahoo", "value": 1},
                    {"symbol": "CSI300", "freshness": "cached", "source": "sina", "value": 1},
                    {"symbol": "SSE", "source": "fallback", "value": 1},
                ]
            },
            "rates": {"items": [{"symbol": "US10Y", "freshness": "stale", "value": 1}]},
        }

        trust = service._summarize_market_temperature_confidence(inputs)

        self.assertEqual(trust["reliableInputCount"], 2)
        self.assertEqual(trust["fallbackInputCount"], 2)
        self.assertEqual(trust["excludedInputCount"], 2)
        self.assertAlmostEqual(trust["confidence"], 0.4, places=2)

    def test_reliable_mixed_temperature_excludes_fallback_items(self) -> None:
        service = MarketOverviewService()
        live_item = {"freshness": "live", "source": "sina"}
        inputs = {
            "futures": {"items": [
                {"symbol": "NQ", "changePercent": 1.2, **live_item},
                {"symbol": "ES", "changePercent": 1.0, **live_item},
                {"symbol": "YM", "changePercent": 0.8, **live_item},
                {"symbol": "RTY", "changePercent": 0.7, **live_item},
                {"symbol": "NQ", "changePercent": -20, "source": "fallback"},
            ]},
            "sentiment": {"items": [{"symbol": "FGI", "value": 70, **live_item}]},
            "rates": {"items": [{"symbol": "US10Y", "changePercent": -0.4, **live_item}, {"symbol": "DXY", "changePercent": -0.5, **live_item}]},
            "fx": {"items": [{"symbol": "DXY", "changePercent": -0.5, **live_item}]},
        }

        with patch.object(service, "_build_market_temperature_inputs", return_value=inputs):
            payload = service.get_market_temperature()

        self.assertTrue(payload["isReliable"])
        self.assertEqual(payload["excludedInputCount"], 1)
        self.assertGreater(payload["scores"]["usRiskAppetite"]["value"], 40)

    def test_temperature_counts_real_inputs(self) -> None:
        service = MarketOverviewService()
        inputs = {
            "indices": {"items": [{"symbol": "000001.SH", "value": 4107, "changePercent": 0.7, "source": "sina", "freshness": "live", "isFallback": False}]},
            "crypto": {"items": [{"symbol": "BTC", "value": 87000, "changePercent": 1.4, "source": "binance", "freshness": "live", "isFallback": False}]},
            "rates": {"items": [{"symbol": "VIX", "value": 16, "changePercent": -2.2, "source": "yahoo", "freshness": "delayed", "isFallback": False}]},
            "fx": {"items": [{"symbol": "DXY", "value": 104, "changePercent": -0.3, "source": "fallback", "freshness": "fallback", "isFallback": True}]},
        }

        with patch.object(service, "_build_market_temperature_inputs", return_value=inputs):
            payload = service.get_market_temperature()

        self.assertGreater(payload["reliableInputCount"], 0)
        self.assertEqual(payload["fallbackInputCount"], 1)
        self.assertEqual(payload["excludedInputCount"], 1)
        self.assertGreater(payload["confidence"], 0)

    def test_missing_required_market_inputs_blocks_temperature_decision_output(self) -> None:
        service = MarketOverviewService()
        inputs = {
            "indices": {"items": [{"symbol": "000001.SH", "value": 4107, "changePercent": 0.7, "source": "sina", "freshness": "live", "isFallback": False}]},
            "crypto": {"items": [{"symbol": "BTC", "value": 87000, "changePercent": 1.4, "source": "binance", "freshness": "live", "isFallback": False}]},
            "rates": {"items": [{"symbol": "US10Y", "source": "fallback", "freshness": "fallback", "isFallback": True}]},
            "fx": {"items": []},
            "futures": {"items": []},
        }

        with patch.object(service, "_build_market_temperature_inputs", return_value=inputs):
            payload = service.get_market_temperature()

        self.assertEqual(payload["reliableInputCount"], 2)
        self.assertGreater(payload["fallbackInputCount"], 0)
        self.assertFalse(payload["isReliable"])
        self.assertTrue(payload["fallbackUsed"])
        self.assertFalse(payload["isFallback"])
        self.assertEqual(payload["source"], "mixed")
        self.assertIn("真实数据不足", payload["warning"])
        self.assertEqual(payload["scores"]["overall"]["label"], "数据不足")
        self.assertNotIn(payload["scores"]["overall"]["label"], {"偏暖", "过热"})

    def test_temperature_excludes_fallback_only_inputs(self) -> None:
        service = MarketOverviewService()
        inputs = {
            "indices": {"items": [{"symbol": "000001.SH", "value": 3120, "source": "fallback", "freshness": "fallback", "isFallback": True}]},
            "crypto": {"items": [{"symbol": "BTC", "value": 75800, "source": "fallback", "freshness": "fallback", "isFallback": True}]},
        }

        with patch.object(service, "_build_market_temperature_inputs", return_value=inputs):
            payload = service.get_market_temperature()

        self.assertEqual(payload["reliableInputCount"], 0)
        self.assertGreater(payload["excludedInputCount"], 0)
        self.assertFalse(payload["isReliable"])

    def test_mixed_card_real_items_counted(self) -> None:
        service = MarketOverviewService()
        inputs = {
            "indices": {
                "source": "mixed",
                "items": [
                    {"symbol": "000001.SH", "value": 4107, "changePercent": 0.7, "source": "sina", "freshness": "live", "isFallback": False},
                    {"symbol": "399001.SZ", "value": 9820, "changePercent": 0.5, "source": "fallback", "freshness": "fallback", "isFallback": True},
                ],
            }
        }

        trust = service._summarize_market_temperature_confidence(inputs)
        coverage = classify_market_payload_reliability(inputs["indices"], category="equity_index")

        self.assertEqual(trust["reliableInputCount"], 1)
        self.assertEqual(trust["fallbackInputCount"], 1)
        self.assertEqual(trust["excludedInputCount"], 1)
        self.assertEqual(coverage["kind"], "mixed")


if __name__ == "__main__":
    unittest.main()
