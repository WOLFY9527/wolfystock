# WolfyStock Scanner DOM Verification

Date: 2026-05-05 Asia/Shanghai  
Repository: `/Users/yehengli/daily_stock_analysis`  
Branch: `main`  
Mode: read-only scanner DOM verification report; no product code, tests, CSS, backend/API, package, config, runtime, or changelog changes

## 1. Executive Summary

Scanner DOM verification status: **PASS with corrected contract-faithful Playwright mocks**.

`/zh/scanner` rendered full scanner content at both required viewports:

- Desktop: `1440x1000`
- Mobile/narrow: `390x844`

The corrected mocked route rendered scanner shell, command/profile controls, candidate area, result history, diagnostics summary, and collapsed developer diagnostics without triggering a scanner run or mutating data.

Key selector findings:

| Selector | Desktop DOM count | Mobile DOM count | Conclusion |
| --- | ---: | ---: | --- |
| `theme-shell--scanner` | 1 | 1 | Active scanner route infrastructure; do not delete. |
| `shell-content-frame--scanner` | 1 | 1 | Active scanner route infrastructure; do not delete. |
| `shell-main-column--scanner` | 1 | 1 | Active scanner route infrastructure; do not delete. |
| `glass-card` | 0 | 0 | Absent on corrected scanner route; scanner no longer blocks a future separate deletion trial. |
| `terminal-card` | 0 | 0 | Absent on corrected scanner route; scanner no longer blocks a future separate deletion trial. |
| `dashboard-card` | 0 | 0 | Absent on corrected scanner route; scanner no longer blocks a future separate deletion trial. |
| `gradient-border-card` | 0 | 0 | Absent on corrected scanner route; scanner no longer blocks a future separate deletion trial. |
| `workspace-page--chat` | 0 | 0 | Absent on scanner; not scanner-owned. |
| `stealth-scrollbar` | 0 | 0 | Absent on corrected scanner route; scrollbar deletion still needs all-route scroll proof. |
| `backtest-entry-shell` | 0 | 0 | Absent on scanner; Backtest route proof remains separate. |
| `product-command-card` | 0 | 0 | Absent on corrected scanner route, but still high-risk until product command ownership is documented. |

What remains inconclusive:

- This pass did not use a live authenticated user session. It used corrected Playwright mocks based on scanner page/test contracts.
- Existing backend on `8000` was observed but not used.
- `apps/dsa-web/src/index.css` became dirty from a parallel CSS deletion task during this audit. This report did not touch it; rendered DOM evidence was collected against the current working tree and build, so CSS deletion conclusions must account for that parallel-state limitation.
- This report does **not** approve any selector deletion. No CSS was deleted, and no selector is approved for deletion directly.

## 2. Methodology

Preflight commands:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -92
./scripts/task_preflight.sh || true
```

Mandatory reading completed:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/checks/css-visual-regression-checklist.md`
- `docs/audits/wolfystock-css-dom-verification-pass1.md`
- `docs/audits/wolfystock-css-selector-usage-verification.md`
- `docs/audits/wolfystock-css-ownership-inventory.md`
- `docs/audits/wolfystock-frontend-design-conformance-audit.md`
- `docs/qa/wolfystock-workflow-qa-pass.md`
- `docs/design/wolfystock-canonical-ui-primitives.md`
- `docs/operations/parallel-codex-playbook.md`

Static investigation commands:

```bash
cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
rg -n "theme-shell--scanner|shell-content-frame--scanner|shell-main-column--scanner|scanner|Scanner|candidate|result history|结果历史|provider|fallback|market profile" src/components src/pages src/api src/types src/__tests__ | head -360
rg -n "theme-shell--scanner|shell-content-frame--scanner|shell-main-column--scanner|glass-card|terminal-card|dashboard-card|gradient-border-card|workspace-page--chat|stealth-scrollbar|backtest-entry-shell|product-command-card" src/index.css src --glob '!index.css' | head -260
```

Inspected scanner/shell files:

- `apps/dsa-web/src/pages/UserScannerPage.tsx`
- `apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx`
- `apps/dsa-web/src/pages/__tests__/ScannerSurfacePage.test.tsx`
- `apps/dsa-web/src/components/layout/Shell.tsx`
- `apps/dsa-web/src/components/layout/__tests__/Shell.test.tsx`

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

