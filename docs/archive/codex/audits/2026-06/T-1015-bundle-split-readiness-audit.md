# T-1015 Bundle Split Execution Readiness Audit

Task: T-1015-AUDIT Bundle split execution readiness audit

Mode: READ-ONLY-AUDIT with one explicitly allowed audit artifact.

Allowed artifact: `docs/codex/audits/archive/2026-06/T-1015-bundle-split-readiness-audit.md`

Observed workspace during audit:

- cwd: `/Users/yehengli/worktrees/t1015-bundle-split-readiness-audit`
- branch: `codex/t1015-bundle-split-readiness-audit`
- observed local HEAD before audit write: `b9c73186`
- observed `origin/main` after fetch: `27b0083c`
- branch state after fetch: behind `origin/main`; no merge, rebase, branch switch, or worktree creation was performed.

Scope boundary:

- Source inspected, not changed.
- Tests inspected, not changed.
- No Vite config, package, lockfile, route, runtime, source, or test changes.
- This audit does not implement lazy imports.
- This audit does not rewrite `manualChunks`.
- This audit keeps the next execution plan bounded and defers known mobile/UX overlap.

## Executive Summary

The current app is already top-level route-lazy. The production build warning is
not primarily caused by direct page imports in `App.tsx`.

Fresh build evidence from this branch shows two warning-class JS chunks:

- `vendor-echarts-DYcDW8an.js`: 526.04 kB minified, 175.62 kB gzip
- `index-B648XxVL.js`: 501.70 kB minified, 166.66 kB gzip

The largest route/page chunks remain below the 500 kB warning:

- `SettingsPage`: 202.56 kB
- `HomeBentoDashboardPage`: 193.35 kB
- `UserScannerPage`: 186.80 kB
- `MarketOverviewPage`: 160.42 kB
- `PortfolioPage`: 124.08 kB

The safest next write is therefore not a broad `manualChunks` rewrite. The next
bounded split should first move shared layout shell code behind an async layout
boundary from `App.tsx`, then rebuild and measure. That is a route/layout-level
split, avoids page UX internals, and is the lowest-overlap way to bring the
barely-over-threshold `index` chunk under the warning line.

The ECharts warning is real but more delicate. It is currently caused by a
single explicit vendor island used only by the Home candlestick chart and the
deterministic backtest chart. A chart-vendor follow-up should run only after the
layout split is measured, and it should be a narrow experiment with explicit
Vite-config authorization, not a general vendor taxonomy rewrite.

Page-internal Home, Scanner, Market, Settings, Options, and Backtest splits
should be deferred while T-1012 mobile readability findings and the active
Options/Backtest mobile containment branch are in flight.

## Evidence Sources

Docs and policy inspected:

- `AGENTS.md`
- `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`
- `docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`
- `docs/codex/audits/archive/2026-06/T-995-bundle-codesplitting-audit.md`
- remote `origin/main:docs/codex/audits/T-1012-mobile-readability-touch-target-audit.md`

Note: the prompt named `T-995-bundle-code-splitting-audit.md`; the exact path is
not present in this branch. The available prior bundle audit is
`docs/codex/audits/archive/2026-06/T-995-bundle-codesplitting-audit.md`.

Frontend files inspected:

- `apps/dsa-web/src/main.tsx`
- `apps/dsa-web/src/App.tsx`
- `apps/dsa-web/vite.config.ts`
- `apps/dsa-web/package.json`
- `apps/dsa-web/src/i18n/core.ts`
- `apps/dsa-web/src/components/layout/Shell.tsx`
- `apps/dsa-web/src/components/layout/PreviewShell.tsx`
- `apps/dsa-web/src/pages/HomeSurfacePage.tsx`
- `apps/dsa-web/src/pages/ScannerSurfacePage.tsx`
- `apps/dsa-web/src/pages/SystemSettingsPage.tsx`
- major page and component import/lazy boundaries under `apps/dsa-web/src/pages/`
  and `apps/dsa-web/src/components/`

