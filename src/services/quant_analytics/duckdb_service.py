# -*- coding: utf-8 -*-
"""Optional, explicitly invoked DuckDB quant analytics accelerator."""

from __future__ import annotations

import importlib
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from src.config import Config, get_config
from src.repositories.stock_repo import StockRepository

logger = logging.getLogger(__name__)


class QuantDuckDBService:
    """Small DuckDB service for bounded quant data validation and benchmarks."""

    DEFAULT_RECENT_ROW_LIMIT = 252
    FACTOR_COLUMNS = (
        "return_1d",
        "log_return_1d",
        "ma5",
        "ma10",
        "ma20",
        "ma60",
        "volume_ma20",
        "volatility_20d",
        "momentum_20d",
        "close_vs_ma20",
        "factor_score",
    )
    FACTOR_COUNT = len(FACTOR_COLUMNS)

    def __init__(
        self,
        database_path: str | None = None,
        enabled: bool = False,
        parquet_root: str | None = None,
        *,
        max_benchmark_symbols: int = 5000,
    ):
        self.database_path = str(database_path or "data/quant/wolfystock.duckdb")
        self.enabled = bool(enabled)
        self.parquet_root = str(parquet_root or "data/quant/parquet")
        self.max_benchmark_symbols = max(1, int(max_benchmark_symbols or 5000))

    @classmethod
    def from_config(cls, config: Optional[Config] = None) -> "QuantDuckDBService":
        cfg = config or get_config()
        return cls(
            database_path=getattr(cfg, "duckdb_database_path", "data/quant/wolfystock.duckdb"),
            enabled=bool(getattr(cfg, "quant_duckdb_enabled", False)),
            parquet_root=getattr(cfg, "quant_parquet_root", "data/quant/parquet"),
            max_benchmark_symbols=int(getattr(cfg, "quant_max_benchmark_symbols", 5000) or 5000),
        )

    def health(self) -> dict:
        payload = {
            "enabled": self.enabled,
            "available": False,
            "databasePath": self._safe_path(self.database_path),
            "parquetRoot": self._safe_path(self.parquet_root),
            "version": None,
            "error": "DuckDB quant engine is disabled" if not self.enabled else None,
            "schemaInitialized": False,
            "status": "disabled" if not self.enabled else "ok",
            "engine": "duckdb",
        }
        if not self.enabled:
            return payload

        available, version, error = self._duckdb_status()
        payload["available"] = available
        payload["version"] = version
        payload["error"] = error
        if not available:
            payload["status"] = "unavailable"
            return payload

        try:
            with self._connect() as conn:
                payload["schemaInitialized"] = self._schema_initialized(conn)
        except Exception as exc:
            payload["status"] = "unavailable"
            payload["error"] = str(exc)
        return payload

    def init_database(self, *, force: bool = False) -> dict:
        return self.initialize_schema(force=force)

    def initialize_schema(self, *, force: bool = False) -> dict:
        disabled = self._disabled_result()
        if disabled and not force:
            return disabled
        available, version, error = self._duckdb_status()
        if not available:
            return self._unavailable_result(error)

        with self._connect(create_parent=True) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ohlcv_daily(
                  symbol TEXT NOT NULL,
                  trade_date DATE NOT NULL,
                  open DOUBLE,
                  high DOUBLE,
                  low DOUBLE,
                  close DOUBLE,
                  volume DOUBLE,
                  amount DOUBLE,
                  adj_close DOUBLE,
                  market TEXT,
                  sector TEXT,
                  source TEXT,
                  ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP,
                  PRIMARY KEY(symbol, trade_date)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS factor_daily(
                  symbol TEXT NOT NULL,
                  trade_date DATE NOT NULL,
                  close DOUBLE,
                  return_1d DOUBLE,
                  log_return_1d DOUBLE,
                  ma5 DOUBLE,
                  ma10 DOUBLE,
                  ma20 DOUBLE,
                  ma60 DOUBLE,
                  volume_ma20 DOUBLE,
                  volatility_20d DOUBLE,
                  momentum_20d DOUBLE,
                  close_vs_ma20 DOUBLE,
                  factor_score DOUBLE,
                  built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP,
                  PRIMARY KEY(symbol, trade_date)
                )
                """
            )
            for table_name, column_name, column_type in (
                ("ohlcv_daily", "adj_close", "DOUBLE"),
                ("ohlcv_daily", "ingested_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ("factor_daily", "return_1d", "DOUBLE"),
                ("factor_daily", "log_return_1d", "DOUBLE"),
                ("factor_daily", "ma10", "DOUBLE"),
                ("factor_daily", "volume_ma20", "DOUBLE"),
                ("factor_daily", "volatility_20d", "DOUBLE"),
                ("factor_daily", "momentum_20d", "DOUBLE"),
                ("factor_daily", "close_vs_ma20", "DOUBLE"),
                ("factor_daily", "built_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ):
                self._ensure_column(conn, table_name, column_name, column_type)
        return {"status": "ok", "engine": "duckdb", "version": version, "schemaInitialized": True}

    def ingest_ohlcv(self, rows: Any) -> dict:
        return self.ingest_ohlcv_rows(rows)

    def ingest_ohlcv_rows(self, rows: Any) -> dict:
        disabled = self._disabled_result()
        if disabled:
            return disabled
        available, _version, error = self._duckdb_status()
        if not available:
            return self._unavailable_result(error)

        records = self._records_from_rows(rows)
        if not records:
            return {"status": "empty", "engine": "duckdb", "ingestedRows": 0, "symbolCount": 0, "durationMs": 0.0}

        started = time.perf_counter()
        parsed_rows = [self._normalize_ohlcv_row(row) for row in records]
        logger.info(
            "DuckDBIngestStarted symbols_count=%s rows=%s source=%s",
            len({row[0] for row in parsed_rows}),
            len(parsed_rows),
            self._compact_source(records),
        )
        with self._connect(create_parent=True) as conn:
            if not self._schema_initialized(conn):
                return self._schema_missing_result()
            conn.execute("BEGIN TRANSACTION")
            try:
                conn.executemany(
                    "DELETE FROM ohlcv_daily WHERE symbol = ? AND trade_date = ?",
                    [(row[0], row[1]) for row in parsed_rows],
                )
                conn.executemany(
                    """
                    INSERT INTO ohlcv_daily (
                        symbol, trade_date, open, high, low, close, volume, amount,
                        adj_close, market, sector, source, ingested_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    parsed_rows,
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                logger.exception("DuckDBIngestFailed rows=%s", len(parsed_rows))
                raise

        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        logger.info(
            "DuckDBIngestCompleted symbols_count=%s rows_ingested=%s duration_ms=%s",
            len({row[0] for row in parsed_rows}),
            len(parsed_rows),
            duration_ms,
        )
        return {
            "status": "ok",
            "engine": "duckdb",
            "ingestedRows": len(parsed_rows),
            "symbolCount": len({row[0] for row in parsed_rows}),
            "durationMs": duration_ms,
        }

    def ingest_ohlcv_from_existing_store(
        self,
        *,
        symbols: Optional[list[str]] = None,
        start_date: Any = None,
        end_date: Any = None,
        max_symbols: Any = None,
        dry_run: bool = False,
        stock_repository: Any = None,
    ) -> dict:
        disabled = self._disabled_result()
        if disabled:
            return {**disabled, "ingestedRows": 0, "symbolCount": 0, "availableRows": 0}
        start = self._parse_optional_date(start_date)
        end = self._parse_optional_date(end_date)
        if start and end and start > end:
            return self._invalid_range_result(ingest=True)

        repo = stock_repository or StockRepository()
        selected_symbols = self._normalize_symbols(symbols)
        if not selected_symbols:
            selected_symbols = self._normalize_symbols(repo.list_distinct_codes())
        selected_symbols = selected_symbols[: self._normalize_symbol_limit(max_symbols)]
        if not selected_symbols:
            return {
                "status": "empty",
                "engine": "duckdb",
                "source": "existing_store",
                "ingestedRows": 0,
                "symbolCount": 0,
                "availableRows": 0,
            }

        rows: list[dict] = []
        for symbol in selected_symbols:
            if start is not None and end is not None:
                source_rows = repo.get_range(symbol, start, end)
            else:
                source_rows = repo.get_recent_daily_rows(code=symbol, limit=self.DEFAULT_RECENT_ROW_LIMIT)
            for source_row in source_rows:
                record = self._ohlcv_record_from_stock_daily(source_row, fallback_symbol=symbol)
                if start is not None and record["trade_date"] < start:
                    continue
                if end is not None and record["trade_date"] > end:
                    continue
                rows.append(record)

        base_payload = {
            "engine": "duckdb",
            "source": "existing_store",
            "ingestedRows": 0,
            "symbolCount": len(selected_symbols),
            "availableRows": len(rows),
            "symbolsRequested": len(selected_symbols),
            "startDate": self._date_to_iso(start),
            "endDate": self._date_to_iso(end),
        }
        if dry_run:
            return {**base_payload, "status": "dry_run"}
        if not rows:
            return {**base_payload, "status": "empty"}
        result = self.ingest_ohlcv(rows)
        return {**base_payload, **result, "source": "existing_store", "availableRows": len(rows)}

    def build_basic_factors(
        self,
        start_date: Any = None,
        end_date: Any = None,
        symbols: Optional[list[str]] = None,
    ) -> dict:
        disabled = self._disabled_result()
        if disabled:
            return disabled
        available, _version, error = self._duckdb_status()
        if not available:
            return self._unavailable_result(error)

        start = self._parse_optional_date(start_date)
        end = self._parse_optional_date(end_date)
        if start and end and start > end:
            return self._invalid_range_result()
        normalized_symbols = self._normalize_symbols(symbols)
        where_sql, params = self._scope_filter_sql("trade_date", start, end, normalized_symbols)
        started = time.perf_counter()
        logger.info(
            "DuckDBFactorBuildStarted symbols_count=%s start_date=%s end_date=%s",
            len(normalized_symbols),
            self._date_to_iso(start),
            self._date_to_iso(end),
        )
        with self._connect(create_parent=True) as conn:
            if not self._schema_initialized(conn):
                return self._schema_missing_result()
            ohlcv_rows = conn.execute(f"SELECT COUNT(*) FROM ohlcv_daily {where_sql}", params).fetchone()[0]
            if int(ohlcv_rows or 0) == 0:
                return {"status": "empty", "engine": "duckdb", "ohlcvRows": 0, "factorRows": 0, "factorCount": self.FACTOR_COUNT}

            conn.execute("BEGIN TRANSACTION")
            try:
                conn.execute(f"DELETE FROM factor_daily {where_sql}", params)
                conn.execute(
                    f"""
                    INSERT INTO factor_daily (
                        symbol, trade_date, close, return_1d, log_return_1d,
                        ma5, ma10, ma20, ma60, volume_ma20, volatility_20d,
                        momentum_20d, close_vs_ma20, factor_score, built_at, updated_at
                    )
                    WITH base AS (
                        SELECT
                            symbol,
                            trade_date,
                            close,
                            volume,
                            LAG(close) OVER (PARTITION BY symbol ORDER BY trade_date) AS prev_close,
                            close / NULLIF(LAG(close, 20) OVER (PARTITION BY symbol ORDER BY trade_date), 0) - 1 AS momentum_20d,
                            AVG(close) OVER (
                                PARTITION BY symbol ORDER BY trade_date
                                ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
                            ) AS ma5,
                            AVG(close) OVER (
                                PARTITION BY symbol ORDER BY trade_date
                                ROWS BETWEEN 9 PRECEDING AND CURRENT ROW
                            ) AS ma10,
                            AVG(close) OVER (
                                PARTITION BY symbol ORDER BY trade_date
                                ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                            ) AS ma20,
                            AVG(close) OVER (
                                PARTITION BY symbol ORDER BY trade_date
                                ROWS BETWEEN 59 PRECEDING AND CURRENT ROW
                            ) AS ma60,
                            AVG(volume) OVER (
                                PARTITION BY symbol ORDER BY trade_date
                                ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                            ) AS volume_ma20
                        FROM ohlcv_daily
                    ),
                    computed AS (
                        SELECT
                            *,
                            close / NULLIF(prev_close, 0) - 1 AS return_1d,
                            CASE
                                WHEN prev_close > 0 AND close > 0 THEN LN(close / prev_close)
                                ELSE NULL
                            END AS log_return_1d
                        FROM base
                    ),
                    windowed AS (
                        SELECT
                            *,
                            STDDEV_SAMP(return_1d) OVER (
                                PARTITION BY symbol ORDER BY trade_date
                                ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                            ) AS volatility_20d,
                            close / NULLIF(ma20, 0) - 1 AS close_vs_ma20
                        FROM computed
                    )
                    SELECT
                        symbol,
                        trade_date,
                        close,
                        return_1d,
                        log_return_1d,
                        ma5,
                        ma10,
                        ma20,
                        ma60,
                        volume_ma20,
                        volatility_20d,
                        momentum_20d,
                        close_vs_ma20,
                        COALESCE(momentum_20d, 0) + COALESCE(close_vs_ma20, 0) - COALESCE(volatility_20d, 0) AS factor_score,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    FROM windowed
                    {where_sql}
                    """,
                    params,
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                logger.exception("DuckDBFactorBuildFailed")
                raise

            factor_rows = conn.execute(f"SELECT COUNT(*) FROM factor_daily {where_sql}", params).fetchone()[0]
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        logger.info("DuckDBFactorBuildCompleted rows_built=%s duration_ms=%s", int(factor_rows or 0), duration_ms)
        return {
            "status": "ok",
            "engine": "duckdb",
            "ohlcvRows": int(ohlcv_rows or 0),
            "factorRows": int(factor_rows or 0),
            "factorCount": self.FACTOR_COUNT,
            "durationMs": duration_ms,
        }

    def get_coverage(self, *, sample_limit: int = 20) -> dict:
        disabled = self._disabled_result()
        if disabled:
            return self._empty_coverage("disabled", "DuckDB quant engine is disabled")
        available, _version, error = self._duckdb_status()
        if not available:
            return self._empty_coverage("unavailable", error or "DuckDB is unavailable")

        limit = max(1, min(int(sample_limit or 20), 100))
        with self._connect(create_parent=True) as conn:
            if not self._schema_initialized(conn):
                return self._empty_coverage("unavailable", "DuckDB quant schema is not initialized")
            totals = conn.execute(
                """
                SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date)
                FROM ohlcv_daily
                """
            ).fetchone()
            factor_totals = conn.execute("SELECT COUNT(*), MAX(trade_date) FROM factor_daily").fetchone()
            symbol_rows = conn.execute(
                """
                SELECT
                    o.symbol,
                    COUNT(*) AS ohlcv_rows,
                    MIN(o.trade_date) AS min_date,
                    MAX(o.trade_date) AS max_date,
                    COALESCE(f.factor_rows, 0) AS factor_rows,
                    f.latest_factor_date
                FROM ohlcv_daily o
                LEFT JOIN (
                    SELECT symbol, COUNT(*) AS factor_rows, MAX(trade_date) AS latest_factor_date
                    FROM factor_daily
                    GROUP BY symbol
                ) f ON f.symbol = o.symbol
                GROUP BY o.symbol, f.factor_rows, f.latest_factor_date
                ORDER BY o.symbol
                LIMIT ?
                """,
                [limit],
            ).fetchall()

        total_ohlcv = int(totals[0] or 0)
        total_factor = int(factor_totals[0] or 0)
        return {
            "status": "ok" if total_ohlcv or total_factor else "empty",
            "engine": "duckdb",
            "enabled": self.enabled,
            "databasePath": self._safe_path(self.database_path),
            "totalOhlcvRows": total_ohlcv,
            "totalFactorRows": total_factor,
            "symbolCount": int(totals[1] or 0),
            "minTradeDate": self._date_to_iso(totals[2]),
            "maxTradeDate": self._date_to_iso(totals[3]),
            "latestFactorDate": self._date_to_iso(factor_totals[1]),
            "symbols": [
                {
                    "symbol": row[0],
                    "ohlcvRows": int(row[1] or 0),
                    "minTradeDate": self._date_to_iso(row[2]),
                    "maxTradeDate": self._date_to_iso(row[3]),
                    "factorRows": int(row[4] or 0),
                    "latestFactorDate": self._date_to_iso(row[5]),
                }
                for row in symbol_rows
            ],
            "emptyReason": None if total_ohlcv or total_factor else "No OHLCV or factor rows have been ingested",
        }

    def benchmark_factor_query(self, symbol_limit: Any = None, start_date: Any = None, end_date: Any = None) -> dict:
        disabled = self._disabled_result()
        if disabled:
            return self._benchmark_disabled_result(disabled["status"])
        available, _version, error = self._duckdb_status()
        if not available:
            result = self._benchmark_disabled_result("unavailable")
            result["error"] = error
            return result

        limit = self._normalize_symbol_limit(symbol_limit)
        start = self._parse_optional_date(start_date)
        end = self._parse_optional_date(end_date)
        if start and end and start > end:
            result = self._benchmark_disabled_result("invalid_request")
            result["error"] = "start_date must be on or before end_date"
            return result
        where_sql, params = self._date_filter_sql("trade_date", start, end, prefix="WHERE")
        started = time.perf_counter()
        with self._connect(create_parent=True) as conn:
            if not self._schema_initialized(conn):
                result = self._benchmark_disabled_result("unavailable")
                result["error"] = "DuckDB quant schema is not initialized"
                return result
            row = conn.execute(
                f"""
                WITH selected_symbols AS (
                    SELECT symbol
                    FROM factor_daily
                    GROUP BY symbol
                    ORDER BY symbol
                    LIMIT ?
                ),
                scoped AS (
                    SELECT *
                    FROM factor_daily
                    WHERE symbol IN (SELECT symbol FROM selected_symbols)
                )
                SELECT
                    COUNT(*) AS factor_rows,
                    COUNT(DISTINCT symbol) AS symbol_count,
                    COUNT(DISTINCT trade_date) AS date_count,
                    AVG(factor_score) AS avg_factor_score,
                    MIN(trade_date) AS min_date,
                    MAX(trade_date) AS max_date
                FROM scoped
                {where_sql}
                """,
                [limit, *params],
            ).fetchone()
            top_rows = conn.execute(
                f"""
                WITH selected_symbols AS (
                    SELECT symbol
                    FROM factor_daily
                    GROUP BY symbol
                    ORDER BY symbol
                    LIMIT ?
                ),
                scoped AS (
                    SELECT *
                    FROM factor_daily
                    WHERE symbol IN (SELECT symbol FROM selected_symbols)
                )
                SELECT symbol, trade_date, close, return_1d, ma20, momentum_20d, volatility_20d, close_vs_ma20, factor_score
                FROM scoped
                {where_sql}
                ORDER BY factor_score DESC NULLS LAST, symbol, trade_date DESC
                LIMIT 5
                """,
                [limit, *params],
            ).fetchall()
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        factor_rows = int(row[0] or 0)
        if factor_rows == 0:
            return {
                "status": "empty",
                "engine": "duckdb",
                "elapsedMs": elapsed_ms,
                "durationMs": elapsed_ms,
                "ohlcvRows": 0,
                "factorRows": 0,
                "rowsScanned": 0,
                "symbolsScanned": 0,
                "symbolCount": 0,
                "dateCount": 0,
                "factorCount": self.FACTOR_COUNT,
                "queryType": "factor_daily_top_scores",
                "dataMode": "empty",
                "startDate": self._date_to_iso(start),
                "endDate": self._date_to_iso(end),
                "topResults": [],
            }
        symbols_scanned = int(row[1] or 0)
        return {
            "status": "ok",
            "engine": "duckdb",
            "elapsedMs": elapsed_ms,
            "durationMs": elapsed_ms,
            "ohlcvRows": self._count_ohlcv_rows(start, end, limit),
            "factorRows": factor_rows,
            "rowsScanned": factor_rows,
            "symbolsScanned": symbols_scanned,
            "symbolCount": symbols_scanned,
            "dateCount": int(row[2] or 0),
            "factorCount": self.FACTOR_COUNT,
            "queryType": "factor_daily_top_scores",
            "dataMode": "real",
            "startDate": self._date_to_iso(start or row[4]),
            "endDate": self._date_to_iso(end or row[5]),
            "topResults": [
                {
                    "symbol": top[0],
                    "tradeDate": self._date_to_iso(top[1]),
                    "close": top[2],
                    "return1d": top[3],
                    "ma20": top[4],
                    "momentum20d": top[5],
                    "volatility20d": top[6],
                    "closeVsMa20": top[7],
                    "factorScore": top[8],
                }
                for top in top_rows
            ],
        }

    def get_factor_snapshot(
        self,
        symbols: Optional[list[str]],
        as_of_date: Any = None,
        lookback_days: Any = None,
        factors: Optional[list[str]] = None,
    ) -> dict:
        requested_symbols = self._normalize_symbols(symbols)[: self.max_benchmark_symbols]
        disabled = self._disabled_result()
        if disabled:
            return self._empty_factor_snapshot(
                "disabled",
                requested_symbols,
                "DuckDB quant engine is disabled",
                data_mode="disabled",
            )
        if not requested_symbols:
            return self._empty_factor_snapshot("invalid_request", [], "symbols are required", data_mode="empty")
        available, _version, error = self._duckdb_status()
        if not available:
            return self._empty_factor_snapshot("unavailable", requested_symbols, error or "DuckDB is unavailable", data_mode="unavailable")
        if not self._database_exists():
            return self._empty_factor_snapshot("empty", requested_symbols, "DuckDB database does not exist", data_mode="empty")

        selected_factors = self._normalize_factor_columns(factors)
        as_of = self._parse_optional_date(as_of_date)
        lookback = self._normalize_lookback_days(lookback_days)
        started = time.perf_counter()
        with self._connect() as conn:
            if not self._schema_initialized(conn):
                return self._empty_factor_snapshot(
                    "unavailable",
                    requested_symbols,
                    "DuckDB quant schema is not initialized",
                    data_mode="unavailable",
                )
            if as_of is None:
                row = conn.execute(
                    "SELECT MAX(trade_date) FROM factor_daily WHERE symbol IN (" + ", ".join(["?"] * len(requested_symbols)) + ")",
                    requested_symbols,
                ).fetchone()
                as_of = row[0] if row else None
            if as_of is None:
                return self._empty_factor_snapshot("empty", requested_symbols, "No factor rows are available", data_mode="empty")
            start = as_of - timedelta(days=lookback - 1) if lookback else None
            date_clauses = ["trade_date <= ?"]
            params: list[Any] = [as_of]
            if start is not None:
                date_clauses.append("trade_date >= ?")
                params.append(start)
            symbol_sql = ", ".join(["?"] * len(requested_symbols))
            select_columns = ", ".join(selected_factors)
            rows = conn.execute(
                f"""
                SELECT symbol, trade_date, {select_columns}
                FROM factor_daily
                WHERE symbol IN ({symbol_sql}) AND {" AND ".join(date_clauses)}
                ORDER BY symbol, trade_date
                """,
                [*requested_symbols, *params],
            ).fetchall()

        return self._factor_snapshot_from_rows(
            rows,
            requested_symbols=requested_symbols,
            factors=selected_factors,
            started=started,
        )

    def validate_factor_coverage(
        self,
        symbols: Optional[list[str]],
        start_date: Any = None,
        end_date: Any = None,
        min_factor_rows: Any = None,
    ) -> dict:
        requested_symbols = self._normalize_symbols(symbols)[: self.max_benchmark_symbols]
        disabled = self._disabled_result()
        if disabled:
            return self._empty_factor_validation(
                "disabled",
                requested_symbols,
                "DuckDB quant engine is disabled",
                data_mode="disabled",
            )
        if not requested_symbols:
            return self._empty_factor_validation("invalid_request", [], "symbols are required", data_mode="empty")
        available, _version, error = self._duckdb_status()
        if not available:
            return self._empty_factor_validation("unavailable", requested_symbols, error or "DuckDB is unavailable", data_mode="unavailable")

        start = self._parse_optional_date(start_date)
        end = self._parse_optional_date(end_date)
        if start and end and start > end:
            return self._empty_factor_validation("invalid_request", requested_symbols, "start_date must be on or before end_date")
        if not self._database_exists():
            return self._empty_factor_validation("empty", requested_symbols, "DuckDB database does not exist", data_mode="empty")

        min_rows = max(1, int(min_factor_rows or 1))
        where_sql, params = self._scope_filter_sql("trade_date", start, end, requested_symbols)
        started = time.perf_counter()
        with self._connect() as conn:
            if not self._schema_initialized(conn):
                return self._empty_factor_validation(
                    "unavailable",
                    requested_symbols,
                    "DuckDB quant schema is not initialized",
                    data_mode="unavailable",
                )
            rows = conn.execute(
                f"""
                SELECT symbol, COUNT(*) AS factor_rows, MIN(trade_date), MAX(trade_date)
                FROM factor_daily
                {where_sql}
                GROUP BY symbol
                ORDER BY symbol
                """,
                params,
            ).fetchall()
        return self._factor_validation_from_rows(
            rows,
            requested_symbols=requested_symbols,
            min_factor_rows=min_rows,
            started=started,
        )

    def compare_factor_context(
        self,
        symbols: Optional[list[str]],
        scanner_snapshot: Optional[dict[str, Any]] = None,
        backtest_snapshot: Optional[dict[str, Any]] = None,
        date_range: Optional[dict[str, Any]] = None,
    ) -> dict:
        started = time.perf_counter()
        range_payload = dict(date_range or {})
        start = range_payload.get("startDate") or range_payload.get("start_date")
        end = range_payload.get("endDate") or range_payload.get("end_date")
        coverage = self.validate_factor_coverage(symbols=symbols, start_date=start, end_date=end)
        snapshot = self.get_factor_snapshot(symbols=symbols, as_of_date=end, lookback_days=5)
        runtime_contexts = []
        if scanner_snapshot:
            runtime_contexts.append("scanner")
        if backtest_snapshot:
            runtime_contexts.append("backtest")

        status = coverage.get("status", "empty")
        data_mode = coverage.get("dataMode", "empty")
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            "status": status,
            "engine": "duckdb",
            "dataMode": data_mode,
            "durationMs": duration_ms,
            "runtimeContexts": runtime_contexts,
            "coverage": coverage.get("coverage", self._factor_coverage_summary([], [])),
            "diagnostics": {
                "missingSymbols": coverage.get("missingSymbols", []),
                "insufficientSymbols": coverage.get("insufficientSymbols", []),
                "scannerSymbols": sorted(self._normalize_symbols(list((scanner_snapshot or {}).keys()))),
                "backtestSymbols": sorted(self._normalize_symbols(list((backtest_snapshot or {}).keys()))),
                "productionRuntimeChanged": False,
                "diagnosticOnly": True,
            },
            "snapshots": snapshot.get("snapshots", []),
            "warnings": list(dict.fromkeys([*coverage.get("warnings", []), *snapshot.get("warnings", [])])),
            "error": coverage.get("error"),
        }

    def query_signal_candidates(self, as_of_date: Any = None, limit: int = 100) -> list[dict]:
        disabled = self._disabled_result()
        if disabled:
            return []
        available, _version, _error = self._duckdb_status()
        if not available:
            return []

        as_of = self._parse_optional_date(as_of_date)
        normalized_limit = max(1, min(int(limit or 100), 1000))
        with self._connect(create_parent=True) as conn:
            if not self._schema_initialized(conn):
                return []
            if as_of is None:
                row = conn.execute("SELECT MAX(trade_date) FROM factor_daily").fetchone()
                as_of = row[0] if row else None
            if as_of is None:
                return []
            rows = conn.execute(
                """
                SELECT
                    symbol, trade_date, close, return_1d, log_return_1d,
                    ma5, ma10, ma20, ma60, volume_ma20, volatility_20d,
                    momentum_20d, close_vs_ma20, factor_score
                FROM factor_daily
                WHERE trade_date = ?
                ORDER BY factor_score DESC NULLS LAST, symbol
                LIMIT ?
                """,
                [as_of, normalized_limit],
            ).fetchall()
        return [
            {
                "symbol": row[0],
                "tradeDate": self._date_to_iso(row[1]),
                "close": row[2],
                "return1d": row[3],
                "logReturn1d": row[4],
                "ma5": row[5],
                "ma10": row[6],
                "ma20": row[7],
                "ma60": row[8],
                "volumeMa20": row[9],
                "volatility20d": row[10],
                "momentum20d": row[11],
                "closeVsMa20": row[12],
                "factorScore": row[13],
            }
            for row in rows
        ]

    def _factor_snapshot_from_rows(
        self,
        rows: list,
        *,
        requested_symbols: list[str],
        factors: list[str],
        started: float,
    ) -> dict:
        covered_symbols = sorted({row[0] for row in rows})
        missing_symbols = [symbol for symbol in requested_symbols if symbol not in covered_symbols]
        factor_dates = sorted({self._date_to_iso(row[1]) for row in rows if row[1] is not None})
        snapshots = []
        for row in rows:
            factor_values = {factor: row[index + 2] for index, factor in enumerate(factors)}
            snapshots.append(
                {
                    "symbol": row[0],
                    "tradeDate": self._date_to_iso(row[1]),
                    "factors": factor_values,
                    "factorTrend": self._factor_trend(factor_values.get("factor_score")),
                    "factorMomentum": self._factor_momentum(factor_values.get("momentum_20d")),
                    "factorDataMode": "real",
                    "factorWarnings": self._factor_warnings(factor_values),
                }
            )
        row_count = len(rows)
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        warnings = []
        if missing_symbols:
            warnings.append("missing_factor_symbols")
        return {
            "status": "ok" if row_count else "empty",
            "engine": "duckdb",
            "dataMode": "real" if row_count else "empty",
            "durationMs": duration_ms,
            "rowCount": row_count,
            "coverage": self._factor_coverage_summary(requested_symbols, covered_symbols, row_count, factor_dates),
            "factorDates": factor_dates,
            "missingSymbols": missing_symbols,
            "factors": factors,
            "snapshots": snapshots,
            "warnings": warnings,
            "error": None,
        }

    def _factor_validation_from_rows(
        self,
        rows: list,
        *,
        requested_symbols: list[str],
        min_factor_rows: int,
        started: float,
    ) -> dict:
        covered_by_symbol = {row[0]: int(row[1] or 0) for row in rows}
        covered_symbols = sorted(covered_by_symbol)
        missing_symbols = [symbol for symbol in requested_symbols if symbol not in covered_by_symbol]
        insufficient_symbols = [symbol for symbol, count in covered_by_symbol.items() if count < min_factor_rows]
        row_count = sum(covered_by_symbol.values())
        factor_dates = sorted(
            {
                self._date_to_iso(value)
                for row in rows
                for value in (row[2], row[3])
                if value is not None
            }
        )
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        status = "ok"
        if not row_count:
            status = "empty"
        elif missing_symbols or insufficient_symbols:
            status = "insufficient"
        warnings = []
        if missing_symbols:
            warnings.append("missing_factor_symbols")
        if insufficient_symbols:
            warnings.append("insufficient_factor_coverage")
        return {
            "status": status,
            "engine": "duckdb",
            "dataMode": "real" if row_count else "empty",
            "durationMs": duration_ms,
            "rowCount": row_count,
            "coverage": self._factor_coverage_summary(
                requested_symbols,
                covered_symbols,
                row_count,
                factor_dates,
                sufficient_symbols=[symbol for symbol, count in covered_by_symbol.items() if count >= min_factor_rows],
            ),
            "factorDates": factor_dates,
            "missingSymbols": missing_symbols,
            "insufficientSymbols": insufficient_symbols,
            "warnings": warnings,
            "error": None,
        }

    def _empty_factor_snapshot(self, status: str, requested_symbols: list[str], reason: str, *, data_mode: str = "empty") -> dict:
        return {
            "status": status,
            "engine": "duckdb",
            "dataMode": data_mode,
            "durationMs": 0.0,
            "rowCount": 0,
            "coverage": self._factor_coverage_summary(requested_symbols, []),
            "factorDates": [],
            "missingSymbols": requested_symbols,
            "factors": list(self.FACTOR_COLUMNS),
            "snapshots": [],
            "warnings": [reason] if reason else [],
            "error": reason if status in {"disabled", "unavailable", "invalid_request"} else None,
        }

    def _empty_factor_validation(self, status: str, requested_symbols: list[str], reason: str, *, data_mode: str = "empty") -> dict:
        return {
            "status": status,
            "engine": "duckdb",
            "dataMode": data_mode,
            "durationMs": 0.0,
            "rowCount": 0,
            "coverage": self._factor_coverage_summary(requested_symbols, []),
            "factorDates": [],
            "missingSymbols": requested_symbols,
            "insufficientSymbols": [],
            "warnings": [reason] if reason else [],
            "error": reason if status in {"disabled", "unavailable", "invalid_request"} else None,
        }

    @staticmethod
    def _factor_coverage_summary(
        requested_symbols: list[str],
        covered_symbols: list[str],
        row_count: int = 0,
        factor_dates: Optional[list[str]] = None,
        *,
        sufficient_symbols: Optional[list[str]] = None,
    ) -> dict:
        factor_dates = factor_dates or []
        sufficient = covered_symbols if sufficient_symbols is None else sufficient_symbols
        return {
            "requestedSymbols": len(requested_symbols),
            "coveredSymbols": len(covered_symbols),
            "missingSymbols": max(0, len(requested_symbols) - len(covered_symbols)),
            "sufficientSymbols": len(sufficient),
            "rowCount": row_count,
            "minFactorDate": min(factor_dates) if factor_dates else None,
            "maxFactorDate": max(factor_dates) if factor_dates else None,
        }

    def _database_exists(self) -> bool:
        return Path(self.database_path).exists()

    @classmethod
    def _normalize_factor_columns(cls, factors: Optional[list[str]]) -> list[str]:
        if not factors:
            return list(cls.FACTOR_COLUMNS)
        allowed = set(cls.FACTOR_COLUMNS)
        normalized = []
        seen = set()
        for factor in factors:
            value = str(factor or "").strip()
            if value in allowed and value not in seen:
                normalized.append(value)
                seen.add(value)
        return normalized or list(cls.FACTOR_COLUMNS)

    @staticmethod
    def _normalize_lookback_days(value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        return max(1, min(int(value), 3660))

    @staticmethod
    def _factor_trend(value: Optional[float]) -> str:
        if value is None:
            return "unknown"
        if value > 0:
            return "positive"
        if value < 0:
            return "negative"
        return "neutral"

    @staticmethod
    def _factor_momentum(value: Optional[float]) -> str:
        if value is None:
            return "unknown"
        if value > 0:
            return "positive"
        if value < 0:
            return "negative"
        return "neutral"

    @staticmethod
    def _factor_warnings(values: dict[str, Any]) -> list[str]:
        return ["partial_factor_row"] if any(value is None for value in values.values()) else []

    def _count_ohlcv_rows(self, start: Optional[date], end: Optional[date], limit: int) -> int:
        where_sql, params = self._date_filter_sql("trade_date", start, end, prefix="WHERE")
        with self._connect(create_parent=True) as conn:
            row = conn.execute(
                f"""
                WITH selected_symbols AS (
                    SELECT symbol
                    FROM ohlcv_daily
                    GROUP BY symbol
                    ORDER BY symbol
                    LIMIT ?
                ),
                scoped AS (
                    SELECT *
                    FROM ohlcv_daily
                    WHERE symbol IN (SELECT symbol FROM selected_symbols)
                )
                SELECT COUNT(*)
                FROM scoped
                {where_sql}
                """,
                [limit, *params],
            ).fetchone()
        return int(row[0] or 0)

    def _connect(self, *, create_parent: bool = False):
        duckdb = importlib.import_module("duckdb")
        db_path = Path(self.database_path)
        if create_parent:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(db_path))

    def _duckdb_status(self) -> tuple[bool, Optional[str], Optional[str]]:
        try:
            duckdb = importlib.import_module("duckdb")
            return True, str(getattr(duckdb, "__version__", "") or "unknown"), None
        except Exception as exc:
            return False, None, str(exc)

    @staticmethod
    def _schema_initialized(conn: Any) -> bool:
        rows = conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name IN ('ohlcv_daily', 'factor_daily')
            """
        ).fetchall()
        return {row[0] for row in rows} == {"ohlcv_daily", "factor_daily"}

    @staticmethod
    def _ensure_column(conn: Any, table_name: str, column_name: str, column_type_sql: str) -> None:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {column_type_sql}")

    @staticmethod
    def _safe_path(value: str) -> str:
        path = Path(value)
        return str(path) if not path.is_absolute() else path.name

    @staticmethod
    def _parse_date(value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value[:10])
        raise ValueError(f"Invalid date value: {value!r}")

    @classmethod
    def _parse_optional_date(cls, value: Any) -> Optional[date]:
        if value is None or value == "":
            return None
        return cls._parse_date(value)

    @classmethod
    def _normalize_ohlcv_row(cls, row: dict) -> tuple:
        symbol = str(row.get("symbol") or row.get("code") or "").strip().upper()
        if not symbol:
            raise ValueError("OHLCV row is missing symbol")
        trade_date = cls._parse_date(row.get("trade_date") or row.get("tradeDate") or row.get("date"))
        close = cls._float_or_none(row.get("close"))
        volume = cls._float_or_none(row.get("volume"))
        amount = cls._float_or_none(row.get("amount"))
        if amount is None and close is not None and volume is not None:
            amount = close * volume
        return (
            symbol,
            trade_date,
            cls._float_or_none(row.get("open")),
            cls._float_or_none(row.get("high")),
            cls._float_or_none(row.get("low")),
            close,
            volume,
            amount,
            cls._float_or_none(row.get("adj_close") or row.get("adjClose")),
            str(row.get("market") or "").strip().upper() or None,
            str(row.get("sector") or "").strip() or None,
            str(row.get("source") or "").strip() or None,
            row.get("ingested_at") or row.get("ingestedAt") or datetime.now(),
            datetime.now(),
        )

    @staticmethod
    def _float_or_none(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        return float(value)

    @staticmethod
    def _date_filter_sql(
        column_name: str,
        start: Optional[date],
        end: Optional[date],
        *,
        prefix: str = "WHERE",
    ) -> tuple[str, list]:
        clauses = []
        params: list[Any] = []
        if start is not None:
            clauses.append(f"{column_name} >= ?")
            params.append(start)
        if end is not None:
            clauses.append(f"{column_name} <= ?")
            params.append(end)
        if not clauses:
            return "", []
        return f"{prefix} " + " AND ".join(clauses), params

    @classmethod
    def _scope_filter_sql(
        cls,
        column_name: str,
        start: Optional[date],
        end: Optional[date],
        symbols: list[str],
        *,
        prefix: str = "WHERE",
    ) -> tuple[str, list]:
        date_sql, params = cls._date_filter_sql(column_name, start, end, prefix="")
        clauses = []
        if date_sql:
            clauses.append(date_sql.strip())
        if symbols:
            clauses.append("symbol IN (" + ", ".join(["?"] * len(symbols)) + ")")
            params.extend(symbols)
        if not clauses:
            return "", []
        return f"{prefix} " + " AND ".join(clauses), params

    def _normalize_symbol_limit(self, value: Any) -> int:
        if value is None or value == "":
            return self.max_benchmark_symbols
        return max(1, min(int(value), self.max_benchmark_symbols))

    @staticmethod
    def _normalize_symbols(symbols: Optional[list[str]]) -> list[str]:
        if not symbols:
            return []
        normalized = []
        seen = set()
        for symbol in symbols:
            value = str(symbol or "").strip().upper()
            if value and value not in seen:
                normalized.append(value)
                seen.add(value)
        return normalized

    @staticmethod
    def _records_from_rows(rows: Any) -> list[dict]:
        if rows is None:
            return []
        if hasattr(rows, "to_dict"):
            try:
                records = rows.to_dict(orient="records")
            except TypeError:
                records = rows.to_dict()
            if isinstance(records, list):
                return [dict(row) for row in records]
        return [dict(row) for row in rows]

    @staticmethod
    def _compact_source(records: list[dict]) -> str:
        sources = sorted({str(row.get("source") or "").strip() for row in records if row.get("source")})
        return ",".join(sources[:3]) or "payload"

    @classmethod
    def _ohlcv_record_from_stock_daily(cls, row: Any, *, fallback_symbol: str) -> dict:
        return {
            "symbol": getattr(row, "code", None) or fallback_symbol,
            "trade_date": cls._parse_date(getattr(row, "date", None)),
            "open": getattr(row, "open", None),
            "high": getattr(row, "high", None),
            "low": getattr(row, "low", None),
            "close": getattr(row, "close", None),
            "volume": getattr(row, "volume", None),
            "amount": getattr(row, "amount", None),
            "source": getattr(row, "data_source", None) or "stock_daily",
        }

    def _empty_coverage(self, status: str, reason: Optional[str]) -> dict:
        return {
            "status": status,
            "engine": "duckdb",
            "enabled": self.enabled,
            "databasePath": self._safe_path(self.database_path),
            "totalOhlcvRows": 0,
            "totalFactorRows": 0,
            "symbolCount": 0,
            "minTradeDate": None,
            "maxTradeDate": None,
            "latestFactorDate": None,
            "symbols": [],
            "emptyReason": reason,
            "error": reason if status in {"unavailable", "disabled"} else None,
        }

    @staticmethod
    def _date_to_iso(value: Any) -> Optional[str]:
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()[:10]
        return str(value)[:10]

    def _disabled_result(self) -> Optional[dict]:
        if self.enabled:
            return None
        return {"status": "disabled", "engine": "duckdb", "error": "DuckDB quant engine is disabled"}

    @staticmethod
    def _unavailable_result(error: Optional[str]) -> dict:
        return {"status": "unavailable", "engine": "duckdb", "error": error or "DuckDB is unavailable"}

    @staticmethod
    def _schema_missing_result() -> dict:
        return {"status": "unavailable", "engine": "duckdb", "error": "DuckDB quant schema is not initialized"}

    def _invalid_range_result(self, *, ingest: bool = False) -> dict:
        payload = {"status": "invalid_request", "engine": "duckdb", "error": "start_date must be on or before end_date"}
        if ingest:
            payload.update({"ingestedRows": 0, "symbolCount": 0, "availableRows": 0})
        else:
            payload.update({"ohlcvRows": 0, "factorRows": 0, "factorCount": self.FACTOR_COUNT})
        return payload

    def _benchmark_disabled_result(self, status: str) -> dict:
        return {
            "status": status,
            "engine": "duckdb",
            "elapsedMs": 0.0,
            "durationMs": 0.0,
            "ohlcvRows": 0,
            "factorRows": 0,
            "rowsScanned": 0,
            "symbolsScanned": 0,
            "symbolCount": 0,
            "dateCount": 0,
            "factorCount": self.FACTOR_COUNT,
            "queryType": "factor_daily_top_scores",
            "dataMode": "empty",
            "startDate": None,
            "endDate": None,
            "topResults": [],
        }
