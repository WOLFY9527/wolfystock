# WolfyStock Codex Task Templates

Purpose: keep user prompts short while preserving WolfyStock guardrails.

Task labels should stay outside the code block.

## Minimum Task Metadata

Every execution prompt should include:

```text
Task ID:
Task title:
Branch:
Workspace:
Mode:
```

Default mode for normal Codex App tasks is `CODEX-ISOLATED`. Use `SERIAL-MAIN` only when the prompt explicitly requests the shared main worktree.

Use the same Task ID in the final report.

## Universal Header

Use this header unless the user explicitly requests same-main/manual-worktree mode:

```text
Use the Codex App isolated task workspace.
Use local environment: WolfyStock Fast.
Base from latest origin/main.

Do not use or checkout long-lived manual worktree branches.
Do not checkout codex/frontend-lane or codex/backend-lane.
Do not create or use manual worktrees under /Users/yehengli/worktrees.
Do not run pip install, npm install, npm ci, or npm audit fix unless dependency/lock files changed and you explicitly report why.
Report actual cwd, branch, and base commit in the final response.

Read and obey:
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md
- docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
```

## Validation Profile Shortcuts

| Task class | Worker default | Landing / pre-push escalation |
| --- | --- | --- |
| frontend shell/UI | focused tests + build + design guard + focused browser proof | `bash scripts/release_secret_scan.sh`; add `tsc --noEmit` only if routes/types/shared interfaces changed |
| backend tests-only guard | focused pytest guard coverage + `git diff --check` | `bash scripts/release_secret_scan.sh`; full gate only if task stopped being tests-only |
| backend endpoint mapping | `python3 -m py_compile` + focused pytest + `git diff --check` | `bash scripts/release_secret_scan.sh` + full gate |
| provider/runtime audit | read-only inspection | re-scope before any write |
| docs-only | command/file-name consistency + `git diff --check` | `bash scripts/release_secret_scan.sh` before commit/push |

`./scripts/ci_gate_fast.sh` is optional iteration feedback. It does not replace task-scoped checks and is not landing proof.

## Read-Only Decision Task

```text
<universal header>

Task: Read-only <topic> triage / inventory.

Goal:
- <what decision to make>
- <what future execution target to evaluate>

Hard rules:
- Read-only.
- Do not edit files.
- Do not create artifacts.
- Do not stage, commit, or push.
- Final output in Codex chat only.

Read first:
- <task-specific docs/files>

Investigation:
- <commands>

Evaluate:
- <candidates>

Decision policy:
- <what counts as safe>
- <what is not allowed>

Final response:
1. Preflight status
2. Current map
3. Candidate table
4. Recommendation
5. Safe future scope if any
6. Tasks not recommended
7. No-write confirmation
8. Actual cwd, branch, base commit, whether main was touched
```

## Frontend Execution Task

```text
<universal header>

Task: <frontend implementation task>.

Read and obey:
- docs/frontend/README.md
- docs/frontend/visual-system.md
- docs/frontend/validation-playbook.md

Goal:
- <3-6 line goal>

Scope:
Change:
- <allowed files/routes>

Do not change:
- <task-specific protected domains>
- backend/API/provider/runtime unless explicitly scoped
- global CSS unless explicitly scoped

Implementation:
1. <step>
2. <step>
3. <step>

Validation:
- npm --prefix apps/dsa-web run test -- <focused tests>
- npm --prefix apps/dsa-web run build
- npm --prefix apps/dsa-web run check:design
- `npx --prefix apps/dsa-web tsc --noEmit --pretty false --project apps/dsa-web/tsconfig.app.json` only if routes/types/shared interfaces changed
- ./scripts/release_secret_scan.sh before commit/push
- browser verification routes/viewports: <routes>, 1440x1000 and 390x844

Commit:
- Stage only task-related files.
- Commit message: <message>
- Push only if the prompt authorizes push and validation passes.

Final report:
- use WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
- include task-specific route/visual observations
```

## Backend Execution Task

```text
<universal header>

Task: <backend implementation or guard task>.

Read and obey:
- docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md
- <domain-specific doc if any>

Goal:
- <3-6 line goal>

Scope:
Change:
- <allowed files/modules>

Do not change:
- <task-specific protected semantics>
- provider runtime / AI routing / auth / storage unless explicitly scoped

Implementation:
1. <step>
2. <step>
3. <step>

Validation:
- python3 -m py_compile <changed python files, if source touched>
- python3 -m pytest -q <focused tests>
- git diff --check
- ./scripts/release_secret_scan.sh before commit/push

Commit:
- Stage only task-related files.
- Commit message: <message>
- Push only if the prompt authorizes push and validation passes.

Final report:
- use WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
```

## Docs-Only Task

```text
<universal header>

Task: <docs-only update>.

Rules:
- Do not edit runtime source.
- Do not stage unrelated dirty files.
- Preserve exact filenames and command paths.
- Keep docs concise and non-duplicative.

Validation:
- git diff --check -- <changed-doc-files>
- bash scripts/release_secret_scan.sh
```

## Compact Surface Delta Task

```text
Use the currently selected Codex worktree/branch.

Read and obey:
- docs/codex/WOLFYSTOCK_SURFACE_MAP.md
- docs/codex/WOLFYSTOCK_CODEX_DISCOVERY_PROTOCOL.md
- docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md
- docs/codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md
- docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md
- docs/codex/NO_ADVICE_REGRESSION_GUARDS.md

Surface:
Change type:
Goal:
Contract delta:
Risk domain:
Validation profile:
Commit:
```

Validation:
Docs-only profile:

- `git diff --check`
- `bash scripts/release_secret_scan.sh --base-ref origin/main`

Commit:
`docs(codex): add surface map discovery protocol`
