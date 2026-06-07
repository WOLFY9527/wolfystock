# Provider Source-Confidence Contract

Status: docs-only contract for future evidence metadata.

Date: 2026-06-07

This contract defines how WolfyStock should describe provider capability,
source confidence, freshness, degraded data states, and display authority
before any future scoring, ranking, provider routing, API, or UI work uses that
metadata.

This document is inert. It does not change provider runtime behavior, provider
order, fallback behavior, MarketCache semantics, API schemas, frontend
surfaces, scoring, ranking, or stored contracts.

## Related Authority

- `docs/provider-data/README.md`
- `docs/operations/provider-capability-metadata.md`
- `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`
- `docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`
- `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`

If these documents conflict with this contract, use the stricter rule and fail
closed until a protected-domain task explicitly resolves the conflict.

## Core Rule

Provider/source authority must never be inferred.

A provider name, source label, source type, freshness label, cache hit,
successful response, high coverage value, or low-latency response is not enough
to grant authority, score contribution, ranking influence, route preference,
right-to-display, or consumer-facing badge eligibility.

Every future use must answer these questions separately:

1. What capability was the provider allowed to claim?
2. What observed source-confidence metadata exists for this payload?
3. How fresh is the observed payload?
4. Is the payload fallback, stale, partial, synthetic, unavailable, or unknown?
5. Is this evidence allowed for the named authority surface?
6. Is the data allowed to be displayed to this audience?
7. Is the target consumer, admin, score, ranking, or runtime use explicitly
   authorized?

If any answer is missing or ambiguous, the contract must fail closed.

## Vocabulary

### Source Confidence

`sourceConfidence` means bounded metadata about how an observed payload should
be interpreted. It may describe provenance, freshness, coverage, degradation,
and confidence caps after a source has already been observed.

It cannot mean:

- provider quality;
- legal/licensing clearance;
- right-to-display;
- decision-grade evidence;
- score/ranking eligibility;
- provider routing preference;
- runtime provider enablement;
- live-call authorization;
- cache freshness authority;
- investment or trading confidence.

### Confidence Weight

`confidenceWeight` is a bounded evidence-quality value or cap. It is not a
score, rank, recommendation, trade signal, or provider priority.

Low confidence may explain limited use. High confidence cannot grant use unless
the surrounding authority contract explicitly allows that use.

### Coverage

`coverage` describes completeness for the named evidence family. It is not the
same as freshness, source authority, or right-to-display.

Partial coverage must stay partial even when the provider is otherwise capable.

### Source Classification

Source classification describes the family a payload came from, such as
official/public, licensed/authorized, public proxy, unofficial proxy, local
cache, local inference, synthetic fixture, or missing source.

Classification is descriptive only. It does not prove entitlement, provider
reliability, live status, score eligibility, or right-to-display.

### Authority Fields

Authority fields must be surface-specific and explicit.

Examples:

- source authority for a named evidence family;
- score contribution for a named scoring path;
- right-to-display for a named audience and product surface;
- admin diagnostic visibility for a gated maintenance route.

No authority field may be reused as an alias for another authority field.
`sourceAuthorityAllowed`, `scoreContributionAllowed`, `authorityGrant`,
`scoreReliabilityAllowed`, and right-to-display status are not
interchangeable.

## Separation Of Concerns

### Provider Capability

Provider capability is static or advisory metadata about what a provider may be
able to support under reviewed conditions.

It may describe:

- provider identity;
- supported domains and markets;
- expected cadence or freshness class;
- quota or cost class;
- credential or entitlement needs;
- recommended cache or operator posture;
- known limitations.

It must not decide:

- provider order;
- live-call paths;
- fallback depth;
- timeout/deadline behavior;
- cache TTL/SWR/cold-start behavior;
- source authority;
- score/ranking eligibility;
- right-to-display;
- frontend badge eligibility.

Provider capability without observed source-confidence metadata is
insufficient. Observed source-confidence metadata without provider capability
is also insufficient.

### Data Freshness

Freshness describes the time or freshness state of an observed payload.

Allowed future freshness vocabulary should stay bounded to the existing
families already used by WolfyStock contracts:

- `fresh`
- `live`
- `delayed`
- `cached`
- `stale`
- `partial`
- `fallback`
- `synthetic`
- `unavailable`
- `unknown`

