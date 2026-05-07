# -*- coding: utf-8 -*-
"""Golden fixtures for standard historical-analysis backtest metrics."""

import os
import tempfile
import unittest
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from src.config import Config
from src.core.backtest_engine import BacktestEngine, EvaluationConfig
from src.services.backtest_service import BacktestService
from src.storage import AnalysisHistory, BacktestResult, DatabaseManager, StockDaily


@dataclass
class GoldenBar:
    date: date
    high: float
    low: float
    close: float


class BacktestGoldenMetricsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_backtest_golden_metrics.db")
        self._original_database_path = os.environ.get("DATABASE_PATH")
        self._original_eval_window = os.environ.get("BACKTEST_EVAL_WINDOW_DAYS")
        self._original_min_age = os.environ.get("BACKTEST_MIN_AGE_DAYS")
        os.environ["DATABASE_PATH"] = self._db_path
        os.environ["BACKTEST_EVAL_WINDOW_DAYS"] = "3"
        os.environ["BACKTEST_MIN_AGE_DAYS"] = "0"

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

    def tearDown(self) -> None:
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
        self._temp_dir.cleanup()

    @staticmethod
    def _bars(start: date, closes: list[float], highs: list[float], lows: list[float]) -> list[GoldenBar]:
        return [
            GoldenBar(
                date=start + timedelta(days=index + 1),
                high=float(highs[index]),
                low=float(lows[index]),
                close=float(closes[index]),
            )
            for index in range(len(closes))
        ]

    def test_engine_golden_return_metrics_use_window_end_close_without_costs(self) -> None:
        result = BacktestEngine.evaluate_single(
            operation_advice="买入",
            analysis_date=date(2024, 1, 1),
            start_price=100.0,
            forward_bars=self._bars(
                date(2024, 1, 1),
                closes=[105.0, 90.0, 110.0],
                highs=[106.0, 92.0, 111.0],
                lows=[104.0, 89.0, 109.0],
            ),
            stop_loss=None,
            take_profit=None,
            config=EvaluationConfig(eval_window_days=3, neutral_band_pct=2.0),
        )

        self.assertEqual(result["eval_status"], "completed")
        self.assertEqual(result["position_recommendation"], "long")
        self.assertAlmostEqual(result["start_price"], 100.0)
        self.assertAlmostEqual(result["end_close"], 110.0)
        self.assertAlmostEqual(result["stock_return_pct"], 10.0)
        self.assertAlmostEqual(result["simulated_entry_price"], 100.0)
        self.assertAlmostEqual(result["simulated_exit_price"], 110.0)
        self.assertEqual(result["simulated_exit_reason"], "window_end")
        self.assertAlmostEqual(result["simulated_return_pct"], 10.0)
        self.assertEqual(result["outcome"], "win")
        self.assertNotIn("fee_bps", result)
        self.assertNotIn("slippage_bps", result)
        self.assertNotIn("max_drawdown_pct", result)

    def test_summary_golden_counts_and_average_returns(self) -> None:
        rows = [
            BacktestResult(
                eval_status="completed",
                position_recommendation="long",
                outcome="win",
                direction_correct=True,
                stock_return_pct=10.0,
                simulated_return_pct=10.0,
                hit_stop_loss=False,
                hit_take_profit=False,
                first_hit="neither",
                operation_advice="买入",
            ),
            BacktestResult(
                eval_status="completed",
                position_recommendation="long",
                outcome="loss",
                direction_correct=False,
                stock_return_pct=-4.0,
                simulated_return_pct=-5.0,
                hit_stop_loss=True,
                hit_take_profit=False,
                first_hit="stop_loss",
                first_hit_trading_days=2,
                operation_advice="买入",
            ),
            BacktestResult(
                eval_status="completed",
                position_recommendation="cash",
                outcome="win",
                direction_correct=True,
                stock_return_pct=-3.0,
                simulated_return_pct=0.0,
                hit_stop_loss=None,
                hit_take_profit=None,
                first_hit="not_applicable",
                operation_advice="卖出",
            ),
            BacktestResult(
                eval_status="insufficient_data",
                position_recommendation="long",
                outcome=None,
                direction_correct=None,
                stock_return_pct=None,
                simulated_return_pct=None,
                operation_advice="买入",
            ),
        ]

        summary = BacktestEngine.compute_summary(
            results=rows,
            scope="overall",
            code="__overall__",
            eval_window_days=3,
            engine_version="v1",
        )

        self.assertEqual(summary["total_evaluations"], 4)
        self.assertEqual(summary["completed_count"], 3)
        self.assertEqual(summary["insufficient_count"], 1)
        self.assertEqual(summary["long_count"], 2)
        self.assertEqual(summary["cash_count"], 1)
        self.assertEqual(summary["win_count"], 2)
        self.assertEqual(summary["loss_count"], 1)
        self.assertEqual(summary["neutral_count"], 0)
        self.assertEqual(summary["win_rate_pct"], 66.67)
        self.assertEqual(summary["direction_accuracy_pct"], 66.67)
        self.assertEqual(summary["avg_stock_return_pct"], 1.0)
        self.assertEqual(summary["avg_simulated_return_pct"], 1.6667)
        self.assertEqual(summary["stop_loss_trigger_rate"], 50.0)
        self.assertEqual(summary["take_profit_trigger_rate"], 0.0)
        self.assertEqual(summary["avg_days_to_first_hit"], 2.0)
        self.assertNotIn("trade_count", summary)
        self.assertNotIn("max_drawdown_pct", summary)

    def test_service_golden_no_lookahead_entry_and_explicit_no_cost_assumption(self) -> None:
        with self.db.get_session() as session:
            session.add(
                AnalysisHistory(
                    query_id="golden-no-lookahead",
                    code="GOLDEN",
                    name="Golden Fixture",
                    report_type="simple",
                    sentiment_score=80,
                    operation_advice="买入",
                    trend_prediction="看多",
                    analysis_summary="fixture",
                    stop_loss=90.0,
                    take_profit=110.0,
                    created_at=datetime(2024, 1, 1, 0, 0, 0),
                    context_snapshot='{"enhanced_context": {"date": "2024-01-01"}}',
                )
            )
            session.add(
                StockDaily(
                    code="GOLDEN",
                    date=date(2024, 1, 1),
                    open=95.0,
                    high=111.0,
                    low=89.0,
                    close=100.0,
                )
            )
            session.add_all([
                StockDaily(code="GOLDEN", date=date(2024, 1, 2), open=101.0, high=106.0, low=99.0, close=105.0),
                StockDaily(code="GOLDEN", date=date(2024, 1, 3), open=105.0, high=107.0, low=96.0, close=102.0),
                StockDaily(code="GOLDEN", date=date(2024, 1, 4), open=102.0, high=108.0, low=101.0, close=104.0),
            ])
            session.commit()

        service = BacktestService(self.db)
        stats = service.run_backtest(code="GOLDEN", force=False, eval_window_days=3, min_age_days=0, limit=10)

        self.assertEqual(stats["saved"], 1)
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["execution_assumptions"]["simulated_entry_timing"], "analysis_date close")
        self.assertEqual(stats["execution_assumptions"]["fees_slippage"], "not applied")

        recent = service.get_recent_evaluations(code="GOLDEN", eval_window_days=3, limit=10, page=1)
        item = recent["items"][0]
        self.assertEqual(item["analysis_date"], "2024-01-01")
        self.assertAlmostEqual(item["start_price"], 100.0)
        self.assertFalse(item["hit_stop_loss"])
        self.assertFalse(item["hit_take_profit"])
        self.assertEqual(item["first_hit"], "neither")
        self.assertIsNone(item["first_hit_date"])
        self.assertEqual(item["simulated_exit_reason"], "window_end")
        self.assertAlmostEqual(item["stock_return_pct"], 4.0)
        self.assertAlmostEqual(item["simulated_return_pct"], 4.0)
        self.assertEqual(item["execution_assumptions"]["fees_slippage"], "not applied")
        self.assertNotIn("max_drawdown_pct", item)

        history = service.list_backtest_runs(code="GOLDEN", page=1, limit=10)
        run = history["items"][0]
        self.assertEqual(run["completed_count"], 1)
        self.assertEqual(run["win_count"], 1)
        self.assertEqual(run["loss_count"], 0)
        self.assertAlmostEqual(run["avg_stock_return_pct"], 4.0)
        self.assertAlmostEqual(run["avg_simulated_return_pct"], 4.0)


if __name__ == "__main__":
    unittest.main()
