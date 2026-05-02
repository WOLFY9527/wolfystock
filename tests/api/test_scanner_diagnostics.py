# -*- coding: utf-8 -*-
"""Scanner diagnostics contract tests."""

from src.repositories.stock_repo import StockRepository
from src.services.market_scanner_service import MarketScannerService
from src.storage import DatabaseManager
from tests.test_market_scanner_service import FakeUsScannerDataManager, seed_crypto_miner_local_history


def test_crypto_mining_scan_returns_full_candidate_diagnostics() -> None:
    DatabaseManager.reset_instance()
    db = DatabaseManager(db_url="sqlite:///:memory:")
    try:
        stock_repo = StockRepository(db)
        seed_crypto_miner_local_history(stock_repo)
        data_manager = FakeUsScannerDataManager()
        service = MarketScannerService(db, data_manager=data_manager)

        result = service.run_scan(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=1,
            universe_limit=50,
            detail_limit=10,
            universe_type="theme",
            theme_id="crypto_miners",
        )

        assert result["summary"]["universe_count"] == 11
        assert result["summary"]["selected_count"] == 1
        assert result["summary"]["rejected_count"] == 8
        assert result["summary"]["data_failed_count"] == 2
        assert result["summary"]["limited_by_result_cap"] is False
        assert len(result["candidates"]) == 11
        assert result["selected"] == result["shortlist"]
        assert all(item["reason"] or item["failed_rules"] for item in result["candidates"] if item["status"] == "rejected")
        assert any(item["status"] == "data_failed" and item["missing_fields"] for item in result["candidates"])
        assert len(data_manager.realtime_quote_calls) == 9
    finally:
        DatabaseManager.reset_instance()
