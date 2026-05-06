# Admin User Directory API Design

Status: Partial
Owner domain: Admin data governance
Related docs: `docs/audits/admin-data-control-center-design.md`, `docs/audits/admin-data-governance-next-phase-design.md`

Date: 2026-05-06
Mode: docs-only API design. No runtime behavior changed.

## 1. Purpose

This note designs a future read-only Admin User Directory and User Detail API. It expands the user-directory portion proposed in `docs/audits/admin-data-control-center-design.md` into an implementation-ready backend contract for:

- `GET /api/v1/admin/users`
- `GET /api/v1/admin/users/{user_id}`

The API is for safe administrative inspection of application users and their authentication/session metadata. It is not a raw database browser, not a security-control API, and not an activity timeline API. It must never return password hashes, raw session IDs, signed cookies, tokens, API keys, secrets, credentials, or raw user-owned business payloads.

## 2. Current confirmed primitives

Static inspection confirms these implementation seams:

- `src/storage.py` defines `AppUser` in `app_users` with `id`, `username`, `display_name`, `password_hash`, `role`, `is_active`, `created_at`, and `updated_at`.
- `src/storage.py` defines `AppUserSession` in `app_user_sessions` with `session_id`, `user_id`, `created_at`, `last_seen_at`, `expires_at`, and `revoked_at`.
- `api/deps.py` defines `CurrentUser`, `resolve_current_user()`, `get_current_user()`, `is_admin_user()`, `ensure_current_user_matches_owner()`, and `require_admin_user()`. Existing admin-only APIs use `Depends(require_admin_user)`.
- `src/auth.py` signs the `dsa_session` cookie, resolves signed cookies with `get_session_identity()`, stores app-user credential hashes through `hash_password_for_storage()`, verifies hashes through `verify_password_hash_string()`, creates session tokens, and rotates session secrets. The signed cookie value and the persisted session secret are credential material and must not be exposed.
- `src/repositories/auth_repo.py` is the narrow auth repository seam. It currently exposes `get_app_user()`, `get_app_user_by_username()`, `create_or_update_app_user()`, `create_app_user_session()`, `revoke_app_user_session()`, and `revoke_all_app_user_sessions()`. It does not yet expose a read-only paginated user list or user-session summary helper.
- `src/storage.py` currently exposes single-user lookup helpers and session mutation helpers, plus private SQLite helpers for active session IDs. A future implementation should add explicit read helpers instead of making endpoint code issue ad hoc ORM queries.
- `api/v1/endpoints/admin_logs.py` and `api/v1/endpoints/market_provider_operations.py` show the current admin endpoint pattern: `APIRouter()`, `response_model=...`, bounded `Query(...)` parameters, and `_: CurrentUser = Depends(require_admin_user)`.
- `api/v1/router.py` registers admin surfaces under the `/api/v1` router, with `admin_logs.router` mounted at `/admin/logs` and `market_provider_operations.router` mounted under `/admin`.
- `api/v1/schemas/admin_logs.py` and `api/v1/schemas/market_provider_operations.py` show the current Pydantic response-model pattern for admin read-only surfaces.
- `src/utils/security.py` provides `is_sensitive_key()`, `mask_secret()`, `sanitize_url()`, `sanitize_message()`, and `sanitize_metadata()` for masking secret-like fields in logs or metadata.
- `src/services/execution_log_service.py` and Phase G control-plane helpers provide the existing admin/audit logging seam for admin actions and execution logs.
- `docs/audits/admin-data-schema-inventory.md` confirms the same user/session sensitive-field policy: list/detail projections may expose user id, username, display name, role, active status, created/updated timestamps, session counts, lifecycle timestamps, and redacted session handles; they must not expose `password_hash`, legacy credential files, signed cookies, raw `session_id`, `.session_secret`, reset/admin-unlock token values, or password request fields.

Confirmed gaps relevant to this design:

- No verified `/api/v1/admin/users` endpoint exists.
- No verified `/api/v1/admin/users/{user_id}` endpoint exists.
- No public safe projection exists for `AppUser.password_hash`; the future API must explicitly exclude it.
- No public safe projection exists for `AppUserSession.session_id`; the future API must expose only a derived display handle.
- There is no current per-user failed-login table, lockout table, password-change timestamp, client IP, user-agent, or permission-capability table in the inspected primitives. Fields that depend on those concepts must be marked future-only until implemented.

