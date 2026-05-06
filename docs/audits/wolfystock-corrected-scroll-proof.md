# WolfyStock Corrected Scroll Proof

Status: Partial
Owner domain: Frontend CSS and DOM verification
Related docs: `docs/audits/wolfystock-css-cleanup-closure-report.md`, `docs/audits/wolfystock-css-ownership-inventory.md`

Date: 2026-05-05 Asia/Shanghai
Repository: `/Users/yehengli/daily_stock_analysis`
Branch: `main`
Mode: read-only audit/report plus one docs artifact; no product code, tests, CSS, backend/API, package, config, scripts, runtime files, or `docs/CHANGELOG.md` edits by this task

## 1. Executive Summary

Corrected proof status: **PASS with limitations**.

The prior route-wide scrollbar audit reported `.stealth-scrollbar=0`, but Scanner, Portfolio, and Market Overview were inconclusive because their route mocks failed page contracts. This corrected pass used route-specific, contract-faithful Playwright mocks and rendered all three target routes at desktop `1440x1000` and mobile `390x844` without page errors.

| Route | Corrected scroll-heavy state rendered? | `.stealth-scrollbar` | Future deletion-trial readiness |
| --- | --- | ---: | --- |
| `/zh/scanner` | Yes: authenticated scanner shell, controls, candidate area, result history, diagnostics summary, developer details collapsed | 0 both viewports | Ready as corrected Scanner evidence; future trial still needs clean CSS state. |
| `/zh/portfolio` | Yes: populated account, multiple holdings, FX, risk/exposure, P&L, trades, cash/events/history sections | 0 both viewports | Ready as corrected Portfolio evidence; future trial still needs clean CSS state. |
| `/zh/market-overview` | Yes: indices, freshness/provider state, volatility, funds flow, macro, sentiment, crypto, cards and dense grids | 0 both viewports | Ready as corrected Market Overview evidence; future trial still needs clean CSS state. |

Deletion-trial verdict: **`stealth-scrollbar` is now stronger future-deletion-trial candidate, but not deleted here**. The remaining blocker is not these three route mocks; it is clean-state trial discipline. During this audit, unrelated parallel dirty files appeared in `apps/dsa-web/src/index.css` and `apps/dsa-web/src/pages/WatchlistPage.tsx`. This task did not touch, stage, or commit them.

Route/state still inconclusive: **clean-state global deletion behavior**. The corrected route proof is good, but the actual deletion trial must rerun from a clean CSS state or explicitly account for any parallel CSS diff.

## 2. Methodology

Required preflight was run first:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -140
./scripts/task_preflight.sh || true
```

Preflight result:

- `pwd`: `/Users/yehengli/daily_stock_analysis`
- branch: `main`
- upstream: `origin/main`, ahead 0 / behind 0
- initial dirty files: 0
- recent commits included `489ec7f`, `47c85ed`, `44321ba`, `2e97b39`, `af19a25`, `799e38e`, and `6cfa4fe`

Mandatory reading completed:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/audits/wolfystock-scrollbar-dom-verification.md`
- `docs/audits/wolfystock-scanner-dom-verification.md`
- `docs/qa/wolfystock-portfolio-populated-holdings-qa.md`
- `docs/audits/wolfystock-frontend-design-conformance-audit.md`
- `docs/design/wolfystock-canonical-ui-primitives.md`
- `docs/checks/css-visual-regression-checklist.md`
- `docs/operations/parallel-codex-playbook.md`

Port inspection before Playwright:

| Port | Status |
| --- | --- |
| `8000` | Existing Python listener; observed only |
| `8001` | Free |
| `5173` | Existing Node listener; observed only |
| `4173` | Free |
| `5174` | Free |
| `5175` | Free before task; used for isolated Vite dev proof; stopped after proof |
| `5176` | Free |

Static investigation command:

```bash
cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
rg -n "stealth-scrollbar|no-scrollbar|custom-scrollbar|overflow-y-auto|overflow-x-auto|overflow-auto|overflow-hidden|scrollbar|scrollHeight|clientHeight|scrollWidth|clientWidth" src/pages/UserScannerPage.tsx src/pages/PortfolioPage.tsx src/pages/MarketOverviewPage.tsx src/components src/__tests__ | head -1000
```

