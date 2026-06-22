# T-1053 Single-stock Evidence Adapter Readiness Audit

Task ID: T-1053-AUDIT

Task title: Single-stock evidence adapter readiness audit

Mode: READ-ONLY-AUDIT with explicitly authorized docs-only audit artifact

Allowed artifact:

`docs/codex/audits/T-1053-single-stock-evidence-adapter-readiness-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1053-single-stock-evidence-adapter-readiness-audit`
- branch: `codex/t1053-single-stock-evidence-adapter-readiness-audit`
- base commit inspected before writing this report: `be5344f8`
- branch state after `git fetch origin`: behind `origin/main` by 2 commits; no merge/rebase was performed because this task requires staying on the selected branch/workspace.

Scope boundary:

- Source, tests, config, package, lockfile, provider, cache, runtime, API, frontend, scanner, portfolio, options, and backtest files were inspected only.
- This audit does not implement a single-stock adapter, DTO lock, provider change, API behavior change, frontend behavior change, score change, or test change.
- Final diff is limited to this Markdown report.

## Readiness verdict

WolfyStock already has the core single-stock evidence ingredients: a Home/report `singleStockEvidencePacket`, a dedicated read-only `/api/v1/stocks/{stock_code}/evidence` endpoint, a pure single-stock metadata contract, a stock evidence packet projector, consumer-safe fundamentals summary filtering, and Home frontend rendering/tests.

The current gap is not missing evidence semantics. The gap is inconsistent metadata preservation across single-stock boundaries:

- quote and intraday API DTOs expose rich source/freshness metadata;
- history exposes diagnostics and `sourceConfidence`, but not first-class freshness/fallback/stale/partial flags;
- the dedicated `/evidence` response strongly locks only `fundamentalsSummary`, while other item payloads remain opaque dictionaries;
- the frontend stock intraday API type/normalizer currently drops backend intraday provenance fields;
- the evidence-only quote adapter currently carries only a small quote snapshot and cannot infer missing freshness/fallback authority.

Recommendation: proceed with exactly one future write only after T-1045/T-1046/T-1047 land or their equivalent contract decisions are stable:

**T-1053-M1: Minimal Home/analysis single-stock evidence consumed-subset DTO lock.**

This future write should be additive and fail-closed. It should lock the already-consumed Home/analysis report evidence subset before any adapter/provider work. It must not add providers, call networks, alter provider routing, change scoring/ranking/filtering, redesign UI, or change user-facing finance behavior.

## Audit questions and answers

### 1. Current single-stock evidence consumers

Primary consumers found:

- Home/report assembly builds `singleStockEvidencePacket`, attaches it into `analysis_result`, report `meta`, top-level report payload, and the API response mirror (`src/services/analysis_service.py:807`, `src/services/analysis_service.py:833`, `src/services/analysis_service.py:858`, `src/services/analysis_service.py:892`, `src/services/analysis_service.py:1907`).
- The dedicated single-stock evidence API endpoint is `GET /api/v1/stocks/{stock_code}/evidence`, using `StockEvidenceService` and a fail-closed read-only quote seam (`api/v1/endpoints/stocks.py:52`, `api/v1/endpoints/stocks.py:284`, `api/v1/endpoints/stocks.py:296`, `api/v1/endpoints/stocks.py:300`, `api/v1/endpoints/stocks.py:315`).
- `StockEvidenceService` builds a read-only evidence payload, attaches `stockEvidencePacket`, and sources quote/technical/fundamental/news blocks from existing read paths (`src/services/agent_stock_evidence_service.py:312`, `src/services/agent_stock_evidence_service.py:328`, `src/services/agent_stock_evidence_service.py:342`, `src/services/agent_stock_evidence_service.py:356`, `src/services/agent_stock_evidence_service.py:376`).
- The analysis endpoint/report path is another current consumer: sync analysis returns report data through `api/v1/endpoints/analysis.py`, while the persisted history schema still models report evidence fields loosely (`api/v1/endpoints/analysis.py:453`, `api/v1/endpoints/analysis.py:561`, `api/v1/schemas/history.py:145`, `api/v1/schemas/history.py:236`).
- Home frontend reads `singleStockEvidencePacket` from multiple report locations for report-derived evidence strips (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:916`).
- Home frontend calls `stockEvidenceApi.getStockEvidence(activeEvidenceTicker)` only for the current evidence ticker and stores the matched item's `stockEvidencePacket.fundamentalsSummary` (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5199`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5210`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5215`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5217`).
- The report-derived evidence strip consumes typed `SingleStockEvidencePacket` domain states and safe summaries (`apps/dsa-web/src/components/common/ConsumerEvidencePacketStrip.tsx:106`, `apps/dsa-web/src/components/common/ConsumerEvidencePacketStrip.tsx:167`, `apps/dsa-web/src/components/common/ConsumerEvidencePacketStrip.tsx:220`).

Conclusion: there are two distinct consumer paths that should stay distinct in future work:

1. Home/report `singleStockEvidencePacket` for report domain-state and evidence strip surfaces.
2. Dedicated `/stocks/{code}/evidence` `stockEvidencePacket`, currently used by Home for `fundamentalsSummary`.

The first future write should target the Home/report consumed subset because it can be locked through schema/tests without touching provider/runtime or evidence adapter code.

### 2. Where metadata exists vs where it is lost

Metadata exists today in these backend boundaries:

- `StockQuote` includes `source`, `sourceType`, `marketTimestamp`, `observedAt`, `freshness`, `isFallback`, `isStale`, `isPartial`, `isSynthetic`, and `sourceConfidence` (`api/v1/schemas/stocks.py:17`, `api/v1/schemas/stocks.py:61`).
- `StockIntradayResponse` includes `source`, `sourceType`, `freshness`, `isFallback`, `isStale`, `isPartial`, `isSynthetic`, `isUnavailable`, and `sourceConfidence` (`api/v1/schemas/stocks.py:158`, `api/v1/schemas/stocks.py:201`).
- `StockHistoryResponse` includes `source`, `diagnostics`, and `sourceConfidence` (`api/v1/schemas/stocks.py:117`, `api/v1/schemas/stocks.py:142`).
- `StockService` builds quote, history, and intraday source-confidence payloads and degrades unavailable/fallback/synthetic/partial cases before endpoint serialization (`src/services/stock_service.py:156`, `src/services/stock_service.py:256`, `src/services/stock_service.py:333`, `src/services/stock_service.py:419`, `src/services/stock_service.py:462`, `src/services/stock_service.py:710`, `src/services/stock_service.py:788`).
- `SourceConfidenceContract` already has freshness, fallback/stale/partial/synthetic/unavailable flags, confidence weight, coverage, degradation reason, and cap reason (`src/services/source_confidence_contract.py:42`, `src/services/source_confidence_contract.py:68`, `src/services/source_confidence_contract.py:106`).
- `single_stock_evidence_contract.py` sanitizes metadata, normalizes freshness, caps confidence, blocks live/fresh claims without proof, and emits claim boundaries (`src/services/single_stock_evidence_contract.py:10`, `src/services/single_stock_evidence_contract.py:22`, `src/services/single_stock_evidence_contract.py:171`, `src/services/single_stock_evidence_contract.py:250`, `src/services/single_stock_evidence_contract.py:291`, `src/services/single_stock_evidence_contract.py:314`).
- `stock_evidence_packet.py` projects required evidence, source refs, score-eligible evidence, observation-only evidence, claim boundaries, confidence caps, and `fundamentalsSummary` from existing evidence payloads (`src/services/stock_evidence_packet.py:14`, `src/services/stock_evidence_packet.py:152`, `src/services/stock_evidence_packet.py:430`, `src/services/stock_evidence_packet.py:456`, `src/services/stock_evidence_packet.py:473`, `src/services/stock_evidence_packet.py:502`, `src/services/stock_evidence_packet.py:550`, `src/services/stock_evidence_packet.py:590`).

Metadata is weaker or lost at these boundaries:

- `StockHistoryResponse` does not expose the same first-class top-level `freshness`, `isFallback`, `isStale`, `isPartial`, `isSynthetic`, and `isUnavailable` fields as quote/intraday. The data is mostly inside `sourceConfidence`/diagnostics, making history a weaker lock point (`api/v1/schemas/stocks.py:117`, `api/v1/schemas/stocks.py:142`).
- `StockEvidencePacketResponse` uses `extra="allow"` and strongly types only `fundamentalsSummary`; `StockEvidenceItemResponse` keeps quote/technical/fundamental/news/SEC evidence as `Dict[str, Any]` (`api/v1/schemas/stocks.py:248`, `api/v1/schemas/stocks.py:260`, `api/v1/schemas/stocks.py:267`).
- `api/v1/schemas/history.py` exposes `researchReadiness`, `evidenceCoverageFrame`, and `singleStockEvidencePacket` as `Any`; the report path also produces `evidenceCitationFrame` and `sourceProvenanceFrame`, but those are not strongly locked in the history/report schema today (`api/v1/schemas/history.py:145`, `api/v1/schemas/history.py:236`, `src/services/analysis_service.py:813`, `src/services/analysis_service.py:820`).
- Frontend dedicated stock evidence types mirror that split: only `fundamentalsSummary` is strongly typed; `quote`, `technical`, `fundamental`, `news`, and `secFilingEvidence` are opaque records (`apps/dsa-web/src/types/stockEvidence.ts:1`, `apps/dsa-web/src/types/stockEvidence.ts:23`, `apps/dsa-web/src/types/stockEvidence.ts:27`).
- Frontend stock intraday type and normalizer keep only `stockCode`, `stockName`, `interval`, `range`, `source`, and `data`; backend intraday provenance fields are dropped at this client boundary (`apps/dsa-web/src/api/stocks.ts:91`, `apps/dsa-web/src/api/stocks.ts:193`).
- The evidence-only quote adapter snapshot carries `source`, price/change/fundamental quote fields, and `market_timestamp`, but not source type, freshness, fallback/stale/partial/synthetic/unavailable flags, or `sourceConfidence` (`src/services/stock_evidence_quote_adapter.py:13`, `src/services/stock_evidence_quote_adapter.py:24`, `src/services/stock_evidence_quote_adapter.py:30`). `UnifiedRealtimeQuote` itself also lacks those first-class fields (`data_provider/realtime_types.py:111`, `data_provider/realtime_types.py:155`).

Conclusion: future work should not invent or infer authority. It should preserve fields already present at each boundary and make missing metadata explicit, fail-closed, and test-locked.

### 3. Official/authorized/scored vs observation-only distinction

Current DTOs and helpers already distinguish these concepts, but not uniformly across all single-stock API/client seams.

Backend separation that already exists:

- `single_stock_evidence_contract.py` always returns `diagnosticOnly=True`, `authorityGrant=False`, and `observationOnly=True` unless live/fresh reliability is proven and no cap reason exists (`src/services/single_stock_evidence_contract.py:314`, `src/services/single_stock_evidence_contract.py:316`, `src/services/single_stock_evidence_contract.py:317`, `src/services/single_stock_evidence_contract.py:318`).
- `stock_evidence_packet.py` separates `scoreEligibleEvidence` from `observationOnlyEvidence`; SEC filing evidence is explicitly observation-only/non-scoring (`src/services/stock_evidence_packet.py:406`, `src/services/stock_evidence_packet.py:430`, `src/services/stock_evidence_packet.py:456`, `src/services/stock_evidence_packet.py:473`).
- `fundamentalsSummary` is explicitly consumer-safe, no-advice, observation-only, non-scoring, and non-authority (`src/services/stock_evidence_packet.py:341`, `src/services/stock_evidence_packet.py:343`, `src/services/stock_evidence_packet.py:344`, `src/services/stock_evidence_packet.py:345`, `src/services/stock_evidence_packet.py:346`).
- `SourceConfidenceContract` and source-authority helpers define source types, score-grade trust levels, degraded source flags, and score-authority reason codes (`src/services/source_confidence_contract.py:18`, `src/services/source_confidence_contract.py:30`, `src/services/source_confidence_contract.py:62`, `src/services/source_confidence_contract.py:180`).
- Home research readiness grants source/score contribution only if all required domains are present and already marked authority/score-contributing (`src/services/analysis_service.py:953`, `src/services/analysis_service.py:958`, `src/services/analysis_service.py:968`, `src/services/analysis_service.py:969`).

Frontend distinction that already exists:

- `StockEvidenceFundamentalsSummary` types `notInvestmentAdvice`, `observationOnly`, `scoreContributionAllowed`, and `sourceAuthorityAllowed` (`apps/dsa-web/src/types/stockEvidence.ts:16`).
- The stock evidence API normalizer defaults `notInvestmentAdvice` and `observationOnly` to true unless explicitly false, while allowing score/source authority only when explicitly true (`apps/dsa-web/src/api/stockEvidence.ts:73`, `apps/dsa-web/src/api/stockEvidence.ts:75`, `apps/dsa-web/src/api/stockEvidence.ts:76`, `apps/dsa-web/src/api/stockEvidence.ts:77`, `apps/dsa-web/src/api/stockEvidence.ts:78`).
- Home fundamentals copy renders observation-only/no-advice copy and insufficient-data fallback instead of turning partial data into stable metrics (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2315`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2319`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2324`).

