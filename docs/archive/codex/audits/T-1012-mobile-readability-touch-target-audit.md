# T-1012 Mobile Readability and Touch Target Audit

Mode: `READ-ONLY-AUDIT`
Viewport focus: `390px` class, primarily `390x844`
Artifact scope: this report only

## Executive Result

- P0 mobile blocker: none found from current code and smoke coverage.
- Highest-priority risk: repeated `32px` to `40px` compact controls on research, scanner, portfolio, watchlist, backtest, settings, and admin surfaces. These are visible but below a comfortable mobile touch target.
- Second-priority risk: several high-density data regions rely on internal horizontal scrolling or `760px` / `720px` table widths. This is not page-breaking because current smokes protect against global overflow, but the narrow viewport reading path is still slow.
- Preferred repair direction: keep research evidence intact and use progressive disclosure, row wrapping, spacing, larger tap targets, and explicit overflow containment. Do not delete evidence or redesign the whole IA.

## Evidence Base

This audit inspected code and existing mobile-capable smoke harnesses. Playwright was not run during the audit; the task is docs-only and existing smoke files were read as evidence sources.

Relevant smoke evidence inspected:

- Home chart has a dedicated `390x844` smoke that checks visibility, ECharts render, context badges, unsafe-copy absence, and no horizontal overflow: `apps/dsa-web/e2e/home-chart-browser.smoke.spec.ts:260`.
- Consumer copy regression loops desktop and mobile for Home, Market Overview, Scanner, and Options Lab, including no horizontal overflow checks: `apps/dsa-web/e2e/consumer-copy-regression.smoke.spec.ts:598`.
- Controlled user testing covers Scanner and Options Lab at the narrow viewport, but Backtest there is desktop-only: `apps/dsa-web/e2e/controlled-user-testing.smoke.spec.ts:791`.
- Market Overview, Scanner, and Watchlist have a `390x844` launch/degrade smoke: `apps/dsa-web/e2e/market-overview-scanner.smoke.spec.ts:90`.
- Portfolio launch surface loops desktop and `390x844`, validates vertical lane order, copy safety, and no page overflow: `apps/dsa-web/e2e/portfolio-launch-surface.spec.ts:4`.
- Backtest result visual smoke loops desktop and narrow viewports and checks the result chart/report path plus no horizontal overflow at `<=390px`: `apps/dsa-web/e2e/backtest-visual-result.smoke.spec.ts:60`.
- Settings/System has mobile harness coverage through `settings-disclosure`: `apps/dsa-web/e2e/settings-disclosure.smoke.spec.ts:43`.
- Admin ops surfaces loop mobile/desktop and assert L0 hierarchy, closed disclosures, no raw secret text, and no horizontal overflow: `apps/dsa-web/e2e/admin-ops-launch-surfaces.spec.ts:453`.

## Surface Findings

### Guest Landing

Classification: P1 touch target issue, P2 copy-wrapping risk.

- The shared Home/guest command bar uses `min-h-10` controls and input shells, so the main input/action path is roughly `40px`, not a comfortable `44px` target: `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5642`.
- Guest registration CTA also uses `min-h-10`, and the guest workflow block uses small two-column labels with `10px` / `11px` text and truncation. Current copy is short enough, but future text expansion is brittle.
- Existing guest P0 verification is route/copy oriented and not a mobile hit-target audit.

Preferred future fix: increase hit area on the command and CTA controls, allow the workflow step labels to wrap or collapse to one column at the smallest width, and keep the read-only research boundary copy.

### Home Research Console and Chart

Classification: P1 touch target issue, P2 secondary evidence readability.

