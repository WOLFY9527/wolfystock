# Historical Market Data Foundation

Contract version: 1
Status: canonical internal contract; integration coverage remains incremental
Owner: historical market-data foundation and repository boundary

WolfyStock historical market-data consumers must use the canonical foundation contract instead of provider-shaped payloads.

```text
Raw provider observation
→ adapter / normalizer
→ CanonicalHistoricalBar
→ HistoricalBarQualityOutcome
→ HistoricalMarketDataRepository
→ HistoricalMarketDataFoundation read methods
→ product integration contract
```

This contract does not authorize changes to provider priority, fallback, source authority, Scanner ranking, Backtest fills/costs, Portfolio accounting, auth, or production backfill behavior.

---

## 1. Canonical bar

`src.services.historical_market_data_foundation.CanonicalHistoricalBar` is the canonical internal bar model.

It carries:

- market, venue and canonical symbol identity;
- provider symbol and interval;
- session date and optional observation timestamp;
- market timezone;
- OHLCV values;
- adjustment metadata;
- currency;
- provider/source identity;
- observation and as-of metadata;
- ingestion and lineage identifiers;
- normalization version;
- quality state.

Provider-specific names such as `Adj Close`, `Date`, `开盘` or `成交量` must remain inside `normalize_provider_historical_bars` or an equivalent owned adapter.

Product consumers must not depend on raw provider field names or payload shape.

---

## 2. Truth and quality invariants

```text
missing != zero
rejected != empty success
degraded != fully authoritative
provider timestamp != ingestion time
stale != fresh
proxy != official
```

Quality validation is deterministic. It must not repair, interpolate, forward-fill or fabricate missing historical bars.

`HistoricalBarQualityOutcome` exposes three product-facing classes:

### `usable`

- product-readable;
- canonical identity is valid;
- ordering and values are valid;
- no quality reason code requires degraded treatment.

### `degraded`

- product-readable with explicit reason codes;
- examples include `missing_session_gap` or `source_metadata_gap`;
- missing bars remain missing;
- consumers must preserve the degraded classification.

### `rejected`

Not product-readable for conditions such as:

- invalid market or symbol identity;
- malformed date/timestamp;
- invalid OHLC relationship;
- negative price or volume values where forbidden;
- non-monotonic ordering;
- conflicting duplicate observations.

Consumers must not convert rejected rows into empty-success, neutral or zero-valued evidence.

---

## 3. Persistence contract

`src.repositories.historical_market_data_repo.HistoricalMarketDataRepository` owns idempotent persistence for this foundation.

Natural key:

```text
market
+ canonical_symbol
+ interval
+ session_date
+ provider
+ adjustment_status
```

Rules:

- repeated ingestion of the same logical observation is a duplicate, not a new bar;
- conflicting re-ingestion is rejected;
- an existing canonical row is preserved when the incoming observation conflicts;
- persistence must retain lineage and quality metadata needed by read consumers;
- repository-owned tables and migrations must stay inside explicit task scope;
- no production backfill or destructive migration is implied by this contract.

---

## 4. Read interface

`HistoricalMarketDataFoundation` exposes stable application-facing reads:

```text
query_bars(symbol, market, interval, start, end)
latest_bar(symbol, market, interval)
coverage_range(symbol, market, interval)
freshness_summary(symbol, market, interval)
provenance_summary(symbol, market, interval)
```

Returned records and summaries must expose enough information to preserve:

- canonical identity;
- requested and observed coverage;
- freshness and as-of state;
- quality classification and reason codes;
- provider/source provenance;
- adjustment state;
- normalization lineage.

They must not leak raw provider payloads or provider-specific field names.

---

## 5. Product integration seams

### Scanner

Scanner may request `coverage_range` and `freshness_summary` before treating historical coverage as available.

Historical coverage alone does not prove quote readiness, universe readiness, candidate eligibility or score eligibility.

### Stock Research

Stock Research may request `query_bars` and `provenance_summary` to construct price-history evidence without understanding provider-specific rows.

A page must preserve missing, stale, degraded and rejected states rather than fabricating a continuous chart.

### Backtest

Backtest may request deterministic ranges through `query_bars` and reject execution when quality, coverage, benchmark or adjustment requirements are not satisfied.

This contract does not change fill, cost, benchmark, calendar, universe, execution or stored-result authority.

---

## 6. Current implementation boundary

Implemented foundation capabilities and product wiring are not the same thing.

A capability is product-integrated only when the relevant consumer has:

1. an owned adapter/read path;
2. explicit quality and freshness handling;
3. focused tests;
4. canonical integration validation;
5. consumer-safe state presentation where applicable.

Until then, describe the seam as available for integration, not as production-ready product coverage.

---

## 7. Versioning and changes

A contract-version change is required when a change breaks or materially redefines:

- canonical identity;
- natural-key semantics;
- adjustment semantics;
- quality classifications;
- read-method behavior;
- provenance or freshness meaning.

Additive metadata that preserves existing meaning may remain within the current version when consumers are backward compatible.

Any change touching provider authority, persistence migration, Scanner eligibility, Backtest execution or public API schema requires explicit ownership and focused plus canonical validation.

---

## 8. Validation authority

At minimum, changes to this contract should validate:

```text
normalization fixtures
quality classification
idempotent duplicate handling
conflict rejection
ordering and range reads
coverage/freshness/provenance summaries
no provider-shape leakage
relevant Scanner / Stock Research / Backtest seam tests
canonical backend gate when shared behavior changed
```

Documentation alone is not readiness evidence.
