# WolfyStock Bundle Composition Report

Status: Superseded
Owner domain: Frontend bundle and visual audit
Replacement or related docs: `docs/audits/wolfystock-echarts-chart-workspace-audit.md`, `docs/audits/wolfystock-phase0-bundle-design-inventory.md`

Date: 2026-05-05 Asia/Shanghai
Repository: `/Users/yehengli/daily_stock_analysis`
Branch: `main`
Mode: measurement/report only; no product-code, runtime, dependency, Vite, Rollup, package, test, script, or changelog changes

## 1. Executive Summary

Current build status: **pass with one Vite large chunk warning**. `cd apps/dsa-web && npm run build` completed successfully, transformed 3,157 modules, emitted assets under `/Users/yehengli/daily_stock_analysis/static`, and warned that one minified chunk is larger than 500 kB.

Largest assets:

| Asset | Size | Gzip | Finding |
| --- | ---: | ---: | --- |
| `assets/index-CKOZGjeY.js` | 1,197.07 kB | 400.94 kB | Shared app/vendor chunk and the only Vite warning source. |
| `assets/index-BH5tm17d.css` | 520.95 kB | 74.08 kB | Single global CSS/Tailwind/theme bundle. |
| `assets/BacktestPage-DgGEGcbn.js` | 233.00 kB | 73.22 kB | Largest route chunk; dominated by motion packages and backtest workspace code. |
| `assets/SystemSettingsPage-CLrg2TLH.js` | 205.18 kB | 57.92 kB | Large settings route chunk, but already route-isolated. |
| `assets/index-aCczo2BI.js` | 156.62 kB | 47.41 kB | Markdown/remark shared package chunk. |

Most likely cause of the 1.19 MB shared `index` chunk: **ECharts and zrender are being pulled into the shared chunk through an eager deterministic backtest result route import**. Source-map attribution for `index-CKOZGjeY.js.map` shows 2,983.6 KiB of source content, including 1,435.2 KiB from `echarts`, 467.4 KiB from `zrender`, and app source from `DeterministicBacktestResultPage`, `BacktestResultReport`, `DeterministicBacktestResultView`, and `DeterministicBacktestChartWorkspace`.

Safest first implementation task: **Backtest Route Lazy Load Trial**. Convert only `DeterministicBacktestResultPage` in `apps/dsa-web/src/App.tsx` from an eager import to the existing `React.lazy` route pattern, then compare `npm run build` output before and after. Do not change Vite/Rollup config for this trial.

Non-goals for this task:

- No product code changed.
- No Vite/Rollup config changed.
- No package files changed.
- No dependencies installed.
- No runtime behavior changed.
- No build output, sourcemaps, analyzer output, or temp files committed.

## 2. Methodology

Required preflight commands were run from the repository root:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -36
./scripts/task_preflight.sh || true
```

Preflight result:

- `pwd`: `/Users/yehengli/daily_stock_analysis`
- branch: `main`
- upstream: `origin/main` ahead 0, behind 0
- dirty files: 0
- recent commits included `8d150d0 docs: add phase0 bundle and design inventory` and `4ffd199 docs: add global codebase audit`

Read-first documents:

- `docs/audits/wolfystock-global-codebase-audit.md`
- `docs/audits/wolfystock-phase0-bundle-design-inventory.md`
- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/operations/parallel-codex-playbook.md`
- `docs/checks/ci-gate-clarity.md`

Build/config inspection commands:

```bash
cat package.json 2>/dev/null || true
cat apps/dsa-web/package.json
sed -n '1,260p' apps/dsa-web/vite.config.* 2>/dev/null || true
grep -R "visualizer\|bundle\|analy\|sourcemap\|manualChunks\|chunkSizeWarningLimit" -n package.json apps/dsa-web/package.json apps/dsa-web/vite.config.* apps/dsa-web/scripts 2>/dev/null || true
```

Findings:

- No root `package.json` output was present.
- `apps/dsa-web/package.json` has no analyzer script.
- No analyzer dependency was present in the web package.
- Vite config has existing manual chunks only for `vendor-react` and `vendor-router`.
- No Vite visualizer, bundle analyzer, sourcemap setting, or chunk warning limit setting was found.

Normal build command:

```bash
cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
npm run build
```

Result: **passed** with the expected Vite large chunk warning.

Source-map strategy:

```bash
cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
npm run build -- --sourcemap
```

