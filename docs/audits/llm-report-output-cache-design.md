# LLM Report Output Cache Design

Date: 2026-05-06
Mode: docs-only design. No runtime behavior changed.

## 1. Purpose

Full-stock LLM report generation is the highest repeated LLM cost risk identified in `docs/audits/llm-external-api-cost-audit.md`. The confirmed hot path can regenerate a complete report for the same effective symbol, report type, language, user or session scope, and freshness window across repeated sync, preview, or completed async workflows.

This design is measurement-first. Cache or reuse behavior should only be considered after duplicate candidate instrumentation confirms that repeated report identities are common enough to justify added correctness, privacy, freshness, and operator-complexity risk.

The goal is to preserve freshness, user trust, analysis semantics, LLM routing semantics, provider fallback semantics, report integrity retry behavior, and report parsing/schema semantics. This note is separate from guest preview reuse in `docs/audits/guest-preview-reuse-design.md` and scanner AI interpretation caching in `docs/audits/scanner-ai-interpretation-cache-design.md`.

## 2. Confirmed current behavior

Confirmed from static inspection:

- Analysis API entry paths live in `api/v1/endpoints/analysis.py`.
- Guest preview path: `api/v1/endpoints/analysis.py::preview_analysis()` resolves or creates the `wolfystock_guest_session` cookie, starts an execution log session with `preview_scope=guest`, and calls `src.services.analysis_service.AnalysisService.analyze_stock(...)` with `persist_history=False`.
- Sync analysis path: `api/v1/endpoints/analysis.py::_handle_sync_analysis()` creates a query id, resolves the authenticated owner through `get_current_user_id(...)`, starts an execution log session, and calls `AnalysisService.analyze_stock(...)`.
- Async analysis path: `api/v1/endpoints/analysis.py::_handle_async_analysis_batch()` submits work through `src/services/task_queue.py::AnalysisTaskQueue.submit_tasks_batch(...)`.
- `src/services/analysis_service.py::AnalysisService.analyze_stock()` constructs `src.core.pipeline.StockAnalysisPipeline` with `owner_id` and `persist_history`, then calls `StockAnalysisPipeline.process_single_stock(...)` with `force_refresh`, report type, and progress callback.
- `src/core/pipeline.py::StockAnalysisPipeline.process_single_stock()` calls `fetch_and_save_stock_data(..., force_refresh=force_refresh)` before `StockAnalysisPipeline.analyze_stock(...)`.
- `src/core/pipeline.py::StockAnalysisPipeline.analyze_stock()` is the main non-agent report path. It builds market, provider, news, sentiment, and structured context, then calls `src/analyzer.py::GeminiAnalyzer.analyze(...)`.
- `src/analyzer.py::GeminiAnalyzer.analyze()` formats the report prompt, calls `GeminiAnalyzer._call_litellm(...)`, parses the response, applies optional report integrity retry through `_build_integrity_retry_prompt(...)`, and persists usage with `src/storage.py::persist_llm_usage(..., call_type="analysis", stock_code=code)`.
- `src/analyzer.py::GeminiAnalyzer._call_litellm()` tries the configured primary model plus fallback models. It records an attempt trace but does not provide report output reuse.
- `src/core/pipeline.py::StockAnalysisPipeline.analyze_stock()` persists analysis history through `self.db.save_analysis_history(...)` only when `self.persist_history` is true.
- `src/storage.py::DatabaseManager.save_analysis_history(...)` writes `analysis_history` rows with owner, query id, code, report type, summary fields, raw result, news content, context snapshot, and created timestamp.
- `src/services/analysis_service.py::AnalysisService.analyze_stock()` calls `src/repositories/analysis_repo.py::AnalysisRepository.attach_persisted_report(...)` when `persist_history=True`, attaching the canonical report payload back to the latest matching history record.
- `src/repositories/analysis_repo.py::AnalysisRepository` provides history read and write helpers such as `get_latest_record(...)`, `save(...)`, and `attach_persisted_report(...)`. Static inspection did not confirm a completed-report reuse gate in the analysis execution path.
- `src/services/task_queue.py::_dedupe_stock_code_key(...)` keys in-flight async dedupe by normalized owner plus canonical stock code. `AnalysisTaskQueue.submit_tasks_batch(...)` rejects duplicate currently-running async work but releases the key after completion.
- `src/storage.py::LLMUsage` and `src/storage.py::persist_llm_usage(...)` provide LLM usage accounting. They are not output reuse or duplicate prevention.

Confirmed implications:

- There is no confirmed LLM report output cache today.
- There is no confirmed duplicate report candidate counter today.
- Stored history supports display and record retrieval, but static inspection did not confirm that repeated analysis requests serve an existing completed report instead of re-running analysis.
- Guest preview intentionally uses `persist_history=False`, so it is not covered by persisted history reuse.
- Async task dedupe is in-flight only; it does not dedupe completed reports.
- Usage accounting records tokens and calls, but does not prevent calls.

## 3. Cache eligibility tiers

Tier 0: no reuse, metrics only

- Observe duplicate report candidates with safe counters.
- Do not change runtime output, provider calls, prompts, routing, fallback, integrity retry, parsing, persistence, APIs, UI, or notifications.

Tier 1: same owner/session short-TTL reuse

- Eligible only for same owner or same guest session, same effective symbol, same report type, same language, same prompt/model/source/code/schema identity, same freshness bucket, and `force_refresh=false`.
- Requires explicit reuse and freshness metadata in the future response contract.

Tier 2: same authenticated user, same day/session, explicit reuse disclosure

- Consider only after Tier 1 metrics show safe hit rates.
- Must remain user-scoped and disclose generated time, source freshness, cache age, and bypass availability.

