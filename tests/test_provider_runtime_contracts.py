# -*- coding: utf-8 -*-
"""Regression tests that freeze current provider runtime contracts."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

from data_provider.base import DataFetcherManager
from data_provider.realtime_types import RealtimeSource, UnifiedRealtimeQuote
from src.repositories.stock_repo import StockRepository
from src.services.agent_stock_evidence_service import StockEvidenceService
from src.services.market_scanner_service import MarketScannerService
from src.services.stock_evidence_quote_adapter import (
    StockEvidenceQuoteAdapter,
    StockEvidenceQuoteSnapshot,
)
from src.services.stock_service import StockService
from src.services.us_history_helper import (
    LOCAL_US_PARQUET_SOURCE,
    LocalUsHistoryLoadResult,
    fetch_daily_history_with_local_us_fallback,
)
from src.storage import DatabaseManager
from tests.test_market_scanner_service import (
    FakeHkScannerDataManager,
    FakeScannerDataManager,
    FakeUsScannerDataManager,
    StructuredScannerDataManager,
    seed_hk_local_history,
    seed_us_local_history,
)


class _RealtimeFetcher:
    def __init__(
        self,
        *,
        name: str,
        priority: int,
        quote: UnifiedRealtimeQuote | None = None,
        quotes_by_source: dict[str | None, UnifiedRealtimeQuote | None] | None = None,
    ) -> None:
        self.name = name
        self.priority = priority
        self.quote = quote
        self.quotes_by_source = dict(quotes_by_source or {})
        self.calls: list[tuple[str, str | None]] = []

    def get_realtime_quote(self, stock_code: str, source: str | None = None):
        self.calls.append((stock_code, source))
        if self.quotes_by_source:
            return self.quotes_by_source.get(source)
        return self.quote


class _RemoteNameFetcher:
    name = "RemoteNameFetcher"
    priority = 1

    def __init__(self, result: str = "远程名称") -> None:
        self.result = result
        self.calls: list[str] = []

    def get_stock_name(self, stock_code: str) -> str:
        self.calls.append(stock_code)
        return self.result


class _BoardWarningScannerDataManager(FakeScannerDataManager):
    def get_belong_boards(self, stock_code: str):
        raise RuntimeError(f"board lookup failed for {stock_code}")


def _realtime_config(*, enabled: bool, priority: str = "efinance,akshare_em,tushare") -> SimpleNamespace:
    return SimpleNamespace(
        enable_realtime_quote=enabled,
        realtime_source_priority=priority,
    )


def _in_memory_db() -> DatabaseManager:
    DatabaseManager.reset_instance()
    return DatabaseManager(db_url="sqlite:///:memory:")


def test_realtime_quote_disabled_returns_none_with_normalized_trace_shape() -> None:
    manager = DataFetcherManager(fetchers=[])

    with patch("src.config.get_config", return_value=_realtime_config(enabled=False)):
        quote = manager.get_realtime_quote("600519")

    assert quote is None
    assert manager.get_last_realtime_quote_trace() == [
        {
            "sequence": 1,
            "provider": "market_realtime",
            "action": "skipped",
            "outcome": "not_configured",
            "status": "not_configured",
            "reason": "enable_realtime_quote_disabled",
            "message": "Realtime quote is disabled by config.",
        }
    ]


def test_cn_quote_keeps_first_success_and_only_merges_missing_supplementary_fields() -> None:
    primary = UnifiedRealtimeQuote(
        code="600519",
        name="贵州茅台",
        source=RealtimeSource.EFINANCE,
        price=1700.0,
        amplitude=3.5,
    )
    secondary = UnifiedRealtimeQuote(
        code="600519",
        name="次级名称",
        source=RealtimeSource.AKSHARE_EM,
        price=9999.0,
        amplitude=9.9,
        volume_ratio=1.7,
        turnover_rate=2.6,
    )
    manager = DataFetcherManager(
        fetchers=[
            _RealtimeFetcher(name="EfinanceFetcher", priority=1, quote=primary),
            _RealtimeFetcher(
                name="AkshareFetcher",
                priority=2,
                quotes_by_source={"em": secondary},
            ),
            _RealtimeFetcher(
                name="TushareFetcher",
                priority=3,
                quote=UnifiedRealtimeQuote(
                    code="600519",
                    name="第三来源",
                    source=RealtimeSource.TUSHARE,
                    price=1.0,
                ),
            ),
        ]
    )

    with patch("src.config.get_config", return_value=_realtime_config(enabled=True)):
        quote = manager.get_realtime_quote("SH600519")

    assert quote is not None
    assert quote.code == "600519"
    assert quote.name == "贵州茅台"
    assert quote.source == RealtimeSource.EFINANCE
    assert quote.price == 1700.0
    assert quote.amplitude == 3.5
    assert quote.volume_ratio == 1.7
    assert quote.turnover_rate == 2.6

    trace = manager.get_last_realtime_quote_trace()
    assert trace[0]["provider"] == "market_route"
    assert trace[0]["message"] == "CN market route selected: efinance -> akshare_em -> tushare"
    assert any(
        item["provider"] == "akshare_em"
        and item["action"] == "succeeded"
        and item["outcome"] == "partial"
        and "volume_ratio, turnover_rate" in str(item["message"] or "")
        for item in trace
    )
    assert trace[-1] == {
        "sequence": 9,
        "provider": "efinance",
        "action": "completed",
        "outcome": "ok",
        "status": "ok",
        "reason": "accepted_with_partial_fields",
        "message": "Final market source accepted: efinance (partial fields).",
    }


def test_unified_realtime_quote_shape_filters_none_and_requires_positive_price() -> None:
    quote = UnifiedRealtimeQuote(
        code="AAPL",
        name="Apple",
        source=RealtimeSource.YFINANCE,
        price=212.8,
        change_pct=6.72,
        volume=None,
        amount=7.72e9,
    )

    assert quote.to_dict() == {
        "code": "AAPL",
        "name": "Apple",
        "source": "yfinance",
        "price": 212.8,
        "change_pct": 6.72,
        "amount": 7.72e9,
    }
    assert quote.has_basic_data() is True
    assert UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.YFINANCE, price=0.0).has_basic_data() is False
    assert UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.YFINANCE, price=None).has_basic_data() is False


def test_us_history_local_hit_bypasses_manager_and_preserves_df_source_contract() -> None:
    local_df = pd.DataFrame({"date": ["2024-01-01"], "close": [100.0]})
    manager = MagicMock()

    with patch(
        "src.services.us_history_helper.load_local_us_daily_history",
        return_value=LocalUsHistoryLoadResult(
            stock_code="AAPL",
            path=Path("/tmp/AAPL.parquet"),
            status="hit",
            dataframe=local_df,
        ),
    ):
        df, source = fetch_daily_history_with_local_us_fallback(
            "AAPL",
            days=20,
            manager=manager,
            log_context="[provider runtime contract]",
        )

    assert df is local_df
    assert source == LOCAL_US_PARQUET_SOURCE
    manager.get_daily_data.assert_not_called()


def test_us_history_remote_fallback_preserves_normalized_symbol_dates_and_source_label() -> None:
    fallback_df = pd.DataFrame({"date": ["2024-01-02"], "close": [101.5]})
    manager = MagicMock()
    manager.get_daily_data.return_value = (fallback_df, "YfinanceFetcher")

    with patch(
        "src.services.us_history_helper.load_local_us_daily_history",
        return_value=LocalUsHistoryLoadResult(
            stock_code="AAPL",
            path=Path("/tmp/AAPL.parquet"),
            status="missing",
        ),
    ):
        df, source = fetch_daily_history_with_local_us_fallback(
            "aapl",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            days=20,
            manager=manager,
            log_context="[provider runtime contract]",
        )

    assert df is fallback_df
    assert source == "YfinanceFetcher"
    manager.get_daily_data.assert_called_once_with(
        stock_code="AAPL",
        start_date="2024-01-01",
        end_date="2024-01-31",
        days=20,
    )


def test_stock_service_history_payload_preserves_aggregation_shape() -> None:
    daily_df = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2024-01-01"),
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1000,
                "amount": 10200,
                "pct_chg": 2.0,
            },
            {
                "date": pd.Timestamp("2024-01-02"),
                "open": 10.2,
                "high": 10.8,
                "low": 10.1,
                "close": 10.6,
                "volume": 1200,
                "amount": 12720,
                "pct_chg": 3.92,
            },
        ]
    )
    manager = SimpleNamespace(get_stock_name=lambda stock_code: "Apple")

    with (
        patch("data_provider.base.DataFetcherManager", return_value=manager),
        patch(
            "src.services.stock_service.fetch_daily_history_with_local_us_fallback",
            return_value=(daily_df, LOCAL_US_PARQUET_SOURCE),
        ),
    ):
        payload = StockService().get_history_data("AAPL", period="daily", days=2)

    assert payload == {
        "stock_code": "AAPL",
        "stock_name": "Apple",
        "period": "daily",
        "data": [
            {
                "date": "2024-01-01",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1000.0,
                "amount": 10200.0,
                "change_percent": 2.0,
            },
            {
                "date": "2024-01-02",
                "open": 10.2,
                "high": 10.8,
                "low": 10.1,
                "close": 10.6,
                "volume": 1200.0,
                "amount": 12720.0,
                "change_percent": 3.92,
            },
        ],
    }


def test_stock_name_lookup_prefers_cache_before_realtime_and_remote_fetchers() -> None:
    manager = DataFetcherManager.__new__(DataFetcherManager)
    manager._stock_name_cache = {"600519": "缓存名称"}
    manager._fetchers = [_RemoteNameFetcher()]
    manager.get_realtime_quote = MagicMock(
        return_value=UnifiedRealtimeQuote(
            code="600519",
            name="实时名称",
            source=RealtimeSource.EFINANCE,
            price=1700.0,
        )
    )

    name = DataFetcherManager.get_stock_name(manager, "600519")

    assert name == "缓存名称"
    manager.get_realtime_quote.assert_not_called()
    assert manager._fetchers[0].calls == []


def test_stock_name_lookup_uses_realtime_only_when_enabled() -> None:
    manager = DataFetcherManager.__new__(DataFetcherManager)
    manager._fetchers = []
    manager.get_realtime_quote = MagicMock(
        return_value=UnifiedRealtimeQuote(
            code="NVDA",
            name="NVIDIA",
            source=RealtimeSource.YFINANCE,
            price=964.0,
        )
    )

    name = DataFetcherManager.get_stock_name(manager, "NVDA", allow_realtime=True)

    assert name == "NVIDIA"
    manager.get_realtime_quote.assert_called_once_with("NVDA")


def test_stock_name_lookup_short_circuits_us_symbols_to_empty_without_cn_fetchers() -> None:
    manager = DataFetcherManager.__new__(DataFetcherManager)
    remote_fetcher = _RemoteNameFetcher(result="CN fallback name")
    manager._fetchers = [remote_fetcher]
    manager.get_realtime_quote = MagicMock()

    name = DataFetcherManager.get_stock_name(manager, "ORCL", allow_realtime=False)

    assert name == ""
    manager.get_realtime_quote.assert_not_called()
    assert remote_fetcher.calls == []


def test_validate_ticker_exists_accepts_meaningful_quote_name_after_placeholder_lookup() -> None:
    manager = SimpleNamespace(
        get_stock_name=lambda stock_code, allow_realtime=False: "待确认股票",
        get_realtime_quote=lambda stock_code: UnifiedRealtimeQuote(
            code=stock_code,
            name="NVIDIA",
            source=RealtimeSource.YFINANCE,
            price=964.0,
        ),
    )

    with patch("data_provider.base.DataFetcherManager", return_value=manager):
        result = StockService().validate_ticker_exists("NVDA")

    assert result == {
        "stock_code": "NVDA",
        "exists": True,
        "stock_name": "NVIDIA",
    }


def test_stock_evidence_quote_preserves_available_provider_source() -> None:
    service = StockEvidenceService(
        fetcher_manager=SimpleNamespace(
            get_realtime_quote=lambda symbol: UnifiedRealtimeQuote(
                code=symbol,
                name="Apple",
                source=RealtimeSource.ALPACA,
                price=214.55,
                change_pct=1.23,
                market_timestamp="2026-05-13T08:30:00Z",
            )
        ),
        stock_repo=MagicMock(),
        analysis_repo=MagicMock(),
    )

    payload = service._quote("AAPL")

    assert payload == {
        "status": "available",
        "price": 214.55,
        "changePct": 1.23,
        "currency": "USD",
        "provider": "alpaca",
        "updatedAt": "2026-05-13T08:30:00Z",
    }


def test_stock_evidence_quote_adapter_returns_inert_snapshot_for_basic_quote() -> None:
    adapter = StockEvidenceQuoteAdapter(
        fetcher_manager=SimpleNamespace(
            get_realtime_quote=lambda symbol: UnifiedRealtimeQuote(
                code=symbol,
                name="Apple",
                source=RealtimeSource.ALPACA,
                price=214.55,
                change_pct=1.23,
                total_mv=3210000000.0,
                pe_ratio=30.2,
                pb_ratio=12.1,
                market_timestamp="2026-05-13T08:30:00Z",
            )
        )
    )

    snapshot = adapter.get_quote_snapshot("AAPL")

    assert snapshot == StockEvidenceQuoteSnapshot(
        source="alpaca",
        price=214.55,
        change_pct=1.23,
        total_mv=3210000000.0,
        pe_ratio=30.2,
        pb_ratio=12.1,
        market_timestamp="2026-05-13T08:30:00Z",
    )


def test_stock_evidence_service_keeps_fetcher_manager_constructor_compatibility() -> None:
    fetcher_manager = SimpleNamespace(get_realtime_quote=lambda symbol: None)
    service = StockEvidenceService(
        fetcher_manager=fetcher_manager,
        stock_repo=MagicMock(),
        analysis_repo=MagicMock(),
    )

    assert service.fetcher_manager is fetcher_manager
    assert service.quote_adapter.fetcher_manager is fetcher_manager


def test_stock_evidence_quote_rejects_partial_or_non_basic_quotes_as_unknown() -> None:
    service = StockEvidenceService(
        fetcher_manager=SimpleNamespace(
            get_realtime_quote=lambda symbol: UnifiedRealtimeQuote(
                code=symbol,
                name="Apple",
                source=RealtimeSource.ALPACA,
                price=0.0,
                change_pct=1.23,
            )
        ),
        stock_repo=MagicMock(),
        analysis_repo=MagicMock(),
    )

    payload = service._quote("AAPL")

    assert payload == {
        "status": "unknown",
        "provider": "realtime_quote",
    }


def test_stock_evidence_quote_surfaces_runtime_errors_as_error_status() -> None:
    service = StockEvidenceService(
        fetcher_manager=SimpleNamespace(
            get_realtime_quote=MagicMock(side_effect=RuntimeError("provider down")),
        ),
        stock_repo=MagicMock(),
        analysis_repo=MagicMock(),
    )

    payload = service._quote("AAPL")

    assert payload["status"] == "error"
    assert payload["provider"] == "realtime_quote"
    assert payload["error"] == "provider down"


def test_cn_scanner_degraded_snapshot_preserves_labels_and_provider_diagnostics() -> None:
    db = _in_memory_db()
    stock_repo = StockRepository(db)
    temp_dir = tempfile.TemporaryDirectory()
    cache_path = Path(temp_dir.name) / "scanner_cn_universe_cache.csv"
    manager = StructuredScannerDataManager(
        snapshot_result={
            "success": False,
            "source": None,
            "data": None,
            "attempts": [
                {
                    "fetcher": "AkshareFetcher",
                    "status": "failed",
                    "reason_code": "akshare_snapshot_fetch_failed",
                    "summary": "akshare unavailable",
                },
                {
                    "fetcher": "EfinanceFetcher",
                    "status": "failed",
                    "reason_code": "efinance_snapshot_fetch_failed",
                    "summary": "efinance timeout",
                },
            ],
            "error_code": "no_realtime_snapshot_available",
            "error_message": "snapshot unavailable",
        }
    )
    for code, history in manager.histories.items():
        stock_repo.save_dataframe(history.copy(), code, data_source="LocalWarmCache")

    result = MarketScannerService(
        db,
        data_manager=manager,
        local_universe_cache_path=str(cache_path),
    ).run_scan(
        market="cn",
        shortlist_size=3,
        universe_limit=50,
        detail_limit=10,
    )
    temp_dir.cleanup()

    scanner_data = result["diagnostics"]["scanner_data"]
    provider_diagnostics = result["diagnostics"]["provider_diagnostics"]

    assert scanner_data["degraded_mode_used"] is True
    assert scanner_data["universe_resolution"]["source"] == "FakeListSource"
    assert scanner_data["snapshot_resolution"]["source"] == "local_history_degraded"
    assert provider_diagnostics["snapshot_source_used"] == "local_history_degraded"
    assert provider_diagnostics["history_source_used"] == "local_db"
    assert provider_diagnostics["fallback_occurred"] is True
    assert provider_diagnostics["fallback_count"] == 2
    assert "local_universe_cache failed (local_universe_cache_missing)" in provider_diagnostics["provider_warnings"]
    assert "AkshareFetcher failed (akshare_snapshot_fetch_failed)" in provider_diagnostics["provider_warnings"]
    assert "snapshot=local_history_degraded" in result["source_summary"]
    assert "history=local_first" in result["source_summary"]


def test_us_and_hk_scanner_route_labels_preserve_quote_sources() -> None:
    us_db = _in_memory_db()
    us_stock_repo = StockRepository(us_db)
    seed_us_local_history(us_stock_repo)
    us_result = MarketScannerService(us_db, data_manager=FakeUsScannerDataManager()).run_scan(
        market="us",
        profile="us_preopen_v1",
        shortlist_size=2,
        universe_limit=50,
        detail_limit=10,
        universe_type="symbols",
        symbols=["NVDA", "PLTR"],
    )

    assert us_result["diagnostics"]["scanner_data"]["snapshot_resolution"]["source"] == "yfinance"
    assert us_result["diagnostics"]["provider_diagnostics"]["quote_source_used"] == "yfinance"
    assert us_result["diagnostics"]["provider_diagnostics"]["snapshot_source_used"] == "yfinance"
    assert "universe=custom_symbols" in us_result["source_summary"]
    assert "snapshot=yfinance" in us_result["source_summary"]

    hk_db = _in_memory_db()
    hk_stock_repo = StockRepository(hk_db)
    seed_hk_local_history(hk_stock_repo)
    hk_result = MarketScannerService(hk_db, data_manager=FakeHkScannerDataManager()).run_scan(
        market="hk",
        profile="hk_preopen_v1",
        shortlist_size=2,
        universe_limit=50,
        detail_limit=10,
        universe_type="symbols",
        symbols=["HK00700", "HK01810"],
    )

    assert hk_result["diagnostics"]["scanner_data"]["snapshot_resolution"]["source"] == "twelve_data"
    assert hk_result["diagnostics"]["provider_diagnostics"]["quote_source_used"] == "twelve_data"
    assert hk_result["diagnostics"]["provider_diagnostics"]["snapshot_source_used"] == "twelve_data"
    assert "universe=custom_symbols" in hk_result["source_summary"]
    assert "snapshot=twelve_data" in hk_result["source_summary"]


def test_scanner_board_lookup_failures_remain_visible_in_candidate_diagnostics() -> None:
    db = _in_memory_db()
    result = MarketScannerService(db, data_manager=_BoardWarningScannerDataManager()).run_scan(
        market="cn",
        shortlist_size=3,
        universe_limit=50,
        detail_limit=10,
    )

    first = result["shortlist"][0]["diagnostics"]
    assert first["board_warning"].startswith("board lookup failed for ")
