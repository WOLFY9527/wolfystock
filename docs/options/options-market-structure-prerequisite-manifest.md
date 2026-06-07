# Options Market-Structure Prerequisite Manifest

Status: prerequisite and boundary manifest only. No runtime implementation is approved.

Task anchor: T-1097 turns the existing observation contract into a future-safe
checklist for any later GEX, gamma regime, gamma flip, call wall, or put wall
task.

This document does not approve provider selection, DTO shape, API exposure,
cache semantics, frontend rendering, scoring effects, optimizer effects,
recommendation use, or decision-grade adoption.

## Manifest Purpose

Any future implementation task must treat this manifest as a gate checklist,
not as implementation approval.

Required standing boundary:

- `observationOnly=true`
- `decisionGrade=false`
- no effect on payoff, scoring, strategy ranking, optimizer, scanner, backtest,
  portfolio, broker/order, alert, notification, or recommendation semantics
- no provider self-claim may stand in for entitlement, redistribution, or
  decision-use authority
- no runtime/API/frontend write may start until all required checklist sections
  below are explicitly approved

## Future Test Categories Required Before Implementation

The first implementation-class task must arrive with focused tests or test plans
for each category below. Missing categories are blockers.

| Category | What must be proved before implementation | Still forbidden at this stage |
| --- | --- | --- |
| Static boundary tests | Observation contract remains additive only; no runtime import coupling; no hidden promotion into source, cache, API, or frontend surfaces. | Any product/runtime implementation. |
| Vocabulary and copy tests | User-facing and admin-facing labels stay observation-only and no-advice safe; forbidden words such as order/advice language are rejected. | Trade/action wording or support/resistance claims. |
| Methodology contract tests | Formula IDs, unit conventions, sign assumptions, bucketing, coverage thresholds, stale-data handling, and blocked reason codes are explicit and versioned. | Silent default formulas or implicit assumptions. |
| Provider authority proof tests | Evidence shows entitlement class, redistribution rights, decision-use rights, production/sandbox state, and source authority are present and reviewable. | Trusting vendor marketing or undocumented plan claims. |
| Coverage and freshness tests | Missing OI, Greeks, IV, multiplier, deliverable handling, stale quotes, delayed chains, or incomplete expirations fail closed with explicit reason codes. | Partial evidence being upgraded to usable-by-default. |
| DTO/API compatibility tests | Any future payload stays additive, versioned, compatibility-reviewed, and blocked by default when required fields are unknown. | Breaking existing response contracts or adding public fields without review. |
| Provider/runtime gate tests | Provider, cache, invalidation, and fail-closed behavior preserve existing options safety seams and do not bypass authority/freshness gates. | Cache/runtime coupling hidden inside docs-only or frontend tasks. |
| Frontend disclosure tests | Default view shows only safe summaries; detail disclosure is explicit; admin-only internals remain hidden from normal users. | Raw provider/debug/schema leakage or decision-grade implication. |
| Decision-grade blocker tests | Every blocked condition below keeps outputs non-actionable and cannot be overridden by copy alone. | Recommendation, tradeability, or optimizer adoption. |

## Provider Rights And Provenance Proof Required

No provider may be treated as market-structure authority until a future task
attaches reviewable proof for all items below.

Required proof bundle:

- provider identity, environment, and plan tier: production vs sandbox, delayed
  vs live, observation-only vs eligible-for-review
- entitlement proof: explicit evidence that the account/plan is allowed to
  access the required fields for chain, open interest, IV, Greeks, multiplier,
  deliverable handling, and freshness metadata
- redistribution proof: whether derived observations may be shown to end users,
  operators, or stored for later display
- decision-use proof: whether the provider terms allow stronger-than-observation
  use; absence of proof means blocked
- provenance proof: source authority chain, as-of timestamps, field lineage, and
  any transformation between vendor payload and normalized contract fields
- freshness proof: quote age, chain age, session rules, delay policy, stale
  downgrade policy, and missing-field downgrade policy
- coverage proof: expiration coverage, OI coverage, IV/Greeks coverage, missing
  contracts/exclusions, and corporate-action/deliverable handling notes
- manual verification record: reviewer, review date, evidence location, and
  expiry/renewal trigger for the proof set

Disallowed substitutes:

- vendor pricing pages
- undocumented sales or chat claims
- provider naming alone
- fixture, dry-run, stub, fallback, or synthetic outputs

## Methodology Approval Checklist

Methodology remains unapproved until every item below is reviewed together.

1. Define the observation family: GEX, gamma regime, gamma flip, call wall,
   put wall, and any concentration notes.
2. Freeze a `methodologyId` and `methodologyVersion` before any DTO or UI task.
3. State formula summaries and unit conventions for each metric.
4. State sign convention and positioning assumption, including whether sign is
   provider-supplied or model-derived.
5. Define spot reference source and as-of rules.
6. Define expiration aggregation window and strike bucket sizing.
7. Define multiplier, deliverable, split, and corporate-action handling.
8. Define stale-data, missing-OI, missing-IV, missing-Greeks, and partial-chain
   handling.
9. Define confidence caps, coverage thresholds, tie-breakers, and blocked reason
   codes.
10. Define permitted consumer-safe labels and forbidden interpretations.
11. Define review owner and re-approval trigger when methodology changes.

Methodology approval must fail if any formula, unit, sign assumption, or blocked
reason code is implicit.

## Review Gates By Layer

No future task may skip layers. Each gate requires explicit sign-off.

### DTO gate

- confirm the observation object is additive and versioned
- confirm unknown or rights-unverified fields remain blocked, not nullable by
  convenience
- confirm no stored contract version or existing response shape is broken

### API gate

- confirm exposure is opt-in and additive
- confirm no endpoint implies recommendation, tradeability, or support/resistance
- confirm blocked reasons, freshness state, and coverage state survive transport

### Provider gate

- confirm normalized inputs exist for required fields without fabrication
- confirm entitlement, redistribution, and decision-use proof bundle is attached
- confirm provider authority is reviewed separately from methodology correctness

### Cache/runtime gate

- confirm TTL, SWR, invalidation, fallback, and stale downgrade rules are
  explicit
- confirm fail-closed behavior on missing freshness, missing coverage, or rights
  expiry
- confirm no hidden coupling to MarketCache or provider-order semantics without a
  protected-domain task

### Frontend gate

- confirm placement remains inside Options Lab unless a later IA task says
  otherwise
- confirm default summary vs detail disclosure vs admin-only internals follow the
  observation contract
- confirm copy keeps no-advice framing and hides raw provider/debug/schema data

## Explicit Blockers For Decision-Grade Or Recommendation Use

Any one blocker below is sufficient to keep all market-structure outputs
observation-only and non-actionable.

- methodology is missing, incomplete, stale, or unapproved
- sign convention or positioning assumption is missing or ambiguous
- provider entitlement, redistribution, decision-use rights, or source
  authority is missing, expired, or unverified
- chain freshness, quote freshness, coverage thresholds, or delayed/stale policy
  is missing
- OI, IV, Greeks, multiplier, deliverable, expiration coverage, or spot
  reference evidence is incomplete
- outputs come from fixture, synthetic, stub, fallback, dry-run, or partial
  evidence
- blocked reason codes, confidence caps, or tie-breakers are undefined
- DTO/API/provider/cache/frontend gates are not all approved in separate scoped
  tasks
- copy or UI implies advice, orderability, support/resistance certainty, or best
  contract semantics
- any attempt is made to feed the observation into scoring, payoff math,
  strategy ranking, optimizer, scanner, backtest, portfolio, broker/order,
  notification, or recommendation paths

## Deferred Implementation Items

The following remain explicitly deferred after T-1097:

- GEX, gamma regime, gamma flip, call wall, and put wall computation
- provider selection or enablement
- DTO or API schema changes
- cache/runtime/fallback/invalidation design
- frontend rendering, copy wiring, or admin exposure
- no-advice policy expansion beyond current observation-only boundary
- any decision-grade, recommendation-grade, or tradeability-grade adoption

## Future Task Entry Criteria

A future implementation-class task may start only when:

1. it names this manifest and the observation contract as required inputs
2. it scopes exactly which layer is being approved or implemented
3. it includes the relevant test categories from this manifest
4. it leaves all unapproved layers deferred
5. it preserves `observationOnly=true` and `decisionGrade=false` unless a later
   protected-domain task explicitly lifts that boundary

Until then, this manifest and the observation contract together are the stop
sign for implementation.
