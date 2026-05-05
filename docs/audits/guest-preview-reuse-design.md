# Guest Preview Reuse Design

Date: 2026-05-06
Mode: docs-only design. No runtime behavior changed.

## 1. Purpose

This note designs a privacy-safe, short-TTL reuse strategy for guest preview analysis so repeated preview requests do not always pay the full provider + LLM cost again.

Goals:
- reduce repeated guest preview LLM/provider cost
- preserve privacy and guest isolation
- preserve freshness disclosure
- avoid changing analysis semantics before metrics exist

## 2. Confirmed current behavior

Confirmed from static inspection:

- `api/v1/endpoints/analysis.py::preview_analysis()` resolves or mints a guest session cookie via `wolfystock_guest_session`, builds a `query_id` shaped like `guest:<session>:<timestamp>`, and starts an execution log session with `preview_scope=guest`.
- `api/v1/endpoints/analysis.py::preview_analysis()` calls `src.services.analysis_service.AnalysisService.analyze_stock()` with `persist_history=False` and forwards `force_refresh` from the request.
- `src/services/analysis_service.py::AnalysisService.analyze_stock()` constructs `src.core.pipeline.StockAnalysisPipeline` and passes through `force_refresh`, `owner_id`, and `persist_history`.
- `src/core/pipeline.py::StockAnalysisPipeline.process_single_stock()` performs the actual analysis work and only calls `self.db.save_analysis_history(...)` when `self.persist_history` is true.
- `src/analyzer.py::GeminiAnalyzer.analyze()` is the LLM-backed analysis seam that can incur repeated provider/LLM cost.
- `src/storage.py::persist_llm_usage()` records token usage after calls; it is accounting, not reuse prevention.
- `src/services/task_queue.py::AnalysisTaskQueue` dedupes only in-flight async work by owner + stock code; it does not provide a completed-report reuse cache.
- `api/deps.py::resolve_current_user()` and `src/auth.py` separate signed auth sessions from guest preview cookies; guest preview is not the same as authenticated user ownership.

Confirmed implications:

- guest preview currently avoids persistence of analysis history, so repeated previews can re-run the full provider + LLM path.
- there is no confirmed stable reuse gate in the preview path today.
- any reuse design must be treated as new behavior and not assumed to exist.

## 3. Reuse eligibility

Eligible only when all of the following match:

- guest preview only
- same guest/session scope
- same symbol
- same report type
- same language
- same source freshness bucket or snapshot hash
- same prompt version
- same model family or model route version
- short TTL only

Must not be reused:

- authenticated user reports unless separately designed
- personalized chat content
- uploaded images
- credential-bearing content
- stale trading decisions without clear freshness disclosure
- content generated under a different prompt/model/source version
- `force_refresh` requests

## 4. Proposed cache/reuse key

A safe conceptual key shape:

- `owner_scope = guest`
- `guest_session_hash`
- `symbol_hash`
- `report_type`
- `language`
- `prompt_version`
- `model_family` or `model_route_version`
- `source_snapshot_hash` or `freshness_bucket`
- `code_version` or `build_version` if available
- `generated_date` or a short session bucket

Unsafe key material:

- raw session id
- raw user id
- raw prompt
- raw news payload
- raw provider response
- token or API key
- full request body if it may include sensitive data

## 5. TTL and invalidation

Recommended policy:

- very short TTL, measured in minutes or a same-session window
- invalidate on `force_refresh`
- invalidate on source freshness change
- invalidate on prompt/model version change
- invalidate on code version change if output schema or parser semantics change
- never silently serve stale output without freshness disclosure

This section is design only. No cache behavior is implemented here.

## 6. Freshness and UI/API disclosure

Future response metadata should conceptually expose:

- `reusedFromPreviewCache`
- `generatedAt`
- `sourceAsOf`
- `freshnessBucket`
- `cacheAgeSeconds`
- `cacheScope = guest-session`
- `cacheKeyHash`
- warning when source is stale

This is future API design only. No response schema changes are made here.

## 7. Privacy and retention guardrails

- do not store raw prompt, news, or provider payloads in cache keys or log labels
- do not store raw guest session ids in user-visible logs
- do not share guest reuse across sessions by default
- do not share reuse across users by default
- keep retention short and documented
- expire or delete entries automatically
- use safe hashes and bounded labels in metrics and logs

## 8. Measurement-first rollout

Tie this reuse idea to `docs/audits/llm-provider-duplicate-cost-metrics-design.md`:

Phase 1:
- instrument duplicate candidate counters only

Phase 2:
- add a read-only duplicate-cost report

Phase 3:
- enable guest preview reuse behind an explicit config or feature flag

Phase 4:
- observe hit rate, stale serve rate, and bypass or force-refresh rate

## 9. Risks and non-goals

Risks:

- stale analysis
- accidental cross-session leakage
- hidden model or prompt drift
- high-cardinality keys
- user trust loss if reuse is undisclosed

Non-goals:

- no general LLM report cache
- no authenticated report cache
- no scanner cache
- no provider cache change
- no MarketCache semantic change
- no prompt or model routing change

## 10. Recommended follow-up Codex tasks

1. Instrumentation-only duplicate guest preview candidate counter.
2. Read-only guest preview repeat-cost report.
3. Design review after metrics are available.
4. Optional short-TTL prototype behind a disabled-by-default flag.
5. UI/API freshness disclosure design.
