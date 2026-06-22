# WolfyStock Backtest DOM Verification

Date: 2026-05-05 Asia/Shanghai
Repository: `/Users/yehengli/daily_stock_analysis`
Branch: `main`
Mode: read-only Backtest DOM verification report; no product code, tests, CSS, backend/API, package, config, runtime, or changelog changes by this task

## 1. Executive Summary

Verdict: `backtest-entry-shell` is **absent as a rendered class** in corrected Backtest entry and result DOM evidence.

The corrected Playwright pass rendered `/zh/backtest` in normal and professional entry states and `/zh/backtest/results/1` in completed deterministic result state at both required viewports:

- Desktop: `1440x1000`
- Mobile: `390x844`

Primary answers:

| Question | Answer |
| --- | --- |
| Does `/zh/backtest` render full Backtest entry/workspace content under corrected mocks? | Yes. Normal entry rendered `normal-backtest-workspace` / `normal-backtest-consolidated-card`; professional entry rendered `pro-backtest-workspace`, workflow rail, step workspace, execution summary, and history drawer content. |
| Does `/zh/backtest/results/1` render full deterministic result content under corrected mocks? | Yes. Completed result rendered the result hero, KPI bento, report, chart workspace, audit/detail sections, tabs, and deterministic dashboard. |
| Is `backtest-entry-shell` present or absent? | Absent as a class in every rendered row. Static source has `data-testid="backtest-entry-shell"` in `DeterministicBacktestFlow.tsx`, but no class usage outside CSS. The current route did not emit that test id either. |
| Which current shell/card/workbench classes own Backtest? | Entry route currently uses `backtest-bento-page`, `backtest-subnav`, `backtest-v1-page`, `backtest-v1-stage`, `normal-backtest-workspace`, `normal-backtest-consolidated-card`, `normal-backtest-form-grid`, and professional `pro-*` test ids/classes mostly expressed through Tailwind. Result route uses `workspace-page--backtest`, `backtest-result-page`, `backtest-result-bento`, `backtest-void-workspace`, `product-section-card`, `summary-block`, `preview-card`, and `metric-card`. |
| Can `backtest-entry-shell` become a future deletion-trial candidate? | Yes, as a focused future deletion-trial candidate for the CSS selector family only. Do not delete it from this report-only audit. Preserve the `data-testid` question separately if tests or old components still rely on it. |

No page errors, console errors, horizontal overflow, raw/debug/provider/schema/token/API-key leakage, or production calculation calls were observed in the corrected Backtest Playwright pass.

Important parallel-work note: preflight started clean, but after baseline checks a parallel change appeared in `apps/dsa-web/src/index.css`. This task did not touch, stage, revert, or inspect that diff beyond `git status --short` / `git diff --stat`. Because CSS was dirty from another task, this report does not claim any CSS file state beyond static reads performed before report writing.

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

Preflight result:

| Check | Result |
| --- | --- |
| `pwd` | `/Users/yehengli/daily_stock_analysis` |
| Branch | `main` |
| Initial `git status --short` | clean |
| Initial upstream | `origin/main`, ahead 0 / behind 0 |
| `task_preflight` | branch `main`; dirty files 0 |

