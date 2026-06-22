# T-1056 Stocks Evidence Endpoint Metadata Readiness Audit

Task ID: T-1056-AUDIT

Task title: Stocks evidence endpoint metadata readiness audit

Mode: READ-ONLY-AUDIT with explicitly authorized docs-only audit artifact

Allowed artifact:

`docs/codex/audits/T-1056-stocks-evidence-endpoint-metadata-readiness-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1056-stocks-evidence-endpoint-metadata-audit`
- branch: `codex/t1056-stocks-evidence-endpoint-metadata-audit`
- base commit inspected before writing this report: `e82103d7`
- branch state after `git fetch origin`: selected branch at `origin/main`; no merge/rebase/branch switch was performed.

Scope boundary:

- Source, tests, config, package, lockfile, provider, cache, runtime, API behavior, frontend behavior, scanner, portfolio, options, and backtest files were inspected only.
- This audit does not implement endpoint, schema, service, provider, cache, runtime, API, frontend, scoring, ranking, filtering, options, backtest, or portfolio changes.
- Final diff is limited to this Markdown report.

## Readiness verdict

The dedicated stock evidence endpoint exists and is mature enough for exactly one narrow future write:

**T-1056-M1: Minimal `/api/v1/stocks/{stock_code}/evidence` item metadata response schema lock.**

This should be an endpoint response schema and API test lock only. It should not change `StockEvidenceService`, `stock_evidence_packet`, provider adapters, quote runtime, cache behavior, or frontend behavior.

Recommendation category: **endpoint schema lock**, not service projection lock, not full deferral.

Why this is safe:

- The route already exists as `GET /api/v1/stocks/{stock_code}/evidence` and returns `StockEvidenceResponse` through Pydantic validation (`api/v1/endpoints/stocks.py:284`, `api/v1/endpoints/stocks.py:296`, `api/v1/endpoints/stocks.py:315`).
- The service already emits stable item slots: `quote`, `technical`, `fundamental`, `news`, optional `secFilingEvidence`, and attached `stockEvidencePacket` (`src/services/agent_stock_evidence_service.py:382`, `src/services/agent_stock_evidence_service.py:391`, `src/services/agent_stock_evidence_service.py:365`).
- T-1054 has already locked Home/analysis consumed sidecars separately through `api/v1/schemas/home_evidence.py` and history/report hydration (`api/v1/schemas/home_evidence.py:122`, `api/v1/schemas/history.py:260`, `api/v1/schemas/history.py:274`).
- Current `/evidence` schema already strongly locks `fundamentalsSummary` and leaves the remaining item blocks compatible as opaque dictionaries (`api/v1/schemas/stocks.py:221`, `api/v1/schemas/stocks.py:248`, `api/v1/schemas/stocks.py:260`).

Why this must not be a service projection lock yet:

- The evidence quote adapter snapshot does not carry `sourceType`, `freshness`, fallback/stale/partial/synthetic/unavailable flags, or `sourceConfidence`; it only carries source, quote values, valuation quote fields, and market timestamp (`src/services/stock_evidence_quote_adapter.py:13`).
- The evidence service `_quote()` therefore cannot honestly emit source-confidence metadata today without either inventing authority or touching provider/runtime boundaries (`src/services/agent_stock_evidence_service.py:396`).
- The packet projector already blocks live-price claims when freshness metadata is absent (`src/services/stock_evidence_packet.py:486`, `src/services/stock_evidence_packet.py:509`).

## Audit questions and answers

### 1. Does a dedicated endpoint exist and what does it return?

Yes. The dedicated endpoint is:

`GET /api/v1/stocks/{stock_code}/evidence`

Observed behavior:

- The route is declared before quote/history routes and uses `response_model=StockEvidenceResponse` with `response_model_exclude_none=True` (`api/v1/endpoints/stocks.py:284`, `api/v1/endpoints/stocks.py:286`, `api/v1/endpoints/stocks.py:287`).
- It instantiates `StockEvidenceService`, replaces the quote seam with `_ReadOnlyEvidenceFetcherManager`, calls `get_stock_evidence([stock_code])`, returns 404 if no items exist, and model-validates the payload (`api/v1/endpoints/stocks.py:296`, `api/v1/endpoints/stocks.py:298`, `api/v1/endpoints/stocks.py:300`, `api/v1/endpoints/stocks.py:303`, `api/v1/endpoints/stocks.py:315`).
- `_ReadOnlyEvidenceFetcherManager.get_realtime_quote()` always returns `None`, so the API route itself does not trigger live quote provider access (`api/v1/endpoints/stocks.py:52`).
- `StockEvidenceService.get_stock_evidence()` normalizes up to three symbols, emits `symbols`, `items`, and `meta`, then attaches `stockEvidencePacket` per item (`src/services/agent_stock_evidence_service.py:328`, `src/services/agent_stock_evidence_service.py:342`, `src/services/agent_stock_evidence_service.py:351`, `src/services/agent_stock_evidence_service.py:356`).
- Each item currently contains `symbol`, `market`, `quote`, `technical`, `fundamental`, `news`, optional `secFilingEvidence`, and attached `stockEvidencePacket` (`src/services/agent_stock_evidence_service.py:382`, `src/services/agent_stock_evidence_service.py:389`, `src/services/agent_stock_evidence_service.py:391`, `src/services/agent_stock_evidence_service.py:393`).

Frontend equivalent:

- `stockEvidenceApi.getStockEvidence(stockCode)` calls `/api/v1/stocks/${encodeURIComponent(stockCode)}/evidence` and normalizes the response (`apps/dsa-web/src/api/stockEvidence.ts:163`, `apps/dsa-web/src/api/stockEvidence.ts:166`, `apps/dsa-web/src/api/stockEvidence.ts:168`).
- Home calls this adapter for the active evidence ticker and currently reads `matchedItem?.stockEvidencePacket?.fundamentalsSummary` (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5210`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5217`).

### 2. Where does opaque item metadata exist or get stripped?

Current strong metadata elsewhere:

- Quote schema exposes `source`, `sourceType`, `marketTimestamp`, `observedAt`, `freshness`, `isFallback`, `isStale`, `isPartial`, `isSynthetic`, and `sourceConfidence` (`api/v1/schemas/stocks.py:61`, `api/v1/schemas/stocks.py:70`).
- Intraday schema exposes `sourceType`, `freshness`, fallback/stale/partial/synthetic/unavailable flags, and `sourceConfidence` (`api/v1/schemas/stocks.py:201`, `api/v1/schemas/stocks.py:210`).
- History schema exposes `source`, `diagnostics`, and `sourceConfidence`, but not first-class top-level freshness/fallback/stale/partial flags (`api/v1/schemas/stocks.py:117`, `api/v1/schemas/stocks.py:144`).
- `StockService` builds source-confidence metadata for quote, history, and intraday paths (`src/services/stock_service.py:133`, `src/services/stock_service.py:662`, `src/services/stock_service.py:710`, `src/services/stock_service.py:776`).

Current dedicated `/evidence` preservation and loss points:

- `StockEvidenceItemResponse` keeps `quote`, `technical`, `fundamental`, `news`, and `secFilingEvidence` as `Dict[str, Any]`, so endpoint validation preserves them opaquely but does not lock field shape (`api/v1/schemas/stocks.py:260`, `api/v1/schemas/stocks.py:267`).
- `StockEvidencePacketResponse` has `extra="allow"` and strongly types only `fundamentalsSummary`; all other packet keys remain pass-through (`api/v1/schemas/stocks.py:248`, `api/v1/schemas/stocks.py:251`, `api/v1/schemas/stocks.py:253`).
- The frontend `StockEvidenceItem` mirrors the backend opacity with `Record<string, unknown>` for item blocks (`apps/dsa-web/src/types/stockEvidence.ts:23`, `apps/dsa-web/src/types/stockEvidence.ts:27`).
- The frontend normalizer preserves opaque item blocks only when they are objects and whitelists only `fundamentalsSummary` fields (`apps/dsa-web/src/api/stockEvidence.ts:41`, `apps/dsa-web/src/api/stockEvidence.ts:99`, `apps/dsa-web/src/api/stockEvidence.ts:119`).

