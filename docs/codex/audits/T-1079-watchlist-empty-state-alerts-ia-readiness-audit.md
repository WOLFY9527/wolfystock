# T-1079 Watchlist empty-state and alerts IA readiness audit

Task ID: T-1079-AUDIT

Task title: Watchlist empty-state and alerts IA readiness audit

Mode: READ-ONLY-AUDIT with one explicitly allowed docs artifact.

Allowed artifact:

`docs/codex/audits/T-1079-watchlist-empty-state-alerts-ia-readiness-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1079-watchlist-empty-alerts-ia-readiness-audit`
- branch: `codex/t1079-watchlist-empty-alerts-ia-readiness-audit`
- branch HEAD inspected: `117fe4c5`
- `origin/main` after latest `git fetch origin`: `87254125`
- branch state after fetch: behind `origin/main` by 2 commits

Scope boundary:

- This audit inspected Watchlist empty state, detail rail, user-alert rail, API/test ownership, and browser rendering only.
- The branch was not rebased or switched; latest-main checks that matter for the duplicate CTA were done with `git show origin/main`.
- No Watchlist source, tests, config, package, lockfile, API, provider/cache/runtime, persistence/state semantics, scanner route behavior, alert delivery/backend, portfolio/options/backtest/auth, or Windows React Doctor work was changed.

## Verdict

The duplicate `打开扫描器` action is real on latest `origin/main`, but it is low harm and not a blocker.

It appears only in the empty Watchlist state because the page header always exposes a Scanner action and the empty-state row exposes the same Scanner action again. Both actions route to the same Scanner path and do not mutate Watchlist persistence, scanner ranking, alert delivery, auth, API state, or backend runtime.

The smallest safe future write is copy-only: de-duplicate the empty-state CTA label while preserving the Scanner navigation target. Do not redesign Watchlist IA, do not move the detail rail, and do not touch user-alert persistence or backend delivery.

## Duplicate CTA finding

Latest-main static check:

- `origin/main:apps/dsa-web/src/pages/WatchlistPage.tsx` still defines one shared Chinese label, `openScanner: '打开扫描器'`, and one English label, `openScanner: 'Open Scanner'`.
- The header action renders `{copy.openScanner}` in `DensePageHeader`.
- The empty-state `CompactEmptyRow` action renders the same `{copy.openScanner}`.
- `origin/main` has no WatchlistPage diff relative to this branch for the empty-state CTA path.

Local branch code evidence:

- Header Scanner action: `apps/dsa-web/src/pages/WatchlistPage.tsx:1632-1645`
- Empty-state owner and duplicate action: `apps/dsa-web/src/pages/WatchlistPage.tsx:1993-2013`
- Empty-state test currently asserts the empty-state action routes to `/zh/scanner`: `apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx:1601-1618`

Browser check against the selected branch confirmed the duplicate is user-visible:

| Scenario | Viewport | `打开扫描器` buttons | Empty state | Detail rail | Horizontal overflow | Console errors |
| --- | ---: | ---: | --- | --- | --- | --- |
| empty watchlist | 1440x1000 | 2 | visible | not rendered | no | 0 |
| empty watchlist | 390x844 | 2 | visible | not rendered | no | 0 |
| non-empty watchlist | 1440x1000 | 1 | not rendered | visible | no | 0 |
| non-empty watchlist | 390x844 | 1 | not rendered | visible | no | 0 |

Assessment:

- Acceptable redundancy: yes. It gives an empty-page recovery action near both the route title and the empty content block.
- Harm: minor IA noise. Two identical labels on the same empty screen make it look like two different actions may exist, even though both go to Scanner.
- Severity: P3 copy polish, not a functional defect.

## Empty-state ownership

`WatchlistPage.tsx` owns the empty state.

The empty state is page-local, not a shared empty-state contract:

- Copy lives in the local `copy` object: title, body, helper, and Scanner action label.
- Rendering lives in the `filteredItems.length > 0 ? rows : CompactEmptyRow` branch.
- Navigation is page-local through `navigate(scannerPath)`.
- The selected-item detail rail is intentionally absent when there are no rows, so user-alert rail state is not involved in the empty state.

This means a future copy-only change can be contained to `WatchlistPage.tsx` and its focused test without touching shared primitives or persistence.

## Alerts and user-alert rail ownership

Watchlist detail rail behavior is split cleanly:

- `WatchlistPage.tsx` owns whether the detail rail is mounted and which active symbol is passed into it. It mounts the rail only when `filteredItems.length > 0 && activeItem`.
- `WatchlistPage.tsx` owns the surrounding context rail sections: selected item summary, current state, risk note, next step, observation summary, data notes, investor signal, catalyst exposure, leveraged ETF mapper, and the user-alert panel.
- `UserAlertsRailPanel` owns current-symbol alert UI: collapsed disclosure, current-symbol filtering, in-app-only/no-order/no-advice copy, create/edit form state, threshold validation, and calls to `userAlertsApi`.
- Backend user-alert persistence and events are owned by `api/v1/endpoints/user_alerts.py`, `api/v1/schemas/user_alerts.py`, and `src/services/user_alert_service.py`; those are not needed for an empty-state copy polish.

Latest `origin/main` changed `UserAlertsRailPanel.tsx` with a local reducer/refactor, but the ownership remains the same:

- `UserAlertsRailPanel` still exports the rail component.
- It still filters rules by `watchlist_price_threshold` and current `symbol`.
- It still renders `data-testid="user-alerts-rail-panel"`.
- It still uses owner-scoped, in-app-only, observation-only, no-order, no-advice copy.

Existing coverage already exercises this boundary:

- Watchlist page mounts user alerts inside the detail rail without route/nav changes: `apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx:946-970`
- User-alert rail filters current-symbol rules and serializes create/update payloads: `apps/dsa-web/src/components/user-alerts/__tests__/UserAlertsRailPanel.test.tsx:68-148`
- Browser smoke keeps Watchlist user alerts bounded and observation-only in the route shell: `apps/dsa-web/e2e/watchlist-user-alerts.smoke.spec.ts:254-460`
- API tests keep user-alert routes owner-scoped/in-app and away from admin notification endpoints: `apps/dsa-web/src/api/__tests__/userAlerts.test.ts:24-214`

## Browser method

Local browser check was available and run against the selected branch.

Method:

- Started task-owned Vite dev server on `http://127.0.0.1:5187`.
- Used Playwright with mocked authenticated auth status, Watchlist payloads, user-alert rules/events, and refresh status.
- Checked `/zh/watchlist` at `1440x1000` and `390x844`.
- Checked both empty and non-empty Watchlist payloads.
- Saved no screenshots and no generated artifacts.

Limit:

- Because the selected branch is behind `origin/main` by two commits and the task forbids branch switching/rebasing, browser verification ran on the selected branch. Static `git show origin/main` checks confirmed the duplicate CTA path in `WatchlistPage.tsx` is unchanged on latest `origin/main`; `UserAlertsRailPanel.tsx` has a newer reducer refactor on `origin/main` but preserves rail ownership and copy semantics.

## Recommended future task

Open exactly one follow-up task only after the current Windows React Doctor lane is no longer editing Watchlist/user-alert display helpers:

**T-1079-COPY1: De-duplicate Watchlist empty-state Scanner CTA label**

Goal:

- Keep the page header Scanner action as `打开扫描器` / `Open Scanner`.
- Give the empty-state action a contextual label such as `从扫描器添加` / `Add from Scanner`.
- Preserve the same `navigate(scannerPath)` target.
- Preserve empty-state title/body/helper unless the label change requires a tiny grammar adjustment.
- Do not remove the empty-state action and do not redesign Watchlist IA.

Allowed future write files:

- `apps/dsa-web/src/pages/WatchlistPage.tsx`
- `apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx`

Forbidden future scope:

- No `UserAlertsRailPanel.tsx` changes.
- No `apps/dsa-web/src/api/userAlerts.ts` or `apps/dsa-web/src/types/userAlerts.ts` changes.
- No `api/v1/endpoints/user_alerts.py`, `api/v1/schemas/user_alerts.py`, or `src/services/user_alert_service.py` changes.
- No Watchlist persistence/state semantics changes.
- No scanner route behavior changes.
- No alert delivery/backend changes.
- No portfolio/options/backtest/auth changes.
- No shared primitive/global design rewrite.
- No broad Watchlist IA redesign.
- No duplicate or overlapping Windows React Doctor cleanup.

Recommended validation for that future write:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/WatchlistPage.test.tsx --run
git diff --check -- apps/dsa-web/src/pages/WatchlistPage.tsx apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx
./scripts/release_secret_scan.sh
```

Recommended browser smoke for that future write:

- `/zh/watchlist` at `1440x1000` and `390x844` with an empty Watchlist payload.
- Confirm one visible `打开扫描器` header action, one visible contextual empty-state Scanner action, same final Scanner route when clicked, no horizontal overflow, and no console/page errors.

## Stop conditions

Stop/no-op instead of writing if any of the following are true when the future task starts:

- Windows React Doctor has dirty or pending changes in `WatchlistPage.tsx` or Watchlist display helpers.
- The duplicate label has already been fixed upstream.
- The future task would require touching user-alert persistence, API payload shape, scanner route behavior, or shared primitives.
- Product direction prefers keeping exact duplicate recovery CTAs as intentional redundancy.
