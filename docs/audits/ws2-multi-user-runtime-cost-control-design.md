# WS2 Multi-user Runtime + LLM/API Cost Control Design

Date: 2026-05-06
Mode: docs-only architecture design. No runtime behavior changed.

## 1. Executive summary

The current WolfyStock server is a reasonable single-process or small-user deployment shape: one API process owns the in-memory analysis queue, the in-memory SSE subscriber list, process-local duplicate protection, and process-local provider/cache state. Recent hardening also adds production security controls, readiness checks, and read-only cost observability surfaces.

That shape is not enough for public multi-user usage. Once the deployment has many users, long-running analyses, scanner/backtest workloads, and LLM/provider quotas competing at the same time, runtime state must move out of one Python process. The production target needs an external queue, durable task state, owner-scoped task reads, explicit quotas, request coalescing, shared cache policy, provider circuit breakers, and queue/latency observability before scaling to multiple API instances.

WS2-R0 is design only. It does not implement Redis, Celery, RQ, workers, migrations, API changes, frontend changes, dependencies, or runtime behavior.

## WS2-R1 implementation note

- Durable task/progress state is now backed by a new `durable_task_states` table and narrow `DatabaseManager` helpers for create/update/complete/fail/read flows.
- Owner-scoped `/api/v1/analysis/status/{task_id}` reads now check the in-memory queue first, then durable state for the authenticated owner, then the existing analysis-history fallback for completed tasks.
- The current process-local queue/SSE implementation remains in place. No worker, Redis, Celery, RQ, Kafka, or external queue cutover has been introduced.
- Remaining WS2 work stays queued for later passes: WS2-R2 worker prototype, WS2-R3 external SSE/polling state, WS2-R4 quota enforcement, and WS2-R5 provider circuit breaker policy.

## WS2-R2 implementation note

- A durable worker prototype now claims and leases one synthetic fixture-backed task type through `durable_task_states`, updates progress, completes safe fixture work, and records sanitized failures.
- Retry behavior is bounded and limited to explicit transient synthetic errors. Validation-style synthetic failures are terminal and are not retried.
- Graceful shutdown is cooperative: the prototype checks a shutdown flag before claiming and between fixture stages, leaving leased in-progress state recoverable by lease expiry instead of corrupting terminal state.
- This is not a production queue cutover. Existing process-local `AnalysisTaskQueue` and SSE behavior remain the production default.
- No Redis, Celery, RQ, Dramatiq, Kafka, or external queue dependency was added, and the prototype does not call live LLM, provider, broker, scanner, backtest, portfolio, or frontend paths.
- Remaining WS2 work stays queued for later passes: WS2-R3 external SSE/polling state, WS2-R4 quota enforcement, and WS2-R5 provider circuit breaker policy.

## WS2-R3 implementation note

- Durable progress/event rows are now backed by `durable_task_progress_events`, with owner scope, per-task sequence ordering, bounded sanitized messages, sanitized metadata, and task/owner/time indexes for replay and cleanup-friendly reads.
- Owner-scoped polling fallback is now available through a narrow durable task status+events endpoint. It returns the latest durable task state, replayable events after an optional sequence, the latest sequence, and terminal-state indication.
- The WS2-R2 synthetic worker prototype now writes durable progress events for claim, fixture progress, retry/failure, and completion paths while remaining fixture-only.
- Current process-local `AnalysisTaskQueue` and `/api/v1/analysis/tasks/stream` SSE behavior remain the default. Production SSE is not routed through durable progress rows in this pass.
- No Redis, Celery, RQ, Dramatiq, Kafka, external queue dependency, multi-instance cutover, quota enforcement, live LLM/provider call, scanner/backtest/portfolio/provider behavior change, or frontend change was introduced.
- Remaining WS2 work stays queued for later passes: WS2-R4 quota enforcement and WS2-R5 provider circuit breaker policy. External SSE replay/cutover remains future work.

## WS2-R4 prerequisite implementation note

