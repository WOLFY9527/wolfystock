# WolfyStock Codex Prompt Context Index

Purpose: this folder holds stable Codex rules so task prompts can stay short without losing quality.

Use this index in prompts when appropriate:

```text
Read first:
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- docs/codex/WOLFYSTOCK_SHARED_MAIN_WORKTREE_PROTOCOL.md
- docs/codex/WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md
- docs/codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md
- docs/codex/WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md
- docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md
- docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
```

## Which docs to read by task type

### Frontend UI implementation
Read:
- `WOLFYSTOCK_SHARED_MAIN_WORKTREE_PROTOCOL.md`
- `WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md`
- `WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`
- `WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md`
- `WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`

### Frontend audit / report-only
Read:
- `WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`
- `WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md`
- `WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`

### Backend provider / API quota / data-source work
Read:
- `WOLFYSTOCK_SHARED_MAIN_WORKTREE_PROTOCOL.md`
- `WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`
- `WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md`
- `WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`

### Backtest universe work
Read:
- `WOLFYSTOCK_SHARED_MAIN_WORKTREE_PROTOCOL.md`
- `WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`
- `WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md`
- `WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`

### Admin / operator UI work
Read:
- `WOLFYSTOCK_SHARED_MAIN_WORKTREE_PROTOCOL.md`
- `WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md`
- `WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`
- `WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md`
- `WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`
- `WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`

## Prompt format reminder

The task label should be outside the code block:

任务类型：执行类（适合 Codex 5.4）

```text
Actual Codex prompt goes here.
```

or:

任务类型：决策类（建议 Codex 5.5）

```text
Actual Codex prompt goes here.
```

Use Codex 5.4 for concrete implementation, validation, commit/push, report-only audits, and routine refactors.
Use Codex 5.5 for architecture decisions, risky domain decisions, task decomposition, and evaluating blockers/reports.
