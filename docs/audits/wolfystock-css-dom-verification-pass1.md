# WolfyStock CSS DOM Verification Pass 1

Date: 2026-05-05 Asia/Shanghai  
Repository: `/Users/yehengli/daily_stock_analysis`  
Branch: `main`  
Mode: read-only rendered DOM evidence pass; no CSS, product code, tests, backend/API, package, config, runtime, or changelog changes

## 1. Executive Summary

Checked **13 required routes** at **2 required viewports** for **26 rendered DOM rows**:

- Desktop: `1440x1000`
- Mobile/narrow: `390x844`
- Candidate selectors checked: `glass-card`, `terminal-card`, `dashboard-card`, `gradient-border-card`, `workspace-page--chat`, `stealth-scrollbar`, `backtest-entry-shell`, `product-command-card`
- Do-not-delete observation selectors checked where route rendering allowed.

Candidate selector summary:

| Selector | Rendered DOM result | Static source result | Current recommendation |
| --- | --- | --- | --- |
| `glass-card` | 0 hits in all 26 rows | CSS only | Strong future deletion-trial candidate; still requires a separate deletion task. |
| `terminal-card` | 0 hits in all 26 rows | CSS only | Strong future deletion-trial candidate; still requires a separate deletion task. |
| `dashboard-card` | 0 hits in all 26 rows | CSS only | Strong future deletion-trial candidate; still requires a separate deletion task. |
| `gradient-border-card` | 0 hits in all 26 rows | CSS only | Strong future deletion-trial candidate; still requires a separate deletion task. |
| `workspace-page--chat` | 0 hits in all 26 rows | test-only negative reference | Possible future deletion-trial candidate, but Chat route was data-limited by mock error. |
| `stealth-scrollbar` | 0 hits in all 26 rows | test-only negative reference | Possible future deletion-trial candidate; route scrollbar replacement proof still needed. |
| `backtest-entry-shell` | 0 hits in all 26 rows | `data-testid` only, not a class | Possible future deletion-trial candidate, but Backtest route was data-limited by mock error. |
| `product-command-card` | 0 hits in all 26 rows | CSS only, high primitive risk | Inconclusive/high-risk; document owner before any deletion trial. |

Strongest future deletion candidates are the four classic card primitives: `glass-card`, `terminal-card`, `dashboard-card`, and `gradient-border-card`. They had zero rendered DOM hits and no non-CSS source hits. `stealth-scrollbar` is also promising, but future proof must focus on active scroll containers and visible scrollbar behavior.

Inconclusive areas: Scanner, Backtest, Backtest Results, Market Overview, and Chat rendered under mocked auth/data but hit page-level mock-shape errors. Their candidate selector counts were still zero, but these rows are **auth/data limited** rather than full route proof. Admin routes rendered after admin mock correction. No CSS was deleted, and no selector is approved for deletion now. Every candidate still requires a future tightly scoped deletion trial before removal.

## 2. Methodology

Commands run:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -88
./scripts/task_preflight.sh || true
```

Read-first inputs:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/checks/css-visual-regression-checklist.md`
- `docs/audits/wolfystock-css-selector-usage-verification.md`
- `docs/audits/wolfystock-css-ownership-inventory.md`
- `docs/audits/wolfystock-frontend-design-conformance-audit.md`
- `docs/qa/wolfystock-workflow-qa-pass.md`
- `docs/operations/parallel-codex-playbook.md`
- `docs/checks/design-guard.md`

Static selector context commands:

```bash
cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
rg -n "\.glass-card|\.terminal-card|\.dashboard-card|\.gradient-border-card|\.workspace-page--chat|\.stealth-scrollbar|\.backtest-entry-shell|\.product-command-card" src/index.css
rg -n "glass-card|terminal-card|dashboard-card|gradient-border-card|workspace-page--chat|stealth-scrollbar|backtest-entry-shell|product-command-card" src --glob '!index.css'
rg -n "theme-shell--scanner|shell-content-frame--scanner|shell-main-column--scanner|custom-scrollbar|theme-market-badge|backtest-void-workspace|backtest-result-bento|gemini-bento-page|settings-surface|home-panel-card|home-subpanel|chart-card|comparison-card" src --glob '!index.css' | head -240
```

Static baseline commands:

```bash
cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
npm run check:design
npm run lint
npm run build

cd /Users/yehengli/daily_stock_analysis
python3 -m compileall -q src api
```

Playwright method:

- Temporary script: `/tmp/wolfystock_css_dom_verification_pass1.mjs`
- Temporary JSON result: `/tmp/wolfystock_css_dom_verification_pass1_results.json`
- Browser: headless Chromium from the local `apps/dsa-web` Playwright install
- Frontend URL: `http://127.0.0.1:5176`
- Server: isolated `npm run preview -- --host 127.0.0.1 --port 5176`
- Auth/data: route interception for `**/api/v1/**`, with authenticated admin status and contract-shaped mocks where practical.
- DOM query: exact class selector, `[class~='...']`, and class-name substring counts.
- Overflow query: `document.documentElement.scrollWidth - document.documentElement.clientWidth`
- Page and console errors collected per route/viewport.
- No screenshots, videos, traces, or Playwright reports were required or committed.

Ports:

| Port | Status/use |
| --- | --- |
| `8000` | Existing Python backend listener observed; not restarted or stopped. |
| `8001` | Free; not used. |
| `5173` | Existing Vite/Codex frontend listener observed; not touched. |
| `4173` | Free; not used. |
| `5174` | Free; not used. |
| `5175` | Free; not used. |
| `5176` | Free before task; started isolated preview for Playwright; stopped after verification. |

Limitations:

- This pass used mocks, not a live authenticated browser session.
- Home and Market Overview produced EventSource MIME console errors because stream endpoints were mocked as JSON.
- Scanner, Backtest, Backtest Results, Market Overview, and Chat hit page-level mock-shape errors. Their DOM counts are recorded, but full route content proof remains inconclusive for those pages.
- `product-command-card` remains high-risk because static CSS has many override locations even though DOM count was zero.
- Full `./scripts/ci_gate.sh` was not run because this is a docs-only audit and the requested validation matrix did not require full CI.

## 3. Static Baseline

| Check | Result | Key output | Notes |
| --- | --- | --- | --- |
| `pwd` | PASS | `/Users/yehengli/daily_stock_analysis` | Required path. |
| Branch | PASS | `main` | Required branch. |
| Initial preflight | PASS | `origin/main`, ahead 0 / behind 0; dirty files 0 | No worktree conflict at start. |
| `npm run check:design` | PASS | 216 files scanned; 0 blocking; 0 warnings | Design guard clean. |
| `npm run lint` | PASS | `eslint .` exited 0 | No lint output. |
| `npm run build` | PASS with warning | 3160 modules transformed; built in 11.18s | Vite warned on `DeterministicBacktestChartWorkspace-p3HXdMxT.js` at 532.42 kB / gzip 178.83 kB. |
| Backend compile | PASS | `python3 -m compileall -q src api` exited 0 | No output. |
| Markdown lint | Not available | Search found docs/package references to `remark`, but no markdown lint script | No markdown lint command was run. |
| `./scripts/ci_gate.sh` | Not run | Docs-only audit | No full CI required for this report-only task. |

## 4. Static Selector Context

