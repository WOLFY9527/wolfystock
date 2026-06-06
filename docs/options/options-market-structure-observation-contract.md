# Options Market-Structure Observation Contract

Status: prerequisite contract only. No runtime implementation is approved.

This document defines the future observation-only contract for Options Lab
market-structure evidence such as GEX, gamma regime, gamma flip, call wall, and
put wall. It is not a provider selection, API schema, DTO, cache plan, frontend
rendering spec, or decision-grade approval.

## Operating Boundary

Future market-structure evidence must first live in Options Lab as additive
derived evidence named `optionsMarketStructureObservation`.

Required invariants:

- `observationOnly=true`
- `decisionGrade=false`
- no broker, order, portfolio, backtest, scanner, alert, notification, optimizer,
  payoff, strategy-ranking, trade-quality score, or recommendation effect
- no consumer-facing implementation until this contract, focused contract tests,
  provider rights proof, and methodology approval exist
- no stronger-than-observation use until a separate protected-domain task reviews
  DTO/API exposure, provider authority, cache/runtime semantics, frontend copy,
  and no-advice policy

Consumer copy must frame these values as research context only. Do not use
execution or advice labels such as `buy`, `sell`, `order`, `best contract`,
`guaranteed`, `confirmed support`, or `confirmed resistance`.

## Indicator Vocabulary

Use these terms only with explicit methodology, coverage, freshness, and rights
metadata.

| Term | Observation meaning | Required caveat |
| --- | --- | --- |
| GEX | Gamma exposure estimate derived from option gamma, open interest, multiplier, spot reference, side, and a documented unit convention. | Formula and units must be explicit; current repository fields alone do not create signed exposure authority. |
| Gamma regime | Summary label for positive, negative, neutral, mixed, unknown, or blocked gamma state. | Must be derived from approved GEX/sign methodology and display the blocked or unknown state when evidence is incomplete. |
| Positive gamma | Net gamma regime label under an approved sign convention and positioning assumption. | Must say whether sign is provider-supplied or model-derived; otherwise label as assumption-only. |
| Negative gamma | Net gamma regime label under the same approved sign convention and positioning assumption. | Must not imply volatility forecast or trading action. |
| Gamma flip | Estimated level or interval where the net gamma regime changes sign. | Must include spot reference, interpolation/bucketing method, and confidence/coverage limits. |
| Call wall | Call-side strike concentration by OI, GEX, or another approved concentration rule. | Must avoid support/resistance claims; label as concentration only. |
| Put wall | Put-side strike concentration by OI, GEX, or another approved concentration rule. | Must avoid support/resistance claims; label as concentration only. |

## Required Input Classes

The contract is vendor-neutral. It does not endorse a paid provider or authorize
network calls, credentials, or provider enablement.

Minimum input classes:

- Chain identity: underlying symbol, market, currency, expiration, strike, side,
  contract symbol, multiplier, deliverable/corporate-action handling, and
  symbology normalization.
- Spot reference: source, timestamp, freshness class, market session, and the
  value used by the methodology.
- Market fields: bid, ask, mid, last, spread, volume, open interest, implied
  volatility, and full Greeks including gamma.
- Coverage: expiration coverage, bid/ask coverage, OI coverage, volume coverage,
  IV coverage, Greeks coverage, missing contracts, and excluded expirations.
- Freshness: per-field as-of timestamps where available, chain as-of, quote
  as-of, maximum accepted age, delayed/stale/synthetic flags, and market-session
  rules.
- Authority and rights: entitlement status, redistribution rights, decision-use
  rights, sandbox/production state, source authority, and provider capability
  proof.
- Methodology inputs: formula, units, sign convention, positioning assumption,
  aggregation window, strike bucket size, stale/OI handling, missing-Greeks
  handling, multiplier/deliverable handling, tie-breakers, and confidence caps.

## Minimum Contract Fields

Future payloads or fixtures may only be designed after a separate DTO/API task.
When that happens, the contract must carry at least these field groups:

- Contract identity: `contractName`, `contractVersion`, `observationOnly`,
  `decisionGrade`, `generatedAt`.
- Scope: `underlying`, `market`, `currency`, `spotReference`, `expirationRange`,
  `aggregationWindow`, `strikeBucket`.