- Quota schema foundation is now backed by `quota_policy_definitions`, `quota_usage_windows`, and `quota_reservations`, with narrow indexes for policy lookup, owner/window accounting, route/provider windows, and reservation lifecycle cleanup.
- `QuotaPolicyService` provides deterministic synthetic checks for route weights, budget-unit estimation, global kill switch, per-user daily/monthly budget, route request caps, token caps, safe rejection reason codes, metadata sanitization, and reserve/consume/release/expired reservation lifecycle.
- Quota enforcement remains disabled by default unless a caller explicitly instantiates the service with enforcement enabled. The service is callable by future routes, but this pass does not wire it into live LLM/provider execution or any product route.
- No live LLM/provider calls were added, and no LLM prompts, model routing, provider fallback, scanner AI behavior, MarketCache behavior, Options Lab behavior, portfolio/backtest/scanner calculations, notifications, broker/order paths, or DuckDB production runtime were changed.
- Remaining WS2-R4 work: route integration/enforcement, admin dashboard and policy editing, provider quota buckets, circuit breaker policy, actual usage reconciliation from provider responses, and retention/cleanup dry runs for quota ledgers.

## WS2-R4A dry-run/pilot integration note

- Admin cost diagnostics now include `POST /api/v1/admin/cost/quota-dry-run`, guarded by `cost:observability:read`, for quota policy dry-run / pilot evaluation.
- The endpoint classifies route family, estimates budget units, returns safe decision metadata, and supports explicit diagnostic `reserve`, `consume`, and `release` operations against the existing synthetic quota reservation tables.
- Default behavior remains non-blocking: no live route enforcement, no user workflow blocking, no provider/LLM blocking, and no scanner/backtest/portfolio/Options/MarketCache/DuckDB/broker/notification behavior change.
- The endpoint response is sanitized and does not include raw prompts, provider payloads, credentials, cookies, raw session identifiers, stack traces, or secret-like request metadata.
- Future work remains separate: selected route enforcement, admin dashboard/policy editing, provider quota buckets, circuit breaker policy, and reconciliation from actual usage.

## WS2-R4B LLM cost ledger foundation note

- LLM pricing policy foundation now exists through `model_pricing_policies`, with provider/model keys, per-1M input/cached-input/output prices, currency, source label/URL metadata, active flag, and effective-date ranges.
- LLM cost ledger foundation now exists through `llm_cost_ledger`, with owner/guest dimensions, route family, call type, provider/model, prompt/cached/completion/total tokens, Decimal-safe estimated USD cost fields, pricing snapshot metadata, optional quota reservation link, request hash, status, and sanitized metadata.
- `LlmCostLedgerService` supports synthetic usage reconciliation: it looks up effective active pricing, returns safe result codes (`ok`, `pricing_unknown`, `invalid_usage`, `pricing_inactive`), computes regular and cached input/output estimated cost, and writes sanitized ledger rows.
- Admin read-only diagnostics now include `GET /api/v1/admin/cost/llm-ledger-summary`, guarded by `cost:observability:read`, for total, per-user, provider/model, and route-family ledger summaries.
- This is not live enforcement and is not wired into live LLM/provider execution. No prompts, model routing/order, fallback, retry, integrity retry, provider behavior, scanner/backtest/portfolio/Options/MarketCache/DuckDB/broker/notification behavior changed.
- Future work remains separate: live instrumentation integration, provider response reconciliation, quota consume/release reconciliation, pricing source update workflow, admin dashboard UX, retention/aggregation policy, and budget enforcement.

## WS2-R4C LLM usage observer reconciliation note

- Existing normalized `persist_llm_usage(...)` writes now invoke a best-effort LLM cost ledger observer after the legacy `llm_usage` row is recorded.
- The observer uses only normalized usage fields already available at the successful response seam: provider/model labels, route family/call type, prompt/cached/completion/total token counts when present, optional owner/guest identifiers, optional request hash, and sanitized bounded metadata.
- Ledger reconciliation is observational only. A ledger write failure is swallowed and cannot change the user-visible LLM result, prompt, model routing/order, provider selection, fallback, retry, integrity retry, or provider behavior.
- No raw prompts, raw provider payloads, credentials, cookies, raw session identifiers, stack traces, or secret-like metadata are stored by the observer.
- Missing active pricing policy remains safe: the ledger row records `pricing_unknown` with zero estimated cost according to `LlmCostLedgerService`; there is no live price fetch or pricing-page scrape.
- Per-user accounting is precise only where the caller passes `owner_user_id` or a guest bucket into the usage seam. Current analyzer/agent usage paths continue to preserve existing behavior and may still write global/null-owner ledger rows until owner context propagation is completed.
- Quota reservation reconciliation is not consumed or released unless a future caller passes a safe `quota_reservation_id`; live quota enforcement remains out of scope.
- Future work remains separate: complete owner/guest propagation at product route boundaries, connect safe quota reservation reconciliation, improve admin dashboard UX, and add retention/aggregation polish.
## 2. Current deployment assumptions

