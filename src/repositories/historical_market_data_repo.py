from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.services.historical_market_data_foundation import (
    HISTORICAL_MARKET_DATA_NORMALIZATION_VERSION,
    CanonicalHistoricalBar,
    HistoricalBarQualityOutcome,
    HistoricalPersistenceResult,
)


SCHEMA_VERSION = "historical_market_data_foundation_v1"


class HistoricalMarketDataRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self.apply_schema()

    @classmethod
    def sqlite(cls, path: str | Path) -> "HistoricalMarketDataRepository":
        resolved = Path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(resolved))
        return cls(conn)

    def apply_schema(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS historical_bars (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market TEXT NOT NULL,
                    venue TEXT NOT NULL,
                    canonical_symbol TEXT NOT NULL,
                    provider_symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    session_date TEXT NOT NULL,
                    timestamp TEXT,
                    timezone TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    adjustment_status TEXT NOT NULL,
                    adjustment_metadata TEXT NOT NULL DEFAULT '{}',
                    currency TEXT,
                    provider TEXT NOT NULL,
                    source TEXT NOT NULL,
                    observed_at TEXT,
                    as_of TEXT,
                    ingestion_id TEXT NOT NULL,
                    lineage_id TEXT NOT NULL,
                    normalization_version TEXT NOT NULL,
                    quality_state TEXT NOT NULL,
                    quality_reason_codes TEXT NOT NULL DEFAULT '[]',
                    raw_identity TEXT NOT NULL,
                    value_fingerprint TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (market, canonical_symbol, interval, session_date, provider, adjustment_status)
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS historical_bar_quality_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    normalization_version TEXT NOT NULL,
                    quality_state TEXT NOT NULL,
                    reason_codes TEXT NOT NULL,
                    product_readable INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self.conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uix_historical_bars_natural_key
                ON historical_bars (market, canonical_symbol, interval, session_date, provider, adjustment_status)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_historical_bars_lookup
                ON historical_bars (market, canonical_symbol, interval, session_date)
                """
            )

    def migration_report(self) -> dict[str, Any]:
        tables = set(self._table_names())
        indexes = set(self._index_names())
        return {
            "schemaVersion": SCHEMA_VERSION,
            "tables": {
                "historical_bars": "present" if "historical_bars" in tables else "missing",
                "historical_bar_quality_runs": "present" if "historical_bar_quality_runs" in tables else "missing",
            },
            "indexes": {
                "uix_historical_bars_natural_key": "present"
                if "uix_historical_bars_natural_key" in indexes
                else "missing",
                "ix_historical_bars_lookup": "present" if "ix_historical_bars_lookup" in indexes else "missing",
            },
            "rollback": {
                "supported": True,
                "strategy": "drop historical_bar_quality_runs then historical_bars before production backfill",
            },
        }

    def upsert_bars(
        self,
        bars: Sequence[CanonicalHistoricalBar],
        quality: HistoricalBarQualityOutcome,
    ) -> HistoricalPersistenceResult:
        inserted = updated = duplicates = conflicts = rejected = 0
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO historical_bar_quality_runs
                    (normalization_version, quality_state, reason_codes, product_readable)
                VALUES (?, ?, ?, ?)
                """,
                (
                    HISTORICAL_MARKET_DATA_NORMALIZATION_VERSION,
                    quality.state,
                    json.dumps(list(quality.reason_codes), ensure_ascii=True),
                    1 if quality.product_readable else 0,
                ),
            )
            if quality.state == "rejected":
                rejected = len(bars)
                for bar in bars:
                    existing = self._find_existing(bar)
                    if existing is not None and str(existing["value_fingerprint"]) != bar.value_fingerprint():
                        conflicts += 1
                return HistoricalPersistenceResult(rejected=rejected, conflicts=conflicts)
            for bar in bars:
                existing = self._find_existing(bar)
                if existing is None:
                    self.conn.execute(_INSERT_SQL, _bar_params(bar))
                    inserted += 1
                    continue
                if str(existing["value_fingerprint"]) == bar.value_fingerprint():
                    duplicates += 1
                    continue
                conflicts += 1
        return HistoricalPersistenceResult(
            inserted=inserted,
            updated=updated,
            duplicates=duplicates,
            conflicts=conflicts,
            rejected=rejected,
        )

    def query_bars(
        self,
        *,
        symbol: str,
        market: str,
        interval: str,
        start: date,
        end: date,
    ) -> list[CanonicalHistoricalBar]:
        rows = self.conn.execute(
            """
            SELECT * FROM historical_bars
            WHERE market = ?
              AND canonical_symbol = ?
              AND interval = ?
              AND session_date >= ?
              AND session_date <= ?
            ORDER BY session_date ASC, timestamp ASC, id ASC
            """,
            (market, symbol, interval, start.isoformat(), end.isoformat()),
        ).fetchall()
        return [_bar_from_row(row) for row in rows]

    def latest_bar(self, *, symbol: str, market: str, interval: str) -> CanonicalHistoricalBar | None:
        row = self.conn.execute(
            """
            SELECT * FROM historical_bars
            WHERE market = ? AND canonical_symbol = ? AND interval = ?
            ORDER BY session_date DESC, timestamp DESC, id DESC
            LIMIT 1
            """,
            (market, symbol, interval),
        ).fetchone()
        return _bar_from_row(row) if row is not None else None

    def _find_existing(self, bar: CanonicalHistoricalBar) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT * FROM historical_bars
            WHERE market = ?
              AND canonical_symbol = ?
              AND interval = ?
              AND session_date = ?
              AND provider = ?
              AND adjustment_status = ?
            LIMIT 1
            """,
            (
                bar.market,
                bar.canonical_symbol,
                bar.interval,
                bar.session_date.isoformat(),
                bar.provider,
                bar.adjustment_status,
            ),
        ).fetchone()

    def _table_names(self) -> list[str]:
        rows = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return [str(row[0]) for row in rows]

    def _index_names(self) -> list[str]:
        rows = self.conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        return [str(row[0]) for row in rows]


_INSERT_SQL = """
INSERT INTO historical_bars (
    market, venue, canonical_symbol, provider_symbol, interval, session_date,
    timestamp, timezone, open, high, low, close, volume, adjustment_status,
    adjustment_metadata, currency, provider, source, observed_at, as_of,
    ingestion_id, lineage_id, normalization_version, quality_state,
    quality_reason_codes, raw_identity, value_fingerprint
) VALUES (
    :market, :venue, :canonical_symbol, :provider_symbol, :interval, :session_date,
    :timestamp, :timezone, :open, :high, :low, :close, :volume, :adjustment_status,
    :adjustment_metadata, :currency, :provider, :source, :observed_at, :as_of,
    :ingestion_id, :lineage_id, :normalization_version, :quality_state,
    :quality_reason_codes, :raw_identity, :value_fingerprint
)
"""


def _bar_params(bar: CanonicalHistoricalBar) -> dict[str, Any]:
    return {
        "market": bar.market,
        "venue": bar.venue,
        "canonical_symbol": bar.canonical_symbol,
        "provider_symbol": bar.provider_symbol,
        "interval": bar.interval,
        "session_date": bar.session_date.isoformat(),
        "timestamp": bar.timestamp.isoformat() if bar.timestamp else None,
        "timezone": bar.timezone,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "adjustment_status": bar.adjustment_status,
        "adjustment_metadata": json.dumps(dict(bar.adjustment_metadata or {}), sort_keys=True, ensure_ascii=True),
        "currency": bar.currency,
        "provider": bar.provider,
        "source": bar.source,
        "observed_at": bar.observed_at.isoformat() if bar.observed_at else None,
        "as_of": bar.as_of.isoformat() if bar.as_of else None,
        "ingestion_id": bar.ingestion_id,
        "lineage_id": bar.lineage_id,
        "normalization_version": bar.normalization_version,
        "quality_state": bar.quality_state,
        "quality_reason_codes": json.dumps(list(bar.quality_reason_codes), ensure_ascii=True),
        "raw_identity": bar.raw_identity,
        "value_fingerprint": bar.value_fingerprint(),
    }


def _bar_from_row(row: Mapping[str, Any]) -> CanonicalHistoricalBar:
    adjustment_metadata = _json_mapping(row["adjustment_metadata"])
    quality_reason_codes = tuple(_json_list(row["quality_reason_codes"]))
    return CanonicalHistoricalBar(
        market=str(row["market"]),
        venue=str(row["venue"]),
        canonical_symbol=str(row["canonical_symbol"]),
        provider_symbol=str(row["provider_symbol"]),
        interval=str(row["interval"]),
        session_date=date.fromisoformat(str(row["session_date"])),
        timestamp=_parse_datetime(row["timestamp"]),
        timezone=str(row["timezone"]),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        volume=float(row["volume"]),
        adjustment_status=str(row["adjustment_status"]),
        adjustment_metadata=adjustment_metadata,
        currency=row["currency"],
        provider=str(row["provider"]),
        source=str(row["source"]),
        observed_at=_parse_datetime(row["observed_at"]),
        as_of=_parse_datetime(row["as_of"]),
        ingestion_id=str(row["ingestion_id"]),
        lineage_id=str(row["lineage_id"]),
        normalization_version=str(row["normalization_version"]),
        quality_state=str(row["quality_state"]),
        quality_reason_codes=quality_reason_codes,
        raw_identity=str(row["raw_identity"]),
    )


def _json_mapping(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _json_list(value: Any) -> list[str]:
    try:
        parsed = json.loads(str(value or "[]"))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value))


__all__ = ["HistoricalMarketDataRepository", "SCHEMA_VERSION"]
