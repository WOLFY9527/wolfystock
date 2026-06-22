# T-1011 Admin Dashboard IA Audit

Task: T-1011 Admin dashboard IA audit

Mode: READ-ONLY-AUDIT with one explicitly allowed audit artifact.

Allowed artifact: `docs/codex/audits/T-1011-admin-dashboard-ia-audit.md`

Observed HEAD during audit: `d21e24e6` (`T-1007: clarify Backtest research-only boundary`)

Branch: `codex/t1011-admin-dashboard-ia-audit`

Scope boundary:

- Source inspected, not changed.
- Tests inspected, not changed.
- No config, lockfile, CI, changelog, source, or test changes.
- Subagents were used for read-only scouting of routes, shell affordance,
  settings/system, admin modules, permission guards, and admin tests.
- This audit does not propose a broad admin redesign.

## Executive Summary

Recommendation: keep `/admin` and locale variants redirecting to
`/settings/system`, and make the next write a narrow copy/test clarification on
the existing System Settings landing surface.

Current IA already treats `/settings/system` as the default admin control-plane
landing. The route map, shell, docs, and tests all point to a federated admin
model: one system landing plus independent admin surfaces for logs, users,
notifications, providers, evidence review, provider circuits, and cost
observability. There is no independent `/admin` dashboard route today, and
adding one now would either duplicate `SystemControlPlane` or require a new
cross-module composition layer that touches multiple permissions and data
contracts.

The product problem is not that a dashboard is missing. The sharper IA issue is
that the short route `/admin` behaves like an admin entry point while the
visible landing title remains `System Settings` / `System`. That is solvable
with copy that makes the current landing role explicit without changing route
structure, shell structure, permissions, or admin module boundaries.

## Evidence Sources

Read-only scouting covered:

- Router and aliases: `apps/dsa-web/src/App.tsx`.
- Admin capability mapping: `apps/dsa-web/src/utils/adminCapabilities.ts`.
- Shell and admin utility menu:
  `apps/dsa-web/src/components/layout/Shell.tsx` and
  `apps/dsa-web/src/components/layout/SidebarNav.tsx`.
- System landing and settings domains:
  `apps/dsa-web/src/pages/SystemSettingsPage.tsx`,
  `apps/dsa-web/src/pages/SettingsPage.tsx`, and
  `apps/dsa-web/src/components/settings/SystemControlPlane.tsx`.
- Admin module pages under `apps/dsa-web/src/pages/`.
- Frontend route/shell/page tests under `apps/dsa-web/src/**/__tests__/`.
- Backend RBAC inventory/contract tests under `tests/`.
- Admin IA docs:
  `docs/product/ADMIN_OPS_IA_CONSOLIDATION.md`,
  `docs/frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md`, and
  `docs/admin-ops/README.md`.

## Current Route Map

There is no standalone `/admin` page. `/admin` is an alias into the system
settings control plane.

| Route | Current behavior | Canonical page / role | Guard |
| --- | --- | --- | --- |
| `/admin` | Redirects to `/settings/system` | System admin landing | reaches `/settings/system` guard |
| `/:locale/admin` | Redirects to `../settings/system` | Localized system admin landing | reaches localized `/settings/system` guard |
| `/admin/system` | Redirects to `/settings/system` | Legacy system alias | reaches `/settings/system` guard |
| `/admin/ai` | Redirects to `/settings/system` | Legacy AI config alias | reaches `/settings/system` guard |
| `/admin/providers` | Redirects to `/admin/market-providers` | Legacy provider alias | reaches provider guard |
| `/admin/evidence` | Redirects to `/admin/evidence-workflow` | Legacy evidence alias | reaches ops-log guard |
| `/admin/costs` | Redirects to `/admin/cost-observability` | Legacy cost alias | reaches cost guard |
| `/settings/system` | Renders `SystemSettingsPage` | System landing, settings, AI/data/notification config | `canReadSystemConfig` |
| `/admin/logs` | Renders `AdminLogsPage` | Business events, logs, diagnostics | `canReadOpsLogs` |
| `/admin/evidence-workflow` | Renders `AdminEvidenceWorkflowPage` | Read-only evidence review workflow | `canReadOpsLogs` |
| `/admin/notifications` | Renders `AdminNotificationsPage` | Admin notification routing and events | `canReadNotifications` |
| `/admin/market-providers` | Renders `MarketProviderOperationsPage` | Provider operations and source gaps | `canReadProviders` |
| `/admin/provider-circuits` | Renders `AdminProviderCircuitDiagnosticsPage` | Provider circuit diagnostics | `canReadProviders` |
| `/admin/users` | Renders `AdminUsersPage` | User governance directory | `canReadUsers` |
| `/admin/users/:userId` | Renders `AdminUsersPage` detail | User detail | `canReadUsers` |
| `/admin/users/:userId/activity` | Renders `AdminUsersPage` activity | User activity | `canReadUserActivity` |
| `/admin/cost-observability` | Renders `AdminCostObservabilityPage` | Budget, quota, ledger, pricing observability | `canReadCostObservability` |

