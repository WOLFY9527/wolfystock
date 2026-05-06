# CI / PostgreSQL Gate Failure Triage Guide

Date: 2026-05-07
Mode: docs-only triage guide. No runtime code, tests, scripts, database schema,
provider behavior, analysis behavior, Options behavior, auth behavior, cost
behavior, or portfolio behavior was changed.

## 1. Purpose

Recurring local `./scripts/ci_gate.sh` failures are not always caused by the
task under review. This guide standardizes how to classify failures as
task-caused, local environment/setup, unrelated dirty worktree, or
flaky/external before reporting or deferring the full gate.

Use this guide when:

- focused tests for the touched domain pass but full `ci_gate` fails;
- local PostgreSQL is missing, stale, or missing baseline tables such as
  `app_users`, `provider_configs`, or `portfolio_accounts`;
- optional local tools such as `flake8`, `akshare`, or `yfinance` are absent;
- the worktree contains concurrent unrelated edits;
- real-PostgreSQL phase tests fail differently from isolated reruns.

This guide does not authorize fixing unrelated test failures, changing schema,
resetting databases, cleaning git state, or widening the task scope.

## 2. Current `ci_gate` Phases

The current backend gate is `scripts/ci_gate.sh`. It first runs
`scripts/task_preflight.sh`, then validates optional tool availability,
critical syntax/lint paths, deterministic smoke commands, and the offline
pytest suite.

| Phase label | Command / behavior | What it validates | Common non-task blockers |
| --- | --- | --- | --- |
| `preflight status` | `scripts/task_preflight.sh` | Branch, upstream, dirty file count/categories, recent commits. | Concurrent dirty files, wrong branch, unrelated generated docs or frontend/backend edits. |
| `environment / optional tools` | Python path plus `flake8`, `akshare`, `yfinance` import checks. | Whether local dev tools and provider libraries are present. In CI, missing `flake8` is blocking; locally it is warning-only. | Missing `flake8`, missing provider packages, mismatched Python interpreter. |
| `backend critical lint` | `flake8 . --select=E9,F63,F7,F82` when available. | Fatal Python syntax/name errors that static lint can catch. | Local `flake8` not installed; CI still requires it. |
| `backend syntax check (core app)` | `python -m py_compile main.py src/config.py src/auth.py src/analyzer.py src/notification.py` | Core import/syntax health. | Dependency import side effects, local interpreter mismatch. |
| `backend syntax check (storage + search)` | `python -m py_compile src/storage.py src/scheduler.py src/search_service.py` | Storage/search/scheduler syntax health. | PostgreSQL env variables or local import side effects if code changes make imports eager. |
| `backend syntax check (market analyzers)` | `python -m py_compile src/market_analyzer.py src/stock_analyzer.py` | Market analyzer syntax health. | Provider dependency import drift. |
| `backend syntax check (data providers)` | `python -m py_compile data_provider/*.py` | Provider module syntax health. | Optional provider packages missing if imports are not guarded. |
| `local deterministic checks` | Informational provider-dependency note. | Separates deterministic script checks from provider availability warnings. | Missing provider modules, unavailable local fetchers. |
| `test.sh code` | `./test.sh code` | Stock-code recognition and conversion checks through the root `test.sh` script. | Optional dependency warnings from `test.sh`, local Python path issues. |
| `test.sh yfinance` | `./test.sh yfinance` | YFinance conversion/smoke path. | Missing `yfinance`, network/provider availability, rate limits. |
| `offline test suite` | `python -m pytest -m "not network"` | Full offline backend regression suite. | Stale local DB, missing PostgreSQL baseline, real-PG phase isolation issues, unrelated dirty tests. |

There is no `scripts/test.sh` in the current checkout; `ci_gate` calls the root
`./test.sh`.

## 3. Common Local Blockers

### Missing PostgreSQL service

Symptoms:

- connection refused or timeout for local PostgreSQL;
- real-PG tests skip/fail depending on configured DSN;
- errors appear before a domain-specific assertion runs.

Classification default: environment/setup failure unless the task changed DB
connection configuration, PostgreSQL phase code, test fixtures, or schema
bootstrap.

Required report language:

```text
ci_gate failed/deferred because local PostgreSQL was unavailable. Focused
task tests: PASS/FAIL. This is classified as environment/setup unless the task
changed DB connection or PostgreSQL bootstrap behavior.
```

### Missing schema baseline

Symptoms:

- missing relation/table errors such as `app_users`, `provider_configs`,
  `portfolio_accounts`, `execution_log_sessions`, or phase-specific tables;
- foreign key setup failures during seed/bootstrap;
- focused SQLite/fallback tests pass, but real-PG setup fails before business
  assertions.

Classification default: environment/setup failure if the task did not touch
schema, migrations, bootstrap, storage initialization, or PostgreSQL phase
code.

Do not repair by hand with ad hoc SQL. Use approved bootstrap scripts or a
separate implementation task.

### Stale local DB

Symptoms:

- table exists but lacks expected columns/indexes;
- FK references point to stale seeded users or old test identities;
- phase tests pass in isolation after clean setup but fail in full order on a
  reused local DSN.

Classification default: environment/setup or flaky/isolation failure. Escalate
to task-caused only if the task changed lifecycle cleanup, factory reset,
identity bootstrap, or phase storage contracts.

### Missing optional dev tools

Symptoms:

- local warning for missing `flake8`;
- warnings for missing `akshare` or `yfinance`;
- provider-dependent script warnings without code assertion failures.

Classification default: environment/setup. In CI, missing `flake8` is blocking;
locally, current `ci_gate` warns and continues.

### Concurrent dirty worktree

Symptoms:

- `scripts/task_preflight.sh` reports dirty categories unrelated to the task;
- failures appear in files or route families not touched by the task;
- `git status --short` shows unrelated docs, frontend, backend, CSS, or test
  edits from another session.

Classification default: unrelated dirty failure if focused tests for the task
pass and the failing tests map to unrelated dirty files or adjacent in-progress
domains.

Required report language:

```text
ci_gate deferred due to unrelated dirty worktree.
Dirty files at gate time:
- <exact path/status>
Focused task tests: <exact commands and PASS/FAIL>.
```

## 4. Failure Classification

### Task-caused failure

Use this when the failure is on the changed surface or a direct contract of the
changed surface.

Examples:

- changed `src/storage.py`, then storage py_compile or DB lifecycle tests fail;
- changed API schema, then matching API contract tests fail;
- changed provider import behavior, then provider syntax/import checks fail;
- changed auth/session logic, then auth or protected-route tests fail;
- changed PostgreSQL schema/bootstrap, then real-PG baseline setup fails.

Required action: fix or explicitly report **NOT YET GREEN** with the exact
failing test and root-cause evidence.

### Environment/setup failure

Use this when the local machine is missing required services, schema baseline,
or optional packages and the task did not touch those contracts.

Examples:

- PostgreSQL is not running;
- local DB lacks `app_users` or `portfolio_accounts`;
- `provider_configs` FK seed fails before task code is exercised;
- `flake8`, `akshare`, or `yfinance` is missing locally.

Required action: report the environment blocker and do not make unrelated setup
changes unless explicitly authorized.

### Unrelated dirty failure

Use this when the gate includes concurrent edits outside the task and the
failure maps to those dirty files or to unrelated domain behavior.

Examples:

- docs-only task but backend tests fail while backend files are dirty from
  another session;
- frontend task but admin/logging backend files are dirty and admin-log tests
  fail;
- target task focused tests pass, but full suite fails in a domain that has
  unstaged unrelated edits.

Required action: leave unrelated files untouched, do not stage them, and report
`ci_gate deferred due to unrelated dirty worktree`.

### Flaky/external failure

Use this when the failure depends on network/provider availability, rate
limits, time, real-PG suite ordering, or shared local service state, and an
isolated rerun or focused command does not reproduce the failure.

Examples:

- yfinance/provider smoke fails with availability or rate-limit symptoms;
- real-PG phase deadlock or identity-table interference appears only in the
  full sweep;
- a full-suite order issue fails once and passes on focused rerun.

Required action: report both the full-gate failure and focused rerun result.
Do not hide the gate result.

## 5. Required Report Language

Every gate triage report should include:

- exact failing command and test, including pytest node id when available;
- whether focused task tests passed, with command names and PASS/FAIL;
- dirty files at the time of the gate, at least the paths relevant to the
  classification;
- whether the failure is task-caused, environment/setup, unrelated dirty, or
  flaky/external;
- why `ci_gate` was deferred, failed, or considered non-authoritative;
- whether any secrets or DB contents were avoided in captured evidence.

Suggested format:

