# WS2-R5 Provider Quota and Circuit Breaker Policy Design

Status: Deferred
Owner domain: Provider and MarketCache readiness
Related docs: `docs/audits/ws2-provider-circuit-data-model-plan.md`, `docs/audits/provider-fallback-budget-reporting-design.md`

Date: 2026-05-06
Mode: docs-only design. No runtime behavior, provider ordering, fallback behavior, MarketCache behavior, schema, migrations, enforcement code, tests, live providers, or servers were changed.

## 1. Executive summary

WolfyStock already has useful provider/cache observability and a quota policy foundation, but public multi-user usage needs an explicit provider quota and circuit breaker policy before any fallback behavior changes. Without that policy, one noisy user, repeated preview route, cold cache miss burst, manual probe loop, or provider outage can consume shared provider capacity, deepen fallback chains, and degrade all users.

In scope for this design:

- provider quota dimensions for future policy and ledger rows;
- circuit breaker states, transitions, cooldowns, and visibility;
- safe failure buckets for timeout, 429, 403, malformed data, quota blocks, and operator controls;
- fallback rules for retry caps, stop conditions, stale/cache-only mode, fail-fast behavior, and freshness disclosure;
- future integration points for `QuotaPolicyService`, provider call instrumentation, MarketCache, admin dashboards, readiness, alerting, and route-level enforcement;
- data model sketches only, including retention tiers.

Not changed in this pass:

- no runtime provider behavior;
- no provider ordering or fallback chain changes;
- no MarketCache TTL, stale-while-revalidate, background refresh, or cold-start fallback changes;
- no quota enforcement integration on live routes;
- no schema, migration, model, API, frontend, tests, or provider adapters;
- no live provider, LLM, broker, scanner, backtest, portfolio, notification, Options Lab, RBAC, or DuckDB behavior.

## 2. Current provider/caching posture

Current provider fallback and counters:

- `AnalysisProviderExecutor` builds market-aware provider chains by category, attempts providers in order, limits attempts by `max_attempts`, skips process-local open circuits, and falls through after timeout, failure, circuit-open skip, or insufficient payload.
- Provider categories can run concurrently, while duplicate provider/category/symbol/params work can be coalesced through an in-process `_inflight` map.
- Existing provider events such as `provider_call_started`, `provider_call_completed`, `provider_call_failed`, `provider_fallback_attempt`, `provider_timeout`, `provider_quota_risk_observed`, `provider_cache_hit`, `provider_cache_miss`, and `provider_inflight_join` are process-local observability counters. They are not billing truth and do not enforce quotas.
- Existing provider circuit state is process-local, category-scoped, and failure-threshold based. It is not a durable multi-instance policy contract.

Current MarketCache posture:

- `MarketCache` is an in-memory, process-local cache with per-panel TTLs, stale-while-revalidate, background refresh, cold-start timeout fallback, fallback factory support, and freshness/error metadata in returned payloads.
- Existing MarketCache events such as `market_cache_hit`, `market_cache_stale_served`, `market_cache_miss`, `market_cache_refresh_started`, `market_cache_refresh_completed`, `market_cache_refresh_failed`, and `market_cache_cold_start_fallback_served` are observability counters.
- This design requires any future shared cache or provider circuit integration to preserve current TTL, stale serving, cold-start timeout, background refresh, fallback factory, and freshness disclosure semantics until a separate behavior-change approval exists.

Cost observability versus enforcement:

- `QuotaPolicyService` now has a synthetic foundation for route weights, budget-unit estimation, global kill switch, per-user budget, route caps, token caps, provider/model labels, reservations, consumption, release, and safe rejection reason codes.
- Current provider and MarketCache counters are useful for measurement, dashboards, and dry-run policy tuning.
- They do not block calls, reserve provider buckets, stop fallback chains, or globally coordinate across API instances.

Known risks:

| Risk | Current concern | Design response |
| --- | --- | --- |
| 429 / rate limit | One provider can become depleted and every user keeps reaching it first. | Add provider quota windows, `provider_429` failure bucket, cooldown, and `provider_quota_depleted` state. |
| 403 / entitlement | Missing entitlement or invalid credentials can repeatedly fail and trigger expensive fallback. | Classify `provider_403` and `auth_or_key_invalid`; fail fast for credential faults until operator action. |
| Timeout | Slow providers consume worker/request capacity and trigger deep fallback. | Add timeout caps, timeout error buckets, and open/degraded circuits by provider/category/route. |
| Cache stampede | Cold process or multi-instance misses can start many identical external calls. | Keep MarketCache behavior unchanged now; future policy should combine singleflight, quota precheck, and stale/cache-only fallback. |
| Stale provider data | Serving stale or fallback data without disclosure can erode trust. | Preserve and require freshness disclosure for stale/cache-only modes. |
| Noisy users | One owner can consume shared provider capacity through repeated routes or probes. | Add owner bucket and global bucket dimensions with route-family caps. |