Route evidence:

- Non-locale aliases are declared at `apps/dsa-web/src/App.tsx:386-391`.
- Canonical non-locale admin pages are declared at
  `apps/dsa-web/src/App.tsx:409-418`.
- Locale aliases are declared at `apps/dsa-web/src/App.tsx:423-428`.
- Localized canonical pages are declared at `apps/dsa-web/src/App.tsx:446-455`.

## Current Permissions And Route Guards

All renderable admin surfaces go through `AdminSurfaceRoute`, which checks the
current product surface and calls `canAccessAdminPath()` before rendering. If
the capability check fails, the route renders an access gate instead of the
admin page.

Key guard evidence:

- `AdminSurfaceRoute` is implemented in `apps/dsa-web/src/App.tsx:211-247`.
- Guest-restricted admin/settings paths are enumerated in
  `apps/dsa-web/src/App.tsx:263-290`.
- Admin path to capability mapping is implemented in
  `apps/dsa-web/src/utils/adminCapabilities.ts:55-78`.
- Missing or non-admin capability state fails closed in
  `apps/dsa-web/src/utils/adminCapabilities.ts:39-53`.
- Backend inventory tests lock the same frontend capability mapping in
  `tests/test_auth_route_capability_inventory.py`.
- Release-facing RBAC tests cover ordinary-user denial, adjacent capability
  denial, and redacted 401/403/429 failures in
  `tests/api/test_auth_rbac_release_contracts.py`.

Permission conclusion:

- Any future admin landing work must preserve `AdminSurfaceRoute`,
  `canAccessAdminPath()`, the existing capability mapping, and the current
  guest redirect behavior.
- A new independent dashboard route would need its own capability decision. That
  is avoidable if `/admin` remains an alias to `/settings/system`.

## Current Shell Affordance

The app does not expose admin as a primary product nav item. Admin surfaces live
in a utility menu labeled `System` / `System`-equivalent localized copy, and the
menu contents are derived from the user's admin capabilities.

Shell evidence:

- The main `NAV_ITEMS` set does not include `/admin`:
  `apps/dsa-web/src/components/layout/SidebarNav.tsx:80-90`.
- Capability-derived admin menu items are built in
  `apps/dsa-web/src/components/layout/SidebarNav.tsx:158-179`.
- The desktop admin dropdown uses `shell-admin-utility-menu` at
  `apps/dsa-web/src/components/layout/SidebarNav.tsx:317-397`.
- The shell maps admin routes to specific route labels in
  `apps/dsa-web/src/components/layout/Shell.tsx:41-89`.
- System-control shell sizing/styling applies to `/settings/system` and admin
  pages via `apps/dsa-web/src/components/layout/Shell.tsx:201-208`.

Test evidence:

- Shell tests assert the system settings wide workspace and admin logs
  system-control shell in
  `apps/dsa-web/src/components/layout/__tests__/Shell.test.tsx`.
