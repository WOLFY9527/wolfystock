# T-1082 Mobile visual overlap reconciliation audit

Task ID: T-1082-AUDIT

Task title: Mobile visual overlap reconciliation audit

Mode: READ-ONLY-AUDIT with one explicitly allowed docs artifact.

Allowed artifact:

`docs/codex/audits/archive/2026-06/T-1082-mobile-visual-overlap-reconciliation-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1082-mobile-visual-overlap-reconciliation-audit`
- branch: `codex/t1082-mobile-visual-overlap-reconciliation-audit`
- branch HEAD inspected: `35c70fa9`
- branch state after `git fetch origin`: behind `origin/main` by 3 commits during closeout preflight

Scope boundary:

- This audit inspected current mobile rendering evidence only.
- No source, tests, config, package, lockfile, screenshots, generated assets, backend/API/provider/cache/runtime, frontend behavior, Watchlist source, or global layout/token/radius files were changed.
- Windows React Doctor may still touch Watchlist. Any Watchlist implementation must wait until that lane is no longer touching Watchlist/display helpers.

## Verdict

The Portfolio 390px overlap report is not reproduced as a real user-visible overlap. Portfolio is contained at 390x844 with no page-level horizontal overflow; the detector noise is consistent with nested panel/control geometry.

The only real mobile visual issue found is Watchlist empty-state stacking. At 390x844, the filter grid, empty-state board, duplicate `打开扫描器` action, advanced filter control, and batch action panel visually collide. This is a true control stack/spacing issue plus duplicate CTA confusion, not just nested-element detector noise.

Rotation Radar does not show real filter/control panel overlap in the 390px screenshot check. It is dense, and the matrix has contained internal horizontal scroll/clip behavior, but the visible filter/control stack remains usable and page-level containment holds.

Recommended next task: one Watchlist-only mobile empty-state stack reconciliation write, but defer execution until Windows React Doctor is no longer touching Watchlist or display helpers.

## Browser method

Fresh evidence source:

- current HEAD: `35c70fa9`
- fresh build: `npm --prefix apps/dsa-web run build`
- task-owned preview: `http://127.0.0.1:4184`
- viewport: `390x844`
- routes checked:
  - `/zh/portfolio`
  - `/zh/watchlist`
  - `/zh/scanner`
  - `/zh/market/liquidity-monitor`
  - `/zh/market/rotation-radar`
  - `/zh/options-lab`

Browser note:

- In-app Browser was attempted against both `http://127.0.0.1:4182/zh/portfolio` and `http://localhost:4182/zh/portfolio`.
- The Browser plugin returned `net::ERR_BLOCKED_BY_CLIENT` for both local URLs, so route rendering was measured with Playwright against the same fresh preview instead.
- Temporary `/tmp/t1082-watchlist-390.png` and `/tmp/t1082-rotation-390.png` screenshots were used only for visual confirmation, then deleted, and are not part of the repo diff.

Fixture boundary:

- Playwright route fulfillment fixed auth and route data to keep the pages in stable read-only states.
- The fixtures were only used to make current UI geometry measurable; this audit does not validate backend data semantics.
- A direct attempt to reuse `e2e/ux-density-audit.spec.ts` failed before tests ran because `e2e/fixtures/productAuth.ts` could not resolve `src/test-utils/productAuthHarness` from that entry. No test or source file was changed for that failure.

## Per-route verdict matrix

| Route | 390px verdict | Real visual overlap | Detector false positive / nested overlap | Horizontal overflow | Control stack / spacing |
| --- | --- | --- | --- | --- | --- |
| `/zh/portfolio` | Acceptable | No | Yes. Nested panel/control pairs were counted, but sibling overlap was `0`. | No, document/body width stayed `390`. | No immediate write. |
| `/zh/watchlist` | Real issue | Yes. Filter grid and empty-state board visibly overlap; duplicate Scanner CTA is visible. | Some nested noise also exists, but it does not explain the visible collision. | No page-level overflow. | Yes. Empty-state controls need page-local mobile stacking. |
| `/zh/scanner` | Contained dense operator layout | No | Yes. Text/span internal scrollWidth and nested controls are detector noise. | No page-level overflow. | Dense but intentional; no immediate write. |
| `/zh/market/liquidity-monitor` | Contained | No | Minimal nested panel noise only. | No page-level overflow. | No immediate write. |
| `/zh/market/rotation-radar` | Dense but acceptable | No user-visible filter/control overlap. | Yes. Automated pairs were triggered by section containers and the internally scrollable matrix/point geometry. | No page-level overflow; matrix scroll/clip is internal. | Dense, but not a blocker. |
| `/zh/options-lab` | Contained | No | Minimal nested hero/readiness overlap noise only. | No page-level overflow. | No immediate write. |

