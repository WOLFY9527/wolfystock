# WolfyStock Evidence Readiness Matrix

Status: docs-only readiness matrix.

Date: 2026-06-07

Purpose: give WolfyStock a single stop/go matrix for evidence-related surfaces
so future tasks do not treat tests/contracts/docs maturity as approval for UI
badges, provider/runtime wiring, or source-authority claims.

## Global rules

- Tests-only readiness is not implementation readiness.
- Visible source/freshness/fallback/stale/partial badges stay deferred unless a
  later surface-specific UI mapping task also approves the supporting tests.
- Provider/source authority inference is forbidden. Provider names, freshness,
  fallback success, cache hits, and coverage are not enough to grant authority,
  score contribution, ranking influence, route preference, or consumer badge
  eligibility.
- Consumer-safe default UI may show bounded product states and timestamps where
  the current surface already supports them. Raw provider/debug/reason-code/
  schema/runtime metadata stays admin-only or internal-only.
- Unless a later protected-domain task explicitly opens broader scope, safe
  next tasks are limited to docs/tests/contracts.

## Status legend

- `Tests/contracts ready`: the repo already has enough docs/tests/contracts to
  lock or clarify the current boundary.
- `Consumer-safe default ready`: the current source already has a bounded user
  surface that can remain in place without new UI exposure.
- `Implementation ready`: a later task may add visible UI badges, runtime
  wiring, provider routing, scoring effects, or new API exposure. For this
  matrix, every surface below remains `No` unless explicitly stated otherwise.

## Matrix

| Surface | Current contract/test status | Consumer-safe default status | Admin-only/internal metadata boundary | Next allowed task type | Forbidden next task type |
| --- | --- | --- | --- | --- | --- |
| Market Overview | T-1046 says Market temperature already publishes and is frontend-consumed, with backend tests locking readiness/actionability/evidence fields, but the current public subset is not yet narrowly DTO-typed. Tests/contracts ready for a narrow consumed-subset DTO/test lock. Implementation readiness: No. | Current page already consumes bounded readiness/actionability/evidence fields. New visible source/freshness/fallback badges remain deferred. | Top-level freshness/source/evidence metadata may support future contracts, but raw authority/source-routing/provider semantics must not leak into consumer UI. | Current docs/tests boundary is locked for the currently consumed readiness/evidence subset. No immediate write is required from this matrix. Optional read-only consistency audit only; docs/tests/contracts only if a specific regression or contract gap is found. | UI badge work, provider/runtime/cache/fallback changes, score/ranking semantics, provider authority inference, broad endpoint reshaping. |
| Liquidity Monitor | T-1080 says the page is consumer-ready at source level; component tests and degraded Playwright smoke already lock safe copy, hidden admin diagnostics, observation-only capital-flow context, and raw-field suppression. Tests readiness: Yes. Implementation readiness for new badges/runtime meaning: No. | Consumer-safe default is ready now. Existing surface already maps readiness/freshness/missing-input limits into product copy. New visible source/fallback/stale/partial badge work remains deferred. | Provider details, score-blocking field names, raw fallback diagnostics, cache/runtime terms, and observation internals stay out of default UI. | Current consumer-safe docs/tests boundary is locked. No immediate write is required from this matrix. Optional read-only consistency audit only; docs/tests/contracts only if a specific regression or contract gap is found. | Provider/cache/runtime changes, scoring changes, raw metadata badge dumps, source-authority inference, new UI disclosure semantics without approved mapping/tests. |
| Rotation Radar | T-1080 says the page is consumer-ready at component/source level; component tests and route smokes cover consumer-safe copy, family-rollup fallback, collapsed detail, and no trading wording. Remaining gap is stale launch smoke coverage. Tests readiness: Yes. Implementation readiness: No. | Consumer-safe default is ready now. Existing surface already translates signal/freshness/readiness into product copy. New visible source/fallback/stale/partial badges remain deferred. | Taxonomy/provider debug language, raw diagnostics, raw theme-flow internals, and trust-source internals must stay collapsed or hidden from default UI. | Current consumer-safe docs/tests boundary is locked for the current surface. No immediate write is required from this matrix. Optional read-only consistency audit only; docs/tests/contracts only if a specific regression or contract gap is found. | Frontend badge/disclosure implementation, provider/runtime/API changes, ranking semantics, authority inference, new route semantics. |
| Single-stock evidence | T-1059 and T-1077 say backend/API metadata transport is ready enough to preserve item metadata, and the frontend adapter preserves opaque item blocks, but Home only consumes `fundamentalsSummary`. Display boundary is not ready for visible metadata badges. Tests/contracts ready for adapter-preservation locks. Implementation readiness: No. | Current safe default is the existing `fundamentalsSummary`/report-side consumer-safe summary only. Visible source/freshness/fallback/stale/partial badges are deferred. | Item-level provider/source/sourceConfidence/authority/debug/raw-record metadata must stay hidden; only consumer-safe summary/provenance projections may be shown. | Current adapter/consumer-boundary docs/tests are locked where applicable. No immediate write is required from this matrix. Optional read-only consistency audit only; docs/tests/contracts only if a specific regression or contract gap is found. | Badge implementation, API/source/type behavior changes, provider authority inference, raw metadata UI, runtime/provider/cache changes. |
| Portfolio pricing/evidence | T-1087 says Portfolio is ready for product-safe stale/delayed pricing display today, but not ready for raw metadata display. Existing tests already cover safe copy and hidden raw diagnostics; the smallest safe next step is tests-only boundary locking. Implementation readiness: No. | Consumer-safe default is ready now for bounded stale/delayed pricing and FX states. Visible source/freshness/fallback/stale/partial badge expansion remains deferred. | `sourceRefs`, reason codes, provider/source/cache/runtime/debug/admin diagnostics, raw fallback tokens, and authority inference stay hidden from default consumer UI. | Current consumer-boundary docs/tests are locked for product-safe pricing/evidence display. No immediate write is required from this matrix. Optional read-only consistency audit only; docs/tests/contracts only if a specific regression or contract gap is found. | New frontend badge work, adapter/schema narrowing, provider/runtime/cache changes, FX/accounting behavior changes, authority inference. |
| Scanner explainability | T-1047 says score caps are live rank-affecting semantics and must not be treated as display-only. T-1078 says consumer-safe IA is ready for docs work, not for new UI implementation or scoring/ranking change. Tests/contracts exist; the immediate safe gap is IA/copy placement, not runtime semantics. Implementation readiness: No. | Current consumer-safe default can rely on bounded row/disclosure patterns already present. New visible raw metadata badges remain deferred. | Raw cap mechanics, provider/source authority fields, provider observation, admin reason codes, raw diagnostics, traces, and ranking internals stay admin-only/internal. | Current IA/docs boundary is locked for consumer-safe summary/disclosure/admin-only separation. No immediate write is required from this matrix. Optional read-only consistency audit only; docs/tests/contracts only if a specific regression or contract gap is found. | Scoring/ranking/cap changes, UI badge implementation without approved IA/tests, provider/cache/runtime changes, raw metadata exposure, authority inference. |
| Options market-structure | T-1086, T-1090, and T-1097 define `optionsMarketStructureObservation` as observation-only with `observationOnly=true` and `decisionGrade=false`, plus a prerequisite manifest and deferred implementation checklist. Docs/contracts ready; implementation readiness: No. | No consumer-facing implementation is approved. Safe default is blocked/deferred except future observation-only wording inside Options Lab after later scoped approval. Visible badges remain deferred. | Provider proof, entitlement/redistribution/decision-use rights, methodology internals, raw diagnostics, cache/runtime semantics, and any decision-grade implication stay internal/admin-only until separately approved. | Current observation-only contract/prerequisite boundary is locked with implementation deferred. No immediate write is required from this matrix. Optional read-only consistency audit only; docs/tests/contracts only if a specific regression or contract gap is found. | API/provider/cache/runtime implementation, frontend rendering, badge work, methodology-as-authority claims, decision-grade or recommendation-grade adoption, provider/source authority inference. |

