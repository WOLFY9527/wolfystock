# T-918 Home Evidence Source Utilization Audit

Task ID: T-918  
Mode: docs-only audit artifact for a prompt that otherwise selected `READ-ONLY-AUDIT` semantics. No runtime code was changed by this task.

## Executive Verdict

Home AI already has enough metadata to say a single-stock run is incomplete, but it still lacks a durable evidence packet that preserves useful source material from provider fetch to LLM prompt to public report. The current Home path is strongest at:

- assembling quote, technical, fundamentals, earnings, news, and sentiment fragments;
- compressing degradation into `dataQualityReport`, `researchReadiness`, and `evidenceCoverageFrame`;
- exposing truthful partial coverage states to the API response.

It is weakest at:

- using the strongest available US fundamentals/earnings evidence in the highest-salience prompt sections;
- preserving bounded top-N news/catalyst evidence instead of flattening it into long text plus a weak classifier block;
- separating static provider capability from actual Home runtime wiring;
- keeping partial/timeout/fallback evidence visible all the way through final report sections.

The largest ORCL-like mismatch is structural: US/HK `fundamental_context` is explicitly unsupported, but the analyzer prompt's richest finance table still depends on `fundamental_context.earnings.financial_report/dividend`. The actual US evidence gathered from FMP/Finnhub/YFinance/Alpha Vantage is only injected later as compact structured blocks, so the LLM sees the best single-stock financial evidence in a weaker and less instructionally prominent form (`data_provider/base.py:2805-2829`, `src/core/pipeline.py:3263-3673`, `src/analyzer.py:1641-1711`).

## Scope And Method

This audit inspected Home/single-stock request flow, provider assembly, context normalization, prompt construction, response projection, and guardrail tests without changing runtime behavior or making live provider calls.

Primary files inspected:

- `api/v1/endpoints/analysis.py:223-326`
- `api/v1/endpoints/analysis.py:561-686`
- `api/v1/endpoints/analysis.py:1151-1274`
- `src/services/analysis_service.py:596-1255`
- `src/core/pipeline.py:384-1244`
- `src/core/pipeline.py:2705-3815`
- `src/analyzer.py:82-149`
- `src/analyzer.py:1529-1867`
- `data_provider/base.py:1093-1275`
- `data_provider/base.py:2805-3106`
- `src/search_service.py:2452-3012`
- `src/services/analysis_provider_planner.py:161-393`
- `src/services/provider_capability_matrix.py:231-426`
- `src/services/provider_capability_matrix.py:1593-1657`
- `src/services/provider_capability_matrix.py:1871-1948`
- `src/services/data_criticality.py:359-522`
- `src/services/data_source_router_diagnostics.py:1-106`
- `src/services/us_history_helper.py:1-215`
- `src/storage.py:9716-9774`
- `tests/services/test_analysis_research_readiness_projection.py:240-432`

## 1. Current Home Single-Stock Path Inventory

### 1.1 Request and response seams

Home single-stock analysis enters through:

- guest preview `POST /api/v1/analysis/analyze-preview`, which runs `AnalysisService.analyze_stock()` synchronously and logs success whenever a response object is built (`api/v1/endpoints/analysis.py:223-326`);
- sync analyze `POST /api/v1/analysis/analyze`, which also treats non-null analysis result payloads as successful completion and then rebuilds the persisted report shape (`api/v1/endpoints/analysis.py:561-686`, `api/v1/endpoints/analysis.py:1151-1274`).

### 1.2 Service and pipeline seams

- `AnalysisService.analyze_stock()` instantiates `StockAnalysisPipeline.process_single_stock()`, then builds the public response (`src/services/analysis_service.py:596-680`).
- `_build_report_payload()` attaches `researchReadiness`, `evidenceCoverageFrame`, `dataQualityReport`, and `decision_trace` to the report and mirrors them into multiple public response locations (`src/services/analysis_service.py:686-851`).
- `_build_home_research_readiness()` and `_build_home_evidence_coverage_frame()` are projection-only consumers of already assembled metadata; they do not improve upstream evidence capture (`src/services/analysis_service.py:853-1255`).

### 1.3 Pipeline assembly

The main Home path:

1. fetches/saves local history or realtime snapshot fallback for the symbol (`src/core/pipeline.py:220-305`);
2. loads analysis context from stored latest rows, not from a dedicated single-stock evidence packet (`src/storage.py:9716-9774`);
3. performs optional news and social sentiment enrichment under short deadlines and fail-open continuation (`src/core/pipeline.py:620-766`);
4. fetches bounded US supplemental categories for quote/fundamentals/earnings/history/technicals only (`src/core/pipeline.py:1076-1166`);
5. builds multidimensional structured blocks for technicals, fundamentals, earnings, sentiment, catalyst, realtime, and market context (`src/core/pipeline.py:923-967`, `src/core/pipeline.py:3263-3815`);
6. compresses quality and degradation into `dataQualityReport` (`src/services/data_criticality.py:359-522`);
7. constructs an LLM prompt from mixed tables, JSON snippets, and flattened news text (`src/analyzer.py:1529-1867`);
8. parses/fills the LLM output, applies quality caps, and returns success-class results if an object exists (`src/analyzer.py:82-149`, `src/analyzer.py:1280-1344`, `src/core/pipeline.py:1168-1244`).

## 2. Source Utilization Inventory And Best-Use Classification

The key distinction is between:

- sources actually wired into the current Home single-stock runtime;
- sources only represented in capability/planner metadata or adjacent helpers.

### 2.1 Sources currently used or directly adjacent to the Home runtime

| Source | Current Home runtime use | Best use for Home AI | Freshness / authority limits | Recommended current role |
| --- | --- | --- | --- | --- |
| DB-local latest OHLCV rows | Actual Home context comes from `get_analysis_context()` and uses latest stored rows plus yesterday comparison (`src/storage.py:9716-9774`). | Primary local context for today/yesterday price/volume deltas and MA status. | Depends on upstream fetch freshness; current function does not replay by exact `target_date`. | `score-grade` only after upstream fetch succeeded and freshness is qualified. |
| Alpaca | Possible US daily history / realtime route in `DataFetcherManager.get_daily_data()` and capability matrix, but only when configured (`data_provider/base.py:1093-1203`, `src/services/provider_capability_matrix.py:273-291`). | Configured US quote/OHLCV enrichment. | Entitlement/feed can be realtime or delayed. | `score-grade` candidate for quote/history, not broad evidence narrative. |
| Yahoo Finance / yfinance | Actual fallback in US daily history route and supplemental fundamentals/earnings (`data_provider/base.py:1093-1203`, `src/core/pipeline.py:1109-1118`). | Cheap delayed cross-check and fallback baseline. | Unofficial, delayed proxy, should not be treated as decision-grade live data (`src/services/provider_capability_matrix.py:231-249`, `src/services/provider_capability_matrix.py:1935-1948`). | `observation-only` or fallback. |
| FMP | Actual US supplemental provider for quote, fundamentals, earnings, historical prices, technical indicators (`src/core/pipeline.py:1105-1129`). | First-line US fundamentals/statements and bounded earnings normalization. | Daily freshness, quota should not be wasted on broad OHLCV or avoidable technicals (`src/services/provider_capability_matrix.py:312-350`). | `score-grade` candidate for fundamentals/earnings after per-field validation. |
| Finnhub | Actual supplemental quote/fundamentals fallback; news capability exists in planner and capability matrix (`src/core/pipeline.py:1105-1114`, `src/services/provider_capability_matrix.py:351-369`). | Bounded quote enrichment, company-news reference, fallback metrics. | Key required, plan dependent, per-symbol fanout can burn quota (`src/services/provider_capability_matrix.py:1593-1609`). | `usable_with_caution`, mostly fallback or bounded observation. |
| Alpha Vantage | Actual deep fallback for overview, quarterly income, and technical indicators (`src/core/pipeline.py:1123-1129`, `src/core/pipeline.py:3263-3673`). | Last-resort deep fundamentals/statements/technicals. | Scarce quota, manual-review freshness (`src/services/provider_capability_matrix.py:371-388`). | `deep-research fallback`, not standard Home score authority. |
| SearchService provider chain | Actual Home news path via `search_comprehensive_intel()` and per-dimension provider fallback/caching (`src/core/pipeline.py:620-679`, `src/search_service.py:2663-3012`). | Recent company-specific news and catalyst search. | Provider calls are optional, cache-backed, and bounded by time window/profile. | `observation-only` until normalized top-N evidence survives to the report. |
| GNews | Actual news provider candidate in planner/capability and likely runtime through `search_news`/`search_comprehensive_intel()` (`src/services/analysis_provider_planner.py:170-172`, `src/services/provider_capability_matrix.py:389-407`). | Explicit top-N recent company news enrichment. | Scarce quota; not suitable scanner-wide. | `observation-only`. |
| Tavily | Actual search provider candidate for news/sentiment/macro dimensions in SearchService (`src/search_service.py:2529-2541`, `src/search_service.py:2894-2921`). | Deep research or fallback search across news/risk/industry dimensions. | Manual-review freshness; multi-dimension search multiplies call count (`src/services/provider_capability_matrix.py:408-426`). | `observation-only`. |
| Social sentiment service | Actual optional US-only enrichment appended into `news_context` when available (`src/core/pipeline.py:705-760`). | Supplemental market narrative or retail attention context. | Optional, timeout-prone, merged into prose rather than preserved structurally. | `observation-only`. |
| `fundamental_context` pipeline | Actual call exists, but returns `market not supported` for US/HK (`data_provider/base.py:2805-2829`). | Rich table-grade structured finance context when supported. | US/HK unsupported today. | `not currently authoritative for Home US/HK`; current prompt dependence is a mismatch. |
| `dataQualityReport` / readiness projections | Actual downstream quality and coverage projections (`src/services/data_criticality.py:359-522`, `src/services/analysis_service.py:778-1255`). | Guardrails and public disclosure. | Compressed metadata, not raw evidence. | `projection-only`, not a replacement for evidence packets. |

