# Provider / MarketCache Instrumentation Validation Plan

Date: 2026-05-06
Mode: docs-only QA plan. No runtime behavior changed.

## 1. Purpose

This plan defines how to validate future Phase 1B provider fallback/cache instrumentation and Phase 1C MarketCache hit/stale/miss instrumentation after implementation.

The validation goal is narrow: prove counters are emitted at the expected seams while provider behavior, MarketCache semantics, external-call behavior, cache mutation, API payload semantics, and user-visible behavior remain unchanged. This plan does not implement counters, tests, APIs, cache behavior, runtime changes, or UI.

Phase 1B should validate provider attempt, fallback-depth, cache-hit/miss, inflight-join, insufficient-payload, timeout, quota-risk, and duplicate-candidate counters. Phase 1C should validate MarketCache fresh-hit, stale-served, miss, refresh, failure, and cold-start fallback counters.

## 2. Expected provider event coverage

| Event | Expected emission scenario | Behavior that must remain unchanged | Privacy guardrails |
| --- | --- | --- | --- |
| `provider_call_started` | A provider attempt is about to begin at an existing provider executor, data fetcher, helper wrapper, or scoped Market Overview provider seam. | Do not add provider calls, reorder providers, alter attempt gating, change timeout/retry/circuit logic, or change validation probe behavior. | Use bounded labels only. Do not emit raw URLs, params, symbols, headers, credentials, request bodies, or response bodies. |
| `provider_call_completed` | A provider attempt succeeds and the existing code accepts the result as sufficient or otherwise successful. | Do not change sufficiency checks, caching eligibility, success classification, returned payloads, or downstream metadata. | Bucket duration and freshness. Do not emit provider payload fields or raw result content. |
| `provider_call_failed` | A provider attempt fails through an existing exception, unavailable-provider, invalid-response, or rejected-result branch. | Do not change exception propagation, fallback continuation, failure classification used by runtime behavior, or circuit state updates. | Emit sanitized `error_bucket` only. Do not emit raw exception text, raw stack traces, raw status bodies, or provider error payloads. |
| `provider_fallback_attempt` | Existing code moves from one provider attempt to the next because of failure, timeout, insufficient payload, circuit-open skip, or unsupported path. | Preserve provider chain order, fallback conditions, max attempts, skip behavior, and stop conditions. | `from_provider`, `to_provider`, `fallback_depth`, and reason buckets must be bounded. No raw request identity. |
| `provider_insufficient_payload` | A provider returns data that existing sufficiency validation rejects, causing fallback or failure. | Do not loosen or tighten sufficiency validation, storable-snapshot checks, field normalization, or fallback behavior. | Do not emit missing raw fields, raw payload snippets, or provider body excerpts. Use `insufficient_payload` or bounded field-family buckets only. |
| `provider_timeout` | Existing timeout handling fires for a provider attempt or validation probe branch. | Do not change timeout values, timeout wrappers, cancellation behavior, background task behavior, fallback behavior, or exception semantics. | Bucket duration. Do not emit raw timeout exception text or low-level stack traces. |
| `provider_quota_risk_observed` | Existing error classification sees quota, entitlement, permission, forbidden, unauthorized, 403, 429, or rate-limit evidence. | Do not add provider probes, do not retry differently, do not suppress or force fallback, and do not inspect secret values. | Emit only `quota_or_entitlement`, `rate_limited`, `forbidden_or_unauthorized`, or similar bounded buckets. Never emit provider response bodies. |
| `provider_cache_hit` | An existing provider cache returns a cached result and prevents the provider call that would otherwise occur. | Do not change cache key construction, cache TTL, acceptance semantics, mutation timing, or returned object semantics. | Emit `cache_key_hash`, not raw cache keys, symbols, params, URLs, or payloads. |
| `provider_cache_miss` | Existing provider cache lookup misses before the normal provider call path proceeds. | Do not add caching, change miss behavior, prefill cache, mutate cache earlier, or change external call count. | Emit a safe hash and bounded miss reason only. Do not expose raw key components. |
| `provider_inflight_join` | Existing singleflight or inflight coalescing joins an already-running provider request. | Do not change `_inflight` lifecycle, lock timing, coalescing semantics, duplicate-call behavior, or exception sharing. | Emit only bounded labels and `cache_key_hash`. Do not expose raw inflight key or payload. |
| `provider_duplicate_candidate_observed` | A repeated provider request identity is observed as a candidate for future measurement, without blocking or deduping it. | Do not dedupe, cache, block, delay, reorder, or reuse responses. Candidate observation must be informational only. | Use safe hashes, bounded labels, and short retention where possible. Do not expose raw user/session ids, symbols, params, URLs, or payloads. |