## Cross-surface stop signs

The following are deferred or forbidden across all rows above unless a later
task explicitly opens the protected domain and names the allowed files:

- visible source/freshness/fallback/stale/partial badges;
- provider/source authority inference;
- provider routing or runtime-order changes;
- cache TTL/SWR/cold-start/fallback semantics changes;
- score/ranking/filter/selection/order semantics;
- new API exposure that promotes currently internal metadata into product UI;
- raw provider/debug/schema/reason-code/runtime metadata in consumer-default UI.

## Current safe follow-up queue

Current-state boundary check:

- Market Overview: current docs/tests boundary is already locked for the
  currently consumed readiness/evidence subset. No immediate write is required
  from this matrix.
- Liquidity Monitor: current consumer-safe docs/tests boundary is already
  locked. No immediate write is required from this matrix.
- Rotation Radar: current consumer-safe docs/tests boundary is already locked
  for the current surface. No immediate write is required from this matrix.
- Portfolio pricing/evidence: current consumer-boundary docs/tests are already
  locked for product-safe pricing/evidence display. No immediate write is
  required from this matrix.
- Single-stock evidence: current adapter/consumer-boundary docs/tests are
  already locked where applicable. No immediate write is required from this
  matrix.
- Scanner explainability: current IA/docs boundary is already locked for
  consumer-safe summary/disclosure/admin-only separation. No immediate write is
  required from this matrix.
- Options market-structure: current observation-only contract/prerequisite
  boundary is already locked with implementation deferred. No immediate write
  is required from this matrix.

Only safe future follow-up from this matrix:

1. No immediate write is required for evidence badges. Visible
   source/freshness/fallback/stale/partial badges remain deferred.
2. Optional read-only audit only: confirm all evidence-boundary docs/tests are
   referenced consistently across the relevant surface docs, contracts, and
   manifests.
3. Future work may proceed only in separately scoped protected-domain tasks for
   provider/runtime/API/scoring/UI badge work. Provider/source authority
   inference remains forbidden unless such a task explicitly reopens that
   domain.

## Out of scope for this matrix

This document does not approve:

- source code changes;
- tests that alter runtime semantics instead of locking current behavior;
- API/provider/cache/runtime/auth/package/config/CI work;
- frontend badge/disclosure implementation;
- scoring/ranking/provider routing behavior changes.
