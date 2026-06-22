# T-1059 Single-stock Evidence Metadata Consumer Readiness Audit

Task ID: T-1059-AUDIT

Task title: Single-stock evidence metadata consumer readiness audit

Mode: READ-ONLY-AUDIT with explicitly authorized docs-only audit artifact, commit, and push.

Allowed artifact:

`docs/codex/audits/T-1059-single-stock-evidence-metadata-consumer-readiness-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1059-single-stock-evidence-consumer-readiness-audit`
- branch: `codex/t1059-single-stock-evidence-consumer-readiness-audit`
- base commit inspected before writing this report: `0949c53c`
- current branch had no local commits ahead of `origin/main` during preflight.

Scope boundary:

- Source, tests, config, package, lockfile, provider, cache, runtime, API behavior, frontend behavior, scanner, portfolio, options, and backtest files were inspected only.
- This audit does not implement metadata badges, frontend UI, adapter changes, provider changes, service metadata expansion, API behavior changes, scanner scoring/ranking/filtering changes, portfolio/options/backtest changes, or network behavior changes.
- Final diff is limited to this Markdown report.

## Readiness verdict

The API serialization boundary is ready: current `/api/v1/stocks/{stock_code}/evidence` schema and endpoint tests preserve optional item metadata, and T-1058 quote diagnostic metadata survives endpoint model validation when supplied by the service.

The frontend display boundary is not ready for metadata badges yet: the only real frontend caller, Home, fetches `/stocks/{code}/evidence` only to read `stockEvidencePacket.fundamentalsSummary`. Item-level `quote`/`technical`/`fundamental`/`news`/`secFilingEvidence` metadata is preserved as opaque records by the frontend adapter, but no component reads it for UI decisions today.

There is also a current test-boundary blocker: one older backend service test still expects quote metadata to be absent and fails against the T-1058 diagnostic projection. That should be fixed before a frontend badge or typed consumer write, because otherwise the suite gives contradictory evidence about whether quote metadata is expected.

Recommended next write:

**T-1059-M1: Tests-only alignment for existing quote diagnostic metadata preservation.**

This should update the stale `StockEvidenceService` test to expect diagnostic quote metadata and assert that authority/score contribution remain closed. It must not change source, provider, runtime, API, frontend, schema, or UI behavior.

## Audit questions and answers

### 1. Which frontend or API consumer surfaces currently read `/stocks/{stock_code}/evidence`?

Current route and API boundary:

- The backend route is `GET /api/v1/stocks/{stock_code}/evidence`, returning `StockEvidenceResponse` with `response_model_exclude_none=True` (`api/v1/endpoints/stocks.py:284`, `api/v1/endpoints/stocks.py:286`, `api/v1/endpoints/stocks.py:287`).
- The route instantiates `StockEvidenceService`, replaces both quote fetcher seams with `_ReadOnlyEvidenceFetcherManager`, calls `get_stock_evidence([stock_code])`, and validates through `StockEvidenceResponse.model_validate(payload)` (`api/v1/endpoints/stocks.py:296`, `api/v1/endpoints/stocks.py:298`, `api/v1/endpoints/stocks.py:300`, `api/v1/endpoints/stocks.py:302`, `api/v1/endpoints/stocks.py:303`, `api/v1/endpoints/stocks.py:315`).
- `_ReadOnlyEvidenceFetcherManager.get_realtime_quote()` returns `None`, so the public API endpoint itself remains fail-closed for quote runtime access (`api/v1/endpoints/stocks.py:52`, `api/v1/endpoints/stocks.py:55`).

Frontend route consumers:

- `stockEvidenceApi.getStockEvidence(stockCode)` is the frontend adapter that calls `/api/v1/stocks/${encodeURIComponent(stockCode)}/evidence` (`apps/dsa-web/src/api/stockEvidence.ts:163`, `apps/dsa-web/src/api/stockEvidence.ts:165`, `apps/dsa-web/src/api/stockEvidence.ts:166`).
- Home imports `stockEvidenceApi` and calls `stockEvidenceApi.getStockEvidence(activeEvidenceTicker)` in one effect (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:16`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5271`).
- Home then selects the matched item and stores only `matchedItem?.stockEvidencePacket?.fundamentalsSummary` (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5276`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5278`).
- Search found no other application surface calling `getStockEvidence` or the `/stocks/{code}/evidence` endpoint outside tests.

Test consumers:

- `tests/api/test_stock_evidence_api.py` covers endpoint serialization, OpenAPI metadata schema, no-fabrication, degraded payloads, and the read-only quote seam.
- `apps/dsa-web/src/api/__tests__/stockEvidence.test.ts` covers frontend adapter normalization and endpoint URL encoding.
- `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx` mocks `stockEvidenceApi.getStockEvidence` and verifies Home fetches the current stock only and renders fundamentals-safe copy.

Adjacent but distinct surfaces:

- Home also consumes report-derived `singleStockEvidencePacket`, `evidenceCitationFrame`, and `sourceProvenanceFrame` from analysis reports; those are not reads of `/stocks/{code}/evidence` (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:938`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5201`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5205`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5209`).
- Scanner, Rotation, Options, Backtest, Portfolio, and admin evidence surfaces use other evidence normalizers or domain payloads, not this single-stock evidence endpoint.

### 2. Whether quote diagnostic metadata from T-1058 is preserved through API serialization

Yes, when the service payload contains it.

Current projection:

- `build_quote_diagnostic_source_metadata()` emits `source`, `sourceType`, `freshness`, `asOf`, `degradationReason`, fallback/stale/partial/synthetic/unavailable flags, `observationOnly=True`, `scoreContributionAllowed=False`, `sourceAuthorityAllowed=False`, `rawPayloadStored=False`, and `sourceConfidence` (`src/services/stock_evidence_quote_adapter.py:58`, `src/services/stock_evidence_quote_adapter.py:89`, `src/services/stock_evidence_quote_adapter.py:104`).
- `StockEvidenceQuoteSnapshot` now carries `source_metadata` (`src/services/stock_evidence_quote_adapter.py:110`, `src/services/stock_evidence_quote_adapter.py:118`).
- `StockEvidenceQuoteAdapter.get_quote_snapshot()` builds `source_metadata` from the quote source and market timestamp without changing provider order or call behavior (`src/services/stock_evidence_quote_adapter.py:127`, `src/services/stock_evidence_quote_adapter.py:140`).
- `StockEvidenceService._quote()` merges `quote.source_metadata` into the public `quote` evidence item; missing/error quote paths also emit unavailable diagnostic metadata (`src/services/agent_stock_evidence_service.py:399`, `src/services/agent_stock_evidence_service.py:407`, `src/services/agent_stock_evidence_service.py:417`, `src/services/agent_stock_evidence_service.py:423`, `src/services/agent_stock_evidence_service.py:430`).

Current serialization lock:

- `StockEvidenceItemMetadataDict` uses an OpenAPI metadata schema that names the optional source/freshness/fallback/stale/partial/synthetic/unavailable/source-confidence/authority fields while allowing additional properties (`api/v1/schemas/stocks.py:260`, `api/v1/schemas/stocks.py:292`).
- `StockEvidenceItemResponse.quote`, `technical`, `fundamental`, `news`, and `secFilingEvidence` all use that metadata dict (`api/v1/schemas/stocks.py:298`, `api/v1/schemas/stocks.py:305`, `api/v1/schemas/stocks.py:309`).
- `test_stock_evidence_endpoint_preserves_item_metadata_shape` verifies metadata survives endpoint response validation across quote, technical, fundamental, news, and SEC evidence blocks (`tests/api/test_stock_evidence_api.py:171`, `tests/api/test_stock_evidence_api.py:243`, `tests/api/test_stock_evidence_api.py:247`, `tests/api/test_stock_evidence_api.py:275`).
- `test_stock_evidence_endpoint_preserves_quote_diagnostic_metadata_and_readonly_seam` verifies the route preserves T-1058 quote diagnostic metadata and keeps the read-only seam installed (`tests/api/test_stock_evidence_api.py:402`, `tests/api/test_stock_evidence_api.py:416`, `tests/api/test_stock_evidence_api.py:470`, `tests/api/test_stock_evidence_api.py:486`).

