# WolfyStock Codex Execution Policy

> Condensed execution policy for Codex tasks in the WolfyStock repository.
> `AGENTS.md` remains the single source of truth for repository AI collaboration rules.
> This file is a prompt-compression policy, not a second rule source.
> Recommended location: `docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md`

## 0. Rule Priority

When Codex reads this file, apply the following priority order:

1. the current user task / Codex prompt
2. repository `AGENTS.md`
3. executable repository reality: code, scripts, CI, tests, package scripts, workflow files
4. this execution policy
5. user-level/global Codex or Superpowers rules
6. generic model defaults

If rules conflict, prefer the more specific repository/task rule.  
If the conflict involves safety, data truthfulness, credentials, protected domains, remote Git operations, or destructive cleanup, choose the conservative path and report the conflict.

## 1. Purpose

This file defines the default operating rules for Codex tasks in WolfyStock.  
Task prompts should reference this file instead of repeating common rules.

The goals are:

- maximize implementation quality
- minimize prompt length and repeated instructions
- reduce unnecessary worktrees, branches, merges, and cleanup
- prevent protected-domain regressions
- keep frontend visual work paused unless explicitly requested
- preserve modular boundaries and future maintainability
- keep validation proportional to the actual change surface

## 2. Default Task Execution Mode

### 2.1 Single Non-High-Risk Task

For a single non-parallel, non-high-risk task, run directly on `main`.

Use `main` when:

- only one Codex worker is running
- the task has a narrow, clear scope
- there is no expected file conflict
- the task does not fall into the high-risk categories below
- the user did not explicitly request a worktree

Default repository path on the user's Mac:

```text
/Users/yehengli/daily_stock_analysis
```

Before editing, Codex must verify:

```bash
cd /Users/yehengli/daily_stock_analysis
git fetch origin
git switch main
git pull --ff-only origin main
git status --short --branch
```

Stop and report if:

- the repository path does not exist
- the branch is not `main`
- `git pull --ff-only` fails
- the working tree is dirty
- the prompt declared a different branch or workspace

Do not create substitute directories such as `/Users/...` on non-Mac environments.  
If running in a different environment, use the repository/workspace path explicitly provided by the current prompt; otherwise stop and report the path mismatch.

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

If the prompt provides a different branch/workspace, the prompt wins.  
If the current branch/workspace does not match the prompt, stop before editing.

### 2.3 High-Risk Tasks

The following tasks should normally push a branch only and should not auto-merge unless the current prompt explicitly authorizes it:

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

For high-risk tasks, prefer a branch/worktree even if only one Codex worker is active.

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

Allowed only when the task-specific prompt explicitly permits:

- frontend type updates needed for backend API compatibility
- narrowly scoped frontend tests
- non-visual API client typing
- critical compile fixes caused by an approved backend contract change

When frontend is touched, run:

```bash
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run build
```

If visual frontend work is explicitly authorized:

- use the existing WolfyStock design language and approved reference mockup as the source of truth
- avoid uncontrolled card sprawl, auto-sized masonry layouts, generic dashboard chrome, or decorative filler copy
- use project frontend/design skills when available
- run browser verification if the environment supports it
- if browser verification is not possible, report the limitation explicitly

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
- merge
- rebase
- delete branches or worktrees
- run destructive commands

Read-only audit worktrees should remain available until the user has captured the final report, unless the prompt explicitly requests a report artifact and cleanup.

Read-only audit tasks must end with:

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

## 7. Auto-Merge / Auto-Integration Policy

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
6. `./scripts/release_secret_scan.sh` passes, or the script is absent and that absence is reported
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

### 7.3 Direct-Main Is Still Authorization-Gated

A direct-main task is not a branch auto-merge, but commit/push on `main` still requires the current prompt to authorize commit/push mode.

If the current prompt does not clearly authorize commit/push, make the change locally and report the exact next command instead of committing.

## 8. Commit / Push Rules

All commits must follow repository `AGENTS.md`:

- commit message in English
- no `Co-Authored-By`
- stage only files directly related to the task

### 8.1 Direct Main Tasks

For direct-main tasks, only when commit/push mode is explicitly authorized:

```bash
git add <changed files>
git commit -m "<clear English message>"
git push origin main
git status --short --branch
```

Only commit if validation passes.

### 8.2 Worktree Tasks

For worktree tasks, only when commit/push mode is explicitly authorized:

```bash
git add <changed files>
git commit -m "<clear English message>"
git push origin <branch>
git status --short --branch
```

Do not merge to main unless explicitly allowed.

### 8.3 Cleanup After Merge

After a branch is merged and pushed to `main`, and cleanup is authorized:

```bash
cd /Users/yehengli/daily_stock_analysis

git worktree remove /Users/yehengli/worktrees/<worktree-name>
git worktree prune
git branch -d <branch>
git push origin --delete <branch>

git worktree list
git status --short --branch
```

Use the full branch name, for example `codex/t217e-backtest-parameter-stability`.  
Do not accidentally produce `codex/codex/...`.

If a worktree is already gone or a branch/ref does not exist, report it as already cleaned, not as a task failure.

## 9. Validation Policy

Always run validation appropriate to the task.  
Do not run unrelated expensive tests only to appear thorough.

### 9.1 Universal Write-Task Checks

For write tasks, run:

```bash
git diff --check
./scripts/release_secret_scan.sh
git status --short --branch
```

If `./scripts/release_secret_scan.sh` is missing or not executable, report that explicitly and continue with available validation unless the current task requires secret-scan enforcement.

### 9.2 Python Changes

Run focused tests and compile changed files:

```bash
python3 -m pytest <focused tests> -q
python3 -m py_compile <changed Python files>
```

If the repository convention or active virtual environment uses `python` instead of `python3`, use the repository-supported command and report it.

### 9.3 Frontend Changes

```bash
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run build
```

For test-only or type-only frontend tasks, add the focused test command if one exists.

### 9.4 Docs / Assets

For normal docs/assets changes:

```bash
git diff --name-status
git diff --check
./scripts/release_secret_scan.sh
```

For AI governance assets, also run:

```bash
python3 scripts/check_ai_assets.py
```

AI governance assets include:

- `AGENTS.md`
- `CLAUDE.md`
- `.github/copilot-instructions.md`
- `.github/instructions/**`
- `.claude/skills/**`
- `docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md`

### 9.5 Provider / Market / Cache

Run relevant cache/freshness/provider tests and confirm:

- provider order unchanged unless explicitly scoped
- API schemas unchanged unless explicitly scoped
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
- no provider behavior changes unless explicitly scoped
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
  or N/A if no commit was created

Final git status:
- ...
```

Use `N/A` for Commit, Push, Rollback, or Workspace fields when they do not apply.

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

Task prompts should always make these fields explicit when relevant:

- task id
- branch
- workspace
- allowed write scope
- forbidden scope
- validation
- commit/push mode
- auto-merge/cleanup mode

## 12. Current Strategic Direction

Until explicitly changed by the user or a newer task ledger:

- frontend visual work is paused
- single non-high-risk tasks run on `main`
- worktrees are for true parallelism or high-risk isolation
- current product-domain work should stay focused instead of jumping across unrelated modules
- backend priority order is a default planning heuristic, not a hard rule:
  1. Backtest institutional research capability
  2. Alpha Factory reproducibility and factor research
  3. Portfolio research read models
  4. Market Intelligence reliability when current tasks require it
  5. Admin/Ops read-only diagnostics

The current user prompt and active task ledger override this strategic direction.
