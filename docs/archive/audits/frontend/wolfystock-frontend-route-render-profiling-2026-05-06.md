# WolfyStock Frontend Route Render Profiling

Date: 2026-05-06 Asia/Shanghai  
Repository: `/Users/yehengli/daily_stock_analysis`  
Branch: `main`  
Mode: report only; no product code, tests, CSS, backend/API, package, config, runtime, or changelog changes

## 1. Executive Summary

Highest-risk routes:

- `/zh/market-overview`: highest API fan-out in the profile, one SSE connection, and the only route with repeated panel fetches across 18 requests.
- `/zh/settings/system`: many derived `useMemo`/`useCallback` branches and the densest route-local config state; likely to benefit from local memo/data-shape cleanup.
- `/zh/backtest/results/1`: lazy-loaded result route with the large `DeterministicBacktestChartWorkspace` chunk and multiple polling/effect paths.
- `/zh/scanner`: duplicate `GET /api/v1/scanner/runs` on initial render.
- `/zh`: task stream SSE connection on every load and a large home/dashboard render surface.

Already acceptable:

- `/zh/watchlist`
- `/zh/portfolio`
- `/zh/admin/logs`
- `/zh/admin/notifications`
- `/zh/chat`
- `/zh/__preview/report`

Biggest no-code opportunities:

- dedupe repeated initial fetches for scanner/history/backtest route entry
- reduce route-local derived state in `SettingsPage.tsx`, `UserScannerPage.tsx`, and `HomeBentoDashboardPage.tsx`
- review route entry polling/SSE behavior on Home and Market Overview
- split or defer the largest lazy route chunk further if product work later allows it

No-code-change confirmation:

- this task only created this report
- no product code, tests, CSS, backend/API, package, config, runtime, or changelog files were modified by this profiling pass

## 2. Methodology

Commands run:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -180
./scripts/task_preflight.sh || true

lsof -i :8000
lsof -i :8001
lsof -i :5173
lsof -i :4173
lsof -i :5174
lsof -i :5175
lsof -i :5176

cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
npm run check:design
npm run lint
npm run build

cd /Users/yehengli/daily_stock_analysis
python3 -m compileall -q src api

cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
rg -n "useEffect|useMemo|useCallback|fetch\\(|EventSource|setInterval|setTimeout|requestAnimationFrame|lazy\\(|Suspense|memo\\(|React\\.memo|useQuery|mutate|performance|PerformanceObserver|console\\.time|api\\." src/pages src/components src/api src/hooks src/utils | head -1200
```

Playwright strategy:

- isolated Vite preview on `http://127.0.0.1:5176`
- browser: headless Chromium through the app-local Playwright install
- viewports: desktop `1440x1000`, mobile `390x844`
- routes profiled:
  - `/zh`
  - `/zh/scanner`
  - `/zh/watchlist`
  - `/zh/backtest`
  - `/zh/backtest/results/1`
  - `/zh/portfolio`
  - `/zh/market-overview`
  - `/zh/settings`
  - `/zh/settings/system`
  - `/zh/admin/logs`
  - `/zh/admin/notifications`
  - `/zh/chat`
  - `/zh/__preview/report`

Mock strategy:

- authenticated admin state was mocked in `localStorage`/`sessionStorage`
- all `/api/**` traffic was intercepted and returned mocked JSON
- `EventSource` was stubbed so Home and Market Overview could render without real streaming
- write-like calls were never exercised against real services

Limitations:

- this is a mock-profile, not a live-data profile
- route timings are approximate browser-side content times, not production RUM
- some route payloads are intentionally simplified; this is enough to compare render behavior, not to validate domain correctness

Ports:

| Port | Status | Use |
| --- | --- | --- |
| `8000` | already in use | existing Python listener, not touched |
| `8001` | free | not used |
| `5173` | already in use | existing frontend listener, not touched |
| `4173` | free | not used |
| `5174` | free | not used |
| `5175` | free | not used |
| `5176` | isolated preview | used for this profiling pass |

## 3. Static Render-Risk Inventory

