# Trust Evidence Snapshot V1 Phase-0 Contract

Status: docs-only phase-0 plan

Date: 2026-06-09

Purpose: define a small shared trust/evidence snapshot boundary before any
backend, API, or frontend implementation work starts.

Non-goals:

- no runtime/provider/cache/fallback behavior changes
- no API rollout in this task
- no UI implementation in this task
- no change to scoring, ranking, recommendation, or no-advice semantics

Related docs:

- `docs/data-reliability/provider-source-confidence-contract.md`
- `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`

## Why This Exists

WolfyStock already carries nearby concepts such as `evidenceSnapshot`,
`sourceFreshnessEvidence`, and `sourceProvenanceFrame`, but the fields and
display boundaries are uneven. The biggest current gap is trust evidence:

- provenance is not projected consistently
- freshness/fallback/stale/partial semantics are repeated
- consumer-safe mapping is route-specific
- admin diagnostics and consumer-safe copy can drift into each other

Phase 0 only defines the contract so later tasks stay bounded.

## Boundary Model

Use three layers. Do not skip layers.

### 1. Runtime/Internal Evidence

Source provider metadata, cache metadata, route/debug codes, raw reason codes,
retry/fallback details, and provider attempt diagnostics remain internal or
admin-gated only.

Examples:

- provider ids and provider families
- route paths and endpoint names
- cache/fallback depth
- raw `snake_case` reason codes
- raw degraded-state buckets used for debugging

### 2. Shared Backend DTO

Future backend tasks should define one additive DTO:
`TrustEvidenceSnapshotV1`.

This DTO is the only payload allowed to cross from backend evidence assembly
into frontend mapping for consumer product routes.

Required fields:

| Field | Type | Notes |
| --- | --- | --- |
| `contractVersion` | string | Fixed value: `trust_evidence_snapshot_v1` |
| `surfaceKey` | string | Named surface, for example `market_overview` |
| `entityKey` | string or null | Card/symbol/domain key when applicable |
| `generatedAt` | ISO datetime | When the snapshot was assembled |
| `asOf` | ISO datetime or date or null | Best user-meaningful observation time |
| `availabilityState` | enum | `available`, `updating`, `delayed`, `partial`, `insufficient`, `observation_only`, `unavailable` |
| `freshnessState` | enum | `live`, `fresh`, `delayed`, `cached`, `stale`, `fallback`, `partial`, `synthetic`, `unavailable`, `unknown` |
| `sourceClass` | enum | `official_public`, `licensed_authorized`, `public_proxy`, `local_cache`, `synthetic`, `unknown` |
| `hasFallback` | boolean | True when replacement/non-primary path was used |
| `isStale` | boolean | True when freshness policy is exceeded |
| `isPartial` | boolean | True when required evidence family is incomplete |
| `isSynthetic` | boolean | True for fixture/inferred/generated values |
| `isAdminOnlyDetail` | boolean | True only for fields that must never flow to consumer mapping directly |
| `consumerState` | enum | `AVAILABLE`, `UPDATING`, `DELAYED`, `PARTIAL`, `INSUFFICIENT`, `OBSERVATION_ONLY`, `UNAVAILABLE` |
| `consumerMessageKey` | string | Bounded translation key, not free-form debug text |
| `consumerBadgeKeys` | string[] | Bounded keys only, see badge rules below |
| `adminDiagnosticRefs` | string[] | Sanitized refs for admin drill-down, not raw payloads |

Optional additive fields:

- `coverageRatio`
- `confidenceWeight`
- `primarySourceLabel`
- `lastSuccessfulAt`
- `missingEvidenceFamilies`
- `degradationFamilies`

Optional fields must still obey the leakage rules below.

### 3. Frontend Mapping Boundary

Frontend should not derive trust semantics from raw provider/runtime fields once
the DTO exists.

Consumer mapping input:

- `TrustEvidenceSnapshotV1` only

Consumer mapping output:

- product state chip or label
- bounded freshness badge
- bounded source/provenance badge when approved for consumer use
- short explanatory copy
- optional "as of" timestamp

