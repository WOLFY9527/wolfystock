# DB Index Batch B: Execution, Provider, and Cost Observability Plan

Status: Partial
Owner domain: Database readiness
Related docs: `docs/audits/db-index-migration-plan-auth-task-log.md`, `docs/audits/db-production-readiness-index-retention-audit.md`

Date: 2026-05-07
Mode: docs-first planning plus non-destructive smoke scaffold. No production database contents, runtime auth/security behavior, provider fallback/runtime behavior, cost/quota enforcement, portfolio/backtest calculations, Options, Data Pipeline, or MarketCache behavior were changed or inspected.

## 1. Executive summary

DB Index Batch A is complete for the first auth/session and durable task/progress lookup paths. Batch B should prepare the next public-readiness slice: execution/admin logs, provider diagnostics, cost observability, provider quota windows, and any remaining durable progress replay gaps.

This plan is intentionally additive. It defines candidate indexes and verification expectations before any production migration. SQLite remains the local/dev compatibility store; PostgreSQL remains the intended durable public multi-user baseline. Production rollout should use online/concurrent index creation where supported and should verify query plans before treating an index as accepted.

No runtime or schema migration is included in this plan. The accompanying smoke scaffold only checks already declared non-destructive index foundations in local SQLite metadata and PostgreSQL baseline text; missing future candidates remain deferred runtime/schema work.

## 2. Scope and non-goals

Included:

- `execution_log_sessions` and `execution_log_events` admin/support reads.
- Phase G `execution_sessions`, `execution_events`, and `admin_logs` baseline readiness.
- Admin log storage/capacity summary and cleanup-preview read paths.
- `llm_usage` raw usage summaries and `llm_cost_ledger` read-only summaries.
- `provider_circuit_events`, `provider_probe_events`, and `provider_quota_windows` diagnostic reads.
- Durable task progress replay only where Batch A coverage leaves a proven gap.
- SQLite versus PostgreSQL rollout notes.

Excluded:

- No auth/security runtime changes.
- No Options, Data Pipeline, provider runtime/fallback, MarketCache, quota enforcement, portfolio, scanner, or backtest behavior changes.
- No production DB reads, writes, cleanup, migrations, or data inspection.
- No broad JSON, GIN, trigram, or text-search indexes without query-plan evidence.
- No retention cleanup implementation.

## 3. Candidate index matrix

