# Historical Market Data Foundation v1

WolfyStock historical market-data consumers should use the canonical foundation
contract instead of provider-shaped payloads. The boundary is:

```text
Raw provider observation
-> adapter/normalizer
-> CanonicalHistoricalBar
-> HistoricalBarQualityOutcome
-> HistoricalMarketDataRepository
-> HistoricalMarketDataFoundation read methods
-> product integration contract
```

## Canonical Bar

`src.services.historical_market_data_foundation.CanonicalHistoricalBar` is the
canonical internal bar model. It carries market and venue identity, canonical
symbol, provider symbol, interval, session date, optional timestamp, market
timezone, OHLCV values, adjustment metadata, currency, provider/source,
observation/as-of metadata, ingestion id, lineage id, normalization version,
and quality state.

Provider-specific field names such as `Adj Close`, `Date`, `开盘`, or `成交量`
must stay inside `normalize_provider_historical_bars`. Product read consumers
must not depend on those raw field names.

## Quality Outcomes

`HistoricalBarQualityOutcome` produces three product-facing states:

- `usable`: product-readable and no quality reason codes.
- `degraded`: product-readable with reason codes such as `missing_session_gap`
  or `source_metadata_gap`; no missing bars are fabricated.
- `rejected`: not product-readable for invalid identity, malformed timestamp,
  invalid OHLC, negative values, non-monotonic ordering, or conflicting
  duplicate bars.

Quality validation is deterministic and does not repair, interpolate, or
fabricate historical market data.

## Persistence

`src.repositories.historical_market_data_repo.HistoricalMarketDataRepository`
owns the idempotent persistence boundary for this foundation. Its natural key is:

```text
market + canonical_symbol + interval + session_date + provider + adjustment_status
```

Repeated ingestion of the same logical observation is counted as a duplicate.
Conflicting re-ingestion is rejected and preserves the existing canonical bar.
The repository creates narrowly scoped SQLite tables for isolated tests and
future migration wiring; this task does not run a production backfill or write
production data.

## Read Interface

`HistoricalMarketDataFoundation` exposes stable application-facing reads:

- `query_bars(symbol, market, interval, start, end)`
- `latest_bar(symbol, market, interval)`
- `coverage_range(symbol, market, interval)`
- `freshness_summary(symbol, market, interval)`
- `provenance_summary(symbol, market, interval)`

The returned objects and summaries expose canonical identity, coverage,
freshness, quality, provider/source provenance, as-of metadata, and
normalization lineage without leaking provider raw payload shapes.

## Product Seams

- Scanner can request `coverage_range` and `freshness_summary` before treating
  historical coverage as available for candidate workflows.
- Stock Research can request `query_bars` plus `provenance_summary` to build
  price-history evidence without understanding provider-specific rows.
- Backtest can request deterministic `query_bars` ranges and reject execution
  when quality or coverage summaries are not acceptable for the chosen run.

This is an integration contract only. It does not wire Scanner, Stock Research,
or Backtest runtime behavior to the new foundation, and it does not alter
provider priority, fallback, source-authority, scoring, fill, cost, portfolio,
or auth semantics.
