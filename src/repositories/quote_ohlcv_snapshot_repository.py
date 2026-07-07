from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from src.services.quote_ohlcv_snapshot_lineage import (
    QUOTE_OHLCV_SNAPSHOT_CONTRACT_VERSION,
    QuoteOhlcvSnapshotPersistenceResult,
    QuoteOhlcvSnapshotRecord,
    snapshot_from_storage_payload,
)


SCHEMA_VERSION = "quote_ohlcv_snapshot_lineage_v1"


class QuoteOhlcvSnapshotRepository:
    """Small SQLite persistence boundary for quote/OHLCV snapshot read models."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self.apply_schema()

    @classmethod
    def sqlite(cls, path: str | Path) -> "QuoteOhlcvSnapshotRepository":
        resolved = Path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return cls(sqlite3.connect(str(resolved)))

    def apply_schema(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quote_ohlcv_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    snapshot_kind TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    market TEXT NOT NULL,
                    quote_as_of TEXT,
                    bar_trade_date_time TEXT,
                    retrieval_time TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    authority_state TEXT NOT NULL,
                    display_state TEXT NOT NULL,
                    freshness_state TEXT NOT NULL,
                    coverage_state TEXT NOT NULL,
                    ohlcv_basis TEXT,
                    lineage_ref TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_quote_ohlcv_snapshots_symbol_lookup
                ON quote_ohlcv_snapshots (market, symbol, snapshot_kind, retrieval_time)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_quote_ohlcv_snapshots_lineage_ref
                ON quote_ohlcv_snapshots (lineage_ref)
                """
            )

    def upsert_snapshot(self, snapshot: QuoteOhlcvSnapshotRecord) -> QuoteOhlcvSnapshotPersistenceResult:
        existing = self.get_snapshot(snapshot.snapshot_id)
        if existing is not None:
            return QuoteOhlcvSnapshotPersistenceResult(snapshot_id=snapshot.snapshot_id, inserted=False)
        payload = snapshot.storage_payload()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO quote_ohlcv_snapshots (
                    snapshot_id, snapshot_kind, symbol, market, quote_as_of,
                    bar_trade_date_time, retrieval_time, source_id, source_type,
                    authority_state, display_state, freshness_state, coverage_state,
                    ohlcv_basis, lineage_ref, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.snapshot_kind,
                    snapshot.symbol,
                    snapshot.market,
                    payload.get("quoteAsOf"),
                    payload.get("barTradeDateTime"),
                    payload.get("retrievalTime"),
                    snapshot.source_id,
                    snapshot.source_type,
                    snapshot.authority_state,
                    snapshot.display_state,
                    snapshot.freshness_state,
                    snapshot.coverage_state,
                    snapshot.ohlcv_basis,
                    snapshot.lineage_ref,
                    json.dumps(payload, sort_keys=True, ensure_ascii=True),
                ),
            )
        return QuoteOhlcvSnapshotPersistenceResult(snapshot_id=snapshot.snapshot_id, inserted=True)

    def get_snapshot(self, snapshot_id: str) -> QuoteOhlcvSnapshotRecord | None:
        row = self.conn.execute(
            """
            SELECT payload FROM quote_ohlcv_snapshots
            WHERE snapshot_id = ?
            LIMIT 1
            """,
            (str(snapshot_id or "").strip(),),
        ).fetchone()
        if row is None:
            return None
        return snapshot_from_storage_payload(_json_mapping(row["payload"]))

    def latest_for_symbol(
        self,
        *,
        symbol: str,
        market: str,
        snapshot_kind: str,
    ) -> QuoteOhlcvSnapshotRecord | None:
        row = self.conn.execute(
            """
            SELECT payload FROM quote_ohlcv_snapshots
            WHERE symbol = ? AND market = ? AND snapshot_kind = ?
            ORDER BY retrieval_time DESC, created_at DESC
            LIMIT 1
            """,
            (symbol, market, snapshot_kind),
        ).fetchone()
        if row is None:
            return None
        return snapshot_from_storage_payload(_json_mapping(row["payload"]))

    def migration_report(self) -> dict[str, Any]:
        tables = set(self._table_names())
        indexes = set(self._index_names())
        return {
            "schemaVersion": SCHEMA_VERSION,
            "contractVersion": QUOTE_OHLCV_SNAPSHOT_CONTRACT_VERSION,
            "tables": {
                "quote_ohlcv_snapshots": "present" if "quote_ohlcv_snapshots" in tables else "missing",
            },
            "indexes": {
                "ix_quote_ohlcv_snapshots_symbol_lookup": "present"
                if "ix_quote_ohlcv_snapshots_symbol_lookup" in indexes
                else "missing",
                "ix_quote_ohlcv_snapshots_lineage_ref": "present"
                if "ix_quote_ohlcv_snapshots_lineage_ref" in indexes
                else "missing",
            },
            "rollback": {
                "supported": True,
                "strategy": "drop quote_ohlcv_snapshots before any production promotion",
            },
        }

    def _table_names(self) -> list[str]:
        rows = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return [str(row[0]) for row in rows]

    def _index_names(self) -> list[str]:
        rows = self.conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        return [str(row[0]) for row in rows]


def _json_mapping(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


__all__ = ["QuoteOhlcvSnapshotRepository", "SCHEMA_VERSION"]
