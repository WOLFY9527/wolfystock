# Admin RBAC R5 Coarse Fallback Removal Plan

Status: Deferred
Owner domain: Admin RBAC and security governance
Related docs: `docs/audits/admin-rbac-capability-model-design.md`, `docs/audits/public-launch-gap-register.md`

Date: 2026-05-07
Mode: docs-only migration and governance plan. No runtime behavior changed.

## Scope

This document plans the eventual RBAC R5 removal of coarse admin fallback after
R3, R3b, R4A, R4B, and final QA. It does not remove fallback, migrate routes,
change frontend navigation, change tests, implement MFA, expand recent reauth,
add role-management UI, or modify Options, Data Pipeline, Provider Circuit,
Cost/Quota, scanner, backtest, portfolio, notification, DuckDB, broker/order,
AI/provider routing, or Security MFA/KDF runtime behavior.

R5 should be treated as a production governance migration, not a mechanical
helper cleanup. The existing coarse admin compatibility remains intentional
until capability inventory, role assignment, audit, frontend fail-closed
behavior, and rollback controls are proven.

## 1. Current fallback behavior

WolfyStock currently has two admin authorization paths:

- Coarse admin identity: `role == "admin"` or resolved `is_admin` continues to
  satisfy legacy admin checks through `require_admin_user()`.
- Capability expansion: existing coarse admins expand to super-admin-equivalent
  capabilities through `expand_admin_capabilities(user)` and
  `has_admin_capability(user, capability)`.

This compatibility exists for three reasons:

- Existing bootstrap/local admin deployments still use the coarse admin role.
- The route surface was migrated in phases, so some routes now use capability
  helpers while adjacent admin routes still depend on `require_admin_user()`.
- The production governance layer is incomplete: MFA enforcement, broad recent
  reauth, role assignment UI, capability mutation audit, and fail-closed audit
  policy are not fully in place.

R5 removal means coarse admin status should no longer silently grant every admin
capability. After removal, a user should be authorized by explicit persisted
role/capability assignment, with bootstrap and emergency access handled by a
documented governance path.

## 2. Capability-guarded route families

The following route families already use capability guards and were covered by
the RBAC final QA:

| Route family | Guard capability |
| --- | --- |
| Admin user security writes: disable, enable, revoke sessions | `users:security:write` |
| Admin portfolio visibility reads: summary, holdings, activity, account detail | `users:portfolio:read` |
| Admin log reads, sessions, event details, storage summary | `ops:logs:read` |
| Admin log cleanup | `ops:logs:write` |
| System config read, schema, validation | `ops:system_config:read` |
| System config writes, runtime cache reset, factory reset | `ops:system_config:write` |
| LLM and data-source probes | `ops:providers:write` |
| Notification/channel reads | `ops:notifications:read` |
| Notification channel writes/tests and notification acknowledgement | `ops:notifications:write` |

R4A also exposes sanitized current-user capability summaries, and R4B consumes
those fields for frontend capability-aware navigation/actions. Backend route
guards remain the authorization source of truth.

## 3. Remaining coarse-admin-only areas

Before fallback removal, every admin surface must be inventoried and classified
as explicit capability-guarded, intentionally public/non-admin, or intentionally
retired. Known remaining coarse-admin-only or compatibility-sensitive areas
include:

- Admin user directory/detail and activity reads not yet migrated to
  `users:read`, `users:activity:read`, or scoped `ops:logs:read`.
- Admin cost observability routes that should require
  `cost:observability:read`.
- Admin market provider operation reads that should require
  `ops:providers:read`.
- Scanner admin operation reads that should require `scanner:admin:read`.
- Optional DuckDB/quant admin reads and writes that should require
  `quant:admin:read` or `quant:admin:write`.
- Any future backtest/admin dashboard routes that should require
  `backtest:admin:read`.
- Any future Options admin surface that should require a separately designed
  `options:admin:read` policy before implementation.
- Frontend entry points that still depend on coarse admin presence for nearby
  or future admin surfaces.
- Transitional auth-disabled local admin paths that need an explicit dev-only
  bootstrap policy.

This list must be refreshed from code before implementation because new admin
routes may have landed after this plan.

## 4. Required capability inventory

R5 needs a route-by-route inventory before any fallback removal patch:

