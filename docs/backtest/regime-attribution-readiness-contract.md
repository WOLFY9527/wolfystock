# Backtest Regime Attribution Readiness Contract

Status: design note for future regime-attribution and performance-decomposition
work. This document does not change current runtime, stored results, tests,
exports, or backtest calculations.

## Current State

- Current regime/readiness surfaces are research/readback scaffolds only.
  Stored-first exports such as `regime_attribution_readiness_json`, and any
  existing regime-named summary/readback projections, must be treated as
  diagnostic-only metadata rather than validated institutional attribution.
- Current backtest outputs do not provide validated market-regime PnL
  attribution, benchmark-relative regime decomposition, or decision-grade
  performance causality.
- Current regime/readiness wording must not imply that the system can already
  explain realized PnL by regime source, regime interval, or execution-period
  causality.

## Missing Institutional Requirements

The following requirements are not yet locked as an approved contract and must
exist before regime attribution can be promoted beyond diagnostic readiness:

- explicit regime source and source version;
- explicit regime timestamp and `as_of` policy;
- explicit join policy between bars, trades, equity-curve rows, and regime
  labels;
- explicit daily PnL allocation rules;
- explicit handling for missing, overlapping, or conflicting regime labels;
- explicit asset, market-session, and trading-calendar alignment rules;
- explicit benchmark attribution assumptions;
- explicit transaction-cost interaction rules;
- explicit reproducibility and stored-result lineage rules.

Without those requirements, any regime-labeled output remains a projection or
gap report, not validated attribution.

## Future Design Principles

Any future regime-attribution work should keep these boundaries:

- start with local, offline fixtures first;
- do not add live provider calls to tests;
- use additive or versioned export metadata instead of mutating existing
  contracts in place;
- do not silently recalculate stored results;
- do not promote regime attribution to decision-grade until validated;
- do not change existing golden results without an explicit versioned contract.

## Recommended Staged Tasks

1. Define a fixture contract for regime-attribution metadata and non-goals.
2. Add a versioned regime-source and join-policy schema or projection.
3. Create a new versioned golden/readback fixture for the approved contract.
4. Implement bounded runtime behavior only after contract approval.

## Boundary Reminder

- This note does not claim that regime attribution is fully implemented today.
- This note does not authorize runtime, service, test, API, schema, export,
  frontend, provider, config, or stored-result semantic changes.
- This note does not change current backtest calculations, exports, readback
  meaning, or existing stored results.
