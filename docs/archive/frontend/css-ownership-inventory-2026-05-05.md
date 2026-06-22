# WolfyStock CSS Ownership Inventory

Date: 2026-05-05 Asia/Shanghai
Repository: `/Users/yehengli/daily_stock_analysis`
Branch audited: `main`
Mode: read-only audit document; no product-code, CSS, build-config, test, package, runtime, or changelog changes

Current use note: this file is retained as CSS deletion provenance, not current
visual-source authority. If its older deep-space/ghost-glass wording conflicts
with `docs/codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md`, the Reflect-Linear
source docs win.

## 1. Executive Summary

`apps/dsa-web/src/index.css` is currently a single global Tailwind plus WolfyStock theme file with **16,912 lines** and **440,792 bytes**. The production build emits one CSS asset, `static/assets/index-tAvUYm06.css`, at **521.59 kB minified / 74.16 kB gzip**.

Current build status: **pass with a Vite large chunk warning**. The warning is not caused by CSS; current output warns because `DeterministicBacktestChartWorkspace-BKWC-FzH.js` is **532.42 kB / 178.83 kB gzip**.

Current design guard status: **pass with warnings**. `npm run check:design` scanned **213 files**, found no blocking failures, and reported **39 warning-only `native-ui` findings**. Per `docs/checks/design-guard.md`, these warnings remain advisory and should not be wired into `ci_gate`.

Main CSS ownership findings:

- The first ~4,200 lines are global foundation: imports, Tailwind layers, design tokens, base styles, shell/workspace primitives, shared report/chart/menu/list/history utilities, classic terminal utilities, settings utilities, and theme-family overrides.
- Lines ~4,200-5,900 contain shared product/report/backtest-result primitives: `product-*`, `metric-*`, `summary-*`, `preview-*`, `chart-*`, `backtest-result-*`, and compare-table rules.
- Lines ~5,900-12,700 are a large SpaceX product override layer that redefines theme variables and heavily styles shell, auth, workspace, backtest, report, chat, market overview, and responsive states.
- Lines ~12,700-16,912 are later corrective overrides for Home, shared shell/scanner, Gemini/bento chat, backtest result entry/void pages, dense dashboard behavior, and phase-1 shared shell/navigation tokens.
- Static selector summary found approximately **1,041 unique class selectors**, **3,554 class selector mentions**, **51 media queries**, **25 keyframes**, **2 `@layer` blocks**, and **3 `:root` blocks**. Top selector prefixes are `backtest`, `home`, `theme`, `workspace`, `shell`, `report`, and `product`.

Safest next CSS-related tasks are usage verification, token documentation, and visual-regression checklists. The unsafe next step is deleting or splitting CSS without route-level visual coverage, because many selectors are route-scoped, dynamically composed, or applied through shell classes.

## 2. Methodology

Commands run:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -52
./scripts/task_preflight.sh || true

sed -n '1,220p' CODEX_FRONTEND_DESIGN_CONSTITUTION.md
sed -n '1,240p' docs/audits/archive/frontend/wolfystock-global-codebase-audit.md
sed -n '1,260p' docs/audits/archive/frontend/wolfystock-phase0-bundle-design-inventory.md
sed -n '1,260p' docs/audits/archive/frontend/wolfystock-bundle-composition-report.md
sed -n '1,240p' docs/checks/design-guard.md
sed -n '1,620p' apps/dsa-web/src/index.css

cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
npm run build
npm run check:design
wc -l src/index.css
wc -c src/index.css
grep -n "^@import\|^@layer\|^:root\|^body\|scrollbar\|no-scrollbar\|glass\|ghost\|backtest\|scanner\|market\|portfolio\|watchlist\|settings\|admin\|chat\|report" src/index.css | head -300
grep -n "^/\*\|^@layer\|^@import\|^:root\|^\.[A-Za-z0-9_-]" src/index.css | head -500
grep -n "home\|scanner\|watchlist\|backtest\|portfolio\|market\|admin\|settings\|chat\|report\|preview\|bento\|glass\|sidebar" src/index.css | head -400
grep -n "no-scrollbar\|scrollbar\|glass\|ghost\|gradient\|shadow\|rounded\|border\|backdrop-blur\|safe-area\|mobile\|overflow" src/index.css | head -500
```

Additional read-only evidence commands:

```bash
cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
node --input-type=module <<'NODE'
// Inline selector summary; no temp file was written.
NODE
rg -n "theme-panel-glass|glass-card|theme-sidebar-shell|theme-shell--scanner|shell-content-frame--scanner|workspace-page--chat|theme-market-badge|home-surface-button|home-history-item|settings-surface|backtest-result-bento|backtest-v1-stage|gemini-bento-page|no-scrollbar|stealth-scrollbar|custom-scrollbar" src | head -220
rg -n "backtest-result-page|backtest-unified-chart-viewer|backtest-entry-shell|backtest-void-workspace|backtest-workbench|comparison-card|compare-section|product-command-card|chart-card|workspace-page--backtest" src | head -220
rg -n "theme-shell--|shell-content-frame--|shell-main-column--|workspace-page--" src/components src/pages src/App.tsx | head -160
rg -n "glass-card|terminal-card|dashboard-card|gradient-border-card|home-history-item|home-subpanel|home-panel-card" src/components src/pages src/App.tsx | head -160

