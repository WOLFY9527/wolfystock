# WolfyStock Scrollbar DOM Verification

Date: 2026-05-05 Asia/Shanghai
Repository: `/Users/yehengli/daily_stock_analysis`
Branch: `main`
Mode: read-only scrollbar ownership audit; no product code, tests, CSS, backend/API, package, config, runtime, or changelog changes

## 1. Executive Summary

`stealth-scrollbar` was **not present in rendered DOM** in the collected 13-route by 2-viewport Playwright matrix. It also has no production TSX owner in the required static search; current source evidence for `stealth-scrollbar` is CSS plus negative test assertions in Market Overview tests.

Current hidden-scrollbar ownership is carried by:

- `no-scrollbar`: active route/local utility used by Chat, Scanner tables/panels, Watchlist table, Backtest rails, Portfolio sections, Settings/System panels, Admin Logs tables, report tables, drawers, and common components.
- `custom-scrollbar`: active only through `components/common/ScrollArea.tsx`, where it is paired with `no-scrollbar`; no rendered hits appeared in this default route matrix.
- route-local overflow utilities: `overflow-y-auto`, `overflow-x-auto`, `overflow-auto`, `overflow-hidden`, plus arbitrary Tailwind scrollbar-hidden utilities such as `[&::-webkit-scrollbar]:hidden`, `[-ms-overflow-style:none]`, and `[scrollbar-width:none]`.
- native/page scroll: several routes rely on shell/page containers with computed `overflow: hidden/auto` rather than literal Tailwind class tokens on the visible element.

Conclusion: `stealth-scrollbar` can be classified as **DOM absent and future deletion-trial candidate**, but not approved for deletion by this report. Stronger scroll-state proof is still needed for Scanner, Portfolio, and Market Overview because the current route-wide mock pass hit page-level fixture-shape errors on those surfaces. The report also carries a parallel-work limitation: `apps/dsa-web/src/index.css` became dirty from another session after preflight, and this task did not touch or stage that CSS.

## 2. Methodology

Required preflight was run first:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -130
./scripts/task_preflight.sh || true
```

Result:

- `pwd`: `/Users/yehengli/daily_stock_analysis`
- branch: `main`
- initial status: clean
- upstream: `origin/main`, ahead 0 / behind 0
- `task_preflight.sh`: PASS, dirty files 0

Mandatory reading completed:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/checks/css-visual-regression-checklist.md`
- `docs/audits/archive/frontend/wolfystock-css-cleanup-closure-report.md`
- `docs/audits/archive/frontend/wolfystock-chat-dom-verification.md`
- `docs/audits/archive/frontend/wolfystock-scanner-dom-verification.md`
- `docs/audits/wolfystock-frontend-design-conformance-audit.md`
- `docs/design/wolfystock-canonical-ui-primitives.md`
- `docs/operations/parallel-codex-playbook.md`

Static investigation:

```bash
cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
rg -n "stealth-scrollbar|no-scrollbar|custom-scrollbar|overflow-y-auto|overflow-auto|scrollbar|scrollWidth|clientWidth|scrollHeight|clientHeight" src/index.css src/pages src/components src/__tests__ | head -900
```

Additional route/component source searches inspected the requested route files and preview report components for scroll/overflow ownership.

Playwright method:

- Browser: headless Chromium from local `apps/dsa-web` Playwright install.
- Frontend: isolated `npm run preview -- --host 127.0.0.1 --port 5175`.
- Existing ports observed and left alone: Python backend on `8000`; Vite/Codex frontend on `5173`; another Node listener on `5176`.
- Viewports: desktop `1440x1000`, mobile `390x844`.
- Routes: `/zh`, `/zh/scanner`, `/zh/watchlist`, `/zh/backtest`, `/zh/backtest/results/1`, `/zh/portfolio`, `/zh/market-overview`, `/zh/settings`, `/zh/settings/system`, `/zh/admin/logs`, `/zh/admin/notifications`, `/zh/chat`, `/zh/__preview/report`.
- API safety: `**/api/v1/**` was intercepted with audit mocks; non-GET requests were fulfilled as blocked fixture responses. No real LLM/provider calls, scanner runs, portfolio writes, notification sends, or backend mutations were triggered.
- Evidence collected per route/viewport: exact class counts, overflow utility token counts, document horizontal overflow delta, page/console errors, request failures, and top scrollable containers where `scrollHeight > clientHeight + 4` or `scrollWidth > clientWidth + 4`.

