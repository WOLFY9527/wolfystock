# WolfyStock Product Command Card Owner Audit

Date: 2026-05-05 Asia/Shanghai
Repository: `/Users/yehengli/daily_stock_analysis`
Branch: `main`
Mode: read-only ownership report; no product code, tests, CSS, backend/API, package, config, runtime, or changelog changes

## 1. Executive Summary

Ownership verdict: **CSS-only orphan but high-risk**.

`product-command-card` has **zero production source hits outside `apps/dsa-web/src/index.css`** in the current `main` checkout. Prior rendered DOM audits also found **0 rendered hits** across required routes, and the corrected scanner DOM pass found **0 scanner hits** at desktop and mobile. Current static evidence still does not make deletion safe, because the selector appears in multiple global product, SpaceX theme, mobile, and Backtest override layers.

Current owner hypothesis: it was a **legacy product command/card primitive for older product and Backtest command surfaces**, now apparently replaced in source by `product-section-card`, `summary-block`, `preview-card`, `metric-card`, `product-command-input`, common backtest workspaces, and Tailwind/common component surfaces. Backtest remains the most likely historical owner because the late CSS contains Backtest rail, Backtest workspace, and mobile overrides targeting this selector.

Deletion safety now: **No**. Do not delete it directly from this audit. A future deletion trial may be reasonable, but only after a dedicated one-family CSS trial proves no rendered DOM usage and no visual/cascade dependency on Backtest entry, Backtest results, preview report, Scanner, Watchlist, and Home command/workbench states.

Recommended next action: create a future **single-selector deletion trial for `product-command-card` only**, after route-level Playwright or browser proof at `1440x1000` and `390x844` for `/zh/backtest`, `/zh/backtest/results/1`, `/zh/__preview/report`, `/zh/scanner`, `/zh/watchlist`, and `/zh`.

## 2. Methodology

Commands run before inspection:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -110
./scripts/task_preflight.sh || true
```

Mandatory files inspected:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/checks/css-visual-regression-checklist.md`
- `docs/audits/wolfystock-css-dom-verification-pass1.md`
- `docs/audits/wolfystock-scanner-dom-verification.md`
- `docs/audits/wolfystock-css-selector-usage-verification.md`
- `docs/audits/wolfystock-css-ownership-inventory.md`
- `docs/audits/wolfystock-frontend-design-conformance-audit.md`
- `docs/design/wolfystock-canonical-ui-primitives.md`
- `docs/operations/parallel-codex-playbook.md`

Static investigation commands:

```bash
cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
rg -n "product-command-card" src/index.css src --glob '!index.css'
rg -n "command card|command-card|CommandCard|product command|ProductCommand|command panel|command bar|CommandBar|product-command|product card|action card|trade command|执行|命令|操作" src/pages src/components src/utils src/__tests__ | head -500
rg -n "product-command-card|backtest-entry-shell|workspace-page--chat|stealth-scrollbar|backtest-result-bento|backtest-void-workspace|gemini-bento-page|home-panel-card|home-subpanel|chart-card|comparison-card" src/index.css | head -260
rg -n "product-command-card" src/index.css
sed -n '3970,4055p' src/index.css
sed -n '5940,6225p' src/index.css
sed -n '6435,6495p' src/index.css
sed -n '8100,8295p' src/index.css
sed -n '9020,9095p' src/index.css
sed -n '15970,16020p' src/index.css
rg -n "product-command-input|product-section-card|summary-block|preview-card|metric-card|product-module-switch|backtest-workbench|pro-execution-rail|backtest-control-rail|product-disclosure" src/components src/pages src/__tests__ | head -500
rg -n "product-command-card" src --glob '!index.css' --glob '**/*.{tsx,ts}' || true
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

Limitations:

- This task did not run Playwright. Prior DOM evidence was read and summarized, but no new browser route proof was created in this pass.
- This report is static ownership documentation plus baseline checks. It does not approve deletion.
- After the clean preflight and baseline commands, unrelated dirty files appeared in the worktree. They were not touched, staged, reverted, formatted, or committed by this task.
- Full `./scripts/ci_gate.sh` was not run because this is report-only documentation and the requested validation matrix did not require full CI when product code, CSS, tests, backend/API, package, and config files are unchanged.

## 3. Static Selector Evidence

| CSS location | Surrounding ownership block | Likely surface | Cascade risk | Adjacent selectors | Notes |
| --- | --- | --- | --- | --- | --- |
| `apps/dsa-web/src/index.css:4019` | Theme-family product/report/chart primitive block near `report-empty-state`, `product-empty-state`, `product-command-row`, `product-action-row`, `product-field-grid`, and `chart-card__footer` | Shared product command primitive | Medium/high | `product-empty-state`, `product-command-row`, `product-action-row`, `summary-block__header`, `chart-card__footer` | Base rule only sets grid layout and gap, but it sits in shared product primitives. |
| `apps/dsa-web/src/index.css:5977` | Global SpaceX/theme surface reset with shell, panel, product, metric, preview, summary, and loading panels | Shared deep-space surface material | High | `theme-sidebar-shell`, `theme-panel-solid`, `theme-panel-glass`, `product-section-card`, `metric-card`, `preview-card`, `summary-block`, `workspace-header-panel` | Selector participates in a broad material reset. Deleting it changes nothing if DOM stays absent, but this block shows it was treated as a product surface peer. |
| `apps/dsa-web/src/index.css:6196` | Backtest workbench shell/rail block | Backtest workbench rail | High | `backtest-workbench-rail`, `backtest-workbench-nav-list`, `backtest-workbench-nav-item` | Modifier `product-command-card--backtest-workbench-rail` has no current source hit, but the name points to historical Backtest command rail ownership. |
| `apps/dsa-web/src/index.css:6465` | `backtest-control-rail` shared card/input normalization | Backtest control rail | High | `product-section-card`, `summary-block`, `metric-card`, `preview-card`, `chart-card`, `backtest-normal-step` | Even absent DOM hits are risky here because this block normalizes card height, background, border, radius, and input controls inside Backtest. |
| `apps/dsa-web/src/index.css:8134` | SpaceX product/backtest surface base | Shared product and Backtest surface | High | `product-section-card`, `workspace-page--backtest`, `product-banner`, `product-disclosure`, `wizard-step` | This is the main material definition for `product-command-card` and `product-section-card`. Current source uses the latter heavily. |
| `apps/dsa-web/src/index.css:8147` | Backtest workspace transition group | Backtest route | High | `product-section-card`, `summary-block`, `metric-card`, `preview-card`, `chart-card`, `product-banner`, `product-module-switch__button`, `wizard-step` | Backtest cascade adjacency means Scanner absence alone cannot prove safety. |
| `apps/dsa-web/src/index.css:8166` | Backtest width and padding override | Backtest route | High | `product-section-card`, `workspace-header-copy` | Controls full-width behavior for command/section cards inside Backtest. |
| `apps/dsa-web/src/index.css:8178` | Backtest command/flow material override | Backtest route | High | `product-section-card--backtest-flow`, `product-section-card--backtest-standard`, `product-section-card--backtest-result`, `product-section-card--backtest-secondary` | Strong evidence of historical Backtest command card ownership. Active replacements are section-card variants. |
| `apps/dsa-web/src/index.css:8264` | Desktop wide media override | Backtest desktop layout | Medium/high | `product-section-card` | Padding changes at `min-width: 1280px`; deletion must be checked at desktop width. |
| `apps/dsa-web/src/index.css:8276` | Extra-wide media override | Backtest extra-wide layout | Medium/high | `product-section-card` | Extra-wide padding still implies route-sensitive cascade. |
| `apps/dsa-web/src/index.css:9049` | Mobile workspace/card radius override | Mobile shared workspace | Medium/high | `workspace-header-panel`, `product-section-card`, `theme-panel-solid`, `theme-panel-glass` | Required mobile deletion proof because the selector shares mobile radius with route panels. |
| `apps/dsa-web/src/index.css:9076` | Mobile workspace/card padding override | Mobile shared workspace | Medium/high | `workspace-header-panel`, `product-section-card` | Required mobile deletion proof because command-card padding would change if a dynamic DOM path exists. |
| `apps/dsa-web/src/index.css:16003` | Dense dashboard / late deep-space compact reset | Shared dense/product material | High | `theme-panel-solid`, `theme-panel-glass`, `settings-surface`, `theme-card-surface`, `product-section-card`, `metric-card`, `preview-card`, `summary-block`, `product-disclosure` | Late cascade layer is broad and authoritative. Treat deletion as high risk until proven route-by-route. |

## 4. Source Search Evidence

Production source hits:

- `rg -n "product-command-card" src --glob '!index.css' --glob '**/*.{tsx,ts}' || true` returned no hits.
- `rg -n "product-command-card" src/index.css src --glob '!index.css'` returned CSS hits only in `src/index.css`.

Test hits:

- No direct test hits for `product-command-card` were found.
- Backtest tests target current execution surfaces such as `pro-execution-rail`, buttons named `执行回测任务`, and existing Backtest route behavior, not the `product-command-card` class.

Command/card related components that may have replaced it:

- `product-section-card` is active in `DeterministicBacktestResultPage.tsx`, `RuleBacktestComparePage.tsx`, `ExecutionTracePanel.tsx`, `DeterministicBacktestResultView.tsx`, `BacktestAuditTables.tsx`, `BacktestOverviewSummary.tsx`, and `HistoricalEvaluationPanel.tsx`.
- `summary-block`, `preview-card`, and `metric-card` are active across deterministic Backtest flow/result/report components.
- `product-command-input` is active in `StockAutocomplete.tsx` and `DeterministicBacktestFlow.tsx`, indicating that the input part of the product command family still exists while the card wrapper does not.
- `product-disclosure` is active through `components/common/Disclosure.tsx`.
- Backtest workspaces now use explicit route/workspace primitives such as `backtest-workbench-*`, `pro-execution-rail`, `backtest-control-rail`, `product-section-card--backtest-*`, `backtest-result-bento`, and `backtest-void-workspace`.

Likely historical owner:

- **Backtest command/workbench surfaces** are the strongest historical owner because the selector appears in Backtest rail, Backtest workspace, desktop, mobile, and late dense-reset layers.
- A secondary historical owner is the older shared **product command primitive** layer, where it sits with `product-command-row`, `product-action-row`, `product-field-grid`, and `product-field`.

## 5. Ownership Hypothesis

Classification: **CSS-only orphan but high-risk**.

Evidence:

- Static source has no current production/test class usage outside CSS.
- Prior DOM reports found 0 rendered hits and still classified the selector as high-risk.
- Current CSS places it beside active product primitives and active Backtest/report/card primitives.
- Current source appears to have migrated rendered surfaces to `product-section-card`, `summary-block`, `preview-card`, `metric-card`, `product-command-input`, Backtest workbench classes, and common components.
- The cascade does not isolate `product-command-card` in one old block. It appears in broad reset and late override layers where deletion must be proven by rendered DOM and visual checks.

This makes the selector neither an active owner nor a low-risk dead selector. It is probably an orphaned legacy product command wrapper whose owner migrated to canonical or semi-canonical Backtest/product primitives, but the migration is not documented enough to delete safely in a report-only task.

## 6. Risk Assessment

Cascade adjacency:

- The selector is grouped with active shared surfaces: `product-section-card`, `metric-card`, `preview-card`, `summary-block`, `product-disclosure`, `workspace-header-panel`, `settings-surface`, and Backtest-specific card variants.
- It appears in both early/base product primitives and late SpaceX/deep-space overrides. Cascade order is part of the behavior in `src/index.css`.
- A direct deletion may be a no-op if DOM remains absent, but a dynamic class path would lose layout, border, background, radius, padding, transition, and mobile behavior.

Product/backtest/report ownership:

- Backtest is the likely historical owner because of `backtest-control-rail`, `workspace-page--backtest`, and `product-command-card--backtest-workbench-rail`.
- Report/preview risk exists because the selector is grouped with `preview-card`, `summary-block`, and chart/report primitives in broad product material resets.
- Product command input remains active, so the product command family is not entirely dead.

Route visual risk:

- `/zh/backtest` must be verified in setup, professional, and normal/deterministic command states.
- `/zh/backtest/results/1` must be verified for result cards, bento, void/chart workspace, details, and assumptions.
- `/zh/__preview/report` must be verified because report/preview primitives are adjacent in the cascade.
- `/zh/scanner`, `/zh/watchlist`, and `/zh` must be verified because command/action surfaces can be product-shaped even without direct source hits.
- Mobile `390x844` is required because mobile-specific `product-command-card` radius and padding overrides exist.

Why scanner absence is insufficient:

- The corrected scanner DOM pass found 0 `product-command-card` hits, but scanner is not the likely owner. The strongest CSS ownership evidence points to Backtest and shared product primitives.
- Scanner command areas use current route-local and shell classes; that does not prove older Backtest command wrappers are gone in every data/mode state.

Why static CSS-only evidence is not enough alone:

- Prior CSS audits explicitly warn that CSS-only selectors can still be emitted dynamically or be tied to route states that static search misses.
- `product-command-card` appears in broad selector groups. Removing one selector from a group requires proving that no current DOM or future route state depends on it.
- CSS deletion requires visual proof, because a zero source hit does not prove no cascade or runtime class dependency exists.

## 7. Recommended Future Tasks

Future deletion trial:

- Run a future deletion trial only for `product-command-card` and its direct modifier `product-command-card--backtest-workbench-rail`.
- Do not combine it with Backtest redesign, Scanner work, report preview alignment, shared primitive extraction, package/config changes, or other CSS cleanup.

Required preconditions before deletion:

- Clean or well-categorized worktree with no unrelated dirty `apps/dsa-web/src/index.css`.
- Source search still shows no non-CSS class usage.
- Rendered DOM queries show 0 hits for `.product-command-card` and `[class*="product-command-card"]`.
- Visual checks confirm no card hierarchy, ghost-glass, padding, radius, input, command rail, or mobile overflow regression.
- Rollback plan is explicit: restore only the removed selector family from the previous commit and rerun the same route matrix.

Routes that must be verified:

- `/zh/backtest`
- `/zh/backtest/results/1`
- `/zh/__preview/report`
- `/zh/scanner`
- `/zh/watchlist`
- `/zh`
- Add `/zh/market-overview` and `/zh/portfolio` if the future trial touches adjacent product/card groups or if route search finds command/card-like wrappers.

Owner migration doc:

- Add a short note to a CSS selector/primitive governance document before or inside the deletion trial stating that current command surfaces are owned by `product-section-card`, `summary-block`, `preview-card`, `metric-card`, common `Button/Input/Select/Disclosure`, and Backtest route-specific workspaces.
- If Backtest still needs a command wrapper, define a current owner name before deleting the legacy selector.

Required tests/checks:

- `cd apps/dsa-web && npm run check:design`
- `cd apps/dsa-web && npm run lint`
- `cd apps/dsa-web && npm run build`
- Relevant Backtest page/result tests if CSS deletion changes snapshots or class-dependent assertions.
- Route-level Playwright or browser DOM/visual checks at `1440x1000` and `390x844`.
- `git diff --check -- apps/dsa-web/src/index.css`
- Full `./scripts/ci_gate.sh` only if the future task changes product code or the CSS deletion has broad shared behavior risk that cannot be covered by targeted frontend checks.

## 8. Non-Goals

- No CSS changed.
- No product code changed.
- No tests changed.
- No selector deletion approved directly.
- No backend/API code changed.
- No package, config, script, runtime, or `docs/CHANGELOG.md` changes.
- No generated artifacts committed.
- No unrelated dirty files staged, reverted, formatted, or committed.

## 9. Appendix

Preflight summary:

```text
pwd: /Users/yehengli/daily_stock_analysis
branch: main
git status --short: clean at task start
git status --branch --short: ## main...origin/main
task_preflight: branch main, upstream origin/main ahead 0 / behind 0, dirty files 0
```

Recent relevant commits observed in `git log --oneline -110`:

```text
96503cf chore(css): remove unused gradient border card selectors
0f0325d chore(css): remove unused dashboard card selectors
338566e chore(css): remove unused terminal card selectors
543d6cb chore(css): remove unused glass card selectors
2e97b39 docs: verify scanner dom shell classes
89933dc docs: verify css selector dom usage
74afcb4 docs: add css visual regression checklist
3f68c7c docs: define canonical ui primitives
6cfa4fe docs: audit frontend design conformance
21b6a3b docs: add css ownership inventory
```

Current `product-command-card` CSS locations:

```text
src/index.css:4019:.product-command-card {
src/index.css:5977:.product-command-card,
src/index.css:6196:.product-command-card--backtest-workbench-rail {
src/index.css:6465:.backtest-control-rail .product-command-card,
src/index.css:8134:.product-command-card,
src/index.css:8147:.workspace-page--backtest .product-command-card,
src/index.css:8166:.workspace-page--backtest .product-command-card,
src/index.css:8178:.workspace-page--backtest .product-command-card,
src/index.css:8264:  .workspace-page--backtest .product-command-card,
src/index.css:8276:  .workspace-page--backtest .product-command-card,
src/index.css:9049:  .product-command-card,
src/index.css:9076:  .product-command-card,
src/index.css:16003:  .product-command-card,
```

Current direct source result:

```text
rg -n "product-command-card" src --glob '!index.css' --glob '**/*.{tsx,ts}' || true
# no output
```

Baseline output summary:

```text
npm run check:design
Files scanned: 216
Design guard passed. No blocking violations or warnings found.

npm run lint
eslint . exited 0

npm run build
3160 modules transformed
CSS asset: ../../static/assets/index-BMuUt6Jr.css 517.43 kB / gzip 73.76 kB
Large chunk warning: DeterministicBacktestChartWorkspace-D7_48C9e.js 532.42 kB / gzip 178.83 kB
built in 8.75s

python3 -m compileall -q src api
exited 0 with no output
```

Markdown lint status:

```text
No markdown lint script was found.
Search found remark package/docs references, but no runnable markdown lint command.
```

Parallel dirty-file note after baseline:

```text
 M apps/dsa-web/src/pages/BacktestPage.tsx
 M apps/dsa-web/src/pages/DeterministicBacktestResultPage.tsx
?? docs/operations/duckdb-production-readiness-checklist.md
```

These files are unrelated to this audit and were not touched, staged, reverted, formatted, or committed by this task.
