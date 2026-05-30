# -*- coding: utf-8 -*-
"""WS2-R1 durable task state foundation tests."""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import text

from api.v1.endpoints.analysis import _format_sse_event, get_analysis_status, poll_analysis_task_progress
from src.storage import DatabaseManager
from src.services.task_queue import AnalysisTaskQueue


class DurableTaskStateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "durable-task-state.db"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.db.create_or_update_app_user(user_id="user-a", username="alice")
        self.db.create_or_update_app_user(user_id="user-b", username="bob")

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def test_durable_task_create_read_update_lifecycle(self) -> None:
        created = self.db.create_durable_task_state(
            task_id="task-lifecycle",
            owner_user_id="user-a",
            task_type="analysis",
            status="pending",
            progress=0,
            current_step="Queued",
            dedupe_key="user-a:AAPL.US",
            metadata={"stock_code": "AAPL.US", "api_key": "not-a-real-key"},
        )

        self.assertEqual(created["task_id"], "task-lifecycle")
        self.assertEqual(created["owner_user_id"], "user-a")
        self.assertNotIn("api_key", created["metadata"])

        updated = self.db.update_durable_task_state(
            task_id="task-lifecycle",
            owner_user_id="user-a",
            status="processing",
            progress=42,
            current_step="Analyzing signals",
            metadata={"stage": "signals"},
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated["status"], "processing")
        self.assertEqual(updated["progress"], 42)
        self.assertEqual(updated["metadata"]["stock_code"], "AAPL.US")
        self.assertEqual(updated["metadata"]["stage"], "signals")

        completed = self.db.mark_durable_task_completed(
            task_id="task-lifecycle",
            owner_user_id="user-a",
        )

        self.assertIsNotNone(completed)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["progress"], 100)
        self.assertIsNotNone(completed["completed_at"])

    def test_active_durable_task_reservation_returns_existing_duplicate(self) -> None:
        created, duplicate = self.db.reserve_durable_task_state(
            task_id="task-active-a",
            owner_user_id="user-a",
            task_type="analysis",
            status="pending",
            progress=0,
            current_step="Queued",
            dedupe_key="user-a:AAPL.US",
            metadata={"stock_code": "AAPL.US"},
        )

        second, second_duplicate = self.db.reserve_durable_task_state(
            task_id="task-active-b",
            owner_user_id="user-a",
            task_type="analysis",
            status="pending",
            progress=0,
            current_step="Queued",
            dedupe_key="user-a:AAPL.US",
            metadata={"stock_code": "AAPL.US"},
        )

        self.assertIsNotNone(created)
        self.assertIsNone(duplicate)
        self.assertIsNone(second)
        self.assertIsNotNone(second_duplicate)
        self.assertEqual(second_duplicate["task_id"], "task-active-a")
        self.assertIsNone(self.db.get_durable_task_state(task_id="task-active-b", owner_user_id="user-a"))

    def test_active_durable_reservation_honors_legacy_dedupe_hash_rows(self) -> None:
        created = self.db.create_durable_task_state(
            task_id="task-legacy-active",
            owner_user_id="user-a",
            task_type="analysis",
            status="pending",
            dedupe_key="user-a:NVDA.US",
            metadata={"stock_code": "NVDA.US"},
        )
        with self.db._engine.begin() as conn:
            conn.execute(
                text("UPDATE durable_task_states SET active_dedupe_key_hash = NULL WHERE task_id = :task_id"),
                {"task_id": created["task_id"]},
            )

        second, duplicate = self.db.reserve_durable_task_state(
            task_id="task-legacy-duplicate",
            owner_user_id="user-a",
            task_type="analysis",
            status="pending",
            dedupe_key="user-a:NVDA.US",
            metadata={"stock_code": "NVDA.US"},
        )

        self.assertIsNone(second)
        self.assertIsNotNone(duplicate)
        self.assertEqual(duplicate["task_id"], "task-legacy-active")

    def test_terminal_durable_task_reservation_releases_dedupe_slot(self) -> None:
        created, duplicate = self.db.reserve_durable_task_state(
            task_id="task-terminal-a",
            owner_user_id="user-a",
            task_type="analysis",
            status="pending",
            dedupe_key="user-a:MSFT.US",
            metadata={"stock_code": "MSFT.US"},
        )
        self.assertIsNotNone(created)
        self.assertIsNone(duplicate)

        self.db.mark_durable_task_completed(task_id="task-terminal-a", owner_user_id="user-a")
        second, second_duplicate = self.db.reserve_durable_task_state(
            task_id="task-terminal-b",
            owner_user_id="user-a",
            task_type="analysis",
            status="pending",
            dedupe_key="user-a:MSFT.US",
            metadata={"stock_code": "MSFT.US"},
        )
        self.assertIsNotNone(second)
        self.assertIsNone(second_duplicate)

        self.db.mark_durable_task_failed(
            task_id="task-terminal-b",
            owner_user_id="user-a",
            error_code="fixture_failed",
            error_summary="fixture failed",
        )
        third, third_duplicate = self.db.reserve_durable_task_state(
            task_id="task-terminal-c",
            owner_user_id="user-a",
            task_type="analysis",
            status="pending",
            dedupe_key="user-a:MSFT.US",
            metadata={"stock_code": "MSFT.US"},
        )
        self.assertIsNotNone(third)
        self.assertIsNone(third_duplicate)

    def test_durable_task_reservation_is_owner_scoped(self) -> None:
        first, first_duplicate = self.db.reserve_durable_task_state(
            task_id="task-owner-a",
            owner_user_id="user-a",
            task_type="analysis",
            status="pending",
            dedupe_key="user-a:TSLA.US",
            metadata={"stock_code": "TSLA.US"},
        )
        second, second_duplicate = self.db.reserve_durable_task_state(
            task_id="task-owner-b",
            owner_user_id="user-b",
            task_type="analysis",
            status="pending",
            dedupe_key="user-b:TSLA.US",
            metadata={"stock_code": "TSLA.US"},
        )

        self.assertIsNotNone(first)
        self.assertIsNone(first_duplicate)
        self.assertIsNotNone(second)
        self.assertIsNone(second_duplicate)

    def test_owner_can_read_own_durable_task_status(self) -> None:
        self.db.create_durable_task_state(
            task_id="task-owned",
            owner_user_id="user-a",
            task_type="analysis",
            status="processing",
            progress=35,
            current_step="Loading quote",
            metadata={"stock_code": "TSLA", "stock_name": "Tesla", "selection_source": "manual"},
        )

        response = get_analysis_status("task-owned", current_user=SimpleNamespace(user_id="user-a"))

        self.assertEqual(response.task_id, "task-owned")
        self.assertEqual(response.status, "processing")
        self.assertEqual(response.progress, 35)
        self.assertEqual(response.stock_name, "Tesla")
        self.assertEqual(response.selection_source, "manual")
        self.assertIsNone(response.result)

    def test_other_user_gets_sanitized_not_found_for_durable_task(self) -> None:
        self.db.create_durable_task_state(
            task_id="task-private",
            owner_user_id="user-a",
            task_type="analysis",
            status="processing",
            progress=10,
            metadata={"stock_code": "MSFT"},
        )

        with self.assertRaises(HTTPException) as ctx:
            get_analysis_status("task-private", current_user=SimpleNamespace(user_id="user-b"))

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["error"], "not_found")
        self.assertNotIn("user-a", json.dumps(ctx.exception.detail))

    def test_failed_task_stores_sanitized_error_summary(self) -> None:
        self.db.create_durable_task_state(
            task_id="task-failed",
            owner_user_id="user-a",
            task_type="analysis",
            metadata={"stock_code": "NVDA", "token": "not-a-real-token"},
        )

        failed = self.db.mark_durable_task_failed(
            task_id="task-failed",
            owner_user_id="user-a",
            error_code="RuntimeError",
            error_summary=(
                "Traceback (most recent call last):\n"
                "RuntimeError: provider failed Authorization: Bearer not-a-real-token api_key=not-a-real-key"
            ),
        )

        self.assertIsNotNone(failed)
        serialized = json.dumps(failed, ensure_ascii=False)
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error_summary"], "Task failed; see server logs for sanitized details")
        self.assertNotIn("not-a-real-token", serialized)
        self.assertNotIn("not-a-real-key", serialized)
        self.assertNotIn("Traceback", serialized)
        self.assertNotIn("token", failed["metadata"])

    def test_progress_event_append_increments_sequence(self) -> None:
        self.db.create_durable_task_state(
            task_id="task-progress-sequence",
            owner_user_id="user-a",
            task_type="analysis",
        )

        first = self.db.append_durable_task_progress_event(
            task_id="task-progress-sequence",
            owner_user_id="user-a",
            event_type="progress",
            stage="stage-1",
            progress=10,
            message="Stage 1",
        )
        second = self.db.append_durable_task_progress_event(
            task_id="task-progress-sequence",
            owner_user_id="user-a",
            event_type="progress",
            stage="stage-2",
            progress=20,
            message="Stage 2",
        )

        self.assertEqual(first["sequence"], 1)
        self.assertEqual(second["sequence"], 2)

    def test_owner_can_list_own_progress_events(self) -> None:
        self.db.create_durable_task_state(
            task_id="task-progress-owned",
            owner_user_id="user-a",
            task_type="analysis",
        )
        self.db.append_durable_task_progress_event(
            task_id="task-progress-owned",
            owner_user_id="user-a",
            event_type="progress",
            progress=25,
            message="Owned event",
        )

        events = self.db.list_durable_task_progress_events(
            task_id="task-progress-owned",
            owner_user_id="user-a",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["message_safe"], "Owned event")

    def test_other_owner_cannot_read_progress_events(self) -> None:
        self.db.create_durable_task_state(
            task_id="task-progress-private",
            owner_user_id="user-a",
            task_type="analysis",
        )
        self.db.append_durable_task_progress_event(
            task_id="task-progress-private",
            owner_user_id="user-a",
            event_type="progress",
            progress=25,
            message="Private event",
        )

        events = self.db.list_durable_task_progress_events(
            task_id="task-progress-private",
            owner_user_id="user-b",
        )

        self.assertEqual(events, [])

    def test_progress_events_after_sequence_returns_newer_only(self) -> None:
        self.db.create_durable_task_state(
            task_id="task-progress-after",
            owner_user_id="user-a",
            task_type="analysis",
        )
        for progress in (10, 20, 30):
            self.db.append_durable_task_progress_event(
                task_id="task-progress-after",
                owner_user_id="user-a",
                event_type="progress",
                progress=progress,
                message=f"Progress {progress}",
            )

        events = self.db.list_durable_task_progress_events_after(
            task_id="task-progress-after",
            owner_user_id="user-a",
            after_sequence=1,
        )

        self.assertEqual([event["sequence"] for event in events], [2, 3])

    def test_progress_event_limit_is_bounded(self) -> None:
        self.db.create_durable_task_state(
            task_id="task-progress-limit",
            owner_user_id="user-a",
            task_type="analysis",
        )
        for index in range(105):
            self.db.append_durable_task_progress_event(
                task_id="task-progress-limit",
                owner_user_id="user-a",
                event_type="progress",
                progress=index % 100,
                message=f"Progress {index}",
            )

        events = self.db.list_durable_task_progress_events(
            task_id="task-progress-limit",
            owner_user_id="user-a",
            limit=500,
        )

        self.assertEqual(len(events), 100)
        self.assertEqual(events[0]["sequence"], 1)
        self.assertEqual(events[-1]["sequence"], 100)

    def test_progress_event_sanitizes_metadata_and_message(self) -> None:
        self.db.create_durable_task_state(
            task_id="task-progress-sanitized",
            owner_user_id="user-a",
            task_type="analysis",
        )

        event = self.db.append_durable_task_progress_event(
            task_id="task-progress-sanitized",
            owner_user_id="user-a",
            event_type="failed",
            stage="failure",
            progress=100,
            message=(
                "Traceback (most recent call last):\n"
                "RuntimeError: Authorization: Bearer not-a-real-token api_key=not-a-real-key"
            ),
            metadata={"api_key": "not-a-real-key", "nested": {"token": "not-a-real-token", "safe": "ok"}},
        )

        serialized = json.dumps(event, ensure_ascii=False)
        self.assertEqual(
            event["message_safe"],
            "Task progress update unavailable; see server logs for sanitized details",
        )
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("not-a-real-token", serialized)
        self.assertNotIn("Traceback", serialized)
        self.assertEqual(event["metadata"]["nested"]["safe"], "ok")

    def test_polling_payload_omits_raw_provider_payloads_and_secrets(self) -> None:
        self.db.create_durable_task_state(
            task_id="task-progress-no-provider-leak",
            owner_user_id="user-a",
            task_type="analysis",
            status="queued",
            metadata={
                "stock_code": "AAPL",
                "selection_source": "manual",
                "raw_provider_payload": {"quote": 123, "authorization": "Bearer not-a-real-token"},
                "provider_response": {"url": "https://provider.example/quote?api_key=not-a-real-key"},
                "nested": {"session_id": "raw-session-id", "safe": "ok"},
            },
        )
        claim = self.db.claim_next_durable_task_state(worker_id="worker-a", task_type="analysis")
        self.assertIsNotNone(claim)
        completed = self.db.complete_claimed_durable_task_state(
            task_id="task-progress-no-provider-leak",
            worker_id="worker-a",
            metadata={
                "result_ref": "fixture:ws2-safe-result",
                "raw_result_payload": {"token": "not-a-real-token"},
                "api_key": "not-a-real-key",
            },
        )
        event = self.db.append_durable_task_progress_event(
            task_id="task-progress-no-provider-leak",
            owner_user_id="user-a",
            event_type="completed",
            progress=100,
            message="Completed with safe result ref",
            metadata={
                "result_ref": "fixture:ws2-safe-result",
                "raw_provider_payload": {"token": "not-a-real-token"},
            },
        )

        response = poll_analysis_task_progress(
            "task-progress-no-provider-leak",
            current_user=SimpleNamespace(user_id="user-a"),
        )
        serialized = json.dumps(
            {
                "completed": completed,
                "event": event,
                "poll": response.model_dump(),
            },
            ensure_ascii=False,
        )

        self.assertEqual(completed["metadata"]["result_ref"], "fixture:ws2-safe-result")
        self.assertEqual(event["metadata"]["result_ref"], "fixture:ws2-safe-result")
        self.assertIn("fixture:ws2-safe-result", serialized)
        for forbidden in (
            "raw_provider_payload",
            "provider_response",
            "raw_result_payload",
            "not-a-real-token",
            "not-a-real-key",
            "raw-session-id",
            "https://provider.example",
            "api_key",
            "session_id",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_polling_endpoint_returns_task_state_and_events(self) -> None:
        self.db.create_durable_task_state(
            task_id="task-progress-poll",
            owner_user_id="user-a",
            task_type="analysis",
            status="processing",
            progress=40,
        )
        self.db.append_durable_task_progress_event(
            task_id="task-progress-poll",
            owner_user_id="user-a",
            event_type="progress",
            progress=40,
            message="Polling event",
        )

        response = poll_analysis_task_progress(
            "task-progress-poll",
            current_user=SimpleNamespace(user_id="user-a"),
        )

        self.assertEqual(response.task.task_id, "task-progress-poll")
        self.assertEqual(response.task.status, "processing")
        self.assertEqual(response.latest_sequence, 1)
        self.assertFalse(response.terminal)
        self.assertEqual(response.events[0].message_safe, "Polling event")

    def test_polling_endpoint_is_owner_scoped(self) -> None:
        self.db.create_durable_task_state(
            task_id="task-progress-poll-private",
            owner_user_id="user-a",
            task_type="analysis",
            status="processing",
        )

        with self.assertRaises(HTTPException) as ctx:
            poll_analysis_task_progress(
                "task-progress-poll-private",
                current_user=SimpleNamespace(user_id="user-b"),
            )

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertNotIn("user-a", json.dumps(ctx.exception.detail))

    def test_process_local_queue_and_sse_contract_remains_present(self) -> None:
        original_instance = AnalysisTaskQueue._instance
        AnalysisTaskQueue._instance = None
        try:
            queue = AnalysisTaskQueue(max_workers=1)
            with patch.dict("os.environ", {"WEB_CONCURRENCY": "2"}, clear=False):
                status = queue.get_runtime_status()
            event = _format_sse_event("task_updated", {"task_id": "task-1", "owner_id": "user-a"})
        finally:
            queue = AnalysisTaskQueue._instance
            if queue is not None and queue is not original_instance:
                executor = getattr(queue, "_executor", None)
                if executor is not None and hasattr(executor, "shutdown"):
                    executor.shutdown(wait=False, cancel_futures=True)
            AnalysisTaskQueue._instance = original_instance

        self.assertEqual(status["mode"], "process_local")
        self.assertTrue(status["single_process_required"])
        self.assertFalse(status["topology_ok"])
        self.assertIn("process-local", status["warning"])
        self.assertIn("single process", status["warning"])
        self.assertTrue(hasattr(AnalysisTaskQueue, "subscribe"))
        self.assertIn("event: task_updated", event)

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
        redis_lines = [
            line.strip()
            for line in combined.splitlines()
            if re.match(r"^\s*redis([<=>\s].*)?$", line)
        ]
        self.assertEqual(len(redis_lines), 1)
        for line in redis_lines:
            self.assertIn("marketcache remote mirror", line)
            self.assertIn("disabled by default", line)


if __name__ == "__main__":
    unittest.main()
