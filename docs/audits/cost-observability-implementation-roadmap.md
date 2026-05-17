# Cost Observability Implementation Roadmap

Status: Partial
Owner domain: Cost observability and quota governance
Related docs: `docs/audits/cost-observability-design-index.md`, `docs/audits/cost-system-final-qa-matrix.md`

Date: 2026-05-06
Mode: docs-only planning. No runtime behavior changed.

## 1. Purpose

This roadmap converts the completed LLM/provider cost audits, duplicate-cost designs, reuse designs, and post-batch QA notes into a safe staged implementation plan.

The order is intentional:

1. measure first with best-effort, non-blocking counters;
2. expose read-only aggregate reporting second;
3. prototype cache/reuse only after measured evidence shows repeated cost.

Future implementation tasks should stay small, serializable where shared seams are involved, and parallelizable only when they touch disjoint files or doc surfaces.

## 2. Inputs reviewed

| Document | Status | Purpose | Key implementation implication |
| --- | --- | --- | --- |
| `docs/audits/llm-external-api-cost-audit.md` | completed | Static inventory of LLM and external-provider repeat-cost risks. | Highest risks are repeated same-symbol/report LLM generation, fallback/integrity retry multipliers, Market Overview fan-out on cold/stale paths, in-process provider caches, and bounded scanner AI calls. |
| `docs/audits/llm-provider-duplicate-cost-metrics-design.md` | completed | Instrumentation design for LLM/provider/cache/scanner duplicate-cost counters. | Phase 1 work must be instrumentation-only with bounded labels, safe hashes, and no provider, routing, prompt, cache, or AI decision changes. |
| `docs/audits/guest-preview-reuse-design.md` | completed | Privacy-safe short-TTL guest preview reuse design. | Guest preview reuse must wait for duplicate counters and read-only reports, stay guest-session scoped, respect `force_refresh`, and disclose freshness. |
| `docs/audits/duplicate-cost-admin-summary-api-design.md` | completed | Future admin-only read-only duplicate-cost summary API design. | Backend summary should aggregate existing accounting/logs plus future counters, use synthetic tests only, and never call providers or LLMs. |
| `docs/audits/scanner-ai-interpretation-cache-design.md` | completed | Optional scanner AI interpretation cache design. | Scanner AI cache work must remain additive and must not alter ranking, selection, score, thresholds, actionability, CSV headers, provider behavior, or prompt/routing logic. |
| `docs/audits/archive/frontend/wolfystock-post-batch-integration-qa.md` | completed | QA closure for recent dashboard, request-staging, scanner dedupe, localization, and cost-audit docs. | Confirms the current direction: read-only admin surfaces, instrumentation first, and no behavior changes to provider runtime, MarketCache, scanner, AI, or UI during cost planning. |
| `docs/audits/ws2-provider-quota-circuit-breaker-policy-design.md` | completed | Provider quota/circuit policy design with retained provider fallback measurement constraints. | Provider fallback measurement should cover fallback depth, quota-risk buckets, cache hits/misses, and inflight joins without changing ordering, fallback, timeout, retry, circuit behavior, or probe posture. |
| `docs/audits/market-overview-cache-reporting-design.md` | pending parallel task | Expected MarketCache hit/stale/miss reporting design. | Treat as not yet available in this checkout. MarketCache instrumentation below must preserve TTL, SWR, background refresh, cold-start timeout, fallback factory, and snapshot semantics. |
| `docs/audits/llm-report-output-cache-design.md` | pending parallel task | Expected LLM report output cache design. | Treat as not yet available in this checkout. Do not implement report output caching until metrics and read-only reporting exist and the cache key/freshness model is approved. |

## 3. Current state summary

Highest repeat-cost risks:

- `api/v1/endpoints/analysis.py::preview_analysis()` and sync analysis can repeat `src/services/analysis_service.py::AnalysisService.analyze_stock()` and `src/analyzer.py::GeminiAnalyzer.analyze()` for the same symbol/report/language/freshness.
- `src/analyzer.py::_call_litellm()` can multiply cost through model/provider fallback, and `src/analyzer.py::GeminiAnalyzer.analyze()` can multiply report cost through integrity retry.
- `src/services/market_overview_service.py` fans out across many Market Overview panels. `src/services/market_cache.py::MarketCache` protects these paths, but cold starts, stale refreshes, multiple workers, and process restarts still need measurement.
- `src/services/analysis_provider_planner.py::AnalysisProviderExecutor` and `data_provider/us_fundamentals_provider.py` have in-process cache/coalescing, but durable duplicate-cost visibility is not confirmed.
- `src/services/scanner_ai_service.py::ScannerAiInterpretationService.interpret_shortlist()` is bounded/top-N/additive, but repeated candidate payloads can repeat LLM interpretation calls when enabled.

Existing protections:

- `MarketCache` supports fresh hits, stale-while-revalidate, background refresh, cold-start fallback, and fallback factories.
- `AnalysisProviderExecutor` has per-category provider cache, `_inflight` coalescing, timeouts, and circuit state.
- `data_provider/us_fundamentals_provider.py` has helper-level request cache.
- `src/services/task_queue.py::TaskQueue` dedupes in-flight async analysis by owner and stock code.
- Scanner AI remains post-selection and optional; deterministic ranking/score/selection stay primary.
- `src/storage.py::LLMUsage` and `persist_llm_usage()` provide accounting, not reuse prevention.

Completed QA status:

- `docs/audits/archive/frontend/wolfystock-post-batch-integration-qa.md` reports PASS for the recent read-only dashboard, request staging, scanner initial request dedupe, Backtest Chinese labels, design check, lint, build, full `./scripts/ci_gate.sh`, and browser QA performed in that prior QA run.
- That QA doc also states the working tree was clean before creating the QA report. This roadmap run also started from a clean worktree.

Current no-go areas:

- No runtime behavior changes.
- No counters, APIs, caches, UI, tests, dependencies, provider calls, LLM calls, or browser verification in this docs-only task.
- No changes to LLM routing, prompt logic, provider ordering/fallback, MarketCache TTL/SWR/cold-start behavior, scanner ranking/selection/thresholds, backtest calculations, portfolio accounting, notifications, or DuckDB production runtime.

## 4. Implementation phases

### Phase 1A: LLM seams instrumentation

Scope:

- Add best-effort counters around outbound LLM attempts, fallback transitions, integrity retry, token-accounting persistence, and duplicate candidates.
- Observe behavior only. Do not dedupe, cache, reorder, retry differently, change prompts, change model routing, or change parser/integrity policy.

Target files/functions:

- `src/analyzer.py::GeminiAnalyzer.analyze()`
- `src/analyzer.py::_call_litellm()`
- `src/analyzer.py::GeminiAnalyzer.generate_text_with_meta()`
- `src/agent/llm_adapter.py::LiteLLMAdapter.call_completion()`
- `src/services/image_stock_extractor.py::extract_stock_codes_from_image()`
- `api/v1/endpoints/analysis.py::preview_analysis()` and sync analysis metadata only
- `src/storage.py::persist_llm_usage()` call sites, if needed for accounting correlation

Event names:

- `llm_call_started`
- `llm_call_completed`
- `llm_call_failed`
- `llm_fallback_attempt`
- `llm_integrity_retry`
- `llm_duplicate_candidate_observed`
- `llm_usage_persisted`

Must not change behavior:

- LLM routing, prompt text, retry policy, fallback order, report integrity policy, parser behavior, analysis persistence, guest preview behavior, or image extraction behavior.

Recommended tests:

- Synthetic/unit tests around emitted metadata only.
- No real LLM calls.
- Assert raw prompts, messages, images, news, provider payloads, user/session ids, and secret values are not emitted.

### Phase 1B: Provider fallback/cache instrumentation

Scope:

- Add provider attempt, fallback-depth, cache-hit/miss, inflight-join, insufficient-payload, timeout, and quota-risk counters at existing provider seams.
- Measure provider cost pressure without changing provider behavior.

Target files/functions:

- `src/services/analysis_provider_planner.py::AnalysisProviderExecutor.execute_category()`
- `src/services/analysis_provider_planner.py::AnalysisProviderExecutor._get_or_call()`
- `src/services/analysis_provider_planner.py::AnalysisProviderExecutor._classify_exception()`
- `data_provider/us_fundamentals_provider.py` helper/cache wrapper seams
- `data_provider/base.py::DataFetcherManager.get_daily_data()` and provider fallback branches, if scoped narrowly
- `src/providers/validation.py` only for separately labeled manual probe results, not report generation