Important nuance:

- The default public API path replaces the quote fetchers with `_ReadOnlyEvidenceFetcherManager`, so a normal API call should produce unavailable quote diagnostics rather than live provider quote diagnostics. The T-1058 metadata is preserved when present; the route does not grant live/source authority.

### 3. Whether frontend types/components currently ignore or consume source/freshness/fallback/stale/partial metadata

Frontend adapter behavior:

- `StockEvidenceItem.quote`, `technical`, `fundamental`, `news`, and `secFilingEvidence` are typed as opaque `Record<string, unknown> | null`, not as a named metadata contract (`apps/dsa-web/src/types/stockEvidence.ts:27`, `apps/dsa-web/src/types/stockEvidence.ts:30`, `apps/dsa-web/src/types/stockEvidence.ts:34`).
- `normalizeStockEvidenceItem()` preserves those item blocks as opaque objects and does not drop metadata keys when the backend supplies them (`apps/dsa-web/src/api/stockEvidence.ts:99`, `apps/dsa-web/src/api/stockEvidence.ts:119`, `apps/dsa-web/src/api/stockEvidence.ts:127`, `apps/dsa-web/src/api/stockEvidence.ts:131`).
- `normalizeFundamentalsSummary()` strongly whitelists consumer-safe fields and defaults `notInvestmentAdvice`/`observationOnly` to true unless explicitly false, while allowing score/source authority only when explicitly true (`apps/dsa-web/src/api/stockEvidence.ts:41`, `apps/dsa-web/src/api/stockEvidence.ts:73`, `apps/dsa-web/src/api/stockEvidence.ts:78`).

Frontend component behavior:

- Home only renders `StockEvidenceFundamentalsSummary`; it does not read item-level `quote.sourceConfidence`, `quote.freshness`, `quote.isFallback`, `quote.isStale`, `quote.isPartial`, `quote.isSynthetic`, or `quote.isUnavailable` from the `/evidence` response (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5278`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5887`).
- `HomeFundamentalsSummaryBlock` uses only the summary's `source`, `freshness`, `period`, `missingFields`, and metric fields (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2332`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2349`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2351`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2352`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2353`).
- The current freshness copy is sanitized into consumer labels such as recent update, partial refresh, supplemental snapshot, and earlier snapshot (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2653`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2659`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2665`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:2668`).
- Home report-derived `HomeSourceProvenanceStrip` already renders source/freshness/observe-only/fallback counts, but from report `sourceProvenanceFrame`, not from `/stocks/{code}/evidence` item metadata (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:1299`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:1379`, `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:1412`).

Test coverage:

- `apps/dsa-web/src/api/__tests__/stockEvidence.test.ts` locks fundamentals summary safe-field preservation, invalid summary dropping, and encoded calls, but does not yet lock item-level metadata preservation with a fixture containing `quote.sourceConfidence` or degraded flags (`apps/dsa-web/src/api/__tests__/stockEvidence.test.ts:18`, `apps/dsa-web/src/api/__tests__/stockEvidence.test.ts:126`, `apps/dsa-web/src/api/__tests__/stockEvidence.test.ts:155`).
- `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx` verifies the current Home fundamentals summary does not display raw/internal names such as `observationOnly`, `scoreContributionAllowed`, `sourceAuthorityAllowed`, `stock_evidence`, `provider`, or `admin` (`apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx:731`, `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx:751`, `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx:755`, `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx:794`).

### 4. Whether consumer UI would benefit from badges such as observation-only, fallback, stale, partial, unavailable, or synthetic

Potentially yes, but not as a direct item-level badge implementation yet.

