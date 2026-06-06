# T-1077 Single-stock Evidence Consumer Metadata Readiness Audit

Task ID: T-1077-AUDIT

Task title: Single-stock evidence consumer metadata readiness audit

Mode: READ-ONLY-AUDIT with explicitly authorized docs-only audit artifact, commit, and push.

Allowed artifact:

`docs/codex/audits/T-1077-single-stock-evidence-consumer-metadata-readiness-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1077-single-stock-evidence-consumer-readiness-audit`
- branch: `codex/t1077-single-stock-evidence-consumer-readiness-audit`
- pre-write HEAD inspected: `117fe4c5`
- `origin/main` after fetch: `6882347d`
- `git status --short --branch` after fetch later reported the task branch behind `origin/main` by 2; no merge/rebase was performed because this task must stay on the selected branch.

Scope boundary:

- Source, tests, config, package, lockfile, provider, cache, runtime, API behavior, frontend behavior, scanner, portfolio, options, and backtest files were inspected only.
- This audit does not implement metadata badges, frontend placeholders, adapter/type changes, provider capability adoption, service metadata expansion, endpoint behavior changes, raw metadata UI, scanner/portfolio/options/backtest changes, or provider/cache/runtime behavior changes.
- Final diff is limited to this Markdown report.

## Readiness verdict

Frontend consumption is **not ready for visible source/freshness/fallback/stale/partial badges**.

The backend endpoint metadata transport is ready enough to preserve item metadata: `/api/v1/stocks/{stock_code}/evidence` validates through `StockEvidenceResponse`, uses metadata-capable item blocks, and current tests lock OpenAPI metadata keys plus endpoint preservation (`api/v1/endpoints/stocks.py:284`, `api/v1/endpoints/stocks.py:315`, `api/v1/schemas/stocks.py:260`, `tests/api/test_stock_evidence_api.py:128`, `tests/api/test_stock_evidence_api.py:171`).

The frontend consumption boundary is only partially ready. `stockEvidenceApi` preserves item blocks as opaque records, but the only real UI consumer, Home, reads only `matchedItem?.stockEvidencePacket?.fundamentalsSummary` and never consumes item-level `quote`/`technical`/`fundamental`/`news`/`secFilingEvidence` metadata for UI decisions (`apps/dsa-web/src/api/stockEvidence.ts:99`, `apps/dsa-web/src/api/stockEvidence.ts:119`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5271`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5278`).

Recommended next write:

**T-1077-M1: Frontend stock evidence adapter item-metadata preservation test lock.**

This should be tests-only. It should prove the current frontend adapter preserves item-level metadata as opaque data while the consumer-safe `fundamentalsSummary` whitelist still drops raw/internal/provider/advice fields. It must not add visible UI, badges, placeholders, source-authority inference, provider capability fields, API changes, source changes, or Home behavior changes.

## Audit questions and answers

### 1. Which metadata is serialized today

Response shape:

- The route is `GET /api/v1/stocks/{stock_code}/evidence`, with `response_model=StockEvidenceResponse` and `response_model_exclude_none=True` (`api/v1/endpoints/stocks.py:284`, `api/v1/endpoints/stocks.py:286`, `api/v1/endpoints/stocks.py:287`).
- The endpoint installs `_ReadOnlyEvidenceFetcherManager` before calling `StockEvidenceService`, then returns `StockEvidenceResponse.model_validate(payload)` (`api/v1/endpoints/stocks.py:52`, `api/v1/endpoints/stocks.py:296`, `api/v1/endpoints/stocks.py:303`, `api/v1/endpoints/stocks.py:315`).
- `StockEvidenceResponse` exposes `symbols`, `items`, and `meta`; `meta` defines `generatedAt` and `source` (`api/v1/schemas/stocks.py:321`, `api/v1/schemas/stocks.py:330`).

Item metadata schema:

- `quote`, `technical`, `fundamental`, `news`, and `secFilingEvidence` share `StockEvidenceItemMetadataDict` (`api/v1/schemas/stocks.py:298`, `api/v1/schemas/stocks.py:305`, `api/v1/schemas/stocks.py:309`).
- The metadata schema allows additional properties and names optional keys including `status`, `provider`, `providerId`, `providerName`, `source`, `sourceType`, `sourceTier`, `trustLevel`, `freshness`, `updatedAt`, `asOf`, `degradationReason`, `isFallback`, `isStale`, `isPartial`, `isSynthetic`, `isUnavailable`, `sourceConfidence`, `observationOnly`, `scoreContributionAllowed`, `sourceAuthorityAllowed`, `rawPayloadStored`, `missingFields`, `freshnessExpectation`, and `records` (`api/v1/schemas/stocks.py:260`, `api/v1/schemas/stocks.py:263`, `api/v1/schemas/stocks.py:288`).
- OpenAPI and endpoint tests lock that metadata schema and preservation behavior (`tests/api/test_stock_evidence_api.py:128`, `tests/api/test_stock_evidence_api.py:141`, `tests/api/test_stock_evidence_api.py:171`, `tests/api/test_stock_evidence_api.py:243`, `tests/api/test_stock_evidence_api.py:247`).

Actual quote diagnostic metadata:

- `build_quote_diagnostic_source_metadata()` emits `source`, `sourceType`, `freshness`, `asOf`, `degradationReason`, `isFallback`, `isStale`, `isPartial`, `isSynthetic`, `isUnavailable`, `observationOnly`, `scoreContributionAllowed`, `sourceAuthorityAllowed`, `rawPayloadStored`, and nested `sourceConfidence` (`src/services/stock_evidence_quote_adapter.py:58`, `src/services/stock_evidence_quote_adapter.py:89`, `src/services/stock_evidence_quote_adapter.py:104`).
- The quote projection merges that metadata into the public `quote` item; missing/error quote paths emit unavailable diagnostic metadata instead of live/provider authority (`src/services/agent_stock_evidence_service.py:399`, `src/services/agent_stock_evidence_service.py:407`, `src/services/agent_stock_evidence_service.py:417`, `src/services/agent_stock_evidence_service.py:423`, `src/services/agent_stock_evidence_service.py:430`).
- Current service/API tests assert quote diagnostics are present and remain observation-only, non-scoring, and non-authoritative (`tests/test_agent_stock_evidence_service.py:492`, `tests/test_agent_stock_evidence_service.py:518`, `tests/test_agent_stock_evidence_service.py:535`, `tests/api/test_stock_evidence_api.py:402`, `tests/api/test_stock_evidence_api.py:481`).

Fundamentals summary:

- `stockEvidencePacket.fundamentalsSummary` is a separate consumer-safe whitelist projection, not an arbitrary metadata dump (`api/v1/schemas/stocks.py:221`, `api/v1/schemas/stocks.py:248`, `api/v1/schemas/stocks.py:253`).
- It allows metric fields, `period`, `source`, `freshness`, `missingFields`, `notInvestmentAdvice`, `observationOnly`, `scoreContributionAllowed`, and `sourceAuthorityAllowed` (`api/v1/schemas/stocks.py:226`, `api/v1/schemas/stocks.py:245`).

### 2. Which frontend adapter/types preserve or drop it

Preserved:

- `StockEvidenceItem.quote`, `technical`, `fundamental`, `news`, and `secFilingEvidence` are typed as `Record<string, unknown> | null`, so item metadata remains opaque rather than named (`apps/dsa-web/src/types/stockEvidence.ts:27`, `apps/dsa-web/src/types/stockEvidence.ts:34`).
- `normalizeOpaqueObject()` returns object payloads unchanged, and `normalizeStockEvidenceItem()` applies that to each item block (`apps/dsa-web/src/api/stockEvidence.ts:99`, `apps/dsa-web/src/api/stockEvidence.ts:127`, `apps/dsa-web/src/api/stockEvidence.ts:131`).
- `normalizeStockEvidencePacket()` preserves unknown packet fields through `...rest`, while normalizing only `fundamentalsSummary` (`apps/dsa-web/src/api/stockEvidence.ts:106`, `apps/dsa-web/src/api/stockEvidence.ts:111`, `apps/dsa-web/src/api/stockEvidence.ts:115`).

