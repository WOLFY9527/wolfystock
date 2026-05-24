# WolfyStock Codex Execution Policy

> Compact execution policy for Codex tasks in the WolfyStock repository.
> `AGENTS.md` remains the repository AI collaboration source of truth.
> This file is a prompt-compression summary, not a replacement for the core guard/runtime docs.
> Recommended location: `docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md`

## 0. Rule Priority

Apply rules in this order:

1. current user task / Codex prompt
2. repository `AGENTS.md`
3. executable repository reality: code, scripts, CI, tests, package scripts, workflow files
4. `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
5. `docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`
6. this execution-policy summary
7. user-level/global Codex or Superpowers rules
8. generic model defaults

If rules conflict, prefer the more specific repository/task rule. If the conflict involves safety, data truthfulness, credentials, protected domains, remote Git operations, or destructive cleanup, choose the conservative path and report the conflict.

## 1. Purpose

Task prompts should reference stable docs instead of repeating long universal guardrails.

This file exists to keep GPT-authored Codex prompts compact while preserving:

- implementation quality
- bounded scope
- protected-domain safety
- proportional validation
- clear commit/push authorization
- consistent final reports

For detailed task behavior, read and obey:

```text
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md
- docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
```

## 2. Default Task Execution Mode

### 2.1 Default: CODEX-ISOLATED

Normal Codex App tasks should use `CODEX-ISOLATED` mode.

Default assumptions:

- use the Codex App isolated task workspace
- use local environment `WolfyStock Fast`
- base from latest `origin/main`
- do not create or use manual worktrees under `/Users/yehengli/worktrees`
- do not work directly in `/Users/yehengli/daily_stock_analysis`
- report actual `cwd`, branch, base commit, commit, push status, and final git status

The current prompt may override this only by explicitly setting a different mode.

### 2.2 Shared Main Exception: SERIAL-MAIN

Use `SERIAL-MAIN` only when the user explicitly asks to work directly in the shared main worktree:

```text
Workspace: /Users/yehengli/daily_stock_analysis
Branch: main
Mode: SERIAL-MAIN
```

When using `SERIAL-MAIN`, read and obey:

```text
- docs/codex/WOLFYSTOCK_SHARED_MAIN_WORKTREE_PROTOCOL.md
```

The prompt must declare target globs, stage allowlist, foreign dirty policy, and validation scope.

### 2.3 Parallel Work: WORKTREE-WORKER

Use manual git worktrees only for true parallelism, high-risk isolation, or when the prompt explicitly requests the mode.

The prompt must declare:

```text
Branch:
Workspace:
Mode: WORKTREE-WORKER
```

Stop before editing if the actual path, branch, git root, or base does not match the prompt.

### 2.4 Read-Only Work: READ-ONLY-AUDIT

Use `READ-ONLY-AUDIT` for audits, design checks, inventories, post-merge risk maps, and planning tasks.

Read-only tasks must not:

- edit files
- create artifacts unless explicitly requested
- stage files
- commit
- push
- merge
- rebase
- delete branches or worktrees
- run destructive commands

Read-only audit worktrees should remain available until the user has captured the final report, unless the prompt explicitly requests a report artifact and cleanup.

## 3. High-Risk Tasks

The following tasks should normally use a branch/worktree and should not auto-merge unless the current prompt explicitly authorizes it:

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

For high-risk tasks, prefer decision/audit first unless the implementation path is already explicit and testable.

## 4. Frontend Freeze

Frontend visual work is paused by default.

Do not start frontend visual work unless the user explicitly requests it.

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

When frontend work is explicitly authorized, follow the WolfyStock frontend visual system and approved Linear-style reference mockup. Avoid uncontrolled card sprawl, auto-sized masonry layouts, generic dashboard chrome, pure-black gutters, ornamental filler copy, and raw provider/schema/debug leakage.

## 5. Product-Domain Planning

Prefer product-domain batches over scattered module hopping.

Common clusters:

- Market Intelligence: Market Overview, Liquidity Monitor, Rotation Radar
- Backtest Research: contracts, walk-forward/OOS, transaction costs, parameter stability, factor bridge
- Alpha Factory: factor observations, metrics, neutralization, exposure, reproducibility, experiment manifests
- Portfolio Research: construction read model, rebalance read model, factor exposure, risk attribution, stress/VaR/benchmark attribution

Avoid mixing unrelated domains in one batch unless one task is read-only or housekeeping.

## 6. Task Sizing

Do not over-split a coherent implementation into tiny helper/test/docs/export tasks if one bounded task can safely complete it.

Split tasks when:

- they touch different protected domains
- they would create merge conflicts
- one task requires audit before implementation
- engine math, storage, provider runtime, or accounting behavior may change
- one task can proceed safely while another must remain serial

Use read-only audits only when the implementation path is uncertain or high-risk. Do not audit small, obvious additive helpers as busywork.

## 7. Protected Domains Summary

Detailed backend protected-domain rules live in:

```text
- docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md
```

Provider/quota rules live in:

```text
- docs/codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md
```

Backtest universe rules live in:

```text
- docs/codex/WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md
```

Core protected principles:

- never make fallback/stale/partial/unavailable/synthetic data appear live or fresh
- do not change provider order or live-call paths unless explicitly scoped
- do not mutate portfolio accounting state unless explicitly scoped
- do not change backtest engine math unless explicitly scoped
- do not change LLM model/provider fallback order, quota semantics, prompts, thresholds, or final advice logic unless explicitly scoped
- do not relax auth/RBAC/security
- do not move protected root governance files or reference assets without explicit approval

## 8. Commit / Push / Auto-Integration

All remote Git actions are authorization-gated by the current prompt.

Execution-class tasks may commit and push only when the prompt's `Commit` section authorizes it.

Rules:

- stage only task-related files explicitly
- never use `git add .`
- commit message must be English
- do not add `Co-Authored-By`
- push only the prompt-named target branch
- do not auto-merge unless the prompt explicitly allows it
- do not delete branches or worktrees unless cleanup is explicitly authorized

If the prompt does not clearly authorize commit/push, make the change locally and report the exact next command instead of committing.

## 9. Validation Policy

Always run validation appropriate to the task. Do not run unrelated expensive tests only to appear thorough.

Universal write-task checks:

```bash
git diff --check
./scripts/release_secret_scan.sh
git status --short --branch
```

Docs-only tasks:

```bash
git diff --check -- <changed-doc-files>
./scripts/release_secret_scan.sh
git status --short --branch
```

AI governance asset changes should also run:

```bash
python3 scripts/check_ai_assets.py
```

AI governance assets include:

- `AGENTS.md`
- `CLAUDE.md`
- `.github/copilot-instructions.md`
- `.github/instructions/**`
- `.claude/skills/**`
- `docs/codex/**`

Frontend changes should follow the standard guard and frontend validation docs.

Backend/source changes should run focused compile/test checks and escalate to full gates only for broad/high-risk runtime changes.

## 10. Final Report

Use:

```text
- docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
```

Every execution-class final report should include:

- task ID and title
- ledger status
- actual branch and workspace
- commit and push status when applicable
- files changed
- behavior added
- validation commands and results
- protected domains confirmed unchanged
- unrelated dirty files left untouched
- risks / notes
- rollback command, or `N/A` if no commit was created
- final `git status --short --branch`

Read-only audits should use the read-only final report format and confirm no files were modified, staged, committed, or pushed.

## 11. Prompt Compression Rule

Task prompts should not repeat this policy.

A good prompt should include only task-specific deltas:

```text
Task ID:
Task title:
Branch:
Workspace:
Mode:

Read and obey:
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md
- docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md

Goal:
Allowed final diff:
Forbidden final diff:
Implementation requirements:
Validation:
Browser verification:
Commit:
Final report:
```

Do not paste long universal guardrails unless the task intentionally overrides this policy.

## 12. Current Strategic Direction

Until explicitly changed by the user or a newer task ledger:

- frontend visual work is paused
- default Codex App work uses `CODEX-ISOLATED`
- `SERIAL-MAIN` is an explicit shared-main exception
- manual worktrees are for true parallelism or high-risk isolation
- current product-domain work should stay focused instead of jumping across unrelated modules
- backend priority order is a planning heuristic, not a hard rule:
  1. Backtest institutional research capability
  2. Alpha Factory reproducibility and factor research
  3. Portfolio research read models
  4. Market Intelligence reliability when current tasks require it
  5. Admin/Ops read-only diagnostics

The current user prompt and active task ledger override this strategic direction.
