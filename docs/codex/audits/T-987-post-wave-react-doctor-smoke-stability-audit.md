# T-987 Post-wave React Doctor and smoke stability audit

Task: T-987 Post-wave React Doctor and smoke stability audit

Mode: SERIAL-MAIN with one explicitly allowed audit artifact.

Allowed artifact: `docs/codex/audits/T-987-post-wave-react-doctor-smoke-stability-audit.md`

Observed HEAD during audit: `9a9a8b4f` (`T-986: refine Scanner workflow hierarchy`)

Scope boundary:

- No product source changes.
- No test changes.
- No backend/frontend runtime or config changes.

## Executive summary

The current frontend wave is smoke-stable but not React-clean. All three
requested Playwright commands passed with no retry and no observed flaky rerun,
so the latest provenance/display/Scanner workflow work is functionally shippable
for continued controlled testing. The next cleanup should target React state and
compiler-compatibility debt on the two wave-heavy routes, not broad visual
redesign.

React Doctor is the stronger signal than the smoke pack:

- Total diagnostics: **722**
- Errors: **130**
- Warnings: **592**
- By category: **Performance 224**, **Bugs 151**, **Maintainability 313**,
  **Accessibility 34**

Current highest-value cleanup area is concentrated in:

- `apps/dsa-web/src/pages/UserScannerPage.tsx`: **119**
- `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`: **95**
- `apps/dsa-web/src/pages/MarketOverviewPage.tsx`: **14**
- `apps/dsa-web/src/components/home-bento/HomeCandlestickChart.tsx`: **11**

The safest next work is a narrow Scanner/Home hardening pass. The largest
remaining risk is Home state orchestration inside a 6206-line page, which should
not be mixed into a small main-branch cleanup.

## Command evidence

### React Doctor

Command:

```bash
npx react-doctor@latest --verbose --yes --no-score
```

Observed result:

- Exit code: non-zero after diagnostics emission.
- Output note: the command still prompted for install confirmation despite
  `--yes`; audit continued manually with `y`.
- Environment note: npm emitted `EBADENGINE` warnings for `ini@7.0.0` under
  Node `v20.20.2`, but React Doctor still ran and produced diagnostics.
- Headline counts from emitted summary:
  - `Bugs`: 19 errors, 132 warnings
  - `Performance`: 111 errors, 113 warnings
  - `Accessibility`: 34 warnings
  - `Maintainability`: 313 warnings

Highest-volume rules:

- `react-compiler-no-manual-memoization`: 252 warnings
- `todo`: 56 performance errors
- `set-state-in-effect`: 41 performance errors
- `js-flatmap-filter`: 36 warnings
- `js-combine-iterations`: 33 warnings
- `no-event-handler`: 29 bug warnings
- `prefer-useReducer`: 27 bug warnings
- `no-chain-state-updates`: 27 bug warnings

### Smoke commands

Commands:

```bash
npm --prefix apps/dsa-web run test:e2e -- e2e/controlled-user-testing.smoke.spec.ts --project=chromium
npm --prefix apps/dsa-web run test:e2e -- e2e/consumer-copy-regression.smoke.spec.ts --project=chromium
npm --prefix apps/dsa-web run test:e2e -- e2e/home-scanner-evidence-browser.smoke.spec.ts --project=chromium
```

Observed result:

- `controlled-user-testing.smoke.spec.ts`: **5 passed** in **27.9s**
- `consumer-copy-regression.smoke.spec.ts`: **8 passed** in **32.4s**
- `home-scanner-evidence-browser.smoke.spec.ts`: **2 passed** in **25.3s**
- Aggregate requested smoke coverage: **15/15 passed**

Classification:

- No direct flake observed.
- Each invocation rebuilt and preview-served the app through Playwright
  `webServer`, so startup cost dominates these runs more than the assertions do.
- Every smoke run repeated the Vite large-chunk warning after minification.
  That is a maintainability/perf smell, not a proven regression from this wave.

