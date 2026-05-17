# WolfyStock CSS Cleanup Closure Report

Date: 2026-05-05
Consolidation update: 2026-05-10

Scope: docs-only closure report for the completed WolfyStock CSS dead-selector cleanup cycle on `main`.

## 1. Executive Summary

The CSS cleanup cycle is closed for the selector families listed in this report. The completed deletion commits removed only unused CSS selector families from `apps/dsa-web/src/index.css`, after prior audit and DOM proof tasks established that the target selectors were either CSS-only, test-negative only, or non-class `data-testid` only in current production source.

Removed selector families:

- `glass-card`
- `terminal-card`
- `dashboard-card`
- `gradient-border-card`
- `product-command-card`
- `workspace-page--chat`
- `backtest-entry-shell`
- `stealth-scrollbar`

Current design guard status: `npm run check:design` passes with no blocking violations or warnings. `npm run lint`, `npm run build`, and `python3 -m compileall -q src api` also pass in the current checkout.

Key protected owners remain active and must not be treated as dead CSS: `no-scrollbar`, `custom-scrollbar`, `ScrollArea`, `gemini-bento-page`, `gemini-bento-page--chat`, chat shell columns, Scanner shell selectors, Backtest result/void workspace primitives, product/report primitives, settings surfaces, Home/report card primitives, chart cards, and comparison cards.

Remaining risk is governance risk, not a known active defect: future cleanup prompts can reintroduce visual regressions if they combine CSS deletion with primitive migration, rely on source search alone, or delete active owner selectors because one mocked route reports zero rendered hits.

## 2. Removed Selector Families

| Selector family | Audit/proof source | Deletion commit | Verification coverage | Rollback command | Notes |
| --- | --- | --- | --- | --- | --- |
| `glass-card` | `wolfystock-css-ownership-inventory.md`, consolidated pre-closure selector audit evidence summarized here | `543d6cb chore(css): remove unused glass card selectors` | Static source search showed CSS-only usage before deletion; rendered DOM pass found zero hits across the route matrix; current static search finds no CSS or production class usage. | `git revert 543d6cb` | Classic card primitive removed as a dedicated family. Future work should protect active `home-panel-card`, `settings-surface`, and product/report primitives instead. |
| `terminal-card` | `wolfystock-css-ownership-inventory.md`, consolidated pre-closure selector audit evidence summarized here | `338566e chore(css): remove unused terminal card selectors` | Static and rendered proof showed no current class owner; current static search finds no CSS or production class usage. | `git revert 338566e` | Removed separately from report/Home primitives that use similar material language. |
| `dashboard-card` | `wolfystock-css-ownership-inventory.md`, consolidated pre-closure selector audit evidence summarized here | `0f0325d chore(css): remove unused dashboard card selectors` | Static and rendered proof showed no current class owner; current static search finds no CSS or production class usage. | `git revert 0f0325d` | Removal does not license deletion of dashboard-like active route classes. |
| `gradient-border-card` | `wolfystock-css-ownership-inventory.md`, consolidated pre-closure selector audit evidence summarized here | `96503cf chore(css): remove unused gradient border card selectors` | Static and rendered proof showed no current wrapper/inner class owner; current static search finds no CSS or production class usage. | `git revert 96503cf` | Deleted as one visual effect family after route proof. Do not infer that active border/glow tokens are removable. |
| `product-command-card` | `wolfystock-scanner-dom-verification.md`, `wolfystock-product-command-card-owner-audit.md`, consolidated pre-closure selector audit evidence summarized here | `aa5950d chore(css): remove unused product command card selectors` | Owner audit found zero production source hits but high historical Backtest/product risk; deletion was isolated to this family; current static search finds no CSS or production class usage. | `git revert aa5950d` | Current owners are `product-section-card`, `summary-block`, `preview-card`, `metric-card`, common controls, and Backtest route primitives. |
| `workspace-page--chat` | `wolfystock-chat-dom-verification.md`, consolidated pre-closure selector audit evidence summarized here | `ea2e636 chore(css): remove unused chat workspace selectors` | Corrected Chat DOM proof established the legacy workspace class was absent while `gemini-bento-page--chat` and current chat layout classes own the route; current static search only finds a negative test assertion. | `git revert ea2e636` | Keep the current bento chat owners protected. Do not resurrect legacy workspace wrapper padding. |
| `backtest-entry-shell` | `wolfystock-backtest-dom-verification.md`, consolidated pre-closure selector audit evidence summarized here | `eae587a chore(css): remove unused backtest entry shell selectors` | Corrected Backtest proof distinguished absent CSS class from the active `data-testid="backtest-entry-shell"`; current static search still finds only that non-class test id. | `git revert eae587a` | The test id is not CSS ownership. Active Backtest owners remain protected. |
| `stealth-scrollbar` | `wolfystock-scrollbar-dom-verification.md`, `wolfystock-corrected-scroll-proof.md`, `wolfystock-scrollarea-custom-scrollbar-owner-inventory.md` | `af2bf51 chore(css): remove unused stealth scrollbar selectors` | Corrected scroll proof covered Scanner, Portfolio, and Market Overview scroll-heavy states at desktop and mobile; current static search only finds negative tests. | `git revert af2bf51` | `stealth-scrollbar` removal does not permit deleting `no-scrollbar` or `custom-scrollbar`. |

