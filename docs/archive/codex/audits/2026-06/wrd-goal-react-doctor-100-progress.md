# WRD React Doctor 100 Progress

Task: raise `apps/dsa-web` React Doctor score to 100 from latest `origin/main`.

Branch: `codex/wrd-goal-react-doctor-100`
Workspace: `/Users/yehengli/worktrees/wrd-goal-react-doctor-100`
Base: `origin/main` at `ad46efda`

## Checkpoint Policy

- Establish a baseline before repairs.
- After every passing coherent repair batch, update this file, commit, and push immediately.
- Keep batches small enough that an interruption loses at most one uncommitted batch.
- If quota, uncertainty, forbidden scope, or unsafe semantics blocks progress, leave the branch clean when possible and report the latest pushed checkpoint plus blockers.
- Do not change forbidden backend/API/provider/cache/runtime/auth/package/lockfile/config/CI domains.

## Baseline

Run after `git fetch origin` from clean dedicated worktree.

- Score: `61`
- Total diagnostics: `567`
- Errors: `112`
- Warnings: `455`
- Affected files: `45`
- Top rules:
  - `react-compiler-no-manual-memoization`: `224`
  - `todo`: `54`
  - `set-state-in-effect`: `41`
  - `no-event-handler`: `30`
  - `no-chain-state-updates`: `27`
  - `no-giant-component`: `25`
  - `prefer-useReducer`: `23`
  - `unused-export`: `16`

## Candidate Manifest

Safe first:

- Remove redundant manual memoization where React Doctor says React Compiler already caches the value/function.
- Replace render helpers that return JSX from inline calls with small components.
- Clean single-pass array derivations for display-only entries.
- Use immutable sort/copy fixes when the current behavior is already immutable.
- Remove unused exports only after confirming no local imports depend on them.

Deferred or blocker-prone:

- `set-state-in-effect`, `no-adjust-state-on-prop-change`, `no-event-handler`, `no-chain-state-updates`: only touch with clear focused coverage and narrowly mechanical behavior-preserving changes.
- `unused-dependency` in `package.json`: forbidden by current scope because package/lockfile changes are disallowed.
- Scanner scoring/ranking/filtering/cap semantics, portfolio accounting, options payoff/scoring/optimizer/no-advice semantics, backtest math/fills/costs/metrics/stored semantics, provider/cache/API/auth/runtime/config/CI: forbidden unless explicitly re-scoped.

## Batch 1: Backtest Report Display Cleanup

Status: committed and pushed as checkpoint `7e28214f`.

Files changed:

- `apps/dsa-web/src/components/backtest/BacktestResultReport.tsx`

Changes:

- Removed redundant `useMemo` wrappers from display-only derived values in the report component.
- Replaced `renderValue()` inline JSX helper with `MetricValue` component.
- Replaced repeated `filter().map()` display entry cleanup with `compactEntries()`.

Diagnostics after batch:

- Score: `61`
- Total diagnostics: `526`
- Errors: `112`
- Warnings: `414`
- Affected files: `45`
- Reduced total diagnostics: `41`
- Reduced by rule:
  - `react-compiler-no-manual-memoization`: `224 -> 194` (`-30`)
  - `js-combine-iterations`: `10 -> 6` (`-4`)
  - `no-render-in-render`: `10 -> 3` (`-7`)
- React Doctor diff for changed file: `0` diagnostics.

Validations run:

- `git diff --check` -> pass
- `./scripts/release_secret_scan.sh` -> pass
- `npm --prefix apps/dsa-web run test -- 'src/components/backtest/__tests__/BacktestResultReport.test.tsx'` -> pass, `18` tests
- `npm --prefix apps/dsa-web run lint` -> pass
- `npm --prefix apps/dsa-web run build` -> pass with existing Vite chunk-size warning
- `npx react-doctor@latest --json --json-compact --yes --no-score` -> remaining diagnostics expected, totals above
- `npx react-doctor@latest --score --yes` -> `61`

Next candidates:

- `UserScannerPage.tsx`: high diagnostic count, start with manual memoization and display-only array derivations; avoid scanner ranking/filtering/cap semantics.
- `HomeBentoDashboardPage.tsx`: many memo/state diagnostics; start only with manual memoization or pure display derivations, defer prop/state adjustment unless tests clearly cover it.
- `DeterministicBacktestResultPage.tsx`: manual memoization and array cleanup are candidates; avoid backtest math/fills/costs/metrics/stored semantics.
- Unused exports in frontend display/shared components can be considered after focused import search.

## Batch 2: Small Display Derivation Cleanup

