# T-953 React Doctor Remaining Issues Triage Audit

Task ID: T-953
Mode: READ-ONLY-AUDIT with task-authorized docs-only report and local commit
Scope: React Doctor remaining-issues triage only. No source/runtime/config/CI behavior was changed.

## Executive Summary

Current `apps/dsa-web` React Doctor state on 2026-06-04 is:

- score: `68`
- total diagnostics: `745`
- severity: `138` error, `607` warning
- affected files: `55`
- categories:
  - Maintainability: `308`
  - Performance: `229`
  - Bugs: `174`
  - Accessibility: `34`

Compared with the last known "around 738" baseline, the current scan is
slightly higher at `745` issues. Treat that delta as a fresh measurement, not a
regression verdict by itself, because this audit used `react-doctor v0.3.0`
today and the earlier number was only approximate.

The remaining backlog is not one uniform compiler lane. The highest-value
future work is concentrated in a small set of route-heavy files where state and
effect orchestration patterns repeatedly trip compiler-related bug/performance
rules. The largest raw warning family, `react-compiler-no-manual-memoization`
(`247`), should not be treated as the default first batch because much of it is
maintainability-only churn and overlaps with active UX tasks.

## Audit Method

Commands used:

```bash
cd apps/dsa-web
npx react-doctor@latest --verbose --yes --no-score
npx react-doctor@latest --json --json-compact --yes --no-score
npx react-doctor@latest --score --yes
```

Notes:

- `--yes` was required to keep the scan non-interactive.
- `--no-score` was used for the full diagnostic passes to avoid extra score API
  noise; score was captured separately with `--score`.
- No React Doctor setup, config, workflow, or CI changes were made.

## What Actually Blocks Value

Do not rank the backlog by count alone. The highest-value compiler repair
targets are the repeated state/effect patterns that can change render timing,
cause extra renders, or fight React Compiler assumptions:

1. `set-state-in-effect` (`49`, error) and `no-adjust-state-on-prop-change`
   (`19`, error)
2. `no-chain-state-updates` (`35`, warning) and `no-event-handler` (`35`, warning)
3. `no-derived-state` (`19`, warning) and `no-cascading-set-state` (`13`, warning)
4. `prefer-useReducer` (`27`, warning) where many related state atoms are
   clearly coupled
5. `react-compiler-no-manual-memoization` (`247`, warning), but only after the
   state/effect flows above are stabilized

Lower-priority or churn-prone classes that should not lead the next wave:

- `todo` (`56`, error): high count but low confidence as a standalone cleanup
  batch without product-owner intent review
- broad `react-compiler-no-manual-memoization` sweeps in active routes: easy to
  create noisy diffs while parallel UX work is landing
- giant-component / render-in-render / unused-export cleanup inside unstable
  product routes: valuable later, but not before correctness-oriented state
  flow fixes

## Domain Breakdown

### Home

- Count: `106`
- Mix: Bugs `48`, Performance `32`, Maintainability `24`, Accessibility `2`
- Main files:
  - `src/pages/HomeBentoDashboardPage.tsx` (`93`)
  - `src/components/home-bento/HomeCandlestickChart.tsx` (`11`)
- High-value patterns:
  - `no-adjust-state-on-prop-change` ×12
  - `no-chain-state-updates` ×12
  - `set-state-in-effect` ×7
  - `react-compiler-no-manual-memoization` ×21
- Conflict: `WAIT`
  - Conflicts directly with active T-948 changes in
    `src/pages/HomeBentoDashboardPage.tsx`,
    `src/api/researchReadiness.ts`, and `src/types/analysis.ts`

### Scanner

- Count: `148`
- Mix: Maintainability `60`, Performance `39`, Accessibility `29`, Bugs `20`
- Main files:
  - `src/pages/UserScannerPage.tsx` (`116`)
  - `src/components/scanner/ScannerCandidatePresenters.tsx` (`31`)
- High-value patterns:
  - `react-compiler-no-manual-memoization` ×50
  - accessibility cluster in presenters (`22`) and page controls (`7`)
  - repeated `set-state-in-effect` / `no-event-handler` / `no-chain-state-updates`
- Conflict: `WAIT`
  - Scanner route ownership overlaps active T-951
  - Even if the T-951 worktree is currently clean, this area should be treated
    as reserved until that UI task lands

### Market

- Count: `124`
- Mix: Performance `53`, Maintainability `39`, Bugs `32`
- Main files:
  - `src/pages/WatchlistPage.tsx` (`57`)
  - `src/pages/MarketProviderOperationsPage.tsx` (`33`)
  - `src/pages/MarketOverviewPage.tsx` (`14`)
  - `src/components/user-alerts/UserAlertsRailPanel.tsx` (`13`)
