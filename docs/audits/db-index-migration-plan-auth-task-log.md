# DB Index Migration Plan: Auth, Tasks, Logs, and LLM Observability

Date: 2026-05-06
Mode: docs-only planning artifact. No runtime code, schema, migrations, tests, live DB contents, or secrets were changed or inspected.

## 1. Executive summary

This is the first production-readiness index batch because it covers the highest-frequency, highest-read-risk paths that now exist in the runtime contract:

- auth/users/sessions
- durable task state and progress replay
- execution/admin logs
- LLM usage/cost observability

These domains are the first to feel public multi-user growth, and they already have stable owner/time/status semantics in code or baseline DDL. The goal of this batch is to define the additive index contract before any migration work starts.

Included:

- lookup and revocation paths for authenticated users and sessions
- guest-session TTL lookup where guest persistence is enabled
- login-throttle bucket cleanup lookups
- durable task state, idempotency, dedupe, lease, and stale cleanup lookups
- durable progress replay and cleanup lookups
- execution/admin log session and event filtering
- observational LLM usage rows and future cost-ledger readiness

Excluded:

- retention implementation
- quota enforcement
- runtime behavior changes
- schema rewrites
- existing provider/cache semantics
- portfolio accounting changes
- scanner/backtest calculation changes
- Options Lab changes
- RBAC route changes

No runtime/schema changes are made in this planning pass.

## Batch A implementation note

Implemented on 2026-05-06 as an additive index-only pass for auth/users/sessions and durable task/progress storage.

- SQLite/local initialization and compatibility migrations now add or confirm the portable Batch A indexes for `app_user_sessions`, `auth_rate_limit_buckets`, `durable_task_states`, and `durable_task_progress_events`.
- Phase A PostgreSQL baseline metadata and SQL now include `app_users(role, is_active)`, `app_user_sessions(user_id, revoked_at, expires_at)`, `app_user_sessions(last_seen_at)`, and guest-session lifecycle indexes. The guest table currently uses `started_at` as its creation lifecycle timestamp, so Batch A indexes that field instead of adding a new `created_at` column.
- PostgreSQL partial indexes and concurrent/online deployment remain future production rollout optimizations; this batch keeps the local/schema path portable and does not force PostgreSQL-only partial index syntax into SQLite initialization.
- Runtime auth/session semantics, durable task status/progress semantics, quota behavior, provider/cache behavior, RBAC routes, scanner/backtest/portfolio calculations, LLM/provider routing, notification routing, DuckDB, and broker/order paths were not changed.

## 2. Proposed index batch A: auth/users/sessions

| Table | Columns | Query / use case | PostgreSQL notes | SQLite / local compatibility | Risk |
| --- | --- | --- | --- | --- | --- |
| `app_users` | `role, is_active` | Admin/user directory filters and active-user listing | Keep as a small btree; if the table grows, it remains cheap and predictable. If a partial admin-only filter becomes dominant later, consider a partial index in a future pass. | Safe on SQLite and already aligned with the current ORM shape. | Low. Only supports filtering; does not change identity semantics. |
| `app_users` | `username` unique lookup | Login and account resolution | Already present as the username uniqueness contract; keep it authoritative across stores. | Safe. No behavior change. | Low. Duplicating the unique constraint would be noise, not value. |
| `app_user_sessions` | `user_id, expires_at` | Active session list, revocation, and “all sessions for user” reads | Keep as the primary active-session access path. `expires_at` should stay in the key so cleanup can order by TTL. | Safe and already mirrored in baseline DDL. | Low. This is the core session index contract. |
| `app_user_sessions` | `user_id, revoked_at, expires_at` or partial `revoked_at is null` | Active-only session lookup and revocation UX | Prefer a partial active-session index in PostgreSQL if active rows dominate and revoked rows are large; otherwise keep the composite btree. | Partial indexes are not portable to every local setup, so keep the composite fallback path for SQLite/dev. | Medium. Must not break session revocation reads. |
| `app_user_sessions` | `last_seen_at` | Stale-session cleanup / idle timeout support | Useful for operational cleanup jobs and admin audit support. | Safe. Small btree, portable. | Low. Cleanup-only support. |
| `guest_sessions` | `expires_at` | Guest TTL cleanup and lookup by lifecycle | If guest persistence is enabled in production, this should be the primary cleanup index. | Safe where guest sessions are present; no effect where guest persistence stays off. | Low to medium, depending on whether guest sessions are truly retained. |
| `guest_sessions` | `created_at` | Guest retention reporting and oldest-row checks | Useful for TTL policy previews and growth summaries. | Portable. | Low. Only supports cleanup observability. |
| `auth_rate_limit_buckets` | `bucket_type, expires_at` | Login throttle bucket cleanup and expiry scans | Keep the expiration scan cheap; this is a bounded control-plane table. | Portable. | Low. No auth-policy change. |