Build evidence commands:

```bash
npm --prefix apps/dsa-web run build -- --outDir /tmp/t1015-bundle-split-build --emptyOutDir
```

Result: passed. Vite emitted the large-chunk warning for `vendor-echarts` and
`index`.

```bash
npm exec vite -- build --outDir /tmp/t1015-bundle-split-sourcemap --emptyOutDir --sourcemap
```

Run from `apps/dsa-web`. Result: passed. Sourcemaps were generated in `/tmp`
only and were not kept in the repo.

## Current Route And Chunk Shape

### Route loading

`App.tsx` already declares route pages with `lazy()`:

- core app/preview/access pages: `apps/dsa-web/src/App.tsx:23-33`
- product/admin pages: `apps/dsa-web/src/App.tsx:34-51`
- route wiring: `apps/dsa-web/src/App.tsx:377-465`
- preview route wiring: `apps/dsa-web/src/App.tsx:484-505`

Existing second-level lazy boundaries:

- Scanner wrapper defers `UserScannerPage`:
  `apps/dsa-web/src/pages/ScannerSurfacePage.tsx:6-29`
- System settings wrapper defers `SettingsPage`:
  `apps/dsa-web/src/pages/SystemSettingsPage.tsx:11,155-157`
- Home already defers chart and full report drawer:
  `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:103-108,1990-2007,6052-6059`
- Backtest and deterministic result pages defer workspaces/report/audit/chart
  panels.
- Market Overview defers the workbench grid and decision-debug details.
- Report Markdown defers the technical-details renderer.

Conclusion: adding generic route-level lazy imports for page modules is not the
next missing step. The next route-level opportunity is the shared layout shell,
not the pages.

### Vite chunking

`vite.config.ts` already defines a narrow vendor chunk function:

- `vendor-react`: React, React DOM, scheduler
- `vendor-echarts`: ECharts and zrender
- `vendor-router`: React Router

Evidence: `apps/dsa-web/vite.config.ts:5-26,48-55`.

The prior T-995 guardrail still applies: do not raise
`chunkSizeWarningLimit`, and do not treat a broad vendor taxonomy rewrite as the
first cleanup.

## Fresh Chunk Table

Fresh production build top assets:

| Asset | Size | Gzip | Current interpretation |
| --- | ---: | ---: | --- |
| `index-DPMBPXxc.css` | 559.54 kB | 79.03 kB | Large CSS asset; important but outside this JS split task. |
| `vendor-echarts-DYcDW8an.js` | 526.04 kB | 175.62 kB | Warning-class JS chunk, manually grouped. |
| `index-B648XxVL.js` | 501.70 kB | 166.66 kB | Warning-class app entry, barely over threshold. |
| `SettingsPage-DzxkTCYp.js` | 202.56 kB | 62.09 kB | Largest page chunk; already second-level lazy. |
| `HomeBentoDashboardPage-BRzyJoEM.js` | 193.35 kB | 64.10 kB | Large route chunk; already has local chart/drawer splits. |
| `vendor-react-CygJK5cN.js` | 192.78 kB | 60.53 kB | Expected vendor chunk. |
| `UserScannerPage-UUtc3cma.js` | 186.80 kB | 55.74 kB | Second-level lazy route chunk. |
| `MarketOverviewPage-BChquvvk.js` | 160.42 kB | 51.70 kB | Lazy route chunk with existing local splits. |
| `PortfolioPage-BsADsWiU.js` | 124.08 kB | 34.18 kB | Lazy route chunk. |
| `BacktestPage-Teyqss8u.js` | 108.39 kB | 36.73 kB | Lazy route chunk with workspace splits. |

Sourcemap size signals inside `index-B648XxVL.js`:

| Source | Source bytes in map | Interpretation |
| --- | ---: | --- |
| `src/i18n/core.ts` | 287.7 KiB | Dominant synchronous app-core source. |
| `tailwind-merge/dist/bundle-mjs.mjs` | 100.2 KiB | Shared utility dependency pulled by common primitives. |
| `src/components/layout/Shell.tsx` | 27.5 KiB | Shared layout shell in sync entry. |
| `src/App.tsx` | 27.4 KiB | Route/auth/preview orchestration in sync entry. |
| `src/api/error.ts` | 26.4 KiB | Shared API error utility in sync graph. |
| `src/stores/stockPoolStore.ts` | 24.6 KiB | Shared store in sync graph. |
| `src/components/layout/SidebarNav.tsx` | 17.8 KiB | Pulled with shell. |
| `src/components/linear/LinearPrimitives.tsx` | 17.6 KiB | Shared primitive graph. |

Sourcemap size signals inside largest page chunks:

| Chunk | Largest local sources | Readiness note |
| --- | --- | --- |
| `SettingsPage` | `SettingsPage.tsx`, `dataSourceLibraryShared.ts`, `useDataSourceLibraryController.ts`, `SystemControlPlane.tsx` | Already split under `SystemSettingsPage`; overlaps T-1012 settings findings. |
| `HomeBentoDashboardPage` | `HomeBentoDashboardPage.tsx`, `homeReportIdentity.ts`, evidence strips | Good future page split, but overlaps T-1012 Home/mobile chart findings. |
| `UserScannerPage` | `UserScannerPage.tsx`, `ScannerCandidatePresenters.tsx`, display panels, diagnostics | Good future page split, but overlaps T-1012 Scanner mobile work. |
| `MarketOverviewPage` | `MarketOverviewWorkbench.tsx`, `MarketOverviewWorkbenchTopSurface.tsx`, page shell | Good future page split, but overlaps T-1012 Market compact-control findings. |
| `PortfolioPage` | `PortfolioPage.tsx`, `PortfolioScenarioRiskPanel.tsx` | Not a first bundle target and overlaps mobile row/action findings. |

ECharts import evidence:

- Only `HomeCandlestickChart-Dp4LL-IP.js` and
  `DeterministicBacktestChartWorkspace-BJxaUhZQ.js` statically import
  `vendor-echarts-DYcDW8an.js`.
- Source import sites:
  - `apps/dsa-web/src/components/home-bento/HomeCandlestickChart.tsx`
  - `apps/dsa-web/src/components/home-bento/homeCandlestickChartUtils.ts`
  - `apps/dsa-web/src/components/backtest/DeterministicBacktestChartWorkspace.tsx`

## Active Conflict Surface

Current worktrees/branches relevant to follow-up planning:

- `main` and `origin/main` are at `27b0083c` (`T-1012: audit mobile readability`).
- `codex/t1018-options-backtest-mobile-containment` is active at the same
  T-1012 head.
- `codex/t1014-post-ux-wave-platform-audit`,
  `codex/t1016-scanner-preexisting-issue-audit`, and
  `codex/t1017-auth-route-policy-decision-audit` also exist as separate
  worktrees.

Conflict implications:

- Do not start Options/Backtest bundle splits while
  `codex/t1018-options-backtest-mobile-containment` is active.
- Do not split Home chart, Scanner controls/candidate rows, Market overview
  compact controls, Settings/System, Portfolio/Watchlist rows, Admin logs, or
  Backtest result/table surfaces until T-1012 mobile follow-ups for those files
  have landed or been explicitly ruled out.
- Avoid touching `SystemSettingsPage.tsx` in this branch without first
  integrating `origin/main`; T-1012 already changed it remotely.
- Any `App.tsx` split conflicts with auth/admin route-policy follow-ups and
  must run route guard tests. It does not inherently touch T-1012 mobile
  control files if kept to layout lazy declarations and route elements.

## Recommended Split Sequence

### 1. App shell layout lazy boundary

Status: safest immediate write after rebasing/integrating current `origin/main`.

Goal:

- Move `Shell` and likely `PreviewShell` behind `React.lazy` boundaries from
  `App.tsx`.
