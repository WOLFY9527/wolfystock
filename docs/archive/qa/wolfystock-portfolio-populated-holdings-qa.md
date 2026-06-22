# WolfyStock Portfolio Populated Holdings QA

Date: 2026-05-05 Asia/Shanghai  
Repository: `/Users/yehengli/daily_stock_analysis`  
Branch: `main`  
Mode: QA/audit/report only; no product code, tests, CSS, backend/API, package, config, runtime, or changelog changes

## 1. Executive Summary

Overall assessment: **PASS with minor follow-up**.

Data mode used: **contract-faithful Playwright mock**. No safe real local authenticated portfolio account was used, and no live portfolio data was mutated. The mock payload was built from the current frontend Portfolio tests, frontend API/type contracts, and backend Portfolio API contract tests. It used one active account, three positions across US/HK/CN markets, mixed profitable/loss holdings, two FX pairs, populated analytics, concentration, currency exposure, market exposure, symbol exposure, and P&L contributor fields.

Top findings:

- **PASS:** `/zh/portfolio` rendered populated accounts and positions at desktop `1440x1000` and mobile `390x844`.
- **PASS:** risk overview, concentration drilldown, currency exposure drilldown, market exposure drilldown, P&L contributors, and risk hints rendered with realistic holdings.
- **PASS:** no console errors, page errors, horizontal overflow, raw/debug/provider/schema leakage, visible native-looking controls, or mutation requests were observed in the Playwright route pass.
- **P3 follow-up:** the desktop shell language/logout controls measured 25 px high in the Playwright small-button scan. This is outside the Portfolio page body and should be grouped with shell/mobile touch-target polish, not fixed in this report task.

Recommended next actions:

1. Add or extend a dedicated Portfolio populated browser/Playwright fixture in a later task so future QA can rerun this contract-faithful scenario without reconstructing the mock manually.
2. Handle the compact shell language/logout controls in a separate shell/touch-target polish task if the team wants a strict 32 px or 44 px target everywhere.
3. Re-run this same route against live local authenticated portfolio data when a safe read-only account is available.

## 2. Methodology

Read-first inputs:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/qa/wolfystock-workflow-qa-pass.md`
- `docs/operations/parallel-codex-playbook.md`
- `docs/checks/design-guard.md`
- `docs/checks/ci-gate-clarity.md`
- `docs/audits/archive/frontend/wolfystock-global-codebase-audit.md`
- `docs/audits/archive/frontend/wolfystock-phase0-bundle-design-inventory.md`

Preflight commands:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -76
./scripts/task_preflight.sh || true
```

Preflight result:

- `pwd`: `/Users/yehengli/daily_stock_analysis`
- branch: `main`
- initial dirty file: `apps/dsa-web/src/pages/WatchlistPage.tsx`
- later parallel state also included `apps/dsa-web/src/components/market-overview/marketOverviewPrimitives.tsx`
- required recent commits were present, including `2aa5ddf`, `f1bac8c`, `34170d1`, `b55da50`, `83b8fbd`, `18b78fb`, `ba6fe0c`, and `23a19fe`
- while this QA was running, another session advanced local `main` to `7b2f58f fix(report): localize preview report chrome`

Static and targeted commands:

```bash
cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
rg -n "PortfolioPage|portfolioApi|analytics|positions|accounts|risk|exposure|currency|market|concentration|pnl|holdings" src/pages src/api src/types src/components | head -260
find src -path "*__tests__*" -type f | grep -Ei "Portfolio|portfolio"
npm run check:design
npm run lint
npm run build
npm run test -- src/pages/__tests__/PortfolioPage.test.tsx --run

cd /Users/yehengli/daily_stock_analysis
python3 -m compileall -q src api
python3 -m pytest tests/test_portfolio_api.py -q
./scripts/ci_gate.sh
```

Playwright/browser method:

- Runner: headless Chromium through Playwright from the existing `apps/dsa-web` install.
- Frontend server: `npm run preview -- --host 127.0.0.1 --port 5176`.
- Route: `http://127.0.0.1:5176/zh/portfolio`.
- Viewports: desktop `1440x1000`; mobile/narrow `390x844`.
- Auth strategy: mocked authenticated admin user via `/api/v1/auth/status`.
- Data strategy: contract-faithful mocked Portfolio API responses.
- Mutation guard: all non-GET/HEAD/OPTIONS `/api/v1/**` requests were recorded; observed mutation request list was empty.
- Browser verification was not separately repeated in Safari or the in-app browser because the Playwright pass fully covered the required route, both viewports, console/page errors, overflow, leakage, controls, and mutation guard.

