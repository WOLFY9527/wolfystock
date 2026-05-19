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
        previous_month_text = (latest_date - timedelta(days=30)).isoformat()
        year_ago_text = (latest_date - timedelta(days=365)).isoformat()
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
            "DFF": [
                MacroObservation("DFF", 4.33, latest_date_text, latest_date_text, "fred:DFF", "official_public", "daily_policy_rate"),
                MacroObservation("DFF", 4.31, previous_date_text, previous_date_text, "fred:DFF", "official_public", "daily_policy_rate"),
            ],
            "CPIAUCSL": [
                MacroObservation("CPIAUCSL", 321.0, latest_date_text, latest_date_text, "fred:CPIAUCSL", "official_public", "monthly_inflation_index"),
                MacroObservation("CPIAUCSL", 319.2, previous_month_text, previous_month_text, "fred:CPIAUCSL", "official_public", "monthly_inflation_index"),
                MacroObservation("CPIAUCSL", 309.9, year_ago_text, year_ago_text, "fred:CPIAUCSL", "official_public", "monthly_inflation_index"),
            ],
            "PPIACO": [
                MacroObservation("PPIACO", 282.0, latest_date_text, latest_date_text, "fred:PPIACO", "official_public", "monthly_inflation_index"),
                MacroObservation("PPIACO", 279.5, previous_month_text, previous_month_text, "fred:PPIACO", "official_public", "monthly_inflation_index"),
                MacroObservation("PPIACO", 248.0, year_ago_text, year_ago_text, "fred:PPIACO", "official_public", "monthly_inflation_index"),
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
        self.assertEqual(rates_items["US10Y"]["providerClass"], "official_daily")
        self.assertTrue(rates_items["US10Y"]["providerAttempted"])
        self.assertTrue(rates_items["US10Y"]["officialOverlayAttempted"])
        self.assertTrue(rates_items["US10Y"]["officialOverlayAvailable"])
        self.assertIsNone(rates_items["US10Y"]["officialOverlayFailureReason"])
        self.assertEqual(rates_items["US10Y"]["activationHint"], "official_daily_overlay_active")
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
        self.assertEqual(macro_items["US10Y"]["sourceType"], rates_items["US10Y"]["sourceType"])
        self.assertEqual(macro_items["US10Y"]["sourceLabel"], rates_items["US10Y"]["sourceLabel"])
        self.assertEqual(macro_items["US10Y"]["sourceTier"], rates_items["US10Y"]["sourceTier"])
        self.assertEqual(macro_items["US10Y"]["trustLevel"], rates_items["US10Y"]["trustLevel"])
        self.assertEqual(macro_items["US10Y"]["freshness"], rates_items["US10Y"]["freshness"])
        self.assertEqual(macro_items["US10Y"]["asOf"], rates_items["US10Y"]["asOf"])
        self.assertEqual(macro_items["US10Y"]["providerClass"], rates_items["US10Y"]["providerClass"])
        self.assertEqual(
            macro_items["US10Y"]["officialOverlayAvailable"],
            rates_items["US10Y"]["officialOverlayAvailable"],
        )
        self.assertEqual(
            macro_items["US10Y"]["officialOverlayFailureReason"],
            rates_items["US10Y"]["officialOverlayFailureReason"],
        )
        self.assertEqual(macro_items["US10Y"]["activationHint"], rates_items["US10Y"]["activationHint"])
        self.assertEqual(macro_items["VIX"]["sourceLabel"], "FRED CBOE VIX Close")
        self.assertEqual(macro_items["SOFR"]["sourceType"], "official_public")
        self.assertEqual(macro_items["SOFR"]["freshness"], "delayed")
        self.assertEqual(macro_items["FEDFUNDS"]["sourceType"], "official_public")
        self.assertEqual(macro_items["FEDFUNDS"]["sourceId"], "fred:DFF")
        self.assertEqual(macro_items["FEDFUNDS"]["asOf"], latest_date_text)
        self.assertEqual(macro_items["FEDFUNDS"]["freshness"], "delayed")
        self.assertEqual(macro_items["CPI"]["sourceType"], "official_public")
        self.assertEqual(macro_items["CPI"]["sourceId"], "fred:CPIAUCSL")
        self.assertEqual(macro_items["CPI"]["asOf"], latest_date_text)
        self.assertEqual(macro_items["CPI"]["freshness"], "delayed")
        self.assertAlmostEqual(macro_items["CPI"]["value"], 3.582, places=3)
        self.assertEqual(macro_items["PPI"]["sourceType"], "official_public")
        self.assertEqual(macro_items["PPI"]["sourceId"], "fred:PPIACO")
        self.assertEqual(macro_items["PPI"]["asOf"], latest_date_text)
        self.assertEqual(macro_items["PPI"]["freshness"], "delayed")
        self.assertAlmostEqual(macro_items["PPI"]["value"], 13.71, places=2)
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

    def test_fred_dgs10_overlay_metadata_is_consistent_when_treasury_row_is_missing(self) -> None:
        service = MarketOverviewService()
        latest_date = datetime.now(timezone.utc).date()
        latest_date_text = latest_date.isoformat()
        previous_date_text = (latest_date - timedelta(days=1)).isoformat()
        fred_points = {
            "DGS10": [
                MacroObservation("DGS10", 4.42, latest_date_text, latest_date_text, "fred:DGS10", "official_public", "daily_rate"),
                MacroObservation("DGS10", 4.47, previous_date_text, previous_date_text, "fred:DGS10", "official_public", "daily_rate"),
            ],
        }
        proxy_as_of = datetime.now(timezone.utc).isoformat(timespec="seconds")
        proxy_items = [
            {
                "symbol": "US10Y",
                "label": "10Y yield",
                "value": 4.5,
                "unit": "%",
                "change_pct": 0.0,
                "changePercent": 0.0,
                "risk_direction": "neutral",
                "trend": [4.48, 4.5],
                "source": "yfinance",
                "sourceLabel": "Yahoo Finance",
                "sourceType": "unofficial_proxy",
                "asOf": proxy_as_of,
            },
            {
                "symbol": "DXY",
                "label": "US Dollar Index",
                "value": 105.2,
                "unit": "idx",
                "change_pct": 0.1,
                "changePercent": 0.1,
                "risk_direction": "decreasing",
                "trend": [105.0, 105.2],
                "source": "yfinance",
                "sourceLabel": "Yahoo Finance",
                "sourceType": "unofficial_proxy",
                "asOf": proxy_as_of,
            },
        ]

        with patch.object(service, "_cached_payload", side_effect=lambda _key, fetcher, _fallback: fetcher()):
            with patch.object(service, "_quote_items", return_value=proxy_items), patch(
                "src.services.market_overview_service.fetch_treasury_daily_rate_observation_points",
                return_value={},
                create=True,
            ), patch(
                "src.services.market_overview_service.fetch_fred_observation_points",
                side_effect=lambda series_id, **_: fred_points.get(series_id, []),
                create=True,
            ):
                rates_payload = service.get_rates()
                macro_payload = service.get_macro()

        rates_items = {item["symbol"]: item for item in rates_payload["items"]}
        macro_items = {item["symbol"]: item for item in macro_payload["items"]}
        for item in (rates_items["US10Y"], macro_items["US10Y"]):
            self.assertEqual(item["source"], "fred")
            self.assertEqual(item["sourceId"], "fred:DGS10")
            self.assertEqual(item["sourceType"], "official_public")
            self.assertEqual(item["sourceLabel"], "FRED US Treasury 10Y Constant Maturity")
            self.assertEqual(item["providerClass"], "official_daily")
            self.assertTrue(item["providerAttempted"])
            self.assertTrue(item["officialOverlayAttempted"])
            self.assertTrue(item["officialOverlayAvailable"])
            self.assertIsNone(item["officialOverlayFailureReason"])
            self.assertEqual(item["activationHint"], "official_daily_overlay_active")
            self.assertNotIn(item["freshness"], {"live", "fresh"})

        self.assertEqual(macro_items["US10Y"]["freshness"], rates_items["US10Y"]["freshness"])
        self.assertEqual(macro_items["US10Y"]["asOf"], rates_items["US10Y"]["asOf"])
        self.assertEqual(macro_items["DXY"]["sourceType"], "unofficial_proxy")
        self.assertFalse(macro_items["DXY"]["officialOverlayAttempted"])
        self.assertFalse(macro_items["DXY"]["officialOverlayAvailable"])
        self.assertEqual(macro_items["DXY"]["officialOverlayFailureReason"], "not_configured")

    def test_macro_panel_marks_monthly_official_series_unavailable_without_live_masquerade_when_history_is_insufficient(self) -> None:
        service = MarketOverviewService()
        latest_date_text = datetime.now(timezone.utc).date().isoformat()

        with patch.object(service, "_cached_payload", side_effect=lambda _key, fetcher, _fallback: fetcher()):
            with patch(
                "src.services.market_overview_service.fetch_treasury_daily_rate_observation_points",
                return_value={},
                create=True,
            ), patch(
                "src.services.market_overview_service.fetch_fred_observation_points",
                side_effect=lambda series_id, **_: {
                    "CPIAUCSL": [
                        MacroObservation("CPIAUCSL", 321.0, latest_date_text, latest_date_text, "fred:CPIAUCSL", "official_public", "monthly_inflation_index"),
                    ],
                    "PPIACO": [
                        MacroObservation("PPIACO", 282.0, latest_date_text, latest_date_text, "fred:PPIACO", "official_public", "monthly_inflation_index"),
                    ],
                }.get(series_id, []),
                create=True,
            ):
                macro_payload = service.get_macro()

        macro_items = {item["symbol"]: item for item in macro_payload["items"]}
        self.assertTrue(macro_payload["fallbackUsed"])
        self.assertTrue(macro_items["CPI"]["isUnavailable"])
        self.assertEqual(macro_items["CPI"]["sourceType"], "official_public")
        self.assertEqual(macro_items["CPI"]["sourceId"], "fred:CPIAUCSL")
        self.assertNotIn(macro_items["CPI"]["freshness"], {"live", "fresh"})
        self.assertTrue(macro_items["PPI"]["isUnavailable"])
        self.assertEqual(macro_items["PPI"]["sourceType"], "official_public")
        self.assertEqual(macro_items["PPI"]["sourceId"], "fred:PPIACO")
        self.assertNotIn(macro_items["PPI"]["freshness"], {"live", "fresh"})


if __name__ == "__main__":
    unittest.main()