Service projection details:

- Evidence `_quote()` currently emits `status`, price/change/currency, `provider`, `updatedAt`, and optional quote-derived fundamental values, but not freshness/source-confidence flags (`src/services/agent_stock_evidence_service.py:403`, `src/services/agent_stock_evidence_service.py:411`).
- `_technical()` emits deterministic technical fields plus `provider` and `updatedAt`, and can mark `partial` when required technical fields are missing (`src/services/agent_stock_evidence_service.py:421`, `src/services/agent_stock_evidence_service.py:444`, `src/services/agent_stock_evidence_service.py:457`).
- `_fundamental()` emits history-derived or quote-derived fundamentals, `provider`, `updatedAt`, `missingFields`, and `status` (`src/services/agent_stock_evidence_service.py:461`, `src/services/agent_stock_evidence_service.py:489`, `src/services/agent_stock_evidence_service.py:547`).
- SEC filing evidence has richer source metadata and observation-only flags when injected and accepted (`src/services/agent_stock_evidence_service.py:211`, `src/services/agent_stock_evidence_service.py:217`, `src/services/agent_stock_evidence_service.py:219`).
- The packet projector builds `sourceRefs`, `requiredEvidence`, `scoreEligibleEvidence`, `observationOnlyEvidence`, `claimBoundaries`, and consumer-safe `fundamentalsSummary` from the item blocks (`src/services/stock_evidence_packet.py:152`, `src/services/stock_evidence_packet.py:430`, `src/services/stock_evidence_packet.py:456`, `src/services/stock_evidence_packet.py:473`, `src/services/stock_evidence_packet.py:502`, `src/services/stock_evidence_packet.py:317`).

Conclusion: metadata is not primarily stripped by Pydantic today; it is mostly not projected into the dedicated evidence item blocks yet. The safe lock is to type and preserve an optional metadata subset when present, not to add or infer new metadata.

### 3. Do current tests cover source/freshness/fallback/stale/partial metadata?

Covered today:

- `/stocks/{code}/evidence` endpoint tests lock `fundamentalsSummary` serialization, no-fabrication when absent, forbidden `fundamentalsSummary` field filtering, invalid-symbol 404, and degraded unknown-symbol payload preservation (`tests/api/test_stock_evidence_api.py:57`, `tests/api/test_stock_evidence_api.py:109`, `tests/api/test_stock_evidence_api.py:127`, `tests/api/test_stock_evidence_api.py:182`, `tests/api/test_stock_evidence_api.py:208`).
- Service tests lock base evidence fields, packet attachment, consumer-safe fundamentals summary, SEC sidecar observation-only behavior, and no raw SEC payload leakage (`tests/test_agent_stock_evidence_service.py:35`, `tests/test_agent_stock_evidence_service.py:83`, `tests/test_agent_stock_evidence_service.py:153`, `tests/test_agent_stock_evidence_service.py:201`).
- Service/runtime tests prove evidence quote provider source is preserved, fallback quotes are not score-eligible, unavailable quotes stay unknown, and packet live-claim boundaries stay blocked without freshness metadata (`tests/test_agent_stock_evidence_service.py:372`, `tests/test_provider_runtime_contracts.py:616`, `tests/test_provider_runtime_contracts.py:725`, `tests/test_provider_runtime_contracts.py:764`).
- Pure single-stock metadata contract tests cover fallback, missing freshness, stale/partial, synthetic/unavailable, sanitization, and inert import behavior (`tests/test_single_stock_evidence_contract.py:22`, `tests/test_single_stock_evidence_contract.py:105`, `tests/test_single_stock_evidence_contract.py:127`, `tests/test_single_stock_evidence_contract.py:179`, `tests/test_single_stock_evidence_contract.py:244`, `tests/test_single_stock_evidence_contract.py:285`).
- Quote and intraday endpoint tests cover source/freshness metadata outside `/evidence` (`tests/test_stock_api_freshness_contract.py:16`, `tests/test_stock_api_freshness_contract.py:139`).
- Frontend `stockEvidenceApi` tests lock `fundamentalsSummary` whitelisting, absent-summary behavior, invalid-summary dropping, and encoded endpoint calls (`apps/dsa-web/src/api/__tests__/stockEvidence.test.ts:18`, `apps/dsa-web/src/api/__tests__/stockEvidence.test.ts:126`, `apps/dsa-web/src/api/__tests__/stockEvidence.test.ts:155`).
- T-1054 Home/analysis tests lock consumed sidecars and additive metadata preservation across report/meta/details mirrors (`tests/services/test_analysis_research_readiness_projection.py:132`, `tests/api/test_analysis.py:307`, `tests/services/test_analysis_research_readiness_projection.py:1301`).

