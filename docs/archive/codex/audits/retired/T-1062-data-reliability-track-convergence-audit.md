# T-1062 Data Reliability Track Convergence Audit

Task ID: T-1062-AUDIT

Task title: Data reliability track convergence audit

Mode: READ-ONLY-AUDIT with explicitly authorized docs-only audit artifact, commit, and push.

Allowed artifact:

`docs/codex/audits/T-1062-data-reliability-track-convergence-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1062-data-reliability-track-convergence-audit`
- branch: `codex/t1062-data-reliability-track-convergence-audit`
- pre-write tracked/staged dirty files: none
- local branch commits ahead of `origin/main` during preflight: none

Scope boundary:

- Source, tests, config, package, lockfile, provider, cache, runtime, API behavior, frontend behavior, scanner, portfolio, options, and backtest files were inspected only.
- This audit does not implement provider/runtime adoption, endpoint wiring, frontend badges, scanner score-cap changes, source-authority inference, or UI redesign.
- Final diff is limited to this Markdown report.

## Executive decision

The data reliability track has largely converged from "missing metadata" into "metadata exists but must not be promoted into runtime authority." The safest next write is not another broad provenance expansion and not quote provider capability adoption.

Recommend exactly one next task:

**T-1062-M1: Market temperature route response-model no-drop contract wire.**

This is a narrow backend API contract task. It should wire the already-existing `MarketTemperatureConsumedSubsetResponse` onto `GET /api/v1/market/temperature` only after adding a route-level test that proves no historical public response keys are dropped. It must not change Market temperature calculations, provider/cache behavior, MarketCache semantics, frontend behavior, or source-authority/scoring semantics.

Why this wins by convergence:

- Provider/source readiness is already implemented as an inert helper and real quote authority adoption is deferred.
- Market temperature has the consumed-subset schema/test lock, but the route still has no `response_model`.
- Liquidity intentionally keeps top-level `observationEvidenceSnapshot` service-only.
- Rotation Radar already has a strict consumer evidence snapshot and frontend consumption.
- Scanner explainability metadata is now contract-locked; score-cap semantics remain protected.
- Single-stock evidence endpoint metadata and quote diagnostic tests are now aligned.
- Frontend badge work is not ready because current consumers either already have safer provenance surfaces or only consume opaque metadata/fundamentals summaries.

## Convergence matrix