## 3. Protected Active Owners

| Selector/class/component | Owner route/component | Why protected | Future migration requirement |
| --- | --- | --- | --- |
| `no-scrollbar` | Shared utility across Chat, Scanner, Portfolio, Market Overview, Backtest, Watchlist, Settings, and tests | Active source/test usage and scroll ownership proof; frontend constitution discourages exposed native scrollbars. | Do not delete. Any replacement must preserve local scroll behavior and hidden native scrollbar affordances across every route using it. |
| `custom-scrollbar` | `components/common/ScrollArea.tsx` and `ScrollArea.test.tsx` | Shared component-owned scrollbar skin; inventory classifies it as protected even without broad route consumers. | Do not delete without a dedicated `ScrollArea` migration/deprecation proof and focused component tests. |
| `ScrollArea` | `components/common/ScrollArea.tsx` | Component owner of `custom-scrollbar`; deleting the CSS without component migration leaves an inconsistent primitive. | Migrate component and tests first, then prove every consumer or non-consumer state explicitly. |
| `gemini-bento-page` | `ChatPage.tsx`, home bento `PageChrome` | Active cross-surface bento skin. | Replace only through a bento shell migration with Chat and Home proof. |
| `gemini-bento-page--chat` | `ChatPage.tsx` | Active Chat route modifier replacing legacy `workspace-page--chat`. | Preserve until Chat shell is migrated with full desktop/mobile DOM and visual proof. |
| `shell-content-frame--chat` | Chat shell/frame route ownership | Chat layout frame ownership; must not be confused with removed legacy workspace selectors. | Migrate only in a Chat shell task with corrected route proof. |
| `shell-main-column--chat` | Chat shell/main column ownership | Chat column and scroll behavior ownership. | Migrate only with full Chat desktop/mobile layout and scroll proof. |
| `backtest-result-bento` | `DeterministicBacktestResultPage.tsx` | Active deterministic result hero/KPI bento. | Do not delete without result route owner migration and chart/result visual proof. |
| `backtest-void-workspace` | `DeterministicBacktestChartWorkspace.tsx`, deterministic result view | Active chart workspace and void/result layout owner. | Migrate only with populated result route, chart workspace, desktop/mobile proof. |
| `product-section-card` | Backtest, report/product surfaces, historical evaluation panels | Current product command/card owner after `product-command-card` removal. | Owner migration must inventory all product/report/Backtest consumers first. |
| `summary-block` | Backtest deterministic flow/result/report sections | Active summary primitive. | Do not delete as a product-command-card follow-up; migrate with component-level replacements. |
| `preview-card` | Backtest deterministic flow/result/report sections | Active preview/info primitive. | Require report and Backtest route proof before any migration. |
| `metric-card` | Backtest, result bento, report/product metrics | Active metric primitive and density owner. | Require density and route proof before replacement. |
| `home-panel-card` | Report/Home components such as `ReportOverview` and `ReportStrategy` | Active report/Home card primitive, not legacy `glass-card`. | Migrate only with report preview/Home visual proof. |
| `home-subpanel` | Report/Home nested panels | Active nested report/Home primitive. | Migrate only with report details/news and Home proof. |
| `chart-card` | Backtest compare/result/chart components | Active chart primitive. | Any migration must prove charts, legends, density, and mobile behavior. |
| `comparison-card` | Backtest comparison components | Active comparison panel primitive. | Require comparison route/component proof before changes. |
| `settings-surface` | Personal and system settings surfaces | Active settings material and admin/settings design owner. | Do not remove while settings/admin raw-config and health surfaces depend on it. |
| Scanner shell selectors: `theme-shell--scanner`, `shell-content-frame--scanner`, `shell-main-column--scanner` | `Shell.tsx`, Scanner route tests, scanner shell DOM | Active route shell, content frame, main column, and scroll ownership. | Dedicated Scanner shell migration only; must include source, tests, populated desktop/mobile proof, and overflow checks. |