```text
ci_gate result: PASS / FAIL / DEFERRED
Classification: task-caused / environment-setup / unrelated-dirty / flaky-external
Exact failing command/test:
Focused tests:
Dirty files at gate time:
Why this is or is not task-related:
Next required action before push:
```

## 6. Cleanup and Safety Rules

Do not run destructive cleanup while triaging a gate failure.

Forbidden without explicit user approval:

- `git reset`, `git clean`, or checkout/restore of unrelated files;
- `git add .`;
- dropping, truncating, deleting, or recreating local DB tables;
- factory reset or schema bootstrap that destroys data;
- printing `.env` values, provider credentials, broker credentials, DB
  passwords, session IDs, cookies, API keys, raw prompts, raw provider payloads,
  or production DB contents;
- changing provider, analysis, options, auth, cost, portfolio, scanner,
  backtest, DB/schema, script, or test code during a docs-only triage task.

Allowed without extra approval:

- read-only `git status --short`, `git diff --stat`, and focused `git diff`
  inspection;
- focused tests for changed files/domains;
- docs-only `git diff --check`;
- sanitized reporting of missing table names, failing test node IDs, and
  bounded error categories.

## 7. Final Pre-push Standard

Before pushing a code-bearing change to `main` or a PR branch, the expected
standard is:

1. Clean worktree except for the intended staged change.
2. One full successful `./scripts/ci_gate.sh`.
3. Frontend validation when `apps/dsa-web` changed:
   - `npm run lint`;
   - `npm run build`;
   - `npm run check:design` when present or relevant.
4. Browser harness smoke for user-visible frontend changes, using an isolated
   preview/dev port and reporting route, viewport, mock/auth state, and
   console/page errors.
5. Explicit report of any skipped validation and why it is safe or not safe.

Docs-only triage changes do not require `ci_gate`. They should run:

```bash
git diff -- docs/audits/ci-postgres-gate-triage-guide.md docs/CHANGELOG.md
git diff --check -- docs/audits/ci-postgres-gate-triage-guide.md docs/CHANGELOG.md
```

If `docs/CHANGELOG.md` is already dirty from another task, skip it and report
that it was not touched.

## 8. Recommended Future Implementation

These are future implementation ideas, not part of this docs-only guide.

### Local PostgreSQL bootstrap smoke

Add a non-destructive local smoke command that checks:

- PostgreSQL connectivity;
- expected schema baseline tables exist;
- synthetic bootstrap user/session fixtures can be created in an isolated test
  schema or disposable DB;
- phase-specific tables are present before real-PG suites run.

The smoke should never drop or recreate user databases without an explicit flag
and confirmation.

### `ci_gate` phase labels

Make phase labels machine-readable and stable so reports can cite:

- preflight;
- optional dependency preflight;
- critical lint;
- py_compile groups;
- root `test.sh` code/yfinance checks;
- offline pytest;
- real-PG setup or phase-specific subgroups if split later.

### Optional dependency preflight

Add a quick local preflight that prints install guidance for optional packages:

- `flake8` as CI-required and local warning/blocking mode;
- `akshare` and `yfinance` as provider-dependent local smoke requirements;
- PostgreSQL client/server availability when real-PG tests are selected.

The preflight should use package names and env var names only, not secret values.

## 9. Quick Decision Table

| Observation | Focused task tests | Dirty state | Default classification | Report action |
| --- | --- | --- | --- | --- |
| Changed file's direct tests fail | Fail | Any | Task-caused | Fix or report NOT YET GREEN. |
| `app_users` or `portfolio_accounts` missing locally | Pass or not reached | Clean or dirty | Environment/setup | Report missing schema baseline; do not repair DB destructively. |
| `provider_configs` FK seed fails before assertions | Pass or not reached | Clean or dirty | Environment/setup | Report bootstrap/seed blocker. |
| Real-PG phase deadlock or identity failure only in full order | Focused rerun passes | Clean | Flaky/external or suite-isolation | Report both full failure and focused rerun. |
| Admin/logging tests fail while admin/logging files are dirty from another task | Pass | Dirty unrelated domain | Unrelated dirty | Defer full gate and list dirty files. |
| Missing `flake8` locally | Pass | Any | Environment/setup | Local warning; CI blocking. |
| Missing `akshare` or `yfinance` | Pass | Any | Environment/setup or flaky/external | Report provider dependency gap. |
| Network/provider rate-limit message | Pass | Any | Flaky/external | Report sanitized provider availability issue. |
