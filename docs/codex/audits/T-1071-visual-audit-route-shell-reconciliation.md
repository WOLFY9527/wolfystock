# T-1071 Visual audit route shell reconciliation

Task ID: T-1071-AUDIT

Task title: Visual audit route shell reconciliation

Mode: READ-ONLY-AUDIT with one explicitly allowed docs artifact.

Allowed artifact: `docs/codex/audits/T-1071-visual-audit-route-shell-reconciliation.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1071-visual-audit-route-shell-reconciliation`
- branch: `codex/t1071-visual-audit-route-shell-reconciliation`
- source/UI base inspected: `cd6ebf3235e5736c2cc38a3dc3437d266b5e78c5`
- note: the task branch was fast-forwarded to current `origin/main` after `origin/main` received a Rotation Radar source fix during this audit. `/zh/market/rotation-radar` was then rechecked at `1440x1000`, `1920x1080`, and `390x844`; the final URL, shell width, 1880px page-shell contract, radius, and overflow verdict remained stable.

## Decision

The visual system findings are mixed:

- The **admin/system-control 1600px inner rail vs consumer 1880px near-full rail** is real in the current browser evidence.
- The **main padding mismatch** is also real as route taxonomy, but it is not currently causing overflow or viewport-specific redirects.
- The **Backtest 0px card radius finding is stale or measurement noise**. Current computed Backtest first-viewport panel radius is 14px at 1440px, 1920px, and 390px.
- The **Home missing 1880px cap finding is not a consumer-shell regression**. Home is intentionally a full-bleed page-scroll route, not a `ConsumerWorkspacePageShell` route.
- The reported **viewport-dependent redirects for Scanner, Rotation, Watchlist, Portfolio, Options, and Liquidity were not reproduced**. The only requested route that redirects is `/zh/admin/providers`, and that is an intentional alias to `/zh/admin/market-providers` at every tested viewport.

Recommended future writes are limited to two narrow tasks:

1. **T-1071-FE1 Admin/system-control rail policy pass**: if product direction wants admin visual parity with consumer routes, reconcile only the admin/system-control page-shell rail classes and tests. Do not rewrite the global shell, shared primitives, auth, routes, or create a new Admin Dashboard.
2. **T-1071-TEST1 Viewport route canonicalization smoke**: add a focused authenticated browser smoke proving the six product routes keep canonical final URLs at 390px/1440px/1920px and that `/zh/admin/providers` is the only expected alias in this set.

Do not start with a broad shell rewrite, global radius/token sweep, auth rewrite, or new Admin Dashboard.

## Method

- Used the running local app at `http://127.0.0.1:8000`.
- Confirmed `/api/health/live` returned `200`.
- Logged in through the local UI with the supplied admin account. This artifact records no password, cookie, session ID, or token.
- Browser-checked every requested route at `1440x1000`, `1920x1080`, and `390x844`.
- After fast-forwarding to include the latest Rotation Radar source fix, rechecked `/zh/market/rotation-radar` at all three viewports.
- Collected DOM/CSS metrics only: final URL, document title, visible route signatures, shell/main widths, page-shell max-width, main padding, horizontal overflow, and visible non-pill border radius.
- No screenshots, generated assets, source files, tests, config files, package files, lockfiles, route/auth/backend/provider/cache/runtime files, commits, or pushes were created during browser measurement.
- Browser console check after the route matrix reported no `error` or `warn` entries in the in-app browser session.

## Source Baseline