## 4. Rules For Future CSS Deletion Prompts

- Delete one selector family per task.
- Gather pre-delete static evidence from CSS, production source, tests, and docs.
- Do not combine CSS deletion with feature work, primitive migration, layout redesign, or route refactors.
- Do not run global formatting or touch unrelated files.
- Use a route matrix that covers Home, Scanner, Watchlist, Backtest entry, Backtest result, Market Overview, Settings, System Settings, Chat, and preview report when the selector family can affect shared surfaces.
- Verify desktop and mobile viewports, normally `1440x1000` and `390x844`.
- Do not commit generated artifacts, screenshots, build outputs, or temporary scripts unless explicitly requested.
- Include an explicit rollback command for every deletion commit.
- Keep active owners protected even when they visually resemble removed selector families.
- Do not delete `custom-scrollbar` without `ScrollArea` migration proof.
- Do not delete `no-scrollbar`.

## 5. What Not To Do

- Do not combine CSS deletion with canonical primitive migration.
- Do not delete active owner classes because rendered count is zero in one route, one viewport, or one mocked state.
- Do not use source search alone as deletion proof.
- Do not touch `apps/dsa-web/src/index.css` when another CSS task or product task is dirty.
- Do not rely on mock-limited routes without corrected proof.
- Do not treat negative test assertions as active class ownership.
- Do not treat a `data-testid` value as CSS class ownership.
- Do not delete shared scroll utilities while route-local overflow behavior still depends on them.

## 6. Remaining CSS Governance Items

- `ScrollArea` migration or deprecation remains optional and should happen only if explicitly needed.
- The CSS visual regression checklist should remain required before any future selector deletion.
- Future shared utility deletion must start with an owner inventory, not a direct CSS edit.
- Scanner shell, Backtest result, Chat bento, Settings, and report/product primitives should stay in the protected-owner list until their owners are migrated.
- Future CSS cleanup prompts should reuse these audit documents instead of rerunning broad dead-selector discovery from scratch.
- This closure report now absorbs the stale pass-1 CSS/DOM audit summary so future tasks can start from the retained closure and route-specific proof docs.

## 7. Verification Baseline

Preflight:

- `pwd`: PASS, `/Users/yehengli/daily_stock_analysis`
- Branch: PASS, `main`
- `git status --branch --short`: PASS, `## main...origin/main` before report creation
- `./scripts/task_preflight.sh || true`: PASS, branch `main`, upstream `origin/main` ahead 0 / behind 0, dirty files 0

Static selector verification:

- Removed-family search:
  - Command: `rg -n "glass-card|terminal-card|dashboard-card|gradient-border-card|product-command-card|workspace-page--chat|backtest-entry-shell|stealth-scrollbar" src/index.css src | head -300`
  - Result: no CSS definitions and no production class owners found. Remaining hits are negative tests for `workspace-page--chat` / `stealth-scrollbar` and `data-testid="backtest-entry-shell"`.
- Protected-owner search:
  - Command: `rg -n "no-scrollbar|custom-scrollbar|ScrollArea|gemini-bento-page|backtest-result-bento|backtest-void-workspace|product-section-card|summary-block|preview-card|metric-card|settings-surface|home-panel-card|home-subpanel|chart-card|comparison-card|theme-shell--scanner|shell-content-frame--scanner|shell-main-column--scanner" src/index.css src/pages src/components src/__tests__ | head -600`
  - Result: active CSS/source/test coverage remains for the protected owners.

Baseline checks:

- `cd apps/dsa-web && npm run check:design`: PASS, 216 files scanned, no blocking violations or warnings.
- `cd apps/dsa-web && npm run lint`: PASS, `eslint .` exited 0.
- `cd apps/dsa-web && npm run build`: PASS with Vite chunk-size warning for `DeterministicBacktestChartWorkspace-1CKEfPQC.js` at 532.42 kB / 178.83 kB gzip.
- `python3 -m compileall -q src api`: PASS, no output.
- `./scripts/ci_gate.sh`: not run. This is a docs-only closure report; targeted frontend design/lint/build checks and backend compile baseline were run instead.
- Markdown lint: not run. Static search found no runnable markdown lint script in the root checkout or `apps/dsa-web/package.json`; prior audit docs report the same limitation.

## 8. Non-Goals

- No CSS changed.
- No product code changed by this report.
- No tests changed.
- No backend/API code changed.
- No package/config changed.
- No generated artifacts committed.
- `docs/CHANGELOG.md` was not edited because the user explicitly scoped this task to a closure report and requested no changelog edit.

## 9. Mandatory Sources Inspected

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/checks/css-visual-regression-checklist.md`
- `docs/audits/wolfystock-css-ownership-inventory.md`
- `docs/audits/archive/frontend/wolfystock-scanner-dom-verification.md`
- `docs/audits/archive/frontend/wolfystock-product-command-card-owner-audit.md`
- `docs/audits/archive/frontend/wolfystock-chat-dom-verification.md`
- `docs/audits/archive/frontend/wolfystock-backtest-dom-verification.md`
- `docs/audits/archive/frontend/wolfystock-scrollbar-dom-verification.md`
- `docs/audits/archive/frontend/wolfystock-corrected-scroll-proof.md`
- `docs/audits/archive/frontend/wolfystock-scrollarea-custom-scrollbar-owner-inventory.md`
- `docs/audits/wolfystock-frontend-design-conformance-audit.md`
- `docs/design/wolfystock-canonical-ui-primitives.md`
- `docs/operations/parallel-codex-playbook.md`

Relevant completed commits inspected:

- `543d6cb chore(css): remove unused glass card selectors`
- `338566e chore(css): remove unused terminal card selectors`
- `0f0325d chore(css): remove unused dashboard card selectors`
- `96503cf chore(css): remove unused gradient border card selectors`
- `aa5950d chore(css): remove unused product command card selectors`
- `ea2e636 chore(css): remove unused chat workspace selectors`
- `eae587a chore(css): remove unused backtest entry shell selectors`
- `af2bf51 chore(css): remove unused stealth scrollbar selectors`
- `89933dc docs: verify css selector dom usage`
- `2e97b39 docs: verify scanner dom shell classes`
- `44321ba docs: verify chat dom shell classes`
- `47c85ed docs: verify backtest dom shell classes`
- `489ec7f docs: verify scrollbar dom usage`
- `519fda2 docs: verify corrected scroll ownership`
- `8aaf984 docs: inventory scrollarea custom scrollbar ownership`

## 10. Prompt Insertion Snippet

Use this snippet in future Codex prompts before any WolfyStock CSS deletion task:

```text
This is a CSS deletion-only task. Delete exactly one selector family and do not combine the deletion with feature work, primitive migration, route refactors, global formatting, generated artifacts, or unrelated cleanup.

Before editing CSS, reuse the existing WolfyStock CSS audits and run static source evidence for the target family. Then run the CSS visual regression route matrix at desktop and mobile viewports. Mock-limited route proof is not sufficient unless corrected proof exists.

Keep these active owners protected: no-scrollbar, custom-scrollbar, ScrollArea, gemini-bento-page, gemini-bento-page--chat, shell-content-frame--chat, shell-main-column--chat, backtest-result-bento, backtest-void-workspace, product-section-card, summary-block, preview-card, metric-card, home-panel-card, home-subpanel, chart-card, comparison-card, settings-surface, theme-shell--scanner, shell-content-frame--scanner, and shell-main-column--scanner.

Do not delete custom-scrollbar without ScrollArea migration proof. Do not delete no-scrollbar. Do not treat a data-testid or one-route zero count as deletion proof. Include an explicit rollback command and stage only the intended file.
```