Result: **worked**. The package script is `tsc -b && vite build`, and npm passed `--sourcemap` through to `vite build --sourcemap`. Vite generated `.js.map` files under `static/assets`, including `index-CKOZGjeY.js.map` at 4,751.92 kB.

Analysis method:

- Parsed each `.js.map` JSON with inline Node.
- Used `sourcesContent` byte length as an estimated source-content contribution.
- Grouped sources by output chunk, node_modules package, and app source path.
- Used built token scans and source import searches to cross-check package attribution.

Limitations:

- Source-content size is not identical to minified output contribution, parsed bytecode cost, or runtime execution cost.
- Shared-chunk grouping is Rollup output behavior, not a direct declaration that every source runs on every route.
- No analyzer HTML/JSON was generated because no analyzer dependency exists locally and no dependency was installed.
- No browser verification was required because this is a static report task and no UI changed.
- Full `./scripts/ci_gate.sh` was not run because the requested validation for this docs-only measurement task did not require it.

## 3. Build Asset Inventory

Normal Vite build output:

```text
✓ 3157 modules transformed.
../../static/assets/index-BH5tm17d.css                         520.95 kB │ gzip:  74.08 kB
../../static/assets/index-aCczo2BI.js                          156.62 kB │ gzip:  47.41 kB
../../static/assets/vendor-react-CygJK5cN.js                   192.78 kB │ gzip:  60.53 kB
../../static/assets/SystemSettingsPage-CLrg2TLH.js             205.18 kB │ gzip:  57.92 kB
../../static/assets/BacktestPage-DgGEGcbn.js                   233.00 kB │ gzip:  73.22 kB
../../static/assets/index-CKOZGjeY.js                        1,197.07 kB │ gzip: 400.94 kB
(!) Some chunks are larger than 500 kB after minification.
✓ built in 8.53s
```

Largest static assets by filesystem inspection:

| Asset | Size | Gzip if available | Sourcemap available? | Likely purpose | Risk |
| --- | ---: | ---: | --- | --- | --- |
| `assets/index-CKOZGjeY.js` | 1.1M / 1,197.07 kB | 400.94 kB | Yes during sourcemap build | Shared app/vendor chunk containing ECharts, zrender, i18n, API/store/layout, and eager deterministic backtest result code | High |
| `assets/index-BH5tm17d.css` | 509K / 520.95 kB | 74.08 kB | No JS map | Global CSS/Tailwind/theme bundle | Medium |
| `assets/BacktestPage-DgGEGcbn.js` | 228K / 233.00 kB | 73.22 kB | Yes | Backtest route chunk with motion packages and backtest workspaces | Medium |
| `assets/SystemSettingsPage-CLrg2TLH.js` | 200K / 205.18 kB | 57.92 kB | Yes | System settings route chunk | Medium |
| `assets/vendor-react-CygJK5cN.js` | 188K / 192.78 kB | 60.53 kB | Yes | React, React DOM, scheduler manual chunk | Low |
| `assets/index-aCczo2BI.js` | 153K / 156.62 kB | 47.41 kB | Yes | Markdown/remark/micromark shared package chunk | Medium |
| `assets/ScannerSurfacePage-9tJNPsjj.js` | 145K / 148.01 kB | 43.40 kB | Yes | Scanner route chunk | Medium |
| `assets/HomeBentoDashboardPage-1P2iOZPn.js` | 129K / 132.13 kB | 45.04 kB | Yes | Home dashboard route chunk | Medium |
| `assets/MarketOverviewPage-DcZybXFy.js` | 110K / 112.72 kB | 32.35 kB | Yes | Market overview route chunk | Low/Medium |
| `assets/PortfolioPage-dzQM3_EP.js` | 83K / 84.63 kB | 20.49 kB | Yes | Portfolio route chunk | Low/Medium |
| `assets/AdminLogsPage-C1hc1n1M.js` | 80K / 81.64 kB | 20.55 kB | Yes | Admin logs route chunk | Low/Medium |
| `assets/PreviewReportPage-R_xM2bPo.js` | 74K / 75.81 kB | 21.84 kB | Yes | Preview report route chunk | Low/Medium |
| `assets/ChatPage-Cztqn3Xw.js` | 52K / 53.54 kB | 16.85 kB | Yes | Chat route chunk | Low |
| `assets/vendor-router-BJJuNhuN.js` | 35K / 36.33 kB | 13.12 kB | Yes | React Router manual chunk | Low |

