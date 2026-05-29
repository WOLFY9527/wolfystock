# Event Calendar Source Candidate Evidence

Status: Observation-only worksheet; no repo-local authority path currently feasible
Scope: docs-only worksheet for future `EventCalendarSourceCandidateEvidence`
Non-goal: no authority grant, no runtime wiring, no registry/provider/gate/API change

## Purpose

Use this worksheet to collect observation-only evidence before any future event-calendar source onboarding work.

This worksheet is:

- evidence collection only
- diagnostic-only
- candidate-only
- not an authority grant
- not decision readiness
- not gate or recommendation readiness
- not repo-local proof of feasible Options authority

This worksheet must not be used as proof that any current repo-local provider, event feed, runtime projection, or timeline surface is authoritative.

## Current Repo Status

Current repository state remains observation-only and non-authoritative:

- an event source-candidate gap contract exists
- event source registry candidate metadata exists
- an inert runtime-safe `EventCalendarSourceCandidateEvidence` contract exists
- candidate-evidence runtime projection exists and remains observation-only
- event helper/registry/runtime projection status is still diagnostic-only and non-authoritative
- existing event intelligence DTO, timeline, and provider protocol code is observation scaffolding only
- no current repo-local path proves licensed provider, exchange, issuer, or official-calendar authority
- no current repo-local provider or source is feasible as Options authority without manual external verification and a later dedicated policy task

Do not read current event presence, event counts, event types, timeline output, helper/runtime projection presence, provider IDs, or provider protocol coverage as proof of source authority.

## Required External Verification Groups

Every future worksheet packet should capture sanitized evidence for all groups below.

| Check | Required evidence | Status |
| --- | --- | --- |
| Source identity | Legal source name, distributor/provider name, product name, source class, sanitized contract/doc reference | `verified` / `partial` / `unverified` |
| Provenance chain | Upstream-to-downstream chain from original source to current distributor/provider, including sublicense hops | `verified` / `partial` / `unverified` |
| Licensed provider / exchange / issuer / official-calendar backing | Written proof of licensed provider, exchange, issuer, or official-calendar backing; otherwise mark explicitly unverified | `verified` / `partial` / `unverified` |
| Entitlement / license / use rights | Entitlement tier, license scope, account/org boundary, allowed internal use, restrictions | `verified` / `partial` / `unverified` |
| Redistribution and decision-use rights | Written proof for redistribution, storage, internal display, and decision-support use; note prohibitions explicitly | `verified` / `partial` / `unverified` |
| Live vs delayed status | Written live/delayed statement, delay window, label/disclaimer requirements | `verified` / `partial` / `unverified` |
| Production vs sandbox status | Proof whether evidence came from production, sandbox, mock, or contract-only materials | `verified` / `partial` / `unverified` |
| As-of / freshness / SLA / max-age policy | `asOf`, cadence, SLA, freshness language, max-age policy, stale-data handling terms | `verified` / `partial` / `unverified` |
| Event taxonomy | Written taxonomy proof for earnings, dividends, ex-dividend, splits, corporate actions, and any policy-scoped macro context | `verified` / `partial` / `unverified` |
| Confirmation status | Proof for confirmed vs estimated vs announced status semantics | `verified` / `partial` / `unverified` |
| Event date / time / session / timezone | Event date, event time, trading session, timezone, and timezone interpretation notes | `verified` / `partial` / `unverified` |
| Provider event ID / event identity | Provider event ID, event identity semantics, dedupe/uniqueness notes, mutation/correction behavior | `verified` / `partial` / `unverified` |
| Coverage scope | Symbol or underlying coverage, lookahead window/date range, coverage gaps, unsupported regions/classes | `verified` / `partial` / `unverified` |

Suggested capture notes:

- record the exact as-of date for every external document or contract reference
- mark missing proof as `unverified`, not inferred
- treat provider marketing copy, provider self-claims, and current runtime output as non-authoritative
- keep citations sanitized and prompt-friendly

## Event Types For Options Context

Track event evidence separately for:

- earnings
- dividends / ex-dividend
- splits / corporate actions
- FOMC / macro context only when explicitly policy-scoped

Do not collapse these into one generic “event coverage” claim. Partial proof for one event type does not verify the others.

## Forbidden Authority Outputs And Shortcuts

This worksheet must not emit, imply, or unlock any of the following:

- `authorityGrant`
- `providerDecisionAuthority`
- `recommendationAuthority`
- `decisionGrade`
- `gateDecision`
- `sourceAuthorityAllowed`
- provider routing
- live-call enablement
- event presence
- event count
- event type
- timeline evidence
- generic macro context
- source labels
- provider capabilities
- provider self-claims
- current provider IDs

These are forbidden shortcuts for authority:

- current event presence/count/type
- timeline evidence or timeline completeness
- generic macro context
- source labels or product naming
- provider capabilities or provider capability metadata
- provider self-claims or marketing language
- current provider IDs
- helper presence
- runtime projection presence
- operator summary completeness

Checklist completeness, observed coverage, or DTO/protocol shape must not be treated as authority.

## Must Not Proceed To Implementation Until Verified

- [ ] Source identity is verified with a sanitized source reference.
- [ ] Provenance chain is verified end to end.
- [ ] Licensed provider / exchange / issuer / official-calendar backing is verified, or the gap is still blocking.
- [ ] Entitlement / license / use rights are verified for intended internal use.
- [ ] Redistribution and decision-use rights are verified.
- [ ] Live vs delayed status is verified.
- [ ] Production vs sandbox status is verified.
- [ ] As-of / freshness / SLA / max-age policy is verified.
- [ ] Event taxonomy is verified for the specific Options event type in scope.
- [ ] Confirmation status semantics are verified.
- [ ] Event date / time / session / timezone semantics are verified.
- [ ] Provider event ID / event identity semantics are verified.
- [ ] Coverage scope is verified.

If any box remains unchecked, do not proceed to implementation.

## Safe Future Sequence

1. External source/license verification
   Verify source identity, provenance, rights, freshness, event taxonomy, confirmation, timezone/session, event identity, and coverage using external evidence.
2. Docs update with verified source facts
   Update this worksheet only after verified facts exist; do not backfill assumptions, current provider IDs, or provider self-claims.
3. Read-only implementation audit
   Inspect current adapter, diagnostic, API, runtime, and policy boundaries without editing runtime code.
4. Keep the inert source-candidate evidence contract observation-only
   The existing candidate-evidence contract and runtime projection must stay diagnostic-only, candidate-only, `authorityGrant=false`, and must not enable live calls or decision use.
5. Authority grant only in a separate future policy task
   Any authority decision requires a distinct policy task with explicit approval, completed manual external verification, verified facts, and separate validation.

## Locked Invariants

- no runtime behavior changes
- no source code changes
- no tests changed
- no provider/source authority upgrade
- no gate/recommendation/`decisionGrade`/API behavior changes
- no live calls
- no broker/order/trading/portfolio mutation
