# WolfyStock Frontend Design Conformance Audit

Date: 2026-05-05 Asia/Shanghai  
Repository: `/Users/yehengli/daily_stock_analysis`  
Branch: `main`  
Mode: audit/report only; no product code, tests, CSS, backend/API, package, config, runtime, or changelog changes

## 1. Executive Summary

Overall design conformance grade: **B**. The current frontend is materially aligned with the WolfyStock design constitution: dark deep-space shell, ghost-glass cards, Chinese-first labels, hidden raw diagnostics, and design guard at 0 warnings. It is not yet fully constitution-conformant at the route-composition level.

Strongest surfaces:

- `/zh/backtest/results/1`: coherent deep-space result shell, compact data-first hierarchy, no mobile overflow.
- `/zh/settings/system`: strong operator control-plane language, dense but readable subsystem cards, developer/raw details not default-open.
- `/zh/market-overview`: route-level card density is high but the visual language is consistent and freshness/fallback states are honest.
- `/zh/watchlist`: good shell/frame alignment and compact workflow actions.

Weakest surfaces:

- `/zh/__preview/report`: polished report content, but visually separate from the main shell primitives; chart toggle chips are too small on mobile and card count is very high.
- `/zh/portfolio`: useful populated-data layout, but tabs/action chips remain around 29 px and card hierarchy is over-fragmented.
- `/zh/settings`, `/zh/admin/logs`, `/zh/chat`: visually consistent, but dense controls still fall below comfortable touch-target height.
- `/zh/scanner`: live route was auth-gated in the existing dev server; the isolated mock fixture was blocked by a mock shape mismatch, so this pass cannot claim full scanner visual conformance.

Highest-priority design debt: **canonical primitive ownership**. The app has many route-local versions of cards, command bars, status chips, icon buttons, dense tabs, and developer details. Passing `npm run check:design` is necessary, but not sufficient: the guard now catches repeatable banned patterns, while this audit still found card over-fragmentation, sub-32 px controls, route-local chip variants, and preview/shell visual drift.

## 2. Methodology

Commands run:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -80
./scripts/task_preflight.sh || true

cd apps/dsa-web
npm run check:design
npm run lint
npm run build

cd /Users/yehengli/daily_stock_analysis
python3 -m compileall -q src api
./scripts/ci_gate.sh
```

Mandatory reading completed:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- workflow and Portfolio QA reports
- parallel Codex playbook
- design guard and CI clarity docs
- global, bundle, CSS ownership, CSS selector, and ECharts audit reports

Playwright/browser method:

- Temporary Playwright script: `/tmp/wolfystock_design_audit.mjs`
- Temporary result JSON: `/tmp/wolfystock_design_audit_results.json`
- Browser: headless Chromium through the existing `apps/dsa-web` Playwright install
- Primary URL: `http://127.0.0.1:5176`
- Secondary auth-gate check for Scanner: existing `http://127.0.0.1:5173`
- Viewports: desktop `1440x1000`, mobile `390x844`
- Data/auth: mocked authenticated admin for most protected routes; existing live dev server showed `/zh/scanner` auth-gated only

Ports:

| Port | Status | Use |
| --- | --- | --- |
| `8000` | Existing Python backend listener | Observed only; not restarted |
| `8001` | Free | Not used |
| `5173` | Existing Vite/Codex frontend listener | Reused only for scanner auth-gate observation |
| `4173` | Free | Not used |
| `5174` | Free | Not used |
| `5175` | Free | Not used |
| `5176` | Free, then started isolated preview | Used for Playwright mock review; stopped and confirmed free |

Limitations:

- Most route checks are **mock verified**, not live-data verified.
- `/zh/scanner` is **auth-gated only** in the live dev-server check; the isolated mock fixture did not fully satisfy the Scanner page contract.
- EventSource console errors on Home and Market Overview came from mocking stream endpoints as JSON; they are fixture limitations, not product-code findings.
- No screenshots, videos, traces, Playwright reports, sourcemaps, or temp files are intended for commit.