### 2.2 Sources/helpers present in the repo but not directly wired into current Home single-stock runtime

| Source / helper | Evidence | Best use | Current Home status | Recommended role if introduced later |
| --- | --- | --- | --- | --- |
| Local US parquet | Dedicated helper exists in `src/services/us_history_helper.py:1-215`. | Local-first deterministic US OHLCV history. | Not used by the current Home path; Home calls `DataFetcherManager.get_daily_data()` directly (`src/core/pipeline.py:220-305`). | `score-grade` for history/technicals once explicitly adopted. |
| Local technical provider `local_history` | Planner lists `local_history` for technicals (`src/services/analysis_provider_planner.py:167`). | Derived indicators from stored/local history instead of external TA APIs. | Not directly visible as an explicit Home runtime route in the current fast US supplemental fetch. | `score-grade` candidate for deterministic technicals. |
| Polygon | No direct match in current Home request/service/pipeline/analyzer path; appears only in tests/runtime source labels, not as an active Home provider route in inspected files. | Could support official-ish US grouped daily reference if separately scoped. | Not currently wired in Home runtime. | `future bounded reference`, not implied by current behavior. |
| Twelve Data | Capability metadata exists and HK route exists in `DataFetcherManager`, but no direct Home US single-stock runtime wiring in the inspected Home flow (`src/services/provider_capability_matrix.py:293-310`, `src/services/provider_capability_matrix.py:1903-1918`). | HK/US quote/OHLCV or FX/crypto cross-check. | Not part of current Home single-stock evidence assembly. | `bounded observation` or fallback. |
| FRED / official Fed liquidity | Capability entries exist only in provider fit/capability metadata (`src/services/provider_capability_matrix.py:1610-1657`). | Official macro/liquidity baselines. | Not directly wired into current Home single-stock fetch/prompt path. | `official macro observation`, potentially score-grade only after cache-qualified contracts. |
| US Treasury baseline | Capability entry exists in provider fit metadata (`src/services/provider_capability_matrix.py:1871-1885`). | Official rate reference and macro cross-check. | Not directly wired into current Home path. | `official macro observation`. |
| Router diagnostic snapshots | Metadata-only snapshots expose source tier, freshness, trust, observation-only, and scoring rules without runtime calls (`src/services/data_source_router_diagnostics.py:1-106`). | Authority/capability disclosure, test fixtures, and implementation planning. | Not used as a Home evidence contract today. | `static authority source` for T-920. |
| Persisted context snapshots / fundamental snapshots | Sync analyze reloads `context_snapshot` and fallback fundamental payload when rebuilding the final report (`api/v1/endpoints/analysis.py:1151-1274`). | Historical review and response hydration. | Used after the fact, not as an upstream evidence packet for prompt quality. | `observation-only replay source` unless normalized earlier in the flow. |
| Tests / fixtures | Evidence coverage tests already model ORCL-like partial, fallback, timeout, and leakage cases (`tests/services/test_analysis_research_readiness_projection.py:272-432`). | Regression evidence and protected-domain guardrails. | Test-only, not runtime input. | `demo/test-only`. |

