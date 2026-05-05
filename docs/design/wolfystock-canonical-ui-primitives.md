# WolfyStock Canonical UI Primitive Specification

Date: 2026-05-05 Asia/Shanghai  
Repository: `/Users/yehengli/daily_stock_analysis`  
Branch: `main`  
Mode: docs-only design governance; no product code, tests, CSS, backend/API, package, config, runtime, generated artifact, or changelog changes

## 1. Executive Summary

`npm run check:design` at 0 warnings is necessary, but it is not enough. The design guard blocks repeatable source anti-patterns such as solid gray backgrounds, visible raw/debug copy, localized-copy fallback risks, and native-control risks. It does not prove route composition, card hierarchy, mobile touch target comfort, preview-shell alignment, or primitive ownership.

The completed frontend design conformance audit found that WolfyStock is visually aligned with the deep-space quant-terminal constitution, but still has high design debt in route-local cards, command bars, status chips, icon buttons, dense tabs, chart toggles, and developer-detail disclosures. Future work must stop adding new local variants before migration starts.

This document defines canonical primitive categories, first-source owners, domain adapter rules, and migration sequencing. It is a practical governance spec, not a new design system. The first migration path should be one low-blast-radius surface, preferably **Admin Notifications** or **Watchlist**, using current common primitives and route tests before extracting broader shared helpers.

Future Codex tasks must search existing helpers/components before adding new ones, reuse established Button/Input/Select/status/developer-detail patterns, avoid route-local duplicate status/chip/button/card patterns, justify any new helper/component in final reports, and preserve `CODEX_FRONTEND_DESIGN_CONSTITUTION.md` plus `docs/checks/design-guard.md`.

## 2. Source Evidence

