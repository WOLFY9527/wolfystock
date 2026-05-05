# Provider Fallback Budget Reporting Design

Date: 2026-05-06
Mode: docs-only design. No runtime behavior changed.

## 1. Purpose

This note designs future read-only provider fallback budget reporting. It builds on:

- `docs/audits/llm-external-api-cost-audit.md`
- `docs/audits/llm-provider-duplicate-cost-metrics-design.md`
- `docs/audits/duplicate-cost-admin-summary-api-design.md`

The goal is to measure provider fallback cost pressure before changing provider ordering, fallback behavior, caching, timeouts, retries, circuit behavior, or budgets.

The report should help operators:

- measure provider fallback chain depth by provider category, market, and endpoint family;
- identify quota-risk provider usage patterns, especially 403, 429, quota, permission, and rate-limit buckets;
- distinguish availability fallback from avoidable duplicate cost;
- surface insufficient-payload fallback separately from transport failures;
- show cache and inflight coalescing benefits before any reuse or budget policy changes;
- preserve current provider ordering and fallback behavior until measured data justifies a separate approved policy review.

This document does not implement counters, APIs, runtime changes, UI, tests, cache, or provider logic.

## 2. Confirmed current behavior

Confirmed by static inspection:

- `src/services/analysis_provider_planner.py::build_analysis_provider_plan()` defines market-aware provider chains by `DataCategory`. US chains include FMP, Finnhub, yfinance, Alpha Vantage, Alpaca, GNews, Tavily, and local fallbacks. CN chains include AkShare, Tushare, pytdx, baostock, efinance, GNews, Tavily, and local fallbacks.
- `src/services/analysis_provider_planner.py::AnalysisProviderExecutor.execute_plan()` runs independent provider categories concurrently.
- `src/services/analysis_provider_planner.py::AnalysisProviderExecutor.execute_category()` attempts providers in order, skips open circuits, records `attempts`, treats insufficient data as `invalid_payload`, classifies exceptions into `timeout`, `rate_limited`, `provider_unavailable`, `invalid_payload`, and `unknown_error`, then falls through to the next provider until `max_attempts`.
- `src/services/analysis_provider_planner.py::AnalysisProviderExecutor._get_or_call()` provides in-process `_cache` hits and `_inflight` coalescing by provider/category/symbol/params cache key. It applies per-category timeouts and only caches data that passes `_has_sufficient_data()`.
- `src/services/analysis_provider_planner.py::AnalysisProviderExecutor._is_circuit_open()`, `_record_failure()`, and `_record_success()` maintain provider/category circuit state in process.
- `src/core/pipeline.py::StockAnalysisPipeline._fetch_us_supplemental_categories()` calls the provider planner for US supplemental `fundamentals`, `earnings`, `historical_prices`, `technical_indicators`, and optional `quote`. It returns the plan, per-category metadata, attempts, partial categories, and failure reasons to the analysis context.
- `data_provider/us_fundamentals_provider.py` contains module-level `_request_cache`, `_cache_get()`, and `_cache_set()` for FMP, Finnhub, and yfinance helper calls. `_request_json()` performs HTTP GET with timeout and raises on HTTP status.
- `data_provider/base.py::DataFetcherManager.get_daily_data()` has ordered provider fallback for daily data. US symbols prefer Alpaca when configured and then Yfinance; HK tries Twelve Data before the generic fetcher chain; other markets iterate configured fetchers and continue on failure.
- `data_provider/base.py::DataFetcherManager._classify_provider_error()` buckets realtime provider failures into `timeout`, `empty_result`, `invalid_response`, `insufficient_fields`, and `provider_error`.
- `src/services/market_cache.py::MarketCache.get_or_refresh()` provides in-memory Market Overview cache behavior: fresh hit, stale-while-revalidate, background refresh, cold-start timeout fallback, and fallback factory use.
- `src/services/market_overview_service.py::MarketOverviewService._cached_payload()` wraps Market Overview fetchers with `MarketCache`, `_market_data_cache`, persistent snapshot fallback, and fallback factories. It does not expose hit/miss counters today.
- `src/services/market_overview_service.py::MarketOverviewService._panel()`, `_market_snapshot()`, and `_classified_snapshot()` record Market Overview fetches through `ExecutionLogService.record_market_overview_fetch()` with cache/fallback metadata.
- `api/v1/endpoints/market.py` exposes Market Overview-related route families such as `/api/v1/market/crypto`, `/sentiment`, `/cn-indices`, `/cn-breadth`, `/cn-flows`, `/sector-rotation`, `/us-breadth`, `/rates`, `/fx-commodities`, `/temperature`, `/market-briefing`, `/futures`, and `/cn-short-sentiment`.
- `api/v1/endpoints/market_overview.py` exposes independent panel routes under `/api/v1/market-overview`, including `indices`, `volatility`, `sentiment`, `funds-flow`, and `macro`.
- `api/v1/endpoints/analysis.py::preview_analysis()` and analysis routes are endpoint-family sources of analysis-provider pressure. `preview_analysis()` calls `AnalysisService.analyze_stock()` with `persist_history=False`.
- `src/services/system_config_service.py::SystemConfigService.test_builtin_data_source()` runs bounded manual remote data-provider validation through `src/providers/validation.py::validate_provider_connection()`. This is a probe path, not background reporting.
- `src/providers/validation.py` exists and supports FMP, Finnhub, Alpha Vantage, Twelve Data, Tushare, and Yahoo/YFinance validation checks with bounded timeouts and sanitized result shapes.

