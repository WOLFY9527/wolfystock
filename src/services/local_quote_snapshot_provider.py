from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.quote_snapshot_readiness import (
    QuoteSnapshot,
    QuoteSnapshotProviderResult,
    QuoteSnapshotReadinessRequest,
)


class LocalQuoteSnapshotJsonProvider:
    """Read-only local quote snapshot cache reader.

    Supported cache shapes are either `{"quotes": [...]}` or a top-level list of
    quote rows. The reader intentionally has no write method.
    """

    def __init__(self, *, cache_path: str | Path | None = None) -> None:
        self.cache_path = Path(str(cache_path)).expanduser() if cache_path else None

    def fetch_quote_snapshots(
        self,
        request: QuoteSnapshotReadinessRequest,
    ) -> QuoteSnapshotProviderResult:
        if self.cache_path is None:
            return QuoteSnapshotProviderResult.unavailable("provider_missing")
        try:
            raw_text = self.cache_path.read_text(encoding="utf-8")
        except OSError:
            return QuoteSnapshotProviderResult.unavailable("provider_missing")
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            return QuoteSnapshotProviderResult.unavailable("provider_unavailable")

        requested = {str(symbol or "").strip().upper() for symbol in request.symbols}
        rows = payload.get("quotes") if isinstance(payload, Mapping) else payload
        if not isinstance(rows, list):
            return QuoteSnapshotProviderResult.unavailable("provider_unavailable")

        snapshots: list[QuoteSnapshot] = []
        for row in rows:
            snapshot = _snapshot_from_row(row)
            if snapshot is None:
                continue
            if snapshot.symbol not in requested:
                continue
            snapshots.append(snapshot)
        if not snapshots:
            return QuoteSnapshotProviderResult.unavailable("provider_missing")
        return QuoteSnapshotProviderResult.available(snapshots)


def _snapshot_from_row(row: Any) -> QuoteSnapshot | None:
    if not isinstance(row, Mapping):
        return None
    symbol = str(row.get("symbol") or "").strip().upper()
    if not symbol:
        return None
    market = str(row.get("market") or "us").strip().lower()
    last = _float_or_none(row.get("last", row.get("price")))
    if last is None or last <= 0:
        return None
    as_of = _datetime_or_none(row.get("asOf") or row.get("timestamp"))
    if as_of is None:
        return None
    return QuoteSnapshot(
        symbol=symbol,
        market=market,
        last=last,
        previous_close=_float_or_none(row.get("previousClose", row.get("previous_close"))),
        volume=_float_or_none(row.get("volume")),
        as_of=as_of,
        currency=str(row.get("currency") or "").strip().upper() or None,
        source=str(row.get("source") or "local_quote_snapshot_cache").strip(),
    )


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _datetime_or_none(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        normalized = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


__all__ = ["LocalQuoteSnapshotJsonProvider"]