## 3. Expected MarketCache event coverage

| Event | Expected emission scenario | Behavior that must remain unchanged | Privacy guardrails |
| --- | --- | --- | --- |
| `market_cache_hit` | `MarketCache` serves an existing fresh entry. | Preserve TTL, freshness calculation, response object, metadata, and no-refresh behavior for fresh hits. | Emit `cache_key_hash`, bounded route family, bounded panel key when safe, and freshness bucket only. No snapshot payload. |
| `market_cache_stale_served` | `MarketCache` serves stale data while preserving existing stale-while-revalidate behavior. | Do not change stale eligibility, returned stale payload, `isRefreshing` semantics, background refresh scheduling, or fallback behavior. | No raw cache key or stale payload. Emit bounded freshness and route/panel labels only. |
| `market_cache_miss` | A cold cache miss enters the existing cold-start fetch or fallback path. | Do not change cold-start timeout, fetch submission, fallback factory use, persistent snapshot fallback, or response semantics. | Hash cache identity. Do not emit raw symbols, URLs, snapshot payloads, or fallback payload bodies. |
| `market_cache_refresh_started` | Existing refresh work starts for a cold miss, stale refresh, or background refresh. | Do not change refresh scheduling, thread/executor behavior, lock behavior, or fetcher invocation count. | Emit bounded labels only. Do not include raw fetcher params or provider URLs. |
| `market_cache_refresh_completed` | Existing refresh work completes successfully and existing cache mutation occurs. | Do not change cache write timing, TTL, snapshot persistence, freshness metadata, or payload transformation. | Do not emit raw payloads or full snapshot metadata. Use duration/freshness buckets. |
| `market_cache_refresh_failed` | Existing refresh work fails and current stale/fallback/error semantics continue. | Do not change stale preservation, fallback response, exception swallowing/propagation, retry scheduling, or execution logs. | Emit sanitized `error_bucket`. Do not emit raw exception text, stack traces, URLs, provider bodies, or snapshot payloads. |
| `market_cache_cold_start_fallback_served` | Existing cold-start timeout/failure fallback returns fallback factory or persistent snapshot data. | Do not change fallback factory behavior, cold-start timeout, persistent snapshot selection, `isRefreshing`, or user-visible response shape. | Emit bounded fallback reason and route/panel labels only. No fallback payload body or raw snapshot key. |

## 4. Privacy validation checklist

Check that no metric, log, label, debug field, test assertion output, or admin summary field includes:

- raw URLs or query strings
- API keys/tokens
- provider response bodies
- raw provider params
- raw exception text
- raw stack traces
- raw user/session ids
- raw prompts/messages/news/images
- raw cache keys
- raw snapshot payloads

Allowed labels should be bounded or hashed:

- `provider`
- `provider_category`
- `market`
- `endpoint_family`
- route family
- `fallback_depth`
- `attempt_index`
- `outcome`
- `retry_reason_bucket`
- `error_bucket`
- `duration_bucket`
- `cache_key_hash`
- `symbol_hash` only when necessary
- `freshness_bucket`
- `panel_key` if bounded and non-sensitive

