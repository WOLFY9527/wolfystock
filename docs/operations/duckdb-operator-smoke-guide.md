# DuckDB Operator Smoke Guide

## Purpose

DuckDB is an optional analytics accelerator for local quant validation, coverage checks, research queries, and benchmark scans. PostgreSQL remains the business database for users, portfolio accounting, watchlists, admin logs, settings, analysis tasks, and backtest metadata.

DuckDB is disabled by default with `QUANT_DUCKDB_ENABLED=false`. Phase 1, Phase 1.5, and Phase 2 do not change scanner, backtest, or portfolio runtime paths. This guide is for safe local operator smoke testing and validation only.

## Safety Principles

- Do not use `pg_duckdb`.
- Do not require or install a PostgreSQL extension.
- Do not run unbounded full-market ingestion by accident.
- Do not commit generated `*.duckdb` or `*.duckdb.wal` files.
- Use temp or explicitly local database paths for smoke tests.
- Disabled mode must not create or write a DuckDB file.
- Parquet import/export is reserved for a planned future path unless a later implementation explicitly adds it.

## Relevant Config Keys

```env
QUANT_ENGINE=python
QUANT_DUCKDB_ENABLED=false
DUCKDB_DATABASE_PATH=data/quant/wolfystock.duckdb
QUANT_PARQUET_ROOT=data/quant/parquet
QUANT_MAX_BENCHMARK_SYMBOLS=5000
```

- `QUANT_ENGINE`: keeps the default runtime engine on the existing Python path.
- `QUANT_DUCKDB_ENABLED`: explicit opt-in for DuckDB operations. Keep `false` unless running a local smoke.
- `DUCKDB_DATABASE_PATH`: target DuckDB file. Use a temp path for operator smoke checks.
- `QUANT_PARQUET_ROOT`: reserved root for future Parquet snapshot import/export.
- `QUANT_MAX_BENCHMARK_SYMBOLS`: upper bound for existing-store ingest and benchmark symbol selection.

Phase 1.5 introduces no additional config beyond the keys above.

## API Endpoints

All endpoints are admin-only. If admin auth is enabled, include the same authenticated session/cookie/header used by local admin API calls. Examples below use `API_BASE` and `AUTH_HEADER` placeholders.

| Endpoint | Purpose | Writes when | Disabled behavior | Key response fields |
| --- | --- | --- | --- | --- |
| `GET /api/v1/quant/duckdb/health` | Report safe availability and schema state. | Never writes in disabled mode; checks schema only when enabled and available. | Returns `status=disabled`, `enabled=false`, and must not create the DB file. | `enabled`, `available`, `databasePath`, `parquetRoot`, `version`, `schemaInitialized`, `status`, `engine`, `error` |
| `POST /api/v1/quant/duckdb/init` | Create DuckDB quant tables. | Writes only when enabled, unless `allowWhenDisabled=true` is deliberately sent. | Default request returns `status=disabled` and does not write. | `status`, `engine`, `version`, `schemaInitialized`, `error` |
| `POST /api/v1/quant/duckdb/ingest-ohlcv` | Ingest normalized payload rows or bounded local `StockDaily` rows. | Writes only when enabled, schema exists, and `dryRun=false`. | Returns `status=disabled`, zero row counts, and does not write. | `status`, `source`, `ingestedRows`, `availableRows`, `symbolCount`, `symbolsRequested`, `durationMs`, `error` |
| `POST /api/v1/quant/duckdb/build-factors` | Build basic daily factors from ingested OHLCV rows. | Writes only when enabled and schema exists. | Returns `status=disabled` and does not write. | `status`, `ohlcvRows`, `factorRows`, `factorCount`, `durationMs`, `error` |
| `GET /api/v1/quant/duckdb/coverage` | Report OHLCV/factor coverage and sample symbols. | Reads only after connecting to an enabled DuckDB database. | Returns disabled/empty coverage with `emptyReason`. | `status`, `enabled`, `databasePath`, `totalOhlcvRows`, `totalFactorRows`, `symbolCount`, `minTradeDate`, `maxTradeDate`, `latestFactorDate`, `symbols`, `emptyReason` |
| `POST /api/v1/quant/duckdb/benchmark` | Run a bounded read-only query over `factor_daily`. | Read-only after connecting to an enabled DuckDB database. | Returns `status=disabled`, empty counts, and no top results. | `durationMs`, `rowsScanned`, `symbolsScanned`, `queryType`, `dataMode`, `startDate`, `endDate`, `topResults` |
| `POST /api/v1/quant/duckdb/factor-snapshot` | Return read-only factor rows for requested symbols/date windows. | Never writes; reads existing `factor_daily` only. | Returns `status=disabled`, `dataMode=disabled`, no rows, and no DB file. | `status`, `dataMode`, `coverage`, `rowCount`, `factorDates`, `missingSymbols`, `snapshots`, `durationMs` |
| `POST /api/v1/quant/duckdb/validate-factor-path` | Validate factor coverage for scanner/backtest-like symbol sets. | Never writes; reads existing `factor_daily` only. | Returns disabled coverage diagnostics and no DB file. | `status`, `dataMode`, `coverage`, `rowCount`, `factorDates`, `missingSymbols`, `insufficientSymbols`, `durationMs` |
| `POST /api/v1/quant/duckdb/compare-runtime-context` | Compare caller-provided scanner/backtest context against factor coverage. | Never writes; diagnostics only. | Returns disabled diagnostics with `productionRuntimeChanged=false`. | `status`, `dataMode`, `runtimeContexts`, `coverage`, `diagnostics`, `snapshots`, `durationMs` |