Playwright method:

- Temporary runner: `/tmp/wolfystock_corrected_scroll_proof.mjs`
- Temporary result JSON: `/tmp/wolfystock_corrected_scroll_proof_results.json`
- Browser: Playwright Chromium from `apps/dsa-web`
- Server: isolated `npm run dev -- --host 127.0.0.1 --port 5175`
- Routes: `/zh/scanner`, `/zh/portfolio`, `/zh/market-overview`
- Viewports: desktop `1440x1000`, mobile `390x844`
- Auth: mocked authenticated admin user through `/api/v1/auth/status`
- API safety: `**/api/v1/**` intercepted; non-GET mutations returned a blocked fixture response
- EventSource safety: `window.EventSource` replaced with an inert mock to avoid MIME fixture errors
- No real scanner runs, portfolio writes, providers, or LLM calls were made
- No screenshots, traces, videos, Playwright reports, or temp files were committed

Mock/data strategy:

- Scanner: fixture run history and run detail with candidate arrays, result history, diagnostics summary, provider diagnostics, comparison/review metadata, themes, status, and watchlist items.
- Portfolio: one populated global account, six holdings across US/HK/CN, FX rates, analytics, concentration, currency/market/symbol exposure, P&L contributors, trades, cash ledger, and corporate actions.
- Market Overview: old `/api/v1/market-overview/*` panels plus new `/api/v1/market/*` panels, temperature scores including `scores.overall`, market briefing, futures, CN short sentiment, crypto, provider/freshness metadata.

Limitations:

- This is mocked browser proof, not live authenticated user-data proof.
- It verifies corrected scroll-heavy route states, not the result of deleting CSS.
- Parallel dirty files appeared after preflight:
  - `apps/dsa-web/src/index.css`
  - `apps/dsa-web/src/pages/WatchlistPage.tsx`
- Static `lint` and `build` are currently blocked by the unrelated dirty `WatchlistPage.tsx`; this audit did not fix or stage it.

## 3. Static Baseline

| Check | Result | Key output |
| --- | --- | --- |
| `pwd` | PASS | `/Users/yehengli/daily_stock_analysis` |
| Branch | PASS | `main` |
| Initial preflight | PASS | clean worktree; `origin/main` ahead 0 / behind 0 |
| Port inspection | PASS | `8000` and `5173` occupied by existing shared listeners; `5175` free and used for isolated proof |
| `npm run check:design` | PASS | 216 files scanned; 0 blocking violations; 0 warnings |
| `npm run lint` | BLOCKED by unrelated dirty file | `WatchlistPage.tsx` unused imports/constants: `Button`, `StatusBadge`, `describeBooleanEnabled`, `describeDisplayStatus`, `WATCHLIST_*`, `displayBadgeVariant` |
| `npm run build` | BLOCKED by unrelated dirty file | same `WatchlistPage.tsx` unused symbols plus missing `ACTION_BUTTON_CLASS`, `CHIP_CLASS`, `ICON_BUTTON_CLASS` |
| `python3 -m compileall -q src api` | PASS | exited 0 with no output |
| Markdown lint | Not run | no markdown lint script found; package scripts only expose `lint: eslint .` |
| `./scripts/ci_gate.sh` | Not run | report-only docs task; static frontend gates are already blocked by unrelated dirty Watchlist work |

## 4. Static Route Ownership Evidence

| Route/surface | Static scroll utility evidence | Current owner interpretation |
| --- | --- | --- |
| Scanner | `UserScannerPage.tsx` uses `overflow-y-auto no-scrollbar` in candidate/list panels, `overflow-x-auto no-scrollbar` for scanner result/simulation tables, and `overflow-hidden` for contained cards/rows. | Scanner owns `no-scrollbar` and route-local overflow utilities; no `stealth-scrollbar` owner found. |
| Portfolio | `PortfolioPage.tsx` uses `overflow-y-auto no-scrollbar` plus arbitrary scrollbar-hidden utilities such as `[&::-webkit-scrollbar]:hidden`, `[-ms-overflow-style:none]`, and `[scrollbar-width:none]`; history card conditionally adds `max-h-[800px] overflow-y-auto no-scrollbar`. | Portfolio owns explicit hidden-scrollbar and vertical scroll containers; no `stealth-scrollbar` owner found. |
| Market Overview | `MarketOverviewPage.tsx`, `MarketOverviewCard.tsx`, `VolatilityCard.tsx`, and `MarketSentimentCard.tsx` use `overflow-y-auto no-scrollbar ui-scroll-y-quiet`; route/card primitives use `overflow-hidden` for clipping. | Market Overview owns dense-card vertical scroll through `no-scrollbar` and route-local overflow utilities; no `stealth-scrollbar` owner found. |
| Shared components | `components/common/ScrollArea.tsx` uses `overflow-y-auto ... custom-scrollbar no-scrollbar`; `Drawer`, report details, settings panels, backtest report tables also use active scroll utilities. | `custom-scrollbar` is shared-component scoped through `ScrollArea`; do not delete without a separate owner inventory. |

