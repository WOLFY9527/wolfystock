# WolfyStock Frontend Launch UX Gap Register

Date: 2026-05-08
Branch checked: `main`
Mode: same-repo audit only. No app code, backend logic, provider logic, scanner
logic, portfolio logic, backtest logic, launch acceptance shared files, package
files, or runtime configuration were changed.

## Verdict

Frontend launch readiness verdict: **NO-GO**.

The current frontend has the correct deep-space direction in many places, but
several launch-critical routes still expose trade-like decision language,
debug/provider/fallback vocabulary, dense control clusters, native-looking
controls, and fragile fallback behavior. User-facing pages should be remediated
before admin/internal polish.

## Browser Evidence

Method:

- Browser: Playwright Chromium against an isolated Vite dev server.
- URL: `http://127.0.0.1:5176`.
- Viewports: desktop `1440x1000`; mobile/narrow `390x844`.
- Backend mode: mocked `/api/v1/**` responses for authenticated product/admin
  states; no live provider, portfolio, scanner, backtest, broker, or backend
  mutation logic was called.
- Screenshots and JSON metrics were written to
  `/tmp/wolfystock-frontend-launch-ux-audit/` and are intentionally not part of
  this docs commit.
- Existing shared ports observed before the audit: `8000` Python listener,
  `5173` Vite listener. They were not killed or reused for the audit server.
- Task-owned port used: `5176`.

Routes inspected:

- `/zh`
- `/zh/chat`
- `/zh/scanner`
- `/zh/watchlist`
- `/zh/market-overview`
- `/zh/market/rotation-radar`
- `/zh/backtest/results/34` as the available backtest result route
- `/options-lab`
- `/zh/portfolio`
- `/zh/admin/users`
- `/zh/admin/logs`
- `/zh/admin/cost-observability`
- `/zh/admin/evidence-workflow`
- `/zh/admin/market-providers`
- `/zh/admin/provider-circuits`

Important limitation: `/zh/market-overview` initially blanked under a minimal
temperature payload with `Cannot read properties of undefined (reading
'overall')`. A rerun with a fuller fallback payload rendered the route. This is
therefore tracked as a frontend fallback-hardening blocker, not as evidence that
the happy-path layout is always blank.

## Top 10 Launch-Blocking UX Issues

1. `/zh` presents a large `AI 动作 买入` result in the first viewport. Launch copy
   should not read like direct personalized trade advice by default.
2. `/zh/chat` leads with `开仓执行判断` and prompt examples asking for buy points,
   stop loss, and target prices before establishing analysis-only framing.
3. `/zh/scanner` is not productized: the first screen is dominated by config,
   history, diagnostics, provider/mock/fallback labels, and 131 buttons on
   desktop metrics.
4. `/zh/scanner` mobile is effectively unusable as a launch surface: measured
   full-page height was 7869 px, with 587 tiny-text nodes and diagnostics before
   clear candidate decision flow.
5. `/zh/portfolio` exposes `交易工作台`, `股票买卖`, and `提交交易` in the default
   surface. Even if this is ledger bookkeeping, it reads as a trade/order
   affordance.
6. `/zh/market-overview` has a blank-screen failure mode when the temperature
   response is incomplete instead of falling back to a user-readable degraded
   state.
7. `/options-lab` shows option chain tables and strategy controls before the
   safety/decision framing is strong enough, with native-looking inputs and
   `mock`/provider terms visible in default text.
8. `/zh/backtest/results/34` keeps export, rerun, data quality, execution
   assumptions, and Trace/ledger controls too close to the primary result story.
9. Admin observability pages default to raw operational vocabulary
   (`Provider`, `Route`, `Cache`, `TTL`, `fallback`, `schema`, `raw`) instead of
   productized operator summaries.
10. `/zh/admin/logs` exposes destructive cleanup actions and an `原始日志` tab in
    the default flow; these should be secondary, confirmed, and capability-
    framed.

## Page-by-Page Register

Scoring: `1` = launch blocker, `5` = launch-ready. "Risk" describes the likely
implementation risk of the recommended fix, not the severity of the finding.