| Domain | Table | Index columns | Query pattern | Expected benefit | Risk | SQLite vs PostgreSQL notes | Online/concurrent migration note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Execution sessions | `execution_log_sessions` | `started_at` | Default admin log session timeline and date-window browsing | Avoid scanning all sessions for newest-first admin views | Low; already covered by SQLite column index | SQLite has a simple `started_at` index; PostgreSQL baseline Phase G uses `execution_sessions(started_at desc, subsystem, overall_status)` for the promoted store | PostgreSQL production should use `CREATE INDEX CONCURRENTLY` for large existing log tables |
| Execution sessions | `execution_log_sessions` | `overall_status, started_at` | Status-filtered admin triage, failed/running/completed filters | Keeps high-cardinality time filtering anchored after status | Low/medium; extra write cost on high-volume log inserts | SQLite can use a portable composite btree. PostgreSQL should prefer descending timestamp if newest-first dominates | Build concurrently; verify planner prefers it for status/date filters before adding adjacent variants |
| Execution sessions | `execution_log_sessions` | `task_id, started_at` | Async task drilldown from status/polling/support views | Direct task-to-session lookup without broad task id scan | Low; task id is bounded metadata | SQLite already indexes `task_id` and has code/query composites; composite task/time remains a future gap | Concurrent index; safe drop-index rollback if write amplification is higher than value |
| Execution sessions | `execution_log_sessions` | `code, started_at` | Symbol drilldown and guest/public analysis support search | Fast symbol-scoped log search for admin support | Low; already present as `ix_exec_session_code_started` | SQLite declaration already exists. PostgreSQL Phase G uses `canonical_symbol` in `execution_sessions`; add a Phase G symbol/time variant only after route migration needs it | Existing SQLite path needs no migration; PostgreSQL add concurrently if promoted admin views filter by symbol |
| Execution sessions | `execution_log_sessions` | `query_id, started_at` | Report/query-linked support lookup | Keeps saved report or preview query support reads bounded | Low; already present as `ix_exec_session_query_started` | SQLite declaration already exists; PostgreSQL Phase G has `query_id` but no dedicated query/time index yet | Add concurrently only when Phase G query drilldown is routed |
| Execution events | `execution_log_events` | `session_id, event_at` | Event timeline for one execution session | Core detail/replay path avoids scanning all events | Low; already present | SQLite declaration exists. PostgreSQL Phase G uses `execution_events(execution_session_id, occurred_at asc)` | Existing SQLite path needs no migration; PostgreSQL promoted table already has equivalent |
| Execution events | `execution_log_events` | `phase, status, event_at` | Phase/status triage and failure category windows | Adds time bounding to current phase/status filter | Medium; may duplicate current `phase, status` until date filters dominate | SQLite currently has `phase, status` plus single `event_at`; composite with `event_at` is a candidate gap | Build concurrently after query-plan evidence; avoid adding broad detail JSON indexes |
| Execution events | `execution_log_events` | `target, event_at` | Provider/model/channel drilldown from event target | Speeds safe target-filtered diagnostics without JSON search | Medium; target cardinality may be uneven | SQLite has a single target index; composite target/time is a candidate gap | Add concurrently only if target/date filters become common and bounded |
| Phase G execution | `execution_sessions` | `owner_user_id, started_at` | Owner-scoped promoted execution timeline | Supports tenant-safe support/admin projections | Low; already in PostgreSQL baseline | SQLite compatibility store still uses legacy `execution_log_sessions` | Already baseline text; production create concurrently when Phase G is migrated into an existing database |
| Phase G execution | `execution_sessions` | `overall_status, started_at` | Promoted status-filtered execution session list | Faster operational triage in the promoted store | Medium; currently included after `started_at, subsystem` in baseline, not leading status | PostgreSQL-only baseline artifact today; no SQLite runtime table | Add as a separate concurrent index only if planner cannot use existing started/subsystem/status index for dominant filters |
| Phase G execution | `execution_events` | `phase, status, occurred_at` | Promoted event triage by phase/status/date | Equivalent to legacy event triage with time bound | Low; baseline already has this shape | PostgreSQL baseline uses `occurred_at desc`; SQLite legacy path needs a future `event_at` extension if needed | Already baseline text; use concurrent creation in production |
| Admin logs | `admin_logs` | `occurred_at` | Default log storage summary, date windows, cleanup previews | Bounded oldest/newest and retention preview scans | Low; baseline has `occurred_at desc, subsystem, event_type` but timestamp-only may still be useful | SQLite admin storage summary currently reads legacy execution logs; Phase G PostgreSQL baseline owns `admin_logs` | Add timestamp-only concurrently only if planner cannot use the composite prefix efficiently |
| Admin logs | `admin_logs` | `severity, occurred_at` | Severity filters and warning/critical storage dashboards | Keeps alert-oriented admin pages bounded | Low/medium; severity values are low-cardinality | PostgreSQL should use btree; SQLite equivalent only if admin_logs is local-runtime promoted | Build concurrently after storage-summary route confirms this predicate |
| Admin logs | `admin_logs` | `category, occurred_at` | Category filtering and drilldown | Speeds category tabs without JSON predicates | Low/medium | PostgreSQL baseline has `category` column but no dedicated category/time index | Concurrent creation; verify category selectivity before accepting |
| Admin logs | `admin_logs` | `event_type, occurred_at` | Event family filtering and notification routing evidence | Supports audit families and notification-related admin searches | Low; baseline composite includes event type after occurred/subsystem | PostgreSQL may need event type first when event filters dominate | Build concurrently if event-type-first route filters become dominant |
| Admin logs | `admin_logs` | `actor_user_id, occurred_at` | Actor-scoped audit search | Supports accountability and admin/user support views | Medium; actor may be null for system events | PostgreSQL-only until local admin_logs store is promoted | Concurrent index; consider partial `actor_user_id is not null` only after production planner evidence |
| Admin logs | `admin_logs` | `related_session_key, occurred_at` | Session-linked audit drilldown | Links admin/audit events back to execution sessions | Low/medium; depends on sessionization consistency | PostgreSQL baseline field exists; SQLite legacy store has separate session ids | Add only if session drilldown is wired; build concurrently |
| LLM raw usage | `llm_usage` | `called_at` | Date-window summaries and retention previews for raw usage rows | Avoid full scans for cost window summaries | Low; already a SQLite column index | SQLite has `called_at`; no PostgreSQL baseline table for legacy `llm_usage` yet | If promoted to PostgreSQL, create concurrently before public raw-row growth |
| LLM raw usage | `llm_usage` | `call_type, called_at` | Usage summaries by analysis/agent/market-review family | More selective route-family-like summary without schema change | Low; portable btree | SQLite currently has `call_type` and `called_at` separately; composite is a future candidate | Add concurrently/online only after confirming the raw usage table remains in production scope |
| LLM raw usage | `llm_usage` | `model, called_at` | Model summary and cost anomaly drilldown | Speeds model/time grouping without scanning raw rows | Low/medium; model names can be high-cardinality but bounded | SQLite currently lacks a model index; future PostgreSQL should prefer cost ledger for richer dimensions | Add only if raw `llm_usage` remains a reporting source; otherwise prefer ledger summaries |
| LLM cost ledger | `llm_cost_ledger` | `owner_user_id, created_at` | Owner cost timeline and admin owner drilldown | Core owner/time observability path | Low; already declared | SQLite has this index; PostgreSQL baseline cost-ledger table is not yet present in the architecture artifact | Create concurrently in PostgreSQL if ledger is promoted with existing rows |
| LLM cost ledger | `llm_cost_ledger` | `owner_user_id, route_family, created_at` | Owner route-family cost summary | Supports budget/burn-down visibility without enforcement changes | Low; already declared | SQLite declaration exists. Keep route family separate from quota enforcement | Existing local path needs no migration; PostgreSQL add concurrently when promoted |
| LLM cost ledger | `llm_cost_ledger` | `provider, model, created_at` | Provider/model cost and anomaly drilldown | Helps identify expensive model/provider windows | Low; already declared | SQLite declaration exists | Add concurrently for production ledger promotion |
| LLM cost ledger | `llm_cost_ledger` | `route_family, created_at` | Global route-family cost summaries | Supports admin read-only cost observability | Low; already declared | SQLite declaration exists | Add concurrently for production ledger promotion |
| Provider quota windows | `provider_quota_windows` | `owner_user_id, provider, route_family, window_start, window_end` | Owner/provider window diagnostics and dry-run accounting | Bounded owner-scoped quota-window reads | Low; already declared | SQLite and PostgreSQL baseline both include this shape | Existing baseline should be created concurrently in production |
| Provider quota windows | `provider_quota_windows` | `provider, provider_category, route_family, window_start, window_end` | Provider/route diagnostics over a time window | Core admin provider capacity view | Low; already declared | SQLite and PostgreSQL baseline both include this shape | Existing baseline should be created concurrently in production |
| Provider quota windows | `provider, route_family, provider_category, window_start` | Probe/provider-window lookup | Supports diagnostic probe views keyed by provider route | Low; already declared | SQLite and PostgreSQL baseline both include this shape | Existing baseline should be created concurrently in production |
| Provider quota windows | `provider, route_family, consumed_units, window_end` | High-burn and expiring-window scans | Helps identify windows approaching limits | Medium; may be less useful before live enforcement | SQLite and PostgreSQL baseline both include this shape | Keep additive; verify with dashboard query plans before relying on it |
| Provider circuit events | `provider_circuit_events` | `provider, provider_category, route_family, created_at` | Provider route event history | Core provider diagnostics view | Low; already declared | SQLite and PostgreSQL baseline both include this shape | Existing baseline should be created concurrently in production |
| Provider circuit events | `to_state, created_at` | Open/half-open/closed transition timeline | Fast state transition filter | Low; already declared | SQLite and PostgreSQL baseline both include this shape | Existing baseline should be created concurrently in production |
| Provider circuit events | `owner_user_id, created_at` | Owner-attributed diagnostic history when available | Supports tenant-safe incident review without raw payloads | Medium; owner can be null for system events | SQLite and PostgreSQL baseline both include this shape | Consider partial non-null in PostgreSQL only after evidence |
| Provider circuit events | `event_type, created_at` | Transition/policy event-family filter | Speeds admin event-type tabs | Low; already declared | SQLite and PostgreSQL baseline both include this shape | Existing baseline should be created concurrently in production |
| Provider circuit events | `reason_bucket, created_at` | Bounded reason-code incident search | Avoids raw exception/text search | Low; already declared | SQLite and PostgreSQL baseline both include this shape | Existing baseline should be created concurrently in production |
| Provider probe events | `provider, provider_category, probe_type, created_at` | Provider probe history by route/type | Core probe diagnostics view | Low; already declared | SQLite and PostgreSQL baseline both include this shape | Existing baseline should be created concurrently in production |
| Provider probe events | `actor_user_id, created_at` | Admin actor probe audit | Supports accountability for manual probes | Low/medium; actor can be null for system probes | SQLite and PostgreSQL baseline both include this shape | Consider partial non-null in PostgreSQL only after evidence |
| Provider probe events | `result_bucket, created_at` | Success/failure/degraded probe triage | Keeps bounded result-code diagnostics cheap | Low; already declared | SQLite and PostgreSQL baseline both include this shape | Existing baseline should be created concurrently in production |
| Provider probe events | `state_id, created_at` | Probe-to-circuit-state drilldown | Links probes to circuit state evidence | Low; already declared | SQLite and PostgreSQL baseline both include this shape | Existing baseline should be created concurrently in production |
| Durable progress replay | `durable_task_progress_events` | `task_id, sequence` unique/index | Stable progress replay order | Core replay correctness and fast polling | Low; Batch A already covers this | SQLite has unique and btree declarations; PostgreSQL migration should preserve equivalent | Already complete in Batch A; production add concurrently where not yet present |
| Durable progress replay | `durable_task_progress_events` | `task_id, owner_user_id, sequence` | Mixed ownership check plus replay in one key | May avoid a second lookup on owner-isolated replay routes | Medium; can be redundant with existing `task_id, sequence` plus task ownership | Keep as deferred until real query plans show a gap | Add concurrently only after evidence; do not add speculatively |