Static selector conclusions:

- `stealth-scrollbar`: not owned by the inspected route TSX files; prior report found CSS/test-negative evidence only.
- `no-scrollbar`: active and route-owned.
- `custom-scrollbar`: active shared component utility through `ScrollArea`, even though it was not emitted by these three corrected route states.
- `overflow-y-auto`, `overflow-x-auto`, `overflow-auto`, `overflow-hidden`: active route/local layout utilities; preserve.
- Arbitrary scrollbar-hidden utilities: active Portfolio local ownership; preserve.

## 5. Rendered Corrected Scroll Matrix

Exact DOM class hits and class-token counts were collected after route load. `Doc delta` is `document.documentElement.scrollWidth - document.documentElement.clientWidth`.

| Route | Viewport | Render status | `.stealth-scrollbar` | `.no-scrollbar` | `.custom-scrollbar` | Overflow token counts | Top scroll containers / owners | Doc delta | Errors | Notes |
| --- | --- | --- | ---: | ---: | ---: | --- | --- | ---: | --- | --- |
| `/zh/scanner` | `1440x1000` | PASS corrected full scanner | 0 | 3 | 0 | `y-auto=3`, `x-auto=0`, `auto=0`, `hidden=2` | sticky sidebar `overflow-y-auto no-scrollbar` `360x555 -> 360x555`; candidate list `overflow-y-auto no-scrollbar` `355x420 -> 355x420`; page computed `hidden/auto` `1440x1475 -> 1440x1475`; `scanner-market-toggle` computed `auto/auto` `206x32 -> 206x32` | 0 | none | Rendered `user-scanner-workspace=1`, `scanner-candidate-scroll-region=1`, `scanner-result-history-summary=1`; developer diagnostics collapsed. |
| `/zh/scanner` | `390x844` | PASS corrected full scanner | 0 | 3 | 0 | `y-auto=3`, `x-auto=0`, `auto=0`, `hidden=2` | candidate list `overflow-y-auto no-scrollbar` `298x420 -> 298x420`; page computed `hidden/auto` `390x2634 -> 390x2634`; market toggle computed `auto/auto` `296x32 -> 296x32`; profile rail computed `auto/auto` `298x29 -> 298x29` | 0 | none | Rendered scanner shell, controls, candidates, history, diagnostics summary; no raw/API-key leakage. |
| `/zh/portfolio` | `1440x1000` | PASS corrected populated account | 0 | 3 | 0 | `y-auto=3`, `x-auto=0`, `auto=0`, `hidden=2` | page computed `hidden/auto` `1298x855 -> 1298x2806`; `portfolio-bento-page` `1296x855 -> 1296x2806`; risk/detail block `lg:overflow-y-auto lg:no-scrollbar` `782x420 -> 782x482`; `portfolio-trade-station-scroll` `362x585 -> 362x585`; `portfolio-history-full` computed `hidden/auto` `817x615 -> 817x615` | 0 | none | Populated holdings, FX, risk/exposure, P&L, trade/history/events sections rendered. |
| `/zh/portfolio` | `390x844` | PASS corrected populated account | 0 | 3 | 0 | `y-auto=3`, `x-auto=0`, `auto=0`, `hidden=2` | page computed `hidden/auto` `323x710 -> 323x5415`; `portfolio-bento-page` `320x710 -> 320x5415`; `portfolio-trade-station-scroll` `255x871 -> 255x871`; `portfolio-history-full` computed `hidden/auto` `290x660 -> 290x660`; local arbitrary hidden-scrollbar utilities present | 0 | none | No horizontal document overflow; no mutation requests. |
| `/zh/market-overview` | `1440x1000` | PASS corrected full overview | 0 | 8 | 0 | `y-auto=8`, `x-auto=0`, `auto=0`, `hidden=136` | page computed `hidden/auto` `1298x855 -> 1298x2141`; `market-overview-shell` `1296x855 -> 1296x2141`; `market-overview-workbench` `1296x855 -> 1296x2141`; dense quote grids `overflow-y-auto no-scrollbar` around `451x176 -> 483x176` | 0 | none | Rendered indices, provider/freshness states, volatility, funds flow, macro, sentiment, crypto, dense cards. |
| `/zh/market-overview` | `390x844` | PASS corrected full overview | 0 | 8 | 0 | `y-auto=8`, `x-auto=0`, `auto=0`, `hidden=136` | page computed `hidden/auto` `323x710 -> 323x4703`; `market-overview-shell` `320x710 -> 320x4703`; `market-overview-workbench` `320x710 -> 320x4703`; dense grids `294x190 -> 294x229/196`; `market-command-chips` computed `auto/auto` `290x28 -> 447x28` | 0 | none | Inert EventSource mock avoided MIME console errors; no raw/API-key leakage. |

