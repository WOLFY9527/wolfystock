# Admin RBAC Final QA Report

Status: Superseded
Owner domain: Admin RBAC and security governance
Related docs: `docs/audits/admin-rbac-r5-coarse-fallback-removal-plan.md`, `docs/audits/public-launch-gap-register.md`

Date: 2026-05-06
Branch checked: `main`
Mode: QA / security regression for completed RBAC R3, R3b, R4A, and R4B.

## Scope

This pass reviewed RBAC guard placement, frontend capability gating, auth
contract safety, and sanitization/audit preservation. No backend route
migration, authorization semantic change, coarse admin fallback removal, MFA,
reauth, role-management UI, scanner, backtest, portfolio accounting, provider
ordering, notification delivery, DuckDB runtime, broker execution, Options Lab,
or WS2 runtime behavior was changed.

## Route Families Checked

- R3 admin security writes:
  - `POST /api/v1/admin/users/{user_id}/disable`
  - `POST /api/v1/admin/users/{user_id}/enable`
  - `POST /api/v1/admin/users/{user_id}/revoke-sessions`
  - Guard remains `require_admin_capability("users:security:write")`.
  - Reason, typed confirmation, self-disable, last-admin, session revoke count,
    and audit result shape remain in place.
- R3 admin portfolio visibility reads:
  - `GET /api/v1/admin/users/{user_id}/portfolio-summary`
  - `GET /api/v1/admin/users/{user_id}/holdings`
  - `GET /api/v1/admin/users/{user_id}/portfolio-activity`
  - `GET /api/v1/admin/users/{user_id}/portfolio/accounts/{account_id}`
  - Guard remains `require_admin_capability("users:portfolio:read")`.
  - Read-only projection and governance view audit behavior remain in place.
- R3b admin logs:
  - Log reads, sessions, details, and storage summary require
    `ops:logs:read`.
  - Cleanup requires `ops:logs:write`.
- R3b system config and provider probes:
  - Config read/schema/validate require `ops:system_config:read`.
  - Config update, runtime cache reset, and factory reset require
    `ops:system_config:write`.
  - LLM and data-source probes require `ops:providers:write`.
- R3b notifications:
  - Notification/channel reads require `ops:notifications:read`.
  - Channel create/update/delete/test and notification ack require
    `ops:notifications:write`.
- Coarse admin compatibility:
  - Existing legacy/coarse admin users still expand through compatibility
    capabilities.
  - Adjacent non-migrated admin surfaces still use `require_admin_user()`.
  - Capability dependency usage remains limited to
    `admin_logs.py`, `admin_notifications.py`, `admin_portfolio.py`,
    `admin_security.py`, and `system_config.py`.

No hard-coded RBAC role-name checks were found in the migrated route endpoint
files. Role-name logic remains in compatibility/helper or service guard
contexts, including the existing last-admin safety guard.

## Frontend Gates Checked

- `resolveAdminCapabilityFlags()` fails closed for missing current-user
  capability fields.
- `AdminSurfaceRoute` blocks admin pages unless the matching capability flag is
  present.
- Sidebar admin actions are capability-aware for:
  - users
  - cost observability
  - notifications
  - providers
  - system settings
- Admin user detail gates:
  - portfolio tab/data require `canReadUserPortfolio`.
  - security write actions require `canWriteUserSecurity`.
  - admin log links require `canReadOpsLogs`.
- Hidden portfolio/security tabs did not fetch forbidden APIs in browser
  checks, and forbidden portfolio/security text was not present in the DOM.

## Auth Contract Safety

Reviewed `auth/status`, `auth/me`, and login-response capability contract
coverage. The contract exposes `adminCapabilities` plus boolean convenience
flags only. Existing tests verify no password hash, raw session id, role
mapping internals, or grant metadata appears in the capability summary payload.

## Sanitization / Audit Review

- Denial responses from capability dependencies remain generic:
  `admin_required` or `admin_capability_required`.
- R3b tests assert denied responses do not expose password hashes, raw session
  markers, cookies, tokens, API keys, secret values, broker/provider
  credentials, webhook URLs, `.env`, traceback text, role inventory, or
  capability inventory.
- System config/probe errors continue to use generic endpoint-level messages
  and masking helpers.
- Notification channel config masking and localized delivery diagnostics remain
  in place.

## Commands And Results

- `python3 -m py_compile api/deps.py src/admin_rbac.py api/v1/endpoints/admin_security.py api/v1/endpoints/admin_portfolio.py api/v1/endpoints/admin_logs.py api/v1/endpoints/system_config.py api/v1/endpoints/admin_notifications.py api/v1/endpoints/auth.py`
  - PASS.
- `pytest tests/test_admin_rbac.py tests/api/test_admin_security.py tests/api/test_admin_portfolio.py tests/api/test_admin_rbac_r3b_routes.py tests/api/test_admin_logs.py tests/api/test_notification_channels.py tests/test_auth_api.py tests/test_system_config_api.py -q`
  - PASS: `139 passed in 19.75s`.
- `cd apps/dsa-web && npm test -- --run src/__tests__/AppRoutes.test.tsx src/components/layout/__tests__/Shell.test.tsx src/pages/__tests__/AdminUsersPage.test.tsx`
  - PASS: `3 passed`, `75 passed`.
- `cd apps/dsa-web && npm run lint --if-present`
  - PASS.
- `cd apps/dsa-web && npm run build --if-present`
  - PASS. Vite emitted the existing chunk-size warning.
- `./scripts/ci_gate.sh`
  - BLOCKED by unrelated dirty/untracked worktree state:
    `tests/test_quota_policy_service.py` imports missing
    `src.services.quota_policy_service`.
  - Earlier gate steps passed through syntax checks and deterministic
    `test.sh code` / `test.sh yfinance` checks before the offline test-suite
    collection error.

## Browser / Playwright Verification

Ports inspected before browser work:

- existing listeners on `:8000` and `:5173`;
- no shared server was killed.

Isolated frontend preview used:

- `http://127.0.0.1:4177`
- command: `cd apps/dsa-web && npm run preview -- --host 127.0.0.1 --port 4177`

Playwright method:

- headless Chromium against the isolated preview;
- mocked `auth/status`, `auth/me`, and relevant admin APIs;
- viewport sizes: `1440x1000` and `390x844`.

Cases passed on both viewports:

- full admin with all capability flags sees portfolio tab/data and performs
  portfolio read API fetches;
- limited admin with `users:read` only sees the portfolio capability gate and
  does not fetch portfolio or admin-log APIs;
- limited admin with `users:read` only sees the security capability gate and
  does not render security action buttons or fetch security write/admin-log
  APIs;
- admin current user with missing capability fields fails closed on
  `/zh/settings/system` and does not fetch system config.

Console/page errors:

- none in the passing Playwright run.

## Gaps / Remaining Production Blockers

- MFA is still not implemented.
- Recent reauth is now wired only to the Phase 3B admin user security write
  pilot; broader sensitive route coverage remains future work.
- Role management UI and capability mutation governance are still absent.
- Audit fail-closed policy remains future work.
- R5 removal of the coarse admin fallback remains future work.

## Final QA Status

Targeted RBAC backend tests, frontend tests, lint, build, and isolated browser
capability checks passed. Repo-level `ci_gate` is not green because of an
unrelated untracked quota-policy test/import blocker in the worktree, not
because of the RBAC route families reviewed here.
