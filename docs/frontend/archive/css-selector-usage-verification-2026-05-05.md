# WolfyStock CSS Selector Usage Verification

Date: 2026-05-05 Asia/Shanghai
Repository: `/Users/yehengli/daily_stock_analysis`
Branch: `main`
Mode: read-only audit/report plus this document; no CSS, product code, tests, package, config, build output, or changelog changes

## 1. Executive Summary

Reviewed **21 selector candidates/prefixes** from the CSS ownership audit and related suspicious global selector families.

Classification summary:

| Classification | Count | Selectors |
| --- | ---: | --- |
| Confirmed used in production source | 10 | `custom-scrollbar`, `theme-market-badge`, `backtest-void-workspace`, `backtest-result-bento`, `gemini-bento-page`, `settings-surface`, `home-panel-card`, `home-subpanel`, `chart-card`, `comparison-card` |
| Likely/confirmed used through shell dynamic composition | 3 | `theme-shell--scanner`, `shell-content-frame--scanner`, `shell-main-column--scanner` |
| Test-only negative reference | 2 | `stealth-scrollbar`, `workspace-page--chat` |
| CSS-only or weak source evidence | 6 | `glass-card`, `terminal-card`, `dashboard-card`, `gradient-border-card`, `backtest-entry-shell`, `product-command-card` |

Strongest cleanup opportunities:

- `glass-card`, `terminal-card`, `dashboard-card`, and `gradient-border-card` have CSS definitions and theme overrides but no source/test class hits outside `src/index.css`.
- `backtest-entry-shell` appears as a `data-testid` in `DeterministicBacktestFlow.tsx`, but no source hit applies the CSS class itself.
- `workspace-page--chat` is explicitly asserted absent in `ChatPage.test.tsx`; the active Chat shell now uses `gemini-bento-page gemini-bento-page--chat`.
- `stealth-scrollbar` has only test-only negative references, while `custom-scrollbar` is active through `ScrollArea`.

What should not be deleted yet:

- Scanner route modifiers `theme-shell--scanner`, `shell-content-frame--scanner`, and `shell-main-column--scanner` are dynamically composed by `Shell.tsx` and asserted by shell tests.
- `theme-market-badge` is active in stock autocomplete market badges, including dynamically selected market modifier classes.
- `settings-surface`, `home-panel-card`, `home-subpanel`, `chart-card`, `comparison-card`, `backtest-result-bento`, `backtest-void-workspace`, and `gemini-bento-page` are active production selectors.
- `product-command-card` has weak/no direct source evidence, but it sits in multiple product/backtest override layers. Treat it as a rendered-DOM verification candidate before deletion.

No selector is marked safe to delete in this report. The strongest candidates should only move to deletion after a future visual/DOM pass proves absence on affected routes.

## 2. Methodology

