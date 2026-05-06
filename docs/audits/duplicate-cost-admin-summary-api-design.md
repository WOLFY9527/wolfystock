# Duplicate-Cost Admin Summary API Design

Date: 2026-05-06
Mode: docs-only design. No runtime behavior changed.

## 1. Purpose

This note designs a future admin-only, read-only API for summarizing duplicate LLM and external-provider cost patterns. It follows the sequence recommended by `docs/audits/llm-external-api-cost-audit.md` and `docs/audits/llm-provider-duplicate-cost-metrics-design.md`: instrument first, expose a read-only admin summary second, and consider cache/reuse prototypes only after measured duplicate candidates justify them.

The API must not call providers, call LLMs, mutate `MarketCache`, write execution logs, change provider ordering, change fallback behavior, or change analysis/scanner decisions. It should only aggregate existing accounting/log data and future instrumentation counters into a privacy-safe operator summary.

## 2. Preconditions

The summary should be implemented after these backend-only prerequisites:

- instrumentation-only counters at LLM/provider/cache seams, using bounded labels and safe hashes;
- a reviewed label model that avoids raw prompts, raw payloads, raw user identifiers, secret config, and unbounded provider URLs;
- a privacy review of all emitted counter metadata and admin response fields.

It should not be implemented against speculative metrics. If built before the new counters exist, scope must be explicitly limited to confirmed existing data such as `src/storage.py::LLMUsage`, `src/storage.py::ExecutionLogSession`, `src/storage.py::ExecutionLogEvent`, and admin-log summaries from `src/services/execution_log_service.py::ExecutionLogService`. In that mode, duplicate-cost values must be labeled as partial estimates.

## 3. Candidate route and permissions

Candidate route:

```text
GET /api/v1/admin/cost/duplicate-summary
```

Permission and behavior rules:

- admin-only via the existing `api.deps.require_admin_user` pattern used by `api/v1/endpoints/admin_logs.py` and `api/v1/endpoints/market_provider_operations.py`;
- read-only, with no writes, no cache mutation, no config mutation, and no execution-log append;
- no LLM calls, provider calls, connectivity probes, browser calls, or background refresh triggers;
- accepts only bounded time-window, bucket, area, limit, and redacted debug parameters;
- returns safe aggregate data first, with any drilldown limited, paginated, and redacted;
- rejects raw prompt search, raw user lookup, raw API key/provider URL search, arbitrary SQL-like filters, and unbounded windows.

## 4. Data sources

