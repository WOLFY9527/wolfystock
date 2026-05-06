# Admin Governance + Cost Observability E2E QA Runbook

Date: 2026-05-06
Mode: docs-only QA/runbook. No runtime behavior changed.

## 1. Purpose

This runbook defines post-implementation validation for the Admin Data Control Center, admin portfolio visibility, admin security controls, duplicate-cost observability, and future cache/reuse prototype entry criteria.

It consolidates the existing admin governance and cost-observability design notes into one static QA checklist. It does not approve new runtime behavior, API changes, frontend changes, schema changes, tests, cache behavior, provider calls, LLM calls, dev-server use, or live API verification.

## 2. Surface inventory

| Surface | Current status | Backend route(s) | Frontend route(s) | Sensitive data classes | Required tests/checks | Blocking dependencies |
| --- | --- | --- | --- | --- | --- | --- |
| Admin Users directory | Implemented backend; frontend implemented per recent context | `GET /api/v1/admin/users` | Admin users/data control route, expected under admin surface | User identity, role, status, session summaries | Admin allowed, non-admin forbidden, unauthenticated rejected, pagination/filter/search, no `password_hash`, no raw session/cookie/token | Stable admin route gate and safe user projection |
| Admin User Detail | Implemented backend; frontend implemented per recent context | `GET /api/v1/admin/users/{user_id}` | Admin user detail route | User profile, status, session counts, redacted handles | Existing user, missing user, forbidden, redacted session handles, no credentials | Target-user existence validation and safe detail projection |
| Admin User Activity | Implemented backend; frontend may be partial or in progress | `GET /api/v1/admin/users/{user_id}/activity`, `GET /api/v1/admin/activity` | User activity tab/timeline if wired | Execution log metadata, analysis metadata, auth session snapshots, request/session handles | Safe timeline projection, source limitations visible, raw prompt/provider/request body absent, hashed handles only | Richer scanner/backtest/portfolio/admin-audit projections remain deferred unless implemented |
| Admin Portfolio Summary/Holdings/Activity/Account Detail | Implemented backend | `GET /api/v1/admin/users/{user_id}/portfolio-summary`, `GET /api/v1/admin/users/{user_id}/holdings`, `GET /api/v1/admin/users/{user_id}/portfolio-activity`, `GET /api/v1/admin/users/{user_id}/portfolio/accounts/{account_id}` | Portfolio tab/detail if wired | Holdings, cash, trades, broker refs, sync metadata, broker payloads | Read-only, owner-target joins, account belongs to target user, masked broker refs, no sync/import/replay/FX refresh, audit event coverage | Frontend UI and audit hardening state may vary by branch |
| Admin Security Controls | In progress or planned unless implementation lands | Proposed `POST /api/v1/admin/users/{user_id}/disable`, `/enable`, `/reset-password`, `/force-password-change`, `/revoke-sessions`, `/unlock` | Security tab/actions if wired | Account state, credential workflow state, session revocation state | Capability checks, reason, typed confirmation, self-action guard, last-admin guard, no credential reveal, audit success/failure/blocked | Dedicated audit helper, RBAC/capability model, security data model gaps |
| Admin Audit | Existing Admin Logs implemented; dedicated admin-governance audit may be in progress/planned | Existing `/api/v1/admin/logs`, `/api/v1/admin/logs/sessions`; future admin audit projection TBD | `/admin/logs`; future admin audit route/tab | Audit metadata, route/action families, actor/target handles | Metadata allowlist, forbidden metadata absent, admin audit reads audited, retention/empty/error states | Fail-closed policy and retention/capacity rules |
| Duplicate-Cost Summary API | Implemented backend per recent commit/context | `GET /api/v1/admin/cost/duplicate-summary` | Cost dashboard route if wired | Aggregate counters, safe hashes, process-local limitations | `readOnly`, `noExternalCalls`, `observational_not_billing`, no raw prompt/provider payload/URL/secret/session/candidate payload | Counter phases 1A-1D must be available and named consistently |
| Duplicate-Cost Dashboard | Frontend may be in progress | Same as summary API | Admin cost observability dashboard if wired | DOM-rendered aggregate cost/counter metadata | Loading/empty/error/forbidden, no secret DOM text, limitations visible, no external calls triggered | Stable backend API and admin route navigation |
| Guest Preview reuse | Planned prototype only | Future analysis preview reuse seam only after approval | Guest preview UI disclosure if ever implemented | Guest session/request handles, report freshness, analysis inputs | Entry criteria review, force refresh bypass, same guest session only, no cross-user reuse, disclosure metadata | Measured duplicate signal and explicit human approval |
| Scanner AI interpretation cache | Planned prototype only | Future scanner AI interpretation cache seam | Scanner AI disclosure if ever implemented | Candidate context hashes, prompt/model/source freshness, AI text | Entry criteria review, additive text only, no rank/score/selection change, force refresh bypass, no raw prompt/provider payload | Scanner AI duplicate candidate metrics and read-only report evidence |
| LLM report output cache | Planned prototype only | Future LLM/report output cache seam | Report cache disclosure if ever implemented | Report input identity, prompt/model/provider identity, source freshness, output metadata | Entry criteria review, freshness/key correctness, no cross-user reuse, force refresh bypass, disabled by default | Duplicate report evidence, approved key/freshness model, rollback plan |