Validation should include static review and focused grep checks for unsafe label names or string formatting that could leak raw payloads, params, provider URLs, exception text, cache keys, or snapshots.

## 5. Behavior preservation checklist

Provider instrumentation must not change:

- provider ordering
- fallback conditions
- timeout values
- retry behavior
- circuit state behavior
- cache TTLs
- `_cache` semantics
- `_inflight` coalescing behavior
- provider validation probe behavior
- external call count

MarketCache instrumentation must not change:

- TTL
- stale-while-revalidate behavior
- background refresh scheduling
- cold-start timeout
- fallback factory behavior
- persistent snapshot behavior
- freshness metadata
- response payload semantics

Implementation review should compare call order, branch conditions, lock scope, exception paths, cache mutation points, and returned values before and after instrumentation. Metric helper failures must be swallowed or isolated so they cannot affect runtime behavior.

## 6. Suggested synthetic tests

Provider tests:

- cache hit emits hit counter without provider call
- cache miss emits miss/start/completed on synthetic success
- inflight join emits join without duplicate provider call
- fallback path emits fallback attempt but preserves provider order
- timeout path emits timeout/failure bucket without changing exception behavior
- quota-risk classification emits quota bucket without raw provider body

MarketCache tests:

- fresh hit emits hit and returns same payload
- stale served emits stale and starts same refresh behavior
- cold miss emits miss and preserves fallback behavior
- refresh success emits refresh started/completed
- refresh failure emits failed and preserves stale/fallback behavior
- metric helper failure is swallowed

Do not implement these tests in this task. Future tests should use synthetic fetchers, fake counters, local fixtures, and call-count assertions only. They must not call live providers, real LLM APIs, manual provider probes, browser routes, or external network services.

## 7. Manual diff review checklist

Review future implementation for:

- no provider order changes
- no timeout/retry/circuit changes
- no MarketCache TTL/SWR/cold-start changes
- no API response shape changes unless explicitly scoped
- no external network calls added
- no dependency additions
- no frontend changes
- bounded labels only
- helper failures non-blocking

Also review that new instrumentation helpers do not read secret config values, print environment values, format raw exceptions into labels, mutate cache keys, alter lock scopes, or introduce background tasks beyond the existing refresh/inflight behavior.

## 8. Recommended commands after implementation

Suggested backend-only verification after a future implementation:

```bash
python3 -m py_compile <touched_backend_files>
python3 -m pytest <focused_provider_executor_synthetic_tests> -q
python3 -m pytest <focused_marketcache_synthetic_tests> -q
rg -n "raw_url|query_string|Authorization|api_key|token|response_body|stack|traceback|cache_key|snapshot" <touched_files>
./scripts/ci_gate.sh
```

Clarifications:

- no live provider calls
- no live LLM calls
- no browser required for backend instrumentation-only work
- run `./scripts/ci_gate.sh` only when repo state allows and concurrent dirty files will not contaminate the result
- if future changes touch docs or `.env.example`, run the relevant docs/config checks required by `AGENTS.md`

## 9. Acceptance criteria

Implementation is acceptable only if:

- behavior unchanged
- provider calls unchanged under synthetic tests
- MarketCache semantics unchanged under synthetic tests
- labels safe and bounded
- metric failures non-blocking
- no raw secrets/payloads emitted
- final git status clean except unrelated files

Acceptance evidence should include call-count assertions, exact synthetic test commands, static privacy review, diff review against behavior-sensitive branches, and a final status report that separates task files from unrelated concurrent dirty files.

## 10. Follow-up sequence

After provider/MarketCache validation passes:

1. Scanner AI duplicate candidate counter Phase 1D
2. Backend duplicate-cost summary API
3. Optional admin UI after backend contract stabilizes
4. Cache/reuse prototypes only after measured evidence

The sequence remains measurement first, read-only reporting second, and cache/reuse behavior changes only after the measured evidence and disclosure model justify them.
