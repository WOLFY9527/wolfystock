# DuckDB Quant Engine Phase 1

WolfyStock keeps PostgreSQL as the business database for users, portfolio accounting, watchlists, admin logs, settings, analysis tasks, and backtest metadata. DuckDB is an optional quant analytics accelerator for future factor computation, signal precomputation, research queries, and benchmark scans.

Phase 1 is intentionally standalone:

- it does not replace PostgreSQL
- it does not replace the existing Python backtest engine
- it does not change scanner selection logic
- it does not change existing backtest calculations
- it does not change Portfolio accounting
- it does not use `pg_duckdb` or require PostgreSQL extensions

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

The DuckDB dependency is imported lazily by `QuantDuckDBService`. If `duckdb` is not installed, health and benchmark calls return an unavailable status instead of breaking app startup.

## Service

The service lives at:

```text
src/services/quant_analytics/duckdb_service.py
```

It supports explicit calls to:

- `health()`
- `initialize_schema()`
- `ingest_ohlcv_rows(rows)`
- `build_basic_factors(start_date=None, end_date=None)`
- `benchmark_factor_query(symbol_limit=None, start_date=None, end_date=None)`
- `query_signal_candidates(as_of_date=None, limit=100)`

Tables created by `initialize_schema()`:

- `ohlcv_daily`
- `factor_daily`

The current factor math is a benchmark skeleton only: MA5, MA20, MA60, 20/60-day momentum, 20-row volatility, 20-row dollar volume, and a placeholder `factor_score = momentum20 - vol20`. It is not a production strategy signal.

## Admin API

Admin-only endpoints:

```text
GET  /api/v1/quant/duckdb/health
POST /api/v1/quant/duckdb/init
POST /api/v1/quant/duckdb/benchmark
```

`health` returns safe status metadata and does not create a database file while the service is disabled.

`init` creates the DuckDB schema only when explicitly invoked. If the service is disabled, it returns `disabled` unless the request includes:

```json
{"allowWhenDisabled": true}
```

`benchmark` reads already-built `factor_daily` rows and returns elapsed time and row/symbol/date counts. With no data, disabled config, or unavailable DuckDB, it returns a clear non-crashing status.

## Limitations

- no production signal integration
- no scanner or backtest consumption
- no Portfolio accounting integration
- no `pg_duckdb`
- no PostgreSQL extension requirement
- no Parquet ingest path beyond the reserved config root
- no app startup dependency on DuckDB