Useful badge semantics:

- `observation-only` is already central to the safe copy and should remain visible in consumer language.
- `partial`, `stale`, `fallback`, and `unavailable` could help explain why Home keeps a summary compact or data-insufficient.
- `synthetic` should only appear as user-safe copy if a future consumer vocabulary maps it to a non-internal label such as prepared sample, test data unavailable, or simulated/placeholder where appropriate. Raw `synthetic` is too internal for ordinary consumer UI.

Why not implement badges now:

- The endpoint's default read-only route intentionally produces unavailable quote diagnostics, so quote badges could become a noisy always-present warning rather than useful decision support.
- Home currently has two evidence contexts: report-derived provenance strips and endpoint-derived fundamentals summary. Mixing `/evidence` item-level badges into the existing Home rail without a small vocabulary plan risks duplicating source/freshness labels already shown from report sidecars.
- Existing tests explicitly guard against raw internal terms in the Home fundamentals block.
- The frontend type boundary does not yet name item metadata fields, so a UI badge implementation would either use ad hoc string reads from opaque records or require a separate type/adapter lock.

### 5. Whether exposing these badges risks visual noise or internal terminology leakage

Yes.

Specific risks:

- Raw keys such as `sourceConfidence`, `sourceAuthorityAllowed`, `scoreContributionAllowed`, `rawPayloadStored`, `degradationReason`, `capReason`, `providerId`, `trustLevel`, and `sourceTier` are internal or operator-facing and should not appear in consumer UI.
- Literal values such as `freshness_not_proven`, `local_or_reported`, `unit_fixture`, `mock`, `synthetic`, and provider IDs can leak implementation details or confuse users.
- Showing every degraded flag independently can create badge sprawl: a single quote item can have `freshness=unknown`, `degradationReason=freshness_not_proven`, `observationOnly=true`, `scoreContributionAllowed=false`, `sourceAuthorityAllowed=false`, and `rawPayloadStored=false`; rendered naively, those are redundant.
- Home already has report-level source provenance and evidence citation strips. Additional endpoint badges should be collapsed, deduplicated, and mapped to consumer copy before appearing.

Safe label direction if a later UI task is opened:

- Use consumer labels such as `仅供观察`, `数据待核验`, `补充快照`, `较早快照`, `部分更新`, `数据暂缺`.
- Avoid raw field names, provider names, source-confidence internals, provider-readiness vocabulary, and score/source-authority terminology in visible copy.
- Prefer a single compact trust/status line over per-field badges unless a real user workflow requires more detail.

### 6. Which exact files would be allowed/forbidden for the next write

Recommended next write:

**T-1059-M1: Tests-only alignment for existing quote diagnostic metadata preservation.**

Rationale:

- API serialization is already locked and currently passes focused preservation tests.
- Frontend UI is not yet consuming item metadata and should not get badges before the test suite consistently reflects T-1058.
- A stale backend service test currently fails because it still asserts `item["quote"]` equals the pre-T-1058 six-field payload.

Allowed files for T-1059-M1:

- `tests/test_agent_stock_evidence_service.py`

Forbidden files for T-1059-M1:

- `src/**`
- `data_provider/**`
- `api/**`
- `apps/**`
- `tests/**` except `tests/test_agent_stock_evidence_service.py`
- `docs/**` except an optional task report if explicitly requested
- root config, CI, package, lockfile, dependency, env, Docker, and script files
- scanner, rotation, portfolio, options, backtest, auth, notification, provider/cache/runtime files

Forbidden semantic changes for T-1059-M1:

- no provider additions;
- no provider order, live-call path, retry, timeout, fallback, cache, TTL, SWR, or MarketCache behavior changes;
- no source-authority or score-contribution promotion;
- no API shape or endpoint behavior changes;
- no service/provider metadata expansion;
- no frontend type, adapter, data-fetching, display, or badge changes;
- no scanner scoring/ranking/filtering/selection changes;
- no portfolio/options/backtest behavior changes.

