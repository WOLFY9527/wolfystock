# WolfyStock Codex Task Templates

Purpose: keep user prompts short while preserving the WolfyStock guardrails.

Task labels should stay outside the code block.

## Universal header

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
- docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
```

## Read-only decision task

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

## Frontend execution task

```text
<universal header>

Task: <frontend implementation task>.

Read and obey:
- docs/codex/WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md
- docs/codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md
- docs/codex/WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md
- CODEX_FRONTEND_DESIGN_CONSTITUTION.md

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
- ./scripts/release_secret_scan.sh
- browser verification routes/viewports: <routes>, 1440x1000 and 390x844

Commit:
- Stage only task-related files.
- Commit message: <message>
- Push if safe.

Final report:
- use WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
- include task-specific chunk/route/visual observations
```

## Backend execution task

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
- ./scripts/release_secret_scan.sh

Commit:
- Stage only task-related files.
- Commit message: <message>
- Push if safe.

Final report:
- use WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
- include protected-domain confirmations
```

## Docs-only / tests-only task

```text
<universal header>

Task: <docs-only or tests-only guard task>.

Scope:
Change:
- <allowed docs/tests>

Do not change:
- runtime source
- frontend source
- backend services
- package/lock files

Validation:
- <focused docs/test commands>
- git diff --check
- ./scripts/release_secret_scan.sh

Commit:
- Stage only task files.
- Commit message: <message>
- Push if safe.

Final report:
- use WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
- state no runtime behavior changed
```

## Report-only audit task

```text
<universal header>

Task: Report-only audit for <topic>.

Rules:
- Prefer chat-only output when possible.
- If an artifact is explicitly required, write under an ignored artifacts path and state kept/deleted rationale.
- Do not edit source/tests/docs unless explicitly scoped.
- Do not commit report-only artifacts unless explicitly requested.

Final report:
- use report-only section in WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
```