Status: committed and pushed as checkpoint `fdd3c756`.

Files changed:

- `apps/dsa-web/src/components/portfolio/PortfolioScenarioRiskPanel.tsx`
- `apps/dsa-web/src/components/watchlist/LeveragedEtfMapper.tsx`

Changes:

- Hoisted portfolio scenario number formatters to module scope.
- Removed a redundant `useMemo` for portfolio scenario symbol options.
- Replaced the leveraged ETF mapper `useMemo` with a file-local pure result builder.

Diagnostics after batch:

- Score: `61`
- Total diagnostics: `521`
- Errors: `112`
- Warnings: `409`
- Affected files: `44`
- Reduced total diagnostics from previous checkpoint: `5`
- Reduced total diagnostics from baseline: `46`
- Reduced by rule from previous checkpoint:
  - `js-hoist-intl`: `7 -> 4` (`-3`)
  - `react-compiler-no-manual-memoization`: `194 -> 192` (`-2`)
- React Doctor diff for changed files: `0` diagnostics.

Validations run:

- `git diff --check` -> pass
- `./scripts/release_secret_scan.sh` -> pass
- `npm --prefix apps/dsa-web run test -- 'src/components/portfolio/__tests__/PortfolioScenarioRiskPanel.test.tsx' 'src/components/watchlist/__tests__/LeveragedEtfMapper.test.tsx'` -> pass, `7` tests
- `npm --prefix apps/dsa-web run lint` -> pass
- `npm --prefix apps/dsa-web run build` -> pass with existing Vite chunk-size warning
- `npx react-doctor@latest --json --json-compact --yes --no-score` -> remaining diagnostics expected, totals above
- `npx react-doctor@latest --score --yes` -> `61`

Next candidates:

- Continue with small pure derivations: `dataSourceLibraryShared.ts` `Set` lookup, remaining `js-hoist-intl`, and immutable sort/copy fixes.
- Avoid `AdminLogsPage.tsx` manual `useCallback` cleanup for now because several callbacks are `useEffect` dependencies; direct removal can change behavior in non-compiler test environments.
- Defer state/effect flow findings unless focused tests cover the exact flow and the change is narrowly mechanical.

## Batch 3: Watchlist Date Formatter Hoist

Status: committed and pushed as checkpoint `403d16d7`.

Files changed:

- `apps/dsa-web/src/pages/WatchlistPage.tsx`

Changes:

- Hoisted language-specific watchlist date-time formatters to module scope.
- Reverted an attempted `dataSourceLibraryShared.ts` alias lookup cleanup before checkpoint because it did not reduce React Doctor diagnostics.

Diagnostics after batch:

- Score: `61`
- Total diagnostics: `520`
- Errors: `112`
- Warnings: `408`
- Affected files: `44`
- Reduced total diagnostics from previous checkpoint: `1`
- Reduced total diagnostics from baseline: `47`
- Reduced by rule from previous checkpoint:
  - `js-hoist-intl`: `4 -> 3` (`-1`)
- React Doctor diff for changed file: `0` diagnostics.

Validations run:

- `git diff --check` -> pass
- `./scripts/release_secret_scan.sh` -> pass
- `npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/WatchlistPage.test.tsx' --no-file-parallelism` -> pass, `47` tests
- `npm --prefix apps/dsa-web run lint` -> pass
- `npm --prefix apps/dsa-web run build` -> pass with existing Vite chunk-size warning
- `npx react-doctor@latest --json --json-compact --yes --no-score` -> remaining diagnostics expected, totals above
- `npx react-doctor@latest --score --yes` -> `61`

Validation note:

- An earlier concurrent gate run of `npm --prefix apps/dsa-web run test -- 'src/components/settings/__tests__/dataSourceLibraryShared.test.ts' 'src/pages/__tests__/WatchlistPage.test.tsx'` failed 2 Watchlist assertions while lint/build/React Doctor were running in parallel. The same focused command immediately passed `52` tests when rerun, and the Watchlist file passed `47` tests with `--no-file-parallelism`. Treated as a resource/timing flake, not a product-code failure.

Next candidates:

- Remaining `js-hoist-intl`: `HomeBentoDashboardPage.tsx` and carefully bounded `UserScannerPage.tsx` formatter helpers.
- Remaining immutable sort/copy: evaluate `OptionsLabPage.tsx` first; avoid scanner ranking/filtering/cap semantics unless the line is purely display-local and tests prove parity.
- Manual memoization: continue only where removing memo does not affect function identity used by effects or child memo contracts in Vitest/non-compiler paths.