## 4. Existing coverage versus deferred gaps

Already covered in current SQLite metadata or PostgreSQL baseline text:

- Legacy execution log session `started_at`, `code + started_at`, and `query_id + started_at`.
- Legacy execution event `session_id + event_at` and `phase + status`.
- Phase G baseline execution event `phase + status + occurred_at`.
- `llm_usage.called_at` and `llm_usage.call_type` single-column raw usage indexes.
- `llm_cost_ledger` owner/time, owner/route/time, provider/model/time, and route/time indexes.
- Provider quota window owner/provider/window, provider/route/window, probe, burn, start/end, and update indexes using the existing `ix_provider_quota_window_*` naming convention.
- Provider circuit event provider/time, state/time, owner/time, type/time, reason/time, operator/time, and created indexes using the existing `ix_provider_circuit_event_*` naming convention.
- Provider probe event provider/time, actor/time, result/time, state/time, and created indexes using the existing `ix_provider_probe_event_*` naming convention.
- Durable progress replay Batch A indexes.

Deferred candidate gaps that should not be added without implementation approval:

- Legacy execution session composites for `overall_status + started_at` and `task_id + started_at`.
- Legacy execution event composites for `phase + status + event_at` and `target + event_at`.
- Phase G status-first execution session indexes if current `started_at + subsystem + overall_status` is not enough.
- Admin log severity/category/event-type/actor/session-first indexes.
- Raw `llm_usage` composites for `call_type + called_at` and `model + called_at` if raw usage remains a production reporting source.
- Durable progress `task_id + owner_user_id + sequence` if owner/replay mixed reads show a real planner gap.
- PostgreSQL cost-ledger baseline DDL if `llm_cost_ledger` is promoted from SQLite runtime into the architecture artifact.