| Route | Launch readiness score | P0 blockers | P1 issues | Recommended fix | Likely files to touch | Risk |
| --- | ---: | --- | --- | --- | --- | --- |
| `/zh` | 2 | First viewport can present `AI 动作 买入` as a primary decision. This reads like direct trade advice rather than bounded analysis. | No semantic page heading was detected; native-looking search input; data-quality/developer vocabulary is visible near the primary report; some large empty vertical bands remain. | Remap decision labels to launch-safe analytical states such as `仅观察`, `有条件可交易`, `不建议`, or `数据不足，禁止判断`; make conditions and no-advice framing primary; keep developer/data-quality evidence collapsed behind clearer product language. | `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`, `apps/dsa-web/src/pages/HomeSurfacePage.tsx`, `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx` | Behavior-risky if decision label semantics change; otherwise visual/copy-only. |
| `/zh/chat` | 2 | Default prompt card `开仓执行判断` asks for entry, stop, and target before the user provides context, making the first impression execution-led. | Right-side console is overpacked; long prompt chips look like cards inside a tool; many unknown evidence badges are visible before a question; mobile first fold hides the control context. | Reframe prompt starters around analysis readiness and risk scenarios, not opening positions; collapse advanced lens/evidence controls until input exists; use a simpler first-run empty state with one primary composer. | `apps/dsa-web/src/pages/ChatPage.tsx`, `apps/dsa-web/src/pages/__tests__/ChatPage.test.tsx`, `apps/dsa-web/src/components/layout/Shell.tsx` if shell-level mobile spacing is adjusted | Mostly visual/copy-only; behavior-risky if changing smart-route defaults. |
| `/zh/scanner` | 1 | Candidate decision flow is buried under configuration, result history, diagnostics, provider/mock/fallback labels, and very high action count. Desktop metrics: 131 buttons, 59 card-like regions, 588 tiny-text nodes. | Candidate cards repeat English labels (`Entry range`, `Target price`, `Stop loss`); `开发者诊断` appears in the default scan flow; mobile requires excessive vertical scrolling and stacks actions before candidates. | Redesign the default hierarchy as: summary decision band, candidate shortlist, one primary candidate action plus `更多`, collapsed diagnostics/history. Replace raw provider terms with user-facing freshness states and move debug into disclosure. | `apps/dsa-web/src/pages/ScannerSurfacePage.tsx`, `apps/dsa-web/src/pages/UserScannerPage.tsx`, `apps/dsa-web/src/pages/scannerPageShared.ts`, scanner tests under `apps/dsa-web/src/pages/__tests__/` and `apps/dsa-web/e2e/` | Behavior-risky if action ordering or default expanded panels change; visual-only for copy/density. |
| `/zh/watchlist` | 3 | None observed. | Filter row and batch actions compete with the list; mobile truncates timestamps; native-looking select/input count remains high; batch `扫描当前筛选` and `回测当前筛选` are too prominent for a default watchlist. | Make watchlist rows the primary surface; move batch operations behind a compact toolbar or selection mode; improve mobile row cards and timestamp wrapping. | `apps/dsa-web/src/pages/WatchlistPage.tsx`, `apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx` | Mostly visual-only; behavior-risky if batch action availability changes. |
| `/zh/market-overview` | 2 | Incomplete temperature payload caused a blank route during browser inspection. Launch fallback must never blank the page. | Happy-path fallback view is readable but still dominated by cache/backup/N/A states; no top-level product heading was detected; many market panels render as dense rows with repeated fallback badges. | Harden `MarketOverviewPage` and API normalizers against partial payloads; keep the current degraded state but summarize fallback once per zone; make the first viewport answer "what market state can I trust?" before showing all panels. | `apps/dsa-web/src/pages/MarketOverviewPage.tsx`, `apps/dsa-web/src/api/market.ts`, `apps/dsa-web/src/api/marketOverview.ts`, `apps/dsa-web/src/pages/__tests__/MarketOverviewPage.test.tsx` | Behavior-risky because fallback/error handling changes; layout cleanup is visual-only. |
| `/zh/market/rotation-radar` | 3 | None observed. | Default view repeats `备用`/`mock`; ETF proxy quality section is hard to interpret; developer details are collapsed but raw freshness terms still dominate user-facing copy. | Productize fallback language into `数据不足`, `部分可用`, `等待快照`; make the first theme card explain "why it matters" and "what to watch next" before proxy mechanics. | `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx`, `apps/dsa-web/src/api/marketRotation.ts`, `apps/dsa-web/src/pages/__tests__/MarketRotationRadarPage.test.tsx` | Mostly visual/copy-only. |
| `/zh/backtest/results/34` | 3 | None observed. | Result story is strong, but export/rerun/preset actions, `数据质量`, `执行假设`, ledger and Trace controls are too prominent; mobile first fold is consumed by the hero and KPI cards. | Keep the report/KPI story first; move exports, reruns, execution assumptions, raw ledger and Trace under a compact evidence drawer; preserve no-broker/no-order wording. | `apps/dsa-web/src/pages/DeterministicBacktestResultPage.tsx`, `apps/dsa-web/src/components/backtest/*`, `apps/dsa-web/src/pages/__tests__/DeterministicBacktestResultPage.test.tsx` | Visual-only unless export/rerun availability is gated. |
| `/options-lab` | 2 | None observed as an order affordance, but the surface is close to a trading workbench and needs stronger default safety framing before launch. | Native-looking inputs/selects; `看涨`/`看跌`/`赌波动` controls and option chain tables appear before decision safety; `mock`, `Provider`, and route/debug terms appear in default text. | Put the decision/safety panel above chain tables; rename risky mode labels to scenario language; collapse raw chain ranking until assumptions are set; replace raw provider/mock copy with user-facing data readiness. | `apps/dsa-web/src/pages/OptionsLabPage.tsx`, `apps/dsa-web/src/api/optionsLab.ts`, `apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx`, Options e2e specs | Visual/copy-only for hierarchy; behavior-risky if chain loading/default strategy evaluation changes. |
| `/zh/portfolio` | 2 | Default `交易工作台`, `股票买卖`, and `提交交易` read as trade/order affordances. This must be made explicitly ledger-only or hidden until the user intentionally enters edit mode. | 13 controls and 8 native-looking controls detected; allocation/risk cards show `暂无` despite holdings; trade station competes with holdings; mobile hides holdings below summary and controls. | Reframe manual mutations as `记账工作台` or move them behind `编辑流水`; keep holdings, P&L, exposure, FX status, and read-only broker sync as default; ensure no broker-order wording appears. | `apps/dsa-web/src/pages/PortfolioPage.tsx`, `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx`, `apps/dsa-web/e2e/fixtures/portfolioSmoke.ts` | Behavior-risky if default mutation affordances are gated; visual-only for copy/layout. |
| `/zh/admin/users` | 3 | None observed. | English `No sessions` appears in Chinese route; raw-session/privacy explanation is too prominent; admin nav is dense on desktop. | Localize remaining status labels and make privacy/raw-session explanation a collapsed "security projection" note. | `apps/dsa-web/src/pages/AdminUsersPage.tsx`, `apps/dsa-web/src/pages/__tests__/AdminUsersPage.test.tsx` | Visual/copy-only. |
| `/zh/admin/logs` | 2 | None for public users, but admin default view exposes cleanup/destructive operations too prominently for a launch control plane. | `原始日志` tab is top-level; cleanup buttons are visible in the first flow; React emitted a duplicate-key warning in browser inspection; storage summary empty state is developer-ish. | Make default view business sessions only; move raw logs and cleanup into a confirmed maintenance drawer; fix duplicate list keys; make capacity empty states operator-readable. | `apps/dsa-web/src/pages/AdminLogsPage.tsx`, `apps/dsa-web/src/api/adminLogs.ts`, `apps/dsa-web/src/pages/__tests__/AdminLogsPage.test.tsx` | Behavior-risky for cleanup gating; visual-only for tab hierarchy/copy. |
| `/zh/admin/cost-observability` | 2 | None observed for external users. | Page auto-renders a `dry-run` diagnostic flow and browser load triggered a mocked POST; raw terms (`Provider`, `MarketCache`, `fallback`, `CACHE`, response shape) dominate default view; 8 controls in first surface. | Present a read-only cost health summary first; require an explicit secondary action for quota dry-run; collapse response-shape/developer sections; translate provider/cache terms to operator labels. | `apps/dsa-web/src/pages/AdminCostObservabilityPage.tsx`, `apps/dsa-web/src/api/adminCost.ts`, `apps/dsa-web/src/pages/__tests__/AdminCostObservabilityPage.test.tsx` | Behavior-risky if dry-run timing changes; visual-only for copy/hierarchy. |
| `/zh/admin/evidence-workflow` | 3 | None observed; page is read-only. | Raw artifact/schema/provider/debug language is still visible in default text; `releaseApproved=false` is useful evidence but too raw for the primary view; many runbook cards appear at once. | Keep the offline/read-only boundary, but replace raw fields with operator states and move schema/provider/debug caveats to collapsed evidence details. | `apps/dsa-web/src/pages/AdminEvidenceWorkflowPage.tsx`, `apps/dsa-web/src/pages/__tests__/AdminEvidenceWorkflowPage.test.tsx` | Visual/copy-only. |
| `/zh/admin/market-providers` | 3 | None observed. | Default view is still a provider/cache/TTL table in card form; raw `mock-provider`, `cache key`, `TTL`, and `原始限制代码` appear in launch view. | Make first viewport an operator SLA summary and degraded-state explanation; keep cache keys, TTL and response-shape details collapsed. | `apps/dsa-web/src/pages/MarketProviderOperationsPage.tsx`, `apps/dsa-web/src/api/marketProviderOperations.ts`, `apps/dsa-web/src/pages/__tests__/MarketProviderOperationsPage.test.tsx` | Visual/copy-only unless drill-through behavior changes. |
| `/zh/admin/provider-circuits` | 2 | None observed. | The page title and first panels expose low-level `Provider / Category / Route`, `fallback`, `Cache`, buckets, and diagnostics vocabulary; it reads like an implementation console rather than an operator readiness view. | Lead with "can production calls proceed?", "what is blocked?", and "what needs credentials?" summaries; move route/category/bucket diagnostics into collapsed details. | `apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx`, `apps/dsa-web/src/api/adminProviderCircuits.ts`, `apps/dsa-web/src/pages/__tests__/AdminProviderCircuitDiagnosticsPage.test.tsx` | Visual/copy-only unless readiness decision semantics change. |

