# -*- coding: utf-8 -*-
"""Durable Runtime v1 synthetic worker prototype tests."""

from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

from src.services.durable_runtime_contracts import DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE
from src.services.durable_runtime_v1 import (
    DurableRuntimeV1PrototypeWorker,
    create_synthetic_runtime_task,
)
from src.storage import DatabaseManager


class DurableRuntimeV1WorkerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "durable-runtime-v1-worker.db"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.db.create_or_update_app_user(user_id="owner-a", username="owner_a")

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def test_worker_completes_analysis_and_backtest_fixture_tasks(self) -> None:
        create_synthetic_runtime_task(
            db=self.db,
            task_id="runtime-analysis-fixture",
            owner_user_id="owner-a",
            job_kind="analysis_fixture",
            fixture_name="synthetic_success",
            symbol="AAPL",
        )
        create_synthetic_runtime_task(
            db=self.db,
            task_id="runtime-backtest-fixture",
            owner_user_id="owner-a",
            job_kind="backtest_fixture",
            fixture_name="synthetic_success",
            symbol="AAPL",
        )
        worker = DurableRuntimeV1PrototypeWorker(db=self.db, worker_id="worker-a")

        first = worker.run_once()
        second = worker.run_once()
        analysis_state = self.db.get_durable_task_state(
            task_id="runtime-analysis-fixture",
            owner_user_id="owner-a",
        )
        backtest_state = self.db.get_durable_task_state(
            task_id="runtime-backtest-fixture",
            owner_user_id="owner-a",
        )

        self.assertEqual(first.status, "completed")
        self.assertEqual(second.status, "completed")
        self.assertEqual(analysis_state["status"], "completed")
        self.assertEqual(backtest_state["status"], "completed")
        self.assertEqual(analysis_state["metadata"]["result_ref"], "fixture:analysis_fixture:synthetic_success")
        self.assertEqual(backtest_state["metadata"]["result_ref"], "fixture:backtest_fixture:synthetic_success")
        self.assertEqual(analysis_state["task_type"], DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE)
        self.assertEqual(backtest_state["task_type"], DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE)

    def test_transient_fixture_retries_then_completes_with_bounded_attempts(self) -> None:
        create_synthetic_runtime_task(
            db=self.db,
            task_id="runtime-transient",
            owner_user_id="owner-a",
            job_kind="analysis_fixture",
            fixture_name="transient_failure",
            symbol="AAPL",
            max_attempts=3,
            metadata={"transient_failures_remaining": 2},
        )
        worker = DurableRuntimeV1PrototypeWorker(db=self.db, worker_id="worker-a")

        self.assertEqual(worker.run_once().status, "retry_queued")
        self.assertEqual(worker.run_once().status, "retry_queued")
        self.assertEqual(worker.run_once().status, "completed")
        state = self.db.get_durable_task_state(task_id="runtime-transient", owner_user_id="owner-a")

        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["attempt_count"], 3)
        self.assertEqual(state["metadata"]["transient_failures_remaining"], 0)

    def test_worker_ignores_production_analysis_rows_by_default(self) -> None:
        self.db.create_durable_task_state(
            task_id="runtime-production-analysis",
            owner_user_id="owner-a",
            task_type="analysis",
            route_family="/api/v1/analysis",
            status="queued",
            current_step="Queued by production analysis route",
            metadata={"stock_code": "AAPL"},
        )
        worker = DurableRuntimeV1PrototypeWorker(db=self.db, worker_id="worker-a")

        result = worker.run_once()
        state = self.db.get_durable_task_state(
            task_id="runtime-production-analysis",
            owner_user_id="owner-a",
        )

        self.assertEqual(result.status, "idle")
        self.assertEqual(state["status"], "queued")
        self.assertEqual(state["attempt_count"], 0)
        self.assertIsNone(state["lease_owner"])

    def test_worker_module_does_not_import_live_runtime_services(self) -> None:
        import src.services.durable_runtime_v1 as module

        source = inspect.getsource(module)

        for forbidden in (
            "AnalysisService",
            "RuleBacktestService",
            "RuleBacktestEngine",
            "MarketCache",
            "_ensure_market_history",
            "_store_result",
            "requests.",
            "urllib.",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
