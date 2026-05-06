# WS2 Multi-instance Smoke Test Design

Date: 2026-05-06
Mode: docs-only smoke-test design. No runtime behavior, schema, migrations, tests, providers, workers, brokers, databases, or frontend code changed.

## 1. Executive summary

WolfyStock has completed or started the WS2 foundations that make a future multi-instance deployment testable: durable task state, a synthetic durable worker prototype, durable progress polling, quota dry-run pieces, cost-ledger observation, and provider circuit storage foundations. The current production-safe runtime contract is still single API process by default because `AnalysisTaskQueue` and `/api/v1/analysis/tasks/stream` SSE state remain process-local.

Multi-instance smoke testing is needed before public multi-user deployment because a load balancer can route submit, status, polling, SSE reconnect, cancellation, export, admin, and quota reads to different API processes. A safe deployment must prove that owner-scoped durable state survives that switch, worker lease/retry behavior is recoverable, polling is the reliability baseline, and readiness warns when the process-local queue/SSE topology is unsafe.

Before public multi-user deployment, the smoke must prove:

- a task submitted through API instance A can be leased by a worker and read from API instance B;
- durable status and progress polling are owner-scoped and replayable from any API instance;
- process-local SSE limitations are visible and do not get misrepresented as cross-instance reliability;
- worker crash, lease expiry, retry, and terminal failure paths do not corrupt task state;
- quota dry-run, cost ledger observation, provider circuit diagnostics, and readiness surfaces expose degraded state without secrets;
- no cross-owner or guest/authenticated bucket leakage occurs across task, progress, quota, cost, provider, and future export paths.

This task does not implement runtime multi-instance behavior. It does not add Redis, Celery, RQ, Kafka, a queue cutover, schema migrations, provider/LLM calls, live quota enforcement, frontend changes, test code, worker process changes, auth/RBAC changes, or modifications to the existing process-local queue/SSE runtime.

## 2. Topology under test

Future synthetic topology:

```text
Browser or smoke client
  -> reverse proxy / load balancer
      -> API instance A
      -> API instance B
  -> worker process
  -> PostgreSQL durable state
  -> optional future queue placeholder
       - Redis/RQ/Celery-style broker, or
       - PostgreSQL-backed queue using leases
```

API instance A/B:

- run the same application build and configuration, with separate process memory;
- do not share `AnalysisTaskQueue` in-memory tasks or SSE subscribers;
- read durable task state and durable progress events from PostgreSQL;
- expose readiness that distinguishes live API health from unsafe task queue/SSE topology.

Worker process:

- claims only durable queued tasks through the future queue/lease contract;
- writes status, progress events, retries, failure summaries, and terminal state to PostgreSQL;
- uses fake provider/LLM adapters only in smoke; no live providers or LLMs.

PostgreSQL:

- is the durable baseline for task state, progress events, quota dry-run/reservation state, cost ledger rows, provider circuit state, and admin readiness summaries;
- smoke data must be synthetic and isolated from production DB contents;
- SQLite remains acceptable for local single-process developer smoke, but it cannot prove cross-instance PostgreSQL readiness.

Optional queue placeholder:

- the design may model Redis/Postgres queue behavior, but the first smoke should not introduce or require a real broker dependency unless a later implementation prompt explicitly approves it;
- a Postgres lease-only synthetic queue is acceptable for design validation because the existing WS2 worker prototype already exercises durable claims and lease expiry.

Reverse proxy / sticky routing:

- sticky routing may keep process-local SSE usable for a single user's direct connection, but it is not a substitute for durable polling;
- smoke must include a non-sticky route switch from API A to API B to prove durable reads;
- direct public backend `:8000` exposure is a fail condition for production readiness.

Polling fallback:

- durable polling is the reliability baseline for multi-instance use;
- a reconnect after SSE loss must resume from `after_sequence` and return only owner-scoped events.

Existing SSE limitation:

- `/api/v1/analysis/tasks/stream` is process-local today;
- an SSE connection to API B must not be expected to see API A's process-local subscriber events unless future external event state is implemented;
- this limitation should be visible in smoke output and readiness warnings.

## 3. Smoke scenarios

