# T-995 Bundle and code-splitting audit

Task: T-995 Bundle and code-splitting audit

Mode: READ-ONLY-AUDIT with one explicitly allowed audit artifact.

Allowed artifact: `docs/codex/audits/archive/2026-06/T-995-bundle-codesplitting-audit.md`

Observed HEAD during audit: `5e94a4fb` (`T-992: audit large-page decomposition`)

Scope boundary:

- Source inspected, not changed.
- Tests inspected, not changed.
- No frontend/runtime/config/lockfile/CI/changelog changes.
- This report does not recommend raising the Vite warning limit as the primary fix.
- This report does not recommend a broad `manualChunks` rewrite without page-level boundary work first.

## Executive summary

Current `apps/dsa-web` bundle behavior is already route-lazy at the top level,
but several route chunks are still large because the lazy page files themselves
remain very large and still synchronously pull substantial local UI graphs.
The latest local build on **2026-06-05** only crosses the 500 kB warning on
`vendor-echarts` (**526.04 kB minified**), while `index` stops just below the
threshold at **498.68 kB**. The recurring page-sized chunks remain the stronger
maintainability signal:

- `SettingsPage`: **202.51 kB**
- `HomeBentoDashboardPage`: **193.05 kB**
- `vendor-react`: **192.78 kB**
- `UserScannerPage`: **186.11 kB**
- `MarketOverviewPage`: **160.42 kB**
- `ReportMarkdownTechnicalDetailsRenderer`: **158.66 kB**
- `BacktestPage`: **107.04 kB**
- `OptionsLabPage`: **95.40 kB**

The safest cleanup path is not a config-first chunking rewrite. The next step
should be a small sequence of route-internal boundary extractions and a narrow
follow-up on chart/markdown-heavy islands. That aligns with T-992: the page
decomposition audit already identified Home/Scanner/Market display seams; this
bundle audit adds a bundle-first execution order on top of those seams.

## Command evidence

### Preflight

- `pwd` -> `/Users/yehengli/worktrees/t995-bundle-codesplitting-audit`
- `git status --short --branch` -> clean on `codex/t995-bundle-codesplitting-audit`
- `git log --oneline -5` -> head at `5e94a4fb`
- `git diff --name-only` -> empty before audit write
- `git diff --cached --name-only` -> empty before audit write

### Build

Command:

```bash
npm --prefix apps/dsa-web run build
```

Observed result:

- Build passed.
- Vite still emitted the standard large-chunk warning.
- Largest emitted assets relevant to this audit:
  - `../../static/assets/vendor-echarts-DYcDW8an.js`: **526.04 kB**
  - `../../static/assets/index-BiSWiMmx.js`: **498.68 kB**
  - `../../static/assets/SettingsPage-16_Bew8N.js`: **202.51 kB**
  - `../../static/assets/HomeBentoDashboardPage-DQ8GjfSs.js`: **193.05 kB**
  - `../../static/assets/UserScannerPage-DuLo-AA3.js`: **186.11 kB**
  - `../../static/assets/MarketOverviewPage-B4R0SNqc.js`: **160.42 kB**
  - `../../static/assets/ReportMarkdownTechnicalDetailsRenderer-iwQdLPpX.js`: **158.66 kB**
  - `../../static/assets/BacktestPage-CtbiDbCQ.js`: **107.04 kB**
  - `../../static/assets/OptionsLabPage-DnXDzlcY.js`: **95.40 kB**

Secondary note:

- `../../static/assets/index-xoFfUhMx.css` is **558.67 kB** minified. That is
  a real asset-size concern, but it is CSS-scope rather than the JS
  code-splitting path requested here.

## Config and route structure

### Current Vite strategy

`apps/dsa-web/vite.config.ts` already uses a small hand-written
`manualChunks` function:

- `react`, `react-dom`, `scheduler` -> `vendor-react`
- `echarts`, `zrender` -> `vendor-echarts`
- `react-router*` -> `vendor-router`

Evidence:

- `apps/dsa-web/vite.config.ts:5-26`
- `apps/dsa-web/vite.config.ts:48-55`

Important guardrail:

- The repo intentionally keeps the default large-chunk warning visible.
- `apps/dsa-web/scripts/launch-build-warning-evidence.test.mjs:16-23`
  explicitly asserts that `package.json` keeps `tsc -b && vite build` and that
  `vite.config.ts` does **not** set `chunkSizeWarningLimit`.