| Inventory item | Required evidence |
| --- | --- |
| Backend route map | Endpoint, HTTP method, current dependency, target capability, sensitivity tier, reason requirement, reauth requirement, audit requirement. |
| Frontend route/action map | Page, tab, action, required auth contract field, hidden/disabled behavior, API calls suppressed when denied. |
| Role mapping | Built-in role to capability mapping for `super-admin`, `security-admin`, `support-admin`, and `ops-admin`. |
| Existing user migration | Count of coarse admins, proposed target role assignment, bootstrap/emergency owner, and users with no explicit role rows. |
| Denial contract | 401/403 reason codes and sanitized error payloads for missing capability, missing MFA, stale reauth, and audit failure. |
| Audit contract | Allow/deny/write/sensitive-read events, safe metadata allowlist, fail-closed route list, and reviewer workflow. |
| Bootstrap contract | How first super-admin is created, how last-super-admin protection is enforced, and how auth-disabled dev mode is bounded. |

The inventory should be generated or reviewed close to implementation time and
attached to the R5 PR description. Stale inventory should block removal.

## 5. Governance requirements

Fallback removal requires explicit admin role/capability governance:

- `super-admin` remains the only role with full administrative authority and
  must be protected by last-super-admin guardrails.
- `security-admin`, `support-admin`, and `ops-admin` must receive only the
  capabilities required for their operational duties.
- Role and capability grants must require actor identity, reason, timestamp,
  target user, capability/role key, outcome, and safe request/session handle.
- Role changes, capability overrides, break-glass use, denied changes, and
  failed audit writes must be reviewable.
- Per-user overrides, if introduced, must have expiry, approver, reason, and
  audit evidence. They should not become the default access model.
- Bootstrap and emergency access must be documented before production fallback
  removal.
- Auth-disabled transitional local admin behavior must not become a production
  bypass.

## 6. Migration sequence

### Phase R5.1: observe

- Keep coarse admin compatibility enabled.
- Add safe observability that records when access was granted only because of
  coarse admin fallback.
- Report route family, required capability, actor safe handle, source surface,
  and outcome without logging secrets, raw sessions, cookies, tokens, provider
  payloads, prompt text, `.env` values, or role inventory.
- Build an admin-only report that shows fallback dependence by route family and
  user.

Exit criteria:

- No sensitive route lacks an explicit target capability.
- Fallback-only grants are known and owned.
- Audit events are sanitized and reviewable.

### Phase R5.2: warn

- Keep fallback enabled.
- Add clear admin-facing warning for users who depend on fallback-only access.
- Add operational warnings in logs/audit summaries for fallback-only grants.
- Publish migration instructions for assigning explicit built-in roles.

Exit criteria:

- Every active coarse admin has an explicit target role assignment plan.
- Warnings do not expose capability inventory or sensitive target details to
  unauthorized users.
- Support/security/ops role owners have reviewed their intended access.

### Phase R5.3: dual-run

- Evaluate both explicit capability authorization and legacy fallback.
- Continue allowing fallback, but record whether explicit capability would have
  allowed or denied the request.
- Fail closed only for routes already selected for pilot enforcement and only
  after rollback is prepared.

Exit criteria:

- Dual-run results show no unexpected deny for intended super-admin,
  security-admin, support-admin, or ops-admin workflows.
- Frontend fail-closed states are proven for missing capability fields.
- Denied responses remain sanitized.

### Phase R5.4: fail-closed pilot

- Select a narrow non-destructive route family first, preferably read-only and
  already covered by frontend gating.
- Disable fallback for that family behind an explicit, reversible deployment
  switch or migration flag.
- Keep emergency super-admin recovery and last-super-admin checks active.

Exit criteria:

- Legacy coarse admin without explicit capabilities is denied on the pilot
  route.
- Explicit capability admin is allowed.
- Support/security/ops split behaves as designed.
- Audit allow/deny evidence is complete and sanitized.
- Rollback has been exercised in staging or a local equivalent.

### Phase R5.5: remove fallback

- Remove coarse-admin-to-super-admin-equivalent expansion as an authorization
  source after all route families are explicit and pilot results are accepted.
- Preserve `role == "admin"` only as historical metadata or migrate it to an
  explicit `super-admin` role row before removal.
- Remove or narrow compatibility branches in tests and docs.
- Keep frontend capability-aware navigation fail-closed for missing capability
  fields.

Exit criteria:

- No production route uses coarse admin fallback for authorization.
- All active admin users have explicit role/capability authority.
- Bootstrap, break-glass, rollback, and last-super-admin workflows are tested.
- Audit review confirms no sensitive denial or grant leakage.

## 7. Rollback strategy

Rollback must be prepared before the first fail-closed pilot:

- Keep a reversible flag or config switch for pilot route fallback enforcement
  until full removal is complete.
