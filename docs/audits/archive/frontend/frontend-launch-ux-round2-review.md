# WolfyStock Frontend Launch UX Round 2 Review

Date: 2026-05-09
Branch checked: `main`
Commit checked: `94fb248c feat(web): harden home chat launch language`
Mode: audit-only. No app code, backend/provider/scanner/portfolio/backtest logic,
runtime configuration, launch acceptance shared files, package files, or
screenshots were changed.

## Executive Verdict

Frontend launch readiness verdict: **NO-GO**.

The first productization batch materially improved the launch posture. The
highest-risk advice wording on Home and Chat is gone, Market Overview no longer
blanked under the mocked route payload, Options Lab now has explicit read-only
and no-advice framing, and admin pages are much closer to operator summaries.

The remaining launch blockers are narrower than round 1, but still block a GO:

1. `/zh/scanner` remains too dense and configuration/diagnostics-led for a
   launch default surface. Mobile is technically overflow-free, but not usable
   as a first-run candidate workflow.
2. `/zh/portfolio` still exposes `交易工作台`, `股票买卖`, `买入`, `卖出`, and
   `提交交易` in the default visible route content.

Tracked round-1 P0 disposition: **4 resolved / 2 remaining**.

## Browser Evidence

- Method: Playwright Chromium against a task-owned Vite dev server.
- URL: `http://127.0.0.1:5176`.
- Viewports: desktop `1440x1000`; mobile `390x844`.
- Harness: repo smoke fixtures plus temporary `/tmp` audit-only mocks for
  protected product/admin states.
- Evidence path: `/tmp/wolfystock-frontend-launch-ux-round2/`.
- Screenshot path: `/tmp/wolfystock-frontend-launch-ux-round2/screenshots/`.
- Existing shared ports observed before audit: backend listener on `8000`,
  frontend listener on `5173`. They were not killed or reused.
- Task-owned port used: `5176`.

All 15 routes were inspected at both viewports. No horizontal overflow, no
solid gray blocks, and no console/page errors were observed in the final audit
pass.

## Page-by-Page Result

Scoring: `1` = launch blocker, `5` = launch-ready.

| Route | Result | Score | P0 status | P1 status | Round-2 evidence |
| --- | --- | ---: | --- | --- | --- |
| `/zh` | PASS | 4 | `AI 动作 买入` resolved. | Still report-first and has one native input, but no direct trade-action label. | No forbidden trading wording; no overflow; no console errors. |
| `/zh/chat` | PASS | 4 | `开仓执行判断`, buy-point, stop-loss, target-price prompt starters resolved. | Mobile is usable but the composer remains low in the viewport. | First fold uses `WOLFY AI 研究台`, `观察条件检查`, and read-only evidence framing. |
| `/zh/scanner` | FAIL | 2 | Still open: default surface is config/diagnostics/density-led. | Raw/mock/provider vocabulary and huge action count remain. | Desktop: 131 visible buttons, page height 3411px. Mobile: 130 buttons, page height 6879px. |
| `/zh/watchlist` | PASS | 4 | No P0 observed. | Native-looking filter controls remain. | Row-first mobile view is usable; no overflow or console errors. |
| `/zh/market-overview` | PASS | 4 | Blank-route fallback issue not reproduced in final pass. | Cache/fallback vocabulary remains visible in primary content. | Rendered at both viewports with no errors and no overflow. |
| `/zh/market/rotation-radar` | PASS | 4 | No P0 observed. | `备用`/fallback freshness text remains visible. | Read-only, non-buy/sell framing is primary. |
| `/zh/backtest/results/34` | PASS-WITH-POLISH | 4 | No P0 observed. | Export/rerun/evidence controls remain close to primary result story. | Result and KPI hierarchy usable on both viewports; no order/broker wording. |
| `/options-lab` | PASS-WITH-POLISH | 3 | No order CTA observed, but terminology remains close to execution language. | `交易质量判断`, `mock`, `Provider`, and native inputs remain visible. | Safety/no-advice framing is present; chain/strategy details are collapsed. |
| `/zh/portfolio` | FAIL | 2 | Still open: default content reads like trade/order input. | Native controls and ledger/manual-entry hierarchy need polish. | Body text includes `交易工作台`, `股票买卖`, `买入`, `卖出`, `提交交易`. |
| `/zh/admin/users` | PASS-WITH-POLISH | 3 | No P0 observed. | English/raw-ish labels remain, including `Read-only F1/F2` and `No sessions` class of issue from round 1. | Operator page renders cleanly with no overflow/errors. |
| `/zh/admin/logs` | PASS-WITH-POLISH | 3 | Cleanup/raw logs no longer dominate as P0. | `原始日志` and cleanup remain visible secondary concepts; 16-17 buttons. | Business-event framing is primary; no console errors in final pass. |
| `/zh/admin/cost-observability` | PASS-WITH-POLISH | 3 | No P0 observed. | `Cost Observability`, dry-run, model ledger, and raw ops terms remain prominent. | Details collapsed, no secret-like output, no errors. |
| `/zh/admin/evidence-workflow` | PASS | 4 | No P0 observed. | Raw/schema notes still exist but are secondary. | Read-only, offline, human-gated framing is clear. |
| `/zh/admin/market-providers` | PASS-WITH-POLISH | 3 | No P0 observed. | Provider/cache/window terminology remains primary. | Read-only snapshot and no external-call boundary are visible. |
| `/zh/admin/provider-circuits` | PASS-WITH-POLISH | 3 | No P0 observed. | `Provider`, `fallback`, `MarketCache`, `enforcement`, and `ops:providers:read` remain primary. | Operator summary is improved, but still implementation-console flavored. |

