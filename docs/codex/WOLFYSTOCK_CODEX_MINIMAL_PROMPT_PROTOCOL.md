# WolfyStock Codex Minimal Prompt Protocol

Purpose: keep Codex prompts short, low-noise, and tightly bounded so Codex does only the requested work.

Use this protocol for low-risk docs, copy, config, and small bounded implementation tasks. It is a prompt-shape, not a replacement for repository rules.

## Core rules

- Prefer the shortest prompt that still makes edit scope, stop conditions, and validation unambiguous.
- Usually omit explicit `Branch` and `Workspace` when the user manually selects the workspace in the Codex app.
- Use whitelist execution: only edit files listed in `Allowed final diff`.
- Stop if the task appears to require any extra file, protected domain, opportunistic cleanup, rename, refactor, or formatting pass.
- Keep final diffs narrow; do not "help" by fixing nearby issues.

## Minimal prompt fields

Use these sections in this order:

```text
Read and obey:
Task:
Execution context:
Intent:
Non-goals:
Allowed final diff:
Hard stop:
Requirements:
Invariants:
Validation:
Commit:
Final report:
```

## Section guidance

### Read and obey

Keep this block stable so shared docs stay cache-friendly.

```text
Read and obey:
- AGENTS.md
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md
- docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
```

Add extra docs only when the task truly needs them.

### Task

Use one stable task line:

```text
Task:
T-### — <short title>
```

### Execution context

Use this exact pattern by default:

```text
Execution context:
Use the currently selected workspace/branch. Do not create, switch, rebase, or delete branches/worktrees unless explicitly instructed.
```

Usually do not restate branch/workspace if the user already selected the workspace in the Codex app.

### Intent

State the desired outcome in 1 to 2 lines. Focus on what should exist at the end, not on how to "improve" surrounding areas.

### Non-goals

List adjacent work Codex must not do. Keep it blunt:

- no opportunistic refactors
- no renames
- no formatting-only churn
- no cleanup outside scope
- no nearby fixes unless explicitly requested

### Allowed final diff

List exact file paths. Prefer one-file or few-file allowlists.

```text
Allowed final diff:
- path/to/file.md
```

This is a whitelist, not a hint. Codex should edit only these files.

### Hard stop

Use an explicit stop rule:

```text
Hard stop:
If you need to edit any file outside Allowed final diff, stop and report why. Do not continue.
```

### Requirements

List only task-specific deliverables. Keep this short and testable.

### Invariants

Name what must remain unchanged, especially for low-risk tasks:

- no runtime behavior changes
- no code changes
- no tests changed
- no existing docs rewritten

### Validation

Include only the commands needed for the scoped change. For docs-only tasks, keep the list short and deterministic.

### Commit

Provide the exact commit message only when the task author wants a commit. Do not treat this section as implicit authorization to push, merge, or clean up branches.

### Final report

Ask for a compact report that covers only:

- file created or changed
- key rules captured
- validation result
- remaining risks

## Example template

```text
Read and obey:
- AGENTS.md
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md
- docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md

Task:
T-### — <short title>

Execution context:
Use the currently selected workspace/branch. Do not create, switch, rebase, or delete branches/worktrees unless explicitly instructed.

Intent:
Create one compact project doc that defines the requested rule set.

Non-goals:
- no code changes
- no extra docs
- no cleanup
- no opportunistic nearby fixes

Allowed final diff:
- docs/codex/<target-file>.md

Hard stop:
If you need to edit any file outside Allowed final diff, stop and report why. Do not continue.

Requirements:
1. Add the requested guardrail.
2. Keep it concise and practical.
3. Include one short example.

Invariants:
- No runtime behavior changes.
- No code changes.
- No tests changed.
- No existing docs rewritten.

Validation:
- git diff --check
- ./scripts/release_secret_scan.sh
- git status --short --branch

Commit:
<exact commit message or "not authorized">

Final report:
Compact only: file changed, key rules captured, validation, risks.
```

## Decision test

A prompt using this protocol is good enough if Codex can answer, before editing:

- what exact file set may be changed;
- what must stay unchanged;
- when to stop instead of expanding scope;
- how to validate;
- what to report at the end.

If any answer is vague, the prompt is still too loose.
