# WolfyStock Codex Compact Prompt Protocol

Purpose: keep Codex task prompts short while preserving safety, design fidelity, validation, and final-report quality.

This file is a prompt-compression layer. Task prompts should reference stable project docs instead of repeating long SOP blocks.

## Core rule

A compact Codex prompt should contain only task-specific deltas:

1. task ID/title/branch/workspace/mode;
2. goal;
3. current known commits/state;
4. allowed files;
5. forbidden files/domains;
6. implementation-specific requirements;
7. validation commands;
8. browser routes/viewports when frontend;
9. commit message;
10. final-report deltas.

Everything else should live in referenced docs.

## Always-reference docs

For implementation tasks:

```text
Read and obey:
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md
- docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
```

For frontend UI tasks add:

```text
- docs/codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md
- docs/codex/CODEX_FRONTEND_DESIGN_CONSTITUTION.md
- docs/codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md
- docs/codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md
- docs/codex/WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md
- docs/codex/WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md
- docs/codex/WOLFYSTOCK_CODEX_VISUAL_EVIDENCE_PROTOCOL.md
- docs/design/wolfystock-canonical-ui-primitives.md
```

For backend tasks add:

```text
- docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md
```

For provider/quota tasks add:

```text
- docs/codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md
```

For backtest universe tasks add:

```text
- docs/codex/WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md
```

## Prompt skeleton

Use this shape for most execution tasks:

```text
Task ID:
Task title:
Branch:
Workspace:
Mode:

Read and obey:
- <stable docs only>

Current known state:
- <required commits / dirty-file expectations / previous task result>

Goal:
- <3-6 task-specific bullets>

Allowed final diff:
- <exact files/globs>

Forbidden final diff:
- <exact files/globs and protected domains>

Implementation requirements:
1. <task-specific requirement>
2. <task-specific requirement>
3. <task-specific requirement>

Validation:
- <commands>

Browser verification:
- <routes/viewports or "not applicable">

Commit:
- Stage only intended files.
- Commit message:
- Push target:

Final report:
- Use WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md.
- Include task-specific proof:
  - <extra proof needed>
```

## What not to repeat

Do not repeat these in every prompt unless the task is high-risk or the prompt needs a stricter override:

- the full protected-domain list;
- generic git safety rules;
- entire final report template;
- full Playwright invocation guidance;
- full frontend design constitution;
- full model/reasoning policy;
- long lists of every validation profile;
- long descriptions of Linear OS principles already present in docs.

## What must stay in the prompt

Do not hide task-specific facts in docs. Always keep these explicit:

- exact Task ID and title;
- exact workspace and branch;
- exact current required commits when continuing a chain;
- exact allowed/forbidden file scopes;
- exact behavior that must be preserved;
- exact browser route and viewport requirements for visible UI changes;
- exact commit message;
- any current dirty-file expectation;
- any stop condition unique to this task.

## Dirty workspace handling

For same-main work, do not repeat the full shared-main protocol. Reference the doc and provide only target globs:

```text
Same-main rules:
Read WOLFYSTOCK_SHARED_MAIN_WORKTREE_PROTOCOL.md.

TARGET_GLOBS:
- <paths>

STAGE_ALLOWLIST:
- <paths>

FOREIGN_DIRTY_POLICY:
Dirty files outside TARGET_GLOBS may exist. Do not edit/stage/commit/reset/revert/clean/stash/move/delete them.
```

## Frontend task compression

Instead of repeating full design language, write:

```text
Design target:
Follow WolfyStock Linear OS. The approved mockup and WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md win over older docs or generic skill guidance.

Task-specific visual target:
- <only the visual deltas for this route>
```

Then reference `WOLFYSTOCK_CODEX_VISUAL_EVIDENCE_PROTOCOL.md` for screenshot and browser proof.

## Final-report compression

Prompt body can say:

```text
Final report:
Use WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md and include:
- <task-specific proof>
```

Do not paste the full template into each prompt.

## Anti-drift rule

A compact prompt is acceptable only if a new Codex session can still answer:

- what am I allowed to edit?
- what must not change?
- how do I validate?
- what counts as done?
- what exact evidence must I report?

If any answer depends on memory outside the repo docs or the prompt body, the prompt is too short.
