# -*- coding: utf-8 -*-
"""Tests for Alpaca market-data fetcher."""

from __future__ import annotations

import json
import os
import socket
import unittest
from unittest.mock import Mock, patch

import requests

from data_provider.alpaca_fetcher import AlpacaFetcher
from data_provider.realtime_types import RealtimeSource
from src.services.uat_provider_isolation import UatProviderIsolationError


class _MockResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class AlpacaFetcherTestCase(unittest.TestCase):
    def test_uat_no_live_providers_blocks_direct_snapshot_before_http(self) -> None:
        session = Mock()
        with patch("data_provider.alpaca_fetcher.requests.Session", return_value=session):
            fetcher = AlpacaFetcher(
                api_key_id="alpaca-id",
                secret_key="alpaca-secret",
            )

        with patch.dict(os.environ, {"WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS": "true"}, clear=False):
            with self.assertRaises(UatProviderIsolationError):
                fetcher.get_realtime_quote("AAPL")

        session.get.assert_not_called()
        self.assertEqual(fetcher.transport_identity, "default_live_transport")

    def test_get_realtime_quote_builds_quote_from_snapshot(self) -> None:
        session = Mock()
        session.get.return_value = _MockResponse(
            {
                "latestTrade": {"p": 214.55, "t": "2026-04-14T13:30:00Z"},
                "latestQuote": {"ap": 214.6, "bp": 214.5, "t": "2026-04-14T13:30:00Z"},
                "dailyBar": {"o": 210.0, "h": 215.2, "l": 209.8, "c": 214.0, "v": 123456, "vw": 213.2},
                "prevDailyBar": {"c": 208.1},
            }
        )
        fetcher = AlpacaFetcher(
            api_key_id="alpaca-id",
            secret_key="alpaca-secret",
            data_feed="sip",
            session=session,
        )

        with patch.object(
            socket.socket,
            "connect",
            side_effect=AssertionError("injected session must not open a socket"),
        ), patch(
            "data_provider.alpaca_fetcher.requests.Session",
            side_effect=AssertionError("injected session must not create a default session"),
        ):
            quote = fetcher.get_realtime_quote("AAPL")

        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertEqual(quote.source, RealtimeSource.ALPACA)
        self.assertEqual(quote.code, "AAPL")
        self.assertAlmostEqual(float(quote.price or 0.0), 214.55, places=2)
        self.assertAlmostEqual(float(quote.pre_close or 0.0), 208.1, places=2)
        self.assertEqual(quote.volume, 123456)
        self.assertEqual(fetcher.transport_identity, "injected_test_transport")
        session.get.assert_called_once_with(
            "https://data.alpaca.markets/v2/stocks/AAPL/snapshot",
            params={"feed": "sip"},
            headers={
                "APCA-API-KEY-ID": "alpaca-id",
                "APCA-API-SECRET-KEY": "alpaca-secret",
                "Accept": "application/json",
            },
            timeout=15,
        )

    def test_get_daily_data_requests_adjusted_bars(self) -> None:
        session = Mock()
        session.get.return_value = _MockResponse(
            {
                "bars": [
                    {"t": "2026-04-11T00:00:00Z", "o": 100.0, "h": 101.0, "l": 99.5, "c": 100.4, "v": 1000, "vw": 100.2},
                    {"t": "2026-04-14T00:00:00Z", "o": 100.5, "h": 102.0, "l": 100.0, "c": 101.6, "v": 1200, "vw": 101.1},
                ]
            }
        )
        fetcher = AlpacaFetcher(
            api_key_id="alpaca-id",
            secret_key="alpaca-secret",
            session=session,
        )

        frame, source = fetcher.get_daily_data("AAPL", start_date="2026-04-10", end_date="2026-04-15", days=10)

        self.assertEqual(source, "AlpacaFetcher")
        self.assertEqual(list(frame["code"].unique()), ["AAPL"])
        self.assertIn("pct_chg", frame.columns)
        session.get.assert_called_once()
        args, kwargs = session.get.call_args
        self.assertEqual(args[0], "https://data.alpaca.markets/v2/stocks/AAPL/bars")
        self.assertEqual(kwargs["params"]["timeframe"], "1Day")
        self.assertEqual(kwargs["params"]["adjustment"], "all")
        self.assertEqual(kwargs["params"]["feed"], "iex")

    def test_proxy_diagnostics_report_env_presence_without_values(self) -> None:
        with patch.dict(
            os.environ,
            {
                "HTTP_PROXY": "http://proxy-secret@127.0.0.1:7890",
                "HTTPS_PROXY": "http://proxy-secret@127.0.0.1:7890",
                "ALL_PROXY": "socks5://proxy-secret@127.0.0.1:7890",
            },
            clear=False,
        ):
            fetcher = AlpacaFetcher(api_key_id="alpaca-id", secret_key="alpaca-secret")

            diagnostics = fetcher.proxy_diagnostics()

        self.assertTrue(diagnostics["sessionTrustEnv"])
        self.assertTrue(diagnostics["httpProxyConfigured"])
        self.assertTrue(diagnostics["httpsProxyConfigured"])
        self.assertTrue(diagnostics["allProxyConfigured"])
        self.assertTrue(diagnostics["alpacaHttpsProxyEligible"])
        dumped = json.dumps(diagnostics, ensure_ascii=False)
        self.assertNotIn("proxy-secret", dumped)
        self.assertNotIn("127.0.0.1:7890", dumped)

    def test_endpoint_reachability_is_sanitized_and_payload_free(self) -> None:
        session = Mock()
        session.head.return_value = _MockResponse({}, status_code=404)
        fetcher = AlpacaFetcher(
            api_key_id="alpaca-id",
            secret_key="alpaca-secret",
            session=session,
        )

        diagnostics = fetcher.endpoint_reachability(timeout=3.5)

        self.assertEqual(
            diagnostics,
            {
                "attempted": True,
                "status": "reachable",
                "failureClass": None,
                "httpStatusClass": "4xx",
            },
        )
        session.head.assert_called_once_with(
            "https://data.alpaca.markets",
            headers={"Accept": "application/json"},
            timeout=3.5,
            allow_redirects=False,
        )
        dumped = json.dumps(diagnostics, ensure_ascii=False)
        self.assertNotIn("alpaca-secret", dumped)
        self.assertNotIn("alpaca-id", dumped)

    def test_endpoint_reachability_classifies_proxy_timeout_without_message_leak(self) -> None:
        session = Mock()
        session.head.side_effect = requests.exceptions.ProxyError("proxy-secret SHOULD_NOT_LEAK")
        fetcher = AlpacaFetcher(
            api_key_id="alpaca-id",
            secret_key="alpaca-secret",
            session=session,
        )

        diagnostics = fetcher.endpoint_reachability(timeout=4.0)

        self.assertEqual(diagnostics["attempted"], True)
        self.assertEqual(diagnostics["status"], "unreachable")
        self.assertEqual(diagnostics["failureClass"], "proxy_unreachable")
        self.assertEqual(diagnostics["httpStatusClass"], None)
        dumped = json.dumps(diagnostics, ensure_ascii=False)
        self.assertNotIn("proxy-secret", dumped)
        self.assertNotIn("SHOULD_NOT_LEAK", dumped)
        self.assertNotIn("alpaca-secret", dumped)


if __name__ == "__main__":
    unittest.main()
