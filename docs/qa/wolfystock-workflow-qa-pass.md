# WolfyStock Workflow QA Pass

Date: 2026-05-05 Asia/Shanghai  
Repository: `/Users/yehengli/daily_stock_analysis`  
Branch: `main`  
Mode: QA/audit/report only; no product code, tests, CSS, backend/API, package, config, runtime, or changelog changes

## 1. Executive Summary

Overall assessment: **pass with follow-up items**. The audited routes loaded coherently under mocked authenticated/admin data at desktop `1440x1000` and narrow `390x844`; no audited route showed horizontal overflow, blank lazy-load state, page/console errors, unstyled native controls, visible raw secret tokens, or default-open developer diagnostics after mock correction.

Major findings:

- **P2:** Several narrow/mobile dense controls measure below a comfortable touch target, especially route tabs, disclosure headers, chart toggles, market refresh icon buttons, and watchlist row selection.
- **P3:** The preview report route still contains English fixture/report copy in the Chinese route.
- **P3:** Portfolio route rendered the risk area and FX transparency, but the mocked account/position payload was data-limited; treat portfolio as mock/data-limited rather than a full data pass.

No-code-change confirmation: this pass only creates `docs/qa/wolfystock-workflow-qa-pass.md`.

Recommended next actions:

1. Run a focused mobile touch-target polish pass using existing Button/Input/Select/common styling patterns and route ownership constraints.
2. Re-run Portfolio with a real local account or a contract-faithful mock fixture before calling portfolio data rendering fully passed.
3. Normalize preview-report Chinese fixture copy where the text is UI chrome rather than market/provider/domain content.

## 2. Methodology

Read-first inputs:

- `docs/frontend/visual-system.md`
- `docs/operations/parallel-codex-playbook.md`
- `docs/checks/design-guard.md`
- `docs/checks/ci-gate-clarity.md`
- `docs/archive/audits/frontend/wolfystock-global-codebase-audit.md`
- `docs/archive/audits/frontend/wolfystock-phase0-bundle-design-inventory.md`
- `docs/archive/audits/frontend/wolfystock-bundle-composition-report.md`
- `docs/archive/frontend/css-ownership-inventory-2026-05-05.md`
- `docs/archive/frontend/css-selector-usage-verification-2026-05-05.md`

Commands run:

```bash
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -64
./scripts/task_preflight.sh || true

cd apps/dsa-web
npm run check:design
npm run lint
npm run build

cd /Users/yehengli/daily_stock_analysis
python3 -m compileall -q src api
./scripts/ci_gate.sh
rg -n "markdownlint|mdlint|lint:md|lint.*markdown|remark.*lint" package.json apps/dsa-web/package.json .github scripts docs 2>/dev/null | head -80
```

Playwright/browser method:

- Temporary Playwright script: `/tmp/wolfystock_workflow_qa.mjs` (removed after run)
- Result JSON: `/tmp/wolfystock_workflow_qa_results.json` (removed after report extraction)
- Runner: headless Chromium from the existing `apps/dsa-web` Playwright install
- App server: `npm run preview -- --host 127.0.0.1 --port 5176`
- Base URL: `http://127.0.0.1:5176`
- Viewports: desktop `1440x1000`, mobile/narrow `390x844`
- Auth/data strategy: mocked authenticated admin user and mocked API data for protected/data-heavy routes
- Limitations: no real local auth session was used; no live backend data was mutated; Portfolio is data-limited because the mock verified route/risk rendering but did not fully hydrate all account/position summary fields

Ports:

| Port | Status | Use in this pass |
| --- | --- | --- |
| `8000` | Existing Python backend listener | Observed only; not called by the Playwright mock pass |
| `8001` | Free | Not used |
| `5173` | Existing Vite frontend with Codex connections | Not touched |
| `4173` | Free | Not used |
| `5174` | Free | Not used |
| `5175` | Free | Not used |
| `5176` | Started isolated Vite preview | Used for Playwright QA; stopped after QA and confirmed free |

## 3. Static Quality Baseline

| Check | Result | Key output | Notes |
| --- | --- | --- | --- |
| `npm run check:design` | PASS | 214 files scanned; 0 blocking; 0 warnings | Confirms design guard clean state after `f1bac8c`. |
| `npm run lint` | PASS | `eslint .` exited 0 | No lint output. |
| `npm run build` | PASS with warning | 3158 modules transformed; built in 8.39s | Vite large chunk warning remains. |
| Largest chunk warning | WARN | `DeterministicBacktestChartWorkspace-xmQGa5CC.js` 532.42 kB / 178.83 kB gzip | After recent lazy-loading, warning source moved from shared index to deterministic chart workspace. |
| Backend compile | PASS | `python3 -m compileall -q src api` exited 0 | No output. |
| `./scripts/ci_gate.sh` | PASS | 1993 passed, 3 skipped, 1 warning, 203 subtests passed in 161.95s | Local warnings: `flake8` and `akshare` missing; backend gate completed successfully. |
| Markdown lint | Not available | Search found docs mentions only, no runnable script | Root has no `package.json`; web package has no markdown lint script. |