- Consumer near-full cap exists in `apps/dsa-web/src/components/layout/ConsumerWorkspaceShell.tsx:10-12`: `--wolfy-consumer-shell-max:1880px` plus `ConsumerWorkspacePageShell` `max-w-[var(--wolfy-consumer-shell-max,1880px)]`.
- Default `TerminalPageShell` remains `max-w-[1600px] mx-auto px-4 xl:px-8` in `apps/dsa-web/src/components/terminal/TerminalPrimitives.tsx:17-22`.
- `Shell.tsx` classifies product and system-control routes as wide at `apps/dsa-web/src/components/layout/Shell.tsx:195-221`.
- `Shell.tsx` applies three different main padding paths at `apps/dsa-web/src/components/layout/Shell.tsx:529-532`:
  - system-control routes: `p-0 shell-main-column--system-control`
  - Home: `px-4 pt-3 pb-8 md:px-6 lg:pt-4 xl:px-8 shell-main-column--home`
  - other wide product routes: `px-6 pt-6 pb-12 md:px-8 xl:px-12`
- Route aliases are explicit in `apps/dsa-web/src/App.tsx:385-394` and localized aliases in `apps/dsa-web/src/App.tsx:421-431`, including `/admin/providers` -> `/admin/market-providers`.
- Current Backtest shell and radius taxonomy are explicit in `apps/dsa-web/src/pages/BacktestPage.tsx:1354-1379` and `apps/dsa-web/src/pages/BacktestPage.tsx:1441-1444`.
- `NormalBacktestWorkspace` still declares a base `rounded-[32px]` on `normal-backtest-consolidated-card` in `apps/dsa-web/src/components/backtest/NormalBacktestWorkspace.tsx:83-85`, but the current `/zh/backtest` page applies a page-level selector that computes that card to 14px in the browser.

## Browser Route Matrix

All rows below used an authenticated admin session. `main` is `.shell-main-column` width. `page` is the first visible `data-terminal-primitive="page-shell"` width and computed `max-width`.

| Route | 1440 final | 1440 main/page | 1920 final | 1920 main/page | 390 final | Overflow | Radius max | Verdict |
| --- | --- | ---: | --- | ---: | --- | ---: | ---: | --- |
| `/zh` | `/zh` | `1440 / n/a` | `/zh` | `1920 / n/a` | `/zh` | `0` | `14` | Home is full-bleed and stable; not a missing consumer cap bug. |
| `/zh/scanner` | `/zh/scanner` | `1382.4 / 1298.4 @ 1880` | `/zh/scanner` | `1850 / 1766 @ 1880` | `/zh/scanner` | `0` | `14` | Canonical route; no viewport redirect. |
| `/zh/watchlist` | `/zh/watchlist` | `1382.4 / 1295.6 @ 1880` | `/zh/watchlist` | `1850 / 1763.2 @ 1880` | `/zh/watchlist` | `0` | `14` | Canonical route; no viewport redirect. |
| `/zh/portfolio` | `/zh/portfolio` | `1382.4 / 1295.6 @ 1880` | `/zh/portfolio` | `1850 / 1763.2 @ 1880` | `/zh/portfolio` | `0` | `14` | Canonical route; no viewport redirect. |
| `/zh/backtest` | `/zh/backtest` | `1382.4 / 1295.6 @ 1880` | `/zh/backtest` | `1850 / 1763.2 @ 1880` | `/zh/backtest` | `0` | `14` | Backtest shell cap and radius are current; 0px radius not reproduced. |
| `/zh/options-lab` | `/zh/options-lab` | `1382.4 / 1295.6 @ 1880` | `/zh/options-lab` | `1850 / 1763.2 @ 1880` | `/zh/options-lab` | `0` | `14 desktop / 10.5 mobile` | Canonical route; no viewport redirect. |
| `/zh/market-overview` | `/zh/market-overview` | `1382.4 / 1295.6 @ 1880` | `/zh/market-overview` | `1850 / 1763.2 @ 1880` | `/zh/market-overview` | `0` | `14` | Canonical route; no viewport redirect. |
| `/zh/market/liquidity-monitor` | `/zh/market/liquidity-monitor` | `1382.4 / 1295.6 @ 1880` | `/zh/market/liquidity-monitor` | `1850 / 1763.2 @ 1880` | `/zh/market/liquidity-monitor` | `0` | `14` | Canonical route; no viewport redirect. |
| `/zh/market/rotation-radar` | `/zh/market/rotation-radar` | `1382.4 / 1295.6 @ 1880` | `/zh/market/rotation-radar` | `1850 / 1763.2 @ 1880` | `/zh/market/rotation-radar` | `0` | `14` | Canonical route; no viewport redirect. |
| `/zh/settings/system` | `/zh/settings/system` | `1382.4 / 1382.4 @ 1600` | `/zh/settings/system` | `1850 / 1600 @ 1600` | `/zh/settings/system` | `0` | `16 desktop / 10.5 mobile` | Real admin/system-control 1600px rail. |
| `/zh/admin/logs` | `/zh/admin/logs` | `1382.4 / 1382.4 @ 1600` | `/zh/admin/logs` | `1850 / 1600 @ 1600` | `/zh/admin/logs` | `0` | `14` | Real admin 1600px rail; no auth gate. |
| `/zh/admin/users` | `/zh/admin/users` | `1382.4 / 1382.4 @ 1600` | `/zh/admin/users` | `1850 / 1600 @ 1600` | `/zh/admin/users` | `0` | `14` | Real admin 1600px rail; no auth gate. |
| `/zh/admin/providers` | `/zh/admin/market-providers` | `1382.4 / 1382.4 @ 1600` | `/zh/admin/market-providers` | `1850 / 1600 @ 1600` | `/zh/admin/market-providers` | `0` | `14` | Intentional admin alias, not a viewport regression. |