## 3. Provider quota dimensions

Future provider quota policy should evaluate these dimensions before outbound provider work begins:

| Dimension | Purpose | Example values / notes |
| --- | --- | --- |
| `provider` | Isolate FMP, Finnhub, yfinance, Alpha Vantage, AkShare, Tushare, GNews, Tavily, and other providers. | Use bounded normalized names only. |
| `route_family` | Separate analysis, preview, Market Overview, scanner, admin probe, and system traffic. | Suggested values: `analysis`, `async_analysis`, `guest_preview`, `provider_market`, `scanner`, `admin_provider_probe`, `system`. |
| `owner_user_id` bucket | Prevent one authenticated user or guest bucket from depleting shared quota. | Store owner/user bucket or safe hash according to existing owner-scope conventions. |
| Global bucket | Protect provider-wide capacity regardless of owner. | Required for shared third-party provider limits. |
| Request window | Bound calls per minute/hour/day by provider and route family. | Use short windows for burst control and daily/monthly windows for budget planning. |
| Retry/fallback cap | Bound total provider attempts per user request and per route family. | Prevent cascading fallback during outages. |
| Timeout cap | Bound time spent per provider attempt and aggregate route/provider stage. | Preserve current timeouts until future implementation approval. |
| External probe/test cap | Prevent admin provider validation loops from exhausting quota. | Probe/test traffic must stay separate from user runtime traffic. |
| Cost unit integration | Convert provider attempts into quota units through `QuotaPolicyService`. | Add provider-specific unit weights later; current service already supports provider labels and route weights. |

Quota decisions should happen in this order in a future implementation:

```text
classify route/provider/owner
  -> check operator disable and global kill switch
  -> check provider circuit state
  -> estimate request units and timeout/retry envelope
  -> reserve owner + provider + route + global buckets
  -> perform existing provider call path unchanged
  -> consume or release reservation from sanitized result
```

## 4. Circuit breaker states

| State | Entry conditions | Exit conditions | Cooldown | Allowed operations | User/admin-visible behavior | Safe logging/metrics |
| --- | --- | --- | --- | --- | --- | --- |
| `closed` | Default healthy state; recent failure rate below threshold; quota available. | Move to `open`, `provider_quota_depleted`, `disabled_by_operator`, or `degraded_cache_only` when policy triggers. | None. | Existing provider calls, cache hits, stale serving, and fallback according to current behavior. | Normal freshness and provider metadata. | Count calls, successes, failures, latency buckets, cache state. |
| `open` | Failure rate, timeout rate, 5xx rate, malformed/insufficient payload rate, or repeated 429 crosses policy threshold. | After cooldown, enter `half_open`; operator can force disabled/enabled only through future audited controls. | Provider/category/route specific, with jitter. | No new live calls to this provider/category except approved half-open probes after cooldown. | User sees fallback, stale/cache-only disclosure, or safe failure depending on route policy. | Log `circuit_open` with provider/category/route, reason bucket, window, no raw payload. |
| `half_open` | `open` cooldown elapsed and policy allows a small recovery sample. | Success count moves to `closed`; failure returns to `open`; quota depletion moves to `provider_quota_depleted`. | Short and sample-limited. | One or a few synthetic or real low-cost attempts, never broad traffic. | Admin sees recovery sampling; users should not see raw test details. | Log sample outcome, duration bucket, safe failure bucket. |
| `degraded_cache_only` | Provider is unhealthy, external quota is risky, or route policy permits serving stale/cache-only instead of failing. | Provider recovers, operator clears degraded mode, or freshness expires beyond route tolerance. | Route/freshness dependent. | Cache hit, stale serving, persistent snapshot/fallback factory where existing product semantics allow it. No new live provider calls. | User sees stale/cache-only freshness disclosure and degraded status. | Count `cache_only_served`, stale age bucket, provider/category, no payload. |
| `disabled_by_operator` | Future audited admin action disables provider/category/route after incident or maintenance. | Future audited enable action; optional cooldown before half-open. | Operator-defined. | No live provider calls. Cache-only may be allowed if route policy permits. | Admin dashboard shows disabled state and actor/audit reference; users see safe unavailable/degraded message. | Audit actor, capability, reason, provider/category, no secrets. |
| `provider_quota_depleted` | Provider bucket or global provider cap is exhausted, or provider returns reliable 429 quota evidence. | Window resets, quota is replenished, operator changes policy, or cooldown moves to half-open if policy allows. | Until quota window reset or configured cooldown. | No live calls except maybe admin-approved probe cap; fallback/cache-only according to route policy. | User sees rate/quota-safe degraded or unavailable message; admin sees depleted bucket. | Count depletion reason, window, remaining units bucket, no provider body. |

