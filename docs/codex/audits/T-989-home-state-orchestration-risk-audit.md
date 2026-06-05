# T-989 Home state orchestration risk audit

Task: T-989 Home state orchestration risk audit

Mode: READ-ONLY-AUDIT with one explicitly allowed audit artifact.

Allowed artifact: `docs/codex/audits/T-989-home-state-orchestration-risk-audit.md`

Observed branch during audit: `codex/t989-home-state-orchestration-audit`

Scope boundary:

- No source code changes.
- No test changes.
- No config, lockfile, CI, or changelog changes.
- This report defines a future write plan only. It does not perform the refactor.

## Executive summary

T-987 correctly identifies Home route/task hydration as the largest remaining
wave-adjacent correctness risk. The current implementation is behavior-rich but
state ownership is spread across event handlers, store snapshots, render-time
memo mirrors, and several independent effects inside
`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`.

The future refactor should not be a visual rewrite and should not change
provider, API, cache, LLM, chart, evidence, or report semantics. The safe target
is a Home-local orchestration reducer/state machine that owns only view
coordination state:

- `activeTicker`
- `pendingAnalysisTicker`
- `hasHydratedInitialTicker`
- `isDashboardLoading`
- `hydratedRouteTaskId`

The future write should keep external synchronization effects for document
title, evidence fetches, task polling, history/task lifecycle, timers, and
query-param-driven dev/test drawer auto-open. It should move route task
hydration, manual submit, history selection, pending clear, task completion
clear, and active ticker backfill into explicit event-time or reducer
transitions.

## Evidence base

Files inspected:

- `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`
- `apps/dsa-web/src/hooks/useDashboardLifecycle.ts`
- `apps/dsa-web/src/hooks/__tests__/useDashboardLifecycle.test.tsx`
- `apps/dsa-web/src/stores/stockPoolStore.ts`
- `apps/dsa-web/src/stores/__tests__/stockPoolStore.test.ts`
- `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx`
- `apps/dsa-web/e2e/home-scanner-evidence-browser.smoke.spec.ts`
- `apps/dsa-web/e2e/controlled-user-testing.smoke.spec.ts`
- `apps/dsa-web/e2e/consumer-copy-regression.smoke.spec.ts`
- `docs/codex/audits/T-987-post-wave-react-doctor-smoke-stability-audit.md`

Relevant T-987 signal:

- React Doctor flagged `no-adjust-state-on-prop-change` and
  `no-chain-state-updates` around `HomeBentoDashboardPage.tsx:5220-5266`,
  `5291-5316`, and `5361-5414`.
- T-987 classifies this as not safe to mix into a small main-branch cleanup.

## Current state and effect map

### State roots

`HomeBentoDashboardPage.tsx:4968-4993` declares the Home-local state involved in
the orchestration risk:

- `activeDrawer`
- `searchQuery`
- `activeTicker`
- `pendingAnalysisTicker`
- `hasHydratedInitialTicker`
- `isDashboardLoading`
- `statusToast`
- guest preview/error/fallback state
- `pendingHistoryDelete`
- `hydratedRouteTaskId`
- trace/full report drawer state
- copy/chart/fundamentals state
- `routeTaskId`, `routeSymbol`, and `routeSource` derived from
  `searchParams`

`HomeBentoDashboardPage.tsx:5000-5018` reads global store state/actions:

- `isAnalyzing`
- `historyItems`
- `selectedReport`
- history refresh/focus/select/delete actions
- task submit/hydrate/sync/refresh actions
- `activeTasks`

### Render-time report mirrors

`HomeBentoDashboardPage.tsx:5035-5064` derives:

- `completedTaskReport`, preferring `routeTaskId` and then
  `pendingAnalysisTicker || activeTicker`
- `focusedTask`, with the same route id first, then ticker, then first active
  task fallback

`HomeBentoDashboardPage.tsx:5073-5121` derives:

- `dashboardData` from trace fixture, guest preview, completed task report,
  selected history report, pending placeholder, or default placeholder
- `activeTraceReport` from trace fixture, completed task report, selected
  history report, or fallback report

These mirrors are render-time derivations today and should remain render-time
derivations after the future write. They should not become copied state.

### Evidence, citation, provenance, and readiness dependencies

`HomeBentoDashboardPage.tsx:5135-5183` derives:

- `activeDecisionTrace`
- `activeReportQuality`
- `activeDataQualityReport`
- `activeResearchReadiness`
- `activeResearchReadinessView`
- `sessionOriginLabel`
- `activeEvidenceCoverageFrame`
- `activeEvidenceCitationFrame`
- `activeSourceProvenanceFrame`
- `activeSingleStockEvidencePacket`
- `sourceSummary`

`HomeBentoDashboardPage.tsx:1381-1490` renders these into:

- `ConsumerResearchReadinessStrip`
- `ConsumerEvidenceCoverageStrip`
- `ConsumerEvidencePacketStrip`
- `HomeSourceProvenanceStrip`
- `HomeEvidenceCitationSummary`

`HomeBentoDashboardPage.tsx:5978-5993` passes the active report mirrors into
`HomeConclusionFirstConsole`.

These dependencies should remain render-time derivation from
`activeTraceReport`. The future write must not move evidence/citation/provenance
normalization into event handlers or reducer state.

### Query-param-driven drawer opening

Current paths:

- `HomeBentoDashboardPage.tsx:4994-4999` derives `traceFixtureReport` from
  `fixture=analysis-trace`.
- `HomeBentoDashboardPage.tsx:5256-5260` opens the trace drawer when
  `trace=open`.
- `HomeBentoDashboardPage.tsx:5262-5266` opens the full report drawer when
  `report=open`.

Classification: must remain effect-driven, but narrow the dependencies in the
future write. This is external route-to-view synchronization for a dev/test
fixture path. It should not enter the main Home reducer unless query-driven
drawers become a product feature.

Risk: both effects depend on the full `searchParams` object and local open
state. They are guarded, so loop risk is low, but they still contribute to the
React Doctor state-in-effect cluster.

Future handling:

- derive primitive booleans such as `shouldAutoOpenTraceDrawer` and
  `shouldAutoOpenReportDrawer` before the effects;
- keep the effects as one-way auto-open only;
- do not auto-close when query params disappear unless explicitly requested.

### Task id / task completion hydration

Current paths:

- `HomeBentoDashboardPage.tsx:5291-5316` detects
  `?symbol=<ticker>&task_id=<id>&source=watchlist`, sets active ticker, marks a
  pending analysis, sets loading, marks initial hydration, remembers
  `hydratedRouteTaskId`, creates a local pending task, and calls
  `refreshTaskProgress`.
- `HomeBentoDashboardPage.tsx:5321-5337` polls `focusedTaskId` until completed
  or failed.
- `HomeBentoDashboardPage.tsx:5392-5414` finds a completed route or pending
  task, then sets active ticker, clears pending/loading, refreshes history, and
  focuses the latest history record for the completed ticker.
- `useDashboardLifecycle.ts:75-98` wires SSE task events into
  `syncTaskCreated`, `syncTaskUpdated`, `syncTaskFailed`, history refresh, and
  task hydration.
- `stockPoolStore.ts:447-485` hydrates recent tasks and refreshes one task's
  progress.
- `stockPoolStore.ts:754-787` upserts task snapshots and caches valid completed
  reports.

Classification: should become reducer/state-machine transitions for the
Home-local state changes, while network/SSE/polling effects remain effect-driven.

Reducer transition candidates:

- `ROUTE_TASK_HYDRATED`
- `TASK_PROGRESS_ATTACHED`
- `TASK_COMPLETED`
- `TASK_FAILED`
- `TASK_CLEARED_OR_IGNORED`

External side effects that should stay outside the reducer:

- `syncTaskCreated`
- `refreshTaskProgress`
- polling interval setup/cleanup
- `refreshHistory(true)`
- `focusLatestHistoryForStock`

Risk: the current route effect batches five local state updates plus a store
mutation and async progress call. The completion effect later clears several of
the same fields. If `selectedReport`, `activeTasks`, or route params change in
between, one render can temporarily combine a stale selected report with a new
pending route task.

### Restored last research display

Current paths:

- `HomeBentoDashboardPage.tsx:5146-5162` derives `sessionOriginLabel` as
  `Last research` / `上次研究` when the user is signed in, no route/task/source
  override exists, no pending analysis exists, and `activeTicker` does not point
  away from the restored ticker.
- `HomeBentoDashboardPage.tsx:5917-5925` renders the label.
- `HomeSurfacePage.test.tsx:715-722` asserts the signed-in conclusion-first
  console displays `上次研究`.

Classification: can remain render-time derivation. Do not store this label in
state and do not turn it into an event-time flag.

