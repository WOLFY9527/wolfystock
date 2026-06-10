# Admin Mission Control Goal Progress

Status: in progress
Date: 2026-06-11
Branch: `codex/goal-admin-mission-control`
Mode: additive admin read-only cockpit. This work must not approve public
launch, enable live enforcement, call providers, send notifications, run
cleanup/restore/migrations, mutate production config, or change auth behavior.

## Goal

Build Admin Mission Control v1 as a read-only operator cockpit that makes
WolfyStock readiness, evidence, blockers, and system posture visible in one
admin place.

## Hard Boundaries

- Public launch stays **NO-GO**.
- Cockpit output is advisory and read-only.
- All surfaced data must be sanitized or bounded summaries.
- No route-boundary quota enforcement, provider circuit enforcement, MFA
  enforcement, notification send, provider live call, database restore,
  cleanup, migration, or production config mutation is introduced.
- Existing admin capability gates remain the only access boundary.

## Checkpoints

- [ ] `checkpoint(admin): map mission control`
- [ ] `checkpoint(admin): add readiness overview`
- [ ] `checkpoint(admin): add blocker and evidence panels`
- [ ] `checkpoint(admin): add admin smoke evidence`
- [ ] `feat(admin): add mission control v1`

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

- Add a dedicated admin cockpit route under `/admin/mission-control`.
- Reuse existing terminal/admin primitives, L0 overview strip, and drill-through
  patterns from existing admin operations pages.
- Prefer frontend aggregation of existing read-only APIs first. Add backend
  projection only if a required posture cannot be represented safely from
  existing responses and docs-derived static cockpit metadata.
- Keep any new backend DTO additive, sanitized, read-only, and admin-only.

## Validation Plan

- Backend touched: run targeted pytest and `python -m py_compile` for changed
  backend files.
- Frontend touched: run targeted Vitest for the new page, route tests,
  typecheck, and production build.
- Smoke: run bounded admin Playwright smoke for `/admin/mission-control`.
- Safety: run `git diff --check` and repository secret scan.

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