## 3. Route design

Both routes are read-only. They must not create, update, delete, revoke, rotate, probe, call providers, run live APIs, or change auth behavior.

### `GET /api/v1/admin/users`

Purpose:

- Return a paginated, filtered, privacy-safe directory of application users.
- Show account metadata, derived session counts, derived last-seen timestamp, and safe risk/attention badges.
- Provide enough information for an admin to decide whether to open a user detail view without exposing credentials or raw user-owned data.

Permission:

- Initial implementation: `Depends(require_admin_user)`.
- Future role split: replace or wrap this with a stricter `users:read` capability after the auth/role model supports it.

Query parameters:

| Param | Type | Default | Limit / allowed values | Semantics |
| --- | --- | --- | --- | --- |
| `q` | string | none | trim, max 128 chars | Case-insensitive search across `id`, `username`, and `display_name`. Do not search password hashes, cookies, raw session IDs, or user-owned business payloads. |
| `role` | string | none | `admin`, `user` initially | Exact role filter using current normalized role values. Unknown roles should return `400 validation_error` unless a future role table defines them. |
| `status` | string | `all` | `all`, `active`, `inactive`, `needs_password`, `sessionless`, `stale_session` | Derived coarse state. `needs_password` means `password_hash` is null or empty, but the hash value is never returned. |
| `active` | bool | none | `true` or `false` | Exact `AppUser.is_active` filter. If both `status` and `active` are provided, they must agree or return `400 validation_error`. |
| `created_from` | ISO datetime | none | inclusive | Filter by `AppUser.created_at >= created_from`. |
| `created_to` | ISO datetime | none | inclusive | Filter by `AppUser.created_at <= created_to`. |
| `last_seen_from` | ISO datetime | none | inclusive | Filter by derived `lastSeenAt >= last_seen_from`, where `lastSeenAt` is `max(AppUserSession.last_seen_at)` for that user. |
| `last_seen_to` | ISO datetime | none | inclusive | Filter by derived `lastSeenAt <= last_seen_to`. |
| `limit` | integer | `50` | min `1`, max `200` | Hard cap at the API boundary. Larger values return `400 validation_error`; do not silently uncap. |
| `offset` | integer | `0` | min `0`, max `10000` | Offset pagination only for the first implementation. Cursor pagination can be added later without removing `offset`. |
| `sort` | string | `created_at_desc` | `created_at_desc`, `created_at_asc`, `updated_at_desc`, `username_asc`, `username_desc`, `last_seen_desc`, `last_seen_asc` | Stable sort. Add `id` as a deterministic tie-breaker. |

Response shape:

```json
{
  "items": [
    {
      "id": "user-123",
      "username": "alice",
      "displayName": "Alice",
      "role": "user",
      "isActive": true,
      "createdAt": "2026-05-06T00:00:00",
      "updatedAt": "2026-05-06T00:00:00",
      "passwordState": "set",
      "lastSeenAt": "2026-05-06T08:00:00",
      "sessionSummary": {
        "activeCount": 1,
        "expiredCount": 0,
        "revokedCount": 0,
        "lastSeenAt": "2026-05-06T08:00:00",
        "nextExpiresAt": "2026-05-07T08:00:00"
      },
      "riskBadges": [],
      "links": {
        "self": "/api/v1/admin/users/user-123",
        "adminLogs": "/api/v1/admin/logs?user_id=user-123"
      }
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0,
  "hasMore": false
}
```

Audit behavior:

- Emit one category-level admin access event for a successful list request.
- Log actor user id, actor role, route, outcome, filter categories used, result count, limit, and offset.
- Do not log raw `q` when it could contain sensitive free text. Prefer a boolean such as `query_present` and a normalized field list.
- Do not log password hashes, raw session IDs, cookies, tokens, API keys, secrets, or credential values.

Errors:

- `401 unauthorized`: no current user when auth requires login.
- `403 admin_required`: current user is not admin.
- `400 validation_error`: invalid datetime, unknown role/status/sort, conflicting `status` and `active`, over-limit `limit`, or over-limit `offset`.
- `500 internal_error`: unexpected storage failure, with sanitized logs only.

