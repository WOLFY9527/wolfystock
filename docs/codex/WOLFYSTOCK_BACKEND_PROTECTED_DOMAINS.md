# WolfyStock Backend Protected Domains

Purpose: stable safety boundaries for backend tasks.

Core rule: do not modify a protected domain unless the task explicitly requires it and tests cover the semantic change.

---

## Protected Domains

### Scanner

Do not change scoring, candidate selection, thresholds, ranking/sorting, AI selection influence, default universe, signal interpretation, or fallback/live labeling unless explicitly scoped.

Allowed only when scoped: presentation metadata, diagnostics metadata, performance optimizations that preserve selected symbols/order/scores, local-only observability.

### Backtest

Do not change single-symbol calculation math, strategy math, fills, costs, exposure formulas, drawdown/return/win-rate calculations, benchmark calculations, or persisted result semantics unless explicitly scoped.

### Portfolio

Do not change accounting, cash ledger, P&L, FX/native currency, holdings, cost basis, transaction/corporate-action behavior, account mutation behavior, or broker sync unless explicitly scoped.

### Provider Runtime

Do not change provider global order, live call paths, first-good-wins fallback, circuit semantics, cache/SWR/TTL semantics, fallback/mock/synthetic not-live semantics, or raw payload handling unless explicitly scoped.

### MarketCache and Freshness

Do not change TTL/SWR behavior, cold-start semantics, fallback/mock/synthetic live labeling, stale labels, cache key behavior, or payload meaning unless explicitly scoped.

### AI Decision Logic

Do not change prompts, model routing, decision thresholds, recommendation semantics, final advice logic, or evidence weighting unless explicitly scoped.

### Auth/RBAC/Security

Do not change dependencies, capabilities, admin route protection, session behavior, CSRF/CORS/security middleware, password/token handling, or permission checks unless explicitly scoped.

### Notification Routing

Do not change delivery routing, webhook/email/send behavior, alert thresholds, retry semantics, or real-send/dry-run boundary unless explicitly scoped.

### DuckDB / Local Quant Storage

Do not change production source-of-truth behavior, default disabled behavior, local-only diagnostics, no-write read diagnostics, or ingest caps unless explicitly scoped.

### Options Lab

Do not change ranking, gates, scoring, payoff math, optimizer behavior, no-trade policy, provider/runtime behavior, public API response shape, or aliases unless explicitly scoped.

### API and Stored Contracts

Do not change API response shapes, stored contract versions, or hidden compatibility semantics as a cleanup side effect.

---

## Inert Contract Surface Rule

`src/contracts` is an inert contract surface only.

Allowed:

- types;
- enums;
- validators;
- constants;
- policy helpers.

Forbidden:

- provider runtime imports;
- LLM/runtime modules;
- API endpoints;
- domain services;
- MarketCache;
- DB connections;
- live-call clients.

Do not create new boundary namespaces such as `src.contracts.providers` unless guards/tests prove they remain inert.

---

## Final Report Requirement

Backend implementation final reports must state:

- which protected domains were touched;
- which protected domains were explicitly confirmed unchanged;
- tests proving no unintended semantic change;
- API response-shape impact;
- fallback/mock/live-labeling impact.
