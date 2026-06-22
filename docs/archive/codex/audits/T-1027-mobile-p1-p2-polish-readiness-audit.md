# T-1027 Mobile P1/P2 Polish Readiness Audit

Task ID: `T-1027-AUDIT`
Mode: `READ-ONLY-AUDIT` with report artifact only
Viewport focus: `390px` mobile class
Artifact scope: this audit document only

## Decision Summary

- Mobile release readiness: no new P1 blocker found from static inspection and existing 390px smoke coverage.
- Smallest valuable next writes: two page-local P2 touch-target passes, first for Home chart controls and second for Scanner controls/actions.
- Not recommended: a global shared-button/mobile primitive sweep. Current evidence points to uneven page-local density, not a safer shared primitive change.
- Deferred: Portfolio/Watchlist and Settings/Admin until a focused QA reproduction exists; Backtest/Options post-containment residuals are no-op for immediate mobile polish.

## Evidence Base

This audit used static code inspection plus existing smoke coverage. No browser run was performed because this task is docs-only and the prompt only requires diff/secret validation.

Inspected evidence:

- Home chart has a dedicated `390x844` smoke that asserts chart visibility, ECharts rendering, context badges, safe copy, and no horizontal overflow: `apps/dsa-web/e2e/home-chart-browser.smoke.spec.ts:260`.
- Scanner and Watchlist have a `390x844` launch smoke with no page-level horizontal overflow: `apps/dsa-web/e2e/market-overview-scanner.smoke.spec.ts:90`.
- Portfolio launch coverage includes desktop and `390x844`, no horizontal overflow, safe-copy checks, and required ledger labels: `apps/dsa-web/e2e/portfolio-launch-surface.spec.ts:4`.
- Backtest result visual smoke loops desktop and `390x844` and checks chart/report visibility, safe research-only copy, folded evidence, and no horizontal overflow at narrow width: `apps/dsa-web/e2e/backtest-visual-result.smoke.spec.ts:60`.
- Settings and Admin mobile smokes exist for system disclosure and admin ops launch surfaces: `apps/dsa-web/e2e/settings-disclosure.smoke.spec.ts:5`, `apps/dsa-web/e2e/admin-ops-launch-surfaces.spec.ts:9`.
- T-1012 was used as the baseline audit. Current code shows several T-1012 P1 items have already been reduced to containment or P2 density observations.

Subagent: skipped. The remaining classification was small enough to resolve by static inspection.

## Mobile Verdict Matrix

| Surface | Verdict | Current evidence | Decision |
| --- | --- | --- | --- |
| Home / Guest hit areas | P2 | Guest command bar now uses `min-h-12`, and guest submit/history/input shells use `min-h-10`: `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5642`. Remaining small interactive targets are Home chart timeframe and indicator buttons at `px-2.5 py-1 text-[10px]`: `apps/dsa-web/src/components/home-bento/HomeCandlestickChartDisplay.tsx:60`, `apps/dsa-web/src/components/home-bento/HomeCandlestickChartDisplay.tsx:96`. | Recommend one local Home chart touch-target task. Guest main hit areas do not need an immediate write. |
| Scanner controls/actions | P2 | Scanner run/more/theme actions still use compact `h-8` or `h-9` controls: `apps/dsa-web/src/pages/UserScannerPage.tsx:2810`, `apps/dsa-web/src/pages/UserScannerPage.tsx:2910`, `apps/dsa-web/src/pages/UserScannerPage.tsx:3042`, `apps/dsa-web/src/pages/UserScannerPage.tsx:3167`. Candidate mobile actions flow through `ScannerActionButton` with `px-2.5 py-1 text-xs`: `apps/dsa-web/src/components/scanner/ScannerActionButton.tsx:24`. | Recommend one Scanner-local touch-target task. Keep ranking/scoring/action semantics unchanged. |
| Portfolio / Watchlist row/action density | Defer | Portfolio still has local table density and some `size-8`/`size-9` actions: `apps/dsa-web/src/pages/PortfolioPage.tsx:82`, `apps/dsa-web/src/pages/PortfolioPage.tsx:2998`. Watchlist row selection remains `32x32`, and copy/remove buttons are `34px`: `apps/dsa-web/src/pages/WatchlistPage.tsx:101`, `apps/dsa-web/src/pages/WatchlistPage.tsx:1945`. Existing smoke covers mobile launch and no page overflow. | Defer. These surfaces are close to portfolio accounting and saved-list workflows, so write only after a focused QA repro or dedicated row/action task. |
| Backtest / Options post-containment residuals | No-op | Options payoff/IV visuals are now contained with `overflow-x-auto` and `min-w-[20rem]`, not the old wider `28rem` minimum: `apps/dsa-web/src/pages/OptionsLabPage.tsx:970`, `apps/dsa-web/src/pages/OptionsLabPage.tsx:1084`. Chain tables remain internally scrollable dense workbench tables: `apps/dsa-web/src/pages/OptionsLabPage.tsx:1524`. Backtest result page uses `overflow-x-hidden` and mobile containment around the report: `apps/dsa-web/src/pages/DeterministicBacktestResultPage.tsx:1599`, `apps/dsa-web/src/pages/DeterministicBacktestResultPage.tsx:1677`. | No immediate mobile polish write. Do not reopen Options/Backtest unless new QA shows a post-containment failure. |
| Settings / Admin compact controls | Defer | Settings category buttons are compact `px-3 py-2`, and system health cards still use two columns at mobile: `apps/dsa-web/src/components/settings/SettingsCategoryNav.tsx:40`, `apps/dsa-web/src/components/settings/SystemControlPlane.tsx:108`. Admin tabs/disclosures use compact buttons: `apps/dsa-web/src/pages/AdminLogsPage.tsx:1857`, `apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx:109`. | Defer. T-1024 is actively fixing System Settings reset on main, so do not touch System Settings source from this lane. Admin density is operator-facing and not an immediate P1. |