### `GET /api/v1/admin/users/{user_id}`

Purpose:

- Return a privacy-safe user detail projection for one application user.
- Include account metadata, derived security/session summary, redacted session summaries, safe risk/attention badges, and links to related admin surfaces.
- Avoid becoming the User Activity Timeline API. Full cross-domain activity belongs in a separate activity endpoint.

Permission:

- Initial implementation: `Depends(require_admin_user)`.
- Future role split: `users:read` for this read-only detail. More sensitive subviews should use separate capabilities.

Path parameter:

- `user_id`: exact `AppUser.id`, trimmed, max 64 chars, no wildcard lookup.

Query parameters:

| Param | Type | Default | Limit / allowed values | Semantics |
| --- | --- | --- | --- | --- |
| `include_sessions` | bool | `true` | `true` or `false` | Include redacted recent sessions. Even when true, raw `session_id` is never returned. |
| `session_limit` | integer | `20` | min `1`, max `50` | Maximum number of session summaries returned. |
| `session_status` | string | `all` | `all`, `active`, `expired`, `revoked` | Filter returned session summaries only. |

Response shape:

```json
{
  "user": {
    "id": "user-123",
    "username": "alice",
    "displayName": "Alice",
    "role": "user",
    "isActive": true,
    "createdAt": "2026-05-06T00:00:00",
    "updatedAt": "2026-05-06T00:00:00",
    "passwordState": "set",
    "lastSeenAt": "2026-05-06T08:00:00",
    "sessionSummary": {
      "activeCount": 1,
      "expiredCount": 0,
      "revokedCount": 0,
      "lastSeenAt": "2026-05-06T08:00:00",
      "nextExpiresAt": "2026-05-07T08:00:00"
    },
    "riskBadges": [],
    "links": {
      "self": "/api/v1/admin/users/user-123",
      "adminLogs": "/api/v1/admin/logs?user_id=user-123"
    }
  },
  "sessions": [
    {
      "sessionHandle": "sess_4f8a1c9b",
      "status": "active",
      "createdAt": "2026-05-06T07:00:00",
      "lastSeenAt": "2026-05-06T08:00:00",
      "expiresAt": "2026-05-07T08:00:00",
      "revokedAt": null
    }
  ],
  "dataLinks": {
    "adminLogs": "/api/v1/admin/logs?user_id=user-123",
    "activity": null,
    "portfolio": null,
    "analysis": null,
    "scanner": null,
    "backtest": null
  },
  "limitations": [
    "failed_login_count_unavailable",
    "client_device_metadata_unavailable"
  ]
}
```

Audit behavior:

- Emit one target-level admin access event for a successful detail request.
- Log actor user id, actor role, target user id or a stable target-user audit hash, route, outcome, included categories, and session-summary count.
- Do not log raw session handles if they are derived from session IDs. If a handle is needed in logs, hash it again under an audit-specific purpose.
- Emit a failed access event for forbidden detail access when the actor can be resolved safely.

Errors:

- `401 unauthorized`: no current user when auth requires login.
- `403 admin_required`: current user is not admin.
- `404 not_found`: no `AppUser` exists for the provided `user_id`.
- `400 validation_error`: invalid `user_id`, invalid session filters, or over-limit `session_limit`.
- `500 internal_error`: unexpected storage failure, with sanitized logs only.

## 4. Response schemas

Future schema file:

- `api/v1/schemas/admin_users.py`

Suggested Pydantic models:

### `AdminUserListResponse`

Fields:

- `items: list[AdminUserListItem]`
- `total: int`
- `limit: int`
- `offset: int`
- `hasMore: bool`
- `summary: dict | AdminUserDirectorySummary` optional future addition for count rollups

### `AdminUserListItem`

Fields:

- `id: str`
- `username: str`
- `displayName: str | None`
- `role: str`
- `isActive: bool`
- `createdAt: str | None`
- `updatedAt: str | None`
- `passwordState: "set" | "unset" | "unknown"`
- `lastSeenAt: str | None`
- `sessionSummary: AdminSessionSummaryCounts`
- `riskBadges: list[AdminUserRiskBadge]`
- `links: AdminDataLinks`

