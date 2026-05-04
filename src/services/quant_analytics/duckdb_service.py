# -*- coding: utf-8 -*-
"""Optional DuckDB quant analytics accelerator skeleton."""

from __future__ import annotations

import importlib
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from src.config import Config, get_config


class QuantDuckDBService:
    """Small, explicitly-invoked DuckDB service for quant research data."""

    FACTOR_COUNT = 8

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
        available, version, error = self._duckdb_status()
        payload = {
            "enabled": self.enabled,
            "available": available,
            "databasePath": self._safe_path(self.database_path),
            "parquetRoot": self._safe_path(self.parquet_root),
            "version": version,
            "error": error,
            "schemaInitialized": False,
            "status": "disabled" if not self.enabled else "ok",
            "engine": "duckdb",
        }
        if not available:
            payload["status"] = "unavailable"
            return payload
        if not self.enabled:
            return payload

        try:
            with self._connect() as conn:
                payload["schemaInitialized"] = self._schema_initialized(conn)
        except Exception as exc:
            payload["status"] = "unavailable"
            payload["error"] = str(exc)
        return payload

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
                  symbol TEXT,
                  trade_date DATE,
                  open DOUBLE,
                  high DOUBLE,
                  low DOUBLE,
                  close DOUBLE,
                  volume DOUBLE,
                  amount DOUBLE,
                  market TEXT,
                  sector TEXT,
                  source TEXT,
                  updated_at TIMESTAMP,
                  PRIMARY KEY(symbol, trade_date)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS factor_daily(
                  symbol TEXT,
                  trade_date DATE,
                  close DOUBLE,
                  ma5 DOUBLE,
                  ma20 DOUBLE,
                  ma60 DOUBLE,
                  momentum20 DOUBLE,
                  momentum60 DOUBLE,
                  vol20 DOUBLE,
                  dollar_volume20 DOUBLE,
                  factor_score DOUBLE,
                  updated_at TIMESTAMP,
                  PRIMARY KEY(symbol, trade_date)
                )
                """
            )
        return {"status": "ok", "engine": "duckdb", "version": version, "schemaInitialized": True}

    def ingest_ohlcv_rows(self, rows: list[dict]) -> dict:
        disabled = self._disabled_result()
        if disabled:
            return disabled
        available, _version, error = self._duckdb_status()
        if not available:
            return self._unavailable_result(error)
        if not rows:
            return {"status": "empty", "ingestedRows": 0, "symbolCount": 0}

        parsed_rows = [self._normalize_ohlcv_row(row) for row in rows]
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
                        market, sector, source, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    parsed_rows,
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

        return {
            "status": "ok",
            "ingestedRows": len(parsed_rows),
            "symbolCount": len({row[0] for row in parsed_rows}),
        }

    def build_basic_factors(self, start_date: Any = None, end_date: Any = None) -> dict:
        disabled = self._disabled_result()
        if disabled:
            return disabled
        available, _version, error = self._duckdb_status()
        if not available:
            return self._unavailable_result(error)

        start = self._parse_optional_date(start_date)
        end = self._parse_optional_date(end_date)
        where_sql, params = self._date_filter_sql("trade_date", start, end)
        with self._connect(create_parent=True) as conn:
            if not self._schema_initialized(conn):
                return self._schema_missing_result()
            ohlcv_rows = conn.execute(f"SELECT COUNT(*) FROM ohlcv_daily {where_sql}", params).fetchone()[0]
            if int(ohlcv_rows or 0) == 0:
                return {"status": "empty", "engine": "duckdb", "ohlcvRows": 0, "factorRows": 0}

            conn.execute("BEGIN TRANSACTION")
            try:
                conn.execute(f"DELETE FROM factor_daily {where_sql}", params)
                conn.execute(
                    f"""
                    INSERT INTO factor_daily (
                        symbol, trade_date, close, ma5, ma20, ma60,
                        momentum20, momentum60, vol20, dollar_volume20,
                        factor_score, updated_at
                    )
                    WITH computed AS (
                        SELECT
                            symbol,
                            trade_date,
                            close,
                            AVG(close) OVER (
                                PARTITION BY symbol ORDER BY trade_date
                                ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
                            ) AS ma5,
                            AVG(close) OVER (
                                PARTITION BY symbol ORDER BY trade_date
                                ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                            ) AS ma20,
                            AVG(close) OVER (
                                PARTITION BY symbol ORDER BY trade_date
                                ROWS BETWEEN 59 PRECEDING AND CURRENT ROW
                            ) AS ma60,
                            close - LAG(close, 20) OVER (
                                PARTITION BY symbol ORDER BY trade_date
                            ) AS momentum20,
                            close - LAG(close, 60) OVER (
                                PARTITION BY symbol ORDER BY trade_date
                            ) AS momentum60,
                            STDDEV_SAMP(close) OVER (
                                PARTITION BY symbol ORDER BY trade_date
                                ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                            ) AS vol20,
                            AVG(close * volume) OVER (
                                PARTITION BY symbol ORDER BY trade_date
                                ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                            ) AS dollar_volume20
                        FROM ohlcv_daily
                    )
                    SELECT
                        symbol,
                        trade_date,
                        close,
                        ma5,
                        ma20,
                        ma60,
                        momentum20,
                        momentum60,
                        vol20,
                        dollar_volume20,
                        COALESCE(momentum20, 0) - COALESCE(vol20, 0) AS factor_score,
                        CURRENT_TIMESTAMP
                    FROM computed
                    {where_sql}
                    """,
                    params,
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

            factor_rows = conn.execute(f"SELECT COUNT(*) FROM factor_daily {where_sql}", params).fetchone()[0]
        return {
            "status": "ok",
            "engine": "duckdb",
            "ohlcvRows": int(ohlcv_rows or 0),
            "factorRows": int(factor_rows or 0),
            "factorCount": self.FACTOR_COUNT,
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
                    AVG(factor_score) AS avg_factor_score
                FROM scoped
                {where_sql}
                """,
                [limit, *params],
            ).fetchone()
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        factor_rows = int(row[0] or 0)
        if factor_rows == 0:
            return {
                "status": "empty",
                "engine": "duckdb",
                "elapsedMs": elapsed_ms,
                "ohlcvRows": 0,
                "factorRows": 0,
                "symbolCount": 0,
                "dateCount": 0,
                "factorCount": self.FACTOR_COUNT,
            }
        return {
            "status": "ok",
            "engine": "duckdb",
            "elapsedMs": elapsed_ms,
            "ohlcvRows": self._count_ohlcv_rows(start, end, limit),
            "factorRows": factor_rows,
            "symbolCount": int(row[1] or 0),
            "dateCount": int(row[2] or 0),
            "factorCount": self.FACTOR_COUNT,
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
                    symbol, trade_date, close, ma5, ma20, ma60,
                    momentum20, momentum60, vol20, dollar_volume20,
                    factor_score
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
                "tradeDate": row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1]),
                "close": row[2],
                "ma5": row[3],
                "ma20": row[4],
                "ma60": row[5],
                "momentum20": row[6],
                "momentum60": row[7],
                "vol20": row[8],
                "dollarVolume20": row[9],
                "factorScore": row[10],
            }
            for row in rows
        ]

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
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            raise ValueError("OHLCV row is missing symbol")
        trade_date = cls._parse_date(row.get("trade_date") or row.get("tradeDate"))
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
            str(row.get("market") or "").strip().upper() or None,
            str(row.get("sector") or "").strip() or None,
            str(row.get("source") or "").strip() or None,
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

    def _normalize_symbol_limit(self, value: Any) -> int:
        if value is None or value == "":
            return self.max_benchmark_symbols
        return max(1, min(int(value), self.max_benchmark_symbols))

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

    def _benchmark_disabled_result(self, status: str) -> dict:
        return {
            "status": status,
            "engine": "duckdb",
            "elapsedMs": 0.0,
            "ohlcvRows": 0,
            "factorRows": 0,
            "symbolCount": 0,
            "dateCount": 0,
            "factorCount": self.FACTOR_COUNT,
        }
