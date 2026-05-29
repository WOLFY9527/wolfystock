# Backtest PIT Universe And Adjusted Data Readiness

Status: design note for future institutional-grade backtest data-readiness
work. This document does not change current runtime, stored results, tests,
exports, provider behavior, or backtest calculations.

## Current State

- Current backtest local-only and source-contract boundaries are useful
  research safeguards, but they are not equivalent to institutional
  point-in-time universe membership or adjusted corporate-action data
  contracts.
- Current backtest outputs must not be claimed as free of survivorship bias,
  corporate-action bias, calendar bias, or adjustment-lineage gaps unless a
  future approved contract proves those properties explicitly.
- Current local/history data should therefore be treated as bounded research
  input, not as PIT-adjusted institutional research data by default.

## Required Future Data Contracts

The following contracts must exist before institutional-grade PIT or
adjusted-data claims are allowed:

- point-in-time universe membership with effective dates;
- delisting and inactive-symbol handling;
- split, dividend, and corporate-action adjusted OHLC lineage;
- explicit adjustment methodology and version;
- exchange calendar and session alignment;
- asset identifier mapping and symbol-change lineage;
- data `as_of` timestamp and vendor/source provenance;
- missing-bar and stale-bar policy;
- reproducibility of historical snapshots.

Without these contracts, current outputs remain useful for local research but
not validated as institution-grade PIT-adjusted evidence.

## Safety Principles

Any future PIT-universe or adjusted-data work should preserve these boundaries:

- start with local and offline fixtures first;
- do not add live provider calls to tests;
- do not allow silent provider fallback in backtest research paths;
- do not silently recalculate stored results;
- add additive or versioned metadata before any runtime use;
- do not make decision-grade institutional claims until PIT and
  adjusted-data evidence exists.

## Recommended Staged Tasks

1. Define a fixture contract for PIT universe and adjusted OHLC metadata.
2. Add a versioned data-provenance projection.
3. Extend golden or readback fixtures for the approved contract.
4. Implement bounded local-only runtime behavior only after contract approval.

## Boundary Reminder

- This task implements none of the future data contracts listed above.
- This note does not authorize runtime, service, test, API, schema, export,
  frontend, provider, config, or generated-file changes.
- This note does not change current backtest calculations, exports,
  stored-result semantics, local-only guards, or provider fallback behavior.