Raw/debug/provider/schema/token/API-key leakage scan: **none found** in all six rendered rows.

## 6. Route Conclusions

### Scanner

Verdict: **Corrected Scanner proof is sufficient for a future `stealth-scrollbar` deletion trial input**.

The route rendered the real authenticated scanner surface under corrected mocks: scanner workspace, market/profile controls, candidate area, result history, diagnostics summary, and collapsed developer diagnostics. `.stealth-scrollbar` was absent at both viewports. Active scroll ownership is `no-scrollbar`, `overflow-y-auto`, computed page scroll, and local horizontal control rails.

Remaining limitation: this did not trigger a real scanner run and did not mutate scanner/watchlist/backtest state. That is intentional for this read-only audit.

### Portfolio

Verdict: **Corrected Portfolio proof is sufficient for a future `stealth-scrollbar` deletion trial input**.

The route rendered a populated account with multiple holdings, FX transparency, risk/exposure sections, P&L contributors, trades, cash ledger, corporate actions, and history. `.stealth-scrollbar` was absent at both viewports. Active scroll ownership is `no-scrollbar`, `overflow-y-auto`, `overflow-hidden`, computed page scroll, and Portfolio-local arbitrary hidden-scrollbar utilities.

Remaining limitation: this was not live portfolio data. No portfolio write, sync, FX refresh, trade, cash, or corporate-action mutation was made.

### Market Overview

Verdict: **Corrected Market Overview proof is sufficient for a future `stealth-scrollbar` deletion trial input**.

The route rendered the full overview with legacy and new market endpoints mocked together: indices/cards, provider/freshness states, volatility, funds flow, macro, sentiment, crypto, market temperature, briefing, futures, and dense quote grids. `.stealth-scrollbar` was absent at both viewports. Active scroll ownership is `no-scrollbar`, `overflow-y-auto`, `overflow-hidden`, `ui-scroll-y-quiet`, computed page scroll, and local horizontal chip rails.

Remaining limitation: market values were fixture data and EventSource was mocked inert. This avoided real providers and stream MIME noise by design.

## 7. Selector Conclusions

### `stealth-scrollbar`

Classification: **DOM absent in corrected target states; future deletion-trial candidate**.

Evidence:

- Corrected Scanner: 0 desktop, 0 mobile.
- Corrected Portfolio: 0 desktop, 0 mobile.
- Corrected Market Overview: 0 desktop, 0 mobile.
- No target-route TSX owner found in static search.

Decision: appropriate for a future clean-state deletion trial, but this report does not delete it.

### `no-scrollbar`

Classification: **active current owner**.

Evidence:

- Scanner: 3 hits per viewport.
- Portfolio: 3 hits per viewport.
- Market Overview: 8 hits per viewport.
- Static usage appears in target routes and shared components.

Decision: do not delete. It is the active hidden-scrollbar utility for these surfaces.

### `custom-scrollbar`

