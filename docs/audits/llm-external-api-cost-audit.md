# LLM / External API Cost Audit

Date: 2026-05-06
Mode: docs-only static audit. No runtime code, UI, tests, config, provider ordering, cache behavior, DuckDB runtime, or LLM/provider traffic was changed.

## 1. Executive summary

Highest repeat-cost risks:

- Synchronous stock analysis can regenerate a full LLM report for the same symbol/report type/user/date when `force_refresh` or repeated sync/preview calls are used. Confirmed path: `api/v1/endpoints/analysis.py::_handle_sync_analysis()` and `preview_analysis()` -> `src/services/analysis_service.py::AnalysisService.analyze_stock()` -> `src/core/pipeline.py::StockAnalysisPipeline.process_single_stock()` -> `src/analyzer.py::GeminiAnalyzer.analyze()`.
- `GeminiAnalyzer.analyze()` may make more than one LLM call per report when model fallback is used and when report integrity retry is enabled. Confirmed in `src/analyzer.py::_call_litellm()` and the integrity retry loop inside `GeminiAnalyzer.analyze()`.
- Market Overview route entry fans out across many backend panels. Backend `MarketCache` protects these panels, but repeated cold starts or TTL mismatch across panels can still produce multiple external calls. Confirmed frontend fan-out in `apps/dsa-web/src/pages/MarketOverviewPage.tsx` and backend cache use in `src/services/market_overview_service.py`.
- US supplemental analysis has strong in-process cache/coalescing, but it is memory-only. Process restart or multiple backend workers can repeat FMP/Finnhub/Yahoo/Alpha Vantage calls for the same symbol/category/date. Confirmed in `src/services/analysis_provider_planner.py` and `data_provider/us_fundamentals_provider.py`.
- Scanner AI is bounded and additive, but can still call the LLM once per top candidate when enabled. Confirmed in `src/services/scanner_ai_service.py::ScannerAiInterpretationService.interpret_shortlist()`.

Already protected areas:

- `src/services/market_cache.py::MarketCache` provides per-key TTL, stale-while-revalidate, background refresh, cold-start fallback, and in-process refresh coalescing for market overview snapshots.
- `src/services/analysis_provider_planner.py::AnalysisProviderExecutor` provides per provider/category/symbol cache, `_inflight` coalescing, timeouts, and circuit state for analysis provider categories.
- `data_provider/us_fundamentals_provider.py` has a module-level request cache for FMP, Finnhub, and yfinance helpers.
- `src/services/task_queue.py::TaskQueue` prevents duplicate in-flight async analysis tasks per owner/symbol.
- `apps/dsa-web/src/pages/MarketOverviewPage.tsx` stages panel requests and has route-entry request dedupe; this is frontend context only.
- `src/storage.py::LLMUsage` and `persist_llm_usage()` track LLM token usage, but this is accounting, not call prevention.

Recommended next steps:

1. Add instrumentation-only counters around confirmed LLM/provider seams.
2. Add a read-only duplicate-risk report using existing `llm_usage`, analysis history, provider diagnostics, and MarketCache metadata.
3. Only after measuring, add opt-in read-through caches with conservative keys and freshness disclosure.

## 2. LLM call inventory