## 3. Proposed index batch B: durable tasks/progress

| Table | Columns | Query / use case | Rollout note |
| --- | --- | --- | --- |
| `durable_task_states` | `task_id` unique | Direct task lookup and status reads | Confirmation only if any environment lags the current unique contract. Do not change task ID semantics. |
| `durable_task_states` | `owner_user_id, created_at` | Owner task history and pagination | First owner-scoped list path. Add only if not already present in the target store. |
| `durable_task_states` | `owner_user_id, status, created_at` | Active/running/failed/completed filters | Primary dashboard and support filter path. |
| `durable_task_states` | `status, updated_at` | Stalled/expired cleanup and worker-leasing sweeps | Use for cleanup and lease recovery only; keep additive. |
| `durable_task_states` | `status, lease_expires_at` | Lease expiry lookup and crash recovery | Needed when lease-backed workers become the dominant read pattern. |
| `durable_task_states` | `idempotency_key_hash` | Retry-safe submission lookup | Add as a lookup key only; do not conflate with dedupe. |
| `durable_task_states` | `dedupe_key_hash` | In-flight coalescing / duplicate suppression | Keep the dedupe contract stable across owner-scoped task submission paths. |
| `durable_task_progress_events` | `task_id, sequence` unique | Replay ordering and append safety | This is the core progress-event contract; preserve it. |
| `durable_task_progress_events` | `task_id, created_at` | Replay by time and cleanup by task age | Existing model already points here; keep it additive. |
| `durable_task_progress_events` | `owner_user_id, created_at` | Owner timeline replay and cleanup | Important for public support and tenant-scoped debugging. |
| `durable_task_progress_events` | `task_id, owner_user_id, sequence` if needed for mixed reads | Combined replay/ownership checks | Only add if the target query plan shows a real need; avoid redundant composite bloat. |

Observed runtime shape already includes `durable_task_states.task_id`, `owner_user_id + created_at`, `owner_user_id + status + created_at`, `status + updated_at`, `status + lease_expires_at`, and progress-event `task_id + sequence`, `task_id + created_at`, `owner_user_id + created_at`. The migration pass should therefore mostly be a confirmation-and-gap pass, not a redesign.

## 4. Proposed index batch C: execution/admin logs

| Table | Columns | Query / use case | PostgreSQL note |
| --- | --- | --- | --- |
| `execution_log_sessions` | `started_at` | Default time-window browsing | Base timeline filter. |
| `execution_log_sessions` | `overall_status, started_at` | Status-filtered session lists | Good for admin triage and history views. |
| `execution_log_sessions` | `task_id, started_at` | Async task drilldown | Useful when users search by task. |
| `execution_log_sessions` | `code, started_at` | Symbol drilldown | Useful for stock-focused analysis sessions. |
| `execution_log_sessions` | `query_id, started_at` | Query-linked support lookup | Useful for report or chat-linked execution sessions. |
| `execution_log_events` | `session_id, event_at` | Event timeline for one session | Primary event replay path. |
| `execution_log_events` | `phase, status, event_at` | Phase/status triage | Better than scanning JSON/text summaries. |
| `execution_log_events` | `target, event_at` | Provider/model/channel drilldowns | Keep this bounded and safe. |
| `admin_logs` | `created_at` / `occurred_at` | Default admin log time window | Use the canonical timestamp field in the target store. |
| `admin_logs` | `level/severity, created_at` | Severity filters | Useful for storage summary and alert pages. |
| `admin_logs` | `category, created_at` | Category filtering | Supports admin log drilldown. |
| `admin_logs` | `event_type, created_at` | Event family filtering | Important for audit and notification routing. |
| `admin_logs` | `actor_user_id, created_at` | Actor-scoped audit search | Tenant/admin accountability path. |
| `admin_logs` | `owner_user_id, created_at` if present in future schema | Owner-scoped audit search | Reserve this for a future owned-audit variant. |
| `admin_logs` | `session_id, created_at` if present in future schema | Session-scoped audit search | Useful if sessionized admin audit gets promoted later. |