## 3. Static Baseline

| Check | Result | Key output | Notes |
| --- | --- | --- | --- |
| `pwd` | PASS | `/Users/yehengli/daily_stock_analysis` | Required path. |
| Branch | PASS | `main` | Required branch. |
| Initial preflight | PASS | clean; `origin/main` ahead 0 / behind 0 | Later unrelated frontend/settings dirty files appeared; not touched. |
| `npm run check:design` | PASS | 214 files scanned; 0 blocking; 0 warnings | Guard is clean after recent polish. |
| `npm run lint` | PASS | `eslint .` exited 0 | No lint output. |
| `npm run build` | PASS with warning | 3158 modules transformed; built in 9.33s | Vite warns on lazy `DeterministicBacktestChartWorkspace-BYXXEcda.js` 532.42 kB / 178.83 kB gzip. |
| Backend compile | PASS | `python3 -m compileall -q src api` exited 0 | No output. |
| `./scripts/ci_gate.sh` | PASS | 1993 passed, 3 skipped, 1 warning, 203 subtests in 154.86s | Local optional-tool warnings: `flake8` and `akshare` missing. |

## 4. Route Conformance Matrix

| Route | Mode | Desktop conformance | Mobile conformance | Shell/frame | Card hierarchy | Controls | Status/chips | Typography/copy | Developer details | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/zh` | mock verified | Good | Mixed | Good | Good | Mixed | Good | Good | Good | No overflow; detail disclosure buttons measured 18 px high; stream mock emitted JSON EventSource console error. |
| `/zh/scanner` | auth-gated only | Limited | Limited | Good gate | Not assessed | Not assessed | Not assessed | Good gate copy | Not assessed | Existing dev server rendered login gate cleanly; full route cannot be claimed. |
| `/zh/watchlist` | mock verified | Good | Good | Good | Good | Mixed | Good | Good | Good | Batch buttons around 28 px; otherwise coherent. |
| `/zh/backtest` | mock verified | Good | Mixed | Good | Mixed | Mixed | Good | Good | Good | Segmented controls/tabs around 28 px; form shell is consistent. |
| `/zh/backtest/results/1` | mock verified | Good | Good | Good | Good | Good | Good | Good | Good | Strongest route-level result surface; no overflow or errors. |
| `/zh/portfolio` | mock verified | Mixed | Mixed | Good | Mixed | Mixed | Mixed | Good | Good | Populated holdings rendered; many route-local tabs/action chips around 29 px; card count high. |
| `/zh/market-overview` | mock verified | Good | Good | Good | Mixed | Good | Good | Good | Good | Honest freshness/fallback language; high card density but consistent material. |
| `/zh/settings` | mock verified | Mixed | Mixed | Good | Good | Mixed | Good | Good | Good | Font-size segmented buttons 31 px; password visibility icon buttons 25 px; checkbox inputs 14 px. |
| `/zh/settings/system` | mock verified | Good | Good | Good | Good | Good | Good | Good | Good | Strong operator control-plane surface; developer/raw labels visible only as collapsed affordances. |
| `/zh/admin/logs` | mock verified | Mixed | Mixed | Good | Good | Mixed | Good | Good | Good | Category tabs around 31 px; raw-log concept is separated from primary event view. |
| `/zh/admin/notifications` | mock verified | Good | Good | Good | Good | Mixed | Good | Good | Good | Uses `displayStatus`-aligned labels; checkbox input is still native-size 14 px. |
| `/zh/chat` | mock verified | Mixed | Mixed | Good | Mixed | Mixed | Good | Good | Good | Dense lens buttons around 30-31 px; mobile console trigger measured 18 px. |
| `/zh/__preview/report` | mock verified | Mixed | Mixed | Different | Mixed | Weak | Good | Good | Good | No overflow; report is polished, but preview shell diverges from main route material and chart toggles are 22-27 px. |

## 5. Cross-Route Design Debt

Shell/page frame:

- Main protected routes mostly use the expected deep-space shell and wide workspace frame.
- Preview report uses `workspace-page--preview` / preview shell styling and feels route-adjacent rather than fully unified with the operational shell.
- Scanner cannot be fully judged because current live route was auth-gated.

Card hierarchy:

- The ghost-glass direction is consistent, but hierarchy is often expressed by repeated `rounded/border/bg-white/[...]` variants instead of canonical surface levels.
- Portfolio, Market Overview, and Preview Report have very high card-like element counts; this creates visual fragmentation even when individual cards look acceptable.
- Nested diagnostics/details generally stay visually quieter than primary cards, which matches the constitution.

Buttons/icon buttons:

- Primary/ghost/destructive patterns are mostly aligned with recent Button/Input/Select polish.
- Repeated route-local segmented controls still fall below comfortable touch targets: Home detail disclosures, Backtest tabs, Portfolio tabs, Settings visibility icons, Admin Logs tabs, Chat lenses, and Preview chart toggles.
- Shell language/logout controls remain compact on desktop, consistent with previous QA observations.

Inputs/selects/controls:

- Design guard reports 0 native-control warnings, so obvious unstyled controls are gone.
- Checkboxes remain native-size in Settings and Admin Notifications; wrappers may be visually acceptable but touch-target policy is not fully resolved.
- Portfolio uses shared `Input`/`Select` heavily, but English labels such as `TRADE DATE`, `QUANTITY`, `PRICE`, `FEE`, and `NOTE` remain visible in the Chinese route and should be reviewed against the Chinese UI rule.

Status chips:

- `displayStatus` adoption improved Admin Notifications and related status labels.
- Market Overview freshness/fallback/cache language is honest and should remain domain-specific rather than collapsed into generic status.
- Portfolio, Backtest, Scanner, Watchlist, and Admin Logs still have route-local chip/tone vocabularies that need adapter-level consolidation.

Typography/copy:

- Chinese UI copy is broadly compact and professional.
- Allowed English terms appear in tickers, metrics, providers, currencies, and report market terms.
- Preview report still exposes English product/company names by domain necessity, but its preview/report chrome should remain under review.

Empty/loading/failure states:

- Empty states are generally quiet and useful.
- Mock-gated Scanner prevents a full empty/failure-state assessment here.
- EventSource stream errors in the audit fixture should not be treated as visible product failures.

Developer details:

- Developer/raw sections are mostly collapsed or represented as explicit `开发者细节`, `原始诊断`, `数据质量`, or `执行假设` affordances.
- No default-visible raw secret/API-key/schema strings were found in the Playwright text scan.

Mobile density/touch targets:

- No audited route showed horizontal overflow at `390x844`.
- Sub-32 px controls remain the most repeatable visual conformance gap.
- Mobile density is usually readable, but Portfolio and Preview Report remain vertically noisy.

CSS/selector ownership risk:

- CSS ownership and selector audits show active shell route modifiers, active report/backtest/scanner primitives, and several CSS-only cleanup candidates.
- CSS deletion should be blocked until a visual regression checklist exists and target routes are DOM-verified.

## 6. Canonical Primitive Candidates

| Primitive | Current scattered implementations | Recommended owner/file | Risk | First migration target |
| --- | --- | --- | --- | --- |
| `PageShell` | `Shell`, preview shell, route-local `main` wrappers | `apps/dsa-web/src/components/layout` | High | Document shell route modifiers first; do not migrate Preview until checklist exists. |
| `SurfaceCard` | `GlassCard`, `SectionShell`, route-local rounded/border cards | `apps/dsa-web/src/components/common` | Medium | Admin Notifications or Watchlist cards. |
| `NestedCard` | `bg-white/[0.025]`, `bg-black/20`, report subpanels | `components/common` plus report adapter | Medium | Portfolio nested risk/exposure blocks. |
| `CommandBar` | Watchlist command bar, Scanner action strip, Market refresh rail, Backtest tabs | `components/common` | Medium | Watchlist command bar, then Scanner. |
| `Button/IconButton` | common `Button`, Scanner `ActionButton`, route-local chip buttons | `components/common/Button.tsx` | Medium | Preview chart toggle buttons and Backtest tabs. |
| `Input/Select/Checkbox` | common primitives plus route-local checkbox wrappers | `components/common` | Medium | Settings/Admin checkbox wrappers. |
| `StatusChip` | `StatusBadge`, `displayStatus`, route-local tones | `utils/displayStatus` + `components/common/StatusBadge` | Medium | Admin Logs generic status chips. |
| `FreshnessBadge` | Market freshness adapters, scanner/watchlist provider states | Market-owned adapter, not generic-only | Medium | Market Overview stays owner; expose docs contract. |
| `DeveloperDetails` | details/disclosure patterns across Home, Scanner, Backtest, Admin, Report | `components/common/DeveloperDetails.tsx` | Medium | Admin Notifications or System Settings. |
| `EmptyState` | route-local empty cards and failure copy | `components/common` | Low/Medium | Watchlist and Portfolio empty states. |
| `MetricCard` | Portfolio, Backtest result, Market temperature, Report summary | `components/common` or route-specific adapters | Medium | Backtest result metric tiles. |
| Mobile action rail/touch-target pattern | Portfolio tabs, Backtest tabs, Preview chart toggles, Chat console trigger | `components/common` | Medium | Preview chart toggles and Backtest segmented controls. |

## 7. Prioritized Follow-Up Tasks

| ID | Priority | Title | Affected surfaces | Likely files | Expected benefit | Risk | Tests/checks | Parallel? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FDA-01 | P0 | Canonical UI Primitive Spec | All frontend routes | new docs/check or `docs/audits/*` | Defines surface/card/button/status ownership before code churn | Low | markdown inspection, `git diff --check` | Yes |
| FDA-02 | P1 | One-surface UI Primitive Migration | Watchlist or Admin Notifications first | `WatchlistPage.tsx` or `AdminNotificationsPage.tsx`, common components | Proves primitive path with low blast radius | Medium | page tests, `check:design`, lint, build, desktop/mobile browser | No with same surface |
| FDA-03 | P1 | Mobile Touch Target Phase 2 | Home, Backtest, Portfolio, Settings, Admin Logs, Chat, Preview | route-local controls plus common Button/IconButton/Checkbox | Resolves most visible post-guard gap | Medium | Playwright/Safari `390x844`, `check:design`, lint, build | Split by route, shared primitive serialized |
| FDA-04 | P1 | Status Utility Phase 3 | Admin Logs, Backtest, Portfolio, Scanner/Watchlist adapters | `displayStatus`, `StatusBadge`, route status helpers | Reduces duplicated chip/tone language | Medium | status utility tests plus page tests | Shared utility serialized |
| FDA-05 | P1 | Preview Report Shell Alignment | `/zh/__preview/report` | `PreviewReportPage.tsx`, report primitives, preview shell docs | Brings preview route closer to shell/card constitution | Medium | Preview tests, desktop/mobile visual checks | No with report CSS work |
| FDA-06 | P2 | Portfolio Card Hierarchy Pass | `/zh/portfolio` | `PortfolioPage.tsx`, common card primitive | Reduces over-fragmented nested surfaces | Medium | Portfolio tests, populated route browser check | Yes if no shared primitive edit |
| FDA-07 | P2 | Scanner Full Authenticated Visual Pass | `/zh/scanner` | QA fixture or local auth setup first | Completes the only route not fully assessed here | Low as audit | authenticated/mock Playwright, no product edits | Yes |
| FDA-08 | P2 | CSS Visual Regression Checklist Before CSS Deletion | CSS cleanup candidates | new checklist doc | Prevents selector deletion regressions | Low | route checklist, `git diff --check` | Yes |
| FDA-09 | P2 | Chinese Form Label Review | Portfolio, Settings, Backtest | route copy/constants | Aligns Chinese UI rule after native-control polish | Low/Medium | page tests, visual review | Yes by route |

## 8. Suggested Parallelization Plan

Can run together:

- `FDA-01` Canonical UI Primitive Spec and `FDA-08` CSS Visual Regression Checklist.
- `FDA-07` Scanner authenticated visual pass with Portfolio or Preview report audit-only work.
- Route-local touch-target passes if they do not edit shared Button/Input/Select/Status files.
- Status copy inventory and CSS selector DOM verification as separate read-only tasks.

Must be serialized:

- Any shared `Button`, `Input`, `Select`, `Checkbox`, `StatusBadge`, or `displayStatus` change before route migrations.
- Preview report shell alignment and report CSS cleanup.
- CSS selector deletion and any route-level visual redesign.
- Portfolio card hierarchy work and Portfolio accounting/data-flow changes.
- Scanner visual migration and Scanner/backtest workflow behavior changes.

## 9. Non-Goals

- No product code changed.
- No tests changed.
- No CSS changed.
- No backend/API changed.
- No package files or config changed.
- No `docs/CHANGELOG.md` changed.
- No generated artifacts committed.
- No issues fixed in this task.

## 10. Appendix

Preflight:

- `pwd`: `/Users/yehengli/daily_stock_analysis`
- branch: `main`
- initial `git status --short`: clean
- initial upstream: `origin/main`, ahead 0 / behind 0

Route observations:

- Routes checked: `/zh`, `/zh/scanner`, `/zh/watchlist`, `/zh/backtest`, `/zh/backtest/results/1`, `/zh/portfolio`, `/zh/market-overview`, `/zh/settings`, `/zh/settings/system`, `/zh/admin/logs`, `/zh/admin/notifications`, `/zh/chat`, `/zh/__preview/report`
- Desktop viewport: `1440x1000`
- Mobile viewport: `390x844`
- Horizontal overflow: `0` for all successfully inspected routes
- Gray solid background class count: `0` in inspected visible DOM samples
- Raw/debug leakage terms: no default-visible raw secret/schema/API-key terms found
- Generated screenshots/videos/traces: none retained

Representative small-control findings:

- Home report detail disclosures: 18 px high.
- Watchlist batch buttons: 28 px high.
- Backtest segmented controls: 28 px high.
- Portfolio tabs/action chips: 29 px high.
- Settings password visibility icon buttons: 25 px; checkbox inputs: 14 px.
- Admin Logs category tabs: 31 px high.
- Admin Notifications checkbox input: 14 px.
- Chat desktop lens buttons: 30 px; mobile console trigger: 18 px.
- Preview report chart toggles: 22-27 px high.

Static command summary:

```text
npm run check:design
Files scanned: 214
Design guard passed. No blocking violations or warnings found.

npm run lint
eslint . exited 0

npm run build
3158 modules transformed
DeterministicBacktestChartWorkspace-BYXXEcda.js 532.42 kB / gzip 178.83 kB
Some chunks are larger than 500 kB after minification.
built in 9.33s

python3 -m compileall -q src api
exited 0

./scripts/ci_gate.sh
1993 passed, 3 skipped, 1 warning, 203 subtests passed in 154.86s
backend-gate completed successfully
```

Markdown lint status:

- No markdown lint script was found in the root checkout or `apps/dsa-web/package.json`.

Parallel safety note:

- After the initial clean preflight, unrelated dirty files appeared under `apps/dsa-web/src/components/settings`, `apps/dsa-web/src/pages`, and `apps/dsa-web/src/api`. They were not modified, staged, formatted, reverted, or committed by this audit.
