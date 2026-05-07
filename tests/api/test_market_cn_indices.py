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
from src.config import Config
from src.services.market_overview_service import MarketOverviewService, get_freshness_status
from src.storage import DatabaseManager


CN_TZ = timezone(timedelta(hours=8))


def _fresh_sina_as_of() -> str:
    return datetime.now(CN_TZ).isoformat(timespec="seconds")


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class MarketCnIndicesApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        MarketOverviewService._market_cache.clear()
        MarketOverviewService._market_data_cache.clear()

    def test_cn_indices_endpoint_returns_stable_contract(self) -> None:
        payload = market.get_cn_indices()

        self.assertTrue(payload["source"])
        self.assertTrue(payload["sourceLabel"])
        self.assertTrue(payload["updatedAt"])
        self.assertIn(payload["freshness"], {"live", "delayed", "cached", "stale", "fallback", "mock", "error"})
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
        self.assertFalse(payload["isFallback"])
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
