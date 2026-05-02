# -*- coding: utf-8 -*-
"""Tests for public FX rate refresh service."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import requests

from src.services.fx_rate_service import FxRateService


class FxRateServiceTestCase(unittest.TestCase):
    def test_fetches_rate_from_frankfurter_provider(self) -> None:
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "amount": 1.0,
            "base": "USD",
            "quote": "CNY",
            "rate": 7.21,
        }

        with patch("src.services.fx_rate_service.requests.get", return_value=response) as mock_get:
            service = FxRateService()
            result = service.fetch_rate("usd", "cny", force_refresh=True)

        self.assertEqual(result["base_currency"], "USD")
        self.assertEqual(result["quote_currency"], "CNY")
        self.assertAlmostEqual(result["rate"], 7.21, places=6)
        self.assertEqual(result["provider"], "frankfurter")
        self.assertFalse(result["cache_hit"])
        self.assertFalse(result["stale"])
        mock_get.assert_called_once()

    def test_returns_cache_hit_on_second_request_within_ttl(self) -> None:
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"rate": 7.21}

        with patch("src.services.fx_rate_service.requests.get", return_value=response):
            service = FxRateService(ttl_seconds=600)
            first = service.fetch_rate("USD", "CNY", force_refresh=True)
            second = service.fetch_rate("USD", "CNY")

        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertFalse(second["stale"])
        self.assertAlmostEqual(second["rate"], 7.21, places=6)

    def test_returns_stale_cache_when_provider_fails(self) -> None:
        service = FxRateService(ttl_seconds=1)
        stale_time = datetime.utcnow() - timedelta(minutes=15)
        service._cache[("USD", "CNY")] = {
            "base_currency": "USD",
            "quote_currency": "CNY",
            "rate": 7.1,
            "provider": "frankfurter",
            "fetched_at": stale_time.isoformat(),
            "cache_hit": False,
            "stale": False,
            "_cached_at": stale_time,
        }

        with patch(
            "src.services.fx_rate_service.requests.get",
            side_effect=requests.exceptions.ConnectionError("network down"),
        ):
            result = service.fetch_rate("USD", "CNY", force_refresh=True)

        self.assertTrue(result["cache_hit"])
        self.assertTrue(result["stale"])
        self.assertEqual(result["error"], "network down")
        self.assertAlmostEqual(result["rate"], 7.1, places=6)

    def test_timeout_is_three_seconds(self) -> None:
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"rate": 7.21}

        with patch("src.services.fx_rate_service.requests.get", return_value=response) as mock_get:
            FxRateService().fetch_rate("USD", "CNY", force_refresh=True)

        self.assertEqual(mock_get.call_args.kwargs["timeout"], 3)


if __name__ == "__main__":
    unittest.main()
