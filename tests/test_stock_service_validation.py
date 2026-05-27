import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.services.stock_service import StockService
from src.services.stock_service_provider_adapter import StockServiceQuoteSnapshot


class StockServiceValidationTestCase(unittest.TestCase):
    def test_validate_ticker_exists_accepts_meaningful_name_without_quote(self) -> None:
        adapter = SimpleNamespace(
            get_stock_name=lambda stock_code, allow_realtime=False: "NVIDIA",
            get_quote_snapshot=lambda stock_code: None,
        )

        with patch("src.services.stock_service.StockServiceProviderAdapter", return_value=adapter):
            result = StockService().validate_ticker_exists("NVDA")

        self.assertTrue(result["exists"])
        self.assertEqual(result["stock_code"], "NVDA")
        self.assertEqual(result["stock_name"], "NVIDIA")

    def test_validate_ticker_exists_rejects_placeholder_or_unknown_names(self) -> None:
        adapter = SimpleNamespace(
            get_stock_name=lambda stock_code, allow_realtime=False: "待确认股票",
            get_quote_snapshot=lambda stock_code: None,
        )

        with patch("src.services.stock_service.StockServiceProviderAdapter", return_value=adapter):
            result = StockService().validate_ticker_exists("ZZZZZ")

        self.assertFalse(result["exists"])
        self.assertEqual(result["stock_code"], "ZZZZZ")
        self.assertIsNone(result["stock_name"])

    def test_get_realtime_quote_maps_adapter_snapshot_without_provider_dto_leakage(self) -> None:
        adapter = SimpleNamespace(
            get_quote_snapshot=lambda stock_code: StockServiceQuoteSnapshot(
                stock_code=stock_code,
                stock_name="Apple",
                current_price=214.55,
                change=2.35,
                change_percent=1.11,
                open=213.0,
                high=215.0,
                low=212.5,
                prev_close=212.2,
                volume=1000.0,
                amount=214550.0,
                source="alpaca",
                market_timestamp="2026-05-28T09:30:00Z",
            )
        )

        with patch("src.services.stock_service.StockServiceProviderAdapter", return_value=adapter):
            result = StockService().get_realtime_quote("AAPL")

        self.assertEqual(result["stock_code"], "AAPL")
        self.assertEqual(result["stock_name"], "Apple")
        self.assertEqual(result["current_price"], 214.55)
        self.assertEqual(result["change"], 2.35)
        self.assertEqual(result["change_percent"], 1.11)
        self.assertEqual(result["open"], 213.0)
        self.assertEqual(result["high"], 215.0)
        self.assertEqual(result["low"], 212.5)
        self.assertEqual(result["prev_close"], 212.2)
        self.assertEqual(result["volume"], 1000.0)
        self.assertEqual(result["amount"], 214550.0)
        self.assertEqual(result["source"], "alpaca")
        self.assertEqual(result["source_type"], "provider_runtime")
        self.assertEqual(result["market_timestamp"], "2026-05-28T09:30:00Z")
        self.assertEqual(result["freshness"], "live")
        self.assertFalse(result["is_fallback"])
        self.assertFalse(result["is_partial"])
        self.assertFalse(result["is_synthetic"])
        self.assertEqual(result["sourceConfidence"]["source"], "alpaca")
        self.assertEqual(result["sourceConfidence"]["asOf"], "2026-05-28T09:30:00Z")
        self.assertEqual(result["sourceConfidence"]["freshness"], "live")
        self.assertIsInstance(result["update_time"], str)
        self.assertEqual(result["observed_at"], result["update_time"])
        self.assertNotEqual(result["update_time"], result["market_timestamp"])

    def test_get_realtime_quote_marks_provider_reported_fallback_as_non_fresh(self) -> None:
        adapter = SimpleNamespace(
            get_quote_snapshot=lambda stock_code: StockServiceQuoteSnapshot(
                stock_code=stock_code,
                stock_name="Apple",
                current_price=214.55,
                change=-1.0,
                change_percent=-0.46,
                open=215.0,
                high=216.0,
                low=213.8,
                prev_close=215.55,
                volume=1000.0,
                amount=214550.0,
                source="fallback",
                market_timestamp="2026-05-28T09:30:00Z",
            )
        )

        with patch("src.services.stock_service.StockServiceProviderAdapter", return_value=adapter):
            result = StockService().get_realtime_quote("AAPL")

        self.assertEqual(result["source"], "fallback")
        self.assertEqual(result["freshness"], "fallback")
        self.assertEqual(result["source_type"], "fallback")
        self.assertTrue(result["is_fallback"])
        self.assertFalse(result["is_stale"])
        self.assertFalse(result["is_synthetic"])
        self.assertEqual(result["sourceConfidence"]["freshness"], "fallback")
        self.assertTrue(result["sourceConfidence"]["isFallback"])
        self.assertNotEqual(result["update_time"], result["market_timestamp"])

    def test_get_realtime_quote_placeholder_does_not_claim_live_freshness(self) -> None:
        with patch("src.services.stock_service.StockServiceProviderAdapter", side_effect=ImportError):
            result = StockService().get_realtime_quote("AAPL")

        self.assertEqual(result["stock_code"], "AAPL")
        self.assertEqual(result["stock_name"], "股票AAPL")
        self.assertEqual(result["source"], "placeholder")
        self.assertEqual(result["source_type"], "synthetic_placeholder")
        self.assertIsNone(result["market_timestamp"])
        self.assertEqual(result["freshness"], "synthetic")
        self.assertFalse(result["is_fallback"])
        self.assertTrue(result["is_partial"])
        self.assertTrue(result["is_synthetic"])
        self.assertEqual(result["sourceConfidence"]["freshness"], "synthetic")
        self.assertTrue(result["sourceConfidence"]["isSynthetic"])
        self.assertEqual(result["observed_at"], result["update_time"])


if __name__ == "__main__":
    unittest.main()