Freshness cannot mean source authority, score authority, provider quality,
right-to-display, or route priority.

`fresh` and `live` may be used only when the underlying contract proves those
states. Degraded evidence must not be relabeled as fresh/live.

### Degraded Data States

These states must stay distinct:

| State | Meaning | Must not imply |
| --- | --- | --- |
| `fallback` | A replacement path or non-primary source was used after the primary path was unavailable, unsuitable, or not used. | Live authority, provider quality, ranking eligibility, or right-to-display. |
| `stale` | The payload is older than the relevant freshness expectation. | Fresh/live status, current market validity, or score authority. |
| `partial` | Coverage is incomplete for the required evidence family. | Fallback, stale, unavailable, or sufficient coverage. |
| `synthetic` | The payload is generated, fixture-like, inferred, or otherwise non-observed as real provider data. | Live provider evidence, official data, or consumer trust badge eligibility. |
| `unavailable` | Required evidence is absent or unusable. | Hidden fallback, zero-confidence success, or permission to synthesize a live-looking value. |
| `unknown` | The contract cannot classify the state safely. | Any positive authority or display grant. |

When several degraded states apply, the projection must preserve the strongest
safety limitation instead of selecting the most favorable label.

### Authority And Right-To-Display

Authority answers whether evidence may be used for a named product or decision
surface. Right-to-display answers whether data may be shown to a named audience
on a named surface.

They are separate from each other and from provider capability, freshness, and
source confidence.

Right-to-display may require owner review for licensing, entitlement,
redistribution, contractual, privacy, or product-risk reasons. It must not be
inferred from:

- successful provider response;
- provider capability metadata;
- `official_public` or similar source classification;
- credential presence;
- cache availability;
- data freshness;
- coverage;
- confidence weight.

If right-to-display is not explicitly established for the audience, consumer
surfaces must receive only a safe unavailable, delayed, partial, or
insufficient product state.

## Consumer-Safe Versus Admin-Only Fields

Consumer-facing product routes must receive translated product states, not raw
provider diagnostics.

### Consumer-Safe Projection

Consumer-safe fields are derived, bounded, and product-language oriented.

Allowed consumer-safe field families:

- product availability status, using the consumer UX vocabulary such as
  `AVAILABLE`, `UPDATING`, `DELAYED`, `PARTIAL`, `INSUFFICIENT`, `PAUSED`, or
  `UNAVAILABLE`;
- coarse confidence posture, such as normal, limited, low, or unavailable;
- last updated/as-of time where the route already supports freshness context;
- one short user-safe explanation;
- feature usability state, such as observation-only, paused, or unavailable.

Consumer-safe projection must not expose provider internals by default. It must
not show raw source-confidence vocabulary as a trust badge.

### Admin-Only Metadata

Admin-only fields may be useful for backstage diagnostics, but must be gated,
sanitized, and absent from consumer-default routes.

Admin-only field families include:

- provider id, provider class name, endpoint name, route path, trace id, cache
  key, fallback depth, retry/circuit state, latency bucket, quota bucket, and
  failure bucket;
- source type, source tier, trust level, entitlement class, provider capability
  row, and credential presence state;
- `sourceAuthorityAllowed`, `scoreContributionAllowed`, `authorityGrant`,
  `scoreReliabilityAllowed`, score-grade eligibility flags, and raw reason
  codes;
- numeric `confidenceWeight`, confidence caps, raw coverage ratios, cap reason,
  degradation reason, fallback/stale/partial/synthetic/unavailable flags, and
  source-confidence validation errors;
- right-to-display review state, license notes, redistribution notes, operator
  review status, and maintainer remediation instructions;
- raw diagnostic JSON after sanitization and only where the admin route
  explicitly allows it.

Admin-only metadata must still not include secrets, raw credentials, cookies,
tokens, request/response bodies, raw provider payloads, raw LLM payloads,
stack traces with sensitive content, or `.env` values.

## Contract Shape For Future Implementations

Any future implementation should be additive and fail-closed.

Minimum metadata posture:

```text
contractVersion: explicit string
diagnosticOnly: true
observationOnly: true
providerRuntimeCalled: false for inert projection helpers
networkCallsEnabled: false for inert projection helpers
marketCacheMutation: false for inert projection helpers
authorityGrant: false unless a protected-domain task grants a named authority
scoreContributionAllowed: false unless a protected-domain task grants a named scoring path
rightToDisplay: explicit named-audience posture, not inferred
```