Dropped or whitelisted:

- `normalizeFundamentalsSummary()` intentionally whitelists consumer-safe fields and drops raw/admin/provider/advice/status fields inside the summary (`apps/dsa-web/src/api/stockEvidence.ts:41`, `apps/dsa-web/src/api/stockEvidence.ts:46`, `apps/dsa-web/src/api/stockEvidence.ts:73`, `apps/dsa-web/src/api/stockEvidence.ts:96`).
- Existing adapter tests lock the summary whitelist and forbidden-field drop, but they do not yet lock item-level metadata preservation with a fixture containing quote degraded flags or `sourceConfidence` (`apps/dsa-web/src/api/__tests__/stockEvidence.test.ts:18`, `apps/dsa-web/src/api/__tests__/stockEvidence.test.ts:107`, `apps/dsa-web/src/api/__tests__/stockEvidence.test.ts:126`, `apps/dsa-web/src/api/__tests__/stockEvidence.test.ts:155`).

### 3. Which UI route currently consumes single-stock evidence

Only Home consumes this endpoint in application source:

- `stockEvidenceApi.getStockEvidence(stockCode)` calls `/api/v1/stocks/${encodeURIComponent(stockCode)}/evidence` (`apps/dsa-web/src/api/stockEvidence.ts:163`, `apps/dsa-web/src/api/stockEvidence.ts:166`).
- Search found the only application source call in `HomeBentoDashboardPage.tsx` (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5271`).
- Home chooses a matching item and stores only `matchedItem?.stockEvidencePacket?.fundamentalsSummary` (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5276`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5278`).
- That summary is rendered through `LinearObservationPanel` and `HomeFundamentalsSummaryBlock`, not through an item metadata badge component (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2332`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5887`).

Adjacent but distinct:

- Home also renders report-derived `singleStockEvidencePacket`, `evidenceCitationFrame`, and `sourceProvenanceFrame`, but those come from analysis reports rather than the `/stocks/{code}/evidence` item metadata (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5201`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5205`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5209`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:6024`).
- `HomeSourceProvenanceStrip` already shows source/freshness/observe-only/fallback counts from report sidecars, so endpoint item badges would duplicate an existing trust surface unless first compressed into the same vocabulary (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:1299`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:1379`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:1412`).

### 4. Whether badges would be understandable or noisy

Understandable if mapped:

- Home already has consumer-safe source labels such as disclosure/market/fundamentals digest, and consumer-safe freshness labels such as recent update, partial refresh, supplemental snapshot, and earlier snapshot (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2643`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2653`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2671`).
- The current fundamentals summary already uses compact state/period/freshness/missing-count chips and observation-only/no-advice copy (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2351`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2357`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2392`).

Noisy if implemented now:

- The endpoint default route is intentionally read-only and fail-closed for quote fetches, so quote metadata can become `unavailable` by default rather than a meaningful provider-quality badge (`api/v1/endpoints/stocks.py:52`, `api/v1/endpoints/stocks.py:299`).
- Home already has a report-side provenance strip with authority/freshness/observe-only/fallback/awaiting-verification counts (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:1408`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:1412`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:1416`).
- Home tests explicitly prevent raw/internal/provider/source-confidence terminology from leaking in the fundamentals and provenance areas (`apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx:751`, `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx:752`, `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx:1863`, `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx:1870`).

Conclusion: source/freshness/fallback/stale/partial concepts can be understandable only after they are reduced to one consumer-safe status vocabulary. A raw item-level badge layer would be noisy today.

### 5. Safe default, disclosure-only, and hidden fields

Safe to display by default:

- Fundamentals metrics, `period`, mapped `source`, mapped `freshness`, `missingFields` count, and no-advice/observation-only copy from `fundamentalsSummary`.
- Existing safe labels include `仅供观察`, `不构成投资建议`, `部分更新`, `补充快照`, `较早快照`, and `数据不足`, not raw schema keys (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2357`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2363`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2365`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2659`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2668`).

Disclosure-only after mapping:

- `asOf` and `updatedAt`, because they help explain timing but do not prove live/fresh authority.
- `isFallback`, `isStale`, `isPartial`, and `isUnavailable`, but only as one collapsed status line or domain-level count, not four separate raw badges.
- `missingFields` details, if surfaced behind an existing details/drawer pattern.

Must remain hidden in consumer UI:

- `provider`, `providerId`, `providerName`, raw `source`, `sourceType`, `sourceTier`, `trustLevel`, `freshnessExpectation`, `readinessState`, and `authorityGrant`.
- `sourceConfidence` and nested `capReason`, `degradationReason`, `confidenceWeight`, `coverage`, `sourceLabel`, or raw source strings.
- `scoreContributionAllowed`, `sourceAuthorityAllowed`, `rawPayloadStored`, raw `records`, provider/admin/debug/cache/router/schema/internal keys, and any buy/sell/valuation/trading advice wording.

Rationale:

- Quote tests explicitly reject deferred provider/readiness keys in quote diagnostics (`tests/api/test_stock_evidence_api.py:487`, `tests/test_agent_stock_evidence_service.py:555`).
- Existing frontend tests already block raw summary and provenance leakage (`apps/dsa-web/src/api/__tests__/stockEvidence.test.ts:107`, `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx:751`, `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx:1870`).
- T-1061 still defers real provider capability/source-authority adoption, so frontend must not infer authority from preserved transport fields.

### 6. Which prerequisite should come first

Choose **tests-only adapter lock** first.

Why not visible placeholder first:

- Home does not consume item-level metadata today, so a placeholder would add UI area before there is a typed consumer contract (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5276`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5278`).
- Any visible placeholder near source/freshness would risk duplicating the existing report-derived provenance strip (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:1379`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:1416`).

Why not docs-only IA spec first:

- A docs IA spec is useful later, but the current adapter behavior is not yet frontend-test-locked for item metadata. A small test lock gives the next IA task a stable input boundary without changing behavior.

Why tests-only is safe:

- It can stay inside `apps/dsa-web/src/api/__tests__/stockEvidence.test.ts`.
- It can prove item-level quote/technical/fundamental/news/SEC metadata survives normalization as opaque records.
- It can simultaneously prove `fundamentalsSummary` still drops raw/internal/provider/advice fields.
- It does not expose metadata, create badges, add source authority, or alter runtime/API/frontend behavior.

## Consumer matrix

| Consumer surface | Reads `/stocks/{code}/evidence` | Preserves item metadata | Displays item metadata | Current safe display | Readiness |
| --- | --- | --- | --- | --- | --- |
| Backend endpoint | Yes | Yes, via metadata-capable item blocks | No UI | Transport only, fail-closed quote seam | Ready for preservation, not authority |
| Frontend adapter | Yes | Yes, opaque `Record<string, unknown>` blocks | No | `fundamentalsSummary` whitelist only | Needs tests-only item metadata lock |
| Home fundamentals summary | Indirectly via adapter | No item-level use | No | Metrics, period, mapped source/freshness, missing count, no-advice copy | Ready for current summary only |
| Home report provenance strip | No, report sidecar only | N/A | Yes, mapped report provenance | Authority/freshness/observe-only/fallback counts | Already has safer provenance surface |
| Scanner/portfolio/options/backtest | No | N/A | N/A | Out of scope | Forbidden for this track |

## Recommended next task

Open exactly one future implementation task:

**T-1077-M1: Frontend stock evidence adapter item-metadata preservation test lock**

Goal:

- Add a focused adapter test proving `normalizeStockEvidenceResponse()` preserves item-level `quote`, `technical`, `fundamental`, `news`, and `secFilingEvidence` metadata as opaque records.
- Include quote diagnostic fixture fields such as `source`, `sourceType`, `freshness`, `asOf`, `isFallback`, `isStale`, `isPartial`, `isSynthetic`, `isUnavailable`, `observationOnly`, `scoreContributionAllowed=false`, `sourceAuthorityAllowed=false`, `rawPayloadStored=false`, and nested `sourceConfidence`.
- Assert the adapter does not fabricate metadata for absent blocks.
- Keep the existing `fundamentalsSummary` whitelist and forbidden-field assertions intact.