Risk: the label is sensitive to `activeTicker`, `pendingAnalysisTicker`, route
params, `selectedReport`, and recent history. If active ticker backfill changes,
this label can disappear or appear incorrectly.

### Active ticker backfill

Current paths:

- `HomeBentoDashboardPage.tsx:5339-5359` schedules a
  `requestAnimationFrame` to set the initial active ticker from selected report,
  recent history, or default ticker.
- `HomeBentoDashboardPage.tsx:5361-5371` backfills `activeTicker` from
  `selectedTicker` if no active ticker exists.
- `HomeBentoDashboardPage.tsx:5422-5436` sets active ticker during manual
  analysis submit.
- `HomeBentoDashboardPage.tsx:5504-5527` sets active ticker during history
  selection.

Classification: should become reducer/state-machine transitions. Some
event-time transitions can dispatch directly, but the initial selected/history
backfill should be a single reducer transition instead of separate effects.

Reducer transition candidates:

- `INITIAL_CONTEXT_READY`
- `MANUAL_ANALYSIS_STARTED`
- `HISTORY_SELECTION_STARTED`
- `ROUTE_TASK_HYDRATED`
- `TASK_COMPLETED`

Risk: two independent backfill effects can race with pending route/manual
analysis. The `requestAnimationFrame` defers one update, which can create a
one-frame mismatch between restored history, pending placeholder, and active
ticker-dependent evidence fetches.

### Pending analysis clear/reset

Current paths:

- `HomeBentoDashboardPage.tsx:5422-5436` sets pending/loading at manual submit.
- `HomeBentoDashboardPage.tsx:5438-5464` clears pending/loading for guest
  preview success/failure.
- `HomeBentoDashboardPage.tsx:5487-5500` clears pending/loading for failed
  signed-in submit.
- `HomeBentoDashboardPage.tsx:5373-5378` clears pending/loading when no route
  task exists and `selectedTicker === pendingAnalysisTicker`.
- `HomeBentoDashboardPage.tsx:5392-5414` clears pending/loading when a matching
  completed task appears.
- `HomeBentoDashboardPage.tsx:5504-5527` clears pending during history
  selection.

Classification: should become reducer/state-machine transitions.

Reducer transition candidates:

- `MANUAL_ANALYSIS_STARTED`
- `MANUAL_ANALYSIS_ACCEPTED`
- `MANUAL_ANALYSIS_DUPLICATE`
- `MANUAL_ANALYSIS_FAILED`
- `GUEST_PREVIEW_RESOLVED`
- `GUEST_PREVIEW_FAILED`
- `HISTORY_SELECTION_STARTED`
- `SELECTED_REPORT_MATCHED_PENDING`
- `TASK_COMPLETED`

Risk: pending/loading state is cleared from success, failure, route, selected
report, and history paths. That makes it hard to prove that Home never shows
stale restored content under a just-submitted ticker.

### Report/result mirror updates

Current paths:

- `HomeBentoDashboardPage.tsx:5035-5048` reads completed task result reports.
- `HomeBentoDashboardPage.tsx:5073-5121` selects dashboard/report mirrors.
- `stockPoolStore.ts:754-782` caches normalized completed task reports.
- `HomeSurfacePage.test.tsx:3179-3285` asserts pending cards update in place
  when a task completes.
- `HomeSurfacePage.test.tsx:3544-3640` asserts snake_case `standard_report`
  payloads hydrate the in-place dashboard.
- `HomeSurfacePage.test.tsx:2577-2716` asserts explicitly opened history detail
  wins over a stale completed task snapshot for the same ticker.

Classification: can become render-time derivation, and mostly already is. The
future write should preserve that design and avoid reducer-owned `dashboardData`
or `activeTraceReport`.

Risk: if the reducer tries to own report selection, it could reverse the current
history-over-stale-task precedence or bypass normal report normalization.

### History drawer trigger and history selection

Current paths:

- `HomeBentoDashboardPage.tsx:5019-5023` uses Safari warm activation to open the
  history drawer.
- `HomeBentoDashboardPage.tsx:5653-5663` renders the history drawer trigger.
- `HomeBentoDashboardPage.tsx:5504-5527` handles history item selection:
  close drawer, clear status/pending, clear store error, set active ticker,
  optionally set loading when no cached snapshot exists, then select persisted
  history detail.
- `HomeBentoDashboardPage.tsx:6079-6181` renders the history drawer and item
  controls.

Classification: should move to event-time transitions for Home-local state
changes. The Safari warm activation hook and the actual drawer open state should
remain untouched unless the future task explicitly scopes it.

