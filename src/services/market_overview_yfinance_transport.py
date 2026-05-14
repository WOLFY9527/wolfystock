# -*- coding: utf-8 -*-
"""Raw yfinance transport helpers for Market Overview."""

from __future__ import annotations

from typing import Any

import yfinance as yf


def fetch_yfinance_quote_history_frame(ticker: str) -> Any:
    return yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)


def fetch_yfinance_spy_atr_history_frame() -> Any:
    return yf.Ticker("SPY").history(period="1mo", interval="1d", auto_adjust=False)
