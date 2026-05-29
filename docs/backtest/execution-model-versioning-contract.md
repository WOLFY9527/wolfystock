# Backtest Execution Model Versioning Contract

Status: design note for future rule-backtest execution-realism work. This
document does not change current runtime, stored results, tests, exports, or
backtest calculations.

## Current Default

- Current rule backtest semantics remain the existing/default execution model.
- Current fee/slippage handling remains a bounded per-side bps assumption model,
  not institutional execution realism.
- Current golden results, stored results, exports, and diagnostic/readiness
  evidence must keep their present meaning unless a future versioned contract is
  approved first.

## Why Versioning Is Required

Fee or slippage bps assumptions alone are not equivalent to institutional
execution realism. They do not, by themselves, model spread regimes, impact,
partial fills, venue/session constraints, or market-specific execution
frictions. Any future execution-realism work must therefore be introduced as a
new explicit execution model version instead of being folded into the current
default semantics.

## Versioning Principles

Any future execution-realism model must satisfy all of the following before
runtime work is approved:

- Every new execution realism model must have an explicit execution model
  version id.
- Exports must show the execution model id and the assumptions used by that
  model.
- Stored results must remain interpretable under the exact execution model that
  produced them.
- Existing golden fixtures cannot be overwritten in place; a new execution
  model requires a new versioned golden contract.
- Diagnostic/readiness evidence must not be promoted to decision-grade
  execution realism by wording, projection, or implied semantics.

## What A Future Versioned Model May Include

The following execution-realism dimensions may be added only after explicit
contract approval for a new versioned model:

- spread model;
- market impact;
- partial fills;
- volume participation caps;
- halt/limit behavior;
- taxes, stamp duty, and market-specific fees;
- calendar and session constraints;
- corporate-action adjusted price lineage.

This note does not imply that any of the items above are implemented now.

## Migration Safety Rules

Any future execution-model versioning work must preserve these boundaries:

- no silent recalculation of stored results;
- no provider or live-call requirement in tests;
- no API or export semantic changes without additive or versioned contracts;
- no change to scanner, portfolio, options, provider, or MarketCache
  semantics.

## Recommended Future Task Order

1. Define a fixture contract for execution model metadata.
2. Add an additive schema/export projection for execution model id and
   assumptions.
3. Create a new versioned golden fixture for the approved model.
4. Implement bounded runtime behavior behind explicit execution model
   selection.

## Boundary Reminder

- This note does not authorize any change to current backtest calculations,
  fills, costs, metrics, or stored-result meaning.
- This note does not authorize runtime, service, test, API, schema, export,
  frontend, provider, or config changes.
- This note keeps current diagnostic/readiness evidence in the research-only
  lane unless a later versioned contract explicitly says otherwise.
