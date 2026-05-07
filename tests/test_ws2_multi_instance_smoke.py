# -*- coding: utf-8 -*-
"""WS2 synthetic multi-instance durable task smoke tests."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from api.v1.endpoints.analysis import get_analysis_status, poll_analysis_task_progress
from src.services.durable_task_worker import (
    SYNTHETIC_TASK_TYPE,
    DurableTaskWorkerPrototype,
)
from src.storage import DatabaseManager


class _EmptyProcessLocalQueue:
    def get_task(self, _task_id: str, *, owner_id: str | None = None) -> None:
        return None


class Ws2MultiInstanceSmokeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "ws2-multi-instance.db"
        self._open_instance_db()
        self._seed_users()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def _open_instance_db(self) -> DatabaseManager:
        DatabaseManager.reset_instance()
        return DatabaseManager(db_url=f"sqlite:///{self.db_path}")

    def _seed_users(self) -> None:
        db = DatabaseManager.get_instance()
        db.create_or_update_app_user(user_id="owner-a", username="alice")
        db.create_or_update_app_user(user_id="owner-b", username="bob")

    def _api_user(self, owner_id: str) -> SimpleNamespace:
        return SimpleNamespace(user_id=owner_id)

    def _api_create_synthetic_task(self, task_id: str, owner_id: str) -> dict:
        db = self._open_instance_db()
        return db.create_durable_task_state(
            task_id=task_id,
            owner_user_id=owner_id,
            task_type=SYNTHETIC_TASK_TYPE,
            status="queued",
            current_step="Queued by API instance",
            max_attempts=3,
            metadata={"stock_code": "AAPL", "selection_source": "manual"},
        )

    def _status_from_fresh_api_instance(self, task_id: str, owner_id: str):
        self._open_instance_db()
        with patch("api.v1.endpoints.analysis.get_task_queue", return_value=_EmptyProcessLocalQueue()):
            return get_analysis_status(task_id, current_user=self._api_user(owner_id))

    def _poll_from_fresh_api_instance(
        self,
        task_id: str,
        owner_id: str,
        *,
        after_sequence: int | None = None,
    ):
        self._open_instance_db()
        with patch("api.v1.endpoints.analysis.get_task_queue", return_value=_EmptyProcessLocalQueue()):
            return poll_analysis_task_progress(
                task_id,
                after_sequence=after_sequence,
                current_user=self._api_user(owner_id),
            )

    def test_api_worker_polling_instances_share_durable_task_state(self) -> None:
        created = self._api_create_synthetic_task("ws2-smoke-owner-a", "owner-a")
        self.assertEqual(created["status"], "queued")

        worker_db = self._open_instance_db()
        worker = DurableTaskWorkerPrototype(db=worker_db, worker_id="worker-b")
        worker_result = worker.run_once()

        status = self._status_from_fresh_api_instance("ws2-smoke-owner-a", "owner-a")
        poll = self._poll_from_fresh_api_instance("ws2-smoke-owner-a", "owner-a", after_sequence=1)

        self.assertEqual(worker_result.status, "completed")
        self.assertEqual(status.task_id, "ws2-smoke-owner-a")
        self.assertEqual(status.status, "completed")
        self.assertEqual(status.progress, 100)
        self.assertEqual(poll.task.status, "completed")
        self.assertTrue(poll.terminal)
        self.assertEqual(poll.latest_sequence, 4)
        self.assertEqual([event.sequence for event in poll.events], [2, 3, 4])
        self.assertEqual(poll.events[-1].event_type, "completed")

    def test_cross_owner_status_and_polling_hide_task_existence(self) -> None:
        self._api_create_synthetic_task("ws2-smoke-private", "owner-a")
        worker = DurableTaskWorkerPrototype(db=self._open_instance_db(), worker_id="worker-b")
        self.assertEqual(worker.run_once().status, "completed")

        with self.assertRaises(HTTPException) as status_ctx:
            self._status_from_fresh_api_instance("ws2-smoke-private", "owner-b")
        with self.assertRaises(HTTPException) as poll_ctx:
            self._poll_from_fresh_api_instance("ws2-smoke-private", "owner-b")

        self.assertEqual(status_ctx.exception.status_code, 404)
        self.assertEqual(poll_ctx.exception.status_code, 404)
        serialized = json.dumps(
            {
                "status": status_ctx.exception.detail,
                "poll": poll_ctx.exception.detail,
            },
            ensure_ascii=False,
        )
        self.assertNotIn("owner-a", serialized)
        self.assertNotIn("alice", serialized)

    def test_stale_worker_lease_is_visible_and_reclaimable_once_expired(self) -> None:
        self._api_create_synthetic_task("ws2-smoke-stale-lease", "owner-a")
        worker_a_db = self._open_instance_db()
        first_claim = worker_a_db.claim_next_durable_task_state(
            worker_id="worker-a",
            task_type=SYNTHETIC_TASK_TYPE,
            lease_seconds=1,
        )
        self.assertIsNotNone(first_claim)
        started_at = datetime.fromisoformat(first_claim["started_at"])
        worker_a_db.heartbeat_durable_task_state(
            task_id="ws2-smoke-stale-lease",
            worker_id="worker-a",
            lease_seconds=1,
            progress=35,
            current_step="Synthetic worker stalled",
            now=started_at,
        )

        visible = self._status_from_fresh_api_instance("ws2-smoke-stale-lease", "owner-a")
        self.assertEqual(visible.status, "processing")
        self.assertEqual(visible.progress, 35)

        expired_time = datetime.fromisoformat(first_claim["lease_expires_at"]) + timedelta(seconds=1)
        worker_b_db = self._open_instance_db()
        second_claim = worker_b_db.claim_next_durable_task_state(
            worker_id="worker-b",
            task_type=SYNTHETIC_TASK_TYPE,
            now=expired_time,
        )
        stale_complete = worker_b_db.complete_claimed_durable_task_state(
            task_id="ws2-smoke-stale-lease",
            worker_id="worker-a",
            now=expired_time,
        )
        recovered_complete = worker_b_db.complete_claimed_durable_task_state(
            task_id="ws2-smoke-stale-lease",
            worker_id="worker-b",
            current_step="Recovered by worker B",
            metadata={"result_ref": "fixture:ws2-recovered"},
            now=expired_time,
        )

        final_status = self._status_from_fresh_api_instance("ws2-smoke-stale-lease", "owner-a")
        final_poll = self._poll_from_fresh_api_instance("ws2-smoke-stale-lease", "owner-a")

        self.assertIsNotNone(second_claim)
        self.assertEqual(second_claim["lease_owner"], "worker-b")
        self.assertEqual(second_claim["attempt_count"], 2)
        self.assertIsNone(stale_complete)
        self.assertIsNotNone(recovered_complete)
        self.assertEqual(final_status.status, "completed")
        self.assertEqual(final_status.progress, 100)
        self.assertTrue(final_poll.terminal)

    def test_progress_replay_survives_worker_handoff(self) -> None:
        self._api_create_synthetic_task("ws2-smoke-handoff", "owner-a")
        worker_a_db = self._open_instance_db()
        first_claim = worker_a_db.claim_next_durable_task_state(
            worker_id="worker-a",
            task_type=SYNTHETIC_TASK_TYPE,
            lease_seconds=1,
        )
        self.assertIsNotNone(first_claim)
        worker_a_db.heartbeat_durable_task_state(
            task_id="ws2-smoke-handoff",
            worker_id="worker-a",
            lease_seconds=1,
            progress=22,
            current_step="Worker A progress",
            now=datetime.fromisoformat(first_claim["started_at"]),
        )
        worker_a_db.append_durable_task_progress_event(
            task_id="ws2-smoke-handoff",
            owner_user_id="owner-a",
            event_type="progress",
            stage="worker-a",
            progress=22,
            message="Worker A progress",
        )

        expired_time = datetime.fromisoformat(first_claim["lease_expires_at"]) + timedelta(seconds=1)
        worker_b_db = self._open_instance_db()
        second_claim = worker_b_db.claim_next_durable_task_state(
            worker_id="worker-b",
            task_type=SYNTHETIC_TASK_TYPE,
            now=expired_time,
        )
        self.assertIsNotNone(second_claim)
        worker_b_db.append_durable_task_progress_event(
            task_id="ws2-smoke-handoff",
            owner_user_id="owner-a",
            event_type="progress",
            stage="worker-b",
            progress=61,
            message="Worker B resumed",
        )
        worker_b_db.heartbeat_durable_task_state(
            task_id="ws2-smoke-handoff",
            worker_id="worker-b",
            lease_seconds=1,
            progress=61,
            current_step="Worker B resumed",
            now=expired_time,
        )
        recovered_complete = worker_b_db.complete_claimed_durable_task_state(
            task_id="ws2-smoke-handoff",
            worker_id="worker-b",
            current_step="Recovered by worker B",
            metadata={"result_ref": "fixture:ws2-replayed"},
            now=expired_time,
        )
        worker_b_db.append_durable_task_progress_event(
            task_id="ws2-smoke-handoff",
            owner_user_id="owner-a",
            event_type="completed",
            stage="worker-b-complete",
            progress=100,
            message="Worker B completed",
            metadata={"result_ref": "fixture:ws2-replayed"},
        )

        poll = self._poll_from_fresh_api_instance("ws2-smoke-handoff", "owner-a")
        self.assertIsNotNone(recovered_complete)
        self.assertEqual(poll.task.status, "completed")
        self.assertEqual([event.sequence for event in poll.events], [1, 2, 3])
        self.assertEqual(poll.events[-1].metadata["result_ref"], "fixture:ws2-replayed")
        self.assertEqual(poll.latest_sequence, 3)

    def test_owner_isolation_stays_intact_after_reclaim(self) -> None:
        self._api_create_synthetic_task("ws2-smoke-owner-lock", "owner-a")
        worker_a_db = self._open_instance_db()
        first_claim = worker_a_db.claim_next_durable_task_state(
            worker_id="worker-a",
            task_type=SYNTHETIC_TASK_TYPE,
            lease_seconds=1,
        )
        self.assertIsNotNone(first_claim)
        expired_time = datetime.fromisoformat(first_claim["lease_expires_at"]) + timedelta(seconds=1)
        worker_b_db = self._open_instance_db()
        second_claim = worker_b_db.claim_next_durable_task_state(
            worker_id="worker-b",
            task_type=SYNTHETIC_TASK_TYPE,
            now=expired_time,
        )
        worker_b_db.complete_claimed_durable_task_state(
            task_id="ws2-smoke-owner-lock",
            worker_id="worker-b",
            now=expired_time,
        )

        with self.assertRaises(HTTPException) as status_ctx:
            self._status_from_fresh_api_instance("ws2-smoke-owner-lock", "owner-b")
        with self.assertRaises(HTTPException) as poll_ctx:
            self._poll_from_fresh_api_instance("ws2-smoke-owner-lock", "owner-b")

        self.assertIsNotNone(second_claim)
        self.assertEqual(status_ctx.exception.status_code, 404)
        self.assertEqual(poll_ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
