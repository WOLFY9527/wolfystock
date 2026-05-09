# WolfyStock Codex Final Report Template

Purpose: standardize Codex completion/blocker reports.

Every execution-class task should use this template unless the user asks otherwise.

## Success report

```text
Implemented, validated, committed, and pushed.

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

Behavior boundaries:
- No backend/API/runtime changes, if frontend-only
- No scanner scoring/selection/threshold changes
- No backtest calculation changes
- No portfolio accounting changes
- No provider runtime order/live-call path changes
- No AI prompt/decision logic changes
- No auth/RBAC/security changes
- No notification routing changes
- Fallback/stale/mock/synthetic live-labeling unchanged

Validation:
- <command> -> <result>
- <command> -> <result>
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
  - no forbidden internal terms
  - task-specific visual checks

Same-main shared worktree handling, if applicable:
- TARGET_GLOBS:
- Foreign dirty files left untouched:
- Staged files:
- Targeted diff/secret scan handling:

Deferred:
- <items explicitly not done>

Rollback:
git revert <hash>
```

## Blocker report

```text
Stopped at <phase>.

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
- did not stage
- did not commit
- did not push
- did not reset/revert/clean/stash

Required user decision:
1. <option>
2. <option>
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

Validation:
- report exists
- required headings present
- screenshots captured
- no secrets found
- no source files modified

Final git status:
<status>
```

## Required wording for protected domains

Use explicit confirmations:

```text
Confirmed unchanged:
- scanner scoring/selection/thresholds
- backtest calculations
- portfolio accounting
- provider runtime order/live-call paths
- AI prompts/decision logic
- auth/RBAC/security
- notification routing
- fallback/mock/synthetic live-labeling
```

## Browser verification minimum

For frontend tasks, include:
- desktop `1440x1000`
- mobile `390x844`
- routes verified
- port used
- whether preview/dev server was stopped
- whether shared `5173` or backend ports were left untouched
- console/page error status
- horizontal overflow status
- auth/mock limitations

## Dirty-file handling minimum

If same-main parallel work is present, include:
- foreign dirty files left untouched
- staged file list
- targeted `git diff --check`
- full or targeted secret scan result
- reason if full secret scan could not be used cleanly

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
