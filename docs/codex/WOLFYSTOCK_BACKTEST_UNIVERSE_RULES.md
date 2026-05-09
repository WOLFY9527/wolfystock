# WolfyStock Backtest Universe Rules

Purpose: stable constraints for large-universe backtest work.

## Current architecture baseline

Backtest universe work has progressed through:
1. local-only universe job scaffold
2. local data coverage preflight
3. local-only sequential execution
4. diagnostics summary / reason buckets / metric leaders / filters / sorts

The next phases should build on this without changing single-symbol strategy math.

## Core rules

1. Universe backtests are local-data-only unless explicitly changed.
2. Do not call live providers.
3. Do not call `_ensure_market_history`.
4. Do not use provider fallback fetches.
5. Do not change single-symbol backtest calculations.
6. Do not add concurrency until sequential behavior is stable and tested.
7. Persist compact result rows, not giant traces.
8. Use paginated results and summary diagnostics.
9. Failures must be isolated per symbol.
10. Deterministic symbol order is required.

## Local data preflight

Preflight should:
- normalize/dedupe symbols deterministically
- inspect local `StockDaily` coverage
- classify:
  - ready
  - partial
  - missing
  - insufficient_data
- record reason codes such as:
  - blocked_missing_local_data
  - insufficient_data
- avoid live fetches

## Sequential execution

Sequential run should:
- load existing job
- validate runnable status
- process symbols in persisted deterministic order
- read local data only
- write compact result rows
- update counters and status
- isolate per-symbol failures
- respect cancel request if model supports it
- reject duplicate runs after execution

Statuses may include:
- preflight_only
- queued
- running
- completed
- completed_with_failures
- failed
- cancelled

## Compact result rows

Result rows should be compact:
- symbol
- status
- reason_code
- total_return_pct
- max_drawdown_pct
- win_rate_pct
- trades_count
- elapsed_ms
- sanitized error/reason

Avoid storing by default:
- full curves
- raw traces
- giant trade logs
- raw provider diagnostics

Full drill-down is a later phase.

## Diagnostics summary

Diagnostics endpoint should provide:
- job progress
- total/succeeded/failed/skipped counts
- reason buckets
- sample symbols per reason, bounded
- metric leaders:
  - top return
  - worst return
  - worst drawdown
  - best win rate
- average/median metrics if efficient
- local data coverage summary
- local-only metadata:
  - liveProviderCallsExecuted: false
  - concurrencyEnabled: false

## Filtering and sorting

Results endpoint may support:
- status
- reasonCode
- symbol
- market
- sequence_index
- total_return_pct
- max_drawdown_pct
- win_rate_pct
- trades_count
- elapsed_ms

Rules:
- keep pagination
- validate sort keys
- use SQL aggregation/filtering where practical
- keep SQLite/Postgres compatibility

## Deferred phases

Do not implement unless explicitly requested:
- bounded worker pool
- broader cancellation API/subsystem
- full per-symbol drill-down
- frontend dashboard
- DuckDB source of truth
- live provider hydration

## Worker pool phase requirements

Before adding concurrency:
- decision-class prompt recommended
- define worker count
- define DB session strategy
- define single writer or safe writes
- define cancellation
- define retry policy
- benchmark sequential baseline
- prove no calculation changes

## Tests

Universe backtest tasks should cover:
- no live provider calls
- no `_ensure_market_history`
- no provider fallback
- deterministic order
- per-symbol failure isolation
- duplicate run behavior
- progress counters
- compact result rows
- diagnostics aggregation
- pagination/filter/sort
- existing single-symbol tests unaffected

Useful commands:

```bash
python3 -m pytest tests/test_rule_backtest_universe_service.py tests/test_backtest_api_contract.py -q
python3 -m pytest tests -q -k "backtest"
python3 -m py_compile src/services/rule_backtest_service.py src/repositories/rule_backtest_repo.py src/services/local_data_preflight_service.py src/storage.py api/v1/endpoints/backtest.py api/v1/schemas/backtest.py
python3 -m py_compile scripts/backtest_large_universe_benchmark.py
```

## Final report must include

- local-only guarantees
- endpoint/service method names
- status/progress behavior
- filters/sorts added
- failure isolation behavior
- deferred items
- confirmation no single-symbol math changed
- confirmation no provider/runtime changes