| Selector | CSS location | Source search evidence | Prior classification | Current verification target |
| --- | --- | --- | --- | --- |
| `glass-card` | `src/index.css:2851`, pseudo-elements at `2865`, `2888`, theme overrides at `4130`, `4138`, `4145`, `4146` | No hits outside CSS | CSS-only / likely dead | Rendered DOM absence across required routes. |
| `terminal-card` | `src/index.css:2767`, `2787`, hover at `2810`, theme overrides at `4126`, `4136`, `4144` | No hits outside CSS | CSS-only / likely dead | Rendered DOM absence across required routes. |
| `dashboard-card` | `src/index.css:2912`, `2926`, `2949`, theme overrides at `4129`, `4137` | No hits outside CSS | CSS-only / likely dead | Rendered DOM absence across dashboard-like routes. |
| `gradient-border-card` | `src/index.css:2824`, inner at `2837`, theme overrides at `4127`, `4128`, `4147`, `4152`, `4157` | No hits outside CSS | CSS-only / likely dead | Rendered wrapper/inner absence. |
| `workspace-page--chat` | `src/index.css:939`, chat overrides at `10998`, `11002`, `12574`, `12580`, `12585`, `12603`, `12609`, `12690`, `12701` | `ChatPage.test.tsx:653` asserts active bento page does not have this class | Test-only negative / likely legacy | Full Chat ancestor DOM absence. |
| `stealth-scrollbar` | `src/index.css:6105`, webkit rules at `6111`, `6119`, `6127` | Test-only negative references in `MarketOverviewPage.test.tsx:1016`, `1334` | Test-only negative / likely legacy | Rendered scroll-container absence. |
| `backtest-entry-shell` | `src/index.css:15598-15846` | `DeterministicBacktestFlow.tsx:1341` uses `data-testid="backtest-entry-shell"` but not the CSS class | CSS-only / weak class evidence | Distinguish class absence from `data-testid`. |
| `product-command-card` | `src/index.css:4235`, `6193`, `6412`, `6681`, `8350`, `8363`, `8382`, `8394`, `8480`, `8492`, `9265`, `9292`, `16219` | No hits outside CSS | CSS-only with design-primitive risk | Rendered DOM absence plus owner-risk note. |
| `theme-shell--scanner` | `src/index.css` scanner shell blocks | `Shell.tsx:208`, `Shell.test.tsx:354` | Do-not-delete | Observe only; not a deletion target. |
| `shell-content-frame--scanner` | `src/index.css` scanner shell blocks | `Shell.tsx:246`, `Shell.test.tsx:356` | Do-not-delete | Observe only; not a deletion target. |
| `shell-main-column--scanner` | `src/index.css` scanner shell blocks | `Shell.tsx:248`, `Shell.test.tsx:359` | Do-not-delete | Observe only; not a deletion target. |
| `custom-scrollbar` | `src/index.css:6105-6128` | `ScrollArea.tsx:30` | Do-not-delete | Observe only; shared utility. |
| `theme-market-badge` | market badge rules and overrides | `SuggestionsList.tsx:80-96` | Do-not-delete | Observe only; dynamic market badge primitive. |
| `backtest-void-workspace` | backtest result/chart workspace CSS | `DeterministicBacktestResultView.tsx`, `DeterministicBacktestChartWorkspace.tsx` | Do-not-delete | Observe only; active result primitive. |
| `backtest-result-bento` | deterministic result bento CSS | `DeterministicBacktestResultPage.tsx:1047-1104` | Do-not-delete | Observe only; active result primitive. |
| `gemini-bento-page` | chat/home bento CSS | `ChatPage.tsx:1649`, `PageChrome.tsx:113` | Do-not-delete | Observe only; active bento skin. |
| `settings-surface` | settings surface CSS | multiple settings components | Do-not-delete | Observe only; active settings primitive. |
| `home-panel-card` | report/home card CSS | report components | Do-not-delete | Observe only; active report primitive. |
| `home-subpanel` | report/home subpanel CSS | `ReportNews.tsx:114` | Do-not-delete | Observe only; active report primitive. |
| `chart-card` | chart CSS | backtest compare/audit components | Do-not-delete | Observe only; active chart primitive. |
| `comparison-card` | comparison CSS | backtest compare/audit components | Do-not-delete | Observe only; active comparison primitive. |

## 5. Rendered DOM Matrix

Candidate selector hit counts were zero for every route/viewport:

`glass-card=0`, `terminal-card=0`, `dashboard-card=0`, `gradient-border-card=0`, `workspace-page--chat=0`, `stealth-scrollbar=0`, `backtest-entry-shell=0`, `product-command-card=0`.

