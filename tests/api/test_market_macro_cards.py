# -*- coding: utf-8 -*-
"""Contract and fallback tests for market macro card endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from api.v1.endpoints import market
from src.services.market_data_source_registry import project_source_provenance
from src.services.official_macro_transport import MacroObservation
from src.services.market_overview_service import MarketOverviewService


class MarketMacroCardsApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        MarketOverviewService._market_cache.clear()
        MarketOverviewService._market_data_cache.clear()

    def test_sector_rotation_endpoint_returns_stable_contract(self) -> None:
        payload = market.get_sector_rotation()

        self.assertTrue(payload["source"])
        self.assertTrue(payload["updatedAt"])
        self.assertTrue(payload["items"])
        first_item = payload["items"][0]
        self.assertIn("relativeStrength", first_item)
        self.assertIn("rank", first_item)
        self.assertIn(first_item["market"], {"CN", "HK", "US"})

    def test_sector_rotation_endpoint_projects_rotation_radar_theme_order_and_scores(self) -> None:
        service = MarketOverviewService()
        as_of = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(timespec="seconds")
        updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        radar_payload = {
            "source": "computed",
            "sourceLabel": "主题篮子计算",
            "updatedAt": updated_at,
            "asOf": as_of,
            "freshness": "delayed",
            "isFallback": False,
            "warning": "部分主题行情暂不可用",
            "themes": [
                {
                    "id": "ai_applications",
                    "name": "AI 应用",
                    "market": "US",
                    "rotationScore": 73,
                    "relativeStrength": 4.0,
                    "source": "computed",
                    "sourceLabel": "主题篮子计算",
                    "freshness": "delayed",
                    "isFallback": False,
                    "isStale": False,
                    "updatedAt": updated_at,
                    "asOf": as_of,
                    "stageExplanation": "已有相对强势，但仍需更多广度确认。",
                    "proxyQuality": {
                        "coveragePercent": 100,
                        "explanation": "代理覆盖完整。",
                    },
                    "themeDetail": {
                        "dataStateLabel": "行情证据已接入",
                    },
                    "timeWindows": {
                        "1d": {
                            "available": True,
                            "averageChangePercent": 4.0,
                        },
                    },
                    "evidence": ["相对强弱领先"],
                },
                {
                    "id": "semiconductors",
                    "name": "半导体",
                    "market": "US",
                    "rotationScore": 68,
                    "relativeStrength": 2.1,
                    "source": "computed",
                    "sourceLabel": "主题篮子计算",
                    "freshness": "delayed",
                    "isFallback": False,
                    "isStale": False,
                    "updatedAt": updated_at,
                    "asOf": as_of,
                    "stageExplanation": "扩散仍需持续观察。",
                    "proxyQuality": {
                        "coveragePercent": 80,
                        "explanation": "代理覆盖部分缺口。",
                    },
                    "themeDetail": {
                        "dataStateLabel": "部分代理缺口",
                    },
                    "timeWindows": {
                        "1d": {
                            "available": True,
                            "averageChangePercent": 2.1,
                        },
                    },
                    "evidence": ["量能扩张"],
                },
            ],
        }
        provider = object()

        with patch.object(service, "_cached_payload", side_effect=lambda _key, fetcher, _fallback: fetcher()):
            with patch(
                "src.services.market_overview_service.get_rotation_radar_quote_provider",
                return_value=provider,
                create=True,
            ), patch(
                "src.services.market_overview_service.MarketRotationRadarService",
                create=True,
            ) as radar_service_cls:
                radar_service_cls.return_value.get_rotation_radar.return_value = radar_payload

                payload = service.get_sector_rotation()

        radar_service_cls.assert_called_once_with(quote_provider=provider, use_shared_cache=True)
        radar_service_cls.return_value.get_rotation_radar.assert_called_once_with()
        self.assertEqual(payload["source"], "computed")
        self.assertEqual(payload["sourceLabel"], "主题篮子计算")
        self.assertEqual(payload["freshness"], "delayed")
        self.assertFalse(payload["fallbackUsed"])
        self.assertFalse(payload["isFallback"])
        self.assertEqual(payload["warning"], "部分主题行情暂不可用")
        self.assertIn("Rotation Radar", payload["explanation"])
        self.assertEqual(
            [(item["symbol"], item["value"], item["rank"]) for item in payload["items"][:2]],
            [
                ("ai_applications", 73, 1),
                ("semiconductors", 68, 2),
            ],
        )
        first_item = payload["items"][0]
        self.assertEqual(first_item["name"], "AI 应用")
        self.assertEqual(first_item["label"], "AI 应用")
        self.assertEqual(first_item["unit"], "score")
        self.assertEqual(first_item["relativeStrength"], 73)
        self.assertEqual(first_item["changePercent"], 4.0)
        self.assertEqual(first_item["source"], "computed")
        self.assertEqual(first_item["freshness"], "delayed")
        self.assertFalse(first_item["isFallback"])
        self.assertIn("广度确认", first_item["explanation"])
        self.assertTrue(first_item["hover_details"])
        self.assertNotIn("买卖", " ".join(first_item["hover_details"]))

    def test_rates_endpoint_returns_us_and_cn_groups(self) -> None:
        payload = market.get_rates()

        self.assertTrue(payload["source"])
        self.assertTrue(payload["updatedAt"])
        symbols = {item["symbol"] for item in payload["items"]}
        self.assertIn("US10Y", symbols)
        self.assertIn("CN10Y", symbols)
        self.assertIn("explanation", payload)

    def test_fx_commodities_endpoint_returns_fx_and_commodities(self) -> None:
        payload = market.get_fx_commodities()

        self.assertTrue(payload["source"])
        self.assertTrue(payload["updatedAt"])
        symbols = {item["symbol"] for item in payload["items"]}
        self.assertIn("DXY", symbols)
        self.assertIn("USDCNH", symbols)
        self.assertIn("GOLD", symbols)
        self.assertIn("explanation", payload)

    def test_macro_card_fallbacks_are_not_empty_when_provider_fails(self) -> None:
        service = MarketOverviewService()

        cases = [
            ("_fetch_sector_rotation_snapshot", service.get_sector_rotation),
            ("_fetch_rates_snapshot", service.get_rates),
            ("_fetch_fx_commodities_snapshot", service.get_fx_commodities),
        ]
        for fetcher_name, getter in cases:
            with self.subTest(fetcher_name=fetcher_name):
                with patch.object(service, fetcher_name, side_effect=RuntimeError("provider down")):
                    payload = getter()

                self.assertEqual(payload["source"], "fallback")
                self.assertTrue(payload["fallbackUsed"])
                self.assertTrue(payload["items"])

    def test_rates_and_macro_panels_expose_official_macro_metadata_when_available(self) -> None:
        service = MarketOverviewService()
        latest_date = datetime.now(timezone.utc).date()
        latest_date_text = latest_date.isoformat()
        previous_date_text = (latest_date - timedelta(days=1)).isoformat()
        treasury_points = {
            "DGS2": [
                MacroObservation("DGS2", 3.87, latest_date_text, latest_date_text, "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
                MacroObservation("DGS2", 3.91, previous_date_text, previous_date_text, "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
            ],
            "DGS10": [
                MacroObservation("DGS10", 4.41, latest_date_text, latest_date_text, "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
                MacroObservation("DGS10", 4.45, previous_date_text, previous_date_text, "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
            ],
            "DGS30": [
                MacroObservation("DGS30", 4.89, latest_date_text, latest_date_text, "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
                MacroObservation("DGS30", 4.92, previous_date_text, previous_date_text, "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
            ],
        }
        fred_points = {
            "BAMLH0A0HYM2": [
                MacroObservation("BAMLH0A0HYM2", 3.31, latest_date_text, latest_date_text, "fred:BAMLH0A0HYM2", "official_public", "daily_credit_stress"),
                MacroObservation("BAMLH0A0HYM2", 3.45, previous_date_text, previous_date_text, "fred:BAMLH0A0HYM2", "official_public", "daily_credit_stress"),
            ],
            "VIXCLS": [
                MacroObservation("VIXCLS", 18.22, latest_date_text, latest_date_text, "fred:VIXCLS", "official_public", "daily_close"),
                MacroObservation("VIXCLS", 19.11, previous_date_text, previous_date_text, "fred:VIXCLS", "official_public", "daily_close"),
            ],
            "SOFR": [
                MacroObservation("SOFR", 5.31, latest_date_text, latest_date_text, "fred:SOFR", "official_public", "daily_fixing"),
                MacroObservation("SOFR", 5.32, previous_date_text, previous_date_text, "fred:SOFR", "official_public", "daily_fixing"),
            ],
        }

        with patch.object(service, "_cached_payload", side_effect=lambda _key, fetcher, _fallback: fetcher()):
            with patch(
                "src.services.market_overview_service.fetch_treasury_daily_rate_observation_points",
                return_value=treasury_points,
                create=True,
            ), patch(
                "src.services.market_overview_service.fetch_fred_observation_points",
                side_effect=lambda series_id, **_: fred_points.get(series_id, []),
                create=True,
            ):
                rates_payload = service.get_rates()
                macro_payload = service.get_macro()

        rates_items = {item["symbol"]: item for item in rates_payload["items"]}
        self.assertEqual(rates_items["US2Y"]["sourceType"], "official_public")
        self.assertEqual(rates_items["US2Y"]["sourceId"], "treasury:daily_treasury_yield_curve")
        self.assertEqual(rates_items["US10Y"]["sourceLabel"], "US Treasury Daily Par Yield Curve Rates")
        self.assertEqual(rates_items["US30Y"]["asOf"], latest_date_text)
        self.assertEqual(rates_items["SOFR"]["sourceType"], "official_public")
        self.assertEqual(rates_items["SOFR"]["sourceId"], "fred:SOFR")
        self.assertFalse(rates_items["US10Y"]["isFallback"])
        self.assertTrue(rates_payload["fallbackUsed"])
        self.assertNotIn("CREDIT", rates_items)
        us10y_provenance = project_source_provenance(
            source_type=rates_items["US10Y"].get("sourceType"),
            source_label=rates_items["US10Y"].get("sourceLabel"),
            freshness=rates_items["US10Y"].get("freshness"),
            is_fallback=bool(rates_items["US10Y"].get("isFallback")),
            is_stale=bool(rates_items["US10Y"].get("isStale")),
        )
        self.assertEqual(us10y_provenance["sourceType"], "official_public")

        macro_items = {item["symbol"]: item for item in macro_payload["items"]}
        self.assertEqual(macro_items["US2Y"]["sourceType"], "official_public")
        self.assertEqual(macro_items["US10Y"]["sourceId"], "treasury:daily_treasury_yield_curve")
        self.assertEqual(macro_items["VIX"]["sourceLabel"], "FRED CBOE VIX Close")
        self.assertEqual(macro_items["SOFR"]["sourceType"], "official_public")
        self.assertEqual(macro_items["SOFR"]["freshness"], "delayed")
        self.assertEqual(macro_items["CREDIT"]["sourceType"], "official_public")
        self.assertEqual(macro_items["CREDIT"]["sourceId"], "fred:BAMLH0A0HYM2")
        self.assertEqual(
            macro_items["CREDIT"]["sourceLabel"],
            "FRED ICE BofA US High Yield Index Option-Adjusted Spread",
        )
        self.assertEqual(macro_items["CREDIT"]["asOf"], latest_date_text)
        self.assertEqual(macro_items["CREDIT"]["freshness"], "delayed")
        self.assertTrue(macro_items["CREDIT"]["observationOnly"])
        self.assertFalse(macro_items["CREDIT"]["includedInScore"])
        credit_provenance = project_source_provenance(
            source_type=macro_items["CREDIT"].get("sourceType"),
            source_label=macro_items["CREDIT"].get("sourceLabel"),
            freshness=macro_items["CREDIT"].get("freshness"),
            is_fallback=bool(macro_items["CREDIT"].get("isFallback")),
            is_stale=bool(macro_items["CREDIT"].get("isStale")),
        )
        self.assertEqual(credit_provenance["sourceType"], "official_public")


if __name__ == "__main__":
    unittest.main()