## 3. Why ORCL-Like Analysis Becomes Partial

### 3.1 US finance evidence reaches the prompt in the wrong shape

`get_fundamental_context()` explicitly returns `market not supported` for `us` and `hk` (`data_provider/base.py:2822-2829`). But the analyzer prompt still gives its richest finance table to `fundamental_context.earnings.data.financial_report` and `dividend`, which is the section most likely to elicit concrete earnings/cash-flow/dividend reasoning (`src/analyzer.py:1641-1684`).

The real US fundamentals/earnings work is happening elsewhere:

- `_fetch_us_supplemental_categories()` gathers FMP/Finnhub/YFinance/Alpha Vantage data (`src/core/pipeline.py:1076-1166`);
- `_build_fundamentals_block()` and `_build_earnings_analysis_block()` normalize that data into structured blocks (`src/core/pipeline.py:3263-3673`);
- the prompt then injects them only as later JSON-ish snippets (`src/analyzer.py:1700-1719`).

Result: the LLM sees US financial evidence, but not in the highest-salience prompt position.

### 3.2 News and catalyst enrichment is optional, timeout-bounded, and fail-open

Optional intelligence is resolved under a short deadline. When it times out, Home marks `optional_enrichment_pending`, appends failure reasons, and continues analysis (`src/core/pipeline.py:625-647`, `src/core/pipeline.py:722-741`). That produces truthful downstream degradation, but it also means:

- the LLM may never see useful recent catalysts;
- the API still returns success if an analysis object exists (`api/v1/endpoints/analysis.py:301-320`, `api/v1/endpoints/analysis.py:625-647`).

### 3.3 News evidence is flattened before it becomes report-grade evidence

The current flow is:

1. `search_comprehensive_intel()` searches multiple dimensions and provider fallbacks (`src/search_service.py:2663-3012`);
2. `_collect_news_items_from_intel()` strips each result to title/snippet/url/dimension/date (`src/core/pipeline.py:2705-2720`);
3. `format_intel_report()` turns intelligence into a long text blob used as `news_context` (`src/core/pipeline.py:650-679`);
4. `_build_sentiment_analysis_block()` classifies at most five items, but keeps `top_positive_items` and `top_negative_items` empty in both weak and ok paths (`src/core/pipeline.py:3687-3815`).

This means the system does gather news, but loses:

- bounded top-N catalyst selection;
- per-item polarity/importance ordering;
- quote-ready citation fields that could survive into the final report;
- an explicit “why this matters to this stock” packet beyond heuristic relevance labels.

### 3.4 Local-first history capability exists but is not what Home actually uses

The repo already has `fetch_daily_history_with_local_us_fallback()` and local parquet support (`src/services/us_history_helper.py:138-215`). Home does not use that helper. The current Home path calls `DataFetcherManager.get_daily_data()`, which for US effectively routes through Alpaca then YFinance (`data_provider/base.py:1093-1203`, `src/core/pipeline.py:220-305`). Analysis context then comes from stored DB rows (`src/storage.py:9716-9774`).

This is not wrong, but it means:

- Home cannot currently claim local deterministic parquet authority;
- history freshness/authority depends on upstream fetch success plus DB persistence;
- “local data exists somewhere in repo” should not be confused with “Home currently uses it”.

### 3.5 Placeholder fill and result-presence success semantics keep partial runs alive

The analyzer can fill missing mandatory fields with placeholders (`src/analyzer.py:116-149`). The pipeline then caps scores and neutralizes unsafe language, but still returns a result object when possible (`src/core/pipeline.py:1168-1244`). The endpoint layer logs success/completion based on result presence, not on a top-level evidence-ready verdict (`api/v1/endpoints/analysis.py:301-320`, `api/v1/endpoints/analysis.py:625-647`).

### 3.6 `evidenceCoverageFrame` and `researchReadiness` are downstream truth, not upstream evidence

`_build_home_evidence_coverage_frame()` is accurate about degraded/missing/blocked domains, and tests already cover ORCL-like partial, missing news/fundamentals/catalysts, provider timeouts, and no raw leakage (`src/services/analysis_service.py:929-1255`, `tests/services/test_analysis_research_readiness_projection.py:272-432`). But these objects are created after the evidence has already been flattened for the prompt and final narrative.

## 4. Evidence Extraction Flow And Where Evidence Is Lost

