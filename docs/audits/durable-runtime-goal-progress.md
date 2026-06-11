# Durable Runtime Goal Progress

Date: 2026-06-11
Mode: guarded prototype. Production cutover remains disabled.

## Goal

Prototype Durable Runtime v1 for analysis/backtest-style jobs using persisted
task state, fixture-backed execution, owner-scoped status, and explicit
multi-instance safety boundaries.

Done means:

- durable task state has a concrete design path for analysis/backtest-style jobs;
- prototype execution can claim, lease, heartbeat, retry, fail, recover, and
  expose owner-scoped status using synthetic/local fixtures;
- process-local SSE limitations remain documented, with durable polling as the
  safe baseline;
- tests cover crash/retry/owner-isolation semantics;
- production queue/worker cutover remains disabled and explicit.

## Current Baseline

Implemented foundations already present:

- `durable_task_states` and `durable_task_progress_events` persist owner-scoped
  state, progress, attempts, leases, dedupe keys, and sanitized metadata.
- `DatabaseManager` exposes durable create/reserve/read/list/progress replay,
  claim, heartbeat, complete, and fail helpers.
- `/api/v1/analysis/status/{task_id}` falls back to durable state when the
  process-local queue has no task.
- `/api/v1/analysis/status/{task_id}/poll` returns owner-scoped durable state
  and replayable progress events.
- `/api/v1/analysis/tasks/{task_id}/progress` durable fallback normalizes stored
  states before response validation and remains owner scoped.
- `DurableTaskWorkerPrototype` is a fixture-backed worker for
  `ws2_synthetic_fixture` tasks.
- `build_durable_runtime_envelope()` keeps synthetic guard fields authoritative
  and drops unsafe secret/internal `extra_metadata` keys.
- `AnalysisTaskQueue` and `/api/v1/analysis/tasks/stream` SSE remain
  process-local.

Important boundary: these foundations do not recover production analysis futures
or rule-backtest background work after process loss. They are prototype and
readiness evidence until a separate cutover task is approved.

Known foundation gaps that remain outside this prototype slice:

- claim is implemented through the current `DatabaseManager` transaction helper,
  not a separately accepted distributed queue contract with fencing tokens;
- retry has a bounded attempt cap but no accepted retry-after/backoff or
  dead-letter policy;
- lease expiry recovery is covered by prototype tests, but there is no
  production supervisor/reaper runbook yet;
- failure reason codes are safe prototype strings, not a final production enum;
- durable rows do not recreate lost process-local futures.

## Durable Runtime v1 Design

Durable Runtime v1 is a narrow prototype layer over the existing durable task
tables. It does not introduce a broker, migration, provider calls, frontend
dependency, or production route cutover.

### Task Envelope

Prototype jobs use a bounded task envelope stored in durable task metadata:

- `runtime_schema`: `durable_runtime_v1`
- `job_kind`: `analysis_fixture` or `backtest_fixture`
- `symbol`: optional synthetic symbol label
- `fixture_name`: local fixture adapter name
- `source`: `synthetic_fixture`
- `production_cutover_enabled`: `false`

The task row remains the source of truth for:

- task id, owner, task type, route family;
- status, progress, current step;
- attempts, max attempts, lease owner, lease expiry;
- sanitized metadata and terminal error summary.

Additional envelope metadata is optional and bounded. The envelope builder drops
synthetic guard overrides and secret/internal metadata keys such as `api_key`,
`token`, `secret`, `prompt`, `raw_*`, `session`, `webhook`, `url`,
`provider_payload`, `stack`, `trace`, `debug`, `authorization`, and `cookie`,
including common nested and camelCase variants.

### State Machine

Prototype-visible states map to existing stored states:

| Stored state | Prototype meaning | Terminal |
| --- | --- | --- |
| `queued` / `pending` / `waiting_retry` | claimable work | no |
| `leased` | claimed by a worker, before first heartbeat | no |
| `processing` | worker heartbeat accepted | no |
| `completed` | terminal success | yes |
| `failed` | terminal failure or retry cap exhausted | yes |
| `cancelled` / `canceled` | future terminal cancellation state | yes |

Allowed transitions:

- reserve/create -> `queued`
- claim -> `leased`, increment `attempt_count`, set `lease_owner` and
  `lease_expires_at`
- heartbeat -> `processing`, extend lease, write progress/current step
- transient fail below retry cap -> `queued`
- transient fail at cap -> `failed`
- non-retryable fail -> `failed`
- complete under active lease -> `completed`
- expired `leased`/`processing` -> claimable by another worker

Rejected transitions:

- stale worker terminal write after lease is reclaimed;
- non-owner status or progress read;
- default synthetic worker claiming production `analysis` rows;
- live provider/LLM/backtest engine execution from this prototype.

### Worker Architecture

`DurableTaskWorkerPrototype` stays fixture-backed. Durable Runtime v1 extends the
prototype around a small synthetic adapter boundary rather than coupling it to
analysis/backtest services.

```text
Synthetic task fixture
  -> durable task row (`task_type=durable_runtime_v1_synthetic`)
  -> worker claim + lease
  -> adapter stage heartbeats
  -> retry/fail/complete terminal write
  -> owner-scoped status/poll projection
```

Adapters are local functions/classes that return deterministic stage outcomes:

- `analysis_fixture`: simulates data/AI/report stages without network calls;
- `backtest_fixture`: simulates parse/compute/export stages without engine math;
- `transient_failure`: fails retryably a configured number of times;
- `terminal_failure`: fails once without retry.

No adapter may import provider clients, call `AnalysisService`, call
`RuleBacktestService`, execute backtest engines, create reports, or open network
connections.

### Status Projection

Safe status comes from durable task state and progress events. The production
status endpoints already provide the conservative read path:

- process-local queue first for current production async tasks;
- durable fallback for persisted owner-scoped rows;
- durable polling for cross-process replay.

Durable Runtime v1 can add prototype-only projection helpers and tests, but the
default production route behavior stays unchanged.

The Home/admin progress route must reuse the same normalized projection as
`/status/{task_id}` before Pydantic validation:

- `queued`, `pending`, `waiting_retry` -> `pending`
- `leased`, `processing`, `running` -> `processing`
- `completed` -> `completed`
- `failed`, `cancelled`, `canceled` -> `failed`

### SSE and Polling Boundary

Process-local SSE remains limited to the current API process. It is useful for a
single-process/local user experience, but it is not cross-instance durable
delivery.

Safe baseline:

- clients use durable polling for cross-instance status and progress replay;
- SSE can be an opportunistic signal only;
- production readiness must keep reporting process-local SSE as non-distributed
  until external broadcast/replay evidence exists.

## Implementation Slices

### Slice 1: Design Durable Worker

Status: complete.

Planned files:

- Create `docs/audits/durable-runtime-goal-progress.md`

Acceptance:

- design names the persisted state contract, worker boundaries, SSE limitation,
  polling baseline, and production NO-GO blockers.

### Slice 2: Task State Machine

Status: complete.

Planned files:

- Add `src/services/durable_runtime_contracts.py` for v1 prototype constants,
  state/failure mapping, and guarded envelope helpers.
- Add focused tests around existing `DatabaseManager` durable state helpers.

Acceptance:

- tests prove claim/lease/heartbeat/complete/fail/retry/recover semantics;
- no migration required;
- stored states remain backward compatible with existing WS2 tests.

Implemented:

- `src/services/durable_runtime_contracts.py`
- `tests/test_durable_runtime_contracts.py`
- `tests/test_durable_runtime_progress_projection.py`
- durable fallback status projection in `api/v1/endpoints/analysis.py`
- durable fallback progress projection in `src/services/system_config_service.py`

Validation:

- `PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m pytest -p no:cacheprovider tests/test_durable_runtime_contracts.py tests/test_durable_runtime_progress_projection.py tests/test_durable_task_state.py tests/test_system_config_service.py tests/test_analysis_api_contract.py -q`
  passed with 130 tests.
- `PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m py_compile src/services/durable_runtime_contracts.py src/services/system_config_service.py api/v1/endpoints/analysis.py`
  passed.
- `git diff --check` passed.
- Secret scan evidence superseded by the final full branch scan in Slice 5.

### Slice 3: Synthetic Worker Prototype

Status: complete.

Planned files:

- Add `src/services/durable_runtime_v1.py` as the prototype worker/adapters
  wrapper over existing durable task storage.
- Keep `src/services/durable_task_worker.py` backward compatible for WS2 tests.
- Add tests proving analysis/backtest-style fixture envelopes do not call live
  providers or engines.

Acceptance:

- worker only claims prototype task type by default;
- fixture stages emit safe progress events;
- retries are bounded by `max_attempts`;
- terminal writes require the active lease.

Implemented:

- `src/services/durable_runtime_v1.py`
- `tests/test_durable_runtime_v1_worker.py`

Validation:

- `PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m pytest -p no:cacheprovider tests/test_durable_runtime_v1_worker.py -q`
  passed with 4 tests.
- `PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m pytest -p no:cacheprovider tests/test_durable_runtime_v1_worker.py tests/test_durable_runtime_contracts.py tests/test_durable_runtime_progress_projection.py tests/test_ws2_durable_task_worker.py -q`
  passed with 32 tests.
