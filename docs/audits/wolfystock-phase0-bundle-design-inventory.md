# WolfyStock Phase 0 Bundle And Design Inventory

Status: Superseded
Owner domain: Frontend bundle and design inventory
Replacement or related docs: `docs/audits/wolfystock-bundle-composition-report.md`, `docs/audits/wolfystock-echarts-chart-workspace-audit.md`

Date: 2026-05-05 Asia/Shanghai
Repository: `/Users/yehengli/daily_stock_analysis`
Branch: `main`
Mode: inventory/report only; no product-code changes

## 1. Executive Summary

Current build status: **pass with a Vite large chunk warning**. `npm run build` completed successfully, transformed 3,157 modules, emitted assets into `/Users/yehengli/daily_stock_analysis/static`, and warned that one minified chunk is larger than 500 kB.

Current design guard status: **pass with warnings**. `npm run check:design` scanned 213 files, found 0 blocking violations, and reported 103 warning-only findings. All current warnings are `native-ui`.

Biggest bundle risks:

| Risk | Evidence | Priority |
| --- | --- | --- |
| Large shared `index-CKOZGjeY.js` chunk | 1,197.07 kB minified / 400.94 kB gzip; statically imported by every route chunk | P0 follow-up |
| Chart and markdown/runtime libraries in shared chunks | Built chunk token inspection found `echarts`, `unified`, `Markdown`, `motion`, and `lucide` in the 1.19 MB shared chunk; `react-markdown`/`micromark` are in `index-aCczo2BI.js` | P0 follow-up |
| Eager deterministic result route import | `src/App.tsx` lazy-loads most pages, but imports `DeterministicBacktestResultPage` eagerly | P1 |
| Large CSS asset | `index-BH5tm17d.css` is 520.95 kB minified / 74.08 kB gzip; source `src/index.css` is 16,912 lines / 440,792 bytes | P1/P2 |
| Large page modules | `SettingsPage.tsx` 5,007 lines, `UserScannerPage.tsx` 4,553, `HomeBentoDashboardPage.tsx` 3,929, `PortfolioPage.tsx` 2,925 | P1/P2 |

Biggest design-warning clusters:

| Surface | Warning count | Notes |
| --- | ---: | --- |
| Backtest workspaces | 46 | `ProBacktestWorkspace`, `DeterministicBacktestFlow`, `NormalBacktestWorkspace`, `HistoricalEvaluationPanel` |
| Scanner | 18 | Mostly unclassed native buttons plus one select and two inputs |
| Chat | 9 | Native button warnings |
| Personal settings | 7 | Native button/input warnings |
| Watchlist | 6 | Native button warnings |

Safest next optimization tasks:

1. Keep Phase 0 no-code and confirm bundle composition with an analyzer in a separate tooling pass.
2. Lazy-load `DeterministicBacktestResultPage` as a narrow P1 trial, because it is the only major route page found as an eager import in `App.tsx`.
3. Burn down `native-ui` warnings by surface, starting with backtest form controls, then scanner/watchlist buttons.
4. Profile CSS ownership before splitting or deleting CSS; current CSS appears to be one global Tailwind plus token/theme file.
5. Extract route-local helpers only after route tests are selected; do not start with broad component splits.

## 2. Methodology

Commands run:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -32
./scripts/task_preflight.sh || true

sed -n '1,240p' docs/audits/wolfystock-global-codebase-audit.md
sed -n '240,520p' docs/audits/wolfystock-global-codebase-audit.md
sed -n '1,260p' CODEX_FRONTEND_DESIGN_CONSTITUTION.md
sed -n '1,240p' docs/checks/design-guard.md
sed -n '1,220p' docs/checks/ci-gate-clarity.md
sed -n '1,260p' docs/operations/parallel-codex-playbook.md

cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
npm run build
find /Users/yehengli/daily_stock_analysis/static -type f \( -name "*.js" -o -name "*.css" \) -exec du -h {} + | sort -hr | head -40
find /Users/yehengli/daily_stock_analysis/static -type f \( -name "*.js" -o -name "*.css" \) -exec ls -lh {} + | sort -k5 -hr | head -40

