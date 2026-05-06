# Admin User Activity Timeline API Design

Status: Partial
Owner domain: Admin data governance
Related docs: `docs/audits/admin-data-control-center-design.md`, `docs/audits/admin-data-governance-next-phase-design.md`

Date: 2026-05-06

Mode: docs-only API design. No runtime behavior changed.

## 1. Purpose

Design a read-only, normalized admin activity timeline for user support, governance, and security review.

The timeline should let an authorized admin answer:

- What did a specific user do recently?
- Which user, guest, admin, or system actor triggered an activity?
- Which analysis, scanner, backtest, portfolio, market/provider, security, or system entity was involved?
- Was the outcome successful, partial, failed, cancelled, skipped, or unknown?
- Which sanitized Admin Logs or execution-log records can support the event?

This design extends the Admin Data Control Center proposal from `docs/audits/admin-data-control-center-design.md`. It proposes future read-only APIs only:

- `GET /api/v1/admin/users/{user_id}/activity`
- `GET /api/v1/admin/activity`

It does not implement endpoints, schemas, services, tests, frontend, migrations, storage changes, authorization changes, or runtime behavior.

## 2. Current confirmed primitives

Confirmed from static inspection:

- `api/deps.py` exposes `CurrentUser`, `resolve_current_user()`, `get_current_user()`, `is_admin_user()`, `ensure_current_user_matches_owner()`, and `require_admin_user()`. Existing admin endpoints use `Depends(require_admin_user)`.
- `src/storage.py` defines `AppUser` with `id`, `username`, `display_name`, `password_hash`, `role`, `is_active`, `created_at`, and `updated_at`.
- `src/storage.py` defines `AppUserSession` with `session_id`, `user_id`, `created_at`, `last_seen_at`, `expires_at`, and `revoked_at`.
- `src/storage.py` defines `ExecutionLogSession` with `session_id`, `task_id`, `query_id`, `analysis_history_id`, `code`, `name`, status, summary, and timestamps.
- `src/storage.py` defines `ExecutionLogEvent` with `session_id`, `event_at`, `phase`, `step`, `target`, `status`, message, error code, and `detail_json`.
- `src/services/execution_log_service.py` is the current admin observability seam. It provides `list_business_events()`, `get_business_event_detail()`, `list_sessions()`, `get_session_detail()`, `summarize_items()`, and `summarize_business_events()`.
- `ExecutionLogService.list_business_events()` already supports filters for category, type, subject, symbol, scanner id, strategy id, backtest id, request id, user id, status, query, date range, limit, and offset. It caps requested limits at 200.
- `ExecutionLogService.list_sessions()` already supports session-oriented filters for task id, stock code, status, log level, category, query, provider, model, channel, date range, limit, and offset. It also caps requested limits at 200.
- `api/v1/endpoints/admin_logs.py` exposes admin-only business-event and execution-session list/detail APIs through `require_admin_user()`.
- `api/v1/schemas/admin_logs.py` defines the current `BusinessEventModel` with fields such as `id`, `event`, `category`, `type`, `eventType`, `status`, `summary`, `actorType`, `actorLabel`, `route`, `endpoint`, `provider`, `source`, `traceId`, `analysisType`, `strategyId`, `scannerId`, `backtestId`, `userId`, `requestId`, `recordId`, timestamps, step counts, and `metadata`.
- `src/utils/security.py` provides `sanitize_metadata()`, `sanitize_message()`, and `sanitize_url()`. These mask secret-like keys and text fragments including API keys, tokens, authorization, credentials, secrets, passwords, bearer values, and secret-like URL parameters.
- `ExecutionLogService` calls these sanitization helpers before exposing business events, session lists, session details, operation details, messages, URLs, and event metadata.
- `AnalysisHistory` in `src/storage.py` is owner-linked through `owner_id` and contains `query_id`, stock/report summary fields, `raw_result`, `news_content`, and `context_snapshot`.
- Scanner runs are owner-linked through `MarketScannerRun.owner_id`; `src/repositories/scanner_repo.py` supports owner-scoped reads and `include_all_owners`.
- Backtest and rule-backtest runs are owner-linked through `BacktestRun.owner_id` and `RuleBacktestRun.owner_id`; their repositories support owner-scoped reads and `include_all_owners`.
- Portfolio accounts and broker-sync records are owner-linked through `owner_id`. Trade, cash-ledger, corporate-action, position, and snapshot records link through portfolio account ids.
- `api/v1/endpoints/portfolio.py` creates `PortfolioService(owner_id=current_user.user_id)` for normal user access and records portfolio audit events through `ExecutionLogService.record_portfolio_event()` after successful write paths.
- Watchlist write paths also use `ExecutionLogService.record_portfolio_event()` with actor metadata.

