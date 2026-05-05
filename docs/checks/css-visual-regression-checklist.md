# CSS Visual Regression Checklist Before CSS Deletion

Date: 2026-05-05 Asia/Shanghai
Repository: `/Users/yehengli/daily_stock_analysis`
Scope: docs-only CSS governance checklist

## 1. Executive Summary

WolfyStock's global CSS is not a loose collection of unused selectors. The CSS ownership inventory and selector usage verification show a single ordered cascade that contains global foundation rules, route shell modifiers, product primitives, late corrective overrides, and mobile/scroll ownership fixes. Some selectors have weak static source evidence, but others are dynamically composed by route shell code or shared across surfaces with names that do not match their current owner.

This checklist is required before any future CSS selector deletion, global CSS splitting, or cascade-order cleanup. It exists to prevent deletion based on static search alone. `rg` and CSS selector summaries can identify candidates, but they cannot prove that a route no longer emits a class at runtime, that a dynamic shell modifier is safe to remove, or that a design primitive has no cascade effect through later override layers.

Use this checklist when a future task proposes to:

- remove one or more selectors from `apps/dsa-web/src/index.css`;
- split global CSS into route or component files;
- migrate shared shell, scrollbar, card, bento, report, chart, settings, scanner, or backtest CSS ownership;
- remove a selector classified as "CSS-only", "likely dead", "legacy", or "weak evidence" by prior audits.

Passing this checklist does not authorize broad cleanup. It authorizes only a tightly scoped deletion trial for the named selector family, with explicit rollback.

## 2. CSS Deletion Policy

- Do not delete CSS from `rg`, grep, selector counts, or build-size evidence alone.
- Do not delete dynamic shell modifiers without owner migration and route proof. This includes `theme-shell--*`, `shell-content-frame--*`, `shell-main-column--*`, and `workspace-page--*`.
- Do not delete design primitives without route proof. Card, glass, bento, report, chart, settings, scrollbar, and status-chip selectors can affect visual hierarchy even when source references are sparse.
- Delete at most one selector family per trial. A family can include a base selector and direct modifiers, but it must not combine unrelated surfaces such as Scanner shell and Backtest result bento.
- Keep product feature work separate from CSS deletion. Do not combine selector deletion with route redesign, preview shell redesign, shared primitive migration, behavior changes, tests rewrites, or backend/API changes.
- Preserve cascade order unless the task is explicitly a CSS splitting or cascade migration task with its own route-level proof.
- If any required route shows horizontal overflow, blank/black state, native fallback, lost deep-space material, clipped controls, or unexpected debug/raw visibility, stop the deletion trial and keep the selector.
- Rollback guidance: restore the deleted selector family from the previous commit, rerun the same route checks, and report the failed route/state that required rollback.

## 3. Selector Risk Register

