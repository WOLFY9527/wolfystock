# -*- coding: utf-8 -*-
"""Contract and fallback tests for market crypto endpoint."""

from __future__ import annotations

import unittest
import threading
import time
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from api.v1.endpoints import market
from data_provider.coinbase_public_provider import parse_ticker_payload
from src.services.market_data_source_registry import project_source_provenance
from src.services.market_overview_service import MarketOverviewService


CN_TZ = timezone(timedelta(hours=8))
COINBASE_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "coinbase_public" / "ticker_sample.json"


class MarketCryptoApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        MarketOverviewService._market_cache.clear()
        MarketOverviewService._market_data_cache.clear()

    def test_get_crypto_returns_contract_payload(self) -> None:
        service = MagicMock()
        service.get_crypto.return_value = {
            "items": [
                {
                    "symbol": "BTC",
                    "price": 76837.04,
                    "change": 1.47,
                    "trend": [74211.0, 75120.0, 76837.04],
                    "last_update": "2026-04-29T10:00:00",
                    "error": None,
                }
            ],
            "last_update": "2026-04-29T10:00:00",
            "error": None,
            "fallback_used": False,
            "source": "binance",
        }

        with patch("api.v1.endpoints.market.MarketOverviewService", return_value=service):
            payload = market.get_crypto()

        self.assertEqual(payload["source"], "binance")
        self.assertFalse(payload["fallback_used"])
        self.assertEqual(payload["items"][0]["symbol"], "BTC")
        self.assertIn("price", payload["items"][0])
        self.assertIn("change", payload["items"][0])
        self.assertIn("trend", payload["items"][0])
        self.assertIn("last_update", payload["items"][0])
        self.assertIn("error", payload["items"][0])

    def test_get_crypto_falls_back_to_last_successful_snapshot(self) -> None:
        service = MarketOverviewService()
        service._market_data_cache["crypto"] = {
            "items": [
                {
                    "symbol": "BTC",
                    "price": 73000.0,
                    "change": 0.5,
                    "trend": [70000.0, 72000.0, 73000.0],
                    "last_update": "2026-04-29T09:00:00",
                    "error": None,
                }
            ],
            "last_update": "2026-04-29T09:00:00",
            "error": None,
            "fallback_used": False,
            "source": "binance",
        }

        with patch.object(service, "_fetch_crypto_market_snapshot", side_effect=RuntimeError("binance down")):
            payload = service.get_crypto()

        self.assertTrue(payload["fallback_used"])
        self.assertEqual(payload["items"][0]["price"], 73000.0)
        self.assertEqual(payload["error"], "更新失败：已回退到最近一次有效数据")
        self.assertEqual(payload["providerHealth"]["errorSummary"], "数据源暂不可用")
        self.assertNotIn("binance down", str(payload))

    def test_get_crypto_uses_cache_within_ttl(self) -> None:
        calls = 0

        def fetcher(self: MarketOverviewService) -> dict:
            nonlocal calls
            calls += 1
            updated_at = datetime(2026, 4, 30, 10, calls, tzinfo=CN_TZ).isoformat(timespec="seconds")
            return {
                "items": [
                    {
                        "symbol": "BTC",
                        "price": 70000 + calls,
                        "change": 1.0,
                        "trend": [69000, 70000 + calls],
                        "last_update": updated_at,
                        "source": "binance",
                    }
                ],
                "last_update": updated_at,
                "source": "binance",
                "fallback_used": False,
            }

        with patch.object(MarketOverviewService, "_fetch_crypto_market_snapshot", fetcher):
            first = market.get_crypto()
            second = market.get_crypto()

        self.assertEqual(calls, 1)
        self.assertEqual(second["items"][0]["price"], first["items"][0]["price"])
        self.assertIn("isRefreshing", second)

    def test_crypto_cold_cache_fast_fallback_when_binance_slow(self) -> None:
        service = MarketOverviewService()
        service.MARKET_COLD_START_TIMEOUT_SECONDS = 0.05
        release_fetch = threading.Event()

        def fetcher() -> dict:
            release_fetch.wait(2)
            return {
                "items": [{"symbol": "BTC", "price": 71000, "change": 1, "trend": [70000, 71000], "source": "binance"}],
                "last_update": datetime(2026, 4, 30, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds"),
                "source": "binance",
                "fallback_used": False,
            }

        start = time.monotonic()
        with patch.object(service, "_fetch_crypto_market_snapshot", side_effect=fetcher):
            payload = service.get_crypto()
        elapsed = time.monotonic() - start

        self.assertLess(elapsed, 0.5)
        self.assertTrue(payload["items"])
        self.assertEqual(payload["freshness"], "unavailable")
        self.assertFalse(payload["isFallback"])
        self.assertTrue(payload["fallbackUsed"])
        self.assertTrue(payload["isUnavailable"])
        self.assertTrue(payload["isRefreshing"])
        self.assertEqual(payload["source"], "unavailable")
        self.assertEqual(payload["sourceLabel"], "未接入")
        self.assertIn("未生成备用价格", payload["warning"])
        self.assertTrue(all(item.get("value") is None for item in payload["items"]))
        release_fetch.set()
        self.assertTrue(service._market_cache.wait_for_refreshes(timeout=2))

    def test_crypto_cache_hit_does_not_refetch(self) -> None:
        service = MarketOverviewService()
        calls = 0

        def fetcher() -> dict:
            nonlocal calls
            calls += 1
            return {
                "items": [{"symbol": "BTC", "price": 70000 + calls, "change": 1, "trend": [69000, 70000 + calls], "source": "binance"}],
                "last_update": datetime(2026, 4, 30, 10, calls, tzinfo=CN_TZ).isoformat(timespec="seconds"),
                "source": "binance",
                "fallback_used": False,
            }

        with patch.object(service, "_fetch_crypto_market_snapshot", side_effect=fetcher):
            first = service.get_crypto()
            second = service.get_crypto()

        self.assertEqual(calls, 1)
        self.assertEqual(second["items"][0]["price"], first["items"][0]["price"])
        self.assertFalse(second["isRefreshing"])

    def test_crypto_stale_returns_old_snapshot_and_refreshes(self) -> None:
        service = MarketOverviewService()
        old_time = datetime(2026, 4, 30, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
        new_time = datetime(2026, 4, 30, 10, 1, tzinfo=CN_TZ).isoformat(timespec="seconds")
        service._market_cache.set(
            "crypto",
            {
                "items": [{"symbol": "BTC", "price": 70000, "change": 1, "trend": [69000, 70000], "source": "binance", "last_update": old_time}],
                "last_update": old_time,
                "source": "binance",
                "fallback_used": False,
            },
            ttl_seconds=1,
        )
        entry = service._market_cache.get("crypto")
        entry.expires_at = entry.fetched_at - timedelta(seconds=1)
        release_refresh = threading.Event()

        def fetcher() -> dict:
            release_refresh.wait(2)
            return {
                "items": [{"symbol": "BTC", "price": 72000, "change": 2, "trend": [70000, 72000], "source": "binance", "last_update": new_time}],
                "last_update": new_time,
                "source": "binance",
                "fallback_used": False,
            }

        with patch.object(service, "_fetch_crypto_market_snapshot", side_effect=fetcher):
            stale = service.get_crypto()
            self.assertEqual(stale["items"][0]["price"], 70000)
            self.assertEqual(stale["source"], "binance")
            self.assertEqual(stale["sourceLabel"], "Binance")
            self.assertEqual(stale["freshness"], "stale")
            self.assertTrue(stale["isStale"])
            self.assertFalse(stale["isFallback"])
            self.assertTrue(stale["isRefreshing"])
            self.assertEqual(stale["items"][0]["freshness"], "stale")
            self.assertTrue(stale["items"][0]["isStale"])
            self.assertFalse(stale["items"][0]["isFallback"])
            release_refresh.set()
            self.assertTrue(service._market_cache.wait_for_refreshes(timeout=2))
            refreshed = service.get_crypto()

        self.assertEqual(refreshed["items"][0]["price"], 72000)
        self.assertFalse(refreshed["isRefreshing"])

    def test_crypto_fallback_shape_matches_frontend(self) -> None:
        service = MarketOverviewService()

        with patch.object(service, "_fetch_crypto_market_snapshot", side_effect=RuntimeError("binance down")):
            payload = service.get_crypto()

        symbols = {item["symbol"] for item in payload["items"]}
        self.assertTrue({"BTC", "ETH", "BNB"}.issubset(symbols))
        self.assertEqual(payload["freshness"], "unavailable")
        self.assertFalse(payload["isFallback"])
        self.assertTrue(payload["fallbackUsed"])
        self.assertTrue(payload["isUnavailable"])
        self.assertNotEqual(payload["freshness"], "live")
        self.assertEqual(payload["source"], "unavailable")
        self.assertIn("未生成备用价格", payload["warning"])
        for item in payload["items"]:
            self.assertIn("symbol", item)
            self.assertIn("name", item)
            self.assertIn("value", item)
            self.assertIn("changePercent", item)
            self.assertIn("sparkline", item)
            self.assertIsNone(item["value"])
            self.assertIsNone(item["changePercent"])
            self.assertTrue(item["isUnavailable"])

    def test_crypto_real_snapshot_counts_as_real(self) -> None:
        service = MarketOverviewService()
        updated_at = datetime.now(CN_TZ).isoformat(timespec="seconds")
        snapshot = {
            "items": [
                {
                    "symbol": "BTC",
                    "label": "Bitcoin",
                    "price": 87000.0,
                    "value": 87000.0,
                    "change": 1.2,
                    "changePercent": 1.2,
                    "trend": [86000.0, 86500.0, 87000.0],
                    "source": "binance",
                    "last_update": updated_at,
                }
            ],
            "last_update": updated_at,
            "updatedAt": updated_at,
            "asOf": updated_at,
            "fallback_used": False,
            "fallbackUsed": False,
            "source": "binance",
        }

        with patch.object(service, "_fetch_crypto_market_snapshot", return_value=snapshot):
            payload = service.get_crypto()

        provenance = project_source_provenance(
            source=payload.get("source"),
            source_type=payload.get("sourceType"),
            source_label=payload.get("sourceLabel"),
            freshness=payload.get("freshness"),
            is_fallback=bool(payload.get("isFallback") or payload.get("fallbackUsed") or payload.get("fallback_used")),
            is_stale=bool(payload.get("isStale")),
        )
        item_provenance = project_source_provenance(
            source=payload["items"][0].get("source"),
            source_type=payload["items"][0].get("sourceType"),
            source_label=payload["items"][0].get("sourceLabel"),
            freshness=payload["items"][0].get("freshness") or payload.get("freshness"),
            is_fallback=bool(payload["items"][0].get("isFallback") or payload["items"][0].get("fallbackUsed")),
            is_stale=bool(payload["items"][0].get("isStale")),
        )
        self.assertEqual(payload["source"], "binance")
        self.assertFalse(payload["isFallback"])
        self.assertIn(payload["freshness"], {"live", "delayed", "cached"})
        self.assertEqual(provenance["sourceType"], "exchange_public")
        self.assertEqual(item_provenance["sourceType"], "exchange_public")

    def test_fetch_crypto_market_snapshot_keeps_shape_via_binance_transport_boundary(self) -> None:
        service = MarketOverviewService()
        updated_at = datetime(2026, 4, 30, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")

        with (
            patch("src.services.market_overview_service.fetch_binance_ticker_snapshot") as ticker_fetch,
            patch.object(service, "_fetch_binance_kline_histories", return_value={"BTCUSDT": [70000.0, 71000.0]}),
            patch.object(service, "_fetch_binance_funding_items", return_value=[]),
            patch("src.services.market_overview_service._now_iso", return_value=updated_at),
        ):
            ticker_fetch.return_value = [
                {
                    "symbol": "BTCUSDT",
                    "lastPrice": "71000",
                    "priceChangePercent": "1.5",
                    "quoteVolume": "123456789",
                    "highPrice": "71500",
                    "lowPrice": "69500",
                }
            ]

            payload = service._fetch_crypto_market_snapshot()

        ticker_fetch.assert_called_once_with(["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"])
        self.assertEqual(payload["source"], "binance")
        self.assertFalse(payload["fallback_used"])
        self.assertEqual(payload["last_update"], updated_at)
        self.assertEqual(payload["items"][0]["symbol"], "BTC")
        self.assertEqual(payload["items"][0]["label"], "Bitcoin")
        self.assertEqual(payload["items"][0]["price"], 71000.0)
        self.assertEqual(payload["items"][0]["change"], 1.5)
        self.assertEqual(payload["items"][0]["trend"], [70000.0, 71000.0])
        self.assertEqual(payload["items"][0]["hover_details"][0], "24H +1.50%")

    def test_fetch_crypto_market_snapshot_preserves_missing_price_as_unavailable(self) -> None:
        service = MarketOverviewService()
        updated_at = datetime(2026, 4, 30, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")

        with (
            patch("src.services.market_overview_service.fetch_binance_ticker_snapshot") as ticker_fetch,
            patch.object(service, "_fetch_binance_kline_histories", return_value={}),
            patch.object(service, "_fetch_binance_funding_items", return_value=[]),
            patch("src.services.market_overview_service._now_iso", return_value=updated_at),
        ):
            ticker_fetch.return_value = [
                {
                    "symbol": "BTCUSDT",
                    "lastPrice": None,
                    "priceChangePercent": None,
                    "quoteVolume": None,
                    "highPrice": None,
                    "lowPrice": None,
                }
            ]

            payload = service._fetch_crypto_market_snapshot()

        item = payload["items"][0]
        self.assertEqual(item["symbol"], "BTC")
        self.assertIsNone(item["price"])
        self.assertIsNone(item["value"])
        self.assertIsNone(item["change"])
        self.assertEqual(item["trend"], [])
        self.assertTrue(item["isUnavailable"])
        self.assertEqual(item["freshness"], "unavailable")
        self.assertEqual(item["unavailableReason"], "missing_last_price")

    def test_get_crypto_service_owns_public_payload_after_binance_transport_calls(self) -> None:
        service = MarketOverviewService()
        ticker_rows = [
            {"symbol": "BTCUSDT", "lastPrice": "70000", "priceChangePercent": "1.2", "quoteVolume": "2200000000", "highPrice": "71000", "lowPrice": "69000"},
            {"symbol": "ETHUSDT", "lastPrice": "3500", "priceChangePercent": "0.4", "quoteVolume": "1200000000", "highPrice": "3550", "lowPrice": "3400"},
            {"symbol": "SOLUSDT", "lastPrice": "155", "priceChangePercent": "2.4", "quoteVolume": "700000000", "highPrice": "160", "lowPrice": "150"},
            {"symbol": "BNBUSDT", "lastPrice": "610", "priceChangePercent": "-0.2", "quoteVolume": "320000000", "highPrice": "618", "lowPrice": "604"},
        ]
        funding_rows = {
            "BTCUSDT": {"lastFundingRate": "0.00012"},
            "ETHUSDT": {"lastFundingRate": "0.00008"},
            "SOLUSDT": {"lastFundingRate": "-0.00005"},
            "BNBUSDT": {"lastFundingRate": "0.00003"},
        }

        def history_rows(symbol: str) -> list[list[str]]:
            close_map = {
                "BTCUSDT": ["68000", "69000", "70000"],
                "ETHUSDT": ["3300", "3400", "3500"],
                "SOLUSDT": ["145", "150", "155"],
                "BNBUSDT": ["600", "605", "610"],
            }
            return [["0", "0", "0", "0", close, "0"] for close in close_map[symbol]]

        with (
            patch("src.services.market_overview_service.fetch_binance_ticker_snapshot", return_value=ticker_rows) as mock_ticker,
            patch("src.services.market_overview_service.fetch_binance_kline_history_rows", side_effect=history_rows) as mock_klines,
            patch("src.services.market_overview_service.fetch_binance_funding_row", side_effect=lambda symbol: funding_rows[symbol]) as mock_funding,
        ):
            payload = service.get_crypto()

        mock_ticker.assert_called_once_with(["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"])
        self.assertEqual(mock_klines.call_count, 4)
        self.assertEqual(mock_funding.call_count, 4)
        self.assertEqual(payload["source"], "binance")
        self.assertEqual(payload["sourceLabel"], "Binance")
        self.assertFalse(payload["fallback_used"])
        self.assertFalse(payload["isFallback"])
        self.assertEqual(payload["providerHealth"]["provider"], "binance")
        self.assertEqual(payload["providerHealth"]["status"], "partial")
        btc_item = next(item for item in payload["items"] if item["symbol"] == "BTC")
        self.assertEqual(btc_item["source"], "binance")
        self.assertEqual(btc_item["sourceLabel"], "Binance")
        self.assertFalse(btc_item["isFallback"])
        self.assertTrue(btc_item["trend"])

    def test_get_crypto_attaches_coinbase_sidecar_without_adding_coinbase_items(self) -> None:
        service = MarketOverviewService()
        updated_at = datetime.now(CN_TZ).isoformat(timespec="seconds")
        snapshot = {
            "items": [
                {
                    "symbol": "BTC",
                    "label": "Bitcoin",
                    "price": 71000.0,
                    "value": 71000.0,
                    "change": 1.5,
                    "changePercent": 1.5,
                    "trend": [70000.0, 71000.0],
                    "source": "binance",
                    "last_update": updated_at,
                }
            ],
            "last_update": updated_at,
            "updatedAt": updated_at,
            "asOf": updated_at,
            "fallback_used": False,
            "fallbackUsed": False,
            "source": "binance",
        }
        coinbase_records = [
            record.to_dict()
            for record in parse_ticker_payload(
                json.loads(COINBASE_FIXTURE_PATH.read_text(encoding="utf-8"))
            ).records
        ]

        with (
            patch.object(service, "_fetch_crypto_market_snapshot", return_value=snapshot),
            patch.object(service, "_coinbase_venue_observation_records", return_value=coinbase_records),
        ):
            payload = service.get_crypto()

        self.assertEqual([item["symbol"] for item in payload["items"]], ["BTC"])
        self.assertNotIn("BTC-USD", {item["symbol"] for item in payload["items"]})
        sidecar = payload["providerHealth"]["venueObservations"]["coinbase"]
        self.assertEqual(sidecar["providerName"], "Coinbase Public")
        self.assertEqual(sidecar["providerId"], "coinbase_public")
        self.assertEqual(sidecar["source"], "coinbase_public")
        self.assertEqual(sidecar["venue"], "coinbase")
        self.assertEqual(sidecar["sourceTier"], "exchange_public")
        self.assertEqual(sidecar["trustLevel"], "usable_with_caution")
        self.assertTrue(sidecar["observationOnly"])
        self.assertFalse(sidecar["scoreContributionAllowed"])
        self.assertEqual(sidecar["productId"], "BTC-USD")
        self.assertEqual(sidecar["symbol"], "BTC-USD")
        self.assertEqual(sidecar["baseCurrency"], "BTC")
        self.assertEqual(sidecar["quoteCurrency"], "USD")
        self.assertEqual(sidecar["asOf"], "2026-05-19T10:15:30.123456Z")
        self.assertEqual(sidecar["updatedAt"], "2026-05-19T10:15:30.123456Z")
        self.assertEqual(sidecar["sourceRef"], "tests/fixtures/coinbase_public/ticker_sample.json")
        self.assertIn(sidecar["freshness"], {"delayed", "cached", "stale"})
        self.assertEqual(len(sidecar["records"]), 1)
        self.assertTrue(sidecar["records"][0]["observationOnly"])
        self.assertFalse(sidecar["records"][0]["scoreContributionAllowed"])

    def test_get_crypto_rejects_coinbase_sidecar_that_claims_scoring_or_live_authority(self) -> None:
        service = MarketOverviewService()
        updated_at = datetime.now(CN_TZ).isoformat(timespec="seconds")
        snapshot = {
            "items": [
                {
                    "symbol": "BTC",
                    "label": "Bitcoin",
                    "price": 71000.0,
                    "value": 71000.0,
                    "change": 1.5,
                    "changePercent": 1.5,
                    "trend": [70000.0, 71000.0],
                    "source": "binance",
                    "last_update": updated_at,
                }
            ],
            "last_update": updated_at,
            "updatedAt": updated_at,
            "asOf": updated_at,
            "fallback_used": False,
            "fallbackUsed": False,
            "source": "binance",
        }
        coinbase_records = [
            {
                "providerName": "Coinbase Public",
                "providerId": "coinbase_public",
                "source": "coinbase_public",
                "venue": "coinbase",
                "sourceTier": "exchange_public",
                "trustLevel": "usable_with_caution",
                "observationOnly": False,
                "scoreContributionAllowed": True,
                "productId": "BTC-USD",
                "symbol": "BTC-USD",
                "baseCurrency": "BTC",
                "quoteCurrency": "USD",
                "asOf": "2026-05-20T10:15:30.123456Z",
                "updatedAt": "2026-05-20T10:15:30.123456Z",
                "freshness": "live",
                "sourceRef": "tests/fixtures/coinbase_public/ticker_sample.json",
            }
        ]

        with (
            patch.object(service, "_fetch_crypto_market_snapshot", return_value=snapshot),
            patch.object(service, "_coinbase_venue_observation_records", return_value=coinbase_records),
        ):
            payload = service.get_crypto()

        sidecar = payload["providerHealth"]["venueObservations"]["coinbase"]
        self.assertEqual([item["symbol"] for item in payload["items"]], ["BTC"])
        self.assertEqual(sidecar["providerId"], "coinbase_public")
        self.assertEqual(sidecar["source"], "coinbase_public")
        self.assertEqual(sidecar["freshness"], "unavailable")
        self.assertTrue(sidecar["observationOnly"])
        self.assertFalse(sidecar["scoreContributionAllowed"])
        self.assertEqual(sidecar["degradationReason"], "market_overview_observation_authority_claim_rejected")
        self.assertIn("scoring_authority_claim", sidecar["routeRejectedReasonCodes"])
        self.assertIn("live_authority_claim", sidecar["routeRejectedReasonCodes"])
        self.assertEqual(sidecar["records"], [])

    def test_get_crypto_marks_coinbase_sidecar_unavailable_when_no_observation_exists(self) -> None:
        service = MarketOverviewService()
        updated_at = datetime.now(CN_TZ).isoformat(timespec="seconds")
        snapshot = {
            "items": [
                {
                    "symbol": "BTC",
                    "label": "Bitcoin",
                    "price": 71000.0,
                    "value": 71000.0,
                    "change": 1.5,
                    "changePercent": 1.5,
                    "trend": [70000.0, 71000.0],
                    "source": "binance",
                    "last_update": updated_at,
                }
            ],
            "last_update": updated_at,
            "updatedAt": updated_at,
            "asOf": updated_at,
            "fallback_used": False,
            "fallbackUsed": False,
            "source": "binance",
        }

        with patch.object(service, "_fetch_crypto_market_snapshot", return_value=snapshot):
            payload = service.get_crypto()

        sidecar = payload["providerHealth"]["venueObservations"]["coinbase"]
        self.assertEqual(sidecar["providerId"], "coinbase_public")
        self.assertEqual(sidecar["source"], "coinbase_public")
        self.assertEqual(sidecar["venue"], "coinbase")
        self.assertEqual(sidecar["sourceTier"], "exchange_public")
        self.assertEqual(sidecar["trustLevel"], "usable_with_caution")
        self.assertEqual(sidecar["freshness"], "unavailable")
        self.assertTrue(sidecar["observationOnly"])
        self.assertFalse(sidecar["scoreContributionAllowed"])
        self.assertIsNone(sidecar["productId"])
        self.assertIsNone(sidecar["symbol"])
        self.assertIsNone(sidecar["baseCurrency"])
        self.assertIsNone(sidecar["quoteCurrency"])
        self.assertIsNone(sidecar["asOf"])
        self.assertEqual(sidecar["updatedAt"], updated_at)
        self.assertEqual(sidecar["degradationReason"], "observation_unavailable")
        self.assertEqual(sidecar["sourceRef"], "coinbase_public:fixture_only")
        self.assertEqual(sidecar["records"], [])


if __name__ == "__main__":
    unittest.main()