Implication:

- Raising the warning threshold is currently contrary to the repo's evidence
  strategy and should only be discussed as a temporary CI-noise measure after
  real boundary work lands.

### Route lazy-loading boundaries

The named T-995 pages are already route-lazy. They are not synchronously pulled
into `main.tsx -> App.tsx`.

Evidence:

- Main entry only mounts `App` plus theme/i18n/preferences providers:
  `apps/dsa-web/src/main.tsx:1-18`
- Route-level lazy declarations:
  `apps/dsa-web/src/App.tsx:23-51`
- Route wiring:
  `apps/dsa-web/src/App.tsx:367-439`

Route conclusions:

- `/` -> lazy `HomeSurfacePage`, then static import into
  `HomeBentoDashboardPage`
  - `apps/dsa-web/src/App.tsx:26`
  - `apps/dsa-web/src/App.tsx:377`
  - `apps/dsa-web/src/pages/HomeSurfacePage.tsx:1-8`
- `/scanner` -> lazy `ScannerSurfacePage`, then second-level lazy
  `UserScannerPage`
  - `apps/dsa-web/src/App.tsx:28`
  - `apps/dsa-web/src/App.tsx:379`
  - `apps/dsa-web/src/pages/ScannerSurfacePage.tsx:1-33`
- `/settings/system` -> lazy `SystemSettingsPage`, then second-level lazy
  `SettingsPage`
  - `apps/dsa-web/src/App.tsx:44`
  - `apps/dsa-web/src/App.tsx:391`
  - `apps/dsa-web/src/pages/SystemSettingsPage.tsx:1-103`
- `/market-overview` -> lazy `MarketOverviewPage`
  - `apps/dsa-web/src/App.tsx:35`
  - `apps/dsa-web/src/App.tsx:382`
- `/backtest` -> lazy `BacktestPage`
  - `apps/dsa-web/src/App.tsx:39`
  - `apps/dsa-web/src/App.tsx:386`
- `/backtest/results/:runId` -> lazy `DeterministicBacktestResultPage`
  - `apps/dsa-web/src/App.tsx:42`
  - `apps/dsa-web/src/App.tsx:389`
- `/options-lab` -> lazy `OptionsLabPage`
  - `apps/dsa-web/src/App.tsx:40`
  - `apps/dsa-web/src/App.tsx:387`

Implication:

- `index` is not large because Home/Scanner/Settings/Market/Backtest/Options
  pages are directly bundled into the synchronous entry.
- `index` is large because the app shell still synchronously carries Router,
  Auth/i18n/theme/preferences providers, preview/login/reset flows, `Shell`,
  route guards, shared layout/navigation, and shared runtime/common utilities.
  See `apps/dsa-web/src/App.tsx:1-19`,
  `apps/dsa-web/src/App.tsx:249-505`,
  and `apps/dsa-web/src/components/layout/Shell.tsx:1-140`.

## Top chunk findings

### 1. `vendor-echarts` is the only current warning-class JS chunk

What it contains:

- Home chart ECharts runtime:
  `apps/dsa-web/src/components/home-bento/HomeCandlestickChart.tsx:3-29`
- Deterministic backtest chart ECharts runtime:
  `apps/dsa-web/src/components/backtest/DeterministicBacktestChartWorkspace.tsx:3-29`

Why it is large:

- The repo intentionally isolates all `echarts`/`zrender` code into one manual
  vendor chunk.
- That reduces duplicate chart runtime across lazy routes, but it also means
  every ECharts path accumulates into one shared warning-class asset.

What matters:

- This is not a config bug by itself.
- The real question is whether ECharts should remain a shared vendor island or
  whether some chart surfaces should migrate to more isolated loading
  boundaries. That is behavior-adjacent and not a safe config-only change.

### 2. `index` is large, but it is a shared-shell problem, not a missed page lazy-load

Evidence:

- `main.tsx` is thin: `apps/dsa-web/src/main.tsx:1-18`
- `App.tsx` synchronously imports Router shell, providers, route guards, and
  preview/auth flow: `apps/dsa-web/src/App.tsx:1-19`, `249-505`
- `Shell` synchronously imports nav, account menu, drawer/dialog shell, and
  shared route framing: `apps/dsa-web/src/components/layout/Shell.tsx:5-140`