- Keep route definitions, auth guards, redirects, locale parsing, and capability
  checks semantically unchanged.
- Do not edit `Shell.tsx` unless a test proves the async boundary needs a local
  fallback adjustment.

Why first:

- It is route/layout-level splitting, not a config rewrite.
- It targets the barely-over-threshold `index` chunk.
- `Shell.tsx`, `SidebarNav.tsx`, and related shell modules are sync contributors
  to `index`.
- It avoids Home/Scanner/Options/Backtest page internals that overlap T-1012
  and active UX branches.

Likely touched files:

- `apps/dsa-web/src/App.tsx`
- `apps/dsa-web/src/__tests__/AppRoutes.test.tsx`
- possibly `apps/dsa-web/src/components/layout/__tests__/Shell.test.tsx`
- possibly `apps/dsa-web/src/components/layout/__tests__/PreviewShell.test.tsx`

Conflict risk:

- Medium with auth/admin route-policy work because `App.tsx` owns route guards.
- Low with T-1012 mobile findings if `Shell.tsx`, CSS, and mobile controls are
  not edited.

Future validation:

```bash
npm --prefix apps/dsa-web run test -- src/__tests__/AppRoutes.test.tsx src/components/layout/__tests__/Shell.test.tsx src/components/layout/__tests__/PreviewShell.test.tsx --run
npm --prefix apps/dsa-web run build
npm --prefix apps/dsa-web run check:design
./scripts/release_secret_scan.sh
```

Browser or smoke validation if the implementation changes visible fallback
behavior:

```bash
npm --prefix apps/dsa-web run test:e2e -- e2e/shell-route-admin-affordance.smoke.spec.ts --project=chromium
```

Expected measurement:

- `index` should drop below 500 kB if shell/sidebar/shared layout code moves out
  of the entry chunk.
- If `index` remains above 500 kB, inspect sourcemap again before touching
  `i18n/core.ts`.

### 2. Conditional ECharts vendor split decision

Status: conditional; not first; do not run while Options/Backtest mobile
containment is active.

Goal:

- Decide whether the current single `vendor-echarts` island should stay as-is or
  be split into narrower chart-runtime chunks.
- Keep this as a measured experiment with explicit Vite-config authorization.
- Do not rewrite all manual chunk rules.

Why conditional:

- `vendor-echarts` is the largest current warning-class JS chunk.
- Evidence is strong that only two chart islands import it.
- However, changing this boundary can create duplicate chart runtime, extra
  waterfalls, or route-specific chart regressions.

Likely touched files if implementation is authorized:

- `apps/dsa-web/vite.config.ts`
- `apps/dsa-web/src/components/home-bento/HomeCandlestickChart.tsx`
- `apps/dsa-web/src/components/home-bento/homeCandlestickChartUtils.ts`
- `apps/dsa-web/src/components/backtest/DeterministicBacktestChartWorkspace.tsx`
- chart-focused tests/smokes only as needed

Conflict risk:

- High with active `codex/t1018-options-backtest-mobile-containment` if it
  touches Backtest chart/result surfaces.
- Medium with T-1012 Home chart/mobile work.
- Medium with build/config reviewers because this is the only recommended task
  that may touch Vite config.

