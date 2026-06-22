# T-1040 Backtest shell width layout consistency readiness audit

Task ID: T-1040-AUDIT

Task title: Backtest shell width layout consistency readiness audit

Mode: READ-ONLY-AUDIT with one explicitly allowed audit artifact.

Allowed artifact: `docs/codex/audits/archive/2026-06/T-1040-backtest-shell-width-layout-consistency-readiness-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1040-backtest-shell-width-readiness-audit`
- branch: `codex/t1040-backtest-shell-width-readiness-audit`
- base commit inspected: `be618cea4a4cb24cb81ced7b8d1fcd6894b746e7`
- `origin/main` after `git fetch origin`: `be618cea4a4cb24cb81ced7b8d1fcd6894b746e7`

Scope boundary:

- Source, tests, config, package, lockfile, route, auth, backend, API, provider,
  cache, runtime, and Backtest engine files were inspected only.
- This audit does not implement layout changes.
- Backtest calculations, fills, costs, metrics, persisted result semantics,
  result reports, tables, charts, comparison math, and stored readback authority
  are explicitly out of scope.

## Readiness verdict

`/zh/backtest` has a real shell-width inconsistency after T-1036 and is ready
for one narrow layout write.

The issue is the Backtest configuration page's local shell override:

- `apps/dsa-web/src/pages/BacktestPage.tsx:1362` renders
  `TerminalPageShell` with `max-w-none mx-0 px-0 ... xl:px-0`.
- `apps/dsa-web/src/pages/__tests__/BacktestPage.test.tsx:933-934`
  explicitly asserts `max-w-none`, `mx-0`, `px-0`, and absence of
  `max-w-[1600px]`, `mx-auto`, `px-4`, `xl:px-8`.
- T-1036 added the consumer shell cap in
  `apps/dsa-web/src/components/layout/ConsumerWorkspaceShell.tsx:10-12`,
  including `--wolfy-consumer-shell-max:1880px` and
  `max-w-[var(--wolfy-consumer-shell-max,1880px)]`.

At normal desktop widths the difference is small because the route lane is
already narrower than 1880px. At ultrawide width it becomes user-visible:

| Route | Viewport | Primary shell width | Computed max-width | Result |
| --- | ---: | ---: | --- | --- |
| `/zh/backtest` | 1440x1000 | 1296px | `none` | no horizontal overflow |
| `/zh/backtest` | 1920x1080 | 1763px | `none` | no horizontal overflow |
| `/zh/backtest` | 2560x1200 | 2403px | `none` | visibly wider than consumer cap |
| `/zh/options-lab` T-1036 consumer-shell comparison | 2560x1200 | 1880px | `1880px` | centered near-full shell |
| `/zh/backtest` | 390x844 | 317px | `none` | no horizontal overflow |

Therefore the immediate issue is shell-width governance, not Backtest form,
table, card, or analytical-content density.

## Evidence inspected

Required guard docs:

- `AGENTS.md`
- `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`
- `docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`

Frontend shell and route ownership:

- `apps/dsa-web/src/components/terminal/TerminalPrimitives.tsx:17-22`
  defines the default `TerminalPageShell` as
  `w-full max-w-[1600px] mx-auto px-4 xl:px-8 ...`.
- `apps/dsa-web/src/components/layout/ConsumerWorkspaceShell.tsx:10-24`
  wraps consumer surfaces with the T-1036 near-full 1880px cap.
- `apps/dsa-web/src/components/layout/Shell.tsx:196-221` classifies Backtest as
  a wide route.
- `apps/dsa-web/src/components/layout/Shell.tsx:529-533` applies
  `shell-content-frame--backtest`, `shell-content-frame--wide`, and the shared
  `shell-main-column` route lane.
- `apps/dsa-web/src/components/layout/__tests__/Shell.test.tsx:629-646`
  asserts Backtest uses the wide workspace lane, not a centered shell cap.

Backtest configuration page:

- `apps/dsa-web/src/pages/BacktestPage.tsx:1354-1363`
  owns the local `backtest-page-shell` width override.
- `apps/dsa-web/src/pages/BacktestPage.tsx:1367-1415`
  shows subnav, research boundary copy, and `backtest-v1-page` as page content
  below that shell.
- `apps/dsa-web/src/components/backtest/NormalBacktestWorkspace.tsx:79-112`
  owns the normal-mode content density, including the 32px consolidated card
  radius and form grid.
- `apps/dsa-web/src/components/backtest/DeterministicBacktestFlow.tsx:714-720`
  owns the pro/cockpit card density.
- `apps/dsa-web/src/index.css:6402-6424` has Backtest route/content CSS for the
  shell frame and `backtest-v1-page` grid/flex rhythm.

Backtest result/report and compare routes:

- `apps/dsa-web/src/pages/DeterministicBacktestResultPage.tsx:1676-1684`
  uses default `TerminalPageShell` with only `className="min-h-0"`.
- `apps/dsa-web/src/pages/__tests__/DeterministicBacktestResultPage.test.tsx:592-596`
  asserts the result shell remains `max-w-[1600px] mx-auto px-4 xl:px-8`.
- `apps/dsa-web/src/pages/RuleBacktestComparePage.tsx:1347-1350`
  uses default `TerminalPageShell`.
