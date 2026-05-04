# DuckDB Quant Engine

WolfyStock keeps PostgreSQL as the business database for users, portfolio accounting, watchlists, admin logs, settings, analysis tasks, and backtest metadata. DuckDB is an optional quant analytics accelerator for factor validation, coverage checks, research queries, and benchmark scans.

For safe local operator validation, see [DuckDB Operator Smoke Guide](operations/duckdb-operator-smoke-guide.md).

DuckDB remains standalone:

- it does not replace PostgreSQL
- it does not use `pg_duckdb`
- it does not require any PostgreSQL extension
- it does not replace the existing Python backtest engine
- it does not change scanner selection logic
- it does not change backtest calculations
- it does not change Portfolio accounting
- it does not change AI decision logic or notification routing

## Configuration

DuckDB is disabled by default.

```env
QUANT_ENGINE=python
QUANT_DUCKDB_ENABLED=false
DUCKDB_DATABASE_PATH=data/quant/wolfystock.duckdb
QUANT_PARQUET_ROOT=data/quant/parquet
QUANT_MAX_BENCHMARK_SYMBOLS=5000
```

Enable local experimentation explicitly:

```env
QUANT_DUCKDB_ENABLED=true
DUCKDB_DATABASE_PATH=data/quant/wolfystock.duckdb
```

The DuckDB dependency is imported lazily by `QuantDuckDBService`. Disabled health checks do not create or write the DuckDB file. Only explicit DuckDB service/API calls such as init, ingest, factor build, coverage, or benchmark may touch the DuckDB database.

## Phase 1.5 Scope

Phase 1.5 adds a safe validation layer on top of the Phase 1 skeleton:

- explicit OHLCV ingest into `ohlcv_daily`
- optional bounded ingest from existing local `StockDaily` storage
- basic daily factor build into `factor_daily`
- row/symbol/date coverage reporting
- richer factor benchmark metadata and top-result samples

This is still not production strategy signal integration. Scanner, backtest, portfolio, AI, notification, and frontend runtime paths do not consume DuckDB data.

## Service

The service lives at:

```text
src/services/quant_analytics/duckdb_service.py
```

Explicit service calls:

- `health()`
- `init_database()` / `initialize_schema()`
- `ingest_ohlcv(rows)` / `ingest_ohlcv_rows(rows)`
- `ingest_ohlcv_from_existing_store(symbols=None, start_date=None, end_date=None, max_symbols=None, dry_run=False)`
- `build_basic_factors(symbols=None, start_date=None, end_date=None)`
- `get_coverage(sample_limit=20)`
- `benchmark_factor_query(symbol_limit=None, start_date=None, end_date=None)`
- `query_signal_candidates(as_of_date=None, limit=100)`

The existing-store ingest reads local `StockDaily` rows through `StockRepository`. It is capped by `QUANT_MAX_BENCHMARK_SYMBOLS`, supports explicit symbol/date bounds, and does not add a new market-data dependency or trigger network downloads.

## Tables

`ohlcv_daily` stores normalized daily bars:

- `symbol`
- `trade_date`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `amount`
- `adj_close`
- `market`
- `sector`
- `source`
- `ingested_at`
- `updated_at`

`factor_daily` stores conservative benchmark factors:

- `symbol`
- `trade_date`
- `close`
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
- `updated_at`

Both tables use `(symbol, trade_date)` uniqueness. Ingest and factor builds use delete-and-reinsert for the affected symbol/date rows so repeated runs do not double-count data.

## Admin API

Admin-only endpoints:

```text
GET  /api/v1/quant/duckdb/health
POST /api/v1/quant/duckdb/init
POST /api/v1/quant/duckdb/ingest-ohlcv
POST /api/v1/quant/duckdb/build-factors
GET  /api/v1/quant/duckdb/coverage
POST /api/v1/quant/duckdb/benchmark
```

Example payload ingest:

```json
{
  "source": "payload",
  "rows": [
    {
      "symbol": "AAPL",
      "tradeDate": "2026-01-02",
      "open": 100.0,
      "high": 102.0,
      "low": 99.0,
      "close": 101.5,
      "volume": 1200000,
      "source": "manual_validation"
    }
  ]
}
```

Example bounded existing-store ingest:

```json
{
  "source": "existing_store",
  "symbols": ["AAPL", "MSFT"],
  "startDate": "2025-01-01",
  "endDate": "2025-12-31",
  "maxSymbols": 2,
  "dryRun": false
}
```

Factor build:

```json
{
  "symbols": ["AAPL", "MSFT"],
  "startDate": "2025-01-01",
  "endDate": "2025-12-31"
}
```

Coverage returns:

- enabled/status metadata
- sanitized database path
- total OHLCV rows
- total factor rows
- symbol count
- min/max OHLCV trade date
- latest factor date
- bounded per-symbol row/date coverage
- clear empty or disabled reason

Benchmark returns:

- `durationMs` / `elapsedMs`
- `symbolsScanned`
- `rowsScanned`
- `queryType`
- `dataMode` (`real`, `empty`, or disabled/unavailable status)
- date range
- top result sample

## Parquet

`QUANT_PARQUET_ROOT` is still reserved for future explicit snapshot import/export. Phase 1.5 does not add Parquet export/import because the core validation path is OHLCV ingest, factor build, coverage reporting, and benchmark validation.

## Cleanup And Rollback

To roll back a local experiment, disable the engine and remove the generated local database:

```bash
rm -f data/quant/wolfystock.duckdb
```

Do not commit generated `.duckdb`, Parquet, log, coverage, screenshot, or test-result artifacts.
