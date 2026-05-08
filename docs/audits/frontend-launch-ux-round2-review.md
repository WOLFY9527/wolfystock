# WolfyStock Frontend Launch UX Round 2 Review

Date: 2026-05-09
Branch checked: `main`
Expected main commit: `94fb248c feat(web): harden home chat launch language`
Mode: audit-only. No app code, backend logic, provider logic, portfolio logic, package files, runtime configuration, screenshots, or launch matrix files were changed.

## Executive Verdict

Frontend launch readiness verdict: **NO-GO** for the committed `main` snapshot.

The first productization batch resolved the largest public-facing safety problems on Home, Chat, Scanner, Options Lab, Rotation Radar, and much of the admin read-only evidence flow. However, two original launch blockers are still not fully closed on committed `main`:

1. `Market Overview` partial temperature payload hardening is not committed to `main`. A concurrent local patch appeared during this audit and adds the intended normalization/test coverage, but it is unstaged, outside this audit, and currently breaks `npm run build` with TypeScript errors.
2. `Portfolio` still exposes `交易工作台`, `股票买卖`, and `提交交易` in the default source. It is better framed by ledger/manual-record metadata than round 1, but the visible Chinese labels still read like trade/order affordances.

Strict P0 disposition: **3 resolved / 2 remaining**.

Conditional verdict: if the in-flight Market Overview fallback fix lands cleanly and Portfolio copy is changed from trade/order wording to ledger/manual-record wording, the remaining state looks like **GO-WITH-POLISH** rather than broad NO-GO.

## Browser Method

- Browser engine: Playwright Chromium.
- Initial clean-main validation port: isolated preview port `4178`.
- Supplemental browser port: existing isolated frontend port `5176`, reused because a later rebuild on `4179` was blocked by unrelated dirty app changes.
- Viewports: desktop `1440x1000`; mobile/narrow `390x844`.
- Backend mode: mocked auth/product/admin API routes for protected route inspection; live providers, broker calls, portfolio mutations, scanner runtime, backtest runtime, and destructive admin operations were not called.
- Screenshots/videos: Playwright generated transient failure artifacts under `apps/dsa-web/test-results/`; no screenshots or videos are committed by this audit.
- Existing shared ports observed before audit: backend listeners on `8000`/`8001`, Vite listener on `5173`, existing frontend listener on `5176`. No shared server was killed.

## Validation Evidence

| Check | Result |
| --- | --- |
| Preflight | PASS: `main`, `HEAD=origin/main=94fb248c`, clean at audit start. |
| `DSA_WEB_PLAYWRIGHT_PORT=4178 npx playwright test e2e/critical-route-launch-smoke.spec.ts --config playwright.config.ts` | PASS: 10/10. Covered Home, Market Overview, Rotation Radar, Scanner, Backtest result, Options Lab, Portfolio, Admin Cost, Provider Circuits, admin user portfolio projection at both viewports. |
| `DSA_WEB_PLAYWRIGHT_PORT=5176 npx playwright test e2e/public-safety-ai-scanner-options.smoke.spec.ts e2e/market-overview-scanner.smoke.spec.ts e2e/no-secret-critical-surface.smoke.spec.ts e2e/admin-evidence-workflow.spec.ts --config playwright.config.ts` | PARTIAL: 20/23 passed. The three failures were supplemental-harness issues: Options Lab strategy table is now hidden/collapsed where the older no-secret test expected it visible; admin cost/provider request counts doubled on the dev server. No raw-secret/overflow assertion failed before those count/visibility expectations. |
| Temporary `/tmp/wolfystock-round2-admin-extra.spec.ts` against `5176` | PASS: 3/3. Covered `/zh/admin/users`, `/zh/admin/logs`, `/zh/admin/market-providers` at both viewports with mocked admin data. |
| Rebuild attempt on `4179` and standalone `npm run build` | BLOCKED by unrelated dirty local app changes in `apps/dsa-web/src/api/market.ts`, `MarketOverviewPage.tsx`, `MarketOverviewPage.test.tsx`, and `market-overview-scanner.smoke.spec.ts`. Current error: `Property 'overall' does not exist on type '{}'` in `src/api/market.ts`. |

## Original P0/P1 Disposition

