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
- observation-only

They exist to explain whether current evidence is authoritative enough for future policy use. They do not create or change policy.
Current repo-local evidence is not sufficient to treat any Options surface as authoritative. Any future authority requires manual external verification first and then a separate dedicated policy task.

## Locked invariants

- Diagnostic output must never feed gates, recommendations, or `decisionGrade`.
- Checklist completeness is diagnostic readiness only, not authority, not decision readiness, and not `decisionGrade`.
- Runtime/helper/operator-summary completeness is diagnostic readiness only, not authority, not decision readiness, and not `decisionGrade`.
- Coverage does not equal authority.
- Provider self-claims are ignored.
- Fixture, synthetic, fallback, dry-run, stub, adapter-contract, and request-shaped evidence is non-authoritative.
- Authority requires an internal WolfyStock policy source.
- No live calls by default.
- No provider routing, budget, or live-call enablement.
- No broker, order, trading, or portfolio mutation.

## Authority decision rule

Treat a surface as authoritative only when all conditions below are true:

1. Sanitized evidence exists in the diagnostic payload.
2. No blocked source class is present.
3. An internal WolfyStock authority policy source explicitly grants that evidence path.
4. Required checklist and evidence families are complete where policy requires them.

If coverage or checklist completeness exists without all four conditions, return a non-authoritative diagnostic state. Do not upgrade authority because a provider reports broad coverage, completeness, or authorization.
If runtime/helper/operator-summary output exists without all four conditions, return a non-authoritative diagnostic state. Do not upgrade authority because a helper, projection, or operator summary exists.

## Checklist evidence families

Use checklist families as diagnostic structure only. They help explain readiness gaps but do not grant authority by themselves.

- Common families: provenance, entitlement, SLA/freshness
- IV-rank families: methodology, lookback, IV evidence
- event-calendar families: event taxonomy, confirmation, timezone/session, coverage scope
- expiration-calendar families: expiration taxonomy, adjusted deliverable, corporate-action evidence

## Current trilogy behavior

Current diagnostic behavior is input-dependent but diagnostic-only:

- `iv-rank`, `event-calendar`, and `expiration-calendar` may emit `authorityEvidenceChecklist` or equivalent checklist/gap output when checklist evidence or policy context is supplied.
- When that context is absent, a surface may still fall back to reason codes or checklist-family gap summaries.
- Emitted checklist completeness remains diagnostic readiness only, not authority, not decision readiness, and not `decisionGrade`.
- Event helper output, runtime projections, and compact operator summaries remain observation-only unless separate authority policy conditions are met later.

## Interpretation warning

Do not interpret any of the following as decision readiness:

- `authoritative`
- `authorityEvidenceChecklist.present`
- `authorizedSourceMetadata`
- `expirationCoverage`
- event count or event type
- current IV
- provider capability metadata
- helper/runtime projection presence
- operator-summary completeness

Those fields may describe diagnostic availability, sanitized evidence shape, or policy context. They must not be used as a proxy for gate readiness, recommendation readiness, or `decisionGrade`.

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
- `authorityEvidenceChecklist.present` indicates diagnostic checklist emission only, not authority or decision readiness.
- `reasonCodes` should explain why evidence is non-authoritative without leaking runtime internals.
- `requiredFutureAuthorityEvidence` should list what internal evidence would be needed before authority can be granted.
- The field must not imply that current repo-local evidence is already feasible as authority.

## Reusable examples

- Enough rows/events/expirations are present, but no internal authority policy source exists:
  return `non_authoritative`.
- A checklist is complete but a blocked source class is present, or policy does not grant the path:
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