| Call site | Trigger path | Input identity candidates | Existing cache/dedupe | Repeat-risk assessment |
| --- | --- | --- | --- | --- |
| `src/analyzer.py::GeminiAnalyzer.analyze()` -> `_call_litellm()` | Main report analysis via `StockAnalysisPipeline.process_single_stock()` | symbol, report language, report type, user/owner, trading date/session, prompt version, model route, source snapshot ids, news freshness | Token usage persisted by `persist_llm_usage()`. No confirmed output cache for final LLM report in this call path. Async queue dedupes only currently running tasks. | High. Same symbol/report can be regenerated across sync calls, preview calls, after task completion, or after process restart. Integrity retry and fallback can multiply calls. |
| `src/analyzer.py::GeminiAnalyzer.generate_text_with_meta()` | Market review and scanner interpretation callers | call type, prompt hash, model, report date/session, market/profile | Persists token usage. No confirmed text output cache. | Medium. Safe to cache only when prompt inputs and freshness are explicit. |
| `src/agent/llm_adapter.py::LiteLLMAdapter.call_completion()` | Agent chat endpoints and bot `/chat`/`/ask` | user, conversation/session id, message history hash, tool set, model route | No confirmed response cache; chat should usually remain uncached unless exact replay semantics are explicit. | Medium/high for repeated identical tool-backed prompts, but personalized/session content makes generic caching unsafe. |
| `src/services/image_stock_extractor.py::extract_stock_codes_from_image()` -> `_call_litellm_vision()` | `api/v1/endpoints/stocks.py::extract_from_image()` image upload | image content hash, mime type, vision model, prompt version | Validates size/type and retries up to three times; no confirmed image-result cache. | Medium. Exact same image uploads can repeat vision token/image cost. Cache only by image hash and never store sensitive image bytes unless explicitly designed. |
| `src/services/scanner_ai_service.py::ScannerAiInterpretationService.interpret_shortlist()` | Scanner shortlist post-processing when enabled | market/profile, run id, symbol, rank, deterministic score, candidate reason payload, model, prompt version | Bounded top-N and disabled/unavailable fallbacks. No confirmed interpretation cache. | Medium. One LLM call per top candidate when enabled; repeated scanner runs over same shortlist may repeat. Must remain additive and never affect scanner rank/selection. |
| `src/services/system_config_service.py::SystemConfigService.test_llm_channel()` | Admin/system setting connectivity test | channel name, base URL, model, timeout | Minimal prompt and timeout; no cache. | Low/intentional. This is a manual connectivity probe and should not be silently cached unless UI clearly labels cached probe results. |

Unclear/needs measurement:

- Stored analysis history is used for history/report display, but this audit did not confirm a stable "serve existing report instead of re-analyze" gate for every sync/preview/API path. Treat duplicate same-symbol same-day analysis as a confirmed risk, not a confirmed bug.

## 3. External provider call inventory

| Provider/source | File/function/endpoint | Existing cache/dedupe/TTL/fallback | Repeat-risk assessment |
| --- | --- | --- | --- |
| Market Overview panels | `api/v1/endpoints/market.py`, `api/v1/endpoints/market_overview.py`, `src/services/market_overview_service.py` | `MarketCache` TTLs by category; `_market_data_cache`; persistent snapshot fallback; admin log records via `ExecutionLogService.record_market_overview_fetch()` | Medium. Protected in one process, but cold start, process restart, multiple workers, or many panels with short TTLs can still fan out. |
| Binance REST | `MarketOverviewService._fetch_crypto_market_snapshot()`, `_fetch_binance_funding_items()`, `_fetch_binance_kline_history()` | Covered by `MarketCache` key such as crypto; funding calls loop per symbol inside fetch. | Medium during cold refresh; one crypto refresh calls ticker, klines per symbol, and funding per symbol. |
| CNN Fear & Greed / Alternative.me | `_fetch_market_sentiment_snapshot()`, `_fetch_cnn_fear_greed_snapshot()`, `_fetch_alternative_fear_greed_snapshot()` | Covered by `MarketCache` sentiment TTL and fallback from CNN to Alternative.me. | Low/medium. Fallback chain can double external calls on CNN failure. |
| Sina CN index quotes | `_fetch_sina_cn_index_quotes()` | Covered by `MarketCache` for CN indices/breadth-related cards depending on caller. | Medium. Public endpoint, but repeated cold route entries could hit it. |
| yfinance Market Overview | `_latest_quote()`, `_atr_item()` | Covered only when called through cached Market Overview fetchers. | Medium. Repeated per ticker inside a panel if panel cache misses. |
| FMP/Finnhub/yfinance/Alpha Vantage US supplemental analysis | `src/core/pipeline.py::_fetch_us_supplemental_categories()`, `src/services/analysis_provider_planner.py`, `data_provider/us_fundamentals_provider.py`, Alpha Vantage helpers imported by pipeline | Provider executor cache/coalescing by provider/category/symbol/params; module-level request cache in `us_fundamentals_provider.py`; lazy fallback by category. | Medium. Good in-process protection, but memory-only and not shared across workers/process restarts. |
| AkShare/Tushare/pytdx/baostock/yfinance core data fetchers | `data_provider/base.py::DataFetcherManager` and fetcher classes | Data manager has provider fallback, route tracing, optional realtime prefetch, provider-specific fallbacks. This audit confirmed fetcher usage but did not fully verify a global shared cache for all realtime/history fetches. | Medium/high for repeated same-symbol realtime/history calls outside cached panels and US supplemental executor. |
| Scanner universe/snapshot/history | `src/services/market_scanner_service.py` | Local universe CSV cache, DB/local fallback, run-review cache, benchmark-review cache, provider diagnostics. | Medium. Universe cache helps stock lists; snapshot/history candidate evaluation can still be expensive per run. |
| Search/news/social sentiment | `src/search_service.py`, `src/services/social_sentiment_service.py` | Retries/provider fallback are present; this audit did not confirm durable cache for all news/social requests. | Medium. News search repeats by symbol/date/query unless a caller reuses stored news context. |
| Portfolio FX | `src/services/fx_rate_service.py`, portfolio service callers | FX service makes HTTP requests; portfolio tests reference yfinance fallback. This audit did not deeply inspect portfolio FX cache policy. | Low/medium. Repeated portfolio page loads or syncs can repeat FX fetches if not cached upstream. |
| Admin provider connectivity tests | `src/services/system_config_service.py` provider test helpers and `src/providers/validation.py` | Manual probes with timeouts; no cache expected. | Low/intentional. Do not hide live probe failures behind cached status unless explicitly labeled. |

