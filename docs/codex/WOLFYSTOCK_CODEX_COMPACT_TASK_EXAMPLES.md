# WolfyStock Codex Compact Task Examples

Purpose: provide short copyable prompt patterns after common SOP has moved into docs.

Model and reasoning recommendations belong outside the black-box prompt. See `WOLFYSTOCK_CODEX_MODEL_ROUTING.md`.

## Example: read-only architecture audit

```text
Task ID: T-###
Task title: Audit <area> architecture risks
Branch: <Codex isolated task branch>
Workspace: <Codex App isolated task workspace>
Mode: READ-ONLY-AUDIT

Read and obey:
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md
- docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
- <task-specific docs>

Goal:
- Map current architecture for <area>.
- Identify safe execution slices.
- Recommend serial/parallel plan.

Hard rules:
- Read-only.
- Do not edit, stage, commit, push, format, or create artifacts.

Inspect:
- <files/globs>

Final report:
Use WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md read-only format.
Include:
- root-cause map
- keep/replace/deprecate table
- safe next task prompts or task boundaries
- no-write confirmation
```

## Example: compact frontend execution

```text
Task ID: T-###
Task title: <route> Linear OS migration
Branch: <Codex isolated task branch>
Workspace: <Codex App isolated task workspace>
Mode: CODEX-ISOLATED

Read and obey:
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md
- docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
- docs/frontend/README.md
- docs/frontend/visual-system.md
- docs/frontend/validation-playbook.md

Current state:
- <required commits>
- <known dirty files>

Goal:
- Migrate <route> to <surface type>.
- Preserve <behavior>.

Allowed final diff:
- <files>

Forbidden final diff:
- <files/domains>

Implementation requirements:
1. <route-specific layout>
2. <behavior to preserve>
3. <test migration/update requirements>

Validation:
- npm --prefix apps/dsa-web run check:design
- python3 scripts/check_frontend_design_constitution.py
- npm --prefix apps/dsa-web run lint
- npm --prefix apps/dsa-web run build
- npm --prefix apps/dsa-web run test -- <focused-test>
- git diff --check
- ./scripts/release_secret_scan.sh

Browser:
Follow docs/frontend/validation-playbook.md.
Route/viewports:
- <route> at 1440x1000, 1920x1080, 390x844

Commit:
- Message: <message>

Final report:
Use WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md.
Include fresh screenshot source and route-specific visual observations.
```

## Example: low-risk docs task

```text
Task ID: T-###
Task title: Update <docs topic>
Branch: <Codex isolated task branch>
Workspace: <Codex App isolated task workspace>
Mode: CODEX-ISOLATED

Read and obey:
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md

Goal:
- Update <docs> to clarify <topic>.
- Do not change product code.

Allowed final diff:
- <docs files>

Forbidden final diff:
- product code
- tests
- package/lock files
- generated artifacts

Validation:
- git diff --check -- <docs files>
- ./scripts/release_secret_scan.sh

Commit:
- Message: <message>

Final report:
Use WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md, docs-only closeout.
```

## Example: backend protected-domain-adjacent execution

```text
Task ID: T-###
Task title: <backend task>
Branch: <Codex isolated task branch>
Workspace: <Codex App isolated task workspace>
Mode: CODEX-ISOLATED

Read and obey:
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md
- docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md

Goal:
- <specific backend goal>

Allowed final diff:
- <files>

Forbidden semantics:
- <task-specific protected semantics>

Implementation requirements:
1. <specific step>
2. <specific step>

Validation:
- python3 -m py_compile <changed files>
- python3 -m pytest -q <focused tests>
- git diff --check
- ./scripts/release_secret_scan.sh

Commit:
- Message: <message>

Final report:
Use WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md.
Explicitly confirm protected domains unchanged.
```
