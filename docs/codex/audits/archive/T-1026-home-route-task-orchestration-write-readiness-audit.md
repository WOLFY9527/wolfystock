# T-1026 Home route task orchestration write-readiness audit

Task ID: T-1026-AUDIT

Task title: Home route task orchestration write-readiness audit

Mode: READ-ONLY-AUDIT with one explicitly allowed audit artifact.

Allowed artifact: `docs/codex/audits/T-1026-home-route-task-orchestration-write-readiness-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1026-home-orchestration-readiness-audit`
- branch: `codex/t1026-home-orchestration-readiness-audit`
- HEAD before this audit artifact: `7658ab01` (`test(web): add market authority copy smoke`)
- After `git fetch origin`, `origin/main` was `6f4d03d7`
  (`fix(web): require system settings reset confirmation`), one commit ahead of
  the selected branch. The selected branch was not rebased, merged, switched, or
  updated before writing this artifact.

Scope boundary:

- Source, tests, config, package, lockfile, API, backend, provider, cache, runtime,
  auth, route behavior, scanner, portfolio, options, backtest, and market files
  were inspected only.
- The exact requested T-989 file,
  `docs/codex/audits/T-989-home-state-orchestration-audit.md`, was not present.
  The adjacent tracked audit
  `docs/codex/audits/T-989-home-state-orchestration-risk-audit.md` was present
  and used as stale-risk context.

## Readiness verdict

Ready for one bounded Home-local write, but not ready for a broad reducer or
state-machine rewrite.

The smallest safe write is to extract and test a pure Home report/task selection
helper that encodes the current precedence among route task, completed task
report, selected history report, pending placeholder, and restored/default
ticker. That is the narrowest step that reduces the remaining correctness risk
without changing data fetching, report rendering, LLM lifecycle, drawer behavior,
or provider/API/runtime semantics.

Do not start by moving all Home state into a reducer. Current tests already cover
many of the failure modes T-989 called out, and a broad rewrite would touch too
many independent effects before the report precedence contract is explicit.

## Evidence inspected

Required docs:

- `AGENTS.md`
- `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`
- `docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`
- `docs/codex/audits/T-1014-post-ux-wave-platform-roadmap-audit.md`
- `docs/codex/audits/T-989-home-state-orchestration-risk-audit.md`

Home code and task lifecycle:

- `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`
- `apps/dsa-web/src/pages/HomeSurfacePage.tsx`
- `apps/dsa-web/src/pages/GuestHomePage.tsx`
- `apps/dsa-web/src/hooks/useDashboardLifecycle.ts`
- `apps/dsa-web/src/hooks/useTaskStream.ts`
- `apps/dsa-web/src/stores/stockPoolStore.ts`
- `apps/dsa-web/src/api/analysis.ts`
- `apps/dsa-web/src/types/analysis.ts`
- `apps/dsa-web/src/utils/taskQueue.ts`

Display/report helpers and tests:

- `apps/dsa-web/src/utils/homeReportIdentity.ts`
- `apps/dsa-web/src/components/home-bento/FullDecisionReportDrawer.tsx`
- `apps/dsa-web/src/components/home-bento/DeepReportDrawer.tsx`
- `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx`
- `apps/dsa-web/src/stores/__tests__/stockPoolStore.test.ts`
- `apps/dsa-web/src/hooks/__tests__/useDashboardLifecycle.test.tsx`
- `apps/dsa-web/src/hooks/__tests__/useTaskStream.test.tsx`
- `apps/dsa-web/src/utils/__tests__/taskQueue.test.ts`
- Home-focused e2e smokes for chart, fundamentals, evidence, copy, and controlled
  user testing.

## Current risk map

### Display extraction

Low immediate write priority.

Home still has a large amount of display extraction inside
`HomeBentoDashboardPage.tsx`, including report quality, evidence packet,
decision trace, normalized dashboard payload, drawer payload, and timeline
builders. Some extraction already exists in `homeReportIdentity.ts`,
`FullDecisionReportDrawer.tsx`, chart components, and Home-focused tests.

Likely user-visible failures here are mostly stale or already guarded:

- sparse completed reports render neutral values instead of demo presets;
- snake_case completed task payloads normalize before display;
- evidence, citation, provenance, and fundamentals copy stay consumer-safe;
- chart unavailable states hide raw provider diagnostics.

Do not make display extraction the immediate write unless it is a pure helper
with focused tests. Avoid moving consumer-safety normalization into event
handlers or task state.

### State orchestration

Highest remaining risk.

The Home route reads many local state roots in the same component:
`activeTicker`, `pendingAnalysisTicker`, `hasHydratedInitialTicker`,
`isDashboardLoading`, `hydratedRouteTaskId`, drawer flags, guest preview state,
chart context, and stock evidence loading state. It also reads global
`selectedReport`, `historyItems`, `activeTasks`, and task/history actions from
`stockPoolStore`.

The remaining risk is not "Home has many states" by itself. The concrete risk is
that the visible report is selected by render-time precedence across:

- `routeTaskId` / `routeSymbol`;
- `completedTaskReport`;
- `selectedReport`;
- `pendingAnalysisTicker`;
- `activeTicker`;
- recent history fallback.

That precedence is currently embedded in `completedTaskReport`,
`focusedTask`, `dashboardData`, `activeTraceReport`, `activeEvidenceTicker`,
`reanalysisTicker`, `sessionOriginLabel`, and completion effects. A small pure
helper can lock the intended precedence before any larger state refactor.

### Data fetching

Not an immediate write target.

Data fetching is split across:

- Home evidence fetch by `activeEvidenceTicker`;
- chart history fetch inside Home chart components;
- history load/refresh/focus in `stockPoolStore`;
- task list/progress API calls;
- SSE task stream.

Current coverage already protects several data-fetching boundaries:

- no extra history re-analysis when a history row is clicked;
- cached history snapshot can render first, then database detail wins;
- completed task reports are normalized before caching;
- route task progress can omit modules without unmounting the running state.

The next write should not change fetch endpoints, polling intervals, SSE wiring,
API clients, stock evidence adapter behavior, chart requests, or history store
semantics.

### LLM/report lifecycle

Medium risk, but mostly covered enough for a narrow helper write.

Current tests cover:

- valid manual submit starts in-place loading and calls `analyzeAsync`;
- malformed ticker input does not call validation or analysis;
- API failure leaves neutral cards instead of local demo content;
- duplicate task handling stays store-owned;
- async task completion replaces pending cards in place;
- snake_case `standard_report` task payloads hydrate the in-place dashboard;
- watchlist route task completion loads the routed task report.

The remaining uncovered concern is a precedence contract, not LLM execution
itself. The next write must not touch prompts, model routing, fallback,
provider/cache behavior, backend report generation, or public API shape.

### Drawer state

Low immediate priority.

Drawer state is mostly local UI state: strategy/fundamentals/tech drill-down,
trace drawer, full report drawer, history drawer, and delete confirmation. Tests
already cover right-rail drill-down restoration, tech drawer synchronization,
full report rendering, decision trace fallback, and history drawer item
selection.

Do not include drawer state in the first write. A reducer rewrite that absorbs
drawer state would expand the blast radius without addressing the route/task
precedence risk.

## Stale or lower-priority risks after recent test cleanup

These T-989-era risks are now lower priority:

- Watchlist route handoff is not untested: tests cover running route state,
  missing progress modules, and completed routed task report display.
- Pending-to-completed analysis is not untested: tests cover manual submit,
  in-place pending cards, completed task replacement, and snake_case payloads.
- History-vs-task precedence has some coverage: persisted history detail wins
  over a stale task snapshot for the same ticker.
- Display/provenance extraction is less urgent than it looked before T-874,
  T-879, T-926, T-936, T-985, T-996, and later Home test cleanup because the
  visible Home evidence, fundamentals, chart, and consumer-copy smokes now exist.
- Drawer state should not be treated as part of route/task orchestration for the
  first write.

Still active:

- The page remains 6207 lines, and report selection precedence is still spread
  across page-local state, store snapshots, and effects.