## Disabled No-Write Smoke Check

Use a path that should not exist before the check. Replace the backend startup command and auth placeholder with the local method for this checkout.

```bash
cd /Users/yehengli/daily_stock_analysis

export API_BASE="http://127.0.0.1:8000"
export AUTH_HEADER="Authorization: Bearer <local-admin-token-if-required>"
export DUCKDB_DATABASE_PATH="/tmp/wolfystock-disabled-smoke.duckdb"
export QUANT_DUCKDB_ENABLED=false

rm -f "$DUCKDB_DATABASE_PATH" "$DUCKDB_DATABASE_PATH.wal"

# Start the backend in another terminal with the same explicit env.
# Example placeholder only:
# QUANT_DUCKDB_ENABLED=false DUCKDB_DATABASE_PATH="$DUCKDB_DATABASE_PATH" python3 main.py --serve

curl -sS -H "$AUTH_HEADER" "$API_BASE/api/v1/quant/duckdb/health"

curl -sS -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{}' \
  "$API_BASE/api/v1/quant/duckdb/init"

curl -sS -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"source":"payload","rows":[{"symbol":"SMOKE","tradeDate":"2026-01-01","open":10,"high":11,"low":9,"close":10.5,"volume":1000}]}' \
  "$API_BASE/api/v1/quant/duckdb/ingest-ohlcv"

curl -sS -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"symbols":["SMOKE"]}' \
  "$API_BASE/api/v1/quant/duckdb/build-factors"

curl -sS -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"symbolLimit":1}' \
  "$API_BASE/api/v1/quant/duckdb/benchmark"

curl -sS -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"symbols":["SMOKE"],"asOfDate":"2026-01-05","lookbackDays":2}' \
  "$API_BASE/api/v1/quant/duckdb/factor-snapshot"

curl -sS -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"symbols":["SMOKE"],"startDate":"2026-01-01","endDate":"2026-01-05"}' \
  "$API_BASE/api/v1/quant/duckdb/validate-factor-path"

test ! -e "$DUCKDB_DATABASE_PATH"
test ! -e "$DUCKDB_DATABASE_PATH.wal"
find /tmp -maxdepth 1 \( -name 'wolfystock-disabled-smoke.duckdb' -o -name 'wolfystock-disabled-smoke.duckdb.wal' \) -print
```

Expected result: health reports disabled, write endpoints return disabled status, benchmark returns disabled/empty counts, and no DuckDB file appears.

Do not send `{"allowWhenDisabled": true}` during this check. That flag exists only for deliberate operator override and can initialize a DB while disabled.

## Enabled Temp DB Smoke Check

Use a temp DB path and explicit opt-in. This flow writes only to `/tmp/wolfystock-smoke.duckdb` and does not touch PostgreSQL business data.