cd /Users/yehengli/daily_stock_analysis
cat /Users/yehengli/daily_stock_analysis/package.json
cat /Users/yehengli/daily_stock_analysis/apps/dsa-web/package.json
grep -R "visualizer\|bundle\|analy" -n package.json apps/dsa-web/package.json apps/dsa-web/vite.config.* apps/dsa-web/scripts 2>/dev/null || true

cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
find src -type f \( -name "*.tsx" -o -name "*.ts" \) -exec wc -l {} + | sort -nr | head -50
find src -type f \( -name "*.tsx" -o -name "*.ts" \) ! -path "*/__tests__/*" -exec wc -l {} + | sort -nr | head -50
grep -R "from ['\"]recharts\|from ['\"]framer-motion\|from ['\"]lucide-react\|from ['\"]react-markdown\|from ['\"]remark\|from ['\"]monaco\|from ['\"]codemirror\|from ['\"]xlsx\|from ['\"]jspdf\|from ['\"]html2canvas" -n src | head -240
grep -R "import .* from ['\"]recharts\|import .* from ['\"]framer-motion\|import .* from ['\"]lucide-react" -n src | head -240
grep -R "from ['\"]echarts\|from ['\"]motion\|from ['\"]@remixicon/react\|from ['\"]zustand\|from ['\"]axios\|from ['\"]react-markdown\|from ['\"]remark-gfm\|from ['\"]recharts" -n src | head -240
grep -R "lazy(\|React.lazy\|import(" -n src | head -240
grep -R "createBrowserRouter\|Routes\|Route path\|path:" -n src | head -240
npm run check:design 2>&1 | tee /tmp/wolfystock-design-inventory.txt
grep -E "warning|WARN|native|raw|debug|provider|schema|English|UNKNOWN|Data Quality|Key Metrics|Advanced Details|Execution Assumptions" -n /tmp/wolfystock-design-inventory.txt | head -240
node --input-type=module - <<'NODE'
import { scanProject } from './scripts/check-design-constitution.mjs';
const result = scanProject();
// Summarize warnings by rule, file, and excerpt type.
NODE
node --input-type=module - <<'NODE'
import { scanProject } from './scripts/check-design-constitution.mjs';
const result = scanProject();
for (const item of result.warnings.slice(80)) {
  console.log(`${item.file}:${item.line}\t${item.rule}\t${item.excerpt}`);
}
NODE
grep -R "UNKNOWN\|Key Metrics\|Data Quality\|Execution Assumptions\|Advanced Details\|SCANNER CANDIDATES\|Critical\|Provider Down\|Provider Error" -n src | head -200
grep -R "provider_down\|provider_error\|schema_error\|debug\|raw metadata\|schema internals\|system prompt\|API key" -n src | head -240
grep -R "<select\|<input\|<button" -n src | head -240
grep -R "overflow-x-auto\|overflow-y-auto\|overflow-auto" -n src | head -240
npm run lint