Not covered yet:

- No dedicated `/stocks/{code}/evidence` API test locks an optional metadata subset across `quote`, `technical`, `fundamental`, `news`, and `secFilingEvidence` after `StockEvidenceResponse.model_validate(...)`.
- No dedicated `/evidence` schema test proves that optional `freshness`, `sourceType`, fallback/stale/partial/synthetic/unavailable flags, and `sourceConfidence` pass through when supplied by the service.
- No dedicated `/evidence` schema test proves those fields remain absent rather than fabricated when the service omits them.
- No frontend `stockEvidence` test locks typed item metadata; current client code intentionally treats item blocks as opaque records.

### 4. Should the future write be endpoint schema lock, service projection lock, or deferral?

Future write should be: **endpoint schema lock**.

Smallest safe implementation shape for T-1056-M1:

1. In `api/v1/schemas/stocks.py`, replace the opaque item block `Dict[str, Any]` annotations with small Pydantic response submodels using `extra="allow"` and `populate_by_name=True`.
2. Keep all metadata fields optional. Candidate optional fields:
   - shared: `status`, `provider`, `providerId`, `providerName`, `source`, `sourceType`, `sourceTier`, `trustLevel`, `freshness`, `updatedAt`, `asOf`, `degradationReason`;
   - flags: `isFallback`, `isStale`, `isPartial`, `isSynthetic`, `isUnavailable`;
   - confidence: `sourceConfidence`;
   - authority: `observationOnly`, `scoreContributionAllowed`, `sourceAuthorityAllowed`, `rawPayloadStored`;
   - domain specifics: `missingFields`, `freshnessExpectation`, `records`.
3. Keep `fundamentalsSummary` filtering exactly as-is.
4. Add focused fake-service endpoint tests in `tests/api/test_stock_evidence_api.py` proving:
   - typed optional metadata is preserved when supplied;
   - missing metadata is not fabricated;
   - fallback/stale/partial/synthetic/unavailable/source-confidence flags survive model validation;
   - SEC observation-only metadata survives model validation;
   - `fundamentalsSummary` still filters forbidden fields.

Explicit non-goals for T-1056-M1:

- Do not add new metadata to `StockEvidenceService`.
- Do not infer freshness/source-confidence fields from `updatedAt`, provider name, quote source, or market timestamp.
- Do not make optional metadata required.
- Do not filter all opaque extra fields outside the existing `fundamentalsSummary` whitelist because that would be a behavior change.
- Do not touch frontend types or display; Home currently consumes only `stockEvidencePacket.fundamentalsSummary` from this endpoint.

Service projection lock remains deferred. Prerequisites for any later service projection write:

- a provider/runtime-safe source-confidence input at the evidence quote adapter seam;
- tests proving no additional provider calls, no provider order change, no cache/TTL/SWR change, and no fabricated live/fresh claims;
- explicit allowed files for `StockEvidenceQuoteAdapter`/`StockEvidenceService` if and only if that later task is scoped.