```bash
cd /Users/yehengli/daily_stock_analysis

export API_BASE="http://127.0.0.1:8000"
export AUTH_HEADER="Authorization: Bearer <local-admin-token-if-required>"
export DUCKDB_DATABASE_PATH="/tmp/wolfystock-smoke.duckdb"
export QUANT_DUCKDB_ENABLED=true
export QUANT_ENGINE=python
export QUANT_MAX_BENCHMARK_SYMBOLS=5

rm -f "$DUCKDB_DATABASE_PATH" "$DUCKDB_DATABASE_PATH.wal"

# Start the backend in another terminal with the same explicit env.
# Example placeholder only:
# QUANT_DUCKDB_ENABLED=true DUCKDB_DATABASE_PATH="$DUCKDB_DATABASE_PATH" QUANT_MAX_BENCHMARK_SYMBOLS=5 python3 main.py --serve

curl -sS -H "$AUTH_HEADER" "$API_BASE/api/v1/quant/duckdb/health"

curl -sS -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{}' \
  "$API_BASE/api/v1/quant/duckdb/init"
```

Payload ingest is the smallest deterministic smoke path:

```bash
curl -sS -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "payload",
    "rows": [
      {"symbol":"SMOKE","tradeDate":"2026-01-01","open":10,"high":11,"low":9,"close":10.0,"volume":1000,"source":"operator_smoke"},
      {"symbol":"SMOKE","tradeDate":"2026-01-02","open":10,"high":12,"low":9,"close":11.0,"volume":1200,"source":"operator_smoke"},
      {"symbol":"SMOKE","tradeDate":"2026-01-03","open":11,"high":13,"low":10,"close":12.0,"volume":1300,"source":"operator_smoke"},
      {"symbol":"SMOKE","tradeDate":"2026-01-04","open":12,"high":14,"low":11,"close":13.0,"volume":1400,"source":"operator_smoke"},
      {"symbol":"SMOKE","tradeDate":"2026-01-05","open":13,"high":15,"low":12,"close":14.0,"volume":1500,"source":"operator_smoke"}
    ]
  }' \
  "$API_BASE/api/v1/quant/duckdb/ingest-ohlcv"
```

Payload ingest is capped at 5,000 rows per request for local-RC safety. Larger payloads return `status=invalid_request` and do not ingest rows; use explicit symbol/date bounds or split manual smoke payloads if you need more coverage.

Existing local `StockDaily` ingest is also supported. Keep it bounded:

```bash
curl -sS -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"source":"existing_store","symbols":["AAPL","MSFT"],"startDate":"2025-01-01","endDate":"2025-12-31","maxSymbols":2,"dryRun":true}' \
  "$API_BASE/api/v1/quant/duckdb/ingest-ohlcv"

curl -sS -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"source":"existing_store","symbols":["AAPL","MSFT"],"startDate":"2025-01-01","endDate":"2025-12-31","maxSymbols":2,"dryRun":false}' \
  "$API_BASE/api/v1/quant/duckdb/ingest-ohlcv"
```

Build factors, inspect coverage, run a bounded benchmark, then clean up:

```bash
curl -sS -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"symbols":["SMOKE"],"startDate":"2026-01-01","endDate":"2026-01-05"}' \
  "$API_BASE/api/v1/quant/duckdb/build-factors"

curl -sS -H "$AUTH_HEADER" "$API_BASE/api/v1/quant/duckdb/coverage"

curl -sS -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"symbolLimit":1,"startDate":"2026-01-01","endDate":"2026-01-05"}' \
  "$API_BASE/api/v1/quant/duckdb/benchmark"

curl -sS -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"symbols":["SMOKE","MISSING"],"asOfDate":"2026-01-05","lookbackDays":3,"factors":["return_1d","factor_score"]}' \
  "$API_BASE/api/v1/quant/duckdb/factor-snapshot"

curl -sS -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"symbols":["SMOKE","MISSING"],"startDate":"2026-01-01","endDate":"2026-01-05","minFactorRows":3}' \
  "$API_BASE/api/v1/quant/duckdb/validate-factor-path"

curl -sS -X POST -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"symbols":["SMOKE"],"scannerSnapshot":{"SMOKE":{"score":80}},"dateRange":{"startDate":"2026-01-01","endDate":"2026-01-05"}}' \
  "$API_BASE/api/v1/quant/duckdb/compare-runtime-context"

rm -f /tmp/wolfystock-smoke.duckdb /tmp/wolfystock-smoke.duckdb.wal
```

## Expected Response Shape

Coverage:

- `enabled` and `status`
- sanitized `databasePath`
- `totalOhlcvRows`
- `totalFactorRows`
- `symbolCount`
- `minTradeDate` and `maxTradeDate`
- `latestFactorDate`
- `symbols` per-symbol sample with row counts and date ranges
- `emptyReason` when no rows are available or the engine is disabled/unavailable