| Area | Classification | Current contracts/tests | Remaining protected-domain risks | Frontend consumption ready |
| --- | --- | --- | --- | --- |
| ProviderSourceReadinessContract / provider confidence | done for inert contract; defer runtime adoption | `ProviderSourceReadinessContract` serializes diagnostic-only, observation-only, no runtime/network/cache flags (`src/services/source_confidence_contract.py:439`). `build_provider_source_readiness_contract()` states it does not import providers, call services, read config, or mutate cache (`src/services/source_confidence_contract.py:575`). Tests prove positive inputs still keep `authorityGrant=false` and `scoreContributionAllowed=false`, and degraded/missing inputs fail closed (`tests/test_source_confidence_contract.py:647`, `tests/test_source_confidence_contract.py:708`, `tests/test_source_confidence_contract.py:750`). | Real adoption would require explicit runtime quote provider capability identity. Inferring provider id, source tier, trust level, or freshness expectation from current quote source strings would be source-authority inference and touches provider runtime/API/scoring authority. | No. There is no safe consumer display target for provider readiness yet; quote metadata remains diagnostic. |
| Market temperature DTO/evidence | ready for narrow write | `MarketTemperatureConsumedSubsetResponse` locks `source`, freshness flags, `researchReadiness`, actionability/evidence frames, `regimeSummary`, `providerHealth`, and `evidenceSnapshot` with `extra="allow"` (`api/v1/schemas/market_temperature.py:75`). Tests validate the consumed subset and historical extra-key preservation (`tests/api/test_market_temperature.py:600`). The route still lacks `response_model` (`api/v1/endpoints/market.py:163`). | Wiring a route response model is an API response-shape touch. It must prove no historical fields are filtered and must not alter `conclusionAllowed`, score caps, regime summary, provider health, MarketCache, provider runtime, or evidence calculations. | Yes for current fields. Frontend types and normalizers consume `researchReadiness`, `marketActionabilityFrame`, and `marketIntelligenceEvidenceFrame` (`apps/dsa-web/src/api/market.ts:694`, `apps/dsa-web/src/api/market.ts:1068`). No frontend write is needed for the recommended task. |
| Liquidity observation evidence | defer | Service builds top-level `observationEvidenceSnapshot` (`src/services/liquidity_monitor_service.py:376`), but `LiquidityMonitorResponse` exposes the public subset without that top-level field (`api/v1/schemas/liquidity_monitor.py:194`). Tests explicitly assert the raw service payload includes it and the API/DTO body excludes it (`tests/test_liquidity_monitor_service.py:2165`, `tests/api/test_liquidity_monitor.py:216`). | Publishing the top-level snapshot would reverse an intentional API contract. It needs product/API confirmation and must not alter liquidity scoring, evidence weighting, provider calls, source metadata, or no-advice boundaries. | Ready only for the current public subset. Frontend consumes `sourceMetadata`, `capitalFlowSignal`, and `liquidityImpulseSynthesis` (`apps/dsa-web/src/api/liquidityMonitor.ts:163`, `apps/dsa-web/src/pages/LiquidityMonitorPage.tsx:2270`), not the service-only snapshot. |
| Rotation Radar evidence | done | Route uses `MarketRotationRadarResponse` (`api/v1/endpoints/market.py:137`). Consumer snapshot/provider/theme models use strict `extra="forbid"` for the key public boundary (`api/v1/schemas/market_rotation.py:247`, `api/v1/schemas/market_rotation.py:314`). Service builds `consumerEvidenceSnapshot` (`src/services/market_rotation_radar_service.py:492`, `src/services/market_rotation_radar_service.py:1620`). Tests lock absent/fallback provider states, authority closures, and admin-field exclusion (`tests/api/test_market_rotation_radar.py:305`, `tests/api/test_market_rotation_radar.py:486`). | Remaining `Dict[str, Any]` areas such as `themeFlowSignal` and family rollups are adjacent to rotation ranking/headline semantics. Tightening them is not the smallest track-wide write unless a future prompt scopes it separately. | Yes. Frontend normalizes `providerState`, `themes`, and `rotationFamilyRollup` and falls back from summary rollup to consumer snapshot rollup when needed (`apps/dsa-web/src/api/marketRotation.ts:483`, `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:389`). |
| Scanner explainability metadata | done; semantic changes blocked | Backend scoring caps are live rank-affecting behavior: `_apply_score_caps_and_explainability()` updates `raw_score`, `final_score`, and `score` (`src/services/market_scanner_service.py:6835`, `src/services/market_scanner_service.py:6922`). API schema now locks score explainability, evidence packet, consumer diagnostics, and candidate evidence frames (`api/v1/schemas/scanner.py:227`, `api/v1/schemas/scanner.py:326`). Tests assert metadata preservation without score/order drift (`tests/api/test_scanner.py:215`). | Any cap-weight, cap-reason, score, rank, shortlist, threshold, sorting, filtering, or degraded-source default change is protected scanner scoring/ranking behavior. | Ready for current safe display only. Frontend types and trust strip read explainability/evidence metadata (`apps/dsa-web/src/types/scanner.ts:325`, `apps/dsa-web/src/components/scanner/ScannerScoreTrustStrip.tsx:113`). No badge or score semantic write is recommended. |
| Single-stock evidence endpoint | done; frontend badges defer | `/stocks/{code}/evidence` item metadata schema allows and documents optional source/freshness/confidence/authority fields while preserving opaque item extras (`api/v1/schemas/stocks.py:260`, `api/v1/schemas/stocks.py:292`). `fundamentalsSummary` remains whitelist-filtered (`api/v1/schemas/stocks.py:221`). API tests preserve item metadata and quote diagnostics (`tests/api/test_stock_evidence_api.py:402`). | Service projection expansion, item-block filtering, provider metadata inference, or frontend badge display could fabricate authority or leak raw/internal terminology. | Partially. The frontend adapter preserves opaque item blocks (`apps/dsa-web/src/api/stockEvidence.ts:119`), but Home only reads `stockEvidencePacket.fundamentalsSummary` from the endpoint (`apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx:5271`). Item metadata badge consumption is not ready. |
| Quote diagnostic metadata / authority adoption | diagnostic done; authority adoption defer | `build_quote_diagnostic_source_metadata()` emits diagnostic-only source/freshness flags, `observationOnly=true`, `scoreContributionAllowed=false`, `sourceAuthorityAllowed=false`, `rawPayloadStored=false`, and nested `sourceConfidence` (`src/services/stock_evidence_quote_adapter.py:58`). `StockEvidenceService._quote()` merges this metadata without changing quote fetch behavior (`src/services/agent_stock_evidence_service.py:399`). Tests prove quote diagnostics preserve provenance, block live claims, exclude deferred provider-readiness keys, and keep quote out of score-eligible evidence (`tests/test_agent_stock_evidence_service.py:492`, `tests/api/test_stock_evidence_api.py:402`). | Real provider capability/source-authority adoption is blocked by T-1061. Current quote evidence lacks explicit provider id, source tier, trust level, and freshness expectation. Inferring them from `UnifiedRealtimeQuote.source` would be implicit authority adoption. | No for authority/readiness. Existing consumer path preserves diagnostics but does not safely display raw item metadata. |

