# WolfyStock Backtest Universe Rules

Purpose: stable constraints for large-universe backtest work.

---

## Core Rules

1. Universe backtests are local-data-only unless explicitly changed.
2. Do not call live providers.
3. Do not call `_ensure_market_history`.
4. Do not use provider fallback fetches.
5. Do not change single-symbol backtest calculations.
6. Do not add concurrency until sequential behavior is stable and tested.
7. Persist compact result rows, not giant traces.
8. Use paginated results and summary diagnostics.
9. Isolate failures per symbol.
10. Deterministic symbol order is required.

---

## Local Data Preflight

Preflight should:

- normalize/dedupe symbols deterministically;
- inspect local `StockDaily` coverage;
- classify ready / partial / missing / insufficient_data;
- record reason codes such as `blocked_missing_local_data` and `insufficient_data`;
- avoid live fetches.

---

## Sequential Execution

Sequential run should:

- load existing job;
- validate runnable status;
- process symbols in persisted deterministic order;
- read local data only;
- write compact result rows;
- update counters/status;
- isolate per-symbol failures;
- respect cancel request if model supports it;
- reject duplicate runs after execution.

Statuses may include:

```text
preflight_only
queued
running
completed
completed_with_failures
failed
cancelled
```

---

## Compact Result Rows

Store compact rows:

- symbol;
- status;
- reason_code;
- total_return_pct;
- max_drawdown_pct;
- win_rate_pct;
- trades_count;
- elapsed_ms;
- sanitized error/reason.

Avoid by default:

- full curves;
- raw traces;
- giant trade logs;
- raw provider diagnostics.

---

## Diagnostics Summary

Diagnostics endpoint should provide:

- job progress;
- total/succeeded/failed/skipped counts;
- reason buckets;
- bounded sample symbols per reason;
- metric leaders;
- average/median metrics if efficient;
- local data coverage summary;
- local-only metadata:
  - `liveProviderCallsExecuted: false`
  - `concurrencyEnabled: false`

---

## Filtering and Sorting

Results endpoint may support:

- status;
- reasonCode;
- symbol;
- market;
- sequence_index;
- total_return_pct;
- max_drawdown_pct;
- win_rate_pct;
- trades_count;
- elapsed_ms.

Rules:

- keep pagination;
- validate sort keys;
- use SQL aggregation/filtering where practical;
- keep SQLite/Postgres compatibility.

---

## Deferred Phases

Do not implement unless explicitly requested:

- bounded worker pool;
- broader cancellation subsystem;
- full per-symbol drill-down;
- frontend dashboard;
- DuckDB source of truth;
- live provider hydration.

---

## Tests

Universe backtest tasks should cover:

- no live provider calls;
- no `_ensure_market_history`;
- no provider fallback;
- deterministic order;
- per-symbol failure isolation;
- duplicate run behavior;
- progress counters;
- compact result rows;
- diagnostics aggregation;
- pagination/filter/sort;
- existing single-symbol tests unaffected.