Confirmed provider sources and chains:

- Analysis provider planner chains exist for FMP, Finnhub, yfinance, Alpha Vantage, Alpaca, AkShare, Tushare, pytdx, baostock, efinance, GNews, Tavily, `social_sentiment_service`, `local_history`, `local_inference`, `local_market_context`, and `static_mapping`.
- Market Overview providers include Binance, Binance WS in the realtime service path, CNN Fear & Greed, Alternative.me, Sina, Eastmoney, yfinance/Yahoo, and computed/fallback sources.
- Manual provider connectivity probes exist for supported built-in data providers, but this design must not call them.

Inferred, not confirmed as existing metrics:

- There are logs and runtime metadata for attempts, fallback use, cache state, provider health, and failures, but no confirmed durable provider fallback budget counter set.
- `AnalysisProviderExecutor` returns attempts in runtime results, but this is not a read-only aggregate report.
- Market Overview execution logs expose some cache/fallback evidence, but they are not exact cache hit/miss/fallback-depth counters.

## 3. Reporting questions

The future report should answer:

- Which provider categories trigger the deepest fallback chains?
- Which providers fail, time out, or return invalid/insufficient payloads most often?
- Which provider categories show insufficient-payload fallback rather than transport failure?
- Which providers are quota-risk due to 403, 429, quota, permission, entitlement, or rate-limit buckets?
- Which provider categories benefit from `_cache` hits and `_inflight` joins?
- Which endpoint families drive provider fallback pressure: analysis sync, guest preview, async analysis, Market Overview panels, Market Overview realtime snapshots, admin provider probes, or background services?
- Which fallback chains are intentional availability behavior rather than avoidable duplicate cost?
- Which provider chains repeatedly succeed only after late fallback, suggesting cost or quota pressure but not necessarily waste?
- Which cache keys or hashed symbols show repeated provider attempts inside a reporting window?
- Where are fallback attempts paired with successful cache/inflight coalescing, indicating existing cost protection is working?

## 4. Proposed dimensions and safe labels

Use bounded labels:

- `provider`
- `provider_category`
- `market`
- `endpoint_family`
- `route`
- `fallback_depth`
- `attempt_index`
- `outcome`
- `retry_reason_bucket`
- `error_bucket`
- `duration_bucket`
- `cache_key_hash`
- `symbol_hash` when necessary
- `owner_scope`
- `freshness_bucket`

