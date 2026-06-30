"""Bounded starter market-data universe shared by product readiness surfaces."""

from __future__ import annotations

from typing import Any


STARTER_MARKET_DATA_SYMBOLS: tuple[str, ...] = ("SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA")


def normalize_starter_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def is_starter_market_data_symbol(value: Any) -> bool:
    return normalize_starter_symbol(value) in STARTER_MARKET_DATA_SYMBOLS


__all__ = [
    "STARTER_MARKET_DATA_SYMBOLS",
    "is_starter_market_data_symbol",
    "normalize_starter_symbol",
]
