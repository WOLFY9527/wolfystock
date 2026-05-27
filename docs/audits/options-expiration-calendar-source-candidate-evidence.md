# Expiration Calendar Source Candidate Evidence

Status: Draft checklist for future evidence collection only
Scope: docs-only packet definition for a future `ExpirationCalendarSourceCandidateEvidence`
Non-goal: no authority grant, no runtime wiring, no registry/provider/gate/API change

## Purpose

Use this packet to collect observation-only evidence before any future expiration-calendar source onboarding work.

This packet is:

- evidence collection only
- diagnostic-only
- candidate-only
- not an authority grant
- not decision readiness
- not gate or recommendation readiness

This packet must not be used as proof that any current provider or source is authoritative.

## Current Repo Status

Current repository state remains observation-only and non-authoritative:

- fixture-backed API/service expiration rows are observation-only
- Tradier adapter-contract expiration rows are observation-only
- runtime diagnostics are local/offline scaffolding
- no current path proves OCC/OPRA/exchange/licensed-source authority

Do not read current fixture rows, adapter-contract rows, provider IDs, or runtime diagnostic output as proof of production authority.

## Required Field Groups

Every future packet should capture sanitized evidence for all groups below.

### 1. Source identity and provenance chain

- candidate source name
- provider or distributor name
- upstream provenance chain
- source class
- market/region coverage claim
- evidence capture method
- sanitized document or contract reference

### 2. OCC / OPRA / exchange / licensed-source backing

- claimed OCC backing, if any
- claimed OPRA backing, if any
- claimed exchange backing, if any
- claimed licensed-source backing, if any
- sanitized proof reference for each claim
- explicit `unverified` state when backing is not proven

Do not infer authority from branding, coverage, or provider self-description.

### 3. Venue and calendar scope

- covered venue or venue family
- supported symbol universe
- supported product class
- expiration-calendar scope boundaries
- unsupported venue or product gaps

### 4. Entitlement, license, redistribution, and decision-use rights

- entitlement requirements
- license tier
- redistribution rights
- storage/retention limits
- internal display rights
- internal decision-use rights
- explicit restrictions or prohibitions

### 5. Production vs sandbox

- environment type: production or sandbox
- whether evidence came from production docs, sandbox docs, or contractual language only
- environment-specific limitations

### 6. Delayed vs live status

- delayed/live claim
- documented delay policy
- delayed labels or disclaimers
- whether status is proven or unverified

### 7. As-of, freshness, SLA, and max-age policy

- source `asOf`
- freshness statement
- update cadence
- SLA or service expectation
- permissible max-age policy for future observation-only use
- stale-data handling notes

### 8. Expiration dates, count, and range

- sample expiration dates
- observed expiration count
- observed earliest/latest range
- symbol-level variation notes
- missing-date or truncation evidence

### 9. Expiration taxonomy

- weekly
- monthly
- quarterly
- standard
- LEAPS
- special expirations

The packet should show whether each taxonomy is proven, missing, partial, or unverified.

### 10. Adjusted deliverable and corporate-action proof

- split-adjustment handling evidence
- adjusted deliverable evidence
- contract multiplier handling evidence
- corporate-action impact notes
- known limitations or unknowns

### 11. OCC memo or equivalent reference

- OCC memo reference when applicable
- equivalent adjustment notice when OCC memo is not the source
- sanitized citation or identifier
- explicit gap when no reference is available

### 12. Sanitized error and audit state

- sanitized error classes
- blocked or missing evidence reasons
- audit capture timestamp
- reviewer or collection owner
- notes on unresolved ambiguity

## External Verification Worksheet

Use this worksheet before any future feasibility claim about OCC/OPRA/exchange/licensed expiration-calendar access.

| Check | Required evidence | Status |
| --- | --- | --- |
| Source identity | Legal source name, distributor/provider name, product/SKU name, sanitized contract/doc reference | `verified` / `partial` / `unverified` |
| Provenance chain | Upstream-to-downstream chain from original source to current distributor, including any sublicense hop | `verified` / `partial` / `unverified` |
| OCC / OPRA / exchange / licensed-source backing | Documented proof of OCC, OPRA, exchange, or other licensed-source backing; otherwise mark explicitly unverified | `verified` / `partial` / `unverified` |
| Entitlement / license / use rights | Entitlement tier, license scope, account/org boundary, allowed internal use | `verified` / `partial` / `unverified` |
| Redistribution and decision-use rights | Written proof for redistribution, storage, internal display, and decision-support use; note prohibitions explicitly | `verified` / `partial` / `unverified` |
| Live vs delayed status | Written live/delayed statement, delay window, label/disclaimer requirements | `verified` / `partial` / `unverified` |
| Production vs sandbox status | Proof whether evidence came from production, sandbox, mock, or contract-only materials | `verified` / `partial` / `unverified` |
| As-of / freshness / SLA / max-age policy | `asOf`, cadence, SLA, freshness language, max-age policy, stale-data handling terms | `verified` / `partial` / `unverified` |
| Expiration taxonomy source | Source proof for weekly/monthly/quarterly/standard/LEAPS/special taxonomy definitions and coverage | `verified` / `partial` / `unverified` |
| Adjusted deliverable / corporate-action / OCC memo evidence | Adjustment handling proof, deliverable/multiplier evidence, corporate-action notes, OCC memo or equivalent reference | `verified` / `partial` / `unverified` |

