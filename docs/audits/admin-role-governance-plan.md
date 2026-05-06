# Admin Role Governance Plan

Date: 2026-05-07
Branch checked: `main`
Mode: docs-only role governance plan. No runtime auth, RBAC, schema, frontend,
tests, Options, Data Pipeline, cost/quota, provider circuit, or MFA behavior was
changed.

## 1. Purpose

This plan defines the target admin role governance model required before
WolfyStock can safely remove coarse admin fallback. It builds on the existing
capability model, RBAC final QA, R5 fallback-removal plan, and public deployment
readiness checklist.

The goal is not to add a new authorization path in this task. The goal is to
make the production governance contract explicit enough that a future
implementation can assign, review, revoke, and audit admin authority without
silently granting every capability to every coarse admin.

## 2. Target role families

Admin roles should be role families that map to explicit capability bundles.
Backend route guards should continue to authorize by capability, not by
hard-coded role-name checks.

| Role family | Primary purpose | Default posture |
| --- | --- | --- |
| `owner` / `super-admin` | Owns bootstrap, emergency recovery, role governance, final production admin decisions, and every admin capability. | Full authority, but still subject to MFA, recent reauth, reason prompts, audit, and last-admin protection. |
| `security-admin` | Manages account security, session revocation, disable/enable actions, future MFA/lockout state, and security audit review. | Security and user-governance authority only; no portfolio/cost/provider/config authority by default. |
| `ops-admin` | Operates logs, system health, masked config, notifications, provider operations, scanner/backtest/quant admin diagnostics where approved. | Operational authority only; no user portfolio or security-write authority by default. |
| `provider-admin` | Owns provider diagnostics, connectivity probes, data-source health review, and future provider-operation pilots. | Provider diagnostics and probe authority only; no broad system config, user security, portfolio, or cost authority by default. |
| `cost-observability-admin` | Reviews LLM usage, duplicate-cost summaries, quota dry-run outputs, and future budget dashboards. | Cost observability read authority only; no policy enforcement or user-sensitive drilldown unless separately approved. |
| `support` / `read-only-admin` | Supports users through safe profile, activity, and limited diagnostic views. | Read-only, redacted, least-privilege support access; no security writes, role changes, full portfolio detail, config writes, provider probes, or secret exposure. |

`owner` and `super-admin` can be treated as the same production role family. If
both labels are used in UI copy, `owner` should mean the human accountability
role and `super-admin` should mean the persisted built-in role key.

## 3. Capability bundles

Capability bundles should be named around work surfaces, but persisted grants
should remain individual capabilities so future route guards can stay precise.

### User governance bundle

- `users:read`: safe user directory and detail projections.
- `users:activity:read`: safe user/global activity timelines.
- `users:security:read`: user account/security/session state.
- `users:security:write`: disable, enable, session revocation, and future
  security-state writes.
- `users:portfolio:read`: sensitive portfolio projections, holdings, activity,
  and account detail.

Default assignment:

- `super-admin`: all user capabilities.
- `security-admin`: `users:read`, `users:activity:read`,
  `users:security:read`, `users:security:write`.
- `support/read-only-admin`: `users:read` and redacted
  `users:activity:read`; portfolio requires explicit time-bounded approval.
- `ops-admin`, `provider-admin`, `cost-observability-admin`: no user-governance
  capability by default.

### Ops bundle

- `ops:logs:read`: operational execution logs, sessions, storage summary, and
  sanitized diagnostics.
- `ops:logs:write`: log retention cleanup or storage actions.
- `ops:system_config:read`: masked config and schema metadata.
- `ops:system_config:write`: config writes, runtime cache reset, factory reset,
  and other system actions.
- `ops:providers:read`: provider operations and status diagnostics.
- `ops:providers:write`: provider probes and provider-affecting operational
  actions.
- `ops:notifications:read`: notification events and channel status.
- `ops:notifications:write`: channel create/update/delete/test and
  acknowledgement actions.

Default assignment:

- `super-admin`: all ops capabilities.
- `ops-admin`: ops logs, masked config, provider, notification, and approved
  operational write capabilities with reauth/MFA where required.
- `provider-admin`: `ops:providers:read` and `ops:providers:write` only.
- `security-admin`: security-scoped audit/log and notification visibility only
  when policy defines the scope.
- `support/read-only-admin`: no ops bundle by default; only support-safe links
  with redacted detail if separately approved.

### Cost observability bundle

- `cost:observability:read`: duplicate-cost summaries, LLM usage summaries,
  quota dry-run observations, and future budget dashboards.

Default assignment:

- `super-admin`: allowed.
- `cost-observability-admin`: allowed.
- `ops-admin`: allowed when operational cost monitoring is part of the role.
- All other role families: denied by default.

Cost observability must remain read-only until a separate quota/cost policy
implementation task approves live enforcement, budget changes, or quota writes.

### Provider diagnostics bundle

- `ops:providers:read`: provider status and diagnostics.
- `ops:providers:write`: bounded connectivity probes and custom-source tests.

Default assignment:

- `super-admin`: allowed.
- `provider-admin`: allowed.
- `ops-admin`: allowed if provider operations are part of ops duty.
- `security-admin`, `support/read-only-admin`,
  `cost-observability-admin`: denied by default.

Provider diagnostics must not expose raw provider payloads, URLs with query
strings, credentials, cookies, raw session ids, exception text, stack traces, or
internal storage details.

## 4. Assignment rules

### Least privilege

- Assign the smallest role family that satisfies the operational duty.
- Prefer built-in role families over per-user overrides.
- Use per-user capability overrides only for time-bounded exceptions with
  approver, reason, expiry, and audit evidence.