cd /Users/yehengli/daily_stock_analysis
python3 -m compileall -q src api
git status --short
git status --branch --short
```

Tools used:

- Vite production build output.
- Existing design guard script.
- Static source searches.
- Build artifact size inspection under `static/assets`.
- Lightweight built-chunk token inspection.

Limitations:

- No bundle analyzer dependency or analyzer script exists in the repo. The root `package.json` is absent; `apps/dsa-web/package.json` has no analyzer script, and grep found no Vite visualizer or analyzer setup.
- No package was installed and no dependency was added.
- No Vite/Rollup config was changed.
- No browser verification was run because this is report-only and no UI behavior changed.
- No full `./scripts/ci_gate.sh` was run; targeted checks were enough for this docs-only inventory.
- Built chunk token inspection is an approximation, not a full module attribution report.

Commands not run and why:

| Command | Reason |
| --- | --- |
| Full `./scripts/ci_gate.sh` | Not required for docs-only inventory; targeted build/design/lint/compile checks were requested |
| Browser/Safari verification | No product UI changed |
| Dev/preview/backend servers | Static/report task; user explicitly said not to start servers |
| Bundle analyzer install | No existing analyzer; user explicitly said not to add dependencies |
| Markdown lint | No markdown lint script was found in available package scripts |

## 3. Build Output And Bundle-Size Inventory

Build result:

- Command: `cd apps/dsa-web && npm run build`
- Result: **passed**
- Modules transformed: 3,157
- Output directory: `/Users/yehengli/daily_stock_analysis/static`
- Warning:

```text
(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
```

Largest build assets:

| Asset/chunk | Size | Gzip | Likely route/feature | Risk | Notes |
| --- | ---: | ---: | --- | --- | --- |
| `assets/index-CKOZGjeY.js` | 1,197.07 kB | 400.94 kB | Shared non-React/non-router app/vendor chunk | High | Exceeds 500 kB warning; all route chunks statically import it. Built token inspection found `echarts`, `unified`, `Markdown`, `motion`, and `lucide`. |
| `assets/index-BH5tm17d.css` | 520.95 kB | 74.08 kB | Global CSS/Tailwind/theme bundle | Medium | Single CSS import from `src/main.tsx`; source `src/index.css` is 16,912 lines. |
| `assets/BacktestPage-DgGEGcbn.js` | 233.00 kB | 73.22 kB | Backtest route | Medium | Largest route chunk; imports shared index plus strategy/catalog/icons/router. Contains `motion` and `unified` tokens. |
| `assets/SystemSettingsPage-CLrg2TLH.js` | 205.18 kB | 57.92 kB | `/settings/system` | Medium | Wraps large `SettingsPage.tsx`. |
| `assets/vendor-react-CygJK5cN.js` | 192.78 kB | 60.53 kB | React/React DOM/scheduler | Low | Explicit manual chunk from existing Vite config. |
| `assets/index-aCczo2BI.js` | 156.62 kB | 47.41 kB | Markdown/remark shared chunk | Medium | Imports only `vendor-react`; token inspection found `react-markdown`, `micromark`, `remark`, and `markdown`. |
| `assets/ScannerSurfacePage-9tJNPsjj.js` | 148.01 kB | 43.40 kB | Scanner route | Medium | Wraps `UserScannerPage.tsx`. |
| `assets/HomeBentoDashboardPage-1P2iOZPn.js` | 132.13 kB | 45.04 kB | Home route | Medium | Home wrapper lazy-loads this. |
| `assets/MarketOverviewPage-DcZybXFy.js` | 112.72 kB | 32.35 kB | Market overview route | Low/Medium | Medium route chunk, not the warning source. |
| `assets/PortfolioPage-dzQM3_EP.js` | 84.63 kB | 20.49 kB | Portfolio route | Low/Medium | Large source module but moderate emitted chunk. |
| `assets/AdminLogsPage-C1hc1n1M.js` | 81.64 kB | 20.55 kB | Admin logs route | Low/Medium | Admin-specific route chunk. |
| `assets/PreviewReportPage-R_xM2bPo.js` | 75.81 kB | 21.84 kB | Preview report route | Low/Medium | Depends on report/markdown surfaces. |
| `assets/ChatPage-Cztqn3Xw.js` | 53.54 kB | 16.85 kB | Chat/Decision Desk route | Low | Imports markdown shared chunk. |
| `assets/vendor-router-BJJuNhuN.js` | 36.33 kB | 13.12 kB | React Router | Low | Explicit manual chunk from existing Vite config. |
| `assets/WatchlistPage-obk0lC14.js` | 35.63 kB | 10.88 kB | Watchlist route | Low | Moderate source size, small emitted chunk. |

Current CSS situation:

| Item | Evidence | Risk | Recommendation |
| --- | --- | --- | --- |
| Single global source CSS | Only `src/main.tsx` imports `./index.css` | Medium | Treat CSS as global shared infrastructure; do not split blindly. |
| Tailwind plus project tokens in one file | `src/index.css` starts with Google font import, `@import "tailwindcss"`, `@layer utilities`, and global theme tokens | Medium | Inventory token/utility groups before any deletion. |
| Large generated CSS asset | `static/assets/index-BH5tm17d.css` is 520,946 bytes, gzip 74,131 bytes | Medium | Profile unused selectors and repeated theme blocks in a future no-code CSS pass. |
| Source CSS is large | `src/index.css` is 16,912 lines / 440,792 bytes | Medium | Consider CSS ownership sections and dead-token audit later, not in this task. |

## 4. Largest Frontend Modules

Top non-test TS/TSX files:

| File | Lines | Surface | Likely risk | Recommended next action |
| --- | ---: | --- | --- | --- |
| `src/i18n/core.ts` | 5,802 | shared i18n | Medium | Do not split during bundle work unless locale loading is profiled. |
| `src/pages/SettingsPage.tsx` | 5,007 | Settings/System Settings | High | Extract tested pure helpers or subpanels only after route tests are selected. |
| `src/pages/UserScannerPage.tsx` | 4,553 | Scanner | High | Start with scanner label/status utility tests before moving helpers. |
| `src/pages/HomeBentoDashboardPage.tsx` | 3,929 | Home | High | Avoid DOM skeleton churn; isolate report/helper logic only if tests cover it. |
| `src/pages/PortfolioPage.tsx` | 2,925 | Portfolio | Medium | Preserve accounting formulas; helper extraction only with Portfolio tests. |
| `src/pages/MarketOverviewPage.tsx` | 2,472 | Market Overview | Medium | Keep provider/freshness semantics; test freshness labels before utility moves. |
| `src/pages/ChatPage.tsx` | 2,017 | Chat/Decision Desk | Medium | Markdown/editor areas are candidates for profile-before-change. |
| `src/pages/AdminLogsPage.tsx` | 1,923 | Admin Logs | Medium | Keep raw diagnostics collapsed; utility extraction can be admin-local first. |
| `src/components/report/StandardReportPanel.tsx` | 1,496 | shared report | Medium | Candidate for report-only lazy/detail isolation after analyzer proof. |
| `src/components/backtest/DeterministicBacktestFlow.tsx` | 1,419 | Backtest | Medium | Also top design-warning source; burn down native controls first. |
| `src/pages/BacktestPage.tsx` | 1,414 | Backtest | Medium | Route chunk is largest page chunk; preserve formulas/workflow. |
| `src/components/settings/LLMChannelEditor.tsx` | 1,314 | Settings | Medium | Keep config visibility/security policy intact. |
| `src/pages/WatchlistPage.tsx` | 1,286 | Watchlist | Medium | UI warnings are small; avoid scanner/backtest coupling. |
| `src/components/backtest/ProBacktestWorkspace.tsx` | 1,237 | Backtest | High | Largest design-warning file; native-control polish is safe next work. |
| `src/components/report/ReportPriceChart.tsx` | 1,233 | shared report/chart | Medium | Profile chart loading before code-splitting. |
| `src/pages/DeterministicBacktestResultPage.tsx` | 1,222 | Backtest result | High | Eager import in `App.tsx`; best lazy-load trial candidate. |
| `src/components/backtest/BacktestResultReport.tsx` | 1,166 | Backtest report | Medium | Detail/export areas may be lazy candidates after analyzer proof. |

Route/surface grouping:

| Surface | Largest files observed |
| --- | --- |
| Home | `HomeBentoDashboardPage.tsx`, `DecisionCard.tsx`, report components |
| Scanner | `UserScannerPage.tsx`, `ScannerSurfacePage.tsx`, scanner types |
| Watchlist | `WatchlistPage.tsx`, watchlist API/helper chunks |
| Backtest | `BacktestPage.tsx`, `DeterministicBacktestFlow.tsx`, `ProBacktestWorkspace.tsx`, `NormalBacktestWorkspace.tsx`, `HistoricalEvaluationPanel.tsx`, `DeterministicBacktestResultPage.tsx`, `BacktestResultReport.tsx` |
| Portfolio | `PortfolioPage.tsx`, portfolio types |
| Market Overview | `MarketOverviewPage.tsx`, `marketOverviewPrimitives.tsx` |
| Admin Logs | `AdminLogsPage.tsx`, `adminLogs.ts` |
| Admin Notifications | `AdminNotificationsPage.tsx`, `NotificationChannelsConfig.tsx` |
| Settings | `SettingsPage.tsx`, `LLMChannelEditor.tsx`, `IntelligentImport.tsx`, settings hooks |
| Chat/Decision Desk | `ChatPage.tsx`, `agentChatStore.ts` |
| Shared components | report markdown/chart/details, common input/select/button, layout shell/sidebar |

## 5. Heavy Import Clusters

| Library/package | Files importing it | Likely bundle impact | Recommendation | Profile first? |
| --- | --- | --- | --- | --- |
| `echarts` | `src/components/backtest/DeterministicBacktestChartWorkspace.tsx` | High; token inspection found `echarts` inside `index-CKOZGjeY.js` | Investigate why chart code enters the shared large chunk; likely tied to eager backtest result route import. | Yes |
| `react-markdown` / `remark-gfm` | `src/components/report/ReportMarkdown.tsx`, `src/pages/ChatPage.tsx` | Medium/high; separate `index-aCczo2BI.js` is 156.62 kB and contains markdown/remark/micromark tokens | Keep shared markdown chunk for now; consider lazy-loading rich markdown renderers only where visible. | Yes |
| `motion/react` | `BacktestPage.tsx`, `DeterministicBacktestFlow.tsx`, `HistoricalEvaluationPanel.tsx` | Medium; backtest route chunk and shared chunk both include motion tokens | Avoid replacing motion before measuring. Consider reducing route-level import spread after backtest warnings are cleaned. | Yes |
| `lucide-react` | Layout, common inputs/select, Home, Scanner, Portfolio, Admin, Chat, Backtest | Medium; many small icon chunks plus `lucide` token in shared chunk | Leave existing usage; icon library is already split into small emitted chunks in many cases. | No for first pass |
| `zustand` | `stockPoolStore.ts`, `agentChatStore.ts` | Low/medium shared runtime | No action without profiler evidence. | Yes before change |
| `axios` | `src/api/index.ts` | Low shared API client | No action. | No |
| `recharts` | Dependency present; only tests matched direct `recharts` text in current source search | Unknown/low current source use | Verify if dependency remains needed in a separate dependency inventory; do not remove in this task. | Yes before removal |

No `monaco`, `codemirror`, `xlsx`, `jspdf`, or `html2canvas` imports were found by the requested source search.

## 6. Route Code-Splitting And Lazy-Loading Inventory

`src/App.tsx` uses `React.lazy` for most major pages:

| Route/page | Eager vs lazy | Chunk/build evidence | Recommended action | Risk |
| --- | --- | --- | --- | --- |
| Home wrapper `HomeSurfacePage` | Lazy | Small wrapper chunk plus `HomeBentoDashboardPage` 132.13 kB | Keep; do not disturb Home shell. | Low |
| Guest home | Lazy | `GuestHomePage` 1.14 kB | No action. | Low |
| Scanner | Lazy wrapper | `ScannerSurfacePage` 148.01 kB | Keep route split; later split scanner internals only with tests. | Medium |
| Chat | Lazy | `ChatPage` 53.54 kB plus markdown chunk | Consider markdown/editor lazy details after analyzer confirmation. | Medium |
| Portfolio | Lazy | `PortfolioPage` 84.63 kB | No route split issue now. | Low |
| Market Overview | Lazy | `MarketOverviewPage` 112.72 kB | No route split issue now. | Low |
| Watchlist | Lazy | `WatchlistPage` 35.63 kB | No route split issue now. | Low |
| Backtest | Lazy | `BacktestPage` 233.00 kB | Candidate for route-internal lazy chart/report sections after design-warning cleanup. | Medium |
| Backtest compare | Lazy | `RuleBacktestComparePage` 30.02 kB | No action. | Low |
| Deterministic backtest result | **Eager** | `src/App.tsx` directly imports `DeterministicBacktestResultPage`; chart tokens appear in shared chunk | Best low-risk lazy-load trial. | Medium |
| Personal settings | Lazy | `PersonalSettingsPage` 12.82 kB | No action. | Low |
| System settings | Lazy wrapper | `SystemSettingsPage` 205.18 kB wraps `SettingsPage` | Candidate for helper extraction, not route split. | Medium |
| Admin logs | Lazy | `AdminLogsPage` 81.64 kB | No route split issue. | Low |
| Admin notifications | Lazy | `AdminNotificationsPage` 27.43 kB | No route split issue. | Low |
| Preview report/full report | Lazy | `PreviewReportPage` 75.81 kB; drawer 14.25 kB | Keep preview isolation. | Low |

Likely low-risk lazy-loading change later:

- Convert `DeterministicBacktestResultPage` in `src/App.tsx` to match the existing lazy page pattern.
- Expected impact: may remove backtest result/chart dependencies from the shared large chunk.
- Required checks: `npm run build`, `npm run lint`, `BacktestPage` and deterministic result route tests, route smoke/browser only if product UI changes are visible.

## 7. Design Guard Inventory

Latest known audit baseline:

- `docs/audits/wolfystock-global-codebase-audit.md` reported `npm run check:design` passed with 103 warnings across 213 scanned files.

Current result:

| Metric | Current |
| --- | ---: |
| Files scanned | 213 |
| Blocking violations | 0 |
| Warning count | 103 |
| Warning rules present | `native-ui` only |
| `raw-debug-copy` warnings | 0 |
| `localized-ui-copy` warnings | 0 |

Warning concentration from existing guard scanner:

| File | Warnings | Category |
| --- | ---: | --- |
| `src/components/backtest/ProBacktestWorkspace.tsx` | 20 | native controls |
| `src/pages/UserScannerPage.tsx` | 18 | native controls |
| `src/components/backtest/DeterministicBacktestFlow.tsx` | 10 | native controls |
| `src/components/backtest/NormalBacktestWorkspace.tsx` | 10 | native controls |
| `src/pages/ChatPage.tsx` | 9 | native controls |
| `src/pages/PersonalSettingsPage.tsx` | 7 | native controls |
| `src/components/backtest/HistoricalEvaluationPanel.tsx` | 6 | native controls |
| `src/pages/WatchlistPage.tsx` | 6 | native controls |
| `src/pages/SettingsPage.tsx` | 4 | native controls |
| `src/components/layout/SidebarNav.tsx` | 3 | native controls |
| `src/components/report/ReportDetails.tsx` | 3 | native controls |
| `src/pages/HomeBentoDashboardPage.tsx` | 3 | native controls |
| `src/components/report/ReportPriceChart.tsx` | 1 | native controls |
| `src/components/settings/FontSizeSettingsCard.tsx` | 1 | native controls |
| `src/pages/MarketOverviewPage.tsx` | 1 | native controls |
| `src/pages/PortfolioPage.tsx` | 1 | native controls |

Warning type breakdown:

| Excerpt kind | Count |
| --- | ---: |
| `<button` without className | 57 |
| `<input` without className or explicit project primitive | 38 |
| `<select` missing `appearance-none` pattern | 8 |

What changed since previous burn-down:

- The current warning count matches the latest global audit count: 103.
- Current source-level classification shows the warning set is now concentrated entirely in `native-ui`; raw debug/provider/schema copy and localized English warning terms are no longer present as design-guard findings.

## 8. Design Warning Classification

| Category | Examples | Likely files/surfaces | Safe next fix | Should it remain warning-only or become blocking? |
| --- | --- | --- | --- | --- |
| Backtest native text/number inputs | `<input` at `DeterministicBacktestFlow`, `NormalBacktestWorkspace`, `HistoricalEvaluationPanel`, `ProBacktestWorkspace` | Backtest | Replace with existing input primitive or explicit WolfyStock ghost field class in one backtest pass. | Warning-only until browser checked. |
| Backtest selects missing full select trigger styling | `<select` at deterministic/normal/pro/historical panels | Backtest | Add `appearance-none pr-10 truncate` styling and custom arrow if needed. | Could become blocking after all existing selects are fixed. |
| Backtest unclassed buttons | Template/open/history buttons in `ProBacktestWorkspace` and `NormalBacktestWorkspace` | Backtest | Apply existing `primary/secondary/chip` button constants. | Warning-only now. |
| Scanner action buttons/select/input | `UserScannerPage.tsx` warnings around run/result/filter controls | Scanner | Fix after backtest, using existing scanner action button classes; avoid logic changes. | Warning-only now. |
| Chat native buttons | `ChatPage.tsx` warnings | Chat/Decision Desk | Use existing ghost/icon button classes without changing chat state. | Warning-only now. |
| Personal settings controls | `PersonalSettingsPage.tsx` buttons/inputs | Settings | Use shared `Button/Input` or local classes. | Warning-only now. |
| Watchlist row/action buttons | `WatchlistPage.tsx` buttons | Watchlist | Apply existing action button class constants. | Warning-only now. |
| Developer/raw diagnostics copy | Static grep still finds `debug`, `provider_error`, `API key` in i18n, tests, admin logs, scanner, settings | Mostly legitimate collapsed diagnostics/tests/settings copy | No guard warning currently; keep manual review for visible surfaces. | Keep warning-only if reintroduced. |
| Tests/fixtures only | Many `provider_down`, `UNKNOWN`, `Critical` matches are in `__tests__` | Tests | No source change. | Not applicable. |
| Internal variable/type names | `latestCriticalError`, `debugMarketPanel`, provider status variables | Internal implementation | No UI copy change unless visible. | Not applicable. |

## 9. Optimization Recommendations

### Phase 0 Follow-Ups, Still No Product Behavior Change

| Priority | Task | Impact | Risk | Touched files/surfaces | Tests/checks | Parallel with DuckDB/backend? |
| --- | --- | --- | --- | --- | --- | --- |
| P0 | Bundle analyzer follow-up using existing or temporary non-committed tooling | High | Low | docs/report only; maybe local temp output | `npm run build`; analyzer output not committed | Yes |
| P0 | Confirm `index-CKOZGjeY.js` composition and why `echarts` is shared | High | Low | read-only frontend build/source | `npm run build`; built-token/analyzer evidence | Yes |
| P1 | CSS ownership inventory for `src/index.css` sections | Medium | Low | docs/report only | `wc`, selector grouping, no source edits | Yes |
| P1 | Design guard full warning CSV/report by file/line/rule | Medium | Low | docs/report only or `/tmp` output | `npm run check:design` | Yes |

### Phase 1 Low-Risk Frontend Cleanup

| Priority | Task | Impact | Risk | Touched files/surfaces | Tests/checks | Parallel with DuckDB/backend? |
| --- | --- | --- | --- | --- | --- | --- |
| P0 | Backtest native controls burn-down | Medium | Medium | `components/backtest/*Workspace*`, `DeterministicBacktestFlow`, `HistoricalEvaluationPanel` | `npm run check:design`, `BacktestPage` tests, `npm run lint`, `npm run build`, browser if visible | Yes, not with other backtest UI work |
| P1 | Scanner native button/select/input burn-down | Medium | Medium | `UserScannerPage.tsx` | `UserScannerPage` tests, design guard, lint/build, browser if visible | Yes, not with scanner work |
| P1 | Watchlist and Chat native button cleanup | Low/Medium | Low/Medium | `WatchlistPage.tsx`, `ChatPage.tsx` | page tests, design guard, lint/build | Yes |
| P2 | Personal settings native controls cleanup | Low | Low | `PersonalSettingsPage.tsx` | personal/settings tests, design guard, lint/build | Yes |

### Phase 2 Code-Splitting/Lazy Loading Candidates

| Priority | Task | Impact | Risk | Touched files/surfaces | Tests/checks | Parallel with DuckDB/backend? |
| --- | --- | --- | --- | --- | --- | --- |
| P0 | Lazy-load `DeterministicBacktestResultPage` from `App.tsx` | High | Medium | `src/App.tsx`, backtest result route | `npm run build`, route tests, lint | Yes, not with route/shell work |
| P1 | Route-internal lazy chart workspace trial | Medium | Medium | backtest chart/result components | analyzer before/after, backtest tests, build | Yes, not with backtest UI cleanup |
| P2 | Rich markdown renderer lazy-loading trial | Medium | Medium | `ReportMarkdown`, Chat/report consumers | report/chat tests, build, analyzer before/after | Yes |
| P2 | Settings panel helper extraction after chunk proof | Medium | Medium | settings page/components | settings tests, lint/build | Yes, not with settings admin work |

### Phase 3 Shared Utility Extraction

| Priority | Task | Impact | Risk | Touched files/surfaces | Tests/checks | Parallel with DuckDB/backend? |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | Scanner/admin/status label utility tests before extraction | Medium | Low | tests/util only first | focused Vitest | Yes |
| P1 | Shared generic status display adapter | Medium | Medium | shared UI/status helpers; scanner/admin/backtest call sites | `StatusBadge`, scanner/admin/backtest tests, lint/build | No, central frontend touch |
| P2 | Market freshness adapter tests | Medium | Low | market primitives/tests | market overview tests | Yes |
| P2 | Report diagnostics/developer details helper | Low/Medium | Medium | report/home/admin/backtest diagnostics | affected page tests, browser if visible | No if it touches shared report UI |

### Phase 4 Backend Profiling Tasks

| Priority | Task | Impact | Risk | Touched files/surfaces | Tests/checks | Parallel with DuckDB/backend? |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | Market provider timing instrumentation | High | Medium | market backend services | market/cache tests, compile, no provider behavior change | Not with market backend work |
| P1 | Scanner/watchlist/backtest batch cap and dedupe verification | High | Medium | scanner/watchlist/backtest tests/services | focused pytest/Vitest | Split by surface only |
| P2 | Report/history normalization profiling | Medium | Medium | history/analysis services | focused history/report tests | Yes if no shared normalizer edits |
| P2 | DuckDB disabled/no-write smoke preservation | High for DuckDB | Medium | quant service/docs/tests | quant tests and disabled smoke | This is DuckDB-specific, not parallel with DuckDB edits |

## 10. Specific Next Codex Prompts To Run

1. Bundle Analysis Follow-up: confirm shared chunk composition with analyzer evidence.
2. Backtest Route Lazy Load Trial: lazy-load deterministic result route and compare build output.
3. Design Guard Burn-down Phase 3: backtest native controls.
4. Scanner Design Guard Burn-down: scanner native controls only.
5. CSS Bundle Inventory: classify `src/index.css` token/utility/page sections.
6. Settings Page Helper Extraction Plan: no code until settings test coverage is mapped.

## 11. Risks And Non-Goals

- No product code changed.
- No optimization was performed.
- No dependencies were installed.
- No route behavior changed.
- No Vite/Rollup or build configuration changed.
- No tests, scripts, backend services, API schemas/endpoints, frontend components/pages, or package files were edited.
- No generated files, build output, screenshots, coverage, local logs, DuckDB files, or `/tmp` files should be committed.
- Measurements may need analyzer confirmation because no bundle analyzer exists in the repo today.
- Design guard warnings are advisory; do not make them blocking until a dedicated visual cleanup pass burns down current warnings.
- The static grep findings include tests, fixtures, internal variables, and legitimate settings/admin copy; visible UI claims need manual/browser verification in later implementation tasks.

## Validation Notes For This Report

Targeted checks completed before writing this report:

| Command | Result |
| --- | --- |
| `./scripts/task_preflight.sh || true` | Branch `main`, upstream `origin/main` ahead 0 / behind 0, dirty files 0 |
| `npm run build` | Passed; 3,157 modules transformed; large chunk warning for `index-CKOZGjeY.js` |
| `npm run check:design` | Passed with 103 warnings, 0 blocking violations, 213 files scanned |
| `npm run lint` | Passed |
| `python3 -m compileall -q src api` | Passed |
| `git status --short` before report edit | Clean |

Markdown lint availability:

- No root `package.json` exists.
- `apps/dsa-web` and `apps/dsa-desktop` package scripts have no markdown lint script.
- `find` found `.venv/bin/markdown2` and `.venv/bin/markdown-it`, but no project markdown lint command.

Rollback:

```bash
git revert <commit>
```
