# Historical OHLCV Seed Operator Runbook

> Status: Canonical runbook
> Contract: [`docs/contracts/historical-market-data.md`](../contracts/historical-market-data.md)
> Scope: explicit local starter-symbol cache seeding; no startup activation or readiness override

This runbook covers the safe local path for attempting and verifying the
starter US historical OHLCV cache seed for `SPY`, `QQQ`, `AAPL`, `MSFT`, `NVDA`, and `TSLA`.
It does not enable providers on app startup and does not make Scanner or
Backtest results appear successful when data is missing.

## Required Gates

Set these only in the operator shell that will run the seed:

- `WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED=true`
- `WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED=true`
- `WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED=true`

Cache location:

- Prefer `LOCAL_US_PARQUET_DIR=<local cache directory>`.
- `US_STOCK_PARQUET_DIR` is a legacy fallback.
- Do not commit generated `.parquet`, `.csv`, `.sqlite`, run output, screenshots,
  WorkBuddy output, or local cache directories.

## Inspect Gates

```bash
python scripts/historical_ohlcv_operator_verifier.py --mode inspect --us-symbols SPY,QQQ,AAPL,MSFT,NVDA,TSLA
```

The output redacts env values and reports whether each gate is enabled.

## Dry Run

```bash
python scripts/historical_ohlcv_operator_verifier.py --mode dry-run --us-symbols SPY,QQQ,AAPL,MSFT,NVDA,TSLA --required-bars 60
```

Dry-run is no-network and no-mutation. Review `nextOperatorAction`, cache
state, dependency state, and intended seed actions before executing.

## Execute Template

Run execute only after inspect and dry-run are reviewed:

```bash
export WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED=true
export WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED=true
export WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED=true
export LOCAL_US_PARQUET_DIR=/example/local/us-parquet-cache

python scripts/historical_ohlcv_operator_verifier.py --mode execute --execute --us-symbols SPY,QQQ,AAPL,MSFT,NVDA,TSLA --required-bars 60
```

PowerShell equivalent for the gates:

```powershell
$env:WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED = "true"
$env:WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED = "true"
$env:WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED = "true"
$env:LOCAL_US_PARQUET_DIR = "C:\example\local\us-parquet-cache"
```

Without `--execute` and all required gates, execute mode fails closed and only
reports a read-only preflight.

## Verify Bars Written

```bash
python scripts/historical_ohlcv_operator_verifier.py --mode verify-cache --us-symbols SPY,QQQ,AAPL,MSFT,NVDA,TSLA --required-bars 60
```

Check `cacheRows[*].cachedBars`, `dateRange`, `freshnessState`, and
`adjustmentState`. Zero bars or missing cache state means the local seed did
not produce usable rows for that symbol.

## Verify Scanner Readiness

```bash
python scripts/historical_ohlcv_operator_verifier.py --mode verify-chain --us-symbols SPY,QQQ,AAPL,MSFT,NVDA,TSLA --required-bars 60
```

Scanner verification reads the existing historical OHLCV readiness seam. It can
show that seeded cache rows are visible, but quote coverage may still block
candidate generation. That is expected until quote snapshot coverage is
configured separately.

## Verify Backtest DATA-110

The same `verify-chain` command checks Backtest DATA-110 with `AAPL` as the
symbol and `SPY` as the benchmark. `backtestReadiness.data110.status` must be
`available` and `executable` must be `true` before treating symbol and benchmark
OHLCV coverage as ready for that verifier request.

## Rollback / Cleanup

To undo local generated cache files, remove only the starter-symbol parquet
files from the local cache directory you configured:

```bash
test -n "$LOCAL_US_PARQUET_DIR" && rm -f \
  "$LOCAL_US_PARQUET_DIR"/SPY.parquet \
  "$LOCAL_US_PARQUET_DIR"/QQQ.parquet \
  "$LOCAL_US_PARQUET_DIR"/AAPL.parquet \
  "$LOCAL_US_PARQUET_DIR"/MSFT.parquet
```

PowerShell:

```powershell
if ($env:LOCAL_US_PARQUET_DIR) {
  Remove-Item -LiteralPath `
    "$env:LOCAL_US_PARQUET_DIR\SPY.parquet", `
    "$env:LOCAL_US_PARQUET_DIR\QQQ.parquet", `
    "$env:LOCAL_US_PARQUET_DIR\AAPL.parquet", `
    "$env:LOCAL_US_PARQUET_DIR\MSFT.parquet" `
    -ErrorAction SilentlyContinue
}
```

Do not delete broader cache directories unless you created them specifically
for this seed attempt.
