# LLM / Provider Duplicate-Cost Metrics Design

Date: 2026-05-06
Mode: docs-only design. No runtime behavior changed.

## 1. Purpose

This note turns `docs/audits/llm-external-api-cost-audit.md` into an implementation-ready instrumentation plan. The goal is to measure duplicate-cost patterns around LLM and external provider calls before adding caching, routing changes, or behavior changes.

Confirmed risk areas from the prior audit are repeated same-symbol same-day report generation, LLM fallback and integrity retry loops, Market Overview panel fan-out on cache miss or stale refresh, mostly in-process US provider caches, and optional scanner AI top-N interpretation calls.

## 2. Metrics principles

- Instrumentation-only first. Counters and events must observe existing behavior, not optimize it.
- Do not change provider ordering, fallback behavior, retry behavior, prompt logic, model routing, AI decision logic, scanner ranking/selection, MarketCache TTL/SWR/cold-start semantics, backtest calculations, portfolio accounting, notification routing, or DuckDB runtime.
- Metrics must be best-effort and non-blocking. Metric failure must never fail a user request.
- Labels must be bounded. Avoid high-cardinality labels unless they are safe hashes.
- Use safe hashes for inputs when identity is needed. Never emit raw prompts, raw news, raw images, uploaded bytes, conversation text, API keys, tokens, or secret config values.
- Distinguish confirmed runtime paths from proposed instrumentation. The event names below are proposed; they are not confirmed to exist today.

## 3. Proposed metric events/counters

