# WRD-008 React Doctor next high-yield domain audit

Task ID: WRD-008

Mode: READ-ONLY-AUDIT with one task-authorized docs-only artifact.

Allowed artifact: `docs/codex/audits/WRD-008-react-doctor-next-high-yield-domain-audit.md`

Scope boundary:

- No source, test, config, script, package, lockfile, workflow, or runtime
  behavior changes were made for this audit.
- React Doctor was used as advisory diagnostic input only.
- The final intended repo diff is docs-only and limited to this audit file.

## Current React Doctor input

Command used from `apps/dsa-web`:

```powershell
npx react-doctor@latest --json --json-compact --yes --no-score
```

Observed result:

- React Doctor exit code: `1`
- JSON status: `"ok": true`
- React Doctor version: `0.4.0`
- Current total diagnostics: `614`
- Severity: `112` errors, `502` warnings
- Category: `Accessibility 7`, `Bugs 131`, `Maintainability 312`,
  `Performance 164`

Interpretation: the non-zero exit is advisory because compact JSON was
parseable and reported `"ok": true`. WRD-008 should use the counts for triage,
not as a release gate.

## Audit decision

Recommended next write task: **Admin Logs + Admin Notifications display-only
React Doctor cleanup**.

Expected diagnostic reduction: **15-25 diagnostics**, with a hard minimum target
of `15`. The visible ceiling is higher because `AdminLogsPage.tsx` and
`AdminNotificationsPage.tsx` currently contain `33` combined
`react-compiler-no-manual-memoization` warnings, but the next write should only
remove memoization that is proven display-only and not referentially required.

Do not start a Watchlist, Options Lab, Home, Settings, or User Alerts write from
this audit.

Rationale:

- `WatchlistPage.tsx` has a high diagnostic count, but it is not a simple count
  win. Its diagnostics sit around selection, persistence, user actions, and
  async flows, so it is medium-risk and should not be selected ahead of a safer
  admin display slice.
- `OptionsLabPage.tsx` and `HomeBentoDashboardPage.tsx` remain high-risk/defer
  targets unless a later task proves an extremely narrow display-only subset.
- `AdminLogsPage.tsx` and `AdminNotificationsPage.tsx` are the best bounded
  admin display cleanup candidate if the write is limited to display derivation
  and the existing page tests stay green.
- `SettingsPage.tsx` should not be selected again from this output because the
  current `17` diagnostics are not at least `15` clearly safe remaining
  diagnostics. `UserAlertsRailPanel.tsx` has `0` diagnostics in the current
  output, so treating User Alerts as a remaining React Doctor target would be a
  stale/false-positive selection.

## Top domain matrix