| Source | Existing or future | Usefulness | Privacy risk | Limitations |
| --- | --- | --- | --- | --- |
| `src/storage.py::LLMUsage` and `persist_llm_usage()` | Existing | Token/call accounting by `call_type`, `model`, optional `stock_code`, and `called_at`. Useful for LLM calls per day and broad call-type trends. | Medium: model names and stock codes may be sensitive in some contexts; user/session scope is not present in this table. | Accounting only. It does not prove duplicate intent, fallback depth, integrity retries, or billing exactness. |
| `src/storage.py::ExecutionLogSession` and `ExecutionLogEvent` | Existing | Session/event context for analysis, market overview fetches, scanner runs, admin actions, statuses, durations, and request ids. | Medium/high: event details can include user, symbol, provider, route, errors, and metadata. | Historical events were not designed as cost counters; high-volume success cache events may be intentionally absent. |
| `src/services/execution_log_service.py::ExecutionLogService.list_business_events()` and `list_sessions()` | Existing | Provides admin-log filtering, health summaries, actor/category/provider rollups, and sanitized metadata patterns. | Medium: current admin logs expose operator-level context and must remain admin-only. | Query/search APIs are event-oriented, not duplicate-cost oriented; raw event matching can overstate causality. |
| `src/services/market_provider_operations_service.py::MarketProviderOperationsService.get_operations()` | Existing | Demonstrates the read-only admin-service pattern over `MarketCache`, market snapshots, and admin-log rollups without provider calls. | Low/medium: exposes provider health and panel status, but should avoid raw response bodies. | Market-provider specific; does not cover LLM, scanner AI, or provider executor counters. |
| `src/services/market_cache.py::MarketCache` entries | Existing in-process state | Current fresh/stale/refreshing/error cache state by key; useful for point-in-time cache status. | Low if only key/status/age are returned. | In-process only, not shared across workers, and reading it only reflects the current process. |
| `src/services/market_overview_service.py::_cached_payload()` and persistent market snapshots | Existing | Snapshot fallback and cached payload paths can explain Market Overview stale/fallback/cold-start behavior. | Medium if raw snapshots are returned; low if only metadata is aggregated. | Existing snapshot metadata is not a complete hit/miss counter. |
| `src/services/analysis_provider_planner.py::AnalysisProviderExecutor` attempt results | Existing runtime behavior, future counters required for durable summary | `_cache`, `_inflight`, fallback attempts, provider attempts, cache hits, and invalid-payload/timeout reasons are the key provider-cost seams. | Medium: raw symbol/provider/category combinations can become sensitive or high-cardinality. | Current cache/inflight state is memory-only; durable hit/miss/inflight-join counters are future required. |
| `src/services/task_queue.py::_dedupe_stock_code_key()` and `AnalysisTaskQueue.submit_tasks_batch()` | Existing runtime behavior, future counters required | Shows async in-flight duplicate rejection by owner/symbol. Future counters can summarize avoided duplicate analysis submissions. | Medium: owner/symbol identity must be hashed or role-scoped. | Only covers in-flight async tasks, not completed-analysis reuse or guest preview repeats. |
| `src/analyzer.py::GeminiAnalyzer._call_litellm()` attempt trace | Existing per-call behavior, future counters required | Identifies LLM attempts, fallback transitions, model success/failure, and usage. | High: prompt text and raw model/config data must never be emitted. | Attempt traces are currently attached to runtime results, not a durable aggregate counter. |
| `src/analyzer.py::GeminiAnalyzer.analyze()` integrity retry path | Existing behavior, future counters required | Explains report-level retry multiplier when required fields are missing. | High if missing fields or previous response text are emitted raw. | Needs explicit instrumentation to count retry reason buckets safely. |
| `src/agent/llm_adapter.py::LiteLLMAdapter.call_completion()` | Existing behavior, future counters required | Agent/chat fallback attempts and failures. | High: chat messages and tool arguments can contain personal or sensitive data. | Should avoid duplicate-response conclusions unless exact replay semantics are separately designed. |
| `src/services/scanner_ai_service.py::ScannerAiInterpretationService.interpret_shortlist()` | Existing behavior, future counters required | Optional bounded top-N scanner interpretation attempts, generated/failed/skipped counts, and fallback use. | Medium/high: candidate reasons and generated interpretation text should not be returned raw. | Current diagnostics are per run; repeated candidate-hash reporting needs future counters. |
| Future LLM/provider/MarketCache/scanner counter events | Future required | Primary source for duplicate candidates, cache hit/miss/inflight-join rate, fallback depth, integrity retries, and bucketed duration/token cost. | Controlled by label policy; should be low if only bounded labels and safe hashes are emitted. | Not available today; API must report `dataSources` and `limitations` clearly. |

## 5. Proposed response shape

The response should be JSON-like and aggregate-first. It must not include raw prompts, raw messages, raw provider responses, raw news payloads, uploaded image data, API keys, tokens, secret config values, or full user/session identifiers.

```json
{
  "generatedAt": "2026-05-06T12:00:00+08:00",
  "window": {
    "from": "2026-05-05T12:00:00+08:00",
    "to": "2026-05-06T12:00:00+08:00",
    "bucket": "hour"
  },
  "summary": {
    "llmCalls": 0,
    "estimatedDuplicateCandidates": 0,
    "providerCalls": 0,
    "providerCacheHitRate": null,
    "marketCacheHitRate": null,
    "fallbackAttempts": 0,
    "integrityRetries": 0
  },
  "llm": {
    "byCallType": [],
    "duplicateCandidates": [],
    "fallbacks": [],
    "integrityRetries": []
  },
  "providers": {
    "byCategory": [],
    "fallbackDepth": [],
    "cacheEfficiency": []
  },
  "marketCache": {
    "byPanelKey": [],
    "staleServed": [],
    "coldFallbacks": []
  },
  "scannerAi": {
    "interpretations": [],
    "duplicateCandidates": [],
    "skips": []
  },
  "limitations": [
    "instrumentation_counters_required_for_exact_duplicate_rate"
  ],
  "metadata": {
    "dataSources": [
      {
        "name": "llm_usage",
        "status": "existing",
        "exactness": "accounting_only"
      },
      {
        "name": "future_duplicate_cost_counters",
        "status": "future_required",
        "exactness": "required_for_duplicate_candidates"
      }
    ],
    "redaction": [
      "raw_prompt_omitted",
      "raw_provider_payload_omitted",
      "safe_hashes_only"
    ],
    "noExternalCalls": true,
    "readOnly": true
  }
}
```

Suggested item shapes:

- `llm.byCallType[]`: `{ "callType": "analysis", "calls": 12, "tokenBucket": "10k-50k", "duplicateCandidateCount": 3 }`
- `llm.duplicateCandidates[]`: `{ "candidateHash": "sha256:...", "scope": "symbol_report_language_freshness", "count": 2, "firstSeenAt": "...", "lastSeenAt": "...", "confidence": "estimated" }`
- `providers.cacheEfficiency[]`: `{ "providerCategory": "fundamentals", "market": "us", "hits": 10, "misses": 4, "inflightJoins": 2, "hitRate": 0.714 }`
- `marketCache.byPanelKey[]`: `{ "panelKey": "crypto", "freshHits": 30, "staleServed": 2, "coldFallbacks": 1, "currentState": "fresh" }`
- `scannerAi.interpretations[]`: `{ "market": "cn", "profile": "us_preopen_v1", "attempted": 3, "generated": 2, "skipped": 5, "fallbackUsed": true }`

## 6. Query parameters

Safe parameters:

- `from` / `to`: ISO datetimes, with a strict maximum range such as 7 or 30 days depending on storage cost;
- `since`: bounded relative shortcut such as `15m`, `1h`, `24h`, or `7d`;
- `bucket`: `hour` or `day`;
- `area`: `all`, `llm`, `provider`, `market-cache`, or `scanner-ai`;
- `limit`: strict maximum, for example default `50`, max `200`;
- `includeDebug`: default `false`; admin-only; still redacted and aggregate-limited.

Rejected parameters:

- raw prompt search;
- raw conversation/message search;
- raw user lookup or full guest-session lookup;
- raw API key, token, provider URL, Authorization header, webhook URL, or secret config lookup;
- arbitrary SQL-like filters;
- unbounded time windows;
- filters that require provider calls, LLM calls, cache refresh, or runtime mutation.

## 7. Privacy and redaction model

The endpoint must use an aggregate-first redaction model:

- no raw prompts;
- no raw conversation text or tool arguments;
- no raw news payloads or search result bodies;
- no image bytes, image URLs, OCR text, or uploaded-image metadata beyond safe content hashes where explicitly approved;
- no provider response bodies;
- no API keys, tokens, Authorization headers, cookie values, webhook URLs, or secret config/env values;
- no full user ids, account ids, session ids, guest session ids, or owner ids;
- no raw stack traces or provider error bodies;
- safe hashes only for identities that need repeat detection;
- bucket exact tokens, durations, and counts where exact values could become high-cardinality or identifying;
- aggregate first; drilldown must stay limited, paginated, and redacted;
- do not expose secret configuration or env values. Env var names may be mentioned in documentation, but never values.

Hashing guidance:

- use a stable server-side salt for operational duplicate grouping if long-lived grouping is required;
- prefer short retention or rotating salts for guest/session-oriented reports;
- expose hash purpose labels such as `symbol_report_language_freshness` rather than raw key components;
- never make hashes reversible by concatenating raw values in returned metadata.

## 8. Duplicate-cost report examples

Examples the future API can support after instrumentation:

- same symbol/report/language/freshness duplicate candidates per day, keyed by a safe `candidateHash`;
- LLM attempts per successful analysis, using `src/analyzer.py::GeminiAnalyzer._call_litellm()` counters plus `LLMUsage` accounting;
- fallback depth by model family/provider category, without raw configured model lists or secret channel details;
- report integrity retry rate from `GeminiAnalyzer.analyze()` and `_build_integrity_retry_prompt()` retry buckets;
- provider cache hit/miss/inflight-join rate from `AnalysisProviderExecutor._get_or_call()`;
- provider fallback depth from `AnalysisProviderExecutor.execute_category()` attempts;
- `MarketCache` fresh/stale/miss/cold fallback by panel key from `MarketCache.get_or_refresh()` counters and current cache metadata;
- Market Overview degraded fetch rollups from `MarketOverviewService._market_snapshot()`, `_classified_snapshot()`, `_panel()`, and `ExecutionLogService.record_market_overview_fetch()`;
- scanner AI interpretation count per run/candidate hash from `ScannerAiInterpretationService.interpret_shortlist()`;
- scanner AI skip reasons for disabled/unavailable/non-CN/beyond-top-N paths;
- guest preview repeat candidates by guest session hash and symbol/report/language/freshness, using `api/v1/endpoints/analysis.py::preview_analysis()` request metadata only after privacy review.

Pseudo-SQL example, marked illustrative only:

```sql
-- Pseudo-SQL only. Future implementation must use repository/service APIs
-- and must not expose raw user/session/prompt fields.
SELECT call_type, date(called_at) AS day, count(*) AS calls
FROM llm_usage
WHERE called_at BETWEEN :from AND :to
GROUP BY call_type, date(called_at);
```

## 9. Failure modes and limitations

