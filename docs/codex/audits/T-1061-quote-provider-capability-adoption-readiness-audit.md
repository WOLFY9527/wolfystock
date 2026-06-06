# T-1061 Quote Provider Capability Adoption Readiness Audit

Task ID: T-1061-AUDIT

Task title: Quote provider capability adoption readiness audit

Mode: READ-ONLY-AUDIT with explicitly authorized docs-only audit artifact, commit, and push.

Allowed artifact:

`docs/codex/audits/T-1061-quote-provider-capability-adoption-readiness-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1061-quote-provider-capability-adoption-readiness-audit`
- branch: `codex/t1061-quote-provider-capability-adoption-readiness-audit`
- current branch had no local commits ahead of `origin/main` during preflight.

Scope boundary:

- Source, tests, config, package, lockfile, provider, cache, runtime, API behavior, frontend behavior, scanner, portfolio, options, and backtest files were inspected only.
- This audit does not wire `ProviderSourceReadinessContract` into runtime, add provider routing, add provider capability inference, grant source authority, grant score contribution, or alter fallback/live/stale/partial semantics.
- Final diff is limited to this Markdown report.

## Readiness verdict

Defer real quote provider capability and source-authority adoption.

The current quote evidence path is ready for diagnostic metadata only. It is not ready to derive or consume real provider capability metadata because the runtime quote object and evidence projection do not carry a trustworthy `providerId`, `sourceTier`, `trustLevel`, or `freshnessExpectation`. Guessing those fields from `UnifiedRealtimeQuote.source`, the quote adapter's `sourceType=local_or_reported`, or the stock quote endpoint's runtime metadata would be implicit authority inference.

`ProviderSourceReadinessContract` can remain as an inert helper, and it is already tested to fail closed and keep `authorityGrant=false` plus `scoreContributionAllowed=false`. It should not be adopted by quote evidence until a separately scoped provider/runtime task supplies explicit quote capability metadata without changing provider order, cache behavior, fallback behavior, network behavior, API contracts, or scoring.

Recommendation: **defer. No source/test/config/runtime future write is safe for T-1061 adoption.**

## Metadata families must stay separate

### Diagnostic quote metadata

Diagnostic quote metadata exists to explain the current evidence item. It includes:

- `source`, `sourceType`, `freshness`, `asOf`
- `isFallback`, `isStale`, `isPartial`, `isSynthetic`, `isUnavailable`
- `observationOnly=true`
- `scoreContributionAllowed=false`
- `sourceAuthorityAllowed=false`
- `rawPayloadStored=false`
- nested `sourceConfidence`

This is produced by `build_quote_diagnostic_source_metadata()` and merged into `StockEvidenceService._quote()` (`src/services/stock_evidence_quote_adapter.py:58`, `src/services/stock_evidence_quote_adapter.py:89`, `src/services/stock_evidence_quote_adapter.py:100`, `src/services/agent_stock_evidence_service.py:399`, `src/services/agent_stock_evidence_service.py:423`).

### Provider capability metadata

Provider capability metadata describes onboarded provider support, source classification, trust, freshness expectation, quota, and routing review posture. It is metadata-only and must not import providers, read credentials, call networks, mutate runtime config, or affect provider order (`src/services/provider_capability_matrix.py:1`, `src/services/provider_capability_matrix.py:76`, `docs/operations/provider-capability-metadata.md:50`).

The currently audited capability/support rows are not evidence that a runtime quote item came from an explicitly qualified provider/capability pair. Tests also keep these support rows observation-only and non-scoring (`tests/test_provider_capability_matrix.py:430`, `tests/test_provider_capability_matrix.py:445`).

### Authority and scoring metadata

Authority and scoring metadata answer a different question: whether an already qualified source may contribute to a named authority or scoring path. Current quote diagnostic metadata explicitly closes both gates. `ProviderSourceReadinessContract` also serializes `authorityGrant=false` and `scoreContributionAllowed=false` regardless of positive caller inputs (`src/services/source_confidence_contract.py:439`, `src/services/source_confidence_contract.py:466`, `tests/test_source_confidence_contract.py:647`).

Do not treat diagnostic metadata or provider capability metadata as authority/scoring metadata.

## Audit questions and answers

### 1. Which quote provider metadata currently exists at runtime

Runtime quote object:

- `UnifiedRealtimeQuote` carries `source` and `market_timestamp` as the only direct provenance fields relevant to quote evidence (`data_provider/realtime_types.py:111`, `data_provider/realtime_types.py:123`, `data_provider/realtime_types.py:153`).
- The `RealtimeSource` enum identifies provider-like source labels such as `yfinance`, `alpaca`, `twelve_data`, and `fallback`, but it does not encode provider capability, source tier, trust level, freshness expectation, or authority (`data_provider/realtime_types.py:93`).

Runtime routing trace:

- US quotes try the yfinance path and return the accepted quote or `None` (`data_provider/base.py:1571`, `data_provider/base.py:1581`, `data_provider/base.py:1591`, `data_provider/base.py:1611`).
- HK quotes try Twelve Data, then AkShare HK, and record attempt/failure outcomes before returning the accepted quote or `None` (`data_provider/base.py:1622`, `data_provider/base.py:1634`, `data_provider/base.py:1681`, `data_provider/base.py:1732`).
- CN quotes use `config.realtime_source_priority`, first-good-wins primary selection, optional supplementation, partial trace entries, and all-provider failure trace entries (`data_provider/base.py:1743`, `data_provider/base.py:1813`, `data_provider/base.py:1837`, `data_provider/base.py:1857`, `data_provider/base.py:1908`, `data_provider/base.py:1924`).

Evidence quote metadata:

- The evidence quote adapter receives `UnifiedRealtimeQuote`, copies source/price fields, and builds diagnostic-only source metadata from `source` and `market_timestamp` (`src/services/stock_evidence_quote_adapter.py:127`, `src/services/stock_evidence_quote_adapter.py:132`, `src/services/stock_evidence_quote_adapter.py:140`).
- Missing quote or runtime error paths become unavailable diagnostic metadata, not live/provider-authorized metadata (`src/services/agent_stock_evidence_service.py:399`, `src/services/agent_stock_evidence_service.py:413`).
- The `/stocks/{code}/evidence` endpoint installs `_ReadOnlyEvidenceFetcherManager`, so the public endpoint seam is fail-closed for quote runtime access by default (`api/v1/endpoints/stocks.py:296`, `api/v1/endpoints/stocks.py:299`).

Adjacent stock quote endpoint:

- `StockService._build_quote_metadata()` can label quote responses as `provider_runtime`, `fallback`, or `synthetic_placeholder`, and treats a present `market_timestamp` as `freshness=live` (`src/services/stock_service.py:776`, `src/services/stock_service.py:787`, `src/services/stock_service.py:802`, `src/services/stock_service.py:807`).
- That endpoint metadata is still not provider capability metadata. It does not prove source tier, trust level, freshness expectation, or score/source authority.

### 2. Whether provider ID, source tier, trust level, and freshness expectation can be derived safely today

No.

Safe derivation would require an explicit runtime quote provider/capability mapping. Today the quote evidence path has only:

- provider-like `source` strings from `UnifiedRealtimeQuote`;
- diagnostic `sourceType` values such as `local_or_reported`, `fallback`, `synthetic`, and `missing`;
- diagnostic freshness values such as `unknown`, `partial`, `fallback`, and `unavailable`.

It does not have:

- explicit `providerId`;
- explicit `capability=quote`;
- explicit `sourceTier`;
- explicit `trustLevel`;
- explicit `freshnessExpectation`;
- runtime proof that the accepted quote matched a specific provider capability support row.

The API evidence schema can preserve fields like `providerId`, `sourceTier`, `trustLevel`, and `freshnessExpectation` when supplied, but preservation is not derivation (`api/v1/schemas/stocks.py:260`, `tests/api/test_stock_evidence_api.py:171`). T-1061 must not promote a serialization allowance into an authority source.

### 3. Where fallback, stale, partial, synthetic, and unavailable state is currently known or lost

Known:

- Runtime routing knows provider attempts, accepted source, insufficient fields, supplement-required partials, supplement attempts, all-provider failure, and provider errors inside `data_provider/base.py` traces (`data_provider/base.py:1585`, `data_provider/base.py:1664`, `data_provider/base.py:1837`, `data_provider/base.py:1860`, `data_provider/base.py:1877`, `data_provider/base.py:1894`, `data_provider/base.py:1924`).
- `UnifiedRealtimeQuote.source=fallback` is preserved into evidence and converted to diagnostic `freshness=fallback` (`data_provider/realtime_types.py:108`, `tests/test_provider_runtime_contracts.py:905`).
- Missing market timestamp is projected as diagnostic partial metadata (`src/services/stock_evidence_quote_adapter.py:140`, `tests/test_provider_runtime_contracts.py:816`).
- Missing quote and runtime errors are projected as unavailable diagnostic metadata (`src/services/agent_stock_evidence_service.py:399`, `tests/test_provider_runtime_contracts.py:870`, `tests/test_provider_runtime_contracts.py:885`, `tests/test_provider_runtime_contracts.py:960`).
- Synthetic/mock/fixture detection is token-based in the diagnostic helper (`src/services/stock_evidence_quote_adapter.py:30`).

