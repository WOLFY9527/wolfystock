# T-1046 Market Liquidity Rotation Evidence DTO Lock Readiness Audit

Task ID: T-1046-AUDIT
Task title: Market Liquidity Rotation evidence DTO lock readiness audit
Mode: READ-ONLY-AUDIT with docs-only report artifact
Date: 2026-06-06
Workspace: `/Users/yehengli/worktrees/t1046-market-liquidity-rotation-evidence-dto-audit`
Branch: `codex/t1046-market-liquidity-rotation-evidence-dto-audit`
Base commit inspected: `e4bff2a98b7218b93195e273b2c1ce67d14cd64a`
Allowed diff: this audit document only

## Executive Decision

Recommend exactly one immediate backend DTO/test write:

**T-1046-M1 Market temperature consumed-subset DTO contract lock**

This is the smallest safe lock because Market temperature already publishes and the frontend already consumes
the relevant readiness/evidence fields, but the backend route still has no `response_model`. The write should be
an inert/additive schema-and-test lock for the currently public, consumer-consumed subset only. It must not
change provider runtime, MarketCache, scoring, readiness math, fallback/live/stale labels, or frontend behavior.

Do **not** make Liquidity `observationEvidenceSnapshot` public in the same write. It is service-built, but current
API and service tests explicitly lock it as service-only and absent from the public response. Do **not** open a
Rotation DTO lock from this audit. Rotation Radar already has the mature typed consumer boundary that T-1021
expected from the other surfaces.

## Per-Surface Verdict

| Surface | DTO/evidence maturity | Current locking evidence | Missing or weak metadata boundary | Verdict |
| --- | --- | --- | --- | --- |
| Market Overview temperature | Service publishes `regimeSummary`, `researchReadiness`, `marketActionabilityFrame`, `marketIntelligenceEvidenceFrame`, `providerHealth`, and `evidenceSnapshot`, but `/api/v1/market/temperature` has no `response_model`. | Backend tests lock additive/fail-closed behavior and key sets for readiness, actionability, evidence, and regime summary. Frontend types and normalizers consume the same fields. | Top-level freshness/source/evidence fields are test-locked but not DTO-typed. A full temperature DTO would be too broad because the endpoint still carries many historical extra fields. | Ready for one narrow consumed-subset DTO/test lock. |
| Liquidity Monitor | Public response is already typed for `score`, `freshness`, `indicators[].evidence`, `coverageDiagnostics`, `capitalFlowSignal`, `liquidityImpulseSynthesis`, and `sourceMetadata`. Service also builds top-level `observationEvidenceSnapshot`. | `LiquidityMonitorResponse` is wired as route `response_model`; tests explicitly assert `observationEvidenceSnapshot` is present in raw service output but absent from the public API/body. Golden fixture tests validate the public DTO. | Top-level `observationEvidenceSnapshot` has useful source/freshness/fallback/stale/partial/sourceConfidence metadata, but it is intentionally not a public typed field today. | Defer top-level snapshot publication. Locking the current public subset is safe but not the highest-value immediate write. |
| Rotation Radar | Strong typed response with strict `consumerEvidenceSnapshot`, `providerState`, and consumer theme quality models. | Route uses `MarketRotationRadarResponse`; consumer snapshot models use `extra="forbid"`; service/API tests lock fallback, partial, provider state, breadth evidence, family rollup, and admin-field exclusion. | Minor remaining looseness is inside `themeFlowSignal` and family rollup `Dict[str, Any]`, but the public consumer snapshot boundary is already mature. | No immediate DTO lock from this audit. Treat as mature and avoid broad writes. |

## Evidence Summary

### Market Overview

- `GET /api/v1/market/temperature` returns `MarketOverviewService().get_market_temperature(...)` without a
  declared `response_model` (`api/v1/endpoints/market.py:163`).
- The service assembles `marketRegimeSynthesis`, `marketDecisionSemantics`, `regimeSummary`,
  `marketActionabilityFrame`, `marketIntelligenceEvidenceFrame`, and then adds `researchReadiness`,
  `providerHealth`, and `evidenceSnapshot` (`src/services/market_overview_service.py:1124`,
  `src/services/market_overview_service.py:1140`, `src/services/market_overview_service.py:1145`,
  `src/services/market_overview_service.py:1225`, `src/services/market_overview_service.py:1227`).
- `researchReadiness` is derived from `conclusionAllowed`, `scoreCap`, source tier/trust, freshness, fallback,
  stale, synthetic, unavailable, and missing-evidence signals
  (`src/services/market_overview_service.py:1273`).
- Backend API tests already lock the public subset and fail-closed behavior:
  `tests/api/test_market_temperature.py:574`, `tests/api/test_market_temperature.py:618`,
  `tests/api/test_market_temperature.py:665`, `tests/api/test_market_temperature.py:874`,
  `tests/api/test_market_temperature.py:997`.
- Frontend consumption is already concrete: `MarketTemperatureResponse` includes `researchReadiness`,
  `marketActionabilityFrame`, `marketIntelligenceEvidenceFrame`, and `regimeSummary`
  (`apps/dsa-web/src/api/market.ts:694`), and the page renders readiness plus actionability/evidence frames from
  `panels.temperature` (`apps/dsa-web/src/pages/MarketOverviewPage.tsx:927`).

Readiness conclusion: a small schema/test lock is ready, but a full route `response_model` must preserve
historical extra fields or avoid wiring in the first write. The immediate lock should target only fields the
frontend already consumes and backend tests already treat as public.

### Liquidity Monitor

- The route already uses `response_model=LiquidityMonitorResponse`
  (`api/v1/endpoints/liquidity_monitor.py:15`).