- `apps/dsa-web/src/pages/__tests__/RuleBacktestComparePage.test.tsx:412-414`
  asserts the compare shell remains `max-w-[1600px] mx-auto px-4 xl:px-8`.
- `apps/dsa-web/src/index.css:4715-4728`, `5525-5535`, and `15115-15218`
  contain Backtest result/report/chart density rules. These are separate from
  the `/zh/backtest` configuration shell-width issue.

Protected-domain context:

- `docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md:43-52` protects Backtest
  calculation math, strategy math, execution assumptions, exposure formulas,
  drawdown/return/win-rate calculations, benchmark calculations, and persisted
  result semantics.

## Browser verification

Method:

- Used Playwright CLI against `http://127.0.0.1:8000`.
- Logged in through the app using the provided admin account; no credential,
  cookie, or session value is recorded in this artifact.
- Captured DOM metrics only; no screenshots were kept.

Routes and results:

| Route | Browser outcome |
| --- | --- |
| `/zh/backtest` | Rendered authenticated Backtest configuration page; `backtest-page-shell`, `normal-backtest-workspace`, and `normal-backtest-consolidated-card` present. |
| `/zh/backtest/results/99` | Route rendered result page shell; API returned missing-resource content for run `99`, but shell measurement was still possible. |
| `/zh/backtest/compare?runIds=101,202` | Route rendered compare page shell; API returned invalid-parameter content for unavailable completed runs, but shell measurement was still possible. |
| `/zh/options-lab` | Used as a T-1036 consumer-shell comparison route because it uses `ConsumerWorkspacePageShell`. |

Observed browser facts:

- `/zh/backtest` has no horizontal overflow at 1440x1000, 1920x1080,
  2560x1200, or 390x844.
- `/zh/backtest` primary shell computed `max-width` is `none` at all measured
  viewports.
- `/zh/backtest` primary shell expands to 2403px on 2560x1200.
- T-1036 consumer-shell comparison route stays capped at 1880px and centered on
  2560x1200.
- Result and compare routes retain default 1600px `TerminalPageShell` behavior
  in code/tests and browser-accessible shell rendering.
- Browser console contained existing CSP report-only/font loading noise; no
  task-specific page crash was observed during measurement.

## Shell width vs content density

Do not treat this as a Backtest density refactor.

The shell-width inconsistency is caused by the top-level
`backtest-page-shell` class list. The dense Backtest content below it is owned by
separate components and CSS:

- Form/workspace density:
  `apps/dsa-web/src/components/backtest/NormalBacktestWorkspace.tsx:79-112`
- Pro cockpit density:
  `apps/dsa-web/src/components/backtest/DeterministicBacktestFlow.tsx:714-720`
- Result/report/chart density:
  `apps/dsa-web/src/index.css:4715-4728`,
  `apps/dsa-web/src/index.css:5525-5535`,
  `apps/dsa-web/src/index.css:15115-15218`

Those areas affect information density, report interpretation, chart workspace,
and result-review hierarchy. They are not necessary to fix the shell width and
should remain unchanged in the immediate write.

## Recommended immediate write

Exactly one immediate write is recommended:

**T-1040-FE1: normalize only the Backtest configuration page shell width to the
T-1036 near-full consumer cap.**

Allowed files for that write:

- `apps/dsa-web/src/pages/BacktestPage.tsx`
- `apps/dsa-web/src/pages/__tests__/BacktestPage.test.tsx`

Implementation shape:

- Replace the local `backtest-page-shell` width override in
  `BacktestPage.tsx:1362` with a near-full capped shell class consistent with
  the T-1036 consumer width contract.
- Keep Backtest page content, subnav, research-boundary copy, tabs, form fields,
  grids, result navigation, API calls, and all Backtest component internals
  unchanged.
- Update the focused `BacktestPage.test.tsx` shell assertion that currently
  requires `max-w-none`.

Recommended exact validation for that write:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/BacktestPage.test.tsx --run
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run build
git diff --check
./scripts/release_secret_scan.sh
```

Recommended browser smoke for that write:

- `/zh/backtest` at 1440x1000, 1920x1080, 2560x1200, and 390x844.
- Confirm:
  - no horizontal overflow;
  - `backtest-page-shell` no longer computes `max-width: none`;
  - ultrawide shell does not exceed the T-1036 near-full cap;
  - normal/pro tabs, subnav, and configuration form remain visible;
  - no Backtest run is launched during visual verification.

## Explicit deferrals

Defer all of the following:

- Backtest engine/math/fill/cost/metric/result semantics.
- Result report, result table, chart, trade ledger, comparison, export, and
  support-evidence behavior.
- Backtest form/table/content-density normalization.
- Backtest result/report CSS cleanup.
- Global layout token sweeps.
- Shared `TerminalPageShell`, `ConsumerWorkspaceShell`, `Shell`, or global CSS
  rewrites.
- Any API, auth, provider, cache, runtime, package, lockfile, route, or backend
  changes.

## Final diff boundary

This audit creates only:

- `docs/codex/audits/archive/2026-06/T-1040-backtest-shell-width-layout-consistency-readiness-audit.md`

No source, tests, config, package, lockfile, route, auth, backend, API,
provider, cache, runtime, Backtest engine, result report/table/chart behavior,
or generated browser artifact should be part of the final diff.
