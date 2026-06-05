# T-992 Large-page decomposition audit

Task: T-992 Large-page decomposition audit

Mode: READ-ONLY-AUDIT with one allowed report artifact.

Allowed artifact: `docs/codex/audits/T-992-large-page-decomposition-audit.md`

Scope boundary:

- Source inspected, not changed.
- Tests inspected, not changed.
- No config, lockfile, CI, changelog, route, API, schema, provider, cache, ranking, scoring, or runtime behavior changes.
- This report intentionally avoids recommending a large "rewrite the page" task.

## Executive summary

T-987 correctly classified the giant-component warnings as maintainability-only.
The practical next step is not a broad page rewrite. The safe path is a small
sequence of display-boundary extractions that preserve current state ownership,
test ids, consumer-safe copy, ranking/order semantics, and runtime/data-fetching
behavior.

Current target sizes:

- `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`: 6207 lines.
- `apps/dsa-web/src/pages/UserScannerPage.tsx`: 4099 lines.
- `apps/dsa-web/src/pages/MarketOverviewPage.tsx`: 974 lines.
- `apps/dsa-web/src/components/home-bento/HomeCandlestickChart.tsx`: 1075 lines.

Recommended safe order:

1. Leaf chart display extraction in `HomeCandlestickChart`: controls,
   unavailable state, and then pure model/option helpers.
2. Home display extraction: conclusion/evidence/provenance cluster, then
   observation rail/fundamentals/events container.
3. Scanner display extraction: conclusion/visual/history display panels, then
   launch controls, then candidate inspector shell.
4. Market display extraction: static layout/section registry, then top-surface
   view-model selector.
5. Isolation-only follow-ups: Home route/task hydration controller, chart
   fetch/interaction/ECharts shell, Scanner run/history/selection pipeline, and
   Market runtime hook.

## Evidence inspected

Primary files:

- `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`
- `apps/dsa-web/src/pages/UserScannerPage.tsx`
- `apps/dsa-web/src/pages/MarketOverviewPage.tsx`
- `apps/dsa-web/src/components/home-bento/HomeCandlestickChart.tsx`

Focused tests and smokes considered:

- `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx`
- `apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx`
- `apps/dsa-web/src/pages/__tests__/MarketOverviewPage.test.tsx`
- `apps/dsa-web/e2e/home-chart-browser.smoke.spec.ts`
- `apps/dsa-web/e2e/home-fundamentals-summary.spec.ts`
- `apps/dsa-web/e2e/home-scanner-evidence-browser.smoke.spec.ts`
- `apps/dsa-web/e2e/controlled-user-testing.smoke.spec.ts`
- `apps/dsa-web/e2e/consumer-copy-regression.smoke.spec.ts`
- `apps/dsa-web/e2e/market-overview-scanner.smoke.spec.ts`
- `apps/dsa-web/e2e/scanner-launch-surface.spec.ts`
- `apps/dsa-web/e2e/readiness-browser-acceptance.smoke.spec.ts`

Note: some older Scanner smokes still mention legacy `user-scanner-bento-page`.
Use the currently active `user-scanner-workspace` coverage and T-987 passing
smoke pack as the stronger validation signal for future Scanner work.

## HomeBentoDashboardPage

Relevant boundaries:

- Main component starts at `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:4966`.
- Local UI/task state is concentrated at
  `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:4973`.
- Store interaction is concentrated at
  `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5000`.
- Home evidence sidecar fetch runs at
  `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5220`.
- Route/task hydration and completion handoff effects run at
  `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5291`.
- Main render body starts at `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5702`.

Extractable regions:

- Render-only / display-only:
  `DecisionTracePanel` at `HomeBentoDashboardPage.tsx:804`,
  `HomeEvidenceCitationSummary` at `HomeBentoDashboardPage.tsx:1171`,
  `HomeSourceProvenanceStrip` at `HomeBentoDashboardPage.tsx:1325`,
  `HomeConclusionFirstConsole` at `HomeBentoDashboardPage.tsx:1381`,
  and `LinearEventsStrip` at `HomeBentoDashboardPage.tsx:2382`.