## 4. Shared Chunk Composition

Source-map analysis worked. `index-CKOZGjeY.js.map` had `sourcesContent=true`, 387 sources, and 2,983.6 KiB of source content.

High-level split for `index-CKOZGjeY.js.map`:

| Group | Estimated source content |
| --- | ---: |
| node_modules packages | 2,147.6 KiB |
| app source | 836.0 KiB |
| other | 0.0 KiB |
| total | 2,983.6 KiB |

Top package contributors in `index-CKOZGjeY.js.map`:

| Package | Estimated source content |
| --- | ---: |
| `echarts` | 1,435.2 KiB |
| `zrender` | 467.4 KiB |
| `axios` | 106.0 KiB |
| `tailwind-merge` | 100.2 KiB |
| `lucide-react` | 12.9 KiB |
| `camelcase` | 7.4 KiB |
| `quick-lru` | 6.5 KiB |
| `camelcase-keys` | 3.5 KiB |
| `next-themes` | 3.3 KiB |
| `map-obj` | 3.2 KiB |
| `zustand` | 1.7 KiB |
| `clsx` | 0.4 KiB |

Top app source contributors in `index-CKOZGjeY.js.map`:

| App source | Estimated source content |
| --- | ---: |
| `src/i18n/core.ts` | 272.8 KiB |
| `src/components/backtest/BacktestResultReport.tsx` | 59.8 KiB |
| `src/pages/DeterministicBacktestResultPage.tsx` | 49.7 KiB |
| `src/components/backtest/shared.tsx` | 34.6 KiB |
| `src/components/backtest/ruleBacktestP6.ts` | 30.1 KiB |
| `src/components/backtest/BacktestAuditTables.tsx` | 27.8 KiB |
| `src/api/error.ts` | 26.4 KiB |
| `src/stores/stockPoolStore.ts` | 24.3 KiB |
| `src/App.tsx` | 20.1 KiB |
| `src/components/backtest/normalizeDeterministicBacktestResult.ts` | 16.7 KiB |
| `src/components/backtest/DeterministicBacktestChartWorkspace.tsx` | 16.4 KiB |
| `src/components/backtest/RuleRunComparisonPanel.tsx` | 15.1 KiB |
| `src/components/backtest/BacktestChartWorkspace.tsx` | 15.1 KiB |
| `src/components/backtest/strategyInspectability.ts` | 13.4 KiB |
| `src/components/backtest/deterministicResultDensity.ts` | 13.2 KiB |

Top source files overall in `index-CKOZGjeY.js.map`:

| Source | Estimated source content |
| --- | ---: |
| `src/i18n/core.ts` | 272.8 KiB |
| `node_modules/tailwind-merge/dist/bundle-mjs.mjs` | 100.2 KiB |
| `node_modules/echarts/lib/core/echarts.js` | 82.4 KiB |
| `src/components/backtest/BacktestResultReport.tsx` | 59.8 KiB |
| `src/pages/DeterministicBacktestResultPage.tsx` | 49.7 KiB |
| `node_modules/echarts/lib/chart/line/LineView.js` | 40.7 KiB |
| `node_modules/zrender/lib/Element.js` | 37.8 KiB |
| `node_modules/echarts/lib/data/SeriesData.js` | 36.4 KiB |
| `node_modules/echarts/lib/data/DataStore.js` | 34.8 KiB |
| `src/components/backtest/shared.tsx` | 34.6 KiB |
| `node_modules/echarts/lib/component/tooltip/TooltipView.js` | 33.8 KiB |
| `node_modules/echarts/lib/chart/bar/BarView.js` | 33.0 KiB |
| `node_modules/echarts/lib/component/dataZoom/SliderZoomView.js` | 31.7 KiB |
| `src/components/backtest/ruleBacktestP6.ts` | 30.1 KiB |
| `node_modules/echarts/lib/model/Global.js` | 28.4 KiB |

Interpretation:

- The warning chunk is not mainly a collection of route page shells. It is dominated by `echarts` and `zrender`.
- The app sources that explain why chart dependencies are shared are backtest result/report/viewer modules that currently enter through the eager deterministic result route.
- `src/i18n/core.ts` is a large shared source contributor, but it is fundamental app infrastructure and should not be the first optimization target.
- `axios`, `zustand`, `tailwind-merge`, `lucide-react`, and app layout/API/store helpers contribute to the shared chunk, but none are the primary warning cause.