- Report action buttons are `min-h-9` or fixed `w-9`, below comfortable mobile touch size: `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5557`.
- Home chart timeframe buttons and indicator chips use `text-[10px]` with `px-2.5 py-1` and no explicit minimum height: `apps/dsa-web/src/components/home-bento/HomeCandlestickChartDisplay.tsx:56`.
- Context badges are non-interactive, but still sit at `text-[10px]` and `min-h-6`, so they are acceptable as metadata but should not become tap targets without resizing: `apps/dsa-web/src/components/home-bento/HomeCandlestickChartDisplay.tsx:126`.
- Secondary evidence zones use `10px` / `11px` labels and truncation in key-level, fundamentals, and event areas. This is not a blocker; the right future move is wrapping and disclosure, not evidence deletion.

Acceptable dense UI: the chart stays primary, has a `390px` smoke, and no current evidence points to global overflow or blank chart rendering.

### Market Overview

Classification: P2 readability / touch comfort.

- Setup actions are `min-h-8 text-[11px]`: `apps/dsa-web/src/components/market-overview/MarketOverviewWorkbenchTopSurface.tsx:202`.
- Category tabs and export use `px-3 py-2 text-xs`, and the category rail is horizontally scrollable: `apps/dsa-web/src/components/market-overview/MarketOverviewWorkbenchTopSurface.tsx:955`.
- Dense quote rows already have `min-h-[44px]` / `min-h-[48px]` and mobile grid collapse, but metadata/freshness is `9px` and nowrap: `apps/dsa-web/src/components/market-overview/marketOverviewPrimitives.tsx:315`.
- Section metadata and compact cards use repeated `10px` / `11px` text: `apps/dsa-web/src/components/market-overview/MarketOverviewWorkbench.tsx:2033`.

Acceptable dense UI: current smokes verify route visibility, consumer-safe copy, partial payload degradation, and no global horizontal overflow at `390px`.

### Scanner

Classification: P1 touch target issue.

- Primary scanner run button is `h-8` on the mobile grid: `apps/dsa-web/src/pages/UserScannerPage.tsx:2878`.
- Candidate filter and sort controls use `px-2 py-0.5 text-xs`: `apps/dsa-web/src/pages/UserScannerPage.tsx:3097`.
- The "more actions" trigger is `h-8 px-2.5 py-1 text-xs`: `apps/dsa-web/src/pages/UserScannerPage.tsx:3161`.
- Shared `ScannerActionButton` resolves compact actions to `px-2.5 py-1 text-xs`, and those actions are used in mobile candidate rows for detail/more/analyze/backtest/watchlist flows: `apps/dsa-web/src/components/scanner/ScannerActionButton.tsx:23`, `apps/dsa-web/src/components/scanner/ScannerCandidatePresenters.tsx:781`.

Acceptable dense UI: the ranked list has a mobile row presenter and is not forcing the desktop `1220px` table into the phone layout.

### Options Lab

Classification: P1 readability for primary visuals, acceptable dense professional UI for chain tables.

- The payoff and IV visuals both force `min-w-[28rem]`, which is about `448px`, wider than a `390px` viewport: `apps/dsa-web/src/pages/OptionsLabPage.tsx:968`, `apps/dsa-web/src/pages/OptionsLabPage.tsx:1080`.
- The chain tables are `min-w-[720px]` but are inside a workbench frame with internal overflow, so they are acceptable dense professional tables when clearly contained: `apps/dsa-web/src/pages/OptionsLabPage.tsx:1519`.
- Current smokes verify the page is visible, read-only boundaries are present, no execution endpoints are called, and no page-level overflow exists. They do not prove the visual chart is quick to read on mobile.

Preferred future fix: add a compact mobile legend/summary before the chart or reduce mobile-only minimum chart width. Do not remove payoff/IV evidence.

### Portfolio

Classification: P1 readability and touch target issue.