Provider event names:

- `provider_call_started`
- `provider_call_completed`
- `provider_call_failed`
- `provider_fallback_attempt`
- `provider_insufficient_payload`
- `provider_timeout`
- `provider_quota_risk_observed`
- `provider_cache_hit`
- `provider_cache_miss`
- `provider_inflight_join`
- `provider_duplicate_candidate_observed`

Must not change provider ordering/fallback:

- Preserve provider order, fallback conditions, timeout values, retries, circuit state behavior, cache TTLs, `_inflight` behavior, and validation probe semantics.

Recommended tests:

- Synthetic provider/executor tests only.
- No live provider calls, no credential reads, and no secret values in output.

### Phase 1C: MarketCache instrumentation

Scope:

- Add hit/stale/miss/refresh/fallback counters for Market Overview cache behavior.
- Keep high-frequency success telemetry out of default user-visible logs unless summarized intentionally.

Target files/functions:

- `src/services/market_cache.py::MarketCache.get_or_refresh()`
- `src/services/market_cache.py::MarketCache._start_background_refresh()`
- `src/services/market_cache.py::MarketCache._refresh()`
- `src/services/market_overview_service.py::_cached_payload()`
- `src/services/market_overview_service.py::_panel()`
- `src/services/market_overview_service.py::_market_snapshot()`
- `src/services/market_overview_service.py::_classified_snapshot()`

Cache event names:

- `market_cache_hit`
- `market_cache_stale_served`
- `market_cache_miss`
- `market_cache_refresh_started`
- `market_cache_refresh_completed`
- `market_cache_refresh_failed`
- `market_cache_cold_start_fallback_served`

Must not change MarketCache semantics:

- Preserve TTLs, stale-while-revalidate, background refresh, cold-start timeout, fallback factories, persistent snapshots, snapshot freshness metadata, and current request behavior.

Recommended tests:

- Synthetic service/cache tests only.
- No browser validation required for instrumentation-only backend work unless a future UI/API change is explicitly added.
- No external provider calls.

### Phase 1D: Scanner AI duplicate candidate counters

Scope:

- Add counters around scanner AI interpretation identity and skip/generate/fail outcomes.
- Observe duplicate candidate hashes and interpretation attempts only.

Target files/functions:

- `src/services/scanner_ai_service.py::ScannerAiInterpretationService.interpret_shortlist()`
- `src/services/scanner_ai_service.py::ScannerAiInterpretationService._interpret_candidate()`
- `src/services/scanner_ai_service.py::ScannerAiInterpretationService._call_analyzer()`
- `src/services/market_scanner_service.py::MarketScannerService._prepare_shortlist()` only if read-only metadata is needed after deterministic shortlist finalization

Event names:

- `scanner_ai_duplicate_candidate_observed`
- `scanner_ai_interpretation_started`
- `scanner_ai_interpretation_completed`
- `scanner_ai_interpretation_skipped`

Must not change ranking/selection/score/CSV:

- Preserve candidate inclusion, shortlist membership, rank, score, thresholds, preview behavior, actionability, diagnostics used for selection/rejection, profile/universe/theme logic, and CSV headers.

Recommended tests:

- Synthetic scanner AI tests proving counters do not alter output candidates.
- No real LLM calls.

### Phase 2: Read-only duplicate-cost admin summary backend

Route:

- `GET /api/v1/admin/cost/duplicate-summary`

Data sources:

- Existing `src/storage.py::LLMUsage`
- Existing `src/storage.py::ExecutionLogSession`
- Existing `src/storage.py::ExecutionLogEvent`
- Existing read-only admin-log/service patterns in `src/services/execution_log_service.py`
- Existing read-only provider/cache summary patterns in `src/services/market_provider_operations_service.py`
- Future counters from Phases 1A through 1D
- Current in-process `src/services/market_cache.py::MarketCache` metadata only as process-local status, not historical truth

Privacy guardrails:

- Admin-only.
- Aggregate-first.
- No raw prompts, raw messages, raw images, raw news, raw provider payloads, raw URLs/query strings, raw stack traces, full users/sessions, credentials, tokens, or secret config values.
- Safe hashes and bounded labels only.
- Include `dataSources`, `limitations`, `readOnly`, and `noExternalCalls` metadata.

Synthetic tests only:

- Use fixture rows and synthetic counters.
- No provider calls, LLM calls, browser calls, cache mutation, log writes, config mutation, background refreshes, or live probes.

### Phase 3: Optional admin UI after backend API stabilizes

Scope:

- Read-only admin UI only after the Phase 2 backend contract stabilizes.
- Aggregate-first summary cards and tables.
- Collapsed raw/developer details by default.
- Clear copy that metrics are operational estimates, not billing truth.

Must not:

- Trigger provider calls, LLM calls, connectivity probes, cache refreshes, config writes, report generation, scanner runs, or background jobs.

### Phase 4: Measured cache/reuse prototypes

Scope:

- Guest preview reuse, based on `docs/audits/guest-preview-reuse-design.md`.
- Scanner AI interpretation cache, based on `docs/audits/scanner-ai-interpretation-cache-design.md`.
- LLM report output cache only after `docs/audits/llm-report-output-cache-design.md` exists and is approved.

Rules:

- Disabled-by-default first.
- Opt-in rollout only after metrics show meaningful repeat candidates.
- Explicit freshness disclosure from the first prototype.
- Respect force-refresh or explicit bypass.
- Cache keys must include prompt/model/source freshness/version identity where relevant.
- No provider policy, scanner decision, MarketCache semantic, portfolio, backtest, notification, or DuckDB runtime changes.

## 5. Parallelization plan

| Task | Can run in parallel with | Must be serialized after | Likely files touched | Runtime risk | Notes |
| --- | --- | --- | --- | --- | --- |
| Docs-only follow-up designs | Other docs-only tasks touching different files | None, if target docs are clean | `docs/audits/*.md` | Low | Check target file dirty status first. Do not edit dirty parallel docs. |
| Phase 1A LLM seams instrumentation | Docs-only work; provider instrumentation only if metrics helper/files are disjoint | Any concurrent work touching the same metrics helper or LLM seams | `src/analyzer.py`, `src/agent/llm_adapter.py`, `src/services/image_stock_extractor.py`, `api/v1/endpoints/analysis.py`, possible shared metrics helper | Medium | Serialize with guest preview/report duplicate counters if they share the same metrics helper. |
| Guest preview duplicate counter | Docs-only work | Phase 1A helper shape, if reused | `api/v1/endpoints/analysis.py`, `src/services/analysis_service.py`, shared metrics helper | Medium | Do not change `persist_history=False`, guest cookies, `force_refresh`, or analysis behavior. |
| Phase 1B provider fallback instrumentation | Docs-only work; LLM instrumentation if helper/files are disjoint | Shared metrics helper changes; provider-report API contract if it depends on counter names | `src/services/analysis_provider_planner.py`, `data_provider/us_fundamentals_provider.py`, `data_provider/base.py`, possible shared metrics helper | Medium | Do not run simultaneously with MarketCache instrumentation if they share helper files or Market Overview wrappers. |
| Phase 1C MarketCache instrumentation | Docs-only work | Shared metrics helper changes; provider instrumentation touching same Market Overview wrappers | `src/services/market_cache.py`, `src/services/market_overview_service.py`, possible shared metrics helper | Medium | Preserve TTL/SWR/cold-start semantics and keep high-frequency success events out of default admin-log noise. |
| Phase 1D scanner AI duplicate counters | Docs-only work; provider instrumentation if files are disjoint | Phase 1A helper shape, if LLM helper/counter API is reused | `src/services/scanner_ai_service.py`, possible shared metrics helper, focused scanner tests | Medium | Must not alter rank, score, selection, thresholds, actionability, diagnostics, or CSV headers. |
| Phase 2 duplicate-cost admin summary backend | Docs-only work | Phases 1A through 1D counter names and label policy | `api/v1/endpoints/*`, `api/v1/router.py`, `src/services/*`, `tests/*` synthetic only | Medium | Backend-only, read-only, no provider/LLM calls, no cache mutation. |
| Phase 3 admin UI | Docs-only work | Stable Phase 2 backend contract | `apps/dsa-web/src/api/*`, `apps/dsa-web/src/pages/*`, route/i18n/test files | Medium | Frontend admin UI must wait until backend contract stabilizes. |
| Phase 4 guest preview reuse prototype | Docs-only work | Metrics and read-only reports proving repeat candidates | `api/v1/endpoints/analysis.py`, `src/services/analysis_service.py`, possible cache/storage files, tests | High | Disabled-by-default; explicit freshness disclosure; preserve guest isolation. |
| Phase 4 scanner AI interpretation cache prototype | Docs-only work | Scanner duplicate counters and read-only report evidence | `src/services/scanner_ai_service.py`, possible cache/storage files, scanner tests | High | Cache additive text only; no scanner decision changes. |
| Phase 4 LLM report output cache prototype | Docs-only work | `docs/audits/llm-report-output-cache-design.md`, metrics, read-only reports, approved key/freshness model | LLM/report/analysis service files, storage/cache files, tests | High | Do not start until cache key, freshness disclosure, and bypass semantics are approved. |

