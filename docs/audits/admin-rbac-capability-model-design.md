# Admin RBAC / Capability Model Design

Status: Partial
Owner domain: Admin RBAC and security governance
Related docs: `docs/audits/admin-rbac-r5-coarse-fallback-removal-plan.md`, `docs/archive/audits/admin-rbac-final-qa-report.md`

Date: 2026-05-06
Mode: docs-only authorization design. No runtime behavior changed.

Implementation note, 2026-05-06:

- Security Phase 3B route pilot has landed for the existing admin user security
  writes only: `POST /api/v1/admin/users/{user_id}/disable`, `POST
  /api/v1/admin/users/{user_id}/enable`, and `POST
  /api/v1/admin/users/{user_id}/revoke-sessions` now keep
  `users:security:write` and also require a recent session-bound
  `POST /api/v1/auth/reauth` marker for authenticated admin sessions. The
  existing auth-disabled transitional local admin path remains compatible
  through an explicit bypass limited to unauthenticated transitional users.
  This phase does not wire recent reauth to system config routes, logs,
  notifications, providers, portfolio reads, scanner, backtest, DuckDB,
  broker/order paths, MFA, password KDF upgrades, or role-management UI.
- Phase R3b route migration has landed for the next narrow ops-sensitive
  backend route set only. Admin log reads now require `ops:logs:read`; admin
  log cleanup requires `ops:logs:write`; system config read/schema/validate
  routes require `ops:system_config:read`; config writes, runtime cache reset,
  and factory reset require `ops:system_config:write`; LLM/data-source probes
  require `ops:providers:write`; notification/channel reads require
  `ops:notifications:read`; notification channel writes/tests and notification
  acknowledgements require `ops:notifications:write`. Existing coarse admins
  remain allowed through compatibility capability expansion. This phase does
  not migrate all admin routes, frontend navigation, role management UI, MFA,
  provider routing, notification delivery semantics, scanner/backtest/portfolio
  logic, Options Lab, or WS2 runtime behavior.
- Phase R4A backend capability summary contract has landed on the existing
  current-user auth contract. `GET /api/v1/auth/status`, `GET
  /api/v1/auth/me`, and login responses now expose a sanitized, sorted
  `currentUser.adminCapabilities` list plus coarse convenience booleans derived
  from `expand_admin_capabilities(user)`: `canReadUsers`,
  `canReadUserActivity`, `canReadUserPortfolio`, `canWriteUserSecurity`,
  `canReadCostObservability`, `canReadOpsLogs`, `canReadProviders`,
  `canReadNotifications`, and `canReadSystemConfig`. This is a UX contract for
  future frontend capability-aware navigation only. Backend route guards remain
  authoritative, `require_admin_user()` remains available, and no additional
  admin routes were migrated in R4A. The response does not expose password
  hashes, raw sessions, cookies, tokens, API keys, secrets, broker/provider
  credentials, `.env` values, raw role mapping internals, or grant metadata.
  Phase R4B frontend capability gating landed separately; R3b does not change
  frontend navigation.
- Phase R3 pilot route migration has landed for the intentionally narrow
  high-risk subset from the route matrix: admin security writes now require
  `users:security:write`, and admin portfolio visibility reads now require
  `users:portfolio:read`. Existing coarse admins remain allowed through the R1
  compatibility expansion. This phase does not migrate the broader admin
  surface, frontend navigation, role management UI, or non-admin runtime
  behavior.
- Phase R2 backend helper primitives have landed in `api/deps.py` without
  migrating any production route. The new helpers are
  `require_admin_capability(capability)`,
  `require_any_admin_capability(capabilities)`,
  `require_sensitive_reason(...)`, `require_recent_admin_reauth(...)`,
  `assert_not_self_destructive_action(...)`, and
  `assert_not_last_super_admin(...)`. They first preserve the existing
  authenticated admin identity requirement, then use the Phase R1
  `expand_admin_capabilities(user)` / `has_admin_capability(user, capability)`
  helpers for capability decisions.
- Phase R2 denial responses are sanitized and do not reveal role inventory,
  password hashes, raw sessions, cookies, tokens, API keys, secrets, broker
  credentials, or `.env` values. `require_recent_admin_reauth(...)` currently
  fails closed when no explicit recent-reauth metadata is supplied, because the
  current route dependency state does not yet carry a wired reauth source.
- Existing route authorization behavior remains unchanged in Phase R2:
  production routes still use `require_admin_user()` where they did before.
  The new helpers are covered by backend tests and are reserved for later route
  migrations. Broad allow/deny audit writes are intentionally deferred until a
  route migration phase can attach safe route context.

- Phase R1 compatibility has landed as a read-only schema/helper layer. SQLite
  initialization now creates and seeds `admin_roles`,
  `admin_role_capabilities`, and `admin_user_roles` with the built-in
  `super-admin`, `security-admin`, `support-admin`, and `ops-admin` roles plus
  the capability taxonomy below.