Mandatory reading completed:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/checks/css-visual-regression-checklist.md`
- `docs/audits/archive/frontend/wolfystock-css-cleanup-closure-report.md`
- `docs/audits/archive/frontend/wolfystock-product-command-card-owner-audit.md`
- `docs/audits/wolfystock-frontend-design-conformance-audit.md`
- `docs/design/wolfystock-canonical-ui-primitives.md`
- `docs/operations/parallel-codex-playbook.md`
- `docs/checks/design-guard.md`

Static investigation commands:

```bash
cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
rg -n "backtest-entry-shell|BacktestPage|DeterministicBacktestResultPage|backtest-result-bento|backtest-void-workspace|product-section-card|summary-block|preview-card|metric-card|backtest-workbench|pro-execution-rail|backtest-control-rail|theme-chart-tab|theme-chart-legend-item" src/index.css src/pages src/components src/__tests__ | head -700
rg -n "backtest-entry-shell|glass-card|terminal-card|dashboard-card|gradient-border-card|product-command-card|workspace-page--chat|stealth-scrollbar" src/index.css src --glob '!index.css' | head -400
```

Files inspected:

- `apps/dsa-web/src/pages/BacktestPage.tsx`
- `apps/dsa-web/src/pages/DeterministicBacktestResultPage.tsx`
- `apps/dsa-web/src/components/backtest/*`
- `apps/dsa-web/src/pages/__tests__/BacktestPage.test.tsx`
- `apps/dsa-web/src/pages/__tests__/DeterministicBacktestResultPage.test.tsx`
- `apps/dsa-web/src/components/backtest/__tests__/*`

Port safety:

| Port | Status/use |
| --- | --- |
| `8000` | Existing Python listener observed; not touched. |
| `8001` | Free in pre-check; not used. |
| `5173` | Existing Node listener observed; not touched. |
| `4173` | Free in pre-check; not used. |
| `5174` | Free in pre-check; not used. |
| `5175` | Free in pre-check; not used. |
| `5176` | Used for isolated `npm run preview -- --host 127.0.0.1 --port 5176`. |

Playwright method:

- Browser: Playwright Chromium from `apps/dsa-web`
- URL: `http://127.0.0.1:5176`
- Frontend server: isolated Vite preview on port `5176`
- Routes: `/zh/backtest`, `/zh/backtest/results/1`
- Entry states: normal default and professional tab state
- Result state: completed deterministic result
- Viewports: `1440x1000`, `390x844`
- Auth/data: corrected contract-faithful route interception for `**/api/v1/**`, based on existing Backtest page/result test shapes
- No heavy jobs were triggered. `POST /api/v1/backtest/rule/run` was mocked if reached, but DOM verification did not need production calculation.
- No backend data was mutated.
- Temporary result JSON: `/tmp/wolfystock_backtest_dom_verification.json`
- No screenshots, videos, traces, Playwright reports, build artifacts, or runtime files were committed.

## 3. Static Baseline

| Check | Result | Key output |
| --- | --- | --- |
| `npm run check:design` | PASS | 216 files scanned; no blocking violations or warnings. |
| `npm run lint` | PASS | `eslint .` exited 0. |
| `npm run build` | PASS with warning | 3160 modules transformed; built in 10.12s. Vite large chunk warning for `DeterministicBacktestChartWorkspace-DO77CKKt.js` at 532.42 kB / gzip 178.84 kB. |
| `python3 -m compileall -q src api` | PASS | exited 0 with no output. |
| Markdown lint | Not available | Search found `remark` package/docs references but no runnable markdown lint script. |
| `./scripts/ci_gate.sh` | Not run | Report-only docs audit; no product code, tests, CSS, backend/API, package, config, scripts, or changelog changes were made by this task. Static frontend/backend baselines were run instead. |

Later worktree note:

```text
 M apps/dsa-web/src/index.css
```

This CSS dirty state appeared after the initial clean preflight and is treated as parallel work. It was not touched by this task.

## 4. Backtest Source/Context Summary

Static source findings:

| Selector or surface | Static evidence | Current interpretation |
| --- | --- | --- |
| `backtest-entry-shell` | CSS rules in `src/index.css`; `DeterministicBacktestFlow.tsx` has `data-testid="backtest-entry-shell"` on a Tailwind/card div; no class usage outside CSS. | CSS selector appears orphaned; test id is a separate non-CSS contract. |
| `/zh/backtest` route | `BacktestPage.tsx` renders `backtest-bento-page`, `backtest-subnav`, `backtest-v1-page`, `backtest-v1-stage`; default rule module chooses `NormalBacktestWorkspace`; professional mode chooses `ProBacktestWorkspace`. | Active entry ownership is the current Normal/Pro workspace DOM, not `.backtest-entry-shell`. |
| Normal entry | `NormalBacktestWorkspace.tsx` renders `normal-backtest-workspace`, `normal-backtest-consolidated-card`, `normal-backtest-form-grid`, `normal-backtest-cta-row`. | Active default entry owner. |
| Professional entry | `ProBacktestWorkspace.tsx` renders `pro-backtest-workspace`, workflow step test ids, `pro-execution-rail` as `data-testid`, and mobile summary test ids. | Active professional owner, but `pro-execution-rail` is not a CSS class in rendered DOM. |
| Result route | `DeterministicBacktestResultPage.tsx` renders root `workspace-page--backtest backtest-result-page`, completed hero `backtest-result-bento`, and result/report stages. | Active deterministic result owner. |
| Chart workspace | `DeterministicBacktestChartWorkspace.tsx` renders `.backtest-void-workspace`. | Active result chart/workspace primitive. |
| Shared result cards | Backtest result/report components render `.product-section-card`, `.summary-block`, `.preview-card`, `.metric-card`. | Active Backtest result/card primitives; not deletion candidates. |
| Removed selector families | `glass-card`, `terminal-card`, `dashboard-card`, `gradient-border-card`, `product-command-card`, `workspace-page--chat`, `stealth-scrollbar` had no rendered hits in this Backtest pass. | Expected absent for this route. |

## 5. Rendered DOM Evidence Matrix

Exact class hit counts:

| Route | Viewport | State | `.backtest-entry-shell` | `.backtest-result-bento` | `.backtest-void-workspace` | `.product-section-card` | `.summary-block` | `.preview-card` | `.metric-card` | `.backtest-workbench` | `.pro-execution-rail` | `.backtest-control-rail` | `.theme-chart-tab` | `.theme-chart-legend-item` | `.glass-card` | `.terminal-card` | `.dashboard-card` | `.gradient-border-card` | `.product-command-card` | `.workspace-page--chat` | `.stealth-scrollbar` | Overflow | Console/page errors |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `/zh/backtest` | `1440x1000` | entry-normal | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 / 0 |
| `/zh/backtest` | `1440x1000` | entry-professional | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 / 0 |
| `/zh/backtest/results/1` | `1440x1000` | result-completed | 0 | 1 | 1 | 1 | 1 | 4 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 / 0 |
| `/zh/backtest` | `390x844` | entry-normal | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 / 0 |
| `/zh/backtest` | `390x844` | entry-professional | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 / 0 |
| `/zh/backtest/results/1` | `390x844` | result-completed | 0 | 1 | 1 | 1 | 1 | 4 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 / 0 |

Route render status:

| Route/state | Render evidence |
| --- | --- |
| `/zh/backtest` entry-normal desktop | Rendered title `回测 - WolfyStock`; test ids included `backtest-bento-page`, `backtest-subnav`, `backtest-v1-page`, `backtest-v1-stage`, `normal-backtest-workspace`, `normal-backtest-consolidated-card`, `normal-backtest-form-grid`, `normal-backtest-cta-row`. |
| `/zh/backtest` entry-normal mobile | Same functional entry content rendered with mobile shell `shell-mobile-active-route`; overflow 0. |
| `/zh/backtest` entry-professional desktop | Rendered `pro-backtest-workspace`, `pro-run-summary-strip`, workflow step ids, `pro-step-workspace`, `pro-step-assets`, `pro-execution-rail`, `pro-execution-readiness`, `pro-mobile-execution-summary`, and history drawer ids. |
| `/zh/backtest` entry-professional mobile | Same professional content rendered under mobile shell; overflow 0. |
| `/zh/backtest/results/1` desktop | Rendered `deterministic-backtest-result-page`, `deterministic-result-page-bento-hero`, `deterministic-result-kpi-bento`, `backtest-result-report`, `deterministic-backtest-result-view`, `deterministic-backtest-chart-workspace`, audit/detail/report sections, and tabs. |
| `/zh/backtest/results/1` mobile | Same completed deterministic result content rendered under mobile shell; overflow 0. |

Substring scans:

| Route | Viewport | State | `backtest` | `workspace` | `result` | `chart` | `trace` | `execution` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/zh/backtest` | `1440x1000` | entry-normal | html yes / text no | html yes / text no | no | no | no | no |
| `/zh/backtest` | `1440x1000` | entry-professional | html yes / text no | html yes / text no | html yes / text yes | no | no | html yes / text yes |
| `/zh/backtest/results/1` | `1440x1000` | result-completed | html yes / text no | html yes / text no | html yes / text no | html yes / text no | html yes / text yes | html yes / text no |
| `/zh/backtest` | `390x844` | entry-normal | html yes / text no | html yes / text no | no | no | no | no |
| `/zh/backtest` | `390x844` | entry-professional | html yes / text no | html yes / text no | html yes / text yes | no | no | html yes / text yes |
| `/zh/backtest/results/1` | `390x844` | result-completed | html yes / text no | html yes / text no | html yes / text no | html yes / text no | html yes / text yes | html yes / text no |

Leakage scan:

- Visible text scan found no default-visible matches for the audit leakage list: `api key`, `apikey`, `secret`, `token`, `schema`, `provider`, `raw`, `debug`, `openai`, `gemini`, `anthropic`.
- Result route exposes normal user-facing execution/audit/report sections, but no secret/token/API-key leakage was visible.

Mock limitations:

- Verification used mocked API responses, not live backend data.
- Current date defaults in the form came from app runtime date logic; no production backtest calculation was executed.
- `pro-execution-rail` was observed as `data-testid`, not as a CSS class; exact class selector count is correctly 0.
- `backtest-entry-shell` was neither a class nor a rendered test id in the current route states. Static source still has a non-class `data-testid` in `DeterministicBacktestFlow.tsx`.

## 6. Selector Conclusions

| Selector | Conclusion |
| --- | --- |
| `backtest-entry-shell` | Rendered class absent across corrected entry/result states. Static source has CSS plus a non-class `data-testid` in `DeterministicBacktestFlow.tsx`. Future CSS deletion trial candidate. |
| `backtest-result-bento` | Active on completed result route: 1 hit at desktop and mobile. Do not delete. |
| `backtest-void-workspace` | Active on completed result route: 1 hit at desktop and mobile. Do not delete. |
| `product-section-card` | Active on completed result route: 1 hit at desktop and mobile. Do not delete. |
| `summary-block` | Active on completed result route: 1 hit at desktop and mobile. Do not delete. |
| `preview-card` | Active on completed result route: 4 hits at desktop and mobile. Do not delete. |
| `metric-card` | Active on completed result route: 6 hits at desktop and mobile. Do not delete. |
| `backtest-workbench` | Absent as exact class in corrected Backtest rows. Static CSS exists for older workbench selectors, but current route did not emit exact `.backtest-workbench`. Candidate only after a separate owner audit; not approved here. |
| `pro-execution-rail` | Absent as exact class; present as `data-testid` in professional entry. Do not treat class absence as component absence. |
| `backtest-control-rail` | Absent as exact class in corrected Backtest rows. CSS appears historical/adjacent; candidate only after separate owner audit. |
| `theme-chart-tab` | Absent in this Backtest route/result pass. It remains active in report chart code and is not a Backtest deletion target here. |
| `theme-chart-legend-item` | Absent in this Backtest route/result pass. It remains active in report chart code and is not a Backtest deletion target here. |
| `glass-card` | Expected absent in this Backtest pass. Already removed selector family remains absent here. |
| `terminal-card` | Expected absent in this Backtest pass. Already removed selector family remains absent here. |
| `dashboard-card` | Expected absent in this Backtest pass. Already removed selector family remains absent here. |
| `gradient-border-card` | Expected absent in this Backtest pass. Already removed selector family remains absent here. |
| `product-command-card` | Expected absent in this Backtest pass. Prior owner audit classified it as CSS-only orphan but high-risk; this pass adds Backtest route absence evidence, not deletion approval. |
| `workspace-page--chat` | Absent in this Backtest pass. Not a Backtest owner. |
| `stealth-scrollbar` | Absent in this Backtest pass. Not enough alone to prove global scrollbar utility deletion safety. |

Overall selector verdict:

- `backtest-entry-shell`: **future deletion-trial candidate** for CSS-only selector family.
- Active Backtest result owners: **keep** `backtest-result-bento`, `backtest-void-workspace`, `product-section-card`, `summary-block`, `preview-card`, and `metric-card`.
- Absent Backtest class selectors with non-class/test-id or cross-route context: do not delete from this report.

## 7. Recommended Next Tasks

1. Run a single-selector CSS deletion trial for `.backtest-entry-shell` and direct `backtest-entry-shell__*` descendants only.
2. Before that deletion trial, confirm `apps/dsa-web/src/index.css` is not dirty from parallel work or explicitly coordinate ownership of the CSS file.
3. In the deletion trial, keep `data-testid="backtest-entry-shell"` out of scope unless tests and current route ownership prove it is also obsolete.
4. Rerun the same Playwright matrix after deletion: `/zh/backtest` normal, `/zh/backtest` professional, and `/zh/backtest/results/1` at `1440x1000` and `390x844`.
5. If auditing older Backtest workbench CSS next, handle `backtest-workbench`, `backtest-control-rail`, and `product-command-card` as separate owner audits or deletion trials; do not bundle them with `backtest-entry-shell`.

## 8. Non-Goals

- No product code changed.
- No tests changed.
- No CSS changed by this task.
- No selectors deleted.
- No backend/API code changed.
- No package/config/script/runtime files changed.
- No `docs/CHANGELOG.md` change.
- No generated screenshots, videos, traces, build output, temp JSON, or Playwright reports committed.
- No unrelated dirty files staged, reverted, formatted, or committed.

## 9. Appendix

Recent relevant commits observed in `git log --oneline -130`:

```text
7e15ee2 fix(report): align preview report shell
aa5950d chore(css): remove unused product command card selectors
a7ff994 fix(ui): improve backtest preview touch targets
2446785 docs: document product command card ownership
3f68c7c docs: define canonical ui primitives
6cfa4fe docs: audit frontend design conformance
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

Markdown lint discovery:

```bash
rg -n "markdownlint|mdlint|remark|lint:md|lint.*markdown" package.json apps/dsa-web/package.json .github scripts docs 2>/dev/null | head -80
```

Validation commands required after writing:

```bash
cd /Users/yehengli/daily_stock_analysis
sed -n '1,380p' docs/audits/archive/frontend/wolfystock-backtest-dom-verification.md
git diff --check -- docs/audits/archive/frontend/wolfystock-backtest-dom-verification.md
```

Rollback for this report commit:

```bash
git revert <commit>
```
