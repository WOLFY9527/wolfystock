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
evidence families plus forbidden authority inputs. This is source metadata
only. It is not provider capability authority, not decision-use approval, not
an Options Lab authority grant, and not approval for gates, recommendations,
`decisionGrade`, provider routing, or live calls.

The matrix documents provider domains, market coverage, quota class, freshness
class, recommended TTL hints, scanner/backtest eligibility, analysis-route
eligibility, and domain priority hints. It is intended for reviews, tests, and
future planner design only.

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