- Expired overrides must fail closed and remain visible in audit history.
- Support roles should begin with aggregate or redacted views and require a
  reason before target-user drilldown.

### Separation of duties

- User security writes and system/provider operations should not be bundled
  together except for `super-admin`.
- Cost observability should be independently assignable from provider probes
  and system config writes.
- Provider diagnostics should not imply system config write authority.
- Support/read-only access should not imply security writes, portfolio detail,
  role management, provider probes, or config writes.
- Break-glass access should be separate from day-to-day admin roles and should
  create high-priority audit evidence.

### Last-admin protection

- The system must prevent disabling, demoting, deleting, locking, expiring, or
  revoking all usable `super-admin` / owner access.
- Last-admin checks must consider active role assignments, account disabled
  state, session/MFA usability, expiry, and break-glass availability.
- Self-destructive actions should be blocked unless a separately designed safe
  recovery flow exists.
- Role revocation workflows must show whether the target user is the last
  usable owner before confirmation.

### Break-glass account policy

- Production should maintain at least one documented break-glass owner path
  before coarse fallback removal.
- Break-glass credentials must not be stored or displayed in admin UI.
- Break-glass use should require MFA or an approved recovery-control equivalent
  once MFA is production-ready.
- Break-glass sessions should have the shortest timeout, require a reason, and
  be visible in audit review.
- Every break-glass use should trigger follow-up review and a rotation or
  re-sealing checklist.

## 5. Approval and audit workflow

### Who can grant or revoke

| Change type | Minimum actor authority | Additional requirement |
| --- | --- | --- |
| Grant/revoke `super-admin` / owner | Existing `super-admin` | Recent reauth, MFA, reason, last-admin check, audit fail-closed. |
| Grant/revoke `security-admin` | `super-admin`; future delegated security governance only after policy approval | Recent reauth, MFA, reason, audit. |
| Grant/revoke `ops-admin` | `super-admin` | Recent reauth, MFA, reason, audit. |
| Grant/revoke `provider-admin` | `super-admin` or approved `ops-admin` with role-management capability | Recent reauth, MFA, reason, audit. |
| Grant/revoke `cost-observability-admin` | `super-admin` or approved ops/cost governance actor | Reason and audit; reauth/MFA in production. |
| Grant/revoke `support/read-only-admin` | `super-admin`; future delegated support governance only after policy approval | Reason and audit; MFA in production. |
| Add per-user override | `super-admin` by default | Expiry, reason, approver, recent reauth, MFA, audit. |
| Revoke per-user override | `super-admin` or owning governance actor | Reason and audit. |

Future implementation should avoid granting role-management authority to every
admin. A separate `roles:manage` or equivalent capability may be needed, but it
must not be implemented as part of this docs-only task.

### Required audit fields

Role and capability audit events should include only safe metadata:

- event id and timestamp;
- actor user id or stable safe handle;
- target user id or stable safe handle;
- action type: grant, revoke, expire, override, deny, approve, break-glass use;
- role key or capability key;
- old state and new state as bounded labels;
- outcome and denial reason code;
- reason category and bounded reason text;
- approver id when separate approval exists;
- expiry timestamp for temporary grants;
- request id or hashed request/session handle;
- source surface: API, UI, CLI, bootstrap, break-glass;
- audit persistence status.

Audit events must not contain passwords, password hashes, raw sessions, cookies,
tokens, API keys, provider credentials, broker credentials, webhook URLs, raw
provider payloads, raw prompts, raw request bodies, stack traces, `.env` values,
or raw role/capability inventory beyond the specific action being audited.

### Reason requirement

Reason is required for:

- any role grant, revocation, expiry change, or override;
- security writes;
- portfolio detail reads;
- target-user activity drilldowns;
- admin audit detail reads;
- destructive cleanup, reset, or config write actions;
- provider probes and notification channel tests;
- break-glass access.

Reason should include a bounded category plus a short free-text note. Empty,
placeholder, or overly long reasons should be rejected. Reason text is audit
metadata and must be treated as potentially user-visible operational evidence.

### Recent reauth and MFA requirement

Production role management must require:

- active authenticated admin session;
- MFA enrollment and successful MFA verification once MFA enforcement is ready;
- recent reauth before role/capability mutation, owner changes, break-glass
  actions, security writes, destructive operational actions, and selected
  sensitive reads;
- stale reauth denial that does not expose role inventory or session internals.

Until MFA runtime enforcement is implemented and piloted, role-management
implementation should remain blocked or local/staging-only.

## 6. Production blockers

Coarse fallback removal and production role management remain blocked until all
of the following are closed or explicitly risk-accepted:

- MFA enforcement for admin accounts, including production TOTP secret storage,
  recovery codes, staged enrollment, verification, and rollback policy.
- Role management UI and API that can assign, revoke, expire, and review roles
  without exposing secrets, sessions, tokens, or raw role inventory to
  unauthorized users.
- Audit review workflow for grants, revocations, denied attempts, fallback-only
  grants, break-glass use, sensitive reads, writes, and audit persistence
  failures.
- Recent reauth coverage for role/capability mutation and high-impact admin
  actions beyond the current narrow security-write pilot.
- Coarse fallback removal gates from the R5 plan: complete route inventory,
  explicit role assignments for active admins, frontend fail-closed browser
  evidence, sanitized denial/audit evidence, pilot rollback evidence, and
  last-admin/break-glass proof.

## 7. Implementation boundary for this task

This document is a prerequisite plan only.

Do not implement from this task:

- runtime auth or RBAC behavior;
- role/capability mutation APIs;
- frontend role-management screens;
- schema or migration changes;
- tests;
- Options, Data Pipeline, provider circuit, cost/quota, portfolio, scanner,
  backtest, notification delivery, broker/order, or MFA runtime changes.
