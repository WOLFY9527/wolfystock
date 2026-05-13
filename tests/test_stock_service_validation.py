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
        self.assertIsInstance(result["update_time"], str)


if __name__ == "__main__":
    unittest.main()