### 4.1 Current extraction flow

1. Raw source acquisition
   - local/remote history via `DataFetcherManager.get_daily_data()` (`data_provider/base.py:1093-1203`);
   - US supplemental providers for quote/fundamentals/earnings/history/technicals (`src/core/pipeline.py:1076-1166`);
   - multi-dimension SearchService intelligence and optional social sentiment (`src/core/pipeline.py:620-766`, `src/search_service.py:2452-3012`).

2. Normalization into structured analysis blocks
   - fundamentals and earnings are merged into normalized blocks with field sources, periods, derived metrics, and summary flags (`src/core/pipeline.py:3263-3673`);
   - sentiment/catalyst logic builds a weak relevance classifier over collected news items (`src/core/pipeline.py:3687-3815`).

3. Data quality compression
   - `build_data_quality_report()` converts missing/stale/non-live/timeout/fallback conditions into caps, tiers, reason codes, and missing domain buckets (`src/services/data_criticality.py:359-522`).

4. Prompt assembly
   - rich tables for price/realtime/chip/trend;
   - rich finance table only when `fundamental_context` supports it;
   - JSON-like structured snippets for fundamentals/earnings/sentiment;
   - flattened `news_context` text block (`src/analyzer.py:1529-1867`).

5. LLM parse/fill
   - JSON parse, repair, lenient validation, integrity retries, placeholder fill (`src/analyzer.py:82-149`, `src/analyzer.py:2106-2291`).

6. Public projection
   - `report`, `researchReadiness`, `evidenceCoverageFrame`, `dataQualityReport`, persisted context snapshots (`src/services/analysis_service.py:686-1255`, `api/v1/endpoints/analysis.py:1151-1274`).

### 4.2 Main evidence loss / flattening points

1. **History authority flattening**
   - Home collapses upstream history provenance into stored DB rows plus limited source metadata, without a durable per-bar authority packet.

2. **Fundamentals salience mismatch**
   - the strongest US finance evidence is normalized, but not promoted into the strongest prompt section.

3. **News/catalyst packet loss**
   - `_collect_news_items_from_intel()` keeps only minimal fields;
   - `format_intel_report()` turns results into prose;
   - `_build_sentiment_analysis_block()` never returns populated top positive/negative evidence arrays (`src/core/pipeline.py:2705-2720`, `src/core/pipeline.py:3687-3815`).

4. **Quality-over-evidence compression**
   - `dataQualityReport` is useful for guardrails, but it compresses rich evidence failure detail into capped reason codes and domain buckets.

5. **Coverage frame post-processing**
   - `evidenceCoverageFrame` truthfully reports which domains are degraded or blocked, but it cannot recover evidence that was never carried forward.

## 5. Implementation-Ready Phased Fixes

The next tasks should stay additive, projection-first, and bounded away from provider-order, cache semantics, or task lifecycle changes unless a later task explicitly expands scope.

### T-919 Single-stock evidence packet contract

Goal:

- introduce one additive `SingleStockEvidencePacketV1` assembled before prompt formatting and before public projection.

Minimum fields:

- `priceHistory`
- `technicals`
- `fundamentals`
- `earnings`
- `news`
- `catalysts`
- `sentiment`
- `valuation`
- `liquidityContext`
- `macroContext`
- per-domain `items`, `sourceAuthority`, `freshness`, `fallbackOrProxy`, `scoreContributionAllowed`, `missingReasons`

Implementation seam:

- build from existing `structured_analysis`, `runtime_execution.data`, `data_quality_report`, and persisted source metadata rather than adding new live calls.

Required tests:

- contract assembly from existing ORCL-like fixtures;
- no raw/internal/provider/cache/env leakage;
- missing domains fail closed to empty bounded packets, not optimistic defaults.

### T-920 Source capability / authority matrix for Home AI

Goal:

- separate “provider can do this in repo” from “Home may treat this as score-grade evidence”.

Implementation seam:

- reuse static capability and diagnostic vocabulary from `analysis_provider_planner`, `provider_capability_matrix`, and `data_source_router_diagnostics` (`src/services/analysis_provider_planner.py:161-393`, `src/services/provider_capability_matrix.py:231-426`, `src/services/data_source_router_diagnostics.py:1-106`).

Output:

- one bounded Home-facing authority map per domain and per market;
- allowed values such as `score_grade`, `observation_only`, `fallback_only`, `demo_only`, `not_wired`.

