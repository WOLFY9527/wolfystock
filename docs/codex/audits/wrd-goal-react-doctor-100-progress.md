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

Status: validated locally, ready for immediate checkpoint commit and push.

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

## Protected Domain Confirmation

No changes in Batch 1 to:

- backend/API/provider/cache/runtime/auth/package/lockfile/config/CI
- provider order, fallback, deadlines, cache semantics, payload shapes
- scanner score/ranking/filtering/cap semantics
- portfolio accounting/ledger/risk math
- options payoff/scoring/strategy/optimizer/no-advice semantics
- backtest math/fills/costs/metrics/stored semantics
- route/auth behavior or protected access policy
- visible product copy/layout beyond equivalent componentization of existing metric value rendering
- `.agents/skills` or ignored files
