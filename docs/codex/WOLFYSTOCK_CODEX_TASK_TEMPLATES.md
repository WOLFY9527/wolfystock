# WolfyStock Codex Task Templates

Purpose: keep Codex prompts short while preserving guardrails.

Task labels should stay outside the code block when possible.

---

## 1. Minimum Task Metadata

Every execution prompt should include:

```text
Task ID: T-###
Task title:
Branch:
Workspace:
Mode:
```

Use the same Task ID in the final report.

---

## 2. Universal Header

Use unless the user explicitly requests same-main/manual-worktree mode:

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

---

## 3. Frontend Execution Task

```text
<universal header>

Task: <frontend implementation task>.

Read and obey:
- docs/codex/CODEX_FRONTEND_DESIGN_CONSTITUTION.md
- docs/codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md
- docs/codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md
- docs/codex/WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md

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

Copy/design discipline:
- Follow Linear-inspired low-noise direction.
- No card-first dashboard regression.
- No meta-explanatory UI copy.
- No raw debug/provider/schema leakage.
- Keep critical warnings honest but compact.

Validation:
- npm --prefix apps/dsa-web run test -- <focused tests> --run
- npm --prefix apps/dsa-web run build
- npm --prefix apps/dsa-web run check:design
- python3 scripts/check_frontend_design_constitution.py
- git diff --check
- bash scripts/release_secret_scan.sh
- browser verification routes/viewports: <routes>, 1440x1000, 1920x1080 if wide, 390x844

Commit:
- Stage only task-related files.
- Commit message: <message>
- Push if safe.

Final report:
- Use WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md.
```

---

## 4. Backend Execution Task

```text
<universal header>

Task: <backend implementation or guard task>.

Read and obey:
- docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md
- docs/codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md if provider/data-source near scope

Goal:
- <goal>

Allowed files:
- <files>

Forbidden files/domains:
- <domains>

Implementation:
1. <step>
2. <step>

Validation:
- python3 -m py_compile <changed files>
- python3 -m pytest <focused tests> -q
- git diff --check
- bash scripts/release_secret_scan.sh

Commit/push if safe.
```

---

## 5. Read-Only Decision/Audit Task

```text
<universal header>

Task: Read-only <topic> audit.

Goal:
- <what decision to make>

Hard rules:
- Read-only.
- Do not edit files.
- Do not create artifacts.
- Do not stage, commit, or push.

Read first:
- <task-specific docs/files>

Investigate:
- <commands/files>

Final response:
1. Preflight status
2. Findings
3. Risks
4. Recommendation
5. Safe future scope if any
6. No-write confirmation
7. Actual cwd, branch, base commit
```

---

## 6. Docs-Only Task

```text
<universal header>

Task: Docs-only <topic>.

Goal:
- <doc update goal>

Allowed files:
- <docs>

Forbidden:
- frontend implementation code
- backend implementation code
- package/lock files

Validation:
- git diff --check
- bash scripts/release_secret_scan.sh

Commit message:
- docs(...): <message>
```

---

## 7. Validation Profile Shortcuts

| Task class | Worker default | Pre-push escalation |
|---|---|---|
| frontend UI | focused tests + build + design guard + focused route Playwright | release secret scan; tsc only if shared types/routes changed |
| backend tests-only | focused pytest + diff check | release secret scan |
| backend endpoint mapping | py_compile + focused pytest + diff check | release secret scan + full ci gate if high-risk |
| provider/runtime audit | read-only inspection | if write-scoped, high-risk validation |
| docs-only | diff check | release secret scan |