## Batch 4: Scanner And Home Formatter Hoist

Status: committed and pushed as checkpoint `a829b39e`.

Files changed:

- `apps/dsa-web/src/pages/UserScannerPage.tsx`
- `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`

Changes:

- Hoisted User Scanner date-time and date-only formatters to module scope.
- Hoisted Home history timestamp formatter to module scope.
- Touched only display formatter helpers; scanner scoring/ranking/filtering/cap semantics and Home selection logic were not changed.

Diagnostics after batch:

- Score: `61`
- Total diagnostics: `517`
- Errors: `112`
- Warnings: `405`
- Affected files: `44`
- Reduced total diagnostics from previous checkpoint: `3`
- Reduced total diagnostics from baseline: `50`
- Reduced by rule from previous checkpoint:
  - `js-hoist-intl`: `3 -> 0` (`-3`)
- React Doctor diff for changed files: `0` diagnostics.

Validations run:

- `git diff --check` -> pass
- `./scripts/release_secret_scan.sh` -> pass
- `npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/UserScannerPage.test.tsx' 'src/pages/__tests__/HomeSurfacePage.test.tsx'` -> pass, `163` tests
- `npm --prefix apps/dsa-web run lint` -> pass
- `npm --prefix apps/dsa-web run build` -> pass with existing Vite chunk-size warning
- `npx react-doctor@latest --json --json-compact --yes --no-score` -> remaining diagnostics expected, totals above
- `npx react-doctor@latest --score --yes` -> `61`

Next candidates:

- Consider `OptionsLabPage.tsx` immutable sort/copy only if focused tests show no options payoff/scoring/strategy/no-advice semantic drift.
- Consider remaining display-only manual memoization in files where callbacks are not `useEffect` dependencies.
- Remaining high-count findings are increasingly state/effect flow, giant component, and reducer suggestions; many require semantic caution or broader refactor boundaries.

## Batch 5: Backtest Shared Dead Export Removal

Status: committed and pushed as checkpoint `70aaa88d`.

Files changed:

- `apps/dsa-web/src/components/backtest/shared.tsx`

Changes:

- Removed dead exported backtest display helpers and table/card components after repository-wide import search found no source or test consumers.
- Removed only unreachable display code; backtest math, fills, costs, metrics, stored semantics, and rendered active paths were not changed.

Diagnostics after batch:

- Score: `61`
- Total diagnostics: `508`
- Errors: `112`
- Warnings: `396`
- Affected files: `43`
- Reduced total diagnostics from previous checkpoint: `9`
- Reduced total diagnostics from baseline: `59`
- Reduced by rule from previous checkpoint:
  - `unused-export`: `16 -> 7` (`-9`)
- React Doctor diff for changed file:
  - `src/components/backtest/shared.tsx`: `9 -> 0` (`-9`)

Validations run:

- `git diff --check` -> pass
- `./scripts/release_secret_scan.sh` -> pass
- `npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/BacktestPage.test.tsx' 'src/pages/__tests__/DeterministicBacktestResultPage.test.tsx' 'src/pages/__tests__/RuleBacktestComparePage.test.tsx' --no-file-parallelism` -> pass, `64` tests
- `npm --prefix apps/dsa-web run lint` -> pass
- `npm --prefix apps/dsa-web run build` -> pass with existing Vite chunk-size warning
- `npx react-doctor@latest --json --json-compact --yes --no-score` -> remaining diagnostics expected, totals above
- `npx react-doctor@latest --score --yes` -> `61`

Next candidates:

- Remaining `unused-export` in scanner presenters and small hooks/components; remove only if repository-wide search proves no source or test consumers, and focused tests cover the importing page.
- Low-risk accessibility semantics such as tag/role equivalence can be considered only when visible layout and route behavior remain unchanged and focused tests cover the route.
- Manual memoization remains mostly blocked where callbacks are effect dependencies or child identity contracts in non-compiler tests.
- State/effect/reducer/giant-component findings remain blocker-prone without narrower behavioral coverage.

## Batch 6: Frontend Presenter Dead Export Cleanup

Status: committed and pushed as checkpoint `58246031`.

Files changed:

- `apps/dsa-web/src/components/home-bento/DeepReportDrawer.tsx`
- `apps/dsa-web/src/components/scanner/ScannerCandidatePresenters.tsx`
- `apps/dsa-web/src/components/scanner/ScannerDisplayAtoms.tsx`
- `apps/dsa-web/src/hooks/useDashboardLifecycle.ts`

Changes:

- Removed unused default exports from Home Bento drawer and dashboard lifecycle hook while keeping their named exports unchanged.
- Removed unreferenced scanner presenter components and their now-unused shared atom.
- Left the scanner page's active presenter exports intact; scanner score/ranking/filtering/cap semantics were not changed.

Diagnostics after batch:

- Score: `61`
- Total diagnostics: `500`
- Errors: `112`
- Warnings: `388`
- Affected files: `41`
- Reduced total diagnostics from previous checkpoint: `8`
- Reduced total diagnostics from baseline: `67`
- Reduced by rule from previous checkpoint:
  - `unused-export`: `7 -> 2` (`-5`)
  - `no-many-boolean-props`: `6 -> 4` (`-2`)
  - `no-noninteractive-element-interactions`: `2 -> 1` (`-1`)
- React Doctor diff for changed files:
  - `src/components/scanner/ScannerCandidatePresenters.tsx`: `9 -> 3` (`-6`)
  - `src/components/home-bento/DeepReportDrawer.tsx`: `1 -> 0` (`-1`)
  - `src/hooks/useDashboardLifecycle.ts`: `1 -> 0` (`-1`)
  - `src/components/scanner/ScannerDisplayAtoms.tsx`: `0`

Validations run:

- `git diff --check` -> pass
- `./scripts/release_secret_scan.sh` -> pass
- `npm --prefix apps/dsa-web run test -- 'src/hooks/__tests__/useDashboardLifecycle.test.tsx' 'src/pages/__tests__/UserScannerPage.test.tsx' 'src/pages/__tests__/HomeSurfacePage.test.tsx' --no-file-parallelism` -> pass, `165` tests
- `npm --prefix apps/dsa-web run lint` -> pass
- `npm --prefix apps/dsa-web run build` -> pass with existing Vite chunk-size warning
- `npx react-doctor@latest --json --json-compact --yes --no-score` -> remaining diagnostics expected, totals above
- `npx react-doctor@latest --score --yes` -> `61`

Next candidates:

- Remaining `unused-export`:
  - `apps/dsa-web/src/api/error.ts` `isApiRequestError`: deferred because API client boundary is close to forbidden API scope.
  - `apps/dsa-web/src/components/backtest/DeterministicBacktestFlow.tsx` default export: removal likely requires deleting or reshaping a large unused component, which is too broad for a small safe batch.
- Remaining scanner presenter findings are on active components and require accessibility/prop-contract changes; evaluate separately with route tests before touching.
- Manual memoization remains mostly unsafe where callbacks are `useEffect` dependencies or non-compiler tests depend on stable identity.

## Batch 7: Deterministic Backtest Display Iteration Cleanup

Status: committed and pushed as checkpoint `9f498db0`.

Files changed:

- `apps/dsa-web/src/pages/DeterministicBacktestResultPage.tsx`

Changes:

- Replaced two display-only `filter().map()` derivations with single-pass `reduce()` derivations.
- Touched risk-control visual rows and parsed-strategy summary labels only; backtest math, fills, costs, metrics, stored semantics, and result payload handling were not changed.

Diagnostics after batch:

- Score: `61`
- Total diagnostics: `498`
- Errors: `112`
- Warnings: `386`
- Affected files: `41`
- Reduced total diagnostics from previous checkpoint: `2`
- Reduced total diagnostics from baseline: `69`
- Reduced by rule from previous checkpoint:
  - `js-combine-iterations`: `6 -> 4` (`-2`)
- React Doctor diff for changed file:
  - `src/pages/DeterministicBacktestResultPage.tsx`: `75 -> 73` (`-2`)

Validations run:

- `git diff --check` -> pass
- `./scripts/release_secret_scan.sh` -> pass
- `npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/DeterministicBacktestResultPage.test.tsx' 'src/pages/tests/DeterministicBacktestResultPage.test.tsx' --no-file-parallelism` -> pass, `28` tests
- `npm --prefix apps/dsa-web run lint` -> pass
- `npm --prefix apps/dsa-web run build` -> pass with existing Vite chunk-size warning
- `npx react-doctor@latest --json --json-compact --yes --no-score` -> remaining diagnostics expected, totals above
- `npx react-doctor@latest --score --yes` -> `61`

Next candidates:

- `UserScannerPage.tsx` has remaining array-iteration findings, but several are near scanner candidate/ranking derivations; only display-only transformations should be considered.
- Accessibility warnings require care because several flagged elements are scroll containers or filter groups where React Doctor's suggested semantic replacement may not preserve intended keyboard behavior.
- Remaining deterministic page findings are mostly state/effect flow, giant component, and manual memoization tied to callback identity; defer without narrower behavior coverage.