| Selector/prefix | Current classification | Owner/surface | Risk | Required proof before deletion | Recommended first action |
| --- | --- | --- | --- | --- | --- |
| `glass-card` | Likely dead / needs DOM proof | Classic glass/card primitive | Medium | Source search, rendered DOM absence on Home, Settings, Chat, Market Overview, and preview report; visual proof that ghost-glass hierarchy is unchanged. | Run read-only DOM verification; do not delete with other card primitives. |
| `terminal-card` | Likely dead / needs DOM proof | Classic terminal/card primitive | Medium | Rendered DOM absence and proof that `home-panel-card` or report surfaces do not depend on inherited terminal material. | Verify DOM and compare Home/report card hierarchy. |
| `dashboard-card` | Likely dead / needs DOM proof | Legacy dashboard primitive | Medium | Rendered DOM absence on Home, Market Overview, Portfolio, and admin routes; no card hierarchy regression. | Verify route DOM before any removal trial. |
| `gradient-border-card` | Likely dead / needs DOM proof | Classic gradient wrapper primitive | Medium | DOM absence for wrapper/inner pairing; no lost border/glow effect on preview/report or command-card surfaces. | Verify all candidate wrapper markup, then trial alone. |
| `workspace-page--chat` | Likely dead / needs DOM proof | Legacy chat workspace modifier | Medium | `/zh/chat` full ancestor DOM absence at desktop/mobile; proof active `gemini-bento-page--chat` remains intact. | Inspect Chat route DOM and tests; do not touch bento selectors. |
| `stealth-scrollbar` | Likely dead / test-only negative evidence | SpaceX scrollbar utility | Medium | DOM absence across route rails and scroll containers; default scrollbars remain hidden through active utilities. | Query scroll containers on every required route. |
| `backtest-entry-shell` | Likely dead / weak class evidence | Backtest entry/setup shell | Medium | `/zh/backtest` DOM absence as a class, not just `data-testid`; entry/setup view unchanged at both viewports. | Verify class vs `data-testid` before considering deletion. |
| `product-command-card` | CSS-only / design primitive risk | Product/backtest command surfaces | High | DOM absence on Backtest, Scanner, preview report, Home, and any command/workbench states; no cascade effect from product override layers. | Do not use as first deletion trial; document owner first. |
| `theme-shell--scanner` | Do-not-delete without owner migration | Scanner route shell | High | Owner migration plan, Shell route DOM proof, scanner route visual proof, and shell tests updated only in a dedicated task. | Keep; document as route infrastructure. |
| `shell-content-frame--scanner` | Do-not-delete without owner migration | Scanner content frame | High | Owner migration plan and proof scanner height/overflow behavior is preserved. | Keep; verify if scanner shell is migrated. |
| `shell-main-column--scanner` | Do-not-delete without owner migration | Scanner main column | High | Owner migration plan and mobile/desktop scanner scroll proof. | Keep; treat as scroll ownership. |
| `custom-scrollbar` | Do-not-delete without owner migration | Shared `ScrollArea` utility | High | Replacement utility, all `ScrollArea` consumers verified, default scrollbars not exposed. | Keep; migrate only through shared component ownership. |
| `theme-market-badge` | Do-not-delete without owner migration | Stock autocomplete market badge | High | Source and DOM proof for all market badge variants, plus readability checks. | Keep; dynamic modifier mapping is active. |
| `backtest-void-workspace` | Do-not-delete without owner migration | Deterministic result/chart workspace | High | Backtest result route visual proof and chart workspace DOM proof after an owner migration. | Keep; active result workspace primitive. |
| `backtest-result-bento` | Do-not-delete without owner migration | Backtest result hero/KPI bento | High | `/zh/backtest/results/1` desktop/mobile visual proof with populated data. | Keep; active result bento primitive. |
| `gemini-bento-page` | Do-not-delete without owner migration | Chat and home-bento page chrome | High | Chat and home-bento DOM proof plus visual proof after migration. | Keep; shared bento skin. |
| `settings-surface` | Do-not-delete without owner migration | Settings/system settings surfaces | High | Personal/system settings route proof; raw config stays collapsed and visual hierarchy remains intact. | Keep; migrate only in Settings-owned task. |
| `home-panel-card` | Do-not-delete without owner migration | Report/Home shared panels | High | Home and preview/report DOM proof; report card hierarchy unchanged. | Keep; name is misleading because report components use it. |
| `home-subpanel` | Do-not-delete without owner migration | Report/Home nested panel | High | Report news/details DOM proof; nested hierarchy unchanged. | Keep unless report owner migrates it. |
| `chart-card` | Do-not-delete without owner migration | Backtest comparison/chart primitive | High | Backtest compare/result chart visual proof and DOM replacement. | Keep; active chart primitive. |
| `comparison-card` | Do-not-delete without owner migration | Backtest comparison panels | High | Backtest comparison route/component proof and card hierarchy unchanged. | Keep; active comparison primitive. |

## 4. Route Visual Checklist

Every future deletion PR must record the evidence location for each route. Evidence can be a local notes file, terminal output, screenshot path, or Playwright trace path, but generated screenshots, videos, traces, logs, and reports must not be committed.

Required viewports:

- desktop `1440x1000`
- mobile/narrow `390x844` or `390x900`

Required visual checks for every route:

- no horizontal overflow;
- no blank/black route state after route load;
- no shell/header obstruction;
- no card border, shadow, blur, or hierarchy regression;
- no lost ghost-glass or deep-space material;
- no visible solid gray/native fallback;
- no default scrollbars exposed;
- no mobile clipped controls or hidden/overlapping text;
- no sub-32px touch target regression where the route has actionable controls;
- status chips remain readable;
- raw/debug/provider/schema details are not default-visible;
- route-specific dynamic shell modifiers remain present or have documented owner migration proof.

