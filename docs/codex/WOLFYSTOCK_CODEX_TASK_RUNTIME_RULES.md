# WolfyStock Codex Task Runtime Rules

Purpose: keep Codex prompts compact without losing operational constraints. Task prompts may reference this file instead of repeating SOP.

---

## 1. Core Operating Rules

1. Treat every task as bounded by its prompt, this file, and referenced guard/design docs.
2. Do not expand scope. If the prompt says audit, do not edit. If it says shell/layout only, do not change behavior.
3. Prefer small, reviewable changes over broad refactors.
4. Stage only task-related files.
5. Never use `git add .`.
6. Push only the task branch or `main` when the prompt explicitly uses same-main mode.
7. Do not commit unrelated formatting, lockfile, config, generated, or cache changes.
8. If workspace, branch, or git root does not match the prompt, stop and report.
9. If a protected domain appears necessary, stop and report the risk instead of modifying it.
10. If validation cannot run, report the exact command attempted and blocker output.

---

## 2. Model / Reasoning Selection

The caller selects model and reasoning in Codex UI or the task title.

Default policy:

```text
Execution tasks: 5.4 + high
Decision / architecture / high-risk audit tasks: 5.5 + xhigh
```

Prompts should be model-agnostic and focus on scope.

---

## 3. Required Prompt Fields

Execution prompts should include:

```text
Task ID:
Task title:
Branch:
Workspace:
Mode:
Read:
Goal:
Allowed files:
Forbidden files:
Implementation:
Protected semantics:
Validation:
Browser:
Final report:
```

Omit sections only when not applicable.

---

## 4. Task Ledger Statuses

Use one exact status:

```text
RUNNING
READY TO LAND
LANDED
NO-OP
BLOCKED
PLANNED
```

---

## 5. Execution Modes

### SERIAL-MAIN

Use when the task is a single safe task on `main`.

Rules:

```text
- Work only in /Users/yehengli/daily_stock_analysis
- Stay on main unless prompt says otherwise
- Do not create a worktree
```

### WORKTREE-WORKER

Use only for true parallel work.

Rules:

```text
- Work only in the workspace path given by the prompt
- Branch must match the branch given by the prompt
- Stop if branch/path mismatch
- Push only this branch
```

### CODEX-APP-ISOLATED

Default for Codex App tasks.

Rules:

```text
- Use isolated task workspace
- Base from latest origin/main
- Do not create manual worktrees
- Report actual cwd/branch/base commit
```

### READ-ONLY-AUDIT

Use for audits, design checks, inventories, and risk mapping.

Rules:

```text
- Do not edit files
- Do not create artifacts
- Do not commit
- Do not push
- Do not run destructive commands
```

---

## 6. Parallelization Rules

Parallelize only when workers do not write overlapping files or semantically coupled domains.

Safe examples:

```text
one UI page + one backend read-only audit
two UI pages with no shared files/components
a read-only audit beside one write task
```

Unsafe examples:

```text
multiple workers editing the same page
multiple workers editing shared primitives/global CSS
one worker changing provider runtime while another changes analysis semantics
multiple workers in portfolio accounting or options ranking
```

If not clearly safe, serialize.

---

## 7. Protected Domains

Unless the prompt explicitly scopes the domain and names allowed files, do not modify:

- scanner scoring/ranking/sorting/selection/result order/API semantics;
- portfolio accounting/cash/holdings/P&L/FX/cost basis/broker sync;
- provider runtime order/live-call semantics/fallback/MarketCache TTL/SWR;
- options ranking/gates/scoring/payoff/no-trade policy;
- backtest calculations/fills/costs/metrics/stored result semantics;
- auth/RBAC/security;
- API response shapes/stored contract versions;
- AI prompts/model routing/decision semantics.

Presentation-only tasks may change UI rendering when allowed, but must preserve underlying semantics.

---

## 8. Frontend Runtime Rules

Read:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md`
- `WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`
- `WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md`

Current direction:

```text
Linear-inspired professional stock research OS
low-noise product software
board/list/table/report surfaces before cards
progressive disclosure
```

Avoid:

- card-first dashboards;
- ghost-glass/card-heavy regressions;
- raw debug/provider/schema text in user UI;
- meta-explanatory copy;
- excessive side gutters;
- native-looking controls;
- unbounded chip/action clutter;
- horizontal overflow.

Frontend shell/global primitive changes require explicit scope. Page work should not silently rewrite global CSS or app shell.

---

## 9. Backend Boundary Rules

Backend refactors must preserve public API behavior unless the prompt explicitly states a contract change.

Endpoint mapping:

- service layer returns internal models/domain data;
- endpoint layer owns API response schemas;
- public response shapes and aliases remain stable;
- add/adjust focused contract tests when possible.

Tests-only guards:

- do not alter runtime code;
- freeze current boundary/import inventory;
- make failure messages actionable.

---

## 10. Validation Matrix

Run focused validation first.

| Task class | Worker default | Pre-push / landing |
|---|---|---|
| frontend UI | focused tests, build, design guard, focused Playwright | release secret scan; add tsc if shared types/routes changed |
| docs-only | doc consistency, file names, `git diff --check` | release secret scan before push |
| backend tests-only | focused pytest, `git diff --check` | release secret scan |
| backend endpoint | py_compile, focused pytest, contract tests | release secret scan + full ci gate if high-risk |
| provider/runtime audit | read-only inspection | if write-scoped, treat high-risk |

`ci_gate_fast.sh` is optional iteration evidence, not landing proof.

---

## 11. Browser Verification

Frontend visual changes require browser proof unless docs/tests-only.

Viewports:

- `1440x1000`
- `1920x1080` for wide workspaces
- `390x844`

Checks:

- primary task visible above fold;
- no horizontal overflow;
- no console/page errors;
- no raw debug/provider/schema leakage;
- no meta-explanatory UI copy;
- route matches template;
- screenshots or observations included in final report.
