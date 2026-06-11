# Admin Mission Control Goal Progress

Status: salvage-fix complete; broader Admin Mission Control v1 incomplete
Date: 2026-06-11
Branch: `codex/goal-admin-mission-control-salvage-fix`
Mode: default-off / prototype-gated admin read-only cockpit. This work must
not approve public launch, enable live enforcement, call providers, send
notifications, run cleanup/restore/migrations, mutate production config, or
change auth behavior.

## Goal

Build Admin Mission Control v1 as a read-only operator cockpit that makes
WolfyStock readiness, evidence, blockers, and system posture visible in one
admin place.

## Hard Boundaries

- Public launch stays **NO-GO**.
- Cockpit output is advisory and read-only.
- All surfaced data must be sanitized or bounded summaries.
- Admin Mission Control is disabled by default and requires explicit prototype
  flags before the route/nav entry or full backend projection is available.
- Disabled default responses do not aggregate provider, quota/cost, storage,
  task-queue, or admin-log summaries.
- No route-boundary quota enforcement, provider circuit enforcement, MFA
  enforcement, notification send, provider live call, database restore,
  cleanup, migration, or production config mutation is introduced.
- Existing admin capability gates remain required on the enabled path; the
  prototype gate is additive and does not change auth/RBAC/session behavior.

## Broad Goal Checkpoints

- [x] `checkpoint(admin): map mission control`
- [ ] `checkpoint(admin): add readiness overview`
- [ ] `checkpoint(admin): add blocker and evidence panels`
- [ ] `checkpoint(admin): add admin smoke evidence`
- [ ] `feat(admin): add mission control v1`

The broad Admin Mission Control v1 is not complete. This document only marks
the bounded salvage-fix slice below as complete.

## Salvage-fix Checkpoints

- [x] Backend default-off prototype gate added.
- [x] Disabled default returns a bounded disabled/prototype response.
- [x] Disabled default does not call `AdminOpsStatusService.build_status()` or
      aggregate high-risk ops summaries.
- [x] Enabled prototype remains admin-only through `ops:logs:read`,
      read-only, advisory, sanitized, and public-launch **NO-GO**.
- [x] Frontend route/nav entry is hidden by default and appears only when
      `VITE_WOLFYSTOCK_ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED=true`.
- [x] Tests cover no mutation, no external calls, no raw IDs/secrets/provider
      payloads/reservation IDs/stack traces/raw diagnostics.

## Prototype Flags

- Backend projection:
  `WOLFYSTOCK_ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED=false` by default.
- Frontend route/navigation advertisement:
  `VITE_WOLFYSTOCK_ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED=false` by default.
- Both flags must be explicitly enabled for the prototype cockpit to be
  advertised in the client and return the full backend projection.

## Source Map

| Domain | Current reusable source | Cockpit posture label |
| --- | --- | --- |
| Security / RBAC / MFA | `docs/audits/index-security-rbac-mfa.md`, `docs/audits/public-launch-readiness-master.md`, admin capability flags | Landed foundation; real operator evidence missing; approval required; public-launch NO-GO |
| Quota / cost | `GET /api/v1/admin/cost/*`, `GET /api/v1/admin/ops/status`, quota dry-run estimate only | Evidence tooling exists; approval required; no live enforcement |
| Provider reliability | `GET /api/v1/admin/providers/*`, `GET /api/v1/admin/market-providers/operations`, operations matrix | Evidence tooling exists; real operator evidence missing; no provider blocking |
| Storage / restore | `GET /api/v1/admin/ops/status`, restore/PITR docs and validators | Evidence tooling exists; real restore evidence missing; public-launch NO-GO |
| WS2 / async | `GET /api/v1/admin/ops/status`, WS2 docs and smoke helpers | Landed foundation; real multi-instance evidence missing; public-launch NO-GO |
| Notifications | `GET /api/v1/admin/notification-channels`, `GET /api/v1/admin/notifications` | Landed foundation; delivery rehearsal evidence missing; no sends |
| Portfolio / backtest | Admin portfolio read APIs, backtest readiness docs and fixtures | Landed foundation; remaining owner-isolation and safety evidence missing |
| Route classification | RBAC route inventory fixtures and auth route tests | Evidence tooling exists; approval required before fallback removal |
| Private-beta readiness | readiness smoke docs/tests and launch master | Evidence tooling exists; public-launch NO-GO |