Lost or not safely carried:

- Runtime attempt traces are stored as manager-side trace state, not as fields on `UnifiedRealtimeQuote` passed to evidence.
- CN supplementation state is trace-only. The accepted `UnifiedRealtimeQuote` does not carry which fields were supplemented or the full attempt chain.
- Staleness is not proven by quote evidence. The quote diagnostic helper has no market-clock or provider SLA context, so normal quote evidence remains `freshness=unknown` even when `market_timestamp` exists (`tests/test_provider_runtime_contracts.py:653`, `tests/test_provider_runtime_contracts.py:743`).
- Provider capability metadata is not joined into quote evidence, and the tests explicitly reject deferred keys such as `providerId`, `sourceTier`, `trustLevel`, `freshnessExpectation`, `readinessState`, and `authorityGrant` inside quote diagnostics (`tests/test_provider_runtime_contracts.py:726`, `tests/test_provider_runtime_contracts.py:731`, `tests/api/test_stock_evidence_api.py:487`).

### 4. Whether ProviderSourceReadinessContract can be adopted without runtime/provider behavior changes

Not for quote evidence adoption.

The helper itself can be called without runtime/provider behavior changes only if callers already provide both inputs:

- provider capability metadata;
- source-confidence metadata.

The helper is inert by design and explicitly avoids provider imports, service calls, config reads, network calls, and cache mutation (`src/services/source_confidence_contract.py:575`). Its dataclass returns `providerRuntimeCalled=false`, `networkCallsEnabled=false`, and `marketCacheMutation=false` (`src/services/source_confidence_contract.py:462`, `src/services/source_confidence_contract.py:466`).

But quote evidence does not yet have safe provider capability input. Wiring the helper now would require one of two unsafe moves:

1. infer capability from `UnifiedRealtimeQuote.source`; or
2. change provider/runtime/cache paths to supply explicit quote capability metadata.

Both are outside the allowed T-1061 boundary. The first is implicit authority inference, and the second touches protected provider/runtime domains.

### 5. What tests would prove authority remains false until provider capability is explicit

Future tests must prove the following before any adoption task can proceed:

1. Existing quote diagnostics remain closed:
   - `observationOnly is True`;
   - `scoreContributionAllowed is False`;
   - `sourceAuthorityAllowed is False`;
   - `rawPayloadStored is False`;
   - no `providerId`, `sourceTier`, `trustLevel`, `freshnessExpectation`, `readinessState`, or `authorityGrant` appears in quote or nested `sourceConfidence`.

2. Degraded quote states stay non-authoritative:
   - fallback quote stays `freshness=fallback`, `isFallback=true`, `scoreContributionAllowed=false`, `sourceAuthorityAllowed=false`;
   - missing timestamp stays `freshness=partial`, `isPartial=true`, and is not score eligible;
   - missing quote/runtime error stays `freshness=unavailable`, `isUnavailable=true`, and is not score eligible;
   - normal provider-like source with timestamp remains `freshness=unknown` in evidence until freshness is explicitly proven.

3. `ProviderSourceReadinessContract` remains inert:
   - import does not import provider clients, MarketCache, runtime planners, API endpoints, config, or live provider modules;
   - positive caller inputs still serialize `authorityGrant=false` and `scoreContributionAllowed=false`;
   - missing capability metadata fails closed;
   - missing source-confidence metadata fails closed;
   - fallback/stale/partial/synthetic/unavailable inputs cannot become `live` or `fresh`.

Existing tests already cover most of this posture (`tests/test_source_confidence_contract.py:647`, `tests/test_source_confidence_contract.py:708`, `tests/test_source_confidence_contract.py:750`, `tests/test_source_confidence_contract.py:776`, `tests/test_source_confidence_contract.py:813`, `tests/test_provider_runtime_contracts.py:743`, `tests/test_provider_runtime_contracts.py:816`, `tests/test_provider_runtime_contracts.py:905`, `tests/test_provider_runtime_contracts.py:960`, `tests/api/test_stock_evidence_api.py:402`).