| Scenario | Synthetic setup | Expected pass condition |
| --- | --- | --- |
| Submit analysis task on API A | Client posts an async synthetic analysis task through API A with owner A credentials. | API A returns an unguessable `task_id`; durable task row exists for owner A; no live provider/LLM call occurs. |
| Worker leases task | A worker process claims the queued task using durable lease semantics. | Task moves through leased/running progress; `lease_owner`, `lease_expires_at`, `attempt_count`, and safe progress events are visible in durable state. |
| Status read from API B | Client reads `/api/v1/analysis/status/{task_id}` through API B. | API B returns owner A's durable status without needing API A memory. |
| Polling returns durable progress | Client polls `/api/v1/analysis/status/{task_id}/poll?after_sequence=N` through API B. | Events after `N` are returned in order, bounded by limit, with `latest_sequence` and `terminal`. |
| Owner A cannot read owner B task | Owner B attempts status and poll reads for owner A's task. | API returns 404 or equivalent owner-hidden response, not existence metadata. |
| SSE process-local limitation is visible | Client opens SSE to API B after task submit on API A with non-sticky routing. | Smoke records that SSE cannot be relied on for cross-instance event delivery while current process-local SSE remains default. |
| Polling fallback works after reconnect | Client drops SSE, reconnects to API B, then polls with last seen sequence. | Polling returns missed durable progress without duplicate or cross-owner events. |
| Worker crash / lease expiry recovery | Worker A claims a task and stops before terminal state; time is advanced or lease expiry is simulated. | Worker B can reclaim after expiry; terminal state is written once; stale worker cannot complete the old lease. |
| Task retry and failure safe summary | Fake adapter returns transient failures until retry cap, then success or terminal failure. | Retry attempts are bounded; non-retryable failures do not retry; stored failure summary is sanitized. |
| Quota dry-run available | Admin/smoke actor calls quota dry-run with synthetic route/provider/model labels. | Decision includes safe allowed/would-block/reason metadata without blocking live work. |
| Cost ledger observer writes usage without blocking | Fake LLM usage is persisted through the observational ledger seam. | Ledger row or synthetic summary is written best-effort; unknown pricing records `pricing_unknown`; task result is not blocked. |
| Provider circuit state can be read if future storage exists | Synthetic provider circuit state is inserted or fixture-loaded. | Admin/readiness sees provider state buckets such as open/degraded/quota-depleted without raw provider payloads. |
| Admin can see readiness/degraded status without secrets | Admin reads health/readiness and degraded summaries. | Output includes storage, queue topology, worker heartbeat, quota/cost/provider states, and no secret values or raw payloads. |

## 4. Owner isolation checks

Task status:

- owner filter is applied before existence is disclosed;
- owner B receives 404/not found for owner A task ids;
- admin cross-owner reads require a future capability-gated diagnostic path and audited reason.

Progress polling:

- `task_id`, `owner_user_id`, and sequence filters are enforced together;
- stale `after_sequence` replay cannot return another owner's events;
- terminal status and last sequence remain owner-scoped.

Cancellation:

- future cancellation must write `cancel_requested_at` only after owner/capability authorization;
- owner B cannot cancel owner A's queued, leased, running, waiting-retry, or terminal tasks;
- worker observes cancellation between stages and records a safe terminal state.

Export/download future paths:

- future report, task artifact, progress export, and failure summary downloads must re-check owner before reading result refs;
- signed or cached download handles must be owner-bound and expire;
- task result refs must not be reusable across owners.

Cost ledger summaries:

- owner summaries include only the authenticated owner or safe guest bucket;
- admin aggregates must be bounded, capability-gated, and avoid raw prompts/provider payloads;
- null-owner/system rows must not be merged into a user's personal cost view.

Quota reservations:

- reservation ids are scoped to owner or guest bucket;
- owner B cannot consume/release owner A reservations;
- expired reservations are reported as safe reason codes, not raw internals.

Provider circuit/admin diagnostics:

- provider/global state is shared operational state but must contain bounded provider/category/route labels only;
- owner-specific depletion or abuse state must not expose another owner's identity or request details;
- admin diagnostics must not include provider URLs, query strings, raw exceptions, credentials, tokens, cookies, or raw session ids.

Guest bucket behavior:

- guest task, quota, and ledger state uses a safe guest bucket hash, never raw guest session ids;
- guest buckets do not leak into authenticated owner summaries after login unless a later migration explicitly links them;
- guest bucket retention is short and cleanup-preview friendly.