Risk: history selection currently mutates drawer, pending, active ticker, and
loading before the store detail fetch resolves. That behavior is intentional for
fast visual response but should be encoded as one transition.

### Provenance/evidence/citation strip rendering dependencies

Current paths:

- `HomeBentoDashboardPage.tsx:903-914` extracts single-stock evidence packets
  from several report locations.
- `HomeBentoDashboardPage.tsx:1171-1243` renders citation summary.
- `HomeBentoDashboardPage.tsx:1245-1379` summarizes and renders source
  provenance.
- `HomeBentoDashboardPage.tsx:1461-1490` renders readiness, coverage, evidence
  packet, provenance, and citations.
- `HomeBentoDashboardPage.tsx:5220-5254` separately fetches fundamentals summary
  by `activeEvidenceTicker`.
- `HomeSurfacePage.test.tsx:680-713` asserts the fundamentals summary remains
  observation-only and hides unavailable metrics.
- `home-scanner-evidence-browser.smoke.spec.ts:611-650`,
  `controlled-user-testing.smoke.spec.ts:1128-1155`, and
  `consumer-copy-regression.smoke.spec.ts:880-895` assert evidence/provenance
  strips are visible, consumer-safe, and free of raw/trading leakage.

Classification:

- report-derived frames: can remain render-time derivation;
- fundamentals network fetch: must remain effect-driven;
- rendered strips: should remain untouched in the first future write.

Risk: active ticker changes also drive `activeEvidenceTicker`, which triggers
the fundamentals fetch. Any one-frame active ticker mismatch can fetch or show
fundamentals for the wrong symbol while the report mirror points elsewhere.

## Classification table

| State path | Current owner | Classification | Future action |
| --- | --- | --- | --- |
| document title from dashboard copy | effect | must remain effect-driven | Leave as-is unless dependencies can be narrowed trivially. |
| stock fundamentals fetch by `activeEvidenceTicker` | effect + local async state | must remain effect-driven | Keep effect; ensure reducer exposes stable active ticker/report input. |
| trace fixture drawer open from query params | effect | must remain effect-driven | Keep one-way auto-open; derive primitive booleans. |
| full report fixture drawer open from query params | effect | must remain effect-driven | Keep one-way auto-open; derive primitive booleans. |
| copy toast reset timer | effect | must remain effect-driven | Leave untouched. |
| status toast reset timer | effect | must remain effect-driven | Leave untouched. |
| zombie storage purge on mount | effect | must remain effect-driven | Leave untouched. |
| dashboard lifecycle hook | hook effects | must remain effect-driven | Leave untouched unless a separate lifecycle task is scoped. |
| focused task polling | effect | must remain effect-driven | Keep effect; feed it reducer-derived focused task identity only. |
| `dashboardData` | `useMemo` | can become render-time derivation | Keep render-time; do not store in reducer. |
| `activeTraceReport` | `useMemo` | can become render-time derivation | Keep render-time; do not store in reducer. |
| readiness/evidence/citation/provenance frames | `useMemo` | can become render-time derivation | Keep render-time; do not store in reducer. |
| restored last research label | `useMemo` | can become render-time derivation | Keep render-time; protect label tests. |
| manual analysis start | event handler | should move to event-time transition | Dispatch `MANUAL_ANALYSIS_STARTED`. |
| manual analysis accepted/duplicate/failed | async event continuation | should move to event-time transition | Dispatch accepted/duplicate/failed transitions. |
| guest preview success/failure | async event continuation | should move to event-time transition | Dispatch guest-specific resolved/failed transitions or keep guest local branch isolated. |
| history drawer item selection | event handler | should move to event-time transition | Dispatch `HISTORY_SELECTION_STARTED` and completion/failure if needed. |
| route watchlist task hydration | effect | should become reducer/state-machine transition | Effect detects external route once, reducer owns local state updates. |
| initial active ticker backfill | effects | should become reducer/state-machine transition | Collapse both backfill effects into one guarded transition. |
| pending clear when selected report matches | effect | should become reducer/state-machine transition | Encode as explicit transition with route guard. |
| task completion local clear/focus | effect | should become reducer/state-machine transition | Reducer clears local pending/loading; effect still refreshes/focuses history. |
| active drawer for strategy/tech/fundamentals | event state | should remain untouched | Keep simple UI state out of orchestration reducer for first write. |
| trace/full report drawer manual open | event state | should remain untouched | Leave existing button behavior. |
| history drawer open/close | event state | should remain untouched | Leave drawer state except history selection event may close it. |
| chart context from chart callback | child callback state | should remain untouched | Do not change chart behavior. |
| delete confirmation state | event state | should remain untouched | Out of scope. |