Confirmed absent or not inspected:

- `docs/audits/admin-data-schema-inventory.md` was not present in this checkout during this design pass.
- No existing `/api/v1/admin/users/{user_id}/activity` endpoint was confirmed.
- No existing `/api/v1/admin/activity` endpoint was confirmed.
- No dedicated activity projection schema/service was confirmed.

Inferred from existing patterns:

- Activity timeline implementation should use `ExecutionLogService` and owner-linked repositories as source primitives, not a raw database browser.
- Existing `business_event` projections are close to the required normalized event model but are not sufficient alone for a complete per-user timeline because some domain data is owner-linked outside execution logs.
- Where stable user ids are not available, existing actor metadata patterns can still distinguish `admin`, `user`, `guest`, `anonymous`, and `system` through actor type plus hashed request/session references.

## 3. Route design

All routes are proposed only.

### 3.1 User activity timeline

Route:

- `GET /api/v1/admin/users/{user_id}/activity`

Purpose:

- Return a read-only normalized timeline for one target user.
- Include only events attributable to `user_id`, plus admin accesses/actions where that user is the target.
- Exclude unrelated users even if a raw log message or generic query text matches.

Permission model:

- Initial implementation should use `Depends(require_admin_user)`.
- Future implementation may replace this with a stricter `require_admin_capability("users:activity:read")`.
- The route must not change user ownership checks used by normal user APIs.

Required path parameter:

- `user_id`: target app-user id. It should be treated as an opaque string and validated against the user directory source when that API exists.

Query parameters:

- `from`: ISO timestamp lower bound. Alias `date_from` may be accepted for consistency with Admin Logs.
- `to`: ISO timestamp upper bound. Alias `date_to` may be accepted.
- `category`: exact normalized event family. Alias of `family` for compatibility with Admin Logs terminology.
- `family`: exact normalized event family.
- `status`: normalized status/outcome filter.
- `entity_type`: normalized entity type filter such as `analysis`, `scanner_run`, `backtest_run`, `portfolio_account`, `portfolio_trade`, `auth_session`, `admin_view`, or `provider_operation`.
- `actor_type`: `admin`, `user`, `guest`, `anonymous`, or `system`.
- `target_user`: optional secondary target filter. For this route it must either be omitted or equal `{user_id}`.
- `q`: bounded full-text search over safe fields only: action labels, entity labels, symbol, source family, route family, provider name, sanitized reason, and hashed/truncated references.
- `limit`: page size.
- `offset`: offset pagination for initial implementation.
- `cursor`: opaque cursor for future cursor pagination.
- `include_system`: default `false`; when `true`, include background/system events clearly linked to the target user or target user's entities.
- `include_admin`: default `false`; when `true`, include admin accesses/actions where `targetUser.id == {user_id}`.

Limits:

- Default `limit`: 50.
- Maximum `limit`: 100 for the user-targeted route.
- Maximum time window: 90 days per request.
- Default time window: 7 days.
- If neither `from` nor `to` is provided, use the default 7-day window.
- If an implementation needs historical backfill beyond 90 days, require an explicit separate export/audit design.

Response sketch:

```json
{
  "items": [
    {
      "id": "act_...",
      "timestamp": "2026-05-06T08:00:00Z",
      "actor": {
        "type": "user",
        "userId": "user_123",
        "label": "alice"
      },
      "targetUser": {
        "id": "user_123",
        "label": "alice"
      },
      "family": "analysis",
      "action": "analysis.completed",
      "entity": {
        "type": "analysis_history",
        "idHash": "sha256:...",
        "label": "AAPL standard report",
        "symbol": "AAPL"
      },
      "status": "success",
      "outcome": "ok",
      "requestIdHash": "sha256:...",
      "sessionIdHash": "sha256:...",
      "source": {
        "kind": "execution_log_session",
        "table": "execution_log_sessions"
      },
      "redactedMetadata": {
        "reportType": "standard"
      },
      "logLinks": [
        {
          "kind": "admin_logs.business_event",
          "id": "123"
        }
      ]
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0,
  "hasMore": false,
  "window": {
    "from": "2026-04-29T08:00:00Z",
    "to": "2026-05-06T08:00:00Z",
    "maxDays": 90
  }
}
```

### 3.2 Global admin activity timeline

Route:

- `GET /api/v1/admin/activity`

Purpose:

- Return a read-only normalized global timeline for admin operations, support triage, and governance.
- Allow filtering to a target user without requiring a user-specific path.

Permission model:

- Initial implementation should use `Depends(require_admin_user)`.
- Future implementation may require a stricter capability for global cross-user activity.

Query parameters:

- Same as the user-targeted route, except `target_user` may target any user.
- `include_admin`: default `true` for this route because admin activity is central to global governance.
- `include_system`: default `false` to avoid noisy background activity unless requested.

Limits:

- Default `limit`: 50.
- Maximum `limit`: 100.
- Maximum time window: 30 days by default for global timelines.
- Default time window: 24 hours.
- Offset pagination may be accepted initially, but cursor pagination should be preferred once multiple source tables are merged.

Filter behavior:

- `target_user` filters events where the user is the target or owner of the affected entity.
- `actor_type=user` filters events initiated by normal users.
- `actor_type=admin` filters admin views/actions.
- `actor_type=guest` and `actor_type=anonymous` must not infer a real app user unless a confirmed link exists.
- `q` must search only safe projected fields. It must not search raw request bodies, prompts, messages, provider payloads, stack traces, cookies, tokens, or raw session ids.

## 4. Event normalization model

The future projection service should normalize every source row into one `AdminActivityEvent`.

Fields:

- `id`: stable activity event id. It may be derived from source kind plus source id, but should not expose raw session ids.
- `timestamp`: event timestamp used for ordering.
- `actor`: object containing `type`, optional `userId`, optional display label, optional role, and optional hashed session/request handles.
- `targetUser`: object containing the affected user id and safe label where known.
- `family`: normalized event family.
- `action`: normalized action string in `family.verb` form, for example `analysis.completed`, `portfolio.trade.created`, `admin.user_activity.viewed`.
- `entity`: object containing `type`, optional `idHash`, optional safe label, optional symbol, optional market, and optional source table.
- `status`: source status normalized to `success`, `failed`, `partial`, `running`, `skipped`, `cancelled`, or `unknown`.
- `outcome`: admin-display outcome normalized to `ok`, `warning`, `failed`, `timeout`, `partial`, or `unknown`.
- `requestIdHash`: hashed request id when present and safe to correlate.
- `sessionIdHash`: hashed app session id, execution session id, guest session id, or trace session id when present and safe to correlate.
- `source`: source descriptor with kind, table/service, and confidence.
- `redactedMetadata`: sanitized safe metadata only.
- `logLinks`: safe links to Admin Logs business events or execution sessions. Links must use public admin-log ids or hashed handles, not raw session/cookie/token values.

Actor model:

```json
{
  "type": "admin",
  "userId": "admin_1",
  "role": "admin",
  "label": "admin",
  "sessionIdHash": "sha256:...",
  "requestIdHash": "sha256:..."
}
```