- API single-process assumption: `docs/DEPLOY.md` and `docs/deploy-webui-cloud.md` currently state that `/api/v1/analysis/*` task queue and SSE state are process-local and should stay single-process unless sticky routing is intentionally provided.
- Analysis task queue: `src/services/task_queue.py` uses a singleton `AnalysisTaskQueue`, `ThreadPoolExecutor`, in-memory `task_id -> TaskInfo`, in-memory owner/symbol dedupe, and an in-memory subscriber list for SSE events.
- SSE state: `/api/v1/analysis/tasks/stream` subscribes to the current process, emits current pending tasks for the owner, filters events by `owner_id`, and sends heartbeats. A second API process would not see this subscriber or task state.
- Status reads: `/api/v1/analysis/status/{task_id}` first checks the in-memory queue, then falls back to persisted analysis history for completed tasks. Pending/running task truth is not durable today.
- Backtest/scanner/options shape: scanner runs and rule backtests already persist domain results, but scanner execution is synchronous in the API request path and rule backtest async execution uses FastAPI `BackgroundTasks`, not an external worker. Options endpoints are fixture-backed/read-only today.
- No simple multi-worker expansion yet: readiness checks expose the process-local task queue topology and warn when worker-count hints imply unsafe multi-worker deployment.
- Current security hardening already done: recent security work covers durable login throttling, safer production cookie/CORS/origin behavior, security headers, reverse-proxy guidance, and sanitized admin/security logs. RBAC, MFA, KDF upgrade, and deeper audit retention remain separate follow-ups.
- Current cost observability already done: LLM/provider/MarketCache/scanner AI instrumentation and duplicate-cost admin summary patterns are read-only, bounded-label, no-external-call, and observational rather than quota enforcement.

## 3. Multi-user risk matrix

| Risk | Current state | User impact | Severity | Required mitigation |
| --- | --- | --- | --- | --- |
| Task status lost across workers | Pending/running analysis state lives in one process memory | Users see 404, stale progress, or missing completion when load-balanced to another process | High | Durable task table plus shared queue lease and owner-scoped status reads |
| LLM cost spikes | LLM usage is recorded and summarized, but not enforced as a budget | One user or route can consume expensive model calls and retry/fallback chains | High | Per-user budgets, per-route cost weights, token caps, retry caps, and global kill switch |
| Provider quota exhaustion | Provider fallback/cache counters exist, but provider quotas are not enforced globally | Shared data providers can hit 429/403 and degrade all users | High | Provider quota buckets, circuit breakers, stale/cache fallback, and alerting |
| Long-running requests | Sync analysis, scanner, and some backtest paths can hold request workers | API latency rises and clients time out under load | High | Move long jobs to workers; enforce API timeouts and async task submission |
| Backtest/scanner CPU contention | Scanner and backtest execution can compete with API request threads | Interactive routes slow down or fail during heavy computation | Medium/High | Queue CPU-heavy work separately, set worker concurrency, and add per-user limits |
| SSE cross-instance issues | SSE subscriber queues are process-local | Clients miss progress events after load-balancing or deploy restarts | High | Sticky routing in Stage C or external event stream/state with polling fallback |
| Per-user data isolation | Many tables and services now include `owner_id`, but future task/cache keys must preserve that pattern | Users may see or affect another user's tasks, cached report, export, or quota | High | Owner checks on every task/status/SSE/export path and owner-aware cache keys |
| DB growth | Analysis history, execution logs, scanner, backtest, portfolio, and LLM usage grow over time | Slow queries, larger backups, full disks, and expensive admin logs | Medium | Retention/archive policy, indexes, partition candidates, backup/restore drills |
| Cache stampede | MarketCache/provider caches are process-local and miss after restart or across workers | Many users can trigger identical external calls at once | Medium/High | Shared cache, per-key locks, request coalescing, stale-while-revalidate |
| Noisy-neighbor users | Current limits are mostly route/request validation, not tenant budgets | One user can occupy workers, queue slots, provider quota, and LLM budget | High | Per-user queue depth, concurrency, budget, and rate-limit enforcement |

