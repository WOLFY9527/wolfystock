# -*- coding: utf-8 -*-
"""Raw Binance HTTP transport helpers for Market Overview crypto paths."""

from __future__ import annotations

import json
from typing import Any, Sequence

import requests


BINANCE_TIMEOUT_SECONDS = 2


def fetch_binance_ticker_snapshot(symbols: Sequence[str]) -> Any:
    response = requests.get(
        "https://api.binance.com/api/v3/ticker/24hr",
        params={"symbols": json.dumps(list(symbols), separators=(",", ":"))},
        timeout=BINANCE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def fetch_binance_kline_history_rows(symbol: str) -> Any:
    response = requests.get(
        "https://api.binance.com/api/v3/klines",
        params={"symbol": symbol, "interval": "1d", "limit": 8},
        timeout=BINANCE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def fetch_binance_funding_row(symbol: str) -> Any:
    response = requests.get(
        "https://fapi.binance.com/fapi/v1/premiumIndex",
        params={"symbol": symbol},
        timeout=BINANCE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()