| File / route | Observed patterns | Risk | Recommended investigation / fix |
| --- | --- | --- | --- |
| `src/pages/HomeBentoDashboardPage.tsx` / `/zh` | many `useMemo`, `useEffect`, timers, `setInterval`, `requestAnimationFrame` around route hydration and task/report syncing | medium | inspect whether task/report derivations can be flattened and whether the task stream can avoid redundant route-entry work |
| `src/pages/UserScannerPage.tsx` / `/zh/scanner` | heavy `useMemo` graph, multiple `useEffect` fetches, history loading, candidate derivations, backtest batch helpers | high | dedupe initial history/run fetches and review the candidate derivation chain for local memoization boundaries |
| `src/pages/WatchlistPage.tsx` / `/zh/watchlist` | moderate `useEffect`/`useMemo` usage with refresh and batch actions | low/medium | no immediate render problem; keep under watch if batch logic grows |
| `src/pages/BacktestPage.tsx` / `/zh/backtest` | several `useEffect` and `useMemo` blocks for results/history/performance views | medium | check if repeated derived views can be shared across entry and result flows |
| `src/pages/DeterministicBacktestResultPage.tsx` / `/zh/backtest/results/:runId` | many derived `useMemo` branches, polling, `setInterval`, lazy result workspace split | high | review polling necessity and whether a lighter route shell can load before chart workspace hydration |
| `src/pages/PortfolioPage.tsx` / `/zh/portfolio` | many `useEffect` and `useMemo` branches around accounts, FX, positions, and editing flows | medium | watch for repeated snapshot/risk derivations when populated data gets heavier |
| `src/pages/MarketOverviewPage.tsx` / `/zh/market-overview` | `useEffect`, `setInterval`, `EventSource`, many panel-derived `useMemo` helpers | high | dedupe panel boot fetches and re-check whether stream fallback paths can avoid extra initial churn |
| `src/pages/SettingsPage.tsx` / `/zh/settings` and `/zh/settings/system` | by far the densest `useMemo`/`useCallback` surface in the app | high | split expensive local derivations by panel and keep config sections from recomputing unrelated branches |
| `src/pages/AdminLogsPage.tsx` / `/zh/admin/logs` | moderate memoization and filtered session derivations | low/medium | acceptable today; watch for growth in filters and detail panes |
| `src/pages/AdminNotificationsPage.tsx` / `/zh/admin/notifications` | lighter effect/memo footprint | low | acceptable today |
| `src/pages/ChatPage.tsx` / `/zh/chat` | `useMemo`/`useCallback` for smart routing, sessions, evidence, send/stop flows; timered toasts | medium | acceptable, but repeated route-entry fetches should stay bounded if session history grows |
| `src/pages/PreviewReportPage.tsx` / `/zh/__preview/report` | small memo footprint and preview-only shell path | low | acceptable today |
| `src/components/report/ReportPriceChart.tsx` | repeated chart geometry, ticks, and animation-ish effect work | medium/high | if chart jank appears, this is the first chart-local place to inspect |
| `src/hooks/useTaskStream.ts` | EventSource creation, reconnect timers, cleanup effects | medium | stream behavior should be kept deliberate; check reconnection cost if task traffic rises |
| `src/App.tsx` | route-level `lazy()` boundaries for large pages | medium | route chunking is already in place; further split only if future UX work justifies it |

## 4. Route Profiling Matrix

