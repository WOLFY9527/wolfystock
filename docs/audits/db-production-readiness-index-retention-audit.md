# DB Production Readiness: Index, Retention, Backup, and Growth Audit

Date: 2026-05-06
Mode: docs-only audit. No runtime code, schema, migrations, tests, live providers, servers, or database contents were changed or inspected.

## 1. Executive summary

Current readiness level: **not ready for broad public multi-user scale**.

WolfyStock now has important multi-user foundations: persisted users/sessions, RBAC compatibility metadata, owner-scoped analysis history, WS2-R1 `durable_task_states`, persisted execution logs, scanner/backtest tables, portfolio tables, read-only cost observability, and PostgreSQL coexistence/shadow stores for several phases. Those foundations are enough for internal or controlled low-user deployments, but they are not yet a complete production database operating model.

Public multi-user blockers:

- Index coverage is uneven across high-growth owner/time/status query paths. Several tables have good first-pass indexes, but production needs an explicit index contract per route and per admin drilldown before user count and history volume grow.
- Retention is implemented for admin logs, but comparable TTL tiers are not yet defined for task progress, terminal task state, LLM usage, scanner/backtest artifacts, provider counters, guest/cache metadata, or Options Lab future cache rows.
- Backup/restore readiness is not yet documented as an operational requirement with encrypted backups, point-in-time recovery, restore drills, and smoke checks.
- Cost observability is explicitly observational, not quota enforcement; `llm_usage` and process counters are not enough to cap tenant growth or noisy-neighbor load.
- SQLite remains suitable for local/dev and compatibility paths, but public production should treat PostgreSQL as the durable multi-user baseline before scaling API instances, workers, or long-running jobs.

Recommended sequence:

1. Freeze the production DB contract by table/domain: owner field, lifecycle timestamps, status fields, idempotency/dedupe fields, retention tier, and required query indexes.
2. Add index migrations in small domain passes, starting with auth/session, durable tasks/progress, execution/admin logs, LLM usage, scanner/backtest, and portfolio ledger/history.
3. Add retention dry-run/reporting for every high-growth domain before enabling actual cleanup.
4. Establish encrypted PostgreSQL backups, PITR, restore drills, and post-restore smoke checks before public onboarding.
5. Add DB observability dashboards and alert thresholds, then implement quota enforcement separately from cost observability.

## 2. Table/domain inventory