Likely causes:

- Shared route shell and auth gating live in the sync graph.
- Shared UI utilities and common layout primitives are used by many routes and
  stay in entry/shared chunks.
- The app keeps both normal and preview route systems in the same top-level
  bundle graph.

Why not to attack this first:

- Entry-shell surgery has broad regression risk across every route.
- T-992 already shows more localized wins in page-internal display boundaries.

### 3. `HomeBentoDashboardPage` remains a large route chunk despite local lazy islands

Current size and shape:

- `HomeBentoDashboardPage` chunk: **193.05 kB**
- File size: **6207 lines**
- Route wrapper is tiny; the large chunk is the page itself:
  `apps/dsa-web/src/pages/HomeSurfacePage.tsx:1-8`

Existing local lazy boundaries:

- `LazyFullDecisionReportDrawer`
- `LazyHomeCandlestickChart`
- `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:103-108`

Likely cause:

- The page still synchronously owns a very large local orchestration/render
  graph, even after the report drawer and chart got isolated.
- T-992 already identified display-only clusters worth extracting before any
  route/controller refactor.

Assessment:

- This is a good target for small prop-only decomposition wins.
- It is not a candidate for config-level chunk surgery first.

### 4. `UserScannerPage` is already second-level lazy, but its own route chunk is still large

Current size and shape:

- `UserScannerPage` chunk: **186.11 kB**
- File size: **4099 lines**
- `ScannerSurfacePage` adds a second async boundary before loading it:
  `apps/dsa-web/src/pages/ScannerSurfacePage.tsx:6-29`

Existing local lazy boundaries:

- `LazyScannerStrategySimulationPanel`
- `LazyScannerBacktestLab`
- `apps/dsa-web/src/pages/UserScannerPage.tsx:102-110`

Likely cause:

- The Scanner page still synchronously owns large candidate presentation,
  workflow, diagnostics, and control surfaces.
- Some scanner backtest runtime is already deferred through
  `useScannerBacktestLab`, so the remaining size is primarily the base scanner
  workspace graph, not the optional backtest lab alone.

Assessment:

- This is another strong fit for T-992-style display extraction.
- Because Scanner is already two-stage lazy, a pure route-level split will not
  buy much more; the next gains must come from inside the page chunk.

### 5. `SettingsPage` is the largest page chunk, but it already has a healthy split direction

Current size and shape:

- `SettingsPage` chunk: **202.51 kB**
- File size: **3556 lines**
- `SystemSettingsPage` already lazy-loads `SettingsPage`:
  `apps/dsa-web/src/pages/SystemSettingsPage.tsx:10,95-97`
- `SettingsPage` already lazy-loads multiple heavy sub-panels and drawers:
  `apps/dsa-web/src/pages/SettingsPage.tsx:74-85`

Likely cause:

- The remaining chunk is mostly the system settings page shell, routing draft
  state, validation, helpers, and admin control composition that still load
  together before those inner panels open.

Assessment:

- This is not the best first target for broad splitting.
- The current architecture is already directionally correct.
- The safer next move is to keep page-level state ownership intact and only
  extract bounded helper/state clusters if a later task specifically targets the
  admin settings page.

### 6. `MarketOverviewPage` is smaller than Home/Scanner/Settings but still carries a broad synchronous request registry

Current size and shape:

- `MarketOverviewPage` chunk: **160.42 kB**
- File size: **974 lines**
- `MarketOverviewWorkbench` is sync-imported by the page:
  `apps/dsa-web/src/pages/MarketOverviewPage.tsx:23-30`
- The workbench itself defers some heavy display subtrees:
  `apps/dsa-web/src/components/market-overview/MarketOverviewWorkbench.tsx:65-71`

Likely cause:

- The page still owns wide request-group registries, staged polling logic,
  fallback payloads, and top-level orchestration:
  `apps/dsa-web/src/pages/MarketOverviewPage.tsx:42-150`
- The workbench holds broad display composition and tab/category registries:
  `apps/dsa-web/src/components/market-overview/MarketOverviewWorkbench.tsx:73-160`

Assessment:

- Market already has some correct lazy seams.
- The next size win is more likely to come from isolating static display
  registries or derived view-model building, not from changing route chunking.

### 7. `ReportMarkdownTechnicalDetailsRenderer` is a targeted heavy island and a credible safe win