Audit documents used:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/audits/wolfystock-frontend-design-conformance-audit.md`
- `docs/qa/wolfystock-workflow-qa-pass.md`
- `docs/qa/wolfystock-portfolio-populated-holdings-qa.md`
- `docs/checks/design-guard.md`
- `docs/audits/wolfystock-css-ownership-inventory.md`
- `docs/audits/wolfystock-css-selector-usage-verification.md`
- `docs/audits/wolfystock-global-codebase-audit.md`
- `docs/audits/wolfystock-phase0-bundle-design-inventory.md`
- `docs/operations/parallel-codex-playbook.md`

Existing components and patterns inspected:

- Common primitives: `apps/dsa-web/src/components/common/Button.tsx`, `GlassCard.tsx`, `SectionShell.tsx`, `Input.tsx`, `Select.tsx`, `Checkbox.tsx`, `Disclosure.tsx`, `MetricCard.tsx`, `PillBadge.tsx`, `ScrollArea.tsx`, `SegmentedControl.tsx`, `WorkspacePageHeader.tsx`
- Status helpers: `apps/dsa-web/src/components/ui/StatusBadge.tsx`, `apps/dsa-web/src/utils/displayStatus.ts`
- Shell owners: `apps/dsa-web/src/components/layout/Shell.tsx`, `PreviewShell.tsx`, `SidebarNav.tsx`
- Market adapters: `apps/dsa-web/src/components/market-overview/marketOverviewPrimitives.tsx`, `MarketOverviewCard.tsx`, `marketOverviewLabels.ts`
- Report/backtest adapters: `apps/dsa-web/src/components/report/*`, `apps/dsa-web/src/components/backtest/*`
- Route-local current usage: `AdminNotificationsPage.tsx`, `AdminLogsPage.tsx`, `WatchlistPage.tsx`, `PortfolioPage.tsx`, `UserScannerPage.tsx`, `BacktestPage.tsx`, `DeterministicBacktestResultPage.tsx`, `PreviewReportPage.tsx`, `ChatPage.tsx`, `HomeBentoDashboardPage.tsx`

Limitations:

- This is a governance document based on source inspection and existing audit reports.
- No rendered DOM, Safari, Playwright, or browser verification was run because no UI changed.
- No migration is approved by this document alone. Each migration still needs targeted tests and visual checks.
- CSS deletion or splitting is explicitly out of scope until visual-regression and DOM-verification checklists exist.

## 3. Primitive Taxonomy

| Primitive | Purpose | Existing owner/pattern | First migration target | Risk | Parallelization note |
| --- | --- | --- | --- | --- | --- |
| PageShell / route shell | Own route frame, width, scroll, masthead, rail, and route modifiers. | `components/layout/Shell.tsx`, `PreviewShell.tsx`, shell route classes such as `theme-shell--scanner`, `shell-content-frame--*`, `workspace-page--*`. | Document Preview Report shell alignment before changing code. | High | Serialize shell changes; audit-only docs can run in parallel. |
| SurfaceCard | Primary ghost-glass route card. | `GlassCard`, `SectionShell`, constitution ghost surface classes. | Admin Notifications rule/list cards or Watchlist command/result cards. | Medium | One route at a time if shared card files change. |
| NestedCard | Quiet inner block inside a surface. | `MetricCard`, `theme-panel-subtle`, `bg-black/20`, `bg-white/[0.025]`. | Portfolio risk/exposure nested blocks after tests. | Medium | Parallel by route only if no shared primitive edit. |
| CommandBar | Dense action/filter strip for route-level commands. | Watchlist command area, Scanner action strip, Backtest tabs, Market refresh rail. | Watchlist command bar. | Medium | Shared extraction serialized; route-local audits parallel-safe. |
| Button | Text action with loading/disabled behavior. | `components/common/Button.tsx`. | Preview chart toggles or Backtest segmented actions after tests. | Medium | Shared Button edits must be serialized. |
| IconButton | Icon-only action with label/title and fixed target. | Current route-local icon buttons plus Button sizing rules. | Market refresh icons or Settings password visibility after target audit. | Medium | Needs shared owner before broad adoption. |
| Input | Text/number/date/password entry. | `components/common/Input.tsx`, `StockAutocomplete` input surface. | Portfolio form label/localization pass after tests. | Medium | Shared Input edits serialized. |
| Select | Native select with ghost overlay and custom arrow. | `components/common/Select.tsx`. | Portfolio and Backtest selects that already use common Select. | Medium | Shared Select edits serialized. |
| Checkbox / row selection | Boolean and row-selection control with large touch wrapper. | `components/common/Checkbox.tsx`, row-local selection controls. | Admin Notifications checkbox, then Watchlist row selection. | Medium | Route-local wrappers parallel-safe; shared Checkbox edit serialized. |
| StatusChip | Generic display status chip, not domain ontology. | `components/ui/StatusBadge.tsx`, `utils/displayStatus.ts`. | Admin Logs generic levels/statuses. | Medium | Status utility changes serialized. |
| FreshnessBadge / provider state badge | Provider freshness, fallback, cache, stale state. | Market-owned `marketOverviewPrimitives.tsx` and freshness labels. | Market Overview documentation first; no generic replacement first. | Medium | Keep market-owned adapter changes serialized with market QA. |
| DeveloperDetails / raw diagnostics disclosure | Collapsed raw/debug/diagnostic area. | `components/common/Disclosure.tsx`, System Control Plane disclosures, report details. | Admin Notifications or System Settings diagnostics. | Medium | Shared Disclosure changes serialized. |
| EmptyState | Quiet no-data, loading, failure-safe content. | Route-local empty cards; common card primitives. | Watchlist empty/filter states or Portfolio empty accounts. | Low/Medium | Parallel by route if no shared component edit. |
| MetricCard | Compact label/value/detail tile. | `components/common/MetricCard.tsx`, Portfolio/Backtest/Market route tiles. | Backtest result metric tiles or Admin Notifications summary tiles. | Medium | Shared extraction serialized. |
| Mobile action rail / touch-target pattern | Mobile-safe dense actions with stable min target. | Recent Button size rules, route-local compact tabs/chips. | Mobile Touch Target Phase 2. | Medium | Parallel by route; shared sizing serialized. |
| Dense tabs / segmented controls | Mode switching without page reflow. | `components/common/SegmentedControl.tsx`, route-local tabs. | Backtest tabs, Portfolio tabs, Admin Logs categories. | Medium | Shared SegmentedControl edits serialized. |
| Chart toggle controls | Chart mode/series/timeframe toggles. | Preview report chart toggles, report/backtest chart toolbar classes. | Preview Report chart toggles. | Medium | Serialize with report/preview shell work. |
| Data table / row action controls | Dense row actions, status, selection, and inline commands. | Watchlist rows, Admin Logs rows, Portfolio holdings/trades. | Watchlist row selection/action controls. | Medium | Parallel by domain only if no shared row primitive edit. |

## 4. Primitive Specifications

### 4.1 PageShell / Route Shell

Usage: own the top-level route frame, route width, shell rail, scroll ownership, and route modifiers. Use `Shell.tsx` route classes and `PreviewShell.tsx` only when the route is truly preview/report-specific.

Visual rules: preserve deep-space background, wide operational workspace, `min-w-0`, `min-h-0`, hidden scrollbars, and route-specific shell modifiers already tested in `Shell.test.tsx`.

Behavior/accessibility rules: route shells must not hide focus rings, trap scroll unexpectedly, or rely on viewport-lock hacks for ordinary pages.

Mobile/touch target rules: shell header controls may be compact on desktop, but mobile route controls must remain reachable without horizontal overflow.

Copy/localization rules: shell chrome is Chinese-first on Chinese routes except accepted terms such as `EN`, tickers, providers, metrics, and currencies.

Do: reuse `Shell.tsx` route modifiers and add route tests when shell classes change. Do not create route-local full-page wrappers that narrow the workspace or bypass shell scroll ownership.

Recommended checks: `Shell.test.tsx`, affected route tests, `npm run check:design`, lint/build, desktop and 390px visual verification for code changes.

First safe migration target: Preview Report shell alignment documentation and checklist before code.

Migration risk: high, because shell changes affect all protected routes.

### 4.2 SurfaceCard

Usage: primary route sections such as summary panels, forms, rule lists, and operational modules.

Visual rules: use ghost-glass material from `GlassCard` or `SectionShell`: transparent white/black surfaces, thin white borders, restrained blur, no solid gray backgrounds, no loud saturated panels.

Behavior/accessibility rules: cards are structural regions only when they contain a section heading or meaningful group. Do not make every small datum a card.

Mobile/touch target rules: card padding may compress on mobile, but controls inside still need comfortable targets.

Copy/localization rules: headings and action copy should be Chinese-first on Chinese routes.

Do: use `GlassCard` for simple surfaces and `SectionShell` when a title/description/actions header is needed. Do not add route-local `rounded/border/bg-white` combinations unless the final report explains why no current primitive fits.

Recommended checks: route tests, `check:design`, desktop/mobile visual pass for visible changes.

First safe migration target: Admin Notifications rule/list cards or Watchlist cards.

Migration risk: medium; card hierarchy can easily over-fragment pages.

### 4.3 NestedCard

Usage: subordinate blocks inside a SurfaceCard, such as diagnostics groups, metric details, exposure buckets, or risk drilldowns.

Visual rules: nested cards must be quieter than parent cards: lower contrast, less blur, smaller radius, less padding. Prefer `MetricCard`, `theme-panel-subtle`, `bg-black/20`, or existing nested route pattern.

Behavior/accessibility rules: nested blocks should not become independent landmarks unless they are independently navigable.

Mobile/touch target rules: avoid dense nested grids that create one-card-per-line vertical noise.

Copy/localization rules: labels should stay compact; use Chinese labels except domain terms.

Do: keep nested diagnostics visually secondary. Do not stack card-inside-card-inside-card without a data hierarchy reason.

Recommended checks: affected route tests and 390px visual review.

First safe migration target: Portfolio risk/exposure blocks after Portfolio populated route coverage.

Migration risk: medium.

### 4.4 CommandBar

Usage: route-level actions, filters, refresh, batch operations, and mode switches.

Visual rules: one command bar per major workflow zone. It should be dense, aligned, and scan-friendly, not a pile of chips.

Behavior/accessibility rules: commands need explicit disabled/loading states, labels for icon-only actions, and no duplicate-click paths for batch work.

Mobile/touch target rules: wrap to rows with stable heights; avoid 22-29 px chip controls on narrow screens.

Copy/localization rules: action copy must be operator-grade Chinese on Chinese routes.

Do: consolidate Watchlist/Scanner/Backtest command strips around shared Button/SegmentedControl primitives. Do not create route-local button chips with unrelated heights, borders, and tones.

Recommended checks: route page tests, batch-action tests where applicable, `check:design`, desktop/mobile visual pass.

First safe migration target: Watchlist command bar.

Migration risk: medium.

### 4.5 Button

Usage: text actions, primary CTAs, secondary actions, destructive actions, and loading buttons.

Visual rules: `components/common/Button.tsx` is the first source. Use existing variants and sizes before adding a class-only local button. Desktop dense controls may use `sm`, but mobile should not go below the project touch target policy.

Behavior/accessibility rules: preserve native button semantics, `type`, disabled state, loading `aria-busy`, keyboard activation, and visible focus.

Mobile/touch target rules: mobile action buttons should prefer at least the common `sm` min height and may need larger wrappers in dense rails.

Copy/localization rules: Chinese route labels should be Chinese; English may remain for compact domain abbreviations.

Do: use `Button` and override only spacing when needed. Do not add local `button` class bundles that reimplement loading, disabled, or focus.

Recommended checks: `Button.test.tsx`, affected route tests, design guard.

First safe migration target: Preview chart toggles or Backtest tab-like buttons after route tests.

Migration risk: medium because Button is shared.

### 4.6 IconButton

Usage: refresh, close, copy, expand, password visibility, chart mode, and row quick actions where text would be too noisy.

Visual rules: icon buttons should use the Button sizing model or a future shared IconButton owner. They need fixed square dimensions, no text overflow, and restrained ghost material.

Behavior/accessibility rules: every icon-only button needs an `aria-label` and preferably `title`. Icons should be decorative if the label carries meaning.

Mobile/touch target rules: actual clickable area should not collapse to 18-25 px. Use padding or wrapper target size.

Copy/localization rules: aria labels and titles should localize.

Do: use lucide icons already in the app where possible. Do not manually create unlabeled icon spans or 20 px click targets.

Recommended checks: route tests that query labels, 390px visual/touch scan.

First safe migration target: Market refresh icons or Settings password visibility buttons.

Migration risk: medium.

### 4.7 Input

Usage: text, password, date, numeric, and token fields.

Visual rules: `components/common/Input.tsx` is canonical. Preserve ghost input surface, focus glow, label, hint, error, leading icon, trailing action, and password toggle behavior.

Behavior/accessibility rules: every input needs label association or accessible name, error text with `role="alert"` when appropriate, and correct `aria-invalid`.

Mobile/touch target rules: use the common `h-10` base or larger; avoid route-local dense inputs.

Copy/localization rules: labels on Chinese routes should be Chinese unless the term is a ticker, currency, provider, field code, or accepted market abbreviation. Portfolio labels such as `TRADE DATE`, `QUANTITY`, `PRICE`, `FEE`, and `NOTE` should be reviewed in a future copy pass.

Do: use common `Input`. Do not style raw `<input>` directly unless the final report explains why the common component cannot support the case.

Recommended checks: `Input.test.tsx`, route form tests, design guard.

First safe migration target: Portfolio form label/localization review after tests.

Migration risk: medium.

### 4.8 Select

Usage: market/profile/account/provider/mode selection where native select semantics are acceptable.

Visual rules: `components/common/Select.tsx` is canonical. It uses a native select for semantics plus a ghost overlay for visual consistency.

Behavior/accessibility rules: keep label association, keyboard support, disabled state, selected value truncation, and custom arrow pointer behavior.

Mobile/touch target rules: preserve `h-10` overlay and avoid clipped values.

Copy/localization rules: option labels should localize unless they are provider names, market codes, tickers, currencies, or domain terms.

Do: use common `Select`. Do not create a local invisible select plus overlay variant.

Recommended checks: `Select.test.tsx`, route tests for selected labels, design guard.

First safe migration target: Portfolio and Backtest selects already near the common pattern.

Migration risk: medium.

### 4.9 Checkbox / Row Selection

Usage: boolean settings, notification channel toggles, row selection, and batch selection.

Visual rules: `components/common/Checkbox.tsx` is the starting owner, but row selection may need a domain wrapper around it. The visual checkbox can remain compact if the label/wrapper provides a larger target.

Behavior/accessibility rules: preserve input semantics, label association, keyboard operation, indeterminate handling if added later, and clear selected state.

Mobile/touch target rules: raw `14x14` or `16x16` checkbox-only targets are not enough for mobile rows. Wrap row selection in a larger hit area.

Copy/localization rules: labels should localize.

Do: use common Checkbox or a row-selection adapter. Do not leave isolated native checkboxes as the only target.

Recommended checks: route selection tests and 390px touch-target scan.

First safe migration target: Admin Notifications checkbox, then Watchlist row selection.

Migration risk: medium.

### 4.10 StatusChip

Usage: generic display status such as success, failed, running, pending, warning, disabled, info, and unknown.

Visual rules: `StatusBadge.tsx` and `displayStatus.ts` are current first sources. Use thin borders, subtle backgrounds, and compact text; do not use large saturated backgrounds.

Behavior/accessibility rules: status text must be visible text, not color-only. Use `data-status`/tone only as supplemental metadata.

Mobile/touch target rules: status chips are not normally interactive; if interactive, they must follow Button/IconButton target rules.

Copy/localization rules: default labels should be Chinese on Chinese routes. English labels may appear on English routes only.

Developer/raw diagnostics rule: raw provider/internal status strings belong in DeveloperDetails, not primary chips, unless converted through a domain adapter.

Do: adapt domain statuses into a shared display primitive. Do not treat `displayStatus` as a universal domain ontology.

Recommended checks: `StatusBadge.test.tsx`, `displayStatus.test.ts`, route status tests.

First safe migration target: Admin Logs generic level/status chips.

Migration risk: medium.

### 4.11 FreshnessBadge / Provider State Badge

Usage: provider freshness, fallback-only, cache hit, stale data, provider down, and partial availability states.

Visual rules: keep Market Overview freshness/provider adapters as the first source. These states carry market-data meaning and should not be flattened into generic success/failure only.

Behavior/accessibility rules: distinguish freshness, runtime health, config validation, and external connectivity. Do not collapse them into one label.

Mobile/touch target rules: noninteractive badges may be compact; refresh or retry controls beside them must meet action target rules.

Copy/localization rules: use honest Chinese labels for stale/fallback/partial states; provider names may stay English.

Developer/raw diagnostics rule: provider raw codes such as `provider_down` or `provider_error` should be adapted for primary UI and kept raw only inside collapsed details.

Do: keep Market-owned adapters around shared chip styling. Do not replace provider freshness with a generic enum.

Recommended checks: Market Overview freshness tests and browser review for market route changes.

First safe migration target: documentation and adapter contract only.

Migration risk: medium.

### 4.12 DeveloperDetails / Raw Diagnostics Disclosure

Usage: raw metadata, request/response snippets, execution assumptions, data quality, provider internals, and debug-only diagnostics.

Visual rules: `Disclosure.tsx` is the common starting point. Developer details must be visually secondary and collapsed by default unless a task explicitly asks otherwise.

Behavior/accessibility rules: summary must be keyboard accessible, descriptive, and stable. Raw content must not expose secrets.

Mobile/touch target rules: summary row must not be an 18 px click target on mobile.

Copy/localization rules: Chinese labels should use terms such as `开发者细节`, `原始诊断`, `数据质量`, or `执行假设`.

Developer/raw diagnostics rule: never expose raw API keys, tokens, webhook URLs, schema internals, system prompts, or provider raw errors in primary UI.

Do: convert route-local `<details>` into a common DeveloperDetails wrapper after one route proves the pattern. Do not dump JSON in visible primary cards.

Recommended checks: route leakage tests, design guard, browser text scan for raw/debug terms.

First safe migration target: Admin Notifications or System Settings.

Migration risk: medium.

### 4.13 EmptyState

Usage: no data, no selected item, filtered-empty, unavailable provider, and safe failure states.

Visual rules: quiet, useful, and proportional. EmptyState should use SurfaceCard or NestedCard material depending on context.

Behavior/accessibility rules: do not fake successful data. If an action is available, use Button and explain the next step.

Mobile/touch target rules: empty-state actions follow Button rules and should not overflow.

Copy/localization rules: Chinese-first and domain-specific. Avoid generic SaaS copy.

Developer/raw diagnostics rule: primary empty states should explain user-facing cause; raw cause belongs in DeveloperDetails.

Do: reuse empty-state structure by route family. Do not create new decorative empty cards for every page.

Recommended checks: route tests for empty/error states and design guard.

First safe migration target: Watchlist or Portfolio empty states.

Migration risk: low/medium.

### 4.14 MetricCard

Usage: KPI tiles, exposure buckets, risk stats, backtest metrics, market temperature, and admin summary counts.

Visual rules: `MetricCard.tsx` is the first source for simple label/value/detail. Domain metric adapters may wrap it for formatting and tone.

Behavior/accessibility rules: do not encode meaning with color alone. Include label, value, unit/context, and unavailable state.

Mobile/touch target rules: metrics are usually static; if clickable, use a Button-like action area.

Copy/localization rules: labels should localize except finance-standard abbreviations such as P/E, EPS, ROE, RSI, MACD.

Do: use MetricCard for simple repeated metric tiles. Do not force complex domain panels into a generic metric component if they need formulas or drilldowns.

Recommended checks: route snapshot/assertion tests and visual review.

First safe migration target: Backtest result metric tiles or Admin Notifications summary tiles.

Migration risk: medium.

### 4.15 Mobile Action Rail / Touch-Target Pattern

Usage: compact mobile rows of actions, tabs, toggles, refresh controls, and row operations.

Visual rules: use consistent heights, gaps, wrapping, and icon/text alignment. Avoid controls below 32 px high unless they are noninteractive badges.

Behavior/accessibility rules: disabled/loading states must remain clear; duplicate-click blocking remains domain-owned for batch workflows.

Mobile/touch target rules: mobile target size is the primary reason this primitive exists. Prefer larger wrappers over tiny visual boxes when density matters.

Copy/localization rules: keep action labels short and Chinese-first.

Do: create a shared pattern only after one route proves it. Do not patch every route with unrelated height tweaks.

Recommended checks: 390px visual/touch scan, route tests, design guard.

First safe migration target: Mobile Touch Target Phase 2.

Migration risk: medium.

### 4.16 Dense Tabs / Segmented Controls

Usage: workflow mode, category, timeframe, and route section switching.

Visual rules: `SegmentedControl.tsx` is the first common owner. Tabs should feel like part of the command surface, not a second navigation system.

Behavior/accessibility rules: use button or tab semantics consistently, preserve focus, selected state, and keyboard operation.

Mobile/touch target rules: avoid sub-32 px tab heights on narrow screens; wrap or scroll quietly when needed.

Copy/localization rules: labels should localize and remain short.

Do: use common SegmentedControl or a domain adapter. Do not add route-local pill strips with unique dimensions and tones.

Recommended checks: component tests, affected route tests, mobile scan.

First safe migration target: Backtest tabs, Portfolio tabs, or Admin Logs categories.

Migration risk: medium.

### 4.17 Chart Toggle Controls

Usage: chart series, timeframe, mode, chart/table, and report/backtest visualization toggles.

Visual rules: chart toggles should reuse Button/SegmentedControl sizing and chart toolbar material. Preview report toggles are a known weak point.

Behavior/accessibility rules: selected state must be clear to screen readers and visible users. Toggles should not resize chart containers.

Mobile/touch target rules: avoid 22-27 px chart toggles; wrap or use a horizontal rail with quiet scroll.

Copy/localization rules: chart UI chrome should be Chinese on Chinese routes except domain terms such as TTM, FY, EPS, RSI, MACD.

Do: align Preview Report and Backtest chart toggles to the same primitive. Do not add chart-specific tiny chips.

Recommended checks: Preview report tests, chart route tests, desktop/mobile visual review.

First safe migration target: Preview Report chart toggles.

Migration risk: medium.

### 4.18 Data Table / Row Action Controls

Usage: tables/lists for watchlist symbols, admin logs, portfolio holdings/trades, notification events, scanner candidates, and backtest rows.

Visual rules: row actions should be compact but stable. Use shared Button/IconButton/StatusChip/Checkbox wrappers, not local mini controls.

Behavior/accessibility rules: rows need visible selected state, keyboard-compatible actions, clear disabled state, and no color-only status meaning.

Mobile/touch target rules: row controls should wrap into action rails or expose one clear primary action plus disclosure/details.

Copy/localization rules: row action labels should localize; symbol/provider/domain fields may remain English.

Developer/raw diagnostics rule: raw row metadata belongs in collapsed DeveloperDetails or row details, not default table cells.

Do: migrate one table/list surface first. Do not invent separate table action controls in every route.

Recommended checks: route table tests, row action tests, mobile scan.

First safe migration target: Watchlist row selection/action controls.

Migration risk: medium.

## 5. Domain Adapter Rules

`displayStatus`: treat `utils/displayStatus.ts` as a display-label utility. It can normalize common display states and localize labels, but it is not a universal domain ontology. Do not add every backend enum, provider code, scanner state, portfolio accounting state, or backtest verdict directly into one giant shared enum.

Admin Logs/Notifications: use `describeAdminLogLevel`, `describeAdminNotificationStatus`, `StatusBadge`, and shared chip styling for generic display. Keep raw metadata collapsed under developer details.

Market freshness/provider: keep market-owned adapters in `marketOverviewPrimitives.tsx` and related market overview files. Freshness, fallback, cache, provider health, and stale data are domain semantics, not generic success/failure.

Scanner statuses: scanner scoring, run state, candidate evaluation, AI additive interpretation, and provider fallback should use scanner adapters around shared display primitives. Scanner AI remains a second-pass interpretation layer, not primary selection.

Watchlist intelligence statuses: keep watchlist-owned semantics for saved scanner intelligence, selected rows, and batch action state, while reusing shared Button, Checkbox, StatusChip, and CommandBar surfaces.

Backtest verdicts: backtest verdicts, execution assumptions, data quality, and deterministic result density should use backtest adapters around shared display primitives. Do not collapse backtest verdicts into admin notification status labels.

Portfolio risk statuses: risk, accounting, FX transparency, broker connection, cash ledger, and valuation states must remain portfolio-owned adapters. Preserve accounting formulas and portfolio semantics.

Why not one giant enum: these domains answer different questions. Provider freshness is about data recency and fallback. Admin logs are about operational severity. Scanner statuses describe candidate evaluation and run lifecycle. Backtest verdicts describe simulation outcome and data assumptions. Portfolio statuses describe accounting, exposure, and broker/FX state. A single enum would erase meaning, grow without ownership, and make future migrations riskier.

## 6. Migration Strategy

Stage 0: docs/checklists only.

- Keep this spec and the audit documents as the source of primitive governance.
- Add CSS visual-regression and DOM-verification checklists before CSS deletion.
- Do not change product code, CSS, tests, backend, package files, or config in Stage 0 docs tasks.

Stage 1: one-surface migration.

- Pick Admin Notifications or Watchlist.
- Reuse current `Button`, `Input`, `Select`, `Checkbox`, `GlassCard`, `SectionShell`, `Disclosure`, `StatusBadge`, and `displayStatus` patterns.
- Add or update route tests first.
- Verify `check:design`, lint, build, and desktop/mobile browser for visible UI changes.

Stage 2: shared primitive extraction only after proven route.

- Extract a shared primitive only when one route proves the desired behavior and another route has the same real need.
- Keep adapter boundaries domain-owned.
- Avoid broad all-route rewrites.

Stage 3: route-by-route adoption.

- Migrate one route or one component family at a time.
- Use the route's existing tests and visual contract.
- Preserve route DOM skeletons unless the task explicitly targets shell/layout.

Stage 4: CSS cleanup only after DOM/visual verification.

- CSS deletion/splitting must wait for a visual regression checklist and rendered DOM verification.
- Source `rg` evidence alone is not enough for deletion because route classes can be dynamically composed.
- Do not delete shell route modifiers or active product/report/backtest selectors without route proof.

## 7. First Recommended Implementation Tasks

| Title | Scope | Likely files | Expected benefit | Risk | Tests/checks | Parallel-safe? |
| --- | --- | --- | --- | --- | --- | --- |
| One-surface primitive migration: Admin Notifications | Convert rule/list cards, status chips, checkbox/touch wrappers, and developer details to current canonical primitives. | `apps/dsa-web/src/pages/AdminNotificationsPage.tsx`, maybe `components/common/*`, `utils/displayStatus.ts` only if tests justify. | Proves primitive reuse on a small admin surface. | Medium | Admin Notifications tests, `displayStatus.test.ts` if touched, `check:design`, lint, build, desktop/mobile browser. | No if shared files change; yes as isolated route work after ownership lock. |
| One-surface primitive migration: Watchlist | Align command bar, row selection, row actions, and status chips. | `WatchlistPage.tsx`, common Button/Checkbox/Status primitives if needed. | Proves dense workflow surface without touching scanner/backtest contracts. | Medium | Watchlist tests, mobile 390px visual scan, `check:design`, lint, build. | No if shared primitives change. |
| Mobile Touch Target Phase 2 | Fix repeat sub-32 px controls route-by-route. | Home, Scanner, Watchlist, Backtest, Portfolio, Settings, Admin Logs, Chat, Preview route files; common Button/IconButton/Checkbox only after plan. | Resolves most visible post-guard conformance gap. | Medium | Route tests, 390px browser scan, `check:design`, lint, build. | Parallel by route; shared sizing serialized. |
| Status Utility Phase 3 | Expand adapter discipline around shared display primitives without creating a giant enum. | `utils/displayStatus.ts`, `components/ui/StatusBadge.tsx`, Admin Logs/Notifications adapters, domain route adapters. | Reduces route-local chip/tone duplication. | Medium | StatusBadge and displayStatus tests, affected route tests. | Shared utility work serialized. |
| Preview Report Shell Alignment | Bring preview report shell/card/toggle behavior closer to main shell while preserving report semantics. | `PreviewReportPage.tsx`, `PreviewShell.tsx`, report components, route tests. | Reduces preview/main shell drift. | Medium | Preview route tests, desktop/mobile visual checks, `check:design`, lint, build. | Not parallel with report CSS cleanup. |
| CSS Visual Regression Checklist | Define routes, viewports, states, and screenshot/DOM expectations before CSS cleanup. | New docs/checklist under `docs/checks` or `docs/design`. | Makes future CSS deletion safer. | Low | Markdown inspection, `git diff --check`. | Yes as docs-only. |
| CSS DOM Verification before deletion | Render/DOM-check dead-selector candidates before any CSS removal. | New audit doc first; later `apps/dsa-web/src/index.css` only after approval. | Prevents deleting dynamically used selectors. | Low as audit, high if deletion follows. | `rg`, rendered DOM checks, build/design guard if code later changes. | Yes as read-only audit; deletion serialized. |
| Data table row action primitive trial | Align row action buttons, status chips, and selection wrappers on one list/table route. | Watchlist or Admin Logs page first. | Establishes reusable row-control shape. | Medium | Route table tests, mobile scan, design guard. | No if shared row primitive is extracted. |

## 8. Prompt Insertion Snippet

Before editing WolfyStock frontend UI, read `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`, `docs/checks/design-guard.md`, and `docs/design/wolfystock-canonical-ui-primitives.md`. Search existing components and helpers before adding new UI primitives. Reuse the established `Button`, `Input`, `Select`, `Checkbox`, `GlassCard`, `SectionShell`, `Disclosure`, `StatusBadge`, `displayStatus`, shell route, developer-detail, and domain adapter patterns wherever possible. Do not add route-local duplicate card/button/chip/input/status/developer-detail variants unless the final report explicitly justifies why no existing primitive fits. Keep domain semantics in adapters, avoid a giant cross-domain enum, preserve Chinese-first UI copy, keep raw diagnostics collapsed, run the design guard for UI code changes, and avoid CSS deletion until DOM and visual verification are complete.

## 9. Non-goals

- No product code changed.
- No CSS changed.
- No tests changed.
- No backend/API code changed.
- No package files or config changed.
- No `docs/CHANGELOG.md` changed.
- No generated artifacts committed.
- No dev servers started, killed, or restarted.
- No issues fixed in this task.
