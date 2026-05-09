# Provider Capability Metadata

Phase 1 adds an inert provider capability matrix at
`src/services/provider_capability_matrix.py`.

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