Allowed future files:

- `apps/dsa-web/src/api/__tests__/stockEvidence.test.ts`

Forbidden future files:

- `apps/dsa-web/src/api/stockEvidence.ts`
- `apps/dsa-web/src/types/stockEvidence.ts`
- `apps/dsa-web/src/pages/**`
- `apps/dsa-web/e2e/**`
- `api/**`
- `src/**`
- `data_provider/**`
- `tests/**` outside `apps/dsa-web/src/api/__tests__/stockEvidence.test.ts`
- `docs/**` unless a task explicitly requests a follow-up report
- root config, package, lockfile, dependency, CI, Docker, provider/cache/runtime, scanner, portfolio, options, and backtest files

Forbidden semantic changes:

- no badge implementation;
- no raw metadata dump into UI;
- no provider/source authority inference;
- no frontend behavior changes;
- no adapter normalization logic changes;
- no API/schema/service/provider/cache/runtime changes;
- no scanner, portfolio, options, or backtest changes;
- no buy/sell/trading/valuation advice copy.

Focused validation for T-1077-M1:

```bash
npm --prefix apps/dsa-web run test -- src/api/__tests__/stockEvidence.test.ts
git diff --check -- apps/dsa-web/src/api/__tests__/stockEvidence.test.ts
./scripts/release_secret_scan.sh
```

Escalate only if that test reveals the adapter currently drops item metadata or if a future prompt explicitly scopes source/type changes.

## Deferred work

Do not open these as the immediate next task:

- Home metadata badges.
- A frontend placeholder or trust/status rail.
- A docs-only IA spec for display vocabulary.
- Frontend item metadata types or normalizer changes.
- Provider capability/source-authority adoption.
- Service/API metadata expansion.

A later IA task may be useful after T-1077-M1, but it should start from a locked adapter fixture and define one collapsed consumer vocabulary before any visible UI.

## Protected-domain warnings

This audit stays adjacent to protected domains but does not modify them:

- API response shape and stored contract versions: preserve existing endpoint behavior; do not add or remove fields as cleanup.
- Provider runtime: no provider order, live-call path, fallback, retry, timeout, budget, cache, TTL, SWR, MarketCache, or network behavior changes.
- Quote freshness/source authority: do not infer live/fresh/authoritative status from `provider`, `source`, `updatedAt`, or `asOf`.
- Source confidence and readiness: diagnostic metadata must remain observation-only and non-scoring until explicit provider capability identity exists.
- Frontend: no raw provider/schema/debug/source-confidence metadata in consumer UI.
- Finance safety: keep copy observation-only and no-advice; do not add buy/sell/trading/valuation wording.
- Scanner, portfolio, options, and backtest are not consumers of this endpoint and must remain untouched.

## Validation evidence for this audit

Commands run before final closeout:

```bash
git diff --check -- docs/codex/audits/T-1077-single-stock-evidence-consumer-metadata-readiness-audit.md
./scripts/release_secret_scan.sh
```

Result:

- `git diff --check -- docs/codex/audits/T-1077-single-stock-evidence-consumer-metadata-readiness-audit.md` passed with no output after adding the new file with intent-to-add for diff checking.
- `./scripts/release_secret_scan.sh` passed: `[PASS] No high-confidence secret patterns found in changed text files.`

## Final audit decision

Proceed with exactly one narrow future write:

**T-1077-M1: Frontend stock evidence adapter item-metadata preservation test lock.**

Do not implement badges now. Do not add a visible placeholder now. Do not expose raw metadata. Do not infer provider authority. Do not touch source/runtime/API/frontend behavior or scanner/portfolio/options/backtest surfaces.

## Final diff confirmation for this audit

- This T-1077 task is report-only.
- No source code changed.
- No tests changed.
- No config/package/lockfile changes.
- No provider additions.
- No provider/cache/runtime/network/API/frontend behavior changes.
- No badge implementation.
- No raw metadata dump into UI.
- No scanner/portfolio/options/backtest changes.
