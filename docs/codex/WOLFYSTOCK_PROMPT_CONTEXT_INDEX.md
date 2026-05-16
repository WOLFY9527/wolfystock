# WolfyStock Codex Prompt Context Index

Purpose: keep Codex prompts short without losing safety or quality.

Task prompts should reference these stable docs instead of repeating long boilerplate.

---

## Always Read for Implementation Tasks

```text
Read and obey:
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md
- docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
```

---

## Prompt Templates

Use:

- `docs/codex/WOLFYSTOCK_CODEX_TASK_TEMPLATES.md`

Task labels stay outside the code block:

```text
任务类型：执行类（适合 Codex 5.4）
```

or:

```text
任务类型：决策类（建议 Codex 5.5）
```

---

## Task Type Index

### Read-only architecture / triage

Read:

- `WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`
- `WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`
- task-specific docs/files

Rules:

- no edits;
- no artifacts;
- no commit/push;
- final decision only.

### Frontend UI implementation

Read:

- `WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`
- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md`
- `WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`
- `WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md`
- `WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`

### Admin / operator UI implementation

Read:

- frontend UI implementation docs above;
- `WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md` if API/auth/provider/admin capabilities are near scope.

### Backend boundary / service implementation

Read:

- `WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`
- `WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`
- `WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`
- relevant tests and service files.

### Backend provider / quota / data-source work

Read:

- `WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`
- `WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md`
- `WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`

### Backtest universe work

Read:

- `WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`
- `WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md`
- `WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`

### Docs-only or tests-only guard work

Read:

- `WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`
- `WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`
- relevant target docs/tests.

---

## What Should Stay in Each Prompt

Do not rely only on docs for task-specific facts. Each prompt must still include:

- task goal;
- allowed files/surfaces;
- forbidden task-specific domains;
- exact implementation scope;
- exact validation commands;
- browser routes/viewports if frontend;
- commit/no-commit policy;
- special stop conditions.

---

## What Should Not Be Repeated

Do not repeat long lists from these docs unless the task is high-risk:

- general git safety;
- protected-domain list;
- frontend design constitution;
- Playwright invocation rules;
- final report template;
- artifact hygiene;
- wrapper/deletion rules;
- ci_gate policy.

---

## Codex App Local Environment

Default prompts should assume:

```text
Use the Codex App isolated task workspace.
Use local environment: WolfyStock Fast.
Base from latest origin/main.
```

Use shared main only when the user explicitly requests it.
