# -*- coding: utf-8 -*-
"""Tests for Alpaca routing inside DataFetcherManager realtime quotes."""

from __future__ import annotations

import unittest
from os import environ
from ssl import SSLEOFError
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from data_provider.base import DataFetchError, DataFetcherManager
from data_provider.provider_credentials import ProviderCredentialBundle
from data_provider.realtime_types import RealtimeSource, UnifiedRealtimeQuote


class _YfinanceStub:
    name = "YfinanceFetcher"
    priority = 4

    def __init__(self, quote: UnifiedRealtimeQuote | None, daily_result=None) -> None:
        self.quote = quote
        self.daily_result = daily_result
        self.calls: list[str] = []
        self.daily_calls: list[str] = []

    def get_realtime_quote(self, stock_code: str):
        self.calls.append(stock_code)
        return self.quote

    def get_daily_data(self, stock_code: str, start_date=None, end_date=None, days: int = 30):
        _ = (start_date, end_date, days)
        self.daily_calls.append(stock_code)
        return self.daily_result


class _AlpacaStub:
    def __init__(self, quote: UnifiedRealtimeQuote | None, daily_result=None, daily_error: Exception | None = None) -> None:
        self.quote = quote
        self.daily_result = daily_result
        self.daily_error = daily_error
        self.calls: list[str] = []
        self.daily_calls: list[str] = []

    def get_realtime_quote(self, stock_code: str):
        self.calls.append(stock_code)
        return self.quote

    def get_daily_data(self, stock_code: str, start_date=None, end_date=None, days: int = 30):
        _ = (start_date, end_date, days)
        self.daily_calls.append(stock_code)
        if self.daily_error is not None:
            raise self.daily_error
        return self.daily_result


