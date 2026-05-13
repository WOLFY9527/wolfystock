# -*- coding: utf-8 -*-
"""Narrow provider-runtime adapter for StockService quote/name access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class StockServiceQuoteSnapshot:
    stock_code: str
    stock_name: Optional[str]
    current_price: float
    change: Optional[float]
    change_percent: Optional[float]
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    prev_close: Optional[float]
    volume: Optional[float]
    amount: Optional[float]


class StockServiceProviderAdapter:
    """Owns StockService-only quote/name access to provider runtime."""

    def __init__(self, *, manager_factory: Optional[Callable[[], Any]] = None) -> None:
        self._manager_factory = manager_factory
        self._manager: Any | None = None

    def get_stock_name(self, stock_code: str, *, allow_realtime: bool = False) -> Optional[str]:
        stock_name = self._get_manager().get_stock_name(stock_code, allow_realtime=allow_realtime)
        return None if stock_name is None else str(stock_name).strip()

    def get_quote_snapshot(self, stock_code: str) -> Optional[StockServiceQuoteSnapshot]:
        quote = self._get_manager().get_realtime_quote(stock_code)
        if quote is None:
            return None
        return StockServiceQuoteSnapshot(
            stock_code=getattr(quote, "code", stock_code),
            stock_name=getattr(quote, "name", None),
            current_price=getattr(quote, "price", 0.0) or 0.0,
            change=getattr(quote, "change_amount", None),
            change_percent=getattr(quote, "change_pct", None),
            open=getattr(quote, "open_price", None),
            high=getattr(quote, "high", None),
            low=getattr(quote, "low", None),
            prev_close=getattr(quote, "pre_close", None),
            volume=getattr(quote, "volume", None),
            amount=getattr(quote, "amount", None),
        )

    def _get_manager(self) -> Any:
        if self._manager is None:
            self._manager = self._create_manager()
        return self._manager

    def _create_manager(self) -> Any:
        if self._manager_factory is not None:
            return self._manager_factory()

        from data_provider.base import DataFetcherManager

        return DataFetcherManager()