Rules:

- `passwordState` is derived from whether `password_hash` is present, not from its value.
- `lastSeenAt` is derived from session metadata and may be null.
- Do not include raw user-owned activity, portfolio rows, analysis reports, scanner candidates, or backtest results in the list item.

### `AdminUserDetailResponse`

Fields:

- `user: AdminUserListItem`
- `sessions: list[AdminSessionSummary]`
- `dataLinks: AdminDataLinks`
- `limitations: list[str]`
- `metadata: dict` optional, redacted and bounded only

Rules:

- Detail may include redacted recent session summaries.
- Detail may include links to future activity, portfolio, analysis, scanner, and backtest admin APIs.
- Detail must not inline raw business-domain payloads.

### `AdminSessionSummary`

Fields:

- `sessionHandle: str`
- `status: "active" | "expired" | "revoked"`
- `createdAt: str | None`
- `lastSeenAt: str | None`
- `expiresAt: str | None`
- `revokedAt: str | None`

Rules:

- `sessionHandle` must be a display-only derived value, for example `sess_` plus a short server-side hash of the raw `session_id`.
- The raw `AppUserSession.session_id` must never be returned.
- The signed cookie value must never be returned.
- Do not infer client IP, user agent, device, or geolocation because current session primitives do not store those fields.

### `AdminSessionSummaryCounts`

Fields:

- `activeCount: int`
- `expiredCount: int`
- `revokedCount: int`
- `lastSeenAt: str | None`
- `nextExpiresAt: str | None`

Rules:

- `activeCount` means sessions with `revoked_at is null` and `expires_at` in the future.
- `expiredCount` means sessions with `revoked_at is null` and `expires_at` in the past.
- `revokedCount` means sessions with `revoked_at is not null`.
- `lastSeenAt` is the latest available `last_seen_at` across the user's sessions.
- `nextExpiresAt` is the nearest future `expires_at` among active sessions.

### `AdminUserRiskBadge`

Fields:

- `code: str`
- `label: str`
- `severity: "info" | "warning" | "critical"`
- `reason: str | None`
- `source: "auth" | "session" | "future_activity" | "future_security"`

Initial badge codes supported by current primitives:

- `admin_account`
- `inactive_account`
- `password_unset`
- `sessionless`
- `all_sessions_expired`
- `revoked_sessions_present`
- `stale_session`

Future-only badge codes, not implementable from the inspected primitives without new data:

- `failed_login_spike`
- `locked_account`
- `force_password_change_required`
- `high_admin_access_volume`
- `credential_rotation_required`

### `AdminDataLinks`

Fields:

- `self: str | None`
- `adminLogs: str | None`
- `activity: str | None`
- `portfolio: str | None`
- `analysis: str | None`
- `scanner: str | None`
- `backtest: str | None`

Rules:

- Links are navigation/drilldown hints, not embedded data.
- Links to future routes should be null until those routes exist.
- Existing Admin Logs links may use the current safe filter shape, for example `/api/v1/admin/logs?user_id={user_id}`.

Explicitly excluded from every response:

- `password_hash`
- legacy `.admin_password_hash` contents
- raw `session_id`
- signed cookie values
- session secret values
- reset tokens
- API keys
- provider keys
- webhook URLs that contain credentials
- bearer tokens
- authorization headers
- private keys
- raw secrets or credential values
- raw prompts, raw model messages, raw provider payloads, uploaded files, and raw business-domain payloads

## 5. Redaction and privacy

Field policy:

| Source field / data | API policy | Notes |
| --- | --- | --- |
| `AppUser.id` | Return | Stable account identifier. Required for routing and admin support. |
| `AppUser.username` | Return | Searchable directory field. |
| `AppUser.display_name` | Return | Safe profile metadata. |
| `AppUser.role` | Return | Current coarse auth role. |
| `AppUser.is_active` | Return as `isActive` | Safe account status. |
| `AppUser.created_at` / `updated_at` | Return | Safe timestamps. |
| `AppUser.password_hash` | Never return | Derive only `passwordState`. Do not log the value. |
| legacy `.admin_password_hash` | Never read for response | Credential file is outside the API contract. |
| `AppUserSession.session_id` | Never return | Derive only `sessionHandle` with a server-side hash. |
| signed `dsa_session` cookie | Never return | Credential material. |
| `AppUserSession.created_at` / `last_seen_at` / `expires_at` / `revoked_at` | Return | Safe session lifecycle metadata. |
| user notification preferences | Exclude from this API | Notification targets can be personal data and belong in a separate scoped design. |
| analysis/scanner/backtest/portfolio payloads | Exclude from this API | Provide links only; separate APIs define their own redaction. |
| execution-log metadata | Exclude from user detail except safe links | Use Admin Logs APIs for sanitized log drilldown. |

