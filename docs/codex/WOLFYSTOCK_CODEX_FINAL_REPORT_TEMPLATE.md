# WolfyStock Codex Final Report Template

Purpose: standardize Codex completion, blocker, read-only, and report-only responses.

Execution-class tasks should use this template unless the user asks otherwise.

## Progress header

Start every response to the user with a short progress update:

```text
Progress update:
- Completed/blocked:
- Current git state:
- Current phase:
- Continue or stop:
- Next priority:
```

## Success report

```text
Implemented, validated, committed, and pushed.

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
- <file>

What changed:
- <user-visible / backend-visible changes>
- <important implementation details>

Boundary impact:
- domains touched:
- platform/contracts touched:
- shared UI touched:
- API/runtime touched:

Reuse/deletion:
- reused existing patterns:
- deleted/consolidated patterns:
- new abstractions added and why:
- wrapper check: added wrapper yes/no; if yes, why not debt and deletion/migration path
- net file count change:
- net concept/primitive count change:

Behavior boundaries:
Confirmed unchanged unless explicitly scoped:
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
- DuckDB/PostgreSQL source-of-truth behavior
- API response shapes/stored contract versions
- fallback/mock/synthetic live-labeling

Validation:
- <command> -> <result>
- <command> -> <result>
- <command> -> <result>

Browser verification, if frontend:
- Method:
- Route(s):
- Viewports:
- Port(s):
- Shared servers left untouched:
- Auth/API mocking limitations:
- Checks:
  - no horizontal overflow
  - no console/page errors
  - no forbidden internal terms
  - no raw/debug/provider/schema leakage
  - task-specific visual checks

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

Rollback:
git revert <hash>
```

## Blocker report

```text
Stopped at <phase>.

Actual workspace:
- cwd:
- branch:
- base commit:

Reason:
<clear blocker>

Preflight / validation run:
- <command> -> <result>
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

## Read-only decision report

```text
Read-only task completed.

Actual workspace:
- cwd:
- branch:
- base commit:

Preflight:
- git status:
- local ahead status:
- dirty/staged status:

Decision summary:
- recommendation:
- safe future execution target, if any:
- tasks not recommended:

Evidence:
- files inspected:
- tests/docs considered:
- main risks:

No-write confirmation:
- no files modified
- no artifacts created
- nothing staged/committed/pushed
```

## Report-only audit report

```text
Report created:
<artifact path>

Scope:
- routes/files audited
- viewports
- method

Top blockers:
1. ...
2. ...
3. ...

Top next tasks:
1. ...
2. ...
3. ...

Artifacts:
- screenshots:
- JSON:
- markdown:
- kept/deleted rationale:

Validation:
- report exists
- required headings present
- screenshots captured if scoped
- no secrets found
- no source files modified

Final git status:
<status>
```

## When not pushed

If committed but not pushed:

```text
Committed locally but not pushed.

Commit:
<hash>

Push blocker:
<reason>

Final git status:
<status>
```

If not committed:

```text
No commit was created.
No push was performed.
```
