# -*- coding: utf-8 -*-
"""Contract tests for future queue-safe backtest job boundaries."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from typing import Any
from types import SimpleNamespace
from unittest.mock import patch

from src.config import Config
from src.services.rule_backtest_service import RuleBacktestService
from src.storage import DatabaseManager, StockDaily


class BacktestJobContractsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_backtest_job_contracts.db")
        os.environ["DATABASE_PATH"] = self._db_path
        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        self._ensure_market_history_patcher = patch.object(
            RuleBacktestService,
            "_ensure_market_history",
            return_value=0,
        )
        self._ensure_market_history_patcher.start()
        self._ensure_market_history_patcher_active = True

        self._seed_history("600519", [10, 10.2, 10.1, 10.5, 11.0, 11.6, 11.8, 11.2, 10.8, 10.2, 9.9, 10.3, 10.9, 11.4, 11.9, 12.1, 11.7, 11.1, 10.7, 10.4, 10.8, 11.3, 11.8, 12.2], start=date(2024, 1, 1))
        self._seed_history("AAPL", [10.0 + (index * 0.2) for index in range(80)], start=date(2025, 1, 1))
        self._seed_history("MSFT", [20.0 + (index * 0.15) for index in range(80)], start=date(2025, 1, 1))

    def tearDown(self) -> None:
        if getattr(self, "_ensure_market_history_patcher_active", False):
            self._ensure_market_history_patcher.stop()
            self._ensure_market_history_patcher_active = False
        DatabaseManager.reset_instance()
        self._temp_dir.cleanup()

    def _seed_history(self, code: str, closes: list[float], *, start: date) -> None:
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

    def _ma_strategy(self) -> dict[str, Any]:
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

    def _assert_json_safe_primitives_only(self, value: Any, *, path: str = "root") -> None:
        if value is None or isinstance(value, (str, int, float, bool)):
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                self._assert_json_safe_primitives_only(item, path=f"{path}[{index}]")
            return
        if isinstance(value, dict):
            for key, item in value.items():
                self.assertIsInstance(key, str, f"{path} has non-string key {key!r}")
                self._assert_json_safe_primitives_only(item, path=f"{path}.{key}")
            return
        self.fail(f"{path} is not JSON-safe: {type(value).__name__}")

    def test_submitted_backtest_request_snapshot_is_json_safe_and_primitive_only(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            submitted = service.submit_backtest(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2024-01-08",
                end_date="2024-01-18",
                lookback_bars=20,
                initial_capital=123456.0,
                fee_bps=1.5,
                slippage_bps=2.5,
                benchmark_mode="index_hs300",
                robustness_config={"monte_carlo": {"simulation_count": 8, "seed": 20260528}},
                confirmed=True,
            )

        run_row = service.repo.get_run(int(submitted["id"]), **service._owner_kwargs())
        self.assertIsNotNone(run_row)
        assert run_row is not None
        summary = json.loads(run_row.summary_json)
        request_payload = summary["request"]

        self.assertEqual(submitted["id"], run_row.id)
        self.assertEqual(request_payload["start_date"], "2024-01-08")
        self.assertEqual(request_payload["end_date"], "2024-01-18")
        self.assertEqual(request_payload["lookback_bars"], 20)
        self.assertEqual(request_payload["benchmark_mode"], "index_hs300")
        self.assertTrue(request_payload["confirmed"])
        self.assertEqual(json.loads(json.dumps(request_payload, ensure_ascii=False)), request_payload)
        self._assert_json_safe_primitives_only(request_payload)

    def test_repeated_readback_of_completed_run_uses_stored_state_without_reexecution(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            submitted = service.submit_backtest(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2024-01-08",
                end_date="2024-01-18",
                lookback_bars=20,
                confirmed=True,
            )
            service.process_submitted_run(int(submitted["id"]))

        with patch.object(service, "parse_strategy", side_effect=AssertionError("readback should not parse again")), patch.object(
            service.engine,
            "run",
            side_effect=AssertionError("readback should not rerun engine"),
        ), patch.object(
            service,
            "_build_ai_summary",
            side_effect=AssertionError("readback should not rebuild summary"),
        ):
            first_detail = service.get_run(int(submitted["id"]))
            second_detail = service.get_run(int(submitted["id"]))
            status = service.get_run_status(int(submitted["id"]))
            history = service.list_runs(code="600519", page=1, limit=10)

        self.assertIsNotNone(first_detail)
        self.assertIsNotNone(second_detail)
        self.assertIsNotNone(status)
        assert first_detail is not None
        assert second_detail is not None
        assert status is not None
        self.assertEqual(first_detail["id"], submitted["id"])
        self.assertEqual(second_detail["id"], submitted["id"])
        self.assertEqual(status["id"], submitted["id"])
        self.assertEqual(first_detail["status"], "completed")
        self.assertEqual(second_detail["status"], "completed")
        self.assertEqual(status["status"], "completed")
        self.assertEqual(first_detail["summary"]["request"], second_detail["summary"]["request"])
        self.assertEqual(status["id"], submitted["id"])
        self.assertEqual(status["status_history"], first_detail["status_history"])
        self.assertEqual(history["items"][0]["id"], submitted["id"])

    def test_universe_job_payloads_remain_json_serializable_local_only_and_stable(self) -> None:
        service = RuleBacktestService(self.db)
        job = service.create_universe_job(
            symbols=["MSFT", "AAPL", "ZZZ"],
            strategy_text="5日均线上穿20日均线买入，下穿卖出",
            parsed_strategy=self._ma_strategy(),
            start_date="2025-01-01",
            end_date="2025-03-21",
            lookback_bars=60,
            request_label="queue boundary",
        )

        with patch.object(RuleBacktestService, "_ensure_market_history") as ensure_mock, patch(
            "src.services.rule_backtest_service.fetch_daily_history_with_local_us_fallback"
        ) as fetch_mock:
            updated = service.run_universe_job_sequential(int(job["id"]))
            status = service.get_universe_job_status(int(job["id"]))
            diagnostics = service.get_universe_job_diagnostics(int(job["id"]))
            results = service.list_universe_job_results(int(job["id"]), page=1, limit=10)
            results_again = service.list_universe_job_results(int(job["id"]), page=1, limit=10)

        ensure_mock.assert_not_called()
        fetch_mock.assert_not_called()
        self.assertIsNotNone(updated)
        self.assertIsNotNone(status)
        self.assertIsNotNone(diagnostics)
        assert updated is not None
        assert status is not None
        assert diagnostics is not None
        self.assertEqual(updated["id"], job["id"])
        self.assertEqual(status["id"], job["id"])
        self.assertTrue(updated["local_data_only"])
        self.assertTrue(status["local_data_only"])
        self.assertEqual(updated["execution_mode"], "sequential_local")
        self.assertTrue(diagnostics["metadata"]["local_only"])
        self.assertFalse(diagnostics["metadata"]["live_provider_calls_executed"])

        for payload in (updated, status, diagnostics, results):
            self.assertEqual(json.loads(json.dumps(payload, ensure_ascii=False)), payload)
            self._assert_json_safe_primitives_only(payload)

        run_ids_by_symbol = {
            item["symbol"]: item["single_run_id"]
            for item in results["items"]
        }
        self.assertEqual(
            run_ids_by_symbol,
            {item["symbol"]: item["single_run_id"] for item in results_again["items"]},
        )
        self.assertIn("single_run_id", results["items"][0])

if __name__ == "__main__":
    unittest.main()
