# Consumer App 2 Goal Progress

Status: active frontend-first rebuild tracker.

## Goal

Rebuild WolfyStock consumer routes into a coherent private-beta app while preserving existing APIs and backend contracts.

Protected boundaries for this goal:

- No backend runtime semantics, provider order/cache/fallback, quota enforcement, auth/RBAC/session behavior, DB schema, broker/order/trade behavior, or external notification sending changes.
- No public-launch claim and no trading/execution path.
- Route work stays frontend-first under `apps/dsa-web/` plus this audit tracker.

## Route Hierarchy

Current route model is stable and will be preserved:

- Start: `/`, `/guest`
- Markets: `/market-overview`, `/market/liquidity-monitor`, `/market/rotation-radar`
- Research: `/scanner`, `/watchlist`
- Account: `/portfolio`
- Validate: `/backtest`, `/backtest/compare`, `/backtest/results/:runId`, `/options-lab`
- Auth entry: `/login`, `/register`, `/reset-password`
- Legacy aliases: `/market`, `/liquidity`, `/rotation`, `/options`, `/guest/scanner`, `/user/scanner`

## Initial IA Gaps

- Navigation was a flat list even though market routes already have `/market/*` hierarchy.
- Primary nav order jumped from Scanner to Portfolio before broader market context.
- Guest users saw protected modules as normal links without an upfront locked/member-only signal.
- Scanner was classified as public-safe for auth bootstrap but still gated for guest feature access.
- Some shell links preserved neither locale nor route hierarchy consistently.
- Page first screens had strong local content, but route purpose, evidence boundary, and next-step copy were not shared across pages.

## Checkpoints

### checkpoint(consumer): map app ia gaps

Status: implemented locally.

Implemented output:

- This audit tracker.
- Frontend-only route metadata describing Start, Markets, Research, Account, Validate in `apps/dsa-web/src/components/layout/consumerAppNavigation.ts`.
- Main shell/nav update that keeps routes stable while exposing grouped IA in `apps/dsa-web/src/components/layout/SidebarNav.tsx`.
- Shared consumer route story band for page purpose, next step, evidence boundary, and no-advice wording in `apps/dsa-web/src/components/layout/ConsumerRouteStory.tsx`.
- Locale-preserving brand and settings utility links.
- Guest-visible locked affordances for signed-in consumer modules without hiding links or changing route guards.

Validation target:

- Focused Shell tests.
- `git diff --check`.
- `./scripts/release_secret_scan.sh --local-only`.

Evidence so far:

- `npm --prefix apps/dsa-web run test -- src/components/layout/__tests__/Shell.test.tsx` passed: 35 tests before the new assertions.
- `npm --prefix apps/dsa-web run test -- src/components/layout/__tests__/Shell.test.tsx` passed after new IA assertions: 39 tests.
- `npm --prefix apps/dsa-web run typecheck` passed.
- `npm --prefix apps/dsa-web run lint:changed` passed.
- `npm --prefix apps/dsa-web run check:design:changed` passed.
- `npm --prefix apps/dsa-web run build:quiet` passed with the existing Vite chunk-size warning.
- `git diff --check` passed after adding intent-to-add for new files.
- `./scripts/release_secret_scan.sh --local-only` passed.

Next verification before the first checkpoint:

- Stage only the IA/shell/audit files.
- Commit `checkpoint(consumer): map app ia gaps`.
- Run full `./scripts/release_secret_scan.sh` after the checkpoint commit and before push.

### read-only review blockers fixed

Status: implemented as a bounded checkpoint fix. This does not complete the full Consumer App 2 rebuild.

Fixed:

- `/guest`, `/zh/guest`, and `/en/guest` now receive the same Home/Start consumer shell classification, story band, wide shell, home modifiers, and page-scroll treatment as `/`.
- Consumer route story copy was reworded away from rendered action/advice vocabulary in route purpose, next-step, evidence boundary, boundary, and link labels. Replacement language uses research observation, scenario review, manual records, no external action, no holding changes, and read-only validation.
- `Shell.test.tsx` now covers dedicated guest routes for the Home shell/story behavior while preserving existing Product Experience shell classes and grouped navigation coverage.

Deferred / unchanged:

- No auth routing, route guards, backend, API, provider/cache/fallback, DB, quota, broker/order/trade, notifications, or page-level product logic changes.
- `AppRoutes.test.tsx` was not changed because existing coverage already proves `/guest`, `/zh/guest`, and `/en/guest` route behavior remains guest-safe.
- The broader Consumer App 2 route-by-route rebuild remains active and incomplete.

Validation evidence:

- Red test before implementation: `npm --prefix apps/dsa-web run test -- src/components/layout/__tests__/Shell.test.tsx` failed on the three new dedicated guest shell/story cases because `consumer-route-story` was absent.
- Green test after implementation: `npm --prefix apps/dsa-web run test -- src/components/layout/__tests__/Shell.test.tsx` passed with 42 tests.
- Focused route/shell regression: `npm --prefix apps/dsa-web run test -- src/components/layout/__tests__/Shell.test.tsx src/__tests__/AppRoutes.test.tsx` passed with 159 tests.
- TypeScript/build gates: `npm --prefix apps/dsa-web run typecheck` passed; `npm --prefix apps/dsa-web run build:quiet` passed with the existing Vite chunk-size warning.
- Changed-file quality gates: `npm --prefix apps/dsa-web run lint:changed` passed; `npm --prefix apps/dsa-web run check:design:changed` passed with 2 files scanned and no blocking violations or warnings.
- Bounded browser smoke: `DSA_WEB_PLAYWRIGHT_PORT=4231 npm --prefix apps/dsa-web run test:e2e -- guest-entry-branding.smoke.spec.ts consumer-copy-forbidden-vocabulary.smoke.spec.ts --project=chromium --workers=1` passed with 4 tests.
- Source copy scan: `rg -n "\b(buy|sell|broker|orders?|trading|execution|advice|guidance)\b|买入|卖出|交易|执行|券商|订单|委托|建议" apps/dsa-web/src/components/layout/consumerAppNavigation.ts` returned no matches.
- Git whitespace, secret scan, final status, commit, and push evidence are reported in the task closeout.

### post-main-sync integration validation

Status: evidence recorded after syncing `codex/goal-consumer-app-2` with current `origin/main`.

Integration evidence:

- The branch was synced with current `origin/main` in merge commit `b0a07e79` (`merge: sync consumer app 2 with current main`).
- Final diff no longer reverts Product Experience/private-beta/research workflow docs or Admin Provider advisory-only safety copy.
- Full `./scripts/release_secret_scan.sh` was executed after the sync and passed.
- Shell/AppRoutes, typecheck, lint:changed, check:design:changed, build:quiet, and bounded Playwright guest-entry/copy smoke passed.

Protected boundary confirmation:

- Consumer App 2 remains frontend-first and does not change backend/API/provider/cache/fallback/quota/auth/DB/broker/notification behavior.

## Validation Asset Audit

Recommended bounded validation set for this goal:

- Shell/route IA: `npm --prefix apps/dsa-web run test -- src/components/layout/__tests__/Shell.test.tsx src/__tests__/AppRoutes.test.tsx`
- Route slices as touched: focused page tests under `apps/dsa-web/src/pages/__tests__/`.
- Build gates: `npm --prefix apps/dsa-web run lint:changed`, `npm --prefix apps/dsa-web run check:design:changed`, `npm --prefix apps/dsa-web run typecheck`, `npm --prefix apps/dsa-web run build:quiet`.
- Bounded Playwright: app-local `npm --prefix apps/dsa-web run test:e2e -- <route specs> --workers=1` with a task-owned `DSA_WEB_PLAYWRIGHT_PORT`.

Known smoke gaps to consider while routing slices continue:

- `/backtest` launch has broad smoke coverage but no dedicated launch spec.
- `/login` and `/register` have unit and shared smoke coverage but no dedicated auth-entry smoke file.
- `/market/liquidity-monitor` has degraded/copy-safety coverage but no dedicated healthy canonical route smoke.
- Portfolio broker sync smoke is opt-in and should stay out of default bounded validation unless explicitly in scope.

## Route-by-Route Worklist

- Home: keep existing research command center, add shared route purpose and market/scanner next-step entry.
- Market Overview: preserve API polling and local snapshot behavior, make it the Markets landing route.
- Liquidity: preserve degraded-state copy and use it as a market subroute.
- Rotation: preserve observation-only theme language and connect it to Scanner as the next research step.
- Scanner: preserve guest gating and run semantics; clarify it is a signed-in research workflow.
- Watchlist: preserve alert/list behavior; position as candidate follow-up, not trading list.
- Portfolio: preserve manual ledger/snapshot behavior; confirm no live order path is added.
- Backtest: preserve deterministic and legacy lanes; position as validation before action.
- Options: preserve read-only scenario language and no execution affordance.
- Login/Register: preserve auth behavior; keep guest return path and private-beta account story.

## Validation Plan

- Unit/component: `npm --prefix apps/dsa-web run test -- src/components/layout/__tests__/Shell.test.tsx`
- Build gates: `npm --prefix apps/dsa-web run typecheck`, `npm --prefix apps/dsa-web run build:quiet`
- Design/lint: `npm --prefix apps/dsa-web run check:design:changed`, `npm --prefix apps/dsa-web run lint:changed`
- Bounded smoke: app-local Playwright on touched consumer routes at desktop and `390x844`
- Always: `git diff --check`, `./scripts/release_secret_scan.sh`
