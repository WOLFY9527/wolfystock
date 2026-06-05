# T-1037 UI spacing/card/grid taxonomy write-readiness audit

Task ID: T-1037-AUDIT
Task title: UI spacing card grid taxonomy write-readiness audit
Mode: READ-ONLY-AUDIT with docs-only report artifact
Workspace: `/Users/yehengli/worktrees/t1037-ui-spacing-card-grid-taxonomy-audit`
Branch: `codex/t1037-ui-spacing-card-grid-taxonomy-audit`
Base commit inspected: `8e53d819`

## Decision

Recommend exactly one bounded next write:

**Home / Guest ResearchConsole local spacing taxonomy pass**

This is smaller and safer than a global token sweep because Home and Guest are owned by one page file, already declare route surface roles, and have measurable first-viewport spacing/radius variation that is not primarily admin/operator density. Do not start with shared primitives, global radius tokens, Backtest CSS, Settings CSS, or a 15-20 file spacing migration.

## Evidence Method

- Static code ownership inspection across required surfaces.
- DOM measurement against `http://127.0.0.1:8000` after successful admin login through the app form.
- Browser measurement used 1440x1000 viewport and did not save screenshots or generated assets.
- All measured routes reported `horizontalOverflow=false`.
- No source files were changed by this audit.

## Current Ownership Summary

### Shared layout and primitives

- `apps/dsa-web/src/components/layout/ConsumerWorkspaceShell.tsx`
  - Owns near-full consumer shell max width after T-1036.
  - `ConsumerWorkspacePageShell` routes through `TerminalPageShell`.
- `apps/dsa-web/src/components/terminal/TerminalPrimitives.tsx`
  - `TerminalPageShell`: `max-w-[1600px]`, `px-4 xl:px-8`, `gap-5`; consumer scope overrides max width to `1880px`.
  - `TerminalGrid`: `grid-cols-1 xl:grid-cols-12 gap-6`.
  - `TerminalPanel`: renders `WolfyShellSurface` with `padding="md"` or `sm`.
- `apps/dsa-web/src/components/linear/LinearPrimitives.tsx`
  - `WolfyShellSurface`: radius `14px`, padding `none/xs/sm/md/lg`.
  - `FixedRegionGrid`: structural grid with `gap-0`; callers often add local gap.
  - `CompactFilterBar` / `ResearchConsoleShell`: local command/console rhythm.
- `apps/dsa-web/src/components/terminal/DenseWorkbenchPrimitives.tsx`
  - Owns row/table-first density for Scanner and Watchlist.
  - Uses dense shell/command/status strip spacing intentionally.
- `apps/dsa-web/src/index.css`
  - Still contains older theme radius variables, Backtest-specific CSS, Settings surfaces, and spacex overrides.
  - This makes a global radius or token migration unsafe as the immediate next write.

## Surface Verdict Matrix

| Surface | Main owner | Observed taxonomy | Verdict |
| --- | --- | --- | --- |
| Home / Guest | `HomeBentoDashboardPage.tsx` | Single file mixes `FixedRegionGrid`, local `home-research-*` classes, `rounded-[8px]`, `rounded-[12px]`, `rounded-[14px]`, `gap-2.5`, `gap-3`, and local command bar overrides. DOM median padding 9px, radius 8px. | True local layout-system issue; safest next write target. |
| Scanner | `UserScannerPage.tsx`, `DenseWorkbenchPrimitives.tsx` | Row-first dense board, compact filters, fixed scroll regions. DOM median padding 4px, radius 5px. | Intentional product density; do not normalize with card rhythm. |
| Portfolio | `PortfolioPage.tsx`, `TerminalPrimitives.tsx` | Terminal grid and panels with local ledger/form sections. DOM max gap 21px, panel radius 14px. | Mixed but tied to ledger/form workflow; not the first write. |
| Market Overview | `MarketOverviewWorkbench*` | Page delegates layout to workbench components; panel primitives and route-specific rails own spacing. | Component-owned monitor surface; avoid page-level sweep. |
| Liquidity Monitor | `LiquidityMonitorPage.tsx` | Terminal shell/grid with local visual evidence panels. DOM median padding 4px because dense indicators dominate. | Some local variation, but data-board density is intentional. |
| Rotation Radar | `MarketRotationRadarPage.tsx` | Terminal shell with local matrix/list/ranking components. DOM sample mostly shell/header due current payload state. | Defer; taxonomy depends on radar/list state. |
| Watchlist | `WatchlistPage.tsx`, `DenseWorkbenchPrimitives.tsx` | Dense rows, board shell, compact filters, context rail. DOM median padding 5px. | Intentional row/list density; not a card-grid fix. |
| Backtest | `BacktestPage.tsx`, backtest component CSS in `index.css` | `TerminalPageShell` overridden to `px-0`, visible `rounded-[24px]` and measured 32px card radius. | Real inconsistency, but high blast radius; defer from immediate write. |
| Options Lab | `OptionsLabPage.tsx`, `WolfyShellSurface`, local panel classes | Many local panels with `p-3/p-4`, `gap-6`, and mixed lab-specific boards. | Medium-risk product surface; defer until Home taxonomy proves pattern. |
| Settings | `SettingsPage.tsx`, `SettingsSectionCard`, `GlassCard` | Legacy settings workspace with `rounded-2xl`, `p-5 md:p-6`, theme radius variables. | Separate preference-console taxonomy; not safe as first write. |
| System Settings | `SystemSettingsPage.tsx`, `SystemControlPlane` | Terminal shell plus system-control content; measured radius range up to 24px. | Admin/control surface; defer. |
| Admin Logs | `AdminLogsPage.tsx`, admin strips, Terminal panels | Dense operator table with panels/rows and deliberate compactness. | Intentional admin density; only fix after admin taxonomy plan. |
| Admin Users | `AdminUsersPage.tsx` | Terminal panels, dense cards, user directory/detail split. | Intentional admin density; defer. |
| Admin Providers | `MarketProviderOperationsPage.tsx` | Terminal page shell/grid with local provider readiness cards. | Admin ops density; defer. |

