# T-1017 auth route policy decision record

Task: T-1017-AUDIT

Mode: READ-ONLY-AUDIT with one explicitly allowed docs artifact.

Allowed artifact: `docs/codex/audits/T-1017-auth-route-policy-decision-record.md`

Scope boundary:

- No source, test, router, auth, RBAC, API, backend, provider, config, lockfile, or package changes.
- No route behavior changes.
- No new auth policy implementation.

## Decision

Keep the current mixed route-access model as the documented baseline.

The current behavior is not a blanket redirect-to-login model and should not be
treated as an unfinished auth rewrite. Future changes should start from a
product decision for the affected route class: public, guest redirect,
same-route overlay, or admin capability gate.

Do not start a blanket login redirect rewrite from this audit. The evidence
supports a smaller follow-up path: document the policy, harden route smoke where
coverage is still representative rather than exhaustive, and align confusing
copy if product wants clearer intent.

## Evidence base

Primary decision inputs:

- T-1009 audit: `docs/codex/audits/T-1009-auth-guard-policy-audit.md`
- Router and guards: `apps/dsa-web/src/App.tsx:185-455`
- Admin capability gate: `apps/dsa-web/src/utils/adminCapabilities.ts:53-80`
- Scanner guest overlay: `apps/dsa-web/src/pages/ScannerSurfacePage.tsx:8-14`
- Watchlist guest overlay: `apps/dsa-web/src/pages/WatchlistPage.tsx:1539-1541`
- T-1009-TEST smoke additions: `apps/dsa-web/e2e/ux-audit-p0-verification.smoke.spec.ts:768-1015`
- Supporting route unit tests: `apps/dsa-web/src/__tests__/AppRoutes.test.tsx:315-540`

## Route policy matrix

| Route class | Current routes | Guest behavior | Logged-in non-admin behavior | Decision status |
| --- | --- | --- | --- | --- |
| Public routes | `/`, `/:locale`, `/guest`, `/:locale/guest`, `/login`, `/:locale/login`, `/reset-password`, `/:locale/reset-password`, preview routes under `/__preview/*` | Stay on public route, except signed-in users are redirected away from guest/login/reset where the router already does so | Uses normal public or signed-in flow | Keep as-is |
| Guest redirect routes | `/settings`, `/settings/*`, localized equivalents | Redirect to localized `/guest` before page content renders | `/settings` is personal settings; `/settings/system` is admin-gated | Keep as-is; copy can be clarified separately |
| Same-route overlay protected consumer routes | `/portfolio`, `/market-overview`, `/watchlist`, `/backtest`, `/options-lab`, `/backtest/compare`, `/backtest/results/:runId`, localized equivalents; `/scanner` via page-level guard | Stay on the requested URL and render `AuthGuardOverlay` through `ConsumerProtectedFrame`; no blanket redirect | Render product surface when signed in | Keep as-is |
| Admin canonical and alias guest redirect routes | Canonical admin routes including `/settings/system`, `/admin/logs`, `/admin/evidence-workflow`, `/admin/notifications`, `/admin/market-providers`, `/admin/provider-circuits`, `/admin/users`, `/admin/users/:userId`, `/admin/users/:userId/activity`, `/admin/cost-observability`, plus aliases `/admin`, `/admin/system`, `/admin/providers`, `/admin/evidence`, `/admin/costs`, `/admin/ai` and localized equivalents | Guests redirect to localized `/guest`; aliases resolve only after the guest restriction check when applicable | See admin capability-gated row | Keep as-is |
| Logged-in non-admin capability-gated admin routes | Same canonical admin routes after alias resolution | Not applicable after guest redirect | Stay on-route and see an admin/capability gate unless `canAccessAdminPath()` grants the specific capability | Keep as-is |
| Public read surfaces | `/market/liquidity-monitor`, `/market/rotation-radar`, aliases `/liquidity`, `/rotation`, localized equivalents | Stay public and render the read surface or canonical public route | Same public read surface | Keep as-is unless product decides these should stop being public |

## Smoke coverage after T-1009-TEST

Already protected by e2e smoke:

- Public read aliases: `/zh/liquidity`, `/en/liquidity`, `/zh/rotation`, `/en/rotation` resolve to canonical liquidity/rotation surfaces without 404 or visible raw leakage.
- Canonical admin guest redirect representatives: `/zh/settings/system`, `/zh/admin/logs`, and `/zh/admin/users/user-123/activity` redirect to guest preview and do not leak admin copy.
- Admin alias guest redirect representative: `/zh/admin/providers` redirects to guest preview and does not leak admin copy.
- Same-route consumer overlay representatives: `/zh/portfolio`, `/zh/watchlist`, `/zh/scanner`, and `/zh/backtest/results/34` stay on-route, show `auth-guard-overlay`, and hide protected product copy.
- Protected options alias representative: `/zh/options` redirects to `/zh/options-lab`, shows the guest overlay, hides product content, and makes no options product API calls.
- Signed-in admin alias canonicalization: `/zh/admin/system`, `/zh/admin/providers`, `/zh/admin/evidence`, `/zh/admin/costs`, and `/zh/admin/ai` resolve to their canonical protected surfaces.
- Nested admin deny gate: `/zh/admin/users/user-123/activity` denies access for an admin account with `users:read` but without `users:activity:read`, and does not call the nested activity/user APIs.

Supporting unit tests also cover `/settings` guest redirects, representative
consumer overlays, admin alias guest/non-admin behavior, liquidity/rotation
aliases, and signed-in canonical route rendering.

## Remaining ambiguity

Treat these as product decisions, not bugs:

1. Whether liquidity and rotation should remain public read surfaces.
   They are public today; changing that would alter product access strategy.

2. Whether `/settings` should stay a guest redirect or expose any guest-local
   preferences copy. The current router redirects guests before the settings
   page renders, so the mismatch is copy/product signaling rather than leakage.

3. Whether same-route overlays should preserve post-login return intent. This
   may improve continuity, but it should be scoped as an overlay/login CTA UX
   task, not as an auth policy rewrite.

## Recommended next tasks

1. Docs/copy alignment task, no route behavior change:
   add this route-class matrix to the maintained product/auth docs or link to
   this decision record, and adjust confusing settings guest copy only if
   product confirms `/settings` should remain redirect-only for guests.

2. Targeted route-smoke hardening, no route behavior change:
   expand e2e smoke from representative coverage to the remaining canonical
   admin routes and a small set of consumer overlay locale variants if future
   auth tasks will depend on exhaustive route confidence.

## Do not open yet

Do not open any of the following until a product decision explicitly authorizes
the target route class and migration plan:

- Blanket auth/login redirect rewrite. Migration risks: breaks the intentional
  guest preview/paywall model, changes same-route overlay semantics, changes
  public liquidity/rotation access, invalidates existing alias smoke, and may
  alter deep-link expectations.
- Route shell rewrite. Migration risks: couples auth policy with layout, can
  reintroduce route fallback/404 regressions, and widens validation beyond the
  current route-policy question.
- RBAC refactor. Migration risks: touches protected security semantics,
  capability mapping, admin API expectations, and backend/client contracts that
  this audit did not authorize changing.

## Final boundary

This decision record documents the current policy only. The final diff for
T-1017 must remain docs-only and limited to this file.
