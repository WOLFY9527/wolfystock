# WS2 Provider Circuit Breaker Data Model Migration Plan

Date: 2026-05-06
Mode: docs-only migration planning. No migrations, runtime provider behavior, provider ordering/fallback, MarketCache TTL/SWR/cold-start behavior, quota enforcement, schema code, tests, live providers, or servers were changed.

Follows: `410c5cef docs(ws2): design provider quota circuit breaker policy`

## 1. Executive summary

Provider circuit storage is needed because the current provider/circuit posture is intentionally process-local and observational. That is useful for duplicate-cost visibility and single-process safety, but it is not enough for public multi-user usage where provider 429s, 403s, slow timeouts, admin probe loops, or repeated fallback chains can affect every user and every API instance.

This plan models the durable data needed for a future provider circuit breaker and provider quota ledger:

- provider quota policy rows for provider/route/owner/global/probe scopes;
- provider quota accounting windows for owner and global provider buckets;
- provider circuit state rows for the current durable state per provider/category/route/owner scope;
- provider circuit event rows for safe state-transition history;
- provider probe event/window rows for bounded admin and half-open recovery probes.

This plan explicitly does not implement:

- no schema migration or table creation;
- no runtime provider behavior change;
- no provider ordering, fallback, retry, timeout, sufficiency, or in-flight coalescing change;
- no MarketCache TTL, stale-while-revalidate, cold-start fallback, background refresh, or payload-shape change;
- no quota enforcement wiring;
- no frontend/admin dashboard implementation;
- no scanner, backtest, portfolio, Options Lab, RBAC, notification, DuckDB, broker, LLM, or live provider behavior change.

## WS2-R5 storage foundation implementation note

- Provider circuit/quota storage foundation has landed with additive SQLite/local ORM tables and matching PostgreSQL baseline DDL for `provider_quota_policies`, `provider_quota_windows`, `provider_circuit_states`, `provider_circuit_events`, and `provider_probe_events`.
- Narrow `DatabaseManager` helpers now cover synthetic-only circuit state upsert/read, state transition plus event append, current circuit listing, provider quota window counter updates, probe event recording, and provider circuit metadata sanitization.
- Synthetic tests cover initialization, state transitions, quota-depleted/operator-disabled states, quota window counters, metadata redaction, and no live provider path usage.
- No enforcement was added. Runtime provider behavior, provider ordering/fallback, MarketCache TTL/SWR/cold-start/background refresh/payload shape, scanner/backtest/portfolio/Options/RBAC, notification, DuckDB, broker/order, and LLM routing remain unchanged.
- Remaining work: dry-run provider counters, read-only admin diagnostics API, dashboard surfacing, and a separately approved enforcement pilot.

## WS2-R5 read-only diagnostics API implementation note

- Read-only admin diagnostics endpoints have landed for the existing storage foundation:
  - `GET /api/v1/admin/providers/circuits`
  - `GET /api/v1/admin/providers/circuits/events`
  - `GET /api/v1/admin/providers/quota-windows`
  - `GET /api/v1/admin/providers/probe-events`
- The endpoints require `ops:providers:read` and return bounded labels/aggregates only: provider, provider category, route family, state, reason bucket, cooldown timestamp, safe operator action reference, quota window counters, probe result bucket, and lifecycle timestamps.
- Responses intentionally omit metadata blobs, owner/guest identifiers, raw provider payloads, raw URLs/query strings, API keys, tokens, cookies, raw session ids, exception text, stack traces, credentials, and developer/internal storage details.
- This landed as diagnostics only. It does not add provider enforcement, live quota enforcement, provider ordering/fallback changes, MarketCache TTL/SWR/cold-start/background refresh/payload-shape changes, Data Pipeline hot-path changes, frontend dashboard UI, or live provider/LLM calls.
- Frontend dashboard surfacing remains future work and should stay read-only/observational until a separately approved enforcement pilot exists.

## WS2-R5 dry-run counter observer implementation note