## Recommended Immediate Write Tasks

### 1. Home Chart Mobile Control Hit Areas

Priority: P2
Why now: this is the clearest remaining mobile touch-density issue, and the fix can stay page-local around the chart controls.

Allowed files:

- `apps/dsa-web/src/components/home-bento/HomeCandlestickChartDisplay.tsx`
- `apps/dsa-web/e2e/home-chart-browser.smoke.spec.ts`

Forbidden semantics:

- Do not change chart data, timeframe meanings, indicator availability, provider routes, evidence packet handling, report generation, research/no-advice copy, Home shell routing, shared primitives, or global CSS.
- Do not modify screenshots.

Validation:

- `npm --prefix apps/dsa-web run test:e2e -- e2e/home-chart-browser.smoke.spec.ts --project=chromium`
- `npm --prefix apps/dsa-web run lint`
- `npm --prefix apps/dsa-web run build`
- `git diff --check`
- `./scripts/release_secret_scan.sh`

Conflict risk: low. The task should only alter Home chart control classes and add focused 390px assertions.

### 2. Scanner Mobile Controls and Candidate Action Hit Areas

Priority: P2
Why now: Scanner still has multiple compact interactive controls in high-frequency paths, and existing mobile smoke coverage already gives a focused validation base.

Allowed files:

- `apps/dsa-web/src/pages/UserScannerPage.tsx`
- `apps/dsa-web/src/components/scanner/ScannerActionButton.tsx`
- `apps/dsa-web/src/components/scanner/ScannerCandidatePresenters.tsx`
- `apps/dsa-web/e2e/market-overview-scanner.smoke.spec.ts`
- `apps/dsa-web/e2e/controlled-user-testing.smoke.spec.ts`

Forbidden semantics:

- Do not change scanner scoring, ranking, selection, sorting, thresholds, candidate payloads, evidence frames, provider/cache behavior, watchlist persistence, portfolio mutations, backtest launch payloads, API contracts, shared `TerminalButton`, shared button primitives, or global CSS.
- Do not modify screenshots.

Validation:

- `npm --prefix apps/dsa-web run test:e2e -- e2e/market-overview-scanner.smoke.spec.ts --grep "scanner" --project=chromium`
- `npm --prefix apps/dsa-web run test:e2e -- e2e/controlled-user-testing.smoke.spec.ts --grep "Scanner" --project=chromium`
- `npm --prefix apps/dsa-web run lint`
- `npm --prefix apps/dsa-web run build`
- `git diff --check`
- `./scripts/release_secret_scan.sh`

Conflict risk: medium. Scanner is dense and near protected ranking/action flows, so keep the change local to hit area, wrapping, and smoke assertions.

## Deferrals

- Portfolio / Watchlist: defer until QA identifies an actual mis-tap or unreadable row/action workflow. A future task should be row-local and must not touch accounting, cash, holdings, P&L, FX, cost basis, watchlist persistence, scanner links, or API payload shape.
- Backtest / Options: no-op for immediate mobile polish. Existing containment and 390px smokes cover the prior P1 class; future work should wait for a concrete post-containment reproduction.
- Settings / Admin: defer because T-1024 is active on System Settings reset and this task must not touch System Settings source. Admin compact controls can remain operator-dense unless a targeted mobile QA issue appears.

## Explicit Rejection: Global Primitive Sweep

A global shared-button/mobile primitive sweep is not recommended for this wave.

Reasons:

- The evidence is page-specific: Home chart controls, Scanner command/action controls, Watchlist row buttons, Settings category buttons, and Admin disclosure buttons each live in different workflow contexts.
- A shared primitive sweep would touch `TerminalButton` or design-system primitives and could unintentionally affect scanner ranking actions, portfolio/watchlist workflows, admin disclosures, and settings controls at once.
- Existing 390px smoke coverage already shows no page-level horizontal overflow; the remaining issue is localized touch density, not a global layout failure.

Only reconsider a global primitive task if measurement proves it is safer than page-local patches across all affected routes and includes full route smoke coverage for Home, Scanner, Watchlist, Portfolio, Backtest, Options, Settings, and Admin.

## Boundary Confirmation

- Source changes recommended: future tasks only; none in this audit.
- This audit does not recommend broad redesign, card rewrites, evidence deletion, copy-safety changes, API/schema changes, backend/provider/cache/runtime changes, auth changes, scoring changes, portfolio accounting changes, Options/Backtest semantic changes, or System Settings changes.
- Final intended diff for T-1027-AUDIT: `docs/codex/audits/T-1027-mobile-p1-p2-polish-readiness-audit.md` only.
