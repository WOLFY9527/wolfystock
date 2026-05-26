# WolfyStock Codex Compact Final Report Protocol

Purpose: standardize short Codex final reports for normal bounded tasks so they stay useful without turning into long postmortems.

## 1. Default Use

Use this compact format for normal bounded execution tasks unless the prompt explicitly asks for a fuller report.

Keep only these sections:

1. Task ID / status
2. Commit / branch state
3. Files changed
4. What changed
5. Invariants preserved
6. Validation
7. Risks / rollback

Omit full logs, large diffs, long explanations, repeated project history, and step-by-step narration unless failure or debugging requires them.

## 2. Compact Success Report

Use the shortest form that still proves the task outcome:

```text
Task ID / status:
- T-###
- READY TO LAND | NO-OP

Commit / branch state:
- branch: <branch>
- commit: <hash message> | not committed
- git status: <short result>

Files changed:
- <path>

What changed:
- <1 to 3 task-scoped bullets>

Invariants preserved:
- no runtime behavior changes
- no code changes outside scope
- no tests changed
- no extra docs rewritten

Validation:
- <command> -> <result>

Risks / rollback:
- <remaining risk or none beyond normal review>
- rollback: <revert command or delete file instruction>
```

## 3. Read-Only Audit Variant

Read-only audits should report:

- verdict
- findings
- recommended next task
- files inspected
- final git status

Do not add execution-only sections such as commit details when nothing was changed.

## 4. Failed Task Variant

If the task fails or blocks, keep the same compact structure where possible and include only the minimal error excerpt needed to diagnose the issue.

Do not paste full stack traces or long command output unless the short excerpt is insufficient.

## 5. Practical Rules

- Prefer command plus result, not raw terminal dumps.
- Keep `What changed` focused on outcome, not implementation diary.
- Keep `Invariants preserved` explicit when the task is docs-only or tightly scoped.
- If no files changed, say so directly.
- If rollback is trivial, say the exact minimal action.
