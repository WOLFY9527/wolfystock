# Admin Role Management UI Design

Date: 2026-05-07
Branch checked: `main`
Mode: docs-only UI design. No runtime auth, RBAC, schema, frontend, tests,
Options, Data Pipeline, cost/quota, provider circuit, or MFA behavior was
changed.

## 1. Purpose

This document designs the future admin role and capability management UI needed
before coarse admin fallback can be removed. It does not implement UI, APIs,
schema, tests, MFA runtime, or authorization changes.

The UI must make admin authority reviewable and safely assignable without
turning role management into another broad admin bypass. Backend route guards
remain the source of truth; frontend controls are workflow and safety aids.

## 2. Read-only role and capability inventory view

The first UI surface should be read-only. It should help owners understand the
current model before any mutation flow exists.

Required sections:

- Role families: `super-admin`, `security-admin`, `ops-admin`,
  `provider-admin`, `cost-observability-admin`, and `support/read-only-admin`.
- Capability bundles: user governance, ops logs/system config/providers/
  notifications, cost observability, and provider diagnostics.
- Built-in role mapping: role family to capability keys with clear allowed,
  denied, optional, and time-bounded override states.
- Route family coverage: high-level route family labels and target
  capabilities, not raw route internals for unauthorized viewers.
- Production readiness warnings: MFA not enforced, role mutation absent,
  audit-review workflow absent, and coarse fallback still present until R5
  gates pass.
- Current viewer authority: the viewer's own sanitized capability summary and
  whether role management is available, pending, or blocked.

The inventory view must not expose:

- passwords or password hashes;
- raw session ids, cookies, or tokens;
- API keys, provider credentials, broker credentials, webhook URLs, or `.env`
  values;
- raw role/capability inventory to users who lack role-governance authority;
- raw request bodies, raw provider payloads, raw prompts, stack traces, or
  secret-bearing diagnostics.

## 3. User capability assignment flow

The future assignment flow should be explicit and review-first.

Recommended flow:

1. Select a target user from a safe admin user projection.
2. Show current effective roles, temporary overrides, expiry dates, and blocked
   states using sanitized labels.
3. Show recommended role families rather than raw per-capability toggles as the
   primary path.
4. Show capability delta before submission: added roles, removed roles, added
   capabilities, removed capabilities, new expiry, and affected sensitive
   surfaces.
5. Require reason category and bounded reason text.
6. Require recent reauth and MFA verification before submit.
7. Re-check last-admin and self-destructive-action guards at submit time.
8. Submit to backend role-management API only after backend confirms all
   policy requirements.
9. Show success or denial using sanitized reason codes and audit event id.

Per-user overrides should be a secondary advanced flow:

- default to disabled unless policy allows overrides;
- require expiry;
- require approver and reason;
- show a warning that overrides are exceptions, not normal access design;
- expose active and expired overrides in audit review.

The UI must not optimistically update protected access. After assignment, it
should refresh the current user's auth/capability contract and target-user role
summary from backend responses.

## 4. Dangerous action confirmations

Dangerous actions require stronger confirmation than ordinary role edits.

Dangerous actions include:

- granting or revoking `super-admin` / owner;
- demoting, disabling, or expiring an owner;
- revoking the acting admin's own role or sessions;
- creating or using break-glass access;
- granting portfolio visibility;
- granting security-write authority;
- granting system config write authority;
- granting provider probe authority;
- adding any per-user override;
- removing the last usable role-management actor.

Confirmation requirements:

- show the exact target user display label and stable safe handle;
- show the role/capability delta;
- show whether the action affects owner count or break-glass readiness;
- require typed confirmation for owner, break-glass, and last-admin-adjacent
  changes;
- require reason category and bounded reason text;
- require recent reauth and MFA before final submit;
- make backend denial authoritative, including stale capability state or
  last-admin changes between review and submit.

Confirmation screens must not display raw sessions, tokens, cookies, secret
values, provider credentials, broker credentials, or unmasked config.

## 5. Recent reauth and MFA requirements

The UI should treat recent reauth and MFA as prerequisites, not optional
warnings.

Required behavior:

- If MFA is required but not enrolled, block role mutation and route the admin
  to the approved MFA enrollment/recovery flow once that flow exists.
- If MFA is enrolled but not recently verified, request MFA verification before
  mutation.
- If recent reauth is stale or missing, request reauth before mutation.
- If either check fails, keep the role mutation draft local only and do not
  submit the change.
- If backend reports stale auth after submit, discard privileged response data,
  show a sanitized denial, and require the admin to restart the final
  confirmation step.

