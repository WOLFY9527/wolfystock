# T-1074 Admin system-control rail policy write-readiness audit

Task ID: T-1074-AUDIT

Task title: Admin system-control rail policy write-readiness audit

Mode: READ-ONLY-AUDIT with one explicitly allowed docs artifact.

Allowed artifact: `docs/codex/audits/T-1074-admin-system-control-rail-policy-write-readiness-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1074-admin-system-control-rail-policy-audit`
- branch: `codex/t1074-admin-system-control-rail-policy-audit`
- source/UI base inspected: `f514728e71a54e5dfd96c05c8faf0d0c2e57b945`

## Decision

The admin/system-control rail should **remain a distinct 1600px operator rail for now**.

This is a real inner-rail policy difference from consumer 1880px route shells, but the current evidence does not show operator density harm, route breakage, or horizontal overflow. Do not align admin to the consumer 1880px contract and do not rewrite the shared shell.

Recommended future write, exactly one:

1. **T-1074-TEST1 Admin rail contract guard**: add focused frontend tests that codify the current admin/system-control rail contract across `/zh/settings/system`, `/zh/admin/logs`, `/zh/admin/users`, and `/zh/admin/market-providers`.

Do not do a source/layout write unless a later browser pass shows concrete operator harm. Do not do a docs-only follow-up; this artifact is the policy record. Do not start a global spacing token migration, shared primitive rewrite, consumer/admin unification, or new Admin Dashboard.

## Source Ownership

### 1. Admin 1600px width owner

The 1600px inner rail is owned by the shared `TerminalPageShell` default:

- `apps/dsa-web/src/components/terminal/TerminalPrimitives.tsx:17-22`
- default class: `w-full max-w-[1600px] mx-auto px-4 xl:px-8 flex flex-col gap-5`

The four audited admin/system-control routes all render a `TerminalPageShell` and do not declare an independent page-local max-width:

- `/zh/settings/system`: `SystemSettingsPage` uses `TerminalPageShell` with `min-h-0 flex-1 overflow-x-hidden py-5 text-white md:py-6` at `apps/dsa-web/src/pages/SystemSettingsPage.tsx:174-177`.
- `/zh/admin/logs`: `AdminLogsPage` uses `TerminalPageShell` with `min-h-0 flex-1 overflow-x-hidden py-5 md:py-6` at `apps/dsa-web/src/pages/AdminLogsPage.tsx:1835-1836`.
- `/zh/admin/users`: `AdminUsersPage` uses `TerminalPageShell` with `min-h-0 flex-1 overflow-x-hidden` at `apps/dsa-web/src/pages/AdminUsersPage.tsx:1364-1367`.
- `/zh/admin/market-providers`: `MarketProviderOperationsPage` uses `TerminalPageShell` with `py-5 md:py-6` at `apps/dsa-web/src/pages/MarketProviderOperationsPage.tsx:2049-2051`.

The consumer 1880px near-full contract is separate and owned by `ConsumerWorkspaceShell`:

- `apps/dsa-web/src/components/layout/ConsumerWorkspaceShell.tsx:10-12`
- it sets `--wolfy-consumer-shell-max:1880px` and overrides nested `page-shell` max width.

### 2. System-control/admin padding owner

The route-family main-column padding is owned by `Shell.tsx`:

- `apps/dsa-web/src/components/layout/Shell.tsx:201-208` classifies `/settings/system` and admin routes as `isSystemControlRoute`.
- `apps/dsa-web/src/components/layout/Shell.tsx:212-221` also treats system-control routes as wide shell routes.
- `apps/dsa-web/src/components/layout/Shell.tsx:529-533` applies `shell-content-frame--system-control`, `shell-main-column--system-control`, and `p-0` on `.shell-main-column`.

The inner page padding still comes from `TerminalPageShell` and route-local additions:

- horizontal inner padding: `px-4 xl:px-8` from `TerminalPageShell`, computed as `28px` at 1440px and 1920px in the browser.
- vertical inner padding: `py-5 md:py-6` on System Settings, Admin Logs, and Market Providers; Admin Users intentionally has `0px` page-shell vertical padding because its directory/detail workspace owns more of the vertical structure.

### 3. Intentional density vs accidental drift

Treat the current 1600px admin rail as **intentional operator density with weakly documented contract**, not as accidental drift.

Evidence for intentional density:

- T-1039 classified System Settings, Admin Logs, Admin Users, and Provider Ops as operator surfaces with dense tables, compact chips, drill-through strips, settings category navigation, and filter asides; it explicitly warned against normalizing them to consumer Home-style spacing or a marketing/dashboard layout.
- T-1037 similarly classified System Settings and admin pages as admin/control or admin-ops density and deferred them from broad spacing/card-grid normalization.
- `SystemSettingsPage.test.tsx` explicitly asserts `max-w-[1600px]`, `mx-auto`, `px-4`, and `xl:px-8` on the system-settings page shell.
- `Shell.test.tsx` explicitly asserts admin logs stay on the system-control shell with `shell-main-column--system-control` and `p-0`.

Evidence for weak contract:

- Only System Settings currently has a direct class-level test for the 1600px page-shell rail.
- Admin Logs asserts the page shell primitive and vertical padding, but not the max-width contract.
- Admin Users and Market Providers rely on the shared `TerminalPageShell` default and broader page tests.
- The policy is therefore real, but under-guarded across the full admin/system-control family.