- Methodology: `methodologyId`, `methodologyVersion`, `formulaSummary`,
  `unitConvention`, `signConvention`, `positioningAssumption`,
  `confidencePolicy`.
- Inputs and coverage: `inputClasses`, `coverage`, `missingEvidence`,
  `excludedInputs`, `inputSnapshotHash`.
- Freshness: `sourceAsOf`, `chainAsOf`, `spotAsOf`, `freshnessClass`,
  `maxAgePolicy`, `delayedOrStaleReason`.
- Rights and authority: `providerClass`, `entitlementStatus`,
  `redistributionRights`, `decisionUseRights`, `sourceAuthority`,
  `manualVerification`.
- Observations: `gexSummary`, `gammaRegime`, `gammaFlip`, `callWall`, `putWall`,
  `concentrationNotes`, `blockedReasonCodes`.
- Safety: `noAdviceDisclosure`, `consumerSafeLabels`, `forbiddenUses`,
  `adminOnlyFields`.

If any required field is unknown, stale, synthetic, fallback-derived, fixture-only,
or rights-unverified, the observation must remain blocked or degraded and must not
be promoted by UI copy.

## Display Tiers

Display is a future frontend task. The tier contract is defined now so future
prompts do not expose raw internals by default.

| Tier | Audience | Allowed content | Forbidden content |
| --- | --- | --- | --- |
| Default summary | Options Lab user | Observation-only label, high-level gamma regime if supported, wall/concentration labels, freshness class, coverage state, and missing-evidence count. | Raw provider payloads, credentials, debug traces, methodology internals, support/resistance claims, trade or order language. |
| Detail disclosure | Options Lab user after explicit expansion | Formula summary, units, sign convention, aggregation window, input coverage, as-of timestamps, missing evidence, and no-advice boundary. | Provider secrets, raw transport diagnostics, paid entitlement details, internal scoring hooks, cache/runtime internals. |
| Admin-only internals | Operators and reviewers | Provider proof, entitlement evidence, redistribution notes, input hashes, dry-run evidence, raw diagnostics summaries, methodology audit notes. | Any consumer-facing advice, order enablement, or hidden decision-grade override. |

## Decision-Grade Blockers

Market-structure observations are decision-grade blocked while any of these is
true:

- methodology, formula, unit convention, sign convention, or positioning
  assumption is missing or unapproved;
- provider entitlement, redistribution rights, decision-use rights, or source
  authority is missing, expired, or manually unverified;
- data is fixture, synthetic, stub, dry-run, fallback, delayed beyond policy,
  stale, partial, or missing freshness proof;
- OI, IV, gamma, multiplier, deliverable/corporate-action handling, spot
  reference, or expiration coverage is incomplete;
- coverage thresholds, confidence caps, tie-breakers, or missing-evidence reason
  codes are not defined;
- copy and tests do not prove observation-only and no-advice behavior;
- DTO/API, provider, cache/runtime, or frontend contracts have not been approved
  in separate protected-domain tasks.

For T-1090 and its immediate descendants, the safe default is that all GEX,
positive/negative gamma, gamma flip, call wall, and put wall outputs are
observation-only and decision-grade blocked.

## Prerequisites Before Implementation

Do not start consumer-facing implementation until all of the following are true:

1. This contract has focused static or contract tests that block runtime imports,
   public API exposure, provider/cache/runtime coupling, and advice/order wording.
2. A provider-neutral methodology spec defines formulas, units, sign assumptions,
   bucketing, coverage thresholds, confidence caps, and missing-evidence codes.
3. Provider rights and authority are verified without vendor self-claims standing
   in for entitlement, redistribution, or decision-use rights.
4. A DTO/API task approves additive response shape and compatibility boundaries.
5. A provider/cache/runtime task approves source authority, live-evidence
   propagation, TTL/SWR/invalidation semantics, and fail-closed behavior.
6. A frontend task approves Options Lab placement, display tiers, copy tests, and
   hidden-by-default internals.
7. A no-advice review confirms the observations cannot affect scoring, optimizer,
   payoff, strategy ranking, scanner, backtest, portfolio, broker/order,
   notification, or recommendation semantics.

Until then, future Codex prompts should treat this document as a stop sign for
implementation and as the minimum checklist for a later docs/test prerequisite.
