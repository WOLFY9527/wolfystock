# WolfyStock Frontend Surface Usage Compatibility Note

This file name is kept for compatibility with older prompts that still reference `WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md`.

The old ghost-glass / terminal-card-first rules are retired.

For all frontend implementation tasks, follow:

- `docs/codex/CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md`

Current direction:

```text
Linear-inspired professional stock research OS
low-noise product software
board/list/table/report surfaces before cards
progressive disclosure
no meta-explanatory UI copy
no card-first dashboard
```

Existing `Terminal*` primitives may still be used when they comply with the current constitution, but they must not reintroduce ghost-glass/card-heavy UI by default.
