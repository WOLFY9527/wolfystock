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

Status: included in the checkpoint commit for this batch after local validation.

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

## Protected Domain Confirmation

No changes in Batches 1 through 5 to:

- backend/API/provider/cache/runtime/auth/package/lockfile/config/CI
- provider order, fallback, deadlines, cache semantics, payload shapes
- scanner score/ranking/filtering/cap semantics
- portfolio accounting/ledger/risk math
- options payoff/scoring/strategy/optimizer/no-advice semantics
- backtest math/fills/costs/metrics/stored semantics
- route/auth behavior or protected access policy
- visible product copy/layout beyond equivalent componentization of existing metric value rendering
- `.agents/skills` or ignored files