Future validation:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx src/pages/__tests__/DeterministicBacktestResultPage.test.tsx --run
npm --prefix apps/dsa-web run build
./scripts/release_secret_scan.sh
```

Add browser/smoke validation if chart loading behavior changes:

```bash
npm --prefix apps/dsa-web run test:e2e -- e2e/home-chart-browser.smoke.spec.ts --project=chromium
npm --prefix apps/dsa-web run test:e2e -- e2e/backtest-visual-result.smoke.spec.ts --project=chromium
```

Success criteria:

- No warning-class ECharts chunk, or a documented decision that keeping one
  shared ECharts vendor island is preferable to duplicated per-route chart
  runtime.
- Home chart and deterministic backtest result chart still render at desktop and
  `390px` viewports.

### 3. Deferred page/panel chunk splits after mobile work settles

Status: deferred; not safe as the immediate next write while T-1012/T-1018
overlap is active.

Goal:

- Continue T-995/T-992 page-internal split direction one page at a time.
- Prefer display/panel boundaries over controller, data-fetching, route,
  provider, cache, scoring, or protected finance semantics.

Candidate order after mobile/UX branches settle:

1. Home display-only split from `HomeBentoDashboardPage.tsx`, excluding chart
   control/touch-target work.
2. Scanner display-only split from `UserScannerPage.tsx`, excluding mobile
   action/control changes and ranking semantics.
3. Market Overview display-registry split from `MarketOverviewWorkbench.tsx`,
   excluding compact-control/mobile changes and request orchestration.

Likely touched files:

- Home:
  - `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`
  - new or existing local modules under `apps/dsa-web/src/components/home-bento/`
  - `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx`
- Scanner:
  - `apps/dsa-web/src/pages/UserScannerPage.tsx`
  - local modules under `apps/dsa-web/src/components/scanner/`
  - `apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx`
- Market Overview:
  - `apps/dsa-web/src/pages/MarketOverviewPage.tsx`
  - `apps/dsa-web/src/components/market-overview/MarketOverviewWorkbench.tsx`
  - local modules under `apps/dsa-web/src/components/market-overview/`
  - `apps/dsa-web/src/pages/__tests__/MarketOverviewPage.test.tsx`

Conflict risk:

- High with T-1012 mobile follow-ups for the same pages.
- Medium with active scanner/auth/admin audit branches if the split crosses
  route guard, rank/action, or evidence-copy boundaries.

Future validation:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx --run
npm --prefix apps/dsa-web run test -- src/pages/__tests__/UserScannerPage.test.tsx --run
npm --prefix apps/dsa-web run test -- src/pages/__tests__/MarketOverviewPage.test.tsx --run
npm --prefix apps/dsa-web run build
./scripts/release_secret_scan.sh
```

Run only the test matching the page actually touched, plus build and secret
scan. Add browser coverage for the affected route if a visible loading boundary
or layout fallback changes.

## Explicit Deferrals

Do not start these as the next bundle split:

- Broad `manualChunks` rewrite for every vendor or route family.
- Raising `chunkSizeWarningLimit`.
- `i18n/core.ts` async/dictionary split. It is a real `index` contributor, but
  it changes app-wide synchronous translation assumptions and should be a
  dedicated architecture task only if the shell split does not solve `index`.
- Options Lab or Backtest bundle splits while
  `codex/t1018-options-backtest-mobile-containment` is active.
- Settings/System split before integrating the T-1012 `SystemSettingsPage`
  changes from `origin/main`.
- Home, Scanner, Market, Portfolio, Watchlist, Settings, or Admin page splits
  that modify the same files named by T-1012 mobile readability follow-ups.

## Final Recommendation

Recommended execution sequence:

1. Land a narrow `App.tsx` shell-layout lazy boundary and measure the `index`
   chunk again.
2. If `vendor-echarts` remains the only warning, run a separate, explicitly
   authorized chart-vendor split decision task after active Options/Backtest and
   Home chart mobile work settles.
3. Resume Home/Scanner/Market page-internal splits only after T-1012 mobile
   overlap is clear, one route at a time.

This sequence preserves the current evidence:

- route-level lazy loading already exists;
- `index` is barely over 500 kB and has a bounded layout-shell split target;
- `vendor-echarts` is isolated and warning-class, but config changes should be
  measured and explicit;
- the largest page chunks are maintainability signals, not current Vite warning
  blockers.

## No-Source-Change Confirmation

- No source, test, config, package, lockfile, route, or runtime behavior was
  changed for this audit.
- Generated build and sourcemap outputs were directed to `/tmp`.
- The intended final diff is this document only.