- Stateful but bounded:
  `LinearTechnicalStructure` at `HomeBentoDashboardPage.tsx:1913`,
  `LinearObservationPanel` at `HomeBentoDashboardPage.tsx:2058`,
  and `HomeFundamentalsSummaryBlock` at `HomeBentoDashboardPage.tsx:2280`.
  These should receive props and callbacks only; keep upstream state in the
  page for the first extraction.
- Risky, do not extract yet:
  report normalization at `HomeBentoDashboardPage.tsx:3158`,
  dashboard construction at `HomeBentoDashboardPage.tsx:4456`,
  the page orchestration block at `HomeBentoDashboardPage.tsx:4966`,
  and the route/task hydration effects at `HomeBentoDashboardPage.tsx:5291`.

Future extraction tasks:

1. Move the conclusion/readiness/evidence/provenance/citation display cluster
   into a dedicated Home display module.
   - Safe on main: yes, if it is prop-only and keeps test ids stable.
   - Validation:
     `npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx`
     `npm --prefix apps/dsa-web run test:e2e -- e2e/home-scanner-evidence-browser.smoke.spec.ts --project=chromium`
     `npm --prefix apps/dsa-web run test:e2e -- e2e/consumer-copy-regression.smoke.spec.ts --project=chromium`
2. Move the observation rail, fundamentals summary, and events secondary deck
   into a dedicated container.
   - Safe on main: yes, if no route/task/store state moves with it.
   - Validation:
     `npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx`
     `npm --prefix apps/dsa-web run test:e2e -- e2e/home-fundamentals-summary.spec.ts --project=chromium`
     `npm --prefix apps/dsa-web run test:e2e -- e2e/controlled-user-testing.smoke.spec.ts --project=chromium`
3. Extract route/task hydration into a hook or controller.
   - Safe on main: no. Needs worktree/isolation.
   - Validation:
     `npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx src/hooks/__tests__/useDashboardLifecycle.test.tsx`
     `npm --prefix apps/dsa-web run test:e2e -- e2e/controlled-user-testing.smoke.spec.ts e2e/readiness-browser-acceptance.smoke.spec.ts --project=chromium`
     `npm --prefix apps/dsa-web run test:e2e -- e2e/home-chart-browser.smoke.spec.ts --project=chromium`

Home invariants:

- Keep Home routed through `/` and `/:locale`; do not turn decomposition into a
  route rewrite.
- Preserve `home-bento-dashboard`, `home-research-console`,
  `home-research-readiness-strip`, `home-evidence-packet-strip`, and
  `home-provenance-strip`.
- Preserve consumer-safe copy: no raw/debug/provider/schema leakage and no
  trading/action wording.
- Preserve watchlist handoff through `symbol`, `task_id` or `taskId`, and
  `source=watchlist`.
- Do not expose task internals, raw LLM/debug wording, raw provider payloads,
  or internal route/cache details.

Do not touch together:

- Do not modify `HomeBentoDashboardPage.tsx` in the same extraction as
  `UserScannerPage.tsx` or `MarketOverviewPage.tsx`.
- Do not combine Home display extraction with `useDashboardLifecycle`,
  `useTaskStream`, `App.tsx`, global CSS, source contracts, or API behavior.
- Do not edit the broad smoke specs as part of a display extraction. Use them
  as validation only.

## UserScannerPage

Relevant boundaries:

- Main component starts at `apps/dsa-web/src/pages/UserScannerPage.tsx:2212`.
- Local run/control state starts at `UserScannerPage.tsx:2217`.
- Run/history state starts at `UserScannerPage.tsx:2231`.
- Selection/sort/filter state starts at `UserScannerPage.tsx:2250`.
- History loading and run selection logic run at `UserScannerPage.tsx:2365`.
- Candidate sorting and diagnostic selection pipeline starts at
  `UserScannerPage.tsx:2573`.
- Main render starts at `UserScannerPage.tsx:3286`.

Extractable regions:

- Render-only / display-only:
  `PillTagGroup` at `UserScannerPage.tsx:1701`,
  `ScannerResultHistorySummary` at `UserScannerPage.tsx:1756`,
  `ScannerVisualEvidenceSummaryPanel` at `UserScannerPage.tsx:1854`,
  `ScannerHistoryFallbackPanel` at `UserScannerPage.tsx:1936`,
  `ScannerConclusionBand` at `UserScannerPage.tsx:1984`, and
  `ScannerWorkflowSummaryPanel` at `UserScannerPage.tsx:2079`.
