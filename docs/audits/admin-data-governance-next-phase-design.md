# Admin Data Governance Next Phase Design

Date: 2026-05-06
Mode: docs-only design. No runtime behavior changed.

## 1. Purpose

This design bundles the next Admin Data Control Center governance surfaces after
the User Directory and Activity Timeline designs:

- Admin Portfolio / Holdings Visibility API Design
- Admin Security Controls API Design
- Admin Audit Events Hardening Design

It is intentionally a design artifact only. It does not implement APIs,
schemas, migrations, frontend UI, tests, runtime behavior, authorization
changes, portfolio accounting changes, scanner/backtest changes, provider
runtime changes, AI/LLM routing changes, notification routing changes, DuckDB
changes, or data mutations.

Implementation note, 2026-05-06:

- The read-only Admin Portfolio Visibility backend API has landed for
  `GET /api/v1/admin/users/{user_id}/portfolio-summary`,
  `GET /api/v1/admin/users/{user_id}/holdings`,
  `GET /api/v1/admin/users/{user_id}/portfolio-activity`, and
  `GET /api/v1/admin/users/{user_id}/portfolio/accounts/{account_id}`.
- The implementation uses safe allowlist projections, target-user portfolio
  ownership joins, masked broker account handles, bounded pagination, and
  best-effort admin-governance audit events via existing execution-log admin
  action patterns.
- It does not add frontend UI, security controls, correction flows, portfolio
  accounting changes, broker sync/import commits, FX refreshes,
  scanner/backtest/provider/MarketCache/AI/notification/DuckDB behavior
  changes, raw broker payload exposure, or raw credential/session exposure.
- The limited Admin Security Controls Phase S1 backend API has landed for
  `POST /api/v1/admin/users/{user_id}/disable`,
  `POST /api/v1/admin/users/{user_id}/enable`, and
  `POST /api/v1/admin/users/{user_id}/revoke-sessions`.
- Phase S1 uses existing `AppUser.is_active`, app-user session revocation,
  `require_admin_user()`, typed confirmations, required reasons,
  self-disable blocking, last-active-admin blocking, and sanitized
  admin-governance audit events. Responses return only safe action status and
  `sessionsRevoked` counts.
- Phase S1 does not implement reset-password, force-password-change, unlock,
  failed-login/lockout models, role/capability migration, security frontend UI,
  password reset token delivery, new migrations, raw session exposure, or
  credential/hash/token exposure.

The target product shape remains a controlled, least-privilege, audited admin
workspace. It must not become a raw database browser and must never reveal
plaintext passwords, password hashes, session IDs, cookies, tokens, API keys,
broker credentials, webhook secrets, provider secrets, reset tokens, or
credential-like values.

## 2. Inputs reviewed

Docs reviewed:

- `docs/audits/admin-data-control-center-design.md`
- `docs/audits/admin-data-schema-inventory.md`
- `docs/audits/admin-user-directory-api-design.md`
- `docs/audits/admin-user-activity-timeline-api-design.md`

Source seams inspected:

- `src/storage.py`
- `src/auth.py`
- `api/deps.py`
- `src/repositories/auth_repo.py`
- `api/v1/endpoints/auth.py`
- `api/v1/endpoints/portfolio.py`
- `src/services/execution_log_service.py`
- `src/utils/security.py`
- Portfolio model/service/repository references through storage, endpoint,
  audit, broker sync, holdings, cash, trade, corporate action, and FX seams
- Scanner, backtest, and analysis storage references only as audit-linkage
  context, without changing their ranking, calculation, prompt, provider, or
  storage semantics

Confirmed current primitives:

- `AppUser` has `id`, `username`, `display_name`, `password_hash`, `role`,
  `is_active`, `created_at`, and `updated_at`.
- `AppUserSession` has `session_id`, `user_id`, `created_at`,
  `last_seen_at`, `expires_at`, and `revoked_at`.
- `CurrentUser`, `is_admin_user()`, and `require_admin_user()` are the current
  admin gate primitives.
- `AuthRepository` supports app-user lookup, create/update, single-session
  revocation, and all-session revocation. It does not currently expose a full
  security-control contract for arbitrary user disable/enable, lockout, failed
  login history, or force-password-change state.
- Portfolio endpoints currently create `PortfolioService(owner_id=current_user.user_id)`
  for user-scoped access and write portfolio audit events through
  `ExecutionLogService.record_portfolio_event()` after successful write paths.
- `ExecutionLogService.record_admin_action()` and `record_portfolio_event()`
  are suitable future audit seams if hardened with a dedicated admin-governance
  helper.
