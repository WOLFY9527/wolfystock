# T-1045 Provider Capability Source Confidence Contract Readiness Audit

## Metadata

- Task ID: T-1045-AUDIT
- Task title: Provider capability source confidence contract readiness audit
- Mode: READ-ONLY-AUDIT with explicit single docs artifact authorization
- Date: 2026-06-06
- Workspace: `/Users/yehengli/worktrees/t1045-provider-capability-source-confidence-audit`
- Branch: `codex/t1045-provider-capability-source-confidence-audit`
- Allowed final diff: this audit document only

## Executive Verdict

WolfyStock already has the ingredients for provider capability and source confidence. The gap is not a missing provider matrix or missing freshness model. The gap is a very small, inert bridge that can answer: "given static/advisory provider capability metadata and already-decided source confidence metadata, what consumer-safe readiness posture can be projected?"

That bridge is safe only if it stays helper/test-only, accepts caller-provided metadata, and never imports provider clients, reads credentials, calls networks, reads/writes MarketCache, changes fallback decisions, changes API payloads, or alters scoring/readiness/ranking semantics.

Readiness verdict: safe for exactly one future write task, limited to an inert contract helper plus focused tests. Runtime/provider/API/frontend work should be deferred.

## Questions Answered

### 1. Existing capability and source-confidence concepts

Current capability concepts:

- `src/services/provider_capability_matrix.py` is explicitly metadata-only and must not import provider clients, read credentials, call networks, mutate runtime config, or affect provider order (`src/services/provider_capability_matrix.py:1`).
- `ProviderCapability` already models provider id/name, domains, markets, quota class, freshness class, recommended TTLs, scanner/backtest eligibility, research-mode eligibility, priority hints, and operator/risk notes (`src/services/provider_capability_matrix.py:22`, `src/services/provider_capability_matrix.py:76`).
- `ProviderScoringContract` separately documents scoring-contract gates such as coverage universe, cadence, freshness floor, coverage ratio floor, required source tier, and score eligibility gate (`src/services/provider_capability_matrix.py:97`).
- `ProviderCapabilitySupportContract`, `ProviderFitMetadataContract`, and `ProviderDryRunProbeContract` already project support, fit, and dry-run probe metadata as side-effect-free DTOs (`src/services/source_confidence_contract.py:180`, `src/services/source_confidence_contract.py:248`, `src/services/source_confidence_contract.py:331`).
- `provider_plan_advisor.py` returns advisory candidates and explicitly says the returned order must not be used as runtime provider execution order without separate approval (`src/services/provider_plan_advisor.py:1`, `src/services/provider_plan_advisor.py:152`).

Current source-confidence concepts:

- `SourceFreshness` already includes `fresh`, `live`, `delayed`, `cached`, `stale`, `partial`, `fallback`, `synthetic`, `unavailable`, and `unknown` (`src/services/source_confidence_contract.py:42`).
- `SourceConfidenceContract` already carries `source`, `sourceLabel`, `asOf`, freshness, fallback/stale/partial/synthetic/unavailable flags, `confidenceWeight`, coverage, degradation reason, and cap reason (`src/services/source_confidence_contract.py:68`).
- `apply_source_confidence_caps()` caps degraded sources so fallback, stale, partial, synthetic, and unavailable evidence cannot be projected as fresh/live or over-weighted (`src/services/source_confidence_contract.py:590`).
- `validate_source_confidence_contract()` rejects degraded sources claiming live/fresh freshness, out-of-range confidence, unavailable coverage, and degraded confidence above caps (`src/services/source_confidence_contract.py:633`).
- `evaluate_score_grade_source_authority()` is already an inert evaluator. It blocks missing, proxy, fallback, stale, partial, synthetic, unavailable, observation-only, non-score-contributing, and non-authority sources with bounded reason codes (`src/services/source_confidence_contract.py:504`).
- `build_provider_evidence_snapshot()` already normalizes evidence-like inputs into a diagnostic-only, observation-only snapshot with no provider runtime changes, no MarketCache mutation, no authority grant, and source-confidence aggregation (`src/services/provider_evidence_snapshot.py:33`, `src/services/provider_evidence_snapshot.py:169`).

Conclusion: reuse the existing source-confidence vocabulary and caps. Do not introduce a parallel provider/freshness vocabulary.

### 2. Where provider, fallback, stale, and partial semantics are decided

Protected runtime decision points:

- `data_provider/base.py` decides realtime quote routing and fallback. US quotes use yfinance-style flow; HK quotes try Twelve Data then AkShare HK; CN quotes use configured `realtime_source_priority` and first-good-wins plus limited supplementation (`data_provider/base.py:1580`, `data_provider/base.py:1622`, `data_provider/base.py:1743`, `data_provider/base.py:1813`).
- The realtime quote loop records attempts, insufficient fields, partial supplements, provider errors, final accepted source, and all-provider failure (`data_provider/base.py:1813`, `data_provider/base.py:1845`, `data_provider/base.py:1894`, `data_provider/base.py:1908`, `data_provider/base.py:1924`).
- Fundamental context timeout, retry, block status, not-supported, failed, and partial semantics are decided in `data_provider/base.py`, not in capability metadata (`data_provider/base.py:2523`, `data_provider/base.py:2572`, `data_provider/base.py:2648`, `data_provider/base.py:2689`, `data_provider/base.py:2805`, `data_provider/base.py:3086`).
- `AnalysisProviderExecutor` carries richer runtime metadata such as `is_fallback`, `cache_hit`, `partial`, attempts, deadline-exceeded results, and provider usage diagnostics (`src/services/analysis_provider_planner.py:85`, `src/services/analysis_provider_planner.py:414`, `src/services/analysis_provider_planner.py:448`, `src/services/analysis_provider_planner.py:485`).
- The executor decides cache hits, invalid payload fallback attempts, fallback-depth success, deadline-exceeded partial results, and failure reason codes (`src/services/analysis_provider_planner.py:535`, `src/services/analysis_provider_planner.py:556`, `src/services/analysis_provider_planner.py:654`, `src/services/analysis_provider_planner.py:690`, `src/services/analysis_provider_planner.py:794`).
- Market provider operations read cache/snapshot/admin-log state and classify display status as live/cache/stale/fallback/partial/unavailable/error/refreshing without calling providers or mutating cache (`src/services/market_provider_operations_service.py:119`, `src/services/market_provider_operations_service.py:136`, `src/services/market_provider_operations_service.py:316`, `src/services/market_provider_operations_service.py:522`).

Projection and readiness decision points:

- Home/analysis readiness evidence extracts `source`, `sourceType`, `sourceTier`, `trustLevel`, freshness, authority, score contribution, and degraded flags from existing blocks only (`src/services/analysis_service.py:191`).
- Missing evidence is forced to unavailable/observation-only/non-authority/non-score-contributing in that projection (`src/services/analysis_service.py:244`).
- Coverage freshness and fallback/proxy normalization are projection helpers, not provider execution logic (`src/services/analysis_service.py:345`, `src/services/analysis_service.py:381`).
- Coverage status degrades when evidence is missing, runtime failed, freshness is not fresh, fallback/proxy is present, or reason codes exist (`src/services/analysis_service.py:499`).
- Home research readiness grants source/score contribution only if all required domains are present and already marked authority/score-contributing (`src/services/analysis_service.py:947`).

Conclusion: a future contract must not decide provider order, fallback, stale, partial, timeout, cache-hit, or live/stale semantics. It may only normalize and cap metadata after these decisions already exist.

### 3. DTO boundaries that expose or hide provenance

Consumer/read-model exposure:

- Stock quote DTOs expose bounded provenance fields: `source`, `sourceType`, `marketTimestamp`, `observedAt`, `freshness`, fallback/stale/partial/synthetic flags, and optional `sourceConfidence` (`api/v1/schemas/stocks.py:17`).
- Stock history/intraday DTOs expose source diagnostics and source-confidence metadata without raw provider payloads (`api/v1/schemas/stocks.py:117`, `api/v1/schemas/stocks.py:158`).
- Single-stock evidence contracts sanitize text, block URL/secret-like strings, normalize freshness, cap confidence, and expose field-level provenance plus claim boundaries (`src/services/single_stock_evidence_contract.py:101`, `src/services/single_stock_evidence_contract.py:250`).
- Analysis coverage frames project `sourceId`, `sourceLabel`, `sourceTier`, provider authority, freshness, fallback/proxy, observation-only, and score-contribution flags from normalized blocks (`src/services/analysis_service.py:1152`).

Admin/diagnostic exposure:

- Market provider operations schemas expose admin-safe source and cache fields: provider, `sourceLabel`, `sourceType`, domain, endpoint, cache key, status, freshness, fallback/stale/refreshing flags, event rollups, cache state, and metadata (`api/v1/schemas/market_provider_operations.py:40`, `api/v1/schemas/market_provider_operations.py:82`, `api/v1/schemas/market_provider_operations.py:125`).
- Market provider operations service sanitizes provider/source/error text and redacts sensitive words before returning admin diagnostics (`src/services/market_provider_operations_service.py:614`).
- Provider usage ledger is sanitized in-process diagnostics only. It does not import providers or store raw payloads, and it drops sensitive metadata keys such as token, secret, password, authorization, cookie, api key, headers, request body, response body, raw, and payload (`src/services/provider_usage_ledger.py:1`, `src/services/provider_usage_ledger.py:25`, `src/services/provider_usage_ledger.py:108`, `src/services/provider_usage_ledger.py:145`).
- Runtime boundary tests assert provider capability metadata matches fixtures, advisory provider plans do not enable network/runtime behavior, usage events are sanitized, MarketCache degraded data is not live, and provider runtime fixtures contain no secret/raw payload leakage (`tests/test_provider_runtime_boundary.py:273`, `tests/test_provider_runtime_boundary.py:284`, `tests/test_provider_runtime_boundary.py:326`, `tests/test_provider_runtime_boundary.py:340`, `tests/test_provider_runtime_boundary.py:354`).

Hidden/protected internals:

- Raw provider payloads, credentials, request/response bodies, headers, stack traces, provider execution order, cache TTL/SWR/cold-start semantics, and router internals should remain hidden from consumer-safe contracts.
- `data_source_router_diagnostics.py` can serialize route-plan metadata for diagnostics, but it explicitly remains inert and sets `providerRuntimeCalled=false` and `networkCallsEnabled=false` (`src/services/data_source_router_diagnostics.py:1`, `src/services/data_source_router_diagnostics.py:79`).

Conclusion: public contracts may expose sanitized provenance summaries. Admin diagnostics may expose bounded operational state. Neither should expose raw provider/admin internals or become a second runtime authority layer.

### 4. Additive and safe contract shape

Smallest safe future shape: `ProviderSourceReadinessContract`.

Purpose: join already-provided static/advisory provider capability metadata with already-normalized source confidence metadata to produce a consumer-safe, fail-closed readiness sidecar.

Recommended fields:

```text
contractVersion: "provider_source_readiness_contract_v1"
diagnosticOnly: true
observationOnly: true
authorityGrant: false
scoreContributionAllowed: false
providerRuntimeCalled: false
networkCallsEnabled: false
marketCacheMutation: false

providerId: string
capability: string | null
source: string
sourceLabel: string
sourceType: string | null
sourceTier: string | null
trustLevel: string | null
freshnessExpectation: string | null

observedFreshness: SourceFreshness
effectiveFreshness: SourceFreshness
confidenceWeight: number
coverage: number | null

readinessState:
  "ready_for_observation"
  | "blocked_missing_capability_metadata"
  | "blocked_missing_source_confidence"
  | "blocked_unavailable_source"
  | "blocked_synthetic_source"
  | "blocked_fallback_source"
  | "blocked_stale_source"
  | "blocked_partial_coverage"
  | "blocked_source_authority"
  | "blocked_score_contribution"

reasonCodes: string[]
capReason: string | null
degradationReason: string | null
```

Rules:

- Inputs must be mappings or existing DTO objects only. No provider imports, no config/env access, no network, no MarketCache, no service calls.
- Missing capability or missing source-confidence fields must fail closed.
- Existing `coerce_source_confidence_contract()` and `evaluate_score_grade_source_authority()` should be reused for caps and reason codes.
- The bridge may say `ready_for_observation`; it must not say score-grade, rank-ready, trade-ready, decision-grade, source-authority-granted, or live-provider-ready.
- `scoreContributionAllowed` must remain false in the bridge unless a later protected-domain task explicitly scopes scoring semantics. For this first write, keep it always false.
- If observed freshness is live/fresh but capability or source-confidence metadata is missing/ambiguous, normalize to unknown/degraded posture and emit bounded reason codes.

Non-goals:

- No API schema changes.
- No provider runtime order or fallback changes.
- No MarketCache TTL/SWR/cold-start changes.
- No scoring, ranking, readiness, or recommendation changes.
- No provider additions or live probes.
- No frontend display changes.

### 5. Files a future write may touch