This design depends on future MFA and reauth runtime support. It should not be
implemented as a UI-only bypass.

## 6. Frontend fail-closed behavior

The role-management UI must fail closed whenever authorization evidence is
missing, stale, contradictory, or denied by the backend.

Fail-closed rules:

- Missing current-user capability fields mean no role-management UI.
- Missing role-management authority means read-only inventory at most.
- Missing MFA/reauth status means mutation disabled.
- Missing target-user role summary means no edit form.
- Backend 401/403 clears protected draft results and displays sanitized denial.
- Hidden tabs and disabled actions must not fetch protected role, session,
  portfolio, provider, config, or audit APIs.
- Stale cached role data must not be rendered after a denial.
- Capability mismatch between frontend and backend must prefer backend denial.

For mixed-authority pages, resolve access separately by view and action. A
support/read-only admin may see safe user profile context while security,
portfolio, role mutation, and raw audit details remain unavailable.

## 7. Browser verification scenarios

Before implementation can be considered ready, browser verification should
cover desktop and narrow/mobile viewports with isolated local servers when
possible.

Required scenarios:

| Scenario | Expected browser result |
| --- | --- |
| Full `super-admin` with MFA and recent reauth | Sees inventory, assignment flow, dangerous confirmations, and sanitized audit event ids after successful mutation. |
| `security-admin` without role-management authority | Sees security-relevant admin surfaces but no role mutation controls. |
| `ops-admin` | Sees ops/admin capability context but cannot grant user security, portfolio, or owner roles. |
| `provider-admin` | Sees provider diagnostics capability context only; no cost, system config, user security, portfolio, or owner role mutation. |
| `cost-observability-admin` | Sees cost observability context only; no provider probes, system config, user security, portfolio, or owner role mutation. |
| `support/read-only-admin` | Sees read-only/redacted support context only; no security writes, role mutation, portfolio detail, config writes, or provider probes. |
| Non-admin authenticated user | Cannot open role inventory or mutation routes; no role/capability inventory leaks in DOM or network responses. |
| Missing capability fields | Fails closed; no role-management API fetches and no protected controls rendered. |
| Stale reauth | Mutation controls require reauth and do not submit until backend accepts a fresh marker. |
| MFA not enrolled or not verified | Mutation blocked with sanitized guidance; no role change request sent. |
| Last-admin revocation attempt | Confirmation is blocked or backend denial is shown; no optimistic demotion state persists. |
| Backend denial after optimistic capability mismatch | Protected data is cleared, denied state is shown, and hidden DOM does not contain role details. |

Browser checks should verify:

- no protected API calls occur for hidden or denied controls;
- no console/page errors on the role-management routes;
- no horizontal overflow or unusable confirmation layouts on narrow viewports;
- no forbidden text or secret-bearing values appear in DOM snapshots;
- audit event ids and denial reason codes are bounded and sanitized.

## 8. Secret, session, and token exposure policy

The UI must never display, store in client-visible state, copy, log, or expose
through DOM attributes:

- passwords or password hashes;
- raw session ids, cookies, tokens, or CSRF-like values;
- API keys, provider credentials, broker credentials, webhook URLs, private
  keys, or `.env` values;
- raw provider payloads, raw prompts, raw LLM responses, raw request bodies, or
  stack traces;
- raw role mapping internals beyond the sanitized role/capability labels the
  viewer is authorized to see.

Debug panels, copied diagnostics, browser console logs, network error messages,
tooltips, disabled-control explanations, and audit previews must follow the
same rule.

## 9. Implementation blockers

Role management UI implementation should not start until these blockers are
closed or explicitly accepted:

- backend role-management API contract exists and is capability-authoritative;
- MFA enrollment, verification, recovery-code, and production secret-storage
  policy are implemented and piloted;
- recent reauth contract is available for role/capability mutation;
- audit write and review workflow exists for role changes, denied attempts,
  break-glass use, and sensitive reads/writes;
- last-admin and break-glass policies are implemented backend-side;
- R5 route inventory confirms remaining coarse-admin-only surfaces and target
  capability coverage;
- rollback strategy exists for role mutation and fallback-removal pilots.

## 10. No implementation in this task

This task intentionally does not implement:

- frontend pages, components, routes, navigation, tests, or browser automation;
- backend role/capability mutation APIs;
- runtime auth/RBAC changes;
- database schema or migrations;
- MFA runtime behavior;
- Options, Data Pipeline, provider circuit, cost/quota, scanner, backtest,
  portfolio, notification delivery, broker/order, or system config behavior.