## 5. Smoke scaffold contract

The Batch B smoke scaffold should stay non-destructive:

- Create a disposable SQLite database through the existing `DatabaseManager` initialization path.
- Inspect SQLite metadata only; do not read production DB rows.
- Read PostgreSQL baseline SQL text only; do not connect to PostgreSQL.
- Assert currently declared Batch B foundation indexes remain present and portable.
- Do not assert deferred future candidate indexes until storage/schema migrations are approved.

## 6. Production rollout notes

When Batch B moves from plan to migration:

1. Confirm the exact admin/API query filters and sort order.
2. Add one domain family at a time.
3. Prefer portable SQLite composites for local/dev compatibility.
4. Use PostgreSQL `CREATE INDEX CONCURRENTLY` or the platform equivalent for large existing tables.
5. Avoid wrapping PostgreSQL concurrent index creation inside a transaction.
6. Verify query plans before and after each index.
7. Record write-amplification and index-size impact.
8. Roll back by dropping only the new index if needed; do not treat retention cleanup as rollback.

## 7. Validation plan

Current pass:

- `git diff -- docs/audits/db-index-batch-b-execution-provider-cost-plan.md docs/CHANGELOG.md`
- `git diff --check -- docs/audits/db-index-batch-b-execution-provider-cost-plan.md docs/CHANGELOG.md tests/test_db_index_batch_b.py`
- `python3 -m py_compile tests/test_db_index_batch_b.py`
- `python3 -m pytest tests/test_db_index_batch_b.py -q`

Future migration pass:

- Add focused SQLite metadata tests for every new runtime index.
- Add PostgreSQL baseline text tests for every promoted baseline index.
- Run route-focused admin log, cost summary, and provider diagnostics tests.
- Run query-plan smoke checks against synthetic or staging-safe data.
- Run restore-smoke index-presence checks after backup/restore drills.

## 8. Final status for this pass

Status: **PLAN READY, RUNTIME/SCHEMA WORK DEFERRED**.

Batch B can proceed as separate implementation slices after approval:

1. execution/admin log composites;
2. admin log storage/capacity indexes;
3. raw `llm_usage` versus `llm_cost_ledger` promotion decision;
4. provider diagnostics confirmation;
5. provider quota-window production query-plan validation;
6. durable progress replay gap check.