Required tests:

- metadata-only unit tests;
- no provider runtime calls;
- current Home runtime wiring must not silently expand.

### T-921 Bounded top-N news / catalyst extraction

Goal:

- preserve the most relevant recent news/catalyst items as structured evidence rather than only prose.

Implementation seam:

- extend the existing `news_items` collection and sentiment/catalyst classifier;
- populate bounded `top_positive_items`, `top_negative_items`, and `top_catalyst_items` with date/title/url/relevance/rationale.

Non-goals:

- no new provider probes;
- no change to provider order or SearchService call volume unless separately scoped.

Required tests:

- company-specific vs industry-noise filtering;
- timeout/fallback partials;
- max-N clipping and date-window enforcement.

### T-922 Fundamentals / earnings evidence normalizer

Goal:

- promote current US supplemental fundamentals/earnings evidence into a single consistent, prompt-ready packet with field-level authority and reporting basis.

Implementation seam:

- reuse `_build_fundamentals_block()` and `_build_earnings_analysis_block()` outputs as the base contract (`src/core/pipeline.py:3263-3673`);
- do not depend on CN-only `fundamental_context` for US/HK prompt salience.

Required tests:

- US symbol with FMP/YFinance/Finnhub/Alpha mixed coverage;
- delayed/fallback/partial field handling;
- explicit `ttm_pending_validation` and `quarterly_series_available` behavior preserved.

### T-923 LLM evidence citation / input hardening

Goal:

- make the prompt and output schema consume `SingleStockEvidencePacketV1` explicitly so the LLM cites bounded evidence instead of paraphrasing flattened blobs.

Implementation seam:

- prompt input order, citation instructions, and parse schema;
- no provider-order or auth/task-lifecycle changes.

Required tests:

- citation-required prompt regression;
- no fabricated finance/news citations when packet is partial;
- ORCL-like partial should produce explicit evidence gaps, not generic shallow analysis.

## 6. Recommended Next Task Sequence

Recommended order:

1. **T-919**: define the additive evidence packet contract first.
2. **T-920**: lock Home-facing authority/freshness semantics before promoting more sources.
3. **T-922**: normalize US fundamentals/earnings into the packet and remove the current salience mismatch.
4. **T-921**: preserve bounded top-N news/catalyst items into the same packet.
5. **T-923**: update prompt/schema consumption only after upstream packet and authority semantics are stable.

Reason:

- T-919/T-920 create the non-runtime-expanding contract layer.
- T-922/T-921 fill the two biggest evidence gaps.
- T-923 should be last so prompt work targets stable upstream evidence structures instead of intermediate shapes.

## 7. Protected Domains And Required Tests Before Any Write Task

### 7.1 Protected domains

Any follow-up write task must treat these as protected unless explicitly scoped:

- provider runtime order and live-call/fallback semantics (`data_provider/base.py`, provider executors, router behavior);
- MarketCache TTL/SWR/background refresh behavior;
- LLM model routing, retry, and unsafe-text guardrails;
- task success/completion semantics in API/execution logs;
- public API response shapes and persisted contract versions;
- scanner/portfolio/options behavior outside Home single-stock audit scope.

### 7.2 Required tests before a write task lands

Minimum pre-write test plan:

- unit tests for the new evidence packet assembly and authority matrix;
- regression tests covering existing ORCL-like partial, missing fundamentals/news/catalysts, provider timeout, and no raw leakage scenarios (`tests/services/test_analysis_research_readiness_projection.py:272-432`);
- prompt/report projection tests proving evidence survives into public report sections and `evidenceCoverageFrame` stays truthful;
- no-network metadata-only tests for capability/authority logic;
- `git diff --check` and secret scan on docs/contracts;
- if prompt/schema changes are introduced later, targeted analyzer parse/regression tests are mandatory.

## 8. Audit Conclusion

Home AI is not primarily missing more providers. It is missing a contract that preserves the best available single-stock evidence in a bounded, authority-aware, citation-ready shape. Today the system can truthfully disclose degradation after the fact, but it does not yet give the LLM or the final report a strong evidence packet early enough to produce consistently rich single-stock analysis.

The immediate path is additive:

- define one evidence packet;
- attach static source authority semantics to it;
- normalize US finance evidence into that packet;
- carry bounded top-N news/catalyst items through to the prompt and report;
- only then harden prompt/output citation behavior.