cd /Users/yehengli/daily_stock_analysis
find static -type f -name "*.css" -exec ls -lh {} + | sort -k5 -hr | head -20
find static -type f -name "*.css" -exec du -h {} + | sort -hr | head -20
rg -n "markdownlint|mdlint|remark|lint:md|lint.*markdown" package.json apps/dsa-web/package.json .github scripts docs 2>/dev/null | head -80
```

Limitations:

- This is a static ownership audit, not a dead-code proof.
- No browser verification was run because no UI changed and the task explicitly did not require browser verification.
- No dev servers were started, stopped, killed, or restarted.
- No packages were installed.
- No generated analyzer output, temporary scripts, screenshots, sourcemaps, or build artifacts were committed.
- Source usage checks were representative. Dynamic class composition and runtime-only route classes still require visual and code-path verification before cleanup.

## 3. Current CSS/Build Status

| Item | Current result | Evidence |
| --- | ---: | --- |
| Source CSS line count | 16,912 lines | `wc -l src/index.css` |
| Source CSS byte size | 440,792 bytes | `wc -c src/index.css` |
| Built CSS asset | `index-tAvUYm06.css` | `npm run build` |
| Built CSS size | 521.59 kB | Vite build output |
| Built CSS gzip size | 74.16 kB | Vite build output |
| Filesystem CSS size | 509K by `ls -lh`, 512K by `du -h` | `find static -type f -name "*.css"` |
| Build status | Pass | `npm run build` exited 0 |
| Vite warning status | Warning remains | `DeterministicBacktestChartWorkspace-BKWC-FzH.js` is 532.42 kB |
| Design guard status | Pass with 39 warnings | `npm run check:design` exited 0 |
| Design guard scan count | 213 files | Design guard output |
| Blocking design findings | 0 observed | Design guard output |
| Warning contract | Advisory | `docs/checks/design-guard.md` says warnings are non-blocking |
| Markdown lint | Not available | No root `package.json`; web package has no markdown lint script |

Build output also emitted `static/assets/index-BpbVnbRF.js` at **431.28 kB / 149.82 kB gzip**, `BacktestPage-BF4vJ7MH.js` at **233.81 kB / 73.49 kB gzip**, and `SystemSettingsPage-CVC5NjMa.js` at **205.32 kB / 57.98 kB gzip**.

## 4. CSS Ownership Map

| Line range | Category | Likely owner/surface | Confidence | Notes |
| --- | --- | --- | --- | --- |
| 1-2 | Imports | Web app global CSS | High | Google fonts plus Tailwind import. |
| 4-72 | Tailwind/base layers | Shared CSS foundation | High | `@layer utilities` contains `no-scrollbar`, `ui-truncate`, quiet horizontal scroll, and control helpers; `@layer base` normalizes `select`. |
| 73-504 | Global tokens/theme variables | Design system / shell / Home / Settings | High | Canonical HSL tokens, typography, shell, nav, chart, badge, Home, Settings, input, gradient, and shadow variables. |
| 512-545 | Base document styles | App root and scanner shell | High | `body`, `html`, `#root`, scanner-shell overflow behavior. |
| 548-733 | Boot splash | App startup visual | Medium | `app-boot-splash*` and early boot animation styling. |
| 824-1339 | Workspace/report/shared surface primitives | Shell, report, chat, status strips | High | `workspace-*`, `report-support-*`, status, split-layout, and chat layout classes. |
| 1350-2192 | Theme shell and global UI primitives | Layout/nav/chart/menu/history | High | `theme-shell`, sidebar/nav, panels, chart toolbar, report hero, menus, market badges, task/history items. |
| 2205-2268 | Mobile shell/root overrides | Global mobile layout | Medium | Mobile font scale, safe-area padding, responsive report hero disclosure. |
| 2274-2750 | Classic terminal utilities | Legacy/shared UI foundation | Medium | Title gradient, gauges, sentiment colors, input/badge/list/feed, global scrollbars, animation utility names, text/background/border/glow helpers. |
| 2767-3575 | Terminal PR utilities and Settings utilities | Shared cards, Home, buttons, Settings | Medium/High | `terminal-card`, `glass-card`, `home-*`, `btn-*`, `settings-*`, `shell-page-frame`, slide-in-left. |
| 3588-4231 | Theme-family overrides | Design system | High | Additional `:root`/`html[data-theme]` variables and overrides for inputs, buttons, cards, chart, Settings, report support. |
| 4235-4925 | Product/report/chart primitives | Backtest/report shared components | High | `product-*`, `metric-*`, `summary-*`, `preview-*`, `audit-*`, `chart-card*`; confirmed used in compare/report/backtest pages. |
| 4929-5904 | Backtest result and compare CSS | Backtest / deterministic result / compare | High | `backtest-result-*`, linked chart, tooltip, audit tables, compare cards, compare nav/report preview, responsive backtest result rules. |
| 5906-9451 | SpaceX product override | Theme/shell/auth/backtest/workspace | Medium | Large override layer. Contains renewed theme variables, stealth/custom scrollbar, shell/nav, auth, backtest workbench/V1, product primitives, and responsive behavior. |
| 9452-11581 | Strict SpaceX product shell | Theme, market overview, chat, report, status | Medium | Theme variables and deep-space corrections, including market-overview shell selectors, chat workspace, report reveal/status grid, skeletons, and responsive blocks. |
| 11582-12717 | SpaceX research workspace final | Research/report/workspace/Home-ish surfaces | Medium | Additional product surface, cards, history, report, and responsive corrections. Needs route-level ownership verification before cleanup. |
| 12718-13701 | Home workspace override | Home / report/history | Medium/High | Explicit Home workspace override for command, status, history, report surfaces. |
| 13702-16016 | Structural shell/Home/scanner/chat/backtest corrections | Shared shell, Scanner, Chat bento, Backtest result/entry | Medium/High | Authoritative shared-shell and homepage pass; scanner shell classes; Gemini bento; backtest result bento, void workspace, entry shell, setup controls. |
| 16017-16369 | Dense dashboard reset | Shared dense dashboard / Backtest | Medium | Shared viewport lock/control compaction; high risk to change without visual checks. |
| 16370-16912 | Phase 1 shell/nav tokens | Shared shell/navigation/scanner | High | Recent shared shell and navigation token layer; should be treated as active design constitution infrastructure. |