| Domain | Current table/code names observed | Current readiness | Production gap |
| --- | --- | --- | --- |
| Auth/users/sessions | SQLite `app_users`, `app_user_sessions`, `auth_rate_limit_buckets`; PostgreSQL Phase A `app_users`, `app_user_sessions`, `guest_sessions`, `user_preferences`, `notification_targets` | Basic persisted identity/session model exists with user/expiry indexes. | Need production session active lookup index contract, session cleanup TTL, guest-session TTL, and restore smoke for login/session revocation. |
| Admin RBAC | SQLite `admin_roles`, `admin_role_capabilities`, `admin_user_roles`; capability design doc | Compatibility metadata exists and route migration is partial. | Need explicit audit/security event retention, role-assignment history if mutable roles are added, and route-denial audit index design before broader RBAC runtime expansion. |
| Durable task state | `durable_task_states` | WS2-R1 table exists with unique `task_id`, owner/time/status indexes, idempotency/dedupe hash columns. | Need progress/event table design, retention by terminal status, worker lease indexes, and cleanup previews before WS2-R2/R3 scale-up. |
| Future task progress/events | Proposed in WS2 design; not observed as implemented table | Not implemented. | Need `task_id + sequence` uniqueness, `owner_user_id + created_at`, replay retention, and SSE/polling query indexes before externalized progress. |
| Analysis history/results | SQLite `analysis_history`; PostgreSQL Phase B `analysis_sessions`, `analysis_records`; chat sessions/messages also exist | Owner/query/time indexes exist for legacy analysis history; Phase B shadows owner sessions/records. | Need production retention/archive policy for raw report payloads, per-owner history pagination indexes, and storage growth reporting. |
| Execution logs/admin logs | SQLite `execution_log_sessions`, `execution_log_events`; PostgreSQL Phase G `execution_sessions`, `execution_events`, `admin_logs`, `system_actions`; admin log cleanup service | Admin-log retention/capacity cleanup exists, including dry-run behavior and storage summary. | Need broader execution-log index coverage by time/status/category/session/user and explicit audit-log fail-closed policy for security-sensitive events. |
| LLM usage/cost observability | `llm_usage`, process-local counters for providers/MarketCache/scanner AI; admin cost summary route | Read-only accounting/observability exists. | `llm_usage` lacks owner/route/time/model index contract and is not quota enforcement or billing truth. Need retention and quota ledger design. |
| Provider/MarketCache persisted state | `market_overview_snapshots`; PostgreSQL Phase C `symbol_master`, `market_data_manifests`, `market_dataset_versions`, `market_data_usage_refs`; process-local MarketCache counters | Some persisted market metadata/snapshots exist; MarketCache itself is process-local. | Need provider counter retention, shared-cache design if introduced, cache growth controls, and no change to current MarketCache TTL/SWR/fallback semantics. |
| Scanner runs/results | SQLite `market_scanner_runs`, `market_scanner_candidates`, `user_watchlist_items`; PostgreSQL Phase D `scanner_runs`, `scanner_candidates`, `watchlists`, `watchlist_items` | Owner/time, market/time, profile/time, run/rank indexes exist in SQLite; Phase D shadow tables exist. | Need owner/status/time index review, candidate artifact retention, watchlist long-term retention, and artifact size dashboards. |
| Backtest runs/results | SQLite `backtest_results`, `backtest_summaries`, `backtest_runs`, `rule_backtest_runs`, `rule_backtest_trades`; PostgreSQL Phase E `backtest_runs`, `backtest_artifacts` | Several owner/time and run/trade indexes exist; artifacts are a known growth surface. | Need owner/status/time indexes for async runs, artifact retention tiers, export artifact cleanup, and migration rollback caveats for large backtest records. |
| Portfolio accounts/holdings/activity | SQLite `portfolio_accounts`, broker sync tables, trades, cash ledger, corporate actions, positions, lots, daily snapshots, FX rates; PostgreSQL Phase F portfolio tables | Many owner/account/time and account/date indexes exist; portfolio is user-owned and business-critical. | Retention should preserve financial/accounting records by default. Need indexes for owner/account/symbol/time drilldowns and backup/restore smoke checks for replay correctness. |
| Options Lab | Fixture-backed endpoints/services; no current persistent options table observed | Current state is read-only fixture/no-order. | If live option chains/caches are added later, define short TTL chain cache, fixture/cache separation, provider entitlement metadata, and no-order/no-broker retention policy. |
| Notification/admin operations | `notification_channels`, `notification_events`; Phase A notification targets; Phase G system actions | Operational tables exist with event type/severity/time and dedupe/time indexes. | Need retention for delivered/acked events, audit preservation for admin channel changes, and restore smoke for notification target safety. |

## 3. Index recommendations

These recommendations are design targets for later migrations. They are not schema changes in this audit.

### Auth/users/sessions

- Keep primary lookup by `app_users.id` and unique username.
- Add or confirm active user/session lookup coverage:
  - `app_users(role, is_active)` for admin/user directory filters.
  - `app_user_sessions(user_id, expires_at)` for active session lists and revocation.
  - `app_user_sessions(user_id, revoked_at, expires_at)` or a partial PostgreSQL index on active sessions where `revoked_at is null`.
  - `app_user_sessions(last_seen_at)` for stale-session cleanup.
  - `guest_sessions(expires_at)` and `guest_sessions(created_at)` if guest sessions are retained in PostgreSQL production.

### Admin RBAC and security audit

- Existing `admin_role_capabilities(role_key, capability)` and `admin_user_roles(user_id, role_key)` are good for read expansion.
- If role mutation is added, add append-only assignment history with:
  - `target_user_id + created_at`
  - `actor_user_id + created_at`
  - `role_key + created_at`
  - `event_type + created_at`
