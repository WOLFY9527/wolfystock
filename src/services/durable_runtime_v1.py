# -*- coding: utf-8 -*-
"""Guarded Durable Runtime v1 synthetic worker prototype."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from src.services.durable_runtime_contracts import (
    DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE,
    build_durable_runtime_envelope,
)
from src.storage import DatabaseManager


ROUTE_FAMILY = "durable-runtime-v1-prototype"


class RetryableFixtureError(Exception):
    """Retryable local fixture failure."""


class TerminalFixtureError(Exception):
    """Non-retryable local fixture failure."""


class LostDurableRuntimeClaim(Exception):
    """The worker's fenced claim is no longer active."""


@dataclass(frozen=True)
class DurableRuntimeRunResult:
    status: str
    task_id: Optional[str] = None
    attempt_count: int = 0


StageHook = Callable[[str, Dict[str, Any]], None]


def create_synthetic_runtime_task(
    *,
    db: Optional[DatabaseManager] = None,
    task_id: str,
    owner_user_id: str,
    job_kind: str,
    fixture_name: str,
    symbol: Optional[str] = None,
    max_attempts: int = 3,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a queued synthetic Durable Runtime v1 task."""
    database = db or DatabaseManager.get_instance()
    envelope = build_durable_runtime_envelope(
        job_kind=job_kind,
        fixture_name=fixture_name,
        symbol=symbol,
        extra_metadata={
            "stock_code": symbol,
            **(metadata or {}),
        },
    )
    return database.create_durable_task_state(
        task_id=task_id,
        owner_user_id=owner_user_id,
        task_type=DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE,
        route_family=ROUTE_FAMILY,
        status="queued",
        current_step="Durable Runtime v1 task queued",
        max_attempts=max_attempts,
        metadata=envelope,
    )


class DurableRuntimeV1PrototypeWorker:
    """Fixture-only worker for Durable Runtime v1 prototype tasks."""

    def __init__(
        self,
        *,
        db: Optional[DatabaseManager] = None,
        worker_id: str,
        lease_seconds: int = 60,
        task_type: str = DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE,
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

    def run_once(self) -> DurableRuntimeRunResult:
        if self._shutdown_requested:
            return DurableRuntimeRunResult(status="shutdown_requested")

        task = self.db.claim_next_durable_task_state(
            worker_id=self.worker_id,
            task_type=self.task_type,
            lease_seconds=self.lease_seconds,
        )
        if task is None:
            return DurableRuntimeRunResult(status="idle")

        task_id = str(task["task_id"])
        owner_user_id = str(task.get("owner_user_id") or "")
        attempt_count = int(task.get("attempt_count") or 0)
        self._append_event(
            task_id,
            owner_user_id=owner_user_id,
            event_type="claimed",
            stage="claim",
            progress=int(task.get("progress") or 0),
            message="Durable Runtime v1 task claimed",
        )

        try:
            result_ref = self._run_fixture(task, claim_attempt=attempt_count)
        except LostDurableRuntimeClaim:
            return DurableRuntimeRunResult(
                status="lost_lease",
                task_id=task_id,
                attempt_count=attempt_count,
            )
        except RetryableFixtureError as exc:
            failed = self.db.fail_claimed_durable_task_state(
                task_id=task_id,
                worker_id=self.worker_id,
                claim_attempt=attempt_count,
                error_code="durable_runtime_retryable_fixture",
                error_summary=str(exc),
                retryable=True,
                current_step="Durable Runtime v1 task queued for retry",
            )
            if failed is None:
                return DurableRuntimeRunResult(
                    status="lost_lease",
                    task_id=task_id,
                    attempt_count=attempt_count,
                )
            status = "retry_queued" if failed and failed.get("status") == "queued" else "failed"
            self._append_event(
                task_id,
                owner_user_id=owner_user_id,
                event_type="retry" if status == "retry_queued" else "failed",
                stage="failure",
                progress=failed.get("progress") if failed else 100,
                message=str(exc),
                metadata={"error_code": "durable_runtime_retryable_fixture", "retryable": status == "retry_queued"},
            )
            return DurableRuntimeRunResult(status=status, task_id=task_id, attempt_count=attempt_count)
        except TerminalFixtureError as exc:
            failed = self.db.fail_claimed_durable_task_state(
                task_id=task_id,
                worker_id=self.worker_id,
                claim_attempt=attempt_count,
                error_code="durable_runtime_terminal_fixture",
                error_summary=str(exc),
                retryable=False,
                current_step="Durable Runtime v1 task failed",
            )
            if failed is None:
                return DurableRuntimeRunResult(
                    status="lost_lease",
                    task_id=task_id,
                    attempt_count=attempt_count,
                )
            self._append_event(
                task_id,
                owner_user_id=owner_user_id,
                event_type="failed",
                stage="failure",
                progress=failed.get("progress") if failed else 100,
                message=str(exc),
                metadata={"error_code": "durable_runtime_terminal_fixture", "retryable": False},
            )
            return DurableRuntimeRunResult(status="failed", task_id=task_id, attempt_count=attempt_count)

        if self._shutdown_requested:
            return DurableRuntimeRunResult(status="shutdown_requested", task_id=task_id, attempt_count=attempt_count)

        completed = self.db.complete_claimed_durable_task_state(
            task_id=task_id,
            worker_id=self.worker_id,
            claim_attempt=attempt_count,
            current_step="Durable Runtime v1 fixture complete",
            metadata={"result_ref": result_ref, "artifact_kind": "synthetic_fixture"},
        )
        if completed is None:
            return DurableRuntimeRunResult(status="lost_lease", task_id=task_id, attempt_count=attempt_count)
        self._append_event(
            task_id,
            owner_user_id=owner_user_id,
            event_type="completed",
            stage="complete",
            progress=100,
            message="Durable Runtime v1 fixture complete",
            metadata={"result_ref": result_ref},
        )
        return DurableRuntimeRunResult(status="completed", task_id=task_id, attempt_count=attempt_count)

    def _run_fixture(self, task: Dict[str, Any], *, claim_attempt: int) -> str:
        metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
        task_id = str(task["task_id"])
        job_kind = str(metadata.get("job_kind") or "").strip()
        fixture_name = str(metadata.get("fixture_name") or "").strip()
        result_ref = f"fixture:{job_kind}:{fixture_name}"

        self._heartbeat(
            task_id,
            claim_attempt=claim_attempt,
            progress=20,
            current_step=f"{job_kind} fixture prepare",
        )
        self._emit_stage("prepare", task)
        if self._shutdown_requested:
            return result_ref

        if fixture_name == "terminal_failure":
            raise TerminalFixtureError("Durable Runtime v1 terminal fixture failure")

        remaining_transient_failures = int(metadata.get("transient_failures_remaining") or 0)
        if fixture_name == "transient_failure" and remaining_transient_failures > 0:
            self._heartbeat(
                task_id,
                claim_attempt=claim_attempt,
                progress=35,
                current_step="Durable Runtime v1 transient fixture failure",
                metadata={"transient_failures_remaining": remaining_transient_failures - 1},
            )
            raise RetryableFixtureError("Durable Runtime v1 transient fixture failure")

        self._heartbeat(
            task_id,
            claim_attempt=claim_attempt,
            progress=70,
            current_step=f"{job_kind} fixture execute",
        )
        self._emit_stage("execute", task)
        return result_ref

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
            raise LostDurableRuntimeClaim
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
