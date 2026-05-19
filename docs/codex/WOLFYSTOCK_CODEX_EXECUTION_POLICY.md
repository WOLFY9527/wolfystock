# WolfyStock Codex Execution Policy

> Condensed execution policy for Codex tasks in the WolfyStock repository.
> `AGENTS.md` remains the single source of truth for repository AI collaboration rules.
> Recommended location: `docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md`

## 1. Purpose

This file defines the default operating rules for Codex tasks in WolfyStock.  
Task prompts should reference this file instead of repeating common rules.

The goals are:

- maximize implementation quality
- minimize prompt length and repeated instructions
- reduce unnecessary worktrees, branches, merges, and cleanup
- prevent protected-domain regressions
- keep frontend work paused unless explicitly requested
- preserve modular boundaries and future maintainability

## 2. Default Task Execution Mode

### 2.1 Single Task

For a single non-parallel task, run directly on `main`.

Use `main` when:

- only one Codex worker is running
- the task has a narrow, clear scope
- there is no expected file conflict
- the user did not explicitly request a worktree

Before editing, Codex must verify:

```bash
cd /Users/yehengli/daily_stock_analysis
git fetch origin
git switch main
git pull --ff-only origin main
git status --short --branch
```

Stop if the working tree is dirty, branch is not `main`, or `git pull --ff-only` fails.

### 2.2 Parallel Tasks

Use git worktrees only when tasks are actually parallel or isolation is explicitly valuable.

Use worktrees when:

- two or more Codex workers are active at the same time
- tasks touch different modules and can safely proceed independently
- a task is high-risk and should not run on `main`
- the user explicitly requests a worktree

Worktree naming convention:

```text
Branch: codex/<task-id>-<short-slug>
Workspace: /Users/yehengli/worktrees/<task-id>-<short-slug>
```

Example:

```text
Branch: codex/t217e-backtest-parameter-stability
Workspace: /Users/yehengli/worktrees/t217e-backtest-parameter-stability
```

### 2.3 High-Risk Tasks

The following tasks should normally push a branch only and should not auto-merge unless explicitly requested:

- DB migrations
- storage changes
- task queue / lease / durable worker changes
- LLM ledger / quota / billing changes
- provider runtime / provider order changes
- MarketCache core behavior changes
- Backtest engine math changes
- Portfolio accounting / holdings / lots / cash ledger / broker sync
- auth / RBAC / admin unlock
- API schema changes that are not clearly additive
- tasks with merge conflicts
- tasks that touch multiple protected domains

## 3. Frontend Freeze

Frontend visual work is paused by default.

Do not start frontend work unless the user explicitly requests it.

Forbidden by default:

- Home visual redesign
- mockup parity work
- global CSS edits
- layout / shell redesign
- Admin visual redesign
- frontend polish
- visual regression baseline work

Allowed only when task-specific prompt explicitly permits:

- frontend type updates needed for backend API compatibility
- narrowly scoped frontend tests
- non-visual API client typing
- critical compile fixes caused by an approved backend contract change

When frontend is touched, run:

```bash
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run build
```

If the task is visual, also run design checks and browser verification as specified by the user.

## 4. Product-Domain Planning

Prefer product-domain batches over scattered module hopping.

A planning phase should choose one functional cluster, such as:

- Market Intelligence
  - Market Overview
  - Liquidity Monitor
  - Rotation Radar

- Backtest Research
  - Backtest contracts
  - walk-forward / OOS
  - transaction costs / slippage / capacity
  - parameter stability
  - factor research bridge

- Alpha Factory
  - factor observations
  - factor metrics
  - neutralization
  - exposure
  - research reports
  - experiment manifests

- Portfolio Research
  - construction read model
  - rebalance read model
  - factor exposure
  - risk attribution
  - stress / VaR / benchmark attribution

Avoid mixing unrelated product domains in the same batch unless one task is purely read-only or housekeeping.

## 5. Task Sizing

### 5.1 Avoid Over-Splitting

Do not split a normal implementation into many tiny tasks when one coherent task can safely complete it.

Bad split:

```text
T-XXXA add helper
T-XXXB add tests
T-XXXC add docs
T-XXXD add export
```

