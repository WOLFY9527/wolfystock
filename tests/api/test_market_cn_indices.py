# -*- coding: utf-8 -*-
"""Contract and fallback tests for China index market endpoint."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

from fastapi.testclient import TestClient

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from api.v1.endpoints import market
from src.services import cn_provider_health_service as health_service_module
from src.services.cn_provider_health_service import CNProviderHealthSnapshotEntry
from src.config import Config
from src.services.market_overview_service import MarketOverviewService, get_freshness_status
from src.storage import DatabaseManager


CN_TZ = timezone(timedelta(hours=8))
EXPECTED_CN_PROVIDER_HEALTH_ENTRY_FIELDS = {
    "providerName",
    "providerId",
    "sourceType",
    "sourceTier",
    "trustLevel",
    "freshnessExpectation",
    "observationOnly",
    "scoreContributionAllowed",
    "dependencyInstalled",
    "providerAvailable",
    "healthStatus",
    "supportedCapabilities",
    "unsupportedCapabilities",
    "contractCapabilities",
    "keyRequired",
    "cacheRequired",
    "backgroundRefreshRecommended",
    "degradationReason",
    "missingProviderReason",
    "attemptedAt",
    "timeoutSeconds",
}
FORBIDDEN_CN_PROVIDER_HEALTH_FIELDS = {
    "quote",
    "quotes",
    "kline",
    "klines",
    "rawPayload",
    "score",
    "scoreContribution",
}


def _fresh_sina_as_of() -> str:
    return datetime.now(CN_TZ).isoformat(timespec="seconds")


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


def _reset_market_test_state() -> None:
    MarketOverviewService._market_cache.wait_for_refreshes(timeout=2)
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    health_service_module.CNProviderHealthService.clear_snapshot_cache()
    DatabaseManager.reset_instance()
    os.environ.pop("MARKET_OVERVIEW_SNAPSHOT_TEST_DB", None)


class MarketCnIndicesApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_market_test_state()

    def tearDown(self) -> None:
        _reset_market_test_state()

    def test_cn_indices_endpoint_returns_stable_contract(self) -> None:
        payload = market.get_cn_indices()

        self.assertTrue(payload["source"])
        self.assertTrue(payload["sourceLabel"])
        self.assertTrue(payload["updatedAt"])
        self.assertIn(payload["freshness"], {"live", "delayed", "cached", "stale", "partial", "fallback", "mock", "error"})
        self.assertIn("isFallback", payload)
        self.assertIn("isStale", payload)
        self.assertTrue(payload["items"])
        first_item = payload["items"][0]
        self.assertIsInstance(first_item["name"], str)
        self.assertIsInstance(first_item["symbol"], str)
        self.assertIsInstance(first_item["value"], (int, float))
        self.assertIn("change", first_item)
        self.assertIn("changePercent", first_item)
        self.assertIn("source", first_item)
        self.assertIn("sourceLabel", first_item)
        self.assertIn("freshness", first_item)
        self.assertIn("isFallback", first_item)
        self.assertIn("warning", first_item)
        self.assertIsInstance(first_item["sparkline"], list)
        self.assertIn(first_item["market"], {"CN", "HK", "Futures"})

    def test_cn_indices_fallback_is_not_empty_when_provider_fails(self) -> None:
        service = MarketOverviewService()

        with patch.object(service, "_fetch_sina_cn_index_quotes", side_effect=RuntimeError("provider down")):
            payload = service.get_cn_indices()

        self.assertEqual(payload["source"], "fallback")
        self.assertEqual(payload["freshness"], "fallback")
        self.assertTrue(payload["fallbackUsed"])
        self.assertTrue(payload["isFallback"])
        self.assertFalse(payload["isPartial"])
        self.assertTrue(payload["items"])
        self.assertEqual(payload["items"][0]["freshness"], "fallback")
        self.assertTrue(payload["items"][0]["isFallback"])
        self.assertEqual(payload["items"][0]["warning"], "备用示例数据，不代表当前行情")

    def test_freshness_helper_never_marks_fallback_live(self) -> None:
        now = datetime(2026, 4, 30, 10, 0, tzinfo=CN_TZ)
        status = get_freshness_status(now.isoformat(), "crypto", "fallback", True, now=now)

        self.assertEqual(status["freshness"], "fallback")
        self.assertTrue(status["isFallback"])
        self.assertTrue(status["warning"])

    def test_freshness_helper_marks_old_crypto_stale(self) -> None:
        now = datetime(2026, 4, 30, 10, 0, tzinfo=CN_TZ)
        as_of = now - timedelta(minutes=20)
        status = get_freshness_status(as_of.isoformat(), "crypto", "binance", False, now=now)

        self.assertEqual(status["freshness"], "stale")
        self.assertTrue(status["isStale"])

    def test_cn_indices_supports_mixed_item_level_metadata(self) -> None:
        service = MarketOverviewService()
        now = _fresh_sina_as_of()
        quote = {
            "000001.SH": {
                "name": "上证指数",
                "symbol": "000001.SH",
                "value": 4107.51,
                "change": 28.88,
                "changePercent": 0.71,
                "sparkline": [4078.63, 4107.51],
                "asOf": now,
            }
        }

        with patch.object(service, "_fetch_sina_cn_index_quotes", return_value=quote):
            payload = service.get_cn_indices()

        self.assertEqual(payload["source"], "mixed")
        self.assertEqual(payload["freshness"], "partial")
        self.assertNotEqual(payload["freshness"], "live")
        self.assertTrue(payload["fallbackUsed"])
        self.assertFalse(payload["isFallback"])
        self.assertTrue(payload["isPartial"])
        live_item = next(item for item in payload["items"] if item["symbol"] == "000001.SH")
        fallback_item = next(item for item in payload["items"] if item["symbol"] == "399001.SZ")
        self.assertEqual(live_item["source"], "sina")
        self.assertEqual(live_item["sourceLabel"], "新浪财经")
        self.assertFalse(live_item["isFallback"])
        self.assertEqual(fallback_item["freshness"], "fallback")
        self.assertTrue(fallback_item["isFallback"])

    def test_cn_indices_sina_items_are_not_fallback(self) -> None:
        service = MarketOverviewService()
        now = _fresh_sina_as_of()
        quotes = {
            "000001.SH": {
                "name": "上证指数",
                "symbol": "000001.SH",
                "value": 4107.51,
                "change": 28.88,
                "changePercent": 0.71,
                "sparkline": [4078.63, 4107.51],
                "asOf": now,
            },
            "399001.SZ": {
                "name": "深证成指",
                "symbol": "399001.SZ",
                "value": 10288.10,
                "change": 48.88,
                "changePercent": 0.48,
                "sparkline": [10210.0, 10288.1],
                "asOf": now,
            },
            "399006.SZ": {
                "name": "创业板指",
                "symbol": "399006.SZ",
                "value": 1988.10,
                "change": 8.88,
                "changePercent": 0.45,
                "sparkline": [1978.0, 1988.1],
                "asOf": now,
            },
        }

        with patch.object(service, "_fetch_sina_cn_index_quotes", return_value=quotes):
            payload = service.get_cn_indices()

        self.assertIn(payload["source"], {"sina", "mixed"})
        self.assertFalse(payload["isFallback"])
        live_items = [item for item in payload["items"] if item["source"] == "sina"]
        self.assertGreaterEqual(len(live_items), 3)
        self.assertTrue(all(not item["isFallback"] for item in live_items))
        self.assertTrue(all(item["freshness"] in {"live", "cached", "delayed"} for item in live_items))

    def test_sina_transport_rows_map_to_canonical_cn_symbols(self) -> None:
        service = MarketOverviewService()

        def row(name: str, open_price: str, previous: str, latest: str, high: str, low: str) -> list[str]:
            values = [""] * 32
            values[0] = name
            values[1] = open_price
            values[2] = previous
            values[3] = latest
            values[4] = high
            values[5] = low
            values[30] = "2026-05-14"
            values[31] = "15:00:00"
            return values

        transport_rows = {
            "sh000001": row("上证指数", "4090.00", "4078.63", "4107.51", "4112.00", "4088.10"),
            "sz399001": row("深证成指", "10210.00", "10239.22", "10288.10", "10302.50", "10198.00"),
            "sh000300": row("沪深300", "3900.00", "3892.00", "3918.88", "3928.50", "3888.20"),
        }

        with patch("src.services.market_overview_service.fetch_sina_cn_index_rows", return_value=transport_rows) as mock_fetch:
            quotes = service._fetch_sina_cn_index_quotes()

        mock_fetch.assert_called_once()
        self.assertEqual(quotes["000001.SH"]["symbol"], "000001.SH")
        self.assertEqual(quotes["399001.SZ"]["symbol"], "399001.SZ")
        self.assertEqual(quotes["000300.SH"]["symbol"], "000300.SH")
        self.assertNotIn("000001.SS", quotes)
        self.assertNotIn("000300.SS", quotes)

    def test_cn_indices_service_owns_public_metadata_after_sina_transport_rows(self) -> None:
        service = MarketOverviewService()

        def row(name: str, open_price: str, previous: str, latest: str, high: str, low: str) -> list[str]:
            values = [""] * 32
            values[0] = name
            values[1] = open_price
            values[2] = previous
            values[3] = latest
            values[4] = high
            values[5] = low
            values[30] = "2026-05-14"
            values[31] = "15:00:00"
            return values

        transport_rows = {
            "sh000001": row("上证指数", "4090.00", "4078.63", "4107.51", "4112.00", "4088.10"),
            "sz399001": row("深证成指", "10210.00", "10239.22", "10288.10", "10302.50", "10198.00"),
            "sh000300": row("沪深300", "3900.00", "3892.00", "3918.88", "3928.50", "3888.20"),
        }

        with patch("src.services.market_overview_service.fetch_sina_cn_index_rows", return_value=transport_rows):
            payload = service.get_cn_indices()

        self.assertEqual(payload["source"], "mixed")
        self.assertEqual(payload["sourceLabel"], "多来源")
        self.assertEqual(payload["freshness"], "partial")
        self.assertNotEqual(payload["freshness"], "live")
        self.assertTrue(payload["fallbackUsed"])
        self.assertEqual(payload["warning"], "备用示例数据，不代表当前行情")
        self.assertFalse(payload["isFallback"])
        self.assertTrue(payload["isPartial"])
        self.assertEqual(payload["providerHealth"]["provider"], "mixed")
        self.assertEqual(payload["providerHealth"]["status"], "partial")
        live_item = next(item for item in payload["items"] if item["symbol"] == "000001.SH")
        fallback_item = next(item for item in payload["items"] if item["symbol"] == "399006.SZ")
        self.assertEqual(live_item["source"], "sina")
        self.assertEqual(live_item["sourceLabel"], "新浪财经")
        self.assertFalse(live_item["isFallback"])
        self.assertEqual(fallback_item["source"], "fallback")
        self.assertTrue(fallback_item["isFallback"])

    def test_cn_indices_full_sina_panel_stays_non_fallback_without_warnings(self) -> None:
        service = MarketOverviewService()
        now = _fresh_sina_as_of()
        quotes = {
            str(item["symbol"]): {
                "name": item["name"],
                "symbol": str(item["symbol"]),
                "value": item["value"],
                "change": item["change"],
                "changePercent": item["changePercent"],
                "sparkline": item["sparkline"],
                "asOf": now,
            }
            for item in service._fallback_cn_indices_snapshot()["items"]
        }

        with patch.object(service, "_fetch_sina_cn_index_quotes", return_value=quotes):
            payload = service.get_cn_indices()

        self.assertEqual(payload["source"], "sina")
        self.assertIn(payload["freshness"], {"live", "cached", "delayed"})
        self.assertFalse(payload["fallbackUsed"])
        self.assertFalse(payload["isFallback"])
        self.assertFalse(payload["isPartial"])
        self.assertIsNone(payload["warning"])
        self.assertTrue(all(item["source"] == "sina" for item in payload["items"]))
        self.assertTrue(all(not item["isFallback"] for item in payload["items"]))

    def test_cn_indices_adds_observation_only_cn_provider_health_metadata(self) -> None:
        service = MarketOverviewService()
        now = _fresh_sina_as_of()
        quotes = {
            "000001.SH": {
                "name": "上证指数",
                "symbol": "000001.SH",
                "value": 4107.51,
                "change": 28.88,
                "changePercent": 0.71,
                "sparkline": [4078.63, 4107.51],
                "asOf": now,
            }
        }
        observation_providers = (
            CNProviderHealthSnapshotEntry(
                provider_name="pytdx",
                provider_id="pytdx",
                source_type="public_proxy",
                source_tier="unofficial_public_api",
                trust_level="usable_with_caution",
                freshness_expectation="best_effort_public_broker_quote_snapshot",
                observation_only=True,
                score_contribution_allowed=False,
                dependency_installed=True,
                provider_available=True,
                health_status="healthy",
                supported_capabilities=("cn_history_daily", "cn_name_lookup", "cn_quote", "cn_realtime_quote"),
                unsupported_capabilities=("hk_history_daily",),
                contract_capabilities=("cn_history_daily", "cn_name_lookup", "cn_quote", "cn_realtime_quote"),
                key_required=False,
                cache_required=True,
                background_refresh_recommended=True,
                degradation_reason=None,
                missing_provider_reason=None,
                attempted_at="2026-05-19T02:03:04+00:00",
                timeout_seconds=1.0,
            ),
            CNProviderHealthSnapshotEntry(
                provider_name="akshare",
                provider_id="akshare",
                source_type="public_proxy",
                source_tier="unofficial_public_api",
                trust_level="weak",
                freshness_expectation="best_effort_public_web_quote_snapshot_and_daily_history",
                observation_only=True,
                score_contribution_allowed=False,
                dependency_installed=False,
                provider_available=False,
                health_status="missing_dependency",
                supported_capabilities=("cn_stock_list",),
                unsupported_capabilities=("hk_index_quote",),
                contract_capabilities=("cn_stock_list", "cn_market_stats"),
                key_required=False,
                cache_required=True,
                background_refresh_recommended=True,
                degradation_reason="akshare_not_installed",
                missing_provider_reason="akshare_not_installed",
                attempted_at=None,
                timeout_seconds=1.0,
            ),
            CNProviderHealthSnapshotEntry(
                provider_name="baostock",
                provider_id="baostock",
                source_type="public_proxy",
                source_tier="third_party_free_api",
                trust_level="usable_with_caution",
                freshness_expectation="t_plus_1_or_delayed",
                observation_only=True,
                score_contribution_allowed=False,
                dependency_installed=True,
                provider_available=False,
                health_status="probe_disabled",
                supported_capabilities=("cn_adjust_factor", "cn_basic_financials", "cn_history_daily", "cn_index_history_daily"),
                unsupported_capabilities=("cn_quote",),
                contract_capabilities=("cn_adjust_factor", "cn_basic_financials", "cn_history_daily", "cn_index_history_daily"),
                key_required=False,
                cache_required=True,
                background_refresh_recommended=True,
                degradation_reason="baostock_live_probe_disabled",
                missing_provider_reason="baostock_live_probe_disabled",
                attempted_at=None,
                timeout_seconds=1.0,
            ),
        )

        with (
            patch.object(service, "_fetch_sina_cn_index_quotes", return_value=quotes),
            patch("src.services.cn_provider_health_service.CNProviderHealthService.get_snapshot", return_value=observation_providers),
        ):
            payload = service.get_cn_indices()

        provider_health = payload["providerHealth"]
        self.assertIn("observationProviders", provider_health)
        self.assertEqual([item["providerId"] for item in provider_health["observationProviders"]], ["pytdx", "akshare", "baostock"])
        self.assertTrue(all(set(item) == EXPECTED_CN_PROVIDER_HEALTH_ENTRY_FIELDS for item in provider_health["observationProviders"]))
        self.assertTrue(all(not FORBIDDEN_CN_PROVIDER_HEALTH_FIELDS.intersection(item) for item in provider_health["observationProviders"]))
        self.assertTrue(all(item["observationOnly"] is True for item in provider_health["observationProviders"]))
        self.assertTrue(all(item["scoreContributionAllowed"] is False for item in provider_health["observationProviders"]))
        self.assertTrue(all(item["keyRequired"] is False for item in provider_health["observationProviders"]))
        self.assertTrue(all(item["cacheRequired"] is True for item in provider_health["observationProviders"]))
        self.assertTrue(all(item["backgroundRefreshRecommended"] is True for item in provider_health["observationProviders"]))
        self.assertEqual(provider_health["observationProviders"][0]["trustLevel"], "usable_with_caution")
        self.assertEqual(provider_health["observationProviders"][1]["trustLevel"], "weak")
        self.assertEqual(provider_health["observationProviders"][2]["trustLevel"], "usable_with_caution")
        self.assertEqual(provider_health["observationProviders"][0]["sourceTier"], "unofficial_public_api")
        self.assertEqual(provider_health["observationProviders"][1]["sourceTier"], "unofficial_public_api")
        self.assertEqual(provider_health["observationProviders"][2]["sourceTier"], "third_party_free_api")
        self.assertEqual(provider_health["observationProviders"][1]["healthStatus"], "missing_dependency")
        self.assertEqual(provider_health["observationProviders"][2]["healthStatus"], "probe_disabled")
        self.assertEqual(payload["items"][0]["source"], "sina")

    def test_cn_indices_rejects_observation_provider_entries_that_claim_scoring_authority(self) -> None:
        service = MarketOverviewService()
        now = _fresh_sina_as_of()
        quotes = {
            "000001.SH": {
                "name": "上证指数",
                "symbol": "000001.SH",
                "value": 4107.51,
                "change": 28.88,
                "changePercent": 0.71,
                "sparkline": [4078.63, 4107.51],
                "asOf": now,
            }
        }
        observation_providers = (
            CNProviderHealthSnapshotEntry(
                provider_name="pytdx",
                provider_id="pytdx",
                source_type="public_proxy",
                source_tier="unofficial_public_api",
                trust_level="usable_with_caution",
                freshness_expectation="best_effort_public_broker_quote_snapshot",
                observation_only=False,
                score_contribution_allowed=True,
                dependency_installed=True,
                provider_available=True,
                health_status="healthy",
                supported_capabilities=("cn_realtime_quote",),
                unsupported_capabilities=(),
                contract_capabilities=("cn_realtime_quote",),
                key_required=False,
                cache_required=True,
                background_refresh_recommended=True,
                degradation_reason=None,
                missing_provider_reason=None,
                attempted_at="2026-05-19T02:03:04+00:00",
                timeout_seconds=1.0,
            ),
        )

        with (
            patch.object(service, "_fetch_sina_cn_index_quotes", return_value=quotes),
            patch("src.services.cn_provider_health_service.CNProviderHealthService.get_snapshot", return_value=observation_providers),
        ):
            payload = service.get_cn_indices()

        entry = payload["providerHealth"]["observationProviders"][0]
        self.assertEqual(entry["providerId"], "pytdx")
        self.assertEqual(entry["sourceType"], "public_proxy")
        self.assertEqual(entry["sourceTier"], "unofficial_public_api")
        self.assertEqual(entry["trustLevel"], "usable_with_caution")
        self.assertTrue(entry["observationOnly"])
        self.assertFalse(entry["scoreContributionAllowed"])
        self.assertFalse(entry["providerAvailable"])
        self.assertEqual(entry["healthStatus"], "rejected")
        self.assertEqual(entry["degradationReason"], "market_overview_observation_authority_claim_rejected")
        self.assertIn("scoring_authority_claim", entry["missingProviderReason"])
        self.assertEqual(payload["items"][0]["source"], "sina")

    def test_normalize_akshare_cn_index_observation_records_maps_codes_and_dedupes(self) -> None:
        service = MarketOverviewService()
        attempted_at = "2026-05-19T09:30:00+08:00"

        records = service._normalize_akshare_cn_index_observation_records(
            [
                {"code": "sh000001", "name": "上证指数", "current": 4107.51},
                {"code": "sh000300", "name": "沪深300", "current": 3918.88},
                {"code": "sh000001", "name": "上证指数", "current": 4108.00},
                {"code": "unsupported", "name": "忽略", "current": 1.0},
            ],
            attempted_at=attempted_at,
        )

        self.assertEqual([record["canonicalSymbol"] for record in records], ["000001.SH", "000300.SH"])
        self.assertTrue(all(record["providerName"] == "akshare" for record in records))
        self.assertTrue(all(record["sourceType"] == "public_proxy" for record in records))
        self.assertTrue(all(record["sourceTier"] == "unofficial_public_api" for record in records))
        self.assertTrue(all(record["trustLevel"] == "weak" for record in records))
        self.assertTrue(all(record["observationOnly"] is True for record in records))
        self.assertTrue(all(record["scoreContributionAllowed"] is False for record in records))
        self.assertTrue(all(record["freshness"] == "unavailable" for record in records))
        self.assertTrue(all(record["asOf"] is None for record in records))
        self.assertTrue(all(record["updatedAt"] == attempted_at for record in records))
        self.assertTrue(all(record["providerTimestampAvailable"] is False for record in records))
        self.assertTrue(all("current" not in record for record in records))

    def test_cn_indices_projects_akshare_observation_coverage_without_appending_rows(self) -> None:
        service = MarketOverviewService()
        now = _fresh_sina_as_of()
        quotes = {
            "000001.SH": {
                "name": "上证指数",
                "symbol": "000001.SH",
                "value": 4107.51,
                "change": 28.88,
                "changePercent": 0.71,
                "sparkline": [4078.63, 4107.51],
                "asOf": now,
            }
        }
        akshare_rows = [
            {"code": "sh000001", "name": "上证指数", "current": 4107.51},
            {"code": "sh000300", "name": "沪深300", "current": 3918.88},
        ]

        with (
            patch.object(service, "_fetch_sina_cn_index_quotes", return_value=quotes),
            patch("data_provider.akshare_fetcher.AkshareFetcher.get_main_indices", return_value=akshare_rows),
        ):
            payload = service.get_cn_indices()

        coverage = payload["providerHealth"]["observationCoverage"]["akshare"]
        self.assertEqual(coverage["providerName"], "akshare")
        self.assertEqual(coverage["sourceType"], "public_proxy")
        self.assertEqual(coverage["sourceTier"], "unofficial_public_api")
        self.assertEqual(coverage["trustLevel"], "weak")
        self.assertTrue(coverage["observationOnly"])
        self.assertFalse(coverage["scoreContributionAllowed"])
        self.assertNotIn(coverage["freshness"], {"live", "fresh"})
        self.assertIn(coverage["freshness"], {"delayed", "stale", "unavailable"})
        self.assertEqual(coverage["coverageCount"], 2)
        self.assertEqual(coverage["matchedCanonicalSymbols"], ["000001.SH", "000300.SH"])
        self.assertEqual(
            coverage["missingExpectedSymbols"],
            ["399001.SZ", "399006.SZ", "000688.SH", "000016.SH"],
        )
        self.assertEqual(coverage["partialCoverageReason"], "partial_coverage")
        self.assertEqual(coverage["degradationReason"], "partial_coverage")
        self.assertFalse(coverage["providerTimestampAvailable"])
        self.assertIsNone(coverage["asOf"])
        self.assertEqual(coverage["freshness"], "unavailable")
        self.assertEqual(len(payload["items"]), len(service._fallback_cn_indices_snapshot()["items"]))
        self.assertTrue(all(item["source"] != "akshare" for item in payload["items"]))
        self.assertEqual(next(item for item in payload["items"] if item["symbol"] == "000001.SH")["source"], "sina")
        self.assertEqual(next(item for item in payload["items"] if item["symbol"] == "000300.SH")["source"], "fallback")

    def test_cn_indices_rejects_akshare_observation_coverage_that_claims_live_authority(self) -> None:
        service = MarketOverviewService()
        now = _fresh_sina_as_of()
        quotes = {
            "000001.SH": {
                "name": "上证指数",
                "symbol": "000001.SH",
                "value": 4107.51,
                "change": 28.88,
                "changePercent": 0.71,
                "sparkline": [4078.63, 4107.51],
                "asOf": now,
            }
        }

        with (
            patch.object(service, "_fetch_sina_cn_index_quotes", return_value=quotes),
            patch.object(
                service,
                "_fetch_akshare_cn_index_observation_rows",
                return_value=[{"code": "sh000001"}, {"code": "sh000300"}],
            ),
            patch.object(
                service,
                "_normalize_akshare_cn_index_observation_records",
                return_value=[
                    {
                        "providerName": "akshare",
                        "providerSymbol": "sh000001",
                        "canonicalSymbol": "000001.SH",
                        "sourceType": "public_proxy",
                        "sourceTier": "unofficial_public_api",
                        "trustLevel": "weak",
                        "observationOnly": True,
                        "scoreContributionAllowed": False,
                        "freshness": "live",
                        "asOf": now,
                        "updatedAt": now,
                        "providerTimestampAvailable": False,
                    },
                    {
                        "providerName": "akshare",
                        "providerSymbol": "sh000300",
                        "canonicalSymbol": "000300.SH",
                        "sourceType": "public_proxy",
                        "sourceTier": "unofficial_public_api",
                        "trustLevel": "weak",
                        "observationOnly": True,
                        "scoreContributionAllowed": False,
                        "freshness": "live",
                        "asOf": now,
                        "updatedAt": now,
                        "providerTimestampAvailable": False,
                    },
                ],
            ),
        ):
            payload = service.get_cn_indices()

        coverage = payload["providerHealth"]["observationCoverage"]["akshare"]
        self.assertEqual(coverage["freshness"], "unavailable")
        self.assertTrue(coverage["observationOnly"])
        self.assertFalse(coverage["scoreContributionAllowed"])
        self.assertEqual(coverage["coverageCount"], 0)
        self.assertEqual(coverage["matchedCanonicalSymbols"], [])
        self.assertEqual(coverage["degradationReason"], "market_overview_observation_authority_claim_rejected")
        self.assertIn("live_authority_claim", coverage["routeRejectedReasonCodes"])
        self.assertEqual(next(item for item in payload["items"] if item["symbol"] == "000001.SH")["source"], "sina")

    def test_cn_indices_keeps_existing_fallback_when_observation_providers_are_degraded(self) -> None:
        service = MarketOverviewService()
        observation_providers = (
            CNProviderHealthSnapshotEntry(
                provider_name="pytdx",
                provider_id="pytdx",
                source_type="public_proxy",
                source_tier="unofficial_public_api",
                trust_level="usable_with_caution",
                freshness_expectation="best_effort_public_broker_quote_snapshot",
                observation_only=True,
                score_contribution_allowed=False,
                dependency_installed=False,
                provider_available=False,
                health_status="missing_dependency",
                supported_capabilities=("cn_history_daily",),
                unsupported_capabilities=("hk_history_daily",),
                contract_capabilities=("cn_history_daily",),
                key_required=False,
                cache_required=True,
                background_refresh_recommended=True,
                degradation_reason="pytdx_not_installed",
                missing_provider_reason="pytdx_not_installed",
                attempted_at=None,
                timeout_seconds=1.0,
            ),
            CNProviderHealthSnapshotEntry(
                provider_name="akshare",
                provider_id="akshare",
                source_type="public_proxy",
                source_tier="unofficial_public_api",
                trust_level="weak",
                freshness_expectation="best_effort_public_web_quote_snapshot_and_daily_history",
                observation_only=True,
                score_contribution_allowed=False,
                dependency_installed=True,
                provider_available=False,
                health_status="probe_failure",
                supported_capabilities=("cn_market_stats",),
                unsupported_capabilities=("hk_index_quote",),
                contract_capabilities=("cn_market_stats",),
                key_required=False,
                cache_required=True,
                background_refresh_recommended=True,
                degradation_reason="akshare_probe_failed",
                missing_provider_reason="akshare_probe_failed",
                attempted_at="2026-05-19T02:03:05+00:00",
                timeout_seconds=1.0,
            ),
            CNProviderHealthSnapshotEntry(
                provider_name="baostock",
                provider_id="baostock",
                source_type="public_proxy",
                source_tier="third_party_free_api",
                trust_level="usable_with_caution",
                freshness_expectation="t_plus_1_or_delayed",
                observation_only=True,
                score_contribution_allowed=False,
                dependency_installed=True,
                provider_available=False,
                health_status="probe_disabled",
                supported_capabilities=("cn_history_daily",),
                unsupported_capabilities=("cn_quote",),
                contract_capabilities=("cn_adjust_factor", "cn_basic_financials", "cn_history_daily", "cn_index_history_daily"),
                key_required=False,
                cache_required=True,
                background_refresh_recommended=True,
                degradation_reason="baostock_live_probe_disabled",
                missing_provider_reason="baostock_live_probe_disabled",
                attempted_at=None,
                timeout_seconds=1.0,
            ),
        )

        with (
            patch.object(service, "_fetch_sina_cn_index_quotes", side_effect=RuntimeError("provider down")),
            patch("src.services.cn_provider_health_service.CNProviderHealthService.get_snapshot", return_value=observation_providers),
        ):
            payload = service.get_cn_indices()

        self.assertEqual(payload["source"], "fallback")
        self.assertTrue(payload["items"])
        self.assertTrue(all(item["isFallback"] for item in payload["items"]))
        self.assertEqual(
            [item["healthStatus"] for item in payload["providerHealth"]["observationProviders"]],
            ["missing_dependency", "probe_failure", "probe_disabled"],
        )
        self.assertTrue(all(item["observationOnly"] is True for item in payload["providerHealth"]["observationProviders"]))
        self.assertTrue(all(item["scoreContributionAllowed"] is False for item in payload["providerHealth"]["observationProviders"]))

    def test_cn_indices_test_reset_ignores_leaked_persistent_snapshot_state(self) -> None:
        old_database_path = os.environ.get("DATABASE_PATH")
        old_snapshot_db_flag = os.environ.get("MARKET_OVERVIEW_SNAPSHOT_TEST_DB")
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "cn-indices-leak.sqlite"
        leaked_snapshot = {
            "source": "mixed",
            "sourceLabel": "多来源",
            "freshness": "partial",
            "updatedAt": "2026-05-19T09:30:00+08:00",
            "asOf": "2026-05-19T09:30:00+08:00",
            "fallbackUsed": True,
            "items": [
                {
                    "name": "上证指数",
                    "symbol": "000001.SH",
                    "value": 4107.51,
                    "change": 28.88,
                    "changePercent": 0.71,
                    "sparkline": [4078.63, 4107.51],
                    "source": "sina",
                    "sourceLabel": "新浪财经",
                    "updatedAt": "2026-05-19T09:30:00+08:00",
                    "asOf": "2026-05-19T09:30:00+08:00",
                },
                {
                    "name": "深证成指",
                    "symbol": "399001.SZ",
                    "value": 9820.42,
                    "change": 52.18,
                    "changePercent": 0.53,
                    "sparkline": [9722.0, 9820.42],
                    "source": "fallback",
                    "sourceLabel": "备用数据",
                    "freshness": "fallback",
                    "isFallback": True,
                    "updatedAt": "2026-05-19T09:30:00+08:00",
                    "asOf": "2026-05-19T09:30:00+08:00",
                },
            ],
        }

        try:
            os.environ["DATABASE_PATH"] = str(db_path)
            os.environ["MARKET_OVERVIEW_SNAPSHOT_TEST_DB"] = "1"
            DatabaseManager.reset_instance()
            DatabaseManager(db_url=f"sqlite:///{db_path}").save_market_overview_snapshot(
                key="market_overview:cn_indices",
                payload=leaked_snapshot,
            )

            contaminated_service = MarketOverviewService()
            with patch.object(contaminated_service, "_fetch_sina_cn_index_quotes", side_effect=RuntimeError("provider down")):
                contaminated = contaminated_service.get_cn_indices()
            self.assertEqual(contaminated["source"], "mixed")

            _reset_market_test_state()

            isolated_service = MarketOverviewService()
            with patch.object(isolated_service, "_fetch_sina_cn_index_quotes", side_effect=RuntimeError("provider down")):
                isolated = isolated_service.get_cn_indices()
            self.assertEqual(isolated["source"], "fallback")
            self.assertTrue(all(item["isFallback"] for item in isolated["items"]))
        finally:
            if old_database_path is None:
                os.environ.pop("DATABASE_PATH", None)
            else:
                os.environ["DATABASE_PATH"] = old_database_path
            if old_snapshot_db_flag is None:
                os.environ.pop("MARKET_OVERVIEW_SNAPSHOT_TEST_DB", None)
            else:
                os.environ["MARKET_OVERVIEW_SNAPSHOT_TEST_DB"] = old_snapshot_db_flag
            DatabaseManager.reset_instance()
            temp_dir.cleanup()

    def test_cn_indices_reuses_cached_observation_provider_health_by_default(self) -> None:
        service = MarketOverviewService()
        now = _fresh_sina_as_of()
        quotes = {
            "000001.SH": {
                "name": "上证指数",
                "symbol": "000001.SH",
                "value": 4107.51,
                "change": 28.88,
                "changePercent": 0.71,
                "sparkline": [4078.63, 4107.51],
                "asOf": now,
            }
        }
        calls = {"pytdx": 0, "akshare": 0, "baostock": 0}

        def pytdx_probe(timeout_seconds: float) -> dict:
            calls["pytdx"] += 1
            return {
                "providerName": "pytdx",
                "providerId": "pytdx",
                "dependencyInstalled": True,
                "providerAvailable": True,
                "supportedCapabilities": [
                    "cn_history_daily",
                    "cn_name_lookup",
                    "cn_quote",
                    "cn_realtime_quote",
                ],
                "unsupportedCapabilities": ["hk_history_daily"],
                "degradationReason": None,
                "missingProviderReason": None,
                "attemptedAt": f"2026-05-19T02:03:0{calls['pytdx']}+00:00",
                "timeoutSeconds": timeout_seconds,
                "serverHealth": "reachable",
            }

        def akshare_probe(timeout_seconds: float) -> dict:
            calls["akshare"] += 1
            raise TimeoutError("AKShare probe timed out")

        def baostock_probe(timeout_seconds: float) -> dict:
            calls["baostock"] += 1
            return {
                "providerName": "baostock",
                "providerId": "baostock",
                "dependencyInstalled": True,
                "providerAvailable": False,
                "supportedCapabilities": [
                    "cn_adjust_factor",
                    "cn_basic_financials",
                    "cn_history_daily",
                    "cn_index_history_daily",
                ],
                "unsupportedCapabilities": ["cn_quote"],
                "degradationReason": "baostock_live_probe_disabled",
                "missingProviderReason": "baostock_live_probe_disabled",
                "attemptedAt": None,
                "timeoutSeconds": timeout_seconds,
                "serverHealth": "probe_disabled",
                "healthStatus": "probe_disabled",
            }

        with (
            patch.object(service, "_fetch_sina_cn_index_quotes", return_value=quotes),
            patch(
                "src.services.market_overview_service.CNProviderHealthService",
                side_effect=lambda: health_service_module.CNProviderHealthService(
                    pytdx_probe=pytdx_probe,
                    akshare_probe=akshare_probe,
                    baostock_probe=baostock_probe,
                ),
            ),
        ):
            first = service.get_cn_indices()
            second = service.get_cn_indices()

        self.assertEqual(calls, {"pytdx": 1, "akshare": 1, "baostock": 1})
        first_observation = {item["providerId"]: item for item in first["providerHealth"]["observationProviders"]}
        second_observation = {item["providerId"]: item for item in second["providerHealth"]["observationProviders"]}
        self.assertEqual(first_observation["pytdx"]["attemptedAt"], "2026-05-19T02:03:01+00:00")
        self.assertEqual(second_observation["pytdx"]["attemptedAt"], "2026-05-19T02:03:01+00:00")
        self.assertEqual(first_observation["akshare"]["healthStatus"], "timeout")
        self.assertEqual(second_observation["akshare"]["healthStatus"], "timeout")
        self.assertEqual(first_observation["akshare"]["degradationReason"], "akshare_probe_timeout")
        self.assertEqual(second_observation["akshare"]["degradationReason"], "akshare_probe_timeout")
        self.assertEqual(first_observation["baostock"]["healthStatus"], "probe_disabled")
        self.assertEqual(second_observation["baostock"]["healthStatus"], "probe_disabled")

    def test_cn_indices_uses_cache_within_ttl(self) -> None:
        calls = 0

        def fetcher(self: MarketOverviewService) -> dict:
            nonlocal calls
            calls += 1
            updated_at = _fresh_sina_as_of()
            return {
                "source": "sina",
                "updatedAt": updated_at,
                "asOf": updated_at,
                "items": [
                    {
                        "name": "上证指数",
                        "symbol": "000001.SH",
                        "value": 4100 + calls,
                        "change": 1,
                        "changePercent": 0.1,
                        "sparkline": [4090, 4100 + calls],
                        "source": "sina",
                        "asOf": updated_at,
                    }
                ],
            }

        with patch.object(MarketOverviewService, "_fetch_cn_indices_snapshot", fetcher):
            first = market.get_cn_indices()
            second = market.get_cn_indices()

        self.assertEqual(calls, 1)
        self.assertEqual(second["items"][0]["value"], first["items"][0]["value"])
        self.assertIn("isRefreshing", second)

    def test_cn_indices_cache_is_shared_across_service_instances(self) -> None:
        calls = 0

        def fetcher(self: MarketOverviewService) -> dict:
            nonlocal calls
            calls += 1
            updated_at = _fresh_sina_as_of()
            return {
                "source": "sina",
                "updatedAt": updated_at,
                "asOf": updated_at,
                "items": [
                    {
                        "name": "上证指数",
                        "symbol": "000001.SH",
                        "value": 4100 + calls,
                        "change": 1,
                        "changePercent": 0.1,
                        "sparkline": [4090, 4100 + calls],
                        "source": "sina",
                        "asOf": updated_at,
                    }
                ],
            }

        with patch.object(MarketOverviewService, "_fetch_cn_indices_snapshot", fetcher):
            first = MarketOverviewService().get_cn_indices()
            second = MarketOverviewService().get_cn_indices()

        self.assertEqual(calls, 1)
        self.assertEqual(second["items"][0]["value"], first["items"][0]["value"])

    def test_authenticated_http_cn_indices_returns_cache_metadata(self) -> None:
        _reset_auth_globals()
        temp_dir = tempfile.TemporaryDirectory()
        data_dir = Path(temp_dir.name)
        env_path = data_dir / ".env"
        db_path = data_dir / "market_http_test.db"
        env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=true",
                    f"DATABASE_PATH={db_path}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(env_path)
        os.environ["DATABASE_PATH"] = str(db_path)
        Config.reset_instance()
        DatabaseManager.reset_instance()

        updated_at = _fresh_sina_as_of()

        def fetcher(self: MarketOverviewService) -> dict:
            return {
                "source": "sina",
                "sourceLabel": "新浪财经",
                "updatedAt": updated_at,
                "asOf": updated_at,
                "items": [
                    {
                        "name": "上证指数",
                        "symbol": "000001.SH",
                        "value": 4107.51,
                        "change": 28.88,
                        "changePercent": 0.71,
                        "sparkline": [4078.63, 4107.51],
                        "source": "sina",
                        "sourceLabel": "新浪财经",
                        "asOf": updated_at,
                    }
                ],
            }

        try:
            app = create_app(static_dir=data_dir / "empty-static")
            client = TestClient(app)
            login_response = client.post(
                "/api/v1/auth/login",
                json={"password": "marketpass", "passwordConfirm": "marketpass"},
            )
            self.assertEqual(login_response.status_code, 200)

            with patch.object(MarketOverviewService, "_fetch_cn_indices_snapshot", fetcher):
                response = client.get("/api/v1/market/cn-indices")

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            for field in (
                "freshness",
                "source",
                "sourceLabel",
                "asOf",
                "updatedAt",
                "isRefreshing",
                "isFallback",
                "warning",
            ):
                self.assertIn(field, payload)
            self.assertEqual(payload["source"], "sina")
            self.assertEqual(payload["sourceLabel"], "新浪财经")
            self.assertEqual(payload["asOf"], updated_at)
            self.assertEqual(payload["updatedAt"], updated_at)
            self.assertIn(payload["freshness"], {"live", "cached", "delayed"})
            first_item = payload["items"][0]
            self.assertEqual(first_item["source"], "sina")
            self.assertEqual(first_item["sourceLabel"], "新浪财经")
            self.assertEqual(first_item["asOf"], updated_at)
            self.assertEqual(first_item["updatedAt"], updated_at)
            self.assertIn(first_item["freshness"], {"live", "cached", "delayed"})
            self.assertFalse(first_item["isFallback"])
        finally:
            DatabaseManager.reset_instance()
            Config.reset_instance()
            _reset_auth_globals()
            os.environ.pop("ENV_FILE", None)
            os.environ.pop("DATABASE_PATH", None)
            temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
