# -*- coding: utf-8 -*-
"""Focused tests for additive backtest professional-readiness diagnostics."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from src.config import Config
from src.services.backtest_professional_readiness import build_backtest_professional_readiness
from src.services.rule_backtest_service import RuleBacktestService
from src.storage import DatabaseManager, StockDaily


class BacktestProfessionalReadinessTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_backtest_professional_readiness.db")
        os.environ["DATABASE_PATH"] = self._db_path
        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        with self.db.get_session() as session:
            closes = [
                10.0,
                10.2,
                10.1,
                10.5,
                11.0,
                11.6,
                11.8,
                11.2,
                10.8,
                10.2,
                9.9,
                10.3,
                10.9,
                11.4,
                11.9,
                12.1,
                11.7,
                11.1,
                10.7,
                10.4,
                10.8,
                11.3,
                11.8,
                12.2,
            ]
            for index, close in enumerate(closes):
                session.add(
                    StockDaily(
                        code="600519",
                        date=date(2024, 1, 1) + timedelta(days=index),
                        open=close - 0.1,
                        high=close + 0.2,
                        low=close - 0.3,
                        close=close,
                        volume=1000.0,
                    )
                )
            session.commit()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self._temp_dir.cleanup()

    def test_readiness_helper_defaults_to_research_prototype(self) -> None:
        readiness = build_backtest_professional_readiness().to_dict()

        self.assertEqual(readiness["overall_state"], "research_prototype")
        self.assertFalse(readiness["professional_quant_ready"])
        self.assertEqual(readiness["adjusted_data_state"], "unknown_or_mixed")
        self.assertEqual(readiness["calendar_state"], "available_bars_only")
        self.assertEqual(readiness["fill_model"], "next_open_baseline")
        self.assertEqual(readiness["commission_model"], "bps_per_side")
        self.assertEqual(readiness["dataset_version"], "unknown")
        self.assertFalse(readiness["professional_reproducibility_ready"])
        self.assertIn("adjusted_data", readiness["categories"])
        self.assertIn("corporate_actions", readiness["categories"])
        self.assertIn("trading_calendar", readiness["categories"])
        self.assertIn("fill_model", readiness["categories"])
        self.assertIn("cost_model", readiness["categories"])
        self.assertIn("reproducibility", readiness["categories"])

    def test_single_symbol_run_and_readback_expose_additive_readiness_without_metric_changes(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(RuleBacktestService, "_ensure_market_history", return_value=0) as ensure_mock, patch(
            "src.services.rule_backtest_service.fetch_daily_history_with_local_us_fallback"
        ) as fetch_mock, patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )
            detail = service.get_run(response["id"])
            status = service.get_run_status(response["id"])

        ensure_mock.assert_called()
        fetch_mock.assert_not_called()
        self.assertIsNotNone(detail)
        self.assertIsNotNone(status)
        self.assertEqual(response["trade_count"], 3)
        self.assertEqual(response["total_return_pct"], 3.2278)
        self.assertEqual(response["max_drawdown_pct"], 9.322)
        self.assertEqual(response["win_rate_pct"], 66.6667)
        self.assertEqual(response["final_equity"], 103227.800782)
        self.assertEqual(response["buy_and_hold_return_pct"], 10.9091)
        self.assertEqual(response["excess_return_vs_buy_and_hold_pct"], -7.6813)
        self.assertEqual(detail["trade_count"], response["trade_count"])
        self.assertEqual(detail["total_return_pct"], response["total_return_pct"])
        self.assertEqual(detail["final_equity"], response["final_equity"])
        self.assertEqual(response["professionalReadiness"]["overall_state"], "research_prototype")
        self.assertFalse(response["professionalReadiness"]["professional_quant_ready"])
        self.assertEqual(response["adjustedDataState"], "unknown_or_mixed")
        self.assertEqual(response["corporateActionState"], "not_ready")
        self.assertEqual(response["tradingCalendarState"], "available_bars_only")
        self.assertEqual(response["fillModelState"], "next_open_baseline")
        self.assertEqual(response["costModelState"], "baseline_bps_only")
        self.assertEqual(response["antiLeakageState"], "basic_bar_close_to_next_open")
        self.assertEqual(response["reproducibilityState"], "partial_without_dataset_lineage")
        self.assertEqual(response["universeBiasState"], "not_applicable_single_symbol")
        self.assertEqual(detail["professionalReadiness"]["overall_state"], "research_prototype")
        self.assertFalse(detail["professionalReadiness"]["professional_quant_ready"])
        self.assertEqual(status["professionalReadiness"]["overall_state"], "research_prototype")
        self.assertFalse(status["professionalReadiness"]["professional_quant_ready"])
        self.assertEqual(status["adjustedDataState"], "unknown_or_mixed")
        self.assertEqual(status["fillModelState"], "next_open_baseline")


if __name__ == "__main__":
    unittest.main()