- Existing coarse admin users (`role == "admin"` or resolved `is_admin`) expand
  to super-admin-equivalent capabilities for compatibility. Non-admin users
  expand to no admin capabilities.
- The new helpers `expand_admin_capabilities(user)` and
  `has_admin_capability(user, capability)` are read-only metadata helpers for
  future phases. Current route authorization behavior is intentionally
  unchanged: admin routes still rely on `require_admin_user()` and no route has
  migrated to capability enforcement yet.
- Phase R1 does not implement MFA, role-management UI, capability overrides,
  route migration, frontend navigation changes, or any scanner/backtest/
  portfolio/provider/MarketCache/AI/notification/DuckDB behavior changes.

## 1. Purpose

WolfyStock's current admin authorization posture is intentionally simple: a
resolved current user is either an admin or not. That coarse gate was enough for
early internal operation, but it is not sufficient before broader production
exposure because every admin receives the same effective access to user
identity, activity, portfolio visibility, security controls, operational logs,
provider diagnostics, notification channels, system settings, and cost
observability.

The production security audit classifies this as a high-risk gap. Public or
semi-public deployment needs least-privilege separation, just-in-time checks for
sensitive actions, and audit evidence that distinguishes who could read data,
who could change security state, and who could change operational controls.

This document designs the target RBAC and capability model only. It does not
change runtime authorization, backend endpoints, frontend UI, schemas,
migrations, tests, portfolio/scanner/backtest/provider/MarketCache/AI/
notification/DuckDB behavior, or deployment behavior.

## 2. Current state

Current backend authorization centers on `api/deps.py`:

- `CurrentUser` carries `user_id`, `username`, `display_name`, `role`,
  `is_admin`, `is_authenticated`, auth/session metadata, and transitional auth
  state.
- `resolve_current_user()` accepts a valid signed session cookie backed by
  `app_user_sessions`, or creates a transitional bootstrap admin when auth is
  disabled.
- `is_admin_user()` checks the boolean admin flag.
- `require_admin_user()` rejects any resolved user whose `is_admin` flag is
  false.

Current persistence and auth seams:

- `src/auth.py` signs session cookies, validates session identity, verifies
  app-user sessions against server-side revocation/expiry, hashes passwords,
  maintains process-local login throttling, and supports legacy bootstrap admin
  compatibility.
- `src/repositories/auth_repo.py` exposes app-user lookup/listing, session
  creation/listing/revocation, bootstrap admin setup, and user create/update
  helpers.
- User rows currently have a coarse `role` string. The implemented admin role
  value is `admin`; frontend and backend checks assume this coarse role.

Known admin surfaces currently guarded by `require_admin_user()` or frontend
`AdminSurfaceRoute`/`isAdminAccount` checks include:

| Surface | Current route(s) | Current guard | Notes |
| --- | --- | --- | --- |
| Users | `GET /api/v1/admin/users`, `GET /api/v1/admin/users/{user_id}` | `require_admin_user()` | Safe user projections; no password hash exposure by design. |
| Activity | `GET /api/v1/admin/users/{user_id}/activity`, `GET /api/v1/admin/activity` | `require_admin_user()` | Safe execution/activity projection with raw payload exclusions. |
| Portfolio | `GET /api/v1/admin/users/{user_id}/portfolio-summary`, `/holdings`, `/portfolio-activity`, `/portfolio/accounts/{account_id}` | `require_admin_user()` | Read-only; masked broker refs; admin governance audit view events. |
| Security controls | `POST /api/v1/admin/users/{user_id}/disable`, `/enable`, `/revoke-sessions` | `require_admin_user()` | Confirmation, reason, self/last-admin guardrails exist in service layer. |
| Cost observability | `GET /api/v1/admin/cost/duplicate-summary` | `require_admin_user()` | Read-only operational observations; no external calls expected. |
| Market providers | `GET /api/v1/admin/market-providers/operations` | `require_admin_user()` | Read-only provider operations status. |
| Logs | `GET /api/v1/admin/logs`, `/sessions`, `/sessions/{session_id}`, `/{event_id}`, `/storage/summary`; `POST /api/v1/admin/logs/cleanup` | `require_admin_user()` | Operational/audit log reads plus retention cleanup. |
| Notifications | `/api/v1/admin/notification-channels`, `/api/v1/admin/notifications`, notification ack/test routes | `require_admin_user()` | Channel management and operational event acknowledgement. |
| System settings | `/api/v1/system/config`, validation/test/action routes | `require_admin_user()` | Reads masked config; some routes test channels/providers or mutate config/actions. |
| Scanner admin operations | `/api/v1/scanner/watchlists/today`, `/watchlists/recent`, `/status` | `require_admin_user()` | Operational scanner reads. |
| Optional DuckDB/quant admin operations | `/api/v1/quant/duckdb/*` | `require_admin_user()` | Optional quant engine health, init, ingest, coverage, benchmark, and diagnostics. |
| Future options lab admin surfaces | None confirmed as implemented in this review | N/A | Keep reserved capability naming for future admin route design only. |

