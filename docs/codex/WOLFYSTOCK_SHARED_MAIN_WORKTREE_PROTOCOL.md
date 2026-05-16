# WolfyStock Shared Main Worktree Protocol

Purpose: safe rules for the exceptional case where one or more Codex sessions work directly in `/Users/yehengli/daily_stock_analysis` on `main`.

Default Codex workflow is the Codex App isolated task workspace. Use this shared-main protocol only when the user explicitly asks to work directly in the shared `main` worktree.

---

## Core Principle

A task may proceed in shared dirty `main` only if it can prove:

1. It will not edit or stage files owned by other tasks.
2. It will only stage files inside declared `TARGET_GLOBS` / `STAGE_ALLOWLIST`.
3. It will use focused validation and targeted diff checks for its own files.
4. It will stop before unsafe rebase/push situations.

---

## Prompt Must Declare

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

---

## Preflight

```bash
cd /Users/yehengli/daily_stock_analysis
git fetch origin
git status --short --branch
git log --oneline --decorate -8
git log --oneline --decorate origin/main..HEAD
git diff --cached --name-only
git diff --name-only
```

---

## Stop Conditions

Stop if any are true:

1. Staged files exist before the task starts.
2. Local `main` is ahead of `origin/main` by an unrelated commit.
3. `origin/main` moved beyond local `main` while dirty files exist.
4. Pre-existing dirty/untracked files overlap `TARGET_GLOBS`.
5. Dirty/untracked files outside `TARGET_GLOBS` are required but appear owned by another task.
6. Validation fails.
7. Browser verification fails for frontend UI work.
8. Intended staged files include foreign dirty files.

---

## Allowed Foreign Dirty Files

Dirty/untracked files outside `TARGET_GLOBS` are `FOREIGN_DIRTY`:

- do not edit;
- do not stage;
- do not commit;
- do not reset/revert/clean/stash;
- mention in final report.

---

## Diff Checks

If foreign dirty files exist, do not rely only on broad diff checks.

```bash
git diff --check -- <TARGET_GLOBS>
```

After staging only task files:

```bash
git diff --cached --name-only
git diff --cached --check
```

The staged list must contain only task files.

---

## Secret Scan

Prefer full scan:

```bash
bash scripts/release_secret_scan.sh
```

If it fails only because of `FOREIGN_DIRTY`, do not stage foreign files. Run a targeted task-file check and report the exception.

If a high-confidence secret appears in task files, stop.

---

## Commit and Push

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