## 5. Page-Specific And Legacy Candidates

| Selector/prefix/section | Evidence | Usage status checked | Classification | Recommendation |
| --- | --- | --- | --- | --- |
| `.backtest-*` | Static summary found `backtest` as the largest prefix: 241 unique class selectors, 632 mentions, broad line span 4929-16339. | Confirmed in `BacktestPage.tsx`, `DeterministicBacktestResultPage.tsx`, `RuleBacktestComparePage.tsx`, and tests. | Confirmed used, page-specific plus shared backtest primitives. | Do not delete. Future cleanup should start with a Backtest visual regression checklist. |
| `.backtest-result-bento*` | Lines 15261-15591; source references in `DeterministicBacktestResultPage.tsx:1047-1104`. | Confirmed used. | Page-specific, active. | Keep until deterministic result page has visual coverage. |
| `.backtest-entry-shell*` / `.backtest-void-workspace*` | Lines 15398-15823. | Not exhaustively traced in this audit. | Needs verification. | Search specific route/component ownership before changing. |
| `.home-*` | Home variables at 415-459; Home classes around 2904-3218 and 12718+. | Confirmed `home-panel-card` and `home-subpanel` in report components; `home-surface-button` in report/preview components. | Confirmed used; partly page-specific, partly report-shared. | Avoid deleting as "Home-only"; some report components depend on it. |
| `.gemini-bento-page*` | Lines 15108-15242 and 16050/16166. | Confirmed in `ChatPage.tsx:1649` and `components/home-bento/PageChrome.tsx:113`. | Confirmed used, cross-surface bento shell. | Treat as shared bento skin, not Chat-only. |
| `.theme-shell--scanner`, `.shell-content-frame--scanner`, `.shell-main-column--scanner` | Lines 13740-13767 and 16440-16460. | Confirmed dynamic composition in `Shell.tsx:208`, `Shell.tsx:246`, `Shell.tsx:248`; tests assert scanner classes. | Confirmed used, shell route modifier. | Unsafe to change without scanner and shell route checks. |
| `.workspace-page--chat` / chat workspace selectors | Early chat selectors at 939/1305 plus SpaceX overrides at 10998 and 12574+. | `workspace-page--chat` itself is not used by `ChatPage` current tests expect it absent; `.gemini-bento-page--chat` is used. | Mixed: possible legacy for `.workspace-page--chat`, confirmed active for bento chat. | Verify with current route DOM before cleanup; do not assume all chat selectors are live. |
| `.theme-market-badge*` | Lines 1990-2032 and repeated theme overrides. | Only CSS references observed in this pass. | Needs verification / possible legacy. | Search market badge rendering paths before deletion; may be dynamically composed. |
| `.settings-*` | Variables at 462-486; classes at 3429-3544; repeated theme overrides. | Confirmed in `IntelligentImport.tsx`, `LLMChannelEditor.tsx`, `SettingsPage.tsx`, `SettingsCategoryNav.tsx`. | Confirmed used, Settings-owned shared utility set. | Keep. Consolidation should be Settings-scoped first. |
| `.glass-card` | Lines 2851-2888 plus theme overrides. | No non-CSS source reference found in representative `rg`. | Possible legacy / needs verification. | Candidate for dead-selector verification, not deletion. |
| `.terminal-card`, `.dashboard-card`, `.gradient-border-card` | Lines 2767-2847 and theme overrides. | No representative non-CSS source hit in this pass. | Possible legacy / needs verification. | Add to dead-selector candidate list; visual search required. |
| `.stealth-scrollbar`, `.custom-scrollbar` | Lines 6105-6128. | No representative source hit found; tests assert some routes should not use `stealth-scrollbar`. | Possible legacy or intentionally avoided. | Candidate for targeted usage audit. |
| `.no-scrollbar` | Lines 5-14; widespread source references across Portfolio, Chat, Scanner, Admin Logs, Market, Backtest, Watchlist, Settings, and tests. | Confirmed used. | Shared utility, active. | Do not consolidate away without replacing all usages and tests. |