Recommended `endpoint_family` values:

- `analysis_sync`
- `analysis_preview`
- `analysis_async`
- `market_overview_panel`
- `market_realtime_snapshot`
- `market_realtime_stream`
- `admin_provider_probe`
- `scanner`
- `system`

Recommended `outcome` values:

- `success`
- `failed`
- `skipped`
- `partial`
- `cache_hit`
- `cache_miss`
- `inflight_join`
- `stale_served`
- `fallback_served`

Recommended `retry_reason_bucket` and `error_bucket` values:

- `timeout`
- `rate_limited`
- `quota_or_entitlement`
- `forbidden_or_unauthorized`
- `provider_unavailable`
- `invalid_payload`
- `insufficient_payload`
- `empty_result`
- `circuit_open`
- `missing_key`
- `unsupported_provider`
- `unknown_error`

Reject these labels and payload fields:

- raw URLs or query strings;
- API keys, tokens, Authorization headers, cookies, webhook URLs, or credential-bearing config values;
- provider response bodies;
- raw exception text;
- raw stack traces;
- raw user ids, account ids, session ids, or guest session ids;
- raw provider params;
- raw prompts, chat messages, news payloads, uploaded images, or LLM/provider raw payloads;
- unbounded symbols unless hashed;
- exact cache keys unless hashed;
- full model/channel configuration or secret channel names.

## 5. Proposed event/counter model

These event names are conceptual only. They do not exist today unless a future task implements them.