| Domain | Count | Errors / warnings | Top files and rules | Risk | Classification |
| --- | ---: | ---: | --- | --- | --- |
| Options/Backtest | `158` | `14 / 144` | `DeterministicBacktestResultPage.tsx` `75`: manual memo `41`, set-state-in-effect `8`, todo `6`, chain updates `5`; `BacktestResultReport.tsx` `43`: manual memo `30`, render-in-render `7`; `OptionsLabPage.tsx` `17`: manual memo `9`, async defer `3` | Medium to high | Defer. Backtest report files may become a future bounded display task, but `OptionsLabPage.tsx` stays high-risk/defer. |
| Scanner | `114` | `15 / 99` | `UserScannerPage.tsx` `105`: manual memo `53`, todo `8`, set-state-in-effect `7`, no-event-handler `7`; `ScannerCandidatePresenters.tsx` `9`: boolean props `4`, unused export `3` | High | Defer. Primary scanner workflows and candidate interactions are too behavior-adjacent for this WRD-008 next write. |
| Market/Watchlist | `93` | `9 / 84` | `WatchlistPage.tsx` `45`: manual memo `15`, no-event-handler `10`, todo `5`, set-state-in-effect `4`; `MarketProviderOperationsPage.tsx` `34`: combine iterations `11`, manual memo `11`; `MarketOverviewPage.tsx` `14`: manual memo `9` | Medium | Watchlist is medium-risk/not selected because selection, persistence, user interactions, and async flows are interleaved. |
| Home | `90` | `24 / 66` | `HomeBentoDashboardPage.tsx` `80`: manual memo `22`, no-adjust-state-on-prop-change `12`, chain updates `12`, set-state-in-effect `7`; `HomeCandlestickChart.tsx` `9`: event handlers `4`, prop callback in effect `2` | High | High-risk defer unless a later task isolates a very small display-only subset. |
| Admin/Ops | `79` | `21 / 58` | `AdminLogsPage.tsx` `40`: manual memo `22`, todo `9`, set-state-in-effect `5`; `AdminNotificationsPage.tsx` `20`: manual memo `11`, todo `6`, set-state-in-effect `1`; other admin pages `19` | Low to medium if bounded | Safe next write only for Logs/Notifications display-only manual-memo cleanup. Defer other admin pages. |
| Settings/Auth/Shell | `32` | `12 / 20` | `SettingsPage.tsx` `17`: preserve manual memo `5`, derived state `2`, event handlers `2`, set-state-in-effect `2`; `AuthContext.tsx` `6`; `LLMChannelEditor.tsx` `5` | Medium | Defer. Settings/User Alerts must not be selected unless there are at least `15` safe remaining diagnostics; current output does not prove that. |
| Portfolio | `29` | `13 / 16` | `PortfolioPage.tsx` `21`: todo `8`, manual memo `7`, set-state-in-effect `4`; `PortfolioScenarioRiskPanel.tsx` `7` | Medium | Not selected in WRD-008. Count is below the `15` safe-reduction threshold once unsafe todo/state-flow work is excluded. |
| Shared/Other | `19` | `4 / 15` | `MarketRotationRadarPage.tsx` `5`; `ReportPriceChart.tsx` `4`; `useSystemConfig.ts` `3`; `useElementSize.ts` `2`; `package.json` `1` | Mixed | False-positive/defer for config/dependency or scattered one-off items; no high-yield safe write here. |

## Classification detail

### Safe next write

**Admin Logs + Admin Notifications display-only cleanup**

Current target counts:

- `apps/dsa-web/src/pages/AdminLogsPage.tsx`: `40` diagnostics
  - manual memo `22`
  - todo `9`
  - set-state-in-effect `5`
  - chain/derived-state/giant/reducer warnings `4`
- `apps/dsa-web/src/pages/AdminNotificationsPage.tsx`: `20` diagnostics
  - manual memo `11`
  - todo `6`
  - set-state-in-effect `1`
  - giant/reducer warnings `2`

Safe subset:

- Remove or simplify display-only `useMemo` / `useCallback` wrappers where the
  value is derived from already-rendered admin read models, labels, or table
  presentation and is not passed as a stability contract to effects, hooks, or
  child memo boundaries.
- Keep the write small enough that the page tests can prove filters, drawers,
  export/copy affordances, notification rendering, read-status labels, and error
  states still behave the same.
- Do not chase every `todo` or state-flow diagnostic in this write. `todo` and
  `set-state-in-effect` should be touched only if the affected code is clearly
  display-only and covered by the allowed tests.

Expected reduction:

- Minimum acceptable reduction: `15`
- Target reduction: `15-25`
- Do not expand scope just to reach the full visible `60` diagnostics across the
  two files.

### Medium-risk

**WatchlistPage**

Current count: `45`.

Why it is not selected:

- The highest groups include manual memo `15`, no-event-handler `10`, todo `5`,
  set-state-in-effect `4`, no-chain-state-updates `2`, and no-derived-state `2`.
- The flagged lines cluster around page state, selected items, actions, async
  refresh flows, and persistence-sensitive watchlist behavior.
- A later Watchlist task is only acceptable if it first proves a display-only
  subset with at least `15` safe diagnostics and keeps selection, persistence,
  user interactions, and network/async semantics untouched.

### High-risk defer

**HomeBentoDashboardPage**