## Recommended next task

Open one future implementation task only:

**T-1062-M1: Market temperature route response-model no-drop contract wire**

Goal:

- Wire `response_model=MarketTemperatureConsumedSubsetResponse` onto `GET /api/v1/market/temperature`.
- Add a route-level regression test proving the API response still includes all historical public keys after response-model serialization.
- Keep the already locked consumed subset as the typed contract while preserving extra fields through `extra="allow"`.

Allowed future write files:

- `api/v1/endpoints/market.py`
- `tests/api/test_market_temperature.py`

Optional only if the existing schema needs a compatibility tweak found by the no-drop test:

- `api/v1/schemas/market_temperature.py`

Acceptance criteria:

- Route declares `response_model=MarketTemperatureConsumedSubsetResponse`.
- New or updated test compares the service payload/public route payload and proves no existing top-level public keys are dropped.
- Existing consumed-subset test remains valid.
- No frontend files are touched.
- No service/provider/cache/runtime files are touched.
- No Market temperature calculation, `conclusionAllowed`, readiness/actionability/evidence frame, provider health, freshness, fallback/stale/partial, MarketCache, or provider runtime semantics change.

Focused validation for that future task:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python3 -m pytest -q tests/api/test_market_temperature.py -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python3 -m py_compile api/v1/endpoints/market.py api/v1/schemas/market_temperature.py
git diff --check -- api/v1/endpoints/market.py api/v1/schemas/market_temperature.py tests/api/test_market_temperature.py
./scripts/release_secret_scan.sh
```

Escalate to `./scripts/ci_gate.sh` only if the task changes service logic, API payload meaning, provider/cache behavior, or the no-drop test reveals response-model serialization is not compatibility-preserving.

## Explicit rejections

This audit explicitly rejects the following as the next data reliability write:

- broad provenance sweep;
- provider additions;
- source authority inference;
- frontend raw metadata badge dump;
- scanner score-cap semantic changes;
- global frontend redesign;
- Liquidity top-level `observationEvidenceSnapshot` publication without explicit API/product confirmation;
- Rotation ranking/headline/score/flow semantic changes;
- quote `ProviderSourceReadinessContract` runtime wiring;
- provider capability adoption from quote source strings;
- MarketCache TTL/SWR/cold-start/cache-key/payload changes.

## Protected-domain warnings

The remaining gaps are mostly protected-domain-adjacent:

- API response shape: the recommended Market route write is safe only with no-drop proof.
- Provider runtime: no provider order, live-call path, fallback, retry, timeout, or network behavior should change.
- MarketCache: no TTL/SWR/cold-start/background refresh/cache-key/payload semantics should change.
- Scanner: score caps are rank-affecting and must not be changed as explainability work.
- Quote authority: diagnostic metadata must not become source authority or score contribution.
- Frontend: raw provider/schema/debug/source-confidence metadata must not be dumped into consumer UI.
- Finance copy: keep consumer-facing language observation-only and no-advice.

## Final audit decision

Proceed with exactly one narrow backend API contract task:

**T-1062-M1: Market temperature route response-model no-drop contract wire.**

Do not continue the quote provider capability track now. Do not open a frontend badge task now. Do not expand scanner scoring/ranking, provider runtime, Liquidity public snapshots, Rotation semantics, portfolio/options/backtest, or global UI design from this audit.

## Final diff confirmation for this audit

- This T-1062 task is report-only.
- No source code changed.
- No tests changed.
- No config/package/lockfile changes.
- No provider additions.
- No provider/cache/runtime/network/API/frontend behavior changes.
- No frontend badge implementation.
- No scanner scoring/ranking/filtering changes.
- No portfolio/accounting/options/backtest behavior changes.
- No `ProviderSourceReadinessContract` runtime wiring.
- No authority or score contribution grant.