## 5. Failure injection

All failure injection must be synthetic. No production DB, live provider, live LLM, broker credential, or real user data is used.

| Failure | Injection method | Expected result |
| --- | --- | --- |
| API A down after task submit | Submit through API A, then route status/poll to API B without relying on API A memory. | Durable state and progress remain readable from API B. |
| API B handles polling | Force status/poll requests to API B after submit on API A. | API B returns the same durable owner-scoped task and events. |
| Worker dies during lease | Stop worker after claim/progress before terminal write. | Task remains non-terminal until lease expiry; next worker can reclaim; stale completion is rejected. |
| DB temporarily unavailable | Use a synthetic DB outage fixture or dependency wrapper in future smoke. | Readiness returns degraded/not ready; API does not leak stack traces or secrets; no terminal state is corrupted. |
| Queue unavailable | Simulate optional queue placeholder refusing enqueue/claim. | Readiness warns; submit either fails safely before task acceptance or records durable accepted state with explicit pending queue error according to future contract. |
| Provider unavailable via fake adapter | Fake provider returns timeout, 429, 403, 5xx, malformed payload, and network error buckets. | Provider circuit/quota dry-run state records safe reason buckets; no live provider call occurs. |
| LLM pricing unknown | Fake LLM usage uses a provider/model without active pricing. | Cost ledger records `pricing_unknown` and zero estimated cost; task success/failure behavior is not blocked. |
| Quota reservation expired | Create synthetic reservation, expire it, then attempt consume/release. | Safe expired-reservation code is returned; no live enforcement side effect. |
| Stale progress replay | Poll with old `after_sequence`, duplicated sequence, and beyond-latest sequence. | Replay is ordered, idempotent for client recovery, bounded by limit, and never crosses owner. |

## 6. Observability checks

Required smoke metrics and log checks:

- task queue depth by status and task type;
- active lease count and max lease age;
- oldest queued task age;
- worker heartbeat age and worker id label;
- polling fallback rate and poll error rate;
- SSE disconnect rate and reconnect reason bucket;
- quota dry-run decisions by route family, owner/guest bucket, provider/model label, and safe reason code;
- cost ledger row count and summarized estimated cost/status buckets, including `pricing_unknown`;
- provider circuit states by provider/category/route and reason bucket;
- DB pool status, connection wait, slow query buckets, table/index/storage growth summaries, and cleanup dry-run candidate counts;
- readiness/live status split, including warnings for unsafe process-local queue/SSE topology;
- no secret leakage in logs, readiness, admin diagnostics, progress events, failure summaries, cost metadata, quota metadata, or provider circuit metadata.

Secret leakage checks must scan for accidental values only through safe synthetic fixtures. The smoke must never print, inspect, copy, or assert against real `.env` values, API keys, cookies, tokens, webhook URLs, raw session ids, raw prompts, raw provider payloads, DB contents, or password hashes.

## 7. Acceptance criteria

Pass criteria:

- no cross-owner data leak in task status, polling, cancellation, quota, cost, provider diagnostics, or future export/download placeholders;
- durable task state survives an API A to API B route switch;
- durable polling works from any API instance using `after_sequence`;
- worker crash and lease expiry recovery do not corrupt terminal state and do not allow stale workers to complete old claims;
- retry and failure summaries are bounded, sanitized, and respect retry caps;
- no live provider or live LLM is required;
- no production DB or production DB contents are used;
- direct public backend `:8000` is not exposed in the production smoke topology;
- readiness warns or fails when configured for unsafe multi-process process-local queue/SSE topology;
- admin readiness/degraded output contains safe labels and reason buckets only;
- the existing process-local `AnalysisTaskQueue` and SSE remain the default until a separate approved cutover.

Fail criteria:

- owner B can infer existence or progress for owner A's task;
- API B cannot read durable status/progress after API A submit;
- SSE is presented as cross-instance reliable while still process-local;
- a worker crash leaves an unrecoverable non-terminal task past lease expiry;
- a stale worker can write terminal state after another worker reclaimed the task;
- smoke requires live provider/LLM credentials or calls;
- smoke prints secrets, raw prompts, raw provider payloads, raw session ids, or DB contents;
- readiness reports healthy for an unsafe multi-worker process-local queue/SSE topology;
- production smoke exposes backend `:8000` directly to the public internet.

