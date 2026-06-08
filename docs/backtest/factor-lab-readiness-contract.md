# Backtest Factor Lab Readiness Contract

Status: observe-only readiness packet for Backtest + Factor Lab metadata.

This contract defines a pure helper that aggregates caller-supplied metadata
into a research-readiness packet. It does not run any engine, provider, cache,
DB, API, frontend, or network path, and it does not change stored backtest
semantics.

## Helper

- Module: `src/services/backtest_factor_lab_readiness.py`
- Entrypoint: `build_backtest_factor_lab_readiness_packet(...)`
- Output: deterministic JSON-safe dict
- Input source: caller-supplied metadata only

The helper accepts bounded metadata through these inputs:

- `backtest_readiness`
- `factor_metrics_availability`
- `bridge_manifest`
- `data_lineage`
- `missing_professional_prerequisites`

Unknown, partial, mixed, or missing evidence must fail closed.

## Output Guardrails

The packet is always:

- observe-only
- research-readiness only
- additive to existing contracts
- safe by default when evidence is missing

The packet must not:

- run backtest engines
- call providers
- touch `MarketCache`
- read or write DB/storage
- import API/frontend modules
- alter calculations, fills, costs, returns, drawdown, win-rate, benchmarks, or stored result meaning

## Professional Readiness Rule

`professionalReady` may be `true` only when every tracked prerequisite is
explicitly present in caller-supplied metadata. Otherwise the packet must stay:

- `observeOnly: true`
- `professionalReady: false`
- `productState: observe_only_not_professional_ready`

## Tracked Dimensions

### P0 professional prerequisites

- `pit_as_of`
  - point-in-time universe membership
  - as-of timestamp policy
- `survivorship_delisted`
  - survivorship-safe universe evidence
  - delisted/inactive-symbol handling
- `corporate_actions`
  - corporate-action-adjusted OHLC lineage
- `calendar_session_halt_constraints`
  - exchange calendar alignment
  - session constraints
  - halt constraints
- `transaction_cost_realism`
  - transaction-cost model
  - slippage model
  - market-impact model
- `portfolio_rebalance_model`
- `dataset_snapshot_version_source_authority`
  - dataset snapshot
  - dataset version
  - source authority

### P1 factor prerequisites

- `decile_returns`
- `panel_contract`
- `forward_return_generation`
- `neutralization`
- `factor_correlation`
- `multi_factor_composition`
- `oos_walk_forward`
- `parameter_stability`

## State Model

Each dimension and component is reported as one of:

- `available`
- `missing`
- `ambiguous`

Rules:

- `available`: explicit positive evidence is present
- `missing`: caller explicitly marks the prerequisite missing, or only explicit negative evidence is present
- `ambiguous`: no explicit evidence, mixed evidence, or unknown evidence

`missing` and `ambiguous` both block `professionalReady`.

## Contract Shape

The packet returns these top-level fields:

- `packetKind`
- `packetVersion`
- `observeOnly`
- `professionalReady`
- `productState`
- `summary`
- `inputObservations`
- `dimensionCounts`
- `blockingPriority`
- `blockingDimensionIds`
- `dimensions`

`dimensions` contains ordered `p0` and `p1` lists. Each item includes:

- `id`
- `priority`
- `label`
- `state`
- `ready`
- `summary`
- `missingReasonCodes`
- `components`

Each component includes:

- `id`
- `label`
- `state`
- `ready`
- `summary`
- `missingReasonCodes`
- `evidencePaths`
- `sourceSections`

## Boundary Reminder

This contract does not authorize changes to:

- backtest calculation math
- trade execution assumptions
- exposure/return/drawdown/win-rate/benchmark semantics
- stored backtest result semantics
- provider runtime order or fallback behavior
- `MarketCache`
- API schemas
- frontend/runtime wiring
- DB/storage paths
