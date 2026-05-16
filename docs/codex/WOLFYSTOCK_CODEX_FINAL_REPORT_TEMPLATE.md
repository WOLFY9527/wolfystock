# WolfyStock Codex Final Report Template

Purpose: standardize Codex completion, blocker, read-only, and report-only responses.

---

## 1. Ledger-Required Fields

Every execution-class final report should include:

```text
Task ID: T-###
Task title: <title>
Ledger status: RUNNING | READY TO LAND | LANDED | NO-OP | BLOCKED | PLANNED
Branch: <branch>
Workspace: <cwd>
```

Success reports should state commit, push status, files changed, validation, risk, and rollback.

---

## 2. Success Report

```text
Implemented, validated, committed, and pushed.

Task ID: <T-###>
Task title: <title>
Ledger status: READY TO LAND | LANDED

Actual workspace:
- cwd: <path>
- branch: <branch>
- base commit: <hash>

Commit:
<hash> <message>

Push:
<remote/branch result>

Final branch status:
<git status --short --branch>

Files changed:
- <file>

What changed:
- <user-visible / backend-visible changes>
- <important implementation details>

Boundary impact:
- domains touched:
- shared UI touched:
- API/runtime touched:
- protected domains confirmed unchanged:

Reuse/deletion:
- reused existing patterns:
- deleted/consolidated patterns:
- new abstractions added and why:
- wrapper check:
- net file/concept count change:

Behavior boundaries confirmed unchanged unless scoped:
- scanner scoring/selection/thresholds/ranking/sorting
- rotation score/stage/fund-flow semantics
- options ranking/gates/recommendation policy
- backtest calculations/fills/costs/metrics
- portfolio accounting/cash/holdings/P&L/FX/cost basis
- provider runtime order/live-call paths/fallback semantics
- MarketCache TTL/SWR/cold-start behavior
- AI prompts/routing/model/decision logic
- auth/RBAC/security
- notification routing
- database source-of-truth behavior
- API response shapes/stored contract versions
- fallback/mock/synthetic live-labeling

Validation:
- <command> -> <result>

Browser verification, if frontend:
- Method:
- Route(s):
- Viewports:
- Port(s):
- Auth/API mocking limitations:
- Checks:
  - no horizontal overflow
  - no console/page errors
  - primary task visible above fold
  - route follows template
  - no forbidden internal terms
  - no raw/debug/provider/schema leakage
  - no meta-explanatory UI copy
  - task-specific visual checks
- Screenshots:

Artifact hygiene:
- generated artifacts kept:
- generated artifacts deleted:
- markdown reports created: yes/no

ci_gate:
- result or reason skipped/deferred:

Final hygiene:
- final git status:
- foreign dirty files:
- secrets printed/committed: no
- unrelated files touched/staged/committed: no

Risks:
- <remaining risk or `none beyond normal review`>

Rollback:
git revert <hash>
```

---

## 3. Blocker Report

```text
Stopped at <phase>.

Task ID: <T-###>
Task title: <title>
Ledger status: BLOCKED

Actual workspace:
- cwd:
- branch:
- base commit:

Reason:
<clear blocker>

Preflight / validation run:
- <command> -> <result>

Current git status:
<git status --short --branch>

Task-related dirty files:
- <file>

Unrelated dirty files:
- <file>

What I did not do:
- did not edit unrelated files
- did not stage unrelated files
- did not commit
- did not push
- did not reset/revert/clean/stash

Safe next options:
1. <option>
2. <option>
```

---

## 4. Read-Only Decision Report

```text
Read-only task completed.

Task ID: <T-###>
Task title: <title>
Ledger status: PLANNED

Actual workspace:
- cwd:
- branch:
- base commit:

Preflight:
- git status:

Findings:
1. <finding>

Recommendation:
- <recommendation>

Safe future write scope:
- <scope>

No-write confirmation:
- files edited: none
- staged: none
- committed: no
- pushed: no
```
