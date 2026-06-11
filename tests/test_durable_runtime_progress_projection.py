# -*- coding: utf-8 -*-
"""Durable Runtime v1 progress projection tests."""

from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

from api.v1.endpoints.analysis import (
    get_analysis_status,
    get_task_progress as get_analysis_task_progress_endpoint,
    poll_analysis_task_progress,
)
from api.v1.schemas.analysis import TaskProgressResponse
from src.services.durable_runtime_contracts import (
    DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE,
    build_durable_runtime_envelope,
    normalize_durable_runtime_status,
)
from src.services.system_config_service import SystemConfigService
from src.services.task_queue import AnalysisTaskQueue
from src.storage import DatabaseManager


class DurableRuntimeProgressProjectionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "durable-runtime-progress.db"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.db.create_or_update_app_user(user_id="owner-a", username="owner_a")
        self.db.create_or_update_app_user(user_id="owner-b", username="owner_b")
        self.service = SystemConfigService()

    def tearDown(self) -> None:
        queue = AnalysisTaskQueue._instance
        if queue is not None:
            executor = getattr(queue, "_executor", None)
            if executor is not None and hasattr(executor, "shutdown"):
                executor.shutdown(wait=False, cancel_futures=True)
        AnalysisTaskQueue._instance = None
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def _create_task(self, task_id: str, status: str) -> None:
        self.db.create_durable_task_state(
            task_id=task_id,
            owner_user_id="owner-a",
            task_type=DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE,
            status=status,
            progress=25,
            current_step=f"Stored state {status}",
            route_family="durable-runtime-v1-prototype",
            metadata=build_durable_runtime_envelope(
                job_kind="analysis_fixture",
                fixture_name="synthetic_success",
                symbol="AAPL",
                extra_metadata={"stock_code": "AAPL", "stock_name": "Apple"},
            ),
        )

    def test_durable_progress_fallback_normalizes_stored_states_for_schema(self) -> None:
        cases = {
            "queued": "pending",
            "pending": "pending",
            "waiting_retry": "pending",
            "leased": "processing",
            "processing": "processing",
            "running": "processing",
            "completed": "completed",
            "failed": "failed",
            "cancelled": "failed",
            "canceled": "failed",
        }

        for stored_status, expected_status in cases.items():
            task_id = f"task-{stored_status.replace('_', '-')}"
            with self.subTest(stored_status=stored_status):
                self._create_task(task_id, stored_status)

                payload = self.service.get_task_progress(task_id, owner_id="owner-a")
                validated = TaskProgressResponse.model_validate(payload)

                self.assertEqual(validated.status, expected_status)
                self.assertEqual(validated.task_id, task_id)
                self.assertEqual(validated.stock_code, "AAPL")
                self.assertEqual(validated.stock_name, "Apple")

    def test_analysis_status_and_poll_use_shared_durable_status_projection(self) -> None:
        stored_statuses = (
            "queued",
            "pending",
            "waiting_retry",
            "leased",
            "processing",
            "running",
            "completed",
            "failed",
            "cancelled",
            "canceled",
        )
        terminal_statuses = {"completed", "failed", "cancelled", "canceled"}

        for stored_status in stored_statuses:
            task_id = f"task-api-{stored_status.replace('_', '-')}"
            with self.subTest(stored_status=stored_status):
                self._create_task(task_id, stored_status)

                status_response = get_analysis_status(
                    task_id,
                    current_user=SimpleNamespace(user_id="owner-a"),
                )
                poll_response = poll_analysis_task_progress(
                    task_id,
                    current_user=SimpleNamespace(user_id="owner-a"),
                )

                expected_status = normalize_durable_runtime_status(stored_status)
                self.assertEqual(status_response.status, expected_status)
                self.assertEqual(poll_response.task.status, expected_status)
                self.assertEqual(poll_response.terminal, stored_status in terminal_statuses)

    def test_tasks_progress_endpoint_durable_fallback_validates_full_status_matrix(self) -> None:
        stored_statuses = (
            "queued",
            "pending",
            "waiting_retry",
            "leased",
            "processing",
            "running",
            "completed",
            "failed",
            "cancelled",
            "canceled",
        )

        for stored_status in stored_statuses:
            task_id = f"task-progress-endpoint-{stored_status.replace('_', '-')}"
            with self.subTest(stored_status=stored_status):
                self._create_task(task_id, stored_status)

                response = get_analysis_task_progress_endpoint(
                    task_id,
                    service=self.service,
                    current_user=SimpleNamespace(user_id="owner-a"),
                )

                self.assertIsInstance(response, TaskProgressResponse)
                self.assertEqual(response.status, normalize_durable_runtime_status(stored_status))

    def test_durable_progress_fallback_remains_owner_scoped(self) -> None:
        self._create_task("task-owner-private", "leased")

        payload = self.service.get_task_progress("task-owner-private", owner_id="owner-b")

        self.assertIsNone(payload)

    def test_tasks_progress_endpoint_hides_cross_owner_durable_state(self) -> None:
        self._create_task("task-owner-private-endpoint", "leased")

        with self.assertRaises(HTTPException) as ctx:
            get_analysis_task_progress_endpoint(
                "task-owner-private-endpoint",
                service=self.service,
                current_user=SimpleNamespace(user_id="owner-b"),
            )

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["error"], "not_found")
        serialized = json.dumps(ctx.exception.detail, ensure_ascii=False)
        self.assertNotIn("owner-a", serialized)
        self.assertNotIn("Apple", serialized)

    def test_analysis_status_uses_same_waiting_retry_projection(self) -> None:
        self._create_task("task-waiting-retry-status", "waiting_retry")

        response = get_analysis_status(
            "task-waiting-retry-status",
            current_user=SimpleNamespace(user_id="owner-a"),
        )

        self.assertEqual(response.status, "pending")


if __name__ == "__main__":
    unittest.main()