## Batch 8: Scanner Helper Iteration Cleanup

Status: committed and pushed as checkpoint `ca9e6eb0`.

Files changed:

- `apps/dsa-web/src/pages/UserScannerPage.tsx`

Changes:

- Replaced scanner helper `map().filter(Boolean)` and display-count derivations with `flatMap()` or single-pass `reduce()` equivalents.
- Touched input/string normalization, notes de-duplication, symbol token counting, and rejection bucket display counts only.
- Explicitly skipped preview threshold and sort/ranking findings because they are closer to scanner selection/ranking semantics.

Diagnostics after batch:

- Score: `61`
- Total diagnostics: `491`
- Errors: `112`
- Warnings: `379`
- Affected files: `41`
- Reduced total diagnostics from previous checkpoint: `7`
- Reduced total diagnostics from baseline: `76`
- Reduced by rule from previous checkpoint:
  - `js-flatmap-filter`: `4 -> 0` (`-4`)
  - `js-combine-iterations`: `4 -> 1` (`-3`)
- React Doctor diff for changed file:
  - `src/pages/UserScannerPage.tsx`: `103 -> 96` (`-7`)

Validations run:

- `git diff --check` -> pass
- `./scripts/release_secret_scan.sh` -> pass
- `npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/UserScannerPage.test.tsx' --no-file-parallelism` -> pass, `88` tests
- `npm --prefix apps/dsa-web run lint` -> pass
- `npm --prefix apps/dsa-web run build` -> pass with existing Vite chunk-size warning
- `npx react-doctor@latest --json --json-compact --yes --no-score` -> remaining diagnostics expected, totals above
- `npx react-doctor@latest --score --yes` -> `61`

Next candidates:

- The remaining `UserScannerPage.tsx` `js-combine-iterations` at preview threshold and `js-tosorted-immutable` are deferred because they sit on scanner threshold/ranking flow.
- Remaining `js-set-map-lookups` in Home/Data Source need separate proof; a previous data-source Set attempt did not reduce diagnostics.
- Remaining safe work is increasingly sparse; most high-count findings are state/effect/reducer/manual memoization changes with behavior risk.

## Batch 9: Admin Cost Empty Counter Direct Derivation

Status: committed and pushed as checkpoint `4f180562`.

Files changed:

- `apps/dsa-web/src/pages/AdminCostObservabilityPage.tsx`

Changes:

- Removed a redundant render-local `useMemo` for the empty-counter boolean.
- Kept admin cost data fetching, duplicate summary payload handling, ledger/risk math, and route behavior unchanged.

Diagnostics after batch:

- Score: `61`
- Total diagnostics: `490`
- Errors: `112`
- Warnings: `378`
- Affected files: `41`
- Reduced total diagnostics from previous checkpoint: `1`
- Reduced total diagnostics from baseline: `77`
- Reduced by rule from previous checkpoint:
  - `react-compiler-no-manual-memoization`: `192 -> 191` (`-1`)
- React Doctor diff for changed file:
  - `src/pages/AdminCostObservabilityPage.tsx`: `2 -> 1` (`-1`)

Validations run:

- `git diff --check` -> pass
- `./scripts/release_secret_scan.sh` -> pass
- `npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/AdminCostObservabilityPage.test.tsx' --no-file-parallelism` -> pass, `25` tests
- `npm --prefix apps/dsa-web run lint` -> pass
- `npm --prefix apps/dsa-web run build` -> pass with existing Vite chunk-size warning
- `npx react-doctor@latest --json --json-compact --yes --no-score` -> remaining diagnostics expected, totals above
- `npx react-doctor@latest --score --yes` -> `61`

Next candidates:

- Remaining single manual memoization findings are either auth/config/load-effect boundaries or draft-state source objects; defer without stronger behavioral coverage.
- `HomeBentoDashboardPage.tsx` `js-set-map-lookups` appears to be string substring matching, not a Set-compatible array lookup.
- Remaining score gains likely require unsafe state/effect/manual memo changes or broader component decomposition.

## Batch 10: Home Skeleton Stable Default

Status: committed and pushed as checkpoint `b7dc5ef0`.

Files changed:

- `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`

Changes:

- Moved the `InPlaceDecisionSkeleton` empty `progressModules` default to a module-scope constant.
- Kept Home dashboard route behavior, visible copy, layout, and selection logic unchanged.

Diagnostics after batch:

- Score: `61`
- Total diagnostics: `489`
- Errors: `112`
- Warnings: `377`
- Affected files: `41`
- Reduced total diagnostics from previous checkpoint: `1`
- Reduced total diagnostics from baseline: `78`
- Reduced by rule from previous checkpoint:
  - `rerender-memo-with-default-value`: `1 -> 0` (`-1`)
- React Doctor diff for changed file:
  - `src/pages/HomeBentoDashboardPage.tsx`: `79 -> 78` (`-1`)

Validations run:

- `git diff --check` -> pass
- `./scripts/release_secret_scan.sh` -> pass
- `npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/HomeSurfacePage.test.tsx' --no-file-parallelism` -> pass, `75` tests
- `npm --prefix apps/dsa-web run lint` -> pass
- `npm --prefix apps/dsa-web run build` -> pass with existing Vite chunk-size warning
- `npx react-doctor@latest --json --json-compact --yes --no-score` -> remaining diagnostics expected, totals above
- `npx react-doctor@latest --score --yes` -> `61`

Next candidates:

- Stop unless explicitly re-scoped: remaining findings require forbidden domains, unsafe semantic changes, or broader state/effect/component decomposition.
- If re-scoped later, start with tests for a single route and explicitly allow the relevant state/effect or accessibility semantic contract.

## Batch 11: Home Chart Native Status Output

Status: committed and pushed as checkpoint `9103ed2c`.

Files changed:

- `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx`

Changes:

- Replaced the Home chart fallback `role="status"` wrapper with the native `<output>` element.
- Added `block` to preserve the previous block-level wrapper layout.
- Added a focused Home Surface assertion that the fallback still exposes the `status` role and now renders as `OUTPUT`.
- Kept Home dashboard route behavior, visible copy, and chart fallback layout unchanged.

Diagnostics after batch:

- Score: `61`
- Total diagnostics: `488`
- Errors: `112`
- Warnings: `376`
- Affected files: `41`
- Reduced total diagnostics from previous checkpoint: `1`
- Reduced total diagnostics from baseline: `79`
- Reduced by rule from previous checkpoint:
  - `prefer-tag-over-role`: `2 -> 1` (`-1`)
- React Doctor diff for changed file:
  - `src/pages/HomeBentoDashboardPage.tsx`: `78 -> 77` (`-1`)

Validations run:

- `git diff --check` -> pass
- `./scripts/release_secret_scan.sh` -> pass
- `npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/HomeSurfacePage.test.tsx' --no-file-parallelism` -> pass, `75` tests
- `npm --prefix apps/dsa-web run lint` -> pass
- `npm --prefix apps/dsa-web run build` -> pass with existing Vite chunk-size warning
- `npx react-doctor@latest --json --json-compact --yes --no-score` -> remaining diagnostics expected, totals above
- `npx react-doctor@latest --score --yes` -> `61`

Next candidates:

- Remaining `prefer-tag-over-role` on the scanner filter bar is not equivalent: the flagged element groups filter buttons, while `<address>` would imply contact/address semantics.
- Remaining accessibility findings need route-specific semantic design and focused tests before changes.
- Remaining score gains still require forbidden domains, unsafe semantic changes, or broader state/effect/component decomposition.

## Batch 12: Shared Element Size Ref Compatibility

Status: included in the checkpoint commit for this batch after local validation.

Files changed:

- `apps/dsa-web/src/hooks/useElementSize.ts`
- `apps/dsa-web/src/hooks/__tests__/useElementSize.test.tsx`
- `apps/dsa-web/src/components/report/ReportPriceChart.tsx`
- `apps/dsa-web/src/components/report/__tests__/StandardReportPanel.test.tsx`
- `apps/dsa-web/src/components/backtest/DeterministicBacktestChartWorkspace.tsx`

Changes:

- Replaced the custom object ref setter in `useElementSize` with a stable callable ref that also preserves `.current` compatibility for existing chart consumers.
- Updated `ReportPriceChart` to call the shared measurement ref while continuing to maintain its local chart-stage ref.
- Removed an obsolete deterministic chart workspace cast now that the returned ref is directly compatible with React's `ref` prop.
- Added hook-level tests for ref identity, `.current` compatibility, initial node measurement, ResizeObserver updates, and detach cleanup.
- Updated the report panel test mock to model the new callable ref contract.

Diagnostics after batch:

- Score: `61`
- Total diagnostics: `486`
- Errors: `110`
- Warnings: `376`
- Affected files: `40`
- Reduced total diagnostics from previous checkpoint: `2`
- Reduced total diagnostics from baseline: `81`
- Reduced by rule from previous checkpoint:
  - `todo`: `54 -> 52` (`-2`)
