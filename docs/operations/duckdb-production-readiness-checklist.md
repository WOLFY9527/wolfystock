# DuckDB Production Readiness Checklist

Date: 2026-05-05 Asia/Shanghai  
Repository: `/Users/yehengli/daily_stock_analysis`  
Branch: `main`  
Mode: docs-only architecture governance

## 1. Executive Summary

DuckDB is currently an optional diagnostic quant engine only. It is used for bounded validation, coverage checks, research queries, factor comparisons, and operator smoke tests when explicitly enabled or explicitly invoked.

WolfyStock production runtime remains unchanged. PostgreSQL remains the business database for users, portfolio accounting, watchlists, admin logs, settings, analysis tasks, and backtest metadata. The existing Python runtime remains the production path for scanner selection, backtest calculations, portfolio accounting, AI decisions, provider behavior, and notification routing.

No scanner, backtest, or portfolio runtime integration is allowed without future explicit approval. DuckDB must not become a production dependency through incidental API usage, admin UI behavior, scheduled jobs, hidden writes, package defaults, or generated artifacts.

This checklist defines the gates, evidence, blockers, operational rules, and future prompt language required before DuckDB can ever be proposed for production runtime use in WolfyStock. Passing this checklist does not approve productionization; it only establishes the minimum evidence needed before a separate production proposal can be reviewed.

## 2. Current Safety Boundary

The current DuckDB boundary is:

- DuckDB is disabled by default with `QUANT_DUCKDB_ENABLED=false`.
- The default runtime engine remains `QUANT_ENGINE=python`.
- Disabled mode must not create `*.duckdb`, `*.duckdb.wal`, Parquet, or other generated database artifacts.
- Read diagnostics require authenticated operator/admin context plus `quant:admin:read`.
- Init, ingest, and factor build require authenticated operator/admin context plus `quant:admin:write`.
- DuckDB writes require explicit operator actions such as init, ingest, or factor build; no auto-run or background trigger is allowed.
- Health, coverage, benchmark, factor snapshot, factor validation, and runtime-context comparison are diagnostic endpoints only.
- `compare-runtime-context` diagnostics must keep `diagnostics.productionRuntimeChanged=false`.
- Scanner scoring, ranking, selection, thresholds, and generated candidates must not consume DuckDB output.
- Backtest accounting, fills, fees, returns, benchmark comparisons, and deterministic calculations must not consume DuckDB output.
- Portfolio accounting, cash ledger, positions, realized/unrealized PnL, FX handling, and ownership boundaries must not consume DuckDB output.
- No full-market automatic jobs may initialize, ingest, build factors, or refresh DuckDB implicitly.
- No hidden background writes may create or mutate DuckDB files.
- No generated DuckDB database, WAL, Parquet, coverage, benchmark, or smoke artifact may be committed.
- Admin UI actions must stay explicit, bounded, authenticated, and visible to operators.
- Local smoke experiments must use temp or explicitly local database paths and clean them up.

## 3. Readiness Gates

All gates below must pass before any production integration can be proposed.

### Correctness Parity

- DuckDB factor calculations must match the current Python reference implementation for deterministic fixtures and representative real snapshots.
- Differences must be explained, reviewed, and approved before use; unexplained differences are blockers.
- Scanner-facing, backtest-facing, and portfolio-facing values must preserve the existing business semantics exactly unless a separate approved business change exists.

### Data Freshness And Lineage

- Every DuckDB row must expose provider/source lineage, ingestion time, build time, symbol normalization, date range, and snapshot identity.
- Freshness rules must distinguish live, cached, stale, partial, and fallback data.
- Provider fallback behavior must remain visible and must not silently change trading, scanner, backtest, or portfolio outcomes.

### Failure-Mode Safety

- DuckDB unavailable, disabled, missing schema, stale data, partial data, corrupted files, locked files, and memory pressure must degrade to explicit diagnostics.
- Failures must not alter scanner results, backtest outputs, portfolio accounting, alerts, notifications, or AI decisions.
- Any fallback from DuckDB to Python must be explicit in logs and response diagnostics.

### Performance And Memory Budget