| Route | Viewport | Mode | Candidate selector hit counts | Do-not-delete selector observations | Overflow | Console/page errors | Notes |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| `/zh` | `1440x1000` | mock | all 0 | none observed | 0 | 1 console; 0 page | Home content rendered; EventSource mock MIME warning. |
| `/zh/scanner` | `1440x1000` | mock / data-limited | all 0 | none observed | 0 | 0 console; 1 page | Mock shape error: `Cannot read properties of undefined (reading '0')`; scanner shell proof inconclusive. |
| `/zh/watchlist` | `1440x1000` | mock | all 0 | none observed | 0 | 0 console; 0 page | Watchlist shell/content rendered. |
| `/zh/backtest` | `1440x1000` | mock / data-limited | all 0 | none observed | 0 | 0 console; 1 page | Mock shape error: `Cannot read properties of undefined (reading 'find')`; entry shell proof inconclusive. |
| `/zh/backtest/results/1` | `1440x1000` | mock / data-limited | all 0 | none observed | 0 | 0 console; 1 page | Mock shape error: `"undefined" is not valid JSON`; result bento observation inconclusive. |
| `/zh/portfolio` | `1440x1000` | mock / data-limited | all 0 | none observed | 0 | 0 console; 0 page | Route rendered, but mock showed mostly empty/data-limited portfolio totals. |
| `/zh/market-overview` | `1440x1000` | mock / data-limited | all 0 | none observed | 0 | 1 console; 1 page | Mock shape error plus EventSource MIME warning; market badge DOM proof inconclusive. |
| `/zh/settings` | `1440x1000` | mock | all 0 | `settings-surface=5` | 0 | 0 console; 0 page | Personal settings rendered; active do-not-delete selector observed. |
| `/zh/settings/system` | `1440x1000` | mock | all 0 | none observed | 0 | 0 console; 0 page | Admin system page rendered under admin mock. |
| `/zh/admin/logs` | `1440x1000` | mock | all 0 | none observed | 0 | 0 console; 0 page | Admin logs shell rendered under admin mock. |
| `/zh/admin/notifications` | `1440x1000` | mock | all 0 | none observed | 0 | 0 console; 0 page | Admin notifications shell rendered under admin mock. |
| `/zh/chat` | `1440x1000` | mock / data-limited | all 0 | none observed | 0 | 0 console; 1 page | Mock shape error: `Cannot read properties of undefined (reading 'forEach')`; `workspace-page--chat` absence counted, but full chat proof inconclusive. |
| `/zh/__preview/report` | `1440x1000` | mock | all 0 | none observed | 0 | 0 console; 0 page | Preview report rendered. |
| `/zh` | `390x844` | mock | all 0 | none observed | 0 | 1 console; 0 page | Home content rendered; EventSource mock MIME warning. |
| `/zh/scanner` | `390x844` | mock / data-limited | all 0 | none observed | 0 | 0 console; 1 page | Same scanner mock shape error; scanner shell proof inconclusive. |
| `/zh/watchlist` | `390x844` | mock | all 0 | none observed | 0 | 0 console; 0 page | Watchlist shell/content rendered. |
| `/zh/backtest` | `390x844` | mock / data-limited | all 0 | none observed | 0 | 0 console; 1 page | Same Backtest mock shape error. |
| `/zh/backtest/results/1` | `390x844` | mock / data-limited | all 0 | none observed | 0 | 0 console; 1 page | Same result JSON mock shape error. |
| `/zh/portfolio` | `390x844` | mock / data-limited | all 0 | none observed | 0 | 0 console; 0 page | Route rendered, but portfolio remains data-limited. |
| `/zh/market-overview` | `390x844` | mock / data-limited | all 0 | none observed | 0 | 1 console; 1 page | Same market mock shape error and EventSource MIME warning. |
| `/zh/settings` | `390x844` | mock | all 0 | `settings-surface=5` | 0 | 0 console; 0 page | Personal settings rendered; active do-not-delete selector observed. |
| `/zh/settings/system` | `390x844` | mock | all 0 | none observed | 0 | 0 console; 0 page | Admin system page rendered; visible API request failure copy came from limited config mock. |
| `/zh/admin/logs` | `390x844` | mock | all 0 | none observed | 0 | 0 console; 0 page | Admin logs shell rendered. |
| `/zh/admin/notifications` | `390x844` | mock | all 0 | none observed | 0 | 0 console; 0 page | Admin notifications shell rendered. |
| `/zh/chat` | `390x844` | mock / data-limited | all 0 | none observed | 0 | 0 console; 1 page | Same Chat mock shape error. |
| `/zh/__preview/report` | `390x844` | mock | all 0 | none observed | 0 | 0 console; 0 page | Preview report rendered. |

## 6. Candidate Classification

### `glass-card`

- DOM evidence summary: 0 hits in all 26 route/viewport rows.
- Static source evidence summary: CSS definitions and theme overrides only; no non-CSS source hits.
- Route limitations: data-heavy route mock errors do not appear likely to hide `glass-card`, but full content proof is incomplete for Scanner, Backtest, Market Overview, and Chat.
- Classification: strong deletion trial candidate; DOM absent across required routes; requires future deletion trial.
- Required future deletion-trial verification: remove only this selector family, rerun the required route matrix, inspect ghost-glass card hierarchy, and rollback immediately on material/card regressions.

