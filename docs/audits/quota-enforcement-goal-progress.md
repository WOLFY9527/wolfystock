# Quota & Billing Enforcement V1 Pilot Progress

Date: 2026-06-11
Status: guarded private-beta pilot architecture, disabled by default

This note tracks the current quota enforcement v1 goal. It separates dry-run
diagnostics, guarded private-beta route pilot behavior, and future public-launch
enforcement. It is not public-launch approval and it is not a provider billing
authority statement.

## Current Boundary

- Route family: `analysis`
- Route boundary: `POST /api/v1/analysis/analyze`
- Eligible request shape: authenticated, auth-enabled, non-transitional, sync,
  single-stock analysis only.
- Explicitly out of scope: guest, auth-disabled bootstrap, transitional users,
  async analysis, scanner, agent/chat, options, provider circuit, market cache,
  portfolio, broker/order, frontend consumer spend caps, public launch.

## Flag Contract

All flags default to disabled or fail-open posture:

- `WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_RELEASE_PILOT_ENABLED=false`
- `WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_RELEASE_OWNER_IDS=`
- `WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_RELEASE_ROLLBACK_ENABLED=false`
- `WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_FAILURE_POLICY=fail_open`
- `WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_KNOWN_COST_CONSUME_ENABLED=false`

Pilot entry requires both
`WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_RELEASE_PILOT_ENABLED=true` and an
explicit owner allowlist match. The rollback flag immediately makes the route
out of scope even if the pilot flag and owner allowlist are configured.

## State Model

### Dry-Run

Dry-run surfaces remain read-only diagnostics. They do not create reservations,
consume reservations, release reservations, call providers, call LLMs, or block
routes. `POST /api/v1/admin/cost/quota-dry-run` remains diagnostic evidence and
must keep `liveEnforcement=false`.

### Private-Beta Pilot

The private-beta pilot is guarded and route-local. When the pilot flag and owner
allowlist match, the sync single-stock route attempts reserve before analysis and
releases in a `finally` path. Reserve failure defaults to fail-open. A
fail-closed reserve failure block is available only through the explicit
`WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_FAILURE_POLICY=fail_closed` flag.

Known-cost consume propagation is separate and default-off. When
`WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_KNOWN_COST_CONSUME_ENABLED=true`, a successful
route reservation is passed into the LLM usage persistence seam so the existing
cost-ledger reservation reconciliation can consume on priced usage. If usage
pricing is not known or analysis fails before usage persistence, the route-level
`finally` release remains the cleanup path.

### Public-Launch Enforcement

Public-launch enforcement remains NO-GO. This pilot does not approve broad route
blocking, public spend caps, provider billing authority, invoice-authoritative
reconciliation, provider circuit enforcement, or frontend consumer spend-cap
claims.

## Operator Evidence

Operators can inspect pilot posture without raw IDs through
`GET /api/v1/admin/ops/status` under `quotaCostAdvisoryStatusSummary.summary`
and `analysisSyncRoutePilot`.

The status exposes only bounded evidence:

- route boundary label;
- pilot status label;
- booleans for configured/effective enablement, rollback, known-cost consume
  flag state, effective known-cost consume propagation, and public
  launch/provider billing authority disclaimers;
- owner allowlist configured boolean and count bucket;
- flag names;
- explicit `rawReservationIdsExposed=false`,
  `idempotencyMaterialExposed=false`, and
  `ownerAllowlistValuesExposed=false`.

It must not expose raw reservation IDs, idempotency keys or hashes, owner
allowlist values, session IDs, tokens, raw exception text, provider payloads, or
secrets.

## Implemented Contract Tests

- Success reserve/release keeps response shape unchanged and omits raw
  reservation or idempotency material from execution metadata.
- Default reserve-only pilot does not pass reservation IDs to the known-cost
  cost path.
- Explicit known-cost consume flag threads the reservation ID only through the
  backend persistence seam.
- Reserve failure defaults fail-open.
- Reserve failure and reserve exception can fail-closed only with explicit
  policy flag.
- Release failure fails open and preserves original success/error behavior.
- Retry identity is deterministic and built only from bounded route fields.
- Rollback flag disables pilot eligibility.
- Owner isolation excludes non-allowlisted owners.
- Admin ops status reports sanitized pilot state without owner IDs or secrets.
- Warning logs redact reservation IDs, token-like fragments, and idempotency
  material.

## Remaining NO-GO Blockers

- No public-launch approval.
- No broad route enforcement or global quota blocking.
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
- set `WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_RELEASE_ROLLBACK_ENABLED=true`;
- leave `WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_KNOWN_COST_CONSUME_ENABLED=false` to keep
  known-cost consume propagation disabled.

Live enforcement is not enabled by default.