Admin mapping input:

- `TrustEvidenceSnapshotV1`
- a separate admin-only diagnostic DTO if needed

Admin routes may show more detail, but only behind explicit admin surfaces and
still without secrets or raw provider payloads.

## Consumer/Admin Separation

Consumer surfaces should answer:

- Can this feature be used?
- How current is the data?
- Is the result limited, partial, or observation-only?

Consumer surfaces should not answer:

- Which provider class failed first?
- Which endpoint or route rejected the request?
- Which raw reason code fired?
- Which cache bucket or circuit state triggered fallback?

Admin surfaces may show:

- source class
- sanitized degradation family
- bounded diagnostic refs
- bounded reason family summaries
- fallback/stale/partial counts

Admin surfaces must still not show by default:

- raw request/response payloads
- secrets or tokens
- raw stack traces
- unbounded free-form provider/debug text copied from runtime

## Badge Rules

Future implementation must keep badge derivation centralized.

Allowed consumer badge keys:

- `source_current`
- `source_delayed`
- `source_stale`
- `source_partial`
- `source_fallback`
- `source_unavailable`
- `observation_only`

Consumer badge rules:

- `source_stale` only when `isStale=true`
- `source_partial` only when `isPartial=true`
- `source_fallback` only when `hasFallback=true`
- degraded badges may co-exist, but `consumerState` must reflect the strongest
  user-facing limitation
- no consumer badge may expose provider names, route names, or raw reason codes

Admin badges can be richer, but must stay bounded and sanitized.

## Forbidden Raw Leakage

The following must not appear in default-visible consumer DOM, accessibility
labels, or consumer-safe API copy once V1 is adopted.

### Raw reason codes

- `stale_official_row`
- `cache_stale`
- `fallback_source`
- `proxy_only_missing_real_source`
- `official_overlay_stale_using_proxy`
- `routeRejected`
- `fallback_used`

### Provider/runtime internals

- `yfinance_proxy`
- `fred`
- `polygon`
- `tushare`
- `MarketCache`
- `providerRuntime`
- `scoreContributionAllowed`
- `sourceAuthorityAllowed`

### Debug route and endpoint details

- `/api/v1/market/...`
- `/api/v1/admin/...`
- `source-provenance:...`
- `market:liquidity`
- `market:marketregime`

These examples are not exhaustive. The rule is broader: no raw `snake_case`
reason codes, no provider internals, and no debug route codes in default
consumer-visible copy.

## Proposed Validation Strategy

Future implementation tasks should validate at three boundaries.

### Backend DTO validation

- unit tests for DTO assembly from representative live/delayed/stale/fallback/
  partial/unavailable inputs
- fail-closed tests when required fields are missing
- additive-schema tests so future optional fields do not break consumers

### Frontend consumer mapping validation

- unit tests that map DTO states into approved consumer copy/badges
- route tests that assert no forbidden raw leakage in default-visible DOM
- accessibility-label checks for the same forbidden vocabulary

### Admin projection validation

- unit tests for bounded admin summaries
- route tests confirming admin-only details stay gated off consumer routes
- tests that admin refs stay sanitized and do not expose secrets/payloads

### Visual/browser validation for later UI tasks

- desktop and mobile proof on impacted routes
- source/freshness/fallback/stale/partial badges render consistently
- no horizontal overflow
- no raw/debug/provider/schema leakage in visible copy

## Implementation Constraints For Later Tasks

Later tasks must keep these boundaries unchanged unless explicitly re-scoped:

- no provider order changes
- no fallback behavior changes
- no MarketCache TTL/SWR/cold-start changes
- no scoring/ranking/recommendation changes
- no new buy/sell/trade posture
- no stored API contract replacement without additive compatibility review

## Decision Summary

Phase 0 adopts one bounded trust/evidence snapshot contract:

- internal/runtime evidence remains separate
- backend emits one shared DTO boundary
- frontend consumer mapping accepts only that DTO
- admin detail is separated and gated
- raw reason/provider/debug leakage is explicitly forbidden

This is enough to start narrow implementation tasks without reopening product
semantics on every route.