Entity model:

```json
{
  "type": "portfolio_trade",
  "idHash": "sha256:...",
  "label": "AAPL buy trade",
  "symbol": "AAPL",
  "market": "us",
  "sourceTable": "portfolio_trades"
}
```

Families:

- `auth`: login, logout, session creation, session revocation, password changed, failed auth if logged.
- `analysis`: user and guest analysis requests, persisted analysis history, report generation lifecycle.
- `scanner`: market scanner runs, selected candidates, scanner operational events.
- `backtest`: deterministic and rule backtest runs, result generation, failures.
- `portfolio`: portfolio account, trade, cash ledger, corporate action, import, sync, and audit events.
- `admin`: admin views/actions, admin data access, settings/admin-control changes.
- `market/provider`: market overview, provider fallback, cache/stale/degraded provider activity.
- `security`: account status changes, session revocation, suspicious activity, permission failures, sensitive admin access.
- `system`: scheduler, background jobs, retention, storage health, and non-user system events.

Status normalization:

| Source values | `status` | `outcome` |
| --- | --- | --- |
| `success`, `succeeded`, `completed`, `ok` | `success` | `ok` |
| `partial`, `partial_success`, degraded fallback | `partial` | `partial` or `warning` |
| `failed`, `error`, `invalid_response`, `empty_result` | `failed` | `failed` |
| `timeout`, `timed_out`, `timeout_unknown` | `failed` | `timeout` |
| `running`, `started`, `in_progress` | `running` | `unknown` |
| `skipped`, `not_configured` | `skipped` | `ok` |
| unknown or missing | `unknown` | `unknown` |

## 5. Data sources

Each source must be projected through a service layer. The activity API must not expose raw ORM rows.

| Source | Status | Owner field | Proposed mapping | Redaction needs | Limitations |
| --- | --- | --- | --- | --- | --- |
| `execution_log_sessions` / `execution_log_events` | Confirmed | `summary_json` and projected business metadata may include `userId`; analysis link through `analysis_history_id`; actor metadata may include actor user/session/request fields | Primary source for normalized operational timeline, log links, request/session correlation, route/provider/category/status | Reuse `sanitize_metadata()`, `sanitize_message()`, `sanitize_url()`; hash session/request ids; hide raw details that contain prompt/body/provider data | Existing user attribution can be incomplete. `list_business_events()` currently loads a bounded session window before in-memory filtering. |
| `analysis_history` | Confirmed | `owner_id` | Add `analysis.created` / `analysis.completed` events with symbol, report type, summary status, query id hash, created timestamp | Do not expose `raw_result`, `news_content`, `context_snapshot`, raw prompt-like report internals, or raw provider payloads | Guest preview may use `persist_history=False`, so not all guest analysis appears here. |
| Scanner runs and candidates | Confirmed | `MarketScannerRun.owner_id`; candidate rows link through run id | Add `scanner.run.started/completed/failed` events and optional safe candidate-count metadata | Hide raw diagnostics that may contain provider payloads or prompt-like content; sanitize diagnostics and notes | Candidate rows do not carry owner id directly; owner must be resolved through the run. |
| Backtest runs/results | Confirmed | `BacktestRun.owner_id`, `RuleBacktestRun.owner_id`, related result rows | Add `backtest.run.completed/failed` and result-link events with metrics summary and code | Hide raw strategy text when prompt-like; hash strategy id/text; sanitize `summary_json`, `ai_summary`, warnings, and notes | Rule backtest strategy text can be sensitive and should not be searched raw. |
| Portfolio accounts/trades/cash/corporate actions | Confirmed | `PortfolioAccount.owner_id`; child records link through `account_id` | Add `portfolio.account.*`, `portfolio.trade.*`, `portfolio.cash_ledger.*`, `portfolio.corporate_action.*`, import/sync events where available | Mask broker account references; avoid raw import payloads; sanitize notes; hash record/account ids when displayed as cross-user audit references | Trade/cash/corporate-action rows do not carry owner id directly; must join through account. |
| Portfolio broker sync state/positions/cash | Confirmed | Direct `owner_id` on broker sync tables | Add safe read-only sync status and import/sync timeline events | Mask broker account refs and payload JSON; do not expose raw broker payloads/files | Current records are current snapshots, not a complete event history unless existing audit/log rows exist. |
| Auth/session events | Partially confirmed | `AppUserSession.user_id` | Add session-created, last-seen, expired, revoked events if safely derivable or explicitly logged | Never expose raw `session_id`, signed cookies, reset tokens, password hash, or session secret; hash/truncate session handles | Failed login events are only included if logged elsewhere. Derived session rows are state snapshots, not full event streams. |
| Admin actions and settings/security access | Confirmed in concept through Admin Logs patterns; exact coverage varies by endpoint | Actor user from `CurrentUser`; target in event metadata where recorded | Add `admin.*` and `security.*` events for sensitive views/actions, including this timeline view | Do not log raw request bodies, secrets, stack traces, target raw session ids, or raw payloads | Viewing the activity timeline itself needs a future audit write path, but this design does not implement it. |
| Market/provider operations | Confirmed | Usually system/global; user link only if event metadata contains user/request/entity link | Add `market/provider.*` events when tied to a target user/entity or when global route is requested | Sanitize URL/error/provider metadata; hide API keys and request bodies | Many provider events are global. User route should exclude unrelated global noise unless linked. |
| System/scheduler/storage health | Confirmed through Admin Logs/storage services | Usually none | Include only in global route by default when requested through `include_system=true` | Sanitize messages and metadata | Can be noisy; default off for user route and global route. |