- Preserve database role/capability rows when rolling back enforcement; do not
  delete grants as part of rollback.
- If an admin lockout occurs, restore compatibility only for the affected route
  family and only long enough to assign explicit roles.
- Maintain a documented bootstrap super-admin recovery path that does not
  expose secrets or raw session data.
- Re-run the denied-sanitization and frontend fail-closed checks after rollback
  to verify the system did not reopen broad data exposure.

After full removal, rollback should prefer restoring explicit role assignments
or the reversible enforcement flag. Reintroducing global coarse-admin
super-admin equivalence should require a production incident decision and a
follow-up removal deadline.

## 8. Test matrix

R5 implementation should include backend, frontend, and browser/API tests for:

| Case | Expected result |
| --- | --- |
| Legacy admin without explicit role rows | Allowed during observe/warn/dual-run; denied in fail-closed pilot/removal for selected routes. |
| Legacy admin migrated to explicit `super-admin` | Allowed on all admin surfaces, subject to MFA, reauth, reason, audit, and last-super-admin policies. |
| Capability admin with one required capability | Allowed only on matching route/action family. |
| `security-admin` | Can read user/security scope and perform security writes only when reason, reauth, MFA policy, and audit requirements pass; cannot read portfolio by default. |
| `support-admin` | Can read safe support user/activity projections; cannot perform security writes, portfolio detail reads, config writes, provider probes, or role changes by default. |
| `ops-admin` | Can read/write approved operational route families; cannot read user portfolio or perform user security writes by default. |
| Non-admin authenticated user | Denied on every admin route without role/capability leakage. |
| Unauthenticated user | Receives unauthorized response without role/capability leakage. |
| Denied sanitization | Responses, logs, audit metadata, and frontend DOM do not expose password hashes, raw sessions, cookies, tokens, API keys, secrets, broker/provider credentials, webhook URLs, `.env` values, tracebacks, role inventory, or capability inventory. |
| Frontend missing capability fields | Fails closed, hides blocked routes/actions, and does not fetch protected APIs. |
| Frontend capability mismatch | Backend denial is handled without rendering protected data from stale cache or hidden DOM. |
| Audit fail-closed routes | Security writes, role changes, sensitive reads, destructive cleanup, factory reset, and break-glass paths deny when required audit persistence fails. |
| Rollback flag | Restores pilot compatibility for the selected route family without deleting explicit role assignments. |

## 9. Production blockers

R5 should not remove global coarse fallback in production until these blockers
are closed or explicitly risk-accepted:

- MFA enforcement for admin accounts, including enrollment, verification,
  recovery-code policy, and production secret storage.
- Recent reauth expansion beyond the current admin user security write pilot to
  config writes, notification writes/tests, provider probes, destructive
  cleanup/reset, role/capability mutation, and sensitive reads selected by
  policy.
- Role management UI or operational workflow for assigning, reviewing,
  revoking, and expiring admin roles/capabilities.
- Audit review workflow for fallback-only grants, denied attempts,
  role/capability changes, break-glass use, sensitive reads, writes, and audit
  persistence failures.
- Route inventory showing no remaining unclassified admin surface.
- Frontend/browser evidence that capability-gated surfaces fail closed and do
  not optimistically fetch forbidden APIs.

## 10. Recommended next implementation prompts

1. `Task: RBAC R5 inventory report only`
   Create a docs-only route/frontend/admin-user capability inventory for R5.
   Do not change runtime code, frontend code, tests, or changelog unless clean.

2. `Task: RBAC R5 observe-mode fallback telemetry`
   Add sanitized audit/observability for requests allowed only by coarse admin
   fallback. Keep authorization behavior unchanged and do not remove fallback.

3. `Task: RBAC role assignment governance design`
   Design the role-management UI/API and audit workflow required before R5
   fail-closed enforcement. Do not implement runtime role mutation.

4. `Task: RBAC R5 dual-run backend pilot`
   For one named route family, evaluate explicit capability and fallback in
   parallel, record sanitized would-allow/would-deny evidence, and keep fallback
   behavior unchanged.

5. `Task: RBAC R5 fail-closed pilot`
   Disable fallback for one approved route family behind a reversible switch,
   with tests for legacy admin denial, explicit capability allowance,
   support/security/ops split, denied sanitization, frontend fail-closed state,
   audit evidence, and rollback.

6. `Task: RBAC R5 final fallback removal`
   Remove global coarse admin capability expansion only after inventory,
   governance, MFA/reauth, frontend, audit, pilot, and rollback evidence are
   accepted.