Current size and shape:

- Chunk size: **158.66 kB**
- Renderer file is tiny:
  `apps/dsa-web/src/components/report/ReportMarkdownTechnicalDetailsRenderer.tsx:1-38`
- It pulls `react-markdown` and `remark-gfm`:
  `apps/dsa-web/src/components/report/ReportMarkdownTechnicalDetailsRenderer.tsx:1-4`
- It is already lazy-loaded only after the `<details>` panel opens:
  `apps/dsa-web/src/components/report/ReportMarkdown.tsx:93-96,260-289`

Likely cause:

- The chunk size is library-dominated, not local-file-dominated.
- Markdown technical evidence is already gated behind explicit user expansion.

Assessment:

- This is already a good lazy boundary.
- More splitting here is possible only if the product wants to trade extra
  request fragmentation for a smaller technical-details island.
- That is lower priority than Home/Scanner/Settings page-shape cleanup.

### 8. Backtest and Options chunks are not urgent warning-class problems, but they reveal different split maturity levels

Backtest:

- `BacktestPage`: **107.04 kB**
- `DeterministicBacktestResultPage`: **89.01 kB**
- `BacktestResultReport`: **73.53 kB**
- `BacktestAuditTables`: **76.07 kB**
- `DeterministicBacktestChartWorkspace`: **15.42 kB**

Evidence:

- `BacktestPage` lazy-loads its three major workspaces:
  `apps/dsa-web/src/pages/BacktestPage.tsx:53-55`
- `DeterministicBacktestResultPage` lazy-loads report and audit tables:
  `apps/dsa-web/src/pages/DeterministicBacktestResultPage.tsx:80,115`
- Result view further lazy-loads the deterministic chart workspace:
  `apps/dsa-web/src/components/backtest/DeterministicBacktestResultView.tsx:30-32`

Assessment:

- Backtest is already materially more split than Home/Scanner.
- Remaining chunk weight is more about rich route functionality than an obvious
  missed lazy seam.

Options:

- `OptionsLabPage`: **95.40 kB**
- File size: **2599 lines**
- No obvious internal `lazy()` boundaries at the page top:
  `apps/dsa-web/src/pages/OptionsLabPage.tsx:1-48`

Assessment:

- Options is the clearest “single large route chunk” among the non-warning
  targets.
- It is a candidate for one future bounded split if the team wants a clean
  standalone code-splitting task.
- It should not be mixed into Home/Scanner decomposition work.

## Quick safe wins vs risky work

### Quick safe wins

1. Use T-992 prop-only display extraction seams inside `HomeBentoDashboardPage`
   and `UserScannerPage` before touching route/controller logic.
2. Add one bounded lazy boundary inside `OptionsLabPage` for the least
   frequently used analytical surface, rather than splitting the whole page at
   once.
3. Leave `ReportMarkdownTechnicalDetailsRenderer` functionally as-is, but
   decide explicitly whether its current lazy-on-open boundary is “good enough”
   so it stops being treated as a mystery chunk.

### Risky code-splitting

1. Broad `manualChunks` rewrites for every big library or page.
   - Risk: fights Rollup's natural graph, can worsen cache invalidation, create
     duplicated async waterfalls, and obscure real page-boundary problems.
2. Entry-shell surgery to shrink `index`.
   - Risk: impacts every route, auth flow, preview route, and shared shell.
3. ECharts vendor re-topology without route-behavior validation.
   - Risk: could replace one large shared chunk with repeated async chart loads
     across Home and Backtest.

### Not worth now

1. Raising `chunkSizeWarningLimit`.
   - Current repo test intentionally forbids this as the default response.
2. Chasing `BacktestPage` or `DeterministicBacktestResultPage` first.
   - They are already meaningfully split and are not current warning-class
     problems.
3. Treating `ReportMarkdownTechnicalDetailsRenderer` as the primary cleanup.
   - It is already lazy on explicit user expansion and is library-driven.

## Recommended next tasks

Keep this list to four tasks. Anything beyond this would turn the audit into an
unbounded backlog.

### 1. Home and Scanner display-boundary extraction for bundle shrink

- Goal:
  - Land the first T-992 prop-only extractions in Home and Scanner to reduce
    synchronous route-chunk weight without touching route/task/store behavior.