## Minimal future write plan

### Goal

Reduce React Doctor `no-adjust-state-on-prop-change` and
`no-chain-state-updates` risk in Home without changing product behavior.

### Allowed files for the future write task

Minimum allowed final diff:

- `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx`

Optional only if the implementation extracts a pure reducer for targeted tests:

- `apps/dsa-web/src/pages/homeDashboardOrchestration.ts`
- `apps/dsa-web/src/pages/__tests__/homeDashboardOrchestration.test.ts`

Do not allow these files unless explicitly scoped:

- API clients
- backend code
- store implementation
- shared report/evidence/readiness types
- `HomeCandlestickChart.tsx`
- global CSS/design primitives
- e2e fixture helpers
- config, lockfile, CI, or changelog files

### Step 1: add a Home-local orchestration reducer

Create a narrow reducer/state-machine for only:

- `activeTicker`
- `pendingAnalysisTicker`
- `hasHydratedInitialTicker`
- `isDashboardLoading`
- `hydratedRouteTaskId`

Do not include:

- `dashboardData`
- `activeTraceReport`
- evidence/citation/provenance frames
- drawer state
- chart state
- guest preview payloads
- store-owned task/history state

### Step 2: move event-time state batches into transitions

Replace grouped `setState` calls in:

- manual submit start/success/failure;
- guest preview resolution/failure;
- history selection start;
- route watchlist task hydration.

The event handlers may still call store/API actions. The reducer should own only
the Home-local view state before and after those calls.

### Step 3: collapse prop/store-driven backfill effects

Replace the separate initial ticker and selected ticker backfill effects with a
single guarded transition based on a derived snapshot:

- selected ticker;
- recent history first ticker;
- default ticker;
- current pending/route state.

The transition must be idempotent and must not run while a route task or pending
manual analysis owns the surface.

### Step 4: encode task completion clear as one transition

Keep the effect that detects a completed route/pending task, but make it dispatch
one local completion transition. Keep these side effects outside the reducer:

- `refreshHistory(true)`
- `focusLatestHistoryForStock(completedTicker)`

### Step 5: keep report mirrors and evidence strips render-derived

Leave `dashboardData`, `activeTraceReport`, readiness, evidence, citation, and
provenance frame derivations as `useMemo` values. Only adjust their dependencies
if the reducer state changes the variable names.

### Step 6: run React Doctor as a diagnostic, not a landing gate

After the future write, run React Doctor and compare the Home diagnostics around
the audited region. The goal is fewer `no-adjust-state-on-prop-change` and
`no-chain-state-updates` hits in Home, but the landing gate should be behavior
tests and e2e smoke, not a zero-diagnostic React Doctor run.

## Required future validation