- The holdings table is `min-w-[760px]` and seven-column at mobile widths; current smoke prevents page-level overflow but not local table reading friction: `apps/dsa-web/src/pages/PortfolioPage.tsx:2995`.
- Row cells combine `text-sm` primary with `text-[11px]` secondary context and truncation: `apps/dsa-web/src/pages/PortfolioPage.tsx:3040`.
- Common portfolio text/icon/danger controls are `py-1.5 text-xs`, `size-9`, and `size-8`: `apps/dsa-web/src/pages/PortfolioPage.tsx:80`.
- Left-tab segmented control is a high-frequency area and should be included in touch-target validation: `apps/dsa-web/src/pages/PortfolioPage.tsx:3457`.

Acceptable dense UI: the mobile lane order is already protected by smoke and should stay lane-first rather than becoming a card wall.

### Watchlist

Classification: P1 touch target issue.

- Row selection is fixed at `32x32`: `apps/dsa-web/src/pages/WatchlistPage.tsx:101`.
- Watchlist row actions and batch commands use compact terminal buttons: `apps/dsa-web/src/pages/WatchlistPage.tsx:1912`, `apps/dsa-web/src/pages/WatchlistPage.tsx:2288`.
- A `390px` launch smoke confirms the route and filter grid avoid page overflow, but the deeper user-alert smoke is desktop-only: `apps/dsa-web/e2e/watchlist-user-alerts.smoke.spec.ts:314`.

Preferred future fix: enlarge row selection and compact action hit areas, wrap button groups, and keep row detail/provenance visible.

### Backtest

Classification: P1 readability and wrapping issue.

- Result tabs are contained but only `36px` high on the result page: `apps/dsa-web/src/pages/DeterministicBacktestResultPage.tsx:1610`.
- Audit and trade tables remain dense table shells and should get a mobile summary/disclosure path before the full table: `apps/dsa-web/src/components/backtest/DeterministicBacktestResultView.tsx:223`.
- The configuration page sticky action bar uses a single `flex items-center gap-3` action row, which can crowd reset/parse/execute buttons at `390px`: `apps/dsa-web/src/components/backtest/DeterministicBacktestFlow.tsx:1473`.
- Existing narrow result smoke clicks the parameters tab but does not cover audit/trades/history tab readability.

Acceptable dense UI: the result chart workspace itself has narrow viewport smoke protection and should not be redesigned broadly.

### Settings / System

Classification: P1 touch target and readability issue.

- Settings category nav buttons use `px-3 py-2` with no explicit minimum height: `apps/dsa-web/src/components/settings/SettingsCategoryNav.tsx:40`.
- System health summary stays two columns on mobile and truncates label/value/detail at `10px` / `11px`: `apps/dsa-web/src/components/settings/SystemControlPlane.tsx:96`.
- Settings smoke checks the default operator-safe visible surface at mobile sizes, but not touch target size.

Preferred future fix: increase nav hit area, move health cards to one column or wrap labels at `390px`, and keep diagnostic details collapsed by default.

### Admin Surfaces

Classification: P1 touch target issue for accessible admin routes; acceptable dense professional UI for operator tables.

- Admin logs tabs use compact buttons with `px-3 py-1.5 text-xs`; filters include `h-9` selects: `apps/dsa-web/src/pages/AdminLogsPage.tsx:1857`.
- Provider circuit diagnostic disclosure buttons use `px-2 py-1 text-[11px]`: `apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx:104`.
- Admin ops smoke already covers mobile/desktop route hierarchy, closed disclosure buttons, and no global overflow. Current dense tables are acceptable if contained and operator-first.

Preferred future fix: enlarge disclosure and tab hit areas without expanding admin internals by default.

## Prioritized Future Write Tasks

### 1. Home / Guest Mobile Hit Area Pass

Priority: P1
Safe on main: yes, if scoped to listed files and no shared design primitive is changed.

Allowed files:

- `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`
- `apps/dsa-web/src/components/home-bento/HomeCandlestickChartDisplay.tsx`
- `apps/dsa-web/src/components/home-bento/HomeCandlestickChart.tsx` only if chart frame spacing needs a local adjustment
- `apps/dsa-web/e2e/home-chart-browser.smoke.spec.ts`
- `apps/dsa-web/e2e/consumer-copy-regression.smoke.spec.ts` only for mobile hit-area assertions

