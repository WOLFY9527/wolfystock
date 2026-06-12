#!/usr/bin/env python3
"""Run a safe synthetic WS2 multi-instance smoke preflight.

This helper emits bounded JSON operator evidence for manual review. By default
it only explains the checks that would run. The synthetic mode uses disposable
SQLite storage and fixture-backed durable task helpers; it does not open
sockets, call staging, inspect environment values, modify task runtime behavior,
or change API/SSE/worker semantics.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.durable_task_worker import (  # noqa: E402
    SYNTHETIC_TASK_TYPE,
    DurableTaskWorkerPrototype,
)
from src.storage import DatabaseManager  # noqa: E402


SCHEMA_VERSION = "wolfystock_ws2_multi_instance_smoke_preflight_v1"
VALIDATION_PROFILE = "PROFILE_DURABLE_PROTECTED"
ACCEPTANCE_EVIDENCE_PROFILE = "PROFILE_WS2_ACCEPTANCE_EVIDENCE_SCOPED"
PASS_STATUS = "preflight-pass-review-required"
FAIL_STATUS = "preflight-fail-review-required"
DRY_RUN_STATUS = "dry-run-review-required"
NETWORK_OPT_IN_ENV = "WOLFYSTOCK_WS2_MULTI_INSTANCE_SMOKE_ENABLE_NETWORK"
EXIT_OK = 0
EXIT_FAILED = 1


@dataclass(frozen=True)
class CheckPlan:
    check_id: str
    would_check: str


CHECK_PLANS: tuple[CheckPlan, ...] = (
    CheckPlan("api_a_submit", "Create an owner-scoped synthetic durable task through the API A seam."),
    CheckPlan("worker_lease", "Verify one active durable worker lease blocks a second worker claim."),
    CheckPlan("api_b_durable_read", "Read completed durable status from a fresh API B process-memory view."),
    CheckPlan("polling_replay", "Replay durable progress after a sequence cursor from a fresh API B view."),
    CheckPlan("owner_isolation", "Verify another owner receives owner-hidden status and polling responses."),
    CheckPlan("lease_expiry_retry", "Reclaim an expired lease and reject stale-worker terminal writes."),
    CheckPlan("failure_safety", "Keep terminal failure pollable with safe reason codes and no exception details."),
)


class _EmptyProcessLocalQueue:
    def get_task(self, _task_id: str, *, owner_id: str | None = None) -> None:
        return None


class _SyntheticTopology:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.open_instance_db()
        self.seed_users()

    def open_instance_db(self) -> DatabaseManager:
        DatabaseManager.reset_instance()
        return DatabaseManager(db_url=f"sqlite:///{self.db_path}")

    def seed_users(self) -> None:
        db = DatabaseManager.get_instance()
        db.create_or_update_app_user(user_id="owner-a", username="operator_a")
        db.create_or_update_app_user(user_id="owner-b", username="operator_b")

    @staticmethod
    def api_user(owner_id: str) -> SimpleNamespace:
        return SimpleNamespace(user_id=owner_id)

    def create_synthetic_task(
        self,
        task_id: str,
        owner_id: str = "owner-a",
        **metadata: object,
    ) -> dict[str, Any]:
        db = self.open_instance_db()
        return db.create_durable_task_state(
            task_id=task_id,
            owner_user_id=owner_id,
            task_type=SYNTHETIC_TASK_TYPE,
            status="queued",
            current_step="Queued by API instance",
            max_attempts=int(metadata.pop("max_attempts", 3)),
            metadata={"stock_code": "AAPL", "selection_source": "manual", **metadata},
        )

    def status_from_fresh_api_instance(self, task_id: str, owner_id: str):
        from api.v1.endpoints.analysis import get_analysis_status

        self.open_instance_db()
        with patch("api.v1.endpoints.analysis.get_task_queue", return_value=_EmptyProcessLocalQueue()):
            return get_analysis_status(task_id, current_user=self.api_user(owner_id))

    def poll_from_fresh_api_instance(
        self,
        task_id: str,
        owner_id: str,
        *,
        after_sequence: int | None = None,
        limit: int = 50,
    ):
        from api.v1.endpoints.analysis import poll_analysis_task_progress

        self.open_instance_db()
        with patch("api.v1.endpoints.analysis.get_task_queue", return_value=_EmptyProcessLocalQueue()):
            return poll_analysis_task_progress(
                task_id,
                after_sequence=after_sequence,
                limit=limit,
                current_user=self.api_user(owner_id),
            )


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _network_opt_in_enabled() -> bool:
    return str(os.environ.get(NETWORK_OPT_IN_ENV) or "").strip() == "1"


def _staging_target_label(staging_base_url: str | None) -> str:
    return "staging-url-configured" if str(staging_base_url or "").strip() else "not-configured"


def _base_summary(
    *,
    mode: str,
    status: str,
    staging_base_url: str | None,
) -> dict[str, Any]:
    network_opt_in = _network_opt_in_enabled()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "validationProfile": VALIDATION_PROFILE,
        "acceptanceEvidenceProfile": ACCEPTANCE_EVIDENCE_PROFILE,
        "generatedAt": _now_iso(),
        "preflightStatus": status,
        "mode": mode,
        "manualReviewRequired": True,
        "runtimeBehaviorChanged": False,
        "taskRuntimeSemanticsChanged": False,
        "apiRuntimeTouched": False,
        "networkCallsExecuted": False,
        "stagingCallsEnabled": bool(staging_base_url and network_opt_in),
        "stagingOptInSatisfied": bool(staging_base_url and network_opt_in),
        "stagingTargetLabel": _staging_target_label(staging_base_url),
        "storageMode": "disposable-sqlite",
        "topologyMode": "synthetic-durable-polling-preflight",
        "sseBroadcastScope": "process-local",
        "pollingFallbackAccepted": True,
        "multiInstanceRiskAccepted": False,
        "evidenceBoundary": {
            "acceptedStagingEvidence": False,
            "ciSyntheticEvidence": False,
            "durablePollingBaseline": True,
            "liveStagingCallsImplemented": False,
            "publicLaunchReady": False,
            "sseCrossInstanceReliable": False,
            "syntheticLocalDryRunEvidence": mode == "synthetic",
            "targetEnvironmentEvidence": False,
        },
        "sseLimitation": {
            "broadcastScope": "process-local",
            "durableFallback": "durable-task-polling",
            "externalReplayImplemented": False,
            "operatorMessage": (
                "process-local SSE is not cross-instance reliable; "
                "durable polling remains the multi-instance baseline"
            ),
        },
        "summary": "Offline WS2 multi-instance smoke preflight using disposable SQLite and sanitized evidence only.",
        "payloadPolicy": {
            "credentialValuesIncluded": False,
            "rawBodiesIncluded": False,
            "exceptionDetailsIncluded": False,
        },
    }


def build_dry_run_summary(*, staging_base_url: str | None = None) -> dict[str, Any]:
    summary = _base_summary(mode="dry-run", status=DRY_RUN_STATUS, staging_base_url=staging_base_url)
    summary["checks"] = [
        {
            "id": plan.check_id,
            "status": "planned",
            "wouldCheck": plan.would_check,
        }
        for plan in CHECK_PLANS
    ]
    return summary


def _api_a_submit(topology: _SyntheticTopology) -> dict[str, Any]:
    created = topology.create_synthetic_task("ws2-preflight-api-a")
    return {
        "apiInstance": "api-a",
        "submitPath": "synthetic-durable-state-helper",
        "transportExercised": False,
        "targetEnvironmentEvidence": False,
        "storedStatus": created["status"],
        "taskType": created["task_type"],
        "ownerScoped": bool(created.get("owner_user_id")),
        "durableRowCreated": True,
        "externalCallsExecuted": False,
    }


def _worker_lease(topology: _SyntheticTopology) -> dict[str, Any]:
    topology.create_synthetic_task("ws2-preflight-active-lease")
    claimed_at = datetime(2026, 1, 1, 12, 0, 0)
    worker_a_db = topology.open_instance_db()
    first_claim = worker_a_db.claim_next_durable_task_state(
        worker_id="worker-a",
        task_type=SYNTHETIC_TASK_TYPE,
        lease_seconds=60,
        now=claimed_at,
    )
    progress_event_recorded = False
    if first_claim is not None:
        worker_a_db.heartbeat_durable_task_state(
            task_id="ws2-preflight-active-lease",
            worker_id="worker-a",
            lease_seconds=60,
            progress=25,
            current_step="Synthetic lease progress",
            now=claimed_at + timedelta(seconds=5),
        )
        worker_a_db.append_durable_task_progress_event(
            task_id="ws2-preflight-active-lease",
            owner_user_id="owner-a",
            event_type="progress",
            stage="worker-lease",
            progress=25,
            message="Synthetic lease progress",
        )
        progress_events = worker_a_db.list_durable_task_progress_events(
            task_id="ws2-preflight-active-lease",
            owner_user_id="owner-a",
        )
        progress_event_recorded = any(event.get("event_type") == "progress" for event in progress_events)
    worker_b_db = topology.open_instance_db()
    second_claim = worker_b_db.claim_next_durable_task_state(
        worker_id="worker-b",
        task_type=SYNTHETIC_TASK_TYPE,
        lease_seconds=60,
        now=claimed_at + timedelta(seconds=30),
    )
    durable = DatabaseManager.get_instance().get_durable_task_state(
        task_id="ws2-preflight-active-lease",
        owner_user_id="owner-a",
    )
    return {
        "firstLeaseClaimed": first_claim is not None,
        "duplicateActiveLeaseBlocked": second_claim is None,
        "storedStatus": durable["status"] if durable else "missing",
        "attemptCount": int((durable or {}).get("attempt_count") or 0),
        "progressPersisted": int((durable or {}).get("progress") or 0) == 25,
        "progressEventRecorded": progress_event_recorded,
    }


def _api_b_durable_read(topology: _SyntheticTopology) -> dict[str, Any]:
    topology.create_synthetic_task("ws2-preflight-api-b")
    worker = DurableTaskWorkerPrototype(db=topology.open_instance_db(), worker_id="worker-b")
    worker_result = worker.run_once()
    status = topology.status_from_fresh_api_instance("ws2-preflight-api-b", "owner-a")
    poll = topology.poll_from_fresh_api_instance("ws2-preflight-api-b", "owner-a", after_sequence=1, limit=3)
    return {
        "apiInstance": "api-b",
        "submittedApiInstance": "api-a",
        "processMemoryShared": False,
        "pollingFallbackUsed": True,
        "transportExercised": False,
        "workerResult": worker_result.status,
        "visibleStatus": status.status,
        "visibleProgress": status.progress,
        "pollTerminal": poll.terminal,
        "latestSequence": poll.latest_sequence,
    }


def _polling_replay(topology: _SyntheticTopology) -> dict[str, Any]:
    topology.create_synthetic_task("ws2-preflight-replay")
    worker = DurableTaskWorkerPrototype(db=topology.open_instance_db(), worker_id="worker-a")
    worker.run_once()
    replay = topology.poll_from_fresh_api_instance(
        "ws2-preflight-replay",
        "owner-a",
        after_sequence=1,
        limit=2,
    )
    return {
        "apiInstance": "api-b",
        "afterSequence": 1,
        "durablePollingBaseline": True,
        "replaySequences": [event.sequence for event in replay.events],
        "latestSequence": replay.latest_sequence,
        "terminal": replay.terminal,
        "boundedByLimit": len(replay.events) == 2,
    }


def _owner_isolation(topology: _SyntheticTopology) -> dict[str, Any]:
    from fastapi import HTTPException

    topology.create_synthetic_task("ws2-preflight-private")
    worker = DurableTaskWorkerPrototype(db=topology.open_instance_db(), worker_id="worker-a")
    worker.run_once()
    status_code = 0
    poll_code = 0
    try:
        topology.status_from_fresh_api_instance("ws2-preflight-private", "owner-b")
    except HTTPException as exc:
        status_code = int(exc.status_code)
    try:
        topology.poll_from_fresh_api_instance("ws2-preflight-private", "owner-b")
    except HTTPException as exc:
        poll_code = int(exc.status_code)
    return {
        "crossOwnerStatusCode": status_code,
        "crossOwnerPollStatusCode": poll_code,
        "ownerHidden": status_code == 404 and poll_code == 404,
        "ownerValueIncluded": False,
        "syntheticOwnerIsolationRepresented": True,
    }


def _lease_expiry_retry(topology: _SyntheticTopology) -> dict[str, Any]:
    topology.create_synthetic_task("ws2-preflight-expired-lease")
    worker_a_db = topology.open_instance_db()
    first_claim = worker_a_db.claim_next_durable_task_state(
        worker_id="worker-a",
        task_type=SYNTHETIC_TASK_TYPE,
        lease_seconds=1,
    )
    if first_claim is None:
        return {
            "firstLeaseClaimed": False,
            "reclaimedAttemptCount": 0,
            "staleWorkerWriteRejected": False,
            "recoveredStatus": "missing",
        }
    started_at = datetime.fromisoformat(first_claim["started_at"])
    worker_a_db.heartbeat_durable_task_state(
        task_id="ws2-preflight-expired-lease",
        worker_id="worker-a",
        lease_seconds=1,
        progress=35,
        current_step="Synthetic worker paused",
        now=started_at,
    )
    expired_time = datetime.fromisoformat(first_claim["lease_expires_at"]) + timedelta(seconds=1)
    worker_b_db = topology.open_instance_db()
    second_claim = worker_b_db.claim_next_durable_task_state(
        worker_id="worker-b",
        task_type=SYNTHETIC_TASK_TYPE,
        now=expired_time,
    )
    stale_complete = worker_b_db.complete_claimed_durable_task_state(
        task_id="ws2-preflight-expired-lease",
        worker_id="worker-a",
        now=expired_time,
    )
    recovered_complete = worker_b_db.complete_claimed_durable_task_state(
        task_id="ws2-preflight-expired-lease",
        worker_id="worker-b",
        current_step="Recovered by worker B",
        metadata={"result_ref": "fixture:ws2-recovered"},
        now=expired_time,
    )
    final_status = topology.status_from_fresh_api_instance("ws2-preflight-expired-lease", "owner-a")
    return {
        "firstLeaseClaimed": True,
        "secondLeaseClaimed": second_claim is not None,
        "reclaimedAttemptCount": int((second_claim or {}).get("attempt_count") or 0),
        "staleWorkerWriteRejected": stale_complete is None,
        "recoveredStatus": final_status.status,
        "terminalWriteAccepted": recovered_complete is not None,
        "leaseExpirySimulated": True,
    }


def _failure_safety(topology: _SyntheticTopology) -> dict[str, Any]:
    topology.create_synthetic_task(
        "ws2-preflight-retry-cap",
        failure_mode="transient",
        transient_failures_remaining=3,
        max_attempts=2,
    )
    worker = DurableTaskWorkerPrototype(db=topology.open_instance_db(), worker_id="worker-a")
    retry_results = [worker.run_once(), worker.run_once()]
    retry_state = DatabaseManager.get_instance().get_durable_task_state(
        task_id="ws2-preflight-retry-cap",
        owner_user_id="owner-a",
    )

    topology.create_synthetic_task(
        "ws2-preflight-failed",
        failure_mode="non_retryable",
        api_key="not-a-real-key",
    )
    failure_worker = DurableTaskWorkerPrototype(db=topology.open_instance_db(), worker_id="worker-a")
    result = failure_worker.run_once()
    poll = topology.poll_from_fresh_api_instance("ws2-preflight-failed", "owner-a")
    failure_events = [event for event in poll.events if event.event_type == "failed"]
    safe_failure_code = None
    if failure_events:
        metadata = failure_events[-1].metadata if isinstance(failure_events[-1].metadata, dict) else {}
        safe_failure_code = metadata.get("error_code")
    return {
        "workerResult": result.status,
        "failedTaskPollable": poll.task.status == "failed",
        "terminal": poll.terminal,
        "safeFailureCode": safe_failure_code,
        "failureEventRecorded": bool(failure_events),
        "credentialValueIncluded": False,
        "retryStatuses": [item.status for item in retry_results],
        "retryCapEnforced": (
            (retry_state or {}).get("status") == "failed"
            and int((retry_state or {}).get("attempt_count") or 0) == 2
            and (retry_state or {}).get("error_code") == "transient_synthetic_error"
        ),
    }


CheckRunner = Callable[[_SyntheticTopology], dict[str, Any]]
CHECK_RUNNERS: dict[str, CheckRunner] = {
    "api_a_submit": _api_a_submit,
    "worker_lease": _worker_lease,
    "api_b_durable_read": _api_b_durable_read,
    "polling_replay": _polling_replay,
    "owner_isolation": _owner_isolation,
    "lease_expiry_retry": _lease_expiry_retry,
    "failure_safety": _failure_safety,
}


def _evidence_passes(check_id: str, evidence: dict[str, Any]) -> bool:
    if check_id == "api_a_submit":
        return evidence.get("storedStatus") == "queued" and evidence.get("durableRowCreated") is True
    if check_id == "worker_lease":
        return (
            evidence.get("firstLeaseClaimed") is True
            and evidence.get("duplicateActiveLeaseBlocked") is True
            and evidence.get("progressPersisted") is True
            and evidence.get("progressEventRecorded") is True
        )
    if check_id == "api_b_durable_read":
        return evidence.get("workerResult") == "completed" and evidence.get("visibleStatus") == "completed"
    if check_id == "polling_replay":
        return evidence.get("replaySequences") == [2, 3] and evidence.get("terminal") is True
    if check_id == "owner_isolation":
        return evidence.get("ownerHidden") is True
    if check_id == "lease_expiry_retry":
        return (
            evidence.get("secondLeaseClaimed") is True
            and evidence.get("reclaimedAttemptCount") == 2
            and evidence.get("staleWorkerWriteRejected") is True
            and evidence.get("recoveredStatus") == "completed"
        )
    if check_id == "failure_safety":
        return (
            evidence.get("workerResult") == "failed"
            and evidence.get("failedTaskPollable") is True
            and evidence.get("terminal") is True
            and evidence.get("safeFailureCode") == "non_retryable_synthetic_error"
            and evidence.get("retryStatuses") == ["retry_queued", "failed"]
            and evidence.get("retryCapEnforced") is True
        )
    return False


def _run_synthetic_check(topology: _SyntheticTopology, plan: CheckPlan) -> dict[str, Any]:
    runner = CHECK_RUNNERS[plan.check_id]
    try:
        evidence = runner(topology)
    except Exception:
        return {
            "id": plan.check_id,
            "status": "fail",
            "failureSummary": "check_failed",
        }
    if not _evidence_passes(plan.check_id, evidence):
        return {
            "id": plan.check_id,
            "status": "fail",
            "failureSummary": "unexpected_evidence",
            "evidence": evidence,
        }
    return {
        "id": plan.check_id,
        "status": "pass",
        "evidence": evidence,
    }


def run_synthetic_preflight(*, staging_base_url: str | None = None) -> tuple[int, dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="ws2-multi-instance-preflight-") as temp_dir:
        checks = []
        for plan in CHECK_PLANS:
            DatabaseManager.reset_instance()
            try:
                topology = _SyntheticTopology(Path(temp_dir) / f"{plan.check_id}.db")
                checks.append(_run_synthetic_check(topology, plan))
            finally:
                DatabaseManager.reset_instance()

    failed = any(check["status"] != "pass" for check in checks)
    summary = _base_summary(
        mode="synthetic",
        status=FAIL_STATUS if failed else PASS_STATUS,
        staging_base_url=staging_base_url,
    )
    summary["checks"] = checks
    return (EXIT_FAILED if failed else EXIT_OK), summary


def _write_summary(summary: dict[str, Any]) -> None:
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run an offline WS2 multi-instance smoke preflight. "
            f"Staging checks are descriptive unless {NETWORK_OPT_IN_ENV}=1 is set."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Emit planned checks only; this is the default.")
    mode.add_argument("--synthetic", action="store_true", help="Run disposable local synthetic checks and emit JSON.")
    parser.add_argument(
        "--staging-base-url",
        help="Optional staging target marker. The URL is never printed; real calls are not implemented here.",
    )
    args = parser.parse_args(argv)

    if args.synthetic:
        exit_code, summary = run_synthetic_preflight(staging_base_url=args.staging_base_url)
    else:
        exit_code = EXIT_OK
        summary = build_dry_run_summary(staging_base_url=args.staging_base_url)
    _write_summary(summary)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
