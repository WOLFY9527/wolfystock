# T-1039 Admin layout sidebar title consistency readiness audit

Task ID: T-1039-AUDIT
Task title: Admin layout sidebar title consistency readiness audit
Mode: READ-ONLY-AUDIT with docs-only report artifact
Workspace: `/Users/yehengli/worktrees/t1039-admin-layout-title-readiness-audit`
Branch: `codex/t1039-admin-layout-title-readiness-audit`
Base commit inspected: `be618cea`

## Decision

Recommend exactly one bounded immediate write:

**T-1039-FE1 Admin document.title completion for User Governance and Provider Ops**

This is safer and smaller than an admin shell/sidebar rewrite because the browser
and code audit found the clearest real defect in page-level document titles, not
in the shared admin navigation contract. Do not create a new Admin Dashboard, do
not rewrite auth/RBAC, do not rewrite routes, and do not change backend/API,
provider, cache, runtime, or data-fetching behavior.

Defer any persistent admin sidebar or admin shell rewrite. Current admin pages
share the same top shell and capability-gated "system" admin menu, while their
internal side rails are route-specific operator controls. Forcing one sidebar
everywhere would collide with dense tables, settings category navigation, and
provider/user drilldown panels.

## Evidence Method

- Static inspection of routes, shell classification, admin navigation, and page
  title code.
- Browser check against `http://127.0.0.1:8000` after local admin login with
  user-provided credentials.
- Routes inspected:
  - `/zh/admin`
  - `/zh/settings/system`
  - `/zh/admin/logs`
  - `/zh/admin/users`
  - `/zh/admin/providers`
- Browser viewport observed: `1280x720`.
- No screenshots or generated assets were saved.
- No source files were modified by this audit.

## Current Admin Routing And Shell Ownership

- `/admin` redirects to `/settings/system`; localized `/zh/admin` redirects to
  `/zh/settings/system` (`apps/dsa-web/src/App.tsx:386`,
  `apps/dsa-web/src/App.tsx:423`).
- `/admin/providers` redirects to `/admin/market-providers`; localized
  `/zh/admin/providers` redirects to `/zh/admin/market-providers`
  (`apps/dsa-web/src/App.tsx:388`, `apps/dsa-web/src/App.tsx:425`).
- Admin/control routes share the system-control shell classification
  (`apps/dsa-web/src/components/layout/Shell.tsx:201`).
- The shared admin navigation is a capability-gated "system" menu in
  `SidebarNav`, not a persistent left sidebar
  (`apps/dsa-web/src/components/layout/SidebarNav.tsx:150`,
  `apps/dsa-web/src/components/layout/SidebarNav.tsx:158`,
  `apps/dsa-web/src/components/layout/SidebarNav.tsx:317`).

## Browser Verdict Matrix

| Requested route | Final route | Visible page title | `document.title` | Sidebar / side-rail verdict | Layout verdict |
| --- | --- | --- | --- | --- | --- |
| `/zh/admin` | `/zh/settings/system` | `系统设置` | `系统设置 - WolfyStock` | Uses shared header admin menu plus Settings internal category aside. No missing admin dashboard. | Intentional admin landing/control layout. |
| `/zh/settings/system` | `/zh/settings/system` | `系统设置` | `系统设置 - WolfyStock` | Same shared header admin menu. Internal settings rail is a settings category/control rail, not global admin nav. | Intentional dense configuration/control surface. |
| `/zh/admin/logs` | `/zh/admin/logs` | `管理员日志` | `管理员日志 - WolfyStock` | Same shared header admin menu. No persistent page sidebar; drill-through strips and dense log panels are page-local. | Intentional operator log density. |
| `/zh/admin/users` | `/zh/admin/users` | `用户目录` | `WolfyStock` | Same shared header admin menu. A left filter aside is page-local search/filter control, not global admin nav. | Intentional user-governance density; title is missing/ambiguous. |
| `/zh/admin/providers` | `/zh/admin/market-providers` | `数据源维护路线图` | `WolfyStock` | Same shared header admin menu. No persistent page sidebar; provider matrix/drilldowns own the page layout. | Intentional provider-ops density; title is missing/ambiguous. |

All five browser-checked final routes reported no horizontal overflow in the
observed desktop viewport.

## Distinctions

### 1. Intentional Admin Dense Layouts

Admin Logs, Admin Users, Provider Ops, and System Settings are operator
surfaces. Dense tables, compact chips, drill-through strips, settings category
navigation, and filter asides are appropriate for these routes. They should not
be normalized to consumer Home-style spacing or a marketing/dashboard layout.

Evidence:

- System Settings explicitly states it is the default admin control entry, not a
  missing standalone dashboard (`apps/dsa-web/src/pages/SystemSettingsPage.tsx:33`,
  `apps/dsa-web/src/pages/SystemSettingsPage.tsx:65`).
- Admin Logs uses a dense terminal shell with an explicit H1 and L0 ops strip
  (`apps/dsa-web/src/pages/AdminLogsPage.tsx:1792`,
  `apps/dsa-web/src/pages/AdminLogsPage.tsx:1798`).
- Admin Users uses one compact support/governance page shell and page-local
  user directory/detail controls (`apps/dsa-web/src/pages/AdminUsersPage.tsx:300`,
  `apps/dsa-web/src/pages/AdminUsersPage.tsx:1362`).