- Temporary script: `/tmp/wolfystock_scanner_dom_verification.mjs`
- Temporary JSON result: `/tmp/wolfystock_scanner_dom_verification_results.json`
- Browser: headless Chromium from the local `apps/dsa-web` Playwright install
- Route: `/zh/scanner`
- Frontend URL: `http://127.0.0.1:5176/zh/scanner`
- Server: isolated `npm run preview -- --host 127.0.0.1 --port 5176`
- Data/auth strategy: corrected contract-faithful Playwright mocks, authenticated non-admin user, scanner run/history/theme/watchlist endpoints mocked, no real scanner runs triggered
- DOM query: exact class counts for scanner shell selectors and candidate deletion selectors; substring scans for `scanner`, `shell-content-frame`, `shell-main-column`, `theme-shell`, `candidate`, `result`, `history`, `command`, `action`, and `custom-scrollbar`
- Overflow query: `document.documentElement.scrollWidth - document.documentElement.clientWidth`
- No screenshots, videos, traces, Playwright reports, generated runtime artifacts, or temp files were committed.

Ports:

| Port | Status/use |
| --- | --- |
| `8000` | Existing Python backend listener observed; not restarted, stopped, or used by the mock pass. |
| `8001` | Free; not used. |
| `5173` | Existing Vite/Codex frontend listener observed; not touched. |
| `4173` | Free; not used. |
| `5174` | Free; not used. |
| `5175` | Free; not used. |
| `5176` | Free before task; started isolated preview for Playwright; stopped after verification and confirmed free. |

Limitations:

- This is rendered DOM evidence under corrected mocks, not live authenticated backend data.
- The corrected mock intentionally blocked non-GET API calls and no UI action was clicked that would start scanner, analysis, watchlist write, or backtest jobs.
- The fixture used provider-like labels such as `fixture_quote`; the raw/debug leakage scan found no visible API key/token/secret/system-prompt/schema text.
- Parallel dirty CSS existed during the browser proof: `apps/dsa-web/src/index.css` showed 57 unrelated deletions. This report did not inspect, stage, or modify that CSS diff.

## 3. Static Baseline

| Check | Result | Key output | Notes |
| --- | --- | --- | --- |
| `pwd` | PASS | `/Users/yehengli/daily_stock_analysis` | Required path. |
| Branch | PASS | `main` | Required branch. |
| Initial preflight | PASS | `origin/main`, ahead 0 / behind 0; dirty files 0 | Worktree was clean at task start. |
| Port inspection | PASS | `8000` Python listener; `5173` node listener; `8001`, `4173`, `5174`, `5175`, `5176` free | Shared servers were not interrupted. |
| Parallel dirty file check | LIMITATION | `apps/dsa-web/src/index.css | 57 deletions(-)` appeared after preflight | Unrelated CSS dirty file was not touched or staged. |
| `npm run check:design` | PASS | 216 files scanned; 0 blocking; 0 warnings | Design guard clean. |
| `npm run lint` | PASS | `eslint .` exited 0 | No lint output. |
| `npm run build` | PASS with warning | 3160 modules transformed; built in 11.38s | Vite warned on `DeterministicBacktestChartWorkspace-Clbq12EG.js` at 532.42 kB / gzip 178.83 kB. |
| Backend compile | PASS | `python3 -m compileall -q src api` exited 0 | No output. |
| Markdown lint | Not available | Search found `remark` package/docs references, but no runnable markdown lint script | No markdown lint command was run. |
| `./scripts/ci_gate.sh` | Not run | Report-only docs task | Full CI was not required because no product code, CSS, tests, backend/API, package, or config files were changed. |

## 4. Scanner Source/Context Summary

Shell class generation evidence:

- `apps/dsa-web/src/components/layout/Shell.tsx:208` appends `theme-shell--scanner` when `isScannerRoute`.
- `apps/dsa-web/src/components/layout/Shell.tsx:246` appends `shell-content-frame--scanner` when `isScannerRoute`.
- `apps/dsa-web/src/components/layout/Shell.tsx:248` appends `shell-main-column--scanner` when `isScannerRoute`.
- `apps/dsa-web/src/components/layout/__tests__/Shell.test.tsx:354-359` asserts all three scanner shell/content/main selectors exist on `/scanner`.

Scanner route/test fixture evidence:

- `apps/dsa-web/src/pages/ScannerSurfacePage.test.tsx` verifies guests receive the auth guard and signed-in/admin accounts render `UserScannerPage`.
- `apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx` provides contract-faithful scanner fixtures for run detail, history response, theme response, watchlist items, strategy simulation, and backtest response shape.
- `UserScannerPage.test.tsx` asserts compact scanner workspace test IDs such as `user-scanner-workspace`, `scanner-sidebar`, `scanner-candidate-scroll-region`, `scanner-result-history-summary`, `scanner-history-empty-state`, and `scanner-diagnostics-summary`.
- `UserScannerPage.test.tsx` asserts developer diagnostics are not rendered by default: `scanner-diagnostics-panel` appears only after clicking the developer diagnostics disclosure.

Candidate selector source evidence:

- Candidate deletion selectors are defined in CSS or CSS-only override layers: `glass-card`, `terminal-card`, `dashboard-card`, `gradient-border-card`, `workspace-page--chat`, `stealth-scrollbar`, `backtest-entry-shell`, and `product-command-card`.
- `workspace-page--chat` has a test-only negative assertion in `ChatPage.test.tsx`.
- `backtest-entry-shell` appears in production as a `data-testid`, not as a CSS class.
- `product-command-card` remains CSS-only by source search but appears in multiple product/backtest override layers, so it remains high-risk even with scanner absence.

Scanner route class observations:

- The scanner page primarily uses Tailwind utilities, shared common components, and data-testid markers for scanner content.
- Corrected DOM substring scans found scanner-related shell class tokens, but no literal candidate/action/command CSS class tokens beyond shell infrastructure.
- `custom-scrollbar` was not present on corrected scanner DOM. Active table overflow uses utility classes such as `overflow-x-auto` and `no-scrollbar` when table view is opened; this audit did not trigger table-view interaction because default route proof was sufficient for shell verification.

## 5. Rendered DOM Evidence

| Viewport | Mode | Route render status | Scanner shell class counts | Candidate selector hit counts | Overflow | Page/console errors | Raw/debug leakage | Notes |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| `1440x1000` | Corrected Playwright mocks | Full scanner route rendered | `theme-shell--scanner=1`; `shell-content-frame--scanner=1`; `shell-main-column--scanner=1` | all candidate selectors `0` | 0 | console `0`; page `0`; unhandled API `0` | none found; developer diagnostics collapsed | Workspace, sidebar, run button, result history, candidate area, and diagnostics summary rendered. |
| `390x844` | Corrected Playwright mocks | Full scanner route rendered | `theme-shell--scanner=1`; `shell-content-frame--scanner=1`; `shell-main-column--scanner=1` | all candidate selectors `0` | 0 | console `0`; page `0`; unhandled API `0` | none found; developer diagnostics collapsed | Same shell/content/candidate/history proof on narrow viewport. |

Exact class hit counts:

| Selector | Desktop | Mobile |
| --- | ---: | ---: |
| `.theme-shell--scanner` | 1 | 1 |
| `.shell-content-frame--scanner` | 1 | 1 |
| `.shell-main-column--scanner` | 1 | 1 |
| `.glass-card` | 0 | 0 |
| `.terminal-card` | 0 | 0 |
| `.dashboard-card` | 0 | 0 |
| `.gradient-border-card` | 0 | 0 |
| `.workspace-page--chat` | 0 | 0 |
| `.stealth-scrollbar` | 0 | 0 |
| `.backtest-entry-shell` | 0 | 0 |
| `.product-command-card` | 0 | 0 |

Substring class scan highlights:

| Substring | Desktop tokens | Mobile tokens |
| --- | --- | --- |
| `scanner` | `theme-shell--scanner`, `shell-content-frame--scanner`, `shell-main-column--scanner` | same |
| `shell-content-frame` | `shell-content-frame`, `shell-content-frame--scanner`, `shell-content-frame--wide` | same |
| `shell-main-column` | `shell-main-column`, `shell-main-column--scanner` | same |
| `theme-shell` | `theme-shell`, `theme-shell--scanner`, `theme-shell--wide` | same |
| `candidate` | none as class tokens | none as class tokens |
| `result` | none as class tokens | none as class tokens |
| `history` | `lucide-history` icon class only | `lucide-history` icon class only |
| `command` | none as class tokens | none as class tokens |
| `action` | none as class tokens | none as class tokens |
| `custom-scrollbar` | none | none |

Visible content evidence included:

- `基础扫描`, `市场`, `扫描配置`, `运行扫描`
- `扫描结果`, `入选 3`, `结果历史`
- `本次扫描`, `最近扫描`, `上次扫描`
- `诊断摘要`, `查看淘汰原因`, `开发者诊断`
- candidate cards for `NVDA`, `AVGO`, and `AMD`

Developer details:

- `scanner-diagnostics-summary` rendered.
- `scanner-diagnostics-panel` was absent by default at both viewports.
- No default-visible API key, token, bearer, authorization, webhook URL, system prompt, raw schema, password, or secret text was detected.

## 6. Selector Conclusions

| Selector | Evidence | Classification | Future action |
| --- | --- | --- | --- |
| `theme-shell--scanner` | Static generation in `Shell.tsx`; shell test assertions; rendered count `1` at desktop and mobile | Active scanner route infrastructure | Keep. Do not delete or migrate without a dedicated scanner shell owner-migration task and route proof. |
| `shell-content-frame--scanner` | Static generation in `Shell.tsx`; shell test assertions; rendered count `1` at desktop and mobile | Active scanner route infrastructure | Keep. Treat as scanner content frame/overflow infrastructure. |
| `shell-main-column--scanner` | Static generation in `Shell.tsx`; shell test assertions; rendered count `1` at desktop and mobile | Active scanner route infrastructure | Keep. Treat as scanner main-column and scroll ownership infrastructure. |
| `glass-card` | CSS-only source evidence; rendered count `0` at both scanner viewports | Absent on corrected scanner route | Scanner no longer blocks a future separate deletion trial, but this report does not approve deletion. |
| `terminal-card` | CSS-only source evidence; rendered count `0` at both scanner viewports | Absent on corrected scanner route | Scanner no longer blocks a future separate deletion trial, but verify Home/report/preview card hierarchy in the deletion task. |
| `dashboard-card` | CSS-only source evidence; rendered count `0` at both scanner viewports | Absent on corrected scanner route | Scanner no longer blocks a future separate deletion trial; dashboard-like routes still need their own deletion-trial proof. |
| `gradient-border-card` | CSS-only wrapper/inner source evidence; rendered count `0` at both scanner viewports | Absent on corrected scanner route | Scanner no longer blocks a future separate deletion trial; verify wrapper/inner absence across other affected routes. |
| `workspace-page--chat` | Test-only negative source evidence for Chat; rendered scanner count `0` | Not scanner-owned; absent on scanner | Scanner evidence is complete, but Chat route remains the deletion owner for this selector. |
| `stealth-scrollbar` | Test-only negative source evidence; rendered scanner count `0`; no `custom-scrollbar` on scanner default DOM | Absent on corrected scanner route | Scanner no longer blocks future scrollbar audit, but deletion still requires all-route scroll-container proof. |
| `backtest-entry-shell` | CSS class has weak source evidence; production Backtest uses same token as `data-testid`, not class; rendered scanner count `0` | Not scanner-owned; absent on scanner | Scanner evidence is complete, but Backtest entry route remains the deletion owner. |
| `product-command-card` | CSS-only source evidence with many product/backtest override layers; rendered scanner count `0` | Absent on corrected scanner route, still high-risk primitive candidate | Do not trial first. Document product command owner and verify Backtest/preview/product command surfaces before any deletion. |

## 7. Recommended Next Tasks