## Pattern Findings

### 1. Card and panel padding

Current active patterns include:

- Linear/Terminal panel default: `p-3` for dense/sm, `p-4 md:p-5` for md.
- Dense workbench: `px-3 py-2`, `px-3 py-2.5`.
- Home local surfaces: `px-3 py-3`, `px-4 py-3.5`, `px-5 py-4`, `px-4 py-2.5`.
- Backtest legacy cards: `px-4 py-3`, `px-4 py-4`, and CSS-backed 24-32px radius cards.
- Settings legacy cards: `p-5 md:p-6`, `GlassCard p-4`, theme radius variables.

True issue: Home and Backtest have perceptible product-surface rhythm drift. Scanner, Watchlist, Admin Logs, and Admin Providers use compact rows/tables intentionally.

### 2. Section spacing

Current active patterns include:

- Shared page shell: `py-5 md:py-6`, `gap-5`.
- Consumer page shell: `py-5 md:py-6`, plus consumer max width override.
- Home member stage: `gap-2.5`, `px-3 py-3`, local `mt-2.5`, `mt-3`.
- Options Lab: `mt-5 grid gap-6`, then nested `gap-6`.
- Dense boards: header `gap-3`, command/status strips with small internal spacing.

True issue: section rhythm is not globally tokenized. Safe first correction should be local to a route that already owns its first-viewport composition.

### 3. Grid gap

Current active patterns include:

- `TerminalGrid`: `gap-6`.
- Home `FixedRegionGrid`: local `gap-3`; CSS spacex override later sets `.home-research-fixed-grid { gap: 0; }`.
- Dense workbench: `gap-2/gap-3` for controls and rows.
- Portfolio/Liquidity/Rotation: `gap-4` local board lanes around Terminal panels.
- Options/Backtest: `gap-6` or CSS card grids.

True issue: there is no single grid taxonomy for RouteConsole vs row-board vs admin-ops. The immediate write should not try to make all grids share one gap.

### 4. Radius usage

Current active patterns include:

- `WolfyShellSurface`: `rounded-[14px]`.
- `TerminalNestedBlock` and many rows: `rounded-md` or `rounded-lg`.
- Home: 7-14px hardcoded local radii plus CSS overrides to 8px.
- Backtest: visible `rounded-[24px]`; DOM measured 32px on `normal-backtest-consolidated-card`.
- Settings: `rounded-2xl`, `rounded-[var(--theme-panel-radius-lg)]`.
- Pills/chips: `rounded-full` intentional.

True issue: route surfaces use several radius systems. Global radius migration is not safe before route taxonomy chooses which surfaces should remain dense, which should be console panels, and which are legacy settings/backtest surfaces.

### 5. Consumer vs admin density

Consumer surfaces are not uniform:

- Home is product-first ResearchConsole and should feel more composed.
- Scanner/Watchlist are dense row boards by design.
- Portfolio is ledger/forms plus risk panels and should remain denser than Home.
- Options/Backtest need no-advice/risk framing and analytical boards, not card-grid smoothing.

Admin surfaces are intentionally denser:

- Admin Logs, Admin Users, and Admin Providers prioritize operator state, tables, diagnostics, and drill-through controls.
- Their compact rows, dense chips, and table shells should not be normalized to Home card spacing.

## DOM Measurement Highlights

Measured after successful login, 1440x1000 viewport:

| Route | Final path | Horizontal overflow | Measured padding range | Measured radius range | Measured gap range |
| --- | --- | --- | --- | --- | --- |
| Home | `/` | no | 4-14px | 5-10px | 2-7px |
| Guest | `/` after logged-in redirect | no | 4-14px | 5-10px | 2-7px |
| Scanner | `/scanner` | no | 2-21px | 5-14px | 2-11px |
| Portfolio | `/portfolio` | no | 4-21px | 5-14px | 2-21px |
| Market Overview | `/market-overview` | no | 4-21px | 5-14px | 2-21px |
| Liquidity Monitor | `/market/liquidity-monitor` | no | 4-21px | 5-14px | 2-21px |
| Rotation Radar | `/market/rotation-radar` | no | 4-21px | 7-14px | 2-18px |
| Watchlist | `/watchlist` | no | 4-21px | 5-14px | 2-18px |
| Backtest | `/backtest` | no | 4-28px | 7-32px | 2-18px |
| Options Lab | `/options-lab` | no | 4-21px | 5-14px | 2-21px |
| Settings | `/settings` | no | 4-21px | 5-14px | 2-18px |
| System Settings | `/settings/system` | no | 4-21px | 5-24px | 2-18px |
| Admin Logs | `/admin/logs` | no | 4-21px | 5-14px | 2-18px |
| Admin Users | `/admin/users` | no | 4-18px | 5-14px | 2-21px |
| Admin Providers | `/admin/market-providers` | no | 4-21px | 5-14px | 2-18px |

Note: Guest route redirects to Home after login, so unauthenticated Guest was inspected statically and the authenticated DOM measurement uses the shared Home rendering path.

## Recommended Immediate Write

### Task title

T-1037-FE1 Home / Guest ResearchConsole local spacing taxonomy pass

### Allowed files

- `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx`
- `apps/dsa-web/src/pages/__tests__/GuestHomePage.test.tsx`

Tests may be skipped if the implementation only changes class strings and browser evidence is stronger, but no other source, CSS, primitive, or config files should be touched.

### Forbidden semantics

- Do not change API calls, auth behavior, guest/member routing, stock evidence fetching, history selection, chart data, report data, drawer behavior, paywall behavior, scanner/watchlist/backtest/portfolio/options/admin behavior, or any backend/runtime/provider/cache semantics.
- Do not edit `TerminalPrimitives`, `LinearPrimitives`, `ConsumerWorkspaceShell`, `index.css`, Tailwind config, route definitions, package files, or lockfiles.
- Do not delete research evidence, technical sections, fundamentals sections, data quality disclosures, source/citation frames, history entries, or guest trust copy to reduce density.
- Do not introduce new shared primitives.
- Do not use investment advice, buy/sell/order/trade/broker CTAs, or raw provider/schema/debug copy.

### Visual contract

- Scope is Home/Guest top-level ResearchConsole rhythm only:
  - command bar,
  - guest command surface,
  - member header strip,
  - primary workspace wrapper,
  - context rail container,
  - secondary deck wrapper.
- Preserve current near-full shell width and T-1036 max-width behavior.
- Keep the first viewport product-first: command bar plus dominant research console must remain visible.
- Use a local taxonomy in the page file, such as local class constants for Home route surface, inset, rail, deck, and compact action groups.
- Normalize only equivalent Home-local shells:
  - top-level console surfaces should use one local radius tier,
  - inset blocks should use one smaller local radius tier,
  - Home-local section gaps should use one route rhythm.
- Do not normalize DenseWorkbench, Admin, Backtest, Options, Portfolio, Liquidity, Rotation, Market Overview, or Settings in this write.
- Desktop and mobile must have no horizontal overflow.

### Validation commands

Run at minimum:

```bash
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx src/pages/__tests__/GuestHomePage.test.tsx --run
npm --prefix apps/dsa-web run build
git diff --check
./scripts/release_secret_scan.sh
```

If tests are not updated because the change is class-only, still run lint/build/diff/secret scan and document that focused tests were unchanged.

### Browser / screenshot measurement requirements

- Use fresh current-task evidence only.
- Use local server or task-owned preview server.
- Required routes:
  - `/`
  - `/guest` while logged out, or a fresh unauthenticated context
  - `/` logged in
- Required viewports:
  - 1440x1000
  - 1920x1080
  - 390x844
- Capture screenshots to `/tmp/T-1037-FE1-fresh-after/` only if needed; do not commit screenshots.
- DOM checks:
  - no horizontal overflow,
  - command bar visible,
  - Home ResearchConsole visible in first viewport,
  - context rail remains bounded on desktop,
  - secondary deck remains below primary workspace,
  - no raw provider/schema/debug text appears in default Home view,
  - no research evidence sections disappear.

### Risk level

Low to medium.

The write is bounded to one page and can be visually verified, but Home is the primary route and has guest/member branches, async states, evidence panels, chart region, drawers, and Safari readiness guards. Keep it class-only and local.

## Explicit Deferrals

- Defer full spacing token migration.
- Defer global radius migration.
- Defer shared primitive rewrites.
- Defer Backtest CSS/card normalization.
- Defer Settings legacy surface migration.
- Defer Admin Logs/Admin Users/Admin Providers density normalization.
- Defer Scanner/Watchlist dense-board normalization.
- Defer deleting or hiding research evidence as a density fix.

## Final Diff Boundary

This audit creates only:

- `docs/codex/audits/T-1037-ui-spacing-card-grid-taxonomy-write-readiness-audit.md`

No source, tests, config, package, lockfile, route, auth, backend, API, provider, cache, runtime, scanner, portfolio, options, backtest, market, admin behavior, screenshots, or generated assets are changed.