| Metric | Purpose | Suggested emission site | Safe dimensions | Avoid as labels | Duplicate-cost report use |
| --- | --- | --- | --- | --- | --- |
| `llm_call_started` | Count every outbound LLM attempt before the call leaves the process. | `src/analyzer.py::_call_litellm()`, `src/agent/llm_adapter.py::LiteLLMAdapter.call_completion()`, image extractor vision call wrapper. | `call_type`, `model_family`, `provider`, `route`, `attempt_index`, `fallback_depth`, `prompt_version`, `input_hash`. | raw prompt, raw messages, raw image bytes, API key, base URL with query. | Baseline LLM attempts per user action or report. |
| `llm_call_completed` | Count successful LLM attempts and duration. | Same LLM call seams, after response parsing and usage extraction. | started labels plus `outcome=success`, `duration_bucket`, `token_bucket`. | raw response, stack trace, exact tokenized prompt. | LLM calls per successful analysis/report/scanner interpretation. |
| `llm_call_failed` | Count failed LLM attempts. | Same LLM call seams, inside exception/failure path. | `call_type`, `provider`, `model_family`, `attempt_index`, `fallback_depth`, `outcome`, `retry_reason`. | exception text as unbounded label, raw response body. | Failure-driven fallback and retry multiplier. |
| `llm_fallback_attempt` | Count model/provider fallback transitions. | `src/analyzer.py::_call_litellm()` attempt trace transition; `src/agent/llm_adapter.py::LiteLLMAdapter.call_completion()` when moving to the next model. | `call_type`, `from_model_family`, `to_model_family`, `fallback_depth`, `retry_reason`. | raw configured model list, secret channel names. | Fallback attempts per completed report or agent call. |
| `llm_integrity_retry` | Count report integrity retry prompts. | `src/analyzer.py::GeminiAnalyzer.analyze()` when `_build_integrity_retry_prompt()` is used. | `call_type=analysis`, `report_type`, `language`, `attempt_index`, `retry_reason`, `missing_field_bucket`. | missing field values from raw LLM output, raw retry prompt. | Integrity retry rate by model/report/language. |
| `llm_duplicate_candidate_observed` | Observe duplicate-cost candidates without blocking or deduping. | Before LLM calls in `GeminiAnalyzer.analyze()`, `generate_text_with_meta()`, scanner interpretation, and guest preview/sync entry metadata. | `call_type`, `owner_scope`, `symbol_hash`, `report_type`, `language`, `freshness_bucket`, `cache_key_hash`, `source_snapshot_hash`. | raw symbol if policy requires hash, raw owner id, prompt/news/image payload. | Same symbol/report/language/freshness requested repeatedly. |
| `llm_usage_persisted` | Confirm token accounting persistence happened. | After `persist_llm_usage()` in `src/analyzer.py` and agent runner/adapter callers that persist usage. | `call_type`, `model_family`, `provider`, `token_bucket`, `stock_scope`. | exact user id, raw prompt. | Compare attempted calls with persisted usage rows. |
| `provider_call_started` | Count outbound provider attempt start. | `src/services/analysis_provider_planner.py::AnalysisProviderExecutor._get_or_call()` and US helper request wrappers. | `provider`, `provider_category`, `market`, `symbol_hash`, `attempt_index`, `cache_key_hash`. | raw URL, query string, API key, raw response. | Provider calls per analysis request/category. |
| `provider_call_completed` | Count successful provider attempts. | Same provider seams after sufficient data or HTTP success normalization. | started labels plus `outcome=success`, `duration_bucket`, `freshness_bucket`. | raw payload, full URL. | Success/fallback depth by category. |
| `provider_call_failed` | Count provider failures and timeouts. | `AnalysisProviderExecutor.execute_category()`, US helper request exception paths, Market Overview fetchers when wrapped later. | `provider`, `provider_category`, `market`, `outcome`, `retry_reason`, `duration_bucket`. | raw stack trace, raw response body, raw provider error body. | Which failures multiply fallback chains. |
| `provider_fallback_attempt` | Count provider chain movement after a failed/insufficient provider. | `AnalysisProviderExecutor.execute_category()` after invalid payload, timeout, quota, or exception. | `provider_category`, `from_provider`, `to_provider`, `fallback_depth`, `retry_reason`, `market`. | raw params, raw URL. | Fallback attempts per successful category. |
| `provider_cache_hit` | Count existing in-process provider cache hits. | `AnalysisProviderExecutor._get_or_call()` cache hit branch; `data_provider/us_fundamentals_provider.py::_cache_get()` caller wrappers if instrumented later. | `provider`, `provider_category`, `market`, `cache_key_hash`, `freshness_bucket`. | raw symbol if not approved, raw cache key. | Hit rate by provider/category. |
| `provider_cache_miss` | Count cache misses that proceed toward a provider call or inflight join. | Same cache miss branches. | same as cache hit plus `miss_reason`. | raw params. | Miss-driven provider fan-out. |
| `provider_inflight_join` | Count coalesced calls joining existing in-flight work. | `AnalysisProviderExecutor._get_or_call()` when `_inflight` already has the key. | `provider`, `provider_category`, `market`, `cache_key_hash`. | raw cache key. | How often existing coalescing avoids duplicate cost. |
| `provider_duplicate_candidate_observed` | Observe repeated provider request identity before any behavior change. | `AnalysisProviderExecutor._get_or_call()` and US helper/cache wrapper boundaries. | `provider`, `provider_category`, `market`, `symbol_hash`, `cache_key_hash`, `freshness_bucket`. | raw URL, raw params, raw response. | Same provider/category/symbol requested repeatedly. |
| `market_cache_hit` | Count fresh MarketCache hits. | `src/services/market_cache.py::MarketCache.get_or_refresh()` fresh hit branch. | `panel_key`, `provider_category`, `route`, `freshness_bucket`. | full URL, raw payload. | Market Overview hit rate by panel key. |
| `market_cache_stale_served` | Count stale values served while refresh proceeds. | `MarketCache.get_or_refresh()` stale branch. | `panel_key`, `provider_category`, `route`, `freshness_bucket`, `is_refreshing`. | raw snapshot payload. | Stale-served rate and refresh pressure. |
| `market_cache_miss` | Count cold misses before fetch/fallback. | `MarketCache.get_or_refresh()` before creating placeholder/cold fetch. | `panel_key`, `provider_category`, `route`. | raw payload. | Cold-start fan-out detection. |
| `market_cache_refresh_started` | Count refresh start. | `MarketCache._start_background_refresh()` and cold refresh path. | `panel_key`, `provider_category`, `route`, `refresh_mode`. | raw payload. | Refresh concurrency and fan-out. |
| `market_cache_refresh_completed` | Count refresh success. | `MarketCache._refresh()` success path. | `panel_key`, `provider_category`, `route`, `duration_bucket`. | raw payload. | Successful refresh rate. |
| `market_cache_refresh_failed` | Count refresh failure. | `MarketCache._refresh()` exception path and cold fetch exception path. | `panel_key`, `provider_category`, `route`, `retry_reason`. | raw exception text as label. | Failure-related stale/fallback serving. |
| `market_cache_cold_start_fallback_served` | Count fallback served because cold fetch timed out or failed. | `MarketCache.get_or_refresh()` cold-start fallback branches. | `panel_key`, `provider_category`, `route`, `freshness_bucket`. | fallback payload. | Cold-start fallback frequency. |
| `scanner_ai_interpretation_started` | Count scanner AI interpretation attempts. | `src/services/scanner_ai_service.py::ScannerAiInterpretationService.interpret_shortlist()` before `_interpret_candidate()`. | `market`, `profile`, `rank_bucket`, `candidate_hash`, `top_n`, `prompt_version`. | raw candidate reasons, raw symbol if hashing required. | Interpretations per run/top-N. |
| `scanner_ai_interpretation_completed` | Count generated scanner interpretations. | Same service after generated payload. | started labels plus `outcome=generated`, `model_family`, `provider`. | raw generated text. | Generated/failed rate by profile. |
| `scanner_ai_interpretation_skipped` | Count disabled, unavailable, non-CN, empty, or beyond-top-N skips. | Same service skip branches. | `market`, `profile`, `skip_reason`, `top_n`, `rank_bucket`. | raw candidate payload. | Confirms bounded AI cost policy is holding. |
| `scanner_ai_duplicate_candidate_observed` | Observe repeated candidate interpretation identity. | Before `_interpret_candidate()`, using run/candidate/prompt hash. | `market`, `profile`, `candidate_hash`, `prompt_version`, `model_family`, `language`. | raw reasons/watch context. | Repeated scanner AI calls for same candidate payload. |