Better:

```text
T-XXX feature tranche
- helper/service
- schema or contract if needed
- focused tests
- docs/changelog only if needed
- validation
```

### 5.2 When to Split

Split tasks when:

- they touch different protected domains
- they would create merge conflicts
- one task requires audit before implementation
- engine math, storage, provider runtime, or accounting behavior may change
- one task can proceed safely while another must remain serial

### 5.3 Audit Tasks

Use read-only audits only when the implementation path is uncertain or high-risk.

Do not use audits as busywork.  
Do not audit small, obvious additive helpers.

Read-only audit tasks must not:

- edit files
- stage files
- commit
- push
- run destructive commands

They must end with:

```bash
git status --short --branch
```

## 6. Protected Domains

### 6.1 Data Truthfulness

Never make fallback, stale, partial, unavailable, or synthetic data appear live or fresh.

Preserve or improve:

- `source`
- `sourceLabel`
- `asOf`
- `freshness`
- `isFallback`
- `isStale`
- `isPartial`
- `isUnavailable`
- `coverage`
- `confidenceWeight`
- `degradationReason`
- `capReason`

Do not invent:

- fake OHLC
- fake market events
- fake scores
- fake signals
- fake provider results
- fake evidence

Missing data must remain explicit.

### 6.2 Provider Runtime

Do not change provider order unless the task explicitly says so.

Do not add new providers unless explicitly requested.

Do not broaden live provider calls in helper-only or test-only tasks.

Provider/cache tasks must preserve:

- timeout/deadline behavior
- fallback truthfulness
- stale snapshot behavior
- public API response compatibility

### 6.3 Portfolio Accounting

Never mutate accounting state unless the task explicitly authorizes it.

Forbidden by default:

- cash ledger writes
- holdings mutation
- lots mutation
- cost basis mutation
- P&L mutation
- account snapshot mutation
- broker sync/import
- orders/trades/execution
- rebalancing execution

Portfolio research tasks should be advisory-only/read-model-only unless explicitly scoped otherwise.

### 6.4 Backtest

Do not change existing engine math unless explicitly requested.

Protected by default:

- `RuleBacktestEngine` execution math
- `BacktestEngine` evaluation math
- stored-first reopen/provenance logic
- persistence/readback boundaries
- provider/local fallback paths

Backtest research scaffolds should be additive and test-fixture based unless the task explicitly promotes them into runtime.

### 6.5 LLM Cost / Ledger / Quota

Do not change provider/model fallback order.

Do not change quota semantics unless the task explicitly requires it.

Preserve:

- ledger idempotency
- logical request identity
- billable attempt identity
- retry attempt accounting
- owner/guest/global scope separation

### 6.6 Auth / RBAC / Admin

Do not relax auth or RBAC.

Do not add admin unlock paths.

Admin diagnostics should be read-only unless explicitly scoped otherwise.

### 6.7 Docs / Assets

Prefer merge, archive, or delete duplicate/stale docs instead of merely moving clutter.

Do not move protected root governance files without explicit user approval:

- `AGENTS.md`
- `CLAUDE.md`
- `SKILL.md`
- `.claude/**`
- `.github/**`
- scripts used by CI
- runtime entrypoints
- config templates

Do not move protected reference assets unless explicitly authorized:

- `docs/design/reference/wolfystock-reflect-linear-home-mockup.png`
- `apps/dsa-web/public/wolfystock-logo-mark.png`
- `apps/dsa-web/public/stocks.index.json`
- docs-referenced payment/banner/secret_config images

## 7. Auto-Merge Policy

### 7.1 Tasks That May Auto-Merge

Codex may auto-merge to `main` only if the task is low-risk and the prompt explicitly allows it.

Low-risk categories:

- docs-only cleanup
- assets-only cleanup
- tests-only hardening
- offline helper / pure service
- read-model-only helper
- additive contract with no runtime integration

Auto-merge requirements:

1. `main` is clean
2. `git pull --ff-only origin main` succeeds
3. merge has no conflicts
4. focused validation passes
5. `git diff --check` passes
6. `./scripts/release_secret_scan.sh` passes
7. final `git status --short --branch` is clean
8. branch/worktree cleanup succeeds or remaining cleanup issue is reported precisely

