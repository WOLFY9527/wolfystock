# WolfyStock Shared Main Worktree Protocol

Purpose: enable safe parallel Codex work in the same `main` working tree without requiring one worktree per task.

This protocol is mandatory when multiple Codex sessions may leave dirty files in `/Users/yehengli/daily_stock_analysis`.

## Core principle

A task may proceed in a shared dirty `main` worktree only if it can prove:

1. It will not edit or stage files owned by other tasks.
2. It will only stage files inside its declared `TARGET_GLOBS`.
3. It will use focused validation and targeted diff checks for its own files.
4. It will stop before unsafe rebase/push situations.

## Prompt must declare

Every same-main executable task must declare:

```text
TARGET_GLOBS:
- exact path or glob for files this task may modify

STAGE_ALLOWLIST:
- exact files or folders allowed to be staged

FOREIGN_DIRTY_POLICY:
- dirty files outside TARGET_GLOBS may exist
- never edit/stage/commit/reset/revert/clean/stash/move/delete them

VALIDATION_SCOPE:
- focused tests
- targeted git diff checks
- targeted secret scan fallback if global secret scan is blocked by foreign dirty files
```

## Preflight

Run:

```bash
git fetch origin
git status --short --branch
git log --oneline --decorate -8
git log --oneline --decorate origin/main..HEAD
git diff --cached --name-only
```

## Stop conditions

Stop and report if any of the following are true:

1. There are staged files before this task starts.
2. Local `main` is ahead of `origin/main` by an unrelated commit.
3. `origin/main` moved beyond local `main` while the worktree has dirty files.
4. Any pre-existing dirty/untracked file overlaps `TARGET_GLOBS`.
5. Any dirty/untracked file outside `TARGET_GLOBS` is required for this task but appears to be owned by another task.
6. Validation fails.
7. Browser verification fails for a frontend task.
8. The intended staged file list contains foreign dirty files.

## Allowed foreign dirty files

Dirty/untracked files outside `TARGET_GLOBS` may remain in the worktree.

They must be treated as `FOREIGN_DIRTY`:

- Do not edit.
- Do not stage.
- Do not commit.
- Do not reset.
- Do not revert.
- Do not clean.
- Do not stash.
- Do not move/delete.
- Mention them in final report.

## Diff checks

If foreign dirty files exist, do not run broad `git diff --check` across the whole worktree as the only whitespace validation.

Run targeted checks:

```bash
git diff --check -- <TARGET_GLOBS>
```

Before commit, after staging only task files, always run:

```bash
git diff --cached --name-only
git diff --cached --check
```

The staged name list must include only task files.

## Secret scan

Run:

```bash
./scripts/release_secret_scan.sh
```

If it passes, continue.

If it fails only because of `FOREIGN_DIRTY`, do not stage foreign files. Then perform a targeted check on intended task files:

```bash
git diff -- <TARGET_GLOBS>
grep -RInE "(password|secret|token|authorization|cookie|api_key|bearer)" <TARGET_GLOBS> || true
```

Continue only if the task files are clean. Mention the global scan exception clearly in the final report.

If any high-confidence secret appears in task files, stop.

## Commit and push

Stage explicitly. Never use:

```bash
git add .
```

Use exact file paths:

```bash
git add path/to/file1 path/to/file2
```

Before push:

```bash
git fetch origin
git log --oneline --decorate origin/main..HEAD
git status --short --branch
```

If `origin/main` moved and foreign dirty files remain, do not rebase. Stop and report the local commit hash and push blocker.

If safe:

```bash
git push origin main
git fetch origin
git status --short --branch
git log --oneline --decorate -8
```

## Recommended concurrency on same main

Safe:
- 1 frontend write task + 1 backend write task if TARGET_GLOBS do not overlap.
- Report-only audits.
- Read-only architecture decisions.

Avoid:
- Two frontend UI write tasks at once.
- Terminal primitives/design guard task plus any page productization task.
- Two tasks both touching `docs/CHANGELOG.md`.
- Two tasks both touching router files.
- Broad refactors in the same main worktree.

## Final report must include

- Commit hash/message.
- Push result.
- Files changed.
- Foreign dirty files left untouched.
- Focused validation results.
- Targeted diff/secret scan handling, including exceptions.
- Final `git status --short --branch`.
