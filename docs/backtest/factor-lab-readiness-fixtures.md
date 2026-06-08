# Backtest Factor Lab Readiness Fixtures

Status: fixture catalog for observe-only Backtest + Factor Lab readiness packet
states.

Related contract: [Backtest Factor Lab Readiness Contract](./factor-lab-readiness-contract.md)
Test coverage: `tests/test_backtest_factor_lab_readiness_fixtures.py`

## Observe-Only Meaning

These fixtures exercise the metadata helper only:

- `src/services/backtest_factor_lab_readiness.py`
- `build_backtest_factor_lab_readiness_packet(...)`

The packet remains observe-only in every state, including when
`professionalReady` becomes `true`.

Observe-only means:

- the helper aggregates caller-supplied metadata only;
- no backtest engine runs;
- no provider, cache, DB, API, or frontend runtime path executes;
- no calculation math, fills, costs, metrics, or stored result semantics change;
- `professionalReady: true` only means every tracked P0/P1 prerequisite is
  explicitly present in metadata supplied by the caller.

It does not mean the helper independently verified those prerequisites in live
runtime.

## Fixture Catalog

| Fixture | Purpose | Expected outcome |
| --- | --- | --- |
| `prototype_ready` | Shows a research-prototype packet with all P0 dimensions explicit while some P1 evidence remains absent. | `observeOnly: true`, `professionalReady: false`, `blockingPriority: P1` |
| `missing_p0` | Proves an explicit P0 gap keeps the packet fail-closed even when all P1 dimensions are present. | `observeOnly: true`, `professionalReady: false`, `blockingPriority: P0` |
| `missing_p1` | Proves a single explicit P1 gap still blocks professional readiness after every P0 dimension is explicit. | `observeOnly: true`, `professionalReady: false`, `blockingPriority: P1` |
| `ambiguous_lineage` | Proves mixed dataset lineage evidence stays ambiguous and blocks readiness at P0 priority. | `observeOnly: true`, `professionalReady: false`, `blockingPriority: P0` |
| `all_prerequisites_present` | Proves readiness flips only when every tracked P0/P1 prerequisite is explicit. | `observeOnly: true`, `professionalReady: true`, `blockingPriority: none` |

## State-Specific Notes

### `prototype_ready`

This fixture is intentionally stronger than the default empty-input case: it
shows a caller can supply explicit PIT, survivorship, corporate-action,
calendar, transaction-cost, rebalance, and lineage coverage and still remain
not professionally ready because `oos_walk_forward` and
`parameter_stability` are still ambiguous.

### `missing_p0`

This fixture isolates `transaction_cost_realism` as an explicit missing P0
dimension. It proves P0 blockers continue to outrank otherwise complete P1
coverage.

### `missing_p1`

This fixture isolates `parameter_stability` as an explicit missing P1
dimension after every P0 dimension is explicit. It proves professional
readiness still stays false even when the packet is otherwise complete.

### `ambiguous_lineage`

This fixture uses mixed dataset-version evidence (`available` plus `unknown`)
to keep the lineage dimension ambiguous. Ambiguous lineage remains blocking
because unknown or mixed evidence must fail closed.

### `all_prerequisites_present`

This fixture is the only catalog state where `professionalReady` becomes true.
It should be treated as a completeness proof for caller-supplied metadata, not
as an authorization to widen runtime claims.

## Forbidden Claims

These fixtures must not be used to claim any of the following:

- live trading readiness;
- personalized financial advice;
- broker/order execution approval;
- independent validation of backtest engine math;
- independent validation of provider/runtime/cache/storage behavior;
- stored result semantics changed or upgraded;
- institutional or decision-grade execution realism beyond caller-supplied
  metadata.