| Event/counter | Purpose | Suggested emission site | Labels | Question answered | Guardrails |
| --- | --- | --- | --- | --- | --- |
| `provider_call_started` | Count provider attempt starts before outbound work or local provider helper work begins. | `AnalysisProviderExecutor._get_or_call()`, `DataFetcherManager.get_daily_data()`, selected Market Overview fetcher wrappers. | `provider`, `provider_category`, `market`, `endpoint_family`, `route`, `attempt_index`, `cache_key_hash`, `symbol_hash`. | How many provider attempts are triggered per endpoint family and category? | Non-blocking; no raw URLs, params, symbols, or response bodies. |
| `provider_call_completed` | Count successful provider attempts and duration. | After sufficient payload is accepted in `AnalysisProviderExecutor.execute_category()`; successful `DataFetcherManager` provider branch; successful Market Overview fetcher wrapper. | Started labels plus `outcome=success`, `duration_bucket`, `freshness_bucket`, `fallback_depth`. | Which providers/categories succeed, and at what fallback depth? | Do not treat success as billing truth. Duration must be bucketed. |
| `provider_call_failed` | Count failed provider attempts. | Exception branches in `AnalysisProviderExecutor.execute_category()`, provider fetcher fallback branches, Market Overview fetch wrapper failures. | `provider`, `provider_category`, `market`, `endpoint_family`, `attempt_index`, `error_bucket`, `duration_bucket`. | Which providers fail or time out most often? | Bucket sanitized reasons only; never emit stack traces or raw response text. |
| `provider_fallback_attempt` | Count movement from one provider to the next. | `AnalysisProviderExecutor.execute_category()` after failed/insufficient/skipped attempts; `DataFetcherManager.get_daily_data()` when continuing to next fetcher. | `provider_category`, `market`, `endpoint_family`, `from_provider`, `to_provider`, `fallback_depth`, `retry_reason_bucket`. | Which chains are deepest and why? | Preserve ordering and fallback behavior; observe only. |
| `provider_insufficient_payload` | Count payloads that returned but did not satisfy category needs. | `AnalysisProviderExecutor.execute_category()` invalid-payload branch; `DataFetcherManager` insufficient-field branches; `MarketOverviewService._is_storable_market_snapshot()` rejection path if instrumented later. | `provider`, `provider_category`, `market`, `endpoint_family`, `attempt_index`, `fallback_depth`. | Which fallbacks are caused by insufficient content rather than availability? | Do not emit raw payload fields or provider body excerpts. |
| `provider_timeout` | Count timeout bucket separately from other failures. | `ProviderTimeout` handling in `AnalysisProviderExecutor.execute_category()`; timeout branches in provider managers; MarketCache cold-start timeout classification when reporting Market Overview pressure. | `provider`, `provider_category`, `market`, `endpoint_family`, `duration_bucket`, `attempt_index`. | Which providers/categories consume timeout budget? | Do not change timeout values. |
| `provider_quota_risk_observed` | Count quota-risk signals such as 403, 429, quota, entitlement, permission, or rate-limit patterns. | `AnalysisProviderExecutor._classify_exception()`, `src/providers/validation.py` check result normalization, provider HTTP wrappers where status is known. | `provider`, `provider_category`, `market`, `endpoint_family`, `error_bucket`, `attempt_index`. | Which providers are likely quota or entitlement constrained? | Do not print credential values or raw provider error bodies. |
| `provider_cache_hit` | Count existing provider cache hits. | `AnalysisProviderExecutor._get_or_call()` cache-hit branch; future wrapper around `us_fundamentals_provider._cache_get()` callers. | `provider`, `provider_category`, `market`, `endpoint_family`, `cache_key_hash`, `freshness_bucket`. | Which categories avoid calls due to existing cache? | Hash cache keys; do not expose symbol or params raw. |
| `provider_cache_miss` | Count provider cache misses. | `AnalysisProviderExecutor._get_or_call()` miss before submitting call; future US helper wrapper miss. | Same as cache hit plus `miss_reason`. | Which misses drive provider attempts? | Observational only; do not add caching semantics. |
| `provider_inflight_join` | Count singleflight joins where duplicate work is coalesced. | `AnalysisProviderExecutor._get_or_call()` when `_inflight` already has the key. | `provider`, `provider_category`, `market`, `endpoint_family`, `cache_key_hash`. | How much duplicate cost is already avoided? | Do not expose raw key; do not mutate `_inflight`. |
| `provider_duplicate_candidate_observed` | Observe repeated provider request identity before behavior changes. | `AnalysisProviderExecutor._get_or_call()` and route/service entry metadata. | `provider`, `provider_category`, `market`, `endpoint_family`, `cache_key_hash`, `symbol_hash`, `freshness_bucket`, `owner_scope`. | Which repeated attempts might be avoidable after measurement? | Candidate only; do not block or dedupe. |

Market Overview-related companion counters can feed this report without changing `MarketCache` behavior:

| Event/counter | Purpose | Suggested emission site | Labels | Question answered | Guardrails |
| --- | --- | --- | --- | --- | --- |
| `market_cache_hit` | Count fresh MarketCache hits. | `MarketCache.get_or_refresh()` fresh-hit branch. | `provider_category`, `route`, `cache_key_hash`, `freshness_bucket`. | Which panel keys are already protected? | No payloads. |
| `market_cache_miss` | Count cold misses. | `MarketCache.get_or_refresh()` cold placeholder path. | `provider_category`, `route`, `cache_key_hash`. | Which routes create cold provider pressure? | Do not alter cold-start behavior. |
| `market_cache_stale_served` | Count stale responses served during refresh. | `MarketCache.get_or_refresh()` stale branch. | `provider_category`, `route`, `cache_key_hash`, `freshness_bucket`. | Is fallback pressure being absorbed by stale serving? | Do not change SWR semantics. |
| `market_cache_cold_start_fallback_served` | Count cold-start fallback due to timeout/failure. | `MarketCache.get_or_refresh()` cold fallback branches. | `provider_category`, `route`, `cache_key_hash`, `error_bucket`. | Which panels need budget visibility under cold starts? | No fallback payload body. |

Manual provider probes should be labeled separately:

- `endpoint_family=admin_provider_probe`
- `owner_scope=admin`
- `outcome` from sanitized `ProviderResult`
- never mixed into automatic runtime fallback rates unless the report explicitly separates manual probes from user-driven runtime traffic.

## 6. Proposed read-only report shape

Future API concept only. Do not implement in this task.

```json
{
  "generatedAt": "...",
  "window": { "from": "...", "to": "...", "bucket": "hour|day" },
  "summary": {
    "providerCalls": 0,
    "fallbackAttempts": 0,
    "quotaRiskEvents": 0,
    "timeoutEvents": 0,
    "insufficientPayloadEvents": 0,
    "cacheHitRate": null,
    "inflightJoins": 0
  },
  "byProviderCategory": [],
  "byProvider": [],
  "fallbackChains": [],
  "quotaRisk": [],
  "cacheEfficiency": [],
  "limitations": [],
  "metadata": {
    "readOnly": true,
    "noExternalCalls": true,
    "providerOrderingUnchanged": true
  }
}
```

Suggested item shapes:

```json
{
  "byProviderCategory": [
    {
      "providerCategory": "fundamentals",
      "market": "us",
      "providerCalls": 0,
      "fallbackAttempts": 0,
      "maxFallbackDepth": 0,
      "insufficientPayloadEvents": 0,
      "timeoutEvents": 0,
      "quotaRiskEvents": 0,
      "cacheHits": 0,
      "cacheMisses": 0,
      "inflightJoins": 0
    }
  ],
  "fallbackChains": [
    {
      "providerCategory": "fundamentals",
      "market": "us",
      "endpointFamily": "analysis_sync",
      "chain": ["fmp", "finnhub", "yfinance"],
      "observedCount": 0,
      "successProvider": "yfinance",
      "fallbackDepth": 2,
      "reasonBuckets": ["rate_limited", "insufficient_payload"],
      "classification": "availability_fallback"
    }
  ],
  "quotaRisk": [
    {
      "provider": "fmp",
      "providerCategory": "quote",
      "market": "us",
      "endpointFamily": "analysis_preview",
      "events": 0,
      "errorBuckets": ["rate_limited"],
      "affectedFallbackChains": 0
    }
  ],
  "cacheEfficiency": [
    {
      "provider": "fmp",
      "providerCategory": "fundamentals",
      "market": "us",
      "cacheHits": 0,
      "cacheMisses": 0,
      "hitRate": null,
      "inflightJoins": 0,
      "duplicateCandidatesObserved": 0
    }
  ]
}
```

Required limitations:

- `instrumentation_counters_required_for_exact_fallback_budget`
- `existing_attempt_metadata_is_runtime_context_not_durable_aggregate`
- `market_cache_current_state_is_process_local`
- `provider_call_counts_are_not_billing_truth`
- `manual_provider_probes_are_separate_from_user_runtime_pressure`

## 7. Integration with duplicate-cost admin summary

This report should feed the future duplicate-cost admin summary by supplying provider-specific fallback budget fields:

- provider calls by category, market, route, and endpoint family;
- fallback attempts and max fallback depth;
- insufficient-payload events;
- timeout and quota-risk buckets;
- cache hit/miss and inflight-join rates;
- duplicate provider request candidates by safe hash.

Relationship to existing docs:

- `docs/audits/llm-external-api-cost-audit.md` identified fallback chains and in-process caches as cost-risk areas.
- `docs/audits/llm-provider-duplicate-cost-metrics-design.md` proposed instrumentation-only provider events. This design narrows the provider-side report shape for fallback budget pressure.
- `docs/audits/duplicate-cost-admin-summary-api-design.md` defines a broader duplicate-cost summary. This provider fallback report can be a nested `providers.fallbackBudget` section or a separate admin-only source feeding that summary.
- `docs/audits/market-overview-cache-reporting-design.md`, if present, should stay focused on MarketCache hit/stale/miss and panel cache behavior. This provider fallback report should consume Market Overview cache metrics only as one pressure source and must not change TTL/SWR/cold-start/fallback semantics.