## 4. Target architecture

Stage A: single API process + PostgreSQL + strict quotas

- Keep the current single API process deployment for analysis queue/SSE safety.
- Use PostgreSQL as the production baseline for auth, history, task state, logs, quota ledgers, and reporting readiness.
- Add quota enforcement before broader public use: per-user daily/monthly budgets, route weights, provider buckets, and global kill switches.
- Keep existing process-local execution until durable task state is ready.

```text
Browser
  -> HTTPS/Nginx
  -> single API process
      -> process-local analysis queue/SSE
      -> PostgreSQL
      -> LLM/providers with quota guardrails
```

Stage B: API + worker + Redis/Postgres queue + durable task state

- API accepts jobs, writes durable task rows, enqueues work, and returns `task_id`.
- Worker leases jobs, emits progress events, writes result/failure state, and releases dedupe keys.
- Redis/RQ/Celery is suitable for fast queue leases; a Postgres-backed queue is simpler operationally but needs careful locking and polling.

```text
Browser -> API -> PostgreSQL task_state
              -> Redis/Postgres queue -> worker pool
Worker -> PostgreSQL progress/result/failure rows
API -> status/poll reads PostgreSQL
```

Stage C: multiple API instances + sticky routing or external SSE state

- Multiple API instances are allowed only after task state and progress state are externalized.
- If SSE remains process-bound, use sticky routing by user/session/task. Prefer external progress/event state so any API instance can serve polling and SSE replay.
- Polling is the compatibility fallback for deploys where proxy/SSE routing is unreliable.

```text
Browser -> Nginx/LB -> API A/B/C
API A/B/C -> shared PostgreSQL task/progress
API A/B/C -> shared event stream or replayable progress table
Workers -> shared queue and task/progress tables
```

Stage D: full multi-tenant quotas, observability, alerting, autoscale

- Add per-tenant budget policies, route quotas, provider circuit breakers, cost dashboards, queue SLOs, alerting, and autoscale rules.
- Separate API, IO-heavy workers, CPU-heavy backtest/scanner workers, and scheduled/system jobs.
- Use readiness checks for DB, queue, worker heartbeat, cache, and provider-degraded state.

## 5. Task queue design

External queue options:

| Option | Fit | Tradeoff |
| --- | --- | --- |
| Redis + RQ | Simple Python worker model, clear retry/timeout concepts | Adds Redis dependency and separate durability/backup concerns |
| Redis + Celery | Mature routing, retries, schedules, worker pools | More operational complexity and larger dependency surface |
| Postgres-backed queue | Fewer moving parts if PostgreSQL is already required | Requires careful `SKIP LOCKED`, polling, cleanup, and throughput design |

Recommended path: design the durable task schema first, then choose a broker. Do not bind API contracts to a specific queue library.

Task table schema concept, not a migration in this task:

| Field | Purpose |
| --- | --- |
| `task_id` | Unguessable public id, generated server-side |
| `owner_id` | User scope for all reads, SSE/poll events, cancellation, and exports |
| `task_type` | `analysis`, `scanner`, `rule_backtest`, `options_scenario`, future system tasks |
| `status` | Durable lifecycle status |
| `idempotency_key_hash` | Safe hash of client idempotency key or generated request identity |
| `dedupe_key_hash` | Safe hash for coalescing equivalent in-flight work |
| `request_fingerprint_hash` | Safe hash of normalized effective input, excluding secrets/raw prompts |
| `priority` | User/system/admin priority with bounded values |
| `attempt_count`, `max_attempts` | Retry accounting |
| `lease_owner`, `lease_expires_at` | Worker lease and crash recovery |
| `timeout_at`, `cancel_requested_at` | Timeout/cancel controls |
| `created_at`, `started_at`, `completed_at`, `updated_at` | Lifecycle timings |
| `result_ref` | Pointer to persisted domain result, not large raw payload by default |
| `failure_code`, `failure_message_safe` | Bounded failure summary with no raw provider payload |

Task states:

- `queued`: accepted and waiting for a worker.
- `leased`: worker has claimed the task but has not emitted first progress.
- `running`: task is executing and progress is available.
- `waiting_retry`: failed attempt is scheduled for retry.
- `succeeded`: completed and result reference is durable.
- `failed`: final failure with safe failure metadata.
- `cancel_requested`: user/admin requested cancellation.
- `canceled`: cancellation reached a terminal state.
- `expired`: task exceeded retention or timeout without recoverable result.