- High-value patterns:
  - `js-flatmap-filter` ×14
  - `js-combine-iterations` ×13
  - `no-event-handler` ×10
  - `react-compiler-no-manual-memoization` ×35
- Conflict: `PARTIAL WAIT`
  - `src/pages/MarketProviderOperationsPage.tsx` is actively dirty in T-952
  - broader Market copy/domain ownership overlaps T-949, even though that
    worktree currently shows no local diff

### Options

- Count: `154`
- Mix: Maintainability `108`, Performance `28`, Bugs `18`
- Main files:
  - `src/pages/DeterministicBacktestResultPage.tsx` (`75`)
  - `src/components/backtest/BacktestResultReport.tsx` (`43`)
  - `src/pages/OptionsLabPage.tsx` (`17`)
- High-value patterns:
  - `react-compiler-no-manual-memoization` ×80
  - `set-state-in-effect` ×8
  - `unused-export` ×10
  - `no-giant-component` / `no-render-in-render` clusters in backtest surfaces
- Conflict: `PARTIAL WAIT`
  - backtest result/report files are not in active T-950 dirty diff and can be
    planned as a future isolated batch
  - `src/pages/OptionsLabPage.tsx` should wait for T-950 domain closeout even
    though the visible dirty file there is test-only today

### Portfolio

- Count: `62`
- Mix: Performance `26`, Bugs `25`, Maintainability `11`
- Main files:
  - `src/pages/PortfolioPage.tsx` (`49`)
  - `src/components/portfolio/PortfolioScenarioRiskPanel.tsx` (`12`)
- High-value patterns:
  - `set-state-in-effect` ×12
  - `no-chain-state-updates` ×8
  - `no-derived-state` ×6
  - `no-event-handler` ×6
- Conflict: `NO KNOWN ACTIVE TASK CONFLICT`

### Auth/Shell

- Count: `44`
- Mix: Performance `19`, Bugs `13`, Maintainability `10`, Accessibility `2`
- Main files:
  - `src/pages/SettingsPage.tsx` (`17`)
  - `src/components/settings/LLMChannelEditor.tsx` (`7`)
  - `src/contexts/AuthContext.tsx` (`6`)
- High-value patterns:
  - `prefer-useReducer` ×6
  - `react-compiler-no-manual-memoization` ×6
  - `preserve-manual-memoization` ×5
  - `prefer-html-dialog` in `src/components/auth/AuthGuardOverlay.tsx`
- Conflict: `NO KNOWN ACTIVE TASK CONFLICT`

### Admin/Ops

- Count: `121`
- Mix: Maintainability `60`, Performance `46`, Bugs `14`, Accessibility `1`
- Main files:
  - `src/pages/AdminLogsPage.tsx` (`48`)
  - `src/pages/MarketProviderOperationsPage.tsx` (`33`)
  - `src/pages/AdminNotificationsPage.tsx` (`22`)
- High-value patterns:
  - `react-compiler-no-manual-memoization` ×57
  - `todo` ×15
  - `js-combine-iterations` ×11
  - `js-flatmap-filter` ×10
- Conflict: `PARTIAL WAIT`
  - Conflicts directly with active T-952 on
    `AdminUsersPage.tsx`, `AdminEvidenceWorkflowPage.tsx`,
    `AdminProviderCircuitDiagnosticsPage.tsx`,
    `SystemSettingsPage.tsx`, and `MarketProviderOperationsPage.tsx`
  - `AdminLogsPage.tsx` and `AdminNotificationsPage.tsx` appear free for a
    later isolated batch after T-952 lands

### Shared Components/Hooks

- Count: `11`
- Mix: Maintainability `5`, Performance `4`, Bugs `2`
- Main files:
  - `src/components/report/ReportPriceChart.tsx` (`4`)
  - `src/hooks/useSystemConfig.ts` (`3`)
  - `src/hooks/useElementSize.ts` (`2`)
- Conflict: `LOW`
  - Still avoid broad shared-hook churn while page-level tasks are active

## Future Repair Batches

These batches are intentionally non-overlapping and independently valuable.

### Batch 1: Home state/effect correctness collapse

Type: high-confidence compiler correctness fixes

Target:

- `src/pages/HomeBentoDashboardPage.tsx`
- `src/components/home-bento/HomeCandlestickChart.tsx`

Fix focus:

- replace state copied from props/effects
- collapse chained effect-driven updates
- move event logic out of effects

Why this batch matters:

- Home has one of the highest concentrations of real correctness-style compiler
  warnings, not just cosmetic memo cleanup

