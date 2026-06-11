# Quota Advisory Reserve/Release Pilot Salvage

Date: 2026-06-11
Status: advisory-only salvage, disabled by default

This note replaces the broader quota and billing enforcement checkpoint for
this branch. The merge candidate is limited to a route-local reserve/release
pilot and sanitized admin evidence. It is not public-launch approval, not live
quota enforcement, not a billing-authority statement, not consume wiring, and
not route blocking.

## Current Boundary

- Route family: `analysis`
- Route boundary: `POST /api/v1/analysis/analyze`
- Eligible request shape: authenticated, auth-enabled, non-transitional, sync,
  single-stock analysis only.
- Explicitly out of scope: guest, auth-disabled bootstrap, transitional users,
  async analysis, scanner, agent/chat, options, provider runtime/cache/fallback,
  market cache, portfolio, broker/order, external notification sending,
  frontend consumer spend caps, public launch.

## Flag Contract

Only these pilot controls are part of this salvage branch:

- `WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_RELEASE_PILOT_ENABLED=false`
- `WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_RELEASE_OWNER_IDS=`
- `WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_RELEASE_ROLLBACK_ENABLED=false`

Pilot entry requires both
`WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_RELEASE_PILOT_ENABLED=true` and an
explicit owner allowlist match. The rollback flag immediately makes the route
out of scope even if the pilot flag and owner allowlist are configured.

## Advisory Pilot Behavior

When the pilot flag and owner allowlist match, the sync single-stock route
attempts reserve before analysis and releases in a `finally` path when a
reservation was created. Reserve failure, reserve exceptions, and release
failure are advisory and fail open. They must not change the original analysis
success or error behavior.

The response shape remains unchanged. Responses must not expose reservation
IDs, idempotency material, owner values, session IDs, tokens, provider payloads,
or raw exceptions.

This salvage branch intentionally does not pass reservation identity into
`AnalysisService`, the pipeline, the analyzer, LLM usage persistence, or ledger
reconciliation. Known-cost consume propagation is not included.

## Admin Evidence

Operators can inspect pilot posture without raw IDs through
`GET /api/v1/admin/ops/status` under `quotaCostAdvisoryStatusSummary.summary`
and `analysisSyncRoutePilot`.

The status exposes only bounded evidence:

- route boundary label;
- pilot status label;
- booleans for configured/effective enablement, rollback, advisory reserve
  failure behavior, consume propagation disabled, public launch disabled,
  live enforcement disabled, and provider/billing authority disabled;
- owner allowlist configured boolean and count bucket;
- flag names;
- explicit `rawReservationIdsExposed=false`,
  `idempotencyMaterialExposed=false`, and
  `ownerAllowlistValuesExposed=false`.

It must not expose raw reservation IDs, idempotency keys or hashes, owner
allowlist values, session IDs, tokens, raw exception text, provider payloads, or
secrets. The status endpoint remains read-only and must not call reserve,
release, consume, provider runtime, external HTTP, notification, or cleanup
paths.

## Implemented Contract Tests

- Success reserve/release keeps response shape unchanged and omits raw
  reservation or idempotency material from execution metadata.
- Route analysis calls do not receive reservation identity.
- Reserve failure and reserve exception fail open.
- Release failure fails open and preserves original success/error behavior.
- Retry identity is deterministic and built only from bounded route fields.
- Rollback flag disables pilot eligibility.
- Owner isolation excludes non-allowlisted owners.
- Admin ops status reports sanitized pilot state without owner IDs or secrets.
- Warning logs redact reservation IDs, token-like fragments, and idempotency
  material.

## Remaining NO-GO Blockers

- No public-launch approval.
- No live enforcement.
- No broad route enforcement or global quota blocking.
- No consume propagation.
- No consumer-facing spend-cap claim.
- No provider invoice or provider billing authority claim.
- No crash/timeout reconciliation beyond route-level release and existing
  terminal-idempotent lifecycle behavior.
- No multi-route quota contract.
- No staging/private-beta acceptance evidence package has been approved.
- No provider circuit enforcement approval.

## Rollback

Any one of the following returns the route to out-of-scope behavior:

- leave `WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_RELEASE_PILOT_ENABLED=false`;
- remove the owner from `WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_RELEASE_OWNER_IDS`;
- set `WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_RELEASE_ROLLBACK_ENABLED=true`.

Live enforcement, consume propagation, and request blocking are not enabled by
this branch.
