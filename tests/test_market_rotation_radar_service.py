# -*- coding: utf-8 -*-
"""Market rotation radar scoring and safety tests."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from src.services.market_rotation_radar_service import MarketRotationRadarService


def _quote(
    symbol: str,
    change: float,
    *,
    volume_ratio: float = 1.0,
    price: float = 100.0,
    freshness: str = "live",
    is_stale: bool = False,
    is_fallback: bool = False,
) -> dict:
    return {
        "symbol": symbol,
        "name": symbol,
        "price": price,
        "changePercent": change,
        "volume": 1_000_000 * volume_ratio,
        "averageVolume": 1_000_000,
        "vwap": price * 0.99,
        "freshness": freshness,
        "isStale": is_stale,
        "isFallback": is_fallback,
        "source": "unit_fixture",
        "sourceLabel": "Unit Fixture",
        "asOf": "2026-05-07T09:45:00+00:00",
    }


class MarketRotationRadarServiceTestCase(unittest.TestCase):
    def test_live_quotes_score_confirmed_rotation_with_breadth_and_newsless_evidence(self) -> None:
        quotes = {
            "QQQ": _quote("QQQ", 0.8),
            "SPY": _quote("SPY", 0.45),
            "IWM": _quote("IWM", 0.15),
            "APP": _quote("APP", 5.1, volume_ratio=2.4, price=310),
            "PLTR": _quote("PLTR", 4.6, volume_ratio=2.0, price=132),
            "CRM": _quote("CRM", 2.8, volume_ratio=1.7, price=285),
            "SNOW": _quote("SNOW", 3.5, volume_ratio=1.8, price=212),
            "ADBE": _quote("ADBE", 2.2, volume_ratio=1.5, price=505),
            "NOW": _quote("NOW", 2.6, volume_ratio=1.6, price=780),
        }
        service = MarketRotationRadarService(
            quote_provider=lambda symbols: {symbol: quotes[symbol] for symbol in symbols if symbol in quotes},
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()
        theme = payload["themes"][0]

        self.assertEqual(theme["id"], "ai_applications")
        self.assertGreaterEqual(theme["rotationScore"], 70)
        self.assertGreaterEqual(theme["confidence"], 0.65)
        self.assertIn(theme["stage"], {"early_rotation", "confirmed_rotation"})
        self.assertGreaterEqual(theme["breadth"]["percentUp"], 80)
        self.assertGreaterEqual(theme["breadth"]["percentOutperformingBenchmark"], 80)
        self.assertGreaterEqual(theme["volume"]["averageRelativeVolume"], 1.5)
        self.assertTrue(theme["newslessRotation"])
        self.assertIn("无明显新闻的同步异动", theme["evidence"])
        self.assertNotIn("fallback_data", theme["riskLabels"])
        self.assertNotIn("stale_data", theme["riskLabels"])

    def test_fallback_when_no_provider_never_marks_live_and_caps_confidence(self) -> None:
        service = MarketRotationRadarService(now_provider=lambda: datetime(2026, 5, 7, tzinfo=timezone.utc))

        payload = service.get_rotation_radar()

        self.assertTrue(payload["isFallback"])
        self.assertEqual(payload["freshness"], "fallback")
        self.assertNotEqual(payload["freshness"], "live")
        self.assertEqual(payload["metadata"]["noExternalCalls"], True)
        self.assertGreaterEqual(len(payload["themes"]), 8)
        for theme in payload["themes"]:
            self.assertTrue(theme["isFallback"])
            self.assertEqual(theme["freshness"], "fallback")
            self.assertNotEqual(theme["freshness"], "live")
            self.assertLessEqual(theme["confidence"], 0.25)
            self.assertEqual(theme["stage"], "weak_or_no_signal")
            self.assertIn("fallback_data", theme["riskLabels"])

    def test_stale_and_missing_data_penalizes_confidence_and_blocks_clean_rotation_claims(self) -> None:
        quotes = {
            "QQQ": _quote("QQQ", 0.7),
            "SPY": _quote("SPY", 0.2),
            "IWM": _quote("IWM", -0.2),
            "NVDA": _quote("NVDA", 7.5, volume_ratio=2.8, price=980, freshness="stale", is_stale=True),
            "AVGO": _quote("AVGO", 0.2, volume_ratio=0.9, price=1450),
            "AMD": _quote("AMD", -0.4, volume_ratio=0.8, price=160),
        }
        service = MarketRotationRadarService(
            quote_provider=lambda symbols: {symbol: quotes[symbol] for symbol in symbols if symbol in quotes},
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()
        infra = next(theme for theme in payload["themes"] if theme["id"] == "ai_infrastructure")

        self.assertIn("stale_data", infra["riskLabels"])
        self.assertIn("thin_breadth", infra["riskLabels"])
        self.assertIn("single_name_driven", infra["riskLabels"])
        self.assertLess(infra["confidence"], 0.55)
        self.assertNotEqual(infra["stage"], "confirmed_rotation")
        self.assertLessEqual(infra["rotationScore"], 69)
        self.assertFalse(infra["newslessRotation"])

    def test_payload_uses_safe_no_advice_and_no_exact_fund_flow_wording(self) -> None:
        payload = MarketRotationRadarService().get_rotation_radar()
        dumped = json.dumps(payload, ensure_ascii=False).lower()

        forbidden = (
            "建议买入",
            "必买",
            "稳赚",
            "下单",
            "best contract",
            "guaranteed",
            "buy now",
            "sell now",
            "主力资金流入金额",
            "exact fund flow",
        )
        for marker in forbidden:
            self.assertNotIn(marker.lower(), dumped)
        self.assertIn("资金轮动迹象", dumped)
        self.assertIn("非买卖建议", dumped)


if __name__ == "__main__":
    unittest.main()