- Production proposals must include measured CPU, memory, disk, and latency budgets under realistic symbol counts and date ranges.
- Benchmarks must cover cold start, warm cache, repeated runs, concurrent operator requests, and worst-case bounded workloads.
- DuckDB must not starve the API server, scheduled jobs, frontend requests, or portfolio/backtest workloads.

### Concurrency And Single-Flight Behavior

- Init, ingest, factor build, cleanup, and backfill operations must have single-flight or equivalent locking behavior.
- Duplicate clicks, repeated API calls, and concurrent sessions must not double-count rows, corrupt files, or create inconsistent coverage.
- Read requests must define behavior while writes are in progress.

### Write Isolation

- DuckDB writes must be isolated from PostgreSQL business data and from Python runtime outputs.
- Default disabled mode must remain no-write.
- Enabled experiments must write only to explicit operator-selected paths or controlled temp paths.
- Production proposals must define transaction behavior, file locking, idempotency, and cleanup on failure.

### Rollback Strategy

- A production proposal must prove that disabling DuckDB restores the current Python runtime without data loss or behavior drift.
- Rollback must include config steps, file cleanup steps, stale artifact detection, and operator verification.
- Rollback must not require database migrations or generated file edits to restore current production behavior.

### Observability

- Logs must identify actor, session, endpoint/action, symbol scope, date range, source snapshot, row counts, duration, data mode, and write path.
- Metrics must cover health, availability, init attempts, ingest rows, factor rows, benchmark duration, comparison mismatches, disabled no-write checks, failures, and cleanup.
- Runtime comparison diagnostics must remain visible and must keep `productionRuntimeChanged=false` until a separately approved production integration changes that contract.

### Admin And Operator Controls

- Admin controls must remain authenticated, permission-gated, explicit, bounded, and visible.
- Dangerous actions must show scope, path, dry-run status, row counts, and cleanup guidance.
- Operator surfaces must distinguish config validation, runtime health, external/provider connectivity, and data coverage.
- Developer details must stay collapsed by default and must not leak unsafe absolute paths, tokens, stack traces, or secrets.

### Permission And Auth Boundaries

- DuckDB routes must remain authenticated operator/admin surfaces unless a separate access model is approved.
- Read diagnostics must continue to require `quant:admin:read`; write-like routes must continue to require `quant:admin:write`.
- Guest, public, and non-admin users must not trigger writes, factor builds, benchmarks with sensitive data, or artifact creation.
- Any future read exposure must define tenant/user ownership, symbol scope, privacy rules, and audit logging.

### Privacy And Security

- DuckDB files must not contain secrets, user tokens, webhook URLs, private account identifiers, or unredacted personal data.
- Local paths returned by APIs or UI must remain sanitized.
- Generated files must be excluded from commits, build artifacts, logs, screenshots, and support bundles unless explicitly approved and scrubbed.

### CI And Smoke Coverage

- Quant DuckDB tests must cover disabled no-write, enabled temp DB, factor build, deterministic parity, duplicate ingest, coverage, benchmark, factor snapshot, factor validation, and runtime comparison diagnostics.
- Scanner, backtest, and portfolio regression tests must pass whenever a proposal touches shared data paths.
- Admin UI changes must have unit and browser checks, including disabled, enabled, unavailable, and error states.
- Generated file scans must prove no `*.duckdb`, `*.duckdb.wal`, or generated Parquet artifacts were created or committed.

### Migration And Backfill Safety

- Any migration/backfill proposal must be dry-run first, bounded by symbol/date/snapshot, idempotent, observable, and reversible.
- Full-market ingest or backfill requires explicit approval and a separate runbook.
- Backfill must not mutate scanner/backtest/portfolio production outputs unless the production change has already been approved separately.

## 4. Non-Negotiable Blockers

Any item below blocks DuckDB production consideration:

- Any discrepancy with Python runtime calculations that is unexplained, unapproved, or untested.
- Any silent fallback that changes trading, scanner, backtest, portfolio, AI, provider, notification, or report outcomes.
- Any default write behavior in disabled mode.
- Any generated DuckDB file committed to the repository.
- Any generated DuckDB file created during normal disabled-mode health, coverage, validation, comparison, or UI loading.
- Any changed scanner scoring, ranking, thresholds, symbol selection, or candidate ordering without dedicated approval.
- Any changed backtest accounting, fills, fees, return calculations, deterministic result semantics, or benchmark semantics without dedicated approval.
- Any changed portfolio accounting, cash ledger, positions, realized/unrealized PnL, FX handling, ownership, or permission semantics without dedicated approval.
- Any hidden scheduled factor job, hidden background ingest, or implicit full-market refresh.
- Any path without the required authenticated operator/admin context and capability guard that can initialize, ingest, build, mutate, or clean DuckDB files.
- Any unbounded ingest/build/benchmark operation exposed without hard limits and operator-visible scope.
- Any unsafe file path, token, secret, stack trace, or private account identifier exposed in UI, logs, or API responses.

## 5. Required Comparison Evidence

Future production proposals must include evidence for:

- DuckDB vs Python factor comparison over deterministic fixtures.
- DuckDB vs Python factor comparison over representative real provider snapshots.
- Deterministic fixture comparison for all current factor columns.
- Edge cases for missing OHLCV fields, missing dates, zero or invalid prices, low volume, and short histories.
- Edge cases for split/corporate-action gaps, adjusted/unadjusted close mismatches, partial sessions, holiday gaps, and stale provider data.
- Repeated-run determinism proving repeated ingest/build operations do not double-count or drift.
- Disabled no-write proof for health, coverage, init without override, ingest, build, benchmark, factor snapshot, validate-factor-path, compare-runtime-context, and admin UI load.
- Enabled temp DB proof using a temp path that is initialized, ingested, built, queried, and cleaned up.
- Clean rollback proof showing that disabling DuckDB restores the Python runtime and leaves no generated files behind.
- Comparison diagnostics proving `productionRuntimeChanged=false` before any approved runtime integration.

Evidence must include exact commands, input fixtures or snapshot identifiers, row counts, mismatch counts, duration, data mode, artifact scan output, and final git status.

## 6. Required Tests And Checks Before Future Production Proposal

Before any future production proposal, run and report the smallest sufficient checks plus any wider checks required by touched areas:

- Backend quant DuckDB tests, including service and API tests.
- Scanner regression tests if scanner paths, symbols, scores, filters, ranking, or thresholds are touched.
- Backtest regression tests if backtest data paths, calculations, accounting, result shaping, or report semantics are touched.
- Portfolio accounting tests if portfolio data paths, positions, cash ledger, PnL, FX, ownership, or account isolation are touched.
- Disabled no-write tests for service, API, and admin UI auto-load behavior.
- Enabled temp DB smoke using an explicit temp path and cleanup verification.
- `./scripts/ci_gate.sh` when code, tests, scripts, backend/API, scanner, backtest, portfolio, or shared runtime behavior changes.
- Playwright admin UI checks on desktop and narrow/mobile layouts when the admin surface changes.
- Generated file scan for `*.duckdb`, `*.duckdb.wal`, Parquet snapshots, coverage output, benchmark output, screenshots, traces, and test reports.
- `git diff --check` for changed files.

For docs-only governance changes, full `ci_gate` is not required unless the task changes executable behavior or the operator explicitly asks for it.

## 7. Operational Rules

### DB Path Rules

- Default disabled configuration must not create the default `DUCKDB_DATABASE_PATH`.
- Local smoke runs must prefer temp paths such as `/tmp/wolfystock-smoke.duckdb`.
- Persistent paths must be explicit, documented, operator-owned, and excluded from commits.
- API/UI responses must return sanitized paths, not unsafe absolute local paths.

### File Cleanup Rules

- Smoke runs must remove the DuckDB file and WAL file after validation.
- Cleanup commands must be scoped to the explicit temp/local path used by the operator.
- Operators must run a generated file scan before committing or pushing.

### Retention Rules

- Diagnostic DuckDB files are local experiment artifacts unless a future production runbook defines retention.
- No retention policy may keep generated DuckDB or Parquet artifacts in the repository.
- Future production retention must define location, owner, lifecycle, backup, restore, encryption, and deletion rules.

### Admin Permissions