## 5. Failure classification

Future provider policy should use these safe buckets only:

| Bucket | Meaning | Retry/circuit implication |
| --- | --- | --- |
| `timeout` | Provider did not complete within the approved timeout envelope. | Retry/fallback may be allowed until caps; repeated timeouts can open circuit. |
| `provider_429` | Provider indicates rate limit or quota depletion. | Prefer circuit/quota depletion over repeated retry; fallback only if cap remains. |
| `provider_403` | Provider denies access or entitlement. | Usually fail fast or operator attention; do not keep probing with same credentials. |
| `provider_5xx` | Provider service error. | Retry/fallback may be allowed with backoff; repeated failures open circuit. |
| `malformed_payload` | Response cannot be parsed or violates expected shape. | Fallback may be allowed; repeated malformed responses open circuit. |
| `insufficient_payload` | Parsed payload lacks enough useful fields for the category. | Fallback may be allowed; track separately from transport errors. |
| `auth_or_key_invalid` | Credential or entitlement configuration appears invalid. | Fail fast and disable/protect provider until operator action. |
| `network_error` | DNS/connect/TLS/connection failure without provider status. | Retry/fallback with cap; repeated failures open circuit. |
| `quota_policy_block` | Internal quota policy denied the attempt before outbound work. | Do not retry live provider; report safe quota reason. |
| `operator_disabled` | Future operator policy disabled provider/category/route. | Do not call provider; cache-only only if allowed. |

Do not store or emit raw URLs, query strings, request params, provider response bodies, raw exception text, stack traces, raw symbols where not explicitly approved, API keys, tokens, cookies, webhook URLs, credentials, private keys, `.env` values, raw session IDs, or provider payload snippets.

## 6. Fallback policy

Fallback is allowed when:

- the failure bucket is transient: `timeout`, `provider_5xx`, `network_error`, `malformed_payload`, or `insufficient_payload`;
- route policy has remaining retry/fallback budget;
- the next provider is not `open`, `disabled_by_operator`, or `provider_quota_depleted`;
- the provider bucket and global bucket have capacity;
- fallback will not violate user-visible freshness requirements.

Fallback should stop when:

- retry/fallback cap is reached;
- aggregate timeout cap is reached;
- failure is `auth_or_key_invalid`, `operator_disabled`, or a hard quota policy block;
- every remaining provider is open, disabled, quota-depleted, or outside route entitlement;
- fallback would hide stale or low-confidence data without disclosure.

Stale/cache-only is allowed when:

- current route already supports stale, fallback factory, or persisted snapshot semantics;
- data freshness remains within the approved route tolerance;
- response includes freshness, stale/cache-only, generated-at/as-of, and degraded disclosure;
- policy explicitly prevents a new live provider call during degraded state.

Fail fast when:

- credentials or entitlement appear invalid;
- operator disabled the provider;
- global kill switch is active;
- route is not allowed to serve stale/cache-only data;
- owner/global/provider quota is depleted and fallback is not approved;
- serving stale data would be misleading or materially unsafe.

Retry cap:

- Count the primary provider attempt plus fallback attempts in one request-level budget.
- Count half-open probes and admin probes separately from normal user traffic.
- Future implementation should record `attempt_index`, `fallback_depth`, `retry_reason_bucket`, and final stop reason.

Avoid cascading provider failures:

- Do not fan out all providers when the first provider fails.
- Respect per-provider open/depleted state before attempting fallback.
- Use jittered cooldowns and half-open sample limits.
- Keep admin probes capped and separate from runtime traffic.
- Prefer stale/cache-only mode over walking a deep fallback chain during broad provider outages.

Freshness disclosure:

- Preserve MarketCache `isRefreshing`, `isStale`, warning, and freshness metadata patterns.
- Future route responses should disclose provider source, cache/stale state, as-of/generated-at timestamps, and degraded reason bucket where product-safe.
- Do not expose raw provider payloads or credential/config details in disclosure.

