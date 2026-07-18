# -*- coding: utf-8 -*-
"""WS2-R2 durable task worker prototype.

This module is intentionally fixture-backed. It does not submit production
analysis work and does not call LLM, market data, broker, or queue providers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from src.storage import DatabaseManager


SYNTHETIC_TASK_TYPE = "ws2_synthetic_fixture"


class TransientSyntheticTaskError(Exception):
    """Retryable fixture failure used by the WS2 worker prototype."""


class NonRetryableSyntheticTaskError(Exception):
    """Terminal fixture failure used by the WS2 worker prototype."""


class LostDurableTaskClaim(Exception):
    """The worker's fenced claim is no longer active."""


@dataclass(frozen=True)
class WorkerRunResult:
    status: str
    task_id: Optional[str] = None
    attempt_count: int = 0


StageHook = Callable[[str, Dict[str, Any]], None]


class DurableTaskWorkerPrototype:
    """Small durable worker prototype for one synthetic task type."""

    def __init__(
        self,
        *,
        db: Optional[DatabaseManager] = None,
        worker_id: str,
        lease_seconds: int = 60,
        task_type: str = SYNTHETIC_TASK_TYPE,
        stage_hook: Optional[StageHook] = None,
    ) -> None:
        self.db = db or DatabaseManager.get_instance()
        self.worker_id = str(worker_id or "").strip()
        if not self.worker_id:
            raise ValueError("worker_id is required")
        self.lease_seconds = max(1, min(int(lease_seconds or 60), 3600))
        self.task_type = task_type
        self.stage_hook = stage_hook
        self._shutdown_requested = False

    def request_shutdown(self) -> None:
        self._shutdown_requested = True

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def run_once(self) -> WorkerRunResult:
        if self._shutdown_requested:
            return WorkerRunResult(status="shutdown_requested")

        task = self.db.claim_next_durable_task_state(
            worker_id=self.worker_id,
            task_type=self.task_type,
            lease_seconds=self.lease_seconds,
        )
        if task is None:
            return WorkerRunResult(status="idle")

        task_id = str(task["task_id"])
        attempt_count = int(task.get("attempt_count") or 0)
        owner_user_id = str(task.get("owner_user_id") or "")
        self._append_event(
            task_id,
            owner_user_id=owner_user_id,
            event_type="claimed",
            stage="claim",
            progress=int(task.get("progress") or 0),
            message="Synthetic task claimed",
        )
        try:
            self._run_synthetic_handler(task, claim_attempt=attempt_count)
        except LostDurableTaskClaim:
            return WorkerRunResult(status="lost_lease", task_id=task_id, attempt_count=attempt_count)
        except TransientSyntheticTaskError as exc:
            failed = self.db.fail_claimed_durable_task_state(
                task_id=task_id,
                worker_id=self.worker_id,
                claim_attempt=attempt_count,
                error_code="transient_synthetic_error",
                error_summary=str(exc),
                retryable=True,
                current_step="Synthetic task queued for retry",
            )
            if failed is None:
                return WorkerRunResult(status="lost_lease", task_id=task_id, attempt_count=attempt_count)
            status = "retry_queued" if failed and failed.get("status") == "queued" else "failed"
            self._append_event(
                task_id,
                owner_user_id=owner_user_id,
                event_type="retry" if status == "retry_queued" else "failed",
                stage="failure",
                progress=failed.get("progress") if failed else 100,
                message=str(exc),
                metadata={"error_code": "transient_synthetic_error", "retryable": status == "retry_queued"},
            )
            return WorkerRunResult(status=status, task_id=task_id, attempt_count=attempt_count)
        except NonRetryableSyntheticTaskError as exc:
            failed = self.db.fail_claimed_durable_task_state(
                task_id=task_id,
                worker_id=self.worker_id,
                claim_attempt=attempt_count,
                error_code="non_retryable_synthetic_error",
                error_summary=str(exc),
                retryable=False,
                current_step="Synthetic task failed",
            )
            if failed is None:
                return WorkerRunResult(status="lost_lease", task_id=task_id, attempt_count=attempt_count)
            self._append_event(
                task_id,
                owner_user_id=owner_user_id,
                event_type="failed",
                stage="failure",
                progress=failed.get("progress") if failed else 100,
                message=str(exc),
                metadata={"error_code": "non_retryable_synthetic_error", "retryable": False},
            )
            return WorkerRunResult(status="failed", task_id=task_id, attempt_count=attempt_count)
        except Exception as exc:
            failed = self.db.fail_claimed_durable_task_state(
                task_id=task_id,
                worker_id=self.worker_id,
                claim_attempt=attempt_count,
                error_code="worker_error",
                error_summary=str(exc),
                retryable=False,
                current_step="Synthetic task failed",
            )
            if failed is None:
                return WorkerRunResult(status="lost_lease", task_id=task_id, attempt_count=attempt_count)
            self._append_event(
                task_id,
                owner_user_id=owner_user_id,
                event_type="failed",
                stage="failure",
                progress=failed.get("progress") if failed else 100,
                message=str(exc),
                metadata={"error_code": "worker_error", "retryable": False},
            )
            return WorkerRunResult(status="failed", task_id=task_id, attempt_count=attempt_count)

        if self._shutdown_requested:
            return WorkerRunResult(status="shutdown_requested", task_id=task_id, attempt_count=attempt_count)

        completed = self.db.complete_claimed_durable_task_state(
            task_id=task_id,
            worker_id=self.worker_id,
            claim_attempt=attempt_count,
            current_step="Synthetic task complete",
            metadata={"result_ref": "fixture:ws2-synthetic"},
        )
        if completed is None:
            return WorkerRunResult(status="lost_lease", task_id=task_id, attempt_count=attempt_count)
        self._append_event(
            task_id,
            owner_user_id=owner_user_id,
            event_type="completed",
            stage="complete",
            progress=100,
            message="Synthetic task complete",
            metadata={"result_ref": "fixture:ws2-synthetic"},
        )
        return WorkerRunResult(status="completed", task_id=task_id, attempt_count=attempt_count)

    def run_until_idle(self, *, max_tasks: int = 20) -> WorkerRunResult:
        last_result = WorkerRunResult(status="idle")
        for _ in range(max(1, min(int(max_tasks or 20), 100))):
            last_result = self.run_once()
            if last_result.status in {"idle", "shutdown_requested"}:
                return last_result
        return last_result

    def _run_synthetic_handler(self, task: Dict[str, Any], *, claim_attempt: int) -> None:
        metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
        task_id = str(task["task_id"])

        self._heartbeat(
            task_id,
            claim_attempt=claim_attempt,
            progress=20,
            current_step="Synthetic stage 1",
        )
        self._emit_stage("stage_1", task)
        if self._shutdown_requested:
            return

        failure_mode = str(metadata.get("failure_mode") or "").strip()
        if failure_mode == "non_retryable":
            raise NonRetryableSyntheticTaskError("Synthetic validation failed")

        remaining_transient_failures = int(metadata.get("transient_failures_remaining") or 0)
        if failure_mode == "transient" and remaining_transient_failures > 0:
            self._heartbeat(
                task_id,
                claim_attempt=claim_attempt,
                progress=30,
                current_step="Synthetic transient failure",
                metadata={"transient_failures_remaining": remaining_transient_failures - 1},
            )
            raise TransientSyntheticTaskError("Synthetic transient failure")

        self._heartbeat(
            task_id,
            claim_attempt=claim_attempt,
            progress=70,
            current_step="Synthetic stage 2",
        )
        self._emit_stage("stage_2", task)

    def _heartbeat(
        self,
        task_id: str,
        *,
        claim_attempt: int,
        progress: int,
        current_step: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        state = self.db.heartbeat_durable_task_state(
            task_id=task_id,
            worker_id=self.worker_id,
            claim_attempt=claim_attempt,
            lease_seconds=self.lease_seconds,
            progress=progress,
            current_step=current_step,
            metadata=metadata,
        )
        if state is None:
            raise LostDurableTaskClaim
        self._append_event(
            task_id,
            owner_user_id=str(state.get("owner_user_id") or ""),
            event_type="progress",
            stage=current_step,
            progress=progress,
            message=current_step,
            metadata=metadata,
        )

    def _emit_stage(self, stage: str, task: Dict[str, Any]) -> None:
        if self.stage_hook is not None:
            self.stage_hook(stage, task)

    def _append_event(
        self,
        task_id: str,
        *,
        owner_user_id: str,
        event_type: str,
        stage: str,
        progress: Optional[int],
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.db.append_durable_task_progress_event(
            task_id=task_id,
            owner_user_id=owner_user_id,
            event_type=event_type,
            stage=stage,
            progress=progress,
            message=message,
            metadata=metadata,
        )