## Top 5 React Doctor fixes worth doing next

### Correctness / user-facing hardening

1. **Scanner Safari activation refs block React Compiler optimization**
   - Evidence: `react-hooks-js/refs` errors at
     `apps/dsa-web/src/pages/UserScannerPage.tsx:3299-3304`,
     `3398-3401`, `3528-3533`
   - Supporting code:
     `useSafariWarmActivation` stores the DOM node in state via callback ref in
     `apps/dsa-web/src/hooks/useSafariInteractionReady.ts:66-107`, and
     `UserScannerPage` wires that object directly into three critical buttons at
     `apps/dsa-web/src/pages/UserScannerPage.tsx:2548-2554`.
   - Why it matters: this is a high-confidence current-wave issue on the Scanner
     route. It affects the run button, history trigger, and AI theme generation
     control. The page passes smoke today, but React Doctor is correctly flagging
     compiler-incompatible render-time ref access on a primary workflow.

2. **Home dashboard is chaining state through effects during route/task hydration**
   - Evidence:
     `react-doctor/no-adjust-state-on-prop-change` errors and
     `no-chain-state-updates` warnings at
     `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5220-5266`,
     `5291-5316`, `5361-5414`
   - Why it matters: this is the largest wave-adjacent correctness risk. The
     Home page currently opens drawers from query params, hydrates route tasks,
     backfills active ticker, clears pending analysis state, and reacts to task
     completion through multiple independent effects. That pattern is exactly
     where stale UI and one-frame mismatches appear even when smoke still passes.

3. **Home candlestick chart resets internal state from copied prop**
   - Evidence:
     `react-doctor/no-derived-useState` at
     `apps/dsa-web/src/components/home-bento/HomeCandlestickChart.tsx:523-529`
   - Why it matters: `prevTicker` is copied into local state and then used to
     reset timeframe/hover/indicator visibility when `ticker` changes. This is a
     narrow, high-confidence stale-state issue on the chart surfaced in the
     controlled-user-testing smoke.

4. **Missing accessible labels on current-wave Home/Scanner inputs**
   - Evidence:
     `react-doctor/control-has-associated-label` warnings at
     `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5677` and
     `apps/dsa-web/src/pages/UserScannerPage.tsx:3482`, `3497`, `3513`, `3558`
   - Why it matters: these are real user-facing controls, not decorative
     internals. The Home omnibar and the Scanner AI theme/custom-symbol inputs
     have visible context but no accessible label binding. This is a small fix
     with clear value and minimal product risk.

### Maintainability-only warnings

5. **Wave-heavy pages are still too large for safe incremental cleanup**
   - Evidence:
     `react-doctor/no-giant-component` on
     `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:4966`,
     `apps/dsa-web/src/pages/UserScannerPage.tsx:2212`,
     `apps/dsa-web/src/pages/MarketOverviewPage.tsx:671`,
     and `apps/dsa-web/src/components/home-bento/HomeCandlestickChart.tsx:449`
   - Why it matters: line counts are now large enough to raise the cost of every
     provenance/display follow-up:
     - `HomeBentoDashboardPage.tsx`: 6206 lines
     - `UserScannerPage.tsx`: 4083 lines
     - `MarketOverviewPage.tsx`: 974 lines
     - `HomeCandlestickChart.tsx`: 1040 lines
   - This is not the first cleanup to do, but it is the clearest reason to avoid
     mixing large refactors into small behavior fixes.

## Smoke pack assessment

### High-value specs worth keeping

- `apps/dsa-web/e2e/controlled-user-testing.smoke.spec.ts`
  - High value because it checks five product-critical workflows across Home,
    Market, Scanner, Backtest, and Options with user-facing assertions.
- `apps/dsa-web/e2e/consumer-copy-regression.smoke.spec.ts`
  - High value because it protects the consumer-safe wording boundary in both
    desktop and narrow viewports.