Sanitization rules:

- Any metadata added later must pass through `sanitize_metadata()` or an equivalent stricter allowlist.
- Free-form messages must pass through `sanitize_message()`.
- URL-like values must pass through `sanitize_url()`.
- Prefer explicit allowlists over recursive sanitization for this API because the response shape is small and security-sensitive.
- Do not return arbitrary ORM `__dict__` payloads or serialize database rows directly.
- Do not include raw query strings in audit metadata. Log bounded filter names and booleans instead.

Privacy boundaries:

- Directory list is aggregate-first and should only reveal safe account metadata.
- User detail is still read-only and should only reveal account/session metadata.
- Security actions such as disable, enable, password reset, force password change, and session revoke are out of scope for this API and require separate designs, permissions, tests, and audit rules.
- User Activity Timeline is out of scope for this API. It should be a separate audited route that can define cross-domain redaction independently.

## 6. Audit model

What to audit:

- Successful directory list access as a category-level event, for example `admin_user_directory.list`.
- Successful user detail access as a target-level event, for example `admin_user_directory.detail`.
- Failed forbidden access attempts when the request actor can be resolved safely.
- Validation failures that indicate suspicious access patterns, such as repeated invalid `sort`, over-limit `limit`, or malformed `user_id`, if the logging volume is bounded.

List audit payload:

- `actor_user_id`
- `actor_role`
- `route`: `/api/v1/admin/users`
- `event_type`: `admin_user_directory.list`
- `outcome`: `success` or `failed`
- `filter_keys`: names only, such as `["role", "active", "created_from"]`
- `query_present`: boolean
- `limit`
- `offset`
- `result_count`

Detail audit payload:

- `actor_user_id`
- `actor_role`
- `route`: `/api/v1/admin/users/{user_id}`
- `event_type`: `admin_user_directory.detail`
- `target_type`: `app_user`
- `target_user_id` or an audit-safe target hash
- `outcome`: `success`, `not_found`, or `forbidden`
- `included_categories`: for example `["account", "session_summary", "session_list"]`

What not to log:

- password hashes
- raw session IDs
- signed cookies
- token values
- reset tokens
- API keys
- secrets
- credentials
- raw query text if it may contain personal or secret-like text
- raw user-owned activity payloads
- raw prompts, model messages, provider payloads, or stack traces

Implementation guidance:

- Reuse `ExecutionLogService.record_admin_action()` or the current Phase G admin-log seam if available in the implementation branch.
- Keep audit writes bounded and best-effort only after the user directory read itself succeeds or fails in a controlled way.
- Do not let audit failure expose data or turn read-only directory lookup into a mutation of business-domain tables.

## 7. Implementation plan

Future implementation steps:

1. Add repository read helpers.
   - Add a narrow helper for paginated user directory reads.
   - Add a helper for one user detail plus bounded session summaries.
   - Keep logic in repository/storage/service layers rather than ad hoc endpoint ORM queries.
   - Preserve SQLite/PostgreSQL coexistence behavior and existing fallback posture.

2. Add response schemas.
   - Create `api/v1/schemas/admin_users.py`.
   - Add `AdminUserListResponse`, `AdminUserListItem`, `AdminUserDetailResponse`, `AdminSessionSummary`, `AdminSessionSummaryCounts`, `AdminUserRiskBadge`, and `AdminDataLinks`.
   - Use explicit fields and aliases; never serialize database rows directly.

3. Add endpoint file.
   - Create `api/v1/endpoints/admin_users.py`.
   - Use `APIRouter()`, bounded `Query(...)` declarations, `response_model=...`, and `Depends(require_admin_user)`.
   - Implement strict validation for limit, offset, sort, role, status, and datetime filters.

