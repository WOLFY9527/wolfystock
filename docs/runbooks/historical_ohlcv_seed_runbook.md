# Historical OHLCV Seed Operator Runbook

Status: canonical local operator procedure
Scope: starter US daily historical OHLCV cache seed
Symbols: `SPY`, `QQQ`, `AAPL`, `MSFT`, `NVDA`, `TSLA`

This runbook describes the safe local path for inspecting, dry-running, executing, verifying, and rolling back the starter cache seed.

It does **not**:

- activate providers on application startup;
- make Scanner or Backtest appear ready when required data is missing;
- change provider order, fallback, quote coverage, source authority, or product readiness semantics;
- authorize deletion of a whole cache directory.

---

## 1. Required gates

Set these only in the operator shell used for the seed:

```bash
export WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED=true
export WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED=true
export WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED=true
```

Cache location:

- prefer `LOCAL_US_PARQUET_DIR=<local cache directory>`;
- `US_STOCK_PARQUET_DIR` is a legacy fallback;
- use an operator-owned local directory whose contents are understood before execution.

Never commit generated `.parquet`, `.csv`, `.sqlite`, verifier output, screenshots, local cache directories, or tool reports.

---

## 2. Inspect gates

```bash
python scripts/historical_ohlcv_operator_verifier.py \
  --mode inspect \
  --us-symbols SPY,QQQ,AAPL,MSFT,NVDA,TSLA
```

The output must redact environment values and report whether each required gate is enabled.

Do not proceed if the verifier prints raw credentials, raw provider URLs, or an unexpected cache path.

---

## 3. Dry run

```bash
python scripts/historical_ohlcv_operator_verifier.py \
  --mode dry-run \
  --us-symbols SPY,QQQ,AAPL,MSFT,NVDA,TSLA \
  --required-bars 60
```

Dry-run must be no-network and no-mutation.

Review:

- `nextOperatorAction`;
- gate state;
- cache path and existing rows;
- dependency state;
- intended symbols and seed actions;
- any fail-closed blocker.

---

## 4. Execute

Run only after inspect and dry-run are reviewed:

```bash
export WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED=true
export WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED=true
export WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED=true
export LOCAL_US_PARQUET_DIR=/example/local/us-parquet-cache

python scripts/historical_ohlcv_operator_verifier.py \
  --mode execute \
  --execute \
  --us-symbols SPY,QQQ,AAPL,MSFT,NVDA,TSLA \
  --required-bars 60
```

PowerShell gate setup:

```powershell
$env:WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED = "true"
$env:WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED = "true"
$env:WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED = "true"
$env:LOCAL_US_PARQUET_DIR = "C:\example\local\us-parquet-cache"
```

Without `--execute` and every required gate, execute mode must fail closed and return only a read-only preflight.

---

## 5. Verify bars written

```bash
python scripts/historical_ohlcv_operator_verifier.py \
  --mode verify-cache \
  --us-symbols SPY,QQQ,AAPL,MSFT,NVDA,TSLA \
  --required-bars 60
```

For each symbol inspect:

- `cachedBars`;
- `dateRange`;
- `freshnessState`;
- `adjustmentState`;
- source/provenance state where reported.

Zero bars, missing cache state, rejected quality, or insufficient coverage means the seed did not produce usable rows for that symbol.

---

## 6. Verify product chain

```bash
python scripts/historical_ohlcv_operator_verifier.py \
  --mode verify-chain \
  --us-symbols SPY,QQQ,AAPL,MSFT,NVDA,TSLA \
  --required-bars 60
```

### Scanner

The verifier reads the existing historical OHLCV readiness seam. Seeded rows may be visible while quote coverage still blocks candidate generation. That is expected until quote snapshot coverage is configured separately.

Do not treat historical bars alone as Scanner readiness.

### Backtest DATA-110

The same command checks `AAPL` as the symbol and `SPY` as the benchmark.

Only treat this verifier request as data-ready when:

```text
backtestReadiness.data110.status = available
backtestReadiness.data110.executable = true
```

This does not change fill, cost, benchmark, universe, execution, or stored-result semantics.

---

## 7. Rollback

Rollback removes only the six starter-symbol files from the exact operator-configured directory.

First inspect the path and matching files:

```bash
: "${LOCAL_US_PARQUET_DIR:?LOCAL_US_PARQUET_DIR must be set to the reviewed seed directory}"
printf 'CACHE_DIR=%s\n' "$LOCAL_US_PARQUET_DIR"
find "$LOCAL_US_PARQUET_DIR" -maxdepth 1 -type f \
  \( -name 'SPY.parquet' -o -name 'QQQ.parquet' -o \
     -name 'AAPL.parquet' -o -name 'MSFT.parquet' -o \
     -name 'NVDA.parquet' -o -name 'TSLA.parquet' \) \
  -print
```

After confirming the directory and files:

```bash
: "${LOCAL_US_PARQUET_DIR:?LOCAL_US_PARQUET_DIR must be set to the reviewed seed directory}"
rm -f -- \
  "$LOCAL_US_PARQUET_DIR/SPY.parquet" \
  "$LOCAL_US_PARQUET_DIR/QQQ.parquet" \
  "$LOCAL_US_PARQUET_DIR/AAPL.parquet" \
  "$LOCAL_US_PARQUET_DIR/MSFT.parquet" \
  "$LOCAL_US_PARQUET_DIR/NVDA.parquet" \
  "$LOCAL_US_PARQUET_DIR/TSLA.parquet"
```

PowerShell inspection:

```powershell
if (-not $env:LOCAL_US_PARQUET_DIR) {
  throw "LOCAL_US_PARQUET_DIR must be set to the reviewed seed directory"
}

$starterFiles = @(
  "SPY.parquet",
  "QQQ.parquet",
  "AAPL.parquet",
  "MSFT.parquet",
  "NVDA.parquet",
  "TSLA.parquet"
)

$starterFiles |
  ForEach-Object { Join-Path $env:LOCAL_US_PARQUET_DIR $_ } |
  Where-Object { Test-Path -LiteralPath $_ }
```

PowerShell removal after review:

```powershell
if (-not $env:LOCAL_US_PARQUET_DIR) {
  throw "LOCAL_US_PARQUET_DIR must be set to the reviewed seed directory"
}

$starterFiles = @(
  "SPY.parquet",
  "QQQ.parquet",
  "AAPL.parquet",
  "MSFT.parquet",
  "NVDA.parquet",
  "TSLA.parquet"
)

$starterFiles |
  ForEach-Object { Join-Path $env:LOCAL_US_PARQUET_DIR $_ } |
  ForEach-Object { Remove-Item -LiteralPath $_ -ErrorAction SilentlyContinue }
```

Do not delete the broader cache directory unless it was created exclusively for this seed attempt and its complete contents have been reviewed.

---

## 8. Completion evidence

Record only sanitized evidence:

```text
verifier mode and exit status
symbol coverage counts and date ranges
quality/freshness classifications
Scanner readiness classification
Backtest DATA-110 classification
exact local cache directory ownership confirmation
rollback status if performed
```

Do not store raw environment values, credentials, provider payloads, personal paths, or generated data files in repository documentation.