- React Doctor diff for changed files:
  - `src/hooks/useElementSize.ts`: `2 -> 0` (`-2`)
  - `src/components/report/ReportPriceChart.tsx`: `4 -> 4`
  - `src/components/backtest/DeterministicBacktestChartWorkspace.tsx`: `1 -> 1`
  - `src/components/report/__tests__/StandardReportPanel.test.tsx`: `0 -> 0`

Validations run:

- `npm --prefix apps/dsa-web run test -- 'src/hooks/__tests__/useElementSize.test.tsx' --no-file-parallelism` -> pass, `3` tests
- `npm --prefix apps/dsa-web run test -- 'src/hooks/__tests__/useElementSize.test.tsx' 'src/pages/__tests__/HomeSurfacePage.test.tsx' 'src/components/report/__tests__/StandardReportPanel.test.tsx' 'src/pages/__tests__/DeterministicBacktestResultPage.test.tsx' 'src/pages/tests/DeterministicBacktestResultPage.test.tsx' --no-file-parallelism` -> pass, `111` tests
- `npm --prefix apps/dsa-web run lint` -> pass
- `npm --prefix apps/dsa-web run build` -> pass with existing Vite chunk-size warning
- `npx react-doctor@latest --json --json-compact --yes --no-score` -> remaining diagnostics expected, totals above
- `npx react-doctor@latest --score --yes` -> `61`

Next candidates:

- Re-check remaining low-count diagnostics after this checkpoint, but treat shared chart measurement and chart interaction paths as exhausted for this task.
- Remaining `todo` errors are concentrated in state/effect/action-flow areas and should not be chased without route-specific behavioral tests.
- Remaining accessibility findings still need semantic design and tests rather than tag substitutions.

## Batch 13: Market Overview Display Derivation Cleanup

Status: included in the checkpoint commit for this batch after local validation.

Files changed:

- `apps/dsa-web/src/pages/MarketOverviewPage.tsx`

Changes:

- Removed a redundant `useMemo` around the market research readiness view, keeping the same display-only builder input.
- Replaced the initial local snapshot `useMemo` with lazy `useState` so localStorage hydration still runs only once during route initialization.
- Left market overview polling, provider gating, panel request order, cache/dedupe behavior, and auto-revalidation timing unchanged.

Diagnostics after batch:

- Score: `61`
- Total diagnostics: `482`
- Errors: `110`
- Warnings: `372`
- Affected files: `40`
- Reduced total diagnostics from previous checkpoint: `4`
- Reduced total diagnostics from baseline: `85`
- Reduced by rule from previous checkpoint:
  - `react-compiler-no-manual-memoization`: `191 -> 189` (`-2`)
  - `no-chain-state-updates`: `27 -> 26` (`-1`)
  - `no-giant-component`: `25 -> 24` (`-1`)
- React Doctor diff for changed file:
  - `src/pages/MarketOverviewPage.tsx`: `14 -> 10` (`-4`)

Validations run:

- `npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/MarketOverviewPage.test.tsx' --no-file-parallelism` -> pass, `89` tests
- `git diff --check` -> pass
- `./scripts/release_secret_scan.sh` -> pass
- `npm --prefix apps/dsa-web run lint` -> pass
- `npm --prefix apps/dsa-web run build` -> pass with existing Vite chunk-size warning
- `npx react-doctor@latest --json --json-compact --yes --no-score` -> remaining diagnostics expected, totals above
- `npx react-doctor@latest --score --yes` -> `61`

Next candidates:

- Remaining `MarketOverviewPage.tsx` callbacks are effect, polling, timeout, and refresh dependencies; removing memoization would change non-compiler runtime behavior.
- Remaining `autoRevalidateTick` is a control state used to re-run scheduling effects; ref conversion would change refresh timing.
- Continue only if another pure display derivation appears outside protected domains.

## Batch 14: Home Trace Display Memo Cleanup

Status: included in the checkpoint commit for this batch after local validation.

Files changed:

- `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`

Changes:

- Removed redundant `useMemo` wrappers around Home skeleton timeline display state, standby copy, trace/readiness/evidence frame derivations, reanalysis ticker display state, and delete dialog copy.
- Kept dashboard selection, dashboard payload selection, route/task hydration, active evidence ticker effects, chart context, and task lifecycle behavior unchanged.
- Rejected a Watchlist display-memo candidate after focused Watchlist tests exposed a loading/summary timing regression; Watchlist was restored before this checkpoint.

Diagnostics after batch:

- Score: `61`
- Total diagnostics: `466`
- Errors: `110`
- Warnings: `356`
- Affected files: `40`
- Reduced total diagnostics from previous checkpoint: `16`
- Reduced total diagnostics from baseline: `101`
- Reduced by rule from previous checkpoint:
  - `react-compiler-no-manual-memoization`: `189 -> 173` (`-16`)
- React Doctor diff for changed file:
  - `src/pages/HomeBentoDashboardPage.tsx`: `77 -> 61` (`-16`)

Validations run:

- `npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/HomeSurfacePage.test.tsx' --no-file-parallelism` -> pass, `75` tests
- `git diff --check` -> pass
- `./scripts/release_secret_scan.sh` -> pass
- `npm --prefix apps/dsa-web run lint` -> pass
- `npm --prefix apps/dsa-web run build` -> pass with existing Vite chunk-size warning
- `npx react-doctor@latest --json --json-compact --yes --no-score` -> remaining diagnostics expected, totals above
- `npx react-doctor@latest --score --yes` -> `61`

Next candidates:

- Remaining Home memo findings are tied to route fixture hydration, recent history and dashboard selection, dashboard payload selection, active evidence ticker effect dependencies, or task lifecycle input identity.
- Watchlist display memo removal is blocked by focused test timing regression, even though React Doctor would reduce diagnostics.
- Continue only with display derivations that do not feed effects, task lifecycle inputs, route hydration, protected scoring/filtering, or tested loading timing.

## Stop Manifest

Latest pushed checkpoint before Batch 14: `a66d3cb3`. The Batch 14 checkpoint is the commit containing this section once pushed.

Final React Doctor state:

- Score: `61`
- Total diagnostics: `466`
- Errors: `110`
- Warnings: `356`
- Affected files: `40`
- Reduced total diagnostics from baseline: `101`

Remaining blocker groups:

- State/effect/action-flow findings: `180` diagnostics across `set-state-in-effect`, `no-event-handler`, chained/cascading state, derived state, prop-state sync, reducer suggestions, and related render flow rules. These require behavior rewrites or route-specific state-flow tests before safe changes.
- Manual memoization findings: `196` diagnostics across `react-compiler-no-manual-memoization` and `preserve-manual-memoization`. The remaining callbacks/memos are largely tied to `useEffect` dependencies, draft-state source objects, child identity contracts, or non-compiler runtime behavior; deleting them mechanically is unsafe.
- Component decomposition findings: `34` diagnostics across giant components, many boolean props, render-in-render, dialog/focus-trap, and pure-function hoist rules. These require broader component/API reshaping and visible/accessibility behavior review.
- Forbidden or protected scope:
  - `package.json` unused dependency is blocked by package/lockfile scope.
  - `src/api/error.ts`, `src/contexts/AuthContext.tsx`, `src/components/auth/AuthGuardOverlay.tsx`, and `src/hooks/useSystemConfig.ts` touch API/auth/config/runtime boundaries.
  - `src/types/portfolio.contract.ts` and portfolio diagnostics are blocked by portfolio contract/accounting/risk boundaries.
  - Remaining scanner threshold/ranking/sort findings are blocked by scanner score/ranking/filtering/cap semantics.
  - Remaining options async/sort findings are blocked by options payoff/scoring/strategy/optimizer/no-advice semantics.
  - Remaining backtest default export/state-flow findings require larger backtest component reshaping and are blocked by backtest protected semantics without stronger coverage.
- Tool suggestions that are unsafe or incompatible as-is:
  - `Array.prototype.toSorted()` suggestions require ES2023 library support while `tsconfig.app.json` targets `ES2022`.
  - `ReportPriceChart` passive listener suggestions are unsafe because the wheel/touch handlers intentionally call `preventDefault()`.
  - `HomeBentoDashboardPage.tsx` `js-set-map-lookups` flags string substring matching, not a Set-compatible array lookup.
  - The remaining scanner `<address>` suggestion and scroll-container `tabIndex` suggestions need explicit semantic design and tests before changes.

## Protected Domain Confirmation

No changes in Batches 1 through 11 to:

- backend/API/provider/cache/runtime/auth/package/lockfile/config/CI
- provider order, fallback, deadlines, cache semantics, payload shapes
- scanner score/ranking/filtering/cap semantics
- portfolio accounting/ledger/risk math
- options payoff/scoring/strategy/optimizer/no-advice semantics
- backtest math/fills/costs/metrics/stored semantics
- route/auth behavior or protected access policy
- visible product copy/layout beyond equivalent componentization of existing metric value rendering
- `.agents/skills` or ignored files
