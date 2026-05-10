# WolfyStock Shared Main Worktree Protocol

Purpose: safe rules for the exceptional case where multiple Codex sessions work directly in `/Users/yehengli/daily_stock_analysis` on `main`.

Default Codex workflow is now the Codex App isolated task workspace with local environment `WolfyStock Fast`. Use this shared-main protocol only when the user explicitly asks to work directly in the shared `main` worktree.

## Core principle

A task may proceed in a shared dirty `main` worktree only if it can prove:

1. It will not edit or stage files owned by other tasks.
2. It will only stage files inside declared `TARGET_GLOBS` / `STAGE_ALLOWLIST`.
3. It will use focused validation and targeted diff checks for its own files.
4. It will stop before unsafe rebase/push situations.

## Prompt must declare

Every same-main executable task must declare:

```text
TARGET_GLOBS:
- exact path or glob this task may modify

STAGE_ALLOWLIST:
- exact files/folders allowed to be staged

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
cd /Users/yehengli/daily_stock_analysis
git fetch origin
git status --short --branch
git log --oneline --decorate -8
git log --oneline --decorate origin/main..HEAD
git diff --cached --name-only
git diff --name-only
```

## Stop conditions

Stop if any are true:

1. Staged files exist before the task starts.
2. Local `main` is ahead of `origin/main` by an unrelated commit.
3. `origin/main` moved beyond local `main` while dirty files exist.
4. Pre-existing dirty/untracked files overlap `TARGET_GLOBS`.
5. Dirty/untracked files outside `TARGET_GLOBS` are required for this task but appear owned by another task.
6. Validation fails.
7. Browser verification fails for frontend UI work.
8. Intended staged files include foreign dirty files.

## Allowed foreign dirty files

Dirty/untracked files outside `TARGET_GLOBS` are `FOREIGN_DIRTY`:

- do not edit;
- do not stage;
- do not commit;
- do not reset/revert/clean/stash;
- mention in final report.

## Diff checks

If foreign dirty files exist, do not rely only on broad diff checks.

Run targeted checks:

```bash
git diff --check -- <TARGET_GLOBS>
```

After staging only task files:

```bash
git diff --cached --name-only
git diff --cached --check
```

The staged list must contain only task files.

## Secret scan

Prefer full scan:

```bash
./scripts/release_secret_scan.sh
```

If it fails only because of `FOREIGN_DIRTY`, do not stage foreign files. Run a targeted task-file check and report the global exception.

If any high-confidence secret appears in task files, stop.

## Commit and push

Stage explicitly. Never use:

```bash
git add .
```

Before push:

```bash
git fetch origin
git log --oneline --decorate origin/main..HEAD
git status --short --branch
```

If `origin/main` moved and foreign dirty files remain, do not rebase. Stop and report local commit hash and push blocker.

If safe:

```bash
git push origin main
git fetch origin
git status --short --branch
git log --oneline --decorate -8
```

## Recommended same-main concurrency

Safe:

- report-only audits;
- read-only architecture decisions;
- one frontend write task plus one backend write task only if `TARGET_GLOBS` do not overlap.

Avoid:

- two frontend UI write tasks at once;
- Terminal primitives/design guard task plus page productization task;
- two tasks touching `docs/CHANGELOG.md`;
- two tasks touching router files;
- broad refactors in shared main.

## Final report additions

Same-main tasks must include:

- `TARGET_GLOBS`;
- foreign dirty files left untouched;
- staged file list;
- targeted diff/secret scan handling;
- final `git status --short --branch`.