| Original issue | Round-2 status | Evidence |
| --- | --- | --- |
| `/zh` first viewport showed `AI 动作 买入`. | **Resolved** | Browser spot check and launch smoke show a neutral analysis panel/search-first landing. No forbidden trading wording in launch smoke. |
| `/zh/chat` default prompt led with `开仓执行判断`. | **Resolved** | Public safety e2e shows `WOLFY AI 研究台`, `观察条件检查`, risk/evidence framing, and no advice/raw internals. Source override removes the execution-led starter. |
| `/zh/scanner` hid candidate flow under config/history/diagnostics and was unusable on mobile. | **Resolved to P1 polish** | Scanner safety and market overview scanner specs pass on desktop/mobile. Candidate pane and scroll region are visible; diagnostics are collapsed by default. |
| `/zh/market-overview` blanked on incomplete temperature payload. | **Still open on committed main** | The committed `main` version does not normalize partial temperature scores before render. A concurrent local patch adds this normalization and a partial-payload e2e, but it is not part of main and currently fails build. |
| `/zh/portfolio` read as broker/order/trade affordance. | **Still open** | Source still contains default `交易工作台`, `股票买卖`, and `提交交易`. Existing smoke verifies no raw credentials/order payloads, but the visible Chinese labels still fail the ledger/manual-record framing check. |
| `/options-lab` showed strategy/chain before safety framing. | **Resolved to polish** | Public safety e2e confirms `数据不足，禁止判断`, synthetic data warning, and collapsed developer details. Older no-secret expectation failed only because a strategy comparison panel is now hidden by default. |
| `/zh/backtest/results/34` exposed evidence/export controls too close to the result story. | **Mostly resolved / P1 polish** | Critical smoke passes with no raw broker/order artifacts. Export buttons and advanced evidence remain visible but are not P0 launch blockers. |
| `/zh/admin/logs` raw logs and cleanup were too prominent. | **Partially resolved / P1 remains** | Extra browser probe confirms `业务事件` is default and `原始日志` is secondary, with no overflow. Cleanup preview/destructive controls remain present in the page source and should stay under tighter maintenance framing. |
| Admin cost/provider/circuit pages exposed raw provider/cache/schema vocabulary. | **Partially resolved / P1 remains** | Developer/response-shape sections are collapsed and secret-free, but `TTL`, `Provider`, `Dry-run`, `Provider SLA`, and route/cache vocabulary remain visible on primary admin surfaces. |
| `/zh/admin/users` retained English status labels. | **Still open P1** | Extra browser snapshot still shows `No sessions` in the Chinese route. |

## Page-by-Page Score

Scoring: `1` = launch blocker, `5` = launch-ready.

| Route | Score | Round-2 notes |
| --- | ---: | --- |
| `/zh` | 4 | Search-first, neutral launch surface. No forbidden first-viewport trading language observed. |
| `/zh/chat` | 4 | Reframed as research/evidence. Protected route requires auth, but mocked-auth browser path is usable on both viewports. |
| `/zh/scanner` | 4 | Candidate-first path now test-covered on desktop/mobile; diagnostics collapsed. Remaining polish is density and raw fallback vocabulary in secondary states. |
| `/zh/watchlist` | 4 | Mobile usability and overflow pass in browser smoke. Batch actions are less launch-blocking but still need hierarchy polish. |
| `/zh/market-overview` | 2 | Main still lacks committed partial-temperature fallback hardening. In-flight dirty patch appears to fix this but is not launch evidence for main. |
| `/zh/market/rotation-radar` | 4 | Read-only shell, no trading instruction language, developer details collapsed in launch smoke. |
| `/zh/backtest/results/34` | 4 | Report/result shell is clean in critical smoke. Export/evidence controls remain P1 polish. |
| `/options-lab` | 4 | Decision safety leads; synthetic data and no-decision state are explicit; detailed chain/strategy panels are collapsed. |
| `/zh/portfolio` | 2 | Credential/order payloads are hidden, but default labels still say `交易工作台`, `股票买卖`, `提交交易`. Needs ledger/manual-record copy pass before launch. |
| `/zh/admin/users` | 3 | Route renders and is overflow-free; Chinese page still shows `No sessions`. |
| `/zh/admin/logs` | 3 | `业务事件` is default and `原始日志` is secondary; cleanup controls still need maintenance-mode containment. |
| `/zh/admin/cost-observability` | 3 | Secret/raw details are collapsed, but `dry-run` remains a primary operational concept and the dev server double-triggered quota dry-run requests. |
| `/zh/admin/evidence-workflow` | 4 | Browser regression passes desktop/mobile. Static read-only boundary, no write/upload/approval affordance, raw/schema notes collapsed. |
| `/zh/admin/market-providers` | 3 | Read-only and overflow-free; raw-ish provider/cache terms such as `TTL`, provider IDs, cache keys, and Admin Logs drill-through remain visible. |
| `/zh/admin/provider-circuits` | 3 | Read-only diagnostics and no raw secret leakage, but `Provider SLA`, `Dry-run`, route/category/bucket vocabulary remain primary. |