- A narrow `ProviderCircuitObserver` helper now records synthetic provider observations into the existing provider circuit storage foundation without reading circuit state for enforcement.
- Supported observation buckets are `success`, `timeout`, `provider_429`, `provider_403`, `provider_5xx`, `network_error`, `malformed_payload`, `insufficient_payload`, `auth_or_key_invalid`, `quota_policy_block`, and `operator_disabled`.
- Success and failure observations update `provider_quota_windows` dry-run counters. Failure/state observations append `provider_circuit_events` with `event_type = policy_dry_run`; probe-like observations also write `provider_probe_events`.
- Cooldown observations are event-only and do not transition durable state to `open`, `half_open`, `provider_quota_depleted`, or any enforcing state.
- Metadata continues through the provider circuit storage sanitizer and uses bounded dry-run labels only. Raw URLs, query strings, request params, provider payloads, exception text, stack traces, credentials, tokens, cookies, session ids, and secrets remain out of stored rows and diagnostics responses.
- No runtime provider call site was integrated in this pass. Provider ordering/fallback, Data Pipeline hot-path cooldown, MarketCache TTL/SWR/cold-start/background refresh/payload shape, quota enforcement, frontend UI, scanner, backtest, portfolio, Options Lab, LLM routing, notification, DuckDB, broker/order, and live provider behavior remain unchanged.

## 2. Proposed tables

Design only. Names are proposed for a later additive schema pass.

### `provider_quota_policies`

Purpose: durable provider-specific policy definitions that can complement the existing `quota_policy_definitions` table when provider bucket behavior needs fields that should not be overloaded onto route/model quota rows.

Key fields:

| Field | Purpose |
| --- | --- |
| `id` | Internal primary key. |
| `policy_key` | Stable unique policy identifier. |
| `scope_type` | `global_provider`, `provider`, `provider_route`, `owner_provider`, `owner_provider_route`, or `probe`. |
| `owner_user_id` | Optional owner scope for authenticated users. Null for global/shared policies. |
| `guest_bucket_hash` | Optional safe guest bucket hash when guest traffic needs a separate cap. |
| `provider` | Normalized bounded provider label such as `fmp`, `finnhub`, `yfinance`, `akshare`, `tushare`, `gnews`, `tavily`, or `searxng`. |
| `provider_category` | Bounded data category such as `quote`, `fundamental`, `historical`, `news`, `search`, `market_overview`, or `probe`. |
| `route_family` | Bounded route family such as `analysis`, `async_analysis`, `guest_preview`, `provider_market`, `scanner`, `admin_provider_probe`, or `system`. |
| `window_type` | `minute`, `hour`, `day`, `month`, or `custom`. |
| `request_cap` | Max allowed provider attempts in the window. |
| `budget_unit_cap` | Max estimated provider cost units in the window. |
| `retry_cap` | Max provider attempts/fallback depth for one request envelope. |
| `timeout_cap_ms` | Future aggregate or per-attempt timeout policy field. Does not change current timeouts by itself. |
| `fallback_cap` | Future max fallback attempts for this provider/route policy. |
| `enabled` | Policy row active flag. |
| `effective_from`, `effective_until` | Optional policy lifecycle. |
| `created_at`, `updated_at` | Lifecycle timestamps. |
| `metadata_json` | Sanitized metadata only. |

Owner/global/provider/route dimensions: supports global provider caps, provider-only caps, provider plus route-family caps, owner plus provider caps, and bounded admin probe caps.

Timestamps: `created_at`, `updated_at`, `effective_from`, `effective_until`.

Sanitized metadata policy: metadata may contain policy version, rollout label, dry-run label, safe ticket/audit reference, and bounded operator note code. It must not contain provider URLs, query strings, raw request params, raw response bodies, exception text, stack traces, symbols beyond approved normalized labels, `.env` values, API keys, tokens, cookies, webhook URLs, broker credentials, private keys, raw session ids, or password hashes.

