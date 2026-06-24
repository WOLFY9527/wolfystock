# -*- coding: utf-8 -*-
"""Contract tests for independent market overview endpoints."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from api.v1.endpoints import market_overview
from src.services.market_overview_service import MarketOverviewService

FORBIDDEN_CONSUMER_REASON_TOKENS = (
    "_blocked",
    "_gate",
    "freshness_blocked",
    "proxy_or_sample_evidence_blocked",
    "source_authority_or_score_gate_blocked",
    "source_authority_blocked",
    "score_gate",
)


class MarketOverviewApiTestCase(unittest.TestCase):
    @staticmethod
    def _fed_liquidity_points(series_id: str, latest: float, previous: float):
        from src.services.official_macro_transport import MacroObservation

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

    @staticmethod
    def _fresh_fed_liquidity_status(*_args, **kwargs) -> dict:
        from src.services.official_macro_liquidity_cache_contracts import (
            OFFICIAL_FED_LIQUIDITY_FRESHNESS_POLICIES,
        )

        series_id = str(kwargs.get("series_id") or "")
        official_observation_date = kwargs.get("official_observation_date")
        return {
            "freshness": "delayed",
            "isFallback": False,
            "isStale": False,
            "isUnavailable": False,
            "source": "fred",
            "sourceType": "official_public",
            "seriesId": series_id,
            "officialObservationDate": official_observation_date,
            "officialAsOf": official_observation_date,
            "freshnessPolicy": OFFICIAL_FED_LIQUIDITY_FRESHNESS_POLICIES.get(series_id),
            "externalProviderCalls": False,
            "cacheOnly": True,
        }

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

    def test_funds_flow_endpoint_redacts_consumer_evidence_reason_family_codes(self) -> None:
        service = self._service()
        service.get_funds_flow.return_value["consumerEvidenceSnapshot"] = {
            "contractVersion": "market_overview_evidence.v1",
            "freshness": "fallback",
            "reasonFamilies": [
                {
                    "rawCode": "source_authority_blocked",
                    "family": "source_authority_blocked",
                    "scope": "score_gate",
                    "sourceField": "sourceAuthorityAllowed",
                }
            ],
        }
        with patch("api.v1.endpoints.market_overview.MarketOverviewService", return_value=service):
            funds_flow = market_overview.get_funds_flow()

        serialized = json.dumps(funds_flow, ensure_ascii=False).lower()
        for raw_token in FORBIDDEN_CONSUMER_REASON_TOKENS:
            self.assertNotIn(raw_token, serialized)


        self.assertEqual(
            funds_flow["consumerEvidenceSnapshot"]["reasonFamilies"],
            [{"label": "证据来源级别不足", "category": "evidence", "sourceField": "evidence"}],
        )

    def test_market_overview_consumer_evidence_snapshot_exposes_safe_data_quality(self) -> None:
        from src.services.market_overview_service import project_market_overview_consumer_evidence_snapshot

        snapshot = project_market_overview_consumer_evidence_snapshot(
            {
                "contractVersion": "market_overview_evidence.v1",
                "freshness": "stale",
                "isStale": True,
                "isFallback": False,
                "isPartial": False,
                "confidenceWeight": 0.12,
                "sourceType": "official_public",
                "reasonCode": "internal_stale_source",
            }
        )

        assert snapshot["dataQuality"] == {
            "state": "delayed",
            "label": "数据延迟",
            "available": False,
        }
        dumped_quality = json.dumps(snapshot["dataQuality"], ensure_ascii=False)
        for field in ("sourceType", "reasonCode", "confidenceWeight", "isStale"):
            assert field not in dumped_quality

    def test_macro_fed_liquidity_cache_bundle_diagnostics_are_cache_only_without_source_calls(self) -> None:
        from src.services.market_overview_service import MarketOverviewService

        service = MarketOverviewService(cn_hk_connect_flow_provider=lambda: None)

        official_points = {
            "WALCL": self._fed_liquidity_points("WALCL", 7485000.0, 7475000.0),
            "RRPONTSYD": self._fed_liquidity_points("RRPONTSYD", 432.2, 455.0),
            "WTREGEN": self._fed_liquidity_points("WTREGEN", 812000.0, 826000.0),
            "WRESBAL": self._fed_liquidity_points("WRESBAL", 3260000.0, 3240000.0),
        }

        with (
            patch(
                "src.services.market_overview_service.get_freshness_status",
                side_effect=self._fresh_fed_liquidity_status,
            ) as freshness_status,
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
        self.assertEqual(bundle["staleSeries"], [])
        self.assertEqual(bundle["coverageRatio"], 1.0)
        self.assertEqual(bundle["sourceType"], "official_public")
        self.assertFalse(bundle["externalProviderCalls"])
        self.assertTrue(bundle["scoreContributionAllowed"])
        self.assertFalse(bundle["observationOnly"])
        freshness_series = {
            str(call.kwargs.get("series_id") or "")
            for call in freshness_status.call_args_list
        }
        self.assertEqual(freshness_series, {"WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"})
        fred_fetch.assert_not_called()
        treasury_fetch.assert_not_called()

    def test_macro_fed_liquidity_missing_series_stays_missing_not_malformed(self) -> None:
        from src.services.market_overview_service import MarketOverviewService

        service = MarketOverviewService(cn_hk_connect_flow_provider=lambda: None)

        with patch(
            "src.services.market_overview_service.get_freshness_status",
            side_effect=self._fresh_fed_liquidity_status,
        ) as freshness_status:
            items = service._official_fed_liquidity_items(
                {
                    "WALCL": self._fed_liquidity_points("WALCL", 7485000.0, 7475000.0),
                    "RRPONTSYD": self._fed_liquidity_points("RRPONTSYD", 432.2, 455.0),
                    "WTREGEN": self._fed_liquidity_points("WTREGEN", 812000.0, 826000.0),
                }
            )

        bundle = items["FED_ASSETS"]["cacheBundleDiagnostics"]
        self.assertFalse(bundle["scoreContributionAllowed"])
        self.assertTrue(bundle["observationOnly"])
        self.assertEqual(bundle["fulfilledSeries"], ["WALCL", "RRPONTSYD", "WTREGEN"])
        self.assertEqual(bundle["missingSeries"], ["WRESBAL"])
        self.assertEqual(bundle["staleSeries"], [])
        self.assertEqual(bundle["malformedSeries"], [])
        self.assertEqual(bundle["unavailableSeries"], ["WRESBAL"])
        freshness_series = {
            str(call.kwargs.get("series_id") or "")
            for call in freshness_status.call_args_list
        }
        self.assertEqual(freshness_series, {"WALCL", "RRPONTSYD", "WTREGEN"})
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

    def test_market_temperature_us_rates_readiness_marks_budget_blocked_row_non_score_grade(self) -> None:
        from src.services.market_overview_service import MarketOverviewService

        service = MarketOverviewService(cn_hk_connect_flow_provider=lambda: None)
        as_of = "2026-05-20T10:00:00+08:00"

        def rate_row(symbol: str, series_id: str, **overrides: object) -> dict:
            row = {
                "symbol": symbol,
                "label": symbol,
                "officialSeriesId": series_id,
                "value": 4.0,
                "changePercent": -0.2,
                "source": "treasury",
                "sourceId": f"treasury:{series_id}",
                "sourceType": "official_public",
                "sourceTier": "official_public",
                "freshness": "cached",
                "asOf": as_of,
                "updatedAt": as_of,
                "confidenceWeight": 1.0,
                "excluded": False,
                "isFallback": False,
                "isUnavailable": False,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
            }
            row.update(overrides)
            return row

        rows = [
            rate_row("US2Y", "DGS2"),
            rate_row("US10Y", "DGS10"),
            rate_row(
                "US30Y",
                "DGS30",
                sourceAuthorityAllowed=False,
                scoreContributionAllowed=False,
                sourceAuthorityReason="budget_exhausted",
                routeRejectedReasonCodes=["budget_exhausted"],
            ),
        ]

        readiness_rows = service._with_official_us_rates_readiness_items(rows)
        guarded = [
            service._guard_market_temperature_score_input(row, panel_key="rates")
            for row in readiness_rows
        ]
        blocked = next(row for row in guarded if row["symbol"] == "US30Y")
        bundle = blocked["cacheBundleDiagnostics"]

        self.assertFalse(bundle["readinessEligible"])
        self.assertFalse(blocked["sourceAuthorityAllowed"])
        self.assertFalse(blocked["scoreContributionAllowed"])
        self.assertEqual(blocked["sourceAuthorityReason"], "budget_exhausted")
        self.assertEqual(bundle["budgetBlockedSeries"], ["DGS30"])
        self.assertIn("budget_blocked_official_macro_route", bundle["reasonCodes"])
        self.assertEqual(service._market_temperature_input_confidence(blocked, "macro_rate"), 0.0)

    def test_market_temperature_usd_pressure_readiness_uses_cache_only_official_row(self) -> None:
        from src.services.market_overview_service import MarketOverviewService

        service = MarketOverviewService(cn_hk_connect_flow_provider=lambda: None)
        row = {
            "symbol": "USD_TWI",
            "label": "Trade-weighted USD",
            "officialSeriesId": "DTWEXBGS",
            "value": 128.42,
            "changePercent": -0.25,
            "source": "fred",
            "sourceId": "fred:DTWEXBGS",
            "sourceType": "official_public",
            "sourceTier": "official_public",
            "freshness": "cached",
            "asOf": "2026-05-20",
            "updatedAt": "2026-05-20",
            "confidenceWeight": 1.0,
            "excluded": False,
            "isFallback": False,
            "isUnavailable": False,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
        }

        readiness_rows = service._with_official_usd_pressure_readiness_items([row])
        guarded = [
            service._guard_market_temperature_score_input(item, panel_key="fx")
            for item in readiness_rows
        ]
        usd = guarded[0]
        bundle = usd["cacheBundleDiagnostics"]

        self.assertTrue(bundle["readinessEligible"])
        self.assertTrue(bundle["scoreGradeEvidenceAllowed"])
        self.assertFalse(bundle["externalProviderCalls"])
        self.assertTrue(usd["sourceAuthorityAllowed"])
        self.assertTrue(usd["scoreContributionAllowed"])

    def test_market_temperature_inputs_attach_existing_observation_signals_without_leaking_admin_fields(self) -> None:
        from src.services.market_overview_service import MarketOverviewService

        service = MarketOverviewService(cn_hk_connect_flow_provider=lambda: None)

        def panel(key: str, *_args, **_kwargs) -> dict:
            return {
                "source": "cached",
                "sourceLabel": "缓存",
                "freshness": "cached",
                "updatedAt": "2026-05-20T10:00:00+08:00",
                "asOf": "2026-05-20T10:00:00+08:00",
                "items": [],
                "panelKey": key,
            }

        liquidity_payload = {
            "capitalFlowSignal": {
                "marketRegime": "risk_on",
                "capitalFlowRegime": "inflow",
                "themeFlowState": "leading",
                "confidenceLabel": "medium",
                "source": "mixed",
                "sourceType": "public_proxy",
                "freshness": "partial",
                "isPartial": True,
                "sourceAuthorityAllowed": False,
                "scoreContributionAllowed": False,
                "likelyDestination": "growth_ai_software_semis",
                "providerId": "private-provider",
                "adminDiagnostics": {"debug": "secret"},
            }
        }
        rotation_payload = {
            "summary": {
                "rotationFamilyRollup": [
                    {
                        "familyId": "ai",
                        "familyName": "AI",
                        "leaderThemeIds": ["ai_apps"],
                        "themeNames": ["AI 应用"],
                        "themeFlowSignal": {
                            "marketRegime": "risk_on",
                            "capitalFlowRegime": "inflow",
                            "themeFlowState": "leading",
                            "confidenceLabel": "high",
                            "source": "rotation_radar_projection",
                            "sourceType": "authorized_licensed_feed",
                            "freshness": "cached",
                            "sourceAuthorityAllowed": True,
                            "scoreContributionAllowed": False,
                            "breadthEvidence": {
                                "source": "rotation_theme_quote_breadth",
                                "observationOnly": True,
                                "authorityGrant": False,
                                "scoreContributionAllowed": False,
                                "observedMembers": 8,
                                "configuredMembers": 10,
                                "coveragePercent": 80.0,
                                "percentUp": 74.0,
                                "percentOutperformingBenchmark": 66.0,
                                "providerRouting": {"winner": "internal"},
                                "adminDiagnostics": {"payload": "secret"},
                                "cacheBundleDiagnostics": {"cacheKey": "rotation:ai"},
                            },
                            "providerRouting": {"winner": "internal"},
                            "adminDiagnostics": {"payload": "secret"},
                        },
                    }
                ]
            }
        }

        with (
            patch.object(service, "_temperature_panel", side_effect=panel),
            patch("src.services.market_overview_service.LiquidityMonitorService") as liquidity_service_cls,
            patch("src.services.market_overview_service.MarketRotationRadarService") as rotation_service_cls,
        ):
            liquidity_service_cls.return_value.get_liquidity_monitor.return_value = liquidity_payload
            rotation_service_cls.return_value.get_rotation_radar.return_value = rotation_payload
            inputs = service._build_market_temperature_inputs_from_internal_snapshots()

        signal = inputs["capitalFlowSignal"]
        assert signal["observationOnly"] is True
        assert signal["sourceAuthorityAllowed"] is False
        assert signal["scoreContributionAllowed"] is False
        assert signal["confidenceLabel"] == "blocked"
        assert "providerId" not in signal
        assert "adminDiagnostics" not in signal

        family = inputs["rotationFamilyRollup"][0]
        assert family["familyId"] == "ai"
        assert family["themeFlowSignal"]["observationOnly"] is True
        assert family["themeFlowSignal"]["scoreContributionAllowed"] is False
        assert family["themeFlowSignal"]["sourceAuthorityAllowed"] is False
        assert family["themeFlowSignal"]["breadthEvidence"] == {
            "diagnosticOnly": True,
            "observationOnly": True,
            "authorityGrant": False,
            "scoreContributionAllowed": False,
            "observedMembers": 8,
            "configuredMembers": 10,
            "coveragePercent": 80.0,
            "percentUp": 74.0,
            "percentOutperformingBenchmark": 66.0,
        }
        assert "providerRouting" not in family["themeFlowSignal"]
        assert "adminDiagnostics" not in family["themeFlowSignal"]
        serialized_family = str(family["themeFlowSignal"])
        assert "internal" not in serialized_family
        assert "cacheBundleDiagnostics" not in serialized_family
        assert "cacheKey" not in serialized_family


class _ExecutionLogStub:
    def record_market_overview_fetch(self, **_: object) -> str:
        return "log-overview-sentiment"


def test_market_overview_sentiment_returns_partial_when_secondary_provider_has_usable_value() -> None:
    service = MarketOverviewService()

    with patch.object(
        service,
        "_fetch_cnn_fear_greed_snapshot",
        side_effect=RuntimeError("cnn unavailable"),
    ), patch.object(
        service,
        "_fetch_alternative_fear_greed_snapshot",
        return_value={"history": [{"value": 22}, {"value": 24}, {"value": 35}], "source": "alternative_me"},
    ), patch("src.services.market_overview_service.ExecutionLogService", _ExecutionLogStub):
        payload = service.get_sentiment()

    assert payload["status"] == "partial"
    assert payload["items"][0]["symbol"] == "FGI"
    assert payload["items"][0]["value"] == 35
    assert payload["source"] == "alternative_me"
    assert payload["sourceLabel"] == "Alternative.me"
    assert payload["providerHealth"]["status"] == "partial"
    assert payload["refreshError"] == "数据源暂不可用"
    assert payload["warning"]
    assert payload["error_message"] is None


def test_market_overview_sentiment_returns_partial_for_stale_last_known_good_snapshot() -> None:
    service = MarketOverviewService()
    service._market_cache.clear()
    service._market_data_cache.clear()
    service._market_data_cache[service.OVERVIEW_SENTIMENT_CACHE_KEY] = {
        "panel_name": "MarketSentimentCard",
        "last_refresh_at": "2026-06-25T10:00:00+08:00",
        "updatedAt": "2026-06-25T10:00:00+08:00",
        "source": "cnn",
        "items": [
            {
                "symbol": "FGI",
                "label": "Fear & Greed",
                "value": 33,
                "unit": "score",
                "change_pct": -2.0,
                "trend": [38, 36, 33],
                "source": "cnn",
            }
        ],
    }

    with patch.object(
        service,
        "_fetch_market_sentiment_snapshot",
        side_effect=RuntimeError("cnn unavailable"),
    ), patch("src.services.market_overview_service.ExecutionLogService", _ExecutionLogStub):
        payload = service.get_sentiment()

    assert payload["status"] == "partial"
    assert payload["items"][0]["value"] == 33
    assert payload["isStale"] is True
    assert payload["providerHealth"]["status"] == "stale"
    assert payload["refreshError"] == "数据源暂不可用"
    assert payload["warning"]
    assert payload["error_message"] == "数据源暂不可用"


def test_market_overview_sentiment_returns_unavailable_when_no_usable_value_exists() -> None:
    service = MarketOverviewService()
    service._market_cache.clear()
    service._market_data_cache.clear()

    with patch.object(
        service,
        "_fetch_market_sentiment_snapshot",
        side_effect=RuntimeError("cnn unavailable"),
    ), patch("src.services.market_overview_service.ExecutionLogService", _ExecutionLogStub):
        payload = service.get_sentiment()

    assert payload["status"] == "unavailable"
    assert payload["items"] == []
    assert payload["providerHealth"]["status"] == "unavailable"
    assert payload["error_message"] == "数据源暂不可用"


if __name__ == "__main__":
    unittest.main()