Exactly one future write task is safe:

Task: add inert `ProviderSourceReadinessContract` helper and focused tests.

Allowed future write files:

- `src/services/source_confidence_contract.py`
- `src/contracts/source_confidence.py`
- `tests/test_source_confidence_contract.py`

Optional docs-only companion if the task prompt explicitly includes documentation:

- `docs/operations/provider-capability-metadata.md`

Acceptance criteria:

- The helper is pure and deterministic.
- It imports no provider clients, MarketCache, config, API endpoints, app services, or runtime provider planner.
- It accepts caller-provided mappings/DTOs only.
- It reuses existing source-confidence caps and source-authority evaluation.
- It returns diagnostic-only and observation-only metadata.
- It fails closed for missing/ambiguous provider, capability, source, source type, source tier, trust level, freshness, fallback, stale, partial, synthetic, unavailable, non-authority, or non-score-contributing inputs.
- Focused tests prove degraded inputs cannot claim live/fresh, score contribution, source authority, or decision-grade readiness.
- Focused tests prove importing the contract does not import live provider clients, runtime planner/executor, MarketCache, API endpoints, or config.

### 6. Files and domains that must remain forbidden

Forbidden files/domains for the first future write:

- `data_provider/**`
- `src/services/analysis_provider_planner.py`
- `src/services/provider_plan_advisor.py`
- `src/services/provider_capability_matrix.py`
- `src/services/data_source_router.py`
- `src/services/data_source_router_diagnostics.py`
- `src/services/market_provider_operations_service.py`
- `src/services/provider_usage_ledger.py`
- `src/services/analysis_service.py`
- `src/services/market_cache.py`
- `src/services/liquidity_monitor_service.py`
- `src/services/market_rotation_radar_service.py`
- `src/services/market_overview_service.py`
- `src/services/options_market_data_provider.py`
- `api/**`
- `apps/**`
- `tests/api/**`
- provider fixtures, cache fixtures, runtime fixtures, package/lock/config/CI files

Forbidden semantic changes:

- provider global order
- live-call paths
- first-good-wins fallback
- fallback/live/stale/partial labeling
- MarketCache TTL/SWR/cold-start/cache-key/payload meaning
- provider usage ledger sanitization
- source-authority, score-contribution, readiness, ranking, scanner score, rotation rank/headline lane, options gates, portfolio/backtest/accounting, AI prompts/routing, auth/RBAC
- public API response shapes and stored contract versions

## Evidence Summary

| Area | Evidence | Readiness implication |
| --- | --- | --- |
| Static capability metadata | `ProviderCapability`, support contracts, fit metadata, dry-run probes | Existing metadata is sufficient for a bridge input, but should not be modified in the first write. |
| Source confidence | `SourceConfidenceContract`, caps, validator, score-authority evaluator | Existing caps and reason codes should be reused directly. |
| Provider evidence snapshot | Diagnostic-only/observation-only aggregate helper | Good reference for fail-closed projection shape. |
| Runtime fallback | `data_provider/base.py` and `AnalysisProviderExecutor` | Protected seam; future helper must not touch or recompute runtime behavior. |
| Route eligibility | `data_source_router.py` and diagnostics snapshot | Useful shape for metadata-only diagnostics, but not the source-confidence bridge itself. |
| DTO/API exposure | stock schemas, market provider operations schemas, single-stock evidence contract | Expose sanitized provenance summaries only; keep raw provider/admin internals hidden. |
| Tests | source-confidence, provider capability matrix, provider evidence snapshot, provider runtime boundary | Existing tests define the required safety posture for future helper tests. |

## Recommendation

Recommend exactly one future write task:

`T-1045-M1: Add inert ProviderSourceReadinessContract helper and tests`

Scope:

- Add a pure helper/class in `src/services/source_confidence_contract.py`.
- Re-export it from `src/contracts/source_confidence.py`.
- Add focused tests in `tests/test_source_confidence_contract.py`.

Do not modify provider runtime, capability matrix contents, routing, cache, API, frontend, schema, scoring, ranking, readiness, or provider additions in this first task.

## Final Boundaries Confirmed For This Audit

- No source code changed.
- No tests changed.
- No config/package/lockfile changes.
- No provider additions.
- No fallback/live/stale/partial semantic changes.
- No scoring/readiness/ranking changes.
- No API/frontend/schema/migration/auth/scanner/portfolio/options/backtest/market behavior changes.