Ports:

| Port | Status before verification | Use in this pass |
| --- | --- | --- |
| `8000` | Existing Python listener | Observed only; not touched |
| `8001` | Free | Not used |
| `5173` | Existing Vite/Codex frontend listener | Observed only; not touched |
| `4173` | Free | Not used |
| `5174` | Free | Not used |
| `5175` | Free | Not used |
| `5176` | Free, then started isolated preview | Used for Playwright QA; stopped after verification and confirmed free |

Limitations:

- This was not live-data verification.
- The mock was faithful to current contracts, but it cannot prove live auth/session/data availability.
- No screenshots, videos, traces, or Playwright reports were retained or committed.

## 3. Static Quality Baseline

| Check | Result | Key output | Notes |
| --- | --- | --- | --- |
| `npm run check:design` | PASS | 214 files scanned; 0 blocking; 0 warnings | Design guard clean. |
| `npm run lint` | PASS | `eslint .` exited 0 | No lint errors. |
| `npm run build` | PASS with warning | 3158 modules transformed; built in 9.30s | Vite large chunk warning remains. |
| Vite chunk warning | WARN | `DeterministicBacktestChartWorkspace-CitVz9mO.js` 532.42 kB / 178.83 kB gzip | Existing large chart workspace warning, not Portfolio-specific. |
| Backend compile | PASS | `python3 -m compileall -q src api` exited 0 | No output. |
| Portfolio page tests | PASS | 1 file, 42 tests passed in 7.53s | `PortfolioPage.test.tsx`. |
| Portfolio API tests | PASS | 29 passed in 14.49s | `tests/test_portfolio_api.py`. |
| Full `ci_gate` | PASS | 1993 passed, 3 skipped, 1 warning, 203 subtests in 161.07s | Local warnings: `flake8` missing, `akshare` missing; pytest warning from Pydantic serializer. |

## 4. Portfolio Data Contract Summary

Mocked endpoints:

| Endpoint | Method | Mock shape |
| --- | --- | --- |
| `/api/v1/auth/status` | GET | authenticated admin user, camelCase auth contract |
| `/api/v1/portfolio/accounts` | GET | one active `global` account with `CNY` base currency |
| `/api/v1/portfolio/snapshot` | GET | aggregate totals, `fx_rates`, `portfolio_attribution`, `analytics`, account snapshots, and positions |
| `/api/v1/portfolio/risk` | GET | concentration, sector concentration, drawdown, stop loss, industry/account attribution |
| `/api/v1/portfolio/trades` | GET | two recent trade records |
| `/api/v1/portfolio/cash-ledger` | GET | empty paginated list |
| `/api/v1/portfolio/corporate-actions` | GET | empty paginated list |
| `/api/v1/portfolio/broker-connections` | GET | empty connection list |
| `/api/v1/portfolio/imports/brokers` | GET | one broker registry item |

Account fields covered:

- `id`, `owner_id`, `name`, `broker`, `market`, `base_currency`, `is_active`, `created_at`, `updated_at`
- snapshot account fields including `account_id`, `account_name`, `as_of`, `cost_method`, `total_cash`, `total_market_value`, `total_equity`, `realized_pnl`, `unrealized_pnl`, `fee_total`, `tax_total`, `fx_stale`, `positions`

Position fields covered:

- `symbol`, `market`, `currency`, `quantity`, `avg_cost`, `total_cost`, `last_price`
- `market_value_base`, `unrealized_pnl_base`, `valuation_currency`
- native/display analytics fields: `cost_basis_native`, `market_value_native`, `unrealized_pnl_native`, `unrealized_pnl_pct`, `display_market_value`, `display_unrealized_pnl`, `display_currency`, `display_fx_status`

Analytics fields covered:

- `analytics.pnl.display_currency`
- `analytics.pnl.realized`, `unrealized`, `total`: `amount`, `amount_display`, `percent`, `currency`, `fx_status`
- `analytics.exposure.by_account`, `by_currency`, `by_market`, `by_symbol`, `by_sector`
- `analytics.exposure.sector_status`
- `analytics.risk.largest_position`, `largest_currency`, `largest_market`, `holding_count`, `account_count`, `cash_percent`, `fx_unavailable`, `warnings`

