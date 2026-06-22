# T-1009 auth guard policy audit

Task: T-1009 UX audit auth guard policy audit

Mode: READ-ONLY-AUDIT with one explicitly allowed audit artifact.

Allowed artifact: `docs/codex/audits/T-1009-auth-guard-policy-audit.md`

Observed branch during audit: `codex/t1009-auth-guard-policy-audit`

Scope boundary:

- No source code changes.
- No test changes.
- No config, lockfile, CI, or changelog changes.
- This report defines current policy, risk classification, and future write gates only.

## Executive summary

The current frontend auth policy is a deliberate mixed model, not a broken or
unfinished attempt at universal redirect-to-login:

- guest-only and high-sensitivity entry points redirect to `/guest`
- registered-user product routes usually stay on the original URL and render a
  same-route auth/paywall overlay
- some routes are intentionally public, including the guest home preview funnel
  and the market intelligence read surfaces
- admin canonical routes do not redirect logged-in non-admin users away; they
  stay on-route and render an admin access gate

The evidence does not support the original blocker claim that protected routes
are broadly leaking meaningful consumer or admin content to guests. The guarded
consumer routes mount placeholders or dedicated guest overlays before real
product surfaces render. Admin routes either redirect guests to `/guest` or
show an access gate to logged-in non-admin users.

Current blocker status:

- True security/product leakage found in guarded route policy: none proven
- UX inconsistency found: yes
- Test coverage gaps before any auth rewrite: yes
- Product decisions required before any "make auth consistent" write: yes

The strongest conclusion is negative: do not start a blanket redirect-to-login
rewrite. That would conflict with the shipped guest preview/paywall model unless
product explicitly decides to retire that model first.

## Evidence base

Primary implementation files inspected:

- `apps/dsa-web/src/App.tsx`
- `apps/dsa-web/src/contexts/AuthContext.tsx`
- `apps/dsa-web/src/hooks/useProductSurface.ts`
- `apps/dsa-web/src/utils/adminCapabilities.ts`
- `apps/dsa-web/src/components/auth/AuthGuardOverlay.tsx`
- `apps/dsa-web/src/components/layout/ConsumerWorkspaceShell.tsx`
- `apps/dsa-web/src/pages/GuestHomePage.tsx`
- `apps/dsa-web/src/pages/HomeSurfacePage.tsx`
- `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`
- `apps/dsa-web/src/pages/ScannerSurfacePage.tsx`
- `apps/dsa-web/src/pages/WatchlistPage.tsx`
- `apps/dsa-web/src/pages/PersonalSettingsPage.tsx`

Primary test and smoke evidence inspected:

- `apps/dsa-web/src/__tests__/AppRoutes.test.tsx`
- `apps/dsa-web/src/components/auth/__tests__/AuthGuardOverlay.test.tsx`
- `apps/dsa-web/src/pages/__tests__/GuestHomePage.test.tsx`
- `apps/dsa-web/e2e/ux-audit-p0-verification.smoke.spec.ts`
- `apps/dsa-web/e2e/shell-route-admin-affordance.smoke.spec.ts`
- `apps/dsa-web/e2e/product-auth-harness.spec.ts`
- `apps/dsa-web/e2e/admin-auth-harness.spec.ts`
- `apps/dsa-web/e2e/admin-evidence-workflow.spec.ts`
- `apps/dsa-web/e2e/fixtures/productAuth.ts`
- `apps/dsa-web/e2e/fixtures/authenticatedRouteSmoke.ts`
- `apps/dsa-web/e2e/fixtures/adminAuth.ts`

Supporting product-policy evidence:

- `tests/test_public_analysis_preview_api.py`
- `docs/full-guide.md`
- `docs/market-scanner.md`
- git history: `e8059fe7` (`T-1001`) and `65403154` (`T-1002`)

## Current policy model

### Auth state resolution

Frontend route policy is driven by `authApi.getStatus()` through
`AuthProvider`. On status fetch failure, the app fails closed into
`loggedIn=false`, `currentUser=null`, and an error state rather than continuing
as authenticated content (`apps/dsa-web/src/contexts/AuthContext.tsx:114-141`,
`apps/dsa-web/src/App.tsx:333-349`).

The product role model is simple and fail-closed:

- `!loggedIn => guest`
- `loggedIn && currentUser.isAdmin => admin`
- otherwise `user`

This is implemented in
`apps/dsa-web/src/hooks/useProductSurface.ts:20-32,78-132`.

### Three active route strategies

1. Guest redirect strategy

- guest visiting `/settings`, `/settings/*`, and all admin canonical/admin alias
  paths is redirected to localized `/guest`
- implemented by `isGuestRestrictedPath` before route rendering
- evidence: `apps/dsa-web/src/App.tsx:263-290,374-376`

2. Same-route overlay strategy

- guest visiting most registered-user product routes stays on the original URL
- the app renders `ConsumerProtectedFrame` and `AuthGuardOverlay`
- implemented by `RegisteredSurfaceRoute` plus page-local short-circuiting for
  `ScannerSurfacePage` and `WatchlistPage`
- evidence:
  `apps/dsa-web/src/App.tsx:185-209,399-407,436-444`,
  `apps/dsa-web/src/pages/ScannerSurfacePage.tsx:8-29`,
  `apps/dsa-web/src/pages/WatchlistPage.tsx:1539-1541`

3. Public/preview strategy

- guest can access `/`, `/:locale`, `/guest`, preview routes, and currently
  `market/liquidity-monitor` plus `market/rotation-radar`
- guest home is not a fallback accident; it is a deliberate preview/paywall
  funnel backed by public preview API behavior
- evidence:
  `apps/dsa-web/src/App.tsx:395-402,432-439,499-520`,
  `apps/dsa-web/src/pages/GuestHomePage.tsx:9-31`,
  `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:4978-5203`,
  `tests/test_public_analysis_preview_api.py:70-151`,
  `docs/full-guide.md:1269-1283`

## Route policy matrix

| Route class | Routes | Current unauthenticated behavior | Classification | Evidence |
| --- | --- | --- | --- | --- |
| Public home | `/`, `/:locale` | Stay on-route and render Home surface in guest mode | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:395-396,432-433`; `apps/dsa-web/src/pages/HomeSurfacePage.tsx:5-7` |
| Guest route | `/guest`, `/:locale/guest` | Stay on-route as guest preview; signed-in users redirect home | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:262,396,433`; `apps/dsa-web/src/pages/GuestHomePage.tsx:21-31`; `apps/dsa-web/src/pages/__tests__/GuestHomePage.test.tsx:170-194` |
| Login/create-account | `/login`, `/:locale/login`, `/register`, `/:locale/register` | Login stays public when auth/setup allows; register redirects into login create mode | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:351-363,456-461` |
| Reset password | `/reset-password`, `/:locale/reset-password` | Public only for logged-out auth-enabled sessions; otherwise redirect home | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:364-373,462-463` |
| Preview routes | `/__preview/*`, `/:locale/__preview/*` | Public preview routes outside main auth shell | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:478-520` |
| Public market intelligence | `/market/liquidity-monitor`, `/:locale/market/liquidity-monitor`, `/market/rotation-radar`, `/:locale/market/rotation-radar` | Stay on-route and render content without auth gate | Acceptable current product behavior today; requires product decision only if the product now wants these to become paid/authenticated | `apps/dsa-web/src/App.tsx:401-402,438-439`; public alias smokes in `apps/dsa-web/e2e/ux-audit-p0-verification.smoke.spec.ts:761-782` |
| Registered-user settings | `/settings`, `/:locale/settings` | Guest redirect to localized `/guest`; logged-in user sees personal settings | UX confusing but safe because page code still contains guest copy that normal auth-enabled routing never exposes | `apps/dsa-web/src/App.tsx:264-265,374-376,408,445`; guest redirect tests in `apps/dsa-web/src/__tests__/AppRoutes.test.tsx:315-328`; guest copy in `apps/dsa-web/src/pages/PersonalSettingsPage.tsx:137-183,191-239` |
| Registered-user product routes with overlay | `/portfolio`, `/market-overview`, `/watchlist`, `/backtest`, `/options-lab`, `/backtest/compare`, `/backtest/results/:runId` and localized variants | Stay on-route, show same-route overlay/paywall, no redirect | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:185-209,399-407,436-444`; route tests in `apps/dsa-web/src/__tests__/AppRoutes.test.tsx:331-344,480-522`; smoke proof in `apps/dsa-web/e2e/ux-audit-p0-verification.smoke.spec.ts:785-797,865-881` |
| Registered-user scanner route | `/scanner`, `/:locale/scanner` | Stay on-route, page-level guest short-circuit returns overlay frame | Acceptable current product behavior | `apps/dsa-web/src/pages/ScannerSurfacePage.tsx:8-29`; scanner note in `docs/market-scanner.md:22-24` |
| Admin canonical routes | `/settings/system`, `/admin/logs`, `/admin/evidence-workflow`, `/admin/notifications`, `/admin/market-providers`, `/admin/provider-circuits`, `/admin/users`, `/admin/users/:userId`, `/admin/users/:userId/activity`, `/admin/cost-observability` and localized variants | Guest redirects to `/guest`; logged-in non-admin stays on-route and sees admin gate; admin account must still satisfy per-route capability | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:211-247,263-290,409-418,446-455`; `apps/dsa-web/src/utils/adminCapabilities.ts:53-79`; route tests in `apps/dsa-web/src/__tests__/AppRoutes.test.tsx:354-448,778-903` |

## Alias matrix

### T-1001 consumer aliases

| Alias | Canonical route | Guest behavior | Classification | Evidence |
| --- | --- | --- | --- | --- |
| `/liquidity`, `/:locale/liquidity` | `/market/liquidity-monitor` | Redirect to canonical public route, then public content | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:392,429`; `apps/dsa-web/src/__tests__/AppRoutes.test.tsx:496-509`; `apps/dsa-web/e2e/ux-audit-p0-verification.smoke.spec.ts:761-782` |
| `/rotation`, `/:locale/rotation` | `/market/rotation-radar` | Redirect to canonical public route, then public content | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:393,430`; `apps/dsa-web/src/__tests__/AppRoutes.test.tsx:511-524`; `apps/dsa-web/e2e/ux-audit-p0-verification.smoke.spec.ts:761-782` |
| `/options`, `/:locale/options` | `/options-lab` | Redirect to canonical protected route, then same-route guest overlay | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:394,431`; `apps/dsa-web/src/__tests__/AppRoutes.test.tsx:480-493`; `apps/dsa-web/e2e/ux-audit-p0-verification.smoke.spec.ts:840-881` |