## 8. Local smoke command sketch

Design-only future command names:

```bash
# Local single-process compatibility smoke; SQLite allowed.
python3 scripts/ws2_multi_instance_smoke.py --mode local-sqlite --fake-provider --fake-llm

# Local PostgreSQL synthetic smoke; requires disposable local PostgreSQL only.
python3 scripts/ws2_multi_instance_smoke.py --mode local-postgres --fake-provider --fake-llm --no-live-credentials

# Optional Make targets if the repo standardizes them later.
make ws2-smoke-local
make ws2-smoke-postgres
make ws2-smoke-ci
```

Expectations:

- `local-sqlite` may prove owner isolation, durable state helpers, polling replay, retry, and sanitized failure behavior, but it cannot prove true multi-instance PostgreSQL readiness;
- `local-postgres` must use a disposable local database with synthetic fixtures only;
- no command may read production DB connection strings, use production DB contents, call live providers, call live LLMs, require Redis/Celery/RQ/Kafka, start public servers, or print secrets;
- fake provider and fake LLM adapters must be the only external-work simulators;
- smoke output should be a concise PASS/FAIL table plus safe diagnostic buckets.

## 9. Rollout sequence

1. Design only: keep this document as the current contract and do not change runtime behavior.
2. Local synthetic smoke script: implement a script that uses fake provider/LLM fixtures and disposable storage to prove owner isolation, durable polling, lease recovery, retry, quota dry-run, cost observer, provider circuit read, and readiness warnings.
3. CI synthetic smoke: run the same script against isolated test storage with no live credentials and no production DB access.
4. Staging multi-instance smoke: run API A/B, one worker, PostgreSQL, and optional approved queue placeholder behind a staging reverse proxy; use fake provider/LLM fixtures and synthetic users only.
5. Production readiness checklist: require HTTPS reverse proxy, no direct public `:8000`, PostgreSQL backups/restore smoke, DB growth dashboards, worker heartbeat, queue depth, readiness/degraded warnings, and secret-leak scans before any public multi-user rollout.
6. Rollback plan: keep single API process with process-local queue/SSE as the fallback deployment; disable worker/queue staging components; route traffic back to the last-good single-process build; verify `/api/health/live`, `/api/health/ready`, status polling, and owner isolation with synthetic data.

## 10. Non-goals

- no runtime behavior changes;
- no queue cutover;
- no Redis/Celery/RQ/Kafka dependency;
- no provider or LLM live calls;
- no live quota enforcement;
- no frontend changes;
- no schema migrations;
- no tests added or modified in this task;
- no changes to `AnalysisTaskQueue`, worker runtime, SSE runtime, provider adapters, MarketCache, quota service, cost ledger runtime, Options, scanner, backtest, portfolio, RBAC, or auth runtime;
- no production DB connection and no DB content inspection.

## 11. Recommended next Codex prompts

1. Implement a docs-backed `scripts/ws2_multi_instance_smoke.py` local synthetic smoke script for SQLite and disposable PostgreSQL modes. Use fake provider/LLM adapters only, do not add Redis/Celery/RQ/Kafka, do not modify runtime queue/SSE/provider behavior, and verify owner isolation, durable polling, worker lease recovery, retry caps, quota dry-run, cost observer, provider circuit reads, and readiness warnings.
2. Add CI wiring for the WS2 synthetic smoke script using isolated test storage and no live credentials. Do not call providers/LLMs, do not connect to production DB, and keep the existing runtime defaults unchanged.
3. Design a staging-only API A/B plus worker smoke environment behind a reverse proxy. Keep provider/LLM fake-only, prove polling from any API instance, make process-local SSE limitations explicit, and require readiness warnings for unsafe topology.
4. Extend readiness documentation for multi-instance staging to include worker heartbeat, queue depth, lease age, polling fallback rate, SSE disconnect rate, provider circuit state, quota dry-run decisions, cost ledger summaries, DB pool/slow query/storage growth, and no-secret logging checks.
5. Draft a production multi-user readiness checklist that keeps single-process runtime as the rollback path until queue/SSE externalization is separately approved.