Risk/exposure/P&L details covered:

- Concentration: top holding `00700` at 74.6%.
- Currency exposure: HKD, USD, CNY buckets.
- Market exposure: HK, US, CN buckets.
- P&L: realized gain, unrealized loss, total loss.
- Contributors: profitable `AAPL` and `600519`, loss contributor `00700`.
- Risk hints: high single-position concentration and small holding count.

Optional/data-limited fields:

- Live broker sync state was not exercised because no mutation or external broker sync is allowed in this task.
- Cash ledger and corporate action rendering were only empty-list verified in the route pass.
- Live FX refresh behavior was covered by existing tests, but the route pass did not click refresh because that would send a mutation request.

## 5. Route Verification Matrix

| Route | Mode | Desktop status | Mobile status | Overflow | Console/page errors | Raw/debug leakage | Native controls | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/zh/portfolio` | contract-faithful mock | PASS | PASS | PASS | PASS | PASS | PASS | Populated account, three positions, analytics, FX, exposure, risk, and P&L sections rendered. |

Route check details:

- Desktop `1440x1000`: `overflow = 0`; console errors `0`; page errors `0`; raw leak matches `0`; visible native-control risks `0`; open developer details `0`.
- Mobile `390x844`: `overflow = 0`; console errors `0`; page errors `0`; raw leak matches `0`; visible native-control risks `0`; open developer details `0`.
- Mutation requests: `[]`.
- Unhandled mocked API paths: `[]`.
- Desktop small-button scan found shell controls `EN` and `退出` at 25 px high; mobile scan found no visible button below the scan threshold.

## 6. Populated Holdings Verification

Accounts:

- One active account, `Global QA Account`, rendered in the page and trade station selectors.
- Account totals rendered with `CNY` display currency and non-zero cash, market value, total equity, realized P&L, and unrealized P&L.

Positions:

- Three symbols rendered: `AAPL`, `00700`, and `600519`.
- Markets and currencies were mixed: US/USD, HK/HKD, CN/CNY.
- Position-level unrealized P&L included both gains and losses.

P&L:

- `已实现盈亏`, `未实现盈亏`, and `总盈亏` tiles rendered.
- Realized P&L was positive.
- Unrealized and total P&L were negative.
- P&L contribution rendered both gain and loss areas.

FX transparency:

- Display currency status rendered as `显示货币 CNY`.
- FX tab/copy rendered.
- Snapshot included USD/CNY and HKD/CNY rates.
- No FX refresh mutation was sent.

Currency exposure:

- Currency exposure drilldown rendered.
- HKD was the largest currency exposure.
- USD and CNY were also available through the exposure contract.

Market exposure:

- Market exposure drilldown rendered.
- HK was the largest market exposure, with US and CN buckets also in the contract.
- Market hint rendered coherently without raw provider/debug text.

Concentration:

- Concentration drilldown rendered.
- Largest holding `00700` at 74.6% produced a coherent concentrated/highly concentrated state.
- The explanatory sentence rendered in Chinese.

P&L contributors:

- Gain contributors included profitable positions.
- Loss contributors included the losing `00700` position.
- Amounts rendered as user-facing money, not raw JSON.

Risk hints:

- Risk hints rendered.
- High single-position concentration and small holding count surfaced as user-facing Chinese labels.
- No developer/raw details were open by default.

Empty/data-limited messaging:

- Cash ledger and corporate actions were empty and did not produce misleading populated claims.
- Broker connections were empty and did not block populated holdings rendering.
- The route remained honest where fields were absent; no fake data was displayed for unsupported live-sync state.

## 7. Issues And Follow-Up Tasks

| ID | Severity | Affected area | Evidence | Likely owner/files | Recommended fix task | Parallel? | Recommended tests/verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PPH-QA-01 | P3 | Shell controls visible on Portfolio desktop | Playwright small-button scan at `1440x1000` found `EN` and `退出` controls at 25 px high. No Portfolio body controls were flagged; mobile scan was clean. | Shared shell/navigation controls, likely `apps/dsa-web/src/components/layout/SidebarNav.tsx` or related shell controls. | If strict touch-target policy applies to desktop shell controls, run a shell-only touch-target polish using existing Button/Input/Select patterns and design constitution. | Yes, shell-only; avoid Portfolio business logic. | Playwright/Safari on shell routes at desktop and `390x844`, `npm run check:design`, `npm run lint`, `npm run build`. |
| PPH-QA-02 | P3 | Portfolio QA repeatability | The contract-faithful mock was assembled in the one-off Playwright run rather than a reusable committed fixture. | Future QA artifact only; if automated, `apps/dsa-web` Playwright/Vitest fixture area chosen in a separate task. | Add a reusable populated Portfolio QA fixture or targeted route smoke test without changing production behavior. | Yes, test/QA-only; do not combine with product fixes. | Re-run `/zh/portfolio` desktop/mobile with the committed fixture and mutation guard. |
| PPH-QA-03 | P3 | Live-data confidence | This pass did not use real local authenticated holdings because safe read-only live account availability was not established. | Operator/local data setup, not product code unless live data reproduces a defect. | Re-run with a read-only live account when available, preserving no-mutation guard. | Yes, QA-only. | Same route matrix plus network log proving no write endpoints. |

## 8. What Passed Cleanly

- Portfolio route rendered populated holdings correctly under the contract-faithful mock.
- Desktop and mobile layouts had no horizontal overflow.
- Risk overview and drilldown sections rendered.
- Currency, market, symbol, sector, account, concentration, and P&L analytics were coherent.
- Empty cash/corporate/broker states stayed honest.
- Chinese labels remained intact for user-visible Portfolio UI.
- No raw/debug/provider/schema/token/API-key text was visible in the default UI.
- No visible native-looking controls were detected.
- Developer/raw details were not open by default.
- No Portfolio mutation requests were sent by the QA script.
- Design guard, lint, build, backend compile, targeted Portfolio tests, Portfolio API tests, and full `ci_gate` all passed.

## 9. Non-Goals

- No product code changed.
- No tests changed.
- No CSS changed.
- No backend/API changed.
- No package files or config changed.
- No `docs/CHANGELOG.md` changed.
- No generated artifacts committed.
- No portfolio data mutated.
- No issues were fixed in this task.

## 10. Appendix

Preflight summary:

```text
pwd: /Users/yehengli/daily_stock_analysis
branch: main
initial status: M apps/dsa-web/src/pages/WatchlistPage.tsx
task_preflight: upstream origin/main ahead 0 / behind 0; dirty files may belong to parallel Codex sessions
```

Port scan summary:

```text
8000: existing Python listener, not touched
8001: free, unused
5173: existing Vite/Codex frontend listener, not touched
4173: free, unused
5174: free, unused
5175: free, unused
5176: free, used for isolated Vite preview, then stopped and confirmed free
```

Playwright mocked API hit summary:

```text
/api/v1/auth/status: 2
/api/v1/portfolio/accounts: 2
/api/v1/portfolio/imports/brokers: 2
/api/v1/portfolio/snapshot: 2
/api/v1/portfolio/trades: 2
/api/v1/portfolio/broker-connections: 2
/api/v1/portfolio/risk: 2
mutationRequests: []
unhandled: []
```

Playwright text checks:

```text
account: true
positions: true
pnl: true
fx: true
exposure: true
marketExposure: true
concentration: true
riskHints: true
contributors: true
```

Static command output summary:

```text
npm run check:design
Files scanned: 214
Design guard passed. No blocking violations or warnings found.

npm run lint
eslint . exited 0

npm run build
3158 modules transformed
DeterministicBacktestChartWorkspace-CitVz9mO.js 532.42 kB / gzip 178.83 kB
Some chunks are larger than 500 kB after minification.
built in 9.30s

python3 -m compileall -q src api
exited 0

npm run test -- src/pages/__tests__/PortfolioPage.test.tsx --run
1 passed, 42 tests passed, duration 7.53s

python3 -m pytest tests/test_portfolio_api.py -q
29 passed in 14.49s

./scripts/ci_gate.sh
1993 passed, 3 skipped, 1 warning, 203 subtests passed in 161.07s
backend-gate completed successfully
```

Markdown lint:

- Checked after report creation. No runnable markdown lint script was found in available package/scripts references.

Parallel safety:

- Existing dirty `apps/dsa-web/src/pages/WatchlistPage.tsx` was not touched, staged, or committed.
- Existing dirty `apps/dsa-web/src/components/market-overview/marketOverviewPrimitives.tsx` was not touched, staged, or committed.
- No report preview fixture/helper files were changed by this task.