Limitations:

- This was a mocked DOM pass, not live authenticated user-data proof.
- Scanner, Portfolio, and Market Overview hit mock-shape page errors in the route-wide collector.
- Home and Market Overview emitted EventSource MIME console errors because stream endpoints were mocked as JSON.
- A parallel session changed `apps/dsa-web/src/index.css` after initial preflight. This report did not touch it. Rendered evidence therefore reflects the current dirty working tree, and future deletion work should rerun from a clean CSS state or explicitly account for the parallel CSS diff.

## 3. Static Baseline

| Check | Result | Key output |
| --- | --- | --- |
| `npm run check:design` | PASS | 216 files scanned; 0 blocking violations; 0 warnings |
| `npm run lint` | PASS | `eslint .` exited 0 |
| `npm run build` | PASS with warning | 3160 modules transformed; Vite chunk-size warning for `DeterministicBacktestChartWorkspace-DO77CKKt.js` at 532.42 kB |
| `python3 -m compileall -q src api` | PASS | exited 0 with no output |
| Markdown lint | Not run | no markdown lint script found; only `remark-gfm` dependency reference was found |
| `./scripts/ci_gate.sh` | Not run | report-only docs task; no product code, tests, CSS, backend/API, package, config, or runtime changes |

Parallel state after preflight:

```text
 M apps/dsa-web/src/index.css
```

The dirty CSS diff was inspected enough to identify it as unrelated parallel selector deletion work. It removed `workspace-page--chat` blocks, not `stealth-scrollbar`; this task did not edit, stage, or revert it.

## 4. Static Ownership Evidence

| Selector/class | Static owner evidence | Current ownership interpretation |
| --- | --- | --- |
| `stealth-scrollbar` | `src/index.css` defines it together with `custom-scrollbar`; production TSX search found no class owner. Market Overview tests assert primary rails do not have `stealth-scrollbar`. | CSS-only / test-negative evidence; possible legacy utility. |
| `no-scrollbar` | Broad active usage across pages/components. Examples: Chat message/code/console panels, Scanner scroll regions/tables, Watchlist table, Backtest rails, Settings main panel, Admin Logs tab/table shells, Portfolio sections, report details/tables, Drawer. | Active hidden-scrollbar owner. |
| `custom-scrollbar` | `components/common/ScrollArea.tsx` uses `custom-scrollbar no-scrollbar` on its viewport. | Active shared component utility; do not delete without `ScrollArea` migration. |
| `overflow-y-auto` | Active in Chat, Scanner, Settings/System, Market Overview cards, Admin Logs, Portfolio, report details, common Drawer/ScrollArea, and backtest workspace. | Route-local vertical scroll owner. |
| `overflow-auto` | Active in Admin raw log `<pre>` and Backtest result ledger table. | Active local two-axis scroll owner. |
| `overflow-hidden` | Active as shell/card clipping and page-frame guard across Chat, PreviewShell, Market Overview, Portfolio/Admin cards, report/backtest components. | Not a scrollbar owner by itself; often establishes contained layout/clipping. |
| native/page scroll | Several rendered containers scroll via computed CSS from shell/page classes, not literal Tailwind tokens. | Active route scroll behavior; must be checked in DOM, not source search alone. |

Route-specific static notes:

- Chat: message/code blocks and console panels use `overflow-y-auto` or `overflow-x-auto` with `no-scrollbar`; root uses `overflow-hidden`.
- Scanner: candidate/history/table regions use `overflow-y-auto` or `overflow-x-auto` with `no-scrollbar`; previous corrected Scanner audit proved shell selectors active and `stealth-scrollbar` absent.
- Watchlist: table shell uses `overflow-x-auto no-scrollbar`.
- Backtest: top action rails use `overflow-x-auto no-scrollbar`; pro workspace and result report components use vertical and two-axis scroll utilities.
- Market Overview: dense quote/card rails use `overflow-y-auto no-scrollbar ui-scroll-y-quiet`; tests explicitly reject old `stealth-scrollbar` rails.
- Portfolio: main/trade/history sections use `overflow-y-auto no-scrollbar` plus explicit arbitrary scrollbar-hidden utilities.
- Settings/System: `settings-main-panel` uses `overflow-y-auto no-scrollbar` plus explicit scrollbar-hidden utilities.
- Admin Logs: tab rail, raw-log table shell, and log lists use `no-scrollbar`; raw log `<pre>` uses `overflow-auto no-scrollbar`.
- Admin Notifications: static source mostly uses `overflow-hidden` card clipping and native/page scroll.
- Preview/report: report details and tables use `no-scrollbar`; preview shell/page uses page-level computed scroll.

## 5. Rendered Scroll-Container Matrix

Counts are exact DOM class hits or class-token hits collected after route load. `Delta` is `document.documentElement.scrollWidth - document.documentElement.clientWidth`.

| Route | Viewport | Render mode / limitation | `.stealth` | `.no` | `.custom` | `overflow-y-auto` | `overflow-auto` | `overflow-hidden` | Delta | Errors |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `/zh` | `1440x1000` | mock rendered; EventSource fixture warning | 0 | 0 | 0 | 0 | 0 | 4 | 0 | console 1 |
| `/zh/scanner` | `1440x1000` | mock-shape page error; route proof inconclusive | 0 | 0 | 0 | 0 | 0 | 0 | 0 | page 1 |
| `/zh/watchlist` | `1440x1000` | mock rendered | 0 | 1 | 0 | 0 | 0 | 0 | 0 | none |
| `/zh/backtest` | `1440x1000` | mock rendered | 0 | 2 | 0 | 0 | 0 | 0 | 0 | none |
| `/zh/backtest/results/1` | `1440x1000` | mock rendered | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none |
| `/zh/portfolio` | `1440x1000` | mock-shape page error; route proof inconclusive | 0 | 0 | 0 | 0 | 0 | 0 | 0 | page 1 |
| `/zh/market-overview` | `1440x1000` | mock-shape page error; EventSource warning | 0 | 0 | 0 | 0 | 0 | 0 | 0 | console 1, page 1 |
| `/zh/settings` | `1440x1000` | mock rendered; page/native scroll | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none |
| `/zh/settings/system` | `1440x1000` | mock rendered | 0 | 3 | 0 | 3 | 0 | 5 | 0 | none |
| `/zh/admin/logs` | `1440x1000` | mock rendered | 0 | 2 | 0 | 1 | 0 | 2 | 0 | none |
| `/zh/admin/notifications` | `1440x1000` | mock rendered; page/native scroll | 0 | 0 | 0 | 0 | 0 | 2 | 0 | none |
| `/zh/chat` | `1440x1000` | mock rendered | 0 | 3 | 0 | 3 | 0 | 4 | 0 | none |
| `/zh/__preview/report` | `1440x1000` | mock rendered; page/native scroll | 0 | 0 | 0 | 0 | 0 | 8 | 0 | none |
| `/zh` | `390x844` | mock rendered; EventSource fixture warning | 0 | 0 | 0 | 0 | 0 | 4 | 0 | console 1 |
| `/zh/scanner` | `390x844` | mock-shape page error; route proof inconclusive | 0 | 0 | 0 | 0 | 0 | 0 | 0 | page 1 |
| `/zh/watchlist` | `390x844` | mock rendered | 0 | 1 | 0 | 0 | 0 | 0 | 0 | none |
| `/zh/backtest` | `390x844` | mock rendered | 0 | 2 | 0 | 0 | 0 | 0 | 0 | none |
| `/zh/backtest/results/1` | `390x844` | mock rendered; page/native scroll | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none |
| `/zh/portfolio` | `390x844` | mock-shape page error; route proof inconclusive | 0 | 0 | 0 | 0 | 0 | 0 | 0 | page 1 |
| `/zh/market-overview` | `390x844` | mock-shape page error; EventSource warning | 0 | 0 | 0 | 0 | 0 | 0 | 0 | console 1, page 1 |
| `/zh/settings` | `390x844` | mock rendered; page/native scroll | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none |
| `/zh/settings/system` | `390x844` | mock rendered | 0 | 3 | 0 | 3 | 0 | 5 | 0 | none |
| `/zh/admin/logs` | `390x844` | mock rendered | 0 | 2 | 0 | 1 | 0 | 2 | 0 | none |
| `/zh/admin/notifications` | `390x844` | mock rendered; page/native scroll | 0 | 0 | 0 | 0 | 0 | 2 | 0 | none |
| `/zh/chat` | `390x844` | mock rendered | 0 | 3 | 0 | 3 | 0 | 4 | 0 | none |
| `/zh/__preview/report` | `390x844` | mock rendered; page/native scroll | 0 | 0 | 0 | 0 | 0 | 8 | 0 | none |

