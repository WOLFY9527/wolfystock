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
        assert {
            "coverage_summary",
            "provider_diagnostics",
            "scanner_data",
            "universe_selection",
        } <= set(result["diagnostics"])
        candidate_by_status = {item["status"]: item for item in result["candidates"]}
        for status in ("selected", "rejected", "data_failed"):
            assert {
                "rank",
                "status",
                "score",
                "provider",
                "reason",
                "failed_rules",
                "missing_fields",
                "metrics",
            } <= set(candidate_by_status[status]), f"{status} candidate diagnostics must keep bounded scanner fields"
            assert candidate_by_status[status]["provider"]
            assert isinstance(candidate_by_status[status]["rank"], int)
            assert candidate_by_status[status]["rank"] > 0
        assert all(item["reason"] or item["failed_rules"] for item in result["candidates"] if item["status"] == "rejected")
        assert any(item["status"] == "data_failed" and item["missing_fields"] for item in result["candidates"])
        assert candidate_by_status["selected"]["score"] is not None
        assert candidate_by_status["selected"]["failed_rules"] == []
        assert candidate_by_status["selected"]["missing_fields"] == []
        assert candidate_by_status["rejected"]["score"] is not None
        assert candidate_by_status["rejected"]["failed_rules"]
        assert candidate_by_status["data_failed"]["score"] is None
        assert candidate_by_status["data_failed"]["missing_fields"]
        assert candidate_by_status["data_failed"]["metrics"] == {}
        assert len(data_manager.realtime_quote_calls) == 9
    finally:
        DatabaseManager.reset_instance()
