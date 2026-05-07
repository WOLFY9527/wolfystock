# -*- coding: utf-8 -*-
"""WS2-R2 durable task worker prototype tests."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

from api.v1.endpoints.analysis import get_analysis_status, poll_analysis_task_progress
from src.services.durable_task_worker import (
    SYNTHETIC_TASK_TYPE,
    DurableTaskWorkerPrototype,
)
from src.storage import DatabaseManager


class DurableTaskWorkerPrototypeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "ws2-worker.db"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.db.create_or_update_app_user(user_id="user-a", username="alice")
        self.db.create_or_update_app_user(user_id="user-b", username="bob")

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def _create_task(self, task_id: str, **metadata: object) -> dict:
        return self.db.create_durable_task_state(
            task_id=task_id,
            owner_user_id="user-a",
            task_type=SYNTHETIC_TASK_TYPE,
            status="queued",
            current_step="Queued",
            max_attempts=int(metadata.pop("max_attempts", 3)),
            metadata={"stock_code": "AAPL", **metadata},
        )

    def test_worker_claims_queued_task_and_completes_it(self) -> None:
        self._create_task("task-complete")
        worker = DurableTaskWorkerPrototype(db=self.db, worker_id="worker-a")

        result = worker.run_once()
        state = self.db.get_durable_task_state(task_id="task-complete", owner_user_id="user-a")
        events = self.db.list_durable_task_progress_events(
            task_id="task-complete",
            owner_user_id="user-a",
        )

        self.assertEqual(result.status, "completed")
        self.assertIsNotNone(state)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["progress"], 100)
        self.assertEqual(state["attempt_count"], 1)
        self.assertIsNone(state["lease_owner"])
        self.assertEqual(state["metadata"]["result_ref"], "fixture:ws2-synthetic")
        self.assertEqual([event["event_type"] for event in events], ["claimed", "progress", "progress", "completed"])
        self.assertEqual(events[-1]["message_safe"], "Synthetic task complete")

    def test_worker_failure_stores_sanitized_error(self) -> None:
        self._create_task("task-sanitized", failure_mode="non_retryable")
        worker = DurableTaskWorkerPrototype(db=self.db, worker_id="worker-a")

        result = worker.run_once()
        state = self.db.get_durable_task_state(task_id="task-sanitized", owner_user_id="user-a")
        events = self.db.list_durable_task_progress_events(
            task_id="task-sanitized",
            owner_user_id="user-a",
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["error_code"], "non_retryable_synthetic_error")
        self.assertNotIn("Traceback", json.dumps(state, ensure_ascii=False))
        self.assertNotIn("api_key", json.dumps(state, ensure_ascii=False))
        self.assertEqual(events[-1]["event_type"], "failed")
        self.assertNotIn("Traceback", json.dumps(events[-1], ensure_ascii=False))

    def test_transient_synthetic_failure_retries_until_bounded_cap(self) -> None:
        self._create_task(
            "task-transient",
            failure_mode="transient",
            transient_failures_remaining=2,
            max_attempts=3,
        )
        worker = DurableTaskWorkerPrototype(db=self.db, worker_id="worker-a")

        self.assertEqual(worker.run_once().status, "retry_queued")
        self.assertEqual(worker.run_once().status, "retry_queued")
        self.assertEqual(worker.run_once().status, "completed")
        state = self.db.get_durable_task_state(task_id="task-transient", owner_user_id="user-a")

        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["attempt_count"], 3)
        self.assertEqual(state["metadata"]["transient_failures_remaining"], 0)

    def test_transient_synthetic_failure_stops_at_max_attempts(self) -> None:
        self._create_task(
            "task-transient-cap",
            failure_mode="transient",
            transient_failures_remaining=3,
            max_attempts=2,
        )
        worker = DurableTaskWorkerPrototype(db=self.db, worker_id="worker-a")

        self.assertEqual(worker.run_once().status, "retry_queued")
        self.assertEqual(worker.run_once().status, "failed")
        state = self.db.get_durable_task_state(task_id="task-transient-cap", owner_user_id="user-a")

        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["attempt_count"], 2)
        self.assertEqual(state["error_code"], "transient_synthetic_error")

    def test_non_retryable_failure_does_not_retry(self) -> None:
        self._create_task("task-terminal", failure_mode="non_retryable", max_attempts=3)
        worker = DurableTaskWorkerPrototype(db=self.db, worker_id="worker-a")

        self.assertEqual(worker.run_once().status, "failed")
        self.assertEqual(worker.run_once().status, "idle")
        state = self.db.get_durable_task_state(task_id="task-terminal", owner_user_id="user-a")

        self.assertEqual(state["attempt_count"], 1)
        self.assertEqual(state["status"], "failed")

    def test_two_workers_do_not_both_complete_same_task(self) -> None:
        self._create_task("task-single-claim")
        first_claim = self.db.claim_next_durable_task_state(
            worker_id="worker-a",
            task_type=SYNTHETIC_TASK_TYPE,
        )
        second_claim = self.db.claim_next_durable_task_state(
            worker_id="worker-b",
            task_type=SYNTHETIC_TASK_TYPE,
        )

        self.assertIsNotNone(first_claim)
        self.assertIsNone(second_claim)
        self.assertIsNotNone(
            self.db.complete_claimed_durable_task_state(
                task_id="task-single-claim",
                worker_id="worker-a",
            )
        )
        self.assertIsNone(
            self.db.complete_claimed_durable_task_state(
                task_id="task-single-claim",
                worker_id="worker-b",
            )
        )

    def test_expired_lease_can_be_reclaimed_by_another_worker(self) -> None:
        self._create_task("task-expired-lease")
        first_claim = self.db.claim_next_durable_task_state(
            worker_id="worker-a",
            task_type=SYNTHETIC_TASK_TYPE,
            lease_seconds=1,
        )
        self.assertIsNotNone(first_claim)
        claimed_at = datetime.fromisoformat(first_claim["started_at"])
        self.db.heartbeat_durable_task_state(
            task_id="task-expired-lease",
            worker_id="worker-a",
            lease_seconds=1,
            progress=25,
            current_step="Worker stalled",
            now=claimed_at,
        )

        expired_time = datetime.fromisoformat(first_claim["lease_expires_at"]) + timedelta(seconds=1)
        second_claim = self.db.claim_next_durable_task_state(
            worker_id="worker-b",
            task_type=SYNTHETIC_TASK_TYPE,
            now=expired_time,
        )
        stale_complete = self.db.complete_claimed_durable_task_state(
            task_id="task-expired-lease",
            worker_id="worker-a",
            now=expired_time,
        )

        self.assertIsNotNone(second_claim)
        self.assertEqual(second_claim["lease_owner"], "worker-b")
        self.assertEqual(second_claim["attempt_count"], 2)
        self.assertIsNone(stale_complete)

    def test_graceful_shutdown_stops_between_stages_without_terminal_state(self) -> None:
        self._create_task("task-shutdown")
        worker_holder = {}

        def request_shutdown(stage: str, _task: dict) -> None:
            if stage == "stage_1":
                worker_holder["worker"].request_shutdown()

        worker = DurableTaskWorkerPrototype(
            db=self.db,
            worker_id="worker-a",
            stage_hook=request_shutdown,
        )
        worker_holder["worker"] = worker

        result = worker.run_once()
        state = self.db.get_durable_task_state(task_id="task-shutdown", owner_user_id="user-a")

        self.assertEqual(result.status, "shutdown_requested")
        self.assertEqual(state["status"], "processing")
        self.assertEqual(state["progress"], 20)
        self.assertEqual(state["lease_owner"], "worker-a")
        self.assertIsNone(state["completed_at"])
        self.assertIsNone(state["failed_at"])
        events = self.db.list_durable_task_progress_events(
            task_id="task-shutdown",
            owner_user_id="user-a",
        )
        self.assertEqual([event["event_type"] for event in events], ["claimed", "progress"])

    def test_owner_scoped_status_remains_intact_for_worker_task(self) -> None:
        self._create_task("task-owner-status")
        worker = DurableTaskWorkerPrototype(db=self.db, worker_id="worker-a")
        worker.run_once()

        own = get_analysis_status("task-owner-status", current_user=SimpleNamespace(user_id="user-a"))
        self.assertEqual(own.task_id, "task-owner-status")
        self.assertEqual(own.status, "completed")

        with self.assertRaises(HTTPException) as ctx:
            get_analysis_status("task-owner-status", current_user=SimpleNamespace(user_id="user-b"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_failed_worker_task_remains_pollable_with_sanitized_payload(self) -> None:
        self._create_task(
            "task-failed-pollable",
            failure_mode="non_retryable",
            api_key="not-a-real-key",
        )
        worker = DurableTaskWorkerPrototype(db=self.db, worker_id="worker-a")

        result = worker.run_once()
        response = poll_analysis_task_progress(
            "task-failed-pollable",
            current_user=SimpleNamespace(user_id="user-a"),
        )
        serialized = json.dumps(response.model_dump(), ensure_ascii=False)

        self.assertEqual(result.status, "failed")
        self.assertEqual(response.task.status, "failed")
        self.assertEqual(response.task.progress, 100)
        self.assertTrue(response.terminal)
        self.assertEqual(response.events[-1].event_type, "failed")
        self.assertEqual(response.events[-1].metadata["error_code"], "non_retryable_synthetic_error")
        self.assertNotIn("Traceback", serialized)
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("not-a-real-key", serialized)

    def test_dependency_manifests_do_not_add_external_worker_stack(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        manifests = [
            repo_root / "requirements.txt",
            repo_root / "pyproject.toml",
            repo_root / "setup.py",
        ]
        combined = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore").lower()
            for path in manifests
            if path.exists()
        )

        for forbidden in ("celery", "rq", "dramatiq", "kafka"):
            self.assertNotIn(forbidden, combined)
        self.assertNotRegex(combined, r"(?m)^\s*redis([<=>\s].*)?$")

    def test_worker_uses_only_synthetic_fixture_path(self) -> None:
        self._create_task("task-fixture-only")
        worker = DurableTaskWorkerPrototype(db=self.db, worker_id="worker-a")

        result = worker.run_once()
        state = self.db.get_durable_task_state(task_id="task-fixture-only", owner_user_id="user-a")

        self.assertEqual(result.status, "completed")
        self.assertEqual(state["task_type"], SYNTHETIC_TASK_TYPE)
        self.assertEqual(state["metadata"]["result_ref"], "fixture:ws2-synthetic")


if __name__ == "__main__":
    unittest.main()