## 6. Guardrails checklist for every future implementation prompt

- Confirm `pwd` and branch before editing.
- Inspect `git status --short` before editing target files.
- Stop if the target file is already dirty.
- Stage only task-related files explicitly; never use `git add .`.
- No broad formatting.
- No behavior changes unless explicitly approved.
- Metrics must be best-effort and non-blocking.
- Metric failures must never fail a user request.
- No raw prompts, messages, images, news, provider payloads, URLs/query strings, stack traces, user/session ids, secrets, tokens, or credential values in labels, logs, responses, or docs.
- Env var names may be mentioned, but never values.
- Bounded labels and safe hashes only.
- Synthetic tests only for admin summary and instrumentation.
- No live LLM calls.
- No live external-provider calls.
- No provider probes during report generation.
- No LLM routing, prompt, retry, parser, AI decision, provider ordering, fallback, timeout, circuit, MarketCache TTL/SWR/cold-start, scanner ranking, scanner threshold, backtest, portfolio, notification, or DuckDB production runtime changes unless that exact behavior change is separately approved.

## 7. Recommended next Codex batch

1. Complete or merge current Phase 1A LLM instrumentation if not already done.
   - Execution guidance: serialize with guest preview/report duplicate counters if they share the same metrics helper or LLM seam files.
   - Parallel safety: safe with docs-only tasks touching different docs.

2. Provider fallback instrumentation Phase 1B.
   - Execution guidance: can run after the shared counter/helper shape is stable.
   - Parallel safety: can run with LLM work only if file/helper ownership is disjoint; avoid overlap with MarketCache instrumentation if Market Overview wrappers or shared helpers are touched.

3. MarketCache hit/stale/miss instrumentation Phase 1C.
   - Execution guidance: serialize with provider instrumentation when both touch Market Overview cache/fetch wrappers or shared metrics helpers.
   - Parallel safety: safe with docs-only tasks and scanner-only work if helpers are already stable.

4. Scanner AI duplicate candidate counter Phase 1D.
   - Execution guidance: can run after any shared LLM metrics helper shape is stable.
   - Parallel safety: safe with provider work if disjoint; serialize with LLM helper changes if reused.

5. Backend-only duplicate-cost summary API after counters exist.
   - Execution guidance: serialize after Phases 1A through 1D establish counter names, label policy, and limitations.
   - Parallel safety: can run with docs-only work, but frontend admin UI must wait for this contract to stabilize.

## 8. Non-goals

No cache implementation yet.

No provider policy changes.

No provider ordering, fallback, timeout, retry, or circuit changes.

No MarketCache TTL, stale-while-revalidate, background refresh, cold-start timeout, fallback factory, or snapshot semantic changes.

No AI decision changes.

No LLM routing, prompt logic, model ordering, parser, or integrity-policy changes.

No scanner ranking, selection, scoring, thresholds, profile, universe, candidate actionability, diagnostics, or CSV changes.

No backtest calculation changes.

No portfolio accounting changes.

No notification routing changes.

No DuckDB production runtime changes.

No frontend admin dashboard before backend API contract stabilization.
