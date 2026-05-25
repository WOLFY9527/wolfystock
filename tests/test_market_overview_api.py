# -*- coding: utf-8 -*-
"""Contract tests for independent market overview endpoints."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from api.v1.endpoints import market_overview


class MarketOverviewApiTestCase(unittest.TestCase):
    def _service(self) -> MagicMock:
        service = MagicMock()
        service.get_indices.return_value = {
            "panel_name": "IndexTrendsCard",
            "last_refresh_at": "2026-04-29T10:00:00",
            "source": "yfinance",
            "sourceLabel": "Yahoo Finance",
            "updatedAt": "2026-04-29T10:00:05",
            "asOf": "2026-04-29T10:00:00",
            "freshness": "delayed",
            "isFallback": False,
            "status": "success",
            "items": [
                {
                    "symbol": "SPX",
                    "label": "S&P 500",
                    "value": 5200.12,
                    "change_pct": 0.42,
                    "risk_direction": "decreasing",
                    "trend": [5180.0, 5200.12],
                    "source": "yfinance",
                    "sourceLabel": "Yahoo Finance",
                    "updatedAt": "2026-04-29T10:00:05",
                    "asOf": "2026-04-29T10:00:00",
                    "freshness": "delayed",
                    "isFallback": False,
                }
            ],
            "log_session_id": "log-1",
        }
        service.get_volatility.return_value = {
            "panel_name": "VolatilityCard",
            "last_refresh_at": "2026-04-29T10:00:00",
            "status": "success",
            "items": [{"symbol": "VIX", "label": "VIX", "value": 16.2, "change_pct": -2.1, "risk_direction": "decreasing", "trend": [17.0, 16.2]}],
            "log_session_id": "log-2",
        }
        service.get_sentiment.return_value = {
            "panel_name": "MarketSentimentCard",
            "last_refresh_at": "2026-04-29T10:00:00",
            "status": "success",
            "items": [{"symbol": "FGI", "label": "CNN Fear & Greed", "value": 52, "unit": "score", "risk_direction": "neutral"}],
            "log_session_id": "log-3",
        }
        service.get_funds_flow.return_value = {
            "panel_name": "FundsFlowCard",
            "last_refresh_at": "2026-04-29T10:00:00",
            "status": "success",
            "items": [{"symbol": "ETF", "label": "ETF flow proxy", "value": 1.2, "unit": "B USD", "risk_direction": "decreasing"}],
            "log_session_id": "log-4",
        }
        service.get_macro.return_value = {
            "panel_name": "MacroIndicatorsCard",
            "last_refresh_at": "2026-04-29T10:00:00",
            "status": "success",
            "items": [{"symbol": "US10Y", "label": "10Y yield", "value": 4.2, "unit": "%", "risk_direction": "increasing"}],
            "log_session_id": "log-5",
        }
        return service

    def test_market_overview_endpoints_return_panel_contracts(self) -> None:
        service = self._service()
        with patch("api.v1.endpoints.market_overview.MarketOverviewService", return_value=service):
            indices = market_overview.get_indices()
            volatility = market_overview.get_volatility()
            sentiment = market_overview.get_sentiment()
            funds_flow = market_overview.get_funds_flow()
            macro = market_overview.get_macro()

        self.assertEqual(indices["panel_name"], "IndexTrendsCard")
        self.assertEqual(volatility["panel_name"], "VolatilityCard")
        self.assertEqual(sentiment["panel_name"], "MarketSentimentCard")
        self.assertEqual(funds_flow["panel_name"], "FundsFlowCard")
        self.assertEqual(macro["panel_name"], "MacroIndicatorsCard")
        for payload in (indices, volatility, sentiment, funds_flow, macro):
            self.assertEqual(payload["status"], "success")
            self.assertTrue(payload["last_refresh_at"])
            self.assertTrue(payload["items"])
            self.assertTrue(payload["log_session_id"])
        self.assertEqual(indices["sourceLabel"], "Yahoo Finance")
        self.assertEqual(indices["updatedAt"], "2026-04-29T10:00:05")
        self.assertEqual(indices["asOf"], "2026-04-29T10:00:00")
        self.assertEqual(indices["freshness"], "delayed")
        self.assertFalse(indices["isFallback"])
        self.assertEqual(indices["items"][0]["sourceLabel"], "Yahoo Finance")
        self.assertEqual(indices["items"][0]["updatedAt"], "2026-04-29T10:00:05")
        self.assertEqual(indices["items"][0]["asOf"], "2026-04-29T10:00:00")
        self.assertEqual(indices["items"][0]["freshness"], "delayed")
        self.assertFalse(indices["items"][0]["isFallback"])

    def test_macro_fed_liquidity_cache_bundle_diagnostics_are_cache_only_without_source_calls(self) -> None:
        from src.services.market_overview_service import MarketOverviewService
        from src.services.official_macro_transport import MacroObservation

        service = MarketOverviewService(cn_hk_connect_flow_provider=lambda: None)

        def points(series_id: str, latest: float, previous: float) -> list[MacroObservation]:
            return [
                MacroObservation(
                    symbol=series_id,
                    value=latest,
                    date="2026-05-22",
                    as_of="2026-05-22T16:15:00+00:00",
                    source_id=f"fred:{series_id}",
                    source_type="official_public",
                    freshness_hint="delayed",
                ),
                MacroObservation(
                    symbol=series_id,
                    value=previous,
                    date="2026-05-15",
                    as_of="2026-05-15T16:15:00+00:00",
                    source_id=f"fred:{series_id}",
                    source_type="official_public",
                    freshness_hint="delayed",
                ),
            ]

        official_points = {
            "WALCL": points("WALCL", 7485000.0, 7475000.0),
            "RRPONTSYD": points("RRPONTSYD", 432.2, 455.0),
            "WTREGEN": points("WTREGEN", 812000.0, 826000.0),
            "WRESBAL": points("WRESBAL", 3260000.0, 3240000.0),
        }

        with (
            patch(
                "src.services.market_overview_service.fetch_fred_observation_points",
                side_effect=AssertionError("cache bundle projection must not fetch FRED"),
            ) as fred_fetch,
            patch(
                "src.services.market_overview_service.fetch_treasury_daily_rate_observation_points",
                side_effect=AssertionError("cache bundle projection must not fetch Treasury"),
            ) as treasury_fetch,
        ):
            items = service._official_fed_liquidity_items(official_points)

        fed_assets = items["FED_ASSETS"]
        bundle = fed_assets["cacheBundleDiagnostics"]
        self.assertEqual(bundle["requiredSeries"], ["WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"])
        self.assertEqual(bundle["fulfilledSeries"], ["WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"])
        self.assertEqual(bundle["missingSeries"], [])
        self.assertEqual(bundle["coverageRatio"], 1.0)
        self.assertEqual(bundle["sourceType"], "official_public")
        self.assertFalse(bundle["externalProviderCalls"])
        self.assertTrue(bundle["scoreContributionAllowed"])
        self.assertFalse(bundle["observationOnly"])
        fred_fetch.assert_not_called()
        treasury_fetch.assert_not_called()

    def test_macro_fed_liquidity_missing_series_stays_missing_not_malformed(self) -> None:
        from src.services.market_overview_service import MarketOverviewService
        from src.services.official_macro_transport import MacroObservation

        service = MarketOverviewService(cn_hk_connect_flow_provider=lambda: None)

        def points(series_id: str, latest: float, previous: float) -> list[MacroObservation]:
            return [
                MacroObservation(
                    symbol=series_id,
                    value=latest,
                    date="2026-05-22",
                    as_of="2026-05-22T16:15:00+00:00",
                    source_id=f"fred:{series_id}",
                    source_type="official_public",
                    freshness_hint="delayed",
                ),
                MacroObservation(
                    symbol=series_id,
                    value=previous,
                    date="2026-05-15",
                    as_of="2026-05-15T16:15:00+00:00",
                    source_id=f"fred:{series_id}",
                    source_type="official_public",
                    freshness_hint="delayed",
                ),
            ]

        items = service._official_fed_liquidity_items(
            {
                "WALCL": points("WALCL", 7485000.0, 7475000.0),
                "RRPONTSYD": points("RRPONTSYD", 432.2, 455.0),
                "WTREGEN": points("WTREGEN", 812000.0, 826000.0),
            }
        )

        bundle = items["FED_ASSETS"]["cacheBundleDiagnostics"]
        self.assertFalse(bundle["scoreContributionAllowed"])
        self.assertTrue(bundle["observationOnly"])
        self.assertEqual(bundle["fulfilledSeries"], ["WALCL", "RRPONTSYD", "WTREGEN"])
        self.assertEqual(bundle["missingSeries"], ["WRESBAL"])
        self.assertEqual(bundle["malformedSeries"], [])
        self.assertEqual(bundle["unavailableSeries"], ["WRESBAL"])
        self.assertFalse(items["FED_ASSETS"]["scoreContributionAllowed"])
        self.assertFalse(items["RESERVES"]["scoreContributionAllowed"])

    def test_market_temperature_rates_uses_complete_official_fed_bundle_only(self) -> None:
        from src.services.market_overview_service import MarketOverviewService

        service = MarketOverviewService(cn_hk_connect_flow_provider=lambda: None)
        as_of = "2026-05-22T16:15:00+00:00"
        series_by_symbol = {
            "FED_ASSETS": "WALCL",
            "FED_RRP": "RRPONTSYD",
            "TGA": "WTREGEN",
            "RESERVES": "WRESBAL",
        }

        def fed_item(
            symbol: str,
            *,
            source: str = "fred",
            source_type: str = "official_public",
            freshness: str = "cached",
            is_fallback: bool = False,
        ) -> dict:
            series_id = series_by_symbol[symbol]
            return {
                "symbol": symbol,
                "label": symbol,
                "value": 1.0,
                "changePercent": 0.2,
                "source": source,
                "sourceId": f"{source}:{series_id}",
                "sourceType": source_type,
                "sourceLabel": "FRED",
                "sourceTier": source_type,
                "trustLevel": "reliable",
                "officialSeriesId": series_id,
                "freshness": freshness,
                "asOf": as_of,
                "updatedAt": as_of,
                "isFallback": is_fallback,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "sourceFreshnessEvidence": {
                    "freshness": freshness,
                    "isFallback": is_fallback,
                    "isStale": freshness == "stale",
                    "isUnavailable": False,
                },
            }

        def build_inputs(macro_items: list[dict]) -> dict:
            def panel(key: str, *_args, **_kwargs) -> dict:
                if key == "macro":
                    return {"source": "mixed", "freshness": "cached", "items": [dict(item) for item in macro_items]}
                return {"source": "unavailable", "freshness": "unavailable", "items": []}

            with patch.object(service, "_temperature_panel", side_effect=panel):
                return service._build_market_temperature_inputs_from_internal_snapshots()

        official_inputs = build_inputs([fed_item(symbol) for symbol in series_by_symbol])
        official_rate_symbols = {
            item["symbol"]
            for item in official_inputs["rates"]["items"]
            if item["symbol"] in series_by_symbol
        }
        self.assertEqual(official_rate_symbols, set(series_by_symbol))
        self.assertTrue(
            all(
                item["cacheBundleDiagnostics"]["scoreContributionAllowed"] is True
                for item in official_inputs["rates"]["items"]
                if item["symbol"] in series_by_symbol
            )
        )

        proxy_inputs = build_inputs(
            [
                fed_item(
                    symbol,
                    source="yfinance_proxy",
                    source_type="public_proxy",
                    freshness="fallback",
                    is_fallback=True,
                )
                for symbol in series_by_symbol
            ]
        )
        proxy_rate_symbols = {
            item["symbol"]
            for item in proxy_inputs["rates"]["items"]
            if item["symbol"] in series_by_symbol
        }
        self.assertEqual(proxy_rate_symbols, set())

        stale_inputs = build_inputs(
            [
                fed_item(
                    symbol,
                    freshness="stale",
                )
                for symbol in series_by_symbol
            ]
        )
        stale_rate_symbols = {
            item["symbol"]
            for item in stale_inputs["rates"]["items"]
            if item["symbol"] in series_by_symbol
        }
        self.assertEqual(stale_rate_symbols, set())

    def test_market_temperature_cn_money_market_degraded_rows_are_not_score_grade(self) -> None:
        from src.services.market_overview_service import MarketOverviewService
        from src.services.official_macro_liquidity_cache_contracts import (
            OFFICIAL_CN_MONEY_MARKET_PROVIDER_ID,
        )

        service = MarketOverviewService(cn_hk_connect_flow_provider=lambda: None)

        def official_row(symbol: str, series_id: str, value: object, **overrides: object) -> dict:
            row = {
                "symbol": symbol,
                "label": symbol,
                "officialSeriesId": series_id,
                "value": value,
                "source": OFFICIAL_CN_MONEY_MARKET_PROVIDER_ID,
                "sourceType": "official_public",
                "sourceTier": "official_public",
                "freshness": "delayed",
                "confidenceWeight": 1.0,
                "excluded": False,
                "isFallback": False,
                "isUnavailable": False,
            }
            row.update(overrides)
            return row

        cases = {
            "missing_shibor": [official_row("DR007", "DR007", 1.86)],
            "fallback_shibor": [
                official_row("DR007", "DR007", 1.86),
                official_row(
                    "SHIBOR",
                    "SHIBOR_ON",
                    1.72,
                    source="fallback",
                    sourceType="fallback_static",
                    isFallback=True,
                    freshness="fallback",
                ),
            ],
            "stale_shibor": [
                official_row("DR007", "DR007", 1.86),
                official_row("SHIBOR", "SHIBOR_ON", 1.72, freshness="stale", isStale=True),
            ],
        }

        for case_name, rows in cases.items():
            with self.subTest(case_name=case_name):
                readiness_rows = service._with_cn_money_market_readiness_items(rows)
                guarded = [
                    service._guard_market_temperature_score_input(row, panel_key="rates")
                    for row in readiness_rows
                ]
                cn_rows = [
                    row
                    for row in guarded
                    if row.get("symbol") in {"DR007", "SHIBOR"}
                ]
                self.assertTrue(cn_rows)
                for row in cn_rows:
                    self.assertFalse(row["cacheBundleDiagnostics"]["readinessEligible"])
                    self.assertFalse(row["sourceAuthorityAllowed"])
                    self.assertFalse(row["scoreContributionAllowed"])
                    self.assertEqual(
                        service._market_temperature_input_confidence(row, "macro_rate"),
                        0.0,
                    )


if __name__ == "__main__":
    unittest.main()