Projection confidence:

- `confirmed`: direct owner id or explicit actor/target user metadata exists.
- `inferred`: target user is derived from linked entity ownership or execution-log summary fields.
- `unknown`: event is not included in a user-targeted route unless it has a confirmed link; global route may include it with no `targetUser`.

## 6. Redaction/privacy model

Hard exclusions:

- No secrets.
- No raw session IDs.
- No signed cookies.
- No tokens.
- No password hashes.
- No API keys.
- No raw prompts.
- No raw LLM messages.
- No raw provider payloads.
- No raw request bodies.
- No raw stack traces.
- No uploaded file contents.
- No broker import payloads.

Required redaction behavior:

- Apply `sanitize_metadata()`-style recursive masking to all projected metadata.
- Apply `sanitize_message()`-style masking to summaries, reasons, error summaries, notes, and labels derived from free-form text.
- Apply `sanitize_url()`-style masking to routes, endpoints, provider URLs, and callback/webhook-like values.
- Hash session ids, request ids, query ids, execution session ids, portfolio record ids, strategy hashes, and external/broker references where display is needed for correlation.
- Use a stable server-side hash salt only if the future implementation already has an approved secret-management pattern. Otherwise prefer one-way hash without revealing raw values and document rotation/correlation limitations.
- Truncate free-form summaries and metadata values to bounded lengths.
- Do not include raw ORM `to_dict()` output for sensitive rows such as `AnalysisHistory`, because it includes raw result/context fields.
- Do not search excluded raw fields for `q`; searching raw sensitive fields can leak existence and timing.

Allowed safe metadata examples:

- Event family and action.
- Status/outcome.
- Symbol, market, report type, scanner profile, universe name, strategy hash, provider name.
- Counts, durations, candidate counts, step counts, warning/failure category.
- Sanitized reason/error summary with secrets masked and stack traces removed.
- Hashed/truncated request/session/entity references.

Denied metadata examples:

- `password_hash`.
- `session_id` raw value.
- Cookie value.
- Authorization header.
- Reset token.
- API key.
- Webhook URL with token.
- Raw `raw_result`, `news_content`, `context_snapshot`.
- Raw `strategy_text` when user-entered or prompt-like.
- Raw provider request/response JSON.
- Raw traceback or request body.

## 7. Audit model