## 6. Utility Duplication Candidates

| Candidate | Evidence | Possible consolidation direction | Risk |
| --- | --- | --- | --- |
| Ghost/glass panel utilities | `theme-panel-glass`, `theme-panel-solid`, `theme-card-surface`, `glass-card`, `home-panel-card`, `settings-surface`, and `product-section-card` repeat border/background/shadow/backdrop concepts. | Document canonical surface levels first: shell panel, product card, nested surface, page-specific accent. Then migrate one surface family at a time. | High. The design constitution requires deep-space/ghost-glass consistency, and these selectors are layered by theme. |
| Scrollbar utilities | `no-scrollbar`, `ui-scroll-x-quiet`, `stealth-scrollbar`, `custom-scrollbar`, global `::-webkit-scrollbar`, and repeated Tailwind arbitrary scrollbar hiding appear together. | Keep `no-scrollbar` as active utility; verify whether `stealth-scrollbar`/`custom-scrollbar` are still needed. | Medium/High. Scroll ownership is route-sensitive and tests assert some scrollbar classes. |
| Animation utilities | `animate-*`, `fade-in`, `zoom-in`, `spacex-*` keyframes, `boot-*`, loading shimmer, report reveal, and dashboard transitions. | Build a keyframe inventory by route and remove only after visual proof. | Medium. Animation selectors can be triggered by class names, state classes, or one-off transitions. |
| Safe-area/mobile utilities | Mobile root padding uses `env(safe-area-inset-*)`; many responsive overrides target shell, Home, Backtest, Chat, and report pages. | Keep global mobile shell rules separate from page-specific responsive rules in documentation. | High. Mobile regressions are likely without browser coverage. |
| Route/page section styles | Backtest, Home, Chat bento, Settings, Market, Scanner shell, report preview, and compare sections each have global CSS in the same file. | Add ownership comments or split only after proving import/order behavior. | High. CSS splitting is harder than JS splitting because cascade order is part of behavior. |
| Product primitive duplication | `product-*`, `metric-*`, `summary-*`, `preview-*`, `chart-card*`, and Backtest-specific overrides are repeated in classic and SpaceX layers. | Compare older and later blocks, then mark authoritative sections before deleting duplicates. | Medium/High. Some duplication is intentional override layering. |