Recommended T-1059-M1 test assertions:

- Keep the current quote provenance assertion for status, price, change percent, currency, provider, and updated time.
- Add assertions for `source`, `sourceType`, `freshness`, `asOf`, `degradationReason`, degraded flags, and `sourceConfidence`.
- Assert `observationOnly is True`, `scoreContributionAllowed is False`, `sourceAuthorityAllowed is False`, and `rawPayloadStored is False`.
- Assert quote evidence remains excluded from `stockEvidencePacket.scoreEligibleEvidence`.
- Assert `price_is_live` remains blocked with `quote_freshness_not_proven`.

Focused validation plan for T-1059-M1:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python3 -m pytest -q \
  tests/test_agent_stock_evidence_service.py::test_service_packet_keeps_quote_provenance_but_blocks_live_claim_without_freshness_metadata \
  tests/test_provider_runtime_contracts.py::test_stock_evidence_quote_projects_diagnostic_source_confidence_without_promotion \
  tests/api/test_stock_evidence_api.py::test_stock_evidence_endpoint_preserves_quote_diagnostic_metadata_and_readonly_seam \
  -p no:cacheprovider
git diff --check -- tests/test_agent_stock_evidence_service.py
./scripts/release_secret_scan.sh
```

Deferred, not recommended as the immediate next write:

- Frontend item-metadata type/test lock in `apps/dsa-web/src/types/stockEvidence.ts` and `apps/dsa-web/src/api/__tests__/stockEvidence.test.ts`.
- Home metadata badges.
- Evidence adapter/service projection expansion.
- Provider-readiness/source-authority wiring.

## Browser check decision

Browser verification was not used for this audit.

Reason:

- No frontend source or UI behavior changed.
- The relevant Home page is identifiable, but the audit question was answered from code and focused tests.
- The endpoint default route intentionally fail-closes quote runtime metadata, so a live page check would not add meaningful evidence about badge readiness without starting or relying on a task-owned server and API state.

## Validation evidence gathered during the audit

Commands run:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python3 -m pytest -q tests/api/test_stock_evidence_api.py::test_stock_evidence_endpoint_preserves_item_metadata_shape tests/api/test_stock_evidence_api.py::test_stock_evidence_endpoint_preserves_quote_diagnostic_metadata_and_readonly_seam -p no:cacheprovider
```

Result: passed, `2 passed in 1.62s`.

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python3 -m pytest -q tests/test_agent_stock_evidence_service.py::test_service_packet_keeps_quote_provenance_but_blocks_live_claim_without_freshness_metadata -p no:cacheprovider
```

Result: failed. The assertion at `tests/test_agent_stock_evidence_service.py:398` still expects `item["quote"]` to equal the old six-field quote payload. Actual quote now includes T-1058 diagnostic metadata such as `asOf`, `degradationReason`, `freshness`, degraded flags, authority closures, and `sourceConfidence`.

```bash
npm --prefix apps/dsa-web run test -- src/api/__tests__/stockEvidence.test.ts --run
```

Result: not run to completion; `vitest` was not found in this worktree (`sh: vitest: command not found`). No dependency installation was performed because this audit is docs-only and dependency refresh is out of scope.

## Final audit decision

Proceed with exactly one narrow future write:

**T-1059-M1: Tests-only alignment for existing quote diagnostic metadata preservation.**

Do not implement metadata badges now. Do not make a frontend UI change now. Do not touch provider/runtime/API semantics. Do not expand service/provider metadata.

After T-1059-M1, a separate frontend consumer-readiness task may be considered, but it should start with a type/test lock and consumer-safe label vocabulary before any visible badges.

## Final diff confirmation for this audit

- This T-1059 task is report-only.
- No source code changed.
- No tests changed.
- No config/package/lockfile changes.
- No provider additions.
- No provider/cache/runtime/network/API/frontend behavior changes.
- No scanner scoring/ranking/filtering changes.
- No portfolio/accounting/FX/holdings changes.
- No options/backtest changes.
