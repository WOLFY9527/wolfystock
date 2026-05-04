# CI Gate Clarity

This document explains how to interpret `scripts/ci_gate.sh` and which targeted checks to run before broad repo gates.

The goal is not to weaken validation. The goal is to make it obvious which failures are:

- caused by the current task
- caused by unrelated dirty work in the same repo
- caused by optional tooling missing from the environment
- caused by provider/data availability issues
- true regressions

## What `ci_gate` now reports

`scripts/ci_gate.sh` prints these sections in order:

1. Preflight status
2. Environment / optional tools
3. Backend syntax checks
4. Critical lint checks
5. Local deterministic smoke checks
6. Offline pytest suite
7. Summary

The preflight section is informational only. It must not fail just because the worktree is dirty.

If you only want the repo-state summary, run `./scripts/task_preflight.sh` directly.

## Preflight status

The preflight helper prints:

- current branch
- upstream branch and ahead/behind state when available
- dirty file count
- dirty file categories by top-level path
- a warning that dirty files may belong to parallel Codex sessions
- recent commits for context

Use this output to decide whether a failure is likely related to the current task or belongs to another parallel session.

## Targeted check matrix

Use the smallest useful checks first, then widen only if needed.

| Task type | Recommended checks |
| --- | --- |
| Frontend UI task | `cd apps/dsa-web && npm run check:design`, relevant Vitest page/component tests, `npm run lint`, `npm run build`, Safari desktop verification, 390px narrow verification |
| Backend API/service task | `python3 -m py_compile <changed files>`, focused `pytest` module(s), related regression `pytest` module(s) |
| Home/report task | `HomeSurfacePage` tests, `reportNormalizer` tests, relevant history/backend tests, Chat/Watchlist smoke tests if the shared normalizer changed |
| Portfolio task | `PortfolioPage` tests, `tests/test_portfolio_service.py` if backend code changed |
| Backtest task | relevant backtest frontend tests, `tests/test_backtest*` if backend code changed |
| Market task | `MarketOverviewPage` tests, market/cache `pytest` tests |
| Admin task | relevant admin page tests, relevant API tests |
| DuckDB task | quant DuckDB tests, portfolio/backtest regression tests, disabled no-write smoke |
| Design task | `cd apps/dsa-web && npm run check:design`, design guard script tests |

If a task touches more than one area, run the checks for each touched area instead of widening to the entire repo immediately.

## How to report blockers

Use the clearest factual label you can.

- Unrelated dirty file blocker
  - Report the exact paths and say they are pre-existing or parallel-session edits.
  - Do not stage or modify them unless they are part of the current task.
  - Example: `Blocked by unrelated dirty files in api/... and docs/...; my task files were not touched.`
- Optional tool warning
  - Report the missing tool explicitly.
  - Say the gate preserved its exit semantics and continued with other checks.
  - Example: `flake8 is missing locally; ci_gate reports this as a warning here, but CI still requires it.`
- Provider/data availability failure
  - Report the failing provider or dataset and the exact missing dependency or fetcher message.
  - Distinguish environment failure from code regression unless the failure reproduces with the required dependency present.
  - Example: `akshare is unavailable in this environment; the provider smoke failure is environment-related unless it reproduces with akshare installed.`
- Browser black/empty DOM fallback
  - If the in-app browser shows a black or empty page, retry in Safari and report both attempts.
  - If Safari also fails, include the route, the chosen port, and the observable symptom.
- Dev server ports
  - When you do need a server, report the exact port you used.
  - Keep this separate from browser-validation results so readers can reproduce the path.

## Optional tools and provider notes

`ci_gate` preserves the existing warning-only posture for missing optional tooling.

- Missing `flake8` remains a warning in local runs, but it is still required in CI.
- `test.sh` already warns when `akshare` or `yfinance` are absent.
- Do not turn missing optional tooling into a blanket skip for real failures.
- Do not claim a provider/data issue is harmless unless the output explicitly shows it is an environment limitation.

## Design guard

The frontend design guard remains separate from `scripts/ci_gate.sh`.

Run it for frontend or design-focused work:

```bash
cd apps/dsa-web
npm run check:design
```

Blocking findings fail the guard. Warning-only findings stay advisory and should be reviewed during visual QA, not converted into backend gate failures.

## Suggested reporting shape

When writing a completion note, keep the evidence split explicit:

1. What changed
2. Which targeted checks were run
3. Whether `ci_gate` passed, failed, or was blocked by unrelated dirty files
4. Whether any warnings were optional-tool or provider/data issues
5. Whether browser verification was done, and on which port

That distinction is the main goal of this pass.