## True / false positive classification

True positive:

- Watchlist empty-state mobile stack:
  - visible duplicate `打开扫描器` count: `2`
  - page-level overflow: no
  - real issue type: vertical stack collision and duplicate CTA confusion
  - evidence: the filter controls visually sit over the empty-state board and action area at 390x844

False positives / acceptable overlap:

- Portfolio:
  - sibling overlap count: `0`
  - nested overlap count was detector noise from normal nested panels and controls
  - first viewport looked visually acceptable and contained
- Scanner:
  - sibling overlap count: `0`
  - contained internal text overflow in small spans, not page overflow
  - dense launch controls are intentional for the operator/research layout
- Liquidity:
  - sibling overlap count: `0`
  - long single-column guidance panel is contained
- Options Lab:
  - sibling overlap count: `0`
  - first viewport is the readiness/hero stack and stays contained
- Rotation Radar:
  - detected sibling overlap pairs did not correspond to visible filter/control collision
  - internal matrix geometry can produce overlap detector noise while page-level containment remains intact

## Specific checks

1. Portfolio real overlap:
   - Not reproduced.
   - `portfolio-account-status-strip` and `portfolio-command-strip` stayed inside the 390px page width.
   - No sibling overlap and no horizontal overflow were observed.

2. Watchlist empty-state controls:
   - Real overlap reproduced.
   - Empty-state Scanner action and header Scanner action both render as `打开扫描器`.
   - The duplicate CTAs are not functionally dangerous, but combined with the visual collision they create avoidable confusion.

3. Rotation Radar mobile filters/control panels:
   - No real filter/control panel overlap was visible.
   - The top market buttons, search, category note, and status/matrix affordances are tight but readable.
   - Internal matrix scroll/clip should remain classified as acceptable detector noise unless a future live-data screenshot shows text actually covering controls.

4. Options/Liquidity/Scanner containment:
   - All three routes held document/body width to `390`.
   - No route-level horizontal overflow.
   - No visible sibling overlap requiring a source write.

## Recommended future task

Open exactly one follow-up only after Windows React Doctor is no longer editing Watchlist or Watchlist display helpers:

**T-1082-FE1: Reconcile Watchlist empty-state mobile stack and Scanner CTA labeling**

Goal:

- Keep the page header Scanner action.
- Make the empty-state Scanner action visually and textually distinct, for example `从扫描器添加`, while preserving the same Scanner route target.
- Fix the 390px vertical stacking so the filter grid, empty state, advanced filter button, and batch action panel do not overlap.
- Keep the fix page-local and mobile-scoped.

Allowed future write files:

- `apps/dsa-web/src/pages/WatchlistPage.tsx`
- `apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx`
- optionally the existing Watchlist e2e smoke if a stable 390px assertion already owns this route

Forbidden future scope:

- No `UserAlertsRailPanel.tsx` changes.
- No user-alert API/type/backend changes.
- No scanner route behavior changes.
- No Watchlist persistence/state semantics changes.
- No portfolio/options/backtest/auth/provider/cache/runtime changes.
- No shared primitive, global CSS, token, radius, or broad Watchlist IA redesign.
- No overlapping Windows React Doctor cleanup.

Recommended future validation:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/WatchlistPage.test.tsx --run
git diff --check -- apps/dsa-web/src/pages/WatchlistPage.tsx apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx
./scripts/release_secret_scan.sh
```

Recommended future browser proof:

- `/zh/watchlist` at `390x844` with empty Watchlist payload.
- Assert no page-level horizontal overflow.
- Assert filter grid, empty state, advanced filter control, and batch action panel have non-overlapping vertical boxes.
- Assert one header `打开扫描器` action and one contextual empty-state Scanner action.

## Audit status

- Recommended next write: Watchlist-only, deferred until Windows React Doctor stops touching Watchlist/display helpers.
- Portfolio fix: not recommended.
- Rotation Radar fix: not recommended from current evidence.
- Scanner/Liquidity/Options fix: not recommended from current evidence.