Benchmark:

- `durationMs` and `elapsedMs`
- `rowsScanned`
- `symbolsScanned`
- `queryType`
- `dataMode`
- `startDate` and `endDate`
- `topResults`

Phase 2 factor validation:

- `dataMode` is `real`, `empty`, `disabled`, or `unavailable`.
- `coverage` contains requested/covered/missing symbol counts, row count, and factor date bounds.
- `missingSymbols` and `insufficientSymbols` are explicit diagnostics.
- `snapshots` include diagnostic factor values and labels such as `factorTrend`, `factorMomentum`, `factorDataMode`, and `factorWarnings`.
- `compare-runtime-context` returns `diagnostics.productionRuntimeChanged=false`; scanner and backtest runtime outputs are not changed.

## Factor Definitions

Phase 1.5 factor rows include:

- `return_1d`
- `log_return_1d`
- `ma5`
- `ma10`
- `ma20`
- `ma60`
- `volume_ma20`
- `volatility_20d`
- `momentum_20d`
- `close_vs_ma20`
- `factor_score`
- `built_at`

These are validation and benchmark factors, not production trading signals.

## Troubleshooting

- DuckDB disabled: confirm `QUANT_DUCKDB_ENABLED=true` is exported in the same process that starts the backend.
- Missing local DB file: enabled read diagnostics report empty/missing state and should not create the DuckDB file. Run explicit init before ingest/build experiments.
- Corrupt, unreadable, permission-denied, or schema-mismatched local DB: diagnostics return sanitized unavailable reason codes such as `corrupt_or_unreadable`, `permission_denied`, or `schema_mismatch`. Move the file aside and rerun with an explicit temp path for local smoke.
- Concurrent operator actions: Run only one DuckDB init/ingest/build action at a time during local smoke. There is still no production single-flight or job-queue guard, so concurrent write behavior remains a production-readiness blocker.
- Factor snapshot is empty: initialize the schema, ingest OHLCV rows, build factors, and check that requested symbols/date windows match `factor_daily`.
- Factor validation is insufficient: inspect `missingSymbols`, `insufficientSymbols`, and `coverage` before comparing scanner/backtest snapshots.
- `duckdb` Python dependency missing: health returns `status=unavailable`; install the project dependencies for the local environment before enabling the smoke path.
- No OHLCV rows: initialize the schema, then run payload ingest or bounded existing-store ingest.
- No factor rows: run `build-factors` after OHLCV ingest; an empty OHLCV table produces `status=empty`.
- Benchmark returns empty or fallback-like output: factor rows are missing, date bounds exclude all rows, or `symbolLimit` selects no symbols.
- Local data store has no symbols: use payload ingest for a deterministic smoke, or provide explicit known local symbols.
- Generated DB path is not ignored: `.gitignore` should ignore `*.duckdb`, `*.duckdb.wal`, and `*.parquet`; verify before staging.
- Permission issue writing temp DB: use a writable local path such as `/tmp/wolfystock-smoke.duckdb`.
- Endpoint unauthorized or admin auth required: authenticate as a local admin and include the local admin session/cookie/header.
- Provider or network data is not required for tests: payload ingest and unit/API tests use local deterministic data.

## Cleanup

```bash
rm -f /tmp/wolfystock-smoke.duckdb /tmp/wolfystock-smoke.duckdb.wal
git status --short
git diff --cached --name-only
```

Confirm no generated `*.duckdb`, `*.duckdb.wal`, or Parquet files are staged.

## Verification Commands

Safe focused regressions:

```bash
python3 -m pytest tests/test_quant_duckdb_service.py tests/api/test_quant_duckdb.py -q
python3 -m pytest tests/test_portfolio_service.py tests/test_backtest* -q
```

The quant tests validate DuckDB service/API behavior, including disabled no-write behavior. The portfolio and backtest regressions confirm runtime paths remain unchanged.

## What This Does Not Do

- Does not replace PostgreSQL.
- Does not enable `pg_duckdb`.
- Does not alter scanner or backtest runtime results.
- Does not change portfolio accounting.
- Does not create production trading signals.
- Does not silently use `factor_score` for production scanner ranking, backtest signals, AI decisions, or notifications.
- Does not implement Parquet import/export yet.
- Does not require full-market ingest.
