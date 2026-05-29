# Backtest Transaction Cost And Slippage Readiness

Status: design note for future execution-realism work. This document does not
change current runtime, stored results, tests, exports, or backtest
calculations.

## Current State

- The current deterministic rule backtest engine accepts explicit
  `fee_bps` / `slippage_bps` assumptions when they are present and carries them
  through the stored execution-assumption surfaces.
- Those assumptions are still a bounded per-side bps model. They should not be
  described as institutional execution realism or broker-grade fill modeling.
- Current walk-forward, robustness, OOS, and parameter-readiness evidence stay
  diagnostic-only. They do not validate real execution quality, live tradability,
  optimizer selection, or production-ready cost realism.

## What Current Backtests Do Not Model

The current engine does not yet model the following execution-realism
dimensions:

- market impact;
- bid/ask spread and spread-regime changes;
- partial fills;
- limit-up, limit-down, and halt behavior;
- exchange, calendar, and session constraints;
- taxes, stamp duty, and market-specific fees;
- corporate-action-adjusted price lineage;
- liquidity or volume participation caps;
- order timing and fill-priority assumptions.

Any future documentation or UI/export wording should avoid implying that these
dimensions already exist.

## Future Design Principles

Any future execution-realism work should follow these guardrails:

- Start with local, offline fixtures first.
- Do not add live provider calls to tests.
- Do not change current golden results unless an explicit versioned contract is
  approved first.
- Version the execution model instead of silently broadening existing semantics.
- Make assumptions explicit in exports and stored read surfaces.
- Keep new readiness outputs diagnostic-only until the model is validated.

## Recommended Staged Tasks

1. Add a docs/tests fixture contract that names the execution-model assumptions
   and non-goals.
2. Design a versioned cost-model schema or projection for future additive
   execution-realism metadata.
3. Extend golden fixtures only after the versioned contract is approved.
4. Implement bounded runtime changes only after contract approval and explicit
   protected-domain review.

## Boundary Reminder

- This note does not claim any new execution realism is implemented now.
- This note does not authorize changes to current rule-backtest math, fills,
  costs, metrics, or stored result semantics.
- This note does not upgrade current OOS or parameter-readiness evidence beyond
  diagnostic-only research support.
