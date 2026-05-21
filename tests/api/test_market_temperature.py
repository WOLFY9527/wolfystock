# -*- coding: utf-8 -*-
"""Contract and fallback tests for market temperature endpoint."""

from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from api.v1.endpoints import market
from src.services.market_overview_service import (
    MarketOverviewService,
    classify_market_payload_reliability,
    get_freshness_status,
)


def _regime_ready_temperature_inputs(*, proxy_dxy: bool = True, observation_only_btc: bool = True) -> dict:
    dxy_source_type = "unofficial_proxy" if proxy_dxy else "official_public"
    dxy_trust_level = "usable_with_caution" if proxy_dxy else "high"
    dxy_freshness = "stale" if proxy_dxy else "live"
    dxy_source = "yfinance_proxy" if proxy_dxy else "fred"
    dxy_reason = "proxy_context_only" if proxy_dxy else None
    btc_score_allowed = not observation_only_btc
    btc_observation_only = observation_only_btc
    btc_reason = "source_authority_router_rejected" if observation_only_btc else None

    return {
        "indices": {
            "items": [
                {
                    "symbol": "HSI",
                    "label": "Hang Seng",
                    "value": 17820.0,
                    "changePercent": -1.2,
                    "source": "sina",
                    "sourceType": "official_public",
                    "trustLevel": "high",
                    "freshness": "live",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                }
            ]
        },
        "breadth": {
            "items": [
                {
                    "symbol": "ADV_RATIO",
                    "label": "Advance Ratio",
                    "value": 38.0,
                    "source": "tickflow",
                    "sourceType": "official_public",
                    "trustLevel": "high",
                    "freshness": "live",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                }
            ]
        },
        "rates": {
            "items": [
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.42,
                    "changePercent": 0.8,
                    "source": "treasury",
                    "sourceType": "official_public",
                    "trustLevel": "high",
                    "freshness": "cached",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 21.3,
                    "changePercent": 5.2,
                    "source": "fred",
                    "sourceType": "official_public",
                    "trustLevel": "high",
                    "freshness": "cached",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
            ]
        },
        "fx": {
            "items": [
                {
                    "symbol": "DXY",
                    "label": "DXY",
                    "value": 105.4,
                    "changePercent": 0.6,
                    "source": dxy_source,
                    "sourceType": dxy_source_type,
                    "trustLevel": dxy_trust_level,
                    "freshness": dxy_freshness,
                    "sourceAuthorityAllowed": not proxy_dxy,
                    "sourceAuthorityReason": dxy_reason,
                    "scoreContributionAllowed": True,
                    "degradationReason": dxy_reason,
                }
            ]
        },
        "futures": {
            "items": [
                {
                    "symbol": "ES",
                    "label": "E-mini S&P",
                    "value": 5250.0,
                    "changePercent": -0.9,
                    "source": "cme",
                    "sourceType": "exchange_public",
                    "trustLevel": "high",
                    "freshness": "live",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
                {
                    "symbol": "NQ",
                    "label": "Nasdaq Futures",
                    "value": 18250.0,
                    "changePercent": -1.2,
                    "source": "cme",
                    "sourceType": "exchange_public",
                    "trustLevel": "high",
                    "freshness": "live",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
                {
                    "symbol": "RTY",
                    "label": "Russell Futures",
                    "value": 2060.0,
                    "changePercent": -1.5,
                    "source": "cme",
                    "sourceType": "exchange_public",
                    "trustLevel": "high",
                    "freshness": "live",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
            ]
        },
        "crypto": {
            "items": [
                {
                    "symbol": "BTC",
                    "label": "Bitcoin",
                    "value": 64000.0,
                    "changePercent": -3.1,
                    "source": "coinbase_public" if observation_only_btc else "binance",
                    "sourceType": "exchange_public",
                    "trustLevel": "high",
                    "freshness": "live",
                    "sourceAuthorityAllowed": not observation_only_btc,
                    "sourceAuthorityReason": btc_reason,
                    "observationOnly": btc_observation_only,
                    "scoreContributionAllowed": btc_score_allowed,
                    "degradationReason": btc_reason,
                },
                {
                    "symbol": "ETH",
                    "label": "Ethereum",
                    "value": 3150.0,
                    "changePercent": -2.6,
                    "source": "binance",
                    "sourceType": "exchange_public",
                    "trustLevel": "high",
                    "freshness": "live",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
            ]
        },
    }


def _rotation_theme(
    *,
    score_contribution_allowed: bool,
    source_authority_allowed: bool,
    rotation_score: float,
    change_percent: float,
    source: str = "alpaca",
    source_type: str = "tier_1_configured",
    trust_level: str = "high",
    freshness: str = "cached",
    source_authority_reason: str | None = None,
) -> dict:
    return {
        "symbol": "ai_applications",
        "label": "AI Applications",
        "value": rotation_score,
        "rotationScore": rotation_score,
        "changePercent": change_percent,
        "source": source,
        "sourceTier": source_type,
        "sourceType": source_type,
        "trustLevel": trust_level,
        "freshness": freshness,
        "sourceAuthorityAllowed": source_authority_allowed,
        "sourceAuthorityReason": source_authority_reason,
        "scoreContributionAllowed": score_contribution_allowed,
        "rankEligible": score_contribution_allowed,
        "headlineEligible": score_contribution_allowed,
        "scoreCap": 0.9 if score_contribution_allowed else 0.0,
        "rankingTrust": {
            "sourceTier": source_type,
            "trustLevel": trust_level,
            "freshness": freshness,
            "scoreCap": 0.9 if score_contribution_allowed else 0.0,
            "conclusionAllowed": score_contribution_allowed,
        },
        "degradationReasons": [] if score_contribution_allowed else [source_authority_reason or "proxy_context_only"],
    }


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
            "marketRegimeSynthesis": {
                "primaryRegime": "risk_on_liquidity_expansion",
                "secondaryRegimes": ["soft_landing_disinflation"],
                "regimeScores": {"risk_on_liquidity_expansion": 0.72},
                "riskAppetite": 0.6,
                "ratesPressure": -0.1,
                "dollarPressure": -0.2,
                "volatilityStress": -0.4,
                "liquidityImpulse": 0.3,
                "cryptoRiskBeta": 0.5,
                "breadthHealth": 0.2,
                "chinaRiskAppetite": 0.1,
                "rotationQuality": 0.0,
                "confidence": 0.66,
                "confidenceLabel": "medium",
                "topDrivers": [],
                "counterEvidence": [],
                "dataGaps": [],
                "narrativeBullets": ["Risk appetite improving."],
                "evidenceQuality": {"discountedEvidenceCount": 0},
                "notInvestmentAdvice": True,
            },
        }

        with patch("api.v1.endpoints.market.MarketOverviewService", return_value=service):
            payload = market.get_temperature()

        self.assertEqual(payload["source"], "computed")
        self.assertTrue(payload["updatedAt"])
        self.assertEqual(set(payload["scores"].keys()), {"overall", "usRiskAppetite", "cnMoneyEffect", "macroPressure", "liquidity"})
        self.assertIn("marketRegimeSynthesis", payload)
        self.assertEqual(payload["marketRegimeSynthesis"]["primaryRegime"], "risk_on_liquidity_expansion")
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
        self.assertEqual(payload["requiredReliableInputCount"], 5)
        self.assertFalse(payload["temperatureAvailable"])
        self.assertTrue(payload["insufficientReliableInputs"])
        self.assertEqual(payload["disabledReason"], "insufficient_reliable_inputs")
        self.assertEqual(payload["unavailableReason"], "insufficient_reliable_inputs")
        self.assertFalse(payload["conclusionAllowed"])
        self.assertGreater(payload["fallbackInputCount"], 0)
        self.assertGreater(payload["excludedInputCount"], 0)
        self.assertFalse(payload["isReliable"])
        self.assertEqual(payload["evidenceSnapshot"]["degradationReason"], "provider_unavailable")
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

    def test_market_temperature_exposes_additive_market_regime_synthesis_payload(self) -> None:
        service = MarketOverviewService()

        with patch.object(service, "_build_market_temperature_inputs", return_value=_regime_ready_temperature_inputs()):
            payload = service.get_market_temperature()

        self.assertIn("marketRegimeSynthesis", payload)
        self.assertIn("scores", payload)
        self.assertIn("source", payload)
        self.assertIn("updatedAt", payload)
        self.assertIn("providerHealth", payload)
        self.assertIn("evidenceSnapshot", payload)
        self.assertIn("overall", payload["scores"])
        self.assertTrue(payload["scores"]["overall"]["label"])

        synthesis = payload["marketRegimeSynthesis"]
        self.assertEqual(
            set(synthesis),
            {
                "primaryRegime",
                "secondaryRegimes",
                "regimeScores",
                "liquidityImpulse",
                "riskAppetite",
                "ratesPressure",
                "dollarPressure",
                "volatilityStress",
                "cryptoRiskBeta",
                "breadthHealth",
                "chinaRiskAppetite",
                "rotationQuality",
                "confidence",
                "confidenceLabel",
                "topDrivers",
                "counterEvidence",
                "dataGaps",
                "narrativeBullets",
                "evidenceQuality",
                "notInvestmentAdvice",
            },
        )
        self.assertIsInstance(synthesis["secondaryRegimes"], list)
        self.assertIsInstance(synthesis["regimeScores"], dict)
        self.assertIsInstance(synthesis["topDrivers"], list)
        self.assertIsInstance(synthesis["counterEvidence"], list)
        self.assertIsInstance(synthesis["dataGaps"], list)
        self.assertIsInstance(synthesis["narrativeBullets"], list)
        self.assertIsInstance(synthesis["evidenceQuality"], dict)

        serialized = json.dumps(synthesis, ensure_ascii=False, sort_keys=True)
        for forbidden in ("rawPayload", "providerPayload", "raw_payload", "provider_payload"):
            self.assertNotIn(forbidden, serialized)

    def test_low_coverage_temperature_synthesis_stays_data_insufficient(self) -> None:
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
            payload = service.get_market_temperature()

        synthesis = payload["marketRegimeSynthesis"]
        self.assertEqual(payload["scores"]["overall"]["label"], "数据不足")
        self.assertLess(payload["confidence"], 0.25)
        self.assertEqual(synthesis["primaryRegime"], "data_insufficient")
        self.assertEqual(synthesis["confidenceLabel"], "insufficient")
        self.assertTrue(synthesis["dataGaps"])
        self.assertLessEqual(synthesis["confidence"], 0.4)

    def test_proxy_stale_and_observation_only_inputs_stay_discounted_in_temperature_synthesis(self) -> None:
        service = MarketOverviewService()

        with patch.object(service, "_build_market_temperature_inputs", return_value=_regime_ready_temperature_inputs(proxy_dxy=False, observation_only_btc=False)):
            official_payload = service.get_market_temperature()

        MarketOverviewService._market_cache.clear()
        MarketOverviewService._market_data_cache.clear()

        with patch.object(service, "_build_market_temperature_inputs", return_value=_regime_ready_temperature_inputs(proxy_dxy=True, observation_only_btc=True)):
            discounted_payload = service.get_market_temperature()

        official_synthesis = official_payload["marketRegimeSynthesis"]
        discounted_synthesis = discounted_payload["marketRegimeSynthesis"]

        self.assertEqual(official_synthesis["primaryRegime"], discounted_synthesis["primaryRegime"])
        self.assertLess(discounted_synthesis["confidence"], official_synthesis["confidence"])
        self.assertGreater(
            discounted_synthesis["evidenceQuality"]["discountedEvidenceCount"],
            official_synthesis["evidenceQuality"]["discountedEvidenceCount"],
        )
        self.assertTrue(
            any(gap["key"] == "crypto:BTC" for gap in discounted_synthesis["dataGaps"])
        )
        self.assertTrue(
            all(driver["key"] != "crypto:BTC" for driver in discounted_synthesis["topDrivers"])
        )

    def test_market_temperature_regime_bridge_blocks_non_scoring_rotation_and_liquidity(self) -> None:
        service = MarketOverviewService()
        blocked_inputs = _regime_ready_temperature_inputs(proxy_dxy=True, observation_only_btc=True)
        blocked_inputs["sectors"] = {
            "items": [
                _rotation_theme(
                    score_contribution_allowed=False,
                    source_authority_allowed=False,
                    source="yfinance_proxy",
                    source_type="unofficial_proxy",
                    trust_level="usable_with_caution",
                    freshness="delayed",
                    source_authority_reason="proxy_context_only",
                    rotation_score=18.0,
                    change_percent=-3.1,
                )
            ]
        }
        blocked_inputs["rates"]["items"][0]["scoreContributionAllowed"] = False
        blocked_inputs["rates"]["items"][0]["sourceAuthorityAllowed"] = False
        blocked_inputs["rates"]["items"][1]["scoreContributionAllowed"] = False
        blocked_inputs["rates"]["items"][1]["sourceAuthorityAllowed"] = False
        blocked_inputs["crypto"]["items"][1]["scoreContributionAllowed"] = False
        blocked_inputs["crypto"]["items"][1]["sourceAuthorityAllowed"] = False
        blocked_inputs["futures"]["items"][0]["scoreContributionAllowed"] = False
        blocked_inputs["futures"]["items"][1]["scoreContributionAllowed"] = False
        blocked_inputs["futures"]["items"][2]["scoreContributionAllowed"] = False
        blocked_inputs["breadth"]["items"][0]["scoreContributionAllowed"] = False

        allowed_inputs = _regime_ready_temperature_inputs(proxy_dxy=False, observation_only_btc=False)
        allowed_inputs["sectors"] = {
            "items": [
                _rotation_theme(
                    score_contribution_allowed=True,
                    source_authority_allowed=True,
                    rotation_score=18.0,
                    change_percent=-3.1,
                )
            ]
        }

        with patch.object(service, "_build_market_temperature_inputs", return_value=blocked_inputs):
            blocked_payload = service.get_market_temperature()

        MarketOverviewService._market_cache.clear()
        MarketOverviewService._market_data_cache.clear()

        with patch.object(service, "_build_market_temperature_inputs", return_value=allowed_inputs):
            allowed_payload = service.get_market_temperature()

        blocked = blocked_payload["marketRegimeSynthesis"]
        allowed = allowed_payload["marketRegimeSynthesis"]

        self.assertNotIn("rotation_leadership", blocked["evidenceQuality"]["coveredPillars"])
        self.assertNotIn("liquidity_impulse", blocked["evidenceQuality"]["coveredPillars"])
        self.assertTrue(any(gap["key"] == "sectors:rotation_leadership" for gap in blocked["dataGaps"]))
        self.assertTrue(any(gap["key"] == "liquidity_monitor:liquidity_impulse" for gap in blocked["dataGaps"]))

        self.assertIn("rotation_leadership", allowed["evidenceQuality"]["coveredPillars"])
        self.assertIn("liquidity_impulse", allowed["evidenceQuality"]["coveredPillars"])
        self.assertLess(allowed["rotationQuality"], 0)
        self.assertLess(allowed["liquidityImpulse"], 0)
        self.assertGreater(allowed["confidence"], blocked["confidence"])

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

    def test_low_coverage_mixed_temperature_is_not_reliable(self) -> None:
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
            payload = service.get_market_temperature()

        self.assertFalse(payload["isReliable"])
        self.assertEqual(payload["source"], "mixed")
        self.assertEqual(payload["sourceLabel"], "多来源")
        self.assertFalse(payload["isFallback"])
        self.assertTrue(payload["fallbackUsed"])
        self.assertEqual(payload["trustLevel"], "weak")
        self.assertLessEqual(payload["scoreCap"], 0.4)
        self.assertFalse(payload["conclusionAllowed"])
        self.assertFalse(payload["temperatureAvailable"])
        self.assertTrue(payload["insufficientReliableInputs"])
        self.assertEqual(payload["disabledReason"], "insufficient_reliable_inputs")
        self.assertEqual(payload["unavailableReason"], "insufficient_reliable_inputs")
        self.assertEqual(payload["requiredReliableInputCount"], 5)
        self.assertEqual(payload["freshness"], "partial")
        self.assertTrue(payload["isPartial"])
        self.assertEqual(payload["providerHealth"]["status"], "partial")
        self.assertIn("low_coverage", payload["degradationReasons"])
        self.assertLess(payload["confidence"], 0.25)
        self.assertLess(payload["evidenceSnapshot"]["coverage"], 0.25)
        self.assertEqual(payload["evidenceSnapshot"]["degradationReason"], "partial_coverage")
        self.assertEqual(payload["scores"]["overall"]["label"], "数据不足")

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

    def test_delayed_real_inputs_keep_discounted_confidence(self) -> None:
        service = MarketOverviewService()
        inputs = {
            "futures": {
                "items": [
                    {"symbol": "ES", "value": 5238, "changePercent": 0.2, "source": "yahoo", "freshness": "delayed", "isFallback": False},
                    {"symbol": "NQ", "value": 18320, "changePercent": 0.4, "source": "yahoo", "freshness": "delayed", "isFallback": False},
                    {"symbol": "YM", "value": 39000, "changePercent": -0.1, "source": "yahoo", "freshness": "delayed", "isFallback": False},
                ]
            }
        }

        trust = service._summarize_market_temperature_confidence(inputs)

        self.assertEqual(trust["reliableInputCount"], 3)
        self.assertEqual(trust["fallbackInputCount"], 0)
        self.assertEqual(trust["excludedInputCount"], 0)
        self.assertEqual(trust["confidence"], 0.7)
        self.assertLess(trust["confidence"], 1.0)

    def test_official_public_inputs_count_as_reliable_temperature_sources(self) -> None:
        service = MarketOverviewService()
        inputs = {
            "futures": {
                "items": [
                    {"symbol": "ES", "value": 5238, "changePercent": 0.2, "source": "yahoo", "freshness": "delayed", "isFallback": False},
                    {"symbol": "NQ", "value": 18320, "changePercent": 0.4, "source": "yahoo", "freshness": "delayed", "isFallback": False},
                ]
            },
            "sentiment": {"items": [{"symbol": "FGI", "value": 70, "source": "cnn", "freshness": "cached", "isFallback": False}]},
            "rates": {
                "items": [
                    {"symbol": "US10Y", "value": 4.41, "changePercent": -0.9, "source": "treasury", "sourceType": "official_public", "freshness": "cached", "isFallback": False},
                    {"symbol": "VIX", "value": 18.22, "changePercent": -4.66, "source": "fred", "sourceType": "official_public", "freshness": "cached", "isFallback": False},
                ]
            },
            "fx": {"items": [{"symbol": "DXY", "value": 104.2, "changePercent": -0.3, "source": "yahoo", "freshness": "delayed", "isFallback": False}]},
        }

        with patch.object(service, "_build_market_temperature_inputs", return_value=inputs):
            payload = service.get_market_temperature()

        self.assertTrue(payload["isReliable"])
        self.assertEqual(payload["trustLevel"], "reliable")
        self.assertGreaterEqual(payload["scoreCap"], 0.9)
        self.assertTrue(payload["conclusionAllowed"])
        self.assertTrue(payload["temperatureAvailable"])
        self.assertFalse(payload["insufficientReliableInputs"])
        self.assertIsNone(payload["disabledReason"])
        self.assertIsNone(payload["unavailableReason"])
        self.assertEqual(payload["requiredReliableInputCount"], 5)
        self.assertEqual(payload["degradationReasons"], [])
        self.assertGreaterEqual(payload["reliableInputCount"], 5)
        self.assertEqual(payload["fallbackInputCount"], 0)
        self.assertGreater(payload["confidence"], 0.7)

    def test_official_macro_daily_rates_remain_delayed_or_stale_not_live(self) -> None:
        delayed = get_freshness_status(
            "2026-05-14T15:00:00+08:00",
            "macro_rate",
            "treasury",
            False,
            source_type="official_public",
            now=datetime(2026, 5, 14, 16, 0, tzinfo=timezone.utc),
        )
        stale = get_freshness_status(
            "2026-05-10T15:00:00+08:00",
            "macro_rate",
            "treasury",
            False,
            source_type="official_public",
            now=datetime(2026, 5, 14, 16, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(delayed["freshness"], "delayed")
        self.assertFalse(delayed["isFallback"])
        self.assertFalse(delayed["isStale"])
        self.assertNotEqual(delayed["freshness"], "live")
        self.assertEqual(stale["freshness"], "stale")
        self.assertFalse(stale["isFallback"])
        self.assertTrue(stale["isStale"])

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
        self.assertEqual(payload["trustLevel"], "weak")
        self.assertFalse(payload["conclusionAllowed"])
        self.assertFalse(payload["temperatureAvailable"])
        self.assertTrue(payload["insufficientReliableInputs"])
        self.assertEqual(payload["disabledReason"], "insufficient_reliable_inputs")
        self.assertEqual(payload["unavailableReason"], "insufficient_reliable_inputs")
        self.assertEqual(payload["requiredReliableInputCount"], 5)
        self.assertIn("low_coverage", payload["degradationReasons"])
        self.assertTrue(payload["fallbackUsed"])
        self.assertFalse(payload["isFallback"])
        self.assertEqual(payload["source"], "mixed")
        self.assertEqual(payload["sourceLabel"], "多来源")
        self.assertEqual(payload["sourceType"], "public_api")
        self.assertEqual(payload["freshness"], "partial")
        self.assertEqual(payload["providerHealth"]["status"], "partial")
        self.assertFalse(payload["providerHealth"]["isFallback"])
        self.assertIn("真实数据不足", payload["warning"])
        self.assertTrue(all(score["label"] == "数据不足" for score in payload["scores"].values()))
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
        self.assertFalse(payload["temperatureAvailable"])
        self.assertEqual(payload["disabledReason"], "insufficient_reliable_inputs")
        self.assertFalse(payload["conclusionAllowed"])

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


def test_temperature_confidence_excludes_legacy_sentiment_panel_family() -> None:
    service = MarketOverviewService()
    legacy_sentiment_panel = {
        "source": "cnn",
        "sourceLabel": "CNN",
        "freshness": "live",
        "isFallback": False,
        "items": [
            {
                "symbol": "FGI",
                "label": "Fear & Greed",
                "value": 52,
                "unit": "score",
                "change_pct": -3.0,
                "trend": [60, 55, 52],
                "source": "cnn",
                "freshness": "live",
                "isFallback": False,
            }
        ],
    }

    trust = service._summarize_market_temperature_confidence(
        {
            "indices": {"items": []},
            "breadth": {"items": []},
            "flows": {"items": []},
            "sectors": {"items": []},
            "rates": {"items": []},
            "fx": {"items": []},
            "futures": {"items": []},
            "sentiment": legacy_sentiment_panel,
            "crypto": {"items": []},
        }
    )

    assert trust["reliableInputCount"] == 0
    assert trust["fallbackInputCount"] >= 1
    assert trust["excludedInputCount"] >= 1
    assert trust["isReliable"] is False


def test_temperature_scores_ignore_source_authority_rejected_inputs() -> None:
    service = MarketOverviewService()
    base_inputs = {
        "indices": {
            "items": [
                {"symbol": "000001.SH", "value": 4100.0, "changePercent": 0.7, "source": "sina", "freshness": "live", "isFallback": False}
            ]
        },
        "breadth": {
            "items": [
                {"symbol": "ADV_RATIO", "value": 61.0, "change": 1.0, "source": "tickflow", "freshness": "live", "isFallback": False},
                {"symbol": "LIMIT_UP", "value": 48.0, "change": 2.0, "source": "tickflow", "freshness": "live", "isFallback": False},
                {"symbol": "LIMIT_DOWN", "value": 21.0, "change": -1.0, "source": "tickflow", "freshness": "live", "isFallback": False},
            ]
        },
        "flows": {
            "items": [
                {"symbol": "CN_ETF", "value": 15.0, "changePercent": 0.3, "source": "eastmoney", "freshness": "live", "isFallback": False},
                {"symbol": "NORTHBOUND", "value": 12.0, "changePercent": 0.1, "source": "eastmoney", "freshness": "live", "isFallback": False},
            ]
        },
        "sectors": {
            "items": [
                {"symbol": "TECH", "value": 1.0, "changePercent": 0.5, "source": "yahoo", "freshness": "delayed", "isFallback": False},
                {"symbol": "AI", "value": 1.0, "changePercent": 0.4, "source": "yahoo", "freshness": "delayed", "isFallback": False},
                {"symbol": "CHIP", "value": 1.0, "changePercent": 0.2, "source": "yahoo", "freshness": "delayed", "isFallback": False},
            ]
        },
        "rates": {
            "items": [
                {"symbol": "US10Y", "value": 4.2, "changePercent": -0.2, "source": "treasury", "sourceType": "official_public", "freshness": "cached", "isFallback": False},
                {"symbol": "VIX", "value": 16.2, "changePercent": -1.1, "source": "fred", "sourceType": "official_public", "freshness": "cached", "isFallback": False},
                {"symbol": "DR007", "value": 1.7, "changePercent": -0.1, "source": "eastmoney", "freshness": "live", "isFallback": False},
                {"symbol": "SHIBOR", "value": 1.8, "changePercent": -0.05, "source": "eastmoney", "freshness": "live", "isFallback": False},
            ]
        },
        "fx": {
            "items": [
                {"symbol": "DXY", "value": 104.3, "changePercent": -0.4, "source": "yahoo", "freshness": "delayed", "isFallback": False},
                {"symbol": "USDCNH", "value": 7.2, "changePercent": -0.2, "source": "yahoo", "freshness": "delayed", "isFallback": False},
                {"symbol": "WTI", "value": 78.0, "changePercent": 0.8, "source": "yahoo", "freshness": "delayed", "isFallback": False},
                {"symbol": "GOLD", "value": 2360.0, "changePercent": 1.6, "source": "yahoo", "freshness": "delayed", "isFallback": False},
            ]
        },
        "futures": {
            "items": [
                {"symbol": "ES", "value": 5238.0, "changePercent": 0.2, "source": "yahoo", "freshness": "delayed", "isFallback": False},
                {"symbol": "NQ", "value": 18320.0, "changePercent": 0.4, "source": "yahoo", "freshness": "delayed", "isFallback": False},
                {"symbol": "YM", "value": 39000.0, "changePercent": -0.1, "source": "yahoo", "freshness": "delayed", "isFallback": False},
            ]
        },
        "sentiment": {
            "items": [
                {"symbol": "FGI", "value": 60, "change": 1.0, "source": "cnn", "freshness": "cached", "isFallback": False}
            ]
        },
        "crypto": {
            "items": [
                {"symbol": "BTC", "value": 87000.0, "changePercent": 1.4, "source": "binance", "freshness": "live", "isFallback": False},
                {"symbol": "ETH", "value": 3200.0, "changePercent": 1.1, "source": "binance", "freshness": "live", "isFallback": False},
                {"symbol": "BNB", "value": 610.0, "changePercent": 0.7, "source": "binance", "freshness": "live", "isFallback": False},
            ]
        },
        "fallback_notice": True,
    }
    rejected_inputs = copy.deepcopy(base_inputs)
    rejected_inputs["crypto"]["items"].append(
        {
            "symbol": "BTC",
            "value": 99000.0,
            "changePercent": 25.0,
            "source": "coinbase_public",
            "sourceType": "exchange_public",
            "freshness": "live",
            "isFallback": False,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "sourceAuthorityRouteRejected": True,
            "sourceAuthorityReason": "source_authority_router_rejected",
            "routeRejectedReasonCodes": [
                "provider_forbidden_for_use_case",
                "provider_observation_only",
                "scoring_not_allowed",
            ],
        }
    )

    baseline_scores = service._compute_market_temperature_scores(
        service._real_market_temperature_inputs(base_inputs)
    )
    rejected_scores = service._compute_market_temperature_scores(
        service._real_market_temperature_inputs(rejected_inputs)
    )

    assert rejected_scores == baseline_scores