## 5. Route And Dependency Attribution

Route import evidence from `apps/dsa-web/src/App.tsx`:

- Most pages are lazy-loaded with `lazy(() => import(...))`.
- `DeterministicBacktestResultPage` is imported eagerly:

```tsx
import DeterministicBacktestResultPage from './pages/DeterministicBacktestResultPage';
```

Route usage:

```tsx
<Route path="/backtest" element={<RegisteredSurfaceRoute><BacktestPage /></RegisteredSurfaceRoute>} />
<Route path="/backtest/results/:runId" element={<RegisteredSurfaceRoute><DeterministicBacktestResultPage /></RegisteredSurfaceRoute>} />
<Route path="backtest" element={<RegisteredSurfaceRoute><BacktestPage /></RegisteredSurfaceRoute>} />
<Route path="backtest/results/:runId" element={<RegisteredSurfaceRoute><DeterministicBacktestResultPage /></RegisteredSurfaceRoute>} />
```

Route/page table:

| Route/page | Eager/lazy | Relevant chunk | Heavy imports or package evidence | Optimization candidate? | Risk |
| --- | --- | --- | --- | --- | --- |
| App shell/layout/auth/i18n | Eager | `index-CKOZGjeY.js` | `i18n/core`, stores, API client, layout, auth, router wrappers | Not first | High if changed broadly |
| Home | Lazy wrapper | `HomeBentoDashboardPage-1P2iOZPn.js` | Mostly app source; small `lucide-react` | No | Low |
| Scanner | Lazy wrapper | `ScannerSurfacePage-9tJNPsjj.js` | `UserScannerPage.tsx` 243.1 KiB source content; small `lucide-react` | Later page-internal only | Medium |
| Chat | Lazy | `ChatPage-Cztqn3Xw.js` + `index-aCczo2BI.js` | `react-markdown`, `remark-gfm`, `lucide-react` | Optional later | Medium |
| Portfolio | Lazy | `PortfolioPage-dzQM3_EP.js` | `lucide-react`; `recharts` only found in a test mock, not direct source import | No | Low/Medium |
| Market overview | Lazy | `MarketOverviewPage-DcZybXFy.js` | `lucide-react`; token scan also sees `remark` string, but no direct markdown import | No | Low/Medium |
| Watchlist | Lazy | `WatchlistPage-obk0lC14.js` | `lucide-react` | No | Low |
| Backtest | Lazy | `BacktestPage-DgGEGcbn.js` | `motion-dom` 330.7 KiB, `framer-motion` 117.8 KiB source content | Later route-internal work | Medium |
| Backtest compare | Lazy | `RuleBacktestComparePage-GK6z8Lif.js` | Small route chunk | No | Low |
| Deterministic backtest result | **Eager** | `index-CKOZGjeY.js` | imports `BacktestResultReport`, `BacktestChartWorkspace`, `BacktestAuditTables`, normalizers, rule P6 helpers; chart path imports ECharts | **Yes, first** | Medium |
| Preview report | Lazy | `PreviewReportPage-R_xM2bPo.js` and markdown chunk | report chart/source modules | Later | Medium |
| System settings | Lazy wrapper | `SystemSettingsPage-CLrg2TLH.js` | large settings app source, no dominant heavy library | Not first | Medium |
| Admin logs | Lazy | `AdminLogsPage-C1hc1n1M.js` | app source only | No | Low |
| Admin notifications | Lazy | `AdminNotificationsPage-DD5mhSC2.js` | small `lucide-react` | No | Low |

## 6. Deterministic Backtest Result Lazy-load Hypothesis

Evidence chain:

1. `src/App.tsx` eagerly imports `DeterministicBacktestResultPage`.
2. `DeterministicBacktestResultPage.tsx` imports:
   - `BacktestResultReport`
   - `BacktestChartWorkspace`
   - `BacktestAuditTables`
   - `BacktestOverviewSummary`
   - `normalizeDeterministicBacktestResult`
   - `ruleBacktestP6`
   - shared backtest helpers
3. `BacktestResultReport.tsx` imports `DeterministicBacktestResultView`.
4. `DeterministicBacktestResultView.tsx` imports `DeterministicBacktestChartWorkspace`.
5. `DeterministicBacktestChartWorkspace.tsx` imports ECharts:
   - `echarts/core`
   - `echarts/charts`
   - `echarts/renderers`
   - `echarts/components`