4. Register routes.
   - Update `api/v1/router.py` to include `admin_users.router` under prefix `/admin` or `/admin/users`, matching existing admin route style.
   - Preserve existing admin routes and tags.

5. Add audit event emission.
   - Record list and detail access events.
   - Record forbidden/not-found outcomes where safe.
   - Redact query/filter details as defined above.

6. Add tests.
   - Cover auth, privacy, query validation, pagination, sorting, inactive users, session summaries, and audit emission.
   - Ensure all tests prove the API is read-only.

7. Update docs when implementation lands.
   - Update this design if the final response contract changes.
   - Update the Admin Data Control Center design index if route availability changes.
   - Update `docs/CHANGELOG.md` for the user-visible admin API when code lands.
   - README update is not required for this docs-only design; it should be evaluated during the future implementation because that is when a user-visible capability actually exists.

## 8. Tests required

Required future tests:

- Admin required: unauthenticated request gets `401` when auth is enabled.
- Admin required: non-admin authenticated user gets `403 admin_required`.
- Admin allowed: admin user can list users.
- Admin allowed: admin user can read one user detail.
- Not found: unknown `user_id` returns `404 not_found`.
- Inactive user handling: inactive users can be filtered and are marked `isActive: false`.
- `status=needs_password` identifies users with missing password hash without returning the hash.
- Pagination: `limit` and `offset` are honored and capped.
- Limit validation: `limit > 200` returns `400 validation_error`.
- Offset validation: negative or over-max offset returns `400 validation_error`.
- Filtering: `q`, `role`, `status`, `active`, `created_from/to`, and `last_seen_from/to` behave as documented.
- Sorting: all allowed `sort` values are stable and deterministic.
- Privacy: `password_hash` never appears anywhere in serialized JSON.
- Privacy: raw `session_id` never appears anywhere in serialized JSON.
- Privacy: signed cookie values, tokens, reset tokens, API keys, secrets, and credentials never appear in serialized JSON or audit metadata.
- Detail sessions: `sessionHandle` is derived and does not equal the persisted `session_id`.
- Audit: directory list emits one category-level access event.
- Audit: user detail emits one target-level access event.
- Audit: forbidden access is audited when the actor can be safely resolved.
- No mutation: list/detail requests do not create users, update users, revoke sessions, rotate secrets, change passwords, call live APIs, or alter business-domain tables.

Minimum local verification for implementation:

- Backend gate or focused pytest for the new endpoint/schemas.
- JSON-response privacy assertions over the full response text, not only typed fields.
- Repository tests over both users with sessions and users without sessions.

## 9. Parallelization

- Compatible with `docs/audits/admin-user-activity-timeline-api-design.md`; this API only returns account/session metadata and links, while the activity design owns cross-domain event timelines.
- Can run in parallel with Activity API implementation work if repository write sets stay separate.
- Should serialize with auth model, role split, capability table, password policy, lockout, failed-login tracking, and session-client-metadata work.
- Frontend implementation should wait for this backend API contract or a compatible mock contract.
- Security-control APIs should be separate follow-up work, not mixed into this read-only implementation.

## 10. Follow-up tasks

- Implement read-only Admin User Directory API. Implemented 2026-05-06 as `GET /api/v1/admin/users`.
- Implement read-only Admin User Detail API. Implemented 2026-05-06 as `GET /api/v1/admin/users/{user_id}` with safe session summaries.
- Implement User Activity Timeline API as a separate audited contract.
- Implement frontend admin user directory and detail routes after the backend contract lands.
- Design security-control APIs separately for disable/enable, password reset, force password change, and session revocation.

## 11. Implementation note 2026-05-06

- Backend routes landed in `api/v1/endpoints/admin_users.py` and are registered under `/api/v1/admin`.
- Safe response schemas landed in `api/v1/schemas/admin_users.py`; directory/detail use `AdminUserService` plus narrow `AuthRepository` read helpers.
- The implementation derives `passwordState` and session counts without returning `password_hash`, raw `session_id`, cookies, tokens, API keys, or secrets.
- Audit writes for directory/detail access are deferred to a later admin-audit hardening pass; the current implementation keeps read paths non-mutating except normal log/table reads.