Current count: `80`.

Reason for defer: the state/effect diagnostics are real, but they sit in route
hydration, pending analysis state, drawer behavior, history selection, and async
task completion. A broad cleanup would be a behavior refactor, not a safe
display pass.

**OptionsLabPage**

Current count: `17`.

Reason for defer: the count barely clears the `15` threshold, but the file is a
product workflow page. Its warnings include async-defer and handler-state
patterns, so it should remain high-risk/defer unless a future task identifies an
extremely narrow display-only subset.

**UserScannerPage**

Current count: `105`.

Reason for defer: high count, but primary scanner workflow controls, candidate
interactions, and async scanner state are involved. This is too behavior-heavy
for the next WRD-008 write.

### False-positive-defer

**User Alerts**

Current `src/components/user-alerts/UserAlertsRailPanel.tsx` count: `0`.

Decision: do not select. Any instruction that treats User Alerts as a remaining
React Doctor cleanup target is stale relative to the current JSON output.

**Settings/User Alerts combined**

Current state:

- `SettingsPage.tsx`: `17` diagnostics, but the safe subset is below `15` after
  excluding preserve-memo, state-flow, event-handler, and todo risk.
- `UserAlertsRailPanel.tsx`: `0` diagnostics.

Decision: do not select again unless a later JSON run shows at least `15` safe,
display-only remaining diagnostics.

**Scattered shared/config items**

Examples: `package.json` unused dependency `1`, `useElementSize.ts` todo `2`,
and small one-off shared warnings. These are not a high-yield safe React Doctor
domain and should not drive a source write from this audit.

## Selected next write task

Title: **WRD-009 Admin Logs/Notifications display-only React Doctor cleanup**

Goal:

- Reduce at least `15` React Doctor diagnostics from admin display pages without
  changing admin log query semantics, notification semantics, filters, drawers,
  status mapping, copy/export behavior, auth boundaries, API calls, polling, or
  route registration.

Allowed files:

- `apps/dsa-web/src/pages/AdminLogsPage.tsx`
- `apps/dsa-web/src/pages/AdminNotificationsPage.tsx`
- `apps/dsa-web/src/pages/__tests__/AdminLogsPage.test.tsx`
- `apps/dsa-web/src/pages/__tests__/AdminNotificationsPage.test.tsx`

Forbidden semantics:

- No API client changes.
- No route, auth, capability, role, navigation, or admin surface registration
  changes.
- No backend, schema, fixture, i18n, package, lockfile, config, workflow, or
  script changes.
- No filter default changes.
- No sort order, pagination, polling, export, copy-to-clipboard, drawer detail,
  read/unread, archive/delete, retry, or error-state behavior changes.
- No broad removal of `todo` comments unless the comment is demonstrably
  obsolete and the behavior is covered by the allowed tests.
- No shared component extraction or admin design-system migration.

Future validation commands for the selected write:

```powershell
npm --prefix apps/dsa-web run test -- src/pages/__tests__/AdminLogsPage.test.tsx src/pages/__tests__/AdminNotificationsPage.test.tsx
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run build
npx react-doctor@latest --json --json-compact --yes --no-score
git diff --check
G:\Git\bin\sh.exe ./scripts/release_secret_scan.sh
git status --short --branch
```

React Doctor success criterion for the future write:

- Current baseline: `614`
- Required post-write maximum: `599`
- Target post-write range: `589-599`
- If the safe admin display subset cannot reduce at least `15` diagnostics,
  pause React Doctor cleanup instead of expanding into behavior-heavy code.

## WRD-008 validation

Required validation for this docs-only audit:

```powershell
git diff --check
G:\Git\bin\sh.exe ./scripts/release_secret_scan.sh
git status --short --branch
```

Final diff confirmation:

- Confirmed after marking the new audit file intent-to-add: final diff is
  docs-only.
- Changed file:
  `docs/codex/audits/WRD-008-react-doctor-next-high-yield-domain-audit.md`
- No source files are allowed in the final diff.