## 4. Safe dimensions / labels

Use bounded labels:

- `call_type`
- `provider`
- `provider_category`
- `model_alias` or `model_family`, not raw secret config
- `route` or endpoint family
- `symbol_type` or `market`, where useful
- `symbol_hash` if symbol-level precision is required
- `owner_scope` such as `authenticated`, `guest`, `admin`, or `system`; use hashed user/session ids only when a report genuinely needs per-owner precision
- `report_type`
- `language`
- `cache_key_hash`
- `prompt_version`
- `source_snapshot_hash`
- `freshness_bucket`
- `attempt_index`
- `fallback_depth`
- `retry_reason`
- `outcome`
- `duration_bucket`

Reject these labels:

- raw prompts
- raw conversation text
- raw image data or uploaded bytes
- raw news payloads
- API keys, tokens, credentials, Authorization headers, webhook URLs, or secret values
- full user identifiers, account identifiers, or un-hashed session ids
- unbounded URLs or query strings
- raw stack traces or provider response bodies as labels

## 5. Emission-site map

| Area | File/function | Metric(s) | Duplicate-cost question answered | Notes/guardrails |
| --- | --- | --- | --- | --- |
| Main stock LLM report | `src/analyzer.py::GeminiAnalyzer.analyze()` | `llm_duplicate_candidate_observed`, `llm_integrity_retry`, `llm_usage_persisted` | Was the same symbol/report/language/freshness generated more than once, and did integrity retry multiply calls? | Confirmed path. Do not change prompts, parser, integrity policy, or placeholder fill. |
| Shared report LLM call | `src/analyzer.py::_call_litellm()` | `llm_call_started`, `llm_call_completed`, `llm_call_failed`, `llm_fallback_attempt` | How many model attempts occur per analysis or text-generation request? | Proposed only. Do not alter model try order or fallback trace. |
| Free-form LLM helper | `src/analyzer.py::generate_text_with_meta()` | `llm_call_started`, `llm_call_completed`, `llm_call_failed`, `llm_usage_persisted`, `llm_duplicate_candidate_observed` | Which non-report callers repeat exact prompt/input identities? | Hash inputs only; do not log prompt text. |
| Agent LLM | `src/agent/llm_adapter.py::LiteLLMAdapter.call_completion()` | `llm_call_started`, `llm_call_completed`, `llm_call_failed`, `llm_fallback_attempt` | Do agent/chat/tool calls retry across models repeatedly? | Chat is personalized; avoid generic response cache assumptions. |
| Vision extraction | `src/services/image_stock_extractor.py::extract_stock_codes_from_image()` | `llm_call_started`, `llm_call_completed`, `llm_call_failed`, `llm_duplicate_candidate_observed` | Are identical image hashes being reprocessed? | Never store raw image data or data URLs in metrics. |
| Scanner AI | `src/services/scanner_ai_service.py::ScannerAiInterpretationService.interpret_shortlist()` | scanner AI metrics plus LLM call metrics through `generate_text_with_meta()` | How many top-N interpretations are generated per run/candidate hash? | AI remains additive; ranking, score, thresholds, and selection stay untouched. |
| US supplemental provider executor | `src/services/analysis_provider_planner.py::AnalysisProviderExecutor._get_or_call()` | provider call/cache/inflight/duplicate metrics | Which provider/category/symbol calls miss cache or join inflight? | Confirmed `_cache` and `_inflight`; do not change TTLs, circuit behavior, or provider order. |
| US fundamentals helpers | `data_provider/us_fundamentals_provider.py` request helpers and cache helpers | provider call/cache/duplicate metrics | Which FMP/Finnhub/yfinance helper calls repeat after in-process cache misses? | Mention env var names only, never values; avoid raw URL/query labels. |
| MarketCache | `src/services/market_cache.py::MarketCache.get_or_refresh()` | MarketCache metrics | Which panel keys hit, serve stale, miss, refresh, fail, or serve cold fallback? | Do not change TTL/SWR/background/cold-start semantics. |
| Market Overview service | `src/services/market_overview_service.py` cached payload/fetch paths | provider call metrics, MarketCache labels, existing execution-log correlation | Which panels fan out to external providers on cache miss/stale refresh? | Existing `record_market_overview_fetch()` logs are confirmed; keep high-volume success metrics out of default user-visible logs unless intentionally summarized. |
| Task queue dedupe | `src/services/task_queue.py` duplicate in-flight analysis dedupe | `llm_duplicate_candidate_observed` or future `analysis_inflight_duplicate_observed` | How many async duplicate submissions are already avoided per owner/symbol? | Confirmed in-flight dedupe only; do not dedupe completed analyses here. |
| Analysis APIs | `api/v1/endpoints/analysis.py` sync and preview paths | duplicate candidate metrics with `route`, `owner_scope`, `report_type`, `language` | Are sync or guest preview calls repeating same symbol/report/day? | `preview_analysis()` is confirmed `persist_history=False`; do not change preview behavior. |
| Market APIs | `api/v1/endpoints/market.py`, `api/v1/endpoints/market_overview.py` | MarketCache and provider metrics with endpoint family | Which endpoint families cause panel fan-out or cold misses? | Static inspection only. Do not start servers or call providers. |