Retention tier: long-lived control-plane table. Keep active rows indefinitely; preserve disabled historical rows for at least 365 days or until superseded by a separate policy-history table.

### `provider_quota_windows`

Purpose: durable accounting windows for provider request/unit reservations and consumption. This is the provider-specific counterpart to existing `quota_usage_windows` when provider buckets need separate states, provider categories, and probe separation.

Key fields:

| Field | Purpose |
| --- | --- |
| `id` | Internal primary key. |
| `policy_key` | Policy row or stable policy label used to compute this window. |
| `owner_user_id` | Optional owner scope. |
| `guest_bucket_hash` | Optional safe guest bucket hash. |
| `provider` | Normalized provider label. |
| `provider_category` | Data category. |
| `route_family` | Route family. |
| `window_type` | `minute`, `hour`, `day`, `month`, or `custom`. |
| `window_start`, `window_end` | Window bounds. |
| `request_count` | Count of completed provider attempts. |
| `reserved_units` | Units reserved but not yet consumed/released. |
| `consumed_units` | Units consumed after sanitized completion. |
| `released_units` | Units released from reservations. |
| `rejected_count` | Count of policy-blocked attempts. |
| `success_count`, `failure_count` | Aggregated provider outcomes. |
| `timeout_count`, `provider_429_count`, `provider_403_count` | Safe failure-family aggregates. |
| `fallback_count` | Count of fallback attempts charged to this window. |
| `probe_count` | Count of admin or half-open probes. |
| `cache_only_count`, `stale_served_count` | Cache-only/stale outcomes when a future route reports them. |
| `created_at`, `updated_at` | Lifecycle timestamps. |
| `metadata_json` | Sanitized metadata only. |

Owner/global/provider/route dimensions: owner and guest buckets are optional; null owner/guest fields represent shared/global buckets. Provider, provider category, route family, and window bounds are the hot lookup dimensions.

Timestamps: `window_start`, `window_end`, `created_at`, `updated_at`.

Sanitized metadata policy: metadata may contain bounded dry-run/enforcement mode, policy version, and safe bucket reason codes. No raw payloads, raw URLs, query params, credentials, raw identifiers, or provider bodies.

Retention tier: raw windows 90-180 days for incident review; daily/monthly aggregate rollups 1-2 years for capacity planning. Cleanup must be preview-first and never treated as rollback.

### `provider_circuit_states`

Purpose: current durable circuit state for a provider/category/route/owner/global scope. This table is the read path for future pre-call checks and admin degraded-state dashboards.

Key fields:

| Field | Purpose |
| --- | --- |
| `id` | Internal primary key. |
| `scope_type` | `global_provider`, `provider`, `provider_route`, `owner_provider`, or `owner_provider_route`. |
| `owner_user_id` | Optional owner scope. |
| `guest_bucket_hash` | Optional safe guest bucket hash. |
| `provider` | Normalized provider label. |
| `provider_category` | Data category. |
| `route_family` | Optional route family. |
| `state` | `closed`, `open`, `half_open`, `degraded_cache_only`, `disabled_by_operator`, or `provider_quota_depleted`. |
| `reason_bucket` | Safe reason bucket. |
| `previous_state` | Previous state for admin display and sanity checks. |
| `opened_at` | When state entered an open/degraded/depleted path. |
| `cooldown_until` | Earliest time a half-open sample can be attempted. |
| `half_open_started_at` | When recovery sampling began. |
| `half_open_sample_limit` | Max approved recovery attempts in the current sample. |
| `half_open_sample_count` | Attempts used in the current sample. |
| `success_sample_count`, `failure_sample_count` | Recovery sample counters. |
| `failure_count`, `success_count` | Bounded current-window counters. |
| `last_transition_event_id` | Reference to the latest event row. |
| `operator_action_ref` | Optional safe audit/action reference. |
| `created_at`, `updated_at` | Lifecycle timestamps. |
| `metadata_json` | Sanitized metadata only. |