## 4. Existing protections

- `MarketCache`: confirmed in `src/services/market_cache.py::MarketCache.get_or_refresh()`. It returns fresh cache hits, serves stale data while background refresh runs, supports cold-start fallback, and marks payloads with `isRefreshing`, `isStale`, `lastError`, and `refreshError`.
- Market Overview service cache and snapshots: confirmed in `src/services/market_overview_service.py::_cached_payload()`, which stores successful snapshots in `_market_data_cache`, saves persistent snapshots, and falls back to memory snapshot, persistent snapshot, or fallback factory.
- Provider category cache/coalescing: confirmed in `src/services/analysis_provider_planner.py::AnalysisProviderExecutor._get_or_call()`, with `_cache`, `_inflight`, per-category TTLs, and timeouts.
- US provider helper cache: confirmed in `data_provider/us_fundamentals_provider.py` via `_request_cache`, `_cache_get()`, and `_cache_set()`.
- Async analysis in-flight dedupe: confirmed in `src/services/task_queue.py::_dedupe_stock_code_key()` and `TaskQueue.submit_tasks_batch()`, keyed by owner plus canonical stock code.
- Scanner local/review caches: confirmed in `src/services/market_scanner_service.py` with `local_universe_cache_path`, `_run_review_cache`, and `_benchmark_review_cache`.
- Frontend request staging/dedupe: confirmed in `apps/dsa-web/src/pages/MarketOverviewPage.tsx` via staged panel request groups, `Promise.allSettled`, `PANEL_REQUEST_TIMEOUT_MS`, and `loadPanelWithRouteEntryDedupe()`.
- Admin/provider observability: confirmed Market Overview fetch logging via `ExecutionLogService.record_market_overview_fetch()` and Market Provider Operations service summary over cache/log data. Prior behavior intentionally default-hides high-frequency cache/prewarm success noise while keeping failure/stale/timeout events visible.
- LLM usage accounting: confirmed in `src/storage.py::LLMUsage` and `persist_llm_usage()`. This records calls/tokens but does not dedupe or cache.

## 5. Cost-risk gaps

- Duplicate same-symbol same-day analysis: no confirmed stable output cache around `AnalysisService.analyze_stock()` or `GeminiAnalyzer.analyze()` for the same symbol/report type/user/date after an analysis completes.
- Guest preview repeats: `preview_analysis()` uses `persist_history=False`, so repeated guest previews can re-run provider and LLM work without reusing stored report history.
- Integrity retry multiplier: one report can require initial LLM call plus fallback attempts plus integrity retry calls. This is intentional behavior, but counters should expose it.
- LLM output cache key is missing: a safe key would need symbol, user/session scope where relevant, report type, language, model, prompt version, source snapshot identities/freshness, news query/freshness, and code version.
- Frontend route fan-out still exists: request staging reduces route-entry bursts, but Market Overview still asks for many panels. Backend cache is the real cost control.
- Provider caches are mostly in-process: `MarketCache`, `AnalysisProviderExecutor`, and `_request_cache` are not confirmed durable/shared across workers.
- Fallback chains can be expensive: CNN -> Alternative.me, FMP -> Finnhub -> yfinance -> Alpha Vantage, and CN provider chains are safe for availability but can multiply quota use under partial failure.
- Cache invalidation policy is uneven: market panels have TTLs; LLM decisions and reports need freshness disclosure and invalidation rules before caching.