Viewing a user activity timeline is a sensitive admin access event.

Future implementation should audit:

- Actor admin user id, role, and actor type.
- Target route: `GET /api/v1/admin/users/{user_id}/activity` or `GET /api/v1/admin/activity`.
- Target user id or hashed target id when present.
- Query window and filters, with `q` length/hash rather than raw sensitive search text if necessary.
- Result count, limit, and whether more pages exist.
- Outcome: success, forbidden, validation error, not found, or failed.
- Request id hash and admin session id hash.
- Reason/context if a future reason-required sensitive-access model exists.

Future implementation must not audit:

- Raw request bodies.
- Raw `q` values if they could contain secrets or user-provided sensitive text.
- Raw session ids.
- Cookies.
- Authorization headers.
- Passwords or password hashes.
- Raw prompt/message/provider payloads.
- Full response payloads.

Recommended audit event:

```json
{
  "family": "admin",
  "action": "admin.user_activity.viewed",
  "actorType": "admin",
  "targetUserId": "user_123",
  "status": "success",
  "metadata": {
    "route": "/api/v1/admin/users/{user_id}/activity",
    "windowDays": 7,
    "filters": ["family", "status"],
    "resultCount": 50,
    "hasMore": true
  }
}
```

The audit write must be best-effort and must not mutate user data. If audit write fails, the endpoint should either fail closed for sensitive access or return with a visible admin-log failure according to a separate implementation decision. This design recommends fail-closed for future high-sensitivity views unless product requirements explicitly choose degraded read access.

## 8. Implementation plan

Future implementation should be split into small phases.

Phase 1: projection service

- Add an `AdminActivityProjectionService` or equivalent under the existing service layer.
- Build source adapters for execution-log business events, analysis history, scanner runs, backtest runs, portfolio audit/activity, auth sessions, admin actions, and market/provider events.
- Normalize each source to `AdminActivityEvent`.
- Enforce time windows, max limits, sort order, and redaction centrally.
- Keep existing `ExecutionLogService` contracts unchanged.

Phase 2: schemas

- Add request/response Pydantic schemas for `AdminActivityEvent`, actor, target user, entity, source, log links, and paginated responses.
- Use camelCase response fields if aligning with current admin log schemas.
- Include documented enum values for family, actor type, status, outcome, entity type, and source confidence.

Phase 3: endpoints/router

- Add admin-only routes:
  - `GET /api/v1/admin/users/{user_id}/activity`
  - `GET /api/v1/admin/activity`
- Register routes under the existing `/api/v1/admin` router structure.
- Reuse `require_admin_user()` initially.
- Add explicit validation for max windows, limits, and user-targeted filter consistency.

Phase 4: audit write

- Add a narrowly scoped audit helper for sensitive admin reads.
- Record successful and failed timeline access without storing sensitive query text or response data.
- Ensure audit failures are covered by tests and have a documented fail-open/fail-closed choice.

Phase 5: pagination and performance

- Start with offset pagination only if source merging remains cheap and bounded.
- Prefer cursor pagination for multi-source timelines.
- Query each source by time window and owner before in-memory merge.
- Do not load raw unbounded Admin Logs and filter after the fact.
- Keep per-source caps lower than the route cap plus merge margin.
- Add indexes only in a separate migration task if profiling proves they are needed.

Phase 6: frontend

- Frontend waits for backend API and schema.
- Admin Data Control Center user detail can consume the user-targeted route.
- Global admin governance page can consume the global route.
- UI must show redaction state and link to Admin Logs rather than exposing raw log details inline.

Out of scope for this design task:

- Endpoint implementation.
- Runtime code changes.
- Schema implementation.
- Tests.
- Frontend routes.
- Migrations.
- Auth or authorization changes.
- Portfolio/scanner/backtest/provider/MarketCache/AI/notification/DuckDB behavior changes.

## 9. Tests required

Future implementation should include at least:

- Admin required: unauthenticated and non-admin requests are rejected.
- Non-admin forbidden: normal users cannot call either route, including their own user id.
- User-targeted route filters strictly by target user and does not include another user's analysis, scanner, backtest, portfolio, auth, or admin-targeted events.
- Global route respects default window, maximum window, default limit, maximum limit, and pagination.
- Ordering is deterministic by timestamp descending with a stable tie-breaker.
- `from`/`to` validation rejects invalid dates and excessive windows.
- `category`/`family`, `status`, `entity_type`, `actor_type`, `target_user`, and `q` filters work together.
- `target_user` on `/admin/users/{user_id}/activity` must match the path user or be rejected.
- `include_system=false` excludes unrelated system events.
- `include_admin=false` excludes admin access/action events from the user route by default.
- `include_admin=true` includes admin events targeting the user.
- Redaction tests assert absence of raw session ids, cookies, tokens, password hashes, API keys, raw prompts/messages/provider payloads, raw stack traces, and raw request bodies.
- `sanitize_metadata()`-style recursive masking is applied to nested metadata.
- Hashing tests assert raw request/session/entity ids are not returned while stable hash references are present when needed.
- Analysis history projection does not return `raw_result`, `news_content`, or `context_snapshot`.
- Rule backtest projection does not return raw user-entered strategy text unless a separate approved redacted summary exists.
- Portfolio projection masks broker account references and raw import/sync payloads.
- Admin timeline view emits a sensitive admin access audit event on success.
- Failed/forbidden/validation-error timeline access emits the expected audit event if the future audit model requires failed attempts.
- Existing `/api/v1/admin/logs` and `/sessions` tests keep passing unchanged.

Suggested focused test files:

- `tests/api/test_admin_user_activity.py` for endpoint contract and authorization.
- `tests/test_admin_activity_projection_service.py` for multi-source normalization, redaction, filtering, and ordering.
- Existing admin log tests should be extended only if shared helpers are intentionally changed.

## 10. Parallelization

This design can run in parallel with the User Directory API design because both are docs/API-design work and no runtime code changes are required.

Future implementation should coordinate with User Directory work on:

- shared admin route structure;
- shared user-safe projection fields;
- shared hashed id helpers;
- shared redaction helpers;
- shared admin sensitive-access audit helper;
- shared pagination conventions;
- shared capability naming if admin roles are split later.

Implementation dependency order:

1. User Directory or equivalent user lookup should land before user-targeted activity implementation if the activity route validates `{user_id}` existence.
2. Activity projection service can start independently against existing owner-linked sources.
3. Backend routes and schemas should land before frontend work.
4. Frontend should wait for stable response shape, filter semantics, and audit behavior.

Risk notes:

- Existing Admin Logs business-event filtering is useful but not enough by itself for a complete user timeline.
- User attribution can be incomplete for legacy/system/global records. The projection must label confidence rather than over-assigning ownership.
- Global provider/system events can be noisy. Keep them excluded by default from user timelines and bounded in global timelines.
- Redaction is a product boundary, not only a display concern. Sensitive fields must be omitted or masked before response serialization.

## 11. Implementation note 2026-05-06

- Backend routes landed in `api/v1/endpoints/admin_users.py`: `GET /api/v1/admin/users/{user_id}/activity` and `GET /api/v1/admin/activity`.
- Safe response schemas landed in `api/v1/schemas/admin_activity.py`; projection logic landed in `src/services/admin_activity_service.py`.
- The first implementation is conservative: it normalizes sanitized Execution Logs business events, safe `AnalysisHistory` metadata, and auth session snapshots. Scanner, backtest, portfolio, and richer admin-audit projections remain deferred limitations.
- Activity responses hash request/session/entity references and omit raw `session_id`, cookies, tokens, password hashes, API keys, raw prompts/messages/provider payloads, request bodies, stack traces, `raw_result`, `news_content`, and `context_snapshot`.
- Sensitive admin-view audit writes are deferred to a later admin-audit hardening pass to avoid inventing a broader audit model in this backend-only phase.