- `LiquidityMonitorResponse` includes score, freshness, indicators, `capitalFlowSignal`,
  `liquidityImpulseSynthesis`, advisory disclosure, and `sourceMetadata`, but not top-level
  `observationEvidenceSnapshot` (`api/v1/schemas/liquidity_monitor.py:194`).
- The service builds top-level `observationEvidenceSnapshot` from indicator evidence and diagnostics
  (`src/services/liquidity_monitor_service.py:376`, `src/services/liquidity_monitor_service.py:391`).
  That helper preserves proxy/fallback/stale/partial/missing counts and source-confidence metadata through
  `build_provider_evidence_snapshot(...)` (`src/services/provider_evidence_snapshot.py:169`).
- Current tests intentionally keep this service-only:
  `tests/test_liquidity_monitor_service.py:2165` asserts the raw payload includes the snapshot and the DTO dump
  excludes it; `tests/api/test_liquidity_monitor.py:216` asserts the public API body does not include it.
- Frontend types/normalization also omit the top-level snapshot and consume only current public fields
  (`apps/dsa-web/src/api/liquidityMonitor.ts:163`, `apps/dsa-web/src/api/liquidityMonitor.ts:255`).

Readiness conclusion: publishing `observationEvidenceSnapshot` would reverse an existing public contract, not
merely lock a missing DTO. It needs explicit product/API confirmation before any additive schema write. The
safe immediate write is not here unless the scope is only to reinforce the current public DTO and service-only
exclusion.

### Rotation Radar

- The route uses `response_model=MarketRotationRadarResponse`
  (`api/v1/endpoints/market.py:137`).
- `RotationRadarConsumerEvidenceSnapshotModel`, `RotationRadarConsumerProviderStateModel`, and
  `RotationRadarConsumerThemeQualityModel` use strict consumer models with `extra="forbid"`
  (`api/v1/schemas/market_rotation.py:247`, `api/v1/schemas/market_rotation.py:280`,
  `api/v1/schemas/market_rotation.py:314`).
- The service builds `consumerEvidenceSnapshot` with freshness, fallback/stale/partial, provider state, ETF proxy
  summary, per-theme quality, and rotation family rollup
  (`src/services/market_rotation_radar_service.py:1546`).
- API and service tests lock whitelist shape and degraded evidence behavior:
  `tests/api/test_market_rotation_radar.py:305`, `tests/api/test_market_rotation_radar.py:325`,
  `tests/api/test_market_rotation_radar.py:486`, `tests/test_market_rotation_radar_service.py:695`,
  `tests/test_market_rotation_radar_service.py:871`.
- Frontend uses summary/theme fields first and falls back to `consumerEvidenceSnapshot.rotationFamilyRollup` only
  when summary rollup is missing (`apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:382`).

Readiness conclusion: Rotation does not need the immediate DTO lock. Its remaining looseness is not a blocking
contract gap for this task.

## Recommended Immediate Write

Open one future implementation task:

**T-1046-M1 Market temperature consumed-subset DTO contract lock**

Allowed files for that future write:

- `api/v1/schemas/market_temperature.py`
- `api/v1/endpoints/market.py` only if the task chooses to wire a response model after proving extra-field
  preservation
- `tests/api/test_market_temperature.py`

Implementation constraints:

- Add an inert/additive Pydantic model for the currently public, frontend-consumed subset:
  `source`, `updatedAt`, `freshness`, `isFallback`, `isStale`, `temperatureAvailable`, `conclusionAllowed`,
  `researchReadiness`, `marketActionabilityFrame`, `marketIntelligenceEvidenceFrame`, `regimeSummary`,
  `providerHealth`, and `evidenceSnapshot`.
- Prefer `extra="allow"` or a schema-only validation path so historical temperature fields are preserved.
- If wiring `response_model`, add a test that serializes the endpoint before/after model validation and proves no
  existing public keys are dropped.
- Compare the old DTO subset and assert additive model invariants separately. Do not churn broad golden payloads.
- Do not add a new `consumerEvidenceSnapshot` for Market temperature in this first write.

Validation plan for that future write:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python3 -m pytest -q tests/api/test_market_temperature.py -p no:cacheprovider
/Users/yehengli/daily_stock_analysis/.venv/bin/python3 -m py_compile api/v1/endpoints/market.py api/v1/schemas/market_temperature.py
git diff --check
./scripts/release_secret_scan.sh
```

## Explicit Deferrals And Rejections

Defer these from the immediate DTO/test write:

- Liquidity top-level `observationEvidenceSnapshot` publication. Current tests make it service-only; flipping it
  public requires explicit API/product confirmation and a separate additive schema compatibility review.
- Rotation Radar DTO lock. The consumer snapshot boundary is already typed, strict, and tested.
- Market temperature full response DTO or broad route filtering. The endpoint has too many historical fields for
  a safe first strong DTO pass.

Explicitly reject these broad provenance/provider sweeps:

- Provider additions, provider order changes, live-call path changes, retry/timeout/fallback behavior changes, or
  entitlement/source activation.
- MarketCache TTL, SWR, cold-start, cache-key, mutation, or provenance write changes.
- Any change to Market `conclusionAllowed`, `scoreCap`, `regimeSummary.label`, official macro freshness,
  Liquidity score contribution, Rotation `rankEligible`, `headlineEligible`, `rankingLane`,
  `sourceAuthorityAllowed`, or `scoreContributionAllowed`.
- Any frontend copy/placement work mixed into the DTO lock.

## Final Diff Confirmation

This T-1046 task is report-only. It did not implement DTO changes, did not change source/tests/config/package or
provider/cache/runtime behavior, and did not change API/frontend behavior.