When:

- `WAIT` until T-948 lands

### Batch 2: Scanner route compiler + accessibility stabilization

Type: correctness fixes plus accessibility fixes

Target:

- `src/pages/UserScannerPage.tsx`
- `src/components/scanner/ScannerCandidatePresenters.tsx`

Fix focus:

- state/effect event-chain cleanup
- reduce refs-heavy patterns only where clearly compiler-hostile
- fix click/keyboard semantics and missing labels

Why this batch matters:

- highest single-file issue count in the repo (`116` on `UserScannerPage.tsx`)
- strongest accessibility concentration (`29` in Scanner domain)

When:

- `WAIT` until T-951 lands

### Batch 3: Backtest/Options compiler cleanup without product copy churn

Type: mixed correctness/performance/maintainability, mostly safe compiler cleanup

Target:

- `src/pages/DeterministicBacktestResultPage.tsx`
- `src/components/backtest/BacktestResultReport.tsx`
- `src/components/backtest/shared.tsx`

Fix focus:

- state/effect simplification
- remove redundant manual memoization after each flow is verified
- combine repeated iterations in report rendering
- avoid touching `OptionsLabPage.tsx` copy/layout in this batch

Why this batch matters:

- large issue yield (`127` combined) with relatively limited overlap with the
  active Options copy task

When:

- can start after confirming T-950 does not widen into these files

### Batch 4: Portfolio state flow normalization

Type: high-confidence compiler correctness fixes

Target:

- `src/pages/PortfolioPage.tsx`
- `src/components/portfolio/PortfolioScenarioRiskPanel.tsx`

Fix focus:

- remove `set-state-in-effect` and derived-state loops
- collapse chain updates into reducer/event-driven state transitions

Why this batch matters:

- concentrated correctness/performance cluster with no known active task conflict

When:

- `READY` as a future isolated write task

### Batch 5: Admin/Ops safe subset after T-952

Type: performance/memoization fixes plus maintainability cleanup

Target:

- first wave: `src/pages/AdminLogsPage.tsx`, `src/pages/AdminNotificationsPage.tsx`
- defer wave: `MarketProviderOperationsPage.tsx` and T-952-owned pages

Fix focus:

- iteration combining
- scoped memo cleanup
- avoid disclosure/copy/layout churn

Why this batch matters:

- `70` issues across Logs + Notifications alone, mostly independent of current
  admin disclosure work

When:

- first wave after T-952 lands and conflict check is rerun

### Batch 6: Shared low-risk accessibility and shell cleanup

Type: accessibility fixes plus maintainability-only warnings

Target:

- `src/components/auth/AuthGuardOverlay.tsx`
- `src/pages/SettingsPage.tsx`
- `src/components/settings/LLMChannelEditor.tsx`
- `src/contexts/AuthContext.tsx`

Fix focus:

- native dialog adoption where practical
- shell/settings reducer cleanup
- preserve-manual-memoization review before removing any protected memo

Why this batch matters:

- low blast radius, no obvious current task collision

When:

- `READY` as a smaller follow-up after a page-heavy batch lands

## Do Not Fix Yet

The following classes should explicitly wait because they are likely to create
churn, conflict, or low-signal noise:

- any Home route compiler cleanup before T-948 lands
- any Scanner route/presenter cleanup before T-951 lands
- any Admin Provider Ops / Admin Users / Admin Evidence / System Settings
  cleanup before T-952 lands
- any `OptionsLabPage.tsx` copy/layout/memo cleanup before T-950 closes
- broad Market-domain cleanup before T-949 ownership is confirmed closed
- repo-wide `react-compiler-no-manual-memoization` search/replace sweeps
- repo-wide `todo` cleanup without product intent review
- giant-component breakup refactors in unstable product routes before the
  correctness-oriented batches above reduce state/effect complexity

## Recommended Next Task

Best next bounded write task after current parallel UX work settles:

1. `T-954 React Doctor portfolio state/effect normalization`

Why this is the safest next slice:

- no known overlap with T-948/T-949/T-950/T-951/T-952
- concentrated high-confidence correctness fixes
- small enough to validate without triggering cross-route churn

Secondary candidate after T-948 lands:

1. `T-955 React Doctor home state/effect cleanup`

## Validation And No-Write Proof

Validation required by the task:

```bash
git diff --name-only
git diff --check
./scripts/release_secret_scan.sh
git status --short --branch
```

No-write confirmation for protected areas:

- no source code changed
- no test files changed
- no package/lock/config/CI/workflow files changed
- no React Doctor setup or CI integration was added
- only this audit markdown file is allowed in the final diff