Unit/focused tests:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx --run
npm --prefix apps/dsa-web run test -- src/stores/__tests__/stockPoolStore.test.ts --run
npm --prefix apps/dsa-web run test -- src/hooks/__tests__/useDashboardLifecycle.test.tsx --run
```

Frontend build/design:

```bash
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run build
npm --prefix apps/dsa-web run check:design
```

Home-focused e2e smoke:

```bash
npm --prefix apps/dsa-web run test:e2e -- e2e/home-scanner-evidence-browser.smoke.spec.ts --project=chromium
npm --prefix apps/dsa-web run test:e2e -- e2e/controlled-user-testing.smoke.spec.ts --project=chromium
npm --prefix apps/dsa-web run test:e2e -- e2e/consumer-copy-regression.smoke.spec.ts --project=chromium
```

Optional route-task focused unit additions, if reducer extraction changes the
route/task path:

- add or update assertions in `HomeSurfacePage.test.tsx` that cover:
  - `/?symbol=WULF&task_id=task-wulf&source=watchlist&market=US` processing
    state;
  - route progress payloads with `modules: null`;
  - completed route task report display;
  - stale selected/history report not winning over route task.

Final hygiene:

```bash
git diff --check
./scripts/release_secret_scan.sh
git status --short --branch
```

## Protected behavior invariants

The future write must preserve:

- Home search command behavior unchanged:
  - valid ticker submit starts in-place analysis;
  - invalid ticker shows the existing formatted ticker error;
  - input clears on accepted submit;
  - duplicate task behavior remains unchanged;
  - guest preview behavior remains unchanged.
- Task/report lifecycle unchanged:
  - route watchlist task handoff remains keyed by `task_id` / `taskId` and
    `symbol`;
  - task progress polling remains bounded to the focused task;
  - completed task reports hydrate in place;
  - persisted history detail can override stale completed task snapshots;
  - no auto-scroll is introduced after completion.
- Restored research labeling unchanged:
  - `Last research` / `上次研究` appears only for restored signed-in research
    with no route/source/task/pending override.
- Evidence packet, citation, and provenance frame rendering unchanged:
  - `home-evidence-packet-strip`, `home-evidence-coverage-strip`,
    `home-provenance-strip`, and optional `home-evidence-citation-strip`
    keep existing visibility, labels, safety copy, and negative leakage
    behavior.
- Chart behavior unchanged:
  - daily OHLC fetch and chart rendering remain as-is;
  - timeframe, indicator, tooltip, unavailable-copy, and mobile chart behavior
    remain protected by existing tests;
  - no changes to `HomeCandlestickChart.tsx` in the first orchestration write.
- No LLM/provider/cache/API behavior changed:
  - no API response shape changes;
  - no provider order, fallback, freshness, cache, or MarketCache semantics
    changed;
  - no LLM prompt, model routing, retry, or recommendation semantics changed;
  - no auth/RBAC behavior changed;
  - no raw provider/schema/debug/task internals exposed.

## Stop conditions for the future write

Stop and request user review if any of these become necessary:

- modifying API clients, backend endpoints, provider/cache/runtime code, LLM
  prompts, shared schemas, shared report/evidence/readiness types, auth/RBAC, or
  global store behavior;
- changing `HomeCandlestickChart.tsx` or chart fetch/aggregation behavior;
- changing e2e fixtures broadly instead of adding narrow Home route/task
  assertions;
- changing visual hierarchy, shell primitives, global CSS, or Home layout
  taxonomy;
- removing or renaming existing Home test IDs used by e2e or unit tests;
- making route query params auto-close drawers or otherwise changing current
  route-driven drawer semantics;
- changing history-vs-task report precedence without a specific user-approved
  behavior decision;
- weakening no-advice, evidence, citation, or provenance safety copy;
- needing config, dependency, lockfile, CI, or changelog changes;
- React Doctor improvements require behavior changes instead of state ownership
  cleanup.

## Future task prompt seed

```text
Task: Home state orchestration reducer refactor
Mode: CODEX-ISOLATED
Allowed final diff:
- apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx
- apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx
- optional: apps/dsa-web/src/pages/homeDashboardOrchestration.ts
- optional: apps/dsa-web/src/pages/__tests__/homeDashboardOrchestration.test.ts

Goal:
Collapse Home-local route/task/pending/activeTicker orchestration into explicit
event-time and reducer/state-machine transitions. Preserve render-derived
dashboard/report/evidence mirrors and all product behavior.

Forbidden:
- backend/API/provider/cache/LLM/auth/schema/shared type changes
- Home chart behavior changes
- e2e fixture rewrites
- visual redesign
- config/lockfile/CI/changelog changes

Required validation:
- npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx --run
- npm --prefix apps/dsa-web run test -- src/stores/__tests__/stockPoolStore.test.ts --run
- npm --prefix apps/dsa-web run test -- src/hooks/__tests__/useDashboardLifecycle.test.tsx --run
- npm --prefix apps/dsa-web run lint
- npm --prefix apps/dsa-web run build
- npm --prefix apps/dsa-web run check:design
- npm --prefix apps/dsa-web run test:e2e -- e2e/home-scanner-evidence-browser.smoke.spec.ts --project=chromium
- npm --prefix apps/dsa-web run test:e2e -- e2e/controlled-user-testing.smoke.spec.ts --project=chromium
- npm --prefix apps/dsa-web run test:e2e -- e2e/consumer-copy-regression.smoke.spec.ts --project=chromium
- git diff --check
- ./scripts/release_secret_scan.sh
- git status --short --branch
```

## Audit conclusion

Proceed with a future isolated Home-local refactor only if the scope stays inside
the allowed files above and preserves all invariants. The first write should not
try to decompose the 6207-line page, touch the chart, change evidence rendering,
or chase all React Doctor diagnostics. Its value is reducing ambiguous
effect-chain ownership around route task hydration, pending clearing, active
ticker backfill, and task completion without changing the Home product surface.
