# Admin Data Control Center Design

Date: 2026-05-06

Mode: docs-only design. No runtime behavior changed.

## 1. Purpose

The current admin platform has useful operational surfaces, but user-owned business data is still mostly opaque from the administrator perspective. Admins can inspect execution logs and market provider operations, yet they do not have a controlled product surface for answering basic support, governance, security, and risk questions such as: which users exist, which accounts are active, what sessions are live, which analyses or scanner runs belong to a user, and what portfolio summaries exist for a user.

The goal is an Admin Data Control Center: a controlled, audited, least-privilege admin workspace for inspecting user, security, activity, analysis, scanner, backtest, portfolio, ownership, and sensitive-data access state. It must not become a raw database browser. It must also never expose plaintext passwords, password hashes, session tokens, API keys, secrets, cookies, or credential-like values.

## 2. Current admin capability snapshot

Confirmed from static inspection:

- Auth and identity are centered on `src/auth.py`, `api/deps.py`, `api/middlewares/auth.py`, `api/v1/endpoints/auth.py`, `src/repositories/auth_repo.py`, and `src/storage.py`.
- `src/storage.py` defines `AppUser` with `id`, `username`, `display_name`, `password_hash`, `role`, `is_active`, `created_at`, and `updated_at`; it defines `AppUserSession` with `session_id`, `user_id`, `created_at`, `last_seen_at`, `expires_at`, and `revoked_at`.
- `api/deps.py` defines `CurrentUser`, `resolve_current_user()`, `get_current_user()`, `is_admin_user()`, `ensure_current_user_matches_owner()`, and `require_admin_user()`. Existing admin-only APIs use `Depends(require_admin_user)`.
- `src/auth.py` signs session cookies under `COOKIE_NAME = "dsa_session"`, validates app-user sessions in `get_session_identity()`, hashes passwords with `hash_password_for_storage()`, verifies hashes with `verify_password_hash_string()`, supports session invalidation via `rotate_session_secret()`, and stores legacy bootstrap admin credentials in `.admin_password_hash`.
- `api/v1/endpoints/auth.py` implements `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/change-password`, `/api/v1/auth/reset-password/request`, admin settings update, and admin unlock verification. Login creates app-user sessions through `AuthRepository.create_app_user_session()`. Logout revokes the current session through `AuthRepository.revoke_app_user_session()`. Password change revokes all sessions for normal users through `AuthRepository.revoke_all_app_user_sessions()`.
- `api/v1/endpoints/admin_logs.py` exposes admin-only log surfaces: `list_execution_logs_root()`, `list_execution_log_sessions()`, `get_execution_log_session_detail()`, `get_business_event_detail()`, `get_log_storage_summary()`, and `cleanup_admin_logs()`.
- `src/services/execution_log_service.py` is the main observability seam. It provides `list_business_events()`, `get_business_event_detail()`, `list_sessions()`, `get_session_detail()`, `summarize_items()`, and `summarize_business_events()`. It calls `sanitize_metadata()`, `sanitize_message()`, and `sanitize_url()` from `src/utils/security.py`.
- `src/utils/security.py` masks secret-like metadata keys and URL/query fragments that include `api_key`, `token`, `authorization`, `credential`, `secret`, or `password`.
- `api/v1/endpoints/market_provider_operations.py` exposes read-only `get_market_provider_operations()` under `Depends(require_admin_user)`. `apps/dsa-web/src/pages/MarketProviderOperationsPage.tsx` links degraded provider operations back to Admin Logs instead of showing raw sensitive details inline.
- `apps/dsa-web/src/App.tsx` defines `AdminSurfaceRoute`, which gates `/admin/logs`, `/admin/notifications`, and `/admin/market-providers` for admin users. `apps/dsa-web/src/components/layout/SidebarNav.tsx` shows admin account utility routes for system settings, notifications, and market provider operations. `apps/dsa-web/src/components/layout/Shell.tsx` treats `/settings/system`, `/admin/notifications`, and `/admin/market-providers` as system-control routes.
- Portfolio endpoints in `api/v1/endpoints/portfolio.py` are user-scoped through `_get_portfolio_service(current_user)` and `PortfolioService(owner_id=current_user.user_id)`. Portfolio writes call `_record_portfolio_audit()` for account archive, trades, cash ledger creation, corporate action creation, and trade update/void paths.
- Portfolio storage in `src/storage.py` includes `PortfolioAccount`, `PortfolioBrokerConnection`, broker sync state/positions/cash balances, trades, cash ledger, corporate actions, replayed positions/lots, daily snapshots, and FX rates. Owner fields exist on account and broker-sync surfaces.
- Scanner records are persisted through `MarketScannerRun` and `MarketScannerCandidate` in `src/storage.py`; `src/repositories/scanner_repo.py` has owner-aware methods such as `get_runs_paginated()`, `get_run()`, and `update_run()` with `owner_id` and `include_all_owners`.
- Backtest records are persisted through `BacktestRun`, `BacktestResult`, `BacktestSummary`, `RuleBacktestRun`, and `RuleBacktestTrade`. `src/repositories/backtest_repo.py` and `src/repositories/rule_backtest_repo.py` support owner-scoped reads and optional all-owner reads via `include_all_owners`.
- Analysis history is stored in `AnalysisHistory` with `owner_id`, `query_id`, stock fields, summary fields, and raw result/context fields. `DatabaseManager` exposes analysis history helpers such as `save_analysis_history()`, `get_analysis_history_paginated()`, and `get_analysis_history_by_id()`.