- Stateful but bounded:
  launch/scope/theme controls at `UserScannerPage.tsx:3385`, command/filter
  controls at `UserScannerPage.tsx:3603`, and candidate inspector rendering at
  `UserScannerPage.tsx:3020` plus `UserScannerPage.tsx:3853`.
- Risky, do not extract yet:
  run/history orchestration at `UserScannerPage.tsx:2365`, sorting/filtering
  and active-detail selection at `UserScannerPage.tsx:2573`, ranked row action
  wiring at `UserScannerPage.tsx:3777`, and Safari warm activation wiring at
  `UserScannerPage.tsx:2548`.

Future extraction tasks:

1. Move conclusion, workflow, visual summary, history summary, and fallback
   display components to a scanner display module.
   - Safe on main: yes.
   - Validation:
     `npm --prefix apps/dsa-web run test -- src/pages/__tests__/UserScannerPage.test.tsx`
     `npm --prefix apps/dsa-web run test:e2e -- e2e/home-scanner-evidence-browser.smoke.spec.ts --project=chromium`
2. Extract `ScannerLaunchControls` for scope/theme/custom-symbol inputs while
   leaving `handleRun`, `handleGenerateTheme`, validation state, and Safari
   activation in the page.
   - Safe on main: yes.
   - Validation:
     `npm --prefix apps/dsa-web run test -- src/pages/__tests__/UserScannerPage.test.tsx`
     `npm --prefix apps/dsa-web run test:e2e -- e2e/consumer-copy-regression.smoke.spec.ts --project=chromium`
3. Extract `ScannerCandidateInspector` around `renderCandidateDetailPanel` and
   context rail rendering, without moving `workbenchDiagnostics` or
   `activeDetailDiagnostic`.
   - Safe on main: yes, only as a props-only shell.
   - Validation:
     `npm --prefix apps/dsa-web run test -- src/pages/__tests__/UserScannerPage.test.tsx`
     `npm --prefix apps/dsa-web run test:e2e -- e2e/controlled-user-testing.smoke.spec.ts --project=chromium`

Scanner invariants:

- Preserve ranking, scoring, filtering, selection, sorting, and result order.
  `sortedCandidates` must keep current local sort behavior and rank tie-break.
- Preserve `selected`, `pool`, `rejected`, `data_failed`, and `all` filter
  semantics.
- Preserve active inspector fallback to the first visible candidate when the
  current candidate disappears.
- Preserve history selection: keep current selected run when present, otherwise
  fall back to the first returned run.
- Preserve top-down context before ranked rows, consumer-safe wording, and
  negative raw/trading leakage guarantees.

Do not touch together:

- Do not combine Scanner decomposition with `HomeBentoDashboardPage.tsx`,
  `HomeCandlestickChart.tsx`, or `MarketOverviewPage.tsx`.
- Do not combine Scanner display extraction with `apps/dsa-web/src/api/scanner.ts`,
  `apps/dsa-web/src/types/scanner.ts`, or
  `apps/dsa-web/src/api/researchReadiness.ts`.
- Do not edit broad smoke packs in the same extraction. Use them as regression
  gates.
- Any extraction that moves run/history selection, comparison/preview/backtest
  source wiring, or Safari activation needs worktree/isolation.

## MarketOverviewPage

Relevant boundaries:

- Polling/request constants begin at
  `apps/dsa-web/src/pages/MarketOverviewPage.tsx:42`.
- Local snapshot read/write begins at `MarketOverviewPage.tsx:251` and
  `MarketOverviewPage.tsx:327`.
- Panel assignment and fallback begin at `MarketOverviewPage.tsx:352` and
  `MarketOverviewPage.tsx:416`.
- Runtime state starts at `MarketOverviewPage.tsx:675`.
- Initial load, manual refresh, auto-revalidate, TTL polling, and crypto stream
  live at `MarketOverviewPage.tsx:702`, `MarketOverviewPage.tsx:767`,
  `MarketOverviewPage.tsx:811`, `MarketOverviewPage.tsx:893`, and
  `MarketOverviewPage.tsx:906`.
- The main display body is already delegated to
  `apps/dsa-web/src/components/market-overview/MarketOverviewWorkbench.tsx`.

