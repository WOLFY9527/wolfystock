# WolfyStock Codex Prompt Context Index

Purpose: keep Codex prompts short without losing safety or quality.

Task prompts should reference these stable docs instead of repeating long boilerplate.

## Always Read For Implementation Tasks

```text
Read and obey:
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md
- docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
```

## Prompt Templates

Use:

- `WOLFYSTOCK_CODEX_TASK_TEMPLATES.md`
- `WOLFYSTOCK_SURFACE_MAP.md`
- `WOLFYSTOCK_CODEX_DISCOVERY_PROTOCOL.md`

Task labels stay outside the code block:

```text
任务类型：执行类（适合 Codex 5.4）
```

or:

```text
任务类型：决策类（建议 Codex 5.5）
```

## Task Type Index

### Surface-Aware Discovery

When a prompt names a product surface, use:

- `WOLFYSTOCK_SURFACE_MAP.md` for stable endpoint/schema/service/client/page/test lookup
- `WOLFYSTOCK_CODEX_DISCOVERY_PROTOCOL.md` for inspection order, stop rules, and guard-doc routing

This lets future prompts stay compact and specify only:

- `Surface`
- `Change type`
- `Goal`
- `Contract delta`
- `Validation profile`
- `Commit`

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
- `docs/frontend/README.md`
- `docs/frontend/visual-system.md`
- `docs/frontend/validation-playbook.md`
- `WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`

### Admin / operator UI implementation

Read frontend UI docs above plus:

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
- `WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`
- relevant target docs/tests.

## What Should Stay In Each Task Prompt

Do not rely only on docs for task-specific facts. Each prompt must still include:

- task goal;
- allowed files/surfaces;
- forbidden task-specific domains;
- exact implementation scope;
- exact validation commands;
- browser routes/viewports if frontend;
- commit message or no-commit policy;
- special stop conditions.

## What Should Not Be Repeated In Prompts

Do not repeat long lists from these docs unless the task is high-risk:

- general git safety;
- full protected-domain list;
- frontend visual constitution;
- Playwright invocation rule;
- final report template;
- artifact hygiene;
- wrapper/deletion rules;
- ci_gate policy.

## Frontend Visual Authority Order

For UI work:

1. approved WolfyStock Linear mockup;
2. `docs/frontend/visual-system.md`;
3. `docs/frontend/README.md`;
4. `docs/archive/design/DESIGN.md` as reference only;
5. installed design skills as execution aids.