- The same tests assert that only capability-authorized admin menu entries are
  visible and missing capability fields hide the admin affordance.

Shell conclusion:

- The shell already supports the current federated admin model.
- Changing the shell/admin entry structure is a larger navigation task and is
  not justified by the `/admin` alias question alone.

## Current Canonical Admin Surfaces

### `/settings/system`

This is the canonical admin landing today. `SystemSettingsPage` wraps
`SettingsPage`, shows an L0 overview strip, and lazy-loads the full settings
control plane. On the system route, `SettingsPage` starts on the `overview`
panel, whose content is `SystemControlPlane`.

Evidence:

- `SystemSettingsPage` title, chips, L0 strip, and reset confirmation:
  `apps/dsa-web/src/pages/SystemSettingsPage.tsx:112-170`.
- `SettingsPage` domain order: AI models, data sources, notifications, advanced:
  `apps/dsa-web/src/pages/SettingsPage.tsx:300-315`.
- System route initial panel is `overview`:
  `apps/dsa-web/src/pages/SettingsPage.tsx:547-586`.
- `SystemControlPlane` first viewport contains system health, priority settings,
  risk boundary, and secondary compatibility/details zones:
  `apps/dsa-web/src/components/settings/SystemControlPlane.tsx:356-537`.

IA role:

- Admin entry landing for system configuration work.
- First screen is operator state, risk, and next action.
- Deep config, raw fields, reload/cache actions, and danger actions are
  secondary or confirmed.

### AI And Provider Config Surface

AI/provider config is not a separate route. It is part of the system settings
landing:

- AI config renders through `AIProviderConfig` from
  `apps/dsa-web/src/pages/SettingsPage.tsx:2422-2439`.
- Data provider/source config renders through `DataSourceConfig` from
  `apps/dsa-web/src/pages/SettingsPage.tsx:2444-2460`.
- Notifications and advanced/runtime settings are sibling panels at
  `apps/dsa-web/src/pages/SettingsPage.tsx:2462-2479`.

IA role:

- AI/model routing, data source setup, notifications, and advanced runtime
  settings are configuration domains under the system landing, not independent
  dashboard modules.

### `/admin/logs`

`AdminLogsPage` is the operational event and diagnostics surface. It prioritizes
business events and health summaries while keeping raw/debug detail behind tabs
and disclosures.

Evidence:

- Main render begins at `apps/dsa-web/src/pages/AdminLogsPage.tsx:1782`.
- Tabs, filters, storage disclosure, issue rollup, data gaps, main queue, and
  detail drawer are covered in the same page.
- Tests cover default business tab behavior, degraded copy, detail drawer, and
  secret/path redaction in `apps/dsa-web/src/pages/__tests__/AdminLogsPage.test.tsx`.

### `/admin/users`

`AdminUsersPage` is a support/governance surface for user directory, detail,
activity, portfolio projections, and security actions.

Evidence:

- Main render begins at `apps/dsa-web/src/pages/AdminUsersPage.tsx:1360`.
- Security actions require reason and confirmation in
  `apps/dsa-web/src/pages/AdminUsersPage.tsx:760-900`.
- Tests cover safe projections, hidden raw sessions/credentials, log drilldown
  gating, and typed confirmation in
  `apps/dsa-web/src/pages/__tests__/AdminUsersPage.test.tsx`.

### `/admin/notifications`

`AdminNotificationsPage` manages admin notification routing, dry-run/test-send
flows, and event acknowledgement.

Evidence:

- Main render begins at
  `apps/dsa-web/src/pages/AdminNotificationsPage.tsx:494`.
- Route coverage summary, create-channel form, rule actions, and events are
  rendered at `apps/dsa-web/src/pages/AdminNotificationsPage.tsx:557-832`.
- Tests cover masked webhook-style values, dry-run, ack/delete behavior, and
  redacted diagnostics in
  `apps/dsa-web/src/pages/__tests__/AdminNotificationsPage.test.tsx`.

### `/admin/market-providers`