- Admin audit/security event lookups should support:
  - `actor_user_id + created_at`
  - `target_user_id + created_at`
  - `capability + outcome + created_at`
  - `session_id + created_at`

### Durable tasks and future progress

- Existing `durable_task_states.task_id` uniqueness is correct.
- Existing `owner_user_id + created_at`, `owner_user_id + status + created_at`, and `status + updated_at` indexes are the right first production shape.
- Before worker scale-out, add or confirm:
  - `dedupe_key_hash + status + created_at` for in-flight coalescing.
  - `idempotency_key_hash + owner_user_id` uniqueness or lookup for retry-safe submissions.
  - `status + updated_at` for stalled/expired task cleanup.
  - `status + lease_expires_at` if lease fields are added.
  - progress table `task_id + sequence` unique.
  - progress table `owner_user_id + created_at` and `task_id + created_at`.

### Analysis history/results

- Existing `analysis_history(owner_id, created_at)` and `analysis_history(owner_id, query_id)` cover user history and task fallback reads.
- Add or confirm:
  - `owner_id + code + created_at` for per-symbol history.
  - `owner_id + report_type + created_at` for report-type filters.
  - `is_test + created_at` for cleanup/test data separation.
  - PostgreSQL Phase B `analysis_sessions(owner_user_id, created_at)` and `analysis_records(analysis_session_id, sequence_no)` for owner timeline and stable record ordering.

### Execution logs/admin logs

- Existing SQLite indexes cover session/time and phase/status, but admin pages filter by task, stock, status, category, provider, model, channel, and date range.
- Add or confirm:
  - sessions: `started_at`, `overall_status + started_at`, `task_id + started_at`, `code + started_at`, `query_id + started_at`.
  - events: `session_id + event_at`, `phase + status + event_at`, `target + event_at` where provider/model/channel filters depend on target search.
  - Phase G/admin logs: `created_at`, `level/severity + created_at`, `category/event_type + created_at`, `actor_user_id + created_at`, `owner_user_id + created_at`, `session_id + created_at`.
- For PostgreSQL, consider partial or GIN/trigram indexes only after query plans prove text/JSON filters dominate; do not add broad JSON indexes speculatively.

### LLM usage/cost

- Current `llm_usage` has `called_at` and `call_type` index flags but lacks owner and route dimensions.
- Future production ledger should include:
  - `owner_user_id + called_at`
  - `owner_user_id + route_family + called_at`
  - `model + called_at`
  - `call_type + called_at`
  - `owner_user_id + model + called_at`
  - reservation/quota table `owner_user_id + window_start + quota_type`
- Keep observational counters separate from enforceable quota reservations.

### Provider/MarketCache/market metadata

- Preserve current provider ordering, fallback, TTL, SWR, cold-start, and MarketCache behavior.
- For persisted metadata/counters:
  - snapshots: `key` primary and `updated_at`.
  - provider usage counters: `provider + route_family + created_at`.
  - market data usage refs: `entity_type + entity_id`, `manifest/version + created_at`.
  - shared cache if added: `cache_key_hash` unique, `fresh_until`, `stale_until`, `updated_at`, and `provider + status + updated_at`.

### Scanner

- Existing scanner run indexes cover scope/time, owner/time, market/time, profile/time; candidates cover run/rank and symbol/created.
- Add or confirm:
  - `owner_id + status + run_at` for user run history.
  - `owner_id + market + profile + run_at` for route filters.
  - candidates `run_id + score` only if score-sorted candidate pages become common.
  - watchlist `owner_id + updated_at`, `owner_id + symbol + market`, `owner_id + score_status + updated_at`.

### Backtest

- Existing indexes cover owner/time for runs and results plus run/trade lookups.
- Add or confirm:
  - `owner_id + status + run_at` for async run lists.
  - `owner_id + code + run_at` for symbol-scoped runs.
  - artifacts `backtest_run_id + artifact_kind` unique and `created_at` for cleanup.
  - trades `run_id + trade_index` and `run_id + entry_date` for exports.

### Portfolio