### `terminal-card`

- DOM evidence summary: 0 hits in all 26 route/viewport rows.
- Static source evidence summary: CSS definitions and theme overrides only; no non-CSS source hits.
- Route limitations: same data-heavy mock limits as above.
- Classification: strong deletion trial candidate; DOM absent across required routes; requires future deletion trial.
- Required future deletion-trial verification: verify Home/report/preview card hierarchy remains unchanged because older report utilities share similar terminal-card material language.

### `dashboard-card`

- DOM evidence summary: 0 hits in all 26 route/viewport rows.
- Static source evidence summary: CSS definitions and theme overrides only; no non-CSS source hits.
- Route limitations: full dashboard-like route content is incomplete where mock errors occurred.
- Classification: strong deletion trial candidate; DOM absent across required routes; requires future deletion trial.
- Required future deletion-trial verification: rerun Home, Portfolio, Market Overview, Admin, and preview report at both viewports with no card hierarchy drift.

### `gradient-border-card`

- DOM evidence summary: 0 hits in all 26 route/viewport rows.
- Static source evidence summary: CSS wrapper/inner definitions and theme overrides only; no non-CSS source hits.
- Route limitations: no rendered wrapper/inner pair observed; data-heavy page errors still limit proof on several surfaces.
- Classification: strong deletion trial candidate; DOM absent across required routes; requires future deletion trial.
- Required future deletion-trial verification: delete only the wrapper/inner family and verify no preview/report/product command glow or border effect regresses.

### `workspace-page--chat`

- DOM evidence summary: 0 hits in all 26 rows.
- Static source evidence summary: no production source hit; `ChatPage.test.tsx` asserts the active bento page does not have this class.
- Route limitations: `/zh/chat` hit a mock-shape page error at both viewports, so full ancestor/content proof is incomplete.
- Classification: possible deletion trial candidate, but currently inconclusive for full Chat route; requires future deletion trial.
- Required future deletion-trial verification: authenticated or corrected-mock Chat route must render full `gemini-bento-page` content and prove `workspace-page--chat` is absent from every ancestor.

### `stealth-scrollbar`

- DOM evidence summary: 0 hits in all 26 rows.
- Static source evidence summary: test-only negative references in Market Overview tests; no production source hit.
- Route limitations: routes with complex scroll regions were partly data-limited by mock errors.
- Classification: possible deletion trial candidate; DOM absent across checked rows; requires future deletion trial.
- Required future deletion-trial verification: inspect route rails and scroll containers for active `custom-scrollbar`, `no-scrollbar`, and visible scrollbar behavior before deleting this utility.

### `backtest-entry-shell`

- DOM evidence summary: 0 hits in all 26 rows.
- Static source evidence summary: current Backtest code uses `data-testid="backtest-entry-shell"` but does not apply the CSS class.
- Route limitations: `/zh/backtest` hit a mock-shape page error at both viewports, so setup/entry content proof is incomplete.
- Classification: possible deletion trial candidate, but inconclusive for full Backtest route; requires future deletion trial.
- Required future deletion-trial verification: Backtest entry/setup must render with corrected mock or live data; confirm zero class hits while preserving the `data-testid`.

### `product-command-card`

- DOM evidence summary: 0 hits in all 26 rows.
- Static source evidence summary: no non-CSS source hits, but many CSS override locations and backtest/product layers reference it.
- Route limitations: Backtest, Scanner, Market Overview, and Chat were data-limited by mock errors, and these are the most relevant product command surfaces.
- Classification: inconclusive; high-risk possible deletion candidate; requires owner documentation before any deletion trial.
- Required future deletion-trial verification: document owner intent first, then run a deletion trial only after populated Backtest/Scanner/preview command surfaces prove no DOM usage and no cascade dependency.

## 7. Do-Not-Delete Observations

Observed in rendered DOM:

- `settings-surface`: 5 hits on `/zh/settings` desktop and 5 hits on `/zh/settings` mobile. This confirms active Settings ownership and it is not a deletion candidate.

