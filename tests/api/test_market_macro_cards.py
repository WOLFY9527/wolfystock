# -*- coding: utf-8 -*-
"""Contract and fallback tests for market macro card endpoints."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from api.v1.endpoints import market
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
        treasury_points = {
            "DGS2": [
                MacroObservation("DGS2", 3.87, "2026-05-13", "2026-05-13", "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
                MacroObservation("DGS2", 3.91, "2026-05-12", "2026-05-12", "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
            ],
            "DGS10": [
                MacroObservation("DGS10", 4.41, "2026-05-13", "2026-05-13", "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
                MacroObservation("DGS10", 4.45, "2026-05-12", "2026-05-12", "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
            ],
            "DGS30": [
                MacroObservation("DGS30", 4.89, "2026-05-13", "2026-05-13", "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
                MacroObservation("DGS30", 4.92, "2026-05-12", "2026-05-12", "treasury:daily_treasury_yield_curve", "official_public", "daily_1530_et"),
            ],
        }
        fred_points = {
            "VIXCLS": [
                MacroObservation("VIXCLS", 18.22, "2026-05-13", "2026-05-13", "fred:VIXCLS", "official_public", "daily_close"),
                MacroObservation("VIXCLS", 19.11, "2026-05-12", "2026-05-12", "fred:VIXCLS", "official_public", "daily_close"),
            ],
            "SOFR": [
                MacroObservation("SOFR", 5.31, "2026-05-13", "2026-05-13", "fred:SOFR", "official_public", "daily_fixing"),
                MacroObservation("SOFR", 5.32, "2026-05-12", "2026-05-12", "fred:SOFR", "official_public", "daily_fixing"),
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
        self.assertEqual(rates_items["US30Y"]["asOf"], "2026-05-13")
        self.assertEqual(rates_items["SOFR"]["sourceType"], "official_public")
        self.assertEqual(rates_items["SOFR"]["sourceId"], "fred:SOFR")
        self.assertFalse(rates_items["US10Y"]["isFallback"])
        self.assertTrue(rates_payload["fallbackUsed"])

        macro_items = {item["symbol"]: item for item in macro_payload["items"]}
        self.assertEqual(macro_items["US2Y"]["sourceType"], "official_public")
        self.assertEqual(macro_items["US10Y"]["sourceId"], "treasury:daily_treasury_yield_curve")
        self.assertEqual(macro_items["VIX"]["sourceLabel"], "FRED CBOE VIX Close")
        self.assertEqual(macro_items["SOFR"]["sourceType"], "official_public")
        self.assertEqual(macro_items["SOFR"]["freshness"], "delayed")


if __name__ == "__main__":
    unittest.main()