Confirmed gaps:

- No verified admin user directory API exists under `/api/v1/admin/users`.
- No verified admin user-detail API exists that aggregates user profile, sessions, activity, portfolio, analysis, scanner, and backtest data.
- No verified admin security-controls API exists for disabling or enabling arbitrary users, force-password-change flags, admin-triggered session revocation, lock/unlock state, or reason-required sensitive-data access.
- No verified frontend admin route exists for `/zh/admin/users`, `/zh/admin/users/:userId`, user security, user activity, user portfolio, user analysis, or `/zh/admin/audit`.
- Existing Admin Logs provide global observability, but they are not a complete user data governance center.

Inferred gaps:

- `AppUser.password_hash` exists, but there is no inspected product-safe admin projection that explicitly hides it.
- `AppUserSession.session_id` exists, but the future admin surface should expose only hashed/truncated identifiers and action controls, not raw session IDs or cookie values.
- `AnalysisHistory.raw_result`, `news_content`, `context_snapshot`, rule backtest prompt-like fields, scanner diagnostics, and LLM/provider metadata can contain sensitive or high-context content; future admin views need redaction, collapse, and audit-by-view.

## 3. Security and privacy principles

- Never display plaintext passwords. A password reveal feature must not exist.
- Never display password hashes, password hash salts, legacy `.admin_password_hash` contents, session signing secrets, raw session IDs, signed cookies, reset tokens, API keys, provider tokens, webhook secrets, or credential-like values.
- Credential controls are action-only: reset password, force password change, disable/enable account, lock/unlock, revoke sessions/tokens, and audit security events. They are not reveal controls.
- Admin sensitive-data access must itself be audited. Viewing user security state, portfolio data, raw-ish activity detail, uploaded files, prompts, or report internals should create an admin access event.
- Least privilege applies to admins. A future support-admin should not automatically receive all security, portfolio, prompt, or raw report access.
- Read-only by default. Destructive or corrective operations require separate designs, permissions, confirmations, and tests.
- Aggregate first, drilldown second. Directory and overview screens should show safe counts/statuses before detail views.
- Redact by default. Raw developer details should be collapsed, sanitized, and unavailable to lower-privilege admin roles.
- Sensitive views should require reason/context if the future product supports it, especially portfolio, security, uploaded file, raw prompt/message, and admin-access-log views.
- Admin APIs must reuse `require_admin_user()` or a stricter future helper, not bypass owner/auth checks with ad hoc request parsing.
- No raw database browser task should be introduced.

## 4. Admin capability model

### 4.1 User Directory

Capabilities:

- List users with pagination and stable sorting.
- Search and filter by username, display name, role, active status, created time, last login/session time, last activity time, and risk/status flags.
- Show role, status, createdAt, updatedAt, lastLogin, lastActivity, auth provider/account type when available.
- Show risk badges such as inactive, no password initialized, session expired, repeated failed login, high admin access volume, or portfolio/security audit attention.

Security posture:

- Hide `password_hash`.
- Hide session IDs and cookies.
- Show counts and timestamps before any sensitive detail.

### 4.2 User Detail

Capabilities:

- Account summary: id, username, display name, role, active status, created/updated timestamps.
- Roles/permissions summary based on current role fields and future permission tables if added.
- Recent sessions with redacted session handle, createdAt, lastSeenAt, expiresAt, revokedAt, client summary if safely available.
- Recent activity timeline across login/logout, analysis, scanner, backtest, portfolio, admin actions, failures, and system/background events.
- Linked analysis/scanner/backtest/portfolio data summaries.
- Admin audit trail for this target user: who viewed or changed this user's admin-visible data.

### 4.3 Security Controls

Capabilities:

- Reset password through a one-time reset flow, not by revealing or setting a visible password in the UI.
- Force password change on next login after a future schema/control exists.
- Disable/enable account.
- Revoke sessions or tokens without exposing token values.
- Unlock account or clear lockout state after a future lockout model exists.
- View failed login attempts and password changed timestamp if safely available.

Hard rule:

- Never reveal plaintext password or password hash.

### 4.4 Activity Timeline

Capabilities:

- Normalize login/logout, analysis requests, scanner runs, backtests, portfolio changes/views, admin actions, errors/failures, API route family, and safe request/session references.
- Use `ExecutionLogService.list_business_events()` and `list_sessions()` concepts where possible.
- Show actor type, actor role, target user, status, event family, entity type, hashed entity id, and redacted metadata.

### 4.5 Portfolio / Holdings Visibility

Capabilities:

- Read-only user portfolio summary.
- Accounts, holdings, cash, exposure, P&L, FX/risk warnings, and broker sync summaries.
- Transaction/activity timeline when present: trades, cash ledger, corporate actions, import/sync events.
- No accounting semantic changes.
- No direct edits until a separate audited correction-flow design exists.

### 4.6 Analysis / Scanner / Backtest Visibility

Capabilities:

- User analysis history with safe metadata and report summaries.
- Scanner run history with run status, market/profile/universe, candidate counts, and deterministic ranking outputs.
- Backtest and rule backtest history with run status, metrics, strategy labels, and result links.
- LLM usage/cost summary where existing instrumentation supports it.
- Links to Admin Logs and execution sessions where available.

Privacy posture:

- Raw model prompts, raw messages, provider debug payloads, raw report JSON, and stack traces stay collapsed, redacted, role-restricted, and audited.

### 4.7 Admin Audit of Admin Actions

Capabilities:

- Every sensitive admin view/action creates an audit event.
- Record who viewed what category, when, target user/entity, reason/context if required, outcome, route/action family, and request id.
- Redact target id or hash target identifiers when displaying cross-user audit data to lower-privilege admins.

## 5. Data classification matrix