Owner scope:

- Every task row has an `owner_id` unless it is explicitly system-owned.
- Status, list, progress, SSE replay, cancellation, and export endpoints must filter by `owner_id` before returning existence.
- Admin reads require capability gates after RBAC and should audit sensitive cross-owner reads.

Idempotency and dedupe:

- `idempotency_key_hash` prevents duplicate submit retries from creating new tasks.
- `dedupe_key_hash` coalesces equivalent in-flight work such as same owner/symbol/report/language/source snapshot.
- Dedupe joins should return the existing `task_id` with metadata such as `coalesced=true`.
- Do not dedupe personalized, uploaded-image, credential-bearing, or security-sensitive requests unless the key includes owner/session and approved freshness scope.

Retry policy:

- Retry only transient failures: timeout, provider 429/5xx, network errors, worker crash before side effects.
- Do not retry validation errors, authorization failures, unsupported symbols, or budget-exceeded states.
- Use exponential backoff with jitter and a bounded `max_attempts`.
- Record each attempt as a progress/event row with safe error buckets.

Timeout policy:

- API submit endpoints should return quickly.
- Worker tasks get per-type hard timeouts and softer stage timeouts.
- LLM/provider calls get route-specific timeout caps.
- Timed-out tasks move to `waiting_retry`, `failed`, or `canceled` according to retry/cancel policy.

Cancellation:

- API writes `cancel_requested_at`.
- Worker checks cancellation between stages and before expensive provider/LLM calls.
- Running external calls may be best-effort only; the result must be discarded if the task was canceled before commit.

Failure storage:

- Store bounded `failure_code`, `failure_stage`, `retryable`, and safe message.
- Do not store raw prompt, raw provider response, stack trace, API key, token, cookie, credential, or raw user-uploaded payload.

Progress events:

- Store durable progress rows: `task_id`, `owner_id`, `sequence`, `event_type`, `stage`, `progress`, `message_safe`, `created_at`.
- SSE can replay from the last seen sequence.
- Polling can return the latest task row plus recent progress events.

SSE/polling strategy:

- Stage A: current process-local SSE is acceptable only for single process.
- Stage B: polling reads durable task/progress state and is the reliability baseline.
- Stage C: SSE either requires sticky routing or reads from shared event state. If SSE misses events, clients fall back to polling by `task_id`.
- Keep heartbeat and proxy no-buffering headers, but do not rely on long-lived SSE as the only task truth.

## 6. LLM/API quota and budget design

Quota dimensions:

- Per-user daily and monthly LLM budget, stored as estimated cost units and token buckets.
- Per-route cost weight: guest preview, sync analysis, async analysis, scanner AI, agent/chat, options scenario, provider-heavy market routes.
- Global budget kill switch for all LLM calls and separate kill switches by provider/model tier.
- Per-user concurrent request limit for API routes and per-user concurrent task limit for workers.
- Per-provider quota buckets for LLM and data providers, including 429/403 handling.
- Model tier routing: free/guest routes use cheaper or disabled tiers; authenticated/premium/admin routes can use higher tiers within policy.
- Token caps by route and model tier; cap prompt/context size before sending a call.
- Retry caps for LLM fallback, integrity retry, provider fallback, and connectivity probes.
- Cost estimation before execution, then actual usage accounting after completion.
- Blocked/degraded states: `budget_exceeded`, `provider_quota_depleted`, `llm_disabled`, `degraded_cache_only`, `retry_cap_reached`.
- Admin cost dashboard integration through existing read-only cost observability surfaces, adding enforcement state and budget burn-down later.

Enforcement flow:

```text
request received
  -> authenticate/guest-scope
  -> classify route cost weight
  -> estimate max cost and concurrency impact
  -> reserve budget/quota
  -> enqueue or execute
  -> record actual usage
  -> release unused reservation or record overage reason
```

Important current-state distinction:

- `llm_usage` and the current process-local instrumentation counters are useful for accounting and duplicate-cost observation.
- They are not budget enforcement and are not billing truth.
- WS2-R4 should add enforcement after the quota schema and policy model are reviewed.

## 7. Request dedupe and cache strategy

Report duplicate candidate coalescing:

- Coalesce in-flight analysis for the same owner, canonical symbol, report type, report language, prompt version, model tier, and source snapshot/freshness bucket.
- Current async dedupe is owner plus canonical stock only and only while the task is in memory. The target dedupe key must be durable and more semantically precise.
- Completed report reuse should be a separate cache policy with freshness disclosure and explicit bypass/force-refresh handling.

Same symbol/report/language/prompt/source snapshot:

- Cache identity should include normalized symbol, report type, language, prompt version, model tier, source snapshot hashes, market session/freshness bucket, and owner/session scope where needed.
- Store safe hashes and metadata, not raw prompts or raw provider payloads.

Scanner AI interpretation dedupe:

- Scanner AI remains additive after deterministic shortlist selection.
- Cache only generated interpretation text by candidate hash, prompt version, market/profile, model tier, language, and freshness.
- Do not change scanner ranking, scoring, thresholds, shortlist membership, actionability, or CSV behavior.

Options chain/scenario cache:

- Options chain cache keys include symbol, expiration, side/filter options, provider, `chainAsOf`, and freshness.
- Scenario cache keys include chain snapshot hash, strategy legs, explicit assumptions, model version, and no account data unless owner-scoped.
- Keep no-order/no-advice posture and no raw provider payload storage.

MarketCache reuse boundaries:

- Current `MarketCache` is in-memory with TTL and stale-while-revalidate. It is useful within one process but not shared across workers.
- A future shared cache must preserve TTL, stale serving, background refresh, cold-start fallback, and freshness metadata.
- Do not reuse market panel payloads for user-specific reports unless the report cache key includes source snapshot identity.

Guest preview reuse constraints:

- Guest preview reuse must be guest-session scoped, short TTL, freshness-disclosed, and bypassable with force-refresh.
- Do not mix authenticated user reports and guest preview cache entries.

Storage guardrails:

- No raw prompt storage.
- No raw provider payload storage.
- No API key, token, cookie, broker credential, webhook URL, password hash, or secret value storage in cache metadata.
- Freshness disclosure must show generated-at, source snapshot/freshness, cache hit/stale status, and bypass status.

## 8. Performance acceleration plan

Backend:

- Async worker: move long analysis, scanner, rule backtest, and options scenario jobs out of API request threads.
- Prewarm: precompute common market panels, scanner universes, and provider metadata on a schedule with quota-aware throttling.
- Stale-while-revalidate: serve safe stale data where the product supports it, then refresh in workers.
- Provider timeout/circuit breaker: enforce per-provider timeout, failure-rate window, 429/403 cooldown, and cache-only degraded mode.
- DB indexes: audit owner/time/status/query indexes for task, progress, logs, LLM usage, scanner, backtest, portfolio, and cache metadata.
- Pagination limits: keep strict maximums on task lists, logs, scanner/backtest history, exports, and admin cost views.
- Route latency metrics: capture p50/p95/p99 by route, auth scope, task type, queue wait, and provider/LLM stage.

Frontend:

- Route-level code splitting for large operational pages and heavy chart workspaces.
- Chart lazy loading for backtest, portfolio, Market Overview, and Options Lab visualizations.
- Table virtualization for admin logs, scanner results, backtest traces, portfolio history, and cost drilldowns.
- Static asset caching through the reverse proxy/CDN while keeping API responses private/no-store unless explicitly safe.
- API request coalescing on the client for duplicate route loads, repeated health/provider calls, and repeated panel refreshes.

## 9. Data isolation and authorization

- Owner id scope for all user data: task rows, progress rows, analysis history, scanner runs, backtest runs, portfolio records, conversation records, exports, quota ledgers, and cache entries that depend on user/session data.
- `task_id` unguessability: use server-generated high-entropy ids and never infer authorization from id entropy alone.
- Task owner checks: status/list/progress/cancel endpoints must filter by owner before returning task existence.
- SSE owner validation: initial pending-task replay and every streamed event must validate owner scope. External event streams must preserve owner metadata.
- Export/download owner checks: execution trace, report export, support bundle, CSV, and future task artifacts must verify owner or admin capability before streaming.
- Admin capability gating after RBAC: cross-owner task views, quota override, cancellation, retention cleanup, and sensitive audit reads need explicit capabilities, not coarse admin alone.
- Audit for sensitive admin reads: record actor, capability, target type, target owner bucket, reason where required, and sanitized outcome. Do not audit raw payload content.

## 10. Database production readiness