### 5. Exact future allowed and forbidden files

Recommended future write:

**T-1056-M1 Minimal `/stocks/{code}/evidence` item metadata response schema lock**

Allowed files for T-1056-M1:

- `api/v1/schemas/stocks.py`
- `tests/api/test_stock_evidence_api.py`

Forbidden files for T-1056-M1:

- `api/v1/endpoints/stocks.py`
- `api/v1/schemas/history.py`
- `api/v1/schemas/home_evidence.py`
- `src/services/agent_stock_evidence_service.py`
- `src/services/stock_evidence_packet.py`
- `src/services/stock_evidence_quote_adapter.py`
- `src/services/single_stock_evidence_contract.py`
- `src/services/source_confidence_contract.py`
- `src/services/stock_service.py`
- `src/services/analysis_service.py`
- `src/services/analysis_provider_planner.py`
- `src/services/provider_plan_advisor.py`
- `src/services/provider_capability_matrix.py`
- `src/services/data_source_router.py`
- `src/services/market_cache.py`
- `data_provider/**`
- `api/v1/endpoints/analysis.py`
- `apps/**`
- `tests/**` except `tests/api/test_stock_evidence_api.py`
- root config, CI, package, lockfile, dependency, env, Docker, and script files
- scanner, rotation, portfolio, options, backtest, auth, notification, provider/cache/runtime files

Forbidden semantic changes for T-1056-M1:

- no endpoint route behavior changes;
- no service projection changes;
- no provider additions;
- no provider order, live-call path, retry, timeout, fallback, cache, TTL, SWR, or MarketCache behavior changes;
- no source-authority or score-contribution promotion;
- no fabricated freshness, fallback, stale, partial, synthetic, unavailable, or source-confidence metadata;
- no scanner scoring/ranking/filtering/selection changes;
- no options/backtest/portfolio behavior changes;
- no frontend redesign, copy change, data-fetching change, or client behavior change;
- no API field removal or hidden response filtering outside the existing `fundamentalsSummary` whitelist.

Focused validation plan for T-1056-M1:

```bash
/Users/yehengli/daily_stock_analysis/.venv/bin/python3 -m pytest -q tests/api/test_stock_evidence_api.py -p no:cacheprovider
/Users/yehengli/daily_stock_analysis/.venv/bin/python3 -m py_compile api/v1/schemas/stocks.py
git diff --check -- api/v1/schemas/stocks.py tests/api/test_stock_evidence_api.py
./scripts/release_secret_scan.sh
```

No frontend validation is recommended for T-1056-M1 because `apps/**` is forbidden and the current frontend endpoint consumer remains intentionally opaque outside `fundamentalsSummary`.

## Explicit rejections

This audit explicitly rejects these as the next write:

- service projection lock for quote freshness/source-confidence metadata;
- `StockEvidenceQuoteAdapter` expansion;
- provider/runtime metadata expansion;
- frontend typed item-block metadata lock;
- broad raw-field filtering across opaque evidence item blocks;
- Home/analysis sidecar relock;
- scanner, ranking, scoring, options, backtest, or portfolio changes.

## Final audit decision

Proceed with one narrow backend endpoint schema/test lock:

**T-1056-M1 Minimal `/stocks/{code}/evidence` item metadata response schema lock.**

The endpoint is ready for a compatibility-preserving Pydantic metadata lock because it already validates through `StockEvidenceResponse` and tests can use fake-service payloads to prove preservation/no-fabrication. It is not ready for a service projection metadata lock because the evidence service does not currently receive enough authoritative metadata to emit source-confidence fields without expanding provider/runtime seams.

## Final diff confirmation for this audit

- This T-1056 task is report-only.
- No source code changed.
- No tests changed.
- No config/package/lockfile changes.
- No provider additions.
- No provider/cache/runtime/network/API/frontend behavior changes.
- No scanner scoring/ranking/filtering changes.
- No portfolio/accounting/FX/holdings changes.
- No options/backtest changes.