6. `index-CKOZGjeY.js.map` includes:
   - `echarts`: 1,435.2 KiB estimated source content
   - `zrender`: 467.4 KiB estimated source content
   - `DeterministicBacktestResultPage.tsx`: 49.7 KiB
   - `BacktestResultReport.tsx`: 59.8 KiB
   - `DeterministicBacktestChartWorkspace.tsx`: 16.4 KiB

Conclusion: **confirmed as the first lazy-load candidate**. The current eager route import is the clearest source-level explanation for why backtest chart/report dependencies are in the shared `index` chunk.

Expected change for a later implementation task:

- `index-CKOZGjeY.js` should lose much or all of `echarts`/`zrender` and deterministic result/report app source.
- A new deterministic result route chunk may appear, or those modules may move into an existing route chunk depending on Rollup's split decisions.
- Total app build size may not drop materially, but initial/shared transfer should improve.

Exact safe implementation plan for later:

1. In `apps/dsa-web/src/App.tsx`, replace the eager import with:

   ```tsx
   const DeterministicBacktestResultPage = lazy(() => import('./pages/DeterministicBacktestResultPage'));
   ```

2. Leave route paths, guards, Suspense wrapper, product source, charts, reports, Vite config, and package files unchanged.
3. Run:
   - `cd apps/dsa-web && npm run test -- src/__tests__/AppRoutes.test.tsx`
   - `cd apps/dsa-web && npm run test -- src/pages/__tests__/DeterministicBacktestResultPage.test.tsx`
   - `cd apps/dsa-web && npm run test -- src/pages/__tests__/BacktestPage.test.tsx`
   - `cd apps/dsa-web && npm run lint`
   - `cd apps/dsa-web && npm run build`
4. Compare build output:
   - old/new `index-*.js` minified and gzip size
   - whether ECharts/zrender move out of the shared chunk
   - whether deterministic result route remains reachable in route tests

Do not add `manualChunks` or change `chunkSizeWarningLimit` in this first trial.

## 7. Markdown/report Rendering Hypothesis

Source import evidence:

- `src/components/report/ReportMarkdown.tsx` imports `react-markdown` and `remark-gfm`.
- `src/pages/ChatPage.tsx` imports `react-markdown` and `remark-gfm`.

Sourcemap and chunk evidence:

- `index-aCczo2BI.js.map` is a markdown package chunk with 655.4 KiB source content.
- Top package contributors in that chunk include:
  - `micromark-core-commonmark`: 111.0 KiB
  - `mdast-util-to-hast`: 48.9 KiB
  - `unified`: 40.7 KiB
  - `micromark`: 40.6 KiB
  - `mdast-util-to-markdown`: 38.7 KiB
  - `react-markdown`: 12.5 KiB
  - `remark-gfm`: 1.2 KiB
- `ReportMarkdown.tsx` is in `PreviewFullReportDrawerPage-ffDJMCUV.js.map`, not in the large `index-CKOZGjeY.js.map`.
- `ChatPage.tsx` is in `ChatPage-Cztqn3Xw.js.map`, while the markdown packages are isolated into the shared markdown package chunk.

Conclusion:

- Markdown/report rendering is **not the primary cause** of the 1.19 MB shared `index-CKOZGjeY.js` warning.
- It is still a meaningful secondary optimization area because the markdown package chunk is 156.62 kB minified / 47.41 kB gzip.
- Optimize after the backtest route lazy-load trial, and only if route-level usage data shows markdown is loaded earlier than needed.

Recommended posture: **do not optimize markdown first**. If evidence later supports it, run an optional Markdown Renderer Lazy-load Trial focused on `ReportMarkdown.tsx` and `ChatPage.tsx` without changing markdown output semantics.

## 8. Icon, Motion, And Chart Library Assessment