Required preflight:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -56
./scripts/task_preflight.sh || true
```

Result:

- `pwd`: `/Users/yehengli/daily_stock_analysis`
- branch: `main`
- upstream: `origin/main`, ahead 0 / behind 0
- preflight dirty files: 0
- recent commits included the requested CSS/native-control/bundle audit commits, with `83b8fbd fix(ui): polish remaining native controls` at HEAD.

Read-first inputs:

```bash
sed -n '1,260p' CODEX_FRONTEND_DESIGN_CONSTITUTION.md
sed -n '1,320p' docs/audits/wolfystock-css-ownership-inventory.md
sed -n '1,300p' docs/audits/archive/frontend/wolfystock-phase0-bundle-design-inventory.md
sed -n '1,280p' docs/audits/archive/frontend/wolfystock-global-codebase-audit.md
sed -n '1,120p' docs/checks/design-guard.md
sed -n '1,220p' apps/dsa-web/src/index.css
```

Baseline commands:

```bash
cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
npm run build
npm run check:design
```

Selector usage commands:

```bash
cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
rg -n "glass-card|terminal-card|dashboard-card|gradient-border-card|stealth-scrollbar|custom-scrollbar|theme-market-badge|workspace-page--chat|theme-shell--scanner|shell-content-frame--scanner|shell-main-column--scanner|backtest-entry-shell|backtest-void-workspace|backtest-result-bento|gemini-bento-page|settings-surface|home-panel-card|home-subpanel|product-command-card|chart-card|comparison-card" src
rg -n "theme-shell--|shell-content-frame--|shell-main-column--|workspace-page--|backtest-entry-shell|backtest-void-workspace|backtest-result-bento|gemini-bento-page" src/components src/pages src/App.tsx
rg -n "glass-card|terminal-card|dashboard-card|gradient-border-card|stealth-scrollbar|custom-scrollbar|theme-market-badge" src/components src/pages src/__tests__ src/pages/__tests__ src/components/__tests__ 2>/dev/null || true
rg -n "\.glass-card|\.terminal-card|\.dashboard-card|\.gradient-border-card|\.stealth-scrollbar|\.custom-scrollbar|\.theme-market-badge|\.workspace-page--chat|\.theme-shell--scanner|\.shell-content-frame--scanner|\.shell-main-column--scanner|\.backtest-entry-shell|\.backtest-void-workspace|\.backtest-result-bento|\.gemini-bento-page|\.settings-surface|\.home-panel-card|\.home-subpanel|\.product-command-card|\.chart-card|\.comparison-card" src/index.css
rg -n "theme-shell--|shell-content-frame--|shell-main-column--|workspace-page--|routeKey|pageKey|surface|variant|classNames|clsx|cn\(" src/components src/pages src/App.tsx | head -240
```

Additional classification helper:

```bash
selectors=(
  glass-card terminal-card dashboard-card gradient-border-card stealth-scrollbar custom-scrollbar theme-market-badge workspace-page--chat theme-shell--scanner shell-content-frame--scanner shell-main-column--scanner backtest-entry-shell backtest-void-workspace backtest-result-bento gemini-bento-page settings-surface home-panel-card home-subpanel product-command-card chart-card comparison-card
)
for s in $selectors; do
  prod=$(rg -l "$s" src --glob '!index.css' --glob '!**/__tests__/**' --glob '!**/*.test.tsx' --glob '!**/*.test.ts' 2>/dev/null | wc -l | tr -d ' ')
  test=$(rg -l "$s" src --glob '**/__tests__/**' --glob '**/*.test.tsx' --glob '**/*.test.ts' 2>/dev/null | wc -l | tr -d ' ')
  css=$(rg -l "\.$s" src/index.css 2>/dev/null | wc -l | tr -d ' ')
  echo "$s prod_files=$prod test_files=$test css_files=$css"