## Remaining Blockers

### P0

1. **Market Overview fallback hardening is not cleanly landed on main.**
   - Current main can still blank or hard-fail on incomplete temperature score payloads.
   - The concurrent local patch is directionally correct but currently fails TypeScript build because `payload?.scores || {}` narrows to `{}` before score-key access.

2. **Portfolio still presents trade/order-like default labels.**
   - The user-facing route still includes `交易工作台`, `股票买卖`, and `提交交易`.
   - This should become `记账工作台` / `手工录入：流水` / `提交流水记录` or equivalent, with broker/order wording kept only for clearly read-only import/sync contexts.

### P1

- Admin Users still leaks English `No sessions` in Chinese UI.
- Admin Logs raw-log and cleanup controls are secondary but still visible as tab/actions; destructive cleanup should remain behind maintenance confirmation mode.
- Admin Cost still foregrounds `dry-run` and operational route/cost internals.
- Market Provider Ops and Provider Circuits still expose provider/cache/TTL/bucket vocabulary as primary operator text.
- Backtest result still has export/evidence controls close to the primary result narrative.

## File-Conflict-Safe Remediation Clusters

1. **Market Overview fallback cluster**
   - Files: `apps/dsa-web/src/api/market.ts`, `apps/dsa-web/src/pages/MarketOverviewPage.tsx`, `apps/dsa-web/src/pages/__tests__/MarketOverviewPage.test.tsx`, `apps/dsa-web/e2e/market-overview-scanner.smoke.spec.ts`.
   - Scope: finish partial temperature normalization, fix TypeScript typing, verify degraded state on desktop/mobile.
   - Conflict note: these files are already dirty from another local session during this audit.

2. **Portfolio ledger-language cluster**
   - Files: `apps/dsa-web/src/pages/PortfolioPage.tsx`, `apps/dsa-web/src/i18n/core.ts`, `apps/dsa-web/e2e/fixtures/portfolioSmoke.ts`, Portfolio page tests.
   - Scope: replace trade/order labels with ledger/manual-record wording; keep broker sync/import visibly read-only; add Chinese wording guard for `交易工作台`, `股票买卖`, `提交交易` on default launch route.

3. **Admin Logs maintenance cluster**
   - Files: `apps/dsa-web/src/pages/AdminLogsPage.tsx`, `apps/dsa-web/src/api/adminLogs.ts`, `apps/dsa-web/src/pages/__tests__/AdminLogsPage.test.tsx`, optional e2e harness.
   - Scope: keep raw logs and cleanup behind a maintenance disclosure/mode; preserve preview-confirm behavior; add browser route coverage.

4. **Admin ops vocabulary cluster**
   - Files: `AdminCostObservabilityPage.tsx`, `MarketProviderOperationsPage.tsx`, `AdminProviderCircuitDiagnosticsPage.tsx`, related API tests and e2e specs.
   - Scope: lead with operator readiness states; collapse provider/cache/TTL/schema/bucket vocabulary behind details; keep read-only/no-runtime-change evidence visible.

5. **Admin user localization cluster**
   - Files: `AdminUsersPage.tsx`, `apps/dsa-web/src/i18n/core.ts`, `AdminUsersPage.test.tsx`.
   - Scope: replace English `No sessions`/risk badges with Chinese labels on `/zh/admin/users`.

6. **Backtest result evidence hierarchy cluster**
   - Files: deterministic backtest result page/components and tests.
   - Scope: keep report/KPI narrative first; move export, ledger, trace, and execution assumptions into a compact evidence drawer.

## Final Status

Round 2 shows meaningful productization progress, but launch should not be marked GO until the committed `main` branch has a clean Market Overview partial-payload fallback and Portfolio no longer reads like a trading/order surface by default.
