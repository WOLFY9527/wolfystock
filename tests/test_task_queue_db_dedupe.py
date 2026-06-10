# -*- coding: utf-8 -*-
"""DB-backed duplicate protection for async analysis task submission."""

from __future__ import annotations

from concurrent.futures import Future
from datetime import datetime, timedelta
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import text

from src.services.task_queue import AnalysisTaskQueue, TaskInfo, _dedupe_stock_code_key
from src.storage import DatabaseManager


class DbBackedAnalysisTaskDedupeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._original_queue_instance = AnalysisTaskQueue._instance
        AnalysisTaskQueue._instance = None
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "task-dedupe.sqlite"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.db.create_or_update_app_user(user_id="user-a", username="alice")
        self.db.create_or_update_app_user(user_id="user-b", username="bob")
        self.db.create_or_update_app_user(user_id="guest-session-a", username="guest-a")

    def tearDown(self) -> None:
        queue = AnalysisTaskQueue._instance
        if queue is not None and queue is not self._original_queue_instance:
            executor = getattr(queue, "_executor", None)
            if executor is not None and hasattr(executor, "shutdown"):
                executor.shutdown(wait=False, cancel_futures=True)
        AnalysisTaskQueue._instance = self._original_queue_instance
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    @staticmethod
    def _new_queue() -> AnalysisTaskQueue:
        AnalysisTaskQueue._instance = None
        queue = AnalysisTaskQueue(max_workers=1)
        queue._executor = type("ExecutorStub", (), {"submit": lambda self, *args, **kwargs: Future()})()
        return queue

    def test_second_process_rejects_active_duplicate_from_durable_state(self) -> None:
        first_queue = self._new_queue()
        accepted, duplicates = first_queue.submit_tasks_batch(["600519"], owner_id="user-a")
        self.assertEqual(len(accepted), 1)
        self.assertEqual(duplicates, [])

        second_queue = self._new_queue()
        accepted_again, duplicates_again = second_queue.submit_tasks_batch(["600519.SH"], owner_id="user-a")

        self.assertEqual(accepted_again, [])
        self.assertEqual(len(duplicates_again), 1)
        self.assertEqual(duplicates_again[0].stock_code, "600519.SH")
        self.assertEqual(duplicates_again[0].existing_task_id, accepted[0].task_id)

    def test_stale_active_durable_row_blocks_retry_until_terminalized(self) -> None:
        stale_started_at = datetime.now() - timedelta(hours=6)
        stale = self.db.create_durable_task_state(
            task_id="task-stale-active",
            owner_user_id="user-a",
            task_type="analysis",
            route_family="/api/v1/analysis",
            status="processing",
            progress=55,
            current_step="Process-local worker disappeared before terminal state",
            dedupe_key=_dedupe_stock_code_key("AAPL.US", "user-a"),
            metadata={"stock_code": "AAPL.US"},
        )
        with self.db._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE durable_task_states
                    SET started_at = :stale_at, updated_at = :stale_at
                    WHERE task_id = :task_id
                    """
                ),
                {"stale_at": stale_started_at, "task_id": stale["task_id"]},
            )

        retry_queue = self._new_queue()
        accepted, duplicates = retry_queue.submit_tasks_batch(["AAPL.US"], owner_id="user-a")

        self.assertEqual(accepted, [])
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0].existing_task_id, "task-stale-active")

        terminalized = self.db.mark_durable_task_failed(
            task_id="task-stale-active",
            owner_user_id="user-a",
            error_code="process_local_lost",
            error_summary="Operator terminalized stale process-local analysis task",
        )
        terminalized_retry_queue = self._new_queue()
        accepted_after_terminal, duplicates_after_terminal = terminalized_retry_queue.submit_tasks_batch(
            ["AAPL.US"],
            owner_id="user-a",
        )

        self.assertIsNotNone(terminalized)
        self.assertEqual(terminalized["status"], "failed")
        self.assertEqual(len(accepted_after_terminal), 1)
        self.assertEqual(duplicates_after_terminal, [])
        self.assertNotEqual(accepted_after_terminal[0].task_id, "task-stale-active")

    def test_completed_and_failed_durable_tasks_allow_new_run(self) -> None:
        first_queue = self._new_queue()
        first, _ = first_queue.submit_tasks_batch(["MSFT"], owner_id="user-a")
        self.db.mark_durable_task_completed(task_id=first[0].task_id, owner_user_id="user-a")

        second_queue = self._new_queue()
        second, second_duplicates = second_queue.submit_tasks_batch(["MSFT"], owner_id="user-a")
        self.assertEqual(len(second), 1)
        self.assertEqual(second_duplicates, [])
        self.assertNotEqual(second[0].task_id, first[0].task_id)

        self.db.mark_durable_task_failed(
            task_id=second[0].task_id,
            owner_user_id="user-a",
            error_code="fixture_failed",
            error_summary="fixture failure",
        )
        third_queue = self._new_queue()
        third, third_duplicates = third_queue.submit_tasks_batch(["MSFT"], owner_id="user-a")

        self.assertEqual(len(third), 1)
        self.assertEqual(third_duplicates, [])
        self.assertNotEqual(third[0].task_id, second[0].task_id)

    def test_owner_and_guest_global_scope_isolation(self) -> None:
        user_queue = self._new_queue()
        user_a, _ = user_queue.submit_tasks_batch(["TSLA"], owner_id="user-a")

        user_b_queue = self._new_queue()
        user_b, user_b_duplicates = user_b_queue.submit_tasks_batch(["TSLA"], owner_id="user-b")
        self.assertEqual(len(user_b), 1)
        self.assertEqual(user_b_duplicates, [])
        self.assertNotEqual(user_b[0].task_id, user_a[0].task_id)

        global_queue = self._new_queue()
        global_task, global_duplicates = global_queue.submit_tasks_batch(["NVDA"], owner_id=None)
        self.assertEqual(len(global_task), 1)
        self.assertEqual(global_duplicates, [])

        guest_queue = self._new_queue()
        guest_task, guest_duplicates = guest_queue.submit_tasks_batch(["NVDA"], owner_id="guest-session-a")
        self.assertEqual(len(guest_task), 1)
        self.assertEqual(guest_duplicates, [])
        self.assertNotEqual(guest_task[0].task_id, global_task[0].task_id)

    def test_process_local_dedupe_short_circuits_before_durable_lookup(self) -> None:
        queue = self._new_queue()
        queue._tasks["task-local"] = TaskInfo(task_id="task-local", stock_code="600519", owner_id="user-a")
        queue._analyzing_stocks[_dedupe_stock_code_key("600519", "user-a")] = "task-local"

        original_reserve = getattr(queue, "_reserve_durable_task_create")

        def fail_if_called(*args, **kwargs):
            raise AssertionError("durable reservation should not run for local duplicates")

        queue._reserve_durable_task_create = fail_if_called
        try:
            accepted, duplicates = queue.submit_tasks_batch(["600519.SH"], owner_id="user-a")
        finally:
            queue._reserve_durable_task_create = original_reserve

        self.assertEqual(accepted, [])
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0].existing_task_id, "task-local")


if __name__ == "__main__":
    unittest.main()