Validation commands:

- `npm --prefix apps/dsa-web run test:e2e -- e2e/home-chart-browser.smoke.spec.ts --project=chromium`
- `npm --prefix apps/dsa-web run test:e2e -- e2e/consumer-copy-regression.smoke.spec.ts --grep "Home" --project=chromium`
- `npm --prefix apps/dsa-web run lint`
- `npm --prefix apps/dsa-web run build`

Do not change:

- Home evidence packet, chart data, provider routes, copy safety boundaries, portfolio/scanner navigation semantics, or report generation behavior.

### 2. Scanner Mobile Controls and Candidate Actions

Priority: P1
Safe on main: no; use a task worktree because Scanner has dense ranking/action flows.

Allowed files:

- `apps/dsa-web/src/pages/UserScannerPage.tsx`
- `apps/dsa-web/src/components/scanner/ScannerActionButton.tsx`
- `apps/dsa-web/src/components/scanner/ScannerCandidatePresenters.tsx`
- `apps/dsa-web/src/components/scanner/ScannerBacktestLab.tsx`
- `apps/dsa-web/e2e/controlled-user-testing.smoke.spec.ts`
- `apps/dsa-web/e2e/market-overview-scanner.smoke.spec.ts`

Validation commands:

- `npm --prefix apps/dsa-web run test:e2e -- e2e/controlled-user-testing.smoke.spec.ts --grep "Scanner" --project=chromium`
- `npm --prefix apps/dsa-web run test:e2e -- e2e/market-overview-scanner.smoke.spec.ts --grep "scanner and watchlist" --project=chromium`
- `npm --prefix apps/dsa-web run lint`
- `npm --prefix apps/dsa-web run build`

Do not change:

- Scanner ranking, scoring, selection semantics, market driver copy, evidence frames, provider/cache behavior, or backtest launch payloads.

### 3. Portfolio / Watchlist Mobile Row and Action Pass

Priority: P1
Safe on main: no; use a task worktree because Portfolio and Watchlist include account, ledger, and saved-list workflows.

Allowed files:

- `apps/dsa-web/src/pages/PortfolioPage.tsx`
- `apps/dsa-web/src/pages/WatchlistPage.tsx`
- `apps/dsa-web/e2e/portfolio-launch-surface.spec.ts`
- `apps/dsa-web/e2e/market-overview-scanner.smoke.spec.ts`
- `apps/dsa-web/e2e/watchlist-user-alerts.smoke.spec.ts` only to add a `390px` variant or targeted hit-area checks

Validation commands:

- `npm --prefix apps/dsa-web run test:e2e -- e2e/portfolio-launch-surface.spec.ts --project=chromium`
- `npm --prefix apps/dsa-web run test:e2e -- e2e/market-overview-scanner.smoke.spec.ts --grep "scanner and watchlist" --project=chromium`
- `npm --prefix apps/dsa-web run test:e2e -- e2e/watchlist-user-alerts.smoke.spec.ts --project=chromium`
- `npm --prefix apps/dsa-web run lint`
- `npm --prefix apps/dsa-web run build`

Do not change:

- Portfolio accounting, cost basis, P&L math, FX conversion, manual ledger semantics, watchlist persistence, scanner links, or API payload shape.

### 4. Options Lab / Backtest Visual and Table Containment

Priority: P1 for Options visuals and Backtest table/tabs; P2 for chain tables.
Safe on main: no if combined; safe on main only when split into a single-surface patch.

Allowed files:

- `apps/dsa-web/src/pages/OptionsLabPage.tsx`
- `apps/dsa-web/src/pages/DeterministicBacktestResultPage.tsx`
- `apps/dsa-web/src/components/backtest/DeterministicBacktestResultView.tsx`
- `apps/dsa-web/src/components/backtest/DeterministicBacktestFlow.tsx`
- `apps/dsa-web/src/index.css` only for existing backtest table/chart containment classes
- `apps/dsa-web/e2e/controlled-user-testing.smoke.spec.ts`
- `apps/dsa-web/e2e/backtest-visual-result.smoke.spec.ts`
- `apps/dsa-web/e2e/consumer-copy-regression.smoke.spec.ts`

Validation commands:

- `npm --prefix apps/dsa-web run test:e2e -- e2e/controlled-user-testing.smoke.spec.ts --grep "Options Lab" --project=chromium`
- `npm --prefix apps/dsa-web run test:e2e -- e2e/backtest-visual-result.smoke.spec.ts --project=chromium`
- `npm --prefix apps/dsa-web run test:e2e -- e2e/consumer-copy-regression.smoke.spec.ts --grep "Options Lab" --project=chromium`
- `npm --prefix apps/dsa-web run lint`
- `npm --prefix apps/dsa-web run build`

Do not change:

- Options decision/risk semantics, order/broker boundaries, backtest simulation math, result schema, audit rows, or research-only copy.

### 5. Market Overview / Settings / Admin Compact Control Cleanup

Priority: P1 for Settings/Admin hit areas, P2 for Market Overview compact controls.
Safe on main: no if shared primitives are touched; safe on main only for a single page-local adjustment.

Allowed files:

- `apps/dsa-web/src/components/market-overview/MarketOverviewWorkbenchTopSurface.tsx`
- `apps/dsa-web/src/components/market-overview/marketOverviewPrimitives.tsx`
- `apps/dsa-web/src/components/settings/SettingsCategoryNav.tsx`
- `apps/dsa-web/src/components/settings/SystemControlPlane.tsx`
- `apps/dsa-web/src/pages/AdminLogsPage.tsx`
- `apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx`
- `apps/dsa-web/e2e/market-overview-scanner.smoke.spec.ts`
- `apps/dsa-web/e2e/settings-disclosure.smoke.spec.ts`
- `apps/dsa-web/e2e/admin-ops-launch-surfaces.spec.ts`

Validation commands:

- `npm --prefix apps/dsa-web run test:e2e -- e2e/market-overview-scanner.smoke.spec.ts --grep "market overview" --project=chromium`
- `npm --prefix apps/dsa-web run test:e2e -- e2e/settings-disclosure.smoke.spec.ts --project=chromium`
- `npm --prefix apps/dsa-web run test:e2e -- e2e/admin-ops-launch-surfaces.spec.ts --project=chromium`
- `npm --prefix apps/dsa-web run lint`
- `npm --prefix apps/dsa-web run build`

Do not change:

- Market scoring, source authority, provider/cache logic, admin auth, raw secret masking, settings config semantics, or disclosure defaults.

## Do Not Touch Together Map

- Do not combine Scanner changes with Portfolio/Watchlist changes if the patch touches `TerminalPrimitives.tsx`, `Button.tsx`, or another shared button primitive. Shared target-size changes must be their own task with full affected-surface smoke coverage.
- Do not combine Home chart controls with Options/Backtest chart containment if a shared chart primitive or `index.css` chart class is touched. Page-local fixes can proceed independently.
- Do not combine Portfolio ledger/table changes with any API, accounting, FX, or persistence work.
- Do not combine Market Overview UI changes with source-authority, provider, cache, scoring, or market temperature logic.
- Do not combine Settings/Admin hit-target cleanup with auth, config semantics, secret masking, or admin workflow behavior.
- Do not pair any readability pass with copy that changes research-only/no-advice boundaries unless the task explicitly scopes consumer-copy validation.

## Audit Close

This audit recommends scoped future UI work only. It does not recommend broad redesign, reducing information density by deleting research evidence, or changing finance/backend semantics.
