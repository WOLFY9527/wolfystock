# -*- coding: utf-8 -*-
"""US rotation radar quote provider built on the raw yfinance transport."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

import pandas as pd

from src.services.market_overview_yfinance_transport import fetch_yfinance_quote_history_frame

QuoteProvider = Callable[[Iterable[str]], Mapping[str, Any]]

_QUOTE_SOURCE = "yfinance_proxy"
_QUOTE_SOURCE_LABEL = "Yahoo Finance"
_QUOTE_MODE = "proxy"
_QUOTE_SOURCE_TYPE = "unofficial_public_api"


def get_rotation_radar_quote_provider() -> QuoteProvider:
    return load_rotation_radar_quotes


def load_rotation_radar_quotes(symbols: Iterable[str]) -> Dict[str, Any]:
    requested_symbols = tuple(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
    quotes: Dict[str, Dict[str, Any]] = {}
    as_of_candidates: list[str] = []
    freshness_counts: Dict[str, int] = {}
    source_counts: Dict[str, int] = {}
    source_label_counts: Dict[str, int] = {}

    for symbol in requested_symbols:
        try:
            frame = fetch_yfinance_quote_history_frame(symbol)
        except Exception:
            continue
        quote = _quote_from_history_frame(symbol, frame)
        if quote is None:
            continue
        quotes[symbol] = quote
        freshness = str(quote.get("freshness") or "unknown")
        freshness_counts[freshness] = freshness_counts.get(freshness, 0) + 1
        source = str(quote.get("source") or "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
        source_label = str(quote.get("sourceLabel") or source)
        source_label_counts[source_label] = source_label_counts.get(source_label, 0) + 1
        if quote.get("asOf"):
            as_of_candidates.append(str(quote["asOf"]))

    usable_symbol_count = len(quotes)
    requested_symbol_count = len(requested_symbols)
    coverage_percent = round((usable_symbol_count / requested_symbol_count) * 100, 1) if requested_symbol_count else 0.0
    freshness = _dominant_label(freshness_counts, default="fallback")
    as_of = max(as_of_candidates) if as_of_candidates else None

    return {
        "quotes": quotes,
        "metadata": {
            "quoteMode": _QUOTE_MODE,
            "sourceType": _QUOTE_SOURCE_TYPE,
            "freshness": freshness,
            "asOf": as_of,
            "noExternalCalls": False,
            "coverage": {
                "requestedSymbolCount": requested_symbol_count,
                "usableSymbolCount": usable_symbol_count,
                "coveragePercent": coverage_percent,
            },
            "sourceCounts": source_counts,
            "sourceLabelCounts": source_label_counts,
            "freshnessCounts": freshness_counts,
        },
    }


def _quote_from_history_frame(symbol: str, frame: Any) -> Optional[Dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return None
    try:
        last_row = frame.iloc[-1]
    except Exception:
        return None

    close = _number(_field(last_row, "Close", "close", "Adj Close", "adj_close"))
    previous_row = frame.iloc[-2] if len(frame) >= 2 else last_row
    previous_close = _number(_field(previous_row, "Close", "close", "Adj Close", "adj_close"))
    high = _number(_field(last_row, "High", "high"))
    low = _number(_field(last_row, "Low", "low"))
    volume = _number(_field(last_row, "Volume", "volume"))
    average_volume = _average_volume(frame)
    vwap = _number(_field(last_row, "VWAP", "vwap"))
    if vwap is None and None not in {high, low, close}:
        vwap = round((float(high) + float(low) + float(close)) / 3, 3)
    if close is None:
        return None

    change_percent = None
    if previous_close not in {None, 0}:
        change_percent = round(((float(close) - float(previous_close)) / float(previous_close)) * 100, 3)

    volume_ratio = None
    if volume is not None and average_volume not in {None, 0}:
        volume_ratio = round(float(volume) / float(average_volume), 3)

    as_of = _as_of_from_index(frame.index[-1] if len(frame.index) else None)
    freshness = _freshness_from_as_of(as_of)
    is_stale = freshness == "stale"

    time_windows = {
        "1d": {
            "changePercent": change_percent,
            "relativeVolume": volume_ratio,
            "freshness": freshness,
            "asOf": as_of,
        }
    }

    return {
        "symbol": symbol,
        "name": symbol,
        "price": close,
        "changePercent": change_percent,
        "volume": volume,
        "averageVolume": average_volume,
        "volumeRatio": volume_ratio,
        "vwap": vwap,
        "trend": _trend_from_frame(frame),
        "timeWindows": time_windows,
        "freshness": freshness,
        "isFallback": False,
        "isStale": is_stale,
        "source": _QUOTE_SOURCE,
        "sourceLabel": _QUOTE_SOURCE_LABEL,
        "sourceType": _QUOTE_SOURCE_TYPE,
        "asOf": as_of,
    }


def _field(row: Any, *names: str) -> Any:
    for name in names:
        if isinstance(row, Mapping) and name in row:
            return row.get(name)
        try:
            value = row[name]
        except Exception:
            continue
        if value is not None:
            return value
    return None


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if number != number:
        return None
    return number


def _average_volume(frame: Any) -> Optional[float]:
    try:
        volumes = [float(value) for value in frame.get("Volume", []) if value is not None]
    except Exception:
        return None
    if len(volumes) > 1:
        volumes = volumes[:-1]
    if not volumes:
        return None
    return round(sum(volumes) / len(volumes), 3)


def _trend_from_frame(frame: Any) -> list[float]:
    try:
        close_series = frame.get("Close", [])
    except Exception:
        return []
    values = []
    for value in close_series:
        number = _number(value)
        if number is not None:
            values.append(number)
    return values


def _as_of_from_index(index_value: Any) -> str:
    if index_value is None:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        timestamp = pd.Timestamp(index_value)
    except Exception:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone.utc)
    else:
        timestamp = timestamp.tz_convert(timezone.utc)
    return timestamp.isoformat()


def _freshness_from_as_of(as_of: str) -> str:
    try:
        parsed = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    except Exception:
        return "delayed"
    current = datetime.now(timezone.utc)
    return "stale" if (current - parsed).days >= 3 else "delayed"


def _dominant_label(counts: Mapping[str, int], *, default: str) -> str:
    if not counts:
        return default
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]