Future dashboard relationship:

- A Market Provider Operations dashboard follow-up can use these aggregates to show provider pressure without adding live probes.
- Future provider budget alerting should wait until instrumentation proves stable labels, privacy safety, and acceptable cardinality.
- Any provider ordering, budget cap, or fallback policy change must be a separate approved task after measured evidence exists.

## 8. Rollout plan

Phase 1: instrumentation-only provider counters

- Add non-blocking counters at confirmed provider seams.
- Cover `AnalysisProviderExecutor.execute_category()`, `_get_or_call()`, provider cache/inflight branches, selected `DataFetcherManager` fallback branches, and Market Overview cache/fetch wrappers only where behavior can remain unchanged.
- Use synthetic tests only.
- Do not expose an API yet.

Phase 2: backend-only read-only fallback budget summary

- Add an admin-only read-only service and route after counters exist.
- Aggregate counters plus existing sanitized execution-log/context metadata.
- Return limitations and data-source exactness.
- Do not call providers, LLMs, validation probes, cache refreshers, or background jobs.

Phase 3: optional admin dashboard section

- Add UI only after the backend contract stabilizes.
- Keep copy clear that values are operational measurements, not billing truth.
- Separate manual provider probes from runtime traffic.

Phase 4: evidence-based provider policy review

- Only after sufficient measured evidence, propose provider budget, provider ordering, fallback, timeout, retry, or circuit policy changes in a separate approved design and implementation task.
- Keep that future review separate from measurement/reporting work.

## 9. Guardrails

Future implementation must:

- be read-only and non-blocking;
- never trigger provider calls;
- never call real LLM APIs;
- never run manual connectivity probes as part of report generation;
- never mutate cache, config, logs, snapshots, reports, scanner runs, backtests, portfolios, notifications, or DuckDB runtime;
- never change provider order, fallback behavior, provider timeout values, retry behavior, or circuit behavior;
- never change `MarketCache` TTL, stale-while-revalidate, background refresh, cold-start timeout, fallback factories, or persistent snapshot behavior;
- never expose secrets, raw payloads, raw provider params, raw URLs/query strings, raw exception text, raw stack traces, raw user/session ids, raw prompts, raw messages, raw images, or raw news payloads;
- use bounded labels and safe hashes only;
- use synthetic tests only;
- clearly report limitations, data-source exactness, and process-local caveats;
- separate availability fallback from avoidable duplicate-cost candidates;
- separate manual admin provider probes from user-driven runtime provider pressure.

Explicitly out of scope for this design:

- counters implementation;
- API endpoint implementation;
- frontend/admin UI implementation;
- runtime provider behavior changes;
- provider ordering changes;
- fallback, timeout, retry, or circuit changes;
- MarketCache behavior changes;
- scanner, backtest, portfolio, AI, notification, or DuckDB behavior changes;
- dependency additions.

## 10. Recommended follow-up Codex tasks

1. Instrumentation-only provider fallback counters.
   Scope: backend counters at `AnalysisProviderExecutor`, selected `DataFetcherManager` branches, and Market Overview cache/fetch seams. No behavior changes. Synthetic tests only.

2. Backend-only provider fallback budget summary with synthetic tests.
   Scope: admin-only read-only aggregation over new counters and existing sanitized metadata. No provider calls, no LLM calls, no cache mutation.

3. Duplicate-cost admin summary integration.
   Scope: add provider fallback budget fields to the broader duplicate-cost summary once both contracts are stable.

4. Optional admin dashboard section after backend API stabilizes.
   Scope: read-only visualization of fallback depth, quota risk, insufficient payloads, timeout buckets, and cache/inflight efficiency.

5. Separate provider policy review only after measured evidence.
   Scope: evaluate provider ordering, fallback, budget, timeout, retry, or circuit policy with measured evidence. This must be a separate approved task and must not be bundled with reporting.