Extractable regions:

- Render-only / display-only:
  tab/module registry in `apps/dsa-web/src/pages/MarketOverviewTabConfig.ts`,
  category layout and section metadata in `MarketOverviewWorkbench.tsx`, and
  top-surface derived display models inside the workbench.
- Stateful but bounded:
  `MarketOverviewWorkbench` owns only UI display state such as active category
  and export feedback.
- Risky, do not extract yet:
  staged load, route-entry dedupe, refresh dedupe, auto-revalidate, polling,
  crypto stream subscription, local snapshot persistence, and fail-closed
  panel fallback.

Future extraction tasks:

1. Extract static layout and section registry.
   - Safe on main: yes.
   - Validation:
     `npm --prefix apps/dsa-web run test -- src/pages/__tests__/MarketOverviewPage.test.tsx --run`
     `npm --prefix apps/dsa-web run test:e2e -- e2e/market-overview-scanner.smoke.spec.ts --project=chromium`
2. Extract top-surface view-model selector for data state, temperature summary,
   briefing summary, hero anchors, visual evidence cards, context highlights,
   and executive groups.
   - Safe on main: yes, if consumer-safe/fail-closed copy remains unchanged.
   - Validation:
     `npm --prefix apps/dsa-web run test -- src/pages/__tests__/MarketOverviewPage.test.tsx --run`
     `npm --prefix apps/dsa-web run test:e2e -- e2e/market-intelligence-actionability.smoke.spec.ts --project=chromium`
     `npm --prefix apps/dsa-web run test:e2e -- e2e/readiness-browser-acceptance.smoke.spec.ts --project=chromium`
3. Extract page runtime into a dedicated hook.
   - Safe on main: no. Needs worktree/isolation.
   - Validation:
     `npm --prefix apps/dsa-web run test -- src/pages/__tests__/MarketOverviewPage.test.tsx --run`
     `npm --prefix apps/dsa-web run test:e2e -- e2e/market-overview-scanner.smoke.spec.ts --project=chromium`
     `npm --prefix apps/dsa-web run test:e2e -- e2e/controlled-user-testing.smoke.spec.ts --project=chromium`

Market invariants:

- Local snapshot must render before backend completion and must not be blanked
  by refresh failure.
- Initial loading must remain staged and StrictMode-safe.
- Polling groups must retain current TTL cadence and manual refresh must target
  only the selected panel.
- Tab/category switching must change visible layout, not refetch everything.
- Crypto must remain REST snapshot first, then optional SSE live updates.
- Readiness, actionability, and visual evidence must remain consumer-safe,
  fail-closed, and compatible with older payloads.

Do not touch together:

- Do not mix `MarketOverviewPage` runtime extraction with
  `MarketOverviewWorkbench` display extraction in one small task.
- Do not combine Market decomposition with Home or Scanner decomposition.
- Do not change market API/provider/cache/freshness semantics, auth/RBAC, or
  admin diagnostics visibility as part of a decomposition.

## HomeCandlestickChart

Relevant boundaries:

- Pure candle/model helpers start around
  `apps/dsa-web/src/components/home-bento/HomeCandlestickChart.tsx:265`.
- Component shell starts at `HomeCandlestickChart.tsx:463`.
- Fetch/status/meta/interaction state starts at `HomeCandlestickChart.tsx:476`.
- History fetch runs at `HomeCandlestickChart.tsx:481`.
- Parent context callback runs at `HomeCandlestickChart.tsx:563`.
- ECharts option construction starts at `HomeCandlestickChart.tsx:574`.
- ECharts instance lifecycle starts at `HomeCandlestickChart.tsx:799`.
- Interaction handlers start at `HomeCandlestickChart.tsx:817`.

Extractable regions:

- Render-only / display-only:
  timeframe strip, indicator chips, context badges, and unavailable panel.
- Stateful but bounded:
  candle transform, indicator availability, tooltip formatting, and option
  factory. These are behavior-affecting but still chart-local.
- Risky, do not extract yet:
  fetch/status/history metadata, unavailable gating, ECharts lifecycle, hover
  coordinate mapping, and the parent `homeChartContext` contract.

Future extraction tasks:

1. Extract chart header controls and unavailable state display.
   - Safe on main: yes.
   - Validation:
     `npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx -t "keeps the Home chart rendered with mobile-safe context labels in a 390px viewport"`
     `npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx -t "shows consumer-safe Home chart unavailable copy when daily OHLC is unavailable"`
2. Extract pure model and option helpers, following the existing
   `homeCandlestickChartUtils.ts` pattern.
   - Safe on main: yes.
   - Validation:
     `npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx -t "renders timeframe controls, hides intraday controls, and aggregates 1W/1M from daily candles"`
     `npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx -t "toggles moving-average indicators without leaving the Home page"`
     `npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx -t "keeps the Home candlestick tooltip inside viewport bounds near chart edges"`
3. Extract chart fetch/interaction shell.
   - Safe on main: no. Needs worktree/isolation.
   - Validation:
     `npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx -t "renders real Home candlesticks from daily OHLC history and exposes hover OHLC values"`
     `npm --prefix apps/dsa-web run test:e2e -- e2e/home-chart-browser.smoke.spec.ts --project=chromium`
     `npm --prefix apps/dsa-web run test:e2e -- e2e/controlled-user-testing.smoke.spec.ts --project=chromium`

Chart invariants:

- Keep history requests daily-only with `{ period: 'daily', days: 365 }`.
- Keep 1W/1M derived from daily candles; do not add intraday controls.
- Render the chart only when status is ready, candle data exists, and volume
  support is available.
- Keep consumer-safe unavailable copy and do not expose provider/raw diagnostics.
- Preserve default indicators, VWAP availability behavior, hover SR-only output,
  and viewport-bounded tooltip positioning.
- Preserve lazy/deferred Home chart mount and do not trigger history fetch during
  fallback.

Do not touch together:

- Do not combine chart extraction with Home route/task orchestration.
- Do not move or change the `homeChartContext` parent contract unless the task
  is explicitly isolated.
- Do not rewrite broad smoke packs as part of chart decomposition.

## Do-not-touch-together map

- Home display extraction:
  do not touch Scanner page, Market page, route entry, lifecycle hooks, global
  CSS, source contracts, or broad smoke specs.
- Home route/task hydration extraction:
  do not touch chart internals, Scanner, Market, API contracts, or broad visual
  display components in the same task.
- Scanner display extraction:
  do not touch Home, Market, scanner API/types, research readiness builder,
  ranking/scoring/filtering/selection logic, or broad smoke specs.
- Scanner run/history/selection extraction:
  worktree/isolation only; do not mix with display extraction.
- Market display extraction:
  do not touch Market runtime loading/polling/cache/SSE behavior or Home/Scanner.
- Market runtime extraction:
  worktree/isolation only; do not mix with workbench display/view-model cleanup.
- Chart display/helper extraction:
  do not touch Home page orchestration or parent context contract.
- Chart fetch/interaction/ECharts lifecycle extraction:
  worktree/isolation only; do not mix with Home display or route/task work.

## Safe extraction order

1. `HomeCandlestickChart` display controls and unavailable state.
2. `HomeCandlestickChart` pure model/option helpers.
3. `HomeBentoDashboardPage` conclusion/evidence/provenance display cluster.
4. `HomeBentoDashboardPage` observation rail/fundamentals/events container.
5. `UserScannerPage` display panels.
6. `UserScannerPage` launch controls.
7. `UserScannerPage` candidate inspector shell.
8. `MarketOverviewPage` static layout/section registry.
9. `MarketOverviewPage` top-surface view-model selector.
10. Isolation-only queue: Home hydration controller, chart fetch/interaction
    shell, Scanner run/history/selection pipeline, Market runtime hook.

This order keeps leaf/display-only work first, pushes protected state semantics
later, and avoids any broad "rewrite the page" task.

## Validation guidance for future work

For safe-on-main display extractions, use the nearest page unit test plus the
smallest route-specific smoke that proves visibility, no raw leakage, no
trading-language regression, and no horizontal overflow.

For isolation-only tasks, add or adjust focused tests before moving logic and
then run the corresponding broad smoke pack. These tasks cross behavior or
runtime ownership and should not be treated as cosmetic decomposition.

## No-write proof for inspected source

During this audit, source, test, config, lockfile, CI, and changelog files were
only read. The only intended diff is this report artifact.