## Top Remaining P0 Blockers

1. **Scanner launch usability is still not candidate-first enough.**
   - It is technically usable, but the first viewport still leads with market
     selectors, scan configuration, history, diagnostics, and many actions
     before a clean candidate decision story.
   - Mobile remains especially heavy: 130 buttons and 6879px page height.

2. **Portfolio still uses trade/order wording in the default page.**
   - The route has better portfolio and FX transparency, but the manual-entry
     station still reads as trading execution.
   - Required remediation is copy and hierarchy: ledger/manual-record wording
     first, trading/order vocabulary absent from default launch content.

## Top Remaining P1 Issues

- Options Lab is safer than round 1 but still shows `交易质量判断`, `mock`,
  `Provider`, and native inputs in launch-facing content.
- Admin cost/provider/circuit pages remain too English and implementation-led
  for operator defaults.
- Admin Users still has English status/risk-badge language in a Chinese route.
- Backtest result still puts export/rerun/evidence controls near the main
  result narrative.
- Watchlist and Portfolio still contain native-looking selects/inputs where a
  launch-facing deep-space control should be used.

## Recommended Next Code Tasks

### Cluster 1: Scanner Launch Hierarchy

Files likely involved:

- `apps/dsa-web/src/pages/ScannerSurfacePage.tsx`
- `apps/dsa-web/src/pages/UserScannerPage.tsx`
- `apps/dsa-web/src/pages/scannerPageShared.ts`
- scanner page tests and e2e smoke specs

Task:

- Make the default route candidate/evidence-first.
- Collapse diagnostics/history/provider detail by default.
- Reduce visible action count and mobile vertical scan burden.

### Cluster 2: Portfolio Ledger Language

Files likely involved:

- `apps/dsa-web/src/pages/PortfolioPage.tsx`
- `apps/dsa-web/src/i18n/core.ts`
- `apps/dsa-web/e2e/fixtures/portfolioSmoke.ts`
- Portfolio page tests/e2e guards

Task:

- Replace `交易工作台`, `股票买卖`, `买入`, `卖出`, `提交交易` in default
  launch content with ledger/manual-record wording.
- Keep broker/order concepts only inside clearly read-only sync/import evidence.

### Cluster 3: Options Lab Polish

Files likely involved:

- `apps/dsa-web/src/pages/OptionsLabPage.tsx`
- Options Lab API/test/e2e files

Task:

- Rename `交易质量判断` and similar terms to scenario/readiness language.
- Keep `mock`/`Provider`/developer freshness behind secondary details.
- Replace native-looking form controls.

### Cluster 4: Admin Ops Vocabulary

Files likely involved:

- `apps/dsa-web/src/pages/AdminCostObservabilityPage.tsx`
- `apps/dsa-web/src/pages/MarketProviderOperationsPage.tsx`
- `apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx`
- related admin API tests/e2e specs

Task:

- Lead with operator readiness summaries.
- Move provider/cache/TTL/schema/bucket/route language behind collapsed details.
- Preserve the current read-only/no-runtime-change boundaries.

### Cluster 5: Admin Logs and Users Polish

Files likely involved:

- `apps/dsa-web/src/pages/AdminLogsPage.tsx`
- `apps/dsa-web/src/pages/AdminUsersPage.tsx`
- `apps/dsa-web/src/i18n/core.ts`
- related admin tests/e2e specs

Task:

- Keep cleanup/raw log operations under a maintenance disclosure.
- Localize remaining English risk/status labels on `/zh/admin/users`.

### Cluster 6: Backtest Evidence Hierarchy

Files likely involved:

- deterministic backtest result page/components
- deterministic backtest result tests/e2e specs

Task:

- Keep report/KPI story first.
- Move export, trace, ledger, and execution assumptions into a compact evidence
  drawer without changing backtest logic.

## Safety Confirmation

- No backend/provider/scanner/portfolio/backtest runtime logic was touched.
- No launch acceptance shared files were touched.
- No app code, tests, package files, or runtime config were changed.
- Screenshots and JSON metrics remain under `/tmp` and are not committed.
- This report is the only repository file changed by this audit.