| Library | Evidence | Assessment | Recommended now? |
| --- | --- | --- | --- |
| `echarts` | Direct imports only in `DeterministicBacktestChartWorkspace.tsx`; `index-CKOZGjeY.js.map` has 1,435.2 KiB `echarts` and 467.4 KiB `zrender` source content | Primary shared chunk driver; likely enters shared chunk through eager deterministic result route | Lazy-load route first, do not remove library |
| `motion` / `framer-motion` | `BacktestPage.tsx`, `DeterministicBacktestFlow.tsx`, `HistoricalEvaluationPanel.tsx`; `BacktestPage-DgGEGcbn.js.map` has 330.7 KiB `motion-dom` and 117.8 KiB `framer-motion` | Route-local to backtest page chunk; not the top shared chunk cause | Do not replace now |
| `lucide-react` | Used across layout, common controls, Home, Scanner, Backtest, Portfolio, Settings, Admin, Chat; source-map chunks show small per-icon contributions | Broad but mostly tree-shaken into small icon chunks/source slices | Do not remove now |
| `@remixicon/react` | Declared dependency; no current `src` import found by `rg` | Candidate for future dependency inventory only | Do not remove in bundle trial |
| `recharts` | Declared dependency; no direct `src` import found except `PortfolioPage.test.tsx` mock | Candidate for future dependency inventory only | Do not remove in bundle trial |
| `axios` | `src/api/index.ts`; 106.0 KiB source content in shared chunk | Shared API client; expected baseline app dependency | Do not change |
| `zustand` | `stockPoolStore.ts`, `agentChatStore.ts`; 1.7 KiB package source in shared chunk plus app stores | Small package footprint; app stores are shared shell state | Do not change |

No removal is recommended in this report. The first optimization should be code-splitting the eager backtest result route, not replacing libraries.

## 9. CSS Ownership Inventory

CSS asset:

- Build asset: `assets/index-BH5tm17d.css`
- Size: 520.95 kB minified / 74.08 kB gzip
- Source: `apps/dsa-web/src/index.css`
- Source length: 16,912 lines

Structure evidence from `src/index.css`:

- Starts with Google font import and Tailwind import:
  - line 1: `@import url(...)`
  - line 2: `@import "tailwindcss";`
- Utility/base sections:
  - line 4: `@layer utilities`
  - line 64: `@layer base`
  - line 82: `:root`
  - line 512: `body`
  - lines 5-14 and 2531-2545 include scrollbar/no-scrollbar rules
- Global theme/material sections:
  - lines 336-339 define panel glass variables
  - lines 1527-1535 define `.theme-panel-glass`
  - lines 2851-2888 define `.glass-card`
  - multiple `html[data-theme]` overrides appear around lines 3588-4210
- Settings-specific-looking tokens/utilities:
  - lines 462-486 define `--settings-*`
  - lines 3429-3545 define `.settings-*`
  - lines 4099-4210 include themed settings button/accent overrides
- Backtest-specific-looking sections:
  - lines 4929 onward define `.backtest-*` result viewer, chart, brush, tooltip, audit table, tabs, report console, and responsive rules
- Market-specific-looking sections:
  - lines 1990-2032 define `.theme-market-badge*`
- Scanner-specific shell flag:
  - lines 540-542 define `[data-scanner-shell='true']`

Conclusion:

- The CSS bundle is large, but it mixes Tailwind import, global tokens, theme overrides, shared material primitives, and page-specific-looking sections.
- CSS should be a separate inventory/guard follow-up. Do not split or delete CSS during the backtest lazy-load trial.
- A safe CSS follow-up should classify selectors by owner and route usage before changing output.

## 10. Recommended Next Implementation Tasks

### 1. Backtest Route Lazy Load Trial

- Files likely touched: `apps/dsa-web/src/App.tsx`
- Risk: Medium
- Expected benefit: likely moves ECharts/zrender and deterministic result/report modules out of `assets/index-*.js`, reducing shared initial JS substantially
- Tests/checks:
  - `cd apps/dsa-web && npm run test -- src/__tests__/AppRoutes.test.tsx`
  - `cd apps/dsa-web && npm run test -- src/pages/__tests__/DeterministicBacktestResultPage.test.tsx`
  - `cd apps/dsa-web && npm run test -- src/pages/__tests__/BacktestPage.test.tsx`
  - `cd apps/dsa-web && npm run lint`
  - `cd apps/dsa-web && npm run build`
  - optional sourcemap diff: confirm `echarts`/`zrender` no longer dominate shared `index`
- Parallel-safe? Yes, if no other session is touching `App.tsx` or deterministic backtest route tests

### 2. Backtest Native Controls Burn-down

- Files likely touched:
  - `apps/dsa-web/src/components/backtest/ProBacktestWorkspace.tsx`
  - `apps/dsa-web/src/components/backtest/DeterministicBacktestFlow.tsx`
  - `apps/dsa-web/src/components/backtest/NormalBacktestWorkspace.tsx`
  - `apps/dsa-web/src/components/backtest/HistoricalEvaluationPanel.tsx`