Owner/global/provider/route dimensions: supports global provider health, per-route provider health, and owner/guest-specific depletion or abuse guardrails without mixing owner state into global state.

Timestamps: `opened_at`, `cooldown_until`, `half_open_started_at`, `created_at`, `updated_at`.

Sanitized metadata policy: only bounded labels, policy version, safe reason code, safe operator action reference, sample counters, and rollout mode. No raw provider payloads, raw query params, exception text, stack traces, secrets, session ids, or credential-derived details.

Retention tier: current-state table is not TTL-deleted while active. Closed healthy rows may be compacted after 180 days of inactivity if event history is retained.

### `provider_circuit_events`

Purpose: append-only state transition, operator action, and policy decision history. This table is the audit and debugging trail; it is not the hot current-state lookup.

Key fields:

| Field | Purpose |
| --- | --- |
| `id` | Internal primary key. |
| `state_id` | Optional reference to `provider_circuit_states`. |
| `event_type` | `state_transition`, `quota_window_depleted`, `cooldown_elapsed`, `half_open_sample`, `operator_disable`, `operator_enable`, `policy_dry_run`, or `cleanup_marker`. |
| `from_state`, `to_state` | State transition values. |
| `reason_bucket` | Safe reason bucket. |
| `owner_user_id`, `guest_bucket_hash` | Optional owner/guest dimensions. |
| `provider`, `provider_category`, `route_family` | Provider and route dimensions. |
| `request_count_bucket`, `duration_bucket_ms`, `failure_count_bucket` | Coarse counters or buckets only. |
| `quota_window_start`, `quota_window_end` | Optional related accounting window. |
| `operator_action_ref` | Optional safe audit reference. |
| `created_at` | Event timestamp. |
| `metadata_json` | Sanitized metadata only. |

Owner/global/provider/route dimensions: same dimensions as current state, plus event-specific operator and quota references.

Timestamps: `created_at`, optional quota window bounds.

Sanitized metadata policy: event metadata may include safe route labels, policy key/version, enforcement mode, and coarse counts. It must not include raw provider request/response payloads, raw exception text, full stack traces, raw symbols unless explicitly allowed, raw session ids, cookies, API keys, tokens, webhook URLs, broker credentials, private keys, or `.env` values.

Retention tier: raw transition events 180-365 days; operator/security-sensitive events 365+ days; monthly aggregates 1-2 years if dashboards need trends.

### `provider_probe_events`

Purpose: bounded record of admin provider probes and future half-open recovery samples. This keeps probe traffic separate from normal user provider usage and makes probe abuse visible without storing provider payloads.

Key fields:

| Field | Purpose |
| --- | --- |
| `id` | Internal primary key. |
| `probe_type` | `admin_connectivity`, `admin_entitlement`, `half_open_recovery`, or `synthetic_fixture`. |
| `probe_source` | `admin`, `system`, `worker`, or `dry_run`. |
| `actor_user_id` | Optional admin actor for audited probes. |
| `provider`, `provider_category`, `route_family` | Provider and route dimensions. |
| `state_id` | Optional circuit state reference. |
| `result_bucket` | `success`, `timeout`, `provider_429`, `provider_403`, `provider_5xx`, `network_error`, `malformed_payload`, `auth_or_key_invalid`, `quota_policy_block`, or `operator_disabled`. |
| `duration_bucket_ms` | Coarse duration bucket. |
| `created_at` | Probe timestamp. |
| `metadata_json` | Sanitized metadata only. |

Owner/global/provider/route dimensions: normally global/admin scoped, but can include owner/guest bucket only if a future design explicitly authorizes owner-scoped probes.

Timestamps: `created_at`.

Sanitized metadata policy: no raw provider responses, request URLs, params, credentials, raw session ids, cookies, tokens, stack traces, or `.env` values. Store only safe probe type, result bucket, policy version, and audit references.

Retention tier: admin/security probe rows 365 days; synthetic/half-open operational probe rows 90-180 days; aggregates 1 year.