## Cross-Route Patterns

- User-facing launch surfaces need a safer financial language layer. `买入`,
  `开仓执行判断`, `股票买卖`, and `提交交易` should not be primary default labels
  unless the surrounding copy clearly says analysis-only, ledger-only, or
  read-only.
- Debug/provider/cache/fallback details are often collapsed technically but
  still visible as default words. The launch UI should default to
  `数据不足`, `部分可用`, `等待快照`, `缓存`, `备用`, and clear operator summaries.
- Dense tables and repeated panels are the main usability problem. Scanner,
  Options, Backtest, Watchlist, Portfolio, and admin observability pages need
  route-level hierarchy, not just polished cards.
- Mobile is usable without horizontal overflow, but many routes are not
  launch-usable on narrow screens because primary workflows require excessive
  vertical scanning or hide the main artifact below controls.
- Several routes still show native-looking inputs/selects or very small control
  clusters. Accessibility fixes should target touch size, labels, focus states,
  and disclosure semantics without broad visual rewrites.

## Recommended Remediation Order

1. Home safety language and report decision label mapping.
2. Chat prompt-starter safety and first-run hierarchy.
3. Scanner launch redesign: candidate-first, diagnostics collapsed.
4. Portfolio default read-only/accounting hierarchy and trade-word cleanup.
5. Market Overview fallback hardening and user-readable degraded state.
6. Options Lab hierarchy: safety/decision before chain tables.
7. Backtest result evidence drawer and mobile first-fold cleanup.
8. Watchlist row-first mobile/desktop density pass.
9. Admin Logs cleanup/raw-log demotion and duplicate-key fix.
10. Admin observability productization for cost/provider/circuit pages.

## Validation Notes

Docs-only validation for this audit should be sufficient. No lint/build is
required unless docs tooling changes. Required follow-up validation before any
frontend implementation should include route-specific Playwright screenshots at
`1440x1000` and `390x844`, no horizontal overflow checks, console/page error
checks, and targeted route tests for any behavior-risky gating or fallback work.