## 3. Admin E2E QA matrix

For every implemented admin surface, validate these common checks before release:

| Surface | Access and auth | State handling | Read-only/ownership | Route/nav/i18n | Desktop/mobile |
| --- | --- | --- | --- | --- | --- |
| Admin Users directory | Admin allowed; non-admin forbidden; unauthenticated rejected | Loading, empty, API error, forbidden | No mutation; safe list projection only | Admin nav visible only to allowed users; `/zh` labels localized | Table density, filter rail, no horizontal overflow |
| Admin User Detail | Admin allowed; non-admin forbidden; unauthenticated rejected | Loading, user not found, API error, forbidden | Target user id matches route; no raw session handles | Detail tabs preserve target route; localized status labels | Header/tabs/summary usable on narrow viewport |
| Admin User Activity | Admin allowed; non-admin forbidden; unauthenticated rejected | Loading, no activity, partial source limitations, API error, forbidden | Target user route rejects mismatched `target_user`; global route filter is bounded | Timeline filters serialize safely; route labels localized | Timeline and detail drawer readable on desktop/mobile |
| Admin Portfolio Summary/Holdings/Activity/Account Detail | Admin allowed; non-admin forbidden; unauthenticated rejected | Loading, no accounts, no holdings, stale/partial source, API error, forbidden | Read-only only; target-user ownership joins; account id belongs to target user | Portfolio tab/routing preserves target user context | Holdings/activity tables do not expose hidden columns on mobile |
| Admin Security Controls | Admin/security capability allowed; insufficient role forbidden; unauthenticated rejected | Disabled control state, action pending, failure, blocked guard, success | Mutating action only after reason and confirmation; self/last-admin guards | Action copy localized and not misleading; audit id shown if returned | Confirmation modal fits narrow view |
| Admin Audit | Security/admin-audit role allowed; support-only role redacted/forbidden as designed | Empty audit window, retention limitation, API error, forbidden | Read-only audit reads; viewing audit is itself audited when backend supports it | Filters preserve route state and labels | Dense audit table and detail drawer usable |
| Duplicate-Cost Dashboard | Admin allowed; non-admin forbidden; unauthenticated rejected | Loading, no observations, partial counters, API error, forbidden | Read-only summary only; no provider/LLM/MarketCache/scanner calls | Limitations and `observational_not_billing` visible | Summary cards and tables readable without truncating safety metadata |

## 4. No-secret verification matrix

| Secret/sensitive class | API response check | Frontend DOM check | Audit metadata check | Logs/checks | Expected handling |
| --- | --- | --- | --- | --- | --- |
| Plaintext password | Never present in any payload | Not rendered in form state, dialogs, tooltips, data attributes | Never stored | Grep response fixtures and logs for password-like raw values | Omit entirely |
| `password_hash` | Field absent | String absent | Field absent | Grep for `password_hash` in admin response fixtures | Omit entirely |
| Raw `session_id` | Only hashed/truncated handle allowed | No full session id in DOM or copied JSON | Hash/truncate only | Grep for raw session-like values in fixtures; avoid printing real values | Redacted handle only |
| Cookies | No signed cookie values | No cookie values in DOM | No cookie values | No cookie/header dumps | Omit entirely |
| Bearer tokens | No Authorization value | No token text in DOM | No token fields | Sanitized logs only | Omit/mask |
| API keys | Env var names may appear; values absent | No key values in DOM or copied diagnostics | No key values | Sanitizer tests/grep with synthetic keys | Configured/masked status only |
| Reset/admin unlock tokens | No token value | No token value | Outcome only | No reset-token logs | Omit value; audit outcome |
| Broker credentials | No token/password/session credential | No credential text | No credential metadata | Synthetic grep only | Omit entirely |
| Broker raw payloads | No `payload_json` or raw import payload by default | No hidden raw JSON text | Counts/status/timestamps only | Grep for `payload_json` and raw broker fields in fixtures | Metadata summary only |
| `sync_metadata_json` | Not returned raw | Not rendered raw | Sanitized summary only | Grep for raw JSON field names | Collapse/sanitize |
| Raw prompts/messages | No prompt/message payload | No prompt text in DOM | No prompt in metadata | Grep synthetic fixtures for prompt fields | Omit or safe summary only |
| Provider payloads | No raw request/response body | No provider raw JSON | Sanitized provider/source labels only | Grep for provider payload keys | Omit/sanitize |
| Raw uploaded file/image content | No bytes/base64/content | No preview of retained raw content unless separately approved | Metadata only | No file content dumps | File type, size bucket, hash only |
| Raw URLs/query strings | Use route templates or sanitized URLs | Query strings not displayed raw | Route/action family only | `sanitize_url`-style checks | Mask query params |
| Stack traces | No stack trace in response | No stack trace in UI | No stack trace in audit | Error fixtures use sanitized summary | Sanitized error code/summary |
| Raw request bodies | No body dump | No request body dump | No raw body | Grep fixtures/logs for body fields | Omit entirely |
| Full user/session ids where not explicitly allowed | Use explicit safe user id policy; session ids never raw | Avoid full session/request ids | Hash/truncate request/session handles | Synthetic id checks only | Allow listed user ids when needed; hash session/request ids |