- Risk: Medium because these are user-visible backtest controls
- Expected benefit: reduces design guard warning volume and prepares backtest surfaces for safer later internal splitting
- Tests/checks:
  - relevant backtest component/page tests
  - `cd apps/dsa-web && npm run check:design`
  - `cd apps/dsa-web && npm run lint`
  - `cd apps/dsa-web && npm run build`
  - browser verification required because controls are visible UI
- Parallel-safe? Yes with the route lazy-load task only if file ownership is kept disjoint; this task should not touch `App.tsx`

### 3. Scanner Native Controls Burn-down

- Files likely touched:
  - `apps/dsa-web/src/pages/UserScannerPage.tsx`
  - possibly existing shared controls under `apps/dsa-web/src/components/common/`
- Risk: Medium because scanner workflow controls are visible and dense
- Expected benefit: reduces scanner design guard warning cluster without changing scanner ranking, selection, or backtest behavior
- Tests/checks:
  - `cd apps/dsa-web && npm run test -- src/pages/__tests__/UserScannerPage.test.tsx`
  - `cd apps/dsa-web && npm run check:design`
  - `cd apps/dsa-web && npm run lint`
  - `cd apps/dsa-web && npm run build`
  - browser verification required
- Parallel-safe? Yes if no other session is touching scanner UI

### 4. CSS Ownership Inventory Or CSS Guard Follow-up

- Files likely touched:
  - inventory-only: `docs/audits/...`
  - guard follow-up, only if requested: `apps/dsa-web/scripts/check-design-constitution.mjs` or docs for CSS ownership rules
- Risk: Low for inventory, Medium for guard/script changes
- Expected benefit: classifies the 16,912-line `src/index.css` before any CSS deletion/splitting
- Tests/checks:
  - inventory-only: markdown inspection and `git diff --check`
  - guard/script: `cd apps/dsa-web && npm run check:design`, script tests if present, `npm run lint`
- Parallel-safe? Inventory is parallel-safe; guard/script changes should not run in parallel with design-guard work

### 5. Optional Markdown Renderer Lazy-load Trial

- Condition: run only after the backtest route lazy-load trial if build evidence still shows markdown chunk loading earlier than desired
- Files likely touched:
  - `apps/dsa-web/src/components/report/ReportMarkdown.tsx`
  - `apps/dsa-web/src/pages/ChatPage.tsx`
  - possibly report preview/full report pages if they directly control markdown rendering boundaries
- Risk: Medium because report/chat markdown rendering must remain semantically identical
- Expected benefit: may defer the 156.62 kB / 47.41 kB markdown package chunk from routes that do not render markdown immediately
- Tests/checks:
  - report markdown/component tests if present
  - `cd apps/dsa-web && npm run test -- src/pages/__tests__/ChatPage.test.tsx`
  - preview/report tests if present
  - `cd apps/dsa-web && npm run lint`
  - `cd apps/dsa-web && npm run build`
  - visual/browser verification for report/chat markdown if UI output changes
- Parallel-safe? Yes only if scoped away from backtest and scanner tasks

### 6. Dependency Inventory For Declared-but-unused Heavy UI Packages

- Files likely touched: docs-only unless a later removal task is explicitly approved
- Risk: Low for inventory, High for dependency removal
- Expected benefit: clarify whether `@remixicon/react` and `recharts` are still required, since they are declared but no direct current `src` imports were found
- Tests/checks:
  - source search
  - package lock inspection
  - no package edits unless a separate removal task is approved
- Parallel-safe? Yes as docs-only; package edits should be isolated

## 11. Non-goals And Safety

This report task intentionally did not:

- Refactor product code.
- Change runtime behavior.
- Change Vite/Rollup config.
- Add or remove dependencies.
- Edit package files.
- Edit tests.
- Edit backend services.
- Edit API schemas or endpoints.
- Edit frontend components/pages.
- Edit design guard scripts.
- Edit `docs/CHANGELOG.md`.
- Start or stop backend/frontend/dev/preview servers.
- Run browser verification.
- Commit static build output.
- Commit sourcemaps.
- Commit analyzer artifacts.

The only intended repository change is:

- `docs/audits/wolfystock-bundle-composition-report.md`