- `activeEvidenceTicker` is derived from the active report/ticker mix; if future
  edits change precedence incorrectly, evidence fetches can target one ticker
  while the visible report points at another.
- Route task completion still triggers local state clearing plus history refresh
  and latest-history focus; a future change needs explicit tests to prevent stale
  selected history from winning over the routed task.

## Immediate write task

Recommend one immediate write:

**T-1026-WRITE: Extract Home report task selection helper**

Goal:

- Make Home's current report/ticker precedence explicit and testable.
- Keep behavior unchanged.
- Reduce the risk of future route/task orchestration edits before any reducer or
  state-machine work.

Smallest safe implementation:

1. Add a pure helper near Home page code, for example
   `apps/dsa-web/src/pages/homeDashboardSelection.ts`.
2. Move only the pure selection logic currently embedded in
   `completedTaskReport`, `focusedTask`, `dashboardData`, `activeTraceReport`,
   `activeEvidenceTicker`, and `reanalysisTicker` as needed.
3. Add focused unit tests for route task precedence, pending ticker precedence,
   selected history fallback, stale completed task rejection, no-symbol rerun
   disablement, and active evidence ticker alignment.
4. Wire `HomeBentoDashboardPage.tsx` to the helper with no UI copy, API, fetch,
   drawer, chart, store, or lifecycle behavior changes.

Allowed files for that future write:

- `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`
- `apps/dsa-web/src/pages/homeDashboardSelection.ts`
- `apps/dsa-web/src/pages/__tests__/homeDashboardSelection.test.ts`
- `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx`

Forbidden files for that future write unless a new prompt explicitly scopes
them:

- API clients and shared response types
- backend/API/provider/cache/runtime/auth code
- `stockPoolStore.ts`
- `useDashboardLifecycle.ts`
- `useTaskStream.ts`
- chart components and chart utilities
- `FullDecisionReportDrawer.tsx`, `DeepReportDrawer.tsx`, and shared drawer
  primitives
- scanner, portfolio, options, backtest, market, watchlist pages
- config, package, lockfile, CI, docs changelog, or global CSS/design primitives

Do not propose or implement a broad reducer/state-machine rewrite until the
helper and tests prove the exact precedence contract is preserved and still
insufficient.

## Validation plan for the future write

Focused unit tests:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/homeDashboardSelection.test.ts --run
npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx --run
npm --prefix apps/dsa-web run test -- src/stores/__tests__/stockPoolStore.test.ts --run
npm --prefix apps/dsa-web run test -- src/hooks/__tests__/useDashboardLifecycle.test.tsx --run
npm --prefix apps/dsa-web run test -- src/hooks/__tests__/useTaskStream.test.tsx --run
```

Home-focused e2e smoke:

```bash
npm --prefix apps/dsa-web run test:e2e -- e2e/home-scanner-evidence-browser.smoke.spec.ts --project=chromium
npm --prefix apps/dsa-web run test:e2e -- e2e/home-fundamentals-summary.spec.ts --project=chromium
npm --prefix apps/dsa-web run test:e2e -- e2e/home-chart-browser.smoke.spec.ts --project=chromium
npm --prefix apps/dsa-web run test:e2e -- e2e/controlled-user-testing.smoke.spec.ts --project=chromium
```

Landing gates:

```bash
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run build
npm --prefix apps/dsa-web run check:design
git diff --check
./scripts/release_secret_scan.sh
```

Regression assertions that must stay true:

- route task query params win over stale selected history while running;
- completed routed task report wins for the routed task id;
- persisted history detail wins after explicit history selection;
- manual pending analysis shows in-place loading and never local demo content;
- selected/current evidence ticker matches the visible report ticker;
- no raw provider/runtime/model/progress internals leak onto Home;
- fundamentals, provenance, chart, and report drawer consumer-safety copy remain
  unchanged.

## Deferrals

Defer these tasks:

- broad Home reducer/state-machine rewrite;
- display extraction beyond pure selection helper support;
- drawer-state refactor;
- store lifecycle rewrite;
- SSE/polling/history hydration changes;
- API/schema/backend/provider/cache/runtime changes;
- any Home visual rewrite or route/auth behavior change.