Conclusion: semantics exist. The future lock should standardize preservation; it should not change score authority, source authority, or advice boundaries.

### 4. Existing safe/fail-closed behavior and tests

Useful existing tests:

- `tests/test_single_stock_evidence_contract.py` covers fallback, missing freshness, stale/partial/synthetic/unavailable caps, sanitization, and import inertness (`tests/test_single_stock_evidence_contract.py:22`, `tests/test_single_stock_evidence_contract.py:105`, `tests/test_single_stock_evidence_contract.py:164`, `tests/test_single_stock_evidence_contract.py:225`, `tests/test_single_stock_evidence_contract.py:244`, `tests/test_single_stock_evidence_contract.py:285`).
- `tests/services/test_single_stock_evidence_packet.py` covers deterministic/pure packet projection, degraded unsupported fundamentals, no raw leakage, fallback/proxy downgrade, and no-advice fail-closed behavior (`tests/services/test_single_stock_evidence_packet.py:234`, `tests/services/test_single_stock_evidence_packet.py:288`, `tests/services/test_single_stock_evidence_packet.py:359`, `tests/services/test_single_stock_evidence_packet.py:423`, `tests/services/test_single_stock_evidence_packet.py:470`).
- `tests/services/test_analysis_research_readiness_projection.py` asserts Home response mirrors `singleStockEvidencePacket` across public payload locations and preserves ORCL/HK-like degraded cases without raw leakage (`tests/services/test_analysis_research_readiness_projection.py:273`, `tests/services/test_analysis_research_readiness_projection.py:502`, `tests/services/test_analysis_research_readiness_projection.py:551`, `tests/services/test_analysis_research_readiness_projection.py:679`).
- `tests/api/test_stock_evidence_api.py` locks dedicated `/evidence` endpoint serialization for `fundamentalsSummary`, missing-summary non-fabrication, forbidden field filtering, invalid symbol 404, and degraded unknown symbol payload (`tests/api/test_stock_evidence_api.py:57`, `tests/api/test_stock_evidence_api.py:109`, `tests/api/test_stock_evidence_api.py:127`, `tests/api/test_stock_evidence_api.py:182`, `tests/api/test_stock_evidence_api.py:208`).
- `apps/dsa-web/src/api/__tests__/stockEvidence.test.ts` locks frontend `stockEvidenceApi` safe-field preservation, absent summary behavior, and invalid summary dropping (`apps/dsa-web/src/api/__tests__/stockEvidence.test.ts:18`, `apps/dsa-web/src/api/__tests__/stockEvidence.test.ts:126`, `apps/dsa-web/src/api/__tests__/stockEvidence.test.ts:155`).
- `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx` covers current-stock-only evidence fetch, consumer-safe fundamentals copy, insufficient-data rendering, raw/internal copy suppression, and report evidence packet strip safety (`apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx:731`, `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx:755`, `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx:1763`).