done
```

Limitations:

- This pass used static source search and CSS location inspection only.
- Playwright/rendered DOM verification was **not** used. No browser visual pass is claimed.
- No backend or frontend dev server was started, stopped, killed, or restarted.
- No package install was run.
- `npm run build` wrote current build output under `static/`, but no build output was staged or committed.
- After the initial clean preflight, unrelated dirty frontend files appeared in the worktree (`AdminNotificationsPage.tsx`, `src/utils/displayStatus.ts`, and `src/utils/__tests__/displayStatus.test.ts`). They were inspected only enough to avoid staging and are not part of this report.

## 3. Baseline Build And Design Status

Command: `cd apps/dsa-web && npm run build`

Result: **PASS**

Key output:

- Vite: `v7.3.1`
- modules transformed: `3157`
- CSS asset: `../../static/assets/index-DOc0I34H.css`
- CSS size: **521.76 kB / 74.17 kB gzip**
- Vite large chunk warning source: `../../static/assets/DeterministicBacktestChartWorkspace-CJMwuE3u.js` at **532.42 kB / 178.83 kB gzip**
- The warning is not caused by CSS.

Command: `cd apps/dsa-web && npm run check:design`

Result: **PASS with warnings**

Key output:

- rules checked: `no-solid-gray-bg` blocking; `raw-debug-copy`, `localized-ui-copy`, and `native-ui` warning
- files scanned: **213**
- blocking violations: **0 observed**
- warning count: **17**
- warning type: `native-ui`
- design guard remains advisory per `docs/checks/design-guard.md`

Markdown lint:

- No markdown lint script was found.
- The repository root has no `package.json`.
- `apps/dsa-web/package.json` scripts are `dev`, `build`, `check:design`, `lint`, `test`, `test:e2e`, `test:smoke`, and `preview`.
- `rg -n "markdownlint|mdlint|remark|lint:md|lint.*markdown" package.json apps/dsa-web/package.json .github scripts docs 2>/dev/null | head -80` found docs mentioning markdown/remark, but no runnable markdown lint script.

Full `./scripts/ci_gate.sh`: **not run**. This is a docs-only selector verification task, and the requested validation did not require full CI.

## 4. Selector Candidate Table

| Selector/prefix | CSS location and ownership context | Source usage evidence | Classification | Risk | Recommendation |
| --- | --- | --- | --- | --- | --- |
| `glass-card` | `src/index.css:2851-2898`; theme override layer at `4126-4147`. Classic terminal/glass primitive. | No production or test hits outside CSS. | CSS-only candidate | Medium | Add to dead-selector verification pass. Do not delete until rendered routes prove no DOM use. |
| `terminal-card` | `src/index.css:2767-2822`; theme override layer at `4126-4147`. Classic terminal card primitive. | No production or test hits outside CSS. | CSS-only candidate | Medium | Add to dead-selector verification pass. Its variables are reused by `home-panel-card`, so verify cascade impact. |
| `dashboard-card` | `src/index.css:2912-2959`; theme override layer at `4126-4147`. Classic dashboard card primitive. | No production or test hits outside CSS. | CSS-only candidate | Medium | Candidate for removal only after DOM proof and route snapshots. |
| `gradient-border-card` | `src/index.css:2824-2849`; theme override layer at `4126-4157`. Classic gradient wrapper primitive. | No production or test hits outside CSS. | CSS-only candidate | Medium | Candidate for removal only after proving no legacy markup still emits it. |
| `stealth-scrollbar` | `src/index.css:6105-6128`. Global SpaceX scrollbar utility paired with `custom-scrollbar`. | Test-only negative references in `MarketOverviewPage.test.tsx:1016` and `1334`; no production source hit. | Test-only reference / possible legacy | Medium | Verify rendered DOM and older route containers before deleting; likely weaker than `custom-scrollbar`. |
| `custom-scrollbar` | `src/index.css:6105-6128`. Shared hidden scrollbar utility. | Production hit in `components/common/ScrollArea.tsx:30`. | Confirmed used | Low | Do not delete unless `ScrollArea` is changed and browser scrollbar behavior is revalidated. |
| `theme-market-badge` | Base rules `1990-2035`; theme overrides at `3928`, `8173`, `9976`, `11838`. Market badge design primitive. | `StockAutocomplete/SuggestionsList.tsx:80-96` maps market modifiers and renders `cn("theme-market-badge", config.className)`. | Confirmed used | Low | Do not delete. Modifier classes are selected dynamically from market config. |
| `workspace-page--chat` | Base route modifier `939-941`; SpaceX chat overrides `10998-11002` and `12574-12701`. Legacy chat workspace modifier. | No production hit; `ChatPage.test.tsx:653` asserts `chat-bento-page` does **not** have this class. | Test-only negative reference / possible legacy | Medium | Strong cleanup candidate, but delete only after rendered `/zh/chat` confirms no ancestor receives this class. |
| `theme-shell--scanner` | Scanner shell overrides `13740-13767` and phase-1 shell tokens `16445-16460`. Route shell modifier. | `Shell.tsx:208` appends class when `isScannerRoute`; `Shell.test.tsx:354` asserts it exists. | Likely/confirmed dynamic composition | High | Do not delete. Must be documented as scanner shell route infrastructure. |
| `shell-content-frame--scanner` | Scanner shell overrides `13750-13755` and `16451-16460`. Route shell content modifier. | `Shell.tsx:246` appends class when `isScannerRoute`; `Shell.test.tsx:356` asserts it exists. | Likely/confirmed dynamic composition | High | Do not delete. Requires scanner route visual coverage for any edit. |
| `shell-main-column--scanner` | Scanner shell overrides `13762-13767`, `16440`, and `16451-16460`. Route shell main-lane modifier. | `Shell.tsx:248` appends class when `isScannerRoute`; `Shell.test.tsx:359` asserts it exists. | Likely/confirmed dynamic composition | High | Do not delete. It controls scanner scroll/height ownership. |
| `backtest-entry-shell` | `src/index.css:15598-15846`. Late Backtest entry/void workspace block. | `DeterministicBacktestFlow.tsx:1341` uses `data-testid="backtest-entry-shell"` but does not apply the CSS class. No source hit for `className="backtest-entry-shell"`. | CSS-only/weak evidence | Medium | Strong candidate for future verification. Confirm current `/zh/backtest` DOM before deletion. |
| `backtest-void-workspace` | `src/index.css:15398-15593`. Deterministic chart workspace/void view block. | `DeterministicBacktestResultView.tsx:39-44`; `DeterministicBacktestChartWorkspace.tsx:364-416`. | Confirmed used | Low | Do not delete. It styles active deterministic result/chart workspace. |
| `backtest-result-bento` | `src/index.css:15261-15360`; responsive rules `15554-15591`. Deterministic result hero/KPI bento. | `DeterministicBacktestResultPage.tsx:1047-1104`. | Confirmed used | Low | Do not delete. Needs result-route visual coverage for any edits. |
| `gemini-bento-page` | `src/index.css:15108-15242`; later global bento selector at `16051` and `16166`. Shared bento page skin. | `ChatPage.tsx:1649`; `components/home-bento/PageChrome.tsx:113`. | Confirmed used | Low | Do not delete. It is shared by Chat and home-bento page chrome. |
| `settings-surface` | Variables `462-468`; utility classes `3429-3454`; overrides at `9886-9894`, `11712`, `11737`, `14010`, `15141`, `16216`. Settings/system surface utility. | Production hits in `SettingsField.tsx`, `FontSizeSettingsCard.tsx`, `IntelligentImport.tsx`, `LLMChannelEditor.tsx`, and `AIProviderConfig.tsx`. | Confirmed used | Low | Do not delete. Treat as Settings design-system primitive. |
| `home-panel-card` | `src/index.css:2904-2910`; theme override `4212`; SpaceX override `10821`. Report/Home panel modifier. | `ReportOverview.tsx:100`, `120`, `143`; `ReportStrategy.tsx:77`; `ReportDetails.tsx:92`; `ReportNews.tsx:56`. | Confirmed used | Low | Do not delete. Despite name, it is used by shared report components. |
| `home-subpanel` | `src/index.css:2973-2988`; theme overrides `4131` and `4139`. Home/report nested panel. | `ReportNews.tsx:114`. | Confirmed used | Low | Do not delete without report/news visual coverage. |
| `product-command-card` | Base utility `4235`; shared product reset `6193`; backtest rail modifier `6412`; backtest overrides `6681`, `8350`, `8363`, `8382`, `8394`, `8480`, `8492`, `9265`, `9292`, `16219`. Product/backtest command card primitive. | No production or test hits outside CSS. | CSS-only candidate with design-primitive risk | High | Do not delete in first pass. Verify rendered Backtest/Scanner/old report DOM and cascade dependencies first. |
| `chart-card` | Base chart rules `4502-4925`; footer/value rules earlier; backtest overrides `5134`, `5162`, `5272`, `6686`, `7381`, `8368`, `8422`, responsive `5901`. Shared SVG chart primitive. | `RuleRunComparisonPanel.tsx:130-151`; `RuleRunComparisonPanel.tsx:264-287`; `BacktestAuditTables.tsx:452-467`. | Confirmed used | Low | Do not delete. Active Backtest comparison/chart primitive. |
| `comparison-card` | `src/index.css:5391-5456`. Rule comparison cards. | `RuleRunComparisonPanel.tsx:264-287`; `BacktestAuditTables.tsx:452-467`. | Confirmed used | Low | Do not delete. Active comparison UI primitive. |

## 5. Dynamic Composition Findings

`Shell.tsx` dynamically composes route modifiers that may not look like ordinary static page classes:

- `theme-shell--scanner` is appended to the shell root when `isScannerRoute`.
- `shell-content-frame--scanner` is appended to the content frame when `isScannerRoute`.
- `shell-main-column--scanner` is appended to the main lane when `isScannerRoute`.
- Related shell classes such as `shell-content-frame--chat`, `shell-main-column--chat`, `theme-shell--wide`, `theme-shell--market-overview`, `shell-content-frame--backtest`, and `shell-content-frame--system-control` follow the same route-composition pattern.

Evidence:

- `Shell.tsx:208` composes `theme-shell--scanner`.
- `Shell.tsx:246` composes `shell-content-frame--scanner`.
- `Shell.tsx:248` composes `shell-main-column--scanner`.
- `Shell.test.tsx:354-359` asserts scanner shell/content/main classes exist.
- `src/index.css:13740-13767` and `16440-16460` contain scanner-specific shell height/overflow fixes.

`workspace-page--*` is a different family:

- `workspace-page--preview` is statically used by `PreviewReportPage.tsx` and `PreviewFullReportDrawerPage.tsx`.
- `workspace-page--backtest` is statically used by `RuleBacktestComparePage.tsx` and `DeterministicBacktestResultPage.tsx`.
- `workspace-page--chat` has CSS but no production source hit in this pass. `ChatPage.test.tsx:653` asserts the active bento page should not have it.

Conclusion:

- Shell route modifiers should be treated as active infrastructure even when they are assembled inside template strings.
- `workspace-page--chat` is a legacy candidate, but deleting it still needs a rendered DOM pass because CSS selectors can target ancestors that static single-component searches miss.

## 6. Dead-Selector Candidate Shortlist

These are **not approved for deletion** by this report. They are candidates for a future verification/removal pass.

| Candidate | Evidence | Risk | Future verification required |
| --- | --- | --- | --- |
| `glass-card` | CSS definitions and theme overrides only; no source/test hits outside CSS. | Medium | Search built/rendered DOM on `/zh`, `/zh/settings`, `/zh/chat`, `/zh/market-overview`, and report preview routes. |
| `terminal-card` | CSS definitions and theme overrides only; no source/test hits outside CSS. | Medium | Verify no legacy report/Home/terminal components emit it; confirm `home-panel-card` does not depend on inherited usage. |
| `dashboard-card` | CSS definitions and theme overrides only; no source/test hits outside CSS. | Medium | Verify no legacy dashboard route or home bento DOM emits it. |
| `gradient-border-card` | CSS definitions and theme overrides only; no source/test hits outside CSS. | Medium | Verify no wrapper components still emit the outer/inner pair. |
| `workspace-page--chat` | No production source hit; test asserts active Chat bento page lacks it. | Medium | Render `/zh/chat` and inspect full ancestor chain before deleting its CSS overrides. |
| `stealth-scrollbar` | No production hit; negative test assertions only. | Medium | Inspect rendered DOM for all route rails/scroll containers; compare with active `custom-scrollbar` and `no-scrollbar`. |
| `backtest-entry-shell` | CSS class has no source hit; current source uses the same token as `data-testid`, not as a class. | Medium | Render `/zh/backtest` and inspect setup/sidebar DOM; verify class absence and visual no-op. |
| `product-command-card` | No source/test hits outside CSS, but many product/backtest override layers reference it. | High | Render Backtest, compare, report preview, Scanner, and any setup/workbench states before considering deletion. |

## 7. Do-Not-Delete Shortlist

These selectors either have confirmed production source usage or are route-shell primitives with tests:

- `theme-shell--scanner`
- `shell-content-frame--scanner`
- `shell-main-column--scanner`
- `custom-scrollbar`
- `theme-market-badge`
- `backtest-void-workspace`
- `backtest-result-bento`
- `gemini-bento-page`
- `settings-surface`
- `home-panel-card`
- `home-subpanel`
- `chart-card`
- `comparison-card`

Additional caution:

- Do not delete `product-command-card` in a first cleanup pass despite weak source evidence; it is embedded in multiple product/backtest override layers and should be proven inactive through rendered DOM coverage.
- Do not delete scanner shell route modifiers as "global CSS." They are intentional shell ownership and scroll/height controls.
- Do not treat CSS-only evidence as enough for deletion when the selector is a design-system primitive or route shell modifier.

## 8. Recommended Next Tasks

| Task | Scope | Likely files touched | Risk | Tests/checks | Parallel-safe? |
| --- | --- | --- | --- | --- | --- |
| CSS Dead Selector Verification Pass 1 | Render/DOM-check `glass-card`, `terminal-card`, `dashboard-card`, `gradient-border-card`, `workspace-page--chat`, `stealth-scrollbar`, `backtest-entry-shell`, and `product-command-card`. | Prefer a new audit doc first; no CSS changes. | Low as audit, high if deletion follows. | `rg`, Playwright DOM queries on `/zh`, `/zh/scanner`, `/zh/chat`, `/zh/backtest`, `/zh/backtest/results/1`, `/zh/settings`, `/zh/market-overview`; `npm run build`; `npm run check:design`. | Yes if read-only. |
| Shell Route Modifier Documentation | Document `theme-shell--*`, `shell-content-frame--*`, `shell-main-column--*`, and `workspace-page--*` ownership. | `docs/audits/*` or a focused architecture/check doc. | Low | Static review plus shell tests if code later changes. | Yes. |
| CSS Visual Regression Checklist | Define desktop/mobile route checklist before any CSS deletion/splitting. | New docs/checklist; no product code. | Low | Browser/Playwright checklist only; no full CI for docs. | Yes. |
| Safe Dead Selector Removal Trial | Remove one low-risk CSS-only family after DOM proof, starting with one of `glass-card`, `dashboard-card`, or `gradient-border-card`. | `apps/dsa-web/src/index.css` only, after approval. | Medium | `npm run build`, `npm run check:design`, targeted route DOM/visual checks, `git diff --check`. | No; serialize CSS deletion. |
| Design Guard Final Native Controls Burn-down | Continue reducing the current 17 advisory native-control findings by surface. | Component/page files named by `npm run check:design`. | Medium | `npm run check:design`, `npm run lint`, `npm run build`, browser checks for touched routes. | Partly, by surface. |

## 9. Non-Goals

- No CSS changed.
- No product code changed.
- No frontend components or pages changed.
- No tests changed.
- No backend files changed.
- No package files changed.
- No Tailwind, Vite, PostCSS, design guard, or runtime config changed.
- No `docs/CHANGELOG.md` change.
- No selector deletion performed.
- No generated build output, screenshots, temporary files, sourcemaps, analyzer files, or runtime artifacts committed.

## 10. Validation Plan For This Report

Required validation for this report document:

```bash
cd /Users/yehengli/daily_stock_analysis
sed -n '1,320p' docs/audits/wolfystock-css-selector-usage-verification.md
git diff --check -- docs/audits/wolfystock-css-selector-usage-verification.md
```

Staging/commit safety for this task:

- Stage only `docs/audits/wolfystock-css-selector-usage-verification.md`.
- Do not stage unrelated dirty frontend files.
- Do not stage generated `static/` output.
- Do not run `git add .`.
