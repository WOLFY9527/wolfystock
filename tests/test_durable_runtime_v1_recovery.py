# -*- coding: utf-8 -*-
"""Durable Runtime v1 recovery and owner-isolation tests."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

from api.v1.endpoints.analysis import get_analysis_status, poll_analysis_task_progress
from src.services.durable_runtime_contracts import DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE
from src.services.durable_runtime_v1 import (
    DurableRuntimeV1PrototypeWorker,
    create_synthetic_runtime_task,
)
from src.storage import DatabaseManager


class DurableRuntimeV1RecoveryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "durable-runtime-v1-recovery.db"
        self.db = self._open_db()
        self.db.create_or_update_app_user(user_id="owner-a", username="owner_a")
        self.db.create_or_update_app_user(user_id="owner-b", username="owner_b")

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def _open_db(self) -> DatabaseManager:
        DatabaseManager.reset_instance()
        return DatabaseManager(db_url=f"sqlite:///{self.db_path}")

    @staticmethod
    def _user(owner_id: str) -> SimpleNamespace:
        return SimpleNamespace(user_id=owner_id)

    def _create_task(self, task_id: str, *, fixture_name: str = "synthetic_success", **metadata: object) -> None:
        create_synthetic_runtime_task(
            db=DatabaseManager.get_instance(),
            task_id=task_id,
            owner_user_id="owner-a",
            job_kind="analysis_fixture",
            fixture_name=fixture_name,
            symbol="AAPL",
            metadata=metadata,
        )

    def test_completed_fixture_is_visible_from_fresh_api_process_memory(self) -> None:
        self._create_task("runtime-api-b-visible")
        worker = DurableRuntimeV1PrototypeWorker(db=DatabaseManager.get_instance(), worker_id="worker-a")
        worker.run_once()

        self._open_db()
        status = get_analysis_status("runtime-api-b-visible", current_user=self._user("owner-a"))
        poll = poll_analysis_task_progress(
            "runtime-api-b-visible",
            after_sequence=1,
            limit=3,
            current_user=self._user("owner-a"),
        )

        self.assertEqual(status.status, "completed")
        self.assertEqual(status.progress, 100)
        self.assertTrue(poll.terminal)
        self.assertEqual([event.sequence for event in poll.events], [2, 3, 4])

    def test_status_and_poll_hide_cross_owner_durable_task(self) -> None:
        self._create_task("runtime-owner-hidden")
        worker = DurableRuntimeV1PrototypeWorker(db=DatabaseManager.get_instance(), worker_id="worker-a")
        worker.run_once()

        self._open_db()
        for read_call in (
            lambda: get_analysis_status("runtime-owner-hidden", current_user=self._user("owner-b")),
            lambda: poll_analysis_task_progress("runtime-owner-hidden", current_user=self._user("owner-b")),
        ):
            with self.subTest(read_call=read_call):
                with self.assertRaises(HTTPException) as ctx:
                    read_call()
                self.assertEqual(ctx.exception.status_code, 404)
                self.assertEqual(ctx.exception.detail["error"], "not_found")
                serialized = json.dumps(ctx.exception.detail, ensure_ascii=False)
                self.assertNotIn("owner-a", serialized)
                self.assertNotIn("AAPL", serialized)

    def test_expired_lease_can_recover_and_stale_worker_cannot_finish(self) -> None:
        self._create_task("runtime-expired-recover")
        worker_holder = {}

        def stop_after_prepare(stage: str, _task: dict) -> None:
            if stage == "prepare":
                worker_holder["worker"].request_shutdown()

        worker_a = DurableRuntimeV1PrototypeWorker(
            db=DatabaseManager.get_instance(),
            worker_id="worker-a",
            lease_seconds=1,
            stage_hook=stop_after_prepare,
        )
        worker_holder["worker"] = worker_a

        result = worker_a.run_once()
        stalled = DatabaseManager.get_instance().get_durable_task_state(
            task_id="runtime-expired-recover",
            owner_user_id="owner-a",
        )
        expired_time = datetime.fromisoformat(stalled["lease_expires_at"]) + timedelta(seconds=1)

        fresh_db = self._open_db()
        recovered_claim = fresh_db.claim_next_durable_task_state(
            worker_id="worker-b",
            task_type=DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE,
            lease_seconds=60,
            now=expired_time,
        )
        stale_complete = fresh_db.complete_claimed_durable_task_state(
            task_id="runtime-expired-recover",
            worker_id="worker-a",
            claim_attempt=stalled["attempt_count"],
            now=expired_time,
        )
        recovered_complete = fresh_db.complete_claimed_durable_task_state(
            task_id="runtime-expired-recover",
            worker_id="worker-b",
            claim_attempt=recovered_claim["attempt_count"],
            current_step="Recovered fixture complete",
            metadata={"result_ref": "fixture:analysis_fixture:synthetic_success"},
            now=expired_time,
        )

        self.assertEqual(result.status, "shutdown_requested")
        self.assertEqual(stalled["status"], "processing")
        self.assertEqual(stalled["lease_owner"], "worker-a")
        self.assertIsNotNone(recovered_claim)
        self.assertEqual(recovered_claim["lease_owner"], "worker-b")
        self.assertEqual(recovered_claim["attempt_count"], 2)
        self.assertIsNone(stale_complete)
        self.assertIsNotNone(recovered_complete)
        self.assertEqual(recovered_complete["status"], "completed")

    def test_terminal_failure_is_pollable_and_sanitized(self) -> None:
        self._create_task("runtime-terminal-failure", fixture_name="terminal_failure", api_key="not-a-real-key")
        worker = DurableRuntimeV1PrototypeWorker(db=DatabaseManager.get_instance(), worker_id="worker-a")

        result = worker.run_once()
        self._open_db()
        poll = poll_analysis_task_progress("runtime-terminal-failure", current_user=self._user("owner-a"))
        serialized = json.dumps(poll.model_dump(), ensure_ascii=False)

        self.assertEqual(result.status, "failed")
        self.assertEqual(poll.task.status, "failed")
        self.assertTrue(poll.terminal)
        self.assertEqual(poll.events[-1].event_type, "failed")
        self.assertNotIn("not-a-real-key", serialized)
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("Traceback", serialized)


if __name__ == "__main__":
    unittest.main()