### 7.2 Tasks That Must Not Auto-Merge

Do not auto-merge:

- DB/storage/task queue changes
- provider/cache runtime changes
- LLM ledger/quota changes
- Backtest engine/API/persistence changes
- Portfolio accounting/broker changes
- auth/RBAC changes
- frontend visual changes
- any task with conflicts
- any task with unrelated failing tests unless user approves

For these tasks, push branch only and provide a final report.

## 8. Commit / Push Rules

### 8.1 Direct Main Tasks

For direct-main tasks:

```bash
git add <changed files>
git commit -m "<clear message>"
git push origin main
git status --short --branch
```

Only commit if validation passes.

### 8.2 Worktree Tasks

For worktree tasks:

```bash
git add <changed files>
git commit -m "<clear message>"
git push origin <branch>
git status --short --branch
```

Do not merge to main unless explicitly allowed.

### 8.3 Cleanup After Merge

After a branch is merged and pushed to `main`:

```bash
cd /Users/yehengli/daily_stock_analysis

git worktree remove /Users/yehengli/worktrees/<worktree-name>
git worktree prune
git branch -d codex/<branch-name>
git push origin --delete codex/<branch-name>

git worktree list
git status --short --branch
```

If a worktree is already gone or a branch/ref does not exist, report it as already cleaned, not as a task failure.

## 9. Validation Policy

Always run validation appropriate to the task.

### 9.1 Universal

```bash
git diff --check
./scripts/release_secret_scan.sh
git status --short --branch
```

### 9.2 Python Changes

Run focused tests and compile changed files:

```bash
python3 -m pytest <focused tests> -q
python3 -m py_compile <changed Python files>
```

### 9.3 Frontend Changes

```bash
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run build
```

### 9.4 Docs / Assets

```bash
python3 scripts/check_ai_assets.py
git diff --name-status
git diff --check
./scripts/release_secret_scan.sh
```

### 9.5 Provider / Market / Cache

Run relevant cache/freshness/provider tests and confirm:

- provider order unchanged
- API schemas unchanged
- stale/fallback/unavailable metadata remains truthful
- no live/fresh masquerading

### 9.6 Backtest

Run relevant:

- backtest contract tests
- golden tests
- rule service tests
- reopen/export tests if touched

Confirm:

- no engine math changes unless explicitly scoped
- no provider behavior changes
- no DB migration unless explicitly scoped
- no frontend changes unless explicitly scoped

### 9.7 Portfolio

Run relevant portfolio read-model/contract tests.

Confirm:

- no cash ledger mutation
- no holdings/lots/cost basis/P&L mutation
- no broker sync/import
- no order/trade execution

## 10. Final Report Format

Every Codex task must report:

```text
Task:
Branch:
Workspace:
Commit:
Push:

Files changed:
- ...

Behavior added:
- ...

Validation:
- command -> result
- command -> result

Confirmed unchanged:
- ...

Risks / notes:
- ...

Rollback:
- git revert <commit>

Final git status:
- ...
```

For read-only audits:

```text
Task:
Branch:
Workspace:

Files inspected:
- ...

Findings:
- ...

Recommended task split:
- ...

High-risk areas:
- ...

Validation:
- read-only only

Confirmation:
- no files modified
- no commits
- final git status
```

## 11. Prompt Compression Rule

Task prompts should not repeat this policy.

A good prompt should include only:

```text
Task:
Branch:
Workspace:

Read:
- AGENTS.md
- docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md

Goal:
...

Task-specific scope:
...

Task-specific constraints:
...

Validation:
...

Commit/push mode:
...
```

Do not paste long universal guardrails unless the task intentionally overrides this policy.

## 12. Current Strategic Direction

Until explicitly changed by the user:

- frontend visual work is paused
- single tasks run on `main`
- worktrees are for true parallelism or high-risk isolation
- current product-domain work should stay focused instead of jumping across unrelated modules
- backend priorities are:
  1. Backtest institutional research capability
  2. Alpha Factory reproducibility and factor research
  3. Portfolio research read models
  4. Market Intelligence reliability, only when needed
  5. Admin/Ops read-only diagnostics
