# -*- coding: utf-8 -*-
"""Integration tests for backtest service and repository.

These tests run against a temporary SQLite DB (same approach as other tests)
and validate idempotency/force semantics, result field correctness,
summary creation, and query methods.
"""

import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pandas as pd

from src.config import Config
from src.core.backtest_engine import OVERALL_SENTINEL_CODE
from src.services.backtest_service import BacktestService
from src.storage import AnalysisHistory, BacktestResult, BacktestRun, BacktestSummary, DatabaseManager, StockDaily


class BacktestServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_backtest_service.db")
        self._original_database_path = os.environ.get("DATABASE_PATH")
        self._original_eval_window = os.environ.get("BACKTEST_EVAL_WINDOW_DAYS")
        self._original_min_age = os.environ.get("BACKTEST_MIN_AGE_DAYS")
        self._original_backtest_enabled = os.environ.get("BACKTEST_ENABLED")
        os.environ["DATABASE_PATH"] = self._db_path
        os.environ["BACKTEST_EVAL_WINDOW_DAYS"] = "3"
        os.environ["BACKTEST_MIN_AGE_DAYS"] = "14"
        os.environ["BACKTEST_ENABLED"] = "true"

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        self._history_fetch_patch = patch(
            "src.services.backtest_service.fetch_daily_history_with_local_us_fallback",
            return_value=(None, None),
        )
        self._history_fetch_mock = self._history_fetch_patch.start()
        self._history_fetch_patch_active = True

        # Ensure analysis is old enough for default min_age_days=14
        old_created_at = datetime(2024, 1, 1, 0, 0, 0)

        with self.db.get_session() as session:
            session.add(
                AnalysisHistory(
                    query_id="q1",
                    code="600519",
                    name="贵州茅台",
                    report_type="simple",
                    sentiment_score=80,
                    operation_advice="买入",
                    trend_prediction="看多",
                    analysis_summary="test",
                    stop_loss=95.0,
                    take_profit=110.0,
                    created_at=old_created_at,
                    context_snapshot='{"enhanced_context": {"date": "2024-01-01"}}',
                )
            )

            # Analysis day close
            session.add(
                StockDaily(
                    code="600519",
                    date=date(2024, 1, 1),
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                )
            )

            # Forward bars (3 days) that hit take-profit on day1
            session.add_all(
                [
                    StockDaily(code="600519", date=date(2024, 1, 2), high=111.0, low=100.0, close=105.0),
                    StockDaily(code="600519", date=date(2024, 1, 3), high=108.0, low=103.0, close=106.0),
                    StockDaily(code="600519", date=date(2024, 1, 4), high=109.0, low=104.0, close=107.0),
                ]
            )
            session.commit()

    def tearDown(self) -> None:
        if getattr(self, "_history_fetch_patch_active", False):
            self._history_fetch_patch.stop()
            self._history_fetch_patch_active = False
        DatabaseManager.reset_instance()
        if self._original_database_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = self._original_database_path
        if self._original_eval_window is None:
            os.environ.pop("BACKTEST_EVAL_WINDOW_DAYS", None)
        else:
            os.environ["BACKTEST_EVAL_WINDOW_DAYS"] = self._original_eval_window
        if self._original_min_age is None:
            os.environ.pop("BACKTEST_MIN_AGE_DAYS", None)
        else:
            os.environ["BACKTEST_MIN_AGE_DAYS"] = self._original_min_age
        if self._original_backtest_enabled is None:
            os.environ.pop("BACKTEST_ENABLED", None)
        else:
            os.environ["BACKTEST_ENABLED"] = self._original_backtest_enabled
        self._temp_dir.cleanup()

    def _count_results(self) -> int:
        with self.db.get_session() as session:
            return session.query(BacktestResult).count()

    def _count_runs(self) -> int:
        with self.db.get_session() as session:
            return session.query(BacktestRun).count()

    def _allow_history_fetch(self) -> None:
        if getattr(self, "_history_fetch_patch_active", False):
            self._history_fetch_patch.stop()
            self._history_fetch_patch_active = False

    def _insert_cached_ohlcv_rows(self, code: str = "CACHED") -> None:
        with self.db.get_session() as session:
            session.add_all(
                [
                    StockDaily(code=code, date=date(2024, 3, 1), open=10.0, high=10.2, low=9.8, close=10.0, volume=100),
                    StockDaily(code=code, date=date(2024, 3, 4), open=10.1, high=10.5, low=10.0, close=10.4, volume=110),
                    StockDaily(code=code, date=date(2024, 3, 5), open=10.4, high=10.8, low=10.2, close=10.7, volume=120),
                    StockDaily(code=code, date=date(2024, 3, 6), open=10.7, high=10.9, low=10.4, close=10.5, volume=130),
                ]
            )
            session.commit()

    def _insert_backtest_sample(self, code: str = "AAPL", sample_date: date = date(2024, 3, 1)) -> None:
        owner_id = self.db.require_user_id(None)
        with self.db.get_session() as session:
            session.add(
                AnalysisHistory(
                    owner_id=owner_id,
                    query_id=f"bt-sample:{code}:{sample_date.isoformat()}:w3",
                    code=code,
                    name=code,
                    report_type="backtest_sample",
                    sentiment_score=50,
                    operation_advice="观望",
                    trend_prediction="中性",
                    analysis_summary="sample",
                    created_at=datetime(2024, 3, 2, 0, 0, 0),
                    context_snapshot=f'{{"enhanced_context": {{"date": "{sample_date.isoformat()}"}}}}',
                )
            )
            session.commit()

    @staticmethod
    def _write_local_us_parquet(cache_dir: str, symbol: str, *, rows: int = 90) -> None:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=max(rows - 1, 0))
        frame = pd.DataFrame(
            [
                {
                    "date": (start_date + timedelta(days=index)).isoformat(),
                    "open": 100.0 + index,
                    "high": 101.0 + index,
                    "low": 99.0 + index,
                    "close": 100.5 + index,
                    "volume": 1_000_000 + index,
                    "adjusted_close": 100.5 + index,
                }
                for index in range(rows)
            ]
        )
        frame.to_parquet(os.path.join(cache_dir, f"{symbol.upper()}.parquet"), index=False)

    def test_force_semantics(self) -> None:
        service = BacktestService(self.db)

        stats1 = service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)
        self.assertEqual(stats1["saved"], 1)
        self.assertEqual(self._count_results(), 1)

        # Non-force should be idempotent
        stats2 = service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)
        self.assertEqual(stats2["saved"], 0)
        self.assertEqual(self._count_results(), 1)

        # Force should replace existing result without unique constraint errors
        stats3 = service.run_backtest(code="600519", force=True, eval_window_days=3, min_age_days=0, limit=10)
        self.assertEqual(stats3["saved"], 1)
        self.assertEqual(self._count_results(), 1)

    def test_engine_disabled_returns_distinct_readiness_without_processing_samples(self) -> None:
        os.environ["BACKTEST_ENABLED"] = "false"
        Config._instance = None
        service = BacktestService(self.db)

        stats = service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)
        status = service.get_sample_status(code="600519")

        self.assertEqual(stats["processed"], 0)
        self.assertEqual(stats["saved"], 0)
        self.assertEqual(stats["no_result_reason"], "engine_disabled")
        self.assertEqual(stats["calculation_status"], "engine_disabled")
        self.assertEqual(stats["sample_status"], "engine_disabled")
        self.assertEqual(stats["execution_readiness"]["state"], "engine_disabled")
        self.assertFalse(stats["execution_readiness"]["result_contract_available"])
        self.assertNotIn("insufficient_history", stats["execution_readiness"]["reason_codes"])
        self.assertEqual(status["sample_readiness_state"], "engine_disabled")
        self.assertEqual(status["execution_readiness"]["state"], "engine_disabled")

    def test_sample_status_without_provider_or_bars_reports_data_disabled_readiness(self) -> None:
        service = BacktestService(self.db)

        status = service.get_sample_status(code="NODATA")

        self.assertEqual(status["sample_readiness_state"], "missing_cache")
        self.assertEqual(status["execution_readiness"]["state"], "data_disabled")
        self.assertFalse(status["execution_readiness"]["result_contract_available"])
        self.assertIn("provider_missing", status["execution_readiness"]["reason_codes"])
        self.assertIn("insufficient_history", status["execution_readiness"]["reason_codes"])

    def test_fixture_local_bars_return_executable_readiness_and_safe_result_contract(self) -> None:
        service = BacktestService(self.db)

        stats = service.run_backtest(code="600519", force=True, eval_window_days=3, min_age_days=0, limit=10)

        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["calculation_status"], "ready")
        self.assertEqual(stats["execution_readiness"]["state"], "executable")
        self.assertTrue(stats["execution_readiness"]["result_contract_available"])
        self.assertTrue(stats["execution_readiness"]["observation_only"])
        self.assertIn("Research diagnostic only", stats["no_advice_disclosure"])

    def test_sample_status_is_passive_with_cached_ohlcv_and_does_not_prepare_samples(self) -> None:
        self._insert_cached_ohlcv_rows()
        service = BacktestService(self.db)

        with (
            patch.object(service, "_ensure_market_history") as ensure_market_history,
            patch.object(service, "_ensure_cached_backtest_samples") as ensure_cached_samples,
        ):
            status = service.get_sample_status(code="CACHED")

        ensure_market_history.assert_not_called()
        ensure_cached_samples.assert_not_called()
        self._history_fetch_mock.assert_not_called()
        self.assertEqual(status["prepared_count"], 0)
        self.assertEqual(status["sample_readiness_state"], "no_samples")
        self.assertFalse(status["execution_readiness"]["result_contract_available"])
        self.assertTrue(status["execution_readiness"]["observation_only"])
        self.assertEqual(status["resolved_source"], "DatabaseCache")
        self.assertFalse(status["fallback_used"])
        self.assertEqual(status["historicalOhlcvReadiness"]["overallState"], "ready")
        self.assertEqual(
            status["probePolicy"],
            {
                "scope": "single",
                "runtimeProbeMode": "bounded_provider_observation",
                "liveProviderProbingAllowed": True,
                "maxRuntimeProbeSymbols": 1,
                "activeHydrationAllowed": False,
                "samplePreparationAllowed": False,
                "backtestExecutionAllowed": False,
                "readinessSources": [
                    "existing_database_rows",
                    "local_us_parquet_cache",
                    "bounded_provider_observation",
                ],
                "consumerSafe": True,
            },
        )
        self.assertEqual(
            status["writePolicy"],
            {
                "scope": "single",
                "mode": "read_only",
                "cacheWritesAllowed": False,
                "databaseWritesAllowed": False,
                "consumerSafe": True,
            },
        )

    def test_historical_readiness_helper_requires_explicit_runtime_probe_opt_in(self) -> None:
        service = BacktestService(self.db)

        with patch.dict(
            os.environ,
            {
                "LOCAL_US_PARQUET_DIR": "",
                "US_STOCK_PARQUET_DIR": "",
            },
            clear=False,
        ), patch(
            "src.services.backtest_service.fetch_daily_history_with_local_us_fallback",
            side_effect=AssertionError("runtime provider observation requires explicit opt-in"),
        ) as fetch_mock:
            readiness = service._build_historical_ohlcv_readiness(
                code="TSLA",
                rows=[],
                required_bars=3,
            )

        fetch_mock.assert_not_called()
        self.assertEqual(readiness["providerState"], "provider_missing")
        self.assertEqual(readiness["overallState"], "blocked")

    def test_sample_status_reads_local_us_parquet_without_preparing_samples(self) -> None:
        self._allow_history_fetch()
        self._write_local_us_parquet(self._temp_dir.name, "AAPL", rows=90)
        self._write_local_us_parquet(self._temp_dir.name, "SPY", rows=90)
        service = BacktestService(self.db)

        with patch.dict(
            os.environ,
            {
                "LOCAL_US_PARQUET_DIR": self._temp_dir.name,
                "US_STOCK_PARQUET_DIR": "",
            },
            clear=False,
        ), patch("src.services.us_history_helper.DataFetcherManager") as manager_cls, patch.object(
            service,
            "_ensure_market_history",
        ) as ensure_market_history, patch.object(
            service,
            "_ensure_cached_backtest_samples",
        ) as ensure_cached_samples:
            status = service.get_sample_status(code="AAPL")

        manager_cls.assert_not_called()
        ensure_market_history.assert_not_called()
        ensure_cached_samples.assert_not_called()
        self.assertEqual(status["prepared_count"], 0)
        self.assertEqual(status["sample_readiness_state"], "no_samples")
        self.assertNotIn("missing_cache", status["sample_blocking_reasons"])
        self.assertNotIn("provider_missing", status["sample_blocking_reasons"])
        self.assertFalse(status["execution_readiness"]["result_contract_available"])
        readiness = status["historicalOhlcvReadiness"]
        self.assertEqual(readiness["providerState"], "available")
        self.assertGreater(readiness["usableBars"], 0)
        self.assertEqual(readiness["missingRequirements"], [])

    def test_backtest_readiness_uses_configured_local_us_parquet_cache_with_benchmark(self) -> None:
        self._write_local_us_parquet(self._temp_dir.name, "AAPL", rows=90)
        self._write_local_us_parquet(self._temp_dir.name, "SPY", rows=90)
        service = BacktestService(self.db)

        with patch.dict(
            os.environ,
            {
                "LOCAL_US_PARQUET_DIR": self._temp_dir.name,
                "US_STOCK_PARQUET_DIR": "",
            },
            clear=False,
        ), patch("src.services.us_history_helper.DataFetcherManager") as manager_cls:
            readiness = service._build_historical_ohlcv_readiness(
                code="AAPL",
                rows=[],
                required_bars=60,
                benchmark_required=True,
                benchmark_symbol="SPY",
            )

        manager_cls.assert_not_called()
        self.assertEqual(readiness["providerState"], "available")
        self.assertEqual(readiness["benchmarkState"], "available")
        self.assertGreater(readiness["usableBars"], 0)
        self.assertGreater(readiness["benchmarkUsableBars"], 0)
        self.assertEqual(readiness["missingRequirements"], [])

    def test_run_backtest_auto_executes_deterministic_cached_ohlcv_sample_path(self) -> None:
        with self.db.get_session() as session:
            session.query(AnalysisHistory).delete()
            session.commit()
        self._insert_cached_ohlcv_rows()
        service = BacktestService(self.db)

        stats = service.run_backtest(code="CACHED", force=False, eval_window_days=3, min_age_days=0, limit=10)

        self.assertGreater(stats["processed"], 0)
        self.assertGreater(stats["saved"], 0)
        self.assertGreater(stats["completed"], 0)
        self.assertEqual(stats["evaluation_mode"], "historical_analysis_evaluation")
        self.assertEqual(stats["resolved_source"], "DatabaseCache")
        self.assertFalse(stats["fallback_used"])
        self.assertTrue(stats["execution_readiness"]["observation_only"])

    def test_sample_status_missing_cache_uses_explicit_missing_cache_state(self) -> None:
        service = BacktestService(self.db)

        status = service.get_sample_status(code="NO_CACHE")

        self.assertEqual(status["prepared_count"], 0)
        self.assertEqual(status["sample_readiness_state"], "missing_cache")
        self.assertIn("missing_cache", status["sample_blocking_reasons"])
        self.assertIn("provider_missing", status["sample_blocking_reasons"])
        self.assertEqual(status["execution_readiness"]["state"], "data_disabled")

    def test_sample_status_insufficient_cached_history_uses_explicit_state(self) -> None:
        with self.db.get_session() as session:
            session.add_all(
                [
                    StockDaily(code="SHORT", date=date(2024, 2, 1), open=10.0, high=10.1, low=9.9, close=10.0),
                    StockDaily(code="SHORT", date=date(2024, 2, 2), open=10.0, high=10.2, low=9.8, close=10.1),
                ]
            )
            session.commit()
        service = BacktestService(self.db)

        status = service.get_sample_status(code="SHORT")

        self.assertEqual(status["prepared_count"], 0)
        self.assertEqual(status["sample_readiness_state"], "insufficient_history")
        self.assertIn("insufficient_history", status["sample_blocking_reasons"])
        self.assertNotIn("missing_cache", status["sample_blocking_reasons"])
        self.assertEqual(status["execution_readiness"]["state"], "data_insufficient")

    def test_blocked_cached_sample_flow_does_not_fabricate_metrics(self) -> None:
        with self.db.get_session() as session:
            session.query(AnalysisHistory).delete()
            session.add(
                AnalysisHistory(
                    query_id="q-short-no-metrics",
                    code="SHORT",
                    name="SHORT",
                    report_type="simple",
                    sentiment_score=50,
                    operation_advice="rule_simulation_flat",
                    trend_prediction="rule_simulation_flat",
                    analysis_summary="short cached history",
                    created_at=datetime(2024, 1, 1, 0, 0, 0),
                    context_snapshot='{"enhanced_context": {"date": "2024-02-01"}}',
                )
            )
            session.add_all(
                [
                    StockDaily(code="SHORT", date=date(2024, 2, 1), open=10.0, high=10.1, low=9.9, close=10.0),
                    StockDaily(code="SHORT", date=date(2024, 2, 2), open=10.0, high=10.2, low=9.8, close=10.1),
                ]
            )
            session.commit()
        service = BacktestService(self.db)

        stats = service.run_backtest(code="SHORT", force=True, eval_window_days=3, min_age_days=0, limit=10)
        summary = service.get_summary(scope="stock", code="SHORT", eval_window_days=3)

        self.assertEqual(stats["completed"], 0)
        self.assertEqual(stats["insufficient"], 1)
        self.assertIsNotNone(summary)
        self.assertEqual(summary["completed_count"], 0)
        self.assertIsNone(summary["win_rate_pct"])
        self.assertIsNone(summary["direction_accuracy_pct"])
        self.assertIsNone(summary["avg_stock_return_pct"])
        self.assertIsNone(summary["avg_simulated_return_pct"])

    def _run_and_get_result(self) -> BacktestResult:
        """Helper: run backtest and return the single BacktestResult row."""
        service = BacktestService(self.db)
        service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)
        with self.db.get_session() as session:
            return session.query(BacktestResult).one()

    def test_result_fields_correct(self) -> None:
        """Verify BacktestResult row contains correct evaluation values."""
        result = self._run_and_get_result()

        self.assertEqual(result.eval_status, "completed")
        self.assertEqual(result.code, "600519")
        self.assertEqual(result.analysis_date, date(2024, 1, 1))
        self.assertEqual(result.operation_advice, "买入")
        self.assertEqual(result.position_recommendation, "long")
        self.assertEqual(result.direction_expected, "up")

        # Prices
        self.assertAlmostEqual(result.start_price, 100.0)
        self.assertAlmostEqual(result.end_close, 107.0)
        self.assertAlmostEqual(result.stock_return_pct, 7.0)

        # Direction & outcome
        self.assertEqual(result.outcome, "win")
        self.assertTrue(result.direction_correct)

        # Target hits -- day2 high=111 >= take_profit=110
        self.assertTrue(result.hit_take_profit)
        self.assertFalse(result.hit_stop_loss)
        self.assertEqual(result.first_hit, "take_profit")
        self.assertEqual(result.first_hit_trading_days, 1)
        self.assertEqual(result.first_hit_date, date(2024, 1, 2))

        # Simulated execution
        self.assertAlmostEqual(result.simulated_entry_price, 100.0)
        self.assertAlmostEqual(result.simulated_exit_price, 110.0)
        self.assertEqual(result.simulated_exit_reason, "take_profit")
        self.assertAlmostEqual(result.simulated_return_pct, 10.0)

    def test_summaries_created_after_run(self) -> None:
        """Verify both overall and per-stock BacktestSummary rows are created."""
        service = BacktestService(self.db)
        service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)

        with self.db.get_session() as session:
            # Overall summary uses sentinel code
            overall = session.query(BacktestSummary).filter(
                BacktestSummary.scope == "overall",
                BacktestSummary.code == OVERALL_SENTINEL_CODE,
            ).first()
            self.assertIsNotNone(overall)
            self.assertEqual(overall.total_evaluations, 1)
            self.assertEqual(overall.completed_count, 1)
            self.assertEqual(overall.win_count, 1)
            self.assertEqual(overall.loss_count, 0)
            self.assertAlmostEqual(overall.win_rate_pct, 100.0)

            # Stock-level summary
            stock = session.query(BacktestSummary).filter(
                BacktestSummary.scope == "stock",
                BacktestSummary.code == "600519",
            ).first()
            self.assertIsNotNone(stock)
            self.assertEqual(stock.total_evaluations, 1)
            self.assertEqual(stock.completed_count, 1)
            self.assertEqual(stock.win_count, 1)

    def test_get_summary_overall_returns_sentinel_as_none(self) -> None:
        """Verify get_summary translates __overall__ sentinel back to None."""
        service = BacktestService(self.db)
        service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)

        summary = service.get_summary(scope="overall", code=None)
        self.assertIsNotNone(summary)
        self.assertIsNone(summary["code"])
        self.assertEqual(summary["scope"], "overall")
        self.assertEqual(summary["win_count"], 1)

    def test_agent_learning_summary_helpers_keep_skill_rollups_neutral_until_supported(self) -> None:
        service = BacktestService(self.db)
        service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)

        global_summary = service.get_global_summary(eval_window_days=3)
        stock_summary = service.get_stock_summary("600519", eval_window_days=3)
        skill_summary = service.get_skill_summary("bull_trend", eval_window_days=3)
        strategy_summary = service.get_strategy_summary("bull_trend", eval_window_days=3)

        self.assertIsNotNone(global_summary)
        self.assertEqual(global_summary["total_evaluations"], 1)
        self.assertAlmostEqual(global_summary["win_rate"], 1.0)
        self.assertAlmostEqual(global_summary["direction_accuracy"], 1.0)
        self.assertAlmostEqual(global_summary["avg_return"], 0.10)

        self.assertIsNotNone(stock_summary)
        self.assertEqual(stock_summary["code"], "600519")
        self.assertAlmostEqual(stock_summary["win_rate"], 1.0)

        self.assertIsNone(skill_summary)
        self.assertIsNone(strategy_summary)

    def test_get_recent_evaluations(self) -> None:
        """Verify get_recent_evaluations returns correct paginated results."""
        service = BacktestService(self.db)
        service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)

        data = service.get_recent_evaluations(code="600519", limit=10, page=1)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["limit"], 10)
        self.assertEqual(len(data["items"]), 1)

        item = data["items"][0]
        self.assertEqual(item["code"], "600519")
        self.assertEqual(item["outcome"], "win")
        self.assertEqual(item["direction_expected"], "up")
        self.assertTrue(item["direction_correct"])
        self.assertEqual(item["evaluation_window_trading_bars"], 3)
        self.assertIn("execution_assumptions", item)

    def test_historical_source_metadata_fields_appear_in_contract(self) -> None:
        service = BacktestService(self.db)
        stats = service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)

        self.assertEqual(stats["requested_mode"], "auto")
        self.assertEqual(stats["resolved_source"], "DatabaseCache")
        self.assertFalse(stats["fallback_used"])
        self.assertIn("latest_prepared_sample_date", stats)
        self.assertIn("latest_eligible_sample_date", stats)
        self.assertIn("pricing_resolved_source", stats)
        self.assertIn("pricing_fallback_used", stats)

        history = service.list_backtest_runs(code="600519", page=1, limit=10)
        history_item = history["items"][0]
        self.assertEqual(history_item["requested_mode"], "auto")
        self.assertEqual(history_item["resolved_source"], "DatabaseCache")
        self.assertFalse(history_item["fallback_used"])

        summary = service.get_summary(scope="stock", code="600519", eval_window_days=3)
        self.assertIsNotNone(summary)
        self.assertEqual(summary["requested_mode"], "auto")
        self.assertEqual(summary["resolved_source"], "DatabaseCache")
        self.assertFalse(summary["fallback_used"])

    def test_get_sample_status_allows_zero_maturity_days_from_config(self) -> None:
        os.environ["BACKTEST_MIN_AGE_DAYS"] = "0"
        Config._instance = None

        service = BacktestService(self.db)
        status = service.get_sample_status(code="600519")

        self.assertEqual(status["min_age_days"], 0)
        self.assertEqual(status["maturity_calendar_days"], 0)
        self.assertEqual(status["requested_mode"], "auto")
        self.assertEqual(status["resolved_source"], "DatabaseCache")
        self.assertFalse(status["fallback_used"])

    def test_get_sample_status_without_code_returns_safe_aggregate(self) -> None:
        service = BacktestService(self.db)

        status = service.get_sample_status(code=None)

        self._history_fetch_mock.assert_not_called()
        self.assertEqual(status["code"], "__all__")
        self.assertEqual(status["scope"], "aggregate")
        self.assertEqual(status["sample_readiness_state"], "missing_cache")
        self.assertIn("provider_missing", status["sample_blocking_reasons"])
        self.assertEqual(
            status["probePolicy"],
            {
                "scope": "aggregate",
                "runtimeProbeMode": "disabled_by_default",
                "liveProviderProbingAllowed": False,
                "maxRuntimeProbeSymbols": 0,
                "evaluatedSymbols": len(status["symbolSpecificReadiness"]),
                "runtimeProbedSymbols": 0,
                "runtimeProbeSkippedSymbols": len(status["symbolSpecificReadiness"]),
                "runtimeProbeSkippedReason": "aggregate_side_effect_boundary",
                "readinessSources": ["existing_database_rows", "local_us_parquet_cache"],
                "consumerSafe": True,
            },
        )
        self.assertEqual(
            status["writePolicy"],
            {
                "scope": "aggregate",
                "mode": "read_only",
                "cacheWritesAllowed": False,
                "databaseWritesAllowed": False,
                "consumerSafe": True,
            },
        )
        readiness = status["historicalOhlcvReadiness"]
        self.assertEqual(readiness["providerState"], "missing_cache")
        self.assertEqual(readiness["overallState"], "missing_cache")
        self.assertFalse(readiness["probePolicy"]["liveProviderProbingAllowed"])
        self.assertFalse(readiness["writePolicy"]["databaseWritesAllowed"])
        self.assertEqual(readiness["requiredBars"], status["eval_window_days"])
        self.assertEqual(readiness["usableBars"], 0)
        self.assertEqual(
            readiness["missingBars"],
            status["eval_window_days"] * len(status["symbolSpecificReadiness"]),
        )
        self.assertTrue(
            all(item["runtimeProbeSkippedReason"] == "aggregate_side_effect_boundary" for item in status["symbolSpecificReadiness"])
        )

    def test_aggregate_sample_status_does_not_call_live_fallback_or_write_cache_by_default(self) -> None:
        service = BacktestService(self.db)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=89)
        frame = pd.DataFrame(
            [
                {
                    "date": (start_date + timedelta(days=index)).isoformat(),
                    "open": 200.0 + index,
                    "high": 201.0 + index,
                    "low": 199.0 + index,
                    "close": 200.5 + index,
                    "volume": 1_000_000 + index,
                }
                for index in range(90)
            ]
        )

        def unsafe_fetch(*args, **_kwargs):
            symbol = str(args[0] or "").upper()
            self.db.save_daily_data(frame, code=symbol, data_source="YfinanceFetcher")
            return frame, "YfinanceFetcher"

        with patch.dict(
            os.environ,
            {
                "LOCAL_US_PARQUET_DIR": self._temp_dir.name,
                "US_STOCK_PARQUET_DIR": "",
                "WOLFYSTOCK_US_OHLCV_TIER1_SYMBOLS": "TSLA,AAPL",
            },
            clear=False,
        ), patch(
            "src.services.backtest_service.fetch_daily_history_with_local_us_fallback",
            side_effect=unsafe_fetch,
        ) as fetch_mock:
            status = service.get_sample_status(code=None)

        fetch_mock.assert_not_called()
        with self.db.get_session() as session:
            persisted_symbols = {
                row[0]
                for row in session.query(StockDaily.code)
                .filter(StockDaily.code.in_(["TSLA", "AAPL"]))
                .all()
            }
        self.assertEqual(persisted_symbols, set())
        self.assertEqual([item["symbol"] for item in status["symbolSpecificReadiness"]], ["TSLA", "AAPL"])
        self.assertEqual(status["historicalOhlcvReadiness"]["overallState"], "missing_cache")
        self.assertEqual(status["productReadModel"]["contractVersion"], "product_read_model_v1")
        self.assertEqual(status["productReadModel"]["surface"], "Backtest readiness")
        self.assertEqual(status["productReadModel"]["state"], "no_evidence")
        self.assertFalse(status["productReadModel"]["ready"])
        self.assertTrue(status["productReadModel"]["readOnly"])
        self.assertFalse(status["productReadModel"]["backtestExecuted"])
        self.assertEqual(status["productReadModel"]["provenance"]["sourceClass"], "historical_market_data")
        self.assertFalse(status["probePolicy"]["liveProviderProbingAllowed"])
        self.assertFalse(status["writePolicy"]["cacheWritesAllowed"])

    def test_aggregate_sample_status_does_not_invoke_us_ohlcv_refresh_control(self) -> None:
        service = BacktestService(self.db)

        with patch(
            "src.services.us_ohlcv_cache_refresh.UsOhlcvCacheRefreshService.refresh",
            side_effect=AssertionError("refresh control called"),
        ) as refresh_mock:
            status = service.get_sample_status(code=None)

        refresh_mock.assert_not_called()
        self._history_fetch_mock.assert_not_called()
        self.assertEqual(status["code"], "__all__")
        self.assertEqual(status["scope"], "aggregate")
        self.assertFalse(status["probePolicy"]["liveProviderProbingAllowed"])
        self.assertFalse(status["writePolicy"]["cacheWritesAllowed"])
        self.assertFalse(status["writePolicy"]["databaseWritesAllowed"])

    def test_aggregate_sample_status_exposes_local_symbol_readiness_without_masking(self) -> None:
        for symbol in ("SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"):
            self._write_local_us_parquet(self._temp_dir.name, symbol, rows=90)
        service = BacktestService(self.db)

        with patch.dict(
            os.environ,
            {
                "LOCAL_US_PARQUET_DIR": self._temp_dir.name,
                "US_STOCK_PARQUET_DIR": "",
            },
            clear=False,
        ), patch("src.services.us_history_helper.DataFetcherManager") as manager_cls:
            aggregate = service.get_sample_status(code=None)
            spy = service.get_sample_status(code="SPY")
            aapl = service.get_sample_status(code="AAPL")

        manager_cls.assert_not_called()
        self.assertEqual(aggregate["code"], "__all__")
        self.assertEqual(aggregate["scope"], "aggregate")
        self.assertEqual(aggregate["sample_readiness_state"], "no_samples")
        symbol_readiness = aggregate["symbolSpecificReadiness"]
        self.assertEqual([item["symbol"] for item in symbol_readiness], ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"])
        self.assertTrue(all(item["historicalOhlcvState"] == "ready" for item in symbol_readiness))
        self.assertTrue(all(item["providerState"] == "available" for item in symbol_readiness))
        self.assertEqual(spy["historicalOhlcvReadiness"]["providerState"], "available")
        self.assertEqual(aapl["historicalOhlcvReadiness"]["providerState"], "available")
        self.assertEqual(aggregate["historicalOhlcvReadiness"]["providerState"], "available")
        self.assertEqual(aggregate["historicalOhlcvReadiness"]["overallState"], "all_available")
        self.assertEqual(aggregate["productReadModel"]["contractVersion"], "product_read_model_v1")
        self.assertEqual(aggregate["productReadModel"]["surface"], "Backtest readiness")
        self.assertEqual(aggregate["productReadModel"]["state"], "pending")
        self.assertFalse(aggregate["productReadModel"]["ready"])
        self.assertEqual(aggregate["productReadModel"]["quality"]["state"], "pending")
        self.assertIn("samples_initializing", aggregate["productReadModel"]["quality"]["missingDataClasses"])
        self.assertEqual(aggregate["productReadModel"]["evidence"]["preparedCount"], 0)
        self.assertEqual(aggregate["productReadModel"]["evidence"]["transition"], "initializing")
        self.assertEqual(aggregate["resolved_source"], "LocalParquet")
        self.assertNotIn("provider_missing", aggregate["sample_blocking_reasons"])

    def test_aggregate_ready_sample_status_does_not_emit_stale_missing_adjustments(self) -> None:
        self._insert_backtest_sample(code="TSLA")
        for symbol in ("TSLA", "NVDA"):
            self._write_local_us_parquet(self._temp_dir.name, symbol, rows=90)
        service = BacktestService(self.db)

        with patch.dict(
            os.environ,
            {
                "LOCAL_US_PARQUET_DIR": self._temp_dir.name,
                "US_STOCK_PARQUET_DIR": "",
                "WOLFYSTOCK_US_OHLCV_TIER1_SYMBOLS": "TSLA,NVDA",
            },
            clear=False,
        ), patch("src.services.us_history_helper.DataFetcherManager") as manager_cls:
            aggregate = service.get_sample_status(code=None)
            tsla = service.get_sample_status(code="TSLA")

        manager_cls.assert_not_called()
        self._history_fetch_mock.assert_not_called()
        self.assertEqual(aggregate["sample_readiness_state"], "ready")
        readiness = aggregate["historicalOhlcvReadiness"]
        self.assertEqual(readiness["overallState"], "all_available")
        self.assertEqual(readiness["providerState"], "available")
        self.assertEqual(readiness["missingRequirements"], [])
        self.assertEqual(readiness["adjustmentState"], "not_required")
        self.assertFalse(
            any(
                "missing_adjustments" in item["missingRequirements"]
                for item in aggregate["symbolSpecificReadiness"]
            )
        )
        self.assertEqual(aggregate["execution_readiness"]["state"], "executable")
        self.assertNotIn("missing_adjustments", aggregate["execution_readiness"]["reason_codes"])
        self.assertFalse(aggregate["probePolicy"]["liveProviderProbingAllowed"])
        self.assertFalse(aggregate["writePolicy"]["cacheWritesAllowed"])
        self.assertFalse(aggregate["writePolicy"]["databaseWritesAllowed"])
        self.assertEqual(aggregate["probePolicy"]["runtimeProbedSymbols"], 0)
        self.assertEqual(tsla["sample_readiness_state"], "ready")
        self.assertEqual(tsla["execution_readiness"]["state"], "executable")

    def test_aggregate_sample_status_preserves_true_missing_adjustments(self) -> None:
        self._insert_backtest_sample(code="AAPL")
        service = BacktestService(self.db)

        def fake_readiness(*, code, required_bars, **_):
            return (
                {
                    "overallState": "degraded",
                    "providerState": "available",
                    "runtimeStatus": "available",
                    "usableBars": required_bars,
                    "missingBars": 0,
                    "missingRequirements": ["missing_adjustments"],
                },
                service._build_source_metadata_from_fetch_source(code=code, source="local_us_parquet"),
            )

        with patch.dict(
            os.environ,
            {
                "WOLFYSTOCK_US_OHLCV_TIER1_SYMBOLS": "AAPL",
            },
            clear=False,
        ), patch.object(
            service,
            "_build_historical_ohlcv_readiness_with_metadata",
            side_effect=fake_readiness,
        ):
            aggregate = service.get_sample_status(code=None)

        self.assertEqual(aggregate["historicalOhlcvReadiness"]["adjustmentState"], "missing")
        self.assertIn("missing_adjustments", aggregate["historicalOhlcvReadiness"]["missingRequirements"])
        self.assertIn("missing_adjustments", aggregate["sample_blocking_reasons"])
        self.assertIn("missing_adjustments", aggregate["execution_readiness"]["reason_codes"])

    def test_sample_status_uses_runtime_truth_without_preparing_backtest_samples(self) -> None:
        service = BacktestService(self.db)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=89)
        frame = pd.DataFrame(
            [
                {
                    "date": (start_date + timedelta(days=index)).isoformat(),
                    "open": 200.0 + index,
                    "high": 201.0 + index,
                    "low": 199.0 + index,
                    "close": 200.5 + index,
                    "volume": 1_000_000 + index,
                }
                for index in range(90)
            ]
        )

        with patch(
            "src.services.backtest_service.fetch_daily_history_with_local_us_fallback",
            return_value=(frame, "AlpacaFetcher"),
        ) as fetch_mock, patch.object(
            service,
            "_ensure_market_history",
        ) as ensure_market_history, patch.object(
            service,
            "_ensure_cached_backtest_samples",
        ) as ensure_cached_samples:
            status = service.get_sample_status(code="TSLA")

        fetch_mock.assert_called_once()
        self.assertEqual(fetch_mock.call_args.args, ("TSLA",))
        self.assertEqual(fetch_mock.call_args.kwargs["days"], 3)
        self.assertTrue(fetch_mock.call_args.kwargs["allow_provider_fallback"])
        ensure_market_history.assert_not_called()
        ensure_cached_samples.assert_not_called()
        with self.db.get_session() as session:
            self.assertEqual(session.query(StockDaily).filter(StockDaily.code == "TSLA").count(), 0)
            self.assertEqual(session.query(AnalysisHistory).filter(AnalysisHistory.code == "TSLA").count(), 0)
        self.assertEqual(status["prepared_count"], 0)
        self.assertEqual(status["sample_readiness_state"], "no_samples")
        self.assertFalse(status["execution_readiness"]["result_contract_available"])
        self.assertEqual(status["resolved_source"], "AlpacaFetcher")
        self.assertEqual(status["historicalOhlcvReadiness"]["providerState"], "available")
        self.assertEqual(status["historicalOhlcvReadiness"]["missingBars"], 0)
        self.assertNotIn("provider_missing", status["sample_blocking_reasons"])
        self.assertEqual(status["probePolicy"]["runtimeProbeMode"], "bounded_provider_observation")
        self.assertTrue(status["probePolicy"]["liveProviderProbingAllowed"])
        self.assertFalse(status["probePolicy"]["activeHydrationAllowed"])
        self.assertFalse(status["writePolicy"]["cacheWritesAllowed"])
        self.assertFalse(status["writePolicy"]["databaseWritesAllowed"])

    def test_aggregate_sample_status_uses_configured_tier1_truth_without_collapsing_to_provider_missing(self) -> None:
        service = BacktestService(self.db)

        def fake_readiness(*, code, rows, required_bars, **_):
            if code == "NVDA":
                return (
                    {
                        "overallState": "ready",
                        "providerState": "available",
                        "runtimeStatus": "available",
                        "usableBars": required_bars,
                        "missingBars": 0,
                        "missingRequirements": [],
                    },
                    service._build_source_metadata_from_fetch_source(code=code, source="local_us_parquet"),
                )
            if code == "AAPL":
                return (
                    {
                        "overallState": "ready",
                        "providerState": "available",
                        "runtimeStatus": "available",
                        "usableBars": required_bars + 30,
                        "missingBars": 0,
                        "missingRequirements": [],
                    },
                    service._build_source_metadata_from_fetch_source(code=code, source="AlpacaFetcher"),
                )
            return (
                {
                    "overallState": "blocked",
                    "providerState": "provider_missing",
                    "runtimeStatus": "missing",
                    "usableBars": 0,
                    "missingBars": required_bars,
                    "missingRequirements": ["provider_missing", "insufficient_history"],
                },
                service._build_source_metadata_from_fetch_source(code=code, source=None),
            )

        with patch.dict(
            os.environ,
            {
                "LOCAL_US_PARQUET_DIR": self._temp_dir.name,
                "US_STOCK_PARQUET_DIR": "",
                "WOLFYSTOCK_US_OHLCV_TIER1_SYMBOLS": "NVDA,AAPL,PLTR",
            },
            clear=False,
        ), patch.object(
            service,
            "_build_historical_ohlcv_readiness_with_metadata",
            side_effect=fake_readiness,
        ) as readiness_mock:
            aggregate = service.get_sample_status(code=None)

        self.assertEqual(
            [call.kwargs["code"] for call in readiness_mock.call_args_list],
            ["NVDA", "AAPL", "PLTR"],
        )
        self.assertTrue(all(call.kwargs["allow_runtime_probe"] is False for call in readiness_mock.call_args_list))
        symbol_readiness = aggregate["symbolSpecificReadiness"]
        self.assertEqual([item["symbol"] for item in symbol_readiness], ["NVDA", "AAPL", "PLTR"])
        self.assertEqual(
            {item["symbol"]: item["historicalOhlcvState"] for item in symbol_readiness},
            {
                "NVDA": "ready",
                "AAPL": "ready",
                "PLTR": "missing_cache",
            },
        )
        self.assertEqual(aggregate["historicalOhlcvReadiness"]["overallState"], "partial")
        self.assertEqual(aggregate["historicalOhlcvReadiness"]["providerState"], "partial")
        self.assertIn("PLTR", aggregate["historicalOhlcvReadiness"]["missingCacheSymbols"])
        self.assertEqual(symbol_readiness[1]["resolvedSource"], "AlpacaFetcher")
        self.assertNotEqual(aggregate["historicalOhlcvReadiness"]["providerState"], "provider_missing")

    def test_run_history_is_recorded_and_results_can_be_reopened(self) -> None:
        service = BacktestService(self.db)
        stats = service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)

        self.assertIsNotNone(stats["run_id"])
        self.assertEqual(self._count_runs(), 1)
        self.assertEqual(stats["evaluation_mode"], "historical_analysis_evaluation")
        self.assertEqual(stats["evaluation_window_trading_bars"], 3)
        self.assertEqual(stats["maturity_calendar_days"], 0)
        self.assertIn("execution_assumptions", stats)

        history = service.list_backtest_runs(code="600519", page=1, limit=10)
        self.assertEqual(history["total"], 1)
        item = history["items"][0]
        self.assertEqual(item["code"], "600519")
        self.assertEqual(item["candidate_count"], 1)
        self.assertGreaterEqual(item["win_rate_pct"], 0)
        self.assertEqual(item["evaluation_mode"], "historical_analysis_evaluation")
        self.assertEqual(item["evaluation_window_trading_bars"], 3)
        self.assertEqual(item["maturity_calendar_days"], 0)

        run_results = service.get_run_results(run_id=item["id"], page=1, limit=10)
        self.assertEqual(run_results["total"], 1)
        self.assertEqual(run_results["items"][0]["code"], "600519")

    def test_run_with_only_recent_analysis_reports_insufficient_history_reason(self) -> None:
        recent_created_at = datetime.now() - timedelta(days=1)
        with self.db.get_session() as session:
            session.add(
                AnalysisHistory(
                    query_id="q-recent",
                    code="000001",
                    name="平安银行",
                    report_type="simple",
                    sentiment_score=55,
                    operation_advice="持有",
                    trend_prediction="震荡",
                    analysis_summary="recent",
                    stop_loss=9.5,
                    take_profit=11.0,
                    created_at=recent_created_at,
                    context_snapshot='{"enhanced_context": {"date": "' + recent_created_at.strftime('%Y-%m-%d') + '"}}',
                )
            )
            session.commit()

        service = BacktestService(self.db)
        stats = service.run_backtest(code="000001", force=False, eval_window_days=3, limit=10)

        self.assertEqual(stats["processed"], 0)
        self.assertEqual(stats["saved"], 0)
        self.assertEqual(stats["candidate_count"], 0)
        self.assertEqual(stats["no_result_reason"], "insufficient_historical_data")
        self.assertIn("14 天", stats["no_result_message"])

    def test_prepare_backtest_samples_populates_analysis_history_and_enables_run(self) -> None:
        with self.db.get_session() as session:
            session.add_all([
                StockDaily(code="000001", date=date(2024, 1, 1), open=10.0, high=10.2, low=9.8, close=10.0),
                StockDaily(code="000001", date=date(2024, 1, 2), open=10.1, high=10.8, low=10.0, close=10.6),
                StockDaily(code="000001", date=date(2024, 1, 3), open=10.6, high=10.7, low=10.2, close=10.3),
                StockDaily(code="000001", date=date(2024, 1, 4), open=10.3, high=10.6, low=10.1, close=10.5),
                StockDaily(code="000001", date=date(2024, 1, 5), open=10.5, high=10.9, low=10.4, close=10.8),
                StockDaily(code="000001", date=date(2024, 1, 8), open=10.8, high=11.1, low=10.7, close=11.0),
                StockDaily(code="000001", date=date(2024, 1, 9), open=11.0, high=11.3, low=10.9, close=11.2),
                StockDaily(code="000001", date=date(2024, 1, 10), open=11.2, high=11.4, low=11.0, close=11.1),
                StockDaily(code="000001", date=date(2024, 1, 11), open=11.1, high=11.5, low=11.0, close=11.4),
                StockDaily(code="000001", date=date(2024, 1, 12), open=11.4, high=11.7, low=11.2, close=11.6),
                StockDaily(code="000001", date=date(2024, 1, 15), open=11.6, high=11.8, low=11.3, close=11.5),
                StockDaily(code="000001", date=date(2024, 1, 16), open=11.5, high=11.9, low=11.4, close=11.8),
                StockDaily(code="000001", date=date(2024, 1, 17), open=11.8, high=12.0, low=11.6, close=11.7),
                StockDaily(code="000001", date=date(2024, 1, 18), open=11.7, high=12.2, low=11.6, close=12.1),
                StockDaily(code="000001", date=date(2024, 1, 19), open=12.1, high=12.4, low=12.0, close=12.3),
            ])
            session.commit()

        service = BacktestService(self.db)
        prep = service.prepare_backtest_samples(code="000001", sample_count=252, eval_window_days=3, min_age_days=14)
        self.assertGreater(prep["prepared"], 0)
        self.assertEqual(prep["sample_count"], 252)

        with self.db.get_session() as session:
            prepared_count = session.query(AnalysisHistory).filter(AnalysisHistory.code == "000001").count()
            self.assertGreater(prepared_count, 0)

        status = service.get_sample_status(code="000001")
        self.assertGreater(status["prepared_count"], 0)
        self.assertIsNotNone(status["prepared_start_date"])
        self.assertIsNotNone(status["prepared_end_date"])

        stats = service.run_backtest(code="000001", force=False, eval_window_days=3, min_age_days=14, limit=10)
        self.assertGreater(stats["saved"], 0)
        self.assertGreater(stats["completed"], 0)

        recent = service.get_recent_evaluations(code="000001", eval_window_days=3, limit=10, page=1)
        self.assertGreater(recent["total"], 0)

    def test_prepare_samples_reports_local_first_source_metadata_on_local_hit(self) -> None:
        frame = pd.DataFrame(
            [
                {"date": "2024-01-01", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 10},
                {"date": "2024-01-02", "open": 101.0, "high": 102.0, "low": 100.0, "close": 101.0, "volume": 10},
                {"date": "2024-01-03", "open": 102.0, "high": 103.0, "low": 101.0, "close": 102.0, "volume": 10},
                {"date": "2024-01-04", "open": 103.0, "high": 104.0, "low": 102.0, "close": 103.0, "volume": 10},
                {"date": "2024-01-05", "open": 104.0, "high": 105.0, "low": 103.0, "close": 104.0, "volume": 10},
                {"date": "2024-01-08", "open": 105.0, "high": 106.0, "low": 104.0, "close": 105.0, "volume": 10},
                {"date": "2024-01-09", "open": 106.0, "high": 107.0, "low": 105.0, "close": 106.0, "volume": 10},
            ]
        )
        service = BacktestService(self.db)

        with patch("src.services.backtest_service.fetch_daily_history_with_local_us_fallback", return_value=(frame, "local_us_parquet")) as fetch_mock:
            prep = service.prepare_backtest_samples(code="AAPL", sample_count=2, eval_window_days=3, min_age_days=14)

        self.assertEqual(prep["requested_mode"], "local_first")
        self.assertEqual(prep["resolved_source"], "LocalParquet")
        self.assertFalse(prep["fallback_used"])
        self.assertEqual(prep["latest_prepared_sample_date"], "2024-01-04")
        self.assertEqual(prep["latest_eligible_sample_date"], "2024-01-04")
        self.assertEqual(prep["excluded_recent_reason"], "evaluation_window_not_satisfied")
        self.assertEqual(prep["pricing_resolved_source"], "LocalParquet")
        self.assertFalse(prep["pricing_fallback_used"])

        status = service.get_sample_status(code="AAPL")
        self.assertEqual(status["latest_prepared_sample_date"], "2024-01-04")
        self.assertEqual(status["latest_eligible_sample_date"], "2024-01-04")
        self.assertEqual(status["excluded_recent_reason"], "evaluation_window_not_satisfied")
        self.assertEqual(status["pricing_resolved_source"], "LocalParquet")
        self.assertFalse(status["pricing_fallback_used"])
        self.assertEqual(fetch_mock.call_args.kwargs["allow_provider_fallback"], False)

    def test_prepare_samples_surfaces_missing_us_history_without_provider_fallback(self) -> None:
        service = BacktestService(self.db)

        with patch("src.services.backtest_service.fetch_daily_history_with_local_us_fallback", return_value=(None, None)) as fetch_mock:
            prep = service.prepare_backtest_samples(code="AAPL", sample_count=2, eval_window_days=3, min_age_days=14)

        self.assertEqual(prep["requested_mode"], "local_first")
        self.assertEqual(prep["resolved_source"], "Unknown")
        self.assertFalse(prep["fallback_used"])
        self.assertEqual(prep["prepared"], 0)
        self.assertEqual(prep["market_rows_saved"], 0)
        self.assertEqual(prep["candidate_rows"], 0)
        self.assertEqual(prep["no_result_reason"], "missing_market_history")
        self.assertEqual(fetch_mock.call_args.kwargs["allow_provider_fallback"], False)

    def test_run_backtest_fetches_missing_us_history_via_shared_local_first_helper(self) -> None:
        with self.db.get_session() as session:
            session.add(
                AnalysisHistory(
                    query_id="q-aapl-runtime-fill",
                    code="AAPL",
                    name="Apple",
                    report_type="simple",
                    sentiment_score=80,
                    operation_advice="买入",
                    trend_prediction="看多",
                    analysis_summary="test",
                    stop_loss=95.0,
                    take_profit=110.0,
                    created_at=datetime(2024, 1, 1, 0, 0, 0),
                    context_snapshot='{"enhanced_context": {"date": "2024-01-01"}}',
                )
            )
            session.commit()

        frame = pd.DataFrame(
            [
                {"date": "2024-01-01", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 10},
                {"date": "2024-01-02", "open": 101.0, "high": 111.0, "low": 100.0, "close": 105.0, "volume": 10},
                {"date": "2024-01-03", "open": 105.0, "high": 108.0, "low": 103.0, "close": 106.0, "volume": 10},
                {"date": "2024-01-04", "open": 106.0, "high": 109.0, "low": 104.0, "close": 107.0, "volume": 10},
            ]
        )
        service = BacktestService(self.db)

        with patch("src.services.backtest_service.fetch_daily_history_with_local_us_fallback", return_value=(frame, "local_us_parquet")) as fetch_mock:
            stats = service.run_backtest(code="AAPL", force=False, eval_window_days=3, min_age_days=0, limit=10)

        self.assertEqual(stats["saved"], 1)
        self.assertEqual(stats["completed"], 1)
        fetch_mock.assert_called_once_with(
            "AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            days=6,
            log_context="[historical-eval fill]",
            allow_provider_fallback=False,
        )

        with self.db.get_session() as session:
            result = session.query(BacktestResult).filter(BacktestResult.code == "AAPL").one()
            daily_rows = session.query(StockDaily).filter(StockDaily.code == "AAPL").order_by(StockDaily.date).all()

        self.assertEqual(result.eval_status, "completed")
        self.assertEqual([row.date.isoformat() for row in daily_rows], ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"])

        recent = service.get_recent_evaluations(code="AAPL", eval_window_days=3, limit=10, page=1)
        data_quality = recent["items"][0]["data_quality"]
        self.assertEqual(data_quality["source"], "local_us_parquet")
        self.assertEqual(data_quality["authority_status"], "allowed")
        self.assertEqual(data_quality["authority_source_type"], "cache_snapshot")
        self.assertEqual(data_quality["authority_reason_codes"], [])

    def test_run_backtest_missing_us_history_does_not_invoke_provider_fallback(self) -> None:
        with self.db.get_session() as session:
            session.add(
                AnalysisHistory(
                    query_id="q-aapl-local-only-missing",
                    code="AAPL",
                    name="Apple",
                    report_type="simple",
                    sentiment_score=80,
                    operation_advice="买入",
                    trend_prediction="看多",
                    analysis_summary="test",
                    stop_loss=95.0,
                    take_profit=110.0,
                    created_at=datetime(2024, 1, 1, 0, 0, 0),
                    context_snapshot='{"enhanced_context": {"date": "2024-01-01"}}',
                )
            )
            session.commit()

        self._allow_history_fetch()
        service = BacktestService(self.db)

        with patch.dict(
            os.environ,
            {
                "LOCAL_US_PARQUET_DIR": self._temp_dir.name,
                "US_STOCK_PARQUET_DIR": self._temp_dir.name,
            },
            clear=False,
        ), patch("src.services.us_history_helper.DataFetcherManager") as manager_cls:
            stats = service.run_backtest(code="AAPL", force=False, eval_window_days=3, min_age_days=0, limit=10)

        manager_cls.assert_not_called()
        self.assertEqual(stats["processed"], 1)
        self.assertEqual(stats["completed"], 0)
        self.assertEqual(stats["insufficient"], 1)
        self.assertFalse(stats["fallback_used"])
        self.assertEqual(stats["data_status"], "data_unavailable")
        self.assertEqual(stats["calculation_status"], "insufficient_sample")
        self.assertEqual(stats["sample_status"], "insufficient_sample")
        self.assertTrue(stats["limitations"])
        self.assertIn("Research diagnostic only", stats["no_advice_disclosure"])

        with self.db.get_session() as session:
            daily_rows = session.query(StockDaily).filter(StockDaily.code == "AAPL").all()
            result = session.query(BacktestResult).filter(BacktestResult.code == "AAPL").one()

        self.assertEqual(daily_rows, [])
        self.assertEqual(result.stock_return_pct, None)

        recent = service.get_recent_evaluations(code="AAPL", eval_window_days=3, limit=10, page=1)
        item = recent["items"][0]
        self.assertEqual(item["eval_status"], "insufficient_data")
        self.assertEqual(item["data_status"], "provider_missing")
        self.assertEqual(item["calculation_status"], "calculation_unavailable")
        self.assertEqual(item["sample_status"], "provider_missing")
        self.assertIsNone(item["stock_return_pct"])
        self.assertIsNone(item["simulated_return_pct"])
        self.assertIn("Research diagnostic only", item["no_advice_disclosure"])

    def test_sample_status_reports_maturity_window_exclusion_for_recent_samples(self) -> None:
        recent_created_at = datetime.now() - timedelta(days=2)
        old_created_at = datetime.now() - timedelta(days=20)
        with self.db.get_session() as session:
            session.add_all([
                AnalysisHistory(
                    query_id="bt-sample:000001:2024-03-01:w3",
                    code="000001",
                    name="平安银行",
                    report_type="backtest_sample",
                    sentiment_score=60,
                    operation_advice="买入",
                    trend_prediction="看多",
                    analysis_summary="old",
                    raw_result='{"market_data_source":"db_cache"}',
                    context_snapshot='{"enhanced_context": {"date": "2024-03-01"}}',
                    created_at=old_created_at,
                ),
                AnalysisHistory(
                    query_id="bt-sample:000001:2024-03-20:w3",
                    code="000001",
                    name="平安银行",
                    report_type="backtest_sample",
                    sentiment_score=60,
                    operation_advice="买入",
                    trend_prediction="看多",
                    analysis_summary="recent",
                    raw_result='{"market_data_source":"db_cache"}',
                    context_snapshot='{"enhanced_context": {"date": "2024-03-20"}}',
                    created_at=recent_created_at,
                ),
            ])
            session.commit()

        service = BacktestService(self.db)
        status = service.get_sample_status(code="000001")

        self.assertEqual(status["latest_prepared_sample_date"], "2024-03-20")
        self.assertEqual(status["latest_eligible_sample_date"], "2024-03-01")
        self.assertEqual(status["excluded_recent_reason"], "maturity_window_not_satisfied")
        self.assertIn("成熟期", status["excluded_recent_message"])

    def test_clear_samples_and_results_separate_reset_paths(self) -> None:
        with self.db.get_session() as session:
            session.add_all(
                [
                    StockDaily(
                        code="600519",
                        date=date(2024, 1, 5) + timedelta(days=index),
                        open=108.0 + index,
                        high=109.0 + index,
                        low=107.0 + index,
                        close=108.5 + index,
                        data_source="DatabaseCache",
                    )
                    for index in range(20)
                ]
            )
            session.commit()

        service = BacktestService(self.db)
        service.prepare_backtest_samples(code="600519", sample_count=60, eval_window_days=3, min_age_days=14)
        service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=14, limit=10)
        self.assertGreater(self._count_results(), 0)
        self.assertEqual(self._count_runs(), 1)

        cleared_results = service.clear_backtest_results(code="600519")
        self.assertGreaterEqual(cleared_results["deleted_results"], 1)
        self.assertEqual(cleared_results["deleted_samples"], 0)
        self.assertEqual(self._count_runs(), 0)
        self.assertEqual(self._count_results(), 0)

        status_after_results_clear = service.get_sample_status(code="600519")
        self.assertGreater(status_after_results_clear["prepared_count"], 0)

        cleared_samples = service.clear_backtest_samples(code="600519")
        self.assertGreaterEqual(cleared_samples["deleted_samples"], 1)
        self.assertEqual(self._count_runs(), 0)
        self.assertEqual(self._count_results(), 0)
        status_after_samples_clear = service.get_sample_status(code="600519")
        self.assertEqual(status_after_samples_clear["prepared_count"], 0)

    def test_multi_stock_summaries(self) -> None:
        """Verify separate summaries for multiple stocks + correct overall aggregate."""
        old_created_at = datetime(2024, 1, 1, 0, 0, 0)

        with self.db.get_session() as session:
            # Second stock with sell advice -- price drops (win for cash/down)
            session.add(
                AnalysisHistory(
                    query_id="q2",
                    code="000001",
                    name="平安银行",
                    report_type="simple",
                    sentiment_score=30,
                    operation_advice="卖出",
                    trend_prediction="看空",
                    analysis_summary="test2",
                    stop_loss=None,
                    take_profit=None,
                    created_at=old_created_at,
                    context_snapshot='{"enhanced_context": {"date": "2024-01-01"}}',
                )
            )
            session.add(
                StockDaily(code="000001", date=date(2024, 1, 1), open=10.0, high=10.2, low=9.8, close=10.0)
            )
            session.add_all([
                StockDaily(code="000001", date=date(2024, 1, 2), high=10.0, low=9.5, close=9.6),
                StockDaily(code="000001", date=date(2024, 1, 3), high=9.7, low=9.3, close=9.4),
                StockDaily(code="000001", date=date(2024, 1, 4), high=9.5, low=9.0, close=9.1),
            ])
            session.commit()

        service = BacktestService(self.db)
        stats = service.run_backtest(code=None, force=False, eval_window_days=3, min_age_days=0, limit=10)
        self.assertEqual(stats["saved"], 2)
        self.assertEqual(stats["completed"], 2)

        with self.db.get_session() as session:
            # Each stock has its own summary
            s1 = session.query(BacktestSummary).filter(
                BacktestSummary.scope == "stock", BacktestSummary.code == "600519"
            ).first()
            s2 = session.query(BacktestSummary).filter(
                BacktestSummary.scope == "stock", BacktestSummary.code == "000001"
            ).first()
            self.assertIsNotNone(s1)
            self.assertIsNotNone(s2)
            self.assertEqual(s1.win_count, 1)
            self.assertEqual(s2.win_count, 1)

            # Overall aggregates both
            overall = session.query(BacktestSummary).filter(
                BacktestSummary.scope == "overall",
                BacktestSummary.code == OVERALL_SENTINEL_CODE,
            ).first()
            self.assertIsNotNone(overall)
            self.assertEqual(overall.total_evaluations, 2)
            self.assertEqual(overall.completed_count, 2)
            self.assertEqual(overall.win_count, 2)


if __name__ == "__main__":
    unittest.main()
