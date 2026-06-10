# Background Job Queue Boundary

Status: boundary note only. No first-class brokered job queue is implemented or enabled today.

## Current status

- T-646 concluded that a real queue implementation is still premature.
- T-647 locked the first safe future boundary with contract tests around backtest job JSON-safe serialization, idempotent stored readback, and local-only universe-job execution.
- Current async/background behavior remains process-local or route/script-specific, not a general broker/worker system.
- T-1405/T-1421 keep durable async recovery as production/multi-instance **NO-GO**. Durable rows, progress events, and the synthetic worker prototype are contract evidence, not launch approval.

## Production deployment boundary

- Current public-safe runtime posture is a single API process, or sticky routing with accepted task visibility limits.
- Sticky routing can reduce user-facing task/SSE confusion, but it is not durable recovery and does not replace owner-scoped durable polling.
- Multi-instance public deployment remains **NO-GO** until an approved durable worker/queue integration can recover production analysis and rule-backtest work after process-local loss.
- Staging acceptance must prove API A/B route switching, worker lease/retry/failure behavior, owner isolation, polling replay, and sanitized operator evidence before this boundary can move.

## Existing mechanisms today

- MarketCache uses in-process `ThreadPoolExecutor`/`Future` refreshes plus existing TTL, SWR, and cold-start de-duplication semantics.
- Rule backtest async submit uses FastAPI `BackgroundTasks` for `process_submitted_run`; it is request-path scoped, not an external worker.
- Rule backtest universe jobs persist DB-backed run/job state and compact symbol rows; execution remains stored, sequential, and local-data-only.
- Analysis async submit uses process-local `AnalysisTaskQueue` futures. Durable task rows can support owner-scoped status/polling and active duplicate protection, but they do not recreate lost futures or resume production analysis execution.
- The WS2 durable worker prototype is fixture-backed synthetic coverage. It must not be presented as production analysis/backtest route recovery.
- Admin log cleanup is an explicit `POST /api/v1/admin/logs/cleanup` maintenance action with dry-run / preview-first semantics; it is not an automatic queue consumer.
- Prewarm, diagnostics, and backfill-like operator surfaces are script-only or explicitly invoked maintenance paths, not a shared job queue layer.

## First safe future queue boundary

- The first candidate, if a queue is ever needed, is backtest async/local-only universe jobs.
- Queue payloads must stay JSON-safe and primitive-only projections.
- Persistent run/job state in the database remains the source of truth.
- Local-only and no-provider-call contracts must stay explicit and visible.
- A first worker payload must not carry DB sessions, service instances, users/sessions, locks, futures, generators, or provider instances.

## Technology posture

- No queue is selected or enabled by this document.
- Reassess only after the serialization/idempotency/local-only contracts remain sufficient and the workload proves a queue is necessary.
- If a first broker is later justified, Dramatiq plus Redis/Valkey currently appears more proportionate than Celery or Temporal, but this note does not choose or authorize any broker.

## Explicitly forbidden in a first queue pass

- provider routing/order changes or provider budget bypass
- live-call expansion
- MarketCache TTL, SWR, cold-start, fallback, or cache-key changes
- scanner ranking changes
- backtest math changes
- accounting, ledger, or trading mutation
- API, schema, frontend, or settings changes
- admin auto-delete behavior
- DB migrations unless separately planned

Operational rule: if future queue work needs dependencies, env/config, Docker, migrations, runtime adapters, or changes outside this boundary, stop and open a separate scoped task.
