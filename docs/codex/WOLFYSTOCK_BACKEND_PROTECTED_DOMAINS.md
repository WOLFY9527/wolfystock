# WolfyStock Backend Protected Domains

Purpose: stable safety boundaries for backend tasks.

Backend prompts should refer to this file instead of repeating the same protected-domain list every time.

## Core rule

Do not modify a protected domain unless the task explicitly requires it and tests cover the semantic change.

## Contracts and boundary staging

`src/contracts` is an inert contract surface only:

- allowed: types, enums, validators, constants, and policy helpers;
- forbidden: provider runtime imports, LLM/runtime modules, API endpoints, domain services, MarketCache, DB connections, and live-call clients.

Do not add `src.contracts.providers` or `src.contracts.freshness` yet unless boundary guards and focused tests prove the namespace is inert.

Future `src/platform` or `src/domains` migrations must be planned and tested first. Do not move scanner, rotation, options, backtest, portfolio, provider, LLM, or cache runtime into a new boundary as a cleanup side effect.

The API layer should remain orchestration, not a hidden home for domain semantics.

## Protected domains

### Scanner

Do not change:
- scoring
- candidate selection
- thresholds
- ranking/sorting
- AI selection influence
- default market universe
- signal interpretation
- fallback/live labeling

Allowed only when explicitly requested:
- presentation/diagnostics metadata
- performance optimizations that preserve selected symbols/order/scores
- local-only preflight or observability

### Backtest

Do not change:
- single-symbol calculation math
- strategy math
- trade execution assumptions
- exposure formulas
- drawdown/return/win-rate calculations
- benchmark calculations
- persisted result semantics

Allowed only when explicitly requested:
- scaffolds around universe jobs
- local-only preflight
- compact diagnostics
- pagination/filtering/sorting around existing results
- performance improvements proven not to change math

### Portfolio

Do not change:
- accounting
- cash ledger semantics
- P&L calculations
- FX/native currency behavior
- holdings calculations
- transaction/corporate-action behavior
- account mutation behavior

Allowed only when explicitly requested:
- read projection optimization
- UI presentation
- compact diagnostics that do not alter accounting

### Provider runtime

Do not change:
- provider global order
- live call paths
- first-good-wins fallback
- provider/freshness contract boundaries by accident
- circuit semantics
- cache/SWR/TTL semantics
- fallback/mock/synthetic not-live semantics
- raw payload handling

Allowed only when explicitly requested:
- quota-aware optional budget skipping
- diagnostics/ledger recording that does not alter provider behavior
- cache-first advisory-only tools
- bounded fanout preserving call set and order of output

### AI decision logic

Do not change:
- prompts
- model routing
- decision thresholds
- recommendation semantics
- final advice logic
- evidence weighting

Allowed only when explicitly requested:
- metadata pass-through
- budget mode propagation that does not alter prompts
- cost/ledger diagnostics

### Auth/RBAC/security

Do not change:
- dependencies
- capabilities
- admin route protection
- session behavior
- CSRF/CORS/security middleware
- password/token handling

Allowed only when explicitly requested:
- tests proving existing enforcement
- UI/admin read-only route following existing capability pattern

### Notification routing

Do not change:
- delivery routing
- webhook/email/send behavior
- alert thresholds
- retry semantics
- real-send vs dry-run boundary

Allowed only when explicitly requested:
- read-only diagnostics
- UI organization that preserves behavior

### DuckDB / local quant storage

Do not change:
- production source-of-truth
- default disabled behavior
- local-only diagnostic nature
- no-write read diagnostics
- ingest caps

Allowed only when explicitly requested:
- local diagnostics hardening
- documentation
- tests proving disabled/no-write behavior

### MarketCache and freshness

Do not change:
- TTL/SWR behavior
- cold-start semantics
- fallback/mock/synthetic not-live semantics
- stale labels
- cache key behavior

Allowed only when explicitly requested:
- UI status consolidation
- diagnostics preserving semantics
- performance optimization that preserves response meaning

### API and stored contracts

Do not change:
- API response shapes as a cleanup side effect
- stored contract versions
- hidden compatibility semantics between API and existing clients

Allowed only when explicitly requested:
- additive fields with explicit compatibility review
- documentation or tests proving current behavior

## Required confirmation in final reports

For backend implementation tasks, final report must explicitly say which protected domains were not changed, for example:

```text
Confirmed unchanged:
- scanner scoring/selection/thresholds
- backtest calculations
- portfolio accounting
- provider runtime order/live-call paths
- AI prompts/decision logic
- auth/RBAC/security
- notification routing
- fallback/mock/synthetic live labeling
```

## Testing guidance by protected domain

Scanner:
- focused scanner tests
- provider freshness/fallback tests
- golden order/score tests if touched

Backtest:
- targeted backtest API/service tests
- `python3 -m pytest tests -q -k "backtest"` for meaningful changes
- compile backend/schema files

Portfolio:
- portfolio API/service tests
- read projection tests
- accounting regression tests if any logic touched

Provider:
- provider fallback/cache/freshness tests
- research budget/profile tests
- no live provider imports/calls in tests if applicable

Auth/RBAC:
- API contract tests
- capability enforcement tests

Notification:
- dry-run/send-boundary tests
- no real send in tests

## If a protected domain must change

Use a decision-class prompt first unless the change is small and already specified.
Explain:
- why the change is necessary
- exact semantic delta
- rollback path
- focused regression tests
- whether full `ci_gate` is required