`MarketProviderOperationsPage` is a provider operations roadmap and diagnostics
surface. It is explicitly read-only/diagnostic and does not change provider
runtime behavior.

Evidence:

- Main render begins at
  `apps/dsa-web/src/pages/MarketProviderOperationsPage.tsx:2045`.
- Source gaps, provider matrix, readiness diagnostics, cache/error summaries,
  and quota/cost clues are rendered within the page.
- Tests cover read-only posture, safe drill-through, query sanitization, and no
  raw credential/local-path leakage in
  `apps/dsa-web/src/pages/__tests__/MarketProviderOperationsPage.test.tsx`.

### `/admin/provider-circuits`

`AdminProviderCircuitDiagnosticsPage` is a provider circuit and quota diagnostic
surface adjacent to provider ops.

Evidence:

- Main render begins at
  `apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx:996`.
- Tests cover diagnostic-only copy, folded technical detail, safe links, and
  redaction in
  `apps/dsa-web/src/pages/__tests__/AdminProviderCircuitDiagnosticsPage.test.tsx`.

### `/admin/evidence-workflow`

`AdminEvidenceWorkflowPage` is a static/read-only evidence workflow review
surface. It emphasizes manual gatekeeping and no write actions.

Evidence:

- Main render begins at
  `apps/dsa-web/src/pages/AdminEvidenceWorkflowPage.tsx:158`.
- The page states that it does not upload evidence, call backend write APIs, or
  change runtime config at
  `apps/dsa-web/src/pages/AdminEvidenceWorkflowPage.tsx:277-305`.
- Tests cover read-only posture, no upload/save/approve action, static
  runbook/schema/command content, and default folded detail in
  `apps/dsa-web/src/pages/__tests__/AdminEvidenceWorkflowPage.test.tsx`.

### `/admin/cost-observability`

`AdminCostObservabilityPage` is a cost, budget, quota, ledger, and pricing
observability surface.

Evidence:

- Main render begins at
  `apps/dsa-web/src/pages/AdminCostObservabilityPage.tsx:1005`.
- Filters, main board, quota dry-run, ledger, and pricing panels are contained
  in this route.
- Tests cover read-only/observation posture, folded details, capability-limited
  fetches, redacted failures, and dry-run wording in
  `apps/dsa-web/src/pages/__tests__/AdminCostObservabilityPage.test.tsx`.

## Admin IA Assessment

The current IA is internally consistent:

1. `/settings/system` is the L0 admin control-plane landing.
2. `/admin` is a convenience alias to that landing.
3. Admin modules are independent canonical surfaces with capability-specific
   route guards.
4. Shell affordance is capability-derived and utility-scoped, not primary-nav.
5. Most admin pages already follow the Admin/Ops L0-L4 pattern: state first,
   drill-through second, raw/diagnostic detail folded.

The current IA weakness is naming and expectation management:

- Users who type `/admin` may expect a distinct dashboard.
- The visible landing still reads as system settings, so the alias can feel like
  a redirect to a lower-level settings page even though the first viewport is
  already an operator control plane.
- A dashboard label would be misleading if it implied live aggregation across
  users, costs, providers, logs, and evidence without a dedicated data contract.

Relevant docs align with the current IA:

- `docs/product/ADMIN_OPS_IA_CONSOLIDATION.md` defines `/settings/system` as the
  L0 system control-plane surface and keeps controlled actions inside existing
  routes.
- `docs/frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md` says admin pages should
  answer state, impact, recommended action, evidence, and detail in that order.
- `docs/admin-ops/README.md` says to use the Admin/Ops IA lane before changing
  admin dashboards and to keep raw logs/destructive maintenance/diagnostics
  behind expansion or confirmation.

## Option Decision

### 1. Keep `/admin` Redirecting To System Settings But Improve Copy

Decision: recommended.

Why:

- Preserves the tested alias map and route guards.
- Makes the admin-entry role explicit without adding a new route or data
  contract.
- Reuses `SystemSettingsPage` and `SystemControlPlane`, which already act as the
  operator first viewport.