`provider_probe_windows` is not required for the first implementation if `provider_quota_windows` can count probe traffic with `route_family = admin_provider_probe` and `provider_category = probe`. Add it only if admin probe rate limits need a physically separate ledger.

## 3. Index plan

Design targets only. A future migration should keep indexes additive and verify query plans before adding broad JSON or text indexes.

### `provider_quota_policies`

| Lookup | Proposed index shape | Purpose |
| --- | --- | --- |
| Provider + route policy lookup | `scope_type, provider, provider_category, route_family, enabled` | Select active policy before a future provider attempt. |
| Owner/provider policy lookup | `owner_user_id, provider, provider_category, route_family, enabled` | Tenant-specific overrides. |
| Guest/provider policy lookup | `guest_bucket_hash, provider, route_family, enabled` | Guest preview or public bucket caps. |
| Effective policy lookup | `enabled, effective_from, effective_until` | Active policy scans and dashboard display. |
| Admin dashboard | `provider, route_family, updated_at` | Provider policy inventory. |

### `provider_quota_windows`

| Lookup | Proposed index shape | Purpose |
| --- | --- | --- |
| Owner/provider/window lookups | `owner_user_id, provider, route_family, window_start, window_end` | Owner quota accounting. |
| Global provider/window lookups | `provider, provider_category, route_family, window_start, window_end` | Shared provider cap accounting. |
| Probe window lookups | `provider, route_family, provider_category, window_start` | Probe caps when `provider_category = probe`. |
| Event time/admin dashboard | `updated_at` and `window_start` | Recent quota burn and dashboard trend reads. |
| Cleanup | `window_end` | Retention cleanup and dry-run previews. |
| Depletion dashboard | `provider, route_family, consumed_units, window_end` | Dashboard sorting for depleted or high-burn windows. |

### `provider_circuit_states`

| Lookup | Proposed index shape | Purpose |
| --- | --- | --- |
| Provider + route + state lookup | `provider, provider_category, route_family, state` | Hot future pre-call state check. |
| Provider + cooldown lookup | `provider, cooldown_until` | Find circuits eligible for half-open sampling. |
| Owner provider state lookup | `owner_user_id, provider, route_family, state` | Tenant-specific degraded/depleted state. |
| Guest provider state lookup | `guest_bucket_hash, provider, route_family, state` | Guest bucket degraded/depleted state. |
| Admin dashboard | `state, updated_at` and `provider, state, updated_at` | Current degraded provider dashboard. |
| Cleanup | `state, updated_at` | Compact inactive closed rows. |

### `provider_circuit_events`

| Lookup | Proposed index shape | Purpose |
| --- | --- | --- |
| Event time lookup | `created_at` | Timeline and retention cleanup. |
| Provider event timeline | `provider, provider_category, route_family, created_at` | Provider incident drilldown. |
| State transition lookup | `to_state, created_at` | Find recent open/depleted/degraded transitions. |
| Operator action references | `operator_action_ref, created_at` | Audit correlation. |
| Owner event lookup | `owner_user_id, created_at` | Tenant-scoped support/debug view. |
| Cleanup | `event_type, created_at` | Retention by event type. |
| Admin dashboard | `reason_bucket, created_at` | Failure bucket trends. |

### `provider_probe_events`

| Lookup | Proposed index shape | Purpose |
| --- | --- | --- |
| Provider probe timeline | `provider, provider_category, probe_type, created_at` | Probe history for one provider. |
| Actor/admin lookup | `actor_user_id, created_at` | Admin probe audit. |
| Result dashboard | `result_bucket, created_at` | Probe success/failure trends. |
| Half-open lookup | `state_id, created_at` | Recovery sampling history for one circuit. |
| Cleanup | `created_at` | Retention cleanup and dry-run previews. |

## 4. State transition persistence

Future state values:

- `closed`: normal state; provider can be attempted if quota/policy allows.
- `open`: provider/category/route is blocked for live calls until cooldown.
- `half_open`: cooldown elapsed and a small recovery sample is allowed.
- `degraded_cache_only`: future policy allows cache/stale/snapshot-only behavior where existing route semantics already support it; no live provider call is implied.
- `disabled_by_operator`: audited operator/admin action disables the provider/category/route.
- `provider_quota_depleted`: provider or global provider bucket is exhausted, or reliable 429 quota evidence was observed.

Persistence rules:

- Every transition writes one `provider_circuit_events` row before or in the same transaction as the `provider_circuit_states` update.
- `provider_circuit_states.last_transition_event_id` references the latest event where supported.
- Operator actions store only `operator_action_ref`, `actor_user_id` where approved, bounded capability/action labels, and safe reason buckets.
- `cooldown_until` is explicit for `open` and `provider_quota_depleted` when cooldown is time-based.
- `half_open_sample_limit`, `half_open_sample_count`, `success_sample_count`, and `failure_sample_count` persist sample state so multi-instance workers do not over-probe.
- `degraded_cache_only` must not imply a MarketCache behavior change. It is only a future policy state that can be read by routes that already support safe stale/cache-only semantics.

Safe reason buckets:

- `timeout`
- `provider_429`
- `provider_403`
- `provider_5xx`
- `malformed_payload`
- `insufficient_payload`
- `auth_or_key_invalid`
- `network_error`
- `quota_policy_block`
- `operator_disabled`
- `cooldown_elapsed`
- `half_open_sample_succeeded`
- `half_open_sample_failed`
- `manual_admin_action`
- `policy_dry_run`

Do not persist raw error text as a reason. Raw exception strings and provider bodies can include URLs, symbols, parameters, credentials, entitlement details, or stack traces.

## 5. Integration with `QuotaPolicyService`

Design only; no enforcement in this task.

Reuse versus separate tables:

- Reuse existing `quota_policy_definitions`, `quota_usage_windows`, and `quota_reservations` for generic route/model budget behavior and synthetic dry-run operations.
- Add provider-specific tables later only if provider circuits need state that does not fit the existing generic quota ledger: provider category, route-specific circuit state, cooldowns, half-open sample counters, provider failure buckets, and probe separation.
- Avoid overloading `quota_policy_definitions.metadata_json` with circuit state. Current-state and transition history should be first-class rows, not hidden JSON policy blobs.
- Keep provider quota windows separate from circuit events. Windows answer "how much capacity was used"; circuit events answer "why did state change."

Reservation/consume/release mapping:

1. Classify `route_family`, `provider`, `provider_category`, and owner/guest/global bucket.
2. Estimate provider budget units from route/provider policy.
3. In a future dry-run phase, record the would-reserve decision without blocking.
4. In a later enforcement phase, reserve owner/provider/global units before outbound provider work.
5. On sanitized success, consume the reservation and increment success/request counters.
6. On skipped or not-started work, release the reservation.
7. On sanitized failure, consume or release according to policy and update safe failure bucket counters.
8. On policy block, record `quota_policy_block` without calling the provider.

Provider bucket reason codes:

- `provider_quota_depleted`
- `provider_route_quota_depleted`
- `owner_provider_quota_depleted`
- `global_provider_quota_depleted`
- `provider_circuit_open`
- `provider_half_open_sample_limit`
- `provider_disabled_by_operator`
- `provider_probe_quota_depleted`
- `provider_timeout_budget_exceeded`
- `provider_fallback_budget_exceeded`

No enforcement yet:

- Future `QuotaPolicyService` integration should begin as dry-run counters.
- The first implementation should prove storage initialization, sanitized writes, and dashboard reads before any route changes.
- Runtime provider order, fallback chain, retry caps, timeouts, sufficiency checks, and MarketCache behavior stay unchanged until a separate behavior-change task approves enforcement.

## 6. Migration rollout strategy

