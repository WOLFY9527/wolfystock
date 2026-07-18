# -*- coding: utf-8 -*-
"""Tests for HK routing inside DataFetcherManager realtime quotes."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from data_provider.base import DataFetcherManager
from data_provider.realtime_types import RealtimeSource, UnifiedRealtimeQuote
from src.config import Config


class _AkshareHkStub:
    name = "AkshareFetcher"
    priority = 2

    def __init__(self, quote: UnifiedRealtimeQuote | None) -> None:
        self.quote = quote
        self.calls: list[tuple[str, str | None]] = []

    def get_realtime_quote(self, stock_code: str, source: str | None = None):
        self.calls.append((stock_code, source))
        return self.quote


class _TwelveDataStub:
    def __init__(self, quote: UnifiedRealtimeQuote | None) -> None:
        self.quote = quote
        self.calls: list[str] = []

    def get_realtime_quote(self, stock_code: str):
        self.calls.append(stock_code)
        return self.quote


class DataFetcherManagerTwelveDataTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        Config.reset_instance()

    def test_hk_quote_prefers_twelve_data_when_available(self) -> None:
        akshare = _AkshareHkStub(
            UnifiedRealtimeQuote(code="HK00700", source=RealtimeSource.AKSHARE_EM, price=500.0)
        )
        twelve_data = _TwelveDataStub(
            UnifiedRealtimeQuote(code="HK00700", source=RealtimeSource.TWELVE_DATA, price=503.5)
        )
        manager = DataFetcherManager(
            fetchers=[akshare],
            injected_provider_fetchers={"twelve_data": twelve_data},
        )

        with patch(
            "data_provider.base.get_provider_credentials",
            side_effect=AssertionError("injected Twelve Data transport must not read credentials"),
        ):
            quote = manager.get_realtime_quote("HK00700")

        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertEqual(quote.source, RealtimeSource.TWELVE_DATA)
        self.assertEqual(twelve_data.calls, ["HK00700"])
        self.assertEqual(akshare.calls, [])
        self.assertEqual(
            [(item["provider"], item["action"]) for item in manager.get_last_realtime_quote_trace()],
            [
                ("market_route", "selected"),
                ("twelve_data", "attempting"),
                ("twelve_data", "succeeded"),
            ],
        )

    def test_hk_quote_falls_back_to_akshare_when_twelve_data_returns_none(self) -> None:
        akshare = _AkshareHkStub(
            UnifiedRealtimeQuote(code="HK00700", source=RealtimeSource.AKSHARE_EM, price=500.0)
        )
        twelve_data = _TwelveDataStub(None)
        manager = DataFetcherManager(
            fetchers=[akshare],
            injected_provider_fetchers={"twelve_data": twelve_data},
        )

        with patch(
            "data_provider.base.get_provider_credentials",
            side_effect=AssertionError("injected Twelve Data transport must not read credentials"),
        ):
            quote = manager.get_realtime_quote("HK00700")

        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertEqual(quote.source, RealtimeSource.AKSHARE_EM)
        self.assertEqual(twelve_data.calls, ["HK00700"])
        self.assertEqual(akshare.calls, [("HK00700", "hk")])
        self.assertEqual(
            [(item["provider"], item["action"]) for item in manager.get_last_realtime_quote_trace()],
            [
                ("market_route", "selected"),
                ("twelve_data", "attempting"),
                ("twelve_data", "failed"),
                ("akshare_hk", "attempting"),
                ("akshare_hk", "succeeded"),
            ],
        )

    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_each_twelve_data_alias_is_runtime_eligible_without_provider_calls(
        self,
        _mock_parse_litellm_yaml,
        _mock_setup_env,
    ) -> None:
        aliases = (
            "TWELVE_DATA_API_KEYS",
            "TWELVE_DATA_API_KEY",
            "TWELVEDATA_API_KEYS",
            "TWELVEDATA_API_KEY",
        )

        for env_name in aliases:
            with self.subTest(env_name=env_name), patch.dict(
                os.environ,
                {"STOCK_LIST": "600519", env_name: "td-runtime-sentinel"},
                clear=True,
            ):
                Config.reset_instance()
                manager = DataFetcherManager(fetchers=[_AkshareHkStub(None)])
                fetcher = object()
                with patch(
                    "data_provider.twelve_data_fetcher.TwelveDataFetcher",
                    return_value=fetcher,
                ) as constructor:
                    resolved = manager._get_twelve_data_fetcher()

                self.assertIs(resolved, fetcher)
                constructor.assert_called_once()
                manager.close()

    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_empty_twelve_data_credentials_are_runtime_ineligible(
        self,
        _mock_parse_litellm_yaml,
        _mock_setup_env,
    ) -> None:
        with patch.dict(
            os.environ,
            {"STOCK_LIST": "600519", "TWELVE_DATA_API_KEYS": " ,  "},
            clear=True,
        ):
            Config.reset_instance()
            manager = DataFetcherManager(fetchers=[_AkshareHkStub(None)])
            with patch(
                "data_provider.twelve_data_fetcher.TwelveDataFetcher",
                side_effect=AssertionError("missing credentials must not construct a provider"),
            ):
                resolved = manager._get_twelve_data_fetcher()

        self.assertIsNone(resolved)
        manager.close()


if __name__ == "__main__":
    unittest.main()