## 5. Admin audit verification

- User directory/list/detail access emits or links to a safe admin access event where backend support exists.
- Activity timeline access is audited for target-user and global routes when the audit helper exists.
- Portfolio summary, holdings, activity, and account detail views are audited with actor, target user, route family, filters, outcome, and safe event id.
- Security action success, failure, and blocked guard outcomes are audited.
- Admin audit reads are themselves audited through an `admin_audit.viewed`-style event when implemented.
- Audit metadata uses an allowlist: actor type/role/id where allowed, target user or hash, route/action family, reason category, filter summary, result count, outcome, timestamp, safe request handle.
- Forbidden metadata is absent: raw request bodies, raw query text that may contain secrets, raw session ids, cookies, bearer tokens, API keys, credential values, broker raw payloads, provider payloads, raw prompts/messages, stack traces.
- High-sensitivity security, portfolio detail/holdings, and admin-audit reads follow the designed fail-closed policy if audit persistence fails, unless a later product decision explicitly chooses degraded read access.
- Audit event IDs are visible in frontend success/detail states when backend responses return them.

## 6. Security controls QA checklist

Apply this checklist to each implemented or future control: disable account, enable account, revoke sessions, reset-password request, force-password-change, and unlock.

- Admin/security capability is required; plain support-admin cannot execute security controls unless explicitly approved.
- Typed confirmation is required for destructive or security-sensitive actions.
- Reason is required and is bounded; optional free text is short and audited.
- Self-action guard blocks disabling, revoking, resetting, or locking the acting admin when the action would endanger admin access.
- Last-admin guard prevents disabling or locking the last usable admin.
- No credential, password, hash, token, raw session id, cookie, or reset token is revealed in request logs, responses, audit metadata, or UI.
- Success, failure, forbidden, and blocked outcomes are audited with a safe `auditEventId` when backend returns one.
- Session revocation reports counts/status only; revoked raw session ids are never exposed.
- Rollback expectations are documented per action: enable can restore account access, force-password-change can be cleared only by an approved flow, session revocation is not reversible, reset-password request must not reveal generated secrets.

## 7. Portfolio visibility QA checklist

- Routes are read-only only.
- No sync, import, replay, FX refresh, cache refresh, accounting recompute, trade/cash/corporate-action mutation, or broker connectivity probe is triggered.
- Target user id is validated for every query.
- Account id belongs to the target user before account detail is returned.
- Broker account references are masked or replaced by stable display handles.
- Raw broker payloads, import files, `payload_json`, and raw `sync_metadata_json` are hidden.
- Broker tokens, IBKR session tokens, cookies, and credentials are absent.
- P&L, cash, holdings, FX stale, and valuation semantics are unchanged from existing portfolio logic.
- Every sensitive portfolio view emits an audit event or records a visible limitation if audit hardening is not yet implemented.

## 8. Duplicate-cost observability QA checklist

Validate the implemented counter phases and read-only summary:

- Phase 1A LLM counters observe outbound attempts, fallback transitions, integrity retries, token accounting persistence, and duplicate candidates without changing prompts, model routing, parser behavior, retry policy, or report semantics.
- Phase 1B provider counters observe provider attempts, fallback depth, cache hit/miss, inflight joins, insufficient payload, timeout, quota risk, and duplicate candidates without changing provider ordering, timeout, retry, circuit, cache, or fallback behavior.
- Phase 1C MarketCache counters observe hit, stale served, miss, refresh started/completed/failed, and cold-start fallback without changing TTL, SWR, cold-start, fallback, or background refresh behavior.
- Phase 1D scanner AI counters observe duplicate candidate hashes and interpretation outcomes without changing rank, score, selection, thresholds, profile, universe, diagnostics, actionability, or CSV headers.
- Duplicate-cost summary API returns `readOnly`, `noExternalCalls`, data source/limitations metadata, and exact `observational_not_billing` disclosure.
- Duplicate-cost dashboard, if implemented, renders the same limitations and does not imply billing truth.
- No endpoint or dashboard load triggers provider calls, LLM calls, MarketCache refreshes, scanner runs, config writes, cache mutations, background jobs, live probes, or audit writes beyond approved read-audit behavior.
- API response, frontend DOM, audit metadata, and logs contain no raw prompts, messages, images, news, provider payloads, URLs/query strings, stack traces, full user/session ids, candidate payloads, credentials, tokens, or secret config values.
- Process-local limitations are visible anywhere process-local counters or in-memory cache status are shown.

## 9. Cost baseline review procedure

Before any cache/reuse prototype:

1. Collect at least three observation windows or three manual QA sessions covering representative admin, guest preview, scanner AI, and report-generation workflows.
2. Capture duplicate candidates by area: LLM report generation, guest preview, provider fallback/cache, MarketCache, scanner AI interpretation.
3. Compare duplicate multipliers by area, separating exact duplicate identity from near-duplicate or normal repeated user intent.
4. Identify high-multiplier areas where repeated work is material and stable enough to justify a prototype.
5. Separate real waste from normal fallback, retry, integrity repair, stale refresh, cold-start behavior, provider degradation, or user-requested force refresh.
6. Record limitations: process-local counters, restarts, multi-worker gaps, incomplete owner attribution, bounded labels, and lack of billing truth.
7. Do not use process-local counters as billing truth. Treat them as operational observations only.
8. Require explicit human approval before any cache/reuse prototype starts.

## 10. Cache/reuse prototype entry criteria

### Guest Preview reuse

- Required measured signal: repeated guest preview requests with matching safe identity and meaningful duplicate LLM/report cost across the same guest session.
- Minimum safety conditions: same guest session only; no cross-user, cross-authenticated-user, or cross-guest-session reuse; no reuse after `force_refresh`; no reuse when input, report type, language, model/prompt identity, source freshness, or safety policy changes.
- Required disclosure metadata: generated/reused state, cache age, freshness bucket, safe cache key hash, limitations.
- Invalidation requirements: source freshness, prompt/report version, model route, report type, language, input identity, safety policy, and manual bypass.
- `force_refresh` behavior: always bypass reuse and produce fresh work.
- Prohibited cross-user reuse: mandatory.
- Required tests: same-session hit, cross-session miss, force-refresh bypass, freshness invalidation, no secret labels/logs, no behavior change when disabled.
- Rollout flag/default disabled: required.
- Rollback plan: disable flag and clear prototype storage if introduced.

### Scanner AI interpretation cache

- Required measured signal: scanner AI duplicate candidate counters show repeated equivalent candidate interpretation payloads with meaningful repeat rate.
- Minimum safety conditions: cache affects additive interpretation text only; deterministic scanner rank, score, selection, thresholds, reasons, actionability, CSV headers, profile, market, universe, and provider behavior remain authoritative and unchanged.
- Required disclosure metadata: generated/cache-hit/cache-miss/skipped/failed/disabled/unavailable state, cache age, freshness bucket, prompt version, model route, safe cache key hash.
- Invalidation requirements: candidate payload hash, prompt version, model route, language, top-N policy, scanner context, source freshness, code/parser/schema version, and force refresh.
- `force_refresh` behavior: bypass cache for all selected candidate interpretations.
- Prohibited cross-user reuse: no cross-user reuse unless a future design proves fully public non-user-scoped equivalence and privacy review approves it.
- Required tests: no ranking/selection diff, exact eligibility match, mismatch invalidation, forced bypass, no raw prompt/provider/candidate payload in logs/responses.
- Rollout flag/default disabled: required.
- Rollback plan: disable flag and ignore/delete cache rows.

### LLM Report Output cache