## 7. CSS Optimization Risk Register

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| Deleting CSS without visual coverage is high risk. | Many selectors are page-specific, route-modified, or dynamically composed. | Require source usage proof plus route visual checks before deletion. |
| Tailwind generated output may include expected utilities. | The built CSS asset includes Tailwind output from `@import "tailwindcss"` plus project CSS. | Do not equate built CSS size with hand-authored dead CSS. |
| Page-specific selectors may still be used by dynamic class names. | Shell route classes are composed in `Shell.tsx`; other state classes may be conditional. | Search source and tests, then inspect rendered DOM where needed. |
| Design constitution requires deep-space/ghost-glass consistency. | Surface utilities are part of the product visual language, not decorative extras. | Document token ownership before consolidation. |
| CSS splitting may be harder than JS splitting. | Cascade order, theme overrides, and route modifiers are globally ordered. | Prefer documentation and selector verification before code splitting. |
| Repeated blocks may be override layers, not duplication. | Later SpaceX and structural correction sections intentionally supersede earlier classic/terminal rules. | Identify authoritative owner and affected route before touching. |
| Build output is generated and should stay out of commits. | `npm run build` writes `static` output. | Keep staging limited to this report file only. |

## 8. Recommended Next Tasks

| Task | Scope | Files likely touched | Risk | Tests/checks | Parallel with frontend UI work? |
| --- | --- | --- | --- | --- | --- |
| CSS Selector Usage Verification | Build a candidate list for `glass-card`, `terminal-card`, `dashboard-card`, `gradient-border-card`, `stealth-scrollbar`, `custom-scrollbar`, and `theme-market-badge`. | New audit doc or temporary scripts only first; later maybe `apps/dsa-web/src/index.css`. | Low for audit, high for deletion. | `rg`, rendered DOM checks for target routes, `npm run build`, `npm run check:design`. | Yes if read-only; no if deleting CSS. |
| CSS Token Section Documentation | Add comments or a doc mapping token groups to Shell, Home, Settings, Backtest, Report, Scanner, and Market. | Prefer `docs/audits/*` first; only later `src/index.css` comments if approved. | Low. | Markdown review; no browser needed for docs-only. | Yes. |
| Backtest/Scanner CSS Visual Regression Checklist | Define route screenshots/states before any Backtest or Scanner CSS cleanup. | New docs/checklist; later Playwright or visual fixtures if approved. | Low for checklist, medium for test automation. | `npm run build`, `npm run check:design`, Safari/in-app browser route checks when UI changes. | Yes as docs-only. |
| Design Guard Warning Burn-down Phase 4 | Continue reducing current 39 advisory `native-ui` warnings by surface. | Component/page files with warning hits, not `index.css` first. | Medium. | `npm run check:design`, `npm run lint`, `npm run build`, browser checks for touched pages. | Partly; coordinate by page. |
| CSS Dead Selector Candidate Verification | For each candidate, prove unused with source search, tests, rendered DOM, and route coverage before deletion. | `apps/dsa-web/src/index.css` only after proof. | High. | Full targeted page visual checks plus build/design/lint. | No; deletion should be serialized. |
| CSS Ownership Comments Pass | If approved, add compact section comments around authoritative large blocks without changing rules. | `apps/dsa-web/src/index.css`. | Medium due to touching large CSS file. | `git diff --check`, `npm run build`, `npm run check:design`. | Not ideal with UI work because it touches the central CSS file. |

## 9. Non-Goals

- No CSS changed.
- No product code changed.
- No frontend components or pages changed by this audit.
- No tests changed.
- No backend files changed.
- No Tailwind, Vite, PostCSS, design guard, package, or runtime config changed.
- No dependencies installed.
- No dev servers started, killed, or restarted.
- No browser verification performed or required.
- No `docs/CHANGELOG.md` change.
- No generated build output, sourcemaps, screenshots, analyzer files, or temp files committed.

## 10. Validation Notes

Report validation commands required for this task:

```bash
cd /Users/yehengli/daily_stock_analysis
sed -n '1,320p' docs/audits/wolfystock-css-ownership-inventory.md
git diff --check -- docs/audits/wolfystock-css-ownership-inventory.md
```

Markdown lint status: no markdown lint script was found. The repository root has no `package.json`; `apps/dsa-web/package.json` scripts are `dev`, `build`, `check:design`, `lint`, `test`, `test:e2e`, `test:smoke`, and `preview`.

Full `./scripts/ci_gate.sh` status: not run. This is a docs-only report task and the requested validation did not require full backend CI.

Worktree note: preflight started clean. After read-only/build commands, `apps/dsa-web/src/pages/ChatPage.tsx` appeared dirty with attribute-order and class changes unrelated to this audit. It was inspected only enough to avoid staging it and must remain uncommitted by this task.