## 6. Safe implementation plan

Phase 1: instrumentation / counters only

- Add per-call counters around `GeminiAnalyzer._call_litellm()`, `LiteLLMAdapter.call_completion()`, `extract_stock_codes_from_image()`, `AnalysisProviderExecutor._get_or_call()`, and `MarketCache.get_or_refresh()`.
- Emit aggregate counts by call type, model/provider, symbol, cache hit/miss, fallback attempt, retry attempt, and duration.
- Do not change provider order, AI decisions, scanner ranking, backtest calculations, portfolio accounting, or UI behavior.

Phase 2: read-through cache for LLM outputs by stable input hash

- Start with non-personalized, low-risk outputs only, such as scanner AI interpretation for a persisted scanner run/candidate payload.
- Include model, prompt version, code version, language, input hash, source freshness, and generated timestamp in the cache record.
- Keep cache bypass explicit through existing `force_refresh` style controls.

Phase 3: provider call coalescing / TTL alignment

- Extend measured hot spots first. Prefer request coalescing and TTL alignment over broad durable caching.
- Consider sharing provider snapshot references from analysis provider executor into report context rather than refetching in downstream renderers.
- Preserve existing fallback behavior and source/freshness metadata.

Phase 4: admin observability and manual invalidation

- Add admin read-only cache diagnostics: keys, age, freshness, source, stale/fallback counts, and last error.
- Add manual invalidation only after ownership and safety rules are clear.

## 7. Guardrails

- Never cache personalized, session-specific, uploaded-image, credential-bearing, or security-sensitive content without explicit keying and retention policy.
- Never cache stale trading decisions without freshness disclosure.
- Separate provider raw snapshots from interpreted AI decisions.
- Include model version, prompt version, source freshness, report language, and source snapshot identity in LLM cache keys.
- Keep scanner deterministic ranking primary; AI interpretation cache must not alter selection, rank, score, thresholds, or actionability.
- Keep MarketCache TTL/SWR/cold-start semantics unchanged unless a future task explicitly targets that behavior.
- Connectivity probes should remain visibly live or clearly labeled as cached.
- Mention env var names only, never values. Relevant names include `LITELLM_MODEL`, `LLM_CHANNELS`, `LITELLM_CONFIG`, `VISION_MODEL`, `OPENAI_VISION_MODEL`, `FMP_API_KEY`, `FMP_API_KEYS`, `FINNHUB_API_KEY`, `FINNHUB_API_KEYS`, `ALPHA_VANTAGE_API_KEY`, `TUSHARE_TOKEN`, `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`, and `TWELVE_DATA_API_KEY`.

## 8. Recommended Codex follow-up tasks

1. Docs/read-only: add a duplicate-cost metrics design note for LLM and provider counters. Scope: docs only; no runtime behavior.
2. Instrumentation-only backend task: add counters/log metadata for LLM attempts, integrity retries, provider cache hits, provider fallback attempts, and MarketCache hit/stale/miss. Explicitly no caching behavior change.
3. Read-only admin report task: expose aggregated duplicate-risk stats from existing `llm_usage`, execution logs, provider diagnostics, and MarketCache metadata. No provider calls.
4. Scanner AI cache prototype: cache only scanner interpretation by persisted run id, candidate symbol, deterministic candidate payload hash, prompt version, model, and language. No scanner ranking/selection changes.
5. Guest preview reuse design: propose a privacy-safe short TTL preview reuse key using guest session id, symbol, report type, language, and source snapshot freshness. Design first; no implementation until approved.
6. Market Overview measurement task: count panel cache hit/stale/miss and external fetch fan-out per route load. Do not modify `MarketCache` TTL/SWR/cold-start behavior.
7. Provider fallback budget task: add read-only reporting for fallback chain depth and quota-risk providers per analysis run. Do not change provider ordering or fallback semantics.