## 6. Duplicate-cost detection queries/reports

Read-only reports should aggregate existing `llm_usage`/execution logs plus new counters. Pseudo-SQL is acceptable in a later task, but do not add runtime queries in this design task.

- Same `symbol_hash` + `report_type` + `language` + `freshness_bucket` generated more than once per day.
- LLM calls per analysis request, grouped by endpoint family, owner scope, and report type.
- Fallback attempts per successful report or scanner interpretation.
- Integrity retry rate by model family, report type, language, and missing-field bucket.
- Provider fallback depth by `provider_category`, market, and endpoint family.
- Provider cache hit/miss/inflight-join rate by provider category and market.
- MarketCache hit/stale/miss/refresh/fallback rate by panel key and endpoint family.
- Scanner AI interpretations per scanner run, top-N, candidate hash, and prompt version.
- Guest preview repeats per day/session using a safe session hash.
- Token and duration buckets by call type to separate duplicate frequency from cost severity.

## 7. Minimal implementation phases

Phase 1: instrumentation-only backend counters

- Add a metrics interface/wrapper only if an existing one is present; otherwise use existing logging/admin event mechanisms with bounded, non-secret metadata.
- Instrument counters only at the seams listed above.
- Preserve all runtime behavior.
- Do not add caching, provider calls, UI, tests that call live providers, dependencies, or routing changes.

Phase 1A LLM-seams implementation note (2026-05-06):

- Added `src/services/llm_instrumentation.py` as a backend-only, process-local, best-effort counter helper. It emits no external network calls and swallows its own sink/logging failures.
- Implemented LLM seam events: `llm_call_started`, `llm_call_completed`, `llm_call_failed`, `llm_fallback_attempt`, `llm_integrity_retry`, and `llm_usage_persisted`.
- Instrumented only `src/analyzer.py::GeminiAnalyzer._call_litellm()`, `GeminiAnalyzer.analyze()` integrity retry/post-usage hooks, `GeminiAnalyzer.generate_text_with_meta()` post-usage hook, `src/agent/llm_adapter.py::LLMToolAdapter.call_completion()`, and `src/services/image_stock_extractor.py::_call_litellm_vision()`.
- Labels are allowlisted and bucketed (`call_type`, `provider`, `model_family`, `route`, `attempt_index`, `fallback_depth`, `retry_reason`, `outcome`, `duration_bucket`, `token_bucket`, `report_type`, `language`). Raw prompts, messages, images, provider payloads, API keys, URLs, exception text, user ids, and session ids are not accepted as labels.
- This phase does not change LLM routing, prompts, model order, fallback/retry behavior, report integrity semantics, caching, provider behavior, scanner/backtest/portfolio/notification/DuckDB runtime, or API response shapes.

