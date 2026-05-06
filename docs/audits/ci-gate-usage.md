# CI Gate Usage Note

Date: 2026-05-07

This note defines the local gate split for routine WolfyStock development.

## Fast iteration gate

Use `scripts/ci_gate_fast.sh` during local Codex/task iteration when the goal is
to catch obvious regressions quickly.

The fast gate detects:

- committed changes in `origin/main...HEAD`;
- unstaged working-tree changes;
- staged changes;
- untracked files.

When active local changes exist, the gate runs checks against the
staged/unstaged/untracked set for the current iteration and reports the
branch-ahead count for awareness. When the worktree is clean, it runs checks
against `origin/main...HEAD`.

It then runs against the selected gate files:

- `python -m py_compile` for changed Python files that still exist;
- focused `pytest` files when an obvious test file maps to the changed Python
  file or when the changed file itself is a Python test;
- frontend `npm run lint`, `npm run test`, and `npm run build` only when
  `apps/dsa-web/` files changed;
- docs whitespace/diff checks only when `docs/` or Markdown files changed.

Skipped stages are printed with the reason, such as no changed Python files, no
obvious focused tests, no frontend changes, or no docs changes.

## Full gate remains mandatory

`scripts/ci_gate_fast.sh` is for iteration only. It does not replace the full
pre-push/release gate:

```bash
./scripts/ci_gate.sh
```

The full gate remains mandatory before final push, release, or any claim that a
code-bearing change is fully green. The fast gate must not be used to waive
known blockers, defer known failing tests, or bypass the current
`scripts/ci_gate.sh` standard.

## Profiling helper

Use `scripts/ci_gate_profile.sh` when the gate itself needs timing evidence.
The default mode runs the offline pytest suite with pytest duration reporting:

```bash
scripts/ci_gate_profile.sh
```

Optional modes:

```bash
scripts/ci_gate_profile.sh frontend
scripts/ci_gate_profile.sh all
```

This helper is read-only in intent and exists to expose slow stages. It is not a
pass/fail substitute for either the fast iteration gate or the full gate.