Classification: **active shared utility, not emitted by these three corrected states**.

Evidence:

- Rendered corrected target routes: 0 hits.
- Static owner: `components/common/ScrollArea.tsx` pairs `custom-scrollbar` with `no-scrollbar`.

Decision: do not delete without a separate `ScrollArea` owner inventory and consumer proof.

### Route-local overflow classes

Classification: **active layout and scroll ownership**.

Evidence:

- `overflow-y-auto`: active in all three corrected route states.
- `overflow-x-auto`: statically active in Scanner tables; not emitted in the captured corrected default states.
- `overflow-auto`: not emitted in these corrected route states, but active elsewhere such as reports/backtest/admin raw views.
- `overflow-hidden`: active clipping/layout utility, especially Market Overview.
- Arbitrary scrollbar-hidden utilities: active Portfolio ownership.

Decision: preserve. Future CSS cleanup must inspect rendered dimensions and computed overflow, not just selector names.

## 8. Recommended Next Tasks

1. Run a clean-state `stealth-scrollbar` deletion trial when `apps/dsa-web/src/index.css` is clean or the CSS diff is explicitly owned by that deletion task.
2. In that deletion trial, rerun this corrected three-route Playwright matrix at `1440x1000` and `390x844`, plus any all-route matrix required by the CSS visual regression checklist.
3. Keep `no-scrollbar` out of scope for deletion; it is active on Scanner, Portfolio, and Market Overview.
4. Create a separate `custom-scrollbar` / `ScrollArea` owner inventory before any `custom-scrollbar` change.
5. If stronger live confidence is needed, rerun Portfolio and Market Overview with safe read-only live data, but keep real writes/providers/LLMs blocked.

## 9. Non-Goals

- No CSS changed.
- No product code changed.
- No tests changed.
- No backend/API changed.
- No package/config/script/runtime files changed.
- No `docs/CHANGELOG.md` changed.
- No real provider calls.
- No real LLM calls.
- No real scanner runs.
- No portfolio mutations.
- No generated screenshots, traces, videos, Playwright reports, or temp artifacts committed.
- No unrelated dirty files staged or committed.

## 10. Appendix

Command output summary:

```text
pwd
/Users/yehengli/daily_stock_analysis

git branch --show-current
main

./scripts/task_preflight.sh || true
PASS; branch main; upstream origin/main ahead 0 / behind 0; dirty files 0

lsof -i :8000
Python listeners on localhost:irdmi

lsof -i :5173
node listener on *:5173

lsof -i :8001, :4173, :5174, :5175, :5176
no output before Playwright

npm run check:design
Files scanned: 216
Design guard passed. No blocking violations or warnings found.

npm run lint
BLOCKED: apps/dsa-web/src/pages/WatchlistPage.tsx unrelated unused-symbol errors

npm run build
BLOCKED: apps/dsa-web/src/pages/WatchlistPage.tsx unrelated TS errors

python3 -m compileall -q src api
PASS; no output

lsof -i :5175 after Playwright
no output
```

Corrected rendered hit-count summary:

| Route | Viewport | `.stealth-scrollbar` | `.no-scrollbar` | `.custom-scrollbar` | `overflow-y-auto` | `overflow-x-auto` | `overflow-auto` | `overflow-hidden` | Doc delta | Errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `/zh/scanner` | desktop | 0 | 3 | 0 | 3 | 0 | 0 | 2 | 0 | 0 |
| `/zh/scanner` | mobile | 0 | 3 | 0 | 3 | 0 | 0 | 2 | 0 | 0 |
| `/zh/portfolio` | desktop | 0 | 3 | 0 | 3 | 0 | 0 | 2 | 0 | 0 |
| `/zh/portfolio` | mobile | 0 | 3 | 0 | 3 | 0 | 0 | 2 | 0 | 0 |
| `/zh/market-overview` | desktop | 0 | 8 | 0 | 8 | 0 | 0 | 136 | 0 | 0 |
| `/zh/market-overview` | mobile | 0 | 8 | 0 | 8 | 0 | 0 | 136 | 0 | 0 |

Parallel dirty state observed after preflight:

```text
 M apps/dsa-web/src/index.css
 M apps/dsa-web/src/pages/WatchlistPage.tsx
```

These files were not touched, staged, or committed by this task.