| Data category | Examples | Admin visibility | Redaction | Allowed actions | Audit required? | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Public/non-sensitive operational metadata | route family, feature name, event category, high-level status | visible | none or minimal | filter, sort, drilldown | yes for admin workspace access | Reuse Admin Logs patterns. |
| User profile fields | id, username, display name, role, active status, createdAt | visible | show stable id; no credentials | list, filter, disable/enable after security phase | yes | Avoid showing email/notification targets unless explicitly classified. |
| Auth/security fields | role, active status, last login, failed login count, password changed timestamp | visible redacted | no raw session/token/cookie; no hash | reset, force change, revoke sessions, lock/unlock | yes | Role split should gate security actions. |
| Password hash | `AppUser.password_hash`, legacy `.admin_password_hash` | hidden | not returned | reset/force-change only | yes for action | Never display or export. |
| Sessions/tokens | app session IDs, signed cookies, reset token, session secret | action-only | hash/truncate session handle; never raw token/cookie | revoke sessions/tokens | yes | Admin logs record action, not token value. |
| Portfolio/holdings | accounts, holdings, cash, exposure, P&L, snapshots | visible or visible aggregate first | mask broker account references where needed | read-only first | yes | Direct corrections out of scope. |
| Analysis reports | summary, sentiment, advice, stock code/name, createdAt | visible | raw result/context redacted/collapsed | read-only, link to logs | yes for drilldown | Raw report payload can include prompt/context detail. |
| Scanner/backtest records | run status, metrics, candidates/trades, strategy text | visible with detail controls | strategy text/prompt-like content collapsed if sensitive | read-only, link to logs | yes for drilldown | Do not change scoring/ranking/calculations. |
| LLM usage | provider/model names, token/cost summary, route family | visible aggregate first | raw prompts/messages hidden by default | read-only, link to cost logs | yes | Align with cost-observability docs. |
| Provider/runtime logs | provider name, degraded status, cache/fallback status | visible redacted | sanitize URLs/errors | read-only | yes | Existing market provider ops is read-only. |
| Secrets/API keys | environment secrets, provider keys, webhook tokens | hidden | never return values; use configured/unconfigured status only | rotate/test via separate curated settings only | yes for actions | Env var names may be shown; values never. |
| Raw prompts/messages | LLM prompts, chat messages, report prompt internals | visible aggregate only or hidden | redact/collapse; role-restricted | read-only only after reason-required access | yes | Prefer summaries and hashes. |
| Uploaded images/files | image analysis inputs, broker import files if persisted | hidden by default | file hash/metadata only | read-only metadata; raw file access separate design | yes | Do not expose full files without explicit retention/access policy. |

## 6. Proposed backend API design

All routes below are proposed only. They do not exist unless implemented in a future task.

### 6.1 User directory

Routes:

- `GET /api/v1/admin/users`
- `GET /api/v1/admin/users/{user_id}`

Purpose:

- Provide admin-only user list and user detail projections.

Read/write behavior:

- Read-only.

Permission model:

- Start with `require_admin_user()`.
- Future: `require_admin_capability("users:read")`.

Privacy/redaction rules:

- Never include `password_hash`.
- Include session counts and last timestamps, not raw session IDs.

Audit requirement:

- Directory list access is audited at category level.
- Detail access is audited with target user id or hashed target id.

Response shape sketch:

```json
{
  "items": [
    {
      "id": "user-...",
      "username": "alice",
      "displayName": "Alice",
      "role": "user",
      "status": "active",
      "createdAt": "2026-05-06T00:00:00Z",
      "lastLoginAt": null,
      "lastActivityAt": null,
      "sessionSummary": {"activeCount": 1, "revokedCount": 0},
      "riskBadges": []
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

Tests needed:

- Admin required.
- Non-admin forbidden.
- Password hashes not present.
- Pagination/filtering.
- Target user detail emits audit event.

### 6.2 Security

Routes:

- `POST /api/v1/admin/users/{user_id}/disable`
- `POST /api/v1/admin/users/{user_id}/enable`
- `POST /api/v1/admin/users/{user_id}/reset-password`
- `POST /api/v1/admin/users/{user_id}/force-password-change`
- `POST /api/v1/admin/users/{user_id}/revoke-sessions`

Purpose:

- Give authorized admins controlled account security actions.

Read/write behavior:

- Mutating, security-sensitive, no credential reveal.

Permission model:

- Future `security-admin` or `super-admin` capability.
- Support-admin may view safe security state but cannot mutate.

Privacy/redaction rules:

- Request and response contain no password, password hash, session token, signed cookie, reset token, or API key value.
- Password reset returns status and delivery/reset-flow metadata only.

Audit requirement:

- Always required, including failed attempts.
- Store action, actor, target, reason, and outcome; never store secret values.

Response shape sketch:

```json
{
  "ok": true,
  "action": "revoke_sessions",
  "targetUserId": "user-...",
  "revokedSessionCount": 2,
  "auditEventId": "admin-audit-..."
}
```

Tests needed:

- Cannot disable last super-admin.
- Self-action guardrails.
- Sessions revoked without token exposure.
- Password reset does not enumerate secrets.
- Audit event written for success/failure.

### 6.3 Activity

Routes:

- `GET /api/v1/admin/users/{user_id}/activity`
- `GET /api/v1/admin/activity`

Purpose:

- Normalize user, system, admin, and security activity across execution logs and domain records.

Read/write behavior:

- Read-only.

Permission model:

- Admin read; future support-admin can read redacted timeline.

Privacy/redaction rules:

- Hash request/session ids.
- Redact metadata through `src/utils/security.py` style rules.

Audit requirement:

- Required for user-specific timeline detail.

Response shape sketch:

```json
{
  "items": [
    {
      "id": "evt_...",
      "timestamp": "2026-05-06T00:00:00Z",
      "actor": {"type": "user", "userId": "user-..."},
      "targetUserId": "user-...",
      "family": "portfolio",
      "action": "cash_ledger",
      "entity": {"type": "portfolio_cash_ledger", "idHash": "sha256:..."},
      "status": "success",
      "metadata": {"symbol": "AAPL"}
    }
  ],
  "total": 1
}
```

Tests needed:

- Cross-source ordering.
- Redaction.
- Actor/target filters.
- Query by symbol/request id hash.

### 6.4 Portfolio

Routes:

- `GET /api/v1/admin/users/{user_id}/portfolio-summary`
- `GET /api/v1/admin/users/{user_id}/holdings`
- `GET /api/v1/admin/users/{user_id}/portfolio-activity`

Purpose:

- Read-only admin visibility into user-owned portfolio state.

Read/write behavior:

- Read-only. No accounting writes, no correction edits.

Permission model:

- Admin read with reason-required access for portfolio detail in later phases.

Privacy/redaction rules:

- Broker account references visible only masked or truncated.
- Do not expose broker session tokens, sync tokens, import raw files, or uploaded file contents.

Audit requirement:

- Required for every user portfolio view.

Response shape sketch:

```json
{
  "userId": "user-...",
  "asOf": "2026-05-06",
  "accountCount": 2,
  "holdingCount": 8,
  "currency": "CNY",
  "totalCash": 10000.0,
  "totalMarketValue": 90000.0,
  "risk": {"cashPercent": 10.0, "fxStale": false},
  "auditEventId": "admin-audit-..."
}
```

Tests needed:

- Owner targeting.
- Read-only behavior.
- No portfolio accounting semantic changes.
- Audit event on view.
- Broker refs redacted.

### 6.5 Analysis/scanner/backtest

Routes:

- `GET /api/v1/admin/users/{user_id}/analysis-history`
- `GET /api/v1/admin/users/{user_id}/scanner-runs`
- `GET /api/v1/admin/users/{user_id}/backtests`

Purpose:

- Read-only user activity/data history across analysis, scanner, and backtest domains.

Read/write behavior:

- Read-only.

Permission model:

- Admin read. Future support-admin can read summarized records; raw/collapsed detail requires elevated permission and reason.

Privacy/redaction rules:

- Hide or collapse raw prompt/message/provider payloads.
- Redact errors and URLs.
- Do not change scanner ranking or backtest calculations.

Audit requirement:

- Required for user-specific detail views.

Response shape sketch:

```json
{
  "items": [
    {
      "id": 123,
      "type": "rule_backtest",
      "code": "AAPL",
      "status": "completed",
      "createdAt": "2026-05-06T00:00:00Z",
      "summary": {"totalReturnPct": 4.2, "tradeCount": 8},
      "logLinks": [{"kind": "admin_log", "sessionIdHash": "sha256:..."}]
    }
  ],
  "total": 1
}
```

Tests needed:

- Owner filters.
- Raw payload redaction.
- Pagination.
- Links to logs are safe.

### 6.6 Audit

Routes:

- `GET /api/v1/admin/admin-audit`
- `GET /api/v1/admin/users/{user_id}/admin-access-log`

Purpose:

- Inspect admin access and admin actions against sensitive data/control surfaces.

Read/write behavior:

- Read-only listing of audit events. Events are written by other admin APIs/views.

Permission model:

- Super-admin/security-admin only for broad audit.
- Targeted user access log can be support-admin visible with redaction.

Privacy/redaction rules:

- Do not include secret values.
- Hash or redact target ids when needed.

Audit requirement:

- Viewing admin audit can itself be audited at category level.

Response shape sketch:

```json
{
  "items": [
    {
      "id": "admin-audit-...",
      "actorUserId": "admin-...",
      "targetUserId": "user-...",
      "category": "portfolio_view",
      "action": "view_summary",
      "reason": "support_ticket",
      "outcome": "success",
      "createdAt": "2026-05-06T00:00:00Z"
    }
  ],
  "total": 1
}
```

Tests needed:

- Audit list permissions.
- Audit events written for all sensitive routes.
- No secrets in audit payload.

## 7. Proposed frontend route design

All routes below are proposed only. They should follow existing locale-aware routing patterns in `apps/dsa-web/src/App.tsx` and admin navigation patterns in `SidebarNav.tsx`.

Suggested routes:

- `/zh/admin/users`
- `/zh/admin/users/:userId`
- `/zh/admin/users/:userId/activity`
- `/zh/admin/users/:userId/security`
- `/zh/admin/users/:userId/portfolio`
- `/zh/admin/users/:userId/analysis`
- `/zh/admin/audit`

UI principles:

- Chinese UI labels by default, with i18n entries in `apps/dsa-web/src/i18n/core.ts`.
- WolfyStock Reflect-Linear style, aligned with `docs/codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md` and existing admin pages such as `AdminLogsPage.tsx` and `MarketProviderOperationsPage.tsx`.
- Dense admin/operator layout: filter rail, result table, detail pane, and compact status/risk badges.
- No raw secret-like data visible.
- Developer/raw details collapsed and redacted.
- Clear read-only vs action controls.
- Sensitive actions require confirmation and reason text where applicable.
- Security actions live in a separate tab from read-only user data.
- Every sensitive action/view should mention audit logging.
- Frontend should not invent capabilities before backend contracts exist.

## 8. Permission and audit model

Initial model:

- Reuse `require_admin_user()` for Phase 1 read-only APIs.
- Add a stricter capability helper only when role split is implemented.

Future roles:

- `super-admin`: full admin data read, security controls, role management, audit review.
- `security-admin`: security state/actions, session revocation, account disable/enable, audit review.
- `support-admin`: read-only user directory, redacted activity, summarized analysis/scanner/backtest, limited portfolio aggregate with reason.
- `ops-admin`: provider operations, Admin Logs, runtime health, no user portfolio/security detail unless separately granted.

Audit rules:

- Directory list: category-level audit.
- User detail: target-user audit.
- Security tab: target-user audit on view and action.
- Portfolio tab: target-user audit on every view.
- Raw-ish analysis/scanner/backtest details: target-user audit on drilldown.
- Admin audit views: audit who viewed audit data.

Guardrails:

- Admin cannot disable the last super-admin.
- Admin self-disable, self-role-demotion, and self-session-revocation need explicit guardrails.
- Destructive/security-sensitive operations require dual confirmation or typed confirmation.
- Reason-required access should be enforced server-side, not only by UI.
- All target ids in audit displays should be safe for the viewer's role.

## 9. Password and credential policy

- Never display plaintext password.
- Never display password hash.
- Never export password hash.
- Never display password salt or legacy admin password-hash file contents.
- Never display raw session token, signed cookie, reset token, session secret, or admin unlock token.
- Never display API keys, provider tokens, webhook tokens, notification credentials, or secrets.
- Password reset should generate a one-time reset flow or set a force-change state after a future force-change model exists.
- Session revocation should invalidate active sessions without exposing token values.
- Admin logs should record the action, actor, target, reason, and outcome, not secret values.
- Env var names may appear in design/docs/UI labels, but values must not be returned or printed.

## 10. Portfolio / holdings admin view policy

- Read-only first.
- Allowed summary fields: account count, holding count, total cash, total market value, total equity, realized/unrealized P&L, FX status, risk warning counts, top exposure buckets, and stale data indicators.
- Holdings visibility: symbol, market, currency, quantity, average cost, last price, market value, unrealized P&L, valuation currency, and updatedAt can be visible to roles with portfolio-read permission.
- Cash visibility: currency-level cash totals and cash ledger timeline can be visible to roles with portfolio-read permission; lower roles may receive aggregate-only views.
- Broker account references should be masked or truncated.
- IBKR or broker session tokens must never be stored in admin responses or logs.
- Transaction correction is out of scope unless a future audited correction flow exists.
- No changes to portfolio accounting semantics, replay rules, FX conversion, P&L, exposure, holdings, cash, import dedupe, broker sync, or risk calculations.
- Every admin view of a user's portfolio should be audit-logged.

## 11. Activity timeline design

Normalized event fields:

- `timestamp`
- `actor`: type, role, safe user id, display label
- `targetUserId`
- `routeFamily` or `actionFamily`
- `entityType`
- `entityIdHash`
- `status` / `outcome`
- `sourceIp` and `userAgent` only if already safely available and policy-approved
- `requestIdHash`
- `sessionIdHash`
- `redactedMetadata`

Event classes:

- User-generated activity: login/logout, analysis requests, scanner runs, backtests, portfolio changes/views.
- System/background activity: scheduled tasks, provider refreshes, cache health, background scanner/watchlist work.
- Admin activity: user detail views, portfolio/security views, security actions, settings changes, log cleanup, factory reset, runtime cache reset.
- Failed/security activity: failed login, rate limit, session revoked, disabled-account login, unauthorized admin route access, suspicious repeated failures.

Implementation direction:

- Reuse `ExecutionLogService` summary/readable-event concepts where possible.
- For entity identifiers, prefer hashes or stable opaque ids over raw session/cookie values.
- Do not store raw request bodies for sensitive actions.
- Normalize status values before frontend display.

## 12. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Admin overreach | Split roles; require reason for sensitive views; audit every sensitive access. |
| Privacy leakage | Aggregate-first UX, redaction by default, raw detail collapsed and permission-gated. |
| Secret leakage | Never return credential fields; use `sanitize_metadata()` patterns; add explicit response tests. |
| Accidental data mutation | Read-only phases first; no raw database browser; separate security/correction flows. |
| Support staff seeing too much | Introduce support-admin with redacted views and no security actions. |
| Raw database browser temptation | Build domain-specific APIs and projections only. |
| Performance risk for large logs/histories | Pagination, indexes, time windows, summary endpoints, async export design only after review. |
| Audit log noise | Important-first defaults; category filters; separate audit category from routine operational logs. |
| Legal/compliance expectations | Record access reason, target category, actor, timestamp, and retention policy. |
| Account takeover via weak reset | One-time reset flow, expiry, rate limits, audit, no password reveal, no reset-token display. |

## 13. Rollout plan

### Phase 0: design and schema inventory only

- Scope: document existing tables, owner fields, sensitive fields, current gaps.
- Likely files: `docs/audits/admin-data-control-center-design.md`, follow-up schema inventory doc.
- Tests: docs-only checks.
- Guardrails: no runtime/schema/test changes.
- Parallel: can run in parallel with cost-observability docs.

### Phase 1: read-only Admin User Directory backend API with synthetic tests

- Scope: `/api/v1/admin/users`, safe user list projection.
- Likely files: `api/v1/endpoints/admin_users.py`, `api/v1/schemas/admin_users.py`, router registration, tests.
- Tests: admin/non-admin access, redaction, pagination.
- Guardrails: no password/session raw fields.
- Parallel: can run with docs/schema inventory; coordinate with auth role work.

### Phase 2: read-only User Detail + Activity Timeline backend API

- Scope: user detail, sessions summary, activity timeline.
- Likely files: admin users endpoint/schema, `ExecutionLogService` projection helpers, tests.
- Tests: timeline normalization, redaction, audit event on sensitive view.
- Guardrails: do not expose raw cookies/session ids.
- Parallel: coordinate with User Directory API because auth/admin helpers may be shared.

### Phase 3: read-only Portfolio/Holdings admin view backend API

- Scope: user portfolio summary, holdings, portfolio activity.
- Likely files: admin portfolio endpoint/schema, `PortfolioService` read projections, tests.
- Tests: owner targeting, read-only behavior, audit view event, redaction.
- Guardrails: no accounting semantic changes.
- Parallel: must serialize with portfolio accounting-sensitive changes.

### Phase 4: security actions

- Scope: disable/enable, revoke sessions, reset password, force password change.
- Likely files: admin user/security endpoint/schema, auth repository/storage if new force-change/lock fields are approved, tests.
- Tests: last super-admin guard, self-action guard, session revocation, audit.
- Guardrails: no credential reveal.
- Parallel: serialize after permission/audit model.

### Phase 5: frontend Admin Data Control Center

- Scope: `/zh/admin/users`, user detail tabs, audit route.
- Likely files: `apps/dsa-web/src/App.tsx`, admin pages, API adapters, i18n, tests.
- Tests: route gating, redaction rendering, action confirmations, responsive layout.
- Guardrails: wait for backend contracts.
- Parallel: can run after Phase 1/2 contracts stabilize.

### Phase 6: admin audit hardening and role split

- Scope: durable admin-access events, role/capability split, reason-required access.
- Likely files: auth/admin helpers, audit service, schemas, tests, docs.
- Tests: capability matrix, audit coverage, forbidden cases.
- Guardrails: avoid widening current admin powers without explicit tests.
- Parallel: coordinate across all admin APIs.

## 14. Parallelization plan

| Task | Can run in parallel with | Must serialize after | Likely files touched | Risk level | Notes |
| --- | --- | --- | --- | --- | --- |
| Docs/schema inventory | Cost-observability docs, admin design docs | None | `docs/audits/*` | Low | Docs-only; no runtime changes. |
| User Directory API | Activity API design | Phase 0 inventory | `api/v1/endpoints/admin_users.py`, schemas, tests | Medium | Coordinate shared admin helpers. |
| Activity Timeline API | User Directory API | Initial event normalization design | admin activity schemas, `ExecutionLogService`, tests | Medium | Must preserve existing Admin Logs contracts. |
| Portfolio admin view | Admin audit design | Portfolio accounting-sensitive changes | admin portfolio endpoints/schemas, portfolio read services, tests | High | Serialize with portfolio accounting work. |
| Security actions | None except docs | Permission/audit model | auth repo, admin security endpoint/schema, tests | High | Must protect last super-admin and secrets. |
| Frontend admin routes | UI design docs | Backend contracts | `apps/dsa-web/src/App.tsx`, admin pages, API clients, i18n, tests | Medium | No frontend route before API response shapes settle. |
| Admin audit hardening | Schema inventory | Sensitive route list and permission model | audit service/endpoints/schemas/tests | High | Audit events become compliance-sensitive. |
| Raw database browser | None | Never | N/A | Prohibited | Do not create this task. |

## 15. Recommended next Codex tasks

1. Admin data schema inventory docs-only.
2. Admin User Directory API design, then implementation after design approval.
3. User Activity Timeline API design, then implementation.
4. Portfolio/Holdings admin visibility API design, then implementation.
5. Security controls design: password reset, force change, revoke sessions, disable/enable.
6. Admin Audit Events design, then implementation.
7. Frontend Admin Users route after backend contracts.
8. End-to-end admin data governance QA.

## 16. Implementation status 2026-05-06

- Available backend routes: `GET /api/v1/admin/users`, `GET /api/v1/admin/users/{user_id}`, `GET /api/v1/admin/users/{user_id}/activity`, and `GET /api/v1/admin/activity`.
- Phase 1/2 scope is backend-only and read-only. No frontend admin user routes were added.
- User directory/detail returns safe user/session projections only. Activity timeline currently uses conservative Execution Logs, AnalysisHistory, and auth session sources; portfolio/scanner/backtest deep projections and security actions remain future phases.
- Explicitly unchanged: authentication behavior, authorization behavior beyond adding admin-only read routes, portfolio accounting, scanner scoring/ranking/selection, backtest calculations, provider runtime/fallback order, MarketCache behavior, AI/LLM routing/prompts, notification routing, and DuckDB production runtime.