Top scroll-container highlights:

| Route | Viewport | Leading scrollable evidence |
| --- | --- | --- |
| `/zh` | desktop | Home decision card horizontal internal delta `42`; no document overflow. |
| `/zh` | mobile | `theme-page-transition ... h-full` computed `hidden/auto`, `323x710 -> 431x1653`; document delta 0 despite internal width deltas. |
| `/zh/watchlist` | desktop | table shell `overflow-x-auto no-scrollbar`, `1201x95 -> 1420x95`. |
| `/zh/watchlist` | mobile | table shell `overflow-x-auto no-scrollbar`, `260x95 -> 1420x95`; page container computed `hidden/auto`, `323x710 -> 323x1429`. |
| `/zh/backtest` | desktop | only `sr-only` measurable overflow after load; action rails still counted as `no-scrollbar=2`. |
| `/zh/backtest` | mobile | `theme-page-transition ... h-full` computed `hidden/auto`, `306x710 -> 306x1414`; `backtest-bento-page` content taller than viewport. |
| `/zh/backtest/results/1` | mobile | `deterministic-backtest-result-page ... workspace-page--backtest`, computed `hidden/auto`, `303x710 -> 303x966`. |
| `/zh/settings` | desktop | `theme-page-transition ... h-full`, computed `hidden/auto`, `1298x855 -> 1298x911`. |
| `/zh/settings` | mobile | `theme-page-transition ... h-full`, computed `hidden/auto`, `323x710 -> 323x1826`. |
| `/zh/settings/system` | desktop | `settings-main-panel` `overflow-y-auto no-scrollbar ... [&::-webkit-scrollbar]:hidden`, `1011x918 -> 1011x1730`; `pre` `overflow-y-auto no-scrollbar`, `792x224 -> 792x511`. |
| `/zh/settings/system` | mobile | `settings-main-panel`, `316x457 -> 316x3638`; `pre` `212x224 -> 212x546`. |
| `/zh/admin/logs` | mobile | `admin-logs-workspace ... overflow-x-hidden`, computed `hidden/auto`, `320x710 -> 320x1280`; tab rail `overflow-x-auto no-scrollbar`, `290x34 -> 497x34`. |
| `/zh/admin/notifications` | mobile | `admin-notifications-workspace ... overflow-x-hidden`, computed `hidden/auto`, `365x773 -> 365x1214`. |
| `/zh/chat` | desktop | console panel child `overflow-y-auto no-scrollbar pr-1`, `324x769 -> 324x908`. |
| `/zh/__preview/report` | desktop | `preview-report-page workspace-page--preview`, computed `hidden/auto`, `1380x918 -> 1380x2134`. |
| `/zh/__preview/report` | mobile | `preview-report-page workspace-page--preview`, `362x771 -> 362x3503`; `theme-chart-toolbar-track`, `161x46 -> 374x46`. |

The raw collector kept up to 10 scrollable containers per route/viewport in `/tmp/wolfystock_scrollbar_dom_results.json`; that file was not committed.

## 6. Selector Conclusions

### `stealth-scrollbar`

Classification: **DOM absent and deletion-trial candidate**.

Evidence:

- Rendered count was 0 on every collected route/viewport row.
- Required static search found CSS definitions but no production TSX owner.
- Existing tests contain negative evidence for old Market Overview rails.

Decision:

- Good candidate for a future tightly scoped deletion trial.
- Do not delete from this report alone because route-wide scroll proof is still limited by Scanner/Portfolio/Market Overview mock errors and the parallel dirty CSS state.

### `no-scrollbar`

Classification: **active owner**.

Evidence:

- Static source usage is broad and route-specific.
- Rendered DOM hits appeared on Watchlist, Backtest, Settings/System, Admin Logs, and Chat in this matrix.
- Prior corrected Scanner and Chat DOM reports also show active `no-scrollbar` ownership on their full route states.

Decision:

- Do not delete.
- Treat as the primary current hidden-scrollbar utility.

### `custom-scrollbar`

Classification: **active owner, but shared-component scoped**.

Evidence:

- Static owner is `components/common/ScrollArea.tsx`.
- It is paired with `no-scrollbar` and `overflow-y-auto`.
- Rendered count was 0 in this default route matrix, which only means no visible default route state emitted `ScrollArea` during the collector.

Decision:

- Do not delete without a deliberate `ScrollArea` owner migration and consumer proof.

### Route-local overflow classes

Classification: **active owner**.

Evidence:

- `overflow-y-auto`, `overflow-x-auto`, `overflow-auto`, and `overflow-hidden` are active in route files and rendered containers.
- Several route scroll owners are page/shell containers with computed `overflow: hidden/auto`, so class-token search alone is insufficient.

Decision:

- Preserve route-local overflow ownership.
- Future deletion work must inspect rendered dimensions and computed overflow, not just class names.

## 7. Recommended Next Tasks

1. Run a clean-state deletion trial for `stealth-scrollbar` only after `apps/dsa-web/src/index.css` is no longer dirty from the parallel task.
2. Before deleting, rerun the same route matrix and include corrected/live proof for Scanner, Portfolio, and Market Overview.
3. Add a focused `ScrollArea` owner inventory before any `custom-scrollbar` change.
4. Keep `no-scrollbar` as the current canonical hidden-scrollbar utility unless a broader utility migration is explicitly scoped.
5. For route scroll-state proof, prioritize Scanner table/history/candidate states, Portfolio populated holdings/history states, Market Overview dense cards/provider states, Backtest result report/ledger states, and Admin Logs raw table/list states.

Routes needing stronger scroll-state proof before any `stealth-scrollbar` deletion:

- `/zh/scanner`: route-wide collector hit `Cannot read properties of undefined (reading 'map')`; use the corrected scanner mock from the scanner DOM verification pattern and include table/history/candidate-list states.
- `/zh/portfolio`: collector hit `J.map is not a function`; use populated holdings/trades/events mocks or live safe read-only data.
- `/zh/market-overview`: collector hit `Cannot read properties of undefined (reading 'overall')`; use corrected market overview data contracts and stream mocks.
- `/zh/backtest/results/1`: current collector rendered without errors, but default result state did not emit result-report scroll utilities; include populated report/ledger/audit panels.
- `/zh/admin/logs`: current collector rendered; stronger proof should include enough rows to activate list/table vertical scrolling.

## 8. Non-Goals

- No CSS deletion.
- No product code edits.
- No test edits.
- No backend/API edits.
- No package/config/runtime edits.
- No `docs/CHANGELOG.md` edit.
- No generated screenshot, video, trace, Playwright report, build output, sourcemap, coverage, DuckDB file, or temp file committed.
- No claim that `stealth-scrollbar` is safe to delete without a future deletion trial.

## 9. Appendix

Commands/results:

```bash
cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
npm run check:design
# PASS: 216 files scanned, 0 blocking violations, 0 warnings

npm run lint
# PASS: eslint exited 0

npm run build
# PASS with existing Vite chunk-size warning for DeterministicBacktestChartWorkspace

cd /Users/yehengli/daily_stock_analysis
python3 -m compileall -q src api
# PASS: exited 0
```

Validation commands required after writing this report:

```bash
cd /Users/yehengli/daily_stock_analysis
sed -n '1,380p' docs/audits/archive/frontend/wolfystock-scrollbar-dom-verification.md
git diff --check -- docs/audits/archive/frontend/wolfystock-scrollbar-dom-verification.md
```

Rollback for this report:

```bash
git revert <commit>
```