- Required measured signal: duplicate report-output observations show repeated equivalent report requests with material LLM cost and stable freshness identity.
- Minimum safety conditions: no report cache before metrics; no prompt, LLM routing, AI decision, provider behavior, report semantics, integrity retry, parser, notification, portfolio, backtest, or DuckDB behavior changes.
- Required disclosure metadata: generated/cache-hit/cache-miss/bypassed state, cache age, report identity hash, prompt/report version, model route, source freshness, limitations.
- Invalidation requirements: symbol/input set, market, report type, language, prompt/report version, model/provider route, source snapshot/freshness, user scope where relevant, parser/schema version, integrity policy, and manual bypass.
- `force_refresh` behavior: bypass cache and record bypass metadata.
- Prohibited cross-user reuse: mandatory unless a future privacy review explicitly approves a public, non-user-scoped cache for a narrow report class.
- Required tests: disabled default, exact key hit, mismatch miss, freshness invalidation, force-refresh bypass, no secret/log leakage, unchanged report semantics.
- Rollout flag/default disabled: required.
- Rollback plan: disable flag, clear cache, and fall back to normal generation path.

## 11. Recommended verification commands

Use these command bundles only when the corresponding implementation exists. All commands should run with synthetic fixtures/mocks and no live provider or LLM calls.

Backend admin API focused tests:

```bash
python3 -m pytest tests/api/test_admin_users.py tests/api/test_admin_user_activity.py -q
python3 -m pytest tests/api/test_admin_portfolio.py -q
```

Frontend admin user tests:

```bash
cd apps/dsa-web
npm run test -- src/pages/__tests__/AdminUserDataControlPage.test.tsx src/__tests__/AppRoutes.test.tsx
```

Duplicate-cost backend tests:

```bash
python3 -m pytest tests/api/test_admin_duplicate_cost.py tests/test_llm_instrumentation.py tests/test_provider_duplicate_cost_metrics.py tests/test_market_cache_metrics.py tests/test_scanner_ai_metrics.py -q
```

Duplicate-cost frontend tests:

```bash
cd apps/dsa-web
npm run test -- src/pages/__tests__/AdminCostObservabilityPage.test.tsx src/__tests__/AppRoutes.test.tsx
```

No-secret grep patterns, using only synthetic fixtures and source/test files:

```bash
rg -n "password_hash|session_id|dsa_session|Authorization|Bearer |api[_-]?key|secret|token|payload_json|sync_metadata_json|raw_result|context_snapshot|raw prompt|provider payload|stack trace" docs/audits tests apps/dsa-web/src
```

Design guard:

```bash
rg -n "force_refresh|observational_not_billing|noExternalCalls|readOnly|process-local|disabled-by-default|no raw|no provider|no LLM" docs/audits
```

Lint/build when frontend code changed:

```bash
cd apps/dsa-web
npm run lint
npm run build
```

Backend gate when backend code changed:

```bash
./scripts/ci_gate.sh
```

Playwright desktop/mobile routes when UI exists:

```bash
# Use mocked API fixtures only. Do not call live APIs or live providers.
# Validate admin users, user detail, activity, portfolio, security, audit,
# and duplicate-cost routes at desktop and mobile viewport sizes.
```

## 12. Release checklist

- Backend tests pass for implemented admin users, activity, portfolio, security, audit, and duplicate-cost surfaces.
- Frontend tests pass for implemented admin data control, security, portfolio, audit, and duplicate-cost routes.
- `./scripts/ci_gate.sh` passes when backend/runtime code changed.
- No-secret API, DOM, audit, and synthetic log checks pass.
- Browser desktop/mobile checks pass for implemented UI routes, using mocked/safe data only.
- `docs/CHANGELOG.md` is updated for user-visible behavior changes. For docs-only runbook work, explain if no changelog entry was added.
- Rollback commands are documented for runtime changes; docs-only rollback is reverting the runbook commit.
- Known limitations are documented: process-local counters, deferred audit model, partial frontend status, deferred cache prototypes.
- Admin-only route gates are verified for implemented routes.

## 13. Open risks and follow-ups

- RBAC/capability model is not yet fully implemented; early read-only APIs may still rely on coarse admin checks.
- Security controls have data model and audit-helper gaps, especially self-action and last-admin guard enforcement.
- Process-local counters are operational observations, not billing truth, and can miss multi-worker/restart history.
- Cache prototypes can create privacy, freshness, attribution, and stale-advice risks unless measurement-first entry criteria are enforced.
- Audit retention/capacity and fail-closed behavior need explicit product decisions before broad admin audit views ship.
- Frontend route sprawl remains a risk; admin users, security, audit, portfolio, and cost routes need coherent IA.
- Privacy review is required before broader support roles or cross-user/admin data visibility expand.