Warning: JSON/GIN/trigram indexes should wait until query-plan evidence shows text or JSON predicates dominate. Do not add broad JSON indexes speculatively.

## 5. Proposed index batch D: LLM usage / cost observability

Current observed `llm_usage` fields:

- `call_type`
- `model`
- `stock_code`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `called_at`

Future observability dimensions to plan for:

- `owner_user_id`
- `route_family`
- `model`
- `called_at`

Recommended future shape:

- `owner_user_id, called_at`
- `owner_user_id, route_family, called_at`
- `model, called_at`
- `call_type, called_at`
- `owner_user_id, model, called_at`

Important distinction:

- observability rows answer “what happened and how much did it cost?”
- quota ledger rows answer “was the request allowed, reserved, or blocked?”

Indexes that should wait for quota schema:

- owner quota window lookups
- reservation state lookups
- enforcement-path hot indexes

Do not merge observability indexing into quota enforcement before the quota schema exists.

## 6. Rollout strategy

1. Additive indexes only.
2. Use PostgreSQL concurrent/index-online guidance where applicable for large tables.
3. Keep SQLite/local/dev compatibility by preserving composite fallback paths and avoiding PostgreSQL-only assumptions in runtime reads.
4. Deploy order:
   1. auth/users/sessions
   2. durable tasks/progress
   3. execution/admin logs
   4. LLM usage observability
5. Rollback caveats:
   - drop-index rollback is safer than data rollback
   - never treat cleanup as rollback
   - keep any future backfill resumable
6. Query-plan verification checklist:
   - confirm the target filter matches the proposed key order
   - confirm the planner uses the new index for the dominant route
   - confirm no broad JSON scan is being used as a substitute
7. No broad JSON indexes until proven by query-plan evidence.

## 7. Test / verification plan for future implementation

- migration smoke tests against a clean database
- query-plan smoke checks for each index family
- route-specific latency checks for:
  - `/api/v1/auth/*`
  - durable task status/progress polling
  - `/api/v1/admin/logs`
  - `/api/v1/usage/*` or admin cost observability surfaces
- admin page filter checks for user, log, and task drilldowns
- cleanup dry-run checks for stale sessions, task progress, and logs
- backup/restore smoke relation:
  - restore should preserve index availability
  - restore should support the same lookup patterns without query regressions

## 8. Risks and non-goals

Risks:

- over-indexing small tables
- choosing partial indexes that do not port cleanly to local/dev
- adding broad text/JSON indexes before evidence
- drifting from the additive-only contract

Non-goals:

- no runtime behavior change
- no retention implementation
- no quota enforcement
- no provider/cache behavior change
- no portfolio accounting change
- no scanner/backtest calculation change
- no Options Lab change
- no RBAC route change

## 9. Recommended next Codex prompt

Implement the first production-readiness index migration batch as additive, docs-backed migrations only. Start with auth/users/sessions and durable tasks/progress, preserve SQLite/local compatibility, avoid runtime behavior changes, and add only the smallest verified indexes needed by the documented query paths. Do not touch quota enforcement, provider/cache logic, portfolio accounting, scanner/backtest calculations, or RBAC routes. Add migration smoke coverage and query-plan checks for the new indexes, then update the changelog with the implemented batch.