## Current Implementation Shape

- Keep a dedicated admin cockpit route under `/admin/mission-control`, but
  default it to a disabled prototype response and hide the frontend nav/route
  entry unless the explicit prototype gate is enabled.
- Reuse existing terminal/admin primitives, L0 overview strip, and drill-through
  patterns from existing admin operations pages.
- The enabled backend projection may aggregate sanitized read-only ops summary
  sections. The disabled default must not aggregate them.
- Keep the backend DTO additive, sanitized, read-only, admin-only, and
  capability-gated when explicitly enabled.

## Validation Evidence

- `PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m pytest -p no:cacheprovider tests/api/test_admin_mission_control.py -q`
  - 2026-06-11: **5 passed**.
- `PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m py_compile api/v1/endpoints/admin_mission_control.py api/v1/schemas/admin_mission_control.py src/services/admin_mission_control_service.py`
  - 2026-06-11: **passed**.
- `npm --prefix apps/dsa-web run test -- src/pages/__tests__/AdminMissionControlPage.test.tsx src/__tests__/AppRoutes.test.tsx src/components/layout/__tests__/Shell.test.tsx`
  - 2026-06-11: **3 files passed, 164 tests passed**.
- `npm --prefix apps/dsa-web run typecheck`
  - 2026-06-11: **passed** (`tsc -b --pretty false`).
- `npm --prefix apps/dsa-web run build`
  - 2026-06-11: **passed** (`vite build`, existing chunk-size warning only).
- `WOLFYSTOCK_ADMIN_OPS_ROUTE_FILTER=mission-control DSA_WEB_PLAYWRIGHT_PORT=4232 npm --prefix apps/dsa-web run test:e2e -- admin-ops-launch-surfaces.spec.ts --project=chromium --workers=1`
  - 2026-06-11: **2 passed**.
- `git diff --check`
  - 2026-06-11: **passed** for the working tree.
- `./scripts/release_secret_scan.sh`
  - 2026-06-11: **passed**, no high-confidence secret patterns found.
- `git diff --check origin/main..HEAD`
  - 2026-06-11: **passed** after commit.
- `git status --short --branch`
  - 2026-06-11 after commit: branch was ahead by 1 with no working-tree
    changes before this evidence update.

## Progress Log

### 2026-06-11 - Map mission control

- Confirmed existing admin routes for logs, evidence workflow, notifications,
  market providers, provider circuits, users, and cost observability.
- Confirmed `AdminOpsStatusService` already aggregates read-only provider,
  quota/cost, storage, task queue, and admin-log evidence summaries with
  `readOnly=true`, `noExternalCalls=true`, and `liveEnforcement=false`.
- Initial decision: build a cockpit view that separates landed foundations,
  evidence tooling, missing real operator evidence, approval requirements, and
  public-launch NO-GO without adding any runtime controls.

### 2026-06-11 - Salvage-fix default-off prototype gate

- Added backend `prototypeGate` metadata and a disabled default response for
  `/api/v1/admin/mission-control`.
- Confirmed the disabled default does not aggregate provider, quota/cost,
  storage, task-queue, or admin-log summaries.
- Added frontend gating so Mission Control is not advertised by default in
  admin navigation and direct route access does not render the cockpit unless
  the client prototype flag is enabled.
- Kept the explicitly enabled path admin-only, read-only, advisory, sanitized,
  and public-launch **NO-GO**.
- This salvage-fix does not complete the broader Admin Mission Control v1 goal.
