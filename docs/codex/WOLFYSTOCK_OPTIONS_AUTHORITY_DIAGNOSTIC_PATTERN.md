# WolfyStock Options Authority Diagnostic Pattern

Purpose: reusable guardrail for Options authority diagnostic tasks such as IV-rank, event-calendar, and expiration-calendar diagnostics.

Use this doc in future prompts instead of repeating the same safety rules.

## When to use this doc

Use this doc when the task is adding, reviewing, or documenting a diagnostic-only authority check for an Options evidence surface.

Typical cases:

- IV-rank authority diagnostic
- event-calendar authority diagnostic
- expiration-calendar authority diagnostic

## Do not use this doc for

Do not use this doc for:

- gates, recommendations, `decisionGrade`, or ranking policy
- live provider routing, fallback order, or runtime behavior
- broker, order, trading, or portfolio mutation flows
- source-of-truth policy changes
- data-quality policy changes outside diagnostic-only authority labeling

## Required pattern

These diagnostics are:

- inert
- offline by default
- sanitized
- diagnostic-only

They exist to explain whether current evidence is authoritative enough for future policy use. They do not create or change policy.

## Locked invariants

- Diagnostic output must never feed gates, recommendations, or `decisionGrade`.
- Coverage does not equal authority.
- Provider self-claims are ignored.
- Fixture, synthetic, fallback, dry-run, stub, adapter-contract, and request-shaped evidence is non-authoritative.
- Authority requires an internal WolfyStock policy source.
- No live calls by default.
- No broker, order, trading, or portfolio mutation.

## Authority decision rule

Treat a surface as authoritative only when both conditions are true:

1. Evidence is present in a sanitized diagnostic payload.
2. An internal WolfyStock authority policy source explicitly marks that evidence path as authoritative.

If coverage exists without internal policy authority, return a non-authoritative diagnostic state. Do not upgrade authority because a provider reports broad coverage, completeness, or authorization.

## Recommended helper shape

Use a compact additive helper/result shape like:

```json
{
  "diagnosticOnly": true,
  "authorityState": "authoritative | non_authoritative | missing",
  "authoritative": false,
  "providerId": "sanitized-provider-id",
  "sourceType": "sanitized-source-type",
  "sourceAuthority": "sanitized-source-authority-claim",
  "authorityPolicySource": "wolfystock_internal_policy",
  "reasonCodes": [
    "coverage_without_internal_authority",
    "provider_self_claim_ignored",
    "fixture_not_authoritative"
  ],
  "requiredFutureAuthorityEvidence": [
    "internal_policy_source",
    "approved_authority_mapping"
  ]
}
```

Notes:

- `diagnosticOnly` must stay `true`.
- `authorityState` is the user-safe summary; `authoritative` is the boolean decision.
- `providerId`, `sourceType`, and `sourceAuthority` must remain sanitized labels, not raw payloads.
- `authorityPolicySource` must point to an internal WolfyStock policy source, not a provider claim.
- `reasonCodes` should explain why evidence is non-authoritative without leaking runtime internals.
- `requiredFutureAuthorityEvidence` should list what internal evidence would be needed before authority can be granted.

## Reusable examples

- Enough rows/events/expirations are present, but no internal authority policy source exists:
  return `non_authoritative`.
- Provider payload says `authorized` or equivalent:
  ignore the self-claim unless an internal WolfyStock policy source independently authorizes it.
- Fixture, fallback, dry-run, stub, adapter-contract, or request-shaped data is present:
  treat it as diagnostic evidence only, never authoritative evidence.

## Explicit non-goals

This pattern must not:

- change runtime provider behavior
- trigger live evidence collection by default
- alter gates, recommendations, or decision semantics
- mutate broker, order, trading, or portfolio state
- redefine authority policy beyond requiring internal WolfyStock policy evidence