## Browser Check

Method:

- Local app: `http://127.0.0.1:8000`
- Auth state: authenticated admin browser session. No password, cookie, session ID, or token was recorded in this artifact.
- Viewports: `1440x1000` and `1920x1080`
- Routes checked: `/zh/settings/system`, `/zh/admin/logs`, `/zh/admin/users`, `/zh/admin/market-providers`
- Metrics captured: final URL, document title, `.shell-content-frame`, `.shell-main-column`, first visible `data-terminal-primitive="page-shell"`, computed max-width, computed padding, scroll width, horizontal overflow, and console error/warn count.
- Browser note: one in-app browser navigation briefly produced an unmounted empty body; a reload mounted the route normally. Final metrics were collected after route mount. Console error/warn output was empty.

All checked routes had `overflowPx=0`.

| Route | Viewport | Final URL | Main width / padding | Page-shell width / max | Page-shell padding | Verdict |
| --- | ---: | --- | ---: | ---: | --- | --- |
| `/zh/settings/system` | 1440 | `/zh/settings/system` | `1382.4`, `0px` | `1382.4 @ 1600px` | `28px x / 21px y` | Shared system-control rail; no overflow. |
| `/zh/admin/logs` | 1440 | `/zh/admin/logs` | `1382.4`, `0px` | `1382.4 @ 1600px` | `28px x / 21px y` | Same admin rail; no overflow. |
| `/zh/admin/users` | 1440 | `/zh/admin/users` | `1382.4`, `0px` | `1382.4 @ 1600px` | `28px x / 0px y` | Same admin rail; page-local vertical structure; no overflow. |
| `/zh/admin/market-providers` | 1440 | `/zh/admin/market-providers` | `1382.4`, `0px` | `1382.4 @ 1600px` | `28px x / 21px y` | Same admin rail; no overflow. |
| `/zh/settings/system` | 1920 | `/zh/settings/system` | `1850`, `0px` | `1600 @ 1600px` | `28px x / 21px y` | Inner rail clamps at 1600px. |
| `/zh/admin/logs` | 1920 | `/zh/admin/logs` | `1850`, `0px` | `1600 @ 1600px` | `28px x / 21px y` | Inner rail clamps at 1600px. |
| `/zh/admin/users` | 1920 | `/zh/admin/users` | `1850`, `0px` | `1600 @ 1600px` | `28px x / 0px y` | Inner rail clamps at 1600px. |
| `/zh/admin/market-providers` | 1920 | `/zh/admin/market-providers` | `1850`, `0px` | `1600 @ 1600px` | `28px x / 21px y` | Inner rail clamps at 1600px. |

## Rail Contract Verdict

`/zh/settings/system`, `/zh/admin/logs`, `/zh/admin/users`, and `/zh/admin/market-providers` should share one admin/system-control rail contract:

- Route family: `Shell.tsx` owns `system-control` classification and `p-0` main-column behavior.
- Inner rail: `TerminalPageShell` currently owns the 1600px centered page-shell.
- Padding: main padding is zero; inner page-shell horizontal padding is the shared terminal padding; vertical padding can remain page-specific because Admin Users has a different directory/detail workspace rhythm.

This shared contract should be documented by tests before any layout source write. The tests should make the contract explicit without changing runtime behavior.

## Future Write Classification

Future write should be **tests-only**.

Recommended task:

### T-1074-TEST1 Admin rail contract guard

Scope:

- Add focused test coverage proving the four audited routes share the admin/system-control rail contract.
- Assert `Shell` gives admin/system-control routes `shell-content-frame--system-control`, `shell-main-column--system-control`, and `p-0`.
- Assert each audited page renders exactly one visible `data-terminal-primitive="page-shell"` inheriting `max-w-[1600px]`, `mx-auto`, `px-4`, and `xl:px-8`.
- Preserve Admin Users' page-local `0px` vertical shell padding as an allowed exception, rather than forcing `py-5 md:py-6`.
- Keep source, route, auth/RBAC, provider/cache/runtime behavior, shared primitives, and visual tokens unchanged.

Suggested focused validation for that future task:

```bash
npm --prefix apps/dsa-web run test -- src/components/layout/__tests__/Shell.test.tsx src/pages/__tests__/SystemSettingsPage.test.tsx src/pages/__tests__/AdminLogsPage.test.tsx src/pages/__tests__/AdminUsersPage.test.tsx src/pages/__tests__/MarketProviderOperationsPage.test.tsx --run
git diff --check
./scripts/release_secret_scan.sh
```

Not recommended now:

- docs-only follow-up: this artifact already records the policy decision.
- narrow frontend source write: no measured operator harm, overflow, or route instability was found.
- consumer/admin unification: T-1071 and this audit both show the divergence is an inner rail policy difference, not a full app-shell collapse.
- global spacing token migration, shared primitive rewrite, or new Admin Dashboard.

## Boundary Confirmation

Allowed final diff for this audit:

- `docs/codex/audits/T-1074-admin-system-control-rail-policy-write-readiness-audit.md`

Forbidden final diff observed:

- no source changes
- no tests changes
- no config changes
- no package or lockfile changes
- no screenshots or generated assets
- no route/auth/frontend/backend/provider/cache/runtime behavior changes
- no shell/layout fixes implemented

This audit is docs-only.