## Finding Reconciliation Matrix

| Reported finding | Current status | Classification | Evidence |
| --- | --- | --- | --- |
| Admin 1600px vs consumer 1880px visual schism | Real as an inner rail difference on system-control/admin pages. | True current visual-policy divergence. | Consumer routes compute page-shell `max-width: 1880px` and 1920 page-shell width around `1763px`; admin/system-control pages compute `max-width: 1600px` and clamp to `1600px` at 1920. Root `main` lane is still `1850px`, so this is an inner rail issue, not a full app-shell collapse. |
| Consumer/Admin/Home main padding mismatch | Real, but currently consistent with route taxonomy and not an overflow or redirect bug. | Intentional route taxonomy with possible visual polish risk. | Product routes measured `shellMainPadL=42px` desktop and `21px` mobile. System-control/admin routes measured `0px` main padding and rely on inner page-shell padding. Home measured full-bleed `main` width with no visible page-shell. |
| Backtest card border-radius still 0px after T-1044 | Not reproduced. | Stale report or browser measurement noise. | `/zh/backtest` computed `maxNonPillRadius=14px` at all three viewports. `backtest-subnav`, `backtest-research-boundary`, and `normal-backtest-consolidated-card` all appeared in the 14px max-radius set. Static source still has a base `rounded-[32px]`, but the page-level taxonomy selector computes the visible card to 14px. |
| Home missing 1880px max-width at ultrawide | Not a current consumer-shell bug. | Intentional Home route exception. | Home does not render a visible `TerminalPageShell`; it measured full-bleed `main=1920px` at 1920 with `overflowPx=0` and a stable local workspace. Treating Home as a missing `ConsumerWorkspacePageShell` route would conflate two different page taxonomies. |
| Scanner/Rotation/Watchlist/Portfolio/Options/Liquidity routes redirect unexpectedly by viewport | Not reproduced. | Stale/noise, likely auth/session or test setup when seen elsewhere. | The six requested product routes kept the same final URL at 1440px, 1920px, and 390px. The measured session was authenticated, so registered routes rendered real pages instead of guest protected frames. |

## Redirect And Auth Classification