Test gaps for the future lock:

- No dedicated test currently proves backend intraday provenance survives frontend `stocksApi.getIntraday()` normalization, because those fields are not typed or returned by the normalizer today (`apps/dsa-web/src/api/stocks.ts:91`, `apps/dsa-web/src/api/stocks.ts:193`).
- No single dedicated API test proves `/stocks/{code}/evidence` preserves a defined metadata subset for quote/technical/fundamental/news/SEC blocks after Pydantic model validation; those blocks are still opaque dictionaries (`api/v1/schemas/stocks.py:260`, `api/v1/schemas/stocks.py:267`).
- No dedicated adapter-boundary test proves `stock_evidence_quote_adapter.py` fails closed when quote freshness/source-confidence metadata is unavailable; current snapshot simply lacks that metadata (`src/services/stock_evidence_quote_adapter.py:13`).

## Smallest safe future write after T-1045/T-1046/T-1047

Future task:

**T-1053-M1 Minimal Home/analysis single-stock evidence consumed-subset DTO lock**

Goal:

- Lock the existing Home/analysis report single-stock evidence subset as additive, consumer-safe, and fail-closed.
- Preserve the current public report mirror locations for `researchReadiness`, `evidenceCoverageFrame`, `singleStockEvidencePacket`, `evidenceCitationFrame`, and `sourceProvenanceFrame`.
- Represent missing metadata explicitly as unavailable/unknown/observation-only instead of inferring live, official, authorized, or score-grade authority.
- Do this before touching `/stocks/{code}/evidence` item-block typing, `stock_evidence_quote_adapter.py`, or frontend display.

Recommended scope:

1. Add or tighten an inert Pydantic consumed-subset schema for Home/analysis evidence fields.
   - Prefer `api/v1/schemas/history.py` plus an optional small `api/v1/schemas/home_evidence.py`.
   - Use `extra="allow"` or equivalent compatibility so historical report payload keys are not dropped.
   - Keep current report mirror locations intact: top level, `meta`, and `details.analysis_result` where they already exist.

