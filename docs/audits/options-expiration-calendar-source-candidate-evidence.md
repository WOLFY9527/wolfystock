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

## Locked Invariants

- no runtime behavior changes
- no source code changes
- no tests changed
- no provider or source authority upgrade
- no gate, recommendation, `decisionGrade`, or API behavior changes
- no live calls
- no broker, order, trading, or portfolio mutation
