# -*- coding: utf-8 -*-
"""Atomicity and recovery contracts for the generic durable task store."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import threading
from types import SimpleNamespace

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.storage import (
    DatabaseManager,
    DurableTaskState,
    DurableTaskStateCorruptError,
    PartialFactoryResetError,
)


TASK_TYPE = "atomicity_fixture"


@pytest.fixture()
def durable_db(tmp_path):
    DatabaseManager.reset_instance()
    db = DatabaseManager(db_url=f"sqlite:///{tmp_path / 'durable-atomicity.db'}")
    db.create_or_update_app_user(user_id="owner-a", username="alice")
    yield db
    DatabaseManager.reset_instance()


def _create_task(db: DatabaseManager, task_id: str, **kwargs):
    return db.create_durable_task_state(
        task_id=task_id,
        owner_user_id="owner-a",
        task_type=TASK_TYPE,
        status="queued",
        current_step="Queued",
        max_attempts=3,
        idempotency_key=f"request:{task_id}",
        metadata={"result_ref": "lkg:queued"},
        **kwargs,
    )


def test_concurrent_claim_is_compare_and_set(
    durable_db: DatabaseManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_task(durable_db, "concurrent-claim")
    workers_ready = threading.Barrier(2)
    original_execute = Session.execute

    def align_candidate_reads(session, statement, *args, **kwargs):
        result = original_execute(session, statement, *args, **kwargs)
        normalized = " ".join(str(statement).lower().split())
        if normalized.startswith("select") and "order by durable_task_states.created_at" in normalized:
            workers_ready.wait(timeout=5)
        return result

    monkeypatch.setattr(Session, "execute", align_candidate_reads)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                durable_db.claim_next_durable_task_state,
                worker_id=worker_id,
                task_type=TASK_TYPE,
                now=datetime(2026, 1, 1, 12, 0, 0),
            )
            for worker_id in ("worker-a", "worker-b")
        ]
        outcomes = [future.result() for future in futures]

    claims = [outcome for outcome in outcomes if outcome is not None]
    assert len(claims) == 1
    assert claims[0]["attempt_count"] == 1


def test_duplicate_worker_attempt_is_fenced_after_reclaim(durable_db: DatabaseManager) -> None:
    _create_task(durable_db, "attempt-fence")
    started = datetime(2026, 1, 1, 12, 0, 0)
    first = durable_db.claim_next_durable_task_state(
        worker_id="stable-worker-id",
        task_type=TASK_TYPE,
        lease_seconds=1,
        now=started,
    )
    recovered = durable_db.claim_next_durable_task_state(
        worker_id="stable-worker-id",
        task_type=TASK_TYPE,
        now=started + timedelta(seconds=2),
    )

    stale = durable_db.complete_claimed_durable_task_state(
        task_id="attempt-fence",
        worker_id="stable-worker-id",
        claim_attempt=first["attempt_count"],
        now=started + timedelta(seconds=2),
    )
    current = durable_db.complete_claimed_durable_task_state(
        task_id="attempt-fence",
        worker_id="stable-worker-id",
        claim_attempt=recovered["attempt_count"],
        now=started + timedelta(seconds=2),
    )

    assert stale is None
    assert current is not None
    assert current["status"] == "completed"


def test_expired_owner_cannot_complete_or_fail_active_claim(durable_db: DatabaseManager) -> None:
    _create_task(durable_db, "expired-owner")
    started = datetime(2026, 1, 1, 12, 0, 0)
    claim = durable_db.claim_next_durable_task_state(
        worker_id="worker-a",
        task_type=TASK_TYPE,
        lease_seconds=1,
        now=started,
    )
    expired = started + timedelta(seconds=2)

    assert durable_db.update_durable_task_state(
        task_id="expired-owner",
        owner_user_id="owner-a",
        status="completed",
        completed_at=started,
    ) is None
    assert durable_db.complete_claimed_durable_task_state(
        task_id="expired-owner",
        worker_id="worker-a",
        claim_attempt=claim["attempt_count"],
        now=expired,
    ) is None
    assert durable_db.fail_claimed_durable_task_state(
        task_id="expired-owner",
        worker_id="worker-a",
        claim_attempt=claim["attempt_count"],
        error_code="late_failure",
        error_summary="expired owner",
        retryable=False,
        now=expired,
    ) is None


def test_abandoned_running_claim_is_explicitly_recovered(durable_db: DatabaseManager) -> None:
    _create_task(durable_db, "abandoned-running")
    started = datetime(2026, 1, 1, 12, 0, 0)
    first = durable_db.claim_next_durable_task_state(
        worker_id="worker-a",
        task_type=TASK_TYPE,
        lease_seconds=1,
        now=started,
    )
    durable_db.heartbeat_durable_task_state(
        task_id="abandoned-running",
        worker_id="worker-a",
        claim_attempt=first["attempt_count"],
        lease_seconds=1,
        status="running",
        now=started,
    )

    recovered = durable_db.claim_next_durable_task_state(
        worker_id="worker-b",
        task_type=TASK_TYPE,
        now=started + timedelta(seconds=2),
    )

    assert recovered["status"] == "leased"
    assert recovered["attempt_count"] == 2
    assert recovered["error_code"] == "abandoned_claim"
    assert recovered["current_step"] == "Recovered abandoned running claim"
    assert recovered["completed_at"] is None


def test_retry_keeps_task_identity_and_fences_prior_attempt(durable_db: DatabaseManager) -> None:
    _create_task(durable_db, "retry-identity")
    started = datetime(2026, 1, 1, 12, 0, 0)
    first = durable_db.claim_next_durable_task_state(
        worker_id="worker-a",
        task_type=TASK_TYPE,
        now=started,
    )
    retry = durable_db.fail_claimed_durable_task_state(
        task_id="retry-identity",
        worker_id="worker-a",
        claim_attempt=first["attempt_count"],
        error_code="transient",
        error_summary="retry",
        retryable=True,
        now=started,
    )
    second = durable_db.claim_next_durable_task_state(
        worker_id="worker-b",
        task_type=TASK_TYPE,
        now=started + timedelta(seconds=1),
    )

    assert retry["status"] == "queued"
    assert first["task_id"] == retry["task_id"] == second["task_id"]
    assert first["attempt_count"] == 1
    assert second["attempt_count"] == 2
    assert durable_db.fail_claimed_durable_task_state(
        task_id="retry-identity",
        worker_id="worker-a",
        claim_attempt=first["attempt_count"],
        error_code="duplicate",
        error_summary="stale retry",
        retryable=False,
        now=started + timedelta(seconds=1),
    ) is None


def test_interrupted_completion_preserves_last_known_good_state(
    durable_db: DatabaseManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_task(durable_db, "interrupted-completion")
    started = datetime(2026, 1, 1, 12, 0, 0)
    claim = durable_db.claim_next_durable_task_state(
        worker_id="worker-a",
        task_type=TASK_TYPE,
        now=started,
    )

    with pytest.raises(DurableTaskStateCorruptError, match="interrupted-completion"):
        durable_db.complete_claimed_durable_task_state(
            task_id="interrupted-completion",
            worker_id="worker-a",
            claim_attempt=claim["attempt_count"],
            metadata={"result_ref": float("nan")},
            now=started,
        )

    last_known_good = durable_db.get_durable_task_state(
        task_id="interrupted-completion",
        owner_user_id="owner-a",
    )
    assert last_known_good["status"] == "leased"
    assert last_known_good["metadata"] == {"result_ref": "lkg:queued"}

    def interrupted_commit(_session):
        raise OSError("simulated durable commit interruption")

    monkeypatch.setattr(durable_db._SessionLocal.class_, "commit", interrupted_commit)
    with pytest.raises(OSError, match="durable commit interruption"):
        durable_db.complete_claimed_durable_task_state(
            task_id="interrupted-completion",
            worker_id="worker-a",
            claim_attempt=claim["attempt_count"],
            metadata={"result_ref": "replacement:new"},
            now=started,
        )

    state = durable_db.get_durable_task_state(
        task_id="interrupted-completion",
        owner_user_id="owner-a",
    )
    assert state["status"] == "leased"
    assert state["metadata"] == {"result_ref": "lkg:queued"}
    assert state["completed_at"] is None


def test_corrupt_durable_metadata_is_not_treated_as_empty(durable_db: DatabaseManager) -> None:
    _create_task(durable_db, "corrupt-state")
    with durable_db.session_scope() as session:
        session.execute(
            update(DurableTaskState)
            .where(DurableTaskState.task_id == "corrupt-state")
            .values(metadata_json="{corrupt replacement")
        )

    with pytest.raises(DurableTaskStateCorruptError, match="corrupt-state"):
        durable_db.get_durable_task_state(task_id="corrupt-state", owner_user_id="owner-a")

    with durable_db.get_session() as session:
        raw = session.execute(
            select(DurableTaskState.metadata_json)
            .where(DurableTaskState.task_id == "corrupt-state")
        ).scalar_one()
    assert raw == "{corrupt replacement"


def test_factory_reset_reports_partial_failure(durable_db: DatabaseManager) -> None:
    durable_db._phase_b_enabled = True
    durable_db._phase_b_store = SimpleNamespace(
        clear_non_bootstrap_state=lambda _user_ids: (_ for _ in ()).throw(
            RuntimeError("simulated phase-b delete failure")
        ),
        dispose=lambda: None,
    )

    with pytest.raises(PartialFactoryResetError) as ctx:
        durable_db.factory_reset_non_bootstrap_state()

    report = ctx.value.report
    assert report["success"] is False
    assert report["partial"] is True
    assert report["failed_stage"] == "phase_b"
    assert report["completed_stages"] == ["sqlite"]
    assert "app_users" in report["cleared"]
    assert durable_db.get_app_user("owner-a") is None
