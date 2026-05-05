# Scanner AI Interpretation Cache Design

Date: 2026-05-06
Mode: docs-only design. No runtime behavior changed.

## 1. Purpose

This note designs a future optional cache for Scanner AI interpretation text.

Goals:

- reduce repeated scanner AI interpretation LLM cost when the same bounded candidate interpretation would otherwise be regenerated
- preserve deterministic scanner output: ranking, score, selection, thresholds, candidate diagnostics, and candidate actionability remain authoritative
- keep AI interpretation additive and non-authoritative
- require duplicate-cost metrics before implementation, following `docs/audits/llm-provider-duplicate-cost-metrics-design.md`

This is a design note only. No cache, counters, APIs, UI, tests, dependencies, provider behavior, or runtime behavior are implemented here.

## 2. Confirmed current behavior

Confirmed from static inspection:

- Scanner API entrypoint: `api/v1/endpoints/scanner.py::run_market_scan()` builds `MarketScannerOperationsService` and calls `MarketScannerOperationsService.run_manual_scan(...)`, which uses `src/services/market_scanner_service.py::MarketScannerService.run_scan()`.
- Scanner deterministic selection happens before AI interpretation. In `src/services/market_scanner_service.py::MarketScannerService._prepare_shortlist()`, candidates are sorted by `(-score, symbol)`, the first `resolved_shortlist_size` candidates become the shortlist, and `rank` is assigned before AI interpretation is called.
- Scanner score is computed before shortlist preparation. CN, US, and HK score paths finalize `candidate["score"]` in `MarketScannerService._finalize_candidates()`, `_finalize_us_candidates()`, and `_finalize_hk_candidates()` after market-specific component scoring.
- AI interpretation is triggered only after deterministic shortlist selection through `src/services/scanner_ai_service.py::ScannerAiInterpretationService.interpret_shortlist(profile=..., candidates=shortlist)`.
- `ScannerAiInterpretationService.interpret_shortlist()` copies the shortlist candidate dictionaries, resolves `top_n` through `_resolve_top_n()`, and attempts AI generation only for candidates with index `<= top_n`.
- `_resolve_top_n()` reads `config.scanner_ai_top_n`, defaults to `3`, and clamps the value to `1..10`.
- Current skip/fallback behavior is explicit:
  - empty shortlist returns skipped diagnostics
  - `SCANNER_AI_ENABLED=false` attaches a disabled payload and keeps rule-based results
  - non-CN profiles are skipped in the current implementation
  - unavailable analyzer attaches an unavailable payload and keeps rule-based results
  - candidates beyond top-N receive skipped payloads
  - failed or unparsable LLM responses attach failed payloads and keep rule-based explanations
- The LLM seam is `ScannerAiInterpretationService._call_analyzer()`. When available, it calls `src/analyzer.py::GeminiAnalyzer.generate_text_with_meta(..., call_type="scanner_interpretation")`, which calls `_call_litellm()` and persists usage through `persist_llm_usage(...)`.
- Candidate prompt input is built in `ScannerAiInterpretationService._build_candidate_prompt()`. It includes market, profile, symbol, name, rank, deterministic score, quality hint, reason summary, reasons, risk notes, watch context, boards, key metrics, and feature signals.
- AI interpretation payloads are attached under candidate diagnostics through `ScannerAiInterpretationService._attach_payload()`, and public payloads are normalized by `public_payload_from_diagnostics()`.
- Persisted scanner rows preserve rank, score, reasons, watch context, boards, and diagnostics in `MarketScannerService._candidate_dict_to_model()`. Public response candidates are shaped by `_public_candidate_dict()`.
- `docs/market-scanner.md` and `docs/market-scanner_EN.md` confirm the product policy: AI is an optional second-pass interpretation layer, does not replace `rank / score`, is not the first-pass selector, does not block Scanner when unavailable, and should stay bounded by small top-N coverage.
- Frontend test context confirms scanner CSV headers are machine-oriented and stable today. `apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx` expects `rank,symbol,name,scannerScore,entryRange,target,stop,reason,risk,universeType,theme,generatedAt,runId`.

Confirmed implications:

- No scanner AI interpretation cache is confirmed to exist today.
- No scanner AI duplicate candidate counters are confirmed to exist today.
- Current AI interpretation is post-selection and additive. It is not part of candidate inclusion, ranking, scoring, threshold pass/fail, or CSV header generation.

Inferred design-relevant points:

- Repeated scanner runs can produce the same or near-identical top candidate payloads, so the optional AI interpretation layer is a plausible repeated LLM cost when enabled.
- Safe reuse cannot be based on symbol alone because the explanation depends on rank, score, reasons, watch context, profile, prompt, model route, language, and data freshness.

## 3. Hard safety boundary

A future cache may only affect explanatory AI interpretation text and closely related display metadata.

It must never alter:

- candidate inclusion
- official shortlist membership
- rank
- score
- threshold pass/fail
- preview threshold behavior
- candidate actionability
- candidate diagnostics used for selection/rejection
- scanner CSV machine headers
- scanner profile, market, universe, theme, or custom-symbol logic
- provider/runtime/fallback behavior
- LLM routing, prompt logic, model ordering, or AI decision logic
- `MarketCache` TTL, stale-while-revalidate, cold-start, or fallback behavior
- backtest calculations
- portfolio accounting
- notification routing
- DuckDB production runtime

The cache must be read only after the deterministic scanner result is finalized enough to identify an already-selected candidate interpretation request. It must not be consulted by scoring, ranking, filtering, or action-routing code.

## 4. Eligibility

A cached interpretation is eligible only if all of the following match:

- persisted scanner run id, or a stable scanner context hash when run-id reuse is explicitly safe
- market
- profile
- candidate symbol hash
- rank bucket, or exact deterministic rank if the implementation can prove exact rank is safe
- deterministic score bucket or score hash
- candidate reason payload hash, including reason summary, reasons, risk notes, watch context, boards, key metrics, feature signals, and quality hint
- prompt version
- model family or model route version
- language
- top-N policy version
- source freshness bucket or scanner data snapshot hash

Must not reuse:

- across different scanner runs unless equivalence is explicitly proven by stable context and payload hashes
- across changed candidate reason payloads
- across changed prompt, model, route, language, or top-N policy
- when scanner data freshness changes materially
- when scanner profile, market, universe type, theme id, or submitted symbol set changes
- when a user requests force refresh or cache bypass
- for ranking decisions
- for selection decisions
- for score decisions
- for threshold pass/fail decisions
- for CSV export header decisions

## 5. Proposed key and stored value

Safe conceptual key shape:

- `cache_scope = scanner_ai_interpretation`
- `run_id` or `scanner_context_hash`
- `market`
- `profile`
- `symbol_hash`
- `candidate_payload_hash`
- `rank_bucket` or `rank_hash`
- `score_bucket` or `score_hash`
- `prompt_version`
- `model_family`
- `language`
- `source_freshness_bucket`
- `top_n_policy_version`

Stored value concept:

- generated interpretation text fields:
  - `summary`
  - `opportunity_type`
  - `risk_interpretation`
  - `watch_plan`
  - optional `review_commentary` only if separately keyed to realized review payload freshness
- `generatedAt`
- `modelFamily`
- `promptVersion`
- `sourceFreshnessBucket`
- `cacheKeyHash`
- `interpretationScope = additive`

Do not store:

- raw prompt
- raw provider request payload
- raw provider response payload beyond the public interpretation fields
- raw secret config
- API keys, tokens, credentials, authorization headers, webhook URLs, or secret values
- raw user/session identifiers
- raw unbounded diagnostics labels

## 6. TTL / invalidation

Recommended starting policy:

- use a short TTL at first
- invalidate by default on a new scanner run unless equivalent context is proven
- invalidate on candidate payload hash change
- invalidate on prompt version change
- invalidate on model family or model route version change
- invalidate on language change
- invalidate on top-N policy version change
- invalidate on scanner source freshness bucket or snapshot hash change
- invalidate on scanner code/parser/schema version change when interpretation payload semantics may drift
- support explicit bypass for force-refresh or troubleshooting paths

Stale values must not be served silently. If a future prototype allows stale interpretation reuse, the response metadata must make age and freshness visible.

## 7. Disclosure and observability

Future response metadata concept:

- `reusedFromScannerAiCache`
- `generatedAt`
- `cacheAgeSeconds`
- `sourceFreshnessBucket`
- `cacheKeyHash`
- `interpretationScope = additive`
- warning field when the interpretation is stale or generated from an older-but-accepted freshness bucket

Metrics tie-in:

- `scanner_ai_duplicate_candidate_observed`
- `scanner_ai_interpretation_started`
- `scanner_ai_interpretation_completed`
- `scanner_ai_interpretation_skipped`
- future hit/miss counters only after the instrumentation plan exists and has measured repeat rate

Observability guardrails:

- use safe hashes for candidate identity
- keep labels bounded
- do not emit raw prompt, raw candidate reason payload, raw provider payload, raw generated text, secrets, or full user/session ids as labels
- distinguish generated, cache-hit, cache-miss, skipped, failed, disabled, and unavailable states
- keep high-volume cache success noise out of user-visible logs unless deliberately summarized

## 8. Rollout plan

Phase 1: instrumentation-only duplicate candidate counters

- Add counters around scanner AI interpretation identity only.
- Preserve scanner ranking, selection, score, thresholds, CSV export, provider behavior, prompt behavior, and UI behavior.

Phase 2: read-only duplicate-cost report

- Report observed repeated scanner AI candidate hashes and estimated duplicated LLM calls.
- Do not add cache behavior or provider calls.

Phase 3: disabled-by-default cache prototype

- Prototype read-through only for additive interpretation text.
- Keep cache disabled unless explicitly enabled in a controlled environment.
- Include cache disclosure metadata from the first prototype.

Phase 4: measured opt-in enablement

- Enable only after measured repeat rate is high enough to justify the complexity.
- Keep scope limited to additive interpretation text.
- Monitor hit rate, miss rate, bypass rate, stale-warning rate, and failure fallback rate.

## 9. Risks and non-goals

Risks:

- stale explanation text
- users over-trusting cached interpretation
- accidental coupling into ranking or candidate actions
- high-cardinality keys
- model, prompt, parser, or source-data drift
- cache hits hiding provider degradation if disclosure is weak
- review commentary reuse becoming unsafe if realized outcome payload freshness is not included

Non-goals:

- no scanner ranking cache
- no scanner score cache
- no candidate selection cache
- no threshold/pass/fail cache
- no scanner CSV changes
- no provider cache changes
- no `MarketCache` changes
- no AI decision routing changes
- no LLM routing or prompt changes
- no frontend UI changes
- no runtime behavior changes in this task

## 10. Recommended follow-up Codex tasks

1. Add scanner AI duplicate candidate counter only.
2. Add scanner AI repeat-cost read-only report.
3. Prototype disabled-by-default scanner interpretation cache after metrics show meaningful repeat rate.
4. Design UI/API disclosure for cached interpretation metadata.
5. Add regression tests proving ranking, selection, score, threshold pass/fail, candidate actionability, and CSV headers remain unchanged.