| Route | Viewport | Render status | Route content time | API request count | Duplicate endpoints | Console/page errors | Horizontal overflow | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/zh` | desktop | PASS | 269 ms | 4 | `GET /api/v1/analysis/tasks/stream` opened once | none | 0 | Home opened the task stream SSE; render was stable. |
| `/zh` | mobile | PASS | 158 ms | 4 | `GET /api/v1/analysis/tasks/stream` opened once | none | 0 | Same as desktop; no overflow. |
| `/zh/scanner` | desktop | PASS | 249 ms | 6 | `GET /api/v1/scanner/runs` x2 | none | 0 | Duplicate history fetch on entry is the clearest no-code optimization candidate. |
| `/zh/scanner` | mobile | PASS | 143 ms | 6 | `GET /api/v1/scanner/runs` x2 | none | 0 | Same duplicate fetch pattern on mobile. |
| `/zh/watchlist` | desktop | PASS | 236 ms | 3 | none | none | 0 | Stable and comparatively lean. |
| `/zh/watchlist` | mobile | PASS | 156 ms | 3 | none | none | 0 | Stable and comparatively lean. |
| `/zh/backtest` | desktop | PASS | 161 ms | 5 | none | none | 0 | Moderate route cost, no instability. |
| `/zh/backtest` | mobile | PASS | 159 ms | 5 | none | none | 0 | Similar to desktop. |
| `/zh/backtest/results/1` | desktop | PASS | 251 ms | 3 | none | none | 0 | Lazy result route loaded cleanly; chart workspace chunk is the large one to watch. |
| `/zh/backtest/results/1` | mobile | PASS | 170 ms | 3 | none | none | 0 | Same result route stability on mobile. |
| `/zh/portfolio` | desktop | PASS | 154 ms | 6 | none | none | 0 | Stable and readable; no obvious repeated fetch loop. |
| `/zh/portfolio` | mobile | PASS | 173 ms | 6 | none | none | 0 | Stable and readable. |
| `/zh/market-overview` | desktop | PASS | 162 ms | 18 | `GET /api/v1/market/*` panels x2 across desktop/mobile profile, SSE opened once | none | 0 | Heaviest initial API fan-out in the profile. |
| `/zh/market-overview` | mobile | PASS | 157 ms | 18 | same panel fan-out | none | 0 | SSE opened once; no visible instability. |
| `/zh/settings` | desktop | PASS | 146 ms | 2 | none | none | 0 | Low API cost; heavy local derivation is static-code-driven rather than request-driven. |
| `/zh/settings` | mobile | PASS | 148 ms | 2 | none | none | 0 | Stable. |
| `/zh/settings/system` | desktop | PASS | 250 ms | 4 | none | none | 0 | Dense config surface; the render cost is mostly derived state, not network. |
| `/zh/settings/system` | mobile | PASS | 256 ms | 4 | none | none | 0 | Same note as desktop. |
| `/zh/admin/logs` | desktop | PASS | 174 ms | 3 | none | none | 0 | Stable. |
| `/zh/admin/logs` | mobile | PASS | 173 ms | 3 | none | none | 0 | Stable. |
| `/zh/admin/notifications` | desktop | PASS | 168 ms | 3 | none | none | 0 | Stable. |
| `/zh/admin/notifications` | mobile | PASS | 169 ms | 3 | none | none | 0 | Stable. |
| `/zh/chat` | desktop | PASS | 156 ms | 5 | none | none | 0 | Moderate fetch cost, but no error or overflow signal. |
| `/zh/chat` | mobile | PASS | 165 ms | 5 | none | none | 0 | Stable. |
| `/zh/__preview/report` | desktop | PASS | 151 ms | 0 | none | none | 0 | Pure preview shell load; no API fan-out from this mock profile. |
| `/zh/__preview/report` | mobile | PASS | 168 ms | 0 | none | none | 0 | Stable. |

## 5. Findings

### High priority

- `/zh/market-overview` is the heaviest route in the profile by request fan-out. It opens one SSE stream and fires 18 API requests on initial render. That is the strongest candidate for request dedupe or staged loading.
- `/zh/scanner` issues `GET /api/v1/scanner/runs` twice on entry. That is a concrete duplicate request pattern with immediate no-code optimization potential.
- `/zh/backtest/results/1` is already stable, but the route depends on the large lazy chart workspace chunk. It is the clearest candidate for future chunk split work if product scope allows it.
- `/zh/settings/system` has a very large derived-state surface. The cost is mostly local computation, not network, so it is the first route to revisit if UI lag shows up.

### Medium priority

- `/zh` and `/zh/market-overview` both use EventSource. Their stream behavior is stable in the mock run, but any further data growth should keep reconnect and cleanup cost under review.
- `/zh/chat` and `/zh/portfolio` are acceptable now, but both have enough local derivation to justify future memo/data-shape hygiene if they get heavier.
- `ReportPriceChart` is the main chart-local candidate for expensive geometry/tick computation if a chart-specific jank report appears.

### Low priority

- `/zh/watchlist`
- `/zh/backtest`
- `/zh/admin/logs`
- `/zh/admin/notifications`
- `/zh/__preview/report`

### No action needed

- no route showed horizontal overflow at either viewport
- no route produced console or page errors in the final profiled run
- no route failed to render under the mocked authenticated/admin setup

## 6. Optimization Recommendations

- Dedupe scanner entry fetches so the route does not request history twice on initial render.
- Stage Market Overview panel boot so the heaviest panels do not all load at once when the route first opens.
- Review `SettingsPage.tsx` for local derived-state partitioning by section; it is the biggest memo/callback hotspot in the repo.
- Keep Home and Market Overview stream behavior deliberate; treat EventSource setup and cleanup as a first-class cost.
- Consider route-level profiling tests for scanner, market overview, and backtest result routes so request duplication shows up before manual profiling.
- If future product work is allowed, split the deterministic backtest chart workspace chunk further.

## 7. Recommended Next Implementation Tasks

1. Deduplicate `/zh/scanner` initial history loading.
   Scope: `UserScannerPage.tsx` only.
   Safety constraints: no scoring logic changes, no route-shape changes, no backend/API changes.

2. Partition `SettingsPage.tsx` derived state by panel.
   Scope: local memo/callback cleanup in settings only.
   Safety constraints: preserve config semantics, raw/system visibility rules, and existing route behavior.

3. Stage a Market Overview fetch profile pass.
   Scope: load order and data-layer dedupe investigation for Market Overview only.
   Safety constraints: no live-provider changes, no backend/API changes, no visual redesign.

## 8. Non-Goals

- no code changed
- no tests changed
- no CSS changed
- no backend/API changed
- no package files or config changed
- no real provider or LLM calls were made
- no scanner runs, portfolio writes, notifications, or DuckDB writes were executed
- no generated traces, screenshots, or videos were committed

## 9. Appendix

Top endpoint counts from the mock profile:

```text
24  GET /api/v1/auth/status
4   GET /api/v1/watchlist/items
4   GET /api/v1/scanner/runs
4   GET /api/v1/backtest/rule/runs
2   GET /api/v1/history
2   GET /api/v1/analysis/tasks
2   GET /api/v1/history/:id
2   GET /api/v1/scanner/themes
2   GET /api/v1/scanner/runs/:id
2   GET /api/v1/watchlist/refresh-status
2   GET /api/v1/backtest/performance
2   GET /api/v1/backtest/results
2   GET /api/v1/backtest/runs
2   GET /api/v1/backtest/rule/runs/:id
2   GET /api/v1/portfolio/accounts
2   GET /api/v1/portfolio/imports/brokers
2   GET /api/v1/portfolio/snapshot
2   GET /api/v1/portfolio/trades
2   GET /api/v1/portfolio/risk
2   GET /api/v1/market-overview/indices
2   GET /api/v1/market-overview/volatility
2   GET /api/v1/market/crypto
2   GET /api/v1/market/sentiment
2   GET /api/v1/market-overview/funds-flow
2   GET /api/v1/market-overview/macro
2   GET /api/v1/market/cn-indices
2   GET /api/v1/market/cn-breadth
2   GET /api/v1/market/cn-flows
2   GET /api/v1/market/sector-rotation
2   GET /api/v1/market/us-breadth
2   GET /api/v1/market/rates
2   GET /api/v1/market/fx-commodities
2   GET /api/v1/market/temperature
2   GET /api/v1/market/market-briefing
2   GET /api/v1/market/futures
2   GET /api/v1/market/cn-short-sentiment
2   GET /api/v1/auth/preferences/notifications
2   GET /api/v1/quant/duckdb/health
2   GET /api/v1/quant/duckdb/coverage
2   GET /api/v1/system/config
2   GET /api/v1/admin/logs
2   GET /api/v1/admin/logs/storage/summary
2   GET /api/v1/admin/notification-channels
2   GET /api/v1/admin/notifications
2   GET /api/v1/agent/chat/sessions
2   GET /api/v1/agent/skills
2   GET /api/v1/agent/models
2   GET /api/v1/agent/provider-health
```

Route-level SSE behavior:

- `/zh`: `GET /api/v1/analysis/tasks/stream`
- `/zh/market-overview`: `GET /api/v1/market/crypto/stream`

Build / baseline results:

- `npm run check:design` -> pass, 216 files scanned, 0 blocking violations, 0 warnings
- `npm run lint` -> pass
- `npm run build` -> pass, with the existing large chunk warning for `DeterministicBacktestChartWorkspace-zWaHo3tJ.js` at 532.42 kB
- `python3 -m compileall -q src api` -> pass
- markdown lint -> not available; no runnable markdown lint script was found

## 10. Final Notes

- `./scripts/ci_gate.sh` was not run for this report-only task.
- The workspace had unrelated dirty frontend files from another concurrent session during this run; they were left untouched.