- PostgreSQL baseline: production multi-user runtime should use PostgreSQL as the durable baseline for auth/session/task/progress/quota/history/log state. SQLite remains useful for local/dev and compatibility until explicit cutover decisions are made.
- Indexes: task table needs owner/status/created, owner/task_id, dedupe hash/status, lease expiry, queue priority, and timeout indexes. Progress needs task/sequence and owner/created indexes. Existing analysis, scanner, backtest, portfolio, and execution-log indexes should be reviewed under production query plans.
- Connection pool: configure pool size, overflow, pool timeout, pre-ping, and worker/API split. Avoid sharing one small pool across API and high-concurrency workers.
- Slow query log: enable database-side slow query logging and app-side query timing for route/task/admin pages.
- Backup/restore: define encrypted backups, retention, restore drills, point-in-time recovery target, and restore smoke checks.
- Retention/archive: define TTLs for task progress, completed task rows, execution logs, LLM usage, provider counters, guest preview cache, scanner/backtest artifacts, and admin audit logs.
- Admin logs capacity: execution logs already exist, but high-frequency success metrics should be aggregated rather than writing unbounded row-per-event logs.
- Migration process: schema changes should be backward-compatible, reviewed, idempotent, and deployable before workers depend on new columns/tables.
- Rollback process: every runtime phase needs a rollback path that can disable workers, stop queue intake, keep API read-only over existing results, and revert schema-dependent code only after data compatibility is understood.

## 11. Observability and alerting

Metrics:

- Route latency p50/p95/p99 by route, method, status, auth scope, and deployment instance.
- Task queue depth by task type, priority, owner bucket, and age.
- Task duration, queue wait, worker lease time, retry count, and timeout count.
- Provider error/timeout/429/403 rate by provider/category/route.
- LLM token/cost estimates by user, route, model tier, provider, and call type.
- Per-user usage: budget consumed, concurrent tasks, queue depth, rate-limit hits.
- Cache hit/miss/stale/fallback/inflight-join rates for MarketCache, provider caches, report cache, scanner AI cache, and options cache.
- SSE connection count, disconnect rate, heartbeat misses, and polling fallback rate.
- DB pool utilization, wait time, slow queries, lock waits, and migration status.
- Error rate by route/task type and safe failure code.
- Rate-limit hits by route, owner bucket, IP/account bucket, and provider bucket.

Alerts:

- Budget exceeded or global budget kill switch engaged.
- Queue stuck: depth or oldest queued age above threshold.
- Provider outage: high timeout/429/403/5xx rate or circuit breaker open.
- High API error rate or p99 latency breach.
- DB backup failed or restore drill overdue.
- Disk/log growth above retention threshold.
- Security anomalies: failed-login spikes, denied admin actions, suspicious export volume, repeated cross-owner access denial.

## 12. Deployment topology

Current recommended single-process deployment:

- Keep one API process for `/api/v1/analysis/*` queue/SSE until external task state exists.
- Use `/api/health/live` for liveness and `/api/health/ready` for storage plus task-queue topology readiness.

Nginx/HTTPS/proxy:

- Terminate HTTPS at Nginx, cloud load balancer, or CDN.
- Forward only trusted headers and configure CORS/CSRF trusted origins explicitly.
- Disable buffering for SSE paths and set longer read timeouts.

API private port only:

- Do not expose public `:8000` directly.
- Bind API to loopback or private network and expose only 80/443 publicly.

Redis/Postgres additions:

- Stage B adds Redis or Postgres-backed queue and durable task/progress tables.
- Use managed Redis/PostgreSQL where possible; otherwise define backup, monitoring, and restart behavior.

Worker process:

- Run separate worker processes for analysis/provider/LLM work.
- Consider separate pools for IO-heavy LLM/provider work and CPU-heavy scanner/backtest work.
- Workers need health/heartbeat rows and graceful shutdown that releases or expires leases.

No direct public 8000:

- Public users should reach only HTTPS. Direct backend ports should be private or firewalled.

Health/readiness checks:

- API readiness: DB reachable, queue reachable, quota policy loaded, task-state schema compatible.
- Worker readiness: DB reachable, broker reachable, can lease heartbeat, policy loaded.
- Degraded readiness can remain live but not accept expensive new work when budgets/provider circuits are closed.

Queue/SSE smoke test:

- Submit one analysis task.
- Confirm durable task row is created.
- Confirm worker leases and completes it.
- Confirm polling status works from any API instance.
- Confirm SSE receives progress or can replay from last sequence.
- Confirm owner B cannot read owner A task/status/progress/export.

## 13. Implementation phases

| Phase | Scope |
| --- | --- |
| WS2-R0 | Design only. This document. No runtime behavior changed. |
| WS2-R1 | Durable task schema plus owner-scoped task status design/implementation. |
| WS2-R2 | Queue worker prototype with one task type, safe leases, retries, and shutdown behavior. |
| WS2-R3 | SSE/polling external state with progress rows and replay/fallback semantics. |
| WS2-R4 | LLM quota enforcement: budget schema, route weights, reservations, token caps, and blocked/degraded states. |
| WS2-R5 | Provider quota/circuit breaker enforcement across data-provider and LLM providers. |
| WS2-R6 | Observability dashboard for queue, route latency, quota, cache, and provider/LLM health. |
| WS2-R7 | Multi-instance deployment test with multiple API instances, workers, queue, PostgreSQL, and proxy routing. |

## 14. Test plan

- Unit tests: task state transitions, dedupe key construction, idempotency, owner filtering, quota policy decisions, retry/timeout classification, circuit breaker state.
- Integration tests: API submit/status/polling against test DB and fake queue; worker lease/complete/fail/retry/cancel with synthetic handlers.
- No live LLM/provider tests: use fake LLM/provider adapters and fixture usage numbers.
- Owner-scope tests: owner A cannot list, poll, stream, cancel, export, or coalesce into owner B tasks unless admin capability allows it.
- Queue failure tests: worker crash, lease expiry, broker unavailable, DB unavailable, duplicate enqueue, retry exhaustion, poison task.
- Budget exceeded tests: per-user daily/monthly, global kill switch, provider bucket exhausted, route weight rejection, degraded cache-only state.
- SSE tests: initial replay, owner filtering, heartbeat, disconnect/reconnect from last sequence, polling fallback.
- Load/smoke tests: bounded local synthetic queue depth, many duplicate submits, many polling clients, no external calls, no browser/server requirement for design-only phase.

## 15. Parallelization plan

Can run in parallel:

- Quota design vs queue design, if schema files and policy docs are disjoint.
- Frontend performance pass vs backend queue work, after backend API contracts are stable or mocked.
- DB index audit vs quota policy design.
- Provider circuit breaker audit vs task schema design, as long as no shared runtime files are edited.

Must serialize:

- Task schema before worker implementation.
- Quota schema before quota enforcement.
- Durable progress/SSE state before multi-instance API deployment.
- Provider/LLM circuit breaker policy before changing fallback behavior.
- Cache key/freshness approval before report/scanner/options reuse prototypes.

## 16. Recommended next Codex prompts

1. WS2-R1 durable task state design/implementation:
   "In `/Users/yehengli/daily_stock_analysis` on `main`, implement only WS2-R1 durable task state for analysis tasks. Add the minimal task/progress schema and owner-scoped status reads. Do not add workers, Redis, Celery, frontend changes, live providers, or LLM calls. Preserve existing process-local queue behavior until explicitly cut over."

2. LLM/API quota schema design/implementation:
   "In `/Users/yehengli/daily_stock_analysis` on `main`, implement only the quota schema and policy service for LLM/API budgets. Add synthetic tests for per-user budget, route weights, token caps, and global kill switch. Do not enforce on live routes yet and do not call LLMs/providers."

3. DB production index/retention audit:
   "In `/Users/yehengli/daily_stock_analysis` on `main`, perform a docs-only DB production readiness audit for task/progress/log/LLM/scanner/backtest/portfolio tables. Recommend indexes, retention, backup, and restore checks. Do not add migrations or runtime code."

4. Frontend performance bundle/code-splitting audit:
   "In `/Users/yehengli/daily_stock_analysis` on `main`, perform a report-only frontend performance audit for route-level code splitting, chart lazy loading, table virtualization, static asset caching, and client request coalescing. Do not modify frontend code."

5. Queue/SSE multi-instance smoke design:
   "In `/Users/yehengli/daily_stock_analysis` on `main`, create a docs-only smoke-test design for multi-instance API + worker + queue + PostgreSQL task state. Cover task submit/status/SSE replay/polling fallback/owner isolation. Do not run servers or live providers."
