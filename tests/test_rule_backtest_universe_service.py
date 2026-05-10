# -*- coding: utf-8 -*-
"""Tests for local-only rule backtest universe job scaffolding."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from src.config import Config
from src.services.rule_backtest_service import RuleBacktestService
from src.storage import DatabaseManager, StockDaily


class RuleBacktestUniverseServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_rule_backtest_universe.db")
        os.environ["DATABASE_PATH"] = self._db_path
        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self._temp_dir.cleanup()

    def _seed_history(self, code: str, closes: list[float], *, start: date = date(2025, 1, 1)) -> None:
        with self.db.get_session() as session:
            for index, close in enumerate(closes):
                session.add(
                    StockDaily(
                        code=code,
                        date=start + timedelta(days=index),
                        open=float(close) - 0.1,
                        high=float(close) + 0.2,
                        low=max(0.01, float(close) - 0.3),
                        close=float(close),
                    )
                )
            session.commit()

    def _ma_strategy(self) -> dict:
        return {
            "version": "v1",
            "timeframe": "daily",
            "source_text": "5日均线上穿20日均线买入，下穿卖出",
            "normalized_text": "5日均线上穿20日均线买入，下穿卖出",
            "entry": {"indicator": "ma_crossover", "direction": "above", "fast_period": 5, "slow_period": 20},
            "exit": {"indicator": "ma_crossover", "direction": "below", "fast_period": 5, "slow_period": 20},
            "confidence": 1.0,
            "needs_confirmation": False,
            "ambiguities": [],
            "summary": {
                "entry": "买入条件：SMA5 上穿 SMA20",
                "exit": "卖出条件：SMA5 下穿 SMA20",
                "strategy": "均线交叉策略",
            },
            "max_lookback": 20,
            "strategy_kind": "moving_average_crossover",
            "setup": {"fast_period": 5, "slow_period": 20, "fast_type": "simple", "slow_type": "simple"},
            "strategy_spec": {
                "strategy_type": "moving_average_crossover",
                "timeframe": "daily",
                "signal": {
                    "indicator_family": "moving_average",
                    "fast_period": 5,
                    "slow_period": 20,
                    "fast_type": "simple",
                    "slow_type": "simple",
                    "entry_condition": "fast_crosses_above_slow",
                    "exit_condition": "fast_crosses_below_slow",
                },
            },
            "executable": True,
            "normalization_state": "ready",
            "detected_strategy_family": "moving_average_crossover",
            "interpretation_confidence": 1.0,
        }

    def test_create_universe_job_prefights_local_data_only_with_deterministic_ordering(self) -> None:
        self._seed_history("AAPL", [10.0, 10.2, 10.4, 10.6, 10.8])
        self._seed_history("MSFT", [20.0, 20.2, 20.4, 20.6, 20.8])
        service = RuleBacktestService(self.db)

        with patch.object(RuleBacktestService, "_ensure_market_history") as ensure_mock, patch(
            "src.services.rule_backtest_service.fetch_daily_history_with_local_us_fallback"
        ) as fetch_mock:
            job = service.create_universe_job(
                symbols=["msft", "AAPL", "AAPL", "ZZZ"],
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2025-01-01",
                end_date="2025-01-05",
                request_label="local preflight",
            )

        self.assertEqual(job["symbol_count"], 3)
        self.assertEqual(job["status"], "completed_with_failures")
        self.assertEqual(job["completed_count"], 2)
        self.assertEqual(job["skipped_count"], 1)
        self.assertTrue(job["local_data_only"])
        self.assertEqual(job["execution_mode"], "preflight_only")
        self.assertEqual(job["professionalReadiness"]["overall_state"], "research_prototype")
        self.assertFalse(job["professionalReadiness"]["professional_quant_ready"])
        self.assertEqual(job["localDataCoverageState"], "mixed")
        self.assertEqual(job["universeBiasState"], "uncontrolled")
        ensure_mock.assert_not_called()
        fetch_mock.assert_not_called()

        results = service.list_universe_job_results(job["id"], page=1, limit=10)
        self.assertEqual([item["symbol"] for item in results["items"]], ["AAPL", "MSFT", "ZZZ"])
        self.assertEqual([item["sequence_index"] for item in results["items"]], [0, 1, 2])
        self.assertEqual(results["items"][0]["status"], "ready_local_data")
        self.assertEqual(results["items"][2]["status"], "skipped")
        self.assertEqual(results["items"][2]["reason_code"], "blocked_missing_local_data")

    def test_preflight_local_data_coverage_reports_ready_partial_missing_and_insufficient(self) -> None:
        self._seed_history("AAPL", [10.0, 10.2, 10.4, 10.6, 10.8])
        self._seed_history("MSFT", [20.0, 20.2, 20.4, 20.6], start=date(2025, 1, 2))
        self._seed_history("NVDA", [30.0, 30.2, 30.4])
        service = RuleBacktestService(self.db)

        with patch.object(RuleBacktestService, "_ensure_market_history") as ensure_mock, patch(
            "src.services.rule_backtest_service.fetch_daily_history_with_local_us_fallback"
        ) as fetch_mock:
            result = service.preflight_local_data_coverage(
                symbols=["zzz", "MSFT", "aapl", "AAPL", "NVDA"],
                start_date="2025-01-01",
                end_date="2025-01-05",
                minimum_required_bars=5,
                minimum_coverage_ratio=0.8,
            )

        ensure_mock.assert_not_called()
        fetch_mock.assert_not_called()
        self.assertEqual(result["symbols"], ["AAPL", "MSFT", "NVDA", "ZZZ"])
        self.assertEqual(result["summary"]["total"], 4)
        self.assertEqual(result["summary"]["ready"], 1)
        self.assertEqual(result["summary"]["partial"], 1)
        self.assertEqual(result["summary"]["insufficient_data"], 1)
        self.assertEqual(result["summary"]["missing"], 1)
        by_symbol = {item["symbol"]: item for item in result["items"]}
        self.assertEqual(by_symbol["AAPL"]["state"], "ready")
        self.assertEqual(by_symbol["MSFT"]["state"], "partial")
        self.assertEqual(by_symbol["MSFT"]["reason_code"], "partial_local_data")
        self.assertEqual(by_symbol["NVDA"]["state"], "insufficient_data")
        self.assertEqual(by_symbol["NVDA"]["reason_code"], "insufficient_data")
        self.assertEqual(by_symbol["ZZZ"]["state"], "missing")
        self.assertEqual(by_symbol["ZZZ"]["reason_code"], "blocked_missing_local_data")

    def test_create_universe_job_uses_local_coverage_preflight_reason_codes(self) -> None:
        self._seed_history("AAPL", [10.0, 10.2, 10.4, 10.6, 10.8])
        self._seed_history("MSFT", [20.0, 20.2, 20.4, 20.6], start=date(2025, 1, 2))
        service = RuleBacktestService(self.db)

        with patch.object(RuleBacktestService, "_ensure_market_history") as ensure_mock, patch(
            "src.services.rule_backtest_service.fetch_daily_history_with_local_us_fallback"
        ) as fetch_mock:
            job = service.create_universe_job(
                symbols=["MSFT", "AAPL", "ZZZ"],
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2025-01-01",
                end_date="2025-01-05",
                lookback_bars=5,
            )

        ensure_mock.assert_not_called()
        fetch_mock.assert_not_called()
        self.assertEqual(job["completed_count"], 1)
        self.assertEqual(job["skipped_count"], 2)

        results = service.list_universe_job_results(job["id"], page=1, limit=10)
        by_symbol = {item["symbol"]: item for item in results["items"]}
        self.assertEqual(by_symbol["AAPL"]["status"], "ready_local_data")
        self.assertEqual(by_symbol["AAPL"]["metrics"]["local_data_preflight"]["state"], "ready")
        self.assertEqual(by_symbol["MSFT"]["status"], "skipped")
        self.assertEqual(by_symbol["MSFT"]["reason_code"], "partial_local_data")
        self.assertEqual(by_symbol["MSFT"]["metrics"]["local_data_preflight"]["state"], "partial")
        self.assertEqual(by_symbol["ZZZ"]["reason_code"], "blocked_missing_local_data")

    def test_universe_job_results_are_paginated_by_sequence_index(self) -> None:
        for code in ["AAPL", "MSFT", "NVDA"]:
            self._seed_history(code, [10.0, 10.2, 10.4, 10.6, 10.8])
        service = RuleBacktestService(self.db)
        job = service.create_universe_job(
            symbols=["NVDA", "MSFT", "AAPL"],
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            start_date="2025-01-01",
            end_date="2025-01-05",
        )

        page = service.list_universe_job_results(job["id"], page=2, limit=1)

        self.assertEqual(page["total"], 3)
        self.assertEqual(page["page"], 2)
        self.assertEqual(page["limit"], 1)
        self.assertEqual([item["symbol"] for item in page["items"]], ["MSFT"])

    def test_create_universe_job_rejects_over_limit_symbol_lists(self) -> None:
        service = RuleBacktestService(self.db)

        with self.assertRaises(ValueError) as ctx:
            service.create_universe_job(
                symbols=[f"T{i:03d}" for i in range(501)],
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            )

        self.assertIn("max universe size is 500", str(ctx.exception))

    def test_run_universe_job_sequential_executes_ready_symbols_local_only(self) -> None:
        closes = [10.0 + (index * 0.2) + (0.4 if index % 7 == 0 else 0.0) for index in range(80)]
        self._seed_history("AAPL", closes)
        self._seed_history("MSFT", [20.0 + (index * 0.15) for index in range(80)])
        service = RuleBacktestService(self.db)
        job = service.create_universe_job(
            symbols=["MSFT", "AAPL", "ZZZ"],
            strategy_text="5日均线上穿20日均线买入，下穿卖出",
            parsed_strategy=self._ma_strategy(),
            start_date="2025-01-01",
            end_date="2025-03-21",
            lookback_bars=60,
        )

        with patch.object(RuleBacktestService, "_ensure_market_history") as ensure_mock, patch(
            "src.services.rule_backtest_service.fetch_daily_history_with_local_us_fallback"
        ) as fetch_mock:
            updated = service.run_universe_job_sequential(job["id"])

        ensure_mock.assert_not_called()
        fetch_mock.assert_not_called()
        self.assertEqual(updated["execution_mode"], "sequential_local")
        self.assertEqual(updated["status"], "completed_with_failures")
        self.assertEqual(updated["symbol_count"], 3)
        self.assertEqual(updated["processed_count"], 3)
        self.assertEqual(updated["completed_count"], 2)
        self.assertEqual(updated["skipped_count"], 1)
        self.assertEqual(updated["failed_count"], 0)
        self.assertEqual(updated["pending_count"], 0)
        self.assertEqual(updated["running_count"], 0)

        results = service.list_universe_job_results(job["id"], page=1, limit=10)
        self.assertEqual([item["symbol"] for item in results["items"]], ["AAPL", "MSFT", "ZZZ"])
        by_symbol = {item["symbol"]: item for item in results["items"]}
        self.assertEqual(by_symbol["AAPL"]["status"], "completed")
        self.assertIn("total_return_pct", by_symbol["AAPL"]["metrics"])
        self.assertIn("max_drawdown_pct", by_symbol["AAPL"]["metrics"])
        self.assertIn("win_rate_pct", by_symbol["AAPL"]["metrics"])
        self.assertIn("trades_count", by_symbol["AAPL"]["metrics"])
        self.assertEqual(by_symbol["AAPL"]["total_return_pct"], by_symbol["AAPL"]["metrics"]["total_return_pct"])
        self.assertEqual(by_symbol["ZZZ"]["status"], "skipped")
        self.assertEqual(by_symbol["ZZZ"]["reason_code"], "blocked_missing_local_data")

    def test_universe_job_diagnostics_reports_preflight_only_empty_local_coverage(self) -> None:
        service = RuleBacktestService(self.db)
        job = service.create_universe_job(
            symbols=["ZZZ", "YYY"],
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            start_date="2025-01-01",
            end_date="2025-01-05",
            lookback_bars=5,
        )

        diagnostics = service.get_universe_job_diagnostics(job["id"])

        self.assertEqual(diagnostics["progress"]["status"], "completed_with_failures")
        self.assertEqual(diagnostics["progress"]["total_count"], 2)
        self.assertEqual(diagnostics["progress"]["processed_count"], 2)
        self.assertEqual(diagnostics["progress"]["succeeded_count"], 0)
        self.assertEqual(diagnostics["progress"]["failed_count"], 0)
        self.assertEqual(diagnostics["progress"]["skipped_count"], 2)
        self.assertEqual(diagnostics["progress"]["progress_pct"], 100.0)
        self.assertEqual(diagnostics["local_data_coverage"]["missing"], 2)
        self.assertEqual(diagnostics["reason_summary"][0]["reason_code"], "blocked_missing_local_data")
        self.assertEqual(diagnostics["reason_summary"][0]["count"], 2)
        self.assertLessEqual(len(diagnostics["reason_summary"][0]["sample_symbols"]), 5)
        self.assertEqual(diagnostics["metadata"]["local_only"], True)
        self.assertEqual(diagnostics["metadata"]["live_provider_calls_executed"], False)
        self.assertEqual(diagnostics["metadata"]["concurrency_enabled"], False)
        self.assertEqual(diagnostics["metadata"]["professionalReadiness"]["overall_state"], "research_prototype")
        self.assertFalse(diagnostics["metadata"]["professionalReadiness"]["professional_quant_ready"])
        self.assertEqual(diagnostics["metadata"]["localDataCoverageState"], "missing")
        self.assertFalse(diagnostics["metadata"]["pointInTimeUniverse"])
        self.assertEqual(diagnostics["metadata"]["survivorshipBiasState"], "uncontrolled")
        self.assertFalse(diagnostics["metadata"]["providerCalls"])

    def test_universe_job_diagnostics_after_sequential_run_is_compact_and_local_only(self) -> None:
        closes = [10.0 + (index * 0.2) + (0.4 if index % 7 == 0 else 0.0) for index in range(80)]
        self._seed_history("AAPL", closes)
        self._seed_history("MSFT", [20.0 + (index * 0.15) for index in range(80)])
        service = RuleBacktestService(self.db)
        job = service.create_universe_job(
            symbols=["MSFT", "AAPL", "ZZZ"],
            strategy_text="5日均线上穿20日均线买入，下穿卖出",
            parsed_strategy=self._ma_strategy(),
            start_date="2025-01-01",
            end_date="2025-03-21",
            lookback_bars=60,
        )

        with patch.object(RuleBacktestService, "_ensure_market_history") as ensure_mock, patch(
            "src.services.rule_backtest_service.fetch_daily_history_with_local_us_fallback"
        ) as fetch_mock:
            service.run_universe_job_sequential(job["id"])
            diagnostics = service.get_universe_job_diagnostics(job["id"])

        ensure_mock.assert_not_called()
        fetch_mock.assert_not_called()
        self.assertEqual(diagnostics["progress"]["total_count"], 3)
        self.assertEqual(diagnostics["progress"]["processed_count"], 3)
        self.assertEqual(diagnostics["progress"]["succeeded_count"], 2)
        self.assertEqual(diagnostics["progress"]["skipped_count"], 1)
        top_returns = diagnostics["performance_summary"]["top_return_symbols"]
        self.assertLessEqual(len(top_returns), 5)
        self.assertGreaterEqual(top_returns[0]["total_return_pct"], top_returns[-1]["total_return_pct"])
        self.assertNotIn("execution_trace", diagnostics)
        self.assertNotIn("equity_curve", diagnostics)
        self.assertEqual(diagnostics["metadata"]["local_only"], True)
        self.assertEqual(diagnostics["metadata"]["live_provider_calls_executed"], False)
        self.assertEqual(diagnostics["metadata"]["concurrency_enabled"], False)
        self.assertEqual(diagnostics["metadata"]["professionalReadiness"]["overall_state"], "research_prototype")
        self.assertFalse(diagnostics["metadata"]["professionalReadiness"]["professional_quant_ready"])
        self.assertEqual(diagnostics["metadata"]["localDataCoverageState"], "mixed")
        self.assertFalse(diagnostics["metadata"]["pointInTimeUniverse"])
        self.assertEqual(diagnostics["metadata"]["survivorshipBiasState"], "uncontrolled")
        self.assertFalse(diagnostics["metadata"]["providerCalls"])

    def test_universe_job_diagnostics_groups_completed_failures_and_skips_by_reason(self) -> None:
        for code in ["AAPL", "MSFT", "NVDA"]:
            self._seed_history(code, [10.0 + (index * 0.2) for index in range(80)])
        service = RuleBacktestService(self.db)
        job = service.create_universe_job(
            symbols=["NVDA", "MSFT", "AAPL", "ZZZ"],
            strategy_text="5日均线上穿20日均线买入，下穿卖出",
            parsed_strategy=self._ma_strategy(),
            start_date="2025-01-01",
            end_date="2025-03-21",
            lookback_bars=60,
        )
        original_run = service.engine.run

        def run_or_fail(**kwargs):
            if kwargs["code"] == "MSFT":
                raise RuntimeError("synthetic execution failure")
            return original_run(**kwargs)

        with patch.object(service.engine, "run", side_effect=run_or_fail):
            service.run_universe_job_sequential(job["id"])

        diagnostics = service.get_universe_job_diagnostics(job["id"])

        reasons = {bucket["reason_code"]: bucket for bucket in diagnostics["reason_summary"]}
        self.assertEqual(reasons["symbol_execution_failed"]["count"], 1)
        self.assertEqual(reasons["symbol_execution_failed"]["sample_symbols"], ["MSFT"])
        self.assertEqual(reasons["blocked_missing_local_data"]["count"], 1)
        self.assertEqual(reasons["blocked_missing_local_data"]["sample_symbols"], ["ZZZ"])
        self.assertEqual(diagnostics["local_data_coverage"]["ready"], 3)
        self.assertEqual(diagnostics["local_data_coverage"]["missing"], 1)

    def test_universe_metric_leaders_are_bounded_and_sorted(self) -> None:
        for code in ["AAPL", "MSFT", "NVDA", "ORCL", "TSLA", "AMZN"]:
            self._seed_history(code, [10.0, 10.2, 10.4, 10.6, 10.8])
        service = RuleBacktestService(self.db)
        job = service.create_universe_job(
            symbols=["AAPL", "MSFT", "NVDA", "ORCL", "TSLA", "AMZN"],
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            start_date="2025-01-01",
            end_date="2025-01-05",
            lookback_bars=5,
        )
        rows = service.repo.get_universe_symbol_results(job["id"])
        metrics_by_symbol = {
            "AAPL": {"total_return_pct": 5.0, "max_drawdown_pct": -2.0, "win_rate_pct": 60.0, "trades_count": 2},
            "MSFT": {"total_return_pct": 12.0, "max_drawdown_pct": -8.0, "win_rate_pct": 80.0, "trades_count": 3},
            "NVDA": {"total_return_pct": -4.0, "max_drawdown_pct": -12.0, "win_rate_pct": 20.0, "trades_count": 1},
            "ORCL": {"total_return_pct": 8.0, "max_drawdown_pct": -1.0, "win_rate_pct": 55.0, "trades_count": 4},
            "TSLA": {"total_return_pct": 20.0, "max_drawdown_pct": -15.0, "win_rate_pct": 90.0, "trades_count": 5},
            "AMZN": {"total_return_pct": 1.0, "max_drawdown_pct": -3.0, "win_rate_pct": 40.0, "trades_count": 2},
        }
        for row in rows:
            service.repo.update_universe_symbol_result(
                int(row.id),
                status="completed",
                reason_code=None,
                reason_message=None,
                metrics_json=service._serialize_json(
                    {
                        **metrics_by_symbol[row.symbol],
                        "local_data_preflight": {"state": "ready"},
                    }
                ),
            )
        service.repo.update_universe_job(
            job["id"],
            status="completed",
            completed_count=6,
            skipped_count=0,
            failed_count=0,
            pending_count=0,
            running_count=0,
        )

        diagnostics = service.get_universe_job_diagnostics(job["id"])

        self.assertEqual(
            [item["symbol"] for item in diagnostics["performance_summary"]["top_return_symbols"]],
            ["TSLA", "MSFT", "ORCL", "AAPL", "AMZN"],
        )
        self.assertEqual(
            [item["symbol"] for item in diagnostics["performance_summary"]["worst_return_symbols"]],
            ["NVDA", "AMZN", "AAPL", "ORCL", "MSFT"],
        )
        self.assertEqual(
            [item["symbol"] for item in diagnostics["performance_summary"]["worst_drawdown_symbols"]],
            ["TSLA", "NVDA", "MSFT", "AMZN", "AAPL"],
        )
        self.assertEqual(
            [item["symbol"] for item in diagnostics["performance_summary"]["best_win_rate_symbols"]],
            ["TSLA", "MSFT", "AAPL", "ORCL", "AMZN"],
        )

    def test_universe_job_results_filter_and_sort_contract(self) -> None:
        for code in ["AAPL", "MSFT", "NVDA"]:
            self._seed_history(code, [10.0, 10.2, 10.4, 10.6, 10.8])
        service = RuleBacktestService(self.db)
        job = service.create_universe_job(
            symbols=["NVDA", "MSFT", "AAPL", "ZZZ"],
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            start_date="2025-01-01",
            end_date="2025-01-05",
            lookback_bars=5,
        )
        rows = service.repo.get_universe_symbol_results(job["id"])
        for row in rows:
            if row.symbol == "AAPL":
                service.repo.update_universe_symbol_result(
                    int(row.id),
                    status="completed",
                    reason_code=None,
                    metrics_json=service._serialize_json({"total_return_pct": 2.0, "local_data_preflight": {"state": "ready"}}),
                )
            elif row.symbol == "MSFT":
                service.repo.update_universe_symbol_result(
                    int(row.id),
                    status="failed",
                    reason_code="symbol_execution_failed",
                    metrics_json=service._serialize_json({"total_return_pct": -1.0, "local_data_preflight": {"state": "ready"}}),
                )
            elif row.symbol == "NVDA":
                service.repo.update_universe_symbol_result(
                    int(row.id),
                    status="completed",
                    reason_code=None,
                    metrics_json=service._serialize_json({"total_return_pct": 7.0, "local_data_preflight": {"state": "ready"}}),
                )

        completed = service.list_universe_job_results(job["id"], page=1, limit=10, status="completed")
        failed_reason = service.list_universe_job_results(
            job["id"],
            page=1,
            limit=10,
            reason_code="symbol_execution_failed",
        )
        sorted_by_return = service.list_universe_job_results(
            job["id"],
            page=1,
            limit=10,
            sort="total_return_pct",
            order="desc",
        )
        sorted_by_sequence = service.list_universe_job_results(
            job["id"],
            page=1,
            limit=10,
            sort="sequence_index",
            order="asc",
        )

        self.assertEqual([item["symbol"] for item in completed["items"]], ["AAPL", "NVDA"])
        self.assertEqual([item["symbol"] for item in failed_reason["items"]], ["MSFT"])
        self.assertEqual([item["symbol"] for item in sorted_by_return["items"][:3]], ["NVDA", "AAPL", "MSFT"])
        self.assertEqual([item["symbol"] for item in sorted_by_sequence["items"]], ["AAPL", "MSFT", "NVDA", "ZZZ"])

        with self.assertRaises(ValueError):
            service.list_universe_job_results(job["id"], page=1, limit=10, sort="unsupported_metric")

    def test_run_universe_job_sequential_isolates_symbol_failures(self) -> None:
        for code in ["AAPL", "MSFT", "NVDA"]:
            self._seed_history(code, [10.0 + (index * 0.2) for index in range(80)])
        service = RuleBacktestService(self.db)
        job = service.create_universe_job(
            symbols=["NVDA", "MSFT", "AAPL"],
            strategy_text="5日均线上穿20日均线买入，下穿卖出",
            parsed_strategy=self._ma_strategy(),
            start_date="2025-01-01",
            end_date="2025-03-21",
            lookback_bars=60,
        )
        original_run = service.engine.run

        def run_or_fail(**kwargs):
            if kwargs["code"] == "MSFT":
                raise RuntimeError("synthetic provider-looking traceback should be sanitized")
            return original_run(**kwargs)

        with patch.object(service.engine, "run", side_effect=run_or_fail):
            updated = service.run_universe_job_sequential(job["id"])

        self.assertEqual(updated["status"], "completed_with_failures")
        self.assertEqual(updated["completed_count"], 2)
        self.assertEqual(updated["failed_count"], 1)
        results = service.list_universe_job_results(job["id"], page=1, limit=10)
        self.assertEqual([item["symbol"] for item in results["items"]], ["AAPL", "MSFT", "NVDA"])
        by_symbol = {item["symbol"]: item for item in results["items"]}
        self.assertEqual(by_symbol["AAPL"]["status"], "completed")
        self.assertEqual(by_symbol["MSFT"]["status"], "failed")
        self.assertEqual(by_symbol["MSFT"]["reason_code"], "symbol_execution_failed")
        self.assertLessEqual(len(by_symbol["MSFT"]["reason_message"]), 160)
        self.assertEqual(by_symbol["NVDA"]["status"], "completed")

    def test_run_universe_job_sequential_rejects_duplicate_runs(self) -> None:
        self._seed_history("AAPL", [10.0 + (index * 0.2) for index in range(80)])
        service = RuleBacktestService(self.db)
        job = service.create_universe_job(
            symbols=["AAPL"],
            strategy_text="5日均线上穿20日均线买入，下穿卖出",
            parsed_strategy=self._ma_strategy(),
            start_date="2025-01-01",
            end_date="2025-03-21",
            lookback_bars=60,
        )

        service.run_universe_job_sequential(job["id"])
        with self.assertRaises(ValueError) as ctx:
            service.run_universe_job_sequential(job["id"])

        self.assertIn("not runnable", str(ctx.exception))

    def test_run_universe_job_sequential_respects_preexisting_cancel_request(self) -> None:
        self._seed_history("AAPL", [10.0 + (index * 0.2) for index in range(80)])
        service = RuleBacktestService(self.db)
        job = service.create_universe_job(
            symbols=["AAPL"],
            strategy_text="5日均线上穿20日均线买入，下穿卖出",
            parsed_strategy=self._ma_strategy(),
            start_date="2025-01-01",
            end_date="2025-03-21",
            lookback_bars=60,
        )
        service.repo.update_universe_job(job["id"], cancel_requested=True)

        updated = service.run_universe_job_sequential(job["id"])

        self.assertEqual(updated["status"], "cancelled")
        self.assertEqual(updated["execution_mode"], "sequential_local")
        self.assertEqual(updated["processed_count"], 0)


if __name__ == "__main__":
    unittest.main()