| Route | Required mode/live-mock-auth-gated | Desktop checks | Mobile checks | Critical components | Selector families likely affected | Required evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `/zh` | Mock or live authenticated Home where possible; auth gate acceptable only if candidate cannot affect Home content. | Shell, Home cards, report history, decision summary, developer details collapsed. | No overflow, no clipped report/history controls, touch targets not worse than baseline. | Home shell, report cards, history rows, decision trace affordance. | `glass-card`, `terminal-card`, `dashboard-card`, `home-panel-card`, `home-subpanel`, `product-command-card`. | Screenshot or DOM notes for shell classes, card selectors, overflow width, collapsed details. |
| `/zh/scanner` | Prefer authenticated/mock populated scanner; auth gate is not enough for scanner shell selector deletion. | Scanner command bar, candidate table/cards, diagnostics, result history, shell height. | Scanner controls visible, scroll ownership correct, no clipped batch actions. | Scanner shell/content/main column, command bar, diagnostics, candidate rows. | `theme-shell--scanner`, `shell-content-frame--scanner`, `shell-main-column--scanner`, `product-command-card`, scrollbar utilities. | DOM class query proving shell modifiers; screenshots/notes for populated and empty states. |
| `/zh/watchlist` | Authenticated/mock populated plus empty state if practical. | Watchlist command bar, filters, selected rows, row actions. | No overflow in rows; selection and action targets not regressed. | Watchlist table/cards, intelligence workflow actions, status chips. | Card primitives, scrollbar utilities, status chip families. | Overflow measurement, row/action screenshot, status chip readability note. |
| `/zh/backtest` | Authenticated/mock Backtest entry/setup with normal/pro/deterministic controls. | Entry shell, tabs, setup form, command/workbench surfaces. | Form controls not clipped, tabs/actions not smaller than baseline, scroll works. | Backtest entry/setup, deterministic controls, command cards. | `backtest-entry-shell`, `product-command-card`, `chart-card`, scrollbar utilities. | DOM query distinguishing class from `data-testid`; desktop/mobile screenshots or notes. |
| `/zh/backtest/results/1` | Mock/live populated deterministic result route. | Result bento, chart workspace, KPI cards, assumptions/details collapsed. | No blank lazy state, no chart/card clipping, details still usable. | Result hero/KPI bento, void/chart workspace, audit/details panels. | `backtest-result-bento`, `backtest-void-workspace`, `chart-card`, `comparison-card`, scrollbar utilities. | Route-load proof, bento/workspace DOM classes, overflow and blank-state checks. |
| `/zh/portfolio` | Populated holdings preferred; also empty/data-limited state if practical. | Holdings, FX transparency, risk drilldown, tabs/action chips. | No horizontal row overflow; chips/actions not clipped or newly sub-32px. | Portfolio bento/cards, holdings rows, risk/FX panels, status chips. | Card primitives, status chips, scrollbar utilities. | Populated or data-limited evidence label, overflow measurement, risk/FX screenshot. |
| `/zh/market-overview` | Mock/live populated market overview with fallback/stale state if practical. | Market freshness, provider/fallback panels, market badges, cards. | No clipped tabs/buttons; freshness/status chips readable. | Market overview shell, provider panels, market badges, refresh controls. | `theme-market-badge`, `dashboard-card`, `glass-card`, scrollbar utilities. | Badge DOM/query proof, fallback/freshness screenshot, overflow notes. |
| `/zh/settings` | Authenticated personal settings. | Settings surfaces, personal controls, provider/settings sections, details collapsed. | Password/icon controls, toggles, and form rows not clipped or regressed. | Settings cards, `settings-surface`, inputs/selects/toggles, developer details. | `settings-surface`, card primitives, native-control-related CSS. | DOM class query, raw secret invisibility note, mobile control screenshot. |
| `/zh/settings/system` | Admin/authenticated system settings. | Runtime health, config validation, connectivity probe remain distinct; developer details collapsed. | Subsystem cards readable; no raw config default visibility. | System settings cards, config groups, raw/developer details. | `settings-surface`, scrollbar utilities, card primitives. | Collapsed/expanded details note where safe, raw/debug visibility check. |
| `/zh/admin/logs` | Admin/authenticated populated logs plus empty state if practical. | Log list, filters, status/level chips, raw metadata collapsed. | Tabs/filters readable; no exposed default scrollbar or clipped chips. | Admin log rows, filters, raw metadata details, status chips. | Card primitives, status chips, scrollbar utilities. | Log row screenshot, collapsed raw metadata proof, overflow measurement. |
| `/zh/admin/notifications` | Admin/authenticated rules populated plus empty/fallback state if practical. | Rule cards, masked targets, dry-run/test-send controls, status labels. | Rule action controls not clipped; masked target copy readable. | Notification rule cards, action buttons, status labels, checkboxes. | Card primitives, native-control CSS, status chips. | Screenshot/DOM notes for rule cards, masked target, no raw secret visibility. |
| `/zh/chat` | Authenticated/mock chat; full route required for Chat selectors. | Chat bento shell, lens controls, provider health, evidence context. | Console trigger/lens controls not clipped; chat scroll works. | `gemini-bento-page`, `gemini-bento-page--chat`, chat panels, evidence/context cards. | `workspace-page--chat`, `gemini-bento-page`, scrollbar utilities, card primitives. | Full ancestor DOM query proving `workspace-page--chat` absence/presence and bento classes. |
| `/zh/__preview/report` | Mock/live preview report with populated content. | Preview shell, report sections, chart toggles, report cards, details collapsed. | No clipped chart toggles, no preview shell/card drift, no overflow. | Preview shell, report cards, chart cards, news/details sections. | `workspace-page--chat` not relevant; `glass-card`, `terminal-card`, `gradient-border-card`, `home-panel-card`, `home-subpanel`, `chart-card`, `product-command-card`. | Preview route screenshot, DOM selector query, card hierarchy and mobile toggle notes. |