Frontend admin routes currently use coarse admin-account gating:

- `/settings/system`
- `/admin/logs`
- `/admin/notifications`
- `/admin/market-providers`
- `/admin/users`
- `/admin/users/:userId`
- `/admin/users/:userId/activity`
- `/admin/cost-observability`

The current pattern is consistent, but it lacks role separation and capability
intent. The target design should preserve existing coarse-admin compatibility
while introducing explicit capabilities route by route.

## 3. Target roles

### `super-admin`

- Purpose: owns the full administrative trust boundary, bootstrap authority,
  role/capability assignment, emergency recovery, and final governance
  decisions.
- Allowed surfaces: all admin surfaces, including user governance, role
  management, security controls, admin audit, portfolio-sensitive reads, system
  settings, notification channel administration, provider operations, cost
  observability, scanner/backtest/admin diagnostics, and future options admin
  surfaces.
- Forbidden surfaces: none by role, but sensitive routes still require reason,
  recent reauthentication, MFA, and audit.
- MFA requirement: mandatory before production exposure.
- Session timeout recommendation: shortest admin timeout, with idle timeout no
  longer than 30 minutes and absolute timeout no longer than 8 hours.
- Audit requirements: all sensitive reads, all writes, denied attempts, role
  changes, break-glass use, and admin audit reads.

### `security-admin`

- Purpose: manages account security posture, session revocation, user disable/
  enable, future MFA/lockout state, and security audit review.
- Allowed surfaces: user directory/detail, user activity, user security state,
  disable/enable/revoke sessions, future password-reset/lockout/MFA controls,
  admin audit/security logs, and relevant security notifications.
- Forbidden surfaces: portfolio holdings/cash/transactions by default, system
  config writes unrelated to security, notification channel writes unrelated to
  security, cost dashboard ownership unless separately granted, provider
  runtime changes, scanner/backtest/quant mutation or operations.
- MFA requirement: mandatory.
- Session timeout recommendation: idle timeout no longer than 30 minutes and
  recent reauth for every security write.
- Audit requirements: all security reads/writes, denied attempts, blocked
  self/last-admin actions, reason text/category, outcome, and audit event id.

### `support-admin`

- Purpose: assists users with account visibility, safe activity triage, and
  read-only support diagnostics without access to high-risk security writes or
  broad financial details by default.
- Allowed surfaces: user directory/detail safe projection, redacted activity,
  limited session status, limited support-safe portfolio summary if approved,
  and links to logs with sensitive metadata collapsed.
- Forbidden surfaces: security writes, role/capability changes, raw/admin audit
  reads beyond support-relevant events, full portfolio holdings/cash/
  transactions unless explicitly granted, system config writes, provider
  operations writes/tests, notification channel writes, quant/DuckDB operations,
  cost observability unless separately granted.
- MFA requirement: required for production support accounts; can be optional in
  local dev until the MFA system exists.
- Session timeout recommendation: idle timeout no longer than 60 minutes and
  absolute timeout no longer than 12 hours.
- Audit requirements: user detail/activity reads, portfolio summary reads if
  enabled, denied sensitive attempts, and reason/context for target-user access.

### `ops-admin`

- Purpose: operates system health, logs, provider/runtime diagnostics,
  notifications, cost observability, and read-only operational dashboards.
- Allowed surfaces: admin logs, log storage summary, market provider operations,
  notification events/channel operations where approved, system runtime health,
  configuration validation/read-only views, cost observability, scanner
  operational status, future backtest/scanner operational dashboards, and
  optional quant health/coverage diagnostics.
- Forbidden surfaces: user portfolio read by default, account security writes,
  role/capability changes, user-sensitive drilldowns unrelated to operations,
  raw secret/config values, destructive reset without super-admin approval, and
  future options lab user data unless separately granted.
- MFA requirement: required before production exposure, especially for any
  write/test/probe operation.
- Session timeout recommendation: idle timeout no longer than 60 minutes; recent
  reauth for config writes, notification channel changes, destructive cleanup,
  and runtime reset actions.
- Audit requirements: operational reads when sensitive, all writes/tests/probes,
  denied attempts, cleanup/reset actions, and provider/notification target
  summaries without secret values.

## 4. Capability taxonomy

Capabilities are strings that describe route-level authority. Roles should map
to capabilities, but route guards should check capabilities rather than hard
coding role names.

Core user and security capabilities:

- `users:read`: list/read safe user directory and detail projections.
- `users:activity:read`: read safe user/global activity timelines.
- `users:portfolio:read`: read sensitive user portfolio projections.
- `users:security:read`: read user account/security/session state.
- `users:security:write`: disable/enable users, revoke sessions, and future
  reset/lockout/MFA actions.
- `admin_audit:read`: read admin audit and security-governance audit events.

Operations capabilities:

- `ops:logs:read`: read operational execution logs, sessions, storage summary,
  and sanitized diagnostics.
- `ops:logs:write`: run log cleanup or retention actions.
- `ops:providers:read`: read provider operations, provider status, and related
  diagnostics.
- `ops:providers:write`: run provider/custom-source probes or provider-affecting
  operational actions.
- `ops:notifications:read`: read admin notification events and channel status.
- `ops:notifications:write`: create/update/delete/test notification channels
  and acknowledge events.
- `ops:system_config:read`: read masked config and schema metadata.
- `ops:system_config:write`: write system config, reset runtime caches, factory
  reset bounded user-owned state, or run other system admin actions.
- `cost:observability:read`: read duplicate-cost and usage observability.

Future or optional capabilities:

- `scanner:admin:read`: read scanner operational status, watchlists, and future
  scanner admin dashboards.
- `backtest:admin:read`: read backtest operational status and future admin
  dashboards if added.
- `options:admin:read`: reserved for future options lab admin surfaces.
- `quant:admin:read`: read optional DuckDB/quant health, coverage, snapshots,
  benchmarks, and diagnostics.
- `quant:admin:write`: initialize/ingest/build optional quant data. This should
  be treated as ops-sensitive and separate from scanner/backtest runtime
  behavior.

Suggested default role mapping:

| Capability | super-admin | security-admin | support-admin | ops-admin |
| --- | --- | --- | --- | --- |
| `users:read` | Yes | Yes | Yes | No by default |
| `users:activity:read` | Yes | Yes | Yes, redacted | Limited operational context |
| `users:portfolio:read` | Yes | No by default | Optional limited approval | No |
| `users:security:read` | Yes | Yes | Limited status only | No |
| `users:security:write` | Yes | Yes | No | No |
| `admin_audit:read` | Yes | Yes for security scope | No by default | Limited ops scope |
| `ops:logs:read` | Yes | Security scope | Limited target-user links | Yes |
| `ops:logs:write` | Yes | No | No | Yes with reauth |
| `ops:providers:read` | Yes | No | No | Yes |
| `ops:providers:write` | Yes | No | No | Yes with reauth |
| `ops:notifications:read` | Yes | Security notifications | No by default | Yes |
| `ops:notifications:write` | Yes | Security-only if needed | No | Yes with reauth |
| `ops:system_config:read` | Yes | Security config subset | No | Yes |
| `ops:system_config:write` | Yes | Security-only if needed | No | Yes with reauth; destructive actions require super-admin |
| `cost:observability:read` | Yes | No by default | No by default | Yes |
| `scanner:admin:read` | Yes | No by default | No by default | Yes |
| `backtest:admin:read` | Yes | No by default | No by default | Yes |
| `options:admin:read` | Yes | No by default | No by default | Optional future ops/support policy |
| `quant:admin:read` | Yes | No | No | Yes |
| `quant:admin:write` | Yes | No | No | Yes with reauth, if enabled |

## 5. Route capability matrix