- Read diagnostics such as health, coverage, benchmark, factor snapshot, validation, and runtime comparison must remain operator/admin routes guarded by `quant:admin:read` while DuckDB is diagnostic.
- Write-like actions such as init, ingest, build, and cleanup must remain operator/admin routes guarded by `quant:admin:write`.
- Any future non-admin read path requires a separate permission model, privacy review, tenant/user boundary review, and audit logging plan.

### Backup And Restore Expectations

- Diagnostic DuckDB files do not need backup and should be disposable.
- Production proposals must define whether DuckDB is a cache, derived artifact, or source of truth.
- If DuckDB ever becomes productionized, backup and restore must be tested before launch and must not replace PostgreSQL business-data backups.

### Logging And Metrics

- Log each write action with actor/session, endpoint/action, database path category, symbol count, date range, row counts, duration, data mode, and result status.
- Log disabled no-write checks and blocked write attempts without leaking secrets or unsafe paths.
- Track mismatch counts, missing symbols, insufficient symbols, stale snapshots, failed cleanup, file-lock failures, and memory/performance budget violations.

### Provider Snapshot Lineage

- Ingested OHLCV and built factors must record source/provider lineage and snapshot identity.
- Factor comparisons must state whether they used live, cached, stale, fallback, fixture, or manually supplied payload data.
- Lineage gaps must block production proposals until resolved.

## 8. Allowed Next Work

The following work is allowed while DuckDB remains diagnostic-only and optional:

- Report-only DuckDB vs Python comparison documents.
- Admin QA smoke reruns for disabled, enabled temp DB, unavailable, and error states.
- Benchmark reports with explicit symbol/date bounds and temp/local paths.
- Controlled temp DB experiments that clean up generated files.
- Deterministic fixture expansion for factor parity, edge cases, and disabled no-write behavior.
- Docs improvements, smoke guide updates, and test coverage improvements that preserve current runtime behavior.
- Additional operator checklists for cleanup, artifact scans, and rollback drills.

## 9. Disallowed Next Work Without Explicit Approval

The following work is disallowed unless the operator explicitly approves that specific scope:

- Replacing Python scanner runtime with DuckDB.
- Changing scanner scoring, ranking, thresholds, filters, candidate generation, or actionability based on DuckDB.
- Replacing backtest calculations, accounting, fills, fees, returns, or result semantics with DuckDB.
- Replacing portfolio accounting, cash ledger, PnL, FX, account ownership, or account isolation with DuckDB.
- Full-market automatic ingest, backfill, or scheduled factor jobs.
- Hidden scheduled factor jobs or background DuckDB writes.
- Persistent production DB writes by default.
- Enabling DuckDB globally by config, package defaults, migration defaults, deployment defaults, or admin UI auto-actions.
- Connecting DuckDB to scanner, backtest, portfolio, AI, notification, or provider production runtime.
- Committing generated DuckDB, WAL, Parquet, benchmark, coverage, smoke, screenshot, trace, or test-result artifacts.

## 10. Future Implementation Prompt Requirements

Use this paragraph in future Codex prompts that touch DuckDB:

> DuckDB remains optional, disabled by default, and diagnostic-only unless this task explicitly approves a named production integration. Do not change scanner scoring, backtest calculations, portfolio accounting, provider behavior, AI decisions, notifications, package/config defaults, migrations, or runtime behavior. Preserve disabled no-write behavior and `diagnostics.productionRuntimeChanged=false` for comparison diagnostics. Use explicit temp/local DB paths for any smoke work, clean up generated files, scan for `*.duckdb`, `*.duckdb.wal`, and generated Parquet artifacts before staging, stage only named task files, and report exact validation evidence and rollback steps.

## 11. Non-Goals

This checklist does not change runtime behavior.

- No product code changed.
- No tests changed.
- No CSS changed.
- No backend/API code changed.
- No scripts changed.
- No package files or config changed.
- No migrations added.
- No generated artifacts committed.
- No DuckDB runtime behavior changed.
- No DuckDB global enablement approved.
- No scanner, backtest, portfolio, AI, provider, notification, or production runtime integration approved.
- No `docs/CHANGELOG.md` update required for this docs-only governance artifact.