## 7. Integration points

Design only; no implementation in this pass.

`QuotaPolicyService` provider bucket integration:

- Extend policy use from route/model budgets to provider-specific request and unit windows.
- Add safe reason codes later for `provider_quota_depleted`, `operator_disabled`, and `circuit_open` if enforcement is implemented.
- Keep reservations explicit and release/consume on sanitized outcomes.

Provider call instrumentation:

- Use existing bounded provider events as the measurement seam.
- Future enforcement should be placed before outbound calls, while instrumentation failures remain best-effort and non-blocking.
- Do not mutate provider order, timeout values, cache key construction, `_inflight` behavior, or sufficiency checks as part of enforcement wiring.

MarketCache interaction:

- Circuit policy can read MarketCache observability and may decide to serve cache-only in future routes.
- It must not change TTLs, SWR behavior, background refresh scheduling, cold-start timeout fallback, fallback factories, or payload shape in this design.
- Shared cache proposals need a separate behavior and migration design.

Admin cost/provider dashboard:

- Add read-only provider quota/circuit state after policy storage exists.
- Distinguish process-local counters from durable policy state.
- Show limitations clearly: observational counters are not billing truth.

Readiness/degraded status:

- Readiness should expose bounded degraded provider state, provider bucket depletion, and global kill switches.
- Liveness should not fail only because one provider is degraded.
- Expensive routes can reject new work while the API remains live.

Alerting:

- Alert on repeated `provider_429`, `provider_403`, `auth_or_key_invalid`, open circuits, provider bucket depletion, deep fallback chains, high stale/cache-only rate, and admin probe abuse.
- Alerts must use safe labels and never include raw provider response text or credentials.

Future route-level enforcement:

- Start with dry-run counters.
- Pilot on low-risk provider-heavy routes.
- Keep analysis, scanner, backtest, portfolio, Options Lab, notification, broker, and DuckDB behavior out of scope unless explicitly approved.

## 8. Data model sketch

Design only; no schema or migration in this pass.

Provider quota policy:

| Field | Purpose |
| --- | --- |
| `policy_key` | Stable policy identifier. |
| `scope_type` | `provider`, `provider_route`, `owner_provider`, `global_provider`, or `probe`. |
| `provider` | Normalized provider label. |
| `route_family` | Route family label. |
| `owner_bucket` | Optional owner/user bucket or null for shared/global. |
| `window_type` | `minute`, `hour`, `daily`, `monthly`. |
| `request_cap` | Max requests in window. |
| `budget_unit_cap` | Max estimated provider units in window. |
| `retry_cap` | Max attempts/fallback depth. |
| `timeout_cap_ms` | Aggregate or per-attempt timeout cap. |
| `enabled` | Policy enabled flag. |
| `metadata_json` | Sanitized metadata only. |

Provider circuit state:

| Field | Purpose |
| --- | --- |
| `provider` | Provider label. |
| `provider_category` | Data category or route category. |
| `route_family` | Optional route family. |
| `state` | One of the six states in this design. |
| `reason_bucket` | Safe reason bucket. |
| `opened_at`, `cooldown_until`, `updated_at` | State timing. |
| `failure_count`, `success_sample_count` | Bounded window counters. |
| `operator_action_ref` | Optional audit reference, not raw reason text. |

Provider usage/counter windows:

| Field | Purpose |
| --- | --- |
| `provider`, `route_family`, `owner_bucket` | Scope. |
| `window_type`, `window_start`, `window_end` | Accounting window. |
| `request_count`, `reserved_units`, `consumed_units` | Quota accounting. |
| `success_count`, `failure_count`, `fallback_count` | Observability aggregate. |
| `timeout_count`, `provider_429_count`, `provider_403_count` | Failure-family aggregate. |
| `cache_hit_count`, `stale_served_count`, `cache_only_count` | Cache interaction aggregate. |

Circuit event/audit rows:

| Field | Purpose |
| --- | --- |
| `event_id` | Stable event id. |
| `provider`, `provider_category`, `route_family` | Scope. |
| `from_state`, `to_state` | Transition. |
| `reason_bucket` | Safe reason. |
| `actor_type`, `actor_ref` | `system` or future audited admin reference. |
| `metadata_json` | Sanitized bounded metadata. |
| `created_at` | Event time. |

Retention tiers:

- raw provider counter events: 30-90 days;
- provider usage windows: raw windows 90-180 days, aggregates 1 year or longer;
- circuit state: current row retained while active, historical state transitions 1 year;
- admin/operator circuit audit: 365 days minimum;
- provider probe events: shorter operational retention, for example 30-90 days, unless tied to admin security audit;
- no raw provider payload, secret, request URL, credential, or full cache key retention.