## 4. Route Verification Matrix

| Route | Mode | Desktop status | Mobile status | Overflow | Console/page errors | Raw/debug leakage | Native controls | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/zh` | mock verified | PASS | PASS | PASS | PASS | PASS | PASS | Home shows confidence as `-`, not fake `0%`; decision source is a visible action, not raw detail dump. |
| `/zh/scanner` | mock verified | PASS | PASS | PASS | PASS | PASS | PASS | Command bar, result history, candidate area, diagnostics, and empty-history copy rendered. |
| `/zh/watchlist` | mock verified | PASS | PASS | PASS | PASS | PASS | PASS | Intelligence command bar, filters, selected/filtered state, and row actions rendered. |
| `/zh/backtest` | mock verified | PASS | PASS | PASS | PASS | PASS | PASS | Normal/pro/deterministic controls rendered. |
| `/zh/backtest/results/1` | mock verified | PASS | PASS | PASS | PASS | PASS | PASS | Lazy result route and chart workspace loaded without blank/black state after contract-faithful mock data. |
| `/zh/portfolio` | mock/data-limited | PASS | PASS | PASS | PASS | PASS | PASS | Risk/FX sections rendered; account/position hydration was limited by mock shape. |
| `/zh/market-overview` | mock verified | PASS | PASS | PASS | PASS | PASS | PASS | Provider/freshness/fallback/stale labels rendered honestly in Chinese. |
| `/zh/settings` | mock verified | PASS | PASS | PASS | PASS | PASS | PASS | Personal settings rendered; raw secret values not visible. |
| `/zh/settings/system` | mock verified | PASS | PASS | PASS | PASS | PASS | PASS | Compact subsystem cards rendered; developer details stayed collapsed. |
| `/zh/admin/logs` | mock verified | PASS | PASS | PASS | PASS | PASS | PASS | Level/status labels rendered in Chinese; raw metadata stayed collapsed. |
| `/zh/admin/notifications` | mock verified | PASS | PASS | PASS | PASS | PASS | PASS | Rule cards, dry-run/test-send copy, and masked target summaries rendered. |
| `/zh/chat` | mock verified | PASS | PASS | PASS | PASS | PASS | PASS | Chat route rendered without default native controls or raw debug leakage. |
| `/zh/__preview/report` | mock verified | PASS | PASS | PASS | PASS | PASS | PASS | Preview route exists and renders; some fixture/report copy remains English on Chinese route. |

## 5. Workflow Findings

### Home/report

- PASS: the Home summary did not show fake `0%` confidence; missing confidence rendered as `-`.
- PASS: report/decision actions rendered without raw payload leakage.
- Follow-up: mobile detail trigger heights are visually dense.

### Scanner

- PASS: command bar, market/profile controls, result history, candidate area, diagnostics, and failure/empty history state rendered.
- PASS: no horizontal overflow at `390x844`.
- Follow-up: scanner segmented and batch controls are 23-27 px high on narrow viewport.

### Watchlist

- PASS: command bar, filters, selected row state, scanner/backtest intelligence, empty/failure-safe labels, and row actions rendered.
- Follow-up: the row selection control measured `14x14`; batch action buttons measured 28 px high.

### Backtest/results

- PASS: Backtest page rendered normal/pro/deterministic control surfaces.
- PASS: deterministic result route lazy-loaded the route shell and chart workspace without blank screen once mocked data matched the route contract.
- Follow-up: result route disclosure headers/tabs are compact at mobile heights around 18-28 px.

### Portfolio

- PASS: route shell, FX transparency, risk overview/drilldown area, and empty/data-limited states rendered without overflow or errors.
- Limitation: mocked portfolio account/position summary did not fully hydrate, so this is not a full data-rendering pass for populated holdings.

### Market Overview

- PASS: provider/freshness/stale/fallback labels rendered in Chinese and marked a stale/fallback panel honestly.
- Follow-up: refresh icon buttons measured `25x25` on mobile.

### Settings/system

- PASS: personal settings and system control plane rendered without raw secret values.
- PASS: compact subsystem cards rendered, including optional dependency states; developer details remained collapsed by default.

### Admin logs/notifications

- PASS: admin logs rendered Chinese level/status labels and kept raw metadata collapsed.
- PASS: notification rule cards rendered masked destination copy and dry-run/test-send controls.

### Chat

- PASS: chat shell, engine/provider health, lens controls, and evidence context rendered without console/page errors.
- PASS: advanced lenses stayed collapsed by default.

## 6. Issues And Follow-Up Tasks

| ID | Severity | Affected route | Evidence | Likely owner/files | Recommended fix task | Parallel? | Recommended verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WQA-01 | P2 | `/zh/scanner`, `/zh/watchlist`, `/zh/backtest`, `/zh/backtest/results/1`, `/zh/market-overview`, `/zh/settings`, `/zh/__preview/report` | Playwright mobile detected visible controls below 32 px high: scanner 23-27 px, watchlist 14-28 px, market refresh icons 25x25, preview chart toggles 22 px, result disclosures 18 px. | `UserScannerPage.tsx`, `WatchlistPage.tsx`, `BacktestPage.tsx`, `DeterministicBacktestResultPage.tsx`, `MarketOverviewPage.tsx`, `PreviewReportPage.tsx`, shared Button/Input/Select primitives where already used. | Mobile touch-target polish using common Button/Input/Select styling patterns without changing route skeletons. | Partly; split by route surface. | Playwright/Safari at `390x844`, `npm run check:design`, `npm run lint`, `npm run build`. |
| WQA-02 | P3 | `/zh/__preview/report` | Chinese preview route body contains fixture/report chrome such as `Intraday snapshot`, `regular session`, and English timeframe labels around report preview. | `PreviewReportPage.tsx`, report preview fixture/data, report localization utilities. | Localize preview fixture/UI chrome while preserving tickers, provider names, metrics, and market-domain terms. | Yes, docs/fixture/UI-copy scoped. | Preview route desktop/mobile plus report rendering tests. |
| WQA-03 | P3 | `/zh/portfolio` | Mocked route rendered FX/risk shell but showed active accounts/holdings as empty while mock snapshot carried positions, so populated portfolio data is not fully verified. | Future QA fixture only first; if product issue reproduces with real API, `PortfolioPage.tsx` and `portfolioApi` normalization. | Re-run Portfolio QA with real local auth/data or a fixture copied from `PortfolioPage.test.tsx` contracts. | Yes as report/test-fixture work; no product fix until reproduced. | Portfolio desktop/mobile with populated holdings, FX transparency, and risk drilldown assertions. |

## 7. What Passed Cleanly

- Design guard is fully clean: 0 blocking and 0 warnings.
- Lint, build, backend compile, and full `ci_gate` passed.
- All required routes rendered at both viewports under mocked auth/admin data.
- No audited route showed horizontal overflow.
- No audited route produced console or page errors after mock contract correction.
- No audited route showed blank/black lazy-load state.
- No audited route exposed raw API key, token, `webhook_url`, raw metadata, system prompt, or schema/debug strings in the default visible UI.
- Developer/raw diagnostic details stayed collapsed by default where present.
- Core route labels were Chinese by default, with expected exceptions for tickers, provider names, metrics, and currencies.

## 8. Non-Goals

- No product code changed.
- No tests changed.
- No CSS changed.
- No backend/API code changed.
- No package files or config changed.
- No `docs/CHANGELOG.md` change.
- No generated screenshots, videos, traces, Playwright reports, build artifacts, logs, DuckDB files, or runtime files committed.
- No issues were fixed in this task.

## 9. Appendix

Preflight:

- `pwd`: `/Users/yehengli/daily_stock_analysis`
- branch: `main`
- `git status --short`: clean before the report file was created
- upstream: `origin/main`, ahead 0 / behind 0
- recent commits included `f1bac8c fix(ui): finish native control polish` and `34170d1 refactor(admin): reuse display status labels`

Playwright route details:

- Routes checked: `/zh`, `/zh/scanner`, `/zh/watchlist`, `/zh/backtest`, `/zh/backtest/results/1`, `/zh/portfolio`, `/zh/market-overview`, `/zh/settings`, `/zh/settings/system`, `/zh/admin/logs`, `/zh/admin/notifications`, `/zh/chat`, `/zh/__preview/report`
- Every route: desktop PASS and mobile PASS under mocked data
- Overflow delta: `0` for every route/viewport
- Console errors: `0` for every route/viewport
- Page errors: `0` for every route/viewport after mock correction
- Unhandled mocked API routes: `0`
- Raw/debug leakage matches: `0`
- Unstyled/native-control risk matches: `0`
- Open developer-detail matches: `0`

Static command output summary:

```text
npm run check:design
Files scanned: 214
Design guard passed. No blocking violations or warnings found.

npm run lint
eslint . exited 0

npm run build
3158 modules transformed
DeterministicBacktestChartWorkspace-xmQGa5CC.js 532.42 kB / gzip 178.83 kB
Some chunks are larger than 500 kB after minification.
built in 8.39s

python3 -m compileall -q src api
exited 0

./scripts/ci_gate.sh
1993 passed, 3 skipped, 1 warning, 203 subtests passed in 161.95s
backend-gate completed successfully
```

Existing audit/pattern references used for recommendations:

- `displayStatus` is the current shared display-status utility; status label follow-ups should reuse it instead of adding page-local status vocabularies.
- Button/Input/Select polish should reuse common styling patterns and the design constitution rather than adding parallel control styles.
- Shell and route ownership constraints from the design constitution and parallel Codex playbook should guide any route-specific touch-target pass.
- CSS selector ownership reports should be referenced before changing global shell, route modifier, scrollbar, or product-card CSS.