Suggested capture notes:

- record the exact as-of date for every external document or contract reference
- mark missing proof as `unverified`, not inferred
- treat provider marketing copy and adapter-contract shape as non-authoritative
- keep citations sanitized and prompt-friendly

## Must Not Proceed To Implementation Until Verified

- [ ] Source identity is verified with a sanitized source reference.
- [ ] Provenance chain is verified end to end.
- [ ] OCC / OPRA / exchange / licensed-source backing is verified, or the gap is still blocking.
- [ ] Entitlement / license / use rights are verified for intended internal use.
- [ ] Redistribution and decision-use rights are verified.
- [ ] Live vs delayed status is verified.
- [ ] Production vs sandbox status is verified.
- [ ] As-of / freshness / SLA / max-age policy is verified.
- [ ] Expiration taxonomy source is verified.
- [ ] Adjusted deliverable / corporate-action / OCC memo evidence is verified.

If any box remains unchecked, do not proceed to provider integration, runtime projection, or authority policy work.

## Forbidden Authority Outputs

This packet must not emit, imply, or unlock any of the following:

- `authorityGrant`
- `providerDecisionAuthority`
- `recommendationAuthority`
- `decisionGrade`
- `gateDecision`
- `sourceAuthorityAllowed`
- provider routing
- live-call enablement

Coverage, provider capability metadata, provider self-claims, or checklist completeness must not be treated as authority.

## Mocked Test Expectations For Later Inert Contract Work

If a later task adds an inert contract for this packet, mocked tests should prove:

- candidate packet exists
- `diagnosticOnly=true`
- `candidateOnly=true`
- `authorityGrant=false`, or no authority field exists at all
- all current or blocked provider IDs remain non-authoritative
- coverage does not grant authority
- provider capability metadata does not grant authority
- provider self-claims do not grant authority

## Later Implementation Boundary

The first future code task, if separately approved, should be contract-only and inert.

Allowed first step:

- add a minimal `ExpirationCalendarSourceCandidateEvidence` contract shape

Not allowed in that first code task:

- provider adapter work
- live calls
- source registry changes
- runtime diagnostic projection
- gates or API changes

Any provider integration, authority policy work, runtime wiring, registry work, or gate/API behavior change requires separate approval and separate validation.

## Practical Checklist

Before any observation-only implementation is proposed, confirm:

- provenance is documented with a sanitized evidence chain
- OCC/OPRA/exchange/licensed-source backing is proven or explicitly marked unverified
- venue/calendar scope is bounded
- entitlement and decision-use rights are documented
- production vs sandbox status is explicit
- delayed vs live status is explicit
- freshness and max-age expectations are explicit
- expiration count/range and taxonomy evidence are captured
- adjusted deliverable and corporate-action evidence are captured
- OCC memo or equivalent references are linked when applicable
- sanitized error/audit state is defined
- no authority, gate, recommendation, routing, or live-enable field is introduced

## Safe Future Sequence

1. External source/license verification
   Confirm source identity, provenance, rights, freshness, taxonomy, and adjustment evidence using the worksheet above.
2. Docs update with verified source facts
   Update this document only after verified facts exist; do not backfill assumptions or provider self-claims.
3. Read-only implementation audit
   Inspect current adapter, diagnostic, API, and policy boundaries without editing runtime code.
4. Inert adapter/packet task only if approved
   If separately approved, limit the first implementation to inert packet/contract shaping with no live calls and no authority grant.
5. Runtime projection only after inert contract validation
   Any runtime-facing projection must wait until the inert contract is validated and still remains diagnostic-only.
6. Authority grant only in a separate future policy task
   Any authority decision requires a distinct policy task with explicit approval, verified facts, and separate validation.

## Locked Invariants

- no runtime behavior changes
- no source code changes
- no tests changed
- no provider or source authority upgrade
- no gate, recommendation, `decisionGrade`, or API behavior changes
- no live calls
- no broker, order, trading, or portfolio mutation