- Keep scanner shell selectors `theme-shell--scanner`, `shell-content-frame--scanner`, and `shell-main-column--scanner` on the do-not-delete list.
- Candidate deletion trials for `glass-card`, `terminal-card`, `dashboard-card`, `gradient-border-card`, `workspace-page--chat`, `stealth-scrollbar`, `backtest-entry-shell`, and `product-command-card` can proceed without the prior scanner mock-shape blocker, but only in separate selector-family deletion tasks with route-level proof.
- Scanner fixture work is sufficient for scanner shell DOM verification. More fixture work is only needed if future scanner primitive migration needs interaction states such as table view, expanded diagnostics, batch backtest handoff, or watchlist writes.
- Defer scanner primitive migration while `apps/dsa-web/src/index.css` is being changed by a parallel deletion task. Scanner CSS/primitive work should be serialized with global CSS edits.
- Do not use this report to approve direct CSS deletion. Use `docs/checks/css-visual-regression-checklist.md` for any future deletion prompt.

Safe future scanner tasks:

- Read-only scanner route DOM checks for additional view states.
- Scanner-specific fixture expansion under tests or temporary Playwright scripts when explicitly requested.
- Scanner shell owner documentation.

Unsafe future scanner tasks without a new scope:

- Deleting scanner shell selectors.
- Migrating scanner shell/content/main-column CSS while global CSS is dirty.
- Combining scanner primitive migration with product behavior changes, real scanner runs, backend/API changes, or Backtest integration changes.
- Deleting `product-command-card` based on scanner absence alone.

## 8. Non-Goals

- No product code changed.
- No CSS changed.
- No tests changed.
- No backend/API changed.
- No package files or config changed.
- No scripts changed.
- No `docs/CHANGELOG.md` changed.
- No real scanner runs triggered.
- No watchlist, analysis, or backtest mutations triggered.
- No generated artifacts committed.
- No selector deletion approved directly.

## 9. Appendix

Preflight summary:

```text
pwd: /Users/yehengli/daily_stock_analysis
branch: main
git status --short: clean at task start
git status --branch --short: ## main...origin/main
task_preflight: branch main, upstream origin/main ahead 0 / behind 0, dirty files 0
```

Recent commits observed included:

```text
89933dc docs: verify css selector dom usage
3f68c7c docs: define canonical ui primitives
74afcb4 docs: add css visual regression checklist
6cfa4fe docs: audit frontend design conformance
799e38e fix(ui): improve mobile touch targets
18b78fb fix(scanner): polish native control styling
b71654c feat(scanner): clarify result history and failure states
```

Static baseline output summary:

```text
npm run check:design
Files scanned: 216
Design guard passed. No blocking violations or warnings found.

npm run lint
eslint . exited 0

npm run build
3160 modules transformed
DeterministicBacktestChartWorkspace-Clbq12EG.js 532.42 kB / gzip 178.83 kB
Some chunks are larger than 500 kB after minification.
built in 11.38s

python3 -m compileall -q src api
exited 0 with no output
```

Port output summary:

```text
8000: Python listener on localhost; observed only
8001: free
5173: node listener; observed only
4173: free
5174: free
5175: free
5176: free before run; used for isolated preview; free after stop
```

Playwright route hit counts:

```text
route: /zh/scanner
desktop 1440x1000:
  renderStatus: full scanner route rendered
  shell counts: 1 / 1 / 1
  candidate selector counts: all 0
  overflowDelta: 0
  console/page/unhandled API errors: 0 / 0 / 0
  diagnostics panel open by default: false

mobile 390x844:
  renderStatus: full scanner route rendered
  shell counts: 1 / 1 / 1
  candidate selector counts: all 0
  overflowDelta: 0
  console/page/unhandled API errors: 0 / 0 / 0
  diagnostics panel open by default: false
```

Markdown lint:

```text
rg -n "markdownlint|mdlint|remark|lint:md|lint.*markdown|markdown.*lint" package.json apps/dsa-web/package.json .github scripts docs 2>/dev/null | head -80
```

Result: no runnable markdown lint script found.

Cleanup:

- Temporary Playwright script/result were created under `/tmp` for evidence extraction only.
- Generated screenshots/videos/traces/reports were not created.
- Temporary `/tmp` files are not part of the commit.