- `apps/dsa-web/e2e/home-scanner-evidence-browser.smoke.spec.ts`
  - High value because it focuses directly on provenance/evidence visibility and
    negative raw-leakage/trading-wording checks for the exact wave that just
    landed.

### Specs that are too broad or duplicated

- `controlled-user-testing.smoke.spec.ts` is broad.
  - It is 1310 lines and spans five routes with route-specific fixture payloads.
  - It is valuable as a pack, but it is too wide to be the only failure signal
    for future Home/Scanner cleanup.

- `consumer-copy-regression.smoke.spec.ts` is broad and partly repetitive.
  - It is 988 lines and duplicates the same safety-pattern idea across Home,
    Market, Scanner, and Options for both desktop and mobile.
  - It should stay, but its fixtures and forbidden-pattern helpers should be
    consolidated before more routes get added.

- `home-scanner-evidence-browser.smoke.spec.ts` is focused but duplicates
  substantial fixture setup already present in the other two specs.
  - It is 697 lines for two tests.
  - Its focused scope is good; its shared fixture extraction is overdue.

### Flake assessment

- No failing retries or timing flake were observed in this audit.
- The bigger medium-term risk is repeated full build/preview startup across
  separate smoke invocations, not assertion instability.

## Recommended next tasks

1. **Scanner React hardening pass**
   - Scope: fix `useSafariWarmActivation` usage for Scanner buttons and add
     missing labels on AI theme/custom symbol inputs.
   - Files likely touched:
     `apps/dsa-web/src/pages/UserScannerPage.tsx`,
     `apps/dsa-web/src/hooks/useSafariInteractionReady.ts`
   - Safe on main: **Yes**, if validation is limited to the two Scanner-related
     smoke specs plus targeted React Doctor diff review.

2. **Home chart + omnibar accessibility/state cleanup**
   - Scope: remove copied `ticker` state reset pattern in
     `HomeCandlestickChart`, add the missing Home omnibar label.
   - Files likely touched:
     `apps/dsa-web/src/components/home-bento/HomeCandlestickChart.tsx`,
     `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`
   - Safe on main: **Yes**, if kept narrow and revalidated with the Home-focused
     smoke coverage.

3. **Home dashboard state-orchestration refactor**
   - Scope: collapse the route hydration / pending analysis / drawer-opening
     effect chain into fewer state transitions with explicit ownership.
   - Files likely touched:
     `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`
   - Safe on main: **No**
   - Reason: this is a behavior-adjacent refactor in a 6206-line route with
     multiple active task flows. Use worktree/isolation.

4. **Smoke fixture consolidation for Home/Scanner provenance**
   - Scope: extract shared auth/evidence/history/provenance fixtures and shared
     forbidden-pattern helpers from the three current smoke specs.
   - Files likely touched:
     `apps/dsa-web/e2e/controlled-user-testing.smoke.spec.ts`,
     `apps/dsa-web/e2e/consumer-copy-regression.smoke.spec.ts`,
     `apps/dsa-web/e2e/home-scanner-evidence-browser.smoke.spec.ts`,
     nearby shared e2e helpers
   - Safe on main: **Yes**, because it is test-only and the duplication is
     already evidenced.

5. **Large-page decomposition / React Compiler cleanup batch**
   - Scope: split Home/Scanner/Market giant components and remove clearly dead
     manual memoization in the touched slices only.
   - Safe on main: **No**
   - Reason: high surface area, high merge conflict risk, and low value if mixed
     with correctness fixes.

## Final recommendation

The next safest, highest-value cleanup is **Task 1 plus Task 2** as one bounded
main-branch hardening wave: Scanner control activation/labels plus Home chart
and omnibar cleanup. Do **not** start with a Home mega-refactor or smoke-suite
redesign first; the current smoke pack is passing and the biggest immediate gain
comes from eliminating the high-confidence React Doctor issues on the exact
surfaces that were just expanded.