Not observed in this rendered pass, but still not deletion candidates because static source/dynamic-shell evidence remains active or route proof was data-limited:

- `theme-shell--scanner`, `shell-content-frame--scanner`, `shell-main-column--scanner`: source and tests confirm dynamic Scanner shell composition; Scanner route DOM was data-limited here, so a separate Scanner authenticated DOM pass is required before any owner migration.
- `custom-scrollbar`: `ScrollArea.tsx` production usage remains active; do not delete without shared component migration.
- `theme-market-badge`: dynamic market badge source usage remains active; Market Overview DOM was data-limited and stock autocomplete was not explicitly exercised.
- `backtest-void-workspace`, `backtest-result-bento`, `chart-card`, `comparison-card`: source usage remains active; Backtest result DOM was data-limited.
- `gemini-bento-page`: production source usage remains active in Chat and Home bento; Chat DOM was data-limited.
- `home-panel-card`, `home-subpanel`: report component source usage remains active even though the preview route did not expose these classes under this fixture.

## 8. Recommended Next Tasks

1. Safe Dead Selector Removal Trial for one selector family only, starting with `glass-card`, `dashboard-card`, or `gradient-border-card`.
2. Additional authenticated/corrected-mock Scanner DOM verification to prove scanner shell modifiers in real DOM.
3. Corrected Backtest and Backtest Results mock verification before trialing `backtest-entry-shell`.
4. Product-command-card owner documentation before any deletion attempt; treat it as high risk until ownership is explicit.
5. CSS deletion prompt requirements based on `docs/checks/css-visual-regression-checklist.md`: one family only, route-level desktop/mobile proof, no product-code edits, explicit rollback plan, `npm run check:design`, `npm run lint`, `npm run build`, Playwright route proof, and `git diff --check`.

## 9. Non-Goals

- No CSS changed.
- No product code changed.
- No tests changed.
- No backend/API changed.
- No package files changed.
- No config files changed.
- No scripts changed.
- No `docs/CHANGELOG.md` changed.
- No generated artifacts committed.
- No selector deletion approved directly by this report.

## 10. Appendix

Preflight output:

- `pwd`: `/Users/yehengli/daily_stock_analysis`
- branch: `main`
- `git status --short`: clean
- `git status --branch --short`: `## main...origin/main`
- preflight dirty files: 0
- recent commits included the requested CSS/design/native-control commits; HEAD at task start was `ff3868e refactor(admin): align notification surface primitives`.

Static command output summary:

```text
npm run check:design
Files scanned: 216
Design guard passed. No blocking violations or warnings found.

npm run lint
eslint . exited 0

npm run build
3160 modules transformed
DeterministicBacktestChartWorkspace-p3HXdMxT.js 532.42 kB / gzip 178.83 kB
Some chunks are larger than 500 kB after minification.
built in 11.18s

python3 -m compileall -q src api
exited 0 with no output
```

Rendered DOM aggregate counts:

| Selector | Total rendered hits across 26 rows |
| --- | ---: |
| `glass-card` | 0 |
| `terminal-card` | 0 |
| `dashboard-card` | 0 |
| `gradient-border-card` | 0 |
| `workspace-page--chat` | 0 |
| `stealth-scrollbar` | 0 |
| `backtest-entry-shell` | 0 |
| `product-command-card` | 0 |
| `settings-surface` | 10 |

Rows with page errors from mock limitations:

- `/zh/scanner` at both viewports: `Cannot read properties of undefined (reading '0')`
- `/zh/backtest` at both viewports: `Cannot read properties of undefined (reading 'find')`
- `/zh/backtest/results/1` at both viewports: `"undefined" is not valid JSON`
- `/zh/market-overview` at both viewports: `Cannot read properties of undefined (reading 'forEach')`
- `/zh/chat` at both viewports: `Cannot read properties of undefined (reading 'forEach')`

Rows with console warnings from mock limitations:

- `/zh` at both viewports: EventSource response mocked as JSON, not `text/event-stream`
- `/zh/market-overview` at both viewports: EventSource response mocked as JSON, not `text/event-stream`

Temporary files:

- `/tmp/wolfystock_css_dom_verification_pass1.mjs`
- `/tmp/wolfystock_css_dom_verification_pass1_results.json`

Both temporary files were used only for local evidence extraction and are not part of the commit.