1. Docs-only now: this file is the migration plan. No schema or code changes are included.
2. Additive schema later: create new tables and indexes without dropping or rewriting existing quota tables.
3. SQLite/local compatibility: define portable baseline tables and indexes for local/dev; reserve PostgreSQL partial or concurrent index optimizations for production migration docs.
4. PostgreSQL production posture: use online/concurrent index guidance for large tables, bounded backfills, and query-plan verification before relying on hot-path reads.
5. Dry-run counters before enforcement: write provider circuit/quota observations while still allowing current runtime behavior.
6. Dashboard before behavior changes: expose read-only admin/provider status, limitations, and data freshness before any blocking logic.
7. Alerting after data quality: only alert after safe reason buckets and duplicate/noise filters are proven.
8. Enforcement later: start with low-risk provider-heavy routes and explicit rollback switches.

Rollback caveats:

- Dropping tables after writes begin loses incident and quota history.
- Retention cleanup is not rollback.
- Disabling enforcement is safer than deleting provider circuit data.
- Closed/current-state rows can be ignored by code if rollback is needed.
- PostgreSQL index rollback is usually a drop-index operation, but table/data rollback must be planned separately.

## 7. Test plan for future implementation

Future implementation should use synthetic fixtures only and must not call live providers.

- table initialization smoke for SQLite/local and PostgreSQL baseline paths;
- additive migration idempotency smoke;
- index/query-plan smoke for provider/state/current lookup and cleanup lookup;
- synthetic provider state transitions:
  - `closed -> open`
  - `open -> half_open`
  - `half_open -> closed`
  - `half_open -> open`
  - `closed -> provider_quota_depleted`
  - `closed -> disabled_by_operator`
  - `open -> degraded_cache_only`
- quota bucket window tests for owner/provider/global/probe windows;
- reservation/consume/release lifecycle tests through synthetic `QuotaPolicyService` calls;
- half-open cooldown and sample-limit tests with no outbound provider calls;
- operator action reference tests with safe audit references only;
- sanitized metadata tests proving no raw secrets, raw payloads, raw URLs, raw query params, stack traces, cookies, tokens, session ids, webhook URLs, private keys, or provider credentials are stored;
- retention dry-run tests for windows/events/probes;
- admin dashboard read tests using seeded synthetic rows only;
- no live provider, LLM, broker, scanner, backtest, portfolio, notification, Options Lab, or MarketCache refresh calls.

## 8. Non-goals

- No provider ordering or fallback changes.
- No MarketCache behavior changes.
- No live provider enforcement.
- No LLM/provider calls.
- No frontend dashboard implementation.
- No scanner behavior change.
- No backtest behavior change.
- No portfolio behavior change.
- No Options Lab behavior change.
- No RBAC behavior change.
- No notification, broker, DuckDB, prompt, model-routing, or report behavior change.
- No schema migration in this pass.
- No tests in this pass.

## 9. Recommended next Codex prompts

1. Implement an additive schema migration for provider circuit/quota storage from `docs/audits/ws2-provider-circuit-data-model-plan.md`. Create only portable SQLite/local initialization and PostgreSQL baseline table/index definitions. Do not wire enforcement, do not change provider ordering/fallback, do not change MarketCache behavior, and do not call live providers.
2. Add synthetic-only storage tests for provider circuit state transitions and provider quota windows. Use fixture rows only; do not call live providers, LLMs, MarketCache refresh paths, scanner, backtest, portfolio, Options Lab, broker, notification, or DuckDB runtime.
3. Add a read-only admin diagnostics API for provider circuit state seeded by synthetic rows. Return safe bounded labels only and do not expose raw provider payloads, URLs, credentials, session ids, stack traces, or `.env` values. Do not add enforcement or frontend UI.
4. Add provider circuit/quota dry-run counters around provider instrumentation without blocking calls. Preserve provider order, fallback, retry, timeout, in-flight coalescing, sufficiency checks, MarketCache TTL/SWR/cold-start behavior, and all product route semantics.
5. Design the frontend admin provider circuit dashboard UX as a docs-only contract. Do not implement frontend code, do not call providers, and keep dashboard data read-only and explicitly observational until enforcement is separately approved.