- Portfolio records should favor correctness and replayability over aggressive deletion.
- Add or confirm:
  - accounts `owner_id + is_active`.
  - broker connections `owner_id + status`, `owner_id + broker_type + broker_account_ref`.
  - trades `account_id + trade_date`, `account_id + is_active + trade_date`, `account_id + symbol + trade_date`.
  - cash ledger `account_id + event_date`.
  - corporate actions `account_id + effective_date`, `account_id + symbol + effective_date`.
  - positions/lots `account_id + symbol`, plus market/currency where query volume requires it.
  - daily snapshots `account_id + snapshot_date + cost_method`.
  - FX rates `from_currency + to_currency + rate_date`.
  - PostgreSQL Phase F owner-aware variants: `owner_user_id + portfolio_account_id + created_at/updated_at` for admin-safe projections.

### Options Lab future persistence

- Current fixture-backed/no-order state does not need production DB indexes.
- If a live provider/cache is added later:
  - option chain cache `symbol + expiration + chain_as_of`.
  - contract cache `contract_symbol + chain_as_of`.
  - scenario cache `owner_user_id + assumptions_hash + created_at` only if user-specific scenario persistence is approved.
  - short TTL indexes on `fresh_until` and `stale_until`.

## 4. Retention recommendations

| Domain | Proposed default tier | Notes |
| --- | --- | --- |
| Task progress rows | 7-14 days for terminal tasks; 30 days for failed/debug samples | Keep enough for support replay, then compact to terminal summary. |
| Completed task state | 30-90 days | Keep `task_id`, owner, status, result pointer, safe timing, and summary; delete bulky progress. |
| Failed/canceled task state | 90-180 days | Longer retention for reliability analysis, but messages must remain sanitized. |
| Execution logs | Existing admin log default is 90 days with minimum retention and cleanup controls | Extend dry-run/capacity summary to execution logs if Phase G becomes the production source. |
| Admin audit/security logs | 365 days minimum; consider 2-7 years depending on compliance posture | Security, admin writes, denials, role changes, session revocations, and backup/restore evidence should outlive operational logs. |
| LLM usage/cost counters | Raw call rows 90-180 days; monthly aggregates 2+ years | Raw rows support incident review; aggregates support cost trend/budget planning. |
| Provider counters | Raw counters 30-90 days; aggregates 1 year | Store bounded labels only; no raw URLs, params, payloads, symbols beyond approved normalized labels, or credentials. |
| Scanner runs/candidates | User-visible runs 180-365 days; bulky diagnostics 30-90 days | Keep watchlist entries until user deletion; compact old candidate diagnostics. |
| Backtest artifacts | Run summaries 1+ year; export artifacts/traces 30-180 days by size | Preserve reproducibility metadata longer than large generated artifacts. |
| Portfolio records | Indefinite by default for user-owned accounting records | Trades, cash ledger, corporate actions, positions, snapshots, and FX records should be exportable and restorable, not TTL-deleted by default. |
| Broker sync payload/cache metadata | Current snapshot until superseded; raw-ish provider payloads should be avoided or short-lived | Prefer normalized fields and masked refs. |
| Guest preview/cache metadata | 24 hours to 7 days | Scope by guest session, avoid mixing with authenticated user state, and keep force-refresh/rate-limit policy separate. |
| Options Lab fixture/cache data | Fixture data can be versioned with code; future live chain cache should be minutes/hours, not days | If a provider is added, retain chain freshness and entitlement metadata but avoid raw provider payload storage. |
| Notification events | Delivered/acked operational events 90-180 days; security/admin notification events 365+ days | Notification channel config history should be audit-preserved when mutable. |

Retention must be implemented as preview-first cleanup:

- Every cleanup job should have a dry-run mode with matched row counts, estimated bytes where available, oldest/newest rows, and protected-row reasons.
- Cleanup must be owner/domain-aware where user data deletion is involved.
- Cleanup must not delete financial source-of-truth records unless a separate user-data deletion/export policy explicitly authorizes it.

## 5. Backup/restore and migration readiness

Production expectations:

- PostgreSQL should be the public multi-user durable store. SQLite remains appropriate for local/dev, compatibility, and controlled single-user paths.
- Enable encrypted backups at rest and in transit. Backup storage must be separated from the primary DB host/account.
- Define a point-in-time recovery target before launch:
  - RPO target: 15 minutes or better for public production.
  - RTO target: 60 minutes or better for first public tier, then tighten after drills.
- Run scheduled restore drills into an isolated environment. Do not restore over production as a drill.
- After restore, run smoke checks against metadata/counts and synthetic fixtures, not real secret values:
  - app can connect to restored DB;
  - admin bootstrap/auth status works with safe test credentials;
  - user/session revocation logic sees restored rows;
  - analysis history owner filters return only expected synthetic owner rows;
  - durable task status lookup works for synthetic task IDs;
  - admin log storage summary works;
  - portfolio replay on synthetic account matches expected totals;
  - scanner/backtest synthetic runs and artifacts are readable;
  - notification target/channel records remain masked.
- Keep migration rollout backward-compatible:
  - additive columns/indexes first;
  - backfill in bounded batches;
  - deploy code that can read old and new shapes;
  - switch writers after read compatibility exists;
  - remove old compatibility only after evidence.
- Migration rollback caveats:
  - dropping columns/tables is rarely safely reversible after writes begin;
  - index creation should use PostgreSQL concurrent/index-online patterns where possible;
  - backfills need resumable checkpoints;
  - retention cleanup is not a rollback mechanism.
- Public exposure reminder: production docs already recommend HTTPS reverse proxy and not exposing backend `:8000` directly to the internet. DB readiness does not relax that requirement.

## 6. Observability recommendations

Add DB observability before scaling public users:

- DB pool metrics:
  - pool size, checked-out connections, wait time, timeout count, overflow, transaction duration.
- Slow query logging:
  - enable threshold-based slow query logs in PostgreSQL;
  - capture route/domain label, sanitized actor/owner hash where approved, duration bucket, row count bucket, and statement fingerprint.
- Admin-page query timing:
  - `/admin/logs`, `/admin/users`, `/admin/cost-observability`, `/admin/market-providers`, `/admin/notifications`, portfolio admin projections, scanner/backtest history pages.
- Storage growth dashboards:
  - table size, index size, dead tuples, autovacuum lag, row count estimates, daily growth rate.
  - PostgreSQL `pg_total_relation_size` should be used only in production-safe admin storage summaries, never by connecting in ad hoc audits.
- Oldest retained row per domain:
  - durable tasks, progress, execution logs, admin audit/security logs, LLM usage, provider counters, scanner candidates, backtest artifacts, guest/cache metadata.
- Cleanup dry-run previews:
  - matched rows, estimated bytes, protected rows, oldest/newest candidate, retention policy version, and whether actual delete is allowed.
- Alert thresholds:
  - DB connection pool wait p95 > 100ms for 10 minutes.
  - Slow query p95 > 500ms on admin/user history routes.
  - Table growth > 20% week over week for logs/tasks/artifacts.
  - Storage > 70% soft limit, > 85% hard warning, > 95% critical.
  - Oldest uncleaned transient row exceeds retention by 2x.
  - Backup missing, failed, or restore drill overdue.
  - Admin audit write failure on sensitive action.

## 7. Risk matrix