2. Add focused tests proving serialization preserves existing public keys and the new consumed subset.
   - Lock `evidenceCitationFrame` and `sourceProvenanceFrame` presence where the report path already produces them.
   - Assert no raw provider/admin/internal strings leak through consumer-facing report evidence fields.
   - Compare consumed subset invariants, not broad golden fixtures.

3. Defer adapter and frontend preservation to later separately scoped tasks.
   - The intraday frontend metadata loss is real, but it is not the first Home/report consumed-subset lock.
   - The dedicated `/stocks/{code}/evidence` opaque item typing is real, but it should not be mixed with the first Home/report schema lock.
   - `stock_evidence_quote_adapter.py` should remain untouched in T-1053-M1 because its current snapshot lacks freshness/source-confidence inputs and any provider-facing change risks scope expansion.

Allowed future write files:

- `api/v1/schemas/history.py`
- optional new file: `api/v1/schemas/home_evidence.py`
- `tests/api/test_analysis.py`
- `tests/services/test_analysis_research_readiness_projection.py`
- optional focused helper regression only if needed: `tests/services/test_home_source_provenance_sidecar.py`

Forbidden future write files/domains for T-1053-M1:

- `data_provider/**`
- `src/core/pipeline.py`
- `src/analyzer.py`
- `src/services/analysis_service.py`
- `src/services/stock_service.py`
- `src/services/agent_stock_evidence_service.py`
- `src/services/stock_evidence_quote_adapter.py`
- `src/services/single_stock_evidence_contract.py`
- `src/services/stock_evidence_packet.py`
- `src/services/single_stock_*.py`
- `api/v1/endpoints/stocks.py`
- `api/v1/schemas/stocks.py`
- `apps/**`
- `src/services/analysis_provider_planner.py`
- `src/services/provider_plan_advisor.py`
- `src/services/provider_capability_matrix.py`
- `src/services/data_source_router.py`
- `src/services/market_cache.py`
- scanner service/schema/frontend ranking surfaces
- portfolio/accounting/FX/holdings files
- options/backtest engine, gates, payoff, or ranking files
- root config, CI, package, lockfile, dependency files
- broad frontend Home page redesign or copy rewrite

Forbidden semantic changes:

- no provider additions;
- no provider order, live-call path, retry, timeout, fallback, cache, TTL, SWR, or MarketCache behavior changes;
- no source-authority or score-contribution promotion;
- no scanner scoring/ranking/filtering/selection changes;
- no single-stock scoring math, advice, recommendation, or valuation-judgment copy changes;
- no portfolio/accounting/FX/holdings changes;
- no options/backtest calculations, gates, ranking, or stored semantics changes;
- no API field removal, hidden response filtering, or report payload key dropping;
- no UI redesign.

Focused validation plan for T-1053-M1:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python3 -m pytest -q tests/api/test_analysis.py tests/services/test_analysis_research_readiness_projection.py -p no:cacheprovider
/Users/yehengli/daily_stock_analysis/.venv/bin/python3 -m py_compile api/v1/schemas/history.py
# If api/v1/schemas/home_evidence.py is created, include it in py_compile.
git diff --check
./scripts/release_secret_scan.sh
```

If a later separate frontend/client metadata-preservation task is opened, use these focused frontend tests then, not in T-1053-M1:

```bash
npm --prefix apps/dsa-web run test -- src/api/__tests__/stockEvidence.test.ts src/api/__tests__/stocks.test.ts --run
npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx --run
```

## Explicit rejections

This audit explicitly rejects these as T-1053 follow-ups:

- broad provider sweep;
- new source integrations;
- new live provider calls;
- provider priority/routing/fallback/cache changes;
- score, ranking, scanner, filter, shortlist, or selection math changes;
- frontend redesign;
- consumer copy that implies advice, trading action, or valuation judgment;
- portfolio/accounting/FX/holdings changes;
- options/backtest engine changes.

## Final audit decision

Proceed with one narrow Home/analysis report consumed-subset contract lock only after upstream T-1045/T-1046/T-1047 decisions are stable enough to reuse their source-confidence/provider/readiness vocabulary.

Do not implement a provider-backed single-stock adapter now. Do not touch `stock_evidence_quote_adapter.py` in the first future write. The current evidence path is adequate for a report/schema readiness lock, not for a provider/runtime expansion.

## Final diff confirmation for this audit

- This T-1053 task is report-only.
- No source code changed.
- No tests changed.
- No config/package/lockfile changes.
- No provider additions.
- No provider/cache/runtime/network/API/frontend behavior changes.
- No scanner scoring/ranking/filtering changes.
- No portfolio/accounting/FX/holdings changes.
- No options/backtest changes.