- Avoids touching shell navigation, backend RBAC, provider behavior, or admin
  module internals.

### 2. Add A Lightweight Admin Overview Page

Decision: not the next write.

Why:

- A new overview would either duplicate the existing `SystemControlPlane` or
  compose status from logs, providers, costs, users, evidence, notifications,
  and settings.
- Cross-module composition would require new permission semantics and likely new
  frontend data orchestration.
- The current admin modules are useful, but their readiness and fetch contracts
  are intentionally route-specific.

### 3. Change Shell/Admin Entry Structure

Decision: not the next write.

Why:

- The current shell affordance is already capability-gated and tested.
- Moving admin into primary navigation would broaden product IA beyond the
  `/admin` landing question.
- Changing shell structure risks breaking capability-derived visibility and
  localized labels for little immediate gain.

### 4. Defer Dashboard Until Ops Modules Stabilize

Decision: true for a real dashboard, but not enough as the next action.

Why:

- A true multi-module admin dashboard should be deferred until admin module
  contracts stabilize.
- The current alias expectation can still be improved now with narrow copy and
  tests.

## Recommended Next Write Task

Recommended task: `T-1011-FE: clarify Admin landing copy on System Settings`.

Goal:

- Keep `/admin`, `/zh/admin`, and `/en/admin` redirecting to the existing
  system settings landing.
- Adjust only the landing copy in `SystemSettingsPage` so it clearly frames the
  page as the admin/system operations landing, not merely a generic settings
  page.
- Add or update a focused test that locks the clarified copy and preserves the
  existing system landing test posture.

Exact allowed files for that future write:

- `apps/dsa-web/src/pages/SystemSettingsPage.tsx`
- `apps/dsa-web/src/pages/__tests__/SystemSettingsPage.test.tsx`

No other files should be changed unless a future prompt explicitly expands
scope.

Validation for that future write:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/SystemSettingsPage.test.tsx src/__tests__/AppRoutes.test.tsx src/components/layout/__tests__/Shell.test.tsx --run
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run build
./scripts/release_secret_scan.sh
git diff --name-only
git diff --check
git status --short --branch
```

Behavior invariants for that future write:

- `/admin`, `/zh/admin`, and `/en/admin` continue redirecting to
  `/settings/system` or the localized system settings route.
- No new `/admin` route element, `/admin/dashboard` route, dashboard component,
  API fetch, schema, or backend endpoint.
- Preserve `AdminSurfaceRoute`, `canAccessAdminPath()`, guest redirect behavior,
  and all current capability mappings.
- Capability fields missing from the current user continue to fail closed.
- The admin utility menu continues to show only capability-authorized entries.
- `evidence-workflow` remains guarded by ops-log read capability and is not
  unlocked by adjacent provider/cost/user capabilities.
- System settings keeps the L0 overview strip, lazy settings page loading,
  factory reset confirmation interception, and secondary placement of raw,
  compatibility, cache/reload, and dangerous actions.
- No provider runtime order, cache/fallback semantics, AI routing/model logic,
  notification routing, cost/provider/user/evidence API behavior, RBAC
  contracts, or stored config semantics change.
- No raw debug payloads, credentials, session identifiers, or local filesystem
  paths are introduced into visible copy or tests.

## Not Recommended

Do not propose or implement these as part of the next write:

- Broad admin redesign.
- New dashboard route.
- Main navigation restructure.
- New cross-admin aggregation API.
- Admin permission contract changes.
- Changes to backend RBAC, provider runtime, AI config save behavior,
  notification routing, cost ledgers, evidence workflow state, or admin user
  security actions.

## Current Task Validation Plan

Required validation for this audit artifact:

```bash
git diff --name-only
git diff --check
./scripts/release_secret_scan.sh
git status --short --branch
```

Expected final diff:

- `docs/codex/audits/T-1011-admin-dashboard-ia-audit.md`

Proof target:

- Docs-only artifact.
- No source files modified.
- No test files modified.
- No config, lockfile, CI, or changelog modified.