### 6. Exact allowed and forbidden files for one future write, if safe

No source/test/runtime future write is safe for real quote provider capability adoption right now.

Allowed future files for a real adoption write:

- none

Forbidden future files for T-1061 adoption until prerequisites are explicitly scoped:

- `data_provider/**`
- `src/services/stock_evidence_quote_adapter.py`
- `src/services/agent_stock_evidence_service.py`
- `src/services/stock_service.py`
- `src/services/stock_service_provider_adapter.py`
- `src/services/source_confidence_contract.py`
- `src/contracts/source_confidence.py`
- `src/services/provider_capability_matrix.py`
- `src/services/single_stock_source_capability_matrix.py`
- `src/services/provider_plan_advisor.py`
- `src/services/data_source_router.py`
- `src/services/data_source_router_diagnostics.py`
- `src/services/analysis_provider_planner.py`
- `src/services/market_cache.py`
- `src/services/market_provider_operations_service.py`
- `api/**`
- `apps/**`
- `tests/**`
- `scripts/**`
- `.github/**`
- root config, package, lockfile, dependency, env, Docker, provider fixture, cache fixture, and runtime fixture files
- scanner, rotation, portfolio, options, backtest, auth, notification, AI/LLM, and report-prompt files

The next safe step is not a write. It is a prerequisite design decision: define how a runtime accepted quote can carry explicit, sanitized provider capability identity without changing provider order, live-call behavior, cache semantics, fallback labels, API response contracts, or scoring. That decision requires a separate protected-domain prompt.

## Protected-domain warnings

Provider capability adoption is adjacent to protected domains:

- provider global order, live-call paths, and first-good-wins fallback;
- fallback/live/stale/partial labeling;
- MarketCache TTL/SWR/cold-start/cache-key/payload meaning;
- provider budget/routing behavior and network call paths;
- source authority, score contribution, readiness, ranking, filtering, and scanner scoring;
- API response shapes and stored contract versions;
- frontend consumer display of raw provider/schema/debug metadata.

T-1061 does not modify any of these domains.

## Validation plan for any later protected-domain adoption prompt

A later adoption prompt should not start by wiring `ProviderSourceReadinessContract`. It should first prove the upstream capability source is explicit and inert.

Minimum future proof before any code adoption:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python3 -m pytest -q \
  tests/test_source_confidence_contract.py \
  tests/test_provider_capability_matrix.py \
  tests/test_provider_runtime_contracts.py::test_stock_evidence_quote_projects_diagnostic_source_confidence_without_promotion \
  tests/test_provider_runtime_contracts.py::test_stock_evidence_quote_marks_missing_quote_timestamp_as_partial_diagnostic_only \
  tests/test_provider_runtime_contracts.py::test_runtime_fallback_quote_keeps_provider_trace_but_packet_downgrades_live_claims \
  tests/test_provider_runtime_contracts.py::test_runtime_unavailable_quote_keeps_unknown_contract_and_no_fake_live_fields \
  tests/api/test_stock_evidence_api.py::test_stock_evidence_endpoint_preserves_quote_diagnostic_metadata_and_readonly_seam \
  -p no:cacheprovider
git diff --check
./scripts/release_secret_scan.sh
```

Additional required assertions for a future adoption task:

- no provider clients are imported by the capability/readiness projection layer;
- no provider runtime order changes;
- no new network calls;
- no MarketCache TTL/SWR/cold-start behavior changes;
- no quote evidence score eligibility;
- no `sourceAuthorityAllowed=true`;
- no `scoreContributionAllowed=true`;
- no raw payload, credential, request, response, header, token, or stack trace leakage.

## Final audit decision

Defer real quote provider capability and source-authority adoption.

Do not adopt `ProviderSourceReadinessContract` into quote evidence now. Do not infer provider ID, source tier, trust level, or freshness expectation from current quote source strings. Do not grant authority or score contribution. Do not change provider runtime, provider routing, fallback/cache semantics, API behavior, frontend behavior, scanner scoring, portfolio, options, or backtest surfaces.

## Final diff confirmation for this audit

- This T-1061 task is report-only.
- No source code changed.
- No tests changed.
- No config/package/lockfile changes.
- No provider additions.
- No provider/cache/runtime/network/API/frontend behavior changes.
- No scanner scoring/ranking/filtering changes.
- No portfolio/accounting/FX/holdings changes.
- No options/backtest changes.
- No `ProviderSourceReadinessContract` runtime wiring.
- No authority or score contribution grant.
