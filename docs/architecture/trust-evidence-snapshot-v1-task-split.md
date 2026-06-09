# Trust Evidence Snapshot V1 Future Task Split

Status: phase-0 backlog

Date: 2026-06-09

Scope: future bounded tasks only. This file does not authorize runtime changes
inside protected domains.

## Task 1: Canonical DTO Shape

Goal:

- define `TrustEvidenceSnapshotV1` in one backend schema location

Write scope:

- backend schema/docs/tests only

Protected-domain notes:

- do not change provider order
- do not change fallback execution
- do not change cache semantics
- additive schema only

Expected validation:

- focused schema tests
- additive serialization tests
- `git diff --check`

## Task 2: Shared Consumer Mapping Utility

Goal:

- create one frontend trust-evidence mapping utility from DTO to consumer-safe
  state, badges, and copy keys

Write scope:

- frontend mapping utility/tests only

Protected-domain notes:

- no route behavior rewrite
- no new provider/debug vocabulary
- no runtime API reshaping beyond consuming the additive DTO

Expected validation:

- focused frontend unit tests
- changed-file lint/typecheck/build if source files change

## Task 3: Shared Forbidden-Leak Guard

Goal:

- add one reusable guard list/test helper covering raw `snake_case` reasons,
  provider internals, and debug route codes

Write scope:

- tests and narrow helper only

Protected-domain notes:

- no runtime behavior changes
- consumer guard must allow approved financial symbols while blocking internal
  diagnostics

Expected validation:

- focused route/component tests
- `git diff --check`

## Task 4: One Consumer Route Pilot

Goal:

- adopt the DTO plus shared mapping on one route family first

Recommended pilot order:

1. Market Overview
2. Home evidence strip
3. Liquidity/Rotation

Protected-domain notes:

- no provider fallback logic changes
- no score/recommendation/no-advice changes
- browser proof required because copy and badges are default-visible

Expected validation:

- impacted frontend unit tests
- impacted route e2e/browser proof
- changed-file lint/typecheck/build

## Task 5: Admin Projection Pilot

Goal:

- define one admin-safe diagnostic projection that reuses the same snapshot
  without leaking raw payloads

Write scope:

- admin projection utility/tests and one admin route family

Protected-domain notes:

- admin may be richer than consumer, but still must be sanitized
- no secrets, raw payloads, or free-form provider errors

Expected validation:

- focused admin unit tests
- impacted admin route tests
- changed-file lint/typecheck/build if frontend source changes

## Task 6: Cross-Route Adoption Sweep

Goal:

- migrate remaining routes that currently repeat freshness/provenance/fallback
  mapping logic

Protected-domain notes:

- do not couple multiple protected runtime changes into the same sweep
- keep adoption route-by-route with local verification

Expected validation:

- route-family focused tests
- browser proof for default-visible routes
- release-grade validation only if the sweep reaches shared route shells

## Order And Stop Rules

Recommended order:

1. DTO shape
2. consumer mapping utility
3. forbidden-leak guard
4. one consumer pilot
5. one admin pilot
6. cross-route sweep

Stop and rescope if a future task requires:

- provider runtime order changes
- fallback semantics changes
- MarketCache semantics changes
- scoring/ranking/recommendation changes
- contract-breaking API replacement

Those are separate protected-domain tasks, not part of this phase-0 plan.
