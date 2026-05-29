# Provider Capability Metadata

Phase 1 adds an inert provider capability matrix at
`src/services/provider_capability_matrix.py`.

Phase 2 starts cache-first advisory planning in
`src/services/provider_plan_advisor.py`. The advisor exposes deterministic
helper functions for reviewing cache/local-first candidate order by domain,
market, and mode. It is not wired into runtime provider execution.

Phase 3 adds an inert source-confidence contract at
`src/contracts/source_confidence.py`, backed by
`src/services/source_confidence_contract.py`. The contract provides
serializable source-confidence and provider-capability DTOs with the fields
`source`, `sourceLabel`, `asOf`, `freshness`, `isFallback`, `isStale`,
`isPartial`, `isSynthetic`, `isUnavailable`, `confidenceWeight`, `coverage`,
`degradationReason`, and `capReason`. Its pure normalization and validation
helpers cap fallback, stale, partial, synthetic, or unavailable sources so they
cannot be represented as live/fresh confidence evidence.

The market data source registry may also carry narrow candidate-source
metadata for future evidence families. The expiration-calendar candidate source
entry is `options_lab.expiration_calendar_candidate_evidence`; it projects as
`sourceType=missing` and describes only provenance, entitlement,
SLA/freshness, expiration taxonomy, and adjusted-deliverable/corporate-action
evidence families plus forbidden authority inputs. The event-calendar
candidate source entry is `options_lab.event_calendar_candidate_evidence`; it
also projects as `sourceType=missing` and describes only candidate-source
families such as provenance, entitlement, SLA/freshness, event taxonomy,
confirmation/event identity, timezone/session, coverage scope, and forbidden
authority inputs. The IV-rank candidate source entry is
`options_lab.iv_rank_candidate_evidence`; it also projects as
`sourceType=missing` and describes only candidate-source classes
(`provider_reported_iv_rank`, `approved_historical_option_iv_series`),
provenance, entitlement, SLA/freshness, methodology, lookback/date-range,
option-IV evidence, contract-universe/moneyness/expiry/missing-data coverage
families, and forbidden authority inputs.

This is source metadata only. It is not provider capability authority, not
data-access proof, not decision-use approval, not IV-rank authority, not
event-calendar authority, not an Options Lab authority grant, and not approval
for gates,
recommendations, `decisionGrade`, provider routing, or live calls.

The matrix documents provider domains, market coverage, quota class, freshness
class, recommended TTL hints, scanner/backtest eligibility, analysis-route
eligibility, and domain priority hints. It is intended for reviews, tests, and
future planner design only.

## Canonical onboarding fields

Use the existing inert metadata DTOs as the canonical onboarding surface for
docs/tests/diagnostics work. A normalized onboarding row should describe:

- provider identity: `providerId`, `providerName`
- supported surfaces: `capability` for capability-support rows, plus
  `domains`/`markets` for matrix capability rows and the first
  `bestUseCases` surface token for fit-metadata rows
- source classification: `sourceType`, `sourceTier`, `trustLevel`
- freshness expectation: `freshnessExpectation` for onboarding metadata, and
  `freshness` / `freshnessCap` when projecting shared source-confidence fields
- cap posture: `capReason`, `confidenceWeightCap`, `coverage`,
  `fallbackEligible`, `syntheticEligible`
- diagnostic posture: `observationOnly=true`,
  `scoreContributionAllowed=false`
- credential and permission status: `paidDataLikelyRequired`, `keyRequired`,
  `cacheRequired`, `backgroundRefreshRecommended`
- runtime readiness: `enabledByDefault=false`, optional
  `missingProviderReason`, optional `planDependent`
- dry-run status: `networkCallExecuted=false`, `noDefaultLiveHttpCalls=true`,
  `liveTestsAvoided=true`, plus bounded credential-count fields instead of raw
  secret values

This onboarding surface is metadata only. It does not grant provider runtime
enablement, provider ordering, budget eligibility, API exposure, authority, or
`decisionGrade` use.

## Canonical vocabulary

Shared onboarding metadata currently uses the following bounded vocabularies:

- provider support `sourceType`: `missing`, `official_public`,
  `public_proxy`
- source-confidence `freshness`: `fresh`, `live`, `delayed`, `cached`,
  `stale`, `partial`, `fallback`, `synthetic`, `unavailable`, `unknown`
- degraded source-confidence `capReason`: `fallback_source`,
  `stale_source`, `partial_coverage`, `synthetic_source`,
  `unavailable_source`

`freshnessExpectation` stays descriptive and row-specific, but diagnostic rows
must remain inside the audited expectation families already represented in the
matrix, such as persisted watchlist freshness audits, stored portfolio
lineage/snapshot evidence, synthetic fixture chains, disabled live stubs, and
authorized-or-cached options gap chains.

## Source-confidence cap behavior

The shared source-confidence contract is fail-closed for degraded evidence:

- fallback sources normalize to `freshness=fallback` and cap at `0.4`
- stale sources normalize to `freshness=stale` and cap at `0.6`
- partial sources normalize to `freshness=partial` and cap at `0.7`
- synthetic sources normalize to `freshness=synthetic` and cap at `0.2`
- unavailable sources normalize to `freshness=unavailable` and cap at `0.0`

These degraded states cannot be represented as `live` or `fresh` confidence
evidence, and the same reason codes are used by the score-grade authority gate
to block false promotion.

## Diagnostic-only posture

Provider onboarding rows in this phase remain read-only diagnostics:

- fit/support/probe metadata stays `observationOnly=true`
- fit/support/probe metadata stays `scoreContributionAllowed=false`
- diagnostic rows do not imply score-grade authority, runtime authority, or
  `decisionGrade` approval
- `missingProviderReason` explains deferred wiring status, not a temporary
  runtime override

## Deferred runtime onboarding requirements

Runtime onboarding remains deferred until a separately authorized task adds:

- provider implementation and configuration wiring
- credential handling and operator documentation
- explicit runtime routing/budget review
- focused offline and runtime-safe validation for the new provider path
- any API/schema/client changes under their own scoped review

This phase does not change:

- runtime provider routing or provider ordering;
- scanner scoring, selection, thresholds, or provider calls;
- backtest calculations or live-data behavior;
- MarketCache TTL, SWR, cold-start, stale, or fallback behavior;
- AI prompts, decision logic, notifications, auth, RBAC, or frontend UI.

Backtest metadata allows only local/cache/local-inference sources. External
providers remain marked as `never` for backtest usage because backtest runs must
make zero live provider calls.

Scanner metadata remains local/cache-first. Scarce or research-oriented sources
such as FMP, Alpha Vantage, GNews, Tavily, and Social Sentiment are not
scanner-wide providers; future use must stay behind deterministic top-N
preselection or explicit research actions.

Technical indicators should be computed locally from available OHLCV whenever
possible. FMP is documented as fundamentals/statements-first. Alpha Vantage is
documented as manual/deep last resort only.

Advisory cache-first plans may include local pseudo-providers such as
`local_cache`, `local_ohlcv`, `local_news_cache`, and `local_inference`. These
labels are planning metadata only and must not upgrade stale, cached, fallback,
mock, synthetic, or inferred data to live provider status.