State coverage requirements:

- Auth gate where relevant: verify the candidate selector cannot affect only the authenticated route before accepting auth-gate-only proof.
- Populated data where relevant: required for Backtest results, Portfolio, Market Overview, Watchlist, Scanner, Admin Logs, and preview report when the selector styles content cards/tables.
- Empty state where relevant: required when the selector styles empty, fallback, or void workspace surfaces.
- Loading state if practical: capture route skeleton/lazy-load behavior for Backtest result and data-heavy routes.
- Error/fallback state if practical: capture provider/freshness/fallback panels for Market Overview, Scanner, Portfolio, Settings/System, and Admin surfaces.
- Developer details collapsed: required by default on routes with diagnostics/raw metadata.
- Developer details expanded: only for CSS-specific checks and only when safe; do not expose secrets in committed artifacts or docs.

## 5. Playwright Verification Template

Use this prose template in future Codex prompts for CSS deletion work:

```text
Run route-level Playwright verification for the candidate selector family:

- Candidate selector family: <selector or prefix>
- Viewports: desktop 1440x1000 and mobile 390x844 or 390x900
- Routes: /zh, /zh/scanner, /zh/watchlist, /zh/backtest, /zh/backtest/results/1,
  /zh/portfolio, /zh/market-overview, /zh/settings, /zh/settings/system,
  /zh/admin/logs, /zh/admin/notifications, /zh/chat, /zh/__preview/report
- Use live auth/data where available; otherwise use contract-faithful mocks.
- Query rendered DOM for:
  document.querySelectorAll(".<candidate>")
  document.querySelectorAll("[class*='<candidate-prefix>']")
  shell route classes on ancestors and scroll containers
- Measure horizontal overflow:
  document.documentElement.scrollWidth - document.documentElement.clientWidth
  and visible container overflow for primary shell/content frames.
- Check native controls and fallback visuals:
  selects/buttons/inputs have project styling, no visible solid gray/native fallback,
  no default scrollbars are exposed.
- Check developer details:
  collapsed by default; expand only relevant CSS-specific details if safe.
- Check small touch targets:
  collect visible actionable controls below 32 px height or width and compare
  against the baseline. Do not make them worse.
- Capture screenshots/traces/video only as local evidence. Do not commit them.
```

The verification output should include:

- route and viewport;
- mode: live, mock, auth-gated, populated, empty, loading, or fallback;
- DOM hit count for the candidate selector family;
- overflow measurement;
- visual PASS/FAIL for material/card hierarchy/scrollbars/native controls;
- evidence location;
- whether screenshots/videos/traces were generated and removed or left untracked outside the commit.

## 6. Future CSS Deletion Task Template

Future deletion prompts must include:

- Candidate selector or selector family.
- Source search evidence from `rg`, including production source, tests, and `apps/dsa-web/src/index.css`.
- Rendered DOM evidence proving the selector is absent or proving the owner migration replacement is present.
- Route coverage list and state coverage list.
- Tests/checks to run:
  - `cd apps/dsa-web && npm run check:design`
  - `cd apps/dsa-web && npm run lint`
  - `cd apps/dsa-web && npm run build`
  - route-specific Playwright desktop/mobile verification
  - `git diff --check`
  - relevant page/component tests for touched surfaces
  - optional `./scripts/ci_gate.sh` when product CSS actually changes or the deletion affects shared behavior beyond frontend styling
- Rollback plan: exact selector family to restore and route/state that must be rechecked.
- Git staging restrictions:
  - stage only the CSS and directly related docs/tests approved for that deletion task;
  - do not use `git add .`;
  - do not stage screenshots, videos, traces, build output, logs, coverage, sourcemaps, DuckDB files, temp files, package files, config, backend/API files, or unrelated dirty files.

Minimum deletion prompt skeleton:

```text
Candidate selector family:
- <selector>

Non-goals:
- no feature work
- no route redesign
- no backend/API/package/config changes
- no unrelated CSS formatting

Evidence required before edit:
- source search summary
- rendered DOM summary by route and viewport
- route visual checklist results

Allowed files:
- apps/dsa-web/src/index.css
- optional focused docs/check update
- optional focused tests only if explicitly approved

Verification:
- npm run check:design
- npm run lint
- npm run build
- relevant page tests
- Playwright route verification at 1440x1000 and 390x844/390x900
- git diff --check

Commit:
- stage explicit paths only
- no generated artifacts
```

## 7. Parallelization Rules

- Read-only DOM verification can run in parallel with other same-repo tasks when it does not start, stop, kill, or restart shared servers without coordination.
- Actual CSS deletion must be serialized because `apps/dsa-web/src/index.css` is a shared cascade file and order is part of behavior.
- Do not combine selector deletion with feature work.
- Do not combine preview shell redesign with global CSS deletion.
- Do not combine shared primitive migration with CSS deletion.
- Do not combine Scanner shell work with Backtest, Portfolio, or preview report CSS cleanup.
- If another session has dirty changes in `apps/dsa-web/src/index.css` or the route files needed for proof, stop and report the conflict before editing.
- Generated screenshots, videos, traces, Playwright reports, build output, logs, sourcemaps, coverage, DuckDB files, and temp files must remain uncommitted.

## 8. Required Commands For Future CSS Deletion PRs

Run from `/Users/yehengli/daily_stock_analysis/apps/dsa-web` unless noted:

```bash
npm run check:design
npm run lint
npm run build
```

Run from `/Users/yehengli/daily_stock_analysis`:

```bash
git diff --check
```

Also run:

- route-specific Playwright desktop/mobile verification using the route matrix in this checklist;
- relevant page/component tests for any route or primitive touched by the deletion;
- `./scripts/ci_gate.sh` only when product CSS actually changes enough to affect shared behavior or when the task owner explicitly requires full CI.

Before committing:

- confirm no generated screenshots/videos/traces are staged;
- confirm no build output, logs, coverage, sourcemaps, DuckDB files, temp files, package files, config, backend/API files, or unrelated dirty files are staged;
- confirm `docs/CHANGELOG.md` is updated only if the deletion task has user-visible behavior or documentation requirements that explicitly require it.

## 9. Non-Goals

- No CSS changed by this checklist.
- No product code changed by this checklist.
- No tests changed by this checklist.
- No selector deletion performed by this checklist.
- No backend/API code changed by this checklist.
- No package files, config files, scripts, runtime files, or `docs/CHANGELOG.md` changed by this checklist.
- No generated screenshots, videos, traces, build output, logs, coverage, sourcemaps, DuckDB files, or temp files should be committed as part of this checklist or a future deletion PR.

## 10. Source Documents Inspected

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/audits/wolfystock-css-ownership-inventory.md`
- `docs/audits/wolfystock-css-selector-usage-verification.md`
- `docs/audits/wolfystock-frontend-design-conformance-audit.md`
- `docs/qa/wolfystock-workflow-qa-pass.md`
- `docs/checks/design-guard.md`
- `docs/operations/parallel-codex-playbook.md`
