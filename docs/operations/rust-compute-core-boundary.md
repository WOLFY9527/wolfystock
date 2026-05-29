# Rust Compute-Core Boundary

Status: shadow-only boundary note. A pure Rust shadow CLI now exists under
`rust/rule-backtest-shadow-cli`, but no Rust code is imported by Python
runtime.

## Current status

- Python remains authoritative for all runtime behavior and outputs.
- T-643 identified the ranked rule backtest metrics/indicator/equity subset as the best first compute-core candidate.
- T-644 added Python-authoritative golden fixtures for future shadow comparison.
- T-694 added an isolated Rust CLI that reads
  `tests/fixtures/backtest/rule_backtest_compute_shadow_cli_v1.json`,
  computes the first normalized `rule_conditions` subset, and validates the
  result against the Python-authoritative expected output.

## Safest first spike

- First spike must be a pure Rust CLI shadow tool, not a PyO3 or runtime import path.
- Input boundary: JSON bars plus explicit strategy and execution assumptions.
- Output boundary: JSON metrics, equity curve, and trades.
- Python output remains the source of truth.
- Rust output may be compared only against the T-644 golden fixtures and existing Python results.
- The current CLI subset is intentionally narrow:
  `Close > MA3` entry, `Close < MA3` exit, SMA close indicator,
  single-position full-notional long/cash, `next_bar_open` entry/exit,
  `same_bar_close` terminal fallback, and bps fee/slippage.
- Any future expansion must continue to fail closed outside the documented
  normalized fixture contract.

## Explicitly forbidden in the first spike

- provider calls
- DB writes
- API or schema changes
- provider routing or provider budget changes
- routing or cache changes
- MarketCache changes
- scanner, Options authority, or portfolio behavior changes
- decisionGrade or authority changes
- frontend changes
- production runtime import, fallback, or mixed-authority execution
- PyO3, maturin, FFI glue, or any Python-callable Rust boundary

## Backlog candidates only

- portfolio risk attribution pure math
- source-confidence normalization
- scanner score/cap subset after extraction

## Non-candidates

- provider adapters
- API routes
- auth/RBAC/admin logs
- MarketCache runtime, locks, or Futures behavior
- DuckDB/quant admin surface
- frontend schema glue

## Operational rule

- If future Rust work needs Cargo, PyO3, maturin, build config, CI config, dependencies, generated artifacts, runtime imports, or any non-doc change outside a dedicated scoped task, stop and open a separate follow-up instead of widening the first spike.
- Treat the CLI as shadow verification tooling only. Do not route Python
  backtest production execution through Rust unless a separate task explicitly
  reopens authority, runtime import, and validation policy.
