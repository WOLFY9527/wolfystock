# IV-Rank Source Candidate Evidence

Status: Observation-only worksheet; no repo-local authority path currently feasible
Scope: docs-only worksheet for future `IvRankSourceCandidateEvidence`
Non-goal: no authority grant, no runtime wiring, no registry/provider/gate/API change

## Purpose

Use this worksheet to collect observation-only evidence before any future IV-rank source onboarding work.

This worksheet is:

- evidence collection only
- diagnostic-only
- candidate-only
- not an authority grant
- not decision readiness
- not gate or recommendation readiness
- not repo-local proof of feasible Options authority

This worksheet must not be used as proof that any current repo-local provider, source label, diagnostic, runtime summary, or local proxy is authoritative.

## Current Repo Status

Current repository state remains observation-only and non-authoritative:

- current IV, selected-contract IV, and Greeks are observation context only
- `historicalIvProxy` and underlying realized volatility are context/proxy only
- runtime diagnostics are local/offline scaffolding
- no current path proves provider-reported IV rank/percentile authority
- no current path proves approved historical option-IV series authority
- no current repo-local provider or source is feasible as Options authority without manual external verification and a later dedicated policy task

Do not read current IV context, selected-contract context, Greeks, local proxies, runtime diagnostic output, compact operator-summary coverage, provider IDs, provider capabilities, or docs as proof of source authority.

## Required External Verification Groups

Every future worksheet packet should capture sanitized evidence for all groups below.

| Check | Required evidence | Status |
| --- | --- | --- |
| Source identity | Legal source name, distributor/provider name, product name, source class, sanitized contract/doc reference | `verified` / `partial` / `unverified` |
| Provenance chain | Upstream-to-downstream chain from original IV source to current distributor/provider, including sublicense hops | `verified` / `partial` / `unverified` |
| Provider-reported IV rank/percentile or approved historical option-IV series | Written proof that the source provides provider-reported IV rank/percentile, or approved historical option-IV series suitable for deriving IV rank | `verified` / `partial` / `unverified` |
| Entitlement / license / use rights | Entitlement tier, license scope, account/org boundary, allowed internal use, restrictions | `verified` / `partial` / `unverified` |
| Redistribution and decision-use rights | Written proof for redistribution, storage, internal display, and decision-support use; note prohibitions explicitly | `verified` / `partial` / `unverified` |
| Live vs delayed status | Written live/delayed statement, delay window, label/disclaimer requirements | `verified` / `partial` / `unverified` |
| Production vs sandbox status | Proof whether evidence came from production, sandbox, mock, or contract-only materials | `verified` / `partial` / `unverified` |
| As-of / freshness / SLA / max-age policy | `asOf`, cadence, SLA, freshness language, max-age policy, stale-data handling terms | `verified` / `partial` / `unverified` |
| Methodology version | Versioned methodology or documented calculation method, including change/correction policy | `verified` / `partial` / `unverified` |
| Percentile/rank definition | Exact definition of IV rank vs IV percentile, denominator, inclusivity, and edge-case handling | `verified` / `partial` / `unverified` |
| Lookback window / date range | Lookback window, start/end dates, trading-day/calendar-day basis, and date-range limits | `verified` / `partial` / `unverified` |
| Calculation basis | Provider-reported field, approved derived series, interpolation rules, and whether values use option IV or underlying volatility | `verified` / `partial` / `unverified` |
| Contract universe | Included option contracts, exclusions, exchange/product coverage, and symbol/underlying coverage | `verified` / `partial` / `unverified` |
| Moneyness selection rules | ATM/OTM/ITM selection, delta bands, strike selection, and tie-breaking rules | `verified` / `partial` / `unverified` |
| Expiry selection rules | Expiration tenor, nearest/standard expiry selection, weekly/monthly handling, and roll rules | `verified` / `partial` / `unverified` |
| Missing-data policy | Sparse history handling, stale points, corporate-action adjustment, holiday/session gaps, and fallback prohibitions | `verified` / `partial` / `unverified` |
| Coverage scope | Covered markets, symbols/underlyings, option classes, date ranges, and unsupported gaps | `verified` / `partial` / `unverified` |

Suggested capture notes:

- record the exact as-of date for every external document or contract reference
- mark missing proof as `unverified`, not inferred
- treat provider marketing copy, provider self-claims, and current runtime output as non-authoritative
- keep citations sanitized and prompt-friendly

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

These are forbidden shortcuts for authority:

- current IV
- selected-contract IV
- Greeks
- `historicalIvProxy`
- underlying realized volatility
- source labels
- provider capabilities
- provider self-claims
- current provider IDs
- docs-only evidence
- coverage completeness
- runtime or operator-summary completeness
- dry-run, fixture, synthetic, fallback, adapter-contract, or request-shaped evidence

Checklist completeness, observed coverage, provider capability metadata, provider self-claims, or documentation presence must not be treated as authority.

## Must Not Proceed To Implementation Until Verified

- [ ] Source identity is verified with a sanitized source reference.
- [ ] Provenance chain is verified end to end.
- [ ] Provider-reported IV rank/percentile or approved historical option-IV series evidence is verified, or the gap is still blocking.
- [ ] Entitlement / license / use rights are verified for intended internal use.
- [ ] Redistribution and decision-use rights are verified.
- [ ] Live vs delayed status is verified.
- [ ] Production vs sandbox status is verified.
- [ ] As-of / freshness / SLA / max-age policy is verified.
- [ ] Methodology version is verified.
- [ ] Percentile/rank definition is verified.
- [ ] Lookback window / date range is verified.
- [ ] Calculation basis is verified.
- [ ] Contract universe is verified.
- [ ] Moneyness selection rules are verified.
- [ ] Expiry selection rules are verified.
- [ ] Missing-data policy is verified.
- [ ] Coverage scope is verified.

If any box remains unchecked, do not proceed to implementation, provider integration, runtime projection, source registry work, gate/recommendation work, or authority policy work.

## Safe Future Sequence

1. External source/license verification
   Verify source identity, provenance, IV-rank or historical option-IV evidence, rights, freshness, methodology, lookback, calculation basis, contract universe, selection rules, missing-data policy, and coverage scope using external evidence.
2. Docs update with verified source facts
   Update this worksheet only after verified facts exist; do not backfill assumptions, current provider IDs, current IV context, or provider self-claims.
3. Read-only implementation audit
   Inspect current adapter, diagnostic, API, runtime, policy, and registry boundaries without editing runtime code.
4. Inert source-candidate gap/packet task only if approved
   If separately approved, limit the first implementation to inert candidate gap/packet shaping with no live calls and no authority grant.
5. Runtime projection only after inert contract validation
   Any runtime-facing projection must wait until the inert contract is validated and still remains diagnostic-only.
6. Authority grant only in a separate future policy task
   Any authority decision requires a distinct policy task with explicit approval, completed manual external verification, verified facts, and separate validation.

## Locked Invariants

- no runtime behavior changes
- no source code changes
- no tests changed
- no provider/source authority upgrade
- no gate/recommendation/`decisionGrade`/API behavior changes
- no live calls
- no broker/order/trading/portfolio mutation