Phase 1B provider fallback/cache implementation note (2026-05-06):

- Added provider events to the existing process-local best-effort helper and instrumented only `src/services/analysis_provider_planner.py::AnalysisProviderExecutor.execute_category()` and `_get_or_call()`.
- Implemented `provider_call_started`, `provider_call_completed`, `provider_call_failed`, `provider_fallback_attempt`, `provider_insufficient_payload`, `provider_timeout`, `provider_quota_risk_observed`, `provider_cache_hit`, `provider_cache_miss`, `provider_inflight_join`, and `provider_duplicate_candidate_observed`.
- Labels stay allowlisted and bounded (`provider`, `provider_category`, `market`, `endpoint_family`, `attempt_index`, `fallback_depth`, `outcome`, `duration_bucket`, `error_bucket`, `retry_reason_bucket`, `cache_key_hash`). Cache keys are hashed; raw symbols, URLs, params, provider payloads, exception text, stack traces, credentials, user/session ids, prompts, messages, news, and images are not emitted.
- This phase does not change provider ordering, fallback behavior, timeout values, retry behavior, circuit behavior, cache TTL/key semantics, `_cache`/`_inflight` behavior, provider validation probes, MarketCache behavior, scanner AI, frontend, or external provider call count.

Phase 1C MarketCache implementation note (2026-05-06):

- Added backend-only MarketCache counters at existing hit/stale/miss/refresh/fallback seams in `src/services/market_cache.py` using the same process-local best-effort helper.
- Implemented `market_cache_hit`, `market_cache_stale_served`, `market_cache_miss`, `market_cache_refresh_started`, `market_cache_refresh_completed`, `market_cache_refresh_failed`, and `market_cache_cold_start_fallback_served`.
- Labels stay bounded and privacy-safe (`panel_key` only when safe, `endpoint_family`, `provider_category`, `refresh_mode`, `outcome`, `freshness_bucket`, `duration_bucket`, `error_bucket`, `cache_key_hash`); raw cache keys, payloads, snapshots, URLs, and exception text are not emitted.
- This phase does not change TTL, stale-while-revalidate behavior, refresh scheduling, cold-start timeout, fallback factory behavior, persistent snapshot behavior, freshness metadata, response payload semantics, or provider behavior.

Phase 2: read-only duplicate-cost summary

- Add a backend-only/admin-only summary using existing LLM usage, execution logs, provider diagnostics, MarketCache metadata, and the new counters.
- The summary must not call providers or LLMs.
- Keep raw prompts, raw images, raw news, full users, and secrets out of the response.

Phase 3: measured cache/design prototypes only after data exists

- Scanner AI interpretation cache design or prototype.
- Guest preview short-TTL reuse design.
- LLM report output cache design.
- Provider fallback budget reporting.

## 8. Implementation guardrails for the next Codex prompt

- No behavior changes.
- Counters must be best-effort and non-blocking.
- Metric failures must never fail the user request.
- Avoid cardinality explosions; use bounded labels and safe hashes.
- Never include raw prompt, conversation, user, image, news, provider response, URL query, stack trace, token, credential, or secret payload.
- Keep scanner ranking, score, thresholds, candidate selection, and actionability untouched.
- Keep MarketCache TTL, stale-while-revalidate, background refresh, cold-start fallback, and fallback factories untouched.
- Keep provider ordering, provider fallback, circuit behavior, retries, and timeouts untouched.
- Keep LLM routing, prompt logic, report integrity policy, and parser behavior untouched.
- Do not call real LLM APIs or external providers during implementation verification.

## 9. Recommended next Codex tasks

1. Instrumentation-only backend counters for LLM/provider seams.
2. Read-only duplicate-cost admin summary backend.
3. Market Overview cache hit/stale/miss reporting.
4. Scanner AI interpretation cache design or prototype, only after metrics confirm repeated candidate hashes.
5. Guest preview reuse design with safe session hash, short TTL, freshness disclosure, and no behavior change until approved.
