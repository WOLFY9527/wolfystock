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
        ensure_mock.assert_not_called()
        fetch_mock.assert_not_called()

        results = service.list_universe_job_results(job["id"], page=1, limit=10)
        self.assertEqual([item["symbol"] for item in results["items"]], ["AAPL", "MSFT", "ZZZ"])
        self.assertEqual([item["sequence_index"] for item in results["items"]], [0, 1, 2])
        self.assertEqual(results["items"][0]["status"], "ready_local_data")
        self.assertEqual(results["items"][2]["status"], "skipped")
        self.assertEqual(results["items"][2]["reason_code"], "blocked_missing_local_data")

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


if __name__ == "__main__":
    unittest.main()