| Route | Current guard | Target capability | Required role(s) | Reason required? | MFA required? | Audit required? | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET /api/v1/admin/users` | `require_admin_user()` | `users:read` | super-admin, security-admin, support-admin | Optional; required when exporting/filtering sensitive cohorts | Yes in production | Yes | Safe list projection only. |
| `GET /api/v1/admin/users/{user_id}` | `require_admin_user()` | `users:read`, `users:security:read` for security fields | super-admin, security-admin, support-admin | Yes for target-user drilldown | Yes in production | Yes | Hide raw credentials/session ids. |
| `GET /api/v1/admin/users/{user_id}/activity` | `require_admin_user()` | `users:activity:read` | super-admin, security-admin, support-admin | Yes | Yes in production | Yes | Redact prompt/provider/request/session details. |
| `GET /api/v1/admin/activity` | `require_admin_user()` | `users:activity:read` or `ops:logs:read` by filters | super-admin, security-admin, ops-admin, support-admin limited | Optional for aggregate; required for target-user filters | Yes in production | Yes | Split global operational vs target-user activity policy. |
| `GET /api/v1/admin/users/{user_id}/portfolio-summary` | `require_admin_user()` | `users:portfolio:read` | super-admin; support-admin only if approved | Yes | Yes | Yes | Read-only; no sync/refresh/recompute. |
| `GET /api/v1/admin/users/{user_id}/holdings` | `require_admin_user()` | `users:portfolio:read` | super-admin by default | Yes | Yes | Yes, fail-closed target | Sensitive holdings/cash/P&L. |
| `GET /api/v1/admin/users/{user_id}/portfolio-activity` | `require_admin_user()` | `users:portfolio:read` | super-admin by default | Yes | Yes | Yes, fail-closed target | Sensitive trades/cash/corporate actions. |
| `GET /api/v1/admin/users/{user_id}/portfolio/accounts/{account_id}` | `require_admin_user()` | `users:portfolio:read` | super-admin by default | Yes | Yes | Yes, fail-closed target | Account ownership check remains required. |
| `POST /api/v1/admin/users/{user_id}/disable` | `require_admin_user()` | `users:security:write` | super-admin, security-admin | Yes | Yes plus recent reauth | Yes, fail-closed | Keep confirmation, self-action, and last-admin guardrails. |
| `POST /api/v1/admin/users/{user_id}/enable` | `require_admin_user()` | `users:security:write` | super-admin, security-admin | Yes | Yes plus recent reauth | Yes, fail-closed | Record success/failure/blocked. |
| `POST /api/v1/admin/users/{user_id}/revoke-sessions` | `require_admin_user()` | `users:security:write` | super-admin, security-admin | Yes | Yes plus recent reauth | Yes, fail-closed | Return counts only, never raw session ids. |
| `GET /api/v1/admin/logs` | `require_admin_user()` | `ops:logs:read` or `admin_audit:read` by filters | super-admin, ops-admin; security-admin for security scope | Optional aggregate; required for user/security filters | Yes in production | Yes | Sanitize metadata and route query summaries. |
| `GET /api/v1/admin/logs/sessions` | `require_admin_user()` | `ops:logs:read` | super-admin, ops-admin | Optional | Yes in production | Yes | Sensitive detail expansion should require reason. |
| `GET /api/v1/admin/logs/sessions/{session_id}` | `require_admin_user()` | `ops:logs:read` | super-admin, ops-admin; security-admin for security scope | Yes | Yes | Yes | Do not expose raw session/cookie/token values. |
| `GET /api/v1/admin/logs/{event_id}` | `require_admin_user()` | `ops:logs:read` or `admin_audit:read` | super-admin, ops-admin; security-admin for security scope | Yes | Yes | Yes | Event detail reads are sensitive. |
| `GET /api/v1/admin/logs/storage/summary` | `require_admin_user()` | `ops:logs:read` | super-admin, ops-admin | No | Yes in production | Optional/low-detail | Operational summary. |
| `POST /api/v1/admin/logs/cleanup` | `require_admin_user()` | `ops:logs:write` | super-admin, ops-admin | Yes | Yes plus recent reauth | Yes | Destructive retention cleanup. |
| `GET /api/v1/admin/cost/duplicate-summary` | `require_admin_user()` | `cost:observability:read` | super-admin, ops-admin | No for aggregate | Yes in production | Yes | Read-only; no external calls. |
| `GET /api/v1/admin/market-providers/operations` | `require_admin_user()` | `ops:providers:read` | super-admin, ops-admin | No | Yes in production | Optional/aggregate | Read-only provider operations. |
| `GET /api/v1/admin/notification-channels` | `require_admin_user()` | `ops:notifications:read` | super-admin, ops-admin | No | Yes in production | Yes | Channel values must stay masked/safe. |
| `POST/PATCH/DELETE /api/v1/admin/notification-channels*` | `require_admin_user()` | `ops:notifications:write` | super-admin, ops-admin | Yes | Yes plus recent reauth | Yes | Includes test delivery; never log credentials. |
| `GET /api/v1/admin/notifications` | `require_admin_user()` | `ops:notifications:read` | super-admin, ops-admin; security-admin for security events | Optional | Yes in production | Yes | Event list may include operational metadata. |
| `POST /api/v1/admin/notifications/{event_id}/ack` | `require_admin_user()` | `ops:notifications:write` | super-admin, ops-admin | Optional | Yes in production | Yes | Acknowledgement is a state change. |
| `GET /api/v1/system/config` | `require_admin_user()` | `ops:system_config:read` | super-admin, ops-admin | No | Yes | Yes | Masked values only. |
| `PUT /api/v1/system/config` | `require_admin_user()` | `ops:system_config:write` | super-admin, ops-admin | Yes | Yes plus recent reauth | Yes, fail-closed | Writes `.env`; secrets remain masked. |
| `POST /api/v1/system/config/validate` | `require_admin_user()` | `ops:system_config:read` | super-admin, ops-admin | No | Yes | Optional | Validation only, no write. |
| `POST /api/v1/system/config/llm/test-channel` | `require_admin_user()` | `ops:providers:write` | super-admin, ops-admin | Yes | Yes plus recent reauth | Yes | External probe; no raw key/value logging. |
| `POST /api/v1/system/config/data-source/test*` | `require_admin_user()` | `ops:providers:write` | super-admin, ops-admin | Yes | Yes plus recent reauth | Yes | External probe; no raw credential exposure. |
| `GET /api/v1/system/config/schema` | `require_admin_user()` | `ops:system_config:read` | super-admin, ops-admin | No | Yes in production | Optional | Metadata only. |
| `POST /api/v1/system/actions/runtime-cache/reset` | `require_admin_user()` | `ops:system_config:write` | super-admin, ops-admin | Yes | Yes plus recent reauth | Yes | Runtime action; no behavior change in this doc. |
| `POST /api/v1/system/actions/factory-reset` | `require_admin_user()` | `ops:system_config:write` plus super-admin policy | super-admin; ops-admin only with explicit approval | Yes | Yes plus recent reauth | Yes, fail-closed | Destructive bounded reset; should require stronger guard. |
| `GET /api/v1/scanner/watchlists/today` | `require_admin_user()` | `scanner:admin:read` | super-admin, ops-admin | No | Yes in production | Optional | Operational read only. |
| `GET /api/v1/scanner/watchlists/recent` | `require_admin_user()` | `scanner:admin:read` | super-admin, ops-admin | No | Yes in production | Optional | Operational read only. |
| `GET /api/v1/scanner/status` | `require_admin_user()` | `scanner:admin:read` | super-admin, ops-admin | No | Yes in production | Optional | Operational read only. |
| `/api/v1/quant/duckdb/*` read routes | `require_admin_user()` | `quant:admin:read` | super-admin, ops-admin | No for aggregate; yes for snapshots/benchmarks if sensitive | Yes in production | Yes for detail | Optional quant admin diagnostics. |
| `/api/v1/quant/duckdb/*` write/init/ingest/build routes | `require_admin_user()` | `quant:admin:write` | super-admin, ops-admin if enabled | Yes | Yes plus recent reauth | Yes | Keep separate from scanner/backtest runtime behavior. |
| Frontend `/settings/system` | `AdminSurfaceRoute` | `ops:system_config:read/write` by action | super-admin, ops-admin | By action | Yes in production | Backend authoritative | Hide/disable controls by capability. |
| Frontend `/admin/users*` | `AdminSurfaceRoute` | `users:*` capabilities by tab/action | super-admin, security-admin, support-admin | Yes for drilldown/actions | Yes in production | Backend authoritative | Tabs should not optimistically expose forbidden data. |
| Frontend `/admin/logs` | `AdminSurfaceRoute` | `ops:logs:read`, `admin_audit:read` | super-admin, ops-admin, scoped security-admin | By detail/filter | Yes in production | Backend authoritative | Filter-dependent access messages. |
| Frontend `/admin/notifications` | `AdminSurfaceRoute` | `ops:notifications:*` | super-admin, ops-admin | By action | Yes in production | Backend authoritative | Channel writes require reauth later. |
| Frontend `/admin/market-providers` | `AdminSurfaceRoute` | `ops:providers:read` | super-admin, ops-admin | No | Yes in production | Backend authoritative | Read-only operations status. |
| Frontend `/admin/cost-observability` | `AdminSurfaceRoute` | `cost:observability:read` | super-admin, ops-admin | No | Yes in production | Backend authoritative | Aggregate read-only dashboard. |
| Future options lab admin routes | Not implemented | `options:admin:read` | super-admin; ops/support only after design | TBD | Yes in production | Yes | Reserved only; do not implement from this doc. |

## 6. Data model design

### Option A: simple role enum extension

Extend the existing `AppUser.role` string from `admin`/`user` to values such as
`super-admin`, `security-admin`, `support-admin`, and `ops-admin`.

Pros:

- Minimal schema change.
- Easy to migrate existing `admin` users into `super-admin` or transitional
  `admin`.
- Simple to reason about in early implementation.

Cons:

- Hard to express scoped access or future product-specific grants.
- Route guards still tend to hard-code role names.
- Exceptions such as support-admin with limited portfolio-read become awkward.

### Option B: `user_roles` table

Add a table that assigns one or more roles to a user.

Pros:

- Supports multiple roles per user.
- Allows gradual migration from coarse `AppUser.role`.
- Keeps role assignment auditable.

Cons:

- Still needs a capability mapping to avoid role checks leaking into routes.
- Requires bootstrap and last-super-admin semantics.

### Option C: `role_capabilities` table

Add a table that maps roles to capability strings.

Pros:

- Route guards can check capabilities.
- Role definitions can evolve without editing every route.
- Good fit for least-privilege admin surface expansion.

Cons:

- Requires careful defaults and migration seeding.
- Needs cache/refresh semantics and audit of role definition changes.

### Option D: `user_capabilities` override table

Add per-user allow/deny capability overrides.

Pros:

- Useful for temporary grants, break-glass access, or tightly scoped pilots.
- Can avoid creating too many one-off roles.

Cons:

- Highest governance risk if used casually.
- Requires expiry, reason, approver, and audit fields to avoid privilege drift.
- Should not be used as the primary model.

### Recommended phased model

Use a phased hybrid:

1. Preserve `AppUser.role` for compatibility and bootstrap.
2. Add `user_roles` and `role_capabilities` as the target authority path.
3. Seed `super-admin`, `security-admin`, `support-admin`, and `ops-admin`.
4. Treat legacy `role == "admin"` as transitional super-admin compatibility
   only during rollout.
5. Add `user_capabilities` only after the core role/capability path is stable,
   and require expiry, reason, approver, and audit for any override.

Suggested schema concepts, not implementation:

- `admin_roles`: role key, display name, description, built-in flag, active
  flag, created/updated metadata.
- `admin_role_capabilities`: role key, capability, effect, created/updated
  metadata.
- `admin_user_roles`: user id, role key, granted by, reason, created/updated
  metadata, optional expiry.
- `admin_user_capability_overrides`: user id, capability, effect, granted by,
  reason, expiry, created/updated metadata.
- `admin_role_audit_events`: actor, target role/user, capability, action,
  outcome, reason, safe request/session handle.

## 7. Dependency/helper design

Future dependency helpers should be explicit, composable, and route-local:

- `require_admin_capability(capability)`: resolves current user, expands roles
  to capabilities, and rejects missing capability with sanitized 403 metadata.
- `require_any_admin_capability([...])`: accepts any one capability from a
  bounded list, useful for routes that can be reached by security or ops scope
  depending on filter/path.
- `require_sensitive_reason(...)`: validates a bounded reason/context field for
  sensitive user drilldowns, portfolio reads, audit reads, security writes,
  destructive log cleanup, config writes, probes, and reset actions.
- `require_recent_admin_reauth(...)`: ensures the admin recently reauthenticated
  before high-impact writes or sensitive reads.
- `assert_not_self_destructive_action(...)`: blocks actions that disable,
  revoke, reset, lock, or otherwise endanger the acting admin's own access
  unless a separately designed safe flow allows it.
- `assert_not_last_super_admin(...)`: prevents deleting, disabling, demoting,
  locking, or expiring the last usable super-admin.

Helper behavior principles:

- Backend guards are authoritative; frontend gates are only UX.
- 401/403 responses should not leak role inventory or sensitive target details.
- Denied access should be audit-recorded with safe metadata when actor identity
  is known.
- Capability checks should not read raw secrets or expose secret values in
  errors, logs, or audit metadata.
- Legacy `require_admin_user()` can remain as a compatibility fallback during
  early rollout, but sensitive routes should migrate first.

## 8. Frontend UX implications

Frontend changes should happen after backend capability contracts exist.
Expected implications:

- Hide nav items by capability, not by coarse `isAdminAccount`.
- Keep backend as the source of truth; hidden nav is not authorization.
- Show disabled controls with concise explanations only when the user has a
  nearby capability and the disabled state helps workflow clarity.
- Use reason prompts before sensitive target-user reads, portfolio drilldowns,
  admin-audit reads, security writes, destructive log cleanup, config writes,
  provider tests, notification channel tests, and reset actions.
- Add MFA or recent-reauth prompts later for sensitive reads/writes.
- Do not optimistically fetch forbidden data and then hide it in the DOM.
- Do not render forbidden data in hidden tabs, data attributes, tooltips, copied
  diagnostics, optimistic cache state, or error details.
- Keep support-admin views safe by default: aggregate first, drilldown second,
  redacted metadata, no raw prompts/provider payloads/session ids/secrets.
- For mixed-capability pages such as `/admin/users/:userId`, resolve tab/action
  access separately so a support-admin can see safe profile/activity while
  security and portfolio tabs remain unavailable.

## 9. Audit model

Audit should use safe metadata only. Do not store real secrets, tokens, password
hashes, cookies, raw session ids, API key values, provider payloads, raw prompts,
raw request bodies, stack traces, broker raw payloads, or raw `.env` values.

Required audit events:

- Every denied admin access when the actor is safely known.
- Every sensitive read success, including user detail drilldown, portfolio
  detail, holdings, portfolio activity, admin audit detail, sensitive log
  detail, and security state detail.
- Security write success, failure, and blocked outcomes.
- Role/capability changes, grants, revocations, expiries, overrides, and
  attempted changes.
- Admin audit reads.
- Config writes, destructive system actions, runtime cache reset, log cleanup,
  provider probes, notification channel writes/tests, and quant write/init/
  ingest/build actions.
- Break-glass or emergency access use.

Safe metadata allowlist:

- Actor user id or stable safe handle.
- Actor role/capability summary.
- Target user id or hashed target id where needed.
- Route/action family.
- Capability required and decision outcome.
- Reason category and bounded reason text when approved.
- Request id or hashed request/session handle.
- Filter summaries, result counts, and high-level status.
- Timestamp, source surface, and audit event id.

Fail-closed recommendation:

- Fail closed when audit persistence fails for security writes, role/capability
  changes, portfolio holdings/activity/account detail reads, admin audit detail
  reads, factory reset, destructive cleanup, and break-glass access.
- Aggregate operational reads may use degraded access only after an explicit
  product decision documents that tradeoff.

## 10. Migration and rollout plan

### Phase R0: design only

- Land this document.
- Do not implement runtime code, schema, migrations, frontend changes, tests, or
  behavior changes.

### Phase R1: schema and compatibility read path

- Add role/capability schema with seeded built-in roles.
- Preserve `AppUser.role` compatibility.
- Map existing `role == "admin"` users to transitional `super-admin`
  capability equivalence.
- Add read-only capability expansion helpers without changing route behavior.
- Add bootstrap and last-super-admin readiness checks.

### Phase R2: backend capability helpers

- Add `require_admin_capability()`, `require_any_admin_capability()`, reason,
  recent-reauth, self-action, and last-super-admin helpers.
- Add audit events for allow/deny decisions using safe metadata.
- Keep coarse admin fallback for non-sensitive routes during rollout.

### Phase R3: migrate admin routes

- Migrate high-risk routes first: security writes, portfolio detail, admin audit
  reads, config writes, log cleanup, notification channel writes, provider
  probes, and factory reset.
- Then migrate user directory/activity, cost observability, provider reads,
  scanner/admin reads, and optional quant diagnostics.
- Keep route-level tests for each migrated capability.

### Phase R4: frontend capability-aware nav

- R4A complete: include safe capability summary fields in the existing
  current-user auth contract.
- R4B pending: consume those fields in frontend navigation and actions.
- Hide or disable nav/actions by capability.
- Add reason prompts and future MFA/reauth prompts.
- Ensure forbidden data is never fetched optimistically.

### Phase R5: remove coarse admin fallback for sensitive routes

- After tests, audit evidence, and frontend handling are stable, remove coarse
  admin fallback from sensitive routes.
- Keep compatibility only for explicitly low-risk routes if needed, with a
  dated removal plan.
- Verify production bootstrap, last-super-admin guard, and break-glass process.

## 11. Test plan

Future implementation should include:

- Route capability tests for every admin endpoint family.
- Non-admin forbidden tests for every admin route.
- Unauthenticated forbidden/unauthorized tests.
- `support-admin` cannot call `users:security:write` routes.
- `ops-admin` cannot call `users:portfolio:read` routes.
- `security-admin` can revoke sessions when MFA/reauth/reason checks pass.
- `security-admin` cannot read portfolio holdings by default.
- `super-admin` can manage roles/capabilities.
- Last-super-admin guard blocks disable/demotion/removal/expiry.
- Self-destructive action guard blocks dangerous self-actions.
- Reason-required routes reject missing or overlong reasons.
- Recent-reauth routes reject stale admin sessions.
- No secret exposure in responses, audit metadata, frontend DOM, or logs.
- Audit events recorded for allow, deny, success, failure, and blocked outcomes.
- Audit fail-closed behavior for security writes and sensitive reads.
- Legacy `role == "admin"` compatibility works only during the intended phase.

## 12. Risks and open questions

- Existing users migration: decide whether every current `admin` becomes
  `super-admin` initially, and how to reduce privileges after rollout.
- Bootstrap admin: define how first admin and recovery admin are represented in
  the new schema.
- Emergency break-glass: decide whether break-glass is a role, a temporary
  capability override, or an external operational procedure.
- Local dev ergonomics: preserve a low-friction local path without weakening
  production defaults.
- Admin MFA dependency: capability rollout can start before MFA, but public
  exposure should not treat the model complete without admin MFA.
- Audit fail-closed choices: define which read paths can degrade and which must
  fail if audit persistence is unavailable.
- Capability cache invalidation: role changes must take effect quickly enough
  to revoke privileges.
- Last-super-admin semantics: account disabled state, session revocation,
  role expiry, bootstrap state, and auth-disabled transitional mode need one
  consistent rule.
- Support visibility: decide whether support-admin may see limited portfolio
  summaries and what masking applies.
- Ops destructive actions: decide whether factory reset and notification/provider
  probes require super-admin approval even when ops-admin owns day-to-day
  operations.
- Frontend current-user contract: decide whether capabilities are returned on
  auth status, a dedicated endpoint, or per-route access metadata.

## 13. Recommended next prompts

1. RBAC schema compatibility implementation.
2. Backend capability helper + tests.
3. Route migration phase.
4. Frontend capability-aware nav.
5. RBAC final QA.