- `sanitize_metadata()`, `sanitize_message()`, and `sanitize_url()` mask
  secret-like metadata, text, and URL fragments.

## 3. Shared principles

- Read-only first: portfolio/holdings visibility starts as read-only admin
  inspection. No correction flow, accounting write, import commit, broker sync,
  cache change, scanner action, or backtest action belongs in this phase.
- Action-only credentials: security controls may reset, force-change, revoke,
  disable/enable, and lock/unlock, but must never reveal credentials.
- No raw secrets: never return plaintext passwords, password hashes, raw
  session IDs, cookies, tokens, API keys, broker credentials, webhook secrets,
  provider secrets, reset tokens, credential-like values, or raw `.env` values.
  Environment variable names may be mentioned; values must not be displayed.
- Audit every sensitive view/action: portfolio summary/detail views, holdings,
  security actions, session revocation, admin audit reads, and failed admin
  attempts need audit events.
- Least privilege: initial pilots can use `require_admin_user()`, but the
  target model must separate support-admin, security-admin, ops-admin, and
  super-admin capabilities.
- No raw database browser: future APIs return explicit safe projections, not
  table dumps, arbitrary SQL output, raw ORM rows, or open JSON browsers.
- Reason-required access: portfolio detail, holdings, security actions, admin
  audit reads, raw-ish diagnostics, and user-owned sensitive data should require
  a bounded reason/context string in future implementation.
- Aggregate first, drilldown second: list/summary routes should expose counts,
  statuses, timestamps, safe labels, and links before detailed rows.
- Explicit allowlists: responses should be built from safe fields, not by
  subtracting sensitive fields from model dictionaries.
- Fail safely: high-sensitivity admin views and security actions should prefer
  fail-closed audit policy unless a later product decision explicitly chooses a
  degraded mode.

## 4. Admin Portfolio / Holdings Visibility API Design

All routes below are proposed future routes only. They do not exist as part of
this document.

### `GET /api/v1/admin/users/{user_id}/portfolio-summary`

Purpose:

- Return a read-only account and valuation overview for one target user.
- Answer whether the user has portfolio accounts, active accounts, holdings,
  cash, broker sync state, FX warnings, and recent ledger activity.

Query params:

- `as_of`: optional ISO date. Defaults to the current portfolio snapshot date
  used by the future service; it must not trigger data refresh.
- `currency`: optional display currency/aggregate currency if already
  supported by portfolio service semantics. It must not change FX accounting.
- `include_inactive`: boolean, default `false`.
- `reason`: required once reason-required sensitive access is enabled.

Response sketch:

```json
{
  "userId": "user-123",
  "accountCount": 2,
  "activeAccountCount": 1,
  "baseCurrencies": ["USD", "CNY"],
  "totalCash": {"amount": 1000.0, "currency": "USD"},
  "totalMarketValue": {"amount": 25000.0, "currency": "USD"},
  "totalEquity": {"amount": 26000.0, "currency": "USD"},
  "realizedPnl": {"amount": 125.0, "currency": "USD"},
  "unrealizedPnl": {"amount": 450.0, "currency": "USD"},
  "fxStatus": {"stale": false, "lastUpdatedAt": "2026-05-06T00:00:00"},
  "brokerSyncSummary": {
    "connections": 1,
    "lastSyncAt": "2026-05-06T00:00:00",
    "statuses": {"success": 1}
  },
  "ledgerCounts": {"trades": 8, "cashEvents": 2, "corporateActions": 1}
}
```

Permission:

- Initial: `require_admin_user()`.
- Future: `users:portfolio:read`; broad summary may be available to
  support-admin, while raw-ish broker diagnostics remain security/super-admin
  only.

Redaction:

- Return no broker token, raw broker payload, `payload_json`,
  `sync_metadata_json`, import-file content, notes by default, or raw account
  reference.
- Broker account references are masked or replaced by stable display handles.

Audit event:

- `admin_portfolio.summary_viewed`
- Include actor, target user, route family, reason/context, filters, outcome,
  count summaries, and request id if available.
- Do not include raw query text, raw account refs, raw payloads, token values,
  or portfolio row dumps.

Required tests:

- Admin required.
- Non-admin forbidden.
- Target user validated.
- Response is read-only and performs no mutations.
- Broker token/ref/raw payload fields are not returned.
- Audit event emitted on success and forbidden/failed access where actor is
  safely resolvable.

### `GET /api/v1/admin/users/{user_id}/holdings`

Purpose:

- Return read-only holdings rows for one user across owned accounts.
- Support support triage without changing holdings, cash, P&L, exposure, FX,
  scanner, or backtest semantics.

Query params:

- `account_id`: optional account filter.
- `symbol`: optional exact symbol filter.
- `market`: optional market filter.
- `currency`: optional display/valuation currency if already supported.
- `include_zero`: boolean, default `false`.
- `limit`: default `50`, max `200`.
- `offset`: default `0`.
- `reason`: required once sensitive-view reason capture is enabled.

Response sketch:

```json
{
  "items": [
    {
      "accountId": 10,
      "accountName": "Main",
      "broker": "IBKR",
      "brokerAccountHandle": "acct_8f21c0",
      "symbol": "AAPL",
      "market": "us",
      "currency": "USD",
      "quantity": 10,
      "avgCost": 150.0,
      "lastPrice": 180.0,
      "marketValueBase": 1800.0,
      "unrealizedPnlBase": 300.0,
      "valuationCurrency": "USD",
      "fxStatus": "current",
      "updatedAt": "2026-05-06T00:00:00"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

Permission:

- Initial: `require_admin_user()`.
- Future: `users:portfolio:read`; lower-privilege admins may need account-level
  masking and reduced P&L/exposure visibility.

Redaction:

- Hide raw broker position refs, raw broker account refs, sync payload JSON,
  metadata JSON, import file details, notes unless explicitly classified, and
  all credential-like values.

Audit event:

- `admin_portfolio.holdings_viewed`

Required tests:

- Admin required and non-admin forbidden.
- Only target user's holdings returned.
- Pagination/filter validation.
- No mutation path called.
- Broker token/ref/raw payload fields absent.
- Audit emitted with safe metadata.

### `GET /api/v1/admin/users/{user_id}/portfolio-activity`

Purpose:

- Return read-only portfolio activity for one user: trades, cash-ledger events,
  corporate actions, import/sync status events, and admin portfolio access
  events where appropriate.

Query params:

- `from`, `to`: bounded date/time window.
- `account_id`: optional account filter.
- `type`: `trade`, `cash`, `corporate_action`, `broker_sync`, `admin_view`, or
  `all`.
- `symbol`: optional exact symbol filter.
- `limit`: default `50`, max `200`.
- `offset`: default `0`.
- `reason`: required for sensitive drilldown.

Response sketch:

```json
{
  "items": [
    {
      "id": "portfolio_activity_...",
      "timestamp": "2026-05-06T00:00:00",
      "type": "trade",
      "accountId": 10,
      "accountName": "Main",
      "symbol": "AAPL",
      "market": "us",
      "currency": "USD",
      "side": "buy",
      "quantity": 10,
      "amount": null,
      "status": "active",
      "noteAvailable": true,
      "source": "portfolio_trades"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

Permission:

- Initial: `require_admin_user()`.
- Future: `users:portfolio:read`; note visibility may require elevated
  capability if notes can contain user-entered sensitive context.

Redaction:

- Do not return raw import rows, full file contents, raw broker payloads,
  broker tokens, raw broker refs, or credential-like values.
- Treat free-form trade/cash/corporate-action notes as sensitive user content:
  expose `noteAvailable` or a short sanitized preview only after classification.

Audit event:

- `admin_portfolio.activity_viewed`

Required tests:

- Admin required and non-admin forbidden.
- Account rows joined through target user's owned accounts only.
- No accounting writes or replay mutations.
- Notes/payloads redacted according to classification.
- Audit emitted for success and failure.

### `GET /api/v1/admin/users/{user_id}/portfolio/accounts/{account_id}`

Purpose:

- Return read-only account-level detail for one target user's portfolio account.
- Support account-specific holdings, cash, broker sync status, FX status, and
  ledger counts without raw payload access.

Query params:

- `include_holdings`: boolean, default `true`.
- `include_cash`: boolean, default `true`.
- `include_activity_summary`: boolean, default `true`.
- `reason`: required for sensitive detail access.

Response sketch:

```json
{
  "account": {
    "id": 10,
    "name": "Main",
    "broker": "IBKR",
    "brokerAccountHandle": "acct_8f21c0",
    "market": "us",
    "baseCurrency": "USD",
    "isActive": true,
    "createdAt": "2026-05-06T00:00:00",
    "updatedAt": "2026-05-06T00:00:00"
  },
  "valuation": {
    "cash": {"amount": 1000.0, "currency": "USD"},
    "marketValue": {"amount": 25000.0, "currency": "USD"},
    "equity": {"amount": 26000.0, "currency": "USD"},
    "realizedPnl": {"amount": 125.0, "currency": "USD"},
    "unrealizedPnl": {"amount": 450.0, "currency": "USD"}
  },
  "brokerSync": {
    "status": "success",
    "lastSyncAt": "2026-05-06T00:00:00",
    "payloadAvailable": true,
    "rawPayloadReturned": false
  }
}
```

Permission:

- Initial: `require_admin_user()`.
- Future: `users:portfolio:read`, with stricter capability for any future raw
  broker diagnostics route.

Redaction:

- Broker refs masked.
- `payload_json` and `sync_metadata_json` hidden/collapsed.
- Broker credentials, session tokens, cookies, API keys, and import file
  contents never returned.

Audit event:

- `admin_portfolio.account_detail_viewed`

Required tests:

- Admin required and non-admin forbidden.
- `account_id` must belong to `user_id`.
- No mutations, no sync triggers, no import commits.
- Raw broker fields absent.
- Audit emitted.

Portfolio policy for the whole phase:

- Read-only first.
- No accounting writes.
- No correction flow in this phase.
- No broker token exposure.
- Broker references masked.
- Raw broker payloads hidden/collapsed.
- Every portfolio view audit-logged.
- No change to holdings, cash, P&L, exposure, FX, import, broker sync,
  scanner, backtest, provider, MarketCache, or AI semantics.

## 5. Portfolio data classification

| Field/source | Visible? | Redaction | Allowed roles | Audit required | Notes |
| --- | --- | --- | --- | --- | --- |
| Account name | Yes | None by default; sanitize display text | support-admin, security-admin, super-admin | Yes | User-owned business data. |
| Broker | Yes | Safe provider/broker label only | support-admin, security-admin, super-admin | Yes | Do not infer credential state beyond configured status. |
| Broker account ref | Limited | Mask/hash/truncate; never raw in broad views | security-admin, super-admin; masked for support-admin | Yes | Financial account identifier. |
| Holdings | Yes | Explicit fields only; no raw payloads | support-admin, security-admin, super-admin | Yes | Read-only; no valuation semantic changes. |
| Cash | Yes | Explicit fields only | support-admin, security-admin, super-admin | Yes | Keep currency/base amount semantics unchanged. |
| Market value | Yes | Explicit numeric projection only | support-admin, security-admin, super-admin | Yes | No recalculation changes. |
| Realized/unrealized P&L | Yes, sensitive | Explicit numeric projection; optional role-based hiding later | support-admin with need-to-know, security-admin, super-admin | Yes | More sensitive than account metadata. |
| FX status | Yes | Status/timestamps/rate source labels only | support-admin, security-admin, super-admin | Yes | Do not change FX freshness or cache behavior. |
| Broker sync `payload_json` | No by default | Hidden/collapsed; raw access requires separate design | super-admin only if future route exists | Yes | May contain raw broker/provider data. |
| `sync_metadata_json` | No by default | Hidden/collapsed; safe summary only | security-admin, super-admin for summary | Yes | May contain provider diagnostics or identifiers. |
| Trade notes | Limited | Default `noteAvailable`; sanitized preview only after classification | support-admin with reason, security-admin, super-admin | Yes | Free-form user content. |
| Import files | No by default | Metadata only: type, count, size bucket, hash if retained | super-admin only if future file-access route exists | Yes | No raw file browser in this phase. |
| IBKR session token | No | Never stored/displayed/returned; mask if encountered in logs | No role | Yes for sync attempt outcome only | Request-only credential-like value. |

## 6. Admin Security Controls API Design

All routes below are proposed future routes only. They are security-sensitive
actions, not credential-reveal endpoints.

Shared request fields:

- `reason`: required, max length to be defined.
- `confirm`: typed confirmation for dangerous actions such as disable,
  revoke sessions, and reset password.
- `requestId`: optional client idempotency/correlation handle if a future
  implementation supports it.

Shared response fields:

- `targetUserId`
- `action`
- `status`
- `changed`
- `auditEventId`
- `message`
- Optional safe counts, such as revoked session count

Shared hard rules:

- No password reveal.
- No password hash reveal.
- No reset token reveal unless the product explicitly designs safe one-time
  delivery in a separate task.
- No session token, raw `session_id`, or cookie reveal.
- Cannot disable or remove access for the last super-admin/admin authority.
- Self-action guardrails are required for disable, revoke all sessions,
  reset password, role changes, and lock/unlock flows.
- Typed confirmation for dangerous actions.
- Reason required for security actions.
- All success and failure outcomes audited.

### `POST /api/v1/admin/users/{user_id}/disable`

Purpose:

- Disable a target user's application account so future authentication fails.

Request body:

```json
{
  "reason": "Support case SEC-123",
  "confirm": "DISABLE",
  "revokeSessions": true
}
```

Response sketch:

```json
{
  "targetUserId": "user-123",
  "action": "disable",
  "status": "success",
  "changed": true,
  "sessionsRevoked": 2,
  "auditEventId": "audit_..."
}
```

Permission/capability:

- Initial design target: `users:security:write`.
- Allow only security-admin or super-admin once capability tables exist.

Audit event:

- `admin_security.account_disabled`

Failure modes:

- Unauthorized or non-admin.
- Missing capability.
- Target user not found.
- Self-disable blocked unless a separate break-glass flow exists.
- Last super-admin/admin authority blocked.
- Target already disabled.
- Audit write failure should fail closed.

Tests:

- Capability required.
- Cannot disable last super-admin.
- Self-action guardrails.
- Optional session revocation does not expose tokens.
- Audit success/failure.

### `POST /api/v1/admin/users/{user_id}/enable`

Purpose:

- Re-enable a disabled account without revealing or changing credentials.

Request body:

```json
{
  "reason": "Support case SEC-124",
  "confirm": "ENABLE"
}
```

Response sketch:

```json
{
  "targetUserId": "user-123",
  "action": "enable",
  "status": "success",
  "changed": true,
  "auditEventId": "audit_..."
}
```

Permission/capability:

- `users:security:write`.

Audit event:

- `admin_security.account_enabled`

Failure modes:

- Unauthorized or missing capability.
- Target user not found.
- Target already enabled.
- Audit write failure should fail closed.

Tests:

- Capability required.
- Re-enable does not reveal password state beyond safe status.
- Audit success/failure.

### `POST /api/v1/admin/users/{user_id}/reset-password`

Purpose:

- Start a safe reset-password flow for the target user.
- The API must not reveal a plaintext password, password hash, raw reset token,
  cookie, session id, API key, or credential-like value.

Request body:

```json
{
  "reason": "User requested reset",
  "confirm": "RESET_PASSWORD",
  "delivery": "configured_channel"
}
```

Response sketch:

```json
{
  "targetUserId": "user-123",
  "action": "reset-password",
  "status": "accepted",
  "changed": false,
  "delivery": {"mode": "configured_channel", "tokenReturned": false},
  "auditEventId": "audit_..."
}
```

Permission/capability:

- `users:security:write`; likely security-admin or super-admin only.

Audit event:

- `admin_security.password_reset_requested`

Failure modes:

- Unauthorized or missing capability.
- Target user not found.
- No safe delivery channel configured.
- Self-reset blocked or separately confirmed depending on future product
  policy.
- Reset-token storage/delivery model missing.
- Audit write failure should fail closed.

Tests:

- No plaintext password or password hash in response.
- No reset token returned unless a separate safe one-time-delivery design is
  explicitly implemented.
- Audit success/failure.

### `POST /api/v1/admin/users/{user_id}/force-password-change`

Purpose:

- Mark a target user as required to change password at next login after a
  future schema flag exists.

Request body:

```json
{
  "reason": "Credential hygiene review",
  "confirm": "FORCE_PASSWORD_CHANGE"
}
```

Response sketch:

```json
{
  "targetUserId": "user-123",
  "action": "force-password-change",
  "status": "success",
  "changed": true,
  "auditEventId": "audit_..."
}
```

Permission/capability:

- `users:security:write`.

Audit event:

- `admin_security.force_password_change_set`

Failure modes:

- Missing future `force_password_change` model/column.
- Unauthorized or missing capability.
- Target user not found.
- Self-action guardrails.
- Audit write failure should fail closed.

Tests:

- Migration-dependent flag behavior when implemented.
- Response contains no credential values.
- Audit success/failure.

### `POST /api/v1/admin/users/{user_id}/revoke-sessions`

Purpose:

- Revoke all or selected target-user sessions without revealing raw session IDs
  or cookies.

Request body:

```json
{
  "reason": "Potential account compromise",
  "confirm": "REVOKE_SESSIONS",
  "scope": "all"
}
```

Response sketch:

```json
{
  "targetUserId": "user-123",
  "action": "revoke-sessions",
  "status": "success",
  "changed": true,
  "revokedCount": 3,
  "auditEventId": "audit_..."
}
```

Permission/capability:

- `users:security:write`.

Audit event:

- `admin_security.sessions_revoked`

Failure modes:

- Unauthorized or missing capability.
- Target user not found.
- Self-revocation guardrail or explicit typed confirmation.
- No active sessions.
- Audit write failure should fail closed.

Tests:

- Sessions revoked without token exposure.
- Raw `session_id` and cookie values absent from request logs, response, and
  audit metadata.
- Audit success/failure.

### `POST /api/v1/admin/users/{user_id}/unlock`

Purpose:

- Clear future account lockout state after a lockout model exists.

Request body:

```json
{
  "reason": "User verified identity",
  "confirm": "UNLOCK"
}
```

Response sketch:

```json
{
  "targetUserId": "user-123",
  "action": "unlock",
  "status": "success",
  "changed": true,
  "auditEventId": "audit_..."
}
```

Permission/capability:

- `users:security:write`.

Audit event:

- `admin_security.account_unlocked`

Failure modes:

- Missing future lockout model.
- Unauthorized or missing capability.
- Target user not found.
- Target not locked.
- Audit write failure should fail closed.

Tests:

- Capability required.
- Lockout state cleared only when model exists.
- No token/hash exposure.
- Audit success/failure.

## 7. Security data model gaps

Existing:

- `AppUser.is_active` exists and can support future disable/enable semantics
  after guardrails are designed.
- `AppUserSession` revocation exists through single-session and all-session
  repository/database methods.
- `AppUser.password_hash` exists but must remain hidden from all admin
  projections.
- Current role is a string field and `require_admin_user()` checks admin role.

Missing or not confirmed:

- `force_password_change` flag may not exist. Future implementation would
  require a migration and login-flow handling.
- Failed login table may not exist. Future failed-login visibility or lockout
  policy would require a migration/storage design.
- Lockout table/columns may not exist. Future lock/unlock controls would
  require a migration and auth-flow integration.
- Role/capability table may not exist. Future support-admin/security-admin/
  super-admin split would require a capability model, migration, and dependency
  helpers.
- Safe password reset token delivery/storage model is not confirmed. Future
  reset-password implementation must design one-time delivery safely before any
  token is generated or exposed.
- Last super-admin/admin authority detection is not a standalone helper today.
  Future disable/security-write implementation must add this guard before any
  security actions ship.

No migration, schema change, auth behavior change, or security implementation
is part of this document.

## 8. Admin Audit Events Hardening Design

Proposed event categories:

| Event | Actor | Target | Action | Outcome | Route/action family | Reason/context | Safe metadata | Forbidden metadata |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `admin_user_directory.list` | admin actor id/role | directory scope | list users | success/failed/forbidden | `/api/v1/admin/users` | optional for broad list | filters used, limit, offset, result count | raw `q`, passwords, hashes, sessions, cookies |
| `admin_user_directory.detail` | admin actor id/role | target user id/hash | view user detail | success/failed/forbidden | `/api/v1/admin/users/{user_id}` | recommended | included sections, session count | raw session IDs, cookies, password state values beyond safe enum |
| `admin_user_activity.viewed` | admin actor id/role | target user id/hash or global scope | view activity | success/failed/forbidden | `/api/v1/admin/users/{user_id}/activity` or `/api/v1/admin/activity` | recommended | categories, date window, result count | raw messages, raw request bodies, raw prompt/report payloads |
| `admin_portfolio.summary_viewed` | admin actor id/role | target user id/hash | view portfolio summary | success/failed/forbidden | portfolio summary | required | account counts, filters, result count | broker refs, raw payloads, tokens, import rows |
| `admin_portfolio.holdings_viewed` | admin actor id/role | target user id/hash | view holdings | success/failed/forbidden | holdings | required | account filter present, symbol filter present, count | raw broker refs, raw position refs, payload JSON |
| `admin_security.account_disabled` | security-admin/super-admin | target user id/hash | disable account | success/failed/blocked | security control | required | changed flag, revoke-session count | password/hash/session IDs/cookies |
| `admin_security.account_enabled` | security-admin/super-admin | target user id/hash | enable account | success/failed/blocked | security control | required | changed flag | password/hash/session IDs/cookies |
| `admin_security.password_reset_requested` | security-admin/super-admin | target user id/hash | request password reset | accepted/failed/blocked | security control | required | delivery mode, tokenReturned=false | plaintext password, password hash, reset token |
| `admin_security.force_password_change_set` | security-admin/super-admin | target user id/hash | force password change | success/failed/blocked | security control | required | changed flag | password/hash/token values |
| `admin_security.sessions_revoked` | security-admin/super-admin | target user id/hash | revoke sessions | success/failed/blocked | security control | required | revoked count, scope | raw session IDs, cookies, bearer tokens |
| `admin_audit.viewed` | admin actor id/role | audit scope or target user hash | view admin audit | success/failed/forbidden | audit logs | required | filters, window, result count | raw request bodies, raw q, secrets, credential values |

Event design requirements:

- Actor: current admin id, username/display label where safe, role, future
  capability set or role family, and hashed/truncated request/session handles.
- Target: target user id or audit hash; target entity handle when safe; never
  raw session/cookie/token values.
- Action: stable machine-readable event name.
- Outcome: success, failed, forbidden, blocked, validation_error, or partial.
- Route/action family: route template or action family, not full raw URL if it
  can contain sensitive query text.
- Reason/context: required for sensitive views/actions, bounded length,
  sanitized, and never treated as a secret store.
- Safe metadata: counts, booleans, enum filters, timestamps, redacted handles,
  coarse status labels.
- Forbidden metadata: raw request bodies, raw free-text query, credentials,
  tokens, cookies, password hashes, raw broker payloads, raw provider payloads,
  raw prompts/messages, raw uploaded files, raw import rows, and secret values.

## 9. Audit storage and redaction policy

Design:

- Reuse `ExecutionLogService.record_admin_action()` and
  `record_portfolio_event()` concepts where suitable, but introduce a dedicated
  future admin-governance audit helper before security controls ship.
- The helper should enforce event names, required reason for sensitive actions,
  actor/target shape, safe metadata allowlists, and forbidden-key rejection.
- Use existing sanitizers as a baseline, then add explicit allowlists for
  high-sensitivity admin events.
- Store route templates/action families rather than raw URLs when query text can
  include sensitive data.
- Store whether `q` was present and which fields were searched, not raw `q`, for
  sensitive admin search.
- Never store raw request bodies for security controls or portfolio views.
- Never store secret values, token values, password hashes, cookies, broker
  credentials, provider secrets, webhook secrets, reset tokens, or credential-
  like values.
- Target ids may be raw only when already visible to super-admin in that
  surface. Otherwise use hash/truncate. Display surfaces can choose stricter
  redaction than storage.
- Audit failure policy: fail closed for high-sensitivity security actions,
  portfolio detail/holdings views, and admin audit reads unless a later product
  decision explicitly chooses fail-open with degraded visibility.
- Audit display policy: admin audit readers must themselves be audited through
  `admin_audit.viewed`.

## 10. Role/capability model

Initial pilot:

- Use `require_admin_user()` for read-only pilot APIs while response projection,
  audit coverage, and route tests are established.

Future roles:

- `super-admin`: full admin governance authority, including security controls,
  role/capability management, and admin audit reads.
- `security-admin`: account security controls, session revocation, lock/unlock,
  password reset workflow, and security audit reads.
- `support-admin`: read-only user directory, safe user detail, activity
  timeline, and masked portfolio/holdings views when reason is supplied.
- `ops-admin`: operational/admin-log/provider/runtime health surfaces without
  user-owned portfolio or security write authority by default.

Capability examples:

- `users:read`
- `users:activity:read`
- `users:portfolio:read`
- `users:security:read`
- `users:security:write`
- `admin_audit:read`

Future dependency helpers:

- `require_admin_capability("users:read")`
- `require_admin_capability("users:portfolio:read")`
- `require_admin_capability("users:security:write")`
- `require_reason_for_sensitive_access(...)`
- `assert_not_self_destructive_action(...)`
- `assert_not_last_super_admin(...)`

These helpers are future design targets only and are not implemented here.

## 11. Implementation sequencing

Phase A: portfolio visibility backend design implementation

- Implement read-only portfolio summary/holdings/account/activity projections
  after User Directory backend exists.
- Reuse owner-linked portfolio account joins; do not bypass target-user
  validation.
- Add audit on every sensitive view before exposing frontend UI.
- Preserve portfolio accounting, holdings, cash, P&L, exposure, FX, import,
  broker sync, scanner, backtest, provider, MarketCache, AI, and notification
  behavior.

Phase B: audit hardening helper

- Add a dedicated admin-governance audit helper before security-control writes.
- Enforce event names, safe metadata allowlist, forbidden metadata rejection,
  reason capture, target handles, and fail-closed policy for high-sensitivity
  routes.

Phase C: security controls design implementation only after audit helper

- Implement disable/enable/reset/force-change/revoke/unlock only after audit
  helper, self-action guardrails, last-admin guardrails, and missing data-model
  migrations are designed.
- Do not reveal passwords, hashes, reset tokens, raw sessions, cookies, or
  credential-like values.

Phase D: frontend after backend contracts

- Build Admin Data Control Center UI only after backend response contracts,
  audit behavior, capability gates, and redaction tests exist.
- No raw database browser UI.

## 12. Parallelization plan

| Task | Can run in parallel with | Must serialize after | Likely files touched | Risk | Notes |
| --- | --- | --- | --- | --- | --- |
| Portfolio read API design implementation | Admin audit helper design, frontend wireframe docs | User Directory backend contract | `api/v1/endpoints/admin_users*.py`, `api/v1/schemas/admin_portfolio*.py`, `src/services/*admin*portfolio*`, tests | Medium | Read-only; must join account rows through target user and audit every view. |
| Portfolio audit event coverage | Portfolio read API service work | Audit event naming policy | `src/services/execution_log_service.py` or new admin audit helper, tests | Medium | No raw payloads in audit metadata. |
| Audit hardening helper | Portfolio read API design, docs | None, but should precede security writes | `src/services/*audit*`, `src/utils/security.py`, tests | Medium/high | Central safety dependency for security controls. |
| Security controls backend API | None for write paths | Audit helper, self-action guard, last-admin guard, needed migrations | auth endpoint/admin endpoint files, auth repo/storage migrations, tests | High | Mutating security-sensitive work; no credential reveal. |
| Capability model | Audit helper docs/tests | Role/capability schema decision | deps/auth/storage/schema/tests | High | Requires migration and auth dependency changes. |
| Frontend Admin Users/Data Control Center | Docs-only planning, backend tests | Backend contracts and audit behavior | `apps/dsa-web/**` | Medium/high | UI must not invent fields or expose raw data. |
| End-to-end admin governance QA | Docs-only follow-ups | Backend + frontend implementation | e2e/tests/docs | Medium | Browser validation only when UI exists. |
| Raw database browser | Nothing | Never scheduled | N/A | Prohibited | Explicit non-goal. |

Explicit sequencing:

- Portfolio read API can run after User Directory backend.
- Security controls must wait for audit helper and self/last-admin guard design.
- Frontend waits for backend contracts.
- No raw database browser task should be created.

## 13. Required tests for future implementation

Portfolio:

- Admin required.
- Non-admin forbidden.
- Target user exists and target-user ownership is enforced.
- User-targeted only; no cross-user leakage.
- Read-only/no mutation; no sync/import/replay/cache refresh side effects.
- Broker token not returned.
- Raw broker account refs masked.
- Raw payload and sync metadata not returned.
- Import files not returned.
- Portfolio views emit audit events.
- Audit metadata contains only safe fields.

Security:

- Admin/security capability required.
- Non-admin forbidden.
- Support-admin cannot perform write controls if role split exists.
- Cannot disable last super-admin/admin authority.
- Self-action guardrails for disable, reset, revoke, lock/unlock.
- Typed confirmation required for dangerous actions.
- Reason required for all security actions.
- Sessions revoked without token, cookie, or raw session id exposure.
- Password reset does not expose plaintext password, password hash, or reset
  token unless a separate safe one-time delivery design is implemented.
- Success, failure, forbidden, and blocked outcomes are audited.
- Audit write failure fails closed for security actions.

Audit:

- Every sensitive route emits an event.
- Forbidden and failed attempts emit an event when actor is safely resolvable.
- Redaction masks secret-like metadata recursively.
- No secrets, password hashes, cookies, tokens, raw request bodies, broker
  payloads, raw provider payloads, raw prompts, raw files, or credential-like
  values appear in stored or returned audit projections.
- Raw `q` is not stored for sensitive searches.
- Admin audit reads emit `admin_audit.viewed`.
- High-sensitivity audit failure behavior matches fail-closed policy.

## 14. Recommended next implementation prompts

1. Admin Portfolio Visibility backend API

   Implement read-only admin portfolio summary, holdings, activity, and account
   detail APIs for target users, using safe allowlist projections, masked broker
   references, no raw broker payloads, and audit events on every view. Preserve
   portfolio accounting, FX, broker sync, import, scanner, backtest, provider,
   MarketCache, AI, notification, and DuckDB runtime behavior.

2. Admin Audit Events hardening helper

   Add a central admin-governance audit helper that enforces event names,
   reason-required sensitive access, safe metadata allowlists, forbidden
   metadata rejection, target/actor handles, and fail-closed behavior for
   security actions and sensitive portfolio/admin-audit views.

3. Admin Security Controls backend API

   After the audit helper and guardrails exist, implement account disable,
   enable, reset-password request, force-password-change, revoke-sessions, and
   unlock APIs with typed confirmations, reason capture, self-action guardrails,
   last-super-admin/admin protection, and no credential/session/token exposure.

4. Frontend Admin Users/Data Control Center after backend contracts

   Build the Admin Data Control Center UI only from backend contracts. Keep
   security controls action-only, portfolio visibility read-only, reason capture
   visible for sensitive access, and admin audit links explicit. Do not add a
   raw database browser or raw payload viewer.

5. End-to-end admin governance QA

   Validate admin/non-admin permissions, redaction, reason-required access,
   audit success/failure behavior, portfolio read-only behavior, security
   guardrails, and absence of secrets across API responses, audit records, and
   frontend surfaces.
