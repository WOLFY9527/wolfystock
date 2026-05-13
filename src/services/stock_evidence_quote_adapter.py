# -*- coding: utf-8 -*-
"""Evidence-only adapter for realtime quote access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from data_provider.base import DataFetcherManager
from data_provider.realtime_types import UnifiedRealtimeQuote


@dataclass(frozen=True)
class StockEvidenceQuoteSnapshot:
    source: str
    price: Optional[float]
    change_pct: Optional[float]
    total_mv: Optional[float]
    pe_ratio: Optional[float]
    pb_ratio: Optional[float]
    market_timestamp: Optional[str]


class StockEvidenceQuoteAdapter:
    """Tiny boundary that isolates provider-runtime quote types for stock evidence."""

    def __init__(self, *, fetcher_manager: Any = None) -> None:
        self.fetcher_manager = fetcher_manager or DataFetcherManager()

    def get_quote_snapshot(self, symbol: str) -> Optional[StockEvidenceQuoteSnapshot]:
        quote = self.fetcher_manager.get_realtime_quote(symbol)
        if not isinstance(quote, UnifiedRealtimeQuote) or not quote.has_basic_data():
            return None
        source = getattr(getattr(quote, "source", None), "value", None) or str(getattr(quote, "source", "") or "")
        return StockEvidenceQuoteSnapshot(
            source=source or "realtime_quote",
            price=quote.price,
            change_pct=quote.change_pct,
            total_mv=quote.total_mv,
            pe_ratio=quote.pe_ratio,
            pb_ratio=quote.pb_ratio,
            market_timestamp=quote.market_timestamp,
        )
