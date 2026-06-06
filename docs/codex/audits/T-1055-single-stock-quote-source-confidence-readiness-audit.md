# T-1055 Single-stock Quote Source Confidence Readiness Audit

Task ID: T-1055-AUDIT

Task title: Single-stock quote source confidence readiness audit

Mode: READ-ONLY-AUDIT with explicitly authorized docs-only audit artifact, commit, and push.

Allowed artifact:

`docs/codex/audits/T-1055-single-stock-quote-source-confidence-readiness-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1055-single-stock-quote-source-confidence-audit`
- branch: `codex/t1055-single-stock-quote-source-confidence-audit`
- base commit inspected before writing this report: `e82103d7`
- current branch had no local commits ahead of `origin/main` during preflight.

Scope boundary:

- Source, tests, config, package, lockfile, provider, cache, runtime, API, frontend, scanner, portfolio, options, and backtest files were inspected only.
- This audit does not implement a quote adapter, source-confidence generator, provider/runtime adapter, API behavior change, frontend behavior change, score change, or test change.
- Final diff is limited to this Markdown report.

## Readiness verdict

Proceed with exactly one narrow future write:

**T-1055-M1: Evidence quote adapter diagnostic source-confidence projection.**

This future write is safe only if it stays at the evidence quote projection boundary and remains diagnostic-only. It should preserve the existing provider call path and public `/stocks/{code}/evidence` fail-closed seam, add no providers, make no network/routing/cache changes, and avoid score/source-authority promotion.

The current system is not ready for a broad provider-readiness adoption in the evidence quote adapter. `ProviderSourceReadinessContract` exists as an inert contract, but quote adapter inputs do not yet carry provider capability metadata, source tier, trust level, or freshness expectation. Those fields must remain deferred.

## Audit questions and answers

### 1. Where quote source/freshness metadata currently exists or is lost

Metadata exists in the dedicated stock quote and intraday paths:

- `StockService.get_realtime_quote()` wraps provider-runtime quote snapshots and emits `source`, `source_type`, `market_timestamp`, `observed_at`, `freshness`, fallback/stale/partial/synthetic flags, and `sourceConfidence` (`src/services/stock_service.py:133`, `src/services/stock_service.py:776`).
- `StockQuote` exposes the quote metadata as camelCase public fields: `sourceType`, `marketTimestamp`, `observedAt`, `freshness`, `isFallback`, `isStale`, `isPartial`, `isSynthetic`, and `sourceConfidence` (`api/v1/schemas/stocks.py:17`, `api/v1/schemas/stocks.py:61`).
- The quote endpoint maps both snake_case and camelCase service fields into `StockQuote` (`api/v1/endpoints/stocks.py:370`).
- `StockService.get_intraday_data()` builds analogous intraday source metadata and `sourceConfidence` (`src/services/stock_service.py:419`, `src/services/stock_service.py:468`, `src/services/stock_service.py:710`).
- `StockIntradayResponse` exposes `sourceType`, `freshness`, degraded flags, `isUnavailable`, and `sourceConfidence` (`api/v1/schemas/stocks.py:158`, `api/v1/schemas/stocks.py:201`).
- The intraday endpoint also maps those metadata fields into `StockIntradayResponse` (`api/v1/endpoints/stocks.py:442`).
- The frontend `stocksApi.getQuote()` type/normalizer preserves quote source metadata (`apps/dsa-web/src/api/stocks.ts:122`, `apps/dsa-web/src/api/stocks.ts:148`), and tests lock that behavior (`apps/dsa-web/src/api/__tests__/stocks.test.ts:20`).

Metadata is lost or weakened in the single-stock evidence quote path:

- `UnifiedRealtimeQuote` only carries `source` and `market_timestamp` as quote provenance. It does not carry `sourceType`, `freshness`, degraded flags, provider capability metadata, or `sourceConfidence` (`data_provider/realtime_types.py:93`, `data_provider/realtime_types.py:111`, `data_provider/realtime_types.py:153`).
- `StockEvidenceQuoteSnapshot` keeps only `source`, price fields, fundamentals-lite fields, and `market_timestamp`; it has no `freshness`, flags, or `sourceConfidence` (`src/services/stock_evidence_quote_adapter.py:13`).
- `StockEvidenceService._quote()` emits only `status`, `price`, `changePct`, `currency`, `provider`, `updatedAt`, and a few quote-derived fundamentals fields (`src/services/agent_stock_evidence_service.py:396`).
- `StockEvidencePacketResponse` strongly types only `fundamentalsSummary`; `StockEvidenceItemResponse.quote` remains an opaque dictionary (`api/v1/schemas/stocks.py:248`, `api/v1/schemas/stocks.py:260`).
- `stockEvidenceApi` and `StockEvidenceItem` keep quote as an opaque record, so frontend evidence consumers can preserve extra quote keys if backend emits them, but they do not currently require or normalize quote source-confidence fields (`apps/dsa-web/src/types/stockEvidence.ts:23`, `apps/dsa-web/src/api/stockEvidence.ts:99`, `apps/dsa-web/src/api/stockEvidence.ts:124`).
- `project_stock_evidence_packet()` falls back to `sourceType=local_or_reported` and `freshness=unknown` when the quote item lacks top-level metadata (`src/services/stock_evidence_packet.py:152`).
- Existing regression coverage shows the current fallback quote keeps provider/as-of but the packet quote source ref remains `freshness=unknown` (`tests/test_provider_runtime_contracts.py:725`).

### 2. Whether existing quote adapter fields can be normalized without runtime behavior changes

Yes, but only narrowly.

The safe normalization surface is diagnostic projection from fields already present in the evidence quote snapshot:

- `source`
- `market_timestamp`
- existing quote numeric fields
- derived degraded state for an explicit `fallback` source

This can be done without changing provider runtime behavior because the evidence adapter already calls `get_realtime_quote()` through the same injected `fetcher_manager`, and the public evidence endpoint already replaces that manager with `_ReadOnlyEvidenceFetcherManager` before calling the service (`api/v1/endpoints/stocks.py:52`, `api/v1/endpoints/stocks.py:296`).

The future write must not alter `DataFetcherManager`, provider order, retry/fallback semantics, MarketCache, stock service quote runtime, or network behavior. It should also avoid changing `project_stock_evidence_packet()` scoring/claim logic. If top-level `quote.freshness` or `quote.sourceType` is introduced, tests must prove that current score-eligible evidence and claim-boundary behavior is not promoted accidentally.

The lowest-risk implementation shape is:

- keep the current quote runtime call unchanged;
- add bounded diagnostic `quote.sourceConfidence` and source/as-of fields to the evidence quote item;
- fail closed for unproven freshness and fallback sources;
- do not set `sourceAuthorityAllowed=true`;
- do not set `scoreContributionAllowed=true`;
- do not add `readinessState` or ProviderSourceReadiness payloads yet.

### 3. Fields deferred until ProviderSourceReadinessContract is adopted

`SourceConfidenceContract` and `ProviderSourceReadinessContract` already exist, but the evidence quote adapter lacks capability metadata needed for a readiness join (`src/services/source_confidence_contract.py:83`, `src/services/source_confidence_contract.py:440`, `src/services/source_confidence_contract.py:575`).

Defer these fields and semantics:

- `providerId`
- `capability`
- provider-readiness `sourceType`
- `sourceTier`
- `trustLevel`
- `freshnessExpectation`
- `observedFreshness`
- `effectiveFreshness`
- `readinessState`
- `reasonCodes`
- `authorityGrant`
- readiness-derived `sourceAuthorityAllowed`
- readiness-derived `scoreContributionAllowed`
- provider capability or source matrix wiring

Reason: these fields require joining quote source-confidence metadata with provider capability/support metadata. Guessing them from `UnifiedRealtimeQuote.source` would overclaim authority and risk changing source/scoring semantics.

### 4. Exact safe file boundaries for one future write

Allowed future write files:

- `src/services/stock_evidence_quote_adapter.py`
- `src/services/agent_stock_evidence_service.py`
- `tests/test_provider_runtime_contracts.py`
- `tests/api/test_stock_evidence_api.py`

No schema change should be required because `StockEvidenceItemResponse.quote` is already an opaque dict and `StockEvidencePacketResponse` is compatibility-open (`api/v1/schemas/stocks.py:248`, `api/v1/schemas/stocks.py:260`).

Forbidden future write files and domains for T-1055-M1:

- `data_provider/**`
- `src/services/stock_service.py`
- `src/services/stock_service_provider_adapter.py`
- `src/services/source_confidence_contract.py`
- `src/contracts/source_confidence.py`
- `src/services/single_stock_source_capability_matrix.py`
- `src/services/stock_evidence_packet.py`
- `src/services/single_stock_evidence_packet.py`
- `src/services/single_stock_evidence_contract.py`
- `src/services/analysis_service.py`
- `api/v1/endpoints/stocks.py`
- `api/v1/schemas/stocks.py`
- `api/v1/schemas/home_evidence.py`
- `api/v1/schemas/history.py`
- `apps/**`
- provider router, capability, planner, usage-ledger, MarketCache, scanner, ranking, portfolio, options, backtest, root config, CI, package, and lockfile paths

### 5. Focused tests proving no provider/runtime/network behavior changed

Future T-1055-M1 should add or update focused tests only in the allowed test files:

1. `tests/test_provider_runtime_contracts.py`
   - Inject a fake `fetcher_manager` returning `UnifiedRealtimeQuote`.
   - Assert exactly the same fetcher manager remains wired to `StockEvidenceService` and `StockEvidenceQuoteAdapter`.
   - Assert no real `DataFetcherManager` construction is needed for the test.
   - Assert `StockEvidenceService._quote()` preserves existing quote fields and adds only bounded diagnostic metadata.
   - Cover at least one normal source and one `RealtimeSource.FALLBACK`.
   - Assert fallback/synthetic/unavailable metadata never claims live/fresh authority.
   - Assert packet claim boundaries and score evidence are not promoted by the diagnostic addition.

2. `tests/api/test_stock_evidence_api.py`
   - Patch `StockEvidenceService` and assert `/api/v1/stocks/{code}/evidence` serializes any new quote diagnostic keys without needing schema churn.
   - Add a seam test proving the endpoint still replaces `quote_adapter.fetcher_manager` and `service.fetcher_manager` with `_ReadOnlyEvidenceFetcherManager`.
   - Assert the endpoint default path remains fail-closed and does not call provider runtime or network.

Recommended validation for the future write:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python3 -m pytest -q tests/test_provider_runtime_contracts.py tests/api/test_stock_evidence_api.py -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python3 -m py_compile src/services/stock_evidence_quote_adapter.py src/services/agent_stock_evidence_service.py
git diff --check
./scripts/release_secret_scan.sh
```

## Explicit rejections

This audit explicitly rejects:

- broad provider sweep;
- new provider integrations;
- new live provider calls;
- provider order changes;
- provider routing, retry, timeout, fallback, cache, TTL, SWR, or MarketCache behavior changes;
- source-authority or score-contribution promotion;
- scanner scoring, ranking, filtering, selection, thresholds, or sorting changes;
- stock score math changes;
- API response-shape rewrites beyond the existing opaque evidence quote dict;
- frontend redesign or Home/report UI changes;
- intraday frontend metadata preservation in T-1055-M1;
- consumer copy that implies advice, trading action, or valuation judgment;
- portfolio/accounting/FX/holdings changes;
- options/backtest calculations, gates, ranking, or stored semantics changes.

## Protected-domain warnings

Protected domains are adjacent but must remain unchanged:

- Provider runtime order/live-call paths/fallback semantics are protected.
- MarketCache TTL/SWR/cold-start/fallback/live-label semantics are protected.
- Source authority and score-contribution policy are protected.
- API response shape changes are protected unless explicitly additive and scoped.
- Scanner ranking/scoring/filtering and Home analysis scoring surfaces are protected.
- Frontend redesign is out of scope.

## Final audit decision

Ready for one narrow future write:

**T-1055-M1: Evidence quote adapter diagnostic source-confidence projection.**

Do not defer the entire workstream. Defer only provider-readiness/source-authority fields until `ProviderSourceReadinessContract` is adopted with real quote provider capability metadata.

Do not implement provider-backed quote adapter changes now. Do not touch provider runtime, `data_provider`, `StockService`, source-confidence contracts, packet scoring logic, or frontend surfaces in the first future write.

## Final diff confirmation for this audit

- This T-1055 task is report-only.
- No source code changed.
- No tests changed.
- No config/package/lockfile changes.
- No provider additions.
- No provider/cache/runtime/network/API/frontend behavior changes.
- No scanner scoring/ranking/filtering changes.
- No portfolio/accounting/FX/holdings changes.
- No options/backtest changes.