- Allowed files:
  - `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`
  - `apps/dsa-web/src/pages/UserScannerPage.tsx`
  - new local display modules under `apps/dsa-web/src/components/home-bento/`
    and `apps/dsa-web/src/components/scanner/`
  - related existing page tests only if needed
- Expected risk:
  - Medium on main if strictly prop-only.
- Validation:
  - `npm --prefix apps/dsa-web run build`
  - `npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx src/pages/__tests__/UserScannerPage.test.tsx`
  - Home/Scanner smoke coverage from T-992 guidance
- Main vs worktree:
  - Main is acceptable if route/task/store effects stay in the page.
- Interaction with T-992:
  - This should directly follow the first two safe T-992 extraction slices, not
    invent a new decomposition strategy.

### 2. Options Lab one-surface lazy split

- Goal:
  - Introduce one bounded internal lazy boundary inside `OptionsLabPage` around
    the least frequently used analytical surface or disclosure-heavy section.
- Allowed files:
  - `apps/dsa-web/src/pages/OptionsLabPage.tsx`
  - one new component under `apps/dsa-web/src/components/options/`
  - related Options page tests if needed
- Expected risk:
  - Medium. Options is a protected product surface, so any split must be
    display-only and preserve no-advice/read-only wording.
- Validation:
  - `npm --prefix apps/dsa-web run build`
  - `npm --prefix apps/dsa-web run test -- src/pages/__tests__/OptionsLabPage.test.tsx`
  - existing consumer-copy regression smoke if routed through browser coverage
- Main vs worktree:
  - Main is acceptable only if no readiness/gate semantics move.
- Interaction with T-992:
  - Independent. Do not combine with Home/Scanner page decomposition.

### 3. Market Overview registry/view-model isolation

- Goal:
  - Reduce `MarketOverviewPage` route-chunk weight by isolating static layout
    registries or top-surface derived view-model building from the page shell.
- Allowed files:
  - `apps/dsa-web/src/pages/MarketOverviewPage.tsx`
  - `apps/dsa-web/src/components/market-overview/MarketOverviewWorkbench.tsx`
  - one or more new local helpers/modules under
    `apps/dsa-web/src/components/market-overview/`
  - existing Market overview tests if needed
- Expected risk:
  - Medium to high because request grouping, polling, fallback, and readiness
    semantics must stay unchanged.
- Validation:
  - `npm --prefix apps/dsa-web run build`
  - `npm --prefix apps/dsa-web run test -- src/pages/__tests__/MarketOverviewPage.test.tsx`
  - market overview browser/smoke coverage already used by T-992 and T-987
- Main vs worktree:
  - Prefer worktree if request orchestration moves; main only if extraction is
    display-registry-only.
- Interaction with T-992:
  - This matches T-992 task 4 and should stay narrower than a full market
    runtime hook refactor.

### 4. Entry-shell bundle audit follow-up

- Goal:
  - Perform a separate read-only audit focused only on `index` and shared-shell
    weight after page-level tasks 1-3 land.
- Allowed files:
  - docs-only audit artifact, or if later implemented:
    `apps/dsa-web/src/App.tsx`,
    `apps/dsa-web/src/components/layout/Shell.tsx`,
    shared shell/common modules explicitly named by that future audit
- Expected risk:
  - High if implemented, because it touches every route.
- Validation:
  - `npm --prefix apps/dsa-web run build`
  - shell/layout tests
  - focused route smoke across home, market, scanner, settings
- Main vs worktree:
  - Worktree only for implementation.
- Interaction with T-992:
  - Separate from T-992. Do not mix shell-weight work with large-page
    decomposition.

## Final recommendation

The next best sequence is:

1. Home + Scanner display extraction using T-992 safe seams.
2. Options Lab one-surface lazy split as an isolated page-level cleanup.
3. Market Overview display-registry isolation only if the team still needs more
   bundle reduction after 1 and 2.
4. Delay any `index`/shell surgery until after those localized wins are
   measured.

This keeps the cleanup aligned with the actual current evidence:

- route-level lazy loading already exists;
- `vendor-echarts` is the only current warning-class JS chunk;
- the largest remaining product signal is still oversized page chunks and large
  local synchronous UI graphs, especially Home, Scanner, and Settings.

## No-write confirmation

- No source/config/test files changed for this audit.
- No generated artifacts were kept.
- The only intended final diff is this audit document.