| Route pattern | Current behavior | Classification |
| --- | --- | --- |
| `/zh/admin/providers` | Always redirects to `/zh/admin/market-providers` at 1440px, 1920px, and 390px. | Intentional route alias. |
| `/zh/admin`, `/zh/admin/system`, `/zh/admin/ai` | Code maps these aliases to `/zh/settings/system`. | Intentional route alias from `App.tsx`. Not part of the requested browser matrix except relevant for interpreting admin reports. |
| `/zh/liquidity`, `/zh/rotation`, `/zh/options` | Code maps these legacy aliases to canonical market/options routes. | Intentional route alias. The requested canonical routes did not redirect. |
| Registered product routes while unauthenticated | Would render protected/guest surfaces or login affordances instead of full workspaces. | Auth/session setup issue if used as visual evidence for route layout. |
| Admin routes while guest/non-admin | Guest redirects to guest preview; non-admin sees an access gate; admin account still needs capability summary. | Auth/session issue, not viewport regression. The authenticated admin session in this audit did not hit admin gates. |

## Verified Current Issues

1. **Admin/system-control inner rail remains 1600px while consumer route page shells use the 1880px near-full contract.**
   - This is visible at 1920px, where admin page shells clamp at `1600px` and consumer page shells measure about `1763px`.
   - This should be handled, if at all, as an admin/system-control page-shell policy decision. It does not justify a global shell rewrite.

2. **Main padding differs by route family.**
   - Home is full-bleed/page-scroll.
   - Consumer product routes use padded `shell-main-column`.
   - Admin/system-control routes use `p-0` and a centered inner `TerminalPageShell`.
   - The browser evidence showed no horizontal overflow or route instability from this difference.

## Stale Or Noise Findings

- Backtest 0px radius: stale or bad-selector measurement. Current visible Backtest panel radius is 14px.
- Backtest `rounded-[32px]` static grep: source-level false positive unless computed style ignores the page-level selector.
- Home missing 1880px max-width: taxonomy mismatch, not a regression.
- Viewport-dependent redirects on canonical product routes: not reproduced after authenticated browser setup.
- Admin provider route redirect: expected alias, not a regression.
- Auth-gated route observations from unauthenticated sessions should not be used as visual shell evidence for registered/admin workspaces.

## Recommended Future Tasks

### 1. T-1071-FE1 Admin/system-control rail policy pass

Scope:

- Decide whether system-control/admin route page shells should remain 1600px for operator density or align closer to the 1880px consumer near-full contract.
- If aligning, change only route-local/admin-local page shell classes and focused tests.
- Preserve admin capability gates, routes, data fetching, provider/cache semantics, logs behavior, and system settings behavior.

Do not:

- rewrite `Shell.tsx` globally;
- rewrite `TerminalPageShell` globally;
- change auth/RBAC;
- add a new Admin Dashboard;
- normalize all radius/tokens across the app.

### 2. T-1071-TEST1 Viewport route canonicalization smoke

Scope:

- Add a focused authenticated browser smoke for:
  - `/zh/scanner`
  - `/zh/watchlist`
  - `/zh/portfolio`
  - `/zh/options-lab`
  - `/zh/market/liquidity-monitor`
  - `/zh/market/rotation-radar`
  - `/zh/admin/providers`
- Verify at 390px, 1440px, and 1920px:
  - canonical product routes keep their final URL;
  - `/zh/admin/providers` consistently resolves to `/zh/admin/market-providers`;
  - no route is judged from an auth-gated guest frame.

Do not:

- change route behavior;
- broaden auth tests;
- mock away real route aliases without documenting them.

## Explicit Deferrals

- Defer broad shell rewrite.
- Defer global token/radius sweep.
- Defer broad auth rewrite.
- Defer new Admin Dashboard.
- Defer Backtest radius work unless a fresh browser pass reproduces a real computed-style regression.
- Defer Home max-width normalization unless product direction explicitly says Home should stop being full-bleed.

## Final Diff Boundary

This audit creates only:

- `docs/codex/audits/T-1071-visual-audit-route-shell-reconciliation.md`

No source, tests, config, package, lockfile, screenshots, generated assets, route/auth/frontend/backend/provider/cache/runtime changes were made by this audit.