| Risk | Severity | Why it matters | Mitigation |
| --- | --- | --- | --- |
| Missing owner/time indexes | High | Multi-user pages and owner-scoped APIs degrade as history grows; risk of slow admin/user queries. | Add per-domain `owner_id/owner_user_id + created_at/updated_at` indexes and verify query plans. |
| Missing owner/status/time indexes | High | Task/run pages and support screens need fast active/failed/completed filters. | Add `owner + status + time` indexes for tasks, scanner, backtest, and queue-like tables. |
| Unbounded execution logs | High | Logs can dominate storage and slow admin pages. | Keep existing retention/capacity controls, extend storage summaries to all execution/admin log sources, and alert on oldest retained rows. |
| Task/progress growth | High | WS2 external progress can grow faster than terminal task rows. | Store bounded progress, compact terminal tasks, TTL progress rows, and index by `task_id + sequence`. |
| LLM usage growth | Medium/High | Cost rows grow with every model attempt and fallback. | Add owner/route/model/time schema, raw-row retention, monthly aggregates, and separate quota ledger. |
| Portfolio history growth | High | Financial records must be durable and replayable; bad cleanup can corrupt trust. | Do not TTL source-of-truth portfolio records by default; add export/archive and restore smoke checks. |
| Scanner/backtest artifact growth | Medium/High | Diagnostics, traces, exports, and candidate payloads can become large. | Retain summaries longer than bulky artifacts; add artifact TTL and dry-run cleanup. |
| Migration rollback risk | High | Destructive schema/data changes cannot be cleanly reverted after public writes. | Use additive migrations, dual-read compatibility, resumable backfills, and rollback plans that preserve data. |
| Backup/restore not tested | Critical | Backups that have never been restored are not production evidence. | Schedule restore drills, document RPO/RTO, run smoke checks after restore, and alert on failures. |
| Audit fail-open risk | High | Admin/security events lost during failures weaken incident response and compliance. | Sensitive admin writes should fail closed or emit durable compensating events; monitor audit write failures. |
| Cost observability mistaken for quota enforcement | High | Operators may assume dashboards cap spend when they only observe it. | Keep docs/API labels explicit; implement quota reservations and enforcement as a separate task. |
| Direct public backend exposure | Medium/High | DB readiness does not protect unsafe network exposure. | Keep reverse-proxy/HTTPS guidance and avoid direct public `:8000` exposure. |

## 8. Next implementation prompts

1. **DB index migration plan for auth/session/task/log domains**
   - Scope: docs + migrations only after review.
   - Add production-safe indexes for active sessions, durable tasks, progress events if implemented, execution logs, and admin logs.
   - Do not change runtime auth/RBAC behavior.

2. **Durable task progress/event schema design**
   - Scope: design first, then migration in a later pass.
   - Include `task_id`, `owner_user_id`, `sequence`, event type/stage, safe message, created time, and replay retention.
   - Do not change WS2 runtime queue/SSE behavior in the design pass.

3. **Retention dry-run framework for non-log domains**
   - Scope: tasks, LLM usage, provider counters, scanner/backtest artifacts, guest/cache metadata.
   - Add dry-run summaries before actual delete support.
   - Do not delete portfolio source-of-truth records.

4. **PostgreSQL backup/restore runbook**
   - Scope: docs and scripts that use synthetic fixtures only.
   - Define encrypted backup, PITR, restore drill cadence, RPO/RTO, and post-restore smoke checklist.
   - Do not print secrets or real DB contents.

5. **DB observability dashboard contract**
   - Scope: metrics design for pool, slow query, storage growth, cleanup lag, and backup status.
   - Use bounded labels and safe fingerprints only.
   - Do not add live provider calls or alter provider/cache behavior.

6. **LLM quota ledger design**
   - Scope: design quota reservations and enforcement separately from existing cost observability.
   - Include owner/route/model/time dimensions and budget windows.
   - Do not change prompts, model order, routing, retry, fallback, or scanner/backtest/portfolio behavior.

7. **Portfolio restore/replay smoke design**
   - Scope: synthetic account fixtures and restore validation checklist.
   - Verify trades/cash/corporate actions/snapshots/FX replay after restore.
   - Do not change accounting, cash, holdings, P&L, sync, import, replay, or FX logic.

## 9. Scope confirmations

This audit intentionally does not change:

- scanner scoring, ranking, selection, thresholds, or actionability;
- backtest calculations or artifacts;
- portfolio accounting, cash, holdings, P&L, sync, import, replay, or FX;
- market provider ordering/fallback or MarketCache TTL/SWR/cold-start behavior;
- AI/LLM prompts, routing, model order, retry, fallback, or decision logic;
- notification routing;
- DuckDB production runtime;
- broker execution or order placement;
- Options Lab behavior;
- RBAC runtime behavior;
- WS2 runtime behavior.