Missing capability metadata, missing source-confidence metadata, unknown
freshness, degraded source state, missing authority review, or missing
right-to-display review must produce a blocked, limited, unavailable, or
observation-only projection.

## Prerequisites Before Scoring Or Ranking Use

No scoring, ranking, sorting, selection, threshold, gate, recommendation, or
decision-grade workflow may consume this metadata until all prerequisites are
met:

1. A protected-domain task explicitly scopes the target scoring/ranking path.
2. The implementation defines exact input DTOs, output fields, versioning, and
   compatibility expectations.
3. Tests prove degraded data cannot claim fresh/live status, source authority,
   score contribution, or decision-grade readiness.
4. Tests prove missing or ambiguous metadata fails closed.
5. Tests prove existing ranking/order/threshold behavior is unchanged unless
   the task explicitly authorizes and documents a semantic change.
6. Owner review confirms source authority and right-to-display are separate.
7. API and stored-contract changes, if any, are explicitly scoped and
   backward-compatible or intentionally versioned.
8. Provider runtime, MarketCache, and fallback semantics are confirmed
   unchanged unless explicitly scoped.

Without these prerequisites, source-confidence metadata may be diagnostic or
observation-only only.

## Prerequisites Before UI Or Badge Use

No consumer-facing badge, chip, disclosure, tooltip, trust label, provider
label, confidence label, or source label may use this metadata until all
prerequisites are met:

1. A UI task explicitly scopes the target route, audience, copy, and field
   mapping.
2. The mapping translates raw metadata into the consumer-safe vocabulary in
   `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`.
3. Provider names, source types, trust tiers, reason codes, entitlement details,
   and raw diagnostics stay out of consumer-default UI.
4. Right-to-display is explicitly established for the audience and surface.
5. The UI makes degraded data honest without implying provider superiority,
   official status, investment advice, or decision-grade certainty.
6. Visual, accessibility, and responsive validation are run for the target
   route when implementation occurs.

Admin UI may show more metadata only when it is gated, sanitized, and clearly
diagnostic.

## Protected-Domain Escalation Rules

Stop and escalate to a separately scoped protected-domain task before changing
any of these domains:

- provider global order;
- provider live-call paths;
- fallback behavior, fallback depth, first-good-wins semantics, or deadline
  behavior;
- MarketCache TTL, SWR, cold-start, background refresh, cache key, or payload
  meaning;
- fallback/mock/synthetic live-labeling;
- scanner scoring, ranking, sorting, selection, thresholds, or score caps;
- rotation/liquidity/options/backtest/portfolio calculations, gates, ranking,
  or recommendation semantics;
- AI prompts, model routing, decision thresholds, or final advice logic;
- auth/RBAC/security behavior;
- notification routing;
- API response shapes or stored contract versions;
- provider credentials, entitlement checks, license classification, or
  right-to-display grants;
- frontend badges, trust labels, provider labels, or consumer disclosure
  surfaces.

Escalation must include the exact semantic delta, owner review path, focused
tests, rollback path, and whether full backend/frontend gates are required.

## Non-Goals

This contract does not authorize:

- source code changes;
- tests or schema changes;
- provider additions;
- provider order, runtime routing, live calls, fallback, deadline, or cache
  changes;
- MarketCache TTL/SWR/cold-start or payload-meaning changes;
- API fields, stored contracts, or client DTO changes;
- frontend UI, badges, chips, trust labels, or disclosures;
- scoring, ranking, sorting, thresholds, gates, score caps, recommendation, or
  decision-grade behavior;
- authority inference from provider/source metadata;
- legal, licensing, or redistribution conclusions;
- raw provider, raw prompt, raw LLM, credential, or secret exposure.

## Acceptance Checklist

Before future work claims compliance with this contract, verify:

- provider capability, source confidence, freshness, degraded state, authority,
  and right-to-display are modeled separately;
- no positive authority is inferred from provider/source/freshness labels;
- fallback, stale, partial, synthetic, unavailable, and unknown fail closed;
- consumer-safe output excludes raw provider diagnostics and raw authority
  fields;
- admin-only output is gated and sanitized;
- scoring/ranking/UI use has its own explicitly scoped task and validation;
- protected-domain changes stop for escalation instead of being folded into a
  metadata task.