## 9. Admin UX

Read-only provider quota/circuit state dashboard:

- show provider, category, route family, state, reason bucket, cooldown remaining, last transition time, request budget, unit budget, retry/fallback cap, timeout cap, and recent safe aggregates;
- separate runtime traffic, admin probes, and system/background traffic;
- label process-local observational counters separately from durable quota/circuit policy state;
- disclose limitations when counters are not durable or not multi-instance complete.

Manual disable/enable future actions:

- future action controls must require explicit admin capability, reason, typed confirmation for broad disable, and audit event reference;
- disabling a provider should be provider/category/route scoped, not an accidental global behavior change;
- enabling should move through `half_open` when policy requires recovery sampling.

Safe probe/test rules:

- probe/test routes must have their own caps and cooldowns;
- probes must never reveal raw provider responses, request URLs, headers, credentials, `.env` values, or raw stack traces;
- probe outcomes should use safe buckets and should not be mixed into runtime provider health unless dashboard explicitly separates them.

No credential exposure:

- no raw API keys, provider credentials, tokens, cookies, webhook URLs, private keys, password hashes, raw session IDs, or provider response bodies;
- env var names may appear in docs/UI help, but values must never be displayed.

## 10. Test plan

Future implementation should use only synthetic adapters and local fixtures:

- synthetic provider adapter tests for success, failure, cache hit, stale/cache-only, and fallback paths;
- 429 simulation mapped to `provider_429` without raw response body exposure;
- 403 simulation mapped to `provider_403` or `auth_or_key_invalid` without credential exposure;
- timeout simulation with existing timeout behavior preserved;
- malformed and insufficient payload simulation;
- half-open recovery success and failure transitions;
- open to half-open cooldown behavior with jitter-safe assertions;
- stale/cache-only mode without changing MarketCache TTL/SWR/cold-start behavior;
- owner bucket and global bucket isolation;
- admin probe cap and runtime traffic separation;
- quota reservation consume/release behavior for provider buckets;
- no live providers, LLMs, brokers, external network, browser routes, or real credentials;
- static checks that logs/metrics/test outputs do not contain raw secrets, raw provider payloads, raw URLs, request params, stack traces, raw cache keys, or raw session IDs.

## 11. Rollout plan

1. Design only: this document, no runtime behavior change.
2. Policy schema: add provider quota/circuit storage only after approval, with SQLite/local compatibility and no enforcement.
3. Dry-run counters: reconcile provider instrumentation with provider quota buckets and circuit state in observe-only mode.
4. Enforcement pilot: enable one low-risk provider/route family with synthetic and staged evidence, preserving provider ordering and fallback unless explicitly approved.
5. Dashboard: add read-only admin provider quota/circuit state, limitations, and degraded readiness.
6. Provider behavior changes: only after policy approval, dry-run evidence, dashboard visibility, rollback plan, and explicit acceptance criteria.

## 12. Recommended next Codex prompts

1. "In `/Users/yehengli/daily_stock_analysis` on `main`, create a docs-only provider quota/circuit data model migration plan. Do not add migrations, runtime code, tests, providers, schema files, or enforcement. Preserve provider ordering, fallback, and MarketCache behavior."
2. "In `/Users/yehengli/daily_stock_analysis` on `main`, implement only synthetic provider circuit state tests and local fake adapter policy tests. Do not call live providers or change runtime provider behavior."
3. "In `/Users/yehengli/daily_stock_analysis` on `main`, add dry-run provider quota bucket accounting behind disabled-by-default policy wiring. Do not enforce, reorder providers, change fallback, change MarketCache, or call live providers."
4. "In `/Users/yehengli/daily_stock_analysis` on `main`, design a read-only admin provider quota/circuit dashboard contract. Do not implement frontend/backend routes or runtime enforcement."
5. "In `/Users/yehengli/daily_stock_analysis` on `main`, perform a report-only privacy review of provider/quota/circuit logs and metric labels. Do not modify code."

## 13. Scope confirmations

This design intentionally does not change:

- runtime provider behavior;
- provider ordering/fallback;
- MarketCache TTL/SWR/cold-start behavior;
- scanner, backtest, portfolio calculations;
- Options Lab;
- RBAC routes;
- WS2 task queue/progress runtime;
- quota enforcement runtime;
- notification routing;
- DuckDB;
- broker/order paths.