### T-1002 admin aliases

| Alias | Canonical route | Guest behavior | Logged-in non-admin behavior | Classification | Evidence |
| --- | --- | --- | --- | --- | --- |
| `/admin/system`, `/:locale/admin/system` | `/settings/system` | Redirect to localized `/guest` | Alias to canonical route, then admin gate | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:266-267,387,424`; `apps/dsa-web/src/__tests__/AppRoutes.test.tsx:376-448` |
| `/admin/providers`, `/:locale/admin/providers` | `/admin/market-providers` | Redirect to localized `/guest` | Alias to canonical route, then admin gate | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:268-269,388,425`; `apps/dsa-web/src/__tests__/AppRoutes.test.tsx:378,383,388,405-448` |
| `/admin/evidence`, `/:locale/admin/evidence` | `/admin/evidence-workflow` | Redirect to localized `/guest` | Alias to canonical route, then admin gate | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:270-271,389,426`; `apps/dsa-web/src/__tests__/AppRoutes.test.tsx:379,384,389,405-448` |
| `/admin/costs`, `/:locale/admin/costs` | `/admin/cost-observability` | Redirect to localized `/guest` | Alias to canonical route, then admin gate | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:272-273,390,427`; `apps/dsa-web/src/__tests__/AppRoutes.test.tsx:380,385,390,405-448` |
| `/admin/ai`, `/:locale/admin/ai` | `/settings/system` | Redirect to localized `/guest` | Alias to canonical route, then admin gate | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:274-275,391,428`; `apps/dsa-web/src/__tests__/AppRoutes.test.tsx:381,386,391,405-448` |

### Other active aliases relevant to the audit

| Alias | Canonical route | Guest behavior | Classification | Evidence |
| --- | --- | --- | --- | --- |
| `/market`, `/:locale/market` | `/market-overview` | Redirect to canonical route, then same-route overlay for guest | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:385,422`; `apps/dsa-web/src/__tests__/AppRoutes.test.tsx:346-352` |
| `/chat`, `/:locale/chat` | `/market-overview` | Redirect to canonical route, then same-route overlay for guest | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:398,435`; `apps/dsa-web/src/__tests__/AppRoutes.test.tsx:450-456` |
| `/admin`, `/:locale/admin` | `/settings/system` | Guest redirect to `/guest`; logged-in non-admin sees admin gate | Acceptable current product behavior | `apps/dsa-web/src/App.tsx:386,423`; `apps/dsa-web/src/__tests__/AppRoutes.test.tsx:354-374`; `apps/dsa-web/e2e/shell-route-admin-affordance.smoke.spec.ts:334-377` |

## Risk classification

### Acceptable current product behavior

- Guest preview home and public preview API are intentional and tested.
- Same-route overlays on consumer paid routes are intentional and tested.
- Admin aliases redirect guests to `/guest` and keep logged-in non-admins on the
  canonical admin URL with an access gate.
- Public liquidity and rotation routes are currently intentional public read
  surfaces, not accidental auth holes.

### UX confusing but safe

1. Mixed protection styles across route classes

- `/portfolio` stays on-route with overlay
- `/settings` redirects guest to `/guest`
- `/admin/*` redirects guests but keeps logged-in non-admins on-route with an
  access gate

This is safe, but a reviewer expecting one universal pattern can easily misread
it as inconsistent or broken.

2. Same-route overlay preserves URL but not post-login redirect intent

`AuthGuardOverlay` sends users to localized `/login` without a `redirect`
parameter even though `buildLoginPath()` exists elsewhere
(`apps/dsa-web/src/components/auth/AuthGuardOverlay.tsx:42-50,170-184`,
`apps/dsa-web/src/hooks/useProductSurface.ts:56-75`).

This is a UX continuity issue, not current leakage.

3. Personal settings contains guest-facing copy that normal auth-enabled routing
never exposes

The page text suggests a guest settings mode, but `App.tsx` redirects guest
`/settings` traffic away before the page renders. That is confusing product
surface signaling, but safe.

### True security/product leakage

None proven in the current guarded-route policy.

Specifically not supported by evidence:

- guest seeing mounted real portfolio/backtest/options/watchlist/scanner content
  behind the overlay
- guest reaching canonical admin content without redirect/gate
- non-admin reaching admin content without capability gate

### Requires product decision

1. Whether public market intelligence routes should remain public

If product wants `liquidity-monitor` or `rotation-radar` to become authenticated
or paywalled, that is a product decision and behavior change, not a bugfix.

2. Whether guest `/settings` should remain a redirect or expose the existing
guest-local-preferences copy

The route and the page copy currently pull in different directions.

3. Whether same-route overlays should preserve a post-login return target

Changing this affects the guest/paywall funnel and should be decided
intentionally rather than slipped into a generic auth cleanup.

## True blockers for future write work

Current blocker list for implementation work:

- No proven leakage blocker requiring an auth rewrite
- One policy blocker: no approved route-class policy for "public vs overlay vs
  guest redirect" if someone wants to normalize behavior
- One test blocker: existing coverage is not broad enough to safely rewrite
  canonical admin guest redirects or all consumer guest overlays in one pass

## Existing test gaps

These are coverage gaps, not proof of current bugs:

1. Canonical admin guest redirect smoke is incomplete

Current tests heavily cover `/settings`, `/zh/admin`, and the T-1002 aliases,
but do not smoke every canonical admin route as a guest redirect target.

2. Browser-level guest overlay smoke is incomplete for the full consumer set

Current browser evidence is strongest for portfolio and options alias.
Market overview, scanner, watchlist, backtest compare, and backtest result
guest overlay behavior still relies mainly on unit-level route evidence.

3. `/admin/users/:userId/activity` capability precision needs explicit tests

`canAccessAdminPath()` distinguishes `canReadUserActivity` from `canReadUsers`,
but the audit did not find a focused deny/allow matrix proving activity-only
access rules.

4. `/guest/scanner` alias behavior exists in the router but lacks direct auth
coverage in the inspected tests.

## Exact tests required for any future auth behavior change

Any future write that changes route auth behavior must add or update all of the
following, scoped to the affected routes:

1. Route unit tests in `apps/dsa-web/src/__tests__/AppRoutes.test.tsx`

- guest behavior for every changed route and locale variant
- alias-to-canonical resolution
- whether the final URL stays on-route or redirects
- logged-in non-admin admin-gate behavior
- admin capability allow/deny behavior

2. Component tests if overlay/gate behavior changes

- `apps/dsa-web/src/components/auth/__tests__/AuthGuardOverlay.test.tsx` for
  CTA target, focus trap, non-dismissible behavior, and backdrop semantics
- `apps/dsa-web/src/pages/__tests__/GuestHomePage.test.tsx` if guest preview or
  paywall funnel changes

3. Guest browser smoke for changed protected consumer routes

Add or update Playwright coverage proving:

- final URL
- overlay visibility
- no protected content leakage text
- no protected API requests where applicable

Relevant harnesses/specs:

- `apps/dsa-web/e2e/ux-audit-p0-verification.smoke.spec.ts`
- `apps/dsa-web/e2e/product-auth-harness.spec.ts`
- `apps/dsa-web/e2e/fixtures/productAuth.ts`

4. Guest browser smoke for changed admin routes

Add or update Playwright coverage proving:

- guest redirect destination
- non-admin gate text on canonical admin routes
- admin alias resolution still lands on the intended canonical route

Relevant harnesses/specs:

- `apps/dsa-web/e2e/shell-route-admin-affordance.smoke.spec.ts`
- `apps/dsa-web/e2e/admin-auth-harness.spec.ts`
- `apps/dsa-web/e2e/fixtures/adminAuth.ts`

5. API/client tests only if login redirect mechanics change

If a future write changes 401/login redirect handling or introduces
route-preserving `redirect` parameters, update:

- `apps/dsa-web/src/api/__tests__/client.test.ts`
- any route/component tests that assert login CTA destinations

6. Backend preview tests if the guest product model changes

If the guest preview funnel or preview persistence policy changes, update:

- `tests/test_public_analysis_preview_api.py`

Do not treat frontend auth cleanup as independent from guest preview behavior.

## Recommended next tasks

Only evidence-supported tasks are recommended:

1. Test-hardening task, no behavior change

- Add guest smoke coverage for canonical admin routes
- Add guest smoke coverage for remaining consumer overlay routes
- Add capability-precision tests for `/admin/users/:userId/activity`

2. Policy decision task, no code yet

- Decide route-by-route whether the desired long-term model is:
  public, guest redirect, same-route overlay, or login redirect
- Explicitly include:
  `/settings`,
  `/market/liquidity-monitor`,
  `/market/rotation-radar`,
  `/market-overview`,
  `/scanner`,
  `/portfolio`,
  `/backtest`,
  `/options-lab`,
  admin canonical routes,
  T-1001/T-1002 aliases

3. Optional UX-only follow-up after policy approval

- If product wants same-route continuity after login, scope a small task to use
  redirect-aware login CTA behavior for overlay routes
- Do not combine this with admin/public-route policy changes

Not recommended:

- blanket redirect-to-login rewrite
- combining guest preview changes with admin-route normalization
- touching backend auth/RBAC semantics as part of a frontend route audit follow-up

## Stop conditions for future write work

Future implementation should stop immediately and report if any of these occur:

1. The proposed change cannot state the target policy per route class

- public
- guest redirect
- same-route overlay
- login redirect

2. The change would alter backend auth/RBAC/security semantics rather than only
frontend route behavior and copy

3. The change proposes blanket redirect-to-login without explicitly preserving
or retiring the guest preview/paywall product model

4. The change touches public market intelligence routes without an explicit
product decision that those routes should stop being public

5. The change cannot provide the route-level test matrix listed above for every
affected canonical route and alias

6. The change mixes admin-route policy, guest preview funnel changes, and
consumer paid-route overlay semantics into one patch

## Audit decision

Current route/auth policy should be treated as:

- intentional mixed policy
- mostly safe
- partially under-documented
- not ready for broad normalization without a prior route-policy decision and
  expanded test coverage

The UX audit should downgrade the earlier "protected-route guest access blocker"
to a more precise finding:

- guarded consumer/admin routes do not currently prove true leakage
- the real risk is policy ambiguity plus incomplete coverage for a future rewrite