Tier 3: cross-user/shared reuse

- Out of scope unless separately approved with privacy, product, legal, and trading-risk review.
- This design does not approve shared report reuse.

Eligible only when all relevant identity components match:

- same effective symbol after canonicalization
- same report type
- same language
- same prompt version
- same model family or model route version
- same source snapshot hash or source freshness bucket
- same code version, schema version, and parser semantics
- same owner/session scope where relevant
- same trading session bucket
- no `force_refresh`

Must not reuse:

- personalized chat or tool content
- uploaded-image-derived requests
- credential-bearing content
- raw user/session content
- different user or session unless separately designed and approved
- stale or materially changed source data
- different prompt, model, route, schema, parser, or code version
- `force_refresh` requests
- trading decisions without freshness disclosure and bypass controls

## 4. Proposed cache key

Safe conceptual key:

- `cache_scope = llm_report_output`
- `owner_scope`
- `owner_hash` or `session_hash` when owner/session scoping is required
- `symbol_hash`
- `report_type`
- `language`
- `prompt_version`
- `model_family` or `model_route_version`
- `source_snapshot_hash` or `freshness_bucket`
- `provider_snapshot_hashes` where available
- `code_version` or `schema_version`
- `trading_session_bucket`
- `input_identity_hash`

Unsafe key material:

- raw prompt
- raw news or provider payload
- raw report content
- raw user id, owner id, session id, or guest cookie
- API keys, tokens, credentials, Authorization headers, webhook URLs, or secret config values
- raw request body when it may contain sensitive content
- raw stack trace, provider error body, or unbounded exception text

## 5. Stored value and metadata

Stored value concept:

- structured report output
- `generatedAt`
- `sourceAsOf` or source freshness metadata
- model family
- prompt version
- schema version
- cache key hash
- `reusedFromCache` flag for future responses
- `cacheAgeSeconds`
- warnings and limitations

Do not store:

- raw prompt unless separately encrypted, retention-scoped, and justified
- secrets or secret-bearing config
- raw full provider payloads unless they are already stored under a reviewed safe snapshot policy
- personal chat content or tool arguments
- uploaded image bytes or OCR text
- raw user/session identifiers

## 6. TTL / invalidation

Recommended starting policy:

- Use a short TTL initially.
- Invalidate on `force_refresh`.
- Invalidate on prompt version, model route version, schema version, parser version, or code version changes.
- Invalidate on source snapshot or source freshness bucket changes.
- Invalidate on report type or language changes.
- Invalidate on material provider failure or fallback state changes when they affect report content.
- Never silently serve stale output.
- Prefer cache miss over ambiguous freshness.

## 7. Freshness disclosure and trust

Future API/UI response metadata should expose:

- `reusedFromReportCache`
- `generatedAt`
- `sourceAsOf`
- `cacheAgeSeconds`
- `freshnessBucket`
- `cacheScope`
- `cacheKeyHash`
- `forceRefreshAvailable`
- stale or limitation warning when relevant

The API and UI must disclose reuse and freshness before cache behavior is enabled. Cached trading analysis should never appear as newly generated live analysis unless the response clearly says when the report was generated and what source freshness it used.

## 8. Measurement-first rollout

Phase 1: instrumentation-only duplicate report candidate counters

- Observe duplicate report identities around `api/v1/endpoints/analysis.py::preview_analysis()`, `_handle_sync_analysis()`, `src/services/analysis_service.py::AnalysisService.analyze_stock()`, and `src/analyzer.py::GeminiAnalyzer.analyze()`.
- Use bounded labels and safe hashes only.
- Preserve all current runtime behavior.

Phase 2: read-only duplicate-cost admin summary

- Build on `docs/audits/duplicate-cost-admin-summary-api-design.md`.
- Aggregate duplicate candidates from future counters plus existing `src/storage.py::LLMUsage` and execution-log context.
- Do not call LLMs, providers, or mutate caches.

Phase 3: disabled-by-default same-session/same-owner short-TTL prototype

- Prototype only after metrics show meaningful duplicate rates.
- Keep it disabled by default.
- Include response metadata from the first prototype.
- Use synthetic tests only in a future implementation task.

Phase 4: measured opt-in

- Enable only with clear freshness disclosure, bypass controls, monitoring, and rollback.
- Track hit rate, miss rate, bypass rate, stale-warning rate, and user-visible freshness metadata.

## 9. Risks and non-goals

Risks:

- stale trading analysis
- hidden prompt, model, source, code, parser, or schema drift
- privacy leakage across users, sessions, or guest identities
- user trust loss from undisclosed reuse
- high-cardinality keys or metrics
- incorrect reuse across markets or trading sessions
- cache hits masking provider degradation or fallback-state changes
- replaying reports generated from partial provider failures as if they were fresh

Non-goals:

- no general cross-user report cache
- no chat cache
- no scanner ranking cache
- no scanner score or selection cache
- no provider cache changes
- no `MarketCache` TTL, stale-while-revalidate, background refresh, cold-start, or fallback change
- no prompt changes
- no model routing or model ordering changes
- no fallback behavior changes
- no integrity retry behavior changes
- no report parsing/schema semantic changes
- no API, UI, test, dependency, frontend, notification, DuckDB, backtest, or portfolio behavior changes in this task

## 10. Recommended follow-up Codex tasks

1. Add duplicate report candidate counters only.
2. Add a read-only report duplicate-cost summary.
3. Run a same-session report cache design review after metrics exist.
4. Prototype a disabled-by-default report cache with synthetic tests only.
5. Design UI/API freshness disclosure for reused report output.