- `PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m py_compile src/services/durable_runtime_v1.py src/services/durable_runtime_contracts.py src/services/system_config_service.py api/v1/endpoints/analysis.py`
  passed.
- `git diff --check` passed.
- Secret scan evidence superseded by the final full branch scan in Slice 5.

### Slice 4: Recovery and Owner Tests

Status: complete.

Planned files:

- Add tests for API A/B disposable SQLite simulation, owner isolation, polling
  replay, expired lease recovery, and stale-worker rejection.

Acceptance:

- another owner gets sanitized not-found responses;
- polling with `after_sequence` returns bounded owner-scoped progress;
- crashed/stalled worker can be recovered after lease expiry;
- stale worker cannot overwrite terminal state.

Implemented:

- `tests/test_durable_runtime_v1_recovery.py` covers fresh API-process status
  visibility, owner-isolated not-found responses, bounded polling replay after
  `after_sequence`, expired lease recovery, stale-worker rejection, and
  sanitized terminal failure polling.
- `tests/test_durable_runtime_progress_projection.py` covers shared durable
  status normalization for `/status/{task_id}`, `/status/{task_id}/poll`, and
  `/api/v1/analysis/tasks/{task_id}/progress`.

Validation:

- Covered by the final focused pytest command in Slice 5.

### Slice 5: Docs and Final Verification

Status: complete for this guarded prototype checkpoint. Production cutover
remains disabled.

Planned files:

- Update docs that summarize process-local SSE, durable polling baseline, and
  prototype-only NO-GO boundaries if gaps remain after implementation.

Acceptance:

- focused pytest passes;
- changed Python files compile;
- diff check and secret scan pass;
- final report lists prototype-only behavior and exact cutover blockers.

Final evidence for this branch checkpoint:

- `PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m pytest -p no:cacheprovider tests/test_durable_runtime_contracts.py tests/test_durable_runtime_progress_projection.py tests/test_durable_runtime_v1_worker.py tests/test_durable_runtime_v1_recovery.py tests/test_durable_task_state.py tests/test_ws2_durable_task_worker.py tests/test_system_config_service.py tests/test_analysis_api_contract.py -q`
- `PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m py_compile src/services/durable_runtime_contracts.py src/services/durable_runtime_v1.py src/services/system_config_service.py api/v1/endpoints/analysis.py`
- `git diff --check origin/main..HEAD`
- `./scripts/release_secret_scan.sh`
  - full branch scan mode; covers committed branch changes from
    `origin/main..HEAD` plus staged, unstaged, and untracked text files.

## Production Cutover Status

Production cutover is disabled.

Current NO-GO areas:

- production analysis async submit still uses process-local `AnalysisTaskQueue`;
- production rule-backtest background work is not recovered by this prototype;
- no broker/queue deployment model has been accepted;
- no staging API A/B + worker + PostgreSQL evidence has been accepted;
- SSE is not cross-instance reliable;
- no external event broadcast/replay service exists;
- no production worker runbook, rollback, or capacity SLO is accepted;
- provider/cache/auth/RBAC/backtest engine behavior is unchanged.

Cutover blockers:

1. Approved production job envelope for real analysis/backtest payloads.
2. Broker or database-backed claim model selected with capacity and rollback
   evidence.
3. Staging API A/B smoke proves submit, worker lease, API B status, polling
   replay, retry/failure safety, and owner isolation.
4. Worker heartbeat/readiness and queue-depth observability accepted.
5. Auth/RBAC review for any cross-owner admin status view.
6. Provider/LLM/backtest adapters explicitly hardened and tested for idempotency.
7. Runbooks for deploy, rollback, stuck lease recovery, and operator escalation.

## Validation Plan

Focused commands for this goal:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m pytest -p no:cacheprovider \
  tests/test_durable_runtime_contracts.py \
  tests/test_durable_runtime_progress_projection.py \
  tests/test_durable_runtime_v1_worker.py \
  tests/test_durable_runtime_v1_recovery.py \
  tests/test_durable_task_state.py \
  tests/test_ws2_durable_task_worker.py \
  tests/test_system_config_service.py \
  tests/test_analysis_api_contract.py \
  -q

PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m py_compile \
  src/services/durable_runtime_contracts.py \
  src/services/durable_runtime_v1.py \
  src/services/system_config_service.py \
  api/v1/endpoints/analysis.py

git diff --check origin/main..HEAD
./scripts/release_secret_scan.sh
```

If new tests or modules are added, include them in the focused pytest and
py_compile command before checkpointing.