class DataFetcherManagerAlpacaTestCase(unittest.TestCase):
    def test_uat_no_live_providers_blocks_us_daily_direct_route_before_fetchers(self) -> None:
        yfinance = _YfinanceStub(
            UnifiedRealtimeQuote(code="MSFT", source=RealtimeSource.YFINANCE, price=410.0),
            daily_result=(pd.DataFrame([{"date": "2026-04-14", "close": 410.0}]), "YfinanceFetcher"),
        )
        manager = DataFetcherManager(fetchers=[yfinance])
        alpaca = _AlpacaStub(
            UnifiedRealtimeQuote(code="MSFT", source=RealtimeSource.ALPACA, price=411.0),
            daily_result=(pd.DataFrame([{"date": "2026-04-14", "close": 411.0}]), "AlpacaFetcher"),
        )

        with patch.dict(environ, {"WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS": "true"}, clear=False), \
             patch("data_provider.base.get_provider_credentials") as mock_credentials, \
             patch.object(manager, "_get_alpaca_fetcher", return_value=alpaca):
            mock_credentials.return_value = ProviderCredentialBundle(
                provider="alpaca",
                auth_mode="key_secret",
                key_id="alpaca-id",
                secret_key="alpaca-secret",
            )
            with self.assertRaises(DataFetchError):
                manager.get_daily_data("MSFT", days=20)

        self.assertEqual(alpaca.daily_calls, [])
        self.assertEqual(yfinance.daily_calls, [])
        trace = manager.get_last_daily_history_trace()
        self.assertTrue(
            any(
                item["provider"] == "datafetchermanager"
                and item["status"] == "blocked"
                and item["reason"] == "uat_no_live_providers"
                for item in trace
            )
        )

    def test_uat_no_live_providers_blocks_us_realtime_direct_route_before_fetchers(self) -> None:
        yfinance = _YfinanceStub(
            UnifiedRealtimeQuote(code="MSFT", source=RealtimeSource.YFINANCE, price=410.0)
        )
        manager = DataFetcherManager(fetchers=[yfinance])
        alpaca = _AlpacaStub(
            UnifiedRealtimeQuote(code="MSFT", source=RealtimeSource.ALPACA, price=411.0)
        )

        with patch.dict(environ, {"WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS": "true"}, clear=False), \
             patch("data_provider.base.get_provider_credentials") as mock_credentials, \
             patch.object(manager, "_get_alpaca_fetcher", return_value=alpaca):
            mock_credentials.return_value = ProviderCredentialBundle(
                provider="alpaca",
                auth_mode="key_secret",
                key_id="alpaca-id",
                secret_key="alpaca-secret",
            )
            quote = manager.get_realtime_quote("MSFT")

        self.assertIsNone(quote)
        self.assertEqual(alpaca.calls, [])
        self.assertEqual(yfinance.calls, [])
        trace = manager.get_last_realtime_quote_trace()
        self.assertTrue(
            any(
                item["provider"] == "datafetchermanager"
                and item["status"] == "blocked"
                and item["reason"] == "uat_no_live_providers"
                for item in trace
            )
        )

    def test_us_quote_prefers_alpaca_when_configured(self) -> None:
        yfinance = _YfinanceStub(
            UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.YFINANCE, price=210.0)
        )
        manager = DataFetcherManager(fetchers=[yfinance])
        alpaca = _AlpacaStub(
            UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.ALPACA, price=214.0)
        )

        with patch("data_provider.base.get_provider_credentials") as mock_credentials:
            mock_credentials.return_value = ProviderCredentialBundle(
                provider="alpaca",
                auth_mode="key_secret",
                key_id="alpaca-id",
                secret_key="alpaca-secret",
                extras={"data_feed": "iex"},
            )
            with patch.object(manager, "_get_alpaca_fetcher", return_value=alpaca):
                quote = manager.get_realtime_quote("AAPL")

        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertEqual(quote.source, RealtimeSource.ALPACA)
        self.assertEqual(alpaca.calls, ["AAPL"])
        self.assertEqual(yfinance.calls, [])
        trace = manager.get_last_realtime_quote_trace()
        self.assertEqual(
            [(item["provider"], item["action"]) for item in trace],
            [("market_route", "selected"), ("alpaca", "attempting"), ("alpaca", "succeeded")],
        )

    def test_us_quote_falls_back_to_yfinance_when_alpaca_returns_none(self) -> None:
        yfinance = _YfinanceStub(
            UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.YFINANCE, price=210.0)
        )
        manager = DataFetcherManager(fetchers=[yfinance])
        alpaca = _AlpacaStub(None)

        with patch("data_provider.base.get_provider_credentials") as mock_credentials:
            mock_credentials.return_value = ProviderCredentialBundle(
                provider="alpaca",
                auth_mode="key_secret",
                key_id="alpaca-id",
                secret_key="alpaca-secret",
                extras={"data_feed": "iex"},
            )
            with patch.object(manager, "_get_alpaca_fetcher", return_value=alpaca):
                quote = manager.get_realtime_quote("AAPL")

        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertEqual(quote.source, RealtimeSource.YFINANCE)
        self.assertEqual(alpaca.calls, ["AAPL"])
        self.assertEqual(yfinance.calls, ["AAPL"])
        trace = manager.get_last_realtime_quote_trace()
        self.assertEqual(
            [(item["provider"], item["action"]) for item in trace],
            [
                ("market_route", "selected"),
                ("alpaca", "attempting"),
                ("alpaca", "failed"),
                ("yfinance", "attempting"),
                ("yfinance", "succeeded"),
            ],
        )

    def test_us_quote_marks_alpaca_as_skipped_when_not_configured(self) -> None:
        yfinance = _YfinanceStub(
            UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.YFINANCE, price=210.0)
        )
        manager = DataFetcherManager(fetchers=[yfinance])

        with patch("data_provider.base.get_provider_credentials") as mock_credentials:
            mock_credentials.return_value = ProviderCredentialBundle(
                provider="alpaca",
                auth_mode="key_secret",
                extras={"data_feed": "iex"},
            )
            quote = manager.get_realtime_quote("AAPL")

        self.assertIsNotNone(quote)
        trace = manager.get_last_realtime_quote_trace()
        self.assertTrue(any(item["provider"] == "alpaca" and item["action"] == "skipped" for item in trace))

    def test_us_quote_skips_each_partial_alpaca_bundle_and_preserves_fallback_trace(self) -> None:
        partial_bundles = (
            ProviderCredentialBundle(
                provider="alpaca",
                auth_mode="key_secret",
                key_id="alpaca-key-sentinel",
                extras={"data_feed": "iex"},
            ),
            ProviderCredentialBundle(
                provider="alpaca",
                auth_mode="key_secret",
                secret_key="alpaca-secret-sentinel",
                extras={"data_feed": "iex"},
            ),
        )

        for credentials in partial_bundles:
            with self.subTest(missing_fields=credentials.missing_fields):
                yfinance = _YfinanceStub(
                    UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.YFINANCE, price=210.0)
                )
                manager = DataFetcherManager(fetchers=[yfinance])
                with patch(
                    "data_provider.base.get_provider_credentials",
                    return_value=credentials,
                ), patch.object(
                    manager,
                    "_get_alpaca_fetcher",
                    side_effect=AssertionError("partial Alpaca credentials must not construct a provider"),
                ):
                    quote = manager.get_realtime_quote("AAPL")

                self.assertIsNotNone(quote)
                self.assertEqual(yfinance.calls, ["AAPL"])
                trace = manager.get_last_realtime_quote_trace()
                self.assertEqual(
                    [(item["provider"], item["action"], item["reason"]) for item in trace],
                    [
                        ("market_route", "selected", None),
                        ("alpaca", "skipped", "incomplete_credentials"),
                        ("yfinance", "attempting", None),
                        ("yfinance", "succeeded", None),
                    ],
                )

    def test_us_daily_history_prefers_alpaca_when_configured(self) -> None:
        daily_frame = pd.DataFrame(
            [
                {"date": "2026-04-11", "close": 100.0},
                {"date": "2026-04-14", "close": 101.2},
            ]
        )
        yfinance = _YfinanceStub(
            UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.YFINANCE, price=210.0),
            daily_result=(daily_frame, "YfinanceFetcher"),
        )
        manager = DataFetcherManager(fetchers=[yfinance])
        alpaca = _AlpacaStub(
            UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.ALPACA, price=214.0),
            daily_result=(daily_frame, "AlpacaFetcher"),
        )

        with patch("data_provider.base.get_provider_credentials") as mock_credentials:
            mock_credentials.return_value = ProviderCredentialBundle(
                provider="alpaca",
                auth_mode="key_secret",
                key_id="alpaca-id",
                secret_key="alpaca-secret",
                extras={"data_feed": "iex"},
            )
            with patch.object(manager, "_get_alpaca_fetcher", return_value=alpaca):
                frame, source = manager.get_daily_data("AAPL", days=20)

        self.assertIs(frame, daily_frame)
        self.assertEqual(source, "AlpacaFetcher")
        self.assertEqual(alpaca.daily_calls, ["AAPL"])
        self.assertEqual(yfinance.daily_calls, [])

    def test_us_daily_history_falls_back_to_yfinance_when_alpaca_fails(self) -> None:
        daily_frame = pd.DataFrame(
            [
                {"date": "2026-04-10", "close": 98.5},
                {"date": "2026-04-11", "close": 100.0},
                {"date": "2026-04-14", "close": 101.2},
            ]
        )
        yfinance = _YfinanceStub(
            UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.YFINANCE, price=210.0),
            daily_result=(daily_frame, "YfinanceFetcher"),
        )
        manager = DataFetcherManager(fetchers=[yfinance])
        alpaca = _AlpacaStub(
            UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.ALPACA, price=214.0),
            daily_error=RuntimeError("alpaca timeout"),
        )

        with patch("data_provider.base.get_provider_credentials") as mock_credentials:
            mock_credentials.return_value = ProviderCredentialBundle(
                provider="alpaca",
                auth_mode="key_secret",
                key_id="alpaca-id",
                secret_key="alpaca-secret",
                extras={"data_feed": "iex"},
            )
            with patch.object(manager, "_get_alpaca_fetcher", return_value=alpaca):
                frame, source = manager.get_daily_data("AAPL", days=20)

        self.assertIs(frame, daily_frame)
        self.assertEqual(source, "YfinanceFetcher")
        self.assertEqual(alpaca.daily_calls, ["AAPL"])
        self.assertEqual(yfinance.daily_calls, ["AAPL"])

    def test_us_daily_history_trace_records_alpaca_ssl_and_yfinance_empty(self) -> None:
        yfinance = _YfinanceStub(
            UnifiedRealtimeQuote(code="ORCL", source=RealtimeSource.YFINANCE, price=130.0),
            daily_result=(pd.DataFrame(), "YfinanceFetcher"),
        )
        manager = DataFetcherManager(fetchers=[yfinance])
        alpaca = _AlpacaStub(
            UnifiedRealtimeQuote(code="ORCL", source=RealtimeSource.ALPACA, price=131.0),
            daily_error=SSLEOFError("EOF occurred in violation of protocol"),
        )

        with patch("data_provider.base.get_provider_credentials") as mock_credentials:
            mock_credentials.return_value = ProviderCredentialBundle(
                provider="alpaca",
                auth_mode="key_secret",
                key_id="alpaca-id",
                secret_key="alpaca-secret",
                extras={"data_feed": "iex"},
            )
            with patch.object(manager, "_get_alpaca_fetcher", return_value=alpaca):
                with self.assertRaises(DataFetchError) as raised:
                    manager.get_daily_data("ORCL", days=365)

        message = str(raised.exception)
        self.assertIn("SSLEOFError", message)
        self.assertIn("YfinanceFetcher", message)
        self.assertIn("provider_returned_empty_history", message)
        trace = manager.get_last_daily_history_trace()
        self.assertTrue(any(item["provider"] == "AlpacaFetcher" and item["action"] == "failed" for item in trace))
        self.assertTrue(
            any(
                item["provider"] == "YfinanceFetcher"
                and item["action"] == "failed"
                and item["outcome"] == "empty_result"
                for item in trace
            )
        )


if __name__ == "__main__":
    unittest.main()