- Provider Ops uses an operations roadmap, L0 strip, drill-through links, and
  matrix sections (`apps/dsa-web/src/pages/MarketProviderOperationsPage.tsx:2046`,
  `apps/dsa-web/src/pages/MarketProviderOperationsPage.tsx:2049`).

### 2. Real Side-Rail / Sidebar Inconsistency

There is no evidence that the shared admin navigation itself is missing from the
checked routes. The same top shell and "system" admin menu were visible across
all inspected admin routes. When opened on Provider Ops, the menu contained:

`系统`, `用户治理`, `成本观测`, `通知`, `数据源运维`, `熔断诊断`, `证据复核`, `系统日志`.

The real inconsistency is lower level: page-local side rails mean different
things on different admin pages.

- System Settings has a settings category/control aside.
- Admin Users has a filter/search aside.
- Admin Logs and Provider Ops do not have a persistent left admin sidebar.

This is a taxonomy/readiness concern, not immediate proof that every admin route
needs a shared sidebar.

### 3. Missing / Ambiguous `document.title`

The strongest immediate defect is page title metadata.

- System Settings lands on `系统设置 - WolfyStock`, via the nested Settings title
  effect (`apps/dsa-web/src/pages/SettingsPage.tsx:589`).
- Admin Logs sets `管理员日志 - WolfyStock`
  (`apps/dsa-web/src/pages/AdminLogsPage.tsx:1454`).
- Admin Users rendered visible `用户目录`, but browser `document.title` remained
  `WolfyStock`.
- Provider Ops rendered visible `数据源维护路线图`, but browser `document.title`
  remained `WolfyStock`.

This is user-visible in browser tabs, task switchers, history entries, and screen
reader context, and it can be fixed without touching layout, routing, auth, API,
or runtime semantics.

### 4. Risks From Forcing One Sidebar Everywhere

A shared persistent admin sidebar is not the smallest safe write now.

Risks:

- It would compete with System Settings' existing category aside and runtime
  context aside.
- It would crowd Admin Logs' dense tables and drawer workflow.
- It would conflict with Admin Users' filter/search aside and detail tabs.
- It would reduce Provider Ops' matrix and drill-through width.
- It would require route/shell behavior decisions across admin surfaces,
  increasing the chance of auth/RBAC, responsive layout, or navigation
  regressions.

If an admin sidebar is still desired later, first write a separate admin
navigation taxonomy spec with desktop/mobile behavior, internal rail ownership,
active state, capability gating, and overflow constraints.

## Recommended Immediate Write

### Task title

T-1039-FE1 Admin document.title completion for User Governance and Provider Ops

### Goal

Add explicit localized `document.title` effects for:

- `AdminUsersPage`
- `MarketProviderOperationsPage`

Expected titles:

- `/zh/admin/users`: `用户治理 - WolfyStock` or `用户目录 - WolfyStock`
- `/en/admin/users`: `User Governance - WolfyStock` or
  `User Directory - WolfyStock`
- `/zh/admin/providers` after redirect to `/zh/admin/market-providers`:
  `数据源运维 - WolfyStock` or `数据源维护路线图 - WolfyStock`
- `/en/admin/providers` after redirect to `/en/admin/market-providers`:
  `Provider Ops - WolfyStock` or `Provider Operations - WolfyStock`

Use the page's current visible language source. Do not introduce a shared
document-title framework unless the implementation proves the two page-local
effects duplicate enough real logic to justify it.

### Allowed future write scope

- `apps/dsa-web/src/pages/AdminUsersPage.tsx`
- `apps/dsa-web/src/pages/MarketProviderOperationsPage.tsx`
- Focused page tests only if they already have a stable pattern for
  `document.title` assertions.

### Forbidden future write scope

- No new Admin Dashboard.
- No admin shell/sidebar implementation.
- No persistent admin sidebar or global nav rewrite.
- No auth/RBAC/security behavior change.
- No route rewrite or redirect change.
- No backend/API/provider/cache/runtime change.
- No package, lockfile, config, CI, or dependency change.
- No raw provider/admin/debug payload exposure.

### Suggested validation for the future write

```bash
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run test -- src/pages/__tests__/AdminUsersPage.test.tsx --run
npm --prefix apps/dsa-web run build
git diff --check
./scripts/release_secret_scan.sh
```

If Provider Ops has no focused test harness suitable for document title, keep
the code change page-local and use browser verification for:

- `/zh/admin/users`
- `/zh/admin/providers`
- `/en/admin/users`
- `/en/admin/providers`

## Deferred Tasks

Do not start these as the immediate write:

- New Admin Dashboard.
- Admin shell/sidebar rewrite.
- Route/auth/RBAC rewrite.
- Backend/API/provider/cache/runtime change.
- Global title manager or route metadata framework.
- Consumer/admin spacing normalization.

## Final Intended Diff For T-1039-AUDIT

- `docs/codex/audits/T-1039-admin-layout-sidebar-title-consistency-readiness-audit.md`

No source, tests, config, package, lockfile, route/auth/RBAC/backend/API,
provider, cache, runtime, admin dashboard, admin shell/sidebar implementation,
screenshots, or generated assets are changed.