- Missing counters before instrumentation: existing `llm_usage` and execution logs can show call/accounting trends, but not exact duplicate candidates.
- In-process caches are not shared across workers: `MarketCache`, `AnalysisProviderExecutor._cache`, and `_inflight` represent current-process behavior unless future counters are durable.
- Historical data is incomplete: old logs may lack actor metadata, cache states, fallback depth, or retry reason buckets.
- Estimates are not billing truth: token counts, call counts, and provider attempts do not necessarily equal invoice amounts.
- High-cardinality risk: raw symbol/user/prompt/provider-url dimensions can make metrics expensive and privacy-sensitive.
- Admin interpretation risk: duplicate candidates can be misread without freshness, source snapshot, report type, language, route, and trace context.
- No causal claims without trace ids: same hashes in a window suggest duplicate candidates, but do not prove avoidable waste unless trace/request context confirms same effective input.
- High-volume success events may be intentionally absent from admin logs to avoid noise; the summary should not infer hit/miss rates from missing log rows.

## 10. Rollout plan

Phase 1: instrumentation-only counters

- Add non-blocking, bounded counters for LLM attempts, fallback attempts, integrity retries, provider call/cache/inflight events, MarketCache hit/stale/miss/fallback events, and scanner AI interpretation attempts.
- Preserve runtime behavior and privacy constraints.

Phase 2: backend-only read-only summary

- Add `GET /api/v1/admin/cost/duplicate-summary` using counters plus existing `llm_usage`, execution logs, MarketCache metadata, and market snapshot metadata.
- Include synthetic-data tests only in the future implementation task.
- Return clear `dataSources`, `limitations`, `readOnly`, and `noExternalCalls` metadata.

Phase 2 implementation note (2026-05-06):

- Added the read-only admin endpoint `GET /api/v1/admin/cost/duplicate-summary`.
- The implementation aggregates the existing process-local instrumentation counter snapshot and existing `llm_usage` accounting summary when available. It does not call LLMs, providers, MarketCache refresh paths, scanner/backtest/portfolio tasks, report generation, config writes, execution-log writes, notifications, or DuckDB runtime.
- Responses include `summary`, `llm`, `providers`, `marketCache`, `scannerAi`, `limitations`, and `metadata`, with `readOnly=true`, `noExternalCalls=true`, `countersSource=process_local`, and `exactness=observational_not_billing`.
- Process-local counters are not timestamped, so `window` and `bucket` are contract fields only for the counter snapshot; the endpoint returns this limitation instead of pretending to provide historical buckets.
- Response rollups use bounded labels and safe hash labels only. Raw prompts, messages, provider/news payloads, URLs/query strings, API keys/tokens, full user/session ids, stack traces, raw response bodies, raw cache keys, raw candidate payloads, and raw reports are not returned.

Phase 3: optional admin frontend dashboard

- Add UI only after the backend contract stabilizes.
- Keep dashboard copy explicit that values are measurement/estimation, not billing truth.

Phase 4: measured cache/reuse prototypes

- Prototype cache or reuse only for measured hot spots with high duplicate-candidate counts.
- Keep scanner ranking, provider ordering, fallback behavior, prompt logic, MarketCache TTL/SWR/cold-start behavior, backtest calculations, portfolio accounting, notification routing, and DuckDB runtime unchanged unless separately approved.

## 11. Future implementation guardrails

Future Codex implementation must:

- be read-only;
- make no external provider calls;
- make no LLM calls;
- not mutate cache, snapshots, execution logs, config, reports, scanner runs, backtests, portfolios, notifications, or DuckDB runtime;
- not alter provider/LLM behavior, routing, prompts, fallback order, retry policy, scanner scoring, scanner selection, scanner thresholds, or MarketCache TTL/SWR/cold-start behavior;
- not expose raw prompts, raw conversations, raw news, raw image data, raw provider payloads, raw URLs, raw stack traces, raw users/sessions, API keys, tokens, or secret config/env values;
- be admin-only through the existing `require_admin_user` pattern;
- include future tests with synthetic data only;
- report limitations clearly in every response.

## 12. Recommended follow-up Codex tasks

1. Instrumentation-only backend counters for LLM/provider seams, including `GeminiAnalyzer._call_litellm()`, `GeminiAnalyzer.analyze()`, `LiteLLMAdapter.call_completion()`, `AnalysisProviderExecutor._get_or_call()`, `MarketCache.get_or_refresh()`, and `ScannerAiInterpretationService.interpret_shortlist()`.
2. Backend-only duplicate-cost summary API with synthetic tests and no provider/LLM/cache mutation.
3. Optional admin frontend dashboard after the backend response contract is stable.
4. Guest preview repeat-cost report design using hashed guest/session and freshness keys.
5. MarketCache hit/stale/miss summary endpoint or section, reusing the read-only pattern in `MarketProviderOperationsService.get_operations()`.
